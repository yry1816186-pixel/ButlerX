from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    SMART_HOME = "smart_home"
    MEDIA = "media"
    SECURITY = "security"
    CLIMATE = "climate"
    LIGHTING = "lighting"
    VOICE = "voice"
    ENERGY = "energy"
    CUSTOM = "custom"


class IntegrationStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"
    PAUSED = "paused"


class IntegrationCapability(Enum):
    DEVICE_CONTROL = "device_control"
    DEVICE_DISCOVERY = "device_discovery"
    STATE_REPORTING = "state_reporting"
    EVENT_SUBSCRIPTION = "event_subscription"
    SCENE_CONTROL = "scene_control"
    AUTOMATION = "automation"
    DATA_QUERY = "data_query"
    MEDIA_CONTROL = "media_control"
    VOICE_CONTROL = "voice_control"


@dataclass
class IntegrationConfig:
    integration_id: str
    name: str
    integration_type: IntegrationType
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    capabilities: Set[IntegrationCapability] = field(default_factory=set)
    auto_connect: bool = True
    retry_interval: float = 60.0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrationDevice:
    device_id: str
    name: str
    integration_id: str
    device_type: str
    capabilities: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def update_state(self, state: Dict[str, Any]) -> None:
        self.state.update(state)
        self.last_seen = time.time()

    def is_stale(self, max_age: float = 300.0) -> bool:
        return time.time() - self.last_seen > max_age

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "integration_id": self.integration_id,
            "device_type": self.device_type,
            "capabilities": self.capabilities,
            "state": self.state,
            "attributes": self.attributes,
            "metadata": self.metadata,
            "discovered_at": self.discovered_at,
            "last_seen": self.last_seen,
        }


@dataclass
class IntegrationEvent:
    event_type: str
    integration_id: str
    device_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "integration_id": self.integration_id,
            "device_id": self.device_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class BaseIntegration(ABC):
    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.status = IntegrationStatus.DISCONNECTED
        self.devices: Dict[str, IntegrationDevice] = {}
        self._event_listeners: List[Callable[[IntegrationEvent], None]] = []
        self._state_listeners: List[Callable[[str, Dict[str, Any]], None]] = []
        self._error_listeners: List[Callable[[Exception], None]] = []

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        pass

    @abstractmethod
    async def discover_devices(self) -> List[IntegrationDevice]:
        pass

    @abstractmethod
    async def control_device(
        self,
        device_id: str,
        command: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def query_device_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        pass

    async def subscribe_events(self) -> bool:
        logger.info(f"Event subscription not implemented for {self.config.name}")
        return False

    async def unsubscribe_events(self) -> bool:
        logger.info(f"Event unsubscription not implemented for {self.config.name}")
        return False

    def add_event_listener(self, listener: Callable[[IntegrationEvent], None]) -> None:
        self._event_listeners.append(listener)

    def remove_event_listener(self, listener: Callable[[IntegrationEvent], None]) -> None:
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    def add_state_listener(self, listener: Callable[[str, Dict[str, Any]], None]) -> None:
        self._state_listeners.append(listener)

    def remove_state_listener(self, listener: Callable[[str, Dict[str, Any]], None]) -> None:
        if listener in self._state_listeners:
            self._state_listeners.remove(listener)

    def add_error_listener(self, listener: Callable[[Exception], None]) -> None:
        self._error_listeners.append(listener)

    def remove_error_listener(self, listener: Callable[[Exception], None]) -> None:
        if listener in self._error_listeners:
            self._error_listeners.remove(listener)

    async def _notify_event(self, event: IntegrationEvent) -> None:
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error in event listener: {e}")

    async def _notify_state_change(self, device_id: str, state: Dict[str, Any]) -> None:
        for listener in self._state_listeners:
            try:
                listener(device_id, state)
            except Exception as e:
                logger.error(f"Error in state listener: {e}")

    async def _notify_error(self, error: Exception) -> None:
        for listener in self._error_listeners:
            try:
                listener(error)
            except Exception as e:
                logger.error(f"Error in error listener: {e}")

    def get_device(self, device_id: str) -> Optional[IntegrationDevice]:
        return self.devices.get(device_id)

    def get_devices(self) -> List[IntegrationDevice]:
        return list(self.devices.values())

    def get_status(self) -> IntegrationStatus:
        return self.status

    def is_connected(self) -> bool:
        return self.status in [IntegrationStatus.CONNECTED, IntegrationStatus.AUTHENTICATED]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integration_id": self.config.integration_id,
            "name": self.config.name,
            "type": self.config.integration_type.value,
            "status": self.status.value,
            "enabled": self.config.enabled,
            "capabilities": [c.value for c in self.config.capabilities],
            "device_count": len(self.devices),
            "devices": [device.to_dict() for device in self.devices.values()],
            "config": self.config.config,
            "metadata": self.config.metadata,
        }
