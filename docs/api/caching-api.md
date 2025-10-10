# Caching API Reference

## CachedDataSource

Wraps any `DataSource` with transparent caching to Parquet bundles.

```python
from rustybt.data.sources import CachedDataSource, YFinanceDataSource

source = YFinanceDataSource()

cached = CachedDataSource(
    adapter=source,
    cache_dir="~/.rustybt/cache",  # Default
    max_size_mb=10240,  # 10GB default
    freshness_policy=None  # Auto-select based on frequency
)

# Fetch with caching
df = await cached.fetch(
    symbols=["AAPL"],
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    frequency="daily"
)

# Get cache statistics
stats = cached.get_stats()
print(f"Hit rate: {stats['hit_rate']}%")
```

## Freshness Policies

### MarketCloseFreshnessPolicy

Refreshes daily data after market close.

```python
from rustybt.data.sources import MarketCloseFreshnessPolicy

policy = MarketCloseFreshnessPolicy(
    market_close_time="16:00",
    timezone="America/New_York"
)
```

### TTLFreshnessPolicy

Time-to-live based freshness for 24/7 markets.

```python
from rustybt.data.sources import TTLFreshnessPolicy

policy = TTLFreshnessPolicy(
    ttl_seconds=3600  # 1 hour
)
```

### HybridFreshnessPolicy

Combines market hours with TTL.

```python
from rustybt.data.sources import HybridFreshnessPolicy

policy = HybridFreshnessPolicy(
    market_close_time="16:00",
    timezone="America/New_York",
    ttl_seconds=300  # 5 minutes during market hours
)
```

---

**See Also**:
- [Caching Guide](../guides/caching-guide.md)
- [DataSource API](datasource-api.md)
