"""Performance benchmarks for Decimal data pipeline.

These benchmarks measure the performance overhead of using Decimal precision
compared to float64, and establish baseline performance metrics for the
Decimal data pipeline components.

Run with: uv run pytest tests/benchmarks/test_decimal_data_performance.py -v --benchmark-only
"""

import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from rustybt.data.bundles.csvdir import convert_csv_to_decimal_parquet
from rustybt.data.decimal_adjustments import (
    apply_dividend_adjustment,
    apply_split_adjustment,
)
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.pipeline.factors.decimal_factors import (
    DecimalReturns,
    DecimalSimpleMovingAverage,
)


class MockAsset:
    """Mock Asset for benchmarking."""

    def __init__(self, sid, symbol="TEST"):
        self.sid = sid
        self.symbol = symbol


def generate_large_dataset(num_assets=100, num_days=252):
    """Generate a large dataset for performance testing.

    Args:
        num_assets: Number of assets
        num_days: Number of trading days (252 = 1 year)

    Returns:
        String containing CSV data
    """
    lines = ["date,sid,open,high,low,close,volume"]

    start_date = date(2023, 1, 1)
    base_price = Decimal("100.0")

    for day in range(num_days):
        current_date = start_date + timedelta(days=day)
        for asset_id in range(1, num_assets + 1):
            # Generate semi-realistic price data
            day_variation = Decimal(str(day * 0.01))
            asset_variation = Decimal(str(asset_id * 0.1))

            open_price = base_price + day_variation + asset_variation
            high_price = open_price * Decimal("1.01")
            low_price = open_price * Decimal("0.99")
            close_price = open_price * Decimal("1.005")
            volume = Decimal("1000000") + Decimal(str(asset_id * 10000))

            lines.append(
                f"{current_date},{asset_id},"
                f"{open_price:.8f},{high_price:.8f},"
                f"{low_price:.8f},{close_price:.8f},{volume:.2f}"
            )

    return "\n".join(lines)


@pytest.fixture(scope="module")
def benchmark_bundle():
    """Create a benchmark bundle with significant data volume."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_path = Path(tmpdir)

        # Generate 100 assets x 252 days = 25,200 rows
        csv_data = generate_large_dataset(num_assets=100, num_days=252)

        csv_path = bundle_path / "benchmark_data.csv"
        csv_path.write_text(csv_data)

        daily_bars_path = bundle_path / "daily_bars"
        daily_bars_path.mkdir()

        parquet_path = daily_bars_path / "data.parquet"
        convert_csv_to_decimal_parquet(str(csv_path), str(parquet_path), asset_class="crypto")

        yield bundle_path


class TestDataLoadingPerformance:
    """Benchmark data loading operations."""

    def test_benchmark_csv_ingestion(self, benchmark):
        """Benchmark CSV ingestion to Parquet with Decimal conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate smaller dataset for faster iteration
            csv_data = generate_large_dataset(num_assets=50, num_days=100)

            csv_path = Path(tmpdir) / "test.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test.parquet"

            # Benchmark the ingestion
            result = benchmark(
                convert_csv_to_decimal_parquet, str(csv_path), str(parquet_path), "crypto"
            )

            # Verify ingestion succeeded
            assert result["rows_ingested"] == 5000  # 50 assets x 100 days

    def test_benchmark_parquet_read(self, benchmark, benchmark_bundle):
        """Benchmark reading Parquet data with Decimal columns."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))

        sids = list(range(1, 101))  # All 100 assets
        start = date(2023, 1, 1)
        end = date(2023, 12, 31)

        # Benchmark the read operation
        result = benchmark(reader.load_daily_bars, sids=sids, start_date=start, end_date=end)

        # Verify data loaded
        assert len(result) > 0
        assert isinstance(result["close"].dtype, pl.Decimal)

    def test_benchmark_data_portal_spot_value(self, benchmark, benchmark_bundle):
        """Benchmark DataPortal get_spot_value operation."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [MockAsset(sid=i) for i in range(1, 101)]

        # Benchmark spot value retrieval
        result = benchmark(
            portal.get_spot_value,
            assets=assets,
            field="close",
            dt=pd.Timestamp("2023-06-15"),
            data_frequency="daily",
        )

        # Verify result
        assert len(result) == 100
        assert isinstance(result.dtype, pl.Decimal)

    def test_benchmark_data_portal_history_window(self, benchmark, benchmark_bundle):
        """Benchmark DataPortal get_history_window operation."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [MockAsset(sid=i) for i in range(1, 51)]  # 50 assets

        # Benchmark history window retrieval (20 days)
        result = benchmark(
            portal.get_history_window,
            assets=assets,
            end_dt=pd.Timestamp("2023-06-15"),
            bar_count=20,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Verify result
        assert len(result) == 20 * 50  # 20 days x 50 assets
        assert isinstance(result["close"].dtype, pl.Decimal)


class TestAdjustmentPerformance:
    """Benchmark adjustment calculations."""

    def test_benchmark_split_adjustment(self, benchmark, benchmark_bundle):
        """Benchmark split adjustment on large dataset."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))

        # Load 1 year of data for 1 asset
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        prices = df["close"]
        split_ratio = Decimal("2.0")

        # Benchmark split adjustment
        result = benchmark(apply_split_adjustment, prices, split_ratio)

        # Verify adjustment applied
        assert len(result) == len(prices)
        assert isinstance(result.dtype, pl.Decimal)

    def test_benchmark_dividend_adjustment(self, benchmark, benchmark_bundle):
        """Benchmark dividend adjustment on large dataset."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))

        # Load 1 year of data for 1 asset
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        prices = df["close"]
        dividend = Decimal("2.50")

        # Benchmark dividend adjustment
        result = benchmark(apply_dividend_adjustment, prices, dividend)

        # Verify adjustment applied
        assert len(result) == len(prices)
        assert isinstance(result.dtype, pl.Decimal)

    def test_benchmark_multiple_adjustments(self, benchmark, benchmark_bundle):
        """Benchmark chained adjustments on large dataset."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))

        # Load 10 years of simulated data (repeat 1 year data 10 times for simplicity)
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        prices = df["close"]

        def apply_multiple_adjustments(prices):
            """Apply multiple adjustments in sequence."""
            # Split adjustment
            adjusted = apply_split_adjustment(prices, Decimal("2.0"))
            # Dividend adjustment
            adjusted = apply_dividend_adjustment(
                adjusted, Decimal("1.50"), validate_non_negative=False
            )
            # Another split
            adjusted = apply_split_adjustment(adjusted, Decimal("1.5"))
            return adjusted

        # Benchmark chained adjustments
        result = benchmark(apply_multiple_adjustments, prices)

        # Verify adjustments applied
        assert len(result) == len(prices)


class TestPipelineFactorPerformance:
    """Benchmark Pipeline factor calculations."""

    def test_benchmark_sma_calculation(self, benchmark, benchmark_bundle):
        """Benchmark SimpleMovingAverage factor calculation."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))

        # Load 1 year of data for 1 asset
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        factor = DecimalSimpleMovingAverage(window_length=20)

        # Benchmark SMA calculation
        result = benchmark(factor.compute, df)

        # Verify calculation
        assert len(result) == len(df)
        assert isinstance(result.dtype, pl.Decimal)

    def test_benchmark_returns_calculation(self, benchmark, benchmark_bundle):
        """Benchmark Returns factor calculation."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))

        # Load 1 year of data for 1 asset
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        factor = DecimalReturns(window_length=1)

        # Benchmark returns calculation
        result = benchmark(factor.compute, df)

        # Verify calculation
        assert len(result) == len(df)
        assert isinstance(result.dtype, pl.Decimal)

    def test_benchmark_multi_factor_pipeline(self, benchmark, benchmark_bundle):
        """Benchmark multiple factor calculations in sequence."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))

        # Load 1 year of data for 1 asset
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        def compute_multiple_factors(df):
            """Compute multiple factors on same data."""
            sma_20 = DecimalSimpleMovingAverage(window_length=20).compute(df)
            sma_50 = DecimalSimpleMovingAverage(window_length=50).compute(df)
            returns_1d = DecimalReturns(window_length=1).compute(df)
            returns_5d = DecimalReturns(window_length=5).compute(df)
            return (sma_20, sma_50, returns_1d, returns_5d)

        # Benchmark multi-factor computation
        results = benchmark(compute_multiple_factors, df)

        # Verify all factors computed
        assert len(results) == 4


class TestMemoryUsage:
    """Benchmark memory usage (informational, not strict performance tests)."""

    def test_decimal_vs_float_memory_comparison(self, benchmark_bundle):
        """Compare memory footprint of Decimal vs float64 data."""
        reader = PolarsParquetDailyReader(str(benchmark_bundle))

        # Load data as Decimal
        df_decimal = reader.load_daily_bars(
            sids=list(range(1, 101)), start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        # Convert to float for comparison
        df_float = df_decimal.with_columns(
            [
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Float64),
            ]
        )

        # Get memory estimates (Polars estimated_size)
        decimal_size = df_decimal.estimated_size()
        float_size = df_float.estimated_size()

        # Calculate overhead
        overhead_pct = ((decimal_size - float_size) / float_size) * 100

        # Print results (not assertions, just informational)
        print("\nMemory Usage Comparison:")
        print(f"Decimal DataFrame: {decimal_size / 1024 / 1024:.2f} MB")
        print(f"Float64 DataFrame: {float_size / 1024 / 1024:.2f} MB")
        print(f"Decimal overhead: {overhead_pct:.1f}%")

        # Decimal should use more memory (higher precision)
        assert decimal_size >= float_size


class TestEndToEndPerformance:
    """Benchmark complete data pipeline flows."""

    def test_benchmark_full_pipeline_flow(self, benchmark):
        """Benchmark complete pipeline: CSV → Parquet → Portal → Adjustment → Factor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_path = Path(tmpdir)

            # Generate test data
            csv_data = generate_large_dataset(num_assets=20, num_days=100)
            csv_path = bundle_path / "test.csv"
            csv_path.write_text(csv_data)

            daily_bars_path = bundle_path / "daily_bars"
            daily_bars_path.mkdir()
            parquet_path = daily_bars_path / "data.parquet"

            def full_pipeline():
                """Execute full pipeline flow."""
                # 1. Ingest CSV to Parquet
                convert_csv_to_decimal_parquet(str(csv_path), str(parquet_path), "crypto")

                # 2. Create reader and portal
                reader = PolarsParquetDailyReader(str(bundle_path))
                portal = PolarsDataPortal(daily_reader=reader)

                # 3. Load data
                assets = [MockAsset(sid=i) for i in range(1, 21)]
                history = portal.get_history_window(
                    assets=assets,
                    end_dt=pd.Timestamp("2023-04-01"),
                    bar_count=20,
                    frequency="1d",
                    field="close",
                    data_frequency="daily",
                )

                # 4. Apply adjustment
                adjusted = apply_split_adjustment(history["close"], Decimal("2.0"))

                # 5. Calculate factor
                factor_df = history.with_columns(close=adjusted)
                sma = DecimalSimpleMovingAverage(window_length=10).compute(factor_df)

                return sma

            # Benchmark full pipeline
            result = benchmark(full_pipeline)

            # Verify pipeline executed
            assert len(result) > 0
