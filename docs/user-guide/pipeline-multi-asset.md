# Using Pipeline with Multiple Asset Types

**Last Updated:** 2025-10-30

## Overview

The Pipeline API in rustybt can be used with any asset type (equities, forex, crypto, futures) by specifying the appropriate **domain** when creating your pipeline.

## Key Concepts

### Domains

A **domain** defines the trading calendar and universe for your pipeline:

- `US_EQUITIES` - US stock market (XNYS calendar, Monday-Friday)
- `GB_EQUITIES` - UK stock market (LSE calendar)
- Custom domains - Create your own for forex (24/5) or crypto (24/7)

### Domain Specialization

Data columns in Pipeline can be **specialized** to different domains:

```python
from rustybt.pipeline.data import EquityPricing

# Generic columns (works with any domain)
EquityPricing.close
EquityPricing.volume

# Domain-specialized columns (works only with US equities)
USEquityPricing.close  # Same as EquityPricing.specialize(US_EQUITIES).close
```

**Important:** Always use **generic** `EquityPricing` (not `USEquityPricing`) when working with non-US asset types.

---

## Example 1: Pipeline with Crypto Data

```python
import pandas as pd
from rustybt import run_algorithm
from rustybt.pipeline import Pipeline
from rustybt.pipeline.data import EquityPricing  # Use generic, not USEquityPricing
from rustybt.pipeline.factors import AverageDollarVolume
from rustybt.pipeline.domain import EquityCalendarDomain

# Create 24/7 domain for crypto
CRYPTO = EquityCalendarDomain(
    country_code="US",
    calendar_name="24/7",
)


def make_pipeline():
    """Create pipeline with crypto domain."""
    avg_volume = AverageDollarVolume(window_length=5)
    top_20_volume = avg_volume.top(20)

    return Pipeline(
        columns={"avg_volume": avg_volume},
        screen=top_20_volume,
        domain=CRYPTO,  # CRITICAL: Specify domain here
    )


def initialize(context):
    """Attach pipeline during initialization."""
    pipe = make_pipeline()
    context.attach_pipeline(pipe, "universe")


def before_trading_start(context, data):
    """Access pipeline output before market opens."""
    # Get universe from pipeline
    pipeline_output = context.pipeline_output("universe")
    context.universe = pipeline_output.index

    print(f"Universe: {len(context.universe)} assets")


# Run backtest with crypto bundle
results = run_algorithm(
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    initialize=initialize,
    before_trading_start=before_trading_start,
    capital_base=100000.0,
    bundle="binance-spot-1d",  # Crypto bundle
    data_frequency="daily",
)
```

---

## Example 2: Pipeline with Forex Data

```python
from rustybt.pipeline.domain import EquityCalendarDomain

# Create 24/5 domain for forex (Sunday night - Friday night)
FOREX = EquityCalendarDomain(
    country_code="US",
    calendar_name="24/5",
)


def make_forex_pipeline():
    """Create pipeline for forex pairs."""
    avg_volume = AverageDollarVolume(window_length=10)
    high_volume_pairs = avg_volume.top(30)

    return Pipeline(
        columns={
            "avg_volume": avg_volume,
            "close": EquityPricing.close.latest,
        },
        screen=high_volume_pairs,
        domain=FOREX,  # Forex domain
    )


def initialize(context):
    pipe = make_forex_pipeline()
    context.attach_pipeline(pipe, "forex_universe")


def before_trading_start(context, data):
    output = context.pipeline_output("forex_universe")
    context.pairs = output.index

    for pair in context.pairs[:5]:
        close_price = output.loc[pair, 'close']
        print(f"{pair.asset_name}: ${close_price:.5f}")


# Run with forex bundle
results = run_algorithm(
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    initialize=initialize,
    before_trading_start=before_trading_start,
    capital_base=100000.0,
    bundle="oanda-forex-1d",  # Forex bundle
    data_frequency="daily",
)
```

---

## Example 3: Multi-Asset Pipeline (Advanced)

You can create multiple pipelines for different asset types:

```python
def initialize(context):
    # Crypto pipeline
    crypto_pipe = Pipeline(
        columns={"volume": EquityPricing.volume.latest},
        screen=AverageDollarVolume(window_length=5).top(10),
        domain=CRYPTO,
    )
    context.attach_pipeline(crypto_pipe, "crypto")

    # Forex pipeline
    forex_pipe = Pipeline(
        columns={"volume": EquityPricing.volume.latest},
        screen=AverageDollarVolume(window_length=5).top(10),
        domain=FOREX,
    )
    context.attach_pipeline(forex_pipe, "forex")


def before_trading_start(context, data):
    # Access each pipeline separately
    crypto_universe = context.pipeline_output("crypto").index
    forex_universe = context.pipeline_output("forex").index

    print(f"Crypto assets: {len(crypto_universe)}")
    print(f"Forex pairs: {len(forex_universe)}")
```

---

## Common Pitfalls

### ❌ Wrong: Using USEquityPricing with Non-Equity Data

```python
from rustybt.pipeline.data import USEquityPricing  # ❌ US-specific

def make_pipeline():
    return Pipeline(
        columns={"close": USEquityPricing.close.latest},  # ❌ Won't work with crypto
        domain=CRYPTO,
    )
```

**Error:** `ValueError: No PipelineLoader registered for column EquityPricing<US>.close`

### ✅ Correct: Using Generic EquityPricing

```python
from rustybt.pipeline.data import EquityPricing  # ✅ Generic

def make_pipeline():
    return Pipeline(
        columns={"close": EquityPricing.close.latest},  # ✅ Works with any domain
        domain=CRYPTO,
    )
```

---

## Domain Requirements

When creating a pipeline, you **MUST** specify a domain if:
1. Using non-US equity data
2. Using forex data
3. Using crypto data
4. Using custom calendars

The domain tells Pipeline:
- Which calendar to use for date alignment
- Which assets are in scope
- How to handle trading hours

---

## Available Built-in Factors

All built-in factors work with any asset type as long as you specify the correct domain:

- `AverageDollarVolume` - Average $ volume over N days
- `SimpleMovingAverage` - Moving average of any column
- `Returns` - Period returns
- `RSI` - Relative Strength Index
- `BollingerBands` - Volatility bands
- Custom factors - Create your own!

---

## Creating Custom Domains

For specialized calendars (e.g., crypto exchanges with specific hours):

```python
from rustybt.pipeline.domain import EquityCalendarDomain

# Custom calendar (must be registered with rustybt first)
BINANCE = EquityCalendarDomain(
    country_code="US",
    calendar_name="binance-24-7",  # Must match registered calendar name
)
```

**Note:** Calendar must be registered using `register_calendar_alias()` before use.

---

## Troubleshooting

### Error: "No PipelineLoader registered for column"

**Cause:** Using domain-specialized columns (like `USEquityPricing`) with a non-matching domain.

**Solution:** Use generic `EquityPricing` columns instead.

### Error: "start_date must be before or equal to end_date"

**Cause:** Calendar date alignment issues with custom domains.

**Solution:** Ensure your date range aligns with the bundle's available data and calendar.

### Error: "Missing lifetimes() method"

**Cause:** AssetFinder implementation incomplete.

**Solution:** This is fixed in recent versions. Ensure you're using rustybt >= 0.x.x.

---

## Best Practices

1. **Always specify domain** when creating pipelines for non-equity data
2. **Use generic `EquityPricing`** not `USEquityPricing` for multi-asset strategies
3. **Access pipelines in `before_trading_start()`** not `handle_data()`
4. **Test with short date ranges** first to validate your pipeline setup
5. **Check bundle calendars** match your domain calendar

---

## Further Reading

- [Pipeline API Guide](../guides/pipeline-api-guide.md)
- [Advanced Pipeline Techniques](../guides/advanced-pipeline-techniques.md)
- [Pipeline API Reference](../api/computation/pipeline-api.md)
- [Data Management](../api/data-management/README.md)

---

**Questions or Issues?**

File an issue on GitHub or check the troubleshooting guide.
