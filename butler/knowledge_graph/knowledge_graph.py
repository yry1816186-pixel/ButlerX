from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from .space_model import SpaceModel, Room, Zone, Area
from .device_registry import DeviceRegistry, Device, DeviceType
from .user_preferences import UserPreferences, UserProfile, EnvironmentPreference

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    def __init__(self) -> None:
        self.space_model = SpaceModel()
        self.device_registry = DeviceRegistry()
        self.user_preferences = UserPreferences()
        self._rule_engine = None

    def query(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        result = {"query": query, "results": []}

        if "客厅" in query_lower or "living" in query_lower:
            rooms = self.space_model.find_rooms_by_type("living_room")
            for room in rooms:
                devices = self.space_model.find_devices_in_room(room.room_id)
                result["results"].append({
                    "type": "room",
                    "name": room.name,
                    "devices": list(devices),
                    "properties": room.properties,
                })

        if "灯" in query_lower or "light" in query_lower:
            devices = self.device_registry.find_devices_by_type(DeviceType.LIGHT)
            for device in devices:
                result["results"].append({
                    "type": "device",
                    "device_id": device.device_id,
                    "name": device.name,
                    "state": device.state,
                    "room_id": device.room_id,
                })

        if "用户" in query_lower or "user" in query_lower:
            users_at_home = self.user_preferences.get_users_at_home()
            result["results"].append({
                "type": "users",
                "users_at_home": [user.name for user in users_at_home],
                "total_users": len(self.user_preferences.users),
            })

        return result

    def get_context_for_user(self, user_id: str) -> Dict[str, Any]:
        user = self.user_preferences.get_user(user_id)
        if not user:
            return {}

        context = {
            "user": {
                "user_id": user.user_id,
                "name": user.name,
                "is_home": user.is_home,
                "last_seen": user.last_seen,
            },
            "preferences": user.preferences,
            "rooms": [],
            "devices": [],
        }

        for room in self.space_model.rooms.values():
            room_data = room.to_dict()
            room_devices = []
            for device_id in room.devices:
                device = self.device_registry.get_device(device_id)
                if device:
                    room_devices.append({
                        "device_id": device.device_id,
                        "name": device.name,
                        "device_type": device.device_type.value,
                        "state": device.state,
                    })
            room_data["devices"] = room_devices
            context["rooms"].append(room_data)

        return context

    def get_room_context(self, room_id: str) -> Dict[str, Any]:
        room = self.space_model.get_room(room_id)
        if not room:
            return {}

        context = room.to_dict()
        devices = []
        for device_id in room.devices:
            device = self.device_registry.get_device(device_id)
            if device:
                devices.append(device.to_dict())
        context["devices"] = devices

        zone = self.space_model.get_parent_zone(room_id)
        if zone:
            context["zone"] = zone.to_dict()

        area = self.space_model.get_parent_area(room_id)
        if area:
            context["area"] = area.to_dict()

        return context

    def find_devices_by_capability_and_location(
        self, 
        capability_name: str, 
        location_name: Optional[str] = None
    ) -> List[Device]:
        if location_name:
            room = None
            for r in self.space_model.rooms.values():
                if location_name in r.name.lower():
                    room = r
                    break
            
            if room:
                devices = []
                for device_id in room.devices:
                    device = self.device_registry.get_device(device_id)
                    if device and device.has_capability(capability_name):
                        devices.append(device)
                return devices

        return self.device_registry.find_devices_with_capability(capability_name)

    def get_user_environment_preferences(
        self, 
        user_id: str, 
        room_id: Optional[str] = None,
        time_of_day: Optional[str] = None,
        activity: Optional[str] = None
    ) -> Optional[EnvironmentPreference]:
        return self.user_preferences.find_matching_environment_preference(
            user_id=user_id,
            room_id=room_id,
            time_of_day=time_of_day,
            activity=activity
        )

    def get_scene_state(self) -> Dict[str, Any]:
        return {
            "space": self.space_model.to_dict(),
            "devices": {
                "total": len(self.device_registry.devices),
                "by_type": {
                    dt.value: len(self.device_registry.device_by_type.get(dt, set()))
                    for dt in DeviceType
                },
                "available": len(self.device_registry.get_available_devices()),
            },
            "users": {
                "total": len(self.user_preferences.users),
                "at_home": len(self.user_preferences.get_users_at_home()),
            },
        }

    def infer_intent_from_context(
        self, 
        text: str, 
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        intent = {
            "text": text,
            "user_id": user_id,
            "inferred_location": None,
            "inferred_target": None,
            "inferred_action": None,
            "context_used": [],
        }

        if user_id:
            user = self.user_preferences.get_user(user_id)
            if user and user.is_home:
                intent["context_used"].append("user_at_home")

        location_keywords = {
            "客厅": "living_room",
            "卧室": "bedroom",
            "厨房": "kitchen",
            "卫生间": "bathroom",
            "书房": "study",
            "阳台": "balcony",
        }

        for keyword, room_type in location_keywords.items():
            if keyword in text:
                rooms = self.space_model.find_rooms_by_type(room_type)
                if rooms:
                    intent["inferred_location"] = {
                        "type": "room",
                        "room_id": rooms[0].room_id,
                        "name": rooms[0].name,
                    }
                    intent["context_used"].append(f"location_{room_type}")
                    break

        action_keywords = {
            "开": "turn_on",
            "关": "turn_off",
            "打开": "turn_on",
            "关闭": "turn_off",
            "调亮": "increase_brightness",
            "调暗": "decrease_brightness",
            "调高": "increase_temperature",
            "调低": "decrease_temperature",
        }

        for keyword, action in action_keywords.items():
            if keyword in text:
                intent["inferred_action"] = action
                intent["context_used"].append(f"action_{action}")
                break

        target_keywords = {
            "灯": "light",
            "灯光": "light",
            "空调": "climate",
            "温度": "temperature",
            "窗帘": "cover",
            "电视": "media_player",
            "音响": "media_player",
        }

        for keyword, target in target_keywords.items():
            if keyword in text:
                intent["inferred_target"] = target
                intent["context_used"].append(f"target_{target}")
                break

        return intent

    def resolve_reference(
        self, 
        reference: str, 
        user_id: Optional[str] = None,
        current_room_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        reference_lower = reference.lower()

        if reference_lower in ["这里", "this"]:
            if current_room_id:
                return {"type": "room", "room_id": current_room_id}
            elif user_id:
                user = self.user_preferences.get_user(user_id)
                if user:
                    for room_id in user.preferences.get("last_room"):
                        room = self.space_model.get_room(room_id)
                        if room:
                            return {"type": "room", "room_id": room_id, "name": room.name}

        if reference_lower in ["那个", "that", "it"]:
            if user_id:
                user = self.user_preferences.get_user(user_id)
                if user:
                    last_device = user.preferences.get("last_device")
                    if last_device:
                        device = self.device_registry.get_device(last_device)
                        if device:
                            return {"type": "device", "device_id": device.device_id, "name": device.name}

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "space_model": self.space_model.to_dict(),
            "device_registry": self.device_registry.to_dict(),
            "user_preferences": self.user_preferences.to_dict(),
        }
