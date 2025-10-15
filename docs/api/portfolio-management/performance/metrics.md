# Performance Metrics

Complete guide to performance measurement and evaluation in RustyBT.

## Overview

RustyBT provides comprehensive performance metrics for evaluating trading strategies:

- **Returns**: Simple, log, time-weighted returns
- **Risk-Adjusted**: Sharpe, Sortino, Calmar ratios
- **Drawdown**: Maximum drawdown, duration, recovery
- **Risk Metrics**: Volatility, beta, alpha
- **Custom Metrics**: Build your own performance measures

## Quick Start

## Performance Analysis Example

```python
class PerformanceAnalysis(TradingAlgorithm):
    def analyze(self, context, perf):
        """Comprehensive performance analysis."""

        print("=" * 60)
        print("PERFORMANCE SUMMARY")
        print("=" * 60)

        # Returns
        total_return = (perf.portfolio_value[-1] / perf.portfolio_value[0]) - 1
        annual_return = calculate_annualized_return(perf)

        print(f"\nReturns:")
        print(f"  Total Return: {total_return:.2%}")
        print(f"  Annualized Return: {annual_return:.2%}")

        # Risk metrics
        daily_returns = perf.returns
        volatility = calculate_volatility(daily_returns)
        sharpe = calculate_sharpe_ratio(daily_returns)
        sortino = calculate_sortino_ratio(daily_returns)

        print(f"\nRisk Metrics:")
        print(f"  Volatility (annual): {volatility:.2%}")
        print(f"  Sharpe Ratio: {sharpe:.2f}")
        print(f"  Sortino Ratio: {sortino:.2f}")

        # Drawdown
        max_dd, dd_duration, recovery = calculate_max_drawdown(perf.portfolio_value)
        calmar = annual_return / abs(max_dd)

        print(f"\nDrawdown:")
        print(f"  Max Drawdown: {max_dd:.2%}")
        print(f"  Drawdown Duration: {dd_duration} days")
        print(f"  Recovery Time: {recovery} days" if recovery else "  Not recovered")
        print(f"  Calmar Ratio: {calmar:.2f}")

        # Trading stats
        print(f"\nTrading Statistics:")
        print(f"  Total Trades: {len(perf.transactions)}")

        if len(perf.transactions) > 0:
            win_rate = calculate_win_rate(perf.transactions)
            profit_factor = calculate_profit_factor(perf.transactions)

            print(f"  Win Rate: {win_rate:.2%}")
            print(f"  Profit Factor: {profit_factor:.2f}")

        print("=" * 60)
```

## Best Practices

### ✅ DO

1. **Compare Against Benchmark**: Always evaluate relative to market/benchmark
2. **Use Multiple Metrics**: Don't rely on single metric (Sharpe alone insufficient)
3. **Consider Drawdowns**: High returns with huge drawdowns = high risk
4. **Annualize Metrics**: For comparison across strategies/time periods
5. **Account for Costs**: Include slippage and commissions in performance

### ❌ DON'T

1. **Ignore Risk**: High returns mean nothing without risk context
2. **Cherry-Pick Metrics**: Report all metrics, not just favorable ones
3. **Overfit to Sharpe**: Can be gamed with certain strategies
4. **Forget Context**: Market conditions affect all metrics
5. **Compare Apples to Oranges**: Match time periods and risk levels

## Related Documentation

- [Performance Calculations](calculations.md) - Detailed calculation methods
- [Performance Interpretation](interpretation.md) - Understanding metrics
- [Portfolio Management](../README.md) - Portfolio tracking
- [Analytics API](../../analytics-api.md) - Advanced analysis tools

## Next Steps

1. Study [Performance Calculations](calculations.md) for implementation details
2. Review [Interpretation Guide](interpretation.md) for metric analysis
3. Explore [Analytics API](../../analytics-api.md) for advanced metrics
