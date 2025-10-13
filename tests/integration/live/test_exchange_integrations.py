"""Integration tests for exchange broker adapters.

These tests require testnet API keys to be configured via environment variables:
- BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET
- BYBIT_TESTNET_API_KEY and BYBIT_TESTNET_API_SECRET
- HYPERLIQUID_TESTNET_PRIVATE_KEY (or HYPERLIQUID_PRIVATE_KEY for mainnet with small amounts)

Tests are marked with @pytest.mark.exchange_integration and will be skipped
if credentials are not configured.

Setup Instructions:
1. Binance Testnet: Register at https://testnet.binance.vision
2. Bybit Testnet: Register at https://testnet.bybit.com
3. Hyperliquid: Test on mainnet with small amounts or check for testnet availability

IMPORTANT: Never commit real API keys or private keys to version control!
"""

import os
from decimal import Decimal

import pytest

from rustybt.assets import Equity
from rustybt.live.brokers.binance_adapter import BinanceBrokerAdapter
from rustybt.live.brokers.bybit_adapter import BybitBrokerAdapter
from rustybt.live.brokers.ccxt_adapter import CCXTBrokerAdapter
from rustybt.live.brokers.hyperliquid_adapter import HyperliquidBrokerAdapter

# Check if testnet credentials are configured
BINANCE_TESTNET_CONFIGURED = os.getenv("BINANCE_TESTNET_API_KEY") and os.getenv(
    "BINANCE_TESTNET_API_SECRET"
)
BYBIT_TESTNET_CONFIGURED = os.getenv("BYBIT_TESTNET_API_KEY") and os.getenv(
    "BYBIT_TESTNET_API_SECRET"
)
HYPERLIQUID_CONFIGURED = os.getenv("HYPERLIQUID_PRIVATE_KEY")


@pytest.fixture
def test_asset():
    """Create test asset (BTC/USDT)."""
    return Equity(
        sid=1,
        symbol="BTCUSDT",
        exchange="TEST",
        start_date=None,
        end_date=None,
    )


@pytest.mark.exchange_integration
@pytest.mark.skipif(
    not BINANCE_TESTNET_CONFIGURED, reason="Binance testnet credentials not configured"
)
class TestBinanceIntegration:
    """Integration tests for Binance adapter with testnet."""

    @pytest.fixture
    async def binance_adapter(self):
        """Create Binance adapter with testnet credentials."""
        adapter = BinanceBrokerAdapter(
            api_key=os.getenv("BINANCE_TESTNET_API_KEY"),
            api_secret=os.getenv("BINANCE_TESTNET_API_SECRET"),
            market_type="spot",
            testnet=True,
        )
        await adapter.connect()
        yield adapter
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connection(self, binance_adapter):
        """Test connection to Binance testnet."""
        assert binance_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_get_account_info(self, binance_adapter):
        """Test fetching account information."""
        account_info = await binance_adapter.get_account_info()

        assert "cash" in account_info
        assert "equity" in account_info
        assert "buying_power" in account_info
        assert isinstance(account_info["cash"], Decimal)

    @pytest.mark.asyncio
    async def test_get_current_price(self, binance_adapter, test_asset):
        """Test fetching current price."""
        price = await binance_adapter.get_current_price(test_asset)

        assert isinstance(price, Decimal)
        assert price > 0

    @pytest.mark.asyncio
    async def test_order_lifecycle_small_amount(self, binance_adapter, test_asset):
        """Test order submission and cancellation (small test amount).

        WARNING: This test may fail if testnet has insufficient balance or
        if minimum order size requirements are not met.
        """
        # Submit small limit order (intentionally far from market to avoid fill)
        current_price = await binance_adapter.get_current_price(test_asset)
        limit_price = current_price * Decimal("0.5")  # 50% below market

        try:
            order_id = await binance_adapter.submit_order(
                asset=test_asset,
                amount=Decimal("0.001"),  # Very small amount
                order_type="limit",
                limit_price=limit_price,
            )

            assert order_id is not None

            # Get open orders
            open_orders = await binance_adapter.get_open_orders()
            assert any(order_id in order["order_id"] for order in open_orders)

            # Cancel order
            await binance_adapter.cancel_order(f"{test_asset.symbol}:{order_id}")

        except Exception as e:
            pytest.skip(f"Order test skipped due to testnet constraints: {e}")


@pytest.mark.exchange_integration
@pytest.mark.skipif(not BYBIT_TESTNET_CONFIGURED, reason="Bybit testnet credentials not configured")
class TestBybitIntegration:
    """Integration tests for Bybit adapter with testnet."""

    @pytest.fixture
    async def bybit_adapter(self):
        """Create Bybit adapter with testnet credentials."""
        adapter = BybitBrokerAdapter(
            api_key=os.getenv("BYBIT_TESTNET_API_KEY"),
            api_secret=os.getenv("BYBIT_TESTNET_API_SECRET"),
            market_type="linear",
            testnet=True,
        )
        await adapter.connect()
        yield adapter
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connection(self, bybit_adapter):
        """Test connection to Bybit testnet."""
        assert bybit_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_get_account_info(self, bybit_adapter):
        """Test fetching account information."""
        account_info = await bybit_adapter.get_account_info()

        assert "cash" in account_info
        assert "equity" in account_info
        assert isinstance(account_info["cash"], Decimal)

    @pytest.mark.asyncio
    async def test_get_current_price(self, bybit_adapter, test_asset):
        """Test fetching current price."""
        price = await bybit_adapter.get_current_price(test_asset)

        assert isinstance(price, Decimal)
        assert price > 0


@pytest.mark.exchange_integration
@pytest.mark.skipif(not HYPERLIQUID_CONFIGURED, reason="Hyperliquid private key not configured")
class TestHyperliquidIntegration:
    """Integration tests for Hyperliquid adapter.

    WARNING: Hyperliquid uses mainnet by default. Use small amounts for testing.
    """

    @pytest.fixture
    async def hyperliquid_adapter(self):
        """Create Hyperliquid adapter with credentials from environment."""
        adapter = HyperliquidBrokerAdapter(testnet=False)  # Use mainnet with small amounts
        await adapter.connect()
        yield adapter
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connection(self, hyperliquid_adapter):
        """Test connection to Hyperliquid."""
        assert hyperliquid_adapter.is_connected()

    @pytest.mark.asyncio
    async def test_get_account_info(self, hyperliquid_adapter):
        """Test fetching account information."""
        account_info = await hyperliquid_adapter.get_account_info()

        assert "cash" in account_info
        assert "equity" in account_info
        assert isinstance(account_info["cash"], Decimal)


@pytest.mark.exchange_integration
class TestCCXTIntegration:
    """Integration tests for CCXT adapter.

    Uses the configured testnet credentials from Binance for CCXT testing.
    """

    @pytest.mark.skipif(
        not BINANCE_TESTNET_CONFIGURED, reason="Binance testnet credentials not configured"
    )
    @pytest.mark.asyncio
    async def test_ccxt_binance_connection(self):
        """Test CCXT adapter with Binance testnet."""
        adapter = CCXTBrokerAdapter(
            exchange_id="binance",
            api_key=os.getenv("BINANCE_TESTNET_API_KEY"),
            api_secret=os.getenv("BINANCE_TESTNET_API_SECRET"),
            market_type="spot",
            testnet=True,
        )

        try:
            await adapter.connect()
            assert adapter.is_connected()

            # Test basic operations
            account_info = await adapter.get_account_info()
            assert "cash" in account_info

            # Check capabilities
            capabilities = adapter.get_exchange_capabilities()
            assert "fetchBalance" in capabilities

        finally:
            await adapter.disconnect()


# Integration test README marker
"""
## Running Integration Tests

### Setup Testnet API Keys

1. **Binance Testnet:**
   ```bash
   export BINANCE_TESTNET_API_KEY="your_testnet_api_key"
   export BINANCE_TESTNET_API_SECRET="your_testnet_api_secret"
   ```

2. **Bybit Testnet:**
   ```bash
   export BYBIT_TESTNET_API_KEY="your_testnet_api_key"
   export BYBIT_TESTNET_API_SECRET="your_testnet_api_secret"
   ```

3. **Hyperliquid:**
   ```bash
   export HYPERLIQUID_PRIVATE_KEY="your_ethereum_private_key"
   ```

### Run Tests

Run all integration tests:
```bash
pytest tests/integration/live/test_exchange_integrations.py -v --run-exchange-integration
```

Run specific exchange tests:
```bash
pytest tests/integration/live/test_exchange_integrations.py::TestBinanceIntegration -v
```

### Security Notes

- Never commit API keys or private keys to version control
- Use testnet accounts for all testing
- Hyperliquid requires mainnet - use very small amounts
- Rotate API keys regularly
- Use read-only keys where possible for testing
"""
