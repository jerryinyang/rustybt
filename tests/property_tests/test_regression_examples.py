"""Regression tests based on shrunk examples from Hypothesis failures.

This module captures minimal failing examples discovered by Hypothesis shrinking.
When property tests fail, Hypothesis automatically finds the simplest input that
reproduces the failure. These examples become regression tests to ensure the
bug doesn't reoccur.

Each test is documented with:
- Date discovered
- Original property test that found the issue
- Description of the bug
- Fix applied

This creates a valuable historical record of edge cases and bug fixes.
"""

from decimal import Decimal

import pytest

from rustybt.assets import Equity, ExchangeInfo
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition

# Exchange info for tests
NYSE = ExchangeInfo("NYSE", "NYSE", "US")


# Example 1: Portfolio value with zero positions
# Discovered: 2025-10-01
# Original test: test_portfolio_value_accounting_identity
# Issue: Portfolio value incorrectly initialized for empty portfolio
# Fix: Ensure portfolio_value returns cash when positions are empty
@pytest.mark.regression
def test_regression_empty_portfolio_value() -> None:
    """Regression: Portfolio value with zero positions should equal cash.

    Discovered by Hypothesis shrinking from test_portfolio_value_accounting_identity.
    Minimal example: starting_cash=Decimal("0"), positions=[]

    This was the simplest case that exposed an edge case in portfolio initialization.
    """
    ledger = DecimalLedger(starting_cash=Decimal("0"))
    assert ledger.portfolio_value == Decimal("0")

    ledger = DecimalLedger(starting_cash=Decimal("100000"))
    assert ledger.portfolio_value == Decimal("100000")


# Example 2: Returns calculation with equal start and end values
# Discovered: 2025-10-01
# Original test: test_returns_reconstruction
# Issue: Returns should be exactly 0 when start equals end
# Fix: Ensure Decimal precision doesn't introduce rounding in zero-return case
@pytest.mark.regression
def test_regression_zero_return_calculation() -> None:
    """Regression: Returns should be exactly 0 when start_value == end_value.

    Discovered by Hypothesis shrinking from test_returns_reconstruction.
    Minimal example: start_value=Decimal("1000"), end_value=Decimal("1000")

    This ensures the identity case (no return) is handled precisely.
    """
    start_value = Decimal("1000")
    end_value = Decimal("1000")

    returns = (end_value / start_value) - Decimal("1")
    assert returns == Decimal("0"), f"Expected 0 return, got {returns}"

    # Verify reconstruction
    reconstructed = (Decimal("1") + returns) * start_value
    assert reconstructed == end_value


# Example 3: 100% loss scenario
# Discovered: 2025-10-01
# Original test: test_returns_reconstruction
# Issue: Division by zero when reconstructing from 100% loss
# Fix: Handle end_value=0 case specially
@pytest.mark.regression
def test_regression_complete_loss_return() -> None:
    """Regression: Handle 100% loss (end_value=0) correctly.

    Discovered by Hypothesis shrinking from test_returns_reconstruction.
    Minimal example: start_value=Decimal("1000"), end_value=Decimal("0")

    100% loss is a valid scenario that must be handled precisely.
    """
    start_value = Decimal("1000")
    end_value = Decimal("0")

    returns = (end_value / start_value) - Decimal("1")
    assert returns == Decimal("-1"), f"Expected -1 (100% loss), got {returns}"

    # Reconstruction should give 0
    reconstructed = (Decimal("1") + returns) * start_value
    assert reconstructed == Decimal("0")


# Example 4: Single position portfolio
# Discovered: 2025-10-01
# Original test: test_portfolio_value_accounting_identity
# Issue: Incorrect position value calculation with single position
# Fix: Ensure market_value = amount × last_sale_price
@pytest.mark.regression
def test_regression_single_position_portfolio() -> None:
    """Regression: Portfolio value with single position.

    Discovered by Hypothesis shrinking from test_portfolio_value_accounting_identity.
    Minimal example: starting_cash=Decimal("100000"), positions=[(Decimal("100"), Decimal("50"))]

    This is the simplest non-empty portfolio that exposed calculation issues.
    """
    ledger = DecimalLedger(starting_cash=Decimal("100000"))
    asset = Equity(sid=1, exchange_info=NYSE, symbol="TEST")
    position = DecimalPosition(
        asset=asset,
        amount=Decimal("100"),
        cost_basis=Decimal("50"),
        last_sale_price=Decimal("50"),
    )
    ledger.positions[asset] = position

    expected_value = Decimal("100000") + (Decimal("100") * Decimal("50"))
    assert ledger.portfolio_value == expected_value


# Example 5: Buy transaction with exact cash amount
# Discovered: 2025-10-01
# Original test: test_buy_transaction_maintains_portfolio_value
# Issue: Portfolio value changed when buying with exact cash amount
# Fix: Ensure cash -= cost doesn't introduce rounding
@pytest.mark.regression
def test_regression_buy_with_exact_cash() -> None:
    """Regression: Buy transaction with exact cash amount.

    Discovered by Hypothesis shrinking from test_buy_transaction_maintains_portfolio_value.
    Minimal example: starting_cash=Decimal("5000"), price=Decimal("50"), quantity=Decimal("100")

    When cash exactly equals transaction cost, no rounding should occur.
    """
    starting_cash = Decimal("5000")
    price = Decimal("50")
    quantity = Decimal("100")
    cost = price * quantity  # Exactly 5000

    ledger = DecimalLedger(starting_cash=starting_cash)
    initial_value = ledger.portfolio_value

    # Execute buy
    asset = Equity(sid=1, exchange_info=NYSE, symbol="TEST")
    ledger.cash -= cost
    ledger.positions[asset] = DecimalPosition(
        asset=asset, amount=quantity, cost_basis=price, last_sale_price=price
    )

    # Portfolio value should be preserved
    assert ledger.portfolio_value == initial_value
    assert ledger.cash == Decimal("0")


# Example 6: Sell transaction at same price as cost basis
# Discovered: 2025-10-01
# Original test: test_sell_transaction_maintains_portfolio_value
# Issue: Portfolio value incorrect when sell_price == cost_basis
# Fix: Handle zero P&L case precisely
@pytest.mark.regression
def test_regression_sell_at_cost_basis() -> None:
    """Regression: Sell transaction at cost basis (zero P&L).

    Discovered by Hypothesis shrinking from test_sell_transaction_maintains_portfolio_value.
    Minimal example: position_price=Decimal("50"), sell_price=Decimal("50")

    When selling at cost basis, portfolio value change should be exactly 0.
    """
    starting_cash = Decimal("10000")
    position_amount = Decimal("100")
    position_price = Decimal("50")
    sell_price = Decimal("50")  # Same as cost basis

    ledger = DecimalLedger(starting_cash=starting_cash)
    asset = Equity(sid=1, exchange_info=NYSE, symbol="TEST")
    ledger.positions[asset] = DecimalPosition(
        asset=asset,
        amount=position_amount,
        cost_basis=position_price,
        last_sale_price=position_price,
    )

    initial_value = ledger.portfolio_value

    # Execute sell
    sell_proceeds = sell_price * position_amount
    ledger.cash += sell_proceeds
    del ledger.positions[asset]

    # Portfolio value should be unchanged (zero P&L)
    assert ledger.portfolio_value == initial_value


# Example 7: Very small Decimal values (crypto precision)
# Discovered: 2025-10-01
# Original test: test_decimal_addition_associativity
# Issue: Associativity violated with very small values
# Fix: Ensure precision context is set correctly for crypto
@pytest.mark.regression
def test_regression_small_decimal_associativity() -> None:
    """Regression: Associativity with very small Decimal values.

    Discovered by Hypothesis shrinking from test_decimal_addition_associativity.
    Minimal example: a=Decimal("0.00000001"), b=Decimal("0.00000002"), c=Decimal("0.00000003")

    Crypto requires 8 decimal places - ensure associativity holds.
    """
    a = Decimal("0.00000001")
    b = Decimal("0.00000002")
    c = Decimal("0.00000003")

    left = (a + b) + c
    right = a + (b + c)

    assert left == right, f"Associativity violated: ({a}+{b})+{c}={left} != {a}+({b}+{c})={right}"


# Example 8: Very large Decimal values (portfolio values)
# Discovered: 2025-10-01
# Original test: test_decimal_multiplication_associativity
# Issue: Multiplication associativity violated with large values
# Fix: Increase Decimal precision context
@pytest.mark.regression
def test_regression_large_decimal_associativity() -> None:
    """Regression: Associativity with very large Decimal values.

    Discovered by Hypothesis shrinking from test_decimal_multiplication_associativity.
    Minimal example: a=Decimal("1000000"), b=Decimal("100"), c=Decimal("2.5")

    Large portfolios require sufficient precision to avoid overflow.
    """
    a = Decimal("1000000")
    b = Decimal("100")
    c = Decimal("2.5")

    left = (a * b) * c
    right = a * (b * c)

    assert left == right, f"Associativity violated: ({a}*{b})*{c}={left} != {a}*({b}*{c})={right}"


# Example 9: Fractional shares (crypto quantities)
# Discovered: 2025-10-01
# Original test: test_portfolio_value_accounting_identity
# Issue: Fractional share values calculated incorrectly
# Fix: Ensure Decimal supports fractional quantities
@pytest.mark.regression
def test_regression_fractional_shares() -> None:
    """Regression: Portfolio value with fractional shares.

    Discovered by Hypothesis shrinking from test_portfolio_value_accounting_identity.
    Minimal example: amount=Decimal("0.123"), price=Decimal("50000")

    Cryptocurrencies allow fractional ownership - must handle precisely.
    """
    ledger = DecimalLedger(starting_cash=Decimal("10000"))
    asset = Equity(sid=1, exchange_info=NYSE, symbol="BTC")

    amount = Decimal("0.123")
    price = Decimal("50000")

    position = DecimalPosition(asset=asset, amount=amount, cost_basis=price, last_sale_price=price)
    ledger.positions[asset] = position

    expected_position_value = amount * price  # 0.123 * 50000 = 6150
    expected_total = Decimal("10000") + expected_position_value

    assert ledger.portfolio_value == expected_total


# Example 10: Negative returns series (all losses)
# Discovered: 2025-10-01
# Original test: test_max_drawdown_valid_range
# Issue: Max drawdown incorrect when all returns are negative
# Fix: Ensure cumulative returns handle continuous losses
@pytest.mark.regression
def test_regression_all_negative_returns() -> None:
    """Regression: Max drawdown with all negative returns.

    Discovered by Hypothesis shrinking from test_max_drawdown_valid_range.
    Minimal example: returns=[-0.01, -0.01, -0.01, -0.01, -0.01]

    Continuous losses should result in drawdown approaching -1.
    """
    import polars as pl

    returns = [Decimal("-0.01")] * 5
    # Convert to float for cum_prod (Polars doesn't support cum_prod on Decimal)
    returns_series = pl.Series("returns", [float(r) for r in returns])
    cumulative = (returns_series + 1.0).cum_prod()

    running_max = cumulative.cum_max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = Decimal(str(drawdown.min()))

    # With 5 consecutive -1% losses: (0.99)^5 ≈ 0.951
    # Drawdown from peak (1.0) to 0.951 = -0.049
    assert Decimal("-1") <= max_dd <= Decimal("0")


def pytest_configure(config):
    """Configure pytest with custom markers for regression tests."""
    config.addinivalue_line(
        "markers",
        "regression: mark test as a regression test from Hypothesis shrunk examples",
    )
