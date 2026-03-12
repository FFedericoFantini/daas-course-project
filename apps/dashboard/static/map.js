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
const droneTelemetry = {};
const zoneLayers = {};
let eventCount = 0;
const MAX_PROJECTION_S = 0.35;

function setStatus(isConnected) {
    const element = document.getElementById("live-status");
    element.textContent = isConnected ? "Live feed connected" : "Live feed disconnected";
    element.className = isConnected ? "ok" : "bad";
}

function droneIcon(state) {
    const color = state === "evading" ? "#d86c1e" : state === "airborne" ? "#188b68" : "#50635a";
    const glow = state === "evading" ? "rgba(216,108,30,0.30)" : "rgba(24,139,104,0.24)";
    return L.divIcon({
        className: "drone-marker",
        html: `
            <div class="drone-shell">
                <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
                    <circle cx="15" cy="15" r="11" fill="${glow}" />
                    <g class="drone-rotor">
                        <path d="M15 3 L22 23 L15 19 L8 23 Z" fill="${color}" stroke="#ffffff" stroke-width="1.1" stroke-linejoin="round" />
                        <circle cx="15" cy="15" r="3.6" fill="#ffffff" opacity="0.95" />
                        <circle cx="15" cy="15" r="1.8" fill="${color}" />
                    </g>
                </svg>
            </div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
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
    droneTelemetry[tel.drone_id] = tel;

    if (!droneMarkers[tel.drone_id]) {
        droneMarkers[tel.drone_id] = L.marker(latLng, { icon: droneIcon(tel.state) }).addTo(map);
        droneTrails[tel.drone_id] = L.polyline([], {
            color: "#188b68",
            weight: 3,
            opacity: 0.32,
            lineCap: "round",
            lineJoin: "round",
        }).addTo(map);
    }

    droneMarkers[tel.drone_id].setIcon(droneIcon(tel.state));
    droneMarkers[tel.drone_id].bindTooltip(
        `<strong>${tel.drone_id}</strong><br>State: ${tel.state}<br>Alt: ${tel.position.alt.toFixed(0)}m<br>Hdg: ${tel.heading.toFixed(0)}&deg;`
    );
    droneTrails[tel.drone_id].addLatLng(latLng);
    const points = droneTrails[tel.drone_id].getLatLngs();
    if (points.length > 120) {
        droneTrails[tel.drone_id].setLatLngs(points.slice(-120));
    }
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

function projectTelemetryPosition(tel) {
    const nowS = Date.now() / 1000;
    const dt = Math.max(0, Math.min(MAX_PROJECTION_S, nowS - tel.timestamp));
    const headingRad = (tel.heading * Math.PI) / 180;
    const north = Math.cos(headingRad) * tel.speed * dt;
    const east = Math.sin(headingRad) * tel.speed * dt;
    const metersPerDegLat = 111320;
    const lat = tel.position.lat + (north / metersPerDegLat);
    const metersPerDegLon = metersPerDegLat * Math.cos((tel.position.lat * Math.PI) / 180);
    const lon = tel.position.lon + (east / Math.max(1e-6, metersPerDegLon));
    return [lat, lon];
}

function animateDrones() {
    Object.entries(droneTelemetry).forEach(([droneId, tel]) => {
        const marker = droneMarkers[droneId];
        if (!marker) {
            return;
        }
        marker.setLatLng(projectTelemetryPosition(tel));
        const element = marker.getElement();
        if (element) {
            const rotor = element.querySelector(".drone-rotor");
            if (rotor) {
                rotor.style.transformOrigin = "15px 15px";
                rotor.style.transform = `rotate(${tel.heading}deg)`;
            }
        }
    });

    requestAnimationFrame(animateDrones);
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
requestAnimationFrame(animateDrones);
bootstrap().catch(() => setStatus(false));
