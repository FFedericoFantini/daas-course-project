import logging
import threading
from collections import defaultdict
from dataclasses import dataclass

import paho.mqtt.client as mqtt
import stmpy

from apps.airspace_core.mission import build_default_route, build_requested_route, validate_activation_route
from apps.airspace_core.rules import conflict_advisories, zone_advisories
from shared.config import CONFLICT_CHECK_INTERVAL_MS, MQTT_BROKER_HOST, MQTT_BROKER_PORT
from shared.models import ActivationStatus, AdvisoryType, AdvisorySeverity, DroneState
from shared.schemas import (
    ActivationMessage,
    AdvisoryMessage,
    AirspaceEvent,
    MissionRequestMessage,
    RegisterMessage,
    TelemetryMessage,
    Zone,
    ZoneCommandMessage,
)
from shared.topics import (
    AIRSPACE_EVENT,
    DRONE_ACTIVATION,
    DRONE_REGISTER_ALL,
    DRONE_SPAWN_REQUEST,
    DRONE_TELEMETRY_ALL,
    MANNED_POSITION_ALL,
    MISSION_REQUEST,
    ZONE_COMMAND,
    ZONE_UPDATE,
)

logger = logging.getLogger(__name__)

ACTIVE_TELEMETRY_STATES = {
    DroneState.ACTIVATED.value,
    DroneState.TAKEOFF.value,
    DroneState.AIRBORNE.value,
    DroneState.MANUAL.value,
    DroneState.EVADING.value,
    DroneState.LANDING.value,
}

INACTIVE_TELEMETRY_STATES = {
    DroneState.IDLE.value,
    DroneState.COMPLETED.value,
    DroneState.ABORTED.value,
    DroneState.OFFLINE.value,
}


@dataclass
class ParticipantLifecycle:
    drone_id: str
    lifecycle_state: str = DroneState.OFFLINE.value
    drone_type: str = ""
    operator: str = ""
    max_altitude: float = 0.0
    max_speed: float = 0.0
    last_register_at: float = 0.0
    last_telemetry_at: float = 0.0
    last_reported_state: str = DroneState.OFFLINE.value
    active_mission_id: str = ""
    last_activation_at: float = 0.0
    last_activation_status: str = ""
    last_event_at: float = 0.0
    last_event_type: str = ""
    completed_mission_count: int = 0
    last_completed_mission_id: str = ""
    last_completed_at: float = 0.0
    last_terminal_state: str = ""
    activation_count: int = 0
    registration_count: int = 0
    refresh_count: int = 0


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
        self.service._record_registration(self.register_msg)
        self.service.publish_event("drone_registered", self.drone_id, "Drone registered")
        self.stm.send("activate")

    def on_activate(self):
        activation = self.service._create_activation_for_drone(self.drone_id, self.mission_counter)
        self.mission_counter += 1
        self.service._record_activation(activation)
        self.service.mqtt_client.publish(DRONE_ACTIVATION.format(drone_id=self.drone_id), activation.to_json())
        self.service.publish_event("drone_activated", self.drone_id, f"Mission {activation.mission_id} assigned")

    def on_delay(self):
        self.service.publish_event("drone_delayed", self.drone_id, "Activation delayed")

    def on_complete(self):
        self.service._mark_participant_inactive(self.drone_id, "Mission completed and drone returned to idle")
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
        active_now = {advisory.drone_id for advisory in advisories}
        previously_active = set(self.service.active_advisories.keys())
        for advisory in advisories:
            self.service.publish_advisory(advisory)
        for drone_id in previously_active - active_now:
            clear_advisory = AdvisoryMessage(
                drone_id=drone_id,
                advisory_type=AdvisoryType.CLEAR_OF_CONFLICT.value,
                severity=AdvisorySeverity.WARNING.value,
                threat_id="",
                details="Conflict clear: return to nominal route and altitude",
            )
            self.service.publish_advisory(clear_advisory)
        self.service.active_advisories = defaultdict(list)
        for advisory in advisories:
            self.service.active_advisories[advisory.drone_id].append(advisory.threat_id)
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
        self.participants: dict[str, ParticipantLifecycle] = {}
        self.activations: dict[str, ActivationMessage] = {}
        self.pending_mission_requests: dict[str, MissionRequestMessage] = {}
        self.drones: dict[str, TelemetryMessage] = {}
        self.manned: dict[str, TelemetryMessage] = {}
        self.zones = self._default_zones()
        self.events: list[AirspaceEvent] = []
        self.active_advisories: dict[str, list[str]] = defaultdict(list)
        self._lock = threading.Lock()

    def _default_zones(self) -> list[Zone]:
        return []

    def next_route_index(self) -> int:
        current = self.route_index
        self.route_index += 1
        return current

    def start(self):
        self.driver.add_machine(self.conflict_monitor.stm)
        self.driver.start(keep_active=True)
        self.mqtt_client.connect(self.broker_host, self.broker_port)
        self.mqtt_client.loop_start()
        self._publish_zones()
        logger.info("Airspace core started")

    def stop(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.driver.stop()

    def publish_event(self, event_type: str, entity_id: str, details: str):
        event = AirspaceEvent(event_type=event_type, entity_id=entity_id, details=details)
        participant = self.participants.get(entity_id)
        if participant is not None:
            participant.last_event_at = event.timestamp
            participant.last_event_type = event_type
        self.events.insert(0, event)
        del self.events[100:]
        self.mqtt_client.publish(AIRSPACE_EVENT, event.to_json())

    def publish_advisory(self, advisory):
        from shared.topics import DRONE_ADVISORY

        self.mqtt_client.publish(DRONE_ADVISORY.format(drone_id=advisory.drone_id), advisory.to_json())
        self.publish_event("advisory", advisory.drone_id, advisory.details)

    def _participant(self, drone_id: str) -> ParticipantLifecycle:
        participant = self.participants.get(drone_id)
        if participant is None:
            participant = ParticipantLifecycle(drone_id=drone_id)
            self.participants[drone_id] = participant
        return participant

    def _apply_registration_metadata(self, participant: ParticipantLifecycle, register_msg: RegisterMessage):
        participant.drone_type = register_msg.drone_type
        participant.operator = register_msg.operator
        participant.max_altitude = register_msg.max_altitude
        participant.max_speed = register_msg.max_speed
        participant.last_register_at = register_msg.timestamp

    def _record_registration(self, register_msg: RegisterMessage):
        participant = self._participant(register_msg.drone_id)
        self._apply_registration_metadata(participant, register_msg)
        participant.registration_count += 1
        participant.last_reported_state = DroneState.REGISTERED.value
        participant.lifecycle_state = DroneState.REGISTERED.value

    def _refresh_registration(self, register_msg: RegisterMessage):
        participant = self._participant(register_msg.drone_id)
        self._apply_registration_metadata(participant, register_msg)
        participant.refresh_count += 1
        if participant.lifecycle_state == DroneState.OFFLINE.value:
            participant.lifecycle_state = DroneState.REGISTERED.value
            participant.last_reported_state = DroneState.REGISTERED.value

    def _record_activation(self, activation: ActivationMessage):
        participant = self._participant(activation.drone_id)
        existing = self.activations.get(activation.drone_id)
        participant.lifecycle_state = "active"
        participant.active_mission_id = activation.mission_id
        participant.last_activation_at = activation.timestamp
        participant.last_activation_status = activation.status
        participant.last_reported_state = DroneState.ACTIVATED.value
        if existing is None or existing.mission_id != activation.mission_id:
            participant.activation_count += 1
        self.activations[activation.drone_id] = activation

    def _create_activation_for_drone(self, drone_id: str, mission_counter: int) -> ActivationMessage:
        request = self.pending_mission_requests.pop(drone_id, None)
        mission_id = f"{drone_id}-mission-{mission_counter:03d}"
        route = build_default_route(self.next_route_index())
        reason = "Mission assigned by airspace core"

        if request is not None:
            requested_route = build_requested_route(request.pickup, request.dropoff)
            validation_error = validate_activation_route(requested_route)
            if validation_error is None:
                route = requested_route
                reason = "Mission assigned from planner request"
            else:
                self.publish_event(
                    "mission_route_fallback",
                    drone_id,
                    f"{validation_error}. Default route assigned instead.",
                )

        validation_error = validate_activation_route(route)
        if validation_error is not None:
            raise ValueError(f"Invalid activation route for {drone_id}: {validation_error}")

        return ActivationMessage(
            drone_id=drone_id,
            status=ActivationStatus.APPROVED.value,
            mission_id=mission_id,
            route=route,
            reason=reason,
        )

    def _handle_mission_request(self, request: MissionRequestMessage):
        drone_id = request.drone_id
        with self._lock:
            if drone_id in self.pending_mission_requests:
                self.publish_event("mission_request_rejected", drone_id, "A pending mission request already exists")
                return
            if drone_id in self.participants:
                self.publish_event(
                    "mission_request_rejected",
                    drone_id,
                    "Drone id already exists in the monitored airspace",
                )
                return
            self.pending_mission_requests[drone_id] = request
            self.publish_event(
                "mission_requested",
                drone_id,
                f"Mission requested from planner: pickup ({request.pickup.lat:.5f}, {request.pickup.lon:.5f})"
                f" -> dropoff ({request.dropoff.lat:.5f}, {request.dropoff.lon:.5f})",
            )
        self.mqtt_client.publish(DRONE_SPAWN_REQUEST, request.to_json())

    def _mark_participant_inactive(self, drone_id: str, details: str):
        participant = self._participant(drone_id)
        participant.lifecycle_state = "inactive"
        participant.active_mission_id = ""
        participant.last_reported_state = DroneState.IDLE.value
        self.publish_event("drone_inactive", drone_id, details)

    def _finalize_mission_from_telemetry(self, telemetry: TelemetryMessage):
        participant = self._participant(telemetry.drone_id)
        mission_id = telemetry.mission_id or participant.active_mission_id
        event_type = "mission_completed" if telemetry.state == DroneState.COMPLETED.value else "mission_aborted"

        if mission_id and participant.last_completed_mission_id != mission_id:
            participant.completed_mission_count += 1
            participant.last_completed_mission_id = mission_id
            participant.last_completed_at = telemetry.timestamp
            participant.last_terminal_state = telemetry.state
            self.publish_event(
                event_type,
                telemetry.drone_id,
                f"Mission {mission_id} reached terminal state {telemetry.state}",
            )

        participant.lifecycle_state = "inactive"
        participant.active_mission_id = ""

    def _update_lifecycle_from_telemetry(self, telemetry: TelemetryMessage):
        participant = self._participant(telemetry.drone_id)
        previous_state = participant.lifecycle_state
        participant.last_telemetry_at = telemetry.timestamp
        participant.last_reported_state = telemetry.state
        if telemetry.mission_id:
            participant.active_mission_id = telemetry.mission_id

        if telemetry.reduced_accuracy:
            participant.lifecycle_state = "degraded"
            if previous_state != "degraded":
                self.publish_event(
                    "drone_degraded",
                    telemetry.drone_id,
                    f"Telemetry quality degraded while drone reported {telemetry.state}",
                )
            return

        if telemetry.state == DroneState.REGISTERED.value:
            participant.lifecycle_state = DroneState.REGISTERED.value
            return

        if telemetry.state in ACTIVE_TELEMETRY_STATES:
            participant.lifecycle_state = "active"
            if previous_state == "degraded":
                self.publish_event(
                    "drone_restored",
                    telemetry.drone_id,
                    f"Telemetry restored while drone reported {telemetry.state}",
                )
            return

        if telemetry.state in {DroneState.COMPLETED.value, DroneState.ABORTED.value}:
            self._finalize_mission_from_telemetry(telemetry)
            return

        if telemetry.state in INACTIVE_TELEMETRY_STATES:
            participant.lifecycle_state = "inactive"
            participant.active_mission_id = ""
            if previous_state != "inactive":
                self.publish_event(
                    "drone_inactive",
                    telemetry.drone_id,
                    f"Drone became inactive after reporting {telemetry.state}",
                )
            return

    def _publish_zones(self):
        self.mqtt_client.publish(ZONE_UPDATE, self._zones_payload())

    def _zones_payload(self) -> str:
        import json
        from dataclasses import asdict

        return json.dumps([asdict(zone) for zone in self.zones])

    def _upsert_zone(self, zone: Zone):
        for index, existing in enumerate(self.zones):
            if existing.zone_id == zone.zone_id:
                self.zones[index] = zone
                self.publish_event("zone_updated", zone.zone_id, f"Constraint {zone.name} updated")
                self._publish_zones()
                return
        self.zones.append(zone)
        self.publish_event("zone_created", zone.zone_id, f"Constraint {zone.name} activated")
        self._publish_zones()

    def _remove_zone(self, zone_id: str):
        for index, existing in enumerate(self.zones):
            if existing.zone_id == zone_id:
                removed = self.zones.pop(index)
                self.publish_event("zone_removed", zone_id, f"Constraint {removed.name} removed")
                self._publish_zones()
                return
        self.publish_event("zone_missing", zone_id, "Constraint removal ignored because the zone does not exist")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        client.subscribe(DRONE_REGISTER_ALL)
        client.subscribe(DRONE_TELEMETRY_ALL)
        client.subscribe(MANNED_POSITION_ALL)
        client.subscribe(ZONE_COMMAND)
        client.subscribe(MISSION_REQUEST)
        logger.info("Connected to MQTT broker")

    def _on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if parts[1] == "drone" and parts[3] == "register":
            self._handle_register(RegisterMessage.from_json(msg.payload))
        elif parts[1] == "drone" and parts[3] == "telemetry":
            self._handle_telemetry(TelemetryMessage.from_json(msg.payload))
        elif parts[1] == "manned":
            self._handle_manned(TelemetryMessage.from_json(msg.payload))
        elif msg.topic == ZONE_COMMAND:
            self._handle_zone_command(ZoneCommandMessage.from_json(msg.payload))
        elif msg.topic == MISSION_REQUEST:
            self._handle_mission_request(MissionRequestMessage.from_json(msg.payload))

    def _handle_register(self, register_msg: RegisterMessage):
        with self._lock:
            if register_msg.drone_id in self.registry_machines:
                self._refresh_registration(register_msg)
                self.publish_event("re_register", register_msg.drone_id, "Duplicate registration treated as idempotent")
                return
            machine = DroneRegistryMachine(self, register_msg)
            self.registry_machines[register_msg.drone_id] = machine
            self.driver.add_machine(machine.stm)

    def _handle_telemetry(self, telemetry: TelemetryMessage):
        self.drones[telemetry.drone_id] = telemetry
        self._update_lifecycle_from_telemetry(telemetry)

    def _handle_manned(self, telemetry: TelemetryMessage):
        self.manned[telemetry.drone_id] = telemetry

    def _handle_zone_command(self, command: ZoneCommandMessage):
        with self._lock:
            if command.action == "upsert":
                if not command.zone:
                    self.publish_event("zone_rejected", command.zone_id or "unknown", "Zone update missing payload")
                    return
                self._upsert_zone(command.zone)
                return
            if command.action == "remove":
                if not command.zone_id:
                    self.publish_event("zone_rejected", "unknown", "Zone removal missing zone_id")
                    return
                self._remove_zone(command.zone_id)
                return
            self.publish_event("zone_rejected", command.zone_id or "unknown", f"Unsupported zone action {command.action}")
