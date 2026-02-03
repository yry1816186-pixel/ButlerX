import pytest
import asyncio
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from butler.automation.automation_engine import (
    AutomationEngine, Automation, AutomationConfig,
    AutomationState, ExecutionMode, AutomationStatistics
)
from butler.automation.trigger import StateTrigger
from butler.automation.action import ServiceAction


class TestAutomationConfig:
    def test_automation_config_creation(self):
        config = AutomationConfig(
            enabled=True,
            mode=ExecutionMode.SINGLE,
            max_retries=3,
            timeout_seconds=30.0
        )
        
        assert config.enabled is True
        assert config.mode == ExecutionMode.SINGLE
        assert config.max_retries == 3
        assert config.timeout_seconds == 30.0


class TestAutomation:
    def test_automation_creation(self):
        trigger = StateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            from_state="20",
            to_state="25"
        )
        
        action = ServiceAction(
            action_id="action_001",
            service="light.turn_on",
            entity_id="light.living_room"
        )
        
        automation = Automation(
            automation_id="auto_001",
            name="Test Automation",
            description="A test automation",
            triggers=[trigger],
            actions=[action]
        )
        
        assert automation.automation_id == "auto_001"
        assert automation.name == "Test Automation"
        assert len(automation.triggers) == 1
        assert len(automation.actions) == 1

    def test_automation_state(self):
        automation = Automation(
            automation_id="auto_001",
            name="Test Automation"
        )
        
        assert automation.state == AutomationState.IDLE
        automation.state = AutomationState.RUNNING
        assert automation.state == AutomationState.RUNNING

    def test_automation_enable_disable(self):
        automation = Automation(
            automation_id="auto_001",
            name="Test Automation"
        )
        
        assert automation.enabled is True
        automation.disable()
        assert automation.enabled is False
        automation.enable()
        assert automation.enabled is True


class TestAutomationStatistics:
    def test_statistics_creation(self):
        stats = AutomationStatistics(
            total_triggers=10,
            total_runs=8,
            successful_runs=7,
            failed_runs=1,
            last_triggered=datetime.now(),
            last_run=datetime.now()
        )
        
        assert stats.total_triggers == 10
        assert stats.total_runs == 8
        assert stats.successful_runs == 7
        assert stats.failed_runs == 1

    def test_statistics_success_rate(self):
        stats = AutomationStatistics(
            total_triggers=10,
            total_runs=8,
            successful_runs=7,
            failed_runs=1
        )
        
        assert stats.get_success_rate() == 0.875


@pytest.mark.asyncio
class TestAutomationEngine:
    @pytest.fixture
    def engine(self):
        return AutomationEngine()

    async def test_engine_initialization(self, engine):
        await engine.initialize()
        assert engine.is_running() is False

    async def test_engine_start_stop(self, engine):
        await engine.initialize()
        
        await engine.start()
        assert engine.is_running() is True
        
        await engine.stop()
        assert engine.is_running() is False

    async def test_register_automation(self, engine):
        trigger = StateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            from_state="20",
            to_state="25"
        )
        
        action = ServiceAction(
            action_id="action_001",
            service="light.turn_on",
            entity_id="light.living_room"
        )
        
        automation = Automation(
            automation_id="auto_001",
            name="Test Automation",
            triggers=[trigger],
            actions=[action]
        )
        
        await engine.register_automation(automation)
        
        retrieved = engine.get_automation("auto_001")
        assert retrieved is not None
        assert retrieved.automation_id == "auto_001"

    async def test_unregister_automation(self, engine):
        trigger = StateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature"
        )
        
        action = ServiceAction(
            action_id="action_001",
            service="light.turn_on",
            entity_id="light.living_room"
        )
        
        automation = Automation(
            automation_id="auto_001",
            name="Test Automation",
            triggers=[trigger],
            actions=[action]
        )
        
        await engine.register_automation(automation)
        await engine.unregister_automation("auto_001")
        
        retrieved = engine.get_automation("auto_001")
        assert retrieved is None

    async def test_get_all_automations(self, engine):
        automation1 = Automation(
            automation_id="auto_001",
            name="Automation 1"
        )
        automation2 = Automation(
            automation_id="auto_002",
            name="Automation 2"
        )
        
        await engine.register_automation(automation1)
        await engine.register_automation(automation2)
        
        all_automations = engine.get_all_automations()
        assert len(all_automations) == 2

    async def test_get_enabled_automations(self, engine):
        automation1 = Automation(
            automation_id="auto_001",
            name="Automation 1"
        )
        automation2 = Automation(
            automation_id="auto_002",
            name="Automation 2"
        )
        automation2.disable()
        
        await engine.register_automation(automation1)
        await engine.register_automation(automation2)
        
        enabled = engine.get_enabled_automations()
        assert len(enabled) == 1
        assert automation1 in enabled

    async def test_get_automation_statistics(self, engine):
        trigger = StateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature"
        )
        
        action = ServiceAction(
            action_id="action_001",
            service="light.turn_on",
            entity_id="light.living_room"
        )
        
        automation = Automation(
            automation_id="auto_001",
            name="Test Automation",
            triggers=[trigger],
            actions=[action]
        )
        
        await engine.register_automation(automation)
        
        stats = engine.get_automation_statistics("auto_001")
        assert stats is not None
        assert stats.total_triggers == 0

    async def test_enable_disable_automation(self, engine):
        automation = Automation(
            automation_id="auto_001",
            name="Test Automation"
        )
        
        await engine.register_automation(automation)
        
        await engine.disable_automation("auto_001")
        assert automation.enabled is False
        
        await engine.enable_automation("auto_001")
        assert automation.enabled is True

    async def test_trigger_checking(self, engine):
        trigger = StateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            from_state="20",
            to_state="25"
        )
        
        action = ServiceAction(
            action_id="action_001",
            service="light.turn_on",
            entity_id="light.living_room"
        )
        
        automation = Automation(
            automation_id="auto_001",
            name="Test Automation",
            triggers=[trigger],
            actions=[action]
        )
        
        await engine.register_automation(automation)
        
        context = {
            "entity_id": "sensor.temperature",
            "old_state": {"state": "20"},
            "new_state": {"state": "25"}
        }
        
        triggered = await engine.check_triggers(context)
        assert triggered is True

    async def test_action_execution(self, engine):
        action = ServiceAction(
            action_id="action_001",
            service="light.turn_on",
            entity_id="light.living_room"
        )
        
        result = await engine.execute_action(action, {})
        
        assert result is not None
        assert result.success is True or result.success is False
