import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
import os
import tempfile

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def sample_device_data():
    return {
        "device_id": "test_device_001",
        "name": "Test Device",
        "device_type": "sensor",
        "domain": "environment",
        "location": "living_room",
        "manufacturer": "Test Manufacturer",
        "model": "Test Model",
        "version": "1.0.0"
    }

@pytest.fixture
def sample_sensor_data():
    return {
        "sensor_id": "test_sensor_001",
        "name": "Test Sensor",
        "sensor_type": "temperature",
        "domain": "environment",
        "location": "living_room",
        "unit": "°C",
        "value": 23.5
    }

@pytest.fixture
def sample_user_data():
    return {
        "user_id": "user_001",
        "name": "Test User",
        "email": "test@example.com",
        "role": "admin"
    }

@pytest.fixture
def sample_service_data():
    return {
        "service_id": "service_001",
        "name": "Test Service",
        "domain": "control",
        "description": "A test service"
    }

@pytest.fixture
def sample_location_data():
    return {
        "location_id": "loc_001",
        "name": "Living Room",
        "type": "room",
        "floor": 1
    }

@pytest.fixture
def sample_automation_data():
    return {
        "automation_id": "auto_001",
        "name": "Test Automation",
        "description": "A test automation",
        "enabled": True
    }

@pytest.fixture
def sample_scenario_data():
    return {
        "scenario_id": "scenario_001",
        "name": "Test Scenario",
        "scenario_type": "time_based"
    }

@pytest.fixture
def sample_context():
    return {
        "timestamp": datetime.now().isoformat(),
        "user_id": "user_001",
        "location": "living_room",
        "device_id": "device_001"
    }

@pytest.fixture
def mock_config():
    return {
        "max_retries": 3,
        "timeout": 30.0,
        "debug": True,
        "log_level": "INFO"
    }

@pytest.fixture
def sample_trigger_data():
    return {
        "trigger_type": "state",
        "entity_id": "sensor.temperature",
        "from_state": None,
        "to_state": "25"
    }

@pytest.fixture
def sample_condition_data():
    return {
        "condition_type": "state",
        "entity_id": "sensor.temperature",
        "state": "25"
    }

@pytest.fixture
def sample_action_data():
    return {
        "action_type": "service",
        "service": "light.turn_on",
        "entity_id": "light.living_room"
    }

@pytest.fixture
def sample_agent_message():
    return {
        "message_id": "msg_001",
        "sender_id": "agent_001",
        "receiver_id": "agent_002",
        "message_type": "request",
        "content": {"action": "test"},
        "timestamp": datetime.now()
    }

@pytest.fixture
def sample_agent_task():
    return {
        "task_id": "task_001",
        "task_type": "analysis",
        "priority": 5,
        "parameters": {"input": "test"},
        "deadline": datetime.now() + timedelta(minutes=10)
    }

@pytest.fixture
def sample_memory_data():
    return {
        "memory_id": "mem_001",
        "content": "Test memory content",
        "importance": 5,
        "tags": ["test", "memory"]
    }

@pytest.fixture
def sample_goal_data():
    return {
        "goal_id": "goal_001",
        "name": "Test Goal",
        "description": "A test goal",
        "priority": 5,
        "deadline": datetime.now() + timedelta(hours=1)
    }

@pytest.fixture
def sample_composite_goal_data():
    return {
        "goal_id": "composite_goal_001",
        "name": "Test Composite Goal",
        "description": "A test composite goal",
        "priority": 5,
        "execution_strategy": "sequential",
        "sub_goals": [
            {"goal_id": "sub_goal_001", "name": "Sub Goal 1"},
            {"goal_id": "sub_goal_002", "name": "Sub Goal 2"}
        ]
    }

@pytest.fixture
def sample_preference_data():
    return {
        "preference_id": "pref_001",
        "name": "Test Preference",
        "preference_type": "string",
        "category": "system",
        "default_value": "default",
        "value": "test_value"
    }

@pytest.fixture
def sample_user_profile_data():
    return {
        "user_id": "user_001",
        "name": "Test User",
        "role": "admin",
        "preferences": {},
        "behaviors": []
    }

@pytest.fixture
def sample_integration_config():
    return {
        "integration_id": "integration_001",
        "name": "Test Integration",
        "integration_type": "smart_home",
        "enabled": True,
        "config": {"host": "localhost", "port": 8080}
    }

@pytest.fixture
def sample_scenario_template():
    return {
        "template_id": "template_001",
        "name": "Test Template",
        "scenario_type": "time_based",
        "description": "A test scenario template"
    }

@pytest.fixture
def sample_camera_config():
    return {
        "camera_id": "camera_001",
        "name": "Test Camera",
        "resolution": (1920, 1080),
        "fps": 30,
        "power_mode": "balanced",
        "motion_threshold": 0.3
    }

@pytest.fixture
def sample_log_entry():
    return {
        "timestamp": datetime.now(),
        "level": "INFO",
        "category": "system",
        "message": "Test log message",
        "context": {"key": "value"}
    }

@pytest.fixture
def sample_metric_data():
    return {
        "name": "test_metric",
        "value": 100,
        "labels": {"source": "test"},
        "timestamp": datetime.now()
    }

@pytest.fixture
def sample_ptz_config():
    return {
        "min_pan": 0.0,
        "max_pan": 180.0,
        "min_tilt": 0.0,
        "max_tilt": 180.0,
        "min_zoom": 1.0,
        "max_zoom": 5.0
    }

@pytest.fixture
def sample_expression_preset():
    return {
        "preset_id": "preset_001",
        "name": "Test Expression",
        "mood": "happy",
        "expression_id": 0x05
    }

@pytest.fixture
def sample_device_discovery_data():
    return {
        "protocol": "mdns",
        "service_type": "_http._tcp.local",
        "scan_timeout": 5.0
    }
