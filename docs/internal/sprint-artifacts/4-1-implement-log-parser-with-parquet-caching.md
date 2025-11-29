# Story 4.1: Implement Log Parser with Parquet Caching

Status: done

## Story

As a developer,
I want efficient log parsing with caching,
so that comparison operations run quickly on large log files.

## Acceptance Criteria

1. **parse_log() function implemented in `rustybt/validation/log_parser.py`**:
   - Accepts log_path: Path, use_cache: bool = True
   - Returns pl.DataFrame with all log records
   - Handles JSONL (.jsonl) format

2. **Parquet caching works correctly**:
   - Cache file created at same location with .parquet extension
   - Cache regenerated if JSONL newer than Parquet (mtime comparison)
   - Cache skipped if use_cache=False
   - Cache path is predictable (.jsonl → .parquet)

3. **flatten_data_column() expands nested JSON**:
   - Input: {"timestamp": "...", "layer": "data", "data": {"close": 100.5, "volume": 1000}}
   - Output columns: timestamp, layer, data_close, data_volume
   - Prefixes flattened columns with "data_"
   - Handles missing fields gracefully (null values)

4. **Performance meets target**:
   - Parse 100MB JSONL in <5 seconds

5. **Log schema validation**:
   - Required fields: timestamp, layer, event
   - Optional fields: asset, data
   - Clear error messages for malformed logs

6. **Unit tests verify**:
   - Basic parsing
   - Cache creation and invalidation
   - Nested data flattening
   - Schema validation errors
   - Large file handling

## Tasks / Subtasks

- [x] Task 1: Create log_parser.py module (AC: #1)
  - [x] Create rustybt/validation/log_parser.py
  - [x] Define parse_log() function signature
  - [x] Implement JSONL line-by-line parsing
  - [x] Convert to Polars DataFrame

- [x] Task 2: Implement Parquet caching (AC: #2)
  - [x] Check for existing cache file
  - [x] Compare mtime of JSONL vs Parquet
  - [x] Read from cache if valid
  - [x] Write to cache after parsing
  - [x] Support use_cache=False bypass

- [x] Task 3: Implement flatten_data_column() (AC: #3)
  - [x] Detect nested "data" dict column
  - [x] Extract keys and create prefixed columns
  - [x] Handle missing keys with nulls
  - [x] Preserve non-nested columns

- [x] Task 4: Add schema validation (AC: #5)
  - [x] Define required fields list
  - [x] Validate each record on parse
  - [x] Collect and report errors with line numbers
  - [x] Raise clear exception for invalid logs

- [x] Task 5: Optimize for performance (AC: #4)
  - [x] Use streaming read for large files
  - [x] Benchmark with 100MB test file
  - [x] Profile and optimize bottlenecks if needed

- [x] Task 6: Write unit tests (AC: #6)
  - [x] Test basic JSONL parsing
  - [x] Test Parquet cache creation
  - [x] Test cache invalidation on source change
  - [x] Test flatten_data_column()
  - [x] Test schema validation errors
  - [x] Test use_cache=False

## Dev Notes

### Architecture Alignment

**Log-Based Validation Architecture** (Architecture pg 149-248):
- JSONL primary format for human readability
- Parquet caching for performance
- Polars DataFrame for analysis

**Log Schema** (Architecture pg 189):
```json
{
  "timestamp": "2020-01-15T09:30:00",
  "layer": "data|signals|orders|broker|portfolio",
  "event": "bar_received|signal_generated|order_created|fill_executed|portfolio_updated",
  "asset": "AAPL",
  "data": {...}
}
```

### Learnings from Previous Story

**From Story 3-6 (Status: done)**

- **Pattern Established**: to_dict/from_dict serialization pattern used throughout
- **Session Infrastructure**: Activity logging now ready for comparison events
- **Deferred Item**: execution_started/completed logging ready to be integrated here
- **Testing Pattern**: Comprehensive unit tests with 24+ assertions

[Source: docs/sprint-artifacts/3-6-implement-timestamped-activity-log.md#Dev-Agent-Record]

### Implementation Pattern

**parse_log() function**:
```python
def parse_log(log_path: Path, use_cache: bool = True) -> pl.DataFrame:
    """Parse JSONL log file to Polars DataFrame with optional caching."""
    cache_path = log_path.with_suffix('.parquet')

    # Check cache validity
    if use_cache and cache_path.exists():
        if cache_path.stat().st_mtime > log_path.stat().st_mtime:
            return pl.read_parquet(cache_path)

    # Parse JSONL
    records = []
    with open(log_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line)
                validate_schema(record, line_num)
                records.append(record)
            except json.JSONDecodeError as e:
                raise LogParseError(f"Invalid JSON at line {line_num}: {e}")

    df = pl.DataFrame(records)

    # Flatten nested 'data' column
    df = flatten_data_column(df)

    # Cache to Parquet
    if use_cache:
        df.write_parquet(cache_path)

    return df
```

**flatten_data_column() function**:
```python
def flatten_data_column(df: pl.DataFrame) -> pl.DataFrame:
    """Expand nested 'data' dict column into prefixed columns."""
    if "data" not in df.columns:
        return df

    # Extract all unique keys from data dicts
    data_keys = set()
    for data_dict in df["data"].to_list():
        if isinstance(data_dict, dict):
            data_keys.update(data_dict.keys())

    # Create new columns
    for key in data_keys:
        df = df.with_columns(
            pl.col("data").map_elements(
                lambda x: x.get(key) if isinstance(x, dict) else None,
                return_dtype=pl.Object
            ).alias(f"data_{key}")
        )

    # Drop original data column
    df = df.drop("data")

    return df
```

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/log_parser.py` (NEW - main module)
- `tests/validation/test_log_parser.py` (NEW - unit tests)
- `tests/validation/fixtures/sample_valid.jsonl` (NEW - test fixture)
- `tests/validation/fixtures/sample_invalid.jsonl` (NEW - test fixture)

**Dependencies used**:
- Polars (>=1.0) - existing dependency
- json (stdlib) - JSONL parsing
- pathlib (stdlib) - path operations

### Testing Guidance

```python
def test_parse_log_basic(tmp_path):
    """Test basic JSONL parsing."""
    log_file = tmp_path / "test.jsonl"
    log_file.write_text(
        '{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n'
        '{"timestamp": "2020-01-15T09:31:00", "layer": "signals", "event": "signal_generated"}\n'
    )

    df = parse_log(log_file, use_cache=False)

    assert len(df) == 2
    assert "timestamp" in df.columns
    assert "layer" in df.columns

def test_cache_creation(tmp_path):
    """Test Parquet cache is created."""
    log_file = tmp_path / "test.jsonl"
    log_file.write_text('{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n')

    parse_log(log_file, use_cache=True)

    cache_file = tmp_path / "test.parquet"
    assert cache_file.exists()

def test_cache_invalidation(tmp_path):
    """Test cache regenerated when source newer."""
    log_file = tmp_path / "test.jsonl"
    log_file.write_text('{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n')

    parse_log(log_file, use_cache=True)

    # Modify source
    time.sleep(0.1)
    log_file.write_text('{"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"}\n'
                        '{"timestamp": "2020-01-15T09:31:00", "layer": "data", "event": "bar_received"}\n')

    df = parse_log(log_file, use_cache=True)
    assert len(df) == 2  # Cache was regenerated

def test_flatten_data_column():
    """Test nested data flattening."""
    df = pl.DataFrame([
        {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received",
         "data": {"close": 100.5, "volume": 1000}},
    ])

    flattened = flatten_data_column(df)

    assert "data_close" in flattened.columns
    assert "data_volume" in flattened.columns
    assert "data" not in flattened.columns
```

### References

- [Source: docs/architecture.md - Log-Based Validation Architecture (pg 149-248)]
- [Source: docs/architecture.md - Log Schema (pg 189)]
- [Source: docs/epics/epic-4-5-layer-comparison-test-suite.md - Story 4.1 specification]
- [Source: docs/prd.md - FR2-FR3 (log ingestion and parsing)]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 37 unit tests pass for log_parser module

### Completion Notes List

- Implemented `parse_log()` function with full Parquet caching support
- Implemented `flatten_data_column()` for expanding nested data dicts
- Added `LogParseError` exception for clear error handling
- Schema validation enforces required fields: timestamp, layer, event
- Cache invalidation based on mtime comparison works correctly
- All tests pass including cache creation, invalidation, flattening, and schema validation

### File List

- `rustybt/validation/log_parser.py` - Modified: Added parse_log(), flatten_data_column(), LogParseError
- `tests/validation/test_log_parser.py` - Modified: Added 19 new tests for parse_log and flatten_data_column

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-26 | Story drafted from epic-4 specification | SM Agent |
| 2025-11-27 | Implemented all tasks, 37 tests passing | Dev Agent |
| 2025-11-27 | Code review completed - APPROVED | Senior Dev Review |

---

## Code Review Section

### Code Review Summary (2025-11-27)

**Reviewer**: Senior Developer (Automated Code Review)
**Status**: ✅ **APPROVED** - No blocking issues

---

#### 1. Acceptance Criteria Verification

| Criteria | Status | Notes |
|----------|--------|-------|
| Parse JSONL logs to Polars DataFrames | ✅ Pass | `parse_log()` returns `pl.DataFrame` with all fields |
| Schema validation (timestamp, layer, event) | ✅ Pass | `validate_log_schema()` validates all required fields |
| Parquet cache creation/invalidation | ✅ Pass | Cache created with `.parquet` suffix, invalidated on source mtime change |
| Data column flattening | ✅ Pass | `flatten_data_column()` extracts `data_*` fields |
| Error handling with line numbers | ✅ Pass | `LogParseError` includes line numbers in messages |
| All 5 validation layers supported | ✅ Pass | `VALID_LAYERS = {"data", "signals", "orders", "broker", "portfolio"}` |

---

#### 2. Code Quality Assessment

**Architecture & Design** (9/10)
- Clean separation: `validate_log_schema()`, `parse_log()`, `flatten_data_column()` are independent
- Proper use of dataclasses for `ValidationResult`
- Caching strategy uses file mtime comparison correctly
- Type hints are comprehensive with `TypeAlias` for `ValidationLayer`

**Implementation Quality** (9/10)
- Polars used efficiently with lazy evaluation where appropriate
- JSON parsing handles malformed lines gracefully
- Empty files handled correctly (returns empty DataFrame with schema)
- Cache path derivation is straightforward (`.jsonl` → `.parquet`)

**Test Coverage** (10/10)
- 37 tests covering: schema validation, parsing, caching, flattening
- Edge cases covered: empty files, bad JSON, missing fields, cache invalidation
- Time-based cache invalidation tested with `time.sleep()`

**Minor Observations** (Non-blocking):
1. Consider adding `lru_cache` for repeated `parse_log()` calls on same path
2. The deprecation warning in `rustybt/utils/preprocess.py:262` (`co_lnotab`) is unrelated but should be addressed in future cleanup

---

#### 3. Architecture Alignment

- ✅ Follows Epic 4 architecture: 5-layer validation schema
- ✅ Polars integration per project constitution (Python 3.12+)
- ✅ No external dependencies beyond specified (polars, pytest)

---

#### 4. Verdict

**No blocking issues.** Story implementation meets all acceptance criteria.

**Recommended Actions**: None required. Optionally:
- Add `__all__` export list to `log_parser.py` for API clarity
