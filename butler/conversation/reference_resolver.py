from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReferenceResolver:
    def __init__(self) -> None:
        self._pronouns = {
            "这里": "here", "这个": "this", "这个房间": "this room",
            "那里": "there", "那个": "that",
            "它": "it", "它们": "them",
            "here": "here", "this": "this", "this room": "this room",
            "there": "there", "that": "that",
            "it": "it", "them": "them",
        }
        self._demonstratives = {
            "这盏灯": "this_light", "那个开关": "that_switch",
            "这个空调": "this_ac", "那个电视": "that_tv",
        }

    def resolve(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        context = context or {}
        result = {
            "resolved": False,
            "resolution": {},
            "original_text": text,
            "confidence": 0.0,
        }

        if not context:
            return result

        text_lower = text.lower()
        resolved_items = []

        if "这里" in text_lower or "this" in text_lower or "这个房间" in text_lower:
            current_room = context.get("current_room")
            if current_room:
                resolved_items.append({
                    "type": "room",
                    "reference": "这里",
                    "resolved_to": current_room,
                    "confidence": 0.9,
                })

        if "那个" in text_lower or "that" in text_lower or "它" in text_lower:
            last_device = context.get("last_device")
            last_action = context.get("last_action")
            
            if last_device:
                resolved_items.append({
                    "type": "device",
                    "reference": "那个/它",
                    "resolved_to": last_device,
                    "confidence": 0.8,
                })
            elif last_action and last_action.get("target"):
                resolved_items.append({
                    "type": "device",
                    "reference": "那个/它",
                    "resolved_to": last_action["target"],
                    "confidence": 0.7,
                })

        user_id = context.get("user_id")
        if user_id:
            user_context = context.get(f"user_{user_id}", {})
            last_room = user_context.get("last_room")
            if last_room and "这里" in text_lower:
                resolved_items.append({
                    "type": "room",
                    "reference": "这里(用户上下文)",
                    "resolved_to": last_room,
                    "confidence": 0.85,
                })

        if resolved_items:
            result["resolved"] = True
            result["resolution"] = {
                "items": resolved_items,
                "replaced_text": self._replace_references(text, resolved_items),
            }
            result["confidence"] = max(item["confidence"] for item in resolved_items)

        return result

    def _replace_references(self, text: str, resolved_items: List[Dict[str, Any]]) -> str:
        replaced_text = text
        for item in resolved_items:
            reference = item["reference"]
            resolved_to = item["resolved_to"]
            if isinstance(resolved_to, dict):
                resolved_to_str = resolved_to.get("name", str(resolved_to))
            else:
                resolved_to_str = str(resolved_to)
            replaced_text = replaced_text.replace(reference, resolved_to_str)
        return replaced_text

    def detect_references(self, text: str) -> List[str]:
        detected = []
        text_lower = text.lower()
        for pronoun in self._pronouns:
            if pronoun in text_lower:
                detected.append(pronoun)
        return detected

    def resolve_device_reference(
        self,
        reference: str,
        available_devices: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        reference_lower = reference.lower()
        
        for device in available_devices:
            device_name = device.get("name", "").lower()
            device_id = device.get("device_id", "").lower()
            
            if reference_lower in device_name or reference_lower in device_id:
                return device

        return None

    def resolve_location_reference(
        self,
        reference: str,
        available_locations: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        reference_lower = reference.lower()
        
        for location in available_locations:
            location_name = location.get("name", "").lower()
            location_id = location.get("room_id", "").lower()
            
            if reference_lower in location_name or reference_lower in location_id:
                return location

        return None
