from collections import defaultdict

from shared.config import (
    CONFLICT_TIME_HORIZON_S,
    DEFAULT_CRUISE_ALTITUDE_M,
    HORIZONTAL_SEPARATION_M,
    MIN_OPERATIONAL_ALTITUDE_M,
    VERTICAL_SEPARATION_M,
)
from shared.geo import bearing_between, haversine_distance, move_position
from shared.models import AdvisorySeverity, AdvisoryType
from shared.schemas import AdvisoryMessage, TelemetryMessage, Zone


def project_telemetry(tel: TelemetryMessage, dt: float) -> TelemetryMessage:
    return TelemetryMessage(
        drone_id=tel.drone_id,
        timestamp=tel.timestamp + dt,
        position=move_position(tel.position, tel.heading, tel.speed, tel.vertical_speed, dt),
        heading=tel.heading,
        speed=tel.speed,
        vertical_speed=tel.vertical_speed,
        state=tel.state,
        battery=tel.battery,
        mission_id=tel.mission_id,
        reduced_accuracy=tel.reduced_accuracy,
    )


def inside_zone(tel: TelemetryMessage, zone: Zone) -> bool:
    horizontal = haversine_distance(tel.position, zone.center)
    vertical = zone.min_alt_m <= tel.position.alt <= zone.max_alt_m
    return horizontal <= zone.radius_m and vertical


def _turn_away_from_zone(tel: TelemetryMessage, zone: Zone) -> str:
    bearing_to_zone = bearing_between(tel.position, zone.center)
    relative = ((bearing_to_zone - tel.heading + 540) % 360) - 180
    return AdvisoryType.TURN_LEFT.value if relative >= 0 else AdvisoryType.TURN_RIGHT.value


def _zone_escape_heading(tel: TelemetryMessage, zone: Zone) -> float:
    return (bearing_between(zone.center, tel.position) + 360) % 360


def _build_conflict_components(conflict_pairs: list[tuple[str, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for first_id, second_id in conflict_pairs:
        graph[first_id].add(second_id)
        graph[second_id].add(first_id)

    components = []
    visited: set[str] = set()
    for drone_id in graph:
        if drone_id in visited:
            continue
        stack = [drone_id]
        component = []
        visited.add(drone_id)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    return components


def _component_altitude_targets(component: list[str], drones: dict[str, TelemetryMessage]) -> dict[str, float]:
    base_altitude = max(
        DEFAULT_CRUISE_ALTITUDE_M,
        max(drones[drone_id].position.alt for drone_id in component),
    )
    center_index = (len(component) - 1) / 2
    targets = {}
    for index, drone_id in enumerate(component):
        offset_steps = index - center_index
        target = base_altitude + (offset_steps * VERTICAL_SEPARATION_M)
        targets[drone_id] = max(MIN_OPERATIONAL_ALTITUDE_M, target)
    return targets


def zone_advisories(drones: dict[str, TelemetryMessage], zones: list[Zone]) -> list[AdvisoryMessage]:
    advisories = []
    for tel in drones.values():
        for zone in zones:
            if zone.restricted and inside_zone(tel, zone):
                advisory_type = _turn_away_from_zone(tel, zone)
                escape_heading = _zone_escape_heading(tel, zone)
                advisories.append(
                    AdvisoryMessage(
                        drone_id=tel.drone_id,
                        advisory_type=advisory_type,
                        severity=AdvisorySeverity.IMMEDIATE.value,
                        threat_id=zone.zone_id,
                        details=(
                            f"Avoid restricted zone {zone.name}: fly heading {escape_heading:.0f}deg "
                            f"and {advisory_type.replace('_', ' ')} to exit the zone"
                        ),
                    )
                )
    return advisories


def conflict_advisories(
    drones: dict[str, TelemetryMessage],
    manned: dict[str, TelemetryMessage],
) -> list[AdvisoryMessage]:
    advisories = []
    conflict_pairs: list[tuple[str, str]] = []
    pair_context: dict[frozenset[str], tuple[float, float, AdvisorySeverity]] = {}
    drone_ids = list(drones.keys())
    for index, first_id in enumerate(drone_ids):
        for second_id in drone_ids[index + 1 :]:
            first = drones[first_id]
            second = drones[second_id]
            h_dist = haversine_distance(first.position, second.position)
            v_dist = abs(first.position.alt - second.position.alt)
            next_first = project_telemetry(first, 1.0)
            next_second = project_telemetry(second, 1.0)
            closing = h_dist - haversine_distance(next_first.position, next_second.position)

            if v_dist > VERTICAL_SEPARATION_M:
                continue
            if h_dist < HORIZONTAL_SEPARATION_M:
                severity = AdvisorySeverity.IMMEDIATE
            elif closing > 0 and h_dist / closing <= CONFLICT_TIME_HORIZON_S:
                severity = AdvisorySeverity.WARNING
            else:
                continue
            conflict_pairs.append((first_id, second_id))
            pair_context[frozenset((first_id, second_id))] = (h_dist, v_dist, severity)

    for component in _build_conflict_components(conflict_pairs):
        targets = _component_altitude_targets(component, drones)
        component_threats = {drone_id: [] for drone_id in component}
        component_severity = AdvisorySeverity.WARNING

        for first_id in component:
            for second_id in component:
                if first_id >= second_id:
                    continue
                pair_key = frozenset((first_id, second_id))
                if pair_key not in pair_context:
                    continue
                h_dist, v_dist, severity = pair_context[pair_key]
                component_threats[first_id].append(f"{second_id} (h={h_dist:.0f}m v={v_dist:.0f}m)")
                component_threats[second_id].append(f"{first_id} (h={h_dist:.0f}m v={v_dist:.0f}m)")
                if severity == AdvisorySeverity.IMMEDIATE:
                    component_severity = AdvisorySeverity.IMMEDIATE

        for drone_id in component:
            target_altitude = targets[drone_id]
            current_altitude = drones[drone_id].position.alt
            if abs(target_altitude - current_altitude) <= 5:
                advisory_type = AdvisoryType.CLIMB.value if drone_id == component[-1] else AdvisoryType.DESCEND.value
            else:
                advisory_type = AdvisoryType.CLIMB.value if target_altitude > current_altitude else AdvisoryType.DESCEND.value
            threat_summary = ", ".join(component_threats[drone_id])
            advisories.append(
                AdvisoryMessage(
                    drone_id=drone_id,
                    advisory_type=advisory_type,
                    severity=component_severity.value,
                    threat_id="|".join(other_id for other_id in component if other_id != drone_id),
                    details=(
                        f"Conflict cluster: change altitude to {target_altitude:.0f}m "
                        f"({advisory_type}) for vertical separation from {threat_summary}"
                    ),
                )
            )

    for drone in drones.values():
        for aircraft in manned.values():
            h_dist = haversine_distance(drone.position, aircraft.position)
            v_dist = abs(drone.position.alt - aircraft.position.alt)
            if h_dist < HORIZONTAL_SEPARATION_M * 2 and v_dist < VERTICAL_SEPARATION_M * 2:
                advisories.append(
                    AdvisoryMessage(
                        drone_id=drone.drone_id,
                        advisory_type=AdvisoryType.DESCEND.value,
                        severity=AdvisorySeverity.IMMEDIATE.value,
                        threat_id=aircraft.drone_id,
                        details=f"Manned aircraft priority: {aircraft.drone_id}",
                    )
                )
    return advisories
