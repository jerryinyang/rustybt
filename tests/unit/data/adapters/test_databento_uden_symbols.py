"""
Tests for Databento adapter UD:EN symbol handling.

Ensures that UD:EN (user-defined) symbols that already contain instrument_id
do not get redundant instrument_id appended, while conventional symbols
continue to work correctly.

Author: Claude Code / James (dev agent)
Date: 2025-11-03
"""

import polars as pl
import pytest

from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig


class TestUDENSymbolDetection:
    """Test UD:EN symbol pattern detection and handling."""

    def test_uden_symbol_no_redundant_id(self, tmp_path):
        """UD:EN symbols should NOT get redundant instrument_id appended.

        Pattern: UD:EN: [TYPE] [DATE][INSTRUMENT_ID]
        Example: "UD:EN: VT 1102869979" where instrument_id=869979
        Expected: Symbol remains "UD:EN: VT 1102869979" (no _869979 appended)
        """
        # Create sample UD:EN data matching real Databento format
        sample_data = pl.DataFrame(
            {
                "ts_event": ["2020-11-02T07:00:00.000000000Z", "2020-11-02T08:00:00.000000000Z"],
                "rtype": [34, 34],
                "publisher_id": [1, 1],
                "instrument_id": [869979, 865600],
                "open": [1.5, 2.0],
                "high": [1.6, 2.1],
                "low": [1.4, 1.9],
                "close": [1.5, 2.0],
                "volume": [100, 200],
                "symbol": ["UD:EN: VT 1102869979", "UD:EN: SG 1102865600"],
            }
        )

        # Save to CSV with OHLCV naming pattern expected by adapter
        csv_path = tmp_path / "test.ohlcv-1h.csv"
        sample_data.write_csv(csv_path)

        # Create adapter config (point to directory, not file)
        config = DatabentoConfig(
            data_path=str(tmp_path),
            use_instrument_id=True,
            symbol_format="symbol_id",
        )

        # Parse OHLCV (this will trigger symbol processing)
        adapter = DatabentoAdapter(config)
        df = adapter._parse_ohlcv_csv()

        # Verify UD:EN symbols are NOT redundant
        assert "UD:EN: VT 1102869979" in df["symbol"].to_list()
        assert "UD:EN: SG 1102865600" in df["symbol"].to_list()

        # Verify redundant format does NOT exist
        assert "UD:EN: VT 1102869979_869979" not in df["symbol"].to_list()
        assert "UD:EN: SG 1102865600_865600" not in df["symbol"].to_list()

        # Verify instrument_id preserved in extra columns
        assert "instrument_id" in df.columns
        assert 869979 in df["instrument_id"].to_list()
        assert 865600 in df["instrument_id"].to_list()

    def test_conventional_symbol_gets_id(self, tmp_path):
        """Conventional symbols SHOULD get instrument_id appended.

        Example: "6AZ0" with instrument_id=108078
        Expected: Symbol becomes "6AZ0_108078"
        """
        # Create sample conventional symbol data
        sample_data = pl.DataFrame(
            {
                "ts_event": ["2020-11-01T23:00:00.000000000Z", "2020-11-01T23:00:00.000000000Z"],
                "rtype": [34, 34],
                "publisher_id": [1, 1],
                "instrument_id": [108078, 19100],
                "open": [0.702, 3250.0],
                "high": [0.703, 3260.0],
                "low": [0.700, 3234.0],
                "close": [0.701, 3244.0],
                "volume": [5628, 59],
                "symbol": ["6AZ0", "ESZ0"],
            }
        )

        # Save to CSV with OHLCV naming pattern
        csv_path = tmp_path / "test.ohlcv-1h.csv"
        sample_data.write_csv(csv_path)

        # Create adapter config (point to directory)
        config = DatabentoConfig(
            data_path=str(tmp_path),
            use_instrument_id=True,
            symbol_format="symbol_id",
        )

        # Parse OHLCV
        adapter = DatabentoAdapter(config)
        df = adapter._parse_ohlcv_csv()

        # Verify conventional symbols GET instrument_id appended
        assert "6AZ0_108078" in df["symbol"].to_list()
        assert "ESZ0_19100" in df["symbol"].to_list()

        # Verify original symbols are NOT present (replaced with composite)
        assert "6AZ0" not in df["symbol"].to_list()
        assert "ESZ0" not in df["symbol"].to_list()

        # Verify original_symbol column preserves the original
        assert "6AZ0" in df["original_symbol"].to_list()
        assert "ESZ0" in df["original_symbol"].to_list()

    def test_mixed_uden_and_conventional(self, tmp_path):
        """Mixed dataset with both UD:EN and conventional symbols.

        Ensures both types are handled correctly in same dataset.
        """
        # Create mixed data
        sample_data = pl.DataFrame(
            {
                "ts_event": [
                    "2020-11-02T07:00:00.000000000Z",
                    "2020-11-02T07:00:00.000000000Z",
                    "2020-11-02T07:00:00.000000000Z",
                    "2020-11-02T07:00:00.000000000Z",
                ],
                "rtype": [34, 34, 34, 34],
                "publisher_id": [1, 1, 1, 1],
                "instrument_id": [869979, 865600, 108078, 19100],
                "open": [1.5, 2.0, 0.702, 3250.0],
                "high": [1.6, 2.1, 0.703, 3260.0],
                "low": [1.4, 1.9, 0.700, 3234.0],
                "close": [1.5, 2.0, 0.701, 3244.0],
                "volume": [100, 200, 5628, 59],
                "symbol": [
                    "UD:EN: VT 1102869979",
                    "UD:EN: SG 1102865600",
                    "6AZ0",
                    "ESZ0",
                ],
            }
        )

        # Save to CSV with OHLCV naming pattern
        csv_path = tmp_path / "test.ohlcv-1h.csv"
        sample_data.write_csv(csv_path)

        # Create adapter config (point to directory)
        config = DatabentoConfig(
            data_path=str(tmp_path),
            use_instrument_id=True,
            symbol_format="symbol_id",
        )

        # Parse OHLCV
        adapter = DatabentoAdapter(config)
        df = adapter._parse_ohlcv_csv()

        # Verify UD:EN symbols (no appending)
        uden_symbols = [s for s in df["symbol"].to_list() if s.startswith("UD:EN:")]
        assert "UD:EN: VT 1102869979" in uden_symbols
        assert "UD:EN: SG 1102865600" in uden_symbols

        # Verify conventional symbols (appending)
        conv_symbols = [s for s in df["symbol"].to_list() if not s.startswith("UD:EN:")]
        assert "6AZ0_108078" in conv_symbols
        assert "ESZ0_19100" in conv_symbols

        # Verify total count
        assert len(df) == 4

        # Verify no redundant UD:EN symbols
        redundant = [s for s in df["symbol"].to_list() if "_" in s and "UD:EN:" in s]
        assert len(redundant) == 0, f"Found redundant UD:EN symbols: {redundant}"

    def test_uden_pattern_variations(self, tmp_path):
        """Test various UD:EN symbol pattern variations from real data."""
        # Real patterns observed in GLBX data
        sample_data = pl.DataFrame(
            {
                "ts_event": [
                    "2020-11-02T07:00:00.000000000Z",
                    "2020-11-02T08:00:00.000000000Z",
                    "2020-11-02T09:00:00.000000000Z",
                    "2020-11-02T10:00:00.000000000Z",
                    "2020-11-02T11:00:00.000000000Z",
                ],
                "rtype": [34, 34, 34, 34, 34],
                "publisher_id": [1, 1, 1, 1, 1],
                "instrument_id": [865600, 854310, 852547, 867064, 940738],
                "open": [1.0, 2.0, 3.0, 4.0, 5.0],
                "high": [1.1, 2.1, 3.1, 4.1, 5.1],
                "low": [0.9, 1.9, 2.9, 3.9, 4.9],
                "close": [1.0, 2.0, 3.0, 4.0, 5.0],
                "volume": [10, 20, 30, 40, 50],
                "symbol": [
                    "UD:EN: SG 1102865600",  # SG type
                    "UD:EN: 3W 1102854310",  # 3W type
                    "UD:EN: VT 1102852547",  # VT type
                    "UD:EN: GN 1102867064",  # GN type
                    "UD:EN: SG 1107940738",  # Different date prefix (1107)
                ],
            }
        )

        # Save to CSV with OHLCV naming pattern
        csv_path = tmp_path / "test.ohlcv-1h.csv"
        sample_data.write_csv(csv_path)

        # Create adapter config (point to directory)
        config = DatabentoConfig(
            data_path=str(tmp_path),
            use_instrument_id=True,
            symbol_format="symbol_id",
        )

        # Parse OHLCV
        adapter = DatabentoAdapter(config)
        df = adapter._parse_ohlcv_csv()

        # Verify ALL UD:EN variations handled correctly
        expected_symbols = [
            "UD:EN: SG 1102865600",
            "UD:EN: 3W 1102854310",
            "UD:EN: VT 1102852547",
            "UD:EN: GN 1102867064",
            "UD:EN: SG 1107940738",
        ]

        actual_symbols = df["symbol"].to_list()
        for expected in expected_symbols:
            assert expected in actual_symbols, f"Missing expected symbol: {expected}"

        # Verify NO redundant IDs
        for symbol in actual_symbols:
            # Count occurrences of instrument_id digits
            for inst_id in df["instrument_id"].to_list():
                id_str = str(inst_id)
                count = symbol.count(id_str)
                assert (
                    count <= 1
                ), f"Symbol '{symbol}' contains instrument_id '{id_str}' more than once"


class TestSymbolFormatBackwardCompat:
    """Test backward compatibility with symbol-only mode."""

    def test_symbol_only_mode_unchanged(self, tmp_path):
        """When use_instrument_id=False, symbols should remain unchanged."""
        sample_data = pl.DataFrame(
            {
                "ts_event": ["2020-11-02T07:00:00.000000000Z"],
                "rtype": [34],
                "publisher_id": [1],
                "instrument_id": [869979],
                "open": [1.5],
                "high": [1.6],
                "low": [1.4],
                "close": [1.5],
                "volume": [100],
                "symbol": ["UD:EN: VT 1102869979"],
            }
        )

        csv_path = tmp_path / "test.ohlcv-1h.csv"
        sample_data.write_csv(csv_path)

        # Legacy mode: use_instrument_id=False
        config = DatabentoConfig(
            data_path=str(tmp_path),
            use_instrument_id=False,
        )

        adapter = DatabentoAdapter(config)
        df = adapter._parse_ohlcv_csv()

        # In legacy mode, symbols remain exactly as-is
        assert "UD:EN: VT 1102869979" in df["symbol"].to_list()

        # No instrument_id column in symbols
        assert "original_symbol" not in df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
