"""Unit tests for freshness policy factory."""

from unittest.mock import Mock

import pytest

from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.data.sources.freshness import (
    AlwaysStaleFreshnessPolicy,
    HybridFreshnessPolicy,
    MarketCloseFreshnessPolicy,
    NeverStaleFreshnessPolicy,
    TTLFreshnessPolicy,
)
from rustybt.data.sources.freshness_factory import FreshnessPolicyFactory


@pytest.fixture
def mock_yfinance_adapter():
    """Create mock YFinance adapter."""
    adapter = Mock(spec=DataSource)
    adapter.get_metadata.return_value = DataSourceMetadata(
        source_type="yfinance",
        source_url="https://query2.finance.yahoo.com",
        api_version="v8",
        supports_live=False,
    )
    adapter.supports_live.return_value = False
    return adapter


@pytest.fixture
def mock_ccxt_adapter():
    """Create mock CCXT adapter."""
    adapter = Mock(spec=DataSource)
    adapter.get_metadata.return_value = DataSourceMetadata(
        source_type="ccxt",
        source_url="https://binance.com/api",
        api_version="v3",
        supports_live=True,
    )
    adapter.supports_live.return_value = True
    return adapter


@pytest.fixture
def mock_csv_adapter():
    """Create mock CSV adapter."""
    adapter = Mock(spec=DataSource)
    adapter.get_metadata.return_value = DataSourceMetadata(
        source_type="csv",
        source_url="/path/to/csv",
        api_version="n/a",
        supports_live=False,
    )
    adapter.supports_live.return_value = False
    return adapter


class TestFreshnessPolicyFactory:
    """Tests for freshness policy factory."""

    def test_live_trading_adapter_always_stale(self, mock_ccxt_adapter):
        """Live trading adapters get AlwaysStaleFreshnessPolicy."""
        # Override supports_live to return True
        mock_ccxt_adapter.supports_live.return_value = True

        policy = FreshnessPolicyFactory.create(mock_ccxt_adapter, "1m")

        assert isinstance(policy, AlwaysStaleFreshnessPolicy)

    def test_csv_adapter_never_stale(self, mock_csv_adapter):
        """CSV adapters get NeverStaleFreshnessPolicy."""
        policy = FreshnessPolicyFactory.create(mock_csv_adapter, "1d")

        assert isinstance(policy, NeverStaleFreshnessPolicy)

    def test_yfinance_daily_market_close(self, mock_yfinance_adapter):
        """YFinance daily data gets MarketCloseFreshnessPolicy."""
        policy = FreshnessPolicyFactory.create(mock_yfinance_adapter, "1d")

        assert isinstance(policy, MarketCloseFreshnessPolicy)

    def test_yfinance_hourly_hybrid(self, mock_yfinance_adapter):
        """YFinance hourly data gets HybridFreshnessPolicy."""
        policy = FreshnessPolicyFactory.create(mock_yfinance_adapter, "1h")

        assert isinstance(policy, HybridFreshnessPolicy)
        assert policy.ttl_seconds == 3600  # 1 hour default

    def test_yfinance_minute_hybrid(self, mock_yfinance_adapter):
        """YFinance minute data gets HybridFreshnessPolicy."""
        policy = FreshnessPolicyFactory.create(mock_yfinance_adapter, "1m")

        assert isinstance(policy, HybridFreshnessPolicy)
        assert policy.ttl_seconds == 300  # 5 minutes default

    def test_ccxt_daily_ttl(self, mock_ccxt_adapter):
        """CCXT daily data gets TTLFreshnessPolicy."""
        # Override supports_live to False for non-live scenario
        mock_ccxt_adapter.supports_live.return_value = False

        policy = FreshnessPolicyFactory.create(mock_ccxt_adapter, "1d")

        assert isinstance(policy, TTLFreshnessPolicy)
        assert policy.ttl_seconds == 86400  # 24 hours

    def test_ccxt_hourly_ttl(self, mock_ccxt_adapter):
        """CCXT hourly data gets TTLFreshnessPolicy."""
        mock_ccxt_adapter.supports_live.return_value = False

        policy = FreshnessPolicyFactory.create(mock_ccxt_adapter, "1h")

        assert isinstance(policy, TTLFreshnessPolicy)
        assert policy.ttl_seconds == 3600  # 1 hour

    def test_config_override_ttl(self, mock_yfinance_adapter):
        """Config can override default TTL values."""
        config = {"yfinance.1h_ttl": 7200}  # 2 hours instead of default 1 hour

        policy = FreshnessPolicyFactory.create(mock_yfinance_adapter, "1h", config=config)

        assert isinstance(policy, HybridFreshnessPolicy)
        assert policy.ttl_seconds == 7200

    def test_unknown_source_type_fallback(self):
        """Unknown source types fall back to conservative TTL."""
        adapter = Mock(spec=DataSource)
        adapter.get_metadata.return_value = DataSourceMetadata(
            source_type="unknown",
            source_url="http://unknown.com",
            api_version="v1",
            supports_live=False,
        )
        adapter.supports_live.return_value = False

        policy = FreshnessPolicyFactory.create(adapter, "1d")

        assert isinstance(policy, TTLFreshnessPolicy)
        assert policy.ttl_seconds == 3600  # Conservative 1 hour fallback

    def test_polygon_adapter_market_close(self):
        """Polygon adapter gets market-aware policies."""
        adapter = Mock(spec=DataSource)
        adapter.get_metadata.return_value = DataSourceMetadata(
            source_type="polygon",
            source_url="https://api.polygon.io",
            api_version="v2",
            supports_live=False,
        )
        adapter.supports_live.return_value = False

        # Daily: market close
        policy = FreshnessPolicyFactory.create(adapter, "1d")
        assert isinstance(policy, MarketCloseFreshnessPolicy)

        # Hourly: hybrid
        policy = FreshnessPolicyFactory.create(adapter, "1h")
        assert isinstance(policy, HybridFreshnessPolicy)

    def test_alpaca_adapter_market_close(self):
        """Alpaca adapter gets market-aware policies."""
        adapter = Mock(spec=DataSource)
        adapter.get_metadata.return_value = DataSourceMetadata(
            source_type="alpaca",
            source_url="https://paper-api.alpaca.markets",
            api_version="v2",
            supports_live=False,
        )
        adapter.supports_live.return_value = False

        policy = FreshnessPolicyFactory.create(adapter, "1d")
        assert isinstance(policy, MarketCloseFreshnessPolicy)

    def test_alphavantage_adapter_market_close(self):
        """AlphaVantage adapter gets market-aware policies."""
        adapter = Mock(spec=DataSource)
        adapter.get_metadata.return_value = DataSourceMetadata(
            source_type="alphavantage",
            source_url="https://www.alphavantage.co/query",
            api_version="v1",
            supports_live=False,
        )
        adapter.supports_live.return_value = False

        policy = FreshnessPolicyFactory.create(adapter, "1d")
        assert isinstance(policy, MarketCloseFreshnessPolicy)

    def test_config_override_daily_to_ttl(self, mock_yfinance_adapter):
        """Config can override daily from market_close to TTL."""
        config = {
            "yfinance.daily": "ttl",
            "yfinance.daily_ttl": 43200,  # 12 hours
        }

        policy = FreshnessPolicyFactory.create(mock_yfinance_adapter, "1d", config=config)

        assert isinstance(policy, TTLFreshnessPolicy)
        assert policy.ttl_seconds == 43200
