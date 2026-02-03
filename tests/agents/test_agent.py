import pytest
import asyncio
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from butler.agents.agent import (
    Agent, AgentConfig, AgentMessage, AgentTask, AgentCapability,
    AgentStatus, MessageType, TaskStatus
)


class TestAgentConfig:
    def test_agent_config_creation(self):
        config = AgentConfig(
            agent_id="test_agent_001",
            name="Test Agent",
            agent_type="test",
            enabled=True,
            heartbeat_interval=30.0
        )

        assert config.name == "Test Agent"
        assert config.agent_type == "test"
        assert config.enabled is True
        assert config.heartbeat_interval == 30.0


class TestAgentMessage:
    def test_message_creation(self):
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            recipient_id="agent_002",
            message_type=MessageType.REQUEST,
            content={"action": "test"},
            timestamp=datetime.now()
        )

        assert message.message_id == "msg_001"
        assert message.sender_id == "agent_001"
        assert message.recipient_id == "agent_002"
        assert message.message_type == MessageType.REQUEST

    def test_message_to_dict(self):
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.REQUEST,
            content={"action": "test"}
        )
        
        data = message.to_dict()
        assert data["message_id"] == "msg_001"
        assert data["message_type"] == "REQUEST"

    def test_message_reply(self):
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.REQUEST,
            content={"action": "test"}
        )
        
        reply = message.create_reply({"result": "success"})
        assert reply.message_id != message.message_id
        assert reply.sender_id == "agent_002"
        assert reply.receiver_id == "agent_001"
        assert reply.reply_to == message.message_id


class TestAgentTask:
    def test_task_creation(self):
        task = AgentTask(
            task_id="task_001",
            task_type="analysis",
            priority=5,
            parameters={"input": "test"},
            deadline=datetime.now() + timedelta(minutes=10)
        )
        
        assert task.task_id == "task_001"
        assert task.task_type == "analysis"
        assert task.priority == 5

    def test_task_status(self):
        task = AgentTask(
            task_id="task_001",
            task_type="analysis"
        )
        
        assert task.status == TaskStatus.PENDING
        task.start()
        assert task.status == TaskStatus.IN_PROGRESS
        task.complete({"result": "done"})
        assert task.status == TaskStatus.COMPLETED

    def test_task_timeout(self):
        task = AgentTask(
            task_id="task_001",
            task_type="analysis",
            deadline=datetime.now() + timedelta(seconds=-1)
        )
        
        assert task.is_timeout() is True

    def test_task_to_dict(self):
        task = AgentTask(
            task_id="task_001",
            task_type="analysis",
            priority=5
        )
        
        data = task.to_dict()
        assert data["task_id"] == "task_001"
        assert data["status"] == "PENDING"


class TestAgentCapability:
    def test_capability_creation(self):
        capability = AgentCapability(
            capability_id="cap_001",
            name="dialogue",
            description="Natural language dialogue processing",
            parameters={"model": "gpt-4"}
        )
        
        assert capability.capability_id == "cap_001"
        assert capability.name == "dialogue"
        assert capability.description == "Natural language dialogue processing"

    def test_capability_to_dict(self):
        capability = AgentCapability(
            capability_id="cap_001",
            name="dialogue",
            description="Natural language dialogue processing"
        )
        
        data = capability.to_dict()
        assert data["capability_id"] == "cap_001"
        assert data["name"] == "dialogue"


class TestMockAgent(Agent):
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def process_message(self, message: AgentMessage) -> AgentMessage:
        return message.create_reply({"status": "processed"})
    
    async def execute_task(self, task: AgentTask) -> any:
        task.complete({"result": "done"})
        return {"result": "done"}


@pytest.mark.asyncio
class TestAgent:
    @pytest.fixture
    def agent(self):
        config = AgentConfig(
            name="Test Agent",
            agent_type="test",
            enabled=True
        )
        return TestMockAgent(config)

    async def test_agent_creation(self, agent):
        assert agent.config.name == "Test Agent"
        assert agent.config.agent_type == "test"
        assert agent.status == AgentStatus.OFFLINE

    async def test_agent_initialization(self, agent):
        result = await agent.initialize()
        assert result is True
        assert agent.status == AgentStatus.IDLE

    async def test_agent_start_stop(self, agent):
        await agent.initialize()
        
        await agent.start()
        assert agent.status == AgentStatus.IDLE
        
        await agent.stop()
        assert agent.status == AgentStatus.STOPPED

    async def test_agent_send_message(self, agent):
        await agent.initialize()
        
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.REQUEST,
            content={"test": "data"}
        )
        
        await agent.send_message(message)
        
        assert len(agent.get_outgoing_messages()) == 1

    async def test_agent_receive_message(self, agent):
        await agent.initialize()
        
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id=agent.agent_id,
            message_type=MessageType.REQUEST,
            content={"test": "data"}
        )
        
        await agent.receive_message(message)
        
        assert len(agent.get_incoming_messages()) == 1

    async def test_agent_add_task(self, agent):
        await agent.initialize()
        
        task = AgentTask(
            task_id="task_001",
            task_type="analysis",
            priority=5
        )
        
        await agent.add_task(task)
        
        assert len(agent.get_pending_tasks()) == 1

    async def test_agent_execute_task(self, agent):
        await agent.initialize()
        
        task = AgentTask(
            task_id="task_001",
            task_type="analysis",
            priority=5
        )
        
        await agent.add_task(task)
        await agent.process_tasks()
        
        assert task.status == TaskStatus.COMPLETED

    async def test_agent_add_capability(self, agent):
        await agent.initialize()
        
        capability = AgentCapability(
            capability_id="cap_001",
            name="dialogue",
            description="Natural language dialogue processing"
        )
        
        agent.add_capability(capability)
        
        assert "dialogue" in agent.get_capabilities()

    async def test_agent_get_statistics(self, agent):
        await agent.initialize()
        
        stats = agent.get_statistics()
        
        assert stats["agent_id"] == agent.agent_id
        assert stats["name"] == agent.config.name
        assert stats["status"] == agent.status.value

    async def test_agent_heartbeat(self, agent):
        await agent.initialize()
        
        assert agent.get_last_heartbeat() is None
        
        agent.update_heartbeat()
        
        assert agent.get_last_heartbeat() is not None
        assert agent.is_heartbeat_timeout(timeout_seconds=60) is False

    async def test_agent_reset_statistics(self, agent):
        await agent.initialize()
        
        stats = agent.get_statistics()
        assert "total_messages_sent" in stats
        assert "total_messages_received" in stats
        
        agent.reset_statistics()
        
        stats = agent.get_statistics()
        assert stats["total_messages_sent"] == 0
        assert stats["total_messages_received"] == 0


class TestAgentStatus:
    def test_status_values(self):
        assert AgentStatus.OFFLINE.value == "offline"
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.BUSY.value == "busy"
        assert AgentStatus.STOPPED.value == "stopped"


class TestMessageType:
    def test_type_values(self):
        assert MessageType.REQUEST.value == "request"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.NOTIFICATION.value == "notification"
        assert MessageType.ERROR.value == "error"


class TestTaskStatus:
    def test_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
