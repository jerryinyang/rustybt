# Analytics Suite

Comprehensive analytics framework for backtest analysis, risk assessment, performance attribution, and trade diagnostics.

## Overview

**Purpose**: Understand strategy performance beyond basic returns:
- **Risk Metrics**: VaR, CVaR, stress tests, tail risk, beta analysis
- **Performance Attribution**: Alpha/beta, factor exposures, timing/selection skill
- **Trade Analysis**: Entry/exit quality, MAE/MFE, holding periods, cost impact
- **Visualization**: Charts, heatmaps, distributions, timelines
- **Report Generation**: Comprehensive backtest reports

**When to Use**:
- ✅ After backtest completion for comprehensive analysis
- ✅ Before deployment to understand risk profile
- ✅ For investor reporting and documentation
- ✅ To diagnose strategy weaknesses and improve execution

---

## Quick Start

### Risk Analysis

```python
from rustybt.analytics.risk import RiskAnalytics
import pandas as pd

# Load backtest results
backtest_df = pd.read_parquet("backtest_results.parquet")  # Must have 'returns' or 'portfolio_value'

# Initialize risk analytics
risk = RiskAnalytics(
    backtest_result=backtest_df,
    confidence_levels=[0.95, 0.99],  # VaR confidence levels
    benchmark_returns=spy_returns,    # Optional: for beta analysis
    positions=positions_df            # Optional: for risk decomposition
)

# Calculate Value at Risk
var_results = risk.calculate_var(method='historical')
print(f"95% VaR: {var_results['var_95']}")  # Max expected loss at 95% confidence
print(f"99% VaR: {var_results['var_99']}")  # Max expected loss at 99% confidence

# Calculate Conditional VaR (tail risk)
cvar_results = risk.calculate_cvar(method='historical')
print(f"95% CVaR: {cvar_results['cvar_95']}")  # Average loss beyond VaR

# Run stress tests
stress_results = risk.run_stress_tests()
print(f"2008 Crisis Loss: {stress_results['2008_financial_crisis']}")
print(f"COVID Crash Loss: {stress_results['covid_crash']}")

# Comprehensive risk report
risk_report = risk.analyze_risk()
print(risk_report['var'])
print(risk_report['cvar'])
print(risk_report['tail_risk'])
print(risk_report['beta'])  # If benchmark provided

# Visualize risk
risk.plot_var_distribution(method='historical', confidence=0.95)
risk.plot_stress_test_results()
```

---

### Performance Attribution

```python
from rustybt.analytics.attribution import PerformanceAttribution

# Initialize attribution analyzer
attrib = PerformanceAttribution(
    backtest_result=backtest_df,
    benchmark_returns=spy_returns,
    factor_returns=ff_factors_df,  # Optional: Fama-French factors
    risk_free_rate=0.02             # Optional: risk-free rate (2%)
)

# Comprehensive attribution analysis
results = attrib.analyze_attribution()

# Alpha and beta
print(f"Alpha: {results['alpha_beta']['alpha']:.4f}")
print(f"Beta: {results['alpha_beta']['beta']:.4f}")
print(f"Alpha significant: {results['alpha_beta']['alpha_significant']}")
print(f"Information Ratio: {results['alpha_beta']['information_ratio']:.2f}")

# Factor attribution (if factors provided)
if 'factor_attribution' in results:
    print("\nFactor Loadings:")
    print(results['factor_attribution']['factor_loadings'])
    print(f"\nR-squared: {results['factor_attribution']['r_squared']:.3f}")

# Timing attribution
if 'timing' in results:
    print(f"\nTiming ability: {results['timing']['timing_coefficient']:.4f}")
    print(f"Timing significant: {results['timing']['timing_significant']}")

# Visualize attribution
attrib.plot_alpha_over_time()
attrib.plot_factor_exposures()
```

---

### Trade Analysis

```python
from rustybt.analytics.trade_analysis import TradeAnalyzer

# Initialize trade analyzer
analyzer = TradeAnalyzer(backtest_result)

# Analyze all trades
analysis = analyzer.analyze_trades()

# Summary statistics
print(f"Total trades: {analysis['summary_stats']['total_trades']}")
print(f"Win rate: {analysis['summary_stats']['win_rate']:.2%}")
print(f"Profit factor: {analysis['summary_stats']['profit_factor']:.2f}")
print(f"Average win: ${analysis['summary_stats']['avg_win']}")
print(f"Average loss: ${analysis['summary_stats']['avg_loss']}")
print(f"Largest win: ${analysis['summary_stats']['largest_win']}")
print(f"Largest loss: ${analysis['summary_stats']['largest_loss']}")

# Entry/exit quality
print(f"\nAverage MAE: {analysis['mae_mfe']['avg_mae']:.2%}")
print(f"Average MFE: {analysis['mae_mfe']['avg_mfe']:.2%}")

# Holding period distribution
print(f"\nAverage holding period: {analysis['holding_period']['avg_holding_hours']} hours")

# Cost impact
print(f"\nTotal commission: ${analysis['costs']['total_commission']}")
print(f"Total slippage: ${analysis['costs']['total_slippage']}")
print(f"Commission impact: {analysis['costs']['commission_pct_of_pnl']:.2%}")

# Visualizations
analyzer.plot_mae_vs_pnl()  # MAE scatter plot
analyzer.plot_mfe_vs_pnl()  # MFE scatter plot
analyzer.plot_trade_timeline()  # Trade timeline
analyzer.plot_holding_period_distribution()  # Holding periods
```

---

## Core Modules

### Risk Analytics
- **Module**: `rustybt.analytics.risk`
- **Purpose**: VaR, CVaR, stress testing, beta analysis, tail risk
- **Key Features**: Multiple VaR methods, scenario analysis, risk decomposition
- **Documentation**: [Risk Metrics](risk/README.md)

### Performance Attribution
- **Module**: `rustybt.analytics.attribution`
- **Purpose**: Decompose returns into alpha, beta, factors, timing, selection
- **Key Features**: Multi-factor models, rolling attribution, timing tests
- **Documentation**: [Performance Attribution](attribution/README.md)

### Trade Analysis
- **Module**: `rustybt.analytics.trade_analysis`
- **Purpose**: Trade-level diagnostics and execution quality analysis
- **Key Features**: MAE/MFE, entry/exit quality, cost impact, trade clustering
- **Documentation**: [Trade Analysis](trade-analysis/README.md)

### Visualization
- **Module**: `rustybt.analytics.visualization`
- **Purpose**: Charts, plots, heatmaps for backtest visualization
- **Key Features**: Returns distribution, equity curve, drawdown chart, correlation heatmap
- **Documentation**: [Visualization Tools](visualization.md)

### Report Generation
- **Module**: `rustybt.analytics.reports`
- **Purpose**: Generate comprehensive backtest reports
- **Key Features**: PDF/HTML export, customizable templates, multi-strategy comparison
- **Documentation**: [Report Generation](reports.md)

---

## Complete Analysis Workflow

```python
from rustybt.analytics.risk import RiskAnalytics
from rustybt.analytics.attribution import PerformanceAttribution
from rustybt.analytics.trade_analysis import TradeAnalyzer
from rustybt.analytics.reports import ReportGenerator
import pandas as pd

# Run backtest
backtest_result = run_backtest(strategy, data)

# 1. Risk Analysis
risk = RiskAnalytics(
    backtest_result=backtest_result.to_dataframe(),
    confidence_levels=[0.95, 0.99],
    benchmark_returns=spy_returns
)

risk_report = risk.analyze_risk()
print("\n=== Risk Analysis ===")
print(f"95% VaR: {risk_report['var']['var_95']}")
print(f"95% CVaR: {risk_report['cvar']['cvar_95']}")
print(f"Beta: {risk_report['beta']['beta']}")
print(f"Max drawdown: {risk_report['tail_risk']['max_loss_1d']}")

# 2. Performance Attribution
attribution = PerformanceAttribution(
    backtest_result=backtest_result.to_dataframe(),
    benchmark_returns=spy_returns
)

attrib_report = attribution.analyze_attribution()
print("\n=== Attribution Analysis ===")
print(f"Alpha: {attrib_report['alpha_beta']['alpha']}")
print(f"Beta: {attrib_report['alpha_beta']['beta']}")
print(f"Information Ratio: {attrib_report['alpha_beta']['information_ratio']}")

# 3. Trade Analysis
trade_analyzer = TradeAnalyzer(backtest_result)
trade_report = trade_analyzer.analyze_trades()

print("\n=== Trade Analysis ===")
print(f"Win rate: {trade_report['summary_stats']['win_rate']:.2%}")
print(f"Profit factor: {trade_report['summary_stats']['profit_factor']}")
print(f"Average MAE: {trade_report['mae_mfe']['avg_mae']:.2%}")
print(f"Average MFE: {trade_report['mae_mfe']['avg_mfe']:.2%}")

# 4. Generate Comprehensive Report
report_gen = ReportGenerator(
    backtest_result=backtest_result,
    risk_analysis=risk_report,
    attribution_analysis=attrib_report,
    trade_analysis=trade_report
)

report_gen.generate_report(
    output_path='backtest_report.html',
    format='html',
    include_plots=True
)

print("\n✅ Comprehensive report saved to backtest_report.html")
```

---

## Key Metrics Reference

### Risk Metrics

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **VaR** | Maximum expected loss at confidence level | Lower = less downside risk |
| **CVaR** | Average loss beyond VaR threshold | More conservative than VaR |
| **Beta** | Market sensitivity | 1.0 = market, > 1.0 = more volatile |
| **Skewness** | Return distribution asymmetry | Negative = more extreme losses |
| **Kurtosis** | Fat tails indicator | High = more extreme events |
| **Max Drawdown** | Largest peak-to-trough decline | Lower = less severe losses |
| **Downside Deviation** | Volatility of negative returns | Lower = less downside risk |

### Performance Metrics

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **Alpha** | Excess return vs. benchmark | Positive = outperformance |
| **Information Ratio** | Alpha / tracking error | Higher = better risk-adjusted alpha |
| **R-squared** | Variance explained by benchmark | Higher = more market-driven |
| **Tracking Error** | Volatility of excess returns | Lower = closer to benchmark |
| **Factor Loadings** | Exposure to risk factors | Shows sources of return |

### Trade Metrics

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **Win Rate** | % of profitable trades | Higher = more consistent |
| **Profit Factor** | Gross profit / gross loss | > 1.0 = profitable |
| **MAE** | Max adverse excursion | Risk taken during trade |
| **MFE** | Max favorable excursion | Profit potential captured |
| **Avg Win / Avg Loss** | Reward/risk ratio | Higher = better risk/reward |

---

## Statistical Foundations

### VaR Calculation Methods

**1. Parametric VaR** (assumes normal distribution):
```
VaR = μ + z * σ
where:
  μ = mean daily return
  σ = standard deviation of daily returns
  z = z-score for confidence level (e.g., -1.645 for 95%)
```

**2. Historical VaR** (empirical quantiles):
```
VaR = quantile(returns, 1 - confidence_level)
```

**3. Monte Carlo VaR** (simulation-based):
```
1. Simulate N returns from estimated distribution
2. VaR = empirical quantile of simulated returns
```

### CVaR (Expected Shortfall)

```
CVaR = E[R | R ≤ VaR]
     = mean of returns below VaR threshold
```

Properties:
- CVaR ≥ VaR (in absolute terms)
- More conservative risk measure
- Captures tail risk better than VaR

### Alpha and Beta

**Linear regression**:
```
R_portfolio = α + β * R_benchmark + ε

where:
  α (alpha) = intercept (excess return)
  β (beta) = slope (market sensitivity)
  ε = error term (idiosyncratic risk)
```

**Information Ratio**:
```
IR = α / TE
where:
  TE (tracking error) = std(R_portfolio - R_benchmark)
```

### MAE and MFE

**MAE** (Maximum Adverse Excursion):
```
For long:  MAE = max(0, (entry_price - min_price) / entry_price)
For short: MAE = max(0, (max_price - entry_price) / entry_price)
```

**MFE** (Maximum Favorable Excursion):
```
For long:  MFE = max(0, (max_price - entry_price) / entry_price)
For short: MFE = max(0, (entry_price - min_price) / entry_price)
```

---

## Best Practices

### ✅ DO

1. **Run comprehensive analysis** after every backtest (risk + attribution + trade)
2. **Use multiple VaR methods** (parametric, historical, Monte Carlo) for robustness
3. **Analyze tail risk** (skewness, kurtosis) beyond VaR/CVaR
4. **Review MAE/MFE** to improve stop-loss and take-profit levels
5. **Calculate beta** to understand market dependency
6. **Examine trade distribution** for clustering and concentration risk
7. **Document risk profile** before deploying strategies

### ❌ DON'T

1. **Rely on VaR alone** (use CVaR and stress tests for tail risk)
2. **Ignore statistical significance** (check p-values for alpha)
3. **Skip trade-level analysis** (aggregate metrics hide execution issues)
4. **Use parametric VaR for non-normal returns** (use historical or Monte Carlo)
5. **Forget transaction costs** (commission/slippage impact profitability)
6. **Ignore correlation risk** (check asset correlation matrix)

---

## Performance Considerations

### Risk Analytics
- **Time Complexity**: O(n) for VaR/CVaR, O(n²) for correlation
- **Memory**: O(n) for returns storage
- **Typical Runtime**: < 1 second for 1000 observations

### Performance Attribution
- **Time Complexity**: O(n) for alpha/beta, O(n × f) for factor models
- **Memory**: O(n × f) where f = number of factors
- **Typical Runtime**: 1-5 seconds for factor models with 1000 observations

### Trade Analysis
- **Time Complexity**: O(t) where t = number of trades
- **Memory**: O(t) for trade storage
- **Typical Runtime**: < 1 second for 1000 trades

---

## See Also

- [Risk Metrics Documentation](risk/README.md)
- [Performance Attribution](attribution/README.md)
- [Trade Analysis](trade-analysis/README.md)
- [Visualization Tools](visualization.md)
- [Report Generation](reports.md)

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
