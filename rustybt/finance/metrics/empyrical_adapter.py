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
"""Adapter for empyrical-reloaded integration.

This module provides conversion between Decimal metrics and empyrical's
float-based metrics, with precision loss warnings.
"""

from decimal import Decimal

import numpy as np
import polars as pl
import structlog

logger = structlog.get_logger(__name__)


def to_float_series(decimal_series: pl.Series, warn_precision_loss: bool = True) -> np.ndarray:
    """Convert Polars Decimal series to NumPy float array for empyrical.

    Args:
        decimal_series: Polars Series with Decimal values
        warn_precision_loss: Whether to log warning about precision loss

    Returns:
        NumPy array with float64 values

    Example:
        >>> decimal_series = pl.Series([Decimal("0.01"), Decimal("0.02")])
        >>> float_array = to_float_series(decimal_series)
    """
    if warn_precision_loss:
        logger.warning(
            "precision_loss_conversion",
            message="Converting Decimal to float for empyrical - precision may be lost",
            series_length=len(decimal_series),
        )

    # Convert to float array
    float_values = [float(Decimal(str(val))) for val in decimal_series]
    return np.array(float_values, dtype=np.float64)


def from_float_value(float_value: float) -> Decimal:
    """Convert float result from empyrical back to Decimal.

    Args:
        float_value: Float value from empyrical calculation

    Returns:
        Decimal representation (with precision limitations)

    Example:
        >>> float_result = 0.123456789
        >>> decimal_result = from_float_value(float_result)
    """
    # Convert through string to maintain precision
    # Limit to 15 significant digits (float64 precision limit)
    return Decimal(str(round(float_value, 15)))


def compare_metrics(
    decimal_value: Decimal,
    empyrical_value: float,
    metric_name: str,
    tolerance: Decimal = Decimal("1e-10"),
) -> bool:
    """Compare Decimal metric with empyrical float metric.

    Args:
        decimal_value: Metric calculated with Decimal
        empyrical_value: Metric calculated with empyrical (float)
        metric_name: Name of metric for logging
        tolerance: Maximum acceptable difference

    Returns:
        True if values match within tolerance

    Example:
        >>> decimal_sharpe = Decimal("1.567")
        >>> float_sharpe = 1.567
        >>> match = compare_metrics(decimal_sharpe, float_sharpe, "sharpe_ratio")
    """
    empyrical_decimal = from_float_value(empyrical_value)
    difference = abs(decimal_value - empyrical_decimal)

    if difference > tolerance:
        logger.warning(
            "metric_mismatch",
            metric=metric_name,
            decimal_value=str(decimal_value),
            empyrical_value=str(empyrical_decimal),
            difference=str(difference),
        )
        return False

    logger.debug(
        "metric_comparison_success",
        metric=metric_name,
        decimal_value=str(decimal_value),
        empyrical_value=str(empyrical_decimal),
        difference=str(difference),
    )
    return True


def validate_decimal_against_empyrical(
    returns: pl.Series,
    decimal_metrics: dict,
    empyrical_metrics: dict,
    tolerance: Decimal = Decimal("1e-8"),
) -> dict:
    """Validate Decimal metrics against empyrical calculations.

    Args:
        returns: Returns series (Decimal)
        decimal_metrics: Metrics calculated with Decimal
        empyrical_metrics: Metrics calculated with empyrical
        tolerance: Maximum acceptable difference

    Returns:
        Dictionary with validation results for each metric

    Example:
        >>> validation = validate_decimal_against_empyrical(
        ...     returns, decimal_metrics, empyrical_metrics
        ... )
    """
    validation_results = {}

    for metric_name in decimal_metrics:
        if metric_name in empyrical_metrics:
            decimal_value = decimal_metrics[metric_name]
            empyrical_value = empyrical_metrics[metric_name]

            matches = compare_metrics(decimal_value, empyrical_value, metric_name, tolerance)

            validation_results[metric_name] = {
                "matches": matches,
                "decimal_value": str(decimal_value),
                "empyrical_value": str(from_float_value(empyrical_value)),
                "difference": str(abs(decimal_value - from_float_value(empyrical_value))),
            }
        else:
            validation_results[metric_name] = {
                "matches": None,
                "decimal_value": str(decimal_metrics[metric_name]),
                "empyrical_value": "N/A",
                "difference": "N/A",
            }

    return validation_results


class EmpyricalAdapter:
    """Adapter for using empyrical with Decimal metrics.

    This class provides methods to use empyrical's advanced metrics
    while maintaining Decimal precision where possible.

    Example:
        >>> adapter = EmpyricalAdapter()
        >>> returns_decimal = pl.Series([Decimal("0.01"), Decimal("0.02")])
        >>> sharpe = adapter.sharpe_ratio(returns_decimal)
    """

    def __init__(self, warn_on_conversion: bool = True):
        """Initialize EmpyricalAdapter.

        Args:
            warn_on_conversion: Whether to warn on Decimal -> float conversion
        """
        self.warn_on_conversion = warn_on_conversion

        try:
            import empyrical as ep

            self.ep = ep
        except ImportError:
            logger.error(
                "empyrical_not_installed",
                message="empyrical-reloaded not installed. Install with: pip install empyrical-reloaded",
            )
            raise

    def sharpe_ratio(
        self,
        returns: pl.Series,
        risk_free: float = 0.0,
        period: str = "daily",
        annualization: int | None = None,
    ) -> Decimal:
        """Calculate Sharpe ratio using empyrical.

        Args:
            returns: Returns series (Decimal)
            risk_free: Risk-free rate
            period: Period ('daily', 'weekly', 'monthly', 'yearly')
            annualization: Optional custom annualization factor

        Returns:
            Sharpe ratio as Decimal

        Example:
            >>> returns = pl.Series([Decimal("0.01"), Decimal("0.02")])
            >>> sharpe = adapter.sharpe_ratio(returns)
        """
        float_returns = to_float_series(returns, self.warn_on_conversion)
        sharpe = self.ep.sharpe_ratio(float_returns, risk_free, period, annualization)
        return from_float_value(sharpe)

    def sortino_ratio(
        self,
        returns: pl.Series,
        required_return: float = 0.0,
        period: str = "daily",
        annualization: int | None = None,
    ) -> Decimal:
        """Calculate Sortino ratio using empyrical.

        Args:
            returns: Returns series (Decimal)
            required_return: Required return threshold
            period: Period ('daily', 'weekly', 'monthly', 'yearly')
            annualization: Optional custom annualization factor

        Returns:
            Sortino ratio as Decimal
        """
        float_returns = to_float_series(returns, self.warn_on_conversion)
        sortino = self.ep.sortino_ratio(float_returns, required_return, period, annualization)
        return from_float_value(sortino)

    def max_drawdown(self, returns: pl.Series) -> Decimal:
        """Calculate maximum drawdown using empyrical.

        Args:
            returns: Returns series (Decimal)

        Returns:
            Maximum drawdown as Decimal
        """
        float_returns = to_float_series(returns, self.warn_on_conversion)
        max_dd = self.ep.max_drawdown(float_returns)
        return from_float_value(max_dd)

    def calmar_ratio(self, returns: pl.Series, period: str = "daily") -> Decimal:
        """Calculate Calmar ratio using empyrical.

        Args:
            returns: Returns series (Decimal)
            period: Period ('daily', 'weekly', 'monthly', 'yearly')

        Returns:
            Calmar ratio as Decimal
        """
        float_returns = to_float_series(returns, self.warn_on_conversion)
        calmar = self.ep.calmar_ratio(float_returns, period)
        return from_float_value(calmar)

    def omega_ratio(
        self, returns: pl.Series, risk_free: float = 0.0, required_return: float = 0.0
    ) -> Decimal:
        """Calculate Omega ratio using empyrical.

        Args:
            returns: Returns series (Decimal)
            risk_free: Risk-free rate
            required_return: Required return threshold

        Returns:
            Omega ratio as Decimal
        """
        float_returns = to_float_series(returns, self.warn_on_conversion)
        omega = self.ep.omega_ratio(float_returns, risk_free, required_return)
        return from_float_value(omega)

    def tail_ratio(self, returns: pl.Series) -> Decimal:
        """Calculate tail ratio using empyrical.

        Args:
            returns: Returns series (Decimal)

        Returns:
            Tail ratio as Decimal
        """
        float_returns = to_float_series(returns, self.warn_on_conversion)
        tail = self.ep.tail_ratio(float_returns)
        return from_float_value(tail)
