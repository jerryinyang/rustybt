"""Integration tests for Decimal data pipeline.

Tests the complete data flow: CSV → Parquet → DataPortal → Adjustments → Factors

This test suite verifies that Decimal precision is preserved through the entire
data pipeline, from ingestion to final calculations.
"""

import tempfile
from datetime import date
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
from rustybt.data.polars.data_portal import LookaheadError, PolarsDataPortal
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.pipeline.factors.decimal_factors import (
    DecimalAverageDollarVolume,
    DecimalLatestPrice,
    DecimalReturns,
    DecimalSimpleMovingAverage,
)


# Simple mock Asset class for testing
class MockAsset:
    """Mock Asset for testing without full Zipline dependencies."""

    def __init__(self, sid, symbol="TEST"):
        self.sid = sid
        self.symbol = symbol
        self.asset_name = symbol
        self.exchange = "TEST"


@pytest.fixture
def sample_csv_data():
    """Create sample CSV data with precise Decimal values."""
    return """date,sid,open,high,low,close,volume
2023-01-01,1,100.12345678,100.50000000,100.00000000,100.25000000,1000000.00
2023-01-02,1,100.25000000,101.00000000,100.10000000,100.75000000,1500000.00
2023-01-03,1,100.75000000,101.50000000,100.50000000,101.25000000,2000000.00
2023-01-04,1,101.25000000,102.00000000,101.00000000,101.50000000,1800000.00
2023-01-05,1,101.50000000,102.50000000,101.25000000,102.00000000,2200000.00
2023-01-01,2,50.11111111,50.25000000,50.00000000,50.15000000,500000.00
2023-01-02,2,50.15000000,50.50000000,50.05000000,50.35000000,750000.00
2023-01-03,2,50.35000000,50.75000000,50.25000000,50.60000000,1000000.00
2023-01-04,2,50.60000000,51.00000000,50.50000000,50.80000000,900000.00
2023-01-05,2,50.80000000,51.25000000,50.70000000,51.00000000,1100000.00
"""


@pytest.fixture
def test_bundle_dir(sample_csv_data):
    """Create a temporary bundle directory with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_path = Path(tmpdir)

        # Create CSV file
        csv_path = bundle_path / "test_data.csv"
        csv_path.write_text(sample_csv_data)

        # Create daily_bars directory structure
        daily_bars_path = bundle_path / "daily_bars"
        daily_bars_path.mkdir()

        # Ingest CSV to Parquet (use crypto for 8 decimal precision)
        parquet_path = daily_bars_path / "data.parquet"
        convert_csv_to_decimal_parquet(
            str(csv_path),
            str(parquet_path),
            asset_class="crypto",  # crypto has 8 decimal places
        )

        yield bundle_path


class TestCSVToParquetIngestion:
    """Test CSV ingestion to Parquet with Decimal preservation."""

    def test_csv_ingestion_preserves_precision(self, test_bundle_dir):
        """Test that CSV ingestion preserves Decimal precision."""
        parquet_path = test_bundle_dir / "daily_bars" / "data.parquet"

        # Read back the Parquet file
        df = pl.read_parquet(parquet_path)

        # Verify Decimal dtype
        assert isinstance(df["open"].dtype, pl.Decimal)
        assert isinstance(df["high"].dtype, pl.Decimal)
        assert isinstance(df["low"].dtype, pl.Decimal)
        assert isinstance(df["close"].dtype, pl.Decimal)
        assert isinstance(df["volume"].dtype, pl.Decimal)

        # Verify exact values preserved
        first_row = df.filter(pl.col("sid") == 1).filter(pl.col("date") == date(2023, 1, 1))
        assert first_row["open"][0] == Decimal("100.12345678")
        assert first_row["close"][0] == Decimal("100.25000000")

    def test_csv_ingestion_handles_multiple_assets(self, test_bundle_dir):
        """Test that multiple assets are ingested correctly."""
        parquet_path = test_bundle_dir / "daily_bars" / "data.parquet"
        df = pl.read_parquet(parquet_path)

        # Verify both assets present
        unique_sids = df["sid"].unique().sort()
        assert len(unique_sids) == 2
        assert unique_sids.to_list() == [1, 2]

        # Verify data for asset 2
        asset2_data = df.filter(pl.col("sid") == 2).filter(pl.col("date") == date(2023, 1, 1))
        assert asset2_data["close"][0] == Decimal("50.15000000")


class TestDataPortalIntegration:
    """Test PolarsDataPortal integration with Parquet readers."""

    def test_data_portal_loads_decimal_data(self, test_bundle_dir):
        """Test that DataPortal loads data with Decimal precision."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        # Create assets
        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get spot value
        prices = portal.get_spot_value(
            assets=[asset1], field="close", dt=pd.Timestamp("2023-01-01"), data_frequency="daily"
        )

        # Verify Decimal precision preserved
        assert prices[0] == Decimal("100.25000000")

    def test_data_portal_history_window(self, test_bundle_dir):
        """Test DataPortal history window returns Decimal data."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get history window
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-03"),
            bar_count=3,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Verify Decimal dtype
        assert isinstance(history["close"].dtype, pl.Decimal)

        # Verify values
        assert len(history) == 3
        assert history["close"][0] == Decimal("100.25000000")
        assert history["close"][1] == Decimal("100.75000000")
        assert history["close"][2] == Decimal("101.25000000")

    def test_data_portal_lookahead_prevention(self, test_bundle_dir):
        """Test that DataPortal prevents lookahead bias."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(
            daily_reader=reader, current_simulation_time=pd.Timestamp("2023-01-02")
        )

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Accessing future data should raise LookaheadError
        with pytest.raises(LookaheadError, match="future data"):
            portal.get_spot_value(
                assets=[asset1],
                field="close",
                dt=pd.Timestamp("2023-01-05"),
                data_frequency="daily",
            )

    def test_data_portal_multiple_assets(self, test_bundle_dir):
        """Test DataPortal with multiple assets."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")
        asset2 = MockAsset(sid=2, symbol="TEST2")

        # Get prices for both assets
        prices = portal.get_spot_value(
            assets=[asset1, asset2],
            field="close",
            dt=pd.Timestamp("2023-01-01"),
            data_frequency="daily",
        )

        # Verify both prices with Decimal precision
        assert prices[0] == Decimal("100.25000000")
        assert prices[1] == Decimal("50.15000000")


class TestAdjustmentIntegration:
    """Test adjustment calculations integrated with DataPortal."""

    def test_split_adjustment_on_portal_data(self, test_bundle_dir):
        """Test applying split adjustment to data from DataPortal."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get historical data
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-05"),
            bar_count=5,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Apply 2-for-1 split adjustment
        adjusted_prices = apply_split_adjustment(history["close"], Decimal("2.0"))

        # Verify prices are halved
        assert adjusted_prices[0] == Decimal("50.12500000")
        assert adjusted_prices[4] == Decimal("51.00000000")

    def test_dividend_adjustment_on_portal_data(self, test_bundle_dir):
        """Test applying dividend adjustment to data from DataPortal."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get historical data
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-05"),
            bar_count=5,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Apply $2.50 dividend adjustment
        adjusted_prices = apply_dividend_adjustment(history["close"], Decimal("2.50"))

        # Verify dividend subtracted
        assert adjusted_prices[0] == Decimal("97.75000000")
        assert adjusted_prices[4] == Decimal("99.50000000")


class TestPipelineFactorIntegration:
    """Test Pipeline factors integrated with DataPortal."""

    def test_latest_price_factor_with_portal_data(self, test_bundle_dir):
        """Test LatestPrice factor with DataPortal data."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get data via portal
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-05"),
            bar_count=1,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Compute factor
        factor = DecimalLatestPrice()
        result = factor.compute(history)

        # Verify result matches portal data
        assert result[0] == Decimal("102.00000000")

    def test_sma_factor_with_portal_data(self, test_bundle_dir):
        """Test SimpleMovingAverage factor with DataPortal data."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get historical data
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-05"),
            bar_count=5,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Compute 3-day SMA
        factor = DecimalSimpleMovingAverage(window_length=3)
        sma_result = factor.compute(history)

        # Last 3 prices: 101.25, 101.50, 102.00
        # Mean = 101.583333...
        assert sma_result[-1] > Decimal("101.58")
        assert sma_result[-1] < Decimal("101.59")

    def test_returns_factor_with_portal_data(self, test_bundle_dir):
        """Test Returns factor with DataPortal data."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get historical data
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-05"),
            bar_count=5,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Compute 1-day returns
        factor = DecimalReturns(window_length=1)
        returns = factor.compute(history)

        # Day 2 return: (100.75 / 100.25) - 1 ≈ 0.00498...
        assert returns[1] > Decimal("0.004")
        assert returns[1] < Decimal("0.005")

    def test_dollar_volume_factor_with_portal_data(self, test_bundle_dir):
        """Test AverageDollarVolume factor with DataPortal data."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get historical data (need both close and volume)
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-05"),
            bar_count=5,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Get volume separately and add to history
        volume_history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-05"),
            bar_count=5,
            frequency="1d",
            field="volume",
            data_frequency="daily",
        )

        # Combine close and volume
        combined = history.with_columns(volume=volume_history["volume"])

        # Compute 3-day average dollar volume
        factor = DecimalAverageDollarVolume(window_length=3)
        avg_dv = factor.compute(combined)

        # Should have meaningful dollar volume values
        assert avg_dv[-1] > Decimal("100000000")  # > 100M


class TestEndToEndPrecision:
    """Test end-to-end precision preservation through entire pipeline."""

    def test_precision_preserved_csv_to_factor(self, test_bundle_dir):
        """Test that precision is preserved from CSV ingestion to factor calculation."""
        # Setup pipeline
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)
        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get data through portal
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-01"),
            bar_count=1,
            frequency="1d",
            field="open",
            data_frequency="daily",
        )

        # Verify exact precision from original CSV
        assert history["open"][0] == Decimal("100.12345678")

    def test_adjustments_preserve_precision(self, test_bundle_dir):
        """Test that adjustments preserve Decimal precision."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)
        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Get data
        history = portal.get_history_window(
            assets=[asset1],
            end_dt=pd.Timestamp("2023-01-03"),
            bar_count=3,
            frequency="1d",
            field="close",
            data_frequency="daily",
        )

        # Apply split adjustment
        split_adjusted = apply_split_adjustment(history["close"], Decimal("2.0"))

        # Apply dividend adjustment to split-adjusted prices
        final_adjusted = apply_dividend_adjustment(split_adjusted, Decimal("1.00"))

        # Verify chained adjustments maintain precision
        # Original: 100.25, Split: 50.125, Dividend: 49.125
        assert final_adjusted[0] == Decimal("49.12500000")

    def test_multiple_assets_precision(self, test_bundle_dir):
        """Test precision preservation with multiple assets."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")
        asset2 = MockAsset(sid=2, symbol="TEST2")

        # Get data for multiple assets
        prices = portal.get_spot_value(
            assets=[asset1, asset2],
            field="open",
            dt=pd.Timestamp("2023-01-01"),
            data_frequency="daily",
        )

        # Verify exact precision for both assets
        assert prices[0] == Decimal("100.12345678")
        assert prices[1] == Decimal("50.11111111")


class TestEdgeCases:
    """Test edge cases and error handling in integration."""

    def test_missing_data_handling(self, test_bundle_dir):
        """Test handling of missing data."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Try to access data outside available range
        from rustybt.data.polars.data_portal import NoDataAvailableError

        with pytest.raises(NoDataAvailableError):
            portal.get_spot_value(
                assets=[asset1],
                field="close",
                dt=pd.Timestamp("2024-01-01"),  # Future date
                data_frequency="daily",
            )

    def test_invalid_field_handling(self, test_bundle_dir):
        """Test handling of invalid field names."""
        reader = PolarsParquetDailyReader(str(test_bundle_dir))
        portal = PolarsDataPortal(daily_reader=reader)

        asset1 = MockAsset(sid=1, symbol="TEST1")

        # Try invalid field
        with pytest.raises(ValueError, match="Invalid field"):
            portal.get_spot_value(
                assets=[asset1],
                field="invalid_field",
                dt=pd.Timestamp("2023-01-01"),
                data_frequency="daily",
            )
