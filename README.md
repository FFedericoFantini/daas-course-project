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
- future SenseHAT integration
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

### Member 1: Airspace Core

Own these files/folders:
- [apps/airspace_core](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core)

Focus:
- registration lifecycle
- activation lifecycle
- conflict logic
- advisory logic
- rule enforcement

### Member 2: Drone Simulator

Own these files/folders:
- [apps/drone_simulator](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator)

Focus:
- STMPY drone state machine
- route following
- telemetry timing
- evasive maneuvers

### Member 3: Dashboard

Own these files/folders:
- [apps/dashboard](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard)

Focus:
- live UI
- visualization quality
- map interaction
- event panel
- browser-side smoothing and rendering

### Member 4: Control Gateway

Own these files/folders:
- [apps/control_gateway](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/control_gateway)

Focus:
- control API
- mock controller
- SenseHAT integration
- command routing

### Shared Ownership

These areas must be agreed before changes:
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

## Current State Machines

Implemented with STMPY:
- `DroneRegistryMachine` in [apps/airspace_core/core.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/core.py)
- `ConflictMonitorMachine` in [apps/airspace_core/core.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/core.py)
- `DroneFlightMachine` in [apps/drone_simulator/fleet.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator/fleet.py)

Not state-machine-driven right now:
- `dashboard`
- `control_gateway`

## Communication Model

- MQTT between backend components
- HTTP + SSE between dashboard backend and browser
- optional HTTP/TCP integration for control input

Canonical topics are defined in:
- [packages/shared/shared/topics.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/topics.py)

Canonical message schemas are defined in:
- [packages/shared/shared/schemas.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/schemas.py)

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

## Key Docs

- Architecture: [docs/architecture.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/architecture.md)
- Team split: [docs/team-split.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/team-split.md)

## Suggested Next Team Milestones

1. Freeze shared schemas and topics.
2. Freeze the deployment diagram and component ownership.
3. Finish end-to-end registration -> activation -> telemetry flow.
4. Finish conflict detection -> advisory -> recovery flow.
5. Add manned aircraft and restricted zone scenarios.
6. Add integration tests across components.
