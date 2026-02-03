from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .device_discovery import (
    DiscoveredDevice,
    DiscoveryProtocol,
    DeviceCategory,
    DeviceDiscoveryListener,
    DeviceDiscoveryManager,
)

logger = logging.getLogger(__name__)


class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNRESPONSIVE = "unresponsive"
    ERROR = "error"
    UNKNOWN = "unknown"


class DeviceConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class DeviceHealth:
    device_id: str
    status: DeviceStatus
    connection_state: DeviceConnectionState
    last_seen: float
    last_ping: float
    ping_count: int = 0
    failed_pings: int = 0
    average_response_time: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_ping(self, response_time: float, success: bool) -> None:
        self.last_ping = time.time()
        self.ping_count += 1

        if success:
            self.failed_pings = 0
            if self.average_response_time == 0:
                self.average_response_time = response_time
            else:
                self.average_response_time = (
                    self.average_response_time * 0.9 + response_time * 0.1
                )
        else:
            self.failed_pings += 1

    def record_error(self, error: str) -> None:
        self.error_count += 1
        self.last_error = error

    def get_health_score(self) -> float:
        if self.ping_count == 0:
            return 50.0

        success_rate = (self.ping_count - self.failed_pings) / self.ping_count

        if self.error_count > 10:
            success_rate *= 0.5

        if self.failed_pings > 5:
            success_rate *= 0.7

        return max(0.0, min(100.0, success_rate * 100))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "status": self.status.value,
            "connection_state": self.connection_state.value,
            "last_seen": self.last_seen,
            "last_ping": self.last_ping,
            "ping_count": self.ping_count,
            "failed_pings": self.failed_pings,
            "average_response_time": self.average_response_time,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "health_score": self.get_health_score(),
        }


@dataclass
class ManagedDevice:
    discovered_device: DiscoveredDevice
    status: DeviceStatus = DeviceStatus.UNKNOWN
    connection_state: DeviceConnectionState = DeviceConnectionState.DISCONNECTED
    health: Optional[DeviceHealth] = None
    configuration: Dict[str, Any] = field(default_factory=dict)
    groups: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    last_updated: float = field(default_factory=time.time)
    last_controlled: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.health:
            self.health = DeviceHealth(
                device_id=self.discovered_device.device_id,
                status=self.status,
                connection_state=self.connection_state,
                last_seen=self.discovered_device.last_seen,
                last_ping=self.discovered_device.last_seen,
            )

    def update_status(self, status: DeviceStatus) -> None:
        self.status = status
        self.last_updated = time.time()
        if self.health:
            self.health.status = status

    def update_connection_state(self, state: DeviceConnectionState) -> None:
        self.connection_state = state
        self.last_updated = time.time()
        if self.health:
            self.health.connection_state = state

    def record_control(self) -> None:
        self.last_controlled = time.time()

    def add_group(self, group: str) -> None:
        self.groups.add(group)

    def remove_group(self, group: str) -> None:
        self.groups.discard(group)

    def add_tag(self, tag: str) -> None:
        self.tags.add(tag)

    def remove_tag(self, tag: str) -> None:
        self.tags.discard(tag)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "discovered_device": self.discovered_device.to_dict(),
            "status": self.status.value,
            "connection_state": self.connection_state.value,
            "health": self.health.to_dict() if self.health else None,
            "configuration": self.configuration,
            "groups": list(self.groups),
            "tags": list(self.tags),
            "last_updated": self.last_updated,
            "last_controlled": self.last_controlled,
            "metadata": self.metadata,
        }


class DeviceGroup:
    def __init__(self, group_id: str, name: str, description: str = ""):
        self.group_id = group_id
        self.name = name
        self.description = description
        self.device_ids: Set[str] = set()
        self.metadata: Dict[str, Any] = {}
        self.created_at: float = time.time()
        self.updated_at: float = time.time()

    def add_device(self, device_id: str) -> None:
        self.device_ids.add(device_id)
        self.updated_at = time.time()

    def remove_device(self, device_id: str) -> None:
        self.device_ids.discard(device_id)
        self.updated_at = time.time()

    def has_device(self, device_id: str) -> bool:
        return device_id in self.device_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "name": self.name,
            "description": self.description,
            "device_ids": list(self.device_ids),
            "device_count": len(self.device_ids),
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DeviceManager(DeviceDiscoveryListener):
    def __init__(self):
        self.discovery_manager = DeviceDiscoveryManager()
        self.discovery_manager.add_listener(self)

        self.managed_devices: Dict[str, ManagedDevice] = {}
        self.device_groups: Dict[str, DeviceGroup] = {}
        self.device_commands: Dict[str, Callable] = {}

        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return

        self._running = True

        await self.discovery_manager.start_continuous_discovery(interval=60.0)
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info("Device manager started")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        await self.discovery_manager.stop()

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        logger.info("Device manager stopped")

    async def _health_check_loop(self) -> None:
        while self._running:
            await asyncio.sleep(30)
            await self._check_device_health()

    async def _check_device_health(self) -> None:
        current_time = time.time()

        for device_id, managed_device in self.managed_devices.items():
            if managed_device.discovered_device.is_stale(max_age_seconds=300):
                managed_device.update_status(DeviceStatus.OFFLINE)
                managed_device.update_connection_state(DeviceConnectionState.DISCONNECTED)
            elif managed_device.status != DeviceStatus.ONLINE:
                managed_device.update_status(DeviceStatus.ONLINE)
                managed_device.update_connection_state(DeviceConnectionState.CONNECTED)

            if managed_device.health:
                managed_device.health.last_seen = current_time

    async def on_device_discovered(self, device: DiscoveredDevice) -> None:
        if device.device_id in self.managed_devices:
            logger.debug(f"Device already managed: {device.device_id}")
            return

        managed_device = ManagedDevice(
            discovered_device=device,
            status=DeviceStatus.ONLINE,
            connection_state=DeviceConnectionState.CONNECTED,
        )

        self.managed_devices[device.device_id] = managed_device
        logger.info(f"New device discovered and managed: {device.name} ({device.device_id})")

    async def on_device_lost(self, device_id: str) -> None:
        if device_id in self.managed_devices:
            managed_device = self.managed_devices[device_id]
            managed_device.update_status(DeviceStatus.OFFLINE)
            managed_device.update_connection_state(DeviceConnectionState.DISCONNECTED)
            logger.info(f"Device lost: {device_id}")

    async def on_device_updated(self, device: DiscoveredDevice) -> None:
        if device.device_id in self.managed_devices:
            self.managed_devices[device.device_id].discovered_device = device
            self.managed_devices[device.device_id].last_updated = time.time()

    async def discover_devices(self, timeout: float = 30.0) -> List[ManagedDevice]:
        discovered = await self.discovery_manager.scan_all(timeout=timeout)

        for device in discovered:
            await self.on_device_discovered(device)

        return list(self.managed_devices.values())

    async def control_device(
        self,
        device_id: str,
        command: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if device_id not in self.managed_devices:
            return {"success": False, "error": "Device not found"}

        managed_device = self.managed_devices[device_id]

        if command in self.device_commands:
            try:
                result = await self.device_commands[command](device_id, parameters or {})
                managed_device.record_control()
                return {"success": True, "result": result}
            except Exception as e:
                logger.error(f"Error controlling device {device_id}: {e}")
                managed_device.health.record_error(str(e)) if managed_device.health else None
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Unknown command"}

    def register_command(self, command: str, handler: Callable) -> None:
        self.device_commands[command] = handler
        logger.info(f"Registered device command: {command}")

    def unregister_command(self, command: str) -> bool:
        if command in self.device_commands:
            del self.device_commands[command]
            return True
        return False

    def create_group(
        self,
        group_id: str,
        name: str,
        description: str = ""
    ) -> DeviceGroup:
        group = DeviceGroup(group_id, name, description)
        self.device_groups[group_id] = group
        logger.info(f"Created device group: {name} ({group_id})")
        return group

    def delete_group(self, group_id: str) -> bool:
        if group_id not in self.device_groups:
            return False

        group = self.device_groups[group_id]

        for device_id in group.device_ids:
            if device_id in self.managed_devices:
                self.managed_devices[device_id].remove_group(group_id)

        del self.device_groups[group_id]
        logger.info(f"Deleted device group: {group_id}")
        return True

    def add_device_to_group(self, device_id: str, group_id: str) -> bool:
        if group_id not in self.device_groups:
            return False

        if device_id not in self.managed_devices:
            return False

        self.device_groups[group_id].add_device(device_id)
        self.managed_devices[device_id].add_group(group_id)

        return True

    def remove_device_from_group(self, device_id: str, group_id: str) -> bool:
        if group_id not in self.device_groups:
            return False

        if device_id not in self.managed_devices:
            return False

        self.device_groups[group_id].remove_device(device_id)
        self.managed_devices[device_id].remove_group(group_id)

        return True

    async def control_group(
        self,
        group_id: str,
        command: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if group_id not in self.device_groups:
            return {"success": False, "error": "Group not found"}

        group = self.device_groups[group_id]
        results = []

        for device_id in group.device_ids:
            result = await self.control_device(device_id, command, parameters)
            results.append({"device_id": device_id, **result})

        successful = sum(1 for r in results if r.get("success", False))
        return {
            "success": successful > 0,
            "results": results,
            "successful": successful,
            "total": len(results),
        }

    def get_device(self, device_id: str) -> Optional[ManagedDevice]:
        return self.managed_devices.get(device_id)

    def get_devices(self) -> List[ManagedDevice]:
        return list(self.managed_devices.values())

    def get_devices_by_status(self, status: DeviceStatus) -> List[ManagedDevice]:
        return [d for d in self.managed_devices.values() if d.status == status]

    def get_devices_by_category(self, category: DeviceCategory) -> List[ManagedDevice]:
        return [
            d for d in self.managed_devices.values()
            if d.discovered_device.category == category
        ]

    def get_devices_by_group(self, group_id: str) -> List[ManagedDevice]:
        if group_id not in self.device_groups:
            return []

        device_ids = self.device_groups[group_id].device_ids
        return [
            self.managed_devices[did] for did in device_ids
            if did in self.managed_devices
        ]

    def get_devices_by_tag(self, tag: str) -> List[ManagedDevice]:
        return [
            d for d in self.managed_devices.values()
            if tag in d.tags
        ]

    def search_devices(self, query: str) -> List[ManagedDevice]:
        query_lower = query.lower()
        results = []

        for device in self.managed_devices.values():
            name = device.discovered_device.name.lower()
            device_id = device.discovered_device.device_id.lower()

            if query_lower in name or query_lower in device_id:
                results.append(device)

            for tag in device.tags:
                if query_lower in tag.lower():
                    results.append(device)
                    break

        return results

    def get_group(self, group_id: str) -> Optional[DeviceGroup]:
        return self.device_groups.get(group_id)

    def get_groups(self) -> List[DeviceGroup]:
        return list(self.device_groups.values())

    def get_device_health_summary(self) -> Dict[str, Any]:
        total = len(self.managed_devices)
        online = len(self.get_devices_by_status(DeviceStatus.ONLINE))
        offline = len(self.get_devices_by_status(DeviceStatus.OFFLINE))
        unresponsive = len(self.get_devices_by_status(DeviceStatus.UNRESPONSIVE))

        health_scores = [
            device.health.get_health_score()
            for device in self.managed_devices.values()
            if device.health
        ]

        avg_health = sum(health_scores) / len(health_scores) if health_scores else 0.0

        return {
            "total_devices": total,
            "online": online,
            "offline": offline,
            "unresponsive": unresponsive,
            "online_rate": (online / total * 100) if total > 0 else 0,
            "average_health_score": avg_health,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "devices": [device.to_dict() for device in self.managed_devices.values()],
            "device_count": len(self.managed_devices),
            "groups": [group.to_dict() for group in self.device_groups.values()],
            "group_count": len(self.device_groups),
            "health_summary": self.get_device_health_summary(),
            "discovery": self.discovery_manager.to_dict(),
        }

    def save_to_file(self, filepath: str) -> None:
        data = {
            "devices": [device.to_dict() for device in self.managed_devices.values()],
            "groups": [group.to_dict() for group in self.device_groups.values()],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Device manager saved to {filepath}")

    def load_from_file(self, filepath: str) -> None:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for group_data in data.get("groups", []):
                group = DeviceGroup(
                    group_id=group_data["group_id"],
                    name=group_data["name"],
                    description=group_data.get("description", ""),
                )
                group.device_ids = set(group_data.get("device_ids", []))
                group.metadata = group_data.get("metadata", {})
                group.created_at = group_data.get("created_at", time.time())
                group.updated_at = group_data.get("updated_at", time.time())
                self.device_groups[group.group_id] = group

            logger.info(f"Device manager loaded from {filepath}")
        except Exception as e:
            logger.error(f"Error loading device manager from {filepath}: {e}")
