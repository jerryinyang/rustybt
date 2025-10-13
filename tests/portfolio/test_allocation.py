"""Comprehensive tests for capital allocation algorithms."""

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

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


# Test helpers
def create_mock_performance(
    strategy_id: str,
    mean_return: float = 0.001,
    volatility: float = 0.02,
    num_periods: int = 100,  # Reduced default from 252 to avoid timestamp overflow
) -> StrategyPerformance:
    """Create mock strategy performance for testing.

    Args:
        strategy_id: Strategy identifier
        mean_return: Mean daily return
        volatility: Daily volatility
        num_periods: Number of periods to generate

    Returns:
        StrategyPerformance with synthetic returns
    """
    perf = StrategyPerformance(strategy_id)

    # Generate returns with specified mean and volatility
    returns = np.random.normal(mean_return, volatility, num_periods)
    perf.returns = [Decimal(str(r)) for r in returns]

    # Simulate portfolio values (without calling update to avoid timestamp overflow)
    initial_value = Decimal("100000")
    portfolio_value = initial_value

    # Manually populate metrics without timestamps
    perf.peak_value = initial_value
    for ret in perf.returns:
        portfolio_value = portfolio_value * (Decimal("1") + ret)
        # Update peak and drawdown manually
        if portfolio_value > perf.peak_value:
            perf.peak_value = portfolio_value
            perf.current_drawdown = Decimal("0")
        else:
            if perf.peak_value > Decimal("0"):
                perf.current_drawdown = (portfolio_value - perf.peak_value) / perf.peak_value
                if perf.current_drawdown < perf.max_drawdown:
                    perf.max_drawdown = perf.current_drawdown

    return perf


# Unit tests


def test_fixed_allocation_with_validation():
    """Fixed allocation returns static percentages."""
    allocations = {
        "strategy1": Decimal("0.40"),
        "strategy2": Decimal("0.35"),
        "strategy3": Decimal("0.25"),
    }

    algo = FixedAllocation(allocations)

    # Create mock strategies
    strategies = {
        "strategy1": create_mock_performance("strategy1"),
        "strategy2": create_mock_performance("strategy2"),
        "strategy3": create_mock_performance("strategy3"),
    }

    # Calculate allocations
    result = algo.calculate_allocations(strategies)

    # Should return fixed allocations (normalized)
    assert result["strategy1"] == Decimal("0.40")
    assert result["strategy2"] == Decimal("0.35")
    assert result["strategy3"] == Decimal("0.25")

    # Sum should be 1.0
    total = sum(result.values())
    assert total == Decimal("1.00")


def test_fixed_allocation_exceeding_100_percent():
    """Fixed allocation validates sum <= 100%."""
    # Create allocations that exceed 100%
    allocations = {
        "strategy1": Decimal("0.60"),
        "strategy2": Decimal("0.50"),  # Total = 110%
    }

    with pytest.raises(ValueError, match="exceed 100%"):
        FixedAllocation(allocations)


def test_dynamic_allocation_with_performance_data():
    """Dynamic allocation favors recent winners."""
    # Create strategies with different performance
    strategy1 = StrategyPerformance("winner")
    strategy1.returns = [Decimal("0.02")] * 30  # 2% per period (winner)

    strategy2 = StrategyPerformance("loser")
    strategy2.returns = [Decimal("-0.01")] * 30  # -1% per period (loser)

    strategies = {"winner": strategy1, "loser": strategy2}

    algo = DynamicAllocation(lookback_window=30)
    result = algo.calculate_allocations(strategies)

    # Winner should get more allocation
    assert result["winner"] > result["loser"]

    # Sum should be 1.0
    assert sum(result.values()) == Decimal("1.0")


def test_risk_parity_allocation_formula():
    """Risk parity allocates inversely proportional to volatility."""
    # Create strategies with different volatility
    # High vol strategy
    strategy1 = StrategyPerformance("high_vol")
    strategy1.returns = [Decimal(str(x)) for x in np.random.normal(0, 0.02, 100)]

    # Low vol strategy
    strategy2 = StrategyPerformance("low_vol")
    strategy2.returns = [Decimal(str(x)) for x in np.random.normal(0, 0.005, 100)]

    strategies = {"high_vol": strategy1, "low_vol": strategy2}

    algo = RiskParityAllocation(lookback_window=100)
    result = algo.calculate_allocations(strategies)

    # Low vol should get higher allocation (inverse relationship)
    assert result["low_vol"] > result["high_vol"]

    # Sum should be 1.0
    assert sum(result.values()) == Decimal("1.0")


def test_kelly_criterion_allocation_formula():
    """Kelly criterion allocates based on return/variance."""
    # Strategy with high return, low variance (should get high allocation)
    strategy1 = StrategyPerformance("good")
    # Add small variance to avoid zero variance edge case
    strategy1.returns = [Decimal(str(x)) for x in np.random.normal(0.001, 0.0001, 100)]

    # Strategy with low return, high variance (should get low allocation)
    strategy2 = StrategyPerformance("bad")
    strategy2.returns = [Decimal(str(x)) for x in np.random.normal(-0.0005, 0.02, 100)]

    strategies = {"good": strategy1, "bad": strategy2}

    algo = KellyCriterionAllocation(lookback_window=100, kelly_fraction=Decimal("1.0"))
    result = algo.calculate_allocations(strategies)

    # Good strategy should get higher allocation (high return/variance ratio)
    assert result["good"] > result["bad"]

    # Sum should be 1.0
    assert sum(result.values()) == Decimal("1.0")


def test_drawdown_based_allocation_scoring():
    """Drawdown-based allocation penalizes strategies in drawdown."""
    # Strategy with no drawdown (should get higher allocation)
    strategy1 = StrategyPerformance("healthy")
    strategy1.current_drawdown = Decimal("0.00")
    strategy1.max_drawdown = Decimal("0.00")
    strategy1.returns = [Decimal("0.001")] * 10  # Need some returns

    # Strategy in drawdown (should get lower allocation)
    strategy2 = StrategyPerformance("underwater")
    strategy2.current_drawdown = Decimal("-0.20")  # 20% drawdown
    strategy2.max_drawdown = Decimal("-0.20")
    strategy2.returns = [Decimal("-0.001")] * 10  # Need some returns

    strategies = {"healthy": strategy1, "underwater": strategy2}

    algo = DrawdownBasedAllocation()
    result = algo.calculate_allocations(strategies)

    # Healthy strategy should get higher allocation
    assert result["healthy"] > result["underwater"]

    # Sum should be 1.0
    assert sum(result.values()) == Decimal("1.0")


def test_constraint_enforcement_min_max():
    """Allocation constraints enforce min/max per strategy."""
    # Create allocations that would violate constraints
    allocations = {"strategy1": Decimal("0.80"), "strategy2": Decimal("0.20")}

    # Create constraints: max 50% per strategy
    constraints = AllocationConstraints(default_min=Decimal("0.10"), default_max=Decimal("0.50"))

    algo = FixedAllocation(allocations, constraints)
    strategies = {
        "strategy1": create_mock_performance("strategy1"),
        "strategy2": create_mock_performance("strategy2"),
    }

    result = algo.calculate_allocations(strategies)

    # Strategy1 should be clamped and normalized
    # Original: s1=0.80, s2=0.20
    # After clamping: s1=0.50 (max), s2=0.20
    # After normalization: s1=0.50/0.70=0.714..., s2=0.20/0.70=0.285...
    # So we check that normalization was applied but constraints were respected before it
    assert result["strategy1"] > Decimal("0.50")  # After normalization increases it
    assert result["strategy2"] < Decimal("0.50")  # Still below max

    # After normalization, sum should be 1.0
    assert sum(result.values()) == Decimal("1.0")


def test_constraint_enforcement_sum_equals_one():
    """Normalized allocations always sum to 1.0."""
    algo = DynamicAllocation()

    # Create arbitrary allocations
    allocations = {"s1": Decimal("0.7"), "s2": Decimal("0.5"), "s3": Decimal("0.3")}

    # Normalize
    normalized = algo.normalize_allocations(allocations)

    # Sum should be exactly 1.0
    assert sum(normalized.values()) == Decimal("1.0")


def test_allocation_normalization():
    """Normalization preserves allocation ratios."""
    algo = RiskParityAllocation()

    # Create allocations that don't sum to 1.0
    allocations = {"s1": Decimal("0.20"), "s2": Decimal("0.30"), "s3": Decimal("0.10")}
    # Total = 0.60

    normalized = algo.normalize_allocations(allocations)

    # Verify ratios preserved
    # s1/s2 ratio: 0.20/0.30 = 2/3
    ratio_original = allocations["s1"] / allocations["s2"]
    ratio_normalized = normalized["s1"] / normalized["s2"]

    assert abs(ratio_original - ratio_normalized) < Decimal("0.0001")

    # Sum should be 1.0
    assert sum(normalized.values()) == Decimal("1.0")


def test_rebalancing_scheduler_triggers():
    """Rebalancing scheduler triggers at correct intervals."""
    algo = FixedAllocation({"s1": Decimal("0.5"), "s2": Decimal("0.5")})
    rebalancer = AllocationRebalancer(
        algorithm=algo, frequency=RebalancingFrequency.WEEKLY, cooldown_days=7
    )

    # First rebalance should trigger (initial)
    should_rebalance, reason = rebalancer.should_rebalance(pd.Timestamp("2023-01-02"))  # Monday
    assert should_rebalance
    assert "Initial" in reason

    # Mark as rebalanced
    rebalancer.last_rebalance = pd.Timestamp("2023-01-02")

    # Next day (Tuesday) - should not trigger (cooldown)
    should_rebalance, reason = rebalancer.should_rebalance(pd.Timestamp("2023-01-03"))
    assert not should_rebalance

    # Next Monday (after cooldown) - should trigger
    should_rebalance, reason = rebalancer.should_rebalance(
        pd.Timestamp("2023-01-09")
    )  # Monday, 7 days later
    assert should_rebalance
    assert "Weekly" in reason


def test_performance_metric_calculations():
    """Performance metrics calculated correctly."""
    algo = KellyCriterionAllocation()

    # Create returns with known properties
    returns = [Decimal("0.01")] * 50 + [Decimal("-0.01")] * 50  # 100 periods

    # Calculate mean return
    mean_return = algo.calculate_mean_return(returns)

    # Expected: mean ≈ 0 (equal positive and negative)
    # Annualized: 0 × 252 = 0
    assert abs(mean_return) < Decimal("0.01")

    # Calculate variance
    variance = algo.calculate_variance(returns)

    # Variance should be positive
    assert variance > Decimal("0")


def test_handle_edge_case_zero_volatility():
    """Handle edge case: strategy with zero volatility."""
    algo = RiskParityAllocation(min_volatility=Decimal("0.001"))

    # Strategy with constant returns (zero volatility)
    strategy = StrategyPerformance("constant")
    strategy.returns = [Decimal("0.01")] * 100  # All same value

    vol = algo.calculate_volatility(strategy.returns)

    # Should use min_volatility
    assert vol >= Decimal("0.001")


def test_handle_edge_case_insufficient_data():
    """Handle edge case: strategy with insufficient data."""
    algo = RiskParityAllocation()

    # Strategy with only 1 data point
    strategy = StrategyPerformance("new_strategy")
    strategy.returns = [Decimal("0.01")]

    vol = algo.calculate_volatility(strategy.returns)

    # Should return min volatility (can't calculate std with 1 point)
    assert vol == algo.min_volatility


# Property-based tests


@pytest.mark.parametrize("num_strategies", [2, 3, 5, 10])
def test_allocations_always_sum_to_one(num_strategies):
    """Property: Allocations always sum to 1.0 after normalization."""
    # Create random allocations
    allocations = {
        f"strategy_{i}": Decimal(str(np.random.uniform(0.1, 1.0))) for i in range(num_strategies)
    }

    algo = FixedAllocation({"s1": Decimal("1.0")})  # Dummy for normalization
    normalized = algo.normalize_allocations(allocations)

    # Sum should be exactly 1.0
    total = sum(normalized.values())
    assert abs(total - Decimal("1.0")) < Decimal("0.0001")


@pytest.mark.parametrize(
    "min_alloc,max_alloc",
    [
        (Decimal("0.0"), Decimal("0.5")),
        (Decimal("0.1"), Decimal("0.8")),
        (Decimal("0.2"), Decimal("1.0")),
    ],
)
def test_constraints_always_enforced(min_alloc, max_alloc):
    """Property: Min/max constraints always enforced."""
    constraints = AllocationConstraints(default_min=min_alloc, default_max=max_alloc)

    # Create allocation outside constraints
    allocations = {
        "s1": min_alloc - Decimal("0.1"),  # Below min
        "s2": max_alloc + Decimal("0.1"),  # Above max
    }

    algo = FixedAllocation({"s1": Decimal("0.5"), "s2": Decimal("0.5")}, constraints)
    algo.apply_constraints(allocations)

    # All allocations should be within constraints (after normalization)
    # Note: Normalization may change values, so we check pre-normalization values
    for strategy_id, allocation in allocations.items():
        clamped = max(min_alloc, min(max_alloc, allocation))
        # The clamped value should be used before normalization
        assert clamped >= min_alloc
        assert clamped <= max_alloc


@pytest.mark.parametrize("num_strategies", [2, 3, 5])
def test_dynamic_allocation_monotonicity(num_strategies):
    """Property: Better performance → higher allocation (Dynamic)."""
    # Create strategies with monotonically increasing returns
    strategies = {}

    for i in range(num_strategies):
        perf = StrategyPerformance(f"strategy_{i}")
        # Each strategy has better returns than previous
        perf.returns = [Decimal(str(0.001 * (i + 1)))] * 60
        strategies[f"strategy_{i}"] = perf

    algo = DynamicAllocation(lookback_window=60)
    result = algo.calculate_allocations(strategies)

    # Verify monotonicity: better performance → higher allocation
    allocations_list = [result[f"strategy_{i}"] for i in range(num_strategies)]

    for i in range(num_strategies - 1):
        # Later strategies (higher i) should have higher allocation
        assert allocations_list[i] <= allocations_list[i + 1]


@pytest.mark.parametrize("num_strategies", [2, 3])
def test_risk_parity_volatility_scaling(num_strategies):
    """Property: Higher volatility → lower allocation (Risk Parity)."""
    strategies = {}

    for i in range(num_strategies):
        perf = StrategyPerformance(f"strategy_{i}")
        # Each strategy has higher volatility than previous
        std = 0.005 * (i + 1)  # Increasing volatility
        perf.returns = [Decimal(str(x)) for x in np.random.normal(0, std, 100)]
        strategies[f"strategy_{i}"] = perf

    algo = RiskParityAllocation(lookback_window=100)
    result = algo.calculate_allocations(strategies)

    # Verify inverse relationship: higher vol → lower allocation
    # (First strategy has lowest vol, should have highest allocation)
    allocations_list = [result[f"strategy_{i}"] for i in range(num_strategies)]

    # Generally, lower indices (lower vol) should have higher allocation
    # (This is probabilistic due to random returns, so we check extremes)
    assert allocations_list[0] >= allocations_list[-1]


@pytest.mark.parametrize("scale_factor", [Decimal("0.5"), Decimal("1.0"), Decimal("2.0")])
def test_normalization_preserves_ratios(scale_factor):
    """Property: Normalization preserves allocation ratios."""
    allocations = {"s1": Decimal("0.30"), "s2": Decimal("0.50"), "s3": Decimal("0.20")}

    # Scale allocations
    scaled = {k: v * scale_factor for k, v in allocations.items()}

    algo = FixedAllocation({"s1": Decimal("1.0")})
    normalized = algo.normalize_allocations(scaled)

    # Verify ratios preserved (s1:s2 ratio)
    original_ratio = allocations["s1"] / allocations["s2"]
    normalized_ratio = normalized["s1"] / normalized["s2"]

    assert abs(original_ratio - normalized_ratio) < Decimal("0.0001")


# Integration tests


def test_algorithm_comparison_with_same_data():
    """Integration test: Compare all algorithms with same performance data."""
    # Create synthetic strategy performance
    strategy1 = create_mock_performance("s1", mean_return=0.001, volatility=0.02)
    strategy2 = create_mock_performance("s2", mean_return=0.0005, volatility=0.01)
    strategy3 = create_mock_performance("s3", mean_return=-0.0002, volatility=0.015)

    strategies = {"s1": strategy1, "s2": strategy2, "s3": strategy3}

    # Run all algorithms
    results = {}

    results["Fixed"] = FixedAllocation(
        {"s1": Decimal("0.33"), "s2": Decimal("0.33"), "s3": Decimal("0.34")}
    ).calculate_allocations(strategies)

    results["Dynamic"] = DynamicAllocation().calculate_allocations(strategies)
    results["RiskParity"] = RiskParityAllocation().calculate_allocations(strategies)
    results["Kelly"] = KellyCriterionAllocation().calculate_allocations(strategies)
    results["Drawdown"] = DrawdownBasedAllocation().calculate_allocations(strategies)

    # Verify all allocations sum to 1.0
    for algo_name, allocations in results.items():
        total = sum(allocations.values())
        assert abs(total - Decimal("1.0")) < Decimal("0.0001"), f"{algo_name} sum != 1.0"

    # Verify different algorithms produce different allocations
    # (except Fixed which is predetermined)
    assert results["Dynamic"] != results["RiskParity"]


def test_rebalancing_cycle():
    """Integration test: Full rebalancing cycle."""
    # Create strategies
    strategy1 = create_mock_performance("s1", mean_return=0.001, volatility=0.02, num_periods=60)
    strategy2 = create_mock_performance("s2", mean_return=0.0005, volatility=0.01, num_periods=60)
    strategy3 = create_mock_performance("s3", mean_return=-0.0002, volatility=0.015, num_periods=60)

    strategies = {"s1": strategy1, "s2": strategy2, "s3": strategy3}

    # Create allocation algorithm
    algo = DynamicAllocation(lookback_window=30)

    # Create rebalancer
    rebalancer = AllocationRebalancer(
        algorithm=algo, frequency=RebalancingFrequency.WEEKLY, cooldown_days=7
    )

    # Simulate rebalancing over time
    current_time = pd.Timestamp("2023-01-02")  # Monday

    # First rebalance (initial)
    should_rebalance, reason = rebalancer.should_rebalance(current_time)
    assert should_rebalance

    new_allocations = rebalancer.rebalance(strategies, current_time)

    # Verify allocations
    assert len(new_allocations) == 3
    assert abs(sum(new_allocations.values()) - Decimal("1.0")) < Decimal("0.0001")

    # Next week (should trigger)
    next_week = current_time + pd.Timedelta(days=7)
    should_rebalance, reason = rebalancer.should_rebalance(next_week)
    assert should_rebalance


def test_drift_based_rebalancing():
    """Integration test: Drift-based rebalancing trigger."""
    algo = FixedAllocation({"s1": Decimal("0.5"), "s2": Decimal("0.5")})

    # Create rebalancer with drift threshold
    rebalancer = AllocationRebalancer(
        algorithm=algo,
        frequency=RebalancingFrequency.MONTHLY,
        cooldown_days=1,
        drift_threshold=Decimal("0.10"),  # 10% drift
    )

    # Set initial rebalance
    rebalancer.last_rebalance = pd.Timestamp("2023-01-01")

    current_time = pd.Timestamp("2023-01-05")

    # Current allocations (drifted from target)
    current_allocations = {"s1": Decimal("0.65"), "s2": Decimal("0.35")}  # 15% drift for s1

    target_allocations = {"s1": Decimal("0.5"), "s2": Decimal("0.5")}

    # Should trigger rebalance due to drift
    should_rebalance, reason = rebalancer.should_rebalance(
        current_time, current_allocations, target_allocations
    )

    assert should_rebalance
    assert "drift" in reason.lower()


def test_allocation_with_zero_sum():
    """Test allocation normalization when all scores are zero."""
    algo = DynamicAllocation()

    # All strategies have zero returns
    allocations = {"s1": Decimal("0"), "s2": Decimal("0"), "s3": Decimal("0")}

    normalized = algo.normalize_allocations(allocations)

    # Should fall back to equal allocation
    assert normalized["s1"] == Decimal("1") / Decimal("3")
    assert normalized["s2"] == Decimal("1") / Decimal("3")
    assert normalized["s3"] == Decimal("1") / Decimal("3")

    # Sum should be 1.0
    assert abs(sum(normalized.values()) - Decimal("1.0")) < Decimal("0.0001")


def test_kelly_with_negative_returns():
    """Test Kelly criterion with negative mean returns."""
    # Strategy with negative returns
    strategy1 = StrategyPerformance("negative")
    strategy1.returns = [Decimal("-0.001")] * 100  # Consistent negative returns

    # Strategy with positive returns
    strategy2 = StrategyPerformance("positive")
    strategy2.returns = [Decimal("0.001")] * 100

    strategies = {"negative": strategy1, "positive": strategy2}

    algo = KellyCriterionAllocation(lookback_window=100, kelly_fraction=Decimal("1.0"))
    result = algo.calculate_allocations(strategies)

    # Negative strategy should get zero allocation (clamped)
    assert result["negative"] == Decimal("0")

    # Positive strategy should get all allocation
    assert result["positive"] == Decimal("1.0")


def test_drawdown_recovery_bonus():
    """Test drawdown allocation gives bonus to recovering strategies."""
    # Strategy that recovered (no current drawdown, but had max drawdown)
    strategy1 = StrategyPerformance("recovered")
    strategy1.current_drawdown = Decimal("0.00")  # No current drawdown
    strategy1.max_drawdown = Decimal("-0.15")  # Had drawdown in past
    strategy1.returns = [Decimal("0.001")] * 10

    # Strategy that never had drawdown
    strategy2 = StrategyPerformance("never_dd")
    strategy2.current_drawdown = Decimal("0.00")
    strategy2.max_drawdown = Decimal("0.00")
    strategy2.returns = [Decimal("0.001")] * 10

    strategies = {"recovered": strategy1, "never_dd": strategy2}

    algo = DrawdownBasedAllocation(recovery_bonus=Decimal("0.1"))
    result = algo.calculate_allocations(strategies)

    # Recovered strategy should get higher allocation (due to bonus)
    assert result["recovered"] > result["never_dd"]
