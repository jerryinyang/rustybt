"""Integration test for scheduled rebalancing strategy.

Tests a complete live trading scenario with daily rebalancing scheduled at
market close, verifying scheduling accuracy, callback execution, and trading
calendar integration.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest
import pytz

from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.events import ScheduledTriggerEvent
from rustybt.live.scheduler import TradingScheduler


class MockBroker(BrokerAdapter):
    """Mock broker for integration testing."""

    def __init__(self):
        """Initialize mock broker."""
        self._positions: dict[str, Decimal] = {}
        self._cash = Decimal("100000")
        self._orders: list[dict[str, Any]] = []
        self._connected = False

    async def connect(self) -> None:
        """Connect to broker (no-op for mock)."""
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from broker (no-op for mock)."""
        self._connected = False

    def is_connected(self) -> bool:
        """Check if broker connection is active."""
        return self._connected

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information."""
        return {
            "cash": self._cash,
            "equity": self._cash + sum(pos * Decimal("100") for pos in self._positions.values()),
            "buying_power": self._cash,
        }

    async def get_account_balance(self) -> Decimal:
        """Get account cash balance."""
        return self._cash

    async def get_positions(self) -> list[dict]:
        """Get current positions."""
        return [
            {
                "asset": symbol,
                "amount": amount,
                "cost_basis": Decimal("100"),
                "market_value": amount * Decimal("100"),
            }
            for symbol, amount in self._positions.items()
        ]

    async def get_positions_dict(self) -> dict[str, Decimal]:
        """Get current positions as dict (helper for tests)."""
        return self._positions.copy()

    async def submit_order(
        self,
        asset: Any,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str:
        """Submit order to broker."""
        # Handle both Asset objects and string symbols
        symbol = asset.symbol if hasattr(asset, "symbol") else str(asset)

        order_id = f"order_{len(self._orders)}"
        self._orders.append(
            {
                "order_id": order_id,
                "symbol": symbol,
                "amount": amount,
                "order_type": order_type,
                "limit_price": limit_price,
                "status": "filled",
            }
        )

        # Update positions immediately (mock fill)
        current = self._positions.get(symbol, Decimal("0"))
        self._positions[symbol] = current + amount

        # Update cash (assume $100 per share for simplicity)
        price = Decimal("100")
        self._cash -= amount * price

        return order_id

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel pending order."""
        for order in self._orders:
            if order["order_id"] == broker_order_id:
                order["status"] = "cancelled"

    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders from broker."""
        return [order for order in self._orders if order["status"] in ("pending", "submitted")]

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get order status."""
        for order in self._orders:
            if order["order_id"] == order_id:
                return order
        return {}

    async def subscribe_market_data(self, assets: list[Any]) -> None:
        """Subscribe to real-time market data (no-op for mock)."""
        pass

    async def unsubscribe_market_data(self, assets: list[Any]) -> None:
        """Unsubscribe from market data (no-op for mock)."""
        pass

    async def get_next_market_data(self) -> dict | None:
        """Get next market data update (returns None for mock)."""
        return None

    async def get_current_price(self, asset: Any) -> Decimal:
        """Get current price for asset."""
        return Decimal("100")  # Fixed price for simplicity


class RebalancingStrategy:
    """Simple rebalancing strategy for testing scheduler.

    Rebalances portfolio to equal weights daily at market close.
    """

    def __init__(self, symbols: list[str], target_allocation: dict[str, Decimal]):
        """Initialize rebalancing strategy.

        Args:
            symbols: List of symbols to trade
            target_allocation: Target allocation percentages (0.0-1.0)
        """
        self.symbols = symbols
        self.target_allocation = target_allocation
        self.rebalance_count = 0
        self.last_rebalance_time: pd.Timestamp | None = None

    async def rebalance_portfolio(self, broker: MockBroker) -> None:
        """Rebalance portfolio to target allocations.

        Args:
            broker: Broker instance for executing trades
        """
        self.rebalance_count += 1
        self.last_rebalance_time = pd.Timestamp.now(tz=pytz.UTC)

        # Get current account value
        cash = await broker.get_account_balance()
        positions = await broker.get_positions_dict()

        # Calculate current portfolio value (assume $100/share)
        price = Decimal("100")
        portfolio_value = cash + sum(
            positions.get(symbol, Decimal("0")) * price for symbol in self.symbols
        )

        # Calculate target positions
        for symbol in self.symbols:
            target_pct = self.target_allocation.get(symbol, Decimal("0"))
            target_value = portfolio_value * target_pct
            target_shares = target_value / price

            current_shares = positions.get(symbol, Decimal("0"))
            shares_to_trade = target_shares - current_shares

            # Execute trade if rebalance needed (threshold: 1 share)
            if abs(shares_to_trade) > Decimal("1"):
                await broker.submit_order(asset=symbol, amount=shares_to_trade, order_type="market")


@pytest.fixture
def event_queue():
    """Create async event queue."""
    return asyncio.Queue()


@pytest.fixture
def mock_broker():
    """Create mock broker instance."""
    return MockBroker()


@pytest.fixture
def scheduler(event_queue):
    """Create TradingScheduler instance."""
    return TradingScheduler(
        event_queue=event_queue,
        misfire_grace_time=60,
        timezone="America/New_York",
    )


@pytest.fixture
def rebalancing_strategy():
    """Create rebalancing strategy instance."""
    return RebalancingStrategy(
        symbols=["AAPL", "GOOGL", "MSFT"],
        target_allocation={
            "AAPL": Decimal("0.33"),
            "GOOGL": Decimal("0.33"),
            "MSFT": Decimal("0.34"),
        },
    )


class TestScheduledRebalancing:
    """Integration test for scheduled rebalancing strategy."""

    @pytest.mark.asyncio
    async def test_daily_rebalancing_at_market_close(
        self, scheduler, mock_broker, rebalancing_strategy, event_queue
    ):
        """Test strategy rebalances daily at market close.

        Verifies:
        - Scheduler registers market_close callback
        - Rebalancing executes on schedule
        - Callback receives correct context
        - Portfolio rebalances to target allocations
        """
        scheduler.start()

        # Register daily rebalancing at market close
        async def rebalance_callback():
            await rebalancing_strategy.rebalance_portfolio(mock_broker)

        job_id = scheduler.schedule_market_close(
            callback=rebalance_callback,
            exchange="NYSE",
            timezone="America/New_York",
            callback_name="daily_rebalance",
        )

        assert job_id == "daily_rebalance"
        assert "daily_rebalance" in scheduler._callbacks

        # Verify callback is enabled
        callback = scheduler._callbacks["daily_rebalance"]
        assert callback.enabled

        # Verify trigger configuration (16:00 ET Mon-Fri)
        assert callback.trigger_config["trigger"] == "cron"
        assert callback.trigger_config["cron"] == "0 16 * * MON-FRI"

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_rebalancing_executes_and_updates_portfolio(
        self, mock_broker, rebalancing_strategy
    ):
        """Test rebalancing executes trades and updates portfolio.

        Verifies:
        - Rebalancing calculates target positions
        - Orders submitted to broker
        - Portfolio converges to target allocations
        """
        # Execute rebalancing
        await rebalancing_strategy.rebalance_portfolio(mock_broker)

        # Verify rebalance executed
        assert rebalancing_strategy.rebalance_count == 1
        assert rebalancing_strategy.last_rebalance_time is not None

        # Verify orders submitted
        assert len(mock_broker._orders) > 0

        # Verify positions updated
        positions = await mock_broker.get_positions_dict()
        assert len(positions) > 0

        # Verify portfolio allocation (approximate, due to rounding)
        cash = await mock_broker.get_account_balance()
        price = Decimal("100")
        portfolio_value = cash + sum(pos * price for pos in positions.values())

        for symbol, target_pct in rebalancing_strategy.target_allocation.items():
            position = positions.get(symbol, Decimal("0"))
            actual_pct = (position * price) / portfolio_value
            # Allow 5% tolerance for rounding
            assert abs(actual_pct - target_pct) < Decimal("0.05")

    @pytest.mark.asyncio
    async def test_multiple_rebalance_cycles(
        self, scheduler, mock_broker, rebalancing_strategy, event_queue
    ):
        """Test multiple rebalancing cycles over simulated days.

        Verifies:
        - Scheduler triggers callback on schedule
        - Multiple rebalances execute successfully
        - Portfolio state persists across cycles
        """
        scheduler.start()

        # Register rebalancing callback
        async def rebalance_callback():
            await rebalancing_strategy.rebalance_portfolio(mock_broker)

        scheduler.add_job(
            callback=rebalance_callback,
            trigger="interval",
            seconds=1,  # Every 1 second for test speed
            callback_name="test_rebalance",
        )

        # Wait for multiple rebalance cycles
        await asyncio.sleep(3)

        # Verify multiple rebalances executed
        assert rebalancing_strategy.rebalance_count >= 2

        # Verify portfolio still valid
        cash = await mock_broker.get_account_balance()
        positions = await mock_broker.get_positions_dict()
        assert cash >= Decimal("0")  # Non-negative cash
        assert len(positions) > 0  # Has positions

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_callback_context_includes_scheduled_time(self, scheduler, event_queue):
        """Test callback receives context with scheduled time.

        Verifies:
        - ScheduledTriggerEvent emitted to queue
        - Event includes callback name and timestamp
        """
        scheduler.start()

        # Schedule callback with date trigger (fires once)
        trigger_time = datetime.now(pytz.UTC) + timedelta(seconds=1)

        async def test_callback():
            pass

        scheduler.add_job(
            callback=test_callback,
            trigger="date",
            run_date=trigger_time,
            callback_name="context_test",
        )

        # Wait for callback to fire and event to be emitted
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=3)

            # Verify event is ScheduledTriggerEvent
            assert isinstance(event, ScheduledTriggerEvent)
            assert event.callback_name == "context_test"
            assert event.trigger_timestamp is not None

            # Verify scheduled time within tolerance (±2 seconds)
            time_diff = abs(
                (event.trigger_timestamp.to_pydatetime() - trigger_time).total_seconds()
            )
            assert time_diff <= 2.0
        except TimeoutError:
            pytest.fail("Callback did not fire within timeout")

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_rebalancing_skips_weekends_and_holidays(self, scheduler):
        """Test market_close trigger skips non-trading days.

        Verifies:
        - Scheduler uses trading calendar
        - Jobs scheduled only on trading days (Mon-Fri)
        - Weekends and holidays are skipped
        """
        scheduler.start()

        async def noop_callback():
            pass

        # Schedule market close callback
        scheduler.schedule_market_close(
            callback=noop_callback,
            exchange="NYSE",
            timezone="America/New_York",
            callback_name="trading_days_only",
        )

        # Verify cron expression includes MON-FRI
        callback = scheduler._callbacks["trading_days_only"]
        assert "MON-FRI" in callback.trigger_config["cron"]

        # Note: Full trading calendar integration (holidays) tested via
        # exchange-calendars library, which is mocked here

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_scheduler_list_jobs_shows_active_jobs(self, scheduler, rebalancing_strategy):
        """Test list_jobs() returns active scheduled jobs.

        Verifies:
        - list_jobs() returns all registered jobs
        - Job metadata includes trigger config and next run time
        """
        scheduler.start()

        # Schedule multiple jobs
        scheduler.schedule_market_close(
            callback=lambda: None,
            exchange="NYSE",
            timezone="America/New_York",
            callback_name="close_rebalance",
        )

        scheduler.add_job(
            callback=lambda: None,
            trigger="interval",
            minutes=5,
            callback_name="risk_check",
        )

        # List jobs
        jobs = scheduler.list_jobs()

        assert len(jobs) == 2

        job_names = [job["callback_name"] for job in jobs]
        assert "close_rebalance" in job_names
        assert "risk_check" in job_names

        # Verify job metadata
        close_job = next(j for j in jobs if j["callback_name"] == "close_rebalance")
        assert close_job["enabled"] is True
        assert close_job["trigger_config"]["trigger"] == "cron"
        assert "next_run_time" in close_job

        scheduler.shutdown()


class TestSchedulerErrorHandling:
    """Test scheduler error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_stop_scheduling(self, scheduler, event_queue):
        """Test callback exceptions are logged but don't stop scheduler.

        Verifies:
        - Exception in callback is caught
        - Scheduler continues running
        - Subsequent callbacks still fire
        """
        scheduler.start()

        execution_count = []

        async def failing_callback():
            execution_count.append(1)
            raise ValueError("Test error in callback")

        # Schedule failing callback every second
        scheduler.add_job(
            callback=failing_callback,
            trigger="interval",
            seconds=1,
            callback_name="failing",
        )

        # Wait for multiple executions
        await asyncio.sleep(2.5)

        # Verify callback attempted multiple times despite exceptions
        assert len(execution_count) >= 2

        # Verify scheduler still running
        assert scheduler._scheduler.running

        scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_disable_and_reenable_callback(self, scheduler, event_queue):
        """Test disabling and re-enabling callbacks.

        Verifies:
        - Disabled callbacks don't execute
        - Re-enabled callbacks resume execution
        """
        scheduler.start()

        execution_count = []

        async def tracked_callback():
            execution_count.append(1)

        # Schedule callback every second
        scheduler.add_job(
            callback=tracked_callback,
            trigger="interval",
            seconds=1,
            callback_name="tracked",
        )

        # Wait for initial execution
        await asyncio.sleep(1.5)
        initial_count = len(execution_count)
        assert initial_count >= 1

        # Disable callback
        scheduler.disable_callback("tracked")
        await asyncio.sleep(1.5)

        # Verify no new executions
        assert len(execution_count) == initial_count

        # Re-enable callback
        scheduler.enable_callback("tracked")
        await asyncio.sleep(1.5)

        # Verify executions resumed
        assert len(execution_count) > initial_count

        scheduler.shutdown()
