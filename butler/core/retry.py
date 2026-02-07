"""Retry mechanism and fallback strategy for the Smart Butler system."""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from .exceptions import ButlerError, RetryableError, TimeoutError as ButlerTimeoutError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BackoffStrategy(Enum):
    """Backoff strategies for retry attempts."""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_WITH_JITTER = "exponential_with_jitter"
    FIBONACCI = "fibonacci"


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts (excluding initial attempt)
        initial_delay_sec: Initial delay before first retry
        max_delay_sec: Maximum delay between retries
        backoff_strategy: Strategy for calculating delay between retries
        backoff_multiplier: Multiplier for exponential backoff
        jitter_factor: Random jitter factor (0-1) for exponential_with_jitter
        retryable_exceptions: List of exception types that trigger retry
        non_retryable_exceptions: List of exception types that should not be retried
        on_retry_callback: Optional callback function called before each retry
        on_failure_callback: Optional callback function called after all retries fail
        retry_if: Optional function to determine if a specific error should be retried
    """

    max_attempts: int = 3
    initial_delay_sec: float = 1.0
    max_delay_sec: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_WITH_JITTER
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1
    retryable_exceptions: List[Type[Exception]] = field(default_factory=list)
    non_retryable_exceptions: List[Type[Exception]] = field(default_factory=list)
    on_retry_callback: Optional[Callable[[Exception, int, float], None]] = None
    on_failure_callback: Optional[Callable[[Exception], None]] = None
    retry_if: Optional[Callable[[Exception], bool]] = None


@dataclass
class FallbackConfig:
    """Configuration for fallback strategies.

    Attributes:
        fallback_functions: List of fallback functions to try in order
        fallback_on_exceptions: List of exception types that trigger fallback
        fallback_timeout_sec: Timeout for each fallback attempt
        max_fallbacks: Maximum number of fallback functions to try
    """

    fallback_functions: List[Callable[[], T]] = field(default_factory=list)
    fallback_on_exceptions: List[Type[Exception]] = field(default_factory=list)
    fallback_timeout_sec: float = 30.0
    max_fallbacks: int = 2


@dataclass
class RetryResult:
    """Result of a retry operation.

    Attributes:
        success: Whether the operation succeeded
        value: The return value if successful
        error: The exception that caused failure if unsuccessful
        attempt_count: Number of attempts made
        total_time_sec: Total time spent on all attempts
    """

    success: bool
    value: Optional[T] = None
    error: Optional[Exception] = None
    attempt_count: int = 0
    total_time_sec: float = 0.0


class RetryEngine:
    """Engine for executing operations with retry and fallback logic.

    Provides configurable retry strategies, backoff algorithms,
    and fallback mechanisms for handling transient failures.
    """

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        """Initialize the retry engine.

        Args:
            config: Retry configuration, uses defaults if None
        """
        self.config = config or RetryConfig()

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        fallback_config: Optional[FallbackConfig] = None,
        **kwargs: Any,
    ) -> RetryResult[T]:
        """Execute a function with retry and fallback logic.

        Args:
            func: The function to execute
            *args: Positional arguments to pass to func
            fallback_config: Optional fallback configuration
            **kwargs: Keyword arguments to pass to func

        Returns:
            RetryResult containing success status, value, or error
        """
        start_time = time.time()
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.config.max_attempts:
            attempt += 1

            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                return RetryResult(
                    success=True,
                    value=result,
                    attempt_count=attempt,
                    total_time_sec=elapsed,
                )

            except Exception as exc:
                last_error = exc
                should_retry = self._should_retry(exc, attempt)

                if not should_retry:
                    elapsed = time.time() - start_time
                    logger.error(
                        "Operation failed with non-retryable error: %s (attempt %d/%d)",
                        exc,
                        attempt,
                        self.config.max_attempts + 1,
                    )
                    if self.config.on_failure_callback:
                        self.config.on_failure_callback(exc)
                    return RetryResult(
                        success=False,
                        error=exc,
                        attempt_count=attempt,
                        total_time_sec=elapsed,
                    )

                if attempt <= self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        "Operation failed: %s, retrying in %.2fs (attempt %d/%d)",
                        exc,
                        delay,
                        attempt,
                        self.config.max_attempts + 1,
                    )

                    if self.config.on_retry_callback:
                        self.config.on_retry_callback(exc, attempt, delay)

                    time.sleep(delay)

        elapsed = time.time() - start_time
        logger.error(
            "Operation failed after %d attempts: %s",
            attempt,
            last_error,
        )

        if self.config.on_failure_callback:
            self.config.on_failure_callback(last_error)

        if fallback_config and fallback_config.fallback_functions:
            return self._execute_fallbacks(fallback_config, start_time)

        return RetryResult(
            success=False,
            error=last_error,
            attempt_count=attempt,
            total_time_sec=elapsed,
        )

    async def execute_async(
        self,
        func: Callable[..., T],
        *args: Any,
        fallback_config: Optional[FallbackConfig] = None,
        **kwargs: Any,
    ) -> RetryResult[T]:
        """Execute an async function with retry and fallback logic.

        Args:
            func: The async function to execute
            *args: Positional arguments to pass to func
            fallback_config: Optional fallback configuration
            **kwargs: Keyword arguments to pass to func

        Returns:
            RetryResult containing success status, value, or error
        """
        start_time = time.time()
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.config.max_attempts:
            attempt += 1

            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                return RetryResult(
                    success=True,
                    value=result,
                    attempt_count=attempt,
                    total_time_sec=elapsed,
                )

            except Exception as exc:
                last_error = exc
                should_retry = self._should_retry(exc, attempt)

                if not should_retry:
                    elapsed = time.time() - start_time
                    logger.error(
                        "Async operation failed with non-retryable error: %s (attempt %d/%d)",
                        exc,
                        attempt,
                        self.config.max_attempts + 1,
                    )
                    if self.config.on_failure_callback:
                        self.config.on_failure_callback(exc)
                    return RetryResult(
                        success=False,
                        error=exc,
                        attempt_count=attempt,
                        total_time_sec=elapsed,
                    )

                if attempt <= self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        "Async operation failed: %s, retrying in %.2fs (attempt %d/%d)",
                        exc,
                        delay,
                        attempt,
                        self.config.max_attempts + 1,
                    )

                    if self.config.on_retry_callback:
                        self.config.on_retry_callback(exc, attempt, delay)

                    await asyncio.sleep(delay)

        elapsed = time.time() - start_time
        logger.error(
            "Async operation failed after %d attempts: %s",
            attempt,
            last_error,
        )

        if self.config.on_failure_callback:
            self.config.on_failure_callback(last_error)

        if fallback_config and fallback_config.fallback_functions:
            return await self._execute_fallbacks_async(fallback_config, start_time)

        return RetryResult(
            success=False,
            error=last_error,
            attempt_count=attempt,
            total_time_sec=elapsed,
        )

    def _should_retry(self, exc: Exception, attempt: int) -> bool:
        """Determine if an exception should trigger a retry.

        Args:
            exc: The exception that occurred
            attempt: Current attempt number

        Returns:
            True if should retry, False otherwise
        """
        if attempt > self.config.max_attempts:
            return False

        if self.config.retry_if and not self.config.retry_if(exc):
            return False

        for exc_type in self.config.non_retryable_exceptions:
            if isinstance(exc, exc_type):
                return False

        if self.config.retryable_exceptions:
            for exc_type in self.config.retryable_exceptions:
                if isinstance(exc, exc_type):
                    return True
            return False

        return True

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay before next retry based on strategy.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        if self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.initial_delay_sec

        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.initial_delay_sec * attempt

        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.initial_delay_sec * (self.config.backoff_multiplier ** (attempt - 1))

        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL_WITH_JITTER:
            base_delay = self.config.initial_delay_sec * (self.config.backoff_multiplier ** (attempt - 1))
            jitter = base_delay * self.config.jitter_factor * (2 * random.random() - 1)
            delay = base_delay + jitter

        elif self.config.backoff_strategy == BackoffStrategy.FIBONACCI:
            delay = self.config.initial_delay_sec * self._fibonacci(attempt)

        else:
            delay = self.config.initial_delay_sec

        return min(delay, self.config.max_delay_sec)

    @staticmethod
    def _fibonacci(n: int) -> int:
        """Calculate the nth Fibonacci number.

        Args:
            n: The position in the Fibonacci sequence (1-indexed)

        Returns:
            The nth Fibonacci number
        """
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(2, n):
            a, b = b, a + b
        return b

    def _execute_fallbacks(self, fallback_config: FallbackConfig, start_time: float) -> RetryResult[T]:
        """Execute fallback functions in sequence.

        Args:
            fallback_config: Fallback configuration
            start_time: Start time of the original operation

        Returns:
            RetryResult with fallback attempt results
        """
        max_fallbacks = min(len(fallback_config.fallback_functions), fallback_config.max_fallbacks)

        for i, fallback_func in enumerate(fallback_config.fallback_functions[:max_fallbacks]):
            try:
                result = fallback_func()
                elapsed = time.time() - start_time
                logger.info("Fallback %d succeeded", i + 1)
                return RetryResult(
                    success=True,
                    value=result,
                    attempt_count=i + 1,
                    total_time_sec=elapsed,
                )
            except Exception as exc:
                logger.warning("Fallback %d failed: %s", i + 1, exc)

        elapsed = time.time() - start_time
        logger.error("All fallbacks failed")
        return RetryResult(
            success=False,
            error=Exception("All fallbacks failed"),
            attempt_count=max_fallbacks,
            total_time_sec=elapsed,
        )

    async def _execute_fallbacks_async(self, fallback_config: FallbackConfig, start_time: float) -> RetryResult[T]:
        """Execute async fallback functions in sequence.

        Args:
            fallback_config: Fallback configuration
            start_time: Start time of the original operation

        Returns:
            RetryResult with fallback attempt results
        """
        max_fallbacks = min(len(fallback_config.fallback_functions), fallback_config.max_fallbacks)

        for i, fallback_func in enumerate(fallback_config.fallback_functions[:max_fallbacks]):
            try:
                result = await fallback_func()
                elapsed = time.time() - start_time
                logger.info("Async fallback %d succeeded", i + 1)
                return RetryResult(
                    success=True,
                    value=result,
                    attempt_count=i + 1,
                    total_time_sec=elapsed,
                )
            except Exception as exc:
                logger.warning("Async fallback %d failed: %s", i + 1, exc)

        elapsed = time.time() - start_time
        logger.error("All async fallbacks failed")
        return RetryResult(
            success=False,
            error=Exception("All async fallbacks failed"),
            attempt_count=max_fallbacks,
            total_time_sec=elapsed,
        )


def retry_with_config(
    max_attempts: int = 3,
    initial_delay_sec: float = 1.0,
    max_delay_sec: float = 60.0,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_WITH_JITTER,
    backoff_multiplier: float = 2.0,
    jitter_factor: float = 0.1,
    retryable_exceptions: Optional[List[Type[Exception]]] = None,
    non_retryable_exceptions: Optional[List[Type[Exception]]] = None,
) -> Callable:
    """Decorator for retrying functions with configurable parameters.

    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay_sec: Initial delay before first retry
        max_delay_sec: Maximum delay between retries
        backoff_strategy: Strategy for calculating delay
        backoff_multiplier: Multiplier for exponential backoff
        jitter_factor: Random jitter factor (0-1)
        retryable_exceptions: List of exception types that trigger retry
        non_retryable_exceptions: List of exception types that should not be retried

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        config = RetryConfig(
            max_attempts=max_attempts,
            initial_delay_sec=initial_delay_sec,
            max_delay_sec=max_delay_sec,
            backoff_strategy=backoff_strategy,
            backoff_multiplier=backoff_multiplier,
            jitter_factor=jitter_factor,
            retryable_exceptions=retryable_exceptions or [],
            non_retryable_exceptions=non_retryable_exceptions or [],
        )
        engine = RetryEngine(config)

        def wrapper(*args: Any, **kwargs: Any) -> T:
            result = engine.execute(func, *args, **kwargs)
            if result.success:
                return result.value
            elif result.error:
                raise result.error
            else:
                raise Exception("Unknown error in retry")

        return wrapper

    return decorator
