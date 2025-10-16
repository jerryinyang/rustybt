"""
Tutorial: Using Slippage Models in RustyBT (Story 4.3)

This example demonstrates how to use the three slippage models:
1. VolumeShareSlippageDecimal - Volume-based impact with volatility adjustment
2. FixedBasisPointSlippageDecimal - Constant basis point slippage
3. BidAskSpreadSlippageDecimal - Bid-ask spread crossing slippage

The execution engine integrates slippage models with latency and partial fill models
for realistic order execution simulation.
"""

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

# Import execution engine
# Import slippage models
from rustybt.finance.slippage import (
    BidAskSpreadSlippageDecimal,
    FixedBasisPointSlippageDecimal,
    VolumeShareSlippageDecimal,
)

# ============================================================================
# Mock Objects for Tutorial
# ============================================================================


@dataclass
class MockAsset:
    """Simple asset for tutorial."""

    symbol: str


@dataclass
class MockOrder:
    """Simple order for tutorial."""

    id: str
    asset: MockAsset
    amount: Decimal  # Positive=buy, negative=sell


# ============================================================================
# Example 1: VolumeShareSlippageDecimal - Volume-Based Impact
# ============================================================================


def example_1_volume_share_slippage():
    """Demonstrate volume-share slippage with volatility adjustment."""
    print("=" * 80)
    print("Example 1: VolumeShareSlippageDecimal")
    print("=" * 80)

    # Create model with custom parameters
    model = VolumeShareSlippageDecimal(
        volume_limit=Decimal("0.025"),  # 2.5% of bar volume
        price_impact=Decimal("0.10"),  # 10% impact coefficient
        power_factor=Decimal("0.5"),  # Square root scaling
        volatility_window=20,  # 20-day volatility
    )

    # Create a buy order
    order = MockOrder(
        id="order-001",
        asset=MockAsset(symbol="AAPL"),
        amount=Decimal("1000"),  # Buy 1000 shares
    )

    # Bar data with price, volume, and volatility
    bar_data = {
        "close": 150.00,
        "volume": 10000,
        "volatility": 0.25,  # 25% annual volatility
    }

    # Calculate slippage
    result = model.calculate_slippage(order, bar_data, pd.Timestamp("2023-01-01 10:00"))

    print("\nOrder Details:")
    print(f"  Asset: {order.asset.symbol}")
    print(f"  Size: {order.amount} shares")
    print(f"  Bar Price: ${bar_data['close']:.2f}")
    print(f"  Bar Volume: {bar_data['volume']:,}")
    print(f"  Volatility: {bar_data['volatility']:.1%}")

    print("\nSlippage Calculation:")
    print(f"  Volume Ratio: {result.metadata['volume_ratio']}")
    print(f"  Volume Impact: {result.metadata['volume_impact']}")
    print(f"  Slippage Amount: ${result.slippage_amount:.4f}")
    print(f"  Slippage (bps): {result.slippage_bps:.2f}")
    print(f"  Slippage (%): {result.slippage_percentage * Decimal('100'):.4f}%")

    # Apply directional slippage
    base_price = Decimal(str(bar_data["close"]))
    order_side = model._get_order_side(order)
    fill_price = model._apply_directional_slippage(base_price, result.slippage_amount, order_side)

    print("\nExecution:")
    print(f"  Base Price: ${base_price:.2f}")
    print(f"  Order Side: {order_side.value}")
    print(f"  Fill Price: ${fill_price:.2f} (slipped {fill_price - base_price:+.4f})")
    print(f"  Total Cost: ${fill_price * order.amount:,.2f}")


# ============================================================================
# Example 2: FixedBasisPointSlippageDecimal - Constant Slippage
# ============================================================================


def example_2_fixed_bps_slippage():
    """Demonstrate fixed basis point slippage."""
    print("\n" + "=" * 80)
    print("Example 2: FixedBasisPointSlippageDecimal")
    print("=" * 80)

    # Create model with 10 bps slippage
    model = FixedBasisPointSlippageDecimal(
        basis_points=Decimal("10.0"),  # 10 bps = 0.10%
        min_slippage=Decimal("0.01"),  # Minimum $0.01
    )

    # Test with high-priced and low-priced stocks
    test_cases = [
        ("AAPL", Decimal("500"), 150.00),  # High-priced stock
        ("PENNY", Decimal("10000"), 5.00),  # Low-priced stock
    ]

    for symbol, size, price in test_cases:
        order = MockOrder(id=f"order-{symbol}", asset=MockAsset(symbol=symbol), amount=size)

        bar_data = {"close": price}

        result = model.calculate_slippage(order, bar_data, pd.Timestamp("2023-01-01"))

        base_price = Decimal(str(price))
        fill_price = model._apply_directional_slippage(
            base_price, result.slippage_amount, model._get_order_side(order)
        )

        print(f"\n{symbol}:")
        print(f"  Order: Buy {size} @ ${price:.2f}")
        print(f"  Slippage: ${result.slippage_amount:.4f} ({result.slippage_bps:.2f} bps)")
        print(f"  Fill Price: ${fill_price:.4f}")
        print(f"  Min Slippage Applied: {result.metadata['min_slippage_applied']}")


# ============================================================================
# Example 3: BidAskSpreadSlippageDecimal - Spread Crossing
# ============================================================================


def example_3_bid_ask_spread_slippage():
    """Demonstrate bid-ask spread slippage."""
    print("\n" + "=" * 80)
    print("Example 3: BidAskSpreadSlippageDecimal")
    print("=" * 80)

    # Create model
    model = BidAskSpreadSlippageDecimal(
        spread_estimate=Decimal("0.001"),  # 0.1% default spread
        spread_factor=Decimal("1.0"),  # No spread multiplier
    )

    # Test Case 1: Real bid/ask data available
    print("\nCase 1: Real Bid/Ask Data")
    order = MockOrder(id="order-001", asset=MockAsset(symbol="AAPL"), amount=Decimal("100"))

    bar_data_with_quotes = {"bid": 149.90, "ask": 150.10, "close": 150.00}

    result = model.calculate_slippage(order, bar_data_with_quotes, pd.Timestamp("2023-01-01"))

    print(f"  Bid: ${bar_data_with_quotes['bid']:.2f}")
    print(f"  Ask: ${bar_data_with_quotes['ask']:.2f}")
    print(f"  Spread: ${Decimal(str(result.metadata['spread'])):.2f}")
    print(f"  Slippage: ${result.slippage_amount:.4f}")
    print(f"  Source: {result.metadata['spread_source']}")

    # Test Case 2: No bid/ask data (estimation)
    print("\nCase 2: Estimated Spread")
    bar_data_no_quotes = {"close": 150.00}

    result2 = model.calculate_slippage(order, bar_data_no_quotes, pd.Timestamp("2023-01-01"))

    print(f"  Close: ${bar_data_no_quotes['close']:.2f}")
    print(f"  Estimated Spread: ${Decimal(str(result2.metadata['estimated_spread'])):.2f}")
    print(f"  Slippage: ${result2.slippage_amount:.4f}")
    print(f"  Source: {result2.metadata['spread_source']}")


# ============================================================================
# Example 4: Directional Slippage
# ============================================================================


def example_4_directional_slippage():
    """Demonstrate directional slippage (buy vs sell)."""
    print("\n" + "=" * 80)
    print("Example 4: Directional Slippage (Buy vs Sell)")
    print("=" * 80)

    model = FixedBasisPointSlippageDecimal(basis_points=Decimal("10.0"))

    base_price = Decimal("100.00")
    bar_data = {"close": 100.00}

    # Buy order
    buy_order = MockOrder(
        id="buy-001",
        asset=MockAsset(symbol="TEST"),
        amount=Decimal("100"),  # Positive = buy
    )

    buy_result = model.calculate_slippage(buy_order, bar_data, pd.Timestamp("2023-01-01"))
    buy_side = model._get_order_side(buy_order)
    buy_fill = model._apply_directional_slippage(base_price, buy_result.slippage_amount, buy_side)

    print("\nBuy Order:")
    print(f"  Base Price: ${base_price:.2f}")
    print(f"  Slippage: ${buy_result.slippage_amount:.4f}")
    print(f"  Fill Price: ${buy_fill:.2f} (worse: pay MORE)")
    print(f"  Impact: ${buy_fill - base_price:+.4f}")

    # Sell order
    sell_order = MockOrder(
        id="sell-001",
        asset=MockAsset(symbol="TEST"),
        amount=Decimal("-100"),  # Negative = sell
    )

    sell_result = model.calculate_slippage(sell_order, bar_data, pd.Timestamp("2023-01-01"))
    sell_side = model._get_order_side(sell_order)
    sell_fill = model._apply_directional_slippage(
        base_price, sell_result.slippage_amount, sell_side
    )

    print("\nSell Order:")
    print(f"  Base Price: ${base_price:.2f}")
    print(f"  Slippage: ${sell_result.slippage_amount:.4f}")
    print(f"  Fill Price: ${sell_fill:.2f} (worse: receive LESS)")
    print(f"  Impact: ${sell_fill - base_price:+.4f}")


# ============================================================================
# Example 5: Comparing Slippage Models
# ============================================================================


def example_5_comparing_models():
    """Compare different slippage models on the same order."""
    print("\n" + "=" * 80)
    print("Example 5: Comparing Slippage Models")
    print("=" * 80)

    # Create all three models
    volume_model = VolumeShareSlippageDecimal()
    fixed_model = FixedBasisPointSlippageDecimal(basis_points=Decimal("5.0"))
    spread_model = BidAskSpreadSlippageDecimal()

    # Same order
    order = MockOrder(id="compare-001", asset=MockAsset(symbol="AAPL"), amount=Decimal("1000"))

    # Same bar data
    bar_data = {"close": 150.00, "volume": 50000, "volatility": 0.20, "bid": 149.95, "ask": 150.05}

    base_price = Decimal("150.00")

    print(f"\nOrder: Buy {order.amount} {order.asset.symbol} @ ${bar_data['close']:.2f}")
    print(f"Bar Volume: {bar_data['volume']:,}")
    print(f"Volatility: {bar_data['volatility']:.1%}")
    print(f"Bid/Ask: ${bar_data['bid']:.2f} / ${bar_data['ask']:.2f}")

    models = [
        ("VolumeShare", volume_model),
        ("FixedBPS", fixed_model),
        ("BidAskSpread", spread_model),
    ]

    print(f"\n{'Model':<20} {'Slippage':<15} {'Slippage (bps)':<15} {'Fill Price':<15}")
    print("-" * 70)

    for name, model in models:
        result = model.calculate_slippage(order, bar_data, pd.Timestamp("2023-01-01"))
        fill_price = model._apply_directional_slippage(
            base_price, result.slippage_amount, model._get_order_side(order)
        )

        print(
            f"{name:<20} ${result.slippage_amount:<14.4f} {result.slippage_bps:<14.2f} ${fill_price:<14.2f}"
        )


# ============================================================================
# Example 6: Execution Engine Integration
# ============================================================================


def example_6_execution_engine():
    """Demonstrate slippage integration with execution engine."""
    print("\n" + "=" * 80)
    print("Example 6: Execution Engine with Slippage + Latency")
    print("=" * 80)

    # Note: This is a conceptual example showing the API
    # In practice, you'd need a real data_portal implementation

    print("\nConcept: Combining slippage with latency simulation")
    print("-" * 80)

    print(
        """
    from rustybt.finance.execution import ExecutionEngine, FixedLatencyModel
    from rustybt.finance.slippage import VolumeShareSlippageDecimal

    # Create execution engine with both models
    engine = ExecutionEngine(
        latency_model=FixedLatencyModel(
            network_ms=Decimal("10.0"),
            broker_ms=Decimal("5.0"),
            exchange_ms=Decimal("2.0")
        ),
        slippage_model=VolumeShareSlippageDecimal(),
        data_portal=your_data_portal  # Provides price/volume data
    )

    # Execute order
    result = engine.execute_order(
        order=your_order,
        current_time=pd.Timestamp("2023-01-01 10:00:00"),
        broker_name="interactive_brokers"
    )

    # Result includes both latency and slippage
    print(f"Execution Time: {result.execution_time}")
    print(f"Latency: {result.latency.total_ms} ms")
    print(f"Slippage: {result.slippage.slippage_bps} bps")
    print(f"Fill Price: ${result.fill_price}")
    """
    )


# ============================================================================
# Main: Run All Examples
# ============================================================================


def main():
    """Run all slippage model examples."""
    print("\n")
    print("*" * 80)
    print("* RustyBT Slippage Models Tutorial")
    print("* Story 4.3: Multiple Slippage Models")
    print("*" * 80)

    example_1_volume_share_slippage()
    example_2_fixed_bps_slippage()
    example_3_bid_ask_spread_slippage()
    example_4_directional_slippage()
    example_5_comparing_models()
    example_6_execution_engine()

    print("\n" + "=" * 80)
    print("Tutorial Complete!")
    print("=" * 80)
    print(
        """
Key Takeaways:

1. VolumeShareSlippageDecimal: Best for modeling market impact based on order size
   - Scales with order volume / bar volume ratio
   - Adjusts for volatility
   - Use for large orders in liquid markets

2. FixedBasisPointSlippageDecimal: Simple constant slippage
   - Easy to configure and understand
   - Consistent costs across all orders
   - Use for simple backtests or when impact data unavailable

3. BidAskSpreadSlippageDecimal: Models spread crossing costs
   - Uses real bid/ask data when available
   - Falls back to estimation
   - Use for markets with visible spreads (forex, crypto)

4. All models enforce directional slippage:
   - Buy orders: price slips UP (pay more)
   - Sell orders: price slips DOWN (receive less)

5. Integration with ExecutionEngine:
   - Combine slippage with latency and partial fills
   - Realistic end-to-end order execution simulation
"""
    )


if __name__ == "__main__":
    main()
