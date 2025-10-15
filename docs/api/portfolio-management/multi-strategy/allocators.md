# Portfolio Allocators and Multi-Strategy Systems

Complete guide to running multiple strategies with capital allocation in RustyBT.

## Overview

Multi-strategy portfolios run several strategies simultaneously with coordinated capital allocation:

- **Capital Allocation**: Distribute capital across strategies
- **Strategy Isolation**: Each strategy operates independently
- **Order Aggregation**: Combine orders across strategies
- **Cross-Strategy Netting**: Offset opposing orders
- **Performance Attribution**: Track strategy-level returns

## Why Multi-Strategy?

**Benefits**:
- ✓ Diversification across uncorrelated strategies
- ✓ Reduced portfolio volatility
- ✓ Better risk-adjusted returns
- ✓ Flexibility to adjust allocations
- ✓ Strategy-level performance tracking

**Challenges**:
- ⚠️ Capital allocation complexity
- ⚠️ Order conflicts between strategies
- ⚠️ Performance attribution accuracy
- ⚠️ Increased monitoring overhead

## Capital Allocation Strategies

### Fixed Allocation

Allocate fixed percentage to each strategy.

```python
from rustybt.algorithm import TradingAlgorithm

class FixedAllocation(TradingAlgorithm):
    """Run multiple strategies with fixed allocation."""

    def initialize(self, context):
        # Define strategies and allocations
        context.strategies = {
            'momentum': {
                'allocation': 0.40,  # 40% of capital
                'strategy': MomentumStrategy()
            },
            'mean_reversion': {
                'allocation': 0.30,  # 30% of capital
                'strategy': MeanReversionStrategy()
            },
            'pairs_trading': {
                'allocation': 0.30,  # 30% of capital
                'strategy': PairsTradingStrategy()
            }
        }

        # Initialize each strategy
        for name, config in context.strategies.items():
            config['strategy'].initialize(context)

    def handle_data(self, context, data):
        portfolio_value = context.portfolio.portfolio_value

        # Allocate capital to each strategy
        for name, config in context.strategies.items():
            allocation = config['allocation']
            strategy = config['strategy']

            # Calculate strategy capital
            strategy_capital = portfolio_value * allocation

            # Create strategy-specific context
            strategy_context = self.create_strategy_context(
                context, name, strategy_capital
            )

            # Run strategy
            strategy.handle_data(strategy_context, data)
```

### Dynamic Allocation

Adjust allocations based on performance or market conditions.

```python
class DynamicAllocation(TradingAlgorithm):
    """Dynamically allocate capital based on performance."""

    def initialize(self, context):
        context.strategies = {
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'trend_following': TrendFollowingStrategy()
        }

        # Initial equal allocation
        n_strategies = len(context.strategies)
        context.allocations = {
            name: 1.0 / n_strategies
            for name in context.strategies.keys()
        }

        # Performance tracking
        context.strategy_returns = {name: [] for name in context.strategies.keys()}
        context.rebalance_frequency = 21  # Rebalance monthly
        context.days_since_rebalance = 0

    def handle_data(self, context, data):
        context.days_since_rebalance += 1

        # Rebalance allocations periodically
        if context.days_since_rebalance >= context.rebalance_frequency:
            self.rebalance_allocations(context)
            context.days_since_rebalance = 0

        # Run strategies with current allocations
        portfolio_value = context.portfolio.portfolio_value

        for name, strategy in context.strategies.items():
            allocation = context.allocations[name]
            strategy_capital = portfolio_value * allocation

            strategy_context = self.create_strategy_context(
                context, name, strategy_capital
            )
            strategy.handle_data(strategy_context, data)

    def rebalance_allocations(self, context):
        """Adjust allocations based on recent performance."""
        # Calculate recent Sharpe ratios
        sharpe_ratios = {}

        for name, returns in context.strategy_returns.items():
            if len(returns) < 20:
                sharpe_ratios[name] = 0.0
            else:
                recent_returns = returns[-20:]  # Last 20 days
                mean_return = np.mean(recent_returns)
                std_return = np.std(recent_returns)
                sharpe = mean_return / std_return if std_return > 0 else 0.0
                sharpe_ratios[name] = max(sharpe, 0)  # No negative allocations

        # Allocate proportionally to Sharpe ratios
        total_sharpe = sum(sharpe_ratios.values())

        if total_sharpe > 0:
            for name in context.strategies.keys():
                context.allocations[name] = sharpe_ratios[name] / total_sharpe
        else:
            # Fall back to equal allocation if all strategies underperforming
            n_strategies = len(context.strategies)
            for name in context.strategies.keys():
                context.allocations[name] = 1.0 / n_strategies

        self.log.info(f"Rebalanced allocations: {context.allocations}")
```

### Risk Parity Allocation

Allocate to equalize risk contribution across strategies.

```python
class RiskParityAllocation(TradingAlgorithm):
    """Allocate capital based on inverse volatility (risk parity)."""

    def initialize(self, context):
        context.strategies = {
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'trend_following': TrendFollowingStrategy()
        }

        context.strategy_returns = {name: [] for name in context.strategies.keys()}
        context.allocations = {}
        context.rebalance_frequency = 21
        context.days_since_rebalance = 0

    def calculate_risk_parity_weights(self, context):
        """Calculate inverse volatility weights."""
        volatilities = {}

        for name, returns in context.strategy_returns.items():
            if len(returns) < 20:
                volatilities[name] = 1.0  # Default
            else:
                vol = np.std(returns[-60:])  # 60-day volatility
                volatilities[name] = vol if vol > 0 else 1.0

        # Inverse volatility weights
        inv_vols = {name: 1.0 / vol for name, vol in volatilities.items()}
        total_inv_vol = sum(inv_vols.values())

        # Normalize to sum to 1
        weights = {name: inv_vol / total_inv_vol
                  for name, inv_vol in inv_vols.items()}

        return weights

    def handle_data(self, context, data):
        context.days_since_rebalance += 1

        if context.days_since_rebalance >= context.rebalance_frequency:
            context.allocations = self.calculate_risk_parity_weights(context)
            context.days_since_rebalance = 0
            self.log.info(f"Risk parity allocations: {context.allocations}")

        # Run strategies with current allocations
        portfolio_value = context.portfolio.portfolio_value

        for name, strategy in context.strategies.items():
            allocation = context.allocations.get(name, 1.0 / len(context.strategies))
            strategy_capital = portfolio_value * allocation

            strategy_context = self.create_strategy_context(
                context, name, strategy_capital
            )
            strategy.handle_data(strategy_context, data)
```

## Strategy Isolation

### Isolated Strategy Context

Each strategy gets its own isolated view of the portfolio.

```python
class StrategyContext:
    """Isolated context for individual strategy."""

    def __init__(self, parent_context, strategy_name, allocated_capital):
        self.parent = parent_context
        self.strategy_name = strategy_name
        self.allocated_capital = allocated_capital

        # Strategy-specific portfolio view
        self.positions = self.get_strategy_positions()
        self.cash = self.calculate_strategy_cash()
        self.portfolio_value = self.cash + self.calculate_positions_value()

    def get_strategy_positions(self):
        """Get only positions owned by this strategy."""
        strategy_positions = {}

        for asset, position in self.parent.portfolio.positions.items():
            # Check if position belongs to this strategy
            if self.is_strategy_position(asset, position):
                strategy_positions[asset] = position

        return strategy_positions

    def is_strategy_position(self, asset, position):
        """Determine if position belongs to this strategy."""
        # Implementation depends on position tracking method
        # Could use tags, separate accounts, or order tracking
        pass

    def order(self, asset, amount, **kwargs):
        """Place order tagged with strategy name."""
        # Tag order with strategy name for tracking
        kwargs['strategy_name'] = self.strategy_name

        # Check if order exceeds allocated capital
        order_value = abs(amount) * self.get_current_price(asset)

        if order_value > self.allocated_capital * 1.1:  # 10% buffer
            self.log.warning(
                f"Strategy {self.strategy_name} order exceeds allocation: "
                f"${order_value:.2f} > ${self.allocated_capital:.2f}"
            )
            # Scale down order
            max_amount = int((self.allocated_capital * 1.1) / self.get_current_price(asset))
            amount = max_amount if amount > 0 else -max_amount

        return self.parent.order(asset, amount, **kwargs)
```

## Order Aggregation

### Combine Orders Across Strategies

```python
class OrderAggregator:
    """Aggregate orders from multiple strategies."""

    def __init__(self):
        self.pending_orders = {}  # Dict[asset] = {strategy: amount}

    def add_order(self, strategy_name, asset, amount):
        """Add order from strategy."""
        if asset not in self.pending_orders:
            self.pending_orders[asset] = {}

        self.pending_orders[asset][strategy_name] = amount

    def aggregate_orders(self):
        """Aggregate orders by asset, netting where possible."""
        aggregated = {}

        for asset, strategy_orders in self.pending_orders.items():
            # Sum all orders for this asset
            total_amount = sum(strategy_orders.values())

            if total_amount != 0:
                aggregated[asset] = {
                    'amount': total_amount,
                    'strategies': strategy_orders
                }

        return aggregated

    def execute_aggregated_orders(self, context):
        """Execute aggregated orders."""
        aggregated = self.aggregate_orders()

        for asset, order_info in aggregated.items():
            amount = order_info['amount']
            strategies = order_info['strategies']

            # Place single aggregated order
            order_id = context.order(asset, amount)

            self.log.info(
                f"Aggregated order for {asset.symbol}: {amount} shares "
                f"from {len(strategies)} strategies"
            )

        # Clear pending orders
        self.pending_orders.clear()

# Usage in multi-strategy algorithm:
class MultiStrategyWithAggregation(TradingAlgorithm):
    def initialize(self, context):
        context.order_aggregator = OrderAggregator()
        context.strategies = {
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy()
        }

    def handle_data(self, context, data):
        # Collect orders from all strategies
        for name, strategy in context.strategies.items():
            strategy_orders = strategy.generate_orders(context, data)

            for asset, amount in strategy_orders.items():
                context.order_aggregator.add_order(name, asset, amount)

        # Execute aggregated orders
        context.order_aggregator.execute_aggregated_orders(context)
```

## Cross-Strategy Netting

### Net Opposing Orders

```python
class StrategyNetting:
    """Net opposing orders between strategies."""

    def __init__(self, netting_enabled=True):
        self.netting_enabled = netting_enabled

    def net_orders(self, strategy_orders):
        """Net orders across strategies.

        Parameters
        ----------
        strategy_orders : dict
            {strategy_name: {asset: amount}}

        Returns
        -------
        netted_orders : dict
            {asset: {net_amount, long_strategies, short_strategies}}
        """
        asset_orders = {}

        # Collect all orders by asset
        for strategy_name, orders in strategy_orders.items():
            for asset, amount in orders.items():
                if asset not in asset_orders:
                    asset_orders[asset] = {'long': {}, 'short': {}}

                if amount > 0:
                    asset_orders[asset]['long'][strategy_name] = amount
                elif amount < 0:
                    asset_orders[asset]['short'][strategy_name] = amount

        # Calculate net orders
        netted = {}

        for asset, orders in asset_orders.items():
            long_total = sum(orders['long'].values())
            short_total = sum(orders['short'].values())
            net_amount = long_total + short_total

            if net_amount != 0 or not self.netting_enabled:
                netted[asset] = {
                    'net_amount': net_amount,
                    'gross_long': long_total,
                    'gross_short': abs(short_total),
                    'long_strategies': orders['long'],
                    'short_strategies': orders['short']
                }

        return netted

    def calculate_netting_benefit(self, strategy_orders):
        """Calculate transaction cost savings from netting."""
        netted = self.net_orders(strategy_orders)

        # Calculate gross orders (no netting)
        gross_value = 0
        for asset, info in netted.items():
            gross_value += info['gross_long'] + info['gross_short']

        # Calculate net orders (with netting)
        net_value = 0
        for asset, info in netted.items():
            net_value += abs(info['net_amount'])

        # Savings in trade value
        savings = gross_value - net_value
        savings_pct = savings / gross_value if gross_value > 0 else 0

        return {
            'gross_value': gross_value,
            'net_value': net_value,
            'savings': savings,
            'savings_pct': savings_pct
        }
```

## Performance Attribution

### Track Strategy-Level Returns

```python
class StrategyAttribution:
    """Attribute performance to individual strategies."""

    def __init__(self):
        self.strategy_values = {}  # {strategy: [values over time]}
        self.strategy_returns = {}  # {strategy: [daily returns]}

    def update(self, strategy_name, portfolio_value, dt):
        """Update strategy portfolio value."""
        if strategy_name not in self.strategy_values:
            self.strategy_values[strategy_name] = []
            self.strategy_returns[strategy_name] = []

        self.strategy_values[strategy_name].append({
            'date': dt,
            'value': portfolio_value
        })

        # Calculate daily return
        if len(self.strategy_values[strategy_name]) > 1:
            prev_value = self.strategy_values[strategy_name][-2]['value']
            daily_return = (portfolio_value - prev_value) / prev_value
            self.strategy_returns[strategy_name].append(daily_return)

    def get_strategy_performance(self, strategy_name):
        """Get performance metrics for strategy."""
        if strategy_name not in self.strategy_returns:
            return None

        returns = self.strategy_returns[strategy_name]

        if len(returns) == 0:
            return None

        return {
            'total_return': np.prod([1 + r for r in returns]) - 1,
            'mean_daily_return': np.mean(returns),
            'volatility': np.std(returns) * np.sqrt(252),
            'sharpe': np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0,
            'max_drawdown': self.calculate_max_drawdown(returns)
        }

    def calculate_max_drawdown(self, returns):
        """Calculate maximum drawdown."""
        cumulative = np.cumprod([1 + r for r in returns])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return np.min(drawdown)

    def get_attribution_summary(self):
        """Get attribution summary for all strategies."""
        summary = {}

        for strategy_name in self.strategy_returns.keys():
            perf = self.get_strategy_performance(strategy_name)
            if perf:
                summary[strategy_name] = perf

        return summary
```

## Complete Multi-Strategy Example

```python
class ProductionMultiStrategy(TradingAlgorithm):
    """Complete multi-strategy system with all features."""

    def initialize(self, context):
        # Initialize strategies
        context.strategies = {
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'pairs_trading': PairsTradingStrategy()
        }

        # Capital allocation
        context.allocations = {
            'momentum': 0.40,
            'mean_reversion': 0.30,
            'pairs_trading': 0.30
        }

        # Components
        context.order_aggregator = OrderAggregator()
        context.netting = StrategyNetting(netting_enabled=True)
        context.attribution = StrategyAttribution()

        # Configuration
        context.rebalance_frequency = 21
        context.days_since_rebalance = 0

    def handle_data(self, context, data):
        context.days_since_rebalance += 1

        # Rebalance allocations if needed
        if context.days_since_rebalance >= context.rebalance_frequency:
            self.rebalance_allocations(context)
            context.days_since_rebalance = 0

        # Run each strategy
        portfolio_value = context.portfolio.portfolio_value
        strategy_orders = {}

        for name, strategy in context.strategies.items():
            allocation = context.allocations[name]
            strategy_capital = portfolio_value * allocation

            # Create isolated context
            strategy_context = StrategyContext(
                context, name, strategy_capital
            )

            # Run strategy and collect orders
            orders = strategy.generate_orders(strategy_context, data)
            strategy_orders[name] = orders

            # Track strategy performance
            strategy_value = strategy_context.portfolio_value
            context.attribution.update(name, strategy_value, context.datetime)

        # Net orders across strategies
        netted_orders = context.netting.net_orders(strategy_orders)

        # Execute netted orders
        for asset, order_info in netted_orders.items():
            amount = order_info['net_amount']
            if amount != 0:
                context.order(asset, amount)

        # Log netting benefit
        benefit = context.netting.calculate_netting_benefit(strategy_orders)
        if benefit['savings'] > 0:
            self.log.info(
                f"Netting saved ${benefit['savings']:,.0f} "
                f"({benefit['savings_pct']:.1%}) in trade value"
            )

    def analyze(self, context, perf):
        """Analyze multi-strategy performance."""
        print("\n" + "="*60)
        print("MULTI-STRATEGY PERFORMANCE ATTRIBUTION")
        print("="*60)

        attribution = context.attribution.get_attribution_summary()

        for strategy_name, metrics in attribution.items():
            print(f"\n{strategy_name.upper()}:")
            print(f"  Total Return: {metrics['total_return']:.2%}")
            print(f"  Volatility: {metrics['volatility']:.2%}")
            print(f"  Sharpe Ratio: {metrics['sharpe']:.2f}")
            print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")

        print("\n" + "="*60)
```

## Best Practices

### ✅ DO

1. **Isolate Strategies**: Give each strategy its own context
2. **Net Orders**: Combine opposing orders to save costs
3. **Track Attribution**: Monitor strategy-level performance
4. **Rebalance Regularly**: Adjust allocations based on performance
5. **Monitor Correlations**: Ensure strategies are diversified

### ❌ DON'T

1. **Over-Allocate**: Ensure allocations sum to ≤ 100%
2. **Ignore Conflicts**: Handle opposing orders intelligently
3. **Mix Timeframes**: Match strategy timeframes appropriately
4. **Forget Costs**: Netting reduces but doesn't eliminate costs
5. **Over-Correlate**: Avoid highly correlated strategies

## Related Documentation

- Performance Attribution (Coming soon) - Detailed attribution methods
- Order Aggregation (Coming soon) - Order combination strategies
- Risk Management - Portfolio-level risk controls
- [Portfolio Management](../README.md) - Portfolio tracking

## Next Steps

1. Study Performance Attribution (Coming soon) for detailed tracking
2. Review Order Aggregation (Coming soon) for optimization
3. Implement multi-strategy system in your framework
