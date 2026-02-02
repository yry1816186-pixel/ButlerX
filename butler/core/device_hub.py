from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..simulator import VirtualDeviceManager
from ..tools.ha_api import HomeAssistantAPI
from ..ir_control import IRController

logger = logging.getLogger(__name__)


class DeviceBackend(Enum):
    HOMEASSISTANT = "homeassistant"
    VIRTUAL = "virtual"
    IR = "ir"
    AUTO = "auto"


class DeviceControlHub:
    def __init__(
        self,
        ha_api: Optional[HomeAssistantAPI] = None,
        virtual_device_manager: Optional[VirtualDeviceManager] = None,
        ir_controller: Optional[IRController] = None,
        default_backend: DeviceBackend = DeviceBackend.AUTO,
    ) -> None:
        self.ha = ha_api or HomeAssistantAPI()
        self.virtual = virtual_device_manager or VirtualDeviceManager()
        self.ir = ir_controller or IRController()
        self.default_backend = default_backend
        
        self._device_backend_map: Dict[str, DeviceBackend] = {}
        self._entity_id_to_device_id: Dict[str, str] = {}
        self._device_id_to_entity_id: Dict[str, str] = {}

    def register_device_backend(
        self,
        device_id: str,
        backend: DeviceBackend,
        entity_id: Optional[str] = None,
    ) -> None:
        self._device_backend_map[device_id] = backend
        if entity_id and backend == DeviceBackend.HOMEASSISTANT:
            self._entity_id_to_device_id[entity_id] = device_id
            self._device_id_to_entity_id[device_id] = entity_id
        logger.info(f"Registered device {device_id} with backend {backend.value}")

    def _get_backend(self, device_id: str) -> DeviceBackend:
        if device_id in self._device_backend_map:
            return self._device_backend_map[device_id]
        
        if self.default_backend != DeviceBackend.AUTO:
            return self.default_backend
        
        if self.ha and not self.ha.mock and device_id.startswith("sensor."):
            return DeviceBackend.HOMEASSISTANT
        elif self.virtual.has_device(device_id):
            return DeviceBackend.VIRTUAL
        else:
            return DeviceBackend.VIRTUAL

    def turn_on(self, device_id: str, **kwargs) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Turning on {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.turn_on(entity_id, **kwargs)
        elif backend == DeviceBackend.IR:
            result = self.ir.send_command(device_id, "power_on")
        else:
            result = self.virtual.execute_command(device_id, "turn_on", kwargs)
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def turn_off(self, device_id: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Turning off {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.turn_off(entity_id)
        elif backend == DeviceBackend.IR:
            result = self.ir.send_command(device_id, "power_off")
        else:
            result = self.virtual.execute_command(device_id, "turn_off", {})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def toggle(self, device_id: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Toggling {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.toggle(entity_id)
        elif backend == DeviceBackend.VIRTUAL:
            state = self.virtual.get_device_state(device_id)
            current_state = state.get("state", {})
            is_on = current_state.get("state") == "on"
            action = "turn_off" if is_on else "turn_on"
            result = self.virtual.execute_command(device_id, action, {})
        else:
            result = {"error": f"Toggle not supported for {backend.value} backend"}
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def set_brightness(self, device_id: str, brightness: int) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Setting brightness {brightness} for {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.set_brightness(entity_id, brightness)
        else:
            result = self.virtual.execute_command(device_id, "set_brightness", {"brightness": brightness})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def set_temperature(self, device_id: str, temperature: float) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Setting temperature {temperature} for {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.set_temperature(entity_id, temperature)
        else:
            result = self.virtual.execute_command(device_id, "set_temperature", {"temperature": temperature})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def set_hvac_mode(self, device_id: str, mode: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Setting HVAC mode {mode} for {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.set_hvac_mode(entity_id, mode)
        else:
            result = self.virtual.execute_command(device_id, "set_hvac_mode", {"mode": mode})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def open_cover(self, device_id: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Opening cover {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.open_cover(entity_id)
        else:
            result = self.virtual.execute_command(device_id, "open", {})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def close_cover(self, device_id: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Closing cover {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.close_cover(entity_id)
        else:
            result = self.virtual.execute_command(device_id, "close", {})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def play_media(self, device_id: str, media_content_id: str, media_content_type: str = "music") -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Playing media {media_content_id} on {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.play_media(entity_id, media_content_id, media_content_type)
        else:
            result = self.virtual.execute_command(device_id, "play_media", {
                "media_content_id": media_content_id,
                "media_content_type": media_content_type,
            })
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def pause(self, device_id: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Pausing {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.pause(entity_id)
        else:
            result = self.virtual.execute_command(device_id, "pause", {})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def play(self, device_id: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Playing {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.play(entity_id)
        else:
            result = self.virtual.execute_command(device_id, "play", {})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def stop(self, device_id: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        logger.info(f"Stopping {device_id} using {backend.value} backend")
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            result = self.ha.stop(entity_id)
        else:
            result = self.virtual.execute_command(device_id, "stop", {})
        
        return {"device_id": device_id, "backend": backend.value, **result}

    def send_ir_command(self, device_id: str, command: str, repeat: int = 1) -> Dict[str, Any]:
        logger.info(f"Sending IR command {command} to {device_id}")
        result = self.ir.send_command(device_id, command, repeat)
        return {"device_id": device_id, "backend": "ir", **result}

    def learn_ir_command(self, device_id: str, command_name: str, duration: float = 5.0) -> Dict[str, Any]:
        logger.info(f"Learning IR command {command_name} for {device_id}")
        session_id = self.ir.start_learning_session(device_id)
        result = self.ir.learn_command(session_id, duration)
        if result.get("success"):
            self.ir.add_mapping(device_id, command_name, result.get("code"))
        return {"device_id": device_id, "backend": "ir", **result}

    def get_device_state(self, device_id: str) -> Dict[str, Any]:
        backend = self._get_backend(device_id)
        
        if backend == DeviceBackend.HOMEASSISTANT:
            entity_id = self._device_id_to_entity_id.get(device_id, device_id)
            state = self.ha.get_state(entity_id)
            if state:
                return {"device_id": device_id, "backend": backend.value, "state": state}
        else:
            state = self.virtual.get_device_state(device_id)
            if state:
                return {"device_id": device_id, "backend": backend.value, "state": state}
        
        return {"device_id": device_id, "backend": backend.value, "error": "Device not found"}

    def list_devices(self, backend: Optional[DeviceBackend] = None) -> List[Dict[str, Any]]:
        devices = []
        
        if backend is None or backend == DeviceBackend.HOMEASSISTANT:
            ha_states = self.ha.get_states()
            for entity_id, state in ha_states.items():
                devices.append({
                    "device_id": self._entity_id_to_device_id.get(entity_id, entity_id),
                    "entity_id": entity_id,
                    "backend": "homeassistant",
                    "state": state,
                })
        
        if backend is None or backend == DeviceBackend.VIRTUAL:
            virtual_devices = self.virtual.list_devices()
            for device in virtual_devices:
                devices.append({
                    "device_id": device.get("device_id"),
                    "backend": "virtual",
                    "type": device.get("type"),
                    "name": device.get("name"),
                })
        
        return devices

    def sync_from_homeassistant(self) -> Dict[str, Any]:
        if self.ha.mock:
            return {"error": "Home Assistant is in mock mode"}
        
        states = self.ha.get_states(force_refresh=True)
        registered = 0
        
        for entity_id, state in states.items():
            device_id = self._entity_id_to_device_id.get(entity_id)
            if not device_id:
                device_id = entity_id.replace(".", "_")
                self.register_device_backend(device_id, DeviceBackend.HOMEASSISTANT, entity_id)
                registered += 1
        
        return {"synced_devices": len(states), "newly_registered": registered}

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        all_states = {}
        
        if not self.ha.mock:
            ha_states = self.ha.get_states()
            for entity_id, state in ha_states.items():
                device_id = self._entity_id_to_device_id.get(entity_id, entity_id)
                all_states[device_id] = {"backend": "homeassistant", "state": state}
        
        virtual_devices = self.virtual.list_devices()
        for device in virtual_devices:
            device_id = device.get("device_id")
            state = self.virtual.get_device_state(device_id)
            if device_id:
                all_states[device_id] = {"backend": "virtual", "state": state}
        
        return all_states
