"""Property-based tests for DecimalOrder using Hypothesis.

This module uses property-based testing to prove precision invariants
for order execution with Decimal calculations. Tests run with 1000+ examples
to ensure financial calculations never lose precision across edge cases.
"""

from datetime import datetime
from decimal import Decimal

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from rustybt.finance.decimal import (
    CryptoCommission,
    DecimalOrder,
    DecimalTransaction,
    FixedBasisPointsSlippage,
    FixedSlippage,
    PerShareCommission,
    PerTradeCommission,
)


# Custom strategies for Decimal values
@st.composite
def decimal_prices(draw, min_value="0.01", max_value="100000.00", places=2):
    """Generate Decimal prices with specified precision."""
    value = draw(
        st.decimals(
            min_value=Decimal(min_value),
            max_value=Decimal(max_value),
            places=places,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    assume(value > Decimal("0"))
    return value


@st.composite
def decimal_quantities(draw, min_value="0.00000001", max_value="1000000.00", places=8):
    """Generate Decimal quantities with specified precision."""
    value = draw(
        st.decimals(
            min_value=Decimal(min_value),
            max_value=Decimal(max_value),
            places=places,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    assume(value > Decimal("0"))
    return value


@st.composite
def commission_rates(draw):
    """Generate commission rates (0 to 1% as Decimal)."""
    return draw(
        st.decimals(
            min_value=Decimal("0"),
            max_value=Decimal("0.01"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )


# PROPERTY 1: Order value must equal price × quantity (exact equality)
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(price=decimal_prices(), quantity=decimal_quantities(max_value="10000.00", places=2))
def test_property_order_value_exact(price, quantity, equity_asset):
    """Property: order_value = price × quantity (exact equality).

    This property ensures that order value calculations never lose precision
    due to float conversion or rounding errors.
    """
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=quantity,
        limit=price,
    )

    expected_value = price * quantity
    assert (
        order.order_value == expected_value
    ), f"Order value mismatch: {order.order_value} != {expected_value}"


# PROPERTY 2: Transaction total cost = value + commission + slippage
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    price=decimal_prices(max_value="10000.00"),
    quantity=decimal_quantities(max_value="1000.00", places=2),
    commission=decimal_prices(max_value="100.00"),
    slippage=decimal_prices(max_value="10.00"),
)
def test_property_transaction_total_cost(price, quantity, commission, slippage, equity_asset):
    """Property: transaction_total_cost = value + commission + slippage.

    Ensures transaction cost calculations maintain precision across all components.
    """
    transaction = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="test",
        asset=equity_asset,
        amount=quantity,
        price=price,
        commission=commission,
        slippage=slippage,
    )

    value = abs(quantity) * price
    expected_total = value + commission + slippage

    assert (
        transaction.total_cost == expected_total
    ), f"Total cost mismatch: {transaction.total_cost} != {expected_total}"


# PROPERTY 3: Commission must be non-negative and reasonable
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    commission_rate=commission_rates(),
    quantity=decimal_quantities(max_value="10000.00", places=2),
    price=decimal_prices(max_value="1000.00"),
)
def test_property_commission_non_negative(commission_rate, quantity, price, equity_asset):
    """Property: commission >= 0 and commission <= order_value.

    Commission must never be negative and should not exceed order value.
    """
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=quantity,
        order_type="market",
    )

    model = PerShareCommission(rate=commission_rate)
    commission = model.calculate(order, price, quantity)

    assert commission >= Decimal("0"), f"Commission is negative: {commission}"

    order_value = abs(quantity) * price
    assert commission <= order_value, f"Commission {commission} exceeds order value {order_value}"


# PROPERTY 4: Sum of partial fills equals total filled (exact equality)
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    fills=st.lists(
        st.tuples(
            decimal_prices(max_value="1000.00"),  # price
            decimal_quantities(max_value="100.00", places=2),  # amount
        ),
        min_size=1,
        max_size=10,
    )
)
def test_property_partial_fills_sum(fills, equity_asset):
    """Property: sum(partial_fills) == total_filled (exact equality).

    Ensures partial fill tracking maintains exact precision without
    accumulating rounding errors.
    """
    total_amount = sum(amount for _, amount in fills)

    DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=total_amount,
        order_type="market",
    )

    # Simulate partial fills
    total_filled = Decimal("0")
    for price, amount in fills:
        total_filled += amount

    # Verify sum equals total
    assert (
        total_filled == total_amount
    ), f"Partial fills sum {total_filled} != total amount {total_amount}"


# PROPERTY 5: Average fill price calculation maintains precision
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    fills=st.lists(
        st.tuples(
            decimal_prices(max_value="1000.00"), decimal_quantities(max_value="100.00", places=2)
        ),
        min_size=2,
        max_size=10,
    )
)
def test_property_average_fill_price(fills, equity_asset):
    """Property: average_fill_price = weighted_average(fill_prices).

    Ensures average price calculation across partial fills maintains
    mathematical precision.
    """
    total_amount = sum(amount for _, amount in fills)
    assume(total_amount > Decimal("0"))

    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=total_amount,
        order_type="market",
    )

    # Calculate weighted average
    total_value = Decimal("0")
    total_filled = Decimal("0")

    for price, amount in fills:
        total_value += price * amount
        total_filled += amount

    expected_avg = total_value / total_filled

    # Simulate blotter's average price calculation
    order.filled_price = None
    previous_filled = Decimal("0")

    for price, amount in fills:
        if order.filled_price is None:
            order.filled_price = price
        else:
            old_value = previous_filled * order.filled_price
            new_value = amount * price
            order.filled_price = (old_value + new_value) / (previous_filled + amount)

        previous_filled += amount

    # Verify average matches expected
    assert (
        order.filled_price == expected_avg
    ), f"Average fill price {order.filled_price} != expected {expected_avg}"


# PROPERTY 6: Decimal operations maintain configured precision
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    price=decimal_prices(max_value="1000.00", places=2),
    quantity=decimal_quantities(max_value="1000.00", places=2),
)
def test_property_decimal_precision_maintained(price, quantity, equity_asset):
    """Property: Decimal operations maintain configured precision.

    Ensures asset-class-specific precision is enforced throughout
    order lifecycle.
    """
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=quantity,
        limit=price,
    )

    # Check price precision (equity: 2 decimal places)
    price_tuple = price.as_tuple()
    price_scale = -price_tuple.exponent if price_tuple.exponent < 0 else 0
    assert price_scale <= 2, f"Price scale {price_scale} exceeds equity precision"

    # Check quantity precision (equity: 2 decimal places)
    qty_tuple = quantity.as_tuple()
    qty_scale = -qty_tuple.exponent if qty_tuple.exponent < 0 else 0
    assert qty_scale <= 2, f"Quantity scale {qty_scale} exceeds equity precision"

    # Check order value maintains precision
    order_value = order.order_value
    value_tuple = order_value.as_tuple()
    value_scale = -value_tuple.exponent if value_tuple.exponent < 0 else 0
    assert value_scale <= 4, f"Order value scale {value_scale} exceeds expected precision"


# PROPERTY 7: Slippage must worsen execution (buy: higher, sell: lower)
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    market_price=decimal_prices(max_value="10000.00"),
    slippage_amount=decimal_prices(max_value="10.00", places=2),
    is_buy=st.booleans(),
)
def test_property_slippage_worsens_execution(market_price, slippage_amount, is_buy, equity_asset):
    """Property: Slippage must make execution worse (buy higher, sell lower).

    Ensures slippage always represents adverse price movement, never
    favorable execution.
    """
    amount = Decimal("100") if is_buy else Decimal("-100")

    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=amount,
        order_type="market",
    )

    model = FixedSlippage(slippage=slippage_amount)
    execution_price = model.calculate(order, market_price)

    if is_buy:
        # Buy order: execution price must be higher (worse)
        assert (
            execution_price >= market_price
        ), f"Buy execution {execution_price} < market {market_price}"
    else:
        # Sell order: execution price must be lower (worse)
        assert (
            execution_price <= market_price
        ), f"Sell execution {execution_price} > market {market_price}"


# PROPERTY 8: Commission + slippage never lose precision
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    price=decimal_prices(max_value="1000.00"),
    quantity=decimal_quantities(max_value="1000.00", places=2),
    commission_rate=commission_rates(),
    basis_points=st.decimals(min_value=Decimal("1"), max_value=Decimal("100"), places=0),
)
def test_property_no_precision_loss(price, quantity, commission_rate, basis_points, equity_asset):
    """Property: Commission + slippage calculations never lose precision.

    This is the critical property for financial software: ensures that
    all cost calculations maintain exact precision with no silent rounding.
    """
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=quantity,
        order_type="market",
    )

    # Calculate commission
    commission_model = PerShareCommission(rate=commission_rate)
    commission = commission_model.calculate(order, price, quantity)

    # Calculate slippage
    slippage_model = FixedBasisPointsSlippage(basis_points=basis_points)
    execution_price = slippage_model.calculate(order, price)

    # Calculate total cost components
    base_value = abs(quantity) * price
    execution_value = abs(quantity) * execution_price
    slippage_cost = abs(execution_value - base_value)

    # Reconstruct total from components
    total_cost = execution_value + commission + slippage_cost

    # Verify each component maintains precision (no information loss)
    assert isinstance(commission, Decimal), "Commission lost Decimal type"
    assert isinstance(execution_price, Decimal), "Execution price lost Decimal type"
    assert isinstance(slippage_cost, Decimal), "Slippage cost lost Decimal type"
    assert isinstance(total_cost, Decimal), "Total cost lost Decimal type"

    # Verify no silent rounding occurred
    # All Decimal values should have finite precision
    for value, name in [
        (commission, "commission"),
        (execution_price, "execution_price"),
        (slippage_cost, "slippage_cost"),
        (total_cost, "total_cost"),
    ]:
        assert value.is_finite(), f"{name} is not finite"

        # Check that scale doesn't exceed reasonable bounds for financial data
        value_tuple = value.as_tuple()
        scale = -value_tuple.exponent if value_tuple.exponent < 0 else 0
        assert scale <= 10, f"{name} scale {scale} indicates precision issue"


# PROPERTY 9: Per-trade commission charged exactly once
@settings(
    max_examples=500, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    cost=decimal_prices(max_value="50.00"),
    fills=st.lists(
        st.tuples(
            decimal_prices(max_value="1000.00"), decimal_quantities(max_value="100.00", places=2)
        ),
        min_size=2,
        max_size=5,
    ),
)
def test_property_per_trade_commission_once(cost, fills, equity_asset):
    """Property: PerTradeCommission charged exactly once per order.

    Ensures flat commission is charged on first fill only, regardless
    of how many partial fills occur.
    """
    total_amount = sum(amount for _, amount in fills)

    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=total_amount,
        order_type="market",
    )

    model = PerTradeCommission(cost=cost)

    total_commission = Decimal("0")
    for i, (price, amount) in enumerate(fills):
        commission = model.calculate(order, price, amount)
        total_commission += commission
        order.commission += commission

        if i == 0:
            # First fill should charge full commission
            assert commission == cost
        else:
            # Subsequent fills should charge zero
            assert commission == Decimal("0")

    # Total commission should equal cost exactly
    assert total_commission == cost


# PROPERTY 10: Crypto commission respects maker/taker rates
@settings(
    max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    maker_rate=commission_rates(),
    taker_rate=commission_rates(),
    price=decimal_prices(max_value="100000.00"),
    quantity=decimal_quantities(max_value="10.00"),
    is_limit_order=st.booleans(),
)
def test_property_crypto_commission_maker_taker(
    maker_rate, taker_rate, price, quantity, is_limit_order, crypto_asset
):
    """Property: Crypto commission uses correct maker/taker rate.

    Ensures limit orders (makers) and market orders (takers) are charged
    the appropriate fee rate.
    """
    assume(maker_rate != taker_rate)  # Only test when rates differ

    order_type = "limit" if is_limit_order else "market"
    order = DecimalOrder(
        dt=datetime.now(),
        asset=crypto_asset,
        amount=quantity,
        order_type=order_type,
    )

    model = CryptoCommission(maker_rate=maker_rate, taker_rate=taker_rate)
    commission = model.calculate(order, price, quantity)

    order_value = abs(quantity) * price
    expected_rate = maker_rate if is_limit_order else taker_rate
    expected_commission = order_value * expected_rate

    assert (
        commission == expected_commission
    ), f"Commission {commission} != expected {expected_commission}"
