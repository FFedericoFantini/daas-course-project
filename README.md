# DAAS Course Project

Modular Drone Airspace Advisory System designed for the TTM4115 project workflow.

This repository is intentionally split into independent components so different team members can work in parallel without blocking each other.

## Project Structure

### `apps/airspace_core`

Main responsibility:
- central airspace logic
- drone registration
- mission activation
- conflict detection
- priority rules
- restricted zones / no-fly zones
- advisory publication

This is the component that decides what the system should do.

### `apps/drone_simulator`

Main responsibility:
- drone state machines
- mission execution
- takeoff / cruise / evasion / landing
- telemetry publication
- advisory handling

This is the component that simulates drone behavior in the airspace.

### `apps/dashboard`

Main responsibility:
- operator-facing dashboards
- live map rendering
- airspace event visualization
- restricted zone visualization
- mission-planner UI for manual drone creation
- browser delivery via Flask

This is the component that shows what is happening and lets an operator request new drone missions from pickup/dropoff points.

### `apps/control_gateway`

Main responsibility:
- manual or external control input
- Raspberry Pi / SenseHAT integration
- command forwarding to drones

This is the component that injects operator or hardware control into the system.

### `packages/shared`

Main responsibility:
- shared schemas
- MQTT topics
- enums
- configuration
- geometry helpers

This package must stay stable because every other component depends on it.

## Recommended Team Split

The repository is now organized to support a team of 6 people working from the final Spec V2.

### Member 1: Federico - Airspace Core Lifecycle

Own these files/folders:
- [apps/airspace_core/core.py](apps/airspace_core/core.py)
- [apps/airspace_core/mission.py](apps/airspace_core/mission.py)

Main focus:
- registration
- activation
- mission assignment
- airspace event publication for lifecycle changes

### Member 2: Mats - Airspace Core Safety Logic

Own these files/folders:
- [apps/airspace_core/rules.py](apps/airspace_core/rules.py)
- [tests/test_rules.py](tests/test_rules.py)

Main focus:
- conflict detection
- advisory logic
- restricted-zone behavior
- priority-rule behavior

Note:
- `core.py` remains primarily owned by Federico; Mats only touches it when a reviewed integration change is needed.

### Member 3: Auslaug - Drone Simulator

Own these files/folders:
- [apps/drone_simulator/fleet.py](apps/drone_simulator/fleet.py)
- [apps/drone_simulator/main.py](apps/drone_simulator/main.py)

Main focus:
- autonomous drone state machines
- telemetry cadence
- mission progression
- advisory execution

### Member 4: Isak - Control Gateway / Raspberry Pi

Own these files/folders:
- [apps/control_gateway/main.py](apps/control_gateway/main.py)

Recommended new files:
- `apps/control_gateway/sensehat_client.py`
- `apps/control_gateway/mock_controller.py`

Main focus:
- external control input
- Raspberry Pi / SenseHAT integration
- command forwarding to the manual drone

### Member 5: Asne - Dashboard Backend

Own these files/folders:
- [apps/dashboard/main.py](apps/dashboard/main.py)

Main focus:
- snapshot endpoint
- SSE stream
- zone command API
- mission request API
- backend aggregation for the operator views

### Member 6: Jordan - Dashboard Frontend and Demo Polish

Own these files/folders:
- [apps/dashboard/templates/index.html](apps/dashboard/templates/index.html)
- [apps/dashboard/static/map.js](apps/dashboard/static/map.js)
- [apps/dashboard/static/style.css](apps/dashboard/static/style.css)
- [docs](docs)

Main focus:
- live UI quality
- map readability
- event panel clarity
- zone visualization
- planner usability
- final demo/readability polish

### Shared Ownership

These areas are contracts and must only be changed after team agreement:
- [packages/shared](packages/shared)
- [tests](tests)
- [scripts/start_local.ps1](scripts/start_local.ps1)

## Component Boundaries

To avoid team collisions:

- `airspace_core` must not contain dashboard rendering logic
- `dashboard` must not contain airspace decision logic
- `drone_simulator` must not decide global rules
- `control_gateway` must not bypass the shared topic/schema contract
- all cross-component contracts must go through `packages/shared`

## Parallel Development Workflow

Use this workflow if teammates are developing directly from the Spec V2 and this repository.

1. Read the Spec V2 use cases first.
2. Read [docs/architecture.md](docs/architecture.md) and [docs/component-contracts.md](docs/component-contracts.md).
3. Pick one owned component and work only inside that component unless the team has agreed a shared-contract change.
4. Treat `packages/shared` as frozen by default.
5. Test each component locally against the current MQTT topics before integrating UI or hardware changes.
6. Merge only after the component still satisfies the related Spec V2 use case.

Practical rule:

- if you need to change a topic name, message schema, enum, or shared config value, stop and sync with the whole team first
- if you only need to change local behavior inside your component, do it without touching shared contracts

## Suggested Work Order

If the team wants to avoid blocking:

1. Freeze [packages/shared/shared/topics.py](packages/shared/shared/topics.py) and [packages/shared/shared/schemas.py](packages/shared/shared/schemas.py).
2. Finish the end-to-end flow `register -> activate -> telemetry`.
3. Finish the end-to-end flow `detect conflict -> publish advisory -> drone reacts`.
4. Finish the end-to-end flow `define zone -> publish zone update -> dashboard shows zone`.
5. Connect the manual drone path `SenseHAT/control gateway -> control topic -> manual drone session`.
6. Finish the planner flow `mission request -> spawn drone -> activate route -> dashboard shows new mission`.

## Current State Machines

Implemented with STMPY:
- `DroneRegistryMachine` in [apps/airspace_core/core.py](apps/airspace_core/core.py)
- `ConflictMonitorMachine` in [apps/airspace_core/core.py](apps/airspace_core/core.py)
- `DroneFlightMachine` in [apps/drone_simulator/fleet.py](apps/drone_simulator/fleet.py)
- `ManualDroneMachine` in [apps/drone_simulator/fleet.py](apps/drone_simulator/fleet.py)

Not state-machine-driven right now:
- `dashboard`
- `control_gateway`

## Communication Model

- MQTT between backend components
- MQTT zone-command flow between dashboard/backend and airspace core
- MQTT mission-request flow between planner dashboard, airspace core, and drone simulator
- HTTP + SSE between dashboard backend and browser
- HTTP + TCP integration for control input

Canonical topics are defined in:
- [packages/shared/shared/topics.py](packages/shared/shared/topics.py)

Canonical message schemas are defined in:
- [packages/shared/shared/schemas.py](packages/shared/shared/schemas.py)

## Traceability To Spec V2

- `Register Drone for Monitored Flight` -> `apps/airspace_core` + `apps/drone_simulator`
- `Register Drone for Monitored Flight (manual planner flow)` -> `apps/dashboard` + `apps/airspace_core` + `apps/drone_simulator`
- `Resolve Airspace Conflict` -> `apps/airspace_core` + `apps/drone_simulator`
- `Define Restricted Airspace Constraints` -> `apps/dashboard` + `apps/airspace_core`
- `Monitor Active Airspace` -> `apps/dashboard`

## Deployment Diagram

The repository implementation follows the same deployment structure described in the final Spec V2.

- [Open the deployment diagram PDF](docs/diagrams/Deployment_Diagram_Team_18.pdf)

## Minimal Local Run

### 1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r apps\airspace_core\requirements.txt
pip install -r apps\drone_simulator\requirements.txt
pip install -r apps\dashboard\requirements.txt
pip install -r apps\control_gateway\requirements.txt
pip install -r requirements-dev.txt
pip install -e packages\shared
```

### 3. Start the broker

```powershell
docker compose -f docker\compose.yml up -d
```

If you already have Mosquitto running locally, you can use that instead.

### 4. Start the components

```powershell
python -m apps.airspace_core.main
python -m apps.dashboard.main
python -m apps.control_gateway.main
python -m apps.drone_simulator.main --drones 6 --manual-drone-id drone-rpi-001
```

Or use:

```powershell
.\scripts\start_local.ps1
```

## Main URLs

- Monitoring Dashboard: [http://127.0.0.1:5001](http://127.0.0.1:5001)
- Mission Planner Dashboard: [http://127.0.0.1:5001/planner](http://127.0.0.1:5001/planner)
- Control Gateway API: [http://127.0.0.1:5002](http://127.0.0.1:5002)

## Mission Planner Dashboard

The repository now includes a second dashboard page dedicated to manual mission creation.

Planner flow:

- open [http://127.0.0.1:5001/planner](http://127.0.0.1:5001/planner)
- choose a unique `drone_id`
- click the map once for the pickup point
- click the map again for the dropoff point
- submit the mission request

What happens next:

- the planner publishes a mission request
- the airspace core stores the requested route
- the simulator spawns the requested drone dynamically
- the airspace core activates that drone with the requested pickup/dropoff route
- the monitoring dashboard starts showing the new drone and mission

## Raspberry Pi / SenseHAT Controlled Drone

By default, one drone is reserved for manual control:
- `drone-rpi-001`

This drone is created by the simulator as a manual STMPY machine.
The remaining drones continue to fly autonomously.

### How it works

- `apps/drone_simulator` creates one manual drone machine
- `apps/control_gateway` accepts control input over HTTP or TCP
- the gateway republishes commands on the drone control MQTT topic
- the manual drone updates heading, speed, and climb/descent from those commands

### HTTP control example

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:5002/control/drone-rpi-001" `
  -ContentType "application/json" `
  -Body '{"heading_delta":8,"throttle_delta":0.6,"speed_delta":0.8}'
```

### TCP control example for Raspberry Pi

The TCP gateway listens on port `9090`.

Each command must be sent as one JSON line:

```json
{"drone_id":"drone-rpi-001","heading_delta":6,"throttle_delta":0.4,"speed_delta":0.5}
```

This makes it easy to connect a Raspberry Pi process that reads SenseHAT values and forwards them directly.

## Key Docs

- Architecture: [docs/architecture.md](docs/architecture.md)
- Component contracts: [docs/component-contracts.md](docs/component-contracts.md)
- Development plan: [docs/development-plan.md](docs/development-plan.md)
- Team split: [docs/team-split.md](docs/team-split.md)

## Suggested Next Team Milestones

1. Freeze shared schemas and topics.
2. Freeze the deployment diagram and component ownership.
3. Finish end-to-end registration -> activation -> telemetry flow.
4. Finish conflict detection -> advisory -> recovery flow.
5. Add manned aircraft and restricted zone scenarios.
6. Add integration tests across components.

