# Team Split

This split is designed so each teammate can work directly from the Spec V2 and this repository without needing extra project context.

## Member 1: Airspace Core

- registration lifecycle
- mission activation
- restricted zones
- priority rules
- conflict detection and advisories
- zone command handling

## Member 2: Drone Simulator

- drone state machines
- mission execution
- telemetry cadence
- advisory reaction
- manual drone support

## Member 3: Dashboard

- HTTP server
- SSE bridge
- frontend map and event log
- operator visibility for rules and advisories
- zone-management flow

## Member 4: Control Gateway

- SenseHAT integration
- mock/manual control
- command routing

## Shared Rules

- Do not change `packages/shared` without team agreement.
- Do not rename MQTT topics without team agreement.
- Do not move logic from one component into another component just to make one task easier.
- Keep each commit tied to one Spec V2 use case or one component responsibility.

## Shared Integration Milestones

1. Shared schema freeze
2. MQTT topic freeze
3. End-to-end registration and activation
4. End-to-end conflict and advisory flow
5. Restricted zone validation
6. Manual drone integration through control gateway
