# Portfolio Allocation & Multi-Strategy Management

**Source Files**:
- `/rustybt/portfolio/allocator.py` (769 lines)
- `/rustybt/portfolio/allocation.py` (801 lines)

**Last Verified**: 2025-10-16

---

## Overview

RustyBT's portfolio allocation system enables sophisticated multi-strategy portfolio management with:

- **Strategy Isolation**: Independent ledgers prevent position interference
- **Capital Allocation**: Dynamic or fixed capital allocation across strategies
- **Performance Tracking**: Per-strategy metrics (Sharpe ratio, drawdown, volatility)
- **Rebalancing**: Scheduled or threshold-based capital reallocation
- **Allocation Algorithms**: Fixed, Dynamic, Risk Parity, Kelly Criterion, Drawdown-Based

This system is designed for **hedge fund-style** portfolio management where multiple uncorrelated strategies operate independently with isolated capital.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [PortfolioAllocator - Multi-Strategy Manager](#portfolioallocator)
3. [StrategyAllocation - Per-Strategy Tracking](#strategyallocation)
4. [StrategyPerformance - Performance Metrics](#strategyperformance)
5. [Allocation Algorithms](#allocation-algorithms)
   - [FixedAllocation](#fixedallocation)
   - [DynamicAllocation](#dynamicallocation)
   - [RiskParityAllocation](#riskparityallocation)
   - [KellyCriterionAllocation](#kellycr

iterionallocation)
   - [DrawdownBasedAllocation](#drawdownbasedallocation)
6. [AllocationRebalancer - Rebalancing Scheduler](#allocationrebalancer)
7. [Production Examples](#production-examples)
8. [Best Practices](#best-practices)

---

## Core Concepts

### Multi-Strategy Execution Flow

```
┌──────────────────────────────────────────────────────────────┐
│                   PortfolioAllocator                          │
│                 (Total Capital: $1M)                          │
└───────────────────┬──────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
   ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
   │Strategy │ │Strategy │ │Strategy │
   │   A     │ │   B     │ │   C     │
   │$400k    │ │$350k    │ │$250k    │
   │(40%)    │ │(35%)    │ │(25%)    │
   └────┬────┘ └────┬────┘ └────┬────┘
        │           │           │
   ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
   │Ledger A │ │Ledger B │ │Ledger C │
   │(Isolated│ │(Isolated│ │(Isolated│
   │Positions│ │Positions│ │Positions│
   └─────────┘ └─────────┘ └─────────┘
```

### Bar-by-Bar Execution (Synchronized)

```python
# For each bar (timestamp, data):
for timestamp, market_data in data_feed:
    # 1. Update all strategy ledgers with latest prices
    allocator.update_ledgers(market_data)

    # 2. Execute all strategies sequentially at same timestamp
    allocator.execute_bar(timestamp, market_data)
    #   → Strategy A: handle_data(ledger_A, data)
    #   → Strategy B: handle_data(ledger_B, data)
    #   → Strategy C: handle_data(ledger_C, data)

    # 3. Update performance metrics for each strategy
    #   → Track returns, volatility, Sharpe, drawdown

    # 4. Aggregate portfolio-level metrics
    #   → Total value, weighted Sharpe, correlation matrix
```

### Strategy Isolation Mechanism

Each strategy has **complete isolation**:
- **Separate DecimalLedger**: Independent cash and positions
- **No Cross-Strategy Access**: Cannot see other strategies' positions
- **Capital Transfers Only Through PortfolioAllocator**: Controlled rebalancing

```python
# Strategy A cannot access Strategy B's ledger
# Each strategy sees only its own ledger:
def handle_data(context, data, ledger):  # This ledger belongs to THIS strategy only
    # Can only trade with this strategy's capital
    ledger.order(asset, amount)  # Uses this strategy's cash
```

---

## PortfolioAllocator

**Source**: `rustybt/portfolio/allocator.py:287-769`

The main multi-strategy portfolio manager that coordinates strategy execution, capital allocation, and performance tracking.

### Class Definition

```python
class PortfolioAllocator:
    """Portfolio allocator for multi-strategy management.

    Manages:
    - Multiple strategies with isolated ledgers
    - Capital allocation and rebalancing
    - Synchronized bar-by-bar execution
    - Portfolio-level performance metrics
    """
```

### Constructor

**Source**: `allocator.py:338-356`

```python
def __init__(
    self,
    total_capital: Decimal,
    name: str = "Portfolio"
) -> None:
    """Initialize portfolio allocator.

    Args:
        total_capital: Total capital to allocate across strategies
        name: Portfolio name for logging
    """
```

**Parameters**:
- `total_capital` (Decimal): Total portfolio capital (e.g., `Decimal("1000000")` for $1M)
- `name` (str): Portfolio identifier for logging (default: "Portfolio")

**Attributes**:
- `strategies` (dict[str, StrategyAllocation]): Active strategies
- `allocated_capital` (Decimal): Total allocated capital (≤ total_capital)
- `current_timestamp` (pd.Timestamp | None): Current execution timestamp
- `execution_count` (int): Number of bars executed

### Example 1: Basic Portfolio Setup

```python
from decimal import Decimal
from rustybt.portfolio.allocator import PortfolioAllocator

# Create portfolio with $1M capital
portfolio = PortfolioAllocator(
    total_capital=Decimal("1000000"),
    name="HedgeFund_Alpha"
)

# Portfolio starts empty
print(portfolio.strategies)  # {}
print(portfolio.allocated_capital)  # Decimal('0')
```

---

## Adding Strategies

### add_strategy()

**Source**: `allocator.py:358-429`

```python
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
```

**Validation**:
- Sum of allocations must be ≤ 100% (≤ `Decimal("1.0")`)
- Strategy IDs must be unique
- Creates independent `DecimalLedger` for each strategy

### Example 2: Adding Multiple Strategies

```python
from rustybt.algorithm import TradingAlgorithm

# Define strategies
class MomentumStrategy(TradingAlgorithm):
    def handle_data(self, context, data, ledger):
        # Momentum logic
        pass

class MeanReversionStrategy(TradingAlgorithm):
    def handle_data(self, context, data, ledger):
        # Mean reversion logic
        pass

class TrendFollowingStrategy(TradingAlgorithm):
    def handle_data(self, context, data, ledger):
        # Trend following logic
        pass

# Create portfolio
portfolio = PortfolioAllocator(
    total_capital=Decimal("1000000"),
    name="MultiStrategy_Fund"
)

# Add strategies with different allocations
alloc_momentum = portfolio.add_strategy(
    strategy_id="momentum",
    strategy=MomentumStrategy(),
    allocation_pct=Decimal("0.40"),  # 40%
    metadata={"description": "Short-term momentum", "lookback": 20}
)

alloc_mean_rev = portfolio.add_strategy(
    strategy_id="mean_reversion",
    strategy=MeanReversionStrategy(),
    allocation_pct=Decimal("0.35"),  # 35%
    metadata={"description": "Mean reversion RSI", "threshold": 30}
)

alloc_trend = portfolio.add_strategy(
    strategy_id="trend_following",
    strategy=TrendFollowingStrategy(),
    allocation_pct=Decimal("0.25"),  # 25%
    metadata={"description": "Long-term trend", "ma_window": 200}
)

# Check allocations
print(f"Allocated: ${portfolio.allocated_capital:,.0f}")  # Allocated: $1,000,000
print(f"Remaining: ${portfolio.total_capital - portfolio.allocated_capital:,.0f}")  # Remaining: $0

# Access strategy allocations
print(alloc_momentum)
# StrategyAllocation(id=momentum, capital=400000, value=400000, return=0.00%, state=running)
```

### Example 3: Partial Allocation (Reserve Cash)

```python
# Allocate only 80% of capital (reserve 20% cash)
portfolio = PortfolioAllocator(
    total_capital=Decimal("1000000"),
    name="Conservative_Fund"
)

portfolio.add_strategy("strategy_a", StrategyA(), Decimal("0.40"))  # 40%
portfolio.add_strategy("strategy_b", StrategyB(), Decimal("0.30"))  # 30%
portfolio.add_strategy("strategy_c", StrategyC(), Decimal("0.10"))  # 10%

# Total allocated: 80%
# Reserved cash: 20% = $200,000
print(portfolio.allocated_capital)  # Decimal('800000')
print(portfolio.total_capital - portfolio.allocated_capital)  # Decimal('200000')
```

### Example 4: Over-Allocation Error (Validation)

```python
portfolio = PortfolioAllocator(total_capital=Decimal("1000000"))

portfolio.add_strategy("strat_a", StrategyA(), Decimal("0.60"))  # 60%
portfolio.add_strategy("strat_b", StrategyB(), Decimal("0.30"))  # 30%

# Try to add 30% more (total would be 120%)
try:
    portfolio.add_strategy("strat_c", StrategyC(), Decimal("0.30"))  # Would exceed 100%
except ValueError as e:
    print(e)
    # Allocation would exceed 100%: current=90.0%, new=30.0%, total=120.0%
```

---

## Executing Strategies

### execute_bar()

**Source**: `allocator.py:514-582`

```python
def execute_bar(
    self,
    timestamp: pd.Timestamp,
    data: dict[str, Any]
) -> None:
    """Execute all active strategies for current bar (synchronized).

    All strategies process the same bar simultaneously (sequentially in code,
    but conceptually at the same timestamp).

    Args:
        timestamp: Current bar timestamp
        data: Market data for all assets
    """
```

**Execution Flow**:
1. Set `current_timestamp` to bar timestamp
2. Iterate through all strategies
3. Skip paused/stopped strategies
4. Call `strategy.handle_data(ledger, data)` for each active strategy
5. Update performance metrics for each strategy
6. Log portfolio-level summary

### Example 5: Bar-by-Bar Execution Loop

```python
import pandas as pd

# Setup portfolio
portfolio = PortfolioAllocator(total_capital=Decimal("1000000"))
portfolio.add_strategy("momentum", MomentumStrategy(), Decimal("0.50"))
portfolio.add_strategy("mean_rev", MeanReversionStrategy(), Decimal("0.50"))

# Simulate bar-by-bar execution
timestamps = pd.date_range("2024-01-01", "2024-12-31", freq="D")

for timestamp in timestamps:
    # Fetch market data for this bar
    market_data = {
        "AAPL": {"price": Decimal("150.00"), "volume": 1000000},
        "GOOGL": {"price": Decimal("140.00"), "volume": 800000},
        # ... more assets
    }

    # Execute all strategies at this timestamp
    portfolio.execute_bar(timestamp, market_data)
    #  → momentum.handle_data(ledger_momentum, market_data)
    #  → mean_rev.handle_data(ledger_mean_rev, market_data)

    # Portfolio automatically tracks:
    # - Per-strategy returns
    # - Per-strategy performance metrics
    # - Portfolio-level aggregates

# After backtest, get metrics
metrics = portfolio.get_portfolio_metrics()
print(metrics)
# {
#     'total_value': '1050000',
#     'portfolio_return': '5.00%',
#     'num_strategies': 2,
#     'active_strategies': 2,
#     'weighted_avg_sharpe': '1.20'
# }
```

---

## Managing Strategy Lifecycle

### pause_strategy() / resume_strategy()

**Source**: `allocator.py:486-512`

```python
def pause_strategy(self, strategy_id: str) -> None:
    """Pause strategy execution (keeps positions, stops trading)."""

def resume_strategy(self, strategy_id: str) -> None:
    """Resume paused strategy."""
```

### remove_strategy()

**Source**: `allocator.py:431-484`

```python
def remove_strategy(
    self,
    strategy_id: str,
    liquidate: bool = True
) -> Decimal:
    """Remove strategy from portfolio.

    Args:
        strategy_id: Strategy to remove
        liquidate: If True, liquidate all positions before removing

    Returns:
        Capital returned to portfolio
    """
```

### Example 6: Strategy Lifecycle Management

```python
# Add 3 strategies
portfolio.add_strategy("strat_a", StrategyA(), Decimal("0.33"))
portfolio.add_strategy("strat_b", StrategyB(), Decimal("0.33"))
portfolio.add_strategy("strat_c", StrategyC(), Decimal("0.34"))

# Execute for some time
for timestamp, data in data_feed:
    portfolio.execute_bar(timestamp, data)

# Pause strategy B (e.g., during high volatility)
portfolio.pause_strategy("strat_b")

# Continue execution (only A and C execute)
for timestamp, data in data_feed:
    portfolio.execute_bar(timestamp, data)  # B is skipped

# Resume strategy B
portfolio.resume_strategy("strat_b")

# Remove strategy C (liquidate positions, return capital)
final_value = portfolio.remove_strategy("strat_c", liquidate=True)
print(f"Strategy C final value: ${final_value:,.2f}")
# Strategy C final value: $345,000.00

# Now capital from C is returned to portfolio (unallocated)
print(portfolio.allocated_capital)  # Reduced by C's capital
```

---

## Rebalancing

### rebalance()

**Source**: `allocator.py:584-667`

```python
def rebalance(
    self,
    new_allocations: dict[str, Decimal],
    reason: str = "Manual rebalancing"
) -> None:
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
```

### Example 7: Manual Rebalancing

```python
# Initial allocations
portfolio.add_strategy("momentum", MomentumStrategy(), Decimal("0.40"))  # 40%
portfolio.add_strategy("mean_rev", MeanReversionStrategy(), Decimal("0.35"))  # 35%
portfolio.add_strategy("trend", TrendFollowingStrategy(), Decimal("0.25"))  # 25%

# After 6 months, momentum strategy outperforming
# Rebalance: increase momentum, reduce others

new_allocations = {
    "momentum": Decimal("0.50"),  # 40% → 50% (+10%)
    "mean_rev": Decimal("0.30"),  # 35% → 30% (-5%)
    "trend": Decimal("0.20"),     # 25% → 20% (-5%)
}

portfolio.rebalance(
    new_allocations=new_allocations,
    reason="Increase momentum allocation due to strong performance"
)

# Portfolio automatically:
# - Transfers $100k from mean_rev to momentum
# - Transfers $50k from trend to momentum
# - Updates allocated_capital for each strategy
# - Validates capital conservation
```

### Example 8: Performance-Based Rebalancing

```python
# Rebalance based on recent performance
def rebalance_by_performance(portfolio):
    """Allocate more to recent winners."""
    strategy_metrics = portfolio.get_strategy_metrics()

    # Get returns for each strategy
    returns = {
        sid: Decimal(metrics['return_pct'].rstrip('%')) / 100
        for sid, metrics in strategy_metrics.items()
    }

    # Calculate scores (min-max normalization)
    min_return = min(returns.values())
    max_return = max(returns.values())

    if max_return > min_return:
        scores = {
            sid: (ret - min_return) / (max_return - min_return)
            for sid, ret in returns.items()
        }
    else:
        # All equal - use equal weighting
        scores = {sid: Decimal("1") for sid in returns}

    # Normalize to sum to 1.0
    total_score = sum(scores.values())
    new_allocations = {
        sid: score / total_score
        for sid, score in scores.items()
    }

    # Apply rebalancing
    portfolio.rebalance(
        new_allocations=new_allocations,
        reason="Performance-based rebalancing (allocate to winners)"
    )

# Execute rebalancing
rebalance_by_performance(portfolio)
```

---

## Portfolio-Level Metrics

### get_portfolio_metrics()

**Source**: `allocator.py:669-716`

```python
def get_portfolio_metrics(self) -> dict[str, Any]:
    """Calculate portfolio-level performance metrics.

    Returns:
        Dictionary with portfolio metrics
    """
```

**Returns**:
- `total_value` (str): Total portfolio value
- `total_cash` (str): Total cash across all strategies
- `portfolio_return` (str): Portfolio return percentage
- `num_strategies` (int): Number of strategies
- `active_strategies` (int): Number of running strategies
- `weighted_avg_sharpe` (str): Weighted average Sharpe ratio

### Example 9: Monitoring Portfolio Performance

```python
# Get portfolio metrics
metrics = portfolio.get_portfolio_metrics()

print(f"Portfolio Value: {metrics['total_value']}")  # Portfolio Value: 1,050,000
print(f"Return: {metrics['portfolio_return']}")  # Return: 5.00%
print(f"Active Strategies: {metrics['active_strategies']}/{metrics['num_strategies']}")  # 3/3
print(f"Weighted Sharpe: {metrics['weighted_avg_sharpe']}")  # Weighted Sharpe: 1.35

# Get per-strategy metrics
strategy_metrics = portfolio.get_strategy_metrics()

for strategy_id, metrics in strategy_metrics.items():
    print(f"\n{strategy_id}:")
    print(f"  Capital: {metrics['allocated_capital']}")
    print(f"  Value: {metrics['current_value']}")
    print(f"  Return: {metrics['return_pct']}")
    print(f"  Sharpe: {metrics['sharpe_ratio']}")
    print(f"  Max DD: {metrics['max_drawdown']}")
```

### get_correlation_matrix()

**Source**: `allocator.py:735-768`

```python
def get_correlation_matrix(self) -> pd.DataFrame | None:
    """Calculate correlation matrix between strategies.

    Returns:
        DataFrame with correlation matrix or None if insufficient data
    """
```

### Example 10: Strategy Correlation Analysis

```python
# Get correlation matrix
corr_matrix = portfolio.get_correlation_matrix()

if corr_matrix is not None:
    print("Strategy Correlation Matrix:")
    print(corr_matrix)
    #                momentum  mean_rev     trend
    # momentum           1.00     -0.35      0.60
    # mean_rev          -0.35      1.00     -0.20
    # trend              0.60     -0.20      1.00

    # Ideal: Low correlations indicate good diversification
    # High correlations (>0.7) may indicate redundant strategies
```

---

## StrategyAllocation

**Source**: `rustybt/portfolio/allocator.py:30-76`

Tracks allocation details for a single strategy.

### Class Definition

```python
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
    performance: StrategyPerformance
    state: StrategyState = StrategyState.INITIALIZING
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)
```

### Properties

```python
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
```

### StrategyState Enum

**Source**: `allocator.py:20-28`

```python
class StrategyState(Enum):
    """Strategy lifecycle states."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    LIQUIDATING = "liquidating"
    STOPPED = "stopped"
```

---

## StrategyPerformance

**Source**: `rustybt/portfolio/allocator.py:78-285`

Tracks performance metrics for individual strategy.

### Class Definition

```python
class StrategyPerformance:
    """Performance tracker for individual strategy.

    Tracks:
    - Returns over time
    - Volatility (rolling and cumulative)
    - Sharpe ratio
    - Maximum drawdown
    - Win rate and profit factor
    """
```

### Constructor

```python
def __init__(
    self,
    strategy_id: str,
    lookback_window: int = 252,  # Trading days for rolling metrics
) -> None:
    """Initialize performance tracker.

    Args:
        strategy_id: Unique strategy identifier
        lookback_window: Number of periods for rolling metrics (252 = ~1 year daily)
    """
```

### Performance Metrics

**Source**: `allocator.py:172-284`

#### volatility (property)

```python
@property
def volatility(self) -> Decimal:
    """Calculate annualized volatility.

    Formula:
        σ_annual = std(daily_returns) × √252

    Returns:
        Annualized volatility
    """
```

#### sharpe_ratio (property)

```python
@property
def sharpe_ratio(self) -> Decimal:
    """Calculate Sharpe ratio.

    Formula: (mean_return - risk_free_rate) / volatility
    Assumes risk-free rate = 0 for simplicity

    Returns:
        Sharpe ratio (annualized)
    """
```

#### win_rate (property)

```python
@property
def win_rate(self) -> Decimal:
    """Calculate win rate (% of winning periods).

    Returns:
        Win rate as decimal (0.6 = 60%)
    """
```

#### profit_factor (property)

```python
@property
def profit_factor(self) -> Decimal:
    """Calculate profit factor (total profit / total loss).

    Returns:
        Profit factor (>1 = profitable, <1 = unprofitable)
    """
```

### Example 11: Accessing Strategy Performance

```python
# Get strategy allocation
alloc = portfolio.strategies["momentum"]

# Access performance metrics
perf = alloc.performance

print(f"Strategy: {perf.strategy_id}")
print(f"Observations: {len(perf.portfolio_values)}")
print(f"Current Value: ${perf.portfolio_values[-1]:,.2f}")
print(f"Peak Value: ${perf.peak_value:,.2f}")
print(f"Current DD: {float(perf.current_drawdown):.2%}")
print(f"Max DD: {float(perf.max_drawdown):.2%}")
print(f"Volatility: {float(perf.volatility):.2%}")
print(f"Sharpe Ratio: {float(perf.sharpe_ratio):.2f}")
print(f"Win Rate: {float(perf.win_rate):.2%}")
print(f"Profit Factor: {float(perf.profit_factor):.2f}")

# Get full metrics dictionary
metrics_dict = perf.get_metrics()
print(metrics_dict)
# {
#     'strategy_id': 'momentum',
#     'num_observations': 252,
#     'current_value': '450000.00',
#     'peak_value': '460000.00',
#     'current_drawdown': '-2.17%',
#     'max_drawdown': '-8.50%',
#     'mean_return': '12.50%',
#     'volatility': '18.00%',
#     'sharpe_ratio': '0.69',
#     'win_rate': '55.00%',
#     'profit_factor': '1.35',
#     'winning_periods': 138,
#     'losing_periods': 113
# }
```

---

## Allocation Algorithms

All allocation algorithms inherit from `AllocationAlgorithm` base class.

### AllocationAlgorithm (Base Class)

**Source**: `rustybt/portfolio/allocation.py:29-128`

```python
class AllocationAlgorithm(ABC):
    """Abstract base class for capital allocation algorithms.

    All allocation algorithms must:
    1. Implement calculate_allocations() method
    2. Return allocations as Dict[strategy_id, allocation_pct]
    3. Ensure allocations sum to <= 1.0 (100%)
    4. Handle edge cases (zero volatility, insufficient data)
    5. Use Decimal precision for all calculations
    """

    @abstractmethod
    def calculate_allocations(
        self,
        strategies: dict[str, StrategyPerformance]
    ) -> dict[str, Decimal]:
        """Calculate allocation percentages for each strategy."""
        pass
```

### AllocationConstraints

**Source**: `allocation.py:130-152`

```python
@dataclass
class AllocationConstraints:
    """Constraints for capital allocation.

    Enforces:
    - Global min/max allocation per strategy
    - Per-strategy overrides
    - Sum <= 1.0 constraint
    """

    default_min: Decimal = Decimal("0.0")
    default_max: Decimal = Decimal("1.0")
    strategy_min: dict[str, Decimal] = field(default_factory=dict)
    strategy_max: dict[str, Decimal] = field(default_factory=dict)
```

---

## FixedAllocation

**Source**: `rustybt/portfolio/allocation.py:154-210`

Static percentage allocation per strategy (buy-and-hold allocation).

### Class Definition

```python
class FixedAllocation(AllocationAlgorithm):
    """Fixed allocation: static percentages per strategy.

    Use case: Conservative allocation when you have predefined strategy weights.

    Example:
        strategy1: 40%
        strategy2: 30%
        strategy3: 30%
    """
```

### Constructor

```python
def __init__(
    self,
    allocations: dict[str, Decimal],
    constraints: AllocationConstraints | None = None,
) -> None:
    """Initialize fixed allocation.

    Args:
        allocations: Fixed allocation percentages per strategy
        constraints: Optional constraints

    Raises:
        ValueError: If allocations sum to > 100%
    """
```

### Example 12: Fixed Allocation

```python
from rustybt.portfolio.allocation import FixedAllocation

# Define fixed allocations
fixed_algo = FixedAllocation(
    allocations={
        "momentum": Decimal("0.40"),
        "mean_reversion": Decimal("0.35"),
        "trend_following": Decimal("0.25"),
    }
)

# Calculate allocations (ignores performance)
allocations = fixed_algo.calculate_allocations(strategy_performances)

print(allocations)
# {
#     'momentum': Decimal('0.40'),
#     'mean_reversion': Decimal('0.35'),
#     'trend_following': Decimal('0.25')
# }

# Use with portfolio rebalancing
portfolio.rebalance(allocations, reason="Fixed allocation strategy")
```

---

## DynamicAllocation

**Source**: `rustybt/portfolio/allocation.py:212-300`

Performance-based allocation favoring recent winners (momentum-based).

### Formula

```
score_i = (return_i - min_return) / (max_return - min_return)
allocation_i = score_i / Σ(score_j)
```

### Constructor

```python
def __init__(
    self,
    lookback_window: int = 60,  # 60 days ~3 months
    min_allocation: Decimal = Decimal("0.05"),  # 5% minimum
    constraints: AllocationConstraints | None = None,
) -> None:
    """Initialize dynamic allocation.

    Args:
        lookback_window: Number of periods for performance calculation
        min_allocation: Minimum allocation for any strategy (avoids zero allocation)
        constraints: Optional constraints
    """
```

### Example 13: Dynamic Allocation (Momentum-Based)

```python
from rustybt.portfolio.allocation import DynamicAllocation

# Create dynamic allocator
dynamic_algo = DynamicAllocation(
    lookback_window=60,  # 3 months
    min_allocation=Decimal("0.05"),  # 5% minimum per strategy
)

# Get strategy performances
strategies = {
    sid: alloc.performance
    for sid, alloc in portfolio.strategies.items()
}

# Calculate allocations based on recent performance
allocations = dynamic_algo.calculate_allocations(strategies)

print(allocations)
# Winners get more, losers get less (but at least 5%)
# {
#     'momentum': Decimal('0.50'),      # Best performer
#     'mean_reversion': Decimal('0.30'), # Middle
#     'trend_following': Decimal('0.20') # Worst performer
# }

# Apply rebalancing
portfolio.rebalance(allocations, reason="Dynamic allocation (favor recent winners)")
```

---

## RiskParityAllocation

**Source**: `rustybt/portfolio/allocation.py:302-405`

Allocate inversely proportional to volatility (equal risk contribution).

### Formula

```
w_i = (1/σ_i) / Σ(1/σ_j)

where σ_i is the volatility of strategy i
```

### Constructor

```python
def __init__(
    self,
    lookback_window: int = 252,  # 1 year daily data
    min_volatility: Decimal = Decimal("0.001"),  # Minimum vol to avoid division by zero
    constraints: AllocationConstraints | None = None,
) -> None:
    """Initialize risk parity allocation.

    Args:
        lookback_window: Number of periods for volatility calculation
        min_volatility: Minimum volatility threshold (avoids division by zero)
        constraints: Optional constraints
    """
```

### Example 14: Risk Parity Allocation

```python
from rustybt.portfolio.allocation import RiskParityAllocation

# Create risk parity allocator
risk_parity = RiskParityAllocation(
    lookback_window=252,  # 1 year
    min_volatility=Decimal("0.001"),
)

# Calculate allocations (inverse volatility weighting)
allocations = risk_parity.calculate_allocations(strategies)

# Strategy with lower volatility gets higher allocation
# Strategy with higher volatility gets lower allocation
print(allocations)
# {
#     'momentum': Decimal('0.25'),        # σ = 25%
#     'mean_reversion': Decimal('0.40'),  # σ = 15% (lower vol → higher allocation)
#     'trend_following': Decimal('0.35')  # σ = 18%
# }

# Apply rebalancing
portfolio.rebalance(allocations, reason="Risk parity (equal risk contribution)")
```

---

## KellyCriterionAllocation

**Source**: `rustybt/portfolio/allocation.py:407-543`

Growth-optimal allocation based on Kelly criterion.

### Formula

```
f*_i = μ_i / σ²_i

where:
    μ_i = expected return (mean return)
    σ²_i = variance of returns
```

### Constructor

```python
def __init__(
    self,
    lookback_window: int = 252,  # 1 year
    kelly_fraction: Decimal = Decimal("0.5"),  # Half-Kelly (conservative)
    min_variance: Decimal = Decimal("0.0001"),
    constraints: AllocationConstraints | None = None,
) -> None:
    """Initialize Kelly criterion allocation.

    Args:
        lookback_window: Number of periods for return/variance calculation
        kelly_fraction: Fraction of Kelly to use (0.5 = half-Kelly, conservative)
        min_variance: Minimum variance threshold
        constraints: Optional constraints
    """
```

### Example 15: Kelly Criterion Allocation

```python
from rustybt.portfolio.allocation import KellyCriterionAllocation

# Create Kelly allocator (use half-Kelly for safety)
kelly = KellyCriterionAllocation(
    lookback_window=252,
    kelly_fraction=Decimal("0.5"),  # Half-Kelly (more conservative)
)

# Calculate growth-optimal allocations
allocations = kelly.calculate_allocations(strategies)

# High return + low variance → higher allocation
# Low return or high variance → lower allocation
print(allocations)
# {
#     'momentum': Decimal('0.45'),        # High Sharpe (μ/σ² high)
#     'mean_reversion': Decimal('0.35'),  # Medium Sharpe
#     'trend_following': Decimal('0.20')  # Lower Sharpe
# }

# Apply rebalancing
portfolio.rebalance(allocations, reason="Kelly criterion (growth optimal)")
```

**Warning**: Full Kelly can be aggressive. Use fractional Kelly (0.25-0.5) for safety.

---

## DrawdownBasedAllocation

**Source**: `rustybt/portfolio/allocation.py:545-634`

Reduce allocation to strategies in drawdown (risk-averse).

### Formula

```
score_i = 1 / (1 + |DD_i|)

where DD_i is the current drawdown of strategy i
```

### Constructor

```python
def __init__(
    self,
    max_drawdown_threshold: Decimal = Decimal("0.20"),  # 20% max drawdown
    recovery_bonus: Decimal = Decimal("0.1"),  # 10% bonus for recovering strategies
    constraints: AllocationConstraints | None = None,
) -> None:
    """Initialize drawdown-based allocation.

    Args:
        max_drawdown_threshold: Drawdown threshold for penalty
        recovery_bonus: Bonus allocation for strategies recovering from drawdown
        constraints: Optional constraints
    """
```

### Example 16: Drawdown-Based Allocation

```python
from rustybt.portfolio.allocation import DrawdownBasedAllocation

# Create drawdown-based allocator
drawdown_algo = DrawdownBasedAllocation(
    max_drawdown_threshold=Decimal("0.20"),  # 20% max
    recovery_bonus=Decimal("0.1"),  # 10% bonus for recovery
)

# Calculate allocations (penalize strategies in drawdown)
allocations = drawdown_algo.calculate_allocations(strategies)

# Strategy in drawdown gets lower allocation
# Recovering strategy gets bonus allocation
print(allocations)
# {
#     'momentum': Decimal('0.50'),        # No drawdown, at peak
#     'mean_reversion': Decimal('0.35'),  # Small drawdown (-5%)
#     'trend_following': Decimal('0.15')  # Large drawdown (-15%), penalized
# }

# Apply rebalancing
portfolio.rebalance(allocations, reason="Drawdown-based (reduce exposure to losers)")
```

---

## AllocationRebalancer

**Source**: `rustybt/portfolio/allocation.py:645-801`

Rebalancing scheduler with frequency and drift-based triggers.

### Class Definition

```python
class AllocationRebalancer:
    """Rebalancing scheduler for allocation algorithms.

    Manages:
    - Rebalancing frequency (daily, weekly, monthly)
    - Cooldown periods (prevent excessive rebalancing)
    - Threshold-based triggers (rebalance if allocation drifts > X%)
    """
```

### Constructor

```python
def __init__(
    self,
    algorithm: AllocationAlgorithm,
    frequency: RebalancingFrequency = RebalancingFrequency.MONTHLY,
    cooldown_days: int = 7,  # Minimum days between rebalances
    drift_threshold: Decimal | None = None,  # Rebalance if drift > threshold
) -> None:
    """Initialize rebalancing scheduler.

    Args:
        algorithm: Allocation algorithm to use
        frequency: Rebalancing frequency
        cooldown_days: Minimum days between rebalances
        drift_threshold: Optional drift threshold for threshold-based rebalancing
    """
```

### RebalancingFrequency Enum

**Source**: `allocation.py:636-643`

```python
class RebalancingFrequency(Enum):
    """Rebalancing frequency options."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"
```

### should_rebalance()

**Source**: `allocation.py:684-744`

```python
def should_rebalance(
    self,
    current_time: pd.Timestamp,
    current_allocations: dict[str, Decimal] | None = None,
    target_allocations: dict[str, Decimal] | None = None,
) -> tuple[bool, str]:
    """Check if rebalancing should occur.

    Returns:
        Tuple of (should_rebalance, reason)
    """
```

### Example 17: Monthly Rebalancing with Risk Parity

```python
from rustybt.portfolio.allocation import (
    RiskParityAllocation,
    AllocationRebalancer,
    RebalancingFrequency,
)

# Create risk parity algorithm
risk_parity = RiskParityAllocation(lookback_window=252)

# Create rebalancer (monthly, with 7-day cooldown)
rebalancer = AllocationRebalancer(
    algorithm=risk_parity,
    frequency=RebalancingFrequency.MONTHLY,
    cooldown_days=7,
)

# In backtest loop
for timestamp, data in data_feed:
    # Execute strategies
    portfolio.execute_bar(timestamp, data)

    # Check if should rebalance
    current_allocs = {
        sid: alloc.allocated_capital / portfolio.total_capital
        for sid, alloc in portfolio.strategies.items()
    }

    should_rebal, reason = rebalancer.should_rebalance(
        current_time=timestamp,
        current_allocations=current_allocs,
    )

    if should_rebal:
        # Calculate new allocations using risk parity
        strategies = {
            sid: alloc.performance
            for sid, alloc in portfolio.strategies.items()
        }
        new_allocations = rebalancer.rebalance(strategies, timestamp)

        # Apply rebalancing
        portfolio.rebalance(new_allocations, reason=reason)
```

### Example 18: Drift-Based Rebalancing

```python
# Rebalance if allocation drifts > 5% from target
rebalancer = AllocationRebalancer(
    algorithm=risk_parity,
    frequency=RebalancingFrequency.MONTHLY,
    cooldown_days=7,
    drift_threshold=Decimal("0.05"),  # 5% drift threshold
)

# Check for drift
target_allocs = {"momentum": Decimal("0.33"), "mean_rev": Decimal("0.33"), "trend": Decimal("0.34")}
current_allocs = {"momentum": Decimal("0.40"), "mean_rev": Decimal("0.30"), "trend": Decimal("0.30")}

should_rebal, reason = rebalancer.should_rebalance(
    current_time=timestamp,
    current_allocations=current_allocs,
    target_allocations=target_allocs,
)

# Momentum drifted from 33% to 40% (7% drift > 5% threshold)
print(should_rebal)  # True
print(reason)  # "Allocation drift (7.0% > 5.0%)"
```

---

## Production Examples

### Example 19: Complete Multi-Strategy Portfolio

```python
from decimal import Decimal
import pandas as pd
from rustybt.portfolio.allocator import PortfolioAllocator
from rustybt.portfolio.allocation import (
    RiskParityAllocation,
    AllocationRebalancer,
    RebalancingFrequency,
)

# 1. Create portfolio
portfolio = PortfolioAllocator(
    total_capital=Decimal("1000000"),
    name="HedgeFund_Diversified"
)

# 2. Add strategies
portfolio.add_strategy(
    "momentum_short_term",
    MomentumStrategy(lookback=20),
    Decimal("0.25"),
    metadata={"description": "Short-term momentum (20-day)"}
)

portfolio.add_strategy(
    "mean_reversion_rsi",
    MeanReversionStrategy(threshold=30),
    Decimal("0.25"),
    metadata={"description": "Mean reversion RSI"}
)

portfolio.add_strategy(
    "trend_ma_crossover",
    TrendFollowingStrategy(fast=50, slow=200),
    Decimal("0.25"),
    metadata={"description": "Moving average crossover"}
)

portfolio.add_strategy(
    "pairs_trading",
    PairsTradingStrategy(pairs=[("AAPL", "GOOGL")]),
    Decimal("0.25"),
    metadata={"description": "Statistical arbitrage pairs"}
)

# 3. Setup rebalancing (monthly risk parity)
risk_parity = RiskParityAllocation(lookback_window=252)
rebalancer = AllocationRebalancer(
    algorithm=risk_parity,
    frequency=RebalancingFrequency.MONTHLY,
    cooldown_days=7,
)

# 4. Backtest execution
timestamps = pd.date_range("2023-01-01", "2024-12-31", freq="D")

for timestamp in timestamps:
    # Fetch market data
    market_data = fetch_market_data(timestamp)

    # Execute all strategies
    portfolio.execute_bar(timestamp, market_data)

    # Check rebalancing
    current_allocs = {
        sid: alloc.allocated_capital / portfolio.total_capital
        for sid, alloc in portfolio.strategies.items()
    }

    should_rebal, reason = rebalancer.should_rebalance(
        current_time=timestamp,
        current_allocations=current_allocs,
    )

    if should_rebal:
        strategies = {
            sid: alloc.performance
            for sid, alloc in portfolio.strategies.items()
        }
        new_allocations = rebalancer.rebalance(strategies, timestamp)
        portfolio.rebalance(new_allocations, reason=reason)

# 5. Final results
print("\n=== Final Portfolio Results ===")
metrics = portfolio.get_portfolio_metrics()
print(f"Total Value: {metrics['total_value']}")
print(f"Return: {metrics['portfolio_return']}")
print(f"Weighted Sharpe: {metrics['weighted_avg_sharpe']}")

print("\n=== Per-Strategy Results ===")
strategy_metrics = portfolio.get_strategy_metrics()
for sid, metrics in strategy_metrics.items():
    print(f"\n{sid}:")
    print(f"  Return: {metrics['return_pct']}")
    print(f"  Sharpe: {metrics['sharpe_ratio']}")
    print(f"  Max DD: {metrics['max_drawdown']}")
    print(f"  Win Rate: {metrics['win_rate']}")

print("\n=== Correlation Matrix ===")
corr_matrix = portfolio.get_correlation_matrix()
if corr_matrix is not None:
    print(corr_matrix)
```

### Example 20: Adaptive Allocation (Switch Based on Market Regime)

```python
from rustybt.portfolio.allocation import (
    RiskParityAllocation,
    DynamicAllocation,
    DrawdownBasedAllocation,
)

# Define market regime detector
class MarketRegime(Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOL = "high_volatility"

def detect_market_regime(market_data) -> MarketRegime:
    """Detect current market regime based on indicators."""
    # Implement regime detection logic
    # (VIX levels, moving averages, volatility, etc.)
    pass

# Create allocators for different regimes
allocators = {
    MarketRegime.BULL: DynamicAllocation(lookback_window=60),  # Momentum in bull market
    MarketRegime.BEAR: DrawdownBasedAllocation(),  # Defensive in bear market
    MarketRegime.SIDEWAYS: RiskParityAllocation(),  # Balanced in sideways market
    MarketRegime.HIGH_VOL: DrawdownBasedAllocation(),  # Conservative in high vol
}

# In backtest loop
for timestamp, data in data_feed:
    portfolio.execute_bar(timestamp, data)

    # Detect current regime
    regime = detect_market_regime(data)

    # Select appropriate allocator
    allocator = allocators[regime]

    # Check rebalancing (monthly)
    if timestamp.day == 1:  # First of month
        strategies = {sid: alloc.performance for sid, alloc in portfolio.strategies.items()}
        new_allocations = allocator.calculate_allocations(strategies)
        portfolio.rebalance(
            new_allocations,
            reason=f"Regime-based rebalancing ({regime.value})"
        )
```

---

## Best Practices

### 1. Strategy Isolation

**DO**:
- Use separate ledgers for each strategy
- Never share positions between strategies
- Transfer capital only through `PortfolioAllocator.rebalance()`

**DON'T**:
- Access other strategies' ledgers directly
- Modify positions from outside strategy's `handle_data()`

### 2. Allocation Constraints

**DO**:
- Set min/max allocation per strategy (e.g., 5-40%)
- Ensure allocations sum to ≤ 100%
- Use `AllocationConstraints` to enforce limits

```python
from rustybt.portfolio.allocation import AllocationConstraints

constraints = AllocationConstraints(
    default_min=Decimal("0.05"),  # 5% minimum
    default_max=Decimal("0.40"),  # 40% maximum
    strategy_min={
        "core_strategy": Decimal("0.20"),  # Core strategy gets at least 20%
    },
)

risk_parity = RiskParityAllocation(constraints=constraints)
```

### 3. Rebalancing Frequency

**DO**:
- Use monthly or quarterly rebalancing for most strategies
- Include cooldown periods (7-30 days) to prevent excessive rebalancing
- Use drift-based triggers (5-10% threshold) for opportunistic rebalancing

**DON'T**:
- Rebalance daily (high transaction costs)
- Rebalance without cooldown (over-trading)

### 4. Performance Monitoring

**DO**:
- Track per-strategy and portfolio-level metrics
- Monitor correlation between strategies (aim for < 0.7)
- Log rebalancing events with reasons

```python
# Log all metrics after each month
if timestamp.day == 1:
    metrics = portfolio.get_portfolio_metrics()
    strategy_metrics = portfolio.get_strategy_metrics()
    corr_matrix = portfolio.get_correlation_matrix()

    logger.info("monthly_metrics", **metrics)
    for sid, m in strategy_metrics.items():
        logger.info("strategy_metrics", strategy_id=sid, **m)
    if corr_matrix is not None:
        logger.info("correlation_matrix", matrix=corr_matrix.to_dict())
```

### 5. Capital Allocation

**DO**:
- Start with equal allocation (33.33% each for 3 strategies)
- Use risk parity for uncorrelated strategies
- Reserve 10-20% cash buffer for opportunities

**DON'T**:
- Allocate 100% immediately (keep some dry powder)
- Over-allocate to single strategy (> 50%)

### 6. Strategy Lifecycle

**DO**:
- Pause underperforming strategies (drawdown > 20%)
- Remove strategies after consistent underperformance (6+ months)
- Add new strategies with small initial allocation (5-10%)

```python
# Example: Pause strategy if drawdown > 20%
for sid, alloc in portfolio.strategies.items():
    if alloc.performance.current_drawdown < Decimal("-0.20"):
        portfolio.pause_strategy(sid)
        logger.warning("strategy_paused_drawdown", strategy_id=sid, dd=alloc.performance.current_drawdown)
```

### 7. Allocation Algorithm Selection

**Use Case Guide**:

| Scenario | Recommended Algorithm | Reason |
|----------|----------------------|--------|
| Predefined weights | `FixedAllocation` | Simple, buy-and-hold |
| Momentum-based | `DynamicAllocation` | Allocate to recent winners |
| Diversification | `RiskParityAllocation` | Equal risk contribution |
| Growth maximization | `KellyCriterionAllocation` | Optimal growth rate |
| Risk-averse | `DrawdownBasedAllocation` | Reduce exposure to losers |
| Market regime | Adaptive (switch algorithms) | Match regime characteristics |

### 8. Error Handling

**DO**:
- Catch strategy execution errors (don't let one strategy crash portfolio)
- Validate allocations before rebalancing
- Log all exceptions with strategy context

```python
# PortfolioAllocator.execute_bar() handles this automatically
try:
    allocation.strategy.handle_data(allocation.ledger, data)
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
```

---

## Cross-References

- **Order Management**: `docs/api/order-management/order-types.md`
- **Execution Pipeline**: `docs/api/order-management/execution/execution-pipeline.md`
- **Transaction Costs**: `docs/api/order-management/transaction-costs/slippage-models-verified.md`
- **Risk Management**: `docs/api/portfolio-management/risk-management.md`
- **Order Aggregation**: `docs/api/portfolio-management/order-aggregation.md`
- **Performance Metrics**: `docs/api/analytics/performance-metrics.md`

---

## Summary

RustyBT's portfolio allocation system provides **institutional-grade multi-strategy management** with:

✅ **Strategy Isolation**: Independent ledgers prevent interference
✅ **Flexible Allocation**: Fixed, dynamic, risk parity, Kelly, drawdown-based algorithms
✅ **Performance Tracking**: Per-strategy metrics (Sharpe, drawdown, volatility, win rate)
✅ **Automated Rebalancing**: Frequency-based or drift-based triggers
✅ **Production-Ready**: Comprehensive logging, error handling, validation

This system enables you to:
- Run multiple uncorrelated strategies simultaneously
- Dynamically allocate capital based on performance or risk
- Monitor individual strategy performance
- Rebalance portfolio based on market conditions
- Build hedge fund-style diversified portfolios

**Key Takeaway**: Use `PortfolioAllocator` as the foundation for multi-strategy portfolios, choose the appropriate `AllocationAlgorithm` for your objectives, and let `AllocationRebalancer` handle periodic capital reallocation.
