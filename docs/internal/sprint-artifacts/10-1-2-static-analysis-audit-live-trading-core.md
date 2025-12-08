# Story 10.1.2: Static Analysis Audit of Live Trading Core

Status: done

## Story

As a **developer**,
I want **static analysis (ruff, mypy) run against all live trading core modules**,
So that **type errors, linting issues, and potential bugs are identified**.

## Acceptance Criteria

1. **AC1:** Static analysis (ruff check) is run on all 7 core live trading modules:
   - `rustybt/live/engine.py`
   - `rustybt/live/order_manager.py`
   - `rustybt/live/state_manager.py`
   - `rustybt/live/strategy_executor.py`
   - `rustybt/live/reconciler.py`
   - `rustybt/live/circuit_breakers.py`
   - `rustybt/live/data_feed.py`

2. **AC2:** Type checking (mypy) is run on all 7 core modules with `--show-error-codes` flag

3. **AC3:** All issues are captured in `tests/live/audit/findings/core_findings.yaml` using the schema from Story 10.1.1

4. **AC4:** Each finding has severity classification based on impact:
   - CRITICAL: Data loss, financial impact, security issues
   - HIGH: Incorrect behavior, crash potential
   - MEDIUM: Edge cases, non-critical error handling
   - LOW: Style, minor improvements

5. **AC5:** A summary report is generated showing counts by module and severity

6. **AC6:** Zero new ruff errors are introduced (existing violations documented)

7. **AC7:** Zero new mypy errors are introduced (existing violations documented)

## Tasks / Subtasks

- [x] Task 1: Run ruff static analysis on core modules (AC: #1)
  - [x] Run `ruff check rustybt/live/engine.py --output-format=json`
  - [x] Run `ruff check rustybt/live/order_manager.py --output-format=json`
  - [x] Run `ruff check rustybt/live/state_manager.py --output-format=json`
  - [x] Run `ruff check rustybt/live/strategy_executor.py --output-format=json`
  - [x] Run `ruff check rustybt/live/reconciler.py --output-format=json`
  - [x] Run `ruff check rustybt/live/circuit_breakers.py --output-format=json`
  - [x] Run `ruff check rustybt/live/data_feed.py --output-format=json`

- [x] Task 2: Run mypy type checking on core modules (AC: #2)
  - [x] Run `mypy rustybt/live/engine.py --show-error-codes`
  - [x] Run mypy on each remaining core module
  - [x] Capture all type errors with line numbers

- [x] Task 3: Create findings YAML file (AC: #3, #4)
  - [x] Create `tests/live/audit/findings/core_findings.yaml`
  - [x] Parse ruff JSON output and convert to finding schema
  - [x] Parse mypy output and convert to finding schema
  - [x] Assign finding IDs using E (Engine), O (OrderManager), etc.
  - [x] Classify severity based on issue type and impact

- [x] Task 4: Generate summary report (AC: #5)
  - [x] Count findings by module
  - [x] Count findings by severity
  - [x] Generate markdown summary table
  - [x] Include ruff and mypy baseline status

- [x] Task 5: Validate no new violations (AC: #6, #7)
  - [x] Compare against any existing baseline
  - [x] Document all existing violations
  - [x] Ensure CI can detect new violations

- [x] Task 6: Write tests for audit process (AC: #1-7)
  - [x] Test that ruff runs without crash
  - [x] Test that mypy runs without crash
  - [x] Test that findings file is valid YAML
  - [x] Test that all findings have required fields

## Dev Notes

### Focus Areas per Module (from PRD)

| Module | Key Focus Areas |
|--------|-----------------|
| `engine.py` | Main loop, event dispatch, error handling |
| `order_manager.py` | Order state machine, timeout handling |
| `state_manager.py` | Persistence, recovery, corruption prevention |
| `strategy_executor.py` | Signal handling, order generation |
| `reconciler.py` | Position sync, discrepancy detection |
| `circuit_breakers.py` | Safety limits, emergency stops |
| `data_feed.py` | Bar assembly, data integrity |

### Severity Classification Guidelines

From the Architecture document, severity classification should follow:

- **CRITICAL**: Issues that could cause financial loss, data corruption, or security vulnerabilities
  - Example: Uncaught exception that could crash during active order
  - Example: State corruption that misreports positions

- **HIGH**: Issues that cause incorrect behavior or have crash potential
  - Example: Missing error handling in async operations
  - Example: Race conditions in state updates

- **MEDIUM**: Edge case bugs or non-critical error handling gaps
  - Example: Missing bounds checking on non-critical parameters

- **LOW**: Style issues, documentation, minor improvements
  - Example: Unused imports, naming conventions

### Architecture Patterns and Constraints

The audit must pay special attention to:
- **Async/await patterns**: All I/O operations should be async per Architecture
- **Decimal precision**: Financial calculations must use Decimal type
- **Error handling**: All exceptions should be logged with context
- **State consistency**: State mutations should be atomic

### Testing Standards

Per existing rustybt patterns:
- Run with `pytest tests/live/audit/test_core_audit.py -v`
- Static analysis tests should be fast (< 30 seconds)
- Results should be deterministic

### References

- [Source: docs/internal/planning/prd-epic-10.md#Audit Scope - Live Trading Core]
- [Source: docs/internal/planning/architecture-epic-10.md#Pattern 5: Audit Finding Classification]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.1.2]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.1.2]

### Learnings from Previous Story

**From Story 10-1-1 (Status: pending)**

This is the first implementation story in Epic 10 - depends on completion of Story 10.1.1 which creates the audit infrastructure.

**Prerequisites:**
- Story 10.1.1 must be complete to provide YAML schema and fixtures
- Use `AuditFinding` model from `tests/live/audit/models.py`
- Use pytest fixtures from `tests/live/audit/conftest.py`

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

claude-opus-4-5-20251101

### Debug Log References

Ran ruff check on all 7 core modules - 0 issues found.
Ran mypy on all 7 core modules with --show-error-codes.
Filtered mypy output to only core module errors (21 findings).
Classified findings by severity based on impact potential.

### Completion Notes List

- ruff check: 0 issues on core modules (clean)
- mypy: 21 findings captured across 4 modules
  - engine.py: 12 findings (8 HIGH, 3 LOW, 1 MEDIUM)
  - state_manager.py: 2 findings (2 LOW)
  - reconciler.py: 4 findings (1 HIGH, 1 MEDIUM, 2 LOW)
  - strategy_executor.py: 2 findings (2 HIGH)
- order_manager.py, circuit_breakers.py, data_feed.py: 0 mypy issues in target modules
- All HIGH severity findings involve missing attributes or type mismatches that could cause runtime errors
- 10 tests pass validating the audit process

### File List

- tests/live/audit/findings/core_findings.yaml (created)
- tests/live/audit/test_core_audit.py (created)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Story implemented - 21 findings captured, 10 tests passing | Dev Agent |
