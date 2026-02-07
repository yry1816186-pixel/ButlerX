"""Pytest configuration and fixtures."""

import os
import tempfile
import pytest
from pathlib import Path

from ..core.config import ButlerConfig
from ..core.db import Database


@pytest.fixture
def temp_db_path():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return ButlerConfig(
        mqtt_host="localhost",
        mqtt_port=1883,
        llm_api_url="https://api.example.com",
        llm_api_key="test_key",
        llm_model="test-model",
        vision_enabled=False,
        system_exec_allowlist=["echo", "cat"],
        script_allowlist=["test.py"],
    )


@pytest.fixture
def test_database(temp_db_path):
    """Create a test database."""
    db = Database(temp_db_path)
    db.init_schema()
    yield db
    db.close()


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.chat.return_value = ("{}")
    return mock


@pytest.fixture
def sample_event():
    """Create a sample event."""
    return {
        "id": "test-event-1",
        "ts": 1234567890.0,
        "type": "test",
        "source": "test",
        "payload": '{"test": "data"}',
    }


@pytest.fixture
def sample_action():
    """Create a sample action."""
    return {
        "action_type": "notify",
        "params": {
            "title": "Test",
            "message": "Test message",
            "level": "info",
        },
    }
