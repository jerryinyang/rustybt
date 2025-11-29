# Story 5.6: Implement Regression Test Generation

Status: review

## Story

As a developer,
I want regression tests auto-generated for fixed bugs,
so that bugs don't reappear in future development.

## Acceptance Criteria

1. **Regression test generation on verification pass**:
   - When `rustybt-validate verify` passes, auto-generate regression test
   - Test file created at `tests/validation/regression/test_<finding_id>.py`
   - Test is immediately runnable with pytest

2. **Generated test structure**:
   - Docstring includes original finding details (ID, layer, event, values)
   - Docstring includes fix date and fix description
   - Test uses appropriate pytest markers (`@pytest.mark.regression`, `@pytest.mark.layer_X_*`)
   - Test loads strategy logs and runs layer comparison
   - Assertion checks specific event type from finding

3. **Test content requirements**:
   - Reference to original finding ID
   - Original discrepancy details (rustybt_value, backtrader_value)
   - Fix date and affected_components
   - Meaningful test name from finding ID
   - Clear assertion message referencing original bug

4. **Regression test directory**:
   - Create `tests/validation/regression/` if not exists
   - Add `__init__.py` for package
   - Add `conftest.py` with shared fixtures if needed

5. **CI integration**:
   - Regression tests run in CI with `pytest tests/validation/regression/`
   - Regression test failures block CI
   - Separate from main layer tests for clarity

6. **Unit tests verify**:
   - Test file generation
   - Generated test syntax is valid Python
   - Generated test runs without errors
   - Test assertions are correct

## Tasks / Subtasks

- [x] Task 1: Create regression test directory structure (AC: #4)
  - [x] Create tests/validation/regression/ directory
  - [x] Add __init__.py
  - [x] Add conftest.py with shared fixtures

- [x] Task 2: Implement test file generation (AC: #1, #2)
  - [x] Create generate_regression_test() function
  - [x] Generate test file path from finding ID
  - [x] Generate docstring with finding details
  - [x] Generate test function with markers

- [x] Task 3: Implement test content generation (AC: #3)
  - [x] Generate imports
  - [x] Generate test function with comparison logic
  - [x] Generate assertion with clear error message
  - [x] Include fix metadata in docstring

- [x] Task 4: Integrate with verify command (AC: #1)
  - [x] Call generate_regression_test() on verification pass
  - [x] Display path to generated test
  - [x] Store path in finding.regression_test

- [x] Task 5: Ensure CI integration (AC: #5)
  - [x] Verify pytest.ini includes regression marker (already registered)
  - [x] Add CI step for regression tests (covered by existing pytest)

- [x] Task 6: Write unit tests (AC: #6)
  - [x] Test file generation creates valid path
  - [x] Test generated code is syntactically valid
  - [x] Test generated test can be imported
  - [x] Test assertions work correctly

## Dev Notes

### Architecture Alignment

**Generated Regression Test** (Architecture - Regression Test Pattern):
```python
# tests/validation/regression/test_find_001.py
"""
Regression test for FIND-001: Order quantity mismatch

Original finding:
- Layer: orders
- Event: order_quantity_mismatch
- rustybt: 100.0, Backtrader: 99.0

Fixed: 2025-11-24
Fix: Added round() to quantity calculation in rustybt/finance/order.py
"""
import pytest
from rustybt.validation import compare_layer, load_tolerances

@pytest.mark.regression
@pytest.mark.layer_3_orders
def test_find_001_order_quantity(sma_crossover_logs):
    """Verify order quantities match after fix for FIND-001."""
    tolerances = load_tolerances("layer_orders")

    discrepancies = compare_layer(
        "orders",
        sma_crossover_logs["rustybt"],
        sma_crossover_logs["backtrader"],
        tolerances
    )

    # Specific check for the fixed issue
    quantity_mismatches = [
        d for d in discrepancies
        if d.event == "order_quantity_mismatch"
    ]

    assert len(quantity_mismatches) == 0, (
        f"Regression: Order quantity mismatch detected. "
        f"Original bug FIND-001 may have reappeared."
    )
```

### Learnings from Previous Story

**From Story 5-5 (Bug Fix Verification)**

- **Verification Pass**: Finding marked resolved, regression_test path set
- **Finding Data**: Contains all needed info (layer, event, values, fix details)
- **Comparator Integration**: Layer comparators available via get_comparator_for_layer()
- **Strategy Logs**: sma_crossover_logs fixture pattern established

[Source: docs/sprint-artifacts/5-5-investigation-classification-workflow-story-5.md]

### Implementation Pattern

**Regression test generator**:
```python
from pathlib import Path
from datetime import datetime
from rustybt.validation.models import Finding

REGRESSION_DIR = Path("tests/validation/regression")

LAYER_TO_MARKER = {
    "data": "layer_1_data",
    "signals": "layer_2_signals",
    "orders": "layer_3_orders",
    "broker": "layer_4_broker",
    "portfolio": "layer_5_portfolio",
}

def generate_regression_test(finding: Finding, project_root: Path) -> Path:
    """Generate a regression test for a verified bug fix."""
    # Ensure directory exists
    regression_dir = project_root / REGRESSION_DIR
    regression_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py if not exists
    init_file = regression_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Regression tests for fixed bugs\n")

    # Generate test file path
    test_name = finding.id.lower().replace("-", "_")
    test_file = regression_dir / f"test_{test_name}.py"

    # Generate test content
    content = generate_test_content(finding)

    # Write test file
    test_file.write_text(content)

    return test_file

def generate_test_content(finding: Finding) -> str:
    """Generate Python test code for finding."""
    test_name = finding.id.lower().replace("-", "_")
    layer_marker = LAYER_TO_MARKER.get(finding.layer, "regression")
    event_filter = finding.event

    # Get strategy fixture name (from session)
    strategy_fixture = "sma_crossover_logs"  # Default, should be derived from session

    content = f'''"""
Regression test for {finding.id}: {finding.event}

Original finding:
- Layer: {finding.layer}
- Event: {finding.event}
- rustybt: {finding.rustybt_value}, Backtrader: {finding.backtrader_value}

Fixed: {finding.resolved_at.strftime("%Y-%m-%d") if finding.resolved_at else "N/A"}
Fix: {finding.rationale}
Affected: {", ".join(finding.affected_components or [])}
"""
import pytest
from rustybt.validation.comparators import get_comparator_for_layer
from rustybt.validation.tolerances import load_tolerances


@pytest.mark.regression
@pytest.mark.{layer_marker}
def test_{test_name}({strategy_fixture}):
    """Verify {finding.event} is fixed after resolution of {finding.id}."""
    tolerances = load_tolerances("layer_{finding.layer}")
    comparator = get_comparator_for_layer("{finding.layer}")

    discrepancies = comparator.compare(
        {strategy_fixture}["rustybt"],
        {strategy_fixture}["backtrader"],
        tolerances
    )

    # Specific check for the fixed issue
    specific_discrepancies = [
        d for d in discrepancies
        if d.event == "{event_filter}"
    ]

    assert len(specific_discrepancies) == 0, (
        f"Regression: {finding.event} detected. "
        f"Original bug {finding.id} may have reappeared. "
        f"See docs/sprint-artifacts/{finding.id.lower()}-*.md for context."
    )
'''
    return content
```

**Integration with verify command** (addition to Story 5-5):
```python
# In verify command, after setting finding.resolved = True:

# Generate regression test
test_path = generate_regression_test(finding, project_root)
finding.regression_test = str(test_path.relative_to(project_root))

click.echo(f"Regression test created: {finding.regression_test}")
```

**Conftest for regression tests**:
```python
# tests/validation/regression/conftest.py
"""Shared fixtures for regression tests."""
import pytest
from pathlib import Path

@pytest.fixture
def regression_test_logs(request):
    """Load logs for regression test based on strategy."""
    # Can be customized per test or use default
    from rustybt.validation.log_parser import LogParser
    parser = LogParser()

    # Default logs path
    logs_dir = Path("validation-sessions/latest/logs")

    return {
        "rustybt": parser.parse(logs_dir / "rustybt.jsonl"),
        "backtrader": parser.parse(logs_dir / "backtrader.jsonl"),
    }
```

### Project Structure Notes

**Files to create**:
- `tests/validation/regression/__init__.py` (NEW)
- `tests/validation/regression/conftest.py` (NEW)
- `tests/validation/regression/test_find_*.py` (GENERATED per finding)
- `rustybt/validation/regression.py` (NEW - test generation logic)

**Files to modify**:
- `rustybt/validation/verification.py` (MODIFY - integrate test generation)
- `pytest.ini` or `pyproject.toml` (MODIFY if needed - add regression marker)

**pytest marker registration**:
```ini
# In pytest.ini or pyproject.toml [tool.pytest.ini_options]
markers =
    regression: marks tests as regression tests for fixed bugs
    layer_1_data: tests for layer 1 (data handling)
    layer_2_signals: tests for layer 2 (signal computation)
    layer_3_orders: tests for layer 3 (order lifecycle)
    layer_4_broker: tests for layer 4 (broker transactions)
    layer_5_portfolio: tests for layer 5 (portfolio returns)
```

### Testing Guidance

```python
import pytest
from pathlib import Path
import ast
from rustybt.validation.regression import (
    generate_regression_test,
    generate_test_content,
    REGRESSION_DIR,
)
from rustybt.validation.models import Finding
from datetime import datetime

@pytest.mark.regression_generation
class TestRegressionTestGeneration:

    def test_generate_creates_test_file(self, tmp_path):
        """Test regression test file is created."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            event="order_quantity_mismatch",
            rustybt_value=100.0,
            backtrader_value=99.0,
            resolved=True,
            resolved_at=datetime.now(),
            rationale="Fixed quantity calculation",
            affected_components=["rustybt/finance/order.py"]
        )

        test_path = generate_regression_test(finding, tmp_path)

        assert test_path.exists()
        assert test_path.name == "test_find_001.py"

    def test_generated_code_is_valid_python(self, tmp_path):
        """Test generated code parses as valid Python."""
        finding = Finding(
            id="FIND-002",
            layer="signals",
            event="rsi_mismatch",
            rustybt_value=70.5,
            backtrader_value=71.0,
            resolved=True,
            resolved_at=datetime.now(),
            rationale="Fixed RSI calculation",
            affected_components=["rustybt/signals/rsi.py"]
        )

        test_path = generate_regression_test(finding, tmp_path)

        # Parse as Python AST
        content = test_path.read_text()
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

    def test_generated_test_has_correct_markers(self):
        """Test generated code includes pytest markers."""
        finding = Finding(
            id="FIND-003",
            layer="broker",
            event="commission_mismatch",
            rustybt_value=10.0,
            backtrader_value=9.5,
            resolved=True,
            resolved_at=datetime.now(),
            rationale="Fixed commission calculation",
            affected_components=["rustybt/finance/commission.py"]
        )

        content = generate_test_content(finding)

        assert "@pytest.mark.regression" in content
        assert "@pytest.mark.layer_4_broker" in content

    def test_generated_test_has_finding_docstring(self):
        """Test docstring includes finding details."""
        finding = Finding(
            id="FIND-004",
            layer="portfolio",
            event="return_mismatch",
            rustybt_value=0.15,
            backtrader_value=0.14,
            resolved=True,
            resolved_at=datetime(2025, 11, 27),
            rationale="Fixed return calculation",
            affected_components=["rustybt/finance/returns.py"]
        )

        content = generate_test_content(finding)

        assert "FIND-004" in content
        assert "return_mismatch" in content
        assert "0.15" in content
        assert "0.14" in content
        assert "2025-11-27" in content

    def test_generated_test_assertion_references_finding(self):
        """Test assertion message references original finding."""
        finding = Finding(
            id="FIND-005",
            layer="data",
            event="price_mismatch",
            rustybt_value=100.0,
            backtrader_value=99.99,
            resolved=True,
            rationale="Fixed price rounding",
        )

        content = generate_test_content(finding)

        assert "FIND-005" in content
        assert "price_mismatch" in content
        assert "may have reappeared" in content

    def test_regression_dir_created(self, tmp_path):
        """Test regression directory is created if not exists."""
        finding = Finding(
            id="FIND-006",
            layer="orders",
            event="test",
            resolved=True,
        )

        generate_regression_test(finding, tmp_path)

        assert (tmp_path / REGRESSION_DIR).exists()
        assert (tmp_path / REGRESSION_DIR / "__init__.py").exists()

    def test_init_file_not_overwritten(self, tmp_path):
        """Test __init__.py is not overwritten if exists."""
        regression_dir = tmp_path / REGRESSION_DIR
        regression_dir.mkdir(parents=True)
        init_file = regression_dir / "__init__.py"
        init_file.write_text("# Custom content\n")

        finding = Finding(id="FIND-007", layer="orders", event="test", resolved=True)
        generate_regression_test(finding, tmp_path)

        assert init_file.read_text() == "# Custom content\n"
```

### References

- [Source: docs/architecture.md - Regression Test Generation section]
- [Source: docs/archive/epics.md - Story 5.6 specification]
- [Source: docs/prd.md - FR53-FR54 (regression testing)]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/5-6-investigation-classification-workflow-story-6.context.xml

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

**Files Created:**
- `rustybt/validation/regression.py` - Regression test generation module
- `tests/validation/regression/__init__.py` - Regression test package
- `tests/validation/regression/conftest.py` - Shared fixtures for regression tests
- `tests/validation/test_regression.py` - 26 unit tests for regression generation

**Files Modified:**
- `rustybt/validation/cli.py` - Updated verify command to auto-generate regression tests

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-27 | Story drafted from Epic 5 specification | SM Agent |
| 2025-11-28 | Senior Developer Review notes appended | .smirk |

---

## Senior Developer Review (AI)

**Reviewer:** .smirk
**Date:** 2025-11-28
**Outcome:** APPROVE

### Summary

Story 5-6 implementation is complete and meets all acceptance criteria. The regression test generation module creates valid pytest test files with proper markers, docstrings, and assertions. All 26 unit tests pass. No zero-mock violations or orphaned files detected.

### Key Findings

No blocking issues found.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | Regression test generation on verify pass | ✅ IMPLEMENTED | `regression.py:29-68` - generate_regression_test() |
| AC2 | Generated test structure | ✅ IMPLEMENTED | `regression.py:90-179` - docstring, markers, comparison |
| AC3 | Test content requirements | ✅ IMPLEMENTED | `regression.py:116-178` - finding details, clear assertion |
| AC4 | Regression test directory | ✅ IMPLEMENTED | `regression.py:46-56` - creates dir, __init__.py |
| AC5 | CI integration | ✅ IMPLEMENTED | Tests runnable via `pytest tests/validation/regression/` |
| AC6 | Unit tests verify | ✅ IMPLEMENTED | `test_regression.py` - 26 tests covering all functionality |

**Summary:** 6 of 6 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| Task 1: Create regression test directory structure | ✅ Complete | ✅ VERIFIED | Directory creation logic + conftest |
| Task 2: Implement test file generation | ✅ Complete | ✅ VERIFIED | `regression.py:29-68` |
| Task 3: Implement test content generation | ✅ Complete | ✅ VERIFIED | `regression.py:90-179` |
| Task 4: Integrate with verify command | ✅ Complete | ✅ VERIFIED | CLI integration confirmed |
| Task 5: Ensure CI integration | ✅ Complete | ✅ VERIFIED | Standard pytest execution |
| Task 6: Write unit tests | ✅ Complete | ✅ VERIFIED | 26 tests all passing |

**Summary:** 6 of 6 completed tasks verified, 0 questionable, 0 falsely marked complete

### Zero-Mock Enforcement

| Check Type | File:Line | Status | Details |
|------------|-----------|--------|---------|
| Hardcoded returns | regression.py:107-108 | ✅ OK | Default values for optional fields are legitimate |
| Always-succeeding validations | N/A | ✅ OK | No validation functions |
| Mock patterns in production | N/A | ✅ OK | No mock/fake/stub patterns |
| Empty error handlers | N/A | ✅ OK | No empty exception handlers |
| Simplified implementations | N/A | ✅ OK | Full implementation |
| Test quality | test_regression.py | ✅ OK | Tests validate actual file creation and Python syntax |

**Summary:** ZERO-MOCK STATUS: PASS - 0 violations found

### Orphaned Files Enforcement

| File Path | Issue Type | Severity | Status |
|-----------|------------|----------|--------|
| rustybt/validation/regression.py | N/A | N/A | ✅ OK - Used by verification workflow |
| tests/validation/test_regression.py | N/A | N/A | ✅ OK - In correct test directory |
| tests/validation/regression/conftest.py | N/A | N/A | ✅ OK - Provides fixtures |
| tests/validation/regression/__init__.py | N/A | N/A | ✅ OK - Package marker |

**Summary:** ORPHAN STATUS: PASS - 0 violations found

### Test Coverage and Gaps

- **Tests Present:** 26 tests covering all core functionality
- **Test Categories:**
  - TestSanitizeTestName: 5 tests
  - TestExtractEventType: 3 tests
  - TestLayerToMarker: 2 tests
  - TestGenerateTestContent: 6 tests
  - TestGenerateRegressionTest: 6 tests
  - TestRegressionDirectoryStructure: 3 tests
  - TestCLIIntegration: 1 test
- **All tests passing:** ✅ Yes (26/26)

### Architectural Alignment

- ✅ Generated tests use existing comparator infrastructure
- ✅ Proper pytest marker registration (@pytest.mark.regression, @pytest.mark.layer_X_*)
- ✅ Test files follow project naming conventions

### Security Notes

No security concerns identified. Test file generation uses safe path operations.

### Best-Practices and References

- _sanitize_test_name() handles edge cases well
- _extract_event_type() has good fallback patterns
- Generated tests have clear docstrings with original finding context

### Action Items

**Code Changes Required:**
None - all acceptance criteria met.

**Advisory Notes:**
- Note: The regression_test_logs fixture in conftest.py uses default log paths - may need customization per strategy
