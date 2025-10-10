# ADR 002: Unified Metadata Schema (Merge Catalogs)

**Status:** Accepted
**Date:** 2025-10-05
**Epic:** Epic X1 - Unified Data Architecture
**Deciders:** Architect (Winston), Product Team

---

## Context

RustyBT has **two separate metadata systems** tracking overlapping information:

### DataCatalog (Global Scope)
- Bundle provenance (source URL, API version)
- Data quality metrics (missing days, OHLCV violations)
- Bundle discovery and listing

### ParquetMetadataCatalog (Per-Bundle Scope)
- Symbol metadata (asset type, exchange)
- File checksums and sizes
- Cache management (LRU tracking)
- Date range tracking

### Problems
- **Duplicate functionality** - both track bundle metadata
- **Inconsistent updates** - one catalog updated, other stale
- **Developer confusion** - which catalog to use for what?
- **Query overhead** - must query both for complete picture
- **Maintenance burden** - two schemas to evolve

---

## Decision

**Merge both catalogs into unified `BundleMetadata` schema** stored in bundle root (not global):

```sql
-- Single metadata database per bundle
-- Location: ~/.zipline/data/{bundle_name}/metadata.db

CREATE TABLE bundle_metadata (
    bundle_name TEXT PRIMARY KEY,

    -- From DataCatalog (provenance)
    source_type TEXT,
    source_url TEXT,
    api_version TEXT,
    fetch_timestamp INTEGER,

    -- From DataCatalog (quality)
    row_count INTEGER,
    missing_days_count INTEGER,
    ohlcv_violations INTEGER,
    validation_passed BOOLEAN,

    -- From ParquetMetadataCatalog (file)
    file_checksum TEXT,
    file_size_bytes INTEGER,

    -- Timestamps
    created_at INTEGER,
    updated_at INTEGER
);

CREATE TABLE bundle_symbols (
    -- From ParquetMetadataCatalog
    bundle_name TEXT,
    symbol TEXT,
    asset_type TEXT,
    exchange TEXT
);

CREATE TABLE bundle_cache (
    -- From ParquetMetadataCatalog
    cache_key TEXT PRIMARY KEY,
    bundle_name TEXT,
    parquet_path TEXT,
    last_accessed INTEGER,
    size_bytes INTEGER
);
```

---

## Consequences

### Positive
✅ **Single source of truth** - all metadata in one schema
✅ **Atomic updates** - transactional consistency (SQLite)
✅ **Simpler queries** - one JOIN vs two database lookups
✅ **Per-bundle scope** - metadata co-located with data
✅ **Easier migration** - script merges both catalogs

### Negative
⚠️ **Migration complexity** - must preserve all existing metadata
⚠️ **Breaking change** - old catalog APIs must be deprecated
⚠️ **Storage increase** - duplicate bundle_name in all tables (denormalized)

### Neutral
- Old `DataCatalog` and `ParquetMetadataCatalog` kept as deprecated wrappers
- Migration script required with rollback capability
- Performance roughly equivalent (SQLite indexed queries)

---

## Alternatives Considered

### Alternative 1: Keep Catalogs Separate, Add Sync Layer
**Rejected because:**
- Complexity: sync logic between catalogs (eventual consistency issues)
- Still two schemas to maintain
- Doesn't solve developer confusion

### Alternative 2: Global Unified Catalog
**Rejected because:**
- Scalability: single SQLite DB for all bundles (lock contention)
- Bundle portability: can't move bundle without global catalog
- Violates bundle isolation (bundles should be self-contained)

### Alternative 3: NoSQL/Document Store (JSON)
**Rejected because:**
- Query performance: no indexes, must scan full documents
- Schema evolution: no migrations, JSON fields inconsistent
- Tooling: SQLite has better Python support (stdlib)

---

## Implementation Plan

### Phase 1: Schema Design (Complete)
- [x] Define unified schema with all fields
- [x] Add indexes for common queries
- [x] Document foreign key relationships

### Phase 2: Migration Script (Story X1.3)
```python
def migrate_catalogs(dry_run=True):
    """Merge DataCatalog + ParquetMetadataCatalog → BundleMetadata."""

    # Backup old catalogs
    backup_catalog_databases()

    # Transactional migration
    with BundleMetadata.transaction() as txn:
        for bundle in DataCatalog.list_bundles():
            # Merge provenance
            txn.insert_metadata(bundle)

            # Merge quality
            txn.insert_quality(bundle)

            # Merge symbols
            for symbol in ParquetMetadataCatalog.get_symbols(bundle):
                txn.insert_symbol(symbol)

            # Merge cache entries
            for entry in ParquetMetadataCatalog.get_cache(bundle):
                txn.insert_cache_entry(entry)

        if dry_run:
            txn.rollback()
            print("DRY RUN: Would migrate X bundles...")
        else:
            txn.commit()
            print("✅ Migration complete")
```

### Phase 3: Backwards Compatibility (Story X1.3)
```python
class DataCatalog:
    """Deprecated wrapper around BundleMetadata."""

    def __init__(self):
        warnings.warn(
            "DataCatalog is deprecated, use BundleMetadata",
            DeprecationWarning,
            stacklevel=2
        )

    def store_metadata(self, bundle_name, metadata):
        # Forward to unified catalog
        BundleMetadata.update(bundle_name, **metadata)
```

### Phase 4: Removal (v2.0)
- Remove old catalog classes
- Update all imports to `BundleMetadata`
- Breaking change documented in CHANGELOG

---

## Migration Safety Measures

### 1. Dry Run Mode
```bash
python scripts/migrate_catalog.py --dry-run
# Preview: Would migrate 347 bundles, 12,450 symbols
```

### 2. Backup Before Migration
```python
def backup_catalog_databases():
    timestamp = int(time.time())
    shutil.copy(
        "~/.zipline/data/catalog.db",
        f"~/.zipline/backups/catalog-{timestamp}.db"
    )
```

### 3. Rollback Capability
```python
def rollback_migration(backup_timestamp):
    """Restore old catalogs from backup."""
    shutil.copy(
        f"~/.zipline/backups/catalog-{backup_timestamp}.db",
        "~/.zipline/data/catalog.db"
    )
    print("✅ Rollback complete")
```

### 4. Validation Checks
```python
def validate_migration():
    """Compare row counts before/after."""
    old_count = DataCatalog.count_bundles()
    new_count = BundleMetadata.count_bundles()
    assert old_count == new_count, "Bundle count mismatch!"
```

---

## Metrics for Success

- [ ] Migration script merges 100% of existing metadata
- [ ] Zero data loss (checksums match before/after)
- [ ] Backwards compatibility: old APIs work with warnings
- [ ] Performance: <10% query latency increase
- [ ] Rollback tested and documented

---

## Related Decisions
- [ADR 001: Unified DataSource Abstraction](001-unified-data-source-abstraction.md)
- [ADR 003: Smart Caching Layer](003-smart-caching-layer.md)

---

## References
- [Epic X1 Architecture](../epic-X1-unified-data-architecture.md)
- [Story X1.3: Unified Metadata Management](../../stories/X1.4.unified-metadata-management.story.md)
