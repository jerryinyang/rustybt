"""Tests for Lighter.xyz data adapter.

Tests cover:
- Asset discovery (get_available_assets, get_assets_by_category, filter_assets_by_pattern)
- OHLCV data fetching with pagination
- Data standardization and validation
- Funding rates
- Error handling

Uses mocks for API responses to avoid network dependencies.
"""

import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.base import ValidationError
from rustybt.data.adapters.lighter_adapter import (
    LIGHTER_OHLCV_SCHEMA,
    TIMEFRAME_MAP,
    LighterConnectionError,
    LighterDataAdapter,
    LighterRateLimitError,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def adapter():
    """Create LighterDataAdapter instance for testing."""
    return LighterDataAdapter(testnet=True)


@pytest.fixture
def mock_markets_response():
    """Mock response from /api/v1/markets endpoint."""
    return {
        "markets": [
            {
                "symbol": "BTC-PERP",
                "base_asset": "BTC",
                "quote_asset": "USD",
                "min_size": "0.001",
                "tick_size": "0.01",
            },
            {
                "symbol": "ETH-PERP",
                "base_asset": "ETH",
                "quote_asset": "USD",
                "min_size": "0.01",
                "tick_size": "0.01",
            },
            {
                "symbol": "SOL-SPOT",
                "base_asset": "SOL",
                "quote_asset": "USD",
                "min_size": "0.1",
                "tick_size": "0.001",
            },
        ]
    }


@pytest.fixture
def mock_candles_response():
    """Mock response from /api/v1/candlesticks endpoint."""
    base_ts = 1704067200  # 2024-01-01 00:00:00 UTC
    return {
        "candles": [
            {
                "timestamp": base_ts,
                "open": "42000.50",
                "high": "42500.00",
                "low": "41800.00",
                "close": "42300.00",
                "volume": "1234.56",
            },
            {
                "timestamp": base_ts + 3600,
                "open": "42300.00",
                "high": "42800.00",
                "low": "42100.00",
                "close": "42600.00",
                "volume": "2345.67",
            },
            {
                "timestamp": base_ts + 7200,
                "open": "42600.00",
                "high": "43000.00",
                "low": "42400.00",
                "close": "42900.00",
                "volume": "3456.78",
            },
        ]
    }


@pytest.fixture
def mock_funding_rates_response():
    """Mock response from /api/v1/funding-rates endpoint."""
    base_ts = 1704067200000  # milliseconds
    return {
        "rates": [
            {"timestamp": base_ts, "rate": "0.0001"},
            {"timestamp": base_ts + 28800000, "rate": "0.00015"},
            {"timestamp": base_ts + 57600000, "rate": "-0.00005"},
        ]
    }


# =============================================================================
# Helper to create mock aiohttp response
# =============================================================================


def create_mock_response(json_data, status=200):
    """Create a mock aiohttp response context manager."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data)
    mock_resp.raise_for_status = MagicMock()

    # Make it work as async context manager
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    return mock_cm


# =============================================================================
# Asset Discovery Tests (Story 10.5.1)
# =============================================================================


class TestAssetDiscovery:
    """Tests for asset discovery functionality."""

    @pytest.mark.asyncio
    async def test_get_available_assets_success(self, adapter, mock_markets_response):
        """Test successful asset discovery."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_markets_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            assets = await adapter.get_available_assets()

            assert len(assets) == 3
            assert assets[0]["symbol"] == "BTC-PERP"
            assert assets[0]["base"] == "BTC"
            assert assets[0]["quote"] == "USD"
            assert assets[0]["category"] == "perpetual"
            assert isinstance(assets[0]["min_size"], Decimal)
            assert isinstance(assets[0]["tick_size"], Decimal)

    @pytest.mark.asyncio
    async def test_get_available_assets_cache(self, adapter, mock_markets_response):
        """Test that assets are cached."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_markets_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            # First call
            assets1 = await adapter.get_available_assets()
            # Second call should use cache
            assets2 = await adapter.get_available_assets()

            # Only one API call should be made
            assert mock_session.get.call_count == 1
            assert assets1 == assets2

    @pytest.mark.asyncio
    async def test_get_assets_by_category_perpetual(self, adapter, mock_markets_response):
        """Test filtering assets by perpetual category."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_markets_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            perps = await adapter.get_assets_by_category("perpetual")

            assert len(perps) == 2
            assert all(a["category"] == "perpetual" for a in perps)

    @pytest.mark.asyncio
    async def test_get_assets_by_category_spot(self, adapter, mock_markets_response):
        """Test filtering assets by spot category."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_markets_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            spots = await adapter.get_assets_by_category("spot")

            assert len(spots) == 1
            assert spots[0]["symbol"] == "SOL-SPOT"

    @pytest.mark.asyncio
    async def test_get_assets_by_category_case_insensitive(self, adapter, mock_markets_response):
        """Test that category filtering is case-insensitive."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_markets_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            perps_lower = await adapter.get_assets_by_category("perpetual")
            # Clear cache for next call
            adapter._assets_cache = None
            perps_upper = await adapter.get_assets_by_category("PERPETUAL")

            assert len(perps_lower) == len(perps_upper)

    def test_filter_assets_by_pattern_exact(self, adapter):
        """Test exact pattern matching."""
        assets = [
            {"symbol": "BTC-PERP", "category": "perpetual"},
            {"symbol": "ETH-PERP", "category": "perpetual"},
            {"symbol": "SOL-PERP", "category": "perpetual"},
        ]

        filtered = adapter.filter_assets_by_pattern(assets, "BTC-PERP")

        assert len(filtered) == 1
        assert filtered[0]["symbol"] == "BTC-PERP"

    def test_filter_assets_by_pattern_wildcard(self, adapter):
        """Test wildcard pattern matching."""
        assets = [
            {"symbol": "BTC-PERP", "category": "perpetual"},
            {"symbol": "ETH-PERP", "category": "perpetual"},
            {"symbol": "BTC-SPOT", "category": "spot"},
        ]

        # Match all BTC symbols
        filtered = adapter.filter_assets_by_pattern(assets, "BTC*")
        assert len(filtered) == 2

        # Match all PERP symbols
        filtered = adapter.filter_assets_by_pattern(assets, "*PERP")
        assert len(filtered) == 2

    def test_filter_assets_by_pattern_regex(self, adapter):
        """Test regex pattern matching."""
        assets = [
            {"symbol": "BTC-PERP", "category": "perpetual"},
            {"symbol": "ETH-PERP", "category": "perpetual"},
            {"symbol": "BTCUSDT", "category": "spot"},
        ]

        # Match symbols containing BTC
        filtered = adapter.filter_assets_by_pattern(assets, "BTC.*")
        assert len(filtered) == 2

    def test_filter_assets_by_pattern_empty(self, adapter):
        """Test empty pattern returns all assets."""
        assets = [
            {"symbol": "BTC-PERP"},
            {"symbol": "ETH-PERP"},
        ]

        filtered = adapter.filter_assets_by_pattern(assets, "")

        assert len(filtered) == 2

    @pytest.mark.asyncio
    async def test_get_available_assets_connection_error(self, adapter):
        """Test handling of connection errors."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            with pytest.raises(LighterConnectionError):
                await adapter.get_available_assets()


# =============================================================================
# OHLCV Data Fetching Tests (Story 10.5.2)
# =============================================================================


class TestOHLCVFetching:
    """Tests for OHLCV data fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_single_symbol(self, adapter, mock_candles_response):
        """Test fetching data for a single symbol."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_candles_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            df = await adapter.fetch(
                symbols=["BTC-PERP"],
                start_date=pd.Timestamp("2024-01-01"),
                end_date=pd.Timestamp("2024-01-02"),
                resolution="1h",
            )

            assert not df.is_empty()
            assert len(df) == 3
            assert "timestamp" in df.columns
            assert "symbol" in df.columns
            assert "open" in df.columns
            assert "high" in df.columns
            assert "low" in df.columns
            assert "close" in df.columns
            assert "volume" in df.columns

    @pytest.mark.asyncio
    async def test_fetch_multiple_symbols(self, adapter, mock_candles_response):
        """Test fetching data for multiple symbols."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_candles_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            df = await adapter.fetch(
                symbols=["BTC-PERP", "ETH-PERP"],
                start_date=pd.Timestamp("2024-01-01"),
                end_date=pd.Timestamp("2024-01-02"),
                resolution="1h",
            )

            assert not df.is_empty()
            # Each symbol gets 3 candles
            assert len(df) == 6

    def test_map_resolution_valid(self, adapter):
        """Test valid resolution mapping."""
        assert adapter._map_resolution("1m") == "1"
        assert adapter._map_resolution("5m") == "5"
        assert adapter._map_resolution("15m") == "15"
        assert adapter._map_resolution("1h") == "60"
        assert adapter._map_resolution("4h") == "240"
        assert adapter._map_resolution("1d") == "1440"

    def test_map_resolution_invalid(self, adapter):
        """Test invalid resolution raises error."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            adapter._map_resolution("2h")

    @pytest.mark.asyncio
    async def test_fetch_empty_response(self, adapter):
        """Test handling of empty response."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response({"candles": []}))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            df = await adapter.fetch(
                symbols=["BTC-PERP"],
                start_date=pd.Timestamp("2024-01-01"),
                end_date=pd.Timestamp("2024-01-02"),
                resolution="1h",
            )

            assert df.is_empty()
            # Should have correct schema
            assert set(df.columns) == set(LIGHTER_OHLCV_SCHEMA.keys())


# =============================================================================
# Data Standardization & Validation Tests (Story 10.5.3)
# =============================================================================


class TestDataStandardization:
    """Tests for data standardization and validation."""

    def test_standardize_column_mapping(self, adapter):
        """Test column name mapping during standardization."""
        # Create DataFrame with raw column names
        raw_df = pl.DataFrame(
            {
                "t": [1704067200000000],  # microseconds
                "symbol": ["BTC-PERP"],
                "o": [42000.5],
                "h": [42500.0],
                "l": [41800.0],
                "c": [42300.0],
                "v": [1234.56],
            }
        )

        standardized = adapter.standardize(raw_df)

        assert "timestamp" in standardized.columns
        assert "open" in standardized.columns
        assert "high" in standardized.columns
        assert "low" in standardized.columns
        assert "close" in standardized.columns
        assert "volume" in standardized.columns

    def test_validate_success(self, adapter):
        """Test validation of valid OHLCV data."""
        valid_df = pl.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01")],
                "symbol": ["BTC-PERP"],
                "open": [Decimal("42000.50")],
                "high": [Decimal("42500.00")],
                "low": [Decimal("41800.00")],
                "close": [Decimal("42300.00")],
                "volume": [Decimal("1234.56")],
            }
        )

        result = adapter.validate(valid_df)
        assert result is True

    def test_validate_missing_columns(self, adapter):
        """Test validation fails with missing columns."""
        invalid_df = pl.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01")],
                "symbol": ["BTC-PERP"],
                "open": [Decimal("42000.50")],
                # Missing high, low, close, volume
            }
        )

        with pytest.raises(ValidationError, match="Missing columns"):
            adapter.validate(invalid_df)

    def test_validate_ohlcv_relationship_low_greater_than_open(self, adapter):
        """Test validation fails when low > open."""
        invalid_df = pl.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01")],
                "symbol": ["BTC-PERP"],
                "open": [Decimal("42000.50")],
                "high": [Decimal("42500.00")],
                "low": [Decimal("42100.00")],  # Low > Open
                "close": [Decimal("42300.00")],
                "volume": [Decimal("1234.56")],
            }
        )

        with pytest.raises(ValidationError, match="OHLCV relationship violated"):
            adapter.validate(invalid_df)

    def test_validate_ohlcv_relationship_high_less_than_close(self, adapter):
        """Test validation fails when high < close."""
        invalid_df = pl.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01")],
                "symbol": ["BTC-PERP"],
                "open": [Decimal("42000.50")],
                "high": [Decimal("42200.00")],  # High < Close
                "low": [Decimal("41800.00")],
                "close": [Decimal("42300.00")],
                "volume": [Decimal("1234.56")],
            }
        )

        with pytest.raises(ValidationError, match="OHLCV relationship violated"):
            adapter.validate(invalid_df)


# =============================================================================
# Funding Rates Tests (Story 10.5.3)
# =============================================================================


class TestFundingRates:
    """Tests for funding rate fetching."""

    @pytest.mark.asyncio
    async def test_get_funding_rates_success(self, adapter, mock_funding_rates_response):
        """Test successful funding rate fetch."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_funding_rates_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            df = await adapter.get_funding_rates("BTC-PERP")

            assert not df.is_empty()
            assert len(df) == 3
            assert "timestamp" in df.columns
            assert "symbol" in df.columns
            assert "funding_rate" in df.columns
            assert df["symbol"].to_list() == ["BTC-PERP"] * 3

    @pytest.mark.asyncio
    async def test_get_funding_rates_with_date_range(self, adapter, mock_funding_rates_response):
        """Test funding rate fetch with date range."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=create_mock_response(mock_funding_rates_response))
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            df = await adapter.get_funding_rates(
                "BTC-PERP",
                start_date=pd.Timestamp("2024-01-01"),
                end_date=pd.Timestamp("2024-01-02"),
            )

            # Verify API was called (get returns a context manager)
            assert mock_session.get.called


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, adapter):
        """Test handling of rate limit errors."""
        # Create a response that returns 429 status
        mock_resp = AsyncMock()
        mock_resp.status = 429
        mock_resp.raise_for_status = MagicMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_cm)
        mock_session.closed = False

        with patch.object(adapter, "_get_session", return_value=mock_session):
            with pytest.raises(LighterRateLimitError):
                await adapter.get_available_assets()

    @pytest.mark.asyncio
    async def test_close_session(self, adapter):
        """Test closing the HTTP session."""
        # Initialize session
        mock_session = AsyncMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        adapter._session = mock_session

        await adapter.close()

        mock_session.close.assert_called_once()
        assert adapter._session is None


# =============================================================================
# Integration Tests (skipped without credentials)
# =============================================================================


skip_without_lighter_testnet = pytest.mark.skipif(
    not os.environ.get("LIGHTER_TESTNET_API_KEY"),
    reason="Lighter.xyz testnet credentials not available",
)


@pytest.mark.integration
@skip_without_lighter_testnet
class TestLighterIntegration:
    """Integration tests for Lighter.xyz data adapter.

    These tests connect to the actual Lighter.xyz testnet API.
    Skipped if credentials are not available.
    """

    @pytest.mark.asyncio
    async def test_live_get_available_assets(self):
        """Test live asset discovery on testnet."""
        async with LighterDataAdapter(testnet=True) as adapter:
            assets = await adapter.get_available_assets()

            assert len(assets) > 0
            assert all("symbol" in a for a in assets)
            assert all("category" in a for a in assets)

    @pytest.mark.asyncio
    async def test_live_fetch_ohlcv(self):
        """Test live OHLCV fetch on testnet."""
        async with LighterDataAdapter(testnet=True) as adapter:
            # Get first available asset
            assets = await adapter.get_available_assets()
            if not assets:
                pytest.skip("No assets available on testnet")

            symbol = assets[0]["symbol"]

            # Fetch recent data
            end_date = pd.Timestamp.utcnow()
            start_date = end_date - pd.Timedelta(days=1)

            df = await adapter.fetch(
                symbols=[symbol],
                start_date=start_date,
                end_date=end_date,
                resolution="1h",
            )

            # May be empty if no trading activity
            assert df.columns == list(LIGHTER_OHLCV_SCHEMA.keys()) or df.is_empty()
