from __future__ import annotations
import logging
import traceback
import sys
from typing import Any, Dict, List, Optional, Callable, Type, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from functools import wraps
from contextlib import contextmanager
import asyncio

class ErrorSeverity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"

class ErrorCategory(Enum):
    NETWORK = "network"
    DEVICE = "device"
    SERVICE = "service"
    AI = "ai"
    AUTOMATION = "automation"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    PERMISSION = "permission"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    EXTERNAL = "external"
    UNKNOWN = "unknown"

class RecoveryStrategy(Enum):
    RETRY = "retry"
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK = "fallback"
    IGNORE = "ignore"
    LOG_AND_CONTINUE = "log_and_continue"
    DEGRADE = "degrade"
    SKIP = "skip"
    ABORT = "abort"
    NOTIFY = "notify"
    RESTART = "restart"

class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class ErrorContext:
    module: str
    function: str
    line: Optional[int] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "function": self.function,
            "line": self.line,
            "variables": self.variables,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class ErrorRecord:
    error_id: str
    exception: Exception
    severity: ErrorSeverity
    category: ErrorCategory
    context: ErrorContext
    traceback_str: str
    recovery_attempted: bool = False
    recovery_strategy: Optional[RecoveryStrategy] = None
    recovery_successful: bool = False
    additional_info: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_id": self.error_id,
            "exception_type": type(self.exception).__name__,
            "exception_message": str(self.exception),
            "severity": self.severity.value,
            "category": self.category.value,
            "context": self.context.to_dict(),
            "traceback": self.traceback_str,
            "recovery_attempted": self.recovery_attempted,
            "recovery_strategy": self.recovery_strategy.value if self.recovery_strategy else None,
            "recovery_successful": self.recovery_successful,
            "additional_info": self.additional_info,
            "timestamp": self.timestamp.isoformat()
        }

class ButlerException(Exception):
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        recovery_strategy: Optional[RecoveryStrategy] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.recovery_strategy = recovery_strategy
        self.context = context or {}

class NetworkException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.NETWORK, **kwargs)

class DeviceException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.DEVICE, **kwargs)

class ServiceException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.SERVICE, **kwargs)

class AIException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.AI, **kwargs)

class AutomationException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.AUTOMATION, **kwargs)

class DatabaseException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.DATABASE, **kwargs)

class ConfigurationException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.CONFIGURATION, **kwargs)

class PermissionException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.PERMISSION, **kwargs)

class HardwareException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.HARDWARE, **kwargs)

class ExternalServiceException(ButlerException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.EXTERNAL, **kwargs)

class ErrorHandler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._logger = logging.getLogger("butler.error_handler")
        self._error_records: List[ErrorRecord] = []
        self._error_counts: Dict[str, int] = {}
        self._error_patterns: Dict[str, List[str]] = {}
        self._recovery_handlers: Dict[Type[Exception], Callable] = {}
        self._error_listeners: List[Callable[[ErrorRecord], None]] = []
        self._max_records = 1000
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

    def handle_error(
        self,
        exception: Exception,
        context: Optional[ErrorContext] = None,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> ErrorRecord:
        import uuid

        error_id = str(uuid.uuid4())

        if context is None:
            frame = sys._getframe(1)
            context = ErrorContext(
                module=frame.f_globals.get('__name__', 'unknown'),
                function=frame.f_code.co_name,
                line=frame.f_lineno
            )

        if isinstance(exception, ButlerException):
            severity = severity or exception.severity
            category = category or exception.category
        else:
            severity = severity or ErrorSeverity.ERROR
            category = category or self._categorize_exception(exception)

        error_record = ErrorRecord(
            error_id=error_id,
            exception=exception,
            severity=severity,
            category=category,
            context=context,
            traceback_str=traceback.format_exc(),
            additional_info=additional_info or {}
        )

        self._error_records.append(error_record)

        error_key = f"{category.value}:{type(exception).__name__}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1

        if len(self._error_records) > self._max_records:
            self._error_records = self._error_records[-self._max_records:]

        self._log_error(error_record)
        self._check_circuit_breaker(error_record)
        self._notify_listeners(error_record)

        if exception in self._recovery_handlers:
            try:
                result = self._recovery_handlers[exception](error_record)
                error_record.recovery_attempted = True
                error_record.recovery_successful = result
            except Exception as recovery_error:
                self._logger.error(f"Recovery handler failed: {recovery_error}")

        return error_record

    def _categorize_exception(self, exception: Exception) -> ErrorCategory:
        exception_type = type(exception).__name__.lower()

        if any(keyword in exception_type for keyword in ['connection', 'network', 'socket', 'http', 'timeout']):
            return ErrorCategory.NETWORK
        elif any(keyword in exception_type for keyword in ['device', 'sensor', 'actuator']):
            return ErrorCategory.DEVICE
        elif any(keyword in exception_type for keyword in ['service', 'api', 'endpoint']):
            return ErrorCategory.SERVICE
        elif any(keyword in exception_type for keyword in ['ai', 'model', 'llm', 'vision', 'nlp']):
            return ErrorCategory.AI
        elif any(keyword in exception_type for keyword in ['automation', 'trigger', 'action']):
            return ErrorCategory.AUTOMATION
        elif any(keyword in exception_type for keyword in ['database', 'sql', 'sqlite', 'query']):
            return ErrorCategory.DATABASE
        elif any(keyword in exception_type for keyword in ['config', 'setting', 'yaml', 'json']):
            return ErrorCategory.CONFIGURATION
        elif any(keyword in exception_type for keyword in ['permission', 'access', 'auth']):
            return ErrorCategory.PERMISSION
        elif any(keyword in exception_type for keyword in ['hardware', 'serial', 'gpio']):
            return ErrorCategory.HARDWARE

        return ErrorCategory.UNKNOWN

    def _log_error(self, record: ErrorRecord):
        log_method = {
            ErrorSeverity.DEBUG: self._logger.debug,
            ErrorSeverity.INFO: self._logger.info,
            ErrorSeverity.WARNING: self._logger.warning,
            ErrorSeverity.ERROR: self._logger.error,
            ErrorSeverity.CRITICAL: self._logger.critical,
            ErrorSeverity.FATAL: self._logger.critical
        }.get(record.severity, self._logger.error)

        log_method(
            f"[{record.category.value.upper()}] {type(record.exception).__name__}: "
            f"{str(record.exception)} in {record.context.module}.{record.context.function}"
        )

        if record.severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            self._logger.debug(f"Traceback:\n{record.traceback_str}")

    def _check_circuit_breaker(self, record: ErrorRecord):
        key = f"{record.category.value}:{type(record.exception).__name__}"

        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = {
                "failure_count": 0,
                "last_failure": None,
                "open": False,
                "threshold": 10,
                "timeout": 60
            }

        breaker = self._circuit_breakers[key]
        breaker["failure_count"] += 1
        breaker["last_failure"] = record.timestamp

        if breaker["failure_count"] >= breaker["threshold"]:
            breaker["open"] = True
            self._logger.warning(f"Circuit breaker opened for {key}")

    def is_circuit_breaker_open(self, category: ErrorCategory, exception_type: Type[Exception]) -> bool:
        key = f"{category.value}:{exception_type.__name__}"
        breaker = self._circuit_breakers.get(key)

        if not breaker or not breaker["open"]:
            return False

        if breaker["last_failure"]:
            elapsed = (datetime.now() - breaker["last_failure"]).total_seconds()
            if elapsed > breaker["timeout"]:
                breaker["open"] = False
                breaker["failure_count"] = 0
                return False

        return True

    def reset_circuit_breaker(self, category: ErrorCategory, exception_type: Type[Exception]):
        key = f"{category.value}:{exception_type.__name__}"
        if key in self._circuit_breakers:
            self._circuit_breakers[key]["open"] = False
            self._circuit_breakers[key]["failure_count"] = 0

    def register_recovery_handler(
        self,
        exception_type: Type[Exception],
        handler: Callable[[ErrorRecord], bool]
    ):
        self._recovery_handlers[exception_type] = handler

    def unregister_recovery_handler(self, exception_type: Type[Exception]):
        if exception_type in self._recovery_handlers:
            del self._recovery_handlers[exception_type]

    def add_error_listener(self, listener: Callable[[ErrorRecord], None]):
        if listener not in self._error_listeners:
            self._error_listeners.append(listener)

    def remove_error_listener(self, listener: Callable[[ErrorRecord], None]):
        if listener in self._error_listeners:
            self._error_listeners.remove(listener)

    def _notify_listeners(self, record: ErrorRecord):
        for listener in self._error_listeners:
            try:
                listener(record)
            except Exception as e:
                self._logger.error(f"Error listener failed: {e}")

    def get_error_records(
        self,
        limit: int = 100,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None
    ) -> List[ErrorRecord]:
        records = self._error_records[-limit:]

        if severity:
            records = [r for r in records if r.severity == severity]

        if category:
            records = [r for r in records if r.category == category]

        return records

    def get_error_statistics(self) -> Dict[str, Any]:
        total_errors = len(self._error_records)

        by_severity = {}
        for record in self._error_records:
            by_severity[record.severity.value] = by_severity.get(record.severity.value, 0) + 1

        by_category = {}
        for record in self._error_records:
            by_category[record.category.value] = by_category.get(record.category.value, 0) + 1

        recent_errors = sum(1 for r in self._error_records if (datetime.now() - r.timestamp).total_seconds() < 3600)

        return {
            "total_errors": total_errors,
            "by_severity": by_severity,
            "by_category": by_category,
            "recent_errors_last_hour": recent_errors,
            "unique_error_types": len(self._error_counts),
            "open_circuit_breakers": sum(1 for b in self._circuit_breakers.values() if b["open"])
        }

    def clear_error_records(self):
        self._error_records.clear()
        self._error_counts.clear()

    def export_errors(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([r.to_dict() for r in self._error_records], f, ensure_ascii=False, indent=2)

def handle_errors(
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    category: Optional[ErrorCategory] = None,
    recovery_strategy: Optional[RecoveryStrategy] = None,
    fallback_value: Any = None,
    log_traceback: bool = True
):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            handler = ErrorHandler()
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                frame = sys._getframe()
                context = ErrorContext(
                    module=frame.f_globals.get('__name__', 'unknown'),
                    function=func.__name__,
                    line=frame.f_lineno
                )

                record = handler.handle_error(
                    exception=e,
                    context=context,
                    severity=severity,
                    category=category,
                    additional_info={"function": func.__name__, "args": str(args)[:200], "kwargs": str(kwargs)[:200]}
                )

                if recovery_strategy == RecoveryStrategy.FALLBACK:
                    return fallback_value
                elif recovery_strategy == RecoveryStrategy.RETRY:
                    return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            handler = ErrorHandler()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                frame = sys._getframe()
                context = ErrorContext(
                    module=frame.f_globals.get('__name__', 'unknown'),
                    function=func.__name__,
                    line=frame.f_lineno
                )

                record = handler.handle_error(
                    exception=e,
                    context=context,
                    severity=severity,
                    category=category,
                    additional_info={"function": func.__name__, "args": str(args)[:200], "kwargs": str(kwargs)[:200]}
                )

                if recovery_strategy == RecoveryStrategy.FALLBACK:
                    return fallback_value
                elif recovery_strategy == RecoveryStrategy.RETRY:
                    return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

@contextmanager
def error_context(
    module: str,
    function: str,
    additional_context: Optional[Dict[str, Any]] = None
):
    handler = ErrorHandler()
    try:
        yield handler
    except Exception as e:
        context = ErrorContext(
            module=module,
            function=function,
            additional_context=additional_context or {}
        )
        handler.handle_error(exception=e, context=context)
        raise

class RetryHandler:
    def __init__(
        self,
        max_attempts: int = 3,
        backoff_factor: float = 1.0,
        exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.exceptions = exceptions or [Exception]

    async def async_retry(self, func, *args, **kwargs):
        handler = ErrorHandler()
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except tuple(self.exceptions) as e:
                last_exception = e

                if attempt < self.max_attempts - 1:
                    delay = self.backoff_factor * (2 ** attempt)
                    await asyncio.sleep(delay)

        frame = sys._getframe(1)
        context = ErrorContext(
            module=frame.f_globals.get('__name__', 'unknown'),
            function=func.__name__,
            line=frame.f_lineno
        )

        handler.handle_error(
            exception=last_exception,
            context=context,
            severity=ErrorSeverity.WARNING,
            additional_info={"max_attempts": self.max_attempts, "actual_attempts": self.max_attempts}
        )

        raise last_exception

    def retry(self, func, *args, **kwargs):
        handler = ErrorHandler()
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except tuple(self.exceptions) as e:
                last_exception = e

                if attempt < self.max_attempts - 1:
                    delay = self.backoff_factor * (2 ** attempt)
                    import time
                    time.sleep(delay)

        frame = sys._getframe(1)
        context = ErrorContext(
            module=frame.f_globals.get('__name__', 'unknown'),
            function=func.__name__,
            line=frame.f_lineno
        )

        handler.handle_error(
            exception=last_exception,
            context=context,
            severity=ErrorSeverity.WARNING,
            additional_info={"max_attempts": self.max_attempts, "actual_attempts": self.max_attempts}
        )

        raise last_exception

def retry(max_attempts: int = 3, backoff_factor: float = 1.0, exceptions: Optional[List[Type[Exception]]] = None):
    retry_handler = RetryHandler(max_attempts, backoff_factor, exceptions)

    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await retry_handler.async_retry(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return retry_handler.retry(func, *args, **kwargs)
            return sync_wrapper

    return decorator
