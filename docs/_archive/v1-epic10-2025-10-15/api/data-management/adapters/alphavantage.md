# AlphaVantage Adapter

Global market data with fundamentals, forex, and technical indicators.

## Overview

**API Key Required**: Yes (free tier at [alphavantage.co](https://www.alphavantage.co))

**Supported Assets**: Global Stocks, Forex, Cryptocurrencies, Commodities

**Features**: Fundamental data, pre-calculated indicators, global coverage

## Quick Start

```python
from rustybt.data.adapters import AlphaVantageAdapter
import pandas as pd
import os

adapter = AlphaVantageAdapter(api_key=os.getenv('ALPHAVANTAGE_API_KEY'))

df = await adapter.fetch(
    symbols=['AAPL', 'IBM'],
    start_date=pd.Timestamp('2024-01-01'),
    end_date=pd.Timestamp('2024-01-31'),
    resolution='1d'
)
```

**Note**: Free tier limited to 25 requests/day.

## See [Adapter Overview](overview.md) for common features.
