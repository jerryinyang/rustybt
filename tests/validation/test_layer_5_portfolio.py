"""Tests for Layer 5 Portfolio Returns Comparator."""

from __future__ import annotations

import pytest
import polars as pl

from rustybt.validation.comparators import ComparisonResult, Layer5PortfolioComparator
from rustybt.validation.tolerance import Layer5Tolerances


@pytest.mark.layer_5_portfolio
class TestLayer5PortfolioComparator:
    """Tests for Layer5PortfolioComparator class."""

    @pytest.fixture
    def comparator(self) -> Layer5PortfolioComparator:
        """Create comparator with default tolerances."""
        return Layer5PortfolioComparator()

    def test_layer_name(self, comparator: Layer5PortfolioComparator) -> None:
        """Test that layer name is correct."""
        assert comparator.layer_name == "portfolio"

    def test_portfolio_value_match(self, comparator: Layer5PortfolioComparator) -> None:
        """Test no discrepancy when portfolio values match."""
        logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "portfolio_value_updated", "data_portfolio_value": 100000.00},
        ])
        discrepancies = comparator.compare_portfolio_values(logs, logs)
        assert len(discrepancies) == 0

    def test_portfolio_value_within_tolerance(self, comparator: Layer5PortfolioComparator) -> None:
        """Test portfolio value comparison within tolerance."""
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "portfolio_value_updated", "data_portfolio_value": 100000.00}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "portfolio_value_updated", "data_portfolio_value": 100000.005}])
        discrepancies = comparator.compare_portfolio_values(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "portfolio_value_mismatch"]) == 0

    def test_portfolio_value_exceeds_tolerance(self) -> None:
        """Test portfolio value comparison exceeds tolerance."""
        strict = Layer5Tolerances(portfolio_value_decimal_places=4)
        comparator = Layer5PortfolioComparator(strict)
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "portfolio_value_updated", "data_portfolio_value": 100000.00}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "portfolio_value_updated", "data_portfolio_value": 100001.00}])
        discrepancies = comparator.compare_portfolio_values(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "portfolio_value_mismatch"]) == 1

    def test_returns_within_tolerance(self, comparator: Layer5PortfolioComparator) -> None:
        """Test returns comparison within tolerance."""
        logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "daily_return_calculated", "data_daily_return": 0.0125}])
        discrepancies = comparator.compare_returns(logs, logs)
        assert len([d for d in discrepancies if d.event == "return_mismatch"]) == 0

    def test_returns_exceeds_tolerance(self) -> None:
        """Test returns comparison exceeds tolerance."""
        strict = Layer5Tolerances(returns_tolerance_pct=0.0001)
        comparator = Layer5PortfolioComparator(strict)
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "daily_return_calculated", "data_daily_return": 0.0125}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "daily_return_calculated", "data_daily_return": 0.0150}])
        discrepancies = comparator.compare_returns(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "return_mismatch"]) == 1

    def test_sharpe_ratio_match(self, comparator: Layer5PortfolioComparator) -> None:
        """Test Sharpe ratio comparison match."""
        logs = pl.DataFrame([{"timestamp": "2020-01-15T16:00:00", "layer": "portfolio", "event": "final_metrics", "data_sharpe_ratio": 1.5}])
        discrepancies = comparator.compare_sharpe_ratio(logs, logs)
        assert len(discrepancies) == 0

    def test_sharpe_ratio_mismatch(self) -> None:
        """Test Sharpe ratio comparison mismatch."""
        strict = Layer5Tolerances(sharpe_decimal_places=6)
        comparator = Layer5PortfolioComparator(strict)
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T16:00:00", "layer": "portfolio", "event": "final_metrics", "data_sharpe_ratio": 1.500000}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T16:00:00", "layer": "portfolio", "event": "final_metrics", "data_sharpe_ratio": 1.500100}])
        discrepancies = comparator.compare_sharpe_ratio(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "sharpe_ratio_mismatch"]) == 1

    def test_drawdown_within_tolerance(self, comparator: Layer5PortfolioComparator) -> None:
        """Test drawdown comparison within tolerance."""
        logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "drawdown_updated", "data_drawdown": 0.05}])
        discrepancies = comparator.compare_drawdowns(logs, logs)
        assert len([d for d in discrepancies if d.event == "drawdown_mismatch"]) == 0

    def test_drawdown_exceeds_tolerance(self) -> None:
        """Test drawdown comparison exceeds tolerance."""
        strict = Layer5Tolerances(drawdown_tolerance_pct=0.0001)
        comparator = Layer5PortfolioComparator(strict)
        rb_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "drawdown_updated", "data_drawdown": 0.05}])
        bt_logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "drawdown_updated", "data_drawdown": 0.10}])
        discrepancies = comparator.compare_drawdowns(rb_logs, bt_logs)
        assert len([d for d in discrepancies if d.event == "drawdown_mismatch"]) == 1

    def test_compare_returns_comparison_result(self, comparator: Layer5PortfolioComparator) -> None:
        """Test compare() returns ComparisonResult."""
        logs = pl.DataFrame([{"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "portfolio_value_updated", "data_portfolio_value": 100000}])
        result = comparator.compare(logs, logs)
        assert isinstance(result, ComparisonResult)
        assert result.layer == "portfolio"

    def test_empty_logs(self, comparator: Layer5PortfolioComparator) -> None:
        """Test handling of empty logs."""
        empty_logs = pl.DataFrame(schema={"timestamp": pl.Utf8, "layer": pl.Utf8, "event": pl.Utf8})
        result = comparator.compare(empty_logs, empty_logs)
        assert result.passed

    def test_full_comparison_pass(self, comparator: Layer5PortfolioComparator) -> None:
        """Test full comparison passes with matching logs."""
        logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "portfolio_value_updated", "data_portfolio_value": 100000},
            {"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "daily_return_calculated", "data_daily_return": 0.01},
            {"timestamp": "2020-01-15T09:30:00", "layer": "portfolio", "event": "drawdown_updated", "data_drawdown": 0.02},
            {"timestamp": "2020-01-15T16:00:00", "layer": "portfolio", "event": "final_metrics", "data_sharpe_ratio": 1.5},
        ])
        result = comparator.compare(logs, logs)
        assert result.passed
        assert len(result.discrepancies) == 0
