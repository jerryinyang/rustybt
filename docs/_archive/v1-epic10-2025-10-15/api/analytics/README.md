# Analytics Suite

Comprehensive tools for analyzing strategy performance, risk metrics, and trade statistics.

## Overview

The analytics suite provides professional-grade analysis tools for understanding strategy performance, including risk metrics, performance attribution, trade analysis, and visualization capabilities.

### Key Features

- **Risk Analytics**: VaR, CVaR, drawdown analysis, volatility metrics
- **Performance Attribution**: Alpha/beta decomposition, factor analysis
- **Trade Analysis**: Win rates, profit factors, trade statistics
- **Visualization**: Equity curves, drawdowns, distributions, custom charts
- **Report Generation**: Professional PDF/HTML reports

### Architecture

```
┌─────────────────────────────────────────────────────┐
│              Backtest Results                        │
├─────────────────────────────────────────────────────┤
│               Analytics Layer                        │
│   ┌──────────┬───────────┬──────────┐              │
│   │   Risk   │ Attribution│  Trade   │              │
│   │ Analytics│  Analysis  │ Analysis │              │
│   └──────────┴───────────┴──────────┘              │
├─────────────────────────────────────────────────────┤
│          Visualization & Reporting                   │
│   ┌──────────┬───────────┬──────────┐              │
│   │  Charts  │Dashboards │ Reports  │              │
│   └──────────┴───────────┴──────────┘              │
└─────────────────────────────────────────────────────┘
```

## Quick Navigation

### Risk Analysis
- **[Risk Metrics](risk/metrics.md)** - Comprehensive risk calculations
- **[VaR & CVaR](risk/var-cvar.md)** - Value at Risk and expected shortfall
- **[Drawdown Analysis](risk/drawdown.md)** - Maximum drawdown and underwater periods

### Performance Attribution
- **Performance Attribution (Coming soon)** - Alpha/beta decomposition
- **Factor Attribution (Coming soon)** - Factor exposure analysis
- **Multi-Strategy Attribution (Coming soon)** - Portfolio-level attribution

### Trade Analysis
- **Trade Statistics (Coming soon)** - Win rates, profit factors, expectancy
- **Trade Patterns (Coming soon)** - Entry/exit timing analysis
- **Trade Timing (Coming soon)** - Holding period analysis

### Visualization
- **Charts (Coming soon)** - Equity curves, returns distributions
- **Dashboards (Coming soon)** - Interactive dashboards
- **Notebooks (Coming soon)** - Jupyter integration

## Quick Start

## Visualization Examples

### Equity Curve with Drawdown

```python
from rustybt.analytics import plot_equity_curve, plot_drawdown
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Equity curve
plot_equity_curve(result, ax=ax1, benchmark=spy_returns)
ax1.set_title('Portfolio Performance')

# Drawdown
plot_drawdown(result, ax=ax2, highlight_top_n=5)
ax2.set_title('Drawdown Analysis')

plt.tight_layout()
plt.show()
```

### Returns Distribution

```python
from rustybt.analytics import plot_returns_distribution

fig = plot_returns_distribution(
    result,
    bins=50,
    show_normal=True,  # Overlay normal distribution
    show_var=True      # Show VaR line
)
plt.show()
```

### Trade Scatter Plot

```python
from rustybt.analytics import TradeAnalyzer

analyzer = TradeAnalyzer(result)
fig = analyzer.plot_trade_scatter()
plt.show()
```

## Best Practices

### 1. Always Include Transaction Costs

```python
# Include realistic costs in backtest
from rustybt.finance.commission import PerShareCommission
from rustybt.finance.slippage import FixedSlippage

result = run_backtest(
    strategy,
    commission=PerShareCommission(0.01),
    slippage=FixedSlippage(0.001)
)

# Then analyze
risk = RiskAnalytics(result)
```

### 2. Use Multiple Metrics

Don't rely on single metric:

```python
metrics = risk.calculate_risk_metrics()

# Check multiple metrics
if (metrics['sharpe_ratio'] > 1.0 and
    metrics['max_drawdown'] > -0.30 and
    metrics['sortino_ratio'] > 1.5):
    print("Strategy passes multi-metric screening")
```

### 3. Compare to Benchmark

```python
attrib = PerformanceAttribution(
    backtest_result=result,
    benchmark_returns=spy_returns
)

results = attrib.analyze_attribution()

# Strategy should beat benchmark on risk-adjusted basis
if results['alpha_beta']['alpha_annualized'] > 0.05:
    print("Positive alpha vs benchmark")
```

### 4. Analyze Trade Quality

```python
analyzer = TradeAnalyzer(result)
stats = analyzer.analyze_trades()

# Good strategies have:
# - Win rate >50%
# - Profit factor >1.5
# - Positive expectancy
if (stats['win_rate'] > 0.50 and
    stats['profit_factor'] > 1.5 and
    stats['expectancy'] > 0):
    print("High quality trades")
```

## Common Pitfalls

### ❌ Ignoring Drawdowns

```python
# WRONG: Only looking at returns
if annual_return > 0.20:
    print("Good strategy!")

# RIGHT: Consider drawdown
if annual_return > 0.20 and max_drawdown > -0.25:
    print("Good risk-adjusted strategy!")
```

### ❌ Cherry-Picking Metrics

```python
# WRONG: Only showing good metrics
print(f"Sharpe: {metrics['sharpe_ratio']}")  # Only if good!

# RIGHT: Show all key metrics
print(f"Sharpe: {metrics['sharpe_ratio']}")
print(f"Sortino: {metrics['sortino_ratio']}")
print(f"Max DD: {metrics['max_drawdown']}")
print(f"Calmar: {metrics['calmar_ratio']}")
```

### ❌ Not Analyzing Trades

```python
# WRONG: Only portfolio-level metrics
risk_metrics = risk.calculate_risk_metrics()

# RIGHT: Also analyze individual trades
trade_stats = analyzer.analyze_trades()
# Check win rate, profit factor, etc.
```

## Examples

See `examples/analytics/` for complete examples:

- `comprehensive_analysis.py` - Full strategy analysis
- `comparative_analysis.py` - Compare multiple strategies
- `rolling_analysis.py` - Time-varying metrics
- `factor_attribution.py` - Factor decomposition
- `generate_report.py` - Professional PDF reports

## See Also

- [Main Analytics API](../analytics-api.md)
- [Optimization Documentation](../optimization/README.md)
- [Live Trading Documentation](../live-trading/README.md)
- [Examples & Tutorials](../../examples/README.md)

## Support

- **Issues**: [GitHub Issues](https://github.com/bmad-dev/rustybt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/bmad-dev/rustybt/discussions)
- **Documentation**: [Full API Reference](https://rustybt.readthedocs.io)
