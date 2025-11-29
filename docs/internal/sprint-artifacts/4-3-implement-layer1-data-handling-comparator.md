# Story 4.3: Implement Layer 1 Data Handling Comparator

Status: done

## Story

As a developer,
I want Layer 1 comparison for data handling,
so that lookahead bias and bar alignment issues are detected between rustybt and Backtrader.

## Acceptance Criteria

1. **Layer1DataComparator class implemented in `rustybt/validation/comparators.py`**:
   - Constructor accepts tolerances dict
   - `compare(rustybt_logs, backtrader_logs)` method returns list[Discrepancy]

2. **Lookahead bias detection**:
   - Detects if strategy accessed future data
   - Compares data_accessed_timestamp vs data_current_bar_timestamp
   - Zero tolerance for lookahead violations
   - Creates Discrepancy with clear description

3. **Bar alignment comparison**:
   - Compares bar counts between frameworks
   - Compares bar timestamps with configured tolerance
   - Compares OHLCV values with price_decimal_places tolerance
   - Compares volume with volume_tolerance_pct

4. **Data integrity validation**:
   - Detects missing bars in either framework
   - Detects timestamp gaps
   - Detects OHLCV anomalies (e.g., high < low)

5. **pytest test file exists**:
   - `tests/validation/test_layer_1_data.py`
   - Uses `@pytest.mark.layer_1_data` marker
   - Tests all comparison scenarios

6. **Unit tests verify**:
   - Lookahead bias detection
   - Bar count comparison
   - OHLCV value comparison with tolerances
   - Known DESIGN differences filtering

## Tasks / Subtasks

- [x] Task 1: Create comparators.py module structure (AC: #1)
  - [x] Create rustybt/validation/comparators.py
  - [x] Define base Comparator abstract class
  - [x] Define Discrepancy dataclass (if not in models.py)
  - [x] Implement Layer1DataComparator class skeleton

- [x] Task 2: Implement lookahead bias detection (AC: #2)
  - [x] Create detect_lookahead_bias() method
  - [x] Extract data access events from logs
  - [x] Compare accessed timestamp vs current bar
  - [x] Return Discrepancy for any violation

- [x] Task 3: Implement bar alignment comparison (AC: #3)
  - [x] Create compare_bar_alignment() method
  - [x] Filter logs for bar_received events
  - [x] Compare bar counts with tolerance
  - [x] Compare individual bar timestamps
  - [x] Compare OHLCV values with decimal precision

- [x] Task 4: Implement data integrity validation (AC: #4)
  - [x] Create validate_data_integrity() method
  - [x] Detect missing bars by timestamp sequence
  - [x] Detect timestamp gaps
  - [x] Detect OHLCV anomalies

- [x] Task 5: Create pytest test file (AC: #5)
  - [x] Create tests/validation/test_layer_1_data.py
  - [x] Register layer_1_data marker in pytest.ini
  - [x] Add test fixtures for sample logs

- [x] Task 6: Write comprehensive unit tests (AC: #6)
  - [x] Test lookahead bias detection
  - [x] Test bar count mismatch detection
  - [x] Test OHLCV comparison with tolerances
  - [x] Test passing case with matching data
  - [x] Test DESIGN difference filtering

## Dev Notes

### Architecture Alignment

**Layer 1 Specification** (Architecture - Data Handling):
- Lookahead bias is CRITICAL - zero tolerance
- Bar alignment uses timestamp_window_ms tolerance
- OHLCV comparison uses price_decimal_places tolerance
- Must detect any case where strategy could access future data

**Log-Based Validation Pattern** (Architecture pg 195-204):
- Compare logs filtered by layer="data"
- Events: bar_received, data_access
- Use Polars for efficient comparison

### Learnings from Previous Stories

**From Story 4-1 (Log Parser)**

- **Parsed Logs**: DataFrame with timestamp, layer, event, data_* columns
- **Data Flattening**: Nested data fields prefixed with "data_"
- **Parquet Cache**: Use cached logs for faster comparison

**From Story 4-2 (Tolerances)**

- **Tolerance Loading**: Use load_tolerances("layer_1_data")
- **Override Support**: Tolerances can be overridden in tests
- **Values Available**: timestamp_window_ms, price_decimal_places, volume_tolerance_pct, bar_count_tolerance

[Source: docs/sprint-artifacts/4-1-5-layer-comparison-test-suite-story-1.md]
[Source: docs/sprint-artifacts/4-2-5-layer-comparison-test-suite-story-2.md]

### Implementation Pattern

**Layer1DataComparator class**:
```python
from dataclasses import dataclass
from typing import Optional, Any
import polars as pl

@dataclass
class Discrepancy:
    """Represents a discrepancy found during comparison."""
    layer: str
    event: str
    timestamp: Optional[str]
    field: str
    rustybt_value: Any
    backtrader_value: Any
    tolerance: Any
    exceeded_by: Any
    asset: Optional[str] = None

class Layer1DataComparator:
    """Comparator for Layer 1: Data Handling."""

    def __init__(self, tolerances: dict):
        self.tolerances = tolerances

    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame
    ) -> list[Discrepancy]:
        """Run all Layer 1 comparisons."""
        discrepancies = []

        # Check for lookahead bias in rustybt logs
        discrepancies.extend(self.detect_lookahead_bias(rustybt_logs))

        # Compare bar alignment between frameworks
        discrepancies.extend(
            self.compare_bar_alignment(rustybt_logs, backtrader_logs)
        )

        # Validate data integrity
        discrepancies.extend(self.validate_data_integrity(rustybt_logs))
        discrepancies.extend(self.validate_data_integrity(backtrader_logs))

        return discrepancies
```

**Lookahead bias detection**:
```python
def detect_lookahead_bias(self, logs: pl.DataFrame) -> list[Discrepancy]:
    """Detect if strategy accessed future data."""
    discrepancies = []

    data_events = logs.filter(pl.col("layer") == "data")

    for row in data_events.iter_rows(named=True):
        accessed_time = row.get("data_accessed_timestamp")
        current_bar = row.get("data_current_bar_timestamp")

        if accessed_time and current_bar:
            if accessed_time > current_bar:
                discrepancies.append(Discrepancy(
                    layer="data",
                    event="lookahead_bias",
                    timestamp=current_bar,
                    field="data_access",
                    rustybt_value=accessed_time,
                    backtrader_value=current_bar,
                    tolerance="none (zero tolerance)",
                    exceeded_by=f"{accessed_time} > {current_bar}",
                    asset=row.get("asset")
                ))

    return discrepancies
```

**Bar alignment comparison**:
```python
def compare_bar_alignment(
    self,
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame
) -> list[Discrepancy]:
    """Compare bar timestamps and OHLCV values."""
    discrepancies = []

    rb_bars = rustybt_logs.filter(pl.col("event") == "bar_received")
    bt_bars = backtrader_logs.filter(pl.col("event") == "bar_received")

    # Compare bar counts
    bar_count_tol = self.tolerances.get("bar_count_tolerance", 0)
    count_diff = abs(len(rb_bars) - len(bt_bars))

    if count_diff > bar_count_tol:
        discrepancies.append(Discrepancy(
            layer="data",
            event="bar_count_mismatch",
            timestamp=None,
            field="bar_count",
            rustybt_value=len(rb_bars),
            backtrader_value=len(bt_bars),
            tolerance=bar_count_tol,
            exceeded_by=count_diff
        ))

    # Compare individual bars
    # ... implementation continues ...

    return discrepancies
```

### Project Structure Notes

**Files to create/modify**:
- `rustybt/validation/comparators.py` (NEW - main comparator module)
- `tests/validation/test_layer_1_data.py` (NEW - Layer 1 tests)
- `pytest.ini` (MODIFY - add layer markers)

**Alignment with unified project structure**:
- Comparators in rustybt/validation/ per architecture
- Tests follow tests/validation/test_layer_*.py pattern
- Discrepancy model may be in models.py or comparators.py

### Testing Guidance

```python
import pytest
import polars as pl
from rustybt.validation.comparators import Layer1DataComparator, Discrepancy

@pytest.mark.layer_1_data
class TestLayer1DataComparator:

    def test_detect_lookahead_bias(self, layer_1_tolerances):
        """Test lookahead bias detection."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "data_access",
                "data_current_bar_timestamp": "2020-01-15T09:30:00",
                "data_accessed_timestamp": "2020-01-15T09:31:00",  # Future!
            }
        ])

        comparator = Layer1DataComparator(layer_1_tolerances.as_dict())
        discrepancies = comparator.detect_lookahead_bias(logs)

        assert len(discrepancies) == 1
        assert discrepancies[0].event == "lookahead_bias"

    def test_bar_count_mismatch(self, layer_1_tolerances):
        """Test bar count comparison."""
        rb_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
            {"timestamp": "2020-01-15T09:31:00", "layer": "data", "event": "bar_received"},
        ])
        bt_logs = pl.DataFrame([
            {"timestamp": "2020-01-15T09:30:00", "layer": "data", "event": "bar_received"},
        ])

        comparator = Layer1DataComparator(layer_1_tolerances.as_dict())
        discrepancies = comparator.compare_bar_alignment(rb_logs, bt_logs)

        assert any(d.event == "bar_count_mismatch" for d in discrepancies)

    def test_ohlcv_comparison_within_tolerance(self, layer_1_tolerances):
        """Test OHLCV values match within tolerance."""
        rb_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.12345,
            }
        ])
        bt_logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.12349,  # Differs at 5th decimal
            }
        ])

        # Default tolerance is 4 decimal places
        comparator = Layer1DataComparator(layer_1_tolerances.as_dict())
        discrepancies = comparator.compare(rb_logs, bt_logs)

        # Should pass - difference is beyond tolerance precision
        price_discrepancies = [d for d in discrepancies if "close" in d.field]
        assert len(price_discrepancies) == 0

    def test_no_discrepancies_matching_data(self, layer_1_tolerances):
        """Test no discrepancies when data matches."""
        logs = pl.DataFrame([
            {
                "timestamp": "2020-01-15T09:30:00",
                "layer": "data",
                "event": "bar_received",
                "data_close": 100.1234,
                "data_volume": 1000,
            }
        ])

        comparator = Layer1DataComparator(layer_1_tolerances.as_dict())
        discrepancies = comparator.compare(logs, logs)

        assert len(discrepancies) == 0
```

### References

- [Source: docs/architecture.md - Layer 1 Data Handling specification]
- [Source: docs/architecture.md - Log-Based Validation Pattern (pg 195-204)]
- [Source: docs/epics/epic-4-5-layer-comparison-test-suite.md - Story 4.3 specification]
- [Source: docs/prd.md - FR4-FR5 (lookahead bias, bar alignment)]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 20 unit tests pass for Layer 1 Data Comparator

### Completion Notes List

- Created comprehensive comparators module with base classes and dataclasses
- Implemented `Discrepancy` dataclass with auto-generated descriptions
- Implemented `ComparisonResult` dataclass with severity counting properties
- Implemented `BaseComparator` abstract class for extensibility
- Implemented `Layer1DataComparator` with:
  - `detect_lookahead_bias()`: Zero-tolerance future data access detection
  - `compare_bar_alignment()`: Bar count and timestamp comparison
  - `validate_data_integrity()`: OHLCV anomaly detection (high < low, etc.)
  - Full tolerance integration via Layer1Tolerances dataclass
- Created comprehensive test suite with 20 tests covering all comparison scenarios

### File List

- `rustybt/validation/comparators.py` - NEW: Layer 1 comparator implementation
- `tests/validation/test_layer_1_data.py` - NEW: 20 unit tests

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-26 | Story drafted from epic-4 specification | SM Agent |
| 2025-11-27 | Implemented all tasks, 20 tests passing | Dev Agent |
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
| Layer1DataComparator class | ✅ Pass | Inherits from `BaseComparator`, accepts `Layer1Tolerances` |
| Lookahead bias detection | ✅ Pass | `detect_lookahead_bias()` checks `data_accessed_timestamp` > `data_current_bar_timestamp` |
| Bar alignment comparison | ✅ Pass | `compare_bar_alignment()` compares counts and OHLCV values |
| Data integrity validation | ✅ Pass | `validate_data_integrity()` detects OHLCV anomalies (high < low, etc.) |
| pytest test file | ✅ Pass | `test_layer_1_data.py` with `@pytest.mark.layer_1_data` marker |
| Unit tests | ✅ Pass | 20 tests covering all comparison scenarios |

---

#### 2. Code Quality Assessment

**Architecture & Design** (10/10)
- Clean abstract base class pattern with `BaseComparator`
- `Discrepancy` dataclass with auto-generated descriptions
- `ComparisonResult` with computed properties (`critical_count`, `warning_count`)
- Proper use of `severity` levels: critical, warning, info

**Implementation Quality** (9/10)
- Lookahead bias detection correctly marks violations as "critical" severity
- OHLCV comparison uses `Decimal` for price precision (prevents float rounding issues)
- Volume tolerance uses percentage-based comparison (correct approach)
- Missing bar detection tracks by timestamp lookup (efficient O(n) approach)

**Test Coverage** (10/10)
- 20 tests covering: lookahead bias, bar count, OHLCV tolerance, data integrity
- Tests for both positive cases (no discrepancies) and negative cases (discrepancies found)
- Tests verify severity levels (critical vs warning)
- Tests for empty logs (edge case)

**Critical Validation** (10/10)
- **Lookahead bias is correctly zero-tolerance** - any future data access is critical
- OHLCV anomaly (high < low) correctly marked as critical
- Bar count mismatch uses configurable tolerance

---

#### 3. Architecture Alignment

- ✅ Layer 1 specification followed (Architecture - Data Handling)
- ✅ Uses Decimal for price comparison (financial precision)
- ✅ Polars DataFrame integration for efficient comparison
- ✅ Clear separation: detection, comparison, validation methods

---

#### 4. Verdict

**No blocking issues.** Story implementation is excellent.

**Strengths Noted**:
- `_compare_ohlcv()` private method keeps `compare_bar_alignment()` clean
- Separate validation of both rustybt and backtrader logs for integrity
- Stats dict in ComparisonResult provides useful diagnostics

**Minor Observation** (Non-blocking):
- Line 221: Consider logging `timestamp > str(current_bar)` comparison uses string comparison; ISO8601 format ensures this works correctly, but a comment would clarify intent
