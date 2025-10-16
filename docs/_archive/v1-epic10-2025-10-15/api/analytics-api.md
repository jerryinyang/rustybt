# Analytics API Reference

**Last Updated**: 2024-10-11

## Overview

The Analytics module provides comprehensive post-backtest analysis tools including professional report generation, performance attribution, risk analytics, trade analysis, and visualization functions.

---

## Report Generation

### ReportGenerator

Generate professional PDF and HTML reports from backtest results.

```python
from rustybt.analytics import ReportGenerator, ReportConfig

config = ReportConfig(
    title="My Trading Strategy",
    subtitle="Momentum-Based Long Strategy"
)

generator = ReportGenerator(backtest_result, config)
generator.generate_report("report.html", format="html")
generator.generate_report("report.pdf", format="pdf")
```

#### Constructor

```python
ReportGenerator(
    backtest_result: Union[pd.DataFrame, pl.DataFrame],
    config: Optional[ReportConfig] = None
)
```

**Parameters**:
- `backtest_result`: DataFrame with backtest results. Must contain:
  - `portfolio_value` or `ending_value` column
  - Datetime index
  - Optional: `returns`, `positions`, `trades` columns
- `config`: Report configuration options

#### Methods

##### `generate_report(output_path: Path, format: str) -> None`

Generate report in specified format.

```python
generator.generate_report("report.html", format="html")
generator.generate_report("report.pdf", format="pdf")
```

**Parameters**:
- `output_path`: Path where report will be saved
- `format`: Output format (`'html'` or `'pdf'`)

**Raises**:
- `ValueError`: If format is not supported
- `IOError`: If file cannot be written

---

### ReportConfig

Configuration for report generation.

```python
from rustybt.analytics import ReportConfig

config = ReportConfig(
    title="Backtest Report",
    subtitle="Q4 2023 Results",
    include_equity_curve=True,
    include_drawdown=True,
    include_returns_distribution=True,
    include_metrics_table=True,
    include_trade_statistics=True,
    include_position_distribution=True,
    custom_charts=[my_custom_chart_func],
    dpi=300,  # High resolution
    figsize=(12, 7)
)
```

**Attributes**:

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | `"Backtest Report"` | Report title |
| `subtitle` | `Optional[str]` | `None` | Optional subtitle |
| `logo_path` | `Optional[Path]` | `None` | Path to logo image |
| `include_equity_curve` | `bool` | `True` | Include equity curve chart |
| `include_drawdown` | `bool` | `True` | Include drawdown chart |
| `include_returns_distribution` | `bool` | `True` | Include returns histogram |
| `include_metrics_table` | `bool` | `True` | Include performance metrics table |
| `include_trade_statistics` | `bool` | `True` | Include trade stats |
| `include_position_distribution` | `bool` | `True` | Include position distribution |
| `custom_charts` | `List[Callable]` | `[]` | Custom chart functions |
| `dpi` | `int` | `150` | Chart resolution (150=screen, 300=print) |
| `figsize` | `tuple` | `(10, 6)` | Default figure size (width, height) inches |

#### Custom Charts

Custom chart functions receive the backtest DataFrame and return base64-encoded image string:

```python
def custom_chart(data: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10, 6))

    # Create your chart
    ax.plot(data.index, data['portfolio_value'])
    ax.set_title('Custom Chart')

    # Convert to base64
    from io import BytesIO
    import base64

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'

config = ReportConfig(custom_charts=[custom_chart])
```

---

## Performance Attribution

### PerformanceAttribution

Decompose returns into alpha, beta, factor exposures, and timing skill.

```python
from rustybt.analytics import PerformanceAttribution

attrib = PerformanceAttribution(
    backtest_result=portfolio_df,
    benchmark_returns=spy_returns,
    factor_returns=fama_french_factors
)

results = attrib.analyze_attribution()
```

#### Constructor

```python
PerformanceAttribution(
    backtest_result: Union[pd.DataFrame, pl.DataFrame],
    benchmark_returns: Optional[pd.Series] = None,
    factor_returns: Optional[pd.DataFrame] = None,
    risk_free_rate: Optional[Union[pd.Series, float]] = None
)
```

**Parameters**:
- `backtest_result`: DataFrame with portfolio values or returns
- `benchmark_returns`: Benchmark returns (e.g., S&P 500) for alpha/beta analysis
- `factor_returns`: DataFrame with factor returns (e.g., Fama-French factors)
  - Common columns: `'Mkt-RF'`, `'SMB'`, `'HML'`, `'RMW'`, `'CMA'`, `'Mom'`
- `risk_free_rate`: Risk-free rate (constant or time series)

#### Methods

##### `analyze_attribution() -> dict`

Run full attribution analysis.

```python
results = attrib.analyze_attribution()

# Alpha/Beta results
alpha_beta = results['alpha_beta']
print(f"Alpha: {alpha_beta['alpha']}")
print(f"Beta: {alpha_beta['beta']}")
print(f"Information Ratio: {alpha_beta['information_ratio']}")

# Factor attribution results
if 'factor_attribution' in results:
    factor_attr = results['factor_attribution']
    print(f"Factor loadings: {factor_attr['factor_loadings']}")

# Timing attribution results
if 'timing' in results:
    timing = results['timing']
    print(f"Has timing skill: {timing['has_timing_skill']}")
```

**Returns**: Dict with keys:
- `'alpha_beta'`: Alpha/beta decomposition (if benchmark provided)
- `'factor_attribution'`: Factor attribution (if factors provided)
- `'timing'`: Timing attribution
- `'rolling'`: Rolling attribution (if sufficient data)

#### Attribution Results

##### Alpha/Beta Results

```python
{
    'alpha': Decimal,              # Daily alpha
    'alpha_annualized': Decimal,   # Annualized alpha
    'alpha_pvalue': float,         # Statistical significance
    'alpha_significant': bool,     # Is alpha significant (p < 0.05)?
    'beta': Decimal,               # Market beta
    'information_ratio': Decimal,   # Alpha / tracking error
    'information_ratio_annualized': Decimal,
    'r_squared': float,            # R-squared of regression
    'tracking_error': Decimal,     # Standard deviation of excess returns
}
```

##### Factor Attribution Results

```python
{
    'alpha': Decimal,                    # Multi-factor alpha
    'alpha_annualized': Decimal,
    'alpha_pvalue': float,
    'alpha_significant': bool,
    'factor_loadings': Dict[str, Decimal],  # Loading on each factor
    'factor_contributions': Dict[str, Decimal],  # Return contribution per factor
    'r_squared': float,
}
```

##### Timing Attribution Results

```python
{
    'timing_coefficient': Decimal,   # Merton-Henriksson timing coefficient
    'timing_pvalue': float,
    'has_timing_skill': bool,
    'timing_direction': str,         # 'positive' or 'negative'
}
```

##### Rolling Attribution Results

```python
{
    'rolling_alpha': pd.Series,          # Rolling 60-day alpha
    'rolling_beta': pd.Series,           # Rolling 60-day beta
    'rolling_information_ratio': pd.Series,
}
```

#### Visualization Methods

##### `plot_attribution_waterfall() -> plt.Figure`

Create waterfall chart showing return decomposition.

```python
fig = attrib.plot_attribution_waterfall(results)
fig.savefig('attribution_waterfall.png', dpi=300)
```

##### `plot_rolling_attribution() -> plt.Figure`

Plot rolling alpha and beta over time.

```python
fig = attrib.plot_rolling_attribution(results)
fig.savefig('rolling_attribution.png', dpi=300)
```

##### `plot_factor_exposures() -> plt.Figure`

Create bar chart of factor loadings.

```python
fig = attrib.plot_factor_exposures(results)
fig.savefig('factor_exposures.png', dpi=300)
```

---

## Risk Analytics

### RiskAnalytics

Comprehensive risk analysis including VaR, CVaR, volatility, and risk metrics.

```python
from rustybt.analytics import RiskAnalytics

risk = RiskAnalytics(backtest_result)
metrics = risk.calculate_risk_metrics()
```

#### Constructor

```python
RiskAnalytics(
    backtest_result: Union[pd.DataFrame, pl.DataFrame],
    benchmark_returns: Optional[pd.Series] = None,
    confidence_level: float = 0.95
)
```

**Parameters**:
- `backtest_result`: DataFrame with portfolio returns
- `benchmark_returns`: Optional benchmark for beta calculation
- `confidence_level`: Confidence level for VaR/CVaR (default: 0.95)

#### Methods

##### `calculate_risk_metrics() -> dict`

Calculate comprehensive risk metrics.

```python
metrics = risk.calculate_risk_metrics()

print(f"Max Drawdown: {metrics['max_drawdown']}")
print(f"VaR (95%): {metrics['value_at_risk']}")
print(f"CVaR (95%): {metrics['conditional_var']}")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']}")
print(f"Sortino Ratio: {metrics['sortino_ratio']}")
```

**Returns**: Dict with keys:

| Metric | Type | Description |
|--------|------|-------------|
| `volatility` | `Decimal` | Annualized volatility |
| `downside_deviation` | `Decimal` | Downside risk (semi-deviation) |
| `max_drawdown` | `Decimal` | Maximum peak-to-trough decline |
| `max_drawdown_duration` | `int` | Days in max drawdown |
| `value_at_risk` | `Decimal` | VaR at confidence level |
| `conditional_var` | `Decimal` | CVaR (expected shortfall) |
| `sharpe_ratio` | `Decimal` | Risk-adjusted return (Sharpe) |
| `sortino_ratio` | `Decimal` | Downside risk-adjusted return |
| `calmar_ratio` | `Decimal` | Return / max drawdown |
| `omega_ratio` | `Decimal` | Probability weighted ratio |
| `beta` | `Decimal` | Market beta (if benchmark provided) |
| `correlation` | `float` | Correlation with benchmark |

##### `calculate_var(confidence_level: float = 0.95, method: str = 'historical') -> Decimal`

Calculate Value at Risk.

```python
var_95 = risk.calculate_var(confidence_level=0.95, method='historical')
var_99 = risk.calculate_var(confidence_level=0.99, method='parametric')
```

**Parameters**:
- `confidence_level`: Confidence level (e.g., 0.95 for 95%)
- `method`: `'historical'` or `'parametric'`

**Returns**: VaR as Decimal (positive value represents potential loss)

##### `calculate_cvar(confidence_level: float = 0.95) -> Decimal`

Calculate Conditional Value at Risk (Expected Shortfall).

```python
cvar_95 = risk.calculate_cvar(confidence_level=0.95)
```

**Returns**: CVaR as Decimal

##### `calculate_drawdown_series() -> pd.Series`

Calculate drawdown series.

```python
drawdowns = risk.calculate_drawdown_series()
max_dd = drawdowns.min()  # Most negative value
```

**Returns**: Series of drawdowns (negative values = underwater)

##### `get_largest_drawdowns(n: int = 5) -> list[dict]`

Get N largest drawdown periods.

```python
top_5_drawdowns = risk.get_largest_drawdowns(n=5)
for dd in top_5_drawdowns:
    print(f"Drawdown: {dd['drawdown']}, Duration: {dd['duration']} days")
```

**Returns**: List of dicts with keys:
- `'drawdown'`: Drawdown magnitude
- `'start_date'`: Peak date
- `'end_date'`: Trough date
- `'recovery_date'`: Recovery date (if recovered)
- `'duration'`: Days from peak to trough

---

## Trade Analysis

### TradeAnalyzer

Analyze individual trades and trade statistics.

```python
from rustybt.analytics import TradeAnalyzer

analyzer = TradeAnalyzer(backtest_result)
stats = analyzer.analyze_trades()
```

#### Constructor

```python
TradeAnalyzer(
    backtest_result: Union[pd.DataFrame, pl.DataFrame],
    trades: Optional[List[Trade]] = None
)
```

**Parameters**:
- `backtest_result`: DataFrame with backtest results
- `trades`: Optional list of Trade objects (extracted automatically if not provided)

#### Methods

##### `analyze_trades() -> dict`

Calculate comprehensive trade statistics.

```python
stats = analyzer.analyze_trades()

print(f"Win Rate: {stats['win_rate']:.1%}")
print(f"Profit Factor: {stats['profit_factor']}")
print(f"Average Win: ${stats['average_win']}")
print(f"Average Loss: ${stats['average_loss']}")
```

**Returns**: Dict with keys:

| Stat | Type | Description |
|------|------|-------------|
| `total_trades` | `int` | Total number of trades |
| `winning_trades` | `int` | Number of winning trades |
| `losing_trades` | `int` | Number of losing trades |
| `win_rate` | `float` | Winning trades / total trades |
| `average_win` | `Decimal` | Average profit per winning trade |
| `average_loss` | `Decimal` | Average loss per losing trade |
| `largest_win` | `Decimal` | Largest winning trade |
| `largest_loss` | `Decimal` | Largest losing trade |
| `profit_factor` | `Decimal` | Gross profit / gross loss |
| `expectancy` | `Decimal` | Average profit per trade |
| `average_holding_period` | `timedelta` | Average time in trade |
| `win_streak` | `int` | Longest winning streak |
| `loss_streak` | `int` | Longest losing streak |

##### `get_trades_dataframe() -> pd.DataFrame`

Get trades as DataFrame.

```python
trades_df = analyzer.get_trades_dataframe()
print(trades_df[['symbol', 'entry_date', 'exit_date', 'pnl', 'return_pct']])
```

**Returns**: DataFrame with columns:
- `symbol`: Asset symbol
- `entry_date`: Entry timestamp
- `exit_date`: Exit timestamp
- `entry_price`: Entry price
- `exit_price`: Exit price
- `quantity`: Position size
- `pnl`: Profit/loss
- `return_pct`: Return percentage
- `holding_period`: Duration
- `side`: `'long'` or `'short'`

##### `plot_trade_distribution() -> plt.Figure`

Create histogram of trade returns.

```python
fig = analyzer.plot_trade_distribution()
fig.savefig('trade_distribution.png', dpi=300)
```

##### `plot_cumulative_pnl() -> plt.Figure`

Plot cumulative P&L over time.

```python
fig = analyzer.plot_cumulative_pnl()
fig.savefig('cumulative_pnl.png', dpi=300)
```

---

## Visualization Functions

Standalone visualization functions for common charts.

### plot_equity_curve

```python
from rustybt.analytics import plot_equity_curve

fig = plot_equity_curve(
    backtest_result,
    benchmark=None,
    figsize=(12, 6),
    title='Portfolio Equity Curve'
)
plt.show()
```

**Parameters**:
- `backtest_result`: DataFrame with `portfolio_value` column
- `benchmark`: Optional benchmark series for comparison
- `figsize`: Figure size (width, height)
- `title`: Chart title

### plot_drawdown

```python
from rustybt.analytics import plot_drawdown

fig = plot_drawdown(
    backtest_result,
    figsize=(12, 4),
    highlight_top_n=5  # Highlight 5 largest drawdowns
)
plt.show()
```

### plot_returns_distribution

```python
from rustybt.analytics import plot_returns_distribution

fig = plot_returns_distribution(
    backtest_result,
    bins=50,
    show_normal=True  # Overlay normal distribution
)
plt.show()
```

### plot_rolling_metrics

```python
from rustybt.analytics import plot_rolling_metrics

fig = plot_rolling_metrics(
    backtest_result,
    window=60,  # 60-day rolling window
    metrics=['sharpe', 'volatility', 'max_drawdown']
)
plt.show()
```

---

## Jupyter Notebook Integration

### setup_notebook

Configure notebook for optimal visualization.

```python
from rustybt.analytics import setup_notebook

setup_notebook()
```

**Effects**:
- Sets matplotlib inline backend
- Configures high-DPI plots
- Sets seaborn style
- Configures pandas display options

### async_backtest

Run backtest asynchronously in notebook.

```python
from rustybt.analytics import async_backtest

result = await async_backtest(
    strategy=MyStrategy(),
    start='2023-01-01',
    end='2023-12-31'
)
```

---

## Complete Example

```python
import pandas as pd
from rustybt.analytics import (
    ReportGenerator,
    ReportConfig,
    PerformanceAttribution,
    RiskAnalytics,
    TradeAnalyzer,
    plot_equity_curve,
    plot_drawdown
)

# Assume we have backtest results
backtest_result = run_backtest(...)

# 1. Generate comprehensive report
config = ReportConfig(
    title="Momentum Strategy Report",
    subtitle="2023 Full Year Results",
    include_equity_curve=True,
    include_drawdown=True,
    dpi=300
)

generator = ReportGenerator(backtest_result, config)
generator.generate_report("report.pdf", format="pdf")

# 2. Performance attribution
attrib = PerformanceAttribution(
    backtest_result=backtest_result,
    benchmark_returns=spy_returns
)

attribution_results = attrib.analyze_attribution()
print(f"Alpha: {attribution_results['alpha_beta']['alpha_annualized']:.2%}")
print(f"Beta: {attribution_results['alpha_beta']['beta']:.2f}")

# 3. Risk analysis
risk = RiskAnalytics(backtest_result)
risk_metrics = risk.calculate_risk_metrics()
print(f"Sharpe: {risk_metrics['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {risk_metrics['max_drawdown']:.2%}")

# 4. Trade analysis
trades = TradeAnalyzer(backtest_result)
trade_stats = trades.analyze_trades()
print(f"Win Rate: {trade_stats['win_rate']:.1%}")
print(f"Profit Factor: {trade_stats['profit_factor']:.2f}")

# 5. Visualizations
plot_equity_curve(backtest_result, benchmark=spy_returns)
plot_drawdown(backtest_result, highlight_top_n=5)
```

---

## See Also

- <!-- Report Generation Example (Coming soon) -->
- <!-- Attribution Analysis Example (Coming soon) -->
- [Examples & Tutorials](../examples/README.md)
