# Bar Readers

Bar readers provide low-level access to OHLCV data stored in various formats.

## Reader Types

### PolarsParquetDailyReader

```python
from rustybt.data.polars import PolarsParquetDailyReader

reader = PolarsParquetDailyReader('/path/to/daily_equities.parquet')

# Load bars for asset
bars = reader.load_raw_arrays(
    sids=[asset.sid],
    fields=['open', 'high', 'low', 'close', 'volume'],
    start_dt=start_date,
    end_dt=end_date
)
```

**Features**:
- Fast columnar reads
- Efficient filtering
- Lazy evaluation via Polars
- Excellent compression

### PolarsParquetMinuteReader

```python
from rustybt.data.polars import PolarsParquetMinuteReader

reader = PolarsParquetMinuteReader('/path/to/minute_equities.parquet')

# Same interface as daily reader
bars = reader.load_raw_arrays(
    sids=[asset.sid],
    fields=['close'],
    start_dt=start_minute,
    end_dt=end_minute
)
```

### HDF5DailyBarReader (Legacy)

```python
from rustybt.data.hdf5_daily_bars import HDF5DailyBarReader

reader = HDF5DailyBarReader('/path/to/daily_equities.h5')
# Same interface as Parquet readers
```

### BcolzDailyBarReader (Deprecated)

```python
from rustybt.data.bcolz_daily_bars import BcolzDailyBarReader

reader = BcolzDailyBarReader('/path/to/daily_equities.bcolz')
# Legacy format, migrate to Parquet
```

## Reader Selection

The dispatch reader automatically selects the appropriate format:

## Data Quality

All readers validate:
- OHLCV relationships (high ≥ open, close, low)
- Temporal consistency
- Schema compliance
- Decimal precision

## Performance Comparison

| Format | Read Speed | Memory | Compression |
|--------|-----------|---------|-------------|
| Parquet | ⚡⚡⚡ | Low | Excellent |
| HDF5 | ⚡⚡ | Medium | Good |
| bcolz | ⚡⚡ | Medium | Good |

**Recommendation**: Use Parquet for new projects.

## See Also

- [Data Portal](data-portal.md) - High-level data access
- [History Loader](history-loader.md) - Efficient batch loading
