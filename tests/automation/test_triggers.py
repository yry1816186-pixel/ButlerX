import pytest
import asyncio
from datetime import datetime, time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from butler.automation.trigger import (
    Trigger, TriggerConfig, TriggerType,
    StateTrigger, TimeTrigger, EventTrigger,
    NumericStateTrigger, TemplateTrigger, SunTrigger,
    MQTTTrigger, TriggerData
)


class TestTriggerConfig:
    def test_trigger_config_creation(self):
        config = TriggerConfig(
            enabled=True,
            debounce_seconds=0.5,
            cooldown_seconds=1.0
        )
        
        assert config.enabled is True
        assert config.debounce_seconds == 0.5
        assert config.cooldown_seconds == 1.0

    def test_trigger_config_default_values(self):
        config = TriggerConfig()
        
        assert config.enabled is True
        assert config.debounce_seconds == 0.0
        assert config.cooldown_seconds == 0.0


class TestStateTrigger:
    @pytest.mark.asyncio
    async def test_state_trigger_creation(self):
        trigger = StateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            from_state="20",
            to_state="25"
        )
        
        assert trigger.trigger_id == "trigger_001"
        assert trigger.entity_id == "sensor.temperature"
        assert trigger.from_state == "20"
        assert trigger.to_state == "25"

    @pytest.mark.asyncio
    async def test_state_trigger_check(self):
        trigger = StateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            from_state="20",
            to_state="25"
        )
        
        context = {
            "entity_id": "sensor.temperature",
            "old_state": {"state": "20"},
            "new_state": {"state": "25"}
        }
        
        result = await trigger.check(context)
        assert result is True

    @pytest.mark.asyncio
    async def test_state_trigger_callback(self):
        callback_called = []
        
        async def callback(trigger_data):
            callback_called.append(trigger_data)
        
        trigger = StateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            from_state="20",
            to_state="25"
        )
        trigger.add_callback(callback)
        
        context = {
            "entity_id": "sensor.temperature",
            "old_state": {"state": "20"},
            "new_state": {"state": "25"}
        }
        
        await trigger.trigger(context)
        
        assert len(callback_called) == 1


class TestTimeTrigger:
    @pytest.mark.asyncio
    async def test_time_trigger_creation(self):
        trigger = TimeTrigger(
            trigger_id="trigger_001",
            trigger_time=time(8, 0)
        )
        
        assert trigger.trigger_id == "trigger_001"
        assert trigger.trigger_time == time(8, 0)

    @pytest.mark.asyncio
    async def test_time_trigger_check(self):
        trigger = TimeTrigger(
            trigger_id="trigger_001",
            trigger_time=time(8, 0)
        )
        
        now = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        context = {"now": now}
        
        result = await trigger.check(context)
        assert result is True


class TestEventTrigger:
    @pytest.mark.asyncio
    async def test_event_trigger_creation(self):
        trigger = EventTrigger(
            trigger_id="trigger_001",
            event_type="custom_event"
        )
        
        assert trigger.trigger_id == "trigger_001"
        assert trigger.event_type == "custom_event"

    @pytest.mark.asyncio
    async def test_event_trigger_check(self):
        trigger = EventTrigger(
            trigger_id="trigger_001",
            event_type="custom_event"
        )
        
        context = {
            "event_type": "custom_event",
            "event_data": {"key": "value"}
        }
        
        result = await trigger.check(context)
        assert result is True


class TestNumericStateTrigger:
    @pytest.mark.asyncio
    async def test_numeric_state_trigger_creation(self):
        trigger = NumericStateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            above=25.0
        )
        
        assert trigger.trigger_id == "trigger_001"
        assert trigger.entity_id == "sensor.temperature"
        assert trigger.above == 25.0

    @pytest.mark.asyncio
    async def test_numeric_state_trigger_check_above(self):
        trigger = NumericStateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            above=25.0
        )
        
        context = {
            "entity_id": "sensor.temperature",
            "new_state": {"state": "26.5"}
        }
        
        result = await trigger.check(context)
        assert result is True

    @pytest.mark.asyncio
    async def test_numeric_state_trigger_check_below(self):
        trigger = NumericStateTrigger(
            trigger_id="trigger_001",
            entity_id="sensor.temperature",
            below=20.0
        )
        
        context = {
            "entity_id": "sensor.temperature",
            "new_state": {"state": "18.5"}
        }
        
        result = await trigger.check(context)
        assert result is True


class TestTemplateTrigger:
    @pytest.mark.asyncio
    async def test_template_trigger_creation(self):
        trigger = TemplateTrigger(
            trigger_id="trigger_001",
            template="{{ states('sensor.temperature') > 25 }}"
        )
        
        assert trigger.trigger_id == "trigger_001"
        assert trigger.template == "{{ states('sensor.temperature') > 25 }}"

    @pytest.mark.asyncio
    async def test_template_trigger_check(self):
        trigger = TemplateTrigger(
            trigger_id="trigger_001",
            template="{{ value > 25 }}"
        )
        
        context = {
            "value": 26.0
        }
        
        result = await trigger.check(context)
        assert result is True


class TestSunTrigger:
    @pytest.mark.asyncio
    async def test_sun_trigger_creation(self):
        trigger = SunTrigger(
            trigger_id="trigger_001",
            event="sunset"
        )
        
        assert trigger.trigger_id == "trigger_001"
        assert trigger.event == "sunset"

    @pytest.mark.asyncio
    async def test_sun_trigger_with_offset(self):
        trigger = SunTrigger(
            trigger_id="trigger_001",
            event="sunset",
            offset_minutes=-30
        )
        
        assert trigger.offset_minutes == -30


class TestMQTTTrigger:
    @pytest.mark.asyncio
    async def test_mqtt_trigger_creation(self):
        trigger = MQTTTrigger(
            trigger_id="trigger_001",
            topic="home/sensor/temperature"
        )
        
        assert trigger.trigger_id == "trigger_001"
        assert trigger.topic == "home/sensor/temperature"

    @pytest.mark.asyncio
    async def test_mqtt_trigger_with_payload(self):
        trigger = MQTTTrigger(
            trigger_id="trigger_001",
            topic="home/sensor/temperature",
            payload="25"
        )
        
        assert trigger.payload == "25"

    @pytest.mark.asyncio
    async def test_mqtt_trigger_check(self):
        trigger = MQTTTrigger(
            trigger_id="trigger_001",
            topic="home/sensor/temperature",
            payload="25"
        )
        
        context = {
            "topic": "home/sensor/temperature",
            "payload": "25"
        }
        
        result = await trigger.check(context)
        assert result is True


class TestTriggerData:
    def test_trigger_data_creation(self):
        data = TriggerData(
            trigger_id="trigger_001",
            trigger_type=TriggerType.STATE,
            timestamp=datetime.now(),
            context={"key": "value"}
        )
        
        assert data.trigger_id == "trigger_001"
        assert data.trigger_type == TriggerType.STATE
        assert data.context == {"key": "value"}

    def test_trigger_data_to_dict(self):
        data = TriggerData(
            trigger_id="trigger_001",
            trigger_type=TriggerType.STATE,
            timestamp=datetime.now(),
            context={"key": "value"}
        )
        
        data_dict = data.to_dict()
        assert data_dict["trigger_id"] == "trigger_001"
        assert data_dict["trigger_type"] == "STATE"
