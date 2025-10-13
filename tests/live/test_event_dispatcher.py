"""Tests for event dispatcher."""

from decimal import Decimal

import pandas as pd
import pytest

from rustybt.live.event_dispatcher import EventDispatcher
from rustybt.live.events import MarketDataEvent


class TestEventDispatcher:
    """Test EventDispatcher."""

    @pytest.mark.asyncio
    async def test_register_handler(self):
        """Test registering event handlers."""
        dispatcher = EventDispatcher()
        call_count = 0

        async def handler(event):
            nonlocal call_count
            call_count += 1

        dispatcher.register_handler("market_data", handler)
        assert dispatcher.get_handler_count("market_data") == 1

    @pytest.mark.asyncio
    async def test_dispatch_to_handler(self):
        """Test dispatching events to handlers."""
        dispatcher = EventDispatcher()
        received_events = []

        async def handler(event):
            received_events.append(event)

        dispatcher.register_handler("market_data", handler)

        event = MarketDataEvent(
            asset_symbol="AAPL",
            open=Decimal("150"),
            high=Decimal("151"),
            low=Decimal("149"),
            close=Decimal("150.50"),
            volume=Decimal("1000000"),
            bar_timestamp=pd.Timestamp.now(),
        )

        await dispatcher.dispatch(event)

        assert len(received_events) == 1
        assert received_events[0] == event

    @pytest.mark.asyncio
    async def test_dispatch_to_multiple_handlers(self):
        """Test dispatching to multiple handlers for same event type."""
        dispatcher = EventDispatcher()
        call_counts = {"handler1": 0, "handler2": 0}

        async def handler1(event):
            call_counts["handler1"] += 1

        async def handler2(event):
            call_counts["handler2"] += 1

        dispatcher.register_handler("market_data", handler1)
        dispatcher.register_handler("market_data", handler2)

        event = MarketDataEvent(
            asset_symbol="AAPL",
            open=Decimal("150"),
            high=Decimal("151"),
            low=Decimal("149"),
            close=Decimal("150.50"),
            volume=Decimal("1000000"),
            bar_timestamp=pd.Timestamp.now(),
        )

        await dispatcher.dispatch(event)

        assert call_counts["handler1"] == 1
        assert call_counts["handler2"] == 1

    @pytest.mark.asyncio
    async def test_dispatch_no_handlers(self):
        """Test dispatching when no handlers registered."""
        dispatcher = EventDispatcher()

        event = MarketDataEvent(
            asset_symbol="AAPL",
            open=Decimal("150"),
            high=Decimal("151"),
            low=Decimal("149"),
            close=Decimal("150.50"),
            volume=Decimal("1000000"),
            bar_timestamp=pd.Timestamp.now(),
        )

        # Should not raise exception
        await dispatcher.dispatch(event)

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_crash(self):
        """Test that handler exceptions are caught and logged."""
        dispatcher = EventDispatcher()
        call_counts = {"handler1": 0, "handler2": 0}

        async def failing_handler(event):
            call_counts["handler1"] += 1
            raise ValueError("Handler error")

        async def working_handler(event):
            call_counts["handler2"] += 1

        dispatcher.register_handler("market_data", failing_handler)
        dispatcher.register_handler("market_data", working_handler)

        event = MarketDataEvent(
            asset_symbol="AAPL",
            open=Decimal("150"),
            high=Decimal("151"),
            low=Decimal("149"),
            close=Decimal("150.50"),
            volume=Decimal("1000000"),
            bar_timestamp=pd.Timestamp.now(),
        )

        # Should not raise exception
        await dispatcher.dispatch(event)

        # Both handlers should have been called
        assert call_counts["handler1"] == 1
        assert call_counts["handler2"] == 1

    @pytest.mark.asyncio
    async def test_unregister_handler(self):
        """Test unregistering handlers."""
        dispatcher = EventDispatcher()

        async def handler(event):
            pass

        dispatcher.register_handler("market_data", handler)
        assert dispatcher.get_handler_count("market_data") == 1

        dispatcher.unregister_handler("market_data", handler)
        assert dispatcher.get_handler_count("market_data") == 0

    @pytest.mark.asyncio
    async def test_clear_handlers(self):
        """Test clearing all handlers."""
        dispatcher = EventDispatcher()

        async def handler1(event):
            pass

        async def handler2(event):
            pass

        dispatcher.register_handler("market_data", handler1)
        dispatcher.register_handler("order_fill", handler2)

        assert dispatcher.get_handler_count("market_data") == 1
        assert dispatcher.get_handler_count("order_fill") == 1

        dispatcher.clear_handlers()

        assert dispatcher.get_handler_count("market_data") == 0
        assert dispatcher.get_handler_count("order_fill") == 0

    @pytest.mark.asyncio
    async def test_clear_handlers_by_type(self):
        """Test clearing handlers for specific event type."""
        dispatcher = EventDispatcher()

        async def handler1(event):
            pass

        async def handler2(event):
            pass

        dispatcher.register_handler("market_data", handler1)
        dispatcher.register_handler("order_fill", handler2)

        dispatcher.clear_handlers("market_data")

        assert dispatcher.get_handler_count("market_data") == 0
        assert dispatcher.get_handler_count("order_fill") == 1
