# Story 8.7: Create Troubleshooting Guide

Status: done

## Story

As a **validation framework user encountering issues**,
I want a **troubleshooting guide**,
so that I can **resolve common problems independently**.

## Acceptance Criteria

1. Guide provides description of problems
2. Guide provides likely causes for each problem
3. Guide provides step-by-step resolutions
4. Guide indicates when to escalate or report a bug
5. Guide covers installation issues (dependency conflicts, version mismatches)
6. Guide covers strategy execution failures (subprocess errors, log generation issues)
7. Guide covers log parsing errors (schema violations, incomplete logs)
8. Guide covers comparison failures (tolerance configuration, missing data)
9. Guide covers session management issues (corrupted sessions, resume failures)
10. Guide covers common error messages and their meanings

## Tasks / Subtasks

- [x] Task 1: Create installation issues section (AC: #1, #2, #3, #5)
  - [x] Subtask 1.1: Document Python version mismatch issues
  - [x] Subtask 1.2: Document Backtrader installation conflicts
  - [x] Subtask 1.3: Document dependency version conflicts
  - [x] Subtask 1.4: Document virtual environment issues
  - [x] Subtask 1.5: Provide diagnostic commands for each issue

- [x] Task 2: Create strategy execution failures section (AC: #1, #2, #3, #6)
  - [x] Subtask 2.1: Document subprocess exit code errors
  - [x] Subtask 2.2: Document strategy import failures
  - [x] Subtask 2.3: Document log file not generated issues
  - [x] Subtask 2.4: Document timeout and memory issues
  - [x] Subtask 2.5: Provide resolution steps for each

- [x] Task 3: Create log parsing errors section (AC: #1, #2, #3, #7)
  - [x] Subtask 3.1: Document JSONL schema validation errors
  - [x] Subtask 3.2: Document incomplete log file issues
  - [x] Subtask 3.3: Document encoding/charset issues
  - [x] Subtask 3.4: Document malformed JSON line errors
  - [x] Subtask 3.5: Provide log inspection techniques

- [x] Task 4: Create comparison failures section (AC: #1, #2, #3, #8)
  - [x] Subtask 4.1: Document tolerance threshold issues
  - [x] Subtask 4.2: Document missing data field errors
  - [x] Subtask 4.3: Document timestamp alignment failures
  - [x] Subtask 4.4: Document unexpected discrepancy patterns
  - [x] Subtask 4.5: Explain tolerance configuration tuning

- [x] Task 5: Create session management issues section (AC: #1, #2, #3, #9)
  - [x] Subtask 5.1: Document corrupted session.yaml issues
  - [x] Subtask 5.2: Document session resume failures
  - [x] Subtask 5.3: Document missing session directory issues
  - [x] Subtask 5.4: Document findings.yaml corruption
  - [x] Subtask 5.5: Provide session repair techniques

- [x] Task 6: Create error messages reference (AC: #1, #2, #3, #10)
  - [x] Subtask 6.1: Compile list of all error messages
  - [x] Subtask 6.2: Document cause for each error
  - [x] Subtask 6.3: Document resolution for each error
  - [x] Subtask 6.4: Include error message text for searchability

- [x] Task 7: Create escalation section (AC: #4)
  - [x] Subtask 7.1: Define when to report a bug
  - [x] Subtask 7.2: Document bug report requirements
  - [x] Subtask 7.3: Provide GitHub issues link
  - [x] Subtask 7.4: Explain how to gather debug information

- [x] Task 8: Testing (All ACs)
  - [x] Subtask 8.1: Verify diagnostic commands work
  - [x] Subtask 8.2: Verify resolutions are accurate
  - [x] Subtask 8.3: Test error message searchability

## Dev Notes

### Architecture Constraints

- **Error Handling Patterns** from architecture:
  - Strategy Execution Errors: Capture all exceptions, log to `session/errors.log`, mark session as `FAILED`
  - Log Parsing Errors: Validate log schema on parse, reject malformed logs with clear error message
  - Comparison Errors: Handle missing data gracefully, report comparison failures as findings

[Source: docs/architecture.md#Error-Handling]

### Testing Standards

- Log parsing must be robust to minor format variations (NFR4)
- System must recover from test failures without corrupting session state (NFR7)
- System must validate all inputs before processing (NFR9)
- System must prevent data loss during investigation workflows (NFR10)

[Source: docs/prd.md#Non-Functional-Requirements]

### Project Structure Notes

- Guide location: `docs/validation/troubleshooting.md`
- Organize by symptom (what the user sees) not by cause
- Include error message text for searchability
- Provide diagnostic commands users can run
- Keep updated as new issues are discovered

[Source: docs/epics/epic-8-user-facing-documentation-usage-guide.md#Story-8.7]

### Common Error Categories

1. **Installation Errors**
   - `ModuleNotFoundError: No module named 'backtrader'`
   - `Python version X.X is not supported`
   - `Conflicting dependencies for package Y`

2. **Execution Errors**
   - `Subprocess returned non-zero exit code`
   - `Strategy execution timed out`
   - `Log file not found at expected path`

3. **Parsing Errors**
   - `Invalid JSON at line N`
   - `Missing required field 'layer' in log entry`
   - `Log file is incomplete (no END marker)`

4. **Comparison Errors**
   - `Tolerance exceeded for field X`
   - `No matching timestamp in Backtrader log`
   - `Asset not found in comparison set`

5. **Session Errors**
   - `Session not found: <session_id>`
   - `Session is in FAILED state`
   - `Cannot resume completed session`

### References

- [Source: docs/epics/epic-8-user-facing-documentation-usage-guide.md#Story-8.7]
- [Source: docs/architecture.md#Error-Handling]
- [Source: docs/prd.md#Non-Functional-Requirements]

### Dependencies

- Requires Stories 8.2-8.6 complete

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/8-7-troubleshooting-guide.context.xml

### Agent Model Used

<!-- Agent model will be recorded during implementation -->

### Debug Log References

- Troubleshooting guide verified comprehensive (891 lines)

### Completion Notes List

- Created comprehensive troubleshooting.md (891 lines)
- Installation issues documented with resolutions
- Strategy execution failures documented
- Log parsing errors documented
- Comparison failures documented
- Session management issues documented
- Error messages reference included
- Escalation section with GitHub links

### File List

**New Files:**
- docs/validation/troubleshooting.md - comprehensive troubleshooting guide (891 lines)

## Change Log

- 2025-11-29: Story 8.7 implementation complete - comprehensive troubleshooting guide
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
Story 8.7 delivers a comprehensive troubleshooting guide (891 lines) covering installation issues, execution failures, parsing errors, comparison issues, session management, and escalation procedures.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | Problem descriptions | ✅ IMPLEMENTED | Each issue has clear description |
| 2 | Likely causes | ✅ IMPLEMENTED | Causes documented per issue |
| 3 | Step-by-step resolutions | ✅ IMPLEMENTED | Resolution steps included |
| 4 | Escalation guidance | ✅ IMPLEMENTED | When to report bugs documented |
| 5 | Installation issues | ✅ IMPLEMENTED | troubleshooting.md installation section |
| 6 | Execution failures | ✅ IMPLEMENTED | Strategy execution section |
| 7 | Log parsing errors | ✅ IMPLEMENTED | Log parsing section |
| 8 | Comparison failures | ✅ IMPLEMENTED | Comparison section |
| 9 | Session management issues | ✅ IMPLEMENTED | Session issues section |
| 10 | Error messages reference | ✅ IMPLEMENTED | Error messages with causes |

**Summary: 10 of 10 acceptance criteria fully implemented**

### Task Completion Validation
**Summary: 8 of 8 completed tasks verified, 0 questionable, 0 falsely marked complete**

### Zero-Mock Enforcement
**ZERO-MOCK STATUS: PASS - 0 violations (documentation-only story)**

### Orphaned Files Enforcement
**ORPHAN STATUS: PASS - 0 violations**

### Action Items

**Code Changes Required:**
None - story approved.
