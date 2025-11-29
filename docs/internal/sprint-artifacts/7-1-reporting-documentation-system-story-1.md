# Story 7.1: Implement Session Report Generator

Status: review

## Story

As a developer,
I want detailed reports per session,
so that validation results are clearly documented.

## Acceptance Criteria

1. **Given** a completed or in-progress session **When** report generation is invoked **Then** a markdown report is generated with the following structure:
   - Session header (ID, strategy, status, date)
   - Summary table (Total findings, BUG count, DESIGN count, layers passed)
   - Layer results sections with per-layer status and findings tables
   - Findings detail section with full information per finding

2. **CLI command `rustybt-validate report <session_id>` produces markdown report**:
   - Report saved to `validation-sessions/{session_id}/report.md`
   - Confirms report path in console output

3. **CLI command `rustybt-validate report <session_id> --format json` produces JSON output**:
   - JSON format suitable for programmatic use and CI integration
   - Contains same data as markdown report in structured format

4. **Reports are automatically saved to session directory**:
   - `validation-sessions/{session_id}/report.md` (markdown)
   - `validation-sessions/{session_id}/report.json` (if JSON format requested)

5. **Report auto-generation on session completion**:
   - When session status changes to COMPLETED, report is automatically generated
   - Report timestamp reflects generation time

## Tasks / Subtasks

- [x] Task 1: Implement ReportGenerator class (AC: #1)
  - [x] Create `rustybt/validation/reporting.py` module
  - [x] Define `ReportGenerator` class with session dependency injection
  - [x] Implement `generate_markdown()` method for markdown output
  - [x] Implement `generate_json()` method for JSON output
  - [x] Test: Unit tests for report generation with mock session data

- [x] Task 2: Implement report template structure (AC: #1)
  - [x] Create markdown template with session header section
  - [x] Implement summary table generation with findings counts
  - [x] Implement per-layer results section generation
  - [x] Implement findings detail section with classification info
  - [x] Test: Verify output matches expected markdown structure

- [x] Task 3: Add CLI report command (AC: #2, #3)
  - [x] Add `report` command to `rustybt/validation/cli.py`
  - [x] Implement `--format` option (markdown default, json optional)
  - [x] Load session from session_id, validate exists
  - [x] Call ReportGenerator with appropriate format
  - [x] Test: CLI integration tests for both formats

- [x] Task 4: Implement report file saving (AC: #4)
  - [x] Save report to session directory path
  - [x] Handle both markdown and JSON file extensions
  - [x] Ensure directory exists before saving
  - [x] Report saved path in console output
  - [x] Test: Verify files saved to correct locations

- [x] Task 5: Implement auto-generation on completion (AC: #5)
  - [x] Hook into SessionManager status change
  - [x] Trigger report generation when status → COMPLETED
  - [x] Add timestamp to report metadata
  - [x] Test: Integration test for auto-generation

- [x] Task 6: Write comprehensive tests (AC: #1-5)
  - [x] Unit tests for ReportGenerator class
  - [x] Integration tests for CLI commands
  - [x] Test with various session states (completed, in-progress, failed)
  - [x] Test with sessions containing BUG, DESIGN, and mixed findings

## Dev Notes

### Architecture Alignment

**Module Location**: `rustybt/validation/reporting.py`

This story implements FR60 (generate validation reports per session) from the PRD.

**Report Structure** (from Epic 7):
```markdown
# Validation Session Report

**Session ID:** 20251123-230000-sma_crossover
**Strategy:** SMA Crossover
**Status:** COMPLETED
**Date:** 2025-11-23

# Summary

| Metric | Value |
|--------|-------|
| Total Findings | 5 |
| BUG | 2 (fixed) |
| DESIGN | 3 (documented) |
| Unclassified | 0 |
| Layers Passed | 5/5 |

# Layer Results

## Layer 1: Data Handling
**Status:** ✓ PASSED

No discrepancies detected.

## Layer 2: Signal Computation
**Status:** ✓ PASSED (2 DESIGN findings)

| Finding | Classification | Description |
|---------|---------------|-------------|
| FIND-001 | DESIGN | RSI smoothing method differs |
| FIND-002 | DESIGN | SMA calculation order differs |

[...]

# Findings Detail

## FIND-001: RSI Smoothing Method
**Classification:** DESIGN
**Layer:** signals
**Rationale:** rustybt uses Wilder's smoothing, Backtrader uses EMA...
[...]
```

**CLI Commands**:
```bash
rustybt-validate report <session_id>
# Report saved to: validation-sessions/{session_id}/report.md

rustybt-validate report <session_id> --format json
# JSON format for programmatic use
```

**Dependencies**:
- `Session` model from `rustybt/validation/models.py`
- `Finding` model from `rustybt/validation/models.py`
- Click CLI framework from `rustybt/validation/cli.py`

### Learnings from Previous Story

**From Story 6-5-initial-strategy-validation-story-5 (Status: review)**

- **Validation Complete**: All 4 strategies validated across all 5 layers - 168 tests pass
- **No BUGs Found**: All discrepancies classified as DESIGN differences (DD-001 to DD-004)
- **Files Available for Report Data**:
  - `docs/validation/design-differences.md` - 4 documented DESIGN differences
  - `docs/validation/bug-fixes.md` - Bug tracking (currently empty)
  - `docs/validation/validation-summary.md` - Full validation report
- **Test Infrastructure**:
  - `tests/validation/regression/` - Regression test directory exists
  - `tests/validation/test_full_validation.py` - 46 integration tests for all strategies
- **CLI Pattern**: Use existing CLI patterns from `rustybt/validation/cli.py`

[Source: docs/sprint-artifacts/6-5-initial-strategy-validation-story-5.md#Dev-Agent-Record]

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/reporting.py` (NEW) - ReportGenerator class
- `rustybt/validation/cli.py` (MODIFY) - Add report command
- `tests/validation/test_reporting.py` (NEW) - Report generation tests

**Existing infrastructure to leverage**:
- `rustybt/validation/models.py` - Session, Finding data models
- `rustybt/validation/session.py` - SessionManager for loading sessions
- `validation-sessions/{session_id}/` - Session storage directories

### Testing Guidance

```python
import pytest
from rustybt.validation.reporting import ReportGenerator
from rustybt.validation.models import Session, Finding

class TestReportGenerator:

    def test_generate_markdown_with_findings(self, sample_session_with_findings):
        """Test markdown report includes all findings."""
        generator = ReportGenerator(sample_session_with_findings)
        report = generator.generate_markdown()

        assert "# Validation Session Report" in report
        assert sample_session_with_findings.id in report
        assert "| Total Findings |" in report

    def test_generate_json_format(self, sample_session_with_findings):
        """Test JSON report contains structured data."""
        generator = ReportGenerator(sample_session_with_findings)
        report = generator.generate_json()

        assert report["session_id"] == sample_session_with_findings.id
        assert "findings" in report
        assert "layers" in report

    def test_report_saved_to_session_directory(self, tmp_session):
        """Test report file saved to correct location."""
        generator = ReportGenerator(tmp_session)
        path = generator.save_markdown()

        assert path.exists()
        assert path.parent == tmp_session.directory
        assert path.name == "report.md"
```

### References

- [Source: docs/epics/epic-7-reporting-documentation-system.md#Story-7.1]
- [Source: docs/architecture.md#Reporting-Documentation]
- [Source: docs/prd.md#FR60-FR67-Reporting-Documentation]
- [Source: docs/architecture.md#CLI-Interface]

## Dev Agent Record

### Context Reference

docs/sprint-artifacts/7-1-reporting-documentation-system-story-1.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Implementation followed the story context and Dev Notes guidance for report structure.

### Completion Notes List

- Implemented ReportGenerator class with full markdown and JSON report generation
- Added CLI `report` command with `--format` option (markdown default, json optional)
- Implemented auto-report generation when session status changes to COMPLETED via SessionManager hook
- Created comprehensive test suite with 32 tests covering all acceptance criteria
- All 823 validation tests pass with no regressions

### File List

**Created:**
- `rustybt/validation/reporting.py` - ReportGenerator class (405 lines)
- `tests/validation/test_reporting.py` - Unit tests for reporting (390 lines)

**Modified:**
- `rustybt/validation/cli.py` - Added `report` command
- `rustybt/validation/session.py` - Added `_auto_generate_report()` hook
- `tests/validation/test_cli.py` - Added CLI tests for report command

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-29 | Story drafted from Epic 7 specification | SM Agent |
| 2025-11-29 | Story implementation complete - all tasks done | Dev Agent |
