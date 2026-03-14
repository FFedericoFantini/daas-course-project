from apps.airspace_core.core import AirspaceCore
from shared.schemas import Position, Zone, ZoneCommandMessage


class DummyMqttClient:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload):
        self.messages.append((topic, payload))


def test_zone_command_round_trip():
    command = ZoneCommandMessage(
        action="upsert",
        zone_id="zone-test",
        zone=Zone(
            zone_id="zone-test",
            name="Test Zone",
            center=Position(lat=63.43, lon=10.39, alt=50.0),
            radius_m=120.0,
        ),
    )

    restored = ZoneCommandMessage.from_json(command.to_json())

    assert restored.action == "upsert"
    assert restored.zone is not None
    assert restored.zone.zone_id == "zone-test"
    assert restored.zone.center.lat == 63.43


def test_airspace_core_upsert_and_remove_zone_command():
    service = AirspaceCore()
    service.mqtt_client = DummyMqttClient()
    service.zones = []

    zone = Zone(
        zone_id="zone-1",
        name="Temporary Restriction",
        center=Position(lat=63.43, lon=10.39, alt=40.0),
        radius_m=150.0,
    )

    service._handle_zone_command(ZoneCommandMessage(action="upsert", zone_id=zone.zone_id, zone=zone))

    assert len(service.zones) == 1
    assert service.zones[0].zone_id == "zone-1"

    service._handle_zone_command(ZoneCommandMessage(action="remove", zone_id="zone-1"))

    assert service.zones == []
