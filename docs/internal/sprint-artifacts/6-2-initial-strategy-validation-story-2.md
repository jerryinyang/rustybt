# Story 6.2: Implement Mean Reversion Strategy (Dual)

Status: review

## Story

As a developer,
I want Mean Reversion strategy implemented in both frameworks,
so that z-score based strategies can be validated.

## Acceptance Criteria

1. **rustybt Mean Reversion implementation exists** at `tests/validation/strategies/rustybt/mean_reversion.py`:
   - Extends `RustyBTValidatedStrategy` base class
   - Implements z-score calculation: `z = (price - mean) / std_dev`
   - Uses rolling window for mean/std calculation
   - Default parameters: lookback_period=20, entry_threshold=2.0, exit_threshold=0.0
   - Buy when z-score < -2 (oversold)
   - Sell when z-score > 2 (overbought)
   - Exit when z-score returns to 0 (mean reversion complete)

2. **Backtrader Mean Reversion implementation exists** at `tests/validation/strategies/backtrader/mean_reversion.py`:
   - Extends `BacktraderValidatedStrategy` base class
   - Implements equivalent z-score calculation
   - Logically equivalent to rustybt implementation
   - Same default parameters

3. **Strategy audit checklist passed**:
   - [x] Same z-score calculation formula
   - [x] Same rolling window implementation
   - [x] Same entry/exit thresholds
   - [x] Same position management logic

4. **Z-score edge cases handled**:
   - Division by zero when std_dev = 0
   - Insufficient data for lookback period
   - NaN/Inf handling

5. **Unit tests verify z-score calculation logic**:
   - Test z-score formula accuracy
   - Test rolling window behavior
   - Test entry/exit signal generation
   - Test edge case handling

6. **Log z-score values for signal comparison**:
   - Log mean, std_dev, z-score on each bar
   - Log entry/exit signals with z-score context

## Tasks / Subtasks

- [x] Task 1: Create rustybt Mean Reversion strategy (AC: #1)
  - [x] Create `tests/validation/strategies/rustybt/mean_reversion.py`
  - [x] Implement `MeanReversionStrategy` class
  - [x] Add rolling mean/std calculation
  - [x] Add z-score computation with `@log_signal()` decorator
  - [x] Implement entry/exit logic based on thresholds

- [x] Task 2: Create Backtrader Mean Reversion strategy (AC: #2)
  - [x] Create `tests/validation/strategies/bt_strategies/mean_reversion.py`
  - [x] Implement equivalent z-score calculation
  - [x] Use Backtrader's rolling statistics if available
  - [x] Ensure log output matches rustybt format

- [x] Task 3: Verify strategy equivalence (AC: #3)
  - [x] Complete strategy audit checklist
  - [x] Compare z-score calculations
  - [x] Verify rolling window alignment
  - [x] Document any framework differences

- [x] Task 4: Handle edge cases (AC: #4)
  - [x] Add division by zero protection
  - [x] Handle insufficient lookback data
  - [x] Test NaN/Inf scenarios
  - [x] Document edge case behavior

- [x] Task 5: Write unit tests (AC: #5)
  - [x] Create `tests/validation/test_mean_reversion_strategy.py`
  - [x] Test z-score calculation accuracy
  - [x] Test rolling window behavior
  - [x] Test signal generation at thresholds
  - [x] Test edge case handling

- [x] Task 6: Validate log output (AC: #6)
  - [x] Verify z-score values logged
  - [x] Check mean/std_dev logging
  - [x] Confirm signal context in logs

## Dev Notes

### Architecture Alignment

**Z-Score Calculation**:
```python
def compute_zscore(self, prices: list[float], lookback: int) -> float:
    """Compute z-score for mean reversion signal."""
    if len(prices) < lookback:
        return 0.0  # Insufficient data

    window = prices[-lookback:]
    mean = sum(window) / len(window)
    variance = sum((p - mean) ** 2 for p in window) / len(window)
    std_dev = variance ** 0.5

    if std_dev == 0:
        return 0.0  # Avoid division by zero

    current_price = prices[-1]
    z_score = (current_price - mean) / std_dev
    return z_score
```

**Mean Reversion Logic**:
- Z-score < -entry_threshold (-2.0): Price significantly below mean → BUY (expect reversion up)
- Z-score > +entry_threshold (+2.0): Price significantly above mean → SELL (expect reversion down)
- |Z-score| < exit_threshold (0.0): Mean reversion complete → EXIT position

**Log Schema for Z-Score**:
```json
{
  "timestamp": "2020-01-15T09:30:00",
  "layer": "signals",
  "event": "zscore_computed",
  "asset": "AAPL",
  "data": {
    "price": 150.25,
    "mean": 148.50,
    "std_dev": 2.15,
    "z_score": 0.81,
    "signal": "HOLD"
  }
}
```

### Learnings from Previous Story

**From Story 6-1 (SMA Crossover)**

- **Strategy Pattern**: Extend ValidatedStrategy base class, use decorators for logging
- **Indicator Setup**: Initialize indicators in `initialize()` method
- **Signal Logging**: Use `@log_signal()` decorator on signal computation
- **Order Logging**: Use `@log_order()` decorator on order execution
- **Testing Pattern**: Test calculation accuracy, signal generation, edge cases

[Source: docs/sprint-artifacts/6-1-initial-strategy-validation-story-1.md]

### Project Structure Notes

**Files to create**:
- `tests/validation/strategies/rustybt/mean_reversion.py` (NEW)
- `tests/validation/strategies/backtrader/mean_reversion.py` (NEW)
- `tests/validation/test_mean_reversion_strategy.py` (NEW)

**Existing files to reference**:
- `tests/validation/strategies/rustybt/sma_crossover.py` - Pattern reference
- `rustybt/validation/base_strategy.py` - Base class
- `rustybt/validation/decorators.py` - Logging decorators

### Testing Guidance

```python
import pytest
from decimal import Decimal

@pytest.mark.layer_2_signals
class TestMeanReversionStrategy:

    def test_zscore_calculation_accuracy(self):
        """Test z-score formula is correct."""
        prices = [100, 102, 98, 101, 99, 100, 103, 97, 100, 101]
        # Expected: mean=100.1, std_dev≈1.92, z_score for 101 ≈ 0.47

    def test_buy_signal_below_threshold(self):
        """Test BUY signal when z-score < -2."""
        # Price significantly below mean triggers buy

    def test_sell_signal_above_threshold(self):
        """Test SELL signal when z-score > 2."""
        # Price significantly above mean triggers sell

    def test_exit_signal_at_mean(self):
        """Test EXIT signal when z-score returns to 0."""
        # Mean reversion complete triggers exit

    def test_division_by_zero_protection(self):
        """Test handling when std_dev = 0."""
        prices = [100, 100, 100, 100, 100]  # No variance
        # Should return z_score = 0, not raise error

    def test_insufficient_lookback_data(self):
        """Test handling when not enough data for lookback."""
        prices = [100, 101, 102]  # Only 3 bars, need 20
        # Should return neutral signal
```

### References

- [Source: docs/architecture.md#Novel-Pattern-Log-Based-Validation-Architecture]
- [Source: docs/epics/epic-6-initial-strategy-validation-4-strategies.md#Story-6.2]
- [Source: docs/prd.md#FR56-Strategy-Validation]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/6-2-initial-strategy-validation-story-2.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Implementation plan: Create dual Mean Reversion strategies with z-score calculation and edge case handling

### Completion Notes List

- ✅ Implemented rustybt MeanReversionStrategy with rolling z-score calculation
- ✅ Implemented Backtrader MeanReversionStrategy using bt.indicators.SMA and StdDev
- ✅ Both strategies log z-score, mean, std_dev to identical JSONL format
- ✅ Default parameters: lookback_period=20, entry_threshold=2.0, exit_threshold=0.0
- ✅ Position management: -1=short, 0=flat, 1=long with proper entry/exit logic
- ✅ Edge case handling: division by zero, insufficient data, NaN/Inf values
- ✅ 24 unit tests all passing covering both implementations, equivalence, and edge cases
- ✅ 699 total validation tests pass with no regressions

### File List

**New Files:**
- `tests/validation/strategies/rustybt/mean_reversion.py` - rustybt mean reversion strategy
- `tests/validation/strategies/bt_strategies/mean_reversion.py` - Backtrader mean reversion strategy
- `tests/validation/test_mean_reversion_strategy.py` - 24 unit tests for both strategies

**Modified Files:**
- `tests/validation/strategies/rustybt/__init__.py` - Export MeanReversionStrategy
- `tests/validation/strategies/bt_strategies/__init__.py` - Export MeanReversionStrategy

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-28 | Story drafted from Epic 6 specification | SM Agent |
| 2025-11-28 | Implemented dual Mean Reversion strategies and tests | Dev Agent |

## Senior Developer Review (AI)

- **Reviewer**: Antigravity (AI Senior Developer)
- **Date**: 2025-11-29
- **Outcome**: **Approve**
- **Summary**: The implementation of the Mean Reversion strategy in both rustybt and Backtrader frameworks is complete and correct. The code follows the required patterns, uses the correct base classes, and implements identical logic. The test suite is comprehensive and verifies equivalence.

### Key Findings

- **HIGH Severity**: None.
- **MEDIUM Severity**: None.
- **LOW Severity**: None.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | rustybt Mean Reversion implementation exists | IMPLEMENTED | `tests/validation/strategies/rustybt/mean_reversion.py` |
| 2 | Backtrader Mean Reversion implementation exists | IMPLEMENTED | `tests/validation/strategies/bt_strategies/mean_reversion.py` |
| 3 | Strategy audit checklist passed | IMPLEMENTED | `tests/validation/test_mean_reversion_strategy.py` (TestStrategyAuditChecklist) |
| 4 | Z-score edge cases handled | IMPLEMENTED | `tests/validation/test_mean_reversion_strategy.py` (TestEdgeCases) |
| 5 | Unit tests verify z-score calculation logic | IMPLEMENTED | `tests/validation/test_mean_reversion_strategy.py` (24 tests passed) |
| 6 | Log z-score values for signal comparison | IMPLEMENTED | Verified in `test_log_output_format` and `test_log_output_matches_schema` |

**Summary**: 6 of 6 acceptance criteria fully implemented.

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| 1. Create rustybt Mean Reversion strategy | [x] | VERIFIED COMPLETE | `tests/validation/strategies/rustybt/mean_reversion.py` |
| 2. Create Backtrader Mean Reversion strategy | [x] | VERIFIED COMPLETE | `tests/validation/strategies/bt_strategies/mean_reversion.py` |
| 3. Verify strategy equivalence | [x] | VERIFIED COMPLETE | `tests/validation/test_mean_reversion_strategy.py` |
| 4. Handle edge cases | [x] | VERIFIED COMPLETE | `tests/validation/test_mean_reversion_strategy.py` |
| 5. Write unit tests | [x] | VERIFIED COMPLETE | `tests/validation/test_mean_reversion_strategy.py` |
| 6. Validate log output | [x] | VERIFIED COMPLETE | `tests/validation/test_mean_reversion_strategy.py` |

**Summary**: 6 of 6 completed tasks verified.

### Zero-Mock Enforcement

| Check Type | File:Line | Status | Details |
|------------|-----------|--------|---------|
| Hardcoded Returns | N/A | PASS | No hardcoded returns found in production code. |
| Always-Succeeding Validations | N/A | PASS | No dummy validations found. |
| Mock Patterns | N/A | PASS | No mock/stub patterns found in production code. |
| Empty Error Handlers | N/A | PASS | No empty error handlers found. |
| Test Quality | `tests/validation/test_mean_reversion_strategy.py` | PASS | Tests use real framework execution and meaningful assertions. |

**Summary**: ZERO-MOCK STATUS: PASS (0 violations)

### Orphaned Files Enforcement

| File Path | Issue Type | Severity | Suggested Location |
|-----------|------------|----------|--------------------|
| `tests/validation/strategies/rustybt/mean_reversion.py` | None | PASS | Correctly placed. |
| `tests/validation/strategies/bt_strategies/mean_reversion.py` | None | PASS | Correctly placed. |
| `tests/validation/test_mean_reversion_strategy.py` | None | PASS | Correctly placed. |

**Summary**: ORPHAN STATUS: PASS (0 violations)

### Action Items

**Code Changes Required:**
- None.

**Advisory Notes:**
- Note: The implementation correctly handles division by zero when standard deviation is zero (e.g., constant prices).
