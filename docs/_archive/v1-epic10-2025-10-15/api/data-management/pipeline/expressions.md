# Pipeline Expressions

Expressions combine pipeline terms using arithmetic, comparison, and logical operations.

## Arithmetic Operations

```python
from rustybt.pipeline.data import EquityPricing

# Addition
sum_price = EquityPricing.open + EquityPricing.close

# Subtraction
price_change = EquityPricing.close - EquityPricing.open

# Multiplication
typical_price = (EquityPricing.high + EquityPricing.low + EquityPricing.close) / 3

# Division
price_ratio = EquityPricing.close / EquityPricing.open
```

## Comparison Operations

```python
# Greater than
bullish = EquityPricing.close > EquityPricing.open

# Less than
bearish = EquityPricing.close < EquityPricing.open

# Between
mid_range = (EquityPricing.close > 50) & (EquityPricing.close < 100)
```

## Statistical Methods

```python
# Ranking
price_rank = EquityPricing.close.rank()

# Z-score
price_zscore = EquityPricing.close.zscore()

# Quantiles
price_quintiles = EquityPricing.close.quantiles(5)

# Winsorization
winsorized = EquityPricing.close.winsorize(
    min_percentile=0.05,
    max_percentile=0.95
)
```

## Window Operations

```python
# Moving averages
sma = EquityPricing.close.average(window_length=20)

# Standard deviation
std = EquityPricing.close.stddev(window_length=20)

# Linear regression
slope = EquityPricing.close.linear_regression(window_length=20).slope
```

## See [Factors](factors.md) and [Filters](filters.md) for more operations.
