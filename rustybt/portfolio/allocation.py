"""Capital allocation algorithms for multi-strategy portfolios.

This module provides various capital allocation algorithms including:
- FixedAllocation: Static percentage allocation
- DynamicAllocation: Performance-based allocation
- RiskParityAllocation: Volatility-weighted allocation
- KellyCriterionAllocation: Growth-optimal allocation
- DrawdownBasedAllocation: Drawdown-aware allocation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import structlog

if TYPE_CHECKING:
    from rustybt.portfolio.allocator import StrategyPerformance

logger = structlog.get_logger()


class AllocationAlgorithm(ABC):
    """Abstract base class for capital allocation algorithms.

    All allocation algorithms must:
    1. Implement calculate_allocations() method
    2. Return allocations as Dict[strategy_id, allocation_pct]
    3. Ensure allocations sum to <= 1.0 (100%)
    4. Handle edge cases (zero volatility, insufficient data)
    5. Use Decimal precision for all calculations
    """

    def __init__(self, constraints: AllocationConstraints | None = None):
        """Initialize allocation algorithm.

        Args:
            constraints: Allocation constraints (min/max per strategy)
        """
        self.constraints = constraints or AllocationConstraints()

    @abstractmethod
    def calculate_allocations(
        self, strategies: dict[str, StrategyPerformance]
    ) -> dict[str, Decimal]:
        """Calculate allocation percentages for each strategy.

        Args:
            strategies: Dict mapping strategy_id to StrategyPerformance

        Returns:
            Dict mapping strategy_id to allocation_pct (0.0 to 1.0)
            Sum of allocations must be <= 1.0
        """
        pass

    def apply_constraints(self, allocations: dict[str, Decimal]) -> dict[str, Decimal]:
        """Apply min/max constraints and normalize.

        Args:
            allocations: Unconstrained allocations

        Returns:
            Constrained and normalized allocations
        """
        # Apply per-strategy min/max constraints
        constrained = {}

        for strategy_id, allocation in allocations.items():
            # Get constraints for this strategy
            min_alloc = self.constraints.get_min(strategy_id)
            max_alloc = self.constraints.get_max(strategy_id)

            # Clamp to constraints
            constrained_alloc = max(min_alloc, min(max_alloc, allocation))
            constrained[strategy_id] = constrained_alloc

            # Log if constrained
            if constrained_alloc != allocation:
                logger.info(
                    "allocation_constrained",
                    strategy_id=strategy_id,
                    original=f"{float(allocation):.1%}",
                    constrained=f"{float(constrained_alloc):.1%}",
                    min=f"{float(min_alloc):.1%}",
                    max=f"{float(max_alloc):.1%}",
                )

        # Normalize to sum to 1.0
        normalized = self.normalize_allocations(constrained)

        return normalized

    def normalize_allocations(self, allocations: dict[str, Decimal]) -> dict[str, Decimal]:
        """Normalize allocations to sum to 1.0.

        Args:
            allocations: Allocations that may not sum to 1.0

        Returns:
            Normalized allocations summing to 1.0
        """
        total = sum(allocations.values())

        if total == Decimal("0"):
            # Equal allocation fallback
            n = len(allocations)
            return {strategy_id: Decimal("1") / Decimal(str(n)) for strategy_id in allocations}

        # Normalize to sum to 1.0
        normalized = {
            strategy_id: allocation / total for strategy_id, allocation in allocations.items()
        }

        logger.debug(
            "allocations_normalized",
            original_sum=f"{float(total):.4f}",
            normalized_sum="1.0000",
        )

        return normalized


@dataclass
class AllocationConstraints:
    """Constraints for capital allocation.

    Enforces:
    - Global min/max allocation per strategy
    - Per-strategy overrides
    - Sum <= 1.0 constraint
    """

    default_min: Decimal = field(default_factory=lambda: Decimal("0.0"))
    default_max: Decimal = field(default_factory=lambda: Decimal("1.0"))
    strategy_min: dict[str, Decimal] = field(default_factory=dict)
    strategy_max: dict[str, Decimal] = field(default_factory=dict)

    def get_min(self, strategy_id: str) -> Decimal:
        """Get minimum allocation for strategy."""
        return self.strategy_min.get(strategy_id, self.default_min)

    def get_max(self, strategy_id: str) -> Decimal:
        """Get maximum allocation for strategy."""
        return self.strategy_max.get(strategy_id, self.default_max)


class FixedAllocation(AllocationAlgorithm):
    """Fixed allocation: static percentages per strategy.

    Use case: Conservative allocation when you have predefined strategy weights.

    Example:
        strategy1: 40%
        strategy2: 30%
        strategy3: 30%
    """

    def __init__(
        self,
        allocations: dict[str, Decimal],
        constraints: AllocationConstraints | None = None,
    ):
        """Initialize fixed allocation.

        Args:
            allocations: Fixed allocation percentages per strategy
            constraints: Optional constraints

        Raises:
            ValueError: If allocations sum to > 100%
        """
        super().__init__(constraints)

        # Validate allocations sum <= 1.0
        total = sum(allocations.values())
        if total > Decimal("1"):
            raise ValueError(f"Fixed allocations exceed 100%: {float(total):.1%}")

        self.allocations = allocations

        logger.info(
            "fixed_allocation_initialized",
            num_strategies=len(allocations),
            total_allocation=f"{float(total):.1%}",
            allocations={k: f"{float(v):.1%}" for k, v in allocations.items()},
        )

    def calculate_allocations(
        self, strategies: dict[str, StrategyPerformance]
    ) -> dict[str, Decimal]:
        """Return fixed allocations (ignores performance)."""
        # Only return allocations for active strategies
        active_allocations = {
            strategy_id: self.allocations[strategy_id]
            for strategy_id in strategies
            if strategy_id in self.allocations
        }

        # Apply constraints
        constrained = self.apply_constraints(active_allocations)

        return constrained


class DynamicAllocation(AllocationAlgorithm):
    """Dynamic allocation: adjust based on recent performance.

    Formula:
        score_i = (return_i - min_return) / (max_return - min_return)
        allocation_i = score_i / Σ(score_j)

    Winners get more capital, losers get less.

    Use case: Momentum-based allocation favoring recent winners.
    """

    def __init__(
        self,
        lookback_window: int = 60,  # 60 days ~3 months
        min_allocation: Decimal = Decimal("0.05"),  # 5% minimum
        constraints: AllocationConstraints | None = None,
    ):
        """Initialize dynamic allocation.

        Args:
            lookback_window: Number of periods for performance calculation
            min_allocation: Minimum allocation for any strategy (avoids zero allocation)
            constraints: Optional constraints
        """
        super().__init__(constraints)
        self.lookback_window = lookback_window
        self.min_allocation = min_allocation

        logger.info(
            "dynamic_allocation_initialized",
            lookback_window=lookback_window,
            min_allocation=f"{float(min_allocation):.1%}",
        )

    def calculate_allocations(
        self, strategies: dict[str, StrategyPerformance]
    ) -> dict[str, Decimal]:
        """Calculate allocations based on recent returns."""
        # Calculate returns for each strategy (over lookback window)
        returns_map: dict[str, Decimal] = {}

        for strategy_id, perf in strategies.items():
            # Use recent returns
            recent_returns = perf.returns[-self.lookback_window :]

            if len(recent_returns) > 0:
                # Calculate cumulative return over window
                cumulative_return = sum(recent_returns)
                returns_map[strategy_id] = cumulative_return
            else:
                # No data - use zero
                returns_map[strategy_id] = Decimal("0")

        # Calculate scores (normalize to 0-1 range)
        if len(returns_map) == 0:
            return {}

        min_return = min(returns_map.values())
        max_return = max(returns_map.values())

        scores: dict[str, Decimal] = {}

        if max_return > min_return:
            # Normalize to 0-1 range
            for strategy_id, ret in returns_map.items():
                score = (ret - min_return) / (max_return - min_return)
                # Add minimum allocation to avoid zero
                scores[strategy_id] = score + self.min_allocation
        else:
            # All returns equal - use equal weighting
            for strategy_id in returns_map:
                scores[strategy_id] = Decimal("1")

        # Normalize scores to sum to 1.0
        allocations = self.normalize_allocations(scores)

        # Apply constraints
        constrained = self.apply_constraints(allocations)

        logger.info(
            "dynamic_allocations_calculated",
            num_strategies=len(constrained),
            returns_range=f"{float(min_return):.2%} to {float(max_return):.2%}",
            allocations={k: f"{float(v):.1%}" for k, v in constrained.items()},
        )

        return constrained


class RiskParityAllocation(AllocationAlgorithm):
    """Risk parity allocation: allocate inversely proportional to volatility.

    Formula:
        w_i = (1/σ_i) / Σ(1/σ_j)

    Where σ_i is the volatility (standard deviation of returns) of strategy i.

    Equal risk contribution: each strategy contributes equal volatility to portfolio.

    Use case: Diversified allocation balancing risk across strategies.
    """

    def __init__(
        self,
        lookback_window: int = 252,  # 1 year daily data
        min_volatility: Decimal = Decimal("0.001"),  # Minimum vol to avoid division by zero
        constraints: AllocationConstraints | None = None,
    ):
        """Initialize risk parity allocation.

        Args:
            lookback_window: Number of periods for volatility calculation
            min_volatility: Minimum volatility threshold (avoids division by zero)
            constraints: Optional constraints
        """
        super().__init__(constraints)
        self.lookback_window = lookback_window
        self.min_volatility = min_volatility

        logger.info(
            "risk_parity_allocation_initialized",
            lookback_window=lookback_window,
            min_volatility=f"{float(min_volatility):.4f}",
        )

    def calculate_volatility(self, returns: list[Decimal]) -> Decimal:
        """Calculate annualized volatility from returns.

        Formula:
            σ_annual = std(returns) × sqrt(252)

        Args:
            returns: List of period returns

        Returns:
            Annualized volatility
        """
        if len(returns) < 2:
            return self.min_volatility

        # Use recent returns (lookback window)
        recent_returns = returns[-self.lookback_window :]

        # Convert to numpy for efficient calculation
        returns_array = np.array([float(r) for r in recent_returns])

        # Calculate standard deviation (sample std with ddof=1)
        std = np.std(returns_array, ddof=1)

        # Annualize (assume daily data, 252 trading days)
        annualized_std = std * np.sqrt(252)

        # Ensure minimum volatility
        volatility = max(Decimal(str(annualized_std)), self.min_volatility)

        return volatility

    def calculate_allocations(
        self, strategies: dict[str, StrategyPerformance]
    ) -> dict[str, Decimal]:
        """Calculate risk parity allocations (inverse volatility weighting)."""
        # Calculate volatility for each strategy
        volatilities: dict[str, Decimal] = {}

        for strategy_id, perf in strategies.items():
            vol = self.calculate_volatility(perf.returns)
            volatilities[strategy_id] = vol

        # Calculate inverse volatility weights
        # w_i = (1/σ_i) / Σ(1/σ_j)
        inverse_vols: dict[str, Decimal] = {}

        for strategy_id, vol in volatilities.items():
            if vol > Decimal("0"):
                inverse_vols[strategy_id] = Decimal("1") / vol
            else:
                inverse_vols[strategy_id] = Decimal("0")

        # Normalize to sum to 1.0
        allocations = self.normalize_allocations(inverse_vols)

        # Apply constraints
        constrained = self.apply_constraints(allocations)

        logger.info(
            "risk_parity_allocations_calculated",
            num_strategies=len(constrained),
            volatilities={k: f"{float(v):.2%}" for k, v in volatilities.items()},
            allocations={k: f"{float(v):.1%}" for k, v in constrained.items()},
        )

        return constrained


class KellyCriterionAllocation(AllocationAlgorithm):
    """Kelly criterion allocation: allocate based on optimal growth.

    Formula:
        f*_i = μ_i / σ²_i

    Where:
        μ_i = expected return (mean return)
        σ²_i = variance of returns

    Kelly fraction maximizes long-term geometric growth rate.

    Use case: Aggressive growth-focused allocation (often fractional Kelly used: f*/2).
    """

    def __init__(
        self,
        lookback_window: int = 252,  # 1 year
        kelly_fraction: Decimal = Decimal("0.5"),  # Half-Kelly (conservative)
        min_variance: Decimal = Decimal("0.0001"),  # Minimum variance to avoid division by zero
        constraints: AllocationConstraints | None = None,
    ):
        """Initialize Kelly criterion allocation.

        Args:
            lookback_window: Number of periods for return/variance calculation
            kelly_fraction: Fraction of Kelly to use (0.5 = half-Kelly, conservative)
            min_variance: Minimum variance threshold
            constraints: Optional constraints
        """
        super().__init__(constraints)
        self.lookback_window = lookback_window
        self.kelly_fraction = kelly_fraction
        self.min_variance = min_variance

        logger.info(
            "kelly_criterion_allocation_initialized",
            lookback_window=lookback_window,
            kelly_fraction=f"{float(kelly_fraction):.1%}",
            min_variance=f"{float(min_variance):.6f}",
        )

    def calculate_mean_return(self, returns: list[Decimal]) -> Decimal:
        """Calculate annualized mean return.

        Args:
            returns: List of period returns

        Returns:
            Annualized mean return
        """
        if len(returns) < 1:
            return Decimal("0")

        # Use recent returns
        recent_returns = returns[-self.lookback_window :]

        # Calculate mean
        returns_array = np.array([float(r) for r in recent_returns])
        mean = np.mean(returns_array)

        # Annualize (assume daily data, 252 trading days)
        annualized_mean = Decimal(str(mean)) * Decimal("252")

        return annualized_mean

    def calculate_variance(self, returns: list[Decimal]) -> Decimal:
        """Calculate annualized variance.

        Args:
            returns: List of period returns

        Returns:
            Annualized variance
        """
        if len(returns) < 2:
            return self.min_variance

        # Use recent returns
        recent_returns = returns[-self.lookback_window :]

        # Calculate variance
        returns_array = np.array([float(r) for r in recent_returns])
        variance = np.var(returns_array, ddof=1)  # Sample variance

        # Annualize (variance scales linearly with time for i.i.d. returns)
        annualized_variance = Decimal(str(variance)) * Decimal("252")

        # Ensure minimum variance
        variance_final = max(annualized_variance, self.min_variance)

        return variance_final

    def calculate_allocations(
        self, strategies: dict[str, StrategyPerformance]
    ) -> dict[str, Decimal]:
        """Calculate Kelly criterion allocations.

        Formula: f*_i = μ_i / σ²_i
        """
        # Calculate Kelly fractions for each strategy
        kelly_fractions: dict[str, Decimal] = {}

        for strategy_id, perf in strategies.items():
            # Calculate mean return and variance
            mean_return = self.calculate_mean_return(perf.returns)
            variance = self.calculate_variance(perf.returns)

            if variance > Decimal("0"):
                # Kelly fraction = μ / σ²
                kelly_f = mean_return / variance

                # Apply fractional Kelly (e.g., half-Kelly)
                kelly_f = kelly_f * self.kelly_fraction

                # Clamp to [0, 1] range (no negative allocations, max 100%)
                kelly_f = max(Decimal("0"), min(kelly_f, Decimal("1")))

                kelly_fractions[strategy_id] = kelly_f
            else:
                kelly_fractions[strategy_id] = Decimal("0")

        # Normalize to sum to 1.0
        allocations = self.normalize_allocations(kelly_fractions)

        # Apply constraints
        constrained = self.apply_constraints(allocations)

        logger.info(
            "kelly_criterion_allocations_calculated",
            num_strategies=len(constrained),
            kelly_fraction=f"{float(self.kelly_fraction):.1%}",
            allocations={k: f"{float(v):.1%}" for k, v in constrained.items()},
        )

        return constrained


class DrawdownBasedAllocation(AllocationAlgorithm):
    """Drawdown-based allocation: reduce allocation to strategies in drawdown.

    Formula:
        score_i = 1 / (1 + |DD_i|)

    Where DD_i is the current drawdown of strategy i (negative value).

    Strategies with larger drawdowns get lower scores (less allocation).
    Recovering strategies get increasing allocation.

    Use case: Risk-averse allocation reducing exposure to underperforming strategies.
    """

    def __init__(
        self,
        max_drawdown_threshold: Decimal = Decimal("0.20"),  # 20% max drawdown
        recovery_bonus: Decimal = Decimal("0.1"),  # 10% bonus for recovering strategies
        constraints: AllocationConstraints | None = None,
    ):
        """Initialize drawdown-based allocation.

        Args:
            max_drawdown_threshold: Drawdown threshold for penalty (20% = -0.20)
            recovery_bonus: Bonus allocation for strategies recovering from drawdown
            constraints: Optional constraints
        """
        super().__init__(constraints)
        self.max_drawdown_threshold = max_drawdown_threshold
        self.recovery_bonus = recovery_bonus

        logger.info(
            "drawdown_based_allocation_initialized",
            max_drawdown_threshold=f"{float(max_drawdown_threshold):.1%}",
            recovery_bonus=f"{float(recovery_bonus):.1%}",
        )

    def calculate_allocations(
        self, strategies: dict[str, StrategyPerformance]
    ) -> dict[str, Decimal]:
        """Calculate drawdown-based allocations.

        Strategies with smaller drawdowns get higher allocation.
        """
        # Calculate scores based on drawdown
        scores: dict[str, Decimal] = {}

        for strategy_id, perf in strategies.items():
            # Get current drawdown (negative value)
            current_dd = perf.current_drawdown

            # Score formula: 1 / (1 + |DD|)
            # Lower drawdown → higher score → higher allocation
            if current_dd < Decimal("0"):
                # In drawdown
                score = Decimal("1") / (Decimal("1") + abs(current_dd))
            else:
                # No drawdown - base score of 1.0
                score = Decimal("1")

                # Check if recovering (was in drawdown recently)
                max_dd = perf.max_drawdown
                if max_dd < Decimal("0"):
                    # Add recovery bonus (strategy has recovered)
                    score = score + self.recovery_bonus

            scores[strategy_id] = score

            logger.debug(
                "drawdown_score_calculated",
                strategy_id=strategy_id,
                current_drawdown=f"{float(current_dd):.2%}",
                max_drawdown=f"{float(perf.max_drawdown):.2%}",
                score=f"{float(score):.3f}",
            )

        # Normalize scores to sum to 1.0
        allocations = self.normalize_allocations(scores)

        # Apply constraints
        constrained = self.apply_constraints(allocations)

        logger.info(
            "drawdown_based_allocations_calculated",
            num_strategies=len(constrained),
            allocations={k: f"{float(v):.1%}" for k, v in constrained.items()},
        )

        return constrained


class RebalancingFrequency(Enum):
    """Rebalancing frequency options."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class AllocationRebalancer:
    """Rebalancing scheduler for allocation algorithms.

    Manages:
    - Rebalancing frequency
    - Cooldown periods (prevent excessive rebalancing)
    - Threshold-based triggers (rebalance if allocation drifts > X%)
    """

    def __init__(
        self,
        algorithm: AllocationAlgorithm,
        frequency: RebalancingFrequency = RebalancingFrequency.MONTHLY,
        cooldown_days: int = 7,  # Minimum days between rebalances
        drift_threshold: Decimal | None = None,  # Rebalance if drift > threshold
    ):
        """Initialize rebalancing scheduler.

        Args:
            algorithm: Allocation algorithm to use
            frequency: Rebalancing frequency
            cooldown_days: Minimum days between rebalances
            drift_threshold: Optional drift threshold for threshold-based rebalancing
        """
        self.algorithm = algorithm
        self.frequency = frequency
        self.cooldown_days = cooldown_days
        self.drift_threshold = drift_threshold

        self.last_rebalance: pd.Timestamp | None = None

        logger.info(
            "allocation_rebalancer_initialized",
            algorithm=type(algorithm).__name__,
            frequency=frequency.value,
            cooldown_days=cooldown_days,
            drift_threshold=f"{float(drift_threshold):.1%}" if drift_threshold else None,
        )

    def should_rebalance(
        self,
        current_time: pd.Timestamp,
        current_allocations: dict[str, Decimal] | None = None,
        target_allocations: dict[str, Decimal] | None = None,
    ) -> tuple[bool, str]:
        """Check if rebalancing should occur.

        Args:
            current_time: Current timestamp
            current_allocations: Current allocations (for drift calculation)
            target_allocations: Target allocations (for drift calculation)

        Returns:
            Tuple of (should_rebalance, reason)
        """
        # Check cooldown period
        if self.last_rebalance is not None:
            days_since_last = (current_time - self.last_rebalance).days
            if days_since_last < self.cooldown_days:
                return False, f"Cooldown period ({days_since_last}/{self.cooldown_days} days)"

        # Check frequency-based trigger
        if self.last_rebalance is None:
            return True, "Initial rebalancing"

        if self.frequency == RebalancingFrequency.DAILY:
            # Rebalance daily
            return True, "Daily rebalancing"

        elif self.frequency == RebalancingFrequency.WEEKLY:
            # Rebalance weekly (Monday)
            if current_time.dayofweek == 0:  # Monday
                days_since = (current_time - self.last_rebalance).days
                if days_since >= 7:
                    return True, "Weekly rebalancing (Monday)"

        elif (
            self.frequency == RebalancingFrequency.MONTHLY
            and current_time.day <= 3
            and current_time.month != self.last_rebalance.month
        ):
            # Rebalance monthly (first business day)
            return True, "Monthly rebalancing (first of month)"

        # Check drift-based trigger
        if (
            self.drift_threshold is not None
            and current_allocations is not None
            and target_allocations is not None
        ):
            # Calculate maximum drift
            max_drift = self._calculate_max_drift(current_allocations, target_allocations)

            if max_drift > self.drift_threshold:
                drift_msg = (
                    f"Allocation drift ({float(max_drift):.1%} > {float(self.drift_threshold):.1%})"
                )
                return True, drift_msg

        return False, "No trigger conditions met"

    def _calculate_max_drift(
        self, current: dict[str, Decimal], target: dict[str, Decimal]
    ) -> Decimal:
        """Calculate maximum allocation drift.

        Args:
            current: Current allocations
            target: Target allocations

        Returns:
            Maximum absolute drift across all strategies
        """
        max_drift = Decimal("0")

        # Check all strategies in either current or target
        all_strategies = set(current.keys()) | set(target.keys())

        for strategy_id in all_strategies:
            current_alloc = current.get(strategy_id, Decimal("0"))
            target_alloc = target.get(strategy_id, Decimal("0"))

            drift = abs(current_alloc - target_alloc)

            if drift > max_drift:
                max_drift = drift

        return max_drift

    def rebalance(
        self, strategies: dict[str, StrategyPerformance], current_time: pd.Timestamp
    ) -> dict[str, Decimal]:
        """Execute rebalancing.

        Args:
            strategies: Strategy performance data
            current_time: Current timestamp

        Returns:
            New target allocations
        """
        # Calculate new allocations
        new_allocations = self.algorithm.calculate_allocations(strategies)

        # Update last rebalance time
        self.last_rebalance = current_time

        logger.info(
            "rebalancing_executed",
            algorithm=type(self.algorithm).__name__,
            timestamp=str(current_time),
            num_strategies=len(new_allocations),
            allocations={k: f"{float(v):.1%}" for k, v in new_allocations.items()},
        )

        return new_allocations
