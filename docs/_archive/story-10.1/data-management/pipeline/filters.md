# Pipeline Filters

Filters represent boolean selections for screening assets.

## Built-in Filters

### StaticAssets

Select specific assets:

```python
from rustybt.pipeline.filters import StaticAssets

universe = StaticAssets([aapl, msft, googl])
pipe.set_screen(universe)
```

### Top/Bottom

Select top/bottom N by factor:

```python
from rustybt.pipeline.factors import SimpleMovingAverage

sma_20 = SimpleMovingAverage(window_length=20)

# Top 10 by price
top_10 = sma_20.top(10)
pipe.set_screen(top_10)

# Bottom 10 by price
bottom_10 = sma_20.bottom(10)
```

### Percentile

Select by percentile:

```python
# Top quintile
top_20_pct = close.percentile_between(80, 100)

# Middle tercile
middle_third = close.percentile_between(33, 67)
```

## Filter Combinations

```python
# AND
filter1 = rsi < 30
filter2 = volume > 1000000
combined = filter1 & filter2

# OR
filter3 = (rsi < 30) | (rsi > 70)

# NOT
not_filter = ~filter1
```

## Custom Filters

```python
from rustybt.pipeline import CustomFilter
from rustybt.pipeline.data import EquityPricing

class HighVolume(CustomFilter):
    inputs = [EquityPricing.volume]
    window_length = 20

    def compute(self, today, assets, out, volume):
        avg_volume = volume.mean(axis=0)
        out[:] = avg_volume > 1_000_000

# Use in pipeline
high_vol = HighVolume()
pipe.set_screen(high_vol)
```

## See [Factors](factors.md) for numerical computations.
