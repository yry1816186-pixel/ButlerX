from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from .agent import Agent, AgentConfig, AgentMessage, MessageType, AgentTask, AgentCapability
from ..core.entity_model import Entity, Device, Sensor, EntityType, EntityDomain

logger = logging.getLogger(__name__)

class DeviceAction(Enum):
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    TOGGLE = "toggle"
    SET_STATE = "set_state"
    GET_STATE = "get_state"
    SET_ATTRIBUTE = "set_attribute"
    GET_ATTRIBUTE = "get_attribute"
    CALL_SERVICE = "call_service"
    DISCOVER = "discover"
    SYNC = "sync"

class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNRESPONSIVE = "unresponsive"
    ERROR = "error"
    UPDATING = "updating"

@dataclass
class DeviceInfo:
    device_id: str
    device_type: str
    name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    capabilities: List[str] = None
    status: DeviceStatus = DeviceStatus.OFFLINE
    last_seen: datetime = None
    attributes: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "capabilities": self.capabilities or [],
            "status": self.status.value,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "attributes": self.attributes or {}
        }

class DeviceAgent(Agent):
    def __init__(
        self,
        config: AgentConfig,
        service_caller: Optional[callable] = None
    ):
        super().__init__(config)
        self._service_caller = service_caller
        self._device_cache: Dict[str, DeviceInfo] = {}
        self._device_groups: Dict[str, List[str]] = {}
        self._device_states: Dict[str, Dict[str, Any]] = {}
        self._pending_operations: Dict[str, Dict[str, Any]] = {}
        self._operation_timeout = 30.0
        self._cache_ttl = 300.0

    async def initialize(self) -> bool:
        try:
            self.add_capability(AgentCapability(
                name="device_control",
                description="Control smart home devices",
                input_types=["device_command", "device_id"],
                output_types=["device_state", "operation_result"],
                parameters={
                    "timeout": {"type": "float", "default": 30.0},
                    "retry_count": {"type": "integer", "default": 3}
                }
            ))

            self.add_capability(AgentCapability(
                name="device_discovery",
                description="Discover and register new devices",
                input_types=["discovery_request"],
                output_types=["devices", "device_info"]
            ))

            self.add_capability(AgentCapability(
                name="device_monitoring",
                description="Monitor device status and health",
                input_types=["device_id"],
                output_types=["status", "health_metrics"]
            ))

            self.add_capability(AgentCapability(
                name="device_grouping",
                description="Group devices for coordinated control",
                input_types=["group_name", "device_ids"],
                output_types=["group_info"]
            ))

            self.add_capability(AgentCapability(
                name="device_synchronization",
                description="Synchronize device states",
                input_types=["sync_request"],
                output_types=["sync_result"]
            ))

            await self._discover_devices()

            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize device agent: {e}")
            return False

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        try:
            if message.message_type == MessageType.REQUEST:
                return await self._handle_request(message)

            elif message.message_type == MessageType.NOTIFICATION:
                await self._handle_notification(message)

        except Exception as e:
            self._logger.error(f"Error processing message: {e}")

        return None

    async def _handle_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        content = message.content if isinstance(message.content, dict) else {"action": message.content}

        action = content.get("action", "get_state")

        if action == "control":
            result = await self._control_device(
                device_id=content.get("device_id"),
                device_action=DeviceAction(content.get("device_action", "set_state")),
                parameters=content.get("parameters", {})
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "discover":
            result = await self._discover_devices(
                device_type=content.get("device_type"),
                force=content.get("force", False)
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "monitor":
            result = await self._monitor_device(
                device_id=content.get("device_id")
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "group_control":
            result = await self._control_group(
                group_name=content.get("group_name"),
                device_action=DeviceAction(content.get("device_action", "set_state")),
                parameters=content.get("parameters", {})
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "create_group":
            result = await self._create_group(
                group_name=content.get("group_name"),
                device_ids=content.get("device_ids", [])
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "sync":
            result = await self._sync_devices(
                device_ids=content.get("device_ids")
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        return None

    async def _handle_notification(self, message: AgentMessage):
        content = message.content if isinstance(message.content, dict) else {}

        if content.get("type") == "device_state_change":
            await self._handle_state_change(
                device_id=content.get("device_id"),
                new_state=content.get("new_state"),
                attributes=content.get("attributes", {})
            )

        elif content.get("type") == "device_discovery":
            await self._register_discovered_device(
                device_info=content.get("device_info", {})
            )

    async def _discover_devices(
        self,
        device_type: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        discovered = []

        if not force:
            for device_id, info in self._device_cache.items():
                if (datetime.now() - info.last_seen).total_seconds() < self._cache_ttl:
                    if device_type is None or info.device_type == device_type:
                        discovered.append(info.to_dict())

            return {
                "devices": discovered,
                "count": len(discovered),
                "cached": True,
                "timestamp": datetime.now().isoformat()
            }

        if self._service_caller:
            try:
                result = await self._service_caller("discovery/scan", {"device_type": device_type})
                discovered = result.get("devices", [])
            except Exception as e:
                self._logger.error(f"Discovery failed: {e}")

        for device_data in discovered:
            device_id = device_data.get("device_id")
            if device_id:
                info = DeviceInfo(
                    device_id=device_id,
                    device_type=device_data.get("device_type", "unknown"),
                    name=device_data.get("name", device_id),
                    manufacturer=device_data.get("manufacturer"),
                    model=device_data.get("model"),
                    firmware_version=device_data.get("firmware_version"),
                    capabilities=device_data.get("capabilities", []),
                    status=DeviceStatus(device_data.get("status", "online")),
                    last_seen=datetime.now(),
                    attributes=device_data.get("attributes", {})
                )
                self._device_cache[device_id] = info

        return {
            "devices": [d.to_dict() for d in self._device_cache.values()],
            "count": len(self._device_cache),
            "cached": False,
            "timestamp": datetime.now().isoformat()
        }

    async def _control_device(
        self,
        device_id: str,
        device_action: DeviceAction,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        import uuid

        operation_id = str(uuid.uuid4())

        self._pending_operations[operation_id] = {
            "device_id": device_id,
            "action": device_action.value,
            "parameters": parameters,
            "started_at": datetime.now(),
            "status": "pending"
        }

        try:
            if self._service_caller:
                service_name = self._action_to_service(device_action)
                service_data = {"entity_id": device_id, **parameters}

                result = await self._service_caller(service_name, service_data)

                self._pending_operations[operation_id]["status"] = "completed"
                self._pending_operations[operation_id]["completed_at"] = datetime.now()

                return {
                    "operation_id": operation_id,
                    "device_id": device_id,
                    "action": device_action.value,
                    "success": True,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "operation_id": operation_id,
                    "device_id": device_id,
                    "action": device_action.value,
                    "success": False,
                    "error": "No service caller available",
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            self._pending_operations[operation_id]["status"] = "failed"
            self._pending_operations[operation_id]["error"] = str(e)

            return {
                "operation_id": operation_id,
                "device_id": device_id,
                "action": device_action.value,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def _monitor_device(self, device_id: str) -> Dict[str, Any]:
        device_info = self._device_cache.get(device_id)

        if not device_info:
            entity = Entity.get(device_id)
            if entity:
                device_info = DeviceInfo(
                    device_id=device_id,
                    device_type=entity.domain.value,
                    name=entity.name,
                    status=DeviceStatus.ONLINE if entity.available else DeviceStatus.OFFLINE,
                    last_seen=datetime.now(),
                    attributes=entity.attributes
                )
                self._device_cache[device_id] = device_info
            else:
                return {
                    "device_id": device_id,
                    "status": "not_found",
                    "error": "Device not found"
                }

        entity = Entity.get(device_id)
        health_metrics = {
            "online": entity.available if entity else False,
            "last_state_change": entity.last_changed.isoformat() if entity else None,
            "last_updated": entity.last_updated.isoformat() if entity else None,
            "state": entity.state if entity else None
        }

        return {
            "device_id": device_id,
            "info": device_info.to_dict(),
            "health_metrics": health_metrics,
            "timestamp": datetime.now().isoformat()
        }

    async def _control_group(
        self,
        group_name: str,
        device_action: DeviceAction,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        if group_name not in self._device_groups:
            return {
                "group_name": group_name,
                "success": False,
                "error": "Group not found"
            }

        device_ids = self._device_groups[group_name]
        results = []

        for device_id in device_ids:
            result = await self._control_device(device_id, device_action, parameters)
            results.append(result)

        successful = sum(1 for r in results if r.get("success", False))

        return {
            "group_name": group_name,
            "device_count": len(device_ids),
            "success_count": successful,
            "failed_count": len(results) - successful,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }

    async def _create_group(
        self,
        group_name: str,
        device_ids: List[str]
    ) -> Dict[str, Any]:
        valid_devices = []
        for device_id in device_ids:
            if device_id in self._device_cache or Entity.get(device_id):
                valid_devices.append(device_id)

        self._device_groups[group_name] = valid_devices

        return {
            "group_name": group_name,
            "device_count": len(valid_devices),
            "device_ids": valid_devices,
            "created_at": datetime.now().isoformat()
        }

    async def _sync_devices(
        self,
        device_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if device_ids is None:
            device_ids = list(self._device_cache.keys())

        synced = []
        failed = []

        for device_id in device_ids:
            try:
                info = await self._monitor_device(device_id)
                synced.append(device_id)
            except Exception as e:
                failed.append({"device_id": device_id, "error": str(e)})

        return {
            "requested_count": len(device_ids),
            "synced_count": len(synced),
            "failed_count": len(failed),
            "synced_devices": synced,
            "failed_devices": failed,
            "timestamp": datetime.now().isoformat()
        }

    async def _handle_state_change(
        self,
        device_id: str,
        new_state: str,
        attributes: Dict[str, Any]
    ):
        entity = Entity.get(device_id)
        if entity:
            entity.state = new_state
            if attributes:
                entity.update_attributes(attributes)

        if device_id in self._device_cache:
            self._device_cache[device_id].status = DeviceStatus.ONLINE
            self._device_cache[device_id].last_seen = datetime.now()

    async def _register_discovered_device(self, device_info: Dict[str, Any]):
        device_id = device_info.get("device_id")
        if device_id:
            info = DeviceInfo(
                device_id=device_id,
                device_type=device_info.get("device_type", "unknown"),
                name=device_info.get("name", device_id),
                manufacturer=device_info.get("manufacturer"),
                model=device_info.get("model"),
                firmware_version=device_info.get("firmware_version"),
                capabilities=device_info.get("capabilities", []),
                status=DeviceStatus(device_info.get("status", "online")),
                last_seen=datetime.now(),
                attributes=device_info.get("attributes", {})
            )
            self._device_cache[device_id] = info

    def _action_to_service(self, action: DeviceAction) -> str:
        service_map = {
            DeviceAction.TURN_ON: "turn_on",
            DeviceAction.TURN_OFF: "turn_off",
            DeviceAction.TOGGLE: "toggle",
            DeviceAction.SET_STATE: "set_state",
            DeviceAction.SET_ATTRIBUTE: "set_attribute",
            DeviceAction.GET_STATE: "get_state",
            DeviceAction.GET_ATTRIBUTE: "get_attribute",
            DeviceAction.CALL_SERVICE: "call_service"
        }
        return service_map.get(action, "call_service")

    async def execute_task(self, task: AgentTask) -> Any:
        task_type = task.task_type
        payload = task.payload

        if task_type == "control":
            return await self._control_device(
                device_id=payload.get("device_id"),
                device_action=DeviceAction(payload.get("device_action", "set_state")),
                parameters=payload.get("parameters", {})
            )

        elif task_type == "discover":
            return await self._discover_devices(
                device_type=payload.get("device_type"),
                force=payload.get("force", False)
            )

        elif task_type == "monitor":
            return await self._monitor_device(
                device_id=payload.get("device_id")
            )

        elif task_type == "group_control":
            return await self._control_group(
                group_name=payload.get("group_name"),
                device_action=DeviceAction(payload.get("device_action", "set_state")),
                parameters=payload.get("parameters", {})
            )

        elif task_type == "sync":
            return await self._sync_devices(
                device_ids=payload.get("device_ids")
            )

        raise ValueError(f"Unknown task type: {task_type}")

    async def shutdown(self):
        self._device_cache.clear()
        self._device_groups.clear()
        self._logger.info("Device agent shutting down")

    def get_device_cache(self) -> Dict[str, DeviceInfo]:
        return self._device_cache.copy()

    def get_groups(self) -> Dict[str, List[str]]:
        return self._device_groups.copy()

    def clear_cache(self):
        self._device_cache.clear()

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "device_capabilities": list(self.capabilities.keys()),
            "cached_devices": len(self._device_cache),
            "device_groups": len(self._device_groups),
            "pending_operations": len(self._pending_operations)
        })
        return base_dict
