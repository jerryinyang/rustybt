"""Unit tests for Decimal slippage models."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.finance.decimal import (
    AsymmetricSlippage,
    DecimalOrder,
    FixedBasisPointsSlippage,
    FixedSlippage,
    NoSlippage,
    VolumeShareSlippage,
)


@pytest.fixture
def buy_order(equity_asset):
    """Create buy order fixture."""
    return DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),  # Buy
        order_type="market",
    )


@pytest.fixture
def sell_order(equity_asset):
    """Create sell order fixture."""
    return DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("-100"),  # Sell
        order_type="market",
    )


def test_no_slippage(buy_order):
    """Test NoSlippage returns market price."""
    model = NoSlippage()
    execution_price = model.calculate(buy_order, Decimal("100.00"))
    assert execution_price == Decimal("100.00")


def test_fixed_slippage_buy(buy_order):
    """Test FixedSlippage for buy order."""
    model = FixedSlippage(slippage=Decimal("0.10"))
    execution_price = model.calculate(buy_order, Decimal("100.00"))

    # Buy: pay more (worse execution)
    assert execution_price == Decimal("100.10")


def test_fixed_slippage_sell(sell_order):
    """Test FixedSlippage for sell order."""
    model = FixedSlippage(slippage=Decimal("0.10"))
    execution_price = model.calculate(sell_order, Decimal("100.00"))

    # Sell: receive less (worse execution)
    assert execution_price == Decimal("99.90")


def test_fixed_slippage_negative():
    """Test FixedSlippage rejects negative slippage."""
    with pytest.raises(ValueError, match="Slippage must be non-negative"):
        FixedSlippage(slippage=Decimal("-0.10"))


def test_fixed_bps_slippage_buy(buy_order):
    """Test FixedBasisPointsSlippage for buy order."""
    model = FixedBasisPointsSlippage(basis_points=Decimal("10"))  # 0.1%
    execution_price = model.calculate(buy_order, Decimal("100.00"))

    # Buy: 100 × 1.001 = 100.10
    assert execution_price == Decimal("100.10")


def test_fixed_bps_slippage_sell(sell_order):
    """Test FixedBasisPointsSlippage for sell order."""
    model = FixedBasisPointsSlippage(basis_points=Decimal("10"))  # 0.1%
    execution_price = model.calculate(sell_order, Decimal("100.00"))

    # Sell: 100 × 0.999 = 99.90
    assert execution_price == Decimal("99.90")


def test_fixed_bps_slippage_negative():
    """Test FixedBasisPointsSlippage rejects negative basis points."""
    with pytest.raises(ValueError, match="Basis points must be non-negative"):
        FixedBasisPointsSlippage(basis_points=Decimal("-10"))


def test_volume_share_slippage_buy(buy_order):
    """Test VolumeShareSlippage for buy order."""
    model = VolumeShareSlippage(
        volume_limit=Decimal("0.025"),
        impact_factor=Decimal("0.1"),
    )

    # Order: 1000 shares, Bar volume: 100000 shares
    # Volume share: 1000 / 100000 = 0.01
    # Price impact: (0.01)^2 × 0.1 = 0.00001
    # Execution price: 100 × (1 + 0.00001) = 100.001
    execution_price = model.calculate(
        buy_order,
        Decimal("100.00"),
        Decimal("1000"),
        Decimal("100000"),
    )

    assert execution_price == Decimal("100.001")


def test_volume_share_slippage_sell(sell_order):
    """Test VolumeShareSlippage for sell order."""
    model = VolumeShareSlippage(
        volume_limit=Decimal("0.025"),
        impact_factor=Decimal("0.1"),
    )

    # Sell: price decreases
    execution_price = model.calculate(
        sell_order,
        Decimal("100.00"),
        Decimal("1000"),
        Decimal("100000"),
    )

    assert execution_price == Decimal("99.999")


def test_volume_share_slippage_exceeds_limit(buy_order):
    """Test VolumeShareSlippage raises error when volume limit exceeded."""
    model = VolumeShareSlippage(
        volume_limit=Decimal("0.025"),  # 2.5% limit
        impact_factor=Decimal("0.1"),
    )

    # Order: 3000 shares, Bar volume: 100000 shares
    # Volume share: 3000 / 100000 = 0.03 (exceeds 0.025 limit)
    with pytest.raises(ValueError, match="Fill volume .* exceeds limit"):
        model.calculate(
            buy_order,
            Decimal("100.00"),
            Decimal("3000"),
            Decimal("100000"),
        )


def test_volume_share_slippage_zero_volume(buy_order):
    """Test VolumeShareSlippage raises error for zero bar volume."""
    model = VolumeShareSlippage()

    with pytest.raises(ValueError, match="Bar volume cannot be zero"):
        model.calculate(
            buy_order,
            Decimal("100.00"),
            Decimal("1000"),
            Decimal("0"),  # Zero volume
        )


def test_asymmetric_slippage_buy(buy_order):
    """Test AsymmetricSlippage for buy order."""
    model = AsymmetricSlippage(
        buy_model=FixedBasisPointsSlippage(Decimal("10")),  # 0.1% on buys
        sell_model=FixedBasisPointsSlippage(Decimal("15")),  # 0.15% on sells
    )

    execution_price = model.calculate(buy_order, Decimal("100.00"))

    # Uses buy model: 100 × 1.001 = 100.10
    assert execution_price == Decimal("100.10")


def test_asymmetric_slippage_sell(sell_order):
    """Test AsymmetricSlippage for sell order."""
    model = AsymmetricSlippage(
        buy_model=FixedBasisPointsSlippage(Decimal("10")),  # 0.1% on buys
        sell_model=FixedBasisPointsSlippage(Decimal("15")),  # 0.15% on sells
    )

    execution_price = model.calculate(sell_order, Decimal("100.00"))

    # Uses sell model: 100 × 0.9985 = 99.85
    assert execution_price == Decimal("99.85")


def test_slippage_worsens_execution(buy_order, sell_order):
    """Property: Slippage must make execution worse."""
    models = [
        FixedSlippage(Decimal("0.10")),
        FixedBasisPointsSlippage(Decimal("10")),
    ]

    market_price = Decimal("100.00")

    for model in models:
        # Buy: execution price > market price
        buy_execution = model.calculate(buy_order, market_price)
        assert buy_execution > market_price, f"{model} improved buy execution"

        # Sell: execution price < market price
        sell_execution = model.calculate(sell_order, market_price)
        assert sell_execution < market_price, f"{model} improved sell execution"
