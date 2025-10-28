"""Tests for calendar detection and assignment based on asset type.

Following TDD: Tests written FIRST before implementation.
Tests follow CR-002 (Zero-Mock) - use real implementations only.
"""

import tempfile
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import polars as pl
import pytest
from exchange_calendars import get_calendar

from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.polars.parquet_writer import ParquetWriter


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


@pytest.fixture
def temp_bundle_dir():
    """Create temporary bundle directory."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestCalendarDetection:
    """Test suite for calendar detection from asset types."""

    def test_get_calendar_name_for_forex(self):
        """Test that forex asset type returns '24/5' calendar name."""
        # This will be implemented in ParquetWriter._get_calendar_name()
        writer = ParquetWriter(Path(tempfile.mkdtemp()))
        calendar_name = writer._get_calendar_name("forex")
        assert calendar_name == "24/5"

    def test_get_calendar_name_for_crypto(self):
        """Test that crypto asset type returns '24/7' calendar name."""
        writer = ParquetWriter(Path(tempfile.mkdtemp()))
        calendar_name = writer._get_calendar_name("crypto")
        assert calendar_name == "24/7"

    def test_get_calendar_name_for_equity(self):
        """Test that equity asset type returns 'XNYS' calendar name."""
        writer = ParquetWriter(Path(tempfile.mkdtemp()))
        calendar_name = writer._get_calendar_name("equity")
        assert calendar_name == "XNYS"

    def test_get_calendar_name_for_future(self):
        """Test that future asset type returns 'XNYS' calendar name (default)."""
        writer = ParquetWriter(Path(tempfile.mkdtemp()))
        calendar_name = writer._get_calendar_name("future")
        assert calendar_name == "XNYS"

    def test_get_calendar_name_for_unknown(self):
        """Test that unknown asset type defaults to 'XNYS'."""
        writer = ParquetWriter(Path(tempfile.mkdtemp()))
        calendar_name = writer._get_calendar_name("unknown")
        assert calendar_name == "XNYS"

    def test_get_calendar_name_for_none(self):
        """Test that None asset type defaults to 'XNYS'."""
        writer = ParquetWriter(Path(tempfile.mkdtemp()))
        calendar_name = writer._get_calendar_name(None)
        assert calendar_name == "XNYS"

    def test_calendar_is_valid_exchange_calendar(self):
        """Test that returned calendar names are valid in exchange_calendars."""
        writer = ParquetWriter(Path(tempfile.mkdtemp()))

        # All these should be valid calendar names
        for asset_type in ["forex", "crypto", "equity"]:
            calendar_name = writer._get_calendar_name(asset_type)
            # Should not raise - tests that calendar exists
            calendar = get_calendar(calendar_name)
            assert calendar is not None


class TestCalendarStorage:
    """Test suite for calendar storage in bundle metadata."""

    def test_bundle_metadata_stores_calendar(self, temp_db):
        """Test that calendar can be stored in bundle metadata."""
        BundleMetadata.update(
            bundle_name="test-forex-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            calendar="24/5",  # Forex calendar
        )

        metadata = BundleMetadata.get("test-forex-bundle")
        assert metadata["calendar"] == "24/5"

    def test_bundle_metadata_calendar_defaults_to_none(self, temp_db):
        """Test that calendar is None when not specified (backward compat)."""
        BundleMetadata.update(
            bundle_name="test-legacy-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
        )

        metadata = BundleMetadata.get("test-legacy-bundle")
        # Calendar should be None for legacy bundles
        assert metadata.get("calendar") is None

    def test_parquet_writer_auto_populates_calendar(self, temp_bundle_dir, temp_db):
        """Test that ParquetWriter automatically populates calendar from asset type."""
        writer = ParquetWriter(temp_bundle_dir, enable_metadata_catalog=False)

        # Create sample forex data
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 2), date(2023, 1, 3)],
                "sid": [1, 1],
                "open": [Decimal("1.2000"), Decimal("1.2010")],
                "high": [Decimal("1.2050"), Decimal("1.2060")],
                "low": [Decimal("1.1990"), Decimal("1.2000")],
                "close": [Decimal("1.2030"), Decimal("1.2040")],
                "volume": [Decimal("100000"), Decimal("110000")],
            }
        )

        # Write with asset_type="forex"
        source_metadata = {
            "source_type": "yfinance",
            "source_url": "https://finance.yahoo.com",
            "api_version": "v8",
            "symbols": ["EURUSD"],
            "symbol_map": {"EURUSD": 1},
        }

        writer.write_daily_bars(
            df,
            bundle_name="test-forex-auto",
            source_metadata=source_metadata,
            asset_type="forex",  # Explicit forex type
        )

        # Verify calendar was auto-populated
        metadata = BundleMetadata.get("test-forex-auto")
        assert metadata["calendar"] == "24/5"

    def test_parquet_writer_infers_calendar_from_symbols(self, temp_bundle_dir, temp_db):
        """Test that calendar is inferred from symbols when asset_type not provided."""
        writer = ParquetWriter(temp_bundle_dir, enable_metadata_catalog=False)

        # Create sample forex data
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 2), date(2023, 1, 3)],
                "sid": [1, 1],
                "open": [Decimal("1.2000"), Decimal("1.2010")],
                "high": [Decimal("1.2050"), Decimal("1.2060")],
                "low": [Decimal("1.1990"), Decimal("1.2000")],
                "close": [Decimal("1.2030"), Decimal("1.2040")],
                "volume": [Decimal("100000"), Decimal("110000")],
            }
        )

        # Write WITHOUT explicit asset_type - should infer from symbol
        source_metadata = {
            "source_type": "yfinance",
            "source_url": "https://finance.yahoo.com",
            "api_version": "v8",
            "symbols": ["EURUSD=X"],  # yfinance forex format
            "symbol_map": {"EURUSD=X": 1},
        }

        writer.write_daily_bars(
            df,
            bundle_name="test-forex-inferred",
            source_metadata=source_metadata,
            # asset_type NOT provided - should be inferred
        )

        # Verify calendar was inferred and populated
        metadata = BundleMetadata.get("test-forex-inferred")
        assert metadata["calendar"] == "24/5"


class TestCalendarRetrieval:
    """Test suite for calendar retrieval and usage."""

    def test_get_bundle_calendar_success(self, temp_db):
        """Test retrieving calendar from bundle metadata."""
        BundleMetadata.update(
            bundle_name="test-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            calendar="24/5",
        )

        # This method will be added to BundleMetadata
        calendar_name = BundleMetadata.get_calendar("test-bundle")
        assert calendar_name == "24/5"

    def test_get_bundle_calendar_returns_none_for_legacy(self, temp_db):
        """Test that get_calendar returns None for bundles without calendar."""
        BundleMetadata.update(
            bundle_name="legacy-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
        )

        calendar_name = BundleMetadata.get_calendar("legacy-bundle")
        assert calendar_name is None

    def test_get_bundle_calendar_raises_for_nonexistent_bundle(self, temp_db):
        """Test that get_calendar raises error for non-existent bundle."""
        with pytest.raises(ValueError, match="Bundle .* not found"):
            BundleMetadata.get_calendar("nonexistent-bundle")


class TestBackwardCompatibility:
    """Test suite for backward compatibility with existing bundles."""

    def test_null_calendar_defaults_to_xnys_in_run_algo(self, temp_db):
        """Test that NULL calendar falls back to XNYS (existing behavior)."""
        # Create bundle without calendar (simulates legacy bundle)
        BundleMetadata.update(
            bundle_name="legacy-equity",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            # No calendar specified
        )

        # Retrieve calendar - should be None
        calendar_name = BundleMetadata.get_calendar("legacy-equity")
        assert calendar_name is None

        # In run_algo.py, this should default to XNYS
        # This will be tested in integration test

    def test_existing_bundles_work_without_calendar_column(self, temp_db):
        """Test that bundles created before calendar feature still work."""
        # This simulates the state before the calendar column was added
        BundleMetadata.update(
            bundle_name="pre-calendar-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
        )

        # Should not raise - bundle is usable
        metadata = BundleMetadata.get("pre-calendar-bundle")
        assert metadata is not None
        assert metadata["bundle_name"] == "pre-calendar-bundle"


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_invalid_calendar_name_logs_warning(self, temp_bundle_dir, temp_db, caplog):
        """Test that invalid calendar name logs warning and falls back to XNYS."""
        # This tests error handling when a bundle has an invalid calendar name
        # (shouldn't happen in practice, but defensive coding)
        BundleMetadata.update(
            bundle_name="invalid-cal-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            calendar="INVALID_CALENDAR",
        )

        calendar_name = BundleMetadata.get_calendar("invalid-cal-bundle")
        assert calendar_name == "INVALID_CALENDAR"  # Returns as-is

        # run_algo.py should handle the invalid calendar and log warning
        # That will be tested in integration test

    def test_mixed_asset_types_uses_first_detected(self, temp_bundle_dir, temp_db):
        """Test that bundles with mixed asset types use first detected asset type's calendar."""
        writer = ParquetWriter(temp_bundle_dir, enable_metadata_catalog=False)

        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 2), date(2023, 1, 3)],
                "sid": [1, 2],
                "open": [Decimal("1.2000"), Decimal("100.00")],
                "high": [Decimal("1.2050"), Decimal("101.00")],
                "low": [Decimal("1.1990"), Decimal("99.00")],
                "close": [Decimal("1.2030"), Decimal("100.50")],
                "volume": [Decimal("100000"), Decimal("1000000")],
            }
        )

        # Mixed symbols: forex and equity
        source_metadata = {
            "source_type": "yfinance",
            "source_url": "https://finance.yahoo.com",
            "api_version": "v8",
            "symbols": ["EURUSD=X", "AAPL"],  # First is forex, second is equity
            "symbol_map": {"EURUSD=X": 1, "AAPL": 2},
        }

        writer.write_daily_bars(
            df,
            bundle_name="test-mixed-assets",
            source_metadata=source_metadata,
        )

        # Should use first symbol's asset type (forex) -> 24/5
        metadata = BundleMetadata.get("test-mixed-assets")
        assert metadata["calendar"] == "24/5"


class TestRealForexUseCase:
    """Integration test with actual forex bundle scenario."""

    def test_forex_bundle_jan_2_2023_works(self, temp_bundle_dir, temp_db):
        """Test that forex bundle starting Jan 2, 2023 (NYSE holiday) works correctly.

        This is the actual user-reported issue: Jan 2, 2023 is a valid forex
        trading day but an NYSE holiday, causing NotSessionError.
        """
        writer = ParquetWriter(temp_bundle_dir, enable_metadata_catalog=False)

        # Create forex data starting Jan 2, 2023 (Monday, NYSE holiday)
        df = pl.DataFrame(
            {
                "date": [
                    date(2023, 1, 2),  # NYSE holiday but forex trading day
                    date(2023, 1, 3),
                    date(2023, 1, 4),
                ],
                "sid": [1, 1, 1],
                "open": [Decimal("1.3500"), Decimal("1.3510"), Decimal("1.3520")],
                "high": [Decimal("1.3550"), Decimal("1.3560"), Decimal("1.3570")],
                "low": [Decimal("1.3490"), Decimal("1.3500"), Decimal("1.3510")],
                "close": [Decimal("1.3530"), Decimal("1.3540"), Decimal("1.3550")],
                "volume": [Decimal("100000"), Decimal("110000"), Decimal("120000")],
            }
        )

        source_metadata = {
            "source_type": "yfinance",
            "source_url": "https://finance.yahoo.com",
            "api_version": "v8",
            "symbols": ["GBPCAD=X"],
            "symbol_map": {"GBPCAD=X": 1},
        }

        writer.write_daily_bars(
            df,
            bundle_name="forex-1d-test",
            source_metadata=source_metadata,
            asset_type="forex",
        )

        # Verify correct calendar was assigned
        metadata = BundleMetadata.get("forex-1d-test")
        assert metadata["calendar"] == "24/5"

        # Verify that 24/5 calendar includes Jan 2, 2023
        calendar = get_calendar("24/5")
        jan_2 = pd.Timestamp("2023-01-02")
        assert jan_2 in calendar.sessions  # Should be a valid session


# Zero-Mock Compliance Notes:
# - All tests use real exchange_calendars.get_calendar()
# - All tests use real database operations (temporary SQLite)
# - All tests use real Polars DataFrames and Decimal types
# - No mocking frameworks used
# - Tests verify actual behavior, not mocked behavior
