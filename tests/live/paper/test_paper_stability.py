"""Paper trading stability and long-running tests.

This module provides tests for paper trading long-running stability:
- 24+ hour continuous operation tests
- Memory monitoring and leak detection
- State integrity verification during extended operation

Story: 10.2.2 - Paper Trading State Persistence & Long-Running Stability

Note: Long-running tests are marked with @pytest.mark.slow and can be
configured via STABILITY_TEST_DURATION_SECONDS environment variable.
For CI, use shorter durations (e.g., 60 seconds).
For nightly builds, use longer durations (e.g., 3600+ seconds).
"""

import asyncio
import gc
import json
import os
import random
import tracemalloc
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from rustybt.assets import Equity, ExchangeInfo
from rustybt.live.brokers.paper_broker import PaperBroker

from .conftest import DeterministicStrategy, SignalPattern, SignalType, create_bar_data

# =============================================================================
# Configuration
# =============================================================================


def get_stability_test_duration() -> int:
    """Get stability test duration from environment variable.

    Returns:
        Duration in seconds. Default: 60 seconds for tests.
        Set STABILITY_TEST_DURATION_SECONDS for longer durations.
    """
    return int(os.environ.get("STABILITY_TEST_DURATION_SECONDS", "60"))


def get_memory_sample_interval() -> int:
    """Get memory sample interval from environment variable.

    Returns:
        Interval in seconds. Default: 10 seconds.
    """
    return int(os.environ.get("MEMORY_SAMPLE_INTERVAL_SECONDS", "10"))


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_asset() -> Equity:
    """Create sample equity asset for testing."""
    exchange_info = ExchangeInfo("NASDAQ", "NASDAQ", "US")
    return Equity(1, exchange_info, symbol="STAB")


@pytest.fixture
def paper_broker_stable() -> PaperBroker:
    """Create PaperBroker configured for stability testing."""
    return PaperBroker(
        starting_cash=Decimal("1000000"),  # Large cash for many trades
        order_latency_ms=1,
        latency_jitter_pct=Decimal("0"),
    )


@pytest.fixture
def memory_log_path(tmp_path) -> Path:
    """Create path for memory log file."""
    return tmp_path / "memory_log.json"


# =============================================================================
# Memory Monitoring Utilities
# =============================================================================


class MemoryMonitor:
    """Memory monitoring utility for stability tests.

    Tracks memory usage over time and detects potential leaks.
    """

    def __init__(self, log_path: Path | None = None):
        """Initialize MemoryMonitor.

        Args:
            log_path: Optional path to write memory samples as JSON
        """
        self.log_path = log_path
        self.samples: list[dict] = []
        self.start_memory: int = 0
        self.peak_memory: int = 0

    def start(self) -> None:
        """Start memory tracing."""
        gc.collect()  # Clean up before measuring
        tracemalloc.start()
        current, _ = tracemalloc.get_traced_memory()
        self.start_memory = current

    def sample(self) -> dict:
        """Take a memory sample.

        Returns:
            Dict with timestamp, current, and peak memory in MB
        """
        current, peak = tracemalloc.get_traced_memory()
        self.peak_memory = max(self.peak_memory, peak)

        sample = {
            "timestamp": datetime.now().isoformat(),
            "current_mb": current / (1024 * 1024),
            "peak_mb": peak / (1024 * 1024),
            "growth_mb": (current - self.start_memory) / (1024 * 1024),
        }
        self.samples.append(sample)
        return sample

    def stop(self) -> None:
        """Stop memory tracing and save log."""
        if self.log_path:
            with open(self.log_path, "w") as f:
                json.dump(self.samples, f, indent=2)
        tracemalloc.stop()

    def get_growth_percentage(self) -> float:
        """Calculate memory growth percentage.

        Returns:
            Growth as percentage (e.g., 5.0 for 5% growth)
        """
        if not self.samples or self.start_memory == 0:
            return 0.0

        final_memory = self.samples[-1]["current_mb"] * (1024 * 1024)
        growth = (final_memory - self.start_memory) / self.start_memory * 100
        return growth

    def has_significant_leak(self, threshold_pct: float = 10.0) -> bool:
        """Check if memory growth exceeds threshold.

        Args:
            threshold_pct: Threshold percentage (default: 10%)

        Returns:
            True if growth exceeds threshold
        """
        return self.get_growth_percentage() > threshold_pct


# =============================================================================
# State Integrity Verifier
# =============================================================================


class StateIntegrityVerifier:
    """Verifies state integrity during long-running operations."""

    def __init__(self, broker: PaperBroker):
        """Initialize verifier with broker.

        Args:
            broker: PaperBroker instance to verify
        """
        self.broker = broker
        self.discrepancies: list[str] = []

    async def verify(self) -> bool:
        """Verify current state integrity.

        Returns:
            True if state is valid, False if discrepancies found
        """
        is_valid = True

        # Verify cash is non-negative (for normal operation)
        if self.broker.cash < Decimal("0"):
            self.discrepancies.append(f"Negative cash: {self.broker.cash}")
            is_valid = False

        # Verify position calculations
        for asset, position in self.broker.positions.items():
            # Check position amount is finite
            if not position.amount.is_finite():
                self.discrepancies.append(f"Non-finite position amount for {asset}")
                is_valid = False

            # Check cost basis is positive (for existing positions)
            if position.amount != Decimal("0") and position.cost_basis <= Decimal("0"):
                self.discrepancies.append(f"Invalid cost basis for {asset}: {position.cost_basis}")
                is_valid = False

        # Verify order tracking consistency
        for order_id, order in self.broker.orders.items():
            # Check filled <= amount
            if abs(order.filled) > abs(order.amount):
                self.discrepancies.append(
                    f"Over-filled order {order_id}: {order.filled} > {order.amount}"
                )
                is_valid = False

        return is_valid

    def get_discrepancies(self) -> list[str]:
        """Get list of discrepancies found."""
        return self.discrepancies.copy()


# =============================================================================
# AC3: Long-Running Stability Tests
# =============================================================================


class TestLongRunningStability:
    """Tests for AC3: Paper trading runs stably for extended periods."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_continuous_operation_no_crashes(self, paper_broker_stable, sample_asset):
        """Test paper trading runs without crashes for configured duration.

        This test runs continuously, executing periodic trades, and monitors
        for exceptions or crashes. Duration is configurable via environment.
        """
        duration_seconds = get_stability_test_duration()
        broker = paper_broker_stable
        await broker.connect()

        start_time = datetime.now()
        end_time = start_time
        iteration = 0
        exceptions_caught: list[str] = []

        # Initial market data
        current_price = Decimal("100.00")
        broker._update_market_data(sample_asset, create_bar_data(current_price))

        while (end_time - start_time).total_seconds() < duration_seconds:
            try:
                # Simulate price movement
                price_change = Decimal(str(random.uniform(-2, 2)))
                current_price = max(Decimal("50"), current_price + price_change)
                broker._update_market_data(sample_asset, create_bar_data(current_price))

                # Execute trade periodically
                if iteration % 10 == 0:  # Trade every 10 iterations
                    # Alternate buy/sell to keep position manageable
                    if iteration % 20 == 0:
                        await broker.submit_order(
                            asset=sample_asset,
                            amount=Decimal("10"),
                            order_type="market",
                        )
                    else:
                        # Only sell if we have position
                        if (
                            sample_asset in broker.positions
                            and broker.positions[sample_asset].amount > 0
                        ):
                            await broker.submit_order(
                                asset=sample_asset,
                                amount=Decimal("-5"),
                                order_type="market",
                            )

                # Small delay to simulate real-time operation
                await asyncio.sleep(0.01)

                iteration += 1
                end_time = datetime.now()

            except Exception as e:
                exceptions_caught.append(f"Iteration {iteration}: {str(e)}")

        # Wait for pending orders to complete
        await asyncio.sleep(0.5)

        # Verify no exceptions
        assert len(exceptions_caught) == 0, f"Exceptions during test: {exceptions_caught}"

        # Verify broker is still responsive
        account = await broker.get_account_info()
        assert "cash" in account
        assert broker.is_connected()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_session_remains_responsive(self, paper_broker_stable, sample_asset):
        """Test that session remains responsive throughout duration."""
        duration_seconds = min(get_stability_test_duration(), 30)  # Cap for this test
        broker = paper_broker_stable
        await broker.connect()

        broker._update_market_data(sample_asset, create_bar_data(Decimal("100.00")))

        start_time = datetime.now()
        response_times: list[float] = []

        while (datetime.now() - start_time).total_seconds() < duration_seconds:
            # Measure response time for account info query
            query_start = datetime.now()
            await broker.get_account_info()
            query_time = (datetime.now() - query_start).total_seconds()
            response_times.append(query_time)

            await asyncio.sleep(0.5)

        # Check response times are reasonable (< 1 second)
        assert len(response_times) > 0
        assert max(response_times) < 1.0, f"Slow response: {max(response_times)}s"
        assert sum(response_times) / len(response_times) < 0.1, "Average response too slow"


# =============================================================================
# AC4: Memory Stability Tests
# =============================================================================


class TestMemoryStability:
    """Tests for AC4: Memory usage remains stable during long-running operation."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_memory_growth_under_threshold(
        self, paper_broker_stable, sample_asset, memory_log_path
    ):
        """Test that memory growth stays under 10% during operation."""
        duration_seconds = get_stability_test_duration()
        sample_interval = get_memory_sample_interval()
        broker = paper_broker_stable

        monitor = MemoryMonitor(log_path=memory_log_path)
        monitor.start()

        await broker.connect()

        broker._update_market_data(sample_asset, create_bar_data(Decimal("100.00")))

        start_time = datetime.now()
        last_sample_time = start_time
        iteration = 0

        while (datetime.now() - start_time).total_seconds() < duration_seconds:
            # Execute trades to stress memory
            if iteration % 5 == 0:
                await broker.submit_order(
                    asset=sample_asset,
                    amount=Decimal("1"),
                    order_type="market",
                )
                await asyncio.sleep(0.02)

            # Periodic memory sample
            if (datetime.now() - last_sample_time).total_seconds() >= sample_interval:
                monitor.sample()
                last_sample_time = datetime.now()

            iteration += 1
            await asyncio.sleep(0.001)

        # Final sample
        monitor.sample()
        monitor.stop()

        # Verify memory growth
        growth_pct = monitor.get_growth_percentage()
        assert growth_pct < 10.0, f"Memory growth {growth_pct:.2f}% exceeds 10% threshold"

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_no_memory_leak_detected(self, paper_broker_stable, sample_asset):
        """Test that no memory leak is detected during operation."""
        broker = paper_broker_stable
        monitor = MemoryMonitor()
        monitor.start()

        await broker.connect()

        broker._update_market_data(sample_asset, create_bar_data(Decimal("100.00")))

        # Run many iterations to detect leaks
        for i in range(100):
            await broker.submit_order(
                asset=sample_asset,
                amount=Decimal("1"),
                order_type="market",
            )
            await asyncio.sleep(0.01)

            if i % 20 == 0:
                monitor.sample()
                gc.collect()  # Force garbage collection

        monitor.sample()
        monitor.stop()

        # Check for significant leak
        assert not monitor.has_significant_leak(10.0)


# =============================================================================
# AC5: State Integrity During Extended Operation
# =============================================================================


class TestStateIntegrityExtended:
    """Tests for AC5: No state corruption occurs during extended operation."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_position_tracking_remains_accurate(self, paper_broker_stable, sample_asset):
        """Test that position tracking remains accurate over time."""
        duration_seconds = min(get_stability_test_duration(), 30)
        broker = paper_broker_stable
        verifier = StateIntegrityVerifier(broker)

        await broker.connect()

        broker._update_market_data(sample_asset, create_bar_data(Decimal("100.00")))

        start_time = datetime.now()
        verification_failures: list[str] = []

        while (datetime.now() - start_time).total_seconds() < duration_seconds:
            # Execute random trades
            amount = Decimal(str(random.randint(1, 10)))
            if random.random() > 0.5:
                await broker.submit_order(
                    asset=sample_asset,
                    amount=amount,
                    order_type="market",
                )
            else:
                if (
                    sample_asset in broker.positions
                    and broker.positions[sample_asset].amount >= amount
                ):
                    await broker.submit_order(
                        asset=sample_asset,
                        amount=-amount,
                        order_type="market",
                    )

            await asyncio.sleep(0.02)

            # Periodic verification
            if not await verifier.verify():
                verification_failures.extend(verifier.get_discrepancies())

        # No integrity issues should be found
        assert len(verification_failures) == 0, f"State integrity issues: {verification_failures}"

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_calculations_remain_correct(self, paper_broker_stable, sample_asset):
        """Test that all calculations remain correct over time."""
        broker = paper_broker_stable
        await broker.connect()

        initial_cash = broker.cash

        broker._update_market_data(sample_asset, create_bar_data(Decimal("100.00")))

        # Track expected vs actual
        expected_position = Decimal("0")
        expected_cash = initial_cash

        for i in range(50):
            price = Decimal("100.00") + Decimal(str(i % 10))
            broker._update_market_data(sample_asset, create_bar_data(price))

            amount = Decimal("10") if i % 2 == 0 else Decimal("-10")

            # Can only sell if we have position
            if amount < 0 and expected_position < abs(amount):
                continue

            await broker.submit_order(
                asset=sample_asset,
                amount=amount,
                order_type="market",
            )
            await asyncio.sleep(0.02)

            # Update expected values
            expected_position += amount
            if amount > 0:
                expected_cash -= amount * price
            else:
                expected_cash += abs(amount) * price

        await asyncio.sleep(0.2)

        # Verify calculations
        actual_position = broker.positions.get(sample_asset)
        if expected_position == Decimal("0"):
            assert actual_position is None or actual_position.amount == Decimal("0")
        else:
            assert actual_position is not None
            assert actual_position.amount == expected_position

        # Cash should match (within small tolerance for order timing)
        assert abs(broker.cash - expected_cash) < Decimal("1.00")


# =============================================================================
# Stability Test Markers
# =============================================================================


class TestStabilityMarkers:
    """Tests for stability test configuration and markers."""

    def test_duration_configurable(self):
        """Test that test duration is configurable via environment."""
        # Default should be 60 seconds
        os.environ.pop("STABILITY_TEST_DURATION_SECONDS", None)
        assert get_stability_test_duration() == 60

        # Should read from environment
        os.environ["STABILITY_TEST_DURATION_SECONDS"] = "3600"
        assert get_stability_test_duration() == 3600

        # Cleanup
        os.environ.pop("STABILITY_TEST_DURATION_SECONDS", None)

    def test_memory_interval_configurable(self):
        """Test that memory sample interval is configurable."""
        os.environ.pop("MEMORY_SAMPLE_INTERVAL_SECONDS", None)
        assert get_memory_sample_interval() == 10

        os.environ["MEMORY_SAMPLE_INTERVAL_SECONDS"] = "60"
        assert get_memory_sample_interval() == 60

        os.environ.pop("MEMORY_SAMPLE_INTERVAL_SECONDS", None)

    def test_memory_monitor_basic(self):
        """Test MemoryMonitor basic functionality."""
        monitor = MemoryMonitor()
        monitor.start()

        # Allocate some memory
        data = [i for i in range(100000)]

        sample = monitor.sample()
        assert "current_mb" in sample
        assert "peak_mb" in sample
        assert sample["current_mb"] > 0

        monitor.stop()

        del data  # Cleanup

    def test_memory_monitor_growth_calculation(self):
        """Test MemoryMonitor growth calculation."""
        monitor = MemoryMonitor()
        monitor.start()

        # Initial sample
        monitor.sample()

        # Growth should be minimal for no allocation
        growth = monitor.get_growth_percentage()
        assert growth < 100  # Reasonable upper bound

        monitor.stop()
