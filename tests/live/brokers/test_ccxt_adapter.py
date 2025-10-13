"""Unit tests for CCXT broker adapter."""

from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import ccxt
import pytest

from rustybt.assets import Equity
from rustybt.live.brokers.ccxt_adapter import (
    CCXTBrokerAdapter,
    CCXTConnectionError,
    CCXTOrderRejectError,
    CCXTRateLimitError,
)


@pytest.fixture
def ccxt_adapter():
    """Create CCXT adapter with test credentials."""
    with patch("ccxt.async_support.binance") as mock_exchange:
        adapter = CCXTBrokerAdapter(
            exchange_id="binance",
            api_key="test_api_key",
            api_secret="test_api_secret",
            market_type="spot",
            testnet=True,
        )
        adapter.exchange = mock_exchange.return_value
        return adapter


@pytest.fixture
def test_asset():
    """Create test asset."""
    return Equity(
        sid=1,
        symbol="BTC/USDT",
        exchange="BINANCE",
        start_date=None,
        end_date=None,
    )


class TestCCXTAdapter:
    """Test suite for CCXTBrokerAdapter."""

    def test_initialization(self, ccxt_adapter):
        """Test adapter initialization."""
        assert ccxt_adapter.exchange_id == "binance"
        assert ccxt_adapter.api_key == "test_api_key"
        assert ccxt_adapter.market_type == "spot"
        assert ccxt_adapter.testnet is True
        assert not ccxt_adapter.is_connected()

    def test_invalid_exchange(self):
        """Test initialization with invalid exchange."""
        with pytest.raises(ValueError, match="Unsupported exchange"):
            CCXTBrokerAdapter(
                exchange_id="invalid_exchange_xyz",
                api_key="test",
                api_secret="test",
            )

    @pytest.mark.asyncio
    async def test_connect_success(self, ccxt_adapter):
        """Test successful connection."""
        # Mock load_markets
        ccxt_adapter.exchange.load_markets = AsyncMock(return_value={})

        # Mock fetch_balance
        ccxt_adapter.exchange.fetch_balance = AsyncMock(
            return_value={"USDT": {"free": 10000, "used": 0, "total": 10000}}
        )

        # Connect
        await ccxt_adapter.connect()

        # Verify
        assert ccxt_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_connect_network_error(self, ccxt_adapter):
        """Test connection failure due to network error."""
        # Mock network error
        ccxt_adapter.exchange.load_markets = AsyncMock(
            side_effect=ccxt.NetworkError("Connection timeout")
        )

        # Should raise connection error
        with pytest.raises(CCXTConnectionError, match="Network error"):
            await ccxt_adapter.connect()

        assert not ccxt_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_submit_market_order_success(self, ccxt_adapter, test_asset):
        """Test successful market order submission."""
        ccxt_adapter._connected = True

        # Mock order response
        ccxt_adapter.exchange.create_order = AsyncMock(
            return_value={
                "id": "test-order-123",
                "symbol": "BTC/USDT",
                "type": "market",
                "side": "buy",
            }
        )

        # Submit order
        order_id = await ccxt_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="market",
        )

        # Verify
        assert order_id == "test-order-123"

    @pytest.mark.asyncio
    async def test_submit_limit_order_success(self, ccxt_adapter, test_asset):
        """Test successful limit order submission."""
        ccxt_adapter._connected = True

        # Mock order response
        ccxt_adapter.exchange.create_order = AsyncMock(
            return_value={
                "id": "test-order-124",
                "symbol": "BTC/USDT",
                "type": "limit",
                "side": "buy",
            }
        )

        # Submit limit order
        order_id = await ccxt_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="limit",
            limit_price=Decimal("50000"),
        )

        # Verify
        assert order_id == "test-order-124"

    @pytest.mark.asyncio
    async def test_submit_order_insufficient_funds(self, ccxt_adapter, test_asset):
        """Test order rejection due to insufficient funds."""
        ccxt_adapter._connected = True

        # Mock insufficient funds error
        ccxt_adapter.exchange.create_order = AsyncMock(
            side_effect=ccxt.InsufficientFunds("Insufficient balance")
        )

        # Should raise order reject error
        with pytest.raises(CCXTOrderRejectError, match="Insufficient funds"):
            await ccxt_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("100"),
                order_type="market",
            )

    @pytest.mark.asyncio
    async def test_submit_order_rate_limit(self, ccxt_adapter, test_asset):
        """Test rate limit error."""
        ccxt_adapter._connected = True

        # Mock rate limit error
        ccxt_adapter.exchange.create_order = AsyncMock(
            side_effect=ccxt.RateLimitExceeded("Rate limit exceeded")
        )

        # Should raise rate limit error
        with pytest.raises(CCXTRateLimitError, match="Rate limit exceeded"):
            await ccxt_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("0.1"),
                order_type="market",
            )

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, ccxt_adapter):
        """Test successful order cancellation."""
        ccxt_adapter._connected = True

        # Mock cancel response
        ccxt_adapter.exchange.cancel_order = AsyncMock(return_value={})

        # Cancel order
        await ccxt_adapter.cancel_order("BTC/USDT:test-order-123")

        # Should not raise

    @pytest.mark.asyncio
    async def test_get_account_info(self, ccxt_adapter):
        """Test get account info."""
        ccxt_adapter._connected = True

        # Mock balance response
        ccxt_adapter.exchange.fetch_balance = AsyncMock(
            return_value={"USDT": {"free": "10000.0", "used": "500.0", "total": "10500.0"}}
        )

        # Get account info
        account_info = await ccxt_adapter.get_account_info()

        # Verify
        assert account_info["cash"] == Decimal("10000.0")
        assert account_info["equity"] == Decimal("10500.0")

    @pytest.mark.asyncio
    async def test_get_positions_supported(self, ccxt_adapter):
        """Test get positions when exchange supports it."""
        ccxt_adapter._connected = True
        ccxt_adapter.exchange.has = {"fetchPositions": True}

        # Mock positions response
        ccxt_adapter.exchange.fetch_positions = AsyncMock(
            return_value=[
                {
                    "symbol": "BTC/USDT",
                    "contracts": 0.5,
                    "side": "long",
                    "entryPrice": 50000.0,
                    "markPrice": 51000.0,
                    "notional": 25500.0,
                    "unrealizedPnl": 500.0,
                }
            ]
        )

        # Get positions
        positions = await ccxt_adapter.get_positions()

        # Verify
        assert len(positions) == 1
        assert positions[0]["symbol"] == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_get_positions_not_supported(self, ccxt_adapter):
        """Test get positions when exchange doesn't support it."""
        ccxt_adapter._connected = True
        ccxt_adapter.exchange.has = {"fetchPositions": False}

        # Get positions
        positions = await ccxt_adapter.get_positions()

        # Should return empty list
        assert positions == []

    @pytest.mark.asyncio
    async def test_get_current_price(self, ccxt_adapter, test_asset):
        """Test get current price."""
        ccxt_adapter._connected = True

        # Mock ticker response
        ccxt_adapter.exchange.fetch_ticker = AsyncMock(
            return_value={"symbol": "BTC/USDT", "last": 51000.50}
        )

        # Get price
        price = await ccxt_adapter.get_current_price(test_asset)

        # Verify
        assert price == Decimal("51000.50")

    def test_get_exchange_capabilities(self, ccxt_adapter):
        """Test get exchange capabilities."""
        ccxt_adapter.exchange.has = {
            "fetchPositions": True,
            "fetchOHLCV": True,
            "fetchTicker": True,
        }

        capabilities = ccxt_adapter.get_exchange_capabilities()

        assert capabilities["fetchPositions"] is True
        assert capabilities["fetchOHLCV"] is True
        assert capabilities["fetchTicker"] is True

    @pytest.mark.asyncio
    async def test_disconnect(self, ccxt_adapter):
        """Test disconnect."""
        ccxt_adapter._connected = True
        ccxt_adapter.exchange.close = AsyncMock()

        # Disconnect
        await ccxt_adapter.disconnect()

        # Verify
        assert not ccxt_adapter.is_connected()
        ccxt_adapter.exchange.close.assert_called_once()


# ====================================================================================
# WebSocket Integration Tests (AC 3, 4, 5)
# ====================================================================================


class TestCCXTWebSocketIntegration:
    """Test WebSocket integration for CCXT adapter (AC 3, 4, 5)."""

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_subscription_multiple_exchanges(self, ccxt_adapter, test_asset):
        """Test WebSocket subscription across multiple exchanges via CCXT (AC 3)."""
        ccxt_adapter._connected = True

        # Mock WebSocket adapter
        mock_ws = AsyncMock()
        ccxt_adapter._ws_adapter = mock_ws

        # Subscribe to market data
        await ccxt_adapter.subscribe_market_data([test_asset])

        # Verify WebSocket subscribe was called
        mock_ws.subscribe.assert_called_once_with(symbols=["BTC/USDT"], channels=["trades"])

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_bar_buffer_aggregation(self, ccxt_adapter):
        """Test BarBuffer aggregation from CCXT Pro WebSocket (AC 5)."""
        from datetime import datetime

        from rustybt.live.streaming.models import TickData, TickSide

        # Setup connected adapter with bar buffer
        ccxt_adapter._connected = True
        bar_buffer_mock = MagicMock()
        ccxt_adapter._bar_buffer = bar_buffer_mock

        # Create a tick
        tick = TickData(
            symbol="BTC/USDT",
            timestamp=datetime.now(UTC),
            price=Decimal("50000.50"),
            volume=Decimal("0.1"),
            side=TickSide.BUY,
        )

        # Call the tick handler (simulates WebSocket callback)
        ccxt_adapter._handle_tick(tick)

        # Verify tick was added to bar buffer
        bar_buffer_mock.add_tick.assert_called_once_with(tick)

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_lifecycle_connect(self, ccxt_adapter):
        """Test WebSocket connects when broker connect() is called (AC 4)."""
        # Mock load_markets and fetch_balance
        ccxt_adapter.exchange.load_markets = AsyncMock(return_value={})
        ccxt_adapter.exchange.fetch_balance = AsyncMock(
            return_value={"USDT": {"free": 10000, "used": 0, "total": 10000}}
        )

        # Connect broker (should initialize and connect WebSocket)
        await ccxt_adapter.connect()

        # Verify WebSocket adapter was initialized
        assert ccxt_adapter._ws_adapter is not None
        assert ccxt_adapter._bar_buffer is not None
        assert ccxt_adapter.is_connected()

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_lifecycle_disconnect(self, ccxt_adapter):
        """Test WebSocket disconnects when broker disconnect() is called (AC 4)."""
        ccxt_adapter._connected = True
        ccxt_adapter.exchange.close = AsyncMock()

        # Mock WebSocket adapter
        mock_ws = AsyncMock()
        ccxt_adapter._ws_adapter = mock_ws

        # Disconnect broker (should disconnect WebSocket)
        await ccxt_adapter.disconnect()

        # Verify WebSocket disconnect was called
        mock_ws.disconnect.assert_called_once()
        assert ccxt_adapter._ws_adapter is None
        assert ccxt_adapter._bar_buffer is None
        assert not ccxt_adapter.is_connected()
