# Story 9.4: NASDAQ Definition Parsing & Schema Understanding

Status: done

## Story

As a **developer working with NASDAQ equity data**,
I want **to parse and understand the NASDAQ Definition dataset structure**,
so that **I can extract equity instrument metadata and extend parsing infrastructure**.

## Acceptance Criteria

1. **AC-9.4.1:** Parse NASDAQ Definition files successfully
   - Can parse symbol-based Definition files (`xnas-itch-{start}-{end}.definition.{SYMBOL}.csv.zst`)
   - **CRITICAL**: NASDAQ uses `split_symbols: true` (files per symbol, NOT per day like CME)
   - Parsing handles NASDAQ-specific schema (65 columns, but simpler usage)

2. **AC-9.4.2:** Document NASDAQ-specific schema differences from CME
   - Equity-relevant fields: `exchange`, `currency`, `lot_size`
   - Fields NOT applicable: `instrument_class` (no derivatives), `underlying_id`, `strike_price`, `expiration`

3. **AC-9.4.3:** Handle both CME and NASDAQ schemas
   - Parsing code auto-detects schema type (CME vs NASDAQ)
   - Unified API for loading Definition regardless of exchange

4. **AC-9.4.4:** Prevent instrument_id collision between exchanges
   - Exchange identifier included in composite key
   - CME and NASDAQ instruments distinguishable

## Tasks / Subtasks

- [x] Task 1: Implement NASDAQ Definition Parsing (AC: #1)
  - [x] 1.1: Extend `_parse_definition_file()` for NASDAQ schema
  - [x] 1.2: Handle NASDAQ symbol-split file pattern: `xnas-itch-{start}-{end}.definition.{SYMBOL}.csv.zst`
  - [x] 1.3: Implement `_find_definition_files_by_symbol()` (contrast with CME's `_find_definition_by_date()`)
  - [x] 1.4: Parse NASDAQ-specific columns

- [x] Task 2: Document Schema Differences (AC: #2)
  - [x] 2.1: Document equity-relevant fields (exchange, currency, lot_size)
  - [x] 2.2: Document non-applicable derivatives fields
  - [x] 2.3: Update `databento/docs/definition_dataset_structure.md` with NASDAQ schema

- [x] Task 3: Implement Schema Detection (AC: #3)
  - [x] 3.1: Add `_detect_definition_schema()` method
  - [x] 3.2: Auto-detect CME vs NASDAQ based on columns/values
  - [x] 3.3: Apply appropriate parsing logic based on schema

- [x] Task 4: Prevent Instrument ID Collision (AC: #4)
  - [x] 4.1: Design composite ID format: `{exchange}_{instrument_id}`
  - [x] 4.2: Implement `_create_composite_instrument_id()` for collision prevention
  - [x] 4.3: Ensure CME and NASDAQ instruments are distinguishable

- [x] Task 5: Testing
  - [x] 5.1: Unit tests for NASDAQ Definition parsing
  - [x] 5.2: Unit tests for schema detection
  - [x] 5.3: Integration tests with sample NASDAQ Definition data
  - [x] 5.4: Tests for cross-exchange ID uniqueness (39 tests passing)

## Dev Notes

### Context and Purpose

This story extends the Definition parsing infrastructure from Story 9.2 to support NASDAQ equities. The key difference is that NASDAQ has no derivatives hierarchy - only cash equities.

### NASDAQ Definition File Pattern

**CRITICAL DIFFERENCE FROM CME**: NASDAQ uses symbol-based splits, NOT date-based!

- File naming: `xnas-itch-{start_date}-{end_date}.definition.{SYMBOL}.csv.zst`
- Examples:
  - `xnas-itch-20180501-20251031.definition.AAPL.csv.zst` (active symbol)
  - `xnas-itch-20180501-20210125.definition.AAXN.csv.zst` (delisted symbol)
- Split strategy: `split_symbols: true` (from metadata.json)
- Compression: zstd
- Format: CSV with 65 columns (same as CME, but many fields unused for equities)
- Total files: 21,800+ symbol files
- Rows per symbol: ~1,888 (one row per trading day)

### Schema Detection

```python
def _detect_definition_schema(self, df: pl.DataFrame) -> str:
    """Detect whether Definition is CME or NASDAQ based on columns/values."""
    if "instrument_class" in df.columns and df["instrument_class"].is_not_null().any():
        return "CME"
    return "NASDAQ"
```

### Collision Prevention

```python
# Prefix instrument_id with exchange for cross-exchange uniqueness
composite_id = f"{exchange}_{instrument_id}"
```

### NASDAQ-Specific Considerations

- No UDS filtering needed (equities don't have user-defined spreads)
- No parent resolution needed (no derivatives hierarchy)
- Different metadata columns relevant (exchange, sector vs expiration, strike)

### Prerequisites

- Story 9.1 (exploration document with NASDAQ package analysis)
- Story 9.2 (reuses CME parsing patterns)

### References

- [Source: docs/internal/planning/epics/epic-9-databento-adapter-definition-integration.md] - Epic definition
- [Source: databento/docs/exploration-existing-infrastructure.md] - **CRITICAL** Story 9.1 exploration document with:
  - Section 2.2: NASDAQ package structure (symbol-split strategy, 21,800+ files, instrument_class='K')
  - Section 2.3: Schema comparison (CME vs NASDAQ field usage differences)
  - Section 3.1: Extension points (`_find_definition_by_symbol()` for NASDAQ)
  - Key discovery: NASDAQ `split_symbols: true` vs CME `split_duration: "day"`
- [Source: databento/docs/definition_dataset_structure.md] - Definition schema
- [Source: Story 9.2] - CME Definition parsing patterns (to be extended)

## Dev Agent Record

### Context Reference

- docs/internal/sprint-artifacts/9-4-nasdaq-definition-parsing-schema-understanding.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

(None)

### Completion Notes List

1. Implemented `_detect_definition_schema()` for auto-detecting CME vs NASDAQ based on instrument_class, user_defined_instrument, and underlying_id columns
2. Implemented `_find_definition_files_by_symbol()` for NASDAQ symbol-split file discovery
3. Implemented `_load_definition_for_symbols()` as unified API for both CME and NASDAQ
4. Extended `_get_definition_key_fields()` to return appropriate fields based on schema type (equity vs derivatives)
5. Implemented `_create_composite_instrument_id()` for cross-exchange collision prevention
6. Updated `_apply_definition_enrichment()` to handle both CME date-split and NASDAQ symbol-split strategies
7. Added comprehensive documentation in databento/docs/definition_dataset_structure.md for schema differences
8. Added 15 new tests for NASDAQ-specific functionality (39 total tests passing)

### File List

**Modified:**
- rustybt/data/adapters/databento_adapter.py - Added NASDAQ parsing methods
- databento/docs/definition_dataset_structure.md - Added CME vs NASDAQ schema comparison
- tests/data/adapters/test_databento_definition.py - Added NASDAQ-specific tests

**New Methods Added:**
- `_detect_definition_schema()` - Auto-detect CME vs NASDAQ
- `_find_definition_files_by_symbol()` - NASDAQ symbol-split file discovery
- `_load_definition_for_symbols()` - Unified API for CME/NASDAQ
- `_create_composite_instrument_id()` - Cross-exchange collision prevention

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2025-12-02 | SM Agent | Initial story draft created from Epic 9 |
