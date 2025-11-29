# Story 7.4: Implement Overall Status Dashboard

Status: done

## Story

As a developer,
I want an overall validation status dashboard,
so that I can see the complete validation picture at a glance.

## Acceptance Criteria

1. **Given** all validation sessions **When** status command is invoked **Then** dashboard is displayed:
   - Header with title and timestamp
   - Strategies validated count and table (strategy, status, findings, last run)
   - Layer coverage count and table (layer, status, notes)
   - Findings summary (total, BUG count, DESIGN count, regression tests)
   - Overall confidence score with visual indicator

2. **CLI command `rustybt-validate status` displays dashboard**:
   - Uses box-drawing characters for ASCII tables
   - Colorized output (green for pass, red for fail) if terminal supports
   - Completes in <1 second for typical use case

3. **JSON output supported for CI integration**:
   - `rustybt-validate status --format json` outputs structured JSON
   - Contains all dashboard data in machine-readable format

4. **Exit codes enable CI integration**:
   - Exit 0 if all strategies validated and no open bugs
   - Exit 1 if any strategy failed or bugs remain open
   - Exit code reflects overall validation health

## Tasks / Subtasks

- [x] Task 1: Implement StatusDashboard class (AC: #1)
  - [x] Create `StatusDashboard` class in `rustybt/validation/reporting.py`
  - [x] Implement session aggregation across all strategies
  - [x] Implement findings summary calculation
  - [x] Implement confidence score algorithm
  - [x] Test: Unit tests for dashboard data aggregation

- [x] Task 2: Implement ASCII table rendering (AC: #1, #2)
  - [x] Create box-drawing character table renderer
  - [x] Implement strategy results table
  - [x] Implement layer coverage table
  - [x] Add color support detection and coloring
  - [x] Test: Verify output formatting

- [x] Task 3: Add CLI status command (AC: #2, #3)
  - [x] Add `status` command to `rustybt/validation/cli.py`
  - [x] Implement `--format` option (text default, json optional)
  - [x] Ensure performance target (<1 second)
  - [x] Test: CLI integration tests

- [x] Task 4: Implement confidence score (AC: #1)
  - [x] Define confidence calculation algorithm
  - [x] Weight factors: strategy coverage, layer coverage, finding resolution
  - [x] Generate visual progress bar indicator
  - [x] Test: Verify confidence calculations

- [x] Task 5: Implement exit codes (AC: #4)
  - [x] Return exit code 0 for healthy validation state
  - [x] Return exit code 1 for failed or incomplete validation
  - [x] Document exit code meanings
  - [x] Test: Integration tests verify exit codes

- [x] Task 6: Write comprehensive tests (AC: #1-4)
  - [x] Unit tests for StatusDashboard
  - [x] Integration tests for CLI command
  - [x] Test exit codes for various states
  - [x] Performance test for <1 second target

## Dev Notes

### Architecture Alignment

**Module Location**: `rustybt/validation/reporting.py` and `rustybt/validation/cli.py`

This story implements FR63 (generate overall validation status report) from the PRD.

**Dashboard Output Structure** (from Epic 7):
```
═══════════════════════════════════════════════════════════════
                   rustybt Validation Status
═══════════════════════════════════════════════════════════════

Strategies Validated: 4/4
┌──────────────────┬───────────┬───────────┬────────────┐
│ Strategy         │ Status    │ Findings  │ Last Run   │
├──────────────────┼───────────┼───────────┼────────────┤
│ SMA Crossover    │ ✓ VALID   │ 5 (0 BUG) │ 2025-11-23 │
│ Mean Reversion   │ ✓ VALID   │ 3 (0 BUG) │ 2025-11-23 │
│ Momentum         │ ✓ VALID   │ 4 (0 BUG) │ 2025-11-24 │
│ Multi-Factor     │ ✓ VALID   │ 6 (0 BUG) │ 2025-11-24 │
└──────────────────┴───────────┴───────────┴────────────┘

Layer Coverage: 5/5 (100%)
┌────────────────────┬────────┬─────────────────────────────┐
│ Layer              │ Status │ Notes                       │
├────────────────────┼────────┼─────────────────────────────┤
│ 1. Data Handling   │ ✓ PASS │ All strategies              │
│ 2. Signals         │ ✓ PASS │ 4 DESIGN differences noted  │
│ 3. Orders          │ ✓ PASS │ All strategies              │
│ 4. Broker          │ ✓ PASS │ All strategies              │
│ 5. Portfolio       │ ✓ PASS │ All strategies              │
└────────────────────┴────────┴─────────────────────────────┘

Findings Summary:
  Total: 18
  BUG: 6 (all fixed ✓)
  DESIGN: 12 (all documented ✓)
  Regression Tests: 6

Overall Confidence: HIGH ███████████░ 92%

═══════════════════════════════════════════════════════════════
```

**CLI Commands**:
```bash
rustybt-validate status
# Displays dashboard

rustybt-validate status --format json
# {"strategies_validated": 4, "layers_covered": 5, "bugs_open": 0, ...}
```

**Confidence Score Algorithm**:
```python
def calculate_confidence() -> float:
    """Calculate overall validation confidence score."""
    # Strategy weight: 40%
    strategy_score = validated_strategies / total_strategies

    # Layer weight: 30%
    layer_score = passed_layers / (total_strategies * 5)

    # Finding resolution weight: 30%
    finding_score = resolved_findings / total_findings if total_findings > 0 else 1.0

    confidence = (strategy_score * 0.4) + (layer_score * 0.3) + (finding_score * 0.3)
    return confidence * 100  # Return as percentage
```

### Learnings from Previous Stories

**From Stories 7-1 to 7-3 (Report Generators)**

- Session scanning patterns from LayerReportGenerator (7-2)
- Aggregation logic reusable for dashboard
- Follow established CLI patterns

**From Story 6-5 (Full Validation)**

- **Current State to Display**:
  - 4/4 strategies validated
  - 20/20 layers pass (5 per strategy)
  - 0 BUG, 4 DESIGN findings
  - Confidence: HIGH (~100%)
- All sessions are COMPLETED status

[Source: docs/sprint-artifacts/6-5-initial-strategy-validation-story-5.md#Completion-Notes-List]

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/reporting.py` (MODIFY) - Add StatusDashboard class
- `rustybt/validation/cli.py` (MODIFY) - Add status command
- `tests/validation/test_reporting.py` (MODIFY) - Add dashboard tests

**Dependencies**:
- Box-drawing characters: Use built-in Unicode characters
- Color support: Check `sys.stdout.isatty()` and environment

**Prerequisites**: Story 7.1-7.3 (Report Generators)

### Testing Guidance

```python
import pytest
from rustybt.validation.reporting import StatusDashboard

class TestStatusDashboard:

    def test_aggregates_all_strategies(self, all_strategy_sessions):
        """Test dashboard shows all 4 strategies."""
        dashboard = StatusDashboard()
        data = dashboard.get_data()

        assert data["strategies_validated"] == 4
        assert len(data["strategies"]) == 4

    def test_calculates_confidence_score(self, healthy_validation_state):
        """Test confidence score calculation."""
        dashboard = StatusDashboard()
        data = dashboard.get_data()

        assert data["confidence"] >= 90  # HIGH confidence
        assert data["confidence"] <= 100

    def test_exit_code_zero_when_healthy(self, healthy_validation_state):
        """Test exit code 0 for healthy state."""
        dashboard = StatusDashboard()
        exit_code = dashboard.get_exit_code()

        assert exit_code == 0

    def test_exit_code_one_when_bugs_open(self, state_with_open_bugs):
        """Test exit code 1 when bugs remain open."""
        dashboard = StatusDashboard()
        exit_code = dashboard.get_exit_code()

        assert exit_code == 1

    def test_json_format_output(self, healthy_validation_state):
        """Test JSON output format."""
        dashboard = StatusDashboard()
        json_output = dashboard.to_json()

        assert "strategies_validated" in json_output
        assert "layers_covered" in json_output
        assert "bugs_open" in json_output
```

### References

- [Source: docs/epics/epic-7-reporting-documentation-system.md#Story-7.4]
- [Source: docs/architecture.md#CLI-Interface]
- [Source: docs/prd.md#FR63-Overall-Status-Report]
- [Source: docs/prd.md#NFR23-Performance]

## Dev Agent Record

### Context Reference

- Story context derived from Epic 7 specification and architecture docs

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed successfully

### Completion Notes List

- Implemented `StatusDashboard` class with full session aggregation (lines 1126-1663 in reporting.py)
- Created `DashboardData` dataclass for structured dashboard data
- Implemented ASCII table rendering with Unicode box-drawing characters
- Added ANSI color support with terminal detection via `supports_color()`
- Implemented confidence score algorithm with 40/30/30 weighting (strategy/layer/findings)
- Added `render_progress_bar()` helper for visual progress indicators
- Added `status` CLI command with `--format` and `--ci` options
- Implemented `is_healthy()` and `get_exit_code()` for CI integration
- All 11 test cases passing in `TestStatusDashboard` and `TestStatusCLI`

### File List

- `rustybt/validation/reporting.py` (MODIFIED) - Added StatusDashboard, DashboardData classes
- `rustybt/validation/cli.py` (MODIFIED) - Added status command (lines 1489-1522)
- `tests/validation/test_reporting.py` (MODIFIED) - Added TestStatusDashboard, TestStatusCLI test classes

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-29 | Story drafted from Epic 7 specification | SM Agent |
| 2025-11-29 | Implementation completed, all tasks done | Dev Agent |
| 2025-11-29 | Code review passed, status updated to done | Code Review |
