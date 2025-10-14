# Troubleshooting Guide

Common data management issues and solutions.

## Performance Issues

### Slow Data Loading

**Symptom**: Bundle loading takes too long

**Solutions**:
```python
# 1. Check file format (use Parquet, not HDF5/bcolz)
# 2. Enable caching
cache = CacheManager(max_memory_mb=2048)

# 3. Use lazy evaluation
df = pl.scan_parquet('data.parquet').filter(...).collect()

# 4. Reduce date range
data = portal.get_history_window(bar_count=20)  # Not 1000
```

### High Memory Usage

**Symptom**: Process using excessive memory

**Solutions**:
```python
# 1. Process in chunks
for chunk in chunks(data, size=10000):
    process(chunk)

# 2. Select only needed columns
df = pl.read_parquet('data.parquet', columns=['close'])

# 3. Use lazy evaluation
df_lazy = pl.scan_parquet('data.parquet')
```

## Data Quality Issues

### Missing Data

**Symptom**: Gaps in historical data

**Solutions**:
```python
# 1. Check metadata
metadata = BundleMetadata.get('my_bundle')
print(f"Missing days: {metadata['missing_days_count']}")
print(f"Gaps: {metadata.get('missing_days_list', [])}")

# 2. Re-ingest data
ingest('my_bundle', show_progress=True)

# 3. Use different adapter
adapter = CCXTAdapter(exchange_id='binance')  # More reliable
```

### OHLCV Violations

**Symptom**: Data fails validation (high > low violations, etc.)

**Solutions**:
```python
# 1. Check source data quality
metadata = BundleMetadata.get('my_bundle')
print(f"Violations: {metadata['ohlcv_violations']}")

# 2. Use validated adapter
adapter = YFinanceAdapter()  # More reliable for stocks

# 3. Apply cleaning
df_cleaned = df.filter(
    (pl.col('high') >= pl.col('low')) &
    (pl.col('high') >= pl.col('open')) &
    (pl.col('high') >= pl.col('close'))
)
```

## Bundle Issues

### Bundle Not Found

**Symptom**: `BundleNotFoundError`

**Solutions**:
```python
# 1. List available bundles
from rustybt.data.bundles import bundles, register, ingest
print(list(bundles.keys()))

# 2. Register bundle
register('my_bundle', ...)

# 3. Ingest bundle
ingest('my_bundle')
```

### Stale Cache

**Symptom**: Old data being returned

**Solutions**:
```python
# 1. Clear cache
from rustybt.data.bundles import clean_cache
clean_cache('my_bundle')

# 2. Re-ingest
ingest('my_bundle', keep_last=1)
```

## Adapter Issues

### Rate Limit Errors

**Symptom**: `RateLimitError` exceptions

**Solutions**:
```python
# 1. Increase delay between requests
adapter = YFinanceAdapter(request_delay=2.0)

# 2. Implement retry logic
from rustybt.data.adapters.base import RateLimitError
import time

try:
    df = await adapter.fetch(...)
except RateLimitError as e:
    time.sleep(60)
    df = await adapter.fetch(...)
```

### Network Errors

**Symptom**: `NetworkError` exceptions

**Solutions**:
```python
# 1. Check internet connection
# 2. Use exponential backoff
# 3. Try different adapter/exchange
adapter = CCXTAdapter(exchange_id='coinbase')  # Alternative
```

## Getting Help

1. **Check Logs**: Enable debug logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **Metadata Inspection**: Check bundle metadata
```python
metadata = BundleMetadata.get('my_bundle')
print(metadata)
```

3. **Community**: Ask on GitHub Discussions
4. **Bug Reports**: File issue on GitHub

## See Also

- [Caching](caching.md) - Cache configuration
- [Optimization](optimization.md) - Performance tuning
- [Data Catalog](../catalog/overview.md) - Bundle management
