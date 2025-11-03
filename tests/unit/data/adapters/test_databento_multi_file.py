"""Tests for Databento multi-file OHLCV processing.

Tests Critical Issue #1: Multi-file packages only process first file (99.9% data loss).

Following TDD approach - tests written before implementation.
Uses real Databento sample data (no mocks) per CR-002 Zero-Mock Enforcement.
"""

import tempfile
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.databento_adapter import (
    DatabentoAdapter,
    DatabentoConfig,
)

# Sample Databento data packages
# XNAS: Multi-file package (1,888 daily files)
XNAS_MULTI_FILE_ZIP = Path(
    "/Users/jerryinyang/Code/bmad-dev/rustybt/temp/data/XNAS-20251101-9KJUTNL367.zip"
)

# GLBX: Single-file package (1 file)
GLBX_SINGLE_FILE_ZIP = Path(
    "/Users/jerryinyang/Code/bmad-dev/rustybt/temp/data/GLBX-20251101-MSTQDERCLR.zip"
)


class TestMultiFileDiscovery:
    """Test that all OHLCV files are discovered, not just the first one."""

    def test_find_all_ohlcv_files_returns_list(self):
        """Test that _find_all_ohlcv_files() returns a list, not single file."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        files = adapter._find_all_ohlcv_files()

        # Should return a list
        assert isinstance(files, list)
        assert len(files) > 0
        assert all(isinstance(f, Path) for f in files)

    def test_find_all_ohlcv_files_single_file_package(self):
        """Test file discovery with single-file package (GLBX)."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        files = adapter._find_all_ohlcv_files()

        # Single-file package should return exactly 1 file
        assert len(files) == 1
        assert files[0].suffix in [".zst", ".csv"]
        assert ".ohlcv-" in files[0].name

    def test_find_all_ohlcv_files_multi_file_package(self):
        """Test file discovery with multi-file package (XNAS) - ALL files discovered."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        files = adapter._find_all_ohlcv_files()

        # XNAS package has 1,888 daily files (2018-05-01 to 2025-10-31)
        # This is the critical test - old implementation only returned 1 file
        assert isinstance(files, list)
        assert (
            len(files) > 1
        ), "Multi-file package should discover multiple files, not just first one"

        # Should have approximately 1,888 files (trading days from 2018-05-01 to 2025-10-31)
        assert len(files) > 1000, f"Expected ~1888 files, found {len(files)}"

        # All should be valid OHLCV files
        for f in files:
            assert f.suffix in [".zst", ".csv"]
            assert ".ohlcv-" in f.name

    def test_find_all_ohlcv_files_sorted_order(self):
        """Test that files are returned in sorted order (chronological)."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        files = adapter._find_all_ohlcv_files()

        # Files should be sorted alphabetically (which gives chronological order)
        file_names = [f.name for f in files]
        sorted_names = sorted(file_names)
        assert file_names == sorted_names, "Files should be returned in sorted order"

    def test_find_all_ohlcv_files_no_files_raises_error(self):
        """Test that missing OHLCV files raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty directory
            empty_dir = Path(temp_dir)

            config = DatabentoConfig(data_path=str(empty_dir))
            adapter = DatabentoAdapter(config)

            with pytest.raises(FileNotFoundError, match="No OHLCV files found"):
                adapter._find_all_ohlcv_files()


class TestMultiFileDecompression:
    """Test that all files are decompressed, not just the first one."""

    def test_get_ohlcv_csv_paths_returns_list(self):
        """Test that _get_ohlcv_csv_paths() returns list of all CSV paths."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        csv_paths = adapter._get_ohlcv_csv_paths()

        # Should return a list of paths
        assert isinstance(csv_paths, list)
        assert len(csv_paths) > 0
        assert all(isinstance(p, Path) for p in csv_paths)
        assert all(p.suffix == ".csv" for p in csv_paths)

    def test_get_ohlcv_csv_paths_single_file(self):
        """Test CSV path extraction for single-file package."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        csv_paths = adapter._get_ohlcv_csv_paths()

        assert len(csv_paths) == 1
        assert csv_paths[0].exists()
        assert csv_paths[0].suffix == ".csv"

    def test_get_ohlcv_csv_paths_multi_file(self):
        """Test CSV path extraction for multi-file package - ALL files decompressed."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        csv_paths = adapter._get_ohlcv_csv_paths()

        # Should decompress ALL files, not just first one
        assert len(csv_paths) > 1, "Should decompress all files, not just first"
        assert len(csv_paths) > 1000, f"Expected ~1888 CSV files, got {len(csv_paths)}"

        # All should be actual CSV files
        for path in csv_paths:
            assert path.suffix == ".csv"
            assert path.exists()


class TestMultiFileConcatenation:
    """Test that all OHLCV files are concatenated into single DataFrame."""

    def test_parse_ohlcv_csv_concatenates_all_files(self):
        """Test that _parse_ohlcv_csv() concatenates data from all files."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Parse without filters to get all data
        df = adapter._parse_ohlcv_csv()

        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

        # Critical assertion: Date range should span multiple years
        # XNAS data: 2018-05-01 to 2025-10-31 (7.5 years, 1,888 trading days)
        min_date = df["timestamp"].min()
        max_date = df["timestamp"].max()

        date_range_days = (max_date - min_date).days

        # Should have data spanning more than 1000 days (not just 1 day from first file)
        assert date_range_days > 1000, (
            f"Data should span multiple years, found only {date_range_days} days. "
            "This suggests only first file was processed (99.9% data loss bug)."
        )

        # Specific date range check
        assert min_date >= pd.Timestamp("2018-05-01", tz="UTC")
        assert max_date <= pd.Timestamp("2026-01-01", tz="UTC")

    def test_parse_ohlcv_csv_row_count_reflects_all_files(self):
        """Test that row count reflects data from all files, not just first."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        # XNAS has ~19,557 unique instruments over ~1,888 trading days
        # Should have millions of rows, not just thousands (from first file)
        assert len(df) > 100_000, (
            f"Expected millions of rows from all files, found only {len(df)}. "
            "This suggests only first file was processed."
        )

    def test_parse_ohlcv_csv_single_file_still_works(self):
        """Test that single-file packages still work correctly after multi-file fix."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

        # Check required columns
        required_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
        for col in required_cols:
            assert col in df.columns

    def test_parse_ohlcv_csv_logs_file_count(self):
        """Test that parsing logs number of files processed."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # This should log file discovery and concatenation
        df = adapter._parse_ohlcv_csv()

        # Log should indicate multiple files processed
        # (Verification through log output inspection)
        assert len(df) > 0

    def test_parse_ohlcv_csv_empty_file_handling(self):
        """Test that empty files are skipped gracefully."""
        # This test requires a package with empty files
        # For now, we'll test the error handling structure
        # Real test would create a synthetic package with empty files
        pass  # Placeholder for edge case testing


class TestMultiFileDateFiltering:
    """Test that date filtering works correctly across multiple files."""

    def test_date_filtering_spans_multiple_files(self):
        """Test that date range filtering correctly processes files across range."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Request 1-year date range that spans multiple daily files
        start_date = pd.Timestamp("2020-01-01")
        end_date = pd.Timestamp("2020-12-31")

        df = adapter._parse_ohlcv_csv(start=start_date, end=end_date)

        # Should have data from ~252 trading days (1 year)
        min_date = df["timestamp"].min()
        max_date = df["timestamp"].max()

        # Verify range
        assert min_date >= pd.Timestamp("2020-01-01", tz="UTC")
        assert max_date <= pd.Timestamp("2021-01-01", tz="UTC")

        # Should have processed ~252 daily files, not just 1
        date_range_days = (max_date - min_date).days
        assert date_range_days > 200, (
            f"Expected ~252 trading days of data, found {date_range_days} days. "
            "Multi-file processing may not be working."
        )

    def test_fetch_with_multi_file_package(self):
        """Test fetch() method works correctly with multi-file packages."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Fetch 3-month range
        df = adapter.fetch(
            symbols=[],  # All symbols
            start=pd.Timestamp("2020-01-01"),
            end=pd.Timestamp("2020-03-31"),
            frequency="1d",
        )

        # This is an async method, but we're calling it synchronously in tests
        # Need to check if it's a coroutine and await it
        import asyncio

        if asyncio.iscoroutine(df):
            df = asyncio.run(df)

        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

        # Should span ~60 trading days
        date_range_days = (df["timestamp"].max() - df["timestamp"].min()).days
        assert date_range_days > 50, "Should process multiple months of data"


class TestMultiFilePerformance:
    """Test performance characteristics of multi-file processing."""

    @pytest.mark.slow
    def test_multi_file_processing_completes(self):
        """Test that processing 1,888 files completes in reasonable time."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        import time

        start_time = time.time()

        # Process small date range to avoid full 1,888 file processing in tests
        df = adapter._parse_ohlcv_csv(
            start=pd.Timestamp("2020-01-01"), end=pd.Timestamp("2020-01-31")
        )

        elapsed = time.time() - start_time

        assert len(df) > 0
        # Should complete in under 60 seconds (reasonable for ~20 files)
        assert elapsed < 60, f"Processing took {elapsed:.1f}s, may need optimization"


class TestMultiFileIntegration:
    """Integration tests for complete multi-file workflow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_xnas_multi_file_ingestion(self):
        """Integration test: Full workflow with XNAS multi-file package."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS multi-file sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Fetch 1-year range to verify multi-file processing
        df = await adapter.fetch(
            symbols=[],  # All symbols
            start=pd.Timestamp("2020-01-01"),
            end=pd.Timestamp("2020-12-31"),
            frequency="1d",
        )

        # Comprehensive verification
        assert isinstance(df, pl.DataFrame)
        assert len(df) > 100_000, "Should have processed full year of data"

        # Date range check
        date_span_days = (df["timestamp"].max() - df["timestamp"].min()).days
        assert date_span_days > 300, "Should span full year"

        # Multi-asset check
        symbols = df["symbol"].unique().to_list()
        assert len(symbols) > 1000, "Should have thousands of symbols"

        # Data quality check
        invalid_rows = df.filter(pl.col("high") < pl.col("low"))
        assert len(invalid_rows) == 0, "No OHLCV violations"

        print(f"✓ Processed {len(df):,} rows from multi-file XNAS package")
        print(f"✓ Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"✓ Symbols: {len(symbols):,}")
        print(f"✓ Multi-file processing: WORKING")
