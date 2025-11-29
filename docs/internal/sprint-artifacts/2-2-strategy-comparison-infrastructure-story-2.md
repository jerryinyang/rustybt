# Story 2.2: Implement ValidatedStrategy Base Class for Backtrader

Status: done

## Story

As a developer,
I want a Backtrader base strategy class with identical logging behavior,
so that Backtrader strategies produce logs in the same format as rustybt.

## Acceptance Criteria

1. **BacktraderValidatedStrategy base class implemented** - `tests/validation/strategies/backtrader/base_validated.py` contains:
   - Class extends `bt.Strategy`
   - Uses `params` tuple for configuration (Backtrader convention)
   - `log_path` parameter in params
   - Opens JSONL log file in `__init__`

2. **_log_event() method implemented** - Identical schema to rustybt:
   - Parameters: `layer: str`, `event: str`, `data: dict`
   - Writes JSON object with fields: timestamp, layer, event, asset, data
   - Flushes after each write
   - Uses ISO8601 timestamp format

3. **Logging matches rustybt schema exactly**:
   - Same field names: timestamp, layer, event, asset, data
   - Same layer values: data, signals, orders, broker, portfolio
   - Same event names for equivalent operations
   - Timestamps in same format

4. **Backtrader lifecycle methods auto-log**:
   - `__init__` logs to layer: "data", event: "initialize"
   - `next()` logs to layer: "data", event: "bar_received"
   - Signal computations → layer: "signals", event: "signal_computed"
   - Order creation → layer: "orders", event: "order_created"

5. **File cleanup in stop() method** - Backtrader lifecycle:
   - `stop()` method closes log file
   - No file handle leaks
   - Proper cleanup even on early termination

6. **Unit tests verify log format matches rustybt**:
   - Test log file creation
   - Test event schema matches Story 2.1 format
   - Test lifecycle method logging
   - Test file cleanup on strategy stop

## Tasks / Subtasks

- [x] Task 1: Create Backtrader strategy directory structure (AC: #1)
  - [x] Create `tests/validation/strategies/bt_strategies/` directory (renamed from backtrader to avoid shadowing)
  - [x] Create `tests/validation/strategies/bt_strategies/__init__.py`
  - [x] Create `tests/validation/strategies/bt_strategies/base_validated.py`
  - [x] Add module docstring

- [x] Task 2: Implement BacktraderValidatedStrategy class (AC: #1, #2)
  - [x] Import backtrader as bt
  - [x] Create class extending bt.Strategy
  - [x] Define params tuple with log_path
  - [x] Open log file in `__init__`
  - [x] Implement `_log_event()` method matching rustybt schema exactly

- [x] Task 3: Implement lifecycle method overrides (AC: #4)
  - [x] Log initialize event in `__init__` after file open
  - [x] Override `next()` with bar_received logging
  - [x] Use `self.data.datetime.datetime()` for timestamps

- [x] Task 4: Implement cleanup in stop() (AC: #5)
  - [x] Override `stop()` method
  - [x] Close log file
  - [x] Handle case where file already closed
  - [x] Added `close()` convenience method

- [x] Task 5: Write unit tests (AC: #6)
  - [x] Create `tests/validation/strategies/bt_strategies/test_base_validated.py`
  - [x] Test strategy instantiation creates log file
  - [x] Test `_log_event()` writes valid JSONL
  - [x] Test log schema matches rustybt format exactly
  - [x] Test `next()` produces bar_received events
  - [x] Test `stop()` closes file properly

- [x] Task 6: Cross-framework schema comparison test
  - [x] Create test that compares rustybt and Backtrader log schemas
  - [x] Verify field names match exactly
  - [x] Verify layer values match exactly
  - [x] Verify event names for equivalent operations match

## Dev Notes

### Learnings from Previous Story

**From Story 2-1 (Status: drafted)**

- **RustyBTValidatedStrategy Created**: Base class at `rustybt/validation/base_strategy.py`
- **Log Schema Defined**: JSON with timestamp, layer, event, asset, data fields
- **_log_event() Pattern**: Flush after each write, ISO8601 timestamps
- **File Cleanup**: `__del__` method closes file handle

**Backtrader class MUST match rustybt** (from Story 2.1):
- Identical field names and types
- Same layer values (data, signals, orders, broker, portfolio)
- Same event naming conventions
- Compatible timestamp formats

[Source: docs/sprint-artifacts/2-1-strategy-comparison-infrastructure-story-1.md]

### Architecture Alignment

**Backtrader Integration** (Architecture pg 163-179):
- Backtrader uses `next()` instead of `handle_data()`
- Backtrader uses `stop()` for cleanup instead of destructor
- Use `self.params` for configuration (Backtrader convention)
- Access data via `self.data.close[0]` syntax

**Log Schema Must Match** (Architecture pg 183-189):
```json
{
  "timestamp": "2020-01-15T09:30:00",
  "layer": "data|signals|orders|broker|portfolio",
  "event": "bar_received|signal_generated|order_created|fill_executed|portfolio_updated",
  "asset": "AAPL",
  "data": {...}
}
```

### Implementation Pattern

```python
import backtrader as bt
from pathlib import Path
import json
from datetime import datetime
from typing import Optional, Any

class BacktraderValidatedStrategy(bt.Strategy):
    """Base class for validated Backtrader strategies with auto-logging."""

    params = (
        ('log_path', None),
    )

    def __init__(self) -> None:
        if self.params.log_path is None:
            raise ValueError("log_path parameter is required")
        self._log_file = open(self.params.log_path, 'w')
        self._log_event("data", "initialize", {
            "params": dict(self.params._getkwargs())
        })
        super().__init__()

    def _log_event(self, layer: str, event: str, data: dict) -> None:
        """Write structured event to JSONL log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "layer": layer,
            "event": event,
            "asset": data.get("asset"),
            "data": data
        }
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    def next(self) -> None:
        self._log_event("data", "bar_received", {
            "timestamp": str(self.data.datetime.datetime()),
            "close": float(self.data.close[0]),
            "volume": float(self.data.volume[0])
        })

    def stop(self) -> None:
        if hasattr(self, '_log_file') and not self._log_file.closed:
            self._log_file.close()
```

### Backtrader-Specific Notes

**Differences from rustybt**:
- Uses `params` tuple for parameters (not constructor args)
- Uses `next()` for bar processing (not `handle_data()`)
- Uses `stop()` for cleanup (not `__del__`)
- Data accessed via `self.data.close[0]` indexing

**Data Access Patterns**:
```python
# Current bar values
self.data.datetime.datetime()  # datetime of current bar
self.data.close[0]             # current close price
self.data.volume[0]            # current volume
self.data.open[0]              # current open price

# Previous bar values
self.data.close[-1]            # previous close
```

### Project Structure Notes

**Files to create**:
- `tests/validation/strategies/backtrader/__init__.py` (NEW)
- `tests/validation/strategies/backtrader/base_validated.py` (NEW - main implementation)
- `tests/validation/strategies/backtrader/test_base_validated.py` (NEW - unit tests)

**Directory structure**:
```
tests/validation/strategies/
├── __init__.py
├── rustybt/
│   └── (from Story 2.1 and later)
└── backtrader/
    ├── __init__.py
    ├── base_validated.py
    └── test_base_validated.py
```

**Dependencies**: backtrader>=1.9.78 (in validation extras)

### Testing Guidance

**Critical tests for schema matching**:
```python
def test_log_schema_matches_rustybt():
    """Verify Backtrader logs have identical schema to rustybt."""
    bt_log = create_backtrader_log()
    rb_log = create_rustybt_log()

    # Parse both
    bt_entry = json.loads(bt_log)
    rb_entry = json.loads(rb_log)

    # Same keys
    assert set(bt_entry.keys()) == set(rb_entry.keys())

    # Same layer values
    assert bt_entry["layer"] in {"data", "signals", "orders", "broker", "portfolio"}
```

### References

- [Source: docs/architecture.md - Backtrader Integration (pg 163-179)]
- [Source: docs/architecture.md - Log Schema (pg 183-189)]
- [Source: docs/epics.md - Story 2.2 specification]
- [Source: docs/sprint-artifacts/2-1-strategy-comparison-infrastructure-story-1.md]

## Dev Agent Record

### Context Reference

- `docs/sprint-artifacts/2-2-strategy-comparison-infrastructure-story-2.context.xml`

### Agent Model Used

- Claude Opus 4.5

### Debug Log References

- Fixed directory naming conflict: `backtrader/` renamed to `bt_strategies/` to avoid shadowing the backtrader package
- Fixed CSV test data format: Added all required columns (Date, Open, High, Low, Close, Volume, OpenInterest) for Backtrader's GenericCSVData
- Fixed test pattern: Tests that call methods after `cerebro.run()` must use custom strategies that log during `next()`, since `stop()` closes the file

### Completion Notes List

1. **Directory Structure Created**: `tests/validation/strategies/bt_strategies/` with proper `__init__.py`
2. **BacktraderValidatedStrategy Implemented**: Full implementation matching rustybt schema
3. **Cross-Framework Schema Compatibility Verified**: Tests confirm identical JSON keys, layer values, and event names
4. **18 Unit Tests Passing**: Comprehensive test coverage for all acceptance criteria
5. **Convenience Methods Added**: `log_signal()` and `log_order_created()` matching rustybt API

### File List

**Created:**
- `tests/validation/strategies/bt_strategies/__init__.py` - Package exports
- `tests/validation/strategies/bt_strategies/base_validated.py` - BacktraderValidatedStrategy implementation
- `tests/validation/strategies/bt_strategies/test_base_validated.py` - 18 unit tests

---

## Review Section

### Code Review Summary (2025-11-26)

**Reviewer:** Senior Developer (Code Review Workflow)
**Status:** ✅ **APPROVED**

#### Acceptance Criteria Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC1: BacktraderValidatedStrategy extends bt.Strategy | ✅ PASS | `tests/validation/strategies/bt_strategies/base_validated.py:57` - `class BacktraderValidatedStrategy(bt.Strategy)` |
| AC2: _log_event() identical schema | ✅ PASS | Lines 141-183 - Same JSON structure as rustybt |
| AC3: Schema matches rustybt exactly | ✅ PASS | `TestCrossFrameworkSchemaComparison` class validates this |
| AC4: Lifecycle methods auto-log | ✅ PASS | `__init__` and `next()` both log appropriately |
| AC5: File cleanup in stop() | ✅ PASS | Lines 276-294 - `stop()` and `close()` methods implemented |
| AC6: Unit tests verify schema match | ✅ PASS | 18 tests including `test_log_schema_has_same_keys`, `test_valid_layers_match_rustybt` |

#### Code Quality Assessment

**Strengths:**
1. **Perfect schema alignment** - `TestCrossFrameworkSchemaComparison::test_log_schema_has_same_keys` explicitly verifies JSON keys match rustybt
2. **Valid layer constants** - `VALID_LAYERS` matches rustybt exactly (frozen set for immutability)
3. **Proper Backtrader conventions** - Uses `params` tuple, `next()` method, `stop()` cleanup
4. **Comprehensive error handling** - ValueError for missing log_path, graceful closed-file handling
5. **Convenience methods** - `log_signal()` and `log_order_created()` match rustybt API

**Architecture Notes:**
- Directory renamed to `bt_strategies/` to avoid shadowing the `backtrader` package - correct decision
- File location in `tests/validation/strategies/` follows ADR-001 (test code in tests/)

#### Test Results

```
tests/validation/strategies/bt_strategies/test_base_validated.py: 18 tests PASSED
```

Key tests:
- `test_log_schema_has_same_keys` - Confirms JSON structure matches rustybt
- `test_valid_layers_match_rustybt` - Confirms layer values identical
- `test_initialize_event_matches_rustybt` - Confirms initialize event format

#### Recommended Actions

**No blocking issues identified.**

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-25 | Story drafted from epics.md specification | SM Agent |
| 2025-11-26 | Code review completed - APPROVED | Code Review Workflow |
