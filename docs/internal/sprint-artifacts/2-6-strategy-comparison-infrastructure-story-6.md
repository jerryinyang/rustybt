# Story 2.6: Implement Log Schema Validation

Status: done

## Story

As a developer,
I want validation that log files follow the expected schema,
so that comparison can detect malformed logs before processing.

## Acceptance Criteria

1. **validate_log_schema() function implemented** - `rustybt/validation/log_parser.py`:
   - Validates JSONL log file against expected schema
   - Streams file to handle large logs (no full memory load)
   - Returns ValidationResult with valid flag, line_count, errors

2. **Schema validation checks required fields**:
   - "timestamp" field required on every entry
   - "layer" field required on every entry
   - "event" field required on every entry

3. **Schema validation checks valid layer values**:
   - Valid layers: {"data", "signals", "orders", "broker", "portfolio"}
   - Invalid layer values reported with line number

4. **Schema validation detects JSON errors**:
   - Invalid JSON lines detected
   - Line number included in error message
   - Parsing continues after errors (collects all errors)

5. **ValidationResult dataclass implemented**:
   - `valid: bool` - True if no errors
   - `line_count: int` - Total lines processed
   - `errors: list[str]` - List of error messages

6. **CLI command for validation**:
   - `rustybt-validate log validate <log_path>`
   - Output: "✓ Valid (1234 lines)" or "✗ Invalid (5 errors)"

7. **Unit tests cover validation scenarios**:
   - Valid log files pass
   - Missing required fields detected
   - Invalid JSON detected
   - Invalid layer values detected

## Tasks / Subtasks

- [x] Task 1: Create/update log_parser.py module (AC: #1, #2, #3, #4)
  - [x] Create or update `rustybt/validation/log_parser.py`
  - [x] Import json, Path, dataclasses
  - [x] Define VALID_LAYERS constant set
  - [x] Implement validate_log_schema() function

- [x] Task 2: Implement ValidationResult dataclass (AC: #5)
  - [x] Create ValidationResult dataclass
  - [x] Fields: valid (bool), line_count (int), errors (list[str])
  - [x] Add __str__ method for nice output

- [x] Task 3: Implement schema validation logic (AC: #2, #3, #4)
  - [x] Stream file line by line (don't load fully into memory)
  - [x] Parse each line as JSON
  - [x] Check required fields: timestamp, layer, event
  - [x] Check layer value is in VALID_LAYERS
  - [x] Collect all errors (don't stop at first)
  - [x] Return ValidationResult

- [x] Task 4: Add CLI command (AC: #6)
  - [x] Update `rustybt/validation/cli.py`
  - [x] Add "log validate" subcommand
  - [x] Accept log_path argument
  - [x] Call validate_log_schema()
  - [x] Print formatted output

- [x] Task 5: Write unit tests (AC: #7)
  - [x] Create `tests/validation/test_log_parser.py`
  - [x] Test valid log file passes
  - [x] Test missing timestamp field
  - [x] Test missing layer field
  - [x] Test missing event field
  - [x] Test invalid layer value
  - [x] Test invalid JSON line
  - [x] Test multiple errors collected

## Dev Notes

### Learnings from Previous Story

**From Story 2-5 (Status: drafted)**

- **Execution Scripts Created**: `execute_rustybt.py`, `execute_backtrader.py`
- **Log Files Produced**: Both scripts output JSONL to --output path
- **Consistent Schema**: Both frameworks produce logs with same schema

**Log validation runs before comparison** (from Story 2.5):
- Execution produces JSONL files
- Validation ensures schema correctness
- Comparison assumes validated logs

[Source: docs/sprint-artifacts/2-5-strategy-comparison-infrastructure-story-5.md]

### Architecture Alignment

**Log Schema** (Architecture pg 183-189):
```json
{
  "timestamp": "2020-01-15T09:30:00",  // Required
  "layer": "data|signals|orders|broker|portfolio",  // Required, must be valid
  "event": "bar_received|...",  // Required
  "asset": "AAPL",  // Optional
  "data": {...}  // Optional
}
```

**Validation Requirements**:
- Stream file to handle large logs (>100MB)
- Collect all errors (don't stop at first)
- Provide actionable error messages with line numbers

### Implementation Pattern

```python
import json
from pathlib import Path
from dataclasses import dataclass


VALID_LAYERS = {"data", "signals", "orders", "broker", "portfolio"}


@dataclass
class ValidationResult:
    """Result of log schema validation."""
    valid: bool
    line_count: int
    errors: list[str]

    def __str__(self) -> str:
        if self.valid:
            return f"✓ Valid ({self.line_count} lines)"
        return f"✗ Invalid ({len(self.errors)} errors)"


def validate_log_schema(log_path: Path) -> ValidationResult:
    """Validate JSONL log file against expected schema.

    Args:
        log_path: Path to JSONL log file

    Returns:
        ValidationResult with valid flag, line count, and errors

    Note:
        Streams file to handle large logs efficiently.
        Collects all errors rather than stopping at first.
    """
    errors: list[str] = []
    line_count = 0

    with open(log_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line_count += 1
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Parse JSON
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")
                continue

            # Check required fields
            if "timestamp" not in entry:
                errors.append(f"Line {line_num}: Missing 'timestamp' field")

            if "layer" not in entry:
                errors.append(f"Line {line_num}: Missing 'layer' field")
            elif entry.get("layer") not in VALID_LAYERS:
                errors.append(
                    f"Line {line_num}: Invalid layer '{entry.get('layer')}', "
                    f"must be one of: {', '.join(sorted(VALID_LAYERS))}"
                )

            if "event" not in entry:
                errors.append(f"Line {line_num}: Missing 'event' field")

    return ValidationResult(
        valid=len(errors) == 0,
        line_count=line_count,
        errors=errors
    )
```

**CLI command** (in cli.py):
```python
import click
from pathlib import Path
from rustybt.validation.log_parser import validate_log_schema

@cli.group()
def log():
    """Log file operations."""
    pass

@log.command()
@click.argument('log_path', type=click.Path(exists=True, path_type=Path))
def validate(log_path: Path):
    """Validate log file schema."""
    result = validate_log_schema(log_path)
    click.echo(str(result))

    if not result.valid:
        for error in result.errors[:10]:  # Show first 10 errors
            click.echo(f"  {error}")
        if len(result.errors) > 10:
            click.echo(f"  ... and {len(result.errors) - 10} more errors")
        raise SystemExit(1)
```

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/log_parser.py` (CREATE or UPDATE)
- `rustybt/validation/cli.py` (UPDATE - add log validate command)
- `tests/validation/test_log_parser.py` (CREATE)

**Dependencies**: No new dependencies (uses Python stdlib: json, dataclasses)

### Testing Guidance

**Test fixtures**:
```python
@pytest.fixture
def valid_log(tmp_path):
    """Create a valid JSONL log file."""
    log_path = tmp_path / "valid.jsonl"
    entries = [
        {"timestamp": "2020-01-01T09:30:00", "layer": "data", "event": "initialize", "data": {}},
        {"timestamp": "2020-01-01T09:30:01", "layer": "data", "event": "bar_received", "data": {}},
        {"timestamp": "2020-01-01T09:30:01", "layer": "signals", "event": "signal_computed", "data": {}},
    ]
    with open(log_path, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return log_path


@pytest.fixture
def invalid_log_missing_timestamp(tmp_path):
    """Create log with missing timestamp."""
    log_path = tmp_path / "invalid.jsonl"
    entries = [
        {"layer": "data", "event": "initialize"},  # Missing timestamp
    ]
    with open(log_path, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return log_path
```

**Test cases**:
```python
def test_valid_log_passes(valid_log):
    result = validate_log_schema(valid_log)
    assert result.valid
    assert result.line_count == 3
    assert len(result.errors) == 0


def test_missing_timestamp_detected(invalid_log_missing_timestamp):
    result = validate_log_schema(invalid_log_missing_timestamp)
    assert not result.valid
    assert "Missing 'timestamp'" in result.errors[0]


def test_invalid_layer_detected(tmp_path):
    log_path = tmp_path / "invalid_layer.jsonl"
    with open(log_path, 'w') as f:
        f.write('{"timestamp": "2020-01-01", "layer": "invalid", "event": "test"}\n')

    result = validate_log_schema(log_path)
    assert not result.valid
    assert "Invalid layer" in result.errors[0]
```

### References

- [Source: docs/architecture.md - Log Schema (pg 183-189)]
- [Source: docs/epics.md - Story 2.6 specification]
- [Source: docs/sprint-artifacts/2-5-strategy-comparison-infrastructure-story-5.md]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/2-6-strategy-comparison-infrastructure-story-6.context.xml`

### Agent Model Used

claude-opus-4-5-20251101

### Debug Log References

- Implemented log_parser.py with ValidationResult dataclass and validate_log_schema()
- Added CLI log validate command to cli.py
- Created comprehensive test suite with 18 passing tests

### Completion Notes List

- VALID_LAYERS constant contains the 5-layer validation architecture: data, signals, orders, broker, portfolio
- ValidationResult dataclass has valid, line_count, and errors fields with __str__ method
- validate_log_schema() streams file line-by-line for memory efficiency with large logs
- Added count_log_entries() helper function for later use in coordinator
- CLI command: `rustybt-validate log validate <log_path>`
- All 18 unit tests pass covering valid logs, missing fields, invalid JSON, invalid layers

### File List

- `rustybt/validation/log_parser.py` (MODIFIED - added ValidationResult, VALID_LAYERS, validate_log_schema, count_log_entries)
- `rustybt/validation/cli.py` (MODIFIED - added log group and validate command)
- `rustybt/validation/__init__.py` (MODIFIED - exported new log_parser items)
- `tests/validation/test_log_parser.py` (NEW - 18 unit tests)

---

## Review Section

### Code Review Summary (2025-11-26)

**Reviewer:** Senior Developer (Code Review Workflow)
**Status:** ✅ **APPROVED**

#### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC1: validate_log_schema() | ✅ PASS | `rustybt/validation/log_parser.py:40-96` - Streams file, returns ValidationResult |
| AC2: Required fields check | ✅ PASS | Checks timestamp, layer, event on every entry |
| AC3: Valid layer values | ✅ PASS | VALID_LAYERS set, invalid values reported with line number |
| AC4: JSON error detection | ✅ PASS | JSONDecodeError caught, parsing continues |
| AC5: ValidationResult dataclass | ✅ PASS | valid, line_count, errors fields with __str__ |
| AC6: CLI command | ✅ PASS | `rustybt-validate log validate <path>` in cli.py |
| AC7: Unit tests | ✅ PASS | 18 tests covering all validation scenarios |

#### Code Quality Assessment

**Strengths:**
1. **Memory efficient** - File streaming with `for line_num, line in enumerate(f, 1)`
2. **Complete error collection** - Continues parsing after errors, collects all issues
3. **Actionable messages** - Line numbers included: `"Line {line_num}: ..."`
4. **Clean dataclass** - ValidationResult with `__str__` for CLI output
5. **Utility function** - `count_log_entries()` added for coordinator use

**VALID_LAYERS Verification:**
```python
VALID_LAYERS: set[str] = {"data", "signals", "orders", "broker", "portfolio"}
```
Matches architecture spec exactly.

#### Test Results

```
tests/validation/test_log_parser.py: 18 tests PASSED
```

Test Classes:
- `TestValidationResult`: 3 tests
- `TestValidLayers`: 2 tests
- `TestValidateLogSchema`: 10 tests (valid, missing fields, invalid values, multiple errors)
- `TestCountLogEntries`: 3 tests

#### CLI Command Output

```
$ rustybt-validate log validate <path>
✓ Valid (1234 lines)
# or
✗ Invalid (5 errors)
  Line 42: Missing 'timestamp' field
  Line 57: Invalid layer 'invalid'
```

#### Recommended Actions

**No blocking issues identified.**

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-25 | Story drafted from epics.md specification | SM Agent |
| 2025-11-25 | Story implementation complete - all ACs satisfied | Dev Agent |
| 2025-11-26 | Code review completed - APPROVED | Code Review Workflow |
