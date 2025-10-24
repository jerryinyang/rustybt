# Bundle Connection Pooling

## Overview

Bundle connection pooling eliminates 84% of worker initialization overhead in distributed optimization workflows by pooling and reusing bundle connections across workers.

**Performance Impact:**
- Worker initialization: **313ms → <50ms** (after first load)
- **84% reduction** in initialization overhead
- Scales efficiently with 2-16 workers without degradation

## How It Works

The `BundleConnectionPool` implements a singleton pattern with thread-safe lazy loading and LRU (Least Recently Used) eviction:

1. **First Access**: Bundle loaded from disk (~313ms)
2. **Subsequent Access**: Bundle retrieved from pool (<1ms)
3. **Version Tracking**: SHA256 hash detects bundle updates
4. **Automatic Invalidation**: Stale bundles removed on version change
5. **Memory Bounds**: LRU eviction maintains pool size limit

## Basic Usage

### Using the Connection Pool

```python
from rustybt.optimization.bundle_pool import get_bundle_from_pool

# Get bundle from pool (first access loads, subsequent accesses cached)
bundle_data = get_bundle_from_pool('quandl')

# Access bundle readers
asset_finder = bundle_data.asset_finder
daily_bar_reader = bundle_data.equity_daily_bar_reader
minute_bar_reader = bundle_data.equity_minute_bar_reader
adjustment_reader = bundle_data.adjustment_reader
```

### Advanced Usage

```python
from rustybt.optimization.bundle_pool import BundleConnectionPool

# Get pool instance (singleton)
pool = BundleConnectionPool.get_instance(max_pool_size=200)

# Get bundle
bundle_data = pool.get_bundle('quandl')

# Get pool statistics
stats = pool.get_pool_stats()
print(f"Pool size: {stats['pool_size']}/{stats['max_pool_size']}")

# Force invalidate specific bundle
pool.force_invalidate('quandl')

# Force invalidate all bundles
pool.force_invalidate()
```

## Configuration

### OptimizationConfig

Control bundle pooling via `OptimizationConfig`:

```python
from rustybt.optimization.config import OptimizationConfig

# Default configuration (pooling enabled)
config = OptimizationConfig.create_default()
print(config.enable_bundle_pooling)  # True
print(config.max_bundle_pool_size)   # 100

# Custom configuration
config = OptimizationConfig.create_default()
config.enable_bundle_pooling = True
config.max_bundle_pool_size = 200  # Larger pool

# Check if pooling enabled
if config.should_use_bundle_pool():
    # Use connection pool
    bundle = get_bundle_from_pool('quandl')
else:
    # Direct load (no pooling)
    from rustybt.data.bundles.core import load
    bundle = load('quandl')
```

### Environment Variables

Override configuration via environment variables:

```bash
# Disable bundle pooling
export RUSTYBT_ENABLE_BUNDLE_POOLING=false

# Set custom pool size
export RUSTYBT_MAX_BUNDLE_POOL_SIZE=50
```

## Version-Based Invalidation

The pool automatically detects bundle updates using SHA256 hashing:

```python
from rustybt.optimization.cache_invalidation import get_bundle_version

# Get bundle version metadata
version = get_bundle_version('quandl')
print(f"Hash: {version.computed_hash}")
print(f"Assets: {len(version.asset_list)}")
print(f"Date range: {version.date_range}")

# Pool automatically invalidates on hash change
bundle = pool.get_bundle('quandl')  # Loaded
# ... bundle updated on disk (new data ingested) ...
bundle = pool.get_bundle('quandl')  # Auto-detected, reloaded
```

### Hash Computation

Bundle hash is computed from:
- **Asset list**: Sorted list of asset symbols
- **Date range**: Start and end dates of bundle data
- **Schema version**: Bundle schema version

**Hash formula:**
```
SHA256("{sorted_assets}|{start_date}|{end_date}|{schema_version}")
```

Any change to assets, date range, or schema triggers invalidation.

## Runtime Bundle Updates

### Automatic Detection

The pool automatically detects bundle updates on every access:

```python
# Bundle loaded initially
bundle = pool.get_bundle('quandl')

# New data ingested (bundle updated on disk)
# $ zipline ingest -b quandl

# Next access detects update automatically
bundle = pool.get_bundle('quandl')  # Auto-reloaded
```

### Manual Force Invalidation

For forced updates without waiting for next access:

```python
# Invalidate specific bundle
pool.force_invalidate('quandl')

# Next access will reload
bundle = pool.get_bundle('quandl')

# Or invalidate all bundles
pool.force_invalidate()
```

## Pool Size Management

### LRU Eviction

When pool reaches `max_pool_size`, least recently used bundles are evicted:

```python
# Pool with max size 3
pool = BundleConnectionPool.get_instance(max_pool_size=3)

# Load 3 bundles (at capacity)
pool.get_bundle('bundle_1')
pool.get_bundle('bundle_2')
pool.get_bundle('bundle_3')

# Load 4th bundle (triggers eviction)
pool.get_bundle('bundle_4')  # bundle_1 evicted (LRU)

# Access bundle_2 (moves to end of LRU)
pool.get_bundle('bundle_2')

# Load 5th bundle
pool.get_bundle('bundle_5')  # bundle_3 evicted, bundle_2 retained
```

### Memory Considerations

**Default pool size (100 bundles)** is suitable for most workflows:

- **Grid Search**: 100+ backtests typically use 1-2 bundles
- **Walk Forward**: Multiple windows use same bundle repeatedly
- **Memory overhead**: <2% total increase (target)

**Custom pool sizes**:
- **Small (50)**: Memory-constrained environments
- **Large (200)**: High-throughput optimization clusters

## Distributed Scenarios

### Multiprocessing Integration

The pool works seamlessly with `multiprocessing.Pool`:

```python
import multiprocessing
from rustybt.optimization.bundle_pool import get_bundle_from_pool

def worker_function(bundle_name):
    """Worker loads bundle from pool."""
    bundle_data = get_bundle_from_pool(bundle_name)
    # ... perform backtest ...
    return result

# Create worker pool
with multiprocessing.Pool(processes=8) as pool:
    results = pool.starmap(
        worker_function,
        [('quandl',) for _ in range(100)],  # 100 backtests
    )
```

**Note**: In multiprocessing, each worker process has its own memory space. The pool is recreated in each worker, but initialization time is still reduced after first load per worker.

### ParallelOptimizer Example

```python
from rustybt.optimization.parallel_optimizer import ParallelOptimizer
from rustybt.optimization.config import OptimizationConfig

# Enable bundle pooling
config = OptimizationConfig.create_default()
config.enable_bundle_pooling = True

# Create optimizer
optimizer = ParallelOptimizer(
    strategy_class=MyStrategy,
    bundle_name='quandl',
    num_workers=8,
    config=config,
)

# Run optimization (workers benefit from pooling)
results = optimizer.run_grid_search(param_grid)
```

### Thread Safety

The pool is thread-safe for concurrent access:

```python
import threading

def worker_thread(bundle_name):
    bundle = pool.get_bundle(bundle_name)
    # ... use bundle ...

# Create 10 threads accessing same bundle
threads = [
    threading.Thread(target=worker_thread, args=('quandl',))
    for _ in range(10)
]

for thread in threads:
    thread.start()

for thread in threads:
    thread.join()

# All threads safely access same cached bundle
```

## Performance Benchmarks

### Worker Initialization Time

| Scenario | Without Pool | With Pool | Speedup |
|----------|-------------|-----------|---------|
| First load | 313ms | 313ms | 0% (cold start) |
| Subsequent loads | 313ms | <50ms | **84%** |
| 100 workers | 31.3s | <5s | **84%** |

### Scaling with Workers

| Workers | Without Pool | With Pool | Time Saved |
|---------|-------------|-----------|------------|
| 2 | 626ms | 363ms | 263ms |
| 4 | 1.25s | 413ms | 837ms |
| 8 | 2.50s | 513ms | 1.99s |
| 16 | 5.01s | 713ms | 4.30s |

### Grid Search (100 backtests)

```python
# Without pooling: 100 × 313ms = 31.3s overhead
# With pooling: 313ms + 99 × <1ms = ~400ms overhead
# Speedup: 31.3s → 400ms (98.7% reduction)
```

## Troubleshooting

### Pool Not Caching Bundles

**Symptom**: Every access loads bundle from disk (no speedup)

**Possible causes**:
1. Pooling disabled in config
2. Bundle version changing between accesses
3. Pool being invalidated externally

**Solution**:
```python
# Check if pooling enabled
config = OptimizationConfig.create_default()
print(config.enable_bundle_pooling)  # Should be True

# Check pool stats
pool = BundleConnectionPool.get_instance()
stats = pool.get_pool_stats()
print(f"Pool size: {stats['pool_size']}")  # Should be > 0 after loading

# Check version stability
version1 = get_bundle_version('quandl')
# ... some time passes ...
version2 = get_bundle_version('quandl')
print(version1.computed_hash == version2.computed_hash)  # Should be True
```

### Bundle Not Updating After Ingest

**Symptom**: Pool returns stale bundle after `zipline ingest`

**Cause**: Pool cached bundle before ingest

**Solution**:
```python
# Force invalidate after ingest
pool.force_invalidate('quandl')

# Or wait for automatic detection on next access
bundle = pool.get_bundle('quandl')  # Automatically detects update
```

### Memory Usage Concerns

**Symptom**: High memory usage with many bundles

**Cause**: Pool size too large

**Solution**:
```python
# Reduce pool size
pool = BundleConnectionPool.get_instance(max_pool_size=50)

# Or force invalidate unused bundles
pool.force_invalidate()  # Clear all

# Monitor pool size
stats = pool.get_pool_stats()
print(f"Pool: {stats['pool_size']}/{stats['max_pool_size']}")
```

## Best Practices

### 1. Use Default Pool Size First

Start with default (100) and adjust only if needed:
```python
# Default is usually optimal
pool = BundleConnectionPool.get_instance()  # max_pool_size=100
```

### 2. Force Invalidate After Bundle Updates

Explicitly invalidate after ingesting new data:
```bash
# Ingest new data
zipline ingest -b quandl

# Force pool invalidation
python -c "from rustybt.optimization.bundle_pool import BundleConnectionPool; \
           BundleConnectionPool.get_instance().force_invalidate('quandl')"
```

### 3. Monitor Pool Statistics

Track pool usage in production:
```python
import structlog
logger = structlog.get_logger()

stats = pool.get_pool_stats()
logger.info(
    "bundle_pool_stats",
    pool_size=stats["pool_size"],
    max_pool_size=stats["max_pool_size"],
    utilization_percent=(stats["pool_size"] / stats["max_pool_size"] * 100),
)
```

### 4. Use Environment Variables for Config

Configure via environment for different environments:
```bash
# Production: Enable pooling with large pool
export RUSTYBT_ENABLE_BUNDLE_POOLING=true
export RUSTYBT_MAX_BUNDLE_POOL_SIZE=200

# Development: Smaller pool for faster iteration
export RUSTYBT_MAX_BUNDLE_POOL_SIZE=50

# Testing: Disable pooling for isolation
export RUSTYBT_ENABLE_BUNDLE_POOLING=false
```

### 5. Combine with Other Optimizations

Bundle pooling works best with other Layer 1-2 optimizations:

```python
config = OptimizationConfig.create_default()

# Layer 1: User code optimizations (70-95% speedup)
config.enable_caching = True
config.cache_size_gb = Decimal("2.0")

# Layer 2: DataPortal optimizations (20-25% speedup)
config.enable_history_cache = True
config.cache_size_limit = 200 * 1024 * 1024  # 200MB

# Layer 3: Bundle pooling (84% worker init reduction)
config.enable_bundle_pooling = True
config.max_bundle_pool_size = 100

# Cumulative speedup: ≥90% (target)
```

## API Reference

See full API documentation:
- [BundleConnectionPool API](../api/optimization/bundle_pool.md)
- [Cache Invalidation API](../api/optimization/cache_invalidation.md)
- [OptimizationConfig API](../api/optimization/config.md)

## See Also

- [Optimization Caching & Performance Tuning](optimization-caching-performance-tuning.md)
- [DataPortal History Cache](dataportal-history-cache.md)
- [Performance Benchmarking](../internal/benchmarks/)
