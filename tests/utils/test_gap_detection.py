"""Tests for gap detection utilities."""

import json
from datetime import datetime, timedelta

import pandas as pd
import polars as pl
import pytest
from exchange_calendars import get_calendar
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.utils.gap_detection import (
    detect_missing_days,
    detect_missing_days_count,
    format_missing_days_list,
    generate_gap_report,
    parse_missing_days_list,
)


class TestGapDetection:
    """Test gap detection for missing trading days."""

    @pytest.fixture
    def nyse_calendar(self):
        """NYSE calendar for testing."""
        return get_calendar("NYSE")

    def test_detect_no_gaps(self, nyse_calendar):
        """Test data with no missing trading days."""
        # Create data with all NYSE trading days in range
        dates = nyse_calendar.sessions_in_range("2023-01-03", "2023-01-10")
        data = pl.DataFrame({"date": dates, "close": [100.0] * len(dates)})

        gaps = detect_missing_days(data, nyse_calendar)
        assert len(gaps) == 0

    def test_detect_single_gap(self, nyse_calendar):
        """Test data with one missing trading day."""
        # Create data missing 2023-01-05
        dates = nyse_calendar.sessions_in_range("2023-01-03", "2023-01-10")
        dates_list = [pd.Timestamp(d) for d in dates]
        dates_list.remove(pd.Timestamp("2023-01-05"))

        data = pl.DataFrame({"date": dates_list, "close": [100.0] * len(dates_list)})

        gaps = detect_missing_days(data, nyse_calendar)
        assert len(gaps) == 1
        assert gaps[0] == pd.Timestamp("2023-01-05")

    def test_detect_multiple_gaps(self, nyse_calendar):
        """Test data with multiple missing trading days."""
        # Create data missing 2023-01-05 and 2023-01-09
        dates = nyse_calendar.sessions_in_range("2023-01-03", "2023-01-10")
        dates_list = [pd.Timestamp(d) for d in dates]
        dates_list.remove(pd.Timestamp("2023-01-05"))
        dates_list.remove(pd.Timestamp("2023-01-09"))

        data = pl.DataFrame({"date": dates_list, "close": [100.0] * len(dates_list)})

        gaps = detect_missing_days(data, nyse_calendar)
        assert len(gaps) == 2
        assert pd.Timestamp("2023-01-05") in gaps
        assert pd.Timestamp("2023-01-09") in gaps

    def test_detect_gaps_custom_date_column(self, nyse_calendar):
        """Test gap detection with custom date column name."""
        dates = nyse_calendar.sessions_in_range("2023-01-03", "2023-01-10")
        dates_list = [pd.Timestamp(d) for d in dates]
        dates_list.remove(pd.Timestamp("2023-01-05"))

        data = pl.DataFrame({"timestamp": dates_list, "close": [100.0] * len(dates_list)})

        gaps = detect_missing_days(data, nyse_calendar, date_column="timestamp")
        assert len(gaps) == 1
        assert gaps[0] == pd.Timestamp("2023-01-05")

    def test_detect_gaps_empty_data(self, nyse_calendar):
        """Test gap detection with empty DataFrame."""
        data = pl.DataFrame({"date": [], "close": []})
        gaps = detect_missing_days(data, nyse_calendar)
        assert len(gaps) == 0

    def test_detect_gaps_missing_date_column(self, nyse_calendar):
        """Test error handling for missing date column."""
        data = pl.DataFrame({"close": [100.0, 101.0]})
        with pytest.raises(ValueError, match="Date column 'date' not found"):
            detect_missing_days(data, nyse_calendar)

    def test_detect_missing_days_count(self, nyse_calendar):
        """Test counting missing trading days."""
        dates = nyse_calendar.sessions_in_range("2023-01-03", "2023-01-10")
        dates_list = [pd.Timestamp(d) for d in dates]
        dates_list.remove(pd.Timestamp("2023-01-05"))
        dates_list.remove(pd.Timestamp("2023-01-09"))

        data = pl.DataFrame({"date": dates_list, "close": [100.0] * len(dates_list)})

        count = detect_missing_days_count(data, nyse_calendar)
        assert count == 2


class TestMissingDaysFormatting:
    """Test missing days list formatting and parsing."""

    def test_format_empty_list(self):
        """Test formatting empty missing days list."""
        result = format_missing_days_list([])
        assert result == "[]"

    def test_format_single_day(self):
        """Test formatting single missing day."""
        missing_days = [pd.Timestamp("2023-01-05")]
        result = format_missing_days_list(missing_days)
        expected = json.dumps(["2023-01-05"])
        assert result == expected

    def test_format_multiple_days(self):
        """Test formatting multiple missing days."""
        missing_days = [pd.Timestamp("2023-01-05"), pd.Timestamp("2023-01-09")]
        result = format_missing_days_list(missing_days)
        expected = json.dumps(["2023-01-05", "2023-01-09"])
        assert result == expected

    def test_parse_empty_list(self):
        """Test parsing empty missing days list."""
        result = parse_missing_days_list("[]")
        assert result == []

        result = parse_missing_days_list(None)
        assert result == []

    def test_parse_single_day(self):
        """Test parsing single missing day."""
        json_str = json.dumps(["2023-01-05"])
        result = parse_missing_days_list(json_str)
        assert len(result) == 1
        assert result[0] == pd.Timestamp("2023-01-05")

    def test_parse_multiple_days(self):
        """Test parsing multiple missing days."""
        json_str = json.dumps(["2023-01-05", "2023-01-09"])
        result = parse_missing_days_list(json_str)
        assert len(result) == 2
        assert result[0] == pd.Timestamp("2023-01-05")
        assert result[1] == pd.Timestamp("2023-01-09")

    def test_roundtrip_format_parse(self):
        """Test roundtrip formatting and parsing."""
        original = [
            pd.Timestamp("2023-01-05"),
            pd.Timestamp("2023-01-09"),
            pd.Timestamp("2023-01-12"),
        ]
        formatted = format_missing_days_list(original)
        parsed = parse_missing_days_list(formatted)
        assert parsed == original


class TestGapReport:
    """Test gap report generation."""

    def test_gap_report_no_gaps(self):
        """Test report with no gaps."""
        report = generate_gap_report([])
        assert report["total_gaps"] == 0
        assert report["gap_ranges"] == []
        assert report["warnings"] == []

    def test_gap_report_single_day(self):
        """Test report with single missing day."""
        missing_days = [pd.Timestamp("2023-01-05")]
        report = generate_gap_report(missing_days, threshold=5)
        assert report["total_gaps"] == 1
        assert len(report["gap_ranges"]) == 1
        assert report["gap_ranges"][0][2] == 1  # Count of consecutive days
        assert report["warnings"] == []  # Below threshold

    def test_gap_report_consecutive_days_below_threshold(self):
        """Test report with consecutive days below warning threshold."""
        missing_days = [
            pd.Timestamp("2023-01-05"),
            pd.Timestamp("2023-01-06"),
            pd.Timestamp("2023-01-09"),
        ]
        report = generate_gap_report(missing_days, threshold=5)
        assert report["total_gaps"] == 3
        assert len(report["gap_ranges"]) == 2  # Two separate ranges
        assert report["warnings"] == []

    def test_gap_report_consecutive_days_above_threshold(self):
        """Test report with consecutive days exceeding threshold."""
        missing_days = [
            pd.Timestamp("2023-01-05"),
            pd.Timestamp("2023-01-06"),
            pd.Timestamp("2023-01-09"),
            pd.Timestamp("2023-01-10"),
            pd.Timestamp("2023-01-11"),
            pd.Timestamp("2023-01-12"),
            pd.Timestamp("2023-01-13"),
            pd.Timestamp("2023-01-16"),
        ]
        report = generate_gap_report(missing_days, threshold=3)

        assert report["total_gaps"] == 8
        assert len(report["warnings"]) > 0
        # Should have warning for 2023-01-09 to 2023-01-13 (5 days)
        assert any("5 consecutive days" in w for w in report["warnings"])

    def test_gap_report_multiple_ranges(self):
        """Test report with multiple gap ranges."""
        missing_days = [
            pd.Timestamp("2023-01-05"),
            pd.Timestamp("2023-01-06"),
            pd.Timestamp("2023-01-10"),
            pd.Timestamp("2023-01-15"),
            pd.Timestamp("2023-01-16"),
            pd.Timestamp("2023-01-17"),
        ]
        report = generate_gap_report(missing_days, threshold=5)

        assert report["total_gaps"] == 6
        assert len(report["gap_ranges"]) == 3
        # Check ranges are correctly identified
        ranges_counts = [r[2] for r in report["gap_ranges"]]
        assert 2 in ranges_counts  # 2023-01-05 to 01-06
        assert 1 in ranges_counts  # 2023-01-10
        assert 3 in ranges_counts  # 2023-01-15 to 01-17

    def test_gap_report_unsorted_input(self):
        """Test that report handles unsorted input correctly."""
        missing_days = [
            pd.Timestamp("2023-01-10"),
            pd.Timestamp("2023-01-05"),
            pd.Timestamp("2023-01-06"),
        ]
        report = generate_gap_report(missing_days, threshold=5)

        # Should sort and identify consecutive range
        assert report["total_gaps"] == 3
        assert len(report["gap_ranges"]) == 2


class TestGapDetectionPropertyBased:
    """Property-based tests for gap detection using Hypothesis."""

    @settings(deadline=1000)  # Allow 1 second for calendar operations
    @given(
        st.lists(
            st.dates(
                min_value=datetime(2020, 1, 1).date(), max_value=datetime(2023, 12, 31).date()
            ),
            min_size=10,
            max_size=50,
            unique=True,
        )
    )
    def test_gap_detection_invariants(self, dates):
        """Property test: Gap detection should satisfy basic invariants."""
        nyse_calendar = get_calendar("NYSE")

        # Convert dates to timestamps and filter to only include trading days
        trading_dates = [
            pd.Timestamp(d) for d in dates if nyse_calendar.is_session(pd.Timestamp(d))
        ]

        if len(trading_dates) < 2:
            # Skip if not enough trading days
            return

        sorted_dates = sorted(trading_dates)
        data = pl.DataFrame(
            {"date": [pd.Timestamp(d) for d in sorted_dates], "close": [100.0] * len(sorted_dates)}
        )

        gaps = detect_missing_days(data, nyse_calendar)

        # Invariant 1: All detected gaps should be valid trading days
        for gap in gaps:
            assert nyse_calendar.is_session(gap), f"Gap {gap} is not a trading day"

        # Invariant 2: Gap count should be non-negative
        gap_count = detect_missing_days_count(data, nyse_calendar)
        assert gap_count >= 0, "Gap count should be non-negative"

        # Invariant 3: Gap count should match length of gaps list
        assert gap_count == len(gaps), "Gap count should match gaps list length"

        # Invariant 4: No detected gaps should be in our actual data
        actual_dates_set = set(pd.to_datetime([pd.Timestamp(d).date() for d in sorted_dates]))
        for gap in gaps:
            gap_date = pd.Timestamp(gap.date())
            assert gap_date not in actual_dates_set, f"Gap {gap_date} is in actual data"

    @given(st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=20))
    def test_gap_report_invariants(self, day_offsets):
        """Property test: Gap report generation should satisfy invariants."""
        base_date = pd.Timestamp("2023-01-01")
        missing_days = [base_date + timedelta(days=offset) for offset in sorted(set(day_offsets))]

        if not missing_days:
            return

        report = generate_gap_report(missing_days, threshold=5)

        # Invariant 1: Total gaps should equal input length
        assert report["total_gaps"] == len(missing_days), "Total gaps should match input length"

        # Invariant 2: Sum of gap_ranges counts should equal total_gaps
        total_from_ranges = sum(count for _, _, count in report["gap_ranges"])
        assert total_from_ranges == report["total_gaps"], "Sum of range counts should equal total"

        # Invariant 3: Gap ranges should be non-overlapping and sorted
        for i in range(len(report["gap_ranges"]) - 1):
            start1, end1, _ = report["gap_ranges"][i]
            start2, end2, _ = report["gap_ranges"][i + 1]
            assert end1 < start2, "Gap ranges should be non-overlapping and sorted"

        # Invariant 4: All warnings should be for ranges exceeding threshold
        for warning in report["warnings"]:
            assert "Gap of" in warning, "Warnings should describe gap"

    @given(
        st.lists(
            st.dates(
                min_value=datetime(2020, 1, 1).date(), max_value=datetime(2023, 12, 31).date()
            ),
            min_size=0,
            max_size=30,
        )
    )
    def test_format_parse_roundtrip(self, dates):
        """Property test: Format and parse should be inverse operations."""
        timestamps = [pd.Timestamp(d) for d in dates]

        # Format to JSON
        formatted = format_missing_days_list(timestamps)

        # Parse back
        parsed = parse_missing_days_list(formatted)

        # Should be equal (order-preserved)
        assert len(parsed) == len(timestamps), "Roundtrip should preserve length"

        for original, roundtrip in zip(timestamps, parsed, strict=False):
            # Compare dates (ignore time components)
            assert original.date() == roundtrip.date(), "Roundtrip should preserve dates"
