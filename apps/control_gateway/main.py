import json
import logging
import socket
import threading

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request

from shared.config import (
    CONTROL_GATEWAY_HTTP_PORT,
    CONTROL_GATEWAY_TCP_PORT,
    DEFAULT_MANUAL_DRONE_ID,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
)
from shared.schemas import ControlMessage
from shared.topics import DRONE_CONTROL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="control-gateway")
mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
mqtt_client.loop_start()


def publish_control(message: ControlMessage):
    mqtt_client.publish(DRONE_CONTROL.format(drone_id=message.drone_id), message.to_json())
    logger.info("Control published for %s", message.drone_id)


def start_tcp_gateway():
    def serve():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", CONTROL_GATEWAY_TCP_PORT))
        server.listen(5)
        logger.info("TCP control gateway listening on %s", CONTROL_GATEWAY_TCP_PORT)

        while True:
            connection, address = server.accept()
            logger.info("Raspberry Pi control client connected from %s", address)
            threading.Thread(target=handle_client, args=(connection, address), daemon=True).start()

    def handle_client(connection: socket.socket, address):
        buffer = ""
        try:
            while True:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    message = ControlMessage(
                        drone_id=payload.get("drone_id", DEFAULT_MANUAL_DRONE_ID),
                        heading_delta=float(payload.get("heading_delta", 0.0)),
                        throttle_delta=float(payload.get("throttle_delta", 0.0)),
                        speed_delta=float(payload.get("speed_delta", 0.0)),
                    )
                    publish_control(message)
        except (ConnectionError, OSError, json.JSONDecodeError) as exc:
            logger.warning("TCP control client %s closed with error: %s", address, exc)
        finally:
            connection.close()
            logger.info("Raspberry Pi control client disconnected from %s", address)

    threading.Thread(target=serve, daemon=True).start()


@app.get("/")
def index():
    return jsonify(
        {
            "ok": True,
            "manual_drone_id": DEFAULT_MANUAL_DRONE_ID,
            "http_port": CONTROL_GATEWAY_HTTP_PORT,
            "tcp_port": CONTROL_GATEWAY_TCP_PORT,
        }
    )


@app.post("/control/<drone_id>")
def send_control(drone_id: str):
    payload = request.get_json(force=True)
    message = ControlMessage(
        drone_id=drone_id,
        heading_delta=float(payload.get("heading_delta", 0.0)),
        throttle_delta=float(payload.get("throttle_delta", 0.0)),
        speed_delta=float(payload.get("speed_delta", 0.0)),
    )
    publish_control(message)
    return jsonify({"ok": True, "drone_id": drone_id})


def main():
    start_tcp_gateway()
    app.run(host="0.0.0.0", port=CONTROL_GATEWAY_HTTP_PORT, debug=False)


if __name__ == "__main__":
    main()
