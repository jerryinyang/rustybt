# Performance Optimization Guide

Advanced techniques for optimizing data operations in RustyBT.

## Memory Management

### 1. Chunked Processing

```python
def process_large_dataset(file_path, chunk_size=100_000):
    """Process large dataset in chunks."""
    df_lazy = pl.scan_parquet(file_path)
    total_rows = df_lazy.select(pl.count()).collect()[0, 0]

    for offset in range(0, total_rows, chunk_size):
        chunk = df_lazy.slice(offset, chunk_size).collect()
        process_chunk(chunk)
        del chunk  # Free memory immediately
```

### 2. Column Selection

```python
# Bad: Load all columns
df = pl.read_parquet('data.parquet')

# Good: Load only needed columns
df = pl.read_parquet('data.parquet', columns=['timestamp', 'close'])
```

### 3. Streaming Mode

```python
# Use Polars streaming for large datasets
df = (pl.scan_parquet('large_file.parquet')
    .filter(pl.col('volume') > 1_000_000)
    .select(['symbol', 'close'])
    .collect(streaming=True)  # Process in streaming mode
)
```

## Query Optimization

### 1. Filter Early

```python
# Bad: Filter after loading
df = pl.read_parquet('data.parquet')
df_filtered = df.filter(pl.col('symbol') == 'AAPL')

# Good: Filter during load (predicate pushdown)
df = (pl.scan_parquet('data.parquet')
    .filter(pl.col('symbol') == 'AAPL')
    .collect()
)
```

### 2. Index Usage

```python
# Create index for fast lookups
df = df.set_sorted('timestamp')

# Fast binary search
result = df.filter(pl.col('timestamp') == target_date)
```

## Parallel Execution

### 1. Polars Parallelism

```python
# Polars automatically parallelizes operations
import polars as pl

# Set thread count (default: all cores)
pl.Config.set_thread_pool_size(8)

# Operations run in parallel automatically
df = (pl.scan_parquet('data.parquet')
    .groupby('symbol')
    .agg(pl.col('close').mean())
    .collect()
)
```

### 2. Multi-Processing

```python
from multiprocessing import Pool

def process_symbol(symbol):
    return expensive_computation(symbol)

# Process symbols in parallel
with Pool(processes=8) as pool:
    results = pool.map(process_symbol, symbols)
```

## I/O Optimization

### 1. Compression Selection

| Compression | Speed | Ratio | Use Case |
|-------------|-------|-------|----------|
| **snappy** | ⚡⚡⚡ | 1.5x | Fast reads |
| **lz4** | ⚡⚡⚡ | 1.5x | Fast reads |
| **zstd** | ⚡⚡ | 3x | Storage |
| **gzip** | ⚡ | 3x | Maximum compression |

### 2. Partitioning

```python
# Partition by symbol for efficient filtering
writer.write_dataset(
    df,
    '/data/partitioned',
    partition_by=['symbol']
)

# Fast symbol-specific reads
df_aapl = pl.read_parquet('/data/partitioned/symbol=AAPL/')
```

## See [Caching](caching.md) and [Troubleshooting](troubleshooting.md) for more.
