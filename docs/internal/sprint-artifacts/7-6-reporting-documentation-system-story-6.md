# Story 7.6: Implement Validation Completion Tracking

Status: done

## Story

As a developer,
I want validation completion percentage tracked,
so that I know how much validation work remains.

## Acceptance Criteria

1. **Given** defined validation scope **When** completion tracking is queried **Then** progress is calculated:
   - Strategy completion: validated_strategies / total_strategies (4)
   - Layer completion: completed_layers / total_layers (20 = 4 strategies × 5 layers)
   - Finding resolution: resolved_findings / total_findings
   - Overall weighted percentage combining all factors

2. **CLI command `rustybt-validate progress` displays progress**:
   - Visual progress bars for each completion category
   - Lists completed vs remaining items
   - Shows "Next Steps" with actionable items

3. **Progress calculation algorithm**:
   ```python
   def calculate_completion() -> ValidationProgress:
       strategy_completion = validated_strategies / total_strategies
       layer_completion = completed_layers / total_layers
       finding_resolution = resolved_findings / total_findings if total_findings > 0 else 1.0
       overall = calculate_weighted_average(...)
   ```

4. **Next steps suggestions based on gaps**:
   - Identifies incomplete strategies
   - Identifies missing layers
   - Suggests commands to continue validation

## Tasks / Subtasks

- [x] Task 1: Implement ValidationProgress model (AC: #1, #3)
  - [x] Create `ValidationProgress` dataclass in `rustybt/validation/reporting.py`
  - [x] Include fields: strategy_completion, layer_completion, finding_resolution, overall
  - [x] Implement calculation methods
  - [x] Test: Unit tests for progress calculations

- [x] Task 2: Implement CompletionTracker class (AC: #1)
  - [x] Create `CompletionTracker` class in `rustybt/validation/reporting.py`
  - [x] Implement session scanning for completion data
  - [x] Implement completion percentage calculations
  - [x] Test: Unit tests for tracker

- [x] Task 3: Add CLI progress command (AC: #2)
  - [x] Add `progress` command to `rustybt/validation/cli.py`
  - [x] Implement progress bar rendering
  - [x] Display completed vs remaining items
  - [x] Test: CLI integration tests

- [x] Task 4: Implement progress bar rendering (AC: #2)
  - [x] Create ASCII progress bar function
  - [x] Handle various completion percentages (0%, 50%, 100%)
  - [x] Use Unicode block characters for visual appeal
  - [x] Test: Verify progress bar output

- [x] Task 5: Implement next steps suggestions (AC: #4)
  - [x] Analyze gaps in validation coverage
  - [x] Generate actionable suggestions
  - [x] Include relevant CLI commands
  - [x] Test: Verify suggestions for various states

- [x] Task 6: Write comprehensive tests (AC: #1-4)
  - [x] Unit tests for ValidationProgress
  - [x] Unit tests for CompletionTracker
  - [x] Integration tests for CLI command
  - [x] Test various completion states

## Dev Notes

### Architecture Alignment

**Module Location**: `rustybt/validation/models.py` and `rustybt/validation/reporting.py`

This story implements FR66 (track validation completion percentage) from the PRD.

**Progress Display** (from Epic 7):
```
Validation Progress
═══════════════════

Strategies: ████████░░ 3/4 (75%)
  ✓ SMA Crossover
  ✓ Mean Reversion
  ✓ Momentum
  ○ Multi-Factor (in progress)

Layers: █████████░ 18/20 (90%)
  Multi-Factor missing: signals, portfolio

Findings: ██████████ 15/15 (100%)
  All findings classified and resolved

Overall: ████████░░ 88%

Next Steps:
  1. Complete Multi-Factor validation (2 layers remaining)
  2. Generate final validation report
```

**CLI Command**:
```bash
rustybt-validate progress
```

**Completion Calculation Logic**:
```python
@dataclass
class ValidationProgress:
    strategy_completion: float  # 0.0 to 1.0
    layer_completion: float     # 0.0 to 1.0
    finding_resolution: float   # 0.0 to 1.0
    overall: float              # Weighted average

def calculate_weighted_average(strategy: float, layer: float, finding: float) -> float:
    """
    Weights:
    - Strategy: 40% (core validation scope)
    - Layer: 30% (depth of validation)
    - Finding: 30% (quality of resolution)
    """
    return (strategy * 0.4) + (layer * 0.3) + (finding * 0.3)
```

**Progress Bar Characters**:
```python
FILLED = "█"
EMPTY = "░"

def render_progress_bar(percentage: float, width: int = 10) -> str:
    filled = int(percentage * width / 100)
    empty = width - filled
    return FILLED * filled + EMPTY * empty
```

### Learnings from Previous Stories

**From Story 7-4 (Status Dashboard)**

- Reuse session scanning and aggregation logic
- Confidence score calculation similar to overall progress
- Progress bar rendering can be shared

**From Story 6-5 (Full Validation)**

- **Current Progress State**:
  - Strategies: 4/4 (100%)
  - Layers: 20/20 (100%)
  - Findings: 4/4 resolved (100%)
  - Overall: 100%
- No incomplete items to suggest

[Source: docs/sprint-artifacts/6-5-initial-strategy-validation-story-5.md#Completion-Notes-List]

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/models.py` (MODIFY) - Add ValidationProgress dataclass
- `rustybt/validation/reporting.py` (MODIFY) - Add CompletionTracker class
- `rustybt/validation/cli.py` (MODIFY) - Add progress command
- `tests/validation/test_reporting.py` (MODIFY) - Add progress tests

**Prerequisites**: Story 7.4 (Overall Status Dashboard)

### Testing Guidance

```python
import pytest
from rustybt.validation.models import ValidationProgress
from rustybt.validation.reporting import CompletionTracker

class TestValidationProgress:

    def test_calculates_strategy_completion(self):
        """Test strategy completion calculation."""
        progress = ValidationProgress.calculate(
            validated_strategies=3,
            total_strategies=4
        )
        assert progress.strategy_completion == 0.75

    def test_calculates_overall_weighted(self):
        """Test weighted overall calculation."""
        progress = ValidationProgress(
            strategy_completion=1.0,
            layer_completion=0.9,
            finding_resolution=1.0,
            overall=0.0  # Will be calculated
        )
        progress.calculate_overall()

        # (1.0 * 0.4) + (0.9 * 0.3) + (1.0 * 0.3) = 0.97
        assert progress.overall == pytest.approx(0.97, rel=0.01)

class TestCompletionTracker:

    def test_identifies_incomplete_strategies(self, partial_validation_state):
        """Test incomplete strategies are identified."""
        tracker = CompletionTracker()
        incomplete = tracker.get_incomplete_strategies()

        assert "multi_factor" in incomplete

    def test_suggests_next_steps(self, partial_validation_state):
        """Test next steps are generated."""
        tracker = CompletionTracker()
        suggestions = tracker.get_next_steps()

        assert len(suggestions) > 0
        assert "Complete" in suggestions[0] or "multi_factor" in suggestions[0]

    def test_handles_complete_state(self, complete_validation_state):
        """Test handles 100% complete state."""
        tracker = CompletionTracker()
        suggestions = tracker.get_next_steps()

        assert "Generate final report" in suggestions[0] or len(suggestions) == 0
```

### References

- [Source: docs/epics/epic-7-reporting-documentation-system.md#Story-7.6]
- [Source: docs/prd.md#FR66-Completion-Tracking]
- [Source: docs/sprint-artifacts/7-4-reporting-documentation-system-story-4.md]

## Dev Agent Record

### Context Reference

- Story context derived from Epic 7 specification and architecture docs

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Implementation completed successfully

### Completion Notes List

- Implemented `ValidationProgress` dataclass with factory method `calculate()` (lines 1970-2046 in reporting.py)
- Implemented weighted completion algorithm: 40% strategy, 30% layer, 30% findings
- Created `CompletionTracker` class for session scanning and progress aggregation (lines 2048-2244)
- Implemented `get_progress()`, `get_incomplete_strategies()`, `get_next_steps()` methods
- Added `render_progress_bar()` helper with Unicode block characters (█/░)
- Added `progress` CLI command (lines 1525-1545 in cli.py)
- Implemented tracking of missing layers per strategy
- All 9 test cases passing in `TestValidationProgress`, `TestCompletionTracker`, and `TestProgressCLI`

### File List

- `rustybt/validation/reporting.py` (MODIFIED) - Added ValidationProgress dataclass, CompletionTracker class
- `rustybt/validation/cli.py` (MODIFIED) - Added progress command
- `tests/validation/test_reporting.py` (MODIFIED) - Added TestValidationProgress, TestCompletionTracker, TestProgressCLI test classes

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-29 | Story drafted from Epic 7 specification | SM Agent |
| 2025-11-29 | Implementation completed, all tasks done | Dev Agent |
| 2025-11-29 | Code review passed, status updated to done | Code Review |
