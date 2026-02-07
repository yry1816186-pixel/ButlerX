"""Tests for sandbox and resource limiting."""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch
from ..core.sandbox import (
    SandboxType,
    ResourceLimits,
    SandboxResult,
    SandboxManager,
    create_safe_limits,
    validate_command_safety,
)


class TestResourceLimits:
    """Tests for ResourceLimits."""

    def test_default_limits(self):
        """Test creating default resource limits."""
        limits = ResourceLimits()
        assert limits.timeout_sec == 30.0
        assert limits.max_memory_mb is None
        assert limits.allowed_network is True

    def test_custom_limits(self):
        """Test creating custom resource limits."""
        limits = ResourceLimits(
            timeout_sec=60.0,
            max_memory_mb=512,
            max_cpu_percent=50,
        )
        assert limits.timeout_sec == 60.0
        assert limits.max_memory_mb == 512
        assert limits.max_cpu_percent == 50

    def test_network_disabled(self):
        """Test disabling network access."""
        limits = ResourceLimits(allowed_network=False)
        assert limits.allowed_network is False


class TestSandboxResult:
    """Tests for SandboxResult."""

    def test_success_result(self):
        """Test creating a success result."""
        result = SandboxResult(
            success=True,
            exit_code=0,
            stdout="output",
            stderr="",
            execution_time_sec=1.5,
        )
        assert result.success is True
        assert result.exit_code == 0
        assert result.timed_out is False

    def test_failure_result(self):
        """Test creating a failure result."""
        result = SandboxResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="error",
            execution_time_sec=2.0,
        )
        assert result.success is False
        assert result.exit_code == 1

    def test_timeout_result(self):
        """Test creating a timeout result."""
        result = SandboxResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr="timeout",
            execution_time_sec=5.0,
            timed_out=True,
        )
        assert result.success is False
        assert result.timed_out is True


class TestSandboxManager:
    """Tests for SandboxManager."""

    def test_manager_initialization(self):
        """Test creating a sandbox manager."""
        manager = SandboxManager()
        assert manager.default_limits.timeout_sec == 30.0
        assert manager._temp_dirs == []

    def test_manager_with_custom_limits(self):
        """Test creating manager with custom limits."""
        limits = ResourceLimits(timeout_sec=60.0)
        manager = SandboxManager(default_limits=limits)
        assert manager.default_limits.timeout_sec == 60.0

    def test_execute_command_success(self):
        """Test executing a successful command."""
        manager = SandboxManager()

        result = manager.execute_command(
            ["echo", "hello"],
            SandboxType.NONE,
        )

        assert result.success is True
        assert "hello" in result.stdout

    def test_execute_command_timeout(self):
        """Test command timeout."""
        limits = ResourceLimits(timeout_sec=0.5)
        manager = SandboxManager(default_limits=limits)

        result = manager.execute_command(
            ["sleep", "10"],
            SandboxType.NONE,
        )

        assert result.success is False
        assert result.timed_out is True

    def test_create_temp_directory(self):
        """Test creating temporary directory."""
        manager = SandboxManager()
        temp_dir = manager.create_temp_directory()

        assert os.path.exists(temp_dir)
        assert temp_dir in manager._temp_dirs

    def test_cleanup_temp_directories(self):
        """Test cleaning up temporary directories."""
        manager = SandboxManager()
        temp_dir = manager.create_temp_directory()

        manager.cleanup()

        assert not os.path.exists(temp_dir)
        assert len(manager._temp_dirs) == 0

    def test_cleanup_after_multiple_temp_dirs(self):
        """Test cleaning up multiple temporary directories."""
        manager = SandboxManager()
        temp_dirs = [manager.create_temp_directory() for _ in range(3)]

        manager.cleanup()

        assert all(not os.path.exists(d) for d in temp_dirs)
        assert len(manager._temp_dirs) == 0


class TestCommandSafety:
    """Tests for command safety validation."""

    def test_empty_command(self):
        """Test empty command validation."""
        is_safe, reason = validate_command_safety([], {"ls"})
        assert is_safe is False
        assert "empty" in reason.lower()

    def test_empty_command_name(self):
        """Test command with empty name."""
        is_safe, reason = validate_command_safety([""], {"ls"})
        assert is_safe is False
        assert "empty" in reason.lower()

    def test_command_in_allowlist(self):
        """Test command in allowlist."""
        is_safe, reason = validate_command_safety(["ls", "-la"], {"ls", "cat"})
        assert is_safe is True
        assert "safe" in reason.lower()

    def test_command_not_in_allowlist(self):
        """Test command not in allowlist."""
        is_safe, reason = validate_command_safety(["rm", "-rf", "/"], {"ls", "cat"})
        assert is_safe is False
        assert "not in allowlist" in reason

    def test_empty_allowlist(self):
        """Test empty allowlist."""
        is_safe, reason = validate_command_safety(["ls"], set())
        assert is_safe is False
        assert "empty" in reason.lower()

    def test_dangerous_command(self):
        """Test dangerous command detection."""
        dangerous_commands = [
            (["rm", "-rf", "/"], "rm"),
            (["dd", "if=/dev/zero", "of=/dev/sda"], "dd"),
            (["format", "c:"], "format"),
        ]

        for cmd, name in dangerous_commands:
            is_safe, reason = validate_command_safety(cmd, {"ls", "cat", name})
            assert is_safe is False
            assert "dangerous" in reason.lower()

    def test_safe_command(self):
        """Test safe command."""
        is_safe, reason = validate_command_safety(
            ["cat", "/etc/hosts"],
            {"cat", "ls", "echo"},
        )
        assert is_safe is True


class TestCreateSafeLimits:
    """Tests for create_safe_limits function."""

    def test_safe_limits_values(self):
        """Test safe limits have conservative values."""
        limits = create_safe_limits()

        assert limits.timeout_sec == 30.0
        assert limits.max_memory_mb == 512
        assert limits.max_cpu_percent == 50
        assert limits.max_processes == 10
        assert limits.max_open_files == 100
        assert limits.max_file_size_mb == 10
        assert limits.allowed_network is False
