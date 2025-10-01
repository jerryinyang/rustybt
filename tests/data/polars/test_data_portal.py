"""Tests for PolarsDataPortal."""

import pytest
import polars as pl
import pandas as pd
from decimal import Decimal
from pathlib import Path
import tempfile
from datetime import date

from rustybt.data.polars.data_portal import (
    PolarsDataPortal,
    NoDataAvailableError,
    LookaheadError,
)
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.assets import Equity
from rustybt.assets.exchange_info import ExchangeInfo


@pytest.fixture
def sample_daily_data():
    """Create sample daily OHLCV data for testing."""
    from rustybt.data.polars.parquet_schema import DAILY_BARS_SCHEMA

    return pl.DataFrame({
        "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)] * 2,
        "sid": [1, 1, 1, 2, 2, 2],
        "open": [Decimal("100.00"), Decimal("102.00"), Decimal("104.00"),
                 Decimal("50.00"), Decimal("51.00"), Decimal("52.00")],
        "high": [Decimal("101.00"), Decimal("103.00"), Decimal("105.00"),
                 Decimal("51.00"), Decimal("52.00"), Decimal("53.00")],
        "low": [Decimal("99.00"), Decimal("101.00"), Decimal("103.00"),
                Decimal("49.00"), Decimal("50.00"), Decimal("51.00")],
        "close": [Decimal("100.50"), Decimal("102.50"), Decimal("104.50"),
                  Decimal("50.50"), Decimal("51.50"), Decimal("52.50")],
        "volume": [Decimal("1000000"), Decimal("1500000"), Decimal("1200000"),
                   Decimal("500000"), Decimal("600000"), Decimal("550000")],
    }, schema=DAILY_BARS_SCHEMA)


@pytest.fixture
def temp_bundle_with_data(sample_daily_data):
    """Create temporary bundle directory with sample data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_path = Path(tmpdir)

        # Create daily_bars subdirectory (PolarsParquetDailyReader expects this)
        daily_bars_path = bundle_path / "daily_bars"
        daily_bars_path.mkdir(parents=True, exist_ok=True)

        # Write data to parquet in the daily_bars directory
        parquet_path = daily_bars_path / "data.parquet"
        sample_daily_data.write_parquet(parquet_path, compression="snappy")

        yield str(bundle_path)


@pytest.fixture
def test_assets():
    """Create test assets."""
    exchange_info = ExchangeInfo("TEST", "Test Exchange", "US")
    return [
        Equity(1, exchange_info=exchange_info, symbol="AAPL"),
        Equity(2, exchange_info=exchange_info, symbol="GOOG"),
    ]


class TestPolarsDataPortal:
    """Test PolarsDataPortal functionality."""

    def test_init_requires_at_least_one_reader(self):
        """Test that initialization requires at least one reader."""
        with pytest.raises(ValueError, match="At least one of daily_reader"):
            PolarsDataPortal()

    def test_init_with_daily_reader(self, temp_bundle_with_data):
        """Test initialization with daily reader."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(daily_reader=reader)

        assert portal.daily_reader is not None
        assert portal.minute_reader is None

    def test_get_spot_value_returns_decimal_series(self, temp_bundle_with_data, test_assets):
        """Test get_spot_value returns Decimal Series."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(daily_reader=reader)

        # Get spot value for first asset
        assets = [test_assets[0]]

        # Get spot value
        prices = portal.get_spot_value(
            assets=assets,
            field="close",
            dt=pd.Timestamp("2023-01-01"),
            data_frequency="daily"
        )

        # Verify result
        assert isinstance(prices, pl.Series)
        assert prices.dtype == pl.Decimal(precision=18, scale=8)
        assert prices[0] == Decimal("100.50")

    def test_get_spot_value_validates_field(self, temp_bundle_with_data, test_assets):
        """Test get_spot_value validates field name."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [test_assets[0]]

        with pytest.raises(ValueError, match="Invalid field"):
            portal.get_spot_value(
                assets=assets,
                field="invalid_field",
                dt=pd.Timestamp("2023-01-01"),
                data_frequency="daily"
            )

    def test_get_spot_value_validates_frequency(self, temp_bundle_with_data, test_assets):
        """Test get_spot_value validates frequency."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [test_assets[0]]

        with pytest.raises(ValueError, match="Unsupported frequency"):
            portal.get_spot_value(
                assets=assets,
                field="close",
                dt=pd.Timestamp("2023-01-01"),
                data_frequency="hourly"
            )

    def test_get_spot_value_prevents_lookahead(self, temp_bundle_with_data, test_assets):
        """Test get_spot_value prevents lookahead bias."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(
            daily_reader=reader,
            current_simulation_time=pd.Timestamp("2023-01-01")
        )

        assets = [test_assets[0]]

        # Attempting to access future data should raise LookaheadError
        with pytest.raises(LookaheadError, match="Attempted to access future data"):
            portal.get_spot_value(
                assets=assets,
                field="close",
                dt=pd.Timestamp("2023-01-02"),
                data_frequency="daily"
            )

    def test_get_spot_value_allows_current_time(self, temp_bundle_with_data, test_assets):
        """Test get_spot_value allows access to current simulation time."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(
            daily_reader=reader,
            current_simulation_time=pd.Timestamp("2023-01-01")
        )

        assets = [test_assets[0]]

        # Accessing current time should succeed
        prices = portal.get_spot_value(
            assets=assets,
            field="close",
            dt=pd.Timestamp("2023-01-01"),
            data_frequency="daily"
        )

        assert prices[0] == Decimal("100.50")

    def test_get_spot_value_handles_missing_data(self, temp_bundle_with_data, test_assets):
        """Test get_spot_value handles missing data gracefully."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [test_assets[0]]

        # Requesting data for a date that doesn't exist
        with pytest.raises(NoDataAvailableError, match="No data found"):
            portal.get_spot_value(
                assets=assets,
                field="close",
                dt=pd.Timestamp("2025-01-01"),
                data_frequency="daily"
            )

    def test_get_spot_value_multiple_assets(self, temp_bundle_with_data, test_assets):
        """Test get_spot_value with multiple assets."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(daily_reader=reader)

        # Use both test assets
        assets = test_assets

        prices = portal.get_spot_value(
            assets=assets,
            field="close",
            dt=pd.Timestamp("2023-01-01"),
            data_frequency="daily"
        )

        assert len(prices) == 2
        assert prices[0] == Decimal("100.50")
        assert prices[1] == Decimal("50.50")

    def test_get_history_window_returns_dataframe(self, temp_bundle_with_data, test_assets):
        """Test get_history_window returns Polars DataFrame."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [test_assets[0]]

        # Get 2-day history window
        df = portal.get_history_window(
            assets=assets,
            end_dt=pd.Timestamp("2023-01-02"),
            bar_count=2,
            frequency="1d",
            field="close",
            data_frequency="daily"
        )

        # Verify result
        assert isinstance(df, pl.DataFrame)
        assert "date" in df.columns
        assert "sid" in df.columns
        assert "close" in df.columns
        assert df["close"].dtype == pl.Decimal(precision=18, scale=8)

    def test_get_history_window_returns_correct_bar_count(self, temp_bundle_with_data, test_assets):
        """Test get_history_window returns correct number of bars."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(daily_reader=reader)

        assets = [test_assets[0]]

        # Get 2-day history window
        df = portal.get_history_window(
            assets=assets,
            end_dt=pd.Timestamp("2023-01-03"),
            bar_count=2,
            frequency="1d",
            field="close",
            data_frequency="daily"
        )

        # Should return 2 bars for 1 asset
        assert len(df) == 2

        # Verify the values are the last 2 days
        closes = df.sort("date")["close"].to_list()
        assert closes == [Decimal("102.50"), Decimal("104.50")]

    def test_get_history_window_prevents_lookahead(self, temp_bundle_with_data, test_assets):
        """Test get_history_window prevents lookahead bias."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(
            daily_reader=reader,
            current_simulation_time=pd.Timestamp("2023-01-01")
        )

        assets = [test_assets[0]]

        # Attempting to access future data should raise LookaheadError
        with pytest.raises(LookaheadError, match="Attempted to access future data"):
            portal.get_history_window(
                assets=assets,
                end_dt=pd.Timestamp("2023-01-02"),
                bar_count=2,
                frequency="1d",
                field="close",
                data_frequency="daily"
            )

    def test_set_simulation_time_updates_current_time(self, temp_bundle_with_data, test_assets):
        """Test set_simulation_time updates current simulation time."""
        reader = PolarsParquetDailyReader(temp_bundle_with_data)
        portal = PolarsDataPortal(
            daily_reader=reader,
            current_simulation_time=pd.Timestamp("2023-01-01")
        )

        # Initially, can't access 2023-01-02
        assets = [test_assets[0]]
        with pytest.raises(LookaheadError):
            portal.get_spot_value(
                assets=assets,
                field="close",
                dt=pd.Timestamp("2023-01-02"),
                data_frequency="daily"
            )

        # Update simulation time
        portal.set_simulation_time(pd.Timestamp("2023-01-02"))

        # Now can access 2023-01-02
        prices = portal.get_spot_value(
            assets=assets,
            field="close",
            dt=pd.Timestamp("2023-01-02"),
            data_frequency="daily"
        )
        assert prices[0] == Decimal("102.50")
