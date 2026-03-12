from shared.config import (
    DEFAULT_AIRSPACE_RADIUS_M,
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    DEFAULT_CRUISE_ALTITUDE_M,
)
from shared.geo import meters_to_lat, meters_to_lon
from shared.schemas import Position


def build_default_route(offset_index: int) -> list[Position]:
    radius = DEFAULT_AIRSPACE_RADIUS_M * 0.35
    dx = ((offset_index % 4) - 1.5) * radius * 0.5
    dy = ((offset_index // 4) - 1.5) * radius * 0.4
    start = Position(
        lat=DEFAULT_CENTER_LAT + meters_to_lat(dy),
        lon=DEFAULT_CENTER_LON + meters_to_lon(dx, DEFAULT_CENTER_LAT),
        alt=0.0,
    )
    end = Position(
        lat=DEFAULT_CENTER_LAT - meters_to_lat(dy),
        lon=DEFAULT_CENTER_LON - meters_to_lon(dx, DEFAULT_CENTER_LAT),
        alt=DEFAULT_CRUISE_ALTITUDE_M,
    )
    return [start, end]
