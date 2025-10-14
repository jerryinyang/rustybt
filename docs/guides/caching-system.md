# Intelligent Caching System

## Overview

RustyBT implements a two-tier intelligent caching system that dramatically accelerates backtests by storing fetched data locally. The system automatically manages cache entries, tracks backtest linkages, and provides detailed statistics.

## Architecture

### Two-Tier Cache Design

1. **Hot Cache (In-Memory)**
   - Storage: LRU cache with Polars DataFrames in memory
   - Size Limit: Configurable (default: 1GB)
   - Performance: <0.01s access time
   - Eviction: Least Recently Used (LRU)

2. **Cold Cache (Disk)**
   - Storage: Parquet files with Snappy compression
   - Size Limit: Configurable (default: 10GB)
   - Performance: <1s access time
   - Eviction: LRU, size-based, or hybrid

### Cache Flow

```
Request Data
    ↓
Check Hot Cache (in-memory)
    ↓ miss
Check Cold Cache (disk)
    ↓ miss
Fetch from Data Adapter
    ↓
Store in Hot + Cold Cache
    ↓
Return Data
```

## Usage

### Basic Usage

```python
from rustybt.data.polars.cache_manager import CacheManager

# Initialize cache manager
cache = CacheManager(
    db_path="data/bundles/quandl/metadata.db",
    cache_directory="data/bundles/quandl/cache",
    hot_cache_size_mb=1024,    # 1GB hot cache
    cold_cache_size_mb=10240,  # 10GB cold cache
    eviction_policy="lru"
)

# Generate cache key
cache_key = cache.generate_cache_key(
    symbols=["AAPL", "MSFT"],
    start_date="2023-01-01",
    end_date="2023-12-31",
    resolution="1d",
    data_source="yfinance"
)

# Check cache (returns None if miss)
df = cache.get_cached_data(cache_key)

if df is None:
    # Fetch from data source
    df = fetch_data_from_yfinance(...)

    # Store in cache with backtest linkage
    cache.put_cached_data(
        cache_key,
        df,
        dataset_id=1,
        backtest_id="backtest-001"
    )
```

### Cache Statistics

```python
# Get cache statistics
stats = cache.get_cache_statistics()

print(f"Hit Rate: {stats['hit_rate']:.2%}")
print(f"Total Size: {stats['total_size_mb']:.2f} MB")
print(f"Entry Count: {stats['entry_count']}")
print(f"Average Access Count: {stats['avg_access_count']:.2f}")

# Session statistics
print(f"Session Hits: {stats['session_stats']['hit_count']}")
print(f"Session Misses: {stats['session_stats']['miss_count']}")
print(f"Hot Cache Hits: {stats['session_stats']['hot_hits']}")
print(f"Cold Cache Hits: {stats['session_stats']['cold_hits']}")

# Query statistics for date range
stats = cache.get_cache_statistics(
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

### Cache Management

```python
# Clear specific cache entry
cache.clear_cache(cache_key="abc123def456")

# Clear all entries for a backtest
cache.clear_cache(backtest_id="backtest-001")

# Clear entire cache
cache.clear_cache()

# Record daily statistics
cache.record_daily_statistics()
```

## Configuration

### Cache Manager Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db_path` | str | Required | Path to SQLite metadata database |
| `cache_directory` | str | Required | Directory for cached Parquet files |
| `hot_cache_size_mb` | int | 1024 | Hot cache size in MB (1GB) |
| `cold_cache_size_mb` | int | 10240 | Cold cache size in MB (10GB) |
| `eviction_policy` | str | "lru" | Eviction policy: "lru", "size", "hybrid" |

### Eviction Policies

1. **LRU (Least Recently Used)**
   - Evicts entries with oldest `last_accessed` timestamp
   - Best for: Temporal access patterns (recent data accessed frequently)

2. **Size-Based**
   - Evicts largest entries first
   - Best for: Maximizing number of cache entries

3. **Hybrid**
   - Combines size-based and LRU
   - Evicts by size first, then by LRU if needed
   - Best for: General-purpose caching

## Cache Key Generation

Cache keys are deterministic SHA256 hashes (first 16 characters) of:

```python
{
    "symbols": sorted(["AAPL", "MSFT"]),  # Sorted for consistency
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "resolution": "1d",
    "data_source": "yfinance"
}
```

**Properties:**
- Deterministic: Same parameters → same cache key
- Order-independent: `["AAPL", "MSFT"]` = `["MSFT", "AAPL"]`
- Unique: Different parameters → different cache keys

## Cache Invalidation

### Checksum-Based Validation

Every cached Parquet file has a SHA256 checksum stored in metadata. On cache hit:

1. Calculate checksum of Parquet file
2. Compare with stored checksum
3. If mismatch: delete cache entry, treat as cache miss

### Manual Invalidation

```python
# Clear specific entry
cache.clear_cache(cache_key="abc123def456")

# Clear by backtest
cache.clear_cache(backtest_id="backtest-001")

# Clear all
cache.clear_cache()
```

## Performance Targets

| Cache Type | Target | Typical Performance |
|------------|--------|---------------------|
| Hot Cache Hit | <0.01s | ~0.0008s (0.8ms) |
| Cold Cache Hit | <1s | ~0.0007s (0.7ms) |
| Cache Miss + Fetch | Varies | Depends on data source |

## Database Schema

### cache_entries Table

| Column | Type | Description |
|--------|------|-------------|
| `cache_key` | TEXT | Primary key (SHA256 hash, 16 chars) |
| `dataset_id` | INTEGER | Foreign key to datasets table |
| `parquet_path` | TEXT | Relative path to cached Parquet file |
| `checksum` | TEXT | SHA256 checksum of Parquet file |
| `created_at` | INTEGER | Unix timestamp |
| `last_accessed` | INTEGER | Unix timestamp |
| `access_count` | INTEGER | Number of cache hits |
| `size_bytes` | INTEGER | File size in bytes |

### backtest_cache_links Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `backtest_id` | TEXT | User-provided backtest identifier |
| `cache_key` | TEXT | Foreign key to cache_entries |
| `linked_at` | INTEGER | Unix timestamp |

### cache_statistics Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `stat_date` | INTEGER | Unix timestamp (day granularity) |
| `hit_count` | INTEGER | Number of cache hits |
| `miss_count` | INTEGER | Number of cache misses |
| `total_size_mb` | REAL | Total cache size in MB |

## Backtest Linkage

Every cache entry can be linked to one or more backtests:

```python
# Store data with backtest linkage
cache.put_cached_data(
    cache_key,
    df,
    dataset_id=1,
    backtest_id="backtest-001"
)

# Query which backtests used specific data
import sqlalchemy as sa
from sqlalchemy.orm import Session

with Session(cache.metadata_catalog.engine) as session:
    stmt = sa.select(cache.metadata_catalog.backtest_cache_links).where(
        cache.metadata_catalog.backtest_cache_links.c.cache_key == cache_key
    )
    results = session.execute(stmt).fetchall()

    for row in results:
        print(f"Backtest: {row.backtest_id}, Linked: {row.linked_at}")
```

## Troubleshooting

### Cache Miss When Expected Hit

**Symptoms:** Data is fetched from source even though it should be cached.

**Possible Causes:**
1. Cache entry evicted due to size limit
2. Checksum mismatch (corrupted file)
3. Cache key parameters don't match exactly

**Solutions:**
```python
# Check if cache entry exists
cache_entry = cache.lookup_cache(cache_key)
if cache_entry is None:
    print("Cache entry not found (miss or evicted)")
else:
    print(f"Cache entry found: {cache_entry}")

# Increase cache size limits
cache.cold_cache_size_mb = 20480  # 20GB
```

### Slow Cache Hits

**Symptoms:** Cache hits take >1 second.

**Possible Causes:**
1. Cold cache access (disk I/O)
2. Large Parquet files
3. Disk performance issues

**Solutions:**
```python
# Check cache statistics
stats = cache.get_cache_statistics()
print(f"Hot Hits: {stats['session_stats']['hot_hits']}")
print(f"Cold Hits: {stats['session_stats']['cold_hits']}")

# If mostly cold hits, increase hot cache size
cache.hot_cache = LRUCache(max_size_bytes=2 * 1024 * 1024 * 1024)  # 2GB
```

### Checksum Mismatch Errors

**Symptoms:** Logs show `cache_checksum_mismatch` errors.

**Possible Causes:**
1. File corruption
2. Manual file modification
3. Filesystem issues

**Solutions:**
```python
# Clear corrupted entries (automatic on mismatch)
# Or manually clear entire cache
cache.clear_cache()

# Re-fetch data
df = fetch_data_from_source(...)
cache.put_cached_data(cache_key, df, dataset_id)
```

### Cache Size Grows Unbounded

**Symptoms:** Cache directory grows beyond configured limit.

**Possible Causes:**
1. Eviction not triggered
2. Many large DataFrames

**Solutions:**
```python
# Manually trigger eviction
cache._check_cold_cache_eviction()

# Check total size
total_size_mb = cache._get_total_cache_size_mb()
print(f"Total Cache Size: {total_size_mb:.2f} MB")

# Adjust eviction policy
cache.eviction_policy = "size"  # Evict largest entries first
```

## Best Practices

1. **Set Appropriate Cache Sizes**
   - Hot cache: 10-20% of available RAM
   - Cold cache: Based on disk space availability

2. **Use Backtest Linkage**
   - Always provide `backtest_id` for traceability
   - Makes it easy to clear cache per backtest

3. **Monitor Cache Statistics**
   - Track hit rate to optimize cache size
   - Record daily statistics for historical analysis

4. **Choose Right Eviction Policy**
   - LRU: For temporal access patterns
   - Size: For maximizing cache entries
   - Hybrid: For general use

5. **Regular Maintenance**
   - Clear old backtests periodically
   - Monitor disk space usage
   - Review cache statistics

## Examples

### Example 1: Basic Backtest Caching

```python
from rustybt.data.polars.cache_manager import CacheManager

# Initialize cache
cache = CacheManager(
    db_path="data/metadata.db",
    cache_directory="data/cache"
)

# Backtest loop
for backtest_id in ["bt-001", "bt-002", "bt-003"]:
    symbols = ["AAPL", "MSFT", "GOOGL"]

    for symbol in symbols:
        # Generate cache key
        cache_key = cache.generate_cache_key(
            symbols=[symbol],
            start_date="2023-01-01",
            end_date="2023-12-31",
            resolution="1d",
            data_source="yfinance"
        )

        # Check cache
        df = cache.get_cached_data(cache_key)

        if df is None:
            # Cache miss: fetch from source
            df = yfinance.download(symbol, start="2023-01-01", end="2023-12-31")

            # Store in cache
            cache.put_cached_data(
                cache_key,
                df,
                dataset_id=1,
                backtest_id=backtest_id
            )

        # Run backtest with df
        run_backtest(df, backtest_id)

# Print statistics
stats = cache.get_cache_statistics()
print(f"Cache Hit Rate: {stats['hit_rate']:.2%}")
```

### Example 2: Multi-Resolution Caching

```python
# Cache different resolutions of same symbol
resolutions = ["1m", "5m", "1h", "1d"]
symbol = "AAPL"

for resolution in resolutions:
    cache_key = cache.generate_cache_key(
        symbols=[symbol],
        start_date="2023-01-01",
        end_date="2023-01-31",
        resolution=resolution,
        data_source="yfinance"
    )

    df = cache.get_cached_data(cache_key)

    if df is None:
        # Fetch and aggregate to resolution
        df = fetch_and_resample(symbol, resolution)
        cache.put_cached_data(cache_key, df, dataset_id=1)
```

### Example 3: Cache Statistics Dashboard

```python
import time

# Run backtests
for i in range(100):
    cache_key = cache.generate_cache_key(
        symbols=["AAPL"],
        start_date="2023-01-01",
        end_date="2023-12-31",
        resolution="1d",
        data_source="yfinance"
    )

    start = time.time()
    df = cache.get_cached_data(cache_key)
    latency = (time.time() - start) * 1000  # ms

    print(f"Backtest {i+1}: Latency = {latency:.2f}ms")

# Record statistics
cache.record_daily_statistics()

# Print dashboard
stats = cache.get_cache_statistics()
print("\n=== Cache Statistics ===")
print(f"Hit Rate: {stats['hit_rate']:.2%}")
print(f"Total Hits: {stats['hit_count']}")
print(f"Total Misses: {stats['miss_count']}")
print(f"Cache Size: {stats['total_size_mb']:.2f} MB")
print(f"Entry Count: {stats['entry_count']}")
print(f"Avg Access Count: {stats['avg_access_count']:.2f}")
print("\n=== Session Statistics ===")
print(f"Hot Cache Hits: {stats['session_stats']['hot_hits']}")
print(f"Cold Cache Hits: {stats['session_stats']['cold_hits']}")
```

## See Also

- [Creating Data Adapters](creating-data-adapters.md)
- [CSV Data Import](csv-data-import.md)
