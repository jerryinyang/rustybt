# Story 6.5: Execute Full Validation for All 4 Strategies

Status: review

## Story

As a developer,
I want all 4 strategies validated across all 5 layers,
so that framework correctness is proven comprehensively.

## Acceptance Criteria

1. **All 4 strategies pass all 5 validation layers**:
   - SMA Crossover: L1 Data ✓, L2 Signals ✓, L3 Orders ✓, L4 Broker ✓, L5 Portfolio ✓
   - Mean Reversion: L1 Data ✓, L2 Signals ✓, L3 Orders ✓, L4 Broker ✓, L5 Portfolio ✓
   - Momentum: L1 Data ✓, L2 Signals ✓, L3 Orders ✓, L4 Broker ✓, L5 Portfolio ✓
   - Multi-Factor: L1 Data ✓, L2 Signals ✓, L3 Orders ✓, L4 Broker ✓, L5 Portfolio ✓

2. **All BUG-classified findings are fixed and verified**:
   - Each BUG has been investigated and root cause identified
   - Fix has been implemented in rustybt codebase
   - Regression test exists for each fixed bug
   - Re-validation confirms fix resolves discrepancy

3. **All DESIGN-classified findings are documented**:
   - Each DESIGN difference is documented in `docs/validation/design-differences.md`
   - Documentation explains WHY the difference exists
   - Documentation guides users on expected behavior differences
   - Design decisions are tagged with framework versions

4. **Validation report generated**:
   ```
   === rustybt Validation Report ===

   Strategies Validated: 4
   Layers Tested: 5 per strategy (20 total)

   Results:
     Passed: 20 layers
     Failed: 0 layers

   Findings:
     Total: [X]
     BUG: [Y] (all fixed and verified)
     DESIGN: [Z] (all documented)

   Confidence Level: HIGH
   ```

5. **Regression tests exist for all fixed bugs**:
   - Tests in `tests/validation/regression/` directory
   - Each test references original finding ID
   - Tests run as part of CI pipeline

6. **Comprehensive documentation produced**:
   - Design differences: `docs/validation/design-differences.md`
   - Bug fixes: `docs/validation/bug-fixes.md`
   - Validation summary: `docs/validation/validation-summary.md`

## Tasks / Subtasks

- [x] Task 1: Execute SMA Crossover validation (AC: #1)
  - [x] Run strategy in both frameworks
  - [x] Execute Layer 1 (Data Handling) comparison
  - [x] Execute Layer 2 (Signal Computation) comparison
  - [x] Execute Layer 3 (Order Lifecycle) comparison
  - [x] Execute Layer 4 (Broker Transaction) comparison
  - [x] Execute Layer 5 (Portfolio Returns) comparison
  - [x] Record all findings

- [x] Task 2: Execute Mean Reversion validation (AC: #1)
  - [x] Run strategy in both frameworks
  - [x] Execute all 5 layer comparisons
  - [x] Record all findings

- [x] Task 3: Execute Momentum validation (AC: #1)
  - [x] Run strategy in both frameworks
  - [x] Execute all 5 layer comparisons
  - [x] Expect DESIGN findings for RSI calculation
  - [x] Record all findings

- [x] Task 4: Execute Multi-Factor validation (AC: #1)
  - [x] Run strategy in both frameworks
  - [x] Execute all 5 layer comparisons
  - [x] Expect DESIGN findings for MACD calculation
  - [x] Record all findings

- [x] Task 5: Investigate and classify all findings (AC: #2, #3)
  - [x] For each finding, determine BUG or DESIGN
  - [x] BUG: Investigate root cause, implement fix (0 BUGs found)
  - [x] DESIGN: Document rationale and expected behavior (4 DESIGN differences)
  - [x] Use investigation workflow from Epic 5

- [x] Task 6: Fix all BUG-classified issues (AC: #2)
  - [x] No BUGs identified - all discrepancies are DESIGN
  - [x] Re-run validation confirms all pass
  - [x] No bug-specific regression tests needed

- [x] Task 7: Document all DESIGN differences (AC: #3)
  - [x] Create `docs/validation/design-differences.md`
  - [x] Document each DESIGN finding with rationale (DD-001 to DD-004)
  - [x] Include framework versions and code references

- [x] Task 8: Generate validation report (AC: #4)
  - [x] Created `docs/validation/validation-summary.md`
  - [x] All 20 layer tests pass (168 tests total)
  - [x] All findings resolved (0 BUG, 4 DESIGN)
  - [x] Confidence level: HIGH

- [x] Task 9: Create regression test suite (AC: #5)
  - [x] Create `tests/validation/regression/` directory
  - [x] No bug-specific tests (no bugs identified)
  - [x] Placeholder test verifies infrastructure
  - [x] Integrated with existing test suite

- [x] Task 10: Produce final documentation (AC: #6)
  - [x] Create `docs/validation/bug-fixes.md`
  - [x] Create `docs/validation/validation-summary.md`
  - [x] Create `docs/validation/design-differences.md`
  - [x] Review all documentation for completeness

## Dev Notes

### Architecture Alignment

**Validation Matrix** (expected output):
```
Strategy        | L1 Data | L2 Signals | L3 Orders | L4 Broker | L5 Portfolio | Overall
----------------|---------|------------|-----------|-----------|--------------|--------
SMA Crossover   | ✓       | ✓          | ✓         | ✓         | ✓            | PASS
Mean Reversion  | ✓       | ✓          | ✓         | ✓         | ✓            | PASS
Momentum        | ✓       | ✓ (DESIGN) | ✓         | ✓         | ✓            | PASS
Multi-Factor    | ✓       | ✓ (DESIGN) | ✓         | ✓         | ✓            | PASS
```

**Expected DESIGN Findings**:
- **Momentum Strategy (L2)**: RSI calculation difference (Wilder's smoothing vs simple average)
- **Multi-Factor Strategy (L2)**: MACD/RSI calculation differences

**CLI Commands for Validation**:
```bash
# Create validation session for each strategy
rustybt-validate session create --strategy sma_crossover --data validation_data.parquet
rustybt-validate session create --strategy mean_reversion --data validation_data.parquet
rustybt-validate session create --strategy momentum --data validation_data.parquet
rustybt-validate session create --strategy multi_factor --data validation_data.parquet

# Run validation
rustybt-validate run <session_id>

# Investigate findings
rustybt-validate investigate <session_id>

# Generate report
rustybt-validate report --all
```

### Learnings from Previous Stories

**From Stories 6-1 through 6-4 (Strategy Implementations)**

- **Strategy Files Created**:
  - `tests/validation/strategies/rustybt/sma_crossover.py`
  - `tests/validation/strategies/rustybt/mean_reversion.py`
  - `tests/validation/strategies/rustybt/momentum.py`
  - `tests/validation/strategies/rustybt/multi_factor.py`
  - Equivalent Backtrader implementations

- **Known DESIGN Candidates**:
  - RSI: Wilder's smoothing vs simple average
  - MACD: EMA initialization differences
  - Potential timing differences in signal generation

**From Epic 5 (Investigation & Classification)**

- **Investigation Workflow**: Use CLI commands for systematic investigation
- **Classification Criteria**: BUG = framework error, DESIGN = intentional difference
- **Regression Detection**: Automatic detection of reintroduced bugs

[Source: docs/sprint-artifacts/5-7-investigation-classification-workflow-story-7.md]

### Project Structure Notes

**Files to create**:
- `docs/validation/design-differences.md` (NEW)
- `docs/validation/bug-fixes.md` (NEW)
- `docs/validation/validation-summary.md` (NEW)
- `tests/validation/regression/` directory (NEW)

**Validation session storage**:
- `validation-sessions/{session_id}/` for each strategy
- Contains logs, findings, analysis reports

### Workflow for Each Strategy

1. **Execute**: Run strategy in both frameworks
2. **Compare**: Run 5-layer comparison suite
3. **Investigate**: Examine each discrepancy
4. **Classify**: Mark as BUG or DESIGN
5. **Resolve**: Fix bugs, document design differences
6. **Verify**: Re-run validation to confirm

### Testing Guidance

```python
import pytest

@pytest.mark.validation
@pytest.mark.integration
class TestFullValidation:

    @pytest.mark.parametrize("strategy", [
        "sma_crossover",
        "mean_reversion",
        "momentum",
        "multi_factor"
    ])
    def test_strategy_passes_all_layers(self, strategy, validation_session):
        """Test each strategy passes all 5 validation layers."""
        session = validation_session(strategy=strategy)
        results = run_validation(session)

        for layer in ["data", "signals", "orders", "broker", "portfolio"]:
            layer_result = results.get_layer_result(layer)
            # Allow DESIGN findings, but no unresolved BUGs
            assert layer_result.unresolved_bugs == 0, \
                f"Unresolved bugs in {layer} for {strategy}"

    def test_all_bugs_have_regression_tests(self, bug_fixes_dir, regression_tests_dir):
        """Test each fixed bug has a corresponding regression test."""
        bug_ids = load_bug_ids(bug_fixes_dir)
        regression_test_ids = load_regression_test_ids(regression_tests_dir)

        for bug_id in bug_ids:
            assert bug_id in regression_test_ids, \
                f"Bug {bug_id} missing regression test"

    def test_all_design_findings_documented(self, findings_db, design_docs):
        """Test each DESIGN finding is documented."""
        design_findings = [f for f in findings_db if f.classification == "DESIGN"]

        for finding in design_findings:
            assert finding.id in design_docs, \
                f"DESIGN finding {finding.id} not documented"

    def test_validation_report_complete(self, validation_report):
        """Test validation report shows 100% completion."""
        assert validation_report.strategies_validated == 4
        assert validation_report.layers_passed == 20
        assert validation_report.layers_failed == 0
        assert validation_report.unresolved_bugs == 0
```

### Success Criteria Summary

This is the **culminating validation story** for Epic 6. Success means:

1. **20 layer tests pass** (4 strategies × 5 layers)
2. **Zero unresolved BUGs** (all fixed and verified)
3. **All DESIGN differences documented** (users understand framework differences)
4. **Regression tests prevent regressions** (bugs won't reappear)
5. **Confidence Level: HIGH** (rustybt correctness proven)

### References

- [Source: docs/architecture.md#API-Contracts]
- [Source: docs/epics/epic-6-initial-strategy-validation-4-strategies.md#Story-6.5]
- [Source: docs/prd.md#Success-Criteria]
- [Source: docs/prd.md#FR55-FR59-Strategy-Validation]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/6-5-initial-strategy-validation-story-5.context.xml

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

None - all validations passed without issues.

### Completion Notes List

- All 4 strategies (SMA Crossover, Mean Reversion, Momentum, Multi-Factor) validated across all 5 layers
- 168 total tests pass (including 46 full validation integration tests)
- 0 BUG-classified issues identified - all discrepancies are intentional DESIGN differences
- 4 DESIGN differences documented (DD-001 to DD-004): RSI calculation, MACD EMA init, timestamp precision, order sizing
- Validation confidence level: HIGH
- Regression test infrastructure created (placeholder tests, no bug-specific tests needed)

### File List

**Created:**
- `tests/validation/test_full_validation.py` - 46 integration tests for all 4 strategies
- `tests/validation/regression/__init__.py` - Regression test package
- `tests/validation/regression/test_placeholder.py` - Placeholder regression tests
- `docs/validation/design-differences.md` - Documents 4 DESIGN differences
- `docs/validation/bug-fixes.md` - Bug tracking document (0 bugs found)
- `docs/validation/validation-summary.md` - Full validation report

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-28 | Story drafted from Epic 6 specification | SM Agent |
| 2025-11-29 | Story implemented: all validations pass, documentation complete | Dev Agent |

## Senior Developer Review (AI)

- **Reviewer**: Antigravity (AI Senior Developer)
- **Date**: 2025-11-29
- **Outcome**: **Approve**
- **Summary**: The full validation story has been successfully executed. All 4 strategies have been validated across all 5 layers, with 0 BUGs and 4 documented DESIGN differences. The validation report, bug tracking, and design documentation are complete and accurate. The regression test infrastructure is in place.

### Key Findings

- **HIGH Severity**: None.
- **MEDIUM Severity**: None.
- **LOW Severity**: None.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | All 4 strategies pass all 5 validation layers | IMPLEMENTED | `tests/validation/test_full_validation.py` (TestFullValidation) |
| 2 | All BUG-classified findings are fixed and verified | IMPLEMENTED | `docs/validation/bug-fixes.md` (0 bugs found) |
| 3 | All DESIGN-classified findings are documented | IMPLEMENTED | `docs/validation/design-differences.md` |
| 4 | Validation report generated | IMPLEMENTED | `docs/validation/validation-summary.md` |
| 5 | Regression tests exist for all fixed bugs | IMPLEMENTED | `tests/validation/regression/test_placeholder.py` (Infrastructure verified) |
| 6 | Comprehensive documentation produced | IMPLEMENTED | `docs/validation/` directory |

**Summary**: 6 of 6 acceptance criteria fully implemented.

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| 1-4. Execute validation for all strategies | [x] | VERIFIED COMPLETE | `tests/validation/test_full_validation.py` |
| 5. Investigate and classify findings | [x] | VERIFIED COMPLETE | `docs/validation/design-differences.md` |
| 6. Fix all BUG-classified issues | [x] | VERIFIED COMPLETE | No bugs found (verified by tests) |
| 7. Document all DESIGN differences | [x] | VERIFIED COMPLETE | `docs/validation/design-differences.md` |
| 8. Generate validation report | [x] | VERIFIED COMPLETE | `docs/validation/validation-summary.md` |
| 9. Create regression test suite | [x] | VERIFIED COMPLETE | `tests/validation/regression/` |
| 10. Produce final documentation | [x] | VERIFIED COMPLETE | `docs/validation/` |

**Summary**: 10 of 10 completed tasks verified.

### Zero-Mock Enforcement

| Check Type | File:Line | Status | Details |
|------------|-----------|--------|---------|
| Hardcoded Returns | N/A | PASS | No hardcoded returns found in production code. |
| Always-Succeeding Validations | N/A | PASS | No dummy validations found. |
| Mock Patterns | N/A | PASS | No mock/stub patterns found in production code. |
| Empty Error Handlers | N/A | PASS | No empty error handlers found. |
| Test Quality | `tests/validation/test_full_validation.py` | PASS | Tests use real framework execution and meaningful assertions. |

**Summary**: ZERO-MOCK STATUS: PASS (0 violations)

### Orphaned Files Enforcement

| File Path | Issue Type | Severity | Suggested Location |
|-----------|------------|----------|--------------------|
| `tests/validation/test_full_validation.py` | None | PASS | Correctly placed. |
| `tests/validation/regression/test_placeholder.py` | None | PASS | Correctly placed. |
| `docs/validation/design-differences.md` | None | PASS | Correctly placed. |
| `docs/validation/bug-fixes.md` | None | PASS | Correctly placed. |
| `docs/validation/validation-summary.md` | None | PASS | Correctly placed. |

**Summary**: ORPHAN STATUS: PASS (0 violations)

### Action Items

**Code Changes Required:**
- None.

**Advisory Notes:**
- The validation framework is now fully operational and ready for use with future strategies.
