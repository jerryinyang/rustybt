"""Tests for event system."""

from decimal import Decimal

import pandas as pd
import pytest

from rustybt.live.events import (
    EventPriority,
    MarketDataEvent,
    OrderFillEvent,
    OrderRejectEvent,
    ScheduledTriggerEvent,
    SystemErrorEvent,
)


class TestEventPriority:
    """Test event priority ordering."""

    def test_event_priority_values(self):
        """Verify priority values are ordered correctly."""
        assert EventPriority.SYSTEM_ERROR < EventPriority.ORDER_FILL
        assert EventPriority.ORDER_FILL < EventPriority.ORDER_REJECT
        assert EventPriority.ORDER_REJECT < EventPriority.SCHEDULED_TRIGGER
        assert EventPriority.SCHEDULED_TRIGGER < EventPriority.MARKET_DATA

    def test_event_priority_comparison(self):
        """Test that events are compared by priority."""
        system_error = SystemErrorEvent(
            error_type="test",
            error_message="test error",
            error_timestamp=pd.Timestamp.now(),
        )

        market_data = MarketDataEvent(
            asset_symbol="AAPL",
            open=Decimal("150"),
            high=Decimal("151"),
            low=Decimal("149"),
            close=Decimal("150.50"),
            volume=Decimal("1000000"),
            bar_timestamp=pd.Timestamp.now(),
        )

        # System error should have higher priority (lower value)
        assert system_error < market_data
        assert market_data > system_error

    def test_event_priority_same_priority_uses_timestamp(self):
        """Test that events with same priority use timestamp ordering."""
        timestamp1 = pd.Timestamp("2025-01-01 10:00:00")
        timestamp2 = pd.Timestamp("2025-01-01 10:00:01")

        event1 = MarketDataEvent(
            asset_symbol="AAPL",
            open=Decimal("150"),
            high=Decimal("151"),
            low=Decimal("149"),
            close=Decimal("150.50"),
            volume=Decimal("1000000"),
            bar_timestamp=timestamp1,
            timestamp=timestamp1,
        )

        event2 = MarketDataEvent(
            asset_symbol="GOOGL",
            open=Decimal("2800"),
            high=Decimal("2810"),
            low=Decimal("2790"),
            close=Decimal("2805"),
            volume=Decimal("500000"),
            bar_timestamp=timestamp2,
            timestamp=timestamp2,
        )

        # Earlier timestamp should have higher priority
        assert event1 < event2


class TestMarketDataEvent:
    """Test MarketDataEvent."""

    def test_market_data_event_creation(self):
        """Test creating market data event."""
        event = MarketDataEvent(
            asset_symbol="AAPL",
            open=Decimal("150"),
            high=Decimal("151"),
            low=Decimal("149"),
            close=Decimal("150.50"),
            volume=Decimal("1000000"),
            bar_timestamp=pd.Timestamp.now(),
        )

        assert event.event_type == "market_data"
        assert event.priority == EventPriority.MARKET_DATA
        assert event.asset_symbol == "AAPL"
        assert event.close == Decimal("150.50")

    def test_market_data_event_immutable(self):
        """Test that events are immutable (frozen)."""
        event = MarketDataEvent(
            asset_symbol="AAPL",
            open=Decimal("150"),
            high=Decimal("151"),
            low=Decimal("149"),
            close=Decimal("150.50"),
            volume=Decimal("1000000"),
            bar_timestamp=pd.Timestamp.now(),
        )

        with pytest.raises(Exception):  # pydantic ValidationError
            event.close = Decimal("160")


class TestOrderFillEvent:
    """Test OrderFillEvent."""

    def test_order_fill_event_creation(self):
        """Test creating order fill event."""
        event = OrderFillEvent(
            order_id="order-123",
            broker_order_id="broker-456",
            asset_symbol="AAPL",
            filled_amount=Decimal("100"),
            fill_price=Decimal("150.50"),
            commission=Decimal("1.00"),
            fill_timestamp=pd.Timestamp.now(),
        )

        assert event.event_type == "order_fill"
        assert event.priority == EventPriority.ORDER_FILL
        assert event.order_id == "order-123"
        assert event.filled_amount == Decimal("100")


class TestOrderRejectEvent:
    """Test OrderRejectEvent."""

    def test_order_reject_event_creation(self):
        """Test creating order reject event."""
        event = OrderRejectEvent(
            order_id="order-123",
            asset_symbol="AAPL",
            amount=Decimal("100"),
            reason="Insufficient funds",
            reject_timestamp=pd.Timestamp.now(),
        )

        assert event.event_type == "order_reject"
        assert event.priority == EventPriority.ORDER_REJECT
        assert event.reason == "Insufficient funds"


class TestScheduledTriggerEvent:
    """Test ScheduledTriggerEvent."""

    def test_scheduled_trigger_event_creation(self):
        """Test creating scheduled trigger event."""
        event = ScheduledTriggerEvent(
            callback_name="rebalance",
            callback_args={"param1": "value1"},
            trigger_timestamp=pd.Timestamp.now(),
        )

        assert event.event_type == "scheduled_trigger"
        assert event.priority == EventPriority.SCHEDULED_TRIGGER
        assert event.callback_name == "rebalance"
        assert event.callback_args["param1"] == "value1"


class TestSystemErrorEvent:
    """Test SystemErrorEvent."""

    def test_system_error_event_creation(self):
        """Test creating system error event."""
        event = SystemErrorEvent(
            error_type="broker_connection",
            error_message="Connection failed",
            exception_details="ConnectionError: timeout",
            error_timestamp=pd.Timestamp.now(),
        )

        assert event.event_type == "system_error"
        assert event.priority == EventPriority.SYSTEM_ERROR
        assert event.error_type == "broker_connection"
