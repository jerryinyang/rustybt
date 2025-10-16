# Report Generation

Professional backtest report generation with charts, metrics, and customizable templates.

## Overview

**Purpose**: Automatically generate comprehensive, publication-quality reports from backtest results in PDF or HTML format.

**Key Features**:
-  **Automated Reports**: Generate complete reports from backtest DataFrames
- = **Rich Visualizations**: Equity curve, drawdown, returns distribution, position analysis
- = **Multiple Formats**: Export to HTML (interactive) or PDF (print-ready)
- < **Customizable**: Configure sections, branding, custom charts
- = **Comprehensive Metrics**: Sharpe ratio, Sortino ratio, max drawdown, win rate, profit factor
- =, **Empyrical Integration**: Accurate financial calculations using industry-standard library

**When to Use**:
-  For investor presentations and pitch decks
-  For documentation and audit trails
-  For strategy comparison reports
-  For regulatory compliance documentation

---

## Quick Start

### Basic HTML Report

```python
from rustybt.analytics.reports import ReportGenerator, ReportConfig
import pandas as pd

# Load backtest results
backtest_df = pd.read_parquet("backtest_results.parquet")

# Create default configuration
config = ReportConfig(
    title="My Strategy Report",
    subtitle="Momentum Strategy - SPY Universe"
)

# Generate report
generator = ReportGenerator(backtest_df, config)
generator.generate_report("report.html", format="html")

print(" Report saved to report.html")
```

### Basic PDF Report

```python
# Same setup, different format
generator = ReportGenerator(backtest_df, config)
generator.generate_report("report.pdf", format="pdf")

print(" Report saved to report.pdf")
```

### Minimal Example (Defaults)

```python
from rustybt.analytics.reports import ReportGenerator

# Use all defaults
generator = ReportGenerator(backtest_df)
generator.generate_report("report.html")  # Defaults to HTML
```

---

## API Reference

### ReportConfig

Configuration dataclass for customizing report generation.

**Signature**:
```python
@dataclass
class ReportConfig:
    title: str = "Backtest Report"
    subtitle: str | None = None
    logo_path: Path | None = None
    include_equity_curve: bool = True
    include_drawdown: bool = True
    include_returns_distribution: bool = True
    include_metrics_table: bool = True
    include_trade_statistics: bool = True
    include_position_distribution: bool = True
    custom_charts: list[Callable] = field(default_factory=list)
    dpi: int = 150
    figsize: tuple = (10, 6)
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | `"Backtest Report"` | Main report title |
| `subtitle` | `str \| None` | `None` | Optional subtitle |
| `logo_path` | `Path \| None` | `None` | Path to logo image (PNG/JPEG) |
| `include_equity_curve` | `bool` | `True` | Include equity curve chart |
| `include_drawdown` | `bool` | `True` | Include drawdown chart |
| `include_returns_distribution` | `bool` | `True` | Include returns histogram |
| `include_metrics_table` | `bool` | `True` | Include performance metrics table |
| `include_trade_statistics` | `bool` | `True` | Include trade statistics |
| `include_position_distribution` | `bool` | `True` | Include position distribution chart |
| `custom_charts` | `list[Callable]` | `[]` | List of custom chart functions |
| `dpi` | `int` | `150` | Chart resolution (150 screen, 300 print) |
| `figsize` | `tuple` | `(10, 6)` | Default figure size (width, height) inches |

**Example**:
```python
from rustybt.analytics.reports import ReportConfig
from pathlib import Path

# Minimal report (only essentials)
config = ReportConfig(
    title="Quick Report",
    include_position_distribution=False,
    include_trade_statistics=False
)

# Professional report (high quality)
config = ReportConfig(
    title="Q4 2024 Performance Report",
    subtitle="Algorithmic Trading Strategy",
    logo_path=Path("company_logo.png"),
    dpi=300,  # High resolution for print
    figsize=(12, 8)
)

# Custom sections only
config = ReportConfig(
    include_equity_curve=True,
    include_drawdown=True,
    include_returns_distribution=False,
    include_metrics_table=True,
    include_trade_statistics=False,
    include_position_distribution=False
)
```

---

### ReportGenerator

Main class for generating backtest reports.

**Signature**:
```python
class ReportGenerator:
    def __init__(
        self,
        backtest_result: pd.DataFrame | pl.DataFrame,
        config: ReportConfig | None = None
    )

    def generate_report(
        self,
        output_path: str | Path,
        format: str = "html"
    ) -> None
```

**Constructor Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `backtest_result` | `pd.DataFrame \| pl.DataFrame` | Backtest results with `portfolio_value` and datetime index |
| `config` | `ReportConfig \| None` | Report configuration (uses defaults if None) |

**Required DataFrame Columns**:
- **Datetime index** or `date`/`timestamp` column
- **Value column**: `portfolio_value` or `ending_value`
- **Optional**: `returns` (calculated from portfolio_value if missing)

**Methods**:

#### generate_report()

Generate and save report to file.

```python
def generate_report(
    self,
    output_path: str | Path,
    format: str = "html"
) -> None
```

**Parameters**:
- `output_path`: Path where report will be saved (`.html` or `.pdf`)
- `format`: Output format - `"html"` (default) or `"pdf"`

**Raises**:
- `ValueError`: If format is not supported or DataFrame missing required columns

**Example**:
```python
from rustybt.analytics.reports import ReportGenerator, ReportConfig

# Initialize
generator = ReportGenerator(backtest_df, config)

# Generate HTML (interactive, shareable)
generator.generate_report("investor_report.html", format="html")

# Generate PDF (print-ready, portable)
generator.generate_report("investor_report.pdf", format="pdf")
```

---

## Performance Metrics Included

### Core Metrics (Always Calculated)

| Metric | Description | Calculation |
|--------|-------------|-------------|
| **Total Return** | Cumulative return over period | `(final_value - initial_value) / initial_value` |
| **Annual Return** | Annualized return | `(1 + total_return)^(1/years) - 1` |
| **Sharpe Ratio** | Risk-adjusted return | `annual_return / annual_volatility` |
| **Sortino Ratio** | Downside risk-adjusted return | `annual_return / downside_deviation` |
| **Max Drawdown** | Largest peak-to-trough decline | `max((portfolio - cummax) / cummax)` |
| **Calmar Ratio** | Return vs max drawdown | `annual_return / abs(max_drawdown)` |
| **Volatility** | Annualized standard deviation | `std(returns) * sqrt(252)` |
| **Trading Days** | Number of trading periods | `len(returns)` |

### Enhanced Metrics (With Empyrical)

If `empyrical` library is installed, additional metrics are calculated:

| Metric | Description |
|--------|-------------|
| **Stability** | R-squared of equity curve linear regression |
| **Tail Ratio** | Ratio of right tail (95th percentile) to left tail (5th percentile) |

**Install empyrical for enhanced metrics**:
```bash
pip install empyrical
```

---

## Trade Statistics Included

| Statistic | Description |
|-----------|-------------|
| **Total Trades** | Number of trading periods analyzed |
| **Winning Trades** | Number of positive return periods |
| **Losing Trades** | Number of negative return periods |
| **Win Rate** | Percentage of profitable trades |
| **Average Win** | Mean return of winning trades |
| **Average Loss** | Mean return of losing trades |
| **Profit Factor** | Total profit / total loss |
| **Largest Win** | Maximum single-period gain |
| **Largest Loss** | Maximum single-period loss |

**Note**: Trade statistics use daily returns as proxy for trades. For true trade-level statistics, use TradeAnalyzer separately.

---

## Complete Examples

### Example 1: Professional Investor Report

Complete report with all sections and branding.

```python
from rustybt.analytics.reports import ReportGenerator, ReportConfig
from pathlib import Path
import pandas as pd

# Load backtest results
backtest_df = pd.read_parquet("backtest_results.parquet")

# Professional configuration
config = ReportConfig(
    title="Algorithmic Trading Strategy Performance",
    subtitle="Momentum-Based Equity Strategy | 2020-2024",
    logo_path=Path("firm_logo.png"),
    dpi=300,  # High resolution for print
    figsize=(12, 8),
    include_equity_curve=True,
    include_drawdown=True,
    include_returns_distribution=True,
    include_metrics_table=True,
    include_trade_statistics=True,
    include_position_distribution=True
)

# Generate both formats
generator = ReportGenerator(backtest_df, config)

# HTML for email/web sharing
generator.generate_report("investor_report.html", format="html")

# PDF for presentations/printing
generator.generate_report("investor_report.pdf", format="pdf")

print(" Reports generated:")
print("  - investor_report.html (interactive)")
print("  - investor_report.pdf (print-ready)")
```

### Example 2: Quick Summary Report

Minimal report with essential metrics only.

```python
from rustybt.analytics.reports import ReportGenerator, ReportConfig

# Quick summary configuration
config = ReportConfig(
    title="Strategy Quick Summary",
    include_equity_curve=True,
    include_drawdown=True,
    include_returns_distribution=False,  # Skip for speed
    include_metrics_table=True,
    include_trade_statistics=False,      # Skip for speed
    include_position_distribution=False, # Skip for speed
    dpi=150  # Standard resolution
)

# Generate fast summary
generator = ReportGenerator(backtest_df, config)
generator.generate_report("quick_summary.html")

print(" Quick summary report generated")
```

### Example 3: Custom Charts

Add custom analysis charts to the report.

```python
from rustybt.analytics.reports import ReportGenerator, ReportConfig
import matplotlib.pyplot as plt
import numpy as np

# Define custom chart functions
def custom_monthly_returns(df):
    """Generate monthly returns heatmap."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Calculate monthly returns
    monthly_returns = df['portfolio_value'].resample('M').last().pct_change()

    # Create bar chart
    ax.bar(monthly_returns.index, monthly_returns.values * 100,
           color=['green' if x > 0 else 'red' for x in monthly_returns.values])

    ax.set_title("Monthly Returns (%)", fontsize=14, fontweight='bold')
    ax.set_xlabel("Month")
    ax.set_ylabel("Return (%)")
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color='black', linewidth=0.8)

    plt.tight_layout()
    return fig

def custom_rolling_volatility(df):
    """Generate rolling 30-day volatility."""
    fig, ax = plt.subplots(figsize=(10, 6))

    returns = df['portfolio_value'].pct_change()
    rolling_vol = returns.rolling(30).std() * np.sqrt(252) * 100

    ax.plot(rolling_vol.index, rolling_vol.values, linewidth=2, color='#ff5722')
    ax.set_title("30-Day Rolling Volatility (%)", fontsize=14, fontweight='bold')
    ax.set_xlabel("Date")
    ax.set_ylabel("Annualized Volatility (%)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig

# Configure with custom charts
config = ReportConfig(
    title="Extended Analysis Report",
    custom_charts=[
        custom_monthly_returns,
        custom_rolling_volatility
    ]
)

# Generate report with custom charts
generator = ReportGenerator(backtest_df, config)
generator.generate_report("extended_report.html")

print(" Extended report with custom charts generated")
```

### Example 4: Multi-Strategy Comparison

Generate reports for multiple strategies.

```python
from rustybt.analytics.reports import ReportGenerator, ReportConfig
import pandas as pd

# Load multiple strategy results
strategies = {
    "Momentum": pd.read_parquet("momentum_results.parquet"),
    "Mean Reversion": pd.read_parquet("mean_reversion_results.parquet"),
    "Trend Following": pd.read_parquet("trend_following_results.parquet")
}

# Generate report for each strategy
for strategy_name, backtest_df in strategies.items():
    config = ReportConfig(
        title=f"{strategy_name} Strategy Performance",
        subtitle="Comparative Analysis | 2020-2024",
        dpi=300
    )

    generator = ReportGenerator(backtest_df, config)

    # Generate both formats
    generator.generate_report(f"{strategy_name}_report.html", format="html")
    generator.generate_report(f"{strategy_name}_report.pdf", format="pdf")

    print(f" Generated reports for {strategy_name}")

print("\n All strategy reports generated")
```

### Example 5: Automated Reporting Pipeline

Integrate report generation into backtest workflow.

```python
from rustybt.analytics.reports import ReportGenerator, ReportConfig
from rustybt.algorithm import TradingAlgorithm
import pandas as pd
from pathlib import Path

def run_backtest_with_report(strategy_class, data, strategy_name):
    """Run backtest and automatically generate report."""

    # Run backtest
    algo = strategy_class()
    result = algo.run(data)

    # Convert to DataFrame
    backtest_df = result.to_dataframe()

    # Save backtest results
    backtest_df.to_parquet(f"{strategy_name}_results.parquet")

    # Generate report
    config = ReportConfig(
        title=f"{strategy_name} Backtest Report",
        subtitle=f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        dpi=300
    )

    generator = ReportGenerator(backtest_df, config)
    generator.generate_report(f"{strategy_name}_report.html", format="html")
    generator.generate_report(f"{strategy_name}_report.pdf", format="pdf")

    print(f" Backtest complete for {strategy_name}")
    print(f"   - Results: {strategy_name}_results.parquet")
    print(f"   - HTML Report: {strategy_name}_report.html")
    print(f"   - PDF Report: {strategy_name}_report.pdf")

    return result

# Run multiple strategies with automatic reporting
strategies = [
    (MomentumStrategy, spy_data, "Momentum_SPY"),
    (MeanReversionStrategy, qqq_data, "MeanReversion_QQQ"),
]

for strategy_class, data, name in strategies:
    run_backtest_with_report(strategy_class, data, name)
```

### Example 6: HTML Email Reports

Generate HTML reports for email distribution.

```python
from rustybt.analytics.reports import ReportGenerator, ReportConfig
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Generate compact HTML report
config = ReportConfig(
    title="Daily Strategy Update",
    include_position_distribution=False,  # Reduce email size
    dpi=100  # Lower resolution for email
)

generator = ReportGenerator(backtest_df, config)
generator.generate_report("daily_report.html", format="html")

# Read HTML content
html_content = Path("daily_report.html").read_text()

# Send email
msg = MIMEMultipart('alternative')
msg['Subject'] = "Daily Strategy Performance Report"
msg['From'] = "reporting@example.com"
msg['To'] = "investors@example.com"

# Attach HTML
html_part = MIMEText(html_content, 'html')
msg.attach(html_part)

# Send (configure SMTP settings)
# smtp = smtplib.SMTP('smtp.gmail.com', 587)
# smtp.starttls()
# smtp.login(username, password)
# smtp.send_message(msg)
# smtp.quit()

print(" Email report prepared")
```

---

## Report Sections

### HTML Report Structure

HTML reports include the following sections in order:

1. **Header**:
   - Title and subtitle
   - Optional logo
   - Generation timestamp

2. **Performance Metrics Table**:
   - Total return, annual return
   - Sharpe ratio, Sortino ratio
   - Max drawdown, Calmar ratio
   - Volatility, trading days
   - (Enhanced metrics if empyrical available)

3. **Equity Curve Chart**:
   - Portfolio value over time
   - Interactive chart (can zoom/pan in browser)

4. **Drawdown Chart**:
   - Drawdown percentage over time
   - Max drawdown annotation

5. **Returns Distribution**:
   - Histogram with KDE overlay
   - Statistics box (mean, std dev, skewness, kurtosis)

6. **Position Distribution** (if available):
   - Top 10 positions bar chart
   - Average position sizes

7. **Trade Statistics Table**:
   - Win rate, profit factor
   - Average win/loss
   - Largest win/loss

8. **Custom Charts** (if configured):
   - User-defined analysis charts

9. **Footer**:
   - Generation timestamp
   - Framework version

### PDF Report Structure

PDF reports are multi-page documents:

1. **Page 1: Title Page**
   - Title, subtitle
   - Date range
   - Key metrics summary
   - Generation timestamp

2. **Page 2: Equity Curve**
   - Full-page equity curve chart

3. **Page 3: Drawdown**
   - Full-page drawdown chart

4. **Page 4: Returns Distribution**
   - Full-page histogram with statistics

5. **Page 5: Position Distribution**
   - Full-page position analysis

6. **Additional Pages: Custom Charts**
   - One chart per page

---

## Interpretation Guide

### Performance Metrics Thresholds

**Total Return**:
- `> 20%`: Strong performance
- `10-20%`: Good performance
- `5-10%`: Moderate performance
- `< 5%`: Underperforming

**Sharpe Ratio**:
- `> 2.0`: Excellent risk-adjusted returns
- `1.0-2.0`: Good risk-adjusted returns
- `0.5-1.0`: Acceptable risk-adjusted returns
- `< 0.5`: Poor risk-adjusted returns

**Sortino Ratio**:
- Usually higher than Sharpe ratio (focuses on downside risk only)
- `> 2.0`: Excellent downside risk management
- `1.0-2.0`: Good downside risk management

**Max Drawdown**:
- `< 10%`: Low risk
- `10-20%`: Moderate risk
- `20-30%`: High risk
- `> 30%`: Very high risk

**Calmar Ratio**:
- `> 1.0`: Return exceeds max drawdown
- `0.5-1.0`: Acceptable risk/return tradeoff
- `< 0.5`: Return does not justify drawdown risk

### Trade Statistics Interpretation

**Win Rate**:
- `> 60%`: High win rate (may have small wins)
- `50-60%`: Moderate win rate
- `40-50%`: Low win rate (needs high profit factor)
- `< 40%`: Very low win rate (risky unless profit factor > 2)

**Profit Factor**:
- `> 2.0`: Very profitable
- `1.5-2.0`: Profitable
- `1.0-1.5`: Marginally profitable
- `< 1.0`: Unprofitable

**Average Win / Average Loss**:
- `> 2.0`: Large wins vs losses (trend-following)
- `1.0-2.0`: Balanced
- `< 1.0`: Small wins, large losses (mean-reversion with risk)

---

## Best Practices

###  DO

1. **Generate Both HTML and PDF**:
   ```python
   # HTML for interactivity, PDF for archival
   generator.generate_report("report.html", format="html")
   generator.generate_report("report.pdf", format="pdf")
   ```

2. **Use High DPI for Print Reports**:
   ```python
   config = ReportConfig(dpi=300)  # Print quality
   ```

3. **Include Subtitle with Context**:
   ```python
   config = ReportConfig(
       title="Strategy Performance",
       subtitle="SPY Universe | 2020-2024 | Daily Rebalancing"
   )
   ```

4. **Add Branding for Professional Reports**:
   ```python
   config = ReportConfig(logo_path=Path("company_logo.png"))
   ```

5. **Version Control Report Configurations**:
   ```python
   # Save configs for reproducibility
   import json
   config_dict = {
       "title": config.title,
       "dpi": config.dpi,
       # ... other settings
   }
   with open("report_config.json", "w") as f:
       json.dump(config_dict, f)
   ```

6. **Automate Report Generation in Workflows**:
   ```python
   # Always generate report after backtest
   result = algo.run(data)
   generator = ReportGenerator(result.to_dataframe())
   generator.generate_report("latest_report.html")
   ```

### L DON'T

1. **Don't Use Low DPI for Print Reports**:
   ```python
   # L Low quality for printing
   config = ReportConfig(dpi=72)

   #  High quality for print
   config = ReportConfig(dpi=300)
   ```

2. **Don't Skip Empyrical for Production**:
   ```python
   # L Missing enhanced metrics
   # (no empyrical installed)

   #  Install empyrical for accurate metrics
   # pip install empyrical
   ```

3. **Don't Generate Reports Without Validation**:
   ```python
   # L Generate report with bad data
   generator = ReportGenerator(empty_df)  # Will fail

   #  Validate data first
   if len(backtest_df) > 0 and 'portfolio_value' in backtest_df.columns:
       generator = ReportGenerator(backtest_df)
       generator.generate_report("report.html")
   ```

4. **Don't Hardcode Paths**:
   ```python
   # L Hardcoded path
   generator.generate_report("/Users/john/reports/report.html")

   #  Use configurable paths
   from pathlib import Path
   report_dir = Path("reports")
   report_dir.mkdir(exist_ok=True)
   generator.generate_report(report_dir / "report.html")
   ```

5. **Don't Include All Sections if Unnecessary**:
   ```python
   # L All sections when data not available
   config = ReportConfig(include_position_distribution=True)
   # But no position data exists

   #  Only include relevant sections
   config = ReportConfig(
       include_position_distribution=False,  # No position data
       include_trade_statistics=True
   )
   ```

---

## Common Pitfalls

### Pitfall 1: Missing Required Columns

**Problem**: DataFrame missing `portfolio_value` or `ending_value` column.

```python
# L Missing required column
df = pd.DataFrame({"returns": [0.01, 0.02, -0.01]})
generator = ReportGenerator(df)  # ERROR: Missing portfolio_value

#  Ensure required column exists
df['portfolio_value'] = (1 + df['returns']).cumprod() * 100000
generator = ReportGenerator(df)  #  Works
```

### Pitfall 2: Non-DateTime Index

**Problem**: Index is not datetime type.

```python
# L Integer index
df.index = range(len(df))

#  Convert to datetime index
df.index = pd.date_range('2024-01-01', periods=len(df), freq='D')
```

### Pitfall 3: Empty or Very Short DataFrames

**Problem**: Not enough data for meaningful metrics.

```python
# L Only 5 data points
short_df = backtest_df.head(5)
generator = ReportGenerator(short_df)  # Metrics will be unreliable

#  Ensure sufficient data
if len(backtest_df) >= 30:  # At least 30 days
    generator = ReportGenerator(backtest_df)
    generator.generate_report("report.html")
else:
    print(" Insufficient data for reliable metrics")
```

### Pitfall 4: Logo File Not Found

**Problem**: Logo path specified but file doesn't exist.

```python
# L File doesn't exist
config = ReportConfig(logo_path=Path("logo.png"))  # FileNotFoundError

#  Check file exists
from pathlib import Path
logo_path = Path("logo.png")
if logo_path.exists():
    config = ReportConfig(logo_path=logo_path)
else:
    config = ReportConfig(logo_path=None)
```

### Pitfall 5: Custom Chart Functions with Errors

**Problem**: Custom chart function raises exception.

```python
# L Custom chart with error
def broken_chart(df):
    fig, ax = plt.subplots()
    ax.plot(df['nonexistent_column'])  # KeyError
    return fig

config = ReportConfig(custom_charts=[broken_chart])

#  Validate custom charts
def safe_custom_chart(df):
    fig, ax = plt.subplots()
    try:
        if 'portfolio_value' in df.columns:
            ax.plot(df.index, df['portfolio_value'])
        else:
            ax.text(0.5, 0.5, "Data not available", ha='center')
    except Exception as e:
        ax.text(0.5, 0.5, f"Error: {str(e)}", ha='center')
    return fig

config = ReportConfig(custom_charts=[safe_custom_chart])
```

---

## HTML vs PDF Comparison

| Feature | HTML | PDF |
|---------|------|-----|
| **File Size** | 500KB - 2MB | 200KB - 1MB |
| **Interactivity** | L Static charts (matplotlib) | L Static only |
| **Shareability** |  Easy to email |  Universal format |
| **Print Quality** |  Browser-dependent |  Consistent |
| **Editing** |  Can modify HTML | L Read-only |
| **Multi-Page** | Single scroll |  Paginated |
| **Generation Speed** | Fast (~1-2 seconds) | Moderate (~2-4 seconds) |
| **Best For** | Email, web sharing | Presentations, printing, archival |

**Recommendation**: Generate both formats for maximum flexibility.

---

## Performance Considerations

### Generation Time

| Report Type | Time Complexity | Typical Runtime |
|-------------|-----------------|-----------------|
| HTML (default sections) | O(n) | 1-2 seconds (10K points) |
| PDF (default sections) | O(n) | 2-4 seconds (10K points) |
| With custom charts | O(n  c) | +0.5s per custom chart |

where:
- n = number of data points
- c = number of custom charts

### File Sizes

- **HTML**: 500KB - 2MB (embedded base64 images)
- **PDF**: 200KB - 1MB (more compact)
- **With high DPI** (300): 2-3 larger files

### Optimization Tips

1. **Reduce DPI for Large Batches**:
   ```python
   config = ReportConfig(dpi=150)  # Faster generation
   ```

2. **Disable Unused Sections**:
   ```python
   config = ReportConfig(
       include_position_distribution=False,  # Skip if no data
       include_trade_statistics=False        # Skip if not needed
   )
   ```

3. **Limit Custom Charts**:
   ```python
   # L Too many custom charts
   config = ReportConfig(custom_charts=[chart1, chart2, ..., chart10])

   #  Essential charts only
   config = ReportConfig(custom_charts=[monthly_returns, rolling_vol])
   ```

4. **Downsample Large Datasets**:
   ```python
   # For 1M+ points, downsample before reporting
   if len(backtest_df) > 100000:
       backtest_df = backtest_df.resample('D').last()

   generator = ReportGenerator(backtest_df)
   ```

---

## See Also

- [Analytics Overview](README.md) - Complete analytics suite
- [Visualization Tools](visualization.md) - Interactive Plotly charts
- [Risk Metrics](risk/README.md) - VaR, CVaR analysis
- [Performance Attribution](attribution/README.md) - Alpha/beta decomposition
- [Trade Analysis](trade-analysis/README.md) - MAE/MFE analysis

---

## References

- **Empyrical**: [https://github.com/quantopian/empyrical](https://github.com/quantopian/empyrical) - Industry-standard Python library for financial metrics
- **Matplotlib**: [https://matplotlib.org/](https://matplotlib.org/) - Publication-quality charts
- **Jinja2**: [https://jinja.palletsprojects.com/](https://jinja.palletsprojects.com/) - Template engine for HTML reports

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
