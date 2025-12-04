# Story 9.3: CME Data Ingestion & Bundle Verification

Status: done

## Story

As a **developer needing CME futures data locally**,
I want **to ingest CME OHLCV data with optional Definition enrichment into a local bundle**,
so that **I have correctly represented CME data available for backtesting**.

## Acceptance Criteria

1. **AC-9.3.1:** OHLCV ingestion works without Definition (backward compatible)
   - OHLCV data is ingested into a local bundle (works without Definition)
   - Existing adapter behavior preserved when Definition not provided
   - No breaking changes to current API

2. **AC-9.3.2:** Definition package enables metadata filtering when provided
   - `definition_package_path` config option added to `DatabentoConfig`
   - When Definition provided, metadata-driven features enabled
   - `include_user_defined_spreads=False` excludes instruments where `user_defined_instrument='Y'` or `instrument_class='T'`
   - `include_user_defined_spreads=True` (default) includes all instruments

3. **AC-9.3.3:** Graceful degradation when Definition absent
   - Filtering options that require Definition are ignored with warning
   - Clear warning logged when filter requested but Definition unavailable

4. **AC-9.3.4:** Bundle verification passes
   - Bundle contains expected instruments for date range
   - OHLCV values match source data (spot check)
   - instrument_id uniqueness preserved
   - With Definition: UDS filtering works correctly
   - With Definition: Metadata columns populated
   - Without Definition: Existing behavior unchanged

## Tasks / Subtasks

- [x] Task 1: Extend DatabentoConfig (AC: #2)
  - [x] 1.1: Add `definition_package_path: Optional[Path] = None`
  - [x] 1.2: Add `include_user_defined_spreads: bool = True`
  - [x] 1.3: Document new config options

- [x] Task 2: Integrate Definition Loading into Ingestion Flow (AC: #2, #3)
  - [x] 2.1: Load Definition data during ingestion if configured
  - [x] 2.2: Merge Definition metadata with OHLCV data
  - [x] 2.3: Implement UDS filtering based on Definition metadata

- [x] Task 3: Implement Graceful Degradation (AC: #1, #3)
  - [x] 3.1: Detect when Definition not configured
  - [x] 3.2: Log warning when filter requested but Definition unavailable
  - [x] 3.3: Ensure existing behavior unchanged without Definition

- [x] Task 4: Enrich Bundle with Metadata (AC: #2)
  - [x] 4.1: Add Definition metadata columns to bundle when available
  - [x] 4.2: Handle missing metadata gracefully

- [x] Task 5: Bundle Verification (AC: #4)
  - [x] 5.1: Verify bundle contains expected instruments
  - [x] 5.2: Spot check OHLCV values against source
  - [x] 5.3: Verify instrument_id uniqueness
  - [x] 5.4: Test UDS filtering with Definition
  - [x] 5.5: Test metadata population with Definition
  - [x] 5.6: Test backward compatibility without Definition

- [x] Task 6: Testing
  - [x] 6.1: Unit tests for config changes
  - [x] 6.2: Integration tests for Definition-enabled ingestion
  - [x] 6.3: Regression tests for backward compatibility

## Dev Notes

### Context and Purpose

This story integrates the CME Definition parsing from Story 9.2 into the actual ingestion workflow. The key principle is **optional enhancement** - Definition provides additional features but is never required.

### Config Changes

```python
@dataclass
class DatabentoConfig:
    # ... existing fields ...
    definition_package_path: Optional[Path] = None
    include_user_defined_spreads: bool = True  # Only applies when Definition available
```

### Graceful Degradation Pattern

```python
if self.config.definition_package_path is None:
    if not self.config.include_user_defined_spreads:
        logger.warning(
            "include_user_defined_spreads=False requires Definition package; ignoring"
        )
```

### Verification Checklist

- [ ] Bundle contains expected instruments for date range
- [ ] OHLCV values match source data (spot check)
- [ ] instrument_id uniqueness preserved
- [ ] With Definition: UDS filtering works correctly
- [ ] With Definition: Metadata columns populated
- [ ] Without Definition: Existing behavior unchanged

### Prerequisites

- Story 9.1 (exploration document)
- Story 9.2 (CME Definition parsing)

### References

- [Source: docs/internal/planning/epics/epic-9-databento-adapter-definition-integration.md] - Epic definition
- [Source: databento/docs/exploration-existing-infrastructure.md] - **CRITICAL** Story 9.1 exploration document with:
  - Section 1.5: Bundle output format (databento_instrument_mappings.json, metadata_columns.parquet)
  - Section 3.1: Extension points (where to hook Definition loading)
  - Section 3.3: DatabentoConfig additions (definition_package_path, include_user_defined_spreads)
  - Section 4: Risk assessment (backward compatibility)
- [Source: databento/docs/definition_dataset_structure.md] - Definition schema
- [Source: databento/docs/implementation_flaws_and_recommendations.md] - Current adapter limitations
- [Source: Story 9.2] - CME Definition parsing implementation

## Dev Agent Record

### Context Reference

- docs/internal/sprint-artifacts/9-3-cme-data-ingestion-bundle-verification.context.xml

### Agent Model Used

(To be assigned)

### Debug Log References

(None yet)

### Completion Notes List

(To be filled during implementation)

### File List

(To be filled during implementation)

## Code Review Notes

**Review Date**: 2025-12-02
**Reviewer**: Senior Dev Agent
**Status**: APPROVED

### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC-9.3.1 | ✅ PASS | Backward compatibility tested - ingestion works without Definition, existing behavior preserved |
| AC-9.3.2 | ✅ PASS | `definition_package_path` and `include_user_defined_spreads` config options work correctly |
| AC-9.3.3 | ✅ PASS | Warning logged when UDS filter requested without Definition: `databento_uds_filter_ignored` |
| AC-9.3.4 | ✅ PASS | Bundle verification passed - see Live Data Verification section |

### Test Coverage

- 45 tests pass for Definition functionality
- Tests include backward compatibility, graceful degradation, enrichment, and UDS filtering
- Real file fixtures used (no mocks)

### Live Data Verification (Bundle Ingestion Test)

Created test bundle `code_review_cme_test_20251202` with actual CME data:

**Input Data** (2025-10-15 to 2025-10-17):
- OHLCV rows before enrichment: **1,927**
- Unique symbols: 937

**Enrichment Results** (with `include_user_defined_spreads=False`):
- OHLCV rows after UDS filtering: **1,662**
- UDS rows filtered: **265**
- Columns added from Definition: `raw_symbol`, `asset`, `instrument_class`, `user_defined_instrument`, `underlying_id`, `expiration`, `activation`, `strike_price`, `min_price_increment`, `contract_multiplier`

**Bundle Contents**:
- `daily_bars/year=2025/month=10/data.parquet`: 1,662 rows, proper Decimal(18,8) schema
- `metadata_columns.parquet`: 1,662 rows with Definition enrichment
- `databento_instrument_mappings.json`: 673 instrument mappings

### Verification Checklist Update

- [x] Bundle contains expected instruments for date range
- [x] OHLCV values match source data (spot check verified)
- [x] instrument_id uniqueness preserved
- [x] With Definition: UDS filtering works correctly (265 rows filtered)
- [x] With Definition: Metadata columns populated (10 columns added)
- [x] Without Definition: Existing behavior unchanged

### Code Quality

- Logging: Comprehensive structlog logging including UDS filtering statistics
- Error handling: Graceful degradation patterns implemented
- Cleanup: Temp directories properly cleaned (verified in context manager)
- Performance: Efficient left join enrichment preserves all OHLCV rows

### No Issues Found

Story implementation fully meets all acceptance criteria. Bundle ingestion with Definition enrichment works correctly.

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2025-12-02 | SM Agent | Initial story draft created from Epic 9 |
| 2025-12-02 | Senior Dev Agent | Code review: APPROVED - All ACs verified with live data test |
