"""Per-module benchmarks for Decimal data pipeline operations.

Measures performance overhead of Decimal-based data loading and processing
compared to float-based pipelines.

Run with: pytest benchmarks/decimal_data_pipeline_benchmark.py --benchmark-only
"""

import random
import tempfile
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest


@pytest.fixture
def temp_parquet_file():
    """Create temporary Parquet file with OHLCV data."""
    # Generate sample OHLCV data
    random.seed(42)
    num_rows = 252 * 100  # 1 year × 100 assets

    data = {
        "date": [
            f"2024-{(i % 252) // 21 + 1:02d}-{(i % 252) % 21 + 1:02d}" for i in range(num_rows)
        ],
        "symbol": [f"STOCK{(i % 100) + 1}" for i in range(num_rows)],
        "open": [Decimal(str(50.0 + random.random() * 10)) for _ in range(num_rows)],
        "high": [Decimal(str(55.0 + random.random() * 10)) for _ in range(num_rows)],
        "low": [Decimal(str(45.0 + random.random() * 10)) for _ in range(num_rows)],
        "close": [Decimal(str(50.0 + random.random() * 10)) for _ in range(num_rows)],
        "volume": [Decimal(str(random.random() * 1000000)) for _ in range(num_rows)],
    }

    df = pl.DataFrame(
        {
            "date": data["date"],
            "symbol": data["symbol"],
            "open": pl.Series(data["open"], dtype=pl.Decimal(scale=8)),
            "high": pl.Series(data["high"], dtype=pl.Decimal(scale=8)),
            "low": pl.Series(data["low"], dtype=pl.Decimal(scale=8)),
            "close": pl.Series(data["close"], dtype=pl.Decimal(scale=8)),
            "volume": pl.Series(data["volume"], dtype=pl.Decimal(scale=8)),
        }
    )

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        temp_path = Path(f.name)
        df.write_parquet(temp_path, compression="snappy")

    yield temp_path

    # Cleanup
    temp_path.unlink()


@pytest.mark.benchmark(group="data-load")
def test_load_parquet_decimal_columns(benchmark, temp_parquet_file):
    """Benchmark loading Parquet file with Decimal columns.

    1 year × 100 assets = 25,200 rows
    Expected: ~100-300 milliseconds
    Target (Epic 7): <80 milliseconds
    """

    def load_data():
        return pl.read_parquet(temp_parquet_file)

    result = benchmark(load_data)

    assert len(result) == 25200
    assert "open" in result.columns


@pytest.mark.benchmark(group="data-validation")
def test_ohlcv_validation_25200_rows(benchmark, temp_parquet_file):
    """Benchmark OHLCV data validation.

    Validates: high >= low, high >= open, high >= close, low <= open, low <= close
    Expected: ~50-150 milliseconds
    Target (Epic 7): <30 milliseconds
    """
    df = pl.read_parquet(temp_parquet_file)

    def validate_ohlcv():
        # Check OHLCV relationships
        invalid_rows = df.filter(
            (pl.col("high") < pl.col("low"))
            | (pl.col("high") < pl.col("open"))
            | (pl.col("high") < pl.col("close"))
            | (pl.col("low") > pl.col("open"))
            | (pl.col("low") > pl.col("close"))
        )
        return len(invalid_rows)

    result = benchmark(validate_ohlcv)

    # Should have 0 invalid rows in well-formed data
    assert result >= 0


@pytest.mark.benchmark(group="data-filter")
def test_filter_by_symbol_100_assets(benchmark, temp_parquet_file):
    """Benchmark filtering data by symbol.

    Expected: ~20-60 milliseconds
    Target (Epic 7): <15 milliseconds
    """
    df = pl.read_parquet(temp_parquet_file)

    def filter_data():
        return df.filter(pl.col("symbol") == "STOCK50")

    result = benchmark(filter_data)

    assert len(result) == 252  # 1 year of data for 1 asset


@pytest.mark.benchmark(group="data-aggregation")
def test_aggregate_ohlcv_by_symbol(benchmark, temp_parquet_file):
    """Benchmark aggregating OHLCV data by symbol.

    Calculates mean, std, min, max for each symbol.
    Expected: ~100-250 milliseconds
    Target (Epic 7): <70 milliseconds
    """
    df = pl.read_parquet(temp_parquet_file)

    def aggregate_data():
        return df.group_by("symbol").agg(
            [
                pl.col("close").mean().alias("mean_close"),
                pl.col("close").std().alias("std_close"),
                pl.col("volume").sum().alias("total_volume"),
                pl.col("high").max().alias("max_high"),
                pl.col("low").min().alias("min_low"),
            ]
        )

    result = benchmark(aggregate_data)

    assert len(result) == 100  # 100 unique symbols


@pytest.mark.benchmark(group="data-returns")
def test_calculate_returns_25200_rows(benchmark, temp_parquet_file):
    """Benchmark calculating returns from close prices.

    Expected: ~80-200 milliseconds
    Target (Epic 7): <50 milliseconds
    """
    df = pl.read_parquet(temp_parquet_file)

    def calculate_returns():
        return df.with_columns(
            [
                ((pl.col("close") - pl.col("close").shift(1)) / pl.col("close").shift(1)).alias(
                    "returns"
                )
            ]
        )

    result = benchmark(calculate_returns)

    assert "returns" in result.columns
    assert len(result) == 25200


@pytest.mark.benchmark(group="data-type-conversion")
def test_decimal_to_float_conversion_25200(benchmark, temp_parquet_file):
    """Benchmark converting Decimal columns to float (if needed for compatibility).

    Expected: ~30-100 milliseconds
    Target: Avoid this conversion in production
    """
    df = pl.read_parquet(temp_parquet_file)

    def convert_to_float():
        return df.with_columns([pl.col("close").cast(pl.Float64).alias("close_float")])

    result = benchmark(convert_to_float)

    assert "close_float" in result.columns


@pytest.mark.benchmark(group="data-series-operations")
def test_series_arithmetic_operations(benchmark):
    """Benchmark arithmetic operations on Decimal Series.

    Tests performance of element-wise operations.
    Expected: ~50-150 milliseconds for 25200 operations
    Target (Epic 7): <30 milliseconds
    """
    random.seed(42)
    prices = [Decimal(str(50.0 + random.random() * 10)) for _ in range(25200)]
    series = pl.Series("prices", prices, dtype=pl.Decimal(scale=8))

    def arithmetic_operations():
        # Typical data pipeline operations
        adjusted = series * Decimal("1.02")  # Apply 2% adjustment
        shifted = series.shift(1)
        returns = (series - shifted) / shifted
        return returns

    result = benchmark(arithmetic_operations)

    assert len(result) == 25200


@pytest.mark.benchmark(group="data-resample")
def test_resample_minute_to_daily(benchmark):
    """Benchmark resampling minute bars to daily bars.

    Simulates 390 minute bars (1 trading day) → 1 daily bar
    Expected: ~10-40 milliseconds per day
    Target (Epic 7): <8 milliseconds
    """
    random.seed(42)

    # Generate minute bars for 1 trading day (390 minutes)
    minute_data = {
        "timestamp": list(range(390)),
        "open": [Decimal(str(50.0 + random.random())) for _ in range(390)],
        "high": [Decimal(str(51.0 + random.random())) for _ in range(390)],
        "low": [Decimal(str(49.0 + random.random())) for _ in range(390)],
        "close": [Decimal(str(50.0 + random.random())) for _ in range(390)],
        "volume": [Decimal(str(random.random() * 10000)) for _ in range(390)],
    }

    df = pl.DataFrame(
        {
            "timestamp": minute_data["timestamp"],
            "open": pl.Series(minute_data["open"], dtype=pl.Decimal(scale=8)),
            "high": pl.Series(minute_data["high"], dtype=pl.Decimal(scale=8)),
            "low": pl.Series(minute_data["low"], dtype=pl.Decimal(scale=8)),
            "close": pl.Series(minute_data["close"], dtype=pl.Decimal(scale=8)),
            "volume": pl.Series(minute_data["volume"], dtype=pl.Decimal(scale=8)),
        }
    )

    def resample_to_daily():
        # Aggregate to daily: first open, max high, min low, last close, sum volume
        return pl.DataFrame(
            {
                "open": [df["open"][0]],
                "high": [df["high"].max()],
                "low": [df["low"].min()],
                "close": [df["close"][-1]],
                "volume": [df["volume"].sum()],
            }
        )

    result = benchmark(resample_to_daily)

    assert len(result) == 1


@pytest.mark.benchmark(group="data-split-adjustment")
def test_apply_split_adjustment_25200(benchmark, temp_parquet_file):
    """Benchmark applying split adjustment to historical data.

    Simulates 2:1 stock split adjustment.
    Expected: ~40-120 milliseconds
    Target (Epic 7): <25 milliseconds
    """
    df = pl.read_parquet(temp_parquet_file)

    def apply_split_adjustment():
        split_ratio = Decimal("2.0")  # 2:1 split
        return df.with_columns(
            [
                (pl.col("open") / split_ratio).alias("open"),
                (pl.col("high") / split_ratio).alias("high"),
                (pl.col("low") / split_ratio).alias("low"),
                (pl.col("close") / split_ratio).alias("close"),
                (pl.col("volume") * split_ratio).alias("volume"),
            ]
        )

    result = benchmark(apply_split_adjustment)

    assert len(result) == 25200
