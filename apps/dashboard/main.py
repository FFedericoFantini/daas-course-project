import json
import queue
import threading

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, render_template

from shared.config import MQTT_BROKER_HOST, MQTT_BROKER_PORT
from shared.topics import (
    AIRSPACE_EVENT,
    DRONE_ACTIVATION_ALL,
    DRONE_TELEMETRY_ALL,
    MANNED_POSITION_ALL,
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


def main():
    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()
