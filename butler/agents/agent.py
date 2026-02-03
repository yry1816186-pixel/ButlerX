from __future__ import annotations
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set, Union
from datetime import datetime
from enum import Enum
import uuid
import json

from ..core.error_handler import handle_errors, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"
    COMMAND = "command"
    HEARTBEAT = "heartbeat"

class AgentPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

@dataclass
class AgentCapability:
    name: str
    description: str
    input_types: List[str] = field(default_factory=list)
    output_types: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_types": self.input_types,
            "output_types": self.output_types,
            "parameters": self.parameters,
            "enabled": self.enabled
        }

@dataclass
class AgentMessage:
    message_id: str
    sender_id: str
    recipient_id: Optional[str]
    message_type: MessageType
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    priority: AgentPriority = AgentPriority.NORMAL
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    requires_response: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "message_type": self.message_type.value,
            "content": self.content if not isinstance(self.content, (bytes, bytearray)) else "<binary>",
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "requires_response": self.requires_response
        }

@dataclass
class AgentConfig:
    agent_id: str
    name: str
    agent_type: str
    version: str = "1.0.0"
    enabled: bool = True
    max_concurrent_tasks: int = 10
    heartbeat_interval: float = 30.0
    response_timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    memory_limit_mb: int = 256
    cpu_threshold: float = 80.0
    custom_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "agent_type": self.agent_type,
            "version": self.version,
            "enabled": self.enabled,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "heartbeat_interval": self.heartbeat_interval,
            "response_timeout": self.response_timeout,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_threshold": self.cpu_threshold,
            "custom_config": self.custom_config
        }

@dataclass
class AgentTask:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: AgentPriority = AgentPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "result": str(self.result)[:500] if self.result else None,
            "error": self.error
        }

class Agent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.INITIALIZING
        self.capabilities: Dict[str, AgentCapability] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running_tasks: Set[str] = set()
        self._message_history: List[AgentMessage] = []
        self._statistics: Dict[str, Any] = {
            "messages_sent": 0,
            "messages_received": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "uptime_seconds": 0,
            "error_count": 0
        }
        self._created_at = datetime.now()
        self._last_heartbeat = datetime.now()
        self._running = False
        self._message_bus: Optional[Callable] = None
        self._logger = logging.getLogger(f"butler.agent.{config.agent_id}")

    @property
    def agent_id(self) -> str:
        return self.config.agent_id

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def agent_type(self) -> str:
        return self.config.agent_type

    @property
    def is_ready(self) -> bool:
        return self.status == AgentStatus.READY

    @property
    def is_busy(self) -> bool:
        return self.status == AgentStatus.BUSY or len(self._running_tasks) >= self.config.max_concurrent_tasks

    @property
    def uptime(self) -> float:
        return (datetime.now() - self._created_at).total_seconds()

    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        pass

    @abstractmethod
    async def execute_task(self, task: AgentTask) -> Any:
        pass

    @abstractmethod
    async def shutdown(self):
        pass

    async def start(self):
        if self._running:
            return

        self._running = True

        try:
            success = await self.initialize()
            if not success:
                self.status = AgentStatus.ERROR
                raise RuntimeError(f"Agent {self.agent_id} failed to initialize")

            self.status = AgentStatus.READY
            self._logger.info(f"Agent {self.agent_id} started and ready")

            await asyncio.gather(
                self._process_task_queue(),
                self._send_heartbeat()
            )

        except Exception as e:
            self.status = AgentStatus.ERROR
            self._statistics["error_count"] += 1
            self._logger.error(f"Agent {self.agent_id} failed to start: {e}")
            raise

    async def stop(self):
        if not self._running:
            return

        self.status = AgentStatus.SHUTTING_DOWN
        self._running = False

        try:
            await self.shutdown()
            self.status = AgentStatus.SHUTDOWN
            self._logger.info(f"Agent {self.agent_id} stopped")
        except Exception as e:
            self.status = AgentStatus.ERROR
            self._logger.error(f"Agent {self.agent_id} error during shutdown: {e}")

    async def send_message(
        self,
        recipient_id: str,
        content: Any,
        message_type: MessageType = MessageType.REQUEST,
        priority: AgentPriority = AgentPriority.NORMAL,
        requires_response: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentMessage]:
        if not self._message_bus:
            self._logger.warning("No message bus configured")
            return None

        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            message_type=message_type,
            content=content,
            priority=priority,
            requires_response=requires_response,
            metadata=metadata or {}
        )

        try:
            await self._message_bus(message)
            self._statistics["messages_sent"] += 1
            self._message_history.append(message)
            return message
        except Exception as e:
            self._logger.error(f"Failed to send message: {e}")
            return None

    async def broadcast_message(
        self,
        content: Any,
        message_type: MessageType = MessageType.BROADCAST,
        priority: AgentPriority = AgentPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ):
        if not self._message_bus:
            return

        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            recipient_id=None,
            message_type=message_type,
            content=content,
            priority=priority,
            metadata=metadata or {}
        )

        await self._message_bus(message)
        self._statistics["messages_sent"] += 1

    async def receive_message(self, message: AgentMessage):
        self._statistics["messages_received"] += 1
        self._message_history.append(message)

        if len(self._message_history) > 1000:
            self._message_history = self._message_history[-1000:]

        try:
            response = await self.process_message(message)

            if message.requires_response and response:
                response.recipient_id = message.sender_id
                response.message_type = MessageType.RESPONSE
                response.correlation_id = message.message_id
                await self._message_bus(response)

        except Exception as e:
            self._logger.error(f"Error processing message: {e}")
            self._statistics["error_count"] += 1

    async def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: AgentPriority = AgentPriority.NORMAL
    ) -> str:
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            payload=payload,
            priority=priority
        )

        await self._task_queue.put(task)
        return task.task_id

    def add_capability(self, capability: AgentCapability):
        self.capabilities[capability.name] = capability

    def remove_capability(self, capability_name: str):
        if capability_name in self.capabilities:
            del self.capabilities[capability_name]

    def has_capability(self, capability_name: str) -> bool:
        return capability_name in self.capabilities and self.capabilities[capability_name].enabled

    def register_message_handler(self, message_type: str, handler: Callable):
        self._message_handlers[message_type] = handler

    def set_message_bus(self, message_bus: Callable):
        self._message_bus = message_bus

    async def _process_task_queue(self):
        while self._running:
            try:
                if self.is_busy:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    task = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                self._running_tasks.add(task.task_id)
                self.status = AgentStatus.BUSY

                task.status = "running"
                task.started_at = datetime.now()

                try:
                    result = await self.execute_task(task)
                    task.result = result
                    task.status = "completed"
                    task.completed_at = datetime.now()
                    self._statistics["tasks_completed"] += 1
                except Exception as e:
                    task.error = str(e)
                    task.status = "failed"
                    task.completed_at = datetime.now()
                    self._statistics["tasks_failed"] += 1
                    self._statistics["error_count"] += 1
                    self._logger.error(f"Task {task.task_id} failed: {e}")

                finally:
                    self._running_tasks.discard(task.task_id)

                    if len(self._running_tasks) < self.config.max_concurrent_tasks:
                        self.status = AgentStatus.READY

            except Exception as e:
                self._logger.error(f"Error in task queue processing: {e}")

    async def _send_heartbeat(self):
        while self._running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                self._last_heartbeat = datetime.now()

                heartbeat = AgentMessage(
                    message_id=str(uuid.uuid4()),
                    sender_id=self.agent_id,
                    recipient_id=None,
                    message_type=MessageType.HEARTBEAT,
                    content={
                        "status": self.status.value,
                        "uptime": self.uptime,
                        "running_tasks": len(self._running_tasks),
                        "statistics": self._statistics
                    }
                )

                if self._message_bus:
                    await self._message_bus(heartbeat)

            except Exception as e:
                self._logger.error(f"Error sending heartbeat: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        return {
            **self._statistics,
            "status": self.status.value,
            "uptime": self.uptime,
            "running_tasks": len(self._running_tasks),
            "queue_size": self._task_queue.qsize(),
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "capabilities": [c.to_dict() for c in self.capabilities.values()]
        }

    def get_message_history(self, limit: int = 50) -> List[AgentMessage]:
        return self._message_history[-limit:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "status": self.status.value,
            "capabilities": [c.to_dict() for c in self.capabilities.values()],
            "statistics": self.get_statistics()
        }
