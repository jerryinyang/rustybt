"""Tests for Layer 2 Signal Computation Comparator."""

from __future__ import annotations

import pytest
import polars as pl

from rustybt.validation.comparators import (
    ComparisonResult,
    Layer2SignalComparator,
)
from rustybt.validation.tolerance import Layer2Tolerances


@pytest.mark.layer_2_signals
class TestLayer2SignalComparator:
    """Tests for Layer2SignalComparator class."""

    @pytest.fixture
    def comparator(self) -> Layer2SignalComparator:
        """Create comparator with default tolerances."""
        return Layer2SignalComparator()

    @pytest.fixture
    def strict_tolerances(self) -> Layer2Tolerances:
        """Create strict tolerances for testing."""
        return Layer2Tolerances(
            indicator_decimal_places=6,
            signal_tolerance_pct=0.0001,
            signal_exact_match=True,
            signal_timestamp_window_ms=0,
        )

    def test_layer_name(self, comparator: Layer2SignalComparator) -> None:
        """Test that layer name is correct."""
        assert comparator.layer_name == "signals"

    def test_signal_count_match(self, comparator: Layer2SignalComparator) -> None:
        """Test no discrepancy when signal counts match."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "sell_signal"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "sell_signal"},
        ])

        discrepancies = comparator.compare_signal_counts(rb_logs, bt_logs)

        assert len(discrepancies) == 0

    def test_signal_count_mismatch_buy(
        self, comparator: Layer2SignalComparator
    ) -> None:
        """Test detection of buy signal count mismatch."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "buy_signal"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
        ])

        discrepancies = comparator.compare_signal_counts(rb_logs, bt_logs)

        assert len(discrepancies) == 1
        assert discrepancies[0].field == "buy_signal_count"

    def test_signal_count_mismatch_sell(
        self, comparator: Layer2SignalComparator
    ) -> None:
        """Test detection of sell signal count mismatch."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "sell_signal"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "sell_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "sell_signal"},
        ])

        discrepancies = comparator.compare_signal_counts(rb_logs, bt_logs)

        assert len(discrepancies) == 1
        assert discrepancies[0].field == "sell_signal_count"

    def test_indicator_values_within_tolerance(
        self, comparator: Layer2SignalComparator
    ) -> None:
        """Test indicator values match within tolerance."""
        rb_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "signals",
                "event": "indicator_computed",
                "data_sma": 100.12345,
            }
        ])
        bt_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "signals",
                "event": "indicator_computed",
                "data_sma": 100.12349,  # Within 4 decimal tolerance
            }
        ])

        discrepancies = comparator.compare_indicator_values(rb_logs, bt_logs)

        assert len(discrepancies) == 0

    def test_indicator_values_exceed_tolerance(
        self, strict_tolerances: Layer2Tolerances
    ) -> None:
        """Test indicator values exceed tolerance."""
        comparator = Layer2SignalComparator(strict_tolerances)

        rb_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "signals",
                "event": "indicator_computed",
                "data_sma": 100.123456,
            }
        ])
        bt_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "signals",
                "event": "indicator_computed",
                "data_sma": 100.123500,  # Exceeds 6 decimal tolerance
            }
        ])

        discrepancies = comparator.compare_indicator_values(rb_logs, bt_logs)

        assert len(discrepancies) == 1
        assert discrepancies[0].field == "data_sma"

    def test_signal_timing_match(self, comparator: Layer2SignalComparator) -> None:
        """Test signal timing matches."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "sell_signal"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "sell_signal"},
        ])

        discrepancies = comparator.compare_signal_timing(rb_logs, bt_logs)

        assert len(discrepancies) == 0

    def test_signal_timing_mismatch(
        self, comparator: Layer2SignalComparator
    ) -> None:
        """Test signal timing mismatch detection."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:31:00", "layer": "signals", "event": "buy_signal"},
        ])

        discrepancies = comparator.compare_signal_timing(rb_logs, bt_logs)

        assert len(discrepancies) == 1
        assert discrepancies[0].event == "signal_timing_mismatch"

    def test_compare_returns_comparison_result(
        self, comparator: Layer2SignalComparator
    ) -> None:
        """Test compare() returns ComparisonResult."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "signals",
                "event": "buy_signal",
            }
        ])

        result = comparator.compare(logs, logs)

        assert isinstance(result, ComparisonResult)
        assert result.layer == "signals"

    def test_no_discrepancies_matching_signals(
        self, comparator: Layer2SignalComparator
    ) -> None:
        """Test no discrepancies when signals match exactly."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "signals",
                "event": "buy_signal",
                "data_sma": 100.0,
            },
            {
                "timestamp": "2020-01-15T09:35:00",
                "layer": "signals",
                "event": "sell_signal",
                "data_sma": 99.0,
            },
        ])

        result = comparator.compare(logs, logs)

        assert result.passed
        assert len(result.discrepancies) == 0

    def test_empty_logs(self, comparator: Layer2SignalComparator) -> None:
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

    def test_signal_exact_match_true(
        self, strict_tolerances: Layer2Tolerances
    ) -> None:
        """Test that signal_exact_match=True makes count mismatch critical."""
        comparator = Layer2SignalComparator(strict_tolerances)

        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "buy_signal"},
        ])

        discrepancies = comparator.compare_signal_counts(rb_logs, bt_logs)

        assert len(discrepancies) == 1
        assert discrepancies[0].severity == "critical"

    def test_signal_exact_match_false(self) -> None:
        """Test that signal_exact_match=False makes count mismatch warning."""
        tolerances = Layer2Tolerances(signal_exact_match=False)
        comparator = Layer2SignalComparator(tolerances)

        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "buy_signal"},
        ])

        discrepancies = comparator.compare_signal_counts(rb_logs, bt_logs)

        assert len(discrepancies) == 1
        assert discrepancies[0].severity == "warning"

    def test_comparison_result_stats(
        self, comparator: Layer2SignalComparator
    ) -> None:
        """Test ComparisonResult includes statistics."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
            {"timestamp": "2020-01-15T09:35:00", "layer": "signals", "event": "sell_signal"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "signals", "event": "buy_signal"},
        ])

        result = comparator.compare(rb_logs, bt_logs)

        assert "rustybt_signal_count" in result.stats
        assert "backtrader_signal_count" in result.stats
        assert result.stats["rustybt_signal_count"] == 2
        assert result.stats["backtrader_signal_count"] == 1

    def test_multiple_indicator_fields(
        self, comparator: Layer2SignalComparator
    ) -> None:
        """Test comparison of multiple indicator fields."""
        rb_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "signals",
                "event": "indicator_computed",
                "data_sma": 100.0,
                "data_ema": 99.5,
                "data_rsi": 50.0,
            }
        ])
        bt_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "signals",
                "event": "indicator_computed",
                "data_sma": 100.0,
                "data_ema": 99.5,
                "data_rsi": 50.0,
            }
        ])

        discrepancies = comparator.compare_indicator_values(rb_logs, bt_logs)

        assert len(discrepancies) == 0
