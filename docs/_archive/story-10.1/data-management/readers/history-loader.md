# History Loader

The History Loader efficiently loads historical data windows with caching and prefetching.

## Overview

History Loader optimizes repeated data access through:
- Intelligent caching
- Prefetch strategies
- Batch loading
- Memory management

## Usage

```python
from rustybt.data.history_loader import DailyHistoryLoader

loader = DailyHistoryLoader(
    trading_calendar=get_calendar('NYSE'),
    reader=daily_bar_reader,
    adjustment_reader=adjustment_reader
)

# Load history window
data = loader.history(
    assets=[asset1, asset2],
    end_dt=pd.Timestamp('2023-01-15'),
    bar_count=20,
    field='close',
    frequency='1d'
)
```

## Caching Strategy

```python
# History loader automatically caches:
# 1. Recently accessed windows
# 2. Commonly requested fields
# 3. Frequently used assets

# First call: loads from disk
data1 = loader.history(assets, end_dt, bar_count=20, field='close')

# Second call: returns from cache (fast)
data2 = loader.history(assets, end_dt, bar_count=20, field='close')
```

## Prefetching

```python
# Enable prefetching for sequential access
loader = DailyHistoryLoader(
    trading_calendar=calendar,
    reader=reader,
    prefetch=True,
    prefetch_window=50  # Prefetch 50 bars ahead
)
```

## See [Data Portal](data-portal.md) for high-level API.
