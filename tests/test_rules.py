from apps.airspace_core.rules import conflict_advisories, zone_advisories
from shared.models import AdvisoryType
from shared.schemas import Position, TelemetryMessage, Zone


def test_zone_advisory_when_drone_inside_restricted_zone():
    drone = TelemetryMessage(
        drone_id="drone-1",
        timestamp=0.0,
        position=Position(lat=63.43, lon=10.39, alt=50),
        heading=0.0,
        speed=0.0,
        vertical_speed=0.0,
        state="airborne",
        battery=100.0,
    )
    zone = Zone(
        zone_id="zone-1",
        name="Test Zone",
        center=Position(lat=63.43, lon=10.39, alt=50),
        radius_m=100,
        min_alt_m=0,
        max_alt_m=80,
        restricted=True,
    )

    advisories = zone_advisories({"drone-1": drone}, [zone])

    assert len(advisories) == 1
    assert advisories[0].drone_id == "drone-1"
    assert advisories[0].advisory_type in {AdvisoryType.TURN_LEFT.value, AdvisoryType.TURN_RIGHT.value}
    assert "Avoid restricted zone" in advisories[0].details
    assert "heading" in advisories[0].details


def test_conflict_advisories_for_head_on_drones():
    first = TelemetryMessage(
        drone_id="a",
        timestamp=0.0,
        position=Position(lat=63.4300, lon=10.3900, alt=60),
        heading=90.0,
        speed=20.0,
        vertical_speed=0.0,
        state="airborne",
        battery=100.0,
    )
    second = TelemetryMessage(
        drone_id="b",
        timestamp=0.0,
        position=Position(lat=63.4300, lon=10.3910, alt=60),
        heading=270.0,
        speed=20.0,
        vertical_speed=0.0,
        state="airborne",
        battery=100.0,
    )

    advisories = conflict_advisories({"a": first, "b": second}, {})

    assert len(advisories) == 2
    assert {advisory.drone_id for advisory in advisories} == {"a", "b"}
    assert {advisory.advisory_type for advisory in advisories} == {
        AdvisoryType.CLIMB.value,
        AdvisoryType.DESCEND.value,
    }
    assert all("change altitude to" in advisory.details for advisory in advisories)


def test_conflict_advisories_for_three_drone_cluster_assign_distinct_targets():
    drones = {
        "a": TelemetryMessage(
            drone_id="a",
            timestamp=0.0,
            position=Position(lat=63.4300, lon=10.3900, alt=60),
            heading=90.0,
            speed=20.0,
            vertical_speed=0.0,
            state="airborne",
            battery=100.0,
        ),
        "b": TelemetryMessage(
            drone_id="b",
            timestamp=0.0,
            position=Position(lat=63.4300, lon=10.3907, alt=60),
            heading=270.0,
            speed=20.0,
            vertical_speed=0.0,
            state="airborne",
            battery=100.0,
        ),
        "c": TelemetryMessage(
            drone_id="c",
            timestamp=0.0,
            position=Position(lat=63.4302, lon=10.39035, alt=60),
            heading=180.0,
            speed=20.0,
            vertical_speed=0.0,
            state="airborne",
            battery=100.0,
        ),
    }

    advisories = conflict_advisories(drones, {})

    assert len(advisories) == 3
    assert {advisory.drone_id for advisory in advisories} == {"a", "b", "c"}
    assert all("Conflict cluster" in advisory.details for advisory in advisories)


def test_conflict_advisories_do_not_descend_below_operational_floor():
    first = TelemetryMessage(
        drone_id="a",
        timestamp=0.0,
        position=Position(lat=63.4300, lon=10.3900, alt=50),
        heading=90.0,
        speed=20.0,
        vertical_speed=0.0,
        state="airborne",
        battery=100.0,
    )
    second = TelemetryMessage(
        drone_id="b",
        timestamp=0.0,
        position=Position(lat=63.4300, lon=10.3910, alt=50),
        heading=270.0,
        speed=20.0,
        vertical_speed=0.0,
        state="airborne",
        battery=100.0,
    )

    advisories = conflict_advisories({"a": first, "b": second}, {})

    descend = next(advisory for advisory in advisories if advisory.advisory_type == AdvisoryType.DESCEND.value)
    assert "45m" in descend.details
