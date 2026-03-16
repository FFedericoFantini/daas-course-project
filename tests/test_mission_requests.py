from apps.airspace_core.core import AirspaceCore
from shared.schemas import MissionRequestMessage, Position
from shared.topics import DRONE_SPAWN_REQUEST


class DummyMqttClient:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload):
        self.messages.append((topic, payload))


def test_mission_request_round_trip():
    request = MissionRequestMessage(
        drone_id="planner-001",
        operator="planner-user",
        drone_type="quadcopter",
        pickup=Position(lat=63.4301, lon=10.3902, alt=0.0),
        dropoff=Position(lat=63.4311, lon=10.4012, alt=0.0),
        cruise_altitude=70.0,
        max_speed=18.5,
    )

    restored = MissionRequestMessage.from_json(request.to_json())

    assert restored.drone_id == "planner-001"
    assert restored.pickup.lat == 63.4301
    assert restored.dropoff.lon == 10.4012
    assert restored.cruise_altitude == 70.0
    assert restored.max_speed == 18.5


def test_airspace_core_stores_manual_request_and_uses_requested_route():
    service = AirspaceCore()
    service.mqtt_client = DummyMqttClient()

    request = MissionRequestMessage(
        drone_id="planner-002",
        operator="planner-user",
        drone_type="quadcopter",
        pickup=Position(lat=63.4305, lon=10.3951, alt=0.0),
        dropoff=Position(lat=63.4370, lon=10.4100, alt=0.0),
        cruise_altitude=60.0,
        max_speed=22.0,
    )

    service._handle_mission_request(request)

    assert service.pending_mission_requests["planner-002"].drone_id == "planner-002"
    assert service.mqtt_client.messages[-1][0] == DRONE_SPAWN_REQUEST
    assert service.events[0].event_type == "mission_requested"

    activation = service._create_activation_for_drone("planner-002", 0)

    assert activation.route[0].lat == 63.4305
    assert activation.route[0].lon == 10.3951
    assert activation.route[-1].lat == 63.4370
    assert activation.route[-1].lon == 10.4100
    assert activation.reason == "Mission assigned from planner request"
    assert "planner-002" not in service.pending_mission_requests
