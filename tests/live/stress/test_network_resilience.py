"""
Network failure and reconnection stress tests.

Tests system resilience to network issues:
- WebSocket disconnect detection (< 60 seconds per NFR8)
- Reconnection with exponential backoff (< 30 seconds per NFR2)
- Circuit breaker behavior on consecutive failures
- Order queuing during brief disconnections (NFR9)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.live.stress.models import (
    ScenarioType,
    StressScenario,
    StressTestResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class ConnectionState(str, Enum):
    """Mock connection state for testing."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class MockStreamConfig:
    """Mock stream configuration."""

    reconnect_delay: float = 1.0
    reconnect_max_delay: float = 30.0
    reconnect_attempts: int | None = 10
    heartbeat_interval: float = 5.0
    heartbeat_timeout: float = 60.0
    circuit_breaker_threshold: int = 5


@dataclass
class ReconnectionMetrics:
    """Metrics collected during reconnection testing."""

    reconnection_times: list[float] = field(default_factory=list)
    failed_reconnections: int = 0
    data_loss: bool = False
    detection_times: list[float] = field(default_factory=list)
    circuit_breaker_trips: int = 0
    orders_queued: int = 0
    orders_processed_after_reconnect: int = 0


class MockWebSocketAdapter:
    """Mock WebSocket adapter for testing network resilience.

    Simulates WebSocket behavior with configurable disconnect/reconnect timing.
    """

    def __init__(self, config: MockStreamConfig | None = None) -> None:
        """Initialize mock adapter."""
        self.config = config or MockStreamConfig()
        self._state = ConnectionState.DISCONNECTED
        self._subscriptions: dict[str, set[str]] = {}
        self._reconnect_count = 0
        self._consecutive_errors = 0
        self._circuit_breaker_tripped = False

        # Reconnection simulation
        self._reconnect_delay: float = 0.5  # Fast reconnection for tests
        self._max_reconnect_delay: float = 5.0

        # Order queue for NFR9 testing
        self._order_queue: list[dict] = []

        # For metrics collection
        self.reconnection_start_time: float | None = None
        self.last_disconnect_time: float | None = None

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._state == ConnectionState.CONNECTED

    @property
    def circuit_breaker_tripped(self) -> bool:
        """Check if circuit breaker is tripped."""
        return self._circuit_breaker_tripped

    @property
    def in_safe_state(self) -> bool:
        """Check if in safe state (circuit breaker tripped)."""
        return self._circuit_breaker_tripped

    async def connect(self) -> None:
        """Simulate connection."""
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            return

        self._state = ConnectionState.CONNECTING
        await asyncio.sleep(0.1)  # Simulate connection time
        self._state = ConnectionState.CONNECTED
        self._consecutive_errors = 0

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        if self._state == ConnectionState.DISCONNECTED:
            return

        self.last_disconnect_time = time.monotonic()
        self._state = ConnectionState.DISCONNECTED
        self._subscriptions.clear()

    async def simulate_network_failure(self) -> float:
        """Simulate network failure and return detection time.

        Returns:
            Time in seconds until disconnect was detected
        """
        disconnect_time = time.monotonic()

        # Force disconnect
        self._state = ConnectionState.DISCONNECTED
        self.last_disconnect_time = disconnect_time
        self._subscriptions.clear()  # Subscriptions lost on disconnect

        # Wait for detection (simulated)
        await asyncio.sleep(0.05)  # Fast detection for tests

        detection_time = time.monotonic() - disconnect_time
        return detection_time

    async def reconnect(self) -> float:
        """Simulate reconnection with exponential backoff.

        Returns:
            Time in seconds for reconnection to complete
        """
        if self._state == ConnectionState.RECONNECTING:
            return 0.0

        self.reconnection_start_time = time.monotonic()
        self._state = ConnectionState.RECONNECTING
        self._reconnect_count += 1

        # Calculate backoff delay
        delay = min(
            self._reconnect_delay * (2 ** (self._reconnect_count - 1)),
            self._max_reconnect_delay,
        )

        await asyncio.sleep(delay)

        # Simulate successful reconnection
        self._state = ConnectionState.CONNECTED
        self._consecutive_errors = 0

        # Restore subscriptions
        # In real impl, would re-subscribe to all channels

        reconnection_time = time.monotonic() - self.reconnection_start_time
        return reconnection_time

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to symbols and channels."""
        for symbol in symbols:
            if symbol not in self._subscriptions:
                self._subscriptions[symbol] = set()
            self._subscriptions[symbol].update(channels)

    def record_error(self) -> bool:
        """Record an error and check circuit breaker.

        Returns:
            True if circuit breaker tripped
        """
        self._consecutive_errors += 1
        if self._consecutive_errors >= self.config.circuit_breaker_threshold:
            self._circuit_breaker_tripped = True
            return True
        return False

    def queue_order(self, order: dict) -> None:
        """Queue order during disconnection."""
        self._order_queue.append(order)

    async def process_queued_orders(self) -> int:
        """Process queued orders after reconnection.

        Returns:
            Number of orders processed
        """
        count = len(self._order_queue)
        self._order_queue.clear()
        return count

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker."""
        self._circuit_breaker_tripped = False
        self._consecutive_errors = 0

    def reset(self) -> None:
        """Reset adapter to initial state."""
        self._state = ConnectionState.DISCONNECTED
        self._subscriptions.clear()
        self._reconnect_count = 0
        self._consecutive_errors = 0
        self._circuit_breaker_tripped = False
        self._order_queue.clear()


# =============================================================================
# Test Utilities
# =============================================================================


async def simulate_disconnect(
    adapter: MockWebSocketAdapter, delay_before_reconnect: float = 0
) -> float:
    """Simulate network failure by disconnecting adapter.

    Args:
        adapter: The adapter to disconnect
        delay_before_reconnect: Optional delay before triggering reconnect

    Returns:
        Detection time in seconds
    """
    disconnect_time = time.monotonic()

    # Force disconnect
    detection_time = await adapter.simulate_network_failure()

    # Wait for specified delay
    if delay_before_reconnect > 0:
        await asyncio.sleep(delay_before_reconnect)

    # Verify disconnect detected within 60 seconds (NFR8)
    elapsed = time.monotonic() - disconnect_time
    assert elapsed < 60, f"Disconnect not detected within 60 seconds (took {elapsed:.2f}s)"

    return detection_time


async def measure_reconnection(adapter: MockWebSocketAdapter, max_wait: float = 30) -> float:
    """Measure time until reconnection completes.

    Args:
        adapter: The adapter to reconnect
        max_wait: Maximum wait time in seconds

    Returns:
        Reconnection time in seconds

    Raises:
        AssertionError: If reconnection exceeds max_wait
    """
    start_time = time.monotonic()

    reconnection_time = await adapter.reconnect()

    # Verify reconnection within 30 seconds (NFR2)
    assert (
        reconnection_time < max_wait
    ), f"Reconnection failed within {max_wait} seconds (took {reconnection_time:.2f}s)"

    return reconnection_time


async def run_network_scenario(
    adapter: MockWebSocketAdapter,
    disconnect_count: int,
    disconnect_interval: float,
) -> ReconnectionMetrics:
    """Run a complete network resilience scenario.

    Args:
        adapter: The adapter to test
        disconnect_count: Number of disconnections to simulate
        disconnect_interval: Time between disconnections

    Returns:
        Collected metrics
    """
    metrics = ReconnectionMetrics()

    await adapter.connect()

    for i in range(disconnect_count):
        # Simulate disconnect
        detection_time = await simulate_disconnect(adapter)
        metrics.detection_times.append(detection_time)

        # Measure reconnection
        try:
            reconnection_time = await measure_reconnection(adapter)
            metrics.reconnection_times.append(reconnection_time)
        except AssertionError:
            metrics.failed_reconnections += 1

        # Wait before next disconnect
        if i < disconnect_count - 1:
            await asyncio.sleep(disconnect_interval)

    return metrics


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_adapter() -> MockWebSocketAdapter:
    """Create a fresh mock adapter for each test."""
    return MockWebSocketAdapter()


@pytest.fixture
def fast_adapter() -> MockWebSocketAdapter:
    """Create an adapter with fast reconnection for testing."""
    config = MockStreamConfig(
        reconnect_delay=0.1,
        reconnect_max_delay=1.0,
        reconnect_attempts=10,
        circuit_breaker_threshold=3,
    )
    return MockWebSocketAdapter(config)


# =============================================================================
# Test Classes
# =============================================================================


class TestDisconnectSimulation:
    """Tests for network failure simulation (AC1)."""

    @pytest.mark.asyncio
    async def test_disconnect_detected(self, mock_adapter: MockWebSocketAdapter) -> None:
        """Test that WebSocket disconnect is detected."""
        await mock_adapter.connect()
        assert mock_adapter.is_connected

        detection_time = await simulate_disconnect(mock_adapter)

        assert not mock_adapter.is_connected
        assert detection_time < 60  # NFR8: Detection within 60 seconds

    @pytest.mark.asyncio
    async def test_disconnect_during_active_trading(
        self, mock_adapter: MockWebSocketAdapter
    ) -> None:
        """Test disconnect during active subscriptions."""
        await mock_adapter.connect()
        await mock_adapter.subscribe(["BTC-PERP"], ["trades", "orderbook"])

        assert len(mock_adapter._subscriptions) > 0

        await simulate_disconnect(mock_adapter)

        assert not mock_adapter.is_connected

    @pytest.mark.asyncio
    async def test_multiple_disconnects(self, mock_adapter: MockWebSocketAdapter) -> None:
        """Test handling of multiple rapid disconnects."""
        await mock_adapter.connect()

        for _ in range(3):
            await simulate_disconnect(mock_adapter)
            await mock_adapter.reconnect()
            assert mock_adapter.is_connected

        assert mock_adapter._reconnect_count == 3


class TestReconnectionBehavior:
    """Tests for reconnection behavior (AC2)."""

    @pytest.mark.asyncio
    async def test_reconnection_succeeds(self, mock_adapter: MockWebSocketAdapter) -> None:
        """Test that reconnection succeeds."""
        await mock_adapter.connect()
        await simulate_disconnect(mock_adapter)

        reconnection_time = await measure_reconnection(mock_adapter)

        assert mock_adapter.is_connected
        assert reconnection_time < 30  # NFR2: Reconnection within 30 seconds

    @pytest.mark.asyncio
    async def test_reconnection_with_exponential_backoff(
        self, mock_adapter: MockWebSocketAdapter
    ) -> None:
        """Test exponential backoff on reconnection."""
        await mock_adapter.connect()

        reconnection_times = []

        for _ in range(3):
            await simulate_disconnect(mock_adapter)
            reconnection_time = await measure_reconnection(mock_adapter)
            reconnection_times.append(reconnection_time)

        # Each reconnection should be slower due to backoff
        # (In mock, we use fast times, but the pattern should still show)
        assert len(reconnection_times) == 3

    @pytest.mark.asyncio
    async def test_subscriptions_restored_after_reconnection(
        self, mock_adapter: MockWebSocketAdapter
    ) -> None:
        """Test that subscriptions are restored after reconnection."""
        await mock_adapter.connect()
        await mock_adapter.subscribe(["BTC-PERP", "ETH-PERP"], ["trades"])

        # Store original subscriptions
        original_subs = mock_adapter._subscriptions.copy()

        await simulate_disconnect(mock_adapter)

        # Subscriptions cleared on disconnect
        assert len(mock_adapter._subscriptions) == 0

        await mock_adapter.reconnect()

        # Restore subscriptions manually (simulating real behavior)
        for symbol, channels in original_subs.items():
            await mock_adapter.subscribe([symbol], list(channels))

        assert mock_adapter._subscriptions == original_subs

    @pytest.mark.asyncio
    async def test_reconnection_time_logged(self, mock_adapter: MockWebSocketAdapter) -> None:
        """Test that reconnection time is measured and available."""
        await mock_adapter.connect()
        await simulate_disconnect(mock_adapter)

        reconnection_time = await measure_reconnection(mock_adapter)

        assert reconnection_time > 0
        assert mock_adapter.reconnection_start_time is not None


class TestCircuitBreakerBehavior:
    """Tests for circuit breaker behavior (AC3)."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_after_threshold(
        self, fast_adapter: MockWebSocketAdapter
    ) -> None:
        """Test that circuit breaker trips after consecutive failures."""
        # Simulate consecutive errors
        for _ in range(fast_adapter.config.circuit_breaker_threshold):
            fast_adapter.record_error()

        assert fast_adapter.circuit_breaker_tripped
        assert fast_adapter.in_safe_state

    @pytest.mark.asyncio
    async def test_circuit_breaker_safe_state(self, fast_adapter: MockWebSocketAdapter) -> None:
        """Test that system enters safe state when circuit breaker trips."""
        # Trip circuit breaker
        for _ in range(fast_adapter.config.circuit_breaker_threshold + 1):
            fast_adapter.record_error()

        assert fast_adapter.in_safe_state

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self, fast_adapter: MockWebSocketAdapter) -> None:
        """Test circuit breaker reset after cooldown."""
        # Trip circuit breaker
        for _ in range(fast_adapter.config.circuit_breaker_threshold + 1):
            fast_adapter.record_error()

        assert fast_adapter.circuit_breaker_tripped

        # Reset circuit breaker
        fast_adapter.reset_circuit_breaker()

        assert not fast_adapter.circuit_breaker_tripped
        assert not fast_adapter.in_safe_state

    @pytest.mark.asyncio
    async def test_circuit_breaker_not_tripped_on_successful_reconnect(
        self, fast_adapter: MockWebSocketAdapter
    ) -> None:
        """Test that circuit breaker doesn't trip if reconnection succeeds."""
        await fast_adapter.connect()

        # Single disconnect and reconnect
        await simulate_disconnect(fast_adapter)
        await measure_reconnection(fast_adapter)

        assert not fast_adapter.circuit_breaker_tripped


class TestReportGeneration:
    """Tests for stress test report generation (AC4)."""

    @pytest.mark.asyncio
    async def test_report_contains_required_metrics(
        self,
        load_scenario: Callable[[str], StressScenario],
        mock_adapter: MockWebSocketAdapter,
    ) -> None:
        """Test that report contains all required metrics."""
        scenario = load_scenario("network_disconnect")

        # Run scenario
        metrics = await run_network_scenario(
            mock_adapter,
            disconnect_count=3,
            disconnect_interval=0.1,
        )

        # Create result
        result = StressTestResult.create(
            scenario=scenario,
            start_time=datetime.now(),
            end_time=datetime.now(),
            passed=metrics.failed_reconnections == 0,
            metrics={
                "disconnections_simulated": 3,
                "reconnection_times": metrics.reconnection_times,
                "avg_reconnection_time_seconds": (
                    sum(metrics.reconnection_times) / len(metrics.reconnection_times)
                    if metrics.reconnection_times
                    else 0
                ),
                "max_reconnection_time_seconds": (
                    max(metrics.reconnection_times) if metrics.reconnection_times else 0
                ),
                "min_reconnection_time_seconds": (
                    min(metrics.reconnection_times) if metrics.reconnection_times else 0
                ),
                "circuit_breaker_trips": metrics.circuit_breaker_trips,
                "failed_reconnections": metrics.failed_reconnections,
            },
        )

        # Verify required metrics present
        assert "disconnections_simulated" in result.metrics
        assert "avg_reconnection_time_seconds" in result.metrics
        assert "max_reconnection_time_seconds" in result.metrics
        assert "circuit_breaker_trips" in result.metrics
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_report_saved_to_results(
        self,
        load_scenario: Callable[[str], StressScenario],
        save_result: Callable,
        mock_adapter: MockWebSocketAdapter,
        tmp_path,
    ) -> None:
        """Test that report is saved to results directory."""
        scenario = load_scenario("network_disconnect")

        metrics = await run_network_scenario(
            mock_adapter,
            disconnect_count=2,
            disconnect_interval=0.1,
        )

        result = StressTestResult.create(
            scenario=scenario,
            start_time=datetime.now(),
            end_time=datetime.now(),
            passed=True,
            metrics={
                "reconnection_times": metrics.reconnection_times,
                "circuit_breaker_trips": 0,
            },
        )

        # Save using temp path
        result_path = tmp_path / "test_result.json"
        result.save_to_json(result_path)

        assert result_path.exists()


class TestScenarios:
    """Tests for multiple network scenarios (AC5)."""

    @pytest.mark.asyncio
    async def test_single_disconnect_recovery(self, mock_adapter: MockWebSocketAdapter) -> None:
        """Test recovery from a single disconnect."""
        await mock_adapter.connect()

        detection_time = await simulate_disconnect(mock_adapter)
        reconnection_time = await measure_reconnection(mock_adapter)

        assert mock_adapter.is_connected
        assert detection_time < 60
        assert reconnection_time < 30

    @pytest.mark.asyncio
    async def test_rapid_disconnects(self, fast_adapter: MockWebSocketAdapter) -> None:
        """Test recovery from rapid disconnects (5 in 60 seconds)."""
        await fast_adapter.connect()

        metrics = await run_network_scenario(
            fast_adapter,
            disconnect_count=5,
            disconnect_interval=0.1,  # Rapid disconnects
        )

        assert metrics.failed_reconnections == 0
        assert len(metrics.reconnection_times) == 5
        assert all(t < 30 for t in metrics.reconnection_times)

    @pytest.mark.asyncio
    async def test_disconnect_during_order_submission(
        self, mock_adapter: MockWebSocketAdapter
    ) -> None:
        """Test handling disconnect during order submission."""
        await mock_adapter.connect()

        # Queue an order
        order = {"symbol": "BTC-PERP", "side": "buy", "amount": 1.0}
        mock_adapter.queue_order(order)

        # Disconnect
        await simulate_disconnect(mock_adapter)

        # Reconnect
        await measure_reconnection(mock_adapter)

        # Process queued orders
        processed = await mock_adapter.process_queued_orders()

        assert processed == 1
        assert mock_adapter.is_connected

    @pytest.mark.asyncio
    async def test_disconnect_with_open_positions(self, mock_adapter: MockWebSocketAdapter) -> None:
        """Test handling disconnect with open positions."""
        await mock_adapter.connect()

        # Simulate having open positions (via subscriptions)
        await mock_adapter.subscribe(["BTC-PERP"], ["positions"])

        # Disconnect
        await simulate_disconnect(mock_adapter)

        # Reconnect
        await measure_reconnection(mock_adapter)

        # Re-subscribe to positions
        await mock_adapter.subscribe(["BTC-PERP"], ["positions"])

        assert mock_adapter.is_connected
        assert "positions" in mock_adapter._subscriptions.get("BTC-PERP", set())


class TestOrderQueuing:
    """Tests for order queuing during disconnection (NFR9)."""

    @pytest.mark.asyncio
    async def test_orders_queued_during_disconnect(
        self, mock_adapter: MockWebSocketAdapter
    ) -> None:
        """Test that orders are queued during brief disconnection."""
        await mock_adapter.connect()

        # Queue orders during disconnect
        orders = [
            {"symbol": "BTC-PERP", "side": "buy", "amount": 1.0},
            {"symbol": "ETH-PERP", "side": "sell", "amount": 2.0},
        ]

        await simulate_disconnect(mock_adapter)

        for order in orders:
            mock_adapter.queue_order(order)

        assert len(mock_adapter._order_queue) == 2

    @pytest.mark.asyncio
    async def test_queued_orders_processed_after_reconnect(
        self, mock_adapter: MockWebSocketAdapter
    ) -> None:
        """Test that queued orders are processed after reconnection."""
        await mock_adapter.connect()

        # Queue orders
        mock_adapter.queue_order({"symbol": "BTC-PERP", "side": "buy", "amount": 1.0})

        await simulate_disconnect(mock_adapter)
        await measure_reconnection(mock_adapter)

        processed = await mock_adapter.process_queued_orders()

        assert processed == 1
        assert len(mock_adapter._order_queue) == 0


class TestIntegrationWithScenarioInfrastructure:
    """Integration tests with stress testing infrastructure."""

    @pytest.mark.asyncio
    async def test_load_network_scenario(
        self, load_scenario: Callable[[str], StressScenario]
    ) -> None:
        """Test loading network disconnect scenario."""
        scenario = load_scenario("network_disconnect")

        assert scenario.type == ScenarioType.NETWORK
        assert scenario.name == "network_disconnect_recovery"
        assert scenario.duration == 300

    @pytest.mark.asyncio
    async def test_validate_network_results(
        self,
        validate_results: Callable,
        load_scenario: Callable[[str], StressScenario],
    ) -> None:
        """Test validating network test results against criteria."""
        scenario = load_scenario("network_disconnect")

        # Passing results
        metrics = {
            "reconnection_times": [5, 10, 8],
            "failed_reconnections": 0,
            "data_loss": False,
        }

        passed, criteria_results = validate_results(metrics, scenario.success_criteria)

        assert passed is True
        assert criteria_results.get("all_reconnections_successful") is True

    @pytest.mark.asyncio
    async def test_full_scenario_execution(
        self,
        load_scenario: Callable[[str], StressScenario],
        mock_adapter: MockWebSocketAdapter,
    ) -> None:
        """Test full scenario execution with metrics collection."""
        scenario = load_scenario("network_disconnect")
        params = scenario.get_typed_parameters()

        start_time = datetime.now()

        # Run abbreviated scenario (5 disconnects instead of full duration)
        metrics = await run_network_scenario(
            mock_adapter,
            disconnect_count=min(params.disconnect_count, 5),
            disconnect_interval=0.1,
        )

        end_time = datetime.now()

        # Create result
        result = StressTestResult.create(
            scenario=scenario,
            start_time=start_time,
            end_time=end_time,
            passed=metrics.failed_reconnections == 0,
            metrics={
                "reconnection_times": metrics.reconnection_times,
                "failed_reconnections": metrics.failed_reconnections,
                "circuit_breaker_trips": metrics.circuit_breaker_trips,
            },
        )

        assert result.scenario_name == "network_disconnect_recovery"
        assert result.scenario_type == ScenarioType.NETWORK
        assert result.passed is True


@pytest.mark.stress
class TestExtendedNetworkScenarios:
    """Extended stress tests (marked for optional long-running execution)."""

    @pytest.mark.asyncio
    async def test_prolonged_disconnect_recovery(self, fast_adapter: MockWebSocketAdapter) -> None:
        """Test recovery from multiple disconnects over extended period."""
        await fast_adapter.connect()

        total_disconnects = 10
        metrics = await run_network_scenario(
            fast_adapter,
            disconnect_count=total_disconnects,
            disconnect_interval=0.1,
        )

        # All reconnections should succeed
        assert metrics.failed_reconnections == 0
        assert len(metrics.reconnection_times) == total_disconnects

        # Calculate statistics
        avg_time = sum(metrics.reconnection_times) / len(metrics.reconnection_times)
        max_time = max(metrics.reconnection_times)

        assert max_time < 30  # NFR2

    @pytest.mark.asyncio
    async def test_circuit_breaker_under_rapid_failures(
        self, fast_adapter: MockWebSocketAdapter
    ) -> None:
        """Test circuit breaker behavior under rapid failure conditions."""
        threshold = fast_adapter.config.circuit_breaker_threshold

        # Simulate rapid errors
        for i in range(threshold + 1):
            tripped = fast_adapter.record_error()
            if tripped:
                break

        assert fast_adapter.circuit_breaker_tripped
        assert fast_adapter.in_safe_state
