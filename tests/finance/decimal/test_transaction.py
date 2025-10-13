"""Unit tests for DecimalTransaction."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.finance.decimal import DecimalTransaction, create_decimal_transaction


def test_transaction_creation(equity_asset):
    """Test transaction creation with Decimal values."""
    txn = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("100"),
        price=Decimal("150.50"),
        commission=Decimal("1.00"),
        slippage=Decimal("0.50"),
    )

    assert txn.amount == Decimal("100")
    assert txn.price == Decimal("150.50")
    assert txn.commission == Decimal("1.00")
    assert txn.slippage == Decimal("0.50")


def test_transaction_value_calculation(equity_asset):
    """Test transaction value calculation: price × amount."""
    txn = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("100"),
        price=Decimal("150.50"),
        commission=Decimal("1.00"),
        slippage=Decimal("0.50"),
    )

    expected_value = Decimal("100") * Decimal("150.50")
    assert txn.transaction_value == expected_value
    assert txn.transaction_value == Decimal("15050.00")


def test_transaction_total_cost_buy(equity_asset):
    """Test total cost for buy transaction."""
    txn = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("100"),  # Buy
        price=Decimal("150.50"),
        commission=Decimal("1.00"),
        slippage=Decimal("0.50"),
    )

    # Buy: cost = value + commission + slippage
    expected_cost = Decimal("15050.00") + Decimal("1.00") + Decimal("0.50")
    assert txn.total_cost == expected_cost
    assert txn.total_cost == Decimal("15051.50")


def test_transaction_total_cost_sell(equity_asset):
    """Test total cost for sell transaction."""
    txn = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("-100"),  # Sell
        price=Decimal("150.50"),
        commission=Decimal("1.00"),
        slippage=Decimal("0.50"),
    )

    # Sell: revenue = value - commission - slippage
    expected_revenue = Decimal("15050.00") - Decimal("1.00") - Decimal("0.50")
    assert txn.total_cost == expected_revenue
    assert txn.total_cost == Decimal("15048.50")


def test_transaction_net_proceeds_buy(equity_asset):
    """Test net proceeds for buy transaction."""
    txn = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("100"),  # Buy
        price=Decimal("150.50"),
        commission=Decimal("1.00"),
        slippage=Decimal("0.50"),
    )

    # Buy: negative proceeds (cash outflow)
    assert txn.net_proceeds == -txn.total_cost
    assert txn.net_proceeds == Decimal("-15051.50")


def test_transaction_net_proceeds_sell(equity_asset):
    """Test net proceeds for sell transaction."""
    txn = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("-100"),  # Sell
        price=Decimal("150.50"),
        commission=Decimal("1.00"),
        slippage=Decimal("0.50"),
    )

    # Sell: positive proceeds (cash inflow)
    assert txn.net_proceeds == txn.total_cost
    assert txn.net_proceeds == Decimal("15048.50")


def test_transaction_validation_non_positive_price(equity_asset):
    """Test that non-positive price raises ValueError."""
    with pytest.raises(ValueError, match="Price must be positive"):
        DecimalTransaction(
            timestamp=datetime.now(),
            order_id="order-123",
            asset=equity_asset,
            amount=Decimal("100"),
            price=Decimal("0"),
            commission=Decimal("1.00"),
        )


def test_transaction_validation_negative_commission(equity_asset):
    """Test that negative commission raises ValueError."""
    with pytest.raises(ValueError, match="Commission must be non-negative"):
        DecimalTransaction(
            timestamp=datetime.now(),
            order_id="order-123",
            asset=equity_asset,
            amount=Decimal("100"),
            price=Decimal("150.50"),
            commission=Decimal("-1.00"),
        )


def test_transaction_validation_negative_slippage(equity_asset):
    """Test that negative slippage raises ValueError."""
    with pytest.raises(ValueError, match="Slippage must be non-negative"):
        DecimalTransaction(
            timestamp=datetime.now(),
            order_id="order-123",
            asset=equity_asset,
            amount=Decimal("100"),
            price=Decimal("150.50"),
            commission=Decimal("1.00"),
            slippage=Decimal("-0.50"),
        )


def test_transaction_immutability(equity_asset):
    """Test that DecimalTransaction is immutable (frozen dataclass)."""
    txn = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("100"),
        price=Decimal("150.50"),
        commission=Decimal("1.00"),
    )

    # Attempt to modify should raise FrozenInstanceError
    with pytest.raises(Exception):  # FrozenInstanceError from dataclasses
        txn.price = Decimal("200.00")


def test_create_decimal_transaction(equity_asset):
    """Test create_decimal_transaction helper function."""
    dt = datetime.now()
    txn = create_decimal_transaction(
        order_id="order-123",
        asset=equity_asset,
        dt=dt,
        price=Decimal("150.50"),
        amount=Decimal("100"),
        commission=Decimal("1.00"),
        slippage=Decimal("0.50"),
    )

    assert isinstance(txn, DecimalTransaction)
    assert txn.order_id == "order-123"
    assert txn.asset == equity_asset
    assert txn.timestamp == dt
    assert txn.price == Decimal("150.50")
    assert txn.amount == Decimal("100")
    assert txn.commission == Decimal("1.00")
    assert txn.slippage == Decimal("0.50")


def test_create_decimal_transaction_zero_amount(equity_asset):
    """Test that zero amount raises ValueError."""
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        create_decimal_transaction(
            order_id="order-123",
            asset=equity_asset,
            dt=datetime.now(),
            price=Decimal("150.50"),
            amount=Decimal("0"),
        )


def test_transaction_to_dict(equity_asset):
    """Test conversion to dictionary."""
    dt = datetime.now()
    txn = DecimalTransaction(
        timestamp=dt,
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("100"),
        price=Decimal("150.50"),
        commission=Decimal("1.00"),
        slippage=Decimal("0.50"),
        broker_order_id="broker-456",
    )

    txn_dict = txn.to_dict()

    assert txn_dict["timestamp"] == dt.isoformat()
    assert txn_dict["order_id"] == "order-123"
    assert txn_dict["asset"] == str(equity_asset)
    assert txn_dict["amount"] == "100"
    assert txn_dict["price"] == "150.50"
    assert txn_dict["commission"] == "1.00"
    assert txn_dict["slippage"] == "0.50"
    assert txn_dict["broker_order_id"] == "broker-456"
    assert txn_dict["transaction_value"] == "15050.00"
    assert txn_dict["total_cost"] == "15051.50"


def test_fractional_crypto_transaction(equity_asset):
    """Test transaction with fractional crypto quantities."""
    txn = DecimalTransaction(
        timestamp=datetime.now(),
        order_id="order-123",
        asset=equity_asset,
        amount=Decimal("0.00000001"),  # 1 Satoshi
        price=Decimal("50000.00"),
        commission=Decimal("0.00000001"),
        slippage=Decimal("0.00000001"),
    )

    expected_value = Decimal("0.00000001") * Decimal("50000.00")
    assert txn.transaction_value == expected_value
    assert txn.transaction_value == Decimal("0.0005")

    # Total cost for buy
    expected_cost = expected_value + Decimal("0.00000001") + Decimal("0.00000001")
    assert txn.total_cost == expected_cost
