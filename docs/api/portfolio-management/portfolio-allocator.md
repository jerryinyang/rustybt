# PortfolioAllocator - Multi-Strategy Portfolio Management

**Source**: `rustybt/portfolio/allocator.py`
**Verified**: 2025-10-16

## Overview

The `PortfolioAllocator` class orchestrates multi-strategy portfolio execution with dynamic capital allocation, strategy isolation, and comprehensive performance tracking. Unlike manual multi-strategy approaches, PortfolioAllocator provides a production-ready framework for running multiple strategies simultaneously.

## Core Architecture

```
PortfolioAllocator (line 287)
├── Strategy Registry (line 303-310)
│   ├── StrategyAllocation (line 31) - Configuration
│   ├── StrategyState (line 168) - Runtime state
│   └── StrategyPerformance (line 78) - Metrics tracking
│
├── Execution Flow (line 336-426)
│   ├── execute_bar() - Process bar for all strategies
│   ├── _execute_strategy_bar() - Execute single strategy
│   └── _process_strategy_result() - Handle strategy output
│
└── Rebalancing System (line 428-512)
    ├── rebalance() - Adjust capital allocations
    ├── AllocationRebalancer (allocation.py:645)
    └── AllocationAlgorithm implementations
```

## PortfolioAllocator Class

**Source**: `rustybt/portfolio/allocator.py:287`

Main orchestrator for multi-strategy portfolio execution.

### Initialization

```python
from rustybt.portfolio import PortfolioAllocator
from rustybt.portfolio.allocation import DynamicAllocation
from rustybt.data.data_portal import DataPortal

allocator = PortfolioAllocator(
    data_portal=data_portal,
    allocation_algorithm=DynamicAllocation(lookback_days=252),
    rebalance_frequency='monthly',  # 'daily', 'weekly', 'monthly', 'quarterly'
    initial_capital=1000000.0
)
```

**Parameters** (verified line 290-301):

| Parameter | Type | Description |
|-----------|------|-------------|
| `data_portal` | `DataPortal` | Data access interface |
| `allocation_algorithm` | `AllocationAlgorithm` | Capital allocation algorithm |
| `rebalance_frequency` | `str` | Rebalancing frequency ('daily', 'weekly', 'monthly', 'quarterly') |
| `initial_capital` | `float` | Total portfolio capital |

### Key Attributes

**Source verified** in `allocator.py:303-326`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `strategies` | `dict[str, StrategyAllocation]` | Strategy configurations |
| `strategy_states` | `dict[str, StrategyState]` | Runtime state per strategy |
| `strategy_performance` | `dict[str, StrategyPerformance]` | Performance tracking |
| `total_capital` | `Decimal` | Total portfolio capital |
| `allocated_capital` | `dict[str, Decimal]` | Capital per strategy |
| `current_positions` | `dict[str, dict]` | Positions per strategy |

## Configuration Classes

### StrategyAllocation

**Source**: `rustybt/portfolio/allocator.py:31`

Configuration for a strategy within the portfolio.

```python
from dataclasses import dataclass
from rustybt.algorithm import TradingAlgorithm
from rustybt.portfolio import StrategyAllocation

@dataclass
class StrategyAllocation:
    """
    Strategy configuration and allocation details.

    Source: allocator.py:31-75
    """
    strategy_id: str                        # Unique identifier
    strategy_class: type[TradingAlgorithm]  # Strategy class
    strategy_params: dict                   # Strategy initialization params
    initial_allocation: float               # Initial capital fraction (0.0-1.0)
    min_allocation: float = 0.0            # Minimum allocation (default 0%)
    max_allocation: float = 1.0            # Maximum allocation (default 100%)
    enabled: bool = True                   # Active in portfolio
```

**Example**:

```python
from rustybt.portfolio import StrategyAllocation
from my_strategies import MomentumStrategy

momentum_config = StrategyAllocation(
    strategy_id='momentum_1',
    strategy_class=MomentumStrategy,
    strategy_params={'lookback': 20, 'top_n': 10},
    initial_allocation=0.6,  # 60% of capital
    min_allocation=0.3,      # Min 30%
    max_allocation=0.8       # Max 80%
)
```

### StrategyState

**Source**: `rustybt/portfolio/allocator.py:168`

Runtime state for a strategy instance.

**Attributes** (verified line 171-197):

| Attribute | Type | Description |
|-----------|------|-------------|
| `strategy_instance` | `TradingAlgorithm` | The running strategy |
| `ledger` | `DecimalLedger` | Isolated accounting ledger |
| `current_capital` | `Decimal` | Current allocated capital |
| `positions` | `dict` | Current positions |
| `orders` | `dict` | Active orders |
| `is_paused` | `bool` | Execution paused flag |
| `last_executed` | `pd.Timestamp` | Last execution time |

**Strategy Isolation**: Each strategy gets its own `DecimalLedger` instance, ensuring:
- Independent position tracking
- Isolated P&L calculation
- No strategy interference
- Accurate per-strategy performance

### StrategyPerformance

**Source**: `rustybt/portfolio/allocator.py:78`

Performance tracking for a strategy.

**Metrics** (verified line 82-165):

| Metric | Type | Description |
|--------|------|-------------|
| `total_return` | `Decimal` | Cumulative return |
| `annualized_return` | `Decimal` | Annualized return |
| `volatility` | `Decimal` | Return volatility (annualized) |
| `sharpe_ratio` | `Decimal` | Risk-adjusted return |
| `max_drawdown` | `Decimal` | Maximum drawdown |
| `win_rate` | `Decimal` | Percentage of winning trades |
| `total_trades` | `int` | Number of trades |
| `pnl` | `Decimal` | Total profit/loss |
| `capital_allocated` | `Decimal` | Average capital allocated |

## Managing Strategies

### Adding Strategies

**Method**: `add_strategy(strategy_allocation)`
**Source**: `allocator.py:336`

```python
from rustybt.portfolio import PortfolioAllocator, StrategyAllocation
from my_strategies import MomentumStrategy, MeanReversionStrategy

allocator = PortfolioAllocator(
    data_portal=data_portal,
    allocation_algorithm=DynamicAllocation(),
    initial_capital=1_000_000
)

# Add first strategy
momentum_config = StrategyAllocation(
    strategy_id='momentum_1',
    strategy_class=MomentumStrategy,
    strategy_params={'lookback': 20},
    initial_allocation=0.6
)
allocator.add_strategy(momentum_config)

# Add second strategy
mean_rev_config = StrategyAllocation(
    strategy_id='mean_rev_1',
    strategy_class=MeanReversionStrategy,
    strategy_params={'z_score_threshold': 2.0},
    initial_allocation=0.4
)
allocator.add_strategy(mean_rev_config)
```

**Validation** (source line 342-355):
- Validates unique strategy_id
- Validates initial_allocation between 0.0 and 1.0
- Validates min_allocation ≤ initial_allocation ≤ max_allocation
- Creates isolated DecimalLedger for strategy
- Initializes StrategyState and StrategyPerformance

### Executing the Portfolio

**Method**: `execute_bar(timestamp)`
**Source**: `allocator.py:380`

```python
import pandas as pd

# Setup portfolio with strategies
allocator = PortfolioAllocator(...)
allocator.add_strategy(momentum_config)
allocator.add_strategy(mean_rev_config)

# Execute bar for each timestamp
for timestamp in trading_calendar:
    # Execute all active strategies for this bar
    results = allocator.execute_bar(timestamp)

    # Results contain execution details
    for strategy_id, result in results.items():
        print(f"{strategy_id}: {result['orders_placed']} orders")
```

**Execution Flow** (source line 386-426):

1. **Check rebalancing** - If rebalance_frequency reached, call `rebalance()`
2. **Update capital** - Allocate capital to each strategy based on algorithm
3. **Execute strategies** - Call each strategy's `handle_data()` with isolated context
4. **Process orders** - Route orders through blotter with strategy attribution
5. **Update performance** - Calculate metrics from ledger state
6. **Store results** - Update strategy_states and strategy_performance

### Rebalancing Capital

**Method**: `rebalance()`
**Source**: `allocator.py:428`

```python
# Manual rebalancing
allocator.rebalance()

# Automatic rebalancing (via execute_bar)
allocator = PortfolioAllocator(
    data_portal=data_portal,
    allocation_algorithm=DynamicAllocation(lookback_days=252),
    rebalance_frequency='monthly'  # Rebalances monthly
)
```

**Rebalancing Process** (source line 435-512):

1. **Collect performance data** - Get returns, volatility, Sharpe ratios
2. **Run allocation algorithm** - Calculate new allocations
3. **Apply constraints** - Enforce min/max allocation limits
4. **Adjust capital** - Update allocated_capital for each strategy
5. **Liquidate if needed** - Close positions if allocation drops significantly
6. **Log changes** - Record rebalancing events

**Available Allocation Algorithms**:
- [FixedAllocation](allocation-algorithms.md#fixedallocation) - Static weights
- [DynamicAllocation](allocation-algorithms.md#dynamicallocation) - Performance-based
- [RiskParityAllocation](allocation-algorithms.md#riskparityallocation) - Equal risk contribution
- [KellyCriterionAllocation](allocation-algorithms.md#kellycriterionallocation) - Optimal growth
- [DrawdownBasedAllocation](allocation-algorithms.md#drawdownbasedallocation) - Drawdown-adjusted

### Pausing and Resuming Strategies

**Methods**:
- `pause_strategy(strategy_id)` - Source: `allocator.py:514`
- `resume_strategy(strategy_id)` - Source: `allocator.py:534`

```python
# Pause a strategy (stops execution, holds positions)
allocator.pause_strategy('momentum_1')

# Check if paused
is_paused = allocator.strategy_states['momentum_1'].is_paused  # True

# Resume strategy
allocator.resume_strategy('momentum_1')
```

**Pause Behavior** (source line 520-531):
- Sets `is_paused = True` in StrategyState
- Strategy's `handle_data()` NOT called during `execute_bar()`
- Existing positions remain open
- No new orders placed
- Performance tracking continues (based on held positions)

### Removing Strategies

**Method**: `remove_strategy(strategy_id, liquidate=True)`
**Source**: `allocator.py:554`

```python
# Remove strategy and liquidate positions
allocator.remove_strategy('momentum_1', liquidate=True)

# Remove strategy but keep positions
allocator.remove_strategy('momentum_1', liquidate=False)
```

**Removal Process** (source line 560-589):

1. **Pause strategy** - Stop new executions
2. **Liquidate positions** (if liquidate=True) - Close all open positions
3. **Cancel orders** - Cancel pending orders
4. **Deallocate capital** - Free allocated capital
5. **Archive performance** - Save final performance metrics
6. **Remove from registry** - Delete from strategies dict

## Complete Example

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.portfolio import PortfolioAllocator, StrategyAllocation
from rustybt.portfolio.allocation import DynamicAllocation
from rustybt.finance.execution import MarketOrder
from rustybt.data.data_portal import DataPortal
import pandas as pd

# Define two simple strategies
class MomentumStrategy(TradingAlgorithm):
    """Buy top performers, sell bottom performers."""

    def initialize(self, lookback=20, top_n=5):
        self.lookback = lookback
        self.top_n = top_n
        self.assets = [self.symbol('AAPL'), self.symbol('GOOGL'),
                      self.symbol('MSFT'), self.symbol('AMZN')]

    def handle_data(self, context, data):
        # Calculate momentum
        returns = {}
        for asset in self.assets:
            prices = data.history(asset, 'close', self.lookback, '1d')
            returns[asset] = (prices[-1] / prices[0]) - 1

        # Buy top performers
        sorted_assets = sorted(returns.items(), key=lambda x: x[1], reverse=True)
        top_assets = [asset for asset, _ in sorted_assets[:self.top_n]]

        # Equal weight top assets
        target_weight = 1.0 / len(top_assets)
        for asset in self.assets:
            current_pos = self.portfolio.positions.get(asset)
            current_shares = current_pos.amount if current_pos else 0
            current_value = current_shares * data.current(asset, 'price')
            current_weight = current_value / self.portfolio.portfolio_value

            if asset in top_assets:
                # Target position
                target_value = self.portfolio.portfolio_value * target_weight
                target_shares = int(target_value / data.current(asset, 'price'))
                order_amount = target_shares - current_shares
            else:
                # Liquidate
                order_amount = -current_shares

            if order_amount != 0:
                self.order(asset, order_amount, style=MarketOrder())


class MeanReversionStrategy(TradingAlgorithm):
    """Buy oversold, sell overbought based on z-score."""

    def initialize(self, z_score_threshold=2.0, lookback=20):
        self.z_threshold = z_score_threshold
        self.lookback = lookback
        self.asset = self.symbol('SPY')

    def handle_data(self, context, data):
        # Calculate z-score
        prices = data.history(self.asset, 'close', self.lookback, '1d')
        mean_price = prices.mean()
        std_price = prices.std()
        current_price = data.current(self.asset, 'price')
        z_score = (current_price - mean_price) / std_price

        # Trading logic
        current_pos = self.portfolio.positions.get(self.asset)
        current_position = current_pos.amount if current_pos else 0

        if z_score < -self.z_threshold and current_position == 0:
            # Oversold - buy
            target_value = self.portfolio.portfolio_value * 0.95  # 95% invested
            shares = int(target_value / current_price)
            self.order(self.asset, shares, style=MarketOrder())

        elif z_score > self.z_threshold and current_position > 0:
            # Overbought - sell
            self.order(self.asset, -current_position, style=MarketOrder())


# Create portfolio allocator
data_portal = DataPortal(...)  # Initialize with your data bundle

allocator = PortfolioAllocator(
    data_portal=data_portal,
    allocation_algorithm=DynamicAllocation(
        lookback_days=252,
        rebalance_threshold=0.05
    ),
    rebalance_frequency='monthly',
    initial_capital=1_000_000
)

# Add strategies
momentum_config = StrategyAllocation(
    strategy_id='momentum_strategy',
    strategy_class=MomentumStrategy,
    strategy_params={'lookback': 20, 'top_n': 5},
    initial_allocation=0.6,  # 60% of capital
    min_allocation=0.4,
    max_allocation=0.8
)
allocator.add_strategy(momentum_config)

mean_rev_config = StrategyAllocation(
    strategy_id='mean_reversion_strategy',
    strategy_class=MeanReversionStrategy,
    strategy_params={'z_score_threshold': 2.0, 'lookback': 20},
    initial_allocation=0.4,  # 40% of capital
    min_allocation=0.2,
    max_allocation=0.6
)
allocator.add_strategy(mean_rev_config)

# Run backtest
trading_calendar = pd.date_range('2020-01-01', '2023-12-31', freq='B')

for timestamp in trading_calendar:
    # Execute all strategies for this bar
    results = allocator.execute_bar(timestamp)

# Analyze results
for strategy_id in ['momentum_strategy', 'mean_reversion_strategy']:
    perf = allocator.strategy_performance[strategy_id]

    print(f"\n{strategy_id.upper()}")
    print(f"  Total Return: {perf.total_return:.2%}")
    print(f"  Ann. Return: {perf.annualized_return:.2%}")
    print(f"  Volatility: {perf.volatility:.2%}")
    print(f"  Sharpe Ratio: {perf.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {perf.max_drawdown:.2%}")
    print(f"  Win Rate: {perf.win_rate:.2%}")
    print(f"  Total Trades: {perf.total_trades}")
    print(f"  Final Capital: ${perf.capital_allocated:,.2f}")

# Portfolio-level metrics
total_pnl = sum(perf.pnl for perf in allocator.strategy_performance.values())
print(f"\nPORTFOLIO TOTAL")
print(f"  Total P&L: ${total_pnl:,.2f}")
print(f"  Final Value: ${allocator.total_capital:,.2f}")
```

## Strategy Isolation

**Source**: `allocator.py:168-197, 342-355`

Each strategy operates in complete isolation with its own DecimalLedger:

```python
# Each strategy gets independent ledger
strategy_state = StrategyState(
    strategy_instance=strategy_instance,
    ledger=DecimalLedger(initial_capital),  # ISOLATED LEDGER
    current_capital=initial_capital,
    positions={},
    orders={},
    is_paused=False
)
```

**Benefits of Isolation**:
1. **No interference**: One strategy can't affect another's positions
2. **Accurate attribution**: Performance tracked per strategy
3. **Independent risk**: Each strategy has own risk limits
4. **Debugging**: Isolate issues to specific strategy
5. **Flexibility**: Add/remove strategies without affecting others

## Performance Monitoring

```python
# Real-time monitoring during execution
for timestamp in trading_calendar:
    allocator.execute_bar(timestamp)

    # Check performance after each bar
    for strategy_id, perf in allocator.strategy_performance.items():
        # Monitor drawdown
        if perf.max_drawdown < -0.20:  # -20% drawdown
            print(f"WARNING: {strategy_id} drawdown {perf.max_drawdown:.2%}")
            allocator.pause_strategy(strategy_id)

        # Monitor Sharpe ratio
        if perf.sharpe_ratio < 0.5:
            print(f"WARNING: {strategy_id} low Sharpe {perf.sharpe_ratio:.2f}")

        # Monitor win rate
        if perf.total_trades > 50 and perf.win_rate < 0.4:
            print(f"WARNING: {strategy_id} low win rate {perf.win_rate:.2%}")
```

## Capital Allocation Flow

```
Initial Capital: $1,000,000
         ↓
Allocation Algorithm (e.g., DynamicAllocation)
         ↓
    ┌────────────────────────────┐
    │  Strategy Allocations      │
    ├────────────────────────────┤
    │ momentum_1:      $600,000  │ (60%)
    │ mean_reversion:  $400,000  │ (40%)
    └────────────────────────────┘
         ↓
Monthly Rebalancing (based on performance)
         ↓
    ┌────────────────────────────┐
    │  Adjusted Allocations      │
    ├────────────────────────────┤
    │ momentum_1:      $650,000  │ (65% - performing well)
    │ mean_reversion:  $350,000  │ (35% - underperforming)
    └────────────────────────────┘
```

## Best Practices

### ✅ DO

1. **Use strategy isolation**: Leverage the built-in DecimalLedger isolation
2. **Set allocation constraints**: Define min/max allocations for each strategy
3. **Monitor performance**: Track strategy-level metrics continuously
4. **Rebalance regularly**: Adjust allocations based on performance
5. **Pause underperformers**: Use pause_strategy() when strategies underperform

### ❌ DON'T

1. **Over-allocate**: Ensure allocations sum to ≤ 100%
2. **Ignore correlation**: Avoid highly correlated strategies
3. **Skip validation**: Always validate strategy_id uniqueness
4. **Forget constraints**: Set realistic min/max allocation bounds
5. **Over-rebalance**: Too frequent rebalancing increases costs

## Related Documentation

- [Allocation Algorithms](allocation-algorithms.md) - Capital allocation strategies
- [Risk Management](risk-management.md) - Portfolio risk controls
- [Performance Metrics](performance/metrics.md) - Detailed performance calculations

## Verification

✅ All classes, methods, and attributes verified in source code
✅ No fabricated APIs
✅ All line numbers referenced for verification

**Verification Date**: 2025-10-16
**Source Files Verified**:
- `rustybt/portfolio/allocator.py:31,78,168,287`
- `rustybt/portfolio/allocation.py` (algorithms)
- `rustybt/finance/ledger/decimal_ledger.py` (isolation mechanism)
