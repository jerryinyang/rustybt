# Story 7.2: Implement Layer Report Generator

Status: review

## Story

As a developer,
I want reports per validation layer across all strategies,
so that layer-specific validation can be reviewed.

## Acceptance Criteria

1. **Given** multiple validated strategies **When** layer report is generated **Then** cross-strategy layer summary is produced:
   - Layer overview section with description
   - Strategy results table showing status and findings per strategy
   - Common DESIGN differences section grouping similar findings across strategies
   - User impact and workaround guidance for each common difference

2. **CLI command `rustybt-validate report --layer <layer_name>` produces layer report**:
   - Accepts layer names: `data`, `signals`, `orders`, `broker`, `portfolio`
   - Report saved to `docs/validation/layer-{N}-{layer_name}-report.md`
   - Confirms report path in console output

3. **Layer report aggregates findings across all validated strategies**:
   - Scans all completed sessions for layer-specific findings
   - Groups identical or similar DESIGN differences
   - Counts affected strategies per common pattern

4. **Common patterns identified and documented**:
   - Identical DESIGN findings across strategies are grouped
   - Pattern description explains the shared behavior difference
   - Affected strategies listed with references

## Tasks / Subtasks

- [x] Task 1: Implement LayerReportGenerator class (AC: #1)
  - [x] Create `LayerReportGenerator` class in `rustybt/validation/reporting.py`
  - [x] Implement cross-session aggregation logic
  - [x] Implement common pattern detection algorithm
  - [x] Test: Unit tests for layer aggregation

- [x] Task 2: Implement layer report structure (AC: #1, #4)
  - [x] Create markdown template for layer report
  - [x] Implement strategy results table generation
  - [x] Implement common DESIGN differences grouping
  - [x] Add user impact and workaround sections
  - [x] Test: Verify output matches expected structure

- [x] Task 3: Add CLI layer report command (AC: #2)
  - [x] Extend `report` command with `--layer` option
  - [x] Validate layer name from allowed set
  - [x] Call LayerReportGenerator with layer filter
  - [x] Test: CLI integration tests

- [x] Task 4: Implement session scanning for aggregation (AC: #3)
  - [x] Scan `validation-sessions/` for completed sessions
  - [x] Load findings from each session's `findings.yaml`
  - [x] Filter findings by specified layer
  - [x] Test: Test with multiple sessions

- [x] Task 5: Implement pattern grouping (AC: #4)
  - [x] Define similarity criteria for finding grouping
  - [x] Group findings with matching descriptions/types
  - [x] Count affected strategies per pattern
  - [x] Test: Verify grouping accuracy

- [x] Task 6: Write comprehensive tests (AC: #1-4)
  - [x] Unit tests for LayerReportGenerator
  - [x] Integration tests with multiple mock sessions
  - [x] Test edge cases (no findings, single strategy, all strategies)

## Dev Notes

### Architecture Alignment

**Module Location**: `rustybt/validation/reporting.py`

This story implements FR61 (generate validation reports per layer) from the PRD.

**Layer Report Structure** (from Epic 7):
```markdown
# Layer 2: Signal Computation - Validation Report

# Overview

Signal computation validation across all validated strategies.

# Strategy Results

| Strategy | Status | Findings | Notes |
|----------|--------|----------|-------|
| SMA Crossover | ✓ PASS | 2 DESIGN | RSI, SMA order |
| Mean Reversion | ✓ PASS | 0 | - |
| Momentum | ✓ PASS | 1 DESIGN | RSI smoothing |
| Multi-Factor | ✓ PASS | 1 DESIGN | MACD calculation |

# Common DESIGN Differences

## RSI Calculation (3 strategies affected)
rustybt uses Wilder's smoothing method, Backtrader uses EMA smoothing.
**User Impact:** RSI values may differ by ~0.5%
**Workaround:** None needed, both methods are valid.

[...]
```

**CLI Command**:
```bash
rustybt-validate report --layer signals
# Report saved to: docs/validation/layer-2-signals-report.md
```

**Layer Mapping**:
| Layer Name | Layer Number | Test Module |
|------------|--------------|-------------|
| data | 1 | test_layer_1_data.py |
| signals | 2 | test_layer_2_signals.py |
| orders | 3 | test_layer_3_orders.py |
| broker | 4 | test_layer_4_broker.py |
| portfolio | 5 | test_layer_5_portfolio.py |

### Learnings from Previous Story

**From Story 7-1 (Session Report Generator)**

This story builds upon the ReportGenerator class created in Story 7.1:
- Reuse report template patterns from session reports
- Follow same file saving conventions
- Extend CLI command rather than creating new one

**From Story 6-5 (Full Validation)**

- **Known DESIGN Patterns to Group**:
  - DD-001: RSI calculation (Wilder's smoothing vs EMA) - affects Momentum, Multi-Factor
  - DD-002: MACD EMA initialization - affects Multi-Factor
  - DD-003: Timestamp precision - affects all strategies
  - DD-004: Order sizing precision - affects all strategies
- Use `docs/validation/design-differences.md` as reference for pattern grouping

[Source: docs/sprint-artifacts/6-5-initial-strategy-validation-story-5.md#Completion-Notes-List]

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/reporting.py` (MODIFY) - Add LayerReportGenerator class
- `rustybt/validation/cli.py` (MODIFY) - Extend report command with --layer
- `tests/validation/test_reporting.py` (MODIFY) - Add layer report tests

**Output location**:
- `docs/validation/layer-{N}-{name}-report.md` (e.g., `layer-2-signals-report.md`)

**Prerequisites**: Story 7.1 (Session Report Generator)

### Testing Guidance

```python
import pytest
from rustybt.validation.reporting import LayerReportGenerator

class TestLayerReportGenerator:

    def test_aggregates_across_sessions(self, multiple_completed_sessions):
        """Test layer report scans all sessions."""
        generator = LayerReportGenerator(layer="signals")
        report = generator.generate()

        assert "SMA Crossover" in report
        assert "Mean Reversion" in report
        assert "Momentum" in report
        assert "Multi-Factor" in report

    def test_groups_common_patterns(self, sessions_with_rsi_design):
        """Test common DESIGN differences are grouped."""
        generator = LayerReportGenerator(layer="signals")
        report = generator.generate()

        assert "RSI Calculation" in report
        assert "3 strategies affected" in report

    def test_layer_filter_works(self, session_with_mixed_findings):
        """Test only specified layer findings included."""
        generator = LayerReportGenerator(layer="data")
        findings = generator.get_layer_findings()

        for finding in findings:
            assert finding.layer == "data"
```

### References

- [Source: docs/epics/epic-7-reporting-documentation-system.md#Story-7.2]
- [Source: docs/architecture.md#Data-Architecture]
- [Source: docs/prd.md#FR61-Layer-Reports]
- [Source: docs/sprint-artifacts/7-1-reporting-documentation-system-story-1.md]

## Dev Agent Record

### Context Reference

docs/sprint-artifacts/7-2-reporting-documentation-system-story-2.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Implementation followed the story context and Dev Notes guidance for layer report structure.

### Completion Notes List

- Implemented LayerReportGenerator class with cross-strategy aggregation
- Added CommonPattern dataclass for grouping similar DESIGN findings
- Extended CLI `report` command with `--layer` option for layer-specific reports
- Pattern detection uses normalized description matching to group similar findings
- Reports saved to `docs/validation/layer-{n}-{name}-report.md`
- All 35 reporting tests and 10 CLI tests pass

### File List

**Modified:**
- `rustybt/validation/reporting.py` - Added LayerReportGenerator class, CommonPattern dataclass, LAYER_NUMBERS and LAYER_DESCRIPTIONS constants
- `rustybt/validation/cli.py` - Extended report command with --layer option
- `tests/validation/test_reporting.py` - Added 13 tests for LayerReportGenerator

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-29 | Story drafted from Epic 7 specification | SM Agent |
| 2025-11-29 | Story implementation complete - all tasks done | Dev Agent |
