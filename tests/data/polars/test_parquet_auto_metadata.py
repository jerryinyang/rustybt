"""Tests for ParquetWriter auto-population of BundleMetadata.

Tests Story 8.4 Phase 3 (Auto-Population) - AC 3.1-3.3:
- ParquetWriter.write_daily_bars() accepts source_metadata parameter
- Auto-population of provenance metadata
- Auto-validation and quality metrics tracking
- Auto-extraction of symbols from DataFrame
- Asset type inference (equity, crypto, future)

Story: 8.4 (Unified Metadata Management)
Phase: 3 (Auto-Population)
"""

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import polars as pl

from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.polars.parquet_schema import DAILY_BARS_SCHEMA
from rustybt.data.polars.parquet_writer import ParquetWriter


def create_ohlcv_df(dates, sids, opens, highs, lows, closes, volumes):
    """Helper to create DataFrame with correct Decimal precision."""
    df = pl.DataFrame(
        {
            "date": dates,
            "sid": sids,
            "open": [str(x) for x in opens],
            "high": [str(x) for x in highs],
            "low": [str(x) for x in lows],
            "close": [str(x) for x in closes],
            "volume": [str(x) for x in volumes],
        }
    )

    df = df.with_columns(
        [
            pl.col("open").cast(pl.Decimal(precision=18, scale=8)),
            pl.col("high").cast(pl.Decimal(precision=18, scale=8)),
            pl.col("low").cast(pl.Decimal(precision=18, scale=8)),
            pl.col("close").cast(pl.Decimal(precision=18, scale=8)),
            pl.col("volume").cast(pl.Decimal(precision=18, scale=8)),
        ]
    )

    return df.cast(DAILY_BARS_SCHEMA, strict=False)


class TestAutoPopulation:
    """Test auto-population of BundleMetadata during Parquet writes."""

    def test_parquet_writer_accepts_source_metadata(self):
        """ParquetWriter.write_daily_bars() accepts source_metadata parameter (AC 3.1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            df = create_ohlcv_df(
                dates=[date(2025, 1, 1)],
                sids=[1],
                opens=[Decimal("100.00")],
                highs=[Decimal("101.00")],
                lows=[Decimal("99.00")],
                closes=[Decimal("100.50")],
                volumes=[Decimal("1000000")],
            )

            source_metadata = {
                "source_type": "yfinance",
                "source_url": "https://query2.finance.yahoo.com/v8/finance/chart/AAPL",
                "api_version": "v8",
                "symbols": ["AAPL"],
            }

            # Should not raise
            path = writer.write_daily_bars(
                df,
                compression="zstd",
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            assert path.exists()

    def test_auto_populates_provenance_metadata(self):
        """Auto-populates provenance metadata in BundleMetadata (AC 3.1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set BundleMetadata to use test database
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            df = pl.DataFrame(
                {
                    "date": [date(2025, 1, 1)],
                    "sid": [1],
                    "open": [Decimal("100.00")],
                    "high": [Decimal("101.00")],
                    "low": [Decimal("99.00")],
                    "close": [Decimal("100.50")],
                    "volume": [1000000],
                }
            )

            source_metadata = {
                "source_type": "yfinance",
                "source_url": "https://query2.finance.yahoo.com/v8/...",
                "api_version": "v8",
                "symbols": ["AAPL"],
            }

            writer.write_daily_bars(
                df,
                compression="zstd",
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            # Verify provenance populated
            metadata = BundleMetadata.get("test-bundle")
            assert metadata is not None
            assert metadata["source_type"] == "yfinance"
            assert metadata["source_url"] == "https://query2.finance.yahoo.com/v8/..."
            assert metadata["api_version"] == "v8"
            assert metadata["fetch_timestamp"] > 0
            assert metadata["row_count"] == 1
            assert metadata["file_checksum"] is not None
            assert metadata["file_size_bytes"] > 0

    def test_auto_validates_quality_metrics(self):
        """Auto-validates OHLCV and updates quality metrics (AC 3.1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            # Valid OHLCV data
            df = pl.DataFrame(
                {
                    "date": [date(2025, 1, 1)],
                    "sid": [1],
                    "open": [Decimal("100.00")],
                    "high": [Decimal("101.00")],
                    "low": [Decimal("99.00")],
                    "close": [Decimal("100.50")],
                    "volume": [1000000],
                }
            )

            source_metadata = {"source_type": "yfinance", "symbols": ["AAPL"]}

            writer.write_daily_bars(
                df,
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            # Verify quality metrics populated
            quality = BundleMetadata.get_quality_metrics("test-bundle")
            assert quality is not None
            assert quality["ohlcv_violations"] == 0
            assert quality["validation_passed"] is True
            assert quality["validation_timestamp"] > 0

    def test_detects_ohlcv_violations(self):
        """Detects OHLCV violations and records them (AC 3.1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            # Invalid OHLCV data (high < low)
            df = pl.DataFrame(
                {
                    "date": [date(2025, 1, 1)],
                    "sid": [1],
                    "open": [Decimal("100.00")],
                    "high": [Decimal("99.00")],  # Invalid: high < low
                    "low": [Decimal("101.00")],
                    "close": [Decimal("100.50")],
                    "volume": [1000000],
                }
            )

            source_metadata = {"source_type": "yfinance", "symbols": ["AAPL", "MSFT"]}

            writer.write_daily_bars(
                df,
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            # Verify violations detected
            quality = BundleMetadata.get_quality_metrics("test-bundle")
            assert quality["ohlcv_violations"] == 1
            assert quality["validation_passed"] is False

    def test_auto_extracts_symbols(self):
        """Auto-extracts symbols from DataFrame and populates bundle_symbols (AC 3.3)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            df = pl.DataFrame(
                {
                    "date": [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)],
                    "sid": [1, 2, 1],
                    # 2 unique symbols
                    "open": [Decimal("100.00"), Decimal("200.00"), Decimal("101.00")],
                    "high": [Decimal("101.00"), Decimal("201.00"), Decimal("102.00")],
                    "low": [Decimal("99.00"), Decimal("199.00"), Decimal("100.00")],
                    "close": [Decimal("100.50"), Decimal("200.50"), Decimal("101.50")],
                    "volume": [1000000, 2000000, 1100000],
                }
            )

            source_metadata = {"source_type": "yfinance", "symbols": ["AAPL", "MSFT"]}

            writer.write_daily_bars(
                df,
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            # Verify symbols extracted
            symbols = BundleMetadata.get_symbols("test-bundle")
            assert len(symbols) == 2

            symbol_names = {s["symbol"] for s in symbols}
            assert "AAPL" in symbol_names
            assert "MSFT" in symbol_names

            # Verify asset types inferred
            for symbol_row in symbols:
                assert symbol_row["asset_type"] == "equity"

    def test_infers_asset_type_crypto(self):
        """Infers crypto asset type from symbol patterns (AC 3.3)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            df = pl.DataFrame(
                {
                    "date": [date(2025, 1, 1)],
                    "sid": [1],
                    # Crypto pattern
                    "open": [Decimal("50000.00")],
                    "high": [Decimal("51000.00")],
                    "low": [Decimal("49000.00")],
                    "close": [Decimal("50500.00")],
                    "volume": [100],
                }
            )

            source_metadata = {"source_type": "ccxt", "symbols": ["BTC/USDT"]}

            writer.write_daily_bars(
                df,
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            symbols = BundleMetadata.get_symbols("test-bundle")
            assert len(symbols) == 1
            assert symbols[0]["symbol"] == "BTC/USDT"
            assert symbols[0]["asset_type"] == "crypto"

    def test_infers_asset_type_future(self):
        """Infers future asset type from symbol patterns (AC 3.3)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            df = pl.DataFrame(
                {
                    "date": [date(2025, 1, 1)],
                    "sid": [1],
                    # Future pattern (contract code + month + year)
                    "open": [Decimal("4500.00")],
                    "high": [Decimal("4510.00")],
                    "low": [Decimal("4490.00")],
                    "close": [Decimal("4505.00")],
                    "volume": [50000],
                }
            )

            source_metadata = {"source_type": "interactive_brokers", "symbols": ["ESH25"]}

            writer.write_daily_bars(
                df,
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            symbols = BundleMetadata.get_symbols("test-bundle")
            assert len(symbols) == 1
            assert symbols[0]["symbol"] == "ESH25"
            assert symbols[0]["asset_type"] == "future"

    def test_extracts_exchange_from_metadata(self):
        """Extracts exchange from source_metadata and populates bundle_symbols (AC 3.3)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            df = pl.DataFrame(
                {
                    "date": [date(2025, 1, 1)],
                    "sid": [1],
                    "open": [Decimal("100.00")],
                    "high": [Decimal("101.00")],
                    "low": [Decimal("99.00")],
                    "close": [Decimal("100.50")],
                    "volume": [1000000],
                }
            )

            source_metadata = {
                "source_type": "yfinance",
                "exchange": "NASDAQ",
                "symbols": ["AAPL"],
            }

            writer.write_daily_bars(
                df,
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            symbols = BundleMetadata.get_symbols("test-bundle")
            assert len(symbols) == 1
            assert symbols[0]["exchange"] == "NASDAQ"

    def test_integration_full_workflow(self):
        """Integration test: Full workflow from write to metadata retrieval (AC 3.1-3.3)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"))

            df = pl.DataFrame(
                {
                    "date": [date(2025, 1, 1), date(2025, 1, 2)],
                    "sid": [1, 2],
                    "open": [Decimal("100.00"), Decimal("50000.00")],
                    "high": [Decimal("101.00"), Decimal("51000.00")],
                    "low": [Decimal("99.00"), Decimal("49000.00")],
                    "close": [Decimal("100.50"), Decimal("50500.00")],
                    "volume": [1000000, 100],
                }
            )

            source_metadata = {
                "source_type": "mixed",
                "source_url": "https://example.com/api",
                "api_version": "v2",
                "exchange": "MIXED",
                "symbols": ["AAPL", "BTC/USDT"],
            }

            writer.write_daily_bars(
                df,
                compression="zstd",
                source_metadata=source_metadata,
                bundle_name="test-bundle",
            )

            # Verify all metadata populated
            metadata = BundleMetadata.get("test-bundle")
            assert metadata["source_type"] == "mixed"
            assert metadata["row_count"] == 2

            quality = BundleMetadata.get_quality_metrics("test-bundle")
            assert quality["ohlcv_violations"] == 0
            assert quality["validation_passed"] is True

            symbols = BundleMetadata.get_symbols("test-bundle")
            assert len(symbols) == 2

            # Verify asset type inference worked
            symbol_map = {s["symbol"]: s for s in symbols}
            assert symbol_map["AAPL"]["asset_type"] == "equity"
            assert symbol_map["BTC/USDT"]["asset_type"] == "crypto"
