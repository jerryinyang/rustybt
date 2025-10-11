# Deprecation Timeline - Epic X1: Unified Data Architecture

**Last Updated**: 2025-10-08

## Overview

Epic X1 introduced unified data architecture. Old APIs are deprecated but remain functional until v2.0 to provide a safe migration path.

---

## Deprecation Schedule

### v1.x (Current - Now until Q2 2026)

**Status**: Deprecated with warnings
**Action Required**: Plan migration
**Breaking**: No

#### Deprecated APIs:
- `rustybt.data.catalog.DataCatalog` → Use `BundleMetadata`
- `rustybt.data.polars.metadata_catalog.ParquetMetadataCatalog` → Use `BundleMetadata`
- `rustybt.data.bundles.adapter_bundles.*_bundle()` functions → Use `DataSource.ingest_to_bundle()`
- `PolarsDataPortal(daily_reader=...)` → Use `PolarsDataPortal(data_source=...)`

#### What Happens:
```python
from rustybt.data.catalog import DataCatalog

catalog = DataCatalog()  # ⚠️ DeprecationWarning emitted
# Still works, but prints warning
```

---

### v2.0 (Estimated Q2 2026 - 6-12 months)

**Status**: Removed
**Action Required**: Must migrate
**Breaking**: Yes

#### Removed APIs:
- `DataCatalog` class deleted
- `ParquetMetadataCatalog` class deleted
- Story X1.1 bridge functions deleted (`adapter_bundles.py`)
- Legacy `PolarsDataPortal(daily_reader=...)` signature removed

#### What Happens:
```python
from rustybt.data.catalog import DataCatalog
# ModuleNotFoundError: No module named 'rustybt.data.catalog'
```

---

## Migration Path

### Immediate (v1.x)

1. **Update code** to use new APIs (see [Migration Guide](guides/migrating-to-unified-data.md))
2. **Run migration script**: `python scripts/migrate_catalog_to_unified.py --apply`
3. **Test thoroughly** with new APIs
4. **Monitor warnings** in logs

### Before v2.0 Release

1. **Fix all deprecation warnings** in your codebase
2. **Update dependencies** if using RustyBT as library
3. **Re-test all algorithms** with new APIs
4. **Backup data** before upgrading to v2.0

---

## API Migration Matrix

| Old API | New API | Migration Effort | Automated? |
|---------|---------|------------------|------------|
| `DataCatalog` | `BundleMetadata` | Low | ✅ Yes (script) |
| `ParquetMetadataCatalog` | `BundleMetadata` | Low | ✅ Yes (script) |
| `yfinance_profiling_bundle()` | `DataSource.ingest_to_bundle()` | Medium | ⚠️ Partial (manual code update) |
| `PolarsDataPortal(daily_reader=...)` | `PolarsDataPortal(data_source=...)` | Low | ❌ No (manual code update) |

---

## Checking for Deprecated API Usage

### Method 1: Run with Warnings as Errors

```bash
python -W error::DeprecationWarning your_algorithm.py
```

This will fail if any deprecated APIs are used.

### Method 2: Grep for Deprecated Imports

```bash
# Check your codebase
grep -r "from rustybt.data.catalog import DataCatalog" .
grep -r "ParquetMetadataCatalog" .
grep -r "adapter_bundles" .
grep -r "daily_reader=" .
```

### Method 3: Use Migration Validator

```bash
# Scans your code for deprecated patterns
python scripts/validate_deprecations.py --path /your/project
```

---

## Compatibility Matrix

| RustyBT Version | Old APIs Work? | New APIs Available? | Recommended Action |
|-----------------|----------------|---------------------|-------------------|
| v1.0 (pre-Epic 8) | ✅ Yes | ❌ No | Upgrade to v1.1+ |
| v1.1-v1.x (current) | ✅ Yes (with warnings) | ✅ Yes | Migrate to new APIs |
| v2.0+ (future) | ❌ No | ✅ Yes | Must use new APIs |

---

## Support Timeline

| Version | Support End Date | Security Patches | Bug Fixes |
|---------|------------------|------------------|-----------|
| v1.0 (pre-Epic 8) | 2025-12-31 | ❌ No | ❌ No |
| v1.x (current) | 2026-12-31 | ✅ Yes | ✅ Yes |
| v2.0+ | Ongoing | ✅ Yes | ✅ Yes |

---

## FAQ

### Can I keep using old APIs forever?

No. v2.0 (Q2 2026) will remove old APIs entirely. You must migrate before then.

### Will my old code break when I upgrade to v1.x?

No. Old APIs work with deprecation warnings. This gives you time to migrate.

### How much work is migration?

- **Automated**: Metadata migration via script (~5 minutes)
- **Manual**: Code updates (~2-8 hours depending on codebase size)
- **Testing**: Full backtest suite recommended (~1-2 days)

### Can I use both old and new APIs simultaneously?

Yes, during v1.x you can mix old and new APIs. This allows gradual migration.

### What if I find a bug during migration?

1. Check [Migration Guide](guides/migrating-to-unified-data.md) troubleshooting section
2. Post in GitHub Issues with `migration-bug` label
3. Rollback with `python scripts/migrate_catalog_to_unified.py --revert`

### Will v2.0 have other breaking changes?

We will announce full v2.0 breaking changes 6 months before release. Subscribe to our [release notes](https://github.com/rustybt/rustybt/releases).

---

## Resources

- [Migration Guide](guides/migrating-to-unified-data.md) - Step-by-step migration instructions
- [Architecture Docs](architecture/unified-data-management.md) - Understanding new system
- [API Reference](api/datasource-api.md) - New API documentation
- [GitHub Issues](https://github.com/rustybt/rustybt/issues) - Report migration problems
