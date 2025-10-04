"""Tests for Binance WebSocket adapter."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from rustybt.live.streaming.base import ParseError, SubscriptionError
from rustybt.live.streaming.binance_stream import BinanceWebSocketAdapter
from rustybt.live.streaming.models import TickSide


class TestBinanceWebSocketAdapter:
    """Tests for BinanceWebSocketAdapter."""

    @pytest.fixture
    def spot_adapter(self) -> BinanceWebSocketAdapter:
        """Create Binance spot adapter."""
        return BinanceWebSocketAdapter(market_type="spot")

    @pytest.fixture
    def futures_adapter(self) -> BinanceWebSocketAdapter:
        """Create Binance futures adapter."""
        return BinanceWebSocketAdapter(market_type="futures")

    def test_spot_adapter_initialization(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test spot adapter initialization."""
        assert spot_adapter.market_type == "spot"
        assert spot_adapter.url == BinanceWebSocketAdapter.SPOT_URL

    def test_futures_adapter_initialization(self, futures_adapter: BinanceWebSocketAdapter) -> None:
        """Test futures adapter initialization."""
        assert futures_adapter.market_type == "futures"
        assert futures_adapter.url == BinanceWebSocketAdapter.FUTURES_URL

    def test_invalid_market_type(self) -> None:
        """Test invalid market type."""
        with pytest.raises(ValueError, match="Invalid market_type"):
            BinanceWebSocketAdapter(market_type="invalid")

    @pytest.mark.asyncio
    async def test_subscribe(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test subscription."""
        mock_ws = AsyncMock()

        async def async_connect(*args, **kwargs):
            return mock_ws

        with patch("rustybt.live.streaming.base.websockets.connect", side_effect=async_connect):
            await spot_adapter.connect()
            await spot_adapter.subscribe(["BTCUSDT"], ["kline_1m", "trade"])

            # Check subscription message sent
            assert mock_ws.send.called
            call_args = mock_ws.send.call_args[0][0]
            assert "SUBSCRIBE" in call_args
            assert "btcusdt@kline_1m" in call_args
            assert "btcusdt@trade" in call_args

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test subscribe when not connected."""
        with pytest.raises(SubscriptionError, match="Not connected"):
            await spot_adapter.subscribe(["BTCUSDT"], ["kline_1m"])

    @pytest.mark.asyncio
    async def test_unsubscribe(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test unsubscription."""
        mock_ws = AsyncMock()

        async def async_connect(*args, **kwargs):
            return mock_ws

        with patch("rustybt.live.streaming.base.websockets.connect", side_effect=async_connect):
            await spot_adapter.connect()
            await spot_adapter.subscribe(["BTCUSDT"], ["kline_1m"])
            await spot_adapter.unsubscribe(["BTCUSDT"], ["kline_1m"])

            # Check unsubscription message sent
            calls = [call[0][0] for call in mock_ws.send.call_args_list]
            assert any("UNSUBSCRIBE" in call for call in calls)

    def test_parse_kline_message(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test parsing kline message."""
        message = {
            "e": "kline",
            "E": 1638747420000,
            "s": "BTCUSDT",
            "k": {
                "t": 1638747360000,
                "T": 1638747419999,
                "s": "BTCUSDT",
                "i": "1m",
                "o": "49500.00",
                "c": "49550.00",
                "h": "49600.00",
                "l": "49480.00",
                "v": "123.456",
                "x": False,
            },
        }

        tick = spot_adapter.parse_message(message)

        assert tick is not None
        assert tick.symbol == "BTCUSDT"
        assert tick.price == Decimal("49550.00")  # Close price
        assert tick.volume == Decimal("123.456")
        assert tick.side == TickSide.UNKNOWN

    def test_parse_trade_message(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test parsing trade message."""
        message = {
            "e": "trade",
            "E": 1638747420000,
            "s": "BTCUSDT",
            "t": 123456,
            "p": "49500.00",
            "q": "0.5",
            "T": 1638747420000,
            "m": True,  # Buyer is maker (sell)
        }

        tick = spot_adapter.parse_message(message)

        assert tick is not None
        assert tick.symbol == "BTCUSDT"
        assert tick.price == Decimal("49500.00")
        assert tick.volume == Decimal("0.5")
        assert tick.side == TickSide.SELL

    def test_parse_trade_message_buy_side(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test parsing trade message with buy side."""
        message = {
            "e": "trade",
            "E": 1638747420000,
            "s": "ETHUSDT",
            "t": 123457,
            "p": "3000.00",
            "q": "2.0",
            "T": 1638747420000,
            "m": False,  # Buyer is taker (buy)
        }

        tick = spot_adapter.parse_message(message)

        assert tick is not None
        assert tick.symbol == "ETHUSDT"
        assert tick.side == TickSide.BUY

    def test_parse_subscription_confirmation(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test parsing subscription confirmation."""
        message = {"result": None, "id": 1}

        tick = spot_adapter.parse_message(message)

        assert tick is None  # No tick data for confirmation

    def test_parse_error_message(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test parsing error message."""
        message = {"error": {"code": -1121, "msg": "Invalid symbol"}}

        with pytest.raises(ParseError, match="Invalid symbol"):
            spot_adapter.parse_message(message)

    def test_parse_unknown_event_type(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test parsing unknown event type."""
        message = {"e": "unknown_event", "data": "something"}

        tick = spot_adapter.parse_message(message)

        assert tick is None

    def test_parse_invalid_kline_message(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test parsing invalid kline message."""
        message = {
            "e": "kline",
            "E": 1638747420000,
            # Missing 'k' field
        }

        with pytest.raises(ParseError, match="Failed to parse kline message"):
            spot_adapter.parse_message(message)

    def test_parse_invalid_trade_message(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test parsing invalid trade message."""
        message = {
            "e": "trade",
            "E": 1638747420000,
            # Missing required fields
        }

        with pytest.raises(ParseError, match="Failed to parse trade message"):
            spot_adapter.parse_message(message)

    def test_build_subscription_message(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test building subscription message."""
        message = spot_adapter._build_subscription_message(
            ["BTCUSDT", "ETHUSDT"],
            ["kline_1m", "trade"],
        )

        assert message["method"] == "SUBSCRIBE"
        assert "btcusdt@kline_1m" in message["params"]
        assert "btcusdt@trade" in message["params"]
        assert "ethusdt@kline_1m" in message["params"]
        assert "ethusdt@trade" in message["params"]

    def test_build_unsubscription_message(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test building unsubscription message."""
        message = spot_adapter._build_unsubscription_message(
            ["BTCUSDT"],
            ["kline_1m"],
        )

        assert message["method"] == "UNSUBSCRIBE"
        assert "btcusdt@kline_1m" in message["params"]

    def test_symbol_case_conversion(self, spot_adapter: BinanceWebSocketAdapter) -> None:
        """Test symbols are converted to lowercase."""
        message = spot_adapter._build_subscription_message(
            ["BTCUSDT"],  # Uppercase
            ["kline_1m"],
        )

        # Binance requires lowercase
        assert "btcusdt@kline_1m" in message["params"]
