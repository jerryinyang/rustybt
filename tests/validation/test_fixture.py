"""Tests for validation data fixture infrastructure.

Story X.2: Verifies that both rustybt and Backtrader receive identical
OHLCV data from the shared Parquet fixture, ensuring validation
comparisons detect real behavioral differences, not data artifacts.

Test Coverage:
    - AC-X2.1: Parquet schema validation
    - AC-X2.2: Deterministic generation (seeded random)
    - AC-X2.3: Cross-framework data identity
    - AC-X2.4: First/last bar and bar count alignment
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import polars as pl
import pytest

from rustybt.validation.generate_fixture import generate_fixture
from tests.validation.conftest import (
    get_fixture_info,
    load_fixture_for_backtrader,
    load_fixture_for_rustybt,
    verify_data_alignment,
)


class TestFixtureGeneration:
    """Tests for fixture generation (AC-X2.1, AC-X2.2)."""

    def test_generate_fixture_creates_valid_parquet(self, tmp_path: Path) -> None:
        """Test that generate_fixture creates a valid Parquet file."""
        output = tmp_path / "test_fixture.parquet"

        result = generate_fixture(
            output=output,
            assets=3,
            start="2023-01-01",
            end="2023-01-31",
            seed=42,
        )

        assert result.exists()
        assert result.suffix == ".parquet"

        # Verify can read with Polars
        df = pl.read_parquet(result)
        assert len(df) > 0

    def test_fixture_schema_matches_specification(self, tmp_path: Path) -> None:
        """Test fixture schema matches Story X.2 specification (AC-X2.1)."""
        output = tmp_path / "schema_test.parquet"
        generate_fixture(output=output, assets=2, start="2023-01-01", end="2023-01-10", seed=42)

        df = pl.read_parquet(output)
        schema = dict(df.schema)

        # Required columns
        assert "timestamp" in df.columns
        assert "asset" in df.columns
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns

        # Type checks
        assert schema["open"] == pl.Float64
        assert schema["high"] == pl.Float64
        assert schema["low"] == pl.Float64
        assert schema["close"] == pl.Float64
        assert schema["volume"] == pl.Int64
        assert schema["asset"] == pl.String

        # Timestamp should be datetime with UTC timezone
        assert df["timestamp"].dtype == pl.Datetime("us", "UTC") or df[
            "timestamp"
        ].dtype == pl.Datetime("ns", "UTC")

    def test_fixture_has_utc_timestamps(self, tmp_path: Path) -> None:
        """Test that timestamps are UTC timezone-aware (AC-X2.1)."""
        output = tmp_path / "utc_test.parquet"
        generate_fixture(output=output, assets=1, start="2023-01-01", end="2023-01-05", seed=42)

        df = pl.read_parquet(output)

        # Check timezone is UTC
        timestamp_dtype = df["timestamp"].dtype
        assert (
            timestamp_dtype.time_zone == "UTC"
        ), f"Expected UTC timezone, got {timestamp_dtype.time_zone}"

    def test_deterministic_generation_same_seed(self, tmp_path: Path) -> None:
        """Test that same seed produces identical data (AC-X2.2)."""
        output1 = tmp_path / "run1.parquet"
        output2 = tmp_path / "run2.parquet"

        # Generate with same seed
        generate_fixture(output=output1, assets=5, start="2023-01-01", end="2023-03-31", seed=12345)
        generate_fixture(output=output2, assets=5, start="2023-01-01", end="2023-03-31", seed=12345)

        df1 = pl.read_parquet(output1)
        df2 = pl.read_parquet(output2)

        # Should be identical
        assert len(df1) == len(df2)
        assert df1.equals(df2)

    def test_different_seeds_produce_different_data(self, tmp_path: Path) -> None:
        """Test that different seeds produce different data (AC-X2.2)."""
        output1 = tmp_path / "seed42.parquet"
        output2 = tmp_path / "seed99.parquet"

        generate_fixture(output=output1, assets=5, start="2023-01-01", end="2023-01-31", seed=42)
        generate_fixture(output=output2, assets=5, start="2023-01-01", end="2023-01-31", seed=99)

        df1 = pl.read_parquet(output1)
        df2 = pl.read_parquet(output2)

        # Same number of rows but different values
        assert len(df1) == len(df2)
        # Close prices should differ
        close1 = df1.filter(pl.col("asset") == df1["asset"].unique()[0])["close"].to_list()
        close2 = df2.filter(pl.col("asset") == df2["asset"].unique()[0])["close"].to_list()
        assert close1 != close2

    def test_ohlc_constraints_respected(self, tmp_path: Path) -> None:
        """Test that OHLCV data respects valid constraints."""
        output = tmp_path / "ohlc_test.parquet"
        generate_fixture(output=output, assets=10, start="2023-01-01", end="2023-06-30", seed=42)

        df = pl.read_parquet(output)

        # High >= max(open, close, low)
        assert (df["high"] >= df["open"]).all()
        assert (df["high"] >= df["close"]).all()
        assert (df["high"] >= df["low"]).all()

        # Low <= min(open, close, high)
        assert (df["low"] <= df["open"]).all()
        assert (df["low"] <= df["close"]).all()
        assert (df["low"] <= df["high"]).all()

        # Volume is positive
        assert (df["volume"] > 0).all()


class TestDataLoadingHelpers:
    """Tests for data loading helper functions."""

    @pytest.fixture
    def sample_fixture(self, tmp_path: Path) -> Path:
        """Create a sample fixture for testing."""
        output = tmp_path / "sample.parquet"
        generate_fixture(output=output, assets=3, start="2023-01-01", end="2023-02-28", seed=42)
        return output

    def test_load_fixture_for_rustybt_returns_polars_df(self, sample_fixture: Path) -> None:
        """Test that rustybt loader returns Polars DataFrame."""
        df = load_fixture_for_rustybt(sample_fixture)

        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

    def test_load_fixture_for_rustybt_preserves_schema(self, sample_fixture: Path) -> None:
        """Test that rustybt loader preserves data types."""
        df = load_fixture_for_rustybt(sample_fixture)

        assert df["open"].dtype == pl.Float64
        assert df["close"].dtype == pl.Float64
        assert df["volume"].dtype == pl.Int64

    def test_load_fixture_for_rustybt_filters_by_asset(self, sample_fixture: Path) -> None:
        """Test that rustybt loader can filter by asset."""
        df = load_fixture_for_rustybt(sample_fixture, asset="AAPL")

        if "asset" in df.columns:
            # If asset column is preserved, check it's filtered
            assets = df["asset"].unique().to_list()
            assert assets == ["AAPL"]

    def test_load_fixture_for_backtrader_returns_tuple(self, sample_fixture: Path) -> None:
        """Test that Backtrader loader returns (PandasData, asset_name) tuple."""
        result = load_fixture_for_backtrader(sample_fixture)

        assert isinstance(result, tuple)
        assert len(result) == 2

        data_feed, asset_name = result
        assert data_feed is not None
        assert asset_name is not None or isinstance(asset_name, str)

    def test_get_fixture_info_returns_metadata(self, sample_fixture: Path) -> None:
        """Test that get_fixture_info returns expected metadata."""
        info = get_fixture_info(sample_fixture)

        assert "assets" in info
        assert "bar_count" in info
        assert "first_timestamp" in info
        assert "last_timestamp" in info
        assert "columns" in info
        assert "schema" in info

        assert len(info["assets"]) == 3
        assert info["bar_count"] > 0


class TestDataAlignment:
    """Tests for cross-framework data alignment (AC-X2.3, AC-X2.4)."""

    @pytest.fixture
    def aligned_fixture(self, tmp_path: Path) -> Path:
        """Create a fixture for alignment testing."""
        output = tmp_path / "aligned.parquet"
        generate_fixture(output=output, assets=3, start="2023-01-01", end="2023-03-31", seed=42)
        return output

    def test_bar_count_matches(self, aligned_fixture: Path) -> None:
        """Test that bar count matches between frameworks (AC-X2.4)."""
        rustybt_df = load_fixture_for_rustybt(aligned_fixture, asset="AAPL")
        bt_data_feed, _ = load_fixture_for_backtrader(aligned_fixture, asset="AAPL")

        # Get Backtrader DataFrame
        bt_df = bt_data_feed.p.dataname

        assert len(rustybt_df) == len(
            bt_df
        ), f"Bar count mismatch: rustybt={len(rustybt_df)}, backtrader={len(bt_df)}"

    def test_first_bar_matches(self, aligned_fixture: Path) -> None:
        """Test that first bar matches between frameworks (AC-X2.4)."""
        rustybt_df = load_fixture_for_rustybt(aligned_fixture, asset="AAPL")
        bt_data_feed, _ = load_fixture_for_backtrader(aligned_fixture, asset="AAPL")

        bt_df = bt_data_feed.p.dataname.reset_index()

        # Compare first bar OHLCV
        for col in ["open", "high", "low", "close", "volume"]:
            rustybt_val = float(rustybt_df[col][0])
            bt_val = float(bt_df[col].iloc[0])
            assert (
                abs(rustybt_val - bt_val) < 1e-10
            ), f"First bar {col} mismatch: rustybt={rustybt_val}, backtrader={bt_val}"

    def test_last_bar_matches(self, aligned_fixture: Path) -> None:
        """Test that last bar matches between frameworks (AC-X2.4)."""
        rustybt_df = load_fixture_for_rustybt(aligned_fixture, asset="AAPL")
        bt_data_feed, _ = load_fixture_for_backtrader(aligned_fixture, asset="AAPL")

        bt_df = bt_data_feed.p.dataname.reset_index()

        # Compare last bar OHLCV
        for col in ["open", "high", "low", "close", "volume"]:
            rustybt_val = float(rustybt_df[col][-1])
            bt_val = float(bt_df[col].iloc[-1])
            assert (
                abs(rustybt_val - bt_val) < 1e-10
            ), f"Last bar {col} mismatch: rustybt={rustybt_val}, backtrader={bt_val}"

    def test_intermediate_samples_match(self, aligned_fixture: Path) -> None:
        """Test that intermediate bars match between frameworks (AC-X2.3)."""
        rustybt_df = load_fixture_for_rustybt(aligned_fixture, asset="AAPL")
        bt_data_feed, _ = load_fixture_for_backtrader(aligned_fixture, asset="AAPL")

        bt_df = bt_data_feed.p.dataname.reset_index()

        # Sample every 10th bar
        sample_indices = list(range(0, len(rustybt_df), 10))[:10]

        for idx in sample_indices:
            for col in ["close"]:
                rustybt_val = float(rustybt_df[col][idx])
                bt_val = float(bt_df[col].iloc[idx])
                assert (
                    abs(rustybt_val - bt_val) < 1e-10
                ), f"Bar {idx} {col} mismatch: rustybt={rustybt_val}, backtrader={bt_val}"

    def test_verify_data_alignment_function(self, aligned_fixture: Path) -> None:
        """Test the verify_data_alignment helper function."""
        rustybt_df = load_fixture_for_rustybt(aligned_fixture, asset="AAPL")
        bt_data_feed, _ = load_fixture_for_backtrader(aligned_fixture, asset="AAPL")

        bt_df = bt_data_feed.p.dataname

        result = verify_data_alignment(rustybt_df, bt_df)

        assert result["aligned"] is True
        assert result["bar_count_match"] is True
        assert result["first_bar_match"] is True
        assert result["last_bar_match"] is True
        assert result["sample_match"] is True

    def test_no_floating_point_conversion_differences(self, aligned_fixture: Path) -> None:
        """Test that no floating-point precision is lost (AC-X2.3)."""
        rustybt_df = load_fixture_for_rustybt(aligned_fixture, asset="AAPL")
        bt_data_feed, _ = load_fixture_for_backtrader(aligned_fixture, asset="AAPL")

        bt_df = bt_data_feed.p.dataname.reset_index()

        # Convert rustybt to pandas for exact comparison
        rustybt_pd = rustybt_df.to_pandas()

        # Check that close prices are bit-for-bit identical
        for i in range(min(100, len(rustybt_pd))):
            rustybt_close = rustybt_pd["close"].iloc[i]
            bt_close = bt_df["close"].iloc[i]
            assert rustybt_close == bt_close, (
                f"Float precision loss at index {i}: "
                f"rustybt={rustybt_close!r}, backtrader={bt_close!r}"
            )


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_load_nonexistent_fixture_raises_error(self) -> None:
        """Test that loading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_fixture_for_rustybt(Path("/nonexistent/fixture.parquet"))

    def test_get_info_nonexistent_fixture_raises_error(self) -> None:
        """Test that getting info for nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_fixture_info(Path("/nonexistent/fixture.parquet"))

    def test_single_asset_fixture(self, tmp_path: Path) -> None:
        """Test handling of single-asset fixture."""
        output = tmp_path / "single_asset.parquet"
        generate_fixture(output=output, assets=1, start="2023-01-01", end="2023-01-31", seed=42)

        rustybt_df = load_fixture_for_rustybt(output)
        bt_data_feed, asset_name = load_fixture_for_backtrader(output)

        assert len(rustybt_df) > 0
        assert bt_data_feed is not None

    def test_short_date_range(self, tmp_path: Path) -> None:
        """Test handling of short date range (1 day)."""
        output = tmp_path / "one_day.parquet"
        generate_fixture(output=output, assets=2, start="2023-01-01", end="2023-01-02", seed=42)

        df = pl.read_parquet(output)
        # Should have 1 day * 2 assets = 2 rows
        assert len(df) == 2
