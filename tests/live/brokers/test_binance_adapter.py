"""Unit tests for Binance broker adapter."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from rustybt.assets import Equity
from rustybt.live.brokers.binance_adapter import (
    BinanceBrokerAdapter,
    BinanceConnectionError,
    BinanceOrderRejectError,
    BinanceRateLimitError,
)


@pytest.fixture
def binance_adapter():
    """Create Binance adapter with test credentials."""
    adapter = BinanceBrokerAdapter(
        api_key="test_api_key",
        api_secret="test_api_secret",
        market_type="spot",
        testnet=True,
    )
    return adapter


@pytest.fixture
def mock_session():
    """Create mock aiohttp session."""
    session = AsyncMock()
    return session


@pytest.fixture
def test_asset():
    """Create test asset."""
    return Equity(
        sid=1,
        symbol="BTCUSDT",
        exchange="BINANCE",
        start_date=None,
        end_date=None,
    )


class TestBinanceAdapter:
    """Test suite for BinanceBrokerAdapter."""

    def test_initialization(self, binance_adapter):
        """Test adapter initialization."""
        assert binance_adapter.api_key == "test_api_key"
        assert binance_adapter.market_type == "spot"
        assert binance_adapter.testnet is True
        assert not binance_adapter.is_connected()

    def test_invalid_market_type(self):
        """Test initialization with invalid market type."""
        with pytest.raises(ValueError, match="Invalid market_type"):
            BinanceBrokerAdapter(
                api_key="test",
                api_secret="test",
                market_type="invalid",
            )

    @pytest.mark.asyncio
    async def test_connect_success(self, binance_adapter):
        """Test successful connection."""
        # Mock HTTP session and WebSocket
        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_session = AsyncMock()
            mock_client_session.return_value = mock_session

            # Mock ping response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={})
            mock_session.request.return_value.__aenter__.return_value = mock_response

            # Mock WebSocket connect
            binance_adapter.ws_adapter.connect = AsyncMock()

            # Connect
            await binance_adapter.connect()

            # Verify
            assert binance_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_connect_failure(self, binance_adapter):
        """Test connection failure."""
        with patch("aiohttp.ClientSession") as mock_client_session:
            mock_session = AsyncMock()
            mock_client_session.return_value = mock_session

            # Mock connection error
            mock_session.request.side_effect = Exception("Connection failed")

            # Should raise connection error
            with pytest.raises(BinanceConnectionError, match="Failed to connect"):
                await binance_adapter.connect()

            assert not binance_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_disconnect(self, binance_adapter):
        """Test disconnect."""
        # Setup connected adapter
        binance_adapter._connected = True
        binance_adapter._session = AsyncMock()
        binance_adapter.ws_adapter.disconnect = AsyncMock()

        # Disconnect
        await binance_adapter.disconnect()

        # Verify
        assert not binance_adapter.is_connected()
        binance_adapter._session.close.assert_called_once()
        binance_adapter.ws_adapter.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_market_order_success(self, binance_adapter, test_asset):
        """Test successful market order submission."""
        binance_adapter._connected = True
        binance_adapter._session = AsyncMock()

        # Mock order response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "orderId": 123456,
                "symbol": "BTCUSDT",
                "status": "FILLED",
            }
        )
        binance_adapter._session.request.return_value.__aenter__.return_value = mock_response

        # Submit order
        order_id = await binance_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="market",
        )

        # Verify
        assert order_id == "123456"

    @pytest.mark.asyncio
    async def test_submit_limit_order_success(self, binance_adapter, test_asset):
        """Test successful limit order submission."""
        binance_adapter._connected = True
        binance_adapter._session = AsyncMock()

        # Mock order response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "orderId": 123457,
                "symbol": "BTCUSDT",
                "status": "NEW",
            }
        )
        binance_adapter._session.request.return_value.__aenter__.return_value = mock_response

        # Submit limit order
        order_id = await binance_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="limit",
            limit_price=Decimal("50000"),
        )

        # Verify
        assert order_id == "123457"

    @pytest.mark.asyncio
    async def test_submit_order_insufficient_balance(self, binance_adapter, test_asset):
        """Test order rejection due to insufficient balance."""
        binance_adapter._connected = True
        binance_adapter._session = AsyncMock()

        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json = AsyncMock(
            return_value={
                "code": -2010,
                "msg": "Account has insufficient balance",
            }
        )
        binance_adapter._session.request.return_value.__aenter__.return_value = mock_response

        # Should raise order reject error
        with pytest.raises(BinanceOrderRejectError, match="Insufficient balance"):
            await binance_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("100"),
                order_type="market",
            )

    @pytest.mark.asyncio
    async def test_submit_order_rate_limit(self, binance_adapter, test_asset):
        """Test rate limit error."""
        binance_adapter._connected = True
        binance_adapter._session = AsyncMock()

        # Mock rate limit response
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.json = AsyncMock(
            return_value={
                "code": -1003,
                "msg": "Rate limit exceeded",
            }
        )
        binance_adapter._session.request.return_value.__aenter__.return_value = mock_response

        # Should raise rate limit error
        with pytest.raises(BinanceRateLimitError, match="Rate limit exceeded"):
            await binance_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("0.1"),
                order_type="market",
            )

    @pytest.mark.asyncio
    async def test_submit_order_zero_amount(self, binance_adapter, test_asset):
        """Test order with zero amount."""
        binance_adapter._connected = True

        # Should raise ValueError
        with pytest.raises(ValueError, match="Order amount cannot be zero"):
            await binance_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("0"),
                order_type="market",
            )

    @pytest.mark.asyncio
    async def test_submit_order_limit_without_price(self, binance_adapter, test_asset):
        """Test limit order without price."""
        binance_adapter._connected = True

        # Should raise ValueError
        with pytest.raises(ValueError, match="limit_price required"):
            await binance_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("0.1"),
                order_type="limit",
            )

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, binance_adapter):
        """Test successful order cancellation."""
        binance_adapter._connected = True
        binance_adapter._session = AsyncMock()

        # Mock cancel response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "symbol": "BTCUSDT",
                "orderId": 123456,
                "status": "CANCELED",
            }
        )
        binance_adapter._session.request.return_value.__aenter__.return_value = mock_response

        # Cancel order
        await binance_adapter.cancel_order("BTCUSDT:123456")

        # Should not raise

    @pytest.mark.asyncio
    async def test_cancel_order_invalid_format(self, binance_adapter):
        """Test cancel with invalid order ID format."""
        binance_adapter._connected = True

        # Should raise ValueError
        with pytest.raises(ValueError, match="Order ID must be in format"):
            await binance_adapter.cancel_order("invalid_format")

    @pytest.mark.asyncio
    async def test_get_account_info_spot(self, binance_adapter):
        """Test get account info for spot account."""
        binance_adapter._connected = True
        binance_adapter._session = AsyncMock()

        # Mock account response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "balances": [
                    {"asset": "USDT", "free": "10000.00", "locked": "0.00"},
                    {"asset": "BTC", "free": "0.5", "locked": "0.0"},
                ]
            }
        )
        binance_adapter._session.request.return_value.__aenter__.return_value = mock_response

        # Get account info
        account_info = await binance_adapter.get_account_info()

        # Verify
        assert account_info["cash"] == Decimal("10000.00")
        assert account_info["equity"] == Decimal("10000.00")

    @pytest.mark.asyncio
    async def test_get_positions_futures(self):
        """Test get positions for futures account."""
        adapter = BinanceBrokerAdapter(
            api_key="test",
            api_secret="test",
            market_type="futures",
            testnet=True,
        )
        adapter._connected = True
        adapter._session = AsyncMock()

        # Mock positions response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value=[
                {
                    "symbol": "BTCUSDT",
                    "positionAmt": "0.5",
                    "entryPrice": "50000.0",
                    "markPrice": "51000.0",
                    "unRealizedProfit": "500.0",
                }
            ]
        )
        adapter._session.request.return_value.__aenter__.return_value = mock_response

        # Get positions
        positions = await adapter.get_positions()

        # Verify
        assert len(positions) == 1
        assert positions[0]["symbol"] == "BTCUSDT"
        assert positions[0]["amount"] == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_get_positions_spot(self, binance_adapter):
        """Test get positions for spot account (returns empty)."""
        binance_adapter._connected = True

        # Spot has no positions
        positions = await binance_adapter.get_positions()

        assert positions == []

    @pytest.mark.asyncio
    async def test_get_current_price(self, binance_adapter, test_asset):
        """Test get current price."""
        binance_adapter._connected = True
        binance_adapter._session = AsyncMock()

        # Mock price response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "symbol": "BTCUSDT",
                "price": "51000.50",
            }
        )
        binance_adapter._session.request.return_value.__aenter__.return_value = mock_response

        # Get price
        price = await binance_adapter.get_current_price(test_asset)

        # Verify
        assert price == Decimal("51000.50")

    @pytest.mark.asyncio
    async def test_subscribe_market_data(self, binance_adapter, test_asset):
        """Test subscribe to market data."""
        binance_adapter._connected = True
        binance_adapter.ws_adapter.subscribe = AsyncMock()

        # Subscribe
        await binance_adapter.subscribe_market_data([test_asset])

        # Verify
        binance_adapter.ws_adapter.subscribe.assert_called_once_with(["BTCUSDT"], ["kline_1m"])

    @pytest.mark.asyncio
    async def test_order_type_mapping(self, binance_adapter):
        """Test order type mapping."""
        assert binance_adapter._map_order_type("market") == "MARKET"
        assert binance_adapter._map_order_type("limit") == "LIMIT"
        assert binance_adapter._map_order_type("stop") == "STOP_LOSS"
        assert binance_adapter._map_order_type("stop-limit") == "STOP_LOSS_LIMIT"

        with pytest.raises(ValueError, match="Unsupported order type"):
            binance_adapter._map_order_type("invalid")

    @pytest.mark.asyncio
    async def test_rate_limiting(self, binance_adapter):
        """Test request rate limiting."""
        # Fill rate limit
        binance_adapter._request_timestamps = [asyncio.get_event_loop().time()] * 1199

        # Next request should not be delayed
        await binance_adapter._check_request_rate_limit()

        # Verify timestamp added
        assert len(binance_adapter._request_timestamps) == 1200

    def test_not_connected_error(self, binance_adapter, test_asset):
        """Test operations when not connected."""
        with pytest.raises(BinanceConnectionError, match="Not connected"):
            asyncio.run(binance_adapter.submit_order(test_asset, Decimal("1"), "market"))

        with pytest.raises(BinanceConnectionError, match="Not connected"):
            asyncio.run(binance_adapter.get_account_info())

        with pytest.raises(BinanceConnectionError, match="Not connected"):
            asyncio.run(binance_adapter.get_current_price(test_asset))


# ====================================================================================
# Advanced Order Type Tests (AC 6)
# ====================================================================================


class TestBinanceAdvancedOrderTypes:
    """Test OCO and Iceberg order types for Binance (AC 6, 9)."""

    @pytest.mark.asyncio
    async def test_oco_order_submission(self, binance_adapter, test_asset):
        """Test OCO (One-Cancels-Other) order submission returns two order IDs (AC 6)."""
        binance_adapter._connected = True

        # Mock OCO order response (Binance returns both order IDs)
        binance_adapter.client.new_oco_order = AsyncMock(
            return_value={
                "orderListId": 123,
                "orders": [
                    {"orderId": 456789, "type": "STOP_LOSS_LIMIT"},
                    {"orderId": 456790, "type": "LIMIT_MAKER"},
                ],
            }
        )

        # Submit OCO order
        order_id = await binance_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="limit",
            limit_price=Decimal("52000"),  # Take profit
            oco_params={
                "stop_price": Decimal("48000"),  # Stop loss trigger
                "stop_limit_price": Decimal("47500"),  # Stop loss limit
            },
        )

        # Verify OCO order was submitted
        binance_adapter.client.new_oco_order.assert_called_once()
        call_args = binance_adapter.client.new_oco_order.call_args[1]
        assert call_args["symbol"] == "BTCUSDT"
        assert call_args["side"] == "SELL"  # Sell to take profit/stop loss
        assert float(call_args["price"]) == 52000.0
        assert float(call_args["stopPrice"]) == 48000.0
        assert float(call_args["stopLimitPrice"]) == 47500.0

        # Order ID should contain list ID
        assert "123" in order_id

    @pytest.mark.asyncio
    async def test_iceberg_order_submission(self, binance_adapter, test_asset):
        """Test Iceberg order with visible quantity < total quantity (AC 6)."""
        binance_adapter._connected = True

        # Mock Iceberg order response
        binance_adapter.client.new_order = AsyncMock(
            return_value={
                "orderId": 789123,
                "type": "LIMIT",
                "icebergQty": "0.01",  # Visible quantity
            }
        )

        # Submit Iceberg order
        order_id = await binance_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),  # Total quantity
            order_type="limit",
            limit_price=Decimal("50000"),
            iceberg_qty=Decimal("0.01"),  # Show only 0.01 at a time
        )

        # Verify Iceberg order was submitted with correct params
        binance_adapter.client.new_order.assert_called_once()
        call_args = binance_adapter.client.new_order.call_args[1]
        assert call_args["symbol"] == "BTCUSDT"
        assert float(call_args["icebergQty"]) == 0.01
        assert float(call_args["quantity"]) == 0.1  # Total quantity

        # Verify order ID returned
        assert order_id == "BTCUSDT:789123"
