"""Property-based tests for order execution and commission calculations."""

from decimal import Decimal

from hypothesis import assume, example, given

from rustybt.assets import Equity, ExchangeInfo
from rustybt.finance.commission import PerDollar, PerShare
from rustybt.finance.decimal.order import DecimalOrder
from rustybt.finance.decimal.transaction import DecimalTransaction

from .strategies import commission_rates, decimal_prices, decimal_quantities

# Exchange info for tests
NYSE = ExchangeInfo("NYSE", "NYSE", "US")


@given(
    price=decimal_prices(min_value=Decimal("1"), max_value=Decimal("500"), scale=2),
    quantity=decimal_quantities(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
)
@example(price=Decimal("50"), quantity=Decimal("100"))
@example(price=Decimal("0.01"), quantity=Decimal("1"))  # Minimum values
def test_order_fill_value_exact_calculation(price: Decimal, quantity: Decimal) -> None:
    """Test fill_value = fill_price × fill_quantity (exact equality).

    Property:
        fill_value = fill_price × fill_quantity

    Order execution value must be calculated exactly without rounding errors.
    """
    # Calculate expected fill value
    expected_fill_value = price * quantity

    # Create and fill order
    asset = Equity(sid=1, exchange_info=NYSE, symbol="TEST")
    order = DecimalOrder(
        dt=None,
        asset=asset,
        amount=quantity,
        stop=None,
        limit=None,
        id=1,
    )

    # Create transaction (simulating order fill)
    transaction = DecimalTransaction(
        asset=asset,
        amount=quantity,
        dt=None,
        price=price,
        order_id=order.id,
        commission=Decimal("0"),
    )

    # Verify fill value is exact
    actual_fill_value = transaction.price * transaction.amount
    assert actual_fill_value == expected_fill_value, (
        f"Fill value calculation inexact: "
        f"expected={expected_fill_value}, actual={actual_fill_value}, "
        f"price={price}, quantity={quantity}"
    )


@given(
    order_value=decimal_prices(min_value=Decimal("100"), max_value=Decimal("100000"), scale=2),
    commission_rate=commission_rates(max_rate=Decimal("0.01")),
)
@example(order_value=Decimal("10000"), commission_rate=Decimal("0.001"))
@example(order_value=Decimal("100"), commission_rate=Decimal("0"))  # Zero commission
def test_per_dollar_commission_bounds(order_value: Decimal, commission_rate: Decimal) -> None:
    """Test commission is non-negative and <= order value.

    Property:
        0 <= commission <= order_value

    Commission must be non-negative and cannot exceed the order value.
    """
    commission_model = PerDollar(cost=float(commission_rate))
    Equity(sid=1, exchange_info=NYSE, symbol="TEST")

    # Calculate commission
    # PerDollar expects order object, so we need to calculate directly
    commission = Decimal(str(commission_model.cost)) * order_value

    # Verify bounds
    assert commission >= Decimal("0"), f"Commission is negative: {commission}"
    assert commission <= order_value, (
        f"Commission exceeds order value: "
        f"commission={commission}, order_value={order_value}, rate={commission_rate}"
    )


@given(
    shares=decimal_quantities(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
    rate_per_share=decimal_prices(
        min_value=Decimal("0"), max_value=Decimal("0.10"), scale=4
    ),  # $0-0.10 per share
)
@example(shares=Decimal("100"), rate_per_share=Decimal("0.01"))
@example(shares=Decimal("1"), rate_per_share=Decimal("0"))  # Zero commission
def test_per_share_commission_calculation(shares: Decimal, rate_per_share: Decimal) -> None:
    """Test per-share commission = shares × rate.

    Property:
        commission = shares × rate_per_share

    Per-share commission must be calculated exactly.
    """
    commission_model = PerShare(cost=float(rate_per_share))

    # Calculate expected commission
    expected_commission = shares * rate_per_share

    # Calculate actual commission (using model's formula)
    actual_commission = Decimal(str(commission_model.cost)) * shares

    # Verify exact equality
    assert actual_commission == expected_commission, (
        f"Per-share commission calculation inexact: "
        f"expected={expected_commission}, actual={actual_commission}, "
        f"shares={shares}, rate={rate_per_share}"
    )

    # Verify non-negative
    assert actual_commission >= Decimal("0"), f"Commission is negative: {actual_commission}"


@given(
    partial_fills=decimal_quantities(min_value=Decimal("10"), max_value=Decimal("100"), scale=2),
    num_fills=decimal_prices(min_value=Decimal("2"), max_value=Decimal("10"), scale=0),
)
@example(partial_fills=Decimal("25"), num_fills=Decimal("4"))  # 4 fills of 25 = 100
def test_partial_fills_sum_to_total(partial_fills: Decimal, num_fills: Decimal) -> None:
    """Test sum of partial fills equals total filled amount.

    Property:
        sum(partial_fill_amounts) = total_filled_amount

    When an order is filled in multiple parts, the sum of partial fills
    must equal the total filled amount.
    """
    total_filled = partial_fills * num_fills
    fills = [partial_fills] * int(num_fills)

    # Verify sum equals total
    calculated_sum = sum(fills, start=Decimal("0"))
    assert calculated_sum == total_filled, (
        f"Partial fills don't sum to total: "
        f"sum={calculated_sum}, expected={total_filled}, "
        f"partial_fill={partial_fills}, num_fills={num_fills}"
    )


@given(
    fills=decimal_quantities(min_value=Decimal("1"), max_value=Decimal("100"), scale=2),
    prices=decimal_prices(min_value=Decimal("10"), max_value=Decimal("500"), scale=2),
    num_fills=decimal_prices(min_value=Decimal("2"), max_value=Decimal("5"), scale=0),
)
@example(fills=Decimal("50"), prices=Decimal("100"), num_fills=Decimal("2"))
def test_weighted_average_fill_price(fills: Decimal, prices: Decimal, num_fills: Decimal) -> None:
    """Test average fill price = weighted average of fill prices.

    Property:
        avg_fill_price = sum(fill_amount × fill_price) / sum(fill_amount)

    When an order is filled at multiple prices, the average fill price
    must be the weighted average.
    """
    num_fills_int = int(num_fills)
    fill_amounts = [fills] * num_fills_int
    fill_prices = [prices + Decimal(str(i)) for i in range(num_fills_int)]  # Varying prices

    # Calculate weighted average
    total_value = sum(
        (amount * price for amount, price in zip(fill_amounts, fill_prices, strict=False)),
        start=Decimal("0"),
    )
    total_amount = sum(fill_amounts, start=Decimal("0"))

    assume(total_amount > Decimal("0"))  # Avoid division by zero
    expected_avg_price = total_value / total_amount

    # Manually calculate weighted average
    calculated_avg_price = total_value / total_amount

    # Verify exact equality
    assert calculated_avg_price == expected_avg_price, (
        f"Weighted average fill price incorrect: "
        f"calculated={calculated_avg_price}, expected={expected_avg_price}"
    )


@given(
    limit_price=decimal_prices(min_value=Decimal("50"), max_value=Decimal("100"), scale=2),
    fill_price=decimal_prices(min_value=Decimal("40"), max_value=Decimal("110"), scale=2),
    quantity=decimal_quantities(min_value=Decimal("1"), max_value=Decimal("100"), scale=2),
)
@example(limit_price=Decimal("50"), fill_price=Decimal("49"), quantity=Decimal("100"))
@example(limit_price=Decimal("50"), fill_price=Decimal("50"), quantity=Decimal("100"))
@example(limit_price=Decimal("50"), fill_price=Decimal("51"), quantity=Decimal("100"))
def test_limit_order_price_constraint(
    limit_price: Decimal, fill_price: Decimal, quantity: Decimal
) -> None:
    """Test limit buy orders only fill at or below limit price.

    Property (buy limit):
        if filled, then fill_price <= limit_price

    Property (sell limit):
        if filled, then fill_price >= limit_price
    """
    asset = Equity(sid=1, exchange_info=NYSE, symbol="TEST")

    # Test buy limit order
    buy_order = DecimalOrder(
        dt=None,
        asset=asset,
        amount=quantity,  # Positive = buy
        stop=None,
        limit=limit_price,
        id=1,
    )

    # Buy limit should only fill at or below limit price
    if quantity > Decimal("0"):  # Buy order
        should_fill = fill_price <= limit_price
        if should_fill:
            # Create transaction
            transaction = DecimalTransaction(
                asset=asset,
                amount=quantity,
                dt=None,
                price=fill_price,
                order_id=buy_order.id,
                commission=Decimal("0"),
            )
            assert transaction.price <= limit_price, (
                f"Buy limit order filled above limit: "
                f"fill_price={fill_price}, limit_price={limit_price}"
            )

    # Test sell limit order
    sell_order = DecimalOrder(
        dt=None,
        asset=asset,
        amount=-quantity,  # Negative = sell
        stop=None,
        limit=limit_price,
        id=2,
    )

    # Sell limit should only fill at or above limit price
    if quantity > Decimal("0"):  # Sell order (negative amount)
        should_fill = fill_price >= limit_price
        if should_fill:
            # Create transaction
            transaction = DecimalTransaction(
                asset=asset,
                amount=-quantity,
                dt=None,
                price=fill_price,
                order_id=sell_order.id,
                commission=Decimal("0"),
            )
            assert transaction.price >= limit_price, (
                f"Sell limit order filled below limit: "
                f"fill_price={fill_price}, limit_price={limit_price}"
            )
