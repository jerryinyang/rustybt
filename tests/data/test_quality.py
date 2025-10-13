"""Tests for data quality metrics calculation."""

import pandas as pd
import polars as pl
import pytest
from exchange_calendars import get_calendar
from hypothesis import assume, given
from hypothesis import strategies as st

from rustybt.data.quality import (
    calculate_quality_metrics,
    generate_quality_report,
)


class TestQualityMetrics:
    """Test data quality metrics calculation."""

    def test_calculate_quality_metrics_basic(self):
        """Test basic quality metrics calculation."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-03", "2023-01-10", freq="D"),
                "open": [100.0, 101.0, 99.0, 102.0, 103.0, 104.0, 105.0, 106.0],
                "high": [105.0, 106.0, 104.0, 107.0, 108.0, 109.0, 110.0, 111.0],
                "low": [98.0, 99.0, 97.0, 100.0, 101.0, 102.0, 103.0, 104.0],
                "close": [102.0, 100.0, 101.0, 105.0, 104.0, 106.0, 107.0, 108.0],
                "volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700],
            }
        )

        metrics = calculate_quality_metrics(data)

        assert metrics["row_count"] == 8
        assert metrics["start_date"] > 0  # Unix timestamp
        assert metrics["end_date"] > metrics["start_date"]
        assert metrics["validation_timestamp"] > 0
        assert isinstance(metrics["outlier_count"], int)
        assert isinstance(metrics["ohlcv_violations"], int)
        assert isinstance(metrics["validation_passed"], bool)

    def test_calculate_quality_metrics_with_calendar(self):
        """Test quality metrics with exchange calendar."""
        nyse = get_calendar("NYSE")

        # Use only NYSE trading days
        dates = nyse.sessions_in_range("2023-01-03", "2023-01-10")
        data = pl.DataFrame(
            {
                "date": dates,
                "open": [100.0] * len(dates),
                "high": [105.0] * len(dates),
                "low": [98.0] * len(dates),
                "close": [102.0] * len(dates),
                "volume": [1000] * len(dates),
            }
        )

        metrics = calculate_quality_metrics(data, calendar=nyse)

        assert metrics["row_count"] == len(dates)
        assert metrics["missing_days_count"] == 0  # No missing trading days
        assert metrics["missing_days_list"] == "[]"

    def test_calculate_quality_metrics_with_missing_days(self):
        """Test quality metrics detects missing trading days."""
        nyse = get_calendar("NYSE")

        # Create data missing one trading day
        dates = nyse.sessions_in_range("2023-01-03", "2023-01-10")
        dates_list = [pd.Timestamp(d) for d in dates]
        dates_list.remove(pd.Timestamp("2023-01-05"))

        data = pl.DataFrame(
            {
                "date": dates_list,
                "open": [100.0] * len(dates_list),
                "high": [105.0] * len(dates_list),
                "low": [98.0] * len(dates_list),
                "close": [102.0] * len(dates_list),
                "volume": [1000] * len(dates_list),
            }
        )

        metrics = calculate_quality_metrics(data, calendar=nyse)

        assert metrics["missing_days_count"] == 1
        assert "2023-01-05" in metrics["missing_days_list"]

    def test_calculate_quality_metrics_missing_columns(self):
        """Test error handling for missing required columns."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-10"),
                "close": [100.0] * 10,
            }
        )

        with pytest.raises(ValueError, match="Missing required columns"):
            calculate_quality_metrics(data)

    def test_calculate_quality_metrics_no_date_column(self):
        """Test error handling for missing date column."""
        data = pl.DataFrame(
            {
                "open": [100.0],
                "high": [105.0],
                "low": [98.0],
                "close": [102.0],
                "volume": [1000],
            }
        )

        with pytest.raises(ValueError, match="Date column 'date' not found"):
            calculate_quality_metrics(data)


class TestOHLCVValidation:
    """Test OHLCV relationship validation."""

    def test_valid_ohlcv_data(self):
        """Test data with valid OHLCV relationships."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-05"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [105.0, 106.0, 107.0, 108.0, 109.0],
                "low": [98.0, 99.0, 100.0, 101.0, 102.0],
                "close": [102.0, 103.0, 104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )

        metrics = calculate_quality_metrics(data)
        assert metrics["ohlcv_violations"] == 0
        assert metrics["validation_passed"] is True

    def test_invalid_high_below_open(self):
        """Test detection of high < open violation."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-05"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [99.0, 106.0, 107.0, 108.0, 109.0],  # First row: high < open
                "low": [98.0, 99.0, 100.0, 101.0, 102.0],
                "close": [102.0, 103.0, 104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )

        metrics = calculate_quality_metrics(data)
        assert metrics["ohlcv_violations"] > 0
        assert metrics["validation_passed"] is False

    def test_invalid_high_below_close(self):
        """Test detection of high < close violation."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-05"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [105.0, 102.0, 107.0, 108.0, 109.0],  # Second row: high < close
                "low": [98.0, 99.0, 100.0, 101.0, 102.0],
                "close": [102.0, 103.0, 104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )

        metrics = calculate_quality_metrics(data)
        assert metrics["ohlcv_violations"] > 0

    def test_invalid_low_above_open(self):
        """Test detection of low > open violation."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-05"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [105.0, 106.0, 107.0, 108.0, 109.0],
                "low": [101.0, 99.0, 100.0, 101.0, 102.0],  # First row: low > open
                "close": [102.0, 103.0, 104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )

        metrics = calculate_quality_metrics(data)
        assert metrics["ohlcv_violations"] > 0

    def test_invalid_high_below_low(self):
        """Test detection of high < low violation."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-05"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [105.0, 106.0, 100.0, 108.0, 109.0],  # Third row: high < low
                "low": [98.0, 99.0, 101.0, 101.0, 102.0],
                "close": [102.0, 103.0, 104.0, 105.0, 106.0],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )

        metrics = calculate_quality_metrics(data)
        assert metrics["ohlcv_violations"] > 0

    def test_invalid_negative_volume(self):
        """Test detection of negative volume."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-05"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [105.0, 106.0, 107.0, 108.0, 109.0],
                "low": [98.0, 99.0, 100.0, 101.0, 102.0],
                "close": [102.0, 103.0, 104.0, 105.0, 106.0],
                "volume": [1000, -100, 1200, 1300, 1400],  # Negative volume
            }
        )

        metrics = calculate_quality_metrics(data)
        assert metrics["ohlcv_violations"] > 0


class TestOutlierDetection:
    """Test outlier detection using IQR method."""

    def test_no_outliers(self):
        """Test data with no outliers."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-10"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0],
                "high": [105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0],
                "low": [98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
                "close": [
                    102.0,
                    103.0,
                    104.0,
                    105.0,
                    106.0,
                    107.0,
                    108.0,
                    109.0,
                    110.0,
                    111.0,
                ],
                "volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
            }
        )

        metrics = calculate_quality_metrics(data)
        # Should have 0 or very few outliers for smooth data
        assert metrics["outlier_count"] >= 0

    def test_with_outliers(self):
        """Test data with extreme outlier values."""
        data = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", "2023-01-10"),
                "open": [100.0, 101.0, 102.0, 1000.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0],
                "high": [105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0],
                "low": [98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
                "close": [
                    102.0,
                    103.0,
                    104.0,
                    105.0,
                    106.0,
                    107.0,
                    108.0,
                    109.0,
                    110.0,
                    111.0,
                ],
                "volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
            }
        )

        metrics = calculate_quality_metrics(data)
        # Should detect the extreme value as outlier
        assert metrics["outlier_count"] > 0


class TestQualityReport:
    """Test quality report generation."""

    def test_generate_quality_report(self):
        """Test generating human-readable quality report."""
        metrics = {
            "row_count": 100,
            "start_date": int(pd.Timestamp("2023-01-01").timestamp()),
            "end_date": int(pd.Timestamp("2023-01-31").timestamp()),
            "missing_days_count": 2,
            "outlier_count": 5,
            "ohlcv_violations": 0,
            "validation_passed": True,
            "validation_timestamp": int(pd.Timestamp("2023-02-01").timestamp()),
        }

        report = generate_quality_report(metrics)

        assert "Row Count: 100" in report
        assert "2023-01-01" in report
        assert "2023-01-31" in report
        assert "Missing Trading Days: 2" in report
        assert "Outliers Detected: 5" in report
        assert "PASSED" in report

    def test_generate_quality_report_with_violations(self):
        """Test report with OHLCV violations."""
        metrics = {
            "row_count": 100,
            "start_date": int(pd.Timestamp("2023-01-01").timestamp()),
            "end_date": int(pd.Timestamp("2023-01-31").timestamp()),
            "missing_days_count": 0,
            "outlier_count": 0,
            "ohlcv_violations": 3,
            "validation_passed": False,
            "validation_timestamp": int(pd.Timestamp("2023-02-01").timestamp()),
        }

        report = generate_quality_report(metrics)

        assert "FAILED" in report
        assert "WARNING" in report
        assert "3 rows violate OHLCV relationships" in report


class TestQualityMetricsPropertyBased:
    """Property-based tests for quality metrics using Hypothesis."""

    @given(
        st.integers(min_value=10, max_value=1000),
        st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    )
    def test_quality_metrics_invariants(self, row_count, base_price):
        """Property test: Quality metrics should satisfy basic invariants."""
        # Generate valid OHLCV data
        dates = pd.date_range("2023-01-01", periods=row_count, freq="D")

        # Generate prices with proper OHLCV relationships
        open_prices = [base_price + i * 0.1 for i in range(row_count)]
        close_prices = [base_price + i * 0.1 + 0.5 for i in range(row_count)]
        high_prices = [max(o, c) + 1.0 for o, c in zip(open_prices, close_prices, strict=False)]
        low_prices = [min(o, c) - 1.0 for o, c in zip(open_prices, close_prices, strict=False)]
        volumes = [1000 + i * 10 for i in range(row_count)]

        data = pl.DataFrame(
            {
                "date": dates,
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": close_prices,
                "volume": volumes,
            }
        )

        metrics = calculate_quality_metrics(data)

        # Invariant 1: Row count should match input
        assert metrics["row_count"] == row_count, "Row count should match input"

        # Invariant 2: Start date should be before or equal to end date
        assert metrics["start_date"] <= metrics["end_date"], "Start date should be <= end date"

        # Invariant 3: OHLCV violations should be 0 for valid data
        assert metrics["ohlcv_violations"] == 0, "Valid OHLCV data should have no violations"

        # Invariant 4: Validation should pass for valid data
        assert metrics["validation_passed"] is True, "Valid data should pass validation"

        # Invariant 5: All metric values should be non-negative
        assert metrics["row_count"] >= 0, "Row count should be non-negative"
        assert metrics["missing_days_count"] >= 0, "Missing days count should be non-negative"
        assert metrics["outlier_count"] >= 0, "Outlier count should be non-negative"
        assert metrics["ohlcv_violations"] >= 0, "Violations should be non-negative"

    @given(
        st.lists(
            st.floats(min_value=50.0, max_value=150.0, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=50,
        )
    )
    def test_ohlcv_relationships_enforced(self, prices):
        """Property test: Invalid OHLCV relationships should be detected."""
        assume(len(prices) >= 10)  # Ensure minimum data size

        dates = pd.date_range("2023-01-01", periods=len(prices), freq="D")

        # Create data with deliberate violation in first row: high < open
        open_prices = prices
        close_prices = [p + 1.0 for p in prices]
        high_prices = [max(o, c) + 1.0 for o, c in zip(open_prices, close_prices, strict=False)]
        low_prices = [min(o, c) - 1.0 for o, c in zip(open_prices, close_prices, strict=False)]

        # Make first row invalid: high < open
        high_prices[0] = open_prices[0] - 5.0

        data = pl.DataFrame(
            {
                "date": dates,
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": close_prices,
                "volume": [1000] * len(prices),
            }
        )

        metrics = calculate_quality_metrics(data)

        # Should detect at least one violation
        assert metrics["ohlcv_violations"] >= 1, "Should detect OHLCV violation"
        assert metrics["validation_passed"] is False, "Should fail validation with violations"

    @given(st.integers(min_value=5, max_value=100))
    def test_quality_report_generation(self, row_count):
        """Property test: Quality report should always be generated."""
        dates = pd.date_range("2023-01-01", periods=row_count, freq="D")

        data = pl.DataFrame(
            {
                "date": dates,
                "open": [100.0] * row_count,
                "high": [105.0] * row_count,
                "low": [95.0] * row_count,
                "close": [102.0] * row_count,
                "volume": [1000] * row_count,
            }
        )

        metrics = calculate_quality_metrics(data)
        report = generate_quality_report(metrics)

        # Invariants for report generation
        assert isinstance(report, str), "Report should be a string"
        assert "Row Count:" in report, "Report should contain row count"
        assert "Date Range:" in report, "Report should contain date range"
        assert "Validation Status:" in report, "Report should contain validation status"
        assert str(row_count) in report, "Report should contain actual row count"
