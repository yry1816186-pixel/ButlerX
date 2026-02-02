from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    LIGHT = "light"
    SWITCH = "switch"
    SENSOR = "sensor"
    CLIMATE = "climate"
    CAMERA = "camera"
    LOCK = "lock"
    COVER = "cover"
    MEDIA_PLAYER = "media_player"
    VACUUM = "vacuum"
    IRRIGATION = "irrigation"
    OTHER = "other"


@dataclass
class DeviceCapability:
    name: str
    capability_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    supported_values: Optional[List[Any]] = None
    read_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "capability_type": self.capability_type,
            "params": self.params,
            "supported_values": self.supported_values,
            "read_only": self.read_only,
        }


@dataclass
class Device:
    device_id: str
    name: str
    device_type: DeviceType
    capabilities: List[DeviceCapability] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    room_id: Optional[str] = None
    zone_id: Optional[str] = None
    area_id: Optional[str] = None
    is_available: bool = True
    last_updated: Optional[float] = None

    def has_capability(self, capability_name: str) -> bool:
        return any(cap.name == capability_name for cap in self.capabilities)

    def get_capability(self, capability_name: str) -> Optional[DeviceCapability]:
        for cap in self.capabilities:
            if cap.name == capability_name:
                return cap
        return None

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def update_state(self, key: str, value: Any) -> None:
        self.state[key] = value

    def update_states(self, states: Dict[str, Any]) -> None:
        self.state.update(states)

    def get_attribute(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "capabilities": [cap.to_dict() for cap in self.capabilities],
            "state": self.state,
            "attributes": self.attributes,
            "room_id": self.room_id,
            "zone_id": self.zone_id,
            "area_id": self.area_id,
            "is_available": self.is_available,
            "last_updated": self.last_updated,
        }


class DeviceRegistry:
    def __init__(self) -> None:
        self.devices: Dict[str, Device] = {}
        self.device_by_type: Dict[DeviceType, Set[str]] = {}
        self.device_by_room: Dict[str, Set[str]] = {}

    def register_device(self, device: Device) -> None:
        self.devices[device.device_id] = device
        if device.device_type not in self.device_by_type:
            self.device_by_type[device.device_type] = set()
        self.device_by_type[device.device_type].add(device.device_id)
        if device.room_id:
            if device.room_id not in self.device_by_room:
                self.device_by_room[device.room_id] = set()
            self.device_by_room[device.room_id].add(device.device_id)
        logger.info(f"Registered device: {device.name} ({device.device_id})")

    def unregister_device(self, device_id: str) -> None:
        device = self.devices.pop(device_id, None)
        if not device:
            return
        if device.device_type in self.device_by_type:
            self.device_by_type[device.device_type].discard(device_id)
        if device.room_id and device.room_id in self.device_by_room:
            self.device_by_room[device.room_id].discard(device_id)
        logger.info(f"Unregistered device: {device_id}")

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)

    def find_devices_by_type(self, device_type: DeviceType) -> List[Device]:
        device_ids = self.device_by_type.get(device_type, set())
        return [self.devices[did] for did in device_ids if did in self.devices]

    def find_devices_by_room(self, room_id: str) -> List[Device]:
        device_ids = self.device_by_room.get(room_id, set())
        return [self.devices[did] for did in device_ids if did in self.devices]

    def find_devices_with_capability(self, capability_name: str) -> List[Device]:
        result = []
        for device in self.devices.values():
            if device.has_capability(capability_name):
                result.append(device)
        return result

    def search_devices(self, query: str) -> List[Device]:
        query_lower = query.lower()
        result = []
        for device in self.devices.values():
            if (query_lower in device.name.lower() or 
                query_lower in device.device_id.lower()):
                result.append(device)
        return result

    def update_device_state(self, device_id: str, state: Dict[str, Any]) -> bool:
        device = self.devices.get(device_id)
        if not device:
            return False
        device.update_states(state)
        return True

    def set_device_availability(self, device_id: str, available: bool) -> bool:
        device = self.devices.get(device_id)
        if not device:
            return False
        device.is_available = available
        return True

    def get_available_devices(self) -> List[Device]:
        return [device for device in self.devices.values() if device.is_available]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "devices": [device.to_dict() for device in self.devices.values()],
            "device_count": len(self.devices),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Device registry saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "DeviceRegistry":
        registry = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for device_data in data.get("devices", []):
            capabilities = []
            for cap_data in device_data.get("capabilities", []):
                cap = DeviceCapability(
                    name=cap_data["name"],
                    capability_type=cap_data["capability_type"],
                    params=cap_data.get("params", {}),
                    supported_values=cap_data.get("supported_values"),
                    read_only=cap_data.get("read_only", False),
                )
                capabilities.append(cap)
            
            device = Device(
                device_id=device_data["device_id"],
                name=device_data["name"],
                device_type=DeviceType(device_data["device_type"]),
                capabilities=capabilities,
                state=device_data.get("state", {}),
                attributes=device_data.get("attributes", {}),
                room_id=device_data.get("room_id"),
                zone_id=device_data.get("zone_id"),
                area_id=device_data.get("area_id"),
                is_available=device_data.get("is_available", True),
                last_updated=device_data.get("last_updated"),
            )
            registry.register_device(device)
        
        logger.info(f"Device registry loaded from {filepath}")
        return registry
