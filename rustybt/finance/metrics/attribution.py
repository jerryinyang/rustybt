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
"""Performance attribution with Decimal precision.

This module implements performance attribution analysis to decompose
portfolio returns into contributions from individual positions.
"""

from decimal import Decimal

import polars as pl
import structlog

from rustybt.finance.metrics.decimal_metrics import InsufficientDataError, InvalidMetricError

logger = structlog.get_logger(__name__)


def calculate_position_attribution(
    position_values: pl.DataFrame,
    position_returns: pl.DataFrame,
    portfolio_value: Decimal,
) -> dict[str, Decimal]:
    """Calculate attribution of returns to individual positions.

    Args:
        position_values: DataFrame with columns ['asset', 'value'] as Decimal
        position_returns: DataFrame with columns ['asset', 'return'] as Decimal
        portfolio_value: Total portfolio value as Decimal

    Returns:
        Dictionary mapping asset symbol to attribution (Decimal)

    Raises:
        InvalidMetricError: If attribution doesn't sum to portfolio return

    Formula:
        attribution(asset) = (position_value / portfolio_value) × position_return

    Example:
        >>> position_values = pl.DataFrame({
        ...     'asset': ['AAPL', 'GOOGL'],
        ...     'value': [Decimal('50000'), Decimal('50000')]
        ... })
        >>> position_returns = pl.DataFrame({
        ...     'asset': ['AAPL', 'GOOGL'],
        ...     'return': [Decimal('0.05'), Decimal('-0.02')]
        ... })
        >>> attr = calculate_position_attribution(position_values, position_returns, Decimal('100000'))
    """
    if portfolio_value == Decimal("0"):
        raise InvalidMetricError("Portfolio value cannot be zero")

    # Join position values and returns
    attribution_df = position_values.join(position_returns, on="asset", how="inner")

    # Calculate attribution for each position
    attributions: dict[str, Decimal] = {}

    for row in attribution_df.iter_rows(named=True):
        asset = row["asset"]
        value = Decimal(str(row["value"]))
        ret = Decimal(str(row["return"]))

        # Attribution = weight × return
        weight = value / portfolio_value
        attribution = weight * ret

        attributions[asset] = attribution

    # Validate that attribution sums to total portfolio return
    total_attribution = sum(attributions.values(), Decimal("0"))
    total_return = sum(
        (Decimal(str(row["value"])) / portfolio_value) * Decimal(str(row["return"]))
        for row in attribution_df.iter_rows(named=True)
    )

    # Allow small rounding errors (1e-10)
    if abs(total_attribution - total_return) > Decimal("1e-10"):
        logger.warning(
            "attribution_sum_mismatch",
            total_attribution=str(total_attribution),
            expected=str(total_return),
        )

    return attributions


def calculate_sector_attribution(
    position_values: pl.DataFrame,
    position_returns: pl.DataFrame,
    position_sectors: dict[str, str],
    portfolio_value: Decimal,
) -> dict[str, Decimal]:
    """Calculate attribution grouped by sector.

    Args:
        position_values: DataFrame with columns ['asset', 'value'] as Decimal
        position_returns: DataFrame with columns ['asset', 'return'] as Decimal
        position_sectors: Mapping of asset symbol to sector name
        portfolio_value: Total portfolio value as Decimal

    Returns:
        Dictionary mapping sector to attribution (Decimal)

    Example:
        >>> sectors = {'AAPL': 'Technology', 'GOOGL': 'Technology', 'JPM': 'Finance'}
        >>> attr = calculate_sector_attribution(values, returns, sectors, portfolio_value)
    """
    # Get position-level attribution
    position_attr = calculate_position_attribution(
        position_values, position_returns, portfolio_value
    )

    # Aggregate by sector
    sector_attr: dict[str, Decimal] = {}

    for asset, attribution in position_attr.items():
        sector = position_sectors.get(asset, "Unknown")

        if sector not in sector_attr:
            sector_attr[sector] = Decimal("0")

        sector_attr[sector] += attribution

    return sector_attr


def calculate_alpha_beta(
    strategy_returns: pl.Series,
    benchmark_returns: pl.Series,
    risk_free_rate: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    """Calculate alpha and beta relative to benchmark.

    Args:
        strategy_returns: Strategy returns as Polars Series with Decimal values
        benchmark_returns: Benchmark returns as Polars Series with Decimal values
        risk_free_rate: Risk-free rate (default: 0)

    Returns:
        Tuple of (alpha, beta) as Decimal

    Raises:
        InsufficientDataError: If insufficient data
        InvalidMetricError: If benchmark variance is zero

    Formula:
        beta = cov(strategy, benchmark) / var(benchmark)
        alpha = mean(strategy) - risk_free_rate - beta × (mean(benchmark) - risk_free_rate)

    Example:
        >>> strategy = pl.Series("returns", [Decimal("0.02"), Decimal("0.01"), ...])
        >>> benchmark = pl.Series("returns", [Decimal("0.015"), Decimal("0.005"), ...])
        >>> alpha, beta = calculate_alpha_beta(strategy, benchmark)
    """
    if len(strategy_returns) < 2 or len(benchmark_returns) < 2:
        raise InsufficientDataError("Need at least 2 returns for alpha/beta calculation")

    if len(strategy_returns) != len(benchmark_returns):
        raise InvalidMetricError(
            f"Strategy and benchmark must have same length: "
            f"{len(strategy_returns)} vs {len(benchmark_returns)}"
        )

    # Calculate means
    strategy_mean = Decimal(str(strategy_returns.mean()))
    benchmark_mean = Decimal(str(benchmark_returns.mean()))

    # Calculate covariance and variance using Polars
    # cov(X, Y) = E[(X - E[X])(Y - E[Y])]
    strategy_demean = strategy_returns - strategy_mean
    benchmark_demean = benchmark_returns - benchmark_mean

    covariance = Decimal(str((strategy_demean * benchmark_demean).mean()))
    benchmark_variance = Decimal(str((benchmark_demean * benchmark_demean).mean()))

    if benchmark_variance == Decimal("0"):
        raise InvalidMetricError("Benchmark variance is zero, cannot calculate beta")

    # Calculate beta
    beta = covariance / benchmark_variance

    # Calculate alpha (CAPM formula)
    alpha = strategy_mean - risk_free_rate - beta * (benchmark_mean - risk_free_rate)

    return alpha, beta


def calculate_time_period_attribution(
    returns_series: pl.Series,
    dates: pl.Series,
    period: str = "monthly",
) -> pl.DataFrame:
    """Calculate attribution breakdown by time period.

    Args:
        returns_series: Returns as Polars Series with Decimal values
        dates: Dates as Polars Series (datetime type)
        period: Time period for aggregation ('daily', 'monthly', 'annual')

    Returns:
        DataFrame with columns ['period', 'return', 'cumulative_return']

    Example:
        >>> returns = pl.Series("returns", [Decimal("0.01"), Decimal("0.02"), ...])
        >>> dates = pl.Series("date", [date(2024, 1, 1), date(2024, 1, 2), ...])
        >>> attr = calculate_time_period_attribution(returns, dates, period='monthly')
    """
    # Create DataFrame
    df = pl.DataFrame({"date": dates, "return": returns_series})

    # Add period column based on aggregation
    if period == "monthly":
        df = df.with_columns(pl.col("date").dt.strftime("%Y-%m").alias("period"))
    elif period == "annual":
        df = df.with_columns(pl.col("date").dt.year().alias("period"))
    elif period == "daily":
        df = df.with_columns(pl.col("date").dt.strftime("%Y-%m-%d").alias("period"))
    else:
        raise ValueError(f"Unknown period: {period}. Use 'daily', 'monthly', or 'annual'.")

    # Group by period and calculate aggregate return
    # For returns: (1 + r1) × (1 + r2) - 1
    period_returns = (
        df.group_by("period")
        .agg(
            [
                # Calculate compound return: prod(1 + r) - 1
                ((pl.col("return") + Decimal("1")).product() - Decimal("1")).alias("return"),
                pl.col("return").count().alias("num_periods"),
            ]
        )
        .sort("period")
    )

    # Calculate cumulative return
    period_returns = period_returns.with_columns(
        ((pl.col("return") + Decimal("1")).cum_prod() - Decimal("1")).alias("cumulative_return")
    )

    return period_returns
