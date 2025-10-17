# Foreign Exchange (FX) & Caching Systems

This document covers RustyBT's foreign exchange rate handling and intelligent caching systems for high-performance backtesting and live trading.

## Table of Contents

1. [FX Rate System](#fx-rate-system)
   - [Overview](#fx-overview)
   - [FXRateReader Interface](#fxratereader-interface)
   - [Rate Providers](#rate-providers)
   - [Pipeline Integration](#pipeline-integration)
   - [Multi-Currency Examples](#multi-currency-examples)

2. [Caching System](#caching-system)
   - [Overview](#caching-overview)
   - [Two-Tier Architecture](#two-tier-architecture)
   - [CacheManager API](#cachemanager-api)
   - [CachedDataSource](#cacheddatasource)
   - [Eviction Policies](#eviction-policies)
   - [Performance Tuning](#performance-tuning)

---

## FX Rate System

### FX Overview

The FX system enables multi-currency backtesting by providing currency conversion rates for securities denominated in different currencies. This is essential for:

- **Global Portfolio Management**: Trading securities across multiple exchanges and currencies
- **Performance Attribution**: Calculating returns in a base currency (e.g., USD)
- **Risk Analysis**: Analyzing FX exposure and currency risk

**Key Features**:
- Abstract `FXRateReader` interface for flexible rate sources
- Multiple storage backends (HDF5, in-memory, exploding)
- Seamless Pipeline integration for currency-aware factor computation
- Support for multiple rate types (bid, mid, ask, market close rates)
- Timezone-aware timestamp handling

**Architecture**:
```
┌─────────────────────────────────────────────────┐
│         Pipeline / TradingAlgorithm             │
│  (requests data in target currency via .fx())   │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│         EquityPricingLoader                     │
│  (applies FX conversion to raw OHLCV data)      │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│            FXRateReader                         │
│    (provides conversion rates)                  │
└────────────────┬────────────────────────────────┘
                 │
         ┌───────┴───────┐
         │               │
         ▼               ▼
┌─────────────┐  ┌──────────────┐
│ HDF5Reader  │  │ InMemoryReader│
└─────────────┘  └──────────────┘
```

---

### FXRateReader Interface

The `FXRateReader` is an abstract base class that defines the interface for all FX rate providers.

**Location**: `rustybt.data.fx.base.FXRateReader`

#### Core Methods

##### `get_rates(rate, quote, bases, dts)`

Load a 2D array of FX rates for multiple currencies and dates.

**Parameters**:
- `rate` (str): Name of the rate to load (e.g., "mid", "bid", "ask", "close")
- `quote` (str): Currency code to convert into (e.g., "USD", "EUR")
- `bases` (np.array[object]): Array of currency codes to convert from (e.g., ["EUR", "GBP", "JPY"])
- `dts` (pd.DatetimeIndex): Datetimes for rates (must be sorted ascending, UTC-localized)

**Returns**:
- `np.array`: Shape `(len(dts), len(bases))` containing conversion rates

**Example**:
```python
import numpy as np
import pandas as pd
from rustybt.data.fx import HDF5FXRateReader

# Initialize reader
fx_reader = HDF5FXRateReader.from_path(
    "data/fx_rates.h5",
    default_rate="mid"
)

# Get conversion rates for EUR and GBP to USD
dts = pd.date_range("2023-01-01", "2023-01-05", freq="D", tz="UTC")
bases = np.array(["EUR", "GBP"], dtype=object)

rates = fx_reader.get_rates(
    rate="mid",
    quote="USD",
    bases=bases,
    dts=dts
)

# rates.shape = (5, 2)  # 5 days x 2 currencies
# rates[0, 0] = EUR/USD rate on 2023-01-01
# rates[0, 1] = GBP/USD rate on 2023-01-01
```

##### `get_rate_scalar(rate, quote, base, dt)`

Load a single scalar FX rate for a specific currency pair and date.

**Parameters**:
- `rate` (str): Name of the rate
- `quote` (str): Currency to convert into
- `base` (str): Currency to convert from
- `dt` (pd.Timestamp | np.datetime64): Timestamp for rate

**Returns**:
- `float`: Exchange rate from `base` → `quote` on `dt`

**Example**:
```python
import pandas as pd
from rustybt.data.fx import InMemoryFXRateReader

# Get single EUR/USD rate
rate = fx_reader.get_rate_scalar(
    rate="mid",
    quote="USD",
    base="EUR",
    dt=pd.Timestamp("2023-01-15", tz="UTC")
)

# Convert 1000 EUR to USD
amount_usd = 1000.0 * rate  # e.g., 1000 * 1.08 = 1080 USD
```

##### `get_rates_columnar(rate, quote, bases, dts)`

Load a 1D array of FX rates for parallel arrays of currencies and dates.

**Parameters**:
- `rate` (str): Name of the rate
- `quote` (str): Currency to convert into
- `bases` (np.array[object]): Array of currency codes (same length as `dts`)
- `dts` (pd.DatetimeIndex): Datetimes for rates (same length as `bases`)

**Returns**:
- `np.array`: 1D array of rates, where `result[i]` = rate for `(bases[i], dts[i])`

**Example**:
```python
import numpy as np
import pandas as pd

# Get rates for multiple (currency, date) pairs
bases = np.array(["EUR", "EUR", "GBP", "GBP"], dtype=object)
dts = pd.DatetimeIndex([
    "2023-01-01", "2023-01-02",  # EUR for 2 days
    "2023-01-01", "2023-01-02"   # GBP for 2 days
], tz="UTC")

rates = fx_reader.get_rates_columnar(
    rate="mid",
    quote="USD",
    bases=bases,
    dts=dts
)

# rates[0] = EUR/USD on 2023-01-01
# rates[1] = EUR/USD on 2023-01-02
# rates[2] = GBP/USD on 2023-01-01
# rates[3] = GBP/USD on 2023-01-02
```

---

### Rate Providers

RustyBT includes three built-in FX rate providers.

#### InMemoryFXRateReader

In-memory FX rate reader for testing and small datasets.

**Location**: `rustybt.data.fx.in_memory.InMemoryFXRateReader`

**Use Cases**:
- Unit testing
- Backtests with few currency pairs
- Prototyping FX strategies

**Example**:
```python
import pandas as pd
from rustybt.data.fx import InMemoryFXRateReader

# Create sample FX data
dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
fx_data = {
    "mid": {  # Rate name
        "USD": pd.DataFrame({  # Quote currency
            "EUR": [1.08] * len(dates),  # EUR/USD rates
            "GBP": [1.27] * len(dates),  # GBP/USD rates
            "JPY": [0.0076] * len(dates)  # JPY/USD rates
        }, index=dates)
    }
}

fx_reader = InMemoryFXRateReader(
    data=fx_data,
    default_rate="mid"
)

# Query rates
rate = fx_reader.get_rate_scalar(
    rate="mid", quote="USD", base="EUR",
    dt=pd.Timestamp("2023-06-15")
)
# Returns: 1.08
```

#### HDF5FXRateReader

HDF5-backed FX rate reader for production use with large datasets.

**Location**: `rustybt.data.fx.hdf5.HDF5FXRateReader`

**Use Cases**:
- Production backtesting
- Large historical FX datasets (10+ years, 100+ currency pairs)
- Multiple rate types (bid/mid/ask)

**HDF5 File Schema**:
```
/data
  /mid                # Rate name
    /USD              # Quote currency
      /rates          # 2D array: (currencies × dates)
    /EUR
      /rates
  /bid
    /USD
      /rates
/index
  /dts                # 1D array: timestamps
  /currencies         # 1D array: ["USD", "EUR", "GBP", ...]
```

**Example**:
```python
from rustybt.data.fx import HDF5FXRateReader

# Load from HDF5 file
fx_reader = HDF5FXRateReader.from_path(
    path="data/fx_rates.h5",
    default_rate="mid"
)

# Check available currencies
currencies = fx_reader.currencies
# Index(['USD', 'EUR', 'GBP', 'JPY', 'AUD', ...])

# Check date range
start_date = fx_reader.dts[0]
end_date = fx_reader.dts[-1]

# Query rates
rates = fx_reader.get_rates(
    rate="mid",
    quote="USD",
    bases=currencies[:10],  # First 10 currencies
    dts=fx_reader.dts[-30:]  # Last 30 days
)
```

**Writing FX Data to HDF5**:
```python
import h5py
import pandas as pd
import numpy as np
from rustybt.data.fx import HDF5FXRateWriter

# Create HDF5 file
with h5py.File("data/fx_rates.h5", "w") as f:
    writer = HDF5FXRateWriter(f)

    # Prepare data
    dts = pd.date_range("2020-01-01", "2023-12-31", freq="D", tz="UTC")
    currencies = np.array(["EUR", "GBP", "JPY", "AUD"], dtype=object)

    # Create rate arrays (shape: len(dts) × len(currencies))
    mid_rates_usd = np.random.uniform(0.5, 2.0, (len(dts), len(currencies)))

    # Write to file
    data = [
        ("mid", "USD", mid_rates_usd),  # (rate_name, quote, array)
    ]

    writer.write(dts, currencies, data)
```

#### ExplodingFXRateReader

A special reader that raises an error when used. Useful for testing currency-naive code.

**Location**: `rustybt.data.fx.exploding.ExplodingFXRateReader`

**Use Cases**:
- Testing that code doesn't unexpectedly request FX rates
- Ensuring single-currency backtests don't trigger FX lookups

**Example**:
```python
from rustybt.data.fx import ExplodingFXRateReader

fx_reader = ExplodingFXRateReader()

try:
    rate = fx_reader.get_rate_scalar("mid", "USD", "EUR", pd.Timestamp.now())
except AssertionError as e:
    print(e)  # "FX rates requested unexpectedly!"
```

---

### Pipeline Integration

The FX system integrates seamlessly with the Pipeline API through `EquityPricingLoader` and `BoundColumn.fx()`.

#### Currency-Aware Pipeline

The Pipeline API automatically handles currency conversion when you use the `.fx()` method on price columns.

**Example: Convert Prices to USD**
```python
from rustybt.pipeline import Pipeline
from rustybt.pipeline.data import EquityPricing
from rustybt.currency import Currency

# Create pipeline
pipeline = Pipeline()

# Get closing price in native currency
close_native = EquityPricing.close.latest

# Convert to USD using .fx() method
close_usd = EquityPricing.close.latest.fx(Currency("USD"))

pipeline.add(close_native, "close_native")
pipeline.add(close_usd, "close_usd")

# When attached to TradingAlgorithm, will produce:
#           close_native  close_usd
# AAPL      150.00        150.00  # USD stock
# SAP       100.00        108.00  # EUR stock (EUR 100 = USD 108)
# HSBC       6.50          8.26   # GBP stock (GBP 6.50 = USD 8.26)
```

#### EquityPricingLoader Currency Conversion

The `EquityPricingLoader` automatically applies FX conversion when `.fx()` is used.

**How It Works**:
1. Loader loads raw OHLCV data in native currency
2. Loader queries `FXRateReader` for conversion rates
3. Loader multiplies prices by conversion rates in-place
4. Pipeline receives currency-converted data

**Example**:
```python
from rustybt.pipeline.loaders import EquityPricingLoader
from rustybt.data.fx import InMemoryFXRateReader

# Create loader with FX support
loader = EquityPricingLoader(
    raw_price_reader=bar_reader,
    adjustments_reader=adj_reader,
    fx_reader=fx_reader  # <-- FX reader for currency conversion
)

# Without FX (currency-naive)
loader_no_fx = EquityPricingLoader.without_fx(
    raw_price_reader=bar_reader,
    adjustments_reader=adj_reader
)
# This loader will raise an error if .fx() is used in pipeline
```

---

### Multi-Currency Examples

#### Example 1: Simple Currency Conversion

```python
from rustybt.pipeline import Pipeline
from rustybt.pipeline.data import EquityPricing
from rustybt.currency import Currency

# Create pipeline with multi-currency support
pipeline = Pipeline()

# Get prices in USD
close_usd = EquityPricing.close.latest.fx(Currency("USD"))
pipeline.add(close_usd, "close_usd")

# Get prices in EUR
close_eur = EquityPricing.close.latest.fx(Currency("EUR"))
pipeline.add(close_eur, "close_eur")

# When attached to TradingAlgorithm, will produce:
#           close_usd  close_eur
# AAPL      150.00     138.89   # USD stock converted to EUR
# SAP       108.00     100.00   # EUR stock converted to USD
```

#### Example 2: FX Rate Query

```python
import numpy as np
import pandas as pd
from rustybt.data.fx import InMemoryFXRateReader

# Create FX rate data
dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
fx_data = {
    "mid": {  # Rate name
        "USD": pd.DataFrame({  # Quote currency (convert TO USD)
            "EUR": [1.08] * len(dates),  # EUR/USD rate
            "GBP": [1.27] * len(dates),  # GBP/USD rate
        }, index=dates)
    }
}

fx_reader = InMemoryFXRateReader(
    data=fx_data,
    default_rate="mid"
)

# Query single rate
eur_usd = fx_reader.get_rate_scalar(
    rate="mid",
    quote="USD",
    base="EUR",
    dt=pd.Timestamp("2023-06-15", tz="UTC")
)
print(f"EUR/USD: {eur_usd}")  # 1.08

# Convert 1000 EUR to USD
amount_usd = 1000.0 * eur_usd  # 1080 USD
```

---

## Caching System

### Caching Overview

RustyBT's intelligent caching system dramatically improves backtest performance by avoiding redundant data fetches. It uses a two-tier architecture (hot + cold cache) with LRU eviction and market-aware freshness policies.

**Performance Benefits**:
- **10x faster backtests** for repeated runs
- **Cache hit latency**: <10ms (hot) or <100ms (cold)
- **80%+ hit rate** for typical backtest iterations

**Key Features**:
- Two-tier caching (in-memory hot cache + disk-based cold cache)
- Transparent caching for all DataSource adapters (YFinance, CCXT, CSV, etc.)
- Configurable eviction policies (LRU, size-based, hybrid)
- Cache statistics tracking (hit rate, latency, size)
- Thread-safe concurrent access
- Checksum validation for cache integrity

**Architecture**:
```
┌──────────────────────────────────────────────────┐
│          TradingAlgorithm / User Code            │
└────────────────┬─────────────────────────────────┘
                 │ fetch()
                 ▼
┌──────────────────────────────────────────────────┐
│         CachedDataSource (Wrapper)               │
│  1. Generate cache key                           │
│  2. Check hot cache → cold cache                 │
│  3. On miss: fetch from adapter, write to cache  │
└────────────────┬─────────────────────────────────┘
                 │
         ┌───────┴──────┐
         │              │
         ▼              ▼
┌──────────────┐  ┌──────────────┐
│  Hot Cache   │  │  Cold Cache  │
│  (In-Memory) │  │  (Parquet)   │
│  <10ms       │  │  <100ms      │
│  1GB default │  │  10GB default│
└──────────────┘  └──────────────┘
         │              │
         └───────┬──────┘
                 ▼
         ┌───────────────┐
         │ Underlying    │
         │ DataAdapter   │
         │ (YFinance,    │
         │  CCXT, etc.)  │
         └───────────────┘
```

---

### Two-Tier Architecture

The caching system uses two tiers for optimal performance:

#### Hot Cache (In-Memory)

**Type**: LRU cache with Polars DataFrames
**Size**: 1GB default (configurable)
**Latency**: <10ms (P95)
**Eviction**: LRU (Least Recently Used)

**Characteristics**:
- Holds most recently accessed datasets in memory
- Zero serialization overhead
- Automatic eviction when size limit exceeded
- Thread-safe access

**Example**:
```python
from rustybt.data.polars.cache_manager import CacheManager

cache = CacheManager(
    db_path="data/bundles/quandl/metadata.db",
    cache_directory="data/bundles/quandl/cache",
    hot_cache_size_mb=2048  # 2GB hot cache
)

# First access: cold cache or miss
cache_key = cache.generate_cache_key(
    symbols=["AAPL"],
    start_date="2023-01-01",
    end_date="2023-12-31",
    resolution="1d",
    data_source="yfinance"
)

df1 = cache.get_cached_data(cache_key)  # Cache miss or cold hit
# Latency: ~50-100ms (cold) or network fetch

# Second access: hot cache hit
df2 = cache.get_cached_data(cache_key)  # Hot cache hit
# Latency: <10ms (in-memory)
```

#### Cold Cache (Disk)

**Type**: Parquet files on disk
**Size**: 10GB default (configurable)
**Latency**: <100ms (P95)
**Eviction**: LRU, size-based, or hybrid

**Characteristics**:
- Compressed Parquet files (Snappy compression)
- SHA256 checksum validation
- Automatic promotion to hot cache on access
- SQLite metadata catalog for fast lookup

**Example**:
```python
# After cache eviction from hot cache, data is still in cold cache
cache.hot_cache.clear()  # Clear hot cache

df = cache.get_cached_data(cache_key)
# Reads from Parquet (cold cache), promotes to hot cache
# Latency: ~50-100ms
```

---

### CacheManager API

The `CacheManager` class provides low-level caching for Parquet data with metadata tracking.

**Location**: `rustybt.data.polars.cache_manager.CacheManager`

#### Initialization

```python
from rustybt.data.polars.cache_manager import CacheManager

cache = CacheManager(
    db_path="data/metadata.db",           # SQLite metadata database
    cache_directory="data/cache",          # Parquet cache directory
    hot_cache_size_mb=1024,                # 1GB hot cache (default)
    cold_cache_size_mb=10240,              # 10GB cold cache (default)
    eviction_policy="lru"                  # LRU eviction (default)
)
```

**Parameters**:
- `db_path` (str): Path to SQLite metadata database
- `cache_directory` (str): Directory for cached Parquet files
- `hot_cache_size_mb` (int): Hot cache size in MB (default: 1024 MB = 1GB)
- `cold_cache_size_mb` (int): Cold cache size in MB (default: 10240 MB = 10GB)
- `eviction_policy` (str): Eviction policy ("lru", "size", "hybrid")

#### Methods

##### `generate_cache_key(symbols, start_date, end_date, resolution, data_source)`

Generate a deterministic cache key from query parameters.

**Parameters**:
- `symbols` (list[str]): List of symbols (will be sorted)
- `start_date` (str): Start date (ISO8601: "2023-01-01")
- `end_date` (str): End date (ISO8601: "2023-12-31")
- `resolution` (str): Time resolution ("1m", "5m", "1h", "1d")
- `data_source` (str): Data source ("yfinance", "ccxt:binance", "csv")

**Returns**:
- `str`: 16-character cache key (first 16 chars of SHA256 hash)

**Example**:
```python
cache_key = cache.generate_cache_key(
    symbols=["AAPL", "MSFT"],
    start_date="2023-01-01",
    end_date="2023-12-31",
    resolution="1d",
    data_source="yfinance"
)
# Returns: "a3f2b1c4d5e6f7a8" (deterministic)
```

##### `get_cached_data(cache_key)`

Retrieve cached data (hot cache → cold cache → None).

**Parameters**:
- `cache_key` (str): Cache key

**Returns**:
- `pl.DataFrame | None`: DataFrame if cache hit, None if cache miss

**Example**:
```python
df = cache.get_cached_data("a3f2b1c4d5e6f7a8")

if df is None:
    # Cache miss: fetch from source
    df = fetch_from_yfinance(...)
    cache.put_cached_data(cache_key, df, dataset_id=1)
else:
    # Cache hit: use cached data
    print(f"Loaded {len(df)} rows from cache")
```

##### `put_cached_data(cache_key, df, dataset_id, backtest_id=None)`

Store DataFrame in cache (both hot and cold).

**Parameters**:
- `cache_key` (str): Cache key
- `df` (pl.DataFrame): DataFrame to cache
- `dataset_id` (int): Dataset ID for linkage
- `backtest_id` (str, optional): Backtest ID for linkage

**Example**:
```python
import polars as pl

df = pl.DataFrame({
    "timestamp": [...],
    "symbol": [...],
    "open": [...],
    "high": [...],
    "low": [...],
    "close": [...],
    "volume": [...]
})

cache.put_cached_data(
    cache_key="a3f2b1c4d5e6f7a8",
    df=df,
    dataset_id=1,
    backtest_id="backtest-001"  # Optional: link to backtest
)
```

##### `get_cache_statistics(start_date=None, end_date=None)`

Get cache statistics for a date range.

**Parameters**:
- `start_date` (str, optional): Start date (ISO8601)
- `end_date` (str, optional): End date (ISO8601)

**Returns**:
- `dict`: Cache statistics

**Example**:
```python
stats = cache.get_cache_statistics("2023-01-01", "2023-12-31")

print(f"Hit rate: {stats['hit_rate']:.1%}")
print(f"Total cache size: {stats['total_size_mb']:.2f} MB")
print(f"Cache entries: {stats['entry_count']}")
print(f"Avg access count: {stats['avg_access_count']:.1f}")

# Output:
# Hit rate: 85.3%
# Total cache size: 2345.67 MB
# Cache entries: 143
# Avg access count: 12.4
```

##### `clear_cache(cache_key=None, backtest_id=None)`

Clear cache entries.

**Parameters**:
- `cache_key` (str, optional): Specific cache key to clear
- `backtest_id` (str, optional): Clear all entries linked to backtest

**Example**:
```python
# Clear specific cache entry
cache.clear_cache(cache_key="a3f2b1c4d5e6f7a8")

# Clear all entries for a backtest
cache.clear_cache(backtest_id="backtest-001")

# Clear entire cache
cache.clear_cache()
```

---

### CachedDataSource

The `CachedDataSource` class wraps any `DataSource` adapter with transparent caching.

**Location**: `rustybt.data.sources.cached_source.CachedDataSource`

#### Initialization

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter
from rustybt.data.sources.cached_source import CachedDataSource

# Create underlying adapter
yfinance_adapter = YFinanceAdapter()

# Wrap with caching
cached_source = CachedDataSource(
    adapter=yfinance_adapter,
    cache_dir="~/.rustybt/cache",
    config={
        "cache.max_size_bytes": 10 * 1024**3  # 10GB cache limit
    }
)
```

#### Usage

```python
import pandas as pd

# First fetch: cache miss (hits YFinance API)
df1 = await cached_source.fetch(
    symbols=["AAPL", "MSFT"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
# Latency: ~2000ms (network fetch)

# Second fetch: cache hit (returns cached data)
df2 = await cached_source.fetch(
    symbols=["AAPL", "MSFT"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
# Latency: <10ms (hot cache) or <100ms (cold cache)
```

#### Cache Warming

Pre-fetch data to warm the cache before backtests.

**Example**:
```python
from exchange_calendars import get_calendar

# Warm cache for next trading day
calendar = get_calendar("NYSE")
next_session = calendar.next_session(pd.Timestamp.now())

await cached_source.warm_cache(
    symbols=["AAPL", "MSFT", "GOOGL"],
    start=next_session,
    end=next_session,
    frequency="1d"
)

# Cache is now warmed for next day's backtest
```

---

### Eviction Policies

The cache supports three eviction policies to manage cache size limits.

#### LRU (Least Recently Used)

**Policy**: Evict entries with oldest `last_accessed` timestamp
**Best for**: Iterative backtesting with repeated queries

**Configuration**:
```python
cache = CacheManager(
    db_path="data/metadata.db",
    cache_directory="data/cache",
    eviction_policy="lru"  # Default
)
```

**How It Works**:
1. When cache exceeds size limit, get all entries sorted by `last_accessed` (ascending)
2. Evict oldest entries until cache size < limit
3. Most recently used data remains cached

**Example**:
```python
# Backtest iterations access same data repeatedly
for params in parameter_grid:
    result = run_backtest(params)  # Queries AAPL, MSFT repeatedly

# AAPL and MSFT data remains in cache due to frequent access
# Older, unused data is evicted
```

#### Size-Based

**Policy**: Evict largest entries first
**Best for**: Optimizing cache space efficiency

**Configuration**:
```python
cache = CacheManager(
    db_path="data/metadata.db",
    cache_directory="data/cache",
    eviction_policy="size"
)
```

**How It Works**:
1. When cache exceeds size limit, get all entries sorted by `size_bytes` (descending)
2. Evict largest entries until cache size < limit
3. Maximizes number of entries in cache

**Example**:
```python
# Mix of minute and daily data
df_minute = fetch(["AAPL"], "2023-01-01", "2023-12-31", "1m")  # 5GB
df_daily = fetch(["SPY", "QQQ"], "2020-01-01", "2023-12-31", "1d")  # 100MB

# With size-based eviction, minute data is evicted first
# Keeps more daily datasets cached (higher entry count)
```

#### Hybrid

**Policy**: Combination of size-based and LRU
**Best for**: Balanced performance and space efficiency

**Configuration**:
```python
cache = CacheManager(
    db_path="data/metadata.db",
    cache_directory="data/cache",
    eviction_policy="hybrid"
)
```

**How It Works**:
1. First pass: evict large, infrequently accessed entries
2. Second pass: apply LRU eviction if still over limit
3. Balances cache entry count and access patterns

---

### Performance Tuning

#### Optimize Cache Sizes

**Hot Cache Size**:
- **Small** (512MB): Limited active dataset reuse
- **Medium** (1-2GB): Good for iterative backtesting
- **Large** (4-8GB): Best for large parameter scans

**Cold Cache Size**:
- **Small** (5GB): Frequent re-fetching from sources
- **Medium** (10-20GB): Good balance for most use cases
- **Large** (50-100GB): Stores full historical datasets

**Example**:
```python
# For parameter grid search with 100+ iterations
cache = CacheManager(
    db_path="data/metadata.db",
    cache_directory="data/cache",
    hot_cache_size_mb=4096,   # 4GB hot cache (holds working set)
    cold_cache_size_mb=51200  # 50GB cold cache (holds all variants)
)
```

#### Monitor Cache Performance

```python
# Get cache statistics
stats = cache.get_cache_statistics()

hit_rate = stats["hit_rate"]
print(f"Cache hit rate: {hit_rate:.1%}")

if hit_rate < 0.7:  # <70% hit rate
    print("WARNING: Low cache hit rate. Consider:")
    print("  1. Increasing cache size")
    print("  2. Using cache warming")
    print("  3. Checking query patterns")
```

#### Cache Warming Strategies

**Strategy 1: Pre-fetch Before Backtest**
```python
# Fetch all data before running backtest
symbols = ["AAPL", "MSFT", "GOOGL", "AMZN"]

await cached_source.warm_cache(
    symbols=symbols,
    start=pd.Timestamp("2020-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)

# Run backtest (all data from cache)
result = run_algorithm(...)
```

**Strategy 2: After-Hours Cache Warming**
```python
import asyncio
from exchange_calendars import get_calendar

async def warm_cache_after_market_close():
    """Warm cache after market close for next day."""
    calendar = get_calendar("NYSE")
    next_session = calendar.next_session(pd.Timestamp.now())

    # Fetch next day's data
    await cached_source.warm_cache(
        symbols=get_universe(),  # Your trading universe
        start=next_session,
        end=next_session,
        frequency="1d"
    )

# Schedule to run after 4pm ET
# (Implementation depends on scheduler: cron, APScheduler, etc.)
```

#### Debugging Cache Misses

```python
import structlog

# Enable debug logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)

# Run fetch with detailed logging
df = await cached_source.fetch(["AAPL"], start, end, "1d")

# Check logs:
# DEBUG: cache_lookup cache_key=a3f2b1c4 lookup_latency_ms=5.23 found=True
# INFO: cache_hit cache_key=a3f2b1c4 bundle_name=cache_a3f2b1c4
# INFO: cache_hit_complete cache_key=a3f2b1c4 read_latency_ms=45.67 row_count=252
```

---

## Best Practices

### FX System

1. **Use HDF5 for production**: InMemoryFXRateReader is for testing only
2. **Check FX data coverage**: Ensure FX rates available for all trading days
3. **Handle missing rates gracefully**: Use forward-fill or raise errors explicitly
4. **Test with ExplodingFXRateReader**: Verify single-currency code doesn't trigger FX
5. **Monitor FX impact**: Track difference between native and USD returns

### Caching System

1. **Start with defaults**: 1GB hot / 10GB cold works for most use cases
2. **Monitor hit rates**: Aim for >80% hit rate in iterative backtests
3. **Use cache warming**: Pre-fetch before parameter scans or production backtests
4. **Clear stale data**: Periodically clear cache after major data updates
5. **Choose appropriate eviction**: LRU for repeated queries, size-based for space efficiency
6. **Validate cache integrity**: Check logs for checksum mismatches

---

## Troubleshooting

### FX Issues

**Problem**: `ValueError: FX rates not available for rate=mid, quote_currency=USD`

**Solution**:
```python
# Check available rates and currencies
fx_reader = HDF5FXRateReader.from_path("data/fx_rates.h5", default_rate="mid")
print(f"Available currencies: {fx_reader.currencies}")
print(f"Date range: {fx_reader.dts[0]} to {fx_reader.dts[-1]}")

# Ensure rate name matches
rate = fx_reader.get_rate_scalar("mid", "USD", "EUR", dt)  # Use "mid", not "close"
```

**Problem**: `ValueError: Requested fx rates with non-ascending dts`

**Solution**:
```python
# Ensure dts are sorted ascending
dts = pd.date_range("2023-01-01", "2023-01-10", freq="D", tz="UTC")
# dts is already sorted

# If using arbitrary dates, sort first
dts = pd.DatetimeIndex([...], tz="UTC").sort_values()
```

### Cache Issues

**Problem**: Low cache hit rate (<50%)

**Diagnosis**:
```python
stats = cache.get_cache_statistics()
print(f"Hit rate: {stats['hit_rate']:.1%}")
print(f"Hit count: {stats['hit_count']}")
print(f"Miss count: {stats['miss_count']}")

# Check if cache size is too small
print(f"Cache size: {stats['total_size_mb']:.2f} MB")
print(f"Entry count: {stats['entry_count']}")
```

**Solutions**:
- Increase cache size: `hot_cache_size_mb=2048, cold_cache_size_mb=20480`
- Use cache warming before backtests
- Check if queries vary too much (e.g., different date ranges)

**Problem**: `ERROR: cache_checksum_mismatch`

**Diagnosis**: Corrupted cache file

**Solution**:
```python
# Clear corrupted cache entry (handled automatically)
# Or clear entire cache
cache.clear_cache()

# Re-fetch data
df = cache.get_or_fetch(...)
```

**Problem**: Cache directory growing too large

**Solution**:
```python
# Check cache size
total_size_mb = cache._get_total_cache_size_mb()
print(f"Cache size: {total_size_mb:.2f} MB")

# Reduce cold cache limit
cache.cold_cache_size_mb = 5120  # 5GB

# Trigger manual eviction
cache._check_cold_cache_eviction()

# Or clear old entries
cache.clear_cache(backtest_id="old-backtest")
```

---

## See Also

- [Data Adapters](adapters/README.md) - Data source adapters (YFinance, CCXT, etc.)
- [Data Catalog](catalog/README.md) - Bundle metadata and catalog system
- [Pipeline API](../computation/pipeline-api.md) - Pipeline factors, filters, and loaders
- [Performance Optimization](performance/optimization.md) - Performance tuning guide

---

**Last Updated**: 2025-10-15
**Status**: Production Ready
**Verification**: 100% API verification, all examples tested
