# Epic X1: Unified Data Architecture - Technical Design

**Version:** 1.0
**Date:** 2025-10-05
**Status:** Planning
**Epic PRD:** [epic-X1-unified-data-architecture.md](../prd/epic-X1-unified-data-architecture.md)

---

## Architecture Overview

### Current Fragmented State

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: DATA ADAPTERS (Epic 6)                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ YFinance   │  │ CCXT       │  │ Polygon    │  │ CSV      │  │
│  │ Adapter    │  │ Adapter    │  │ Adapter    │  │ Adapter  │  │
│  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │
│         ↓ fetch_ohlcv() → Polars DataFrame                      │
│  Problem: No bundle creation capability                         │
└─────────────────────────────────────────────────────────────────┘
                             ↓ (MANUAL INTEGRATION REQUIRED)
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: BUNDLE SYSTEM (Zipline Legacy)                        │
│  ┌───────────────────┐  ┌──────────────────┐                    │
│  │ quandl_bundle()   │  │ csvdir_bundle()  │                    │
│  │ (manual script)   │  │ (manual script)  │                    │
│  └───────────────────┘  └──────────────────┘                    │
│         ↓ writes to                                             │
│  ┌───────────────────────────────────────────────────┐          │
│  │ Parquet Storage + AssetDB                         │          │
│  │ - daily_bars/, minute_bars/                       │          │
│  │ - assets-8.sqlite (symbol metadata)               │          │
│  └───────────────────────────────────────────────────┘          │
│  Problem: Adapter-specific ingest scripts required              │
└─────────────────────────────────────────────────────────────────┘
                             ↓ (NO INTEGRATION)
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: METADATA CATALOGS (2 separate systems)                │
│  ┌─────────────────────┐   ┌──────────────────────────────┐    │
│  │ DataCatalog         │   │ ParquetMetadataCatalog       │    │
│  │ - Provenance        │   │ - Symbol metadata            │    │
│  │ - Quality metrics   │   │ - File checksums             │    │
│  │ - Bundle discovery  │   │ - Cache management           │    │
│  │                     │   │ - Date ranges                │    │
│  │ (global scope)      │   │ (per-bundle scope)           │    │
│  └─────────────────────┘   └──────────────────────────────┘    │
│  Problem: Duplicate functionality, inconsistent tracking        │
└─────────────────────────────────────────────────────────────────┘

CRITICAL ISSUES:
❌ Epic 7 BLOCKED: Cannot create profiling bundles from adapters
❌ Manual scripting required for each data source
❌ Metadata fragmented across 2 independent systems (duplication)
❌ No cache optimization (redundant API calls)
❌ No live/backtest data sharing
```

### Target Unified State

```
┌─────────────────────────────────────────────────────────────────┐
│  DATASOURCE LAYER (Unified Interface)                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  DataSource ABC (base interface)                         │   │
│  │  - fetch(symbols, start, end, freq) → DataFrame          │   │
│  │  - ingest_to_bundle(bundle_name, **kwargs)               │   │
│  │  - get_metadata() → {provenance, quality}                │   │
│  │  - supports_live() → bool                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓ implements                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ YFinance   │  │ CCXT       │  │ Polygon    │  │ CSV      │  │
│  │ Source     │  │ Source     │  │ Source     │  │ Source   │  │
│  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │
│         ↓                ↓                ↓              ↓      │
│    Unified bundle creation (single code path)                   │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  CACHING LAYER (Smart Cache + Freshness)                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  CachedDataSource (transparent wrapper)                  │   │
│  │  1. Metadata lookup: bundle exists for (symbols, dates)? │   │
│  │  2. Freshness check: is cached data stale?               │   │
│  │  3. Cache HIT → Read Parquet (fast path <100ms)          │   │
│  │  4. Cache MISS → Adapter fetch → Write bundle            │   │
│  │  5. Update metadata (provenance + quality)               │   │
│  │  6. Track cache stats (hit/miss rate)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  BUNDLE STORAGE (Parquet + Unified Metadata)                    │
│  ┌──────────────────────┐  ┌───────────────────────────────┐   │
│  │ Parquet Files        │  │ BundleMetadata (SQLite)       │   │
│  │ - daily_bars/        │  │ [Replaces 2 catalog systems]  │   │
│  │ - minute_bars/       │  │                               │   │
│  │ - OHLCV Decimal      │  │ Merged DataCatalog fields:    │   │
│  │                      │  │ - source_url, api_version     │   │
│  │                      │  │ - fetch_timestamp             │   │
│  │                      │  │ - quality metrics (missing    │   │
│  │                      │  │   days, ohlcv_violations)     │   │
│  │                      │  │                               │   │
│  │                      │  │ Merged ParquetCatalog fields: │   │
│  │                      │  │ - symbols (asset_type, exch)  │   │
│  │                      │  │ - file_checksum, size_bytes   │   │
│  │                      │  │ - cache (LRU, hit/miss stats) │   │
│  └──────────────────────┘  └───────────────────────────────┘   │
│           ↓                              ↓                      │
│  AssetDB (symbol info)       Single metadata store             │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│  DATAPORTAL (Unified Access - Unchanged API)                    │
│  - data.current(assets, field)                                  │
│  - data.history(assets, field, bar_count)                       │
│  - Same API for live trading and backtesting                    │
└─────────────────────────────────────────────────────────────────┘

BENEFITS:
✅ Adapters auto-create bundles (Epic 7 unblocked)
✅ Single metadata store (no duplication)
✅ Smart caching (>80% hit rate, 10x faster than API)
✅ Live/backtest data sharing
✅ Backwards compatible (old APIs deprecated, not removed)
```

---

## Component Design

### 1. DataSource Interface (Story X1.2)

**File**: `rustybt/data/sources/base.py`

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import polars as pl
import pandas as pd
from decimal import Decimal

class DataSource(ABC):
    """Unified interface for all data sources (adapters + bundles).

    Provides:
    - Data fetching (fetch)
    - Bundle creation (ingest_to_bundle)
    - Metadata tracking (get_metadata)
    - Live trading support query (supports_live)
    """

    @abstractmethod
    async def fetch(
        self,
        symbols: List[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,  # '1d', '1h', '1m', etc.
    ) -> pl.DataFrame:
        """Fetch OHLCV data for symbols.

        Returns:
            Polars DataFrame with columns:
            - timestamp, symbol, open, high, low, close, volume (all Decimal)
        """
        pass

    @abstractmethod
    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: List[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs,
    ) -> None:
        """Ingest data into bundle format.

        Automatically:
        - Fetches data via self.fetch()
        - Writes to Parquet via ParquetWriter
        - Updates BundleMetadata (provenance + quality)
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Get source metadata (provenance).

        Returns:
            {
                'source_type': 'yfinance',
                'source_url': 'https://query2.finance.yahoo.com/...',
                'api_version': 'v8',
                'supports_live': False
            }
        """
        pass

    @abstractmethod
    def supports_live(self) -> bool:
        """Whether source supports live streaming data.

        Returns:
            True: CCXT (WebSocket), Polygon (WebSocket)
            False: YFinance (15min delay), CSV (static)
        """
        pass
```

**Implementation Example** (YFinanceAdapter):

```python
from rustybt.data.adapters.base import BaseDataAdapter
from rustybt.data.sources.base import DataSource
from rustybt.data.polars.parquet_writer import ParquetWriter
from rustybt.data.bundles.metadata import BundleMetadata

class YFinanceDataSource(BaseDataAdapter, DataSource):
    """YFinance implementation of DataSource."""

    async def fetch(self, symbols, start, end, frequency):
        # Existing adapter logic
        return await self.fetch_ohlcv(symbols, start, end, frequency)

    def ingest_to_bundle(self, bundle_name, symbols, start, end, frequency, **kwargs):
        # NEW: Unified bundle creation
        df = self.fetch(symbols, start, end, frequency)

        # Write Parquet
        writer = ParquetWriter(bundle_path=f"~/.zipline/data/{bundle_name}")
        writer.write_daily_bars(df) if frequency == '1d' else writer.write_minute_bars(df)

        # Update metadata (replaces DataCatalog)
        metadata = self.get_metadata()
        BundleMetadata.update(
            bundle_name=bundle_name,
            source_type=metadata['source_type'],
            source_url=metadata['source_url'],
            api_version=metadata['api_version'],
            fetch_timestamp=int(time.time()),
            file_checksum=calculate_checksum(writer.output_path),
            row_count=len(df)
        )

        # Validate quality (replaces DataCatalog)
        quality = validate_ohlcv(df)
        BundleMetadata.update_quality(
            bundle_name=bundle_name,
            missing_days_count=quality.missing_days,
            ohlcv_violations=quality.violations,
            validation_passed=quality.is_valid
        )

    def get_metadata(self):
        return {
            'source_type': 'yfinance',
            'source_url': 'https://query2.finance.yahoo.com/v8/finance/chart',
            'api_version': 'v8',
            'supports_live': False
        }

    def supports_live(self):
        return False  # YFinance has 15min delay
```

---

### 2. Unified Metadata Schema (Story X1.4)

**Key Decision**: Merge catalog functionality into `BundleMetadata`, not separate class

**Extended Schema**: `rustybt/data/bundles/metadata_schema.py`

```sql
-- Base bundle metadata (existing)
CREATE TABLE bundle_metadata (
    bundle_name TEXT PRIMARY KEY,
    calendar_name TEXT NOT NULL,
    start_session INTEGER NOT NULL,
    end_session INTEGER NOT NULL,

    -- MERGED from DataCatalog (provenance tracking)
    source_type TEXT,          -- 'yfinance', 'ccxt', 'csv'
    source_url TEXT,           -- API endpoint URL
    api_version TEXT,          -- API version identifier
    fetch_timestamp INTEGER,   -- Unix timestamp when fetched
    data_version TEXT,         -- Data version from API
    timezone TEXT DEFAULT 'UTC',

    -- MERGED from DataCatalog (quality metrics)
    row_count INTEGER,
    missing_days_count INTEGER DEFAULT 0,
    missing_days_list TEXT DEFAULT '[]',  -- JSON array
    outlier_count INTEGER DEFAULT 0,
    ohlcv_violations INTEGER DEFAULT 0,
    validation_passed BOOLEAN DEFAULT TRUE,
    validation_timestamp INTEGER,

    -- MERGED from ParquetMetadataCatalog (file metadata)
    file_checksum TEXT,        -- SHA256 of Parquet files
    file_size_bytes INTEGER,

    -- Timestamps
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- MERGED from ParquetMetadataCatalog (symbol metadata)
CREATE TABLE bundle_symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT,           -- 'equity', 'crypto', 'future'
    exchange TEXT,             -- 'NYSE', 'binance'
    FOREIGN KEY (bundle_name) REFERENCES bundle_metadata(bundle_name)
);
CREATE INDEX idx_bundle_symbols_bundle ON bundle_symbols(bundle_name);
CREATE INDEX idx_bundle_symbols_symbol ON bundle_symbols(symbol);

-- MERGED from ParquetMetadataCatalog (cache management)
CREATE TABLE bundle_cache (
    cache_key TEXT PRIMARY KEY,
    bundle_name TEXT NOT NULL,
    parquet_path TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    last_accessed INTEGER NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 1,
    size_bytes INTEGER NOT NULL,
    FOREIGN KEY (bundle_name) REFERENCES bundle_metadata(bundle_name)
);
CREATE INDEX idx_bundle_cache_accessed ON bundle_cache(last_accessed);  -- LRU eviction
CREATE INDEX idx_bundle_cache_bundle ON bundle_cache(bundle_name);

-- MERGED from ParquetMetadataCatalog (cache statistics)
CREATE TABLE cache_statistics (
    stat_date INTEGER PRIMARY KEY,  -- Unix timestamp (day granularity)
    hit_count INTEGER DEFAULT 0,
    miss_count INTEGER DEFAULT 0,
    total_size_mb REAL DEFAULT 0.0,
    avg_fetch_latency_ms REAL DEFAULT 0.0
);
```

**Migration**: `scripts/migrate_catalog_to_bundle_metadata.py`

```python
def migrate_catalogs_to_bundle_metadata():
    """Merge DataCatalog + ParquetMetadataCatalog → BundleMetadata."""

    # Read old DataCatalog
    old_datacatalog = DataCatalog()
    bundles = old_datacatalog.list_bundles()

    for bundle in bundles:
        # Merge DataCatalog provenance
        BundleMetadata.update(
            bundle_name=bundle['bundle_name'],
            source_type=bundle['source_type'],
            source_url=bundle['source_url'],
            api_version=bundle['api_version'],
            fetch_timestamp=bundle['fetch_timestamp'],
        )

        # Merge DataCatalog quality
        quality = old_datacatalog.get_quality_metrics(bundle['bundle_name'])
        BundleMetadata.update_quality(
            bundle_name=bundle['bundle_name'],
            row_count=quality['row_count'],
            missing_days_count=quality['missing_days_count'],
            ohlcv_violations=quality['ohlcv_violations'],
            validation_passed=quality['validation_passed']
        )

    # Read old ParquetMetadataCatalog (per-bundle)
    for bundle_dir in Path("~/.zipline/data").iterdir():
        metadata_db = bundle_dir / "metadata.db"
        if not metadata_db.exists():
            continue

        parquet_catalog = ParquetMetadataCatalog(str(metadata_db))

        # Merge symbols
        symbols = parquet_catalog.get_all_symbols()
        for symbol in symbols:
            BundleMetadata.add_symbol(
                bundle_name=bundle_dir.name,
                symbol=symbol['symbol'],
                asset_type=symbol['asset_type'],
                exchange=symbol['exchange']
            )

        # Merge cache entries
        cache_entries = parquet_catalog.get_cache_entries()
        for entry in cache_entries:
            BundleMetadata.add_cache_entry(
                cache_key=entry['cache_key'],
                bundle_name=bundle_dir.name,
                parquet_path=entry['parquet_path'],
                last_accessed=entry['last_accessed'],
                size_bytes=entry['size_bytes']
            )

    print("✅ Migration complete. Old catalog data merged into BundleMetadata.")
```

---

### 3. Smart Caching (Story X1.3)

**File**: `rustybt/data/sources/cached_source.py`

```python
class CachedDataSource:
    """Transparent caching wrapper for DataSource."""

    def __init__(self, adapter: DataSource, cache_dir: Path):
        self.adapter = adapter
        self.cache_dir = cache_dir

    async def fetch(self, symbols, start, end, frequency):
        # 1. Generate cache key
        cache_key = self._generate_cache_key(symbols, start, end, frequency)

        # 2. Check if bundle exists
        bundle_name = BundleMetadata.find_cached(cache_key)
        if bundle_name:
            # 3. Check freshness
            if self._is_fresh(bundle_name, frequency):
                logger.info("cache_hit", cache_key=cache_key)
                BundleMetadata.increment_hit_count()
                return self._read_from_bundle(bundle_name)

        # 4. Cache miss → fetch from adapter
        logger.info("cache_miss", cache_key=cache_key)
        BundleMetadata.increment_miss_count()

        df = await self.adapter.fetch(symbols, start, end, frequency)

        # 5. Write to bundle
        bundle_name = f"cache-{cache_key}"
        self.adapter.ingest_to_bundle(bundle_name, symbols, start, end, frequency)

        # 6. Update cache metadata
        BundleMetadata.add_cache_entry(
            cache_key=cache_key,
            bundle_name=bundle_name,
            parquet_path=self.cache_dir / bundle_name,
            size_bytes=self._get_bundle_size(bundle_name)
        )

        # 7. Check cache size limit → LRU eviction
        self._enforce_cache_limit()

        return df

    def _is_fresh(self, bundle_name: str, frequency: str) -> bool:
        """Check if cached data is stale based on frequency."""
        metadata = BundleMetadata.get(bundle_name)
        fetch_timestamp = metadata['fetch_timestamp']
        now = int(time.time())

        if frequency == '1d':
            # Daily: refresh after market close (4:00 PM ET)
            market_close = self._get_last_market_close()
            return fetch_timestamp > market_close
        elif frequency == '1h':
            # Hourly: refresh every 1 hour
            return (now - fetch_timestamp) < 3600
        elif frequency == '1m':
            # Minute: refresh every 5 minutes
            return (now - fetch_timestamp) < 300
        else:
            return False  # Unknown frequency → treat as stale

    def _enforce_cache_limit(self):
        """LRU eviction to keep cache under max size."""
        max_size = Config.get('cache.max_size_bytes', default=10 * 1024**3)  # 10GB

        total_size = BundleMetadata.get_cache_size()
        if total_size < max_size:
            return  # Under limit

        # Evict LRU entries
        lru_entries = BundleMetadata.get_lru_cache_entries()
        for entry in lru_entries:
            self._delete_bundle(entry['bundle_name'])
            BundleMetadata.delete_cache_entry(entry['cache_key'])

            total_size -= entry['size_bytes']
            if total_size < max_size:
                break  # Under limit now

        logger.info("cache_eviction", evicted_count=len(lru_entries), new_size_mb=total_size / 1024**2)
```

---

## Integration with Existing Systems

### PolarsDataPortal (Story X1.5)

**Before** (current):
```python
class PolarsDataPortal:
    def __init__(self, asset_finder, calendar, daily_reader, minute_reader):
        self.daily_reader = daily_reader  # Direct Parquet read
        self.minute_reader = minute_reader
```

**After** (unified):
```python
class PolarsDataPortal:
    def __init__(
        self,
        asset_finder,
        calendar,
        data_source: Optional[DataSource] = None,  # NEW
        use_cache: bool = True,  # NEW
    ):
        if data_source:
            # Use DataSource (with optional caching)
            self.data_source = (
                CachedDataSource(data_source, cache_dir="~/.zipline/cache")
                if use_cache
                else data_source
            )
        else:
            # Fallback: old bundle readers (backwards compat)
            self.data_source = BundleDataSource(daily_reader, minute_reader)

    async def get_spot_value(self, assets, field, dt, frequency):
        # Unified path: use DataSource
        symbols = [asset.symbol for asset in assets]
        df = await self.data_source.fetch(
            symbols=symbols,
            start=dt,
            end=dt,
            frequency=frequency
        )
        return df[field]
```

### TradingAlgorithm (Story X1.5)

```python
class TradingAlgorithm:
    def __init__(
        self,
        ...,
        data_source: Optional[DataSource] = None,  # NEW
        bundle: Optional[str] = None,  # Existing
    ):
        if data_source:
            # Use provided DataSource (live or backtest)
            self.data_source = data_source
        elif bundle:
            # Load bundle as DataSource (backwards compat)
            self.data_source = BundleDataSource.from_bundle(bundle)
        else:
            raise ValueError("Must provide data_source or bundle")

        # Create DataPortal with DataSource
        self.data_portal = PolarsDataPortal(
            asset_finder=self.asset_finder,
            calendar=self.calendar,
            data_source=self.data_source,
            use_cache=(not self.live_trading)  # Cache for backtest, not live
        )
```

---

## Performance Characteristics

### Cache Hit Path (Story X1.3 Target)
- Metadata lookup: <10ms (SQLite indexed query)
- Parquet read: <100ms (cached file, optimized scan)
- Total latency: <110ms

### Cache Miss Path
- Adapter fetch: 1-5s (network API call)
- Parquet write: 50-200ms (depends on data size)
- Metadata update: <50ms (SQLite insert)
- Total latency: 1-5.5s

### Cache Hit Rate (Story X1.3 Target)
- Repeated backtests: >80% (same data, different strategies)
- Freshness overhead: <5% false invalidations
- LRU eviction accuracy: <10% premature evictions

---

## Testing Strategy

### Unit Tests (All Stories)
- `tests/data/sources/test_data_source.py`: DataSource interface compliance
- `tests/data/sources/test_cached_source.py`: Cache logic, freshness, LRU
- `tests/data/bundles/test_unified_metadata.py`: Metadata merge correctness
- **Coverage Target**: ≥90%

### Integration Tests (Stories 8.1, 8.5)
- `tests/integration/data/test_adapter_to_bundle.py`: Adapter → Bundle → DataPortal
- `tests/integration/data/test_cache_end_to_end.py`: Cache hit/miss, eviction
- `tests/integration/data/test_metadata_migration.py`: Catalog merge validation

### Performance Tests (Story X1.3)
- Benchmark cache lookup latency (<10ms target)
- Benchmark cache hit read (<100ms target)
- Benchmark cache eviction (LRU correctness)

---

## Migration Path

### For Users

**Old Way** (pre-Epic X1):
```bash
# Manual ingest script
rustybt ingest csvdir --csvdir /path/to/csv

# Or custom Python script
from rustybt.data.adapters import YFinanceAdapter
adapter = YFinanceAdapter()
df = adapter.fetch_ohlcv(["AAPL"], start, end, "1d")
# ... manual bundle creation ...
```

**New Way** (Epic X1):
```bash
# One command for any source
rustybt ingest yfinance --symbols AAPL,MSFT --bundle my-data
rustybt ingest ccxt --exchange binance --symbols BTC/USDT --bundle crypto
```

### For Developers

**Old Way** (pre-Epic X1):
```python
# Manual metadata tracking
from rustybt.data.catalog import DataCatalog
catalog = DataCatalog()
catalog.store_metadata({...})
catalog.store_quality_metrics({...})
```

**New Way** (Epic X1):
```python
# Automatic metadata tracking
from rustybt.data.sources import get_source
source = get_source("yfinance")
source.ingest_to_bundle("my-bundle", ["AAPL"], start, end, "1d")
# Metadata tracked automatically
```

---

## Change Log
| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-05 | 1.0 | Initial architecture design for Epic X1 | John (Product Manager) |
