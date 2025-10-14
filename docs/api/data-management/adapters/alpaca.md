# Alpaca Adapter

Commission-free trading platform with integrated market data access.

## Overview

**API Key Required**: Yes (free account at [alpaca.markets](https://alpaca.markets))

**Supported Assets**: US Stocks, ETFs, Cryptocurrencies

**Features**: Real-time data for account holders, paper trading, historical data

## Quick Start

```python
from rustybt.data.adapters import AlpacaAdapter
import pandas as pd
import os

adapter = AlpacaAdapter(
    api_key=os.getenv('ALPACA_API_KEY'),
    api_secret=os.getenv('ALPACA_API_SECRET'),
    paper=True  # Use paper trading
)

df = await adapter.fetch(
    symbols=['AAPL', 'TSLA'],
    start_date=pd.Timestamp('2024-01-01'),
    end_date=pd.Timestamp('2024-01-31'),
    resolution='1d'
)
```

## See [Adapter Overview](overview.md) for common features.
