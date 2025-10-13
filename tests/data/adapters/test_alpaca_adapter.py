"""Tests for AlpacaAdapter.

This module tests the Alpaca Market Data API adapter for US stocks.
"""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter
from rustybt.data.adapters.api_provider_base import AuthenticationError, DataParsingError


def test_adapter_initialization_paper() -> None:
    """AlpacaAdapter initializes correctly for paper trading."""
    with patch.dict(
        "os.environ",
        {"ALPACA_API_KEY": "test_key", "ALPACA_API_SECRET": "test_secret"},
    ):
        adapter = AlpacaAdapter(is_paper=True)

        assert adapter.is_paper is True
        assert adapter.api_key == "test_key"
        assert adapter.api_secret == "test_secret"
        assert adapter.api_rate_limiter.requests_per_minute == 200


def test_adapter_initialization_live() -> None:
    """AlpacaAdapter initializes correctly for live trading."""
    with patch.dict(
        "os.environ",
        {"ALPACA_API_KEY": "test_key", "ALPACA_API_SECRET": "test_secret"},
    ):
        adapter = AlpacaAdapter(is_paper=False)

        assert adapter.is_paper is False


def test_adapter_initialization_missing_api_key() -> None:
    """AlpacaAdapter raises AuthenticationError when API key missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(AuthenticationError, match="API key not found"):
            AlpacaAdapter()


def test_auth_headers() -> None:
    """AlpacaAdapter generates correct auth headers."""
    with patch.dict(
        "os.environ",
        {"ALPACA_API_KEY": "key_123", "ALPACA_API_SECRET": "secret_456"},
    ):
        adapter = AlpacaAdapter()
        headers = adapter._get_auth_headers()

        assert headers == {
            "APCA-API-KEY-ID": "key_123",
            "APCA-API-SECRET-KEY": "secret_456",
        }


def test_timeframe_mapping() -> None:
    """Timeframe mapping contains expected values."""
    assert AlpacaAdapter.TIMEFRAME_MAP["1m"] == "1Min"
    assert AlpacaAdapter.TIMEFRAME_MAP["5m"] == "5Min"
    assert AlpacaAdapter.TIMEFRAME_MAP["1h"] == "1Hour"
    assert AlpacaAdapter.TIMEFRAME_MAP["1d"] == "1Day"


@pytest.mark.asyncio
async def test_fetch_ohlcv_invalid_timeframe() -> None:
    """fetch_ohlcv raises ValueError for invalid timeframe."""
    with patch.dict(
        "os.environ",
        {"ALPACA_API_KEY": "test_key", "ALPACA_API_SECRET": "test_secret"},
    ):
        adapter = AlpacaAdapter()

        with pytest.raises(ValueError, match="Invalid timeframe"):
            await adapter.fetch_ohlcv(
                "AAPL",
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-31"),
                "invalid",
            )


@pytest.mark.asyncio
async def test_parse_bars_response() -> None:
    """Bars response parsing works correctly."""
    with patch.dict(
        "os.environ",
        {"ALPACA_API_KEY": "test_key", "ALPACA_API_SECRET": "test_secret"},
    ):
        adapter = AlpacaAdapter()

        # Mock bars response
        mock_response = {
            "bars": [
                {
                    "t": "2021-01-01T16:00:00Z",
                    "o": 133.52,
                    "h": 133.61,
                    "l": 133.51,
                    "c": 133.59,
                    "v": 100000,
                    "n": 1234,
                    "vw": 133.56,
                },
                {
                    "t": "2021-01-02T16:00:00Z",
                    "o": 133.60,
                    "h": 133.75,
                    "l": 133.55,
                    "c": 133.72,
                    "v": 120000,
                    "n": 1500,
                    "vw": 133.65,
                },
            ]
        }

        df = adapter._parse_bars_response(mock_response, "AAPL")

        # Verify DataFrame structure
        assert len(df) == 2
        assert "timestamp" in df.columns
        assert "symbol" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns

        # Verify values
        assert df["symbol"][0] == "AAPL"
        assert df["open"][0] == Decimal("133.52")
        assert df["close"][1] == Decimal("133.72")


@pytest.mark.asyncio
async def test_parse_bars_response_no_bars() -> None:
    """Parsing raises DataParsingError when no bars."""
    with patch.dict(
        "os.environ",
        {"ALPACA_API_KEY": "test_key", "ALPACA_API_SECRET": "test_secret"},
    ):
        adapter = AlpacaAdapter()

        mock_response = {"bars": []}

        with pytest.raises(DataParsingError, match="No bars found"):
            adapter._parse_bars_response(mock_response, "AAPL")


@pytest.mark.asyncio
async def test_validation_passes() -> None:
    """Validation passes for valid OHLCV data."""
    with patch.dict(
        "os.environ",
        {"ALPACA_API_KEY": "test_key", "ALPACA_API_SECRET": "test_secret"},
    ):
        adapter = AlpacaAdapter()

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
