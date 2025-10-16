# Data Catalog Architecture

## Overview

The RustyBT data catalog provides a unified, high-performance data management system for storing, retrieving, and caching OHLCV (Open, High, Low, Close, Volume) market data. This architecture replaces Zipline's bcolz/HDF5 storage with a modern Polars/Parquet stack, delivering 5-10x performance improvements and 50-80% storage reduction while maintaining financial-grade Decimal precision.

**Version:** 1.0
**Epic:** Epic 3 - Modern Data Architecture & MVP Data Sources
**Created:** 2025-10-01
**Status:** Design Approved

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         User Strategy Code                               │
│                    (TradingAlgorithm, Backtester)                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ data.current(), data.history()
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                        PolarsDataPortal                                  │
│                   (Unified Data Access Layer)                            │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Cache Lookup → Cache Hit? → Return Polars DataFrame             │   │
│  │       ↓ Cache Miss                                               │   │
│  │  DataCatalog Query → BarReader → CacheManager Update             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ↓               ↓               ↓
    ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
    │   DataCatalog    │ │ CacheManager │ │  BarReaders      │
    │   (Metadata)     │ │ (Two-Tier)   │ │  (Parquet I/O)   │
    └────────┬─────────┘ └──────┬───────┘ └────────┬─────────┘
             │                  │                   │
             ↓                  ↓                   ↓
    ┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
    │ SQLite Metadata │ │  In-Memory Cache │ │ Parquet Storage  │
    │  - Datasets     │ │ (Polars LazyFrame│ │  - Daily Bars    │
    │  - Symbols      │ │  LRU Eviction)   │ │  - Minute Bars   │
    │  - Date Ranges  │ │                  │ │  (Partitioned)   │
    │  - Checksums    │ │  Disk Cache      │ │                  │
    │  - Backtest     │ │ (Parquet Files)  │ │  OHLCV Schema:   │
    │    Linkage      │ │                  │ │  Decimal(18,8)   │
    └─────────────────┘ └──────────────────┘ └──────────────────┘
             ↑                                          ↑
             │                                          │
             └──────────────────┬───────────────────────┘
                                │
                    ┌───────────┴────────────┐
                    │   Data Adapters        │
                    │  (Ingest External Data)│
                    └───────────┬────────────┘
                                │
                    ┌───────────┼────────────┐
                    ↓           ↓            ↓
            ┌─────────────┐ ┌─────────┐ ┌─────────┐
            │ CCXTAdapter │ │YFinance │ │   CSV   │
            │(100+ Crypto │ │ Adapter │ │ Adapter │
            │  Exchanges) │ │(Stocks) │ │(Custom) │
            └─────────────┘ └─────────┘ └─────────┘
```

---

## Component Architecture

### 1. DataCatalog (Metadata Management)

**Location:** `rustybt/data/polars/catalog.py`

**Purpose:** Central metadata registry for all available datasets, providing fast lookups for dataset discovery, date range queries, and cache key generation.

**Key Responsibilities:**
- Register datasets from data adapters
- Track dataset metadata (source, symbols, date ranges, resolution)
- Generate unique dataset IDs and cache keys
- Link backtests to cached datasets for reuse
- Manage checksums for data integrity validation

**Interface:**
```python
from typing import List, Optional
import polars as pl
import pandas as pd
from decimal import Decimal

class DataCatalog:
    """Central metadata registry for data management."""

    def __init__(self, metadata_db_path: str):
        """Initialize catalog with SQLite metadata database.

        Args:
            metadata_db_path: Path to SQLite metadata database
        """
        self.metadata_db_path = metadata_db_path
        self.engine = create_engine(f"sqlite:///{metadata_db_path}")

    def register_dataset(
        self,
        source: str,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        checksum: str,
    ) -> str:
        """Register new dataset in catalog.

        Args:
            source: Data source identifier ('ccxt:binance', 'yfinance', 'csv:custom')
            symbols: List of symbols in dataset
            start_date: Dataset start date
            end_date: Dataset end date
            resolution: Data resolution ('1d', '1h', '1m', etc.)
            checksum: Dataset checksum (SHA256 of Parquet files)

        Returns:
            dataset_id: Unique dataset identifier
        """

    def find_dataset(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        source: Optional[str] = None,
    ) -> Optional[str]:
        """Find existing dataset matching criteria.

        Args:
            symbols: Required symbols
            start_date: Required start date
            end_date: Required end date
            resolution: Required resolution
            source: Optional source filter

        Returns:
            dataset_id if found, None otherwise
        """

    def get_dataset_info(self, dataset_id: str) -> dict:
        """Get full dataset metadata.

        Args:
            dataset_id: Dataset identifier

        Returns:
            Dictionary with dataset metadata
        """

    def link_backtest_to_dataset(
        self,
        backtest_id: str,
        dataset_id: str,
        cached_at: pd.Timestamp,
    ):
        """Link backtest to dataset for cache tracking.

        Args:
            backtest_id: Backtest identifier
            dataset_id: Dataset identifier
            cached_at: Timestamp when data was cached
        """

    def get_datasets_for_backtest(self, backtest_id: str) -> List[str]:
        """Get all datasets used by backtest.

        Args:
            backtest_id: Backtest identifier

        Returns:
            List of dataset IDs
        """
```

**SQLite Schema:** See [SQLite Metadata Catalog Schema](#sqlite-metadata-catalog-schema) section below.

---

### 2. CacheManager (Two-Tier Caching)

**Location:** `rustybt/data/polars/cache_manager.py`

**Purpose:** High-performance two-tier cache (in-memory hot cache + disk-based cold cache) to minimize redundant data fetches and accelerate backtests.

**Key Responsibilities:**
- Maintain in-memory cache of recently accessed Polars LazyFrames
- Persist cold cache to disk as Parquet files
- Implement LRU eviction policy with configurable size limits
- Generate cache keys from query parameters (symbols, date_range, resolution, source)
- Invalidate cache entries when upstream data changes (checksum validation)

**Cache Architecture:**
```
┌─────────────────────────────────────────────────────┐
│              CacheManager                            │
├─────────────────────────────────────────────────────┤
│  Cache Hit/Miss Logic:                              │
│                                                      │
│  Query(symbols, date_range, resolution, source)     │
│    ↓                                                 │
│  Generate Cache Key:                                │
│    cache_key = hash(symbols, date_range,            │
│                     resolution, source)              │
│    ↓                                                 │
│  Check Hot Cache (In-Memory):                       │
│    ├─ Hit → Return Polars LazyFrame                 │
│    └─ Miss ↓                                         │
│  Check Cold Cache (Disk Parquet):                   │
│    ├─ Hit → Load to Hot Cache → Return              │
│    └─ Miss ↓                                         │
│  Fetch from BarReader → Store in Both Caches        │
├─────────────────────────────────────────────────────┤
│  Hot Cache: OrderedDict[cache_key, LazyFrame]       │
│  - Max size: 1GB (configurable)                     │
│  - Eviction: LRU (least recently used)              │
│                                                      │
│  Cold Cache: Parquet files in cache directory       │
│  - Max size: 50GB (configurable)                    │
│  - Eviction: LRU with periodic cleanup              │
└─────────────────────────────────────────────────────┘
```

**Interface:**
```python
from typing import List, Optional
import polars as pl
import pandas as pd
from pathlib import Path

class CacheManager:
    """Two-tier cache manager for OHLCV data."""

    def __init__(
        self,
        cache_dir: Path,
        hot_cache_size_mb: int = 1024,
        cold_cache_size_mb: int = 51200,
    ):
        """Initialize cache manager.

        Args:
            cache_dir: Directory for cold cache storage
            hot_cache_size_mb: Max in-memory cache size in MB
            cold_cache_size_mb: Max disk cache size in MB
        """
        self.cache_dir = cache_dir
        self.hot_cache_size_mb = hot_cache_size_mb
        self.cold_cache_size_mb = cold_cache_size_mb
        self._hot_cache: OrderedDict[str, pl.LazyFrame] = OrderedDict()
        self._hot_cache_size_bytes = 0

    def get(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        source: str,
    ) -> Optional[pl.LazyFrame]:
        """Get data from cache.

        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            resolution: Data resolution
            source: Data source

        Returns:
            Cached LazyFrame if found, None otherwise
        """

    def put(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        source: str,
        data: pl.LazyFrame,
    ):
        """Put data into cache.

        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            resolution: Data resolution
            source: Data source
            data: Data to cache
        """

    def invalidate(self, cache_key: str):
        """Invalidate cache entry.

        Args:
            cache_key: Cache key to invalidate
        """

    def clear(self):
        """Clear entire cache (hot and cold)."""

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with hit rate, size, entry count
        """

    def _generate_cache_key(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        source: str,
    ) -> str:
        """Generate cache key from query parameters.

        Args:
            symbols: List of symbols (sorted)
            start_date: Start date
            end_date: End date
            resolution: Data resolution
            source: Data source

        Returns:
            SHA256 hash as cache key
        """
        import hashlib
        import json

        cache_params = {
            "symbols": sorted(symbols),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "resolution": resolution,
            "source": source,
        }
        cache_str = json.dumps(cache_params, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def _evict_lru_hot_cache(self):
        """Evict least recently used entry from hot cache."""

    def _evict_lru_cold_cache(self):
        """Evict least recently used files from cold cache."""
```

**Cache Key Format:**
```python
# Example cache key generation
symbols = ["AAPL", "MSFT", "GOOG"]
start_date = pd.Timestamp("2023-01-01")
end_date = pd.Timestamp("2023-12-31")
resolution = "1d"
source = "yfinance"

# Deterministic cache key (SHA256)
cache_key = "a3f5b2c1d4e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2"
```

**Cache Invalidation Triggers:**
1. **Checksum Change:** Dataset checksum differs from cached version
2. **Manual Refresh:** User explicitly requests data refresh
3. **TTL Expiration:** Time-to-live exceeded (configurable, default: 7 days)
4. **Upstream Update:** Data adapter reports new data available

---

### 3. PolarsParquetDailyReader (Daily Bar Storage)

**Location:** `rustybt/data/polars/parquet_daily_bars.py`

**Purpose:** Read daily OHLCV bars from Parquet storage with partition pruning and lazy evaluation.

**Key Responsibilities:**
- Load daily bars from Parquet files partitioned by (year, month)
- Return Polars LazyFrames with Decimal columns
- Support date range queries with automatic partition pruning
- Provide efficient get_last_traded_dt() for forward-fill logic

**Directory Structure:**
```
data/bundles/{bundle_name}/daily_bars/
├── year=2022/
│   ├── month=01/
│   │   └── data.parquet  (~10MB for 3000 assets, full month)
│   ├── month=02/
│   │   └── data.parquet
│   └── ...
├── year=2023/
│   ├── month=01/
│   │   └── data.parquet
│   └── ...
└── metadata.db (SQLite)
```

**Parquet Schema:**
```python
{
    "date": pl.Date,                          # Trading date (local timezone)
    "sid": pl.Int64,                          # Security ID (asset identifier)
    "open": pl.Decimal(precision=18, scale=8),  # Opening price
    "high": pl.Decimal(precision=18, scale=8),  # Highest price
    "low": pl.Decimal(precision=18, scale=8),   # Lowest price
    "close": pl.Decimal(precision=18, scale=8), # Closing price
    "volume": pl.Decimal(precision=18, scale=8), # Trading volume
}
```

**Interface:**
```python
import polars as pl
import pandas as pd
from typing import List, Optional

class PolarsParquetDailyReader:
    """Read daily OHLCV bars from Parquet storage."""

    def __init__(self, parquet_dir: str):
        """Initialize reader.

        Args:
            parquet_dir: Path to daily_bars/ directory
        """
        self.parquet_dir = parquet_dir

    def load_raw_arrays(
        self,
        sids: List[int],
        fields: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pl.LazyFrame:
        """Load OHLCV data as Polars LazyFrame.

        Args:
            sids: List of asset IDs
            fields: List of fields to load ('open', 'high', 'low', 'close', 'volume')
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Polars LazyFrame with Decimal columns
        """

    def get_last_traded_dt(
        self,
        asset_sid: int,
        dt: pd.Timestamp,
    ) -> Optional[pd.Timestamp]:
        """Get last traded date for asset before dt.

        Args:
            asset_sid: Asset ID
            dt: Reference date

        Returns:
            Last traded date, or None if no data
        """

    def get_value(
        self,
        sid: int,
        dt: pd.Timestamp,
        field: str,
    ) -> Optional[Decimal]:
        """Get single field value for asset at date.

        Args:
            sid: Asset ID
            dt: Date
            field: Field name

        Returns:
            Decimal value, or None if no data
        """
```

**Partition Pruning Example:**
```python
# Query for Q1 2023 data
reader = PolarsParquetDailyReader("data/bundles/quandl/daily_bars")
df = reader.load_raw_arrays(
    sids=[1, 2, 3],
    fields=["close", "volume"],
    start_date=pd.Timestamp("2023-01-01"),
    end_date=pd.Timestamp("2023-03-31"),
)

# Polars automatically prunes to:
#   year=2023/month=01/data.parquet
#   year=2023/month=02/data.parquet
#   year=2023/month=03/data.parquet
# (Skips all other years and months)
```

---

### 4. PolarsParquetMinuteReader (Minute Bar Storage)

**Location:** `rustybt/data/polars/parquet_minute_bars.py`

**Purpose:** Read minute OHLCV bars from Parquet storage with deep partitioning (year/month/day) for efficient intraday queries.

**Directory Structure:**
```
data/bundles/{bundle_name}/minute_bars/
├── year=2023/
│   ├── month=01/
│   │   ├── day=01/
│   │   │   └── data.parquet  (~500MB for 3000 assets, full day)
│   │   ├── day=02/
│   │   │   └── data.parquet
│   │   └── ...
│   └── month=02/
│       └── ...
└── metadata.db (SQLite)
```

**Parquet Schema:**
```python
{
    "timestamp": pl.Datetime("us"),           # Timestamp with microsecond precision (UTC)
    "sid": pl.Int64,                          # Security ID (asset identifier)
    "open": pl.Decimal(precision=18, scale=8),  # Opening price
    "high": pl.Decimal(precision=18, scale=8),  # Highest price
    "low": pl.Decimal(precision=18, scale=8),   # Lowest price
    "close": pl.Decimal(precision=18, scale=8), # Closing price
    "volume": pl.Decimal(precision=18, scale=8), # Trading volume
}
```

**Interface:** Similar to `PolarsParquetDailyReader` but with timestamp-based queries.

---

### 5. PolarsDataPortal (Unified Data Access Layer)

**Location:** `rustybt/data/polars/data_portal.py`

**Purpose:** Unified interface for data access, integrating cache, catalog, and bar readers. Extends Zipline's DataPortal API.

**Integration Points:**
- Accessed via `data.current()`, `data.history()` in user strategies
- Coordinates between CacheManager, DataCatalog, and BarReaders
- Returns Polars DataFrames (with pandas fallback for compatibility)

**Interface:**
```python
import polars as pl
import pandas as pd
from typing import List
from zipline.data.data_portal import DataPortal

class PolarsDataPortal(DataPortal):
    """Unified data access layer with Polars backend."""

    def __init__(
        self,
        asset_finder,
        trading_calendar,
        daily_bar_reader: PolarsParquetDailyReader,
        minute_bar_reader: PolarsParquetMinuteReader,
        cache_manager: CacheManager,
        data_catalog: DataCatalog,
    ):
        """Initialize data portal.

        Args:
            asset_finder: AssetFinder for asset lookups
            trading_calendar: TradingCalendar for date validation
            daily_bar_reader: Daily bar reader
            minute_bar_reader: Minute bar reader
            cache_manager: Cache manager
            data_catalog: Data catalog
        """

    def get_spot_value(
        self,
        assets: List[Asset],
        field: str,
        dt: pd.Timestamp,
        data_frequency: str,
    ) -> pl.Series:
        """Get current field values as Polars Series (Decimal dtype).

        Args:
            assets: List of assets
            field: Field name ('open', 'high', 'low', 'close', 'volume')
            dt: Timestamp
            data_frequency: 'daily' or 'minute'

        Returns:
            Polars Series with Decimal values
        """

    def get_history_window(
        self,
        assets: List[Asset],
        end_dt: pd.Timestamp,
        bar_count: int,
        frequency: str,
        field: str,
        data_frequency: str,
    ) -> pl.DataFrame:
        """Get historical window as Polars DataFrame (Decimal columns).

        Args:
            assets: List of assets
            end_dt: End timestamp
            bar_count: Number of bars to fetch
            frequency: Bar frequency ('1d', '1h', '1m')
            field: Field name
            data_frequency: 'daily' or 'minute'

        Returns:
            Polars DataFrame with Decimal columns
        """
```

---

### 6. BaseDataAdapter (Data Source Integration)

**Location:** `rustybt/data/adapters/base.py`

**Purpose:** Abstract base class for external data source integrations (CCXT, YFinance, CSV).

**Key Responsibilities:**
- Fetch OHLCV data from external sources
- Validate data quality (OHLCV relationships, outliers, completeness)
- Standardize to RustyBT schema (Polars DataFrame with Decimal columns)
- Write to Parquet storage via DataCatalog

**Interface:**
```python
from abc import ABC, abstractmethod
import polars as pl
import pandas as pd
from typing import List

class BaseDataAdapter(ABC):
    """Base class for data source adapters."""

    @abstractmethod
    async def fetch(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from source.

        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            resolution: Data resolution ('1d', '1h', '1m', etc.)

        Returns:
            Polars DataFrame with OHLCV data
        """

    @abstractmethod
    def validate(self, df: pl.DataFrame) -> bool:
        """Validate OHLCV relationships and data quality.

        Args:
            df: DataFrame to validate

        Returns:
            True if valid, raises ValidationError otherwise
        """

    @abstractmethod
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider-specific format to RustyBT schema.

        Args:
            df: DataFrame to standardize

        Returns:
            Standardized DataFrame with Decimal columns
        """

    def ingest(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        catalog: DataCatalog,
        parquet_writer,
    ) -> str:
        """Full ingestion workflow.

        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            resolution: Data resolution
            catalog: DataCatalog for registration
            parquet_writer: Writer for Parquet storage

        Returns:
            dataset_id
        """
        # 1. Fetch data
        df = await self.fetch(symbols, start_date, end_date, resolution)

        # 2. Validate
        self.validate(df)

        # 3. Standardize
        df = self.standardize(df)

        # 4. Write to Parquet
        parquet_path = parquet_writer.write(df, resolution)

        # 5. Register in catalog
        checksum = calculate_checksum(parquet_path)
        dataset_id = catalog.register_dataset(
            source=self.source_name,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            resolution=resolution,
            checksum=checksum,
        )

        return dataset_id
```

**Standard OHLCV Schema:**
```python
{
    "timestamp": pl.Datetime("us"),  # or "date": pl.Date for daily
    "symbol": pl.Utf8,
    "open": pl.Decimal(18, 8),
    "high": pl.Decimal(18, 8),
    "low": pl.Decimal(18, 8),
    "close": pl.Decimal(18, 8),
    "volume": pl.Decimal(18, 8),
}
```

**Validation Rules:**
1. **OHLCV Relationships:**
   - `high >= max(open, close)`
   - `low <= min(open, close)`
   - `high >= low`
   - `volume >= 0`

2. **Temporal Consistency:**
   - Timestamps sorted ascending
   - No duplicate timestamps per symbol
   - No future data (timestamp <= current time)

3. **Completeness:**
   - No NULL values in required fields
   - Continuous date/time ranges (no gaps)

4. **Outlier Detection:**
   - Flag price changes >3 standard deviations
   - Flag volume spikes >5 standard deviations

**Implementations:**
- `CCXTDataAdapter`: Crypto data via CCXT (100+ exchanges)
- `YFinanceAdapter`: Stock/ETF/forex via yfinance
- `CSVAdapter`: Custom CSV data with configurable schema mapping

---

## Parquet Storage Schema

### Daily Bars Schema

```python
DAILY_BARS_SCHEMA = {
    "date": pl.Date,                          # Trading date (local timezone)
    "sid": pl.Int64,                          # Security ID (asset identifier)
    "open": pl.Decimal(precision=18, scale=8),  # Opening price
    "high": pl.Decimal(precision=18, scale=8),  # Highest price
    "low": pl.Decimal(precision=18, scale=8),   # Lowest price
    "close": pl.Decimal(precision=18, scale=8), # Closing price
    "volume": pl.Decimal(precision=18, scale=8), # Trading volume
}
```

**Decimal Precision Rationale:**
- `Decimal(18, 8)`: 18 total digits, 8 decimal places
- Supports cryptocurrency: 0.00000001 BTC (satoshi)
- Supports equities: $9,999,999.99 (high-priced stocks)
- Total range: -999,999,999.99999999 to +999,999,999.99999999

**Partition Strategy:**
- **Level 1:** Year (`year=2023`)
- **Level 2:** Month (`month=01`)
- **Rationale:** Balances query efficiency (prune full years/months) with file size (~10MB/month/3000 assets)

**Compression:**
- **Algorithm:** ZSTD level 3
- **Rationale:** Better compression than Snappy (50-60% vs 30-40%) with acceptable decompression speed
- **Expected Size:** 50-80% reduction vs HDF5 baseline

**Schema Evolution:**
- Store schema version in Parquet metadata: `schema_version=1`
- Add new optional columns without breaking existing readers
- Document breaking changes in migration guide

### Minute Bars Schema

```python
MINUTE_BARS_SCHEMA = {
    "timestamp": pl.Datetime("us"),           # Timestamp with microsecond precision (UTC)
    "sid": pl.Int64,                          # Security ID (asset identifier)
    "open": pl.Decimal(precision=18, scale=8),  # Opening price
    "high": pl.Decimal(precision=18, scale=8),  # Highest price
    "low": pl.Decimal(precision=18, scale=8),   # Lowest price
    "close": pl.Decimal(precision=18, scale=8), # Closing price
    "volume": pl.Decimal(precision=18, scale=8), # Trading volume
}
```

**Partition Strategy:**
- **Level 1:** Year (`year=2023`)
- **Level 2:** Month (`month=01`)
- **Level 3:** Day (`day=01`)
- **Rationale:** Minimize data scanned for intraday queries (~500MB/day/3000 assets)

**Compression:** Same as daily bars (ZSTD level 3)

---

## SQLite Metadata Catalog Schema

**Location:** `data/bundles/{bundle_name}/metadata.db`

### datasets Table

```sql
CREATE TABLE datasets (
    dataset_id TEXT PRIMARY KEY,              -- UUID v4 identifier
    source TEXT NOT NULL,                     -- 'ccxt:binance', 'yfinance', 'csv:custom'
    resolution TEXT NOT NULL,                 -- '1d', '1h', '1m', etc.
    start_date INTEGER NOT NULL,              -- Unix timestamp (UTC)
    end_date INTEGER NOT NULL,                -- Unix timestamp (UTC)
    checksum TEXT NOT NULL,                   -- SHA256 of Parquet files
    parquet_path TEXT NOT NULL,               -- Relative path to Parquet directory
    created_at INTEGER NOT NULL,              -- Unix timestamp
    last_updated INTEGER NOT NULL,            -- Unix timestamp
    row_count INTEGER NOT NULL,               -- Total rows in dataset
    size_bytes INTEGER NOT NULL               -- Total size in bytes
);

CREATE INDEX idx_datasets_source ON datasets(source);
CREATE INDEX idx_datasets_resolution ON datasets(resolution);
CREATE INDEX idx_datasets_dates ON datasets(start_date, end_date);
```

### symbols Table

```sql
CREATE TABLE symbols (
    symbol_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    symbol TEXT NOT NULL,                     -- 'AAPL', 'BTC/USDT', etc.
    asset_type TEXT NOT NULL,                 -- 'equity', 'cryptocurrency', 'future'
    exchange TEXT,                            -- 'NYSE', 'binance', etc.
    metadata TEXT,                            -- JSON with additional metadata
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    UNIQUE(dataset_id, symbol)
);

CREATE INDEX idx_symbols_dataset ON symbols(dataset_id);
CREATE INDEX idx_symbols_symbol ON symbols(symbol);
```

### date_ranges Table

```sql
CREATE TABLE date_ranges (
    range_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    start_date INTEGER NOT NULL,              -- Unix timestamp
    end_date INTEGER NOT NULL,                -- Unix timestamp
    bar_count INTEGER NOT NULL,               -- Number of bars in range
    has_gaps BOOLEAN DEFAULT 0,               -- True if missing data detected
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
);

CREATE INDEX idx_date_ranges_dataset ON date_ranges(dataset_id);
CREATE INDEX idx_date_ranges_symbol ON date_ranges(symbol);
```

### checksums Table

```sql
CREATE TABLE checksums (
    checksum_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    file_path TEXT NOT NULL,                  -- Parquet file path
    checksum TEXT NOT NULL,                   -- SHA256 of file
    last_validated INTEGER NOT NULL,          -- Unix timestamp
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    UNIQUE(dataset_id, file_path)
);

CREATE INDEX idx_checksums_dataset ON checksums(dataset_id);
```

### backtest_data_links Table

```sql
CREATE TABLE backtest_data_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id TEXT NOT NULL,                -- Backtest identifier (UUID)
    dataset_id TEXT NOT NULL,
    cached_at INTEGER NOT NULL,               -- Unix timestamp when cached
    cache_key TEXT NOT NULL,                  -- Cache key for lookup
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
);

CREATE INDEX idx_backtest_links_backtest ON backtest_data_links(backtest_id);
CREATE INDEX idx_backtest_links_dataset ON backtest_data_links(dataset_id);
CREATE INDEX idx_backtest_links_cache_key ON backtest_data_links(cache_key);
```

**Usage Example:**
```python
# Find all datasets for backtest
cursor.execute("""
    SELECT d.dataset_id, d.source, d.resolution, d.start_date, d.end_date
    FROM datasets d
    JOIN backtest_data_links bdl ON d.dataset_id = bdl.dataset_id
    WHERE bdl.backtest_id = ?
""", (backtest_id,))
```

---

## Caching Strategy

### Two-Tier Cache Architecture

**Tier 1: Hot Cache (In-Memory)**
- **Storage:** `OrderedDict[cache_key, pl.LazyFrame]`
- **Max Size:** 1GB (configurable via `RUSTYBT_HOT_CACHE_SIZE_MB`)
- **Eviction:** LRU (Least Recently Used)
- **Latency:** <1ms for cache hits
- **Use Case:** Recently accessed datasets (last 10-50 queries)

**Tier 2: Cold Cache (Disk Parquet)**
- **Storage:** Parquet files in `{cache_dir}/cold_cache/`
- **Max Size:** 50GB (configurable via `RUSTYBT_COLD_CACHE_SIZE_MB`)
- **Eviction:** LRU with periodic cleanup (hourly)
- **Latency:** 10-100ms for cache hits (depending on file size)
- **Use Case:** Frequently reused datasets across backtests

### Cache Key Design

**Format:**
```python
cache_key = SHA256(
    symbols: List[str] (sorted),
    start_date: str (ISO8601),
    end_date: str (ISO8601),
    resolution: str,
    source: str,
)
```

**Example:**
```python
import hashlib
import json

cache_params = {
    "symbols": ["AAPL", "GOOG", "MSFT"],  # Sorted
    "start_date": "2023-01-01T00:00:00Z",
    "end_date": "2023-12-31T23:59:59Z",
    "resolution": "1d",
    "source": "yfinance",
}
cache_key = hashlib.sha256(
    json.dumps(cache_params, sort_keys=True).encode()
).hexdigest()
# Result: "a3f5b2c1d4e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2"
```

**Cache Hit Logic:**
1. Generate cache key from query parameters
2. Check hot cache (OrderedDict lookup)
3. If miss, check cold cache (Parquet file exists?)
4. If miss, fetch from BarReader and populate both caches

### Cache Invalidation Strategy

**Triggers:**
1. **Checksum Mismatch:** Dataset checksum in catalog differs from cached version
2. **Manual Refresh:** User calls `cache_manager.invalidate(cache_key)`
3. **TTL Expiration:** Time-to-live exceeded (default: 7 days)
4. **Upstream Update:** Data adapter reports new data available

**Invalidation Flow:**
```python
def check_cache_validity(cache_key: str, dataset_id: str) -> bool:
    """Check if cache entry is still valid.

    Args:
        cache_key: Cache key
        dataset_id: Dataset ID from catalog

    Returns:
        True if valid, False if invalidated
    """
    # 1. Check if entry exists
    if cache_key not in cache_manager._hot_cache:
        cold_cache_path = cache_manager._get_cold_cache_path(cache_key)
        if not cold_cache_path.exists():
            return False  # Cache miss

    # 2. Get cached dataset checksum
    cached_checksum = cache_manager._get_cached_checksum(cache_key)

    # 3. Get current dataset checksum from catalog
    current_checksum = data_catalog.get_dataset_info(dataset_id)["checksum"]

    # 4. Compare checksums
    if cached_checksum != current_checksum:
        cache_manager.invalidate(cache_key)
        return False  # Invalidated

    # 5. Check TTL
    cached_at = cache_manager._get_cached_at(cache_key)
    ttl_seconds = config.get("cache_ttl_seconds", 7 * 24 * 3600)  # 7 days
    if (pd.Timestamp.now() - cached_at).total_seconds() > ttl_seconds:
        cache_manager.invalidate(cache_key)
        return False  # Expired

    return True  # Valid
```

### Backtest Linkage Mechanism

**Purpose:** Track which datasets were used by which backtests to enable cache reuse across similar backtests.

**Workflow:**
1. **During Backtest Initialization:**
   - Generate cache key for each data query
   - Check if dataset exists in catalog
   - If exists, link backtest to dataset in `backtest_data_links` table
   - If not, fetch data, create dataset, then link

2. **Cache Reuse Scenario:**
   ```python
   # Backtest A: AAPL, MSFT daily data 2023-01-01 to 2023-12-31
   backtest_a_id = "uuid-backtest-a"
   dataset_id_1 = "uuid-dataset-1"
   cache_key_1 = "hash-of-aapl-msft-2023-daily"

   # Link backtest A to dataset
   data_catalog.link_backtest_to_dataset(
       backtest_a_id, dataset_id_1, pd.Timestamp.now()
   )

   # Backtest B: Same symbols/dates/resolution
   backtest_b_id = "uuid-backtest-b"
   # Cache hit! Reuse dataset_id_1 and cache_key_1
   # Link backtest B to same dataset
   data_catalog.link_backtest_to_dataset(
       backtest_b_id, dataset_id_1, pd.Timestamp.now()
   )
   ```

3. **Benefits:**
   - Audit trail: which backtests used which data
   - Cache warming: pre-load hot cache for frequently used datasets
   - Analytics: identify most popular datasets for optimization

---

## Migration Plan from HDF5 to Parquet

### Conversion Utility Workflow

**Tool:** `rustybt/data/bundles/migration.py`

**Steps:**
1. **Scan HDF5 Bundle:**
   - Detect all HDF5 files in bundle directory
   - Read metadata (symbols, date ranges, resolution)

2. **Read HDF5 Data:**
   - Load OHLCV data from HDF5 into pandas DataFrame
   - Convert float64 columns to Decimal

3. **Validate Data:**
   - Run OHLCV relationship checks
   - Detect and log any anomalies

4. **Write to Parquet:**
   - Partition by (year, month) for daily or (year, month, day) for minute
   - Apply ZSTD compression
   - Write Decimal columns using Polars

5. **Register in Catalog:**
   - Calculate checksums
   - Create dataset entry in SQLite metadata catalog

6. **Verify Migration:**
   - Checksum comparison (HDF5 vs Parquet)
   - Row count validation
   - Spot check random samples

**Command-Line Interface:**
```bash
# Migrate single bundle
rustybt ingest migrate-hdf5-to-parquet \
    --bundle quandl \
    --source-dir data/bundles/quandl \
    --output-dir data/bundles/quandl_parquet \
    --validate

# Migrate all bundles
rustybt ingest migrate-hdf5-to-parquet \
    --all \
    --validate \
    --parallel 4
```

**Example Migration Code:**
```python
from rustybt.data.bundles.migration import HDF5ToParquetMigrator

migrator = HDF5ToParquetMigrator(
    source_bundle_dir="data/bundles/quandl",
    output_bundle_dir="data/bundles/quandl_parquet",
)

# Run migration
result = migrator.migrate(
    validate=True,           # Run validation after migration
    keep_hdf5=True,          # Keep original HDF5 files
    compression="zstd",      # ZSTD compression
    compression_level=3,     # Level 3 for balance
)

print(f"Migrated {result['row_count']} rows")
print(f"HDF5 size: {result['hdf5_size_mb']} MB")
print(f"Parquet size: {result['parquet_size_mb']} MB")
print(f"Compression ratio: {result['compression_ratio']:.2%}")
```

### Validation Strategy

**Checksums:**
- Calculate SHA256 of HDF5 data (after sorting)
- Calculate SHA256 of Parquet data (after sorting)
- Compare checksums to ensure data integrity

**Row Count Validation:**
```python
hdf5_row_count = len(hdf5_df)
parquet_row_count = len(pl.read_parquet(parquet_path))
assert hdf5_row_count == parquet_row_count, "Row count mismatch!"
```

**Spot Check Random Samples:**
```python
# Sample 1000 random rows
sample_indices = np.random.choice(len(hdf5_df), size=1000, replace=False)
hdf5_sample = hdf5_df.iloc[sample_indices]
parquet_sample = parquet_df.filter(pl.col("row_id").is_in(sample_indices))

# Compare Decimal precision
for col in ["open", "high", "low", "close", "volume"]:
    hdf5_values = hdf5_sample[col].apply(Decimal)
    parquet_values = parquet_sample[col].to_list()
    assert all(hdf5_values == parquet_values), f"Mismatch in {col}!"
```

### Parallel Path Support

**Feature Flag:** `RUSTYBT_USE_POLARS`

**Behavior:**
- If `RUSTYBT_USE_POLARS=1`: Use PolarsDataPortal and Parquet readers
- If `RUSTYBT_USE_POLARS=0`: Use Zipline's DataPortal and HDF5/bcolz readers

**Implementation:**
```python
# In rustybt/__init__.py
import os

USE_POLARS = os.environ.get("RUSTYBT_USE_POLARS", "1") == "1"

if USE_POLARS:
    from rustybt.data.polars import PolarsDataPortal as DataPortal
else:
    from zipline.data.data_portal import DataPortal
```

**Migration Strategy:**
1. **Phase 1 (Weeks 1-2):** Implement Parquet writers and readers, feature flag off by default
2. **Phase 2 (Weeks 3-4):** Enable feature flag for new bundles, run parallel validation
3. **Phase 3 (Weeks 5-6):** Migrate existing bundles, validate with production backtests
4. **Phase 4 (Week 7):** Enable feature flag by default, deprecate HDF5
5. **Phase 5 (Week 8+):** Remove HDF5 support after 3-month grace period

### Rollback Plan

**If migration issues occur:**
1. **Immediate:** Disable feature flag (`RUSTYBT_USE_POLARS=0`)
2. **Restore:** HDF5/bcolz bundles are preserved (not deleted during migration)
3. **Debug:** Analyze discrepancies between HDF5 and Parquet
4. **Fix:** Patch migration utility and re-run
5. **Validate:** Run comprehensive test suite before re-enabling

**Rollback Command:**
```bash
# Revert to HDF5
export RUSTYBT_USE_POLARS=0
rustybt run my_strategy.py --bundle quandl

# Delete failed Parquet migration
rm -rf data/bundles/quandl_parquet
```

---

## Interface Contracts

### DataCatalog Interface

```python
from typing import List, Optional
import pandas as pd

class DataCatalog:
    def register_dataset(
        self,
        source: str,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        checksum: str,
    ) -> str:
        """Register new dataset in catalog."""

    def find_dataset(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        source: Optional[str] = None,
    ) -> Optional[str]:
        """Find existing dataset matching criteria."""

    def get_dataset_info(self, dataset_id: str) -> dict:
        """Get full dataset metadata."""

    def link_backtest_to_dataset(
        self,
        backtest_id: str,
        dataset_id: str,
        cached_at: pd.Timestamp,
    ):
        """Link backtest to dataset for cache tracking."""
```

### CacheManager Interface

```python
from typing import List, Optional
import polars as pl
import pandas as pd

class CacheManager:
    def get(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        source: str,
    ) -> Optional[pl.LazyFrame]:
        """Get data from cache."""

    def put(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        source: str,
        data: pl.LazyFrame,
    ):
        """Put data into cache."""

    def invalidate(self, cache_key: str):
        """Invalidate cache entry."""

    def clear(self):
        """Clear entire cache."""
```

### BaseDataAdapter Interface

```python
from abc import ABC, abstractmethod
import polars as pl
import pandas as pd
from typing import List

class BaseDataAdapter(ABC):
    @abstractmethod
    async def fetch(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from source."""

    @abstractmethod
    def validate(self, df: pl.DataFrame) -> bool:
        """Validate OHLCV relationships and data quality."""

    @abstractmethod
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider-specific format to RustyBT schema."""
```

---

## Performance Targets

### Cache Performance

- **Hot Cache Hit:** <1ms latency
- **Cold Cache Hit:** 10-100ms latency (depending on file size)
- **Cache Miss:** Variable (depends on data source and network)

### Parquet Compression

- **Target:** 50-80% size reduction vs HDF5 baseline
- **Measured:** ZSTD level 3 compression
- **Benchmark:** 100MB HDF5 → 20-50MB Parquet

### Lazy Loading

- **Memory Efficiency:** Load only required partitions into memory
- **Partition Pruning:** Skip irrelevant year/month/day directories
- **Example:** Query Q1 2023 data from 10-year dataset → Load only 3 months

### Multi-Resolution Aggregation

- **Use Case:** Aggregate minute bars to daily bars on-the-fly
- **Performance:** 10-50ms for typical dataset (1000 symbols, 1 day)
- **Implementation:** Polars lazy evaluation with `group_by("date").agg()`

---

## Data Flow Diagrams

### Data Ingestion Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. User triggers data ingestion                                │
│     rustybt ingest --source ccxt:binance --symbols BTC/USDT ... │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. DataAdapter.fetch()                                         │
│     - Connect to CCXT API                                       │
│     - Fetch OHLCV data for symbols/date range                   │
│     - Return Polars DataFrame (raw data)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. DataAdapter.validate()                                      │
│     - Check OHLCV relationships                                 │
│     - Detect outliers                                           │
│     - Verify temporal consistency                               │
│     - Raise ValidationError if issues found                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. DataAdapter.standardize()                                   │
│     - Convert to RustyBT schema (Decimal columns)               │
│     - Add sid column (asset ID)                                 │
│     - Standardize timezone (UTC)                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. ParquetWriter.write()                                       │
│     - Partition by (year, month) or (year, month, day)          │
│     - Apply ZSTD compression                                    │
│     - Write to data/bundles/{bundle}/daily_bars/ or minute_bars/│
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  6. DataCatalog.register_dataset()                              │
│     - Calculate checksum (SHA256)                               │
│     - Insert into datasets, symbols, date_ranges tables         │
│     - Return dataset_id                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Data Query Flow (with Caching)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. User strategy calls data.history()                          │
│     df = data.history(assets=[AAPL, MSFT], bars=30, freq='1d') │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. PolarsDataPortal generates cache key                        │
│     cache_key = hash(symbols, start_date, end_date, resolution) │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. CacheManager.get(cache_key)                                 │
│     ├─ Check hot cache (in-memory OrderedDict)                  │
│     │  └─ HIT? → Return Polars LazyFrame                        │
│     ├─ Check cold cache (disk Parquet)                          │
│     │  └─ HIT? → Load to hot cache → Return                     │
│     └─ MISS? → Continue to step 4                               │
└────────────────────────────┬────────────────────────────────────┘
                             │ Cache Miss
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. DataCatalog.find_dataset()                                  │
│     - Query SQLite for matching dataset                         │
│     - Check if checksum matches cached version                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  5. BarReader.load_raw_arrays()                                 │
│     - Scan Parquet files with partition pruning                 │
│     - Filter by sids and date range                             │
│     - Return Polars LazyFrame (Decimal columns)                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  6. CacheManager.put(cache_key, data)                           │
│     - Store in hot cache (in-memory)                            │
│     - Write to cold cache (Parquet file)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  7. Return Polars DataFrame to user strategy                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration Examples

### Data Catalog Configuration

```yaml
# config/data_catalog.yaml

catalog:
  metadata_db: "data/bundles/metadata.db"
  parquet_dir: "data/bundles"

cache:
  hot_cache_size_mb: 1024          # 1GB in-memory cache
  cold_cache_size_mb: 51200        # 50GB disk cache
  cache_dir: "data/cache"
  ttl_seconds: 604800              # 7 days
  eviction_policy: "lru"

parquet:
  compression: "zstd"
  compression_level: 3
  partition_strategy:
    daily: ["year", "month"]
    minute: ["year", "month", "day"]

validation:
  ohlcv_checks: true
  outlier_detection: true
  outlier_std_threshold: 3.0
  temporal_consistency: true
```

### Data Adapter Configuration

```yaml
# config/data_adapters.yaml

adapters:
  ccxt:
    exchange: "binance"
    testnet: false
    rate_limit: true
    timeout: 30000                # 30 seconds
    retry_attempts: 3
    retry_delay: 5000             # 5 seconds

  yfinance:
    timeout: 30
    retry_attempts: 3
    adjusted_prices: false        # Use unadjusted prices

  csv:
    schema_mapping:
      date_column: "Date"
      open_column: "Open"
      high_column: "High"
      low_column: "Low"
      close_column: "Close"
      volume_column: "Volume"
    date_format: "%Y-%m-%d"
    delimiter: ","
    timezone: "UTC"
```

---

## Testing Strategy

### Unit Tests

**Test File:** `tests/data/polars/test_catalog.py`

**Coverage:**
- DataCatalog registration and lookup
- Cache key generation (deterministic)
- Checksum calculation and validation
- SQLite metadata CRUD operations

**Example Test:**
```python
def test_cache_key_generation():
    """Cache key must be deterministic and unique."""
    cache_manager = CacheManager(cache_dir="/tmp/cache")

    key1 = cache_manager._generate_cache_key(
        symbols=["AAPL", "MSFT"],
        start_date=pd.Timestamp("2023-01-01"),
        end_date=pd.Timestamp("2023-12-31"),
        resolution="1d",
        source="yfinance",
    )

    key2 = cache_manager._generate_cache_key(
        symbols=["MSFT", "AAPL"],  # Different order
        start_date=pd.Timestamp("2023-01-01"),
        end_date=pd.Timestamp("2023-12-31"),
        resolution="1d",
        source="yfinance",
    )

    # Cache keys must be identical (symbols sorted)
    assert key1 == key2
```

### Integration Tests

**Test File:** `tests/data/polars/test_parquet_roundtrip.py`

**Coverage:**
- Write Polars DataFrame to Parquet
- Read back and verify Decimal precision
- Partition pruning correctness
- Compression ratio validation

**Example Test:**
```python
def test_parquet_decimal_roundtrip():
    """Decimal precision must be preserved in Parquet roundtrip."""
    from decimal import Decimal
    import polars as pl

    # Create test data with Decimal
    df = pl.DataFrame({
        "date": [pl.Date(2023, 1, 1)],
        "sid": [1],
        "close": [Decimal("123.45678901")],
    }, schema=DAILY_BARS_SCHEMA)

    # Write to Parquet
    parquet_path = "/tmp/test_decimal.parquet"
    df.write_parquet(parquet_path, compression="zstd")

    # Read back
    df_read = pl.read_parquet(parquet_path)

    # Verify Decimal precision preserved
    assert df_read["close"][0] == Decimal("123.45678901")
    assert isinstance(df_read["close"][0], Decimal)
```

### Property-Based Tests

**Test File:** `tests/data/polars/test_validation.py`

**Coverage:**
- OHLCV relationship invariants (high >= low, etc.)
- Cache key uniqueness (different inputs → different keys)
- Partition pruning correctness (only required partitions loaded)

**Example Test:**
```python
from hypothesis import given, strategies as st
import polars as pl
from decimal import Decimal

@given(
    open_price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000")),
    high_offset=st.decimals(min_value=Decimal("0"), max_value=Decimal("100")),
    low_offset=st.decimals(min_value=Decimal("0"), max_value=Decimal("100")),
)
def test_ohlcv_invariants(open_price, high_offset, low_offset):
    """OHLCV relationships must always hold."""
    high = open_price + high_offset
    low = max(open_price - low_offset, Decimal("0.01"))
    close = (high + low) / 2

    df = pl.DataFrame({
        "open": [open_price],
        "high": [high],
        "low": [low],
        "close": [close],
    })

    # Validate
    adapter = BaseDataAdapter()
    assert adapter.validate(df) == True

    # Invariants
    assert df["high"][0] >= df["low"][0]
    assert df["high"][0] >= df["open"][0]
    assert df["low"][0] <= df["close"][0]
```

### Performance Benchmarks

**Test File:** `tests/data/polars/test_benchmarks.py`

**Coverage:**
- Cache hit latency (<1ms for hot, <100ms for cold)
- Parquet compression ratio (50-80% reduction)
- Lazy loading memory efficiency
- Query performance with partition pruning

**Example Benchmark:**
```python
import pytest
import time
import polars as pl

@pytest.mark.benchmark
def test_cache_hit_latency(benchmark):
    """Hot cache hit must return in <1ms."""
    cache_manager = CacheManager(cache_dir="/tmp/cache")

    # Pre-populate cache
    cache_manager.put(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2023-01-01"),
        end_date=pd.Timestamp("2023-12-31"),
        resolution="1d",
        source="yfinance",
        data=pl.LazyFrame({"close": [100.0]}),
    )

    # Benchmark cache hit
    def cache_hit():
        return cache_manager.get(
            symbols=["AAPL"],
            start_date=pd.Timestamp("2023-01-01"),
            end_date=pd.Timestamp("2023-12-31"),
            resolution="1d",
            source="yfinance",
        )

    result = benchmark(cache_hit)
    assert result.stats.mean < 0.001  # <1ms
```

---

## Security Considerations

### Data Integrity

1. **Checksums:** SHA256 checksums for all Parquet files to detect corruption
2. **Validation:** OHLCV relationship checks before ingestion
3. **Audit Trail:** All data modifications logged in `order_audit_log` table

### Access Control

1. **File Permissions:** Parquet files readable by backtest process only (chmod 600)
2. **API Keys:** Data adapter credentials encrypted at rest (AES-256)
3. **Database:** SQLite metadata database with write access restricted

### Data Privacy

1. **PII:** No personally identifiable information stored in OHLCV data
2. **Compliance:** Data retention policies configurable (default: 5 years)
3. **Anonymization:** Backtest IDs are UUIDs (no user identification)

---

## Future Enhancements

### Phase 2 (Post-MVP)

1. **Distributed Caching:** Redis integration for multi-node cache sharing
2. **Incremental Updates:** Fetch only new bars since last update
3. **Real-Time Streaming:** WebSocket data feeds for live trading
4. **Data Quality Dashboard:** Visualize data gaps, outliers, validation failures
5. **Multi-Source Merging:** Combine data from multiple providers with conflict resolution

### Phase 3 (Advanced Features)

1. **Data Versioning:** Track schema changes over time with migration paths
2. **Time Travel Queries:** Query historical versions of datasets
3. **Federated Queries:** Query across multiple bundles/exchanges
4. **ML Feature Store:** Pre-compute technical indicators and store in Parquet

---

## References

### Internal Documentation

- [Tech Stack](tech-stack.md): Technology selection rationale
- [Component Architecture](component-architecture.md): Detailed component designs
- [Data Models and Schema Changes](data-models-and-schema-changes.md): Database schemas
- [Coding Standards](coding-standards.md): Python and Decimal best practices
- [Testing Strategy](testing-strategy.md): Test coverage requirements

### External Resources

- [Polars Documentation](https://pola-rs.github.io/polars/): Polars API reference
- [Apache Parquet Format](https://parquet.apache.org/docs/): Parquet specification
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/): Database abstraction layer
- [CCXT Documentation](https://docs.ccxt.com/): Crypto exchange API library
- [yfinance Documentation](https://github.com/ranaroussi/yfinance): Yahoo Finance API

---

## Change Log

| Date       | Version | Description                          | Author       |
|------------|---------|--------------------------------------|--------------|
| 2025-10-01 | 1.0     | Initial architecture design          | James (Dev)  |

---

**Document Status:** ✅ Design Complete - Ready for Implementation
