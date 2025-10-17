# Pipeline API Guide

**Last Updated**: 2024-10-11

## Overview

The Pipeline API is RustyBT's framework for factor-based trading strategies and quantitative research. It provides a declarative way to define computations over large universes of assets, compute factors, and screen/rank securities.

---

## Table of Contents

1. [What is Pipeline?](#what-is-pipeline)
2. [When to Use Pipeline](#when-to-use-pipeline)
3. [Core Concepts](#core-concepts)
4. [Built-in Factors](#built-in-factors)
5. [Custom Factors](#custom-factors)
6. [Filters and Screens](#filters-and-screens)
7. [Integration with TradingAlgorithm](#integration-with-tradingalgorithm)
8. [Performance Optimization](#performance-optimization)
9. [Best Practices](#best-practices)
10. [Example Strategies](#example-strategies)

---

## What is Pipeline?

Pipeline is a declarative framework for computing factors (quantitative signals) across many assets efficiently.

### Traditional Approach (Without Pipeline)

```python
def handle_data(context, data):
    # Compute momentum for each asset manually
    for asset in context.universe:
        prices = data.history(asset, 'close', 63, '1d')
        returns = prices.pct_change()
        momentum = (1 + returns).prod() - 1

        if momentum > 0.10:  # 10% threshold
            context.buy_candidates.append(asset)
```

**Problems**:
- Repetitive code
- Slow (loops over assets)
- Hard to maintain
- No caching

### Pipeline Approach

```python
def make_pipeline():
    returns = Returns(window_length=63)
    high_momentum = returns > 0.10

    return Pipeline(
        columns={'momentum': returns},
        screen=high_momentum
    )
```

**Benefits**:
- Declarative and concise
- Automatic caching and optimization
- Vectorized computations (fast)
- Easy to understand and maintain

---

## When to Use Pipeline

### ✅ **Use Pipeline For**:

1. **Factor-Based Strategies**
   - Momentum, value, quality, growth factors
   - Multi-factor models
   - Factor research and backtesting

2. **Statistical Arbitrage**
   - Pair selection based on cointegration
   - Mean reversion indicators
   - Relative value strategies

3. **Large Universe Screening**
   - Screening 1000+ stocks
   - Ranking by multiple factors
   - Sector-neutral selections

4. **Quantitative Research**
   - Testing new factors
   - Factor correlation analysis
   - Performance attribution

### ❌ **Don't Use Pipeline For**:

1. **Simple Technical Indicators**
   - Basic SMA crossovers
   - Single-asset strategies
   - Use regular `data.history()` instead

2. **High-Frequency Trading**
   - Intraday tick-level strategies
   - Order book analysis
   - Use WebSocket streaming instead

3. **Fixed Universe**
   - Trading 2-3 specific symbols
   - No screening/ranking needed
   - Pipeline adds unnecessary complexity

---

## Core Concepts

### 1. Factors

**Factors** are numeric computations over asset data.

```python
from rustybt.pipeline.factors import SimpleMovingAverage, Returns

# Built-in factors
sma_50 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=50)
returns_1m = Returns(window_length=21)

# Factor algebra
momentum = (returns_1m + returns_3m) / 2  # Combined factor
```

### 2. Filters

**Filters** are boolean computations that screen assets.

```python
from rustybt.pipeline.filters import Filter

# Comparison filters
high_price = USEquityPricing.close > 50
high_volume = USEquityPricing.volume > 1000000

# Combining filters
liquid_and_expensive = high_price & high_volume
```

### 3. Classifiers

**Classifiers** are categorical computations (e.g., sector, industry).

```python
from rustybt.pipeline.classifiers import Classifier

# Sector classifier
sector = Sector()

# Use in groupby operations
top_per_sector = momentum.top(5, groupby=sector)
```

### 4. Pipeline

**Pipeline** ties factors, filters, and classifiers together.

```python
from rustybt.pipeline import Pipeline

pipe = Pipeline(
    columns={
        'momentum': momentum,
        'sma_50': sma_50,
    },
    screen=liquid_and_expensive
)
```

---

## Built-in Factors

### Technical Indicators

```python
from rustybt.pipeline.factors import (
    SimpleMovingAverage,
    ExponentialWeightedMovingAverage,
    RSI,
    BollingerBands,
    VWAP
)

# Simple moving average
sma = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=50)

# Exponential weighted moving average
ewma = ExponentialWeightedMovingAverage(
    inputs=[USEquityPricing.close],
    window_length=50,
    decay_rate=0.94
)

# RSI
rsi = RSI(inputs=[USEquityPricing.close], window_length=14)

# Bollinger Bands
bb = BollingerBands(
    inputs=[USEquityPricing.close],
    window_length=20,
    k=2.0  # Standard deviations
)
```

### Statistical Factors

```python
from rustybt.pipeline.factors import AnnualizedVolatility, SimpleBeta
from rustybt.pipeline.factors.statistical import RollingPearsonOfReturns

# Volatility
volatility = AnnualizedVolatility(
    window_length=252  # Annual volatility
)

# Beta (vs market)
beta = SimpleBeta(
    target=returns,
    regression_length=252
)

# Correlation
correlation = RollingPearsonOfReturns(
    target=returns,
    returns=market_returns,
    window_length=63
)
```

### Returns Factors

```python
from rustybt.pipeline.factors import Returns

# 1-month momentum
returns_1m = Returns(window_length=21)

# 3-month momentum
returns_3m = Returns(window_length=63)

# 6-month momentum
returns_6m = Returns(window_length=126)

# Composite momentum
momentum_score = (returns_1m + returns_3m + returns_6m) / 3
```

---

## Custom Factors

### Creating a Custom Factor

```python
from rustybt.pipeline import CustomFactor
from rustybt.pipeline.data import USEquityPricing

class MeanReversion(CustomFactor):
    """Z-score of price vs N-day mean."""

    inputs = [USEquityPricing.close]
    window_length = 20

    def compute(self, today, assets, out, close):
        """Compute z-score.

        Args:
            today: Current date
            assets: Asset universe
            out: Output array to fill
            close: Close price array (window_length x num_assets)
        """
        # Calculate mean and std for each asset
        mean = close.mean(axis=0)
        std = close.std(axis=0)

        # Calculate z-score
        current_price = close[-1]
        z_score = (current_price - mean) / (std + 1e-9)  # Avoid division by zero

        out[:] = -z_score  # Negative: oversold is positive signal

# Use in pipeline
mean_reversion = MeanReversion()
oversold = mean_reversion > 1.5  # Z-score > 1.5 standard deviations
```

### Advanced Custom Factor

```python
class TrendStrength(CustomFactor):
    """Measure trend strength using linear regression R-squared."""

    inputs = [USEquityPricing.close]
    window_length = 50

    def compute(self, today, assets, out, close):
        import numpy as np
        from scipy import stats

        # For each asset
        for i, asset in enumerate(assets):
            prices = close[:, i]

            # Linear regression
            x = np.arange(len(prices))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, prices)

            # R-squared indicates trend strength
            out[i] = r_value ** 2

# Use it
trend = TrendStrength()
strong_trend = trend > 0.7  # R² > 0.7
```

---

## Filters and Screens

### Basic Filters

```python
# Price filters
high_price = USEquityPricing.close > 20
low_price = USEquityPricing.close < 100

# Volume filters
liquid = USEquityPricing.volume > 1000000

# Combine filters
tradable = high_price & liquid
```

### Percentile Filters

```python
# Top 20% by dollar volume
dollar_volume = USEquityPricing.close * USEquityPricing.volume
top_20_pct = dollar_volume.percentile_between(80, 100)

# Bottom 10% by price
bottom_10_pct = USEquityPricing.close.percentile_between(0, 10)
```

### Ranking Filters

```python
momentum = Returns(window_length=63)

# Top 50 momentum stocks
top_50 = momentum.top(50)

# Bottom 50 (losers)
bottom_50 = momentum.bottom(50)

# Decile rankings
top_decile = momentum.percentile_between(90, 100)
```

### Factor-Based Screens

```python
# Multi-factor screen
momentum = Returns(window_length=63)
volatility = AnnualizedVolatility(window_length=252)

high_momentum = momentum.top(100)
low_volatility = volatility.bottom(100)

# Combine: high momentum + low volatility
screen = high_momentum & low_volatility
```

---

## Integration with TradingAlgorithm

### Attaching Pipeline

```python
from rustybt import TradingAlgorithm
from rustybt.pipeline import Pipeline

class MomentumStrategy(TradingAlgorithm):
    def initialize(self):
        # Create pipeline
        pipe = self.make_pipeline()

        # Attach to algorithm
        self.attach_pipeline(pipe, 'momentum_screen')

        # Schedule rebalance
        self.schedule_function(
            self.rebalance,
            date_rule=self.date_rules.week_start(),
            time_rule=self.time_rules.market_open()
        )

    def make_pipeline(self):
        momentum = Returns(window_length=63)
        top_momentum = momentum.top(50)

        return Pipeline(
            columns={'momentum': momentum},
            screen=top_momentum
        )

    def rebalance(self, context, data):
        # Get pipeline output
        pipeline_output = self.pipeline_output('momentum_screen')

        # pipeline_output is a DataFrame with assets as index
        target_assets = set(pipeline_output.index)

        # Close positions not in screen
        for asset in context.portfolio.positions:
            if asset not in target_assets:
                self.order_target_percent(asset, 0)

        # Equal weight new positions
        weight = 1.0 / len(target_assets) if target_assets else 0
        for asset in target_assets:
            self.order_target_percent(asset, weight)
```

## Running Pipeline Strategies

Pipeline strategies use class-based structure and **must be executed via CLI** (not Python API).

### Execution Method

Save your strategy class to a file (e.g., `momentum_strategy.py`) and run with CLI:

```bash
rustybt run -f momentum_strategy.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31
```

!!! important "Class-Based Strategies Require CLI"
    Pipeline strategies inherit from `TradingAlgorithm` and can **only** be run using the CLI (`rustybt run -f`). The Python API `run_algorithm()` function only supports function-based strategies with `initialize` and `handle_data` parameters.

### Multiple Pipelines

```python
def initialize(self):
    # Long pipeline (high momentum)
    long_pipe = self.make_long_pipeline()
    self.attach_pipeline(long_pipe, 'long')

    # Short pipeline (low momentum)
    short_pipe = self.make_short_pipeline()
    self.attach_pipeline(short_pipe, 'short')

def rebalance(self, context, data):
    # Get both outputs
    long_output = self.pipeline_output('long')
    short_output = self.pipeline_output('short')

    # Long/short portfolio
    for asset in long_output.index:
        self.order_target_percent(asset, 0.5 / len(long_output))

    for asset in short_output.index:
        self.order_target_percent(asset, -0.5 / len(short_output))
```

---

## Performance Optimization

### 1. Efficient Universe Selection

Filter universe early:

```python
# ❌ Bad: Compute factors for all stocks, then filter
momentum = Returns(window_length=63)
screen = momentum.top(50)

# ✅ Good: Filter universe first, then compute
liquid = (USEquityPricing.close * USEquityPricing.volume).top(1000)
momentum = Returns(window_length=63, mask=liquid)
screen = momentum.top(50)
```

### 2. Factor Reuse

Reuse factors across pipelines:

```python
# Define factors once
momentum = Returns(window_length=63)
volatility = AnnualizedVolatility(window_length=252)

# Use in multiple places
long_screen = momentum.top(50) & volatility.bottom(100)
short_screen = momentum.bottom(50) & volatility.bottom(100)
```

### 3. Window Length Optimization

Use minimum required window:

```python
# ❌ Bad: Unnecessarily long window
returns = Returns(window_length=500)  # Need 500 days of data

# ✅ Good: Use only what you need
returns = Returns(window_length=63)  # 3 months sufficient
```

---

## Best Practices

### 1. Start Simple

```python
# Start with single factor
momentum = Returns(window_length=63)
screen = momentum.top(50)

# Add complexity incrementally
# Then add: volatility filter, sector neutrality, etc.
```

### 2. Test Factors Independently

```python
# Test factor distribution
pipe = Pipeline(columns={'factor': my_factor})
output = pipe.run(start_date, end_date)

# Analyze
print(output['factor'].describe())
output['factor'].hist(bins=50)
```

### 3. Use Proper Masking

```python
# Always mask to tradable universe
tradable = (
    (USEquityPricing.close > 5) &
    (USEquityPricing.volume > 100000)
)

# Apply mask to all factors
momentum = Returns(window_length=63, mask=tradable)
```

### 4. Document Factor Logic

```python
class MyCustomFactor(CustomFactor):
    """Short description.

    Detailed explanation of:
    - What the factor measures
    - Why it's predictive
    - Expected range of values
    - Academic paper reference (if applicable)
    """
    pass
```

---

## Example Strategies

### 1. Pure Momentum

```python
def make_pipeline():
    momentum = Returns(window_length=126)
    top_momentum = momentum.top(50)

    return Pipeline(
        columns={'momentum': momentum},
        screen=top_momentum
    )
```

### 2. Low Volatility

```python
def make_pipeline():
    volatility = AnnualizedVolatility(
        window_length=252
    )
    low_vol = volatility.bottom(50)

    return Pipeline(
        columns={'volatility': volatility},
        screen=low_vol
    )
```

### 3. Quality + Momentum

```python
def make_pipeline():
    momentum = Returns(window_length=126)
    volatility = AnnualizedVolatility(
        window_length=252
    )

    # Quality = low volatility
    quality = volatility.bottom(200)

    # Momentum within quality stocks
    top_momentum = momentum.top(50, mask=quality)

    return Pipeline(
        columns={
            'momentum': momentum,
            'volatility': volatility,
        },
        screen=top_momentum
    )
```

### 4. Sector Neutral

```python
def make_pipeline():
    momentum = Returns(window_length=126)
    sector = Sector()  # Requires sector data

    # Top 3 momentum stocks per sector
    top_per_sector = momentum.top(3, groupby=sector)

    return Pipeline(
        columns={
            'momentum': momentum,
            'sector': sector,
        },
        screen=top_per_sector
    )
```

---

## Troubleshooting

### Common Issues

#### "Window starts before data"

**Cause**: Factor window longer than available data

**Solution**: Reduce window length or start backtest later

#### "No output from pipeline"

**Cause**: Screen too restrictive, no assets pass

**Solution**: Loosen filters or check data availability

#### "Factor values are NaN"

**Cause**: Insufficient data or division by zero

**Solution**: Add epsilon to denominators, check data quality

---

## Next Steps

- **Example**: <!-- Pipeline Tutorial (Coming soon) -->
- **API Reference**: Coming soon
- **Factor Library**: Explore built-in factors in `rustybt.pipeline.factors`
- **Research**: Use Pipeline for factor research and backtesting

---

**Last Updated**: 2024-10-11
