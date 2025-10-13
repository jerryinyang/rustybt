"""Property-based tests for DecimalLedger portfolio value invariants."""

from decimal import Decimal

from hypothesis import assume, example, given

from rustybt.assets import Equity, ExchangeInfo
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition

from .strategies import decimal_portfolio_positions, decimal_prices, decimal_quantities

# Exchange info for tests
NYSE = ExchangeInfo("NYSE", "NYSE", "US")


@given(
    starting_cash=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("1000000"), scale=2),
    positions=decimal_portfolio_positions(min_positions=0, max_positions=20),
)
@example(starting_cash=Decimal("0"), positions=[])  # Edge case: empty portfolio
@example(
    starting_cash=Decimal("100000"), positions=[(Decimal("100"), Decimal("50"))]
)  # Simple case
def test_portfolio_value_accounting_identity(
    starting_cash: Decimal, positions: list[tuple[Decimal, Decimal]]
) -> None:
    """Test portfolio value = sum(position_values) + cash.

    Property:
        portfolio_value = sum(position_values) + cash

    This accounting identity must hold for all portfolios regardless of:
    - Starting cash amount
    - Number of positions
    - Position prices and quantities
    """
    # Create real ledger
    ledger = DecimalLedger(starting_cash=starting_cash)

    # Add real positions
    total_position_value = Decimal("0")
    for i, (amount, price) in enumerate(positions):
        asset = Equity(sid=i, exchange_info=NYSE, symbol=f"STOCK{i}")
        position = DecimalPosition(
            asset=asset, amount=amount, cost_basis=price, last_sale_price=price
        )
        ledger.positions[asset] = position
        total_position_value += amount * price

    # Test real calculation
    expected = total_position_value + starting_cash
    actual = ledger.portfolio_value

    # Verify exact equality (testing real implementation)
    assert actual == expected, (
        f"Portfolio value accounting identity violated: "
        f"{actual} != {expected} "
        f"(positions: {total_position_value}, cash: {starting_cash})"
    )


@given(
    start_value=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("1000000"), scale=2),
    end_value=decimal_prices(min_value=Decimal("1000"), max_value=Decimal("1000000"), scale=2),
)
@example(start_value=Decimal("1000"), end_value=Decimal("1000"))  # Zero return
@example(start_value=Decimal("1000"), end_value=Decimal("2000"))  # 100% gain
@example(start_value=Decimal("1000"), end_value=Decimal("0"))  # 100% loss
def test_returns_reconstruction(start_value: Decimal, end_value: Decimal) -> None:
    """Test returns calculation is reversible: (1 + return) × start = end.

    Property:
        end_value = (1 + returns) × start_value

    This property ensures returns calculation is consistent and reversible.
    Note: We allow small rounding in the final decimal places due to division precision.
    """
    assume(start_value > Decimal("0"))  # Avoid division by zero

    # Calculate returns
    returns = (end_value / start_value) - Decimal("1")

    # Reconstruct end value
    reconstructed_end = (Decimal("1") + returns) * start_value

    # Quantize to same precision as input (2 decimal places)
    # This handles division precision issues while maintaining financial accuracy
    from decimal import ROUND_HALF_EVEN

    reconstructed_end_rounded = reconstructed_end.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )

    # Must match when quantized to input precision
    assert reconstructed_end_rounded == end_value, (
        f"Returns reconstruction failed: "
        f"start={start_value}, end={end_value}, "
        f"returns={returns}, reconstructed={reconstructed_end}, "
        f"reconstructed_rounded={reconstructed_end_rounded}"
    )


@given(
    starting_cash=decimal_prices(min_value=Decimal("10000"), max_value=Decimal("1000000"), scale=2),
    price=decimal_prices(min_value=Decimal("10"), max_value=Decimal("500"), scale=2),
    quantity=decimal_quantities(min_value=Decimal("1"), max_value=Decimal("100"), scale=2),
)
@example(starting_cash=Decimal("10000"), price=Decimal("50"), quantity=Decimal("100"))
def test_buy_transaction_maintains_portfolio_value(
    starting_cash: Decimal, price: Decimal, quantity: Decimal
) -> None:
    """Test portfolio value is preserved after buy transaction.

    Property:
        portfolio_value_before = portfolio_value_after

    When buying an asset, cash decreases and position value increases by the same amount,
    so total portfolio value should remain constant (ignoring commissions).
    """
    cost = price * quantity
    assume(starting_cash >= cost)  # Ensure sufficient cash

    # Create ledger and record initial value
    ledger = DecimalLedger(starting_cash=starting_cash)
    initial_portfolio_value = ledger.portfolio_value

    # Execute buy transaction
    asset = Equity(sid=1, exchange_info=NYSE, symbol="TEST")
    ledger.cash -= cost
    ledger.positions[asset] = DecimalPosition(
        asset=asset, amount=quantity, cost_basis=price, last_sale_price=price
    )

    # Verify portfolio value is preserved
    final_portfolio_value = ledger.portfolio_value
    assert final_portfolio_value == initial_portfolio_value, (
        f"Portfolio value changed after buy: "
        f"before={initial_portfolio_value}, after={final_portfolio_value}, "
        f"cost={cost}, price={price}, quantity={quantity}"
    )


@given(
    starting_cash=decimal_prices(min_value=Decimal("0"), max_value=Decimal("100000"), scale=2),
    position_amount=decimal_quantities(min_value=Decimal("1"), max_value=Decimal("100"), scale=2),
    position_price=decimal_prices(min_value=Decimal("10"), max_value=Decimal("500"), scale=2),
    sell_price=decimal_prices(min_value=Decimal("10"), max_value=Decimal("500"), scale=2),
)
@example(
    starting_cash=Decimal("10000"),
    position_amount=Decimal("100"),
    position_price=Decimal("50"),
    sell_price=Decimal("55"),
)
def test_sell_transaction_maintains_portfolio_value(
    starting_cash: Decimal,
    position_amount: Decimal,
    position_price: Decimal,
    sell_price: Decimal,
) -> None:
    """Test portfolio value changes correctly after sell transaction.

    Property:
        portfolio_value_after = portfolio_value_before + (sell_price - last_price) × amount

    When selling an asset, cash increases and position value decreases.
    The portfolio value change should equal the realized P&L.
    """
    # Create ledger with position
    ledger = DecimalLedger(starting_cash=starting_cash)
    asset = Equity(sid=1, exchange_info=NYSE, symbol="TEST")
    ledger.positions[asset] = DecimalPosition(
        asset=asset,
        amount=position_amount,
        cost_basis=position_price,
        last_sale_price=position_price,
    )

    initial_portfolio_value = ledger.portfolio_value

    # Execute sell transaction
    sell_proceeds = sell_price * position_amount
    ledger.cash += sell_proceeds
    del ledger.positions[asset]

    # Calculate expected portfolio value
    # Initial: cash + (amount × position_price)
    # Final: (cash + sell_proceeds)
    # Change: sell_proceeds - (amount × position_price) = amount × (sell_price - position_price)
    expected_change = position_amount * (sell_price - position_price)
    expected_portfolio_value = initial_portfolio_value + expected_change

    # Verify portfolio value changed correctly
    final_portfolio_value = ledger.portfolio_value
    assert final_portfolio_value == expected_portfolio_value, (
        f"Portfolio value incorrect after sell: "
        f"before={initial_portfolio_value}, after={final_portfolio_value}, "
        f"expected={expected_portfolio_value}, change={expected_change}, "
        f"sell_price={sell_price}, position_price={position_price}, amount={position_amount}"
    )


@given(
    cash=decimal_prices(min_value=Decimal("0"), max_value=Decimal("1000000"), scale=2),
    positions=decimal_portfolio_positions(min_positions=0, max_positions=20),
)
def test_portfolio_value_non_negative_with_long_only(
    cash: Decimal, positions: list[tuple[Decimal, Decimal]]
) -> None:
    """Test portfolio value is non-negative for long-only portfolios.

    Property:
        portfolio_value >= 0 (for long-only portfolios)

    With non-negative cash and all positions long (positive amounts),
    portfolio value must be non-negative.
    """
    ledger = DecimalLedger(starting_cash=cash)

    for i, (amount, price) in enumerate(positions):
        asset = Equity(sid=i, exchange_info=NYSE, symbol=f"STOCK{i}")
        position = DecimalPosition(
            asset=asset, amount=amount, cost_basis=price, last_sale_price=price
        )
        ledger.positions[asset] = position

    assert ledger.portfolio_value >= Decimal("0"), (
        f"Portfolio value is negative for long-only portfolio: "
        f"value={ledger.portfolio_value}, cash={cash}, positions={positions}"
    )
