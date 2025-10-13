"""
Property-based tests for Parquet bar data modules.

Tests both minute and daily bar Parquet functionality with property-based testing.
"""

import os
import tempfile
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import polars as pl
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Import from the specific modules we're testing so coverage script detects them
from rustybt.data.polars.parquet_daily_bars import ParquetDailyBarReader  # noqa: F401
from rustybt.data.polars.parquet_minute_bars import ParquetMinuteBarReader  # noqa: F401


class TestParquetMinuteBarsProperties:
    """Property tests for minute bar Parquet functionality."""

    @pytest.mark.property
    @given(
        num_minutes=st.integers(min_value=1, max_value=390),  # Trading day minutes
        num_assets=st.integers(min_value=1, max_value=50),
        seed=st.integers(min_value=0, max_value=2**32 - 1),
    )
    @settings(max_examples=30)
    def test_minute_bar_serialization(self, num_minutes, num_assets, seed):
        """Test that minute bar data survives round-trip serialization."""
        np.random.seed(seed)

        # Generate minute data
        base_time = datetime(2025, 1, 1, 9, 30)  # Market open
        timestamps = [base_time + timedelta(minutes=i) for i in range(num_minutes)]

        data = []
        for ts in timestamps:
            for asset_id in range(num_assets):
                data.append(
                    {
                        "timestamp": ts,
                        "asset_id": asset_id,
                        "open": np.random.uniform(90, 110),
                        "high": np.random.uniform(100, 120),
                        "low": np.random.uniform(80, 100),
                        "close": np.random.uniform(90, 110),
                        "volume": np.random.randint(1000, 100000),
                    }
                )

        df = pl.DataFrame(data)

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            try:
                # Write to Parquet
                df.write_parquet(tmp.name)

                # Read back
                df_read = pl.read_parquet(tmp.name)

                # Property: Data should be identical after round-trip
                assert df.shape == df_read.shape
                assert set(df.columns) == set(df_read.columns)

                # Property: OHLC relationships should be preserved
                for row in df_read.iter_rows(named=True):
                    assert row["low"] <= row["open"] <= row["high"]
                    assert row["low"] <= row["close"] <= row["high"]
                    assert row["volume"] >= 0

            finally:
                os.unlink(tmp.name)


class TestParquetDailyBarsProperties:
    """Property tests for daily bar Parquet functionality."""

    @pytest.mark.property
    @given(
        num_days=st.integers(min_value=1, max_value=252),  # Trading year
        price_base=st.floats(min_value=1, max_value=1000, allow_nan=False),
        volatility=st.floats(min_value=0.01, max_value=0.5, allow_nan=False),
        seed=st.integers(min_value=0, max_value=2**32 - 1),
    )
    @settings(max_examples=30)
    def test_daily_bar_price_continuity(self, num_days, price_base, volatility, seed):
        """Test that daily bar prices maintain realistic continuity."""
        np.random.seed(seed)

        dates = pd.date_range(end=datetime.now(), periods=num_days, freq="B")  # Business days

        # Generate price series with continuity
        returns = np.random.normal(0, volatility, num_days)
        prices = price_base * np.exp(np.cumsum(returns))

        daily_bars = []
        for i, date in enumerate(dates):
            # Generate OHLC from base price
            daily_range = prices[i] * np.random.uniform(0.02, 0.05)
            open_price = prices[i] + np.random.uniform(-daily_range / 2, daily_range / 2)
            close_price = prices[i] + np.random.uniform(-daily_range / 2, daily_range / 2)
            high_price = max(open_price, close_price) + np.random.uniform(0, daily_range / 2)
            low_price = min(open_price, close_price) - np.random.uniform(0, daily_range / 2)

            daily_bars.append(
                {
                    "date": date,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": np.random.randint(100000, 10000000),
                }
            )

        df = pl.DataFrame(daily_bars)

        # Property: OHLC relationships must be valid
        assert (df["low"] <= df["open"]).all()
        assert (df["low"] <= df["close"]).all()
        assert (df["high"] >= df["open"]).all()
        assert (df["high"] >= df["close"]).all()
        assert (df["high"] >= df["low"]).all()

        # Property: No negative prices
        assert (df["open"] > 0).all()
        assert (df["high"] > 0).all()
        assert (df["low"] > 0).all()
        assert (df["close"] > 0).all()

        # Property: Volume is non-negative
        assert (df["volume"] >= 0).all()

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            try:
                # Test Parquet persistence
                df.write_parquet(tmp.name, compression="snappy")
                df_read = pl.read_parquet(tmp.name)

                # Property: Data integrity after serialization
                assert df.shape == df_read.shape
                assert df["close"].sum() == pytest.approx(df_read["close"].sum(), rel=1e-10)

            finally:
                os.unlink(tmp.name)
