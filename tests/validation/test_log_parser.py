"""Tests for log_parser module - schema validation and parsing for JSONL logs."""

from __future__ import annotations

import json
import time
from pathlib import Path

import polars as pl
import pytest

from rustybt.validation.log_parser import (
    VALID_LAYERS,
    LogParseError,
    ValidationResult,
    count_log_entries,
    flatten_data_column,
    parse_log,
    validate_log_schema,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result_str(self) -> None:
        """Test string representation of valid result."""
        result = ValidationResult(valid=True, line_count=100, errors=[])
        assert str(result) == "✓ Valid (100 lines)"

    def test_invalid_result_str(self) -> None:
        """Test string representation of invalid result."""
        result = ValidationResult(
            valid=False,
            line_count=50,
            errors=["Error 1", "Error 2", "Error 3"],
        )
        assert str(result) == "✗ Invalid (3 errors)"

    def test_zero_lines_valid(self) -> None:
        """Test valid result with zero lines."""
        result = ValidationResult(valid=True, line_count=0, errors=[])
        assert str(result) == "✓ Valid (0 lines)"


class TestValidLayers:
    """Tests for VALID_LAYERS constant."""

    def test_valid_layers_set(self) -> None:
        """Test VALID_LAYERS contains expected values."""
        assert VALID_LAYERS == {"data", "signals", "orders", "broker", "portfolio"}

    def test_valid_layers_is_set(self) -> None:
        """Test VALID_LAYERS is a set (for O(1) lookup)."""
        assert isinstance(VALID_LAYERS, set)


class TestValidateLogSchema:
    """Tests for validate_log_schema function."""

    @pytest.fixture
    def valid_log(self, tmp_path: Path) -> Path:
        """Create a valid JSONL log file."""
        log_path = tmp_path / "valid.jsonl"
        entries = [
            {
                "timestamp": "2020-01-01T09:30:00",
                "layer": "data",
                "event": "initialize",
                "data": {},
            },
            {
                "timestamp": "2020-01-01T09:30:01",
                "layer": "data",
                "event": "bar_received",
                "data": {"close": 100.0},
            },
            {
                "timestamp": "2020-01-01T09:30:01",
                "layer": "signals",
                "event": "signal_computed",
                "data": {"signal": 1},
            },
        ]
        with open(log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return log_path

    @pytest.fixture
    def invalid_log_missing_timestamp(self, tmp_path: Path) -> Path:
        """Create log with missing timestamp."""
        log_path = tmp_path / "missing_timestamp.jsonl"
        entries = [
            {"layer": "data", "event": "initialize"},  # Missing timestamp
        ]
        with open(log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return log_path

    @pytest.fixture
    def invalid_log_missing_layer(self, tmp_path: Path) -> Path:
        """Create log with missing layer."""
        log_path = tmp_path / "missing_layer.jsonl"
        entries = [
            {"timestamp": "2020-01-01T09:30:00", "event": "initialize"},
        ]
        with open(log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return log_path

    @pytest.fixture
    def invalid_log_missing_event(self, tmp_path: Path) -> Path:
        """Create log with missing event."""
        log_path = tmp_path / "missing_event.jsonl"
        entries = [
            {"timestamp": "2020-01-01T09:30:00", "layer": "data"},
        ]
        with open(log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return log_path

    @pytest.fixture
    def invalid_log_bad_layer(self, tmp_path: Path) -> Path:
        """Create log with invalid layer value."""
        log_path = tmp_path / "bad_layer.jsonl"
        entries = [
            {
                "timestamp": "2020-01-01T09:30:00",
                "layer": "invalid_layer",
                "event": "test",
            },
        ]
        with open(log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return log_path

    @pytest.fixture
    def invalid_log_bad_json(self, tmp_path: Path) -> Path:
        """Create log with invalid JSON line."""
        log_path = tmp_path / "bad_json.jsonl"
        with open(log_path, "w") as f:
            f.write('{"timestamp": "2020-01-01", "layer": "data", "event": "ok"}\n')
            f.write("not valid json\n")
            f.write('{"timestamp": "2020-01-02", "layer": "data", "event": "ok"}\n')
        return log_path

    def test_valid_log_passes(self, valid_log: Path) -> None:
        """Test valid log file returns valid=True."""
        result = validate_log_schema(valid_log)
        assert result.valid
        assert result.line_count == 3
        assert len(result.errors) == 0

    def test_missing_timestamp_detected(
        self, invalid_log_missing_timestamp: Path
    ) -> None:
        """Test missing timestamp field is detected."""
        result = validate_log_schema(invalid_log_missing_timestamp)
        assert not result.valid
        assert len(result.errors) == 1
        assert "Missing 'timestamp'" in result.errors[0]
        assert "Line 1" in result.errors[0]

    def test_missing_layer_detected(self, invalid_log_missing_layer: Path) -> None:
        """Test missing layer field is detected."""
        result = validate_log_schema(invalid_log_missing_layer)
        assert not result.valid
        assert any("Missing 'layer'" in e for e in result.errors)

    def test_missing_event_detected(self, invalid_log_missing_event: Path) -> None:
        """Test missing event field is detected."""
        result = validate_log_schema(invalid_log_missing_event)
        assert not result.valid
        assert any("Missing 'event'" in e for e in result.errors)

    def test_invalid_layer_detected(self, invalid_log_bad_layer: Path) -> None:
        """Test invalid layer value is detected with line number."""
        result = validate_log_schema(invalid_log_bad_layer)
        assert not result.valid
        assert len(result.errors) == 1
        assert "Invalid layer" in result.errors[0]
        assert "invalid_layer" in result.errors[0]
        assert "Line 1" in result.errors[0]

    def test_invalid_json_detected(self, invalid_log_bad_json: Path) -> None:
        """Test invalid JSON line is detected with line number."""
        result = validate_log_schema(invalid_log_bad_json)
        assert not result.valid
        assert any("Invalid JSON" in e for e in result.errors)
        assert any("Line 2" in e for e in result.errors)

    def test_multiple_errors_collected(self, tmp_path: Path) -> None:
        """Test that multiple errors are collected in a single pass."""
        log_path = tmp_path / "multi_error.jsonl"
        entries = [
            {"layer": "data", "event": "e1"},  # Missing timestamp
            {"timestamp": "2020-01-01", "event": "e2"},  # Missing layer
            {"timestamp": "2020-01-01", "layer": "invalid"},  # Invalid layer (no event)
        ]
        with open(log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        result = validate_log_schema(log_path)
        assert not result.valid
        # Should collect errors from all three lines
        assert len(result.errors) >= 3
        assert result.line_count == 3

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped but counted."""
        log_path = tmp_path / "with_empty.jsonl"
        with open(log_path, "w") as f:
            f.write('{"timestamp": "2020-01-01", "layer": "data", "event": "ok"}\n')
            f.write("\n")  # Empty line
            f.write('{"timestamp": "2020-01-02", "layer": "data", "event": "ok"}\n')

        result = validate_log_schema(log_path)
        assert result.valid
        assert result.line_count == 3  # All lines counted

    def test_all_valid_layers_accepted(self, tmp_path: Path) -> None:
        """Test that all valid layer values are accepted."""
        log_path = tmp_path / "all_layers.jsonl"
        with open(log_path, "w") as f:
            for layer in VALID_LAYERS:
                entry = {"timestamp": "2020-01-01", "layer": layer, "event": "test"}
                f.write(json.dumps(entry) + "\n")

        result = validate_log_schema(log_path)
        assert result.valid
        assert result.line_count == len(VALID_LAYERS)

    def test_empty_file(self, tmp_path: Path) -> None:
        """Test that empty file is valid with zero lines."""
        log_path = tmp_path / "empty.jsonl"
        log_path.touch()

        result = validate_log_schema(log_path)
        assert result.valid
        assert result.line_count == 0
        assert len(result.errors) == 0


class TestCountLogEntries:
    """Tests for count_log_entries function."""

    def test_count_entries(self, tmp_path: Path) -> None:
        """Test counting entries in a log file."""
        log_path = tmp_path / "test.jsonl"
        with open(log_path, "w") as f:
            for i in range(5):
                f.write(f'{{"line": {i}}}\n')

        assert count_log_entries(log_path) == 5

    def test_count_empty_file(self, tmp_path: Path) -> None:
        """Test counting entries in empty file."""
        log_path = tmp_path / "empty.jsonl"
        log_path.touch()

        assert count_log_entries(log_path) == 0

    def test_count_skips_empty_lines(self, tmp_path: Path) -> None:
        """Test that empty lines are not counted."""
        log_path = tmp_path / "with_blanks.jsonl"
        with open(log_path, "w") as f:
            f.write('{"line": 1}\n')
            f.write("\n")
            f.write('{"line": 2}\n')

        assert count_log_entries(log_path) == 2


class TestParseLog:
    """Tests for parse_log function - JSONL to DataFrame with caching."""

    @pytest.fixture
    def valid_log(self, tmp_path: Path) -> Path:
        """Create a valid JSONL log file."""
        log_path = tmp_path / "test.jsonl"
        entries = [
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
            },
            {
                "timestamp": "2020-01-15T09:31:00",
                "layer": "signals",
                "event": "signal_generated",
            },
        ]
        with open(log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return log_path

    def test_parse_log_basic(self, valid_log: Path) -> None:
        """Test basic JSONL parsing."""
        df = parse_log(valid_log, use_cache=False)

        assert len(df) == 2
        assert "timestamp" in df.columns
        assert "layer" in df.columns
        assert "event" in df.columns

    def test_parse_log_returns_polars_dataframe(self, valid_log: Path) -> None:
        """Test that parse_log returns a Polars DataFrame."""
        df = parse_log(valid_log, use_cache=False)
        assert isinstance(df, pl.DataFrame)

    def test_cache_creation(self, tmp_path: Path) -> None:
        """Test Parquet cache is created when use_cache=True."""
        log_path = tmp_path / "test.jsonl"
        log_path.write_text(
            '{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n'
        )

        parse_log(log_path, use_cache=True)

        cache_path = tmp_path / "test.parquet"
        assert cache_path.exists()

    def test_cache_not_created_when_disabled(self, tmp_path: Path) -> None:
        """Test cache is not created when use_cache=False."""
        log_path = tmp_path / "test.jsonl"
        log_path.write_text(
            '{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n'
        )

        parse_log(log_path, use_cache=False)

        cache_path = tmp_path / "test.parquet"
        assert not cache_path.exists()

    def test_cache_invalidation_on_source_change(self, tmp_path: Path) -> None:
        """Test cache is regenerated when source file is newer."""
        log_path = tmp_path / "test.jsonl"
        log_path.write_text(
            '{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n'
        )

        # First parse creates cache
        df1 = parse_log(log_path, use_cache=True)
        assert len(df1) == 1

        # Wait to ensure mtime difference
        time.sleep(0.1)

        # Modify source file
        log_path.write_text(
            '{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n'
            '{"timestamp": "2020-01-15T09:31:00", "layer": "data", "event": "bar_received"}\n'
        )

        # Second parse should regenerate cache
        df2 = parse_log(log_path, use_cache=True)
        assert len(df2) == 2  # Cache was regenerated

    def test_cache_used_when_valid(self, tmp_path: Path) -> None:
        """Test cache is used when it's newer than source."""
        log_path = tmp_path / "test.jsonl"
        log_path.write_text(
            '{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n'
        )

        # First parse creates cache
        parse_log(log_path, use_cache=True)

        # Verify cache exists
        cache_path = tmp_path / "test.parquet"
        assert cache_path.exists()

        # Read from cache (should be faster, but we just verify it works)
        df = parse_log(log_path, use_cache=True)
        assert len(df) == 1

    def test_parse_log_with_asset_field(self, tmp_path: Path) -> None:
        """Test parsing log with optional asset field."""
        log_path = tmp_path / "test.jsonl"
        log_path.write_text(
            '{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received", "asset": "AAPL"}\n'
        )

        df = parse_log(log_path, use_cache=False)

        assert "asset" in df.columns
        assert df["asset"][0] == "AAPL"

    def test_parse_log_schema_validation_error(self, tmp_path: Path) -> None:
        """Test that schema validation errors are raised."""
        log_path = tmp_path / "invalid.jsonl"
        log_path.write_text(
            '{"layer": "data", "event": "bar_received"}\n'  # Missing timestamp
        )

        with pytest.raises(LogParseError) as exc_info:
            parse_log(log_path, use_cache=False)

        assert "Missing 'timestamp'" in str(exc_info.value)

    def test_parse_log_invalid_json_error(self, tmp_path: Path) -> None:
        """Test that invalid JSON raises error."""
        log_path = tmp_path / "invalid.jsonl"
        log_path.write_text("not valid json\n")

        with pytest.raises(LogParseError) as exc_info:
            parse_log(log_path, use_cache=False)

        assert "Invalid JSON" in str(exc_info.value)

    def test_parse_log_file_not_found(self, tmp_path: Path) -> None:
        """Test FileNotFoundError for missing file."""
        log_path = tmp_path / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError):
            parse_log(log_path, use_cache=False)

    def test_parse_log_empty_file(self, tmp_path: Path) -> None:
        """Test parsing empty file returns empty DataFrame."""
        log_path = tmp_path / "empty.jsonl"
        log_path.touch()

        df = parse_log(log_path, use_cache=False)

        assert len(df) == 0
        assert "timestamp" in df.columns
        assert "layer" in df.columns

    def test_parse_log_with_data_flattening(self, tmp_path: Path) -> None:
        """Test that nested data field is flattened."""
        log_path = tmp_path / "test.jsonl"
        log_path.write_text(
            '{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received", "data": {"close": 100.5, "volume": 1000}}\n'
        )

        df = parse_log(log_path, use_cache=False)

        assert "data_close" in df.columns
        assert "data_volume" in df.columns
        assert "data" not in df.columns  # Original column removed
        assert df["data_close"][0] == 100.5
        assert df["data_volume"][0] == 1000


class TestFlattenDataColumn:
    """Tests for flatten_data_column function."""

    def test_flatten_data_column_basic(self) -> None:
        """Test basic flattening of data column."""
        df = pl.DataFrame(
            [
                {
                    "timestamp": "2020-01-15T09:30:00",
                    "layer": "data",
                    "event": "bar_received",
                    "data": {"close": 100.5, "volume": 1000},
                },
            ]
        )

        flattened = flatten_data_column(df)

        assert "data_close" in flattened.columns
        assert "data_volume" in flattened.columns
        assert "data" not in flattened.columns

    def test_flatten_data_column_no_data(self) -> None:
        """Test flattening when no data column exists."""
        df = pl.DataFrame(
            [
                {
                    "timestamp": "2020-01-15T09:30:00",
                    "layer": "data",
                    "event": "bar_received",
                },
            ]
        )

        flattened = flatten_data_column(df)

        # Should return unchanged
        assert "data" not in flattened.columns
        assert "timestamp" in flattened.columns

    def test_flatten_data_column_missing_keys(self) -> None:
        """Test flattening with missing keys in some rows."""
        df = pl.DataFrame(
            [
                {
                    "timestamp": "2020-01-15T09:30:00",
                    "layer": "data",
                    "event": "bar",
                    "data": {"close": 100.5},
                },
                {
                    "timestamp": "2020-01-15T09:31:00",
                    "layer": "data",
                    "event": "bar",
                    "data": {"volume": 1000},
                },
            ]
        )

        flattened = flatten_data_column(df)

        assert "data_close" in flattened.columns
        assert "data_volume" in flattened.columns
        # First row should have null volume
        assert flattened["data_volume"][0] is None
        # Second row should have null close
        assert flattened["data_close"][1] is None

    def test_flatten_data_column_preserves_other_columns(self) -> None:
        """Test that non-data columns are preserved."""
        df = pl.DataFrame(
            [
                {
                    "timestamp": "2020-01-15T09:30:00",
                    "layer": "data",
                    "event": "bar_received",
                    "asset": "AAPL",
                    "data": {"close": 100.5},
                },
            ]
        )

        flattened = flatten_data_column(df)

        assert "timestamp" in flattened.columns
        assert "layer" in flattened.columns
        assert "event" in flattened.columns
        assert "asset" in flattened.columns
        assert flattened["asset"][0] == "AAPL"

    def test_flatten_data_column_empty_data_dict(self) -> None:
        """Test flattening with empty data dict."""
        df = pl.DataFrame(
            [
                {
                    "timestamp": "2020-01-15T09:30:00",
                    "layer": "data",
                    "event": "bar_received",
                    "data": {},
                },
            ]
        )

        flattened = flatten_data_column(df)

        # data column should be removed, no data_* columns added
        assert "data" not in flattened.columns

    def test_flatten_data_column_empty_dataframe(self) -> None:
        """Test flattening empty DataFrame with data column."""
        df = pl.DataFrame(
            schema={
                "timestamp": pl.Utf8,
                "layer": pl.Utf8,
                "event": pl.Utf8,
                "data": pl.Object,
            }
        )

        flattened = flatten_data_column(df)

        assert "data" not in flattened.columns
        assert len(flattened) == 0

    def test_flatten_data_column_deterministic_order(self) -> None:
        """Test that flattened columns have deterministic order."""
        df = pl.DataFrame(
            [
                {
                    "timestamp": "2020-01-15T09:30:00",
                    "layer": "data",
                    "event": "bar",
                    "data": {"z_field": 1, "a_field": 2, "m_field": 3},
                },
            ]
        )

        flattened = flatten_data_column(df)

        # Columns should be sorted alphabetically
        data_cols = [c for c in flattened.columns if c.startswith("data_")]
        assert data_cols == ["data_a_field", "data_m_field", "data_z_field"]
