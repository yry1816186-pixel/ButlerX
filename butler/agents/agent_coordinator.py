from __future__ import annotations
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random

from .agent import Agent, AgentMessage, AgentTask, AgentStatus, AgentPriority, MessageType
from .agent_registry import AgentRegistry

logger = logging.getLogger(__name__)

class CoordinationStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    PRIORITY_BASED = "priority_based"
    CAPABILITY_MATCH = "capability_match"
    RANDOM = "random"

class LoadBalancingStrategy(Enum):
    DYNAMIC = "dynamic"
    STATIC = "static"
    ADAPTIVE = "adaptive"

@dataclass
class CoordinationRule:
    rule_id: str
    name: str
    description: str
    agent_types: List[str]
    required_capabilities: List[str]
    max_concurrent_tasks: int = 1
    priority: int = 0
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "agent_types": self.agent_types,
            "required_capabilities": self.required_capabilities,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "priority": self.priority,
            "enabled": self.enabled
        }

@dataclass
class CoordinationTask:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    required_capabilities: List[str]
    priority: AgentPriority = AgentPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None
    status: str = "pending"
    retries: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "required_capabilities": self.required_capabilities,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "retries": self.retries,
            "max_retries": self.max_retries
        }

@dataclass
class AgentLoad:
    agent_id: str
    running_tasks: int
    queue_size: int
    cpu_usage: float
    memory_usage: float
    success_rate: float
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "running_tasks": self.running_tasks,
            "queue_size": self.queue_size,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "success_rate": self.success_rate,
            "last_updated": self.last_updated.isoformat()
        }

@dataclass
class CoordinationMetrics:
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    retried_tasks: int = 0
    average_response_time: float = 0.0
    tasks_by_agent: Dict[str, int] = field(default_factory=dict)
    tasks_by_type: Dict[str, int] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "retried_tasks": self.retried_tasks,
            "success_rate": self.successful_tasks / self.total_tasks if self.total_tasks > 0 else 0,
            "average_response_time": self.average_response_time,
            "tasks_by_agent": self.tasks_by_agent,
            "tasks_by_type": self.tasks_by_type,
            "uptime_seconds": uptime
        }

class AgentCoordinator:
    def __init__(self, registry: AgentRegistry):
        self._registry = registry
        self._coordination_strategy = CoordinationStrategy.LEAST_LOADED
        self._load_balancing_strategy = LoadBalancingStrategy.DYNAMIC
        self._rules: List[CoordinationRule] = []
        self._pending_tasks: Dict[str, CoordinationTask] = {}
        self._active_tasks: Dict[str, CoordinationTask] = {}
        self._agent_loads: Dict[str, AgentLoad] = {}
        self._metrics = CoordinationMetrics()
        self._round_robin_index = 0
        self._running = False
        self._coordination_interval = 1.0
        self._task_timeout = 300.0
        self._listeners: List[Callable] = []
        self._logger = logging.getLogger("butler.coordinator")

    async def start(self):
        if self._running:
            return

        self._running = True
        self._metrics.start_time = datetime.now()

        asyncio.create_task(self._coordination_loop())
        self._logger.info("Agent coordinator started")

    async def stop(self):
        if not self._running:
            return

        self._running = False
        self._logger.info("Agent coordinator stopped")

    def set_coordination_strategy(self, strategy: CoordinationStrategy):
        self._coordination_strategy = strategy
        self._logger.info(f"Coordination strategy changed to {strategy.value}")

    def set_load_balancing_strategy(self, strategy: LoadBalancingStrategy):
        self._load_balancing_strategy = strategy
        self._logger.info(f"Load balancing strategy changed to {strategy.value}")

    def add_rule(self, rule: CoordinationRule):
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, rule_id: str) -> bool:
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                del self._rules[i]
                return True
        return False

    def get_rules(self) -> List[CoordinationRule]:
        return self._rules.copy()

    async def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        required_capabilities: List[str],
        priority: AgentPriority = AgentPriority.NORMAL,
        deadline: Optional[datetime] = None
    ) -> str:
        import uuid

        task = CoordinationTask(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            payload=payload,
            required_capabilities=required_capabilities,
            priority=priority,
            deadline=deadline
        )

        self._pending_tasks[task.task_id] = task
        self._metrics.total_tasks += 1

        if task_type not in self._metrics.tasks_by_type:
            self._metrics.tasks_by_type[task_type] = 0
        self._metrics.tasks_by_type[task_type] += 1

        self._notify_listeners("task_submitted", task)
        self._logger.info(f"Task {task.task_id} submitted: {task_type}")

        return task.task_id

    async def cancel_task(self, task_id: str) -> bool:
        if task_id in self._pending_tasks:
            del self._pending_tasks[task_id]
            self._notify_listeners("task_cancelled", {"task_id": task_id})
            return True
        elif task_id in self._active_tasks:
            task = self._active_tasks[task_id]
            if task.assigned_to:
                agent = self._registry.get(task.assigned_to)
                if agent:
                    self._logger.warning(f"Cancelling task on agent {task.assigned_to}")
            del self._active_tasks[task_id]
            return True
        return False

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        if task_id in self._pending_tasks:
            return self._pending_tasks[task_id].to_dict()
        elif task_id in self._active_tasks:
            return self._active_tasks[task_id].to_dict()
        return None

    async def _coordination_loop(self):
        while self._running:
            try:
                await self._assign_pending_tasks()
                await self._update_agent_loads()
                await self._check_task_timeouts()
                await self._balance_load()
            except Exception as e:
                self._logger.error(f"Error in coordination loop: {e}")

            await asyncio.sleep(self._coordination_interval)

    async def _assign_pending_tasks(self):
        pending = list(self._pending_tasks.values())
        pending.sort(key=lambda t: t.priority.value, reverse=True)

        for task in pending:
            if task.task_id not in self._pending_tasks:
                continue

            if task.deadline and datetime.now() > task.deadline:
                del self._pending_tasks[task.task_id]
                self._metrics.failed_tasks += 1
                self._logger.warning(f"Task {task.task_id} exceeded deadline")
                continue

            agent = await self._select_agent_for_task(task)
            if agent:
                await self._assign_task_to_agent(task, agent)

    async def _select_agent_for_task(self, task: CoordinationTask) -> Optional[Agent]:
        ready_agents = self._registry.get_ready_agents()
        if not ready_agents:
            return None

        for rule in self._rules:
            if not rule.enabled:
                continue

            if any(cap not in task.required_capabilities for cap in rule.required_capabilities):
                continue

            matching_agents = [
                agent for agent in ready_agents
                if agent.agent_type in rule.agent_types
                and all(agent.has_capability(cap) for cap in task.required_capabilities)
            ]

            if matching_agents:
                return self._select_from_candidates(task, matching_agents)

        capable_agents = [
            agent for agent in ready_agents
            if all(agent.has_capability(cap) for cap in task.required_capabilities)
        ]

        if capable_agents:
            return self._select_from_candidates(task, capable_agents)

        return None

    async def _select_from_candidates(self, task: CoordinationTask, candidates: List[Agent]) -> Optional[Agent]:
        if not candidates:
            return None

        if self._coordination_strategy == CoordinationStrategy.ROUND_ROBIN:
            return self._round_robin_select(candidates)

        elif self._coordination_strategy == CoordinationStrategy.LEAST_LOADED:
            return min(candidates, key=lambda a: len(a._running_tasks))

        elif self._coordination_strategy == CoordinationStrategy.PRIORITY_BASED:
            return max(candidates, key=lambda a: a.config.max_concurrent_tasks)

        elif self._coordination_strategy == CoordinationStrategy.CAPABILITY_MATCH:
            return max(
                candidates,
                key=lambda a: sum(1 for cap in task.required_capabilities if a.has_capability(cap))
            )

        elif self._coordination_strategy == CoordinationStrategy.RANDOM:
            return random.choice(candidates)

        return candidates[0]

    def _round_robin_select(self, candidates: List[Agent]) -> Agent:
        agent = candidates[self._round_robin_index % len(candidates)]
        self._round_robin_index += 1
        return agent

    async def _assign_task_to_agent(self, task: CoordinationTask, agent: Agent):
        try:
            task_id = await agent.submit_task(task.task_type, task.payload, task.priority)

            task.assigned_to = agent.agent_id
            task.status = "assigned"

            self._active_tasks[task.task_id] = task
            del self._pending_tasks[task.task_id]

            if agent.agent_id not in self._metrics.tasks_by_agent:
                self._metrics.tasks_by_agent[agent.agent_id] = 0
            self._metrics.tasks_by_agent[agent.agent_id] += 1

            self._notify_listeners("task_assigned", {"task": task.to_dict(), "agent_id": agent.agent_id})
            self._logger.info(f"Task {task.task_id} assigned to {agent.agent_id}")

        except Exception as e:
            self._logger.error(f"Failed to assign task to agent: {e}")
            task.retries += 1
            if task.retries >= task.max_retries:
                del self._pending_tasks[task.task_id]
                self._metrics.failed_tasks += 1

    async def _update_agent_loads(self):
        agents = self._registry.get_all()

        for agent in agents:
            stats = agent.get_statistics()
            load = AgentLoad(
                agent_id=agent.agent_id,
                running_tasks=len(agent._running_tasks),
                queue_size=stats.get("queue_size", 0),
                cpu_usage=0.0,
                memory_usage=0.0,
                success_rate=stats.get("success_rate", 1.0)
            )
            self._agent_loads[agent.agent_id] = load

    async def _check_task_timeouts(self):
        now = datetime.now()

        for task_id, task in list(self._active_tasks.items()):
            elapsed = (now - task.created_at).total_seconds()

            if elapsed > self._task_timeout:
                self._logger.warning(f"Task {task_id} timed out after {elapsed}s")
                await self._retry_task(task)

    async def _retry_task(self, task: CoordinationTask):
        if task.retries >= task.max_retries:
            del self._active_tasks[task.task_id]
            self._metrics.failed_tasks += 1
            self._logger.error(f"Task {task.task_id} failed after {task.retries} retries")
            return

        task.retries += 1
        task.assigned_to = None
        task.status = "pending"

        self._pending_tasks[task.task_id] = task
        del self._active_tasks[task.task_id]

        self._metrics.retried_tasks += 1
        self._logger.info(f"Retrying task {task.task_id} (attempt {task.retries + 1})")

    async def _balance_load(self):
        if self._load_balancing_strategy == LoadBalancingStrategy.STATIC:
            return

        agent_loads = list(self._agent_loads.values())
        if not agent_loads:
            return

        avg_load = sum(a.running_tasks for a in agent_loads) / len(agent_loads)

        overloaded = [a for a in agent_loads if a.running_tasks > avg_load * 1.5]
        underloaded = [a for a in agent_loads if a.running_tasks < avg_load * 0.5]

        if overloaded and underloaded:
            self._logger.debug(f"Load imbalance detected: {len(overloaded)} overloaded, {len(underloaded)} underloaded")

    async def handle_task_completion(self, task_id: str, success: bool):
        if task_id in self._active_tasks:
            task = self._active_tasks[task_id]

            if success:
                self._metrics.successful_tasks += 1
                task.status = "completed"
            else:
                self._metrics.failed_tasks += 1
                await self._retry_task(task)
                return

            del self._active_tasks[task_id]
            self._notify_listeners("task_completed", {"task_id": task_id, "success": success})

    def get_metrics(self) -> CoordinationMetrics:
        return self._metrics

    def get_agent_loads(self) -> Dict[str, AgentLoad]:
        return self._agent_loads.copy()

    def get_pending_tasks(self) -> List[CoordinationTask]:
        return list(self._pending_tasks.values())

    def get_active_tasks(self) -> List[CoordinationTask]:
        return list(self._active_tasks.values())

    def register_listener(self, listener: Callable):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: Callable):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, event_type: str, data: Any):
        for listener in self._listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                self._logger.error(f"Listener error: {e}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coordination_strategy": self._coordination_strategy.value,
            "load_balancing_strategy": self._load_balancing_strategy.value,
            "rules": [r.to_dict() for r in self._rules],
            "pending_tasks": len(self._pending_tasks),
            "active_tasks": len(self._active_tasks),
            "metrics": self._metrics.to_dict(),
            "agent_loads": {k: v.to_dict() for k, v in self._agent_loads.items()},
            "running": self._running
        }
