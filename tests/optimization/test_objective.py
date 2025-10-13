"""Tests for objective function."""

from decimal import Decimal

import pytest

from rustybt.optimization.objective import ObjectiveFunction


class TestObjectiveFunction:
    """Tests for ObjectiveFunction."""

    def test_standard_metric_sharpe_ratio(self):
        """Test objective function with standard Sharpe ratio metric."""
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        backtest_result = {
            "performance_metrics": {
                "sharpe_ratio": 1.5,
                "sortino_ratio": 2.0,
                "total_return": 0.25,
            }
        }

        score = obj_func.evaluate(backtest_result)

        assert score == Decimal("1.5")
        assert isinstance(score, Decimal)

    def test_standard_metric_total_return(self):
        """Test objective function with total return metric."""
        obj_func = ObjectiveFunction(metric="total_return")

        backtest_result = {
            "performance_metrics": {
                "sharpe_ratio": 1.5,
                "total_return": 0.42,
            }
        }

        score = obj_func.evaluate(backtest_result)

        assert score == Decimal("0.42")

    def test_custom_metric_function(self):
        """Test objective function with custom metric function."""

        def custom_metric(backtest_result):
            """Calculate custom metric: return / max_drawdown."""
            metrics = backtest_result["performance_metrics"]
            total_return = Decimal(str(metrics["total_return"]))
            max_dd = Decimal(str(metrics["max_drawdown"]))
            return total_return / max_dd

        obj_func = ObjectiveFunction(metric="custom", custom_function=custom_metric)

        backtest_result = {
            "performance_metrics": {
                "total_return": 0.50,
                "max_drawdown": 0.10,
            }
        }

        score = obj_func.evaluate(backtest_result)

        assert score == Decimal("5.0")

    def test_custom_metric_requires_function(self):
        """Test custom metric without function raises error."""
        with pytest.raises(ValueError) as exc_info:
            ObjectiveFunction(metric="custom")

        assert "custom_function required" in str(exc_info.value)

    def test_standard_metric_with_custom_function_raises(self):
        """Test standard metric with custom function raises error."""

        def dummy_func(result):
            return Decimal("1.0")

        with pytest.raises(ValueError) as exc_info:
            ObjectiveFunction(metric="sharpe_ratio", custom_function=dummy_func)

        assert "only valid when metric='custom'" in str(exc_info.value)

    def test_missing_metric_in_results(self):
        """Test evaluation with missing metric raises KeyError."""
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        backtest_result = {
            "performance_metrics": {
                "total_return": 0.25,
                # Missing sharpe_ratio
            }
        }

        with pytest.raises(KeyError) as exc_info:
            obj_func.evaluate(backtest_result)

        assert "sharpe_ratio" in str(exc_info.value)

    def test_higher_is_better_true(self):
        """Test higher_is_better=True doesn't invert score."""
        obj_func = ObjectiveFunction(metric="sharpe_ratio", higher_is_better=True)

        backtest_result = {"performance_metrics": {"sharpe_ratio": 2.5}}

        score = obj_func.evaluate(backtest_result)

        assert score == Decimal("2.5")

    def test_higher_is_better_false(self):
        """Test higher_is_better=False inverts score."""
        obj_func = ObjectiveFunction(metric="max_drawdown", higher_is_better=False)

        backtest_result = {"performance_metrics": {"max_drawdown": 0.15}}

        score = obj_func.evaluate(backtest_result)

        # Should be inverted
        assert score == Decimal("-0.15")

    def test_repr(self):
        """Test string representation."""
        obj_func = ObjectiveFunction(metric="sharpe_ratio", higher_is_better=True)

        repr_str = repr(obj_func)

        assert "sharpe_ratio" in repr_str
        assert "higher_is_better=True" in repr_str

    def test_decimal_precision_maintained(self):
        """Test Decimal precision is maintained throughout calculation."""
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        # Use high-precision value
        backtest_result = {
            "performance_metrics": {"sharpe_ratio": "1.23456789012345678901234567890"}
        }

        score = obj_func.evaluate(backtest_result)

        assert isinstance(score, Decimal)
        # Decimal should preserve precision
        assert str(score) == "1.23456789012345678901234567890"
