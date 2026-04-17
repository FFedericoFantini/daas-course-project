from apps.drone_simulator.fleet import DroneFlightMachine
from shared.models import DroneState
from shared.schemas import Position


class DummyMqttClient:
    def publish(self, *args, **kwargs):
        return None


def test_takeoff_transitions_to_cruise_within_altitude_tolerance():
    machine = DroneFlightMachine("drone-001", DummyMqttClient(), {})
    machine.route = [
        Position(lat=63.4305, lon=10.3951, alt=0.0),
        Position(lat=63.4310, lon=10.3960, alt=60.0),
    ]
    machine.nominal_route = list(machine.route)
    machine.nominal_altitude = 60.0
    machine.altitude_target = 60.0
    machine.position = Position(lat=63.4305, lon=10.3951, alt=59.4)
    machine.speed = 0.0
    machine.vertical_speed = 0.0

    sent_events = []
    machine.stm.send = lambda event: sent_events.append(event)
    machine._schedule_tick = lambda: None

    machine.tick_takeoff()

    assert machine.state == DroneState.TAKEOFF
    assert machine.position.alt == 60.0
    assert machine.position.lat == 63.4305
    assert machine.position.lon == 10.3951
    assert machine.vertical_speed == 0.0
    assert sent_events == ["cruise"]


def test_complete_mission_snaps_to_exact_dropoff_point():
    machine = DroneFlightMachine("drone-001", DummyMqttClient(), {})
    machine.landing_site = Position(lat=63.4310, lon=10.3960, alt=60.0)
    machine.position = Position(lat=63.4309, lon=10.3958, alt=2.0)

    machine.complete_mission()

    assert machine.position.lat == 63.4310
    assert machine.position.lon == 10.3960
    assert machine.position.alt == 0.0
    assert machine.state == DroneState.IDLE
