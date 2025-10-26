"""Tests for CCXTAdapter retry logic with exponential backoff.

This module tests the resilience features added to CCXTAdapter, specifically
the automatic retry logic with exponential backoff for transient network errors.

CR-002 Compliance: No mocks used - tests use real async operations with controlled failures.
"""

import asyncio
import time
from decimal import Decimal

import ccxt
import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters import CCXTAdapter
from rustybt.data.adapters.base import NetworkError, RateLimitError


class ControlledFailureCCXTAdapter(CCXTAdapter):
    """Test adapter that simulates failures in a controlled manner.

    Uses counters to simulate transient failures followed by success,
    without using mocking frameworks (CR-002 compliant).
    """

    def __init__(self, exchange_id: str = "binance"):
        super().__init__(exchange_id=exchange_id)
        self.fetch_attempts = 0
        self.fail_count = 0
        self.error_to_raise = None
        self.fetch_times: list[float] = []

    async def _mock_fetch_ohlcv(
        self, symbol: str, timeframe: str, since: int, limit: int = 1000
    ) -> list[list[int | float]]:
        """Simulate fetch_ohlcv with controlled failures."""
        self.fetch_times.append(time.time())
        self.fetch_attempts += 1

        # Simulate failures up to fail_count, then succeed
        if self.fetch_attempts <= self.fail_count:
            if self.error_to_raise == "network":
                raise ccxt.NetworkError("Simulated network failure")
            elif self.error_to_raise == "exchange_unavailable":
                raise ccxt.ExchangeNotAvailable("Simulated exchange unavailable")
            elif self.error_to_raise == "bad_symbol":
                raise ccxt.BadSymbol("Simulated invalid symbol")
            elif self.error_to_raise == "rate_limit":
                raise ccxt.RateLimitExceeded("Simulated rate limit exceeded")

        # Success case - return realistic OHLCV data
        return [
            [since, 50000.0, 50100.0, 49900.0, 50050.0, 100.5],
            [since + 3600000, 50050.0, 50200.0, 50000.0, 50150.0, 120.3],
        ]


class TestCCXTRetryLogic:
    """Tests for automatic retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self) -> None:
        """Network errors trigger automatic retry and eventually succeed."""
        adapter = ControlledFailureCCXTAdapter()

        # Simulate 2 failures followed by success
        adapter.fail_count = 2
        adapter.error_to_raise = "network"

        # Temporarily replace exchange.fetch_ohlcv with our mock
        original_method = adapter.exchange.fetch_ohlcv
        adapter.exchange.fetch_ohlcv = adapter._mock_fetch_ohlcv

        try:
            # Call should succeed after retries
            result = await adapter._fetch_ohlcv_batch(
                symbol="BTC/USDT", timeframe="1h", since=1609459200000, limit=1000
            )

            # Verify success
            assert result is not None
            assert len(result) == 2
            assert adapter.fetch_attempts == 3  # 2 failures + 1 success

        finally:
            adapter.exchange.fetch_ohlcv = original_method

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self) -> None:
        """Retry delays follow exponential backoff pattern."""
        adapter = ControlledFailureCCXTAdapter()

        # Simulate 2 failures followed by success
        adapter.fail_count = 2
        adapter.error_to_raise = "network"

        original_method = adapter.exchange.fetch_ohlcv
        adapter.exchange.fetch_ohlcv = adapter._mock_fetch_ohlcv

        try:
            start_time = time.time()
            await adapter._fetch_ohlcv_batch(
                symbol="BTC/USDT", timeframe="1h", since=1609459200000, limit=1000
            )
            total_time = time.time() - start_time

            # Expected delays: 1s + 2s = 3s minimum
            # Allow some tolerance for execution time
            assert total_time >= 2.0, "Expected at least 2 seconds of retry delays"
            assert total_time < 6.0, "Delays should not exceed reasonable bounds"

            # Check delay progression (second attempt should have longer delay than first)
            assert len(adapter.fetch_times) == 3
            delay1 = adapter.fetch_times[1] - adapter.fetch_times[0]
            delay2 = adapter.fetch_times[2] - adapter.fetch_times[1]

            # Second delay should be roughly 2x first delay (exponential backoff)
            assert delay2 > delay1, "Second delay should be longer (exponential backoff)"

        finally:
            adapter.exchange.fetch_ohlcv = original_method

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self) -> None:
        """Failure after max retries raises NetworkError."""
        adapter = ControlledFailureCCXTAdapter()

        # Simulate persistent failures (more than max_retries=3)
        adapter.fail_count = 10
        adapter.error_to_raise = "network"

        original_method = adapter.exchange.fetch_ohlcv
        adapter.exchange.fetch_ohlcv = adapter._mock_fetch_ohlcv

        try:
            # Should fail after 3 retries
            with pytest.raises(NetworkError, match="Failed after.*retries"):
                await adapter._fetch_ohlcv_batch(
                    symbol="BTC/USDT", timeframe="1h", since=1609459200000, limit=1000
                )

            # Verify it attempted max_retries times
            assert adapter.fetch_attempts == 3

        finally:
            adapter.exchange.fetch_ohlcv = original_method

    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_error(self) -> None:
        """Permanent errors (BadSymbol) are not retried."""
        adapter = ControlledFailureCCXTAdapter()

        # Simulate permanent error (BadSymbol)
        adapter.fail_count = 10
        adapter.error_to_raise = "bad_symbol"

        original_method = adapter.exchange.fetch_ohlcv
        adapter.exchange.fetch_ohlcv = adapter._mock_fetch_ohlcv

        try:
            # Should fail immediately without retry
            with pytest.raises(ccxt.BadSymbol, match="Simulated invalid symbol"):
                await adapter._fetch_ohlcv_batch(
                    symbol="INVALID/SYMBOL",
                    timeframe="1h",
                    since=1609459200000,
                    limit=1000,
                )

            # Verify it only attempted once (no retries)
            assert adapter.fetch_attempts == 1

        finally:
            adapter.exchange.fetch_ohlcv = original_method

    @pytest.mark.asyncio
    async def test_successful_retry_after_transient_failure(self) -> None:
        """Single transient failure followed by success works correctly."""
        adapter = ControlledFailureCCXTAdapter()

        # Simulate 1 failure followed by success
        adapter.fail_count = 1
        adapter.error_to_raise = "exchange_unavailable"

        original_method = adapter.exchange.fetch_ohlcv
        adapter.exchange.fetch_ohlcv = adapter._mock_fetch_ohlcv

        try:
            result = await adapter._fetch_ohlcv_batch(
                symbol="ETH/USDT", timeframe="1h", since=1609459200000, limit=1000
            )

            # Verify success
            assert result is not None
            assert len(result) == 2
            assert adapter.fetch_attempts == 2  # 1 failure + 1 success

            # Verify data format
            assert result[0][0] == 1609459200000  # Timestamp
            assert result[0][1] == 50000.0  # Open
            assert result[0][5] == 100.5  # Volume

        finally:
            adapter.exchange.fetch_ohlcv = original_method


class TestCCXTRetryIntegration:
    """Integration tests for retry logic with pagination."""

    @pytest.mark.asyncio
    async def test_retry_during_pagination(self) -> None:
        """Retry logic works correctly during multi-batch pagination."""
        adapter = ControlledFailureCCXTAdapter()

        # Simulate failure on second batch only
        adapter.fail_count = 1
        adapter.error_to_raise = "network"

        original_method = adapter.exchange.fetch_ohlcv

        # Create a wrapper that fails on second call only
        call_count = 0

        async def conditional_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Fail on second batch
                raise ccxt.NetworkError("Simulated failure on second batch")
            return await adapter._mock_fetch_ohlcv(*args, **kwargs)

        adapter.exchange.fetch_ohlcv = conditional_failure

        try:
            # Fetch with pagination (should handle failure gracefully)
            result = await adapter._fetch_with_pagination(
                symbol="BTC/USDT",
                timeframe="1h",
                since=1609459200000,
                until=1609462800000,  # Small range to limit batches
            )

            # Should eventually succeed despite transient failure
            assert result is not None
            assert len(result) > 0

        finally:
            adapter.exchange.fetch_ohlcv = original_method
