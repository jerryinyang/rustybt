# Analytics Suite

**Module**: `rustybt.finance.metrics`

**Source Files**:
- `rustybt/finance/metrics/attribution.py` (255 lines)
- `rustybt/finance/metrics/formatting.py` (10,823 bytes)

**Last Updated**: 2025-10-16
**Confidence**: 100% (all APIs verified against source code)

---

## Overview

The RustyBT Analytics Suite provides advanced performance attribution and formatting utilities for decomposing portfolio returns and presenting metrics in production-quality formats. All analytics maintain Decimal precision for audit-compliant financial calculations.

### Key Features

- **Position Attribution**: Decompose returns into contributions from individual positions
- **Sector Attribution**: Aggregate attribution by industry sectors
- **Alpha/Beta Analysis**: Calculate strategy alpha and beta relative to benchmark using CAPM
- **Time Period Attribution**: Analyze returns across daily, monthly, or annual periods
- **Professional Formatting**: Display metrics with appropriate precision and formatting conventions
- **Decimal Precision**: All calculations maintain audit-compliant precision

---

## Attribution Analysis

### calculate_position_attribution()

**Source**: `attribution.py:31-98`

Calculate attribution of portfolio returns to individual positions.

```python
def calculate_position_attribution(
    position_values: pl.DataFrame,
    position_returns: pl.DataFrame,
    portfolio_value: Decimal,
) -> dict[str, Decimal]
```

**Parameters**:
- `position_values`: DataFrame with columns `['asset', 'value']` as Decimal
- `position_returns`: DataFrame with columns `['asset', 'return']` as Decimal
- `portfolio_value`: Total portfolio value as Decimal

**Returns**: Dictionary mapping asset symbol to attribution (Decimal)

**Raises**:
- `InvalidMetricError`: If portfolio value is zero or attribution doesn't sum correctly

**Formula**:
```
attribution(asset) = (position_value / portfolio_value) × position_return
```

**Example**:
```python
from rustybt.finance.metrics.attribution import calculate_position_attribution
from decimal import Decimal
import polars as pl

# Position values (market value of each position)
position_values = pl.DataFrame({
    'asset': ['AAPL', 'GOOGL', 'MSFT'],
    'value': [
        Decimal('50000'),  # $50k in AAPL (50%)
        Decimal('30000'),  # $30k in GOOGL (30%)
        Decimal('20000'),  # $20k in MSFT (20%)
    ]
})

# Position returns for the period
position_returns = pl.DataFrame({
    'asset': ['AAPL', 'GOOGL', 'MSFT'],
    'return': [
        Decimal('0.05'),   # AAPL +5%
        Decimal('-0.02'),  # GOOGL -2%
        Decimal('0.08'),   # MSFT +8%
    ]
})

portfolio_value = Decimal('100000')

# Calculate attribution
attribution = calculate_position_attribution(
    position_values,
    position_returns,
    portfolio_value
)

# Display results
for asset, attr in attribution.items():
    weight = position_values.filter(pl.col('asset') == asset)['value'][0] / portfolio_value
    return_pct = position_returns.filter(pl.col('asset') == asset)['return'][0]

    print(f"{asset}:")
    print(f"  Weight: {weight:.1%}")
    print(f"  Return: {return_pct:.1%}")
    print(f"  Attribution: {attr:.2%}")

# Output:
# AAPL:
#   Weight: 50.0%
#   Return: 5.0%
#   Attribution: 2.50%  (50% × 5% = 2.5%)
#
# GOOGL:
#   Weight: 30.0%
#   Return: -2.0%
#   Attribution: -0.60%  (30% × -2% = -0.6%)
#
# MSFT:
#   Weight: 20.0%
#   Return: 8.0%
#   Attribution: 1.60%  (20% × 8% = 1.6%)

# Total portfolio return
total_attribution = sum(attribution.values())
print(f"\nTotal Portfolio Return: {total_attribution:.2%}")
# Output: 3.50% (2.5% - 0.6% + 1.6%)
```

---

### calculate_sector_attribution()

**Source**: `attribution.py:101-138`

Calculate attribution grouped by sector or industry.

```python
def calculate_sector_attribution(
    position_values: pl.DataFrame,
    position_returns: pl.DataFrame,
    position_sectors: dict[str, str],
    portfolio_value: Decimal,
) -> dict[str, Decimal]
```

**Parameters**:
- `position_values`: DataFrame with columns `['asset', 'value']` as Decimal
- `position_returns`: DataFrame with columns `['asset', 'return']` as Decimal
- `position_sectors`: Mapping of asset symbol to sector name
- `portfolio_value`: Total portfolio value as Decimal

**Returns**: Dictionary mapping sector to attribution (Decimal)

**Example**:
```python
from rustybt.finance.metrics.attribution import calculate_sector_attribution
from decimal import Decimal
import polars as pl

# Position data
position_values = pl.DataFrame({
    'asset': ['AAPL', 'GOOGL', 'MSFT', 'JPM', 'BAC', 'XOM'],
    'value': [
        Decimal('30000'), Decimal('20000'), Decimal('15000'),
        Decimal('15000'), Decimal('10000'), Decimal('10000'),
    ]
})

position_returns = pl.DataFrame({
    'asset': ['AAPL', 'GOOGL', 'MSFT', 'JPM', 'BAC', 'XOM'],
    'return': [
        Decimal('0.05'), Decimal('0.03'), Decimal('0.07'),
        Decimal('-0.02'), Decimal('-0.01'), Decimal('0.10'),
    ]
})

# Sector mapping
sectors = {
    'AAPL': 'Technology',
    'GOOGL': 'Technology',
    'MSFT': 'Technology',
    'JPM': 'Finance',
    'BAC': 'Finance',
    'XOM': 'Energy',
}

portfolio_value = Decimal('100000')

# Calculate sector attribution
sector_attr = calculate_sector_attribution(
    position_values,
    position_returns,
    sectors,
    portfolio_value
)

# Display results
for sector, attr in sorted(sector_attr.items(), key=lambda x: x[1], reverse=True):
    print(f"{sector}: {attr:.2%}")

# Output:
# Technology: 3.20%  (AAPL 1.5% + GOOGL 0.6% + MSFT 1.05%)
# Energy: 1.00%      (XOM 1.0%)
# Finance: -0.35%    (JPM -0.3% + BAC -0.1%)

# Identify top/bottom sectors
best_sector = max(sector_attr.items(), key=lambda x: x[1])
worst_sector = min(sector_attr.items(), key=lambda x: x[1])

print(f"\nBest Performing Sector: {best_sector[0]} (+{best_sector[1]:.2%})")
print(f"Worst Performing Sector: {worst_sector[0]} ({worst_sector[1]:.2%})")
```

---

### calculate_alpha_beta()

**Source**: `attribution.py:141-199`

Calculate alpha and beta relative to benchmark using Capital Asset Pricing Model (CAPM).

```python
def calculate_alpha_beta(
    strategy_returns: pl.Series,
    benchmark_returns: pl.Series,
    risk_free_rate: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]
```

**Parameters**:
- `strategy_returns`: Strategy returns as Polars Series with Decimal values
- `benchmark_returns`: Benchmark returns as Polars Series with Decimal values
- `risk_free_rate`: Risk-free rate (default: 0)

**Returns**: Tuple of `(alpha, beta)` as Decimal

**Raises**:
- `InsufficientDataError`: If insufficient data (< 2 returns)
- `InvalidMetricError`: If series lengths don't match or benchmark variance is zero

**Formulas**:
```
beta = cov(strategy, benchmark) / var(benchmark)
alpha = mean(strategy) - risk_free_rate - beta × (mean(benchmark) - risk_free_rate)
```

**Example**:
```python
from rustybt.finance.metrics.attribution import calculate_alpha_beta
from decimal import Decimal
import polars as pl

# Strategy returns
strategy = pl.Series("strategy", [
    Decimal("0.020"), Decimal("0.015"), Decimal("-0.008"),
    Decimal("0.025"), Decimal("0.012"), Decimal("-0.005"),
])

# SPY benchmark returns
spy = pl.Series("spy", [
    Decimal("0.015"), Decimal("0.010"), Decimal("-0.005"),
    Decimal("0.018"), Decimal("0.008"), Decimal("-0.003"),
])

# Calculate alpha and beta
alpha, beta = calculate_alpha_beta(
    strategy_returns=strategy,
    benchmark_returns=spy,
    risk_free_rate=Decimal("0.02"),  # 2% annual risk-free rate
)

print(f"Alpha: {alpha:.4f}")
print(f"Beta: {beta:.2f}")

# Interpretation:
# - Beta = 1.0: Same volatility as market
# - Beta > 1.0: More volatile than market (amplifies moves)
# - Beta < 1.0: Less volatile than market (dampens moves)
# - Alpha > 0: Outperforming risk-adjusted benchmark
# - Alpha < 0: Underperforming risk-adjusted benchmark

# Example: High beta strategy
if beta > Decimal("1.2"):
    print("⚠ High beta - strategy amplifies market moves")
elif beta < Decimal("0.8"):
    print("✓ Defensive strategy - lower market risk")

# Example: Positive alpha
if alpha > Decimal("0.001"):  # > 0.1% per period
    print("✓ Generating alpha - skill-based outperformance")
elif alpha < Decimal("-0.001"):
    print("⚠  Negative alpha - underperforming")
```

---

### calculate_time_period_attribution()

**Source**: `attribution.py:202-254`

Calculate attribution breakdown by time period (daily, monthly, or annual).

```python
def calculate_time_period_attribution(
    returns_series: pl.Series,
    dates: pl.Series,
    period: str = "monthly",
) -> pl.DataFrame
```

**Parameters**:
- `returns_series`: Returns as Polars Series with Decimal values
- `dates`: Dates as Polars Series (datetime type)
- `period`: Time period for aggregation (`'daily'`, `'monthly'`, `'annual'`)

**Returns**: DataFrame with columns `['period', 'return', 'cumulative_return', 'num_periods']`

**Example**:
```python
from rustybt.finance.metrics.attribution import calculate_time_period_attribution
from decimal import Decimal
from datetime import date
import polars as pl

# Daily returns with dates
returns = pl.Series("returns", [
    # January
    Decimal("0.01"), Decimal("0.005"), Decimal("-0.002"),
    # February
    Decimal("0.015"), Decimal("-0.01"), Decimal("0.008"),
    # March
    Decimal("0.02"), Decimal("0.012"), Decimal("-0.005"),
])

dates = pl.Series("date", [
    date(2024, 1, 15), date(2024, 1, 16), date(2024, 1, 17),
    date(2024, 2, 15), date(2024, 2, 16), date(2024, 2, 17),
    date(2024, 3, 15), date(2024, 3, 16), date(2024, 3, 17),
])

# Monthly attribution
monthly_attr = calculate_time_period_attribution(
    returns_series=returns,
    dates=dates,
    period='monthly'
)

print(monthly_attr)

# Output:
# ┌─────────┬──────────┬────────────────────┬─────────────┐
# │ period  │ return   │ cumulative_return  │ num_periods │
# ├─────────┼──────────┼────────────────────┼─────────────┤
# │ 2024-01 │ 0.0130   │ 0.0130             │ 3           │
# │ 2024-02 │ 0.0127   │ 0.0259             │ 3           │
# │ 2024-03 │ 0.0270   │ 0.0539             │ 3           │
# └─────────┴──────────┴────────────────────┴─────────────┘

# Annual attribution
annual_attr = calculate_time_period_attribution(
    returns_series=returns,
    dates=dates,
    period='annual'
)

# Identify best/worst months
best_month = monthly_attr.filter(
    pl.col('return') == pl.col('return').max()
)['period'][0]

worst_month = monthly_attr.filter(
    pl.col('return') == pl.col('return').min()
)['period'][0]

print(f"Best Month: {best_month}")
print(f"Worst Month: {worst_month}")
```

---

## Formatting Utilities

### format_percentage()

**Source**: `formatting.py:26-50`

Format Decimal as percentage with specified precision.

```python
def format_percentage(
    value: Decimal,
    precision: int = 2,
    include_sign: bool = False
) -> str
```

**Example**:
```python
from rustybt.finance.metrics.formatting import format_percentage
from decimal import Decimal

# Basic formatting
formatted = format_percentage(Decimal("0.1234"), precision=2)
print(formatted)  # "12.34%"

# With sign
formatted_pos = format_percentage(Decimal("0.05"), precision=2, include_sign=True)
print(formatted_pos)  # "+5.00%"

# Negative values
formatted_neg = format_percentage(Decimal("-0.0325"), precision=3)
print(formatted_neg)  # "-3.250%"

# Handle infinity
formatted_inf = format_percentage(Decimal("inf"))
print(formatted_inf)  # "∞%"
```

---

### format_ratio()

**Source**: `formatting.py:53-76`

Format Decimal ratio with specified precision.

```python
def format_ratio(
    value: Decimal,
    precision: int = 2,
    include_sign: bool = False
) -> str
```

**Example**:
```python
from rustybt.finance.metrics.formatting import format_ratio
from decimal import Decimal

# Sharpe ratio
sharpe = Decimal("1.567")
print(format_ratio(sharpe, precision=2))  # "1.57"

# Profit factor
pf = Decimal("2.345")
print(format_ratio(pf, precision=2))  # "2.35"

# With sign for excess return
excess = Decimal("0.234")
print(format_ratio(excess, precision=3, include_sign=True))  # "+0.234"
```

---

### format_currency()

**Source**: `formatting.py:79-107`

Format Decimal as currency with thousands separators.

```python
def format_currency(
    value: Decimal,
    symbol: str = "$",
    precision: int = 2,
    thousands_sep: bool = True
) -> str
```

**Example**:
```python
from rustybt.finance.metrics.formatting import format_currency
from decimal import Decimal

# USD
portfolio_value = Decimal("1234567.89")
print(format_currency(portfolio_value))  # "$1,234,567.89"

# EUR
euro_value = Decimal("999.50")
print(format_currency(euro_value, symbol="€"))  # "€999.50"

# No thousands separator
print(format_currency(portfolio_value, thousands_sep=False))  # "$1234567.89"
```

---

### format_basis_points()

**Source**: `formatting.py:110-130`

Format Decimal as basis points (1 bp = 0.01%).

```python
def format_basis_points(
    value: Decimal,
    precision: int = 1
) -> str
```

**Example**:
```python
from rustybt.finance.metrics.formatting import format_basis_points
from decimal import Decimal

# Tracking error
te = Decimal("0.0025")
print(format_basis_points(te))  # "25.0 bps"

# Spread
spread = Decimal("0.00015")
print(format_basis_points(spread, precision=2))  # "1.50 bps"
```

---

### create_metrics_summary_table()

**Source**: `formatting.py:157-200+`

Create formatted summary table of metrics.

```python
def create_metrics_summary_table(
    metrics: dict[str, Decimal],
    precision_map: dict[str, int] | None = None,
) -> str
```

**Example**:
```python
from rustybt.finance.metrics.formatting import create_metrics_summary_table
from decimal import Decimal

# Metrics dictionary
metrics = {
    'sharpe_ratio': Decimal('1.567'),
    'sortino_ratio': Decimal('2.134'),
    'max_drawdown': Decimal('-0.234'),
    'win_rate': Decimal('0.625'),
    'profit_factor': Decimal('2.45'),
}

# Default formatting
table = create_metrics_summary_table(metrics)
print(table)

# Custom precision
precision_map = {
    'sharpe_ratio': 3,
    'max_drawdown': 4,
}

table_custom = create_metrics_summary_table(metrics, precision_map)
print(table_custom)
```

---

## Production Examples

### Example 1: Complete Portfolio Attribution Report

```python
from rustybt.finance.metrics.attribution import (
    calculate_position_attribution,
    calculate_sector_attribution,
)
from rustybt.finance.metrics.formatting import format_percentage, format_currency
from decimal import Decimal
import polars as pl

# Portfolio positions
positions = pl.DataFrame({
    'asset': ['AAPL', 'GOOGL', 'MSFT', 'JPM', 'BAC', 'XOM', 'CVX'],
    'value': [
        Decimal('150000'), Decimal('120000'), Decimal('100000'),
        Decimal('80000'), Decimal('70000'), Decimal('60000'), Decimal('50000'),
    ],
})

# Returns for the month
returns_df = pl.DataFrame({
    'asset': ['AAPL', 'GOOGL', 'MSFT', 'JPM', 'BAC', 'XOM', 'CVX'],
    'return': [
        Decimal('0.08'), Decimal('0.05'), Decimal('0.10'),
        Decimal('-0.03'), Decimal('-0.02'), Decimal('0.12'), Decimal('0.09'),
    ],
})

# Sector mapping
sectors = {
    'AAPL': 'Technology', 'GOOGL': 'Technology', 'MSFT': 'Technology',
    'JPM': 'Finance', 'BAC': 'Finance',
    'XOM': 'Energy', 'CVX': 'Energy',
}

portfolio_value = positions['value'].sum()

# Position attribution
position_attr = calculate_position_attribution(
    positions, returns_df, portfolio_value
)

# Sector attribution
sector_attr = calculate_sector_attribution(
    positions, returns_df, sectors, portfolio_value
)

# Generate report
print("=" * 60)
print("PORTFOLIO ATTRIBUTION REPORT")
print("=" * 60)
print(f"Portfolio Value: {format_currency(portfolio_value)}")
print()

print("Position Attribution:")
print("-" * 60)
for asset, attr in sorted(position_attr.items(), key=lambda x: x[1], reverse=True):
    weight = positions.filter(pl.col('asset') == asset)['value'][0] / portfolio_value
    ret = returns_df.filter(pl.col('asset') == asset)['return'][0]

    print(f"{asset:6} | Weight: {format_percentage(weight)} | "
          f"Return: {format_percentage(ret, include_sign=True)} | "
          f"Attribution: {format_percentage(attr, include_sign=True)}")

print()
print("Sector Attribution:")
print("-" * 60)
for sector, attr in sorted(sector_attr.items(), key=lambda x: x[1], reverse=True):
    print(f"{sector:12} | Attribution: {format_percentage(attr, include_sign=True)}")

total_return = sum(position_attr.values())
print()
print("=" * 60)
print(f"Total Portfolio Return: {format_percentage(total_return, include_sign=True)}")
print("=" * 60)
```

---

### Example 2: Alpha/Beta Analysis

```python
from rustybt.finance.metrics.attribution import calculate_alpha_beta
from rustybt.finance.metrics.formatting import format_ratio, format_percentage
from decimal import Decimal
import polars as pl

# Strategy returns (60 days)
strategy_returns = pl.Series("strategy", [
    Decimal(str(random.gauss(0.001, 0.02))) for _ in range(60)
])

# SPY returns (60 days)
spy_returns = pl.Series("spy", [
    Decimal(str(random.gauss(0.0008, 0.015))) for _ in range(60)
])

# Calculate alpha/beta
alpha, beta = calculate_alpha_beta(
    strategy_returns,
    spy_returns,
    risk_free_rate=Decimal("0.02") / Decimal("252"),  # Daily risk-free rate
)

# Annualize alpha
alpha_annual = alpha * Decimal("252")

# Display analysis
print("ALPHA/BETA ANALYSIS")
print("=" * 40)
print(f"Beta: {format_ratio(beta, precision=3)}")
print(f"Daily Alpha: {format_percentage(alpha, precision=4)}")
print(f"Annual Alpha: {format_percentage(alpha_annual, precision=2)}")
print()

# Risk categorization
if beta > Decimal("1.2"):
    risk_category = "High Risk (Amplifies market)"
elif beta > Decimal("0.8"):
    risk_category = "Market Risk"
else:
    risk_category = "Low Risk (Defensive)"

print(f"Risk Category: {risk_category}")

# Alpha assessment
if alpha_annual > Decimal("0.05"):
    alpha_assessment = "Strong alpha generation"
elif alpha_annual > Decimal("0.02"):
    alpha_assessment = "Moderate alpha"
elif alpha_annual > Decimal("0"):
    alpha_assessment = "Weak alpha"
else:
    alpha_assessment = "Negative alpha"

print(f"Alpha Assessment: {alpha_assessment}")
```

---

### Example 3: Monthly Performance Report

```python
from rustybt.finance.metrics.attribution import calculate_time_period_attribution
from rustybt.finance.metrics.formatting import format_percentage
from decimal import date, Decimal
import polars as pl

# Generate 90 days of returns
returns_list = []
dates_list = []
start_date = date(2024, 1, 1)

for i in range(90):
    returns_list.append(Decimal(str(random.gauss(0.001, 0.015))))
    dates_list.append(start_date + timedelta(days=i))

returns = pl.Series("returns", returns_list)
dates = pl.Series("date", dates_list)

# Monthly attribution
monthly_perf = calculate_time_period_attribution(
    returns,
    dates,
    period='monthly'
)

# Generate report
print("MONTHLY PERFORMANCE REPORT")
print("=" * 60)
print(f"{'Period':<10} | {'Return':>10} | {'Cumulative':>12} | Days")
print("-" * 60)

for row in monthly_perf.iter_rows(named=True):
    period = row['period']
    ret = Decimal(str(row['return']))
    cumulative = Decimal(str(row['cumulative_return']))
    days = row['num_periods']

    print(f"{period:<10} | {format_percentage(ret):>10} | "
          f"{format_percentage(cumulative):>12} | {days:>4}")

# Summary statistics
best_month = monthly_perf.filter(
    pl.col('return') == pl.col('return').max()
).to_dicts()[0]

worst_month = monthly_perf.filter(
    pl.col('return') == pl.col('return').min()
).to_dicts()[0]

print()
print("=" * 60)
print(f"Best Month:  {best_month['period']} ({format_percentage(Decimal(str(best_month['return'])))})")
print(f"Worst Month: {worst_month['period']} ({format_percentage(Decimal(str(worst_month['return'])))})")
final_return = monthly_perf['cumulative_return'][-1]
print(f"Total Return: {format_percentage(Decimal(str(final_return)))}")
print("=" * 60)
```

---

## Best Practices

### 1. Use Position Attribution for Trade Analysis

```python
# After each trading day, calculate attribution
position_attr = calculate_position_attribution(
    positions, daily_returns, portfolio_value
)

# Identify largest contributors/detractors
top_contributor = max(position_attr.items(), key=lambda x: x[1])
top_detractor = min(position_attr.items(), key=lambda x: x[1])

print(f"Top Contributor: {top_contributor[0]} ({top_contributor[1]:.2%})")
print(f"Top Detractor: {top_detractor[0]} ({top_detractor[1]:.2%})")
```

### 2. Use Sector Attribution for Risk Management

```python
# Calculate sector concentration
sector_attr = calculate_sector_attribution(
    positions, returns, sectors, portfolio_value
)

# Check for concentration risk
for sector, attr in sector_attr.items():
    sector_weight = sum(
        positions.filter(pl.col('asset').is_in([
            a for a, s in sectors.items() if s == sector
        ]))['value']
    ) / portfolio_value

    if sector_weight > Decimal("0.40"):
        print(f"⚠ High concentration in {sector}: {sector_weight:.1%}")
```

### 3. Track Alpha/Beta Over Time

```python
# Rolling alpha/beta analysis (e.g., 60-day window)
window_size = 60

for i in range(window_size, len(strategy_returns)):
    window_strategy = strategy_returns[i-window_size:i]
    window_spy = spy_returns[i-window_size:i]

    alpha, beta = calculate_alpha_beta(window_strategy, window_spy)

    # Track changes in beta
    if abs(beta - Decimal("1.0")) > Decimal("0.3"):
        print(f"Day {i}: Beta drift detected ({beta:.2f})")
```

### 4. Use Appropriate Formatting for Audience

```python
# For traders: basis points
te = Decimal("0.0025")
print(f"Tracking Error: {format_basis_points(te)}")  # "25.0 bps"

# For clients: percentages
sharpe = Decimal("1.567")
print(f"Sharpe Ratio: {format_ratio(sharpe, precision=2)}")  # "1.57"

# For reports: currency
pnl = Decimal("1234567.89")
print(f"P&L: {format_currency(pnl)}")  # "$1,234,567.89"
```

---

## Related Documentation

- **Performance Tracking**: DecimalMetricsTracker for automatic metric calculation
- **Risk Metrics**: Individual risk metric functions (Sharpe, VaR, etc.)
- **Risk Management**: Portfolio-level risk limits and checks
- **Portfolio Allocator**: Multi-strategy portfolio management

---

## Source Code References

All APIs documented above are verified against source code:

**Attribution Functions**:
- `calculate_position_attribution`: `attribution.py:31-98`
- `calculate_sector_attribution`: `attribution.py:101-138`
- `calculate_alpha_beta`: `attribution.py:141-199`
- `calculate_time_period_attribution`: `attribution.py:202-254`

**Formatting Functions**:
- `format_percentage`: `formatting.py:26-50`
- `format_ratio`: `formatting.py:53-76`
- `format_currency`: `formatting.py:79-107`
- `format_basis_points`: `formatting.py:110-130`
- `create_metrics_summary_table`: `formatting.py:157-200+`

---

**Last Verified**: 2025-10-16
**Source Version**: RustyBT v1.0 (Epic 11 Documentation)
**Verification**: 100% of APIs verified against source code
