# DAAS Course Project

Modular Drone Airspace Advisory System rebuilt from scratch to align with the project specification and the TTM4115 course guidance on components, communication, and STMPY state machines.

## Goals

- Split the system into independent components so team members can work in parallel.
- Use STMPY to model the lifecycle of active system entities.
- Use MQTT for asynchronous inter-component communication.
- Use HTTP/SSE for dashboard access.
- Cover registration, mission activation, telemetry publication, conflict detection, priority rules, advisories, restricted zones, and safety monitoring.

## Components

- `apps/airspace_core`
  Central airspace authority. Tracks entities, applies rules, detects conflicts, and issues advisories.
- `apps/drone_simulator`
  Runs one or more drone state machines, mission execution, telemetry publication, and advisory handling.
- `apps/dashboard`
  Flask dashboard with REST + SSE bridge. Renders drones, events, advisories, and zones.
- `apps/control_gateway`
  SenseHAT or mock control bridge for manually controlled drones.
- `packages/shared`
  Shared schemas, topics, configuration, geometry, and enums used by every component.

## Team Split

- Member A: `apps/airspace_core`
- Member B: `apps/drone_simulator`
- Member C: `apps/dashboard`
- Member D: `apps/control_gateway`
- Shared ownership: `packages/shared`, integration tests, and `docs/`

## Running

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r apps\airspace_core\requirements.txt
pip install -r apps\drone_simulator\requirements.txt
pip install -r apps\dashboard\requirements.txt
pip install -r apps\control_gateway\requirements.txt
pip install -e packages\shared
docker compose -f docker\compose.yml up -d
python -m apps.airspace_core.main
python -m apps.dashboard.main
python -m apps.drone_simulator.main --drones 5
```

## Architecture

See [docs/architecture.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/architecture.md).
