"""Tests for Parquet metadata catalog.

Tests cover:
- Dataset creation and retrieval
- Symbol management
- Date range tracking
- Checksum validation
- Metadata queries
"""

import tempfile
from datetime import date
from pathlib import Path

import pytest

from rustybt.data.polars.metadata_catalog import (
    ParquetMetadataCatalog,
    calculate_file_checksum,
)


@pytest.fixture
def temp_catalog():
    """Create temporary metadata catalog for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_metadata.db"
        catalog = ParquetMetadataCatalog(str(db_path))
        yield catalog


@pytest.fixture
def temp_parquet_file():
    """Create temporary Parquet file for checksum testing."""
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp.write(b"test parquet data")
        tmp.flush()
        yield Path(tmp.name)
        Path(tmp.name).unlink()


class TestDatasetManagement:
    """Test dataset creation and retrieval."""

    def test_create_dataset(self, temp_catalog):
        """Test creating a dataset."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
            schema_version=1,
        )

        assert dataset_id > 0

    def test_get_dataset_info(self, temp_catalog):
        """Test retrieving dataset metadata."""
        # Create dataset
        dataset_id = temp_catalog.create_dataset(
            source="ccxt",
            resolution="1h",
            schema_version=1,
        )

        # Retrieve
        info = temp_catalog.get_dataset_info(dataset_id)

        assert info is not None
        assert info["dataset_id"] == dataset_id
        assert info["source"] == "ccxt"
        assert info["resolution"] == "1h"
        assert info["schema_version"] == 1

    def test_get_nonexistent_dataset(self, temp_catalog):
        """Test retrieving non-existent dataset returns None."""
        info = temp_catalog.get_dataset_info(9999)
        assert info is None


class TestSymbolManagement:
    """Test symbol management."""

    def test_add_symbol(self, temp_catalog):
        """Test adding symbol to dataset."""
        # Create dataset
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        # Add symbol
        symbol_id = temp_catalog.add_symbol(
            dataset_id=dataset_id,
            symbol="AAPL",
            asset_type="equity",
            exchange="NASDAQ",
        )

        assert symbol_id > 0

    def test_get_symbols(self, temp_catalog):
        """Test retrieving symbols for dataset."""
        # Create dataset
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        # Add multiple symbols
        symbols_to_add = [
            ("AAPL", "equity", "NASDAQ"),
            ("GOOGL", "equity", "NASDAQ"),
            ("BTC/USDT", "crypto", "binance"),
        ]

        for symbol, asset_type, exchange in symbols_to_add:
            temp_catalog.add_symbol(
                dataset_id=dataset_id,
                symbol=symbol,
                asset_type=asset_type,
                exchange=exchange,
            )

        # Retrieve
        symbols = temp_catalog.get_symbols(dataset_id)

        assert len(symbols) == 3
        assert symbols[0]["symbol"] == "AAPL"
        assert symbols[1]["symbol"] == "GOOGL"
        assert symbols[2]["symbol"] == "BTC/USDT"

    def test_get_symbols_empty_dataset(self, temp_catalog):
        """Test retrieving symbols from empty dataset."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        symbols = temp_catalog.get_symbols(dataset_id)
        assert len(symbols) == 0


class TestDateRangeManagement:
    """Test date range tracking."""

    def test_update_date_range_with_dates(self, temp_catalog):
        """Test updating date range with date objects."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        temp_catalog.update_date_range(
            dataset_id=dataset_id,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )

        # Retrieve
        date_range = temp_catalog.get_date_range(dataset_id)

        assert date_range is not None
        assert date_range["start_date"] == date(2023, 1, 1)
        assert date_range["end_date"] == date(2023, 12, 31)

    def test_update_date_range_with_strings(self, temp_catalog):
        """Test updating date range with ISO strings."""
        dataset_id = temp_catalog.create_dataset(
            source="ccxt",
            resolution="1h",
        )

        temp_catalog.update_date_range(
            dataset_id=dataset_id,
            start_date="2023-06-01",
            end_date="2023-06-30",
        )

        # Retrieve
        date_range = temp_catalog.get_date_range(dataset_id)

        assert date_range is not None
        assert date_range["start_date"] == date(2023, 6, 1)
        assert date_range["end_date"] == date(2023, 6, 30)

    def test_update_existing_date_range(self, temp_catalog):
        """Test updating existing date range."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        # Initial range
        temp_catalog.update_date_range(
            dataset_id=dataset_id,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 6, 30),
        )

        # Update range
        temp_catalog.update_date_range(
            dataset_id=dataset_id,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )

        # Retrieve
        date_range = temp_catalog.get_date_range(dataset_id)

        assert date_range["end_date"] == date(2023, 12, 31)

    def test_get_date_range_nonexistent(self, temp_catalog):
        """Test retrieving date range for dataset without one."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        date_range = temp_catalog.get_date_range(dataset_id)
        assert date_range is None


class TestChecksumManagement:
    """Test checksum validation."""

    def test_add_checksum(self, temp_catalog):
        """Test adding checksum for Parquet file."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        checksum_id = temp_catalog.add_checksum(
            dataset_id=dataset_id,
            parquet_path="year=2023/month=01/data.parquet",
            checksum="a7b2c3d4e5f6",
        )

        assert checksum_id > 0

    def test_update_checksum(self, temp_catalog):
        """Test updating existing checksum."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        parquet_path = "year=2023/month=01/data.parquet"

        # Add initial checksum
        checksum_id1 = temp_catalog.add_checksum(
            dataset_id=dataset_id,
            parquet_path=parquet_path,
            checksum="old_checksum",
        )

        # Update checksum
        checksum_id2 = temp_catalog.add_checksum(
            dataset_id=dataset_id,
            parquet_path=parquet_path,
            checksum="new_checksum",
        )

        # Should update same entry
        assert checksum_id1 == checksum_id2

    def test_verify_checksum_valid(self, temp_catalog, temp_parquet_file):
        """Test verifying valid checksum."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        # Calculate actual checksum
        actual_checksum = calculate_file_checksum(temp_parquet_file)

        # Add to catalog
        temp_catalog.add_checksum(
            dataset_id=dataset_id,
            parquet_path=str(temp_parquet_file.name),
            checksum=actual_checksum,
        )

        # Verify
        is_valid = temp_catalog.verify_checksum(
            str(temp_parquet_file.name),
            actual_checksum,
        )

        assert is_valid is True

    def test_verify_checksum_mismatch(self, temp_catalog, temp_parquet_file):
        """Test verifying mismatched checksum."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        # Add incorrect checksum
        temp_catalog.add_checksum(
            dataset_id=dataset_id,
            parquet_path=str(temp_parquet_file.name),
            checksum="wrong_checksum",
        )

        # Calculate actual checksum
        actual_checksum = calculate_file_checksum(temp_parquet_file)

        # Verify should fail
        is_valid = temp_catalog.verify_checksum(
            str(temp_parquet_file.name),
            actual_checksum,
        )

        assert is_valid is False

    def test_verify_checksum_not_found(self, temp_catalog):
        """Test verifying checksum for non-existent file."""
        is_valid = temp_catalog.verify_checksum(
            "nonexistent.parquet",
            "some_checksum",
        )

        assert is_valid is False


class TestParquetFileQueries:
    """Test querying Parquet file paths."""

    def test_find_parquet_files(self, temp_catalog):
        """Test finding Parquet files for dataset."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        # Add multiple files
        paths = [
            "year=2023/month=01/data.parquet",
            "year=2023/month=02/data.parquet",
            "year=2023/month=03/data.parquet",
        ]

        for path in paths:
            temp_catalog.add_checksum(
                dataset_id=dataset_id,
                parquet_path=path,
                checksum="test_checksum",
            )

        # Find files
        found_paths = temp_catalog.find_parquet_files(dataset_id)

        assert len(found_paths) == 3
        assert set(found_paths) == set(paths)

    def test_find_parquet_files_empty(self, temp_catalog):
        """Test finding files for dataset with no files."""
        dataset_id = temp_catalog.create_dataset(
            source="yfinance",
            resolution="1d",
        )

        paths = temp_catalog.find_parquet_files(dataset_id)

        assert len(paths) == 0


class TestCalculateFileChecksum:
    """Test file checksum calculation."""

    def test_calculate_checksum(self, temp_parquet_file):
        """Test calculating SHA256 checksum of file."""
        checksum = calculate_file_checksum(temp_parquet_file)

        # SHA256 produces 64 hex characters
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_calculate_checksum_deterministic(self, temp_parquet_file):
        """Test checksum is deterministic."""
        checksum1 = calculate_file_checksum(temp_parquet_file)
        checksum2 = calculate_file_checksum(temp_parquet_file)

        assert checksum1 == checksum2

    def test_calculate_checksum_different_files(self):
        """Test different files have different checksums."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp1:
            tmp1.write(b"content1")
            tmp1.flush()
            path1 = Path(tmp1.name)

        with tempfile.NamedTemporaryFile(delete=False) as tmp2:
            tmp2.write(b"content2")
            tmp2.flush()
            path2 = Path(tmp2.name)

        try:
            checksum1 = calculate_file_checksum(path1)
            checksum2 = calculate_file_checksum(path2)

            assert checksum1 != checksum2

        finally:
            path1.unlink()
            path2.unlink()
