# Story 5.5: Implement Bug Fix Verification

Status: review

## Story

As a developer,
I want to verify that bug fixes resolve discrepancies,
so that fixes are validated before marking findings as resolved.

## Acceptance Criteria

1. **Verify CLI command implemented**:
   - `rustybt-validate verify <finding_id>` invokes verification
   - Displays original discrepancy details
   - Re-runs strategy execution for both frameworks
   - Re-runs layer comparison for affected layer
   - Reports verification result (pass/fail)

2. **Strategy re-execution**:
   - Locate original session with same parameters
   - Re-execute rustybt strategy with identical config
   - Re-execute Backtrader strategy with identical config
   - Capture new logs to temporary location

3. **Layer re-comparison**:
   - Run comparison only for the finding's layer
   - Use same tolerance configuration
   - Check if original discrepancy still present

4. **Verification pass handling**:
   - If discrepancy no longer present → verification passes
   - Update finding: `resolved = True`, `resolved_at = datetime.now()`
   - Store path to regression test (created in Story 5.6)
   - Display success message with next steps

5. **Verification fail handling**:
   - If discrepancy still present → verification fails
   - Display current values vs expected
   - Keep finding status unchanged
   - Suggest debugging steps

6. **Unit tests verify**:
   - CLI command parsing
   - Strategy re-execution logic
   - Comparison result handling
   - Finding update on pass/fail

## Tasks / Subtasks

- [x] Task 1: Implement verify CLI command (AC: #1)
  - [x] Add `verify` command with finding_id argument
  - [x] Load finding and associated session
  - [x] Display original discrepancy details

- [x] Task 2: Implement strategy re-execution (AC: #2)
  - [x] Load session configuration (strategy, data fixture, parameters)
  - [x] Execute rustybt strategy to temp log file
  - [x] Execute Backtrader strategy to temp log file
  - [x] Handle execution errors gracefully

- [x] Task 3: Implement layer re-comparison (AC: #3)
  - [x] Load appropriate layer comparator
  - [x] Load tolerance configuration for layer
  - [x] Run comparison on new logs
  - [x] Check if original discrepancy event found

- [x] Task 4: Implement pass handling (AC: #4)
  - [x] Update finding.resolved = True
  - [x] Update finding.resolved_at
  - [x] Set finding.regression_test path
  - [x] Save finding to YAML
  - [x] Display success message

- [x] Task 5: Implement fail handling (AC: #5)
  - [x] Display current discrepancy values
  - [x] Show expected values
  - [x] Keep finding status as classified but unresolved
  - [x] Suggest next debugging steps

- [x] Task 6: Write unit tests (AC: #6)
  - [x] Test CLI command
  - [x] Test re-execution with mock strategies
  - [x] Test pass/fail handling
  - [x] Test finding persistence

## Dev Notes

### Architecture Alignment

**Verify Command** (Architecture - Bug Fix Verification):
```bash
rustybt-validate verify FIND-001
#
# === Verifying Fix for FIND-001 ===
#
# Original discrepancy:
#   Layer: orders
#   Event: order_quantity_mismatch
#   rustybt: 100.0, Backtrader: 99.0
#
# Re-running strategy execution...
# ✓ rustybt executed successfully
# ✓ Backtrader executed successfully
#
# Re-running layer comparison...
# ✓ Order quantities now match
#
# === Fix Verified ===
# FIND-001 marked as resolved
# Regression test created: tests/validation/regression/test_find_001.py
```

**Verification Failure Output**:
```
# ✗ Verification failed
# Discrepancy still present:
#   rustybt: 100.0, Backtrader: 99.0
#
# Fix not complete. Finding remains open.
```

### Learnings from Previous Stories

**From Stories 5-1 through 5-4 (Investigation and Classification)**

- **Finding Model**: Has layer, event, session reference needed for re-execution
- **Session Storage**: Session directory contains strategy config, data paths
- **Comparators**: Layer comparators implemented in Epic 4 (Stories 4-3 through 4-7)
- **Tolerance Config**: YAML files per layer in tests/validation/config/

[Source: docs/sprint-artifacts/5-3-investigation-classification-workflow-story-3.md]
[Source: docs/sprint-artifacts/4-7-implement-layer5-portfolio-returns-comparator.md]

### Implementation Pattern

**Verify command**:
```python
@cli.command()
@click.argument('finding_id')
def verify(finding_id: str):
    """Verify a bug fix resolves the discrepancy."""
    click.echo(f"\n=== Verifying Fix for {finding_id} ===\n")

    # Load finding and session
    finding = load_finding(finding_id)
    if not finding:
        click.echo(f"Error: Finding {finding_id} not found.")
        return

    if finding.classification != "BUG":
        click.echo(f"Error: Finding {finding_id} is not classified as BUG.")
        return

    session = load_session_for_finding(finding)

    # Show original discrepancy
    click.echo("Original discrepancy:")
    click.echo(f"  Layer: {finding.layer}")
    click.echo(f"  Event: {finding.event}")
    click.echo(f"  rustybt: {finding.rustybt_value}, Backtrader: {finding.backtrader_value}")
    click.echo()

    # Re-execute strategies
    click.echo("Re-running strategy execution...")
    try:
        rb_logs, bt_logs = re_execute_strategies(session)
        click.echo("✓ rustybt executed successfully")
        click.echo("✓ Backtrader executed successfully")
    except ExecutionError as e:
        click.echo(f"✗ Execution failed: {e}")
        return

    # Re-run comparison
    click.echo("\nRe-running layer comparison...")
    discrepancies = compare_layer_for_finding(finding, rb_logs, bt_logs)

    # Check if original discrepancy still present
    original_still_present = any(
        d.event == finding.event and d.layer == finding.layer
        for d in discrepancies
    )

    if not original_still_present:
        # Verification passed
        click.echo(f"✓ {finding.event} no longer detected")
        click.echo("\n=== Fix Verified ===")

        finding.resolved = True
        finding.resolved_at = datetime.now()
        finding.regression_test = f"tests/validation/regression/test_{finding_id.lower().replace('-', '_')}.py"

        save_finding(finding, session)

        click.echo(f"{finding_id} marked as resolved")
        click.echo(f"Regression test will be created: {finding.regression_test}")
    else:
        # Verification failed
        current = next(d for d in discrepancies if d.event == finding.event)
        click.echo("✗ Verification failed")
        click.echo("Discrepancy still present:")
        click.echo(f"  rustybt: {current.rustybt_value}, Backtrader: {current.backtrader_value}")
        click.echo()
        click.echo("Fix not complete. Finding remains open.")
        click.echo("\nDebugging suggestions:")
        click.echo("  1. Check if the fix was applied to the correct file")
        click.echo("  2. Review the comparison tolerance settings")
        click.echo("  3. Use 'rustybt-validate investigate' to view context")
```

**Strategy re-execution**:
```python
import tempfile
from pathlib import Path
import subprocess

def re_execute_strategies(session: Session) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Re-execute strategies and return log DataFrames."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rb_log_path = tmp_path / "rustybt.jsonl"
        bt_log_path = tmp_path / "backtrader.jsonl"

        # Run rustybt strategy
        run_rustybt_strategy(
            strategy_path=session.rustybt_strategy_path,
            data_path=session.data_fixture,
            output_log=rb_log_path,
            config=session.strategy_config
        )

        # Run Backtrader strategy
        run_backtrader_strategy(
            strategy_path=session.backtrader_strategy_path,
            data_path=session.data_fixture,
            output_log=bt_log_path,
            config=session.strategy_config
        )

        # Parse logs
        from rustybt.validation.log_parser import LogParser
        parser = LogParser()

        rb_logs = parser.parse(rb_log_path)
        bt_logs = parser.parse(bt_log_path)

        return rb_logs, bt_logs

def run_rustybt_strategy(strategy_path: Path, data_path: Path,
                         output_log: Path, config: dict) -> None:
    """Execute rustybt strategy in subprocess."""
    result = subprocess.run([
        "python", "-m", "rustybt.validation.runner",
        "--strategy", str(strategy_path),
        "--data", str(data_path),
        "--output", str(output_log),
        "--config", json.dumps(config)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        raise ExecutionError(f"rustybt execution failed: {result.stderr}")

def run_backtrader_strategy(strategy_path: Path, data_path: Path,
                            output_log: Path, config: dict) -> None:
    """Execute Backtrader strategy in subprocess."""
    result = subprocess.run([
        "python", "-m", "rustybt.validation.runner_backtrader",
        "--strategy", str(strategy_path),
        "--data", str(data_path),
        "--output", str(output_log),
        "--config", json.dumps(config)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        raise ExecutionError(f"Backtrader execution failed: {result.stderr}")
```

**Layer comparison for finding**:
```python
def compare_layer_for_finding(
    finding: Finding,
    rb_logs: pl.DataFrame,
    bt_logs: pl.DataFrame
) -> list[Discrepancy]:
    """Run comparison for the finding's layer only."""
    from rustybt.validation.comparators import get_comparator_for_layer
    from rustybt.validation.tolerances import load_tolerances

    comparator = get_comparator_for_layer(finding.layer)
    tolerances = load_tolerances(f"layer_{finding.layer}")

    return comparator.compare(rb_logs, bt_logs, tolerances)
```

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/cli.py` (MODIFY - add verify command)
- `rustybt/validation/verification.py` (NEW - verification logic)
- `rustybt/validation/runner.py` (NEW if not exists - rustybt execution)
- `rustybt/validation/runner_backtrader.py` (NEW if not exists - Backtrader execution)
- `tests/validation/test_verification.py` (NEW - verification tests)

**Finding YAML with resolved fields**:
```yaml
findings:
  - id: FIND-001
    layer: orders
    event: order_quantity_mismatch
    classification: BUG
    rationale: "Order quantity calculation doesn't account for fractional shares"
    severity: Major
    resolved: true
    resolved_at: "2025-11-27T12:00:00"
    regression_test: "tests/validation/regression/test_find_001.py"
```

### Testing Guidance

```python
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from rustybt.validation.cli import cli
from rustybt.validation.verification import (
    re_execute_strategies,
    compare_layer_for_finding,
)
from rustybt.validation.models import Finding, Session

@pytest.mark.verification
class TestVerifyCommand:

    def test_verify_command_exists(self):
        """Test verify command is registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ['verify', '--help'])
        assert result.exit_code == 0
        assert 'finding_id' in result.output

    def test_verify_requires_bug_classification(self, mock_finding):
        """Test verify rejects non-BUG findings."""
        mock_finding.classification = "DESIGN"

        with patch('rustybt.validation.verification.load_finding', return_value=mock_finding):
            runner = CliRunner()
            result = runner.invoke(cli, ['verify', 'FIND-001'])

        assert "not classified as BUG" in result.output

    def test_verify_pass_updates_finding(self, mock_finding, mock_session):
        """Test successful verification updates finding."""
        mock_finding.classification = "BUG"
        mock_finding.event = "order_quantity_mismatch"
        mock_finding.layer = "orders"

        with patch('rustybt.validation.verification.load_finding', return_value=mock_finding):
            with patch('rustybt.validation.verification.load_session_for_finding', return_value=mock_session):
                with patch('rustybt.validation.verification.re_execute_strategies') as mock_exec:
                    mock_exec.return_value = (MagicMock(), MagicMock())

                    with patch('rustybt.validation.verification.compare_layer_for_finding') as mock_compare:
                        # No discrepancies = pass
                        mock_compare.return_value = []

                        with patch('rustybt.validation.verification.save_finding'):
                            runner = CliRunner()
                            result = runner.invoke(cli, ['verify', 'FIND-001'])

        assert "Fix Verified" in result.output
        assert mock_finding.resolved == True
        assert mock_finding.resolved_at is not None

    def test_verify_fail_keeps_finding_open(self, mock_finding, mock_session):
        """Test failed verification keeps finding unresolved."""
        mock_finding.classification = "BUG"
        mock_finding.event = "order_quantity_mismatch"
        mock_finding.layer = "orders"
        mock_finding.resolved = False

        mock_discrepancy = MagicMock()
        mock_discrepancy.event = "order_quantity_mismatch"
        mock_discrepancy.layer = "orders"
        mock_discrepancy.rustybt_value = 100.0
        mock_discrepancy.backtrader_value = 99.0

        with patch('rustybt.validation.verification.load_finding', return_value=mock_finding):
            with patch('rustybt.validation.verification.load_session_for_finding', return_value=mock_session):
                with patch('rustybt.validation.verification.re_execute_strategies') as mock_exec:
                    mock_exec.return_value = (MagicMock(), MagicMock())

                    with patch('rustybt.validation.verification.compare_layer_for_finding') as mock_compare:
                        # Discrepancy still present = fail
                        mock_compare.return_value = [mock_discrepancy]

                        runner = CliRunner()
                        result = runner.invoke(cli, ['verify', 'FIND-001'])

        assert "Verification failed" in result.output
        assert mock_finding.resolved == False

    def test_strategy_execution_error_handling(self, mock_finding, mock_session):
        """Test execution error is handled gracefully."""
        mock_finding.classification = "BUG"

        with patch('rustybt.validation.verification.load_finding', return_value=mock_finding):
            with patch('rustybt.validation.verification.load_session_for_finding', return_value=mock_session):
                with patch('rustybt.validation.verification.re_execute_strategies') as mock_exec:
                    from rustybt.validation.verification import ExecutionError
                    mock_exec.side_effect = ExecutionError("Strategy crashed")

                    runner = CliRunner()
                    result = runner.invoke(cli, ['verify', 'FIND-001'])

        assert "Execution failed" in result.output
```

### References

- [Source: docs/architecture.md - Bug Fix Verification section]
- [Source: docs/archive/epics.md - Story 5.5 specification]
- [Source: docs/prd.md - FR53-FR54 (fix verification)]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/5-5-investigation-classification-workflow-story-5.context.xml

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

**Files Created:**
- `rustybt/validation/verification.py` - New verification module with re-execution and comparison logic
- `tests/validation/test_verification.py` - 25 unit tests covering all acceptance criteria

**Files Modified:**
- `rustybt/validation/cli.py` - Added `verify` command
- `rustybt/validation/models.py` - Added `resolved_at` and `regression_test` fields to Finding

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

Story 5-5 implementation is complete and meets all acceptance criteria. The verification module provides comprehensive bug fix verification by re-executing strategies, running layer comparison, and updating finding status. All 25 unit tests pass. No zero-mock violations or orphaned files detected.

### Key Findings

No blocking issues found.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC1 | Verify CLI command implemented | ✅ IMPLEMENTED | `cli.py` - verify command with finding_id argument |
| AC2 | Strategy re-execution | ✅ IMPLEMENTED | `verification.py:116-171` - re_execute_strategies() |
| AC3 | Layer re-comparison | ✅ IMPLEMENTED | `verification.py:174-202` - compare_layer_for_finding() |
| AC4 | Verification pass handling | ✅ IMPLEMENTED | `verification.py:260-264` - VerificationResult with passed=True |
| AC5 | Verification fail handling | ✅ IMPLEMENTED | `verification.py:248-264` - discrepancy detection |
| AC6 | Unit tests verify | ✅ IMPLEMENTED | `test_verification.py` - 25 tests covering all functionality |

**Summary:** 6 of 6 acceptance criteria fully implemented

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| Task 1: Implement verify CLI command | ✅ Complete | ✅ VERIFIED | CLI verify command exists |
| Task 2: Implement strategy re-execution | ✅ Complete | ✅ VERIFIED | `verification.py:116-171` |
| Task 3: Implement layer re-comparison | ✅ Complete | ✅ VERIFIED | `verification.py:174-202` |
| Task 4: Implement pass handling | ✅ Complete | ✅ VERIFIED | VerificationResult with resolved update |
| Task 5: Implement fail handling | ✅ Complete | ✅ VERIFIED | discrepancy persistence check |
| Task 6: Write unit tests | ✅ Complete | ✅ VERIFIED | 25 tests all passing |

**Summary:** 6 of 6 completed tasks verified, 0 questionable, 0 falsely marked complete

### Zero-Mock Enforcement

| Check Type | File:Line | Status | Details |
|------------|-----------|--------|---------|
| Hardcoded returns | verification.py:113 | ✅ OK | `return None` for unknown layer is legitimate default |
| Always-succeeding validations | N/A | ✅ OK | verify_fix properly checks classification |
| Mock patterns in production | N/A | ✅ OK | No mock/fake/stub patterns |
| Empty error handlers | N/A | ✅ OK | ExecutionError raised properly |
| Simplified implementations | N/A | ✅ OK | Full implementation |
| Test quality | test_verification.py | ✅ OK | Tests use mock.patch for subprocess, validate logic |

**Summary:** ZERO-MOCK STATUS: PASS - 0 violations found

### Orphaned Files Enforcement

| File Path | Issue Type | Severity | Status |
|-----------|------------|----------|--------|
| rustybt/validation/verification.py | N/A | N/A | ✅ OK - Used by CLI verify command |
| tests/validation/test_verification.py | N/A | N/A | ✅ OK - In correct test directory |

**Summary:** ORPHAN STATUS: PASS - 0 violations found

### Test Coverage and Gaps

- **Tests Present:** 25 tests covering all core functionality
- **Test Categories:**
  - TestGetComparatorForLayer: 6 tests
  - TestLoadTolerancesForLayer: 2 tests
  - TestVerificationResult: 3 tests
  - TestCompareLayerForFinding: 2 tests
  - TestVerifyFix: 5 tests
  - TestLoadFinding: 2 tests
  - TestSaveFinding: 1 test
  - TestCLIVerifyCommand: 4 tests
- **All tests passing:** ✅ Yes (25/25)

### Architectural Alignment

- ✅ Uses existing layer comparators from Epic 4
- ✅ Integrates with SessionManager for finding persistence
- ✅ Uses runner module for strategy execution

### Security Notes

- Uses subprocess with explicit arguments (no shell injection risk)
- Temporary directory cleanup via context manager
- No security concerns identified

### Best-Practices and References

- VerificationResult class provides clean result encapsulation
- Proper error handling with ExecutionError
- Reuses existing comparators and tolerance config

### Action Items

**Code Changes Required:**
None - all acceptance criteria met.

**Advisory Notes:**
- Note: The regression_test path is set but not created (Story 5-6 handles test generation)
