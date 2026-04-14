from enum import Enum


class DroneState(str, Enum):
    OFFLINE = "offline"
    REGISTERED = "registered"
    IDLE = "idle"
    ACTIVATED = "activated"
    TAKEOFF = "takeoff"
    AIRBORNE = "airborne"
    MANUAL = "manual"
    EVADING = "evading"
    LANDING = "landing"
    COMPLETED = "completed"
    ABORTED = "aborted"


class AdvisoryType(str, Enum):
    CLEAR_OF_CONFLICT = "clear_of_conflict"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    CLIMB = "climb"
    DESCEND = "descend"
    HOLD_POSITION = "hold_position"
    ABORT_MISSION = "abort_mission"


class AdvisorySeverity(str, Enum):
    WARNING = "warning"
    IMMEDIATE = "immediate"


class ActivationStatus(str, Enum):
    APPROVED = "approved"
    DELAYED = "delayed"
    REJECTED = "rejected"
