# Polygon Adapter

Professional-grade market data from Polygon.io covering stocks, options, forex, and crypto.

## Overview

**API Key Required**: Yes (get free tier at [polygon.io](https://polygon.io))

**Supported Assets**: Stocks, Options, Forex, Cryptocurrencies

**Features**: Real-time and historical OHLCV, tick data, trades, quotes

## Quick Start

```python
from rustybt.data.adapters import PolygonAdapter
import pandas as pd
import os

adapter = PolygonAdapter(api_key=os.getenv('POLYGON_API_KEY'))

df = await adapter.fetch(
    symbols=['AAPL', 'MSFT'],
    start_date=pd.Timestamp('2024-01-01'),
    end_date=pd.Timestamp('2024-01-31'),
    resolution='1d'
)
```

## See [Adapter Overview](overview.md) for common features.
