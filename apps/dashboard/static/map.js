const map = L.map("map", {
    center: [63.4305, 10.3951],
    zoom: 13,
});

L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
}).addTo(map);

const droneMarkers = {};
const droneTrails = {};
const zoneLayers = {};
let eventCount = 0;

function setStatus(isConnected) {
    const element = document.getElementById("live-status");
    element.textContent = isConnected ? "Live feed connected" : "Live feed disconnected";
    element.className = isConnected ? "ok" : "bad";
}

function droneIcon(state) {
    const color = state === "evading" ? "#d86c1e" : state === "airborne" ? "#188b68" : "#50635a";
    return L.divIcon({
        className: "",
        html: `<svg width="22" height="22" viewBox="0 0 22 22"><circle cx="11" cy="11" r="8" fill="${color}" /></svg>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
    });
}

function addEvent(event) {
    eventCount += 1;
    document.getElementById("event-count").textContent = `Events: ${eventCount}`;
    const log = document.getElementById("event-log");
    const item = document.createElement("div");
    item.className = `event-item ${event.event_type === "advisory" ? "advisory" : ""}`;
    item.innerHTML = `<strong>${event.entity_id}</strong><div>${event.details}</div>`;
    log.prepend(item);
    while (log.children.length > 50) {
        log.removeChild(log.lastChild);
    }
}

function updateDrone(tel) {
    const latLng = [tel.position.lat, tel.position.lon];
    if (!droneMarkers[tel.drone_id]) {
        droneMarkers[tel.drone_id] = L.marker(latLng, { icon: droneIcon(tel.state) }).addTo(map);
        droneTrails[tel.drone_id] = L.polyline([], { color: "#188b68", weight: 2, opacity: 0.45 }).addTo(map);
    }
    droneMarkers[tel.drone_id].setLatLng(latLng);
    droneMarkers[tel.drone_id].setIcon(droneIcon(tel.state));
    droneMarkers[tel.drone_id].bindTooltip(
        `<strong>${tel.drone_id}</strong><br>State: ${tel.state}<br>Alt: ${tel.position.alt.toFixed(0)}m`
    );
    droneTrails[tel.drone_id].addLatLng(latLng);
    document.getElementById("drone-count").textContent = `Drones: ${Object.keys(droneMarkers).length}`;
}

function updateZones(zones) {
    Object.values(zoneLayers).forEach((layer) => layer.remove());
    zones.forEach((zone) => {
        const circle = L.circle([zone.center.lat, zone.center.lon], {
            radius: zone.radius_m,
            color: "#c0392b",
            fillColor: "#c0392b",
            fillOpacity: 0.12,
        }).addTo(map);
        circle.bindTooltip(`${zone.name}`);
        zoneLayers[zone.zone_id] = circle;
    });
}

async function bootstrap() {
    const response = await fetch("/api/snapshot");
    const snapshot = await response.json();
    snapshot.drones.forEach(updateDrone);
    snapshot.events.slice().reverse().forEach(addEvent);
    updateZones(snapshot.zones || []);

    const source = new EventSource("/api/stream");
    source.addEventListener("ready", () => setStatus(true));
    source.addEventListener("telemetry", (event) => updateDrone(JSON.parse(event.data)));
    source.addEventListener("airspace_event", (event) => addEvent(JSON.parse(event.data)));
    source.addEventListener("zones", (event) => updateZones(JSON.parse(event.data)));
    source.onerror = () => setStatus(false);
}

setStatus(false);
bootstrap().catch(() => setStatus(false));
