from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .ir_controller import IRCommand, IRDevice

logger = logging.getLogger(__name__)


@dataclass
class IRMapping:
    mapping_id: str
    name: str
    semantic_actions: Dict[str, str] = field(default_factory=dict)
    device_commands: Dict[str, Dict[str, str]] = field(default_factory=dict)
    state_simulations: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "name": self.name,
            "semantic_actions": self.semantic_actions,
            "device_commands": self.device_commands,
            "state_simulations": self.state_simulations,
            "metadata": self.metadata,
        }


class IRMappingRegistry:
    def __init__(self) -> None:
        self.mappings: Dict[str, IRMapping] = {}
        self._init_default_mappings()

    def _init_default_mappings(self) -> None:
        default_mappings = [
            IRMapping(
                mapping_id="tv_samsung_mapping",
                name="三星电视控制映射",
                semantic_actions={
                    "turn_on": "power_on",
                    "turn_off": "power_off",
                    "volume_up": "volume_up",
                    "volume_down": "volume_down",
                    "channel_up": "channel_up",
                    "channel_down": "channel_down",
                    "mute": "mute",
                },
                device_commands={
                    "tv_samsung": {
                        "power_on": "power_on",
                        "power_off": "power_off",
                        "volume_up": "vol_up",
                        "volume_down": "vol_down",
                        "channel_up": "ch_up",
                        "channel_down": "ch_down",
                        "mute": "mute",
                    }
                },
                state_simulations={
                    "power": {"on": "power_on", "off": "power_off"},
                    "volume": {"up": "volume_up", "down": "volume_down"},
                },
            ),
            IRMapping(
                mapping_id="ac_midea_mapping",
                name="美的空调控制映射",
                semantic_actions={
                    "turn_on": "power_on",
                    "turn_off": "power_off",
                    "temperature_up": "temp_up",
                    "temperature_down": "temp_down",
                    "mode_cool": "mode_cool",
                    "mode_heat": "mode_heat",
                    "mode_auto": "mode_auto",
                    "fan_up": "fan_up",
                    "fan_down": "fan_down",
                },
                device_commands={
                    "air_conditioner_midea": {
                        "power_on": "power",
                        "power_off": "power",
                        "temp_up": "temp_up",
                        "temp_down": "temp_down",
                        "mode_cool": "mode_cool",
                        "mode_heat": "mode_heat",
                        "mode_auto": "mode_auto",
                        "fan_up": "fan_up",
                        "fan_down": "fan_down",
                    }
                },
                state_simulations={
                    "power": {"on": "power_on", "off": "power_off"},
                    "temperature": {"up": "temperature_up", "down": "temperature_down"},
                    "mode": {"cool": "mode_cool", "heat": "mode_heat", "auto": "mode_auto"},
                },
            ),
            IRMapping(
                mapping_id="fan_xiaomi_mapping",
                name="小米风扇控制映射",
                semantic_actions={
                    "turn_on": "power_on",
                    "turn_off": "power_off",
                    "speed_up": "speed_up",
                    "speed_down": "speed_down",
                    "oscillation_toggle": "oscillation",
                },
                device_commands={
                    "fan_xiaomi": {
                        "power_on": "power",
                        "power_off": "power",
                        "speed_up": "speed_up",
                        "speed_down": "speed_down",
                        "oscillation": "oscillation",
                    }
                },
                state_simulations={
                    "power": {"on": "power_on", "off": "power_off"},
                    "speed": {"up": "speed_up", "down": "speed_down"},
                },
            ),
        ]

        for mapping in default_mappings:
            self.add_mapping(mapping)

        logger.info(f"Initialized {len(default_mappings)} default IR mappings")

    def add_mapping(self, mapping: IRMapping) -> None:
        self.mappings[mapping.mapping_id] = mapping
        logger.info(f"Added IR mapping: {mapping.name}")

    def remove_mapping(self, mapping_id: str) -> bool:
        if mapping_id not in self.mappings:
            return False
        mapping = self.mappings.pop(mapping_id)
        logger.info(f"Removed IR mapping: {mapping.name}")
        return True

    def get_mapping(self, mapping_id: str) -> Optional[IRMapping]:
        return self.mappings.get(mapping_id)

    def resolve_action_to_command(
        self,
        semantic_action: str,
        device_id: str
    ) -> Optional[str]:
        for mapping in self.mappings.values():
            if semantic_action in mapping.semantic_actions:
                device_commands = mapping.device_commands.get(device_id, {})
                mapped_command = mapping.semantic_actions[semantic_action]
                actual_command = device_commands.get(mapped_command)
                if actual_command:
                    return actual_command

        return None

    def simulate_state(
        self,
        device_id: str,
        state_type: str,
        state_value: str
    ) -> Optional[str]:
        for mapping in self.mappings.values():
            state_sim = mapping.state_simulations.get(state_type, {})
            if state_value in state_sim:
                device_commands = mapping.device_commands.get(device_id, {})
                simulated_action = state_sim[state_value]
                actual_command = device_commands.get(simulated_action)
                if actual_command:
                    return actual_command

        return None

    def get_supported_actions_for_device(
        self,
        device_id: str
    ) -> List[str]:
        actions = set()
        for mapping in self.mappings.values():
            if device_id in mapping.device_commands:
                actions.update(mapping.semantic_actions.keys())
        return list(actions)

    def get_devices_for_action(
        self,
        semantic_action: str
    ) -> List[str]:
        devices = set()
        for mapping in self.mappings.values():
            if semantic_action in mapping.semantic_actions:
                devices.update(mapping.device_commands.keys())
        return list(devices)

    def create_custom_mapping(
        self,
        mapping_id: str,
        name: str,
        semantic_actions: Dict[str, str],
        device_commands: Dict[str, Dict[str, str]]
    ) -> IRMapping:
        mapping = IRMapping(
            mapping_id=mapping_id,
            name=name,
            semantic_actions=semantic_actions,
            device_commands=device_commands,
        )
        self.add_mapping(mapping)
        return mapping

    def list_mappings(self) -> List[IRMapping]:
        return list(self.mappings.values())

    def search_mappings(
        self,
        query: str
    ) -> List[IRMapping]:
        query_lower = query.lower()
        return [
            mapping for mapping in self.mappings.values()
            if (query_lower in mapping.name.lower() or 
                query_lower in mapping.mapping_id.lower())
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mappings": [mapping.to_dict() for mapping in self.mappings.values()],
            "mapping_count": len(self.mappings),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"IR mappings saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "IRMappingRegistry":
        registry = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for mapping_data in data.get("mappings", []):
            mapping = IRMapping(
                mapping_id=mapping_data["mapping_id"],
                name=mapping_data["name"],
                semantic_actions=mapping_data.get("semantic_actions", {}),
                device_commands=mapping_data.get("device_commands", {}),
                state_simulations=mapping_data.get("state_simulations", {}),
                metadata=mapping_data.get("metadata", {}),
            )
            registry.add_mapping(mapping)

        logger.info(f"IR mappings loaded from {filepath}")
        return registry
