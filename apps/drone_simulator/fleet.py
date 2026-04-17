import logging
import math
import re
import time
import json

import paho.mqtt.client as mqtt
import stmpy

from shared.config import (
    DEFAULT_MANUAL_DRONE_ID,
    DEFAULT_CRUISE_SPEED_MS,
    DEFAULT_CRUISE_ALTITUDE_M,
    DEFAULT_DRONE_COUNT,
    DEFAULT_VERTICAL_SPEED_MS,
    EVASION_HEADING_CHANGE_DEG,
    EVASION_TIMEOUT_S,
    EVASION_VERTICAL_SPEED_MS,
    MANUAL_DRONE_MAX_SPEED_MS,
    MIN_OPERATIONAL_ALTITUDE_M,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    TELEMETRY_INTERVAL_MS,
    VERTICAL_SEPARATION_M,
)
from shared.geo import bearing_between, haversine_distance, meters_to_lat, meters_to_lon, move_position
from shared.models import AdvisoryType, DroneState
from shared.schemas import (
    ActivationMessage,
    AdvisoryMessage,
    ControlMessage,
    MissionRequestMessage,
    Position,
    RegisterMessage,
    TelemetryMessage,
    Zone,
)
from shared.topics import DRONE_ACTIVATION, DRONE_ADVISORY, DRONE_CONTROL, DRONE_REGISTER, DRONE_SPAWN_REQUEST, DRONE_TELEMETRY, ZONE_UPDATE

logger = logging.getLogger(__name__)
ALTITUDE_TARGET_PATTERN = re.compile(r"change altitude to (\d+(?:\.\d+)?)m")
HEADING_TARGET_PATTERN = re.compile(r"heading (\d+(?:\.\d+)?)deg")
ZONE_DETOUR_BACKTRACK_M = 80.0


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def project_on_segment(start: Position, end: Position, point: Position) -> Position:
    avg_lat_rad = math.radians((start.lat + end.lat) / 2)
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = max(1e-6, meters_per_deg_lat * math.cos(avg_lat_rad))

    end_x = (end.lon - start.lon) * meters_per_deg_lon
    end_y = (end.lat - start.lat) * meters_per_deg_lat
    point_x = (point.lon - start.lon) * meters_per_deg_lon
    point_y = (point.lat - start.lat) * meters_per_deg_lat
    segment_length_sq = (end_x * end_x) + (end_y * end_y)

    if segment_length_sq <= 1e-6:
        return Position(lat=start.lat, lon=start.lon, alt=point.alt)

    t = clamp(((point_x * end_x) + (point_y * end_y)) / segment_length_sq, 0.0, 1.0)
    projected_x = end_x * t
    projected_y = end_y * t

    return Position(
        lat=start.lat + (projected_y / meters_per_deg_lat),
        lon=start.lon + (projected_x / meters_per_deg_lon),
        alt=point.alt,
    )


class DroneFlightMachine:
    def __init__(
        self,
        drone_id: str,
        mqtt_client: mqtt.Client,
        zone_catalog: dict[str, Zone],
        *,
        drone_type: str = "quadcopter",
        operator: str = "simulator",
        max_altitude: float = DEFAULT_CRUISE_ALTITUDE_M,
        max_speed: float = DEFAULT_CRUISE_SPEED_MS,
    ):
        self.drone_id = drone_id
        self.mqtt_client = mqtt_client
        self.zone_catalog = zone_catalog
        self.drone_type = drone_type
        self.operator = operator
        self.max_altitude = max_altitude
        self.max_speed = max_speed
        self.position = Position(lat=63.4305, lon=10.3951, alt=0.0)
        self.heading = 0.0
        self.speed = 0.0
        self.vertical_speed = 0.0
        self.battery = 100.0
        self.state = DroneState.REGISTERED
        self.nominal_altitude = max_altitude
        self.altitude_target = max_altitude
        self.route = []
        self.nominal_route = []
        self.landing_site: Position | None = None
        self.zone_detour_active = False
        self.active_zone_detour_id: str | None = None
        self.zone_detour_resume_at = 0.0
        self.zone_detour_destination: Position | None = None
        self.current_waypoint_index = 0
        self.mission_id = ""
        self.last_advisory: AdvisoryMessage | None = None
        self.last_applied_advisory_key: tuple[str, str, str] | None = None
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
            {"trigger": "activate", "source": "registered", "target": "takeoff", "effect": "start_mission"},
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
            drone_type=self.drone_type,
            operator=self.operator,
            max_altitude=self.max_altitude,
            max_speed=self.max_speed,
        )
        self.mqtt_client.publish(DRONE_REGISTER.format(drone_id=self.drone_id), message.to_json())
        self.stm.send("registration_done")

    def start_mission(self):
        self.state = DroneState.ACTIVATED
        self.speed = DEFAULT_CRUISE_SPEED_MS * 0.4
        self.vertical_speed = DEFAULT_VERTICAL_SPEED_MS
        self.altitude_target = self.nominal_altitude
        self.landing_site = self.route[-1] if self.route else None
        self.current_waypoint_index = 1 if len(self.route) > 1 else 0
        if self.route:
            self.position = Position(self.route[0].lat, self.route[0].lon, 0.0)
        if len(self.route) > 1:
            self.heading = bearing_between(self.route[0], self.route[1])
        self._schedule_tick()

    def tick_takeoff(self):
        self.state = DroneState.TAKEOFF
        self.altitude_target = self.nominal_altitude
        self._track_altitude_target(DEFAULT_VERTICAL_SPEED_MS)
        self._advance()
        if abs(self.position.alt - self.nominal_altitude) <= 1.0 or self.position.alt >= self.nominal_altitude:
            self.position.alt = self.nominal_altitude
            self.vertical_speed = 0.0
            self.stm.send("cruise")
            return
        self._schedule_tick()

    def enter_airborne(self):
        self.state = DroneState.AIRBORNE
        self.speed = DEFAULT_CRUISE_SPEED_MS
        self.altitude_target = self.nominal_altitude
        self.last_applied_advisory_key = None
        self._track_altitude_target(DEFAULT_VERTICAL_SPEED_MS)
        self._schedule_tick()

    def tick_airborne(self):
        self._track_altitude_target(DEFAULT_VERTICAL_SPEED_MS)
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
        self._apply_advisory(force=True)
        self._schedule_tick()

    def refresh_advisory(self):
        self._apply_advisory()

    def _apply_advisory(self, force: bool = False):
        advisory = self.last_advisory
        if not advisory:
            return
        advisory_key = (advisory.advisory_type, advisory.threat_id, advisory.details)
        if not force and advisory_key == self.last_applied_advisory_key:
            return
        self.last_applied_advisory_key = advisory_key
        if advisory.advisory_type == AdvisoryType.TURN_RIGHT.value:
            if self.zone_detour_active and advisory.threat_id == self.active_zone_detour_id:
                return
            if not self._apply_zone_detour():
                self.heading = self._advisory_target_heading((self.heading + EVASION_HEADING_CHANGE_DEG) % 360)
            self.altitude_target = self.nominal_altitude
        elif advisory.advisory_type == AdvisoryType.TURN_LEFT.value:
            if self.zone_detour_active and advisory.threat_id == self.active_zone_detour_id:
                return
            if not self._apply_zone_detour():
                self.heading = self._advisory_target_heading((self.heading - EVASION_HEADING_CHANGE_DEG) % 360)
            self.altitude_target = self.nominal_altitude
        elif advisory.advisory_type == AdvisoryType.CLIMB.value:
            self.altitude_target = self._advisory_target_altitude(self.nominal_altitude + VERTICAL_SEPARATION_M)
            self._track_altitude_target(EVASION_VERTICAL_SPEED_MS)
        elif advisory.advisory_type == AdvisoryType.DESCEND.value:
            self.altitude_target = self._advisory_target_altitude(
                max(MIN_OPERATIONAL_ALTITUDE_M, self.nominal_altitude - VERTICAL_SEPARATION_M)
            )
            self._track_altitude_target(EVASION_VERTICAL_SPEED_MS)
        elif advisory.advisory_type in {AdvisoryType.HOLD_POSITION.value, AdvisoryType.ABORT_MISSION.value}:
            self.speed = 0.0
            self.vertical_speed = 0.0

    def tick_evading(self):
        self._track_altitude_target(EVASION_VERTICAL_SPEED_MS)
        if self.zone_detour_active and time.time() < self.zone_detour_resume_at:
            self.speed = 0.0
            self._publish_telemetry()
            self._schedule_tick()
            return

        if self.zone_detour_active and self.speed <= 0.0:
            self.speed = DEFAULT_CRUISE_SPEED_MS * 0.85

        self._advance()
        if self.current_waypoint_index < len(self.route):
            target = self.route[self.current_waypoint_index]
            if haversine_distance(self.position, target) < 25:
                self.current_waypoint_index += 1
                if self.current_waypoint_index < len(self.route):
                    self.heading = bearing_between(self.position, self.route[self.current_waypoint_index])

        if self.zone_detour_active:
            if self.current_waypoint_index >= len(self.route):
                self.stm.send("clear")
                return
        elif self.last_advisory and self.last_advisory.advisory_type == AdvisoryType.CLEAR_OF_CONFLICT.value:
            self.stm.send("clear")
            return
        if time.time() - self.evasion_started_at > EVASION_TIMEOUT_S:
            self.stm.send("clear")
            return
        self._schedule_tick()

    def resume_route(self):
        self.state = DroneState.AIRBORNE
        self.speed = DEFAULT_CRUISE_SPEED_MS
        self.altitude_target = self.nominal_altitude
        self.last_applied_advisory_key = None
        self._track_altitude_target(DEFAULT_VERTICAL_SPEED_MS)
        if self.zone_detour_active:
            destination = self.zone_detour_destination or (self.nominal_route[-1] if self.nominal_route else self.position)
            self.zone_detour_active = False
            self.active_zone_detour_id = None
            self.zone_detour_resume_at = 0.0
            self.zone_detour_destination = None
            if haversine_distance(self.position, destination) > 15:
                self.route = [self.position, destination]
            else:
                self.route = [self.position]
            self.current_waypoint_index = 1 if len(self.route) > 1 else 0
        elif len(self.nominal_route) >= 2:
            final_target = self.nominal_route[-1]
            recovery_point = project_on_segment(self.nominal_route[0], final_target, self.position)
            if haversine_distance(self.position, recovery_point) > 20:
                self.route = [self.position, recovery_point, final_target]
            else:
                self.route = [self.position, final_target]
            self.current_waypoint_index = 1
        if self.current_waypoint_index < len(self.route):
            self.heading = bearing_between(self.position, self.route[self.current_waypoint_index])
        self._schedule_tick()

    def start_landing(self):
        self.state = DroneState.LANDING
        if self.landing_site is not None:
            self.position = Position(self.landing_site.lat, self.landing_site.lon, self.position.alt)
        self.speed = 0.0
        self.vertical_speed = -DEFAULT_VERTICAL_SPEED_MS
        self.altitude_target = 0.0
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
        self.altitude_target = 0.0
        self._publish_telemetry()
        self.state = DroneState.IDLE

    def accept_activation(self, activation: ActivationMessage):
        if self.state not in {DroneState.IDLE, DroneState.REGISTERED}:
            if self.mission_id == activation.mission_id:
                return
            logger.warning(
                "[%s] Ignoring activation for mission %s while in state %s (current mission %s)",
                self.drone_id,
                activation.mission_id,
                self.state.value,
                self.mission_id or "none",
            )
            return
        self.route = list(activation.route)
        self.nominal_route = list(activation.route)
        self.zone_detour_active = False
        self.active_zone_detour_id = None
        self.zone_detour_resume_at = 0.0
        self.zone_detour_destination = None
        self.mission_id = activation.mission_id
        self.stm.send("activate")

    def accept_advisory(self, advisory: AdvisoryMessage):
        self.last_advisory = advisory
        self.stm.send("advisory")

    def accept_control(self, heading_delta: float, throttle_delta: float, speed_delta: float = 0.0):
        self.heading = (self.heading + heading_delta) % 360
        self.vertical_speed += throttle_delta
        if speed_delta:
            self.speed = clamp(self.speed + speed_delta, 0.0, DEFAULT_CRUISE_SPEED_MS)

    def _track_altitude_target(self, max_vertical_speed: float):
        altitude_error = self.altitude_target - self.position.alt
        if abs(altitude_error) <= 1.0:
            self.vertical_speed = 0.0
            return
        self.vertical_speed = clamp(altitude_error, -max_vertical_speed, max_vertical_speed)

    def _advisory_target_altitude(self, fallback: float) -> float:
        advisory = self.last_advisory
        if advisory:
            match = ALTITUDE_TARGET_PATTERN.search(advisory.details)
            if match:
                return max(MIN_OPERATIONAL_ALTITUDE_M, float(match.group(1)))
        return max(MIN_OPERATIONAL_ALTITUDE_M, fallback)

    def _advisory_target_heading(self, fallback: float) -> float:
        advisory = self.last_advisory
        if advisory:
            match = HEADING_TARGET_PATTERN.search(advisory.details)
            if match:
                return float(match.group(1)) % 360
        return fallback % 360

    def _apply_zone_detour(self) -> bool:
        advisory = self.last_advisory
        if not advisory or advisory.threat_id not in self.zone_catalog:
            return False
        zone = self.zone_catalog[advisory.threat_id]
        remaining_route = self._remaining_nominal_route()
        if not remaining_route:
            return False
        final_target = remaining_route[-1]
        detour_plan = self._build_zone_detour_plan(zone, final_target)
        if detour_plan is None:
            return False
        detour_start, detour = detour_plan

        self.route = [self.position, detour_start, *detour, final_target]
        self.current_waypoint_index = 1
        self.zone_detour_active = True
        self.active_zone_detour_id = zone.zone_id
        self.zone_detour_resume_at = time.time() + 0.8
        self.zone_detour_destination = final_target
        self.heading = bearing_between(self.position, self.route[self.current_waypoint_index])
        self.speed = 0.0
        return True

    def _build_zone_detour_plan(self, zone: Zone, final_target: Position) -> tuple[Position, list[Position]] | None:
        candidates: list[tuple[float, Position, list[Position]]] = []
        for side in (1, -1):
            start_point = self._detour_start_point(zone, side)
            detour = self._build_zone_detour(zone, start_point, final_target, side)
            if detour is None:
                continue
            score = self._score_zone_detour(start_point, detour, final_target)
            candidates.append((score, start_point, detour))
        if not candidates:
            return None
        _, start_point, detour = min(candidates, key=lambda item: item[0])
        return start_point, detour

    def _build_zone_detour(self, zone: Zone, start_point: Position, final_target: Position, side: int) -> list[Position] | None:
        clearance = zone.radius_m + 120.0
        current_x, current_y = self._relative_xy(zone.center, start_point)
        final_x, final_y = self._relative_xy(zone.center, final_target)
        start_angle = math.atan2(current_y, current_x)
        end_angle = math.atan2(final_y, final_x)
        arc_delta = (end_angle - start_angle) % (2 * math.pi)
        if side < 0:
            arc_delta = arc_delta - (2 * math.pi) if arc_delta > 0 else arc_delta
        else:
            if arc_delta < 0:
                arc_delta += 2 * math.pi

        step_count = max(4, min(10, int(abs(arc_delta) / (math.pi / 8)) + 1))
        waypoints = []
        for step in range(1, step_count + 1):
            fraction = step / step_count
            angle = start_angle + (arc_delta * fraction)
            dx = math.cos(angle) * clearance
            dy = math.sin(angle) * clearance
            waypoint = Position(
                lat=zone.center.lat + meters_to_lat(dy),
                lon=zone.center.lon + meters_to_lon(dx, zone.center.lat),
                alt=self.nominal_altitude,
            )
            if self._point_inside_any_zone(waypoint, zone.zone_id):
                return None
            if haversine_distance(start_point, waypoint) > 20:
                waypoints.append(waypoint)
        return waypoints or None

    def _score_zone_detour(self, start_point: Position, detour: list[Position], final_target: Position) -> float:
        route_points = [self.position, start_point, *detour, final_target]
        score = 0.0
        segment_bearings = []
        for index in range(len(route_points) - 1):
            start = route_points[index]
            end = route_points[index + 1]
            score += haversine_distance(start, end)
            segment_bearings.append(bearing_between(start, end))

        if segment_bearings:
            heading_penalty = abs(((segment_bearings[0] - self.heading + 540.0) % 360.0) - 180.0)
            score += heading_penalty * 3.0

        for first, second in zip(segment_bearings, segment_bearings[1:]):
            turn_delta = abs(((second - first + 540.0) % 360.0) - 180.0)
            score += turn_delta * 1.5

        return score

    def _relative_xy(self, center: Position, point: Position) -> tuple[float, float]:
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = max(1e-6, meters_per_deg_lat * math.cos(math.radians(center.lat)))
        dx = (point.lon - center.lon) * meters_per_deg_lon
        dy = (point.lat - center.lat) * meters_per_deg_lat
        return dx, dy

    def _point_inside_any_zone(self, point: Position, ignore_zone_id: str) -> bool:
        for zone_id, zone in self.zone_catalog.items():
            if zone_id == ignore_zone_id or not zone.restricted:
                continue
            if haversine_distance(point, zone.center) <= zone.radius_m:
                return True
        return False

    def _inside_zone_by_id(self, zone_id: str) -> bool:
        zone = self.zone_catalog.get(zone_id)
        if zone is None or not zone.restricted:
            return False
        return haversine_distance(self.position, zone.center) <= zone.radius_m

    def _detour_start_point(self, zone: Zone, side: int) -> Position:
        clearance = zone.radius_m + 120.0
        center_x, center_y = self._relative_xy(zone.center, self.position)
        radius = max(1e-6, math.hypot(center_x, center_y))
        radial_angle = math.atan2(center_y, center_x)

        # Place the entry point on the safe circle, slightly ahead along the chosen tangent
        # so the drone starts skimming the boundary instead of bouncing backward.
        tangent_offset = side * (math.pi / 7)
        entry_angle = radial_angle + tangent_offset
        entry_x = math.cos(entry_angle) * clearance
        entry_y = math.sin(entry_angle) * clearance
        candidate = Position(
            lat=zone.center.lat + meters_to_lat(entry_y),
            lon=zone.center.lon + meters_to_lon(entry_x, zone.center.lat),
            alt=self.nominal_altitude,
        )

        if self._point_inside_any_zone(candidate, zone.zone_id):
            outward_angle = radial_angle
            entry_x = math.cos(outward_angle) * clearance
            entry_y = math.sin(outward_angle) * clearance
            candidate = Position(
                lat=zone.center.lat + meters_to_lat(entry_y),
                lon=zone.center.lon + meters_to_lon(entry_x, zone.center.lat),
                alt=self.nominal_altitude,
            )

        approach_bearing = bearing_between(self.position, candidate)
        heading_delta = abs(((approach_bearing - self.heading + 540.0) % 360.0) - 180.0)
        if heading_delta > 120.0:
            backed_off = move_position(
                self.position,
                (self.heading + 180.0) % 360.0,
                speed=ZONE_DETOUR_BACKTRACK_M * 0.5,
                vertical_speed=0.0,
                dt=1.0,
            )
            return Position(lat=backed_off.lat, lon=backed_off.lon, alt=self.nominal_altitude)

        return candidate

    def _resume_nominal_route(self) -> list[Position]:
        if len(self.nominal_route) < 2:
            return [self.position]

        best_projection = self.nominal_route[-1]
        best_index = len(self.nominal_route) - 1
        best_distance = float("inf")

        for index in range(len(self.nominal_route) - 1):
            start = self.nominal_route[index]
            end = self.nominal_route[index + 1]
            projection = project_on_segment(start, end, self.position)
            distance = haversine_distance(self.position, projection)
            if distance < best_distance:
                best_distance = distance
                best_projection = projection
                best_index = index + 1

        resumed_route = [self.position]
        if haversine_distance(self.position, best_projection) > 15:
            resumed_route.append(best_projection)
        resumed_route.extend(self.nominal_route[best_index:])
        return resumed_route

    def _remaining_nominal_route(self) -> list[Position]:
        resumed = self._resume_nominal_route()
        return resumed[1:] if len(resumed) > 1 else []

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


class ManualDroneMachine:
    def __init__(self, drone_id: str, mqtt_client: mqtt.Client):
        self.drone_id = drone_id
        self.mqtt_client = mqtt_client
        self.position = Position(lat=63.4305, lon=10.3951, alt=0.0)
        self.heading = 0.0
        self.speed = 0.0
        self.vertical_speed = 0.0
        self.battery = 100.0
        self.state = DroneState.REGISTERED
        self.nominal_altitude = DEFAULT_CRUISE_ALTITUDE_M
        self.altitude_target = DEFAULT_CRUISE_ALTITUDE_M
        self.route = []
        self.landing_site: Position | None = None
        self.mission_id = ""
        self.last_advisory: AdvisoryMessage | None = None
        self.last_applied_advisory_key: tuple[str, str, str] | None = None
        self.evasion_started_at = 0.0
        self.last_control_at = 0.0
        self.stm = self._build_machine()

    def _build_machine(self):
        states = [
            {"name": "registered", "entry": "publish_registration"},
            {"name": "idle"},
            {"name": "manual", "entry": "enter_manual", "t_tick": "tick_manual", "control": "apply_live_control"},
            {"name": "evading", "entry": "enter_evading", "t_tick": "tick_evading", "advisory": "refresh_advisory"},
        ]
        transitions = [
            {"source": "initial", "target": "registered"},
            {"trigger": "registration_done", "source": "registered", "target": "idle"},
            {"trigger": "activate", "source": "registered", "target": "manual", "effect": "start_manual_mission"},
            {"trigger": "activate", "source": "idle", "target": "manual", "effect": "start_manual_mission"},
            {"trigger": "advisory", "source": "manual", "target": "evading"},
            {"trigger": "clear", "source": "evading", "target": "manual", "effect": "resume_manual"},
        ]
        return stmpy.Machine(name=self.drone_id, transitions=transitions, states=states, obj=self)

    def publish_registration(self):
        message = RegisterMessage(
            drone_id=self.drone_id,
            drone_type="sensehat-controlled",
            operator="raspberry-pi",
            max_altitude=DEFAULT_CRUISE_ALTITUDE_M,
            max_speed=MANUAL_DRONE_MAX_SPEED_MS,
        )
        self.mqtt_client.publish(DRONE_REGISTER.format(drone_id=self.drone_id), message.to_json())
        self.stm.send("registration_done")

    def start_manual_mission(self):
        if self.route:
            self.position = Position(self.route[0].lat, self.route[0].lon, 0.0)
            self.landing_site = self.route[-1]
        self.speed = 0.0
        self.vertical_speed = 0.0

    def enter_manual(self):
        self.state = DroneState.MANUAL
        self.last_applied_advisory_key = None
        self._schedule_tick()

    def apply_live_control(self):
        self.last_control_at = time.time()

    def tick_manual(self):
        # Decay climb/descent if controls stop arriving so the drone stabilizes.
        if time.time() - self.last_control_at > 1.0:
            self.vertical_speed *= 0.85
        self._advance()
        self._schedule_tick()

    def accept_activation(self, activation: ActivationMessage):
        if self.state not in {DroneState.IDLE, DroneState.REGISTERED}:
            if self.mission_id == activation.mission_id:
                return
            logger.warning(
                "[%s] Ignoring activation for mission %s while in state %s (current mission %s)",
                self.drone_id,
                activation.mission_id,
                self.state.value,
                self.mission_id or "none",
            )
            return
        self.route = list(activation.route)
        self.mission_id = activation.mission_id
        self.stm.send("activate")

    def accept_control(self, heading_delta: float, throttle_delta: float, speed_delta: float):
        self.heading = (self.heading + heading_delta) % 360
        self.vertical_speed = clamp(self.vertical_speed + throttle_delta, -DEFAULT_VERTICAL_SPEED_MS, DEFAULT_VERTICAL_SPEED_MS)
        self.speed = clamp(self.speed + speed_delta, 0.0, MANUAL_DRONE_MAX_SPEED_MS)
        logger.info(
            "[%s] Manual control heading_delta=%s throttle_delta=%s speed_delta=%s -> heading=%.1f speed=%.1f vs=%.1f",
            self.drone_id,
            heading_delta,
            throttle_delta,
            speed_delta,
            self.heading,
            self.speed,
            self.vertical_speed,
        )
        self.stm.send("control")

    def accept_advisory(self, advisory: AdvisoryMessage):
        self.last_advisory = advisory
        self.stm.send("advisory")

    def enter_evading(self):
        self.state = DroneState.EVADING
        self.evasion_started_at = time.time()
        self._apply_advisory(force=True)
        self._schedule_tick()

    def refresh_advisory(self):
        self._apply_advisory()

    def _apply_advisory(self, force: bool = False):
        advisory = self.last_advisory
        if not advisory:
            return
        advisory_key = (advisory.advisory_type, advisory.threat_id, advisory.details)
        if not force and advisory_key == self.last_applied_advisory_key:
            return
        self.last_applied_advisory_key = advisory_key
        if advisory.advisory_type == AdvisoryType.TURN_RIGHT.value:
            self.heading = self._advisory_target_heading((self.heading + EVASION_HEADING_CHANGE_DEG) % 360)
        elif advisory.advisory_type == AdvisoryType.TURN_LEFT.value:
            self.heading = self._advisory_target_heading((self.heading - EVASION_HEADING_CHANGE_DEG) % 360)
        elif advisory.advisory_type == AdvisoryType.CLIMB.value:
            self.altitude_target = self._advisory_target_altitude(self.nominal_altitude + VERTICAL_SEPARATION_M)
            self._track_altitude_target(EVASION_VERTICAL_SPEED_MS)
        elif advisory.advisory_type == AdvisoryType.DESCEND.value:
            self.altitude_target = self._advisory_target_altitude(
                max(MIN_OPERATIONAL_ALTITUDE_M, self.nominal_altitude - VERTICAL_SEPARATION_M)
            )
            self._track_altitude_target(EVASION_VERTICAL_SPEED_MS)
        elif advisory.advisory_type in {AdvisoryType.HOLD_POSITION.value, AdvisoryType.ABORT_MISSION.value}:
            self.speed = 0.0
            self.vertical_speed = 0.0

    def tick_evading(self):
        self._track_altitude_target(EVASION_VERTICAL_SPEED_MS)
        self._advance()
        if self.last_advisory and self.last_advisory.advisory_type == AdvisoryType.CLEAR_OF_CONFLICT.value:
            self.stm.send("clear")
            return
        if time.time() - self.evasion_started_at > EVASION_TIMEOUT_S:
            self.stm.send("clear")
            return
        self._schedule_tick()

    def resume_manual(self):
        self.state = DroneState.MANUAL
        self.altitude_target = self.nominal_altitude
        self.last_applied_advisory_key = None
        self._schedule_tick()

    def _track_altitude_target(self, max_vertical_speed: float):
        altitude_error = self.altitude_target - self.position.alt
        if abs(altitude_error) <= 1.0:
            self.vertical_speed = 0.0
            return
        self.vertical_speed = clamp(altitude_error, -max_vertical_speed, max_vertical_speed)

    def _advisory_target_altitude(self, fallback: float) -> float:
        advisory = self.last_advisory
        if advisory:
            match = ALTITUDE_TARGET_PATTERN.search(advisory.details)
            if match:
                return max(MIN_OPERATIONAL_ALTITUDE_M, float(match.group(1)))
        return max(MIN_OPERATIONAL_ALTITUDE_M, fallback)

    def _advisory_target_heading(self, fallback: float) -> float:
        advisory = self.last_advisory
        if advisory:
            match = HEADING_TARGET_PATTERN.search(advisory.details)
            if match:
                return float(match.group(1)) % 360
        return fallback % 360

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
    def __init__(
        self,
        drones: int = DEFAULT_DRONE_COUNT,
        broker_host: str = MQTT_BROKER_HOST,
        broker_port: int = MQTT_BROKER_PORT,
        manual_drone_id: str | None = None,
    ):
        self.drone_count = drones
        self.manual_drone_id = manual_drone_id
        self.driver = stmpy.Driver()
        self.mqtt_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="drone-simulator",
        )
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.drones: dict[str, DroneFlightMachine | ManualDroneMachine] = {}
        self.zones: dict[str, Zone] = {}

    def start(self):
        autonomous_count = self.drone_count - (1 if self.manual_drone_id else 0)
        for index in range(autonomous_count):
            drone_id = f"drone-{index:03d}"
            machine = DroneFlightMachine(drone_id, self.mqtt_client, self.zones)
            self.drones[drone_id] = machine
        if self.manual_drone_id:
            self.drones[self.manual_drone_id] = ManualDroneMachine(self.manual_drone_id, self.mqtt_client)
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
        client.subscribe(DRONE_SPAWN_REQUEST)
        client.subscribe(ZONE_UPDATE)
        for drone_id in self.drones:
            client.subscribe(DRONE_ACTIVATION.format(drone_id=drone_id))
            client.subscribe(DRONE_ADVISORY.format(drone_id=drone_id))
            client.subscribe(DRONE_CONTROL.format(drone_id=drone_id))
        logger.info("Simulator connected to MQTT broker")

    def _spawn_requested_drone(self, request: MissionRequestMessage):
        if request.drone_id in self.drones:
            logger.info("Ignoring spawn request for existing drone %s", request.drone_id)
            return

        machine = DroneFlightMachine(
            request.drone_id,
            self.mqtt_client,
            self.zones,
            drone_type=request.drone_type,
            operator=request.operator,
            max_altitude=request.cruise_altitude,
            max_speed=request.max_speed,
        )
        self.drones[request.drone_id] = machine
        self.mqtt_client.subscribe(DRONE_ACTIVATION.format(drone_id=request.drone_id))
        self.mqtt_client.subscribe(DRONE_ADVISORY.format(drone_id=request.drone_id))
        self.mqtt_client.subscribe(DRONE_CONTROL.format(drone_id=request.drone_id))
        self.driver.add_machine(machine.stm)
        logger.info("Spawned requested drone %s from planner flow", request.drone_id)

    def _on_message(self, client, userdata, msg):
        if msg.topic == DRONE_SPAWN_REQUEST:
            self._spawn_requested_drone(MissionRequestMessage.from_json(msg.payload))
            return
        if msg.topic == ZONE_UPDATE:
            payload = json.loads(msg.payload.decode("utf-8"))
            self.zones.clear()
            for item in payload:
                zone = Zone(
                    zone_id=item["zone_id"],
                    name=item["name"],
                    center=Position(**item["center"]),
                    radius_m=float(item["radius_m"]),
                    min_alt_m=float(item.get("min_alt_m", 0.0)),
                    max_alt_m=float(item.get("max_alt_m", DEFAULT_CRUISE_ALTITUDE_M)),
                    restricted=bool(item.get("restricted", True)),
                )
                self.zones[zone.zone_id] = zone
            return

        parts = msg.topic.split("/")
        drone_id = parts[2]
        if parts[3] == "activation":
            self.drones[drone_id].accept_activation(ActivationMessage.from_json(msg.payload))
        elif parts[3] == "advisory":
            self.drones[drone_id].accept_advisory(AdvisoryMessage.from_json(msg.payload))
        elif parts[3] == "control":
            payload = ControlMessage.from_json(msg.payload)
            logger.info(
                "[%s] Control message received heading_delta=%s throttle_delta=%s speed_delta=%s",
                drone_id,
                payload.heading_delta,
                payload.throttle_delta,
                payload.speed_delta,
            )
            self.drones[drone_id].accept_control(payload.heading_delta, payload.throttle_delta, payload.speed_delta)
