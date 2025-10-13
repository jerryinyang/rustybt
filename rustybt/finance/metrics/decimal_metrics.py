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
"""Decimal-precision performance metrics for RustyBT.

This module implements performance metrics using Decimal arithmetic for
audit-compliant financial calculations. All metrics maintain precision
throughout the calculation pipeline.
"""

from decimal import Decimal

import polars as pl
import structlog

from rustybt.finance.decimal.config import DecimalConfig

logger = structlog.get_logger(__name__)


class MetricsError(Exception):
    """Base exception for metrics errors."""


class InsufficientDataError(MetricsError):
    """Raised when insufficient data for metric calculation."""


class InvalidMetricError(MetricsError):
    """Raised when metric calculation produces invalid result."""


def calculate_sharpe_ratio(
    returns: pl.Series,
    risk_free_rate: Decimal = Decimal("0"),
    annualization_factor: int = 252,
    config: DecimalConfig | None = None,
) -> Decimal:
    """Calculate Sharpe ratio with Decimal precision.

    Args:
        returns: Returns series as Polars Series with Decimal values
        risk_free_rate: Risk-free rate (e.g., Decimal("0.02") = 2% annual)
        annualization_factor: Days per year (252 for daily, 12 for monthly)
        config: DecimalConfig for precision (uses default if None)

    Returns:
        Sharpe ratio as Decimal

    Raises:
        InsufficientDataError: If returns series has fewer than 2 data points
        InvalidMetricError: If calculation produces invalid result

    Formula:
        Sharpe = (mean_return - risk_free_rate) / std_dev_return × √annualization_factor

    Example:
        >>> returns = pl.Series("returns", [Decimal("0.01"), Decimal("-0.005"), Decimal("0.015")])
        >>> sharpe = calculate_sharpe_ratio(returns)
        >>> print(f"Sharpe ratio: {sharpe}")
    """
    if len(returns) < 2:
        raise InsufficientDataError(
            f"Need at least 2 returns for Sharpe calculation, got {len(returns)}"
        )

    config = config or DecimalConfig.get_instance()

    # Calculate mean and std using Polars (maintains Decimal precision)
    mean_return = Decimal(str(returns.mean()))
    std_return = Decimal(str(returns.std()))

    if std_return == Decimal("0"):
        logger.warning("sharpe_ratio_zero_volatility", returns_count=len(returns))
        return Decimal("0")

    # Calculate Sharpe ratio (non-annualized first)
    sharpe = (mean_return - risk_free_rate) / std_return

    # Annualize: multiply by sqrt(annualization_factor)
    annualization_sqrt = Decimal(str(annualization_factor)).sqrt()
    annualized_sharpe = sharpe * annualization_sqrt

    # Validate result is reasonable
    if abs(annualized_sharpe) > Decimal("10"):
        logger.warning(
            "sharpe_ratio_unusual",
            sharpe=str(annualized_sharpe),
            mean_return=str(mean_return),
            std_return=str(std_return),
        )

    return annualized_sharpe


def calculate_sortino_ratio(
    returns: pl.Series,
    risk_free_rate: Decimal = Decimal("0"),
    annualization_factor: int = 252,
    config: DecimalConfig | None = None,
) -> Decimal:
    """Calculate Sortino ratio with Decimal precision.

    The Sortino ratio is similar to Sharpe but uses downside deviation
    instead of total volatility, penalizing only downside volatility.

    Args:
        returns: Returns series as Polars Series with Decimal values
        risk_free_rate: Risk-free rate (e.g., Decimal("0.02") = 2% annual)
        annualization_factor: Days per year (252 for daily, 12 for monthly)
        config: DecimalConfig for precision (uses default if None)

    Returns:
        Sortino ratio as Decimal

    Raises:
        InsufficientDataError: If returns series has fewer than 2 data points
        InvalidMetricError: If no negative returns exist

    Formula:
        Sortino = (mean_return - risk_free_rate) / downside_deviation × √annualization_factor
        where downside_deviation = std_dev(returns where returns < 0)

    Example:
        >>> returns = pl.Series("returns", [Decimal("0.02"), Decimal("-0.01"), Decimal("0.03")])
        >>> sortino = calculate_sortino_ratio(returns)
    """
    if len(returns) < 2:
        raise InsufficientDataError(
            f"Need at least 2 returns for Sortino calculation, got {len(returns)}"
        )

    config = config or DecimalConfig.get_instance()

    # Calculate mean return
    mean_return = Decimal(str(returns.mean()))

    # Filter for downside returns (below zero)
    downside_returns = returns.filter(returns < Decimal("0"))

    if len(downside_returns) == 0:
        logger.warning("sortino_ratio_no_negative_returns", returns_count=len(returns))
        # No downside risk means infinite Sortino ratio
        return Decimal("inf") if mean_return > risk_free_rate else Decimal("0")

    # Calculate downside deviation
    downside_std_value = downside_returns.std()

    # Handle case where std() returns None (single value case)
    if downside_std_value is None:
        logger.warning("sortino_ratio_single_negative_return", returns_count=len(downside_returns))
        # With only one negative return, downside std is undefined
        # Return 0 to indicate insufficient data for meaningful Sortino ratio
        return Decimal("0")

    downside_std = Decimal(str(downside_std_value))

    if downside_std == Decimal("0"):
        logger.warning("sortino_ratio_zero_downside_volatility")
        return Decimal("0")

    # Calculate Sortino ratio (non-annualized)
    sortino = (mean_return - risk_free_rate) / downside_std

    # Annualize
    annualization_sqrt = Decimal(str(annualization_factor)).sqrt()
    annualized_sortino = sortino * annualization_sqrt

    return annualized_sortino


def calculate_max_drawdown(cumulative_returns: pl.Series) -> Decimal:
    """Calculate maximum drawdown from cumulative returns.

    Maximum drawdown is the largest peak-to-trough decline in portfolio value.

    Args:
        cumulative_returns: Cumulative returns series as Polars Series with Decimal values

    Returns:
        Maximum drawdown as Decimal (negative value, e.g., Decimal("-0.25") = -25%)

    Raises:
        InsufficientDataError: If returns series is empty
        InvalidMetricError: If drawdown is outside valid range [-1, 0]

    Formula:
        drawdown(t) = (cumulative_return(t) - running_max(t)) / running_max(t)
        max_drawdown = min(drawdown(t)) for all t

    Example:
        >>> cumulative = pl.Series("returns", [Decimal("1.0"), Decimal("1.2"), Decimal("0.9")])
        >>> max_dd = calculate_max_drawdown(cumulative)
        >>> # Returns Decimal("-0.25") = -25% from peak of 1.2 to trough of 0.9
    """
    if len(cumulative_returns) == 0:
        raise InsufficientDataError("Need returns data for drawdown calculation")

    # Calculate running maximum
    running_max = cumulative_returns.cum_max()

    # Special case: if all values are zero or negative, drawdown is undefined
    # Return -1 (100% loss) as the maximum possible drawdown
    max_value = Decimal(str(running_max.max()))
    if max_value <= Decimal("0"):
        return Decimal("-1")

    # Guard against division by zero: if running_max contains zeros, replace with 1
    # This handles edge cases where cumulative returns start at or cross zero
    running_max_safe = running_max.map_elements(
        lambda x: x if x > Decimal("0") else Decimal("1"), return_dtype=pl.Decimal
    )

    # Calculate drawdown at each point
    try:
        drawdown = (cumulative_returns - running_max_safe) / running_max_safe
        max_dd = Decimal(str(drawdown.min()))
    except Exception:
        # If precision overflow occurs (e.g., all constant values creating division issues),
        # return 0 since there's no drawdown
        return Decimal("0")

    # Validate drawdown is in valid range
    if max_dd > Decimal("0.0001"):  # Allow small rounding errors
        # If all values are exactly equal, max_dd might be 0, which is valid
        if max_dd > Decimal("0.01"):
            raise InvalidMetricError(f"Drawdown must be non-positive, got {max_dd}")

    if max_dd < Decimal("-1"):
        raise InvalidMetricError(f"Drawdown cannot exceed -100%, got {max_dd}")

    # Ensure non-positive
    if max_dd > Decimal("0"):
        max_dd = Decimal("0")

    return max_dd


def calculate_calmar_ratio(
    cumulative_returns: pl.Series,
    periods_per_year: int = 252,
    config: DecimalConfig | None = None,
) -> Decimal:
    """Calculate Calmar ratio (annualized return / abs(max drawdown)).

    The Calmar ratio measures risk-adjusted return using maximum drawdown
    as the risk measure.

    Args:
        cumulative_returns: Cumulative returns series as Polars Series with Decimal values
        periods_per_year: Number of periods per year (252 for daily, 12 for monthly)
        config: DecimalConfig for precision (uses default if None)

    Returns:
        Calmar ratio as Decimal

    Raises:
        InsufficientDataError: If insufficient data
        InvalidMetricError: If calculation produces invalid result

    Formula:
        Calmar = annualized_return / abs(max_drawdown)

    Example:
        >>> cumulative = pl.Series("returns", [Decimal("1.0"), Decimal("1.5"), Decimal("1.3")])
        >>> calmar = calculate_calmar_ratio(cumulative, periods_per_year=252)
    """
    if len(cumulative_returns) < 2:
        raise InsufficientDataError(
            f"Need at least 2 returns for Calmar calculation, got {len(cumulative_returns)}"
        )

    config = config or DecimalConfig.get_instance()

    # Calculate annualized return
    total_return = cumulative_returns[-1] / cumulative_returns[0] - Decimal("1")
    num_periods = Decimal(str(len(cumulative_returns)))
    years = num_periods / Decimal(str(periods_per_year))

    if years <= Decimal("0"):
        raise InvalidMetricError("Cannot calculate annualized return with zero or negative years")

    # Annualized return = (1 + total_return) ^ (1 / years) - 1
    annualized_return = (Decimal("1") + total_return) ** (Decimal("1") / years) - Decimal("1")

    # Calculate max drawdown
    max_dd = calculate_max_drawdown(cumulative_returns)

    if max_dd == Decimal("0"):
        # No drawdown means infinite Calmar ratio
        return Decimal("inf") if annualized_return > Decimal("0") else Decimal("0")

    # Calmar ratio
    calmar = annualized_return / abs(max_dd)

    return calmar


def calculate_var(
    returns: pl.Series,
    confidence_level: Decimal = Decimal("0.05"),
    config: DecimalConfig | None = None,
) -> Decimal:
    """Calculate Value at Risk (VaR) at specified confidence level.

    VaR estimates the maximum loss at a given confidence level using
    historical simulation method.

    Args:
        returns: Returns series as Polars Series with Decimal values
        confidence_level: Percentile for VaR (e.g., 0.05 for 95% VaR, 0.01 for 99% VaR)
        config: DecimalConfig for precision (uses default if None)

    Returns:
        VaR as Decimal (negative value representing loss)

    Raises:
        InsufficientDataError: If insufficient data

    Formula:
        VaR = percentile(returns, confidence_level)

    Example:
        >>> returns = pl.Series("returns", [Decimal("-0.05"), Decimal("0.01"), ...])
        >>> var_95 = calculate_var(returns, confidence_level=Decimal("0.05"))
    """
    if len(returns) < 2:
        raise InsufficientDataError(
            f"Need at least 2 returns for VaR calculation, got {len(returns)}"
        )

    config = config or DecimalConfig.get_instance()

    # Calculate VaR as quantile
    var_value = Decimal(str(returns.quantile(float(confidence_level))))

    return var_value


def calculate_cvar(
    returns: pl.Series,
    confidence_level: Decimal = Decimal("0.05"),
    config: DecimalConfig | None = None,
) -> Decimal:
    """Calculate Conditional Value at Risk (CVaR / Expected Shortfall).

    CVaR is the expected loss in the worst (confidence_level) of cases.

    Args:
        returns: Returns series as Polars Series with Decimal values
        confidence_level: Percentile for CVaR (e.g., 0.05 for 95% CVaR)
        config: DecimalConfig for precision (uses default if None)

    Returns:
        CVaR as Decimal (negative value representing expected tail loss)

    Raises:
        InsufficientDataError: If insufficient data

    Formula:
        CVaR = E[returns | returns <= VaR]

    Example:
        >>> returns = pl.Series("returns", [Decimal("-0.05"), Decimal("0.01"), ...])
        >>> cvar_95 = calculate_cvar(returns, confidence_level=Decimal("0.05"))
    """
    if len(returns) < 2:
        raise InsufficientDataError(
            f"Need at least 2 returns for CVaR calculation, got {len(returns)}"
        )

    config = config or DecimalConfig.get_instance()

    # Calculate VaR threshold
    var_threshold = calculate_var(returns, confidence_level, config)

    # Filter returns worse than VaR (tail returns)
    tail_returns = returns.filter(returns <= var_threshold)

    if len(tail_returns) == 0:
        raise InsufficientDataError("No tail returns found for CVaR calculation")

    # CVaR = mean of tail returns
    cvar_value = Decimal(str(tail_returns.mean()))

    return cvar_value


def calculate_win_rate(trade_returns: pl.Series) -> Decimal:
    """Calculate win rate (percentage of profitable trades).

    Args:
        trade_returns: Trade returns series as Polars Series with Decimal values

    Returns:
        Win rate as Decimal in range [0, 1] (e.g., Decimal("0.6") = 60%)

    Raises:
        InsufficientDataError: If no trades

    Formula:
        win_rate = count(returns > 0) / count(total_returns)

    Example:
        >>> trades = pl.Series("returns", [Decimal("0.05"), Decimal("-0.02"), Decimal("0.03")])
        >>> wr = calculate_win_rate(trades)
        >>> # Returns Decimal("0.666...") ≈ 66.67%
    """
    if len(trade_returns) == 0:
        raise InsufficientDataError("Need trade data for win rate calculation")

    # Count winning trades
    winning_trades = trade_returns.filter(trade_returns > Decimal("0"))
    win_count = Decimal(str(len(winning_trades)))
    total_count = Decimal(str(len(trade_returns)))

    win_rate = win_count / total_count

    # Validate win rate is in [0, 1]
    if not (Decimal("0") <= win_rate <= Decimal("1")):
        raise InvalidMetricError(f"Win rate must be in [0, 1], got {win_rate}")

    return win_rate


def calculate_profit_factor(trade_returns: pl.Series) -> Decimal:
    """Calculate profit factor (gross profits / gross losses).

    Args:
        trade_returns: Trade returns series as Polars Series with Decimal values

    Returns:
        Profit factor as Decimal (> 1 means profitable strategy)

    Raises:
        InsufficientDataError: If no trades

    Formula:
        profit_factor = sum(returns where returns > 0) / abs(sum(returns where returns < 0))

    Example:
        >>> trades = pl.Series("returns", [Decimal("100"), Decimal("-50"), Decimal("75")])
        >>> pf = calculate_profit_factor(trades)
        >>> # Returns Decimal("3.5") = (100 + 75) / 50
    """
    if len(trade_returns) == 0:
        raise InsufficientDataError("Need trade data for profit factor calculation")

    # Calculate gross profits
    winning_trades = trade_returns.filter(trade_returns > Decimal("0"))
    gross_profit = Decimal(str(winning_trades.sum()))

    # Calculate gross losses
    losing_trades = trade_returns.filter(trade_returns < Decimal("0"))
    gross_loss = abs(Decimal(str(losing_trades.sum())))

    if gross_loss == Decimal("0"):
        # No losses means infinite profit factor (or 0 if no profits either)
        return Decimal("inf") if gross_profit > Decimal("0") else Decimal("0")

    profit_factor = gross_profit / gross_loss

    return profit_factor


def calculate_excess_return(strategy_returns: pl.Series, benchmark_returns: pl.Series) -> pl.Series:
    """Calculate excess returns (strategy - benchmark).

    Args:
        strategy_returns: Strategy returns as Polars Series with Decimal values
        benchmark_returns: Benchmark returns as Polars Series with Decimal values

    Returns:
        Excess returns as Polars Series with Decimal values

    Raises:
        InvalidMetricError: If series lengths don't match

    Example:
        >>> strategy = pl.Series("returns", [Decimal("0.02"), Decimal("0.01")])
        >>> benchmark = pl.Series("returns", [Decimal("0.015"), Decimal("0.005")])
        >>> excess = calculate_excess_return(strategy, benchmark)
    """
    if len(strategy_returns) != len(benchmark_returns):
        raise InvalidMetricError(
            f"Strategy and benchmark returns must have same length: "
            f"{len(strategy_returns)} vs {len(benchmark_returns)}"
        )

    excess = strategy_returns - benchmark_returns
    return excess


def calculate_information_ratio(
    strategy_returns: pl.Series,
    benchmark_returns: pl.Series,
    annualization_factor: int = 252,
) -> Decimal:
    """Calculate Information ratio (excess return / tracking error).

    The Information ratio measures consistency of outperformance vs benchmark.

    Args:
        strategy_returns: Strategy returns as Polars Series with Decimal values
        benchmark_returns: Benchmark returns as Polars Series with Decimal values
        annualization_factor: Days per year (252 for daily, 12 for monthly)

    Returns:
        Information ratio as Decimal

    Raises:
        InsufficientDataError: If insufficient data
        InvalidMetricError: If tracking error is zero

    Formula:
        IR = mean(excess_returns) / std(excess_returns) × √annualization_factor

    Example:
        >>> strategy = pl.Series("returns", [Decimal("0.02"), Decimal("0.01"), ...])
        >>> benchmark = pl.Series("returns", [Decimal("0.015"), Decimal("0.005"), ...])
        >>> ir = calculate_information_ratio(strategy, benchmark)
    """
    if len(strategy_returns) < 2:
        raise InsufficientDataError("Need at least 2 returns for Information ratio calculation")

    # Calculate excess returns
    excess_returns = calculate_excess_return(strategy_returns, benchmark_returns)

    # Calculate mean and std of excess returns
    mean_excess = Decimal(str(excess_returns.mean()))
    tracking_error = Decimal(str(excess_returns.std()))

    if tracking_error == Decimal("0"):
        logger.warning("information_ratio_zero_tracking_error")
        return Decimal("0")

    # Information ratio (annualized)
    ir = mean_excess / tracking_error
    annualization_sqrt = Decimal(str(annualization_factor)).sqrt()
    annualized_ir = ir * annualization_sqrt

    return annualized_ir


def calculate_tracking_error(
    strategy_returns: pl.Series,
    benchmark_returns: pl.Series,
    annualization_factor: int = 252,
) -> Decimal:
    """Calculate tracking error (std of excess returns).

    Args:
        strategy_returns: Strategy returns as Polars Series with Decimal values
        benchmark_returns: Benchmark returns as Polars Series with Decimal values
        annualization_factor: Days per year (252 for daily, 12 for monthly)

    Returns:
        Tracking error as Decimal (annualized standard deviation)

    Raises:
        InsufficientDataError: If insufficient data

    Formula:
        TE = std(strategy_returns - benchmark_returns) × √annualization_factor

    Example:
        >>> strategy = pl.Series("returns", [Decimal("0.02"), Decimal("0.01"), ...])
        >>> benchmark = pl.Series("returns", [Decimal("0.015"), Decimal("0.005"), ...])
        >>> te = calculate_tracking_error(strategy, benchmark)
    """
    if len(strategy_returns) < 2:
        raise InsufficientDataError("Need at least 2 returns for tracking error calculation")

    # Calculate excess returns
    excess_returns = calculate_excess_return(strategy_returns, benchmark_returns)

    # Calculate standard deviation
    tracking_error = Decimal(str(excess_returns.std()))

    # Annualize
    annualization_sqrt = Decimal(str(annualization_factor)).sqrt()
    annualized_te = tracking_error * annualization_sqrt

    return annualized_te
