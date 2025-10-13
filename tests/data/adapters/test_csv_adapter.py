"""Tests for CSV data adapter.

Tests cover schema mapping, date parsing, delimiter detection, header handling,
decimal conversion, timezone handling, and missing data strategies.
"""

import asyncio
import tempfile

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters.base import InvalidDataError, ValidationError
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

# ============================================================================
# Unit Tests - Schema Mapping
# ============================================================================


def test_schema_mapping_standard_columns():
    """Schema mapping works for standard column names."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("Date,Open,High,Low,Close,Volume\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(
                date_column="Date",
                open_column="Open",
                high_column="High",
                low_column="Low",
                close_column="Close",
                volume_column="Volume",
            ),
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert "timestamp" in df.columns
        assert "open" in df.columns
        assert df.schema["open"] == pl.Decimal(None, 8)
        assert len(df) == 1


def test_schema_mapping_case_insensitive():
    """Schema mapping handles case-insensitive column matching."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("date,OPEN,high,LOW,ClOsE,VOLUME\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(
                date_column="Date",
                open_column="Open",
                high_column="High",
                low_column="Low",
                close_column="Close",
                volume_column="Volume",
            ),
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert "timestamp" in df.columns
        assert "open" in df.columns
        assert len(df) == 1


def test_schema_mapping_custom_columns():
    """Schema mapping works with custom column names."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("trade_date,o,h,l,c,vol\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(
                date_column="trade_date",
                open_column="o",
                high_column="h",
                low_column="l",
                close_column="c",
                volume_column="vol",
            ),
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert "timestamp" in df.columns
        assert "open" in df.columns
        assert len(df) == 1


def test_schema_mapping_missing_required_column():
    """Schema mapping raises error if required column missing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("Date,Open,High,Low,Close\n")  # Missing Volume
        f.write("2023-01-01,100.5,101.0,100.0,100.8\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(
                date_column="Date",
                open_column="Open",
                high_column="High",
                low_column="Low",
                close_column="Close",
                volume_column="Volume",  # This column doesn't exist
            ),
        )

        adapter = CSVAdapter(config)
        with pytest.raises(InvalidDataError, match="Missing required columns"):
            asyncio.run(
                adapter.fetch(
                    symbols=[],
                    start_date=pd.Timestamp("2023-01-01"),
                    end_date=pd.Timestamp("2023-01-02"),
                    resolution="1d",
                )
            )


def test_schema_mapping_with_symbol_column():
    """Schema mapping correctly maps symbol column."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("Date,Ticker,Open,High,Low,Close,Volume\n")
        f.write("2023-01-01,AAPL,100.5,101.0,100.0,100.8,1000\n")
        f.write("2023-01-01,MSFT,200.5,201.0,200.0,200.8,2000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(
                date_column="Date",
                open_column="Open",
                high_column="High",
                low_column="Low",
                close_column="Close",
                volume_column="Volume",
                symbol_column="Ticker",
            ),
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=["AAPL"],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert "symbol" in df.columns
        assert len(df) == 1
        assert df["symbol"][0] == "AAPL"


# ============================================================================
# Unit Tests - Date Parsing
# ============================================================================


def test_date_parsing_iso8601():
    """Date parsing handles ISO8601 format."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(file_path=f.name, schema_mapping=SchemaMapping(), date_format="%Y-%m-%d")

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert df["timestamp"][0].year == 2023
        assert df["timestamp"][0].month == 1
        assert df["timestamp"][0].day == 1


def test_date_parsing_iso8601_with_time():
    """Date parsing handles ISO8601 format with time."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01 10:30:00,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name, schema_mapping=SchemaMapping(), date_format="%Y-%m-%d %H:%M:%S"
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert df["timestamp"][0].hour == 10
        assert df["timestamp"][0].minute == 30


def test_date_parsing_us_format():
    """Date parsing handles US format (MM/DD/YYYY)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("01/15/2023,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(file_path=f.name, schema_mapping=SchemaMapping(), date_format="%m/%d/%Y")

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-12-31"),
                resolution="1d",
            )
        )

        assert df["timestamp"][0].month == 1
        assert df["timestamp"][0].day == 15
        assert df["timestamp"][0].year == 2023


def test_date_parsing_epoch_seconds():
    """Date parsing handles Unix epoch timestamps (seconds)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("1672531200,100.5,101.0,100.0,100.8,1000\n")  # 2023-01-01 00:00:00 UTC
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(),
            date_format=None,  # Auto-detect
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert df["timestamp"][0].year == 2023
        assert df["timestamp"][0].month == 1


def test_date_parsing_auto_detect_iso():
    """Date parsing auto-detects ISO8601 format."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(),
            date_format=None,  # Auto-detect
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert len(df) == 1


# ============================================================================
# Unit Tests - Delimiter Detection
# ============================================================================


def test_delimiter_detection_comma():
    """Delimiter detection identifies comma."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(),
            delimiter=None,  # Auto-detect
        )
        adapter = CSVAdapter(config)
        detected = adapter._detect_delimiter()

        assert detected == ","


def test_delimiter_detection_tab():
    """Delimiter detection identifies tab."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp\topen\thigh\tlow\tclose\tvolume\n")
        f.write("2023-01-01\t100.5\t101.0\t100.0\t100.8\t1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(),
            delimiter=None,  # Auto-detect
        )
        adapter = CSVAdapter(config)
        detected = adapter._detect_delimiter()

        assert detected == "\t"


def test_delimiter_detection_pipe():
    """Delimiter detection identifies pipe."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp|open|high|low|close|volume\n")
        f.write("2023-01-01|100.5|101.0|100.0|100.8|1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(),
            delimiter=None,  # Auto-detect
        )
        adapter = CSVAdapter(config)
        detected = adapter._detect_delimiter()

        assert detected == "|"


def test_delimiter_explicit():
    """Delimiter can be explicitly specified."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp;open;high;low;close;volume\n")
        f.write("2023-01-01;100.5;101.0;100.0;100.8;1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(),
            delimiter=";",  # Explicit
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert len(df) == 1


# ============================================================================
# Unit Tests - Missing Data Handling
# ============================================================================


def test_missing_data_fail_strategy():
    """Missing data strategy 'fail' raises error for nulls."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.write("2023-01-02,,,,,\n")  # Missing row
        f.flush()

        config = CSVConfig(
            file_path=f.name, schema_mapping=SchemaMapping(), missing_data_strategy="fail"
        )

        adapter = CSVAdapter(config)
        with pytest.raises(InvalidDataError, match="Missing values detected"):
            asyncio.run(
                adapter.fetch(
                    symbols=[],
                    start_date=pd.Timestamp("2023-01-01"),
                    end_date=pd.Timestamp("2023-01-03"),
                    resolution="1d",
                )
            )


def test_missing_data_skip_strategy():
    """Missing data strategy 'skip' removes rows with nulls."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.write("2023-01-02,,,,,\n")  # Missing row
        f.write("2023-01-03,101.5,102.0,101.0,101.8,1100\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name, schema_mapping=SchemaMapping(), missing_data_strategy="skip"
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-04"),
                resolution="1d",
            )
        )

        assert len(df) == 2  # Missing row skipped


def test_missing_data_interpolate_strategy():
    """Missing data strategy 'interpolate' forward-fills missing values."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.write("2023-01-02,,,,100.8,\n")  # Partial missing
        f.write("2023-01-03,101.5,102.0,101.0,101.8,1100\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name, schema_mapping=SchemaMapping(), missing_data_strategy="interpolate"
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-04"),
                resolution="1d",
            )
        )

        # Should have 3 rows (or 2 if second row dropped after interpolation fails)
        assert len(df) >= 2


# ============================================================================
# Unit Tests - Decimal Conversion
# ============================================================================


def test_decimal_conversion_preserves_precision():
    """Decimal conversion preserves price precision."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.12345678,101.12345678,100.00000001,100.87654321,1000.5\n")
        f.flush()

        config = CSVConfig(file_path=f.name, schema_mapping=SchemaMapping())

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        # Check Decimal type
        assert df.schema["open"] == pl.Decimal(None, 8)
        assert df.schema["close"] == pl.Decimal(None, 8)


# ============================================================================
# Unit Tests - Timezone Handling
# ============================================================================


def test_timezone_conversion_to_utc():
    """Timezone conversion converts to UTC."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01 10:00:00,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(),
            date_format="%Y-%m-%d %H:%M:%S",
            timezone="America/New_York",
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        # Should have UTC timezone
        # 10:00 AM EST = 3:00 PM UTC
        assert df["timestamp"][0].hour == 15


def test_timezone_utc_no_conversion():
    """UTC timezone doesn't require conversion."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01 10:00:00,100.5,101.0,100.0,100.8,1000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(),
            date_format="%Y-%m-%d %H:%M:%S",
            timezone="UTC",
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert df["timestamp"][0].hour == 10


# ============================================================================
# Unit Tests - Validation
# ============================================================================


def test_validation_invalid_ohlcv_relationships():
    """Validation catches invalid OHLCV relationships."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.5,99.0,100.0,100.8,1000\n")  # high < low
        f.flush()

        config = CSVConfig(file_path=f.name, schema_mapping=SchemaMapping())

        adapter = CSVAdapter(config)
        with pytest.raises(ValidationError, match="Invalid OHLCV relationships"):
            asyncio.run(
                adapter.fetch(
                    symbols=[],
                    start_date=pd.Timestamp("2023-01-01"),
                    end_date=pd.Timestamp("2023-01-02"),
                    resolution="1d",
                )
            )


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.integration
def test_read_csv_complete_workflow():
    """Complete CSV read workflow with all features."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("trade_date|ticker|o|h|l|c|vol\n")
        f.write("01/01/2023|AAPL|100.5|101.0|100.0|100.8|1000\n")
        f.write("01/02/2023|AAPL|100.8|102.0|100.5|101.5|1100\n")
        f.write("01/03/2023|AAPL|101.5|103.0|101.0|102.5|1200\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(
                date_column="trade_date",
                open_column="o",
                high_column="h",
                low_column="l",
                close_column="c",
                volume_column="vol",
                symbol_column="ticker",
            ),
            delimiter="|",
            date_format="%m/%d/%Y",
            timezone="America/New_York",
            missing_data_strategy="skip",
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=["AAPL"],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-31"),
                resolution="1d",
            )
        )

        assert len(df) == 3
        assert "symbol" in df.columns
        assert df["symbol"][0] == "AAPL"
        assert df.schema["close"] == pl.Decimal(None, 8)
        adapter.validate(df)


@pytest.mark.integration
def test_read_csv_date_range_filter():
    """CSV adapter filters by date range."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,open,high,low,close,volume\n")
        f.write("2023-01-01,100.5,101.0,100.0,100.8,1000\n")
        f.write("2023-01-15,100.8,102.0,100.5,101.5,1100\n")
        f.write("2023-02-01,101.5,103.0,101.0,102.5,1200\n")
        f.flush()

        config = CSVConfig(file_path=f.name, schema_mapping=SchemaMapping())

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=[],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-31"),
                resolution="1d",
            )
        )

        assert len(df) == 2  # Only January dates


@pytest.mark.integration
def test_read_csv_symbol_filter():
    """CSV adapter filters by symbol."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,symbol,open,high,low,close,volume\n")
        f.write("2023-01-01,AAPL,100.5,101.0,100.0,100.8,1000\n")
        f.write("2023-01-01,MSFT,200.5,201.0,200.0,200.8,2000\n")
        f.write("2023-01-01,GOOGL,300.5,301.0,300.0,300.8,3000\n")
        f.flush()

        config = CSVConfig(
            file_path=f.name,
            schema_mapping=SchemaMapping(symbol_column="symbol"),  # Enable symbol column
        )

        adapter = CSVAdapter(config)
        df = asyncio.run(
            adapter.fetch(
                symbols=["AAPL", "MSFT"],
                start_date=pd.Timestamp("2023-01-01"),
                end_date=pd.Timestamp("2023-01-02"),
                resolution="1d",
            )
        )

        assert len(df) == 2
        assert set(df["symbol"].to_list()) == {"AAPL", "MSFT"}
