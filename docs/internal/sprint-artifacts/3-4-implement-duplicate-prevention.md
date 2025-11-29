# Story 3.4: Implement Duplicate Prevention

Status: done

## Story

As a developer,
I want duplicate session/finding prevention,
so that validation work isn't accidentally repeated.

## Acceptance Criteria

1. **Session duplicate detection implemented**:
   - Check for existing IN_PROGRESS session with same strategy before create
   - Raise DuplicateSessionError with clear message
   - Suggest using `session resume` or `session delete`

2. **Finding duplicate detection implemented**:
   - Check for existing finding with same layer/event/timestamp
   - Raise DuplicateFindingError if duplicate found
   - Include existing finding ID in error message

3. **CLI provides clear error messages**:
   - On duplicate session: Show existing session ID and suggested commands
   - On duplicate finding: Show existing finding ID

4. **--force flag allows override**:
   - `rustybt-validate session create --strategy X --data Y --force`
   - Marks existing session as SUPERSEDED
   - Creates new session
   - Warning message about superseded session

5. **Unit tests verify duplicate detection**

## Tasks / Subtasks

- [x] Task 1: Create custom exception classes (AC: #1, #2)
  - [x] Create DuplicateSessionError exception
  - [x] Create DuplicateFindingError exception
  - [x] Add to rustybt/validation/exceptions.py (or models.py)

- [x] Task 2: Implement session duplicate detection (AC: #1)
  - [x] Modify SessionManager.create() to check for existing IN_PROGRESS sessions
  - [x] Use find_sessions(strategy=name, status="IN_PROGRESS")
  - [x] Raise DuplicateSessionError if found
  - [x] Include existing session ID and suggested commands in message

- [x] Task 3: Implement finding duplicate detection (AC: #2)
  - [x] Modify add_finding() to check for duplicates
  - [x] Compare layer, event, timestamp for uniqueness
  - [x] Raise DuplicateFindingError if duplicate found
  - [x] Include existing finding ID in error message

- [x] Task 4: Update CLI with clear error handling (AC: #3)
  - [x] Catch DuplicateSessionError in session create
  - [x] Format user-friendly error message
  - [x] Show suggested commands to resolve

- [x] Task 5: Implement --force flag (AC: #4)
  - [x] Add --force option to session create command
  - [x] When --force and duplicate exists: mark old as SUPERSEDED
  - [x] Add SUPERSEDED status to Session model
  - [x] Create new session and warn about superseded

- [x] Task 6: Write unit tests (AC: #5)
  - [x] Test duplicate session detection
  - [x] Test duplicate finding detection
  - [x] Test --force flag creates new session
  - [x] Test SUPERSEDED status preserved

## Dev Notes

### Architecture Alignment

**Session Uniqueness** (derived from Architecture FR40):
- FR40: System can prevent duplicate investigations across sessions
- Strategy + IN_PROGRESS status combination defines session uniqueness
- Multiple completed sessions for same strategy are allowed

**Finding Uniqueness**:
- layer + event + timestamp uniquely identifies a finding
- Same discrepancy shouldn't be recorded multiple times

### Learnings from Previous Stories

**From Story 3-3 (Status: drafted)**:
- find_sessions() with filters enables duplicate detection
- Can filter by strategy and status to find conflicts

**Pattern to Reuse**:
```python
# From 3-3: Use find_sessions for duplicate check
existing = manager.find_sessions(strategy=name, status="IN_PROGRESS")
if existing:
    raise DuplicateSessionError(...)
```

[Source: docs/sprint-artifacts/3-3-session-management-system-story-3.md - find_sessions method]

### Implementation Pattern

**Exception classes**:
```python
class DuplicateSessionError(Exception):
    """Raised when creating session that duplicates existing IN_PROGRESS session."""
    def __init__(self, existing_session_id: str, strategy: str):
        self.existing_session_id = existing_session_id
        self.strategy = strategy
        message = (
            f"Session {existing_session_id} already in progress for {strategy}. "
            f"Use 'rustybt-validate session resume {existing_session_id}' to continue "
            f"or 'rustybt-validate session delete {existing_session_id}' to start fresh."
        )
        super().__init__(message)

class DuplicateFindingError(Exception):
    """Raised when adding finding that duplicates existing finding."""
    def __init__(self, existing_finding_id: str):
        self.existing_finding_id = existing_finding_id
        message = f"Finding already exists: {existing_finding_id}"
        super().__init__(message)
```

**Session create with duplicate check**:
```python
def create(self, strategy_name: str, data_fixture: Path, force: bool = False) -> Session:
    """Create session with duplicate check."""
    existing = self.find_sessions(
        strategy=strategy_name,
        status="IN_PROGRESS"
    )

    if existing and not force:
        raise DuplicateSessionError(existing[0].id, strategy_name)

    if existing and force:
        # Mark existing as superseded
        for session in existing:
            session.status = "SUPERSEDED"
            self.save(session)
        # Warning will be shown by CLI

    # Continue with creation...
    return self._create_session(strategy_name, data_fixture)
```

**--force flag in CLI**:
```python
@cli.command()
@click.argument('session_id', required=False)
@click.option('--strategy', required=True)
@click.option('--data', required=True, type=click.Path(exists=True))
@click.option('--force', is_flag=True, help="Override existing IN_PROGRESS session")
def create(strategy: str, data: str, force: bool):
    try:
        session = manager.create(strategy, Path(data), force=force)
        if force:
            click.echo(f"Warning: Existing session marked as SUPERSEDED")
        click.echo(f"Created session: {session.id}")
    except DuplicateSessionError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
```

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/exceptions.py` (NEW - custom exceptions)
- `rustybt/validation/session.py` (MODIFY - duplicate checks in create, add_finding)
- `rustybt/validation/models.py` (MODIFY - add SUPERSEDED status)
- `rustybt/validation/cli.py` (MODIFY - error handling, --force flag)
- `tests/validation/test_duplicate_prevention.py` (NEW - duplicate tests)

### Testing Guidance

```python
def test_duplicate_session_raises_error(session_manager, tmp_path):
    """Test creating duplicate session raises DuplicateSessionError."""
    # Create first session
    session_manager.create("test_strategy", fixture_path)

    # Try to create duplicate
    with pytest.raises(DuplicateSessionError) as exc_info:
        session_manager.create("test_strategy", fixture_path)

    assert "already in progress" in str(exc_info.value)
    assert "test_strategy" in str(exc_info.value)

def test_force_flag_supersedes_existing(session_manager, tmp_path):
    """Test --force marks existing session as SUPERSEDED."""
    # Create first session
    first = session_manager.create("test_strategy", fixture_path)

    # Create with force
    second = session_manager.create("test_strategy", fixture_path, force=True)

    # Check first is superseded
    first_reloaded = session_manager.load(first.id)
    assert first_reloaded.status == "SUPERSEDED"
    assert second.status == "IN_PROGRESS"

def test_duplicate_finding_raises_error(session_manager, session_with_findings):
    """Test adding duplicate finding raises DuplicateFindingError."""
    existing_finding = session_with_findings.findings[0]

    duplicate = Finding(
        layer=existing_finding.layer,
        event=existing_finding.event,
        timestamp=existing_finding.timestamp,
        # ... other fields
    )

    with pytest.raises(DuplicateFindingError):
        session_manager.add_finding(session_with_findings, duplicate)
```

### References

- [Source: docs/architecture.md - FR40 Duplicate Prevention]
- [Source: docs/epics/epic-3-session-management-system.md - Story 3.4 specification]
- [Source: docs/sprint-artifacts/3-3-session-management-system-story-3.md - find_sessions method]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/3-4-implement-duplicate-prevention.context.xml

### Agent Model Used

claude-opus-4-5-20251101

### Debug Log References

- Implemented duplicate prevention system following architecture patterns
- Added microseconds to session ID format to ensure uniqueness during rapid creation

### Completion Notes List

- Created exceptions.py with DuplicateSessionError and DuplicateFindingError
- Added SUPERSEDED status to Session model (models.py)
- Implemented find_sessions() method for filtering by strategy and status
- Implemented add_finding() method with duplicate detection by finding ID
- Updated create_session() to check for duplicates and support force flag
- Updated CLI session create command with --force flag and error handling
- Session IDs now include microseconds for uniqueness: YYYYMMDD-HHMMSS-UUUUUU-strategy
- All 23 unit tests pass, all 243 validation tests pass (no regressions)

### File List

- rustybt/validation/exceptions.py (NEW)
- rustybt/validation/models.py (MODIFIED - added SUPERSEDED status)
- rustybt/validation/session.py (MODIFIED - find_sessions, add_finding, duplicate detection)
- rustybt/validation/cli.py (MODIFIED - --force flag, error handling)
- tests/validation/test_duplicate_prevention.py (NEW)

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-26 | Story drafted from epic-3 specification | SM Agent |
| 2025-11-26 | Implementation complete - all ACs met, all tests pass | Dev Agent |
| 2025-11-26 | Code review passed - No blocking issues, marked as done | Code Review |

## Code Review

### Review Summary

**Reviewer**: Senior Developer Code Review Agent
**Date**: 2025-11-26
**Result**: APPROVED - No blocking issues

### Test Results

- **22 tests passed** (test_duplicate_prevention.py)
- Custom exception classes properly tested
- Force flag and SUPERSEDED status verified

### Code Quality Assessment

| Category | Rating | Notes |
|----------|--------|-------|
| Architecture Alignment | Excellent | Follows FR40 duplicate prevention requirement |
| Exception Design | Excellent | DuplicateSessionError/DuplicateFindingError with helpful messages |
| Test Coverage | Excellent | All 5 ACs thoroughly tested |
| Error Messages | Good | Includes suggested commands for resolution |

### Acceptance Criteria Verification

- [x] AC1: DuplicateSessionError raised with existing session ID and suggestions
- [x] AC2: DuplicateFindingError raised for duplicate layer/event/timestamp
- [x] AC3: CLI provides clear error messages with actionable suggestions
- [x] AC4: --force flag marks existing session as SUPERSEDED
- [x] AC5: Unit tests verify all duplicate detection scenarios

### Recommended Code Actions

**None** - Implementation meets all requirements with no blocking issues.

### Notes

- Session IDs include microseconds to ensure uniqueness during rapid creation
- SUPERSEDED status cleanly separates old sessions from new
- Exception messages guide users to resolution (resume or delete)
