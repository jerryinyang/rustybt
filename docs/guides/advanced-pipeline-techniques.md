# Advanced Pipeline Techniques

**Last Updated:** 2025-10-31

This guide covers advanced Pipeline techniques for building sophisticated quantitative trading strategies.

## Table of Contents

1. [Combining Factors](#combining-factors)
2. [Combining Filters](#combining-filters)
3. [Creating Custom Factors](#creating-custom-factors)
4. [Creating Custom Filters](#creating-custom-filters)
5. [Advanced Patterns](#advanced-patterns)
6. [Best Practices](#best-practices)

---

## Combining Factors

One of Pipeline's most powerful features is the ability to combine factors to create sophisticated signals.

### Arithmetic Operations

Factors support standard arithmetic operations:

```python
from rustybt.pipeline.factors import Returns, AnnualizedVolatility

# Simple arithmetic
returns_1m = Returns(window_length=21)
returns_3m = Returns(window_length=63)

# Addition
combined_momentum = returns_1m + returns_3m

# Weighted average
momentum_score = (0.3 * returns_1m) + (0.7 * returns_3m)

# Division (e.g., risk-adjusted returns)
volatility = AnnualizedVolatility(window_length=252)
risk_adjusted = returns_1m / volatility

# Multiple operations
composite = (returns_1m + returns_3m) / 2
```

### Ranking and Normalization

Rank or normalize factors before combining (common for multi-factor models):

```python
# Rank factors before combining
returns_1m_rank = returns_1m.rank()
returns_3m_rank = returns_3m.rank()
vol_rank = volatility.rank()

# Equal-weight composite (lower volatility rank is better)
quality_momentum = (returns_1m_rank + returns_3m_rank - vol_rank) / 3

# Z-score normalization
returns_1m_z = returns_1m.zscore()
returns_3m_z = returns_3m.zscore()
normalized_composite = (returns_1m_z + returns_3m_z) / 2
```

### Working with Multi-Output Factors

Some factors return multiple outputs (e.g., Bollinger Bands, Ichimoku):

```python
from rustybt.pipeline.factors import BollingerBands, IchimokuKinkoHyo

# Access individual outputs
bb = BollingerBands(window_length=20, k=2.0)
upper = bb.upper
middle = bb.middle
lower = bb.lower

# Combine outputs
bb_width = (upper - lower) / middle  # Bollinger Band width as percentage
bb_position = (USEquityPricing.close.latest - lower) / (upper - lower)

# Ichimoku components
ichimoku = IchimokuKinkoHyo(window_length=52)
cloud_thickness = ichimoku.senkou_span_a - ichimoku.senkou_span_b

# Use in filters
price = USEquityPricing.close.latest
above_cloud = price > ichimoku.senkou_span_a
below_cloud = price < ichimoku.senkou_span_b
```

---

## Combining Filters

Filters can be combined using logical operations to create complex selection criteria.

### Logical Operations

```python
from rustybt.pipeline.factors import Returns, AverageDollarVolume
from rustybt.pipeline.data import USEquityPricing

# Individual filters
liquid = AverageDollarVolume(window_length=20).top(500)
price_filter = USEquityPricing.close.latest > 5
momentum_filter = Returns(window_length=21) > 0.05

# AND (&) - Must meet ALL conditions
conservative_universe = liquid & price_filter & momentum_filter

# OR (|) - Must meet ANY condition
returns_1m = Returns(window_length=21)
returns_3m = Returns(window_length=63)
high_momentum = (returns_1m > 0.10) | (returns_3m > 0.20)

# NOT (~) - Exclude matching assets
not_penny_stocks = ~(USEquityPricing.close.latest < 5)

# Complex combinations with parentheses
advanced_filter = (
    liquid &
    not_penny_stocks &
    (high_momentum | (volatility < 0.20))
)
```

### Top/Bottom with Masking

Use the `mask` parameter to restrict `top()` or `bottom()` to a subset:

```python
# Top N after applying filter
liquid_filter = AverageDollarVolume(window_length=20).top(1000)
returns = Returns(window_length=21)

# Top 50 momentum stocks from liquid universe only
top_momentum = returns.top(50, mask=liquid_filter)

# Bottom 50 volatility from high momentum stocks
high_momentum_filter = returns.top(200)
low_vol = volatility.bottom(50, mask=high_momentum_filter)
```

---

## Creating Custom Factors

When built-in factors don't meet your needs, create custom factors.

### Basic Custom Factor

```python
from rustybt.pipeline import CustomFactor
from rustybt.pipeline.data import USEquityPricing
import numpy as np

class MeanReversion(CustomFactor):
    """Z-score of price vs N-day mean."""

    inputs = [USEquityPricing.close]
    window_length = 20

    def compute(self, today, assets, out, close):
        """Compute z-score.

        Parameters
        ----------
        today : pd.Timestamp
            Current date
        assets : np.ndarray
            Array of SIDs (asset identifiers)
        out : np.ndarray
            Output array to fill
        close : np.ndarray
            Close price array (window_length x num_assets)
        """
        # Calculate mean and std for each asset (axis=0 is time)
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

### Custom Factor with Parameters

```python
class CustomRSI(CustomFactor):
    """RSI with configurable overbought/oversold levels."""

    inputs = [USEquityPricing.close]
    window_length = 14
    params = {
        'overbought': 70,
        'oversold': 30,
    }

    def compute(self, today, assets, out, close, overbought, oversold):
        """Compute RSI and classify."""
        # Calculate price changes
        delta = np.diff(close, axis=0)

        # Separate gains and losses
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)

        # Average gains and losses
        avg_gain = gains.mean(axis=0)
        avg_loss = losses.mean(axis=0)

        # Calculate RS and RSI
        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))

        out[:] = rsi

# Usage with custom parameters
rsi = CustomRSI(overbought=80, oversold=20)
```

### Advanced Custom Factor

```python
class TrendStrength(CustomFactor):
    """Measure trend strength using linear regression R-squared."""

    inputs = [USEquityPricing.close]
    window_length = 50

    def compute(self, today, assets, out, close):
        from scipy import stats

        # For each asset
        for i in range(len(assets)):
            prices = close[:, i]

            # Skip if too many NaNs
            if np.isnan(prices).sum() > self.window_length * 0.2:
                out[i] = np.nan
                continue

            # Linear regression
            x = np.arange(len(prices))
            # Remove NaNs
            mask = ~np.isnan(prices)
            if mask.sum() < 2:
                out[i] = np.nan
                continue

            slope, intercept, r_value, p_value, std_err = stats.linregress(
                x[mask], prices[mask]
            )

            # R-squared indicates trend strength
            out[i] = r_value ** 2

# Use it
trend = TrendStrength()
strong_trend = trend > 0.7  # R² > 0.7
```

---

## Creating Custom Filters

Create custom filters for complex selection logic.

### Basic Custom Filter

```python
from rustybt.pipeline import CustomFilter

class VolatilityFilter(CustomFilter):
    """Select stocks with volatility in specified range."""

    inputs = [Returns(window_length=2)]
    window_length = 252
    params = ('min_vol', 'max_vol')

    def compute(self, today, assets, out, returns, min_vol, max_vol):
        """Filter by volatility range.

        Parameters
        ----------
        today : pd.Timestamp
        assets : np.ndarray of int (SIDs)
        out : np.ndarray[bool]
            Output array (True = include, False = exclude)
        returns : np.ndarray
            Daily returns array
        min_vol, max_vol : float
            Volatility range
        """
        volatility = np.std(returns, axis=0) * np.sqrt(252)
        out[:] = (volatility >= min_vol) & (volatility <= max_vol)

# Usage
moderate_vol = VolatilityFilter(min_vol=0.15, max_vol=0.35)
```

### Custom Filter with Asset Finder (Advanced)

For filtering based on asset metadata (names, types, etc.), use a factory pattern with closures:

```python
from rustybt.pipeline import CustomFilter
from rustybt.data.bundles.core import load

FIAT_CURRENCIES = {
    'USD', 'USDT', 'USDC', 'BUSD', 'DAI',
    'EUR', 'GBP', 'AUD', 'CAD', 'CHF',
    'HKD', 'JPY', 'NZD', 'SGD',
    'UAH', 'TRY', 'RUB', 'ZAR', 'NGN',
    'BRL', 'ARS', 'MXN', 'CLP',
    'CZK', 'DKK', 'NOK', 'SEK', 'PLN',
    'HUF', 'RON', 'PHP', 'IDR', 'THB',
    'VND', 'SAR', 'AED', 'INR', 'CNY',
    'KRW', 'KZT',
}

def make_fiat_filter(asset_finder):
    """Factory function to create a CustomFilter with access to asset_finder.

    This uses a closure to give the filter access to the asset finder
    without passing it through the constructor (CustomFilter doesn't support
    custom constructor parameters).

    Parameters
    ----------
    asset_finder : AssetFinder
        Asset finder instance from bundle

    Returns
    -------
    ExcludeFiatPairs
        Filter instance that excludes fiat pairs
    """
    class ExcludeFiatPairs(CustomFilter):
        """Exclude cryptocurrency pairs involving fiat currencies.

        This demonstrates accessing asset metadata in CustomFilter by using
        the asset finder (from closure) to map SIDs to Asset objects.
        """

        inputs = ()
        window_length = 1

        def compute(self, today, assets, out):
            """Filter based on asset names.

            Parameters
            ----------
            today : pd.Timestamp
            assets : np.ndarray of int
                Array of SIDs (security identifiers)
            out : np.ndarray[bool]
                Output array to fill
            """
            for i, sid in enumerate(assets):
                # Look up asset by SID using asset_finder from closure
                asset = asset_finder.retrieve_asset(sid)
                asset_name = asset.asset_name

                # Parse and check for fiat
                parts = asset_name.replace(':', '/').split('/')
                is_fiat = any(
                    part.upper().strip() in FIAT_CURRENCIES
                    for part in parts
                )

                out[i] = not is_fiat  # True = include, False = exclude

    return ExcludeFiatPairs()


def make_pipeline():
    """Example usage with asset finder."""
    from rustybt.pipeline import Pipeline
    from rustybt.pipeline.factors import AverageDollarVolume
    from rustybt.pipeline.domain import EquityCalendarDomain

    # Get asset finder from bundle
    bundle_data = load('binance-spot-1d')
    asset_finder = bundle_data.asset_finder

    # Create domain and filters
    CRYPTO = EquityCalendarDomain(country_code="US", calendar_name="24/7")
    avg_volume = AverageDollarVolume(window_length=5)
    exclude_fiat = make_fiat_filter(asset_finder)  # Use factory function

    # Combine: filter non-fiat FIRST, then take top 10
    # This guarantees exactly 10 non-fiat assets
    non_fiat_top_10 = avg_volume.top(10, mask=exclude_fiat)

    return Pipeline(
        columns={'avg_volume': avg_volume},
        screen=non_fiat_top_10,
        domain=CRYPTO,
    )
```

### Alternative: Post-Pipeline Filtering

For simple cases or when asset finder isn't needed, filter after pipeline output:

```python
def make_pipeline():
    """Get top 30, will filter to 10 non-fiat."""
    avg_volume = AverageDollarVolume(window_length=5)
    return Pipeline(
        columns={'avg_volume': avg_volume},
        screen=avg_volume.top(30),  # Oversample
        domain=CRYPTO,
    )

def before_trading_start(context, data):
    """Filter to top 10 non-fiat pairs."""
    pipeline_output = context.pipeline_output('universe')

    # Filter using custom logic
    def is_fiat_pair(symbol):
        parts = symbol.replace(':', '/').split('/')
        return any(p.upper() in FIAT_CURRENCIES for p in parts)

    # Filter and take top 10
    non_fiat = pipeline_output[
        ~pipeline_output.index.map(lambda a: is_fiat_pair(a.asset_name))
    ]
    top_10 = non_fiat.nlargest(10, 'avg_volume')
    context.universe = list(top_10.index)
```

**When to use each approach:**
- **CustomFilter with asset finder:** Guarantees exact count, more efficient, recommended for production
- **Post-pipeline filtering:** Simpler, good for prototyping, may not guarantee exact count

---

## Advanced Patterns

### Multi-Stage Filtering

Build complex universes through progressive filtering:

```python
# Stage 1: Broad universe
liquid = AverageDollarVolume(window_length=20).top(1000)
price_filter = USEquityPricing.close.latest > 5
stage1 = liquid & price_filter

# Stage 2: Momentum screen
returns = Returns(window_length=21)
momentum_filter = returns.top(200, mask=stage1)

# Stage 3: Quality screen
volatility = AnnualizedVolatility(window_length=252)
quality_filter = volatility.bottom(100, mask=momentum_filter)

# Final universe
final_universe = quality_filter
```

### Factor-Driven Filters

Create filters from factor values:

```python
# Define factors
returns_1m = Returns(window_length=21)
returns_3m = Returns(window_length=63)
volatility = AnnualizedVolatility(window_length=252)

# Multiple conditions
positive_momentum = returns_1m > 0
sustained_momentum = returns_3m > 0.10
low_risk = volatility < 0.30

# Combine into final filter
quality_growth = positive_momentum & sustained_momentum & low_risk

# Top N from filtered universe
top_quality = returns_1m.top(50, mask=quality_growth)
```

### Conditional Strategy Logic

Different universe logic based on market conditions:

```python
from rustybt.pipeline.factors import RSI, Returns

# RSI-based conditions
rsi = RSI(window_length=14)
oversold = rsi < 30
overbought = rsi > 70

# Different logic for different conditions
returns = Returns(window_length=21)

# Mean reversion for extreme RSI
mean_reversion_universe = oversold | overbought

# Momentum for neutral RSI
neutral_rsi = ~(oversold | overbought)
momentum_universe = neutral_rsi & (returns > 0.05)

# Combined strategy
either_strategy = mean_reversion_universe | momentum_universe
```

### Sector-Neutral Selection

Select top N assets per group (e.g., sector):

```python
from rustybt.pipeline.classifiers import Sector

# Define momentum and sector
momentum = Returns(window_length=63)
sector = Sector()

# Top 3 momentum stocks per sector
top_per_sector = momentum.top(3, groupby=sector)

pipeline = Pipeline(
    columns={
        'momentum': momentum,
        'sector': sector,
    },
    screen=top_per_sector,
)
```

---

## Best Practices

### 1. Use Parentheses for Clarity

Make complex combinations clear with parentheses:

```python
# Clear
universe = (liquid & price_filter) & (momentum | quality)

# Unclear - operator precedence may surprise you
universe = liquid & price_filter & momentum | quality
```

### 2. Name Intermediate Steps

Improve readability by naming intermediate computations:

```python
# Good - clear intent
liquid = AverageDollarVolume(window_length=20).top(1000)
price_ok = USEquityPricing.close.latest > 5
base_universe = liquid & price_ok

# Less clear - hard to understand
universe = AverageDollarVolume(window_length=20).top(1000) & (USEquityPricing.close.latest > 5)
```

### 3. Apply Broad Filters First

More efficient - reduces computation for subsequent factors:

```python
# Efficient: broad filter first
liquid = dollar_volume.top(1000)  # Quick
expensive_calc = custom_factor.top(50, mask=liquid)  # Only on 1000 assets

# Inefficient: expensive calc on all assets
expensive = custom_factor.top(50)  # Slow on all assets
liquid_and_expensive = expensive & liquid
```

### 4. Test Filters Separately

Debug incrementally by testing each filter:

```python
# Test each filter individually
pipe1 = Pipeline(columns={}, screen=filter1)
output1 = engine.run_pipeline(pipe1, start, end)
print(f"Filter1: {len(output1)} assets")

pipe2 = Pipeline(columns={}, screen=filter2)
output2 = engine.run_pipeline(pipe2, start, end)
print(f"Filter2: {len(output2)} assets")

# Then combine
pipe_combined = Pipeline(columns={}, screen=filter1 & filter2)
output_combined = engine.run_pipeline(pipe_combined, start, end)
print(f"Combined: {len(output_combined)} assets")
```

### 5. Document Factor Logic

Add clear docstrings to custom factors:

```python
class MyCustomFactor(CustomFactor):
    """Short description of what this factor measures.

    Detailed explanation:
    - What the factor measures
    - Why it's predictive
    - Expected range of values
    - Any academic paper references

    Parameters
    ----------
    inputs : list
        Description of required inputs
    window_length : int
        Description of window parameter

    Notes
    -----
    Any important implementation details or caveats.
    """
    pass
```

### 6. Handle Edge Cases

Protect against NaN, inf, and division by zero:

```python
def compute(self, today, assets, out, prices):
    # Check for sufficient data
    if np.isnan(prices).sum() > self.window_length * 0.5:
        out[:] = np.nan
        return

    # Protect against division by zero
    denominator = prices.std(axis=0)
    out[:] = prices.mean(axis=0) / (denominator + 1e-9)

    # Handle infinities
    out[~np.isfinite(out)] = np.nan
```

---

## Related Documentation

- [Pipeline API Reference](../api/computation/pipeline-api.md) - Complete API documentation
- [Pipeline Guide](./pipeline-api-guide.md) - Getting started with Pipeline
- [Pipeline Multi-Asset Guide](../user-guide/pipeline-multi-asset.md) - Using Pipeline with crypto, forex, etc.

---

**Last Updated:** 2025-10-31
