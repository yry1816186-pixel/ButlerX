from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException

from ..core.utils import utc_ts

logger = logging.getLogger(__name__)


class HomeAssistantAPI:
    def __init__(
        self,
        url: str = "http://localhost:8123",
        token: Optional[str] = None,
        mock: bool = False,
        timeout_sec: int = 10,
    ) -> None:
        self.url = url.rstrip("/")
        self.token = token
        self.mock = mock
        self.timeout_sec = timeout_sec
        self._headers = {}
        if self.token:
            self._headers["Authorization"] = f"Bearer {self.token}"
            self._headers["Content-Type"] = "application/json"
        self._states_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 5.0

    def _request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.mock:
            return self._mock_response(method, path, data)

        url = f"{self.url}{path}"
        try:
            if method == "GET":
                response = requests.get(url, headers=self._headers, timeout=self.timeout_sec)
            elif method == "POST":
                response = requests.post(url, headers=self._headers, json=data, timeout=self.timeout_sec)
            elif method == "PUT":
                response = requests.put(url, headers=self._headers, json=data, timeout=self.timeout_sec)
            elif method == "DELETE":
                response = requests.delete(url, headers=self._headers, timeout=self.timeout_sec)
            else:
                return {"error": f"Unsupported method: {method}"}

            if response.status_code >= 400:
                logger.error(f"HA API error: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}", "message": response.text}

            return response.json() if response.content else {}
        except RequestException as e:
            logger.error(f"HA API request failed: {e}")
            return {"error": str(e)}

    def _mock_response(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if "/api/services/" in path and method == "POST":
            domain, service = path.split("/")[-2], path.split("/")[-1]
            entity_id = data.get("entity_id", "light.default") if data else None
            logger.info(f"Mock HA call: {domain}.{service} on {entity_id}")
            return {
                "status": "ok",
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "data": data or {},
                "ts": utc_ts(),
            }
        return {"status": "ok", "mock": True, "ts": utc_ts()}

    def get_states(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        current_time = time.time()
        if not force_refresh and current_time - self._cache_timestamp < self._cache_ttl:
            return self._states_cache

        response = self._request("GET", "/api/states")
        if "error" not in response:
            self._states_cache = {state["entity_id"]: state for state in response}
            self._cache_timestamp = current_time
        return self._states_cache

    def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        states = self.get_states()
        return states.get(entity_id)

    def call_service(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict[str, Any]] = None,
        entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = service_data or {}
        if entity_id:
            data["entity_id"] = entity_id

        path = f"/api/services/{domain}/{service}"
        response = self._request("POST", path, data)

        if "error" not in response:
            self._cache_timestamp = 0
            response.update({
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "ts": utc_ts(),
            })
        return response

    def turn_on(self, entity_id: str, **kwargs) -> Dict[str, Any]:
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "turn_on", entity_id=entity_id, **kwargs)

    def turn_off(self, entity_id: str) -> Dict[str, Any]:
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "turn_off", entity_id=entity_id)

    def toggle(self, entity_id: str) -> Dict[str, Any]:
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "toggle", entity_id=entity_id)

    def set_brightness(self, entity_id: str, brightness: int) -> Dict[str, Any]:
        return self.call_service("light", "turn_on", entity_id=entity_id, brightness=brightness)

    def set_temperature(self, entity_id: str, temperature: float) -> Dict[str, Any]:
        return self.call_service("climate", "set_temperature", entity_id=entity_id, temperature=temperature)

    def set_hvac_mode(self, entity_id: str, mode: str) -> Dict[str, Any]:
        return self.call_service("climate", "set_hvac_mode", entity_id=entity_id, hvac_mode=mode)

    def open_cover(self, entity_id: str) -> Dict[str, Any]:
        return self.call_service("cover", "open_cover", entity_id=entity_id)

    def close_cover(self, entity_id: str) -> Dict[str, Any]:
        return self.call_service("cover", "close_cover", entity_id=entity_id)

    def set_cover_position(self, entity_id: str, position: int) -> Dict[str, Any]:
        return self.call_service("cover", "set_cover_position", entity_id=entity_id, position=position)

    def play_media(self, entity_id: str, media_content_id: str, media_content_type: str = "music") -> Dict[str, Any]:
        return self.call_service(
            "media_player",
            "play_media",
            entity_id=entity_id,
            media_content_id=media_content_id,
            media_content_type=media_content_type,
        )

    def pause(self, entity_id: str) -> Dict[str, Any]:
        return self.call_service("media_player", "media_pause", entity_id=entity_id)

    def play(self, entity_id: str) -> Dict[str, Any]:
        return self.call_service("media_player", "media_play", entity_id=entity_id)

    def stop(self, entity_id: str) -> Dict[str, Any]:
        return self.call_service("media_player", "media_stop", entity_id=entity_id)

    def get_devices(self) -> Dict[str, Dict[str, Any]]:
        response = self._request("GET", "/api/devices")
        return response

    def get_entities(self) -> Dict[str, Dict[str, Any]]:
        response = self._request("GET", "/api/entities")
        return response

    def get_services(self) -> Dict[str, List[str]]:
        response = self._request("GET", "/api/services")
        return response

    def get_areas(self) -> Dict[str, Dict[str, Any]]:
        response = self._request("GET", "/api/areas")
        return response

    def activate_scene(self, scene_entity_id: str) -> Dict[str, Any]:
        return self.call_service("scene", "turn_on", entity_id=scene_entity_id)

    def activate_script(self, script_entity_id: str) -> Dict[str, Any]:
        return self.call_service("script", "turn_on", entity_id=script_entity_id)

    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        devices = self.get_devices()
        for device in devices.values():
            if device.get("id") == device_id:
                return device
        return None

    def get_entity_attributes(self, entity_id: str) -> Dict[str, Any]:
        state = self.get_state(entity_id)
        return state.get("attributes", {}) if state else {}

    def is_entity_on(self, entity_id: str) -> bool:
        state = self.get_state(entity_id)
        if state:
            return state.get("state") in ["on", "open", "home", "playing"]
        return False

    def get_entity_value(self, entity_id: str, attribute: Optional[str] = None) -> Any:
        state = self.get_state(entity_id)
        if not state:
            return None
        if attribute:
            return state.get("attributes", {}).get(attribute)
        return state.get("state")

    def call_service_template(
        self,
        template: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = {"template": template}
        if variables:
            data["variables"] = variables
        return self._request("POST", "/api/services/homeassistant/trigger", data)
