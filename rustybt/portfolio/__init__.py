"""Portfolio management module.

This module provides multi-strategy portfolio allocation and management
capabilities, including:

- PortfolioAllocator: Manage multiple strategies with isolated capital
- StrategyAllocation: Track individual strategy allocations
- StrategyPerformance: Monitor per-strategy performance metrics
- StrategyState: Lifecycle states for strategy management
- Capital allocation algorithms (Fixed, Dynamic, Risk Parity, Kelly, Drawdown-based)
- AllocationRebalancer: Automated rebalancing with configurable frequencies
- OrderAggregator: Aggregate and net orders across strategies to minimize costs
"""

from rustybt.portfolio.aggregator import (
    AggregatedOrder,
    NetOrderResult,
    OrderAggregator,
    OrderContribution,
    OrderDirection,
)
from rustybt.portfolio.allocation import (
    AllocationAlgorithm,
    AllocationConstraints,
    AllocationRebalancer,
    DrawdownBasedAllocation,
    DynamicAllocation,
    FixedAllocation,
    KellyCriterionAllocation,
    RebalancingFrequency,
    RiskParityAllocation,
)
from rustybt.portfolio.allocator import (
    PortfolioAllocator,
    StrategyAllocation,
    StrategyPerformance,
    StrategyState,
)

__all__ = [
    "AggregatedOrder",
    "AllocationAlgorithm",
    "AllocationConstraints",
    "AllocationRebalancer",
    "DrawdownBasedAllocation",
    "DynamicAllocation",
    "FixedAllocation",
    "KellyCriterionAllocation",
    "NetOrderResult",
    "OrderAggregator",
    "OrderContribution",
    "OrderDirection",
    "PortfolioAllocator",
    "RebalancingFrequency",
    "RiskParityAllocation",
    "StrategyAllocation",
    "StrategyPerformance",
    "StrategyState",
]
