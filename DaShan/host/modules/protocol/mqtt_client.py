from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


@dataclass
class MQTTClientConfig:
    broker_host: str = "localhost"
    broker_port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "dashan-host"
    
    topic_status: str = "daShan/status"
    topic_log: str = "daShan/log"
    topic_image: str = "daShan/image"
    topic_command: str = "daShan/command"
    
    status_interval: float = 5.0
    log_batch_size: int = 10
    log_flush_interval: float = 2.0
    max_log_queue: int = 100


@dataclass
class LogEntry:
    timestamp: float
    type: str
    level: str
    message: str
    context: Optional[Dict[str, Any]] = None


class DaShanMQTTClient:
    def __init__(self, config: MQTTClientConfig):
        self.config = config
        self.connected = False
        self.log_queue: List[LogEntry] = []
        self._stop_event = threading.Event()
        self._log_thread: Optional[threading.Thread] = None
        self._status_thread: Optional[threading.Thread] = None
        
        self._command_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        self.client = mqtt.Client(client_id=config.client_id)
        self._setup_client()
    
    def _setup_client(self):
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        if self.config.username and self.config.password:
            self.client.username_pw_set(
                self.config.username,
                self.config.password
            )
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"DaShan MQTT connected to broker")
            self.connected = True
            
            client.subscribe(self.config.topic_command)
            logger.info(f"Subscribed to command topic: {self.config.topic_command}")
            
            self._start_status_thread()
            self._start_log_thread()
        else:
            logger.error(f"DaShan MQTT connection failed: {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"DaShan MQTT disconnected: {rc}")
        self.connected = False
        self._stop_status_thread()
        self._stop_log_thread()
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            command = payload.get("command")
            params = payload.get("params", {})
            priority = payload.get("priority", "normal")
            
            logger.info(f"Received command: {command} (priority: {priority})")
            
            for callback in self._command_callbacks:
                try:
                    callback(command, params)
                except Exception as e:
                    logger.error(f"Command callback error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MQTT message: {e}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _start_status_thread(self):
        if self._status_thread and self._status_thread.is_alive():
            return
        
        self._status_thread = threading.Thread(
            target=self._status_loop,
            daemon=True
        )
        self._status_thread.start()
        logger.debug("Status thread started")
    
    def _stop_status_thread(self):
        if self._status_thread:
            self._stop_event.set()
            self._status_thread.join(timeout=2.0)
            self._stop_event.clear()
            logger.debug("Status thread stopped")
    
    def _start_log_thread(self):
        if self._log_thread and self._log_thread.is_alive():
            return
        
        self._log_thread = threading.Thread(
            target=self._log_loop,
            daemon=True
        )
        self._log_thread.start()
        logger.debug("Log thread started")
    
    def _stop_log_thread(self):
        if self._log_thread:
            self._stop_event.set()
            self._log_thread.join(timeout=2.0)
            self._stop_event.clear()
            logger.debug("Log thread stopped")
    
    def _status_loop(self):
        while self.connected and not self._stop_event.is_set():
            self._publish_status()
            time.sleep(self.config.status_interval)
    
    def _log_loop(self):
        while self.connected and not self._stop_event.is_set():
            self._flush_logs()
            time.sleep(self.config.log_flush_interval)
    
    def _publish_status(self, status: Optional[Dict[str, Any]] = None):
        if not self.connected:
            return
        
        payload = status or self._get_default_status()
        payload["timestamp"] = time.time()
        
        try:
            self.client.publish(
                self.config.topic_status,
                json.dumps(payload, ensure_ascii=False)
            )
        except Exception as e:
            logger.error(f"Failed to publish status: {e}")
    
    def _get_default_status(self) -> Dict[str, Any]:
        return {
            "state": "SLEEP",
            "expression": 0,
            "emotion": {
                "type": "neutral",
                "intensity": 0.0
            },
            "servo": {
                "horizontal": 90,
                "vertical": 90
            },
            "battery": 100,
            "proximity": False,
            "distance": 0.0,
            "light": 0
        }
    
    def _flush_logs(self):
        if not self.log_queue:
            return
        
        batch = self.log_queue[:self.config.log_batch_size]
        self.log_queue = self.log_queue[self.config.log_batch_size:]
        
        for entry in batch:
            try:
                payload = {
                    "timestamp": entry.timestamp,
                    "type": entry.type,
                    "level": entry.level,
                    "message": entry.message
                }
                
                if entry.context:
                    payload["context"] = entry.context
                
                self.client.publish(
                    self.config.topic_log,
                    json.dumps(payload, ensure_ascii=False)
                )
            except Exception as e:
                logger.error(f"Failed to publish log: {e}")
        
        logger.debug(f"Flushed {len(batch)} log entries")
    
    def connect(self) -> bool:
        try:
            self.client.connect(
                self.config.broker_host,
                self.config.broker_port,
                keepalive=60
            )
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        self.connected = False
        self._stop_event.set()
        
        self._stop_status_thread()
        self._stop_log_thread()
        
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("DaShan MQTT client disconnected")
    
    def update_state(self, state: str, expression: int = 0):
        self._publish_status({
            "state": state,
            "expression": expression
        })
    
    def update_expression(self, expression_id: int, brightness: int = 255):
        self._publish_status({
            "expression": expression_id
        })
    
    def update_emotion(self, emotion_type: str, intensity: float = 0.0, confidence: float = 0.0):
        self._publish_status({
            "emotion": {
                "type": emotion_type,
                "intensity": intensity,
                "confidence": confidence
            }
        })
    
    def update_servo(self, horizontal: int, vertical: int):
        self._publish_status({
            "servo": {
                "horizontal": horizontal,
                "vertical": vertical
            }
        })
    
    def update_sensors(self, proximity: bool, distance: float, light: int):
        self._publish_status({
            "proximity": proximity,
            "distance": distance,
            "light": light
        })
    
    def add_log(self, log_type: str, level: str, message: str, context: Optional[Dict[str, Any]] = None):
        entry = LogEntry(
            timestamp=time.time(),
            type=log_type,
            level=level,
            message=message,
            context=context
        )
        
        self.log_queue.append(entry)
        
        if len(self.log_queue) > self.config.max_log_queue:
            self.log_queue = self.log_queue[-self.config.max_log_queue:]
        
        logger.debug(f"Log queued: [{log_type}] {message}")
    
    def publish_image(self, image_base64: str, face_detected: bool = False, face_location: Optional[Dict[str, int]] = None):
        if not self.connected:
            return
        
        payload = {
            "timestamp": time.time(),
            "image": image_base64,
            "face_detected": face_detected
        }
        
        if face_location:
            payload["face_location"] = face_location
        
        try:
            self.client.publish(
                self.config.topic_image,
                json.dumps(payload, ensure_ascii=False)
            )
        except Exception as e:
            logger.error(f"Failed to publish image: {e}")
    
    def on_command(self, callback: Callable[[str, Dict[str, Any]], None]):
        self._command_callbacks.append(callback)
    
    def is_connected(self) -> bool:
        return self.connected
    
    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "log_queue_size": len(self.log_queue),
            "config": {
                "broker": f"{self.config.broker_host}:{self.config.broker_port}",
                "topics": {
                    "status": self.config.topic_status,
                    "log": self.config.topic_log,
                    "image": self.config.topic_image,
                    "command": self.config.topic_command
                }
            }
        }
