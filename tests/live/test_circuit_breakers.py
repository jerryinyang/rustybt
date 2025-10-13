"""Unit tests for circuit breakers.

Tests all circuit breaker types:
- DrawdownCircuitBreaker
- DailyLossCircuitBreaker
- OrderRateCircuitBreaker
- ErrorRateCircuitBreaker
- ManualCircuitBreaker
- CircuitBreakerManager
"""

import time
from decimal import Decimal

import pytest

from rustybt.live.circuit_breakers import (
    CircuitBreakerError,
    CircuitBreakerManager,
    CircuitBreakerState,
    CircuitBreakerTrippedEvent,
    CircuitBreakerType,
    DailyLossCircuitBreaker,
    DrawdownCircuitBreaker,
    ErrorRateCircuitBreaker,
    ManualCircuitBreaker,
    ManualHaltEvent,
    OrderRateCircuitBreaker,
)


class TestDrawdownCircuitBreaker:
    """Tests for DrawdownCircuitBreaker."""

    def test_initialization(self) -> None:
        """Test breaker initializes correctly."""
        breaker = DrawdownCircuitBreaker(
            threshold=Decimal("-0.10"), initial_portfolio_value=Decimal("100000")
        )
        assert breaker.state == CircuitBreakerState.NORMAL
        assert not breaker.is_tripped

    def test_no_trip_within_threshold(self) -> None:
        """Test breaker does not trip within threshold."""
        breaker = DrawdownCircuitBreaker(
            threshold=Decimal("-0.10"), initial_portfolio_value=Decimal("100000")
        )

        # -5% drawdown, should not trip
        event = breaker.check(Decimal("95000"))
        assert event is None
        assert not breaker.is_tripped

    def test_trip_at_threshold(self) -> None:
        """Test breaker trips when threshold exceeded."""
        breaker = DrawdownCircuitBreaker(
            threshold=Decimal("-0.10"), initial_portfolio_value=Decimal("100000")
        )

        # -11% drawdown, should trip
        event = breaker.check(Decimal("89000"))
        assert event is not None
        assert isinstance(event, CircuitBreakerTrippedEvent)
        assert event.breaker_type == CircuitBreakerType.DRAWDOWN
        assert breaker.is_tripped
        assert breaker.state == CircuitBreakerState.TRIPPED

    def test_high_water_mark_update(self) -> None:
        """Test high-water mark updates when portfolio increases."""
        breaker = DrawdownCircuitBreaker(
            threshold=Decimal("-0.10"), initial_portfolio_value=Decimal("100000")
        )

        # Increase to 110k
        event = breaker.check(Decimal("110000"))
        assert event is None

        # Drop to 100k (9.09% from new HWM), should not trip
        event = breaker.check(Decimal("100000"))
        assert event is None

    def test_trip_after_high_water_mark_update(self) -> None:
        """Test breaker trips based on new high-water mark."""
        breaker = DrawdownCircuitBreaker(
            threshold=Decimal("-0.10"), initial_portfolio_value=Decimal("100000")
        )

        # Increase to 110k
        breaker.check(Decimal("110000"))

        # Drop to 98k (10.9% from 110k), should trip
        event = breaker.check(Decimal("98000"))
        assert event is not None
        assert breaker.is_tripped

    def test_no_check_after_trip(self) -> None:
        """Test breaker doesn't check after already tripped."""
        breaker = DrawdownCircuitBreaker(
            threshold=Decimal("-0.10"), initial_portfolio_value=Decimal("100000")
        )

        # Trip
        breaker.check(Decimal("89000"))

        # Further drops don't generate new events
        event = breaker.check(Decimal("80000"))
        assert event is None

    def test_reset(self) -> None:
        """Test breaker can be reset."""
        breaker = DrawdownCircuitBreaker(
            threshold=Decimal("-0.10"), initial_portfolio_value=Decimal("100000")
        )

        # Trip and reset
        breaker.check(Decimal("89000"))
        assert breaker.is_tripped
        breaker.reset()
        assert not breaker.is_tripped
        assert breaker.state == CircuitBreakerState.NORMAL


class TestDailyLossCircuitBreaker:
    """Tests for DailyLossCircuitBreaker."""

    def test_initialization_percentage(self) -> None:
        """Test breaker initializes correctly with percentage limit."""
        breaker = DailyLossCircuitBreaker(
            limit=Decimal("-0.05"), initial_portfolio_value=Decimal("100000"), is_percentage=True
        )
        assert breaker.state == CircuitBreakerState.NORMAL

    def test_initialization_absolute(self) -> None:
        """Test breaker initializes correctly with absolute limit."""
        breaker = DailyLossCircuitBreaker(
            limit=Decimal("-5000"), initial_portfolio_value=Decimal("100000"), is_percentage=False
        )
        assert breaker.state == CircuitBreakerState.NORMAL

    def test_no_trip_percentage_within_limit(self) -> None:
        """Test percentage breaker does not trip within limit."""
        breaker = DailyLossCircuitBreaker(
            limit=Decimal("-0.05"), initial_portfolio_value=Decimal("100000"), is_percentage=True
        )

        # -3% loss, should not trip
        event = breaker.check(Decimal("97000"))
        assert event is None

    def test_trip_percentage_at_limit(self) -> None:
        """Test percentage breaker trips when limit exceeded."""
        breaker = DailyLossCircuitBreaker(
            limit=Decimal("-0.05"), initial_portfolio_value=Decimal("100000"), is_percentage=True
        )

        # -6% loss, should trip
        event = breaker.check(Decimal("94000"))
        assert event is not None
        assert isinstance(event, CircuitBreakerTrippedEvent)
        assert event.breaker_type == CircuitBreakerType.DAILY_LOSS
        assert breaker.is_tripped

    def test_no_trip_absolute_within_limit(self) -> None:
        """Test absolute breaker does not trip within limit."""
        breaker = DailyLossCircuitBreaker(
            limit=Decimal("-5000"), initial_portfolio_value=Decimal("100000"), is_percentage=False
        )

        # -$3000 loss, should not trip
        event = breaker.check(Decimal("97000"))
        assert event is None

    def test_trip_absolute_at_limit(self) -> None:
        """Test absolute breaker trips when limit exceeded."""
        breaker = DailyLossCircuitBreaker(
            limit=Decimal("-5000"), initial_portfolio_value=Decimal("100000"), is_percentage=False
        )

        # -$6000 loss, should trip
        event = breaker.check(Decimal("94000"))
        assert event is not None
        assert breaker.is_tripped

    def test_daily_reset(self) -> None:
        """Test daily reset resets counter and state."""
        breaker = DailyLossCircuitBreaker(
            limit=Decimal("-0.05"), initial_portfolio_value=Decimal("100000"), is_percentage=True
        )

        # Trip
        breaker.check(Decimal("94000"))
        assert breaker.is_tripped

        # Reset for new day with new starting value
        breaker.reset_daily(Decimal("110000"))
        assert not breaker.is_tripped

        # -3% from new starting value should not trip
        event = breaker.check(Decimal("106700"))
        assert event is None


class TestOrderRateCircuitBreaker:
    """Tests for OrderRateCircuitBreaker."""

    def test_initialization(self) -> None:
        """Test breaker initializes correctly."""
        breaker = OrderRateCircuitBreaker(max_orders=100, window_seconds=60)
        assert breaker.state == CircuitBreakerState.NORMAL

    def test_no_trip_within_limit(self) -> None:
        """Test breaker does not trip within limit."""
        breaker = OrderRateCircuitBreaker(max_orders=10, window_seconds=60)

        # Submit 10 orders (at limit)
        for _ in range(10):
            event = breaker.record_order()
            assert event is None

    def test_trip_at_limit(self) -> None:
        """Test breaker trips when limit exceeded."""
        breaker = OrderRateCircuitBreaker(max_orders=10, window_seconds=60)

        # Submit 11 orders (exceeds limit)
        for i in range(11):
            if i < 10:
                event = breaker.record_order()
                assert event is None
            else:
                event = breaker.record_order()
                assert event is not None
                assert isinstance(event, CircuitBreakerTrippedEvent)
                assert event.breaker_type == CircuitBreakerType.ORDER_RATE
                assert breaker.is_tripped

    def test_raises_after_trip(self) -> None:
        """Test breaker raises CircuitBreakerError after trip."""
        breaker = OrderRateCircuitBreaker(max_orders=5, window_seconds=60)

        # Trip breaker
        for _ in range(6):
            try:
                breaker.record_order()
            except CircuitBreakerError:
                pass

        # Subsequent orders should raise
        with pytest.raises(CircuitBreakerError):
            breaker.record_order()

    def test_window_sliding(self) -> None:
        """Test sliding window removes old orders."""
        breaker = OrderRateCircuitBreaker(max_orders=10, window_seconds=1)

        # Submit 10 orders
        for _ in range(10):
            breaker.record_order()

        # Wait for window to pass
        time.sleep(1.1)

        # Should be able to submit 10 more orders
        for i in range(10):
            event = breaker.record_order()
            assert event is None


class TestErrorRateCircuitBreaker:
    """Tests for ErrorRateCircuitBreaker."""

    def test_initialization(self) -> None:
        """Test breaker initializes correctly."""
        breaker = ErrorRateCircuitBreaker(max_errors=10, window_seconds=60)
        assert breaker.state == CircuitBreakerState.NORMAL

    def test_no_trip_within_limit(self) -> None:
        """Test breaker does not trip within limit."""
        breaker = ErrorRateCircuitBreaker(max_errors=10, window_seconds=60)

        # Record 10 errors (at limit)
        for _ in range(10):
            event = breaker.record_error("order_rejected")
            assert event is None

    def test_trip_at_limit(self) -> None:
        """Test breaker trips when limit exceeded."""
        breaker = ErrorRateCircuitBreaker(max_errors=10, window_seconds=60)

        # Record 11 errors (exceeds limit)
        for i in range(11):
            event = breaker.record_error("order_rejected")
            if i < 10:
                assert event is None
            else:
                assert event is not None
                assert isinstance(event, CircuitBreakerTrippedEvent)
                assert event.breaker_type == CircuitBreakerType.ERROR_RATE
                assert breaker.is_tripped

    def test_error_types_tracked(self) -> None:
        """Test different error types are tracked."""
        breaker = ErrorRateCircuitBreaker(max_errors=10, window_seconds=60)

        # Record different error types (10 errors)
        for _ in range(5):
            breaker.record_error("order_rejected")
        for _ in range(3):
            breaker.record_error("broker_error")
        for _ in range(2):
            breaker.record_error("data_error")

        # 11th error should trip
        event = breaker.record_error("order_rejected")
        assert event is not None
        assert "error_types" in event.details
        assert event.details["error_types"]["order_rejected"] == 6
        assert event.details["error_types"]["broker_error"] == 3
        assert event.details["error_types"]["data_error"] == 2

    def test_window_sliding(self) -> None:
        """Test sliding window removes old errors."""
        breaker = ErrorRateCircuitBreaker(max_errors=10, window_seconds=1)

        # Record 10 errors
        for _ in range(10):
            breaker.record_error("test_error")

        # Wait for window to pass
        time.sleep(1.1)

        # Should be able to record 10 more errors
        for i in range(10):
            event = breaker.record_error("test_error")
            assert event is None


class TestManualCircuitBreaker:
    """Tests for ManualCircuitBreaker."""

    def test_initialization(self) -> None:
        """Test breaker initializes correctly."""
        breaker = ManualCircuitBreaker()
        assert breaker.state == CircuitBreakerState.NORMAL

    def test_manual_trip(self) -> None:
        """Test manual trip works."""
        breaker = ManualCircuitBreaker()

        event = breaker.trip("Emergency halt", operator="trader_alice")
        assert isinstance(event, ManualHaltEvent)
        assert event.reason == "Emergency halt"
        assert event.operator == "trader_alice"
        assert breaker.state == CircuitBreakerState.MANUALLY_HALTED
        assert breaker.is_tripped

    def test_reset(self) -> None:
        """Test reset works."""
        breaker = ManualCircuitBreaker()

        breaker.trip("Test halt", operator="test")
        assert breaker.is_tripped

        breaker.reset()
        assert not breaker.is_tripped
        assert breaker.state == CircuitBreakerState.NORMAL


class TestCircuitBreakerManager:
    """Tests for CircuitBreakerManager."""

    def test_initialization(self) -> None:
        """Test manager initializes correctly."""
        manager = CircuitBreakerManager()
        assert manager.state == CircuitBreakerState.NORMAL
        assert not manager.is_tripped

    def test_initialization_with_breakers(self) -> None:
        """Test manager initializes with breakers."""
        drawdown = DrawdownCircuitBreaker(Decimal("-0.10"), Decimal("100000"))
        daily_loss = DailyLossCircuitBreaker(Decimal("-0.05"), Decimal("100000"))
        order_rate = OrderRateCircuitBreaker(100, 60)
        error_rate = ErrorRateCircuitBreaker(10, 60)

        manager = CircuitBreakerManager(
            drawdown_breaker=drawdown,
            daily_loss_breaker=daily_loss,
            order_rate_breaker=order_rate,
            error_rate_breaker=error_rate,
        )

        status = manager.get_status()
        assert status["drawdown"]["enabled"]
        assert status["daily_loss"]["enabled"]
        assert status["order_rate"]["enabled"]
        assert status["error_rate"]["enabled"]
        assert status["manual"]["enabled"]

    @pytest.mark.asyncio
    async def test_check_drawdown(self) -> None:
        """Test drawdown check works."""
        drawdown = DrawdownCircuitBreaker(Decimal("-0.10"), Decimal("100000"))
        manager = CircuitBreakerManager(drawdown_breaker=drawdown)

        events = []

        async def callback(event):
            events.append(event)

        manager.register_event_callback(callback)

        # Should not trip
        await manager.check_drawdown(Decimal("95000"))
        assert len(events) == 0
        assert not manager.is_tripped

        # Should trip
        await manager.check_drawdown(Decimal("89000"))
        assert len(events) == 1
        assert manager.is_tripped
        assert manager.state == CircuitBreakerState.TRIPPED

    @pytest.mark.asyncio
    async def test_check_daily_loss(self) -> None:
        """Test daily loss check works."""
        daily_loss = DailyLossCircuitBreaker(Decimal("-0.05"), Decimal("100000"))
        manager = CircuitBreakerManager(daily_loss_breaker=daily_loss)

        events = []

        async def callback(event):
            events.append(event)

        manager.register_event_callback(callback)

        # Should not trip
        await manager.check_daily_loss(Decimal("97000"))
        assert len(events) == 0

        # Should trip
        await manager.check_daily_loss(Decimal("94000"))
        assert len(events) == 1
        assert manager.is_tripped

    @pytest.mark.asyncio
    async def test_record_order(self) -> None:
        """Test order recording works."""
        order_rate = OrderRateCircuitBreaker(5, 60)
        manager = CircuitBreakerManager(order_rate_breaker=order_rate)

        events = []

        async def callback(event):
            events.append(event)

        manager.register_event_callback(callback)

        # Submit 5 orders (should not trip)
        for _ in range(5):
            await manager.record_order()
        assert len(events) == 0

        # 6th order should trip
        await manager.record_order()
        assert len(events) == 1
        assert manager.is_tripped

    @pytest.mark.asyncio
    async def test_record_error(self) -> None:
        """Test error recording works."""
        error_rate = ErrorRateCircuitBreaker(5, 60)
        manager = CircuitBreakerManager(error_rate_breaker=error_rate)

        events = []

        async def callback(event):
            events.append(event)

        manager.register_event_callback(callback)

        # Record 5 errors (should not trip)
        for _ in range(5):
            await manager.record_error("order_rejected")
        assert len(events) == 0

        # 6th error should trip
        await manager.record_error("order_rejected")
        assert len(events) == 1
        assert manager.is_tripped

    @pytest.mark.asyncio
    async def test_manual_halt(self) -> None:
        """Test manual halt works."""
        manager = CircuitBreakerManager()

        events = []

        async def callback(event):
            events.append(event)

        manager.register_event_callback(callback)

        await manager.manual_halt("Emergency stop", operator="trader_bob")
        assert len(events) == 1
        assert isinstance(events[0], ManualHaltEvent)
        assert manager.state == CircuitBreakerState.MANUALLY_HALTED
        assert manager.is_tripped

    def test_reset_all(self) -> None:
        """Test reset all breakers works."""
        drawdown = DrawdownCircuitBreaker(Decimal("-0.10"), Decimal("100000"))
        daily_loss = DailyLossCircuitBreaker(Decimal("-0.05"), Decimal("100000"))

        manager = CircuitBreakerManager(
            drawdown_breaker=drawdown,
            daily_loss_breaker=daily_loss,
        )

        # Trip both breakers
        drawdown.check(Decimal("89000"))
        daily_loss.check(Decimal("94000"))
        assert manager.is_tripped

        # Reset all
        manager.reset_all()
        assert not manager.is_tripped
        assert manager.state == CircuitBreakerState.NORMAL

    def test_manual_halt_overrides_state(self) -> None:
        """Test manual halt state takes precedence."""
        drawdown = DrawdownCircuitBreaker(Decimal("-0.10"), Decimal("100000"))
        manager = CircuitBreakerManager(drawdown_breaker=drawdown)

        # Trip drawdown
        drawdown.check(Decimal("89000"))
        assert manager.state == CircuitBreakerState.TRIPPED

        # Manual halt should override
        manager._manual_breaker.trip("Override", operator="admin")
        assert manager.state == CircuitBreakerState.MANUALLY_HALTED

    def test_get_status(self) -> None:
        """Test get_status returns correct status."""
        drawdown = DrawdownCircuitBreaker(Decimal("-0.10"), Decimal("100000"))
        manager = CircuitBreakerManager(drawdown_breaker=drawdown)

        status = manager.get_status()
        assert status["overall_state"] == "normal"
        assert not status["is_tripped"]
        assert status["drawdown"]["enabled"]
        assert status["drawdown"]["state"] == "normal"

        # Trip drawdown
        drawdown.check(Decimal("89000"))
        status = manager.get_status()
        assert status["overall_state"] == "tripped"
        assert status["is_tripped"]
        assert status["drawdown"]["state"] == "tripped"

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self) -> None:
        """Test multiple callbacks receive events."""
        manager = CircuitBreakerManager()

        events1 = []
        events2 = []

        async def callback1(event):
            events1.append(event)

        async def callback2(event):
            events2.append(event)

        manager.register_event_callback(callback1)
        manager.register_event_callback(callback2)

        await manager.manual_halt("Test", operator="test")

        assert len(events1) == 1
        assert len(events2) == 1

    def test_reset_daily_loss(self) -> None:
        """Test reset_daily_loss works."""
        daily_loss = DailyLossCircuitBreaker(Decimal("-0.05"), Decimal("100000"))
        manager = CircuitBreakerManager(daily_loss_breaker=daily_loss)

        # Trip
        daily_loss.check(Decimal("94000"))
        assert manager.is_tripped

        # Reset for new day
        manager.reset_daily_loss(Decimal("110000"))
        assert not manager.is_tripped
