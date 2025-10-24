"""Tests for asset-aware validation and gap pattern detection."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from rustybt.data.polars.parquet_writer import ParquetWriter


class TestAssetTypeInference:
    """Test robust asset type inference."""

    def test_forex_detection_yfinance_format(self, tmp_path):
        """Test forex detection for Yahoo Finance format (EURUSD=X)."""
        writer = ParquetWriter(str(tmp_path))

        # Test various yfinance forex formats
        assert writer._infer_asset_type("EURUSD=X") == "forex"
        assert writer._infer_asset_type("GBPJPY=X") == "forex"
        assert writer._infer_asset_type("USDJPY=X") == "forex"

    def test_forex_detection_slash_format(self, tmp_path):
        """Test forex detection for slash format (EUR/USD)."""
        writer = ParquetWriter(str(tmp_path))

        assert writer._infer_asset_type("EUR/USD") == "forex"
        assert writer._infer_asset_type("GBP/JPY") == "forex"
        assert writer._infer_asset_type("USD/CHF") == "forex"

    def test_forex_detection_no_separator(self, tmp_path):
        """Test forex detection for no separator format (EURUSD)."""
        writer = ParquetWriter(str(tmp_path))

        assert writer._infer_asset_type("EURUSD") == "forex"
        assert writer._infer_asset_type("GBPJPY") == "forex"
        assert writer._infer_asset_type("USDJPY") == "forex"

    def test_crypto_detection_slash_format(self, tmp_path):
        """Test crypto detection for slash format (BTC/USDT)."""
        writer = ParquetWriter(str(tmp_path))

        assert writer._infer_asset_type("BTC/USDT") == "crypto"
        assert writer._infer_asset_type("ETH/USD") == "crypto"
        assert writer._infer_asset_type("SOL/USDC") == "crypto"

    def test_crypto_detection_no_separator(self, tmp_path):
        """Test crypto detection for no separator format (BTCUSDT)."""
        writer = ParquetWriter(str(tmp_path))

        assert writer._infer_asset_type("BTCUSDT") == "crypto"
        assert writer._infer_asset_type("ETHUSDC") == "crypto"
        assert writer._infer_asset_type("SOLUSDT") == "crypto"
        assert writer._infer_asset_type("BTCUSD") == "crypto"

    def test_equity_detection(self, tmp_path):
        """Test equity detection."""
        writer = ParquetWriter(str(tmp_path))

        assert writer._infer_asset_type("AAPL") == "equity"
        assert writer._infer_asset_type("MSFT") == "equity"
        assert writer._infer_asset_type("GOOGL") == "equity"

    def test_future_detection(self, tmp_path):
        """Test futures contract detection."""
        writer = ParquetWriter(str(tmp_path))

        assert writer._infer_asset_type("ESH25") == "future"
        assert writer._infer_asset_type("NQM24") == "future"
        assert writer._infer_asset_type("GCZ23") == "future"


class TestGapPatternAnalysis:
    """Test gap pattern analysis for distinguishing regular vs irregular gaps."""

    def test_weekend_gap_pattern(self, tmp_path):
        """Test detection of regular weekend pattern."""
        writer = ParquetWriter(str(tmp_path))

        # Create weekday-only data (Monday-Friday) for 4 weeks
        start_date = date(2023, 1, 2)  # Monday
        present_dates = []
        for week in range(4):
            for day in range(5):  # Mon-Fri
                present_dates.append(start_date + timedelta(weeks=week, days=day))

        # Missing dates are weekends
        end_date = present_dates[-1]
        all_dates_range = []
        current = start_date
        while current <= end_date:
            all_dates_range.append(current)
            current += timedelta(days=1)

        missing_dates = [d for d in all_dates_range if d not in present_dates]

        result = writer._analyze_gap_pattern(missing_dates, present_dates)

        assert result["is_regular_pattern"] is True
        assert result["weekend_gap_ratio"] > 0.9  # Most gaps are weekends
        assert result["max_gap_days"] == 2  # Weekend is 2 days

    def test_irregular_gap_pattern(self, tmp_path):
        """Test detection of irregular gap pattern (data quality issue)."""
        writer = ParquetWriter(str(tmp_path))

        # Create data with random gaps
        start_date = date(2023, 1, 1)
        present_dates = [
            start_date,
            start_date + timedelta(days=1),
            start_date + timedelta(days=2),
            start_date + timedelta(days=5),  # 3-day gap
            start_date + timedelta(days=6),
            start_date + timedelta(days=10),  # 4-day gap
            start_date + timedelta(days=11),
            start_date + timedelta(days=13),  # 2-day gap
            start_date + timedelta(days=20),  # 7-day gap
        ]

        end_date = present_dates[-1]
        all_dates_range = []
        current = start_date
        while current <= end_date:
            all_dates_range.append(current)
            current += timedelta(days=1)

        missing_dates = [d for d in all_dates_range if d not in present_dates]

        result = writer._analyze_gap_pattern(missing_dates, present_dates)

        assert result["is_regular_pattern"] is False  # Irregular pattern
        assert result["gap_length_variance"] > 2.0  # High variance

    def test_no_gaps(self, tmp_path):
        """Test analysis when no gaps present."""
        writer = ParquetWriter(str(tmp_path))

        result = writer._analyze_gap_pattern([], [date(2023, 1, i) for i in range(1, 31)])

        assert result["is_regular_pattern"] is True
        assert result["weekend_gap_ratio"] == 0.0
        assert result["max_gap_days"] == 0


class TestAssetAwareValidation:
    """Test asset-aware validation logic integration."""

    def test_forex_with_weekend_gaps_passes(self, tmp_path):
        """Test forex data with weekend gaps passes validation."""
        writer = ParquetWriter(str(tmp_path))

        # Create weekday-only data (simulating forex market hours)
        dates = []
        start_date = date(2023, 1, 2)  # Monday
        for week in range(4):
            for day in range(5):  # Mon-Fri only
                dates.append(start_date + timedelta(weeks=week, days=day))

        df = pl.DataFrame(
            {
                "date": dates,
                "sid": [1] * len(dates),
                "open": [Decimal("1.0800")] * len(dates),
                "high": [Decimal("1.0850")] * len(dates),
                "low": [Decimal("1.0750")] * len(dates),
                "close": [Decimal("1.0820")] * len(dates),
                "volume": [Decimal("1000000")] * len(dates),
            }
        )

        source_metadata = {
            "source_type": "yfinance",
            "source_url": "https://finance.yahoo.com",
            "api_version": "v8",
            "symbols": ["EURUSD=X"],
        }

        # Write with forex asset type
        output_path = writer.write_daily_bars(
            df,
            bundle_name="test-forex",
            source_metadata=source_metadata,
            asset_type="forex",
        )

        assert output_path.exists()

    def test_crypto_with_gaps_fails(self, tmp_path):
        """Test crypto data with irregular gaps should log warning."""
        writer = ParquetWriter(str(tmp_path))

        # Create data with irregular gaps (simulating missing data)
        dates = [
            date(2023, 1, 1),
            date(2023, 1, 2),
            date(2023, 1, 5),  # gap
            date(2023, 1, 8),  # gap
            date(2023, 1, 15),  # large gap
        ]

        df = pl.DataFrame(
            {
                "date": dates,
                "sid": [1] * len(dates),
                "open": [Decimal("40000")] * len(dates),
                "high": [Decimal("41000")] * len(dates),
                "low": [Decimal("39000")] * len(dates),
                "close": [Decimal("40500")] * len(dates),
                "volume": [Decimal("1000000")] * len(dates),
            }
        )

        source_metadata = {
            "source_type": "exchange",
            "source_url": "https://api.exchange.com",
            "api_version": "v1",
            "symbols": ["BTC/USDT"],
        }

        # Write with crypto asset type - should detect irregular pattern
        output_path = writer.write_daily_bars(
            df,
            bundle_name="test-crypto",
            source_metadata=source_metadata,
            asset_type="crypto",
        )

        assert output_path.exists()


@pytest.fixture
def tmp_path(tmp_path_factory):
    """Create temporary directory for tests."""
    return tmp_path_factory.mktemp("parquet_test")
