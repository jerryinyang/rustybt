"""Tests for unified BundleMetadata class."""

import tempfile
import time
from pathlib import Path

import pytest

from rustybt.data.bundles.metadata import BundleMetadata


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    BundleMetadata.set_db_path(db_path)
    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)
    BundleMetadata._engine = None
    BundleMetadata._db_path = None


def test_bundle_metadata_create_and_get(temp_db):
    """Test creating and retrieving bundle metadata."""
    # Create bundle with provenance
    BundleMetadata.update(
        bundle_name="test-bundle",
        source_type="yfinance",
        source_url="https://query2.finance.yahoo.com/v8/...",
        api_version="v8",
        fetch_timestamp=int(time.time()),
        checksum="abc123",
    )

    # Retrieve bundle
    metadata = BundleMetadata.get("test-bundle")

    assert metadata is not None
    assert metadata["bundle_name"] == "test-bundle"
    assert metadata["source_type"] == "yfinance"
    assert metadata["source_url"] == "https://query2.finance.yahoo.com/v8/..."
    assert metadata["api_version"] == "v8"
    assert metadata["checksum"] == "abc123"


def test_bundle_metadata_with_quality_metrics(temp_db):
    """Test bundle metadata with quality metrics."""
    current_time = int(time.time())

    # Create bundle with both provenance and quality
    BundleMetadata.update(
        bundle_name="test-bundle",
        source_type="yfinance",
        fetch_timestamp=current_time,
        checksum="abc123",
        row_count=1000,
        start_date=current_time - 86400 * 30,
        end_date=current_time,
        ohlcv_violations=0,
        validation_passed=True,
        validation_timestamp=current_time,
    )

    # Retrieve and verify
    metadata = BundleMetadata.get("test-bundle")

    assert metadata["row_count"] == 1000
    assert metadata["ohlcv_violations"] == 0
    assert metadata["validation_passed"] is True


def test_bundle_metadata_add_symbols(temp_db):
    """Test adding symbols to bundle."""
    # Create bundle first
    BundleMetadata.update(
        bundle_name="test-bundle",
        source_type="yfinance",
        fetch_timestamp=int(time.time()),
        checksum="abc123",
    )

    # Add symbols
    BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NASDAQ")
    BundleMetadata.add_symbol("test-bundle", "MSFT", "equity", "NASDAQ")
    BundleMetadata.add_symbol("test-bundle", "GOOGL", "equity", "NASDAQ")

    # Retrieve symbols
    symbols = BundleMetadata.get_symbols("test-bundle")

    assert len(symbols) == 3
    assert any(s["symbol"] == "AAPL" and s["asset_type"] == "equity" for s in symbols)
    assert any(s["symbol"] == "MSFT" for s in symbols)
    assert any(s["symbol"] == "GOOGL" for s in symbols)


def test_bundle_metadata_list_bundles(temp_db):
    """Test listing all bundles."""
    # Create multiple bundles
    for i in range(3):
        BundleMetadata.update(
            bundle_name=f"test-bundle-{i}",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum=f"checksum-{i}",
        )

    # List all bundles
    bundles = BundleMetadata.list_bundles()

    assert len(bundles) >= 3
    bundle_names = [b["bundle_name"] for b in bundles]
    assert "test-bundle-0" in bundle_names
    assert "test-bundle-1" in bundle_names
    assert "test-bundle-2" in bundle_names


def test_bundle_metadata_filter_by_source_type(temp_db):
    """Test filtering bundles by source type."""
    # Create bundles with different sources
    BundleMetadata.update(
        bundle_name="yfinance-bundle",
        source_type="yfinance",
        fetch_timestamp=int(time.time()),
        checksum="abc",
    )
    BundleMetadata.update(
        bundle_name="ccxt-bundle",
        source_type="ccxt",
        fetch_timestamp=int(time.time()),
        checksum="def",
    )

    # Filter by source type
    yfinance_bundles = BundleMetadata.list_bundles(source_type="yfinance")
    ccxt_bundles = BundleMetadata.list_bundles(source_type="ccxt")

    assert len(yfinance_bundles) >= 1
    assert len(ccxt_bundles) >= 1
    assert all(b["source_type"] == "yfinance" for b in yfinance_bundles)
    assert all(b["source_type"] == "ccxt" for b in ccxt_bundles)


def test_bundle_metadata_delete(temp_db):
    """Test deleting bundle."""
    # Create bundle
    BundleMetadata.update(
        bundle_name="test-bundle",
        source_type="yfinance",
        fetch_timestamp=int(time.time()),
        checksum="abc123",
    )

    # Verify it exists
    assert BundleMetadata.get("test-bundle") is not None

    # Delete
    deleted = BundleMetadata.delete("test-bundle")
    assert deleted is True

    # Verify it's gone
    assert BundleMetadata.get("test-bundle") is None


def test_bundle_metadata_count_methods(temp_db):
    """Test counting methods."""
    # Create bundles and symbols
    BundleMetadata.update(
        bundle_name="test-bundle-1",
        source_type="yfinance",
        fetch_timestamp=int(time.time()),
        checksum="abc",
        row_count=100,
        start_date=int(time.time()),
        end_date=int(time.time()),
        validation_timestamp=int(time.time()),
    )

    BundleMetadata.add_symbol("test-bundle-1", "AAPL", "equity", "NASDAQ")
    BundleMetadata.add_symbol("test-bundle-1", "MSFT", "equity", "NASDAQ")

    # Test counts
    assert BundleMetadata.count_bundles() >= 1
    assert BundleMetadata.count_quality_records() >= 1
    assert BundleMetadata.count_symbols("test-bundle-1") == 2
    assert BundleMetadata.count_all_symbols() >= 2


def test_bundle_metadata_update_existing(temp_db):
    """Test updating existing bundle metadata."""
    # Create initial bundle
    BundleMetadata.update(
        bundle_name="test-bundle",
        source_type="yfinance",
        fetch_timestamp=100,
        checksum="old-checksum",
    )

    # Update with new data
    BundleMetadata.update(
        bundle_name="test-bundle",
        fetch_timestamp=200,
        checksum="new-checksum",
    )

    # Verify update
    metadata = BundleMetadata.get("test-bundle")
    assert metadata["fetch_timestamp"] == 200
    assert metadata["checksum"] == "new-checksum"


def test_bundle_metadata_symbol_uniqueness(temp_db):
    """Test that symbols are unique per bundle."""
    # Create bundle
    BundleMetadata.update(
        bundle_name="test-bundle",
        source_type="yfinance",
        fetch_timestamp=int(time.time()),
        checksum="abc",
    )

    # Add same symbol twice (should update, not duplicate)
    BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NASDAQ")
    BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NYSE")  # Update exchange

    # Verify only one entry
    symbols = BundleMetadata.get_symbols("test-bundle")
    aapl_symbols = [s for s in symbols if s["symbol"] == "AAPL"]

    assert len(aapl_symbols) == 1
    assert aapl_symbols[0]["exchange"] == "NYSE"  # Updated value
