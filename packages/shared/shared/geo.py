import math

from shared.schemas import Position


EARTH_RADIUS_M = 6_371_000


def meters_to_lat(meters: float) -> float:
    return (meters / EARTH_RADIUS_M) * (180 / math.pi)


def meters_to_lon(meters: float, lat: float) -> float:
    return (meters / (EARTH_RADIUS_M * math.cos(math.radians(lat)))) * (180 / math.pi)


def haversine_distance(a: Position, b: Position) -> float:
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    sin_lat = math.sin(dlat / 2)
    sin_lon = math.sin(dlon / 2)
    c = 2 * math.asin(math.sqrt(sin_lat ** 2 + math.cos(lat1) * math.cos(lat2) * sin_lon ** 2))
    return EARTH_RADIUS_M * c


def bearing_between(a: Position, b: Position) -> float:
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def move_position(position: Position, heading: float, speed: float, vertical_speed: float, dt: float) -> Position:
    heading_rad = math.radians(heading)
    north = math.cos(heading_rad) * speed * dt
    east = math.sin(heading_rad) * speed * dt
    return Position(
        lat=position.lat + meters_to_lat(north),
        lon=position.lon + meters_to_lon(east, position.lat),
        alt=max(0.0, position.alt + vertical_speed * dt),
    )
