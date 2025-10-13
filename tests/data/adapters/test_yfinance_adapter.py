"""Tests for YFinanceAdapter.

This module tests the YFinance data adapter for fetching stock/ETF/forex data.
Includes both unit tests and integration tests (marked with @pytest.mark.live).
"""

from decimal import Decimal

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.base import InvalidDataError, NetworkError
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

# ============================================================================
# Unit Tests
# ============================================================================


def test_adapter_initialization() -> None:
    """YFinanceAdapter initializes with correct defaults."""
    adapter = YFinanceAdapter()

    assert adapter.name == "YFinanceAdapter"
    assert adapter.request_delay == 1.0
    assert adapter.fetch_dividends_flag is True
    assert adapter.fetch_splits_flag is True
    assert adapter.last_request_time == 0.0


def test_adapter_custom_initialization() -> None:
    """YFinanceAdapter accepts custom initialization parameters."""
    adapter = YFinanceAdapter(request_delay=2.0, fetch_dividends=False, fetch_splits=False)

    assert adapter.request_delay == 2.0
    assert adapter.fetch_dividends_flag is False
    assert adapter.fetch_splits_flag is False


def test_symbol_normalization() -> None:
    """Symbol normalization converts to uppercase and trims whitespace."""
    adapter = YFinanceAdapter()

    assert adapter._normalize_symbol("aapl") == "AAPL"
    assert adapter._normalize_symbol("  msft  ") == "MSFT"
    assert adapter._normalize_symbol("GOOGL") == "GOOGL"
    assert adapter._normalize_symbol("eurusd=x") == "EURUSD=X"


def test_resolution_mapping() -> None:
    """Resolution mapping contains expected timeframes."""
    assert "1m" in YFinanceAdapter.RESOLUTION_MAPPING
    assert "5m" in YFinanceAdapter.RESOLUTION_MAPPING
    assert "15m" in YFinanceAdapter.RESOLUTION_MAPPING
    assert "30m" in YFinanceAdapter.RESOLUTION_MAPPING
    assert "1h" in YFinanceAdapter.RESOLUTION_MAPPING
    assert "1d" in YFinanceAdapter.RESOLUTION_MAPPING
    assert "1wk" in YFinanceAdapter.RESOLUTION_MAPPING
    assert "1mo" in YFinanceAdapter.RESOLUTION_MAPPING


def test_intraday_resolutions_defined() -> None:
    """Intraday resolutions are correctly identified."""
    assert "1m" in YFinanceAdapter.INTRADAY_RESOLUTIONS
    assert "5m" in YFinanceAdapter.INTRADAY_RESOLUTIONS
    assert "15m" in YFinanceAdapter.INTRADAY_RESOLUTIONS
    assert "30m" in YFinanceAdapter.INTRADAY_RESOLUTIONS
    assert "1h" in YFinanceAdapter.INTRADAY_RESOLUTIONS
    assert "1d" not in YFinanceAdapter.INTRADAY_RESOLUTIONS
    assert "1wk" not in YFinanceAdapter.INTRADAY_RESOLUTIONS


def test_pandas_to_polars_conversion() -> None:
    """Pandas DataFrame converts to Polars with Decimal columns correctly."""
    adapter = YFinanceAdapter()

    # Create sample pandas DataFrame (yfinance format)
    df_pandas = pd.DataFrame(
        {
            "Date": pd.date_range("2023-01-01", periods=3),
            "Open": [100.5, 101.0, 102.5],
            "High": [101.0, 102.0, 103.0],
            "Low": [100.0, 100.5, 102.0],
            "Close": [100.8, 101.5, 102.8],
            "Volume": [1000000, 1100000, 1200000],
            "symbol": ["AAPL"] * 3,
        }
    ).set_index("Date")

    df_polars = adapter._pandas_to_polars(df_pandas)

    # Verify schema
    assert "timestamp" in df_polars.columns
    assert "symbol" in df_polars.columns
    assert "open" in df_polars.columns
    assert "high" in df_polars.columns
    assert "low" in df_polars.columns
    assert "close" in df_polars.columns
    assert "volume" in df_polars.columns

    # Verify data types
    assert df_polars.schema["timestamp"] == pl.Datetime("us")
    assert df_polars.schema["symbol"] == pl.Utf8
    # Decimal columns with scale=8
    assert df_polars.schema["open"] == pl.Decimal(None, 8)
    assert df_polars.schema["high"] == pl.Decimal(None, 8)
    assert df_polars.schema["low"] == pl.Decimal(None, 8)
    assert df_polars.schema["close"] == pl.Decimal(None, 8)
    assert df_polars.schema["volume"] == pl.Decimal(None, 8)

    # Verify row count
    assert len(df_polars) == 3


def test_pandas_to_polars_preserves_values() -> None:
    """Decimal conversion preserves price precision."""
    adapter = YFinanceAdapter()

    # Create sample with precise decimal values
    df_pandas = pd.DataFrame(
        {
            "Date": pd.date_range("2023-01-01", periods=1),
            "Open": [123.456789],
            "High": [124.567890],
            "Low": [122.345678],
            "Close": [123.987654],
            "Volume": [1234567],
            "symbol": ["AAPL"],
        }
    ).set_index("Date")

    df_polars = adapter._pandas_to_polars(df_pandas)

    # Verify values are preserved (within float precision)
    open_val = df_polars["open"][0]
    close_val = df_polars["close"][0]

    # Convert to string for comparison (Decimal comparison)
    assert str(open_val).startswith("123.456")
    assert str(close_val).startswith("123.987")


@pytest.mark.asyncio
async def test_intraday_date_range_validation_rejects_long_ranges() -> None:
    """Intraday resolution rejects date ranges >60 days."""
    adapter = YFinanceAdapter()

    with pytest.raises(ValueError, match="limited to 60 days"):
        await adapter.fetch(
            symbols=["AAPL"],
            start_date=pd.Timestamp("2023-01-01"),
            end_date=pd.Timestamp("2023-03-15"),  # 73 days
            resolution="1m",
        )


@pytest.mark.asyncio
async def test_intraday_date_range_validation_accepts_valid_ranges() -> None:
    """Intraday resolution accepts date ranges <=60 days."""
    import contextlib

    adapter = YFinanceAdapter()

    # This should not raise ValueError (will fail at fetch due to network, but validation passes)
    # We're testing the date range validation, not the actual fetch
    with contextlib.suppress(NetworkError, InvalidDataError):
        await adapter.fetch(
            symbols=["AAPL"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-30"),  # 29 days
            resolution="1m",
        )


@pytest.mark.asyncio
async def test_unsupported_resolution_raises_error() -> None:
    """Unsupported resolution raises ValueError."""
    adapter = YFinanceAdapter()

    with pytest.raises(ValueError, match="Unsupported resolution"):
        await adapter.fetch(
            symbols=["AAPL"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-31"),
            resolution="2h",  # Not supported
        )


@pytest.mark.asyncio
async def test_rate_limiting_enforces_delay() -> None:
    """Rate limiting enforces request delay."""
    adapter = YFinanceAdapter(request_delay=0.5)

    import time

    start_time = time.time()
    await adapter._rate_limit()
    await adapter._rate_limit()
    elapsed = time.time() - start_time

    # Second call should wait at least 0.5 seconds
    assert elapsed >= 0.5


def test_reshape_multi_ticker_with_valid_data() -> None:
    """Multi-ticker DataFrame reshapes correctly."""
    adapter = YFinanceAdapter()

    # Create multi-index DataFrame (yfinance multi-ticker format)
    index = pd.date_range("2023-01-01", periods=2)
    columns = pd.MultiIndex.from_product(
        [["AAPL", "MSFT"], ["Open", "High", "Low", "Close", "Volume"]]
    )

    df = pd.DataFrame(
        [[100, 101, 99, 100.5, 1000, 200, 201, 199, 200.5, 2000]] * 2,
        index=index,
        columns=columns,
    )

    reshaped = adapter._reshape_multi_ticker(df, ["AAPL", "MSFT"])

    # Verify both symbols present
    assert "symbol" in reshaped.columns
    assert set(reshaped["symbol"].unique()) == {"AAPL", "MSFT"}
    assert len(reshaped) == 4  # 2 rows * 2 symbols


def test_reshape_multi_ticker_with_missing_symbol() -> None:
    """Multi-ticker reshape handles missing symbols gracefully."""
    adapter = YFinanceAdapter()

    # Create multi-index DataFrame with only one symbol
    index = pd.date_range("2023-01-01", periods=2)
    columns = pd.MultiIndex.from_product([["AAPL"], ["Open", "High", "Low", "Close", "Volume"]])

    df = pd.DataFrame([[100, 101, 99, 100.5, 1000]] * 2, index=index, columns=columns)

    # Request includes symbol not in data
    reshaped = adapter._reshape_multi_ticker(df, ["AAPL", "INVALID"])

    # Should only contain AAPL
    assert "symbol" in reshaped.columns
    assert list(reshaped["symbol"].unique()) == ["AAPL"]


# ============================================================================
# Integration Tests (Live Data)
# ============================================================================


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_live_equity_daily_data() -> None:
    """Fetch live AAPL daily data from Yahoo Finance."""
    adapter = YFinanceAdapter()

    df = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d",
    )

    # Verify data returned
    assert len(df) > 0, "No data returned for AAPL"

    # Verify symbol present
    assert "AAPL" in df["symbol"].unique().to_list()

    # Verify schema
    assert df.schema["timestamp"] == pl.Datetime("us")
    assert df.schema["symbol"] == pl.Utf8
    assert df.schema["close"] == pl.Decimal(None, None)

    # Verify validation passes
    adapter.validate(df)


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_live_etf_data() -> None:
    """Fetch live SPY ETF daily data."""
    adapter = YFinanceAdapter()

    df = await adapter.fetch(
        symbols=["SPY"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d",
    )

    assert len(df) > 0
    assert "SPY" in df["symbol"].unique().to_list()
    adapter.validate(df)


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_live_forex_data() -> None:
    """Fetch live EURUSD=X forex data."""
    adapter = YFinanceAdapter()

    df = await adapter.fetch(
        symbols=["EURUSD=X"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d",
    )

    assert len(df) > 0
    assert "EURUSD=X" in df["symbol"].unique().to_list()
    adapter.validate(df)


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_live_intraday_data() -> None:
    """Fetch live intraday (1h) data for SPY."""
    adapter = YFinanceAdapter()

    # Use recent dates for intraday (within 60 days)
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=5)

    df = await adapter.fetch(
        symbols=["SPY"],
        start_date=start_date,
        end_date=end_date,
        resolution="1h",
    )

    assert len(df) > 0
    assert "SPY" in df["symbol"].unique().to_list()
    adapter.validate(df)


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_multiple_symbols() -> None:
    """Fetch multiple symbols in single request."""
    adapter = YFinanceAdapter()

    df = await adapter.fetch(
        symbols=["AAPL", "MSFT", "GOOGL"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d",
    )

    assert len(df) > 0

    # Verify all symbols present
    symbols_in_data = df["symbol"].unique().to_list()
    assert "AAPL" in symbols_in_data
    assert "MSFT" in symbols_in_data
    assert "GOOGL" in symbols_in_data

    adapter.validate(df)


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_invalid_symbol_raises_error() -> None:
    """Invalid symbol raises InvalidDataError."""
    adapter = YFinanceAdapter()

    with pytest.raises(InvalidDataError, match="No data returned"):
        await adapter.fetch(
            symbols=["INVALIDTICKER123"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-31"),
            resolution="1d",
        )


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_dividends() -> None:
    """Fetch dividend data for AAPL."""
    adapter = YFinanceAdapter()

    dividends = await adapter.fetch_dividends(["AAPL"])

    # AAPL should have dividend history
    assert "AAPL" in dividends
    assert len(dividends["AAPL"]) > 0

    # Verify schema
    div_df = dividends["AAPL"]
    assert "date" in div_df.columns
    assert "symbol" in div_df.columns
    assert "dividend" in div_df.columns

    # Verify all dividends are positive
    for dividend_amount in div_df["dividend"].to_list():
        assert dividend_amount > Decimal(0)


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_splits() -> None:
    """Fetch split data for AAPL."""
    adapter = YFinanceAdapter()

    splits = await adapter.fetch_splits(["AAPL"])

    # AAPL has had stock splits (e.g., 4:1 in 2020, 7:1 in 2014)
    if "AAPL" in splits:
        split_df = splits["AAPL"]
        assert "date" in split_df.columns
        assert "symbol" in split_df.columns
        assert "split_ratio" in split_df.columns

        # Verify split ratios are positive
        for ratio in split_df["split_ratio"].to_list():
            assert ratio > Decimal(0)


@pytest.mark.live
@pytest.mark.asyncio
async def test_fetch_dividends_for_symbol_without_dividends() -> None:
    """Fetch dividends for symbol without dividend history returns empty dict."""
    adapter = YFinanceAdapter()

    # Some tech companies don't pay dividends
    dividends = await adapter.fetch_dividends(["BRK-B"])

    # BRK-B doesn't pay dividends, should not be in result
    # (or if present, should be empty)
    if "BRK-B" in dividends:
        assert len(dividends["BRK-B"]) == 0


@pytest.mark.live
@pytest.mark.asyncio
async def test_validate_ohlcv_relationships() -> None:
    """Fetched data passes OHLCV validation."""
    adapter = YFinanceAdapter()

    df = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-10"),
        resolution="1d",
    )

    # Validation should pass (no exception)
    result = adapter.validate(df)
    assert result is True


@pytest.mark.live
@pytest.mark.asyncio
async def test_decimal_precision_preservation() -> None:
    """Decimal conversion preserves price precision."""
    adapter = YFinanceAdapter()

    df = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-03"),
        resolution="1d",
    )

    # Verify Decimal type
    first_row = df.row(0, named=True)
    close_price = first_row["close"]

    # Should be Decimal type
    assert isinstance(close_price, Decimal)

    # Should have reasonable price range for AAPL
    assert Decimal("50") < close_price < Decimal("300")
