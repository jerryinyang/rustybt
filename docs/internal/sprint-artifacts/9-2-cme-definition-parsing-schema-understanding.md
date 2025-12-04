# Story 9.2: CME Definition Parsing & Schema Understanding

Status: done

## Story

As a **developer working with CME futures data**,
I want **to implement CME Definition dataset parsing based on exploration findings**,
so that **I can extract instrument metadata and build reusable parsing infrastructure**.

## Acceptance Criteria

1. **AC-9.2.1:** Parse CME Definition files successfully
   - Can parse daily Definition files (`glbx-mdp3-{YYYYMMDD}.definition.csv.zst`)
   - Can decompress zstd-compressed CSV files
   - Parsing handles all 65 columns documented in schema

2. **AC-9.2.2:** Extract key metadata fields
   - `instrument_id`, `raw_symbol`, `symbol`, `asset`
   - `instrument_class` (F/C/P/S/T)
   - `user_defined_instrument` (Y/N)
   - `underlying_id` for parent relationships
   - `expiration`, `activation`, `strike_price`
   - `min_price_increment`, `contract_multiplier`

3. **AC-9.2.3:** Document schema findings
   - Column types and valid values
   - Instrument class distribution
   - User-Defined Spread identification patterns
   - Parent/child relationship structure via `underlying_id`

4. **AC-9.2.4:** Structure parsing code for reuse
   - Parsing methods added to `databento_adapter.py`
   - Code structured for extension in Story 9.4 (NASDAQ)

## Tasks / Subtasks

- [x] Task 1: Implement Definition File Parsing (AC: #1)
  - [x] 1.1: Add `_parse_definition_file()` method to adapter
  - [x] 1.2: Implement zstd decompression for Definition CSV
  - [x] 1.3: Handle CME Definition file pattern: `glbx-mdp3-{YYYYMMDD}.definition.csv.zst`
  - [x] 1.4: Parse CSV with correct column types (Polars schema)

- [x] Task 2: Extract Key Metadata Fields (AC: #2)
  - [x] 2.1: Extract core identification fields (instrument_id, raw_symbol, symbol, asset)
  - [x] 2.2: Extract instrument classification (instrument_class, user_defined_instrument)
  - [x] 2.3: Extract relationship fields (underlying_id)
  - [x] 2.4: Extract contract metadata (expiration, activation, strike_price, min_price_increment, contract_multiplier)

- [x] Task 3: Implement Date-Based Loading (AC: #1, #4)
  - [x] 3.1: Add `_load_definition_for_date()` method
  - [x] 3.2: Handle Definition package path configuration
  - [x] 3.3: Return None gracefully if Definition not configured

- [x] Task 4: Document Schema Findings (AC: #3)
  - [x] 4.1: Update `databento/docs/definition_dataset_structure.md` with parsing findings
  - [x] 4.2: Document column types and valid values
  - [x] 4.3: Document instrument class distribution
  - [x] 4.4: Document UDS identification patterns
  - [x] 4.5: Document parent/child relationships via underlying_id

- [x] Task 5: Testing
  - [x] 5.1: Create unit tests for `_parse_definition_file()`
  - [x] 5.2: Create unit tests for `_load_definition_for_date()`
  - [x] 5.3: Add integration test with sample CME Definition data

## Dev Notes

### Context and Purpose

This story implements the **CME Definition parsing infrastructure** that will be reused for NASDAQ in Story 9.4. The focus is on correct schema handling and reusable code patterns.

### Key Implementation Methods

```python
def _parse_definition_file(self, file_path: Path) -> pl.DataFrame:
    """Parse a single Definition CSV file.

    Returns DataFrame with instrument metadata indexed by instrument_id.
    """

def _load_definition_for_date(self, date: pd.Timestamp) -> Optional[pl.DataFrame]:
    """Load Definition data for a specific date.

    Returns None if Definition package not configured.
    """
```

### CME Definition File Pattern

- File naming: `glbx-mdp3-{YYYYMMDD}.definition.csv.zst`
- Compression: zstd
- Format: CSV with 65 columns

### Instrument Class Values

| Code | Meaning |
|------|---------|
| F | Future |
| C | Call Option |
| P | Put Option |
| S | Spread |
| T | User-Defined Spread (UDS) |

### Prerequisites

- Story 9.1 (exploration document provides integration plan)

### References

- [Source: docs/internal/planning/epics/epic-9-databento-adapter-definition-integration.md] - Epic definition
- [Source: databento/docs/exploration-existing-infrastructure.md] - **CRITICAL** Story 9.1 exploration document with:
  - Section 1: Current adapter architecture (DatabentoConfig, ingestion flow, symbology handling)
  - Section 2: Definition package analysis (CME day-split strategy, 65-column schema, 4,000 rows/day)
  - Section 3: Integration plan (new methods, config changes)
  - Section 4: Risk assessment
  - Appendix A: Complete 65-column reference
- [Source: databento/docs/definition_dataset_structure.md] - Existing Definition schema documentation
- [Source: databento/docs/implementation_flaws_and_recommendations.md] - Current adapter limitations

## Dev Agent Record

### Context Reference

- docs/internal/sprint-artifacts/9-2-cme-definition-parsing-schema-understanding.context.xml

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
| AC-9.2.1 | ✅ PASS | `_parse_definition_file()` at line 1284-1336 handles zstd decompression, parses all 65 columns |
| AC-9.2.2 | ✅ PASS | `_get_definition_key_fields()` at line 1449-1518 extracts all key metadata fields |
| AC-9.2.3 | ✅ PASS | Documentation in `databento/docs/exploration-existing-infrastructure.md` with complete schema reference |
| AC-9.2.4 | ✅ PASS | Code structured for reuse - NASDAQ-specific methods extend CME base pattern |

### Test Coverage

- 45 tests pass for Definition functionality
- Real file fixtures used (no mocks)
- Tests cover: parsing, loading, key field extraction, UDS filtering

### Live Data Verification

- Successfully parsed Definition for 2025-10-15: **3,434 rows, 65 columns**
- Instrument class distribution verified:
  - F (Futures): 355
  - S (Spreads): 1,581
  - C (Calls): 239
  - P (Puts): 239
  - T (UDS): 1,020
- User-Defined Spreads: 1,020 (29.7%)

### Code Quality

- Logging: Comprehensive structlog logging for all operations
- Error handling: Graceful degradation when Definition not configured
- Type hints: Proper type annotations throughout
- Documentation: Clear docstrings on all public methods

### No Issues Found

Story implementation fully meets all acceptance criteria.

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2025-12-02 | SM Agent | Initial story draft created from Epic 9 |
| 2025-12-02 | Senior Dev Agent | Code review: APPROVED - All ACs verified |
