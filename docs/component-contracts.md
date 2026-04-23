# Component Contracts

This document defines the current contracts between the DAAS runtime components.
It is intended to make clear which component owns each responsibility and which
interfaces must remain stable.

## Ownership Boundaries

### `apps/airspace_core`

Owns:

- Drone registration lifecycle.
- Mission activation and mission-request validation.
- Retained activation cleanup.
- Restricted-airspace constraints.
- Conflict detection and advisory generation.
- Airspace event publication.

Must not own:

- Browser rendering.
- Dashboard UI state management.
- Sense HAT input parsing.
- Local drone movement simulation.

### `apps/drone_simulator`

Owns:

- Autonomous drone sessions.
- Manual drone session.
- Drone takeoff, cruise, evasion, landing, completion, and abort behavior.
- Telemetry cadence.
- Advisory execution.
- Dashboard-requested drone spawning.

Must not own:

- Global airspace policy.
- Zone command validation policy.
- Dashboard aggregation.
- Manual input device handling.

### `apps/dashboard`

Owns:

- Operator dashboard HTTP shell.
- `/api/snapshot` bootstrap data.
- `/api/stream` live browser feed.
- Browser map rendering.
- Mission-request form and API.
- Zone create/remove form and API.
- Dashboard-only cleanup of completed mission overlays.

Must not own:

- Conflict detection.
- Mission activation decisions.
- Advisory policy.
- Drone movement simulation.

### `apps/control_gateway`

Owns:

- HTTP manual control endpoint.
- Optional TCP manual control bridge.
- Translation from external input payloads to shared `ControlMessage` payloads.
- Publishing manual control commands to MQTT.
- Raspberry Pi Sense HAT controller script.

Must not own:

- Drone registration.
- Airspace advisories.
- Zone logic.
- Dashboard visualization.

### `packages/shared`

Owns:

- MQTT topic names.
- Message schemas.
- Shared enums.
- Runtime configuration defaults.
- Geographic helper functions.

Changes to this package affect multiple components and should be treated as
contract changes.

## MQTT Topic Contract

The canonical topic list is implemented in `packages/shared/shared/topics.py`.

| Topic | Producer | Consumer | Purpose |
| --- | --- | --- | --- |
| `daas/drone/{drone_id}/register` | Simulator | Airspace Core | Drone registration |
| `daas/drone/{drone_id}/activation` | Airspace Core | Simulator, Dashboard | Mission activation |
| `daas/drone/{drone_id}/telemetry` | Simulator | Airspace Core, Dashboard | Live telemetry |
| `daas/drone/{drone_id}/advisory` | Airspace Core | Simulator | Conflict or zone advisory |
| `daas/drone/{drone_id}/control` | Control Gateway | Simulator | Manual control command |
| `daas/drone/spawn/request` | Airspace Core | Simulator | Spawn a dashboard-requested drone |
| `daas/manned/{aircraft_id}/position` | External/mocked publisher | Airspace Core, Dashboard | Manned aircraft position |
| `daas/airspace/event` | Airspace Core | Dashboard | Event feed |
| `daas/airspace/zones` | Airspace Core | Dashboard, Simulator | Active zone list |
| `daas/airspace/zones/command` | Dashboard | Airspace Core | Create/update/remove zone |
| `daas/airspace/missions/request` | Dashboard | Airspace Core | Request a new mission |

## Dashboard HTTP Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/` | `GET` | Serve the dashboard page |
| `/api/snapshot` | `GET` | Return current drones, manned aircraft, activations, events, and zones |
| `/api/stream` | `GET` | Server-Sent Events stream for live browser updates |
| `/api/zones` | `POST` | Publish a zone create/update command |
| `/api/zones/<zone_id>` | `DELETE` | Publish a zone removal command |
| `/api/mission-requests` | `POST` | Publish a mission request with pickup/dropoff points |

The dashboard backend publishes requests to MQTT. It does not decide whether a
mission or zone is operationally safe.

## Control Gateway Contract

| Endpoint | Method/protocol | Purpose |
| --- | --- | --- |
| `/` | `GET` | Return gateway status and configured ports |
| `/control/<drone_id>` | `POST` | Send manual control for one drone |
| `9090` | TCP | Optional newline-delimited JSON control input |

HTTP control payload:

```json
{
  "heading_delta": 8,
  "throttle_delta": 0.6,
  "speed_delta": 0.8
}
```

TCP control payload:

```json
{"drone_id":"drone-rpi-001","heading_delta":6,"throttle_delta":0.4,"speed_delta":0.5}
```

The default manual drone ID is `drone-rpi-001`.

## Runtime Configuration Contract

Important environment variables are defined in `packages/shared/shared/config.py`.

| Variable | Default | Used by |
| --- | --- | --- |
| `MQTT_BROKER_HOST` | `localhost` | Core, dashboard, simulator, gateway |
| `MQTT_BROKER_PORT` | `1883` | Core, dashboard, simulator, gateway |
| `DEFAULT_MANUAL_DRONE_ID` | `drone-rpi-001` | Simulator, gateway |
| `CONTROL_GATEWAY_HTTP_PORT` | `5002` | Gateway |
| `CONTROL_GATEWAY_TCP_PORT` | `9090` | Gateway |
| `DEFAULT_CRUISE_ALTITUDE_M` | `60` | Core, simulator, dashboard |
| `DEFAULT_CRUISE_SPEED_MS` | `25` | Simulator, dashboard |
| `TELEMETRY_INTERVAL_MS` | `200` | Simulator |

For the distributed deployment, components running outside Raspberry Pi 4B #1
must set `MQTT_BROKER_HOST=<PI1_IP>`.
