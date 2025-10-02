"""Tests for order aggregation engine.

Test Coverage:
- Unit tests: Order netting, grouping, fill allocation, commission savings
- Property tests: Aggregation invariants, savings properties
- Integration tests: Multi-strategy portfolio with aggregation
"""

from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rustybt.portfolio.aggregator import (
    OrderAggregator,
    OrderDirection,
)


# Mock order class for testing
class MockOrder:
    """Mock order for testing."""

    def __init__(
        self,
        asset: str,
        amount: Decimal,
        side: str,
        order_type: str = "market",
        limit_price: Decimal | None = None,
    ):
        """Initialize mock order.

        Args:
            asset: Asset symbol
            amount: Order amount (positive)
            side: Order side ("buy" or "sell")
            order_type: Order type ("market" or "limit")
            limit_price: Limit price for limit orders
        """
        self.asset = MockAsset(asset)
        self.amount = amount
        self.side = side
        self.order_type = order_type
        self.limit_price = limit_price
        self.strategy_id = None  # Set by aggregator


class MockAsset:
    """Mock asset for testing."""

    def __init__(self, symbol: str):
        """Initialize mock asset.

        Args:
            symbol: Asset symbol
        """
        self.symbol = symbol

    def __eq__(self, other):
        """Check equality."""
        if isinstance(other, MockAsset):
            return self.symbol == other.symbol
        return False

    def __hash__(self):
        """Hash for use as dict key."""
        return hash(self.symbol)

    def __str__(self):
        """String representation."""
        return self.symbol


def create_order(
    symbol: str,
    amount: Decimal,
    side: str,
    order_type: str = "market",
    limit_price: Decimal | None = None,
) -> MockOrder:
    """Helper to create mock order.

    Args:
        symbol: Asset symbol
        amount: Order amount
        side: Order side ("buy" or "sell")
        order_type: Order type
        limit_price: Limit price

    Returns:
        MockOrder instance
    """
    return MockOrder(symbol, amount, side, order_type, limit_price)


# Unit Tests


def test_simple_two_strategy_netting():
    """Simple netting: 100 buy + 50 sell → 50 net buy."""
    aggregator = OrderAggregator()

    # Strategy A: Buy 100
    # Strategy B: Sell 50
    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("50"), "sell")],
    }

    result = aggregator.aggregate_orders(orders)

    # Should create 1 aggregated order
    assert len(result.aggregated_orders) == 1

    agg_order = result.aggregated_orders[0]

    # Net amount should be +50 (buy)
    assert agg_order.net_amount == Decimal("50")
    assert agg_order.direction == OrderDirection.BUY

    # Should have 2 contributions
    assert len(agg_order.contributions) == 2

    # Verify contributions
    contributions_by_strategy = {
        c.strategy_id: c.contribution_amount for c in agg_order.contributions
    }
    assert contributions_by_strategy["strategy_a"] == Decimal("100")
    assert contributions_by_strategy["strategy_b"] == Decimal("-50")


def test_complex_three_strategy_netting():
    """Complex netting: 100 buy + 80 sell + 30 buy → 50 net buy."""
    aggregator = OrderAggregator()

    # Strategy A: Buy 100
    # Strategy B: Sell 80
    # Strategy C: Buy 30
    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("80"), "sell")],
        "strategy_c": [create_order("AAPL", Decimal("30"), "buy")],
    }

    result = aggregator.aggregate_orders(orders)

    # Should create 1 aggregated order
    assert len(result.aggregated_orders) == 1

    agg_order = result.aggregated_orders[0]

    # Net amount: 100 - 80 + 30 = 50 (buy)
    assert agg_order.net_amount == Decimal("50")
    assert agg_order.direction == OrderDirection.BUY

    # Should have 3 contributions
    assert len(agg_order.contributions) == 3


def test_full_netting_cancel_both():
    """Full netting: 100 buy + 100 sell → 0 net, cancel both."""
    aggregator = OrderAggregator()

    # Strategy A: Buy 100
    # Strategy B: Sell 100
    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("100"), "sell")],
    }

    result = aggregator.aggregate_orders(orders)

    # Should have no aggregated orders (fully netted)
    assert len(result.aggregated_orders) == 0
    assert result.fully_netted_count == 2

    # Commission savings should be 100%
    assert result.total_aggregated_commission == Decimal("0")
    assert result.total_savings == result.total_original_commission


def test_order_grouping_by_asset_type_price():
    """Orders grouped by asset, order type, and limit price."""
    aggregator = OrderAggregator()

    # Different assets
    orders = {
        "strategy_a": [
            create_order("AAPL", Decimal("100"), "buy", order_type="market"),
            create_order("GOOGL", Decimal("50"), "buy", order_type="market"),
        ],
        "strategy_b": [create_order("AAPL", Decimal("50"), "sell", order_type="market")],
    }

    result = aggregator.aggregate_orders(orders)

    # Should create 2 groups (AAPL and GOOGL)
    assert len(result.aggregated_orders) == 2

    # Find AAPL order
    aapl_order = next(o for o in result.aggregated_orders if o.asset.symbol == "AAPL")
    googl_order = next(o for o in result.aggregated_orders if o.asset.symbol == "GOOGL")

    # AAPL: 100 buy - 50 sell = 50 buy
    assert aapl_order.net_amount == Decimal("50")

    # GOOGL: 50 buy (no offsetting)
    assert googl_order.net_amount == Decimal("50")


def test_fill_allocation_proportional_distribution():
    """Fill allocation proportionally distributes to strategies."""
    aggregator = OrderAggregator()

    # Strategy A: Buy 100
    # Strategy B: Sell 50
    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("50"), "sell")],
    }

    result = aggregator.aggregate_orders(orders)
    agg_order = result.aggregated_orders[0]

    # Allocate fill of 50 shares
    fill_price = Decimal("150.00")
    fill_quantity = Decimal("50")

    allocations = aggregator.allocate_fill(agg_order, fill_price, fill_quantity)

    # Total contribution: |100| + |50| = 150
    # Strategy A: 50 × (100/150) = 33.33
    # Strategy B: 50 × (50/150) = 16.67

    assert "strategy_a" in allocations
    assert "strategy_b" in allocations

    # Verify proportions
    expected_a = Decimal("50") * (Decimal("100") / Decimal("150"))
    expected_b = Decimal("50") * (Decimal("50") / Decimal("150"))

    assert abs(allocations["strategy_a"] - expected_a) < Decimal("0.01")
    assert abs(abs(allocations["strategy_b"]) - expected_b) < Decimal("0.01")

    # Verify direction preserved
    assert allocations["strategy_a"] > Decimal("0")  # Buy
    assert allocations["strategy_b"] < Decimal("0")  # Sell


def test_order_attribution_tracking():
    """Order attribution tracked for each strategy."""
    aggregator = OrderAggregator()

    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("80"), "sell")],
        "strategy_c": [create_order("AAPL", Decimal("30"), "buy")],
    }

    result = aggregator.aggregate_orders(orders)
    agg_order = result.aggregated_orders[0]

    # Should have 3 contributions
    assert len(agg_order.contributions) == 3

    # Each contribution should have strategy_id
    strategy_ids = {c.strategy_id for c in agg_order.contributions}
    assert strategy_ids == {"strategy_a", "strategy_b", "strategy_c"}

    # Each contribution should have percentage
    total_pct = sum(c.contribution_pct for c in agg_order.contributions)
    assert abs(total_pct - Decimal("1.0")) < Decimal("0.01")


def test_commission_savings_calculation():
    """Commission savings calculated correctly."""
    aggregator = OrderAggregator()

    # Strategy A: Buy 100
    # Strategy B: Sell 50
    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("50"), "sell")],
    }

    result = aggregator.aggregate_orders(orders)

    # Original commission: (100 + 50) × $0.005 = $0.75
    expected_original = Decimal("150") * Decimal("0.005")
    assert abs(result.total_original_commission - expected_original) < Decimal("0.01")

    # Aggregated commission: 50 × $0.005 = $0.25
    expected_aggregated = Decimal("50") * Decimal("0.005")
    assert abs(result.total_aggregated_commission - expected_aggregated) < Decimal("0.01")

    # Savings: $0.75 - $0.25 = $0.50
    expected_savings = expected_original - expected_aggregated
    assert abs(result.total_savings - expected_savings) < Decimal("0.01")


def test_limit_price_compatibility():
    """Limit orders with same price can be aggregated."""
    aggregator = OrderAggregator()

    # Both have same limit price
    orders = {
        "strategy_a": [
            create_order(
                "AAPL", Decimal("100"), "buy", order_type="limit", limit_price=Decimal("150.00")
            )
        ],
        "strategy_b": [
            create_order(
                "AAPL", Decimal("50"), "sell", order_type="limit", limit_price=Decimal("150.00")
            )
        ],
    }

    result = aggregator.aggregate_orders(orders)

    # Should aggregate
    assert len(result.aggregated_orders) == 1


def test_limit_price_incompatibility():
    """Limit orders with different prices NOT aggregated."""
    aggregator = OrderAggregator()

    # Different limit prices
    orders = {
        "strategy_a": [
            create_order(
                "AAPL", Decimal("100"), "buy", order_type="limit", limit_price=Decimal("150.00")
            )
        ],
        "strategy_b": [
            create_order(
                "AAPL", Decimal("50"), "sell", order_type="limit", limit_price=Decimal("151.00")
            )
        ],
    }

    result = aggregator.aggregate_orders(orders)

    # Should NOT aggregate (different limit prices)
    assert len(result.aggregated_orders) == 2


def test_market_order_aggregation():
    """Market orders can be aggregated together."""
    aggregator = OrderAggregator()

    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy", order_type="market")],
        "strategy_b": [create_order("AAPL", Decimal("50"), "sell", order_type="market")],
    }

    result = aggregator.aggregate_orders(orders)

    # Should aggregate
    assert len(result.aggregated_orders) == 1
    assert result.aggregated_orders[0].order_type == "market"


def test_edge_case_zero_net():
    """Handle edge case: zero net position (full netting)."""
    aggregator = OrderAggregator()

    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("100"), "sell")],
    }

    result = aggregator.aggregate_orders(orders)

    # Should have no executable orders
    assert len(result.aggregated_orders) == 0
    assert result.fully_netted_count == 2


def test_edge_case_rounding():
    """Handle edge case: rounding in fill allocation."""
    aggregator = OrderAggregator()

    # Create orders with amounts that don't divide evenly
    orders = {
        "strategy_a": [create_order("AAPL", Decimal("33"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("33"), "buy")],
        "strategy_c": [create_order("AAPL", Decimal("34"), "buy")],
    }

    result = aggregator.aggregate_orders(orders)
    agg_order = result.aggregated_orders[0]

    # Allocate fill of 100 shares
    allocations = aggregator.allocate_fill(agg_order, Decimal("150.00"), Decimal("100"))

    # Sum should equal 100 (within tolerance)
    total_allocated = sum(abs(qty) for qty in allocations.values())
    assert abs(total_allocated - Decimal("100")) < Decimal("0.1")


def test_edge_case_no_orders():
    """Handle edge case: no orders to aggregate."""
    aggregator = OrderAggregator()

    orders = {}

    result = aggregator.aggregate_orders(orders)

    # Should return empty result
    assert result.original_orders_count == 0
    assert len(result.aggregated_orders) == 0
    assert result.fully_netted_count == 0
    assert result.total_savings == Decimal("0")


def test_edge_case_single_strategy():
    """Handle edge case: single strategy (no netting possible)."""
    aggregator = OrderAggregator()

    orders = {"strategy_a": [create_order("AAPL", Decimal("100"), "buy")]}

    result = aggregator.aggregate_orders(orders)

    # Should have 1 aggregated order (no netting)
    assert len(result.aggregated_orders) == 1
    assert result.aggregated_orders[0].net_amount == Decimal("100")

    # No savings (single order)
    assert result.total_savings == Decimal("0")


def test_multiple_assets_separate_groups():
    """Multiple assets should create separate order groups."""
    aggregator = OrderAggregator()

    orders = {
        "strategy_a": [
            create_order("AAPL", Decimal("100"), "buy"),
            create_order("GOOGL", Decimal("50"), "buy"),
        ],
        "strategy_b": [
            create_order("AAPL", Decimal("50"), "sell"),
            create_order("GOOGL", Decimal("25"), "sell"),
        ],
    }

    result = aggregator.aggregate_orders(orders)

    # Should create 2 aggregated orders (AAPL and GOOGL)
    assert len(result.aggregated_orders) == 2

    # Verify each asset netted correctly
    aapl_order = next(o for o in result.aggregated_orders if o.asset.symbol == "AAPL")
    googl_order = next(o for o in result.aggregated_orders if o.asset.symbol == "GOOGL")

    assert aapl_order.net_amount == Decimal("50")  # 100 - 50
    assert googl_order.net_amount == Decimal("25")  # 50 - 25


def test_aggregator_statistics():
    """Aggregator statistics tracked correctly."""
    aggregator = OrderAggregator()

    # First aggregation
    orders1 = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("50"), "sell")],
    }
    aggregator.aggregate_orders(orders1)

    # Second aggregation
    orders2 = {
        "strategy_a": [create_order("GOOGL", Decimal("100"), "buy")],
        "strategy_b": [create_order("GOOGL", Decimal("100"), "sell")],
    }
    aggregator.aggregate_orders(orders2)

    stats = aggregator.get_statistics()

    # Should have processed 4 orders total
    assert stats["total_orders_processed"] == 4

    # Should have created 1 aggregated order (first) and fully netted 1 (second)
    assert stats["total_orders_aggregated"] == 1
    assert stats["total_orders_netted"] == 2


# Property-Based Tests


@given(
    amounts=st.lists(
        st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"), places=2),
        min_size=2,
        max_size=10,
    ),
)
@settings(suppress_health_check=[HealthCheck.filter_too_much])
def test_aggregation_never_increases_costs(amounts):
    """Property: Aggregation never increases transaction costs."""

    aggregator = OrderAggregator()

    # Create random orders
    orders = {}
    for i, amount in enumerate(amounts):
        side = "buy" if i % 2 == 0 else "sell"
        orders[f"strategy_{i}"] = [create_order("AAPL", amount, side)]

    result = aggregator.aggregate_orders(orders)

    # Property: Aggregated commission <= Original commission
    assert result.total_aggregated_commission <= result.total_original_commission
    assert result.total_savings >= Decimal("0")


@given(num_strategies=st.integers(min_value=2, max_value=5))
def test_fill_allocation_sums_correctly(num_strategies):
    """Property: Fill allocation sums to fill quantity."""
    aggregator = OrderAggregator()

    # Create orders
    orders = {}
    for i in range(num_strategies):
        amount = Decimal(str((i + 1) * 10))
        side = "buy" if i % 2 == 0 else "sell"
        orders[f"strategy_{i}"] = [create_order("AAPL", amount, side)]

    result = aggregator.aggregate_orders(orders)

    if len(result.aggregated_orders) > 0:
        agg_order = result.aggregated_orders[0]

        # Allocate fill
        fill_quantity = abs(agg_order.net_amount)
        allocations = aggregator.allocate_fill(agg_order, Decimal("150.00"), fill_quantity)

        # Property: Sum of allocated fills = fill quantity (within tolerance)
        total_allocated = sum(abs(qty) for qty in allocations.values())
        assert abs(total_allocated - fill_quantity) < Decimal("0.1")


@given(
    buy_amount=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"), places=2),
    sell_amount=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"), places=2),
)
def test_net_amount_equals_sum_of_contributions(buy_amount, sell_amount):
    """Property: Net amount equals sum of contributions."""
    aggregator = OrderAggregator()

    orders = {
        "strategy_buy": [create_order("AAPL", buy_amount, "buy")],
        "strategy_sell": [create_order("AAPL", sell_amount, "sell")],
    }

    result = aggregator.aggregate_orders(orders)

    if len(result.aggregated_orders) > 0:
        agg_order = result.aggregated_orders[0]

        # Calculate expected net
        expected_net = buy_amount - sell_amount

        # Property: Net amount = sum of contributions
        assert abs(agg_order.net_amount - expected_net) < Decimal("0.01")


@given(num_strategies=st.integers(min_value=2, max_value=5))
def test_savings_always_non_negative(num_strategies):
    """Property: Commission savings always non-negative."""
    aggregator = OrderAggregator()

    # Create random orders
    orders = {}
    for i in range(num_strategies):
        amount = Decimal(str((i + 1) * 50))
        side = "buy" if i % 2 == 0 else "sell"
        orders[f"strategy_{i}"] = [create_order("AAPL", amount, side)]

    result = aggregator.aggregate_orders(orders)

    # Property: Savings >= 0
    assert result.total_savings >= Decimal("0")
    assert result.savings_pct >= Decimal("0")


def test_attribution_preserved():
    """Property: Order attribution preserved through aggregation."""
    aggregator = OrderAggregator()

    # Create orders with known strategies
    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("50"), "sell")],
        "strategy_c": [create_order("AAPL", Decimal("30"), "buy")],
    }

    result = aggregator.aggregate_orders(orders)
    agg_order = result.aggregated_orders[0]

    # Property: All original strategies present in contributions
    contributing_strategies = {c.strategy_id for c in agg_order.contributions}
    original_strategies = set(orders.keys())

    assert contributing_strategies == original_strategies


# Integration Tests


def test_commission_savings_verification():
    """Integration test: Verify commission savings calculation."""
    aggregator = OrderAggregator()

    # Create scenario with known commission
    # 3 orders of 100 shares each at $0.005 per share
    # Without aggregation: 3 × 100 × $0.005 = $1.50
    # With aggregation (net 100): 1 × 100 × $0.005 = $0.50
    # Expected savings: $1.00 (66.7%)

    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("100"), "sell")],
        "strategy_c": [create_order("AAPL", Decimal("100"), "buy")],
    }

    result = aggregator.aggregate_orders(orders)

    # Net: 100 - 100 + 100 = 100 (buy)
    assert result.aggregated_orders[0].net_amount == Decimal("100")

    # Original commission: 300 × $0.005 = $1.50
    expected_original = Decimal("1.50")
    assert abs(result.total_original_commission - expected_original) < Decimal("0.01")

    # Aggregated commission: 100 × $0.005 = $0.50
    expected_aggregated = Decimal("0.50")
    assert abs(result.total_aggregated_commission - expected_aggregated) < Decimal("0.01")

    # Savings: $1.00
    expected_savings = Decimal("1.00")
    assert abs(result.total_savings - expected_savings) < Decimal("0.01")

    # Savings percentage: 66.7%
    assert abs(result.savings_pct - Decimal("66.67")) < Decimal("0.1")


def test_multi_day_aggregation():
    """Integration test: Multi-day aggregation tracking."""
    aggregator = OrderAggregator()

    total_savings = Decimal("0")

    # Simulate 10 days of trading
    for _day in range(10):
        orders = {
            "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
            "strategy_b": [create_order("AAPL", Decimal("50"), "sell")],
        }

        result = aggregator.aggregate_orders(orders)
        total_savings += result.total_savings

    # Should have meaningful cumulative savings
    assert total_savings > Decimal("0")
    assert aggregator.cumulative_savings == total_savings

    # Get statistics
    stats = aggregator.get_statistics()
    assert stats["total_orders_processed"] == 20  # 2 orders × 10 days
    assert stats["total_orders_aggregated"] == 10  # 1 aggregated per day


def test_complex_multi_strategy_scenario():
    """Integration test: Complex multi-strategy scenario."""
    aggregator = OrderAggregator()

    # 5 strategies with various positions
    orders = {
        "momentum": [create_order("AAPL", Decimal("200"), "buy")],
        "mean_reversion": [create_order("AAPL", Decimal("150"), "sell")],
        "trend": [create_order("AAPL", Decimal("100"), "buy")],
        "value": [create_order("AAPL", Decimal("50"), "sell")],
        "growth": [create_order("AAPL", Decimal("75"), "buy")],
    }

    result = aggregator.aggregate_orders(orders)

    # Net: 200 - 150 + 100 - 50 + 75 = 175 (buy)
    assert len(result.aggregated_orders) == 1
    assert result.aggregated_orders[0].net_amount == Decimal("175")

    # Should have 5 contributions
    assert len(result.aggregated_orders[0].contributions) == 5

    # Allocate fill
    agg_order = result.aggregated_orders[0]
    allocations = aggregator.allocate_fill(agg_order, Decimal("150.00"), Decimal("175"))

    # All 5 strategies should receive allocations
    assert len(allocations) == 5

    # Verify total allocation
    total_allocated = sum(abs(qty) for qty in allocations.values())
    assert abs(total_allocated - Decimal("175")) < Decimal("0.1")


def test_partial_fill_allocation():
    """Integration test: Partial fill allocation."""
    aggregator = OrderAggregator()

    orders = {
        "strategy_a": [create_order("AAPL", Decimal("100"), "buy")],
        "strategy_b": [create_order("AAPL", Decimal("50"), "sell")],
    }

    result = aggregator.aggregate_orders(orders)
    agg_order = result.aggregated_orders[0]

    # Net amount is 50, but only 25 filled (partial)
    allocations = aggregator.allocate_fill(agg_order, Decimal("150.00"), Decimal("25"))

    # Total contribution: |100| + |50| = 150
    # Strategy A: 25 × (100/150) = 16.67
    # Strategy B: 25 × (50/150) = 8.33

    expected_a = Decimal("25") * (Decimal("100") / Decimal("150"))
    expected_b = Decimal("25") * (Decimal("50") / Decimal("150"))

    assert abs(allocations["strategy_a"] - expected_a) < Decimal("0.01")
    assert abs(abs(allocations["strategy_b"]) - expected_b) < Decimal("0.01")

    # Verify total
    total_allocated = sum(abs(qty) for qty in allocations.values())
    assert abs(total_allocated - Decimal("25")) < Decimal("0.1")
