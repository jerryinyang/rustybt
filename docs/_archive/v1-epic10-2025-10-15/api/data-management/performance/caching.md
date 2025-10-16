# Caching and Performance

Comprehensive guide to caching strategies and performance optimization for data operations.

## Cache System Architecture

RustyBT provides multi-level caching:

1. **Memory Cache**: Fast in-memory LRU cache
2. **Disk Cache**: Persistent on-disk cache
3. **Bundle Cache**: Cached bundle metadata
4. **History Cache**: Historical data windows

## Memory Caching

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
- [Data Catalog](../catalog/bundles.md) - Bundle caching
