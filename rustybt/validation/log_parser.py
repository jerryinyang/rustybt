"""
Log Parsing Utilities.

This module provides functionality to parse JSONL logs into Polars DataFrames
and validate log schemas. Supports Parquet caching for improved performance
on large log files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl


# Valid layer values for log entries - must match the 5-layer validation architecture
VALID_LAYERS: set[str] = {"data", "signals", "orders", "broker", "portfolio"}

# Required fields for log schema validation
REQUIRED_FIELDS: set[str] = {"timestamp", "layer", "event"}

# Optional fields that may be present
OPTIONAL_FIELDS: set[str] = {"asset", "data"}


class LogParseError(Exception):
    """Exception raised for log parsing errors."""

    pass


@dataclass
class ValidationResult:
    """Result of log schema validation.

    Attributes:
        valid: True if no schema errors were found
        line_count: Total number of lines processed
        errors: List of error messages with line numbers
    """

    valid: bool
    line_count: int
    errors: list[str]

    def __str__(self) -> str:
        """Format validation result for display."""
        if self.valid:
            return f"✓ Valid ({self.line_count} lines)"
        return f"✗ Invalid ({len(self.errors)} errors)"


def parse_log(log_path: Path, use_cache: bool = True) -> pl.DataFrame:
    """Parse JSONL log file to Polars DataFrame with optional Parquet caching.

    This function efficiently parses JSONL validation logs into a Polars
    DataFrame. When caching is enabled, it creates a Parquet cache file
    at the same location for faster subsequent reads.

    Args:
        log_path: Path to JSONL log file
        use_cache: If True, use/create Parquet cache (default: True)

    Returns:
        Polars DataFrame with all log records. The DataFrame includes:
        - timestamp: Log entry timestamp
        - layer: Validation layer (data, signals, orders, broker, portfolio)
        - event: Event type (bar_received, signal_generated, etc.)
        - asset: Asset symbol (optional, may be null)
        - data_*: Flattened fields from nested 'data' dict

    Raises:
        LogParseError: If log file contains invalid JSON or schema errors
        FileNotFoundError: If log file does not exist

    Example:
        >>> df = parse_log(Path("rustybt.jsonl"))
        >>> df.filter(pl.col("layer") == "data").head()
    """
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    cache_path = log_path.with_suffix(".parquet")

    # Check cache validity
    if use_cache and cache_path.exists():
        # Cache is valid if it's newer than the source file
        if cache_path.stat().st_mtime > log_path.stat().st_mtime:
            return pl.read_parquet(cache_path)

    # Parse JSONL file
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    with open(log_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Parse JSON
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")
                continue

            # Validate schema
            validation_errors = _validate_record_schema(record, line_num)
            if validation_errors:
                errors.extend(validation_errors)
                continue

            records.append(record)

    # Raise if any errors occurred
    if errors:
        raise LogParseError(
            f"Log parsing failed with {len(errors)} error(s):\n"
            + "\n".join(errors[:10])  # Show first 10 errors
            + (f"\n... and {len(errors) - 10} more" if len(errors) > 10 else "")
        )

    # Handle empty log file
    if not records:
        return pl.DataFrame(
            schema={
                "timestamp": pl.Utf8,
                "layer": pl.Utf8,
                "event": pl.Utf8,
                "asset": pl.Utf8,
            }
        )

    # Convert to DataFrame with explicit schema inference
    # Use infer_schema_length=None to read all rows for schema inference
    # This handles cases where early rows have null for a column that later has strings
    df = pl.DataFrame(records, infer_schema_length=None)

    # Flatten nested 'data' column if present
    df = flatten_data_column(df)

    # Write to cache
    if use_cache:
        df.write_parquet(cache_path)

    return df


def flatten_data_column(df: pl.DataFrame) -> pl.DataFrame:
    """Expand nested 'data' dict column into prefixed columns.

    Takes a DataFrame with a 'data' column containing dictionaries and
    expands it into separate columns prefixed with 'data_'.

    Args:
        df: DataFrame potentially containing a 'data' column with dicts

    Returns:
        DataFrame with flattened columns. Original 'data' column is removed.
        New columns are named 'data_{key}' for each key found in the dicts.
        Missing keys in individual records result in null values.

    Example:
        Input:  {"timestamp": "...", "layer": "data", "data": {"close": 100.5}}
        Output: {"timestamp": "...", "layer": "data", "data_close": 100.5}
    """
    if "data" not in df.columns:
        return df

    if df.is_empty():
        return df.drop("data")

    # Extract all unique keys from data dicts
    data_keys: set[str] = set()
    data_values = df["data"].to_list()

    for data_dict in data_values:
        if isinstance(data_dict, dict):
            data_keys.update(data_dict.keys())

    if not data_keys:
        # No dict data to flatten, just drop the column
        return df.drop("data")

    # Create new columns for each key
    # Use Utf8 (string) dtype to ensure Parquet compatibility
    # Values will be automatically converted to strings
    new_columns: list[pl.Expr] = []
    for key in sorted(data_keys):  # Sort for deterministic column order
        new_columns.append(
            pl.col("data")
            .map_elements(
                lambda x, k=key: str(x.get(k)) if isinstance(x, dict) and x.get(k) is not None else None,
                return_dtype=pl.Utf8,
            )
            .alias(f"data_{key}")
        )

    # Add new columns and drop original
    df = df.with_columns(new_columns)
    df = df.drop("data")

    return df


def _validate_record_schema(record: dict[str, Any], line_num: int) -> list[str]:
    """Validate a single log record against the expected schema.

    Args:
        record: Parsed JSON record
        line_num: Line number for error reporting

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Check required fields
    if "timestamp" not in record:
        errors.append(f"Line {line_num}: Missing 'timestamp' field")

    if "layer" not in record:
        errors.append(f"Line {line_num}: Missing 'layer' field")
    elif record.get("layer") not in VALID_LAYERS:
        errors.append(
            f"Line {line_num}: Invalid layer '{record.get('layer')}', "
            f"must be one of: {', '.join(sorted(VALID_LAYERS))}"
        )

    if "event" not in record:
        errors.append(f"Line {line_num}: Missing 'event' field")

    return errors


def validate_log_schema(log_path: Path) -> ValidationResult:
    """Validate JSONL log file against expected schema.

    Validates that each line is valid JSON with required fields:
    - timestamp: Required on every entry
    - layer: Required, must be one of VALID_LAYERS
    - event: Required on every entry

    Args:
        log_path: Path to JSONL log file

    Returns:
        ValidationResult with valid flag, line count, and errors

    Note:
        Streams file to handle large logs efficiently (>100MB).
        Collects all errors rather than stopping at first.
    """
    errors: list[str] = []
    line_count = 0

    with open(log_path) as f:
        for line_num, line in enumerate(f, 1):
            line_count += 1
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Parse JSON
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")
                continue

            # Check required fields
            if "timestamp" not in entry:
                errors.append(f"Line {line_num}: Missing 'timestamp' field")

            if "layer" not in entry:
                errors.append(f"Line {line_num}: Missing 'layer' field")
            elif entry.get("layer") not in VALID_LAYERS:
                errors.append(
                    f"Line {line_num}: Invalid layer '{entry.get('layer')}', "
                    f"must be one of: {', '.join(sorted(VALID_LAYERS))}"
                )

            if "event" not in entry:
                errors.append(f"Line {line_num}: Missing 'event' field")

    return ValidationResult(
        valid=len(errors) == 0,
        line_count=line_count,
        errors=errors,
    )


def count_log_entries(log_path: Path) -> int:
    """Count the number of entries in a JSONL log file.

    Args:
        log_path: Path to JSONL log file

    Returns:
        Number of non-empty lines in the file
    """
    count = 0
    with open(log_path) as f:
        for line in f:
            if line.strip():
                count += 1
    return count
