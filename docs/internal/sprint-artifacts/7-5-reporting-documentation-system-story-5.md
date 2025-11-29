# Story 7.5: Implement DESIGN Differences Documentation

Status: done

## Story

As a developer,
I want auto-generated documentation for all DESIGN differences,
so that users understand framework behavioral differences.

## Acceptance Criteria

1. **Given** DESIGN-classified findings **When** documentation generation is invoked **Then** user-facing documentation is generated:
   - Grouped by validation layer (Signal Computation, Order Execution, Broker Transactions, etc.)
   - Each finding includes: ID, description, difference explanation, impact assessment, recommendation
   - Written in user-friendly language (not developer jargon)

2. **Documentation file `docs/validation/design-differences.md` is generated**:
   - Structured with clear sections per layer
   - Includes framework versions covered
   - Auto-updates when new DESIGN findings are added

3. **CLI command `rustybt-validate docs generate` produces documentation**:
   - Generates `docs/validation/design-differences.md`
   - Generates `docs/validation/bug-fixes.md`
   - Reports generated file paths

4. **Documentation auto-updates when new findings are classified**:
   - Re-running `docs generate` incorporates new findings
   - Maintains existing documentation structure
   - Preserves manual additions (if any) in marked sections

## Tasks / Subtasks

- [x] Task 1: Implement DocumentationGenerator class (AC: #1)
  - [x] Create `DocumentationGenerator` class in `rustybt/validation/reporting.py`
  - [x] Implement DESIGN findings extraction and grouping
  - [x] Implement user-friendly description conversion
  - [x] Test: Unit tests for documentation generation

- [x] Task 2: Implement documentation structure (AC: #1, #2)
  - [x] Create markdown template for design-differences.md
  - [x] Group findings by layer
  - [x] Include finding ID, description, impact, recommendation per entry
  - [x] Add framework version header
  - [x] Test: Verify output matches expected structure

- [x] Task 3: Add CLI docs command (AC: #3)
  - [x] Add `docs` command group to `rustybt/validation/cli.py`
  - [x] Add `generate` subcommand
  - [x] Generate both design-differences.md and bug-fixes.md
  - [x] Test: CLI integration tests

- [x] Task 4: Implement bug-fixes.md generation (AC: #3)
  - [x] Create template for bug-fixes.md
  - [x] Include fixed bug IDs, descriptions, and regression test references
  - [x] Handle case of no bugs (empty or "None" message)
  - [x] Test: Verify bug-fixes.md generation

- [x] Task 5: Implement auto-update logic (AC: #4)
  - [x] Detect existing documentation
  - [x] Merge new findings with existing content
  - [x] Preserve manually-added sections (marked with comments)
  - [x] Test: Test incremental update scenarios

- [x] Task 6: Write comprehensive tests (AC: #1-4)
  - [x] Unit tests for DocumentationGenerator
  - [x] Integration tests for CLI command
  - [x] Test update/regeneration scenarios

## Dev Notes

### Architecture Alignment

**Module Location**: `rustybt/validation/reporting.py` and `rustybt/validation/cli.py`

This story implements FR65 (generate user-facing documentation of DESIGN differences) from the PRD.

**Documentation Structure** (from Epic 7):
```markdown
# rustybt vs Backtrader: Design Differences

This document describes intentional design differences between rustybt and Backtrader discovered during validation.

# Signal Computation

## RSI Calculation Method

**Finding:** FIND-001, FIND-007, FIND-012

**Difference:**
- rustybt uses Wilder's smoothing (exponential moving average with α = 1/period)
- Backtrader uses standard EMA smoothing

**Impact:**
RSI values may differ by ~0.5% between frameworks. This does not affect trading signal timing in most cases.

**Recommendation:**
No action needed. Both methods are industry-standard approaches to RSI calculation.

---

## MACD Calculation

**Finding:** FIND-015

**Difference:**
- rustybt calculates MACD signal line using 9-period EMA
- Backtrader uses 9-period SMA by default

[...]

# Order Execution

[...]

# Broker Transactions

[...]
```

**CLI Command**:
```bash
rustybt-validate docs generate
# Generated: docs/validation/design-differences.md
# Generated: docs/validation/bug-fixes.md
```

**Manual Section Markers** (for preserving user edits):
```markdown
<!-- MANUAL SECTION START -->
Any content here is preserved during regeneration.
<!-- MANUAL SECTION END -->
```

### Learnings from Previous Stories

**From Stories 7-1 to 7-4 (Report Infrastructure)**

- Reuse session scanning and findings extraction
- Follow established markdown generation patterns
- Leverage CLI command patterns

**From Story 6-5 (Full Validation)**

- **Existing Documentation**:
  - `docs/validation/design-differences.md` already created with DD-001 to DD-004
  - `docs/validation/bug-fixes.md` exists (currently empty - no bugs found)
- **Current DESIGN Findings**:
  - DD-001: RSI calculation (Wilder's smoothing)
  - DD-002: MACD EMA initialization
  - DD-003: Timestamp precision
  - DD-004: Order sizing precision

[Source: docs/sprint-artifacts/6-5-initial-strategy-validation-story-5.md#File-List]

**Important**: This story should enhance existing documentation, not replace it. The generator should support incremental updates.

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/reporting.py` (MODIFY) - Add DocumentationGenerator class
- `rustybt/validation/cli.py` (MODIFY) - Add docs generate command
- `tests/validation/test_reporting.py` (MODIFY) - Add documentation tests

**Output files**:
- `docs/validation/design-differences.md` (GENERATED)
- `docs/validation/bug-fixes.md` (GENERATED)

**Prerequisites**: Story 5.4 (DESIGN classification system from Epic 5)

### Testing Guidance

```python
import pytest
from rustybt.validation.reporting import DocumentationGenerator

class TestDocumentationGenerator:

    def test_groups_by_layer(self, findings_across_layers):
        """Test findings are grouped by validation layer."""
        generator = DocumentationGenerator()
        doc = generator.generate_design_differences()

        assert "# Signal Computation" in doc
        assert "# Order Execution" in doc

    def test_includes_finding_details(self, design_finding):
        """Test each finding includes required fields."""
        generator = DocumentationGenerator()
        doc = generator.generate_design_differences()

        assert "**Finding:**" in doc
        assert "**Difference:**" in doc
        assert "**Impact:**" in doc
        assert "**Recommendation:**" in doc

    def test_user_friendly_language(self, technical_finding):
        """Test output uses user-friendly language."""
        generator = DocumentationGenerator()
        doc = generator.generate_design_differences()

        # Should not contain technical jargon
        assert "pl.DataFrame" not in doc
        assert "JSONL" not in doc

    def test_preserves_manual_sections(self, doc_with_manual_content):
        """Test manual sections are preserved on regeneration."""
        generator = DocumentationGenerator()
        doc = generator.generate_design_differences()

        assert "<!-- MANUAL SECTION START -->" in doc
        assert "User's custom note" in doc
        assert "<!-- MANUAL SECTION END -->" in doc

    def test_handles_no_bugs(self, state_with_no_bugs):
        """Test bug-fixes.md generated correctly when no bugs."""
        generator = DocumentationGenerator()
        doc = generator.generate_bug_fixes()

        assert "No bugs identified" in doc or "None" in doc
```

### References

- [Source: docs/epics/epic-7-reporting-documentation-system.md#Story-7.5]
- [Source: docs/prd.md#FR65-DESIGN-Documentation]
- [Source: docs/architecture.md#Finding-Classification-Workflow]
- [Source: docs/validation/design-differences.md] (existing file to enhance)

## Dev Agent Record

### Context Reference

- Story context derived from Epic 7 specification and architecture docs

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed successfully

### Completion Notes List

- Implemented `DocumentationGenerator` class (lines 1667-1965 in reporting.py)
- Implemented `generate_design_differences()` with layer-based grouping
- Implemented `generate_bug_fixes()` with regression test references
- Added `_get_design_findings_by_layer()` helper for finding aggregation
- Implemented `_format_design_finding()` for user-friendly output
- Added manual section preservation using HTML comment markers
- Added `docs` CLI command group with `generate` and `preview` subcommands
- Implemented `save_design_differences()` and `save_bug_fixes()` methods
- Added `generate_all()` convenience method
- All 8 test cases passing in `TestDocumentationGenerator` and `TestDocsCLI`

### File List

- `rustybt/validation/reporting.py` (MODIFIED) - Added DocumentationGenerator class
- `rustybt/validation/cli.py` (MODIFIED) - Added docs command group (lines 1580-1665)
- `tests/validation/test_reporting.py` (MODIFIED) - Added TestDocumentationGenerator, TestDocsCLI test classes

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-29 | Story drafted from Epic 7 specification | SM Agent |
| 2025-11-29 | Implementation completed, all tasks done | Dev Agent |
| 2025-11-29 | Code review passed, status updated to done | Code Review |
