# Development Plan

This document turns the final Spec V2 into a concrete development plan for the repository.

The goal is to let multiple teammates work in parallel without changing the same files or breaking the shared contracts.

## Project Goal

Build a DAAS prototype that supports these sea-level use cases:

- `Register Drone for Monitored Flight`
- `Resolve Airspace Conflict`
- `Define Restricted Airspace Constraints`
- `Monitor Active Airspace`

The implementation must stay aligned with:

- [docs/architecture.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/architecture.md)
- [docs/component-contracts.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/component-contracts.md)
- the final Spec V2

## Freeze First

Before teammates start in parallel, treat these files as shared contracts:

- [packages/shared/shared/topics.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/topics.py)
- [packages/shared/shared/schemas.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/schemas.py)
- [packages/shared/shared/models.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/models.py)
- [packages/shared/shared/config.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/config.py)

Rule:

- do not change these files casually
- if one of these files must change, the whole team must sync first

## Recommended Team Split

Use this split if you have six people.

### Workstream A1: Airspace Core Lifecycle

Owner:

- Federico

Own files:

- [apps/airspace_core/core.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/core.py)
- [apps/airspace_core/mission.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/mission.py)
- [apps/airspace_core/main.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/main.py)

Main responsibility:

- central lifecycle logic
- registration and activation
- mission assignment
- lifecycle events

Concrete tasks:

1. Finish the registration lifecycle in `core.py`.
2. Keep one mission assignment flow per registered drone.
3. Keep activation publishing stable.
4. Keep lifecycle-related events stable.

Definition of done:

- a drone can register and receive an activation
- the dashboard shows the drone after activation
- simulator registration stays idempotent

### Workstream A2: Airspace Core Safety Logic

Owner:

- Mats

Own files:

- [apps/airspace_core/rules.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/rules.py)
- [tests/test_rules.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/tests/test_rules.py)
- [tests/test_zone_commands.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/tests/test_zone_commands.py)

Main responsibility:

- conflict detection
- advisory policy
- restricted-zone behavior
- priority rules

Concrete tasks:

1. Improve conflict handling so it matches the Spec V2 state machine more closely.
2. Keep zone and conflict logic centralized in `rules.py`.
3. Add tests for edge cases in advisory and zone behavior.
4. Coordinate with Federico for any required integration hook inside `core.py`.

Definition of done:

- conflict scenarios generate deterministic advisories
- zone violations generate consistent behavior
- tests cover the rule logic well enough for demo confidence

### Workstream B1: Drone Simulator

Owner:

- Auslaug

Own files:

- [apps/drone_simulator/fleet.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator/fleet.py)
- [apps/drone_simulator/main.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator/main.py)

Main responsibility:

- autonomous drone behavior
- route execution
- telemetry cadence
- advisory execution

Concrete tasks:

1. Stabilize `DroneFlightMachine` for the autonomous drones.
2. Keep telemetry periodic and consistent across states.
3. Make advisory handling visible in telemetry and drone state.
4. Make route recovery after evasion deterministic enough for demos.

Definition of done:

- autonomous drones complete `takeoff -> airborne -> landing`
- advisory messages cause visible evasion behavior
- telemetry reflects the drone state correctly on the dashboard

### Workstream B2: Control Gateway / Raspberry Pi

Owner:

- Isak

Own files:

- [apps/control_gateway/main.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/control_gateway/main.py)

Recommended new files to create if needed:

- `apps/control_gateway/sensehat_client.py`
- `apps/control_gateway/mock_controller.py`

Main responsibility:

- external control ingestion
- Raspberry Pi / SenseHAT bridge
- TCP and HTTP command forwarding
- support for the manual drone demo scenario

Concrete tasks:

1. Keep the HTTP control endpoint stable.
2. Keep the TCP control bridge stable.
3. Build a Raspberry Pi client that reads keyboard input, SenseHAT joystick, or accelerometer input.
4. Convert those inputs into `heading_delta`, `throttle_delta`, and `speed_delta`.
5. Coordinate with Auslaug to validate the manual drone path end to end.

Definition of done:

- a control client can connect from a Raspberry Pi
- commands reach the manual drone through MQTT
- the manual drone visibly moves on the dashboard

### Workstream C1: Dashboard Backend

Owner:

- Asne

Own files:

- [apps/dashboard/main.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard/main.py)

Main responsibility:

- operator-facing backend
- snapshot and stream
- zone command API
- backend aggregation

Concrete tasks:

1. Keep `/api/snapshot` and `/api/stream` stable.
2. Keep zone create/delete endpoints stable.
3. Make sure backend payloads remain compatible with the frontend.
4. Do not embed airspace decision logic in the backend.

Definition of done:

- dashboard boots from `/api/snapshot`
- live updates work through SSE
- zone commands can be submitted from the UI or API

### Workstream C2: Dashboard Frontend and Demo Polish

Owner:

- Jordan

Own files:

- [apps/dashboard/templates/index.html](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard/templates/index.html)
- [apps/dashboard/static/map.js](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard/static/map.js)
- [apps/dashboard/static/style.css](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard/static/style.css)
- [docs](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs)

Main responsibility:

- map rendering
- event visibility
- zone visualization
- dashboard readability
- final demo polish

Concrete tasks:

1. Make drones, zones, and events readable at demo scale.
2. Improve visual distinction for advisory and conflict states.
3. Keep the UI aligned with what the Spec V2 promises.
4. Support final demo screenshots and documentation polish.

Definition of done:

- the dashboard is readable during live updates
- conflict and zone states are visually obvious
- the frontend is stable enough for demo recording

## Shared Work Only During Integration

These files should only be touched during agreed integration work:

- [packages/shared/shared/topics.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/topics.py)
- [packages/shared/shared/schemas.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/schemas.py)
- [packages/shared/shared/models.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/models.py)
- [packages/shared/shared/config.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/packages/shared/shared/config.py)
- [scripts/start_local.ps1](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/scripts/start_local.ps1)
- [README.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/README.md)

## Integration Order

Follow this order to reduce blocking.

### Milestone 1: Shared Contract Freeze

Deliverables:

- topics finalized
- schemas finalized
- config defaults finalized

### Milestone 2: UC-S1 End-to-End

Use case:

- `Register Drone for Monitored Flight`

Flow:

- simulator publishes registration
- airspace core stores the drone
- airspace core publishes activation
- drone session starts
- dashboard shows the drone

### Milestone 3: UC-S4 End-to-End

Use case:

- `Monitor Active Airspace`

Flow:

- telemetry reaches the core
- dashboard receives snapshot and stream updates
- drones and events are visible live

### Milestone 4: UC-S2 End-to-End

Use case:

- `Resolve Airspace Conflict`

Flow:

- conflict detected by the core
- advisory published
- drone changes behavior
- telemetry reflects evasion
- event log shows the resolution

### Milestone 5: UC-S3 End-to-End

Use case:

- `Define Restricted Airspace Constraints`

Flow:

- dashboard or API submits a zone command
- core updates active zones
- zone update is published
- dashboard shows the new zone

### Milestone 6: Manual Drone Demo

Flow:

- Raspberry Pi or mock client sends control input
- control gateway forwards commands
- manual drone reacts
- dashboard shows manual movement

## Branch and Merge Rules

Keep this simple:

- one branch per workstream
- one feature/fix per commit
- do not mix UI, simulator, and core logic in the same commit
- merge only after the related use-case flow still works locally

Recommended branch names:

- `core-lifecycle/...`
- `core-safety/...`
- `sim/...`
- `control/...`
- `dashboard-backend/...`
- `dashboard-frontend/...`

## What Each Teammate Must Read First

Before writing code, each teammate should read:

1. the relevant Spec V2 use cases
2. [README.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/README.md)
3. [docs/architecture.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/architecture.md)
4. [docs/component-contracts.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/component-contracts.md)
5. this file

## If You Have Only Four People

Combine these workstreams:

- one person: Airspace Core Lifecycle + Airspace Core Safety
- one person: Drone Simulator
- one person: Dashboard Backend + Dashboard Frontend
- one person: Control Gateway / Raspberry Pi

## If You Have Only Three People

Combine these workstreams:

- one person: Airspace Core
- one person: Drone Simulator + Control Gateway
- one person: Dashboard

In that case, do not combine Airspace Core and Drone Simulator under the same person unless absolutely necessary.
