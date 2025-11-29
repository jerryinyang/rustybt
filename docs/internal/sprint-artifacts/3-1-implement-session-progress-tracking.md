``# Story 3.1: Implement Session Progress Tracking

Status: done

## Story

As a developer,
I want session progress tracked at each stage,
so that I can see where each validation session stands.

## Acceptance Criteria

1. **SessionStage enum implemented** - Define all session lifecycle stages:
   - CREATED: Session initialized
   - EXECUTING: Strategies running
   - EXECUTED: Logs collected
   - COMPARING: Running comparison
   - COMPARED: Discrepancies found
   - INVESTIGATING: Manual investigation
   - COMPLETED: All findings resolved
   - FAILED: Error occurred

2. **Session model includes progress fields**:
   - `stage: SessionStage` with default CREATED
   - `stage_started_at: Optional[datetime]`
   - `execution_completed_at: Optional[datetime]`
   - `comparison_completed_at: Optional[datetime]`
   - `layers_completed: list[str]` (tracks which layers are done)

3. **SessionManager.update_stage() method implemented**:
   - Updates session stage with timestamp
   - Saves session after stage change
   - Raises ValueError for invalid stage transitions

4. **CLI shows stage in session list**:
   - `rustybt-validate session list` displays stage column
   - Format: Session ID | Strategy | Stage | Created

5. **Unit tests verify stage transitions**:
   - Valid transitions succeed
   - Invalid transitions raise ValueError
   - Timestamps recorded correctly

## Tasks / Subtasks

- [x] Task 1: Create SessionStage enum (AC: #1)
  - [x] Add SessionStage enum to `rustybt/validation/models.py`
  - [x] Define all 8 stage values with string representations
  - [x] Add docstring explaining stage lifecycle

- [x] Task 2: Extend Session model with progress fields (AC: #2)
  - [x] Add `stage` field with SessionStage type and default
  - [x] Add `stage_started_at` Optional[datetime] field
  - [x] Add `execution_completed_at` Optional[datetime] field
  - [x] Add `comparison_completed_at` Optional[datetime] field
  - [x] Add `layers_completed` list[str] field with default_factory
  - [x] Update Session serialization/deserialization for YAML

- [x] Task 3: Implement update_stage() method (AC: #3)
  - [x] Add `update_stage()` to SessionManager
  - [x] Set stage and stage_started_at timestamp
  - [x] Define valid stage transition rules
  - [x] Raise ValueError for invalid transitions
  - [x] Call self.save() after update

- [x] Task 4: Update CLI session list to show stage (AC: #4)
  - [x] Modify `session list` command output format
  - [x] Add Stage column to table output
  - [x] Include stage in JSON output format

- [x] Task 5: Write unit tests for stage tracking (AC: #5)
  - [x] Test SessionStage enum values
  - [x] Test valid stage transitions
  - [x] Test invalid stage transitions raise ValueError
  - [x] Test timestamps are recorded correctly
  - [x] Test layers_completed tracking

## Dev Notes

### Architecture Alignment

**Session Model Extension** (Architecture pg 359-387):
- Session dataclass already exists with core fields
- Stage tracking adds lifecycle management
- YAML serialization must handle Enum types

**Session Storage** (Architecture ADR-003):
- Session state persisted in YAML files
- Stage transitions atomic (save after each change)

**Stage Transition Rules**:
```
CREATED -> EXECUTING (start execution)
EXECUTING -> EXECUTED (logs collected) or FAILED (execution error)
EXECUTED -> COMPARING (start comparison)
COMPARING -> COMPARED (discrepancies found) or FAILED (comparison error)
COMPARED -> INVESTIGATING (manual investigation started)
INVESTIGATING -> COMPLETED (all findings resolved) or COMPARED (back to review)
Any -> FAILED (error at any point)
FAILED -> CREATED (retry from scratch)
```

### Learnings from Previous Story

**From Story 2-7-strategy-comparison-infrastructure-story-7 (Status: review)**

- **ExecutionResult Created**: `rustybt/validation/coordinator.py` contains ExecutionResult dataclass with success tracking pattern
- **Session Status Update Pattern**: `update_execution_result()` in session.py shows how to update and save session state
- **EXECUTED Status Added**: Session model already has EXECUTED in status literal - extend for full stage enum
- **Coordinator Integration**: execute_dual() orchestrates framework execution - stage tracking will wrap this

**Pattern to Reuse**:
- ExecutionResult.success property pattern can inform stage transition validation
- Session update pattern: modify fields, call self.save()

**Note**: Story 2-7 is in review status. The coordinator functionality is complete and working (14 tests pass). Session stage tracking builds on top of this foundation.

[Source: docs/sprint-artifacts/2-7-strategy-comparison-infrastructure-story-7.md#Dev-Agent-Record]

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/models.py` (MODIFY - add SessionStage enum, extend Session)
- `rustybt/validation/session.py` (MODIFY - add update_stage method)
- `rustybt/validation/cli.py` (MODIFY - update session list output)
- `tests/validation/test_session_stages.py` (NEW - stage tracking tests)

**Naming convention**: SessionStage enum follows existing pattern (see Architecture Naming Conventions)

### Testing Guidance

**Unit test patterns**:
```python
def test_session_stage_enum_values():
    """Verify all stage values defined."""
    assert SessionStage.CREATED.value == "created"
    assert SessionStage.EXECUTING.value == "executing"
    # ... all 8 stages

def test_valid_stage_transition():
    """Verify valid transitions succeed."""
    session = create_test_session()
    manager = SessionManager()
    manager.update_stage(session, SessionStage.EXECUTING)
    assert session.stage == SessionStage.EXECUTING
    assert session.stage_started_at is not None

def test_invalid_stage_transition():
    """Verify invalid transitions raise ValueError."""
    session = create_test_session()
    session.stage = SessionStage.CREATED
    manager = SessionManager()
    with pytest.raises(ValueError, match="Invalid stage transition"):
        manager.update_stage(session, SessionStage.COMPLETED)  # Can't skip to completed
```

### References

- [Source: docs/architecture.md - Session Model (pg 359-387)]
- [Source: docs/architecture.md - ADR-003 YAML Session Storage]
- [Source: docs/epics/epic-3-session-management-system.md - Story 3.1 specification]
- [Source: docs/sprint-artifacts/2-7-strategy-comparison-infrastructure-story-7.md - session update patterns]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/3-1-implement-session-progress-tracking.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Implementation followed the staged approach:
1. Added SessionStage enum with 8 lifecycle stages and comprehensive docstring
2. Extended Session dataclass with 5 new fields for progress tracking
3. Updated YAML serialization/deserialization in SessionManager
4. Implemented update_stage() with transition validation and timestamp management
5. Updated CLI to display stage in session list and show commands

### Completion Notes List

- **SessionStage Enum**: Created with CREATED, EXECUTING, EXECUTED, COMPARING, COMPARED, INVESTIGATING, COMPLETED, FAILED stages
- **Session Model Extended**: Added stage, stage_started_at, execution_completed_at, comparison_completed_at, layers_completed fields
- **Stage Transitions**: Implemented VALID_TRANSITIONS map in SessionManager with validation logic
- **CLI Enhanced**: Session list now shows Stage column; session show displays all stage-related timestamps
- **JSON Support**: Added --json flag to session list command for programmatic access
- **Backward Compatible**: Existing sessions without stage field default to CREATED on load
- **33 Unit Tests**: Comprehensive test coverage for enum, model fields, transitions, timestamps, and persistence

### File List

**Modified:**
- rustybt/validation/models.py - Added SessionStage enum and extended Session dataclass
- rustybt/validation/session.py - Added update_stage() method, updated load/save for new fields
- rustybt/validation/cli.py - Updated session list with Stage column, enhanced session show
- rustybt/validation/__init__.py - Exported SessionStage

**Created:**
- tests/validation/test_session_stages.py - 33 comprehensive unit tests

---

## Code Review

### Review Summary

| Criteria | Status | Notes |
|----------|--------|-------|
| **Acceptance Criteria** | ✅ PASS | All 5 ACs verified with evidence |
| **Unit Tests** | ✅ PASS | 33/33 tests pass (0 failures) |
| **Zero-Mock Compliance** | ✅ PASS | 0 mock/placeholder violations |
| **Orphaned Files** | ✅ PASS | 0 orphaned files |
| **Code Quality** | ✅ PASS | Syntax valid, imports resolve |
| **Security** | ✅ PASS | Uses yaml.safe_load, no unsafe patterns |
| **Integration** | ✅ PASS | Stage workflow validated end-to-end |

### Acceptance Criteria Verification

| AC# | Description | Evidence |
|-----|-------------|----------|
| 1 | SessionStage enum with 8 stages | `rustybt/validation/models.py:84-116` - Enum defines CREATED through FAILED with string values |
| 2 | Session model progress fields | `rustybt/validation/models.py:155-160` - All 5 fields present with correct types and defaults |
| 3 | update_stage() method | `rustybt/validation/session.py:167-209` - Validates transitions, sets timestamps, auto-saves |
| 4 | CLI shows stage column | `rustybt/validation/cli.py:152-159` - Table output includes Stage column, JSON includes stage field |
| 5 | Unit tests for transitions | `tests/validation/test_session_stages.py` - 33 tests covering valid/invalid transitions, timestamps, persistence |

### Test Execution Results

```
========== test session starts ==========
tests/validation/test_session_stages.py - 33 passed in 0.18s
```

**Test Coverage by Class:**
- TestSessionStageEnum (4 tests): Enum values, count, value parsing
- TestSessionModelStageFields (5 tests): Default values, explicit values
- TestUpdateStageValidTransitions (10 tests): Full lifecycle transitions
- TestUpdateStageInvalidTransitions (6 tests): Blocked transitions, error messages
- TestUpdateStageTimestamps (4 tests): Timestamp recording
- TestUpdateStageSavesSession (2 tests): Persistence verification
- TestLayersCompleted (3 tests): Layer tracking

### Architecture Alignment

✅ **Session Model** - Fields match Architecture spec (pg 359-387)
✅ **YAML Persistence** - Uses safe_load per ADR-003
✅ **Stage Transitions** - Follow documented workflow lifecycle
✅ **Enum Pattern** - Consistent with codebase conventions

### Review Outcome

**APPROVED** ✅

Story is ready for completion. All acceptance criteria met, comprehensive test coverage, clean code quality, and no security issues identified.

### Reviewer

Code Review Agent (Claude Opus 4.5)

### Review Date

2025-11-26

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-26 | Story drafted from epic-3 specification | SM Agent |
| 2025-11-26 | Implementation complete - All 5 ACs satisfied, 33 tests passing | Dev Agent |
| 2025-11-26 | Code review APPROVED | Code Review Agent |
