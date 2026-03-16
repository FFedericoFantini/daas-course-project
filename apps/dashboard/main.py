import json
import queue
import threading

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, render_template, request

from shared.config import DEFAULT_CRUISE_ALTITUDE_M, DEFAULT_CRUISE_SPEED_MS, MQTT_BROKER_HOST, MQTT_BROKER_PORT
from shared.schemas import MissionRequestMessage, Position, Zone, ZoneCommandMessage
from shared.topics import (
    AIRSPACE_EVENT,
    DRONE_ACTIVATION_ALL,
    DRONE_TELEMETRY_ALL,
    MISSION_REQUEST,
    MANNED_POSITION_ALL,
    ZONE_COMMAND,
    ZONE_UPDATE,
)

app = Flask(__name__, template_folder="templates", static_folder="static")

state_lock = threading.Lock()
latest_drones = {}
latest_manned = {}
activations = {}
events = []
zones = []
subscribers = []


def publish_stream(event_type: str, payload):
    dead = []
    for subscriber in subscribers:
        try:
            subscriber.put_nowait({"type": event_type, "payload": payload})
        except queue.Full:
            dead.append(subscriber)
    for subscriber in dead:
        if subscriber in subscribers:
            subscribers.remove(subscriber)


def on_connect(client, userdata, flags, reason_code, properties=None):
    client.subscribe(DRONE_TELEMETRY_ALL)
    client.subscribe(DRONE_ACTIVATION_ALL)
    client.subscribe(AIRSPACE_EVENT)
    client.subscribe(MANNED_POSITION_ALL)
    client.subscribe(ZONE_UPDATE)


def on_message(client, userdata, msg):
    topic = msg.topic
    parts = topic.split("/")
    payload = json.loads(msg.payload.decode("utf-8"))
    with state_lock:
        if parts[1] == "drone" and parts[3] == "telemetry":
            latest_drones[payload["drone_id"]] = payload
            event_type = "telemetry"
        elif parts[1] == "drone" and parts[3] == "activation":
            activations[payload["drone_id"]] = payload
            event_type = "activation"
        elif parts[1] == "manned":
            latest_manned[payload["drone_id"]] = payload
            event_type = "manned"
        elif topic == AIRSPACE_EVENT:
            events.insert(0, payload)
            del events[50:]
            event_type = "airspace_event"
        elif topic == ZONE_UPDATE:
            zones.clear()
            zones.extend(payload)
            event_type = "zones"
        else:
            return
    publish_stream(event_type, payload)


def create_mqtt_bridge():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="dashboard-backend")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    client.loop_start()
    return client


mqtt_client = create_mqtt_bridge()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/planner")
def planner():
    return render_template("planner.html")


@app.route("/api/snapshot")
def snapshot():
    with state_lock:
        return jsonify(
            {
                "drones": list(latest_drones.values()),
                "manned": list(latest_manned.values()),
                "activations": activations,
                "events": events,
                "zones": zones,
            }
        )


@app.route("/api/stream")
def stream():
    subscriber = queue.Queue(maxsize=200)
    subscribers.append(subscriber)

    def generate():
        yield "event: ready\ndata: {}\n\n"
        try:
            while True:
                message = subscriber.get()
                yield f"event: {message['type']}\ndata: {json.dumps(message['payload'])}\n\n"
        finally:
            if subscriber in subscribers:
                subscribers.remove(subscriber)

    return Response(generate(), mimetype="text/event-stream")


@app.post("/api/zones")
def upsert_zone():
    payload = request.get_json(force=True)
    center = payload.get("center", {})
    zone = Zone(
        zone_id=payload["zone_id"],
        name=payload["name"],
        center=Position(lat=float(center["lat"]), lon=float(center["lon"]), alt=float(center.get("alt", 0.0))),
        radius_m=float(payload["radius_m"]),
        min_alt_m=float(payload.get("min_alt_m", 0.0)),
        max_alt_m=float(payload.get("max_alt_m", 120.0)),
        restricted=bool(payload.get("restricted", True)),
    )
    command = ZoneCommandMessage(action="upsert", zone_id=zone.zone_id, zone=zone)
    mqtt_client.publish(ZONE_COMMAND, command.to_json())
    return jsonify({"ok": True, "action": "upsert", "zone_id": zone.zone_id})


@app.delete("/api/zones/<zone_id>")
def delete_zone(zone_id: str):
    command = ZoneCommandMessage(action="remove", zone_id=zone_id)
    mqtt_client.publish(ZONE_COMMAND, command.to_json())
    return jsonify({"ok": True, "action": "remove", "zone_id": zone_id})


@app.post("/api/mission-requests")
def create_mission_request():
    payload = request.get_json(force=True)
    pickup = payload.get("pickup", {})
    dropoff = payload.get("dropoff", {})
    mission = MissionRequestMessage(
        drone_id=payload["drone_id"],
        operator=payload.get("operator", "planner"),
        drone_type=payload.get("drone_type", "quadcopter"),
        pickup=Position(lat=float(pickup["lat"]), lon=float(pickup["lon"]), alt=float(pickup.get("alt", 0.0))),
        dropoff=Position(lat=float(dropoff["lat"]), lon=float(dropoff["lon"]), alt=float(dropoff.get("alt", 0.0))),
        cruise_altitude=float(payload.get("cruise_altitude", DEFAULT_CRUISE_ALTITUDE_M)),
        max_speed=float(payload.get("max_speed", DEFAULT_CRUISE_SPEED_MS)),
    )
    mqtt_client.publish(MISSION_REQUEST, mission.to_json())
    return jsonify({"ok": True, "drone_id": mission.drone_id, "action": "mission_request"})


def main():
    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()
