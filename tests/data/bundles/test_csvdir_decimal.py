"""Tests for CSV bundle ingestion with Decimal precision."""

import tempfile
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from rustybt.data.bundles.csvdir import convert_csv_to_decimal_parquet
from rustybt.data.polars.validation import ValidationError


class TestCSVDecimalIngestion:
    """Test CSV ingestion with Decimal precision preservation."""

    def test_convert_csv_equity_daily_preserves_precision(self):
        """Test daily equity CSV ingestion preserves precision."""
        csv_data = """date,open,high,low,close,volume
2023-01-01,123.45,123.50,123.40,123.48,1000000
2023-01-02,123.48,123.60,123.45,123.55,1500000
2023-01-03,123.55,123.70,123.50,123.65,1200000
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_equity.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test_equity.parquet"

            # Ingest with equity precision
            summary = convert_csv_to_decimal_parquet(
                str(csv_path), str(parquet_path), asset_class="equity", frequency="daily"
            )

            # Verify summary
            assert summary["rows_ingested"] == 3
            assert len(summary["errors"]) == 0

            # Read Parquet and verify precision
            df = pl.read_parquet(parquet_path)

            # Verify schema
            assert df["open"].dtype == pl.Decimal(precision=18, scale=2)
            assert df["close"].dtype == pl.Decimal(precision=18, scale=2)

            # Verify exact values
            assert df["open"][0] == Decimal("123.45")
            assert df["close"][0] == Decimal("123.48")
            assert df["volume"][0] == Decimal("1000000")

    def test_convert_csv_crypto_daily_preserves_high_precision(self):
        """Test daily crypto CSV ingestion preserves 8 decimal places."""
        csv_data = """date,open,high,low,close,volume
2023-01-01,0.00012345,0.00012400,0.00012300,0.00012380,1000000.12345678
2023-01-02,0.00012380,0.00012500,0.00012350,0.00012450,1500000.87654321
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_crypto.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test_crypto.parquet"

            # Ingest with crypto precision
            summary = convert_csv_to_decimal_parquet(
                str(csv_path), str(parquet_path), asset_class="crypto", frequency="daily"
            )

            # Verify summary
            assert summary["rows_ingested"] == 2
            assert len(summary["errors"]) == 0

            # Read Parquet and verify precision
            df = pl.read_parquet(parquet_path)

            # Verify schema
            assert df["open"].dtype == pl.Decimal(precision=18, scale=8)

            # Verify exact values with 8 decimal places
            assert df["open"][0] == Decimal("0.00012345")
            assert df["close"][0] == Decimal("0.00012380")
            # Volume should preserve 8 decimals
            assert df["volume"][0] == Decimal("1000000.12345678")

    def test_convert_csv_rejects_negative_prices(self):
        """Test CSV ingestion rejects negative prices."""
        csv_data = """date,open,high,low,close,volume
2023-01-01,123.45,123.50,-123.40,123.48,1000000
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_negative.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test_negative.parquet"

            # Should raise ValueError for negative prices
            with pytest.raises(ValueError, match="Negative values detected"):
                convert_csv_to_decimal_parquet(
                    str(csv_path), str(parquet_path), asset_class="equity", frequency="daily"
                )

    def test_convert_csv_rejects_scientific_notation(self):
        """Test CSV ingestion rejects scientific notation."""
        csv_data = """date,open,high,low,close,volume
2023-01-01,1.23e2,123.50,123.40,123.48,1000000
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_scientific.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test_scientific.parquet"

            # Should raise ValueError for scientific notation
            with pytest.raises(ValueError, match="Scientific notation detected"):
                convert_csv_to_decimal_parquet(
                    str(csv_path), str(parquet_path), asset_class="equity", frequency="daily"
                )

    def test_convert_csv_validates_ohlcv_relationships(self):
        """Test CSV ingestion validates OHLCV relationships."""
        csv_data = """date,open,high,low,close,volume
2023-01-01,123.45,123.40,123.50,123.48,1000000
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_invalid_ohlcv.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test_invalid_ohlcv.parquet"

            # Should raise ValidationError for invalid OHLCV (high < low)
            with pytest.raises(ValidationError, match="Invalid OHLCV"):
                convert_csv_to_decimal_parquet(
                    str(csv_path), str(parquet_path), asset_class="equity", frequency="daily"
                )

    def test_convert_csv_handles_missing_file(self):
        """Test CSV ingestion handles missing file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "nonexistent.csv"
            parquet_path = Path(tmpdir) / "test.parquet"

            # Should raise FileNotFoundError
            with pytest.raises(FileNotFoundError):
                convert_csv_to_decimal_parquet(
                    str(csv_path), str(parquet_path), asset_class="equity", frequency="daily"
                )

    def test_convert_csv_minute_data(self):
        """Test minute-frequency CSV ingestion."""
        csv_data = """timestamp,open,high,low,close,volume
2023-01-01 09:30:00,123.45,123.50,123.40,123.48,10000
2023-01-01 09:31:00,123.48,123.60,123.45,123.55,15000
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_minute.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test_minute.parquet"

            # Ingest as minute data
            summary = convert_csv_to_decimal_parquet(
                str(csv_path), str(parquet_path), asset_class="equity", frequency="minute"
            )

            # Verify summary
            assert summary["rows_ingested"] == 2

            # Read Parquet and verify schema
            df = pl.read_parquet(parquet_path)
            assert "timestamp" in df.columns
            assert df["timestamp"].dtype == pl.Datetime("us")

    def test_convert_csv_very_small_crypto_values(self):
        """Test CSV ingestion handles very small crypto values (Satoshi level)."""
        csv_data = """date,open,high,low,close,volume
2023-01-01,0.00000001,0.00000002,0.00000001,0.00000001,1000000.00000000
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_satoshi.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test_satoshi.parquet"

            # Ingest with crypto precision
            convert_csv_to_decimal_parquet(
                str(csv_path), str(parquet_path), asset_class="crypto", frequency="daily"
            )

            # Read Parquet and verify precision
            df = pl.read_parquet(parquet_path)

            # Verify exact Satoshi-level precision
            assert df["open"][0] == Decimal("0.00000001")
            assert df["high"][0] == Decimal("0.00000002")

    def test_convert_csv_very_large_values(self):
        """Test CSV ingestion handles very large stock prices."""
        csv_data = """date,open,high,low,close,volume
2023-01-01,500000.00,550000.00,490000.00,520000.00,1000
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_large.csv"
            csv_path.write_text(csv_data)

            parquet_path = Path(tmpdir) / "test_large.parquet"

            # Ingest with equity precision
            convert_csv_to_decimal_parquet(
                str(csv_path), str(parquet_path), asset_class="equity", frequency="daily"
            )

            # Read Parquet and verify values
            df = pl.read_parquet(parquet_path)

            # Verify large values
            assert df["open"][0] == Decimal("500000.00")
            assert df["high"][0] == Decimal("550000.00")
