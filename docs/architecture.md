# Architecture

This document describes the current implementation architecture of the Drone
Airspace Advisory System (DAAS). It is aligned with the final repository state
and with the intended deployment on two Raspberry Pi 4B devices and one PC.

## Design Principles

- Components communicate through explicit MQTT topics or HTTP endpoints.
- Shared message formats and topic names are centralized in `packages/shared`.
- Airspace decisions stay inside `apps/airspace_core`.
- Drone movement and mission execution stay inside `apps/drone_simulator`.
- The dashboard visualizes state but does not decide airspace behavior.
- The control gateway translates external manual input into MQTT control
  commands but does not control flight policy.

## Runtime Deployment

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

The manual Raspberry Pi does not run the drone simulation. It sends joystick
commands to the control gateway, which forwards them through MQTT to the manual
drone session running in the simulator on the PC.

## Main Components

### Airspace Core

Location:

- `apps/airspace_core/core.py`
- `apps/airspace_core/rules.py`
- `apps/airspace_core/mission.py`

Responsibilities:

- Receive drone registration messages.
- Maintain participant lifecycle state.
- Assign default missions to registered drones.
- Process dashboard mission requests.
- Publish activation messages.
- Manage restricted no-fly zones.
- Detect conflicts and restricted-airspace violations.
- Publish advisories and airspace events.
- Clear retained activations after completed or aborted missions.

State machines:

- `DroneRegistryMachine`: registration and activation lifecycle for each drone.
- `ConflictMonitorMachine`: periodic conflict and restricted-zone scan loop.

### Drone Simulator

Location:

- `apps/drone_simulator/fleet.py`
- `apps/drone_simulator/main.py`

Responsibilities:

- Create autonomous drone sessions.
- Create one optional manual drone session.
- Spawn new drones requested from the dashboard planner flow.
- Execute takeoff, cruise, evasion, landing, completion, and abort behavior.
- Publish telemetry at a fixed cadence.
- Subscribe to activations, advisories, control messages, and zone updates.
- Apply advisory behavior such as climb, descend, turn, hold, abort, or zone
  detour.

State machines:

- `DroneFlightMachine`: autonomous mission execution.
- `ManualDroneMachine`: manual drone behavior driven by control messages.

### Dashboard

Location:

- `apps/dashboard/main.py`
- `apps/dashboard/templates/index.html`
- `apps/dashboard/static/map.js`
- `apps/dashboard/static/style.css`

Responsibilities:

- Serve the operator dashboard.
- Subscribe to MQTT telemetry, activations, events, manned aircraft positions,
  and zone updates.
- Provide an initial snapshot through `/api/snapshot`.
- Push live browser updates through `/api/stream`.
- Publish mission requests through `/api/mission-requests`.
- Publish no-fly-zone commands through `/api/zones`.
- Render drones, trails, mission overlays, restricted zones, and event feed.
- Remove completed or aborted drone overlays after the cleanup delay.

### Control Gateway

Location:

- `apps/control_gateway/main.py`
- `apps/control_gateway/manual-drone-controller.py`

Responsibilities:

- Expose an HTTP API for manual drone control.
- Expose an optional TCP socket for newline-delimited JSON control input.
- Convert external control input into `ControlMessage` payloads.
- Publish control messages to the selected drone topic.
- Support the Raspberry Pi 4B with Sense HAT joystick controller.

### Shared Package

Location:

- `packages/shared/shared`

Responsibilities:

- MQTT topic definitions.
- Message schemas.
- Shared enum models.
- Runtime configuration defaults.
- Geographic helper functions.

## Communication

MQTT is the primary integration mechanism:

- Drone registration: `daas/drone/{drone_id}/register`
- Drone activation: `daas/drone/{drone_id}/activation`
- Drone telemetry: `daas/drone/{drone_id}/telemetry`
- Drone advisory: `daas/drone/{drone_id}/advisory`
- Manual drone control: `daas/drone/{drone_id}/control`
- Dashboard mission request: `daas/airspace/missions/request`
- Simulator spawn request: `daas/drone/spawn/request`
- Zone command: `daas/airspace/zones/command`
- Zone update: `daas/airspace/zones`
- Airspace event: `daas/airspace/event`
- Manned aircraft position: `daas/manned/{aircraft_id}/position`

HTTP is used for:

- Dashboard page and API on port `5001`.
- Control gateway API on port `5002`.

SSE is used for:

- Dashboard backend to browser live updates through `/api/stream`.

TCP is used for:

- Optional control gateway clients on port `9090`.

## Main Runtime Flow

1. The simulator publishes a registration for each drone.
2. The Airspace Core stores the participant and publishes an activation.
3. The simulator receives the activation and starts the mission.
4. The simulator publishes telemetry.
5. The dashboard backend receives telemetry and forwards it to the browser.
6. The Airspace Core evaluates telemetry against active constraints and
   separation rules.
7. If needed, the Airspace Core publishes advisories.
8. The simulator reacts to advisories and updates telemetry.
9. Completed or aborted missions are cleaned from retained activation state and
   dashboard overlays after the cleanup delay.

## Manual Drone Flow

1. The Sense HAT joystick on Raspberry Pi 4B #2 produces directional input.
2. `manual-drone-controller.py` sends an HTTP request to the control gateway.
3. The control gateway publishes a `ControlMessage` over MQTT.
4. `ManualDroneMachine` applies heading, throttle, and speed changes.
5. The dashboard visualizes the manual drone as `drone-rpi-001`.

## Traceability To Spec V3

- Register Drone for Monitored Flight: `DroneRegistryMachine`,
  `RegisterMessage`, and `ActivationMessage`.
- Monitor Active Airspace: telemetry topics, dashboard snapshot, and dashboard
  SSE stream.
- Resolve Airspace Conflict: `ConflictMonitorMachine`, `rules.py`, advisory
  topics, and simulator advisory handling.
- Define Restricted Airspace Constraints: dashboard zone API, `ZONE_COMMAND`,
  Airspace Core zone handling, and `ZONE_UPDATE`.
- Manual Drone Control: control gateway HTTP/TCP interfaces, Sense HAT
  controller script, and `ManualDroneMachine`.
