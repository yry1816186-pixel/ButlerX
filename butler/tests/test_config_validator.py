"""Tests for configuration validation."""

import pytest
from ..core.config import ButlerConfig
from ..core.config_validator import (
    ConfigValidator,
    ValidationResult,
    validate_config,
)


class TestConfigValidator:
    """Tests for ConfigValidator."""

    def test_validator_initialization(self):
        """Test creating a config validator."""
        validator = ConfigValidator()
        assert validator.REQUIRED_FIELDS == {"mqtt_host", "mqtt_port"}

    def test_validate_required_field_missing(self):
        """Test validation with missing required field."""
        config = ButlerConfig(mqtt_host="localhost")
        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.is_valid is False
        assert any("mqtt_port" in error for error in result.errors)

    def test_validate_all_required_fields_present(self):
        """Test validation with all required fields."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
        )
        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.errors == []

    def test_validate_invalid_url(self):
        """Test validation of invalid URL."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            llm_api_url="not-a-url",
        )
        validator = ConfigValidator()
        result = validator.validate(config)

        assert any("LLM API URL" in error for error in result.errors)

    def test_validate_insecure_url_warning(self):
        """Test warning for insecure URL."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            llm_api_url="http://api.example.com",
        )
        validator = ConfigValidator()
        result = validator.validate(config)

        assert any("insecure" in warning for warning in result.warnings)

    def test_validate_port_out_of_range(self):
        """Test validation of port out of range."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=99999,
        )
        validator = ConfigValidator()
        result = validator.validate(config)

        assert any("port" in error and "out of valid range" in error for error in result.errors)

    def test_validate_mqtt_tls_port_mismatch_warning(self):
        """Test warning for TLS enabled with non-TLS port."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            mqtt_use_tls=True,
        )
        validator = ConfigValidator()
        result = validator.validate(config)

        assert any("TLS" in warning for warning in result.warnings)

    def test_validate_path_does_not_exist(self):
        """Test validation of non-existent path."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            openclaw_cli_path="/nonexistent/path",
        )
        validator = ConfigValidator()
        result = validator.validate(config)

        assert any("does not exist" in warning for warning in result.warnings)

    def test_validate_empty_allowlist_warning(self):
        """Test warning for empty allowlist."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
            system_exec_allowlist=[],
            script_allowlist=[],
        )
        validator = ConfigValidator()
        result = validator.validate(config)

        assert any("allowlist is empty" in warning for warning in result.warnings)


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_result_initialization(self):
        """Test creating a validation result."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_add_error(self):
        """Test adding an error."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        result.add_error("Test error")

        assert result.is_valid is False
        assert "Test error" in result.errors

    def test_add_warning(self):
        """Test adding a warning."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        result.add_warning("Test warning")

        assert "Test warning" in result.warnings
        assert result.is_valid is True  # Warnings don't affect validity


class TestValidateConfigFunction:
    """Tests for validate_config convenience function."""

    def test_validate_config_returns_tuple(self):
        """Test validate_config returns a tuple."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
        )
        result = validate_config(config)

        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_validate_config_valid(self):
        """Test validate_config with valid config."""
        config = ButlerConfig(
            mqtt_host="localhost",
            mqtt_port=1883,
        )
        is_valid, errors, warnings = validate_config(config)

        assert is_valid is True
        assert errors == []

    def test_validate_config_invalid(self):
        """Test validate_config with invalid config."""
        config = ButlerConfig()
        is_valid, errors, warnings = validate_config(config)

        assert is_valid is False
        assert len(errors) > 0

    @staticmethod
    def _is_valid_url(url):
        """Test helper to validate URL."""
        validator = ConfigValidator()
        return validator._is_valid_url(url)
