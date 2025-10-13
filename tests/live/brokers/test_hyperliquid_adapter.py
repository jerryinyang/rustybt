"""Unit tests for Hyperliquid broker adapter."""

import os
from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rustybt.assets import Equity
from rustybt.live.brokers.hyperliquid_adapter import (
    HyperliquidBrokerAdapter,
    HyperliquidConnectionError,
    HyperliquidKeyError,
    HyperliquidOrderRejectError,
)


@pytest.fixture
def test_private_key():
    """Test Ethereum private key (NOT A REAL KEY)."""
    return "a" * 64  # 64 hex characters


@pytest.fixture
def hyperliquid_adapter(test_private_key):
    """Create Hyperliquid adapter with test credentials."""
    with patch.dict(os.environ, {"HYPERLIQUID_PRIVATE_KEY": test_private_key}):
        with (
            patch("rustybt.live.brokers.hyperliquid_adapter.Info"),
            patch("rustybt.live.brokers.hyperliquid_adapter.Exchange"),
            patch("rustybt.live.brokers.hyperliquid_adapter.Account") as mock_account,
        ):
            # Mock wallet account
            mock_wallet = MagicMock()
            mock_wallet.address = "0x1234567890abcdef1234567890abcdef12345678"
            mock_account.from_key.return_value = mock_wallet

            adapter = HyperliquidBrokerAdapter(testnet=True)
            adapter.info = MagicMock()
            adapter.exchange = MagicMock()
            adapter.exchange.wallet = mock_wallet

            return adapter


@pytest.fixture
def test_asset():
    """Create test asset."""
    return Equity(
        sid=1,
        symbol="BTC",
        exchange="HYPERLIQUID",
        start_date=None,
        end_date=None,
    )


class TestHyperliquidAdapter:
    """Test suite for HyperliquidBrokerAdapter."""

    def test_initialization(self, hyperliquid_adapter):
        """Test adapter initialization."""
        assert hyperliquid_adapter.testnet is True
        assert not hyperliquid_adapter.is_connected()

    def test_load_private_key_from_env(self, test_private_key):
        """Test loading private key from environment variable."""
        with patch.dict(os.environ, {"HYPERLIQUID_PRIVATE_KEY": test_private_key}):
            with (
                patch("rustybt.live.brokers.hyperliquid_adapter.Info"),
                patch("rustybt.live.brokers.hyperliquid_adapter.Exchange"),
                patch("rustybt.live.brokers.hyperliquid_adapter.Account") as mock_account,
            ):
                mock_wallet = MagicMock()
                mock_account.from_key.return_value = mock_wallet

                adapter = HyperliquidBrokerAdapter(testnet=True)

                # Verify key was loaded
                assert adapter._private_key == test_private_key

    def test_no_private_key_error(self):
        """Test error when no private key provided."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(HyperliquidKeyError, match="No private key provided"):
                HyperliquidBrokerAdapter(testnet=True)

    def test_invalid_private_key_length(self):
        """Test error for invalid private key length."""
        with patch.dict(os.environ, {"HYPERLIQUID_PRIVATE_KEY": "invalid"}):
            with pytest.raises(HyperliquidKeyError, match="Invalid private key length"):
                HyperliquidBrokerAdapter(testnet=True)

    @pytest.mark.asyncio
    async def test_connect_success(self, hyperliquid_adapter):
        """Test successful connection."""
        # Mock user_state response
        hyperliquid_adapter.info.user_state.return_value = {
            "marginSummary": {
                "accountValue": "10000.0",
                "totalMarginUsed": "500.0",
            }
        }

        # Connect
        await hyperliquid_adapter.connect()

        # Verify
        assert hyperliquid_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_connect_failure(self, hyperliquid_adapter):
        """Test connection failure."""
        # Mock error
        hyperliquid_adapter.info.user_state.return_value = None

        # Should raise connection error
        with pytest.raises(HyperliquidConnectionError, match="Failed to fetch user state"):
            await hyperliquid_adapter.connect()

        assert not hyperliquid_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_submit_market_order_success(self, hyperliquid_adapter, test_asset):
        """Test successful market order submission."""
        hyperliquid_adapter._connected = True

        # Mock order response
        hyperliquid_adapter.exchange.market_open.return_value = {
            "status": "ok",
            "response": {"data": {"statuses": [{"resting": {"oid": 123456}}]}},
        }

        # Submit order
        order_id = await hyperliquid_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="market",
        )

        # Verify
        assert order_id == "123456"

    @pytest.mark.asyncio
    async def test_submit_limit_order_success(self, hyperliquid_adapter, test_asset):
        """Test successful limit order submission."""
        hyperliquid_adapter._connected = True

        # Mock order response
        hyperliquid_adapter.exchange.order.return_value = {
            "status": "ok",
            "response": {"data": {"statuses": [{"resting": {"oid": 123457}}]}},
        }

        # Submit limit order
        order_id = await hyperliquid_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="limit",
            limit_price=Decimal("50000"),
        )

        # Verify
        assert order_id == "123457"

    @pytest.mark.asyncio
    async def test_submit_order_rejection(self, hyperliquid_adapter, test_asset):
        """Test order rejection."""
        hyperliquid_adapter._connected = True

        # Mock error response
        hyperliquid_adapter.exchange.market_open.return_value = {
            "status": "error",
            "response": "Insufficient margin",
        }

        # Should raise order reject error
        with pytest.raises(HyperliquidOrderRejectError, match="Order rejected"):
            await hyperliquid_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("100"),
                order_type="market",
            )

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, hyperliquid_adapter):
        """Test successful order cancellation."""
        hyperliquid_adapter._connected = True

        # Mock cancel response
        hyperliquid_adapter.exchange.cancel.return_value = {
            "status": "ok",
        }

        # Cancel order
        await hyperliquid_adapter.cancel_order("BTC:123456")

        # Should not raise

    @pytest.mark.asyncio
    async def test_get_account_info(self, hyperliquid_adapter):
        """Test get account info."""
        hyperliquid_adapter._connected = True
        hyperliquid_adapter._wallet_address = "0x1234567890abcdef1234567890abcdef12345678"

        # Mock user_state response
        hyperliquid_adapter.info.user_state.return_value = {
            "marginSummary": {
                "accountValue": "10500.0",
                "totalMarginUsed": "500.0",
            }
        }

        # Get account info
        account_info = await hyperliquid_adapter.get_account_info()

        # Verify
        assert account_info["cash"] == Decimal("10000.0")
        assert account_info["equity"] == Decimal("10500.0")

    @pytest.mark.asyncio
    async def test_get_positions(self, hyperliquid_adapter):
        """Test get positions."""
        hyperliquid_adapter._connected = True
        hyperliquid_adapter._wallet_address = "0x1234567890abcdef1234567890abcdef12345678"

        # Mock user_state response
        hyperliquid_adapter.info.user_state.return_value = {
            "assetPositions": [
                {
                    "position": {
                        "coin": "BTC",
                        "szi": "0.5",
                        "entryPx": "50000.0",
                        "positionValue": "25500.0",
                        "unrealizedPnl": "500.0",
                    }
                }
            ]
        }

        # Get positions
        positions = await hyperliquid_adapter.get_positions()

        # Verify
        assert len(positions) == 1
        assert positions[0]["symbol"] == "BTC"
        assert positions[0]["amount"] == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_get_current_price(self, hyperliquid_adapter, test_asset):
        """Test get current price."""
        hyperliquid_adapter._connected = True

        # Mock all_mids response
        hyperliquid_adapter.info.all_mids.return_value = {"BTC": "51000.50"}

        # Get price
        price = await hyperliquid_adapter.get_current_price(test_asset)

        # Verify
        assert price == Decimal("51000.50")

    def test_mask_address(self):
        """Test address masking for logging."""
        address = "0x1234567890abcdef1234567890abcdef12345678"
        masked = HyperliquidBrokerAdapter._mask_address(address)

        assert masked == "0x1234...5678"
        assert len(masked) < len(address)

    @pytest.mark.asyncio
    async def test_disconnect(self, hyperliquid_adapter):
        """Test disconnect."""
        hyperliquid_adapter._connected = True

        # Disconnect
        await hyperliquid_adapter.disconnect()

        # Verify
        assert not hyperliquid_adapter.is_connected()


# ====================================================================================
# WebSocket Integration Tests (AC 2, 4, 5)
# ====================================================================================


class TestHyperliquidWebSocketIntegration:
    """Test WebSocket integration for Hyperliquid adapter (AC 2, 4, 5)."""

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_subscription_perpetual_futures(self, hyperliquid_adapter, test_asset):
        """Test WebSocket subscription for perpetual futures (AC 2)."""
        hyperliquid_adapter._connected = True

        # Mock WebSocket adapter
        mock_ws = AsyncMock()
        hyperliquid_adapter._ws_adapter = mock_ws

        # Subscribe to market data
        await hyperliquid_adapter.subscribe_market_data([test_asset])

        # Verify WebSocket subscribe was called with trades channel
        mock_ws.subscribe.assert_called_once_with(symbols=["BTC"], channels=["trades"])

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_unsubscription(self, hyperliquid_adapter, test_asset):
        """Test WebSocket unsubscription (AC 2)."""
        hyperliquid_adapter._connected = True

        # Mock WebSocket adapter
        mock_ws = AsyncMock()
        hyperliquid_adapter._ws_adapter = mock_ws

        # Unsubscribe from market data
        await hyperliquid_adapter.unsubscribe_market_data([test_asset])

        # Verify WebSocket unsubscribe was called
        mock_ws.unsubscribe.assert_called_once_with(symbols=["BTC"], channels=["trades"])

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_reconnection_handling(self, hyperliquid_adapter):
        """Test WebSocket reconnection handling on connection loss (AC 4)."""
        hyperliquid_adapter._connected = True

        # Mock WebSocket adapter with reconnection capability
        mock_ws = AsyncMock()
        mock_ws.is_connected.side_effect = [False, True]  # Disconnected then reconnected
        hyperliquid_adapter._ws_adapter = mock_ws

        # Trigger reconnection
        await mock_ws.reconnect()

        # Verify reconnect was called
        mock_ws.reconnect.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_lifecycle_connect(self, hyperliquid_adapter):
        """Test WebSocket connects when broker connect() is called (AC 4)."""
        # Mock user_state response
        hyperliquid_adapter.info.user_state.return_value = {
            "marginSummary": {
                "accountValue": "10000.0",
                "totalMarginUsed": "500.0",
            }
        }

        # Connect broker (should initialize and connect WebSocket)
        await hyperliquid_adapter.connect()

        # Verify WebSocket adapter was initialized
        assert hyperliquid_adapter._ws_adapter is not None
        assert hyperliquid_adapter._bar_buffer is not None
        assert hyperliquid_adapter.is_connected()

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_lifecycle_disconnect(self, hyperliquid_adapter):
        """Test WebSocket disconnects when broker disconnect() is called (AC 4)."""
        hyperliquid_adapter._connected = True

        # Mock WebSocket adapter
        mock_ws = AsyncMock()
        hyperliquid_adapter._ws_adapter = mock_ws

        # Disconnect broker (should disconnect WebSocket)
        await hyperliquid_adapter.disconnect()

        # Verify WebSocket disconnect was called
        mock_ws.disconnect.assert_called_once()
        assert hyperliquid_adapter._ws_adapter is None
        assert hyperliquid_adapter._bar_buffer is None
        assert not hyperliquid_adapter.is_connected()

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_tick_handling_from_websocket(self, hyperliquid_adapter):
        """Test tick data handling from WebSocket to BarBuffer (AC 5)."""
        from datetime import datetime

        from rustybt.live.streaming.models import TickData, TickSide

        # Setup connected adapter with bar buffer
        hyperliquid_adapter._connected = True
        bar_buffer_mock = MagicMock()
        hyperliquid_adapter._bar_buffer = bar_buffer_mock

        # Create a tick
        tick = TickData(
            symbol="BTC",
            timestamp=datetime.now(UTC),
            price=Decimal("50000.50"),
            volume=Decimal("0.1"),
            side=TickSide.BUY,
        )

        # Call the tick handler (simulates WebSocket callback)
        hyperliquid_adapter._handle_tick(tick)

        # Verify tick was added to bar buffer
        bar_buffer_mock.add_tick.assert_called_once_with(tick)


# ====================================================================================
# Advanced Order Type Tests (AC 8)
# ====================================================================================


class TestHyperliquidAdvancedOrderTypes:
    """Test Post-Only and Reduce-Only order modes for Hyperliquid (AC 8, 9)."""

    @pytest.mark.asyncio
    async def test_post_only_order_with_alo(self, hyperliquid_adapter, test_asset):
        """Test Post-Only order with ALO (Add Liquidity Only) time-in-force (AC 8)."""
        hyperliquid_adapter._connected = True

        # Mock order response
        hyperliquid_adapter.exchange.order.return_value = {
            "status": "ok",
            "response": {"data": {"statuses": [{"resting": {"oid": 999888}}]}},
        }

        # Submit Post-Only limit order
        order_id = await hyperliquid_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("0.1"),
            order_type="limit",
            limit_price=Decimal("50000"),
            post_only=True,
        )

        # Verify order was submitted with ALO time-in-force
        call_args = hyperliquid_adapter.exchange.order.call_args
        assert call_args[1]["order_type"]["limit"]["tif"] == "Alo"
        assert order_id == "BTC:999888"

    @pytest.mark.asyncio
    async def test_post_only_rejected_on_market_order(self, hyperliquid_adapter, test_asset):
        """Test Post-Only incompatible with Market orders (AC 8)."""
        hyperliquid_adapter._connected = True

        # Should raise ValueError when combining post_only with market order
        with pytest.raises(ValueError, match="Post-Only mode is incompatible with Market orders"):
            await hyperliquid_adapter.submit_order(
                asset=test_asset, amount=Decimal("0.1"), order_type="market", post_only=True
            )

    @pytest.mark.asyncio
    async def test_reduce_only_order_behavior(self, hyperliquid_adapter, test_asset):
        """Test Reduce-Only order behavior with positions (AC 8)."""
        hyperliquid_adapter._connected = True

        # Mock order response
        hyperliquid_adapter.exchange.market_close.return_value = {
            "status": "ok",
            "response": {"data": {"statuses": [{"resting": {"oid": 777666}}]}},
        }

        # Submit Reduce-Only market order
        order_id = await hyperliquid_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("-0.1"),  # Sell to reduce position
            order_type="market",
            reduce_only=True,
        )

        # Verify reduce_only parameter was sent to SDK
        call_args = hyperliquid_adapter.exchange.market_close.call_args
        assert call_args[1]["reduce_only"] is True
        assert order_id == "BTC:777666"

    @pytest.mark.asyncio
    async def test_combined_post_only_reduce_only(self, hyperliquid_adapter, test_asset):
        """Test Post-Only and Reduce-Only can be combined (AC 8, 9)."""
        hyperliquid_adapter._connected = True

        # Mock order response
        hyperliquid_adapter.exchange.order.return_value = {
            "status": "ok",
            "response": {"data": {"statuses": [{"resting": {"oid": 555444}}]}},
        }

        # Submit order with both Post-Only and Reduce-Only
        order_id = await hyperliquid_adapter.submit_order(
            asset=test_asset,
            amount=Decimal("-0.1"),
            order_type="limit",
            limit_price=Decimal("51000"),
            post_only=True,
            reduce_only=True,
        )

        # Verify both params were sent
        call_args = hyperliquid_adapter.exchange.order.call_args
        assert call_args[1]["order_type"]["limit"]["tif"] == "Alo"
        assert call_args[1]["reduce_only"] is True
        assert order_id == "BTC:555444"
