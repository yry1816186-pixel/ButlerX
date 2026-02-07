"""Sandbox and resource limiting utilities for Smart Butler system."""

import logging
import os
import resource
import signal
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .exceptions import SystemExecutionError, TimeoutError as ButlerTimeoutError

logger = logging.getLogger(__name__)


class SandboxType(Enum):
    """Types of sandbox execution environments."""

    NONE = "none"
    CHROOT = "chroot"
    NAMESPACE = "namespace"
    DOCKER = "docker"
    FIREJAIL = "firejail"


@dataclass
class ResourceLimits:
    """Resource limits for sandboxed execution.

    Attributes:
        timeout_sec: Maximum execution time in seconds
        max_memory_mb: Maximum memory in megabytes
        max_cpu_percent: Maximum CPU usage percentage
        max_processes: Maximum number of processes
        max_open_files: Maximum number of open file descriptors
        max_file_size_mb: Maximum file size in megabytes
        allowed_paths: List of allowed file system paths
        blocked_paths: List of blocked file system paths
        allowed_network: Whether network access is allowed
        allowed_hosts: List of allowed network hosts
        blocked_ports: List of blocked network ports
    """

    timeout_sec: float = 30.0
    max_memory_mb: Optional[int] = None
    max_cpu_percent: Optional[int] = None
    max_processes: Optional[int] = None
    max_open_files: Optional[int] = None
    max_file_size_mb: Optional[int] = None
    allowed_paths: List[str] = field(default_factory=list)
    blocked_paths: List[str] = field(default_factory=list)
    allowed_network: bool = True
    allowed_hosts: List[str] = field(default_factory=list)
    blocked_ports: List[int] = field(default_factory=list)


@dataclass
class SandboxResult:
    """Result of a sandboxed execution.

    Attributes:
        success: Whether execution succeeded
        exit_code: Process exit code
        stdout: Standard output content
        stderr: Standard error content
        execution_time_sec: Time taken to execute
        timed_out: Whether execution timed out
        memory_used_mb: Memory used in MB (if available)
        cpu_percent: CPU usage percentage (if available)
    """

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time_sec: float
    timed_out: bool = False
    memory_used_mb: Optional[float] = None
    cpu_percent: Optional[float] = None


class SandboxManager:
    """Manages sandboxed execution with resource limits.

    Provides multiple levels of sandboxing from basic resource limits
    to full isolation using container technologies.
    """

    def __init__(self, default_limits: Optional[ResourceLimits] = None) -> None:
        """Initialize sandbox manager.

        Args:
            default_limits: Default resource limits to apply
        """
        self.default_limits = default_limits or ResourceLimits()
        self._temp_dirs: List[str] = []

    def execute_command(
        self,
        command: List[str],
        limits: Optional[ResourceLimits] = None,
        sandbox_type: SandboxType = SandboxType.NONE,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """Execute a command in a sandboxed environment.

        Args:
            command: Command and arguments as a list
            limits: Resource limits to apply
            sandbox_type: Type of sandbox to use
            working_dir: Working directory for execution
            env: Environment variables to set

        Returns:
            SandboxResult with execution details
        """
        limits = limits or self.default_limits
        start_time = 0.0

        try:
            if sandbox_type == SandboxType.FIREJAIL and self._is_firejail_available():
                return self._execute_with_firejail(command, limits, working_dir, env)
            elif sandbox_type == SandboxType.DOCKER and self._is_docker_available():
                return self._execute_with_docker(command, limits, working_dir, env)
            else:
                return self._execute_with_limits(command, limits, working_dir, env)

        except subprocess.TimeoutExpired:
            elapsed = 0.0
            if start_time > 0:
                elapsed = 0.0
            logger.warning("Command timed out after %s seconds", limits.timeout_sec)
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Execution timed out",
                execution_time_sec=elapsed,
                timed_out=True,
            )
        except Exception as exc:
            logger.error("Sandbox execution failed: %s", exc)
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                execution_time_sec=0.0,
            )

    def _execute_with_limits(
        self,
        command: List[str],
        limits: ResourceLimits,
        working_dir: Optional[str],
        env: Optional[Dict[str, str]],
    ) -> SandboxResult:
        """Execute command with resource limits using subprocess.

        Args:
            command: Command and arguments
            limits: Resource limits to apply
            working_dir: Working directory
            env: Environment variables

        Returns:
            SandboxResult with execution details
        """
        start_time = 0.0

        try:
            start_time = 0.0

            process_env = os.environ.copy()
            if env:
                process_env.update(env)

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir,
                env=process_env,
                preexec_fn=lambda: self._set_resource_limits(limits),
            )

            try:
                stdout, stderr = process.communicate(timeout=limits.timeout_sec)
                elapsed = 0.0

                return SandboxResult(
                    success=process.returncode == 0,
                    exit_code=process.returncode,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    execution_time_sec=elapsed,
                )

            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                elapsed = 0.0

                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    execution_time_sec=elapsed,
                    timed_out=True,
                )

        except Exception as exc:
            logger.error("Execution with limits failed: %s", exc)
            raise SystemExecutionError(str(exc), command=" ".join(command))

    def _execute_with_firejail(
        self,
        command: List[str],
        limits: ResourceLimits,
        working_dir: Optional[str],
        env: Optional[Dict[str, str]],
    ) -> SandboxResult:
        """Execute command using Firejail sandbox.

        Args:
            command: Command and arguments
            limits: Resource limits to apply
            working_dir: Working directory
            env: Environment variables

        Returns:
            SandboxResult with execution details
        """
        start_time = 0.0

        firejail_args = [
            "firejail",
            "--quiet",
            f"--timeout={int(limits.timeout_sec)}",
        ]

        if limits.max_memory_mb:
            firejail_args.append(f"--rlimit-as={limits.max_memory_mb * 1024 * 1024}")

        if limits.max_processes:
            firejail_args.append(f"--rlimit-nproc={limits.max_processes}")

        if limits.allowed_paths:
            for path in limits.allowed_paths:
                firejail_args.append(f"--private={path}")

        if limits.blocked_paths:
            for path in limits.blocked_paths:
                firejail_args.append(f"--blacklist={path}")

        if not limits.allowed_network:
            firejail_args.append("--net=none")

        if working_dir:
            firejail_args.extend(["--private-cwd", working_dir])

        full_command = firejail_args + command

        try:
            start_time = 0.0

            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = process.communicate(timeout=limits.timeout_sec)
                elapsed = 0.0

                return SandboxResult(
                    success=process.returncode == 0,
                    exit_code=process.returncode,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    execution_time_sec=elapsed,
                )

            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                elapsed = 0.0

                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    execution_time_sec=elapsed,
                    timed_out=True,
                )

        except Exception as exc:
            logger.error("Firejail execution failed: %s", exc)
            raise SystemExecutionError(str(exc), command=" ".join(command))

    def _execute_with_docker(
        self,
        command: List[str],
        limits: ResourceLimits,
        working_dir: Optional[str],
        env: Optional[Dict[str, str]],
    ) -> SandboxResult:
        """Execute command using Docker container.

        Args:
            command: Command and arguments
            limits: Resource limits to apply
            working_dir: Working directory
            env: Environment variables

        Returns:
            SandboxResult with execution details
        """
        raise NotImplementedError("Docker sandbox not yet implemented")

    def _set_resource_limits(self, limits: ResourceLimits) -> None:
        """Set resource limits for the current process.

        Args:
            limits: Resource limits to apply
        """
        try:
            if limits.max_memory_mb:
                memory_bytes = limits.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

            if limits.max_processes:
                resource.setrlimit(resource.RLIMIT_NPROC, (limits.max_processes, limits.max_processes))

            if limits.max_open_files:
                resource.setrlimit(resource.RLIMIT_NOFILE, (limits.max_open_files, limits.max_open_files))

            if limits.max_file_size_mb:
                file_size = limits.max_file_size_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_FSIZE, (file_size, file_size))

        except (ValueError, resource.error) as exc:
            logger.warning("Failed to set resource limits: %s", exc)

    @staticmethod
    def _is_firejail_available() -> bool:
        """Check if Firejail is available on the system."""
        try:
            result = subprocess.run(
                ["firejail", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _is_docker_available() -> bool:
        """Check if Docker is available on the system."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def create_temp_directory(self, prefix: str = "butler_sandbox_") -> str:
        """Create a temporary directory for sandboxed execution.

        Args:
            prefix: Prefix for the directory name

        Returns:
            Path to the created temporary directory
        """
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        self._temp_dirs.append(temp_dir)
        return temp_dir

    def cleanup(self) -> None:
        """Clean up temporary directories created by this manager."""
        for temp_dir in self._temp_dirs:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug("Cleaned up temporary directory: %s", temp_dir)
            except Exception as exc:
                logger.warning("Failed to clean up temporary directory %s: %s", temp_dir, exc)
        self._temp_dirs.clear()


def create_safe_limits() -> ResourceLimits:
    """Create safe default resource limits for sandboxed execution.

    Returns:
        ResourceLimits with conservative safe values
    """
    return ResourceLimits(
        timeout_sec=30.0,
        max_memory_mb=512,
        max_cpu_percent=50,
        max_processes=10,
        max_open_files=100,
        max_file_size_mb=10,
        allowed_network=False,
    )


def validate_command_safety(command: List[str], allowlist: Set[str]) -> Tuple[bool, str]:
    """Validate that a command is safe to execute.

    Args:
        command: Command and arguments
        allowlist: Set of allowed commands

    Returns:
        Tuple of (is_safe, reason)
    """
    if not command:
        return False, "Command is empty"

    if not command[0]:
        return False, "Command name is empty"

    command_name = os.path.basename(command[0]).lower()

    if not allowlist:
        return False, "Allowlist is empty"

    if command_name not in [cmd.lower() for cmd in allowlist]:
        return False, f"Command '{command_name}' is not in allowlist"

    dangerous_commands = [
        "rm", "dd", "mkfs", "fdisk", "format",
        "del", "rmdir", "format.com",
    ]

    if command_name in dangerous_commands:
        return False, f"Command '{command_name}' is considered dangerous"

    return True, "Command is safe"
