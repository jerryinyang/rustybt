"""Per-module benchmarks for DecimalLedger.

Measures performance overhead of DecimalLedger operations compared to float-based
ledger operations.

Run with: pytest benchmarks/decimal_ledger_benchmark.py --benchmark-only
"""

from collections import namedtuple
from decimal import Decimal

import pytest

from rustybt.assets import Equity
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition

# Test fixture for exchange info
ExchangeInfo = namedtuple("ExchangeInfo", ["canonical_name", "name", "country_code"])
TEST_EXCHANGE = ExchangeInfo(
    canonical_name="NYSE", name="New York Stock Exchange", country_code="US"
)


@pytest.fixture
def small_portfolio() -> DecimalLedger:
    """Create portfolio with 10 positions."""
    ledger = DecimalLedger(starting_cash=Decimal("1000000"))

    for i in range(1, 11):
        asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("50"),
            last_sale_price=Decimal(str(50.0 + i * 0.5)),
            last_sale_date=None,
        )
        ledger.positions[asset] = position

    return ledger


@pytest.fixture
def large_portfolio() -> DecimalLedger:
    """Create portfolio with 100 positions."""
    ledger = DecimalLedger(starting_cash=Decimal("1000000"))

    for i in range(1, 101):
        asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("50"),
            last_sale_price=Decimal(str(50.0 + i * 0.1)),
            last_sale_date=None,
        )
        ledger.positions[asset] = position

    return ledger


@pytest.mark.benchmark(group="ledger-portfolio-value")
def test_portfolio_value_10_positions(benchmark, small_portfolio):
    """Benchmark portfolio value calculation with 10 positions.

    Expected: ~50-100 microseconds
    Target (Epic 7): <30 microseconds
    """
    result = benchmark(lambda: small_portfolio.portfolio_value)

    assert result > Decimal("1000000")
    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="ledger-portfolio-value")
def test_portfolio_value_100_positions(benchmark, large_portfolio):
    """Benchmark portfolio value calculation with 100 positions.

    Expected: ~200-400 microseconds
    Target (Epic 7): <150 microseconds
    """
    result = benchmark(lambda: large_portfolio.portfolio_value)

    assert result > Decimal("1000000")
    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="ledger-portfolio-value")
@pytest.mark.parametrize("num_positions", [10, 50, 100, 500, 1000])
def test_portfolio_value_scalability(benchmark, num_positions):
    """Test portfolio value calculation scales linearly with position count.

    Expected: O(n) complexity
    Target: Linear scaling with minimal overhead
    """
    ledger = DecimalLedger(starting_cash=Decimal("1000000"))

    for i in range(1, num_positions + 1):
        asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("50"),
            last_sale_price=Decimal("55"),
            last_sale_date=None,
        )
        ledger.positions[asset] = position

    result = benchmark(lambda: ledger.portfolio_value)

    assert result > Decimal("1000000")


@pytest.mark.benchmark(group="ledger-positions-value")
def test_positions_value_100_positions(benchmark, large_portfolio):
    """Benchmark positions_value calculation with 100 positions.

    Expected: ~150-300 microseconds
    Target (Epic 7): <100 microseconds
    """
    result = benchmark(lambda: large_portfolio.positions_value)

    assert result > Decimal("0")
    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="ledger-cash-flow")
def test_cash_updates_1000_operations(benchmark):
    """Benchmark cash balance updates (deposits/withdrawals).

    Simulates 1000 cash flow operations.
    Expected: ~100-200 microseconds per 1000 operations
    """

    def cash_flow_operations():
        ledger = DecimalLedger(starting_cash=Decimal("1000000"))

        for i in range(1000):
            # Alternate deposits and withdrawals
            if i % 2 == 0:
                ledger.cash += Decimal("100")
            else:
                ledger.cash -= Decimal("50")

        return ledger.cash

    result = benchmark(cash_flow_operations)

    # 1000 operations: 500 deposits of $100, 500 withdrawals of $50
    expected = Decimal("1000000") + Decimal("100") * 500 - Decimal("50") * 500
    assert result == expected


@pytest.mark.benchmark(group="ledger-position-lookup")
def test_position_lookup_100_positions(benchmark, large_portfolio):
    """Benchmark position lookup performance.

    Tests dictionary lookup performance for position access.
    Expected: O(1) constant time lookup
    """
    test_asset = Equity(sid=50, exchange_info=TEST_EXCHANGE, symbol="STOCK50")

    def lookup_position():
        return large_portfolio.positions.get(test_asset)

    result = benchmark(lookup_position)

    assert result is not None
    assert result.amount == Decimal("100")


@pytest.mark.benchmark(group="ledger-iteration")
def test_iterate_all_positions_100(benchmark, large_portfolio):
    """Benchmark iterating through all positions.

    Tests performance of iterating position dictionary.
    Expected: ~100-200 microseconds for 100 positions
    """

    def iterate_positions():
        total_value = Decimal("0")
        for asset, position in large_portfolio.positions.items():
            total_value += position.amount * position.last_sale_price
        return total_value

    result = benchmark(iterate_positions)

    assert result > Decimal("0")
    assert isinstance(result, Decimal)
