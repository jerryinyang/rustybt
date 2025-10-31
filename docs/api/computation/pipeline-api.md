# Zipline Pipeline API

The Zipline Pipeline API provides a declarative framework for defining cross-sectional computations across assets. It enables strategy logic to be expressed as composable Factors, Filters, and Classifiers.

> **Note**: This document covers the **Computation Pipeline** (strategy calculations). For data ingestion pipelines, see [Data Pipeline System](../data-management/pipeline/README.md).

## Overview

The Pipeline API separates **what to compute** (factor definitions) from **how to compute it** (execution engine). This enables:

- **Declarative strategy logic** - Express computations as factor graphs
- **Automatic optimization** - Engine optimizes execution plans
- **Backtesting integration** - Seamlessly integrates with TradingAlgorithm
- **Reusable components** - Build libraries of factors

### Key Concepts

| Concept | Purpose | Example |
|---------|---------|---------|
| **Factor** | Numerical computation | Moving average, RSI, returns |
| **Filter** | Boolean screening | Top 500 by volume, Price > $10 |
| **Classifier** | Categorical grouping | Sector, exchange, market cap tier |
| **Pipeline** | Collection of computations | Daily alpha signal generator |

## Architecture

### Execution Flow

```
Strategy Definition (Python)
       ↓
Factor Graph Construction
       ↓
Execution Plan Optimization
       ↓
Data Loading (via DataPortal)
       ↓
Computation (vectorized)
       ↓
Results DataFrame
```

### Component Hierarchy

```
Pipeline
├── Columns (named Factors/Filters)
├── Screen (optional Filter)
└── Domain (universe definition)

Factor (Numerical)
├── Built-in (SimpleMovingAverage, Returns)
├── Technical (RSI, Bollinger Bands)
├── Statistical (Zscore, Correlation)
└── Custom (user-defined)

Filter (Boolean)
├── Comparison (>, <, ==)
├── Logical (AND, OR, NOT)
└── Statistical (Top/Bottom N)
```

## Factors

Factors compute numerical values for each asset. They are the building blocks of quantitative strategies.

### Built-in Factors

#### Latest Price
```python
from rustybt.pipeline.factors import Latest
from rustybt.pipeline.data import USEquityPricing

# Get latest closing price
close_price = USEquityPricing.close.latest
```

#### Returns
```python
from rustybt.pipeline.factors import Returns

# 1-day returns
returns_1d = Returns(window_length=2)

# 20-day returns
returns_20d = Returns(window_length=21)
```

#### Simple Moving Average
```python
from rustybt.pipeline.factors import SimpleMovingAverage

# 50-day SMA
sma_50 = SimpleMovingAverage(
    inputs=[USEquityPricing.close],
    window_length=50
)

# 200-day SMA
sma_200 = SimpleMovingAverage(
    inputs=[USEquityPricing.close],
    window_length=200
)
```

### Technical Indicators

#### RSI (Relative Strength Index)
```python
from rustybt.pipeline.factors import RSI

# 14-period RSI
rsi = RSI(window_length=14)
```

#### Bollinger Bands
```python
from rustybt.pipeline.factors import BollingerBands

# 20-day Bollinger Bands
bb = BollingerBands(window_length=20)
bb_upper = bb.upper
bb_lower = bb.lower
bb_pct = bb.percent  # Position within bands (0-1)
```

#### VWAP (Volume-Weighted Average Price)
```python
from rustybt.pipeline.factors import VWAP

# 20-day VWAP
vwap_20 = VWAP(window_length=20)
```

#### Aroon
```python
from rustybt.pipeline.factors import Aroon

# 25-period Aroon indicator
aroon = Aroon(window_length=25)

# Access both up and down components
aroon_up = aroon.up
aroon_down = aroon.down

# Identify strong uptrends (Aroon Up > 70, Aroon Down < 30)
strong_uptrend = (aroon.up > 70) & (aroon.down < 30)
```

The Aroon indicator helps identify trend changes and strength. Values range from 0-100.

#### Fast Stochastic Oscillator
```python
from rustybt.pipeline.factors import FastStochasticOscillator

# 14-period Fast Stochastic (%K)
fast_stoch = FastStochasticOscillator(window_length=14)

# Identify oversold/overbought conditions
oversold = fast_stoch < 20
overbought = fast_stoch > 80
```

Fast Stochastic measures momentum. Values below 20 suggest oversold, above 80 suggest overbought.

#### Ichimoku Kinko Hyo (Ichimoku Cloud)
```python
from rustybt.pipeline.factors import IchimokuKinkoHyo

# Ichimoku with custom parameters
ichimoku = IchimokuKinkoHyo(
    window_length=52,  # Senkou Span B window
    tenkan_sen_length=9,
    kijun_sen_length=26,
    chikou_span_length=26
)

# Access components
tenkan_sen = ichimoku.tenkan_sen  # Conversion line
kijun_sen = ichimoku.kijun_sen  # Base line
senkou_span_a = ichimoku.senkou_span_a  # Leading Span A
senkou_span_b = ichimoku.senkou_span_b  # Leading Span B
chikou_span = ichimoku.chikou_span  # Lagging Span

# Bullish signal: price above cloud
price = USEquityPricing.close.latest
above_cloud = price > senkou_span_a
```

Ichimoku is a comprehensive trend-following indicator with multiple components.

#### MACD Signal
```python
from rustybt.pipeline.factors import MACDSignal, MovingAverageConvergenceDivergenceSignal

# Standard MACD parameters (12, 26, 9)
macd_signal = MACDSignal()

# Or use full name
macd = MovingAverageConvergenceDivergenceSignal()

# MACD crossover (bullish when MACD crosses above signal)
macd_value = macd  # MACD line
# Note: MACD outputs the signal line; MACD line calculation requires custom factor
```

#### Rate of Change Percentage
```python
from rustybt.pipeline.factors import RateOfChangePercentage

# 10-day rate of change
roc = RateOfChangePercentage(
    inputs=[USEquityPricing.close],
    window_length=10
)

# Momentum filter
strong_momentum = roc > 5  # > 5% change
```

ROC measures percentage price change over N periods.

#### True Range
```python
from rustybt.pipeline.factors import TrueRange

# True Range (2-day default)
tr = TrueRange()

# Average True Range (ATR) - use with moving average
from rustybt.pipeline.factors import SimpleMovingAverage
atr = SimpleMovingAverage(inputs=[tr], window_length=14)

# Volatility filter
high_volatility = atr > atr.mean(window_length=252)
```

True Range measures daily price range including gaps.

### Advanced Technical Factors

#### Exponential Weighted Moving Average (EWMA)
```python
from rustybt.pipeline.factors import EWMA, ExponentialWeightedMovingAverage

# 20-day EWMA with default decay
ewma_20 = EWMA(inputs=[USEquityPricing.close], window_length=20)

# Or use full name
ewma = ExponentialWeightedMovingAverage(
    inputs=[USEquityPricing.close],
    window_length=20
)

# Crossover strategy
ewma_short = EWMA(inputs=[USEquityPricing.close], window_length=12)
ewma_long = EWMA(inputs=[USEquityPricing.close], window_length=26)
bullish_cross = ewma_short > ewma_long
```

#### Exponential Weighted Moving Standard Deviation
```python
from rustybt.pipeline.factors import EWMSTD, ExponentialWeightedMovingStdDev

# 20-day EWMSTD
ewmstd = EWMSTD(inputs=[USEquityPricing.close], window_length=20)

# Volatility breakout
vol_breakout = USEquityPricing.close.latest > (
    EWMA(inputs=[USEquityPricing.close], window_length=20) + 2 * ewmstd
)
```

#### Linear Weighted Moving Average
```python
from rustybt.pipeline.factors import LinearWeightedMovingAverage

# 20-day LWMA (more weight on recent prices)
lwma = LinearWeightedMovingAverage(
    inputs=[USEquityPricing.close],
    window_length=20
)

# Trend filter
price = USEquityPricing.close.latest
uptrend = price > lwma
```

LWMA weights recent prices more heavily using linear weighting.

#### Max Drawdown
```python
from rustybt.pipeline.factors import MaxDrawdown

# 252-day (1 year) max drawdown
max_dd = MaxDrawdown(inputs=[USEquityPricing.close], window_length=252)

# Select low drawdown stocks
low_drawdown = max_dd.bottom(100)  # Bottom 100 by drawdown
```

MaxDrawdown measures maximum peak-to-trough decline over the window.

#### Daily Returns
```python
from rustybt.pipeline.factors import DailyReturns

# Daily returns (window_length=2 fixed)
daily_returns = DailyReturns()

# Multi-day returns use Returns factor
from rustybt.pipeline.factors import Returns
monthly_returns = Returns(window_length=21)
```

DailyReturns is a convenience factor equivalent to `Returns(window_length=2)`.

#### Percent Change
```python
from rustybt.pipeline.factors import PercentChange

# 10-day percent change on volume
volume_change = PercentChange(
    inputs=[USEquityPricing.volume],
    window_length=10
)

# Volume surge detection
volume_surge = volume_change > 50  # 50% increase
```

PercentChange works on any input, not just price.

#### Average Dollar Volume
```python
from rustybt.pipeline.factors import AverageDollarVolume

# 20-day average dollar volume
avg_dollar_vol = AverageDollarVolume(window_length=20)

# Liquidity filter (top 500 by dollar volume)
liquid_universe = avg_dollar_vol.top(500)
```

#### Weighted Average Value
```python
from rustybt.pipeline.factors import WeightedAverageValue

# Custom weighted average
weighted_avg = WeightedAverageValue(
    inputs=[USEquityPricing.close, USEquityPricing.volume],
    window_length=20
)
# This is what VWAP uses internally
```

WeightedAverageValue is the base for VWAP and similar calculations.

### Statistical Factors

#### Annualized Volatility
```python
from rustybt.pipeline.factors import AnnualizedVolatility

# 252-day (1 year) annualized volatility
annual_vol = AnnualizedVolatility(window_length=252)

# Low volatility filter
low_vol = annual_vol.bottom(100)
```

#### Rolling Sharpe Ratio
```python
from rustybt.pipeline.factors import RollingSharpeRatio

# 252-day rolling Sharpe ratio
sharpe = RollingSharpeRatio(window_length=252)

# Select high risk-adjusted return stocks
high_sharpe = sharpe.top(50)
```

RollingSharpeRatio measures risk-adjusted returns over the window.

#### Simple Beta
```python
from rustybt.pipeline.factors import SimpleBeta, Returns

# Calculate beta vs market (e.g., SPY)
returns = Returns(window_length=2)
beta = SimpleBeta(
    target=returns,
    regression_length=252
)

# Low beta filter
low_beta = beta < 0.7
```

SimpleBeta calculates asset beta relative to a target (typically market returns).

#### Rolling Pearson Correlation
```python
from rustybt.pipeline.factors import RollingPearson, RollingPearsonOfReturns

# Correlation between two factors
factor_a = Returns(window_length=21)
factor_b = Returns(window_length=63)

correlation = RollingPearson(
    base_factor=factor_a,
    target=factor_b,
    correlation_length=252
)

# Or use convenience method for returns correlation
returns_corr = RollingPearsonOfReturns(
    target=market_returns,
    returns_length=2,
    correlation_length=252
)

# Pairs trading: find negatively correlated assets
negatively_correlated = correlation < -0.5
```

#### Rolling Spearman Correlation
```python
from rustybt.pipeline.factors import RollingSpearman, RollingSpearmanOfReturns

# Rank correlation (non-parametric)
spearman_corr = RollingSpearman(
    base_factor=factor_a,
    target=factor_b,
    correlation_length=252
)

# Returns-specific version
returns_spearman = RollingSpearmanOfReturns(
    target=market_returns,
    returns_length=2,
    correlation_length=252
)
```

Spearman correlation is based on ranks, robust to outliers.

#### Rolling Linear Regression of Returns
```python
from rustybt.pipeline.factors import RollingLinearRegressionOfReturns

# Calculate alpha and beta via regression
regression = RollingLinearRegressionOfReturns(
    target=market_returns,
    returns_length=2,
    regression_length=252
)

# Access regression outputs
alpha = regression.alpha  # Intercept (excess return)
beta = regression.beta  # Slope (market sensitivity)

# Alpha-seeking strategy
high_alpha = alpha.top(50)
```

Performs rolling linear regression, provides alpha and beta outputs.

### Event-Based Factors

#### Business Days Since Previous Event
```python
from rustybt.pipeline.factors import BusinessDaysSincePreviousEvent
from rustybt.pipeline.data import EarningsCalendar

# Days since last earnings announcement
days_since_earnings = BusinessDaysSincePreviousEvent(
    inputs=[EarningsCalendar.announcement_date]
)

# Recently announced (within 5 days)
recent_earnings = days_since_earnings <= 5
```

#### Business Days Until Next Event
```python
from rustybt.pipeline.factors import BusinessDaysUntilNextEvent

# Days until next earnings
days_until_earnings = BusinessDaysUntilNextEvent(
    inputs=[EarningsCalendar.announcement_date]
)

# Upcoming earnings (within 10 days)
upcoming_earnings = days_until_earnings <= 10
```

### Advanced Factors

#### Least Correlated Pairs
```python
from rustybt.pipeline.factors import LeastCorrelatedPairs

# Find least correlated pairs for pair trading
least_corr = LeastCorrelatedPairs(window_length=252)

# Use in pair selection strategy
pairs_universe = least_corr.top(20)
```

#### Peer Count
```python
from rustybt.pipeline.factors import PeerCount
from rustybt.pipeline.classifiers import Sector

# Count peers in same sector
peer_count = PeerCount(inputs=[Sector()])

# Avoid illiquid sectors
sufficient_peers = peer_count >= 10
```

### Decimal-Aware Factors

RustyBT provides Decimal-precision factors for financial-grade calculations:

```python
from rustybt.pipeline.factors.decimal_factors import (
    DecimalLatestPrice,
    DecimalSimpleMovingAverage,
)

# Latest price (Decimal)
latest_price = DecimalLatestPrice()

# SMA with Decimal precision
sma_decimal = DecimalSimpleMovingAverage(window_length=20)
```

### Custom Factors

Create custom factors by subclassing `CustomFactor`:

```python
from rustybt.pipeline import CustomFactor
import numpy as np

class MeanReversionScore(CustomFactor):
    """Calculate mean reversion signal."""

    inputs = [USEquityPricing.close]
    window_length = 20

    def compute(self, today, assets, out, close):
        # Calculate z-score
        mean = np.mean(close, axis=0)
        std = np.std(close, axis=0)
        current = close[-1]
        out[:] = -(current - mean) / std  # Negative for mean reversion
```

Usage:
```python
mean_reversion = MeanReversionScore()
```

## Filters

Filters produce boolean values for screening assets.

### Comparison Filters

```python
# Price filters
cheap = USEquityPricing.close.latest < 50
expensive = USEquityPricing.close.latest > 100

# Volume filters
liquid = USEquityPricing.volume.latest > 1_000_000
illiquid = USEquityPricing.volume.latest < 100_000

# Factor filters
rsi = RSI(window_length=14)
oversold = rsi < 30
overbought = rsi > 70
```

### Logical Combinators

```python
# AND
tradeable = liquid & (USEquityPricing.close.latest > 5)

# OR
extreme = oversold | overbought

# NOT
not_penny = ~(USEquityPricing.close.latest < 5)
```

### Statistical Filters

#### Top/Bottom N
```python
# Top 100 by dollar volume
dollar_volume = USEquityPricing.close.latest * USEquityPricing.volume.latest
top_100 = dollar_volume.top(100)

# Bottom 50 by market cap
bottom_50_mcap = market_cap.bottom(50)
```

#### Percentile Filters
```python
# Top 10% by returns
returns_1d = Returns(window_length=2)
top_decile = returns_1d.percentile_between(90, 100)

# Middle 50% by volatility
volatility = Returns(window_length=2).stddev(window_length=252)
middle_half = volatility.percentile_between(25, 75)
```

### Advanced Filters

#### Smoothing Filters

Smoothing filters check if a condition holds over multiple periods.

##### All
```python
from rustybt.pipeline.filters import All

# Price above SMA for all of the last 5 days
price_above_sma = USEquityPricing.close.latest > sma_20
sustained_uptrend = All(inputs=[price_above_sma], window_length=5)

# Use case: confirm trend persistence
confirmed_breakout = price_above_resistance & sustained_uptrend
```

`All` returns True only if the input filter is True for ALL periods in the window.

##### Any
```python
from rustybt.pipeline.filters import Any

# Price touched upper Bollinger Band in last 10 days
touched_upper_band = USEquityPricing.close.latest >= bb.upper
recent_overbought = Any(inputs=[touched_upper_band], window_length=10)

# Avoid recently overbought stocks
avoid_overbought = ~recent_overbought
```

`Any` returns True if the input filter is True for ANY period in the window.

##### AtLeastN
```python
from rustybt.pipeline.filters import AtLeastN

# Volume above average for at least 3 of last 5 days
high_volume = USEquityPricing.volume.latest > volume_avg
volume_interest = AtLeastN(inputs=[high_volume], window_length=5, N=3)

# Require sustained volume, not just one spike
confirmed_breakout = price_breakout & volume_interest
```

`AtLeastN` returns True if the input filter is True for at least N periods.

#### Data Quality Filters

##### AllPresent
```python
from rustybt.pipeline.filters import AllPresent

# Ensure all data columns are present (no missing data)
all_data_present = AllPresent()

# Use as base filter to avoid NaN issues
pipeline = Pipeline(
    columns={'momentum': momentum_factor},
    screen=all_data_present & momentum_factor.top(50)
)
```

`AllPresent` filters out assets with missing data in any column.

##### NotNullFilter / NullFilter
```python
from rustybt.pipeline.filters import NotNullFilter, NullFilter

# Filter out assets with null values in specific column
has_earnings_data = NotNullFilter(inputs=[EarningsCalendar.eps])

# Or select only assets with null values
missing_earnings = NullFilter(inputs=[EarningsCalendar.eps])
```

#### Selection Filters

##### SingleAsset
```python
from rustybt.pipeline.filters import SingleAsset
from rustybt.pipeline import Pipeline

# Create filter for single asset
aapl = asset_finder.lookup_symbol('AAPL', as_of_date=None)
aapl_only = SingleAsset(asset=aapl)

# Pipeline that computes only for AAPL
aapl_pipeline = Pipeline(
    columns={'close': USEquityPricing.close.latest},
    screen=aapl_only
)
```

`SingleAsset` selects exactly one asset by Asset object.

##### StaticAssets / StaticSids
```python
from rustybt.pipeline.filters import StaticAssets, StaticSids

# Filter to specific list of assets
assets = [asset_finder.lookup_symbol(s, as_of_date=None)
          for s in ['AAPL', 'MSFT', 'GOOGL']]
tech_only = StaticAssets(assets=assets)

# Or by SIDs
sids = [1, 2, 3]
specific_sids = StaticSids(sids=sids)

# Pipeline for specific universe
custom_universe_pipeline = Pipeline(
    columns={'momentum': momentum_factor},
    screen=tech_only
)
```

`StaticAssets` and `StaticSids` filter to a specific predefined set.

#### Advanced Filters

##### PercentileFilter
```python
from rustybt.pipeline.filters import PercentileFilter

# Top 10% by returns
returns = Returns(window_length=21)
top_decile = PercentileFilter(
    inputs=[returns],
    min_percentile=90,
    max_percentile=100
)

# Middle 50% by volatility
volatility = AnnualizedVolatility(window_length=252)
middle_vol = PercentileFilter(
    inputs=[volatility],
    min_percentile=25,
    max_percentile=75
)
```

`PercentileFilter` selects assets within specified percentile range.

##### MaximumFilter
```python
from rustybt.pipeline.filters import MaximumFilter

# Select maximum value across multiple filters/factors
filter_a = momentum.top(100)
filter_b = volatility.bottom(100)

# Assets in EITHER filter
either_filter = MaximumFilter(inputs=[filter_a, filter_b])
```

`MaximumFilter` applies logical OR across input filters.

##### ArrayPredicate
```python
from rustybt.pipeline.filters import ArrayPredicate
import numpy as np

# Custom array-based predicate
def custom_predicate(array):
    # array shape: (num_assets,)
    return array > np.median(array)

custom_filter = ArrayPredicate(
    inputs=[momentum_factor],
    predicate=custom_predicate
)
```

`ArrayPredicate` applies a custom function to create filters.

##### NumExprFilter
```python
from rustybt.pipeline.filters import NumExprFilter

# Complex filter using NumExpr for performance
# Combine multiple factors efficiently
momentum_filter = NumExprFilter(
    inputs=[returns_1m, returns_3m, volatility],
    expr="(returns_1m > 0.05) & (returns_3m > 0.10) & (volatility < 0.30)"
)
```

`NumExprFilter` evaluates complex expressions efficiently using NumExpr.

### Custom Filters

```python
from rustybt.pipeline import CustomFilter

class VolatilityFilter(CustomFilter):
    """Select stocks with volatility in specified range."""

    inputs = [Returns(window_length=2)]
    window_length = 252

    def __init__(self, min_vol, max_vol):
        self.min_vol = min_vol
        self.max_vol = max_vol

    def compute(self, today, assets, out, returns):
        volatility = np.std(returns, axis=0) * np.sqrt(252)
        out[:] = (volatility >= self.min_vol) & (volatility <= self.max_vol)
```

## Advanced Techniques

For advanced Pipeline usage including combining factors/filters and creating custom factors/filters, see:

**[Advanced Pipeline Techniques Guide](../../guides/advanced-pipeline-techniques.md)**

This comprehensive guide covers:
- Combining factors (arithmetic, ranking, normalization)
- Combining filters (logical operations, masking)
- Creating custom factors
- Creating custom filters (including asset metadata filtering)
- Advanced patterns (multi-stage filtering, conditional logic)
- Best practices

### Quick Examples

#### Combine Factors

```python
# Arithmetic operations
returns_1m = Returns(window_length=21)
returns_3m = Returns(window_length=63)
momentum_score = (0.3 * returns_1m) + (0.7 * returns_3m)

# Risk-adjusted returns
volatility = AnnualizedVolatility(window_length=252)
sharpe_ratio = returns_1m / volatility
```

#### Combine Filters

```python
# Logical operations
liquid = AverageDollarVolume(window_length=20).top(500)
price_filter = USEquityPricing.close.latest > 5
momentum = Returns(window_length=21) > 0.05

# AND, OR, NOT
universe = liquid & price_filter & momentum
high_momentum = (returns_1m > 0.10) | (returns_3m > 0.20)
not_penny_stocks = ~(USEquityPricing.close.latest < 5)
```

**For complete examples and advanced patterns, see [Advanced Pipeline Techniques](../../guides/advanced-pipeline-techniques.md).**

## Pipeline Construction

### Basic Pipeline

```python
from rustybt.pipeline import Pipeline

# Define computations
close = USEquityPricing.close.latest
volume = USEquityPricing.volume.latest
sma_20 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=20)
sma_50 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=50)

# Create pipeline
pipeline = Pipeline(
    columns={
        'close': close,
        'volume': volume,
        'sma_20': sma_20,
        'sma_50': sma_50,
    }
)
```

### Adding a Screen

```python
# Define screen
universe = (
    (USEquityPricing.close.latest > 5) &
    (USEquityPricing.volume.latest > 1_000_000)
)

# Create pipeline with screen
pipeline = Pipeline(
    columns={
        'close': close,
        'sma_20': sma_20,
    },
    screen=universe
)
```

### Integration with TradingAlgorithm

```python
from rustybt.algorithm import TradingAlgorithm

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Define pipeline
        pipe = Pipeline(
            columns={
                'sentiment': sentiment_score,
                'returns_20d': Returns(window_length=21),
            },
            screen=liquid_universe
        )

        # Attach pipeline
        self.attach_pipeline(pipe, 'my_pipeline')

    def before_trading_start(self, context, data):
        # Get pipeline output
        output = self.pipeline_output('my_pipeline')

        # Use results
        top_sentiment = output.nlargest(10, 'sentiment')
        context.longs = top_sentiment.index
```

## Expressions and Operators

Factors and Filters support mathematical and logical operations:

### Arithmetic Operations

```python
close = USEquityPricing.close.latest
volume = USEquityPricing.volume.latest

# Addition
total_price = close + 10

# Subtraction
price_delta = close - sma_20

# Multiplication
dollar_volume = close * volume

# Division
price_ratio = close / sma_50

# Power
price_squared = close ** 2
```

### Comparison Operations

```python
# Greater than
above_sma = close > sma_20

# Less than
below_sma = close < sma_20

# Equal / Not equal
at_target = close == 100
not_at_target = close != 100

# Greater/Less than or equal
above_or_at = close >= sma_20
below_or_at = close <= sma_20
```

### Window Methods

```python
# Rolling mean
returns = Returns(window_length=2)
avg_returns = returns.mean(window_length=20)

# Rolling standard deviation
volatility = returns.stddev(window_length=252)

# Rolling max/min
high_20d = USEquityPricing.high.max(window_length=20)
low_20d = USEquityPricing.low.min(window_length=20)

# Rolling sum
volume_20d = USEquityPricing.volume.sum(window_length=20)
```

### Rank and Percentile

```python
# Rank (1 = lowest)
volume_rank = USEquityPricing.volume.latest.rank()

# Percentile rank (0-100)
volume_pctile = USEquityPricing.volume.latest.percentile_rank()

# Demean (subtract cross-sectional mean)
demeaned_returns = returns.demean()

# Z-score (normalize to mean=0, std=1)
normalized_returns = returns.zscore()
```

## Common Patterns

### Pattern 1: Mean Reversion Strategy

```python
from rustybt.pipeline import Pipeline
from rustybt.pipeline.factors import Returns, AverageDollarVolume
from rustybt.pipeline.data import USEquityPricing

# Define liquid universe
dollar_volume = AverageDollarVolume(window_length=20)
liquid_universe = dollar_volume.top(1000)

# Calculate z-score of returns
returns = Returns(window_length=2)
returns_zscore = returns.zscore(window_length=252)

# Select extreme values
oversold = returns_zscore < -2
overbought = returns_zscore > 2

# Create pipeline
pipeline = Pipeline(
    columns={
        'returns_zscore': returns_zscore,
        'signal': -returns_zscore,  # Negative for mean reversion
        'close': USEquityPricing.close.latest,
    },
    screen=liquid_universe & (oversold | overbought)
)
```

### Pattern 2: Momentum Strategy

```python
# Multi-period momentum
returns_1m = Returns(window_length=21)
returns_3m = Returns(window_length=63)
returns_6m = Returns(window_length=126)

# Combined momentum score
momentum = (
    returns_1m.rank() +
    returns_3m.rank() +
    returns_6m.rank()
)

# Screen for winners
winners = momentum.top(50)

pipeline = Pipeline(
    columns={
        'momentum': momentum,
        'returns_1m': returns_1m,
    },
    screen=winners
)
```

### Pattern 3: Technical Breakout

```python
# Define technical indicators
sma_20 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=20)
sma_50 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=50)
close = USEquityPricing.close.latest

# Breakout conditions
golden_cross = sma_20 > sma_50
above_sma = close > sma_20
high_volume = USEquityPricing.volume.latest > USEquityPricing.volume.mean(20) * 1.5

# Combined signal
breakout = golden_cross & above_sma & high_volume

pipeline = Pipeline(
    columns={
        'close': close,
        'sma_20': sma_20,
        'sma_50': sma_50,
    },
    screen=breakout
)
```

### Pattern 4: Statistical Arbitrage

```python
from rustybt.pipeline.factors import (
    Returns,
    SimpleBeta,
    AverageDollarVolume,
    RollingLinearRegressionOfReturns
)

# Define universe
liquid_universe = AverageDollarVolume(window_length=20).top(500)

# Calculate returns
returns = Returns(window_length=2)

# Calculate beta via regression (requires market returns as target)
regression = RollingLinearRegressionOfReturns(
    target=returns,  # This would be market returns in practice
    returns_length=2,
    regression_length=252
)

# Access alpha and beta from regression
alpha = regression.alpha  # Excess return (intercept)
beta = regression.beta  # Market sensitivity (slope)

# Alpha-seeking strategy: high alpha, reasonable beta
high_alpha = alpha.zscore(window_length=20) > 1.5
reasonable_beta = (beta > 0.5) & (beta < 1.5)

pipeline = Pipeline(
    columns={
        'alpha': alpha,
        'beta': beta,
        'returns': returns,
    },
    screen=liquid_universe & high_alpha & reasonable_beta
)
```

### Pattern 5: Multi-Factor Quality + Momentum

```python
from rustybt.pipeline.factors import (
    Returns,
    AnnualizedVolatility,
    MaxDrawdown,
    RollingSharpeRatio,
    AverageDollarVolume,
    SimpleMovingAverage
)
from rustybt.pipeline.filters import All

# Universe selection
liquid = AverageDollarVolume(window_length=20).top(1000)
price_filter = USEquityPricing.close.latest > 5

# Momentum factors
returns_1m = Returns(window_length=21)
returns_3m = Returns(window_length=63)
returns_6m = Returns(window_length=126)

# Composite momentum (equal weight)
momentum_score = (
    returns_1m.rank() +
    returns_3m.rank() +
    returns_6m.rank()
) / 3

# Quality factors
volatility = AnnualizedVolatility(window_length=252)
max_dd = MaxDrawdown(inputs=[USEquityPricing.close], window_length=252)
sharpe = RollingSharpeRatio(window_length=252)

# Quality composite (lower volatility/drawdown = better quality)
quality_score = (
    volatility.rank() +  # Note: will invert later
    max_dd.rank() +
    (-sharpe.rank())  # Higher Sharpe is better
) / 3

# Invert quality score so lower is better
quality_score = -quality_score

# Trend confirmation
sma_50 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=50)
sma_200 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=200)
price = USEquityPricing.close.latest

# Sustained uptrend
uptrend_filter = sma_50 > sma_200
sustained_uptrend = All(inputs=[uptrend_filter], window_length=5)

# Combined strategy: top momentum + quality stocks in uptrends
top_momentum = momentum_score.top(200)
top_quality = quality_score.top(200)
final_screen = liquid & price_filter & top_momentum & top_quality & sustained_uptrend

pipeline = Pipeline(
    columns={
        'momentum': momentum_score,
        'quality': quality_score,
        'volatility': volatility,
        'sharpe': sharpe,
        'returns_1m': returns_1m,
    },
    screen=final_screen
)
```

### Pattern 6: Pairs Trading with Correlation

```python
from rustybt.pipeline.factors import RollingPearson, Returns
from rustybt.pipeline.filters import StaticAssets

# Select pairs manually (in practice, would be more systematic)
asset_a = asset_finder.lookup_symbol('AAPL', as_of_date=None)
asset_b = asset_finder.lookup_symbol('MSFT', as_of_date=None)
pair_universe = StaticAssets(assets=[asset_a, asset_b])

# Calculate returns
returns = Returns(window_length=2)

# Rolling correlation between pairs
# Note: This requires both assets in universe
correlation = RollingPearson(
    base_factor=returns,
    target=returns,  # In practice, specify target asset returns
    correlation_length=60
)

# Z-score of returns (for mean reversion)
returns_zscore = returns.zscore(window_length=60)

# Entry signals: high correlation + divergence
high_correlation = correlation > 0.7
diverged = returns_zscore.abs() > 1.5

pipeline = Pipeline(
    columns={
        'returns': returns,
        'returns_zscore': returns_zscore,
        'correlation': correlation,
        'close': USEquityPricing.close.latest,
    },
    screen=pair_universe & high_correlation & diverged
)
```

## Performance Optimization

### 1. Minimize Window Lengths

```python
# GOOD: Use only what you need
sma_short = SimpleMovingAverage(window_length=20)

# AVOID: Excessive window length
sma_long = SimpleMovingAverage(window_length=5000)  # Too long
```

### 2. Reuse Computations

```python
# GOOD: Compute once, use multiple times
returns = Returns(window_length=2)
returns_mean = returns.mean(window_length=20)
returns_std = returns.stddev(window_length=20)
returns_zscore = (returns - returns_mean) / returns_std

# AVOID: Redundant computations
returns_mean = Returns(window_length=2).mean(window_length=20)
returns_std = Returns(window_length=2).stddev(window_length=20)
```

### 3. Screen Early

```python
# GOOD: Screen reduces computation universe
expensive_universe = USEquityPricing.close.latest > 100

pipeline = Pipeline(
    columns={
        'complex_factor': expensive_computation,
    },
    screen=expensive_universe  # Computes only for screened assets
)

# AVOID: No screen = computes for all assets
pipeline = Pipeline(
    columns={
        'complex_factor': expensive_computation,
    }
)
```

### 4. Use Built-in Factors

```python
# GOOD: Use optimized built-in
sma = SimpleMovingAverage(window_length=20)

# AVOID: Custom implementation (slower)
class SlowSMA(CustomFactor):
    window_length = 20
    def compute(self, today, assets, out, close):
        out[:] = np.mean(close, axis=0)  # Slower than built-in
```

## Data Loaders

Pipeline loaders are responsible for loading data into the pipeline system. They bridge the gap between raw data storage (bar readers) and pipeline computations by providing AdjustedArrays that automatically handle corporate actions (splits, dividends).

### Loader Architecture

```
Pipeline Engine
      ↓
   Loaders
      ↓
┌─────────────┬──────────────┬────────────┐
│  Equity     │  DataFrame   │  Custom    │
│  Pricing    │  Loader      │  Loaders   │
│  Loader     │              │            │
└─────────────┴──────────────┴────────────┘
      ↓              ↓             ↓
Bar Readers    DataFrames    Custom Sources
```

### Built-in Loaders

#### EquityPricingLoader

Loads OHLCV data with support for price/volume adjustments and currency conversion.

```python
from rustybt.pipeline.loaders import EquityPricingLoader

# With FX support
loader = EquityPricingLoader(
    raw_price_reader=bar_reader,
    adjustments_reader=adjustments_reader,
    fx_reader=fx_reader
)

# Without FX (simpler)
loader = EquityPricingLoader.without_fx(
    raw_price_reader=bar_reader,
    adjustments_reader=adjustments_reader
)
```

**Features**:
- Automatic price/volume adjustments (splits, dividends)
- Currency conversion support
- Handles corporate actions
- Works with any BarReader

**Use Cases**:
- Standard equity backtesting
- Multi-currency portfolios
- Historical price analysis

---

#### DataFrameLoader

Loads custom data from pandas DataFrames.

```python
# Note: DataFrameLoader is planned for future releases
# For now, use EquityPricingLoader or custom loaders
```

**With Adjustments**:
```python
# Define adjustments (e.g., 2:1 split)
adjustments = pd.DataFrame({
    'sid': [1],
    'value': [2.0],
    'kind': [0],  # Multiply adjustment
    'start_date': [pd.NaT],
    'end_date': [pd.Timestamp('2024-01-15')],
    'apply_date': [pd.Timestamp('2024-01-15')]
})

loader = DataFrameLoader(
    column=MyDataset.custom_field,
    baseline=baseline,
    adjustments=adjustments
)
```

**Features**:
- In-memory data loading
- Support for adjustments
- Fast for small datasets
- Great for testing

**Use Cases**:
- Testing custom factors
- Alternative data integration
- Small datasets that fit in memory
- Rapid prototyping

---

### Custom Loaders

Create custom loaders for special data sources:

```python
from rustybt.pipeline.loaders.base import PipelineLoader
from rustybt.lib.adjusted_array import AdjustedArray

class APIDataLoader(PipelineLoader):
    """Load data from REST API."""

    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key

    def load_adjusted_array(self, domain, columns, dates, sids, mask):
        """
        Load data as AdjustedArrays.

        Parameters
        ----------
        domain : Domain
            Pipeline domain
        columns : list[BoundColumn]
            Columns to load
        dates : pd.DatetimeIndex
            Dates to load
        sids : pd.Int64Index
            Asset IDs to load
        mask : np.array[bool]
            Asset tradeable mask

        Returns
        -------
        dict[BoundColumn -> AdjustedArray]
        """
        # Fetch data from API
        raw_data = self._fetch_from_api(columns, dates, sids)

        # Convert to AdjustedArrays
        out = {}
        for column, data_array in raw_data.items():
            out[column] = AdjustedArray(
                data=data_array.astype(column.dtype),
                adjustments={},  # No adjustments
                missing_value=column.missing_value
            )

        return out

    def _fetch_from_api(self, columns, dates, sids):
        # API fetching logic
        import requests
        response = requests.get(
            f"{self.api_url}/data",
            params={
                'columns': [c.name for c in columns],
                'start': dates[0].isoformat(),
                'end': dates[-1].isoformat(),
                'sids': list(sids)
            },
            headers={'Authorization': f'Bearer {self.api_key}'}
        )
        # Convert response to arrays
        # ... implementation ...
        return data_dict

    @property
    def currency_aware(self):
        """Whether loader supports currency conversion."""
        return False  # This loader doesn't support FX
```

**Usage**:
```python
# Register custom loader in pipeline
from rustybt.pipeline import Pipeline
from rustybt.pipeline.engine import SimplePipelineEngine

api_loader = APIDataLoader(
    api_url="https://api.example.com",
    api_key="your-api-key"
)

# Create engine with custom loader
engine = SimplePipelineEngine(
    get_loader=lambda column: api_loader,
    asset_finder=finder,
    default_domain=domain
)

# Run pipeline
output = engine.run_pipeline(pipeline, start_date, end_date)
```

### Loader Best Practices

1. **Use Built-in Loaders When Possible**
   ```python
   # GOOD: Use EquityPricingLoader for OHLCV
   loader = EquityPricingLoader.without_fx(bar_reader, adjustments_reader)

   # AVOID: Custom loader for standard data
   # class CustomOHLCVLoader(PipelineLoader): ...
   ```

2. **Implement Currency Awareness Correctly**
   ```python
   @property
   def currency_aware(self):
       # Return True only if loader actually supports FX conversion
       return hasattr(self, 'fx_reader')
   ```

3. **Handle Missing Data**
   ```python
   def load_adjusted_array(self, domain, columns, dates, sids, mask):
       data = self._fetch_data(...)

       # Fill missing values appropriately
       data = np.where(np.isnan(data), column.missing_value, data)

       return {
           column: AdjustedArray(data, {}, column.missing_value)
       }
   ```

4. **Cache Expensive Operations**
   ```python
   class CachedLoader(PipelineLoader):
       def __init__(self, *args, **kwargs):
           super().__init__(*args, **kwargs)
           self._cache = {}

       def load_adjusted_array(self, domain, columns, dates, sids, mask):
           cache_key = (tuple(dates), tuple(sids))
           if cache_key in self._cache:
               return self._cache[cache_key]

           result = self._load_impl(domain, columns, dates, sids, mask)
           self._cache[cache_key] = result
           return result
   ```

5. **Test Loaders Independently**
   ```python
   import pytest
   # Note: Testing utilities are being refactored

   def test_custom_loader():
       """Test custom loader loads data correctly."""
       loader = APIDataLoader(api_url="...", api_key="...")

       dates = pd.date_range('2024-01-01', periods=10)
       sids = pd.Int64Index([1, 2, 3])

       result = loader.load_adjusted_array(
           domain=test_domain,
           columns=[MyDataset.field],
           dates=dates,
           sids=sids,
           mask=np.ones((len(dates), len(sids)), dtype=bool)
       )

       assert MyDataset.field in result
       assert result[MyDataset.field].data.shape == (len(dates), len(sids))
   ```

## Testing Strategies

### Unit Testing Factors

```python
import pytest
from rustybt.pipeline import Pipeline
# Note: Testing utilities are being refactored

def test_mean_reversion_factor():
    """Test custom mean reversion factor."""
    # Create test data
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    sids = [1, 2, 3]

    data = create_test_data(
        dates=dates,
        sids=sids,
        close_prices={1: 100, 2: 50, 3: 200}
    )

    # Create factor
    factor = MeanReversionScore()

    # Compute
    result = factor.compute(data)

    # Assert expected behavior
    assert len(result) == len(sids)
    assert result.notna().all()
```

### Backtesting Pipelines

```python
from rustybt.utils.run_algo import run_algorithm

# Test strategy with pipeline
result = run_algorithm(
    start=pd.Timestamp('2023-01-01'),
    end=pd.Timestamp('2023-12-31'),
    initialize=initialize,
    capital_base=100_000,
    data_frequency='daily',
    bundle='quandl'
)

# Analyze results
print(f"Total return: {result.portfolio_value[-1] / 100_000 - 1:.2%}")
print(f"Sharpe ratio: {result.sharpe:.2f}")
```

## Best Practices

1. **Name your columns clearly** - Use descriptive names
2. **Document factor logic** - Add docstrings to custom factors
3. **Test in isolation** - Unit test factors before integration
4. **Monitor performance** - Track pipeline execution time
5. **Version factor definitions** - Track changes to factor logic
6. **Validate assumptions** - Check factor distributions and correlations

## See Also

- [Data Pipeline System](../data-management/pipeline/README.md) - Data ingestion pipelines
- [PolarsDataPortal](../data-management/readers/polars-data-portal.md) - Modern Decimal-precision data access
- [DataPortal (Legacy)](../data-management/readers/data-portal.md) - Legacy pandas-based data access
- [Bar Readers](../data-management/readers/bar-reader.md) - Bar reader interface
- [Data Sources](../data-management/adapters/README.md) - Available data sources
