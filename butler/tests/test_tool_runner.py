"""Tests for ToolRunner."""

import pytest
from unittest.mock import MagicMock, patch
from ..core.config import ButlerConfig
from ..core.tool_runner import ToolRunner
from ..core.models import ActionResult
from ..core.exceptions import ValidationError, ActionExecutionError


class TestToolRunnerInitialization:
    """Tests for ToolRunner initialization."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            vision_enabled=False,
            ha_mock=True,
            ha_url="http://localhost:8123",
        )

    @pytest.fixture
    def tool_runner(self, mock_config):
        """Create a ToolRunner instance."""
        db_mock = MagicMock()
        scheduler_mock = MagicMock()
        return ToolRunner(mock_config, scheduler_mock, db_mock)

    def test_initialization(self, tool_runner):
        """Test ToolRunner initialization."""
        assert tool_runner.config is not None
        assert tool_runner.ha is not None
        assert tool_runner.email is not None
        assert tool_runner.openclaw is not None
        assert tool_runner.device_hub is not None


class TestExecutePlan:
    """Tests for execute_plan method."""

    @pytest.fixture
    def mock_config(self):
        return ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            vision_enabled=False,
            ha_mock=True,
        )

    @pytest.fixture
    def tool_runner(self, mock_config):
        db_mock = MagicMock()
        scheduler_mock = MagicMock()
        return ToolRunner(mock_config, scheduler_mock, db_mock)

    def test_execute_empty_plan(self, tool_runner):
        """Test executing an empty plan."""
        results = tool_runner.execute_plan("plan-1", [], False)

        assert results == []

    def test_execute_single_action(self, tool_runner):
        """Test executing a plan with one action."""
        action = {
            "action_type": "notify",
            "params": {
                "title": "Test",
                "message": "Test message",
                "level": "info",
            },
        }

        results = tool_runner.execute_plan("plan-1", [action], False)

        assert len(results) == 1
        assert results[0].plan_id == "plan-1"
        assert results[0].action_type == "notify"

    def test_execute_multiple_actions(self, tool_runner):
        """Test executing a plan with multiple actions."""
        actions = [
            {
                "action_type": "notify",
                "params": {"title": "Test1", "message": "Msg1", "level": "info"},
            },
            {
                "action_type": "notify",
                "params": {"title": "Test2", "message": "Msg2", "level": "warning"},
            },
        ]

        results = tool_runner.execute_plan("plan-1", actions, False)

        assert len(results) == 2

    def test_privacy_mode_blocks_action(self, tool_runner):
        """Test privacy mode blocks camera actions."""
        action = {
            "action_type": "snapshot",
            "params": {},
        }

        results = tool_runner.execute_plan("plan-1", [action], True)

        assert len(results) == 1
        assert results[0].status == "error"
        assert "privacy_mode_blocked" in results[0].output


class TestActionExecution:
    """Tests for individual action execution."""

    @pytest.fixture
    def mock_config(self):
        return ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            vision_enabled=False,
            ha_mock=True,
        )

    @pytest.fixture
    def tool_runner(self, mock_config):
        db_mock = MagicMock()
        scheduler_mock = MagicMock()
        return ToolRunner(mock_config, scheduler_mock, db_mock)

    def test_notify_action_success(self, tool_runner):
        """Test successful notify action."""
        action = {
            "action_type": "notify",
            "params": {"title": "Test", "message": "Msg", "level": "info"},
        }

        result = tool_runner._execute_action("plan-1", action)

        assert result.status == "ok"

    def test_system_exec_validation_no_command(self, tool_runner):
        """Test system_exec validation without command."""
        action = {
            "action_type": "system_exec",
            "params": {"command": ""},
        }

        result = tool_runner._execute_action("plan-1", action)

        assert result.status == "error"
        assert "command" in result.output.get("details", {}).get("field", "")

    def test_email_send_validation_no_to(self, tool_runner):
        """Test email_send validation without 'to'."""
        action = {
            "action_type": "email_send",
            "params": {
                "subject": "Test",
                "body": "Test body",
                "to": [],
            },
        }

        result = tool_runner._execute_action("plan-1", action)

        assert result.status == "error"
        assert "to" in result.output.get("details", {}).get("field", "")

    def test_email_send_validation_no_subject(self, tool_runner):
        """Test email_send validation without subject."""
        action = {
            "action_type": "email_send",
            "params": {
                "to": ["test@example.com"],
                "subject": "",
                "body": "Test body",
            },
        }

        result = tool_runner._execute_action("plan-1", action)

        assert result.status == "error"
        assert "subject" in result.output.get("details", {}).get("field", "")

    def test_image_generate_validation_no_prompt(self, tool_runner):
        """Test image_generate validation without prompt."""
        action = {
            "action_type": "image_generate",
            "params": {"prompt": ""},
        }

        result = tool_runner._execute_action("plan-1", action)

        assert result.status == "error"
        assert "prompt" in result.output.get("details", {}).get("field", "")

    def test_device_turn_on_validation_no_device_id(self, tool_runner):
        """Test device_turn_on validation without device_id."""
        action = {
            "action_type": "device_turn_on",
            "params": {"device_id": ""},
        }

        result = tool_runner._execute_action("plan-1", action)

        assert result.status == "error"
        assert "device_id" in result.output.get("details", {}).get("field", "")

    def test_unsupported_action_type(self, tool_runner):
        """Test unsupported action type."""
        action = {
            "action_type": "unknown_action",
            "params": {},
        }

        result = tool_runner._execute_action("plan-1", action)

        assert result.status == "error"
        assert "Unsupported action_type" in result.output.get("error", "")


class TestPrivacyMode:
    """Tests for privacy mode blocking."""

    @pytest.fixture
    def mock_config(self):
        return ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            vision_enabled=False,
            privacy_block_store_kinds=["sensitive"],
            camera_action_types=["snapshot", "ptz_goto_preset"],
        )

    @pytest.fixture
    def tool_runner(self, mock_config):
        db_mock = MagicMock()
        scheduler_mock = MagicMock()
        return ToolRunner(mock_config, scheduler_mock, db_mock)

    def test_privacy_mode_blocks_camera_action(self, tool_runner):
        """Test privacy mode blocks camera action."""
        action = {
            "action_type": "snapshot",
            "params": {},
        }

        blocked = tool_runner._blocked_by_privacy(action, True)

        assert blocked is True

    def test_privacy_mode_allows_notify(self, tool_runner):
        """Test privacy mode allows notify action."""
        action = {
            "action_type": "notify",
            "params": {"title": "Test", "message": "Msg", "level": "info"},
        }

        blocked = tool_runner._blocked_by_privacy(action, True)

        assert blocked is False

    def test_privacy_disabled_allows_all(self, tool_runner):
        """Test disabled privacy mode allows all actions."""
        action = {
            "action_type": "snapshot",
            "params": {},
        }

        blocked = tool_runner._blocked_by_privacy(action, False)

        assert blocked is False

    def test_privacy_mode_blocks_sensitive_event(self, tool_runner):
        """Test privacy mode blocks sensitive event storage."""
        action = {
            "action_type": "store_event",
            "params": {"kind": "sensitive", "data": "test"},
        }

        blocked = tool_runner._blocked_by_privacy(action, True)

        assert blocked is True

    def test_privacy_mode_allows_normal_event(self, tool_runner):
        """Test privacy mode allows normal event storage."""
        action = {
            "action_type": "store_event",
            "params": {"kind": "normal", "data": "test"},
        }

        blocked = tool_runner._blocked_by_privacy(action, True)

        assert blocked is False
