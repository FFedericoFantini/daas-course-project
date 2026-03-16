from apps.airspace_core.mission import ROUTE_BLUEPRINTS, build_default_route
from shared.config import DEFAULT_CENTER_LAT, DEFAULT_CENTER_LON
from shared.geo import haversine_distance
from shared.schemas import Position


def distance_from_center(position: Position) -> float:
    center = Position(lat=DEFAULT_CENTER_LAT, lon=DEFAULT_CENTER_LON, alt=position.alt)
    return haversine_distance(center, position)


def test_default_route_generation_is_deterministic():
    first = build_default_route(0)
    second = build_default_route(0)

    assert first == second


def test_first_blueprint_cycle_produces_distinct_routes():
    first_cycle = [build_default_route(index) for index in range(len(ROUTE_BLUEPRINTS))]

    starts = {(route[0].lat, route[0].lon) for route in first_cycle}
    ends = {(route[-1].lat, route[-1].lon) for route in first_cycle}

    assert len(starts) == len(ROUTE_BLUEPRINTS)
    assert len(ends) == len(ROUTE_BLUEPRINTS)


def test_later_route_cycles_stay_deterministic_but_move_inward():
    outer = build_default_route(0)
    inner = build_default_route(len(ROUTE_BLUEPRINTS))

    outer_distance = distance_from_center(outer[0])
    inner_distance = distance_from_center(inner[0])

    assert inner != outer
    assert inner_distance < outer_distance
    assert outer[0].alt == 0.0
    assert outer[-1].alt > outer[0].alt
