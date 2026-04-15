# Drone Airspace Advisory System (DAAS)

This repository contains the implementation of the DAAS course project. The system demonstrates monitored low-altitude drone operations in shared urban airspace with live visualization, mission assignment, restricted-airspace handling, conflict advisories, and manual drone control integration.

## System Overview

The project is organized as a distributed system with four main runtime components:

- `apps/airspace_core`
  - central coordination logic
  - drone registration and activation
  - mission assignment
  - restricted zone management
  - conflict detection and advisory publication

- `apps/drone_simulator`
  - autonomous drone mission execution
  - telemetry publication
  - advisory handling
  - one manual drone session for external control input

- `apps/dashboard`
  - live monitoring dashboard
  - mission request form with pickup and dropoff selection on the map
  - no-fly zone creation and removal
  - event feed and mission overlays

- `apps/control_gateway`
  - HTTP and TCP control input bridge
  - forwards manual control commands to the reserved manual drone

Shared contracts used by all components are defined in `packages/shared`.

## Implemented Functionality

The current implementation supports these end-to-end flows:

- drone registration through MQTT
- monitored-flight activation with mission routes
- continuous telemetry updates from simulated drones
- live airspace monitoring in the browser
- mission requests from the dashboard with pickup/dropoff selection
- dynamic spawning of requested drones
- creation and removal of restricted no-fly zones
- conflict detection and advisory publication
- advisory execution in the simulator
- manual control of one dedicated drone through the control gateway

## Repository Structure

```text
apps/
  airspace_core/      Central coordination logic
  control_gateway/    HTTP/TCP control bridge
  dashboard/          Flask backend and browser UI
  drone_simulator/    Simulated drone sessions
packages/
  shared/             Shared schemas, topics, config, enums, geometry helpers
docker/
  compose.yml         Mosquitto broker container
docs/
  architecture.md
  dashboard-demo.md
  diagrams/
tests/
```

## Prerequisites

- Python 3.12
- `pip`
- an MQTT broker on `localhost:1883`

You can use either:

- a local Mosquitto installation/service
- or Docker Desktop with the broker from `docker/compose.yml`

## Installation

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
pip install -r apps\airspace_core\requirements.txt
pip install -r apps\drone_simulator\requirements.txt
pip install -r apps\dashboard\requirements.txt
pip install -r apps\control_gateway\requirements.txt
pip install -r requirements-dev.txt
pip install -e packages\shared
```

## Start the MQTT Broker

If you use Docker:

```powershell
docker compose -f docker\compose.yml up -d
```

If you already have a local Mosquitto service running on port `1883`, you can use that instead.

## Run the Project

### Option 1: Windows helper script

```powershell
.\scripts\start_local.ps1
```

This starts:

- `apps.airspace_core.main`
- `apps.dashboard.main`
- `apps.control_gateway.main`
- `apps.drone_simulator.main --drones 6 --manual-drone-id drone-rpi-001`

### Option 2: Start each component manually

Open four terminals in the repository root and run:

```powershell
python -m apps.airspace_core.main
```

```powershell
python -m apps.dashboard.main
```

```powershell
python -m apps.control_gateway.main
```

```powershell
python -m apps.drone_simulator.main --drones 6 --manual-drone-id drone-rpi-001
```

## Main URLs

- Dashboard: [http://127.0.0.1:5001](http://127.0.0.1:5001)
- Control gateway: [http://127.0.0.1:5002](http://127.0.0.1:5002)

## Using the Dashboard

The main dashboard provides:

- live drone positions and trails
- mission overlays
- event log
- mission request form
- no-fly zone management

### Create a mission

1. Open the dashboard.
2. Enter a unique `drone_id`.
3. Click `Pick on map` in the `Mission Request` section.
4. Click once for the pickup point.
5. Click once for the dropoff point.
6. Submit the form.

The airspace core stores the request, the simulator spawns the drone, and the mission appears in the dashboard.

### Create a no-fly zone

1. Open the dashboard.
2. In the `No-fly Zones` section, click `Pick on map`.
3. Select the center point.
4. Set name, radius, and altitude range.
5. Submit the form.

The zone is published to the airspace core and then shown in the live view.

## Manual Drone Control

One drone is reserved for manual control by default:

- `drone-rpi-001`

This drone can be controlled through the control gateway over HTTP or TCP.

### HTTP example

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:5002/control/drone-rpi-001" `
  -ContentType "application/json" `
  -Body '{"heading_delta":8,"throttle_delta":0.6,"speed_delta":0.8}'
```

### TCP example

The TCP gateway listens on port `9090`. Send one JSON object per line:

```json
{"drone_id":"drone-rpi-001","heading_delta":6,"throttle_delta":0.4,"speed_delta":0.5}
```

This is the integration point intended for Raspberry Pi / Sense HAT input.

## Stop the Project

If you started the components manually, stop them with `Ctrl+C` in each terminal.

If you used Docker for the broker, stop it with:

```powershell
docker compose -f docker\compose.yml down
```

## Tests

Run the automated test suite with:

```powershell
python -m pytest
```

## Additional Documentation

- [Architecture notes](docs/architecture.md)
- [Dashboard demo notes](docs/dashboard-demo.md)
- [Deployment diagram PDF](docs/diagrams/Deployment_Diagram_Team_18.pdf)
