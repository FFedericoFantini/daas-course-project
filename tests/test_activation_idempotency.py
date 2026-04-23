from apps.drone_simulator.fleet import DroneFlightMachine, ManualDroneMachine
from shared.models import DroneState
from shared.schemas import ActivationMessage, Position


class DummyMqttClient:
    def publish(self, *args, **kwargs):
        return None


def sample_activation(mission_id: str = "mission-001") -> ActivationMessage:
    return ActivationMessage(
        drone_id="drone-001",
        status="approved",
        mission_id=mission_id,
        route=[
            Position(lat=63.4305, lon=10.3951, alt=0.0),
            Position(lat=63.4310, lon=10.3960, alt=60.0),
        ],
        reason="test",
    )


def test_autonomous_drone_ignores_duplicate_activation_for_same_mission():
    machine = DroneFlightMachine("drone-001", DummyMqttClient(), {})
    machine.state = DroneState.TAKEOFF
    machine.mission_id = "mission-001"

    sent_events = []
    machine.stm.send = lambda event: sent_events.append(event)

    machine.accept_activation(sample_activation("mission-001"))

    assert sent_events == []


def test_manual_drone_ignores_duplicate_activation_for_same_mission():
    machine = ManualDroneMachine("drone-rpi-001", DummyMqttClient())
    machine.state = DroneState.MANUAL
    machine.mission_id = "mission-001"

    sent_events = []
    machine.stm.send = lambda event: sent_events.append(event)

    activation = ActivationMessage(
        drone_id="drone-rpi-001",
        status="approved",
        mission_id="mission-001",
        route=[
            Position(lat=63.4305, lon=10.3951, alt=0.0),
            Position(lat=63.4310, lon=10.3960, alt=60.0),
        ],
        reason="test",
    )

    machine.accept_activation(activation)

    assert sent_events == []
