import logging
import time

import paho.mqtt.client as mqtt
import stmpy

from shared.config import (
    DEFAULT_CRUISE_ALTITUDE_M,
    DEFAULT_CRUISE_SPEED_MS,
    DEFAULT_DRONE_COUNT,
    DEFAULT_VERTICAL_SPEED_MS,
    EVASION_HEADING_CHANGE_DEG,
    EVASION_TIMEOUT_S,
    EVASION_VERTICAL_SPEED_MS,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    TELEMETRY_INTERVAL_MS,
)
from shared.geo import bearing_between, haversine_distance, move_position
from shared.models import AdvisoryType, DroneState
from shared.schemas import ActivationMessage, AdvisoryMessage, ControlMessage, Position, RegisterMessage, TelemetryMessage
from shared.topics import DRONE_ACTIVATION, DRONE_ADVISORY, DRONE_CONTROL, DRONE_REGISTER, DRONE_TELEMETRY

logger = logging.getLogger(__name__)


class DroneFlightMachine:
    def __init__(self, drone_id: str, mqtt_client: mqtt.Client):
        self.drone_id = drone_id
        self.mqtt_client = mqtt_client
        self.position = Position(lat=63.4305, lon=10.3951, alt=0.0)
        self.heading = 0.0
        self.speed = 0.0
        self.vertical_speed = 0.0
        self.battery = 100.0
        self.state = DroneState.REGISTERED
        self.route = []
        self.current_waypoint_index = 0
        self.mission_id = ""
        self.last_advisory: AdvisoryMessage | None = None
        self.evasion_started_at = 0.0
        self.stm = self._build_machine()

    def _build_machine(self):
        states = [
            {"name": "registered", "entry": "publish_registration"},
            {"name": "idle"},
            {"name": "takeoff", "t_tick": "tick_takeoff"},
            {"name": "airborne", "t_tick": "tick_airborne"},
            {"name": "evading", "t_tick": "tick_evading", "advisory": "refresh_advisory"},
            {"name": "landing", "t_tick": "tick_landing"},
        ]
        transitions = [
            {"source": "initial", "target": "registered"},
            {"trigger": "registration_done", "source": "registered", "target": "idle"},
            {"trigger": "activate", "source": "idle", "target": "takeoff", "effect": "start_mission"},
            {"trigger": "cruise", "source": "takeoff", "target": "airborne", "effect": "enter_airborne"},
            {"trigger": "advisory", "source": "takeoff", "target": "evading", "effect": "enter_evading"},
            {"trigger": "advisory", "source": "airborne", "target": "evading", "effect": "enter_evading"},
            {"trigger": "clear", "source": "evading", "target": "airborne", "effect": "resume_route"},
            {"trigger": "land", "source": "airborne", "target": "landing", "effect": "start_landing"},
            {"trigger": "complete", "source": "landing", "target": "idle", "effect": "complete_mission"},
        ]
        return stmpy.Machine(name=self.drone_id, transitions=transitions, states=states, obj=self)

    def publish_registration(self):
        message = RegisterMessage(
            drone_id=self.drone_id,
            drone_type="quadcopter",
            operator="simulator",
            max_altitude=DEFAULT_CRUISE_ALTITUDE_M,
            max_speed=DEFAULT_CRUISE_SPEED_MS,
        )
        self.mqtt_client.publish(DRONE_REGISTER.format(drone_id=self.drone_id), message.to_json())
        self.stm.send("registration_done")

    def start_mission(self):
        self.state = DroneState.ACTIVATED
        self.speed = DEFAULT_CRUISE_SPEED_MS * 0.4
        self.vertical_speed = DEFAULT_VERTICAL_SPEED_MS
        self.current_waypoint_index = 1 if len(self.route) > 1 else 0
        if self.route:
            self.position = Position(self.route[0].lat, self.route[0].lon, 0.0)
        if len(self.route) > 1:
            self.heading = bearing_between(self.route[0], self.route[1])
        self._schedule_tick()

    def tick_takeoff(self):
        self.state = DroneState.TAKEOFF
        self._advance()
        if self.position.alt >= DEFAULT_CRUISE_ALTITUDE_M:
            self.position.alt = DEFAULT_CRUISE_ALTITUDE_M
            self.stm.send("cruise")
            return
        self._schedule_tick()

    def enter_airborne(self):
        self.state = DroneState.AIRBORNE
        self.speed = DEFAULT_CRUISE_SPEED_MS
        self.vertical_speed = 0.0
        self._schedule_tick()

    def tick_airborne(self):
        self._advance()
        if self.current_waypoint_index < len(self.route):
            target = self.route[self.current_waypoint_index]
            if haversine_distance(self.position, target) < 25:
                self.current_waypoint_index += 1
                if self.current_waypoint_index >= len(self.route):
                    self.stm.send("land")
                    return
                self.heading = bearing_between(self.position, self.route[self.current_waypoint_index])
        self._schedule_tick()

    def enter_evading(self):
        self.state = DroneState.EVADING
        self.evasion_started_at = time.time()
        self._apply_advisory()
        self._schedule_tick()

    def refresh_advisory(self):
        self._apply_advisory()

    def _apply_advisory(self):
        advisory = self.last_advisory
        if not advisory:
            return
        if advisory.advisory_type == AdvisoryType.TURN_RIGHT.value:
            self.heading = (self.heading + EVASION_HEADING_CHANGE_DEG) % 360
        elif advisory.advisory_type == AdvisoryType.TURN_LEFT.value:
            self.heading = (self.heading - EVASION_HEADING_CHANGE_DEG) % 360
        elif advisory.advisory_type == AdvisoryType.CLIMB.value:
            self.vertical_speed = EVASION_VERTICAL_SPEED_MS
        elif advisory.advisory_type == AdvisoryType.DESCEND.value:
            self.vertical_speed = -EVASION_VERTICAL_SPEED_MS
        elif advisory.advisory_type in {AdvisoryType.HOLD_POSITION.value, AdvisoryType.ABORT_MISSION.value}:
            self.speed = 0.0
            self.vertical_speed = 0.0

    def tick_evading(self):
        self._advance()
        if self.last_advisory and self.last_advisory.advisory_type == AdvisoryType.CLEAR_OF_CONFLICT.value:
            self.stm.send("clear")
            return
        if time.time() - self.evasion_started_at > EVASION_TIMEOUT_S:
            self.stm.send("clear")
            return
        self._schedule_tick()

    def resume_route(self):
        self.state = DroneState.AIRBORNE
        self.speed = DEFAULT_CRUISE_SPEED_MS
        self.vertical_speed = 0.0
        if self.current_waypoint_index < len(self.route):
            self.heading = bearing_between(self.position, self.route[self.current_waypoint_index])
        self._schedule_tick()

    def start_landing(self):
        self.state = DroneState.LANDING
        self.speed = DEFAULT_CRUISE_SPEED_MS * 0.35
        self.vertical_speed = -DEFAULT_VERTICAL_SPEED_MS
        self._schedule_tick()

    def tick_landing(self):
        self._advance()
        if self.position.alt <= 0:
            self.position.alt = 0.0
            self.stm.send("complete")
            return
        self._schedule_tick()

    def complete_mission(self):
        self.state = DroneState.COMPLETED
        self.speed = 0.0
        self.vertical_speed = 0.0
        self._publish_telemetry()
        self.state = DroneState.IDLE

    def accept_activation(self, activation: ActivationMessage):
        self.route = activation.route
        self.mission_id = activation.mission_id
        self.stm.send("activate")

    def accept_advisory(self, advisory: AdvisoryMessage):
        self.last_advisory = advisory
        self.stm.send("advisory")

    def accept_control(self, heading_delta: float, throttle_delta: float):
        self.heading = (self.heading + heading_delta) % 360
        self.vertical_speed += throttle_delta

    def _advance(self):
        self.position = move_position(
            self.position, self.heading, self.speed, self.vertical_speed, TELEMETRY_INTERVAL_MS / 1000.0
        )
        self.battery = max(0.0, self.battery - 0.02)
        self._publish_telemetry()

    def _publish_telemetry(self):
        telemetry = TelemetryMessage(
            drone_id=self.drone_id,
            timestamp=time.time(),
            position=self.position,
            heading=self.heading,
            speed=self.speed,
            vertical_speed=self.vertical_speed,
            state=self.state.value,
            battery=self.battery,
            mission_id=self.mission_id,
        )
        self.mqtt_client.publish(DRONE_TELEMETRY.format(drone_id=self.drone_id), telemetry.to_json())

    def _schedule_tick(self):
        self.stm.start_timer("t_tick", TELEMETRY_INTERVAL_MS)


class SimulatorService:
    def __init__(self, drones: int = DEFAULT_DRONE_COUNT, broker_host: str = MQTT_BROKER_HOST, broker_port: int = MQTT_BROKER_PORT):
        self.drone_count = drones
        self.driver = stmpy.Driver()
        self.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="drone-simulator",
        )
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.drones: dict[str, DroneFlightMachine] = {}

    def start(self):
        for index in range(self.drone_count):
            drone_id = f"drone-{index:03d}"
            machine = DroneFlightMachine(drone_id, self.mqtt_client)
            self.drones[drone_id] = machine
        self.mqtt_client.connect(self.broker_host, self.broker_port)
        self.mqtt_client.loop_start()
        for machine in self.drones.values():
            self.driver.add_machine(machine.stm)
        self.driver.start(keep_active=True)
        logger.info("Simulator started with %s drones", self.drone_count)

    def stop(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.driver.stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        for drone_id in self.drones:
            client.subscribe(DRONE_ACTIVATION.format(drone_id=drone_id))
            client.subscribe(DRONE_ADVISORY.format(drone_id=drone_id))
            client.subscribe(DRONE_CONTROL.format(drone_id=drone_id))
        logger.info("Simulator connected to MQTT broker")

    def _on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        drone_id = parts[2]
        if parts[3] == "activation":
            self.drones[drone_id].accept_activation(ActivationMessage.from_json(msg.payload))
        elif parts[3] == "advisory":
            self.drones[drone_id].accept_advisory(AdvisoryMessage.from_json(msg.payload))
        elif parts[3] == "control":
            payload = ControlMessage.from_json(msg.payload)
            self.drones[drone_id].accept_control(payload.heading_delta, payload.throttle_delta)
