from dataclasses import asdict, dataclass, field
import json
import time


@dataclass
class Position:
    lat: float
    lon: float
    alt: float


@dataclass
class Zone:
    zone_id: str
    name: str
    center: Position
    radius_m: float
    min_alt_m: float = 0.0
    max_alt_m: float = 120.0
    restricted: bool = True


@dataclass
class RegisterMessage:
    drone_id: str
    drone_type: str
    operator: str
    max_altitude: float
    max_speed: float
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | bytes) -> "RegisterMessage":
        return cls(**json.loads(data))


@dataclass
class ActivationMessage:
    drone_id: str
    status: str
    mission_id: str
    route: list[Position]
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        payload = asdict(self)
        return json.dumps(payload)

    @classmethod
    def from_json(cls, data: str | bytes) -> "ActivationMessage":
        payload = json.loads(data)
        payload["route"] = [Position(**item) for item in payload.get("route", [])]
        return cls(**payload)


@dataclass
class TelemetryMessage:
    drone_id: str
    timestamp: float
    position: Position
    heading: float
    speed: float
    vertical_speed: float
    state: str
    battery: float
    mission_id: str = ""
    reduced_accuracy: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | bytes) -> "TelemetryMessage":
        payload = json.loads(data)
        payload["position"] = Position(**payload["position"])
        return cls(**payload)


@dataclass
class AdvisoryMessage:
    drone_id: str
    advisory_type: str
    severity: str
    threat_id: str
    details: str
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | bytes) -> "AdvisoryMessage":
        return cls(**json.loads(data))


@dataclass
class ControlMessage:
    drone_id: str
    heading_delta: float = 0.0
    throttle_delta: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | bytes) -> "ControlMessage":
        return cls(**json.loads(data))


@dataclass
class AirspaceEvent:
    event_type: str
    entity_id: str
    details: str
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | bytes) -> "AirspaceEvent":
        return cls(**json.loads(data))
