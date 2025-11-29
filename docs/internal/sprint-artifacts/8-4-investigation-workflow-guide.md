# Story 8.4: Create Investigation Workflow User Guide

Status: done

## Story

As a **validation framework user**,
I want an **investigation workflow user guide**,
so that I can **properly investigate and classify discrepancies**.

## Acceptance Criteria

1. Users understand how to read discrepancy reports
2. Users understand how to use the investigation CLI commands
3. Users understand when to classify findings as BUG vs DESIGN
4. Users understand how to document investigation rationale
5. Users understand how to verify bug fixes and mark findings as resolved
6. Guide includes decision tree for BUG vs DESIGN classification
7. Guide includes real examples of BUG findings (with investigation walkthrough)
8. Guide includes real examples of DESIGN findings (with documentation approach)
9. Guide includes investigation best practices (reproducibility, evidence gathering)
10. Guide includes tips for source code linking and root cause analysis

## Tasks / Subtasks

- [x] Task 1: Create discrepancy report reading section (AC: #1)
  - [x] Subtask 1.1: Explain report structure and fields
  - [x] Subtask 1.2: Document expected vs actual value interpretation
  - [x] Subtask 1.3: Explain layer-specific discrepancy details
  - [x] Subtask 1.4: Show example report with annotations

- [x] Task 2: Create CLI investigation commands section (AC: #2)
  - [x] Subtask 2.1: Document `rustybt-validate investigate <session_id>` command
  - [x] Subtask 2.2: Document `rustybt-validate investigate --layer <layer>` filtering
  - [x] Subtask 2.3: Document `rustybt-validate classify <finding_id>` command
  - [x] Subtask 2.4: Show typical investigation workflow sequence

- [x] Task 3: Create BUG vs DESIGN classification guide (AC: #3, #6)
  - [x] Subtask 3.1: Define BUG classification criteria (framework error requiring fix)
  - [x] Subtask 3.2: Define DESIGN classification criteria (intentional difference)
  - [x] Subtask 3.3: Create decision tree flowchart
  - [x] Subtask 3.4: Document edge cases and judgment calls

- [x] Task 4: Create documentation requirements section (AC: #4)
  - [x] Subtask 4.1: Document rationale requirements for BUG classifications
  - [x] Subtask 4.2: Document rationale requirements for DESIGN classifications
  - [x] Subtask 4.3: Provide rationale templates and examples
  - [x] Subtask 4.4: Explain findings.yaml structure

- [x] Task 5: Create fix verification section (AC: #5)
  - [x] Subtask 5.1: Document bug fix workflow (code change → revalidate)
  - [x] Subtask 5.2: Document how to mark findings as resolved
  - [x] Subtask 5.3: Document regression test creation
  - [x] Subtask 5.4: Document DESIGN documentation generation

- [x] Task 6: Create BUG example walkthrough (AC: #7)
  - [x] Subtask 6.1: Choose real or realistic bug example
  - [x] Subtask 6.2: Walk through investigation steps
  - [x] Subtask 6.3: Show source code linking
  - [x] Subtask 6.4: Show fix and verification

- [x] Task 7: Create DESIGN example walkthrough (AC: #8)
  - [x] Subtask 7.1: Choose real or realistic design difference example
  - [x] Subtask 7.2: Walk through investigation steps
  - [x] Subtask 7.3: Show rationale documentation
  - [x] Subtask 7.4: Show user-facing documentation generation

- [x] Task 8: Create best practices section (AC: #9, #10)
  - [x] Subtask 8.1: Reproducibility guidelines
  - [x] Subtask 8.2: Evidence gathering techniques
  - [x] Subtask 8.3: Source code navigation tips
  - [x] Subtask 8.4: Root cause analysis methodology

- [x] Task 9: Testing (All ACs)
  - [x] Subtask 9.1: Verify CLI commands documented correctly
  - [x] Subtask 9.2: Verify decision tree logic is clear
  - [x] Subtask 9.3: Review examples for accuracy and completeness

## Dev Notes

### Architecture Constraints

- **Finding Classification Workflow**: All findings must be classified as BUG or DESIGN
- CLI enforces classification before marking finding as resolved
- Unclassified findings block validation completion
- Findings stored in `session/findings.yaml` with structured format

[Source: docs/internal/planning/architecture.md#Pattern-4:-Finding-Classification-Workflow]

### Testing Standards

- Investigation workflow must guide user through classification process (NFR19)
- Zero false positives and false negatives in test suite (NFR2, NFR3)
- All classifications must include timestamps and author (NFR26)

[Source: docs/internal/planning/prd.md#Non-Functional-Requirements]

### Project Structure Notes

- Guide location: `docs/validation/investigation-guide.md`
- Reference actual findings from Epic 6 strategy validation if available
- Cross-reference with DESIGN differences documentation

[Source: docs/internal/planning/epics/epic-8-user-facing-documentation-usage-guide.md#Story-8.4]

### Investigation CLI Reference

```bash
rustybt-validate investigate <session_id> [--layer data]
rustybt-validate classify <finding_id> --type BUG|DESIGN --rationale "..."
rustybt-validate verify <finding_id>
```

[Source: docs/internal/planning/architecture.md#CLI-Interface]

### References

- [Source: docs/internal/planning/epics/epic-8-user-facing-documentation-usage-guide.md#Story-8.4]
- [Source: docs/internal/planning/architecture.md#Pattern-4:-Finding-Classification-Workflow]
- [Source: docs/internal/planning/prd.md#Investigation-&-Classification-Workflow]
- [Source: docs/internal/planning/architecture.md#CLI-Interface]

### Dependencies

- Requires Story 8.2 complete (getting started) - DONE
- Requires Story 8.3 complete (strategy implementation) - DONE

## Dev Agent Record

### Context Reference

- docs/internal/sprint-artifacts/8-4-investigation-workflow-guide.context.xml

### Agent Model Used

claude-opus-4-5-20251101

### Debug Log References

- Verified CLI: rustybt-validate investigate --help (filter by layer, finding, status)
- Verified CLI: rustybt-validate verify --help (verifies bug fixes)
- Reviewed story 8-4 context for requirements

### Completion Notes List

- Created comprehensive investigation-guide.md
- Included investigation process overview with ASCII flowchart
- Documented report structure and field meanings
- Created complete CLI command reference with examples
- Created BUG vs DESIGN decision tree with ASCII diagram
- Documented classification criteria for both BUG and DESIGN
- Created detailed BUG example walkthrough (signal crossover bug)
- Created detailed DESIGN example walkthrough (order execution timing)
- Included bug fix workflow with verify command
- Included design documentation workflow
- Added best practices section (reproducibility, evidence, source linking, root cause)

### File List

**New Files:**
- docs/validation/investigation-guide.md - comprehensive investigation workflow guide

**Modified Files:**
- mkdocs.yml - already included Investigation Workflow Guide from Story 8.3

## Change Log

- 2025-11-29: Story 8.4 implementation complete - comprehensive investigation workflow guide
- 2025-11-29: Senior Developer Review - APPROVED

---

## Senior Developer Review (AI)

### Reviewer
.smirk

### Date
2025-11-29

### Outcome
**APPROVE** - All acceptance criteria implemented and verified with evidence.

### Summary
Story 8.4 delivers a comprehensive investigation workflow guide with decision trees, CLI commands, and real-world examples for both BUG and DESIGN classifications.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | Read discrepancy reports | ✅ IMPLEMENTED | investigation-guide.md:39-88 |
| 2 | Use investigation CLI commands | ✅ IMPLEMENTED | guide.md:90-131 |
| 3 | Classify BUG vs DESIGN | ✅ IMPLEMENTED | guide.md:132-189 |
| 4 | Document investigation rationale | ✅ IMPLEMENTED | guide.md:191-221 |
| 5 | Verify bug fixes and resolve | ✅ IMPLEMENTED | guide.md:223-298 |
| 6 | Decision tree for classification | ✅ IMPLEMENTED | guide.md:132-159 - ASCII diagram |
| 7 | BUG example walkthrough | ✅ IMPLEMENTED | guide.md:300-362 |
| 8 | DESIGN example walkthrough | ✅ IMPLEMENTED | guide.md:364-402 |
| 9 | Best practices | ✅ IMPLEMENTED | guide.md:404-452 |
| 10 | Source code linking tips | ✅ IMPLEMENTED | guide.md:439-452 |

**Summary: 10 of 10 acceptance criteria fully implemented**

### Task Completion Validation
**Summary: 9 of 9 completed tasks verified, 0 questionable, 0 falsely marked complete**

### Zero-Mock Enforcement
**ZERO-MOCK STATUS: PASS - 0 violations (documentation-only story)**

### Orphaned Files Enforcement
**ORPHAN STATUS: PASS - 0 violations**

### Action Items

**Code Changes Required:**
None - story approved.

**Advisory Notes:**
- Note: Consider adding a "quick reference" card for common commands
