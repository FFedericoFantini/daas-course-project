const plannerMap = L.map("planner-map", {
    center: [63.4305, 10.3951],
    zoom: 13,
});

L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
}).addTo(plannerMap);

const pickupFields = {
    lat: document.getElementById("pickup-lat"),
    lon: document.getElementById("pickup-lon"),
};
const dropoffFields = {
    lat: document.getElementById("dropoff-lat"),
    lon: document.getElementById("dropoff-lon"),
};
const statusElement = document.getElementById("status");
const form = document.getElementById("planner-form");

let pickupMarker = null;
let dropoffMarker = null;
let routeLine = null;
let selectionStage = "pickup";

function updateStatus(message, ok = true) {
    statusElement.textContent = message;
    statusElement.className = ok ? "ok" : "bad";
}

function setFieldPair(fields, latlng) {
    fields.lat.value = latlng.lat.toFixed(6);
    fields.lon.value = latlng.lng.toFixed(6);
}

function resetPlanner() {
    if (pickupMarker) {
        plannerMap.removeLayer(pickupMarker);
        pickupMarker = null;
    }
    if (dropoffMarker) {
        plannerMap.removeLayer(dropoffMarker);
        dropoffMarker = null;
    }
    if (routeLine) {
        plannerMap.removeLayer(routeLine);
        routeLine = null;
    }

    pickupFields.lat.value = "";
    pickupFields.lon.value = "";
    dropoffFields.lat.value = "";
    dropoffFields.lon.value = "";
    selectionStage = "pickup";
    updateStatus("Planner reset. Click the map to choose a new pickup point.", true);
}

plannerMap.on("click", (event) => {
    if (selectionStage === "pickup") {
        if (pickupMarker) {
            plannerMap.removeLayer(pickupMarker);
        }
        pickupMarker = L.marker(event.latlng).addTo(plannerMap).bindTooltip("Pickup", {
            permanent: true,
            direction: "top",
            offset: [0, -8],
        });
        setFieldPair(pickupFields, event.latlng);
        selectionStage = "dropoff";
        updateStatus("Pickup point set. Click again to choose the delivery point.", true);
        return;
    }

    if (dropoffMarker) {
        plannerMap.removeLayer(dropoffMarker);
    }
    dropoffMarker = L.marker(event.latlng).addTo(plannerMap).bindTooltip("Dropoff", {
        permanent: true,
        direction: "top",
        offset: [0, -8],
    });
    setFieldPair(dropoffFields, event.latlng);

    if (routeLine) {
        plannerMap.removeLayer(routeLine);
    }
    routeLine = L.polyline(
        [pickupMarker.getLatLng(), event.latlng],
        { color: "#1b7f5a", weight: 3, opacity: 0.85, dashArray: "8 6" }
    ).addTo(plannerMap);

    selectionStage = "done";
    updateStatus("Pickup and dropoff selected. You can now submit the mission request.", true);
});

document.getElementById("reset-points").addEventListener("click", resetPlanner);

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!pickupFields.lat.value || !dropoffFields.lat.value) {
        updateStatus("Choose both pickup and dropoff points on the map before submitting.", false);
        return;
    }

    const payload = {
        drone_id: document.getElementById("drone-id").value.trim(),
        operator: document.getElementById("operator").value.trim() || "planner",
        drone_type: document.getElementById("drone-type").value.trim() || "quadcopter",
        cruise_altitude: Number(document.getElementById("cruise-altitude").value || 60),
        max_speed: Number(document.getElementById("max-speed").value || 25),
        pickup: {
            lat: Number(pickupFields.lat.value),
            lon: Number(pickupFields.lon.value),
            alt: 0,
        },
        dropoff: {
            lat: Number(dropoffFields.lat.value),
            lon: Number(dropoffFields.lon.value),
            alt: 0,
        },
    };

    try {
        const response = await fetch("/api/mission-requests", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
            throw new Error(result.error || "Mission request failed");
        }
        updateStatus(`Mission request queued for ${result.drone_id}. Open the monitoring dashboard to watch it appear.`, true);
        form.reset();
        resetPlanner();
    } catch (error) {
        updateStatus(error.message || "Mission request failed", false);
    }
});

updateStatus("Click the map to place the pickup point.", true);
