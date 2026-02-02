from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


@dataclass
class DaShanConfig:
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    client_id: str = "butler-dashan-adapter"
    
    topic_status: str = "daShan/status"
    topic_log: str = "daShan/log"
    topic_command: str = "daShan/command"
    topic_image: str = "daShan/image"
    
    status_update_interval: float = 5.0
    max_log_queue_size: int = 100
    log_batch_size: int = 10


@dataclass
class DaShanState:
    state: str = "SLEEP"
    expression_id: int = 0
    expression_name: str = "SLEEP"
    emotion_type: str = "neutral"
    emotion_intensity: float = 0.0
    servo_horizontal: int = 90
    servo_vertical: int = 90
    battery: int = 100
    proximity: bool = False
    distance: float = 0.0
    light: int = 0
    last_update: float = 0.0


@dataclass
class DaShanLogEntry:
    timestamp: float
    type: str
    level: str
    message: str
    context: Optional[Dict[str, Any]] = None


class DaShanAdapter:
    def __init__(self, config: DaShanConfig):
        self.config = config
        self.current_state = DaShanState()
        self.log_queue: List[DaShanLogEntry] = []
        self.last_status_update = 0.0
        self.connected = False
        
        self._status_callbacks: List[Callable[[DaShanState], None]] = []
        self._log_callbacks: List[Callable[[DaShanLogEntry], None]] = []
        self._image_callbacks: List[Callable[[str], None]] = []
        
        self.client = mqtt.Client(client_id=config.client_id)
        self._setup_client()
    
    def _setup_client(self):
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        if self.config.mqtt_username and self.config.mqtt_password:
            self.client.username_pw_set(
                self.config.mqtt_username,
                self.config.mqtt_password
            )
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"DaShan adapter connected to MQTT broker")
            self.connected = True
            
            client.subscribe(self.config.topic_status)
            client.subscribe(self.config.topic_log)
            client.subscribe(self.config.topic_image)
            
            logger.info(f"Subscribed to: {self.config.topic_status}, {self.config.topic_log}, {self.config.topic_image}")
        else:
            logger.error(f"DaShan adapter failed to connect: {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"DaShan adapter disconnected: {rc}")
        self.connected = False
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            if msg.topic == self.config.topic_status:
                self._handle_status_update(payload)
            elif msg.topic == self.config.topic_log:
                self._handle_log_entry(payload)
            elif msg.topic == self.config.topic_image:
                self._handle_image_data(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MQTT message: {e}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _handle_status_update(self, payload: Dict[str, Any]):
        self.current_state = DaShanState(
            state=payload.get("state", "SLEEP"),
            expression_id=payload.get("expression", 0),
            expression_name=self._get_expression_name(payload.get("expression", 0)),
            emotion_type=payload.get("emotion", {}).get("type", "neutral"),
            emotion_intensity=payload.get("emotion", {}).get("intensity", 0.0),
            servo_horizontal=payload.get("servo", {}).get("horizontal", 90),
            servo_vertical=payload.get("servo", {}).get("vertical", 90),
            battery=payload.get("battery", 100),
            proximity=payload.get("proximity", False),
            distance=payload.get("distance", 0.0),
            light=payload.get("light", 0),
            last_update=time.time()
        )
        
        logger.debug(f"DaShan state updated: {self.current_state.state}")
        
        for callback in self._status_callbacks:
            try:
                callback(self.current_state)
            except Exception as e:
                logger.error(f"Status callback error: {e}")
    
    def _handle_log_entry(self, payload: Dict[str, Any]):
        entry = DaShanLogEntry(
            timestamp=payload.get("timestamp", time.time()),
            type=payload.get("type", "unknown"),
            level=payload.get("level", "INFO"),
            message=payload.get("message", ""),
            context=payload.get("context")
        )
        
        self.log_queue.append(entry)
        
        if len(self.log_queue) > self.config.max_log_queue_size:
            self.log_queue = self.log_queue[-self.config.max_log_queue_size:]
        
        logger.debug(f"DaShan log: [{entry.type}] {entry.message}")
        
        for callback in self._log_callbacks:
            try:
                callback(entry)
            except Exception as e:
                logger.error(f"Log callback error: {e}")
    
    def _handle_image_data(self, payload: Dict[str, Any]):
        image_data = payload.get("image", "")
        face_detected = payload.get("face_detected", False)
        
        logger.debug(f"DaShan image received: face_detected={face_detected}")
        
        for callback in self._image_callbacks:
            try:
                callback(image_data)
            except Exception as e:
                logger.error(f"Image callback error: {e}")
    
    def _get_expression_name(self, expression_id: int) -> str:
        expressions = {
            0: "SLEEP",
            1: "WAKE",
            2: "LISTEN",
            3: "THINK",
            4: "TALK",
            5: "HAPPY",
            6: "SAD",
            7: "ANGRY",
            8: "SURPRISED",
            9: "SHY",
            10: "CURIOUS",
        }
        return expressions.get(expression_id, f"UNKNOWN({expression_id})")
    
    def connect(self) -> bool:
        try:
            self.client.connect(
                self.config.mqtt_host,
                self.config.mqtt_port,
                keepalive=60
            )
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            return False
    
    def disconnect(self):
        self.connected = False
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("DaShan adapter disconnected")
    
    def send_command(self, command: str, params: Dict[str, Any], priority: str = "normal") -> bool:
        if not self.connected:
            logger.warning("DaShan not connected, cannot send command")
            return False
        
        payload = {
            "command": command,
            "params": params,
            "priority": priority,
            "timestamp": time.time()
        }
        
        try:
            self.client.publish(
                self.config.topic_command,
                json.dumps(payload, ensure_ascii=False)
            )
            logger.info(f"DaShan command sent: {command}")
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False
    
    def set_expression(self, expression_id: int, brightness: int = 255) -> bool:
        return self.send_command("set_expression", {
            "expression_id": expression_id,
            "brightness": brightness
        })
    
    def set_servo(self, horizontal: int, vertical: int) -> bool:
        return self.send_command("set_servo", {
            "servo_h": horizontal,
            "servo_v": vertical
        })
    
    def play_animation(self, animation_name: str) -> bool:
        return self.send_command("play_animation", {
            "animation": animation_name
        })
    
    def speak(self, text: str) -> bool:
        return self.send_command("speak", {
            "text": text
        })
    
    def set_state(self, state: str) -> bool:
        return self.send_command("set_state", {
            "state": state
        })
    
    def on_status_update(self, callback: Callable[[DaShanState], None]):
        self._status_callbacks.append(callback)
    
    def on_log_entry(self, callback: Callable[[DaShanLogEntry], None]):
        self._log_callbacks.append(callback)
    
    def on_image_data(self, callback: Callable[[str], None]):
        self._image_callbacks.append(callback)
    
    def get_current_state(self) -> DaShanState:
        return self.current_state
    
    def get_recent_logs(self, limit: int = 50) -> List[DaShanLogEntry]:
        return self.log_queue[-limit:]
    
    def get_logs_by_type(self, log_type: str, limit: int = 50) -> List[DaShanLogEntry]:
        filtered = [log for log in self.log_queue if log.type == log_type]
        return filtered[-limit:]
    
    def get_logs_by_level(self, level: str, limit: int = 50) -> List[DaShanLogEntry]:
        filtered = [log for log in self.log_queue if log.level == level]
        return filtered[-limit:]
    
    def clear_logs(self):
        self.log_queue.clear()
        logger.info("DaShan log queue cleared")
    
    def get_state_summary(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "state": self.current_state.state,
            "expression": self.current_state.expression_name,
            "emotion": self.current_state.emotion_type,
            "servo": {
                "horizontal": self.current_state.servo_horizontal,
                "vertical": self.current_state.servo_vertical
            },
            "battery": self.current_state.battery,
            "proximity": self.current_state.proximity,
            "distance": self.current_state.distance,
            "light": self.current_state.light,
            "last_update": self.current_state.last_update,
            "log_count": len(self.log_queue)
        }
