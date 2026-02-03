from __future__ import annotations
import logging
from typing import Dict, List, Optional, Callable, Set
from datetime import datetime
import json

from .agent import Agent, AgentConfig, AgentMessage, AgentStatus, MessageType

logger = logging.getLogger(__name__)

class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._agent_types: Dict[str, Set[str]] = {}
        self._capabilities_index: Dict[str, Set[str]] = {}
        self._message_subscribers: Dict[str, List[str]] = {}
        self._registry_listeners: List[Callable] = []
        self._created_at = datetime.now()

    def register(self, agent: Agent) -> bool:
        if agent.agent_id in self._agents:
            logger.warning(f"Agent {agent.agent_id} already registered")
            return False

        self._agents[agent.agent_id] = agent

        if agent.agent_type not in self._agent_types:
            self._agent_types[agent.agent_type] = set()
        self._agent_types[agent.agent_type].add(agent.agent_id)

        for capability_name in agent.capabilities.keys():
            if capability_name not in self._capabilities_index:
                self._capabilities_index[capability_name] = set()
            self._capabilities_index[capability_name].add(agent.agent_id)

        self._notify_listeners("register", agent)
        logger.info(f"Agent {agent.agent_id} ({agent.name}) registered")
        return True

    def unregister(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]

        if agent.agent_type in self._agent_types:
            self._agent_types[agent.agent_type].discard(agent_id)

        for capability_name, agents_set in self._capabilities_index.items():
            agents_set.discard(agent_id)

        del self._agents[agent_id]

        self._notify_listeners("unregister", agent)
        logger.info(f"Agent {agent_id} unregistered")
        return True

    def get(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    def get_by_type(self, agent_type: str) -> List[Agent]:
        agent_ids = self._agent_types.get(agent_type, set())
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_by_capability(self, capability_name: str) -> List[Agent]:
        agent_ids = self._capabilities_index.get(capability_name, set())
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_all(self) -> List[Agent]:
        return list(self._agents.values())

    def get_ready_agents(self) -> List[Agent]:
        return [agent for agent in self._agents.values() if agent.is_ready]

    def get_busy_agents(self) -> List[Agent]:
        return [agent for agent in self._agents.values() if agent.is_busy]

    def find_best_agent_for_task(
        self,
        required_capabilities: List[str],
        exclude_agent_ids: Optional[List[str]] = None
    ) -> Optional[Agent]:
        exclude_set = set(exclude_agent_ids or [])

        for capability in required_capabilities:
            capable_agents = [
                agent for agent in self.get_by_capability(capability)
                if agent.is_ready and agent.agent_id not in exclude_set
            ]

            if capable_agents:
                return min(
                    capable_agents,
                    key=lambda a: len(a._running_tasks)
                )

        return None

    def get_statistics(self) -> Dict[str, Any]:
        agents = self.get_all()
        ready_count = sum(1 for a in agents if a.is_ready)
        busy_count = sum(1 for a in agents if a.is_busy)
        error_count = sum(1 for a in agents if a.status == AgentStatus.ERROR)

        by_type = {}
        for agent_type, agent_ids in self._agent_types.items():
            by_type[agent_type] = len(agent_ids)

        total_tasks_completed = sum(a._statistics.get("tasks_completed", 0) for a in agents)
        total_tasks_failed = sum(a._statistics.get("tasks_failed", 0) for a in agents)

        return {
            "total_agents": len(agents),
            "ready_agents": ready_count,
            "busy_agents": busy_count,
            "error_agents": error_count,
            "by_type": by_type,
            "total_tasks_completed": total_tasks_completed,
            "total_tasks_failed": total_tasks_failed,
            "total_capabilities": len(self._capabilities_index)
        }

    async def broadcast_message(self, message: AgentMessage, sender_id: str):
        recipients = []

        if message.recipient_id:
            target_agent = self.get(message.recipient_id)
            if target_agent and target_agent.agent_id != sender_id:
                recipients.append(target_agent)
        else:
            for agent in self._agents.values():
                if agent.agent_id != sender_id:
                    recipients.append(agent)

        for recipient in recipients:
            try:
                await recipient.receive_message(message)
            except Exception as e:
                logger.error(f"Failed to deliver message to {recipient.agent_id}: {e}")

    async def route_message(self, message: AgentMessage):
        if message.recipient_id:
            target_agent = self.get(message.recipient_id)
            if target_agent:
                await target_agent.receive_message(message)
            else:
                logger.warning(f"Unknown recipient: {message.recipient_id}")
        else:
            await self.broadcast_message(message, message.sender_id)

    def register_change_listener(self, listener: Callable):
        if listener not in self._registry_listeners:
            self._registry_listeners.append(listener)

    def unregister_change_listener(self, listener: Callable):
        if listener in self._registry_listeners:
            self._registry_listeners.remove(listener)

    def _notify_listeners(self, action: str, agent: Agent):
        for listener in self._registry_listeners:
            try:
                listener(action, agent)
            except Exception as e:
                logger.error(f"Registry listener error: {e}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agents": [agent.to_dict() for agent in self._agents.values()],
            "statistics": self.get_statistics(),
            "created_at": self._created_at.isoformat()
        }

    def export_registry(self, filepath: str):
        data = {
            "agents": [agent.to_dict() for agent in self._agents.values()],
            "statistics": self.get_statistics()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def clear_registry(self):
        self._agents.clear()
        self._agent_types.clear()
        self._capabilities_index.clear()
        logger.info("Registry cleared")
