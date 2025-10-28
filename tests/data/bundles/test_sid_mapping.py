"""Tests for SID mapping consistency between parquet files and database.

This test suite verifies the fix for the critical SID mismatch bug where:
- Parquet files used sequential SIDs (1-25)
- Database used auto-increment SIDs (1290-1314)
- Result: Data existed but was not accessible

Tests follow CR-002 (Zero-Mock Enforcement):
- No mocking frameworks used
- Tests use real database operations (temporary SQLite)
- Tests verify actual behavior, not mocked behavior
"""

import tempfile
import time
from pathlib import Path

import pytest

from rustybt.data.adapters.utils import build_symbol_sid_map
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


class TestExplicitSIDParameter:
    """Tests for add_symbol() with explicit SID parameter."""

    def test_add_symbol_with_explicit_sid(self, temp_db):
        """Test that add_symbol() uses explicit SID when provided."""
        # Create bundle
        BundleMetadata.update(
            bundle_name="test-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="abc123",
        )

        # Add symbol with explicit SID=1000
        symbol_id = BundleMetadata.add_symbol(
            bundle_name="test-bundle",
            symbol="AAPL",
            asset_type="equity",
            exchange="NASDAQ",
            sid=1000,
        )

        # Verify returned SID matches explicit value
        assert symbol_id == 1000

        # Verify symbol is stored with correct SID in database
        symbols = BundleMetadata.get_symbols("test-bundle")
        assert len(symbols) == 1
        assert symbols[0]["symbol"] == "AAPL"
        assert symbols[0]["symbol_id"] == 1000

    def test_add_symbol_with_explicit_sid_multiple(self, temp_db):
        """Test multiple symbols with explicit SIDs."""
        BundleMetadata.update(
            bundle_name="forex-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="def456",
        )

        # Add multiple symbols with explicit SIDs matching parquet file
        sid_1 = BundleMetadata.add_symbol("forex-bundle", "EURUSD=X", "forex", "FX", sid=1)
        sid_2 = BundleMetadata.add_symbol("forex-bundle", "GBPUSD=X", "forex", "FX", sid=2)
        sid_3 = BundleMetadata.add_symbol("forex-bundle", "JPYUSD=X", "forex", "FX", sid=3)

        # Verify all SIDs match explicit values
        assert sid_1 == 1
        assert sid_2 == 2
        assert sid_3 == 3

        # Verify in database
        symbols = BundleMetadata.get_symbols("forex-bundle")
        assert len(symbols) == 3
        assert symbols[0]["symbol_id"] == 1
        assert symbols[1]["symbol_id"] == 2
        assert symbols[2]["symbol_id"] == 3

    def test_add_symbol_explicit_sid_updates_auto_increment(self, temp_db):
        """Test that explicit SID updates auto-increment to prevent conflicts."""
        BundleMetadata.update(
            bundle_name="mixed-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="ghi789",
        )

        # Add symbol with explicit SID=1000
        BundleMetadata.add_symbol("mixed-bundle", "SYMBOL1", "equity", "NYSE", sid=1000)

        # Add symbol without SID (auto-increment continues from max SID)
        auto_sid = BundleMetadata.add_symbol("mixed-bundle", "SYMBOL2", "equity", "NYSE")

        # Auto-increment continues from max(SID) to prevent conflicts
        assert auto_sid == 1001

    def test_add_symbol_duplicate_explicit_sid_returns_existing(self, temp_db):
        """Test adding same symbol twice with explicit SID returns existing ID."""
        BundleMetadata.update(
            bundle_name="test-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="jkl012",
        )

        # Add symbol with explicit SID=500
        sid_1 = BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NASDAQ", sid=500)
        assert sid_1 == 500

        # Add same symbol again (should return existing SID)
        sid_2 = BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NASDAQ", sid=500)
        assert sid_2 == 500

        # Verify only one record exists
        symbols = BundleMetadata.get_symbols("test-bundle")
        assert len(symbols) == 1


class TestAutoIncrementBackwardCompatibility:
    """Tests for add_symbol() without explicit SID (backward compatibility)."""

    def test_add_symbol_without_sid_uses_auto_increment(self, temp_db):
        """Test that add_symbol() without SID uses database auto-increment."""
        BundleMetadata.update(
            bundle_name="test-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="mno345",
        )

        # Add symbols without explicit SID (backward compatible behavior)
        sid_1 = BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NASDAQ")
        sid_2 = BundleMetadata.add_symbol("test-bundle", "MSFT", "equity", "NASDAQ")
        sid_3 = BundleMetadata.add_symbol("test-bundle", "GOOGL", "equity", "NASDAQ")

        # Auto-increment should start from 1 and increment
        assert sid_1 == 1
        assert sid_2 == 2
        assert sid_3 == 3

    def test_add_symbol_auto_increment_continues_across_bundles(self, temp_db):
        """Test that auto-increment continues globally across bundles."""
        # Create first bundle
        BundleMetadata.update(
            bundle_name="bundle-1",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="pqr678",
        )

        # Add symbols to first bundle (SIDs 1, 2)
        sid_1 = BundleMetadata.add_symbol("bundle-1", "AAPL", "equity", "NASDAQ")
        sid_2 = BundleMetadata.add_symbol("bundle-1", "MSFT", "equity", "NASDAQ")

        # Create second bundle
        BundleMetadata.update(
            bundle_name="bundle-2",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="stu901",
        )

        # Add symbols to second bundle (should continue from 3)
        sid_3 = BundleMetadata.add_symbol("bundle-2", "GOOGL", "equity", "NASDAQ")
        sid_4 = BundleMetadata.add_symbol("bundle-2", "AMZN", "equity", "NASDAQ")

        assert sid_1 == 1
        assert sid_2 == 2
        assert sid_3 == 3  # Continues auto-increment
        assert sid_4 == 4


class TestGetNextSymbolId:
    """Tests for get_next_symbol_id() method."""

    def test_get_next_symbol_id_empty_database(self, temp_db):
        """Test get_next_symbol_id() returns 1 for empty database."""
        next_id = BundleMetadata.get_next_symbol_id()
        assert next_id == 1

    def test_get_next_symbol_id_with_existing_symbols(self, temp_db):
        """Test get_next_symbol_id() returns max + 1."""
        BundleMetadata.update(
            bundle_name="test-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="vwx234",
        )

        # Add 3 symbols (SIDs 1, 2, 3)
        BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NASDAQ")
        BundleMetadata.add_symbol("test-bundle", "MSFT", "equity", "NASDAQ")
        BundleMetadata.add_symbol("test-bundle", "GOOGL", "equity", "NASDAQ")

        # Next ID should be 4
        next_id = BundleMetadata.get_next_symbol_id()
        assert next_id == 4

    def test_get_next_symbol_id_with_explicit_sid(self, temp_db):
        """Test get_next_symbol_id() accounts for explicit SIDs."""
        BundleMetadata.update(
            bundle_name="test-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="yza567",
        )

        # Add symbol with explicit SID=1000
        BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NASDAQ", sid=1000)

        # Next ID should be 1001 (max + 1)
        next_id = BundleMetadata.get_next_symbol_id()
        assert next_id == 1001

    def test_get_next_symbol_id_with_mixed_sids(self, temp_db):
        """Test get_next_symbol_id() with mix of auto and explicit SIDs."""
        BundleMetadata.update(
            bundle_name="test-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="bcd890",
        )

        # Add symbols with auto-increment (1, 2)
        BundleMetadata.add_symbol("test-bundle", "AAPL", "equity", "NASDAQ")
        BundleMetadata.add_symbol("test-bundle", "MSFT", "equity", "NASDAQ")

        # Add symbol with explicit SID=500 (updates auto-increment)
        BundleMetadata.add_symbol("test-bundle", "GOOGL", "equity", "NASDAQ", sid=500)

        # Add another auto-increment (continues from 501)
        sid = BundleMetadata.add_symbol("test-bundle", "AMZN", "equity", "NASDAQ")
        assert sid == 501

        # Next ID should be 502 (max SID + 1, which is 501 + 1)
        next_id = BundleMetadata.get_next_symbol_id()
        assert next_id == 502


class TestBuildSymbolSidMap:
    """Tests for build_symbol_sid_map() database integration."""

    def test_build_symbol_sid_map_empty_database(self, temp_db):
        """Test build_symbol_sid_map() starts from 1 for empty database."""
        symbols = ["EURUSD=X", "GBPUSD=X", "JPYUSD=X"]
        symbol_map = build_symbol_sid_map(symbols)

        # Should start from 1
        assert symbol_map["EURUSD=X"] == 1
        assert symbol_map["GBPUSD=X"] == 2
        assert symbol_map["JPYUSD=X"] == 3

    def test_build_symbol_sid_map_with_existing_symbols(self, temp_db):
        """Test build_symbol_sid_map() continues from existing max SID."""
        # Create bundle with existing symbols
        BundleMetadata.update(
            bundle_name="existing-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="efg123",
        )

        # Add symbols (SIDs 1, 2, 3)
        BundleMetadata.add_symbol("existing-bundle", "AAPL", "equity", "NASDAQ")
        BundleMetadata.add_symbol("existing-bundle", "MSFT", "equity", "NASDAQ")
        BundleMetadata.add_symbol("existing-bundle", "GOOGL", "equity", "NASDAQ")

        # Build symbol map for new bundle (should start from 4)
        symbols = ["EURUSD=X", "GBPUSD=X"]
        symbol_map = build_symbol_sid_map(symbols)

        assert symbol_map["EURUSD=X"] == 4
        assert symbol_map["GBPUSD=X"] == 5

    def test_build_symbol_sid_map_normalizes_symbols(self, temp_db):
        """Test build_symbol_sid_map() normalizes symbol names."""
        symbols = ["eurusd=x", " GBPUSD=X ", "jpyusd=x"]
        symbol_map = build_symbol_sid_map(symbols)

        # All should be normalized to uppercase
        assert "EURUSD=X" in symbol_map
        assert "GBPUSD=X" in symbol_map
        assert "JPYUSD=X" in symbol_map

    def test_build_symbol_sid_map_deterministic(self, temp_db):
        """Test build_symbol_sid_map() produces deterministic mapping."""
        symbols = ["EURUSD=X", "GBPUSD=X", "JPYUSD=X", "AUDUSD=X", "NZDUSD=X"]

        # Build map twice
        map_1 = build_symbol_sid_map(symbols)
        map_2 = build_symbol_sid_map(symbols)

        # Should be identical (deterministic)
        assert map_1 == map_2


class TestSIDConsistencyIntegration:
    """Integration tests for SID consistency between parquet and database."""

    def test_parquet_database_sid_consistency(self, temp_db):
        """Test that SIDs used in parquet match SIDs stored in database.

        This test simulates the full ingestion flow:
        1. build_symbol_sid_map() creates SID mapping
        2. Parquet writer uses these SIDs
        3. Metadata writer uses same SIDs (passed via sid parameter)
        4. Result: parquet and database have matching SIDs
        """
        # Create bundle
        BundleMetadata.update(
            bundle_name="forex-1d",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="hij456",
        )

        # Step 1: Build symbol-to-SID mapping (what adapter does)
        symbols = ["EURUSD=X", "GBPUSD=X", "JPYUSD=X", "AUDUSD=X"]
        symbol_map = build_symbol_sid_map(symbols)

        # Step 2: Add symbols to database using same SIDs (what writer does)
        for symbol in symbols:
            sid = symbol_map[symbol]
            BundleMetadata.add_symbol(
                bundle_name="forex-1d",
                symbol=symbol,
                asset_type="forex",
                exchange="FX",
                sid=sid,  # Pass explicit SID from symbol_map
            )

        # Step 3: Verify database SIDs match symbol_map SIDs
        db_symbols = BundleMetadata.get_symbols("forex-1d")

        for db_symbol in db_symbols:
            symbol_name = db_symbol["symbol"]
            db_sid = db_symbol["symbol_id"]
            map_sid = symbol_map[symbol_name]

            # This is the critical check: database SID must match symbol_map SID
            assert db_sid == map_sid, (
                f"SID mismatch for {symbol_name}: "
                f"database has {db_sid}, symbol_map has {map_sid}"
            )

    def test_multiple_bundle_ingestion_sid_isolation(self, temp_db):
        """Test that multiple bundles get non-overlapping SIDs.

        Simulates ingesting multiple bundles in sequence to verify
        SIDs don't conflict across bundles.
        """
        # Ingest first bundle (equity)
        BundleMetadata.update(
            bundle_name="equity-daily",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="klm789",
        )

        equity_symbols = ["AAPL", "MSFT", "GOOGL"]
        equity_map = build_symbol_sid_map(equity_symbols)

        for symbol in equity_symbols:
            BundleMetadata.add_symbol(
                "equity-daily", symbol, "equity", "NASDAQ", sid=equity_map[symbol]
            )

        # Ingest second bundle (forex) - should get non-overlapping SIDs
        BundleMetadata.update(
            bundle_name="forex-1d",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="nop012",
        )

        forex_symbols = ["EURUSD=X", "GBPUSD=X"]
        forex_map = build_symbol_sid_map(forex_symbols)

        for symbol in forex_symbols:
            BundleMetadata.add_symbol("forex-1d", symbol, "forex", "FX", sid=forex_map[symbol])

        # Verify no SID overlap
        equity_sids = set(equity_map.values())
        forex_sids = set(forex_map.values())

        # No intersection between SID sets
        assert equity_sids.isdisjoint(
            forex_sids
        ), f"SID overlap detected! Equity SIDs: {equity_sids}, Forex SIDs: {forex_sids}"

    def test_sid_mismatch_scenario_does_not_occur(self, temp_db):
        """Test that the original bug scenario (SID mismatch) does not occur.

        Original bug:
        - Parquet files: SIDs 1-25 (from build_symbol_sid_map)
        - Database: SIDs 1290-1314 (from auto-increment)
        - Result: Mismatch, data not accessible

        With fix:
        - Parquet files: SIDs from build_symbol_sid_map (e.g., 1-25)
        - Database: Same SIDs passed explicitly (e.g., 1-25)
        - Result: Match, data accessible
        """
        # Create existing bundle to offset auto-increment
        BundleMetadata.update(
            bundle_name="existing-bundle",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="qrs345",
        )

        # Add many symbols to push auto-increment high (simulate 1290-1314)
        for i in range(1289):
            BundleMetadata.add_symbol("existing-bundle", f"SYM{i}", "equity", "NYSE")

        # Now ingest forex bundle (the bug scenario)
        BundleMetadata.update(
            bundle_name="forex-1d",
            source_type="yfinance",
            fetch_timestamp=int(time.time()),
            checksum="tuv678",
        )

        # Build symbol map (should start from 1290, not 1)
        forex_symbols = ["EURUSD=X", "GBPUSD=X", "JPYUSD=X"]
        symbol_map = build_symbol_sid_map(forex_symbols)

        # Verify symbol_map starts from next available SID (1290)
        assert min(symbol_map.values()) == 1290

        # Add symbols to database with explicit SIDs
        for symbol in forex_symbols:
            BundleMetadata.add_symbol("forex-1d", symbol, "forex", "FX", sid=symbol_map[symbol])

        # Verify database has same SIDs as symbol_map
        db_symbols = BundleMetadata.get_symbols("forex-1d")

        for db_symbol in db_symbols:
            symbol_name = db_symbol["symbol"]
            db_sid = db_symbol["symbol_id"]
            map_sid = symbol_map[symbol_name]

            # This verifies the bug is fixed
            assert db_sid == map_sid
            # And SIDs are in the 1290+ range, not 1-3
            assert db_sid >= 1290
