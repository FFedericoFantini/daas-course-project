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
- operator-facing dashboard
- live map rendering
- airspace event visualization
- restricted zone visualization
- browser delivery via Flask

This is the component that shows what is happening.

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

This split is aligned with the final Spec V2 so each teammate can work on one component with minimal overlap.

### Member 1: Airspace Core

Own these files/folders:
- [apps/airspace_core](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core)

Main Spec V2 alignment:
- `Register Drone for Monitored Flight`
- `Resolve Airspace Conflict`
- `Define Restricted Airspace Constraints`

Main deliverables:
- registration and activation lifecycle
- conflict detection and advisory publication
- zone command handling
- airspace event generation
- manned-aircraft and priority-rule support

Do not own:
- browser rendering
- map visuals
- SenseHAT input parsing
- local drone motion logic

### Member 2: Drone Simulator

Own these files/folders:
- [apps/drone_simulator](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator)

Main Spec V2 alignment:
- `Register Drone for Monitored Flight`
- `Resolve Airspace Conflict`

Main deliverables:
- `DroneFlightMachine` and `ManualDroneMachine`
- mission execution and route following
- telemetry cadence
- advisory execution and recovery
- manual drone behavior for Raspberry Pi input

Do not own:
- global airspace rules
- dashboard state aggregation
- zone validation policy

### Member 3: Dashboard

Own these files/folders:
- [apps/dashboard](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard)

Main Spec V2 alignment:
- `Monitor Active Airspace`
- `Define Restricted Airspace Constraints`

Main deliverables:
- live airspace map
- event log and status panels
- zone visualization
- zone-management UI or API client flow
- browser-side smoothing and operator visibility

Do not own:
- conflict logic
- mission activation logic
- drone control routing

### Member 4: Control Gateway / Raspberry Pi

Own these files/folders:
- [apps/control_gateway](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/control_gateway)

Main Spec V2 alignment:
- manual-control integration for the monitored drone scenario

Main deliverables:
- HTTP/TCP control ingestion
- SenseHAT bridge
- command validation and forwarding
- integration support for the manual drone session

Do not own:
- drone registration
- advisory generation
- dashboard aggregation logic

### Shared Ownership

These areas are contracts and must only be changed after team agreement:
- [packages/shared](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared)
- [docs](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs)
- [tests](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/tests)

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
2. Read [docs/architecture.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/architecture.md) and [docs/component-contracts.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/component-contracts.md).
3. Pick one owned component and work only inside that component unless the team has agreed a shared-contract change.
4. Treat `packages/shared` as frozen by default.
5. Test each component locally against the current MQTT topics before integrating UI or hardware changes.
6. Merge only after the component still satisfies the related Spec V2 use case.

Practical rule:

- if you need to change a topic name, message schema, enum, or shared config value, stop and sync with the whole team first
- if you only need to change local behavior inside your component, do it without touching shared contracts

## Suggested Work Order

If the team wants to avoid blocking:

1. Freeze [packages/shared/shared/topics.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/topics.py) and [packages/shared/shared/schemas.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/schemas.py).
2. Finish the end-to-end flow `register -> activate -> telemetry`.
3. Finish the end-to-end flow `detect conflict -> publish advisory -> drone reacts`.
4. Finish the end-to-end flow `define zone -> publish zone update -> dashboard shows zone`.
5. Connect the manual drone path `SenseHAT/control gateway -> control topic -> manual drone session`.

## Current State Machines

Implemented with STMPY:
- `DroneRegistryMachine` in [apps/airspace_core/core.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/core.py)
- `ConflictMonitorMachine` in [apps/airspace_core/core.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/core.py)
- `DroneFlightMachine` in [apps/drone_simulator/fleet.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator/fleet.py)
- `ManualDroneMachine` in [apps/drone_simulator/fleet.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator/fleet.py)

Not state-machine-driven right now:
- `dashboard`
- `control_gateway`

## Communication Model

- MQTT between backend components
- MQTT zone-command flow between dashboard/backend and airspace core
- HTTP + SSE between dashboard backend and browser
- HTTP + TCP integration for control input

Canonical topics are defined in:
- [packages/shared/shared/topics.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/topics.py)

Canonical message schemas are defined in:
- [packages/shared/shared/schemas.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/schemas.py)

## Traceability To Spec V2

- `Register Drone for Monitored Flight` -> `apps/airspace_core` + `apps/drone_simulator`
- `Resolve Airspace Conflict` -> `apps/airspace_core` + `apps/drone_simulator`
- `Define Restricted Airspace Constraints` -> `apps/dashboard` + `apps/airspace_core`
- `Monitor Active Airspace` -> `apps/dashboard`

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
python -m apps.drone_simulator.main --drones 5
```

Or use:

```powershell
.\scripts\start_local.ps1
```

## Main URLs

- Dashboard: [http://127.0.0.1:5001](http://127.0.0.1:5001)
- Control Gateway API: [http://127.0.0.1:5002](http://127.0.0.1:5002)

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

- Architecture: [docs/architecture.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/architecture.md)
- Component contracts: [docs/component-contracts.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/component-contracts.md)
- Team split: [docs/team-split.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/team-split.md)

## Suggested Next Team Milestones

1. Freeze shared schemas and topics.
2. Freeze the deployment diagram and component ownership.
3. Finish end-to-end registration -> activation -> telemetry flow.
4. Finish conflict detection -> advisory -> recovery flow.
5. Add manned aircraft and restricted zone scenarios.
6. Add integration tests across components.
