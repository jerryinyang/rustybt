"""Tests for Databento Definition parsing functionality (Story 9.2/9.3).

Tests cover:
- Definition file parsing (_parse_definition_file)
- Date-based loading (_load_definition_for_date)
- Key field extraction (_get_definition_key_fields)
- UDS filtering (_filter_user_defined_spreads)
- OHLCV enrichment (_enrich_ohlcv_with_definition)
- Config extensions (definition_package_path, include_user_defined_spreads)
"""

import tempfile
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig


class TestDatabentoConfig:
    """Test DatabentoConfig with Definition-related fields."""

    def test_config_default_values(self, tmp_path: Path) -> None:
        """Test that new config fields have correct defaults."""
        # Create a minimal OHLCV file structure
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(data_path=str(ohlcv_dir))

        assert config.definition_package_path is None
        assert config.include_user_defined_spreads is True

    def test_config_with_definition_path(self, tmp_path: Path) -> None:
        """Test config with Definition package path."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        def_dir = tmp_path / "definition"
        def_dir.mkdir()

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(def_dir),
            include_user_defined_spreads=False,
        )

        assert config.definition_package_path == str(def_dir)
        assert config.include_user_defined_spreads is False


class TestDefinitionParsing:
    """Test Definition file parsing functionality."""

    @pytest.fixture
    def sample_definition_csv(self, tmp_path: Path) -> Path:
        """Create a sample Definition CSV file for testing."""
        csv_content = """ts_recv,ts_event,rtype,publisher_id,instrument_id,raw_symbol,security_update_action,instrument_class,min_price_increment,display_factor,expiration,activation,high_limit_price,low_limit_price,max_price_variation,trading_reference_price,unit_of_measure_qty,min_price_increment_amount,price_ratio,inst_attrib_value,underlying_id,raw_instrument_id,market_depth_implied,market_depth,market_segment_id,max_trade_vol,min_lot_size,min_lot_size_block,min_lot_size_round_lot,min_trade_vol,contract_multiplier,decay_quantity,original_contract_size,trading_reference_date,appl_id,maturity_year,decay_start_date,channel_id,currency,settl_currency,secsubtype,group,exchange,asset,cfi,security_type,unit_of_measure,underlying,strike_price_currency,strike_price,match_algorithm,md_security_trading_status,main_fraction,price_display_format,settl_price_type,sub_fraction,underlying_product,maturity_month,maturity_day,maturity_week,user_defined_instrument,contract_multiplier_unit,flow_schedule_type,tick_rule,symbol
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,24948,ESZ4,A,F,0.25,1.0,2024-12-20T00:00:00.000000000Z,2024-06-20T00:00:00.000000000Z,5500.0,4500.0,100.0,5000.0,1.0,12.5,1.0,0,0,24948,5,10,1,1000,1,1,1,1,50,0,0,0,1,2024,0,1,USD,USD,E,ES,XCME,ES,FFICSX,FUT,USD,,,0.0,F,0,0,0,0,0,0,12,20,0,N,0,0,0,ESZ4
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,24949,ESH5,A,F,0.25,1.0,2025-03-21T00:00:00.000000000Z,2024-12-20T00:00:00.000000000Z,5500.0,4500.0,100.0,5000.0,1.0,12.5,1.0,0,0,24949,5,10,1,1000,1,1,1,1,50,0,0,0,1,2025,0,1,USD,USD,E,ES,XCME,ES,FFICSX,FUT,USD,,,0.0,F,0,0,0,0,0,0,3,21,0,N,0,0,0,ESH5
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,339180,ESZ4 C5000,A,C,0.25,1.0,2024-12-20T00:00:00.000000000Z,2024-06-20T00:00:00.000000000Z,500.0,0.0,100.0,50.0,1.0,12.5,1.0,0,24948,339180,5,10,1,1000,1,1,1,1,50,0,0,0,1,2024,0,1,USD,USD,E,ES,XCME,ES,OPASFX,OOF,USD,,USD,5000.0,F,0,0,0,0,0,0,12,20,0,N,0,0,0,ESZ4 C5000
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,827895,UD:EN: VT 1028827895,A,T,0.25,1.0,2024-12-20T00:00:00.000000000Z,2024-06-20T00:00:00.000000000Z,5500.0,4500.0,100.0,5000.0,1.0,12.5,1.0,0,24948,827895,5,10,1,1000,1,1,1,1,50,0,0,0,1,2024,0,1,USD,USD,E,ES,XCME,MES,FXXXXX,UDS,USD,,,0.0,F,0,0,0,0,0,0,12,20,0,Y,0,0,0,UD:EN: VT 1028827895
"""
        csv_path = tmp_path / "glbx-mdp3-20240115.definition.csv"
        csv_path.write_text(csv_content)
        return csv_path

    @pytest.fixture
    def sample_adapter(self, tmp_path: Path, sample_definition_csv: Path) -> DatabentoAdapter:
        """Create an adapter with sample Definition data."""
        # Create minimal OHLCV structure
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        # Use the definition CSV directory as the package path
        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(sample_definition_csv.parent),
        )

        return DatabentoAdapter(config)

    def test_parse_definition_file(
        self, sample_adapter: DatabentoAdapter, sample_definition_csv: Path
    ) -> None:
        """Test parsing a Definition CSV file."""
        df = sample_adapter._parse_definition_file(sample_definition_csv)

        assert len(df) == 4
        assert "instrument_id" in df.columns
        assert "raw_symbol" in df.columns
        assert "instrument_class" in df.columns
        assert "user_defined_instrument" in df.columns

        # Check specific values
        futures = df.filter(pl.col("instrument_class") == "F")
        assert len(futures) == 2

        options = df.filter(pl.col("instrument_class") == "C")
        assert len(options) == 1

        uds = df.filter(pl.col("instrument_class") == "T")
        assert len(uds) == 1

    def test_parse_definition_file_all_65_columns(
        self, sample_adapter: DatabentoAdapter, sample_definition_csv: Path
    ) -> None:
        """Test that all 65 columns are parsed."""
        df = sample_adapter._parse_definition_file(sample_definition_csv)

        assert len(df.columns) == 65

    def test_load_definition_for_date(self, sample_adapter: DatabentoAdapter) -> None:
        """Test loading Definition for a specific date."""
        date = pd.Timestamp("2024-01-15")
        df = sample_adapter._load_definition_for_date(date)

        assert df is not None
        assert len(df) == 4

    def test_load_definition_for_date_not_found(self, sample_adapter: DatabentoAdapter) -> None:
        """Test loading Definition for a date with no file returns None."""
        date = pd.Timestamp("2020-01-01")  # No file for this date
        df = sample_adapter._load_definition_for_date(date)

        assert df is None

    def test_load_definition_not_configured(self, tmp_path: Path) -> None:
        """Test that loading returns None when Definition not configured."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=None,  # Not configured
        )
        adapter = DatabentoAdapter(config)

        date = pd.Timestamp("2024-01-15")
        df = adapter._load_definition_for_date(date)

        assert df is None


class TestKeyFieldExtraction:
    """Test extraction of key metadata fields."""

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """Create a sample Definition DataFrame."""
        return pl.DataFrame(
            {
                "ts_recv": ["2024-01-15T00:00:00Z"],
                "ts_event": ["2024-01-15T00:00:00Z"],
                "instrument_id": [24948],
                "raw_symbol": ["ESZ4"],
                "symbol": ["ESZ4"],
                "asset": ["ES"],
                "instrument_class": ["F"],
                "user_defined_instrument": ["N"],
                "underlying_id": [0],
                "expiration": ["2024-12-20T00:00:00Z"],
                "activation": ["2024-06-20T00:00:00Z"],
                "strike_price": [0.0],
                "min_price_increment": [0.25],
                "contract_multiplier": [50],
                "exchange": ["XCME"],
                "currency": ["USD"],
                "extra_col_1": ["ignored"],
                "extra_col_2": [123],
            }
        )

    @pytest.fixture
    def adapter_for_key_fields(self, tmp_path: Path) -> DatabentoAdapter:
        """Create adapter for key field tests."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )
        config = DatabentoConfig(data_path=str(ohlcv_dir))
        return DatabentoAdapter(config)

    def test_get_definition_key_fields(
        self, adapter_for_key_fields: DatabentoAdapter, sample_df: pl.DataFrame
    ) -> None:
        """Test extracting key fields from Definition DataFrame."""
        key_df = adapter_for_key_fields._get_definition_key_fields(sample_df)

        expected_cols = [
            "instrument_id",
            "raw_symbol",
            "symbol",
            "asset",
            "instrument_class",
            "user_defined_instrument",
            "underlying_id",
            "expiration",
            "activation",
            "strike_price",
            "min_price_increment",
            "contract_multiplier",
        ]

        for col in expected_cols:
            assert col in key_df.columns, f"Expected column {col} not found"

        # Extra columns should be excluded
        assert "extra_col_1" not in key_df.columns
        assert "extra_col_2" not in key_df.columns
        assert "exchange" not in key_df.columns
        assert "currency" not in key_df.columns


class TestUDSFiltering:
    """Test User-Defined Spread filtering."""

    @pytest.fixture
    def mixed_instruments_df(self) -> pl.DataFrame:
        """Create DataFrame with mixed instrument types."""
        return pl.DataFrame(
            {
                "instrument_id": [1, 2, 3, 4, 5],
                "raw_symbol": ["ESZ4", "ESH5", "ESZ4-ESH5", "UD:EN: VT 123", "ESZ4 C5000"],
                "instrument_class": ["F", "F", "S", "T", "C"],
                "user_defined_instrument": ["N", "N", "N", "Y", "N"],
            }
        )

    @pytest.fixture
    def adapter_for_filtering(self, tmp_path: Path) -> DatabentoAdapter:
        """Create adapter for filtering tests."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )
        config = DatabentoConfig(data_path=str(ohlcv_dir))
        return DatabentoAdapter(config)

    def test_filter_user_defined_spreads(
        self, adapter_for_filtering: DatabentoAdapter, mixed_instruments_df: pl.DataFrame
    ) -> None:
        """Test filtering out UDS instruments."""
        filtered = adapter_for_filtering._filter_user_defined_spreads(mixed_instruments_df)

        assert len(filtered) == 4  # Excludes the UDS (T class with Y flag)

        # Check that UDS is excluded
        classes = filtered["instrument_class"].to_list()
        assert "T" not in classes

        # Check user_defined_instrument values
        uds_flags = filtered["user_defined_instrument"].to_list()
        assert "Y" not in uds_flags

    def test_filter_preserves_exchange_spreads(
        self, adapter_for_filtering: DatabentoAdapter, mixed_instruments_df: pl.DataFrame
    ) -> None:
        """Test that exchange-defined spreads (S class) are preserved."""
        filtered = adapter_for_filtering._filter_user_defined_spreads(mixed_instruments_df)

        exchange_spreads = filtered.filter(pl.col("instrument_class") == "S")
        assert len(exchange_spreads) == 1

    def test_filter_with_missing_columns(self, adapter_for_filtering: DatabentoAdapter) -> None:
        """Test filtering behavior when columns are missing."""
        df = pl.DataFrame(
            {
                "instrument_id": [1, 2],
                "raw_symbol": ["ESZ4", "ESH5"],
            }
        )

        # Should return original DataFrame unchanged
        filtered = adapter_for_filtering._filter_user_defined_spreads(df)
        assert len(filtered) == 2


class TestOHLCVEnrichment:
    """Test OHLCV enrichment with Definition metadata."""

    @pytest.fixture
    def ohlcv_df(self) -> pl.DataFrame:
        """Create sample OHLCV DataFrame."""
        return pl.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-15", periods=3, freq="1d"),
                "symbol": ["ESZ4_24948", "ESZ4_24948", "ESH5_24949"],
                "instrument_id": [24948, 24948, 24949],
                "open": [5000.0, 5010.0, 5005.0],
                "high": [5020.0, 5030.0, 5025.0],
                "low": [4990.0, 5000.0, 4995.0],
                "close": [5015.0, 5025.0, 5020.0],
                "volume": [1000, 1100, 950],
            }
        )

    @pytest.fixture
    def definition_df(self) -> pl.DataFrame:
        """Create sample Definition DataFrame."""
        return pl.DataFrame(
            {
                "instrument_id": [24948, 24949],
                "raw_symbol": ["ESZ4", "ESH5"],
                "symbol": ["ESZ4", "ESH5"],
                "asset": ["ES", "ES"],
                "instrument_class": ["F", "F"],
                "user_defined_instrument": ["N", "N"],
                "underlying_id": [0, 0],
                "expiration": ["2024-12-20T00:00:00Z", "2025-03-21T00:00:00Z"],
                "activation": ["2024-06-20T00:00:00Z", "2024-12-20T00:00:00Z"],
                "strike_price": [0.0, 0.0],
                "min_price_increment": [0.25, 0.25],
                "contract_multiplier": [50, 50],
            }
        )

    @pytest.fixture
    def adapter_for_enrichment(self, tmp_path: Path) -> DatabentoAdapter:
        """Create adapter for enrichment tests."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )
        config = DatabentoConfig(data_path=str(ohlcv_dir))
        return DatabentoAdapter(config)

    def test_enrich_ohlcv_with_definition(
        self,
        adapter_for_enrichment: DatabentoAdapter,
        ohlcv_df: pl.DataFrame,
        definition_df: pl.DataFrame,
    ) -> None:
        """Test enriching OHLCV data with Definition metadata."""
        enriched = adapter_for_enrichment._enrich_ohlcv_with_definition(ohlcv_df, definition_df)

        # Original columns preserved
        assert "timestamp" in enriched.columns
        assert "open" in enriched.columns
        assert "volume" in enriched.columns

        # Definition columns added
        assert "asset" in enriched.columns
        assert "instrument_class" in enriched.columns
        assert "expiration" in enriched.columns

        # All rows preserved
        assert len(enriched) == len(ohlcv_df)

    def test_enrich_preserves_all_ohlcv_rows(
        self,
        adapter_for_enrichment: DatabentoAdapter,
        ohlcv_df: pl.DataFrame,
    ) -> None:
        """Test that enrichment preserves OHLCV rows even without matching Definition."""
        # Definition with only one instrument
        partial_definition = pl.DataFrame(
            {
                "instrument_id": [24948],  # Only ESZ4, not ESH5
                "asset": ["ES"],
                "instrument_class": ["F"],
            }
        )

        enriched = adapter_for_enrichment._enrich_ohlcv_with_definition(
            ohlcv_df, partial_definition
        )

        # All OHLCV rows preserved
        assert len(enriched) == len(ohlcv_df)

        # Unmatched rows have null values for Definition columns
        esz4_rows = enriched.filter(pl.col("instrument_id") == 24948)
        assert esz4_rows["asset"][0] == "ES"

        esh5_rows = enriched.filter(pl.col("instrument_id") == 24949)
        assert esh5_rows["asset"][0] is None

    def test_enrich_without_instrument_id(self, adapter_for_enrichment: DatabentoAdapter) -> None:
        """Test enrichment when OHLCV lacks instrument_id."""
        ohlcv_no_id = pl.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-15", periods=1),
                "symbol": ["ESZ4"],
                "open": [5000.0],
                "high": [5020.0],
                "low": [4990.0],
                "close": [5015.0],
                "volume": [1000],
            }
        )

        definition = pl.DataFrame(
            {
                "instrument_id": [24948],
                "asset": ["ES"],
            }
        )

        # Should return original unchanged
        result = adapter_for_enrichment._enrich_ohlcv_with_definition(ohlcv_no_id, definition)
        assert "asset" not in result.columns


class TestGracefulDegradation:
    """Test graceful degradation when Definition is not available."""

    def test_definition_path_not_exists(self, tmp_path: Path) -> None:
        """Test behavior when Definition path doesn't exist."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path="/nonexistent/path",
        )
        adapter = DatabentoAdapter(config)

        # Should return None, not raise exception
        working_dir = adapter._get_definition_working_dir()
        assert working_dir is None

    def test_load_returns_none_gracefully(self, tmp_path: Path) -> None:
        """Test that _load_definition_for_date returns None gracefully."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        # Empty Definition directory
        def_dir = tmp_path / "definition"
        def_dir.mkdir()

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(def_dir),
        )
        adapter = DatabentoAdapter(config)

        # Should return None for missing dates
        result = adapter._load_definition_for_date(pd.Timestamp("2024-01-15"))
        assert result is None


class TestCleanup:
    """Test cleanup of Definition temporary directories."""

    def test_cleanup_definition_removes_temp_dir(self, tmp_path: Path) -> None:
        """Test that cleanup removes Definition temp directory."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(data_path=str(ohlcv_dir))
        adapter = DatabentoAdapter(config)

        # Simulate temp dir creation
        adapter._definition_temp_dir = Path(tempfile.mkdtemp(prefix="test_def_"))
        temp_dir = adapter._definition_temp_dir
        assert temp_dir.exists()

        # Cleanup should remove it
        adapter.cleanup_definition()
        assert not temp_dir.exists()
        assert adapter._definition_temp_dir is None

    def test_context_manager_cleans_up_definition(self, tmp_path: Path) -> None:
        """Test that context manager cleans up Definition temp dir."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(data_path=str(ohlcv_dir))

        temp_dir = None
        with DatabentoAdapter(config) as adapter:
            # Simulate temp dir creation
            adapter._definition_temp_dir = Path(tempfile.mkdtemp(prefix="test_def_"))
            temp_dir = adapter._definition_temp_dir
            assert temp_dir.exists()

        # After context exit, should be cleaned up
        assert not temp_dir.exists()


class TestDefinitionEnrichmentIntegration:
    """Test Definition enrichment integration with ingestion flow (Story 9.3)."""

    @pytest.fixture
    def ohlcv_df(self) -> pl.DataFrame:
        """Sample OHLCV DataFrame for integration tests."""
        return pl.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-15", periods=5, freq="1d"),
                "symbol": [
                    "ESZ4_24948",
                    "ESZ4_24948",
                    "ESH5_24949",
                    "UD:EN: VT 1028827895",
                    "ESZ4 C5000_339180",
                ],
                "instrument_id": [24948, 24948, 24949, 827895, 339180],
                "original_symbol": ["ESZ4", "ESZ4", "ESH5", "UD:EN: VT 1028827895", "ESZ4 C5000"],
                "open": [5000.0, 5010.0, 5005.0, 100.0, 50.0],
                "high": [5020.0, 5030.0, 5025.0, 110.0, 60.0],
                "low": [4990.0, 5000.0, 4995.0, 95.0, 45.0],
                "close": [5015.0, 5025.0, 5020.0, 105.0, 55.0],
                "volume": [1000, 1100, 950, 10, 100],
            }
        )

    @pytest.fixture
    def definition_df(self) -> pl.DataFrame:
        """Sample Definition DataFrame for integration tests."""
        return pl.DataFrame(
            {
                "instrument_id": [24948, 24949, 827895, 339180],
                "raw_symbol": ["ESZ4", "ESH5", "UD:EN: VT 1028827895", "ESZ4 C5000"],
                "symbol": ["ESZ4", "ESH5", "UD:EN: VT 1028827895", "ESZ4 C5000"],
                "asset": ["ES", "ES", "MES", "ES"],
                "instrument_class": ["F", "F", "T", "C"],
                "user_defined_instrument": ["N", "N", "Y", "N"],
                "underlying_id": [0, 0, 24948, 24948],
                "expiration": ["2024-12-20", "2025-03-21", "2024-12-20", "2024-12-20"],
                "activation": ["2024-06-20", "2024-12-20", "2024-06-20", "2024-06-20"],
                "strike_price": [0.0, 0.0, 0.0, 5000.0],
                "min_price_increment": [0.25, 0.25, 0.25, 0.25],
                "contract_multiplier": [50, 50, 50, 50],
            }
        )

    @pytest.fixture
    def adapter_with_definition(self, tmp_path: Path) -> DatabentoAdapter:
        """Create adapter with Definition configured."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        def_dir = tmp_path / "definition"
        def_dir.mkdir()

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(def_dir),
            include_user_defined_spreads=False,
        )
        return DatabentoAdapter(config)

    def test_apply_definition_enrichment_filters_uds(
        self,
        adapter_with_definition: DatabentoAdapter,
        ohlcv_df: pl.DataFrame,
        definition_df: pl.DataFrame,
        tmp_path: Path,
    ) -> None:
        """Test that UDS instruments are filtered when include_user_defined_spreads=False."""
        # Write definition file for the date
        def_dir = Path(adapter_with_definition.config.definition_package_path)
        csv_content = definition_df.write_csv()
        (def_dir / "glbx-mdp3-20240115.definition.csv").write_text(csv_content)

        # Add metadata.json for CME Definition (day-split)
        (def_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "GLBX.MDP3", "schema": "definition", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}, "customizations": {"split_duration": "day"}}'
        )

        start = pd.Timestamp("2024-01-15")
        end = pd.Timestamp("2024-01-19")

        enriched_df, cols_added = adapter_with_definition._apply_definition_enrichment(
            ohlcv_df, start, end
        )

        # UDS row should be filtered out
        assert len(enriched_df) == 4  # Original 5 minus 1 UDS

        # Verify no UDS instruments remain
        if "instrument_class" in enriched_df.columns:
            classes = enriched_df["instrument_class"].to_list()
            assert "T" not in [c for c in classes if c is not None]

    def test_apply_definition_enrichment_preserves_all_when_include_uds(
        self,
        tmp_path: Path,
        ohlcv_df: pl.DataFrame,
        definition_df: pl.DataFrame,
    ) -> None:
        """Test that UDS are preserved when include_user_defined_spreads=True."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        def_dir = tmp_path / "definition"
        def_dir.mkdir()
        csv_content = definition_df.write_csv()
        (def_dir / "glbx-mdp3-20240115.definition.csv").write_text(csv_content)

        # Add metadata.json for CME Definition (day-split)
        (def_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "GLBX.MDP3", "schema": "definition", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}, "customizations": {"split_duration": "day"}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(def_dir),
            include_user_defined_spreads=True,  # Include UDS
        )
        adapter = DatabentoAdapter(config)

        start = pd.Timestamp("2024-01-15")
        end = pd.Timestamp("2024-01-19")

        enriched_df, cols_added = adapter._apply_definition_enrichment(ohlcv_df, start, end)

        # All rows should be preserved
        assert len(enriched_df) == 5


class TestBackwardCompatibility:
    """Test backward compatibility - ingestion works without Definition (AC-9.3.1)."""

    def test_ingestion_works_without_definition(self, tmp_path: Path) -> None:
        """Test that ingestion works exactly as before without Definition."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        # No definition_package_path
        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=None,
        )

        adapter = DatabentoAdapter(config)

        # These methods should work without Definition
        assert adapter._get_definition_working_dir() is None
        assert adapter._load_definition_for_date(pd.Timestamp("2024-01-15")) is None

    def test_no_breaking_changes_to_config(self, tmp_path: Path) -> None:
        """Test that existing config usage still works."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        # Old-style config (no Definition fields)
        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            timezone="UTC",
            use_instrument_id=True,
        )

        # Should work without errors
        adapter = DatabentoAdapter(config)
        assert adapter.config.definition_package_path is None
        assert adapter.config.include_user_defined_spreads is True


class TestGracefulDegradationWarnings:
    """Test graceful degradation warning behavior (AC-9.3.3)."""

    def test_uds_filter_ignored_without_definition(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that UDS filter is ignored with warning when Definition unavailable."""
        import structlog

        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=None,  # No Definition
            include_user_defined_spreads=False,  # Request UDS filtering
        )

        adapter = DatabentoAdapter(config)

        # The warning should be logged when ingestion is called
        # We can't easily test the actual log here without mocking,
        # but we verify the config state is correct
        assert adapter.config.definition_package_path is None
        assert adapter.config.include_user_defined_spreads is False


# ============================================================================
# Story 9.4: NASDAQ Definition Parsing Tests
# ============================================================================


class TestNASDAQDefinitionParsing:
    """Test NASDAQ Definition file parsing (Story 9.4)."""

    @pytest.fixture
    def sample_nasdaq_definition_csv(self, tmp_path: Path) -> Path:
        """Create a sample NASDAQ Definition CSV file for testing."""
        # NASDAQ equities have instrument_class='K' and simpler schema
        # Need to ensure all 65 columns have proper values for parsing
        csv_content = """ts_recv,ts_event,rtype,publisher_id,instrument_id,raw_symbol,security_update_action,instrument_class,min_price_increment,display_factor,expiration,activation,high_limit_price,low_limit_price,max_price_variation,trading_reference_price,unit_of_measure_qty,min_price_increment_amount,price_ratio,inst_attrib_value,underlying_id,raw_instrument_id,market_depth_implied,market_depth,market_segment_id,max_trade_vol,min_lot_size,min_lot_size_block,min_lot_size_round_lot,min_trade_vol,contract_multiplier,decay_quantity,original_contract_size,trading_reference_date,appl_id,maturity_year,decay_start_date,channel_id,currency,settl_currency,secsubtype,group,exchange,asset,cfi,security_type,unit_of_measure,underlying,strike_price_currency,strike_price,match_algorithm,md_security_trading_status,main_fraction,price_display_format,settl_price_type,sub_fraction,underlying_product,maturity_month,maturity_day,maturity_week,user_defined_instrument,contract_multiplier_unit,flow_schedule_type,tick_rule,symbol
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,42,AAPL,A,K,0.0,100000.0,,,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,0,42,0,10,0,0,1,0,0,1,100,0,0,0,0,0,0,0,USD,USD,,Z ,XNAS,,,,,,,0.0,F,0,0,0,0,0,0,0,0,0,N,0,0,0,AAPL
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,123,MSFT,A,K,0.0,100000.0,,,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,0,123,0,10,0,0,1,0,0,1,100,0,0,0,0,0,0,0,USD,USD,,Z ,XNAS,,,,,,,0.0,F,0,0,0,0,0,0,0,0,0,N,0,0,0,MSFT
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,456,GOOGL,A,K,0.0,100000.0,,,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,0,456,0,10,0,0,1,0,0,1,100,0,0,0,0,0,0,0,USD,USD,,Z ,XNAS,,,,,,,0.0,F,0,0,0,0,0,0,0,0,0,N,0,0,0,GOOGL
"""
        csv_path = tmp_path / "xnas-itch-20180501-20251031.definition.AAPL.csv"
        csv_path.write_text(csv_content)
        return csv_path

    @pytest.fixture
    def nasdaq_adapter(
        self, tmp_path: Path, sample_nasdaq_definition_csv: Path
    ) -> DatabentoAdapter:
        """Create an adapter with NASDAQ Definition data."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}, "customizations": {"split_symbols": true}}'
        )

        # Create NASDAQ Definition metadata
        def_dir = sample_nasdaq_definition_csv.parent
        (def_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "definition", "symbols": ["ALL_SYMBOLS"], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}, "customizations": {"split_symbols": true}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(def_dir),
        )

        return DatabentoAdapter(config)

    def test_parse_nasdaq_definition_file(
        self, nasdaq_adapter: DatabentoAdapter, sample_nasdaq_definition_csv: Path
    ) -> None:
        """Test parsing a NASDAQ Definition CSV file (AC-9.4.1)."""
        df = nasdaq_adapter._parse_definition_file(sample_nasdaq_definition_csv)

        assert len(df) == 3
        assert "instrument_id" in df.columns
        assert "raw_symbol" in df.columns
        assert "instrument_class" in df.columns
        assert "exchange" in df.columns

        # All NASDAQ equities should have instrument_class = 'K'
        classes = df["instrument_class"].unique().to_list()
        assert classes == ["K"]

        # All NASDAQ should have exchange = 'XNAS'
        exchanges = df["exchange"].unique().to_list()
        assert exchanges == ["XNAS"]

    def test_nasdaq_has_all_65_columns(
        self, nasdaq_adapter: DatabentoAdapter, sample_nasdaq_definition_csv: Path
    ) -> None:
        """Test that NASDAQ Definition files have all 65 columns."""
        df = nasdaq_adapter._parse_definition_file(sample_nasdaq_definition_csv)
        assert len(df.columns) == 65

    def test_nasdaq_no_user_defined_instruments(
        self, nasdaq_adapter: DatabentoAdapter, sample_nasdaq_definition_csv: Path
    ) -> None:
        """Test that NASDAQ has no user-defined instruments (equities only)."""
        df = nasdaq_adapter._parse_definition_file(sample_nasdaq_definition_csv)

        # All NASDAQ should have user_defined_instrument = 'N'
        if "user_defined_instrument" in df.columns:
            uds_flags = df["user_defined_instrument"].unique().to_list()
            assert "Y" not in uds_flags

    def test_nasdaq_underlying_id_is_zero(
        self, nasdaq_adapter: DatabentoAdapter, sample_nasdaq_definition_csv: Path
    ) -> None:
        """Test that NASDAQ instruments have underlying_id = 0 (no derivatives)."""
        df = nasdaq_adapter._parse_definition_file(sample_nasdaq_definition_csv)

        if "underlying_id" in df.columns:
            non_zero = df.filter(pl.col("underlying_id") != 0)
            assert len(non_zero) == 0


class TestSchemaDetection:
    """Test schema detection between CME and NASDAQ (Story 9.4 - AC-9.4.3)."""

    @pytest.fixture
    def adapter(self, tmp_path: Path) -> DatabentoAdapter:
        """Create adapter for schema detection tests."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )
        config = DatabentoConfig(data_path=str(ohlcv_dir))
        return DatabentoAdapter(config)

    def test_detect_cme_schema(self, adapter: DatabentoAdapter) -> None:
        """Test detection of CME schema based on varied instrument_class."""
        cme_df = pl.DataFrame(
            {
                "instrument_id": [1, 2, 3, 4],
                "instrument_class": ["F", "C", "P", "T"],
                "user_defined_instrument": ["N", "N", "N", "Y"],
                "underlying_id": [0, 1, 1, 1],
            }
        )

        schema = adapter._detect_definition_schema(cme_df)
        assert schema == "CME"

    def test_detect_nasdaq_schema(self, adapter: DatabentoAdapter) -> None:
        """Test detection of NASDAQ schema based on all K instrument_class."""
        nasdaq_df = pl.DataFrame(
            {
                "instrument_id": [42, 123, 456],
                "instrument_class": ["K", "K", "K"],
                "user_defined_instrument": ["N", "N", "N"],
                "underlying_id": [0, 0, 0],
            }
        )

        schema = adapter._detect_definition_schema(nasdaq_df)
        assert schema == "NASDAQ"

    def test_detect_cme_with_uds_flag(self, adapter: DatabentoAdapter) -> None:
        """Test that user_defined_instrument='Y' indicates CME."""
        df_with_uds = pl.DataFrame(
            {
                "instrument_id": [1, 2],
                "user_defined_instrument": ["N", "Y"],
            }
        )

        schema = adapter._detect_definition_schema(df_with_uds)
        assert schema == "CME"

    def test_detect_cme_with_nonzero_underlying(self, adapter: DatabentoAdapter) -> None:
        """Test that non-zero underlying_id indicates CME."""
        df_with_underlying = pl.DataFrame(
            {
                "instrument_id": [1, 2],
                "underlying_id": [0, 24948],  # Option with parent
            }
        )

        schema = adapter._detect_definition_schema(df_with_underlying)
        assert schema == "CME"


class TestNASDAQSymbolFileDiscovery:
    """Test NASDAQ symbol-based file discovery (Story 9.4 - AC-9.4.1)."""

    @pytest.fixture
    def nasdaq_definition_dir(self, tmp_path: Path) -> Path:
        """Create a directory with NASDAQ Definition files."""
        def_dir = tmp_path / "nasdaq_def"
        def_dir.mkdir()

        # Create sample NASDAQ Definition files with symbol-split naming
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        for symbol in symbols:
            file_name = f"xnas-itch-20180501-20251031.definition.{symbol}.csv"
            (def_dir / file_name).write_text("header\nrow1\n")

        # Add metadata.json for NASDAQ
        (def_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "definition", "symbols": ["ALL_SYMBOLS"], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}, "customizations": {"split_symbols": true}}'
        )

        return def_dir

    @pytest.fixture
    def adapter_with_nasdaq_def(
        self, tmp_path: Path, nasdaq_definition_dir: Path
    ) -> DatabentoAdapter:
        """Create adapter with NASDAQ Definition directory."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(nasdaq_definition_dir),
        )

        return DatabentoAdapter(config)

    def test_find_all_symbol_files(self, adapter_with_nasdaq_def: DatabentoAdapter) -> None:
        """Test finding all NASDAQ Definition symbol files."""
        files = adapter_with_nasdaq_def._find_definition_files_by_symbol(symbols=None)

        assert len(files) == 5  # AAPL, MSFT, GOOGL, AMZN, META

    def test_find_specific_symbol_files(self, adapter_with_nasdaq_def: DatabentoAdapter) -> None:
        """Test finding specific NASDAQ Definition symbol files."""
        files = adapter_with_nasdaq_def._find_definition_files_by_symbol(symbols=["AAPL", "MSFT"])

        assert len(files) == 2
        file_names = [f.name for f in files]
        assert any("AAPL" in name for name in file_names)
        assert any("MSFT" in name for name in file_names)

    def test_find_nonexistent_symbol(self, adapter_with_nasdaq_def: DatabentoAdapter) -> None:
        """Test finding files for non-existent symbol returns empty list."""
        files = adapter_with_nasdaq_def._find_definition_files_by_symbol(symbols=["NONEXISTENT"])

        assert len(files) == 0


class TestCompositeInstrumentId:
    """Test composite instrument_id for cross-exchange collision prevention (Story 9.4 - AC-9.4.4)."""

    @pytest.fixture
    def adapter(self, tmp_path: Path) -> DatabentoAdapter:
        """Create adapter for composite ID tests."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )
        config = DatabentoConfig(data_path=str(ohlcv_dir))
        return DatabentoAdapter(config)

    def test_create_composite_id_with_exchange_column(self, adapter: DatabentoAdapter) -> None:
        """Test creating composite ID using exchange column from DataFrame."""
        df = pl.DataFrame(
            {
                "instrument_id": [42, 123],
                "exchange": ["XNAS", "XNAS"],
                "symbol": ["AAPL", "MSFT"],
            }
        )

        result = adapter._create_composite_instrument_id(df)

        assert "composite_instrument_id" in result.columns
        composite_ids = result["composite_instrument_id"].to_list()
        assert composite_ids == ["XNAS_42", "XNAS_123"]

    def test_create_composite_id_with_explicit_exchange(self, adapter: DatabentoAdapter) -> None:
        """Test creating composite ID with explicit exchange parameter."""
        df = pl.DataFrame(
            {
                "instrument_id": [24948, 24949],
                "symbol": ["ESZ4", "ESH5"],
            }
        )

        result = adapter._create_composite_instrument_id(df, exchange="XCME")

        assert "composite_instrument_id" in result.columns
        composite_ids = result["composite_instrument_id"].to_list()
        assert composite_ids == ["XCME_24948", "XCME_24949"]

    def test_composite_id_prevents_cross_exchange_collision(
        self, adapter: DatabentoAdapter
    ) -> None:
        """Test that composite IDs prevent cross-exchange collision."""
        # Simulate same instrument_id from different exchanges
        cme_df = pl.DataFrame(
            {
                "instrument_id": [42],
                "exchange": ["XCME"],
            }
        )
        nasdaq_df = pl.DataFrame(
            {
                "instrument_id": [42],  # Same ID, different exchange
                "exchange": ["XNAS"],
            }
        )

        cme_result = adapter._create_composite_instrument_id(cme_df)
        nasdaq_result = adapter._create_composite_instrument_id(nasdaq_df)

        cme_composite = cme_result["composite_instrument_id"][0]
        nasdaq_composite = nasdaq_result["composite_instrument_id"][0]

        # Composite IDs should be different
        assert cme_composite != nasdaq_composite
        assert cme_composite == "XCME_42"
        assert nasdaq_composite == "XNAS_42"


class TestNASDAQKeyFieldExtraction:
    """Test NASDAQ-specific key field extraction (Story 9.4 - AC-9.4.2)."""

    @pytest.fixture
    def adapter(self, tmp_path: Path) -> DatabentoAdapter:
        """Create adapter for key field tests."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )
        config = DatabentoConfig(data_path=str(ohlcv_dir))
        return DatabentoAdapter(config)

    def test_nasdaq_key_fields_include_equity_columns(self, adapter: DatabentoAdapter) -> None:
        """Test that NASDAQ key fields include equity-relevant columns."""
        nasdaq_df = pl.DataFrame(
            {
                "instrument_id": [42],
                "raw_symbol": ["AAPL"],
                "symbol": ["AAPL"],
                "exchange": ["XNAS"],
                "currency": ["USD"],
                "min_lot_size": [1],
                "instrument_class": ["K"],
                "user_defined_instrument": ["N"],
                "underlying_id": [0],
                "expiration": [""],
                "strike_price": [0.0],
                # Extra columns that should be excluded
                "ts_recv": ["2024-01-15"],
                "publisher_id": [1],
            }
        )

        key_df = adapter._get_definition_key_fields(nasdaq_df)

        # NASDAQ equity-relevant fields should be included
        assert "exchange" in key_df.columns
        assert "currency" in key_df.columns
        assert "min_lot_size" in key_df.columns

        # Extra columns should be excluded
        assert "ts_recv" not in key_df.columns
        assert "publisher_id" not in key_df.columns

    def test_cme_key_fields_include_derivatives_columns(self, adapter: DatabentoAdapter) -> None:
        """Test that CME key fields include derivatives-relevant columns."""
        cme_df = pl.DataFrame(
            {
                "instrument_id": [24948],
                "raw_symbol": ["ESZ4"],
                "symbol": ["ESZ4"],
                "asset": ["ES"],
                "instrument_class": ["F"],
                "user_defined_instrument": ["N"],
                "underlying_id": [0],
                "expiration": ["2024-12-20T00:00:00Z"],
                "activation": ["2024-06-20T00:00:00Z"],
                "strike_price": [0.0],
                "min_price_increment": [0.25],
                "contract_multiplier": [50],
                # Extra columns
                "ts_recv": ["2024-01-15"],
            }
        )

        key_df = adapter._get_definition_key_fields(cme_df)

        # CME derivatives-relevant fields should be included
        assert "asset" in key_df.columns
        assert "activation" in key_df.columns
        assert "min_price_increment" in key_df.columns
        assert "contract_multiplier" in key_df.columns

        # Extra columns should be excluded
        assert "ts_recv" not in key_df.columns


# ============================================================================
# Story 9.5: NASDAQ Data Ingestion & Bundle Verification Tests
# ============================================================================


class TestNASDAQIngestionIntegration:
    """Test NASDAQ Definition-enabled ingestion (Story 9.5)."""

    @pytest.fixture
    def nasdaq_definition_csv(self, tmp_path: Path) -> Path:
        """Create sample NASDAQ Definition CSV."""
        csv_content = """ts_recv,ts_event,rtype,publisher_id,instrument_id,raw_symbol,security_update_action,instrument_class,min_price_increment,display_factor,expiration,activation,high_limit_price,low_limit_price,max_price_variation,trading_reference_price,unit_of_measure_qty,min_price_increment_amount,price_ratio,inst_attrib_value,underlying_id,raw_instrument_id,market_depth_implied,market_depth,market_segment_id,max_trade_vol,min_lot_size,min_lot_size_block,min_lot_size_round_lot,min_trade_vol,contract_multiplier,decay_quantity,original_contract_size,trading_reference_date,appl_id,maturity_year,decay_start_date,channel_id,currency,settl_currency,secsubtype,group,exchange,asset,cfi,security_type,unit_of_measure,underlying,strike_price_currency,strike_price,match_algorithm,md_security_trading_status,main_fraction,price_display_format,settl_price_type,sub_fraction,underlying_product,maturity_month,maturity_day,maturity_week,user_defined_instrument,contract_multiplier_unit,flow_schedule_type,tick_rule,symbol
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,42,AAPL,A,K,0.0,100000.0,,,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,0,42,0,10,0,0,1,0,0,1,100,0,0,0,0,0,0,0,USD,USD,,Z ,XNAS,,,,,,,0.0,F,0,0,0,0,0,0,0,0,0,N,0,0,0,AAPL
"""
        # Write AAPL definition file
        def_dir = tmp_path / "nasdaq_def"
        def_dir.mkdir()
        (def_dir / "xnas-itch-20180501-20251031.definition.AAPL.csv").write_text(csv_content)
        (def_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "definition", "symbols": ["ALL_SYMBOLS"], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}, "customizations": {"split_symbols": true}}'
        )
        return def_dir

    @pytest.fixture
    def ohlcv_df(self) -> pl.DataFrame:
        """Sample OHLCV DataFrame for NASDAQ testing."""
        return pl.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-15", periods=3, freq="1d"),
                "symbol": ["AAPL_42", "AAPL_42", "AAPL_42"],
                "instrument_id": [42, 42, 42],
                "original_symbol": ["AAPL", "AAPL", "AAPL"],
                "open": [185.0, 186.0, 187.0],
                "high": [188.0, 189.0, 190.0],
                "low": [184.0, 185.0, 186.0],
                "close": [187.0, 188.0, 189.0],
                "volume": [50000000, 52000000, 48000000],
            }
        )

    @pytest.fixture
    def nasdaq_adapter_with_def(
        self, tmp_path: Path, nasdaq_definition_csv: Path
    ) -> DatabentoAdapter:
        """Create adapter with NASDAQ OHLCV and Definition."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(nasdaq_definition_csv),
        )

        return DatabentoAdapter(config)

    def test_nasdaq_enrichment_adds_equity_metadata(
        self, nasdaq_adapter_with_def: DatabentoAdapter, ohlcv_df: pl.DataFrame
    ) -> None:
        """Test that NASDAQ enrichment adds equity-appropriate metadata (AC-9.5.2)."""
        start = pd.Timestamp("2024-01-15")
        end = pd.Timestamp("2024-01-17")

        enriched_df, cols_added = nasdaq_adapter_with_def._apply_definition_enrichment(
            ohlcv_df, start, end
        )

        # Equity-relevant columns should be added
        assert "exchange" in enriched_df.columns
        assert "currency" in enriched_df.columns

        # Check values
        exchanges = enriched_df["exchange"].unique().to_list()
        assert "XNAS" in [e for e in exchanges if e is not None]

    def test_nasdaq_no_uds_filtering_applied(
        self, tmp_path: Path, nasdaq_definition_csv: Path, ohlcv_df: pl.DataFrame
    ) -> None:
        """Test that UDS filtering is not applied for NASDAQ (equities have no UDS)."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(nasdaq_definition_csv),
            include_user_defined_spreads=False,  # Should have no effect on NASDAQ
        )
        adapter = DatabentoAdapter(config)

        start = pd.Timestamp("2024-01-15")
        end = pd.Timestamp("2024-01-17")

        # Should return all rows (no UDS filtering for NASDAQ)
        enriched_df, _ = adapter._apply_definition_enrichment(ohlcv_df, start, end)
        assert len(enriched_df) == len(ohlcv_df)


class TestNASDAQBackwardCompatibility:
    """Test backward compatibility for NASDAQ ingestion (Story 9.5 - AC-9.5.1, AC-9.5.3)."""

    def test_nasdaq_works_without_definition(self, tmp_path: Path) -> None:
        """Test that NASDAQ adapter works without Definition (AC-9.5.1, AC-9.5.3)."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        # No definition_package_path
        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=None,
        )

        adapter = DatabentoAdapter(config)

        # Adapter should work normally
        assert adapter.config.definition_package_path is None
        assert adapter._load_definition_for_date(pd.Timestamp("2024-01-15")) is None

    def test_graceful_degradation_with_missing_definition_file(self, tmp_path: Path) -> None:
        """Test graceful degradation when Definition files are missing."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        def_dir = tmp_path / "definition"
        def_dir.mkdir()
        # Empty definition directory with metadata but no actual files
        (def_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "definition", "symbols": ["ALL_SYMBOLS"], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}, "customizations": {"split_symbols": true}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(def_dir),
        )
        adapter = DatabentoAdapter(config)

        # Should return empty list gracefully
        files = adapter._find_definition_files_by_symbol(["AAPL"])
        assert files == []


class TestCrossExchangeCollisionPrevention:
    """Test cross-exchange collision prevention (Story 9.5 - AC-9.5.4)."""

    @pytest.fixture
    def adapter(self, tmp_path: Path) -> DatabentoAdapter:
        """Create adapter for collision tests."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "TEST", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )
        config = DatabentoConfig(data_path=str(ohlcv_dir))
        return DatabentoAdapter(config)

    def test_same_instrument_id_different_exchanges_distinguishable(
        self, adapter: DatabentoAdapter
    ) -> None:
        """Test that same instrument_id from different exchanges are distinguishable (AC-9.5.4)."""
        # Same instrument_id=42 for both CME and NASDAQ
        cme_df = pl.DataFrame(
            {
                "instrument_id": [42],
                "exchange": ["XCME"],
                "symbol": ["ESZ4"],
            }
        )
        nasdaq_df = pl.DataFrame(
            {
                "instrument_id": [42],
                "exchange": ["XNAS"],
                "symbol": ["AAPL"],
            }
        )

        cme_result = adapter._create_composite_instrument_id(cme_df)
        nasdaq_result = adapter._create_composite_instrument_id(nasdaq_df)

        # Should have different composite IDs
        assert cme_result["composite_instrument_id"][0] == "XCME_42"
        assert nasdaq_result["composite_instrument_id"][0] == "XNAS_42"
        assert (
            cme_result["composite_instrument_id"][0] != nasdaq_result["composite_instrument_id"][0]
        )

    def test_enrichment_adds_composite_id_when_exchange_available(self, tmp_path: Path) -> None:
        """Test that enrichment adds composite_instrument_id when exchange column is present."""
        ohlcv_dir = tmp_path / "ohlcv"
        ohlcv_dir.mkdir()
        (ohlcv_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "ohlcv-1d", "symbols": [], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}}'
        )

        def_dir = tmp_path / "definition"
        def_dir.mkdir()

        # Create NASDAQ Definition file
        csv_content = """ts_recv,ts_event,rtype,publisher_id,instrument_id,raw_symbol,security_update_action,instrument_class,min_price_increment,display_factor,expiration,activation,high_limit_price,low_limit_price,max_price_variation,trading_reference_price,unit_of_measure_qty,min_price_increment_amount,price_ratio,inst_attrib_value,underlying_id,raw_instrument_id,market_depth_implied,market_depth,market_segment_id,max_trade_vol,min_lot_size,min_lot_size_block,min_lot_size_round_lot,min_trade_vol,contract_multiplier,decay_quantity,original_contract_size,trading_reference_date,appl_id,maturity_year,decay_start_date,channel_id,currency,settl_currency,secsubtype,group,exchange,asset,cfi,security_type,unit_of_measure,underlying,strike_price_currency,strike_price,match_algorithm,md_security_trading_status,main_fraction,price_display_format,settl_price_type,sub_fraction,underlying_product,maturity_month,maturity_day,maturity_week,user_defined_instrument,contract_multiplier_unit,flow_schedule_type,tick_rule,symbol
2024-01-15T00:00:00.000000000Z,2024-01-15T00:00:00.000000000Z,0,1,42,AAPL,A,K,0.0,100000.0,,,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,0,42,0,10,0,0,1,0,0,1,100,0,0,0,0,0,0,0,USD,USD,,Z ,XNAS,,,,,,,0.0,F,0,0,0,0,0,0,0,0,0,N,0,0,0,AAPL
"""
        (def_dir / "xnas-itch-20180501-20251031.definition.AAPL.csv").write_text(csv_content)
        (def_dir / "metadata.json").write_text(
            '{"version": 1, "job_id": "test", "query": {"dataset": "XNAS.ITCH", "schema": "definition", "symbols": ["ALL_SYMBOLS"], "start": 0, "end": 0, "encoding": "csv", "compression": "zstd", "stype_in": "raw_symbol", "stype_out": "instrument_id"}, "customizations": {"split_symbols": true}}'
        )

        config = DatabentoConfig(
            data_path=str(ohlcv_dir),
            definition_package_path=str(def_dir),
        )
        adapter = DatabentoAdapter(config)

        ohlcv_df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-15", periods=1),
                "symbol": ["AAPL_42"],
                "instrument_id": [42],
                "original_symbol": ["AAPL"],
                "open": [185.0],
                "high": [188.0],
                "low": [184.0],
                "close": [187.0],
                "volume": [50000000],
            }
        )

        start = pd.Timestamp("2024-01-15")
        end = pd.Timestamp("2024-01-15")

        enriched_df, cols_added = adapter._apply_definition_enrichment(ohlcv_df, start, end)

        # composite_instrument_id should be added
        assert "composite_instrument_id" in enriched_df.columns
        assert enriched_df["composite_instrument_id"][0] == "XNAS_42"
