# Trade Analysis

Trade-level diagnostics and execution quality analysis for backtests. Analyze individual trades to identify weaknesses and improve strategy execution.

## Overview

**Purpose**: Analyze trade execution quality beyond aggregate metrics:
- **MAE/MFE**: Maximum Adverse/Favorable Excursion (stop-loss/take-profit optimization)
- **Trade Statistics**: Win rate, profit factor, expectancy, average win/loss
- **Holding Periods**: Time in trade distribution and analysis
- **Cost Impact**: Commission and slippage effects on profitability
- **Trade Clustering**: Concentration risk by time and asset
- **Entry/Exit Quality**: Timing analysis vs. optimal prices

**When to Use**:
- ✅ To optimize stop-loss and take-profit levels
- ✅ To diagnose execution problems (slippage, poor timing)
- ✅ To validate that profits aren't from few lucky trades
- ✅ To understand trade distribution and patterns

---

## Quick Start

### Basic Trade Statistics

```python
from rustybt.analytics.trade_analysis import TradeAnalyzer

# Load backtest result
backtest_result = run_backtest(strategy, data)

# Initialize trade analyzer
analyzer = TradeAnalyzer(backtest_result)

# Analyze all trades
analysis = analyzer.analyze_trades()

# Summary statistics
stats = analysis['summary_stats']
print(f"Total trades: {stats['total_trades']}")
print(f"Win rate: {stats['win_rate']:.2%}")
print(f"Profit factor: {stats['profit_factor']:.2f}")
print(f"Average win: ${stats['avg_win']:.2f}")
print(f"Average loss: ${stats['avg_loss']:.2f}")
print(f"Largest win: ${stats['largest_win']:.2f}")
print(f"Largest loss: ${stats['largest_loss']:.2f}")
print(f"Expectancy: ${stats['expectancy']:.2f}")

# Output:
# Total trades: 245
# Win rate: 58.37%
# Profit factor: 1.85
# Average win: $425.30
# Average loss: $248.15
# Largest win: $2,150.00
# Largest loss: $890.50
# Expectancy: $95.42 (average profit per trade)
```

**Interpretation**:
- **Win rate > 50%**: More winners than losers (good)
- **Profit factor > 1.5**: Solid profitability
- **Expectancy > 0**: Positive expected profit per trade
- **Avg win > avg loss**: Good reward/risk ratio

---

### MAE/MFE Analysis

```python
# MAE/MFE analysis (Maximum Adverse/Favorable Excursion)
mae_mfe = analysis['mae_mfe']

print("=== MAE Analysis ===")
print(f"Average MAE: {mae_mfe['avg_mae']:.2%}")
print(f"Median MAE: {mae_mfe['median_mae']:.2%}")
print(f"95th percentile MAE: {mae_mfe['mae_95th']:.2%}")

print("\n=== MFE Analysis ===")
print(f"Average MFE: {mae_mfe['avg_mfe']:.2%}")
print(f"Median MFE: {mae_mfe['median_mfe']:.2%}")
print(f"95th percentile MFE: {mae_mfe['mfe_95th']:.2%}")

# Visualize MAE vs. PnL
analyzer.plot_mae_vs_pnl(output_path='mae_scatter.png')

# Visualize MFE vs. PnL
analyzer.plot_mfe_vs_pnl(output_path='mfe_scatter.png')

# Interpretation:
# - Average MAE = 2.5%: Trades typically move 2.5% against you
# - Average MFE = 5.8%: Trades typically move 5.8% in your favor
# - If MFE >> MAE: Room to widen profit targets
# - If MAE is large on winners: Stop-loss too wide (giving back profits)
```

**MAE Interpretation** (Maximum Adverse Excursion):
- **MAE on losing trades**: How far trades moved against you before hitting stop-loss
- **MAE on winning trades**: Temporary drawdown before profit
- **High MAE on winners**: Stop-loss placement saved trades that recovered

**MFE Interpretation** (Maximum Favorable Excursion):
- **MFE on winning trades**: Peak profit during trade
- **MFE on losers**: How much profit was available before reversal
- **High MFE on losers**: Exit too late (gave back profits)

---

### Cost Impact Analysis

```python
# Cost analysis
costs = analysis['costs']

print("=== Cost Impact ===")
print(f"Total commission: ${costs['total_commission']:.2f}")
print(f"Total slippage: ${costs['total_slippage']:.2f}")
print(f"Total costs: ${costs['total_costs']:.2f}")
print(f"Commission % of gross PnL: {costs['commission_pct_of_pnl']:.2%}")
print(f"Slippage % of gross PnL: {costs['slippage_pct_of_pnl']:.2%}")
print(f"Total costs % of gross PnL: {costs['total_costs_pct']:.2%}")

# Interpretation:
# - Total costs = $12,450
# - Costs = 18% of gross PnL
# - High cost % indicates strategy may not be profitable after realistic costs
```

---

### Holding Period Analysis

```python
# Holding period distribution
holding = analysis['holding_period']

print("=== Holding Period Analysis ===")
print(f"Average holding: {holding['avg_holding_hours']:.1f} hours")
print(f"Median holding: {holding['median_holding_hours']:.1f} hours")
print(f"Min holding: {holding['min_holding_hours']:.1f} hours")
print(f"Max holding: {holding['max_holding_hours']:.1f} hours")

# Visualize holding period distribution
analyzer.plot_holding_period_distribution(output_path='holding_dist.png')

# Interpretation:
# - Average = 18.5 hours (intraday to next day)
# - Median = 12.2 hours (shorter than average, some outliers)
# - Max = 240 hours (10 days) - identify these long-held positions
```

---

## API Reference

### TradeAnalyzer

```python
from rustybt.analytics.trade_analysis import TradeAnalyzer

class TradeAnalyzer:
    """Analyze trade execution quality and patterns."""

    def __init__(self, backtest_result: Any):
        """Initialize trade analyzer.

        Args:
            backtest_result: Backtest result object containing:
                - transactions: List of transaction objects with:
                  * timestamp: datetime
                  * asset: Asset
                  * amount: Decimal (position size, positive=long, negative=short)
                  * price: Decimal (execution price)
                  * commission: Decimal
                  * slippage: Decimal
                - price_data: Price history DataFrame for all traded assets
                - portfolio_history: Optional portfolio value history

        Raises:
            ValueError: If backtest_result missing required attributes
            InsufficientTradeDataError: If no completed trades found

        Example:
            >>> result = run_backtest(strategy, data)
            >>> analyzer = TradeAnalyzer(result)
        """
```

---

### analyze_trades()

```python
def analyze_trades(self) -> dict[str, Any]:
    """Perform comprehensive trade analysis.

    Returns:
        Dictionary containing:
        {
            'summary_stats': {
                'total_trades': int,                # Number of completed trades
                'winning_trades': int,
                'losing_trades': int,
                'win_rate': Decimal,               # % of profitable trades
                'profit_factor': Decimal,          # Gross profit / gross loss
                'avg_win': Decimal,                # Average winning trade $
                'avg_loss': Decimal,               # Average losing trade $
                'largest_win': Decimal,
                'largest_loss': Decimal,
                'expectancy': Decimal,             # Expected profit per trade
                'total_pnl': Decimal,
                'gross_profit': Decimal,
                'gross_loss': Decimal
            },

            'mae_mfe': {
                'avg_mae': Decimal,                # Average MAE as % of entry
                'median_mae': Decimal,
                'mae_95th': Decimal,               # 95th percentile MAE
                'avg_mfe': Decimal,                # Average MFE as % of entry
                'median_mfe': Decimal,
                'mfe_95th': Decimal,
                'mae_on_winners': Decimal,         # MAE for profitable trades
                'mae_on_losers': Decimal,
                'mfe_on_winners': Decimal,
                'mfe_on_losers': Decimal
            },

            'holding_period': {
                'avg_holding_hours': float,
                'median_holding_hours': float,
                'min_holding_hours': float,
                'max_holding_hours': float,
                'std_holding_hours': float,
                'holding_distribution': dict      # Histogram bins
            },

            'costs': {
                'total_commission': Decimal,
                'total_slippage': Decimal,
                'total_costs': Decimal,
                'commission_pct_of_pnl': Decimal,  # Commission as % of gross PnL
                'slippage_pct_of_pnl': Decimal,
                'total_costs_pct': Decimal
            },

            'trade_clustering': {
                'trades_by_asset': dict,           # Asset -> trade count
                'trades_by_month': dict,           # Month -> trade count
                'trades_by_hour': dict,            # Hour -> trade count
                'max_concurrent_trades': int
            }
        }

    Example:
        >>> analysis = analyzer.analyze_trades()
        >>> print(f"Win rate: {analysis['summary_stats']['win_rate']:.2%}")
        >>> print(f"Expectancy: ${analysis['summary_stats']['expectancy']:.2f}")
    """
```

---

### MAE and MFE

**MAE** (Maximum Adverse Excursion):
- Maximum unrealized loss during trade (worst drawdown)
- Measured as % of entry price
- Used to optimize stop-loss placement

**MFE** (Maximum Favorable Excursion):
- Maximum unrealized profit during trade (peak profit)
- Measured as % of entry price
- Used to optimize take-profit placement

**Formulas**:
```python
# For long trades
MAE = max(0, (entry_price - min_price_during_trade) / entry_price)
MFE = max(0, (max_price_during_trade - entry_price) / entry_price)

# For short trades
MAE = max(0, (max_price_during_trade - entry_price) / entry_price)
MFE = max(0, (entry_price - min_price_during_trade) / entry_price)
```

---

## Complete Examples

### Comprehensive Trade Analysis

```python
from rustybt.analytics.trade_analysis import TradeAnalyzer
import matplotlib.pyplot as plt

# Run backtest
result = run_backtest(strategy, data)

# Analyze trades
analyzer = TradeAnalyzer(result)
analysis = analyzer.analyze_trades()

# 1. Summary Statistics
print("=== Trade Summary ===")
stats = analysis['summary_stats']
for key, value in stats.items():
    if isinstance(value, (int, float)):
        if 'rate' in key or 'factor' in key:
            print(f"{key}: {value:.2%}" if value < 10 else f"{key}: {value:.2f}")
        elif 'pnl' in key or 'profit' in key or 'loss' in key or 'win' in key or 'expectancy' in key:
            print(f"{key}: ${value:,.2f}")
        else:
            print(f"{key}: {value}")

# 2. Win/Loss Analysis
print("\n=== Win/Loss Analysis ===")
win_rate = stats['win_rate']
profit_factor = stats['profit_factor']

if win_rate > 0.55 and profit_factor > 1.5:
    print("✅ Excellent win rate and profit factor")
elif win_rate > 0.50 and profit_factor > 1.2:
    print("✅ Good win rate and profit factor")
else:
    print("⚠️  Win rate or profit factor needs improvement")

# 3. MAE/MFE Analysis
print("\n=== MAE/MFE Analysis ===")
mae_mfe = analysis['mae_mfe']

print(f"Average MAE: {mae_mfe['avg_mae']:.2%}")
print(f"Average MFE: {mae_mfe['avg_mfe']:.2%}")
print(f"MAE on winners: {mae_mfe['mae_on_winners']:.2%}")
print(f"MFE on losers: {mae_mfe['mfe_on_losers']:.2%}")

# Recommendations based on MAE/MFE
if mae_mfe['mae_on_winners'] > 0.05:
    print("\n💡 High MAE on winners - consider tighter stop-loss to lock in profits")

if mae_mfe['mfe_on_losers'] > 0.03:
    print("💡 High MFE on losers - consider tighter take-profit to capture gains before reversal")

# 4. Cost Impact
print("\n=== Cost Impact ===")
costs = analysis['costs']
print(f"Total costs: ${costs['total_costs']:,.2f}")
print(f"Costs as % of gross PnL: {costs['total_costs_pct']:.2%}")

if costs['total_costs_pct'] > 0.20:
    print("⚠️  High transaction costs (> 20% of gross PnL)")
    print("   Consider reducing trade frequency or increasing position size")

# 5. Holding Period
print("\n=== Holding Period ===")
holding = analysis['holding_period']
print(f"Average: {holding['avg_holding_hours']:.1f} hours")
print(f"Median: {holding['median_holding_hours']:.1f} hours")

# 6. Trade Clustering
print("\n=== Trade Clustering ===")
clustering = analysis['trade_clustering']

print("Top 5 most traded assets:")
top_assets = sorted(clustering['trades_by_asset'].items(), key=lambda x: x[1], reverse=True)[:5]
for asset, count in top_assets:
    pct = count / stats['total_trades'] * 100
    print(f"  {asset}: {count} trades ({pct:.1f}%)")

print(f"\nMax concurrent trades: {clustering['max_concurrent_trades']}")

# 7. Visualizations
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# MAE scatter
analyzer.plot_mae_vs_pnl(ax=axes[0, 0])
axes[0, 0].set_title('MAE vs. PnL')

# MFE scatter
analyzer.plot_mfe_vs_pnl(ax=axes[0, 1])
axes[0, 1].set_title('MFE vs. PnL')

# Holding period distribution
analyzer.plot_holding_period_distribution(ax=axes[1, 0])
axes[1, 0].set_title('Holding Period Distribution')

# Trade timeline
analyzer.plot_trade_timeline(ax=axes[1, 1])
axes[1, 1].set_title('Trade Timeline')

plt.tight_layout()
plt.savefig('trade_analysis.png', dpi=150)
print("\n📊 Visualizations saved to 'trade_analysis.png'")
```

---

### Stop-Loss Optimization Using MAE

```python
# Analyze MAE to find optimal stop-loss
analysis = analyzer.analyze_trades()
mae_data = analysis['mae_mfe']

# Get all trades with MAE/MFE data
trades = analyzer.trades

# Separate winners and losers
winners = [t for t in trades if t.pnl > 0]
losers = [t for t in trades if t.pnl <= 0]

# Analyze MAE distribution on winners
mae_winners = [float(t.mae) for t in winners]
mae_percentiles = [50, 75, 90, 95, 99]

print("=== MAE Distribution on Winning Trades ===")
import numpy as np
for pct in mae_percentiles:
    mae_pct = np.percentile(mae_winners, pct)
    print(f"{pct}th percentile MAE: {mae_pct:.2%}")

# Recommendation
mae_95 = np.percentile(mae_winners, 95)
print(f"\n💡 Recommended stop-loss: {mae_95:.2%}")
print(f"   Rationale: 95% of winning trades stayed within {mae_95:.2%} drawdown")
print(f"   This would preserve most winners while cutting losers early")

# Backtest with different stop-loss levels
stop_loss_levels = [0.02, 0.03, 0.04, 0.05]  # 2%, 3%, 4%, 5%
for sl in stop_loss_levels:
    # Count trades that would be stopped out
    stopped_winners = sum(1 for t in winners if t.mae > sl)
    preserved_winners = len(winners) - stopped_winners

    print(f"\nStop-loss = {sl:.2%}:")
    print(f"  Would preserve {preserved_winners}/{len(winners)} winners ({preserved_winners/len(winners)*100:.1f}%)")
    print(f"  Would stop out {stopped_winners} potential winners")
```

---

### Take-Profit Optimization Using MFE

```python
# Analyze MFE to find optimal take-profit
trades = analyzer.trades
losers = [t for t in trades if t.pnl <= 0]

# MFE on losing trades shows profit we gave back
mfe_losers = [float(t.mfe) for t in losers]

print("=== MFE Distribution on Losing Trades ===")
for pct in [50, 75, 90]:
    mfe_pct = np.percentile(mfe_losers, pct)
    print(f"{pct}th percentile MFE: {mfe_pct:.2%}")

# Recommendation
mfe_75 = np.percentile(mfe_losers, 75)
print(f"\n💡 Recommended take-profit: {mfe_75:.2%}")
print(f"   Rationale: 75% of losing trades had at least {mfe_75:.2%} profit available")
print(f"   Taking profit at this level would convert many losers to small winners")

# Calculate impact
potential_saves = sum(1 for t in losers if t.mfe > mfe_75)
print(f"   Would save {potential_saves}/{len(losers)} losing trades ({potential_saves/len(losers)*100:.1f}%)")
```

---

## Interpretation Guide

### Win Rate

**Win Rate = 58%**

Meaning: 58% of trades are profitable

**Ranges**:
- **< 40%**: Poor (needs improvement) ⚠️
- **40-50%**: Below average (acceptable if high reward/risk)
- **50-60%**: Good ✅
- **60-70%**: Excellent ✅✅
- **> 70%**: Exceptional (verify not overfitted)

**Note**: Win rate alone is NOT sufficient
```python
# High win rate, low profit factor = BAD
win_rate = 0.80  # 80% winners
avg_win = $100
avg_loss = $500  # Rare but large losses
profit_factor = 0.67  # Unprofitable!

# Low win rate, high profit factor = GOOD
win_rate = 0.40  # 40% winners
avg_win = $500
avg_loss = $100
profit_factor = 3.33  # Profitable!
```

---

### Profit Factor

**Profit Factor = Gross Profit / Gross Loss**

**Ranges**:
- **< 1.0**: Unprofitable ❌
- **1.0-1.5**: Marginally profitable (after costs may be unprofitable) ⚠️
- **1.5-2.0**: Good profitability ✅
- **2.0-3.0**: Excellent profitability ✅✅
- **> 3.0**: Exceptional (verify not overfitted)

**Example**:
```python
gross_profit = $50,000
gross_loss = $27,000
profit_factor = 50000 / 27000 = 1.85  # Good

# After costs
commission = $5,000
net_profit = 50000 - 27000 - 5000 = $18,000  # Still profitable
```

---

### Expectancy

**Expectancy = Average Profit Per Trade**

```python
expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

# Example:
win_rate = 0.55
avg_win = $400
avg_loss = $250
expectancy = (0.55 * 400) - (0.45 * 250) = $220 - $112.50 = $107.50
```

**Interpretation**:
- **Expectancy > 0**: Profitable strategy ✅
- **Expectancy < 0**: Unprofitable strategy ❌
- **Higher expectancy**: More profit per trade (better)

**Use Case**: Position sizing
```python
# Kelly Criterion for position sizing
win_rate = 0.55
avg_win_to_loss = 400 / 250 = 1.6
kelly_fraction = win_rate - (1 - win_rate) / avg_win_to_loss
kelly_fraction = 0.55 - 0.45 / 1.6 = 0.27  # Risk 27% of capital (aggressive!)

# Conservative: Use 25-50% of Kelly
position_size = kelly_fraction * 0.5 = 13.5% of capital
```

---

## Best Practices

### ✅ DO

1. **Analyze MAE/MFE** to optimize stops and targets
   ```python
   analysis = analyzer.analyze_trades()
   mae_95 = analysis['mae_mfe']['mae_95th']
   # Set stop-loss at 95th percentile MAE of winners
   ```

2. **Check cost impact** on profitability
   ```python
   if costs['total_costs_pct'] > 0.15:
       # Costs too high, reduce trade frequency
   ```

3. **Examine trade distribution** for concentration risk
   ```python
   clustering = analysis['trade_clustering']
   # Ensure not too concentrated in one asset or time period
   ```

4. **Validate expectancy is positive**
   ```python
   if stats['expectancy'] <= 0:
       print("⚠️  Negative expectancy - strategy unprofitable")
   ```

---

### ❌ DON'T

1. **Don't rely on win rate alone**
   ```python
   # BAD: Only check win rate
   if win_rate > 0.60:
       print("Good strategy")

   # GOOD: Check win rate AND profit factor
   if win_rate > 0.55 and profit_factor > 1.5:
       print("Good strategy")
   ```

2. **Don't ignore MAE/MFE**
   ```python
   # BAD: Arbitrary stop-loss
   stop_loss = 0.05  # 5% (why?)

   # GOOD: Data-driven stop-loss
   mae_95 = np.percentile([t.mae for t in winners], 95)
   stop_loss = mae_95  # Based on actual trade data
   ```

3. **Don't forget transaction costs**
   ```python
   # BAD: Ignore costs
   net_profit = gross_profit - gross_loss

   # GOOD: Include costs
   net_profit = gross_profit - gross_loss - commission - slippage
   ```

---

## Visualization

### MAE vs. PnL Scatter

```python
fig = analyzer.plot_mae_vs_pnl(
    figsize=(10, 6),
    output_path='mae_scatter.png'
)
```

**Interpretation**:
- **Vertical clustering at MAE value**: Consistent stop-loss
- **Wide MAE distribution on winners**: No systematic stop-loss

### MFE vs. PnL Scatter

```python
fig = analyzer.plot_mfe_vs_pnl(
    figsize=(10, 6),
    output_path='mfe_scatter.png'
)
```

**Interpretation**:
- **High MFE on losers**: Gave back profits (tighten take-profit)
- **Low MFE on winners**: Captured most available profit ✅

### Trade Timeline

```python
fig = analyzer.plot_trade_timeline(
    figsize=(12, 6),
    output_path='trade_timeline.png'
)
```

---

## See Also

- [Analytics Suite Overview](../README.md)
- [Risk Analytics](../risk/README.md)
- [Performance Attribution](../attribution/README.md)
- [Optimization Framework](../../optimization/README.md)

---

## References

### Academic Sources

1. **MAE/MFE Methodology**:
   - Tomasini, E., & Jaekle, U. (2009). *Trading Systems: A New Approach to System Development and Portfolio Optimisation*. Harriman House.
   - Sweeney, J. (1996). "Maximum Adverse Excursion: Analyzing Price Fluctuations for Trading Management". *Technical Analysis of Stocks & Commodities*.

2. **Trade Analysis**:
   - Tharp, V. K. (2008). *Trade Your Way to Financial Freedom*. McGraw-Hill.
   - Pardo, R. (2008). *The Evaluation and Optimization of Trading Strategies*. Wiley.

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
