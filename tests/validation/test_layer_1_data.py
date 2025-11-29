"""Tests for Layer 1 Data Handling Comparator."""

from __future__ import annotations

import pytest
import polars as pl

from rustybt.validation.comparators import (
    ComparisonResult,
    Discrepancy,
    Layer1DataComparator,
)
from rustybt.validation.tolerance import Layer1Tolerances


@pytest.mark.layer_1_data
class TestLayer1DataComparator:
    """Tests for Layer1DataComparator class."""

    @pytest.fixture
    def comparator(self) -> Layer1DataComparator:
        """Create comparator with default tolerances."""
        return Layer1DataComparator()

    @pytest.fixture
    def custom_tolerances(self) -> Layer1Tolerances:
        """Create custom tolerances for testing."""
        return Layer1Tolerances(
            timestamp_window_ms=1,
            price_decimal_places=4,
            volume_tolerance_pct=0.001,
            bar_count_tolerance=0,
        )

    def test_layer_name(self, comparator: Layer1DataComparator) -> None:
        """Test that layer name is correct."""
        assert comparator.layer_name == "data"

    def test_detect_lookahead_bias(self, comparator: Layer1DataComparator) -> None:
        """Test lookahead bias detection catches future data access."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "data_access",
                "data_current_bar_timestamp": "2020-01-15T09:30:00",
                "data_accessed_timestamp": "2020-01-15T09:31:00",  # Future!
            }
        ])

        discrepancies = comparator.detect_lookahead_bias(logs)

        assert len(discrepancies) == 1
        assert discrepancies[0].event == "lookahead_bias"
        assert discrepancies[0].severity == "critical"

    def test_no_lookahead_bias_when_current(
        self, comparator: Layer1DataComparator
    ) -> None:
        """Test no lookahead bias when accessing current data."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "data_access",
                "data_current_bar_timestamp": "2020-01-15T09:30:00",
                "data_accessed_timestamp": "2020-01-15T09:30:00",  # Current
            }
        ])

        discrepancies = comparator.detect_lookahead_bias(logs)
        assert len(discrepancies) == 0

    def test_no_lookahead_bias_when_past(
        self, comparator: Layer1DataComparator
    ) -> None:
        """Test no lookahead bias when accessing past data."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "data_access",
                "data_current_bar_timestamp": "2020-01-15T09:31:00",
                "data_accessed_timestamp": "2020-01-15T09:30:00",  # Past
            }
        ])

        discrepancies = comparator.detect_lookahead_bias(logs)
        assert len(discrepancies) == 0

    def test_bar_count_mismatch(self, comparator: Layer1DataComparator) -> None:
        """Test bar count mismatch detection."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
            {"timestamp": "2020-01-15T09:31:00", "layer": "data", "event": "bar_received"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
        ])

        discrepancies = comparator.compare_bar_alignment(rb_logs, bt_logs)

        assert any(d.event == "bar_count_mismatch" for d in discrepancies)

    def test_bar_count_match(self, comparator: Layer1DataComparator) -> None:
        """Test no discrepancy when bar counts match."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
            {"timestamp": "2020-01-15T09:31:00", "layer": "data", "event": "bar_received"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
            {"timestamp": "2020-01-15T09:31:00", "layer": "data", "event": "bar_received"},
        ])

        discrepancies = comparator.compare_bar_alignment(rb_logs, bt_logs)

        # No bar count mismatch
        assert not any(d.event == "bar_count_mismatch" for d in discrepancies)

    def test_ohlcv_comparison_within_tolerance(
        self, comparator: Layer1DataComparator
    ) -> None:
        """Test OHLCV values match within tolerance."""
        rb_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.12345,
            }
        ])
        bt_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.12349,  # Differs at 5th decimal
            }
        ])

        # Default tolerance is 4 decimal places = 0.0001
        result = comparator.compare(rb_logs, bt_logs)

        # Should pass - difference is beyond tolerance precision
        price_discrepancies = [
            d for d in result.discrepancies if "close" in d.field
        ]
        assert len(price_discrepancies) == 0

    def test_ohlcv_comparison_exceeds_tolerance(
        self, comparator: Layer1DataComparator
    ) -> None:
        """Test OHLCV values exceed tolerance."""
        rb_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.1234,
            }
        ])
        bt_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.1300,  # Differs at 3rd decimal
            }
        ])

        result = comparator.compare(rb_logs, bt_logs)

        # Should fail - difference exceeds 4 decimal place tolerance
        price_discrepancies = [
            d for d in result.discrepancies if "close" in d.field
        ]
        assert len(price_discrepancies) == 1

    def test_no_discrepancies_matching_data(
        self, comparator: Layer1DataComparator
    ) -> None:
        """Test no discrepancies when data matches exactly."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.1234,
                "data_volume": 1000,
            }
        ])

        result = comparator.compare(logs, logs)

        assert result.passed
        assert len(result.discrepancies) == 0

    def test_missing_bar_detection(self, comparator: Layer1DataComparator) -> None:
        """Test detection of missing bars in Backtrader logs."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
            {"timestamp": "2020-01-15T09:31:00", "layer": "data", "event": "bar_received"},
            {"timestamp": "2020-01-15T09:32:00", "layer": "data", "event": "bar_received"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
            # Missing 09:31:00
            {"timestamp": "2020-01-15T09:32:00", "layer": "data", "event": "bar_received"},
        ])

        discrepancies = comparator.compare_bar_alignment(rb_logs, bt_logs)

        assert any(d.event == "missing_bar" for d in discrepancies)

    def test_ohlcv_anomaly_high_lt_low(
        self, comparator: Layer1DataComparator
    ) -> None:
        """Test detection of OHLCV anomaly: high < low."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_high": 99.0,  # High < Low is invalid
                "data_low": 100.0,
                "data_open": 99.5,
                "data_close": 99.5,
            }
        ])

        discrepancies = comparator.validate_data_integrity(logs, "test")

        assert any(d.event == "ohlcv_anomaly" for d in discrepancies)
        assert any(d.severity == "critical" for d in discrepancies)

    def test_compare_returns_comparison_result(
        self, comparator: Layer1DataComparator
    ) -> None:
        """Test compare() returns ComparisonResult."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
            }
        ])

        result = comparator.compare(logs, logs)

        assert isinstance(result, ComparisonResult)
        assert result.layer == "data"
        assert isinstance(result.stats, dict)

    def test_comparison_result_stats(
        self, comparator: Layer1DataComparator
    ) -> None:
        """Test ComparisonResult includes statistics."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
            {"timestamp": "2020-01-15T09:31:00", "layer": "data", "event": "bar_received"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
        ])

        result = comparator.compare(rb_logs, bt_logs)

        assert result.stats["rustybt_bar_count"] == 2
        assert result.stats["backtrader_bar_count"] == 1

    def test_custom_tolerances(self, custom_tolerances: Layer1Tolerances) -> None:
        """Test comparator with custom tolerances."""
        comparator = Layer1DataComparator(custom_tolerances)

        rb_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.1234,
            }
        ])
        bt_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.1234,
            }
        ])

        result = comparator.compare(rb_logs, bt_logs)
        assert result.passed

    def test_empty_logs(self, comparator: Layer1DataComparator) -> None:
        """Test handling of empty logs."""
        empty_logs = pl.DataFrame(
            schema={
                "timestamp": pl.Utf8,
                "layer": pl.Utf8,
                "event": pl.Utf8,
            }
        )

        result = comparator.compare(empty_logs, empty_logs)

        assert result.passed
        assert len(result.discrepancies) == 0


@pytest.mark.layer_1_data
class TestDiscrepancy:
    """Tests for Discrepancy dataclass."""

    def test_discrepancy_auto_description(self) -> None:
        """Test that description is auto-generated if not provided."""
        discrepancy = Discrepancy(
            layer="data",
            event="test",
            timestamp="2020-01-15T09:30:00",
            field="close",
            rustybt_value=100.0,
            backtrader_value=101.0,
            tolerance=0.01,
            exceeded_by=1.0,
        )

        assert "data/test" in discrepancy.description
        assert "close" in discrepancy.description

    def test_discrepancy_custom_description(self) -> None:
        """Test that custom description is preserved."""
        discrepancy = Discrepancy(
            layer="data",
            event="test",
            timestamp="2020-01-15T09:30:00",
            field="close",
            rustybt_value=100.0,
            backtrader_value=101.0,
            tolerance=0.01,
            exceeded_by=1.0,
            description="Custom description",
        )

        assert discrepancy.description == "Custom description"

    def test_discrepancy_default_severity(self) -> None:
        """Test default severity is warning."""
        discrepancy = Discrepancy(
            layer="data",
            event="test",
            timestamp=None,
            field="test",
            rustybt_value=1,
            backtrader_value=2,
            tolerance=0,
            exceeded_by=1,
        )

        assert discrepancy.severity == "warning"


@pytest.mark.layer_1_data
class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""

    def test_critical_count(self) -> None:
        """Test critical_count property."""
        result = ComparisonResult(
            layer="data",
            passed=False,
            discrepancies=[
                Discrepancy("data", "e1", None, "f1", 1, 2, 0, 1, severity="critical"),
                Discrepancy("data", "e2", None, "f2", 1, 2, 0, 1, severity="warning"),
                Discrepancy("data", "e3", None, "f3", 1, 2, 0, 1, severity="critical"),
            ],
        )

        assert result.critical_count == 2

    def test_warning_count(self) -> None:
        """Test warning_count property."""
        result = ComparisonResult(
            layer="data",
            passed=True,
            discrepancies=[
                Discrepancy("data", "e1", None, "f1", 1, 2, 0, 1, severity="warning"),
                Discrepancy("data", "e2", None, "f2", 1, 2, 0, 1, severity="warning"),
                Discrepancy("data", "e3", None, "f3", 1, 2, 0, 1, severity="info"),
            ],
        )

        assert result.warning_count == 2
