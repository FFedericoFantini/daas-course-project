# Architecture

## Design Principles

- Components are loosely coupled and communicate through topics or explicit HTTP endpoints.
- Each long-lived runtime responsibility has a state machine.
- Shared contracts are centralized in a single package.
- Safety-critical logic stays inside `airspace_core`.

## Main Components

### Airspace Core

Responsibilities:

- register and track drones
- activate or reject missions
- manage restricted zones and priority rules
- predict conflicts using telemetry snapshots
- issue advisories and clear-of-conflict notifications
- expose airspace state to the dashboard

State machines:

- `DroneRegistryMachine`: registration and activation lifecycle per drone
- `ConflictMonitorMachine`: periodic conflict scan loop
- `DroneFlightMachine`: takeoff -> airborne -> evading -> landing per autonomous drone
- `ManualDroneMachine`: manual flight and advisory handling for the SenseHAT-controlled drone

### Drone Simulator

Responsibilities:

- create missions
- execute drone flight lifecycle
- publish telemetry
- react to advisories
- simulate augmented/manual drones

State machines:

- `DroneFlightMachine` per drone
- optional `MissionSupervisorMachine` per simulation run

### Dashboard

Responsibilities:

- subscribe to live airspace updates
- serve map, status, and event feed
- display active drones, manned aircraft, advisories, and zones

### Control Gateway

Responsibilities:

- receive external inputs from SenseHAT or a mock controller
- translate control signals into drone control events
- forward control commands to the proper drone session

## Communication

- MQTT: telemetry, registration, activation, advisories, conflict events, zone updates
- MQTT command topic: dashboard/backend requests zone changes through `daas/airspace/zones/command`
- HTTP: dashboard shell and configuration endpoints
- SSE: backend-to-browser live feed
- TCP: optional SenseHAT input bridge

## Topic Contract

The canonical topic list is defined in `packages/shared/shared/topics.py`.

## Suggested Work Split

- Core rules and monitoring: one member
- Simulator and flight state machines: one member
- Dashboard and live visualization: one member
- Control gateway and integration support: one member

## Traceability To Spec

- UC-C1 / UC-K1: `DroneRegistryMachine`
- UC-S1: `DroneRegistryMachine` + activation messages to drone sessions
- UC-S2: `ConflictMonitorMachine` + advisory publication + `DroneFlightMachine`/`ManualDroneMachine`
- UC-S3: zone command flow (`dashboard` -> `ZONE_COMMAND` -> `airspace_core`)
- UC-S4: dashboard MQTT/SSE snapshot and stream pipeline
- No-fly zones / geolock: `airspace_core.rules`
