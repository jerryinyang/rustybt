# Story 3.3: Implement Session Query Commands

Status: done

## Story

As a developer,
I want comprehensive session query commands,
so that I can find and inspect sessions efficiently.

## Acceptance Criteria

1. **Session list with filters implemented**:
   - `--strategy <name>` filters by strategy name
   - `--status <status>` filters by session status (IN_PROGRESS, COMPLETED, FAILED)
   - `--stage <stage>` filters by session stage
   - `--since <date>` filters sessions created after date
   - `--has-findings` filters to sessions with findings

2. **Session show command with details**:
   - Displays full session metadata
   - Shows progress timeline with timestamps
   - Displays findings summary (count by classification)
   - Shows layers completed vs pending

3. **Session findings command**:
   - `rustybt-validate session findings <session_id>`
   - Lists all findings with ID, layer, classification, description
   - Shows unclassified findings prominently

4. **Output format options**:
   - `--format table` (default) for human-readable output
   - `--format json` for programmatic use
   - Both formats supported by list, show, findings commands

5. **Unit tests verify query filtering logic**

## Tasks / Subtasks

- [x] Task 1: Implement find_sessions() with filters (AC: #1)
  - [x] Add find_sessions() method to SessionManager
  - [x] Accept filter parameters: strategy, status, stage, since, has_findings
  - [x] Apply filters using AND logic
  - [x] Return list of matching sessions

- [x] Task 2: Update CLI session list command (AC: #1)
  - [x] Add Click options for each filter
  - [x] Call find_sessions() with filter values
  - [x] Display results in table or json format

- [x] Task 3: Implement session show command (AC: #2)
  - [x] Add `session show` command with session_id argument
  - [x] Load session and display full details
  - [x] Format progress timeline with checkmarks
  - [x] Calculate findings summary
  - [x] Show layers completed vs pending

- [x] Task 4: Implement session findings command (AC: #3)
  - [x] Add `session findings` command
  - [x] Load session findings from findings.yaml
  - [x] Display as table: ID | Layer | Classification | Description
  - [x] Highlight unclassified findings with "-" marker

- [x] Task 5: Implement output format options (AC: #4)
  - [x] Add --format option to list, show, findings commands
  - [x] Implement table formatter (simple alignment)
  - [x] Implement JSON formatter
  - [x] Set table as default

- [x] Task 6: Write unit tests for query logic (AC: #5)
  - [x] Test filter by strategy
  - [x] Test filter by status
  - [x] Test filter by stage
  - [x] Test filter by date
  - [x] Test filter by has_findings
  - [x] Test combined filters (AND logic)
  - [x] Test JSON output format

## Dev Notes

### Architecture Alignment

**CLI Interface** (Architecture pg 435-452):
- Session management commands under `session` subgroup
- Consistent filter patterns across commands
- Table format with simple alignment (no external deps)

**Session Storage** (Architecture ADR-003):
- Query reads from session directories
- Session metadata in session.yaml
- Findings in findings.yaml

### Learnings from Previous Stories

**From Story 3-1 (Status: drafted)**:
- SessionStage enum provides stage values for filtering
- Session model has stage field for stage-based queries

**From Story 3-2 (Status: drafted)**:
- Session loading pattern established in resume()
- _load_findings() helper can be reused for findings command

**Pattern to Follow**:
- filter functions accept Optional parameters (None = no filter)
- Multiple filters combined with AND logic

[Source: docs/sprint-artifacts/3-1-session-management-system-story-1.md]
[Source: docs/sprint-artifacts/3-2-session-management-system-story-2.md]

### Implementation Pattern

```python
def find_sessions(
    self,
    strategy: Optional[str] = None,
    status: Optional[str] = None,
    stage: Optional[SessionStage] = None,
    since: Optional[datetime] = None,
    has_findings: bool = False
) -> list[Session]:
    """Find sessions matching filter criteria."""
    sessions = self.list_all()

    if strategy:
        sessions = [s for s in sessions if s.strategy_name == strategy]

    if status:
        sessions = [s for s in sessions if s.status == status]

    if stage:
        sessions = [s for s in sessions if s.stage == stage]

    if since:
        sessions = [s for s in sessions if s.created_at >= since]

    if has_findings:
        sessions = [s for s in sessions if len(s.findings) > 0]

    return sorted(sessions, key=lambda s: s.created_at, reverse=True)
```

**CLI show command output**:
```
Session: 20251123-230000-sma_crossover
Strategy: sma_crossover
Status: IN_PROGRESS
Stage: compared
Created: 2025-11-23 23:00:00

Progress:
  [x] Execution completed (23:01:00)
  [x] Comparison completed (23:02:00)
  [ ] Investigation in progress

Findings: 5 total (2 BUG, 1 DESIGN, 2 unclassified)

Layers Completed: data, signals
Layers Pending: orders, broker, portfolio
```

### Project Structure Notes

**Files to modify**:
- `rustybt/validation/session.py` (MODIFY - add find_sessions())
- `rustybt/validation/cli.py` (MODIFY - add show, findings commands, filters)
- `tests/validation/test_session_queries.py` (NEW - query tests)

**No new dependencies** - Table formatting uses string formatting, JSON uses stdlib json

### Testing Guidance

```python
def test_find_sessions_filter_by_strategy(session_manager, test_sessions):
    """Test filtering by strategy name."""
    results = session_manager.find_sessions(strategy="sma_crossover")
    assert all(s.strategy_name == "sma_crossover" for s in results)

def test_find_sessions_filter_by_stage(session_manager, test_sessions):
    """Test filtering by session stage."""
    results = session_manager.find_sessions(stage=SessionStage.COMPARED)
    assert all(s.stage == SessionStage.COMPARED for s in results)

def test_find_sessions_combined_filters(session_manager, test_sessions):
    """Test multiple filters applied together."""
    results = session_manager.find_sessions(
        strategy="sma_crossover",
        status="IN_PROGRESS"
    )
    for session in results:
        assert session.strategy_name == "sma_crossover"
        assert session.status == "IN_PROGRESS"
```

### References

- [Source: docs/architecture.md - CLI Interface (pg 435-452)]
- [Source: docs/architecture.md - Session Storage ADR-003]
- [Source: docs/epics/epic-3-session-management-system.md - Story 3.3 specification]
- [Source: docs/sprint-artifacts/3-1-session-management-system-story-1.md - SessionStage enum]
- [Source: docs/sprint-artifacts/3-2-session-management-system-story-2.md - Session loading patterns]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/3-3-implement-session-query-commands.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Implementation leveraged existing find_sessions() infrastructure and extended with:
1. Additional filters: stage, since, has_findings
2. CLI updates for all filter options with validation
3. Enhanced session show with progress timeline
4. New session findings command

### Completion Notes List

- **find_sessions()**: Extended with stage (SessionStage), since (datetime), and has_findings (bool) filters
- **CLI session list**: Added --strategy, --stage, --since, --has-findings, --format options with input validation
- **CLI session show**: Enhanced with progress timeline display, findings summary, and layers status
- **CLI session findings**: New command showing ID/Layer/Classification/Description table, highlights unclassified
- **Helper functions**: _display_progress_timeline(), _format_findings_summary(), _get_pending_layers()
- **Output formats**: --format option supports "table" (default) and "json" for list, show, findings commands
- **22 Unit Tests**: Comprehensive coverage of all filter combinations and edge cases

### File List

**Modified:**
- rustybt/validation/session.py - Extended find_sessions() with new filters (already existed)
- rustybt/validation/cli.py - Updated session list, enhanced session show, added session findings command

**Created:**
- tests/validation/test_session_queries.py - 22 comprehensive tests for query functionality

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-26 | Story drafted from epic-3 specification | SM Agent |
| 2025-11-26 | Implementation complete - All 5 ACs satisfied, 22 tests passing | Dev Agent |
| 2025-11-26 | Code review passed - No blocking issues, marked as done | Code Review |

## Code Review

### Review Summary

**Reviewer**: Senior Developer Code Review Agent
**Date**: 2025-11-26
**Result**: APPROVED - No blocking issues

### Test Results

- **22 tests passed** (test_session_queries.py)
- 8 test classes covering all filter combinations
- Sorting order verified (newest first)

### Code Quality Assessment

| Category | Rating | Notes |
|----------|--------|-------|
| Architecture Alignment | Excellent | CLI interface follows architecture pg 435-452 |
| Test Coverage | Excellent | All 5 ACs with dedicated test classes |
| Filter Logic | Excellent | AND logic correctly implemented |
| Output Formats | Good | Table and JSON formats work correctly |

### Acceptance Criteria Verification

- [x] AC1: find_sessions() with strategy, status, stage, since, has_findings filters
- [x] AC2: session show displays metadata, progress timeline, findings summary
- [x] AC3: session findings lists findings with ID/layer/classification
- [x] AC4: --format option supports table (default) and json
- [x] AC5: Unit tests verify all query filtering logic

### Recommended Code Actions

**None** - Implementation meets all requirements with no blocking issues.

### Notes

- Helper functions (_format_findings_summary, _get_pending_layers) provide clean CLI output
- Stage validation with proper error messages
- Date parsing with ISO format support
