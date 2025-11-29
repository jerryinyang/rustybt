# Story 2.4: Implement Subprocess Execution Runner

Status: done

## Story

As a developer,
I want a runner that executes strategies in isolated subprocesses,
so that rustybt and Backtrader don't conflict during execution.

## Acceptance Criteria

1. **run_rustybt_strategy() function implemented** - `rustybt/validation/runner.py`:
   - Executes rustybt strategy in subprocess
   - Parameters: strategy_module, data_path, output_log, params (optional)
   - Uses `subprocess.run()` with capture_output=True
   - Returns CompletedProcess object
   - Enforces timeout (default 300 seconds)

2. **run_backtrader_strategy() function implemented**:
   - Executes Backtrader strategy in subprocess
   - Same parameter interface as rustybt runner
   - Uses separate execution script
   - Returns CompletedProcess object

3. **Subprocess execution uses sys.executable**:
   - Ensures same Python interpreter
   - Passes parameters via command line arguments
   - JSON serializes params dict

4. **Runners capture stdout/stderr**:
   - text=True for string output
   - capture_output=True captures both streams
   - Output available for error diagnostics

5. **Timeout enforcement**:
   - Default 300 second timeout
   - Raises TimeoutExpired on timeout
   - Configurable per call

6. **Integration test executes simple strategy**:
   - Execute same strategy in both frameworks
   - Verify both produce log files
   - Verify exit codes

## Tasks / Subtasks

- [x] Task 1: Create runner.py module (AC: #1, #2)
  - [x] Create `rustybt/validation/runner.py`
  - [x] Import subprocess, sys, json, Path
  - [x] Add module docstring
  - [x] Define DEFAULT_TIMEOUT = 300

- [x] Task 2: Implement run_rustybt_strategy() (AC: #1, #3, #4, #5)
  - [x] Define function signature with type hints
  - [x] Build command list using sys.executable
  - [x] Target module: rustybt.validation.execute_rustybt
  - [x] Add --strategy, --data, --output arguments
  - [x] JSON serialize params if provided
  - [x] Call subprocess.run() with timeout
  - [x] Return CompletedProcess

- [x] Task 3: Implement run_backtrader_strategy() (AC: #2, #3, #4, #5)
  - [x] Define function signature matching rustybt
  - [x] Build command list using sys.executable
  - [x] Target module: rustybt.validation.execute_backtrader
  - [x] Same argument structure as rustybt
  - [x] Call subprocess.run() with timeout
  - [x] Return CompletedProcess

- [x] Task 4: Write unit tests
  - [x] Create `tests/validation/test_runner.py`
  - [x] Test command construction
  - [x] Test timeout parameter
  - [x] Test params serialization
  - [x] Mock subprocess.run for isolated testing

- [x] Task 5: Write integration test (AC: #6)
  - [x] Create simple test strategy for both frameworks
  - [x] Execute both using runners
  - [x] Verify log files created
  - [x] Verify exit codes (0 = success)
  - [x] Skip if Backtrader not installed

## Dev Notes

### Learnings from Previous Story

**From Story 2-3 (Status: drafted)**

- **Decorators Created**: @log_signal, @log_order, @log_portfolio in `rustybt/validation/decorators.py`
- **_log_event() Required**: Both base classes have the logging interface
- **Framework-Agnostic Design**: Decorators work with both frameworks

**Runner depends on base classes** (from Story 2.1, 2.2):
- Strategies must extend ValidatedStrategy base classes
- Strategies produce JSONL logs at output_log path
- Log schema is identical for both frameworks

[Source: docs/sprint-artifacts/2-1-strategy-comparison-infrastructure-story-1.md]
[Source: docs/sprint-artifacts/2-2-strategy-comparison-infrastructure-story-2.md]
[Source: docs/sprint-artifacts/2-3-strategy-comparison-infrastructure-story-3.md]

### Architecture Alignment

**Subprocess Isolation Pattern** (Architecture pg 249-268):
- Execute rustybt and Backtrader in separate processes
- Prevents dependency conflicts
- Clean environment isolation
- Mirrors real-world usage patterns

**ADR-004** (Architecture pg 650-662):
- Decision: Run frameworks in separate subprocesses
- Rationale: Prevents import conflicts, clean isolation
- Alternatives rejected: Same process (conflicts), Docker (overkill)

### Implementation Pattern

```python
import subprocess
import sys
import json
from pathlib import Path
from typing import Optional

DEFAULT_TIMEOUT = 300  # 5 minutes


def run_rustybt_strategy(
    strategy_module: str,
    data_path: Path,
    output_log: Path,
    params: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> subprocess.CompletedProcess:
    """Execute rustybt strategy in subprocess.

    Args:
        strategy_module: Python module path to strategy class
        data_path: Path to data fixture (Parquet)
        output_log: Path for JSONL log output
        params: Optional strategy parameters
        timeout: Execution timeout in seconds (default 300)

    Returns:
        CompletedProcess with returncode, stdout, stderr

    Raises:
        TimeoutExpired: If execution exceeds timeout
    """
    cmd = [
        sys.executable, "-m", "rustybt.validation.execute_rustybt",
        "--strategy", strategy_module,
        "--data", str(data_path),
        "--output", str(output_log),
    ]
    if params:
        cmd.extend(["--params", json.dumps(params)])

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )


def run_backtrader_strategy(
    strategy_module: str,
    data_path: Path,
    output_log: Path,
    params: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> subprocess.CompletedProcess:
    """Execute Backtrader strategy in subprocess.

    Args:
        strategy_module: Python module path to strategy class
        data_path: Path to data fixture (Parquet)
        output_log: Path for JSONL log output
        params: Optional strategy parameters
        timeout: Execution timeout in seconds (default 300)

    Returns:
        CompletedProcess with returncode, stdout, stderr

    Raises:
        TimeoutExpired: If execution exceeds timeout
    """
    cmd = [
        sys.executable, "-m", "rustybt.validation.execute_backtrader",
        "--strategy", strategy_module,
        "--data", str(data_path),
        "--output", str(output_log),
    ]
    if params:
        cmd.extend(["--params", json.dumps(params)])

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )
```

### Project Structure Notes

**Files to create**:
- `rustybt/validation/runner.py` (NEW - subprocess runners)
- `tests/validation/test_runner.py` (NEW - unit tests)

**Files to modify**:
- `rustybt/validation/__init__.py` (MODIFIED - export runner functions)

**Dependencies**: No new dependencies (uses Python stdlib: subprocess, sys, json)

### Testing Guidance

**Unit tests (mocked)**:
```python
import pytest
from unittest.mock import patch, MagicMock
from rustybt.validation.runner import run_rustybt_strategy, run_backtrader_strategy

class TestRunner:
    @patch('subprocess.run')
    def test_run_rustybt_builds_correct_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        run_rustybt_strategy(
            strategy_module="test.strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl")
        )

        # Verify command structure
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd
        assert "rustybt.validation.execute_rustybt" in cmd
        assert "--strategy" in cmd
        assert "--data" in cmd
        assert "--output" in cmd
```

**Integration test (requires both frameworks)**:
```python
@pytest.mark.integration
def test_dual_execution(tmp_path, validation_data_fixture):
    """Test executing strategy in both frameworks."""
    rb_log = tmp_path / "rustybt.jsonl"
    bt_log = tmp_path / "backtrader.jsonl"

    rb_result = run_rustybt_strategy(
        strategy_module="tests.validation.strategies.rustybt.simple",
        data_path=validation_data_fixture,
        output_log=rb_log
    )

    bt_result = run_backtrader_strategy(
        strategy_module="tests.validation.strategies.backtrader.simple",
        data_path=validation_data_fixture,
        output_log=bt_log
    )

    assert rb_result.returncode == 0
    assert bt_result.returncode == 0
    assert rb_log.exists()
    assert bt_log.exists()
```

### References

- [Source: docs/architecture.md - Subprocess Isolation Pattern (pg 249-268)]
- [Source: docs/architecture.md - ADR-004 Subprocess Isolation]
- [Source: docs/epics.md - Story 2.4 specification]
- [Source: docs/sprint-artifacts/2-1-strategy-comparison-infrastructure-story-1.md]
- [Source: docs/sprint-artifacts/2-2-strategy-comparison-infrastructure-story-2.md]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/2-4-strategy-comparison-infrastructure-story-4.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Implemented runner module with two main functions: run_rustybt_strategy() and run_backtrader_strategy()
- Both functions use subprocess.run() with capture_output=True, text=True
- Default timeout set to 300 seconds, configurable per call
- Params are JSON serialized when provided

### Completion Notes List

- ✅ Created `rustybt/validation/runner.py` with subprocess execution functions
- ✅ Implemented run_rustybt_strategy() and run_backtrader_strategy()
- ✅ Both use sys.executable for consistent Python interpreter
- ✅ Added DEFAULT_TIMEOUT = 300 constant
- ✅ Updated `rustybt/validation/__init__.py` to export runner functions
- ✅ Created comprehensive unit tests in `tests/validation/test_runner.py` (16 tests)
- ✅ Created integration tests in `tests/validation/test_runner_integration.py` (10 tests)
- ✅ All 146 validation tests pass with no regressions

### File List

**New Files:**
- `rustybt/validation/runner.py` - Subprocess execution runner functions
- `tests/validation/test_runner.py` - Unit tests for runner module
- `tests/validation/test_runner_integration.py` - Integration tests for dual framework execution
- `tests/validation/strategies/rustybt/simple_strategy.py` - Simple test strategy for rustybt
- `tests/validation/strategies/bt_strategies/simple_strategy.py` - Simple test strategy for Backtrader

**Modified Files:**
- `rustybt/validation/__init__.py` - Added exports for runner functions

---

## Review Section

### Code Review Summary (2025-11-26)

**Reviewer:** Senior Developer (Code Review Workflow)
**Status:** ✅ **APPROVED**

#### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC1: run_rustybt_strategy() | ✅ PASS | `rustybt/validation/runner.py:42-118` - Full implementation |
| AC2: run_backtrader_strategy() | ✅ PASS | `runner.py:121-197` - Mirrors rustybt interface |
| AC3: Uses sys.executable | ✅ PASS | Line 98-99, 177-178 |
| AC4: Captures stdout/stderr | ✅ PASS | `capture_output=True, text=True` in subprocess.run() |
| AC5: Timeout enforcement | ✅ PASS | DEFAULT_TIMEOUT = 300, configurable per call |
| AC6: Integration test | ✅ PASS | `test_runner_integration.py` - 10 integration tests |

#### Code Quality Assessment

**Strengths:**
1. **Clean interface** - Both runners have identical signatures for consistency
2. **Proper error handling** - subprocess.TimeoutExpired raised on timeout
3. **Path handling** - Converts Path objects to strings for command line
4. **JSON serialization** - Params dict safely serialized
5. **Comprehensive docstrings** - NumPy style with examples

**Architecture Compliance:**
- ✅ Follows ADR-004 (Subprocess Isolation)
- ✅ Uses sys.executable for interpreter consistency
- ✅ No framework imports in runner module (isolation preserved)

**Test Coverage:**
- `test_runner.py`: 16 unit tests (mocked subprocess)
- `test_runner_integration.py`: 10 integration tests
  - `test_executes_simple_strategy` for both frameworks
  - `test_dual_execution_produces_logs` - Full validation chain
  - `test_logs_have_compatible_schema` - Cross-framework verification

#### Test Results

```
tests/validation/test_runner.py: 16 tests PASSED
tests/validation/test_runner_integration.py: 10 tests PASSED
```

#### Recommended Actions

**No blocking issues identified.**

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-25 | Story drafted from epics.md specification | SM Agent |
| 2025-11-25 | Implementation complete - all ACs satisfied | Dev Agent |
| 2025-11-26 | Code review completed - APPROVED | Code Review Workflow |
