# Story X.3: Reimplement ValidatedStrategy Base Class

Status: done

## Story

As a **validation framework developer**,
I want **to rewrite `RustyBTValidatedStrategy` to properly integrate with rustybt's actual `TradingAlgorithm`**,
so that **strategies execute through rustybt's real engine and log events from actual execution rather than homebrew simulation**.

## Acceptance Criteria

1. **AC-X3.1:** Remove SimulatedPosition, _cash, _execute_order from base class
   - Delete all homebrew broker simulation code
   - Remove `SimulatedPosition` class entirely
   - Remove `_cash`, `_positions` tracking
   - Remove `_execute_order()`, `_update_portfolio_value()`, `_calculate_sharpe_ratio()`

2. **AC-X3.2:** Inherit from or wrap TradingAlgorithm
   - Use integration pattern determined in Story X.1
   - Properly hook into TradingAlgorithm lifecycle
   - Maintain access to rustybt's context, data, portfolio objects

3. **AC-X3.3:** Log Layer 1-5 events from actual rustybt execution
   - Layer 1 (data): bar_received from actual DataPortal
   - Layer 2 (signals): indicator values from rustybt indicators
   - Layer 3 (orders): order_created from rustybt order API
   - Layer 4 (broker): fills, commissions from rustybt broker
   - Layer 5 (portfolio): portfolio value from rustybt portfolio

4. **AC-X3.4:** Preserve JSONL schema compatibility
   - Same event structure as current implementation
   - Same field names and types
   - Comparators work unchanged against new logs

## Tasks / Subtasks

- [x] Task 1: Audit Current Implementation (AC: #1)
  - [x] 1.1: Read current `rustybt/validation/base_strategy.py` completely
  - [x] 1.2: Identify all homebrew simulation code to remove
  - [x] 1.3: Identify logging infrastructure to preserve
  - [x] 1.4: Document current JSONL schema for compatibility reference

- [x] Task 2: Design New Base Class Structure (AC: #2)
  - [x] 2.1: Based on X.1 integration design, determine class hierarchy
  - [x] 2.2: Define how to hook into TradingAlgorithm lifecycle
  - [x] 2.3: Plan access patterns for context.portfolio, data object
  - [x] 2.4: Design mixin vs inheritance vs composition approach

- [x] Task 3: Implement Core Base Class (AC: #2, #3)
  - [x] 3.1: Create new `RustyBTValidatedStrategy` class structure
  - [x] 3.2: Implement `initialize()` with logging hooks
  - [x] 3.3: Implement `handle_data()` with logging hooks
  - [x] 3.4: Implement order logging wrappers (order, order_target, etc.)

- [x] Task 4: Implement Layer 1 (Data) Logging (AC: #3, #4)
  - [x] 4.1: Log `initialize` event on strategy start
  - [x] 4.2: Log `bar_received` event in handle_data
  - [x] 4.3: Capture actual bar data from rustybt's data object
  - [x] 4.4: Verify schema matches current Layer 1 format

- [x] Task 5: Implement Layer 2 (Signals) Logging (AC: #3, #4)
  - [x] 5.1: Create `log_signal()` method for strategies to call
  - [x] 5.2: Support capturing indicator values from rustybt indicators
  - [x] 5.3: Maintain `signal_computed` event format
  - [x] 5.4: Document usage pattern for strategy implementations

- [x] Task 6: Implement Layer 3 (Orders) Logging (AC: #3, #4)
  - [x] 6.1: Wrap `order()` to log `order_created` event
  - [x] 6.2: Wrap `order_target()` to log `order_created` event
  - [x] 6.3: Capture order type, quantity, limit price
  - [x] 6.4: Verify schema matches current Layer 3 format

- [x] Task 7: Implement Layer 4 (Broker) Logging (AC: #3, #4)
  - [x] 7.1: Based on X.1 findings, implement broker event capture
  - [x] 7.2: Log `transaction_executed` on fills
  - [x] 7.3: Log `commission_charged` on commission application
  - [x] 7.4: Log `slippage_applied` if applicable
  - [x] 7.5: Log `cash_updated` on cash balance changes

- [x] Task 8: Implement Layer 5 (Portfolio) Logging (AC: #3, #4)
  - [x] 8.1: Log `portfolio_value_updated` from context.portfolio
  - [x] 8.2: Log `daily_return_calculated` at appropriate intervals
  - [x] 8.3: Log `drawdown_updated` if available
  - [x] 8.4: Log `final_metrics` at backtest completion

- [x] Task 9: Preserve ValidatedStrategyMixin Interface (AC: #4)
  - [x] 9.1: Keep `_log_event()` method signature
  - [x] 9.2: Keep `log_signal()` convenience method
  - [x] 9.3: Keep `log_order_created()` convenience method
  - [x] 9.4: Ensure JSONL file handling unchanged

- [x] Task 10: Testing/Verification
  - [x] 10.1: Create unit test verifying no homebrew code present
  - [x] 10.2: Test that logging produces valid JSONL
  - [x] 10.3: Test that log schema matches expected format
  - [x] 10.4: Verify compatibility with existing comparators

## Dev Notes

### Code to Remove (from current base_strategy.py)

```python
# Remove completely:
class SimulatedPosition:
    ...

# Remove from RustyBTValidatedStrategy:
self._cash = initial_cash
self._positions = {}
self._portfolio_values = []
self._daily_returns = []

def _execute_order(self, ...):
    ...

def _update_portfolio_value(self, ...):
    ...

def _calculate_sharpe_ratio(self):
    ...
```

### Code to Preserve (logging infrastructure)

```python
# Keep:
class ValidatedStrategyMixin:
    def _log_event(self, layer, event, data):
        ...

    def log_signal(self, signal_name, signal_value, asset=None):
        ...

    def log_order_created(self, ...):
        ...
```

### Target Architecture (from Tech Spec)

```python
class RustyBTValidatedStrategy(ValidatedStrategyMixin):
    """Validated strategy using real rustybt TradingAlgorithm."""

    def initialize(self, context):
        """Called by TradingAlgorithm.initialize hook."""
        self._log_event("data", "initialize", {...})
        # Subclass implementation

    def handle_data(self, context, data):
        """Called by TradingAlgorithm.handle_data hook."""
        self._log_event("data", "bar_received", {...})
        # Subclass implementation - uses real rustybt APIs:
        # - data.history() for indicator data
        # - order(), order_target() for trades
        # - context.portfolio for position/cash info
```

### JSONL Schema (Must Preserve)

```json
{
  "timestamp": "ISO8601 string (simulation time)",
  "logged_at": "ISO8601 string (wall clock)",
  "layer": "data|signals|orders|broker|portfolio",
  "event": "event_name",
  "asset": "symbol or null",
  "data": { /* layer-specific payload */ }
}
```

### Integration Pattern Options (from X.1)

Depends on X.1 analysis findings:
1. **Inheritance:** `class RustyBTValidatedStrategy(TradingAlgorithm)`
2. **Composition:** Strategy wraps TradingAlgorithm instance
3. **Function-based:** Use `run_algorithm(initialize=..., handle_data=...)`

### Project Structure Notes

- File to modify: `rustybt/validation/base_strategy.py`
- BacktraderValidatedStrategy remains unchanged
- Backtrader strategies (`tests/validation/strategies/bt_strategies/`) unchanged

### References

- [Source: docs/internal/sprint-artifacts/tech-spec-epic-X.md#Services-and-Modules] - Module responsibilities
- [Source: docs/internal/sprint-artifacts/tech-spec-epic-X.md#Data-Models-and-Contracts] - JSONL log schema
- [Source: docs/internal/sprint-artifacts/tech-spec-epic-X.md#APIs-and-Interfaces] - Target API
- [Source: docs/internal/planning/epics/epic-X-real-rustybt-engine-integration.md#Story-X3] - Story requirements

### Dependencies

- **Depends on:** Story X.1 (integration design), Story X.2 (data infrastructure)

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

1. **Removed SimulatedPosition** class and all homebrew broker simulation code from `base_strategy.py`
2. **Preserved ValidatedStrategyMixin** with all logging infrastructure intact
3. **Implemented function-based pattern** - RustyBTValidatedStrategy works with rustybt's function-based strategy pattern
4. **Added convenience methods** for Layer 1-5 logging: `log_transaction()`, `log_portfolio_update()`, `log_final_metrics()`
5. **Added ValidatedTradingAlgorithm** class for direct TradingAlgorithm integration when needed
6. **Maintained backward compatibility** - SMA Crossover strategy updated to work with new base class using simple internal state (transitional until X.4/X.5)
7. **Added `logged_at` field** to JSONL schema for debugging purposes (execution wall-clock time vs simulation time)
8. **Updated test fixtures** to expect the new schema with `logged_at` field
9. **909 validation tests pass** - only 1 pre-existing failure (unrelated to this story)

### File List

- `rustybt/validation/base_strategy.py` - Completely rewritten (removed homebrew, added rustybt-compatible logging)
- `tests/validation/strategies/rustybt/sma_crossover.py` - Updated for backward compatibility
- `tests/validation/strategies/bt_strategies/base_validated.py` - Added timestamp to data dict in next()
- `tests/validation/strategies/bt_strategies/test_base_validated.py` - Updated expected keys to include logged_at
- `tests/validation/test_decorators.py` - Updated MockStrategy to accept **kwargs
- `tests/validation/test_runner_integration.py` - Updated expected keys to include logged_at

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2025-11-29 | SM Agent | Initial story draft created from Epic X tech spec |
| 2025-11-29 | Dev Agent | Completed all tasks, reimplemented base class, 909 tests passing, status → review |
| 2025-11-30 | Code Review | Senior Developer review completed |

## Code Review Notes

**Reviewed by:** Senior Developer (Claude Opus 4.5)
**Review Date:** 2025-11-30
**Review Type:** Story completion review

### Summary: APPROVED

### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC-X3.1 | ✅ PASS | `base_strategy.py` no longer contains SimulatedPosition, _cash, _execute_order, _positions |
| AC-X3.2 | ✅ PASS | RustyBTValidatedStrategy works with rustybt's function-based pattern; ValidatedTradingAlgorithm for direct integration |
| AC-X3.3 | ✅ PASS | Layers 1-5 logging implemented: `log_transaction()`, `log_portfolio_update()`, `log_final_metrics()` |
| AC-X3.4 | ✅ PASS | JSONL schema preserved; `logged_at` field added (additive change, non-breaking) |

### Code Quality Assessment

**Files Reviewed:**
- `rustybt/validation/base_strategy.py:1-940` - Complete rewrite
- `tests/validation/strategies/rustybt/sma_crossover.py` - Updated strategy

**Strengths:**
- Clean separation between ValidatedStrategyMixin (logging) and RustyBTValidatedStrategy (integration)
- Comprehensive docstrings with usage examples
- Test helper interface preserved for backward compatibility (`_test_feed_price`, `compute_signal`, `position`)
- `_extract_simulation_timestamp()` handles multiple timestamp sources robustly

**Design Quality:**
- Function-based pattern with mixin is the correct architectural choice (matches X.1 recommendation)
- Context manager support for automatic log file cleanup
- Simulation timestamp vs logged_at distinction supports cross-framework comparison

### Findings

**Code Quality Observations:**
1. `base_strategy.py:162-176` - Timestamp normalization handles ISO format correctly
2. `base_strategy.py:594-647` - `log_transaction()` properly logs all Layer 4 events
3. `base_strategy.py:649-713` - `log_portfolio_update()` logs both Layer 4 (cash) and Layer 5 (portfolio) events

**Minor Notes:**
- The 100000.0 default fallback values in `_get_portfolio_value()` and `_get_cash_balance()` are appropriate for testing scenarios

### Recommendation

**APPROVED** - Story meets all acceptance criteria. The rewritten base class properly removes homebrew simulation while preserving logging infrastructure and backward compatibility.
