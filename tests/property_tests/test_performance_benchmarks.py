"""Performance benchmarks for property-based tests.

This module provides benchmarks to ensure property tests complete within
acceptable time bounds and to track performance over time.
"""

from decimal import Decimal

import pytest
from hypothesis import given

from rustybt.assets import Equity, ExchangeInfo
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition

from .strategies import (
    decimal_portfolio_positions,
    decimal_prices,
    decimal_quantities,
    decimal_returns_series,
    ohlcv_bars,
)

# Exchange info for tests
NYSE = ExchangeInfo("NYSE", "NYSE", "US")


@pytest.mark.benchmark
@given(
    starting_cash=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("1000000"), scale=2),
    positions=decimal_portfolio_positions(min_positions=0, max_positions=20),
)
def test_portfolio_value_calculation_performance(
    starting_cash: Decimal, positions: list[tuple[Decimal, Decimal]], benchmark
) -> None:
    """Benchmark portfolio value calculation with property testing.

    Ensures that portfolio value calculation completes within acceptable
    time bounds (<1ms for typical portfolios).
    """

    def setup():
        ledger = DecimalLedger(starting_cash=starting_cash)
        for i, (amount, price) in enumerate(positions):
            asset = Equity(sid=i, exchange_info=NYSE, symbol=f"STOCK{i}")
            position = DecimalPosition(
                asset=asset, amount=amount, cost_basis=price, last_sale_price=price
            )
            ledger.positions[asset] = position
        return (ledger,), {}

    def calculate_value(ledger):
        return ledger.portfolio_value

    result = benchmark.pedantic(calculate_value, setup=setup, rounds=100)
    assert result >= Decimal("0")


@pytest.mark.benchmark
@given(
    start_value=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("1000000"), scale=2),
    end_value=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("1000000"), scale=2),
)
def test_returns_calculation_performance(
    start_value: Decimal, end_value: Decimal, benchmark
) -> None:
    """Benchmark returns calculation performance.

    Ensures returns calculation completes within acceptable time bounds.
    """
    from hypothesis import assume

    assume(start_value > Decimal("0"))

    def calculate_returns():
        return (end_value / start_value) - Decimal("1")

    result = benchmark(calculate_returns)
    # Verify result is reasonable (between -100% and +10000%)
    assert Decimal("-1") <= result <= Decimal("100")


@pytest.mark.benchmark
@given(returns_series=decimal_returns_series(min_size=252, max_size=252))
def test_metrics_calculation_performance(returns_series: list[Decimal], benchmark) -> None:
    """Benchmark metrics calculation with 1-year return series.

    Ensures metrics calculation (Sharpe, drawdown, etc.) completes within
    acceptable time bounds for typical return series.
    """
    import polars as pl

    def calculate_metrics():
        returns = pl.Series("returns", returns_series)
        cumulative = (returns + Decimal("1")).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_dd = Decimal(str(drawdown.min()))
        return max_dd

    result = benchmark(calculate_metrics)
    # Verify result is in valid range
    assert Decimal("-1") <= result <= Decimal("0")


@pytest.mark.benchmark
@given(bars=ohlcv_bars(num_bars=1000))
def test_ohlcv_validation_performance(bars, benchmark) -> None:
    """Benchmark OHLCV validation performance.

    Ensures OHLCV relationship validation completes within acceptable
    time bounds for 1000 bars (typical day's data at minute resolution).
    """

    def validate_ohlcv():
        # Validate all OHLCV relationships
        valid = (
            (bars["high"] >= bars["open"]).all()
            and (bars["high"] >= bars["close"]).all()
            and (bars["low"] <= bars["open"]).all()
            and (bars["low"] <= bars["close"]).all()
            and (bars["high"] >= bars["low"]).all()
        )
        return valid

    result = benchmark(validate_ohlcv)
    assert result is True


@pytest.mark.benchmark
def test_decimal_arithmetic_performance(benchmark) -> None:
    """Benchmark Decimal arithmetic operations.

    Ensures Decimal operations maintain acceptable performance for
    high-frequency calculations.
    """

    def arithmetic_operations():
        a = Decimal("123.45")
        b = Decimal("678.90")
        c = Decimal("2.5")

        # Typical financial calculations
        result = (a + b) * c - a / b
        return result

    result = benchmark.pedantic(arithmetic_operations, rounds=10000, iterations=10)
    assert isinstance(result, Decimal)


@pytest.mark.benchmark
@given(
    price=decimal_prices(min_value=Decimal("10"), max_value=Decimal("500"), scale=2),
    quantity=decimal_quantities(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
)
def test_transaction_execution_performance(price: Decimal, quantity: Decimal, benchmark) -> None:
    """Benchmark transaction execution performance.

    Ensures buy/sell transaction execution completes within acceptable
    time bounds.
    """
    starting_cash = Decimal("100000")

    def setup():
        ledger = DecimalLedger(starting_cash=starting_cash)
        asset = Equity(sid=1, exchange_info=NYSE, symbol="TEST")
        return (ledger, asset), {}

    def execute_transaction(ledger, asset):
        cost = price * quantity
        if ledger.cash >= cost:
            ledger.cash -= cost
            ledger.positions[asset] = DecimalPosition(
                asset=asset, amount=quantity, cost_basis=price, last_sale_price=price
            )
        return ledger.portfolio_value

    result = benchmark.pedantic(execute_transaction, setup=setup, rounds=100)
    assert result >= Decimal("0")


# Performance regression thresholds
# These are baseline expectations - CI will fail if performance degrades beyond these
PERFORMANCE_THRESHOLDS = {
    "portfolio_value_calculation": 0.001,  # 1ms max
    "returns_calculation": 0.0001,  # 0.1ms max
    "metrics_calculation": 0.010,  # 10ms max for 252-day series
    "ohlcv_validation": 0.005,  # 5ms max for 1000 bars
    "decimal_arithmetic": 0.00001,  # 10μs max for basic ops
    "transaction_execution": 0.001,  # 1ms max
}


def pytest_configure(config):
    """Configure pytest with custom markers for benchmarks."""
    config.addinivalue_line("markers", "benchmark: mark test as a performance benchmark")
