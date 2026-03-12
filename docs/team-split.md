# Team Split

## Member 1: Airspace Core

- registration lifecycle
- mission activation
- restricted zones
- priority rules
- conflict detection and advisories

## Member 2: Drone Simulator

- drone state machines
- mission execution
- telemetry cadence
- advisory reaction

## Member 3: Dashboard

- HTTP server
- SSE bridge
- frontend map and event log
- operator visibility for rules and advisories

## Member 4: Control Gateway

- SenseHAT integration
- mock/manual control
- command routing

## Shared Integration Milestones

1. Shared schema freeze
2. MQTT topic freeze
3. End-to-end registration and activation
4. End-to-end conflict and advisory flow
5. Restricted zone validation
