# Adapter Selection Guide

## Overview

RustyBT provides multiple data adapters for fetching market data from various sources. This guide helps you choose the right adapter for your use case.

## Quick Decision Tree

```
Need market data?
│
├─ Local CSV files? → CSV Adapter
│
├─ Cryptocurrency?
│  └─ 100+ exchanges? → CCXT Adapter
│
├─ US Stocks?
│  ├─ Free/testing? → YFinance Adapter
│  ├─ Paper trading? → Alpaca Adapter (paper mode)
│  ├─ Production/real-time? → Polygon or Alpaca (live mode)
│  └─ Global stocks? → AlphaVantage Adapter
│
├─ Forex?
│  ├─ Real-time? → Polygon Adapter
│  └─ Free tier okay? → AlphaVantage Adapter
│
└─ Options?
   └─ US options? → Polygon Adapter
```

## Adapter Comparison Matrix

| Adapter | Asset Classes | Cost | Rate Limits | Real-time | Best For |
|---------|---------------|------|-------------|-----------|----------|
| **CSV** | Any (custom) | Free | None | No | Custom data, backtesting |
| **CCXT** | Crypto | Free | Exchange-specific | Yes (some) | Crypto trading, multi-exchange |
| **YFinance** | Stocks, ETFs, indices, forex | Free | ~2000/hr | No (15-min delay) | Development, research |
| **Polygon** | Stocks, options, forex, crypto | Free-$99/mo | 5-100/min | Yes | Production US markets |
| **Alpaca** | US stocks | Free-Paid | 200/min | Yes | US stock trading |
| **AlphaVantage** | Stocks, forex, crypto | Free-$50/mo | 5-75/min | No | Global markets |

## Detailed Comparisons

### For Cryptocurrency Data

#### CCXT Adapter

**Pros**:
- ✅ Access to 100+ exchanges
- ✅ Unified interface across all exchanges
- ✅ Free for most exchanges
- ✅ Real-time data from many exchanges
- ✅ High-frequency intraday data (1m, 5m, 15m, etc.)

**Cons**:
- ❌ Each exchange has different rate limits
- ❌ Symbol formats vary by exchange
- ❌ Some exchanges require API keys

**Use When**:
- Trading or analyzing multiple cryptocurrencies
- Need data from specific exchanges (Binance, Coinbase, Kraken, etc.)
- Building crypto trading strategies

**Example**:
```python
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

adapter = CCXTAdapter(exchange_id="binance")
data = await adapter.fetch(["BTC/USDT", "ETH/USDT"], start, end, "1h")
```

---

### For US Stock Data

#### YFinance Adapter (Free)

**Pros**:
- ✅ Completely free
- ✅ No API key required
- ✅ Good for US stocks and ETFs
- ✅ 10+ years of historical data
- ✅ Dividend and split data available

**Cons**:
- ❌ 15-minute delayed data
- ❌ Intraday data limited to 60 days
- ❌ Rate limits (informal, ~2000/hr)
- ❌ No real-time streaming

**Use When**:
- Development and testing
- Academic research
- Backtesting strategies
- Don't need real-time data

**Example**:
```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

adapter = YFinanceAdapter()
data = await adapter.fetch(["AAPL", "MSFT"], start, end, "1d")
```

#### Alpaca Adapter (Paper: Free, Live: Paid)

**Pros**:
- ✅ Free paper trading feed (IEX)
- ✅ Real-time data (live mode)
- ✅ 200 requests/minute
- ✅ Good for algorithmic trading
- ✅ WebSocket support for live streaming

**Cons**:
- ❌ US stocks only (no forex/options)
- ❌ Live feed requires paid subscription
- ❌ IEX feed (paper) has limited market coverage

**Use When**:
- Building algorithmic trading systems
- Need paper trading environment
- Want real-time US stock data (live mode)

**Example**:
```python
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

# Paper trading (free)
adapter = AlpacaAdapter(is_paper=True)

# Live trading (paid)
adapter_live = AlpacaAdapter(is_paper=False)
```

#### Polygon Adapter (Free-$99/mo)

**Pros**:
- ✅ Real-time data (all tiers)
- ✅ US stocks, options, forex, crypto
- ✅ High rate limits (developer tier: 100/min)
- ✅ Professional-grade data quality
- ✅ WebSocket support

**Cons**:
- ❌ Free tier very limited (5 req/min)
- ❌ Best features require paid tiers
- ❌ Focused on US markets

**Use When**:
- Production trading systems
- Need real-time US market data
- Trading options
- Budget for professional data

**Example**:
```python
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

# US stocks (developer tier for production)
adapter = PolygonAdapter(tier="developer", asset_type="stocks")

# Options
adapter_options = PolygonAdapter(tier="developer", asset_type="options")
```

---

### For Forex Data

#### Polygon Adapter

**Pros**:
- ✅ Real-time forex data
- ✅ High-frequency resolutions
- ✅ Good rate limits (paid tiers)

**Cons**:
- ❌ Requires paid tier for production
- ❌ Limited to major currency pairs

**Use When**:
- Need real-time forex data
- Trading major currency pairs
- Have budget for professional data

**Example**:
```python
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

adapter = PolygonAdapter(tier="developer", asset_type="forex")
data = await adapter.fetch_ohlcv("EURUSD", start, end, "1h")
```

#### AlphaVantage Adapter

**Pros**:
- ✅ Free tier available
- ✅ Global forex coverage
- ✅ Simple API

**Cons**:
- ❌ Very strict rate limits (free: 5 req/min)
- ❌ Delayed data
- ❌ No real-time streaming

**Use When**:
- Backtesting forex strategies
- Research and development
- Don't need real-time data
- Limited budget

**Example**:
```python
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

adapter = AlphaVantageAdapter(tier="free", asset_type="forex")
data = await adapter.fetch_ohlcv("EUR/USD", start, end, "1d")
```

---

### For Custom Data

#### CSV Adapter

**Pros**:
- ✅ Import any CSV format
- ✅ Flexible schema mapping
- ✅ Auto-detection of delimiters and dates
- ✅ No rate limits (local files)
- ✅ Timezone conversion support
- ✅ Missing data handling strategies

**Cons**:
- ❌ Requires data preparation
- ❌ No automatic updates
- ❌ Not suitable for live trading

**Use When**:
- Have proprietary data sources
- Testing with custom datasets
- Academic research with specific data
- Data from vendors not supported by adapters

**Example**:
```python
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

config = CSVConfig(
    file_path="data/custom_data.csv",
    schema_mapping=SchemaMapping(
        date_column="Date",
        open_column="Open",
        high_column="High",
        low_column="Low",
        close_column="Close",
        volume_column="Volume"
    )
)

adapter = CSVAdapter(config)
```

---

## Use Case Recommendations

### Backtesting Historical Strategies

**Recommended**: YFinance (free) or CSV (custom data)

**Why**: No need for real-time data, want to minimize costs, need long historical data.

**Setup**:
```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

adapter = YFinanceAdapter()

# Fetch 10 years of daily data
data = await adapter.fetch(
    symbols=["SPY"],
    start_date=pd.Timestamp("2014-01-01"),
    end_date=pd.Timestamp("2024-01-01"),
    resolution="1d"
)
```

### Live Algorithmic Trading (US Stocks)

**Recommended**: Alpaca (live) or Polygon (developer tier)

**Why**: Need real-time data, WebSocket support, high rate limits.

**Setup**:
```python
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

# Real-time trading
adapter = AlpacaAdapter(is_paper=False)
```

### Cryptocurrency Trading

**Recommended**: CCXT

**Why**: Access to 100+ exchanges, real-time data, high-frequency support.

**Setup**:
```python
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

adapter = CCXTAdapter(exchange_id="binance")

# High-frequency data
data = await adapter.fetch(
    symbols=["BTC/USDT"],
    start_date=pd.Timestamp("2024-01-01"),
    end_date=pd.Timestamp("2024-01-02"),
    resolution="1m"
)
```

### Research and Development

**Recommended**: YFinance

**Why**: Free, no API key required, sufficient for testing and development.

**Setup**:
```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

adapter = YFinanceAdapter()
```

### Global Market Analysis

**Recommended**: AlphaVantage (premium) or Polygon

**Why**: Access to global markets, multiple asset classes, professional data.

**Setup**:
```python
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

# Global stocks
adapter = AlphaVantageAdapter(tier="premium", asset_type="stocks")

# Can fetch US, UK, European, Asian stocks
data_us = await adapter.fetch_ohlcv("AAPL", start, end, "1d")
data_uk = await adapter.fetch_ohlcv("IBM.LON", start, end, "1d")
```

---

## Cost Optimization Strategies

### Development Phase

1. **Use Free Adapters**:
   - YFinance for US stocks
   - CCXT for crypto (most exchanges free)
   - CSV for custom data

2. **Test with Small Date Ranges**:
   - Minimize API calls during development
   - Cache downloaded data locally

3. **Use Paper Trading Modes**:
   - Alpaca paper trading (free IEX feed)
   - Polygon free tier for testing

### Production Phase

1. **Evaluate Data Needs**:
   - Real-time vs. 15-minute delayed
   - Frequency of updates required
   - Number of symbols to track

2. **Choose Cost-Effective Tier**:
   - Alpaca: $0 (paper) to enterprise pricing (live)
   - Polygon: $0 (limited) to $99/mo (developer)
   - AlphaVantage: $0 to $49.99/mo

3. **Cache Aggressively**:
   - Store historical data locally
   - Only fetch recent updates
   - Use bundle system for efficient storage

---

## Performance Considerations

### Rate Limits

| Adapter | Free Tier | Paid Tier | Daily Limits |
|---------|-----------|-----------|--------------|
| YFinance | ~2000/hr | N/A | Informal |
| CCXT | Exchange-specific | Exchange-specific | Varies |
| Polygon | 5/min | 100/min | None |
| Alpaca | 200/min | 200/min | None |
| AlphaVantage | 5/min | 75/min | 500-1200/day |

**Tip**: For high-frequency needs, use Polygon (developer) or Alpaca.

### Data Freshness

| Adapter | Delay | Live Streaming |
|---------|-------|----------------|
| YFinance | 15 minutes | No |
| CCXT | Exchange-specific | Yes (some) |
| Polygon | Real-time | Yes |
| Alpaca | Real-time (live) | Yes |
| AlphaVantage | Delayed | No |

**Tip**: For live trading, use Polygon, Alpaca, or CCXT.

---

## Migration Paths

### From YFinance to Production

**Path**: YFinance → Alpaca (paper) → Alpaca (live)

**Steps**:
1. Develop strategy with YFinance (free)
2. Test with Alpaca paper trading (free)
3. Deploy to Alpaca live (paid) when ready

### From Free to Paid Tiers

**Path**: Free tier → Starter tier → Professional tier

**When to Upgrade**:
- Hit rate limits regularly
- Need real-time data
- Scaling to more symbols
- Moving to production

---

## See Also

- [Base Adapter Framework](./base-adapter.md) - Core adapter interface
- [CCXT Adapter](./ccxt-adapter.md) - Cryptocurrency exchanges
- [YFinance Adapter](./yfinance-adapter.md) - Free stock data
- [CSV Adapter](./csv-adapter.md) - Custom data import
- [Polygon Adapter](./polygon-adapter.md) - Professional US markets
- [Alpaca Adapter](./alpaca-adapter.md) - US stock trading
- [AlphaVantage Adapter](./alphavantage-adapter.md) - Global markets
