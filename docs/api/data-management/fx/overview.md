# Foreign Exchange (FX) Data

Comprehensive guide to foreign exchange rate handling for multi-currency trading strategies.

## Overview

RustyBT provides a flexible FX rate system for:
- **Multi-currency portfolios**: Track positions in different currencies
- **Currency conversion**: Convert values between currencies at historical rates
- **Rate management**: Store and retrieve exchange rates efficiently
- **Cross-currency analysis**: Compare performance across currency zones

## Architecture

```
┌────────────────────────────────────┐
│      Trading Strategy              │
│  (Multi-currency portfolio)        │
└──────────────┬─────────────────────┘
               │
        ┌──────▼──────┐
        │ FXRateReader│
        └──────┬──────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌───▼──┐  ┌───▼────┐
│In Mem │  │ HDF5 │  │Explode │
└───────┘  └──────┘  └────────┘
```

## Core Concepts

### Rate Names

Rates represent different exchange rate quotes:
- **`mid`**: Mid-market rate (average of bid/ask)
- **`bid`**: Bid rate (bank buys base currency)
- **`ask`**: Ask rate (bank sells base currency)
- **`close`**: Official closing rate
- **Custom**: Any user-defined rate name

### Currency Codes

Standard 3-letter ISO 4217 codes:
- `USD` - US Dollar
- `EUR` - Euro
- `GBP` - British Pound
- `JPY` - Japanese Yen
- `CHF` - Swiss Franc
- etc.

### Quote vs Base

```python
# Converting 100 EUR to USD at rate 1.10
# EUR is "base" (what you have)
# USD is "quote" (what you want)
# Rate: 1 EUR = 1.10 USD
usd_value = 100 * 1.10  # 110 USD
```

## Quick Start

### In-Memory FX Rates (Testing)

```python
from rustybt.data.fx import InMemoryFXRateReader
import pandas as pd
import numpy as np

# Create rate data
dates = pd.date_range('2024-01-01', '2024-01-31', freq='D')
currencies = ['EUR', 'GBP', 'JPY']

# EUR/USD rates (how many USD per 1 EUR)
eur_usd_rates = np.linspace(1.08, 1.12, len(dates))
gbp_usd_rates = np.linspace(1.25, 1.28, len(dates))
jpy_usd_rates = np.linspace(0.0067, 0.0070, len(dates))  # 1 JPY to USD

# Build data structure
data = {
    'mid': {  # Rate name
        'USD': pd.DataFrame({  # Quote currency
            'EUR': eur_usd_rates,
            'GBP': gbp_usd_rates,
            'JPY': jpy_usd_rates
        }, index=dates)
    }
}

# Create reader
fx_reader = InMemoryFXRateReader(
    data=data,
    default_rate='mid'
)

# Get single rate
rate = fx_reader.get_rate_scalar(
    rate='mid',
    quote='USD',
    base='EUR',
    dt=pd.Timestamp('2024-01-15')
)
print(f"EUR/USD rate: {rate}")

# Get multiple rates
rates = fx_reader.get_rates(
    rate='mid',
    quote='USD',
    bases=np.array(['EUR', 'GBP']),
    dts=pd.DatetimeIndex(['2024-01-15', '2024-01-16'])
)
print(f"Rates shape: {rates.shape}")  # (2 dates, 2 currencies)
```

### HDF5 FX Rates (Production)

```python
from rustybt.data.fx import HDF5FXRateReader, HDF5FXRateWriter
import pandas as pd

# Write rates to HDF5
writer = HDF5FXRateWriter('/path/to/fx_rates.h5')

# Write EUR/USD rates
writer.write(
    rate='mid',
    quote='USD',
    rates=pd.DataFrame({
        'EUR': [1.08, 1.09, 1.10],
        'GBP': [1.25, 1.26, 1.27],
        'JPY': [0.0067, 0.0068, 0.0069]
    }, index=pd.date_range('2024-01-01', periods=3))
)

# Read rates
reader = HDF5FXRateReader('/path/to/fx_rates.h5')

rate = reader.get_rate_scalar(
    rate='mid',
    quote='USD',
    base='EUR',
    dt=pd.Timestamp('2024-01-02')
)
```

## FX Rate Readers

### Base Interface

All FX readers implement `FXRateReader`:

```python
from rustybt.data.fx import FXRateReader

class FXRateReader(ABC):
    """Base interface for FX rate readers."""

    def get_rates(self, rate, quote, bases, dts):
        """Get 2D array of rates.

        Args:
            rate: Rate name ('mid', 'bid', 'ask', etc.)
            quote: Currency to convert TO
            bases: Array of currencies to convert FROM
            dts: Timestamps for rate lookups

        Returns:
            Array of shape (len(dts), len(bases))
        """

    def get_rate_scalar(self, rate, quote, base, dt):
        """Get single rate value."""

    def get_rates_columnar(self, rate, quote, bases, dts):
        """Get rates for parallel (base, dt) pairs."""
```

### InMemoryFXRateReader

**Use for**: Testing, small datasets, prototyping

```python
from rustybt.data.fx import InMemoryFXRateReader

reader = InMemoryFXRateReader(
    data={
        'mid': {
            'USD': pd.DataFrame(...),  # Indexed by dates, columns=currencies
            'EUR': pd.DataFrame(...),
        }
    },
    default_rate='mid'
)
```

**Pros**:
- Fast lookup
- Simple setup
- Good for testing

**Cons**:
- Limited by RAM
- No persistence

### HDF5FXRateReader

**Use for**: Production, large datasets, historical rates

```python
from rustybt.data.fx import HDF5FXRateReader

reader = HDF5FXRateReader('/path/to/fx_rates.h5')
```

**Pros**:
- Efficient storage
- Fast random access
- Persistent
- Industry standard format

**Cons**:
- Requires HDF5 file
- Write overhead

### ExplodingFXRateReader

**Use for**: Testing multi-currency code without real rates

```python
from rustybt.data.fx import ExplodingFXRateReader

reader = ExplodingFXRateReader()

# Raises error on any rate lookup
# Useful to ensure single-currency code doesn't accidentally use FX
```

## Usage in Strategies

### Multi-Currency Portfolio

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.data.fx import HDF5FXRateReader

class GlobalEquityStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Assets in different currencies
        context.us_stock = self.symbol('AAPL')    # USD
        context.uk_stock = self.symbol('VOD.L')   # GBP
        context.jp_stock = self.symbol('7203.T')  # JPY

        # Load FX rates
        context.fx_reader = HDF5FXRateReader('fx_rates.h5')

    def handle_data(self, context, data):
        # Get current prices (in local currencies)
        aapl_price_usd = data.current(context.us_stock, 'close')
        vod_price_gbp = data.current(context.uk_stock, 'close')
        toyota_price_jpy = data.current(context.jp_stock, 'close')

        # Convert to USD for comparison
        dt = context.self.get_datetime()

        gbp_usd_rate = context.fx_reader.get_rate_scalar(
            rate='mid',
            quote='USD',
            base='GBP',
            dt=dt
        )

        jpy_usd_rate = context.fx_reader.get_rate_scalar(
            rate='mid',
            quote='USD',
            base='JPY',
            dt=dt
        )

        vod_price_usd = vod_price_gbp * gbp_usd_rate
        toyota_price_usd = toyota_price_jpy * jpy_usd_rate

        # Equal-weight allocation in USD terms
        order_target_percent(context.us_stock, 0.33)
        order_target_percent(context.uk_stock, 0.33)
        order_target_percent(context.jp_stock, 0.33)
```

### Currency Conversion Utility

```python
def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    dt: pd.Timestamp,
    fx_reader: FXRateReader,
    rate_name: str = 'mid'
) -> float:
    """Convert amount from one currency to another.

    Args:
        amount: Amount in from_currency
        from_currency: Source currency code
        to_currency: Target currency code
        dt: Date for exchange rate lookup
        fx_reader: FX rate reader
        rate_name: Rate to use ('mid', 'bid', 'ask')

    Returns:
        Amount in to_currency
    """
    if from_currency == to_currency:
        return amount

    rate = fx_reader.get_rate_scalar(
        rate=rate_name,
        quote=to_currency,
        base=from_currency,
        dt=dt
    )

    return amount * rate

# Usage
eur_amount = 100.0
usd_amount = convert_currency(
    amount=eur_amount,
    from_currency='EUR',
    to_currency='USD',
    dt=pd.Timestamp('2024-01-15'),
    fx_reader=fx_reader
)
```

## Data Sources

### Historical FX Rates

**Free Sources**:
- European Central Bank (ECB) - Daily rates
- Federal Reserve - Daily rates
- OANDA - Historical rates (limited)

**Paid Sources**:
- Bloomberg - Real-time and historical
- Refinitiv - Professional FX data
- AlphaVantage - API access

### Fetching ECB Rates

```python
import pandas as pd
import requests

def fetch_ecb_rates(start_date, end_date):
    """Fetch EUR exchange rates from ECB."""
    url = "https://data-api.ecb.europa.eu/service/data/EXR/..."

    # Implementation details...
    response = requests.get(url)
    # Parse XML response
    # Return DataFrame
    pass
```

## Best Practices

### 1. Consistent Rate Names

```python
# Good: Use standard rate names
RATE_NAMES = {
    'mid': 'Mid-market rate',
    'bid': 'Bid rate',
    'ask': 'Ask rate',
    'close': 'Official close'
}

# Bad: Inconsistent naming
# 'midpoint', 'mid_rate', 'middle', etc.
```

### 2. Handle Missing Rates

```python
def safe_get_rate(fx_reader, rate, quote, base, dt):
    """Get rate with fallback to 1.0 for same currency."""
    if quote == base:
        return 1.0

    try:
        rate_value = fx_reader.get_rate_scalar(rate, quote, base, dt)
        if np.isnan(rate_value):
            raise ValueError(f"No rate for {base}/{quote} on {dt}")
        return rate_value
    except Exception as e:
        logger.error(f"FX rate lookup failed: {e}")
        raise
```

### 3. Cache Frequently Used Rates

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_fx_rate(rate_name, quote, base, dt_str):
    """Cached FX rate lookup."""
    dt = pd.Timestamp(dt_str)
    return fx_reader.get_rate_scalar(rate_name, quote, base, dt)
```

### 4. Validate Rate Consistency

```python
def validate_fx_triangle(fx_reader, currency_a, currency_b, currency_c, dt):
    """Validate triangular arbitrage consistency."""
    # A->B->C should equal A->C
    ab = fx_reader.get_rate_scalar('mid', currency_b, currency_a, dt)
    bc = fx_reader.get_rate_scalar('mid', currency_c, currency_b, dt)
    ac = fx_reader.get_rate_scalar('mid', currency_c, currency_a, dt)

    indirect = ab * bc
    tolerance = 0.001  # 0.1% tolerance

    if abs(indirect - ac) / ac > tolerance:
        raise ValueError(f"FX triangle inconsistency: {indirect} vs {ac}")
```

## Performance Considerations

### HDF5 Storage Efficiency

```python
# Efficient: Use HDF5 for large rate datasets
writer = HDF5FXRateWriter('fx_rates.h5')

# Write all rates for one quote currency at once
for quote in ['USD', 'EUR', 'GBP']:
    writer.write(
        rate='mid',
        quote=quote,
        rates=large_dataframe  # Many dates and currencies
    )

# Fast random access during backtest
rate = reader.get_rate_scalar('mid', 'USD', 'EUR', dt)
```

### Batch Lookups

```python
# Efficient: Batch lookup
rates = fx_reader.get_rates(
    rate='mid',
    quote='USD',
    bases=np.array(['EUR', 'GBP', 'JPY']),
    dts=pd.date_range('2024-01-01', '2024-01-31')
)

# Inefficient: Loop of scalar lookups
for dt in dates:
    for base in currencies:
        rate = fx_reader.get_rate_scalar('mid', 'USD', base, dt)
```

## Troubleshooting

### Issue: Missing Rate Data

```python
# Check available rates
with pd.HDFStore('fx_rates.h5', mode='r') as store:
    print(store.keys())  # List all stored rates

# Verify date coverage
rates_df = reader.get_rates('mid', 'USD', ['EUR'], date_range)
print(f"Coverage: {(~np.isnan(rates_df)).sum()} / {len(rates_df)}")
```

### Issue: Inverted Rates

```python
# If you have USD/EUR but need EUR/USD
usd_eur = fx_reader.get_rate_scalar('mid', 'EUR', 'USD', dt)
eur_usd = 1.0 / usd_eur  # Invert
```

### Issue: Cross Rates

```python
def get_cross_rate(fx_reader, quote, base, via, dt):
    """Calculate cross rate via intermediate currency."""
    # Get EUR/USD via GBP: EUR->GBP->USD
    eur_gbp = fx_reader.get_rate_scalar('mid', via, base, dt)
    gbp_usd = fx_reader.get_rate_scalar('mid', quote, via, dt)
    return eur_gbp * gbp_usd

# EUR/USD via GBP
eur_usd_cross = get_cross_rate(fx_reader, 'USD', 'EUR', 'GBP', dt)
```

## API Reference

See detailed guides:
- [FX Rate Providers](providers.md) - Data sources and fetching
- [FX Converters](converters.md) - Currency conversion utilities
- [FX Storage](storage.md) - In-memory vs HDF5 storage comparison

## See Also

- [Data Portal](../readers/data-portal.md) - Data access integration
- Multi-Asset Strategies (Coming soon) - Multi-currency examples
- Performance (Coming soon) - FX lookup optimization
