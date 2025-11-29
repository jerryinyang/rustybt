"""Tests for Layer 3 Order Lifecycle Comparator."""

from __future__ import annotations

import pytest
import polars as pl

from rustybt.validation.comparators import ComparisonResult, Layer3OrdersComparator
from rustybt.validation.tolerance import Layer3Tolerances


@pytest.mark.layer_3_orders
class TestLayer3OrdersComparator:
    """Tests for Layer3OrdersComparator class."""

    @pytest.fixture
    def comparator(self) -> Layer3OrdersComparator:
        """Create comparator with default tolerances."""
        return Layer3OrdersComparator()

    def test_layer_name(self, comparator: Layer3OrdersComparator) -> None:
        """Test that layer name is correct."""
        assert comparator.layer_name == "orders"

    def test_order_count_match(self, comparator: Layer3OrdersComparator) -> None:
        """Test no discrepancy when order counts match."""
        logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 100, "data_order_type": "market"},
        ])
        result = comparator.compare(logs, logs)
        assert result.passed
        assert len([d for d in result.discrepancies if "order" in d.event]) == 0

    def test_order_count_mismatch(self, comparator: Layer3OrdersComparator) -> None:
        """Test detection of order count mismatch."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 100},
            {"timestamp": "2020-01-15T09:31:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 50},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 100},
        ])
        discrepancies = comparator.compare_order_creation(rb_logs, bt_logs)
        assert any(d.event == "order_count_mismatch" for d in discrepancies)

    def test_order_type_mismatch(self, comparator: Layer3OrdersComparator) -> None:
        """Test detection of order type mismatch."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 100, "data_order_type": "market"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 100, "data_order_type": "limit"},
        ])
        discrepancies = comparator.compare_order_creation(rb_logs, bt_logs)
        assert any(d.event == "order_type_mismatch" for d in discrepancies)

    def test_fill_price_within_tolerance(self, comparator: Layer3OrdersComparator) -> None:
        """Test fill price comparison within tolerance."""
        # Default tolerance is 4 decimal places (0.0001), so diff must be <= 0.0001
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_filled", "asset": "AAPL", "data_fill_price": 150.12340}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_filled", "asset": "AAPL", "data_fill_price": 150.12345}])
        discrepancies = comparator.compare_order_execution(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "fill_price_mismatch"]) == 0

    def test_fill_price_exceeds_tolerance(self) -> None:
        """Test fill price comparison exceeds tolerance."""
        strict = Layer3Tolerances(fill_price_decimal_places=6)
        comparator = Layer3OrdersComparator(strict)
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_filled", "asset": "AAPL", "data_fill_price": 150.123456}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_filled", "asset": "AAPL", "data_fill_price": 150.123500}])
        discrepancies = comparator.compare_order_execution(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "fill_price_mismatch"]) == 1

    def test_state_transition_match(self, comparator: Layer3OrdersComparator) -> None:
        """Test correct state transition sequence."""
        logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "CREATED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "SUBMITTED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "FILLED"},
        ])
        discrepancies = comparator.compare_order_states(logs, logs)
        assert len(discrepancies) == 0

    def test_state_transition_mismatch(self, comparator: Layer3OrdersComparator) -> None:
        """Test state transition mismatch detection."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "CREATED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "SUBMITTED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "FILLED"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "CREATED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "FILLED"},
        ])
        discrepancies = comparator.compare_order_states(rb_logs, bt_logs)
        assert any(d.event == "state_transition_mismatch" for d in discrepancies)

    def test_partial_fill_handling(self, comparator: Layer3OrdersComparator) -> None:
        """Test partial fill state sequence."""
        logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "CREATED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "PARTIALLY_FILLED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "FILLED"},
        ])
        discrepancies = comparator.compare_order_states(logs, logs)
        assert len(discrepancies) == 0

    def test_compare_returns_comparison_result(self, comparator: Layer3OrdersComparator) -> None:
        """Test compare() returns ComparisonResult."""
        logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 100}])
        result = comparator.compare(logs, logs)
        assert isinstance(result, ComparisonResult)
        assert result.layer == "orders"

    def test_empty_logs(self, comparator: Layer3OrdersComparator) -> None:
        """Test handling of empty logs."""
        empty_logs = pl.DataFrame(schema={"timestamp": pl.Utf8, "layer": pl.Utf8, "event": pl.Utf8})
        result = comparator.compare(empty_logs, empty_logs)
        assert result.passed
