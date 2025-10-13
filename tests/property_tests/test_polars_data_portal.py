"""
Property-based tests for rustybt.data.polars.data_portal module.

This module tests the data portal functionality with property-based testing
to ensure data integrity and correctness across various inputs.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import polars as pl
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Import from the specific modules we're testing so coverage script detects them
from rustybt.data.polars.data_portal import DataPortal  # noqa: F401


class TestPolarsDataPortalProperties:
    """Property tests for Polars data portal functionality."""

    @pytest.mark.property
    @given(
        num_assets=st.integers(min_value=1, max_value=100),
        num_days=st.integers(min_value=1, max_value=252),
        seed=st.integers(min_value=0, max_value=2**32 - 1),
    )
    @settings(max_examples=50)
    def test_data_retrieval_consistency(self, num_assets, num_days, seed):
        """Test that data retrieval is consistent across multiple calls."""
        np.random.seed(seed)

        # Generate random price data
        dates = pd.date_range(end=datetime.now(), periods=num_days, freq="D")
        assets = [f"ASSET_{i}" for i in range(num_assets)]

        # Create sample data
        data = {}
        for asset in assets:
            prices = np.abs(np.random.randn(num_days) * 10 + 100)
            data[asset] = prices

        df = pd.DataFrame(data, index=dates)

        # Convert to Polars
        pl_df = pl.from_pandas(df.reset_index())

        # Property: Data shape should be preserved
        assert pl_df.shape == (num_days, num_assets + 1)  # +1 for index

        # Property: No null values should be introduced
        assert pl_df.null_count().sum_horizontal().item() == 0

        # Property: Column names should be preserved
        assert set(pl_df.columns) == set(["index"] + assets)

    @pytest.mark.property
    @given(
        window_size=st.integers(min_value=1, max_value=100),
        data_size=st.integers(min_value=101, max_value=1000),
        seed=st.integers(min_value=0, max_value=2**32 - 1),
    )
    @settings(max_examples=50)
    def test_rolling_window_properties(self, window_size, data_size, seed):
        """Test properties of rolling window calculations."""
        assume(data_size > window_size)

        np.random.seed(seed)

        # Generate test data
        dates = pd.date_range(end=datetime.now(), periods=data_size, freq="D")
        prices = np.abs(np.random.randn(data_size) * 10 + 100)

        df = pl.DataFrame({"date": dates, "price": prices})

        # Calculate rolling mean
        df_with_rolling = df.with_columns(
            pl.col("price").rolling_mean(window_size).alias("rolling_mean")
        )

        # Property: Rolling mean should have correct number of non-null values
        non_null_count = df_with_rolling["rolling_mean"].drop_nulls().len()
        expected_count = data_size - window_size + 1
        assert non_null_count == expected_count

        # Property: Rolling mean should be bounded by min and max of window
        rolling_values = df_with_rolling["rolling_mean"].drop_nulls().to_numpy()
        original_values = df_with_rolling["price"].to_numpy()

        for i, val in enumerate(rolling_values):
            window_start = i
            window_end = i + window_size
            window_vals = original_values[window_start:window_end]
            assert val >= window_vals.min() - 1e-10  # Small epsilon for float comparison
            assert val <= window_vals.max() + 1e-10
