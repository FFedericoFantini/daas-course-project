# Team Split

This split is designed for a team of 6 people working directly from the final Spec V2 and this repository.

## Six-Person Assignment Table

| Member | Ownership | Main files | Main responsibilities | Main dependencies |
| --- | --- | --- | --- | --- |
| 1 - Federico | Airspace Core Lifecycle | `apps/airspace_core/core.py`, `apps/airspace_core/mission.py` | registration, activation, mission assignment, lifecycle events | shared schemas/topics, simulator registration flow |
| 2 - Mats | Airspace Core Safety Logic | `apps/airspace_core/rules.py`, `tests/test_rules.py` | conflict detection, advisory policy, restricted-zone behavior, priority logic | telemetry from simulator, event/advisory publish path in core |
| 3 - Auslaug | Drone Simulator | `apps/drone_simulator/fleet.py`, `apps/drone_simulator/main.py` | autonomous drone state machines, mission execution, telemetry, advisory execution | activation and advisory topics |
| 4 - Isak | Control Gateway / Raspberry Pi | `apps/control_gateway/main.py` plus new gateway client files | SenseHAT or keyboard control input, TCP/HTTP forwarding, manual drone integration | control topic contract, simulator manual drone path |
| 5 - Asne | Dashboard Backend | `apps/dashboard/main.py` | snapshot endpoint, SSE stream, zone command API, backend aggregation | MQTT topics, zone command contract |
| 6 - Jordan | Dashboard Frontend and Demo Polish | `apps/dashboard/templates/index.html`, `apps/dashboard/static/map.js`, `apps/dashboard/static/style.css`, `docs/` | UI readability, map rendering, event visibility, zone presentation, final demo polish | dashboard backend responses |

## Role Details

### Member 1: Federico - Airspace Core Lifecycle

Main tasks:

- keep drone registration stable
- keep activation/mission assignment stable
- publish lifecycle events
- protect `core.py` from unrelated logic

Must not own:

- conflict rules
- dashboard rendering
- Raspberry Pi integration

### Member 2: Mats - Airspace Core Safety Logic

Main tasks:

- tune conflict detection logic
- tune restricted-zone behavior
- tune priority handling
- add tests for rule behavior

Must not own:

- dashboard UI
- drone movement logic
- direct Raspberry Pi handling

Important rule:

- Federico is the primary owner of `core.py`
- Mats should only touch `core.py` for agreed integration points

### Member 3: Auslaug - Drone Simulator

Main tasks:

- finish autonomous drone state transitions
- keep telemetry periodic and visible
- make advisory reactions visible on the map
- keep route execution deterministic enough for demos

Must not own:

- global conflict policy
- dashboard aggregation

### Member 4: Isak - Control Gateway / Raspberry Pi

Main tasks:

- finish the HTTP control path
- finish the TCP control path
- build a Raspberry Pi client using keyboard, SenseHAT joystick, or accelerometer input
- translate input into `heading_delta`, `throttle_delta`, and `speed_delta`

Must not own:

- advisory generation
- zone logic
- dashboard rendering

### Member 5: Asne - Dashboard Backend

Main tasks:

- keep `/api/snapshot` stable
- keep `/api/stream` stable
- keep zone API endpoints stable
- bridge backend MQTT updates to the browser

Must not own:

- browser styling
- frontend map design decisions
- airspace decision logic

### Member 6: Jordan - Dashboard Frontend and Demo Polish

Main tasks:

- keep the map readable
- keep drones, paths, and zones visually clear
- improve event log readability
- support demo polish and report/demo screenshots

Must not own:

- conflict logic
- activation logic
- MQTT contracts

## Shared Rules

- Do not change `packages/shared` without team agreement.
- Do not rename MQTT topics without team agreement.
- Do not move logic from one component into another component just to make one task easier.
- Keep each commit tied to one Spec V2 use case or one component responsibility.
- If two members need the same file, one of them must be the declared primary owner.

## Shared Integration Milestones

1. Shared schema freeze
2. MQTT topic freeze
3. End-to-end registration and activation
4. End-to-end conflict and advisory flow
5. Restricted zone validation
6. Manual drone integration through control gateway
7. Dashboard readability and final demo polish
