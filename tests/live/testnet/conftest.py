"""Testnet test configuration and fixtures.

This module provides shared fixtures for testnet integration tests:
- Credential loading from environment variables
- Skip decorators for missing credentials
- Broker adapter fixtures for each exchange

Environment Variables (see .env.example for setup instructions):

    Hyperliquid (DEX with Ethereum private key auth):
        HYPERLIQUID_PRIVATE_KEY: Ethereum private key (0x-prefixed, 66 chars)
        HYPERLIQUID_WALLET_ADDRESS: Main wallet address for positions

    Binance Futures Testnet:
        BINANCE_TESTNET_API_KEY: Testnet API key from testnet.binancefuture.com
        BINANCE_TESTNET_SECRET: Testnet API secret

    Bybit Testnet:
        BYBIT_TESTNET_API_KEY: Testnet API key from testnet.bybit.com
        BYBIT_TESTNET_SECRET: Testnet API secret

    Lighter.xyz (planned):
        LIGHTER_API_PRIVATE_KEY: API key private key
        LIGHTER_ETH_PRIVATE_KEY: ETH wallet private key
        LIGHTER_ACCOUNT_INDEX: Account index
        LIGHTER_API_KEY_INDEX: API key index (2-254)
"""

import os
from dataclasses import dataclass
from decimal import Decimal

import pytest

# =============================================================================
# Credential Configuration
# =============================================================================


@dataclass
class HyperliquidCredentials:
    """Hyperliquid testnet credentials.

    Authentication: Hyperliquid uses Ethereum private keys, not API key/secret pairs.
    The private_key can be either:
    - Your main wallet private key (not recommended for bots)
    - An API wallet private key (recommended - can trade but cannot withdraw)

    The wallet_address should always be your MAIN wallet address, even when
    using an API wallet's private key.
    """

    private_key: str
    wallet_address: str | None = None

    @classmethod
    def from_env(cls) -> "HyperliquidCredentials | None":
        """Load credentials from environment variables."""
        private_key = os.environ.get("HYPERLIQUID_PRIVATE_KEY")
        if not private_key:
            return None
        wallet_address = os.environ.get("HYPERLIQUID_WALLET_ADDRESS")
        return cls(private_key=private_key, wallet_address=wallet_address)


@dataclass
class BinanceCredentials:
    """Binance testnet credentials."""

    api_key: str
    api_secret: str

    @classmethod
    def from_env(cls) -> "BinanceCredentials | None":
        """Load credentials from environment variables."""
        api_key = os.environ.get("BINANCE_TESTNET_API_KEY")
        api_secret = os.environ.get("BINANCE_TESTNET_SECRET")
        if not api_key or not api_secret:
            return None
        return cls(api_key=api_key, api_secret=api_secret)


@dataclass
class BybitCredentials:
    """Bybit testnet credentials."""

    api_key: str
    api_secret: str

    @classmethod
    def from_env(cls) -> "BybitCredentials | None":
        """Load credentials from environment variables."""
        api_key = os.environ.get("BYBIT_TESTNET_API_KEY")
        api_secret = os.environ.get("BYBIT_TESTNET_SECRET")
        if not api_key or not api_secret:
            return None
        return cls(api_key=api_key, api_secret=api_secret)


@dataclass
class LighterCredentials:
    """Lighter.xyz testnet credentials.

    Authentication: Lighter uses ETH private keys + API key indices.
    - api_private_key: The API key's private key (generated on Lighter app)
    - eth_private_key: Your ETH wallet private key for signing
    - account_index: Your account index on Lighter
    - api_key_index: API key index (2-254, 0=desktop, 1=mobile reserved)

    Testnet URL: https://testnet.zklighter.elliot.ai
    """

    api_private_key: str
    eth_private_key: str
    account_index: int = 0
    api_key_index: int = 2

    @classmethod
    def from_env(cls) -> "LighterCredentials | None":
        """Load credentials from environment variables."""
        api_private_key = os.environ.get("LIGHTER_API_PRIVATE_KEY")
        eth_private_key = os.environ.get("LIGHTER_ETH_PRIVATE_KEY")
        if not api_private_key or not eth_private_key:
            return None
        account_index = int(os.environ.get("LIGHTER_ACCOUNT_INDEX", "0"))
        api_key_index = int(os.environ.get("LIGHTER_API_KEY_INDEX", "2"))
        return cls(
            api_private_key=api_private_key,
            eth_private_key=eth_private_key,
            account_index=account_index,
            api_key_index=api_key_index,
        )


# =============================================================================
# Skip Decorators
# =============================================================================


def has_hyperliquid_credentials() -> bool:
    """Check if Hyperliquid testnet credentials are available."""
    return HyperliquidCredentials.from_env() is not None


def has_binance_credentials() -> bool:
    """Check if Binance testnet credentials are available."""
    return BinanceCredentials.from_env() is not None


def has_bybit_credentials() -> bool:
    """Check if Bybit testnet credentials are available."""
    return BybitCredentials.from_env() is not None


def has_lighter_credentials() -> bool:
    """Check if Lighter.xyz testnet credentials are available."""
    return LighterCredentials.from_env() is not None


# Skip decorators for missing credentials
skip_without_hyperliquid_creds = pytest.mark.skipif(
    not has_hyperliquid_credentials(),
    reason="Hyperliquid testnet credentials not available. "
    "Set HYPERLIQUID_PRIVATE_KEY environment variable.",
)

skip_without_binance_creds = pytest.mark.skipif(
    not has_binance_credentials(),
    reason="Binance testnet credentials not available. "
    "Set BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET environment variables.",
)

skip_without_bybit_creds = pytest.mark.skipif(
    not has_bybit_credentials(),
    reason="Bybit testnet credentials not available. "
    "Set BYBIT_TESTNET_API_KEY and BYBIT_TESTNET_SECRET environment variables.",
)

skip_without_lighter_creds = pytest.mark.skipif(
    not has_lighter_credentials(),
    reason="Lighter.xyz testnet credentials not available. "
    "Set LIGHTER_API_PRIVATE_KEY and LIGHTER_ETH_PRIVATE_KEY environment variables.",
)


# =============================================================================
# Test Markers
# =============================================================================


# Mark for tests that require any testnet credentials
requires_testnet = pytest.mark.testnet


# =============================================================================
# Credential Fixtures
# =============================================================================


@pytest.fixture
def hyperliquid_credentials() -> HyperliquidCredentials | None:
    """Get Hyperliquid testnet credentials if available."""
    return HyperliquidCredentials.from_env()


@pytest.fixture
def binance_credentials() -> BinanceCredentials | None:
    """Get Binance testnet credentials if available."""
    return BinanceCredentials.from_env()


@pytest.fixture
def bybit_credentials() -> BybitCredentials | None:
    """Get Bybit testnet credentials if available."""
    return BybitCredentials.from_env()


@pytest.fixture
def lighter_credentials() -> LighterCredentials | None:
    """Get Lighter.xyz testnet credentials if available."""
    return LighterCredentials.from_env()


# =============================================================================
# Test Configuration
# =============================================================================


@dataclass
class OrderTestConfig:
    """Configuration for test orders to minimize testnet fund usage."""

    # Minimal order sizes to avoid depleting testnet funds
    btc_min_size: Decimal = Decimal("0.001")
    eth_min_size: Decimal = Decimal("0.01")

    # Unlikely limit prices that won't fill (for order cancellation tests)
    btc_unlikely_buy_price: Decimal = Decimal("10000")  # Far below market
    btc_unlikely_sell_price: Decimal = Decimal("500000")  # Far above market
    eth_unlikely_buy_price: Decimal = Decimal("500")  # Far below market
    eth_unlikely_sell_price: Decimal = Decimal("50000")  # Far above market


@pytest.fixture
def test_order_config() -> OrderTestConfig:
    """Get test order configuration."""
    return OrderTestConfig()


# =============================================================================
# Common Test Symbols
# =============================================================================


@pytest.fixture
def btc_symbol() -> str:
    """Bitcoin trading symbol."""
    return "BTC"


@pytest.fixture
def eth_symbol() -> str:
    """Ethereum trading symbol."""
    return "ETH"


@pytest.fixture
def btcusdt_symbol() -> str:
    """Bitcoin-USDT trading pair for Binance/Bybit."""
    return "BTCUSDT"


@pytest.fixture
def ethusdt_symbol() -> str:
    """Ethereum-USDT trading pair for Binance/Bybit."""
    return "ETHUSDT"
