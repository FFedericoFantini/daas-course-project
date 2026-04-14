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
const missionMarkers = {};
const zoneLayers = {};
let currentZones = [];
let draftZoneLayer = null;
let isPickingZone = false;
let eventCount = 0;
const MAX_PROJECTION_S = 0.35;

const zoneForm = document.getElementById("zone-form");
const zoneNameInput = document.getElementById("zone-name");
const zoneRadiusInput = document.getElementById("zone-radius");
const zoneMaxAltInput = document.getElementById("zone-max-alt");
const zoneLatInput = document.getElementById("zone-lat");
const zoneLonInput = document.getElementById("zone-lon");
const zonePickButton = document.getElementById("zone-pick");
const zoneStatus = document.getElementById("zone-status");
const zoneList = document.getElementById("zone-list");

function setStatus(isConnected) {
    const element = document.getElementById("live-status");
    element.textContent = isConnected ? "Live feed connected" : "Live feed disconnected";
    element.className = isConnected ? "ok" : "bad";
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatTime(timestamp) {
    if (!timestamp) {
        return "now";
    }
    return new Date(timestamp * 1000).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function droneIcon(state) {
    const color = state === "evading" ? "#d86c1e" : state === "airborne" ? "#188b68" : "#50635a";
    return L.divIcon({
        className: "drone-marker",
        html: `<div class="drone-dot" style="background:${color}"></div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20],
    });
}

function addEvent(event) {
    eventCount += 1;
    document.getElementById("event-count").textContent = `Events: ${eventCount}`;
    const log = document.getElementById("event-log");
    const item = document.createElement("div");
    const eventType = event.event_type || "event";
    item.className = `event-item ${eventType === "advisory" ? "advisory" : ""} ${eventType.includes("zone") ? "zone-event" : ""}`;
    item.innerHTML = `
        <div class="event-meta">
            <strong>${escapeHtml(event.entity_id || "airspace")}</strong>
            <span>${escapeHtml(eventType)} - ${formatTime(event.timestamp)}</span>
        </div>
        <div>${escapeHtml(event.details || "No details provided.")}</div>
    `;
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
        `<strong>${escapeHtml(tel.drone_id)}</strong><br>State: ${escapeHtml(tel.state)}<br>Alt: ${tel.position.alt.toFixed(0)}m<br>Hdg: ${tel.heading.toFixed(0)}&deg;`
    );
    droneTrails[tel.drone_id].addLatLng(latLng);
    const points = droneTrails[tel.drone_id].getLatLngs();
    if (points.length > 120) {
        droneTrails[tel.drone_id].setLatLngs(points.slice(-120));
    }
    document.getElementById("drone-count").textContent = `Drones: ${Object.keys(droneMarkers).length}`;
}

function updateActivation(activation) {
    if (!activation.route || activation.route.length === 0) {
        return;
    }
    const droneId = activation.drone_id;
    const start = activation.route[0];
    const destination = activation.route[activation.route.length - 1];

    if (missionMarkers[droneId]) {
        missionMarkers[droneId].pickup.setLatLng([start.lat, start.lon]);
        missionMarkers[droneId].dropoff.setLatLng([destination.lat, destination.lon]);
        missionMarkers[droneId].path.setLatLngs(
            activation.route.map((point) => [point.lat, point.lon])
        );
        return;
    }

    const pickup = L.circleMarker([start.lat, start.lon], {
        radius: 9,
        color: "#ffffff",
        weight: 2,
        fillColor: "#2563eb",
        fillOpacity: 0.95,
    })
        .bindTooltip(`${droneId} pickup`, { permanent: true, direction: "top", offset: [0, -8] })
        .addTo(map);
    const dropoff = L.circleMarker([destination.lat, destination.lon], {
        radius: 9,
        color: "#ffffff",
        weight: 2,
        fillColor: "#b45309",
        fillOpacity: 0.95,
    })
        .bindTooltip(`${droneId} drop`, { permanent: true, direction: "top", offset: [0, -8] })
        .addTo(map);
    const path = L.polyline(
        activation.route.map((point) => [point.lat, point.lon]),
        {
            color: "#6b7280",
            weight: 2,
            opacity: 0.55,
            dashArray: "8 6",
        }
    ).addTo(map);

    missionMarkers[droneId] = { pickup, dropoff, path };
}

function updateZones(zones) {
    zones = zones || [];
    currentZones = zones;
    Object.values(zoneLayers).forEach((layer) => layer.remove());
    Object.keys(zoneLayers).forEach((zoneId) => delete zoneLayers[zoneId]);
    zones.forEach((zone) => {
        const circle = L.circle([zone.center.lat, zone.center.lon], {
            radius: zone.radius_m,
            color: "#c0392b",
            fillColor: "#c0392b",
            fillOpacity: 0.18,
            weight: 2,
            dashArray: zone.restricted ? "" : "6 6",
        }).addTo(map);
        circle.bindTooltip(
            `<strong>${escapeHtml(zone.name)}</strong><br>${Math.round(zone.radius_m)}m radius<br>${Math.round(zone.min_alt_m)}-${Math.round(zone.max_alt_m)}m AGL`,
            { sticky: true }
        );
        zoneLayers[zone.zone_id] = circle;
    });
    renderZoneList();
}

function renderZoneList() {
    zoneList.innerHTML = "";
    if (!currentZones.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No active no-fly zones yet.";
        zoneList.appendChild(empty);
        return;
    }

    currentZones.forEach((zone) => {
        const item = document.createElement("article");
        item.className = "zone-item";
        item.innerHTML = `
            <div>
                <strong>${escapeHtml(zone.name)}</strong>
                <span>${Math.round(zone.radius_m)}m radius - ${Math.round(zone.min_alt_m)}-${Math.round(zone.max_alt_m)}m</span>
            </div>
            <button class="danger" type="button" data-zone-id="${escapeHtml(zone.zone_id)}">Remove</button>
        `;
        zoneList.appendChild(item);
    });
}

function setZoneStatus(message, ok = true) {
    zoneStatus.textContent = message;
    zoneStatus.className = `zone-status ${ok ? "ok" : "bad"}`;
}

function zonePayloadFromForm() {
    const lat = Number(zoneLatInput.value);
    const lon = Number(zoneLonInput.value);
    const radius = Number(zoneRadiusInput.value);
    const maxAlt = Number(zoneMaxAltInput.value);
    const name = zoneNameInput.value.trim();

    return {
        zone_id: `zone-${Date.now()}`,
        name,
        center: { lat, lon, alt: 0 },
        radius_m: radius,
        min_alt_m: 0,
        max_alt_m: maxAlt,
        restricted: true,
    };
}

function updateDraftZone() {
    if (!zoneLatInput.value || !zoneLonInput.value) {
        return;
    }

    const latLng = [Number(zoneLatInput.value), Number(zoneLonInput.value)];
    const radius = Number(zoneRadiusInput.value || 250);
    if (draftZoneLayer) {
        draftZoneLayer.setLatLng(latLng);
        draftZoneLayer.setRadius(radius);
        return;
    }

    draftZoneLayer = L.circle(latLng, {
        radius,
        color: "#7a1e18",
        fillColor: "#c0392b",
        fillOpacity: 0.10,
        weight: 2,
        dashArray: "5 6",
    }).addTo(map);
    draftZoneLayer.bindTooltip("Draft no-fly zone", { permanent: false, sticky: true });
}

function setDraftCenter(latlng) {
    zoneLatInput.value = latlng.lat.toFixed(6);
    zoneLonInput.value = latlng.lng.toFixed(6);
    updateDraftZone();
    isPickingZone = false;
    zonePickButton.classList.remove("active");
    setZoneStatus("Center selected. Adjust the radius if needed, then publish the zone.", true);
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
    });

    requestAnimationFrame(animateDrones);
}

async function bootstrap() {
    const response = await fetch("/api/snapshot");
    const snapshot = await response.json();
    snapshot.drones.forEach(updateDrone);
    Object.values(snapshot.activations || {}).forEach(updateActivation);
    snapshot.events.slice().reverse().forEach(addEvent);
    updateZones(snapshot.zones || []);

    const source = new EventSource("/api/stream");
    source.addEventListener("ready", () => setStatus(true));
    source.addEventListener("telemetry", (event) => updateDrone(JSON.parse(event.data)));
    source.addEventListener("activation", (event) => updateActivation(JSON.parse(event.data)));
    source.addEventListener("airspace_event", (event) => addEvent(JSON.parse(event.data)));
    source.addEventListener("zones", (event) => updateZones(JSON.parse(event.data)));
    source.onerror = () => setStatus(false);
}

map.on("click", (event) => {
    if (isPickingZone) {
        setDraftCenter(event.latlng);
    }
});

zonePickButton.addEventListener("click", () => {
    isPickingZone = !isPickingZone;
    zonePickButton.classList.toggle("active", isPickingZone);
    setZoneStatus(isPickingZone ? "Click the map to place the center of the no-fly zone." : "Zone picking cancelled.", true);
});

zoneRadiusInput.addEventListener("input", updateDraftZone);

zoneForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!zoneLatInput.value || !zoneLonInput.value) {
        setZoneStatus("Pick a center point on the map before publishing.", false);
        return;
    }

    const payload = zonePayloadFromForm();
    if (!payload.name || payload.radius_m <= 0 || payload.max_alt_m <= 0) {
        setZoneStatus("Zone name, radius, and max altitude must be valid.", false);
        return;
    }

    try {
        const response = await fetch("/api/zones", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
            throw new Error(result.error || "Zone publish failed");
        }
        setZoneStatus(`No-fly zone queued: ${payload.name}.`, true);
        if (draftZoneLayer) {
            draftZoneLayer.remove();
            draftZoneLayer = null;
        }
    } catch (error) {
        setZoneStatus(error.message || "Zone publish failed.", false);
    }
});

zoneList.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-zone-id]");
    if (!button) {
        return;
    }
    const zoneId = button.dataset.zoneId;
    try {
        const response = await fetch(`/api/zones/${encodeURIComponent(zoneId)}`, { method: "DELETE" });
        const result = await response.json();
        if (!response.ok || !result.ok) {
            throw new Error(result.error || "Zone removal failed");
        }
        setZoneStatus(`Removal queued for ${zoneId}.`, true);
    } catch (error) {
        setZoneStatus(error.message || "Zone removal failed.", false);
    }
});

setStatus(false);
requestAnimationFrame(animateDrones);
bootstrap().catch(() => setStatus(false));
