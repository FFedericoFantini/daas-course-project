from shared.config import CONFLICT_TIME_HORIZON_S, HORIZONTAL_SEPARATION_M, VERTICAL_SEPARATION_M
from shared.geo import haversine_distance, move_position
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


def zone_advisories(drones: dict[str, TelemetryMessage], zones: list[Zone]) -> list[AdvisoryMessage]:
    advisories = []
    for tel in drones.values():
        for zone in zones:
            if zone.restricted and inside_zone(tel, zone):
                advisories.append(
                    AdvisoryMessage(
                        drone_id=tel.drone_id,
                        advisory_type=AdvisoryType.HOLD_POSITION.value,
                        severity=AdvisorySeverity.IMMEDIATE.value,
                        threat_id=zone.zone_id,
                        details=f"Restricted zone violation: {zone.name}",
                    )
                )
    return advisories


def conflict_advisories(
    drones: dict[str, TelemetryMessage],
    manned: dict[str, TelemetryMessage],
) -> list[AdvisoryMessage]:
    advisories = []
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

            advisories.append(
                AdvisoryMessage(
                    drone_id=first_id,
                    advisory_type=AdvisoryType.TURN_RIGHT.value,
                    severity=severity.value,
                    threat_id=second_id,
                    details=f"Conflict with {second_id}: h={h_dist:.0f}m v={v_dist:.0f}m",
                )
            )
            advisories.append(
                AdvisoryMessage(
                    drone_id=second_id,
                    advisory_type=AdvisoryType.TURN_LEFT.value,
                    severity=severity.value,
                    threat_id=first_id,
                    details=f"Conflict with {first_id}: h={h_dist:.0f}m v={v_dist:.0f}m",
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
