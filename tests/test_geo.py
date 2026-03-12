from shared.geo import move_position
from shared.schemas import Position


def test_move_position_changes_altitude_and_latitude():
    start = Position(lat=63.43, lon=10.39, alt=0.0)
    end = move_position(start, heading=0.0, speed=10.0, vertical_speed=2.0, dt=1.0)

    assert end.alt == 2.0
    assert end.lat > start.lat
