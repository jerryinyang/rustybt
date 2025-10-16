# Visualization Tools

Interactive charting and visualization tools for backtest analysis using Plotly.

## Overview

**Purpose**: Create professional, interactive charts for backtest analysis, strategy comparison, and investor reporting.

**Key Features**:
- = **Interactive Charts**: Plotly-based with zoom, pan, hover tooltips
- < **Theme Support**: Light and dark themes for presentations
- = **Common Visualizations**: Equity curve, drawdown, returns distribution, rolling metrics
- = **Flexible Input**: Supports both pandas and Polars DataFrames
- = **Export**: Save to HTML, PNG, or embed in Jupyter notebooks

**When to Use**:
-  For backtest visualization and diagnostics
-  For investor presentations and reports
-  For strategy comparison and analysis
-  For exploratory data analysis in Jupyter notebooks

---

## Quick Start

### Basic Equity Curve

```python
from rustybt.analytics import plot_equity_curve
import pandas as pd

# Load backtest results
backtest_df = pd.read_parquet("backtest_results.parquet")

# Plot equity curve with drawdown
fig = plot_equity_curve(
    backtest_result=backtest_df,
    title="My Strategy Performance",
    theme="light",
    show_drawdown=True
)

# Display in Jupyter
fig.show()

# Or save to file
fig.write_html("equity_curve.html")
fig.write_image("equity_curve.png")
```

### Returns Distribution

```python
from rustybt.analytics import plot_returns_distribution

# Plot returns distribution with statistics
fig = plot_returns_distribution(
    backtest_result=backtest_df,
    title="Daily Returns Distribution",
    bins=50
)

fig.show()
```

### Rolling Performance Metrics

```python
from rustybt.analytics import plot_rolling_metrics

# Plot rolling Sharpe ratio and volatility
fig = plot_rolling_metrics(
    backtest_result=backtest_df,
    window=60,  # 60-day rolling window
    title="Rolling Performance (60d)"
)

fig.show()
```

---

## API Reference

### plot_equity_curve()

Plot interactive portfolio equity curve with optional drawdown subplot.

**Signature**:
```python
def plot_equity_curve(
    backtest_result: pd.DataFrame | pl.DataFrame,
    title: str = "Portfolio Equity Curve",
    theme: str = "light",
    show_drawdown: bool = True,
) -> go.Figure
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backtest_result` | `pd.DataFrame \| pl.DataFrame` | *(required)* | Backtest results with `portfolio_value` and datetime index |
| `title` | `str` | `"Portfolio Equity Curve"` | Chart title |
| `theme` | `str` | `"light"` | Color theme: `"light"` or `"dark"` |
| `show_drawdown` | `bool` | `True` | Show drawdown subplot below equity curve |

**Returns**: `plotly.graph_objects.Figure` - Interactive Plotly figure

**Required DataFrame Columns**:
- **Datetime index** or `date`/`timestamp` column
- **Value column**: `portfolio_value` or `ending_value`

**Example**:
```python
from rustybt.analytics import plot_equity_curve

# Basic equity curve
fig = plot_equity_curve(backtest_df)
fig.show()

# Dark theme without drawdown
fig = plot_equity_curve(
    backtest_df,
    title="Strategy A vs Strategy B",
    theme="dark",
    show_drawdown=False
)
fig.show()

# Save to HTML for sharing
fig.write_html("backtest_equity.html")
```

**Visualization Features**:
-  Hover tooltip shows date and portfolio value
-  Zoom and pan for detailed inspection
-  Drawdown subplot synchronized with equity curve
-  Max drawdown line automatically annotated

---

### plot_drawdown()

Plot standalone portfolio drawdown chart.

**Signature**:
```python
def plot_drawdown(
    backtest_result: pd.DataFrame | pl.DataFrame,
    title: str = "Portfolio Drawdown",
    theme: str = "light",
) -> go.Figure
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backtest_result` | `pd.DataFrame \| pl.DataFrame` | *(required)* | Backtest results with `portfolio_value` and datetime index |
| `title` | `str` | `"Portfolio Drawdown"` | Chart title |
| `theme` | `str` | `"light"` | Color theme: `"light"` or `"dark"` |

**Returns**: `plotly.graph_objects.Figure` - Interactive Plotly figure

**Required DataFrame Columns**:
- **Datetime index** or `date`/`timestamp` column
- **Value column**: `portfolio_value` or `ending_value`

**Drawdown Calculation**:
```
drawdown = (portfolio_value - cumulative_max) / cumulative_max
max_drawdown = min(drawdown)
```

**Example**:
```python
from rustybt.analytics import plot_drawdown

# Plot drawdown with max drawdown annotation
fig = plot_drawdown(backtest_df, theme="light")
fig.show()

# Dark theme for presentations
fig = plot_drawdown(backtest_df, theme="dark")
fig.write_image("drawdown_dark.png", width=1200, height=600)
```

**Interpretation**:
- **Drawdown = 0%**: Portfolio at all-time high
- **Drawdown < -10%**: Moderate decline from peak
- **Drawdown < -20%**: Significant decline from peak
- **Max Drawdown**: Largest peak-to-trough decline (shown as dashed line)

---

### plot_returns_distribution()

Plot histogram of returns with statistics overlay.

**Signature**:
```python
def plot_returns_distribution(
    backtest_result: pd.DataFrame | pl.DataFrame,
    title: str = "Returns Distribution",
    theme: str = "light",
    bins: int = 50,
) -> go.Figure
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backtest_result` | `pd.DataFrame \| pl.DataFrame` | *(required)* | Backtest results with `returns` or `portfolio_value` |
| `title` | `str` | `"Returns Distribution"` | Chart title |
| `theme` | `str` | `"light"` | Color theme: `"light"` or `"dark"` |
| `bins` | `int` | `50` | Number of histogram bins |

**Returns**: `plotly.graph_objects.Figure` - Interactive Plotly figure

**Required DataFrame Columns**:
- **Datetime index** or `date`/`timestamp` column
- **Returns**: `returns` column OR `portfolio_value` (will calculate returns)

**Statistics Displayed**:
- **Mean**: Average daily return
- **Std Dev**: Standard deviation (volatility)
- **Skewness**: Distribution asymmetry (negative = left tail)
- **Kurtosis**: Fat tails indicator (high = extreme events)

**Example**:
```python
from rustybt.analytics import plot_returns_distribution

# Basic returns distribution
fig = plot_returns_distribution(backtest_df)
fig.show()

# More bins for detailed distribution
fig = plot_returns_distribution(backtest_df, bins=100)
fig.show()
```

**Interpretation**:
- **Mean > 0**: Positive average return
- **Skewness < 0**: More extreme losses than gains (risky)
- **Skewness > 0**: More extreme gains than losses (favorable)
- **Kurtosis > 3**: Fat tails, more extreme events than normal distribution
- **Kurtosis < 3**: Thin tails, fewer extreme events

---

### plot_rolling_metrics()

Plot rolling Sharpe ratio and volatility over time.

**Signature**:
```python
def plot_rolling_metrics(
    backtest_result: pd.DataFrame | pl.DataFrame,
    window: int = 30,
    title: str = "Rolling Performance Metrics",
    theme: str = "light",
) -> go.Figure
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backtest_result` | `pd.DataFrame \| pl.DataFrame` | *(required)* | Backtest results with returns data |
| `window` | `int` | `30` | Rolling window size in days |
| `title` | `str` | `"Rolling Performance Metrics"` | Chart title |
| `theme` | `str` | `"light"` | Color theme: `"light"` or `"dark"` |

**Returns**: `plotly.graph_objects.Figure` - Interactive Plotly figure with 2 subplots

**Required DataFrame Columns**:
- **Datetime index** or `date`/`timestamp` column
- **Returns**: `returns` column OR `portfolio_value` (will calculate returns)

**Metrics Calculated** (annualized):
- **Rolling Sharpe Ratio**: `mean(returns) / std(returns) * sqrt(252)`
- **Rolling Volatility**: `std(returns) * sqrt(252)` (annualized)

**Example**:
```python
from rustybt.analytics import plot_rolling_metrics

# 30-day rolling metrics
fig = plot_rolling_metrics(backtest_df, window=30)
fig.show()

# 60-day rolling metrics for smoother trends
fig = plot_rolling_metrics(backtest_df, window=60)
fig.show()

# Quarterly (90-day) metrics
fig = plot_rolling_metrics(
    backtest_df,
    window=90,
    title="Quarterly Rolling Performance"
)
fig.show()
```

**Interpretation**:
- **Sharpe > 1.0**: Good risk-adjusted performance
- **Sharpe > 2.0**: Excellent risk-adjusted performance
- **Sharpe < 0**: Negative risk-adjusted return (losing money)
- **Volatility trends**: Rising volatility = increasing risk

---

## Complete Examples

### Example 1: Multi-Chart Dashboard

Create a comprehensive visualization dashboard combining multiple charts.

```python
from rustybt.analytics import (
    plot_equity_curve,
    plot_returns_distribution,
    plot_rolling_metrics,
)
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# Load backtest results
backtest_df = pd.read_parquet("backtest_results.parquet")

# Create individual charts
equity_fig = plot_equity_curve(backtest_df, show_drawdown=True)
returns_fig = plot_returns_distribution(backtest_df)
rolling_fig = plot_rolling_metrics(backtest_df, window=60)

# Display all charts in Jupyter
equity_fig.show()
returns_fig.show()
rolling_fig.show()

# Save all charts to HTML files
equity_fig.write_html("equity_curve.html")
returns_fig.write_html("returns_dist.html")
rolling_fig.write_html("rolling_metrics.html")
```

### Example 2: Strategy Comparison

Compare multiple strategies on the same chart.

```python
from rustybt.analytics import plot_equity_curve
import plotly.graph_objects as go

# Load multiple strategy results
strategy_a = pd.read_parquet("strategy_a_results.parquet")
strategy_b = pd.read_parquet("strategy_b_results.parquet")
benchmark = pd.read_parquet("benchmark_results.parquet")

# Create base figure
fig = go.Figure()

# Add each strategy
strategies = [
    (strategy_a, "Strategy A", "#1f77b4"),
    (strategy_b, "Strategy B", "#ff7f0e"),
    (benchmark, "S&P 500 Benchmark", "#2ca02c"),
]

for df, name, color in strategies:
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["portfolio_value"],
            mode="lines",
            name=name,
            line={"color": color, "width": 2},
            hovertemplate=f"{name}<br>Date: %{{x}}<br>Value: $%{{y:,.2f}}<extra></extra>",
        )
    )

# Update layout
fig.update_layout(
    title="Strategy Comparison: A vs B vs Benchmark",
    xaxis_title="Date",
    yaxis_title="Portfolio Value ($)",
    template="plotly_white",
    hovermode="x unified",
    height=600,
    showlegend=True,
    legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
)

fig.show()
fig.write_html("strategy_comparison.html")
```

### Example 3: Dark Theme for Presentations

Create publication-quality charts with dark theme.

```python
from rustybt.analytics import (
    plot_equity_curve,
    plot_returns_distribution,
    plot_rolling_metrics,
)

# Dark theme for all charts
theme = "dark"

# Equity curve with drawdown
equity_fig = plot_equity_curve(
    backtest_df,
    title="Momentum Strategy - Equity Curve",
    theme=theme,
    show_drawdown=True,
)

# Returns distribution
returns_fig = plot_returns_distribution(
    backtest_df,
    title="Daily Returns Distribution",
    theme=theme,
    bins=60,
)

# Rolling metrics
rolling_fig = plot_rolling_metrics(
    backtest_df,
    window=90,
    title="Quarterly Rolling Performance",
    theme=theme,
)

# Save high-resolution PNG for presentations
equity_fig.write_image("equity_dark.png", width=1920, height=1080, scale=2)
returns_fig.write_image("returns_dark.png", width=1920, height=1080, scale=2)
rolling_fig.write_image("rolling_dark.png", width=1920, height=1080, scale=2)
```

### Example 4: Jupyter Notebook Integration

Create interactive charts in Jupyter notebooks with custom styling.

```python
# In Jupyter notebook cell
from rustybt.analytics import plot_equity_curve, plot_returns_distribution
import pandas as pd

# Configure Plotly for Jupyter
import plotly.io as pio
pio.renderers.default = "notebook"

# Load results
backtest_df = pd.read_parquet("backtest_results.parquet")

# Interactive equity curve
fig1 = plot_equity_curve(backtest_df, show_drawdown=True)
fig1.show()

# Interactive returns distribution
fig2 = plot_returns_distribution(backtest_df, bins=50)
fig2.show()

# Custom sizing
fig1.update_layout(width=1000, height=600)
fig1.show()
```

### Example 5: Export for Web Dashboards

Export charts for embedding in web applications.

```python
from rustybt.analytics import plot_equity_curve
import plotly.io as pio

# Create chart
fig = plot_equity_curve(backtest_df, theme="light")

# Export as HTML div (for embedding)
html_div = pio.to_html(fig, include_plotlyjs='cdn', div_id='equity-chart')

# Export as JSON (for frontend frameworks)
fig_json = fig.to_json()

# Export as static image
fig.write_image("equity.png", width=1200, height=800)
fig.write_image("equity.svg", width=1200, height=800)  # Vector format
```

### Example 6: Custom Color Themes

Create custom color themes for branding.

```python
import plotly.graph_objects as go
from rustybt.analytics.visualization import _ensure_pandas

# Define custom colors
custom_colors = {
    "background": "#0d1117",
    "paper": "#161b22",
    "text": "#c9d1d9",
    "grid": "#30363d",
    "positive": "#3fb950",
    "negative": "#f85149",
    "primary": "#58a6ff",
}

# Create custom equity curve
df = _ensure_pandas(backtest_df)
dates = df.index
values = df["portfolio_value"]

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=dates,
        y=values,
        mode="lines",
        name="Portfolio Value",
        line={"color": custom_colors["primary"], "width": 2.5},
        hovertemplate="Date: %{x}<br>Value: $%{y:,.2f}<extra></extra>",
    )
)

fig.update_layout(
    title="Custom Branded Equity Curve",
    template="plotly_dark",
    plot_bgcolor=custom_colors["background"],
    paper_bgcolor=custom_colors["paper"],
    font={"color": custom_colors["text"], "family": "Arial, sans-serif"},
    xaxis={"gridcolor": custom_colors["grid"], "title": "Date"},
    yaxis={"gridcolor": custom_colors["grid"], "title": "Portfolio Value ($)"},
    hovermode="x unified",
    height=600,
)

fig.show()
```

---

## Interpretation Guide

### Equity Curve Patterns

**Smooth Upward Trend**:
-  Consistent, stable returns
-  Low volatility
-  Good for risk-averse investors

**Steep Upward with Pullbacks**:
-  High returns but also high volatility
-  Expect periodic drawdowns
-  Requires strong risk tolerance

**Flat or Choppy**:
- L Strategy not generating alpha
- L May be underperforming benchmark
- L Consider parameter optimization

**Declining**:
- L Losing money
- L Strategy not working for this period/market
- L Requires immediate remediation

### Drawdown Analysis

**Max Drawdown < 10%**:
-  Low risk strategy
-  Suitable for conservative portfolios

**Max Drawdown 10-20%**:
-  Moderate risk
-  Acceptable for balanced portfolios

**Max Drawdown 20-30%**:
-  High risk
-  Only for aggressive investors

**Max Drawdown > 30%**:
- L Very high risk
- L Most investors will exit before recovery
- L Consider risk management improvements

**Drawdown Duration**:
- **Short recovery (< 3 months)**: Resilient strategy
- **Long recovery (> 6 months)**: Patience required, may lose investors
- **No recovery**: Strategy may be broken

### Returns Distribution

**Normal Distribution (bell curve)**:
-  Predictable risk profile
-  VaR models will be accurate
-  Easy to risk manage

**Negative Skew (left tail)**:
-  More frequent large losses
-  Use CVaR instead of VaR
-  Implement tail risk hedges

**Positive Skew (right tail)**:
-  More frequent large gains
-  Favorable asymmetry
-  Trend-following characteristics

**High Kurtosis (fat tails)**:
-  More extreme events than expected
-  Black swan risk
-  Increase position size limits

**Low Kurtosis (thin tails)**:
-  Fewer extreme events
-  Mean-reversion characteristics
-  Predictable returns

### Rolling Metrics

**Stable Sharpe Ratio**:
-  Consistent risk-adjusted performance
-  Strategy works in multiple regimes

**Declining Sharpe Ratio**:
-  Strategy degrading over time
-  May be experiencing regime change
-  Consider parameter re-optimization

**Increasing Volatility**:
-  Rising market risk
-  May need to reduce position sizes
-  Consider volatility-targeting

**Volatile Sharpe Ratio**:
-  Regime-dependent strategy
-  May need regime filters
-  Consider reducing exposure in low-Sharpe periods

---

## Best Practices

###  DO

1. **Use Interactive Charts for Exploration**:
   ```python
   # Interactive charts allow zooming and inspection
   fig = plot_equity_curve(backtest_df, show_drawdown=True)
   fig.show()  # Interactive in Jupyter
   ```

2. **Export Static Images for Reports**:
   ```python
   # High-resolution for presentations
   fig.write_image("chart.png", width=1920, height=1080, scale=2)
   ```

3. **Use Dark Theme for Presentations**:
   ```python
   # Better visibility on projectors
   fig = plot_equity_curve(backtest_df, theme="dark")
   ```

4. **Combine Multiple Visualizations**:
   ```python
   # Show complete picture
   plot_equity_curve(df).show()
   plot_returns_distribution(df).show()
   plot_rolling_metrics(df).show()
   ```

5. **Add Context with Titles and Annotations**:
   ```python
   fig = plot_equity_curve(
       backtest_df,
       title="Momentum Strategy (2020-2024) - SPY Universe"
   )
   ```

6. **Use Rolling Metrics to Detect Regime Changes**:
   ```python
   # Longer windows for trend detection
   fig = plot_rolling_metrics(backtest_df, window=90)
   ```

7. **Export HTML for Interactive Sharing**:
   ```python
   # Recipients can zoom and inspect
   fig.write_html("backtest_results.html")
   ```

### L DON'T

1. **Don't Use Too Many Bins for Returns Distribution**:
   ```python
   # L Too many bins - noisy histogram
   fig = plot_returns_distribution(backtest_df, bins=200)

   #  Optimal bins for clarity
   fig = plot_returns_distribution(backtest_df, bins=50)
   ```

2. **Don't Use Short Rolling Windows for Long Backtests**:
   ```python
   # L 10-day window on 5-year backtest - too noisy
   fig = plot_rolling_metrics(backtest_df, window=10)

   #  60-90 day window for trends
   fig = plot_rolling_metrics(backtest_df, window=60)
   ```

3. **Don't Mix DataFrames with Different Frequencies**:
   ```python
   # L Mixing daily and hourly data
   # Will cause misaligned dates

   #  Resample to common frequency first
   hourly_df = hourly_df.resample('D').last()
   ```

4. **Don't Ignore Drawdown Duration**:
   ```python
   # L Only looking at max drawdown magnitude

   #  Inspect drawdown chart for duration
   fig = plot_drawdown(backtest_df)
   # Look for long underwater periods
   ```

5. **Don't Use Light Theme on Projectors**:
   ```python
   # L Light theme washes out on projectors
   fig = plot_equity_curve(backtest_df, theme="light")

   #  Dark theme for presentations
   fig = plot_equity_curve(backtest_df, theme="dark")
   ```

6. **Don't Overwrite Existing Variables**:
   ```python
   # L Overwriting prevents comparison
   fig = plot_equity_curve(strategy_a)
   fig = plot_equity_curve(strategy_b)  # Lost strategy_a chart

   #  Use descriptive variable names
   fig_a = plot_equity_curve(strategy_a)
   fig_b = plot_equity_curve(strategy_b)
   ```

---

## Common Pitfalls

### Pitfall 1: Missing Required Columns

**Problem**: DataFrame missing expected columns.

```python
# L DataFrame without required columns
df = pd.DataFrame({"value": [100, 101, 102]})
fig = plot_equity_curve(df)  # ERROR: Missing portfolio_value

#  Ensure required columns exist
df = df.rename(columns={"value": "portfolio_value"})
df.index = pd.date_range('2024-01-01', periods=len(df))
fig = plot_equity_curve(df)  #  Works
```

**Solution**: Verify required columns before plotting:
- `plot_equity_curve()` requires `portfolio_value` or `ending_value`
- `plot_returns_distribution()` requires `returns` or `portfolio_value`
- All functions require datetime index or `date`/`timestamp` column

### Pitfall 2: Non-DateTime Index

**Problem**: Index is not datetime type.

```python
# L Integer index
df.index = range(len(df))
fig = plot_equity_curve(df)  # X-axis shows integers

#  Convert to datetime index
df.index = pd.date_range('2024-01-01', periods=len(df), freq='D')
fig = plot_equity_curve(df)  #  X-axis shows dates
```

### Pitfall 3: NaN Values Causing Gaps

**Problem**: NaN values create gaps in charts.

```python
# L NaN values in portfolio_value
df.loc['2024-03-15', 'portfolio_value'] = np.nan

#  Forward fill missing values
df['portfolio_value'] = df['portfolio_value'].ffill()

# Or drop NaN rows
df = df.dropna(subset=['portfolio_value'])
```

### Pitfall 4: Too Much Data for Rolling Windows

**Problem**: Rolling window too large for dataset.

```python
# L 252-day window on 100-day backtest
fig = plot_rolling_metrics(backtest_df, window=252)  # Mostly NaN

#  Window d 1/3 of total days
total_days = len(backtest_df)
window = min(60, total_days // 3)
fig = plot_rolling_metrics(backtest_df, window=window)
```

### Pitfall 5: Image Export Without kaleido

**Problem**: Cannot export static images without kaleido library.

```python
# L Will fail if kaleido not installed
fig.write_image("chart.png")  # ERROR: kaleido required

#  Install kaleido first
# pip install kaleido
fig.write_image("chart.png")
```

---

## Theme Customization

### Built-in Themes

**Light Theme** (default):
```python
fig = plot_equity_curve(backtest_df, theme="light")
```
- Background: White (`#ffffff`)
- Text: Dark gray (`#2e2e2e`)
- Positive: Green (`#00c853`)
- Negative: Red (`#d32f2f`)
- Primary: Blue (`#1976d2`)

**Dark Theme**:
```python
fig = plot_equity_curve(backtest_df, theme="dark")
```
- Background: Dark gray (`#1e1e1e`)
- Paper: Darker gray (`#2d2d2d`)
- Text: Light gray (`#e0e0e0`)
- Positive: Bright green (`#00ff88`)
- Negative: Bright red (`#ff5252`)
- Primary: Cyan (`#4fc3f7`)

### Custom Theme Example

```python
import plotly.graph_objects as go

# Create figure with custom colors
fig = plot_equity_curve(backtest_df, theme="light")

# Apply custom theme
fig.update_layout(
    plot_bgcolor="#f5f5f5",      # Light gray background
    paper_bgcolor="#ffffff",      # White paper
    font=dict(
        family="Roboto, sans-serif",
        size=12,
        color="#333333"
    ),
    title_font=dict(
        size=18,
        color="#1976d2"
    ),
)

# Update trace colors
fig.data[0].line.color = "#e91e63"  # Pink equity curve

fig.show()
```

---

## Jupyter Integration

### Display Configurations

```python
# Configure Plotly renderer for Jupyter
import plotly.io as pio

# For Jupyter Notebook
pio.renderers.default = "notebook"

# For JupyterLab
pio.renderers.default = "jupyterlab"

# For VS Code
pio.renderers.default = "vscode"

# For static HTML (no interactivity)
pio.renderers.default = "svg"
```

### Inline Display

```python
# Display inline in Jupyter
from rustybt.analytics import plot_equity_curve

fig = plot_equity_curve(backtest_df)
fig.show()  # Renders inline automatically
```

### Custom Sizing

```python
# Set figure size
fig = plot_equity_curve(backtest_df)
fig.update_layout(width=1000, height=600)
fig.show()
```

### Multiple Charts in One Cell

```python
# Display multiple charts vertically
from rustybt.analytics import (
    plot_equity_curve,
    plot_returns_distribution,
    plot_rolling_metrics,
)

# All charts display in order
plot_equity_curve(backtest_df).show()
plot_returns_distribution(backtest_df).show()
plot_rolling_metrics(backtest_df).show()
```

---

## Performance Considerations

### Time Complexity

| Function | Time Complexity | Typical Runtime |
|----------|----------------|-----------------|
| `plot_equity_curve()` | O(n) | < 100ms for 10K points |
| `plot_drawdown()` | O(n) | < 100ms for 10K points |
| `plot_returns_distribution()` | O(n) | < 50ms for 10K points |
| `plot_rolling_metrics()` | O(n  w) | 200ms for 10K points, w=60 |

where:
- n = number of data points
- w = rolling window size

### Memory Usage

- **Minimal**: Charts use DataFrame references, not copies
- **Plotly overhead**: ~2-5 MB per chart in browser
- **Export**: PNG files typically 200-500 KB

### Optimization Tips

1. **Downsample Large Datasets**:
   ```python
   # For 1M+ points, downsample before plotting
   df_daily = hourly_df.resample('D').last()
   fig = plot_equity_curve(df_daily)
   ```

2. **Use Fewer Bins for Large Datasets**:
   ```python
   # Fewer bins = faster rendering
   fig = plot_returns_distribution(large_df, bins=30)
   ```

3. **Disable Drawdown Subplot if Not Needed**:
   ```python
   # Faster rendering without subplot
   fig = plot_equity_curve(df, show_drawdown=False)
   ```

4. **Export Static Images for Large Reports**:
   ```python
   # Static images load faster than interactive HTML
   fig.write_image("chart.png")
   ```

---

## See Also

- [Analytics Overview](README.md) - Complete analytics suite
- [Risk Metrics](risk/README.md) - VaR, CVaR, stress testing
- [Performance Attribution](attribution/README.md) - Alpha/beta decomposition
- [Trade Analysis](trade-analysis/README.md) - MAE/MFE analysis
- [Report Generation](reports.md) - Automated report creation

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
