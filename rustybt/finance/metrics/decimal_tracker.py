#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Decimal metrics tracker for aggregating performance metrics.

This module provides the DecimalMetricsTracker class for tracking and
calculating performance metrics with Decimal precision over time.
"""

from collections.abc import Callable
from decimal import Decimal

import polars as pl
import structlog

from rustybt.finance.decimal.config import DecimalConfig
from rustybt.finance.metrics.decimal_metrics import (
    calculate_calmar_ratio,
    calculate_cvar,
    calculate_information_ratio,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_tracking_error,
    calculate_var,
    calculate_win_rate,
)
from rustybt.finance.metrics.formatting import create_metrics_summary_table, metrics_to_json

logger = structlog.get_logger(__name__)


class DecimalMetricsTracker:
    """Track and calculate performance metrics with Decimal precision.

    This class maintains a history of returns and calculates a comprehensive
    suite of performance metrics using Decimal arithmetic.

    Example:
        >>> tracker = DecimalMetricsTracker(strategy_name="MyStrategy")
        >>> tracker.update(returns=pl.Series([Decimal("0.01"), Decimal("0.02")]))
        >>> metrics = tracker.calculate_all_metrics()
        >>> summary = tracker.get_metrics_summary()
    """

    def __init__(
        self,
        strategy_name: str = "Strategy",
        risk_free_rate: Decimal = Decimal("0.02"),
        annualization_factor: int = 252,
        config: DecimalConfig | None = None,
    ):
        """Initialize DecimalMetricsTracker.

        Args:
            strategy_name: Name of the strategy being tracked
            risk_free_rate: Annual risk-free rate (default: 2%)
            annualization_factor: Periods per year (252 for daily, 12 for monthly)
            config: DecimalConfig for precision (uses default if None)
        """
        self.strategy_name = strategy_name
        self.risk_free_rate = risk_free_rate
        self.annualization_factor = annualization_factor
        self.config = config or DecimalConfig.get_instance()

        # Returns history
        self._returns: list[Decimal] = []
        self._cumulative_returns: list[Decimal] = [Decimal("1")]  # Start at 1.0

        # Trade history
        self._trade_returns: list[Decimal] = []

        # Benchmark data (optional)
        self._benchmark_returns: list[Decimal] = []

        # Custom metrics registry
        self._custom_metrics: dict[str, Callable[[pl.Series], Decimal]] = {}

        # Cached metrics
        self._metrics_cache: dict[str, Decimal] | None = None
        self._cache_valid = False

    def update(
        self,
        returns: pl.Series,
        trade_returns: pl.Series | None = None,
        benchmark_returns: pl.Series | None = None,
    ) -> None:
        """Update tracker with new returns data.

        Args:
            returns: New returns data as Polars Series
            trade_returns: Optional trade-level returns
            benchmark_returns: Optional benchmark returns for comparison

        Example:
            >>> tracker.update(returns=pl.Series([Decimal("0.01"), Decimal("0.02")]))
        """
        # Append returns
        for ret in returns:
            ret_decimal = Decimal(str(ret))
            self._returns.append(ret_decimal)

            # Update cumulative returns
            last_cumulative = self._cumulative_returns[-1]
            new_cumulative = last_cumulative * (Decimal("1") + ret_decimal)
            self._cumulative_returns.append(new_cumulative)

        # Append trade returns if provided
        if trade_returns is not None:
            for trade_ret in trade_returns:
                self._trade_returns.append(Decimal(str(trade_ret)))

        # Append benchmark returns if provided
        if benchmark_returns is not None:
            for bench_ret in benchmark_returns:
                self._benchmark_returns.append(Decimal(str(bench_ret)))

        # Invalidate cache
        self._cache_valid = False

        logger.debug(
            "metrics_tracker_updated",
            strategy=self.strategy_name,
            total_returns=len(self._returns),
            total_trades=len(self._trade_returns),
        )

    def register_custom_metric(
        self, name: str, metric_func: Callable[[pl.Series], Decimal]
    ) -> None:
        """Register a custom metric calculation function.

        Args:
            name: Name of the metric
            metric_func: Function that takes returns series and returns Decimal

        Example:
            >>> def custom_metric(returns: pl.Series) -> Decimal:
            ...     return Decimal(str(returns.mean())) * Decimal("100")
            >>> tracker.register_custom_metric("mean_x100", custom_metric)
        """
        self._custom_metrics[name] = metric_func
        logger.info("custom_metric_registered", metric_name=name, strategy=self.strategy_name)

    def calculate_all_metrics(self, force_recalculate: bool = False) -> dict[str, Decimal]:
        """Calculate full suite of performance metrics.

        Args:
            force_recalculate: Force recalculation even if cache is valid

        Returns:
            Dictionary mapping metric name to Decimal value

        Example:
            >>> metrics = tracker.calculate_all_metrics()
            >>> print(metrics['sharpe_ratio'])
        """
        if self._cache_valid and not force_recalculate:
            return self._metrics_cache  # type: ignore

        metrics: dict[str, Decimal] = {}

        if len(self._returns) < 2:
            logger.warning("insufficient_data_for_metrics", returns_count=len(self._returns))
            return metrics

        # Create Polars series
        returns_series = pl.Series("returns", self._returns)
        cumulative_series = pl.Series(
            "cumulative", self._cumulative_returns[1:]
        )  # Skip initial 1.0

        # Risk-adjusted return metrics
        try:
            metrics["sharpe_ratio"] = calculate_sharpe_ratio(
                returns_series, self.risk_free_rate, self.annualization_factor, self.config
            )
        except Exception as e:
            logger.warning("sharpe_calculation_failed", error=str(e))
            metrics["sharpe_ratio"] = Decimal("0")

        try:
            metrics["sortino_ratio"] = calculate_sortino_ratio(
                returns_series, self.risk_free_rate, self.annualization_factor, self.config
            )
        except Exception as e:
            logger.warning("sortino_calculation_failed", error=str(e))
            metrics["sortino_ratio"] = Decimal("0")

        # Drawdown metrics
        try:
            metrics["max_drawdown"] = calculate_max_drawdown(cumulative_series)
        except Exception as e:
            logger.warning("max_drawdown_calculation_failed", error=str(e))
            metrics["max_drawdown"] = Decimal("0")

        try:
            metrics["calmar_ratio"] = calculate_calmar_ratio(
                cumulative_series, self.annualization_factor, self.config
            )
        except Exception as e:
            logger.warning("calmar_calculation_failed", error=str(e))
            metrics["calmar_ratio"] = Decimal("0")

        # Risk metrics (VaR, CVaR)
        for confidence_level in [Decimal("0.05"), Decimal("0.01")]:
            confidence_pct = int((Decimal("1") - confidence_level) * Decimal("100"))

            try:
                var_value = calculate_var(returns_series, confidence_level, self.config)
                metrics[f"var_{confidence_pct}"] = var_value
            except Exception as e:
                logger.warning(
                    "var_calculation_failed", confidence_level=str(confidence_level), error=str(e)
                )
                metrics[f"var_{confidence_pct}"] = Decimal("0")

            try:
                cvar_value = calculate_cvar(returns_series, confidence_level, self.config)
                metrics[f"cvar_{confidence_pct}"] = cvar_value
            except Exception as e:
                logger.warning(
                    "cvar_calculation_failed", confidence_level=str(confidence_level), error=str(e)
                )
                metrics[f"cvar_{confidence_pct}"] = Decimal("0")

        # Trade statistics
        if len(self._trade_returns) > 0:
            trade_series = pl.Series("trades", self._trade_returns)

            try:
                metrics["win_rate"] = calculate_win_rate(trade_series)
            except Exception as e:
                logger.warning("win_rate_calculation_failed", error=str(e))
                metrics["win_rate"] = Decimal("0")

            try:
                metrics["profit_factor"] = calculate_profit_factor(trade_series)
            except Exception as e:
                logger.warning("profit_factor_calculation_failed", error=str(e))
                metrics["profit_factor"] = Decimal("0")

        # Benchmark comparison metrics
        if len(self._benchmark_returns) > 0 and len(self._benchmark_returns) == len(self._returns):
            benchmark_series = pl.Series("benchmark", self._benchmark_returns)

            try:
                metrics["information_ratio"] = calculate_information_ratio(
                    returns_series, benchmark_series, self.annualization_factor
                )
            except Exception as e:
                logger.warning("information_ratio_calculation_failed", error=str(e))
                metrics["information_ratio"] = Decimal("0")

            try:
                metrics["tracking_error"] = calculate_tracking_error(
                    returns_series, benchmark_series, self.annualization_factor
                )
            except Exception as e:
                logger.warning("tracking_error_calculation_failed", error=str(e))
                metrics["tracking_error"] = Decimal("0")

        # Basic statistics
        metrics["mean_return"] = Decimal(str(returns_series.mean()))
        metrics["volatility"] = Decimal(str(returns_series.std()))
        metrics["cumulative_return"] = cumulative_series[-1] - Decimal("1")

        # Calculate annualized return
        if len(self._cumulative_returns) > 1:
            total_return = self._cumulative_returns[-1] - Decimal("1")
            num_periods = Decimal(str(len(self._returns)))
            years = num_periods / Decimal(str(self.annualization_factor))
            if years > Decimal("0"):
                metrics["annual_return"] = (Decimal("1") + total_return) ** (
                    Decimal("1") / years
                ) - Decimal("1")
            else:
                metrics["annual_return"] = Decimal("0")
        else:
            metrics["annual_return"] = Decimal("0")

        # Custom metrics
        for name, metric_func in self._custom_metrics.items():
            try:
                metrics[name] = metric_func(returns_series)
            except Exception as e:
                logger.warning("custom_metric_calculation_failed", metric_name=name, error=str(e))
                metrics[name] = Decimal("0")

        # Cache results
        self._metrics_cache = metrics
        self._cache_valid = True

        return metrics

    def get_metrics_summary(self, precision_map: dict[str, int] | None = None) -> str:
        """Get formatted summary of metrics.

        Args:
            precision_map: Optional mapping of metric name to display precision

        Returns:
            Formatted string summary

        Example:
            >>> summary = tracker.get_metrics_summary()
            >>> print(summary)
        """
        metrics = self.calculate_all_metrics()
        return create_metrics_summary_table(metrics, precision_map)

    def get_metrics_json(self) -> str:
        """Get metrics as JSON string.

        Returns:
            JSON string with metrics

        Example:
            >>> json_str = tracker.get_metrics_json()
        """
        metrics = self.calculate_all_metrics()
        return metrics_to_json(metrics)

    def reset(self) -> None:
        """Reset all tracked data.

        Example:
            >>> tracker.reset()
        """
        self._returns.clear()
        self._cumulative_returns = [Decimal("1")]
        self._trade_returns.clear()
        self._benchmark_returns.clear()
        self._metrics_cache = None
        self._cache_valid = False

        logger.info("metrics_tracker_reset", strategy=self.strategy_name)

    def get_returns_series(self) -> pl.Series:
        """Get returns as Polars Series.

        Returns:
            Polars Series with all returns

        Example:
            >>> returns = tracker.get_returns_series()
        """
        return pl.Series("returns", self._returns)

    def get_cumulative_returns_series(self) -> pl.Series:
        """Get cumulative returns as Polars Series.

        Returns:
            Polars Series with cumulative returns

        Example:
            >>> cumulative = tracker.get_cumulative_returns_series()
        """
        return pl.Series("cumulative", self._cumulative_returns[1:])  # Skip initial 1.0
