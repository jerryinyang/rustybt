"""Comprehensive tests for commission models (Story 4.4).

Tests cover:
- Per-share commission calculation
- Percentage commission calculation
- Tiered commission with volume discounts
- Maker/taker commission differentiation
- Minimum commission enforcement
- Volume tracker month reset logic
- Property-based tests
- Integration with execution engine
"""

from decimal import Decimal

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.finance.commission import (
    CommissionConfigurationError,
    CommissionResult,
    MakerTakerCommission,
    PercentageCommission,
    PerShareCommission,
    TieredCommission,
    VolumeTracker,
)

# ============================================================================
# Test Fixtures
# ============================================================================


class MockAsset:
    """Mock asset for testing."""

    def __init__(self, symbol: str):
        self.symbol = symbol


class MockOrder:
    """Mock order for testing."""

    def __init__(
        self,
        id: str,
        asset: MockAsset,
        amount: Decimal,
        order_type: str = "market",
        immediate_fill: bool | None = None,
    ):
        self.id = id
        self.asset = asset
        self.amount = amount
        self.order_type = order_type
        self.immediate_fill = immediate_fill


@pytest.fixture
def mock_asset():
    """Create mock asset."""
    return MockAsset(symbol="AAPL")


@pytest.fixture
def current_time():
    """Create test timestamp."""
    return pd.Timestamp("2023-01-01 10:00:00")


# ============================================================================
# Unit Tests - PerShareCommission
# ============================================================================


def test_per_share_commission_calculation(mock_asset, current_time):
    """PerShareCommission calculates fee based on share count."""
    model = PerShareCommission(cost_per_share=Decimal("0.005"), min_commission=Decimal("1.00"))

    order = MockOrder(id="order-1", asset=mock_asset, amount=Decimal("100"))

    result = model.calculate_commission(
        order, fill_price=Decimal("150.00"), fill_quantity=Decimal("100"), current_time=current_time
    )

    # Commission = 100 shares × $0.005 = $0.50
    # Minimum = $1.00, so commission = $1.00
    assert result.commission == Decimal("1.00")
    assert result.model_name == "PerShareCommission"
    assert result.metadata["minimum_applied"] is True


def test_per_share_commission_above_minimum(mock_asset, current_time):
    """PerShareCommission above minimum threshold."""
    model = PerShareCommission(cost_per_share=Decimal("0.005"), min_commission=Decimal("1.00"))

    order = MockOrder(id="order-2", asset=mock_asset, amount=Decimal("1000"))

    result = model.calculate_commission(
        order,
        fill_price=Decimal("150.00"),
        fill_quantity=Decimal("1000"),
        current_time=current_time,
    )

    # Commission = 1000 shares × $0.005 = $5.00 (above minimum)
    assert result.commission == Decimal("5.00")
    assert result.metadata["minimum_applied"] is False


def test_per_share_commission_handles_negative_quantity(mock_asset, current_time):
    """PerShareCommission handles negative quantities (sell orders)."""
    model = PerShareCommission(cost_per_share=Decimal("0.005"), min_commission=Decimal("1.00"))

    order = MockOrder(id="order-3", asset=mock_asset, amount=Decimal("-500"))

    result = model.calculate_commission(
        order,
        fill_price=Decimal("150.00"),
        fill_quantity=Decimal("-500"),
        current_time=current_time,
    )

    # Commission = 500 shares × $0.005 = $2.50
    assert result.commission == Decimal("2.50")


# ============================================================================
# Unit Tests - PercentageCommission
# ============================================================================


def test_percentage_commission_calculation(mock_asset, current_time):
    """PercentageCommission calculates fee as percentage of trade value."""
    model = PercentageCommission(percentage=Decimal("0.001"), min_commission=Decimal("0"))  # 0.1%

    order = MockOrder(id="order-4", asset=mock_asset, amount=Decimal("100"))

    result = model.calculate_commission(
        order, fill_price=Decimal("150.00"), fill_quantity=Decimal("100"), current_time=current_time
    )

    # Trade value = 100 × $150 = $15,000
    # Commission = $15,000 × 0.001 = $15.00
    assert result.commission == Decimal("15.00")
    assert result.model_name == "PercentageCommission"


def test_percentage_commission_minimum_enforced(mock_asset, current_time):
    """PercentageCommission enforces minimum commission."""
    model = PercentageCommission(percentage=Decimal("0.001"), min_commission=Decimal("5.00"))

    order = MockOrder(id="order-5", asset=mock_asset, amount=Decimal("10"))

    result = model.calculate_commission(
        order, fill_price=Decimal("10.00"), fill_quantity=Decimal("10"), current_time=current_time
    )

    # Trade value = 10 × $10 = $100
    # Commission = $100 × 0.001 = $0.10
    # Minimum = $5.00, so commission = $5.00
    assert result.commission == Decimal("5.00")
    assert result.metadata["minimum_applied"] is True


def test_percentage_commission_metadata(mock_asset, current_time):
    """PercentageCommission includes basis points in metadata."""
    model = PercentageCommission(percentage=Decimal("0.001"), min_commission=Decimal("0"))

    order = MockOrder(id="order-6", asset=mock_asset, amount=Decimal("100"))

    result = model.calculate_commission(
        order, fill_price=Decimal("100.00"), fill_quantity=Decimal("100"), current_time=current_time
    )

    # 0.001 = 0.1% = 10 basis points
    # Check that bps is present and converts to 10
    assert Decimal(result.metadata["percentage_bps"]) == Decimal("10")


# ============================================================================
# Unit Tests - VolumeTracker
# ============================================================================


def test_volume_tracker_month_reset():
    """VolumeTracker resets volume at month boundaries."""
    tracker = VolumeTracker()

    # Add volume in January
    tracker.add_volume(Decimal("50000"), pd.Timestamp("2023-01-15"))
    jan_volume = tracker.get_monthly_volume(pd.Timestamp("2023-01-20"))
    assert jan_volume == Decimal("50000")

    # Check volume in February (should reset)
    feb_volume = tracker.get_monthly_volume(pd.Timestamp("2023-02-01"))
    assert feb_volume == Decimal("0")

    # Add volume in February
    tracker.add_volume(Decimal("30000"), pd.Timestamp("2023-02-05"))
    feb_volume_after = tracker.get_monthly_volume(pd.Timestamp("2023-02-10"))
    assert feb_volume_after == Decimal("30000")

    # January volume should still be stored
    jan_volume_still = tracker.monthly_volumes.get("2023-01")
    assert jan_volume_still == Decimal("50000")


def test_volume_tracker_accumulates_within_month():
    """VolumeTracker accumulates volume within same month."""
    tracker = VolumeTracker()

    tracker.add_volume(Decimal("10000"), pd.Timestamp("2023-01-01"))
    tracker.add_volume(Decimal("20000"), pd.Timestamp("2023-01-10"))
    tracker.add_volume(Decimal("15000"), pd.Timestamp("2023-01-20"))

    total_volume = tracker.get_monthly_volume(pd.Timestamp("2023-01-25"))
    assert total_volume == Decimal("45000")


# ============================================================================
# Unit Tests - TieredCommission
# ============================================================================


def test_tiered_commission_volume_discount(mock_asset):
    """TieredCommission applies volume discounts."""
    tiers = {
        Decimal("0"): Decimal("0.001"),  # 0.1% base
        Decimal("100000"): Decimal("0.0005"),  # 0.05% after $100k
        Decimal("1000000"): Decimal("0.0002"),  # 0.02% after $1M
    }

    model = TieredCommission(tiers=tiers)

    order = MockOrder(id="order-7", asset=mock_asset, amount=Decimal("1000"))

    # First trade: start at base tier (0.1%)
    result1 = model.calculate_commission(
        order,
        fill_price=Decimal("50.00"),
        fill_quantity=Decimal("1000"),
        current_time=pd.Timestamp("2023-01-01 10:00"),
    )

    # Trade value = 1000 × $50 = $50,000
    # Commission = $50,000 × 0.001 = $50.00
    assert result1.commission == Decimal("50.00")
    assert result1.tier_applied == "tier_0"

    # Second trade: same month, now at $50k volume, still tier_0
    result2 = model.calculate_commission(
        order,
        fill_price=Decimal("50.00"),
        fill_quantity=Decimal("1000"),
        current_time=pd.Timestamp("2023-01-01 11:00"),
    )
    assert result2.tier_applied == "tier_0"

    # Third trade: after crossing $100k threshold
    order2 = MockOrder(id="order-8", asset=mock_asset, amount=Decimal("100"))
    result3 = model.calculate_commission(
        order2,
        fill_price=Decimal("50.00"),
        fill_quantity=Decimal("100"),
        current_time=pd.Timestamp("2023-01-01 12:00"),
    )

    # Now at tier_100000 (0.05%)
    # Trade value = 100 × $50 = $5,000
    # Commission = $5,000 × 0.0005 = $2.50
    assert result3.commission == Decimal("2.50")
    assert result3.tier_applied == "tier_100000"


def test_tiered_commission_resets_monthly(mock_asset):
    """TieredCommission resets tiers at month boundaries."""
    tiers = {
        Decimal("0"): Decimal("0.001"),
        Decimal("100000"): Decimal("0.0005"),
    }

    model = TieredCommission(tiers=tiers)

    order = MockOrder(id="order-9", asset=mock_asset, amount=Decimal("10000"))

    # Build up volume in January
    for i in range(12):
        model.calculate_commission(
            order,
            fill_price=Decimal("10.00"),
            fill_quantity=Decimal("10000"),
            current_time=pd.Timestamp(f"2023-01-{i + 1:02d} 10:00"),
        )

    # Should be at tier_100000
    assert model.volume_tracker.get_monthly_volume(pd.Timestamp("2023-01-31")) >= Decimal("100000")

    # New month: back to tier_0
    result = model.calculate_commission(
        order,
        fill_price=Decimal("10.00"),
        fill_quantity=Decimal("10000"),
        current_time=pd.Timestamp("2023-02-01 10:00"),
    )

    # Trade value = 10000 × $10 = $100,000
    # Commission = $100,000 × 0.001 = $100.00 (tier_0 rate)
    assert result.tier_applied == "tier_0"


def test_tiered_commission_empty_tiers_raises_error():
    """TieredCommission raises error on empty tiers."""
    with pytest.raises(CommissionConfigurationError, match="Tiers dictionary cannot be empty"):
        TieredCommission(tiers={})


# ============================================================================
# Unit Tests - MakerTakerCommission
# ============================================================================


def test_maker_taker_commission_maker(mock_asset, current_time):
    """MakerTakerCommission applies maker rate for limit orders."""
    model = MakerTakerCommission(
        maker_rate=Decimal("0.0002"),  # 0.02% maker
        taker_rate=Decimal("0.0004"),  # 0.04% taker
        min_commission=Decimal("0"),
    )

    # Limit order that rested (maker)
    order = MockOrder(
        id="order-10",
        asset=mock_asset,
        amount=Decimal("0.1"),
        order_type="limit",
        immediate_fill=False,
    )

    result = model.calculate_commission(
        order,
        fill_price=Decimal("30000.00"),
        fill_quantity=Decimal("0.1"),
        current_time=current_time,
    )

    # Trade value = 0.1 × $30,000 = $3,000
    # Maker commission = $3,000 × 0.0002 = $0.60
    assert result.commission == Decimal("0.60")
    assert result.maker_taker == "maker"
    assert result.model_name == "MakerTakerCommission"


def test_maker_taker_commission_taker(mock_asset, current_time):
    """MakerTakerCommission applies taker rate for market orders."""
    model = MakerTakerCommission(
        maker_rate=Decimal("0.0002"), taker_rate=Decimal("0.0004"), min_commission=Decimal("0")
    )

    # Market order (taker)
    order = MockOrder(id="order-11", asset=mock_asset, amount=Decimal("0.1"), order_type="market")

    result = model.calculate_commission(
        order,
        fill_price=Decimal("30000.00"),
        fill_quantity=Decimal("0.1"),
        current_time=current_time,
    )

    # Trade value = 0.1 × $30,000 = $3,000
    # Taker commission = $3,000 × 0.0004 = $1.20
    assert result.commission == Decimal("1.20")
    assert result.maker_taker == "taker"


def test_maker_rebate(mock_asset, current_time):
    """MakerTakerCommission can have negative commission (rebate)."""
    model = MakerTakerCommission(
        maker_rate=Decimal("-0.0001"),  # -0.01% maker rebate
        taker_rate=Decimal("0.0004"),
        min_commission=Decimal("0"),
    )

    order = MockOrder(
        id="order-12",
        asset=mock_asset,
        amount=Decimal("1.0"),
        order_type="limit",
        immediate_fill=False,
    )

    result = model.calculate_commission(
        order,
        fill_price=Decimal("30000.00"),
        fill_quantity=Decimal("1.0"),
        current_time=current_time,
    )

    # Trade value = 1.0 × $30,000 = $30,000
    # Maker rebate = $30,000 × -0.0001 = -$3.00 (receive $3)
    assert result.commission == Decimal("-3.00")
    assert result.metadata["is_rebate"] is True


def test_maker_minimum_not_applied_to_rebate(mock_asset, current_time):
    """MakerTakerCommission does not apply minimum to negative commission."""
    model = MakerTakerCommission(
        maker_rate=Decimal("-0.0001"),
        taker_rate=Decimal("0.0004"),
        min_commission=Decimal("1.00"),
    )

    order = MockOrder(
        id="order-13",
        asset=mock_asset,
        amount=Decimal("1.0"),
        order_type="limit",
        immediate_fill=False,
    )

    result = model.calculate_commission(
        order,
        fill_price=Decimal("30000.00"),
        fill_quantity=Decimal("1.0"),
        current_time=current_time,
    )

    # Rebate should not be subject to minimum
    assert result.commission < Decimal("0")
    assert result.metadata["minimum_applied"] is False


# ============================================================================
# Property-Based Tests
# ============================================================================


@given(
    quantity=st.decimals(
        min_value=Decimal("1"), max_value=Decimal("10000"), allow_nan=False, allow_infinity=False
    ),
    price=st.decimals(
        min_value=Decimal("1"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False
    ),
    rate=st.decimals(
        min_value=Decimal("0"), max_value=Decimal("0.01"), allow_nan=False, allow_infinity=False
    ),
)
def test_commission_never_negative_for_positive_rates(quantity, price, rate):
    """Property: Commission is never negative for positive rates."""
    model = PercentageCommission(percentage=rate, min_commission=Decimal("0"))

    asset = MockAsset(symbol="TEST")
    order = MockOrder(id="test", asset=asset, amount=quantity)

    result = model.calculate_commission(order, price, quantity, pd.Timestamp("2023-01-01"))

    # Property: Non-negative commission for positive rates
    assert result.commission >= Decimal("0")


@given(
    quantity=st.decimals(
        min_value=Decimal("1"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False
    ),
    price=st.decimals(
        min_value=Decimal("10"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False
    ),
    percentage=st.decimals(
        min_value=Decimal("0.0001"),
        max_value=Decimal("0.05"),
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_commission_never_exceeds_trade_value(quantity, price, percentage):
    """Property: Commission should be less than trade value (sanity check)."""
    model = PercentageCommission(percentage=percentage, min_commission=Decimal("0"))

    asset = MockAsset(symbol="TEST")
    order = MockOrder(id="test", asset=asset, amount=quantity)

    result = model.calculate_commission(order, price, quantity, pd.Timestamp("2023-01-01"))

    trade_value = price * quantity

    # Property: Commission should be reasonable (< 10% of trade value)
    assert result.commission <= trade_value * Decimal("0.10")


@given(
    cost_per_share=st.decimals(
        min_value=Decimal("0.001"),
        max_value=Decimal("0.01"),
        allow_nan=False,
        allow_infinity=False,
    ),
    min_commission=st.decimals(
        min_value=Decimal("0"), max_value=Decimal("10"), allow_nan=False, allow_infinity=False
    ),
)
def test_minimum_commission_always_enforced(cost_per_share, min_commission):
    """Property: Minimum commission is always enforced."""
    model = PerShareCommission(cost_per_share=cost_per_share, min_commission=min_commission)

    asset = MockAsset(symbol="TEST")
    # Small order (likely below minimum)
    order = MockOrder(id="test", asset=asset, amount=Decimal("10"))

    result = model.calculate_commission(
        order, Decimal("100"), Decimal("10"), pd.Timestamp("2023-01-01")
    )

    # Property: Commission is at least minimum
    assert result.commission >= min_commission


# ============================================================================
# Integration Tests
# ============================================================================


def test_commission_integration_with_execution_engine(mock_asset, current_time):
    """Integration test: Commission applied in execution pipeline."""
    from rustybt.finance.execution import ExecutionEngine

    # Create execution engine with commission model
    commission_model = PerShareCommission(
        cost_per_share=Decimal("0.005"), min_commission=Decimal("1.00")
    )

    execution_engine = ExecutionEngine(commission_model=commission_model)

    order = MockOrder(id="integration-1", asset=mock_asset, amount=Decimal("100"))

    # Provide bar data to avoid data portal requirement
    bar_data = {"close": 150.00, "volume": 100000}

    # Execute order
    result = execution_engine.execute_order(order, current_time, bar_data=bar_data)

    # Verify commission was calculated and included in result
    assert result.commission is not None
    assert result.commission.commission == Decimal("1.00")  # Minimum applied
    assert result.commission.model_name == "PerShareCommission"


def test_real_world_broker_profiles(mock_asset, current_time):
    """Integration test: Real broker commission profiles."""
    # Test Interactive Brokers
    ib_model = PerShareCommission(cost_per_share=Decimal("0.005"), min_commission=Decimal("1.00"))

    # Small IB trade (hits minimum)
    ib_order = MockOrder(id="ib-1", asset=mock_asset, amount=Decimal("50"))
    ib_result = ib_model.calculate_commission(ib_order, Decimal("100"), Decimal("50"), current_time)
    assert ib_result.commission == Decimal("1.00")

    # Large IB trade (above minimum)
    ib_order_large = MockOrder(id="ib-2", asset=mock_asset, amount=Decimal("1000"))
    ib_result_large = ib_model.calculate_commission(
        ib_order_large, Decimal("100"), Decimal("1000"), current_time
    )
    assert ib_result_large.commission == Decimal("5.00")  # 1000 × $0.005

    # Test Binance
    binance_model = MakerTakerCommission(maker_rate=Decimal("0.001"), taker_rate=Decimal("0.001"))

    # Binance crypto trade
    btc_asset = MockAsset(symbol="BTC-USD")
    binance_order = MockOrder(
        id="binance-1", asset=btc_asset, amount=Decimal("0.1"), order_type="market"
    )
    binance_result = binance_model.calculate_commission(
        binance_order, Decimal("30000"), Decimal("0.1"), current_time
    )
    # Trade value = 0.1 × $30,000 = $3,000
    # Commission = $3,000 × 0.001 = $3.00
    assert binance_result.commission == Decimal("3.00")
    assert binance_result.maker_taker == "taker"


def test_tiered_commission_with_multiple_assets(current_time):
    """Integration test: Tiered commission tracking across multiple assets."""
    tiers = {
        Decimal("0"): Decimal("0.001"),
        Decimal("100000"): Decimal("0.0005"),
    }

    model = TieredCommission(tiers=tiers)

    # Trade multiple assets, volume should accumulate
    assets = [MockAsset(symbol=f"STOCK{i}") for i in range(5)]

    total_commission = Decimal("0")

    for i, asset in enumerate(assets):
        order = MockOrder(id=f"multi-{i}", asset=asset, amount=Decimal("5000"))

        result = model.calculate_commission(
            order,
            fill_price=Decimal("20.00"),
            fill_quantity=Decimal("5000"),
            current_time=current_time,
        )

        total_commission += result.commission

    # After trading 5 × 5000 × $20 = $500k, should be at tier_100000
    assert model.volume_tracker.get_monthly_volume(current_time) >= Decimal("100000")


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_zero_quantity_commission(mock_asset, current_time):
    """Commission calculation with zero quantity."""
    model = PercentageCommission(percentage=Decimal("0.001"), min_commission=Decimal("1.00"))

    order = MockOrder(id="zero-qty", asset=mock_asset, amount=Decimal("0"))

    result = model.calculate_commission(
        order, fill_price=Decimal("100.00"), fill_quantity=Decimal("0"), current_time=current_time
    )

    # Zero quantity should result in minimum commission
    assert result.commission == Decimal("1.00")


def test_very_large_trade_commission(mock_asset, current_time):
    """Commission calculation with very large trade."""
    model = PercentageCommission(percentage=Decimal("0.001"), min_commission=Decimal("0"))

    order = MockOrder(id="large-trade", asset=mock_asset, amount=Decimal("1000000"))

    result = model.calculate_commission(
        order,
        fill_price=Decimal("10000.00"),
        fill_quantity=Decimal("1000000"),
        current_time=current_time,
    )

    # Trade value = 1M × $10,000 = $10B
    # Commission = $10B × 0.001 = $10M
    expected_commission = Decimal("10000000000") * Decimal("0.001")
    assert result.commission == expected_commission


def test_commission_result_frozen():
    """CommissionResult is immutable (frozen dataclass)."""
    result = CommissionResult(
        commission=Decimal("10.00"),
        model_name="Test",
        metadata={"test": "value"},
    )

    # Attempt to modify should raise error
    with pytest.raises((AttributeError, Exception)):
        result.commission = Decimal("20.00")
