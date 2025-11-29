# Story 7.7: Implement Next Actions Recommender

Status: done

## Story

As a developer,
I want recommended next actions for validation,
so that I know what to work on next.

## Acceptance Criteria

1. **Given** current validation state **When** next actions are queried **Then** prioritized recommendations are provided:
   - Priority 1: Open bugs (highest priority)
   - Priority 2: Unclassified findings (need investigation)
   - Priority 3: Incomplete strategies (continue validation)
   - Priority 4: Missing documentation (update docs)

2. **Recommendations include actionable commands**:
   - Each recommendation includes a CLI command to execute
   - Commands are copy-pasteable
   - Priority levels indicated (HIGH, MEDIUM, LOW)

3. **CLI command `rustybt-validate next` displays recommendations**:
   - Lists recommendations in priority order
   - Shows count of items per recommendation
   - Provides executable commands

4. **Recommendations update dynamically**:
   - Re-running `next` reflects current state
   - Completed items no longer appear
   - New findings trigger new recommendations

## Tasks / Subtasks

- [x] Task 1: Implement Recommendation model (AC: #1, #2)
  - [x] Create `Recommendation` dataclass in `rustybt/validation/reporting.py`
  - [x] Include fields: priority, action, details, command
  - [x] Implement priority levels (HIGH, MEDIUM, LOW)
  - [x] Test: Unit tests for Recommendation model

- [x] Task 2: Implement NextActionsRecommender class (AC: #1)
  - [x] Create `NextActionsRecommender` class in `rustybt/validation/reporting.py`
  - [x] Implement priority 1: open bugs detection
  - [x] Implement priority 2: unclassified findings detection
  - [x] Implement priority 3: incomplete strategies detection
  - [x] Implement priority 4: documentation status detection
  - [x] Test: Unit tests for each priority level

- [x] Task 3: Add CLI next-actions command (AC: #3)
  - [x] Add `next-actions` command to `rustybt/validation/cli.py`
  - [x] Display recommendations with priority indicators
  - [x] Include copy-pasteable commands
  - [x] Test: CLI integration tests

- [x] Task 4: Implement command generation (AC: #2)
  - [x] Generate appropriate CLI commands for each recommendation
  - [x] Include relevant parameters (session IDs, finding IDs)
  - [x] Format commands for easy copying
  - [x] Test: Verify command generation

- [x] Task 5: Implement dynamic state analysis (AC: #4)
  - [x] Scan current validation state on each invocation
  - [x] Filter out completed items
  - [x] Detect new findings from recent sessions
  - [x] Test: Test state change scenarios

- [x] Task 6: Write comprehensive tests (AC: #1-4)
  - [x] Unit tests for Recommendation model
  - [x] Unit tests for NextActionsRecommender
  - [x] Integration tests for CLI command
  - [x] Test various validation states

## Dev Notes

### Architecture Alignment

**Module Location**: `rustybt/validation/models.py` and `rustybt/validation/reporting.py`

This story implements FR67 (identify next recommended validation actions) from the PRD.

**Recommendation Logic** (from Epic 7):
```python
def recommend_next_actions() -> list[Recommendation]:
    """Recommend next validation actions based on current state."""
    actions = []

    # Priority 1: Open bugs
    open_bugs = get_open_bug_findings()
    if open_bugs:
        actions.append(Recommendation(
            priority=1,
            action="Fix open bugs",
            details=f"{len(open_bugs)} BUG findings require fixes",
            command="rustybt-validate investigate --bugs"
        ))

    # Priority 2: Unclassified findings
    unclassified = get_unclassified_findings()
    if unclassified:
        actions.append(Recommendation(
            priority=2,
            action="Classify findings",
            details=f"{len(unclassified)} findings need classification",
            command="rustybt-validate investigate --unclassified"
        ))

    # Priority 3: Incomplete strategies
    incomplete = get_incomplete_strategies()
    if incomplete:
        actions.append(Recommendation(
            priority=3,
            action="Complete strategy validation",
            details=f"{incomplete[0]} has incomplete layers",
            command=f"rustybt-validate run {incomplete[0].session_id}"
        ))

    # Priority 4: Missing documentation
    if needs_documentation_update():
        actions.append(Recommendation(
            priority=4,
            action="Update documentation",
            details="DESIGN differences need documentation refresh",
            command="rustybt-validate docs generate"
        ))

    return sorted(actions, key=lambda x: x.priority)
```

**CLI Output** (from Epic 7):
```
Recommended Next Actions
════════════════════════

1. [HIGH] Fix open bugs (2 BUG findings)
   Command: rustybt-validate investigate --bugs

2. [MEDIUM] Classify findings (3 unclassified)
   Command: rustybt-validate investigate --unclassified

3. [LOW] Update documentation
   Command: rustybt-validate docs generate
```

**CLI Command**:
```bash
rustybt-validate next
```

**Priority Mapping**:
| Priority | Level | Indicator |
|----------|-------|-----------|
| 1 | HIGH | [HIGH] (red if color supported) |
| 2 | MEDIUM | [MEDIUM] (yellow if color supported) |
| 3-4 | LOW | [LOW] (green if color supported) |

### Learnings from Previous Stories

**From Story 7-6 (Completion Tracking)**

- Progress tracking provides state data for recommendations
- "Next Steps" from progress command similar to this feature
- Reuse state analysis logic

**From Stories 7-4 and 7-5**

- Session scanning and aggregation patterns
- CLI command patterns

**From Story 6-5 (Full Validation)**

- **Current State** (likely empty recommendations):
  - 0 open bugs
  - 0 unclassified findings
  - 4/4 strategies complete
  - Documentation exists
- Expected output: "All validation complete. Generate final report."

[Source: docs/sprint-artifacts/6-5-initial-strategy-validation-story-5.md#Completion-Notes-List]

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/models.py` (MODIFY) - Add Recommendation dataclass
- `rustybt/validation/reporting.py` (MODIFY) - Add NextActionsRecommender class
- `rustybt/validation/cli.py` (MODIFY) - Add next command
- `tests/validation/test_reporting.py` (MODIFY) - Add recommender tests

**Prerequisites**: Story 7.6 (Validation Completion Tracking)

### Testing Guidance

```python
import pytest
from rustybt.validation.models import Recommendation
from rustybt.validation.reporting import NextActionsRecommender

class TestRecommendation:

    def test_priority_ordering(self):
        """Test recommendations sort by priority."""
        recs = [
            Recommendation(priority=3, action="Low", details="", command=""),
            Recommendation(priority=1, action="High", details="", command=""),
            Recommendation(priority=2, action="Medium", details="", command=""),
        ]
        sorted_recs = sorted(recs, key=lambda x: x.priority)

        assert sorted_recs[0].priority == 1
        assert sorted_recs[1].priority == 2
        assert sorted_recs[2].priority == 3

class TestNextActionsRecommender:

    def test_prioritizes_open_bugs(self, state_with_open_bugs):
        """Test open bugs are highest priority."""
        recommender = NextActionsRecommender()
        recs = recommender.recommend()

        assert recs[0].action == "Fix open bugs"
        assert recs[0].priority == 1

    def test_includes_commands(self, state_with_unclassified):
        """Test recommendations include executable commands."""
        recommender = NextActionsRecommender()
        recs = recommender.recommend()

        for rec in recs:
            assert rec.command.startswith("rustybt-validate")

    def test_empty_when_complete(self, complete_validation_state):
        """Test no recommendations when validation complete."""
        recommender = NextActionsRecommender()
        recs = recommender.recommend()

        # Either empty or single "generate final report" recommendation
        assert len(recs) <= 1

    def test_updates_dynamically(self, changing_state):
        """Test recommendations update with state changes."""
        recommender = NextActionsRecommender()

        # Initial state has unclassified
        recs1 = recommender.recommend()
        assert any(r.action == "Classify findings" for r in recs1)

        # After classification
        changing_state.classify_all()
        recs2 = recommender.recommend()
        assert not any(r.action == "Classify findings" for r in recs2)
```

### References

- [Source: docs/epics/epic-7-reporting-documentation-system.md#Story-7.7]
- [Source: docs/prd.md#FR67-Next-Actions]
- [Source: docs/sprint-artifacts/7-6-reporting-documentation-system-story-6.md]

## Dev Agent Record

### Context Reference

- Story context derived from Epic 7 specification and architecture docs

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed successfully

### Completion Notes List

- Implemented `Recommendation` dataclass with priority levels and `get_priority_label()` method (lines 2249-2272 in reporting.py)
- Implemented `NextActionsRecommender` class with full recommendation logic (lines 2274-2461)
- Added Priority 1: Open bugs detection with `rustybt-validate investigate --bugs` command
- Added Priority 2: Unclassified findings detection with investigate command
- Added Priority 3: Incomplete strategies detection with resume command
- Added Priority 4: Documentation update detection with docs generate command
- Implemented `recommend()` method returning sorted list of Recommendations
- Added `render()` method for formatted CLI output with priority indicators
- Added `next-actions` CLI command (lines 1548-1568 in cli.py)
- All 8 test cases passing in `TestRecommendation`, `TestNextActionsRecommender`, and `TestNextActionsCLI`

### File List

- `rustybt/validation/reporting.py` (MODIFIED) - Added Recommendation dataclass, NextActionsRecommender class
- `rustybt/validation/cli.py` (MODIFIED) - Added next-actions command
- `tests/validation/test_reporting.py` (MODIFIED) - Added TestRecommendation, TestNextActionsRecommender, TestNextActionsCLI test classes

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-29 | Story drafted from Epic 7 specification | SM Agent |
| 2025-11-29 | Implementation completed, all tasks done | Dev Agent |
| 2025-11-29 | Code review passed, status updated to done | Code Review |
