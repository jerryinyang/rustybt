"""Tutorial: Capital Allocation Algorithms

This tutorial demonstrates the various capital allocation algorithms available
in RustyBT for multi-strategy portfolio management.

Covered algorithms:
1. FixedAllocation - Static percentage allocation
2. DynamicAllocation - Performance-based momentum allocation
3. RiskParityAllocation - Volatility-weighted equal risk contribution
4. KellyCriterionAllocation - Growth-optimal allocation
5. DrawdownBasedAllocation - Risk-averse drawdown-aware allocation
6. AllocationRebalancer - Automated rebalancing scheduler
"""

from decimal import Decimal

import numpy as np
import pandas as pd

from rustybt.portfolio.allocation import (
    AllocationConstraints,
    AllocationRebalancer,
    DrawdownBasedAllocation,
    DynamicAllocation,
    FixedAllocation,
    KellyCriterionAllocation,
    RebalancingFrequency,
    RiskParityAllocation,
)
from rustybt.portfolio.allocator import StrategyPerformance

# ============================================================================
# Helper: Create Synthetic Strategy Performance
# ============================================================================


def create_synthetic_strategy(
    strategy_id: str, mean_return: float, volatility: float, num_periods: int = 252
) -> StrategyPerformance:
    """Create synthetic strategy performance for demonstration.

    Args:
        strategy_id: Strategy identifier
        mean_return: Mean daily return
        volatility: Daily volatility (standard deviation)
        num_periods: Number of trading days to simulate

    Returns:
        StrategyPerformance with synthetic returns
    """
    perf = StrategyPerformance(strategy_id)

    # Generate synthetic returns
    np.random.seed(42)  # For reproducibility
    returns = np.random.normal(mean_return, volatility, num_periods)
    perf.returns = [Decimal(str(r)) for r in returns]

    # Simulate portfolio values
    initial_value = Decimal("100000")
    portfolio_value = initial_value
    perf.peak_value = initial_value

    for ret in perf.returns:
        portfolio_value = portfolio_value * (Decimal("1") + ret)

        # Update peak and drawdown
        if portfolio_value > perf.peak_value:
            perf.peak_value = portfolio_value
            perf.current_drawdown = Decimal("0")
        else:
            if perf.peak_value > Decimal("0"):
                perf.current_drawdown = (portfolio_value - perf.peak_value) / perf.peak_value
                if perf.current_drawdown < perf.max_drawdown:
                    perf.max_drawdown = perf.current_drawdown

    print(f"\n{strategy_id}:")
    print(f"  Mean Return: {float(perf.mean_return):.2%}")
    print(f"  Volatility: {float(perf.volatility):.2%}")
    print(f"  Sharpe Ratio: {float(perf.sharpe_ratio):.2f}")
    print(f"  Max Drawdown: {float(perf.max_drawdown):.2%}")

    return perf


# ============================================================================
# Example 1: Fixed Allocation
# ============================================================================


def example_fixed_allocation():
    """Example: Fixed allocation with predefined weights."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Fixed Allocation")
    print("=" * 70)
    print("\nUse Case: Conservative allocation with predefined strategy weights")
    print("Best For: Stable portfolios where you trust your initial allocation")

    # Create strategies
    strategies = {
        "momentum": create_synthetic_strategy("Momentum", 0.0008, 0.015),
        "mean_reversion": create_synthetic_strategy("Mean Reversion", 0.0006, 0.01),
        "trend_following": create_synthetic_strategy("Trend Following", 0.0007, 0.018),
    }

    # Define fixed allocations (40% / 30% / 30%)
    fixed_alloc = FixedAllocation(
        {
            "momentum": Decimal("0.40"),
            "mean_reversion": Decimal("0.30"),
            "trend_following": Decimal("0.30"),
        }
    )

    # Calculate allocations
    allocations = fixed_alloc.calculate_allocations(strategies)

    print("\nFixed Allocations:")
    for strategy_id, allocation in allocations.items():
        print(f"  {strategy_id:20s}: {float(allocation):6.1%}")

    print(f"\nTotal Allocation: {float(sum(allocations.values())):.1%}")


# ============================================================================
# Example 2: Dynamic Allocation (Momentum-Based)
# ============================================================================


def example_dynamic_allocation():
    """Example: Dynamic allocation based on recent performance."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Dynamic Allocation (Performance-Based)")
    print("=" * 70)
    print("\nUse Case: Momentum-based allocation favoring recent winners")
    print("Best For: Trend-following portfolios, adaptive strategies")

    # Create strategies with varying performance
    strategies = {
        "winner": create_synthetic_strategy("Winner Strategy", 0.0015, 0.02),  # High returns
        "average": create_synthetic_strategy("Average Strategy", 0.0005, 0.01),  # Medium
        "loser": create_synthetic_strategy("Loser Strategy", -0.0003, 0.015),  # Negative
    }

    # Create dynamic allocator (60-day lookback)
    dynamic_alloc = DynamicAllocation(
        lookback_window=60,
        min_allocation=Decimal("0.05"),  # 60 days  # 5% minimum
    )

    # Calculate allocations
    allocations = dynamic_alloc.calculate_allocations(strategies)

    print("\nDynamic Allocations (Momentum-Based):")
    for strategy_id, allocation in allocations.items():
        perf = strategies[strategy_id]
        recent_return = sum(perf.returns[-60:])  # 60-day return
        print(
            f"  {strategy_id:20s}: {float(allocation):6.1%} "
            f"(60d return: {float(recent_return):6.2%})"
        )

    print(f"\nTotal Allocation: {float(sum(allocations.values())):.1%}")
    print("\nNote: Winner gets highest allocation, loser gets minimum (5%)")


# ============================================================================
# Example 3: Risk Parity Allocation
# ============================================================================


def example_risk_parity_allocation():
    """Example: Risk parity allocation for equal risk contribution."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Risk Parity Allocation (Volatility-Weighted)")
    print("=" * 70)
    print("\nUse Case: Diversified allocation balancing risk across strategies")
    print("Best For: Risk-managed portfolios, equal risk contribution")

    # Create strategies with different volatility profiles
    strategies = {
        "low_vol": create_synthetic_strategy("Low Vol Strategy", 0.0005, 0.008),  # Low volatility
        "medium_vol": create_synthetic_strategy(
            "Medium Vol Strategy", 0.0007, 0.015
        ),  # Medium volatility
        "high_vol": create_synthetic_strategy(
            "High Vol Strategy", 0.0010, 0.025
        ),  # High volatility
    }

    # Create risk parity allocator
    risk_parity = RiskParityAllocation(
        lookback_window=252,  # 1 year
        min_volatility=Decimal("0.001"),  # Minimum 0.1%
    )

    # Calculate allocations
    allocations = risk_parity.calculate_allocations(strategies)

    print("\nRisk Parity Allocations:")
    for strategy_id, allocation in allocations.items():
        perf = strategies[strategy_id]
        print(
            f"  {strategy_id:20s}: {float(allocation):6.1%} "
            f"(volatility: {float(perf.volatility):6.2%})"
        )

    print(f"\nTotal Allocation: {float(sum(allocations.values())):.1%}")
    print("\nNote: Lower volatility strategies get higher allocation (inverse weighting)")


# ============================================================================
# Example 4: Kelly Criterion Allocation
# ============================================================================


def example_kelly_criterion_allocation():
    """Example: Kelly criterion for growth-optimal allocation."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Kelly Criterion Allocation (Growth-Optimal)")
    print("=" * 70)
    print("\nUse Case: Aggressive growth-focused allocation")
    print("Best For: Maximizing long-term geometric growth (use half-Kelly for safety)")

    # Create strategies
    strategies = {
        "high_sharpe": create_synthetic_strategy(
            "High Sharpe Strategy", 0.0012, 0.01
        ),  # Good return/variance
        "medium_sharpe": create_synthetic_strategy(
            "Medium Sharpe Strategy", 0.0008, 0.015
        ),  # Medium
        "low_sharpe": create_synthetic_strategy("Low Sharpe Strategy", 0.0005, 0.02),  # Low
    }

    # Create Kelly allocator (half-Kelly for conservative approach)
    kelly_alloc = KellyCriterionAllocation(
        lookback_window=252,  # 1 year
        kelly_fraction=Decimal("0.5"),  # Half-Kelly (conservative)
        min_variance=Decimal("0.0001"),
    )

    # Calculate allocations
    allocations = kelly_alloc.calculate_allocations(strategies)

    print("\nKelly Criterion Allocations (Half-Kelly):")
    for strategy_id, allocation in allocations.items():
        perf = strategies[strategy_id]
        print(
            f"  {strategy_id:20s}: {float(allocation):6.1%} "
            f"(Sharpe: {float(perf.sharpe_ratio):5.2f})"
        )

    print(f"\nTotal Allocation: {float(sum(allocations.values())):.1%}")
    print("\nNote: Higher Sharpe ratio strategies get higher allocation")


# ============================================================================
# Example 5: Drawdown-Based Allocation
# ============================================================================


def example_drawdown_based_allocation():
    """Example: Drawdown-based allocation reducing exposure to underperformers."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Drawdown-Based Allocation (Risk-Averse)")
    print("=" * 70)
    print("\nUse Case: Risk-averse allocation reducing exposure to strategies in drawdown")
    print("Best For: Capital preservation, defensive portfolios")

    # Create strategies with different drawdown states
    strategies = {}

    # Healthy strategy (no drawdown)
    healthy = StrategyPerformance("Healthy Strategy")
    healthy.returns = [Decimal("0.001")] * 100
    healthy.current_drawdown = Decimal("0.00")
    healthy.max_drawdown = Decimal("0.00")
    strategies["healthy"] = healthy

    # Strategy in moderate drawdown
    moderate_dd = StrategyPerformance("Moderate DD Strategy")
    moderate_dd.returns = [Decimal("-0.0005")] * 50 + [Decimal("0.0005")] * 50
    moderate_dd.current_drawdown = Decimal("-0.10")  # 10% drawdown
    moderate_dd.max_drawdown = Decimal("-0.10")
    strategies["moderate_dd"] = moderate_dd

    # Strategy in severe drawdown
    severe_dd = StrategyPerformance("Severe DD Strategy")
    severe_dd.returns = [Decimal("-0.001")] * 100
    severe_dd.current_drawdown = Decimal("-0.25")  # 25% drawdown
    severe_dd.max_drawdown = Decimal("-0.25")
    strategies["severe_dd"] = severe_dd

    # Recovering strategy (was in drawdown, now recovered)
    recovered = StrategyPerformance("Recovered Strategy")
    recovered.returns = [Decimal("0.001")] * 100
    recovered.current_drawdown = Decimal("0.00")  # No current drawdown
    recovered.max_drawdown = Decimal("-0.15")  # Had 15% drawdown in past
    strategies["recovered"] = recovered

    # Create drawdown-based allocator
    dd_alloc = DrawdownBasedAllocation(
        max_drawdown_threshold=Decimal("0.20"),  # 20% threshold
        recovery_bonus=Decimal("0.10"),  # 10% bonus for recovered strategies
    )

    # Calculate allocations
    allocations = dd_alloc.calculate_allocations(strategies)

    print("\nDrawdown-Based Allocations:")
    for strategy_id, allocation in allocations.items():
        perf = strategies[strategy_id]
        print(
            f"  {strategy_id:25s}: {float(allocation):6.1%} "
            f"(current DD: {float(perf.current_drawdown):6.1%}, "
            f"max DD: {float(perf.max_drawdown):6.1%})"
        )

    print(f"\nTotal Allocation: {float(sum(allocations.values())):.1%}")
    print("\nNote: Strategies in drawdown get reduced allocation, recovered get bonus")


# ============================================================================
# Example 6: Allocation Constraints
# ============================================================================


def example_allocation_constraints():
    """Example: Enforcing min/max constraints on allocations."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Allocation Constraints")
    print("=" * 70)
    print("\nUse Case: Enforce min/max allocation limits per strategy")
    print("Best For: Risk management, regulatory compliance")

    # Create strategies
    strategies = {
        "strategy1": create_synthetic_strategy("Strategy 1", 0.0015, 0.025),  # High vol
        "strategy2": create_synthetic_strategy("Strategy 2", 0.0008, 0.01),  # Low vol
        "strategy3": create_synthetic_strategy("Strategy 3", 0.0010, 0.015),  # Medium
    }

    # Create constraints (min 10%, max 50% per strategy)
    constraints = AllocationConstraints(
        default_min=Decimal("0.10"),  # 10% minimum
        default_max=Decimal("0.50"),  # 50% maximum
        strategy_min={"strategy1": Decimal("0.05")},  # Override: allow strategy1 down to 5%
        strategy_max={"strategy3": Decimal("0.40")},  # Override: limit strategy3 to 40%
    )

    # Create risk parity with constraints
    risk_parity = RiskParityAllocation(constraints=constraints)

    # Calculate allocations
    allocations_unconstrained = RiskParityAllocation().calculate_allocations(strategies)
    allocations_constrained = risk_parity.calculate_allocations(strategies)

    print("\nAllocations (Unconstrained vs Constrained):")
    for strategy_id in strategies:
        unconstrained = allocations_unconstrained[strategy_id]
        constrained = allocations_constrained[strategy_id]
        print(f"  {strategy_id:12s}: {float(unconstrained):6.1%} → {float(constrained):6.1%}")

    print(f"\nTotal Allocation: {float(sum(allocations_constrained.values())):.1%}")


# ============================================================================
# Example 7: Automated Rebalancing
# ============================================================================


def example_automated_rebalancing():
    """Example: Automated rebalancing with scheduler."""
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Automated Rebalancing")
    print("=" * 70)
    print("\nUse Case: Periodic rebalancing with frequency control")
    print("Best For: Systematic portfolio management, reduce transaction costs")

    # Create strategies
    strategies = {
        "strategy1": create_synthetic_strategy("Strategy 1", 0.0008, 0.015),
        "strategy2": create_synthetic_strategy("Strategy 2", 0.0006, 0.01),
        "strategy3": create_synthetic_strategy("Strategy 3", 0.0007, 0.012),
    }

    # Create allocation algorithm
    algo = DynamicAllocation(lookback_window=60)

    # Create rebalancer (weekly frequency, 7-day cooldown)
    rebalancer = AllocationRebalancer(
        algorithm=algo,
        frequency=RebalancingFrequency.WEEKLY,
        cooldown_days=7,
        drift_threshold=Decimal("0.10"),  # Rebalance if drift > 10%
    )

    # Simulate rebalancing over time
    print("\nRebalancing Schedule:")

    # Day 0 (Monday) - Initial rebalancing
    day0 = pd.Timestamp("2023-01-02")  # Monday
    should_rebalance, reason = rebalancer.should_rebalance(day0)
    print(f"\n{day0.date()} ({day0.day_name()}): {reason}")
    if should_rebalance:
        new_allocations = rebalancer.rebalance(strategies, day0)
        print(
            "  Rebalanced: "
            + ", ".join([f"{k}={float(v):.1%}" for k, v in new_allocations.items()])
        )

    # Day 3 (Thursday) - Should not trigger (cooldown)
    day3 = pd.Timestamp("2023-01-05")
    should_rebalance, reason = rebalancer.should_rebalance(day3)
    print(f"\n{day3.date()} ({day3.day_name()}): {reason}")

    # Day 7 (Next Monday) - Should not trigger (only 5 days, cooldown=7)
    day7 = pd.Timestamp("2023-01-09")
    should_rebalance, reason = rebalancer.should_rebalance(day7)
    print(f"\n{day7.date()} ({day7.day_name()}): {reason}")

    # Day 9 (Wednesday, after cooldown) - Should trigger (weekly + cooldown passed)
    day9 = pd.Timestamp("2023-01-11")
    should_rebalance, reason = rebalancer.should_rebalance(day9)
    print(f"\n{day9.date()} ({day9.day_name()}): {reason}")
    if should_rebalance:
        new_allocations = rebalancer.rebalance(strategies, day9)
        print(
            "  Rebalanced: "
            + ", ".join([f"{k}={float(v):.1%}" for k, v in new_allocations.items()])
        )


# ============================================================================
# Example 8: Algorithm Comparison
# ============================================================================


def example_algorithm_comparison():
    """Example: Compare all allocation algorithms side-by-side."""
    print("\n" + "=" * 70)
    print("EXAMPLE 8: Algorithm Comparison")
    print("=" * 70)
    print("\nCompare all allocation algorithms with same strategy data")

    # Create diverse strategies
    strategies = {
        "high_return_high_vol": create_synthetic_strategy("High Return/Vol", 0.0012, 0.025),
        "medium_return_low_vol": create_synthetic_strategy("Medium Return/Low Vol", 0.0008, 0.01),
        "low_return_medium_vol": create_synthetic_strategy("Low Return/Med Vol", 0.0004, 0.015),
    }

    # Run all algorithms
    results = {}

    # 1. Fixed (equal weight)
    results["Fixed (Equal)"] = FixedAllocation(
        {
            "high_return_high_vol": Decimal("0.33"),
            "medium_return_low_vol": Decimal("0.33"),
            "low_return_medium_vol": Decimal("0.34"),
        }
    ).calculate_allocations(strategies)

    # 2. Dynamic (momentum-based)
    results["Dynamic"] = DynamicAllocation(lookback_window=60).calculate_allocations(strategies)

    # 3. Risk Parity
    results["Risk Parity"] = RiskParityAllocation(lookback_window=252).calculate_allocations(
        strategies
    )

    # 4. Kelly Criterion
    results["Kelly (Half)"] = KellyCriterionAllocation(
        lookback_window=252, kelly_fraction=Decimal("0.5")
    ).calculate_allocations(strategies)

    # 5. Drawdown-Based (all healthy for now)
    for perf in strategies.values():
        perf.current_drawdown = Decimal("0")
        perf.max_drawdown = Decimal("0")
    results["Drawdown"] = DrawdownBasedAllocation().calculate_allocations(strategies)

    # Print comparison table
    print("\nAllocation Comparison Table:")
    print(
        f"\n{'Algorithm':<20s} | {'High R/V':>12s} | {'Med R/Low V':>12s} | {'Low R/Med V':>12s} |"
    )
    print("-" * 70)

    for algo_name, allocations in results.items():
        row = f"{algo_name:<20s} |"
        for strategy_id in strategies:
            alloc = allocations[strategy_id]
            row += f" {float(alloc):11.1%} |"
        print(row)

    print("\nKey Observations:")
    print("- Fixed: Equal allocation across all strategies")
    print("- Dynamic: Favors recent performance winners")
    print("- Risk Parity: Higher allocation to low-volatility strategies")
    print("- Kelly: Balances return vs. variance (Sharpe-like)")
    print("- Drawdown: All equal when no drawdowns present")


# ============================================================================
# Main: Run All Examples
# ============================================================================


def main():
    """Run all allocation algorithm examples."""
    print("\n" + "=" * 70)
    print("RUSTYBT CAPITAL ALLOCATION ALGORITHMS TUTORIAL")
    print("=" * 70)

    # Run examples
    example_fixed_allocation()
    example_dynamic_allocation()
    example_risk_parity_allocation()
    example_kelly_criterion_allocation()
    example_drawdown_based_allocation()
    example_allocation_constraints()
    example_automated_rebalancing()
    example_algorithm_comparison()

    print("\n" + "=" * 70)
    print("Tutorial Complete!")
    print("=" * 70)
    print("\nFor more information, see documentation:")
    print("  - rustybt/portfolio/allocation.py")
    print("  - tests/portfolio/test_allocation.py")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
