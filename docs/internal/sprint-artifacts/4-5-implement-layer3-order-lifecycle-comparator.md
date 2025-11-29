# Story 4.5: Implement Layer 3 Order Lifecycle Comparator

Status: done

## Story

As a developer,
I want Layer 3 comparison for order lifecycle,
so that order creation, execution, and state transition differences between rustybt and Backtrader are detected.

## Acceptance Criteria

1. **Layer3OrdersComparator class implemented**:
   - In `rustybt/validation/comparators.py`
   - Constructor accepts tolerances dict
   - `compare(rustybt_logs, backtrader_logs)` returns list[Discrepancy]

2. **Order creation comparison**:
   - Compares order counts by type (market, limit, stop)
   - Compares order quantities
   - Compares order timing (which bar)
   - Matches orders by timestamp + asset + quantity (not order ID)

3. **Order execution comparison**:
   - Compares fill prices (with tolerance)
   - Compares fill quantities
   - Compares fill timing
   - Handles partial fills

4. **Order state transition comparison**:
   - Validates CREATED → SUBMITTED → FILLED sequence
   - Validates CREATED → CANCELLED handling
   - Detects missing state transitions
   - Compares state at each transition

5. **pytest test file exists**:
   - `tests/validation/test_layer_3_orders.py`
   - Uses `@pytest.mark.layer_3_orders` marker
   - Tests all order comparison scenarios

6. **Unit tests verify**:
   - Order creation comparison
   - Order execution comparison
   - State transition validation
   - Partial fill handling

## Tasks / Subtasks

- [x] Task 1: Implement Layer3OrdersComparator (AC: #1)
  - [x] Add class to comparators.py
  - [x] Define compare() method signature
  - [x] Filter logs by layer="orders"

- [x] Task 2: Implement order creation comparison (AC: #2)
  - [x] Create compare_order_creation() method
  - [x] Filter for order_created events
  - [x] Match orders by timestamp + asset + quantity
  - [x] Compare order types and quantities

- [x] Task 3: Implement order execution comparison (AC: #3)
  - [x] Create compare_order_execution() method
  - [x] Filter for order_filled events
  - [x] Compare fill prices with tolerance
  - [x] Handle partial fills

- [x] Task 4: Implement state transition comparison (AC: #4)
  - [x] Create compare_order_states() method
  - [x] Track order state sequences
  - [x] Validate expected transitions
  - [x] Detect anomalies

- [x] Task 5: Create test file (AC: #5)
  - [x] Create tests/validation/test_layer_3_orders.py
  - [x] Register layer_3_orders marker
  - [x] Add test fixtures for order logs

- [x] Task 6: Write comprehensive tests (AC: #6)
  - [x] Test order count comparison
  - [x] Test fill price comparison
  - [x] Test state transition validation
  - [x] Test partial fill scenarios

## Dev Notes

### Architecture Alignment

**Layer 3 Specification** (Architecture - Order Lifecycle):
- Order IDs may differ - match by timestamp + asset + quantity
- Fill prices may differ due to slippage model differences (DESIGN)
- State transitions should match exactly
- Events: order_created, order_submitted, order_filled, order_cancelled

**Order Lifecycle States**:
```
CREATED → SUBMITTED → FILLED (normal flow)
CREATED → SUBMITTED → PARTIALLY_FILLED → FILLED (partial fill)
CREATED → SUBMITTED → CANCELLED (cancellation)
CREATED → REJECTED (immediate rejection)
```

### Learnings from Previous Stories

**From Stories 4-3, 4-4 (Layer 1-2 Comparators)**

- **Comparator Pattern**: Consistent class structure with compare() method
- **Discrepancy Model**: Same dataclass for all layers
- **Tolerance Integration**: tolerances dict passed to constructor
- **Test Markers**: @pytest.mark.layer_X_name pattern

[Source: docs/sprint-artifacts/4-3-5-layer-comparison-test-suite-story-3.md]
[Source: docs/sprint-artifacts/4-4-5-layer-comparison-test-suite-story-4.md]

### Implementation Pattern

**Layer3OrdersComparator class**:
```python
class Layer3OrdersComparator:
    """Comparator for Layer 3: Order Lifecycle."""

    def __init__(self, tolerances: dict):
        self.tolerances = tolerances

    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame
    ) -> list[Discrepancy]:
        """Run all Layer 3 comparisons."""
        discrepancies = []

        discrepancies.extend(
            self.compare_order_creation(rustybt_logs, backtrader_logs)
        )
        discrepancies.extend(
            self.compare_order_execution(rustybt_logs, backtrader_logs)
        )
        discrepancies.extend(
            self.compare_order_states(rustybt_logs, backtrader_logs)
        )

        return discrepancies
```

**Order creation comparison**:
```python
def compare_order_creation(
    self,
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame
) -> list[Discrepancy]:
    """Compare order creation events."""
    discrepancies = []

    rb_orders = rustybt_logs.filter(pl.col("event") == "order_created")
    bt_orders = backtrader_logs.filter(pl.col("event") == "order_created")

    # Compare order counts
    if len(rb_orders) != len(bt_orders):
        discrepancies.append(Discrepancy(
            layer="orders",
            event="order_count_mismatch",
            timestamp=None,
            field="order_count",
            rustybt_value=len(rb_orders),
            backtrader_value=len(bt_orders),
            tolerance=0,
            exceeded_by=abs(len(rb_orders) - len(bt_orders))
        ))

    # Match orders by timestamp + asset + quantity
    for rb_row in rb_orders.iter_rows(named=True):
        timestamp = rb_row["timestamp"]
        asset = rb_row.get("asset")
        quantity = rb_row.get("data_quantity")

        # Find matching Backtrader order
        matches = bt_orders.filter(
            (pl.col("timestamp") == timestamp) &
            (pl.col("asset") == asset) &
            (pl.col("data_quantity") == quantity)
        )

        if len(matches) == 0:
            discrepancies.append(Discrepancy(
                layer="orders",
                event="order_not_found",
                timestamp=timestamp,
                field="order_match",
                rustybt_value=f"{asset}:{quantity}",
                backtrader_value="not found",
                tolerance="exact match",
                exceeded_by="missing order",
                asset=asset
            ))
            continue

        # Compare order types
        bt_row = matches.row(0, named=True)
        rb_type = rb_row.get("data_order_type")
        bt_type = bt_row.get("data_order_type")

        if rb_type != bt_type:
            discrepancies.append(Discrepancy(
                layer="orders",
                event="order_type_mismatch",
                timestamp=timestamp,
                field="order_type",
                rustybt_value=rb_type,
                backtrader_value=bt_type,
                tolerance="exact match",
                exceeded_by=f"{rb_type} != {bt_type}",
                asset=asset
            ))

    return discrepancies
```

**Order execution comparison**:
```python
def compare_order_execution(
    self,
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame
) -> list[Discrepancy]:
    """Compare order fill events."""
    discrepancies = []
    price_tol = self.tolerances.get("fill_price_decimal_places", 4)

    rb_fills = rustybt_logs.filter(pl.col("event") == "order_filled")
    bt_fills = backtrader_logs.filter(pl.col("event") == "order_filled")

    # Match fills and compare prices
    for rb_row in rb_fills.iter_rows(named=True):
        timestamp = rb_row["timestamp"]
        asset = rb_row.get("asset")

        matches = bt_fills.filter(
            (pl.col("timestamp") == timestamp) &
            (pl.col("asset") == asset)
        )

        if len(matches) == 0:
            continue  # Already caught in order creation

        bt_row = matches.row(0, named=True)
        rb_price = rb_row.get("data_fill_price")
        bt_price = bt_row.get("data_fill_price")

        if not values_match(rb_price, bt_price, price_tol):
            discrepancies.append(Discrepancy(
                layer="orders",
                event="fill_price_mismatch",
                timestamp=timestamp,
                field="fill_price",
                rustybt_value=rb_price,
                backtrader_value=bt_price,
                tolerance=f"{price_tol} decimal places",
                exceeded_by=abs(rb_price - bt_price),
                asset=asset
            ))

    return discrepancies
```

**Order state transition comparison**:
```python
def compare_order_states(
    self,
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame
) -> list[Discrepancy]:
    """Compare order state transitions."""
    discrepancies = []

    # Extract state transitions per order
    rb_states = self._extract_state_sequences(rustybt_logs)
    bt_states = self._extract_state_sequences(backtrader_logs)

    # Compare state sequences
    for order_key, rb_seq in rb_states.items():
        if order_key not in bt_states:
            continue

        bt_seq = bt_states[order_key]

        if rb_seq != bt_seq:
            discrepancies.append(Discrepancy(
                layer="orders",
                event="state_transition_mismatch",
                timestamp=None,
                field=f"order_{order_key}_states",
                rustybt_value=" -> ".join(rb_seq),
                backtrader_value=" -> ".join(bt_seq),
                tolerance="exact sequence match",
                exceeded_by="sequence differs"
            ))

    return discrepancies

def _extract_state_sequences(self, logs: pl.DataFrame) -> dict:
    """Extract state sequences per order."""
    order_states = {}

    for row in logs.filter(pl.col("layer") == "orders").iter_rows(named=True):
        order_key = f"{row['timestamp']}_{row.get('asset')}"
        state = row.get("data_order_state")

        if state:
            if order_key not in order_states:
                order_states[order_key] = []
            order_states[order_key].append(state)

    return order_states
```

### Project Structure Notes

**Files to modify**:
- `rustybt/validation/comparators.py` (MODIFY - add Layer3OrdersComparator)
- `tests/validation/config/layer_3_tolerances.yaml` (MODIFY - add order tolerances)
- `tests/validation/test_layer_3_orders.py` (NEW - Layer 3 tests)

**Layer 3 tolerances**:
```yaml
layer_3_orders:
  order_count_tolerance: 0  # Orders must match exactly
  fill_price_decimal_places: 4  # Fill price comparison precision
  fill_quantity_tolerance: 0  # Fill quantities must match
  state_sequence_match: true  # State transitions must match
```

### Testing Guidance

```python
import pytest
import polars as pl
from rustybt.validation.comparators import Layer3OrdersComparator

@pytest.mark.layer_3_orders
class TestLayer3OrdersComparator:

    def test_order_creation_match(self, layer_3_tolerances):
        """Test matching order creation."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "orders",
                "event": "order_created",
                "asset": "AAPL",
                "data_quantity": 100,
                "data_order_type": "market",
            }
        ])

        comparator = Layer3OrdersComparator(layer_3_tolerances.as_dict())
        discrepancies = comparator.compare(logs, logs)

        order_discrepancies = [d for d in discrepancies if "order" in d.event]
        assert len(order_discrepancies) == 0

    def test_order_count_mismatch(self, layer_3_tolerances):
        """Test order count mismatch detection."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 100},
            {"timestamp": "2020-01-15T09:31:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 50},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "event": "order_created", "asset": "AAPL", "data_quantity": 100},
        ])

        comparator = Layer3OrdersComparator(layer_3_tolerances.as_dict())
        discrepancies = comparator.compare(rb_logs, bt_logs)

        assert any(d.event == "order_count_mismatch" for d in discrepancies)

    def test_fill_price_comparison(self, layer_3_tolerances):
        """Test fill price comparison with tolerance."""
        rb_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "orders",
                "event": "order_filled",
                "asset": "AAPL",
                "data_fill_price": 150.1234,
            }
        ])
        bt_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "orders",
                "event": "order_filled",
                "asset": "AAPL",
                "data_fill_price": 150.1239,  # Differs at 4th decimal
            }
        ])

        comparator = Layer3OrdersComparator(layer_3_tolerances.as_dict())
        discrepancies = comparator.compare(rb_logs, bt_logs)

        # Should pass within 4 decimal tolerance
        price_discrepancies = [d for d in discrepancies if d.event == "fill_price_mismatch"]
        assert len(price_discrepancies) == 0

    def test_state_transition_validation(self, layer_3_tolerances):
        """Test order state transition comparison."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "CREATED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "SUBMITTED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "FILLED"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "CREATED"},
            {"timestamp": "2020-01-15T09:30:00", "layer": "orders", "asset": "AAPL", "data_order_state": "FILLED"},  # Missing SUBMITTED
        ])

        comparator = Layer3OrdersComparator(layer_3_tolerances.as_dict())
        discrepancies = comparator.compare_order_states(rb_logs, bt_logs)

        assert any(d.event == "state_transition_mismatch" for d in discrepancies)
```

### References

- [Source: docs/architecture.md - Layer 3 Order Lifecycle specification]
- [Source: docs/epics/epic-4-5-layer-comparison-test-suite.md - Story 4.5 specification]
- [Source: docs/prd.md - FR9-FR11 (order lifecycle comparison)]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 11 unit tests pass for Layer 3 Order Lifecycle Comparator

### Completion Notes List

- Implemented `Layer3OrdersComparator` class in comparators.py with:
  - `compare_order_creation()`: Order count and type comparison
  - `compare_order_execution()`: Fill price comparison with decimal tolerance
  - `compare_order_states()`: State transition sequence validation
- Integrated with `Layer3Tolerances` dataclass
- Returns `ComparisonResult` with statistics and discrepancies
- Created comprehensive test suite with 11 tests covering all comparison scenarios

### File List

- `rustybt/validation/comparators.py` - MODIFIED: Added Layer3OrdersComparator
- `tests/validation/test_layer_3_orders.py` - NEW: 11 unit tests
- `tests/validation/config/layer_3_tolerances.yaml` - NEW: Layer 3 config

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-26 | Story drafted from epic-4 specification | SM Agent |
| 2025-11-27 | Implemented all tasks, 11 tests passing | Dev Agent |
| 2025-11-27 | Code review completed - APPROVED | Senior Dev Review |

---

## Code Review Section

### Code Review Summary (2025-11-27)

**Reviewer**: Senior Developer (Automated Code Review)
**Status**: ✅ **APPROVED** - No blocking issues

---

#### 1. Acceptance Criteria Verification

| Criteria | Status | Notes |
|----------|--------|-------|
| Layer3OrdersComparator class | ✅ Pass | Inherits from `BaseComparator`, accepts `Layer3Tolerances` |
| Order creation comparison | ✅ Pass | `compare_order_creation()` matches by timestamp+asset+quantity |
| Order execution comparison | ✅ Pass | `compare_order_execution()` compares fill prices with decimal tolerance |
| Order state transition comparison | ✅ Pass | `compare_order_states()` validates CREATED→SUBMITTED→FILLED sequences |
| pytest test file | ✅ Pass | `test_layer_3_orders.py` with `@pytest.mark.layer_3_orders` marker |
| Unit tests | ✅ Pass | 11 tests covering creation, execution, state transitions, partial fills |

---

#### 2. Code Quality Assessment

**Architecture & Design** (9/10)
- Consistent pattern with Layer 1-2 comparators (BaseComparator inheritance)
- Order matching by timestamp+asset+quantity (not order ID) is correct per architecture
- State sequence extraction uses `_extract_state_sequences()` helper

**Implementation Quality** (9/10)
- Fill price comparison uses configurable `fill_price_decimal_places` tolerance
- State transition comparison tracks order lifecycles correctly
- Partial fill state `PARTIALLY_FILLED` properly handled in test suite

**Test Coverage** (10/10)
- 11 tests covering: order count, order type, fill price, state transitions, partial fills
- Tests for both tolerance passing and exceeding cases
- Empty logs edge case handled

**Critical Validation** (9/10)
- Order type mismatch detection (market vs limit) works correctly
- State transition mismatch detection catches missing intermediate states

---

#### 3. Architecture Alignment

- ✅ Layer 3 specification followed (Architecture - Order Lifecycle)
- ✅ Orders matched by timestamp+asset+quantity (not order ID per spec)
- ✅ State transitions: CREATED→SUBMITTED→FILLED validated
- ✅ YAML tolerance configuration integrated

---

#### 4. Verdict

**No blocking issues.** Story implementation is complete.

**Strengths Noted**:
- Clean separation of comparison methods (creation, execution, states)
- `order_id_exact_match: false` in config correctly reflects architecture decision
- Partial fill handling tested with PARTIALLY_FILLED state
