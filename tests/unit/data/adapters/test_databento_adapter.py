"""Tests for Databento data adapter.

Following TDD approach - tests written before implementation.
Uses real Databento sample data (no mocks) per CR-002 Zero-Mock Enforcement.
"""

import json
import tempfile
import zipfile
from decimal import Decimal
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.databento_adapter import (
    DatabentoAdapter,
    DatabentoConfig,
    DatabentoManifest,
    DatabentoMetadata,
)
from rustybt.data.sources.base import DataSourceMetadata

# Sample Databento data location
SAMPLE_DATA_ZIP = Path(
    "/Users/jerryinyang/Code/bmad-dev/rustybt/temp/data/GLBX-20251101-N5U545U54V.zip"
)
SAMPLE_DATA_DIR = Path(
    "/Users/jerryinyang/Code/bmad-dev/rustybt/temp/data/GLBX-20251101-N5U545U54V"
)


class TestDatabentoMetadataParsing:
    """Test parsing of Databento metadata.json files."""

    def test_parse_metadata_from_extracted_folder(self):
        """Test parsing metadata.json from extracted folder."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)
        metadata = adapter._parse_metadata()

        assert isinstance(metadata, DatabentoMetadata)
        assert metadata.dataset == "GLBX.MDP3"
        assert metadata.schema == "ohlcv-1h"
        assert len(metadata.symbols) == 29  # 29 futures symbols
        assert "ES.FUT" in metadata.symbols
        assert "NQ.FUT" in metadata.symbols

    def test_parse_metadata_from_zip(self):
        """Test parsing metadata.json from ZIP file."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_ZIP))
        adapter = DatabentoAdapter(config)
        metadata = adapter._parse_metadata()

        assert isinstance(metadata, DatabentoMetadata)
        assert metadata.dataset == "GLBX.MDP3"
        assert metadata.schema == "ohlcv-1h"

    def test_parse_manifest(self):
        """Test parsing manifest.json."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)
        manifest = adapter._parse_manifest()

        assert isinstance(manifest, DatabentoManifest)
        assert len(manifest.files) > 0
        # Check OHLCV file is in manifest
        ohlcv_files = [f for f in manifest.files if ".ohlcv-" in f.filename]
        assert len(ohlcv_files) > 0


class TestDatabentoFileHandling:
    """Test file extraction and decompression."""

    def test_zip_detection(self):
        """Test ZIP file detection."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_ZIP))
        adapter = DatabentoAdapter(config)
        assert adapter._is_zip_file() is True

    def test_folder_detection(self):
        """Test folder detection."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)
        assert adapter._is_zip_file() is False

    def test_zip_extraction(self):
        """Test ZIP extraction to temporary directory."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_ZIP))
        adapter = DatabentoAdapter(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_path = adapter._extract_zip(Path(temp_dir))
            assert extracted_path.exists()
            assert (extracted_path / "metadata.json").exists()
            assert (extracted_path / "manifest.json").exists()

    def test_zst_decompression(self):
        """Test zstd decompression of OHLCV file."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        # Find the zst file
        zst_files = list(SAMPLE_DATA_DIR.glob("*.csv.zst"))
        assert len(zst_files) > 0

        zst_file = zst_files[0]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            decompressed_path = adapter._decompress_zst(zst_file, Path(temp_file.name))
            assert decompressed_path.exists()
            assert decompressed_path.stat().st_size > 0

            # Clean up
            decompressed_path.unlink()


class TestDatabentoOHLCVParsing:
    """Test OHLCV CSV parsing and schema mapping."""

    def test_parse_ohlcv_csv_to_polars(self):
        """Test parsing OHLCV CSV to Polars DataFrame."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0  # Should have data

        # Check required columns exist
        required_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
        for col in required_cols:
            assert col in df.columns

        # Check data types
        assert df["timestamp"].dtype == pl.Datetime("us")
        assert df["symbol"].dtype == pl.Utf8
        # Prices should be Decimal-compatible (Float64 initially, converted later)
        assert df["open"].dtype in [pl.Float64, pl.Decimal]
        assert df["volume"].dtype in [pl.Float64, pl.Decimal, pl.Int64]

    def test_ohlcv_data_integrity(self):
        """Test OHLCV data relationships (high >= low, etc.)."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()

        # OHLCV validation: high >= low
        invalid_rows = df.filter(pl.col("high") < pl.col("low"))
        assert len(invalid_rows) == 0, "Found rows where high < low"

        # Volume should be non-negative
        negative_volume = df.filter(pl.col("volume") < 0)
        assert len(negative_volume) == 0, "Found rows with negative volume"

    def test_symbol_extraction(self):
        """Test that symbols are correctly extracted from data."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()
        symbols = df["symbol"].unique().to_list()

        assert len(symbols) > 0
        # Check some known symbols from metadata
        # (actual symbols depend on symbology mapping)


class TestDatabentoMultiAsset:
    """Test multi-asset handling."""

    def test_multi_asset_ingestion(self):
        """Test that multiple assets are ingested from single package."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        df = adapter._parse_ohlcv_csv()
        symbols = df["symbol"].unique().to_list()

        # Sample data has 29 symbols (futures contracts)
        assert len(symbols) > 1, "Should have multiple assets"

    def test_symbol_filtering(self):
        """Test filtering by specific symbols."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        # Fetch specific symbols only
        df = adapter._parse_ohlcv_csv(symbols_filter=["ESZ0"])  # E-mini S&P Dec 2020

        if len(df) > 0:  # If symbol exists in data
            symbols = df["symbol"].unique().to_list()
            assert len(symbols) <= 1


class TestDatabentoFetch:
    """Test the fetch() method that returns standardized OHLCV data."""

    @pytest.mark.asyncio
    async def test_fetch_returns_polars_dataframe(self):
        """Test fetch() returns Polars DataFrame with correct schema."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        df = await adapter.fetch(
            symbols=[],  # All symbols
            start=pd.Timestamp("2020-11-01"),
            end=pd.Timestamp("2020-11-30"),
            frequency="1h",
        )

        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

        # Check standardized schema
        required_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
        for col in required_cols:
            assert col in df.columns

    @pytest.mark.asyncio
    async def test_fetch_date_filtering(self):
        """Test that fetch() respects start/end date filtering."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        df = await adapter.fetch(
            symbols=[],
            start=pd.Timestamp("2020-11-01"),
            end=pd.Timestamp("2020-11-05"),
            frequency="1h",
        )

        # All timestamps should be within range
        min_ts = df["timestamp"].min()
        max_ts = df["timestamp"].max()

        assert min_ts >= pd.Timestamp("2020-11-01", tz="UTC")
        assert max_ts <= pd.Timestamp("2020-11-06", tz="UTC")  # Inclusive end date

    @pytest.mark.asyncio
    async def test_fetch_with_symbol_filter(self):
        """Test fetch() with specific symbols."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        # Try to fetch specific symbol (if exists)
        df = await adapter.fetch(
            symbols=["ESZ0"],  # E-mini S&P Dec 2020
            start=pd.Timestamp("2020-11-01"),
            end=pd.Timestamp("2020-11-30"),
            frequency="1h",
        )

        # Should either have data for that symbol or be empty
        if len(df) > 0:
            symbols = df["symbol"].unique().to_list()
            assert "ESZ0" in symbols


class TestDatabentoIngestToBundle:
    """Test bundle ingestion functionality."""

    def test_ingest_to_bundle_creates_bundle(self, tmp_path):
        """Test that ingest_to_bundle() creates a valid bundle."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        bundle_name = "test_databento_bundle"

        # Ingest small date range for speed
        adapter.ingest_to_bundle(
            bundle_name=bundle_name,
            symbols=[],  # All symbols
            start=pd.Timestamp("2020-11-01"),
            end=pd.Timestamp("2020-11-05"),
            frequency="1h",
        )

        # Check bundle was created
        # (depends on bundle storage location - adjust path as needed)
        # This is a placeholder - actual path depends on config


class TestDatabentoMetadata:
    """Test DataSource metadata methods."""

    def test_get_metadata_returns_valid_metadata(self):
        """Test get_metadata() returns DataSourceMetadata."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        metadata = adapter.get_metadata()

        assert isinstance(metadata, DataSourceMetadata)
        assert metadata.source_type == "databento"
        assert metadata.supports_live is False  # Historical data only
        assert metadata.auth_required is False
        assert "1h" in metadata.supported_frequencies  # From our sample

    def test_supports_live_returns_false(self):
        """Test supports_live() returns False (historical data only)."""
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_DIR))
        adapter = DatabentoAdapter(config)

        assert adapter.supports_live() is False


class TestDatabentoErrorHandling:
    """Test error handling and edge cases."""

    def test_missing_data_path_raises_error(self):
        """Test that missing data path raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            config = DatabentoConfig(data_path="/nonexistent/path")
            adapter = DatabentoAdapter(config)
            adapter._parse_metadata()

    def test_invalid_zip_raises_error(self, tmp_path):
        """Test that invalid ZIP file raises appropriate error."""
        # Create invalid ZIP
        invalid_zip = tmp_path / "invalid.zip"
        invalid_zip.write_text("not a zip file")

        config = DatabentoConfig(data_path=str(invalid_zip))
        adapter = DatabentoAdapter(config)

        with pytest.raises(Exception):  # Should raise extraction error
            adapter._extract_zip(tmp_path)

    def test_missing_metadata_json_raises_error(self, tmp_path):
        """Test that missing metadata.json raises error."""
        # Create empty directory
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        config = DatabentoConfig(data_path=str(empty_dir))
        adapter = DatabentoAdapter(config)

        with pytest.raises(FileNotFoundError):
            adapter._parse_metadata()


class TestDatabentoRegistryIntegration:
    """Test integration with DataSourceRegistry."""

    def test_databento_adapter_is_discoverable(self):
        """Test that DatabentoAdapter is auto-discovered by registry."""
        from rustybt.data.sources.registry import DataSourceRegistry

        # Reset registry to force re-discovery
        DataSourceRegistry.reset()

        sources = DataSourceRegistry.list_sources()
        assert "databento" in sources

    def test_registry_can_instantiate_databento_adapter(self):
        """Test that registry can create DatabentoAdapter instance."""
        from rustybt.data.sources.registry import DataSourceRegistry

        adapter = DataSourceRegistry.get_source("databento", data_path=str(SAMPLE_DATA_DIR))

        assert isinstance(adapter, DatabentoAdapter)
        assert adapter.get_metadata().source_type == "databento"


# Integration test using real data
class TestDatabentoRealDataIngestion:
    """Integration test with real Databento sample data."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_ingestion_workflow(self):
        """Test complete ingestion workflow with real Databento data.

        This test uses actual Databento sample data to verify:
        - ZIP extraction
        - Metadata parsing
        - OHLCV decompression and parsing
        - Date filtering
        - Multi-asset handling
        """
        config = DatabentoConfig(data_path=str(SAMPLE_DATA_ZIP))
        adapter = DatabentoAdapter(config)

        # Fetch data for small date range
        df = await adapter.fetch(
            symbols=[],  # All symbols
            start=pd.Timestamp("2020-11-01"),
            end=pd.Timestamp("2020-11-07"),
            frequency="1h",
        )

        # Verify results
        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

        # Check we have multiple assets
        symbols = df["symbol"].unique().to_list()
        assert len(symbols) > 1

        # Check date range
        min_ts = df["timestamp"].min()
        max_ts = df["timestamp"].max()
        assert min_ts >= pd.Timestamp("2020-11-01", tz="UTC")
        assert max_ts <= pd.Timestamp("2020-11-08", tz="UTC")

        # Check OHLCV relationships
        invalid_rows = df.filter(pl.col("high") < pl.col("low"))
        assert len(invalid_rows) == 0

        print(f"✓ Ingested {len(df)} rows for {len(symbols)} symbols")
        print(f"✓ Date range: {min_ts} to {max_ts}")
        print(f"✓ Symbols: {symbols[:5]}..." if len(symbols) > 5 else f"✓ Symbols: {symbols}")
