# Dashboard Demo Notes

Use this checklist when presenting the monitoring dashboard.

## Monitoring View

Open the dashboard at:

- `http://127.0.0.1:5001`

The dashboard should show:

- the live connection status
- active drone count
- total event count
- a mission request panel on the main dashboard
- drone markers with heading, altitude, and state tooltips
- green flight trails for recent drone movement
- red no-fly zone circles on the map
- the event panel with advisory and zone events highlighted

## Mission Request Flow

1. In the `Mission Request` panel, click `Pick on map`.
2. Click once for the pickup point and again for the dropoff point.
3. Fill in a unique drone ID and adjust the mission settings if needed.
4. Click `Request mission`.
5. Wait for the planner flow to publish the new mission request.
6. Confirm the mission overlay appears on the map and the new drone starts showing up once telemetry arrives.

## No-fly Zone Flow

1. In the `No-fly Zones` panel, click `Pick on map`.
2. Click the map where the restricted area should be centered.
3. Adjust the zone name, radius, and maximum altitude.
4. Click `Publish zone`.
5. Wait for the airspace core to publish the zone update.
6. Confirm the red zone appears on the map and in the active zone list.

To remove a zone, click `Remove` next to that zone in the list. The dashboard sends a removal command and updates after the airspace core publishes the new zone state.

## Demo Readability Tips

- Use a radius of `250m` to `500m` for a clear visual area at the default Trondheim zoom level.
- Keep the event panel visible while triggering conflict or zone scenarios.
- Hover over drones and zones during the demo to show the current state, altitude, radius, and altitude band.
- If the dashboard says the live feed is disconnected, restart the dashboard backend after confirming the MQTT broker is running.
