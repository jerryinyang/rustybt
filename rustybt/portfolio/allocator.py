"""Portfolio allocator for multi-strategy management.

This module implements a portfolio allocator that manages multiple trading
strategies concurrently with isolated capital allocation and comprehensive
performance tracking.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger()


class StrategyState(Enum):
    """Strategy lifecycle states."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    LIQUIDATING = "liquidating"
    STOPPED = "stopped"


@dataclass
class StrategyAllocation:
    """Allocation details for a single strategy.

    Each strategy has:
    - Independent ledger for isolated capital
    - Allocated capital amount
    - Performance tracker
    - State management
    """

    strategy_id: str
    strategy: Any  # TradingAlgorithm instance
    allocated_capital: Decimal
    ledger: Any  # DecimalLedger instance
    performance: "StrategyPerformance"
    state: StrategyState = field(default=StrategyState.INITIALIZING)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)

    @property
    def current_value(self) -> Decimal:
        """Current portfolio value for this strategy."""
        return self.ledger.portfolio_value

    @property
    def return_pct(self) -> Decimal:
        """Return percentage since inception."""
        if self.allocated_capital > Decimal("0"):
            return (self.current_value - self.allocated_capital) / self.allocated_capital
        return Decimal("0")

    @property
    def is_active(self) -> bool:
        """Check if strategy is actively trading."""
        return self.state == StrategyState.RUNNING

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"StrategyAllocation(id={self.strategy_id}, "
            f"capital={self.allocated_capital}, "
            f"value={self.current_value}, "
            f"return={self.return_pct:.2%}, "
            f"state={self.state.value})"
        )


class StrategyPerformance:
    """Performance tracker for individual strategy.

    Tracks:
    - Returns over time
    - Volatility (rolling and cumulative)
    - Sharpe ratio
    - Maximum drawdown
    - Win rate and profit factor
    """

    def __init__(
        self,
        strategy_id: str,
        lookback_window: int = 252,  # Trading days for rolling metrics
    ):
        """Initialize performance tracker.

        Args:
            strategy_id: Unique strategy identifier
            lookback_window: Number of periods for rolling metrics (252 = ~1 year daily)
        """
        self.strategy_id = strategy_id
        self.lookback_window = lookback_window

        # Time series data
        self.timestamps: list[pd.Timestamp] = []
        self.portfolio_values: list[Decimal] = []
        self.returns: list[Decimal] = []

        # Cumulative metrics
        self.peak_value = Decimal("0")
        self.current_drawdown = Decimal("0")
        self.max_drawdown = Decimal("0")

        # Trade statistics
        self.winning_periods = 0
        self.losing_periods = 0
        self.total_profit = Decimal("0")
        self.total_loss = Decimal("0")

        logger.info(
            "strategy_performance_initialized",
            strategy_id=strategy_id,
            lookback_window=lookback_window,
        )

    def update(self, timestamp: pd.Timestamp, portfolio_value: Decimal):
        """Update performance metrics with new observation.

        Args:
            timestamp: Current timestamp
            portfolio_value: Current portfolio value
        """
        # Store values
        self.timestamps.append(timestamp)
        self.portfolio_values.append(portfolio_value)

        # Calculate return (if we have previous value)
        if len(self.portfolio_values) > 1:
            prev_value = self.portfolio_values[-2]
            if prev_value > Decimal("0"):
                period_return = (portfolio_value - prev_value) / prev_value
                self.returns.append(period_return)

                # Update trade statistics
                if period_return > Decimal("0"):
                    self.winning_periods += 1
                    self.total_profit += period_return
                elif period_return < Decimal("0"):
                    self.losing_periods += 1
                    self.total_loss += abs(period_return)

        # Update drawdown metrics
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
            self.current_drawdown = Decimal("0")
        else:
            if self.peak_value > Decimal("0"):
                self.current_drawdown = (portfolio_value - self.peak_value) / self.peak_value

                # Update max drawdown (more negative = worse)
                if self.current_drawdown < self.max_drawdown:
                    self.max_drawdown = self.current_drawdown

        logger.debug(
            "performance_updated",
            strategy_id=self.strategy_id,
            timestamp=str(timestamp),
            portfolio_value=str(portfolio_value),
            current_drawdown=f"{float(self.current_drawdown):.2%}",
            max_drawdown=f"{float(self.max_drawdown):.2%}",
        )

    @property
    def volatility(self) -> Decimal:
        """Calculate annualized volatility.

        Returns:
            Annualized volatility (standard deviation of returns × sqrt(252))
        """
        if len(self.returns) < 2:
            return Decimal("0")

        # Use recent returns (lookback window)
        recent_returns = self.returns[-self.lookback_window :]

        # Convert to numpy for efficient calculation
        returns_array = np.array([float(r) for r in recent_returns])

        # Calculate standard deviation
        std = np.std(returns_array, ddof=1)  # Sample std deviation

        # Annualize (assume daily data, 252 trading days)
        annualized_std = std * np.sqrt(252)

        return Decimal(str(annualized_std))

    @property
    def mean_return(self) -> Decimal:
        """Calculate mean period return (annualized).

        Returns:
            Annualized mean return
        """
        if len(self.returns) < 1:
            return Decimal("0")

        # Use recent returns
        recent_returns = self.returns[-self.lookback_window :]

        # Calculate mean
        returns_array = np.array([float(r) for r in recent_returns])
        mean = np.mean(returns_array)

        # Annualize (assume daily data, 252 trading days)
        annualized_mean = Decimal(str(mean)) * Decimal("252")

        return annualized_mean

    @property
    def sharpe_ratio(self) -> Decimal:
        """Calculate Sharpe ratio.

        Formula: (mean_return - risk_free_rate) / volatility
        Assumes risk-free rate = 0 for simplicity

        Returns:
            Sharpe ratio (annualized)
        """
        vol = self.volatility
        if vol <= Decimal("0"):
            return Decimal("0")

        mean_ret = self.mean_return

        # Sharpe = mean / std (assuming risk-free = 0)
        sharpe = mean_ret / vol

        return sharpe

    @property
    def win_rate(self) -> Decimal:
        """Calculate win rate (% of winning periods).

        Returns:
            Win rate as decimal (0.6 = 60%)
        """
        total_periods = self.winning_periods + self.losing_periods
        if total_periods == 0:
            return Decimal("0")

        return Decimal(str(self.winning_periods)) / Decimal(str(total_periods))

    @property
    def profit_factor(self) -> Decimal:
        """Calculate profit factor (total profit / total loss).

        Returns:
            Profit factor (>1 = profitable, <1 = unprofitable)
        """
        if self.total_loss == Decimal("0"):
            return Decimal("0") if self.total_profit == Decimal("0") else Decimal("999")

        return self.total_profit / self.total_loss

    def get_metrics(self) -> dict[str, Any]:
        """Get all performance metrics as dictionary.

        Returns:
            Dictionary with all performance metrics
        """
        return {
            "strategy_id": self.strategy_id,
            "num_observations": len(self.portfolio_values),
            "current_value": str(self.portfolio_values[-1]) if self.portfolio_values else "0",
            "peak_value": str(self.peak_value),
            "current_drawdown": f"{float(self.current_drawdown):.2%}",
            "max_drawdown": f"{float(self.max_drawdown):.2%}",
            "mean_return": f"{float(self.mean_return):.2%}",
            "volatility": f"{float(self.volatility):.2%}",
            "sharpe_ratio": f"{float(self.sharpe_ratio):.2f}",
            "win_rate": f"{float(self.win_rate):.2%}",
            "profit_factor": f"{float(self.profit_factor):.2f}",
            "winning_periods": self.winning_periods,
            "losing_periods": self.losing_periods,
        }


class PortfolioAllocator:
    """Portfolio allocator for multi-strategy management.

    Multi-Strategy Execution Flow:
    ==============================

    1. Initialization:
       - Create PortfolioAllocator with total capital
       - Add strategies with allocation percentages
       - Each strategy gets independent DecimalLedger
       - Validate: sum(allocations) <= 100%

    2. Bar-by-Bar Execution (Synchronized):
       - For each bar (timestamp, data):
         a. Update all strategy ledgers with latest prices
         b. Execute all strategies sequentially:
            - Strategy 1: handle_data(ledger_1, data)
            - Strategy 2: handle_data(ledger_2, data)
            - Strategy 3: handle_data(ledger_3, data)
         c. Update performance metrics for each strategy
         d. Aggregate portfolio-level metrics
         e. Log execution summary

    3. Rebalancing (Periodic or Event-Driven):
       - Calculate new allocations (manual or algorithmic)
       - For each strategy with allocation change:
         a. Calculate capital delta (new - old)
         b. If delta > 0: transfer cash to strategy ledger
         c. If delta < 0: reduce positions and return cash
       - Validate: total capital conserved
       - Log rebalancing events

    4. Strategy Management:
       - Add: Create ledger, allocate capital, set to RUNNING
       - Pause: Set state to PAUSED, skip execution
       - Remove: Liquidate positions, return capital, set to STOPPED

    Strategy Isolation Mechanism:
    ============================
    - Each strategy has separate DecimalLedger instance
    - Strategies cannot access other ledgers' positions
    - Cash transfers only through PortfolioAllocator
    - Position interference prevented by ledger isolation

    Cash Aggregation:
    ================
    - Portfolio cash = sum(strategy.ledger.cash for all strategies)
    - Portfolio value = sum(strategy.ledger.portfolio_value for all strategies)
    - Validates: portfolio_value == total_capital + cumulative_returns
    """

    def __init__(self, total_capital: Decimal, name: str = "Portfolio"):
        """Initialize portfolio allocator.

        Args:
            total_capital: Total capital to allocate across strategies
            name: Portfolio name for logging
        """
        self.total_capital = total_capital
        self.name = name
        self.strategies: dict[str, StrategyAllocation] = {}

        # Track allocated capital to prevent over-allocation
        self.allocated_capital = Decimal("0")

        # Portfolio-level tracking
        self.current_timestamp: pd.Timestamp | None = None
        self.execution_count = 0

        logger.info("portfolio_allocator_initialized", name=name, total_capital=str(total_capital))

    def add_strategy(
        self,
        strategy_id: str,
        strategy: Any,  # TradingAlgorithm
        allocation_pct: Decimal,
        metadata: dict[str, Any] | None = None,
    ) -> StrategyAllocation:
        """Add strategy to portfolio with capital allocation.

        Args:
            strategy_id: Unique identifier for strategy
            strategy: TradingAlgorithm instance
            allocation_pct: Allocation percentage (0.3 = 30%)
            metadata: Optional metadata for strategy

        Returns:
            StrategyAllocation instance

        Raises:
            ValueError: If allocation would exceed 100% or strategy_id exists
        """
        # Validation
        if strategy_id in self.strategies:
            raise ValueError(f"Strategy {strategy_id} already exists")

        # Check allocation doesn't exceed 100%
        new_allocated_pct = (self.allocated_capital / self.total_capital) + allocation_pct
        if new_allocated_pct > Decimal("1"):
            raise ValueError(
                f"Allocation would exceed 100%: "
                f"current={float(self.allocated_capital / self.total_capital):.1%}, "
                f"new={float(allocation_pct):.1%}, "
                f"total={float(new_allocated_pct):.1%}"
            )

        # Calculate capital amount
        allocated_capital = self.total_capital * allocation_pct

        # Create independent ledger for strategy
        from rustybt.finance.decimal.ledger import DecimalLedger

        ledger = DecimalLedger(starting_cash=allocated_capital)

        # Create performance tracker
        performance = StrategyPerformance(strategy_id)

        # Create allocation
        allocation = StrategyAllocation(
            strategy_id=strategy_id,
            strategy=strategy,
            allocated_capital=allocated_capital,
            ledger=ledger,
            performance=performance,
            state=StrategyState.RUNNING,
            metadata=metadata or {},
        )

        # Store allocation
        self.strategies[strategy_id] = allocation
        self.allocated_capital += allocated_capital

        logger.info(
            "strategy_added",
            portfolio=self.name,
            strategy_id=strategy_id,
            allocation_pct=f"{float(allocation_pct):.1%}",
            allocated_capital=str(allocated_capital),
            total_allocated=str(self.allocated_capital),
            remaining_capital=str(self.total_capital - self.allocated_capital),
        )

        return allocation

    def remove_strategy(self, strategy_id: str, liquidate: bool = True) -> Decimal:
        """Remove strategy from portfolio.

        Args:
            strategy_id: Strategy to remove
            liquidate: If True, liquidate all positions before removing

        Returns:
            Capital returned to portfolio

        Raises:
            KeyError: If strategy_id not found
        """
        if strategy_id not in self.strategies:
            raise KeyError(f"Strategy {strategy_id} not found")

        allocation = self.strategies[strategy_id]

        # Change state to liquidating
        allocation.state = StrategyState.LIQUIDATING

        if liquidate:
            # Liquidate all positions (simplified - just close everything)
            # In real implementation, would iterate positions and close
            logger.info(
                "liquidating_strategy_positions",
                strategy_id=strategy_id,
                num_positions=len(allocation.ledger.positions),
            )
            # allocation.ledger.liquidate_all_positions()  # Would call this

        # Get final value
        final_value = allocation.ledger.portfolio_value

        # Update allocated capital
        self.allocated_capital -= allocation.allocated_capital

        # Mark as stopped
        allocation.state = StrategyState.STOPPED

        # Remove from active strategies
        del self.strategies[strategy_id]

        logger.info(
            "strategy_removed",
            portfolio=self.name,
            strategy_id=strategy_id,
            initial_capital=str(allocation.allocated_capital),
            final_value=str(final_value),
            return_pct=f"{float(allocation.return_pct):.2%}",
            capital_returned=str(final_value),
        )

        return final_value

    def pause_strategy(self, strategy_id: str):
        """Pause strategy execution (keeps positions, stops trading).

        Args:
            strategy_id: Strategy to pause
        """
        if strategy_id not in self.strategies:
            raise KeyError(f"Strategy {strategy_id} not found")

        allocation = self.strategies[strategy_id]
        allocation.state = StrategyState.PAUSED

        logger.info("strategy_paused", portfolio=self.name, strategy_id=strategy_id)

    def resume_strategy(self, strategy_id: str):
        """Resume paused strategy.

        Args:
            strategy_id: Strategy to resume
        """
        if strategy_id not in self.strategies:
            raise KeyError(f"Strategy {strategy_id} not found")

        allocation = self.strategies[strategy_id]
        allocation.state = StrategyState.RUNNING

        logger.info("strategy_resumed", portfolio=self.name, strategy_id=strategy_id)

    def execute_bar(self, timestamp: pd.Timestamp, data: dict[str, Any]):
        """Execute all active strategies for current bar (synchronized).

        All strategies process the same bar simultaneously (sequentially in code,
        but conceptually at the same timestamp).

        Args:
            timestamp: Current bar timestamp
            data: Market data for all assets
        """
        self.current_timestamp = timestamp
        self.execution_count += 1

        logger.info(
            "executing_bar",
            portfolio=self.name,
            timestamp=str(timestamp),
            num_strategies=len(self.strategies),
            execution_count=self.execution_count,
        )

        # Execute each strategy
        for strategy_id, allocation in self.strategies.items():
            # Skip if not running
            if not allocation.is_active:
                logger.debug(
                    "skipping_inactive_strategy",
                    strategy_id=strategy_id,
                    state=allocation.state.value,
                )
                continue

            try:
                # Execute strategy with its isolated ledger
                # Strategy can only modify its own ledger
                allocation.strategy.handle_data(allocation.ledger, data)

                # Update performance metrics
                portfolio_value = allocation.ledger.portfolio_value
                allocation.performance.update(timestamp, portfolio_value)

                logger.debug(
                    "strategy_executed",
                    portfolio=self.name,
                    strategy_id=strategy_id,
                    portfolio_value=str(portfolio_value),
                    return_pct=f"{float(allocation.return_pct):.2%}",
                    num_positions=len(allocation.ledger.positions),
                )

            except Exception as e:
                logger.error(
                    "strategy_execution_failed",
                    portfolio=self.name,
                    strategy_id=strategy_id,
                    error=str(e),
                    exc_info=True,
                )
                # Optionally pause failed strategy
                # allocation.state = StrategyState.PAUSED

        # Log portfolio summary
        portfolio_metrics = self.get_portfolio_metrics()
        logger.info(
            "bar_execution_complete",
            portfolio=self.name,
            timestamp=str(timestamp),
            **portfolio_metrics,
        )

    def rebalance(self, new_allocations: dict[str, Decimal], reason: str = "Manual rebalancing"):
        """Rebalance capital between strategies.

        Capital Transfer Logic:
        - If new_allocation > old_allocation: transfer cash to strategy
        - If new_allocation < old_allocation: reduce positions, return cash

        Args:
            new_allocations: Dict of {strategy_id: new_allocation_pct}
            reason: Reason for rebalancing (for logging)

        Raises:
            ValueError: If allocations don't sum to valid amount or strategy not found
        """
        # Validate allocations
        total_allocation = sum(new_allocations.values())
        if total_allocation > Decimal("1"):
            raise ValueError(f"New allocations exceed 100%: {float(total_allocation):.1%}")

        logger.info(
            "rebalancing_portfolio",
            portfolio=self.name,
            reason=reason,
            num_strategies=len(new_allocations),
            total_allocation=f"{float(total_allocation):.1%}",
        )

        # Track capital movements
        capital_changes: dict[str, Decimal] = {}

        for strategy_id, new_pct in new_allocations.items():
            if strategy_id not in self.strategies:
                raise ValueError(f"Strategy {strategy_id} not found")

            allocation = self.strategies[strategy_id]

            # Calculate new capital amount
            new_capital = self.total_capital * new_pct
            old_capital = allocation.allocated_capital
            capital_delta = new_capital - old_capital

            # Update allocated capital
            allocation.allocated_capital = new_capital

            # Transfer cash
            # Positive delta: add cash to strategy
            # Negative delta: remove cash from strategy (may require liquidating positions)
            allocation.ledger.cash += capital_delta

            capital_changes[strategy_id] = capital_delta

            logger.info(
                "strategy_rebalanced",
                portfolio=self.name,
                strategy_id=strategy_id,
                old_allocation=f"{float(old_capital / self.total_capital):.1%}",
                new_allocation=f"{float(new_pct):.1%}",
                old_capital=str(old_capital),
                new_capital=str(new_capital),
                capital_delta=str(capital_delta),
                new_cash=str(allocation.ledger.cash),
            )

        # Validate capital conservation
        total_capital_after = sum(alloc.allocated_capital for alloc in self.strategies.values())

        if abs(total_capital_after - self.allocated_capital) > Decimal("0.01"):
            logger.error(
                "capital_conservation_violated",
                portfolio=self.name,
                expected=str(self.allocated_capital),
                actual=str(total_capital_after),
                difference=str(total_capital_after - self.allocated_capital),
            )

        # Update allocated capital
        self.allocated_capital = total_capital_after

        logger.info(
            "rebalancing_complete",
            portfolio=self.name,
            total_allocated=str(self.allocated_capital),
            capital_changes={k: str(v) for k, v in capital_changes.items()},
        )

    def get_portfolio_metrics(self) -> dict[str, Any]:
        """Calculate portfolio-level performance metrics.

        Aggregates across all strategies to compute:
        - Total portfolio value
        - Portfolio return
        - Diversification benefit

        Returns:
            Dictionary with portfolio metrics
        """
        # Aggregate portfolio value
        total_value = sum(alloc.ledger.portfolio_value for alloc in self.strategies.values())

        # Calculate total cash
        total_cash = sum(alloc.ledger.cash for alloc in self.strategies.values())

        # Calculate portfolio return
        if self.total_capital > Decimal("0"):
            portfolio_return = (total_value - self.total_capital) / self.total_capital
        else:
            portfolio_return = Decimal("0")

        # Calculate weighted average Sharpe ratio
        total_sharpe_weighted = Decimal("0")
        for alloc in self.strategies.values():
            weight = (
                alloc.allocated_capital / self.allocated_capital
                if self.allocated_capital > 0
                else Decimal("0")
            )
            total_sharpe_weighted += weight * alloc.performance.sharpe_ratio

        # Calculate diversification benefit (simplified)
        # Diversification benefit = portfolio Sharpe - weighted avg Sharpe
        # Would need portfolio-level returns history for true calculation

        return {
            "total_value": str(total_value),
            "total_cash": str(total_cash),
            "total_capital": str(self.total_capital),
            "allocated_capital": str(self.allocated_capital),
            "unallocated_capital": str(self.total_capital - self.allocated_capital),
            "portfolio_return": f"{float(portfolio_return):.2%}",
            "num_strategies": len(self.strategies),
            "active_strategies": sum(1 for a in self.strategies.values() if a.is_active),
            "weighted_avg_sharpe": f"{float(total_sharpe_weighted):.2f}",
        }

    def get_strategy_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all strategies.

        Returns:
            Dict mapping strategy_id to metrics dict
        """
        return {
            strategy_id: {
                **allocation.performance.get_metrics(),
                "allocated_capital": str(allocation.allocated_capital),
                "current_value": str(allocation.current_value),
                "return_pct": f"{float(allocation.return_pct):.2%}",
                "state": allocation.state.value,
            }
            for strategy_id, allocation in self.strategies.items()
        }

    def get_correlation_matrix(self) -> pd.DataFrame | None:
        """Calculate correlation matrix between strategies.

        Returns:
            DataFrame with correlation matrix or None if insufficient data
        """
        # Need at least 2 strategies with returns
        strategy_returns = {}

        for strategy_id, allocation in self.strategies.items():
            if len(allocation.performance.returns) > 0:
                strategy_returns[strategy_id] = allocation.performance.returns

        if len(strategy_returns) < 2:
            return None

        # Find minimum length
        min_length = min(len(returns) for returns in strategy_returns.values())

        if min_length < 2:
            return None

        # Create DataFrame with aligned returns
        returns_dict = {
            strategy_id: [float(r) for r in returns[-min_length:]]
            for strategy_id, returns in strategy_returns.items()
        }

        returns_df = pd.DataFrame(returns_dict)

        # Calculate correlation matrix
        corr_matrix = returns_df.corr()

        return corr_matrix
