# External API Integration

## Broker API Integration

### Interactive Brokers (ib_async)
**Library:** `ib_async` (Pythonic async wrapper for IB API)
**Use Case:** Stocks, futures, options, forex for traditional markets
**Connection:** TWS or IB Gateway (localhost or remote)

**Authentication:**
```python
credentials = {
    "host": "127.0.0.1",
    "port": 7497,        # 7497=live, 7496=paper
    "client_id": 1
}
```

**Supported Order Types:**
- Market, Limit, Stop, Stop-Limit, Trailing Stop
- Bracket (entry + stop-loss + take-profit)
- OCO (One-Cancels-Other)

**Rate Limits:**
- 50 requests/second for market data
- 100 orders/second for order submission
- No API key required (local connection)

**Error Handling:**
- Connection timeout: 30s
- Reconnection with exponential backoff
- Order status polling for confirmation

### Binance (binance-connector)
**Library:** `binance-connector` (official Python SDK)
**Use Case:** Spot and futures crypto trading
**Endpoint:** `https://api.binance.com` (live), `https://testnet.binance.vision` (testnet)

**Authentication:**
```python
credentials = {
    "api_key": "...",
    "api_secret": "...",
    "testnet": False
}
```

**Supported Order Types:**
- Market, Limit, Stop-Loss, Stop-Loss-Limit, Take-Profit, Take-Profit-Limit
- OCO (One-Cancels-Other)
- Iceberg (partial quantity display)

**Rate Limits:**
- REST API: 1200 requests/minute (weight-based)
- WebSocket: 5 connections per IP
- Order placement: 100 orders/10s per symbol

**Error Codes:**
- `-1021`: Timestamp out of sync (adjust local clock)
- `-1022`: Invalid signature (check secret)
- `-2010`: Insufficient balance
- `-2011`: Order would trigger immediately (market order on limit-only market)

### Bybit (pybit)
**Library:** `pybit` (official Python SDK)
**Use Case:** Spot and derivatives crypto trading
**Endpoint:** `https://api.bybit.com` (live), `https://api-testnet.bybit.com` (testnet)

**Authentication:**
```python
credentials = {
    "api_key": "...",
    "api_secret": "...",
    "testnet": True
}
```

**Supported Order Types:**
- Market, Limit, Conditional (stop/take-profit)
- Post-Only (maker-only)
- Reduce-Only (close positions)

**Rate Limits:**
- REST API: 120 requests/minute
- WebSocket: 10 messages/second
- Order placement: 100 orders/second per symbol

### Hyperliquid (hyperliquid-python-sdk)
**Library:** `hyperliquid-python-sdk` (official SDK)
**Use Case:** Decentralized perpetual futures
**Endpoint:** `https://api.hyperliquid.xyz`

**Authentication:**
```python
credentials = {
    "private_key": "...",  # Ethereum private key
    "account_address": "0x..."
}
```

**Supported Order Types:**
- Market, Limit, Stop-Market, Stop-Limit
- Post-Only (maker-only)
- Reduce-Only (close positions)

**Rate Limits:**
- REST API: 600 requests/minute
- WebSocket: Real-time updates (no polling needed)
- Order placement: 20 orders/second

**Unique Features:**
- On-chain settlement (L1 Arbitrum)
- No KYC required
- Sub-account support
- Perpetual futures only (no spot)

### CCXT (Generic Multi-Exchange)
**Library:** `ccxt` v4.x+
**Use Case:** 100+ crypto exchanges with unified API
**Supported Exchanges:** Binance, Coinbase, Kraken, FTX, Huobi, OKX, Bitfinex, etc.

**Authentication:**
```python
import ccxt
exchange = ccxt.binance({
    'apiKey': '...',
    'secret': '...',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}  # or 'future'
})
```

**Unified Order Types:**
- Market, Limit (standardized across exchanges)
- Stop, Stop-Limit (where supported)
- Exchange-specific types via `exchange.create_order(type='exchange_specific_type')`

**Rate Limiting:**
- Automatic per-exchange rate limiting via `enableRateLimit: True`
- Respects exchange metadata for limits
- Built-in queue and delay management

**Error Handling:**
- `ccxt.NetworkError`: Connection issues, retry
- `ccxt.ExchangeError`: Exchange-specific errors
- `ccxt.InsufficientFunds`: Insufficient balance
- `ccxt.InvalidOrder`: Order validation failed

## Data API Integration

### Yahoo Finance (yfinance)
**Library:** `yfinance` 0.2.x+
**Use Case:** Free historical and live data for stocks, ETFs, forex, indices
**Cost:** Free (no API key required)

**Data Coverage:**
- Stocks: NYSE, NASDAQ, global exchanges
- ETFs: US and international
- Forex: Major currency pairs (EURUSD=X)
- Indices: S&P 500 (^GSPC), Dow Jones (^DJI)
- Commodities: Gold (GC=F), Oil (CL=F)

**Resolutions:**
- Intraday: 1m, 2m, 5m, 15m, 30m, 60m, 90m (max 60 days history)
- Daily: 1d (unlimited history)
- Weekly/Monthly: 1wk, 1mo, 3mo

**API Usage:**
```python
import yfinance as yf

# Single ticker
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="1mo", interval="1d")

# Multiple tickers
data = yf.download(
    tickers="AAPL MSFT GOOGL",
    start="2023-01-01",
    end="2023-12-31",
    interval="1d"
)
```

**Rate Limits:**
- No official rate limit, but recommended: <2000 requests/hour
- Implement 1-second delay between requests
- Yahoo may block aggressive scraping

**Data Quality:**
- Adjusted prices for splits and dividends
- Corporate actions data included
- Occasional missing bars (gaps)
- 15-20 minute delay for live data

### CCXT (Market Data)
**Library:** `ccxt` v4.x+
**Use Case:** Historical crypto OHLCV data from 100+ exchanges
**Cost:** Free (some exchanges require API key even for public data)

**Data Coverage:**
- OHLCV: All trading pairs per exchange
- Resolutions: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
- History: Varies by exchange (typically 500-1000 bars per request)

**API Usage:**
```python
import ccxt
exchange = ccxt.binance()

# Fetch OHLCV
ohlcv = exchange.fetch_ohlcv(
    symbol='BTC/USDT',
    timeframe='1h',
    since=exchange.parse8601('2023-01-01T00:00:00Z'),
    limit=1000
)
```

**Rate Limits:**
- Per-exchange (Binance: 1200 req/min, Coinbase: 10 req/sec)
- Use `exchange.enableRateLimit = True` for automatic throttling

**Data Quality:**
- Real-time data where supported
- Historical gaps for low-liquidity pairs
- Timestamp alignment varies by exchange (align to UTC)

### Optional: Polygon.io, Alpaca, Alpha Vantage
**Status:** Out of MVP scope (Epic 6)
**Use Case:** Premium data sources with higher quality and more features

**Polygon.io:**
- Stocks, options, forex, crypto
- Real-time and historical data
- Cost: $29-$399/month
- Websocket streaming

**Alpaca:**
- Commission-free stock trading
- Real-time market data
- Free for paper trading
- Cost: $0-$99/month for live data

**Alpha Vantage:**
- Stocks, forex, crypto, technical indicators
- Free tier: 5 requests/minute, 500 requests/day
- Premium: $49.99-$499/month

**Integration:** Same `BaseDataAdapter` interface, prioritize post-MVP.

## WebSocket Streaming (Epic 6)
**Purpose:** Real-time market data for live trading
**Status:** Deferred to Epic 6 (out of MVP)

**Supported Brokers:**
- Binance: `wss://stream.binance.com:9443`
- Bybit: `wss://stream.bybit.com/v5/public/spot`
- Hyperliquid: `wss://api.hyperliquid.xyz/ws`
- Interactive Brokers: via ib_async subscription

**Features:**
- Subscribe to orderbook updates (bid/ask)
- Trade stream for tick-by-tick data
- Kline (candlestick) stream for bar data
- Account updates for position changes

**Implementation:**
```python
import websockets
import json

async def subscribe_binance_kline(symbol: str, interval: str):
    uri = "wss://stream.binance.com:9443/ws"
    async with websockets.connect(uri) as ws:
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [f"{symbol.lower()}@kline_{interval}"],
            "id": 1
        }
        await ws.send(json.dumps(subscribe_msg))

        async for message in ws:
            data = json.loads(message)
            if 'k' in data:
                kline = data['k']
                # Process kline data
                yield {
                    "timestamp": kline['t'],
                    "open": Decimal(kline['o']),
                    "high": Decimal(kline['h']),
                    "low": Decimal(kline['l']),
                    "close": Decimal(kline['c']),
                    "volume": Decimal(kline['v'])
                }
```

---
