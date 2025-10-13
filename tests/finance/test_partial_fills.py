"""
Tests for partial fill models (Story 4.2).

This module tests partial fill simulation including:
- Volume-based fill logic
- Multi-bar fill persistence
- Order state tracking
- Average fill price calculation
- Market impact modeling
"""

from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from rustybt.finance.execution import (
    AggressiveFillModel,
    BalancedFillModel,
    ConservativeFillModel,
    Order,
    OrderState,
    OrderTracker,
    PartialFill,
    VolumeBasedFillModel,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_asset():
    """Create mock asset for testing."""
    asset = Mock()
    asset.symbol = "AAPL"
    asset.sid = 1
    return asset


@pytest.fixture
def mock_data_portal():
    """Create mock data portal for testing."""
    portal = MagicMock()
    # Default: Return volume and price
    portal.get_volume.return_value = Decimal("10000")
    portal.get_price.return_value = Decimal("50.00")
    return portal


# ============================================================================
# Unit Tests - PartialFill
# ============================================================================


def test_partial_fill_value_calculation():
    """PartialFill calculates value correctly."""
    fill = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:00"),
        quantity=Decimal("100"),
        price=Decimal("50.00"),
    )

    assert fill.value == Decimal("5000.00")
    assert fill.quantity == Decimal("100")
    assert fill.price == Decimal("50.00")


def test_partial_fill_frozen():
    """PartialFill is immutable (frozen dataclass)."""
    fill = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:00"),
        quantity=Decimal("100"),
        price=Decimal("50.00"),
    )

    with pytest.raises(AttributeError):
        fill.quantity = Decimal("200")


# ============================================================================
# Unit Tests - Order
# ============================================================================


def test_order_initialization(mock_asset):
    """Order initializes with correct default values."""
    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("1000"),
        order_type="market",
    )

    assert order.id == "order-1"
    assert order.asset == mock_asset
    assert order.amount == Decimal("1000")
    assert order.order_type == "market"
    assert order.state == OrderState.NEW
    assert order.partial_fills == []
    assert order.filled_quantity == Decimal("0")
    assert order.remaining_quantity == Decimal("1000")
    assert not order.is_fully_filled
    assert order.average_fill_price is None


def test_order_filled_quantity_calculation(mock_asset):
    """Order correctly calculates filled quantity."""
    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("1000"),
        order_type="market",
    )

    fill1 = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:00"),
        quantity=Decimal("300"),
        price=Decimal("50.00"),
    )
    fill2 = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:01"),
        quantity=Decimal("400"),
        price=Decimal("51.00"),
    )

    order.add_fill(fill1)
    assert order.filled_quantity == Decimal("300")
    assert order.remaining_quantity == Decimal("700")
    assert order.state == OrderState.PARTIALLY_FILLED

    order.add_fill(fill2)
    assert order.filled_quantity == Decimal("700")
    assert order.remaining_quantity == Decimal("300")
    assert order.state == OrderState.PARTIALLY_FILLED


def test_order_fully_filled(mock_asset):
    """Order transitions to FILLED state when fully filled."""
    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("1000"),
        order_type="market",
    )

    fill = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:00"),
        quantity=Decimal("1000"),
        price=Decimal("50.00"),
    )

    order.add_fill(fill)

    assert order.is_fully_filled
    assert order.state == OrderState.FILLED
    assert order.remaining_quantity == Decimal("0")


def test_order_average_fill_price_calculation(mock_asset):
    """Order calculates VWAP correctly across multiple fills."""
    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("200"),
        order_type="market",
    )

    # Add partial fills at different prices
    fill1 = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:00"),
        quantity=Decimal("100"),
        price=Decimal("50.00"),
    )
    fill2 = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:01"),
        quantity=Decimal("100"),
        price=Decimal("52.00"),
    )

    order.add_fill(fill1)
    order.add_fill(fill2)

    # VWAP = (100 × 50 + 100 × 52) / 200 = 51.00
    expected_vwap = Decimal("51.00")
    assert order.average_fill_price == expected_vwap


def test_order_add_fill_exceeds_amount(mock_asset):
    """Order.add_fill raises error if fill exceeds order amount."""
    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    fill = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:00"),
        quantity=Decimal("150"),
        price=Decimal("50.00"),
    )

    with pytest.raises(ValueError, match="would exceed remaining order quantity"):
        order.add_fill(fill)


def test_order_sell_amount_handling(mock_asset):
    """Order handles negative amounts (sell orders) correctly."""
    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("-500"),  # Sell order
        order_type="market",
    )

    assert order.remaining_quantity == Decimal("500")  # Absolute value

    fill = PartialFill(
        timestamp=pd.Timestamp("2023-01-01 10:00"),
        quantity=Decimal("300"),
        price=Decimal("50.00"),
    )

    order.add_fill(fill)
    assert order.remaining_quantity == Decimal("200")


# ============================================================================
# Unit Tests - VolumeBasedFillModel
# ============================================================================


def test_volume_based_fill_model_initialization():
    """VolumeBasedFillModel initializes with correct defaults."""
    model = VolumeBasedFillModel()

    assert model.fill_ratio == Decimal("0.10")
    assert model.market_impact_factor == Decimal("0.01")


def test_volume_based_fill_model_custom_params():
    """VolumeBasedFillModel accepts custom parameters."""
    model = VolumeBasedFillModel(
        fill_ratio=Decimal("0.20"),
        market_impact_factor=Decimal("0.02"),
    )

    assert model.fill_ratio == Decimal("0.20")
    assert model.market_impact_factor == Decimal("0.02")


def test_volume_based_fill_model_invalid_fill_ratio():
    """VolumeBasedFillModel raises error for invalid fill_ratio."""
    with pytest.raises(ValueError, match="fill_ratio must be between 0 and 1"):
        VolumeBasedFillModel(fill_ratio=Decimal("1.5"))

    with pytest.raises(ValueError, match="fill_ratio must be between 0 and 1"):
        VolumeBasedFillModel(fill_ratio=Decimal("-0.1"))


def test_volume_based_fill_model_invalid_market_impact():
    """VolumeBasedFillModel raises error for negative market_impact_factor."""
    with pytest.raises(ValueError, match="market_impact_factor must be non-negative"):
        VolumeBasedFillModel(market_impact_factor=Decimal("-0.01"))


def test_small_order_fills_completely(mock_asset):
    """Small order (<10% volume) fills completely in one bar."""
    model = VolumeBasedFillModel(fill_ratio=Decimal("0.10"))

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    bar_volume = Decimal("10000")
    bar_price = Decimal("50.00")
    current_time = pd.Timestamp("2023-01-01 10:00")

    partial_fill = model.calculate_fill(order, bar_volume, bar_price, current_time)

    assert partial_fill is not None
    assert partial_fill.quantity == Decimal("100")
    assert partial_fill.timestamp == current_time
    # Small order should have minimal market impact
    assert partial_fill.price >= bar_price


def test_large_order_fills_partially(mock_asset):
    """Large order (>10% volume) fills partially."""
    model = VolumeBasedFillModel(fill_ratio=Decimal("0.10"))

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("2000"),
        order_type="market",
    )

    bar_volume = Decimal("10000")
    bar_price = Decimal("50.00")
    current_time = pd.Timestamp("2023-01-01 10:00")

    # First bar: fill 10% of volume = 1,000 shares
    partial_fill_1 = model.calculate_fill(order, bar_volume, bar_price, current_time)

    assert partial_fill_1 is not None
    assert partial_fill_1.quantity == Decimal("1000")
    order.add_fill(partial_fill_1)

    assert not order.is_fully_filled
    assert order.remaining_quantity == Decimal("1000")

    # Second bar: fill remaining 1,000 shares
    current_time_2 = pd.Timestamp("2023-01-01 10:01")
    partial_fill_2 = model.calculate_fill(order, bar_volume, bar_price, current_time_2)

    assert partial_fill_2 is not None
    assert partial_fill_2.quantity == Decimal("1000")
    order.add_fill(partial_fill_2)

    assert order.is_fully_filled


def test_market_impact_calculation_buy_order(mock_asset):
    """Market impact increases price for buy orders."""
    model = VolumeBasedFillModel(
        fill_ratio=Decimal("0.10"),
        market_impact_factor=Decimal("0.01"),
    )

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("1000"),  # Buy order (positive)
        order_type="market",
    )

    bar_volume = Decimal("10000")
    bar_price = Decimal("50.00")
    current_time = pd.Timestamp("2023-01-01 10:00")

    partial_fill = model.calculate_fill(order, bar_volume, bar_price, current_time)

    # Order is 1000 / 10000 = 10% of volume
    # Market impact = 0.01 * 0.10 = 0.001 = 0.1%
    # Fill price = 50.00 * (1 + 0.001) = 50.05
    expected_price = Decimal("50.05")

    assert partial_fill is not None
    assert partial_fill.price == expected_price


def test_market_impact_calculation_sell_order(mock_asset):
    """Market impact decreases price for sell orders."""
    model = VolumeBasedFillModel(
        fill_ratio=Decimal("0.10"),
        market_impact_factor=Decimal("0.01"),
    )

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("-1000"),  # Sell order (negative)
        order_type="market",
    )

    bar_volume = Decimal("10000")
    bar_price = Decimal("50.00")
    current_time = pd.Timestamp("2023-01-01 10:00")

    partial_fill = model.calculate_fill(order, bar_volume, bar_price, current_time)

    # Market impact = 0.01 * 0.10 = 0.001 = 0.1%
    # Fill price = 50.00 * (1 - 0.001) = 49.95
    expected_price = Decimal("49.95")

    assert partial_fill is not None
    assert partial_fill.price == expected_price


def test_no_fill_when_no_volume(mock_asset):
    """No fill when bar volume is zero."""
    model = VolumeBasedFillModel()

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    bar_volume = Decimal("0")
    bar_price = Decimal("50.00")
    current_time = pd.Timestamp("2023-01-01 10:00")

    partial_fill = model.calculate_fill(order, bar_volume, bar_price, current_time)

    assert partial_fill is None


# ============================================================================
# Unit Tests - Fill Model Variants
# ============================================================================


def test_aggressive_fill_model_parameters():
    """AggressiveFillModel uses higher fill ratio and market impact."""
    model = AggressiveFillModel()

    assert model.fill_ratio == Decimal("0.25")
    assert model.market_impact_factor == Decimal("0.02")


def test_conservative_fill_model_parameters():
    """ConservativeFillModel uses lower fill ratio and market impact."""
    model = ConservativeFillModel()

    assert model.fill_ratio == Decimal("0.05")
    assert model.market_impact_factor == Decimal("0.005")


def test_balanced_fill_model_parameters():
    """BalancedFillModel uses moderate fill ratio and market impact."""
    model = BalancedFillModel()

    assert model.fill_ratio == Decimal("0.10")
    assert model.market_impact_factor == Decimal("0.01")


def test_aggressive_model_fills_faster(mock_asset):
    """AggressiveFillModel fills larger quantity per bar."""
    aggressive_model = AggressiveFillModel()
    balanced_model = BalancedFillModel()

    order_aggressive = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("5000"),
        order_type="market",
    )
    order_balanced = Order(
        id="order-2",
        asset=mock_asset,
        amount=Decimal("5000"),
        order_type="market",
    )

    bar_volume = Decimal("10000")
    bar_price = Decimal("50.00")
    current_time = pd.Timestamp("2023-01-01 10:00")

    fill_aggressive = aggressive_model.calculate_fill(
        order_aggressive, bar_volume, bar_price, current_time
    )
    fill_balanced = balanced_model.calculate_fill(
        order_balanced, bar_volume, bar_price, current_time
    )

    # Aggressive: 25% of 10000 = 2500
    # Balanced: 10% of 10000 = 1000
    assert fill_aggressive.quantity == Decimal("2500")
    assert fill_balanced.quantity == Decimal("1000")
    assert fill_aggressive.quantity > fill_balanced.quantity


# ============================================================================
# Unit Tests - OrderTracker
# ============================================================================


def test_order_tracker_initialization():
    """OrderTracker initializes with correct state."""
    model = BalancedFillModel()
    tracker = OrderTracker(model)

    assert tracker.fill_model == model
    assert tracker.open_orders == {}
    assert tracker.get_open_orders() == []


def test_order_tracker_add_order(mock_asset):
    """OrderTracker.add_order adds order to open orders."""
    tracker = OrderTracker(BalancedFillModel())

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("1000"),
        order_type="market",
    )

    current_time = pd.Timestamp("2023-01-01 10:00")
    tracker.add_order(order, current_time)

    assert order.id in tracker.open_orders
    assert order.created_at == current_time
    assert len(tracker.get_open_orders()) == 1


def test_order_tracker_process_bar_fills_order(mock_asset, mock_data_portal):
    """OrderTracker.process_bar fills order when volume available."""
    tracker = OrderTracker(BalancedFillModel())

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    current_time = pd.Timestamp("2023-01-01 10:00")
    tracker.add_order(order, current_time)

    # Configure mock data portal
    mock_data_portal.get_volume.return_value = Decimal("10000")
    mock_data_portal.get_price.return_value = Decimal("50.00")

    # Process bar - order should fill completely (100 < 10% of 10000)
    filled_orders = tracker.process_bar(current_time, mock_data_portal)

    assert len(filled_orders) == 1
    assert filled_orders[0].id == "order-1"
    assert filled_orders[0].is_fully_filled
    assert len(tracker.get_open_orders()) == 0


def test_order_tracker_multi_bar_fill(mock_asset, mock_data_portal):
    """OrderTracker persists partially filled orders across bars."""
    tracker = OrderTracker(BalancedFillModel())

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("2000"),
        order_type="market",
    )

    current_time_1 = pd.Timestamp("2023-01-01 10:00")
    tracker.add_order(order, current_time_1)

    # Configure mock data portal
    mock_data_portal.get_volume.return_value = Decimal("10000")
    mock_data_portal.get_price.return_value = Decimal("50.00")

    # First bar: partial fill (1000 shares)
    filled_orders_1 = tracker.process_bar(current_time_1, mock_data_portal)

    assert len(filled_orders_1) == 0  # Not fully filled yet
    assert len(tracker.get_open_orders()) == 1
    assert order.filled_quantity == Decimal("1000")
    assert order.state == OrderState.PARTIALLY_FILLED

    # Second bar: complete fill
    current_time_2 = pd.Timestamp("2023-01-01 10:01")
    filled_orders_2 = tracker.process_bar(current_time_2, mock_data_portal)

    assert len(filled_orders_2) == 1
    assert filled_orders_2[0].is_fully_filled
    assert len(tracker.get_open_orders()) == 0


def test_order_tracker_timeout(mock_asset, mock_data_portal):
    """OrderTracker cancels order after timeout."""
    tracker = OrderTracker(BalancedFillModel())

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("1000"),
        order_type="market",
        timeout_bars=5,  # Cancel after 5 bars
    )

    current_time_1 = pd.Timestamp("2023-01-01 10:00")
    tracker.add_order(order, current_time_1)

    # Configure mock to return zero volume (no fills)
    mock_data_portal.get_volume.return_value = Decimal("0")
    mock_data_portal.get_price.return_value = Decimal("50.00")

    # Process 6 bars (exceeds timeout) - need to process AFTER the initial bar
    for i in range(1, 7):  # Start from bar 1 to simulate time passing
        current_time = pd.Timestamp(f"2023-01-01 10:{i:02d}")
        tracker.process_bar(current_time, mock_data_portal)

    # Order should be canceled and removed
    assert len(tracker.get_open_orders()) == 0
    assert order.state == OrderState.CANCELED


def test_order_tracker_cancel_order(mock_asset):
    """OrderTracker.cancel_order cancels open order."""
    tracker = OrderTracker(BalancedFillModel())

    order = Order(
        id="order-1",
        asset=mock_asset,
        amount=Decimal("1000"),
        order_type="market",
    )

    current_time = pd.Timestamp("2023-01-01 10:00")
    tracker.add_order(order, current_time)

    # Cancel order
    canceled_order = tracker.cancel_order("order-1")

    assert canceled_order is not None
    assert canceled_order.id == "order-1"
    assert canceled_order.state == OrderState.CANCELED
    assert len(tracker.get_open_orders()) == 0


def test_order_tracker_cancel_nonexistent_order():
    """OrderTracker.cancel_order returns None for nonexistent order."""
    tracker = OrderTracker(BalancedFillModel())

    canceled_order = tracker.cancel_order("nonexistent")

    assert canceled_order is None


# ============================================================================
# Property-Based Tests
# ============================================================================


@given(
    order_size=st.decimals(
        min_value=Decimal("1"),
        max_value=Decimal("10000"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
    bar_volume=st.decimals(
        min_value=Decimal("1000"),
        max_value=Decimal("100000"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
)
def test_filled_quantity_never_exceeds_order_size(order_size, bar_volume):
    """Property: Cumulative filled quantity never exceeds order size."""
    # Create mock asset inline to avoid fixture issues with hypothesis
    asset = Mock()
    asset.symbol = "AAPL"
    asset.sid = 1

    model = VolumeBasedFillModel(fill_ratio=Decimal("0.10"))

    order = Order(
        id="order-test",
        asset=asset,
        amount=order_size,
        order_type="market",
    )

    bar_price = Decimal("50.00")
    base_time = pd.Timestamp("2023-01-01 10:00:00")

    # Simulate up to 100 bars
    for i in range(100):
        if order.is_fully_filled:
            break

        current_time = base_time + pd.Timedelta(minutes=i)
        partial_fill = model.calculate_fill(order, bar_volume, bar_price, current_time)

        if partial_fill:
            order.add_fill(partial_fill)

    # Property: filled quantity <= order size
    assert order.filled_quantity <= order_size


@given(
    fills=st.lists(
        st.tuples(
            st.decimals(
                min_value=Decimal("1"),
                max_value=Decimal("1000"),
                allow_nan=False,
                allow_infinity=False,
                places=2,
            ),
            st.decimals(
                min_value=Decimal("10"),
                max_value=Decimal("100"),
                allow_nan=False,
                allow_infinity=False,
                places=2,
            ),
        ),
        min_size=2,
        max_size=10,
    )
)
def test_average_price_between_min_max(fills):
    """Property: Average fill price always between min and max fill prices."""
    assume(len(fills) >= 2)

    # Create mock asset inline to avoid fixture issues with hypothesis
    asset = Mock()
    asset.symbol = "AAPL"
    asset.sid = 1

    total_quantity = sum(qty for qty, _ in fills)
    order = Order(
        id="order-test",
        asset=asset,
        amount=total_quantity,
        order_type="market",
    )

    for i, (qty, price) in enumerate(fills):
        partial_fill = PartialFill(
            timestamp=pd.Timestamp(f"2023-01-01 10:{i:02d}"),
            quantity=qty,
            price=price,
        )
        order.add_fill(partial_fill)

    avg_price = order.average_fill_price
    min_price = min(price for _, price in fills)
    max_price = max(price for _, price in fills)

    assert min_price <= avg_price <= max_price


@given(
    fill_ratio=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("0.99"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
    market_impact_factor=st.decimals(
        min_value=Decimal("0.001"),
        max_value=Decimal("0.10"),
        allow_nan=False,
        allow_infinity=False,
        places=3,
    ),
)
def test_volume_based_model_valid_parameters(fill_ratio, market_impact_factor):
    """Property: VolumeBasedFillModel accepts valid parameter ranges."""
    model = VolumeBasedFillModel(
        fill_ratio=fill_ratio,
        market_impact_factor=market_impact_factor,
    )

    assert model.fill_ratio == fill_ratio
    assert model.market_impact_factor == market_impact_factor


# ============================================================================
# Integration Tests
# ============================================================================


def test_integration_multi_bar_fill_realistic_scenario(mock_asset):
    """Integration: Realistic multi-bar fill with volume data."""
    # Simulate filling a 10,000 share order over multiple bars with varying volume

    tracker = OrderTracker(BalancedFillModel())

    order = Order(
        id="order-large",
        asset=mock_asset,
        amount=Decimal("10000"),
        order_type="market",
    )

    # Create mock data portal with varying volume and prices
    data_portal = MagicMock()

    # Define realistic volume and price sequences
    volume_sequence = [
        Decimal("5000"),  # Low volume bar
        Decimal("15000"),  # Normal volume
        Decimal("20000"),  # High volume
        Decimal("10000"),  # Normal volume
        Decimal("8000"),  # Lower volume
        Decimal("12000"),  # Normal volume
    ]

    price_sequence = [
        Decimal("50.00"),
        Decimal("50.10"),
        Decimal("50.05"),
        Decimal("49.95"),
        Decimal("50.20"),
        Decimal("50.15"),
    ]

    current_time = pd.Timestamp("2023-01-01 10:00")
    tracker.add_order(order, current_time)

    for i, (volume, price) in enumerate(zip(volume_sequence, price_sequence, strict=False)):
        data_portal.get_volume.return_value = volume
        data_portal.get_price.return_value = price

        bar_time = pd.Timestamp(f"2023-01-01 10:{i:02d}")
        filled_orders = tracker.process_bar(bar_time, data_portal)

        if filled_orders:
            break

    # With balanced model (10% fill ratio):
    # Bar 0: 500 shares (10% of 5000)
    # Bar 1: 1500 shares (10% of 15000)
    # Bar 2: 2000 shares (10% of 20000)
    # Bar 3: 1000 shares (10% of 10000)
    # Bar 4: 800 shares (10% of 8000)
    # Bar 5: 1200 shares (10% of 12000)
    # Total: 7000 shares - still not filled (need 3 more bars)

    assert order.state in (OrderState.PARTIALLY_FILLED, OrderState.FILLED)
    assert order.filled_quantity > Decimal("0")
    assert len(order.partial_fills) > 0
    assert order.average_fill_price is not None


def test_integration_average_fill_price_degradation_with_size(mock_asset):
    """Integration: Larger orders get worse average prices due to market impact."""
    small_order = Order(
        id="order-small",
        asset=mock_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    large_order = Order(
        id="order-large",
        asset=mock_asset,
        amount=Decimal("1000"),
        order_type="market",
    )

    model = VolumeBasedFillModel(
        fill_ratio=Decimal("0.10"),
        market_impact_factor=Decimal("0.01"),
    )

    bar_volume = Decimal("10000")
    bar_price = Decimal("50.00")
    current_time = pd.Timestamp("2023-01-01 10:00")

    # Fill small order
    small_fill = model.calculate_fill(small_order, bar_volume, bar_price, current_time)
    small_order.add_fill(small_fill)

    # Fill large order (first partial fill)
    large_fill = model.calculate_fill(large_order, bar_volume, bar_price, current_time)
    large_order.add_fill(large_fill)

    # Small order should get better price (less market impact)
    assert small_order.average_fill_price < large_order.average_fill_price
