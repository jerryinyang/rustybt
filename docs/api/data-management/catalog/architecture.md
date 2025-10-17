# Catalog Architecture

Detailed technical architecture of RustyBT's data catalog system.

## Overview

The catalog architecture provides a unified metadata management system for bundles, replacing the previous fragmented approach (DataCatalog + ParquetMetadataCatalog). The design emphasizes performance, data integrity, and ease of use.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                            │
│  ┌────────────────┐  ┌───────────────────┐  ┌────────────────┐ │
│  │ Data Adapters  │  │ Bundle Management │  │  User Strategies│ │
│  │ (CCXT, YFin)   │  │  (register, load) │  │  (algorithms)  │ │
│  └────────┬───────┘  └─────────┬─────────┘  └────────┬───────┘ │
└───────────┼──────────────────────┼──────────────────────┼────────┘
            │                       │                       │
            └───────────┬───────────┴──────────┬───────────┘
                        │                      │
            ┌───────────▼────────────┐ ┌───────▼────────────┐
            │ BundleMetadataTracker  │ │  BundleMetadata    │
            │ (Ingestion Helper)     │ │  (Core Catalog)    │
            └───────────┬────────────┘ └───────┬────────────┘
                        │                      │
                        └──────────┬───────────┘
                                   │
                      ┌────────────▼──────────────┐
                      │   SQLite Database Layer   │
                      │  ┌────────────────────┐   │
                      │  │ bundle_metadata    │   │
                      │  ├────────────────────┤   │
                      │  │ bundle_symbols     │   │
                      │  ├────────────────────┤   │
                      │  │ bundle_cache       │   │
                      │  ├────────────────────┤   │
                      │  │ cache_statistics   │   │
                      │  └────────────────────┘   │
                      └───────────────────────────┘
```

## Database Schema Design

### Entity-Relationship Model

```
bundle_metadata (1) ──< (M) bundle_symbols
      │
      │ (referenced by)
      │
bundle_cache (M) ─> (1) bundle_metadata.bundle_name

cache_statistics (independent, aggregated metrics)
```

### Table Definitions

#### bundle_metadata

**Purpose**: Core bundle information including provenance, quality, and file metadata.

**Schema**:
```sql
CREATE TABLE bundle_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_name TEXT NOT NULL UNIQUE,

    -- Provenance
    source_type TEXT NOT NULL,
    source_url TEXT,
    api_version TEXT,
    fetch_timestamp INTEGER NOT NULL,
    data_version TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',

    -- Quality Metrics
    row_count INTEGER,
    start_date INTEGER,
    end_date INTEGER,
    missing_days_count INTEGER NOT NULL DEFAULT 0,
    missing_days_list TEXT NOT NULL DEFAULT '[]',
    outlier_count INTEGER NOT NULL DEFAULT 0,
    ohlcv_violations INTEGER NOT NULL DEFAULT 0,
    validation_passed BOOLEAN NOT NULL DEFAULT TRUE,
    validation_timestamp INTEGER,

    -- File Metadata
    file_checksum TEXT,
    file_size_bytes INTEGER,
    checksum TEXT,  -- Legacy compatibility

    -- Timestamps
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Indexes for fast lookup
CREATE INDEX idx_bundle_metadata_name ON bundle_metadata(bundle_name);
CREATE INDEX idx_bundle_metadata_fetch ON bundle_metadata(fetch_timestamp);
CREATE INDEX idx_bundle_metadata_validation ON bundle_metadata(validation_timestamp);
```

**Design Decisions**:
1. **Unique bundle_name**: Primary identifier for bundles
2. **Unix timestamps**: All dates/times stored as integers for performance
3. **JSON in TEXT**: `missing_days_list` stored as JSON string for flexibility
4. **Dual checksums**: `file_checksum` (new) and `checksum` (legacy) for migration
5. **Default values**: Sensible defaults for quality fields

#### bundle_symbols

**Purpose**: Track symbols within bundles with asset type and exchange information.

**Schema**:
```sql
CREATE TABLE bundle_symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT,  -- 'equity', 'crypto', 'future', etc.
    exchange TEXT,    -- 'NYSE', 'binance', etc.

    FOREIGN KEY (bundle_name) REFERENCES bundle_metadata(bundle_name),
    UNIQUE (bundle_name, symbol)
);

-- Indexes for symbol lookup
CREATE INDEX idx_bundle_symbols_bundle ON bundle_symbols(bundle_name);
CREATE INDEX idx_bundle_symbols_symbol ON bundle_symbols(symbol);
```

**Design Decisions**:
1. **Composite uniqueness**: (bundle_name, symbol) ensures no duplicates
2. **Foreign key**: Maintains referential integrity with bundle_metadata
3. **Dual indexes**: Fast lookup by both bundle and symbol
4. **Optional metadata**: asset_type and exchange are nullable for flexibility

#### bundle_cache

**Purpose**: Cache entry tracking for LRU eviction and performance monitoring.

**Schema**:
```sql
CREATE TABLE bundle_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL UNIQUE,
    bundle_name TEXT NOT NULL,
    bundle_path TEXT NOT NULL,

    -- Cache metadata
    symbols TEXT,  -- JSON list of symbols
    start TEXT,
    end TEXT,
    frequency TEXT,

    -- Performance tracking
    fetch_timestamp INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    row_count INTEGER,
    last_accessed INTEGER NOT NULL,  -- For LRU eviction
);

-- Indexes for cache operations
CREATE INDEX idx_bundle_cache_key ON bundle_cache(cache_key);
CREATE INDEX idx_bundle_cache_last_accessed ON bundle_cache(last_accessed);
```

**Design Decisions**:
1. **Unique cache_key**: SHA256-based key for fast lookup
2. **last_accessed index**: Enables efficient LRU eviction queries
3. **JSON symbols**: Flexible symbol list storage
4. **Size tracking**: For cache size management

#### cache_statistics

**Purpose**: Daily aggregated cache performance metrics.

**Schema**:
```sql
CREATE TABLE cache_statistics (
    stat_date INTEGER PRIMARY KEY,  -- Unix timestamp (day granularity)
    hit_count INTEGER DEFAULT 0,
    miss_count INTEGER DEFAULT 0,
    total_size_mb REAL DEFAULT 0.0,
    avg_fetch_latency_ms REAL DEFAULT 0.0
);

CREATE INDEX idx_cache_statistics_date ON cache_statistics(stat_date);
```

**Design Decisions**:
1. **Daily granularity**: stat_date rounded to day start
2. **Aggregated metrics**: Hit rate calculated from hit/miss counts
3. **Size in MB**: Human-readable cache size
4. **Latency tracking**: Performance monitoring

## Class Architecture

### BundleMetadata

**Design Pattern**: Singleton with class methods (no instance state)

**Key Methods**:

```python
class BundleMetadata:
    # Core CRUD operations
    @classmethod
    def update(cls, bundle_name: str, **metadata) -> None

    @classmethod
    def get(cls, bundle_name: str) -> dict | None

    @classmethod
    def list_bundles(cls, source_type=None, start_date=None, end_date=None) -> list[dict]

    @classmethod
    def delete(cls, bundle_name: str) -> bool

    # Symbol management
    @classmethod
    def add_symbol(cls, bundle_name: str, symbol: str, asset_type=None, exchange=None) -> int

    @classmethod
    def get_symbols(cls, bundle_name: str) -> list[dict]

    # Quality metrics
    @classmethod
    def get_quality_metrics(cls, bundle_name: str) -> dict | None

    # Cache management
    @classmethod
    def add_cache_entry(cls, cache_key: str, bundle_name: str, parquet_path: str, size_bytes: int) -> None

    # Utility methods
    @classmethod
    def count_bundles(cls) -> int

    @classmethod
    def count_symbols(cls, bundle_name: str) -> int
```

**Design Decisions**:
1. **Class methods**: No instance state, simpler API
2. **Lazy engine creation**: SQLAlchemy engine created on first use
3. **Single database**: Shared across all operations
4. **Field normalization**: Automatic type conversion and validation
5. **Backward compatibility**: Legacy checksum field support

### BundleMetadataTracker

**Design Pattern**: Composition with DataCatalog/BundleMetadata

**Key Methods**:

```python
class BundleMetadataTracker:
    def __init__(self, catalog: DataCatalog | None = None)

    def record_bundle_ingestion(
        self,
        bundle_name: str,
        source_type: str,
        data_files: list[Path],
        data: pl.DataFrame | None = None,
        **kwargs
    ) -> dict[str, Any]

    def record_csv_bundle(
        self,
        bundle_name: str,
        csv_dir: Path,
        data: pl.DataFrame | None = None,
        calendar: ExchangeCalendar | None = None
    ) -> dict[str, Any]

    def record_api_bundle(
        self,
        bundle_name: str,
        source_type: str,
        data_file: Path,
        **kwargs
    ) -> dict[str, Any]
```

**Design Decisions**:
1. **Automated collection**: Metadata extraction from data files
2. **Quality calculation**: Automatic OHLCV validation if data provided
3. **Checksum computation**: File integrity verification
4. **Calendar-aware**: Trading day gap detection
5. **Convenience functions**: Specialized methods for common sources

## Data Flow

### Bundle Ingestion Flow

```
1. User initiates bundle ingestion
   └─> Calls adapter.fetch_ohlcv(symbols, start, end)

2. Adapter fetches data
   └─> Returns Polars DataFrame with OHLCV data

3. Bundle writer saves data to Parquet
   └─> Creates partitioned Parquet files

4. BundleMetadataTracker called
   ├─> Calculates file checksums
   ├─> Computes quality metrics (if data provided)
   └─> Calls BundleMetadata.update()

5. BundleMetadata stores metadata
   ├─> Inserts/updates bundle_metadata row
   ├─> Adds symbols to bundle_symbols
   └─> Returns success
```

### Catalog Query Flow

```
1. User queries bundle
   └─> BundleMetadata.get(bundle_name)

2. SQLAlchemy query
   ├─> SELECT FROM bundle_metadata WHERE bundle_name = ?
   └─> Returns row or None

3. Post-processing
   ├─> Deserialize JSON fields (missing_days_list)
   ├─> Remove internal fields (id)
   └─> Return dictionary

4. User receives metadata
   └─> Access provenance, quality, file info
```

### Cache Eviction Flow

```
1. Cache size exceeds limit
   └─> Query: SELECT * FROM bundle_cache ORDER BY last_accessed ASC

2. Iterate oldest entries
   ├─> Calculate cumulative size
   └─> Identify entries to evict

3. Delete cache entries
   ├─> DELETE FROM bundle_cache WHERE cache_key = ?
   └─> Delete physical Parquet files

4. Update statistics
   └─> INCREMENT cache_statistics.eviction_count
```

## Performance Optimization

### Indexing Strategy

1. **bundle_metadata**:
   - `bundle_name`: Primary lookup (unique index)
   - `fetch_timestamp`: Temporal queries
   - `validation_timestamp`: Quality filtering

2. **bundle_symbols**:
   - `bundle_name`: Symbol lookup by bundle
   - `symbol`: Cross-bundle symbol search
   - Composite `(bundle_name, symbol)`: Uniqueness

3. **bundle_cache**:
   - `cache_key`: Cache hit lookup
   - `last_accessed`: LRU eviction queries

4. **cache_statistics**:
   - `stat_date`: Temporal aggregation

### Query Performance Targets

| Operation | Target Latency | Actual (Typical) |
|-----------|----------------|------------------|
| Bundle metadata lookup | <5ms | 2-3ms |
| Symbol query (by bundle) | <10ms | 5-8ms |
| Cache key lookup | <10ms | 3-5ms |
| List bundles (all) | <50ms | 20-30ms |
| Statistics (30 days) | <50ms | 15-25ms |

### Optimization Techniques

1. **Connection Pooling**: SQLAlchemy engine reused across calls
2. **Prepared Statements**: Parameterized queries for safety and speed
3. **Bulk Operations**: Batch symbol inserts when possible
4. **Lazy Loading**: Engine created only when needed
5. **Field Indexing**: Strategic indexes on common query patterns

## Migration Strategy

### From DataCatalog

**Changes**:
- Instance methods → Class methods
- `store_metadata(dict)` → `update(bundle_name, **kwargs)`
- `get_bundle_metadata(name)` → `get(name)`

**Compatibility**: DataCatalog still works (delegates to BundleMetadata)

### From ParquetMetadataCatalog

**Changes**:
- Dataset-centric → Bundle-centric
- `dataset_id` → `bundle_name`
- Separate tables → Unified bundle_metadata

**Migration Path**: Re-ingest bundles with new catalog

## Best Practices

### 1. Metadata Updates

```python
# Good: Update all relevant fields together
BundleMetadata.update(
    bundle_name="my-bundle",
    source_type="yfinance",
    row_count=10000,
    validation_passed=True
)

# Avoid: Multiple separate updates
BundleMetadata.update(bundle_name="my-bundle", source_type="yfinance")
BundleMetadata.update(bundle_name="my-bundle", row_count=10000)  # Inefficient
```

### 2. Symbol Management

```python
# Good: Add symbols during ingestion
for symbol in symbols:
    BundleMetadata.add_symbol(bundle_name, symbol, asset_type, exchange)

# Good: Query symbols for display
symbols = BundleMetadata.get_symbols(bundle_name)
for s in symbols:
    print(f"{s['symbol']} ({s['asset_type']})")
```

### 3. Quality Tracking

```python
# Good: Use BundleMetadataTracker for automated collection
tracker = BundleMetadataTracker()
result = tracker.record_bundle_ingestion(
    bundle_name="my-bundle",
    source_type="yfinance",
    data_files=[data_file],
    data=df  # Quality calculated automatically
)

# Avoid: Manual quality calculation (error-prone)
```

### 4. Cache Management

```python
# Good: Let catalog manage cache
BundleMetadata.add_cache_entry(cache_key, bundle_name, path, size)

# Query LRU for eviction
from rustybt.data.catalog import DataCatalog
catalog = DataCatalog()
lru_entries = catalog.get_lru_cache_entries()
```

## Design Rationale

### Why SQLite?

1. **Single-file database**: Easy backup and migration
2. **Zero configuration**: No server setup required
3. **ACID compliance**: Data integrity guaranteed
4. **Fast for reads**: Metadata queries are read-heavy
5. **Python integration**: Excellent SQLAlchemy support

### Why Class Methods?

1. **Simplicity**: No instance state to manage
2. **Thread-safe**: SQLAlchemy handles connection pooling
3. **Global scope**: Single catalog across application
4. **Easy testing**: `set_db_path()` for test isolation

### Why Merged Tables?

**Before**: Separate `bundle_metadata` and `quality_metrics` tables
**After**: Unified `bundle_metadata` with quality fields

**Benefits**:
1. Fewer joins for common queries
2. Simpler schema
3. Atomic updates (all metadata in one transaction)
4. Better query performance (no JOIN overhead)

**Trade-offs**:
- More NULL values (quality metrics optional)
- Wider table (acceptable for metadata)

## Future Enhancements

### Planned (v2.0)

1. **Remove deprecated APIs**:
   - Delete `DataCatalog` class
   - Delete `ParquetMetadataCatalog` class

2. **Enhanced statistics**:
   - Per-bundle cache statistics
   - Access patterns tracking
   - Predictive cache warming

3. **Distributed catalog** (optional):
   - PostgreSQL backend for multi-user
   - Catalog replication
   - Concurrent ingestion support

### Under Consideration

1. **Versioned metadata**: Track metadata history
2. **Metadata validation**: Schema enforcement
3. **Bundle dependencies**: Track bundle relationships
4. **Automated cleanup**: TTL-based metadata expiration

## References

- [Catalog API Reference](catalog-api.md) - Complete API documentation
