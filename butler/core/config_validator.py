"""Configuration validation utilities for the Smart Butler system."""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .config import ButlerConfig
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a configuration validation.

    Attributes:
        is_valid: Whether the configuration is valid
        errors: List of validation errors
        warnings: List of validation warnings
    """

    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)


class ConfigValidator:
    """Validates ButlerConfig instances for correctness and security.

    Performs comprehensive validation of:
    - Required fields and their types
    - URL formats and connectivity
    - File paths and permissions
    - Port numbers and network settings
    - Security-sensitive configurations
    """

    REQUIRED_FIELDS: Set[str] = {
        "mqtt_host",
        "mqtt_port",
    }

    OPTIONAL_BUT_RECOMMENDED_FIELDS: Set[str] = {
        "mqtt_username",
        "mqtt_password",
        "llm_api_url",
        "llm_api_key",
    }

    SECURE_HTTP_PROTOCOLS: Set[str] = {"https", "wss"}
    INSECURE_HTTP_PROTOCOLS: Set[str] = {"http", "ws"}

    DEFAULT_SAFE_PORTS: Set[int] = {
        80,
        443,
        8080,
        8123,
        8883,
        9000,
        5000,
        3000,
    }

    def __init__(self) -> None:
        """Initialize the validator."""
        self.url_pattern = re.compile(
            r"^(https?|wss?)://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

    def validate(self, config: ButlerConfig) -> ValidationResult:
        """Validate a ButlerConfig instance.

        Args:
            config: The ButlerConfig instance to validate

        Returns:
            ValidationResult with validation status and messages
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        self._validate_required_fields(config, result)
        self._validate_urls(config, result)
        self._validate_ports(config, result)
        self._validate_paths(config, result)
        self._validate_llm_config(config, result)
        self._validate_mqtt_config(config, result)
        self._validate_openclaw_config(config, result)
        self._validate_email_config(config, result)
        self._validate_vision_config(config, result)
        self._validate_security_settings(config, result)

        if result.errors:
            logger.error("Configuration validation failed with %d errors", len(result.errors))
            for error in result.errors:
                logger.error("  - %s", error)

        if result.warnings:
            logger.warning("Configuration validation produced %d warnings", len(result.warnings))
            for warning in result.warnings:
                logger.warning("  - %s", warning)

        return result

    def _validate_required_fields(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate that all required fields are present."""
        for field in self.REQUIRED_FIELDS:
            if not hasattr(config, field) or getattr(config, field) is None:
                result.add_error(f"Required field '{field}' is missing or None")

    def _validate_urls(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate URL fields."""
        url_fields = {
            "llm_api_url": "LLM API",
            "ha_url": "Home Assistant",
            "gateway_base_url": "Gateway",
            "openclaw_gateway_url": "OpenClaw Gateway",
            "asr_api_url": "ASR API",
            "image_api_url": "Image Generation API",
            "search_api_url": "Web Search API",
        }

        for field, name in url_fields.items():
            value = getattr(config, field, None)
            if not value:
                continue

            if not self._is_valid_url(value):
                result.add_error(f"{name} URL '{value}' is invalid")

            protocol = value.split("://")[0].lower() if "://" in value else ""
            if protocol in self.INSECURE_HTTP_PROTOCOLS:
                result.add_warning(f"{name} URL uses insecure protocol '{protocol}'")

    def _validate_ports(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate port number fields."""
        port_fields = {
            "mqtt_port": "MQTT",
            "email_imap_port": "Email IMAP",
            "email_smtp_port": "Email SMTP",
            "gateway_timeout_sec": "Gateway timeout",
            "asr_timeout_sec": "ASR timeout",
            "image_timeout_sec": "Image generation timeout",
            "search_timeout_sec": "Web search timeout",
        }

        for field, name in port_fields.items():
            value = getattr(config, field, None)
            if value is None:
                continue

            try:
                port = int(value)
                if port < 1 or port > 65535:
                    result.add_error(f"{name} port {port} is out of valid range (1-65535)")
            except (ValueError, TypeError):
                result.add_error(f"{name} port '{value}' is not a valid number")

    def _validate_paths(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate file path fields."""
        path_fields = {
            "openclaw_cli_path": "OpenClaw CLI",
            "script_dir": "Script directory",
            "vision_face_model_path": "Face recognition model",
            "vision_object_model_path": "Object detection model",
            "asr_download_dir": "ASR model download directory",
            "asr_vosk_model_path": "Vosk model path",
        }

        for field, name in path_fields.items():
            value = getattr(config, field, None)
            if not value:
                continue

            if not isinstance(value, str):
                result.add_error(f"{name} path must be a string")
                continue

            if not os.path.isabs(value):
                result.add_warning(f"{name} path '{value}' is relative, may cause issues")

            if os.path.exists(value):
                if os.path.isdir(value) and not field.endswith("_path"):
                    result.add_warning(f"{name} path '{value}' is a directory, expected a file")
            else:
                if field.endswith("_path"):
                    result.add_warning(f"{name} path '{value}' does not exist")

    def _validate_llm_config(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate LLM configuration."""
        api_key = getattr(config, "llm_api_key", None)
        api_url = getattr(config, "llm_api_url", None)

        if api_url and not api_key:
            result.add_warning("LLM API URL is configured but API key is missing")

        if api_key and not api_url:
            result.add_warning("LLM API key is configured but API URL is missing")

        model = getattr(config, "llm_model", None)
        if not model:
            result.add_warning("LLM model is not configured")

    def _validate_mqtt_config(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate MQTT configuration."""
        host = getattr(config, "mqtt_host", None)
        port = getattr(config, "mqtt_port", None)

        if host and not self._is_valid_host(host):
            result.add_error(f"MQTT host '{host}' is invalid")

        username = getattr(config, "mqtt_username", None)
        password = getattr(config, "mqtt_password", None)

        if password and not username:
            result.add_warning("MQTT password is set but username is missing")

        use_tls = getattr(config, "mqtt_use_tls", False)
        if use_tls and port == 1883:
            result.add_warning("MQTT TLS is enabled but port is 1883 (non-TLS)")

    def _validate_openclaw_config(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate OpenClaw configuration."""
        cli_path = getattr(config, "openclaw_cli_path", None)
        gateway_enabled = getattr(config, "openclaw_gateway_enabled", False)

        if not cli_path and not gateway_enabled:
            result.add_warning("Neither OpenClaw CLI path nor Gateway mode is configured")

        if gateway_enabled:
            gateway_url = getattr(config, "openclaw_gateway_url", None)
            if not gateway_url:
                result.add_error("OpenClaw Gateway is enabled but URL is not configured")

            gateway_token = getattr(config, "openclaw_gateway_token", None)
            gateway_password = getattr(config, "openclaw_gateway_password", None)

            if not gateway_token and not gateway_password:
                result.add_warning("OpenClaw Gateway is enabled but neither token nor password is configured")

    def _validate_email_config(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate email configuration."""
        imap_host = getattr(config, "email_imap_host", None)
        smtp_host = getattr(config, "email_smtp_host", None)
        username = getattr(config, "email_username", None)
        password = getattr(config, "email_password", None)

        if imap_host and not (username and password):
            result.add_warning("Email IMAP host is configured but credentials are incomplete")

        if smtp_host and not (username and password):
            result.add_warning("Email SMTP host is configured but credentials are incomplete")

    def _validate_vision_config(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate vision configuration."""
        vision_enabled = getattr(config, "vision_enabled", False)

        if vision_enabled:
            face_model = getattr(config, "vision_face_model_path", None)
            object_model = getattr(config, "vision_object_model_path", None)

            if not face_model:
                result.add_warning("Vision is enabled but face model path is not configured")

            if not object_model:
                result.add_warning("Vision is enabled but object model path is not configured")

    def _validate_security_settings(self, config: ButlerConfig, result: ValidationResult) -> None:
        """Validate security-related settings."""
        system_exec_allowlist = getattr(config, "system_exec_allowlist", [])
        script_allowlist = getattr(config, "script_allowlist", [])

        if not system_exec_allowlist:
            result.add_warning("System execution allowlist is empty - no commands will be allowed")

        if not script_allowlist:
            result.add_warning("Script execution allowlist is empty - no scripts will be allowed")

        privacy_block_kinds = getattr(config, "privacy_block_store_kinds", [])
        if not privacy_block_kinds:
            result.add_warning("Privacy mode block kinds are not configured - sensitive events may be stored")

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Check if a string is a valid URL."""
        try:
            result = re.match(
                r"^(https?|wss?)://"
                r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
                r"localhost|"
                r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
                r"(?::\d+)?"
                r"(?:/?|[/?]\S+)$",
                url,
                re.IGNORECASE,
            )
            return bool(result)
        except (TypeError, AttributeError):
            return False

    @staticmethod
    def _is_valid_host(host: str) -> bool:
        """Check if a string is a valid hostname or IP address."""
        if not host or not isinstance(host, str):
            return False

        if host == "localhost":
            return True

        ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        if re.match(ipv4_pattern, host):
            try:
                octets = [int(octet) for octet in host.split(".")]
                return all(0 <= octet <= 255 for octet in octets)
            except ValueError:
                return False

        hostname_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
        return bool(re.match(hostname_pattern, host))


def validate_config(config: ButlerConfig) -> Tuple[bool, List[str], List[str]]:
    """Validate a ButlerConfig instance.

    Convenience function that returns validation result as a tuple.

    Args:
        config: The ButlerConfig instance to validate

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    validator = ConfigValidator()
    result = validator.validate(config)
    return result.is_valid, result.errors, result.warnings
