"""Unit tests for Bybit broker adapter."""

from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rustybt.assets import Equity
from rustybt.live.brokers.bybit_adapter import (
    BybitBrokerAdapter,
    BybitConnectionError,
    BybitOrderRejectError,
)


@pytest.fixture
def bybit_adapter():
    """Create Bybit adapter with test credentials."""
    with patch("rustybt.live.brokers.bybit_adapter.HTTP") as mock_http:
        adapter = BybitBrokerAdapter(
            api_key="test_api_key",
            api_secret="test_api_secret",
            market_type="linear",
            testnet=True,
        )
        adapter.client = mock_http.return_value
        return adapter


@pytest.fixture
def test_asset():
    """Create test asset."""
    return Equity(
        sid=1,
        symbol="BTCUSDT",
        exchange="BYBIT",
        start_date=None,
        end_date=None,
    )


class TestBybitAdapter:
    """Test suite for BybitBrokerAdapter."""

    def test_initialization(self, bybit_adapter):
        """Test adapter initialization."""
        assert bybit_adapter.api_key == "test_api_key"
        assert bybit_adapter.market_type == "linear"
        assert bybit_adapter.testnet is True
        assert not bybit_adapter.is_connected()

    def test_invalid_market_type(self):
        """Test initialization with invalid market type."""
        with pytest.raises(ValueError, match="Invalid market_type"):
            BybitBrokerAdapter(
                api_key="test",
                api_secret="test",
                market_type="invalid",
            )

    @pytest.mark.asyncio
    async def test_connect_success(self, bybit_adapter):
        """Test successful connection."""
        # Mock server time response
        bybit_adapter.client.get_server_time.return_value = {
            "retCode": 0,
            "result": {"timeSecond": "1234567890"},
        }

        # Connect
        await bybit_adapter.connect()

        # Verify
        assert bybit_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_connect_failure(self, bybit_adapter):
        """Test connection failure."""
        # Mock error response
        bybit_adapter.client.get_server_time.return_value = {
            "retCode": 10001,
            "retMsg": "Authentication failed",
        }

        # Should raise connection error
        with pytest.raises(BybitConnectionError, match="Failed to connect"):
            await bybit_adapter.connect()

        assert not bybit_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_submit_market_order_success(self, bybit_adapter, test_asset):
        """Test successful market order submission."""
        bybit_adapter._connected = True

        # Mock order response
        bybit_adapter.client.place_order.return_value = {
            "retCode": 0,
            "result": {"orderId": "test-order-123"},
        }

        # Submit order
        order_id = await bybit_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="market",
        )

        # Verify
        assert order_id == "test-order-123"

    @pytest.mark.asyncio
    async def test_submit_limit_order_success(self, bybit_adapter, test_asset):
        """Test successful limit order submission."""
        bybit_adapter._connected = True

        # Mock order response
        bybit_adapter.client.place_order.return_value = {
            "retCode": 0,
            "result": {"orderId": "test-order-124"},
        }

        # Submit limit order
        order_id = await bybit_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="limit",
            limit_price=Decimal("50000"),
        )

        # Verify
        assert order_id == "test-order-124"

    @pytest.mark.asyncio
    async def test_submit_order_insufficient_balance(self, bybit_adapter, test_asset):
        """Test order rejection due to insufficient balance."""
        bybit_adapter._connected = True

        # Mock error response
        bybit_adapter.client.place_order.return_value = {
            "retCode": 110001,
            "retMsg": "Insufficient balance",
        }

        # Should raise order reject error
        with pytest.raises(BybitOrderRejectError, match="Insufficient balance"):
            await bybit_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("100"),
                order_type="market",
            )

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, bybit_adapter):
        """Test successful order cancellation."""
        bybit_adapter._connected = True

        # Mock cancel response
        bybit_adapter.client.cancel_order.return_value = {
            "retCode": 0,
            "result": {},
        }

        # Cancel order
        await bybit_adapter.cancel_order("BTCUSDT:test-order-123")

        # Should not raise

    @pytest.mark.asyncio
    async def test_get_account_info_linear(self, bybit_adapter):
        """Test get account info for linear (unified) account."""
        bybit_adapter._connected = True

        # Mock wallet balance response
        bybit_adapter.client.get_wallet_balance.return_value = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "totalEquity": "10500.0",
                        "totalAvailableBalance": "10000.0",
                    }
                ]
            },
        }

        # Get account info
        account_info = await bybit_adapter.get_account_info()

        # Verify
        assert account_info["cash"] == Decimal("10000.0")
        assert account_info["equity"] == Decimal("10500.0")

    @pytest.mark.asyncio
    async def test_get_positions_success(self, bybit_adapter):
        """Test get positions."""
        bybit_adapter._connected = True

        # Mock positions response
        bybit_adapter.client.get_positions.return_value = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "size": "0.5",
                        "side": "Buy",
                        "avgPrice": "50000.0",
                        "markPrice": "51000.0",
                        "unrealisedPnl": "500.0",
                    }
                ]
            },
        }

        # Get positions
        positions = await bybit_adapter.get_positions()

        # Verify
        assert len(positions) == 1
        assert positions[0]["symbol"] == "BTCUSDT"
        assert positions[0]["amount"] == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_get_current_price(self, bybit_adapter, test_asset):
        """Test get current price."""
        bybit_adapter._connected = True

        # Mock ticker response
        bybit_adapter.client.get_tickers.return_value = {
            "retCode": 0,
            "result": {"list": [{"symbol": "BTCUSDT", "lastPrice": "51000.50"}]},
        }

        # Get price
        price = await bybit_adapter.get_current_price(test_asset)

        # Verify
        assert price == Decimal("51000.50")

    def test_get_category(self, bybit_adapter):
        """Test category mapping."""
        assert bybit_adapter._get_category() == "linear"

        bybit_adapter.market_type = "spot"
        assert bybit_adapter._get_category() == "spot"

        bybit_adapter.market_type = "inverse"
        assert bybit_adapter._get_category() == "inverse"

    def test_order_type_mapping(self, bybit_adapter):
        """Test order type mapping."""
        assert bybit_adapter._map_order_type("market") == "Market"
        assert bybit_adapter._map_order_type("limit") == "Limit"

        with pytest.raises(ValueError, match="Unsupported order type"):
            bybit_adapter._map_order_type("invalid")


# ====================================================================================
# WebSocket Integration Tests (AC 1, 4, 5)
# ====================================================================================


class TestBybitWebSocketIntegration:
    """Test WebSocket integration for Bybit adapter (AC 1, 4, 5)."""

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_subscription_multiple_symbols(self, bybit_adapter, test_asset):
        """Test WebSocket subscription with multiple symbols (AC 1)."""
        bybit_adapter._connected = True

        # Mock WebSocket adapter
        mock_ws = AsyncMock()
        bybit_adapter._ws_adapter = mock_ws

        # Create test assets
        asset1 = test_asset
        asset2 = Equity(sid=2, symbol="ETHUSDT", exchange="BYBIT", start_date=None, end_date=None)

        # Subscribe to market data
        await bybit_adapter.subscribe_market_data([asset1, asset2])

        # Verify WebSocket subscribe was called with correct symbols and channels
        mock_ws.subscribe.assert_called_once_with(
            symbols=["BTCUSDT", "ETHUSDT"], channels=["publicTrade"]
        )

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_unsubscription(self, bybit_adapter, test_asset):
        """Test WebSocket unsubscription (AC 1)."""
        bybit_adapter._connected = True

        # Mock WebSocket adapter
        mock_ws = AsyncMock()
        bybit_adapter._ws_adapter = mock_ws

        # Unsubscribe from market data
        await bybit_adapter.unsubscribe_market_data([test_asset])

        # Verify WebSocket unsubscribe was called
        mock_ws.unsubscribe.assert_called_once_with(symbols=["BTCUSDT"], channels=["publicTrade"])

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_lifecycle_connect(self, bybit_adapter):
        """Test WebSocket connects when broker connect() is called (AC 4)."""
        # Mock server time and WebSocket adapter
        bybit_adapter.client.get_server_time.return_value = {
            "retCode": 0,
            "result": {"timeSecond": "1234567890"},
        }

        # Connect broker (should initialize and connect WebSocket)
        await bybit_adapter.connect()

        # Verify WebSocket adapter was initialized
        assert bybit_adapter._ws_adapter is not None
        assert bybit_adapter._bar_buffer is not None
        assert bybit_adapter.is_connected()

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_lifecycle_disconnect(self, bybit_adapter):
        """Test WebSocket disconnects when broker disconnect() is called (AC 4)."""
        bybit_adapter._connected = True

        # Mock WebSocket adapter
        mock_ws = AsyncMock()
        bybit_adapter._ws_adapter = mock_ws

        # Disconnect broker (should disconnect WebSocket)
        await bybit_adapter.disconnect()

        # Verify WebSocket disconnect was called
        mock_ws.disconnect.assert_called_once()
        assert bybit_adapter._ws_adapter is None
        assert bybit_adapter._bar_buffer is None
        assert not bybit_adapter.is_connected()

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_tick_to_bar_buffer_flow(self, bybit_adapter):
        """Test TickData flows from WebSocket to BarBuffer (AC 5)."""
        from datetime import datetime

        from rustybt.live.streaming.models import TickData, TickSide

        # Setup connected adapter with bar buffer
        bybit_adapter._connected = True
        bar_buffer_mock = MagicMock()
        bybit_adapter._bar_buffer = bar_buffer_mock

        # Create a tick
        tick = TickData(
            symbol="BTCUSDT",
            timestamp=datetime.now(UTC),
            price=Decimal("50000.50"),
            volume=Decimal("0.1"),
            side=TickSide.BUY,
        )

        # Call the tick handler (simulates WebSocket callback)
        bybit_adapter._handle_tick(tick)

        # Verify tick was added to bar buffer
        bar_buffer_mock.add_tick.assert_called_once_with(tick)

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_bar_complete_to_queue(self, bybit_adapter):
        """Test completed OHLCV bar pushed to market data queue (AC 5)."""
        from datetime import datetime

        from rustybt.live.streaming.bar_buffer import OHLCVBar

        # Setup connected adapter
        bybit_adapter._connected = True

        # Create a completed bar
        bar = OHLCVBar(
            symbol="BTCUSDT",
            timestamp=datetime.now(UTC),
            open=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            close=Decimal("50050"),
            volume=Decimal("10.5"),
        )

        # Call the bar complete handler
        bybit_adapter._handle_bar_complete(bar)

        # Verify bar was pushed to queue
        assert not bybit_adapter._market_data_queue.empty()
        market_data = await bybit_adapter._market_data_queue.get()
        assert market_data["type"] == "bar"
        assert market_data["symbol"] == "BTCUSDT"
        assert market_data["close"] == Decimal("50050")


# ====================================================================================
# Advanced Order Type Tests (AC 7)
# ====================================================================================


class TestBybitAdvancedOrderTypes:
    """Test Post-Only and Reduce-Only order modes for Bybit (AC 7, 9)."""

    @pytest.mark.asyncio
    async def test_post_only_order_success(self, bybit_adapter, test_asset):
        """Test Post-Only order with timeInForce='PostOnly' (AC 7)."""
        bybit_adapter._connected = True

        # Mock order response
        bybit_adapter.client.place_order.return_value = {
            "retCode": 0,
            "result": {"orderId": "post-only-123"},
        }

        # Submit Post-Only limit order
        order_id = await bybit_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="limit",
            limit_price=Decimal("50000"),
            post_only=True,
        )

        # Verify order was submitted with correct params
        call_args = bybit_adapter.client.place_order.call_args
        assert call_args[1]["timeInForce"] == "PostOnly"
        assert order_id == "BTCUSDT:post-only-123"

    @pytest.mark.asyncio
    async def test_post_only_rejected_on_market_order(self, bybit_adapter, test_asset):
        """Test Post-Only incompatible with Market orders (AC 7)."""
        bybit_adapter._connected = True

        # Should raise ValueError when combining post_only with market order
        with pytest.raises(ValueError, match="Post-Only mode is incompatible with Market orders"):
            await bybit_adapter.submit_order(
                asset=test_asset, amount=Decimal("0.1"), order_type="market", post_only=True
            )

    @pytest.mark.asyncio
    async def test_reduce_only_order_success(self, bybit_adapter, test_asset):
        """Test Reduce-Only order with reduceOnly=True (AC 7)."""
        bybit_adapter._connected = True

        # Mock order response
        bybit_adapter.client.place_order.return_value = {
            "retCode": 0,
            "result": {"orderId": "reduce-only-456"},
        }

        # Submit Reduce-Only market order
        order_id = await bybit_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("-0.1"),  # Sell to reduce position
            order_type="market",
            reduce_only=True,
        )

        # Verify order was submitted with reduceOnly=True
        call_args = bybit_adapter.client.place_order.call_args
        assert call_args[1]["reduceOnly"] is True
        assert order_id == "BTCUSDT:reduce-only-456"

    @pytest.mark.asyncio
    async def test_combined_post_only_reduce_only(self, bybit_adapter, test_asset):
        """Test Post-Only and Reduce-Only can be combined (AC 7, 9)."""
        bybit_adapter._connected = True

        # Mock order response
        bybit_adapter.client.place_order.return_value = {
            "retCode": 0,
            "result": {"orderId": "combined-789"},
        }

        # Submit order with both Post-Only and Reduce-Only
        order_id = await bybit_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("-0.1"),
            order_type="limit",
            limit_price=Decimal("51000"),
            post_only=True,
            reduce_only=True,
        )

        # Verify both params were sent
        call_args = bybit_adapter.client.place_order.call_args
        assert call_args[1]["timeInForce"] == "PostOnly"
        assert call_args[1]["reduceOnly"] is True
        assert order_id == "BTCUSDT:combined-789"
