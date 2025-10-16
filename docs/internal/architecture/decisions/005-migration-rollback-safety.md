# ADR 005: Migration Rollback and Transaction Safety

**Status:** Accepted
**Date:** 2025-10-05
**Epic:** Epic X1 - Unified Data Architecture
**Deciders:** Architect (Winston), Product Team

---

## Context

The Epic X1 migration merges two catalog systems (DataCatalog + ParquetMetadataCatalog) into unified BundleMetadata. This is a **high-risk operation**:

### Data at Risk
- **Provenance metadata**: Source URLs, API versions, fetch timestamps
- **Quality metrics**: Missing days, OHLCV violations, validation status
- **Symbol metadata**: Asset types, exchanges, 10,000+ symbols across bundles
- **Cache entries**: Parquet paths, checksums, LRU tracking
- **File metadata**: Checksums, sizes, partition info

### Migration Risks
1. **Partial failure**: Migrate 50% of bundles, then crash → inconsistent state
2. **Data corruption**: SQL syntax error → invalid foreign keys
3. **Disk full**: Write fails midway → incomplete migration
4. **User error**: Accidentally delete backup → no recovery
5. **Schema mismatch**: Old code expects old catalog → application breaks

### Current Gaps
The [story 8.1](../../stories/X1.1.adapter-bundle-bridge.story.md) migration plan lacks:
- ❌ Rollback mechanism
- ❌ Dry-run preview mode
- ❌ Validation checkpoints
- ❌ Backup automation
- ❌ Transaction safety

---

## Decision

Implement **transactional migration with rollback capability** using:

1. **SQLite Transactions**: All-or-nothing migration (ACID guarantees)
2. **Automatic Backup**: Create timestamped backup before migration
3. **Dry-Run Mode**: Preview changes without committing
4. **Savepoints**: Partial rollback to specific checkpoints
5. **Validation**: Compare row counts before/after
6. **Rollback Command**: Restore from backup if migration fails

### Migration Script Design

```python
class MigrationTransaction:
    """Transactional wrapper for SQLite migrations."""

    def __enter__(self):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("BEGIN IMMEDIATE")  # Acquire exclusive lock
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()  # Success
        else:
            self.conn.rollback()  # Failure

    def savepoint(self, name: str):
        """Create named savepoint for partial rollback."""
        self.conn.execute(f"SAVEPOINT {name}")

    def rollback_to_savepoint(self, name: str):
        """Rollback to specific checkpoint."""
        self.conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
```

### Backup Manifest

```python
@dataclass
class BackupManifest:
    timestamp: int                          # Unix timestamp
    backup_path: Path                       # ~/.zipline/backups/catalog-backup-{timestamp}
    datacatalog_checksum: str               # SHA256 of DataCatalog DB
    parquet_catalogs: Dict[str, str]        # bundle_name → checksum
    bundle_count: int                       # Total bundles backed up
```

---

## Migration Workflow

### Phase 1: Backup
```bash
python scripts/migrate_catalog_to_unified.py --backup
```

1. Create timestamped backup directory
2. Copy `catalog.db` (DataCatalog)
3. Copy all `{bundle}/metadata.db` (ParquetMetadataCatalog)
4. Calculate SHA256 checksums
5. Write `manifest.json` with checksums + metadata

**Output:**
```
Creating backup at ~/.zipline/backups/catalog-backup-1696512000...
  ✓ DataCatalog backed up (a3f2e1c9...)
  ✓ yfinance-daily/metadata.db backed up
  ✓ ccxt-hourly/metadata.db backed up
✓ Backup complete: 347 bundles backed up
```

### Phase 2: Dry Run
```bash
python scripts/migrate_catalog_to_unified.py --dry-run
```

1. Begin SQLite transaction
2. Migrate DataCatalog → BundleMetadata
3. Migrate ParquetMetadataCatalog → BundleMetadata
4. **Rollback transaction** (no changes saved)
5. Print preview summary

**Output:**
```
Starting migration...
Migrating DataCatalog... ✓
Migrating ParquetMetadataCatalogs... ✓

DRY RUN: Rolling back transaction (no changes saved)

Migration Preview (Dry Run)
┌──────────────────────────┬────────┐
│ Metric                   │  Count │
├──────────────────────────┼────────┤
│ Bundles Migrated         │    347 │
│ Symbols Migrated         │ 12,450 │
│ Cache Entries Migrated   │  1,023 │
│ Quality Records Migrated │    289 │
└──────────────────────────┴────────┘
```

### Phase 3: Execute Migration
```bash
python scripts/migrate_catalog_to_unified.py --backup
```

1. Create backup (Phase 1)
2. Begin SQLite transaction
3. Migrate DataCatalog with savepoint
   - If error: rollback to savepoint
4. Migrate ParquetMetadataCatalog with savepoint per bundle
   - If error: rollback to savepoint
5. Commit transaction (all-or-nothing)
6. Validate row counts

**Output:**
```
Creating backup at ~/.zipline/backups/catalog-backup-1696512000...
✓ Backup complete: 347 bundles backed up

Starting migration...
Migrating DataCatalog... ✓
Migrating ParquetMetadataCatalogs... ✓
✓ Transaction committed

Validating migration...
  ✓ Bundle count matches: 347
  ✓ Quality records match: 289
  ✓ Symbol counts match: 12,450
✓ Validation passed
```

### Phase 4: Rollback (If Needed)
```bash
python scripts/migrate_catalog_to_unified.py --rollback 1696512000
```

1. Load backup manifest
2. Restore `catalog.db` from backup
3. Restore all `{bundle}/metadata.db` from backup
4. Verify checksums match

**Output:**
```
Restoring from backup 1696512000...
  ✓ DataCatalog restored
  ✓ yfinance-daily/metadata.db restored
  ✓ ccxt-hourly/metadata.db restored
✓ Rollback complete
```

---

## Consequences

### Positive
✅ **Zero data loss risk** - Transaction rollback on any failure
✅ **Preview mode** - Dry run shows changes before commit
✅ **Automatic backup** - Timestamped archives with checksums
✅ **One-command rollback** - Instant restore from backup
✅ **Validation built-in** - Row count comparison after migration
✅ **Partial rollback** - Savepoints per bundle (isolate failures)

### Negative
⚠️ **Storage overhead** - Backup doubles disk usage temporarily
⚠️ **Migration time** - Backup + checksums add 30-60s overhead
⚠️ **Complexity** - More code to maintain (transaction logic)

### Neutral
- Backup directory grows over time (manual cleanup required)
- Dry run helpful for large catalogs (>1000 bundles)
- Exclusive lock during migration (other processes blocked)

---

## Transaction Safety Guarantees

### ACID Properties

1. **Atomicity**: All-or-nothing migration
   - SQLite transaction commits only if 100% success
   - Any error triggers full rollback

2. **Consistency**: Database constraints enforced
   - Foreign keys validated (bundle_name references)
   - Unique constraints checked (cache_key, symbols)

3. **Isolation**: Exclusive lock during migration
   - `BEGIN IMMEDIATE` acquires write lock
   - Other processes cannot modify catalog during migration

4. **Durability**: Committed changes persisted
   - SQLite WAL mode (write-ahead logging)
   - Checksums verify file integrity

### Savepoint Strategy

```python
def migrate_parquet_catalogs(txn, stats):
    for bundle in bundles:
        txn.savepoint(f"bundle_{bundle.name}")  # Checkpoint

        try:
            # Migrate symbols, cache for this bundle
            ...
        except Exception as e:
            txn.rollback_to_savepoint(f"bundle_{bundle.name}")  # Partial rollback
            stats.errors.append(f"Failed {bundle.name}: {e}")
            continue  # Skip this bundle, continue others
```

**Benefit**: Isolate failures to individual bundles (don't abort entire migration)

---

## Validation Checkpoints

### Pre-Migration
- [ ] Check disk space (need 2x catalog size for backup)
- [ ] Verify SQLite database accessible (not corrupted)
- [ ] Count bundles in DataCatalog
- [ ] Count symbols in ParquetMetadataCatalog

### Post-Migration
- [ ] Compare bundle counts (old vs new)
- [ ] Compare quality record counts
- [ ] Compare symbol counts
- [ ] Verify checksums match backup
- [ ] Test old APIs still work (backwards compat)

### Validation Script
```bash
python scripts/migrate_catalog_to_unified.py --validate
```

```python
def validate_migration() -> bool:
    # Compare bundle counts
    old_count = DataCatalog().count_bundles()
    new_count = BundleMetadata.count_bundles()
    assert old_count == new_count, "Bundle count mismatch!"

    # Compare quality metrics
    old_quality = DataCatalog().count_quality_metrics()
    new_quality = BundleMetadata.count_quality_records()
    assert old_quality == new_quality, "Quality record mismatch!"

    # Compare symbols
    old_symbols = sum(ParquetCatalog(b).count_symbols() for b in bundles)
    new_symbols = BundleMetadata.count_all_symbols()
    assert old_symbols == new_symbols, "Symbol count mismatch!"

    return True
```

---

## Error Recovery Scenarios

### Scenario 1: Disk Full During Migration
**Problem**: Write fails at 80% completion
**Recovery**:
1. Transaction rolls back (SQLite deletes partial writes)
2. Restore from backup (automatic if `--backup` used)
3. Free disk space
4. Re-run migration

### Scenario 2: SQLite Corruption
**Problem**: Database file corrupted midway
**Recovery**:
1. Transaction cannot commit (integrity check fails)
2. Automatic rollback
3. Restore from backup
4. Investigate corruption cause (disk errors, power loss)

### Scenario 3: User Interruption (Ctrl+C)
**Problem**: User cancels migration midway
**Recovery**:
1. Python `KeyboardInterrupt` caught
2. Transaction `__exit__` triggers rollback
3. Database unchanged
4. Re-run migration when ready

### Scenario 4: Schema Mismatch
**Problem**: Old code expects old catalog schema
**Recovery**:
1. Backwards compatibility layer (deprecated wrappers)
2. Old `DataCatalog` forwards to `BundleMetadata`
3. Deprecation warnings logged
4. Update code to use new APIs

---

## Testing Strategy

### Unit Tests
```python
def test_transaction_rollback():
    """Verify rollback on exception."""
    with pytest.raises(ValueError):
        with MigrationTransaction(db_path) as txn:
            txn.execute("INSERT INTO bundle_metadata ...")
            raise ValueError("Simulated error")

    # Verify no changes committed
    assert BundleMetadata.count_bundles() == 0

def test_savepoint_partial_rollback():
    """Verify savepoint rollback."""
    with MigrationTransaction(db_path) as txn:
        txn.execute("INSERT INTO bundle_metadata VALUES ('bundle1')")
        txn.savepoint("checkpoint1")

        txn.execute("INSERT INTO bundle_metadata VALUES ('bundle2')")
        txn.rollback_to_savepoint("checkpoint1")

        # Only bundle1 exists, bundle2 rolled back
        assert txn.execute("SELECT * FROM bundle_metadata").fetchall() == [('bundle1',)]
```

### Integration Tests
```python
@pytest.mark.integration
def test_full_migration_with_rollback():
    """End-to-end migration + rollback."""
    # Setup: create old catalogs
    datacatalog = DataCatalog()
    datacatalog.store_metadata({"bundle_name": "test", ...})

    # Backup
    manifest = create_backup(backup_dir)

    # Migrate
    stats = run_migration(dry_run=False, backup=False)
    assert stats.bundles_migrated == 1

    # Rollback
    restore_from_backup(manifest)

    # Verify old catalog restored
    assert datacatalog.count_bundles() == 1
```

### Stress Tests
```python
def test_migration_1000_bundles():
    """Stress test with large catalog."""
    # Create 1000 fake bundles
    for i in range(1000):
        datacatalog.store_metadata({"bundle_name": f"bundle_{i}", ...})

    stats = run_migration(dry_run=False)
    assert stats.bundles_migrated == 1000
    assert len(stats.errors) == 0
```

---

## Metrics for Success

- [ ] Dry run completes in <30s for 1000 bundles
- [ ] Migration with backup completes in <2min for 1000 bundles
- [ ] Rollback completes in <30s
- [ ] Validation detects 100% of data mismatches
- [ ] Zero data loss in production migrations
- [ ] Test coverage ≥95% for migration code

---

## Related Decisions
- [ADR 002: Unified Metadata Schema](002-unified-metadata-schema.md)
- [ADR 001: Unified DataSource Abstraction](001-unified-data-source-abstraction.md)

---

## References
- [Epic X1 Architecture](../epic-X1-unified-data-architecture.md)
- [Story X1.3: Unified Metadata Management](../../stories/X1.4.unified-metadata-management.story.md)
- [Migration Script](../../../scripts/migrate_catalog_to_unified.py)
- [SQLite Transaction Documentation](https://www.sqlite.org/lang_transaction.html)
