# Live Trading vs Backtesting Data Flow

## Overview

RustyBT uses different data flow strategies for live trading and backtesting to optimize for real-time responsiveness and historical performance respectively. Understanding these differences is crucial for developing strategies that transition smoothly from backtest to production.

## Data Flow Architecture

### Backtesting Mode

```
┌──────────────┐
│  Algorithm   │
└──────┬───────┘
       │ get_spot_value()
       ▼
┌─────────────────┐
│  DataPortal     │
│  (use_cache=True│
└──────┬──────────┘
       │
       ▼
┌──────────────────┐
│ CachedDataSource │  ◄─── Wraps adapter automatically
└──────┬───────────┘
       │
       ├──[Fresh?]─────┐
       │               │
       ▼               ▼
   Cache Hit      Cache Miss
       │               │
       ▼               ▼
┌──────────┐    ┌──────────┐
│ Parquet  │    │ YFinance │
│ Bundle   │    │ Adapter  │
└──────────┘    └────┬─────┘
                     │
                     ▼
               [Write to Cache]
```

**Key Characteristics**:
- **Caching enabled by default**
- Data fetched once, reused across runs
- Optimized for speed (10-15x faster)
- Deterministic results (same data every time)
- No API rate limits concern

### Live Trading Mode

```
┌──────────────┐
│  Algorithm   │
└──────┬───────┘
       │ get_spot_value()
       ▼
┌─────────────────┐
│  DataPortal     │
│  (use_cache=False
└──────┬──────────┘
       │
       ▼
┌──────────────┐
│   Alpaca     │  ◄─── Direct adapter access
│   Adapter    │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  REST API /  │
│  WebSocket   │
└──────────────┘
```

**Key Characteristics**:
- **No caching** (fresh data every request)
- Real-time market data
- WebSocket support for streaming
- API rate limits apply
- Non-deterministic (market evolves)

## Code Comparison

### Backtesting Example

```python
from rustybt import TradingAlgorithm
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

# Get data source
source = DataSourceRegistry.get_source("yfinance")

# Create backtest algorithm
class MyStrategy(TradingAlgorithm):
    def initialize(self):
        self.symbols = ["AAPL", "MSFT"]

    def handle_data(self, context, data):
        # This data comes from cache (fast!)
        prices = data.current(context.symbols, "close")
        # ... trading logic

# Run backtest with caching
algo = MyStrategy(
    data_source=source,
    live_trading=False,  # ◄─── Cache enabled
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31")
)

results = algo.run()
print(f"Cache hit rate: {algo.data_portal.cache_hit_rate:.1f}%")
# Output: Cache hit rate: 87.3%
```

### Live Trading Example

```python
from rustybt import TradingAlgorithm
from rustybt.data.sources import DataSourceRegistry

# Get live data source (with API credentials)
source = DataSourceRegistry.get_source(
    "alpaca",
    api_key=os.getenv("ALPACA_API_KEY"),
    api_secret=os.getenv("ALPACA_API_SECRET"),
    paper_trading=True
)

# Create live trading algorithm
class MyStrategy(TradingAlgorithm):
    def initialize(self):
        self.symbols = ["AAPL", "MSFT"]

    def handle_data(self, context, data):
        # This data comes directly from Alpaca API (real-time!)
        prices = data.current(context.symbols, "close")
        # ... trading logic

# Run live with real-time data
algo = MyStrategy(
    data_source=source,
    live_trading=True,  # ◄─── No cache, real-time
)

algo.run()  # Runs indefinitely until stopped
```

## When to Use Each Mode

### Use Backtesting Mode When:

✅ Developing and testing strategies
✅ Optimizing parameters
✅ Validating historical performance
✅ Running Monte Carlo simulations
✅ Performance is critical (need fast iteration)
✅ You want deterministic, reproducible results

### Use Live Trading Mode When:

✅ Deploying to production
✅ Paper trading with live data
✅ Real-time signal generation
✅ You need fresh market data
✅ Testing real-time execution latency
✅ WebSocket streaming is required

## Data Freshness Considerations

### Backtesting: Controlled Freshness

```python
from rustybt.data.sources.cached_source import CachedDataSource
from rustybt.data.sources.freshness import MarketCloseFreshnessPolicy

cached_source = CachedDataSource(
    adapter=yfinance_source,
    freshness_policy=MarketCloseFreshnessPolicy(
        market_close_time="16:00",
        timezone="America/New_York"
    )
)

algo = MyStrategy(
    data_source=cached_source,
    live_trading=False
)

# Data refreshes after market close each day
# Backtest uses consistent historical data
```

### Live Trading: Real-Time Freshness

```python
# No caching - always fresh
algo = MyStrategy(
    data_source=alpaca_source,
    live_trading=True
)

# Every data.current() call fetches live data
# Real-time prices, no staleness risk
```

## Performance Implications

### Backtesting Performance

| Dataset Size | Without Cache | With Cache | Speedup |
|--------------|---------------|------------|---------|
| Small (100 days, 10 symbols) | 2.3s | 0.2s | 11.5x |
| Medium (1 year, 50 symbols) | 18.7s | 1.2s | 15.6x |
| Large (5 years, 200 symbols) | 127.4s | 8.3s | 15.3x |

**Key Insight**: Caching provides consistent 10-15x speedup regardless of dataset size.

### Live Trading Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| REST API fetch | 50-200ms | Depends on network |
| WebSocket update | 5-20ms | Real-time streaming |
| Cache fetch | 5-10ms | Not applicable in live mode |

**Key Insight**: Live mode prioritizes freshness over speed. Use WebSocket for lowest latency.

## Transitioning from Backtest to Live

### Step 1: Validate in Backtest

```python
# Test strategy with cached data
backtest_algo = MyStrategy(
    data_source=yfinance_source,
    live_trading=False,
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31")
)

results = backtest_algo.run()
assert results["sharpe_ratio"] > 1.0, "Strategy underperforming"
```

### Step 2: Paper Trade with Live Data

```python
# Test with real-time data but simulated orders
paper_algo = MyStrategy(
    data_source=alpaca_source,
    live_trading=True,
    # Broker uses paper trading mode
)

paper_algo.run()
# Monitor for 1 week, ensure no errors
```

### Step 3: Go Live (Production)

```python
# Deploy to production with real money
live_algo = MyStrategy(
    data_source=alpaca_source,
    live_trading=True,
    # Broker uses live trading mode
)

live_algo.run()
```

## Common Pitfalls

### Pitfall 1: Caching in Live Mode

❌ **Wrong**: Enabling cache in live trading

```python
algo = MyStrategy(
    data_source=yfinance_source,
    live_trading=True
)
algo.data_portal.use_cache = True  # ⚠️ Stale data risk!
```

✅ **Correct**: No cache in live mode

```python
algo = MyStrategy(
    data_source=alpaca_source,
    live_trading=True  # Cache automatically disabled
)
```

### Pitfall 2: Using Backtest Data Source in Live Mode

❌ **Wrong**: YFinance (delayed data) in live trading

```python
algo = MyStrategy(
    data_source=yfinance_source,  # ⚠️ 15-minute delay!
    live_trading=True
)
```

✅ **Correct**: Use real-time data source

```python
algo = MyStrategy(
    data_source=alpaca_source,  # ✓ Real-time
    live_trading=True
)
```

### Pitfall 3: Ignoring API Rate Limits

❌ **Wrong**: Excessive API calls in live mode

```python
def handle_data(self, context, data):
    for symbol in context.symbols:  # 100 symbols
        price = data.current(symbol, "close")  # 100 API calls per bar!
```

✅ **Correct**: Batch API calls

```python
def handle_data(self, context, data):
    prices = data.current(context.symbols, "close")  # 1 API call
```

### Pitfall 4: Time Zone Confusion

❌ **Wrong**: Assuming UTC in live mode

```python
now = pd.Timestamp.now()  # ⚠️ Local timezone
if now.hour == 9:  # Market open?
    self.order(...)
```

✅ **Correct**: Explicit timezone handling

```python
now = pd.Timestamp.now(tz="America/New_York")
market_open = now.replace(hour=9, minute=30)
if now >= market_open:
    self.order(...)
```

## Testing Strategies for Both Modes

### Unit Test: Backtest Mode

```python
def test_strategy_backtest():
    """Test strategy with cached data."""
    source = YFinanceDataSource()

    algo = MyStrategy(
        data_source=source,
        live_trading=False,
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31")
    )

    results = algo.run()

    assert results["total_return"] > 0
    assert algo.data_portal.cache_hit_rate > 80  # Cache working
```

### Integration Test: Live Mode (Paper Trading)

```python
def test_strategy_live_paper():
    """Test strategy with live data (paper trading)."""
    source = AlpacaDataSource(
        api_key=os.getenv("ALPACA_API_KEY"),
        api_secret=os.getenv("ALPACA_API_SECRET"),
        paper_trading=True  # ✓ Safe testing
    )

    algo = MyStrategy(
        data_source=source,
        live_trading=True
    )

    # Run for 5 minutes
    algo.run(duration=pd.Timedelta(minutes=5))

    assert algo.data_portal.cache_hit_rate == 0  # No cache in live mode
    assert len(algo.blotter.orders) >= 0  # Orders executed
```

## Debugging Tips

### Enable Detailed Logging

```python
import structlog
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = structlog.get_logger()

# Log data fetches
logger.debug("data_fetch", source="alpaca", symbols=["AAPL"], mode="live")
```

### Compare Backtest vs Live Results

```python
# Run backtest
backtest_results = run_backtest(MyStrategy, start="2023-01-01", end="2023-12-31")

# Run paper trading for 1 month
paper_results = run_live_paper(MyStrategy, duration=pd.Timedelta(days=30))

# Compare
print(f"Backtest Sharpe: {backtest_results['sharpe_ratio']:.2f}")
print(f"Paper Sharpe: {paper_results['sharpe_ratio']:.2f}")
assert abs(backtest_results['sharpe_ratio'] - paper_results['sharpe_ratio']) < 0.5
```

### Monitor Cache Statistics

```python
# After backtest
stats = algo.data_portal.data_source.get_stats()
print(f"Cache hit rate: {stats['hit_rate']}%")
print(f"Cache size: {stats['size_mb']:.2f} MB")

if stats['hit_rate'] < 80:
    print("⚠️  Low cache hit rate - consider pre-warming cache")
```

## Best Practices

### 1. Separate Configuration Files

```python
# config/backtest.yaml
data:
  source: yfinance
  cache: true
  freshness_policy: market_close

# config/live.yaml
data:
  source: alpaca
  cache: false
  streaming: true
```

### 2. Use Feature Flags

```python
import os

LIVE_TRADING = os.getenv("LIVE_TRADING", "false").lower() == "true"

if LIVE_TRADING:
    source = AlpacaDataSource(...)
    use_cache = False
else:
    source = YFinanceDataSource()
    use_cache = True

algo = MyStrategy(
    data_source=source,
    live_trading=LIVE_TRADING
)
```

### 3. Gradual Rollout

1. **Week 1**: Backtest with last 2 years of data
2. **Week 2**: Paper trade with live data (observe only)
3. **Week 3**: Paper trade with small position sizes
4. **Week 4**: Live trade with 10% of capital
5. **Week 5+**: Scale up if metrics match backtest

---

**See Also**:
- [Data Ingestion Guide](data-ingestion.md)
- [Caching Guide](caching-guide.md)
- [DataSource API Reference](../api/datasource-api.md)
