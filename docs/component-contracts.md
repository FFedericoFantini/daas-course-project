# Component Contracts

This document freezes the practical contracts between components so the team can work in parallel without changing each other's internals.

## Ownership Boundaries

### `apps/airspace_core`

Owns:

- drone registration lifecycle
- mission activation
- restricted-airspace constraints
- conflict detection
- advisory publication
- airspace events

Must not own:

- browser rendering
- map visuals
- SenseHAT input parsing
- local drone motion logic

### `apps/drone_simulator`

Owns:

- autonomous drone mission sessions
- manual drone session
- telemetry cadence
- mission progression
- advisory execution

Must not own:

- global airspace rules
- zone validation policies
- dashboard state aggregation

### `apps/dashboard`

Owns:

- HTTP shell for the operator UI
- SSE live updates to the browser
- map/event visualization
- zone-definition request submission

Must not own:

- direct airspace decisions
- conflict logic
- mission activation logic

### `apps/control_gateway`

Owns:

- Raspberry Pi or mock external control input
- TCP/HTTP control ingestion
- translation to MQTT control messages

Must not own:

- drone registration
- advisory generation
- dashboard state

### `packages/shared`

Owns:

- topic names
- message schemas
- enums
- configuration
- geometry helpers

This package is the shared contract. Changes here must be agreed by the whole team.

## Stable Interfaces

### MQTT Topics

- `daas/drone/{drone_id}/register`
- `daas/drone/{drone_id}/activation`
- `daas/drone/{drone_id}/telemetry`
- `daas/drone/{drone_id}/advisory`
- `daas/drone/{drone_id}/control`
- `daas/manned/{aircraft_id}/position`
- `daas/airspace/event`
- `daas/airspace/zones`
- `daas/airspace/zones/command`

### Dashboard HTTP Endpoints

- `GET /` -> operator dashboard shell
- `GET /api/snapshot` -> current aggregated state for bootstrap
- `GET /api/stream` -> SSE live feed
- `POST /api/zones` -> request zone create/update
- `DELETE /api/zones/<zone_id>` -> request zone removal

### Control Gateway HTTP/TCP Endpoints

- `GET /` -> capability/status probe
- `POST /control/<drone_id>` -> send manual control
- TCP `9090` -> newline-delimited JSON control input

## Recommended Parallel Work Plan

### Workstream 1: Airspace Core

Deliverables:

- registration/activation lifecycle
- zone command handling
- conflict/advisory logic
- event publication

Integration dependency:

- depends only on stable schemas/topics from `packages/shared`

### Workstream 2: Drone Simulator

Deliverables:

- drone session behavior
- manual drone behavior
- telemetry publication
- advisory response

Integration dependency:

- depends only on activation/advisory/control topic contracts

### Workstream 3: Dashboard

Deliverables:

- live map
- event log
- zone visualization
- zone definition UI or API client

Integration dependency:

- depends only on snapshot/SSE payloads and zone command API

### Workstream 4: Control Gateway

Deliverables:

- SenseHAT bridge
- HTTP/TCP control ingestion
- command publishing

Integration dependency:

- depends only on the control topic contract
