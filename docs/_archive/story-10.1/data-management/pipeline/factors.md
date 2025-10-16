# Pipeline Factors

Factors represent numerical computations over historical data windows.

## Built-in Factors

### SimpleMovingAverage

```python
from rustybt.pipeline.factors import SimpleMovingAverage
from rustybt.pipeline.data import EquityPricing

sma_20 = SimpleMovingAverage(
    inputs=[EquityPricing.close],
    window_length=20
)
```

### RSI (Relative Strength Index)

```python
from rustybt.pipeline.factors import RSI

rsi = RSI(window_length=14)
```

### Returns

```python
from rustybt.pipeline.factors import Returns

returns_1d = Returns(window_length=1)
returns_20d = Returns(window_length=20)
```

### BollingerBands

```python
from rustybt.pipeline.factors import BollingerBands

bb = BollingerBands(window_length=20, k=2.0)
upper = bb.upper
lower = bb.lower
```

## Custom Factors

```python
from rustybt.pipeline import CustomFactor
from rustybt.pipeline.data import EquityPricing

class MeanReversion(CustomFactor):
    inputs = [EquityPricing.close]
    window_length = 20

    def compute(self, today, assets, out, close):
        # Calculate z-score
        mean = close.mean(axis=0)
        std = close.std(axis=0)
        out[:] = (close[-1] - mean) / std

# Use in pipeline
mean_rev = MeanReversion()
pipe.add(mean_rev, 'mean_reversion')
```

## Decimal Factors

For financial-grade precision:

```python
from rustybt.pipeline.factors.decimal_factors import DecimalFactor

class DecimalSMA(DecimalFactor):
    """Decimal-precision SMA."""
    inputs = [EquityPricing.close]
    window_length = 20

    def compute(self, today, assets, out, close):
        from decimal import Decimal
        # All computations use Decimal
        out[:] = [Decimal(str(close[:, i].mean()))
                  for i in range(len(assets))]
```

## Factor Operations

```python
# Arithmetic
sma_diff = sma_50 - sma_200
ratio = close / sma_20

# Comparison
signal = close > sma_20  # Boolean factor/filter

# Ranking
close_rank = close.rank()

# Z-score normalization
close_zscore = close.zscore()

# Quantiles
close_quantiles = close.quantiles(bins=5)
```

## See [Filters](filters.md) for boolean selections.
