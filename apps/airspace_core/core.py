import logging
import threading
from collections import defaultdict

import paho.mqtt.client as mqtt
import stmpy

from apps.airspace_core.mission import build_default_route
from apps.airspace_core.rules import conflict_advisories, zone_advisories
from shared.config import CONFLICT_CHECK_INTERVAL_MS, MQTT_BROKER_HOST, MQTT_BROKER_PORT
from shared.models import ActivationStatus
from shared.schemas import ActivationMessage, AirspaceEvent, RegisterMessage, TelemetryMessage, Zone
from shared.topics import (
    AIRSPACE_EVENT,
    DRONE_ACTIVATION,
    DRONE_REGISTER_ALL,
    DRONE_TELEMETRY_ALL,
    MANNED_POSITION_ALL,
    ZONE_UPDATE,
)

logger = logging.getLogger(__name__)


class DroneRegistryMachine:
    def __init__(self, service: "AirspaceCore", register_msg: RegisterMessage):
        self.service = service
        self.register_msg = register_msg
        self.drone_id = register_msg.drone_id
        self.mission_counter = 0
        self.stm = self._build_machine()

    def _build_machine(self):
        transitions = [
            {"source": "initial", "target": "registered", "effect": "on_registered"},
            {"trigger": "activate", "source": "registered", "target": "active", "effect": "on_activate"},
            {"trigger": "delay", "source": "registered", "target": "registered", "effect": "on_delay"},
            {"trigger": "complete", "source": "active", "target": "registered", "effect": "on_complete"},
        ]
        return stmpy.Machine(name=f"registry-{self.drone_id}", transitions=transitions, obj=self)

    def on_registered(self):
        self.service.publish_event("drone_registered", self.drone_id, "Drone registered")
        self.stm.send("activate")

    def on_activate(self):
        mission_id = f"{self.drone_id}-mission-{self.mission_counter:03d}"
        route = build_default_route(self.service.next_route_index())
        activation = ActivationMessage(
            drone_id=self.drone_id,
            status=ActivationStatus.APPROVED.value,
            mission_id=mission_id,
            route=route,
            reason="Mission assigned by airspace core",
        )
        self.mission_counter += 1
        self.service.activations[self.drone_id] = activation
        self.service.mqtt_client.publish(DRONE_ACTIVATION.format(drone_id=self.drone_id), activation.to_json())
        self.service.publish_event("drone_activated", self.drone_id, f"Mission {mission_id} assigned")

    def on_delay(self):
        self.service.publish_event("drone_delayed", self.drone_id, "Activation delayed")

    def on_complete(self):
        self.service.publish_event("mission_completed", self.drone_id, "Drone returned to registered")


class ConflictMonitorMachine:
    def __init__(self, service: "AirspaceCore"):
        self.service = service
        self.stm = self._build_machine()

    def _build_machine(self):
        transitions = [
            {"source": "initial", "target": "monitoring", "effect": "schedule"},
            {"trigger": "tick", "source": "monitoring", "target": "monitoring", "effect": "run_scan"},
        ]
        return stmpy.Machine(name="conflict-monitor", transitions=transitions, obj=self)

    def schedule(self):
        self.stm.start_timer("tick", CONFLICT_CHECK_INTERVAL_MS)

    def run_scan(self):
        advisories = []
        advisories.extend(zone_advisories(self.service.drones, self.service.zones))
        advisories.extend(conflict_advisories(self.service.drones, self.service.manned))
        for advisory in advisories:
            self.service.publish_advisory(advisory)
        self.schedule()


class AirspaceCore:
    def __init__(self, broker_host: str = MQTT_BROKER_HOST, broker_port: int = MQTT_BROKER_PORT):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="airspace-core",
        )
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message

        self.driver = stmpy.Driver()
        self.conflict_monitor = ConflictMonitorMachine(self)
        self.route_index = 0

        self.registry_machines: dict[str, DroneRegistryMachine] = {}
        self.activations: dict[str, ActivationMessage] = {}
        self.drones: dict[str, TelemetryMessage] = {}
        self.manned: dict[str, TelemetryMessage] = {}
        self.zones = self._default_zones()
        self.events: list[AirspaceEvent] = []
        self.active_advisories: dict[str, list[str]] = defaultdict(list)
        self._lock = threading.Lock()

    def _default_zones(self) -> list[Zone]:
        from shared.config import DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON
        from shared.schemas import Position

        return [
            Zone(
                zone_id="hospital-helipad",
                name="Hospital Helipad Priority Zone",
                center=Position(lat=DEFAULT_CENTER_LAT + 0.01, lon=DEFAULT_CENTER_LON - 0.01, alt=60),
                radius_m=250,
                min_alt_m=0,
                max_alt_m=150,
                restricted=True,
            )
        ]

    def next_route_index(self) -> int:
        current = self.route_index
        self.route_index += 1
        return current

    def start(self):
        self.driver.add_machine(self.conflict_monitor.stm)
        self.driver.start(keep_active=True)
        self.mqtt_client.connect(self.broker_host, self.broker_port)
        self.mqtt_client.loop_start()
        self.mqtt_client.publish(ZONE_UPDATE, self._zones_payload())
        logger.info("Airspace core started")

    def stop(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.driver.stop()

    def publish_event(self, event_type: str, entity_id: str, details: str):
        event = AirspaceEvent(event_type=event_type, entity_id=entity_id, details=details)
        self.events.insert(0, event)
        del self.events[100:]
        self.mqtt_client.publish(AIRSPACE_EVENT, event.to_json())

    def publish_advisory(self, advisory):
        from shared.topics import DRONE_ADVISORY

        self.mqtt_client.publish(DRONE_ADVISORY.format(drone_id=advisory.drone_id), advisory.to_json())
        self.publish_event("advisory", advisory.drone_id, advisory.details)

    def _zones_payload(self) -> str:
        import json
        from dataclasses import asdict

        return json.dumps([asdict(zone) for zone in self.zones])

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        client.subscribe(DRONE_REGISTER_ALL)
        client.subscribe(DRONE_TELEMETRY_ALL)
        client.subscribe(MANNED_POSITION_ALL)
        logger.info("Connected to MQTT broker")

    def _on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if parts[1] == "drone" and parts[3] == "register":
            self._handle_register(RegisterMessage.from_json(msg.payload))
        elif parts[1] == "drone" and parts[3] == "telemetry":
            self._handle_telemetry(TelemetryMessage.from_json(msg.payload))
        elif parts[1] == "manned":
            self._handle_manned(TelemetryMessage.from_json(msg.payload))

    def _handle_register(self, register_msg: RegisterMessage):
        with self._lock:
            if register_msg.drone_id in self.registry_machines:
                self.publish_event("re_register", register_msg.drone_id, "Duplicate registration treated as idempotent")
                return
            machine = DroneRegistryMachine(self, register_msg)
            self.registry_machines[register_msg.drone_id] = machine
            self.driver.add_machine(machine.stm)

    def _handle_telemetry(self, telemetry: TelemetryMessage):
        self.drones[telemetry.drone_id] = telemetry

    def _handle_manned(self, telemetry: TelemetryMessage):
        self.manned[telemetry.drone_id] = telemetry
