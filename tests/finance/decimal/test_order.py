"""Unit tests for DecimalOrder."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.finance.decimal import (
    DecimalOrder,
    InsufficientPrecisionError,
    InvalidPriceError,
    InvalidQuantityError,
)
from rustybt.finance.decimal.config import DecimalConfig


@pytest.fixture
def config():
    """Decimal configuration fixture."""
    return DecimalConfig.get_instance()


def test_order_creation_with_decimal(equity_asset):
    """Test order creation with Decimal prices and quantities."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="limit",
        limit=Decimal("150.50"),
    )

    assert order.amount == Decimal("100")
    assert order.limit == Decimal("150.50")
    assert order.filled == Decimal("0")
    assert order.remaining == Decimal("100")
    assert order.order_type == "limit"


def test_order_value_calculation(equity_asset):
    """Test order value: price × quantity."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
        limit=Decimal("150.50"),
    )

    expected_value = Decimal("100") * Decimal("150.50")
    assert order.order_value == expected_value
    assert order.order_value == Decimal("15050.00")


def test_fractional_crypto_order(crypto_asset):
    """Test fractional order quantity for crypto (Satoshi precision)."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=crypto_asset,
        amount=Decimal("0.00000001"),  # 1 Satoshi
        order_type="market",
    )

    assert order.amount == Decimal("0.00000001")

    # Verify order value with high price
    market_price = Decimal("50000.00")
    order.filled_price = market_price
    expected_value = Decimal("0.00000001") * Decimal("50000.00")
    assert order.order_value == expected_value


def test_order_validation_zero_amount(equity_asset):
    """Test that zero amount raises InvalidQuantityError."""
    with pytest.raises(InvalidQuantityError, match="Order amount cannot be zero"):
        DecimalOrder(
            dt=datetime.now(),
            asset=equity_asset,
            amount=Decimal("0"),
            order_type="market",
        )


def test_order_validation_negative_limit_price(equity_asset):
    """Test that negative limit price raises InvalidPriceError."""
    with pytest.raises(InvalidPriceError, match="Limit price must be positive"):
        DecimalOrder(
            dt=datetime.now(),
            asset=equity_asset,
            amount=Decimal("100"),
            limit=Decimal("-150.00"),
        )


def test_order_validation_negative_stop_price(equity_asset):
    """Test that negative stop price raises InvalidPriceError."""
    with pytest.raises(InvalidPriceError, match="Stop price must be positive"):
        DecimalOrder(
            dt=datetime.now(),
            asset=equity_asset,
            amount=Decimal("100"),
            stop=Decimal("-150.00"),
        )


def test_order_validation_excessive_precision(equity_asset, config):
    """Test that excessive precision raises InsufficientPrecisionError."""
    # Equity asset should have scale=2, so 3 decimal places should fail
    with pytest.raises(InsufficientPrecisionError, match="scale .* exceeds expected"):
        DecimalOrder(
            dt=datetime.now(),
            asset=equity_asset,
            amount=Decimal("100.123"),  # 3 decimal places
            order_type="market",
        )


def test_remaining_calculation(equity_asset):
    """Test remaining unfilled quantity calculation."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    assert order.remaining == Decimal("100")

    # Simulate partial fill
    order.filled = Decimal("30")
    assert order.remaining == Decimal("70")

    # Simulate complete fill
    order.filled = Decimal("100")
    assert order.remaining == Decimal("0")


def test_trailing_stop_buy_order(equity_asset):
    """Test trailing stop for buy order."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),  # Buy
        trail_amount=Decimal("5.00"),
    )

    # Initial price: $100
    order.update_trailing_stop(Decimal("100.00"))
    assert order.stop == Decimal("105.00")  # 100 + 5

    # Price drops to $95 (new low)
    order.update_trailing_stop(Decimal("95.00"))
    assert order.stop == Decimal("100.00")  # 95 + 5

    # Price goes back up to $98 (not a new low)
    order.update_trailing_stop(Decimal("98.00"))
    assert order.stop == Decimal("100.00")  # Still 95 + 5


def test_trailing_stop_sell_order(equity_asset):
    """Test trailing stop for sell order."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),  # Sell
        trail_amount=Decimal("5.00"),
    )

    # Initial price: $100
    order.update_trailing_stop(Decimal("100.00"))
    assert order.stop == Decimal("95.00")  # 100 - 5

    # Price rises to $105 (new high)
    order.update_trailing_stop(Decimal("105.00"))
    assert order.stop == Decimal("100.00")  # 105 - 5

    # Price drops to $103 (not a new high)
    order.update_trailing_stop(Decimal("103.00"))
    assert order.stop == Decimal("100.00")  # Still 105 - 5


def test_check_triggers_buy_limit_order(equity_asset):
    """Test trigger checking for buy limit order."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),  # Buy
        limit=Decimal("150.00"),
    )

    # Price at $151: limit not reached
    order.check_triggers(Decimal("151.00"), datetime.now())
    assert not order.limit_reached
    assert not order.triggered

    # Price at $150: limit reached
    order.check_triggers(Decimal("150.00"), datetime.now())
    assert order.limit_reached
    assert order.triggered


def test_check_triggers_sell_limit_order(equity_asset):
    """Test trigger checking for sell limit order."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),  # Sell
        limit=Decimal("150.00"),
    )

    # Price at $149: limit not reached
    order.check_triggers(Decimal("149.00"), datetime.now())
    assert not order.limit_reached
    assert not order.triggered

    # Price at $150: limit reached
    order.check_triggers(Decimal("150.00"), datetime.now())
    assert order.limit_reached
    assert order.triggered


def test_check_triggers_buy_stop_order(equity_asset):
    """Test trigger checking for buy stop order."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),  # Buy
        stop=Decimal("150.00"),
    )

    # Price at $149: stop not reached
    order.check_triggers(Decimal("149.00"), datetime.now())
    assert not order.stop_reached
    assert not order.triggered

    # Price at $150: stop reached
    order.check_triggers(Decimal("150.00"), datetime.now())
    assert order.stop_reached
    assert order.triggered


def test_check_triggers_sell_stop_order(equity_asset):
    """Test trigger checking for sell stop order."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),  # Sell
        stop=Decimal("150.00"),
    )

    # Price at $151: stop not reached
    order.check_triggers(Decimal("151.00"), datetime.now())
    assert not order.stop_reached
    assert not order.triggered

    # Price at $150: stop reached
    order.check_triggers(Decimal("150.00"), datetime.now())
    assert order.stop_reached
    assert order.triggered


def test_handle_split(equity_asset):
    """Test order adjustment for stock split."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
        limit=Decimal("150.00"),
        stop=Decimal("145.00"),
    )

    # 2:1 split
    order.handle_split(Decimal("2"))

    assert order.amount == Decimal("50")  # 100 / 2
    assert order.limit == Decimal("300.00")  # 150 * 2
    assert order.stop == Decimal("290.00")  # 145 * 2


def test_order_direction(equity_asset):
    """Test order direction calculation."""
    buy_order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
    )
    assert buy_order.direction == 1

    sell_order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),
    )
    assert sell_order.direction == -1


# Advanced Order Type Tests (AC 7)


def test_stop_limit_buy_order_triggers(equity_asset):
    """Test StopLimit buy order trigger sequence with Decimal precision.

    Buy StopLimit: triggered when price >= stop, then executes when price <= limit.
    """
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),  # Buy
        stop=Decimal("150.00"),  # Trigger at $150
        limit=Decimal("152.00"),  # Execute at $152 or below
    )

    # Price at $149: neither stop nor limit reached
    stop_reached, limit_reached, sl_stop_reached = order.check_order_triggers(Decimal("149.00"))
    assert not stop_reached
    assert not limit_reached
    assert not sl_stop_reached

    # Price at $150: stop reached but price below limit, so limit also reached
    stop_reached, limit_reached, sl_stop_reached = order.check_order_triggers(Decimal("150.00"))
    assert not stop_reached  # For StopLimit, this stays False
    assert limit_reached  # Price is within limit
    assert sl_stop_reached  # Stop portion triggered

    # Price at $153: stop reached but price above limit
    order.stop_reached = False
    order.limit_reached = False
    stop_reached, limit_reached, sl_stop_reached = order.check_order_triggers(Decimal("153.00"))
    assert not limit_reached  # Price exceeds limit
    assert sl_stop_reached


def test_stop_limit_sell_order_triggers(equity_asset):
    """Test StopLimit sell order trigger sequence with Decimal precision.

    Sell StopLimit: triggered when price <= stop, then executes when price >= limit.
    """
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),  # Sell
        stop=Decimal("150.00"),  # Trigger at $150
        limit=Decimal("148.00"),  # Execute at $148 or above
    )

    # Price at $151: neither stop nor limit reached
    stop_reached, limit_reached, sl_stop_reached = order.check_order_triggers(Decimal("151.00"))
    assert not stop_reached
    assert not limit_reached
    assert not sl_stop_reached

    # Price at $150: stop reached and price above limit
    stop_reached, limit_reached, sl_stop_reached = order.check_order_triggers(Decimal("150.00"))
    assert limit_reached  # Price meets limit requirement
    assert sl_stop_reached  # Stop portion triggered

    # Price at $147: stop reached but price below limit
    order.stop_reached = False
    order.limit_reached = False
    stop_reached, limit_reached, sl_stop_reached = order.check_order_triggers(Decimal("147.00"))
    assert not limit_reached  # Price below limit
    assert sl_stop_reached


def test_stop_limit_converts_to_limit_after_trigger(equity_asset):
    """Test that StopLimit becomes Limit order after stop is triggered."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
        stop=Decimal("150.00"),
        limit=Decimal("152.00"),
    )

    # Trigger stop
    order.check_triggers(Decimal("150.00"), datetime.now())

    # After trigger, stop should be cleared (converted to limit order)
    assert order.stop is None
    assert order.limit == Decimal("152.00")


def test_trailing_stop_with_percent(equity_asset):
    """Test trailing stop with percentage instead of fixed amount."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),  # Sell
        trail_percent=Decimal("0.05"),  # 5% trail
    )

    # Initial price: $100
    order.update_trailing_stop(Decimal("100.00"))
    Decimal("100.00") * (Decimal("1") - Decimal("0.05"))
    assert order.stop == Decimal("95.00")

    # Price rises to $110 (new high for sell)
    order.update_trailing_stop(Decimal("110.00"))
    Decimal("110.00") * (Decimal("1") - Decimal("0.05"))
    assert order.stop == Decimal("104.50")  # 110 * 0.95


def test_trailing_stop_buy_with_percent(equity_asset):
    """Test trailing stop buy order with percentage."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),  # Buy
        trail_percent=Decimal("0.05"),  # 5% trail
    )

    # Initial price: $100
    order.update_trailing_stop(Decimal("100.00"))
    Decimal("100.00") * (Decimal("1") + Decimal("0.05"))
    assert order.stop == Decimal("105.00")

    # Price drops to $90 (new low for buy)
    order.update_trailing_stop(Decimal("90.00"))
    Decimal("90.00") * (Decimal("1") + Decimal("0.05"))
    assert order.stop == Decimal("94.50")  # 90 * 1.05


def test_trailing_stop_precision_maintained(equity_asset):
    """Test that trailing stop calculations maintain Decimal precision."""
    order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),
        trail_amount=Decimal("0.01"),  # Penny trail
    )

    # Test with price that could cause precision issues with floats
    order.update_trailing_stop(Decimal("123.456"))  # Note: will be rounded to scale

    # Stop should be exactly trail_amount below highest price
    # Verify calculation maintains precision
    assert isinstance(order.stop, Decimal)
    assert order.trailing_highest_price is not None


def test_bracket_order_fields(equity_asset):
    """Test bracket order with profit target and stop loss."""
    # Parent order
    parent_order = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    # Profit target (child order 1)
    profit_target = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),  # Opposite direction
        limit=Decimal("160.00"),  # Take profit at $160
        parent_order_id=parent_order.id,
    )

    # Stop loss (child order 2)
    stop_loss = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),  # Opposite direction
        stop=Decimal("140.00"),  # Stop loss at $140
        parent_order_id=parent_order.id,
    )

    # Verify bracket structure
    assert profit_target.parent_order_id == parent_order.id
    assert stop_loss.parent_order_id == parent_order.id
    assert profit_target.amount == -parent_order.amount
    assert stop_loss.amount == -parent_order.amount


def test_linked_orders_oco(equity_asset):
    """Test One-Cancels-Other (OCO) linked orders."""
    # Create two linked orders (profit target and stop loss)
    order1 = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),
        limit=Decimal("160.00"),
    )

    order2 = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),
        stop=Decimal("140.00"),
    )

    # Link them together (OCO relationship)
    order1.linked_order_ids = [order2.id]
    order2.linked_order_ids = [order1.id]

    # Verify linkage
    assert order2.id in order1.linked_order_ids
    assert order1.id in order2.linked_order_ids


def test_advanced_order_decimal_precision(equity_asset):
    """Test that all advanced order types maintain Decimal precision."""
    # StopLimit order
    stop_limit = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100.50"),
        stop=Decimal("150.25"),
        limit=Decimal("152.75"),
    )

    assert isinstance(stop_limit.stop, Decimal)
    assert isinstance(stop_limit.limit, Decimal)
    assert stop_limit.stop == Decimal("150.25")
    assert stop_limit.limit == Decimal("152.75")

    # Trailing stop with amount
    trailing = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100.00"),
        trail_amount=Decimal("5.50"),
    )

    assert isinstance(trailing.trail_amount, Decimal)
    assert trailing.trail_amount == Decimal("5.50")

    # Trailing stop with percent
    trailing_pct = DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100.00"),
        trail_percent=Decimal("0.025"),  # 2.5%
    )

    assert isinstance(trailing_pct.trail_percent, Decimal)
    assert trailing_pct.trail_percent == Decimal("0.025")
