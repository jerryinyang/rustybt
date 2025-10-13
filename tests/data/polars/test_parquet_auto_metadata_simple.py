"""Simplified tests for ParquetWriter auto-population.

Story 8.4 Phase 3 - AC 3.1-3.3
"""

import tempfile
from datetime import date
from pathlib import Path

import polars as pl

from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.polars.parquet_writer import ParquetWriter


def test_accepts_source_metadata_and_autopopulates():
    """ParquetWriter auto-populates provenance and symbols (AC 3.1-3.3)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        BundleMetadata.set_db_path(str(db_path))
        BundleMetadata._get_engine()

        writer = ParquetWriter(str(Path(tmpdir) / "test-bundle"), enable_metadata_catalog=False)

        # Create DataFrame with exact schema types
        df = pl.DataFrame(
            {
                "date": pl.Series("date", [date(2025, 1, 1)], dtype=pl.Date),
                "sid": pl.Series("sid", [1], dtype=pl.Int64),
                "open": pl.Series("open", ["100.00000000"], dtype=pl.Decimal(18, 8)),
                "high": pl.Series("high", ["101.00000000"], dtype=pl.Decimal(18, 8)),
                "low": pl.Series("low", ["99.00000000"], dtype=pl.Decimal(18, 8)),
                "close": pl.Series("close", ["100.50000000"], dtype=pl.Decimal(18, 8)),
                "volume": pl.Series("volume", ["1000000.00000000"], dtype=pl.Decimal(18, 8)),
            }
        )

        source_metadata = {
            "source_type": "yfinance",
            "source_url": "https://api.example.com",
            "api_version": "v1",
            "symbols": ["AAPL", "BTC/USDT", "ESH25"],
        }

        path = writer.write_daily_bars(
            df, source_metadata=source_metadata, bundle_name="test-bundle"
        )
        assert path.exists()

        # Verify provenance (AC 3.1)
        metadata = BundleMetadata.get("test-bundle")
        assert metadata["source_type"] == "yfinance"
        assert metadata["source_url"] == "https://api.example.com"
        assert metadata["api_version"] == "v1"
        assert metadata["checksum"] is not None
        assert metadata["fetch_timestamp"] > 0

        # Verify symbols with asset type inference (AC 3.3)
        symbols = BundleMetadata.get_symbols("test-bundle")
        assert len(symbols) == 3

        symbol_map = {s["symbol"]: s for s in symbols}

        # Test equity inference
        assert symbol_map["AAPL"]["asset_type"] == "equity"

        # Test crypto inference (pattern: contains "/")
        assert symbol_map["BTC/USDT"]["asset_type"] == "crypto"

        # Test future inference (pattern: ends with digits)
        assert symbol_map["ESH25"]["asset_type"] == "future"

        print("✅ Phase 3 auto-population test passed!")
