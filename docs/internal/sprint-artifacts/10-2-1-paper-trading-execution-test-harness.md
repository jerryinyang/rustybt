# Story 10.2.1: Paper Trading Execution Test Harness

Status: done

## Story

As a **developer**,
I want **an end-to-end test harness for paper trading execution**,
So that **I can validate strategy execution, order fills, and position tracking**.

## Acceptance Criteria

1. **AC1:** A test harness exists that can execute trading strategies in paper trading mode via `PaperBroker`:
   - Test strategy generates known signals
   - Orders are submitted through the paper broker
   - Strategy execution completes without errors

2. **AC2:** Order fills are simulated according to configurable fill models:
   - **Immediate model**: Fill occurs at current simulated price within same tick
   - **Delayed model**: Fill occurs after configurable delay (default 100ms)
   - Fill model is selectable via test configuration

3. **AC3:** Positions are tracked accurately:
   - Entry price matches fill price
   - Position size matches order quantity
   - Direction (long/short) is correct based on order side

4. **AC4:** PnL calculations match expected values:
   - Unrealized PnL computed correctly for open positions
   - Realized PnL computed correctly on position close
   - PnL uses Decimal precision for financial accuracy

5. **AC5:** Order state transitions follow expected lifecycle:
   - `pending → submitted → filled` for successful orders
   - `pending → submitted → cancelled` for cancelled orders
   - All transitions are logged for audit

6. **AC6:** Tests cover both long and short positions with various scenarios

## Tasks / Subtasks

- [x] Task 1: Create paper trading test infrastructure (AC: #1)
  - [x] Create `tests/live/paper/` directory
  - [x] Create `tests/live/paper/__init__.py`
  - [x] Create `tests/live/paper/conftest.py` with fixtures
  - [x] Create deterministic test strategy class

- [x] Task 2: Implement test strategy with known signals (AC: #1)
  - [x] Create `TestStrategy` class in conftest or test file
  - [x] Generate predictable BUY/SELL signals at known intervals
  - [x] Support configurable signal patterns

- [x] Task 3: Implement fill model tests (AC: #2)
  - [x] Test immediate fill model (market order → instant fill)
  - [x] Test delayed fill model (market order → fill after delay)
  - [x] Verify fill price matches expected simulated price
  - [x] Verify fill timing matches configured delay

- [x] Task 4: Implement position tracking tests (AC: #3)
  - [x] Test long position creation
  - [x] Test short position creation
  - [x] Verify entry price accuracy
  - [x] Verify position size accuracy
  - [x] Test position updates on additional orders

- [x] Task 5: Implement PnL calculation tests (AC: #4)
  - [x] Test unrealized PnL for open long position
  - [x] Test unrealized PnL for open short position
  - [x] Test realized PnL on position close
  - [x] Verify Decimal precision (no floating point errors)
  - [x] Test PnL with multiple partial closes

- [x] Task 6: Implement order lifecycle tests (AC: #5)
  - [x] Test successful order flow: pending → submitted → filled
  - [x] Test cancelled order flow: pending → submitted → cancelled
  - [x] Test timeout scenarios
  - [x] Verify all transitions logged

- [x] Task 7: Create comprehensive test scenarios (AC: #6)
  - [x] Test: Long entry, price up, long exit (profit)
  - [x] Test: Long entry, price down, long exit (loss)
  - [x] Test: Short entry, price down, short exit (profit)
  - [x] Test: Short entry, price up, short exit (loss)
  - [x] Test: Multiple concurrent positions

- [x] Task 8: Write test file `test_paper_execution.py` (AC: #1-6)
  - [x] Combine all tests into organized test file
  - [x] Add appropriate markers and fixtures
  - [x] Verify all tests pass

## Dev Notes

### Test Strategy Design

The test strategy should be deterministic to ensure reproducible results:

```python
class TestStrategy:
    """Deterministic test strategy with known signal patterns."""

    def __init__(self, signal_pattern: list[tuple[int, str]]):
        """
        Args:
            signal_pattern: List of (bar_index, signal_type) tuples
                           e.g., [(5, "BUY"), (10, "SELL")]
        """
        self.signal_pattern = signal_pattern

    def on_bar(self, bar_index: int, bar_data: dict) -> str | None:
        for idx, signal in self.signal_pattern:
            if bar_index == idx:
                return signal
        return None
```

### Fill Model Configuration

From the PRD, fill models should be configurable:

```python
@dataclass
class FillModelConfig:
    model: Literal["immediate", "delayed"] = "immediate"
    delay_ms: int = 100  # Only used for delayed model
    partial_fill_probability: float = 0.0  # Future enhancement
```

### PnL Calculation Verification

From NFR requirements, all financial calculations use Decimal:

```python
from decimal import Decimal

# Long position PnL
unrealized_pnl = (current_price - entry_price) * position_size

# Short position PnL
unrealized_pnl = (entry_price - current_price) * abs(position_size)
```

### Architecture Patterns and Constraints

From Tech Spec:
- Paper trading overhead must be < 10ms vs live path (NFR3)
- Paper trading must produce deterministic results (NFR11)
- All order state transitions logged for audit (NFR10)

### Prerequisites

- Epic 10.1 must be complete (audit findings resolved)
- PaperBroker from `rustybt/live/brokers/paper_broker.py` must be functional

### References

- [Source: docs/internal/planning/prd-epic-10.md#Paper Trading Validation]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.2.1]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.2.1]

## Dev Agent Record

### Context Reference

- `docs/internal/sprint-artifacts/10-2-1-paper-trading-execution-test-harness.context.xml`

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 34 tests in `test_paper_execution.py` passed on 2025-12-08
- All 82 tests in `tests/live/paper/` passed (including persistence, stability, parity tests)

### Completion Notes List

**Summary:** Story 10.2.1 was already fully implemented with comprehensive test coverage. All 8 tasks were verified complete:

1. **Test Infrastructure:** `tests/live/paper/` directory exists with `__init__.py`, `conftest.py` containing fixtures and test strategies
2. **Deterministic Strategy:** `DeterministicStrategy` class with `SignalPattern` dataclass for predictable signal generation at specific bar indices
3. **Fill Models:** Tests for immediate (1ms latency) and delayed (100ms latency) fill models with jitter support
4. **Position Tracking:** Tests for long/short position creation, entry price accuracy, size accuracy (including fractional), direction correctness
5. **PnL Calculations:** Tests for unrealized PnL (long/short), realized PnL on close, Decimal precision verification, partial closes
6. **Order Lifecycle:** Tests for pending → submitted → filled flow, cancelled flow, timeout scenarios, audit logging via transactions
7. **Trading Scenarios:** Tests for all profit/loss combinations (long up/down, short up/down), multiple concurrent positions, rapid buy-sell cycles
8. **Test Organization:** All tests organized by AC in `test_paper_execution.py` with proper markers and fixtures

**Additional Fixtures Implemented:**
- `paper_broker_immediate`: Minimal latency for immediate fills
- `paper_broker_delayed`: 100ms latency with 20% jitter
- `paper_broker_with_costs`: Realistic commission and slippage
- `execute_strategy_on_broker`: Helper for executing test strategies

### File List

| File | Action | Notes |
|------|--------|-------|
| tests/live/paper/__init__.py | existing | Package init |
| tests/live/paper/conftest.py | existing | Test fixtures and helpers |
| tests/live/paper/test_paper_execution.py | existing | Main execution tests (34 tests) |
| tests/live/paper/test_paper_persistence.py | existing | State persistence tests |
| tests/live/paper/test_paper_stability.py | existing | Long-running stability tests |
| tests/live/paper/test_paper_parity.py | existing | Live parity verification |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-08 | Story verified complete - all tests passing | Dev Agent |
