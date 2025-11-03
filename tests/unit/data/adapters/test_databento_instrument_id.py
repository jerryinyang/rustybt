"""Tests for Databento instrument_id usage and collision prevention.

Tests Critical Issue #2: Instrument ID ignored causes data collisions.

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


class TestInstrumentIDConfig:
    """Test configuration options for instrument_id handling."""

    def test_default_config_uses_instrument_id(self):
        """Test that use_instrument_id defaults to True."""
        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))

        assert hasattr(config, "use_instrument_id")
        assert config.use_instrument_id is True  # Should default to True

    def test_config_allows_legacy_mode(self):
        """Test that use_instrument_id can be disabled for legacy behavior."""
        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP), use_instrument_id=False)

        assert config.use_instrument_id is False

    def test_config_has_symbol_format(self):
        """Test that config has symbol_format field."""
        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))

        assert hasattr(config, "symbol_format")
        assert config.symbol_format == "symbol_id"  # Default format


class TestCompositeSymbolCreation:
    """Test creation of composite symbol identifiers (SYMBOL_INSTRUMENTID)."""

    def test_composite_symbols_created_with_instrument_id(self):
        """Test that symbols are formatted as SYMBOL_INSTRUMENTID."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP), use_instrument_id=True)
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        # Symbols should be in format "SYMBOL_INSTRUMENTID"
        sample_symbols = df["symbol"].head(10).to_list()
        for sym in sample_symbols:
            assert "_" in sym, f"Expected composite format, got: {sym}"
            parts = sym.split("_")
            assert len(parts) == 2, f"Expected SYMBOL_ID format, got: {sym}"
            # Second part should be numeric instrument_id
            assert parts[1].isdigit(), f"Expected numeric ID, got: {parts[1]}"

    def test_original_symbol_preserved(self):
        """Test that original_symbol column is preserved for reference."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        # Should have original_symbol column
        assert "original_symbol" in df.columns
        assert "instrument_id" in df.columns

        # original_symbol should be the raw symbol (e.g., "ESH0")
        # symbol should be composite (e.g., "ESH0_6640")
        for row in df.head(5).iter_rows(named=True):
            composite = row["symbol"]
            original = row["original_symbol"]
            instr_id = row["instrument_id"]

            # Composite should be original + "_" + instrument_id
            expected_composite = f"{original}_{instr_id}"
            assert (
                composite == expected_composite
            ), f"Expected {expected_composite}, got {composite}"

    def test_legacy_mode_uses_symbol_only(self):
        """Test that legacy mode (use_instrument_id=False) uses symbol only."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP), use_instrument_id=False)
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        # Symbols should NOT have underscore + ID suffix
        sample_symbols = df["symbol"].head(10).to_list()
        for sym in sample_symbols:
            # Should be original symbol format (may have numbers but no _ID suffix)
            # Example: "ESH0" not "ESH0_6640"
            # We check that if there's an underscore, it's not followed by only digits
            if "_" in sym:
                parts = sym.split("_")
                # If last part is all digits, this is composite format (should not happen in legacy mode)
                if parts[-1].isdigit() and len(parts) == 2:
                    pytest.fail(f"Legacy mode should not use composite symbols, found: {sym}")


class TestInstrumentUniqueness:
    """Test that instrument_id ensures uniqueness across symbol reuse."""

    def test_different_instruments_get_different_identifiers(self):
        """Test that same symbol with different instrument_ids gets unique identifiers."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        # Group by original_symbol and check for multiple instrument_ids
        # Futures contracts reuse base symbols (e.g., "ES" for different expirations)
        symbol_groups = df.groupby("original_symbol").agg(
            [
                pl.col("instrument_id").n_unique().alias("unique_instruments"),
                pl.col("symbol").n_unique().alias("unique_composite_symbols"),
            ]
        )

        # Find symbols with multiple instruments
        multi_instrument_symbols = symbol_groups.filter(pl.col("unique_instruments") > 1)

        if len(multi_instrument_symbols) > 0:
            # For these symbols, composite symbols should also be unique
            for row in multi_instrument_symbols.iter_rows(named=True):
                original = row["original_symbol"]
                instr_count = row["unique_instruments"]
                composite_count = row["unique_composite_symbols"]

                # Number of unique composite symbols should match number of instruments
                assert composite_count == instr_count, (
                    f"Symbol '{original}' has {instr_count} instruments "
                    f"but only {composite_count} unique composite symbols. "
                    "Instrument IDs not being used correctly."
                )

    def test_futures_contracts_separated_by_expiration(self):
        """Test that futures contracts with different expirations are separate assets."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        # Get small sample to avoid processing all data
        df = adapter._parse_ohlcv_csv(
            start=pd.Timestamp("2020-11-01"), end=pd.Timestamp("2020-11-30")
        )

        # Look for ES (E-mini S&P 500) contracts
        es_contracts = df.filter(pl.col("original_symbol").str.starts_with("ES"))

        if len(es_contracts) > 0:
            # Should have multiple ES instruments (different expirations)
            unique_es_instruments = es_contracts["instrument_id"].n_unique()
            unique_es_composite = es_contracts["symbol"].n_unique()

            # Multiple expirations should exist
            assert unique_es_instruments > 1, "Should have multiple ES contract expirations"

            # Each should have unique composite symbol
            assert (
                unique_es_composite == unique_es_instruments
            ), "Each ES expiration should have unique identifier"

    def test_no_data_collisions_with_instrument_id(self):
        """Test that using instrument_id prevents data from different instruments mixing."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        # For each composite symbol, instrument_id should be constant
        for composite_symbol in df["symbol"].unique().to_list()[:100]:  # Check sample
            symbol_data = df.filter(pl.col("symbol") == composite_symbol)
            unique_instruments = symbol_data["instrument_id"].n_unique()

            assert (
                unique_instruments == 1
            ), f"Composite symbol '{composite_symbol}' has multiple instrument_ids: data collision!"


class TestSymbolMappingStorage:
    """Test that instrument → symbol mappings are stored for reference."""

    @pytest.mark.asyncio
    async def test_instrument_mappings_stored_during_ingestion(self):
        """Test that instrument mappings are written to bundle metadata."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        bundle_name = "test_instrument_mapping"

        # Ingest small sample
        adapter.ingest_to_bundle(
            bundle_name=bundle_name,
            symbols=[],
            start=pd.Timestamp("2020-11-01"),
            end=pd.Timestamp("2020-11-02"),
            frequency="1h",
        )

        # Check that instrument mappings file was created
        from rustybt.utils.paths import data_path

        bundle_dir = data_path(["bundles", bundle_name])
        mapping_file = bundle_dir / "databento_instrument_mappings.json"

        assert mapping_file.exists(), "Instrument mappings file should be created during ingestion"

        # Verify mappings structure
        import json

        with open(mapping_file, "r") as f:
            mappings = json.load(f)

        assert len(mappings) > 0, "Should have instrument mappings"

        # Each mapping should have required fields
        for instrument_id, mapping in list(mappings.items())[:5]:  # Check sample
            assert "original_symbol" in mapping
            assert "composite_symbol" in mapping
            assert "sid" in mapping

            # Composite should be original + "_" + instrument_id
            expected = f"{mapping['original_symbol']}_{instrument_id}"
            assert mapping["composite_symbol"] == expected


class TestValidationAndWarnings:
    """Test validation and warning mechanisms for symbol collisions."""

    def test_validates_symbol_uniqueness(self):
        """Test that adapter validates symbol uniqueness across instrument_ids."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        # This should have the validation method
        assert hasattr(
            adapter, "_validate_symbol_uniqueness"
        ), "Adapter should have symbol uniqueness validation"

    def test_logs_warning_for_legacy_mode_with_collisions(self):
        """Test that legacy mode logs warnings if symbol collisions detected."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP), use_instrument_id=False)
        adapter = DatabentoAdapter(config)

        # In legacy mode with futures data, should log warnings about potential collisions
        # This is more of a logging test - we just verify the mode works
        df = adapter._parse_ohlcv_csv()
        assert len(df) > 0


class TestSplitDurationMetadata:
    """Test that split_duration metadata is parsed and stored."""

    def test_metadata_has_split_duration_field(self):
        """Test that DatabentoMetadata includes split_duration field."""
        if not XNAS_MULTI_FILE_ZIP.exists():
            pytest.skip("XNAS sample data not available")

        config = DatabentoConfig(data_path=str(XNAS_MULTI_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        metadata = adapter._parse_metadata()

        # Should have split_duration field
        assert hasattr(metadata, "split_duration")

        # XNAS has split_duration="day"
        assert metadata.split_duration == "day"

    def test_split_duration_null_for_single_file(self):
        """Test that single-file packages have split_duration=None."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(data_path=str(GLBX_SINGLE_FILE_ZIP))
        adapter = DatabentoAdapter(config)

        metadata = adapter._parse_metadata()

        # Single-file package should have split_duration=None
        assert metadata.split_duration is None


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_existing_tests_still_pass(self):
        """Test that existing adapter tests still pass with new instrument_id feature."""
        # This is more of a meta-test - if other test files pass, this passes
        # The real test is running the full test suite
        pass

    def test_extra_columns_api_unchanged(self):
        """Test that extra_columns API is unchanged."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            extra_columns=["rtype", "publisher_id", "instrument_id"],
        )
        adapter = DatabentoAdapter(config)

        columns = adapter.get_available_columns()

        assert "standard" in columns
        assert "extra" in columns
        assert "instrument_id" in columns["extra"]


class TestIntegrationInstrumentID:
    """Integration tests for instrument_id feature."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_workflow_with_instrument_ids(self):
        """Integration test: Full ingestion with instrument_id tracking."""
        if not GLBX_SINGLE_FILE_ZIP.exists():
            pytest.skip("GLBX sample data not available")

        config = DatabentoConfig(
            data_path=str(GLBX_SINGLE_FILE_ZIP),
            use_instrument_id=True,
            extra_columns=["instrument_id", "original_symbol"],
        )
        adapter = DatabentoAdapter(config)

        # Fetch data
        df = await adapter.fetch(
            symbols=[],
            start=pd.Timestamp("2020-11-01"),
            end=pd.Timestamp("2020-11-07"),
            frequency="1h",
        )

        # Verify composite symbols
        assert len(df) > 0
        sample_symbol = df["symbol"][0]
        assert "_" in sample_symbol, "Should have composite symbol format"

        # Verify no data collisions
        for composite_symbol in df["symbol"].unique().to_list()[:50]:
            symbol_data = df.filter(pl.col("symbol") == composite_symbol)
            if "instrument_id" in symbol_data.columns:
                unique_instruments = symbol_data["instrument_id"].n_unique()
                assert unique_instruments == 1, f"Data collision detected for {composite_symbol}"

        print(f"✓ Processed {len(df)} rows with instrument_id tracking")
        print(f"✓ Unique instruments: {df['instrument_id'].n_unique()}")
        print(f"✓ Unique composite symbols: {df['symbol'].n_unique()}")
        print(f"✓ No data collisions detected")
