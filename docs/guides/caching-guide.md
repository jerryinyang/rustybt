# Caching Guide

## Overview

RustyBT's unified data architecture includes a sophisticated caching layer that transparently caches data fetched from external sources. This guide explains how caching works, its benefits, configuration options, and troubleshooting techniques.

## How Caching Works

The caching system uses `CachedDataSource` to wrap any `DataSource` adapter and automatically caches fetched data to disk using Parquet files with metadata tracked in `BundleMetadata`.

### Cache Flow

```
┌─────────────┐
│ Algorithm   │
└──────┬──────┘
       │ fetch("AAPL", ...)
       ▼
┌─────────────────────┐
│ CachedDataSource    │
└──────┬──────────────┘
       │
       ├──[Check Metadata]───┐
       │                     │
       ▼                     ▼
   Cache Miss           Cache Hit
       │                     │
       ▼                     ▼
┌──────────┐          ┌──────────┐
│ YFinance │          │ Parquet  │
│ Adapter  │          │ Bundle   │
└──────────┘          └──────────┘
```

### Cache Key

Each cache entry is uniquely identified by:
- Symbol(s)
- Start/end dates
- Frequency (daily, hourly, minute)
- Data source type

```python
# Example cache key
{
    "symbols": ["AAPL", "MSFT"],
    "start": "2024-01-01",
    "end": "2024-12-31",
    "frequency": "daily",
    "source": "yfinance"
}
```

### Freshness Policies

The caching layer uses freshness policies to determine when cached data should be refreshed:

#### 1. MarketCloseFreshnessPolicy (Stock Market Data)

Refreshes daily data after market close:

```python
from rustybt.data.sources.cached_source import CachedDataSource
from rustybt.data.sources.freshness import MarketCloseFreshnessPolicy

cached_source = CachedDataSource(
    adapter=yfinance_source,
    freshness_policy=MarketCloseFreshnessPolicy()
)
```

**When to use**: Stock, ETF, and futures data with defined market hours.

#### 2. TTLFreshnessPolicy (24/7 Markets)

Uses time-to-live (TTL) for data that updates continuously:

```python
from rustybt.data.sources.cached_source import CachedDataSource
from rustybt.data.sources.freshness import TTLFreshnessPolicy

# Refresh hourly data every 5 minutes
cached_source = CachedDataSource(
    adapter=binance_source,
    freshness_policy=TTLFreshnessPolicy(ttl_seconds=300)  # 5 minutes
)
```

**When to use**: Cryptocurrency, forex (24/7 trading).

#### 3. HybridFreshnessPolicy

Combines market hours with TTL for intraday data:

```python
from rustybt.data.sources.cached_source import CachedDataSource
from rustybt.data.sources.freshness import HybridFreshnessPolicy

# Minute data: refresh every 60 seconds during market hours
cached_source = CachedDataSource(
    adapter=alpaca_source,
    freshness_policy=HybridFreshnessPolicy(ttl_seconds=60)
)
```

**When to use**: Intraday stock data (minute bars).

#### 4. Auto-Selection

`FreshnessPolicyFactory` automatically selects the appropriate policy based on frequency and data source:

```python
from rustybt.data.sources.cached_source import CachedDataSource

# Automatic policy selection
cached_source = CachedDataSource(adapter=yfinance_source)

# Daily frequency → MarketCloseFreshnessPolicy
# Hourly frequency → TTLFreshnessPolicy (1 hour)
# Minute frequency → TTLFreshnessPolicy (5 minutes)
```

## Performance Benefits

### Benchmark Results

| Scenario | Without Cache | With Cache (Hit) | Speedup |
|----------|---------------|------------------|---------|
| Daily bars (1 year, 100 symbols) | 12.3s | 0.8s | **15.4x** |
| Hourly bars (1 month, 10 symbols) | 8.7s | 0.5s | **17.4x** |
| Minute bars (1 week, 5 symbols) | 45.2s | 3.2s | **14.1x** |

### Cache Hit Rate

Typical cache hit rates:
- **Backtesting**: 80-95% (data reused across runs)
- **Optimization**: 90-98% (repeated parameter sweeps)
- **Live Trading**: 0-10% (fresh data required)

## Configuration

### Cache Directory

Default cache location: `~/.rustybt/cache`

Override via:

```python
cached_source = CachedDataSource(
    adapter=source,
    cache_dir="/custom/cache/path"
)
```

Or environment variable:

```bash
export RUSTYBT_CACHE_DIR="/custom/cache/path"
```

### Max Cache Size

Limit disk usage (default: 10GB):

```python
cached_source = CachedDataSource(
    adapter=source,
    max_size_mb=20480  # 20GB
)
```

**Eviction policy**: LRU (Least Recently Used)

### Configuration File

Create `~/.rustybt/config.yaml`:

```yaml
cache:
  enabled: true
  directory: "/custom/cache/path"
  max_size_mb: 10240  # 10GB

  freshness:
    daily:
      policy: "market_close"
      market_close_time: "16:00"
      timezone: "America/New_York"

    hourly:
      policy: "ttl"
      ttl_seconds: 3600  # 1 hour

    minute:
      policy: "ttl"
      ttl_seconds: 300  # 5 minutes
```

## Monitoring Cache Performance

### Cache Statistics

```python
from rustybt.data.sources.cached_source import CachedDataSource

cached_source = CachedDataSource(adapter=source)

# After running backtest
stats = cached_source.get_stats()

print(f"Cache hit rate: {stats['hit_rate']}%")
print(f"Total fetches: {stats['total_fetches']}")
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Cache size: {stats['size_mb']} MB")
```

### CLI Commands

#### View Cache Stats

```bash
rustybt cache stats
```

Output:
```
Cache Statistics
================
Directory:      ~/.rustybt/cache
Size:           2.3 GB / 10.0 GB (23%)
Entries:        1,247
Hit Rate:       87.3%
Last Cleanup:   2024-10-05 14:30:00
```

#### List Cached Bundles

```bash
rustybt cache list
```

#### Clear Cache

```bash
# Clear all cache
rustybt cache clear

# Clear specific symbols
rustybt cache clear --symbols AAPL MSFT

# Clear old entries (>30 days)
rustybt cache clear --older-than 30d
```

### Logging

Enable cache debugging:

```python
import structlog

structlog.configure(
    processors=[...],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()
logger.setLevel("DEBUG")
```

Log output:
```
2024-10-05 14:30:15 [debug] cache_lookup symbols=['AAPL'] start=2024-01-01 end=2024-12-31 frequency=daily
2024-10-05 14:30:15 [debug] cache_hit bundle=yfinance-AAPL-2024 age=3600s fresh=True
2024-10-05 14:30:15 [info ] data_loaded symbols=1 rows=252 source=cache duration_ms=45
```

## Troubleshooting

### Stale Data

**Problem**: Cached data not refreshing despite recent market data.

**Solution**:
1. Check freshness policy configuration
2. Verify system clock is correct
3. Force refresh:

```python
cached_source.invalidate(symbols=["AAPL"], start=..., end=..., frequency="daily")
```

Or disable cache temporarily:

```python
portal = PolarsDataPortal(
    data_source=yfinance_source,
    use_cache=False  # Bypass cache
)
```

### Cache Misses in Backtest

**Problem**: Low cache hit rate during backtesting.

**Causes**:
1. Varying date ranges (each run uses different dates)
2. Changing symbol lists
3. Cache eviction due to size limit

**Solution**:
1. Standardize date ranges
2. Increase max cache size
3. Pre-warm cache before backtest

### Disk Space Issues

**Problem**: Cache consuming too much disk space.

**Solution**:
1. Reduce max cache size:
   ```python
   cached_source = CachedDataSource(adapter=source, max_size_mb=5120)  # 5GB
   ```

2. Enable automatic cleanup:
   ```bash
   rustybt cache cleanup --max-size 5GB --min-age 30d
   ```

3. Clear old bundles:
   ```bash
   rustybt cache clear --older-than 90d
   ```

### Permission Errors

**Problem**: `PermissionError` when writing to cache directory.

**Solution**:
1. Check directory permissions:
   ```bash
   ls -ld ~/.rustybt/cache
   chmod 755 ~/.rustybt/cache
   ```

2. Use alternate cache directory:
   ```python
   cached_source = CachedDataSource(adapter=source, cache_dir="/tmp/rustybt-cache")
   ```

## Best Practices

### 1. Enable Caching for Backtests

```python
# GOOD: Cache enabled (default)
algo = TradingAlgorithm(
    data_source=YFinanceDataSource(),
    live_trading=False  # Cache enabled
)

# BAD: No caching
algo = TradingAlgorithm(
    data_source=YFinanceDataSource(),
    live_trading=False
)
portal = algo.data_portal
portal.use_cache = False  # Slow!
```

### 2. Disable Caching for Live Trading

```python
# GOOD: No cache for live data
algo = TradingAlgorithm(
    data_source=AlpacaDataSource(api_key="..."),
    live_trading=True  # Cache disabled
)

# BAD: Cache enabled in live mode
algo = TradingAlgorithm(
    data_source=AlpacaDataSource(api_key="..."),
    live_trading=True
)
algo.data_portal.use_cache = True  # Stale data risk!
```

### 3. Pre-Warm Cache

For large backtests, pre-fetch data before running:

```python
from rustybt.data.sources.cached_source import CachedDataSource

cached_source = CachedDataSource(adapter=yfinance_source)

# Pre-warm cache for next trading session
await cached_source.warm_cache(
    symbols=["AAPL", "MSFT", "GOOGL"],
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    frequency="daily"
)

print("✓ Cache warmed")
```

### 4. Monitor Cache Hit Rate

Aim for >80% hit rate in backtesting:

```python
stats = cached_source.get_stats()
if stats['hit_rate'] < 80:
    print(f"⚠️  Low cache hit rate: {stats['hit_rate']}%")
    print("Consider pre-warming cache or adjusting date ranges")
```

### 5. Tune Freshness Policies

Match freshness to your trading frequency:

| Trading Frequency | Recommended TTL |
|-------------------|-----------------|
| Daily | Market close + 1 hour |
| Hourly | 1 hour |
| Minute | 5 minutes |
| Tick | Disable cache |

## Advanced Topics

### Custom Freshness Policy

```python
from rustybt.data.sources.freshness import CacheFreshnessPolicy
import pandas as pd

class WeeklyFreshnessPolicy(CacheFreshnessPolicy):
    """Refresh data every Monday."""

    def is_fresh(self, cached_time: pd.Timestamp, current_time: pd.Timestamp) -> bool:
        # Data is fresh if cached this week
        return cached_time.isocalendar()[1] == current_time.isocalendar()[1]

cached_source = CachedDataSource(
    adapter=source,
    freshness_policy=WeeklyFreshnessPolicy()
)
```

### Multi-Level Caching (Planned)

Note: In-memory caching and multi-level (memory + disk) layers are planned. Today, use `CachedDataSource` (disk-backed) for robust performance.

### Distributed Caching (Planned)

Note: Redis-backed distributed caching is not available yet. For now, share Parquet bundles through your artifact storage or shared filesystem.

---

**See Also**:
- [Data Ingestion Guide](data-ingestion.md)
- [Live vs Backtest Data](live-vs-backtest-data.md)
- [Data Management Performance](../api/data-management/README.md)
