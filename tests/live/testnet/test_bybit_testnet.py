"""Bybit testnet integration tests (fallback).

This module tests:
- Connection establishment to Bybit testnet
- Account info retrieval
- Limit order submission and cancellation
- Market order submission and fill

All tests are skipped if BYBIT_TESTNET_API_KEY and BYBIT_TESTNET_SECRET are not set.

Story: 10.2.4 - Testnet Connection & Basic Order Flow
"""

import asyncio
from decimal import Decimal

import pytest

from rustybt.assets import ExchangeInfo, Future
from rustybt.live.brokers.bybit_adapter import (
    BybitBrokerAdapter,
    BybitConnectionError,
)

from .conftest import (
    BybitCredentials,
    OrderTestConfig,
    skip_without_bybit_creds,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def bybit_exchange() -> ExchangeInfo:
    """Create Bybit exchange info."""
    return ExchangeInfo("BYBIT", "Bybit", "GLOBAL")


@pytest.fixture
def btcusdt_perp(bybit_exchange) -> Future:
    """Create BTCUSDT linear perpetual asset for Bybit."""
    return Future(
        sid=1,
        exchange_info=bybit_exchange,
        symbol="BTCUSDT",
        root_symbol="BTC",
    )


@pytest.fixture
def ethusdt_perp(bybit_exchange) -> Future:
    """Create ETHUSDT linear perpetual asset for Bybit."""
    return Future(
        sid=2,
        exchange_info=bybit_exchange,
        symbol="ETHUSDT",
        root_symbol="ETH",
    )


@pytest.fixture
def bybit_adapter(bybit_credentials: BybitCredentials | None):
    """Create Bybit adapter for testnet (not connected).

    Tests must call connect() themselves.
    """
    if bybit_credentials is None:
        pytest.skip("Bybit credentials not available")

    adapter = BybitBrokerAdapter(
        api_key=bybit_credentials.api_key,
        api_secret=bybit_credentials.api_secret,
        market_type="linear",  # Linear perpetuals
        testnet=True,  # Always use testnet for tests
    )

    return adapter


# =============================================================================
# AC1: Connection Tests
# =============================================================================


@skip_without_bybit_creds
class TestBybitConnection:
    """Tests for AC1: Connection to Bybit testnet."""

    @pytest.mark.asyncio
    async def test_connection_established(self, bybit_adapter):
        """Test that connection to testnet is successfully established."""
        assert not bybit_adapter.is_connected()

        await bybit_adapter.connect()

        assert bybit_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_account_info_retrieved(self, bybit_adapter):
        """Test that account information can be retrieved."""
        await bybit_adapter.connect()

        account_info = await bybit_adapter.get_account_info()

        assert "cash" in account_info
        assert "equity" in account_info
        assert "buying_power" in account_info
        assert isinstance(account_info["cash"], Decimal)

    @pytest.mark.asyncio
    async def test_positions_retrieved(self, bybit_adapter):
        """Test that positions can be retrieved."""
        await bybit_adapter.connect()

        positions = await bybit_adapter.get_positions()

        assert isinstance(positions, list)

    @pytest.mark.asyncio
    async def test_disconnect_clean(self, bybit_adapter):
        """Test that disconnect is clean."""
        await bybit_adapter.connect()
        assert bybit_adapter.is_connected()

        await bybit_adapter.disconnect()
        assert not bybit_adapter.is_connected()


# =============================================================================
# AC2: Limit Order Tests
# =============================================================================


@skip_without_bybit_creds
class TestBybitLimitOrder:
    """Tests for AC2: Limit order submission and cancellation."""

    @pytest.mark.asyncio
    async def test_limit_order_submission(
        self,
        bybit_adapter,
        btcusdt_perp,
        test_order_config: OrderTestConfig,
    ):
        """Test limit order submission at unlikely price."""
        await bybit_adapter.connect()

        order_id = await bybit_adapter.submit_order(
            asset=btcusdt_perp,
            amount=test_order_config.btc_min_size,
            order_type="limit",
            limit_price=test_order_config.btc_unlikely_buy_price,
        )

        assert order_id is not None
        assert isinstance(order_id, str)

        # Cleanup
        try:
            await bybit_adapter.cancel_order(order_id)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_limit_order_in_open_orders(
        self,
        bybit_adapter,
        btcusdt_perp,
        test_order_config: OrderTestConfig,
    ):
        """Test that limit order appears in open orders."""
        await bybit_adapter.connect()

        order_id = await bybit_adapter.submit_order(
            asset=btcusdt_perp,
            amount=test_order_config.btc_min_size,
            order_type="limit",
            limit_price=test_order_config.btc_unlikely_buy_price,
        )

        await asyncio.sleep(0.5)

        try:
            open_orders = await bybit_adapter.get_open_orders()
            order_ids = [o["order_id"] for o in open_orders]
            assert order_id in order_ids
        finally:
            try:
                await bybit_adapter.cancel_order(order_id)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_limit_order_cancellation(
        self,
        bybit_adapter,
        btcusdt_perp,
        test_order_config: OrderTestConfig,
    ):
        """Test limit order cancellation."""
        await bybit_adapter.connect()

        order_id = await bybit_adapter.submit_order(
            asset=btcusdt_perp,
            amount=test_order_config.btc_min_size,
            order_type="limit",
            limit_price=test_order_config.btc_unlikely_buy_price,
        )

        await asyncio.sleep(0.5)

        # Cancel order
        await bybit_adapter.cancel_order(order_id)

        await asyncio.sleep(0.5)

        # Verify removed from open orders
        open_orders = await bybit_adapter.get_open_orders()
        order_ids = [o["order_id"] for o in open_orders]
        assert order_id not in order_ids


# =============================================================================
# AC3: Market Order Tests
# =============================================================================


@skip_without_bybit_creds
class TestBybitMarketOrder:
    """Tests for AC3: Market order submission and fill."""

    @pytest.mark.asyncio
    async def test_market_order_submission(
        self,
        bybit_adapter,
        btcusdt_perp,
        test_order_config: OrderTestConfig,
    ):
        """Test market order submission."""
        await bybit_adapter.connect()

        try:
            order_id = await bybit_adapter.submit_order(
                asset=btcusdt_perp,
                amount=test_order_config.btc_min_size,
                order_type="market",
            )

            assert order_id is not None

            await asyncio.sleep(1.0)

        finally:
            # Cleanup: close position
            try:
                await bybit_adapter.submit_order(
                    asset=btcusdt_perp,
                    amount=-test_order_config.btc_min_size,
                    order_type="market",
                )
            except Exception:
                pass


# =============================================================================
# Error Handling Tests
# =============================================================================


@skip_without_bybit_creds
class TestBybitErrorHandling:
    """Tests for Bybit error handling."""

    @pytest.mark.asyncio
    async def test_operations_before_connect_fail(self, bybit_credentials):
        """Test that operations before connect raise appropriate errors."""
        adapter = BybitBrokerAdapter(
            api_key=bybit_credentials.api_key,
            api_secret=bybit_credentials.api_secret,
            market_type="linear",
            testnet=True,
        )

        assert not adapter.is_connected()

        with pytest.raises(BybitConnectionError):
            await adapter.get_account_info()

    @pytest.mark.asyncio
    async def test_invalid_order_parameters(
        self,
        bybit_adapter,
        btcusdt_perp,
    ):
        """Test invalid order parameters raise ValueError."""
        await bybit_adapter.connect()

        with pytest.raises(ValueError, match="cannot be zero"):
            await bybit_adapter.submit_order(
                asset=btcusdt_perp,
                amount=Decimal("0"),
                order_type="market",
            )
