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
- **[Performance Attribution](attribution/performance.md)** - Alpha/beta decomposition
- **[Factor Attribution](attribution/factor.md)** - Factor exposure analysis
- **[Multi-Strategy Attribution](attribution/multi-strategy.md)** - Portfolio-level attribution

### Trade Analysis
- **[Trade Statistics](trade-analysis/statistics.md)** - Win rates, profit factors, expectancy
- **[Trade Patterns](trade-analysis/patterns.md)** - Entry/exit timing analysis
- **[Trade Timing](trade-analysis/timing.md)** - Holding period analysis

### Visualization
- **[Charts](visualization/charts.md)** - Equity curves, returns distributions
- **[Dashboards](visualization/dashboards.md)** - Interactive dashboards
- **[Notebooks](visualization/notebooks.md)** - Jupyter integration

## Quick Start

### Basic Risk Analysis

```python
from rustybt.analytics import RiskAnalytics

# Analyze backtest results
risk = RiskAnalytics(backtest_result)
metrics = risk.calculate_risk_metrics()

print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
print(f"VaR (95%): {metrics['value_at_risk']:.2%}")
```

### Performance Attribution

```python
from rustybt.analytics import PerformanceAttribution

attrib = PerformanceAttribution(
    backtest_result=portfolio_returns,
    benchmark_returns=spy_returns
)

results = attrib.analyze_attribution()
print(f"Alpha: {results['alpha_beta']['alpha_annualized']:.2%}")
print(f"Beta: {results['alpha_beta']['beta']:.2f}")
```

### Trade Analysis

```python
from rustybt.analytics import TradeAnalyzer

analyzer = TradeAnalyzer(backtest_result)
stats = analyzer.analyze_trades()

print(f"Win Rate: {stats['win_rate']:.1%}")
print(f"Profit Factor: {stats['profit_factor']:.2f}")
print(f"Avg Win: ${stats['average_win']:.2f}")
print(f"Avg Loss: ${stats['average_loss']:.2f}")
```

### Report Generation

```python
from rustybt.analytics import ReportGenerator, ReportConfig

config = ReportConfig(
    title="Strategy Performance Report",
    include_equity_curve=True,
    include_drawdown=True,
    include_metrics_table=True
)

generator = ReportGenerator(backtest_result, config)
generator.generate_report("report.pdf", format="pdf")
```

## Core Classes

### RiskAnalytics

Comprehensive risk analysis.

```python
from rustybt.analytics import RiskAnalytics

risk = RiskAnalytics(
    backtest_result=result,
    benchmark_returns=spy,
    confidence_level=0.95
)

metrics = risk.calculate_risk_metrics()
# Returns: dict with sharpe, sortino, max_drawdown, VaR, CVaR, etc.
```

### PerformanceAttribution

Decompose returns into alpha, beta, and factors.

```python
from rustybt.analytics import PerformanceAttribution

attrib = PerformanceAttribution(
    backtest_result=portfolio,
    benchmark_returns=benchmark,
    factor_returns=fama_french
)

results = attrib.analyze_attribution()
# Returns: alpha/beta, factor loadings, timing analysis
```

### TradeAnalyzer

Analyze individual trades.

```python
from rustybt.analytics import TradeAnalyzer

analyzer = TradeAnalyzer(backtest_result)
stats = analyzer.analyze_trades()

# Get trades as DataFrame
trades_df = analyzer.get_trades_dataframe()
```

### ReportGenerator

Generate professional reports.

```python
from rustybt.analytics import ReportGenerator, ReportConfig

generator = ReportGenerator(backtest_result, config)
generator.generate_report("report.html", format="html")
generator.generate_report("report.pdf", format="pdf")
```

## Key Metrics

### Risk Metrics

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **Sharpe Ratio** | Risk-adjusted return | >1.0 good, >2.0 excellent |
| **Sortino Ratio** | Downside risk-adjusted | >1.5 good, >2.5 excellent |
| **Calmar Ratio** | Return / max drawdown | >1.0 good, >2.0 excellent |
| **Max Drawdown** | Largest peak-to-trough | <20% good, <30% acceptable |
| **VaR (95%)** | Value at risk | Expected loss 5% of time |
| **CVaR (95%)** | Conditional VaR | Average loss when VaR exceeded |
| **Volatility** | Annualized std dev | Lower better for same return |

### Trade Metrics

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **Win Rate** | Winning trades / total | >50% good, >60% excellent |
| **Profit Factor** | Gross profit / gross loss | >1.5 good, >2.0 excellent |
| **Expectancy** | Average profit per trade | Positive required |
| **Average Win** | Mean profit per win | Higher better |
| **Average Loss** | Mean loss per loss | Smaller better (absolute) |
| **Win/Loss Ratio** | Avg win / avg loss | >1.0 preferred |

## Common Workflows

### Workflow 1: Complete Strategy Analysis

```python
from rustybt.analytics import (
    RiskAnalytics,
    PerformanceAttribution,
    TradeAnalyzer,
    ReportGenerator
)

# Run backtest
result = run_backtest(strategy, start, end)

# 1. Risk analysis
risk = RiskAnalytics(result)
risk_metrics = risk.calculate_risk_metrics()

# 2. Performance attribution
attrib = PerformanceAttribution(result, spy_returns)
attribution = attrib.analyze_attribution()

# 3. Trade analysis
trades = TradeAnalyzer(result)
trade_stats = trades.analyze_trades()

# 4. Generate report
generator = ReportGenerator(result)
generator.generate_report("strategy_report.pdf")
```

### Workflow 2: Comparative Analysis

```python
# Compare multiple strategies
strategies = ['momentum', 'mean_reversion', 'breakout']
results = {}

for strategy_name in strategies:
    result = run_backtest(strategy_name, start, end)
    risk = RiskAnalytics(result)
    results[strategy_name] = risk.calculate_risk_metrics()

# Compare metrics
import pandas as pd
comparison = pd.DataFrame(results).T
print(comparison[['sharpe_ratio', 'max_drawdown', 'annual_return']])
```

### Workflow 3: Rolling Analysis

```python
# Analyze performance over time
from rustybt.analytics import RollingAnalytics

rolling = RollingAnalytics(result, window=60)  # 60-day window

rolling_sharpe = rolling.calculate_rolling_sharpe()
rolling_drawdown = rolling.calculate_rolling_drawdown()
rolling_volatility = rolling.calculate_rolling_volatility()

# Plot evolution
rolling.plot_rolling_metrics()
```

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
from rustybt.finance import PerShareCommission, FixedSlippage

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
