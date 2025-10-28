# [2025-10-27 18:48:44] - Fix Bundle SID Mapping Mismatch

**Commit:** [Pending]
**Focus Area:** Framework - Data Bundles
**Severity:** 🔴 CRITICAL

---

## ⚠️ MANDATORY PRE-FLIGHT CHECKLIST

### For Framework Code Updates: Pre-Flight Checklist

- [x] **Understanding**
  - [x] Understand code to be modified: `rustybt/data/bundles/metadata.py:403`, `rustybt/data/polars/parquet_writer.py:574`
  - [x] Reviewed related code: `rustybt/data/adapters/utils.py:87` (build_symbol_sid_map)
  - [x] Understand side effects: All bundle ingestions will use consistent SIDs
  - [x] Confirmed issue: Parquet files use SIDs 1-25, database uses auto-increment SIDs 1290-1314

- [x] **Standards Review**
  - [x] Read `docs/internal/architecture/coding-standards.md` (loaded at session start)
  - [x] Read `docs/internal/architecture/zero-mock-enforcement.md` (loaded at session start)
  - [x] Understand CR-002 (Zero-Mock) requirements - NO MOCKS in tests
  - [x] Understand CR-004 (Type Safety) requirements - full type hints

- [x] **Testing Strategy**
  - [x] Plan tests BEFORE writing code (TDD approach)
  - [x] Tests use real implementations (NO MOCKS per CR-002)
  - [x] Tests cover: explicit SID, auto-increment SID, SID conflicts
  - [x] Target 90%+ code coverage

- [x] **Type Safety**
  - [x] Plan complete type hints (Python 3.12+ syntax)
  - [x] Plan mypy --strict compliance
  - [x] Plan proper error handling for SID conflicts

- [x] **Environment Ready**
  - [x] Testing environment available
  - [x] Linting tools available
  - [x] Type checking available

- [x] **Impact Analysis**
  - [x] Identified all affected components: BundleMetadata, ParquetWriter
  - [x] No breaking changes - backward compatible (SID is optional)
  - [x] Existing bundles unaffected, new ingestions will be fixed

**Code Pre-Flight Complete**: [x] YES [ ] NO

---

## User-Reported Issue

**User Error:**
```
KeyError: <class 'rustybt.assets._assets.Asset'>
```

**After fixing dispatch reader, discovered:**
```
"No data found for 1 assets between 2021-06-11 and 2021-06-11"
```

**User Scenario:**
User ingested forex bundle programmatically using `temp/ingests/stocks_forex.py`. When running backtest with the bundle, all assets show "not tradable" even though data exists.

**Expected Behavior:**
Backtest should access data from parquet files using asset SIDs.

**Actual Behavior:**
- Asset database has SIDs: 1290-1314 (from auto-increment)
- Parquet files have SIDs: 1-25 (from `build_symbol_sid_map`)
- Reader looks for SID 1314 but parquet only has SID 25
- Result: "No data found"

**Impact:**
- 🔴 CRITICAL: ALL programmatically ingested bundles have mismatched SIDs
- Affects any bundle created via `DataSource.ingest_to_bundle()`
- Data is ingested correctly but cannot be accessed
- Silent data corruption - no errors during ingestion

---

## Issues Found

**Issue 1: SID mapping mismatch** - `rustybt/data/adapters/utils.py:87`
`build_symbol_sid_map()` always starts SID numbering from 1, creating a local mapping (1-25) that doesn't match the global asset database.

**Issue 2: Auto-increment SID assignment** - `rustybt/data/bundles/metadata.py:451`
`BundleMetadata.add_symbol()` uses database auto-increment for SIDs, which continues from previous bundles (e.g., 1290-1314), creating mismatch with parquet SIDs.

**Issue 3: No SID parameter in add_symbol** - `rustybt/data/bundles/metadata.py:403`
`add_symbol()` method doesn't accept explicit SID, forcing use of auto-increment.

---

## Root Cause Analysis

**Why did this issue occur:**
1. Two separate SID assignment mechanisms exist in parallel
2. `build_symbol_sid_map()` creates local sequential SIDs for parquet files
3. `BundleMetadata.add_symbol()` uses global auto-increment for asset database
4. No synchronization between the two systems
5. Programmatic ingestion exposes the bug (CLI might have different path)

**What pattern should prevent recurrence:**
1. Single source of truth for SID assignment
2. `add_symbol()` should accept explicit SID parameter
3. Parquet writer should pass SID from symbol_map to add_symbol()
4. Add validation to detect SID mismatches during ingestion
5. Add integration test for programmatic bundle ingestion

---

## Tests Added/Modified

**Status:** [Pending]

**Test Cases** (planned):
1. `test_add_symbol_with_explicit_sid` - Verify explicit SID is used
2. `test_add_symbol_auto_increment` - Verify backward compatibility
3. `test_sid_consistency_after_ingestion` - Verify parquet and DB match
4. `test_multiple_bundles_sid_isolation` - Verify bundle SIDs don't conflict

**Zero-Mock Compliance**: ✅
- Uses real database operations
- Uses real parquet file I/O
- No mocking frameworks

**Coverage**: Target 90%+

---

## Fixes Applied

**Status:** [Pending]

**1. Modified `rustybt/data/bundles/metadata.py:add_symbol()`**
- Added optional `sid` parameter (default None)
- When `sid` provided, use it instead of auto-increment
- When `sid` is None, use auto-increment (backward compatible)
- Added conflict detection if SID already exists

**2. Modified `rustybt/data/polars/parquet_writer.py:_autopopulate_bundle_metadata()`**
- Extract SID from symbol_map
- Pass SID to `BundleMetadata.add_symbol()`
- Ensures parquet SID matches database SID

---

## Documentation Updated

**Planned updates:**
- [ ] Add docstring note about explicit SID parameter
- [ ] Document SID assignment behavior
- [ ] Add warning in migration guide about re-ingesting old bundles

---

## Verification

- [ ] All tests pass
- [ ] Linting clean
- [ ] Type checking passes
- [ ] No zero-mock violations
- [ ] Manual test: Re-ingest forex bundle with fix
- [ ] Manual test: Verify SIDs match between parquet and database
- [ ] Manual test: Run aura.py strategy successfully

---

## Files Modified

- [ ] `rustybt/data/bundles/metadata.py` - Add `sid` parameter to `add_symbol()`
- [ ] `rustybt/data/polars/parquet_writer.py` - Pass SID when calling `add_symbol()`
- [ ] `tests/data/bundles/test_bundle_metadata.py` - Add tests for explicit SID

---

## Statistics

- Issues found: 3 (SID map, auto-increment, no SID param)
- Issues fixed: [Pending]
- Tests added: [Pending]
- Lines changed: [Pending]

---

## Commit Hash

[Pending]

---

## Branch

`fix/20251027-184838-bundle-sid-mapping-mismatch`

---

## Notes

- This bug was discovered while investigating the handle_data argument bug
- The dispatch reader fix exposed this deeper SID mismatch issue
- Affects ALL programmatically ingested bundles
- Backward compatible fix - existing bundles unaffected, new ingestions will be correct

---
