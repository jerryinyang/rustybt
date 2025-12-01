# Story X.2: Design Shared Data Fixture Infrastructure

Status: done

## Story

As a **validation framework developer**,
I want **to design and implement data fixture infrastructure that ensures both rustybt and Backtrader consume identical synthetic data through their native data loading mechanisms**,
so that **validation comparisons are deterministic and any differences detected are truly behavioral rather than data-related**.

## Acceptance Criteria

1. **AC-X2.1:** Produce canonical Parquet file with OHLCV + asset + timestamp
   - Schema: timestamp (datetime64[ns, UTC]), asset (string), open/high/low/close (float64), volume (int64)
   - Consistent with existing validation fixture format
   - Stored in standard location for both frameworks to access

2. **AC-X2.2:** Deterministic data generation (seeded random)
   - Same seed produces identical data across runs
   - Configurable parameters: date range, asset count, data characteristics
   - No external data dependencies

3. **AC-X2.3:** rustybt receives identical bars as Backtrader
   - Both frameworks see same OHLCV values for each timestamp
   - No floating-point conversion differences
   - Timezone handling consistent

4. **AC-X2.4:** First bar, last bar, bar count match exactly
   - Timestamp comparison verifies alignment
   - OHLCV values match at boundaries
   - Total bar count identical

## Tasks / Subtasks

- [x] Task 1: Review Existing Fixture Generator (AC: #1, #2)
  - [x] 1.1: Read `rustybt/validation/generate_fixture.py` current implementation
  - [x] 1.2: Verify schema matches required format (timestamp, asset, OHLCV)
  - [x] 1.3: Confirm deterministic seeding is implemented
  - [x] 1.4: Identify any enhancements needed for rustybt DataBundle compatibility

- [x] Task 2: Analyze rustybt Data Loading (AC: #3, #4)
  - [x] 2.1: Based on X.1 findings, understand DataBundle/DataPortal requirements
  - [x] 2.2: Determine if Parquet can be loaded directly or needs conversion
  - [x] 2.3: Document any adapter/wrapper needed for rustybt consumption
  - [x] 2.4: Create helper function to register fixture as rustybt bundle

- [x] Task 3: Verify Backtrader Data Loading (AC: #3, #4)
  - [x] 3.1: Confirm existing PandasData feed works with fixture
  - [x] 3.2: Verify timestamp/timezone handling matches rustybt approach
  - [x] 3.3: Document any normalization needed for consistency

- [x] Task 4: Implement Data Loading Helpers in conftest.py (AC: #3, #4)
  - [x] 4.1: Create `load_fixture_for_rustybt()` helper
  - [x] 4.2: Create `load_fixture_for_backtrader()` helper
  - [x] 4.3: Ensure both return data in format their respective frameworks expect
  - [x] 4.4: Add pytest fixtures for validation tests

- [x] Task 5: Create Data Alignment Tests (AC: #4)
  - [x] 5.1: Test first bar matches (timestamp + OHLCV)
  - [x] 5.2: Test last bar matches (timestamp + OHLCV)
  - [x] 5.3: Test bar count matches
  - [x] 5.4: Test intermediate samples match (random sampling)

- [x] Task 6: Update generate_fixture.py if Needed (AC: #1, #2)
  - [x] 6.1: Add rustybt-compatible output option if required
  - [x] 6.2: Ensure schema documentation is updated
  - [x] 6.3: Add CLI options for format selection if needed

- [x] Task 7: Testing/Verification
  - [x] 7.1: Run fixture generation with fixed seed
  - [x] 7.2: Load fixture in both frameworks
  - [x] 7.3: Compare first/last/count programmatically
  - [x] 7.4: Verify determinism by regenerating with same seed

## Dev Notes

### Data Fixture Schema (from Tech Spec)

```
columns:
  - timestamp: datetime64[ns, UTC]
  - asset: string (e.g., "AAPL", "TEST_ASSET_0")
  - open: float64
  - high: float64
  - low: float64
  - close: float64
  - volume: int64
```

### Architecture Alignment

This story depends on findings from X.1 regarding:
- How rustybt's DataBundle/DataPortal expects data
- Whether direct Parquet loading is supported
- Any required adapters or registration steps

### Key Considerations

1. **Timezone Handling:** Both frameworks must interpret timestamps identically
   - Prefer UTC throughout to avoid ambiguity
   - Document any timezone conversion requirements

2. **Floating-Point Precision:** Parquet preserves float64 precision
   - No conversion through intermediate formats
   - Both frameworks should read identical binary values

3. **Asset Identification:** Consistent asset naming convention
   - Use simple string identifiers (e.g., "TEST_ASSET_0")
   - Avoid special characters that might be handled differently

### Testing Strategy

Primary test: Generate fixture → Load in rustybt → Load in Backtrader → Compare bar-by-bar

```python
def test_data_alignment():
    rustybt_bars = load_fixture_for_rustybt("fixture.parquet")
    bt_bars = load_fixture_for_backtrader("fixture.parquet")

    assert rustybt_bars[0].timestamp == bt_bars[0].timestamp
    assert rustybt_bars[0].close == bt_bars[0].close
    assert len(rustybt_bars) == len(bt_bars)
```

### Project Structure Notes

- Fixture location: `tests/validation/fixtures/validation_data.parquet`
- Helpers location: `tests/validation/conftest.py`
- Generator: `rustybt/validation/generate_fixture.py`

### References

- [Source: docs/internal/sprint-artifacts/tech-spec-epic-X.md#Data-Models-and-Contracts] - Data fixture schema
- [Source: docs/internal/planning/epics/epic-X-real-rustybt-engine-integration.md#Story-X2] - Story requirements
- [Source: docs/internal/planning/architecture.md#Data-Flow] - Data flow architecture

### Dependencies

- **Depends on:** Story X.1 (need to understand rustybt data loading API first)

## Dev Agent Record

### Context Reference

- docs/internal/sprint-artifacts/X-2-design-shared-data-fixture-infrastructure.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

1. **Fixture Generator Updated:** Added UTC timezone support to `generate_fixture.py` - timestamps now stored as `datetime64[ns, UTC]` for cross-framework consistency.

2. **Data Loading Helpers Implemented:** Created `load_fixture_for_rustybt()` and `load_fixture_for_backtrader()` in `tests/validation/conftest.py`:
   - `load_fixture_for_rustybt()` - Returns Polars DataFrame with UTC timestamps
   - `load_fixture_for_backtrader()` - Returns (bt.feeds.PandasData, asset_name) tuple
   - `get_fixture_info()` - Returns fixture metadata
   - `verify_data_alignment()` - Cross-framework alignment verification

3. **Alignment Tests Created:** 21 tests in `tests/validation/test_fixture.py` covering:
   - Schema validation (AC-X2.1)
   - Deterministic generation (AC-X2.2)
   - Cross-framework data identity (AC-X2.3)
   - First/last/count alignment (AC-X2.4)

4. **Default Fixture Generated:** Created `tests/validation/fixtures/validation_data.parquet` with 3 assets, 6 months of data, seed=42.

5. **All Tests Passing:** 21/21 tests pass verifying data alignment between frameworks.

### File List

**Created:**
- `tests/validation/test_fixture.py` - 21 alignment tests
- `tests/validation/fixtures/validation_data.parquet` - Default validation fixture

**Modified:**
- `rustybt/validation/generate_fixture.py` - Added UTC timezone support
- `tests/validation/conftest.py` - Added data loading helpers and pytest fixtures

### Test Results

```
21 passed, 8 warnings in 0.33s
```

All acceptance criteria verified:
- AC-X2.1 ✅ Parquet schema with UTC timestamps
- AC-X2.2 ✅ Deterministic generation (same seed = identical data)
- AC-X2.3 ✅ No floating-point differences between frameworks
- AC-X2.4 ✅ First/last/count match exactly

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2025-11-29 | SM Agent | Initial story draft created from Epic X tech spec |
| 2025-11-29 | Dev Agent | Completed all tasks, implemented data loading infrastructure, 21 tests passing, status → review |
| 2025-11-30 | Code Review | Senior Developer review completed |

## Code Review Notes

**Reviewed by:** Senior Developer (Claude Opus 4.5)
**Review Date:** 2025-11-30
**Review Type:** Story completion review

### Summary: APPROVED

### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC-X2.1 | ✅ PASS | `generate_fixture.py:112-117` produces UTC timestamps; schema matches spec |
| AC-X2.2 | ✅ PASS | `test_deterministic_generation_same_seed` verifies identical data with same seed |
| AC-X2.3 | ✅ PASS | `test_no_floating_point_conversion_differences` confirms bit-for-bit equality |
| AC-X2.4 | ✅ PASS | `test_bar_count_matches`, `test_first_bar_matches`, `test_last_bar_matches` all pass |

### Code Quality Assessment

**Files Reviewed:**
- `rustybt/validation/generate_fixture.py` - ✅ Clean, well-documented
- `tests/validation/conftest.py` - ✅ Good separation of concerns
- `tests/validation/test_fixture.py` - ✅ Comprehensive test coverage

**Test Verification:**
```
21 passed in 0.44s
```

### Findings

**Strengths:**
- UTC timezone handling is correctly implemented throughout
- Clean separation between rustybt and Backtrader data loading
- Comprehensive test coverage with 21 tests covering all AC requirements
- Helper functions follow good patterns (`load_fixture_for_rustybt()`, `load_fixture_for_backtrader()`)
- OHLC constraints validation ensures generated data is valid

**Minor Notes:**
- The `verify_data_alignment()` utility provides excellent debugging capability for future issues

### Recommendation

**APPROVED** - Story exceeds acceptance criteria with comprehensive test coverage and clean implementation. Data infrastructure is ready for use by subsequent stories.
