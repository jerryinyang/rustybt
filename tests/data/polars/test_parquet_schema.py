"""Tests for Parquet schema definitions."""

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from rustybt.data.polars.parquet_schema import (
    ADJUSTMENTS_SCHEMA,
    DAILY_BARS_SCHEMA,
    MINUTE_BARS_SCHEMA,
    get_schema_for_frequency,
    validate_schema,
)


def test_daily_bars_schema():
    """Test daily bars schema has correct types."""
    assert DAILY_BARS_SCHEMA["date"] == pl.Date
    assert DAILY_BARS_SCHEMA["sid"] == pl.Int64
    assert DAILY_BARS_SCHEMA["open"] == pl.Decimal(precision=18, scale=8)
    assert DAILY_BARS_SCHEMA["high"] == pl.Decimal(precision=18, scale=8)
    assert DAILY_BARS_SCHEMA["low"] == pl.Decimal(precision=18, scale=8)
    assert DAILY_BARS_SCHEMA["close"] == pl.Decimal(precision=18, scale=8)
    assert DAILY_BARS_SCHEMA["volume"] == pl.Decimal(precision=18, scale=8)


def test_minute_bars_schema():
    """Test minute bars schema has correct types."""
    assert MINUTE_BARS_SCHEMA["timestamp"] == pl.Datetime("us")
    assert MINUTE_BARS_SCHEMA["sid"] == pl.Int64
    assert MINUTE_BARS_SCHEMA["open"] == pl.Decimal(precision=18, scale=8)


def test_adjustments_schema():
    """Test adjustments schema has correct types."""
    assert ADJUSTMENTS_SCHEMA["date"] == pl.Date
    assert ADJUSTMENTS_SCHEMA["sid"] == pl.Int64
    assert ADJUSTMENTS_SCHEMA["adjustment_type"] == pl.Utf8
    assert ADJUSTMENTS_SCHEMA["split_ratio"] == pl.Decimal(precision=18, scale=8)
    assert ADJUSTMENTS_SCHEMA["dividend_amount"] == pl.Decimal(precision=18, scale=8)


def test_get_schema_for_frequency_daily():
    """Test getting schema for daily frequency."""
    schema = get_schema_for_frequency("daily")
    assert schema == DAILY_BARS_SCHEMA


def test_get_schema_for_frequency_minute():
    """Test getting schema for minute frequency."""
    schema = get_schema_for_frequency("minute")
    assert schema == MINUTE_BARS_SCHEMA


def test_get_schema_for_frequency_invalid():
    """Test getting schema for invalid frequency raises error."""
    with pytest.raises(ValueError, match="Unsupported frequency"):
        get_schema_for_frequency("hourly")


def test_validate_schema_success():
    """Test schema validation passes for correct schema."""
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [Decimal("100.12345678")],
            "high": [Decimal("101.12345678")],
            "low": [Decimal("99.12345678")],
            "close": [Decimal("100.50000000")],
            "volume": [Decimal("1000000")],
        },
        schema=DAILY_BARS_SCHEMA,
    )

    # Should not raise
    validate_schema(df, DAILY_BARS_SCHEMA)


def test_validate_schema_missing_column():
    """Test schema validation fails for missing column."""
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            # Missing open, high, low, close, volume
        }
    )

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_schema(df, DAILY_BARS_SCHEMA)


def test_validate_schema_extra_column():
    """Test schema validation fails for extra column."""
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [Decimal("100")],
            "high": [Decimal("101")],
            "low": [Decimal("99")],
            "close": [Decimal("100.5")],
            "volume": [Decimal("1000")],
            "extra_col": [42],  # Extra column
        },
        schema={
            **DAILY_BARS_SCHEMA,
            "extra_col": pl.Int64,
        },
    )

    with pytest.raises(ValueError, match="Unexpected extra columns"):
        validate_schema(df, DAILY_BARS_SCHEMA)


def test_validate_schema_wrong_type():
    """Test schema validation fails for wrong data type."""
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [100.0],  # Float instead of Decimal
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000.0],
        }
    )

    with pytest.raises(ValueError, match="incorrect type"):
        validate_schema(df, DAILY_BARS_SCHEMA)


def test_decimal_precision_preserved():
    """Test Decimal precision is preserved in schema."""
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [Decimal("123.45678901")],
            "high": [Decimal("124.45678901")],
            "low": [Decimal("122.45678901")],
            "close": [Decimal("123.50000000")],
            "volume": [Decimal("1000000.12345678")],
        },
        schema=DAILY_BARS_SCHEMA,
    )

    # Verify Decimal values are preserved exactly
    assert df["open"][0] == Decimal("123.45678901")
    assert df["volume"][0] == Decimal("1000000.12345678")


def test_create_dataframe_with_schema():
    """Test creating DataFrame directly with schema."""
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [Decimal("100")],
            "high": [Decimal("105")],
            "low": [Decimal("95")],
            "close": [Decimal("102")],
            "volume": [Decimal("1000")],
        },
        schema=DAILY_BARS_SCHEMA,
    )

    assert len(df) == 1
    assert df.schema == DAILY_BARS_SCHEMA
