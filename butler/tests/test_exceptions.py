"""Tests for custom exceptions."""

import pytest
from ..core.exceptions import (
    ButlerError,
    ConfigurationError,
    DatabaseError,
    ActionExecutionError,
    ValidationError,
    RetryableError,
)


class TestButlerError:
    """Tests for ButlerError base class."""

    def test_base_error_creation(self):
        """Test creating a base ButlerError."""
        error = ButlerError("Test error")
        assert error.message == "Test error"
        assert error.error_code is None
        assert error.details == {}

    def test_error_with_code(self):
        """Test creating an error with error code."""
        error = ButlerError("Test error", error_code="TEST_ERROR")
        assert error.error_code == "TEST_ERROR"

    def test_error_with_details(self):
        """Test creating an error with details."""
        details = {"field": "test", "value": "123"}
        error = ButlerError("Test error", details=details)
        assert error.details == details

    def test_to_dict_basic(self):
        """Test converting basic error to dict."""
        error = ButlerError("Test error")
        result = error.to_dict()
        assert result == {"error": "Test error"}

    def test_to_dict_with_code(self):
        """Test converting error with code to dict."""
        error = ButlerError("Test error", error_code="TEST_ERROR")
        result = error.to_dict()
        assert "error_code" in result
        assert result["error_code"] == "TEST_ERROR"

    def test_to_dict_with_details(self):
        """Test converting error with details to dict."""
        details = {"field": "test"}
        error = ButlerError("Test error", details=details)
        result = error.to_dict()
        assert "details" in result
        assert result["details"] == details


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_configuration_error_creation(self):
        """Test creating a configuration error."""
        error = ConfigurationError("Invalid URL")
        assert error.error_code == "CONFIG_ERROR"

    def test_configuration_error_with_field(self):
        """Test creating a configuration error with field."""
        error = ConfigurationError("Invalid field", field="mqtt_host")
        result = error.to_dict()
        assert result["details"]["field"] == "mqtt_host"


class TestDatabaseError:
    """Tests for DatabaseError."""

    def test_database_error_creation(self):
        """Test creating a database error."""
        error = DatabaseError("Query failed")
        assert error.error_code == "DATABASE_ERROR"

    def test_database_error_with_query(self):
        """Test creating a database error with query."""
        query = "SELECT * FROM test"
        error = DatabaseError("Query failed", query=query)
        result = error.to_dict()
        assert result["details"]["query"] == query


class TestActionExecutionError:
    """Tests for ActionExecutionError."""

    def test_action_execution_error_creation(self):
        """Test creating an action execution error."""
        error = ActionExecutionError("Action failed")
        assert error.error_code == "ACTION_EXECUTION_ERROR"

    def test_action_execution_error_with_plan_id(self):
        """Test creating an action execution error with plan ID."""
        error = ActionExecutionError("Action failed", plan_id="plan-123")
        result = error.to_dict()
        assert result["details"]["plan_id"] == "plan-123"


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_creation(self):
        """Test creating a validation error."""
        error = ValidationError("Invalid input")
        assert error.error_code == "VALIDATION_ERROR"

    def test_validation_error_with_field_and_value(self):
        """Test creating a validation error with field and value."""
        error = ValidationError("Invalid value", field="age", value=-5)
        result = error.to_dict()
        assert result["details"]["field"] == "age"
        assert result["details"]["value"] == -5


class TestRetryableError:
    """Tests for RetryableError."""

    def test_retryable_error_creation(self):
        """Test creating a retryable error."""
        error = RetryableError("Temporary failure")
        assert error.error_code == "RETRYABLE_ERROR"

    def test_retryable_error_retry_info(self):
        """Test retryable error contains retry information."""
        error = RetryableError("Temporary failure", retry_count=2, max_retries=5)
        result = error.to_dict()
        assert result["details"]["retry_count"] == 2
        assert result["details"]["max_retries"] == 5

    def test_retryable_error_attributes(self):
        """Test retryable error has retry attributes."""
        error = RetryableError("Temporary failure", retry_count=2, max_retries=5)
        assert error.retry_count == 2
        assert error.max_retries == 5
