# Story 1.3: Implement Core Data Models

Status: done

## Story

As a developer,
I want foundational data models defined,
so that validation code has strongly-typed structures for sessions, findings, and discrepancies.

## Acceptance Criteria

1. **Session model implemented** - `Session` dataclass captures validation session metadata
   - Fields: id (str), created_at (datetime), strategy_name (str), rustybt_version (str), backtrader_version (str), python_version (str), status (Literal), data_fixture (Path), findings (list[Finding])
   - ID format: `{YYYYMMDD}-{HHMMSS}-{strategy_name}`
   - Status values: "IN_PROGRESS", "COMPLETED", "FAILED"

2. **Finding model implemented** - `Finding` dataclass captures layer discrepancies and classifications
   - Fields: id (str), layer (Literal), description (str), classification (Optional[Literal]), rationale (Optional[str]), investigated_by (Optional[str]), investigated_at (Optional[datetime]), resolved (bool), rustybt_value (Any), backtrader_value (Any)
   - Layer values: "data", "signals", "orders", "broker", "portfolio"
   - Classification values: "BUG", "DESIGN", None

3. **Discrepancy model implemented** - `Discrepancy` dataclass captures specific value mismatches during comparison
   - Fields: layer (str), event (str), timestamp (datetime), asset (Optional[str]), field (str), rustybt_value (Any), backtrader_value (Any), tolerance (Any), exceeded_by (Any)

4. **Models are type-safe** - All models use Python 3.12+ type hints and are mypy-strict compatible
   - Literal types for constrained values
   - Optional types for nullable fields
   - Proper imports from typing module

5. **Models are exported** - Models are importable from `rustybt.validation`
   - `from rustybt.validation import Session, Finding, Discrepancy` works
   - Models exported in `rustybt/validation/__init__.py`

## Tasks / Subtasks

- [x] Task 1: Implement Session model (AC: #1)
  - [x] Create `rustybt/validation/models.py` file
  - [x] Import required types: dataclass, field, datetime, Path, Literal, Optional, Any
  - [x] Define Session dataclass with 9 fields and type hints
  - [x] Add field defaults: findings=field(default_factory=list)
  - [x] Add docstring explaining session lifecycle and ID format
  - [x] Add example docstring showing typical Session instantiation

- [x] Task 2: Implement Finding model (AC: #2)
  - [x] Define Finding dataclass with 10 fields and type hints
  - [x] Use Literal["data", "signals", "orders", "broker", "portfolio"] for layer
  - [x] Use Optional[Literal["BUG", "DESIGN"]] for classification
  - [x] Set default values: classification=None, rationale=None, investigated_by=None, investigated_at=None, resolved=False, rustybt_value=None, backtrader_value=None
  - [x] Add docstring explaining BUG vs DESIGN classification

- [x] Task 3: Implement Discrepancy model (AC: #3)
  - [x] Define Discrepancy dataclass with 9 fields and type hints
  - [x] Use str for layer (not Literal - allows flexibility)
  - [x] Use Optional[str] for asset (some events are portfolio-wide)
  - [x] Add docstring explaining tolerance-based comparison

- [x] Task 4: Add type safety and module docstring (AC: #4)
  - [x] Add module-level docstring to models.py explaining purpose
  - [x] Verify all imports from typing module
  - [x] Use Python 3.12+ syntax (| for Union types)
  - [x] Add `from __future__ import annotations` for forward references if needed

- [x] Task 5: Export models from package (AC: #5)
  - [x] Edit `rustybt/validation/__init__.py`
  - [x] Add `from .models import Session, Finding, Discrepancy`
  - [x] Add `__all__ = ["Session", "Finding", "Discrepancy"]`
  - [x] Verify import works: `python -c "from rustybt.validation import Session, Finding, Discrepancy"`

- [x] Task 6: Add unit tests for models
  - [x] Create `tests/validation/test_models.py`
  - [x] Test Session instantiation with all required fields
  - [x] Test Finding with BUG and DESIGN classifications
  - [x] Test Discrepancy creation with tolerance exceeded
  - [x] Test default values are applied correctly
  - [x] Test type hints are enforced (mypy check)

## Dev Notes

### Learnings from Previous Story

**From Story 1.2 (Status: drafted/completed)**

- **Dependencies Available**: PyYAML, Click, Backtrader now installed via optional dependencies
- **CLI Stub**: Minimal CLI with --version flag exists at `rustybt/validation/cli.py`
- **Module Importability**: `rustybt.validation` package is importable
- **pyproject.toml Modified**: Entry point registered, validation extras defined

[Source: docs/sprint-artifacts/1-2-configure-validation-framework-dependencies.md#Dev-Agent-Record]

### Architecture Alignment

**Data Models** (Architecture pg 359-402):
- **Dataclass pattern**: Lightweight, built-in, type-safe (no Pydantic dependency)
- **Session model**: Maps to `session.yaml` storage format (PyYAML serialization)
- **Finding model**: Supports BUG/DESIGN classification workflow (FR41-FR54)
- **Discrepancy model**: Captures comparison results from 5-layer test suite (FR1-FR22)

**Type Safety Requirements**:
- Python 3.12+ syntax (use `str | None` instead of `Optional[str]` where preferred)
- Mypy strict mode compatible (no implicit `Any` types)
- Literal types for constrained enums (status, layer, classification)

### Model Design Rationale

**Session.id Format**: `{YYYYMMDD}-{HHMMSS}-{strategy_name}`
- Example: `20251124-143000-sma_crossover`
- Sortable by timestamp
- Human-readable
- Strategy name included for easy identification

**Finding.classification**:
- **BUG**: rustybt behavior differs from expected (fix required)
- **DESIGN**: Intentional difference (document and accept)
- **None**: Not yet investigated

**Discrepancy.tolerance**:
- Stores the tolerance threshold that was exceeded
- Enables analysis of "how far off" values are
- Supports both absolute and relative tolerances

### Python 3.12+ Type Hints

**Modern syntax examples**:
```python
from typing import Literal, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class Session:
    id: str
    created_at: datetime
    strategy_name: str
    rustybt_version: str
    backtrader_version: str
    python_version: str
    status: Literal["IN_PROGRESS", "COMPLETED", "FAILED"]
    data_fixture: Path
    findings: list[Finding] = field(default_factory=list)  # Python 3.12+ generics
```

**Avoid**:
- `from typing import List, Optional` (use built-in list, | None)
- Implicit Any types (always be explicit)

### Project Structure Notes

**Files modified**:
- `rustybt/validation/models.py` (NEW - core data models)
- `rustybt/validation/__init__.py` (MODIFIED - export models)

**Files created**:
- `tests/validation/test_models.py` (NEW - model unit tests)

### Testing Guidance

**Unit tests** (Task 6):
```python
def test_session_creation():
    session = Session(
        id="20251124-143000-test",
        created_at=datetime.now(),
        strategy_name="test",
        rustybt_version="0.1.0",
        backtrader_version="1.9.78",
        python_version="3.12.0",
        status="IN_PROGRESS",
        data_fixture=Path("fixtures/data.parquet"),
    )
    assert session.status == "IN_PROGRESS"
    assert len(session.findings) == 0  # Default empty list
```

**Property-based testing** (deferred to Story 2.6):
- Use Hypothesis to generate valid/invalid model instances
- Verify serialization/deserialization round-trips

### References

- [Source: docs/architecture.md - Data Models (pg 359-402)]
- [Source: docs/architecture.md - Session Storage (pg 23, ADR-003)]
- [Source: docs/prd.md - FR31-FR40 (Session Management)]
- [Source: docs/prd.md - FR41-FR54 (Investigation & Classification)]
- [Source: docs/epics.md - Story 1.3 specification]
- [Source: docs/sprint-artifacts/1-2-configure-validation-framework-dependencies.md]

## Dev Agent Record

### Context Reference

- [Context File](docs/sprint-artifacts/1-3-implement-core-data-models.context.xml)

### Agent Model Used

<!-- Will be filled during implementation -->

### Debug Log References

<!-- Will be added during implementation -->

### Completion Notes List

<!-- Will be added during implementation -->

### File List

- `rustybt/validation/models.py` - Core data models (Session, Finding, Discrepancy)
- `rustybt/validation/__init__.py` - Module exports
- `tests/validation/test_models.py` - Unit tests (13 tests)

---

## Code Review Notes

**Review Date:** 2025-11-25
**Reviewer:** Senior Developer Code Review (Claude Opus 4.5)
**Outcome:** ✅ **APPROVED**

### Acceptance Criteria Validation

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | Session model with 9 fields | ✅ PASS | `models.py:36-66` |
| AC2 | Finding model with 10 fields | ✅ PASS | `models.py:69-101` |
| AC3 | Discrepancy model with 9 fields | ✅ PASS | `models.py:104-131` |
| AC4 | Type-safe (Python 3.12+) | ✅ PASS | Uses `str | None`, `Literal` types, ruff passes |
| AC5 | Exported from `rustybt.validation` | ✅ PASS | `__init__.py:7-9` |

### Test Results

- **13 tests passing** (100%)
- Coverage: All model fields, default values, classifications, status literals
- Integration tests: Session with Findings, multiple findings across layers

### Code Quality Assessment

- ✅ Clean dataclass implementation
- ✅ Proper Python 3.12+ type hints
- ✅ Comprehensive docstrings with examples
- ✅ Ruff linting passes
- ✅ No security vulnerabilities

### Actions Required for Completion

**None** - Story is complete and ready for DONE status.

### Minor Observations (Non-blocking)

- All subtask checkboxes are unchecked `[ ]` despite work being complete - this is a bookkeeping issue only
- Consider adding `__repr__` methods for better debugging output in future enhancement
