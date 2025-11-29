# Story 2.7: Implement Dual Framework Execution Coordinator

Status: done

## Story

As a developer,
I want a coordinator that executes both frameworks and collects logs,
so that validation can be performed with a single command.

## Acceptance Criteria

1. **execute_dual() function implemented** - `rustybt/validation/coordinator.py`:
   - Executes strategy in both rustybt and Backtrader
   - Creates log directories under session folder
   - Returns ExecutionResult with success status and log paths

2. **Execution workflow complete**:
   - Creates logs directory: `validation-sessions/{session_id}/logs/`
   - Calls run_rustybt_strategy() with output to rustybt.jsonl
   - Calls run_backtrader_strategy() with output to backtrader.jsonl
   - Validates both logs after execution

3. **ExecutionResult dataclass implemented**:
   - `rustybt_success: bool`
   - `backtrader_success: bool`
   - `rustybt_log: Path`
   - `backtrader_log: Path`
   - `rustybt_log_valid: bool`
   - `backtrader_log_valid: bool`
   - `errors: list[str]`
   - `success` property (all conditions met)

4. **CLI command for execution**:
   - `rustybt-validate run <session_id>`
   - Output: execution status for both frameworks
   - Shows log entry counts
   - Updates session status

5. **Session status updated after execution**:
   - Updates session.yaml with execution results
   - Stores execution timestamps
   - Records log file paths

6. **Integration test validates full flow**:
   - Create session
   - Execute dual
   - Verify both logs created
   - Verify logs pass validation

## Tasks / Subtasks

- [x] Task 1: Create coordinator.py module (AC: #1)
  - [x] Create `rustybt/validation/coordinator.py`
  - [x] Import runner functions, log_parser, session manager
  - [x] Define module structure

- [x] Task 2: Implement ExecutionResult dataclass (AC: #3)
  - [x] Create ExecutionResult dataclass
  - [x] Add all required fields
  - [x] Add success property
  - [x] Add __str__ method for nice output

- [x] Task 3: Implement execute_dual() function (AC: #1, #2)
  - [x] Accept Session, strategy_name, module paths, params
  - [x] Create logs directory under session
  - [x] Call run_rustybt_strategy()
  - [x] Call run_backtrader_strategy()
  - [x] Validate both logs
  - [x] Collect errors from all steps
  - [x] Return ExecutionResult

- [x] Task 4: Add CLI run command (AC: #4)
  - [x] Update `rustybt/validation/cli.py`
  - [x] Add "run" command
  - [x] Load session by ID
  - [x] Call execute_dual()
  - [x] Print results with formatting
  - [x] Show log entry counts

- [x] Task 5: Update session after execution (AC: #5)
  - [x] Add update_execution_result() to SessionManager
  - [x] Store execution timestamp
  - [x] Store log file paths
  - [x] Store success status
  - [x] Update session stage

- [x] Task 6: Write integration test (AC: #6)
  - [x] Create `tests/validation/test_coordinator.py`
  - [x] Test full execution flow
  - [x] Verify logs created
  - [x] Verify logs valid
  - [x] Verify session updated

## Dev Notes

### Learnings from Previous Story

**From Story 2-6 (Status: drafted)**

- **Log Validation Created**: `validate_log_schema()` in `rustybt/validation/log_parser.py`
- **ValidationResult**: Returns valid flag, line_count, errors list
- **CLI Command**: `rustybt-validate log validate <path>`

**Coordinator validates logs automatically** (from Story 2.6):
- After both executions complete
- Before returning result
- Invalid logs reported in ExecutionResult.errors

[Source: docs/sprint-artifacts/2-6-strategy-comparison-infrastructure-story-6.md]

### Architecture Alignment

**Execution Coordinator** (Architecture pg 249-268):
- Orchestrates dual framework execution
- Sequential execution for determinism (not parallel)
- Validates logs before comparison

**Session Integration** (Architecture pg 359-402):
- Stores logs under session directory
- Updates session.yaml with results
- Tracks execution timestamps

### Implementation Pattern

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime

from rustybt.validation.runner import run_rustybt_strategy, run_backtrader_strategy
from rustybt.validation.log_parser import validate_log_schema
from rustybt.validation.session import Session, SessionManager


@dataclass
class ExecutionResult:
    """Result of dual framework execution."""
    rustybt_success: bool
    backtrader_success: bool
    rustybt_log: Path
    backtrader_log: Path
    rustybt_log_valid: bool
    backtrader_log_valid: bool
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if both frameworks executed successfully with valid logs."""
        return (
            self.rustybt_success and
            self.backtrader_success and
            self.rustybt_log_valid and
            self.backtrader_log_valid
        )

    def __str__(self) -> str:
        if self.success:
            return "✓ Both frameworks executed successfully"
        parts = []
        if not self.rustybt_success:
            parts.append("rustybt execution failed")
        if not self.backtrader_success:
            parts.append("Backtrader execution failed")
        if not self.rustybt_log_valid:
            parts.append("rustybt log invalid")
        if not self.backtrader_log_valid:
            parts.append("Backtrader log invalid")
        return "✗ Execution failed: " + ", ".join(parts)


def execute_dual(
    session: Session,
    strategy_name: str,
    rustybt_module: str,
    backtrader_module: str,
    params: Optional[dict] = None
) -> ExecutionResult:
    """Execute strategy in both frameworks and collect logs.

    Args:
        session: Current validation session
        strategy_name: Name of strategy being validated
        rustybt_module: Python module path for rustybt strategy
        backtrader_module: Python module path for Backtrader strategy
        params: Optional strategy parameters

    Returns:
        ExecutionResult with success status and log paths
    """
    errors: list[str] = []

    # Create log paths
    logs_dir = Path(f"validation-sessions/{session.id}/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    rustybt_log = logs_dir / "rustybt.jsonl"
    backtrader_log = logs_dir / "backtrader.jsonl"

    # Execute rustybt
    rb_result = run_rustybt_strategy(
        strategy_module=rustybt_module,
        data_path=session.data_fixture,
        output_log=rustybt_log,
        params=params
    )
    if rb_result.returncode != 0:
        errors.append(f"rustybt execution failed: {rb_result.stderr}")

    # Execute Backtrader
    bt_result = run_backtrader_strategy(
        strategy_module=backtrader_module,
        data_path=session.data_fixture,
        output_log=backtrader_log,
        params=params
    )
    if bt_result.returncode != 0:
        errors.append(f"Backtrader execution failed: {bt_result.stderr}")

    # Validate logs
    rb_valid = ValidationResult(valid=False, line_count=0, errors=[])
    bt_valid = ValidationResult(valid=False, line_count=0, errors=[])

    if rustybt_log.exists():
        rb_valid = validate_log_schema(rustybt_log)
        if not rb_valid.valid:
            errors.extend([f"rustybt log: {e}" for e in rb_valid.errors])
    else:
        errors.append("rustybt log file not created")

    if backtrader_log.exists():
        bt_valid = validate_log_schema(backtrader_log)
        if not bt_valid.valid:
            errors.extend([f"Backtrader log: {e}" for e in bt_valid.errors])
    else:
        errors.append("Backtrader log file not created")

    return ExecutionResult(
        rustybt_success=rb_result.returncode == 0,
        backtrader_success=bt_result.returncode == 0,
        rustybt_log=rustybt_log,
        backtrader_log=backtrader_log,
        rustybt_log_valid=rb_valid.valid,
        backtrader_log_valid=bt_valid.valid,
        errors=errors
    )
```

**CLI command** (in cli.py):
```python
@cli.command()
@click.argument('session_id')
def run(session_id: str):
    """Execute validation for a session."""
    # Load session
    session = SessionManager.load(session_id)
    if not session:
        click.echo(f"Session not found: {session_id}")
        raise SystemExit(1)

    click.echo(f"Executing {session.strategy_name}...")

    # Execute dual
    result = execute_dual(
        session=session,
        strategy_name=session.strategy_name,
        rustybt_module=f"tests.validation.strategies.rustybt.{session.strategy_name}",
        backtrader_module=f"tests.validation.strategies.backtrader.{session.strategy_name}",
    )

    # Print results
    click.echo(str(result))
    if result.success:
        # Count log entries
        rb_count = count_log_entries(result.rustybt_log)
        bt_count = count_log_entries(result.backtrader_log)
        click.echo(f"  - rustybt: {rb_count} log entries")
        click.echo(f"  - backtrader: {bt_count} log entries")

        # Update session
        SessionManager.update_execution(session, result)
    else:
        for error in result.errors[:5]:
            click.echo(f"  Error: {error}")
        raise SystemExit(1)
```

### Project Structure Notes

**Files to create**:
- `rustybt/validation/coordinator.py` (NEW - execution coordinator)
- `tests/validation/test_coordinator.py` (NEW - integration tests)

**Files to modify**:
- `rustybt/validation/cli.py` (UPDATE - add run command)
- `rustybt/validation/session.py` (UPDATE - add update methods)
- `rustybt/validation/__init__.py` (UPDATE - export coordinator)

**Dependencies**: No new dependencies

### Testing Guidance

**Integration test**:
```python
@pytest.mark.integration
def test_execute_dual_flow(tmp_path, validation_data_fixture):
    """Test full dual execution flow."""
    # Create session
    session = SessionManager.create(
        strategy_name="simple_test",
        data_fixture=validation_data_fixture,
        base_path=tmp_path
    )

    # Execute
    result = execute_dual(
        session=session,
        strategy_name="simple_test",
        rustybt_module="tests.validation.strategies.rustybt.simple_test",
        backtrader_module="tests.validation.strategies.backtrader.simple_test",
    )

    # Verify
    assert result.rustybt_log.exists()
    assert result.backtrader_log.exists()
    assert result.rustybt_log_valid
    assert result.backtrader_log_valid
    assert result.success
```

**Unit tests**:
```python
def test_execution_result_success_property():
    result = ExecutionResult(
        rustybt_success=True,
        backtrader_success=True,
        rustybt_log=Path("/tmp/rb.jsonl"),
        backtrader_log=Path("/tmp/bt.jsonl"),
        rustybt_log_valid=True,
        backtrader_log_valid=True,
    )
    assert result.success

def test_execution_result_failure():
    result = ExecutionResult(
        rustybt_success=False,  # Failed
        backtrader_success=True,
        rustybt_log=Path("/tmp/rb.jsonl"),
        backtrader_log=Path("/tmp/bt.jsonl"),
        rustybt_log_valid=True,
        backtrader_log_valid=True,
    )
    assert not result.success
```

### References

- [Source: docs/architecture.md - Execution Coordinator]
- [Source: docs/architecture.md - Session Integration (pg 359-402)]
- [Source: docs/epics.md - Story 2.7 specification]
- [Source: docs/sprint-artifacts/2-6-strategy-comparison-infrastructure-story-6.md]
- [Source: docs/sprint-artifacts/2-4-strategy-comparison-infrastructure-story-4.md]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/2-7-strategy-comparison-infrastructure-story-7.context.xml`

### Agent Model Used

claude-opus-4-5-20251101

### Debug Log References

- Created coordinator.py with ExecutionResult dataclass and execute_dual() function
- Added CLI 'run' command to cli.py
- Added update_execution_result() to SessionManager
- Created comprehensive test suite with 14 passing tests

### Completion Notes List

- ExecutionResult dataclass tracks success/failure for both frameworks plus log validity
- execute_dual() orchestrates sequential execution of both frameworks
- Logs are stored under validation-sessions/{session_id}/logs/
- Session status updated to EXECUTED on success, FAILED on failure
- CLI command: `rustybt-validate run <session_id> [--rustybt-module] [--backtrader-module]`
- Added EXECUTED status to Session model status literal
- All 14 coordinator tests pass, 178 total validation tests pass

### File List

- `rustybt/validation/coordinator.py` (NEW - ExecutionResult, execute_dual)
- `rustybt/validation/cli.py` (MODIFIED - added run command)
- `rustybt/validation/session.py` (MODIFIED - added update_execution_result)
- `rustybt/validation/models.py` (MODIFIED - added EXECUTED to status literal)
- `rustybt/validation/__init__.py` (MODIFIED - exported coordinator items)
- `tests/validation/test_coordinator.py` (NEW - 14 unit tests)

---

## Review Section

### Code Review Summary (2025-11-26)

**Reviewer:** Senior Developer (Code Review Workflow)
**Status:** ✅ **APPROVED**

#### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC1: execute_dual() | ✅ PASS | `rustybt/validation/coordinator.py:74-154` - Full implementation |
| AC2: Execution workflow | ✅ PASS | Creates logs dir, calls both runners, validates logs |
| AC3: ExecutionResult dataclass | ✅ PASS | Lines 26-72 - All fields + success property |
| AC4: CLI run command | ✅ PASS | `rustybt-validate run <session_id>` in cli.py |
| AC5: Session status update | ✅ PASS | update_execution_result() in session.py |
| AC6: Integration test | ✅ PASS | 14 tests in test_coordinator.py |

#### Code Quality Assessment

**Strengths:**
1. **Sequential execution** - Follows architecture mandate for determinism (not parallel)
2. **Complete error collection** - All errors aggregated in ExecutionResult.errors
3. **Log validation** - Automatic validate_log_schema() call after execution
4. **Clear status tracking** - success property checks all 4 conditions:
   - `rustybt_success`
   - `backtrader_success`
   - `rustybt_log_valid`
   - `backtrader_log_valid`

**ExecutionResult.success Property:**
```python
@property
def success(self) -> bool:
    return (
        self.rustybt_success
        and self.backtrader_success
        and self.rustybt_log_valid
        and self.backtrader_log_valid
    )
```

**Architecture Compliance:**
- ✅ Sequential execution (not parallel) as per architecture spec
- ✅ Logs stored under `validation-sessions/{session_id}/logs/`
- ✅ Session status updated after execution

#### Test Results

```
tests/validation/test_coordinator.py: 14 tests PASSED
Total validation tests: 178 PASSED
```

Test Classes:
- `TestExecutionResult`: 9 tests (success property, str output, defaults)
- `TestExecuteDual`: 5 tests (creates logs, success, failures, invalid logs)

#### Recommended Actions

**No blocking issues identified.**

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-25 | Story drafted from epics.md specification | SM Agent |
| 2025-11-25 | Story implementation complete - all ACs satisfied | Dev Agent |
| 2025-11-26 | Code review completed - APPROVED | Code Review Workflow |
