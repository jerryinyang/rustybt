"""Objective function for extracting metrics from backtest results."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any, Literal

ObjectiveMetric = Literal[
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "total_return",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "custom",
]


class ObjectiveFunction:
    """Extract objective metric from backtest results."""

    def __init__(
        self,
        metric: ObjectiveMetric,
        custom_function: Callable[[dict[str, Any]], Decimal] | None = None,
        higher_is_better: bool = True,
    ):
        """Initialize objective function.

        Args:
            metric: Standard metric name or "custom"
            custom_function: Custom metric extraction function (required if metric="custom")
            higher_is_better: Whether higher scores are better (for optimization direction)

        Raises:
            ValueError: If configuration is invalid
        """
        self.metric = metric
        self.custom_function = custom_function
        self.higher_is_better = higher_is_better

        if metric == "custom" and custom_function is None:
            raise ValueError("custom_function required when metric='custom'")

        if metric != "custom" and custom_function is not None:
            raise ValueError("custom_function only valid when metric='custom'")

    def evaluate(self, backtest_result: dict[str, Any]) -> Decimal:
        """Extract objective metric from backtest result.

        Args:
            backtest_result: Dictionary containing backtest performance metrics

        Returns:
            Objective score as Decimal (higher is better if higher_is_better=True)

        Raises:
            KeyError: If required metric not in backtest results
            ValueError: If metric calculation fails
        """
        if self.metric == "custom":
            # Custom function receives full backtest result
            score = self.custom_function(backtest_result)
            if not isinstance(score, Decimal):
                score = Decimal(str(score))
        else:
            # Extract standard metric from backtest results
            metrics = backtest_result.get("performance_metrics", {})
            if self.metric not in metrics:
                raise KeyError(f"Metric '{self.metric}' not in backtest results")

            metric_value = metrics[self.metric]
            score = Decimal(str(metric_value))

        # Invert score if lower is better
        if not self.higher_is_better:
            score = -score

        return score

    def __repr__(self) -> str:
        """String representation."""
        return f"ObjectiveFunction(metric={self.metric}, higher_is_better={self.higher_is_better})"
