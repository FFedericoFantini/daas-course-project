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
- `AdvisoryLifecycleMachine`: advisory issued -> active -> cleared/escalated

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
- UC-S1 / UC-F1: `DroneFlightMachine`
- UC-S2: `ConflictMonitorMachine`
- UC-S3: `AdvisoryLifecycleMachine`
- No-fly zones / geolock: `airspace_core.rules`
