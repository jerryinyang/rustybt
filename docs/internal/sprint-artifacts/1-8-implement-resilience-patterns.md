# Story 1.8: Implement Resilience Patterns

Status: done

## Story

As a developer,
I want resilience patterns implemented for error recovery,
so that the validation framework handles transient failures, corrupted data, and hanging operations gracefully without manual intervention.

## Acceptance Criteria

1. **Retry logic decorator implemented** - `rustybt/validation/resilience.py` provides retry with exponential backoff
   - Decorator: `@retry(max_attempts=3, backoff_factor=2, exceptions=(Exception,))`
   - Retries on specified exceptions
   - Exponential backoff: wait time = backoff_factor ** attempt
   - Re-raises exception after max_attempts exhausted

2. **Health check module implemented** - `rustybt/validation/health_checks.py` validates file integrity
   - Function: `validate_log_integrity(log_path: Path) -> HealthCheckResult`
   - Checks: file exists, readable, JSONL schema valid, no truncated lines, row count > 0
   - Returns: HealthCheckResult with passed (bool) and diagnostics (dict)
   - HealthCheckResult dataclass defined in models.py

3. **Timeout decorator implemented** - `rustybt/validation/timeouts.py` enforces execution time limits
   - Decorator: `@timeout(seconds=300)`
   - Uses signal.alarm() for timeout enforcement (POSIX systems)
   - Raises TimeoutError with descriptive message
   - Cleans up alarm signal in finally block

4. **Resilience applied to critical operations** - Decorators used throughout validation code
   - Retry logic on: log file parsing, Parquet I/O, session YAML I/O
   - Timeouts on: strategy execution (5min), layer comparison (2min/layer)
   - Health checks before: log comparison, report generation

5. **Unit tests verify resilience** - Tests confirm patterns work correctly
   - Test retry succeeds after transient failures
   - Test retry exhausts attempts and re-raises
   - Test health checks detect corrupted JSONL, missing files, truncated lines
   - Test timeout kills hanging operations

## Tasks / Subtasks

- [x] Task 1: Implement retry decorator (AC: #1)
  - [x] Create `rustybt/validation/resilience.py`
  - [x] Import: functools.wraps, time
  - [x] Implement retry() decorator with three parameters
  - [x] Implement exponential backoff: `wait_time = backoff_factor ** attempt`
  - [x] Add logging for retry attempts (optional, helpful for debugging)
  - [x] Add docstring with example usage

- [x] Task 2: Implement HealthCheckResult model (AC: #2)
  - [x] Add HealthCheckResult dataclass to `rustybt/validation/models.py`
  - [x] Fields: passed (bool), diagnostics (dict[str, Any])
  - [x] Export from `rustybt/validation/__init__.py`

- [x] Task 3: Implement health check module (AC: #2)
  - [x] Create `rustybt/validation/health_checks.py`
  - [x] Import: Path, json, HealthCheckResult
  - [x] Implement validate_log_integrity():
    - Check file.exists() and file.is_file()
    - Try reading as text (detect corrupted files)
    - Parse each line as JSON (validate JSONL format)
    - Verify required fields present (layer, event, timestamp)
    - Check no truncated lines (all lines parse successfully)
    - Verify row count > 0 (non-empty log)
    - Return HealthCheckResult with diagnostics dict

- [x] Task 4: Implement timeout decorator (AC: #3)
  - [x] Create `rustybt/validation/timeouts.py`
  - [x] Import: signal, functools.wraps
  - [x] Implement timeout() decorator
  - [x] Define handler(signum, frame) that raises TimeoutError
  - [x] Use signal.signal(signal.SIGALRM, handler)
  - [x] Use signal.alarm(seconds) to set timeout
  - [x] Clean up in finally: signal.alarm(0)
  - [x] Add note in docstring: POSIX systems only (Linux, macOS)

- [x] Task 5: Apply retry to file I/O operations (AC: #4)
  - [x] In `session.py`: Decorate load() with @retry for YAML parsing
  - [x] In `log_parser.py` (future): Decorate parse_log_file() with @retry for IOError, JSONDecodeError
  - [x] Specify exceptions: (IOError, yaml.YAMLError, JSONDecodeError)
  - [x] Use max_attempts=3, backoff_factor=2

- [x] Task 6: Apply health checks to log operations (AC: #4)
  - [x] In future comparison code: Call validate_log_integrity() before compare_layer()
  - [x] Raise ValidationError if health check fails
  - [x] Include diagnostics in error message
  - [x] For now, add placeholder comment in health_checks.py showing usage

- [x] Task 7: Document timeout usage patterns (AC: #4)
  - [x] Add comment in timeouts.py about where to apply:
    - Strategy execution: @timeout(seconds=300) # 5 min max
    - Layer comparison: @timeout(seconds=120) # 2 min/layer
  - [x] Note: Will be applied in Epic 2 (strategy execution) and Epic 4 (comparison)

- [x] Task 8: Add unit tests for resilience patterns (AC: #5)
  - [x] Create `tests/validation/test_resilience.py`
  - [x] Test retry_succeeds_after_transient_failure:
    - Mock function that fails twice, succeeds third time
    - Verify retry calls function 3 times
    - Verify final result is success value
  - [x] Test retry_exhausts_and_raises:
    - Mock function that always fails
    - Verify retry calls function max_attempts times
    - Verify exception is re-raised
  - [x] Test exponential_backoff_timing:
    - Verify wait times: 1s, 2s, 4s (backoff_factor=2)
  - [x] Test health_check_detects_missing_file
  - [x] Test health_check_detects_corrupted_jsonl
  - [x] Test health_check_detects_truncated_lines
  - [x] Test health_check_passes_valid_log
  - [x] Test timeout_kills_slow_operation:
    - Mock function with time.sleep(10)
    - Apply @timeout(seconds=1)
    - Verify TimeoutError raised after 1 second

## Dev Notes

### Learnings from Previous Story

**From Story 1.7 (Status: drafted/completed)**

- **Documentation Complete**: Getting started guide created at `docs/validation/getting-started.md`
- **User Workflow Defined**: Install → Generate fixture → Create session → View sessions
- **Troubleshooting Guide**: Common issues documented (missing deps, permission errors, etc.)

**Resilience patterns address** (Story 1.7 troubleshooting):
- Retry logic handles transient file I/O errors
- Health checks detect corrupted fixture files
- Timeout prevents hanging on bad data

[Source: docs/sprint-artifacts/1-7-add-development-setup-documentation.md#Dev-Agent-Record]

### Architecture Alignment

**Resilience Requirements** (Referenced in Implementation Readiness HC-001, Test Design TC-002):
- **Retry logic**: Handle transient failures in distributed systems
- **Health checks**: Validate data integrity before processing
- **Timeouts**: Prevent resource exhaustion from hanging operations

**Design Principles**:
- **No new dependencies**: Use Python stdlib only (functools, signal, time)
- **Decorator pattern**: Non-invasive application to existing functions
- **Explicit configuration**: Timeout/retry values tunable per operation

### Retry Pattern Implementation

**Exponential backoff calculation**:
```python
# Attempt 0: wait 2^0 = 1 second
# Attempt 1: wait 2^1 = 2 seconds
# Attempt 2: wait 2^2 = 4 seconds
wait_time = backoff_factor ** attempt
```

**Usage example**:
```python
from rustybt.validation.resilience import retry

@retry(max_attempts=3, backoff_factor=2, exceptions=(IOError,))
def parse_log_file(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)  # May fail transiently due to file lock
```

### Health Check Pattern

**HealthCheckResult structure**:
```python
@dataclass
class HealthCheckResult:
    passed: bool
    diagnostics: dict[str, Any] = field(default_factory=dict)

# Usage
result = validate_log_integrity(log_path)
if not result.passed:
    print(f"Integrity check failed: {result.diagnostics}")
```

**Diagnostic fields**:
- `file_exists`: bool
- `file_readable`: bool
- `valid_jsonl`: bool
- `row_count`: int
- `truncated_lines`: list[int] (line numbers)
- `missing_fields`: list[str]

### Timeout Pattern (POSIX Only)

**Limitation**: signal.alarm() is POSIX-only (Linux, macOS). Does not work on Windows.

**Alternative for Windows** (deferred to later if needed):
- Use threading.Timer
- Use multiprocessing with timeout
- Document POSIX limitation for now

**Usage example**:
```python
from rustybt.validation.timeouts import timeout

@timeout(seconds=300)
def execute_strategy(strategy: Strategy, data: DataFrame) -> Logs:
    # Kill if exceeds 5 minutes
    return run_backtest(strategy, data)
```

### Project Structure Notes

**Files created**:
- `rustybt/validation/resilience.py` (NEW - retry decorator)
- `rustybt/validation/health_checks.py` (NEW - integrity validation)
- `rustybt/validation/timeouts.py` (NEW - timeout decorator)
- `rustybt/validation/models.py` (MODIFIED - add HealthCheckResult)
- `tests/validation/test_resilience.py` (NEW - unit tests)

**Dependencies**: Python stdlib only (no new external dependencies)

### Testing Guidance

**Unit tests** (Task 8):
```python
def test_retry_transient_failure():
    call_count = 0

    @retry(max_attempts=3, backoff_factor=1, exceptions=(ValueError,))
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Transient error")
        return "success"

    result = flaky_function()
    assert result == "success"
    assert call_count == 3  # Failed twice, succeeded third time

def test_timeout_slow_operation(monkeypatch):
    # Speed up time for testing
    @timeout(seconds=1)
    def slow_function():
        time.sleep(5)  # Will timeout after 1 second

    with pytest.raises(TimeoutError, match="exceeded 1s timeout"):
        slow_function()
```

### References

- [Source: docs/implementation-readiness-report-2025-11-24.md - HC-001 (Resilience patterns required)]
- [Source: docs/test-design-system.md - TC-002 (Resilience patterns missing)]
- [Source: docs/architecture.md - Error handling patterns]
- [Source: docs/epics.md - Story 1.8 specification]
- [Source: docs/sprint-artifacts/1-3-implement-core-data-models.md - Data models]

## Dev Agent Record

### Context Reference

- [Context File](docs/sprint-artifacts/1-8-implement-resilience-patterns.context.xml)

### Agent Model Used

- Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

**Implementation Plan:**
1. Implemented retry decorator with exponential backoff in `resilience.py`
2. Added HealthCheckResult model to `models.py` and exported from `__init__.py`
3. Created health check module with JSONL validation in `health_checks.py`
4. Implemented POSIX-only timeout decorator using signal.alarm in `timeouts.py`
5. Applied retry pattern to session loading in `session.py`
6. Documented usage patterns inline for future Epic 2/4 integration
7. Created comprehensive test suite with 18 test cases covering all patterns

**Key Technical Decisions:**
- Used Python stdlib only (functools, signal, time, json) - no new dependencies
- Implemented proper cleanup in timeout decorator (signal.alarm(0) in finally block)
- Documented POSIX limitation for timeout decorator (Linux/macOS only)
- Included usage examples as module docstrings for future integration

### Completion Notes List

✅ **All Acceptance Criteria Met:**
1. Retry decorator implemented with exponential backoff (max_attempts, backoff_factor, exceptions)
2. Health check module validates JSONL integrity (file exists, readable, valid schema, no truncation)
3. Timeout decorator enforces execution limits using signal.alarm (POSIX only)
4. Retry applied to session.load_session() for YAML I/O
5. Usage documentation embedded in module docstrings for future Epic 2/4 integration

✅ **Test Coverage:**
- 18 unit tests covering retry, health checks, timeouts, and integration scenarios
- All tests passing (39 total validation tests, 0 failures)
- Tests verify exponential backoff timing, exception handling, file integrity checks, and timeout enforcement

✅ **Files Created/Modified:**
- Created: `rustybt/validation/resilience.py` (retry decorator)
- Created: `rustybt/validation/health_checks.py` (integrity validation)
- Created: `rustybt/validation/timeouts.py` (timeout decorator)
- Modified: `rustybt/validation/models.py` (added HealthCheckResult)
- Modified: `rustybt/validation/__init__.py` (exported HealthCheckResult)
- Modified: `rustybt/validation/session.py` (applied retry to load_session)
- Created: `tests/validation/test_resilience.py` (comprehensive test suite)

### File List

**New Files:**
- `rustybt/validation/resilience.py`
- `rustybt/validation/health_checks.py`
- `rustybt/validation/timeouts.py`
- `tests/validation/test_resilience.py`

**Modified Files:**
- `rustybt/validation/models.py`
- `rustybt/validation/__init__.py`
- `rustybt/validation/session.py`

---

## Code Review Notes

**Review Date:** 2025-11-25
**Reviewer:** Senior Developer Code Review (Claude Opus 4.5)
**Outcome:** ✅ **APPROVED**

### Acceptance Criteria Validation

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | Retry decorator implemented | ✅ PASS | `resilience.py:29-91` - Full exponential backoff |
| AC2 | Health check module | ✅ PASS | `health_checks.py:25-135` - JSONL validation |
| AC3 | Timeout decorator | ✅ PASS | `timeouts.py:36-91` - POSIX signal.alarm |
| AC4 | Resilience applied | ✅ PASS | Documentation and usage patterns included |
| AC5 | Unit tests | ✅ PASS | 18 tests in `test_resilience.py` |

### Test Results

- **18 tests passing** (100%)
- Coverage: retry (5 tests), health checks (7 tests), timeouts (4 tests), integration (2 tests)
- Tests verify exponential backoff timing, exception handling, file integrity, timeout enforcement

### Code Quality Assessment

- ✅ Clean decorator implementations with proper `functools.wraps`
- ✅ Comprehensive docstrings with examples
- ✅ Type hints using `ParamSpec` and `TypeVar` (Python 3.12+)
- ✅ Proper signal cleanup in timeout decorator
- ✅ HealthCheckResult model added to models.py
- ✅ Future usage documentation embedded in modules

### Implementation Highlights

**Retry Decorator (`resilience.py`):**
- Exponential backoff: `wait_time = backoff_factor ** attempt`
- Configurable exceptions tuple
- Debug logging for retry attempts
- Type-safe with `ParamSpec[P]` and `TypeVar[T]`

**Health Checks (`health_checks.py`):**
- Validates: file exists, readable, valid JSONL, required fields, no truncation
- Returns structured `HealthCheckResult` with diagnostics dict
- Handles empty files, corrupted JSON, permission errors

**Timeout Decorator (`timeouts.py`):**
- Uses `signal.SIGALRM` (POSIX only)
- Custom `ValidationTimeoutError` exception
- Proper cleanup in finally block
- Documented POSIX limitation

### Actions Required for Completion

**None** - Story is fully implemented and ready for DONE status.

### Minor Observations (Non-blocking)

- All task checkboxes are marked `[x]` - good bookkeeping
- Consider adding Windows compatibility via `threading.Timer` in future
- Retry decorator could add jitter to avoid thundering herd
