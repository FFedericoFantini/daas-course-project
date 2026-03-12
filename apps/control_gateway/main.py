import logging

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request

from shared.config import MQTT_BROKER_HOST, MQTT_BROKER_PORT
from shared.schemas import ControlMessage
from shared.topics import DRONE_CONTROL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="control-gateway")
mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
mqtt_client.loop_start()


@app.post("/control/<drone_id>")
def send_control(drone_id: str):
    payload = request.get_json(force=True)
    message = ControlMessage(
        drone_id=drone_id,
        heading_delta=float(payload.get("heading_delta", 0.0)),
        throttle_delta=float(payload.get("throttle_delta", 0.0)),
    )
    mqtt_client.publish(DRONE_CONTROL.format(drone_id=drone_id), message.to_json())
    logger.info("Control published for %s", drone_id)
    return jsonify({"ok": True, "drone_id": drone_id})


def main():
    app.run(host="0.0.0.0", port=5002, debug=False)


if __name__ == "__main__":
    main()
