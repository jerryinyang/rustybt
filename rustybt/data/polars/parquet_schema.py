"""Parquet schema definitions for OHLCV data with Decimal precision.

This module defines the schema for storing price data in Parquet format
with Decimal types to ensure financial-grade precision.

Schema Rationale:
- Decimal(18, 8): 18 total digits, 8 decimal places
  - Supports both cryptocurrency (e.g., 0.00000001 BTC satoshi)
  - Supports equities (e.g., 9999999.99 for high-priced stocks)
  - Total range: -999999999.99999999 to +999999999.99999999
- Date/Datetime: Native temporal types for efficient filtering
- Int64: Asset IDs (sids) for large universe support (up to 2^63-1 assets)

Example:
    >>> import polars as pl
    >>> from decimal import Decimal
    >>> df = pl.DataFrame({
    ...     "date": [pl.Date(2023, 1, 1)],
    ...     "sid": [1],
    ...     "open": [Decimal("100.12345678")],
    ...     "high": [Decimal("101.12345678")],
    ...     "low": [Decimal("99.12345678")],
    ...     "close": [Decimal("100.50000000")],
    ...     "volume": [Decimal("1000000")],
    ... }, schema=DAILY_BARS_SCHEMA)
"""

import polars as pl

# Daily bars schema
# Used for daily OHLCV data storage in Parquet format
DAILY_BARS_SCHEMA: dict[str, pl.DataType] = {
    "date": pl.Date,  # Trading date (local timezone)
    "sid": pl.Int64,  # Security ID (asset identifier)
    "open": pl.Decimal(precision=18, scale=8),  # Opening price
    "high": pl.Decimal(precision=18, scale=8),  # Highest price
    "low": pl.Decimal(precision=18, scale=8),  # Lowest price
    "close": pl.Decimal(precision=18, scale=8),  # Closing price
    "volume": pl.Decimal(precision=18, scale=8),  # Trading volume
}

# Minute bars schema
# Used for intraday minute-level OHLCV data storage
MINUTE_BARS_SCHEMA: dict[str, pl.DataType] = {
    "timestamp": pl.Datetime("us"),  # Timestamp with microsecond precision (UTC)
    "sid": pl.Int64,  # Security ID (asset identifier)
    "open": pl.Decimal(precision=18, scale=8),  # Opening price
    "high": pl.Decimal(precision=18, scale=8),  # Highest price
    "low": pl.Decimal(precision=18, scale=8),  # Lowest price
    "close": pl.Decimal(precision=18, scale=8),  # Closing price
    "volume": pl.Decimal(precision=18, scale=8),  # Trading volume
}

# Adjustments schema
# Used for corporate actions (splits, dividends)
ADJUSTMENTS_SCHEMA: dict[str, pl.DataType] = {
    "date": pl.Date,  # Effective date of adjustment
    "sid": pl.Int64,  # Security ID (asset identifier)
    "adjustment_type": pl.Utf8,  # Type: "split" or "dividend"
    "split_ratio": pl.Decimal(precision=18, scale=8),  # Split ratio (e.g., 2.0 for 2-for-1)
    "dividend_amount": pl.Decimal(precision=18, scale=8),  # Per-share dividend amount
}


def get_schema_for_frequency(frequency: str) -> dict[str, pl.DataType]:
    """Get appropriate schema for data frequency.

    Args:
        frequency: Data frequency - "daily" or "minute"

    Returns:
        Schema dictionary for the specified frequency

    Raises:
        ValueError: If frequency is not supported

    Example:
        >>> schema = get_schema_for_frequency("daily")
        >>> assert "date" in schema
        >>> assert schema["open"] == pl.Decimal(precision=18, scale=8)
    """
    if frequency == "daily":
        return DAILY_BARS_SCHEMA
    elif frequency == "minute":
        return MINUTE_BARS_SCHEMA
    else:
        raise ValueError(f"Unsupported frequency: {frequency}. Must be 'daily' or 'minute'")


def validate_schema(df: pl.DataFrame, expected_schema: dict[str, pl.DataType]) -> None:
    """Validate DataFrame schema matches expected schema.

    Args:
        df: Polars DataFrame to validate
        expected_schema: Expected schema dictionary

    Raises:
        ValueError: If schema doesn't match expectations

    Example:
        >>> df = pl.DataFrame({"date": [pl.Date(2023, 1, 1)], "sid": [1]})
        >>> validate_schema(df, {"date": pl.Date, "sid": pl.Int64})
    """
    df_schema = dict(zip(df.columns, df.dtypes, strict=False))

    # Check for missing columns
    missing_cols = set(expected_schema.keys()) - set(df_schema.keys())
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Check for extra columns
    extra_cols = set(df_schema.keys()) - set(expected_schema.keys())
    if extra_cols:
        raise ValueError(f"Unexpected extra columns: {extra_cols}")

    # Check data types match
    for col, expected_dtype in expected_schema.items():
        actual_dtype = df_schema[col]
        if actual_dtype != expected_dtype:
            raise ValueError(
                f"Column '{col}' has incorrect type. Expected {expected_dtype}, got {actual_dtype}"
            )
