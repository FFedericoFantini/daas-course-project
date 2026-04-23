# Drone Airspace Advisory System (DAAS)

This repository contains the implementation of the Drone Airspace Advisory System
(DAAS) course project. The system demonstrates monitored low-altitude drone
operations in a shared urban airspace. It includes autonomous simulated drones,
manual drone control through a Raspberry Pi 4B with Sense HAT, live dashboard
visualization, mission requests, restricted no-fly zones, conflict detection, and
advisory publication.

The intended demonstration deployment uses three devices:

| Device | Runtime role | Main responsibility |
| --- | --- | --- |
| Raspberry Pi 4B #1 | MQTT broker, Airspace Core, dashboard backend, control gateway | Central ATC/coordination node |
| PC | Drone simulator and browser client | Runs the simulated drone fleet and opens the dashboard |
| Raspberry Pi 4B #2 with Sense HAT | Manual control input | Sends joystick commands for the manual drone |

The manual Raspberry Pi does not fly a physical drone. It controls a simulated
manual drone session, normally identified as `drone-rpi-001`, through the control
gateway.

## What Works

The demonstrated system supports the following end-to-end functionality:

- Drone registration through MQTT.
- Automatic activation of simulated drone missions.
- Mission requests from the dashboard with pickup and dropoff points selected on
  the map.
- Dynamic spawning of requested drones in the simulator.
- Live telemetry publication and dashboard visualization.
- Mission route, pickup point, and dropoff point visualization.
- Cleanup of completed or aborted missions from the dashboard after a short delay.
- Temporary restricted-area creation and removal from the dashboard.
- Restricted-airspace advisories when a drone enters a no-fly zone.
- Drone-to-drone and drone-to-manned-aircraft conflict advisories.
- Manual control of one simulated drone through Raspberry Pi Sense HAT joystick
  input.
- A distinctive dashboard marker for the Raspberry Pi controlled drone.

## Repository Structure

```text
apps/
  airspace_core/      ATC logic: registration, activation, constraints, advisories
  control_gateway/    HTTP/TCP bridge for manual control commands
  dashboard/          Flask backend and browser dashboard
  drone_simulator/    Autonomous and manual drone simulation runtime
packages/
  shared/             Shared schemas, MQTT topics, config, enums, geometry helpers
docker/
  compose.yml         Optional Mosquitto broker container
  mosquitto/config/   Broker configuration used by Docker
docs/
  architecture.md
  component-contracts.md
  dashboard-demo.md
  diagrams/
tests/
  Automated tests for core logic, routes, zones, simulator behavior, and lifecycle
```

## Runtime Architecture

The system is distributed, but the components are loosely coupled.

```text
Raspberry Pi 4B #1
  Mosquitto MQTT broker
  apps.airspace_core.main
  apps.dashboard.main
  apps.control_gateway.main

PC
  apps.drone_simulator.main
  Web browser connected to http://<PI1_IP>:5001

Raspberry Pi 4B #2 with Sense HAT
  apps/control_gateway/manual-drone-controller.py
```

Main communication paths:

- MQTT is used for drone registration, activation, telemetry, advisories, zone
  updates, mission requests, and manual control messages.
- HTTP is used by the browser to access the dashboard backend.
- Server-Sent Events are used by the dashboard backend to push live updates to
  the browser.
- HTTP is used by the Sense HAT controller script to send joystick input to the
  control gateway.
- TCP port `9090` is also available in the control gateway for newline-delimited
  JSON control input, but the included Sense HAT script uses HTTP by default.

## Main Ports

| Port | Runs on | Used by | Purpose |
| --- | --- | --- | --- |
| `1883` | Raspberry Pi 4B #1 | Core, dashboard backend, simulator, control gateway | MQTT broker |
| `5001` | Raspberry Pi 4B #1 | PC browser | Dashboard HTTP server |
| `5002` | Raspberry Pi 4B #1 | Raspberry Pi 4B #2 Sense HAT script | Control gateway HTTP API |
| `9090` | Raspberry Pi 4B #1 | Optional controller clients | Control gateway TCP API |

If a firewall is enabled on Raspberry Pi 4B #1, allow these ports:

```bash
sudo ufw allow 1883/tcp
sudo ufw allow 5001/tcp
sudo ufw allow 5002/tcp
sudo ufw allow 9090/tcp
```

## Shared Configuration

The most important runtime configuration is read from environment variables.

| Variable | Default | Meaning |
| --- | --- | --- |
| `MQTT_BROKER_HOST` | `localhost` | Hostname or IP of the MQTT broker |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker TCP port |
| `DEFAULT_MANUAL_DRONE_ID` | `drone-rpi-001` | ID of the manually controlled drone |
| `CONTROL_GATEWAY_HTTP_PORT` | `5002` | HTTP port for manual control commands |
| `CONTROL_GATEWAY_TCP_PORT` | `9090` | TCP port for optional manual control clients |
| `CONTROL_URL` | `http://192.168.0.196:5002/control` | Base URL used by the Sense HAT controller script |
| `DRONE_ID` | `drone-rpi-001` | Drone controlled by the Sense HAT script |
| `DEFAULT_CRUISE_SPEED_MS` | `25` | Nominal autonomous drone speed |
| `TELEMETRY_INTERVAL_MS` | `200` | Simulator telemetry interval |

For the distributed deployment, every component that uses MQTT must point to
Raspberry Pi 4B #1:

```bash
export MQTT_BROKER_HOST=<PI1_IP>
```

On Raspberry Pi 4B #1 itself, `MQTT_BROKER_HOST=localhost` is correct because
the broker runs on the same device.

## Device Setup

Use the same repository on all three devices. Replace `<PI1_IP>` with the IP
address of Raspberry Pi 4B #1. On Raspberry Pi OS, find it with:

```bash
hostname -I
```

### Raspberry Pi 4B #1: broker, core, dashboard backend, control gateway

Install system dependencies:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip mosquitto mosquitto-clients
```

Configure Mosquitto to accept connections from the PC and the second Raspberry
Pi:

```bash
sudo tee /etc/mosquitto/conf.d/daas.conf > /dev/null <<'EOF'
listener 1883 0.0.0.0
allow_anonymous true
persistence false
EOF

sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
```

Clone the repository and install Python dependencies:

```bash
git clone https://github.com/FFedericoFantini/daas-course-project.git
cd daas-course-project

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

pip install -r apps/airspace_core/requirements.txt
pip install -r apps/dashboard/requirements.txt
pip install -r apps/control_gateway/requirements.txt
pip install -e packages/shared
```

Start the three backend services in three separate terminals:

```bash
cd daas-course-project
source .venv/bin/activate
export MQTT_BROKER_HOST=localhost
python -m apps.airspace_core.main
```

```bash
cd daas-course-project
source .venv/bin/activate
export MQTT_BROKER_HOST=localhost
python -m apps.dashboard.main
```

```bash
cd daas-course-project
source .venv/bin/activate
export MQTT_BROKER_HOST=localhost
export DEFAULT_MANUAL_DRONE_ID=drone-rpi-001
python -m apps.control_gateway.main
```

After these commands, Raspberry Pi 4B #1 should expose:

- MQTT broker at `mqtt://<PI1_IP>:1883`
- Dashboard at `http://<PI1_IP>:5001`
- Control gateway at `http://<PI1_IP>:5002`

### PC: drone simulator and dashboard browser

The PC runs the simulated drone fleet and opens the dashboard in a browser. The
simulator must connect to the MQTT broker on Raspberry Pi 4B #1.

On Windows PowerShell:

```powershell
git clone https://github.com/FFedericoFantini/daas-course-project.git
cd daas-course-project

py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

pip install -r apps\drone_simulator\requirements.txt
pip install -e packages\shared
```

Start the simulator:

```powershell
$env:MQTT_BROKER_HOST="<PI1_IP>"
python -m apps.drone_simulator.main --drones 6 --manual-drone-id drone-rpi-001
```

Then open the dashboard from the PC browser:

```text
http://<PI1_IP>:5001
```

Do not use `http://127.0.0.1:5001` from the PC in the distributed deployment,
because `127.0.0.1` would refer to the PC, not to Raspberry Pi 4B #1.

### Raspberry Pi 4B #2: Sense HAT manual controller

This device reads joystick events from the Sense HAT and sends control commands
to the control gateway running on Raspberry Pi 4B #1.

Install system dependencies:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip sense-hat
```

Clone the repository and prepare Python:

```bash
git clone https://github.com/FFedericoFantini/daas-course-project.git
cd daas-course-project

python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install requests
```

Start the Sense HAT controller:

```bash
export CONTROL_URL="http://<PI1_IP>:5002/control"
export DRONE_ID="drone-rpi-001"
python apps/control_gateway/manual-drone-controller.py
```

Joystick behavior:

- `up`: increase throttle and speed.
- `down`: decrease throttle and speed.
- `left`: turn left.
- `right`: turn right.

The LED matrix displays an arrow corresponding to the last joystick direction.
The simulator clamps manual speed and vertical speed to safe configured limits.

## Recommended Startup Order

Start the system in this order:

1. On Raspberry Pi 4B #1, start or verify Mosquitto.
2. On Raspberry Pi 4B #1, start `apps.airspace_core.main`.
3. On Raspberry Pi 4B #1, start `apps.dashboard.main`.
4. On Raspberry Pi 4B #1, start `apps.control_gateway.main`.
5. On the PC, start `apps.drone_simulator.main`.
6. On Raspberry Pi 4B #2, start `manual-drone-controller.py`.
7. On the PC, open `http://<PI1_IP>:5001`.

The core should be started before the simulator so that drone registration and
activation messages are received immediately.

## How To Use The Dashboard

The dashboard shows the current airspace state:

- Active drones and their latest telemetry.
- Drone state, altitude, heading, and mode tooltip.
- Manual Raspberry Pi controlled drone marker.
- Recent flight trail.
- Active mission route, pickup point, and dropoff point.
- Active restricted no-fly zones.
- Airspace event feed.

### Create a mission request

1. Open `http://<PI1_IP>:5001`.
2. In the `Mission Request` panel, enter a unique `drone_id`.
3. Click `Pick on map`.
4. Click once on the map for the pickup point.
5. Click once on the map for the dropoff point.
6. Adjust cruise altitude or max speed if needed.
7. Click `Request mission`.

The dashboard publishes the request to MQTT. The Airspace Core validates it,
the simulator spawns the requested drone, and the mission appears on the map
when telemetry starts arriving.

### Create a restricted no-fly zone

1. In the `No-fly Zones` panel, click `Pick on map`.
2. Click the map to choose the zone center.
3. Set the name, radius, and altitude band.
4. Click `Publish zone`.

The dashboard sends the request to the Airspace Core. The core publishes the
updated zone list, and both the simulator and dashboard receive the update.

To remove a zone, use the `Remove` button in the active zone list.

## System Workflow

The main runtime workflow is:

1. The simulator creates drone state machines and publishes registration
   messages on `daas/drone/{drone_id}/register`.
2. The Airspace Core receives each registration and publishes an activation on
   `daas/drone/{drone_id}/activation`.
3. The simulator receives the activation, starts the mission, and publishes
   telemetry on `daas/drone/{drone_id}/telemetry`.
4. The dashboard backend subscribes to telemetry, activations, zones, and events,
   then forwards live updates to the browser through Server-Sent Events.
5. The Airspace Core continuously evaluates telemetry against separation rules
   and active restricted zones.
6. If a conflict or restricted-airspace violation is detected, the core publishes
   an advisory on `daas/drone/{drone_id}/advisory`.
7. The simulator receives advisories and adjusts the drone behavior, for example
   by climbing, descending, turning, or detouring around a zone.
8. When a mission reaches a terminal state, the dashboard and core remove the
   stale mission overlay after a cleanup delay.

Manual control workflow:

1. The Sense HAT script reads joystick input on Raspberry Pi 4B #2.
2. It sends HTTP `POST` requests to `http://<PI1_IP>:5002/control/drone-rpi-001`.
3. The control gateway converts the HTTP request into an MQTT control message on
   `daas/drone/drone-rpi-001/control`.
4. The manual drone state machine in the simulator applies heading, throttle, and
   speed changes.
5. The dashboard displays the updated manual drone telemetry.

## Important MQTT Topics

| Topic | Purpose |
| --- | --- |
| `daas/drone/{drone_id}/register` | Drone registration |
| `daas/drone/{drone_id}/activation` | Mission activation |
| `daas/drone/{drone_id}/telemetry` | Live drone telemetry |
| `daas/drone/{drone_id}/advisory` | Conflict or zone advisory |
| `daas/drone/{drone_id}/control` | Manual control command |
| `daas/drone/spawn/request` | Request the simulator to spawn a dashboard-created drone |
| `daas/airspace/missions/request` | Dashboard mission request |
| `daas/airspace/zones/command` | Dashboard restricted-zone create/remove command |
| `daas/airspace/zones` | Current restricted-zone list |
| `daas/airspace/event` | Airspace event feed |

The canonical topic definitions are in `packages/shared/shared/topics.py`.

## Stop The System

Stop each Python process with `Ctrl+C` in its terminal.

If Mosquitto is running as a Raspberry Pi service and should be stopped:

```bash
sudo systemctl stop mosquitto
```

If the optional Docker broker is used instead:

```bash
docker compose -f docker/compose.yml down
```

## Optional Local Single-Machine Run

For development or quick demonstration on one Windows machine, install all
dependencies and run the helper script:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

pip install -r apps\airspace_core\requirements.txt
pip install -r apps\drone_simulator\requirements.txt
pip install -r apps\dashboard\requirements.txt
pip install -r apps\control_gateway\requirements.txt
pip install -r requirements-dev.txt
pip install -e packages\shared

.\scripts\start_local.ps1
```

This starts the core, dashboard, control gateway, and simulator on the same PC.
It still requires an MQTT broker on `localhost:1883`, for example Mosquitto or
the Docker broker from `docker/compose.yml`.

## Tests

Install test dependencies:

```bash
pip install -r requirements-dev.txt
pip install -e packages/shared
```

Run the test suite:

```bash
python -m pytest
```

The tests cover route generation, geometry helpers, conflict rules, zone
commands, mission request handling, activation idempotency, simulator takeoff,
and cleanup of retained activations.

## Troubleshooting

If the dashboard opens but no drones appear:

- Check that the PC simulator is running.
- Check that the PC has `MQTT_BROKER_HOST=<PI1_IP>`.
- Check that Raspberry Pi 4B #1 allows inbound TCP port `1883`.
- Start the Airspace Core before starting the simulator.

If the PC cannot open the dashboard:

- Use `http://<PI1_IP>:5001`, not `127.0.0.1`.
- Check that `apps.dashboard.main` is running on Raspberry Pi 4B #1.
- Check that port `5001` is reachable from the PC.

If the Sense HAT does not control the manual drone:

- Check that `apps.control_gateway.main` is running on Raspberry Pi 4B #1.
- Check that Raspberry Pi 4B #2 uses
  `CONTROL_URL=http://<PI1_IP>:5002/control`.
- Check that the simulator was started with
  `--manual-drone-id drone-rpi-001`.
- Check that both the simulator and gateway use the same manual drone ID.

If old missions appear after a restart:

- Verify that Mosquitto is configured with `persistence false`.
- Restart Mosquitto and then restart the core, dashboard, and simulator.

## Additional Documentation

- [Architecture notes](docs/architecture.md)
- [Component contracts](docs/component-contracts.md)
- [Dashboard demo notes](docs/dashboard-demo.md)
- [Deployment diagram PDF](docs/diagrams/Deployment_Diagram_Team_18.pdf)
- [Specification document PDF](docs/Specification_Document/Team_18__Spec_V3.pdf)
