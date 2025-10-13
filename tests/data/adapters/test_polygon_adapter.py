"""Tests for PolygonAdapter.

This module tests the Polygon.io data adapter for stocks, options, forex, and crypto.
Includes unit tests with mocked responses.
"""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.api_provider_base import (
    AuthenticationError,
    DataParsingError,
)
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

# ============================================================================
# Unit Tests
# ============================================================================


def test_adapter_initialization_stocks() -> None:
    """PolygonAdapter initializes correctly for stocks."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")

        assert adapter.tier == "free"
        assert adapter.asset_type == "stocks"
        assert adapter.api_key == "test_key"
        assert adapter.api_rate_limiter.requests_per_minute == 5


def test_adapter_initialization_crypto() -> None:
    """PolygonAdapter initializes correctly for crypto."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="developer", asset_type="crypto")

        assert adapter.tier == "developer"
        assert adapter.asset_type == "crypto"
        assert adapter.api_rate_limiter.requests_per_minute == 100


def test_adapter_initialization_invalid_tier() -> None:
    """PolygonAdapter raises ValueError for invalid tier."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        with pytest.raises(ValueError, match="Invalid tier"):
            PolygonAdapter(tier="invalid", asset_type="stocks")


def test_adapter_initialization_invalid_asset_type() -> None:
    """PolygonAdapter raises ValueError for invalid asset_type."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        with pytest.raises(ValueError, match="Invalid asset_type"):
            PolygonAdapter(tier="free", asset_type="invalid")


def test_adapter_initialization_missing_api_key() -> None:
    """PolygonAdapter raises AuthenticationError when API key missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(AuthenticationError, match="API key not found"):
            PolygonAdapter(tier="free", asset_type="stocks")


def test_auth_headers() -> None:
    """PolygonAdapter generates correct auth headers."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key_123"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")
        headers = adapter._get_auth_headers()

        assert headers == {"Authorization": "Bearer test_key_123"}


def test_auth_params() -> None:
    """PolygonAdapter returns empty auth params (uses headers)."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")
        params = adapter._get_auth_params()

        assert params == {}


def test_build_ticker_symbol_stocks() -> None:
    """Ticker symbol builder works for stocks."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")

        assert adapter._build_ticker_symbol("aapl") == "AAPL"
        assert adapter._build_ticker_symbol("MSFT") == "MSFT"


def test_build_ticker_symbol_forex() -> None:
    """Ticker symbol builder works for forex."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="forex")

        assert adapter._build_ticker_symbol("eurusd") == "C:EURUSD"
        assert adapter._build_ticker_symbol("GBPJPY") == "C:GBPJPY"


def test_build_ticker_symbol_crypto() -> None:
    """Ticker symbol builder works for crypto."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="crypto")

        assert adapter._build_ticker_symbol("btcusd") == "X:BTCUSD"
        assert adapter._build_ticker_symbol("ETHUSD") == "X:ETHUSD"


def test_timeframe_mapping() -> None:
    """Timeframe mapping contains expected values."""
    assert PolygonAdapter.TIMEFRAME_MAP["1m"] == ("1", "minute")
    assert PolygonAdapter.TIMEFRAME_MAP["5m"] == ("5", "minute")
    assert PolygonAdapter.TIMEFRAME_MAP["1h"] == ("1", "hour")
    assert PolygonAdapter.TIMEFRAME_MAP["1d"] == ("1", "day")
    assert PolygonAdapter.TIMEFRAME_MAP["1w"] == ("1", "week")


@pytest.mark.asyncio
async def test_fetch_ohlcv_invalid_timeframe() -> None:
    """fetch_ohlcv raises ValueError for invalid timeframe."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")

        with pytest.raises(ValueError, match="Invalid timeframe"):
            await adapter.fetch_ohlcv(
                "AAPL",
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-31"),
                "invalid",
            )


@pytest.mark.asyncio
async def test_parse_aggregates_response() -> None:
    """Aggregates response parsing works correctly."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")

        # Mock aggregates response
        mock_response = {
            "results": [
                {
                    "t": 1609459200000,  # 2021-01-01 00:00:00 UTC
                    "o": 133.52,
                    "h": 133.61,
                    "l": 133.51,
                    "c": 133.59,
                    "v": 100000,
                },
                {
                    "t": 1609545600000,  # 2021-01-02 00:00:00 UTC
                    "o": 133.60,
                    "h": 133.75,
                    "l": 133.55,
                    "c": 133.72,
                    "v": 120000,
                },
            ]
        }

        df = adapter._parse_aggregates_response(mock_response, "AAPL")

        # Verify DataFrame structure
        assert len(df) == 2
        assert "timestamp" in df.columns
        assert "symbol" in df.columns
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns

        # Verify data types
        assert df["symbol"].dtype == pl.Utf8
        # Check that decimal columns are Decimal type (precision may vary from source)
        assert "decimal" in str(df["open"].dtype).lower()
        assert "decimal" in str(df["close"].dtype).lower()

        # Verify values
        assert df["symbol"][0] == "AAPL"
        assert df["open"][0] == Decimal("133.52")
        assert df["close"][1] == Decimal("133.72")


@pytest.mark.asyncio
async def test_parse_aggregates_response_no_results() -> None:
    """Parsing raises DataParsingError when no results."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")

        mock_response = {"results": []}

        with pytest.raises(DataParsingError, match="No results found"):
            adapter._parse_aggregates_response(mock_response, "AAPL")


@pytest.mark.asyncio
async def test_validation_passes() -> None:
    """Validation passes for valid OHLCV data."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")

        # Create valid DataFrame
        df = pl.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
                "symbol": ["AAPL", "AAPL"],
                "open": [Decimal("100.0"), Decimal("101.0")],
                "high": [Decimal("105.0"), Decimal("106.0")],
                "low": [Decimal("99.0"), Decimal("100.0")],
                "close": [Decimal("102.0"), Decimal("103.0")],
                "volume": [Decimal("1000000"), Decimal("1100000")],
            }
        )

        # Should not raise
        assert adapter.validate(df) is True


@pytest.mark.asyncio
async def test_standardize_converts_types() -> None:
    """Standardize converts columns to correct types."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")

        # Create DataFrame with non-standard types
        df = pl.DataFrame(
            {
                "timestamp": ["2024-01-01", "2024-01-02"],
                "symbol": ["AAPL", "AAPL"],
                "open": [100.0, 101.0],  # float instead of Decimal
                "high": [105.0, 106.0],
                "low": [99.0, 100.0],
                "close": [102.0, 103.0],
                "volume": [1000000, 1100000],
            }
        )

        df_std = adapter.standardize(df)

        # Verify types after standardization
        assert df_std["timestamp"].dtype == pl.Datetime("us")
        assert "decimal" in str(df_std["open"].dtype).lower()
        assert "decimal" in str(df_std["high"].dtype).lower()
        assert "decimal" in str(df_std["low"].dtype).lower()
        assert "decimal" in str(df_std["close"].dtype).lower()
        assert "decimal" in str(df_std["volume"].dtype).lower()


@pytest.mark.asyncio
async def test_standardize_sorts_by_timestamp() -> None:
    """Standardize sorts data by timestamp."""
    with patch.dict("os.environ", {"POLYGON_API_KEY": "test_key"}):
        adapter = PolygonAdapter(tier="free", asset_type="stocks")

        # Create unsorted DataFrame
        df = pl.DataFrame(
            {
                "timestamp": [
                    pd.Timestamp("2024-01-03"),
                    pd.Timestamp("2024-01-01"),
                    pd.Timestamp("2024-01-02"),
                ],
                "symbol": ["AAPL", "AAPL", "AAPL"],
                "open": [Decimal("100"), Decimal("100"), Decimal("100")],
                "high": [Decimal("105"), Decimal("105"), Decimal("105")],
                "low": [Decimal("99"), Decimal("99"), Decimal("99")],
                "close": [Decimal("102"), Decimal("102"), Decimal("102")],
                "volume": [Decimal("1000000"), Decimal("1000000"), Decimal("1000000")],
            }
        )

        df_std = adapter.standardize(df)

        # Verify sorted
        assert df_std["timestamp"][0] == pd.Timestamp("2024-01-01")
        assert df_std["timestamp"][1] == pd.Timestamp("2024-01-02")
        assert df_std["timestamp"][2] == pd.Timestamp("2024-01-03")
