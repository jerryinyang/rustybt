"""Tests for AlphaVantageAdapter.

This module tests the Alpha Vantage data adapter for stocks, forex, and crypto.
"""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter
from rustybt.data.adapters.api_provider_base import (
    AuthenticationError,
    DataParsingError,
)


def test_adapter_initialization_stocks() -> None:
    """AlphaVantageAdapter initializes correctly for stocks."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        assert adapter.tier == "free"
        assert adapter.asset_type == "stocks"
        assert adapter.api_key == "test_key"
        assert adapter.api_rate_limiter.requests_per_minute == 5
        assert adapter.api_rate_limiter.requests_per_day == 500


def test_adapter_initialization_premium() -> None:
    """AlphaVantageAdapter initializes correctly for premium tier."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="premium", asset_type="stocks")

        assert adapter.tier == "premium"
        assert adapter.api_rate_limiter.requests_per_minute == 75
        assert adapter.api_rate_limiter.requests_per_day == 1200


def test_adapter_initialization_invalid_tier() -> None:
    """AlphaVantageAdapter raises ValueError for invalid tier."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        with pytest.raises(ValueError, match="Invalid tier"):
            AlphaVantageAdapter(tier="invalid", asset_type="stocks")


def test_adapter_initialization_missing_api_key() -> None:
    """AlphaVantageAdapter raises AuthenticationError when API key missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(AuthenticationError, match="API key not found"):
            AlphaVantageAdapter(tier="free", asset_type="stocks")


def test_auth_params() -> None:
    """AlphaVantageAdapter generates correct auth params."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key_123"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")
        params = adapter._get_auth_params()

        assert params == {"apikey": "test_key_123"}


def test_get_function_name_stocks() -> None:
    """Function name generation works for stocks."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        assert adapter._get_function_name("1m") == "TIME_SERIES_INTRADAY"
        assert adapter._get_function_name("1d") == "TIME_SERIES_DAILY"
        assert adapter._get_function_name("1d", adjusted=True) == "TIME_SERIES_DAILY_ADJUSTED"
        assert adapter._get_function_name("1w") == "TIME_SERIES_WEEKLY"
        assert adapter._get_function_name("1w", adjusted=True) == "TIME_SERIES_WEEKLY_ADJUSTED"
        assert adapter._get_function_name("1M") == "TIME_SERIES_MONTHLY"
        assert adapter._get_function_name("1M", adjusted=True) == "TIME_SERIES_MONTHLY_ADJUSTED"


def test_get_function_name_forex() -> None:
    """Function name generation works for forex."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="forex")

        assert adapter._get_function_name("5m") == "FX_INTRADAY"
        assert adapter._get_function_name("1d") == "FX_DAILY"
        assert adapter._get_function_name("1w") == "FX_WEEKLY"
        assert adapter._get_function_name("1M") == "FX_MONTHLY"


def test_get_function_name_crypto() -> None:
    """Function name generation works for crypto."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="crypto")

        assert adapter._get_function_name("15m") == "CRYPTO_INTRADAY"
        assert adapter._get_function_name("1d") == "DIGITAL_CURRENCY_DAILY"
        assert adapter._get_function_name("1w") == "DIGITAL_CURRENCY_WEEKLY"
        assert adapter._get_function_name("1M") == "DIGITAL_CURRENCY_MONTHLY"


def test_intraday_intervals_mapping() -> None:
    """Intraday intervals mapping contains expected values."""
    assert AlphaVantageAdapter.INTRADAY_INTERVALS["1m"] == "1min"
    assert AlphaVantageAdapter.INTRADAY_INTERVALS["5m"] == "5min"
    assert AlphaVantageAdapter.INTRADAY_INTERVALS["1h"] == "60min"


@pytest.mark.asyncio
async def test_fetch_ohlcv_forex_invalid_symbol() -> None:
    """fetch_ohlcv raises ValueError for invalid forex symbol format."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="forex")

        with pytest.raises(ValueError, match="Forex symbol must be in format"):
            await adapter.fetch_ohlcv(
                "EURUSD",  # Missing slash
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-31"),
                "1d",
            )


@pytest.mark.asyncio
async def test_parse_time_series_response() -> None:
    """Time series response parsing works correctly."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        # Mock time series response (daily format)
        mock_response = {
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "133.60",
                    "2. high": "133.75",
                    "3. low": "133.55",
                    "4. close": "133.72",
                    "5. volume": "120000",
                },
                "2024-01-01": {
                    "1. open": "133.52",
                    "2. high": "133.61",
                    "3. low": "133.51",
                    "4. close": "133.59",
                    "5. volume": "100000",
                },
            }
        }

        df = adapter._parse_time_series_response(
            mock_response,
            "AAPL",
            pd.Timestamp("2024-01-01", tz="UTC"),
            pd.Timestamp("2024-01-02", tz="UTC"),
            "1d",
            adjusted=False,
        )

        # Verify DataFrame structure
        assert len(df) == 2
        assert "timestamp" in df.columns
        assert "symbol" in df.columns
        assert "open" in df.columns

        # Verify values
        assert df["symbol"][0] == "AAPL"
        assert df["open"][0] == Decimal("133.52")


@pytest.mark.asyncio
async def test_parse_time_series_response_no_data() -> None:
    """Parsing raises DataParsingError when no time series data."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        mock_response = {}

        with pytest.raises(DataParsingError, match="No time series data found"):
            adapter._parse_time_series_response(
                mock_response,
                "AAPL",
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-31"),
                "1d",
                adjusted=False,
            )


@pytest.mark.asyncio
async def test_validation_passes() -> None:
    """Validation passes for valid OHLCV data."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

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

        assert adapter.validate(df) is True


def test_get_response_keys_standard() -> None:
    """Response key detection works for standard format."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        values = {
            "1. open": "100.0",
            "2. high": "105.0",
            "3. low": "99.0",
            "4. close": "102.0",
            "5. volume": "1000000",
        }

        keys = adapter._get_response_keys(values, adjusted=False)
        assert keys == ("1. open", "2. high", "3. low", "4. close", "5. volume")


def test_get_response_keys_adjusted() -> None:
    """Response key detection works for adjusted format."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        values = {
            "1. open": "100.0",
            "2. high": "105.0",
            "3. low": "99.0",
            "4. close": "102.0",
            "5. adjusted close": "101.5",
            "6. volume": "1000000",
        }

        keys = adapter._get_response_keys(values, adjusted=True)
        assert keys == ("1. open", "2. high", "3. low", "5. adjusted close", "6. volume")


def test_get_response_keys_crypto_usd() -> None:
    """Response key detection works for crypto USD format."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="crypto")

        values = {
            "1a. open (USD)": "50000.0",
            "2a. high (USD)": "51000.0",
            "3a. low (USD)": "49500.0",
            "4a. close (USD)": "50500.0",
            "5. volume": "100",
        }

        keys = adapter._get_response_keys(values, adjusted=False)
        assert keys == (
            "1a. open (USD)",
            "2a. high (USD)",
            "3a. low (USD)",
            "4a. close (USD)",
            "5. volume",
        )


def test_get_response_keys_unknown_format() -> None:
    """Response key detection raises error for unknown format."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        values = {"unknown_key": "value"}

        with pytest.raises(DataParsingError, match="Unknown Alpha Vantage response format"):
            adapter._get_response_keys(values, adjusted=False)


@pytest.mark.asyncio
async def test_parse_adjusted_data() -> None:
    """Adjusted data parsing uses adjusted close."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        # Mock adjusted time series response
        mock_response = {
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "133.60",
                    "2. high": "133.75",
                    "3. low": "133.55",
                    "4. close": "133.72",
                    "5. adjusted close": "130.00",  # Adjusted for splits/dividends
                    "6. volume": "120000",
                },
            }
        }

        df = adapter._parse_time_series_response(
            mock_response,
            "AAPL",
            pd.Timestamp("2024-01-02", tz="UTC"),
            pd.Timestamp("2024-01-02", tz="UTC"),
            "1d",
            adjusted=True,
        )

        # Verify adjusted close is used
        assert len(df) == 1
        assert df["close"][0] == Decimal("130.00")


@pytest.mark.asyncio
async def test_extended_hours_validation() -> None:
    """extended_hours parameter only valid for intraday."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        with pytest.raises(ValueError, match="extended_hours only valid for intraday"):
            await adapter.fetch_ohlcv(
                "AAPL",
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-31"),
                "1d",
                extended_hours=True,
            )


@pytest.mark.asyncio
async def test_month_parameter_validation() -> None:
    """month parameter only valid for intraday."""
    with patch.dict("os.environ", {"ALPHAVANTAGE_API_KEY": "test_key"}):
        adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

        with pytest.raises(ValueError, match="month parameter only valid for intraday"):
            await adapter.fetch_ohlcv(
                "AAPL",
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-31"),
                "1d",
                month="2024-01",
            )


def test_timeframe_mapping() -> None:
    """Timeframe mapping contains expected values."""
    assert AlphaVantageAdapter.TIMEFRAME_MAPPING["1d"] == "daily"
    assert AlphaVantageAdapter.TIMEFRAME_MAPPING["1w"] == "weekly"
    assert AlphaVantageAdapter.TIMEFRAME_MAPPING["1M"] == "monthly"
