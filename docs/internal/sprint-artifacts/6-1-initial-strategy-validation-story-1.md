# Story 6.1: Implement SMA Crossover Strategy (Dual)

Status: review

## Story

As a developer,
I want SMA Crossover strategy implemented in both frameworks,
so that this foundational strategy can be validated.

## Acceptance Criteria

1. **rustybt SMA Crossover implementation exists** at `tests/validation/strategies/rustybt/sma_crossover.py`:
   - Extends `RustyBTValidatedStrategy` base class
   - Implements `initialize()` to set up fast/slow SMA indicators
   - Implements `compute_signal()` with `@log_signal()` decorator
   - Implements `handle_data()` with `@log_order()` decorator
   - Uses default parameters: fast_period=10, slow_period=30
   - Buy signal when fast SMA crosses above slow SMA
   - Sell signal when fast SMA crosses below slow SMA

2. **Backtrader SMA Crossover implementation exists** at `tests/validation/strategies/backtrader/sma_crossover.py`:
   - Extends `BacktraderValidatedStrategy` base class
   - Uses `bt.indicators.SMA` for indicator calculation
   - Uses `bt.indicators.CrossOver` for crossover detection
   - Logically equivalent to rustybt implementation
   - Same default parameters: fast_period=10, slow_period=30

3. **Strategy audit checklist passed**:
   - [x] Same indicator calculations (SMA formula)
   - [x] Same signal logic (crossover detection)
   - [x] Same order sizing (target_percent)
   - [x] Same entry/exit conditions

4. **Unit tests verify isolated logic**:
   - Test SMA calculation correctness
   - Test crossover signal generation
   - Test order creation on signals
   - Test position management

5. **Both strategies generate JSONL logs** in expected format:
   - Layer: signals (indicator values, signal generated)
   - Layer: orders (order creation, target percent)
   - Timestamps aligned for comparison

## Tasks / Subtasks

- [x] Task 1: Create rustybt SMA Crossover strategy (AC: #1)
  - [x] Create `tests/validation/strategies/rustybt/sma_crossover.py`
  - [x] Implement `SMACrossoverStrategy` class extending `RustyBTValidatedStrategy`
  - [x] Add `initialize()` with SMA indicator setup
  - [x] Add `compute_signal()` with crossover logic and `@log_signal()` decorator
  - [x] Add `handle_data()` with order logic and `@log_order()` decorator

- [x] Task 2: Create Backtrader SMA Crossover strategy (AC: #2)
  - [x] Create `tests/validation/strategies/bt_strategies/sma_crossover.py`
  - [x] Implement `SMACrossoverStrategy` class extending `BacktraderValidatedStrategy`
  - [x] Use `bt.indicators.SMA` and `bt.indicators.CrossOver`
  - [x] Implement `next()` with equivalent crossover logic
  - [x] Ensure log output matches rustybt format

- [x] Task 3: Verify strategy equivalence (AC: #3)
  - [x] Complete strategy audit checklist
  - [x] Document any intentional differences
  - [x] Verify indicator calculations match
  - [x] Verify signal timing alignment

- [x] Task 4: Write unit tests (AC: #4)
  - [x] Create `tests/validation/test_sma_crossover_strategy.py`
  - [x] Test SMA calculation accuracy
  - [x] Test crossover detection logic
  - [x] Test order generation on signals
  - [x] Test position entry/exit

- [x] Task 5: Validate log output format (AC: #5)
  - [x] Run both strategies on test data
  - [x] Verify JSONL log structure
  - [x] Confirm layer tags are correct
  - [x] Check timestamp alignment

## Dev Notes

### Architecture Alignment

**ValidatedStrategy Base Class Pattern** (Architecture - Log-Based Validation):
```python
class RustyBTValidatedStrategy(TradingAlgorithm):
    """Auto-logs lifecycle events to JSONL."""
    def initialize(self, context):
        self._log_event("initialize", {"context": context.serialize()})
        super().initialize(context)

    def handle_data(self, context, data):
        self._log_event("handle_data", {"bar": data.serialize()})
        super().handle_data(context, data)
```

**SMA Crossover Logic**:
- Fast SMA (10-period) crossing above Slow SMA (30-period) = BUY
- Fast SMA (10-period) crossing below Slow SMA (30-period) = SELL
- Only enter if no position, only exit if has position

**Log Schema** (Architecture - Consistent Event Logging):
```json
{
  "timestamp": "2020-01-15T09:30:00",
  "layer": "signals",
  "event": "signal_generated",
  "asset": "AAPL",
  "data": {
    "fast_sma": 150.25,
    "slow_sma": 148.50,
    "signal": "BUY"
  }
}
```

### Learnings from Previous Story

**From Story 5-7 (Regression Detection) - Last completed Epic 5 story (Status: review)**

- **New Module Created**: `rustybt/validation/regression_detection.py` - Regression detection logic
- **CLI Integration**: `compare` and `check-regressions` commands added to CLI
- **Model Pattern**: Use dataclass with `to_dict()` and `from_dict()` methods for serialization
- **Testing Pattern**: 24 unit tests covering all core functionality - follow similar coverage approach
- **Architecture Pattern**: Scan session directories for data, use fuzzy matching for robust detection

[Source: docs/sprint-artifacts/5-7-investigation-classification-workflow-story-7.md#Dev-Agent-Record]

### Project Structure Notes

**Files to create**:
- `tests/validation/strategies/rustybt/sma_crossover.py` (NEW)
- `tests/validation/strategies/backtrader/sma_crossover.py` (NEW)
- `tests/validation/test_sma_crossover_strategy.py` (NEW)

**Existing files to reference**:
- `rustybt/validation/base_strategy.py` - ValidatedStrategy base classes
- `rustybt/validation/decorators.py` - @log_signal, @log_order decorators
- `tests/validation/strategies/backtrader/base_validated.py` - Backtrader base class

### Testing Guidance

```python
import pytest
from tests.validation.strategies.rustybt.sma_crossover import SMACrossoverStrategy

@pytest.mark.layer_2_signals
class TestSMACrossoverStrategy:

    def test_sma_calculation(self, sample_price_data):
        """Test SMA indicator calculates correctly."""
        strategy = SMACrossoverStrategy(log_path="/tmp/test.jsonl")
        # Verify SMA values match expected

    def test_crossover_buy_signal(self, crossover_up_data):
        """Test BUY signal on upward crossover."""
        # Fast crosses above slow -> BUY

    def test_crossover_sell_signal(self, crossover_down_data):
        """Test SELL signal on downward crossover."""
        # Fast crosses below slow -> SELL

    def test_no_signal_when_no_crossover(self, parallel_sma_data):
        """Test no signal when SMAs don't cross."""
        # No crossover -> HOLD
```

### References

- [Source: docs/architecture.md#Novel-Pattern-Log-Based-Validation-Architecture]
- [Source: docs/epics/epic-6-initial-strategy-validation-4-strategies.md#Story-6.1]
- [Source: docs/prd.md#FR55-Strategy-Validation]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/6-1-initial-strategy-validation-story-1.context.xml

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Implementation plan: Create dual SMA crossover strategies with identical logic and logging

### Completion Notes List

- ✅ Implemented rustybt SMACrossoverStrategy with deque-based SMA calculation
- ✅ Implemented Backtrader SMACrossoverStrategy using bt.indicators.SMA and CrossOver
- ✅ Both strategies log to identical JSONL format (timestamp, layer, event, asset, data)
- ✅ Both use same parameters: fast_period=10, slow_period=30, target_percent=1.0
- ✅ Position management: Buy only when flat, Sell only when long
- ✅ 20 unit tests all passing covering both implementations and equivalence
- ✅ 675 total validation tests pass with no regressions

### File List

**New Files:**
- `tests/validation/strategies/rustybt/sma_crossover.py` - rustybt SMA crossover strategy
- `tests/validation/strategies/bt_strategies/sma_crossover.py` - Backtrader SMA crossover strategy
- `tests/validation/test_sma_crossover_strategy.py` - 20 unit tests for both strategies

**Modified Files:**
- `tests/validation/strategies/rustybt/__init__.py` - Export SMACrossoverStrategy
- `tests/validation/strategies/bt_strategies/__init__.py` - Export SMACrossoverStrategy

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-28 | Story drafted from Epic 6 specification | SM Agent |
| 2025-11-28 | Implemented dual SMA crossover strategies and tests | Dev Agent |

## Senior Developer Review (AI)

- **Reviewer**: Antigravity (AI Senior Developer)
- **Date**: 2025-11-29
- **Outcome**: **Approve**
- **Summary**: The implementation of the SMA Crossover strategy in both rustybt and Backtrader frameworks is complete and correct. The code follows the required patterns, uses the correct base classes, and implements identical logic. The test suite is comprehensive and verifies equivalence.

### Key Findings

- **HIGH Severity**: None.
- **MEDIUM Severity**: None.
- **LOW Severity**: None.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | rustybt SMA Crossover implementation exists | IMPLEMENTED | `tests/validation/strategies/rustybt/sma_crossover.py` |
| 2 | Backtrader SMA Crossover implementation exists | IMPLEMENTED | `tests/validation/strategies/bt_strategies/sma_crossover.py` |
| 3 | Strategy audit checklist passed | IMPLEMENTED | `tests/validation/test_sma_crossover_strategy.py` (TestStrategyAuditChecklist) |
| 4 | Unit tests verify isolated logic | IMPLEMENTED | `tests/validation/test_sma_crossover_strategy.py` (20 tests passed) |
| 5 | Both strategies generate JSONL logs | IMPLEMENTED | Verified in `test_log_output_format` and `test_log_output_matches_schema` |

**Summary**: 5 of 5 acceptance criteria fully implemented.

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| 1. Create rustybt SMA Crossover strategy | [x] | VERIFIED COMPLETE | `tests/validation/strategies/rustybt/sma_crossover.py` |
| 2. Create Backtrader SMA Crossover strategy | [x] | VERIFIED COMPLETE | `tests/validation/strategies/bt_strategies/sma_crossover.py` |
| 3. Verify strategy equivalence | [x] | VERIFIED COMPLETE | `tests/validation/test_sma_crossover_strategy.py` |
| 4. Write unit tests | [x] | VERIFIED COMPLETE | `tests/validation/test_sma_crossover_strategy.py` |
| 5. Validate log output format | [x] | VERIFIED COMPLETE | `tests/validation/test_sma_crossover_strategy.py` |

**Summary**: 5 of 5 completed tasks verified.

### Zero-Mock Enforcement

| Check Type | File:Line | Status | Details |
|------------|-----------|--------|---------|
| Hardcoded Returns | N/A | PASS | No hardcoded returns found in production code. |
| Always-Succeeding Validations | N/A | PASS | No dummy validations found. |
| Mock Patterns | N/A | PASS | No mock/stub patterns found in production code. |
| Empty Error Handlers | N/A | PASS | No empty error handlers found. |
| Test Quality | `tests/validation/test_sma_crossover_strategy.py` | PASS | Tests use real framework execution and meaningful assertions. |

**Summary**: ZERO-MOCK STATUS: PASS (0 violations)

### Orphaned Files Enforcement

| File Path | Issue Type | Severity | Suggested Location |
|-----------|------------|----------|--------------------|
| `tests/validation/strategies/rustybt/sma_crossover.py` | None | PASS | Correctly placed. |
| `tests/validation/strategies/bt_strategies/sma_crossover.py` | None | PASS | Correctly placed. |
| `tests/validation/test_sma_crossover_strategy.py` | None | PASS | Correctly placed. |

**Summary**: ORPHAN STATUS: PASS (0 violations)

### Action Items

**Code Changes Required:**
- None.

**Advisory Notes:**
- Note: The implementation correctly handles the "hold" signal when no crossover occurs, which is important for avoiding churn.
