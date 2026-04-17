from types import SimpleNamespace

from apps.drone_simulator.fleet import SimulatorService
from shared.topics import DRONE_ACTIVATION


class RecordingDrone:
    def __init__(self):
        self.activations = []

    def accept_activation(self, activation):
        self.activations.append(activation)


def test_simulator_ignores_empty_retained_activation_payload():
    service = SimulatorService(drones=0)
    drone = RecordingDrone()
    service.drones["drone-001"] = drone

    message = SimpleNamespace(
        topic=DRONE_ACTIVATION.format(drone_id="drone-001"),
        payload=b"",
    )

    service._on_message(None, None, message)

    assert drone.activations == []
