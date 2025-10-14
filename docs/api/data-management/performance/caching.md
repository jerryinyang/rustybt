# Caching and Performance

Comprehensive guide to caching strategies and performance optimization for data operations.

## Cache System Architecture

RustyBT provides multi-level caching:

1. **Memory Cache**: Fast in-memory LRU cache
2. **Disk Cache**: Persistent on-disk cache
3. **Bundle Cache**: Cached bundle metadata
4. **History Cache**: Historical data windows

## Memory Caching

### CacheManager

```python
from rustybt.data.polars.cache_manager import CacheManager

# Configure cache
cache = CacheManager(
    max_memory_mb=2048,  # 2GB memory limit
    disk_cache_path='/path/to/cache',
    eviction_policy='lru'  # Least Recently Used
)

# Cache is used automatically by data portal and readers
```

### Manual Caching

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(asset, window):
    # Cached computation
    return compute_feature(asset, window)

# First call: computes
result1 = expensive_computation(asset, 20)

# Second call: returns cached
result2 = expensive_computation(asset, 20)  # Fast!
```

## Disk Caching

### Bundle Cache

```python
# Bundle data automatically cached
from rustybt.data.bundles import load

bundle_data = load('my_bundle')  # Cached after first load

# Cache location: ~/.rustybt/data/my_bundle/.cache/
```

### Custom Disk Cache

```python
import pickle
from pathlib import Path

class DiskCache:
    def __init__(self, cache_dir='/path/to/cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def get(self, key):
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        return None

    def set(self, key, value):
        cache_file = self.cache_dir / f"{key}.pkl"
        with open(cache_file, 'wb') as f:
            pickle.dump(value, f)

# Usage
cache = DiskCache()
data = cache.get('my_data')
if data is None:
    data = expensive_fetch()
    cache.set('my_data', data)
```

## Performance Optimization

### 1. Lazy Evaluation (Polars)

```python
import polars as pl

# Lazy frame (doesn't load data immediately)
df_lazy = pl.scan_parquet('/data/large_file.parquet')

# Chain operations (executed together)
result = (df_lazy
    .filter(pl.col('symbol') == 'AAPL')
    .select(['timestamp', 'close'])
    .tail(100)
    .collect()  # Execute all operations at once
)
```

### 2. Parallel Processing

```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

async def parallel_fetch(symbols):
    """Fetch multiple symbols in parallel."""
    with ThreadPoolExecutor(max_workers=8) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, fetch_symbol, symbol)
            for symbol in symbols
        ]
        return await asyncio.gather(*tasks)

# Fetch 100 symbols in parallel
results = await parallel_fetch(large_symbol_list)
```

### 3. Batch Operations

```python
# Bad: Individual operations
for symbol in symbols:
    df = fetch_single(symbol)  # 100 API calls

# Good: Batch operation
df = fetch_batch(symbols, batch_size=10)  # 10 API calls
```

### 4. Prefetching

```python
from rustybt.data.history_loader import DailyHistoryLoader

loader = DailyHistoryLoader(
    trading_calendar=calendar,
    reader=reader,
    prefetch=True,  # Enable prefetching
    prefetch_window=50  # Prefetch 50 bars ahead
)
```

### 5. Compression

```python
# Use efficient compression for Parquet
from rustybt.data.polars.parquet_writer import ParquetWriter

writer = ParquetWriter(
    path='/data/output.parquet',
    compression='zstd',  # Options: snappy, gzip, zstd, lz4
    compression_level=3   # Balance speed vs size
)
```

## Cache Invalidation

### Time-Based Invalidation

```python
import time
from functools import wraps

def cached_with_ttl(ttl_seconds=3600):
    """Cache with time-to-live."""
    cache = {}

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(kwargs.items()))
            now = time.time()

            if key in cache:
                value, timestamp = cache[key]
                if now - timestamp < ttl_seconds:
                    return value

            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result
        return wrapper
    return decorator

@cached_with_ttl(ttl_seconds=1800)  # 30 minutes
def fetch_data(symbol):
    return expensive_api_call(symbol)
```

### Manual Invalidation

```python
# Clear all bundle caches
from rustybt.data.bundles import clean_cache

clean_cache('my_bundle')

# Clear specific cache
cache_manager.invalidate('cache_key')

# Clear all caches
cache_manager.clear()
```

## Monitoring Performance

### Timing Operations

```python
import time

def time_operation(func):
    """Decorator to time operations."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        print(f"{func.__name__} took {duration:.2f}s")
        return result
    return wrapper

@time_operation
def fetch_large_dataset():
    return fetch_data()
```

### Cache Statistics

```python
from rustybt.data.polars.cache_manager import CacheManager

cache = CacheManager(max_memory_mb=1024)

# Get cache stats
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Total hits: {stats['hits']}")
print(f"Total misses: {stats['misses']}")
print(f"Cache size: {stats['size_mb']:.2f} MB")
```

## Best Practices

1. **Cache Hot Data**: Cache frequently accessed data
2. **Set Appropriate TTL**: Balance freshness vs performance
3. **Monitor Hit Rates**: Track cache effectiveness
4. **Use Lazy Evaluation**: Minimize memory usage
5. **Batch Operations**: Reduce API calls
6. **Compress Storage**: Use efficient formats (Parquet + zstd)
7. **Profile First**: Identify bottlenecks before optimizing

## See Also

- [Optimization Guide](optimization.md) - Advanced optimization techniques
- [Troubleshooting](troubleshooting.md) - Performance debugging
- [Data Catalog](../catalog/overview.md) - Bundle caching
