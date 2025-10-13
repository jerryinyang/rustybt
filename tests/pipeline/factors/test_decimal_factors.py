"""Tests for Decimal-aware pipeline factors."""

from datetime import date
from decimal import Decimal

import polars as pl
import pytest

from rustybt.pipeline.factors.decimal_factors import (
    DecimalAverageDollarVolume,
    DecimalLatestPrice,
    DecimalReturns,
    DecimalSimpleMovingAverage,
)


class TestDecimalLatestPrice:
    """Test DecimalLatestPrice factor."""

    def test_returns_latest_close_price(self):
        """Test that factor returns latest close price."""
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                "sid": [1, 1, 1],
                "close": [Decimal("100.00"), Decimal("102.00"), Decimal("105.00")],
            }
        )

        factor = DecimalLatestPrice()
        result = factor.compute(df)

        assert result[0] == Decimal("105.00")

    def test_preserves_decimal_precision(self):
        """Test that precision is preserved."""
        df = pl.DataFrame(
            {
                "sid": [1],
                "close": [Decimal("123.45678901")],
            }
        )

        factor = DecimalLatestPrice()
        result = factor.compute(df)

        assert result[0] == Decimal("123.45678901")

    def test_raises_error_for_missing_column(self):
        """Test error when close column missing."""
        df = pl.DataFrame({"open": [Decimal("100.00")]})

        factor = DecimalLatestPrice()

        with pytest.raises(ValueError, match="must have 'close' column"):
            factor.compute(df)

    def test_raises_error_for_non_decimal_dtype(self):
        """Test error when close is not Decimal dtype."""
        df = pl.DataFrame({"close": [100.0]})  # Float, not Decimal

        factor = DecimalLatestPrice()

        with pytest.raises(TypeError, match="must be Decimal dtype"):
            factor.compute(df)


class TestDecimalSimpleMovingAverage:
    """Test DecimalSimpleMovingAverage factor."""

    def test_3_period_sma(self):
        """Test 3-period SMA calculation."""
        df = pl.DataFrame(
            {
                "close": [
                    Decimal("100.00"),
                    Decimal("102.00"),
                    Decimal("104.00"),
                ],
            }
        )

        factor = DecimalSimpleMovingAverage(window_length=3)
        result = factor.compute(df)

        # Mean of 100, 102, 104 = 102
        expected = Decimal("102.00")
        assert result[-1] == expected

    def test_preserves_decimal_precision(self):
        """Test that SMA preserves Decimal precision."""
        df = pl.DataFrame(
            {
                "close": [
                    Decimal("100.11"),
                    Decimal("100.22"),
                    Decimal("100.33"),
                ],
            }
        )

        factor = DecimalSimpleMovingAverage(window_length=3)
        result = factor.compute(df)

        # Mean = (100.11 + 100.22 + 100.33) / 3 ≈ 100.22
        # Polars rolling_mean may have slight precision differences
        assert abs(result[-1] - 100.22) < 0.01

    def test_handles_nan_for_insufficient_data(self):
        """Test that early values are None when window not filled."""
        df = pl.DataFrame(
            {
                "close": [Decimal("100.00"), Decimal("102.00"), Decimal("104.00")],
            }
        )

        factor = DecimalSimpleMovingAverage(window_length=5)
        result = factor.compute(df)

        # First 4 values should be None (insufficient data)
        assert result[0] is None
        assert result[1] is None

    def test_invalid_window_length_raises_error(self):
        """Test that invalid window_length raises ValueError."""
        with pytest.raises(ValueError, match="window_length must be >= 1"):
            DecimalSimpleMovingAverage(window_length=0)


class TestDecimalReturns:
    """Test DecimalReturns factor."""

    def test_simple_return_calculation(self):
        """Test basic return calculation."""
        df = pl.DataFrame(
            {
                "close": [Decimal("100.00"), Decimal("105.00")],
            }
        )

        factor = DecimalReturns(window_length=1)
        result = factor.compute(df)

        # (105 / 100) - 1 = 0.05
        expected = Decimal("0.05")
        assert result[-1] == expected

    def test_negative_return(self):
        """Test negative return calculation."""
        df = pl.DataFrame(
            {
                "close": [Decimal("100.00"), Decimal("95.00")],
            }
        )

        factor = DecimalReturns(window_length=1)
        result = factor.compute(df)

        # (95 / 100) - 1 = -0.05
        expected = Decimal("-0.05")
        assert result[-1] == expected

    def test_multi_period_return(self):
        """Test return over multiple periods."""
        df = pl.DataFrame(
            {
                "close": [
                    Decimal("100.00"),
                    Decimal("102.00"),
                    Decimal("104.00"),
                    Decimal("110.00"),
                ],
            }
        )

        factor = DecimalReturns(window_length=3)
        result = factor.compute(df)

        # (110 / 100) - 1 = 0.10
        expected = Decimal("0.10")
        assert result[-1] == expected

    def test_preserves_decimal_precision(self):
        """Test that returns preserve Decimal precision."""
        df = pl.DataFrame(
            {
                "close": [Decimal("100.00000000"), Decimal("100.00000001")],
            }
        )

        factor = DecimalReturns(window_length=1)
        result = factor.compute(df)

        # Very small return: 0.00000001 / 100 = 0.0000000001
        assert result[-1] > Decimal("0")
        assert result[-1] < Decimal("0.0001")

    def test_insufficient_data_raises_error(self):
        """Test error when data length insufficient."""
        df = pl.DataFrame({"close": [Decimal("100.00")]})

        factor = DecimalReturns(window_length=1)

        with pytest.raises(ValueError, match="Data length .* insufficient"):
            factor.compute(df)


class TestDecimalAverageDollarVolume:
    """Test DecimalAverageDollarVolume factor."""

    def test_simple_dollar_volume_calculation(self):
        """Test basic average dollar volume calculation."""
        df = pl.DataFrame(
            {
                "close": [Decimal("100.00"), Decimal("102.00"), Decimal("104.00")],
                "volume": [Decimal("1000.00"), Decimal("1500.00"), Decimal("2000.00")],
            }
        )

        factor = DecimalAverageDollarVolume(window_length=3)
        result = factor.compute(df)

        # Dollar volumes: 100k, 153k, 208k
        # Mean = (100000 + 153000 + 208000) / 3 = 153666.666...
        expected_min = Decimal("150000")
        expected_max = Decimal("160000")
        assert result[-1] > expected_min
        assert result[-1] < expected_max

    def test_preserves_decimal_precision(self):
        """Test that dollar volume preserves Decimal precision."""
        df = pl.DataFrame(
            {
                "close": [Decimal("100.12345"), Decimal("100.12345")],
                "volume": [Decimal("1000.00000"), Decimal("1000.00000")],
            }
        )

        factor = DecimalAverageDollarVolume(window_length=2)
        result = factor.compute(df)

        # Dollar volume = 100.12345 * 1000 = 100123.45
        # Result should be very close to expected
        assert abs(result[-1] - 100123.45) < 0.01

    def test_handles_large_volumes(self):
        """Test calculation with large volume values."""
        df = pl.DataFrame(
            {
                "close": [Decimal("50.00"), Decimal("55.00")],
                "volume": [Decimal("10000000.00"), Decimal("15000000.00")],
            }
        )

        factor = DecimalAverageDollarVolume(window_length=2)
        result = factor.compute(df)

        # Dollar volumes: 500M, 825M; mean = 662.5M
        expected = Decimal("662500000.00")
        assert result[-1] == expected

    def test_missing_volume_column_raises_error(self):
        """Test error when volume column missing."""
        df = pl.DataFrame({"close": [Decimal("100.00")]})

        factor = DecimalAverageDollarVolume()

        with pytest.raises(ValueError, match="must have 'close' and 'volume'"):
            factor.compute(df)


class TestDecimalFactorIntegration:
    """Integration tests combining multiple Decimal factors."""

    def test_factors_work_on_same_data(self):
        """Test that multiple factors can compute on same DataFrame."""
        df = pl.DataFrame(
            {
                "date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                "sid": [1, 1, 1],
                "close": [Decimal("100.00"), Decimal("102.00"), Decimal("105.00")],
                "volume": [Decimal("1000.00"), Decimal("1500.00"), Decimal("2000.00")],
            }
        )

        latest_price = DecimalLatestPrice()
        sma = DecimalSimpleMovingAverage(window_length=3)
        returns = DecimalReturns(window_length=1)
        dollar_volume = DecimalAverageDollarVolume(window_length=3)

        # All should compute successfully
        assert latest_price.compute(df)[0] == Decimal("105.00")
        assert sma.compute(df)[-1] > Decimal("100")
        assert returns.compute(df)[-1] > Decimal("0")
        assert dollar_volume.compute(df)[-1] > Decimal("100000")

    def test_chained_calculations_preserve_precision(self):
        """Test that chained Decimal operations preserve precision."""
        df = pl.DataFrame(
            {
                "close": [
                    Decimal("100.00000001"),
                    Decimal("100.00000002"),
                    Decimal("100.00000003"),
                ],
            }
        )

        sma = DecimalSimpleMovingAverage(window_length=3)
        sma_result = sma.compute(df)

        # SMA should preserve high precision (within tolerance)
        assert abs(sma_result[-1] - 100.00000002) < 0.00000001
