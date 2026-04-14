from shared.config import (
    DEFAULT_AIRSPACE_RADIUS_M,
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    DEFAULT_CRUISE_ALTITUDE_M,
)
from shared.geo import haversine_distance, meters_to_lat, meters_to_lon
from shared.schemas import Position

MIN_ROUTE_DISTANCE_M = 25.0
DEFAULT_ROUTE_RADIUS_FACTOR = 0.38
DEFAULT_ROUTE_RING_STEP = 0.08

# Each blueprint is (start_dx, start_dy, end_dx, end_dy) normalized to a route radius.
# The layouts are chosen to produce visually distinct corridors on the monitoring map.
ROUTE_BLUEPRINTS = (
    (-0.95, -0.60, 0.95, 0.60),
    (-0.95, 0.00, 0.95, 0.00),
    (-0.95, 0.60, 0.95, -0.60),
    (-0.60, -0.95, 0.60, 0.95),
    (0.00, -0.95, 0.00, 0.95),
    (0.60, -0.95, -0.60, 0.95),
    (-0.75, -0.25, 0.75, 0.25),
    (-0.75, 0.25, 0.75, -0.25),
)


def _build_position(dx_m: float, dy_m: float, alt_m: float) -> Position:
    return Position(
        lat=DEFAULT_CENTER_LAT + meters_to_lat(dy_m),
        lon=DEFAULT_CENTER_LON + meters_to_lon(dx_m, DEFAULT_CENTER_LAT),
        alt=alt_m,
    )


def _scale_to_radius(dx: float, dy: float, radius_m: float) -> tuple[float, float]:
    magnitude = max(1e-6, (dx * dx + dy * dy) ** 0.5)
    scale = radius_m / magnitude
    return dx * scale, dy * scale


def build_default_route(offset_index: int) -> list[Position]:
    blueprint_index = offset_index % len(ROUTE_BLUEPRINTS)
    ring_index = offset_index // len(ROUTE_BLUEPRINTS)
    scale = max(0.55, 1.0 - (ring_index * DEFAULT_ROUTE_RING_STEP))
    route_radius_m = DEFAULT_AIRSPACE_RADIUS_M * DEFAULT_ROUTE_RADIUS_FACTOR * scale

    start_dx, start_dy, end_dx, end_dy = ROUTE_BLUEPRINTS[blueprint_index]
    start_offset_x, start_offset_y = _scale_to_radius(start_dx, start_dy, route_radius_m)
    end_offset_x, end_offset_y = _scale_to_radius(end_dx, end_dy, route_radius_m)
    start = _build_position(start_offset_x, start_offset_y, 0.0)
    center = _build_position(0.0, 0.0, DEFAULT_CRUISE_ALTITUDE_M)
    end = _build_position(end_offset_x, end_offset_y, DEFAULT_CRUISE_ALTITUDE_M)
    return [start, center, end]


def build_requested_route(pickup: Position, dropoff: Position) -> list[Position]:
    return [
        Position(lat=pickup.lat, lon=pickup.lon, alt=pickup.alt),
        Position(lat=dropoff.lat, lon=dropoff.lon, alt=dropoff.alt),
    ]


def validate_activation_route(route: list[Position], min_route_distance_m: float = MIN_ROUTE_DISTANCE_M) -> str | None:
    if len(route) < 2:
        return "Activation route must contain at least a pickup point and a dropoff point"

    start = route[0]
    end = route[-1]
    if haversine_distance(start, end) < min_route_distance_m:
        return "Pickup and dropoff are too close to build a meaningful mission route"

    return None
