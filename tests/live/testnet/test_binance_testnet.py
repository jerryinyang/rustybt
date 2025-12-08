"""Binance testnet integration tests (fallback).

This module tests:
- Connection establishment to Binance testnet
- Account info retrieval
- Limit order submission and cancellation
- Market order submission and fill

All tests are skipped if BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET are not set.

Story: 10.2.4 - Testnet Connection & Basic Order Flow
"""

import asyncio
from decimal import Decimal

import pytest

from rustybt.assets import ExchangeInfo, Future
from rustybt.live.brokers.binance_adapter import (
    BinanceBrokerAdapter,
    BinanceConnectionError,
)

from .conftest import (
    BinanceCredentials,
    OrderTestConfig,
    skip_without_binance_creds,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def binance_exchange() -> ExchangeInfo:
    """Create Binance exchange info."""
    return ExchangeInfo("BINANCE", "Binance", "GLOBAL")


@pytest.fixture
def btcusdt_perp(binance_exchange) -> Future:
    """Create BTCUSDT perpetual asset for Binance futures."""
    return Future(
        sid=1,
        exchange_info=binance_exchange,
        symbol="BTCUSDT",
        root_symbol="BTC",
    )


@pytest.fixture
def ethusdt_perp(binance_exchange) -> Future:
    """Create ETHUSDT perpetual asset for Binance futures."""
    return Future(
        sid=2,
        exchange_info=binance_exchange,
        symbol="ETHUSDT",
        root_symbol="ETH",
    )


@pytest.fixture
def binance_futures_adapter(binance_credentials: BinanceCredentials | None):
    """Create Binance futures adapter for testnet (not connected).

    Tests must call connect() themselves.
    """
    if binance_credentials is None:
        pytest.skip("Binance credentials not available")

    adapter = BinanceBrokerAdapter(
        api_key=binance_credentials.api_key,
        api_secret=binance_credentials.api_secret,
        market_type="futures",
        testnet=True,  # Always use testnet for tests
    )

    return adapter


# =============================================================================
# AC1: Connection Tests
# =============================================================================


@skip_without_binance_creds
class TestBinanceConnection:
    """Tests for AC1: Connection to Binance testnet."""

    @pytest.mark.asyncio
    async def test_connection_established(self, binance_futures_adapter):
        """Test that connection to testnet is successfully established."""
        assert not binance_futures_adapter.is_connected()

        await binance_futures_adapter.connect()

        assert binance_futures_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_account_info_retrieved(self, binance_futures_adapter):
        """Test that account information can be retrieved."""
        await binance_futures_adapter.connect()

        account_info = await binance_futures_adapter.get_account_info()

        assert "cash" in account_info
        assert "equity" in account_info
        assert "buying_power" in account_info
        assert isinstance(account_info["cash"], Decimal)

    @pytest.mark.asyncio
    async def test_positions_retrieved(self, binance_futures_adapter):
        """Test that positions can be retrieved."""
        await binance_futures_adapter.connect()

        positions = await binance_futures_adapter.get_positions()

        assert isinstance(positions, list)

    @pytest.mark.asyncio
    async def test_disconnect_clean(self, binance_futures_adapter):
        """Test that disconnect is clean."""
        await binance_futures_adapter.connect()
        assert binance_futures_adapter.is_connected()

        await binance_futures_adapter.disconnect()
        assert not binance_futures_adapter.is_connected()


# =============================================================================
# AC2: Limit Order Tests
# =============================================================================


@skip_without_binance_creds
class TestBinanceLimitOrder:
    """Tests for AC2: Limit order submission and cancellation."""

    @pytest.mark.asyncio
    async def test_limit_order_submission(
        self,
        binance_futures_adapter,
        btcusdt_perp,
        test_order_config: OrderTestConfig,
    ):
        """Test limit order submission at unlikely price."""
        await binance_futures_adapter.connect()

        order_id = await binance_futures_adapter.submit_order(
            asset=btcusdt_perp,
            amount=test_order_config.btc_min_size,
            order_type="limit",
            limit_price=test_order_config.btc_unlikely_buy_price,
        )

        assert order_id is not None
        assert isinstance(order_id, str)

        # Cleanup
        try:
            await binance_futures_adapter.cancel_order(order_id)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_limit_order_in_open_orders(
        self,
        binance_futures_adapter,
        btcusdt_perp,
        test_order_config: OrderTestConfig,
    ):
        """Test that limit order appears in open orders."""
        await binance_futures_adapter.connect()

        order_id = await binance_futures_adapter.submit_order(
            asset=btcusdt_perp,
            amount=test_order_config.btc_min_size,
            order_type="limit",
            limit_price=test_order_config.btc_unlikely_buy_price,
        )

        await asyncio.sleep(0.5)

        try:
            open_orders = await binance_futures_adapter.get_open_orders()
            order_ids = [o["order_id"] for o in open_orders]
            assert order_id in order_ids
        finally:
            try:
                await binance_futures_adapter.cancel_order(order_id)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_limit_order_cancellation(
        self,
        binance_futures_adapter,
        btcusdt_perp,
        test_order_config: OrderTestConfig,
    ):
        """Test limit order cancellation."""
        await binance_futures_adapter.connect()

        order_id = await binance_futures_adapter.submit_order(
            asset=btcusdt_perp,
            amount=test_order_config.btc_min_size,
            order_type="limit",
            limit_price=test_order_config.btc_unlikely_buy_price,
        )

        await asyncio.sleep(0.5)

        # Cancel order
        await binance_futures_adapter.cancel_order(order_id)

        await asyncio.sleep(0.5)

        # Verify removed from open orders
        open_orders = await binance_futures_adapter.get_open_orders()
        order_ids = [o["order_id"] for o in open_orders]
        assert order_id not in order_ids


# =============================================================================
# AC3: Market Order Tests
# =============================================================================


@skip_without_binance_creds
class TestBinanceMarketOrder:
    """Tests for AC3: Market order submission and fill."""

    @pytest.mark.asyncio
    async def test_market_order_submission(
        self,
        binance_futures_adapter,
        btcusdt_perp,
        test_order_config: OrderTestConfig,
    ):
        """Test market order submission."""
        await binance_futures_adapter.connect()

        try:
            order_id = await binance_futures_adapter.submit_order(
                asset=btcusdt_perp,
                amount=test_order_config.btc_min_size,
                order_type="market",
            )

            assert order_id is not None

            await asyncio.sleep(1.0)

        finally:
            # Cleanup: close position
            try:
                await binance_futures_adapter.submit_order(
                    asset=btcusdt_perp,
                    amount=-test_order_config.btc_min_size,
                    order_type="market",
                )
            except Exception:
                pass


# =============================================================================
# Error Handling Tests
# =============================================================================


@skip_without_binance_creds
class TestBinanceErrorHandling:
    """Tests for Binance error handling."""

    @pytest.mark.asyncio
    async def test_operations_before_connect_fail(self, binance_credentials):
        """Test that operations before connect raise appropriate errors."""
        adapter = BinanceBrokerAdapter(
            api_key=binance_credentials.api_key,
            api_secret=binance_credentials.api_secret,
            market_type="futures",
            testnet=True,
        )

        assert not adapter.is_connected()

        with pytest.raises(BinanceConnectionError):
            await adapter.get_account_info()

    @pytest.mark.asyncio
    async def test_invalid_order_parameters(
        self,
        binance_futures_adapter,
        btcusdt_perp,
    ):
        """Test invalid order parameters raise ValueError."""
        await binance_futures_adapter.connect()

        with pytest.raises(ValueError, match="cannot be zero"):
            await binance_futures_adapter.submit_order(
                asset=btcusdt_perp,
                amount=Decimal("0"),
                order_type="market",
            )
