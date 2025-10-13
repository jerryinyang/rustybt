"""Simple performance tests for Decimal data pipeline.

These tests verify that operations complete within reasonable time limits
and provide basic performance metrics without requiring pytest-benchmark.
"""

import tempfile
import time
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
    """Mock Asset for performance testing."""

    def __init__(self, sid, symbol="TEST"):
        self.sid = sid
        self.symbol = symbol


def generate_test_dataset(num_assets=100, num_days=252):
    """Generate test dataset for performance testing."""
    lines = ["date,sid,open,high,low,close,volume"]

    start_date = date(2023, 1, 1)
    base_price = Decimal("100.0")

    for day in range(num_days):
        current_date = start_date + timedelta(days=day)
        for asset_id in range(1, num_assets + 1):
            day_var = Decimal(str(day * 0.01))
            asset_var = Decimal(str(asset_id * 0.1))

            open_p = base_price + day_var + asset_var
            high_p = open_p * Decimal("1.01")
            low_p = open_p * Decimal("0.99")
            close_p = open_p * Decimal("1.005")
            volume = Decimal("1000000") + Decimal(str(asset_id * 10000))

            lines.append(
                f"{current_date},{asset_id},"
                f"{open_p:.8f},{high_p:.8f},"
                f"{low_p:.8f},{close_p:.8f},{volume:.2f}"
            )

    return "\n".join(lines)


@pytest.fixture
def small_bundle():
    """Create a small test bundle (50 assets, 100 days = 5K rows)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_path = Path(tmpdir)
        csv_data = generate_test_dataset(num_assets=50, num_days=100)

        csv_path = bundle_path / "test.csv"
        csv_path.write_text(csv_data)

        daily_bars_path = bundle_path / "daily_bars"
        daily_bars_path.mkdir()

        parquet_path = daily_bars_path / "data.parquet"
        convert_csv_to_decimal_parquet(str(csv_path), str(parquet_path), "crypto")

        yield bundle_path


@pytest.fixture
def large_bundle():
    """Create a larger test bundle (100 assets, 252 days = 25K rows)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_path = Path(tmpdir)
        csv_data = generate_test_dataset(num_assets=100, num_days=252)

        csv_path = bundle_path / "test.csv"
        csv_path.write_text(csv_data)

        daily_bars_path = bundle_path / "daily_bars"
        daily_bars_path.mkdir()

        parquet_path = daily_bars_path / "data.parquet"
        convert_csv_to_decimal_parquet(str(csv_path), str(parquet_path), "crypto")

        yield bundle_path


class TestDataLoadingPerformance:
    """Test data loading performance."""

    def test_csv_ingestion_completes_quickly(self):
        """Test that CSV ingestion completes in reasonable time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_data = generate_test_dataset(num_assets=50, num_days=100)
            csv_path = Path(tmpdir) / "test.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test.parquet"

            start = time.time()
            result = convert_csv_to_decimal_parquet(str(csv_path), str(parquet_path), "crypto")
            elapsed = time.time() - start

            print(f"\nCSV Ingestion (5K rows): {elapsed:.3f}s")
            assert result["rows_ingested"] == 5000
            assert elapsed < 5.0  # Should complete in under 5 seconds

    def test_parquet_read_completes_quickly(self, large_bundle):
        """Test that Parquet reading completes in reasonable time."""
        reader = PolarsParquetDailyReader(str(large_bundle))

        start = time.time()
        df = reader.load_daily_bars(
            sids=list(range(1, 101)), start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )
        elapsed = time.time() - start

        print(f"\nParquet Read (25K rows): {elapsed:.3f}s")
        assert len(df) > 0
        assert elapsed < 2.0  # Should complete in under 2 seconds

    def test_data_portal_spot_value_performance(self, small_bundle):
        """Test DataPortal spot value retrieval performance."""
        reader = PolarsParquetDailyReader(str(small_bundle))
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [MockAsset(sid=i) for i in range(1, 51)]

        start = time.time()
        prices = portal.get_spot_value(
            assets=assets, field="close", dt=pd.Timestamp("2023-02-15"), data_frequency="daily"
        )
        elapsed = time.time() - start

        print(f"\nDataPortal Spot Value (50 assets): {elapsed:.3f}s")
        assert len(prices) == 50
        assert elapsed < 1.0  # Should complete in under 1 second

    def test_data_portal_history_window_performance(self, small_bundle):
        """Test DataPortal history window performance."""
        reader = PolarsParquetDailyReader(str(small_bundle))
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [MockAsset(sid=i) for i in range(1, 51)]

        start = time.time()
        history = portal.get_history_window(
            assets=assets,
            end_dt=pd.Timestamp("2023-03-15"),
            bar_count=20,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )
        elapsed = time.time() - start

        print(f"\nDataPortal History Window (50 assets, 20 days): {elapsed:.3f}s")
        assert len(history) == 20 * 50
        assert elapsed < 1.0  # Should complete in under 1 second


class TestAdjustmentPerformance:
    """Test adjustment calculation performance."""

    def test_split_adjustment_performance(self, large_bundle):
        """Test split adjustment performance on large dataset."""
        reader = PolarsParquetDailyReader(str(large_bundle))
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        prices = df["close"]
        split_ratio = Decimal("2.0")

        start = time.time()
        adjusted = apply_split_adjustment(prices, split_ratio)
        elapsed = time.time() - start

        print(f"\nSplit Adjustment (252 rows): {elapsed:.4f}s")
        assert len(adjusted) == len(prices)
        assert elapsed < 0.1  # Should be very fast

    def test_dividend_adjustment_performance(self, large_bundle):
        """Test dividend adjustment performance on large dataset."""
        reader = PolarsParquetDailyReader(str(large_bundle))
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        prices = df["close"]
        dividend = Decimal("2.50")

        start = time.time()
        adjusted = apply_dividend_adjustment(prices, dividend)
        elapsed = time.time() - start

        print(f"\nDividend Adjustment (252 rows): {elapsed:.4f}s")
        assert len(adjusted) == len(prices)
        assert elapsed < 0.1  # Should be very fast

    def test_chained_adjustments_performance(self, large_bundle):
        """Test chained adjustments performance."""
        reader = PolarsParquetDailyReader(str(large_bundle))
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        prices = df["close"]

        start = time.time()
        # Apply multiple adjustments
        adjusted = apply_split_adjustment(prices, Decimal("2.0"))
        adjusted = apply_dividend_adjustment(adjusted, Decimal("1.50"), validate_non_negative=False)
        adjusted = apply_split_adjustment(adjusted, Decimal("1.5"))
        elapsed = time.time() - start

        print(f"\nChained Adjustments (3 operations, 252 rows): {elapsed:.4f}s")
        assert len(adjusted) == len(prices)
        assert elapsed < 0.2  # Should complete quickly


class TestPipelineFactorPerformance:
    """Test Pipeline factor calculation performance."""

    def test_sma_calculation_performance(self, large_bundle):
        """Test SMA calculation performance."""
        reader = PolarsParquetDailyReader(str(large_bundle))
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        factor = DecimalSimpleMovingAverage(window_length=20)

        start = time.time()
        sma = factor.compute(df)
        elapsed = time.time() - start

        print(f"\nSMA Calculation (252 rows, window=20): {elapsed:.4f}s")
        assert len(sma) == len(df)
        assert elapsed < 0.2  # Should be fast

    def test_returns_calculation_performance(self, large_bundle):
        """Test returns calculation performance."""
        reader = PolarsParquetDailyReader(str(large_bundle))
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        factor = DecimalReturns(window_length=1)

        start = time.time()
        returns = factor.compute(df)
        elapsed = time.time() - start

        print(f"\nReturns Calculation (252 rows): {elapsed:.4f}s")
        assert len(returns) == len(df)
        assert elapsed < 0.2  # Should be fast

    def test_multi_factor_performance(self, large_bundle):
        """Test multiple factor calculations performance."""
        reader = PolarsParquetDailyReader(str(large_bundle))
        df = reader.load_daily_bars(
            sids=[1], start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        start = time.time()
        # Calculate multiple factors
        sma_20 = DecimalSimpleMovingAverage(window_length=20).compute(df)
        DecimalSimpleMovingAverage(window_length=50).compute(df)
        DecimalReturns(window_length=1).compute(df)
        DecimalReturns(window_length=5).compute(df)
        elapsed = time.time() - start

        print(f"\nMulti-Factor Calculation (4 factors, 252 rows): {elapsed:.4f}s")
        assert len(sma_20) == len(df)
        assert elapsed < 1.0  # Should complete in under 1 second


class TestEndToEndPerformance:
    """Test end-to-end pipeline performance."""

    def test_full_pipeline_performance(self):
        """Test complete pipeline flow performance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_path = Path(tmpdir)

            # Generate test data
            csv_data = generate_test_dataset(num_assets=20, num_days=100)
            csv_path = bundle_path / "test.csv"
            csv_path.write_text(csv_data)

            daily_bars_path = bundle_path / "daily_bars"
            daily_bars_path.mkdir()
            parquet_path = daily_bars_path / "data.parquet"

            start = time.time()

            # 1. Ingest
            convert_csv_to_decimal_parquet(str(csv_path), str(parquet_path), "crypto")

            # 2. Create reader and portal
            reader = PolarsParquetDailyReader(str(bundle_path))
            portal = PolarsDataPortal(daily_reader=reader)

            # 3. Load data
            assets = [MockAsset(sid=i) for i in range(1, 21)]
            history = portal.get_history_window(
                assets=assets,
                end_dt=pd.Timestamp("2023-03-15"),
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

            elapsed = time.time() - start

            print(f"\nFull Pipeline (CSV→Portal→Adjustment→Factor): {elapsed:.3f}s")
            assert len(sma) > 0
            assert elapsed < 5.0  # Should complete in under 5 seconds


class TestMemoryUsage:
    """Test memory usage characteristics."""

    def test_decimal_vs_float_memory(self, large_bundle):
        """Compare Decimal vs float64 memory footprint."""
        reader = PolarsParquetDailyReader(str(large_bundle))

        # Load as Decimal
        df_decimal = reader.load_daily_bars(
            sids=list(range(1, 101)), start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        # Convert to float64
        df_float = df_decimal.with_columns(
            [
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Float64),
            ]
        )

        decimal_size = df_decimal.estimated_size()
        float_size = df_float.estimated_size()
        overhead_pct = ((decimal_size - float_size) / float_size) * 100

        print("\nMemory Usage:")
        print(f"  Decimal: {decimal_size / 1024 / 1024:.2f} MB")
        print(f"  Float64: {float_size / 1024 / 1024:.2f} MB")
        print(f"  Overhead: {overhead_pct:.1f}%")

        # Decimal uses more memory (higher precision)
        assert decimal_size >= float_size
        # But overhead should be reasonable (< 300%)
        assert overhead_pct < 300
