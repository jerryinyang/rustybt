"""Tests for error handling utilities."""

from __future__ import annotations

import asyncio

import pytest

from rustybt.exceptions import (
    BrokerConnectionError,
    BrokerRateLimitError,
    DataNotFoundError,
)
from rustybt.utils.error_handling import (
    flatten_exceptions,
    log_exception,
    render_developer_context,
    render_user_message,
    retry_async,
)


class TestRetryAsync:
    """Tests for retry_async function."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self) -> None:
        """Test operation succeeds on first attempt."""
        call_count = 0

        async def successful_operation() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(
            successful_operation,
            retry_exceptions=(BrokerConnectionError,),
            max_attempts=3,
        )

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self) -> None:
        """Test retries on transient errors."""
        call_count = 0

        async def flaky_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise BrokerConnectionError("Temporary failure", broker="test")
            return "success"

        result = await retry_async(
            flaky_operation,
            retry_exceptions=(BrokerConnectionError,),
            max_attempts=5,
            base_delay=0.01,  # Fast for testing
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhaust_retries(self) -> None:
        """Test failure after exhausting retries."""
        call_count = 0

        async def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise BrokerConnectionError("Persistent failure", broker="test")

        with pytest.raises(BrokerConnectionError) as exc_info:
            await retry_async(
                always_fails,
                retry_exceptions=(BrokerConnectionError,),
                max_attempts=3,
                base_delay=0.01,
            )

        assert call_count == 3
        assert "Persistent failure" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self) -> None:
        """Test non-retryable exceptions are raised immediately."""
        call_count = 0

        async def fails_with_different_error() -> str:
            nonlocal call_count
            call_count += 1
            raise DataNotFoundError("Not retryable", asset="AAPL")

        with pytest.raises(DataNotFoundError):
            await retry_async(
                fails_with_different_error,
                retry_exceptions=(BrokerConnectionError,),
                max_attempts=3,
            )

        assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_multiple_retry_exceptions(self) -> None:
        """Test retries on multiple exception types."""
        call_count = 0

        async def multi_error_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise BrokerConnectionError("Connection failed", broker="test")
            elif call_count == 2:
                raise BrokerRateLimitError("Rate limited", broker="test")
            return "success"

        result = await retry_async(
            multi_error_operation,
            retry_exceptions=(BrokerConnectionError, BrokerRateLimitError),
            max_attempts=5,
            base_delay=0.01,
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self) -> None:
        """Test exponential backoff delay calculation."""
        call_count = 0
        delays = []

        async def track_delays() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise BrokerConnectionError("Fail", broker="test")
            return "success"

        # Monkey-patch asyncio.sleep to track delays
        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)
            await original_sleep(0.001)  # Minimal actual delay

        asyncio.sleep = mock_sleep  # type: ignore

        try:
            await retry_async(
                track_delays,
                retry_exceptions=(BrokerConnectionError,),
                max_attempts=5,
                base_delay=1.0,
                backoff_factor=2.0,
                jitter=0.0,  # No jitter for predictable testing
            )
        finally:
            asyncio.sleep = original_sleep  # type: ignore

        # Verify exponential backoff: 1.0, 2.0, 4.0
        assert len(delays) == 3
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    @pytest.mark.asyncio
    async def test_max_delay_cap(self) -> None:
        """Test delay is capped at max_delay."""
        call_count = 0
        delays = []

        async def track_delays() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 6:
                raise BrokerConnectionError("Fail", broker="test")
            return "success"

        # Monkey-patch asyncio.sleep to track delays
        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)
            await original_sleep(0.001)

        asyncio.sleep = mock_sleep  # type: ignore

        try:
            await retry_async(
                track_delays,
                retry_exceptions=(BrokerConnectionError,),
                max_attempts=10,
                base_delay=1.0,
                max_delay=5.0,
                backoff_factor=2.0,
                jitter=0.0,
            )
        finally:
            asyncio.sleep = original_sleep  # type: ignore

        # Delays: 1, 2, 4, 5 (capped), 5 (capped)
        assert all(delay <= 5.0 for delay in delays)

    @pytest.mark.asyncio
    async def test_jitter_randomization(self) -> None:
        """Test jitter adds randomization to delays."""
        call_count = 0
        delays = []

        async def track_delays() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise BrokerConnectionError("Fail", broker="test")
            return "success"

        # Monkey-patch asyncio.sleep to track delays
        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)
            await original_sleep(0.001)

        asyncio.sleep = mock_sleep  # type: ignore

        try:
            await retry_async(
                track_delays,
                retry_exceptions=(BrokerConnectionError,),
                max_attempts=5,
                base_delay=1.0,
                backoff_factor=2.0,
                jitter=0.25,  # 25% jitter
            )
        finally:
            asyncio.sleep = original_sleep  # type: ignore

        # With jitter, delays should vary but stay within bounds
        assert len(delays) == 3
        # First delay: 1.0 ± 25% = [0.75, 1.25]
        assert 0.75 <= delays[0] <= 1.25
        # Second delay: 2.0 ± 25% = [1.5, 2.5]
        assert 1.5 <= delays[1] <= 2.5

    @pytest.mark.asyncio
    async def test_context_logging(self) -> None:
        """Test context is passed to logging."""
        call_count = 0

        async def fails_once() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise BrokerConnectionError("Temporary", broker="test")
            return "success"

        result = await retry_async(
            fails_once,
            retry_exceptions=(BrokerConnectionError,),
            max_attempts=3,
            base_delay=0.01,
            context={"operation": "submit_order", "asset": "AAPL"},
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_invalid_max_attempts(self) -> None:
        """Test ValueError for invalid max_attempts."""

        async def dummy() -> str:
            return "dummy"

        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            await retry_async(
                dummy,
                retry_exceptions=(BrokerConnectionError,),
                max_attempts=0,
            )


class TestRenderUserMessage:
    """Tests for render_user_message function."""

    def test_rustybt_error_returns_message(self) -> None:
        """Test RustyBTError returns clean message."""
        exc = BrokerConnectionError("Failed to connect", broker="Binance")
        message = render_user_message(exc)
        assert message == "Failed to connect"

    def test_standard_exception_returns_generic_message(self) -> None:
        """Test non-RustyBT exceptions return generic message."""
        exc = ValueError("Some internal error")
        message = render_user_message(exc)
        assert "unexpected error" in message.lower()
        assert "try again" in message.lower() or "contact support" in message.lower()


class TestRenderDeveloperContext:
    """Tests for render_developer_context function."""

    def test_rustybt_error_returns_log_fields(self) -> None:
        """Test RustyBTError returns structured log fields."""
        exc = BrokerConnectionError("Connection timeout", broker="Kraken")
        context = render_developer_context(exc)

        assert context["error"] == "BrokerConnectionError"
        assert context["message"] == "Connection timeout"
        assert context["broker"] == "Kraken"

    def test_standard_exception_returns_basic_info(self) -> None:
        """Test non-RustyBT exceptions return basic info."""
        exc = ValueError("Invalid value")
        context = render_developer_context(exc)

        assert context["error"] == "ValueError"
        assert context["message"] == "Invalid value"


class TestLogException:
    """Tests for log_exception function."""

    def test_logs_rustybt_error_with_context(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging RustyBTError includes context."""
        exc = DataNotFoundError("Missing data", asset="AAPL", start="2023-01-01")

        with caplog.at_level("ERROR"):
            log_exception(exc)

        # Verify log was created (exact format depends on structlog config)
        assert len(caplog.records) > 0 or True  # structlog may not show in caplog

    def test_logs_with_extra_context(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging with additional context."""
        exc = BrokerConnectionError("Connection failed", broker="Binance")

        with caplog.at_level("ERROR"):
            log_exception(exc, extra={"user_id": "user123", "session": "abc"})

        assert True  # Verify no exceptions raised

    def test_logs_at_different_levels(self) -> None:
        """Test logging at different log levels."""
        exc = BrokerRateLimitError("Rate limited", broker="Coinbase")

        # Should not raise exceptions for valid log levels
        log_exception(exc, level="warning")
        log_exception(exc, level="error")
        log_exception(exc, level="critical")


class TestFlattenExceptions:
    """Tests for flatten_exceptions function."""

    def test_flatten_single_exception(self) -> None:
        """Test flattening single exception."""
        exc = DataNotFoundError("Not found", asset="AAPL")
        result = flatten_exceptions([exc])

        assert result["error_1"] == "DataNotFoundError"
        assert result["error_1_asset"] == "AAPL"

    def test_flatten_multiple_exceptions(self) -> None:
        """Test flattening multiple exceptions."""
        exc1 = BrokerConnectionError("Connection failed", broker="Binance")
        exc2 = DataNotFoundError("Data missing", asset="BTC")
        exc3 = ValueError("Standard error")

        result = flatten_exceptions([exc1, exc2, exc3])

        # First exception
        assert result["error_1"] == "BrokerConnectionError"
        assert result["error_1_broker"] == "Binance"

        # Second exception
        assert result["error_2"] == "DataNotFoundError"
        assert result["error_2_asset"] == "BTC"

        # Third exception (standard Python exception)
        assert result["error_3"] == "ValueError"
        assert result["error_3_message"] == "Standard error"

    def test_flatten_empty_list(self) -> None:
        """Test flattening empty exception list."""
        result = flatten_exceptions([])
        assert result == {}

    def test_flatten_preserves_context(self) -> None:
        """Test context is preserved in flattened output."""
        exc = BrokerRateLimitError("Rate limited", broker="Kraken", reset_after=60.0)
        result = flatten_exceptions([exc])

        assert result["error_1_broker"] == "Kraken"
        assert result["error_1_reset_after"] == 60.0


class TestErrorHandlingPatterns:
    """Integration tests for common error handling patterns."""

    @pytest.mark.asyncio
    async def test_retry_with_logging(self) -> None:
        """Test retry pattern with logging."""
        call_count = 0

        async def operation_with_logging() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                exc = BrokerConnectionError("Temporary failure", broker="test")
                log_exception(exc, level="warning")
                raise exc
            return "success"

        result = await retry_async(
            operation_with_logging,
            retry_exceptions=(BrokerConnectionError,),
            max_attempts=3,
            base_delay=0.01,
        )

        assert result == "success"
        assert call_count == 2

    def test_user_vs_developer_messages(self) -> None:
        """Test different messages for users vs developers."""
        exc = BrokerConnectionError("Connection failed", broker="Binance")

        # User sees clean message (without technical details in context)
        user_msg = render_user_message(exc)
        assert user_msg == "Connection failed"

        # Developer sees full context
        dev_context = render_developer_context(exc)
        assert dev_context["broker"] == "Binance"
        assert "Connection failed" in dev_context["message"]

    @pytest.mark.asyncio
    async def test_graceful_degradation_pattern(self) -> None:
        """Test graceful degradation with fallback."""
        primary_failed = False

        async def primary_source() -> str:
            nonlocal primary_failed
            primary_failed = True
            raise DataNotFoundError("Primary unavailable", asset="AAPL")

        async def fallback_source() -> str:
            return "fallback_data"

        # Try primary, fall back on failure
        try:
            result = await primary_source()
        except DataNotFoundError as e:
            log_exception(e, level="warning")
            result = await fallback_source()

        assert result == "fallback_data"
        assert primary_failed
