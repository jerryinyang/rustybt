# Story 10.2.2: Paper Trading State Persistence & Long-Running Stability

Status: done

## Story

As a **developer**,
I want **paper trading state to persist across restarts and run stably for 24+ hours**,
So that **users can trust paper trading for extended strategy validation**.

## Acceptance Criteria

1. **AC1:** Paper trading state persists across session restarts:
   - Open positions restored exactly (size, entry price, unrealized PnL)
   - Order history preserved
   - Session continues from restored state

2. **AC2:** State restoration is accurate:
   - Position size matches pre-restart value
   - Entry price matches pre-restart value
   - Unrealized PnL recalculates correctly with current prices

3. **AC3:** Paper trading runs stably for 24+ hours continuously:
   - No crashes or unhandled exceptions
   - Session remains responsive throughout

4. **AC4:** Memory usage remains stable during long-running operation:
   - Memory growth < 10% over 24 hours
   - No memory leaks detected

5. **AC5:** No state corruption occurs during extended operation:
   - Position tracking remains accurate
   - All calculations remain correct

6. **AC6:** All order state transitions are logged for audit trail

## Tasks / Subtasks

- [ ] Task 1: Implement state persistence test (AC: #1, #2)
  - [ ] Create paper trading session with open positions
  - [ ] Save session state
  - [ ] Stop session
  - [ ] Restore session from saved state
  - [ ] Verify positions match exactly
  - [ ] Verify order history preserved

- [ ] Task 2: Test state restoration accuracy (AC: #2)
  - [ ] Create multiple positions (long and short)
  - [ ] Record exact values before restart
  - [ ] Restart and restore
  - [ ] Assert exact match on all position fields
  - [ ] Test with different position counts

- [ ] Task 3: Implement long-running stability test (AC: #3)
  - [ ] Create `tests/live/paper/test_paper_stability.py`
  - [ ] Configure test for 24-hour duration (or shorter CI variant)
  - [ ] Use pytest-timeout for duration control
  - [ ] Run strategy with periodic signals
  - [ ] Monitor for exceptions

- [ ] Task 4: Implement memory monitoring (AC: #4)
  - [ ] Use `tracemalloc` or `memory_profiler`
  - [ ] Sample memory at hourly intervals
  - [ ] Log memory snapshots to JSON
  - [ ] Calculate memory growth percentage
  - [ ] Assert < 10% growth

- [ ] Task 5: Implement state integrity verification (AC: #5)
  - [ ] Periodically verify position calculations
  - [ ] Compare expected vs actual PnL
  - [ ] Check for data structure corruption
  - [ ] Log any discrepancies

- [ ] Task 6: Verify audit logging (AC: #6)
  - [ ] Confirm all state transitions logged
  - [ ] Verify log format matches audit requirements
  - [ ] Test log retrieval and parsing

- [ ] Task 7: Create stability test markers (AC: #3, #4)
  - [ ] Add `@pytest.mark.slow` for long tests
  - [ ] Add configurable duration via environment variable
  - [ ] Support shorter duration for CI (1 hour)
  - [ ] Support full duration for nightly (24 hours)

## Dev Notes

### State Persistence Implementation

The `state_manager.py` should handle paper trading state. Key verification points:

```python
# State to persist
{
    "positions": [
        {
            "symbol": "BTC-PERP",
            "size": Decimal("0.5"),  # Positive=long, negative=short
            "entry_price": Decimal("45000.00"),
            "entry_time": "2025-12-05T10:00:00Z"
        }
    ],
    "order_history": [...],
    "session_start": "2025-12-05T09:00:00Z",
    "last_update": "2025-12-05T10:30:00Z"
}
```

### Memory Monitoring Strategy

```python
import tracemalloc

tracemalloc.start()
# ... run for interval ...
current, peak = tracemalloc.get_traced_memory()
# Log to JSON: {"timestamp": "...", "current_mb": current/1024/1024, "peak_mb": peak/1024/1024}
```

Memory samples should be taken every hour during the 24-hour test.

### Long-Running Test Configuration

```python
@pytest.mark.slow
@pytest.mark.timeout(86400)  # 24 hours in seconds
def test_paper_trading_24h_stability():
    """Long-running stability test for paper trading."""
    duration = int(os.environ.get("STABILITY_TEST_HOURS", "24")) * 3600
    # ... test implementation
```

### Architecture Patterns and Constraints

From NFRs:
- **NFR4:** Memory usage must remain stable during 48-hour continuous operation (no leaks)
- **NFR5:** State persistence operations must complete within 1 second
- **NFR11:** Paper trading must produce deterministic results given same inputs
- **NFR12:** State recovery after restart must restore exact position state

### Prerequisites

- Story 10.2.1 must be complete (paper trading execution test harness)
- State manager functionality must be working

### References

- [Source: docs/internal/planning/prd-epic-10.md#Paper Trading Validation - FR10, FR11]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.2.2]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#NFR Performance]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.2.2]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

<!-- Will be filled by dev agent -->

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
