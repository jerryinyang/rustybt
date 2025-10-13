"""Unit tests for Decimal commission models."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.finance.decimal import (
    CryptoCommission,
    DecimalOrder,
    NoCommission,
    PerDollarCommission,
    PerShareCommission,
    PerTradeCommission,
)


@pytest.fixture
def market_order(equity_asset):
    """Create market order fixture."""
    return DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="market",
    )


@pytest.fixture
def limit_order(equity_asset):
    """Create limit order fixture."""
    return DecimalOrder(
        dt=datetime.now(),
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="limit",
        limit=Decimal("150.00"),
    )


def test_no_commission(market_order):
    """Test NoCommission model returns zero."""
    model = NoCommission()
    commission = model.calculate(market_order, Decimal("150.00"), Decimal("100"))
    assert commission == Decimal("0")


def test_per_share_commission(market_order):
    """Test PerShareCommission calculation."""
    model = PerShareCommission(rate=Decimal("0.005"))
    commission = model.calculate(market_order, Decimal("150.00"), Decimal("100"))

    # 100 shares × $0.005 = $0.50
    assert commission == Decimal("0.50")


def test_per_share_commission_with_minimum(market_order):
    """Test PerShareCommission with minimum."""
    model = PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00"))

    # First fill: 10 shares × $0.005 = $0.05, but minimum is $1.00
    commission = model.calculate(market_order, Decimal("150.00"), Decimal("10"))
    assert commission == Decimal("1.00")


def test_per_share_commission_exceeds_minimum(market_order):
    """Test PerShareCommission when it exceeds minimum."""
    model = PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00"))

    # 300 shares × $0.005 = $1.50 (exceeds minimum)
    commission = model.calculate(market_order, Decimal("150.00"), Decimal("300"))
    assert commission == Decimal("1.50")


def test_per_share_commission_negative_rate():
    """Test PerShareCommission rejects negative rate."""
    with pytest.raises(ValueError, match="Commission rate must be non-negative"):
        PerShareCommission(rate=Decimal("-0.005"))


def test_per_trade_commission(market_order):
    """Test PerTradeCommission charged once."""
    model = PerTradeCommission(cost=Decimal("5.00"))

    # First fill: charge full commission
    commission = model.calculate(market_order, Decimal("150.00"), Decimal("50"))
    assert commission == Decimal("5.00")

    # Simulate order has already paid commission
    market_order.commission = Decimal("5.00")

    # Second fill: no additional commission
    commission = model.calculate(market_order, Decimal("150.00"), Decimal("50"))
    assert commission == Decimal("0")


def test_per_trade_commission_negative_cost():
    """Test PerTradeCommission rejects negative cost."""
    with pytest.raises(ValueError, match="Commission cost must be non-negative"):
        PerTradeCommission(cost=Decimal("-5.00"))


def test_per_dollar_commission(market_order):
    """Test PerDollarCommission calculation."""
    model = PerDollarCommission(rate=Decimal("0.0015"))  # 0.15%

    # 100 shares × $150 = $15,000
    # Commission: $15,000 × 0.0015 = $22.50
    commission = model.calculate(market_order, Decimal("150.00"), Decimal("100"))
    assert commission == Decimal("22.50")


def test_per_dollar_commission_negative_rate():
    """Test PerDollarCommission rejects negative rate."""
    with pytest.raises(ValueError, match="Commission rate must be non-negative"):
        PerDollarCommission(rate=Decimal("-0.0015"))


def test_crypto_commission_maker(limit_order):
    """Test CryptoCommission for maker order (limit)."""
    model = CryptoCommission(
        maker_rate=Decimal("0.001"),  # 0.1%
        taker_rate=Decimal("0.002"),  # 0.2%
    )

    # Limit order is maker
    # 100 × $50,000 = $5,000,000
    # Commission: $5,000,000 × 0.001 = $5,000
    commission = model.calculate(limit_order, Decimal("50000.00"), Decimal("100"))
    assert commission == Decimal("5000.00")


def test_crypto_commission_taker(market_order):
    """Test CryptoCommission for taker order (market)."""
    model = CryptoCommission(
        maker_rate=Decimal("0.001"),  # 0.1%
        taker_rate=Decimal("0.002"),  # 0.2%
    )

    # Market order is taker
    # 100 × $50,000 = $5,000,000
    # Commission: $5,000,000 × 0.002 = $10,000
    commission = model.calculate(market_order, Decimal("50000.00"), Decimal("100"))
    assert commission == Decimal("10000.00")


def test_crypto_commission_fractional_crypto(market_order):
    """Test CryptoCommission with fractional crypto quantities."""
    model = CryptoCommission(
        maker_rate=Decimal("0.001"),
        taker_rate=Decimal("0.002"),
    )

    # 0.00000001 BTC × $50,000 = $0.0005
    # Commission: $0.0005 × 0.002 = $0.000001
    commission = model.calculate(market_order, Decimal("50000.00"), Decimal("0.00000001"))
    assert commission == Decimal("0.000001")


def test_crypto_commission_negative_maker_rate():
    """Test CryptoCommission rejects negative maker rate."""
    with pytest.raises(ValueError, match="Maker rate must be non-negative"):
        CryptoCommission(
            maker_rate=Decimal("-0.001"),
            taker_rate=Decimal("0.002"),
        )


def test_crypto_commission_negative_taker_rate():
    """Test CryptoCommission rejects negative taker rate."""
    with pytest.raises(ValueError, match="Taker rate must be non-negative"):
        CryptoCommission(
            maker_rate=Decimal("0.001"),
            taker_rate=Decimal("-0.002"),
        )


def test_commission_non_negative(market_order):
    """Property: Commission must always be non-negative."""
    models = [
        NoCommission(),
        PerShareCommission(Decimal("0.005")),
        PerTradeCommission(Decimal("5.00")),
        PerDollarCommission(Decimal("0.0015")),
        CryptoCommission(Decimal("0.001"), Decimal("0.002")),
    ]

    for model in models:
        commission = model.calculate(market_order, Decimal("150.00"), Decimal("100"))
        assert commission >= Decimal("0"), f"{model} returned negative commission"
