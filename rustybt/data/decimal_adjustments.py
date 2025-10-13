"""Decimal-based adjustment calculations for corporate actions.

This module provides functions to apply split and dividend adjustments
to price data using Decimal arithmetic for financial-grade precision.

All adjustments use Decimal types from Python's decimal module to avoid
floating-point rounding errors.
"""

from decimal import Decimal

import polars as pl
import structlog

logger = structlog.get_logger(__name__)


class AdjustmentError(Exception):
    """Base exception for adjustment calculation errors."""


class NegativePriceError(AdjustmentError):
    """Raised when adjustment results in negative prices."""


def apply_split_adjustment(
    prices: pl.Series,
    split_ratio: Decimal,
) -> pl.Series:
    """Apply split adjustment to price series using Decimal arithmetic.

    Args:
        prices: Polars Series with Decimal prices (pl.Decimal dtype)
        split_ratio: Split ratio as Decimal (e.g., Decimal("2.0") for 2-for-1)

    Returns:
        Adjusted prices as Polars Series with Decimal dtype

    Raises:
        ValueError: If split_ratio is zero or negative
        TypeError: If prices is not Decimal dtype

    Formula:
        adjusted_price = price / split_ratio

    Example:
        >>> prices = pl.Series([Decimal("100.00"), Decimal("102.50")], dtype=pl.Decimal(18, 8))
        >>> split_ratio = Decimal("2.0")
        >>> adjusted = apply_split_adjustment(prices, split_ratio)
        >>> assert adjusted[0] == Decimal("50.00")
        >>> assert adjusted[1] == Decimal("51.25")

    Note:
        This function adjusts historical prices backward in time. For a 2-for-1
        split on date T, all prices before T are divided by 2 to maintain
        continuity in returns calculations.
    """
    # Validate split ratio
    if split_ratio <= Decimal("0"):
        raise ValueError(f"Split ratio must be positive, got {split_ratio}")

    # Validate prices dtype
    if not isinstance(prices.dtype, pl.Decimal):
        raise TypeError(
            f"Prices must be Decimal dtype, got {prices.dtype}. "
            "Convert using: prices.cast(pl.Decimal(18, 8))"
        )

    logger.debug(
        "applying_split_adjustment",
        split_ratio=str(split_ratio),
        num_prices=len(prices),
    )

    # Use Polars expression for vectorized Decimal division
    # Polars natively supports Decimal arithmetic
    adjusted = prices / split_ratio

    logger.info(
        "split_adjustment_applied",
        split_ratio=str(split_ratio),
        num_prices=len(prices),
        min_price_before=str(prices.min()),
        min_price_after=str(adjusted.min()),
        max_price_before=str(prices.max()),
        max_price_after=str(adjusted.max()),
    )

    return adjusted


def apply_dividend_adjustment(
    prices: pl.Series,
    dividend_amount: Decimal,
    validate_non_negative: bool = True,
) -> pl.Series:
    """Apply dividend adjustment to price series using Decimal arithmetic.

    Args:
        prices: Polars Series with Decimal prices (pl.Decimal dtype)
        dividend_amount: Dividend per share as Decimal
        validate_non_negative: If True, raise error if adjusted prices go negative

    Returns:
        Adjusted prices as Polars Series with Decimal dtype

    Raises:
        NegativePriceError: If validation enabled and adjusted prices are negative
        ValueError: If dividend_amount is negative
        TypeError: If prices is not Decimal dtype

    Formula:
        adjusted_price = price - dividend_amount

    Validation:
        Ensures adjusted prices remain non-negative (if validate_non_negative=True)

    Example:
        >>> prices = pl.Series([Decimal("100.00"), Decimal("102.50")], dtype=pl.Decimal(18, 8))
        >>> dividend = Decimal("2.50")
        >>> adjusted = apply_dividend_adjustment(prices, dividend)
        >>> assert adjusted[0] == Decimal("97.50")
        >>> assert adjusted[1] == Decimal("100.00")

    Note:
        This function adjusts historical prices backward in time. For a dividend
        payment on ex-date T, all prices before T are reduced by the dividend
        amount to maintain continuity.
    """
    # Validate dividend amount
    if dividend_amount < Decimal("0"):
        raise ValueError(f"Dividend amount cannot be negative, got {dividend_amount}")

    # Validate prices dtype
    if not isinstance(prices.dtype, pl.Decimal):
        raise TypeError(
            f"Prices must be Decimal dtype, got {prices.dtype}. "
            "Convert using: prices.cast(pl.Decimal(18, 8))"
        )

    logger.debug(
        "applying_dividend_adjustment",
        dividend_amount=str(dividend_amount),
        num_prices=len(prices),
    )

    # Use Polars expression for vectorized Decimal subtraction
    adjusted = prices - dividend_amount

    # Validate non-negative prices if requested
    if validate_non_negative:
        min_adjusted = adjusted.min()
        if min_adjusted is not None and min_adjusted < Decimal("0"):
            raise NegativePriceError(
                f"Dividend adjustment results in negative prices. "
                f"Min adjusted price: {min_adjusted}, dividend: {dividend_amount}. "
                f"This may indicate incorrect dividend data or prices."
            )

    logger.info(
        "dividend_adjustment_applied",
        dividend_amount=str(dividend_amount),
        num_prices=len(prices),
        min_price_before=str(prices.min()),
        min_price_after=str(adjusted.min()),
        max_price_before=str(prices.max()),
        max_price_after=str(adjusted.max()),
    )

    return adjusted


def apply_split_adjustment_to_dataframe(
    df: pl.DataFrame,
    split_ratio: Decimal,
    price_columns: list[str] | None = None,
) -> pl.DataFrame:
    """Apply split adjustment to all price columns in DataFrame.

    Args:
        df: Polars DataFrame with Decimal price columns
        split_ratio: Split ratio as Decimal (e.g., Decimal("2.0") for 2-for-1)
        price_columns: List of price columns to adjust (default: OHLC columns)

    Returns:
        New DataFrame with adjusted price columns

    Raises:
        ValueError: If split_ratio is zero or negative
        KeyError: If specified price columns not found in DataFrame

    Example:
        >>> df = pl.DataFrame({
        ...     "date": [date(2023, 1, 1), date(2023, 1, 2)],
        ...     "open": [Decimal("100.00"), Decimal("102.00")],
        ...     "close": [Decimal("101.00"), Decimal("103.00")],
        ... })
        >>> adjusted = apply_split_adjustment_to_dataframe(df, Decimal("2.0"))
        >>> assert adjusted["open"][0] == Decimal("50.00")

    Note:
        Volume is NOT adjusted by this function. Volume adjustments must be
        applied separately (volume is multiplied by split_ratio, not divided).
    """
    if price_columns is None:
        price_columns = ["open", "high", "low", "close"]

    # Validate columns exist
    missing_cols = set(price_columns) - set(df.columns)
    if missing_cols:
        raise KeyError(f"Price columns not found in DataFrame: {missing_cols}")

    logger.debug(
        "applying_split_adjustment_to_dataframe",
        split_ratio=str(split_ratio),
        num_rows=len(df),
        price_columns=price_columns,
    )

    # Apply split adjustment to each price column
    adjusted_df = df.with_columns([(pl.col(col) / split_ratio).alias(col) for col in price_columns])

    return adjusted_df


def apply_dividend_adjustment_to_dataframe(
    df: pl.DataFrame,
    dividend_amount: Decimal,
    price_columns: list[str] | None = None,
    validate_non_negative: bool = True,
) -> pl.DataFrame:
    """Apply dividend adjustment to all price columns in DataFrame.

    Args:
        df: Polars DataFrame with Decimal price columns
        dividend_amount: Dividend per share as Decimal
        price_columns: List of price columns to adjust (default: OHLC columns)
        validate_non_negative: If True, raise error if adjusted prices go negative

    Returns:
        New DataFrame with adjusted price columns

    Raises:
        NegativePriceError: If validation enabled and adjusted prices are negative
        ValueError: If dividend_amount is negative
        KeyError: If specified price columns not found in DataFrame

    Example:
        >>> df = pl.DataFrame({
        ...     "date": [date(2023, 1, 1), date(2023, 1, 2)],
        ...     "open": [Decimal("100.00"), Decimal("102.00")],
        ...     "close": [Decimal("101.00"), Decimal("103.00")],
        ... })
        >>> adjusted = apply_dividend_adjustment_to_dataframe(df, Decimal("2.50"))
        >>> assert adjusted["open"][0] == Decimal("97.50")
    """
    if price_columns is None:
        price_columns = ["open", "high", "low", "close"]

    # Validate columns exist
    missing_cols = set(price_columns) - set(df.columns)
    if missing_cols:
        raise KeyError(f"Price columns not found in DataFrame: {missing_cols}")

    logger.debug(
        "applying_dividend_adjustment_to_dataframe",
        dividend_amount=str(dividend_amount),
        num_rows=len(df),
        price_columns=price_columns,
    )

    # Apply dividend adjustment to each price column
    adjusted_df = df.with_columns(
        [(pl.col(col) - dividend_amount).alias(col) for col in price_columns]
    )

    # Validate non-negative prices if requested
    if validate_non_negative:
        for col in price_columns:
            min_val = adjusted_df[col].min()
            if min_val is not None and min_val < Decimal("0"):
                raise NegativePriceError(
                    f"Dividend adjustment results in negative prices in column '{col}'. "
                    f"Min value: {min_val}, dividend: {dividend_amount}"
                )

    return adjusted_df
