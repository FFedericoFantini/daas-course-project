# Dashboard Demo Notes

Use this checklist when presenting the monitoring dashboard.

## Dashboard URL

For the three-device deployment, open the dashboard from the PC browser at:

```text
http://<PI1_IP>:5001
```

`<PI1_IP>` is the IP address of Raspberry Pi 4B #1, where the dashboard backend
is running.

For a local single-machine run, use:

```text
http://127.0.0.1:5001
```

## Monitoring View

The dashboard should show:

- Live connection status.
- Active drone count.
- Total event count.
- Mission request panel.
- No-fly-zone panel.
- Drone markers with heading, altitude, state, and mode tooltips.
- A distinctive marker for `drone-rpi-001`, the Raspberry Pi controlled drone.
- Recent flight trails.
- Active mission route, pickup point, and dropoff point.
- Red no-fly-zone circles on the map.
- Event panel with advisory and zone events highlighted.

## Startup Checks

Before opening the dashboard:

1. Raspberry Pi 4B #1 is running Mosquitto.
2. Raspberry Pi 4B #1 is running `apps.airspace_core.main`.
3. Raspberry Pi 4B #1 is running `apps.dashboard.main`.
4. Raspberry Pi 4B #1 is running `apps.control_gateway.main`.
5. The PC is running `apps.drone_simulator.main --drones 6 --manual-drone-id drone-rpi-001`.
6. The PC simulator has `MQTT_BROKER_HOST=<PI1_IP>`.

## Mission Request Flow

1. In the `Mission Request` panel, enter a unique drone ID.
2. Click `Pick on map`.
3. Click once for the pickup point.
4. Click once for the dropoff point.
5. Adjust cruise altitude and max speed if needed.
6. Click `Request mission`.
7. Confirm that the mission request appears in the event feed.
8. Confirm that the mission overlay appears when the requested drone starts
   publishing telemetry.

Expected behavior:

- The dashboard publishes the request to `daas/airspace/missions/request`.
- The Airspace Core validates the request.
- The Airspace Core publishes a simulator spawn request if the drone does not
  already exist.
- The simulator creates the requested drone session.
- The requested drone starts from the selected pickup point and lands at the
  selected dropoff point.
- Completed or aborted mission overlays are removed after the cleanup delay.

## No-Fly Zone Flow

1. In the `No-fly Zones` panel, click `Pick on map`.
2. Click the map where the restricted area should be centered.
3. Adjust the zone name, radius, and maximum altitude.
4. Click `Publish zone`.
5. Confirm that the Airspace Core publishes a zone event.
6. Confirm that the red zone appears on the map and in the active zone list.

To remove a zone, click `Remove` next to that zone in the list. The dashboard
sends a removal command, and the zone disappears after the Airspace Core
publishes the updated zone list.

## Manual Drone Flow

1. Start `manual-drone-controller.py` on Raspberry Pi 4B #2 with:

```bash
export CONTROL_URL="http://<PI1_IP>:5002/control"
export DRONE_ID="drone-rpi-001"
python apps/control_gateway/manual-drone-controller.py
```

2. Move the Sense HAT joystick.
3. Confirm that the LED matrix shows the direction arrow.
4. Confirm that `drone-rpi-001` changes heading, speed, or vertical movement on
   the dashboard.

## Demo Readability Tips

- Use a zone radius of `250m` to `500m` for a clear visual area at the default
  Trondheim zoom level.
- Keep the event panel visible while triggering conflict or zone scenarios.
- Hover over drones and zones to show state, altitude, radius, and altitude band.
- If the dashboard says the live feed is disconnected, restart the dashboard
  backend after confirming the MQTT broker is running.
- If no drones appear, verify that the simulator is connected to the Raspberry Pi
  broker through `MQTT_BROKER_HOST=<PI1_IP>`.
