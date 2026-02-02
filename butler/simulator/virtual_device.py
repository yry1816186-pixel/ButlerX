from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class VirtualDeviceType(Enum):
    LIGHT = "light"
    SWITCH = "switch"
    SENSOR = "sensor"
    CLIMATE = "climate"
    CAMERA = "camera"
    LOCK = "lock"
    COVER = "cover"
    MEDIA_PLAYER = "media_player"
    OTHER = "other"


@dataclass
class VirtualDevice:
    device_id: str
    name: str
    device_type: VirtualDeviceType
    state: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    is_available: bool = True
    event_callback: Optional[Callable] = None
    created_at: float = field(default_factory=time.time)

    def set_state(self, key: str, value: Any) -> None:
        old_value = self.state.get(key)
        self.state[key] = value
        logger.debug(f"{self.name}: {key} changed from {old_value} to {value}")

        if self.event_callback:
            self.event_callback({
                "device_id": self.device_id,
                "event_type": "state_change",
                "key": key,
                "old_value": old_value,
                "new_value": value,
                "timestamp": time.time(),
            })

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def update_state(self, states: Dict[str, Any]) -> None:
        for key, value in states.items():
            self.set_state(key, value)

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "device_id": self.device_id,
            "command": command,
            "params": params,
            "timestamp": time.time(),
        }

        if not self.is_available:
            result["message"] = f"设备 {self.name} 不可用"
            return result

        try:
            if self.device_type == VirtualDeviceType.LIGHT:
                result = self._handle_light_command(command, params)
            elif self.device_type == VirtualDeviceType.SWITCH:
                result = self._handle_switch_command(command, params)
            elif self.device_type == VirtualDeviceType.SENSOR:
                result = self._handle_sensor_command(command, params)
            elif self.device_type == VirtualDeviceType.CLIMATE:
                result = self._handle_climate_command(command, params)
            elif self.device_type == VirtualDeviceType.CAMERA:
                result = self._handle_camera_command(command, params)
            elif self.device_type == VirtualDeviceType.LOCK:
                result = self._handle_lock_command(command, params)
            elif self.device_type == VirtualDeviceType.COVER:
                result = self._handle_cover_command(command, params)
            elif self.device_type == VirtualDeviceType.MEDIA_PLAYER:
                result = self._handle_media_player_command(command, params)
            else:
                result["message"] = f"不支持的设备类型: {self.device_type}"

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            result["message"] = f"命令执行失败: {str(e)}"

        return result

    def _handle_light_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if command == "turn_on":
            self.set_state("state", "on")
            if "brightness" in params:
                self.set_state("brightness", params["brightness"])
            if "color" in params:
                self.set_state("color", params["color"])
            return {
                "success": True,
                "message": f"已打开 {self.name}",
                "state": self.state,
            }
        elif command == "turn_off":
            self.set_state("state", "off")
            return {
                "success": True,
                "message": f"已关闭 {self.name}",
                "state": self.state,
            }
        elif command == "set_brightness":
            brightness = params.get("value", 100)
            self.set_state("brightness", brightness)
            self.set_state("state", "on")
            return {
                "success": True,
                "message": f"已设置 {self.name} 亮度为 {brightness}%",
                "state": self.state,
            }
        elif command == "set_color_temp":
            color_temp = params.get("value", 3000)
            self.set_state("color_temp", color_temp)
            return {
                "success": True,
                "message": f"已设置 {self.name} 色温为 {color_temp}K",
                "state": self.state,
            }

        return {
            "success": False,
            "message": f"不支持的灯光命令: {command}",
        }

    def _handle_switch_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if command == "turn_on":
            self.set_state("state", "on")
            return {
                "success": True,
                "message": f"已打开 {self.name}",
                "state": self.state,
            }
        elif command == "turn_off":
            self.set_state("state", "off")
            return {
                "success": True,
                "message": f"已关闭 {self.name}",
                "state": self.state,
            }

        return {
            "success": False,
            "message": f"不支持的开关命令: {command}",
        }

    def _handle_sensor_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if command == "read":
            return {
                "success": True,
                "message": f"读取 {self.name} 传感器数据",
                "state": self.state,
            }
        elif command == "simulate_value":
            value = params.get("value")
            self.set_state("value", value)
            return {
                "success": True,
                "message": f"已模拟 {self.name} 值为 {value}",
                "state": self.state,
            }

        return {
            "success": False,
            "message": f"不支持的传感器命令: {command}",
        }

    def _handle_climate_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if command == "turn_on":
            self.set_state("state", "on")
            return {
                "success": True,
                "message": f"已打开 {self.name}",
                "state": self.state,
            }
        elif command == "turn_off":
            self.set_state("state", "off")
            return {
                "success": True,
                "message": f"已关闭 {self.name}",
                "state": self.state,
            }
        elif command == "set_temperature":
            temp = params.get("value", 24)
            self.set_state("temperature", temp)
            self.set_state("state", "on")
            return {
                "success": True,
                "message": f"已设置 {self.name} 温度为 {temp}℃",
                "state": self.state,
            }
        elif command == "set_mode":
            mode = params.get("mode", "auto")
            self.set_state("mode", mode)
            return {
                "success": True,
                "message": f"已设置 {self.name} 模式为 {mode}",
                "state": self.state,
            }

        return {
            "success": False,
            "message": f"不支持的空调命令: {command}",
        }

    def _handle_camera_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if command == "start_recording":
            self.set_state("recording", True)
            return {
                "success": True,
                "message": f"已开始录制 {self.name}",
                "state": self.state,
            }
        elif command == "stop_recording":
            self.set_state("recording", False)
            return {
                "success": True,
                "message": f"已停止录制 {self.name}",
                "state": self.state,
            }
        elif command == "capture_image":
            return {
                "success": True,
                "message": f"已捕获 {self.name} 图像",
                "state": self.state,
            }

        return {
            "success": False,
            "message": f"不支持的摄像头命令: {command}",
        }

    def _handle_lock_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if command == "lock":
            self.set_state("state", "locked")
            return {
                "success": True,
                "message": f"已锁定 {self.name}",
                "state": self.state,
            }
        elif command == "unlock":
            self.set_state("state", "unlocked")
            return {
                "success": True,
                "message": f"已解锁 {self.name}",
                "state": self.state,
            }

        return {
            "success": False,
            "message": f"不支持的门锁命令: {command}",
        }

    def _handle_cover_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if command == "open":
            self.set_state("state", "open")
            self.set_state("position", 100)
            return {
                "success": True,
                "message": f"已打开 {self.name}",
                "state": self.state,
            }
        elif command == "close":
            self.set_state("state", "closed")
            self.set_state("position", 0)
            return {
                "success": True,
                "message": f"已关闭 {self.name}",
                "state": self.state,
            }
        elif command == "set_position":
            position = params.get("value", 50)
            self.set_state("position", position)
            state = "open" if position > 0 else "closed"
            self.set_state("state", state)
            return {
                "success": True,
                "message": f"已设置 {self.name} 位置为 {position}%",
                "state": self.state,
            }

        return {
            "success": False,
            "message": f"不支持的窗帘命令: {command}",
        }

    def _handle_media_player_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if command == "turn_on":
            self.set_state("state", "on")
            return {
                "success": True,
                "message": f"已打开 {self.name}",
                "state": self.state,
            }
        elif command == "turn_off":
            self.set_state("state", "off")
            return {
                "success": True,
                "message": f"已关闭 {self.name}",
                "state": self.state,
            }
        elif command == "play":
            self.set_state("state", "playing")
            return {
                "success": True,
                "message": f"已播放 {self.name}",
                "state": self.state,
            }
        elif command == "pause":
            self.set_state("state", "paused")
            return {
                "success": True,
                "message": f"已暂停 {self.name}",
                "state": self.state,
            }
        elif command == "set_volume":
            volume = params.get("value", 50)
            self.set_state("volume", volume)
            return {
                "success": True,
                "message": f"已设置 {self.name} 音量为 {volume}",
                "state": self.state,
            }

        return {
            "success": False,
            "message": f"不支持的媒体播放器命令: {command}",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "state": self.state,
            "attributes": self.attributes,
            "capabilities": self.capabilities,
            "is_available": self.is_available,
            "created_at": self.created_at,
        }


class VirtualDeviceManager:
    def __init__(self) -> None:
        self.devices: Dict[str, VirtualDevice] = {}
        self._init_default_devices()

    def _init_default_devices(self) -> None:
        default_devices = [
            VirtualDevice(
                device_id="living_room_light",
                name="客厅灯",
                device_type=VirtualDeviceType.LIGHT,
                state={"state": "off", "brightness": 100, "color_temp": 4000},
                capabilities=["turn_on", "turn_off", "set_brightness", "set_color_temp"],
            ),
            VirtualDevice(
                device_id="bedroom_light",
                name="卧室灯",
                device_type=VirtualDeviceType.LIGHT,
                state={"state": "off", "brightness": 80, "color_temp": 3000},
                capabilities=["turn_on", "turn_off", "set_brightness", "set_color_temp"],
            ),
            VirtualDevice(
                device_id="kitchen_light",
                name="厨房灯",
                device_type=VirtualDeviceType.LIGHT,
                state={"state": "off", "brightness": 100, "color_temp": 4000},
                capabilities=["turn_on", "turn_off", "set_brightness"],
            ),
            VirtualDevice(
                device_id="living_room_ac",
                name="客厅空调",
                device_type=VirtualDeviceType.CLIMATE,
                state={"state": "off", "temperature": 24, "mode": "auto"},
                capabilities=["turn_on", "turn_off", "set_temperature", "set_mode"],
            ),
            VirtualDevice(
                device_id="bedroom_ac",
                name="卧室空调",
                device_type=VirtualDeviceType.CLIMATE,
                state={"state": "off", "temperature": 22, "mode": "cool"},
                capabilities=["turn_on", "turn_off", "set_temperature", "set_mode"],
            ),
            VirtualDevice(
                device_id="living_room_curtain",
                name="客厅窗帘",
                device_type=VirtualDeviceType.COVER,
                state={"state": "closed", "position": 0},
                capabilities=["open", "close", "set_position"],
            ),
            VirtualDevice(
                device_id="temperature_sensor",
                name="温度传感器",
                device_type=VirtualDeviceType.SENSOR,
                state={"value": 24.5, "unit": "℃"},
                capabilities=["read", "simulate_value"],
            ),
            VirtualDevice(
                device_id="humidity_sensor",
                name="湿度传感器",
                device_type=VirtualDeviceType.SENSOR,
                state={"value": 45.0, "unit": "%"},
                capabilities=["read", "simulate_value"],
            ),
            VirtualDevice(
                device_id="living_room_camera",
                name="客厅摄像头",
                device_type=VirtualDeviceType.CAMERA,
                state={"recording": False, "motion": False},
                capabilities=["start_recording", "stop_recording", "capture_image"],
            ),
            VirtualDevice(
                device_id="front_door_lock",
                name="前门锁",
                device_type=VirtualDeviceType.LOCK,
                state={"state": "locked"},
                capabilities=["lock", "unlock"],
            ),
        ]

        for device in default_devices:
            self.add_device(device)

        logger.info(f"Initialized {len(default_devices)} virtual devices")

    def add_device(self, device: VirtualDevice) -> None:
        self.devices[device.device_id] = device
        logger.info(f"Added virtual device: {device.name}")

    def remove_device(self, device_id: str) -> bool:
        if device_id not in self.devices:
            return False
        device = self.devices.pop(device_id)
        logger.info(f"Removed virtual device: {device.name}")
        return True

    def get_device(self, device_id: str) -> Optional[VirtualDevice]:
        return self.devices.get(device_id)

    def list_devices(
        self,
        device_type: Optional[VirtualDeviceType] = None
    ) -> List[VirtualDevice]:
        devices = list(self.devices.values())
        if device_type:
            devices = [d for d in devices if d.device_type == device_type]
        return devices

    def execute_command(
        self,
        device_id: str,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        device = self.devices.get(device_id)
        if not device:
            return {
                "success": False,
                "message": f"设备不存在: {device_id}",
            }

        return device.execute_command(command, params)

    def batch_execute_commands(
        self,
        commands: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results = []
        for cmd in commands:
            device_id = cmd.get("device_id")
            command = cmd.get("command")
            params = cmd.get("params", {})
            result = self.execute_command(device_id, command, params)
            results.append(result)
        return results

    def set_device_availability(
        self,
        device_id: str,
        available: bool
    ) -> bool:
        device = self.devices.get(device_id)
        if not device:
            return False
        device.is_available = available
        logger.info(f"Set device {device.name} availability to {available}")
        return True

    def search_devices(self, query: str) -> List[VirtualDevice]:
        query_lower = query.lower()
        return [
            device for device in self.devices.values()
            if (query_lower in device.name.lower() or 
                query_lower in device.device_id.lower())
        ]

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        return {
            device_id: device.state
            for device_id, device in self.devices.items()
        }

    def reset_all_devices(self) -> None:
        for device in self.devices.values():
            device.state = {}
        logger.info("Reset all virtual devices")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "devices": [device.to_dict() for device in self.devices.values()],
            "device_count": len(self.devices),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Virtual devices saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "VirtualDeviceManager":
        manager = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for device_data in data.get("devices", []):
            device = VirtualDevice(
                device_id=device_data["device_id"],
                name=device_data["name"],
                device_type=VirtualDeviceType(device_data["device_type"]),
                state=device_data.get("state", {}),
                attributes=device_data.get("attributes", {}),
                capabilities=device_data.get("capabilities", []),
                is_available=device_data.get("is_available", True),
            )
            manager.add_device(device)

        logger.info(f"Virtual devices loaded from {filepath}")
        return manager
