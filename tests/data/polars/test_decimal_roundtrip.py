"""Tests for Decimal precision preservation through roundtrip cycles.

These tests ensure no precision loss occurs during:
- CSV ingestion → Parquet storage → Parquet read
- DataFrame write → Parquet → DataFrame read
- Multiple read/write cycles
"""

import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl

from rustybt.data.polars.aggregation import (
    resample_minute_to_daily,
)
from rustybt.data.polars.parquet_schema import DAILY_BARS_SCHEMA, MINUTE_BARS_SCHEMA


def test_parquet_roundtrip_daily_bars():
    """Test Decimal precision preserved through Parquet write/read cycle."""
    # Create test data with precise Decimal values
    original_df = pl.DataFrame(
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

    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = Path(tmpdir) / "test.parquet"

        # Write to Parquet
        original_df.write_parquet(parquet_path, compression="snappy")

        # Read back
        loaded_df = pl.read_parquet(parquet_path)

        # Verify exact equality (no precision loss)
        assert loaded_df["open"][0] == original_df["open"][0]
        assert loaded_df["high"][0] == original_df["high"][0]
        assert loaded_df["low"][0] == original_df["low"][0]
        assert loaded_df["close"][0] == original_df["close"][0]
        assert loaded_df["volume"][0] == original_df["volume"][0]


def test_parquet_roundtrip_satoshi_precision():
    """Test Bitcoin satoshi precision (0.00000001) is preserved."""
    original_df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [Decimal("0.00000001")],  # 1 satoshi
            "high": [Decimal("0.00000002")],
            "low": [Decimal("0.00000001")],
            "close": [Decimal("0.00000001")],
            "volume": [Decimal("1000000000.00000000")],
        },
        schema=DAILY_BARS_SCHEMA,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = Path(tmpdir) / "satoshi.parquet"

        # Write and read
        original_df.write_parquet(parquet_path)
        loaded_df = pl.read_parquet(parquet_path)

        # Verify satoshi precision preserved
        assert loaded_df["open"][0] == Decimal("0.00000001")
        assert loaded_df["high"][0] == Decimal("0.00000002")


def test_parquet_roundtrip_high_value_stocks():
    """Test high-value stock prices are preserved."""
    # Test with BRK.A-like prices (> $500,000)
    original_df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [Decimal("542380.50")],
            "high": [Decimal("543200.75")],
            "low": [Decimal("541500.25")],
            "close": [Decimal("542800.00")],
            "volume": [Decimal("100.00")],
        },
        schema=DAILY_BARS_SCHEMA,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = Path(tmpdir) / "high_value.parquet"

        original_df.write_parquet(parquet_path)
        loaded_df = pl.read_parquet(parquet_path)

        assert loaded_df["open"][0] == Decimal("542380.50")
        assert loaded_df["high"][0] == Decimal("543200.75")


def test_multiple_roundtrip_cycles():
    """Test precision preserved through multiple write/read cycles."""
    original_df = pl.DataFrame(
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

    with tempfile.TemporaryDirectory() as tmpdir:
        # Perform 10 write/read cycles
        df = original_df
        for i in range(10):
            parquet_path = Path(tmpdir) / f"cycle_{i}.parquet"
            df.write_parquet(parquet_path)
            df = pl.read_parquet(parquet_path)

        # Verify values still exact after 10 cycles
        assert df["open"][0] == original_df["open"][0]
        assert df["high"][0] == original_df["high"][0]
        assert df["low"][0] == original_df["low"][0]
        assert df["close"][0] == original_df["close"][0]
        assert df["volume"][0] == original_df["volume"][0]


def test_aggregation_preserves_precision():
    """Test minute → daily aggregation preserves Decimal precision."""
    minute_df = pl.DataFrame(
        {
            "timestamp": [
                datetime(2023, 1, 1, 9, 30),
                datetime(2023, 1, 1, 9, 31),
                datetime(2023, 1, 1, 9, 32),
            ],
            "sid": [1, 1, 1],
            "open": [
                Decimal("100.01234567"),
                Decimal("100.02234567"),
                Decimal("100.03234567"),
            ],
            "high": [
                Decimal("100.05234567"),
                Decimal("100.06234567"),
                Decimal("100.07234567"),
            ],
            "low": [
                Decimal("99.99234567"),
                Decimal("99.98234567"),
                Decimal("99.97234567"),
            ],
            "close": [
                Decimal("100.02234567"),
                Decimal("100.03234567"),
                Decimal("100.04234567"),
            ],
            "volume": [Decimal("1000"), Decimal("1500"), Decimal("2000")],
        },
        schema=MINUTE_BARS_SCHEMA,
    )

    daily_df = resample_minute_to_daily(minute_df)

    # Verify aggregation results maintain precision
    assert daily_df["open"][0] == Decimal("100.01234567")  # First open
    assert daily_df["high"][0] == Decimal("100.07234567")  # Max high
    assert daily_df["low"][0] == Decimal("99.97234567")  # Min low
    assert daily_df["close"][0] == Decimal("100.04234567")  # Last close
    assert daily_df["volume"][0] == Decimal("4500")  # Sum volume


def test_compression_preserves_precision():
    """Test different compression codecs preserve Decimal precision."""
    original_df = pl.DataFrame(
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

    compression_codecs = ["snappy", "zstd", "lz4"]

    with tempfile.TemporaryDirectory() as tmpdir:
        for codec in compression_codecs:
            parquet_path = Path(tmpdir) / f"test_{codec}.parquet"

            # Write with compression
            original_df.write_parquet(parquet_path, compression=codec)

            # Read back
            loaded_df = pl.read_parquet(parquet_path)

            # Verify precision preserved regardless of compression
            assert (
                loaded_df["open"][0] == original_df["open"][0]
            ), f"Compression {codec} lost precision"
            assert (
                loaded_df["volume"][0] == original_df["volume"][0]
            ), f"Compression {codec} lost precision"


def test_negative_values_precision():
    """Test negative Decimal values (e.g., for returns) are preserved."""
    # While prices are non-negative, derived values like returns can be negative
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [Decimal("-0.05123456")],  # Negative return
            "high": [Decimal("0.10123456")],
            "low": [Decimal("-0.08123456")],
            "close": [Decimal("-0.02123456")],
            "volume": [Decimal("1000")],
        },
        schema=DAILY_BARS_SCHEMA,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = Path(tmpdir) / "negative.parquet"

        df.write_parquet(parquet_path)
        loaded_df = pl.read_parquet(parquet_path)

        assert loaded_df["open"][0] == Decimal("-0.05123456")
        assert loaded_df["low"][0] == Decimal("-0.08123456")


def test_zero_values_precision():
    """Test zero values maintain precision."""
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, 1)],
            "sid": [1],
            "open": [Decimal("0.00000000")],
            "high": [Decimal("0.00000001")],
            "low": [Decimal("0.00000000")],
            "close": [Decimal("0.00000000")],
            "volume": [Decimal("0")],
        },
        schema=DAILY_BARS_SCHEMA,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = Path(tmpdir) / "zeros.parquet"

        df.write_parquet(parquet_path)
        loaded_df = pl.read_parquet(parquet_path)

        assert loaded_df["open"][0] == Decimal("0.00000000")
        assert loaded_df["volume"][0] == Decimal("0")


def test_large_dataset_roundtrip():
    """Test precision preserved for large datasets."""
    # Create 1000 rows with varying Decimal precision
    n_rows = 1000
    df = pl.DataFrame(
        {
            "date": [date(2023, 1, i % 28 + 1) for i in range(n_rows)],
            "sid": [i % 10 + 1 for i in range(n_rows)],
            "open": [Decimal(f"{100 + i * 0.12345678}") for i in range(n_rows)],
            "high": [Decimal(f"{101 + i * 0.12345678}") for i in range(n_rows)],
            "low": [Decimal(f"{99 + i * 0.12345678}") for i in range(n_rows)],
            "close": [Decimal(f"{100.5 + i * 0.12345678}") for i in range(n_rows)],
            "volume": [Decimal(f"{1000 + i}") for i in range(n_rows)],
        },
        schema=DAILY_BARS_SCHEMA,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        parquet_path = Path(tmpdir) / "large.parquet"

        df.write_parquet(parquet_path)
        loaded_df = pl.read_parquet(parquet_path)

        # Verify all rows maintain precision
        assert len(loaded_df) == n_rows
        for i in range(n_rows):
            assert loaded_df["open"][i] == df["open"][i]
            assert loaded_df["close"][i] == df["close"][i]
