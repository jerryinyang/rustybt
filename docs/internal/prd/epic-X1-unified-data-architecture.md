# Epic X1: Unified Data Architecture

**Epic Goal**: Unify fragmented data systems (Adapters, Bundles, Catalogs) into a cohesive `DataSource` architecture that eliminates duplication, enables fluid data flow between live trading and backtesting, and provides automatic metadata tracking with smart caching.

**Priority**: **CRITICAL - Blocks Epic 7** (Performance Optimization)

**Status**: In Progress (Phase 1 - Story X1.1)

**Timeline**: 3-4 weeks (Phase 1: 1-2 days, Phase 2: 2 weeks, Phase 3: 1 week, Phase 4: 3 days)

**Effort**: High (architectural refactor)

**Architecture Review**: ✅ Complete (2025-10-05)
- [ADR 001: Unified DataSource Abstraction](../architecture/decisions/001-unified-data-source-abstraction.md)
- [ADR 002: Unified Metadata Schema](../architecture/decisions/002-unified-metadata-schema.md)
- [ADR 003: Smart Caching Layer](../architecture/decisions/003-smart-caching-layer.md)
- [ADR 004: Cache Freshness Strategies](../architecture/decisions/004-cache-freshness-strategies.md)
- [ADR 005: Migration Rollback Safety](../architecture/decisions/005-migration-rollback-safety.md)

---

## Executive Summary

### The Problem

RustyBT currently has **three separate data systems** that operate independently:

1. **Data Adapters** (Epic 6): Fetch external data (YFinance, CCXT, Polygon, etc.)
   - ✅ Well-implemented, comprehensive test coverage
   - ❌ No bundle creation capability
   - ❌ Not integrated with Zipline bundle system

2. **Bundle System** (Zipline Legacy): Pre-processed backtest data storage
   - ✅ Optimized for fast local I/O
   - ✅ Integrated with AssetFinder, DataPortal
   - ❌ Requires manual ingest scripts per source
   - ❌ CSV/Quandl-only, no adapter support

3. **Catalog Systems** (2 separate implementations):
   - `DataCatalog`: High-level bundle provenance (source, quality metrics)
   - `ParquetMetadataCatalog`: File-level Parquet metadata (symbols, date ranges, checksums)
   - ❌ Operate independently, duplicate functionality
   - ❌ No automatic metadata tracking

**Impact**:
- **Epic 7 (Profiling) is BLOCKED**: Cannot create bundles from adapters
- **Developer friction**: Manual scripting required for data ingestion
- **Fragmented metadata**: Two catalog systems, inconsistent tracking
- **No cache optimization**: Redundant API calls, no backtest/live data reuse

### The Solution

Create a **Unified DataSource Architecture** that:

1. **Merges catalog functionality** into Bundle/DataSource layer (eliminate redundancy)
2. **Adapters create bundles automatically** via unified `DataSource` interface
3. **Smart caching** eliminates redundant API calls (backtest/live data sharing)
4. **Automatic metadata tracking** embedded in all data operations
5. **Backwards compatible** with gradual migration path

### Unique Catalog Features to Preserve

**From DataCatalog** (merge into DataSource metadata):
- ✅ **Provenance tracking**: source_url, api_version, fetch_timestamp
- ✅ **Quality metrics**: missing_days, ohlcv_violations, validation_passed
- ✅ **Bundle discovery**: `list_bundles(source_type, start_date, end_date)`

**From ParquetMetadataCatalog** (merge into Bundle infrastructure):
- ✅ **Symbol-level metadata**: asset_type, exchange
- ✅ **File integrity**: checksums, size_bytes
- ✅ **Cache management**: cache_entries, LRU eviction, hit/miss stats
- ✅ **Backtest linkage**: reuse cached datasets across backtests

**To Deprecate** (duplicates Bundle functionality):
- ❌ **Dataset storage** (Parquet files) - already in BundleData
- ❌ **Date range tracking** - already in AssetDB/Bundle metadata
- ❌ **Resolution tracking** - already specified in bundle name/config

### Success Criteria

1. **Epic 7 Unblocked**: Profiling bundles created via adapters (1-2 days)
2. **Single Data Path**: All data flows through `DataSource` → Bundle → DataPortal
3. **Metadata Consolidation**: One unified metadata store (no duplication)
4. **Cache Hit Rate**: >80% for repeated backtests with same data
5. **Zero Breaking Changes**: Existing code works with deprecation warnings
6. **Performance Neutral**: <5% overhead vs. current direct Parquet reads

---

## Business Value

### For Developers
- **Simplified API**: One interface for all data sources (`DataSource`)
- **Auto-bundling**: No manual ingest scripts required
- **Better DX**: `rustybt ingest yfinance --symbols AAPL` just works

### For Performance (Enables Epic 7)
- **Profiling unblocked**: Can create realistic backtest datasets
- **Cache optimization**: Reduce API calls by 80%+
- **Faster backtests**: Cached data reads ~10x faster than API calls

### For Production Use
- **Live/backtest parity**: Same data infrastructure for both modes
- **Data quality**: Automatic validation and tracking
- **Audit trail**: Complete provenance for regulatory compliance

---

## Technical Architecture

### Current State (Fragmented)

```
┌─────────────────────────────────────────────────────────────┐
│  ADAPTERS (fetch data)                                      │
│  YFinance, CCXT, Polygon, Alpaca, AlphaVantage, CSV        │
└────────────────────────────┬────────────────────────────────┘
                             │ (no integration)
                             ↓
┌─────────────────────────────────────────────────────────────┐
│  BUNDLES (store data)                                       │
│  quandl_bundle(), csvdir_bundle() - manual scripts          │
│  ↓                                                           │
│  Parquet Storage + AssetDB                                  │
└────────────────────────────┬────────────────────────────────┘
                             │ (no integration)
                             ↓
┌─────────────────────────────────────────────────────────────┐
│  CATALOGS (metadata tracking) - 2 separate systems          │
│  DataCatalog (provenance) | ParquetMetadataCatalog (files) │
└─────────────────────────────────────────────────────────────┘

PROBLEMS:
- Adapters can't create bundles (Epic 7 blocked)
- Manual scripting required per data source
- Metadata fragmented across 2 systems
- No cache reuse between live/backtest
```

### Target State (Unified)

```
┌─────────────────────────────────────────────────────────────┐
│  DATASOURCE (Unified Interface)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ YFinance     │  │ CCXT         │  │ CSV          │      │
│  │ Source       │  │ Source       │  │ Source       │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                  ↓                 ↓              │
│    .fetch() → Polars DataFrame                             │
│    .ingest_to_bundle() → automatic bundle creation         │
│    .get_metadata() → provenance + quality                  │
└────────────────────────────┬────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│  CACHED DATASOURCE (Smart Caching Layer)                   │
│  ┌─────────────────────────────────────────────────┐       │
│  │  1. Check metadata: Does bundle exist?          │       │
│  │  2. Cache HIT → Read Parquet (fast)             │       │
│  │  3. Cache MISS → Adapter fetch → Write bundle   │       │
│  │  4. Freshness check → Re-fetch if stale         │       │
│  │  5. Update metadata (provenance + quality)      │       │
│  └─────────────────────────────────────────────────┘       │
└────────────────────────────┬────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│  BUNDLE STORAGE (Parquet + Metadata)                        │
│  ┌──────────────────┐  ┌────────────────────────────┐      │
│  │ Parquet Files    │  │ Unified Metadata           │      │
│  │ - daily_bars/    │  │ - Provenance (source, URL) │      │
│  │ - minute_bars/   │  │ - Quality (validation)     │      │
│  │ - OHLCV Decimal  │  │ - Symbols (asset_type)     │      │
│  │                  │  │ - Cache (LRU, hit/miss)    │      │
│  │                  │  │ - Checksums (integrity)    │      │
│  └──────────────────┘  └────────────────────────────┘      │
│           ↓                         ↓                       │
│  AssetDB (symbol info)   BundleMetadata (SQLite)           │
└────────────────────────────┬────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│  DATAPORTAL (Unified Access)                                │
│  - TradingAlgorithm.data.current()                          │
│  - TradingAlgorithm.data.history()                          │
│  - Same API for live and backtest                           │
└─────────────────────────────────────────────────────────────┘

BENEFITS:
✅ Adapters auto-create bundles
✅ Single metadata store (no duplication)
✅ Smart caching (80%+ cache hit rate)
✅ Live/backtest data sharing
```

### Key Design Principles

1. **Merge, Don't Duplicate**: Catalog metadata embedded in Bundle/DataSource layer
2. **Backwards Compatible**: Old APIs work (deprecated, removed in v2.0)
3. **Progressive Enhancement**: Each phase adds value independently
4. **Zero Configuration**: Smart defaults, explicit overrides
5. **Metadata Everywhere**: Automatic provenance tracking on every operation

---

## Epic Stories

### Story X1.1: Adapter-Bundle Bridge (Epic 7 Unblocking) ✅ IMPLEMENTED
**Duration**: 1-2 days
**Priority**: P0 - Critical (blocks Epic 7)
**Status**: ✅ **Implementation Complete** (2025-10-05)

**Goal**: Create minimal bridge to unblock Story 7.1 profiling

**Deliverables**:
- ✅ `rustybt/data/bundles/adapter_bundles.py` module
- ✅ 4 profiling bundle functions (with deprecation warnings):
  - `yfinance_profiling_bundle()` (50 stocks, 2 years, daily)
  - `ccxt_hourly_profiling_bundle()` (20 crypto, 6 months, hourly)
  - `ccxt_minute_profiling_bundle()` (10 crypto, 1 month, minute)
  - `csv_profiling_bundle()` (CSV wrapper with metadata tracking)
- ✅ CLI: `rustybt ingest yfinance-profiling`
- ✅ Integration tests: adapter → bundle → DataPortal (≥90% coverage)
- ✅ Documentation: [Adapter-Bundle Bridge Pattern](../architecture/adapter-bundle-bridge.md)
- ✅ Automatic metadata tracking: provenance + quality validation
- ✅ Test suite: `tests/data/bundles/test_adapter_bundles.py`

**Success Criteria**:
- ✅ Epic 7 profiling scenarios have data bundles
- ✅ End-to-end test passes: fetch → bundle → backtest
- ✅ Metadata automatically tracked via `_track_api_bundle_metadata()`
- ✅ Deprecation warnings for v2.0 migration path
- ✅ OHLCV validation (high/low violations detected)

**Architectural Improvements**:
- Deprecation warnings added (removal in v2.0)
- Migration guide included in docs
- Performance benchmarks documented (17-40s per bundle)
- Bridge pattern fully documented with examples

**Story Link**: [docs/stories/X1.1.adapter-bundle-bridge.story.md](../stories/X1.1.adapter-bundle-bridge.story.md)

---

### Story X1.2: Unified DataSource Abstraction
**Duration**: 1 week
**Priority**: P0 - Critical

**Goal**: Create clean `DataSource` interface unifying adapters + bundles

**Deliverables**:
- `rustybt/data/sources/base.py` with `DataSource` ABC
- Interface methods:
  - `fetch(symbols, start, end, frequency)` → DataFrame
  - `ingest_to_bundle(bundle_name, **kwargs)` → None
  - `get_metadata()` → dict (provenance + quality)
  - `supports_live()` → bool
- Refactor 6 adapters to implement `DataSource`:
  - YFinanceAdapter, CCXTAdapter, PolygonAdapter
  - AlpacaAdapter, AlphaVantageAdapter, CSVAdapter
- `DataSourceRegistry` for dynamic discovery
- Unified CLI: `rustybt ingest <source> --bundle <name>`
- Single code path for all bundle creation

**Success Criteria**:
- All adapters implement `DataSource` interface
- Old adapter APIs still work (backwards compatible)
- `rustybt ingest yfinance --symbols AAPL,MSFT --bundle my-data` works
- No code duplication in bundle creation logic

---

### Story X1.3: Smart Caching Layer
**Duration**: 1 week
**Priority**: P1 - High

**Goal**: Implement transparent caching with market-aware freshness policies

**Architecture References**:
- [ADR 003: Smart Caching Layer](../architecture/decisions/003-smart-caching-layer.md)
- [ADR 004: Cache Freshness Strategies](../architecture/decisions/004-cache-freshness-strategies.md)

**Design Decision**:
- ✅ Transparent `CachedDataSource` wrapper (Strategy Pattern)
- ✅ Market-aware freshness policies (daily/hourly/minute)
- ✅ LRU eviction with configurable max size (default 10GB)
- ✅ Thread-safe cache operations (eviction lock)

**Deliverables**:
- `rustybt/data/sources/cached_source.py` - `CachedDataSource` wrapper
- `rustybt/data/sources/freshness.py` - Freshness policy strategies:
  ```python
  class CacheFreshnessPolicy(ABC):
      @abstractmethod
      def is_fresh(bundle_metadata, frequency, calendar) -> bool

      @abstractmethod
      def get_next_refresh_time(bundle_metadata, frequency, calendar) -> Timestamp

  # Implementations:
  - MarketCloseFreshnessPolicy  # Daily data, refresh after market close
  - TTLFreshnessPolicy           # Simple time-to-live (crypto 24/7)
  - HybridFreshnessPolicy        # TTL + market hours (NYSE hourly)
  - NeverStaleFreshnessPolicy    # Static data (CSV files)
  - AlwaysStaleFreshnessPolicy   # Live trading (force fetch)
  ```

- `rustybt/data/sources/freshness_factory.py` - Policy selection:
  ```python
  class FreshnessPolicyFactory:
      @staticmethod
      def create(adapter: DataSource, frequency: str) -> CacheFreshnessPolicy:
          # Select policy based on adapter type + frequency
          # YFinance daily → MarketCloseFreshnessPolicy
          # CCXT hourly → TTLFreshnessPolicy
          # CSV → NeverStaleFreshnessPolicy
  ```

- Cache workflow:
  ```python
  async def fetch(symbols, start, end, frequency):
      cache_key = hash(symbols, start, end, frequency)
      bundle = BundleMetadata.find_cached(cache_key)

      if bundle and policy.is_fresh(bundle, frequency, calendar):
          return read_from_cache(bundle)  # <100ms

      df = await adapter.fetch(...)  # API call
      write_to_cache(cache_key, df)
      enforce_cache_limit()  # LRU eviction
      return df
  ```

- LRU eviction with thread safety:
  ```python
  def _enforce_cache_limit(self):
      with self._eviction_lock:  # Thread-safe
          total_size = BundleMetadata.get_cache_size()
          if total_size < max_size:
              return

          # Evict LRU entries
          for entry in BundleMetadata.get_lru_cache_entries():
              delete_bundle(entry['bundle_name'])
              total_size -= entry['size_bytes']
              if total_size < max_size:
                  break
  ```

- Configuration support (`rustybt/config/cache_freshness.yaml`):
  ```yaml
  freshness_policies:
    yfinance:
      daily: market_close
      hourly: hybrid_3600  # 1h TTL during market hours
    ccxt:
      daily: ttl_86400     # 24h TTL
      hourly: ttl_3600     # 1h TTL
    csv:
      daily: never_stale

  calendars:
    yfinance: NYSE
    ccxt: 24/7
  ```

- Cache statistics tracking:
  - `BundleMetadata.cache_stats` table (hit_count, miss_count, hit_rate)
  - CLI: `rustybt cache stats` shows metrics
  - Performance logging (cache_hit/cache_miss events)

**Success Criteria**:
- Cache lookup latency <10ms (SQLite indexed query)
- Cache hit read latency <100ms (Parquet scan)
- Cache hit rate >80% for repeated backtests
- Freshness policies prevent stale data (0 staleness bugs)
- LRU eviction keeps cache under max size
- Thread-safe concurrent access (parallel DataPortals)
- All edge cases covered: weekends, holidays, early closures
- Test coverage ≥95% for all freshness policies

---

### Story X1.4: Unified Metadata Management
**Duration**: 1 week
**Priority**: P1 - High

**Goal**: Merge DataCatalog + ParquetMetadataCatalog into unified Bundle metadata

**Architecture References**:
- [ADR 002: Unified Metadata Schema](../architecture/decisions/002-unified-metadata-schema.md)
- [ADR 005: Migration Rollback Safety](../architecture/decisions/005-migration-rollback-safety.md)

**Design Decision**:
- ❌ Don't create separate `UnifiedCatalog` class (more complexity)
- ✅ Extend `BundleMetadata` schema with merged catalog fields
- ✅ Transactional migration with automatic backup + rollback
- ✅ Backwards compatibility via deprecated wrapper APIs

**Deliverables**:
- Extended `BundleMetadata` schema in `rustybt/data/bundles/metadata_schema.py`:
  ```sql
  -- Merged from DataCatalog (provenance)
  ALTER TABLE bundle_metadata ADD COLUMN source_type TEXT;
  ALTER TABLE bundle_metadata ADD COLUMN source_url TEXT;
  ALTER TABLE bundle_metadata ADD COLUMN api_version TEXT;
  ALTER TABLE bundle_metadata ADD COLUMN fetch_timestamp INTEGER;

  -- Merged from DataCatalog (quality)
  ALTER TABLE bundle_metadata ADD COLUMN row_count INTEGER;
  ALTER TABLE bundle_metadata ADD COLUMN missing_days_count INTEGER;
  ALTER TABLE bundle_metadata ADD COLUMN ohlcv_violations INTEGER;
  ALTER TABLE bundle_metadata ADD COLUMN validation_passed BOOLEAN;

  -- Merged from ParquetMetadataCatalog (symbols)
  CREATE TABLE bundle_symbols (
      bundle_name TEXT,
      symbol TEXT,
      asset_type TEXT,
      exchange TEXT,
      FOREIGN KEY (bundle_name) REFERENCES bundle_metadata(bundle_name)
  );

  -- Merged from ParquetMetadataCatalog (file integrity)
  ALTER TABLE bundle_metadata ADD COLUMN file_checksum TEXT;
  ALTER TABLE bundle_metadata ADD COLUMN file_size_bytes INTEGER;

  -- Merged from ParquetMetadataCatalog (cache)
  CREATE TABLE bundle_cache (
      cache_key TEXT PRIMARY KEY,
      bundle_name TEXT,
      last_accessed INTEGER,
      size_bytes INTEGER,
      FOREIGN KEY (bundle_name) REFERENCES bundle_metadata(bundle_name)
  );
  ```

- Migration script: `scripts/migrate_catalog_to_unified.py` (✅ IMPLEMENTED):
  ```bash
  # Dry-run preview (no changes)
  python scripts/migrate_catalog_to_unified.py --dry-run

  # Execute migration with automatic backup
  python scripts/migrate_catalog_to_unified.py --backup

  # Rollback to backup if needed
  python scripts/migrate_catalog_to_unified.py --rollback 1696512000

  # Validate migration integrity
  python scripts/migrate_catalog_to_unified.py --validate
  ```

- Migration features:
  - ✅ SQLite transactions (all-or-nothing, ACID guarantees)
  - ✅ Automatic timestamped backup with SHA256 checksums
  - ✅ Savepoints for partial rollback (per-bundle isolation)
  - ✅ Validation checkpoints (compare row counts before/after)
  - ✅ One-command rollback (restore from backup)
  - ✅ Progress tracking with Rich UI

- Update `ParquetWriter` to auto-populate metadata:
  ```python
  def write_daily_bars(self, df, bundle_name, source_metadata):
      path = self._write_parquet(df)

      # Auto-track merged metadata
      BundleMetadata.update(
          bundle_name=bundle_name,
          source_type=source_metadata['source_type'],
          source_url=source_metadata['source_url'],
          api_version=source_metadata['api_version'],
          fetch_timestamp=int(time.time()),
          row_count=len(df),
          file_checksum=calculate_checksum(path),
          file_size_bytes=path.stat().st_size
      )

      # Auto-validate quality
      quality = validate_ohlcv(df)
      BundleMetadata.update_quality(
          bundle_name=bundle_name,
          missing_days_count=quality.missing_days,
          ohlcv_violations=quality.violations,
          validation_passed=quality.is_valid
      )
  ```

- Deprecated wrapper classes:
  ```python
  class DataCatalog:
      """Deprecated: Forwards to BundleMetadata."""
      def __init__(self):
          warnings.warn(
              "DataCatalog is deprecated. Use BundleMetadata instead.",
              DeprecationWarning
          )
      def store_metadata(self, bundle_name, metadata):
          BundleMetadata.update(bundle_name, **metadata)
  ```

- CLI commands:
  - `rustybt bundle list` → all bundles with metadata
  - `rustybt bundle info <name>` → detailed provenance + quality
  - `rustybt bundle validate <name>` → quality check

**Success Criteria**:
- Migration script merges catalogs with zero data loss
- Dry-run mode previews changes accurately
- Rollback restores to pre-migration state (tested)
- `ParquetWriter` auto-populates all merged fields
- `DataCatalog` deprecated but functional (warnings)
- Validation confirms row count matches before/after
- No separate catalog database files (consolidated)
- Test coverage ≥90% for migration script

---

### Story X1.5: Integration and Documentation
**Duration**: 3 days
**Priority**: P2 - Medium

**Goal**: Complete integration and comprehensive documentation

**Deliverables**:
- Update `PolarsDataPortal` to use `CachedDataSource`
- Update `TradingAlgorithm` to accept `data_source` parameter:
  - Live mode: use adapter directly (no bundle)
  - Backtest mode: use `CachedDataSource` (auto-bundle)
- Architecture docs: `docs/architecture/unified-data-architecture.md`
- User guide: `docs/guides/data-ingestion-guide.md`
- Migration guide: `docs/guides/catalog-migration-guide.md`
- API reference: `docs/api/datasource-api.md`
- Example scripts:
  - `examples/ingest_yfinance.py`
  - `examples/ingest_ccxt.py`
  - `examples/backtest_with_unified_data.py`
- Deprecation plan (remove in v2.0, 6-12 months)

**Success Criteria**:
- All docs complete and reviewed
- Example scripts run successfully
- Migration guide tested end-to-end
- Old APIs marked deprecated with clear warnings

---

## Implementation Sequence

### Phase 1: Unblock Epic 7 (1-2 days)
**Stories**: X1.1 (Adapter-Bundle Bridge)

**Outcome**: Epic 7 profiling can proceed

---

### Phase 2: Core Architecture (2 weeks)
**Stories**: X1.2 (DataSource), X1.4 (Unified Metadata)

**Outcome**: Clean unified architecture, no catalog duplication

---

### Phase 3: Optimization (1 week)
**Stories**: X1.3 (Smart Caching)

**Outcome**: >80% cache hit rate, reduced API calls

---

### Phase 4: Polish (3 days)
**Stories**: X1.5 (Integration, Docs)

**Outcome**: Production-ready, fully documented

---

## Risks and Mitigations

### High Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Breaking changes in adapter refactor** | High - breaks existing code | - Comprehensive backwards compatibility tests<br>- Deprecation warnings (not immediate removal)<br>- Test all adapter usage patterns<br>- Parallel run old/new APIs |
| **Metadata migration data loss** | Critical - lose provenance | - Dry-run migration mode<br>- Backup recommendations<br>- Rollback script<br>- Row count validation |
| **Performance regression from caching overhead** | Medium - slower backtests | - Benchmark before/after<br>- Target: <5% overhead vs direct read<br>- Profile cache lookup path<br>- Optimize hot paths |

### Medium Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Cache staleness bugs (serving old data)** | Medium - incorrect backtest results | - Comprehensive freshness policy tests<br>- Validation checks on cache read<br>- Manual cache clear command |
| **Complex merge logic for catalogs** | Medium - bugs in metadata tracking | - Extensive unit tests<br>- Integration tests for all metadata fields<br>- Manual QA on migration |

### Low Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **CLI command name conflicts** | Low - user confusion | - Deprecate old commands gradually<br>- Clear help text |
| **Documentation lag** | Low - poor DX | - Write docs in parallel with code<br>- Review before merge |

---

## Success Metrics

### Phase 1 (Immediate - Story X1.1)
- ✅ Epic 7 unblocked (profiling can run)
- ✅ 3 profiling bundles created successfully
- ✅ Integration test passes: adapter → bundle → DataPortal

### Phase 2 (Core - Stories X1.2, X1.4)
- ✅ All 6 adapters implement `DataSource` interface
- ✅ Single unified metadata store (no DataCatalog/ParquetMetadataCatalog duplication)
- ✅ CLI simplification: `rustybt ingest <source>` for all sources
- ✅ Migration script runs without data loss

### Phase 3 (Optimization - Story X1.3)
- ✅ Cache hit rate >80% for repeated backtests
- ✅ Cache lookup latency <100ms
- ✅ Freshness policy prevents stale data (0 staleness bugs in QA)

### Phase 4 (Polish - Story X1.5)
- ✅ All documentation complete and accurate
- ✅ Example scripts run successfully
- ✅ Backwards compatibility: old APIs work with warnings
- ✅ No critical bugs in production testing

### Overall Epic Success
- ✅ Epic 7 (Profiling) can proceed without blockers
- ✅ Metadata consolidated: 50% reduction in duplicate code
- ✅ Developer experience: 1-line data ingestion (`rustybt ingest yfinance`)
- ✅ Performance neutral: <5% overhead vs current implementation
- ✅ Production ready: comprehensive tests, docs, examples

---

## Dependencies

### Blocks
- **Epic 7: Performance Optimization** (profiling requires data bundles)

### Requires
- ✅ Epic 3: Modern Data Architecture (Polars/Parquet infrastructure complete)
- ✅ Epic 6: Live Trading Engine (adapters implemented)

### Related
- Epic 9+: Future Rust optimizations can accelerate cache lookup, Parquet I/O

---

## Open Questions

1. **Cache size limit**: Default 10GB appropriate? Should be configurable?
   - **Decision**: 10GB default, configurable via `rustybt config set cache.max_size 20GB`

2. **Freshness policy granularity**: Per-asset-class or global?
   - **Decision**: Per-frequency (daily/hourly/minute), not per-asset-class (simpler)

3. **Migration window**: How long to maintain DataCatalog backwards compatibility?
   - **Decision**: 6-12 months, remove in v2.0

4. **Bundle naming**: Auto-generate or user-specified?
   - **Decision**: User-specified (explicit), auto-suggest based on source/symbols

---

## Notes

**Architectural Philosophy**: "Merge, don't duplicate"
- Catalog functionality is metadata tracking + quality validation
- Bundles already have metadata (AssetDB, BundleData)
- Extend Bundle metadata rather than create separate catalog system
- Result: Simpler architecture, less duplication, better DX

**Performance Considerations**:
- Metadata operations must be fast (<50ms) - use SQLite with indexes
- Cache lookup must be faster than API call (>10x speedup)
- Parquet read must be faster than network fetch (~100x speedup)

**Testing Strategy**:
- Unit tests: ≥90% coverage for all new modules
- Integration tests: End-to-end adapter → bundle → backtest
- Performance tests: Cache latency benchmarks
- Migration tests: Catalog merge without data loss

---

## Change Log
| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-05 | 1.0 | Initial Epic X1 PRD creation | John (Product Manager) |
| 2025-10-05 | 1.1 | Updated with architectural review results, ADR references, Story X1.1 implementation complete, reordered stories (X1.3 Caching before X1.4 Metadata) | John (Product Manager) |
