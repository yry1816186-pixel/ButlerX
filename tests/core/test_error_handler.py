import pytest
import asyncio
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from butler.core.error_handler import (
    ErrorHandler, ErrorRecord, ErrorSeverity, ErrorCategory,
    RecoveryStrategy, CircuitBreakerState
)


class TestErrorRecord:
    def test_error_record_creation(self):
        record = ErrorRecord(
            error_id="err001",
            error_type=ValueError,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DEVICE,
            message="Test error message",
            timestamp=datetime.now(),
            context={"key": "value"}
        )
        
        assert record.error_id == "err001"
        assert record.error_type == ValueError
        assert record.severity == ErrorSeverity.HIGH
        assert record.category == ErrorCategory.DEVICE
        assert record.message == "Test error message"
        assert record.context == {"key": "value"}

    def test_error_record_to_dict(self):
        record = ErrorRecord(
            error_id="err001",
            error_type=ValueError,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DEVICE,
            message="Test error message"
        )
        
        data = record.to_dict()
        assert data["error_id"] == "err001"
        assert data["severity"] == "HIGH"
        assert data["category"] == "DEVICE"


class TestErrorHandler:
    @pytest.fixture
    def error_handler(self):
        handler = ErrorHandler.get_instance()
        handler.clear_records()
        return handler

    def test_singleton_pattern(self, error_handler):
        handler2 = ErrorHandler.get_instance()
        assert error_handler is handler2

    def test_register_error(self, error_handler):
        error = ValueError("Test error")
        record = error_handler.register_error(
            error=error,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.SYSTEM,
            context={"test": "context"}
        )
        
        assert record is not None
        assert record.error_type == ValueError
        assert record.severity == ErrorSeverity.MEDIUM

    def test_get_error_by_id(self, error_handler):
        error = ValueError("Test error")
        record = error_handler.register_error(
            error=error,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.SYSTEM
        )
        
        retrieved = error_handler.get_error_by_id(record.error_id)
        assert retrieved is not None
        assert retrieved.error_id == record.error_id

    def test_get_errors_by_category(self, error_handler):
        error_handler.register_error(
            error=ValueError("Test 1"),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.DEVICE
        )
        error_handler.register_error(
            error=ValueError("Test 2"),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DEVICE
        )
        error_handler.register_error(
            error=ValueError("Test 3"),
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.SYSTEM
        )
        
        device_errors = error_handler.get_errors_by_category(ErrorCategory.DEVICE)
        assert len(device_errors) == 2

    def test_get_errors_by_severity(self, error_handler):
        error_handler.register_error(
            error=ValueError("Test 1"),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.SYSTEM
        )
        error_handler.register_error(
            error=ValueError("Test 2"),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DEVICE
        )
        error_handler.register_error(
            error=ValueError("Test 3"),
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.SYSTEM
        )
        
        high_errors = error_handler.get_errors_by_severity(ErrorSeverity.HIGH)
        assert len(high_errors) == 2

    def test_get_recent_errors(self, error_handler):
        error_handler.register_error(
            error=ValueError("Test 1"),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.SYSTEM
        )
        error_handler.register_error(
            error=ValueError("Test 2"),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.SYSTEM
        )
        
        recent = error_handler.get_recent_errors(limit=1)
        assert len(recent) == 1

    def test_circuit_breaker(self, error_handler):
        handler_name = "test_handler"
        
        assert error_handler.get_circuit_breaker_state(handler_name) == CircuitBreakerState.CLOSED
        
        for _ in range(5):
            error_handler.record_circuit_breaker_failure(handler_name)
        
        assert error_handler.get_circuit_breaker_state(handler_name) == CircuitBreakerState.OPEN
        assert error_handler.is_circuit_breaker_open(handler_name) is True

    def test_reset_circuit_breaker(self, error_handler):
        handler_name = "test_handler"
        
        for _ in range(5):
            error_handler.record_circuit_breaker_failure(handler_name)
        
        assert error_handler.is_circuit_breaker_open(handler_name) is True
        
        error_handler.reset_circuit_breaker(handler_name)
        assert error_handler.is_circuit_breaker_open(handler_name) is False

    def test_register_recovery_handler(self, error_handler):
        async def recovery_fn(error_record):
            return {"recovered": True}
        
        error_handler.register_recovery_handler(ValueError, recovery_fn)
        assert ValueError in error_handler.get_recovery_handlers()

    def test_execute_recovery(self, error_handler):
        async def recovery_fn(error_record):
            return {"recovered": True}
        
        error_handler.register_recovery_handler(ValueError, recovery_fn)
        
        record = error_handler.register_error(
            error=ValueError("Test error"),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.SYSTEM
        )
        
        result = asyncio.run(error_handler.execute_recovery(record))
        assert result["recovered"] is True

    def test_clear_records(self, error_handler):
        error_handler.register_error(
            error=ValueError("Test error"),
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.SYSTEM
        )
        
        assert len(error_handler.get_all_errors()) > 0
        
        error_handler.clear_records()
        assert len(error_handler.get_all_errors()) == 0

    def test_get_error_statistics(self, error_handler):
        error_handler.register_error(
            error=ValueError("Test 1"),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DEVICE
        )
        error_handler.register_error(
            error=ValueError("Test 2"),
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DEVICE
        )
        error_handler.register_error(
            error=ValueError("Test 3"),
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.SYSTEM
        )
        
        stats = error_handler.get_error_statistics()
        assert stats["total_errors"] == 3
        assert stats["by_severity"]["HIGH"] == 2
        assert stats["by_category"]["DEVICE"] == 2


class TestRecoveryStrategy:
    def test_strategy_values(self):
        assert RecoveryStrategy.RETRY.value == "retry"
        assert RecoveryStrategy.CIRCUIT_BREAKER.value == "circuit_breaker"
        assert RecoveryStrategy.FALLBACK.value == "fallback"
        assert RecoveryStrategy.IGNORE.value == "ignore"
        assert RecoveryStrategy.LOG_AND_CONTINUE.value == "log_and_continue"


class TestCircuitBreakerState:
    def test_state_values(self):
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"


class TestDecorators:
    def test_handle_errors_decorator(self):
        from butler.core.error_handler import handle_errors
        
        error_handler = ErrorHandler.get_instance()
        
        @handle_errors(category=ErrorCategory.SYSTEM, severity=ErrorSeverity.LOW)
        def test_function():
            raise ValueError("Test error")
        
        result = test_function()
        assert result is not None
        assert result["success"] is False

    def test_retry_decorator(self):
        from butler.core.error_handler import retry
        
        attempt_count = [0]
        
        @retry(max_attempts=3, delay=0.01)
        def test_function():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Not yet")
            return "success"
        
        result = test_function()
        assert result == "success"
        assert attempt_count[0] == 3
