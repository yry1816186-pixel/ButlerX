from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type

from .integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationDevice,
    IntegrationEvent,
    IntegrationType,
    IntegrationStatus,
    IntegrationCapability,
)

logger = logging.getLogger(__name__)


class IntegrationPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class IntegrationInstance:
    integration: BaseIntegration
    config: IntegrationConfig
    status: IntegrationStatus = IntegrationStatus.DISCONNECTED
    connected_at: Optional[float] = None
    last_error: Optional[str] = None
    error_count: int = 0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integration_id": self.config.integration_id,
            "name": self.config.name,
            "type": self.config.integration_type.value,
            "status": self.status.value,
            "enabled": self.config.enabled,
            "connected_at": self.connected_at,
            "last_error": self.last_error,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "capabilities": [c.value for c in self.config.capabilities],
            "device_count": len(self.integration.devices),
            "metadata": self.metadata,
        }


class IntegrationManager:
    def __init__(self):
        self._integrations: Dict[str, IntegrationInstance] = {}
        self._integration_classes: Dict[str, Type[BaseIntegration]] = {}
        self._integration_configs: Dict[str, IntegrationConfig] = {}

        self._event_history: List[IntegrationEvent] = []
        self._max_history_size = 1000

        self._listeners: List[Callable[[IntegrationEvent], None]] = []

        self._running = False
        self._task: Optional[asyncio.Task] = None

        self._init_default_configs()

    def _init_default_configs(self) -> None:
        default_configs = [
            IntegrationConfig(
                integration_id="home_assistant",
                name="Home Assistant",
                integration_type=IntegrationType.SMART_HOME,
                config={
                    "url": "http://localhost:8123",
                    "token": "",
                    "websocket_url": "ws://localhost:8123/api/websocket",
                },
                capabilities={
                    IntegrationCapability.DEVICE_CONTROL,
                    IntegrationCapability.DEVICE_DISCOVERY,
                    IntegrationCapability.STATE_REPORTING,
                    IntegrationCapability.EVENT_SUBSCRIPTION,
                    IntegrationCapability.SCENE_CONTROL,
                    IntegrationCapability.AUTOMATION,
                },
                auto_connect=True,
                retry_interval=30.0,
                max_retries=5,
            ),
            IntegrationConfig(
                integration_id="philips_hue",
                name="Philips Hue",
                integration_type=IntegrationType.LIGHTING,
                config={
                    "bridge_ip": "",
                    "username": "",
                    "api_key": "",
                },
                capabilities={
                    IntegrationCapability.DEVICE_CONTROL,
                    IntegrationCapability.DEVICE_DISCOVERY,
                    IntegrationCapability.STATE_REPORTING,
                    IntegrationCapability.SCENE_CONTROL,
                },
                auto_connect=True,
                retry_interval=60.0,
                max_retries=3,
            ),
            IntegrationConfig(
                integration_id="sonos",
                name="Sonos",
                integration_type=IntegrationType.MEDIA,
                config={
                    "discovery_enabled": True,
                },
                capabilities={
                    IntegrationCapability.DEVICE_DISCOVERY,
                    IntegrationCapability.DEVICE_CONTROL,
                    IntegrationCapability.MEDIA_CONTROL,
                },
                auto_connect=True,
                retry_interval=30.0,
                max_retries=3,
            ),
            IntegrationConfig(
                integration_id="ring",
                name="Ring",
                integration_type=IntegrationType.SECURITY,
                config={
                    "api_key": "",
                    "api_secret": "",
                },
                capabilities={
                    IntegrationCapability.DEVICE_DISCOVERY,
                    IntegrationCapability.DEVICE_CONTROL,
                    IntegrationCapability.EVENT_SUBSCRIPTION,
                    IntegrationCapability.DATA_QUERY,
                },
                auto_connect=False,
                retry_interval=60.0,
                max_retries=3,
            ),
            IntegrationConfig(
                integration_id="nest",
                name="Google Nest",
                integration_type=IntegrationType.CLIMATE,
                config={
                    "client_id": "",
                    "client_secret": "",
                    "refresh_token": "",
                },
                capabilities={
                    IntegrationCapability.DEVICE_DISCOVERY,
                    IntegrationCapability.DEVICE_CONTROL,
                    IntegrationCapability.STATE_REPORTING,
                },
                auto_connect=True,
                retry_interval=60.0,
                max_retries=3,
            ),
            IntegrationConfig(
                integration_id="homekit",
                name="Apple HomeKit",
                integration_type=IntegrationType.SMART_HOME,
                config={
                    "pin": "0000",
                    "pairing_enabled": False,
                },
                capabilities={
                    IntegrationCapability.DEVICE_DISCOVERY,
                    IntegrationCapability.DEVICE_CONTROL,
                    IntegrationCapability.STATE_REPORTING,
                },
                auto_connect=False,
                retry_interval=60.0,
                max_retries=3,
            ),
            IntegrationConfig(
                integration_id="spotify",
                name="Spotify",
                integration_type=IntegrationType.MEDIA,
                config={
                    "client_id": "",
                    "client_secret": "",
                    "redirect_uri": "",
                },
                capabilities={
                    IntegrationCapability.MEDIA_CONTROL,
                },
                auto_connect=False,
                retry_interval=30.0,
                max_retries=3,
            ),
            IntegrationConfig(
                integration_id="xiaomi_miio",
                name="Xiaomi Mijia",
                integration_type=IntegrationType.SMART_HOME,
                config={
                    "host": "",
                    "token": "",
                },
                capabilities={
                    IntegrationCapability.DEVICE_CONTROL,
                    IntegrationCapability.DEVICE_DISCOVERY,
                    IntegrationCapability.STATE_REPORTING,
                },
                auto_connect=True,
                retry_interval=30.0,
                max_retries=3,
            ),
        ]

        for config in default_configs:
            self._integration_configs[config.integration_id] = config

        logger.info(f"Initialized {len(default_configs)} integration configs")

    def register_integration_class(
        self,
        integration_id: str,
        integration_class: Type[BaseIntegration]
    ) -> None:
        self._integration_classes[integration_id] = integration_class
        logger.info(f"Registered integration class: {integration_id}")

    def unregister_integration_class(self, integration_id: str) -> bool:
        if integration_id in self._integration_classes:
            del self._integration_classes[integration_id]
            return True
        return False

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("Integration manager started")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        for instance in self._integrations.values():
            if instance.status == IntegrationStatus.CONNECTED:
                await self._disconnect_integration(instance.config.integration_id)

        logger.info("Integration manager stopped")

    async def _monitoring_loop(self) -> None:
        while self._running:
            await self._check_integrations()
            await asyncio.sleep(30.0)

    async def _check_integrations(self) -> None:
        for instance in self._integrations.values():
            config = instance.config

            if not config.enabled:
                continue

            if instance.status == IntegrationStatus.CONNECTED:
                await instance.integration.subscribe_events()

            elif instance.status == IntegrationStatus.DISCONNECTED:
                if config.auto_connect:
                    await self._connect_integration(config.integration_id)

            elif instance.status == IntegrationStatus.ERROR:
                if instance.retry_count < config.max_retries:
                    await asyncio.sleep(config.retry_interval)
                    await self._connect_integration(config.integration_id)
                    instance.retry_count += 1

    async def _connect_integration(self, integration_id: str) -> bool:
        instance = self._integrations.get(integration_id)
        if not instance:
            return False

        config = instance.config
        integration_class = self._integration_classes.get(integration_id)

        if not integration_class:
            logger.warning(f"No integration class registered for {integration_id}")
            return False

        try:
            instance.status = IntegrationStatus.CONNECTING
            logger.info(f"Connecting to integration: {config.name}")

            integration = integration_class(config)

            success = await integration.connect()
            if success:
                instance.integration = integration
                instance.status = IntegrationStatus.CONNECTED
                instance.connected_at = time.time()
                instance.last_error = None
                instance.error_count = 0
                instance.retry_count = 0

                await integration.discover_devices()

                for device in integration.get_devices():
                    instance.integration.devices[device.device_id] = device

                logger.info(f"Successfully connected to {config.name}")
                return True
            else:
                instance.status = IntegrationStatus.ERROR
                instance.last_error = "Connection failed"
                instance.error_count += 1
                logger.error(f"Failed to connect to {config.name}")
                return False

        except Exception as e:
            instance.status = IntegrationStatus.ERROR
            instance.last_error = str(e)
            instance.error_count += 1
            logger.error(f"Error connecting to {config.name}: {e}")
            return False

    async def _disconnect_integration(self, integration_id: str) -> bool:
        instance = self._integrations.get(integration_id)
        if not instance:
            return False

        try:
            await instance.integration.disconnect()
            instance.status = IntegrationStatus.DISCONNECTED
            instance.connected_at = None
            logger.info(f"Disconnected from {instance.config.name}")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from {instance.config.name}: {e}")
            return False

    def add_listener(self, listener: Callable[[IntegrationEvent], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[IntegrationEvent], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def _notify_event(self, event: IntegrationEvent) -> None:
        self._event_history.append(event)

        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]

        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error in integration event listener: {e}")

    def register_config(self, config: IntegrationConfig) -> None:
        self._integration_configs[config.integration_id] = config
        logger.info(f"Registered integration config: {config.name}")

    def unregister_config(self, integration_id: str) -> bool:
        if integration_id in self._integration_configs:
            del self._integration_configs[integration_id]
            return True
        return False

    def get_config(self, integration_id: str) -> Optional[IntegrationConfig]:
        return self._integration_configs.get(integration_id)

    def get_configs(self, integration_type: Optional[IntegrationType] = None) -> List[IntegrationConfig]:
        configs = list(self._integration_configs.values())

        if integration_type:
            configs = [c for c in configs if c.integration_type == integration_type]

        return configs

    async def add_integration(self, integration_id: str) -> bool:
        config = self._integration_configs.get(integration_id)
        if not config:
            return False

        instance = IntegrationInstance(
            integration=None,
            config=config,
            status=IntegrationStatus.DISCONNECTED,
        )

        self._integrations[integration_id] = instance

        if config.auto_connect:
            return await self._connect_integration(integration_id)

        return True

    async def remove_integration(self, integration_id: str) -> bool:
        if integration_id not in self._integrations:
            return False

        await self._disconnect_integration(integration_id)
        del self._integrations[integration_id]

        logger.info(f"Removed integration: {integration_id}")
        return True

    async def enable_integration(self, integration_id: str) -> bool:
        instance = self._integrations.get(integration_id)
        if not instance:
            return False

        instance.config.enabled = True

        if instance.status == IntegrationStatus.DISCONNECTED:
            return await self._connect_integration(integration_id)

        return True

    async def disable_integration(self, integration_id: str) -> bool:
        instance = self._integrations.get(integration_id)
        if not instance:
            return False

        instance.config.enabled = False
        await self._disconnect_integration(integration_id)

        return True

    async def control_device(
        self,
        integration_id: str,
        device_id: str,
        command: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        instance = self._integrations.get(integration_id)
        if not instance or not instance.is_connected():
            return {"success": False, "error": "Integration not connected"}

        try:
            result = await instance.integration.control_device(device_id, command, parameters)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error controlling device: {e}")
            return {"success": False, "error": str(e)}

    async def discover_devices(self, integration_id: str) -> List[IntegrationDevice]:
        instance = self._integrations.get(integration_id)
        if not instance or not instance.is_connected():
            return []

        try:
            devices = await instance.integration.discover_devices()

            for device in devices:
                instance.integration.devices[device.device_id] = device

            return devices
        except Exception as e:
            logger.error(f"Error discovering devices: {e}")
            return []

    def get_integration(self, integration_id: str) -> Optional[IntegrationInstance]:
        return self._integrations.get(integration_id)

    def get_integrations(
        self,
        integration_type: Optional[IntegrationType] = None,
        status: Optional[IntegrationStatus] = None
    ) -> List[IntegrationInstance]:
        integrations = list(self._integrations.values())

        if integration_type:
            integrations = [i for i in integrations if i.config.integration_type == integration_type]

        if status:
            integrations = [i for i in integrations if i.status == status]

        return integrations

    def get_all_devices(self) -> List[IntegrationDevice]:
        devices = []

        for instance in self._integrations.values():
            if instance.is_connected():
                devices.extend(instance.integration.get_devices())

        return devices

    def get_device(self, device_id: str) -> Optional[IntegrationDevice]:
        for instance in self._integrations.values():
            if instance.is_connected():
                device = instance.integration.get_device(device_id)
                if device:
                    return device
        return None

    def get_event_history(
        self,
        integration_id: Optional[str] = None,
        limit: int = 100
    ) -> List[IntegrationEvent]:
        events = self._event_history

        if integration_id:
            events = [e for e in events if e.integration_id == integration_id]

        return events[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        total = len(self._integrations)
        connected = sum(1 for i in self._integrations.values() if i.is_connected())
        enabled = sum(1 for i in self._integrations.values() if i.config.enabled)

        total_devices = sum(len(i.integration.devices) for i in self._integrations.values())

        by_type = {}
        for instance in self._integrations.values():
            type_name = instance.config.integration_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

        return {
            "total_integrations": total,
            "connected_integrations": connected,
            "enabled_integrations": enabled,
            "total_devices": total_devices,
            "by_type": by_type,
            "connection_rate": (connected / total * 100) if total > 0 else 0,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integrations": [instance.to_dict() for instance in self._integrations.values()],
            "statistics": self.get_statistics(),
        }

    def save_to_file(self, filepath: str) -> None:
        data = {
            "configs": [config.to_dict() for config in self._integration_configs.values()],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Integration configs saved to {filepath}")

    def load_from_file(self, filepath: str) -> None:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for config_data in data.get("configs", []):
                config = IntegrationConfig(**config_data)
                self._integration_configs[config.integration_id] = config

            logger.info(f"Integration configs loaded from {filepath}")
        except Exception as e:
            logger.error(f"Error loading integration configs from {filepath}: {e}")
