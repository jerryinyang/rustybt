# Pipeline Loaders

Loaders provide custom data to pipeline computations.

## Built-in Loaders

### EquityPricingLoader

Loads OHLCV data:

```python
from rustybt.pipeline.loaders import EquityPricingLoader
from rustybt.pipeline.data import EquityPricing

# Used automatically for EquityPricing columns
inputs = [EquityPricing.close, EquityPricing.volume]
```

### USEquityPricingLoader

Specialized for US equities with adjustments.

## Custom Loaders

```python
from rustybt.pipeline.loaders import USEquityPricingLoader

class FundamentalsLoader(PipelineLoader):
    """Load fundamental data."""

    def load_adjusted_array(self, domain, columns, dates, sids, mask):
        # Load data from custom source
        data = self.fetch_fundamentals(sids, dates)

        # Return as AdjustedArray
        return AdjustedArray(
            data=data,
            adjustments={},  # No adjustments
            missing_value=np.nan
        )

# Register loader
pipe.add_loader(FundamentalsLoader())
```

## Data Sources

```python
from rustybt.pipeline.data import DataSet, Column

class Fundamentals(DataSet):
    """Fundamental data columns."""

    pe_ratio = Column(dtype=float)
    market_cap = Column(dtype=float)
    revenue = Column(dtype=float)

# Use in factors
from rustybt.pipeline import CustomFactor

class ValueFactor(CustomFactor):
    inputs = [Fundamentals.pe_ratio, Fundamentals.market_cap]
    window_length = 1

    def compute(self, today, assets, out, pe, mcap):
        out[:] = mcap / pe  # Simple value score
```

## See [Overview](overview.md) for pipeline architecture.
