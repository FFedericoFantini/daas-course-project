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

Use this split if you have four people.

### Workstream A: Airspace Core

Owner:

- one teammate

Own files:

- [apps/airspace_core/core.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/core.py)
- [apps/airspace_core/rules.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/rules.py)
- [apps/airspace_core/mission.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/mission.py)
- [apps/airspace_core/main.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/airspace_core/main.py)

Main responsibility:

- central coordination logic
- registration and activation
- conflict detection
- advisory publication
- zone command handling
- airspace event publication

Concrete tasks:

1. Finish the registration lifecycle in `core.py`.
2. Keep one mission assignment flow per registered drone.
3. Improve conflict handling so it matches the Spec V2 state machine more closely.
4. Ensure zone create/update/remove commands are handled cleanly.
5. Publish airspace events for registration, activation, zone updates, advisories, and recovery.
6. Keep `rules.py` as the only place for zone and conflict logic.

Definition of done:

- a drone can register and receive an activation
- the core publishes telemetry-driven advisories
- the core accepts zone commands and republishes current zones
- dashboard and simulator can run without importing core internals

### Workstream B: Drone Simulator

Owner:

- one teammate

Own files:

- [apps/drone_simulator/fleet.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator/fleet.py)
- [apps/drone_simulator/main.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/drone_simulator/main.py)

Main responsibility:

- drone session behavior
- state machines
- route execution
- telemetry publication
- advisory execution
- manual drone behavior

Concrete tasks:

1. Stabilize `DroneFlightMachine` for the autonomous drones.
2. Stabilize `ManualDroneMachine` for the Raspberry Pi controlled drone.
3. Keep telemetry periodic and consistent across states.
4. Make advisory handling visible in telemetry and drone state.
5. Make route recovery after evasion deterministic enough for demos.
6. Add small tests for the simulator logic if possible.

Definition of done:

- autonomous drones complete `takeoff -> airborne -> landing`
- manual drone reacts to control messages
- advisory messages cause visible evasion behavior
- telemetry reflects the drone state correctly on the dashboard

### Workstream C: Dashboard

Owner:

- one teammate

Own files:

- [apps/dashboard/main.py](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard/main.py)
- [apps/dashboard/templates/index.html](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard/templates/index.html)
- [apps/dashboard/static/map.js](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard/static/map.js)
- [apps/dashboard/static/style.css](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/apps/dashboard/static/style.css)

Main responsibility:

- operator-facing monitoring interface
- live updates
- map rendering
- event visibility
- zone visualization and zone submission

Concrete tasks:

1. Keep `/api/snapshot` and `/api/stream` stable.
2. Improve the live map so drones, paths, and zones are readable.
3. Show conflict/advisory-related events clearly in the UI.
4. Add or improve the UI flow for creating and deleting restricted zones.
5. Make sure the dashboard reflects the current airspace state without embedding any decision logic.

Definition of done:

- drones are visible and updated live
- zones are visible
- airspace events are readable
- a user can create or remove a zone through the dashboard/backend flow

### Workstream D: Control Gateway / Raspberry Pi

Owner:

- one teammate

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
5. Send those commands to the control gateway so the manual drone moves on the dashboard.

Definition of done:

- a control client can connect from a Raspberry Pi
- commands reach the manual drone through MQTT
- the manual drone visibly moves on the dashboard

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

- `core/...`
- `sim/...`
- `dashboard/...`
- `control/...`

## What Each Teammate Must Read First

Before writing code, each teammate should read:

1. the relevant Spec V2 use cases
2. [README.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/README.md)
3. [docs/architecture.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/architecture.md)
4. [docs/component-contracts.md](/C:/Users/fedef/OneDrive/Documenti/Playground/daas-course-project/docs/component-contracts.md)
5. this file

## If You Have Only Three People

Combine these workstreams:

- one person: Airspace Core
- one person: Drone Simulator
- one person: Dashboard + Control Gateway

In that case, do not combine Airspace Core and Drone Simulator under the same person unless absolutely necessary.
