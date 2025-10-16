# FX Rate Data Providers

Sources for historical and real-time foreign exchange data.

## Free Data Sources

### European Central Bank (ECB)

**Coverage**: EUR against 40+ currencies
**Frequency**: Daily (business days)
**Historical**: From 1999
**Format**: XML, CSV

```python
import requests
import pandas as pd

def fetch_ecb_rates(start_date, end_date):
    """Fetch ECB FX rates."""
    url = "https://data-api.ecb.europa.eu/service/data/EXR/D..EUR.SP00.A"
    # Add date parameters and parse response
    # Returns DataFrame with rates
    pass
```

### Federal Reserve

**Coverage**: USD against major currencies
**Frequency**: Daily
**Historical**: Extensive
**API**: FRED (Federal Reserve Economic Data)

### OANDA

**Coverage**: 190+ currencies
**Frequency**: Daily (free), intraday (paid)
**Historical**: Limited on free tier
**Format**: JSON API

## Commercial Providers

### Bloomberg

**Coverage**: All major and exotic pairs
**Frequency**: Real-time tick data
**Historical**: Decades of data
**Access**: Terminal or API (expensive)

### Refinitiv

**Coverage**: Comprehensive FX data
**Frequency**: Real-time
**Features**: Bid/ask spreads, order book
**Access**: Enterprise license

### AlphaVantage

**Coverage**: 150+ currencies
**Frequency**: Daily (free), intraday (premium)
**API**: REST JSON
**Limits**: 25 requests/day (free)

```python
def fetch_alphavantage_fx(from_currency, to_currency, api_key):
    """Fetch FX rate from AlphaVantage."""
    url = f"https://www.alphavantage.co/query"
    params = {
        'function': 'FX_DAILY',
        'from_symbol': from_currency,
        'to_symbol': to_currency,
        'apikey': api_key
    }
    # Returns JSON with daily rates
    pass
```

## Data Quality Considerations

1. **Bid/Ask Spreads**: Free sources typically only provide mid rates
2. **Update Frequency**: Real-time vs end-of-day
3. **Historical Depth**: How far back data is available
4. **Reliability**: Data gaps and corrections
5. **Licensing**: Commercial use restrictions

## See [FX Overview](overview.md) for storage and usage.
