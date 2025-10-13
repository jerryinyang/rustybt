"""Per-module benchmarks for Decimal metrics calculations.

Measures performance overhead of Decimal-based metrics compared to float-based
metrics (empyrical-reloaded).

Run with: pytest benchmarks/decimal_metrics_benchmark.py --benchmark-only
"""

import random
from decimal import Decimal

import polars as pl
import pytest


class DecimalMetrics:
    """Decimal-based metrics calculator."""

    @staticmethod
    def sharpe_ratio(returns: pl.Series, risk_free_rate: Decimal = Decimal("0")) -> Decimal:
        """Calculate Sharpe ratio with Decimal precision."""
        if len(returns) < 2:
            return Decimal("0")

        excess_returns = returns.map_elements(
            lambda x: x - risk_free_rate if x is not None else Decimal("0"),
            return_dtype=pl.Decimal(scale=8),
        )

        mean_return = excess_returns.mean()
        std_return = excess_returns.std()

        if mean_return is None or std_return is None or std_return == 0:
            return Decimal("0")

        return Decimal(str(mean_return)) / Decimal(str(std_return))

    @staticmethod
    def max_drawdown(cumulative_returns: pl.Series) -> Decimal:
        """Calculate maximum drawdown with Decimal precision."""
        running_max = cumulative_returns.cum_max()
        drawdown = cumulative_returns - running_max

        normalized_drawdown = drawdown / running_max.map_elements(
            lambda x: x if x != 0 else Decimal("1"), return_dtype=pl.Decimal(scale=8)
        )

        min_dd = normalized_drawdown.min()
        return Decimal(str(min_dd)) if min_dd is not None else Decimal("0")

    @staticmethod
    def sortino_ratio(returns: pl.Series, risk_free_rate: Decimal = Decimal("0")) -> Decimal:
        """Calculate Sortino ratio (downside deviation only)."""
        if len(returns) < 2:
            return Decimal("0")

        excess_returns = returns.map_elements(
            lambda x: x - risk_free_rate if x is not None else Decimal("0"),
            return_dtype=pl.Decimal(scale=8),
        )

        mean_return = excess_returns.mean()

        # Downside deviation (only negative returns)
        downside_returns = excess_returns.filter(excess_returns < 0)
        if len(downside_returns) == 0:
            return Decimal("0")

        downside_std = downside_returns.std()

        if mean_return is None or downside_std is None or downside_std == 0:
            return Decimal("0")

        return Decimal(str(mean_return)) / Decimal(str(downside_std))

    @staticmethod
    def cumulative_return(returns: pl.Series) -> Decimal:
        """Calculate cumulative return from series."""
        if len(returns) == 0:
            return Decimal("0")

        # Manual cumulative product
        cumulative = Decimal("1")
        for ret in returns:
            cumulative *= Decimal("1") + ret

        return cumulative - Decimal("1")


@pytest.fixture
def returns_252() -> pl.Series:
    """Generate 252 daily returns (1 year)."""
    random.seed(42)
    returns = [Decimal(str(random.gauss(0.0005, 0.015))) for _ in range(252)]
    return pl.Series("returns", returns, dtype=pl.Decimal(scale=8))


@pytest.fixture
def returns_1260() -> pl.Series:
    """Generate 1260 daily returns (5 years)."""
    random.seed(42)
    returns = [Decimal(str(random.gauss(0.0005, 0.015))) for _ in range(1260)]
    return pl.Series("returns", returns, dtype=pl.Decimal(scale=8))


@pytest.mark.benchmark(group="metrics-sharpe")
def test_sharpe_ratio_252_returns(benchmark, returns_252):
    """Benchmark Sharpe ratio calculation with 252 returns (1 year).

    Expected: ~300-600 microseconds
    Target (Epic 7): <150 microseconds
    """
    result = benchmark(DecimalMetrics.sharpe_ratio, returns_252)

    assert isinstance(result, Decimal)
    assert Decimal("-5") < result < Decimal("5")


@pytest.mark.benchmark(group="metrics-sharpe")
def test_sharpe_ratio_1260_returns(benchmark, returns_1260):
    """Benchmark Sharpe ratio calculation with 1260 returns (5 years).

    Tests scalability with larger datasets.
    Expected: ~1-3 milliseconds
    Target (Epic 7): <500 microseconds
    """
    result = benchmark(DecimalMetrics.sharpe_ratio, returns_1260)

    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="metrics-drawdown")
def test_max_drawdown_252_returns(benchmark, returns_252):
    """Benchmark maximum drawdown calculation with 252 returns.

    Expected: ~500-1000 microseconds
    Target (Epic 7): <250 microseconds
    """
    # Generate cumulative returns
    price_factors = returns_252.map_elements(
        lambda x: Decimal("1") + x, return_dtype=pl.Decimal(scale=8)
    )

    cumulative = Decimal("1")
    cumulative_list = []
    for factor in price_factors:
        cumulative = cumulative * factor
        cumulative_list.append(cumulative)

    cumulative_returns = pl.Series("cumulative", cumulative_list, dtype=pl.Decimal(scale=8))

    result = benchmark(DecimalMetrics.max_drawdown, cumulative_returns)

    assert isinstance(result, Decimal)
    assert result <= Decimal("0")


@pytest.mark.benchmark(group="metrics-sortino")
def test_sortino_ratio_252_returns(benchmark, returns_252):
    """Benchmark Sortino ratio calculation with 252 returns.

    Expected: ~400-800 microseconds
    Target (Epic 7): <200 microseconds
    """
    result = benchmark(DecimalMetrics.sortino_ratio, returns_252)

    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="metrics-cumulative")
def test_cumulative_return_252(benchmark, returns_252):
    """Benchmark cumulative return calculation.

    Expected: ~100-300 microseconds for 252 returns
    Target (Epic 7): <50 microseconds
    """
    result = benchmark(DecimalMetrics.cumulative_return, returns_252)

    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="metrics-batch")
def test_all_metrics_252_returns(benchmark, returns_252):
    """Benchmark calculating all metrics together.

    Simulates real-world usage where multiple metrics are calculated.
    Expected: ~2-5 milliseconds for all metrics
    Target (Epic 7): <1 millisecond
    """

    def calculate_all_metrics():
        # Generate cumulative returns for drawdown
        price_factors = returns_252.map_elements(
            lambda x: Decimal("1") + x, return_dtype=pl.Decimal(scale=8)
        )

        cumulative = Decimal("1")
        cumulative_list = []
        for factor in price_factors:
            cumulative = cumulative * factor
            cumulative_list.append(cumulative)

        cumulative_returns = pl.Series("cumulative", cumulative_list, dtype=pl.Decimal(scale=8))

        return {
            "sharpe": DecimalMetrics.sharpe_ratio(returns_252),
            "sortino": DecimalMetrics.sortino_ratio(returns_252),
            "max_drawdown": DecimalMetrics.max_drawdown(cumulative_returns),
            "cumulative_return": DecimalMetrics.cumulative_return(returns_252),
        }

    result = benchmark(calculate_all_metrics)

    assert len(result) == 4
    assert all(isinstance(v, Decimal) for v in result.values())


@pytest.mark.benchmark(group="metrics-returns-series")
@pytest.mark.parametrize("num_returns", [100, 252, 500, 1000, 2520])
def test_sharpe_scalability(benchmark, num_returns):
    """Test Sharpe ratio calculation scales with return series length.

    Expected: Linear O(n) scaling
    Target: Maintain linear performance characteristic
    """
    random.seed(42)
    returns = [Decimal(str(random.gauss(0.0005, 0.015))) for _ in range(num_returns)]
    returns_series = pl.Series("returns", returns, dtype=pl.Decimal(scale=8))

    result = benchmark(DecimalMetrics.sharpe_ratio, returns_series)

    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="metrics-decimal-operations")
def test_decimal_statistics_operations(benchmark):
    """Benchmark Decimal statistical operations (mean, std, min, max).

    Measures overhead of statistical calculations on Decimal Series.
    Expected: ~200-500 microseconds for 252 values
    Target (Epic 7): <100 microseconds
    """
    random.seed(42)
    values = [Decimal(str(random.gauss(0.0005, 0.015))) for _ in range(252)]
    series = pl.Series("values", values, dtype=pl.Decimal(scale=8))

    def calculate_statistics():
        return {
            "mean": Decimal(str(series.mean())),
            "std": Decimal(str(series.std())),
            "min": Decimal(str(series.min())),
            "max": Decimal(str(series.max())),
        }

    result = benchmark(calculate_statistics)

    assert len(result) == 4
    assert all(isinstance(v, Decimal) for v in result.values())
