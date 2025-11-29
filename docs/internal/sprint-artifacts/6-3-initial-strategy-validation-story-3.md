# Story 6.3: Implement Momentum Strategy (Dual)

Status: review

## Story

As a developer,
I want Momentum strategy with RSI and trailing stops implemented,
so that more complex order management can be validated.

## Acceptance Criteria

1. **rustybt Momentum implementation exists** at `tests/validation/strategies/rustybt/momentum.py`:
   - Extends `RustyBTValidatedStrategy` base class
   - Implements RSI indicator calculation
   - Implements trailing stop logic
   - Default parameters: rsi_period=14, oversold=30, overbought=70, trailing_stop_pct=0.05
   - Buy when RSI < 30 (oversold, expecting upward momentum)
   - Sell when RSI > 70 (overbought, expecting downward momentum)
   - Exit via trailing stop at 5%

2. **Backtrader Momentum implementation exists** at `tests/validation/strategies/backtrader/momentum.py`:
   - Extends `BacktraderValidatedStrategy` base class
   - Uses `bt.indicators.RSI` or equivalent calculation
   - Implements equivalent trailing stop logic
   - Logically equivalent to rustybt implementation

3. **Trailing stop logic correctly implemented**:
   - For LONG positions: stop_price = max(stop_price, current_price * (1 - trailing_pct))
   - For SHORT positions: stop_price = min(stop_price, current_price * (1 + trailing_pct))
   - Stop price only moves in favorable direction (ratchets)
   - Exit triggered when price crosses stop

4. **Strategy audit checklist passed**:
   - [x] Same RSI calculation (note: may be DESIGN difference - rustybt uses simple average, Backtrader uses Wilder's smoothing)
   - [x] Same trailing stop logic
   - [x] Same entry conditions (RSI thresholds)
   - [x] Same exit conditions (RSI + trailing stop)

5. **Log stop price updates for comparison**:
   - Log RSI value on each bar
   - Log stop price updates when position exists
   - Log exit trigger reason (RSI exit vs trailing stop)

6. **Unit tests verify**:
   - RSI calculation logic
   - Trailing stop ratcheting behavior
   - Entry/exit signal generation
   - Position management with stops

## Tasks / Subtasks

- [x] Task 1: Create rustybt Momentum strategy (AC: #1)
  - [x] Create `tests/validation/strategies/rustybt/momentum.py`
  - [x] Implement `MomentumStrategy` class
  - [x] Add RSI indicator calculation
  - [x] Implement trailing stop logic with stop price tracking
  - [x] Add entry/exit logic based on RSI and stops

- [x] Task 2: Create Backtrader Momentum strategy (AC: #2)
  - [x] Create `tests/validation/strategies/bt_strategies/momentum.py`
  - [x] Use `bt.indicators.RSI` for RSI calculation
  - [x] Implement equivalent trailing stop logic
  - [x] Ensure log output matches rustybt format

- [x] Task 3: Implement trailing stop logic (AC: #3)
  - [x] Create `update_trailing_stop()` method
  - [x] Handle LONG position stop updates
  - [x] Handle SHORT position stop updates
  - [x] Implement stop trigger detection

- [x] Task 4: Verify strategy equivalence (AC: #4)
  - [x] Complete strategy audit checklist
  - [x] Document RSI calculation differences (DESIGN candidate)
  - [x] Verify trailing stop behavior matches
  - [x] Document any other differences

- [x] Task 5: Validate log output (AC: #5)
  - [x] Log RSI values with `@log_signal()` decorator
  - [x] Log stop price updates
  - [x] Log exit trigger reasons
  - [x] Verify log format consistency

- [x] Task 6: Write unit tests (AC: #6)
  - [x] Create `tests/validation/test_momentum_strategy.py`
  - [x] Test RSI calculation accuracy
  - [x] Test trailing stop ratcheting
  - [x] Test entry signals at RSI thresholds
  - [x] Test exit via trailing stop

## Dev Notes

### Architecture Alignment

**RSI Calculation** (Note: May differ between frameworks - DESIGN candidate):
```python
def compute_rsi(self, prices: list[float], period: int = 14) -> float:
    """Compute Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0  # Neutral when insufficient data

    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi
```

**Trailing Stop Logic**:
```python
def update_trailing_stop(self, current_price: float) -> None:
    """Update trailing stop price (ratchets in favorable direction only)."""
    if self.position_type == "LONG":
        new_stop = current_price * (1 - self.trailing_stop_pct)
        self.stop_price = max(self.stop_price, new_stop)
    elif self.position_type == "SHORT":
        new_stop = current_price * (1 + self.trailing_stop_pct)
        self.stop_price = min(self.stop_price, new_stop)

def check_stop_triggered(self, current_price: float) -> bool:
    """Check if trailing stop has been triggered."""
    if self.position_type == "LONG":
        return current_price <= self.stop_price
    elif self.position_type == "SHORT":
        return current_price >= self.stop_price
    return False
```

**Log Schema for Momentum**:
```json
{
  "timestamp": "2020-01-15T09:30:00",
  "layer": "signals",
  "event": "rsi_computed",
  "asset": "AAPL",
  "data": {
    "price": 150.25,
    "rsi": 28.5,
    "signal": "BUY",
    "stop_price": null
  }
}
```

```json
{
  "timestamp": "2020-01-16T09:30:00",
  "layer": "orders",
  "event": "stop_updated",
  "asset": "AAPL",
  "data": {
    "price": 155.00,
    "previous_stop": 142.74,
    "new_stop": 147.25,
    "position_type": "LONG"
  }
}
```

### Learnings from Previous Stories

**From Story 6-1 (SMA Crossover) and 6-2 (Mean Reversion)**

- **Strategy Pattern**: Extend ValidatedStrategy, use decorators for consistent logging
- **Indicator Differences**: RSI calculation may differ between frameworks - document as DESIGN
- **Edge Cases**: Handle insufficient data, division by zero scenarios
- **Testing Coverage**: Test calculation accuracy, signal generation, edge cases

[Source: docs/sprint-artifacts/6-1-initial-strategy-validation-story-1.md]
[Source: docs/sprint-artifacts/6-2-initial-strategy-validation-story-2.md]

### Project Structure Notes

**Files to create**:
- `tests/validation/strategies/rustybt/momentum.py` (NEW)
- `tests/validation/strategies/backtrader/momentum.py` (NEW)
- `tests/validation/test_momentum_strategy.py` (NEW)

**Existing files to reference**:
- `tests/validation/strategies/rustybt/sma_crossover.py` - Pattern reference
- `tests/validation/strategies/rustybt/mean_reversion.py` - Pattern reference

### Technical Notes

**RSI Calculation Differences (Potential DESIGN)**:
- rustybt may use simple average for RSI
- Backtrader uses Wilder's smoothing (exponential)
- This is a known DESIGN difference if detected
- Document in `docs/validation/design-differences.md#rsi-calculation`

**Trailing Stop Implementation**:
- Key validation point for order management
- Must log every stop price update
- Exit trigger reason must be explicit (RSI exit vs stop exit)

### Testing Guidance

```python
import pytest

@pytest.mark.layer_2_signals
@pytest.mark.layer_3_orders
class TestMomentumStrategy:

    def test_rsi_calculation_oversold(self):
        """Test RSI correctly identifies oversold condition."""
        # Series of declining prices -> RSI < 30

    def test_rsi_calculation_overbought(self):
        """Test RSI correctly identifies overbought condition."""
        # Series of rising prices -> RSI > 70

    def test_trailing_stop_ratchets_up_for_long(self):
        """Test stop price increases with rising prices for LONG."""
        strategy = MomentumStrategy(trailing_stop_pct=0.05)
        strategy.position_type = "LONG"
        strategy.stop_price = 95.0

        strategy.update_trailing_stop(100.0)  # Stop should be 95.0
        assert strategy.stop_price == 95.0

        strategy.update_trailing_stop(110.0)  # Stop should be 104.5
        assert strategy.stop_price == 104.5

        strategy.update_trailing_stop(105.0)  # Stop should stay 104.5 (ratchet)
        assert strategy.stop_price == 104.5

    def test_trailing_stop_triggers_exit(self):
        """Test exit when price crosses stop."""
        strategy = MomentumStrategy(trailing_stop_pct=0.05)
        strategy.position_type = "LONG"
        strategy.stop_price = 100.0

        assert not strategy.check_stop_triggered(101.0)
        assert strategy.check_stop_triggered(99.0)

    def test_exit_reason_logged(self):
        """Test exit trigger reason is logged correctly."""
        # Verify log contains "trailing_stop" or "rsi_exit" as reason
```

### References

- [Source: docs/architecture.md#Novel-Pattern-Log-Based-Validation-Architecture]
- [Source: docs/epics/epic-6-initial-strategy-validation-4-strategies.md#Story-6.3]
- [Source: docs/prd.md#FR57-Strategy-Validation]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/6-3-initial-strategy-validation-story-3.context.xml

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- All 24 unit tests pass for momentum strategy
- RSI calculation differs: rustybt uses simple average, Backtrader uses Wilder's smoothing (known DESIGN difference)
- Trailing stop logic is identical between frameworks
- Fixed base class `close()` method conflict with Backtrader's built-in `close()` - renamed to `close_log()`
- Test data fixtures extended to 45-50 points to avoid RSI division-by-zero with Backtrader

### File List

- `tests/validation/strategies/rustybt/momentum.py` (NEW) - RustyBT Momentum strategy with RSI and trailing stops
- `tests/validation/strategies/bt_strategies/momentum.py` (NEW) - Backtrader Momentum strategy with bt.indicators.RSI
- `tests/validation/test_momentum_strategy.py` (NEW) - 24 unit tests for momentum strategy
- `tests/validation/strategies/rustybt/__init__.py` (MODIFIED) - Added MomentumStrategy export
- `tests/validation/strategies/bt_strategies/__init__.py` (MODIFIED) - Added MomentumStrategy export
- `tests/validation/strategies/bt_strategies/base_validated.py` (MODIFIED) - Renamed close() to close_log() to avoid conflict

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-28 | Story drafted from Epic 6 specification | SM Agent |
| 2025-11-28 | Implemented dual Momentum strategies and tests | Dev Agent |

## Senior Developer Review (AI)

- **Reviewer**: Antigravity (AI Senior Developer)
- **Date**: 2025-11-29
- **Outcome**: **Approve**
- **Summary**: The implementation of the Momentum strategy in both rustybt and Backtrader frameworks is complete and correct. The code follows the required patterns, uses the correct base classes, and implements identical logic. The test suite is comprehensive and verifies equivalence, including the known design difference in RSI calculation (simple average vs Wilder's smoothing).

### Key Findings

- **HIGH Severity**: None.
- **MEDIUM Severity**: None.
- **LOW Severity**: None.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | rustybt Momentum implementation exists | IMPLEMENTED | `tests/validation/strategies/rustybt/momentum.py` |
| 2 | Backtrader Momentum implementation exists | IMPLEMENTED | `tests/validation/strategies/bt_strategies/momentum.py` |
| 3 | Trailing stop logic correctly implemented | IMPLEMENTED | `tests/validation/test_momentum_strategy.py` (TestTrailingStopLogic) |
| 4 | Strategy audit checklist passed | IMPLEMENTED | `tests/validation/test_momentum_strategy.py` (TestStrategyAuditChecklist) |
| 5 | Log stop price updates for comparison | IMPLEMENTED | Verified in `test_log_output_format` and `test_log_output_matches_schema` |
| 6 | Unit tests verify RSI and trailing stop logic | IMPLEMENTED | `tests/validation/test_momentum_strategy.py` (24 tests passed) |

**Summary**: 6 of 6 acceptance criteria fully implemented.

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| 1. Create rustybt Momentum strategy | [x] | VERIFIED COMPLETE | `tests/validation/strategies/rustybt/momentum.py` |
| 2. Create Backtrader Momentum strategy | [x] | VERIFIED COMPLETE | `tests/validation/strategies/bt_strategies/momentum.py` |
| 3. Implement trailing stop logic | [x] | VERIFIED COMPLETE | `tests/validation/test_momentum_strategy.py` |
| 4. Verify strategy equivalence | [x] | VERIFIED COMPLETE | `tests/validation/test_momentum_strategy.py` |
| 5. Validate log output | [x] | VERIFIED COMPLETE | `tests/validation/test_momentum_strategy.py` |
| 6. Write unit tests | [x] | VERIFIED COMPLETE | `tests/validation/test_momentum_strategy.py` |

**Summary**: 6 of 6 completed tasks verified.

### Zero-Mock Enforcement

| Check Type | File:Line | Status | Details |
|------------|-----------|--------|---------|
| Hardcoded Returns | N/A | PASS | No hardcoded returns found in production code. |
| Always-Succeeding Validations | N/A | PASS | No dummy validations found. |
| Mock Patterns | N/A | PASS | No mock/stub patterns found in production code. |
| Empty Error Handlers | N/A | PASS | No empty error handlers found. |
| Test Quality | `tests/validation/test_momentum_strategy.py` | PASS | Tests use real framework execution and meaningful assertions. |

**Summary**: ZERO-MOCK STATUS: PASS (0 violations)

### Orphaned Files Enforcement

| File Path | Issue Type | Severity | Suggested Location |
|-----------|------------|----------|--------------------|
| `tests/validation/strategies/rustybt/momentum.py` | None | PASS | Correctly placed. |
| `tests/validation/strategies/bt_strategies/momentum.py` | None | PASS | Correctly placed. |
| `tests/validation/test_momentum_strategy.py` | None | PASS | Correctly placed. |

**Summary**: ORPHAN STATUS: PASS (0 violations)

### Action Items

**Code Changes Required:**
- None.

**Advisory Notes:**
- Note: The RSI calculation difference (simple average vs Wilder's smoothing) is a known design choice and is acceptable for this validation phase.
