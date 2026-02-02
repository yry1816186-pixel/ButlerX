import json
import logging
import os
import time

import paho.mqtt.client as mqtt

from ..core.config import load_config

logger = logging.getLogger(__name__)


def build_event(event_type: str, payload: dict, severity: int) -> dict:
    return {
        "source": "sim",
        "type": event_type,
        "payload": payload,
        "severity": severity,
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config()
    host = config.mqtt_host
    port = config.mqtt_port
    topic_in_event = config.topic_in_event[0] if config.topic_in_event else "butler/in/event"
    interval = int(os.getenv("SIM_INTERVAL_SEC", "30"))
    once = os.getenv("SIM_ONCE", "0") == "1"

    events = [
        build_event(
            "zone_person_detected",
            {"zone": config.arrival_zone, "camera": config.entry_camera_default},
            1,
        ),
        build_event(
            "find_object_request",
            {"object": "keys", "cameras": config.find_keys_cameras},
            1,
        ),
        build_event(
            "intrusion",
            {
                "person": config.intrusion_unknown_person_value,
                "mode": config.intrusion_mode_required,
                "camera": config.intrusion_camera_default,
            },
            3,
        ),
        build_event(
            "patrol_request",
            {"mode": "start", "presets": config.patrol_presets},
            1,
        ),
    ]

    client = mqtt.Client(client_id="butler-simulator")
    client.connect(host, port, keepalive=config.mqtt_keepalive_sec)
    client.loop_start()

    index = 0
    while True:
        event = events[index % len(events)]
        client.publish(topic_in_event, json.dumps(event), qos=0)
        logger.info("Simulator event published: %s", event["type"])
        index += 1
        if once:
            break
        time.sleep(interval)

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
