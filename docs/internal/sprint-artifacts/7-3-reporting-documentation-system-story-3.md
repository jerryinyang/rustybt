# Story 7.3: Implement Strategy Report Generator

Status: review

## Story

As a developer,
I want reports per strategy across all layers,
so that strategy-specific validation can be reviewed.

## Acceptance Criteria

1. **Given** a fully validated strategy **When** strategy report is generated **Then** comprehensive strategy summary is produced:
   - Strategy overview section (name, description, parameters)
   - Validation results table showing all 5 layer statuses and finding counts
   - Overall validation status (✓ VALIDATED or ✗ FAILED)
   - Findings summary with all discoveries for this strategy
   - Recommendations section for users

2. **CLI command `rustybt-validate report --strategy <strategy_name>` produces strategy report**:
   - Accepts strategy names: `sma_crossover`, `mean_reversion`, `momentum`, `multi_factor`
   - Report saved to `docs/validation/strategy-{strategy_name}-report.md`
   - Confirms report path in console output

3. **Strategy report focuses on single strategy across all layers**:
   - Aggregates findings from all 5 validation layers
   - Shows layer-by-layer progression of validation
   - Highlights any outstanding issues or DESIGN differences

4. **Recommendations section provides user guidance**:
   - Lists all DESIGN differences relevant to this strategy
   - Provides practical recommendations for each difference
   - References detailed findings documentation

## Tasks / Subtasks

- [x] Task 1: Implement StrategyReportGenerator class (AC: #1)
  - [x] Create `StrategyReportGenerator` class in `rustybt/validation/reporting.py`
  - [x] Implement strategy-scoped session filtering
  - [x] Implement layer status aggregation
  - [x] Test: Unit tests for strategy filtering

- [x] Task 2: Implement strategy report structure (AC: #1, #4)
  - [x] Create markdown template for strategy report
  - [x] Implement strategy overview section with parameters
  - [x] Implement validation results table for all 5 layers
  - [x] Implement findings summary section
  - [x] Implement recommendations section
  - [x] Test: Verify output matches expected structure

- [x] Task 3: Add CLI strategy report command (AC: #2)
  - [x] Extend `report` command with `--strategy` option
  - [x] Validate strategy name from allowed set
  - [x] Call StrategyReportGenerator with strategy filter
  - [x] Test: CLI integration tests

- [x] Task 4: Implement layer aggregation (AC: #3)
  - [x] Find most recent session for specified strategy
  - [x] Extract layer results from session findings
  - [x] Compute overall validation status
  - [x] Test: Test with various session states

- [x] Task 5: Implement recommendations generation (AC: #4)
  - [x] Parse DESIGN findings for actionable recommendations
  - [x] Link to detailed design-differences.md sections
  - [x] Phrase recommendations in user-friendly language
  - [x] Test: Verify recommendations are generated

- [x] Task 6: Write comprehensive tests (AC: #1-4)
  - [x] Unit tests for StrategyReportGenerator
  - [x] Integration tests with mock strategy sessions
  - [x] Test all 4 strategy types

## Dev Notes

### Architecture Alignment

**Module Location**: `rustybt/validation/reporting.py`

This story implements FR62 (generate validation reports per strategy) from the PRD.

**Strategy Report Structure** (from Epic 7):
```markdown
# SMA Crossover Strategy - Validation Report

# Strategy Overview

Simple Moving Average Crossover strategy validated against Backtrader.

**Parameters:**
- Fast Period: 10
- Slow Period: 30

# Validation Results

| Layer | Status | Findings |
|-------|--------|----------|
| Data Handling | ✓ PASS | 0 |
| Signal Computation | ✓ PASS | 2 DESIGN |
| Order Lifecycle | ✓ PASS | 0 |
| Broker Transactions | ✓ PASS | 0 |
| Portfolio Returns | ✓ PASS | 0 |

**Overall Status:** ✓ VALIDATED

# Findings Summary

[... detailed findings ...]

# Recommendations

- RSI values may differ slightly from Backtrader (see DESIGN-001)
- Strategy behaves identically for practical trading purposes
```

**CLI Command**:
```bash
rustybt-validate report --strategy sma_crossover
# Report saved to: docs/validation/strategy-sma-crossover-report.md
```

**Strategy Name Mapping**:
| Strategy Name | Display Name | Parameters |
|---------------|--------------|------------|
| sma_crossover | SMA Crossover | fast=10, slow=30 |
| mean_reversion | Mean Reversion | period=20, z_threshold=2.0 |
| momentum | Momentum | rsi_period=14, trailing_stop=0.05 |
| multi_factor | Multi-Factor | ema_period=20, rsi_period=14 |

### Learnings from Previous Stories

**From Story 7-1 (Session Report Generator)**

- Reuse `ReportGenerator` base patterns
- Follow consistent markdown template structure
- Use same file saving conventions

**From Story 7-2 (Layer Report Generator)**

- Session scanning logic can be reused with strategy filter
- Findings aggregation patterns applicable here

**From Story 6-5 (Full Validation)**

- **Per-Strategy Results Available**:
  - SMA Crossover: 5/5 layers pass, 0 DESIGN
  - Mean Reversion: 5/5 layers pass, 0 DESIGN
  - Momentum: 5/5 layers pass, 1 DESIGN (RSI)
  - Multi-Factor: 5/5 layers pass, 2 DESIGN (RSI, MACD)
- All 4 strategies are VALIDATED status

[Source: docs/sprint-artifacts/6-5-initial-strategy-validation-story-5.md#Dev-Notes]

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/reporting.py` (MODIFY) - Add StrategyReportGenerator class
- `rustybt/validation/cli.py` (MODIFY) - Extend report command with --strategy
- `tests/validation/test_reporting.py` (MODIFY) - Add strategy report tests

**Output location**:
- `docs/validation/strategy-{name}-report.md` (e.g., `strategy-sma-crossover-report.md`)

**Prerequisites**: Story 7.1 (Session Report Generator)

### Testing Guidance

```python
import pytest
from rustybt.validation.reporting import StrategyReportGenerator

class TestStrategyReportGenerator:

    def test_generates_for_specific_strategy(self, sma_crossover_session):
        """Test report only includes specified strategy."""
        generator = StrategyReportGenerator(strategy="sma_crossover")
        report = generator.generate()

        assert "SMA Crossover" in report
        assert "Mean Reversion" not in report

    def test_shows_all_layers(self, completed_strategy_session):
        """Test all 5 layers appear in results table."""
        generator = StrategyReportGenerator(strategy="momentum")
        report = generator.generate()

        assert "Data Handling" in report
        assert "Signal Computation" in report
        assert "Order Lifecycle" in report
        assert "Broker Transactions" in report
        assert "Portfolio Returns" in report

    def test_overall_status_calculated(self, passing_strategy_session):
        """Test overall status is VALIDATED when all layers pass."""
        generator = StrategyReportGenerator(strategy="mean_reversion")
        report = generator.generate()

        assert "✓ VALIDATED" in report

    def test_recommendations_generated(self, strategy_with_design_findings):
        """Test recommendations section includes DESIGN differences."""
        generator = StrategyReportGenerator(strategy="momentum")
        report = generator.generate()

        assert "# Recommendations" in report
        assert "RSI" in report
```

### References

- [Source: docs/epics/epic-7-reporting-documentation-system.md#Story-7.3]
- [Source: docs/architecture.md#Strategy-Comparison-Infrastructure]
- [Source: docs/prd.md#FR62-Strategy-Reports]
- [Source: docs/sprint-artifacts/7-1-reporting-documentation-system-story-1.md]

## Dev Agent Record

### Context Reference

docs/sprint-artifacts/7-3-reporting-documentation-system-story-3.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Implementation followed the story context and Dev Notes guidance for strategy report structure.

### Completion Notes List

- Implemented StrategyReportGenerator class with strategy-scoped session filtering
- Added STRATEGY_DISPLAY_NAMES, STRATEGY_DESCRIPTIONS, and STRATEGY_PARAMETERS mappings
- Extended CLI `report` command with `--strategy` option for strategy-specific reports
- Reports include Strategy Overview, Parameters, Validation Results table, Findings Summary, and Recommendations
- Overall status calculation: ✓ VALIDATED, ⚠ PARTIAL, or ✗ FAILED
- Reports saved to `docs/validation/strategy-{name}-report.md`
- All 51 reporting tests pass

### File List

**Modified:**
- `rustybt/validation/reporting.py` - Added StrategyReportGenerator class, STRATEGY_* constants
- `rustybt/validation/cli.py` - Extended report command with --strategy option
- `tests/validation/test_reporting.py` - Added 16 tests for StrategyReportGenerator

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-29 | Story drafted from Epic 7 specification | SM Agent |
| 2025-11-29 | Story implementation complete - all tasks done | Dev Agent |
