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

### Statistical Factors

#### Z-Score
```python
# Note: Advanced statistical factors like Zscore are planned for future releases
# For now, use custom factors with zscore calculations
```

#### Linear Regression
```python
# Note: LinearRegression factor is planned for future releases
# For now, use custom factors for regression analysis
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
# Calculate beta to market
spy_returns = Returns(window_length=2, inputs=[spy_close])
stock_returns = Returns(window_length=2)

# Regression to calculate beta
# Note: Advanced regression factors are planned for future releases
beta = RollingLinearRegression(
    dependent=stock_returns,
    independent=spy_returns,
    window_length=252
).beta

# Alpha (excess returns)
alpha = stock_returns - (beta * spy_returns)

# Select high alpha stocks
high_alpha = alpha.zscore(window_length=20) > 1.5

pipeline = Pipeline(
    columns={
        'alpha': alpha,
        'beta': beta,
    },
    screen=high_alpha
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
