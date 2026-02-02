from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from ..core.config import ButlerConfig, load_config
from ..core.utils import new_uuid, utc_ts

logger = logging.getLogger(__name__)

MODE_OBSERVE = "OBSERVE"
MODE_MAP = "MAP"
RAW_TABLE = "raw_messages"
_PATH_TOKEN = re.compile(r"[^\.\[\]]+|\[\d+\]")


def _get_by_path(data: Any, path: str) -> Optional[Any]:
    if not path:
        return None
    current = data
    for token in _PATH_TOKEN.findall(path):
        if token.startswith("[") and token.endswith("]"):
            if not isinstance(current, list):
                return None
            try:
                index = int(token[1:-1])
            except ValueError:
                return None
            if index >= len(current):
                return None
            current = current[index]
        else:
            if not isinstance(current, dict) or token not in current:
                return None
            current = current[token]
    return current


def map_frigate_event(raw_event: Dict[str, Any], config: ButlerConfig) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for target_key, source_path in config.frigate_payload_map.items():
        value = _get_by_path(raw_event, str(source_path))
        if value is not None:
            payload[target_key] = value

    if config.frigate_passthrough_raw:
        payload["raw"] = raw_event

    severity = config.frigate_severity_default
    if config.frigate_severity_path:
        mapped_severity = _get_by_path(raw_event, config.frigate_severity_path)
        try:
            severity = int(mapped_severity)
        except (TypeError, ValueError):
            severity = config.frigate_severity_default

    return {
        "source": "frigate",
        "type": config.frigate_event_type,
        "payload": payload,
        "severity": severity,
        "ts": utc_ts(),
        "event_id": new_uuid(),
    }


class RawMessageStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {RAW_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def insert(self, topic: str, payload: str) -> None:
        if not self.conn:
            return
        self.conn.execute(
            f"INSERT INTO {RAW_TABLE} (ts, topic, payload) VALUES (?, ?, ?)",
            (utc_ts(), topic, payload),
        )
        self.conn.commit()


class FrigateAdapter:
    def __init__(self, config: ButlerConfig) -> None:
        self.config = config
        self.mode = (config.frigate_mode or MODE_OBSERVE).upper()
        if self.mode not in {MODE_OBSERVE, MODE_MAP}:
            logger.warning("Unknown FRIGATE_MODE %s; defaulting to OBSERVE", self.mode)
            self.mode = MODE_OBSERVE
        self.sub_topic = config.frigate_sub_topic or "frigate/#"
        self.publish_topic = (
            config.topic_in_event[0] if config.topic_in_event else "butler/in/event"
        )
        self.mapping_ready = bool(config.frigate_payload_map)
        self._mapping_warned = False
        self.client = mqtt.Client(client_id=f"butler-frigate-{new_uuid()}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.raw_store: Optional[RawMessageStore] = None
        if self.mode == MODE_OBSERVE or config.frigate_debug_raw:
            try:
                self.raw_store = RawMessageStore(config.db_path)
            except sqlite3.Error as exc:
                logger.error("Raw message DB init failed: %s", exc)

    def start(self) -> None:
        logger.info("Frigate adapter mode=%s sub_topic=%s", self.mode, self.sub_topic)
        self.client.reconnect_delay_set(
            min_delay=self.config.mqtt_reconnect_min_sec,
            max_delay=self.config.mqtt_reconnect_max_sec,
        )
        self.client.connect(
            self.config.mqtt_host,
            self.config.mqtt_port,
            keepalive=self.config.mqtt_keepalive_sec,
        )
        self.client.loop_start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Frigate adapter stopping")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
        if rc == 0:
            logger.info("Frigate adapter connected; subscribing to %s", self.sub_topic)
            client.subscribe([(self.sub_topic, 0)])
        else:
            logger.error("Frigate adapter MQTT connect failed: %s", rc)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        logger.warning("Frigate adapter disconnected: %s", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        raw_payload = msg.payload.decode("utf-8", errors="ignore")
        if self.mode == MODE_OBSERVE or self.config.frigate_debug_raw:
            self._store_raw(msg.topic, raw_payload)
            logger.info("Observed message on %s", msg.topic)

        if self.mode == MODE_OBSERVE:
            return

        if not self.mapping_ready:
            if not self._mapping_warned:
                logger.warning("FRIGATE_MODE=MAP but no payload mapping configured.")
                self._mapping_warned = True
            return

        try:
            raw_event = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from Frigate topic %s", msg.topic)
            return

        mapped = map_frigate_event(raw_event, self.config)
        client.publish(self.publish_topic, json.dumps(mapped), qos=0)

    def _store_raw(self, topic: str, payload: str) -> None:
        if self.raw_store:
            self.raw_store.insert(topic, payload)
            return
        self._append_raw_file(topic, payload)

    def _append_raw_file(self, topic: str, payload: str) -> None:
        path = self.config.frigate_raw_log_path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        entry = {"ts": utc_ts(), "topic": topic, "payload": payload}
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True))
            handle.write("\n")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config()
    adapter = FrigateAdapter(config)
    adapter.start()


if __name__ == "__main__":
    main()
