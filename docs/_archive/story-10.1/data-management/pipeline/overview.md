# Pipeline System Overview

The Pipeline system provides a declarative framework for computing cross-sectional factors, filters, and features.

## Overview

Pipeline enables you to:
- Define factors (numerical computations)
- Create filters (boolean selections)
- Build classifiers (categorical groupings)
- Combine expressions declaratively

## Architecture

```
Pipeline
├── Factors (numerical)
│   ├── SimpleMovingAverage
│   ├── RSI
│   └── Custom factors
├── Filters (boolean)
│   ├── StaticAssets
│   ├── Top/Bottom
│   └── Custom filters
└── Classifiers (categorical)
    ├── Sector
    └── Custom classifiers
```

## Quick Start

```python
from rustybt.pipeline import Pipeline
from rustybt.pipeline.data import EquityPricing
from rustybt.pipeline.factors import SimpleMovingAverage, RSI

# Create pipeline
pipe = Pipeline()

# Add factors
sma_20 = SimpleMovingAverage(
    inputs=[EquityPricing.close],
    window_length=20
)
rsi = RSI(window_length=14)

pipe.add(sma_20, 'sma_20')
pipe.add(rsi, 'rsi')

# Add filter
pipe.set_screen(rsi < 30)  # Oversold stocks
```

## Using in Strategy

```python
from rustybt.algorithm import TradingAlgorithm

class PipelineStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Attach pipeline
        self.attach_pipeline(pipe, 'my_pipe')

    def before_trading_start(self, context, data):
        # Get pipeline output
        output = self.pipeline_output('my_pipe')

        # Use factor values
        for asset in output.index:
            if output.loc[asset, 'rsi'] < 30:
                self.order_target_percent(asset, 0.10)
```

## See detailed guides:
- [Factors](factors.md) - Numerical computations
- [Filters](filters.md) - Boolean selections
- [Loaders](loaders.md) - Custom data loading
- [Expressions](expressions.md) - Combining terms
