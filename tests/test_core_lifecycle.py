from apps.airspace_core.core import AirspaceCore
from shared.schemas import ActivationMessage, Position, RegisterMessage, TelemetryMessage


class DummyMqttClient:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, **kwargs):
        self.messages.append((topic, payload, kwargs))


def test_participant_lifecycle_tracks_registration_activation_and_telemetry():
    service = AirspaceCore()
    service.mqtt_client = DummyMqttClient()

    register = RegisterMessage(
        drone_id="drone-123",
        drone_type="quadcopter",
        operator="simulator",
        max_altitude=60.0,
        max_speed=25.0,
        timestamp=10.0,
    )
    service._record_registration(register)

    participant = service.participants["drone-123"]
    assert participant.lifecycle_state == "registered"
    assert participant.registration_count == 1
    assert participant.last_register_at == 10.0
    assert participant.drone_type == "quadcopter"
    assert participant.operator == "simulator"
    assert participant.last_reported_state == "registered"

    activation = ActivationMessage(
        drone_id="drone-123",
        status="approved",
        mission_id="drone-123-mission-000",
        route=[
            Position(lat=63.43, lon=10.39, alt=0.0),
            Position(lat=63.44, lon=10.40, alt=60.0),
        ],
    )
    service._record_activation(activation)

    participant = service.participants["drone-123"]
    assert participant.lifecycle_state == "active"
    assert participant.active_mission_id == "drone-123-mission-000"
    assert participant.activation_count == 1
    assert participant.last_activation_at == activation.timestamp
    assert participant.last_activation_status == "approved"
    assert service.activations["drone-123"].mission_id == "drone-123-mission-000"

    degraded = TelemetryMessage(
        drone_id="drone-123",
        timestamp=20.0,
        position=Position(lat=63.43, lon=10.39, alt=40.0),
        heading=90.0,
        speed=15.0,
        vertical_speed=0.0,
        state="airborne",
        battery=99.0,
        mission_id="drone-123-mission-000",
        reduced_accuracy=True,
    )
    service._handle_telemetry(degraded)

    participant = service.participants["drone-123"]
    assert participant.lifecycle_state == "degraded"
    assert service.events[0].event_type == "drone_degraded"

    restored = TelemetryMessage(
        drone_id="drone-123",
        timestamp=21.0,
        position=Position(lat=63.431, lon=10.391, alt=45.0),
        heading=92.0,
        speed=15.0,
        vertical_speed=0.0,
        state="airborne",
        battery=98.5,
        mission_id="drone-123-mission-000",
    )
    service._handle_telemetry(restored)

    participant = service.participants["drone-123"]
    assert participant.lifecycle_state == "active"
    assert service.events[0].event_type == "drone_restored"

    completed = TelemetryMessage(
        drone_id="drone-123",
        timestamp=22.0,
        position=Position(lat=63.432, lon=10.392, alt=0.0),
        heading=0.0,
        speed=0.0,
        vertical_speed=0.0,
        state="completed",
        battery=98.0,
        mission_id="drone-123-mission-000",
    )
    service._handle_telemetry(completed)

    participant = service.participants["drone-123"]
    assert participant.lifecycle_state == "inactive"
    assert participant.active_mission_id == ""
    assert participant.completed_mission_count == 1
    assert participant.last_completed_mission_id == "drone-123-mission-000"
    assert participant.last_terminal_state == "completed"
    assert service.events[0].event_type == "mission_completed"
    assert participant.last_event_type == "mission_completed"
    assert participant.last_event_at == service.events[0].timestamp

    idle = TelemetryMessage(
        drone_id="drone-123",
        timestamp=23.0,
        position=Position(lat=63.432, lon=10.392, alt=0.0),
        heading=0.0,
        speed=0.0,
        vertical_speed=0.0,
        state="idle",
        battery=97.8,
        mission_id="drone-123-mission-000",
    )
    service._handle_telemetry(idle)

    participant = service.participants["drone-123"]
    assert participant.completed_mission_count == 1
    assert service.events[0].event_type == "mission_completed"


def test_duplicate_register_refreshes_metadata_without_creating_new_activation():
    service = AirspaceCore()
    service.mqtt_client = DummyMqttClient()

    original = RegisterMessage(
        drone_id="drone-dup",
        drone_type="quadcopter",
        operator="simulator",
        max_altitude=60.0,
        max_speed=25.0,
        timestamp=10.0,
    )
    service._record_registration(original)
    activation = ActivationMessage(
        drone_id="drone-dup",
        status="approved",
        mission_id="drone-dup-mission-000",
        route=[Position(lat=63.43, lon=10.39, alt=0.0), Position(lat=63.44, lon=10.40, alt=60.0)],
    )
    service._record_activation(activation)
    service.registry_machines["drone-dup"] = object()

    duplicate = RegisterMessage(
        drone_id="drone-dup",
        drone_type="fixed-wing",
        operator="pilot-refresh",
        max_altitude=75.0,
        max_speed=32.0,
        timestamp=20.0,
    )
    service._handle_register(duplicate)

    participant = service.participants["drone-dup"]
    assert len(service.registry_machines) == 1
    assert participant.lifecycle_state == "active"
    assert participant.active_mission_id == "drone-dup-mission-000"
    assert participant.activation_count == 1
    assert participant.registration_count == 1
    assert participant.refresh_count == 1
    assert participant.drone_type == "fixed-wing"
    assert participant.operator == "pilot-refresh"
    assert participant.max_altitude == 75.0
    assert participant.max_speed == 32.0
    assert service.activations["drone-dup"].mission_id == "drone-dup-mission-000"
    assert service.events[0].event_type == "re_register"
    assert participant.last_event_type == "re_register"


def test_aborted_mission_generates_terminal_event_once():
    service = AirspaceCore()
    service.mqtt_client = DummyMqttClient()

    activation = ActivationMessage(
        drone_id="drone-abort",
        status="approved",
        mission_id="drone-abort-mission-000",
        route=[Position(lat=63.43, lon=10.39, alt=0.0), Position(lat=63.44, lon=10.40, alt=60.0)],
    )
    service._record_activation(activation)

    aborted = TelemetryMessage(
        drone_id="drone-abort",
        timestamp=30.0,
        position=Position(lat=63.432, lon=10.392, alt=12.0),
        heading=0.0,
        speed=0.0,
        vertical_speed=-1.0,
        state="aborted",
        battery=97.0,
        mission_id="drone-abort-mission-000",
    )
    service._handle_telemetry(aborted)
    service._handle_telemetry(aborted)

    participant = service.participants["drone-abort"]
    assert participant.lifecycle_state == "inactive"
    assert participant.completed_mission_count == 1
    assert participant.last_completed_mission_id == "drone-abort-mission-000"
    assert participant.last_terminal_state == "aborted"
    assert service.events[0].event_type == "mission_aborted"
