"""Tests for Layer 4 Broker Transaction Comparator."""

from __future__ import annotations

import pytest
import polars as pl

from rustybt.validation.comparators import ComparisonResult, Layer4BrokerComparator
from rustybt.validation.tolerance import Layer4Tolerances


@pytest.mark.layer_4_broker
class TestLayer4BrokerComparator:
    """Tests for Layer4BrokerComparator class."""

    @pytest.fixture
    def comparator(self) -> Layer4BrokerComparator:
        """Create comparator with default tolerances."""
        return Layer4BrokerComparator()

    def test_layer_name(self, comparator: Layer4BrokerComparator) -> None:
        """Test that layer name is correct."""
        assert comparator.layer_name == "broker"

    def test_transaction_count_match(self, comparator: Layer4BrokerComparator) -> None:
        """Test no discrepancy when transaction counts match."""
        logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "transaction_executed", "asset": "AAPL"},
        ])
        result = comparator.compare(logs, logs)
        assert result.passed

    def test_transaction_count_mismatch(self, comparator: Layer4BrokerComparator) -> None:
        """Test detection of transaction count mismatch."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "transaction_executed", "asset": "AAPL"},
            {"timestamp": "2020-01-15T09:31:00", "layer": "broker", "event": "transaction_executed", "asset": "AAPL"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "transaction_executed", "asset": "AAPL"},
        ])
        discrepancies = comparator.compare_transactions(rb_logs, bt_logs)
        assert any(d.event == "transaction_count_mismatch" for d in discrepancies)

    def test_cash_balance_within_tolerance(self, comparator: Layer4BrokerComparator) -> None:
        """Test cash balance comparison within tolerance."""
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "cash_updated", "data_cash_balance": 100000.00}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "cash_updated", "data_cash_balance": 100000.005}])
        discrepancies = comparator.compare_cash_balance(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "cash_balance_mismatch"]) == 0

    def test_cash_balance_exceeds_tolerance(self) -> None:
        """Test cash balance comparison exceeds tolerance."""
        strict = Layer4Tolerances(cash_decimal_places=4)
        comparator = Layer4BrokerComparator(strict)
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "cash_updated", "data_cash_balance": 100000.00}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "cash_updated", "data_cash_balance": 100001.00}])
        discrepancies = comparator.compare_cash_balance(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "cash_balance_mismatch"]) == 1

    def test_commission_within_tolerance(self, comparator: Layer4BrokerComparator) -> None:
        """Test commission comparison within tolerance."""
        logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "commission_charged", "asset": "AAPL", "data_commission": 9.99}])
        discrepancies = comparator.compare_commissions(logs, logs)
        assert len([d for d in discrepancies if d.event == "commission_mismatch"]) == 0

    def test_commission_exceeds_tolerance(self) -> None:
        """Test commission comparison exceeds tolerance."""
        strict = Layer4Tolerances(commission_decimal_places=4)
        comparator = Layer4BrokerComparator(strict)
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "commission_charged", "asset": "AAPL", "data_commission": 9.99}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "commission_charged", "asset": "AAPL", "data_commission": 10.00}])
        discrepancies = comparator.compare_commissions(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "commission_mismatch"]) == 1

    def test_slippage_within_tolerance(self, comparator: Layer4BrokerComparator) -> None:
        """Test slippage comparison within tolerance."""
        logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "slippage_applied", "asset": "AAPL", "data_slippage": 0.05}])
        discrepancies = comparator.compare_slippage(logs, logs)
        assert len([d for d in discrepancies if d.event == "slippage_mismatch"]) == 0

    def test_slippage_exceeds_tolerance(self) -> None:
        """Test slippage comparison exceeds tolerance."""
        strict = Layer4Tolerances(slippage_tolerance_pct=0.0001)
        comparator = Layer4BrokerComparator(strict)
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "slippage_applied", "asset": "AAPL", "data_slippage": 0.05}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "slippage_applied", "asset": "AAPL", "data_slippage": 0.10}])
        discrepancies = comparator.compare_slippage(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "slippage_mismatch"]) == 1

    def test_compare_returns_comparison_result(self, comparator: Layer4BrokerComparator) -> None:
        """Test compare() returns ComparisonResult."""
        logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "broker", "event": "transaction_executed", "asset": "AAPL"}])
        result = comparator.compare(logs, logs)
        assert isinstance(result, ComparisonResult)
        assert result.layer == "broker"

    def test_empty_logs(self, comparator: Layer4BrokerComparator) -> None:
        """Test handling of empty logs."""
        empty_logs = pl.DataFrame(schema={"timestamp": pl.Utf8, "layer": pl.Utf8, "event": pl.Utf8})
        result = comparator.compare(empty_logs, empty_logs)
        assert result.passed
