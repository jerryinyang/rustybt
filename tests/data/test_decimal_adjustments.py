"""Tests for Decimal-based adjustment calculations.

Tests cover split and dividend adjustments with various edge cases
and precision scenarios.
"""

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from rustybt.data.decimal_adjustments import (
    NegativePriceError,
    apply_dividend_adjustment,
    apply_dividend_adjustment_to_dataframe,
    apply_split_adjustment,
    apply_split_adjustment_to_dataframe,
)


class TestSplitAdjustment:
    """Test split adjustment calculations."""

    def test_simple_2_for_1_split(self):
        """Test 2-for-1 split halves prices."""
        prices = pl.Series(
            [Decimal("100.00"), Decimal("102.50"), Decimal("105.00")],
            dtype=pl.Decimal(18, 8),
        )
        split_ratio = Decimal("2.0")

        adjusted = apply_split_adjustment(prices, split_ratio)

        assert adjusted[0] == Decimal("50.00")
        assert adjusted[1] == Decimal("51.25")
        assert adjusted[2] == Decimal("52.50")

    def test_3_for_1_split(self):
        """Test 3-for-1 split divides prices by 3."""
        prices = pl.Series(
            [Decimal("300.00"), Decimal("303.00")],
            dtype=pl.Decimal(18, 8),
        )
        split_ratio = Decimal("3.0")

        adjusted = apply_split_adjustment(prices, split_ratio)

        assert adjusted[0] == Decimal("100.00")
        assert adjusted[1] == Decimal("101.00")

    def test_reverse_split_1_for_2(self):
        """Test reverse split (1-for-2) doubles prices."""
        prices = pl.Series(
            [Decimal("50.00"), Decimal("52.00")],
            dtype=pl.Decimal(18, 8),
        )
        split_ratio = Decimal("0.5")

        adjusted = apply_split_adjustment(prices, split_ratio)

        assert adjusted[0] == Decimal("100.00")
        assert adjusted[1] == Decimal("104.00")

    def test_fractional_split_ratio(self):
        """Test split with fractional ratio."""
        prices = pl.Series(
            [Decimal("100.00")],
            dtype=pl.Decimal(18, 8),
        )
        split_ratio = Decimal("1.5")

        adjusted = apply_split_adjustment(prices, split_ratio)

        # Polars divides Decimals and truncates to schema precision (18, 8)
        # 100.00 / 1.5 = 66.666666666666... truncated to 66.66666667 (8 decimals)
        # But Polars keeps more precision internally (14 decimals in this case)
        expected = Decimal("66.666666666666")
        assert adjusted[0] == expected

    def test_high_precision_split(self):
        """Test split preserves high-precision Decimal values."""
        prices = pl.Series(
            [Decimal("123.45678901")],
            dtype=pl.Decimal(18, 8),
        )
        split_ratio = Decimal("2.0")

        adjusted = apply_split_adjustment(prices, split_ratio)

        # Polars maintains precision based on the operation
        # 123.45678901 / 2.0 = 61.728394505
        expected = Decimal("61.728394505000")
        assert adjusted[0] == expected

    def test_zero_split_ratio_raises_error(self):
        """Test that zero split ratio raises ValueError."""
        prices = pl.Series([Decimal("100.00")], dtype=pl.Decimal(18, 8))

        with pytest.raises(ValueError, match="Split ratio must be positive"):
            apply_split_adjustment(prices, Decimal("0"))

    def test_negative_split_ratio_raises_error(self):
        """Test that negative split ratio raises ValueError."""
        prices = pl.Series([Decimal("100.00")], dtype=pl.Decimal(18, 8))

        with pytest.raises(ValueError, match="Split ratio must be positive"):
            apply_split_adjustment(prices, Decimal("-2.0"))

    def test_non_decimal_prices_raises_error(self):
        """Test that non-Decimal dtype raises TypeError."""
        prices = pl.Series([100.0, 102.5], dtype=pl.Float64)

        with pytest.raises(TypeError, match="Prices must be Decimal dtype"):
            apply_split_adjustment(prices, Decimal("2.0"))

    def test_empty_series(self):
        """Test split adjustment on empty series."""
        prices = pl.Series([], dtype=pl.Decimal(18, 8))
        split_ratio = Decimal("2.0")

        adjusted = apply_split_adjustment(prices, split_ratio)

        assert len(adjusted) == 0
        assert isinstance(adjusted.dtype, pl.Decimal)


class TestDividendAdjustment:
    """Test dividend adjustment calculations."""

    def test_simple_dividend_adjustment(self):
        """Test dividend adjustment subtracts from prices."""
        prices = pl.Series(
            [Decimal("100.00"), Decimal("102.50"), Decimal("105.00")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("2.50")

        adjusted = apply_dividend_adjustment(prices, dividend)

        assert adjusted[0] == Decimal("97.50")
        assert adjusted[1] == Decimal("100.00")
        assert adjusted[2] == Decimal("102.50")

    def test_small_dividend(self):
        """Test adjustment with small dividend amount."""
        prices = pl.Series(
            [Decimal("100.00")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("0.25")

        adjusted = apply_dividend_adjustment(prices, dividend)

        assert adjusted[0] == Decimal("99.75")

    def test_large_dividend(self):
        """Test adjustment with large dividend amount."""
        prices = pl.Series(
            [Decimal("100.00")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("50.00")

        adjusted = apply_dividend_adjustment(prices, dividend)

        assert adjusted[0] == Decimal("50.00")

    def test_high_precision_dividend(self):
        """Test dividend with high-precision Decimal value."""
        prices = pl.Series(
            [Decimal("100.00000000")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("1.23456789")

        adjusted = apply_dividend_adjustment(prices, dividend)

        # Precision preserved to 8 decimals (schema limit)
        expected = Decimal("98.76543211")
        assert adjusted[0] == expected

    def test_negative_price_raises_error_by_default(self):
        """Test that negative adjusted prices raise NegativePriceError."""
        prices = pl.Series(
            [Decimal("10.00")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("15.00")  # Dividend larger than price

        with pytest.raises(NegativePriceError, match="negative prices"):
            apply_dividend_adjustment(prices, dividend)

    def test_negative_price_allowed_when_validation_disabled(self):
        """Test negative prices allowed when validate_non_negative=False."""
        prices = pl.Series(
            [Decimal("10.00")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("15.00")

        adjusted = apply_dividend_adjustment(prices, dividend, validate_non_negative=False)

        assert adjusted[0] == Decimal("-5.00")

    def test_negative_dividend_raises_error(self):
        """Test that negative dividend raises ValueError."""
        prices = pl.Series([Decimal("100.00")], dtype=pl.Decimal(18, 8))

        with pytest.raises(ValueError, match="cannot be negative"):
            apply_dividend_adjustment(prices, Decimal("-2.50"))

    def test_non_decimal_prices_raises_error(self):
        """Test that non-Decimal dtype raises TypeError."""
        prices = pl.Series([100.0, 102.5], dtype=pl.Float64)

        with pytest.raises(TypeError, match="Prices must be Decimal dtype"):
            apply_dividend_adjustment(prices, Decimal("2.50"))

    def test_zero_dividend(self):
        """Test zero dividend leaves prices unchanged."""
        prices = pl.Series(
            [Decimal("100.00"), Decimal("102.50")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("0.00")

        adjusted = apply_dividend_adjustment(prices, dividend)

        assert adjusted[0] == Decimal("100.00")
        assert adjusted[1] == Decimal("102.50")

    def test_empty_series(self):
        """Test dividend adjustment on empty series."""
        prices = pl.Series([], dtype=pl.Decimal(18, 8))
        dividend = Decimal("2.50")

        adjusted = apply_dividend_adjustment(prices, dividend)

        assert len(adjusted) == 0
        assert isinstance(adjusted.dtype, pl.Decimal)


class TestSplitAdjustmentDataFrame:
    """Test split adjustment on DataFrames."""

    def test_split_adjustment_all_ohlc_columns(self):
        """Test split adjustment applies to all OHLC columns."""
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1), date(2023, 1, 2)],
                "sid": [1, 1],
                "open": [Decimal("100.00"), Decimal("102.00")],
                "high": [Decimal("105.00"), Decimal("107.00")],
                "low": [Decimal("98.00"), Decimal("100.00")],
                "close": [Decimal("103.00"), Decimal("105.00")],
                "volume": [Decimal("1000000"), Decimal("1500000")],
            }
        )

        split_ratio = Decimal("2.0")
        adjusted = apply_split_adjustment_to_dataframe(df, split_ratio)

        # Verify prices are halved
        assert adjusted["open"][0] == Decimal("50.00")
        assert adjusted["high"][0] == Decimal("52.50")
        assert adjusted["low"][0] == Decimal("49.00")
        assert adjusted["close"][0] == Decimal("51.50")

        # Verify volume is NOT adjusted (function only adjusts prices)
        assert adjusted["volume"][0] == Decimal("1000000")

    def test_split_adjustment_custom_columns(self):
        """Test split adjustment with custom column selection."""
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1)],
                "price": [Decimal("100.00")],
                "other": [Decimal("50.00")],
            }
        )

        split_ratio = Decimal("2.0")
        adjusted = apply_split_adjustment_to_dataframe(df, split_ratio, price_columns=["price"])

        # Only "price" column is adjusted
        assert adjusted["price"][0] == Decimal("50.00")
        assert adjusted["other"][0] == Decimal("50.00")  # Unchanged

    def test_missing_column_raises_error(self):
        """Test that missing price column raises KeyError."""
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1)],
                "open": [Decimal("100.00")],
            }
        )

        with pytest.raises(KeyError, match="Price columns not found"):
            apply_split_adjustment_to_dataframe(df, Decimal("2.0"), price_columns=["open", "close"])


class TestDividendAdjustmentDataFrame:
    """Test dividend adjustment on DataFrames."""

    def test_dividend_adjustment_all_ohlc_columns(self):
        """Test dividend adjustment applies to all OHLC columns."""
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1), date(2023, 1, 2)],
                "sid": [1, 1],
                "open": [Decimal("100.00"), Decimal("102.00")],
                "high": [Decimal("105.00"), Decimal("107.00")],
                "low": [Decimal("98.00"), Decimal("100.00")],
                "close": [Decimal("103.00"), Decimal("105.00")],
                "volume": [Decimal("1000000"), Decimal("1500000")],
            }
        )

        dividend = Decimal("2.50")
        adjusted = apply_dividend_adjustment_to_dataframe(df, dividend)

        # Verify dividend subtracted from all prices
        assert adjusted["open"][0] == Decimal("97.50")
        assert adjusted["high"][0] == Decimal("102.50")
        assert adjusted["low"][0] == Decimal("95.50")
        assert adjusted["close"][0] == Decimal("100.50")

        # Verify volume is NOT adjusted
        assert adjusted["volume"][0] == Decimal("1000000")

    def test_dividend_adjustment_custom_columns(self):
        """Test dividend adjustment with custom column selection."""
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1)],
                "price": [Decimal("100.00")],
                "other": [Decimal("50.00")],
            }
        )

        dividend = Decimal("2.50")
        adjusted = apply_dividend_adjustment_to_dataframe(df, dividend, price_columns=["price"])

        # Only "price" column is adjusted
        assert adjusted["price"][0] == Decimal("97.50")
        assert adjusted["other"][0] == Decimal("50.00")  # Unchanged

    def test_negative_price_validation_in_dataframe(self):
        """Test that negative prices raise error in DataFrame adjustment."""
        df = pl.DataFrame(
            {
                "open": [Decimal("10.00")],
                "high": [Decimal("15.00")],
                "low": [Decimal("9.00")],
                "close": [Decimal("12.00")],
            }
        )

        dividend = Decimal("15.00")

        with pytest.raises(NegativePriceError, match="negative prices"):
            apply_dividend_adjustment_to_dataframe(df, dividend)

    def test_negative_price_allowed_when_validation_disabled(self):
        """Test negative prices allowed in DataFrame when validation disabled."""
        df = pl.DataFrame(
            {
                "open": [Decimal("10.00")],
                "high": [Decimal("15.00")],
                "low": [Decimal("9.00")],
                "close": [Decimal("12.00")],
            }
        )

        dividend = Decimal("15.00")
        adjusted = apply_dividend_adjustment_to_dataframe(df, dividend, validate_non_negative=False)

        assert adjusted["open"][0] == Decimal("-5.00")
        assert adjusted["close"][0] == Decimal("-3.00")

    def test_missing_column_raises_error(self):
        """Test that missing price column raises KeyError."""
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1)],
                "open": [Decimal("100.00")],
            }
        )

        with pytest.raises(KeyError, match="Price columns not found"):
            apply_dividend_adjustment_to_dataframe(
                df, Decimal("2.50"), price_columns=["open", "close"]
            )


class TestPrecisionPreservation:
    """Test that adjustments preserve Decimal precision."""

    def test_split_maintains_exact_decimal_precision(self):
        """Test split adjustment maintains exact Decimal precision."""
        # Use values that would lose precision with float64
        prices = pl.Series(
            [Decimal("123.45678901"), Decimal("987.65432109")],
            dtype=pl.Decimal(18, 8),
        )
        split_ratio = Decimal("3.0")

        adjusted = apply_split_adjustment(prices, split_ratio)

        # Polars maintains precision based on operation
        # 123.45678901 / 3.0 = 41.152263003333...
        assert adjusted[0] == Decimal("41.152263003333")
        assert adjusted[1] == Decimal("329.21810703000")

    def test_dividend_maintains_exact_decimal_precision(self):
        """Test dividend adjustment maintains exact Decimal precision."""
        prices = pl.Series(
            [Decimal("100.00000001")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("0.00000001")

        adjusted = apply_dividend_adjustment(prices, dividend)

        assert adjusted[0] == Decimal("100.00000000")

    def test_no_floating_point_errors(self):
        """Test that adjustments avoid floating-point rounding errors."""
        # Classic float precision problem: 0.1 + 0.2 != 0.3
        prices = pl.Series(
            [Decimal("0.30")],
            dtype=pl.Decimal(18, 8),
        )
        dividend = Decimal("0.10")

        adjusted = apply_dividend_adjustment(prices, dividend)

        # With Decimal, this is exact
        assert adjusted[0] == Decimal("0.20")

    def test_repeated_adjustments_preserve_precision(self):
        """Test that multiple adjustments don't accumulate errors."""
        prices = pl.Series([Decimal("100.00")], dtype=pl.Decimal(18, 8))

        # Apply split adjustment twice
        adjusted1 = apply_split_adjustment(prices, Decimal("2.0"))
        adjusted2 = apply_split_adjustment(adjusted1, Decimal("2.0"))

        # Should be exactly 25.00, not 24.999999...
        assert adjusted2[0] == Decimal("25.00")
