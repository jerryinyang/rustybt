"""Tests for Lighter.xyz WebSocket streaming adapter.

Tests cover:
- Connection management
- Subscription/unsubscription
- Message parsing (trades, candles, errors)
- Bar aggregation from ticks
- Reconnection with buffering
- Multi-channel subscription

Uses mocks for WebSocket to avoid network dependencies.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rustybt.live.streaming.bar_buffer import OHLCVBar
from rustybt.live.streaming.base import ConnectionState, SubscriptionError
from rustybt.live.streaming.lighter_stream import (
    LighterStreamConfig,
    LighterWebSocketAdapter,
)
from rustybt.live.streaming.models import StreamConfig, TickData, TickSide

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create test configuration."""
    return LighterStreamConfig(
        bar_resolution=60,
        heartbeat_interval=30,
        heartbeat_timeout=60,
        reconnect_attempts=3,
    )


@pytest.fixture
def adapter(config):
    """Create LighterWebSocketAdapter instance for testing."""
    return LighterWebSocketAdapter(testnet=True, config=config)


@pytest.fixture
def trade_message():
    """Sample trade message from Lighter WebSocket."""
    return {
        "type": "trade",
        "data": {
            "symbol": "BTC-PERP",
            "price": "42000.50",
            "size": "0.1",
            "side": "buy",
            "timestamp": 1704067200000,
        },
    }


@pytest.fixture
def candle_message():
    """Sample candle message from Lighter WebSocket."""
    return {
        "type": "candle",
        "data": {
            "symbol": "BTC-PERP",
            "open": "42000.00",
            "high": "42500.00",
            "low": "41800.00",
            "close": "42300.00",
            "volume": "1234.56",
            "timestamp": 1704067200000,
        },
    }


@pytest.fixture
def subscription_confirmation():
    """Sample subscription confirmation message."""
    return {
        "type": "subscribed",
        "channel": "trades",
        "symbol": "BTC-PERP",
    }


@pytest.fixture
def error_message():
    """Sample error message."""
    return {
        "type": "error",
        "message": "Invalid symbol",
    }


# =============================================================================
# Configuration Tests
# =============================================================================


class TestLighterStreamConfig:
    """Tests for LighterStreamConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LighterStreamConfig()

        assert config.bar_resolution == 60
        assert config.heartbeat_interval == 30
        assert config.heartbeat_timeout == 60
        assert config.max_symbols_per_subscription == 50
        assert config.enable_trade_stream is True
        assert config.enable_orderbook_stream is False

    def test_custom_config(self):
        """Test custom configuration values."""
        config = LighterStreamConfig(
            bar_resolution=300,
            max_symbols_per_subscription=100,
            enable_orderbook_stream=True,
        )

        assert config.bar_resolution == 300
        assert config.max_symbols_per_subscription == 100
        assert config.enable_orderbook_stream is True


# =============================================================================
# Initialization Tests
# =============================================================================


class TestInitialization:
    """Tests for adapter initialization."""

    def test_testnet_url(self):
        """Test testnet URL is used by default."""
        adapter = LighterWebSocketAdapter(testnet=True)
        assert "testnet" in adapter.url

    def test_mainnet_url(self):
        """Test mainnet URL when testnet=False."""
        adapter = LighterWebSocketAdapter(testnet=False)
        assert "mainnet" in adapter.url

    def test_standard_config_converted(self):
        """Test standard StreamConfig is converted to LighterStreamConfig."""
        standard_config = StreamConfig(bar_resolution=120)
        adapter = LighterWebSocketAdapter(testnet=True, config=standard_config)

        assert adapter.config.bar_resolution == 120

    def test_bar_buffer_initialized(self, adapter):
        """Test bar buffer is initialized."""
        assert adapter._bar_buffer is not None
        assert adapter._bar_buffer.bar_resolution == 60


# =============================================================================
# Message Parsing Tests (Story 10.5.4)
# =============================================================================


class TestMessageParsing:
    """Tests for message parsing."""

    def test_parse_trade_message(self, adapter, trade_message):
        """Test parsing trade message to TickData."""
        tick = adapter.parse_message(trade_message)

        assert tick is not None
        assert tick.symbol == "BTC-PERP"
        assert tick.price == Decimal("42000.50")
        assert tick.volume == Decimal("0.1")
        assert tick.side == TickSide.BUY
        assert isinstance(tick.timestamp, datetime)

    def test_parse_trade_with_different_field_names(self, adapter):
        """Test parsing trade with alternative field names."""
        message = {
            "type": "trade",
            "data": {
                "market": "ETH-PERP",
                "px": "2500.00",
                "sz": "1.5",
                "s": "sell",
                "ts": 1704067200,  # Seconds
            },
        }

        tick = adapter.parse_message(message)

        assert tick is not None
        assert tick.symbol == "ETH-PERP"
        assert tick.price == Decimal("2500.00")
        assert tick.volume == Decimal("1.5")
        assert tick.side == TickSide.SELL

    def test_parse_candle_message(self, adapter, candle_message):
        """Test parsing candle message."""
        tick = adapter.parse_message(candle_message)

        assert tick is not None
        assert tick.symbol == "BTC-PERP"
        assert tick.price == Decimal("42300.00")  # Close price

    def test_parse_subscription_confirmation(self, adapter, subscription_confirmation):
        """Test handling subscription confirmation."""
        tick = adapter.parse_message(subscription_confirmation)

        assert tick is None
        assert adapter._subscription_confirmed["BTC-PERP:trades"] is True

    def test_parse_error_message(self, adapter, error_message):
        """Test handling error message."""
        tick = adapter.parse_message(error_message)

        assert tick is None

    def test_parse_heartbeat_message(self, adapter):
        """Test handling heartbeat/pong message."""
        tick = adapter.parse_message({"type": "pong"})
        assert tick is None

        tick = adapter.parse_message({"type": "heartbeat"})
        assert tick is None

    def test_parse_unknown_message(self, adapter):
        """Test handling unknown message type."""
        tick = adapter.parse_message({"type": "unknown", "data": {}})
        assert tick is None

    def test_parse_buy_side_variants(self, adapter):
        """Test parsing various buy side indicators."""
        for side_str in ["buy", "b", "bid", "long"]:
            message = {
                "type": "trade",
                "data": {
                    "symbol": "BTC-PERP",
                    "price": "42000",
                    "size": "0.1",
                    "side": side_str,
                    "timestamp": 1704067200000,
                },
            }
            tick = adapter.parse_message(message)
            assert tick.side == TickSide.BUY, f"Failed for side: {side_str}"

    def test_parse_sell_side_variants(self, adapter):
        """Test parsing various sell side indicators."""
        for side_str in ["sell", "s", "ask", "short"]:
            message = {
                "type": "trade",
                "data": {
                    "symbol": "BTC-PERP",
                    "price": "42000",
                    "size": "0.1",
                    "side": side_str,
                    "timestamp": 1704067200000,
                },
            }
            tick = adapter.parse_message(message)
            assert tick.side == TickSide.SELL, f"Failed for side: {side_str}"


# =============================================================================
# Subscription Tests (Story 10.5.5)
# =============================================================================


class TestSubscription:
    """Tests for subscription management."""

    @pytest.mark.asyncio
    async def test_subscribe_single_symbol(self, adapter):
        """Test subscribing to a single symbol."""
        adapter._state = ConnectionState.CONNECTED
        adapter._websocket = AsyncMock()

        await adapter.subscribe(["BTC-PERP"], ["trades"])

        assert "BTC-PERP" in adapter._subscriptions
        assert "trades" in adapter._subscriptions["BTC-PERP"]

    @pytest.mark.asyncio
    async def test_subscribe_multiple_symbols(self, adapter):
        """Test subscribing to multiple symbols."""
        adapter._state = ConnectionState.CONNECTED
        adapter._websocket = AsyncMock()

        await adapter.subscribe(["BTC-PERP", "ETH-PERP"], ["trades"])

        assert "BTC-PERP" in adapter._subscriptions
        assert "ETH-PERP" in adapter._subscriptions
        assert adapter._websocket.send.call_count == 2

    @pytest.mark.asyncio
    async def test_subscribe_multiple_channels(self, adapter):
        """Test subscribing to multiple channels."""
        adapter._state = ConnectionState.CONNECTED
        adapter._websocket = AsyncMock()

        await adapter.subscribe(["BTC-PERP"], ["trades", "orderbook"])

        assert "trades" in adapter._subscriptions["BTC-PERP"]
        assert "orderbook" in adapter._subscriptions["BTC-PERP"]

    @pytest.mark.asyncio
    async def test_subscribe_not_connected_raises(self, adapter):
        """Test subscribing when not connected raises error."""
        adapter._state = ConnectionState.DISCONNECTED

        with pytest.raises(SubscriptionError, match="Not connected"):
            await adapter.subscribe(["BTC-PERP"], ["trades"])

    @pytest.mark.asyncio
    async def test_unsubscribe(self, adapter):
        """Test unsubscribing from symbol."""
        adapter._state = ConnectionState.CONNECTED
        adapter._websocket = AsyncMock()
        adapter._subscriptions["BTC-PERP"] = {"trades", "orderbook"}

        await adapter.unsubscribe(["BTC-PERP"], ["trades"])

        assert "trades" not in adapter._subscriptions["BTC-PERP"]
        assert "orderbook" in adapter._subscriptions["BTC-PERP"]

    @pytest.mark.asyncio
    async def test_unsubscribe_last_channel_removes_symbol(self, adapter):
        """Test unsubscribing last channel removes symbol entry."""
        adapter._state = ConnectionState.CONNECTED
        adapter._websocket = AsyncMock()
        adapter._subscriptions["BTC-PERP"] = {"trades"}

        await adapter.unsubscribe(["BTC-PERP"], ["trades"])

        assert "BTC-PERP" not in adapter._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_all_channels(self, adapter):
        """Test subscribing to all available channels."""
        adapter._state = ConnectionState.CONNECTED
        adapter._websocket = AsyncMock()

        # Enable orderbook in config
        adapter.config = LighterStreamConfig(enable_orderbook_stream=True)

        await adapter.subscribe_all_channels(["BTC-PERP"])

        assert "trades" in adapter._subscriptions["BTC-PERP"]
        assert "orderbook" in adapter._subscriptions["BTC-PERP"]


# =============================================================================
# Bar Aggregation Tests (Story 10.5.5)
# =============================================================================


class TestBarAggregation:
    """Tests for tick-to-bar aggregation."""

    def test_tick_added_to_buffer(self, adapter, trade_message):
        """Test that ticks are added to bar buffer."""
        # Parse trade message
        tick = adapter.parse_message(trade_message)

        # Buffer should have data for BTC-PERP
        assert "BTC-PERP" in adapter._bar_buffer._current_bars

    def test_bar_callback_on_complete(self, adapter):
        """Test bar callback is called when bar completes."""
        completed_bars = []

        def on_bar(bar: OHLCVBar):
            completed_bars.append(bar)

        adapter.on_bar = on_bar

        # Simulate ticks crossing bar boundary
        base_ts = 1704067200000  # Start of a minute

        # First tick - starts bar
        msg1 = {
            "type": "trade",
            "data": {
                "symbol": "BTC-PERP",
                "price": "42000.00",
                "size": "0.1",
                "side": "buy",
                "timestamp": base_ts,
            },
        }
        adapter.parse_message(msg1)

        # Second tick - crosses to next minute
        msg2 = {
            "type": "trade",
            "data": {
                "symbol": "BTC-PERP",
                "price": "42100.00",
                "size": "0.2",
                "side": "buy",
                "timestamp": base_ts + 60000,  # Next minute
            },
        }
        adapter.parse_message(msg2)

        # Bar should have been completed
        assert len(completed_bars) == 1
        assert completed_bars[0].symbol == "BTC-PERP"

    def test_flush_bars(self, adapter, trade_message):
        """Test flushing incomplete bars."""
        # Add tick to buffer
        adapter.parse_message(trade_message)

        # Flush bars
        flushed = adapter.flush_bars()

        assert "BTC-PERP" in flushed
        assert isinstance(flushed["BTC-PERP"], OHLCVBar)

    def test_get_bar_buffer_state(self, adapter, trade_message):
        """Test getting bar buffer state."""
        # Add tick to buffer
        adapter.parse_message(trade_message)

        state = adapter.get_bar_buffer_state()

        assert state["enabled"] is True
        assert state["bar_resolution"] == 60
        assert "BTC-PERP" in state["symbols_buffering"]


# =============================================================================
# Buffering Tests (Story 10.5.6)
# =============================================================================


class TestBuffering:
    """Tests for message buffering during reconnection."""

    def test_enable_buffering(self, adapter):
        """Test enabling buffering."""
        adapter.enable_buffering()

        assert adapter._buffering_enabled is True
        assert len(adapter._message_buffer) == 0

    def test_disable_buffering(self, adapter):
        """Test disabling buffering clears buffer."""
        adapter.enable_buffering()
        adapter._message_buffer.append({"test": "message"})

        adapter.disable_buffering()

        assert adapter._buffering_enabled is False
        assert len(adapter._message_buffer) == 0

    def test_get_buffered_messages(self, adapter):
        """Test getting buffered messages returns copy."""
        adapter.enable_buffering()
        test_msg = {"test": "message"}
        adapter._message_buffer.append(test_msg)

        buffered = adapter.get_buffered_messages()

        assert len(buffered) == 1
        assert buffered[0] == test_msg
        # Verify it's a copy
        buffered.append({"another": "message"})
        assert len(adapter._message_buffer) == 1

    @pytest.mark.asyncio
    async def test_replay_buffer_empty(self, adapter):
        """Test replaying empty buffer does nothing."""
        await adapter.replay_buffer()  # Should not raise

    @pytest.mark.asyncio
    async def test_replay_buffer_with_messages(self, adapter, trade_message):
        """Test replaying buffer processes messages."""
        ticks_received = []

        def on_tick(tick: TickData):
            ticks_received.append(tick)

        adapter.on_tick = on_tick
        adapter._message_buffer.append(trade_message)

        await adapter.replay_buffer()

        assert len(ticks_received) == 1
        assert ticks_received[0].symbol == "BTC-PERP"
        assert len(adapter._message_buffer) == 0


# =============================================================================
# Message Format Tests
# =============================================================================


class TestMessageFormat:
    """Tests for subscription message format."""

    def test_subscription_message_format(self, adapter):
        """Test subscription message format."""
        msg = adapter._build_subscription_message(["BTC-PERP"], ["trades"])

        assert msg["method"] == "subscribe"
        assert msg["params"]["channel"] == "trades"
        assert msg["params"]["symbol"] == "BTC-PERP"

    def test_unsubscription_message_format(self, adapter):
        """Test unsubscription message format."""
        msg = adapter._build_unsubscription_message(["BTC-PERP"], ["trades"])

        assert msg["method"] == "unsubscribe"
        assert msg["params"]["channel"] == "trades"
        assert msg["params"]["symbol"] == "BTC-PERP"


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestContextManager:
    """Tests for context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager(self, adapter):
        """Test async context manager connect/disconnect."""
        with patch.object(adapter, "connect", new_callable=AsyncMock) as mock_connect:
            with patch.object(adapter, "disconnect", new_callable=AsyncMock) as mock_disconnect:
                async with adapter:
                    mock_connect.assert_called_once()

                mock_disconnect.assert_called_once()


# =============================================================================
# Integration Tests (skipped without credentials)
# =============================================================================


@pytest.mark.integration
@pytest.mark.skip(reason="Requires live WebSocket connection")
class TestLighterStreamIntegration:
    """Integration tests for Lighter WebSocket adapter.

    These tests connect to the actual Lighter.xyz testnet WebSocket.
    Skipped by default - run manually for integration testing.
    """

    @pytest.mark.asyncio
    async def test_live_connect_and_subscribe(self):
        """Test live connection and subscription."""
        ticks_received = []

        def on_tick(tick: TickData):
            ticks_received.append(tick)

        adapter = LighterWebSocketAdapter(testnet=True, on_tick=on_tick)

        async with adapter:
            await adapter.subscribe(["BTC-PERP"], ["trades"])

            # Wait for some ticks
            await asyncio.sleep(10)

        assert len(ticks_received) > 0
