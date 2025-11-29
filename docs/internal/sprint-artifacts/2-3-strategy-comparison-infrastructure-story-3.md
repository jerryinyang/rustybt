# Story 2.3: Create Log Event Decorators for Custom Logic

Status: done

## Story

As a developer,
I want decorators to log custom strategy logic,
so that strategies can log signals, orders, and portfolio events without boilerplate.

## Acceptance Criteria

1. **@log_signal decorator implemented** - `rustybt/validation/decorators.py`:
   - Logs signal computation results to "signals" layer
   - Captures method name, return value, and arguments
   - Works with both rustybt and Backtrader base classes

2. **@log_order decorator implemented**:
   - Logs order creation to "orders" layer
   - Captures order type, asset, quantity, limit price
   - Handles None returns gracefully

3. **@log_portfolio decorator implemented**:
   - Logs portfolio state to "portfolio" layer
   - Captures portfolio value, cash, positions
   - Works after any portfolio-modifying operation

4. **Decorators preserve method metadata**:
   - Use `functools.wraps` to preserve `__name__`, `__doc__`
   - Method signature preserved for introspection

5. **Decorators handle exceptions gracefully**:
   - Log failure event before re-raising exception
   - Include exception type and message in log
   - Don't suppress or modify exceptions

6. **Unit tests demonstrate decorator usage**:
   - Test each decorator with sample strategies
   - Test decorator chaining
   - Test exception handling
   - Test metadata preservation

## Tasks / Subtasks

- [x] Task 1: Create decorators.py module (AC: #1, #2, #3)
  - [x] Create `rustybt/validation/decorators.py`
  - [x] Import functools, typing
  - [x] Add module docstring

- [x] Task 2: Implement @log_signal decorator (AC: #1, #4, #5)
  - [x] Define `log_signal(layer: str = "signals")` decorator factory
  - [x] Use `functools.wraps` for metadata preservation
  - [x] Call method and capture return value
  - [x] Log: signal_name, signal_value, args, kwargs
  - [x] Handle exceptions with failure logging
  - [x] Re-raise any exceptions

- [x] Task 3: Implement @log_order decorator (AC: #2, #4, #5)
  - [x] Define `log_order(layer: str = "orders")` decorator factory
  - [x] Use `functools.wraps` for metadata preservation
  - [x] Call method and capture order object
  - [x] Extract order_type, asset, quantity, limit_price (with fallbacks)
  - [x] Handle None returns (no order created)
  - [x] Handle exceptions with failure logging

- [x] Task 4: Implement @log_portfolio decorator (AC: #3, #4, #5)
  - [x] Define `log_portfolio(layer: str = "portfolio")` decorator factory
  - [x] Use `functools.wraps` for metadata preservation
  - [x] Call method first
  - [x] Access self.portfolio or self.broker for state (framework-agnostic)
  - [x] Log: portfolio_value, cash, positions dict
  - [x] Handle exceptions with failure logging

- [x] Task 5: Write unit tests (AC: #6)
  - [x] Create `tests/validation/test_decorators.py`
  - [x] Test @log_signal with mock strategy
  - [x] Test @log_order with mock strategy
  - [x] Test @log_portfolio with mock strategy
  - [x] Test decorator chaining (multiple decorators)
  - [x] Test exception handling (log + re-raise)
  - [x] Test metadata preservation (__name__, __doc__)
  - [x] Test integration with RustyBTValidatedStrategy

- [x] Task 6: Create example usage in documentation
  - [x] Add docstring examples to each decorator
  - [x] Show usage in ValidatedStrategy subclass
  - [x] Document direct _log_event() alternative

## Dev Notes

### Learnings from Previous Story

**From Story 2-2 (Status: drafted)**

- **BacktraderValidatedStrategy Created**: Base class at `tests/validation/strategies/backtrader/base_validated.py`
- **_log_event() Method**: Both base classes have identical `_log_event(layer, event, data)` interface
- **Log Schema**: JSON with timestamp, layer, event, asset, data fields

**Decorators require _log_event()** (from Story 2.1, 2.2):
- Both base classes implement `_log_event(layer, event, data)`
- Decorators call `self._log_event()` internally
- Decorators are optional - strategies can call `_log_event()` directly

[Source: docs/sprint-artifacts/2-1-strategy-comparison-infrastructure-story-1.md]
[Source: docs/sprint-artifacts/2-2-strategy-comparison-infrastructure-story-2.md]

### Architecture Alignment

**Decorator Pattern** (Architecture pg 163-179):
- `@log_event` decorator for custom logic
- Balance of automation and flexibility
- Optional - strategies can use direct `_log_event()` calls

**Implementation Requirements**:
- Use `functools.wraps` to preserve method metadata
- Convert Decimal/float values consistently in logs
- Handle None returns gracefully
- Decorators should be framework-agnostic

### Implementation Pattern

```python
from functools import wraps
from typing import Callable, TypeVar, Any, Optional

F = TypeVar('F', bound=Callable[..., Any])

def log_signal(layer: str = "signals") -> Callable[[F], F]:
    """Decorator to log signal computation results.

    Example:
        @log_signal()
        def compute_rsi(self, period: int) -> float:
            return calculate_rsi(self.data, period)
    """
    def decorator(method: F) -> F:
        @wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                result = method(self, *args, **kwargs)
                self._log_event(layer, "signal_computed", {
                    "signal_name": method.__name__,
                    "signal_value": result,
                    "args": str(args),
                })
                return result
            except Exception as e:
                self._log_event(layer, "signal_failed", {
                    "signal_name": method.__name__,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                })
                raise
        return wrapper  # type: ignore
    return decorator


def log_order(layer: str = "orders") -> Callable[[F], F]:
    """Decorator to log order creation.

    Example:
        @log_order()
        def place_buy_order(self, asset: str, quantity: int) -> Order:
            return self.order(asset, quantity)
    """
    def decorator(method: F) -> F:
        @wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                order = method(self, *args, **kwargs)
                if order is not None:
                    self._log_event(layer, "order_created", {
                        "order_type": type(order).__name__,
                        "asset": str(getattr(order, 'asset', None)),
                        "quantity": float(getattr(order, 'quantity', 0)),
                        "limit_price": float(getattr(order, 'limit_price', 0))
                            if hasattr(order, 'limit_price') else None,
                    })
                return order
            except Exception as e:
                self._log_event(layer, "order_failed", {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                })
                raise
        return wrapper  # type: ignore
    return decorator


def log_portfolio(layer: str = "portfolio") -> Callable[[F], F]:
    """Decorator to log portfolio state after method execution.

    Example:
        @log_portfolio()
        def rebalance(self) -> None:
            # Rebalancing logic
            pass
    """
    def decorator(method: F) -> F:
        @wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                result = method(self, *args, **kwargs)
                self._log_event(layer, "portfolio_updated", {
                    "portfolio_value": float(self.portfolio.portfolio_value),
                    "cash": float(self.portfolio.cash),
                    "positions": {
                        str(k): float(v.amount)
                        for k, v in self.portfolio.positions.items()
                    },
                })
                return result
            except Exception as e:
                self._log_event(layer, "portfolio_update_failed", {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                })
                raise
        return wrapper  # type: ignore
    return decorator
```

### Usage Examples

**In rustybt strategy**:
```python
class MyStrategy(RustyBTValidatedStrategy):
    @log_signal()
    def compute_moving_average(self, period: int) -> float:
        return self.data.history(self.data.current, "close", period).mean()

    @log_order()
    def place_market_order(self, asset, quantity):
        return self.order(asset, quantity)

    @log_portfolio()
    def rebalance_portfolio(self):
        # Rebalancing logic
        pass
```

**In Backtrader strategy**:
```python
class MyStrategy(BacktraderValidatedStrategy):
    @log_signal()
    def compute_rsi(self) -> float:
        return bt.indicators.RSI(self.data, period=14)[0]

    @log_order()
    def place_buy(self):
        return self.buy()
```

### Project Structure Notes

**Files to create**:
- `rustybt/validation/decorators.py` (NEW - main implementation)
- `tests/validation/test_decorators.py` (NEW - unit tests)

**Files to modify**:
- `rustybt/validation/__init__.py` (MODIFIED - export decorators)

**Dependencies**: No new dependencies (uses Python stdlib: functools, typing)

### Testing Guidance

**Mock strategy for testing**:
```python
class MockStrategy:
    """Mock strategy with _log_event for testing decorators."""
    def __init__(self):
        self.logged_events = []

    def _log_event(self, layer: str, event: str, data: dict) -> None:
        self.logged_events.append({"layer": layer, "event": event, "data": data})

    @log_signal()
    def compute_signal(self) -> float:
        return 42.0

    @log_order()
    def place_order(self):
        return MockOrder()

    @log_portfolio()
    def update_portfolio(self):
        pass

    @property
    def portfolio(self):
        return MockPortfolio()
```

### References

- [Source: docs/architecture.md - Decorator Pattern (pg 163-179)]
- [Source: docs/epics.md - Story 2.3 specification]
- [Source: docs/sprint-artifacts/2-1-strategy-comparison-infrastructure-story-1.md]
- [Source: docs/sprint-artifacts/2-2-strategy-comparison-infrastructure-story-2.md]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/2-3-strategy-comparison-infrastructure-story-3.context.xml`

### Agent Model Used

- Claude Opus 4.5

### Debug Log References

- All 22 tests pass on first run
- Decorators are framework-agnostic, working with both rustybt and Backtrader base classes
- Helper functions added for safe serialization of arguments and position values

### Completion Notes List

1. **@log_signal Decorator**: Logs signal computations with method name, return value, args/kwargs
2. **@log_order Decorator**: Logs order creation with type, asset, quantity, limit price; handles None returns
3. **@log_portfolio Decorator**: Logs portfolio state (value, cash, positions) after method execution
4. **Exception Handling**: All decorators log failure events before re-raising exceptions
5. **Metadata Preservation**: All decorators use `functools.wraps` to preserve `__name__`, `__doc__`
6. **Framework-Agnostic**: Decorators work with any class that has `_log_event()` method
7. **Comprehensive Tests**: 22 unit tests covering all acceptance criteria

### File List

**Created:**
- `rustybt/validation/decorators.py` - Decorator implementations
- `tests/validation/test_decorators.py` - 22 unit tests

**Modified:**
- `rustybt/validation/__init__.py` - Added decorator exports

---

## Review Section

### Code Review Summary (2025-11-26)

**Reviewer:** Senior Developer (Code Review Workflow)
**Status:** ✅ **APPROVED**

#### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC1: @log_signal decorator | ✅ PASS | `rustybt/validation/decorators.py:46-110` - Logs to signals layer, captures return value |
| AC2: @log_order decorator | ✅ PASS | `decorators.py:113-195` - Handles None gracefully, extracts order attributes |
| AC3: @log_portfolio decorator | ✅ PASS | `decorators.py:198-303` - Framework-agnostic (supports self.portfolio and self.broker) |
| AC4: Metadata preservation | ✅ PASS | All decorators use `functools.wraps` |
| AC5: Exception handling | ✅ PASS | signal_failed, order_failed, portfolio_update_failed events logged |
| AC6: Unit tests | ✅ PASS | 22 tests covering all scenarios |

#### Code Quality Assessment

**Strengths:**
1. **Framework-agnostic design** - Works with any class that has `_log_event()` method
2. **Safe serialization** - `_safe_str()` and `_serialize_args/kwargs()` handle complex types
3. **Graceful None handling** - @log_order doesn't log when method returns None
4. **Flexible portfolio access** - Checks both `self.portfolio` and `self.broker` (Backtrader style)
5. **Custom layer support** - All decorators accept `layer` parameter for flexibility

**Test Coverage Highlights:**
- `TestLogSignalDecorator`: 5 tests
- `TestLogOrderDecorator`: 6 tests
- `TestLogPortfolioDecorator`: 4 tests
- `TestDecoratorChaining`: 2 tests (multiple decorators work together)
- `TestDecoratorWithRealStrategy`: Integration with RustyBTValidatedStrategy
- `TestEdgeCases`: 4 tests for edge cases

#### Test Results

```
tests/validation/test_decorators.py: 28 tests PASSED (including 6 new tests for @log_broker decorator)
```

#### Recommended Actions

**No blocking issues identified.**

✅ **Implemented (2025-11-26):** Added `@log_broker` decorator for broker layer events. The decorator logs broker events (fills, rejections, cancellations) to the "broker" validation layer.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-25 | Story drafted from epics.md specification | SM Agent |
| 2025-11-26 | Code review completed - APPROVED | Code Review Workflow |
| 2025-11-26 | Implemented optional review recommendation: @log_broker decorator for broker layer events | Dev Agent (Claude Opus 4.5) |
