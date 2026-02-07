"""Custom exceptions for the Smart Butler system."""

from typing import Any, Dict, Optional


class ButlerError(Exception):
    """Base exception for all Butler system errors."""

    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        result = {"error": self.message}
        if self.error_code:
            result["error_code"] = self.error_code
        if self.details:
            result["details"] = self.details
        return result


class ConfigurationError(ButlerError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(message, error_code="CONFIG_ERROR", details=error_details)


class DatabaseError(ButlerError):
    """Raised when database operations fail."""

    def __init__(self, message: str, query: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if query:
            error_details["query"] = query
        super().__init__(message, error_code="DATABASE_ERROR", details=error_details)


class MQTTError(ButlerError):
    """Raised when MQTT communication fails."""

    def __init__(self, message: str, topic: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if topic:
            error_details["topic"] = topic
        super().__init__(message, error_code="MQTT_ERROR", details=error_details)


class LLMError(ButlerError):
    """Raised when LLM API calls fail."""

    def __init__(self, message: str, model: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if model:
            error_details["model"] = model
        super().__init__(message, error_code="LLM_ERROR", details=error_details)


class PolicyViolationError(ButlerError):
    """Raised when an action violates policy rules."""

    def __init__(self, message: str, action_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if action_type:
            error_details["action_type"] = action_type
        super().__init__(message, error_code="POLICY_VIOLATION", details=error_details)


class ActionExecutionError(ButlerError):
    """Raised when action execution fails."""

    def __init__(self, message: str, action_type: Optional[str] = None, plan_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if action_type:
            error_details["action_type"] = action_type
        if plan_id:
            error_details["plan_id"] = plan_id
        super().__init__(message, error_code="ACTION_EXECUTION_ERROR", details=error_details)


class ToolError(ButlerError):
    """Base exception for tool-specific errors."""

    def __init__(self, message: str, tool: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if tool:
            error_details["tool"] = tool
        super().__init__(message, error_code="TOOL_ERROR", details=error_details)


class VisionError(ToolError):
    """Raised when vision operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, tool="vision", details=details)


class VoiceError(ToolError):
    """Raised when voice operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, tool="voice", details=details)


class PTZError(ToolError):
    """Raised when PTZ camera operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, tool="ptz", details=details)


class HomeAssistantError(ToolError):
    """Raised when Home Assistant operations fail."""

    def __init__(self, message: str, service: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if service:
            error_details["service"] = service
        super().__init__(message, tool="homeassistant", details=error_details)


class EmailError(ToolError):
    """Raised when email operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, tool="email", details=details)


class ImageGenerationError(ToolError):
    """Raised when image generation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, tool="image_generation", details=details)


class WebSearchError(ToolError):
    """Raised when web search fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, tool="web_search", details=details)


class OpenClawError(ToolError):
    """Raised when OpenClaw operations fail."""

    def __init__(self, message: str, channel: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if channel:
            error_details["channel"] = channel
        super().__init__(message, tool="openclaw", details=error_details)


class SystemExecutionError(ToolError):
    """Raised when system execution is blocked or fails."""

    def __init__(self, message: str, command: Optional[str] = None, reason: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if command:
            error_details["command"] = command
        if reason:
            error_details["reason"] = reason
        super().__init__(message, tool="system_exec", details=error_details)


class ScriptExecutionError(ToolError):
    """Raised when script execution is blocked or fails."""

    def __init__(self, message: str, script: Optional[str] = None, reason: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if script:
            error_details["script"] = script
        if reason:
            error_details["reason"] = reason
        super().__init__(message, tool="script_run", details=error_details)


class DeviceError(ToolError):
    """Raised when device operations fail."""

    def __init__(self, message: str, device_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if device_id:
            error_details["device_id"] = device_id
        super().__init__(message, tool="device", details=error_details)


class IRControlError(ToolError):
    """Raised when infrared control operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, tool="ir_control", details=details)


class SchedulingError(ButlerError):
    """Raised when task scheduling fails."""

    def __init__(self, message: str, task_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if task_id:
            error_details["task_id"] = task_id
        super().__init__(message, error_code="SCHEDULING_ERROR", details=error_details)


class AuthenticationError(ButlerError):
    """Raised when authentication fails."""

    def __init__(self, message: str, service: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if service:
            error_details["service"] = service
        super().__init__(message, error_code="AUTHENTICATION_ERROR", details=error_details)


class PermissionDeniedError(ButlerError):
    """Raised when permission is denied for an operation."""

    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        super().__init__(message, error_code="PERMISSION_DENIED", details=error_details)


class PrivacyModeError(ButlerError):
    """Raised when an action is blocked by privacy mode."""

    def __init__(self, message: str, action_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if action_type:
            error_details["action_type"] = action_type
        super().__init__(message, error_code="PRIVACY_MODE_BLOCKED", details=error_details)


class ValidationError(ButlerError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = value
        super().__init__(message, error_code="VALIDATION_ERROR", details=error_details)


class TimeoutError(ButlerError):
    """Raised when an operation times out."""

    def __init__(self, message: str, timeout_sec: Optional[float] = None, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        if timeout_sec is not None:
            error_details["timeout_sec"] = timeout_sec
        super().__init__(message, error_code="TIMEOUT", details=error_details)


class RetryableError(ButlerError):
    """Base class for errors that can be retried."""

    def __init__(self, message: str, retry_count: int = 0, max_retries: int = 3, details: Optional[Dict[str, Any]] = None) -> None:
        error_details = details or {}
        error_details["retry_count"] = retry_count
        error_details["max_retries"] = max_retries
        super().__init__(message, error_code="RETRYABLE_ERROR", details=error_details)
        self.retry_count = retry_count
        self.max_retries = max_retries
