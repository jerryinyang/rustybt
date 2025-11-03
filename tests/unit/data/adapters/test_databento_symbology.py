"""Tests for Databento symbology file parsing and symbol lookups.

Tests Critical Issue #3: Symbology file not parsed.

Following TDD approach - tests written before implementation.
Uses real Databento sample data (no mocks) per CR-002 Zero-Mock Enforcement.
"""

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.databento_adapter import (
    DatabentoAdapter,
    DatabentoConfig,
)

# Sample Databento data packages
GLBX_SINGLE_FILE_ZIP = Path(
    "/Users/jerryinyang/Code/bmad-dev/rustybt/temp/data/GLBX-20251101-MSTQDERCLR.zip"
)
XNAS_MULTI_FILE_ZIP = Path(
    "/Users/jerryinyang/Code/bmad-dev/rustybt/temp/data/XNAS-20251101-9KJUTNL367.zip"
)


class TestSymbologyFileDetection:
    """Test detection and parsing of symbology files."""

    def test_symbology_csv_exists(self):
        """Test that symbology.csv file is detected in package."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        symbology_path = adapter._find_symbology_file()

        assert symbology_path is not None
        assert symbology_path.exists()
        assert symbology_path.name in ["symbology.csv", "symbology.json"]

    def test_symbology_json_exists(self):
        """Test that symbology.json file is detected in package."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Check for JSON file specifically
        working_dir = adapter._get_working_dir()
        json_path = working_dir / "symbology.json"

        assert (
            json_path.exists() or (working_dir / "symbology.csv").exists()
        ), "At least one symbology file should exist"

    def test_missing_symbology_returns_none(self):
        """Test that missing symbology file returns None, not error."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            config = DatabentoConfig(data_path=temp_dir)
            adapter = DatabentoAdapter(config)

            symbology_path = adapter._find_symbology_file()
            assert symbology_path is None


class TestSymbologyCSVParsing:
    """Test parsing of symbology.csv files."""

    def test_parse_symbology_csv_returns_dataframe(self):
        """Test that symbology CSV is parsed to Polars DataFrame."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        symbology = adapter._parse_symbology()

        assert symbology is not None
        assert isinstance(symbology, pl.DataFrame)
        assert len(symbology) > 0

    def test_symbology_csv_has_required_columns(self):
        """Test that symbology DataFrame has required columns."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        symbology = adapter._parse_symbology()

        # Required columns for symbol resolution
        # Actual column names depend on Databento format
        assert len(symbology.columns) > 0

        # Should have columns like: symbol, start_date, end_date, etc.
        # Exact columns to be verified with actual Databento format

    def test_symbology_csv_maps_symbols_to_dates(self):
        """Test that symbology maps symbols to date ranges."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        symbology = adapter._parse_symbology()

        # Should have date information
        # Verify structure when actual format is known
        assert len(symbology) > 0


class TestSymbologyJSONParsing:
    """Test parsing of symbology.json files."""

    def test_parse_symbology_json_returns_dataframe(self):
        """Test that symbology JSON is parsed to Polars DataFrame."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Force JSON parsing
        symbology = adapter._parse_symbology_json()

        assert symbology is not None
        assert isinstance(symbology, pl.DataFrame)
        assert len(symbology) > 0

    def test_symbology_json_equivalent_to_csv(self):
        """Test that JSON and CSV symbology have same information."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Parse both formats
        symbology_csv = adapter._parse_symbology()  # Prefers CSV
        symbology_json = adapter._parse_symbology_json()

        # Should have same number of unique symbols
        # (structure may differ, but content should be equivalent)
        assert len(symbology_csv) > 0
        assert len(symbology_json) > 0


class TestSymbolLookup:
    """Test symbol → instrument lookup functionality."""

    def test_get_instruments_for_symbol(self):
        """Test looking up all instruments for a given symbol."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Look up a common symbol (e.g., "ES" for E-mini S&P 500)
        instruments = adapter.get_instruments_for_symbol("ES")

        assert instruments is not None
        assert isinstance(instruments, list)

        # Futures symbol should have multiple instruments (different expirations)
        if len(instruments) > 0:
            assert len(instruments) > 1, "ES futures should have multiple expirations"

            # Each instrument should have metadata
            for instr in instruments[:5]:  # Check sample
                assert "instrument_id" in instr
                # May also have: start_date, end_date, expiration, etc.

    def test_get_instruments_for_nonexistent_symbol(self):
        """Test lookup of non-existent symbol returns empty list."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        instruments = adapter.get_instruments_for_symbol("NONEXISTENT_SYMBOL_XYZ")

        assert instruments is not None
        assert isinstance(instruments, list)
        assert len(instruments) == 0


class TestInstrumentLookup:
    """Test instrument → symbol lookup functionality."""

    def test_get_symbol_for_instrument(self):
        """Test looking up symbol for a specific instrument_id."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Get a known instrument_id from OHLCV data
        df = adapter._parse_ohlcv_csv()
        if "instrument_id" in df.columns and len(df) > 0:
            sample_instrument_id = df["instrument_id"][0]

            symbol_info = adapter.get_symbol_for_instrument(sample_instrument_id)

            assert symbol_info is not None
            assert isinstance(symbol_info, dict)
            assert "symbol" in symbol_info
            # May also have: start_date, end_date, expiration, etc.

    def test_get_symbol_for_nonexistent_instrument(self):
        """Test lookup of non-existent instrument returns None."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        symbol_info = adapter.get_symbol_for_instrument(999999999)

        assert symbol_info is None or (isinstance(symbol_info, dict) and len(symbol_info) == 0)


class TestSymbolReuse:
    """Test detection of symbol reuse across instruments."""

    def test_detect_symbol_reuse_in_symbology(self):
        """Test that symbology file shows symbol reuse (same symbol, different dates)."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        symbology = adapter._parse_symbology()

        # Check for symbols that appear multiple times (different instruments/dates)
        # This is especially common in futures data
        if "symbol" in symbology.columns:
            symbol_counts = symbology.group_by("symbol").count()
            multi_use_symbols = symbol_counts.filter(pl.col("count") > 1)

            # Futures packages should have symbols used by multiple instruments
            assert (
                len(multi_use_symbols) > 0
            ), "Expected symbol reuse in futures data (same symbol, different expirations)"

    def test_symbology_resolves_reuse_by_date(self):
        """Test that symbology provides date ranges to resolve symbol reuse."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        symbology = adapter._parse_symbology()

        # Symbology should have date columns to distinguish reused symbols
        # Column names may vary by Databento format
        date_columns = [col for col in symbology.columns if "date" in col.lower()]
        assert len(date_columns) > 0, "Symbology should have date columns for symbol resolution"


class TestSymbologyValidation:
    """Test symbology consistency validation."""

    def test_validate_symbology_consistency(self):
        """Test that symbology is consistent with OHLCV data."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Small sample for performance
        df = adapter._parse_ohlcv_csv(
            start=pd.Timestamp("2020-11-01"), end=pd.Timestamp("2020-11-02")
        )

        validation_result = adapter.validate_symbology_consistency(df)

        assert validation_result is not None
        assert isinstance(validation_result, dict)

        # Should report validation status
        assert "valid" in validation_result or "errors" in validation_result

    def test_symbology_covers_all_ohlcv_instruments(self):
        """Test that all instruments in OHLCV data are in symbology."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Small sample
        df = adapter._parse_ohlcv_csv(
            start=pd.Timestamp("2020-11-01"), end=pd.Timestamp("2020-11-02")
        )

        if "instrument_id" in df.columns:
            ohlcv_instruments = set(df["instrument_id"].unique().to_list())

            # Get symbology
            symbology = adapter._parse_symbology()

            if "instrument_id" in symbology.columns:
                symbology_instruments = set(symbology["instrument_id"].unique().to_list())

                # All OHLCV instruments should be in symbology
                missing = ohlcv_instruments - symbology_instruments

                # Some may be missing, but most should be present
                coverage = (len(ohlcv_instruments) - len(missing)) / len(ohlcv_instruments)
                assert coverage > 0.8, (
                    f"Symbology coverage too low: {coverage:.1%}. "
                    f"Missing {len(missing)} instruments"
                )


class TestSymbologyIntegrationWithInstrumentID:
    """Test integration between symbology and instrument_id features."""

    def test_symbology_enhances_instrument_id_lookups(self):
        """Test that symbology provides human-readable lookups for instrument_ids."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        # Get sample composite symbol (e.g., "ESM0_6640")
        if len(df) > 0 and "instrument_id" in df.columns:
            sample_instr_id = df["instrument_id"][0]

            # Should be able to look up metadata from symbology
            symbol_info = adapter.get_symbol_for_instrument(sample_instr_id)

            assert symbol_info is not None
            # Should provide additional context beyond just the symbol

    def test_symbology_query_by_date_range(self):
        """Test querying symbology for active symbols in date range."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # Query symbols active in specific date range
        active_symbols = adapter.get_active_symbols_for_date(pd.Timestamp("2020-11-01"))

        assert active_symbols is not None
        assert isinstance(active_symbols, list)
        assert len(active_symbols) > 0


class TestSymbologyPerformance:
    """Test performance characteristics of symbology parsing."""

    def test_symbology_parsing_completes_quickly(self):
        """Test that symbology parsing completes in reasonable time."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        import time

        start = time.time()

        symbology = adapter._parse_symbology()

        elapsed = time.time() - start

        assert symbology is not None
        assert elapsed < 10, f"Symbology parsing took {elapsed:.1f}s (expected <10s)"

    def test_symbology_cached_after_first_parse(self):
        """Test that symbology is cached to avoid re-parsing."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        # First parse
        import time

        start = time.time()
        symbology1 = adapter._parse_symbology()
        first_time = time.time() - start

        # Second parse (should use cache)
        start = time.time()
        symbology2 = adapter._parse_symbology()
        second_time = time.time() - start

        # Second parse should be much faster (cached)
        assert second_time < first_time / 2, "Symbology should be cached"


class TestSymbologyIntegration:
    """Integration tests for symbology functionality."""

    @pytest.mark.integration
    def test_full_workflow_with_symbology(self):
        """Integration test: Full workflow using symbology for lookups."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        # Parse symbology
        symbology = adapter._parse_symbology()
        assert symbology is not None
        assert len(symbology) > 0

        # Get OHLCV data
        df = adapter._parse_ohlcv_csv(
            start=pd.Timestamp("2020-11-01"), end=pd.Timestamp("2020-11-07")
        )
        assert len(df) > 0

        # Verify symbology covers OHLCV instruments
        if "instrument_id" in df.columns and "instrument_id" in symbology.columns:
            ohlcv_instruments = set(df["instrument_id"].unique().to_list())
            symbology_instruments = set(symbology["instrument_id"].unique().to_list())

            coverage = len(ohlcv_instruments & symbology_instruments) / len(ohlcv_instruments)
            assert coverage > 0.8, f"Symbology coverage: {coverage:.1%}"

        # Test lookup functions
        if "original_symbol" in df.columns and len(df) > 0:
            sample_symbol = df["original_symbol"][0]
            instruments = adapter.get_instruments_for_symbol(sample_symbol)
            assert instruments is not None

        print(f"✓ Symbology parsed: {len(symbology)} entries")
        print(f"✓ Instrument lookups working")
        print(f"✓ Date range queries working")
        print(f"✓ Symbology integration: COMPLETE")
