"""Tests for retry mechanism."""

import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
import pytest
from ..core.retry import (
    RetryEngine,
    RetryConfig,
    BackoffStrategy,
    FallbackConfig,
    retry_with_config,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test creating default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay_sec == 1.0
        assert config.max_delay_sec == 60.0
        assert config.backoff_strategy == BackoffStrategy.EXPONENTIAL_WITH_JITTER
        assert config.backoff_multiplier == 2.0
        assert config.jitter_factor == 0.1

    def test_custom_config(self):
        """Test creating custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay_sec=2.0,
            backoff_strategy=BackoffStrategy.LINEAR,
        )
        assert config.max_attempts == 5
        assert config.initial_delay_sec == 2.0
        assert config.backoff_strategy == BackoffStrategy.LINEAR


class TestRetryEngine:
    """Tests for RetryEngine."""

    def test_successful_execution_no_retry(self):
        """Test successful execution without retries."""
        config = RetryConfig(max_attempts=3)
        engine = RetryEngine(config)

        mock_func = MagicMock(return_value="success")

        result = engine.execute(mock_func)

        assert result.success is True
        assert result.value == "success"
        assert result.attempt_count == 1
        assert mock_func.call_count == 1

    def test_successful_execution_after_one_retry(self):
        """Test successful execution after one retry."""
        config = RetryConfig(max_attempts=3, initial_delay_sec=0.1)
        engine = RetryEngine(config)

        mock_func = MagicMock(side_effect=[Exception("fail"), "success"])

        result = engine.execute(mock_func)

        assert result.success is True
        assert result.value == "success"
        assert result.attempt_count == 2
        assert mock_func.call_count == 2

    def test_failure_after_max_retries(self):
        """Test failure after maximum retries."""
        config = RetryConfig(max_attempts=3, initial_delay_sec=0.1)
        engine = RetryEngine(config)

        mock_func = MagicMock(side_effect=Exception("fail"))

        result = engine.execute(mock_func)

        assert result.success is False
        assert result.error is not None
        assert result.attempt_count == 4  # Initial + 3 retries
        assert mock_func.call_count == 4

    def test_exponential_backoff(self):
        """Test exponential backoff strategy."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay_sec=1.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0,
        )
        engine = RetryEngine(config)

        call_times = []

        def tracking_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("fail")
            return "success"

        engine.execute(tracking_func)

        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            assert 0.8 < delay1 < 1.2  # ~1 second

        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            assert 1.8 < delay2 < 2.2  # ~2 seconds

    def test_linear_backoff(self):
        """Test linear backoff strategy."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay_sec=1.0,
            backoff_strategy=BackoffStrategy.LINEAR,
        )
        engine = RetryEngine(config)

        call_times = []

        def tracking_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("fail")
            return "success"

        engine.execute(tracking_func)

        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            assert 0.8 < delay1 < 1.2  # ~1 second

        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            assert 1.8 < delay2 < 2.2  # ~2 seconds

    def test_fixed_backoff(self):
        """Test fixed backoff strategy."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay_sec=1.0,
            backoff_strategy=BackoffStrategy.FIXED,
        )
        engine = RetryEngine(config)

        call_times = []

        def tracking_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception("fail")
            return "success"

        engine.execute(tracking_func)

        for i in range(1, len(call_times)):
            delay = call_times[i] - call_times[i - 1]
            assert 0.8 < delay < 1.2  # ~1 second each time

    def test_retryable_exceptions(self):
        """Test retrying only specific exceptions."""
        config = RetryConfig(
            max_attempts=3,
            retryable_exceptions=[ValueError],
            initial_delay_sec=0.1,
        )
        engine = RetryEngine(config)

        mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])

        result = engine.execute(mock_func)

        assert result.success is True
        assert mock_func.call_count == 2

    def test_non_retryable_exceptions(self):
        """Test not retrying non-retryable exceptions."""
        config = RetryConfig(
            max_attempts=3,
            non_retryable_exceptions=[ValueError],
            initial_delay_sec=0.1,
        )
        engine = RetryConfig(config)

        mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])

        result = engine.execute(mock_func)

        assert result.success is False
        assert mock_func.call_count == 1

    def test_on_retry_callback(self):
        """Test retry callback is called."""
        callback_calls = []

        def retry_callback(exc, attempt, delay):
            callback_calls.append((exc, attempt, delay))

        config = RetryConfig(
            max_attempts=2,
            initial_delay_sec=0.1,
            on_retry_callback=retry_callback,
        )
        engine = RetryEngine(config)

        mock_func = MagicMock(side_effect=[Exception("fail"), "success"])

        result = engine.execute(mock_func)

        assert len(callback_calls) == 1
        assert callback_calls[0][1] == 1  # First retry

    def test_on_failure_callback(self):
        """Test failure callback is called."""
        failure_called = []

        def failure_callback(exc):
            failure_called.append(exc)

        config = RetryConfig(
            max_attempts=2,
            initial_delay_sec=0.1,
            on_failure_callback=failure_callback,
        )
        engine = RetryEngine(config)

        mock_func = MagicMock(side_effect=Exception("fail"))

        result = engine.execute(mock_func)

        assert result.success is False
        assert len(failure_called) == 1

    def test_fallback_success(self):
        """Test fallback function succeeds."""
        fallback_called = []

        def fallback1():
            fallback_called.append(1)
            raise Exception("fallback1 failed")

        def fallback2():
            fallback_called.append(2)
            return "fallback_success"

        fallback_config = FallbackConfig(
            fallback_functions=[fallback1, fallback2],
            fallback_timeout_sec=1.0,
        )

        config = RetryConfig(max_attempts=1, initial_delay_sec=0.1)
        engine = RetryEngine(config)

        mock_func = MagicMock(side_effect=Exception("main failed"))

        result = engine.execute(mock_func, fallback_config=fallback_config)

        assert result.success is True
        assert result.value == "fallback_success"
        assert len(fallback_called) == 2

    def test_max_delay_limit(self):
        """Test maximum delay is respected."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay_sec=10.0,
            max_delay_sec=15.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0,
        )
        engine = RetryEngine(config)

        delays = []
        original_sleep = time.sleep

        def tracking_sleep(seconds):
            delays.append(seconds)
            return original_sleep(min(seconds, 1.0))

        time.sleep = tracking_sleep

        try:
            mock_func = MagicMock(side_effect=[Exception("fail")] * 6)
            engine.execute(mock_func)
        finally:
            time.sleep = original_sleep

        assert max(delays) <= 15.0  # Should not exceed max delay


class TestRetryDecorator:
    """Tests for retry decorator."""

    def test_decorator_success(self):
        """Test decorator with successful function."""
        @retry_with_config(max_attempts=2)
        def test_func():
            return "success"

        result = test_func()

        assert result == "success"

    def test_decorator_with_retry(self):
        """Test decorator with function that requires retry."""
        call_count = [0]

        @retry_with_config(max_attempts=3, initial_delay_sec=0.1)
        def test_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("fail")
            return "success"

        result = test_func()

        assert result == "success"
        assert call_count[0] == 3


class TestAsyncRetry:
    """Tests for async retry functionality."""

    @pytest.mark.asyncio
    async def test_async_successful_execution(self):
        """Test async successful execution."""
        config = RetryConfig(max_attempts=3)
        engine = RetryEngine(config)

        async mock_func():
            return "success"

        result = await engine.execute_async(mock_func)

        assert result.success is True
        assert result.value == "success"

    @pytest.mark.asyncio
    async def test_async_retry_on_failure(self):
        """Test async retry on failure."""
        config = RetryConfig(max_attempts=3, initial_delay_sec=0.1)
        engine = RetryEngine(config)

        call_count = [0]

        async mock_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("fail")
            return "success"

        result = await engine.execute_async(mock_func)

        assert result.success is True
        assert call_count[0] == 2
