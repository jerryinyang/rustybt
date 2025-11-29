# Story 6.4: Implement Multi-Factor Strategy (Dual)

Status: review

## Story

As a developer,
I want Multi-Factor strategy combining EMA + RSI + MACD implemented,
so that complex multi-indicator strategies can be validated.

## Acceptance Criteria

1. **rustybt Multi-Factor implementation exists** at `tests/validation/strategies/rustybt/multi_factor.py`:
   - Extends `RustyBTValidatedStrategy` base class
   - Implements three indicators: EMA(50), RSI(14), MACD(12,26,9)
   - Default parameters: ema_period=50, rsi_period=14, macd_fast=12, macd_slow=26, macd_signal=9
   - Buy when ALL conditions met: Price > EMA, 50 < RSI < 70, MACD > Signal
   - Sell when ANY condition fails or RSI > 80 (overbought exit)

2. **Backtrader Multi-Factor implementation exists** at `tests/validation/strategies/backtrader/multi_factor.py`:
   - Extends `BacktraderValidatedStrategy` base class
   - Uses `bt.indicators.EMA`, `bt.indicators.RSI`, `bt.indicators.MACD`
   - Logically equivalent to rustybt implementation
   - Same default parameters

3. **Factor scoring system implemented**:
   - Each factor returns 1 (bullish) or 0 (not bullish)
   - Entry requires all factors = 1 (score = 3)
   - Exit when any factor = 0 or RSI > 80
   - Log individual factor values for debugging

4. **Strategy audit checklist passed**:
   - [x] Same EMA calculation
   - [x] Same RSI calculation (may be DESIGN)
   - [x] Same MACD calculation (may be DESIGN)
   - [x] Same factor combination logic
   - [x] Same entry/exit conditions

5. **Log individual factor values for debugging**:
   - Log each indicator value on every bar
   - Log factor scores (0 or 1) for each factor
   - Log combined signal with factor breakdown

6. **Unit tests verify**:
   - EMA calculation accuracy
   - RSI calculation accuracy
   - MACD calculation accuracy
   - Factor scoring logic
   - Entry/exit conditions

## Tasks / Subtasks

- [x] Task 1: Create rustybt Multi-Factor strategy (AC: #1)
  - [x] Create `tests/validation/strategies/rustybt/multi_factor.py`
  - [x] Implement `MultiFactorStrategy` class
  - [x] Add EMA indicator calculation
  - [x] Add RSI indicator calculation
  - [x] Add MACD indicator calculation (MACD line and signal line)
  - [x] Implement factor-based entry/exit logic

- [x] Task 2: Create Backtrader Multi-Factor strategy (AC: #2)
  - [x] Create `tests/validation/strategies/bt_strategies/multi_factor.py`
  - [x] Use Backtrader's built-in indicators
  - [x] Implement equivalent factor logic
  - [x] Ensure log output matches rustybt format

- [x] Task 3: Implement factor scoring system (AC: #3)
  - [x] Create `compute_factors()` method
  - [x] Return dict with factor name and score (0/1)
  - [x] Implement entry logic (all factors = 1)
  - [x] Implement exit logic (any factor = 0 or RSI > 80)

- [x] Task 4: Verify strategy equivalence (AC: #4)
  - [x] Complete strategy audit checklist
  - [x] Document MACD calculation differences (DESIGN candidate)
  - [x] Document RSI calculation differences (DESIGN candidate)
  - [x] Verify factor combination logic matches

- [x] Task 5: Validate log output (AC: #5)
  - [x] Log all indicator values
  - [x] Log individual factor scores
  - [x] Log combined signal with breakdown
  - [x] Verify log format consistency

- [x] Task 6: Write unit tests (AC: #6)
  - [x] Create `tests/validation/test_multi_factor_strategy.py`
  - [x] Test EMA calculation
  - [x] Test RSI calculation
  - [x] Test MACD calculation (MACD line and signal)
  - [x] Test factor scoring
  - [x] Test entry/exit conditions

## Dev Notes

### Architecture Alignment

**Factor Computation**:
```python
def compute_factors(self, data) -> dict[str, int]:
    """Compute factor scores for multi-factor strategy."""
    factors = {
        "trend": 1 if data.close > self.ema[-1] else 0,
        "momentum_rsi": 1 if 50 < self.rsi[-1] < 70 else 0,
        "momentum_macd": 1 if self.macd[-1] > self.macd_signal[-1] else 0,
    }
    return factors

def compute_signal(self, context, data) -> str:
    """Generate signal based on factor alignment."""
    factors = self.compute_factors(data)
    total_score = sum(factors.values())

    # Log factors for comparison
    self._log_factors(factors)

    # Entry: all factors must be bullish
    if total_score == 3 and not self.has_position():
        return "BUY"

    # Exit: any factor fails OR RSI overbought
    if self.has_position():
        if total_score < 3 or self.rsi[-1] > 80:
            return "SELL"

    return "HOLD"
```

**MACD Calculation**:
```python
def compute_macd(self, prices: list[float]) -> tuple[float, float]:
    """Compute MACD line and signal line."""
    fast_ema = self.compute_ema(prices, self.macd_fast)
    slow_ema = self.compute_ema(prices, self.macd_slow)

    macd_line = fast_ema - slow_ema

    # Signal line is EMA of MACD line
    # Note: This requires storing MACD history
    macd_signal = self.compute_ema(self.macd_history, self.macd_signal_period)

    return macd_line, macd_signal
```

**Log Schema for Multi-Factor**:
```json
{
  "timestamp": "2020-01-15T09:30:00",
  "layer": "signals",
  "event": "factors_computed",
  "asset": "AAPL",
  "data": {
    "price": 150.25,
    "ema_50": 148.50,
    "rsi": 55.2,
    "macd": 1.25,
    "macd_signal": 0.95,
    "factors": {
      "trend": 1,
      "momentum_rsi": 1,
      "momentum_macd": 1
    },
    "total_score": 3,
    "signal": "BUY"
  }
}
```

### Learnings from Previous Stories

**From Stories 6-1, 6-2, 6-3**

- **Indicator Differences**: RSI and MACD calculations may differ between frameworks
- **DESIGN Classification**: Document calculation differences as DESIGN, not BUG
- **Factor Logging**: Log individual components for debugging discrepancies
- **Testing Pattern**: Test each indicator separately, then combined logic

**Known DESIGN Candidates**:
- RSI: Wilder's smoothing vs simple average
- MACD: EMA calculation method may differ
- EMA: Initial value handling may differ

[Source: docs/sprint-artifacts/6-3-initial-strategy-validation-story-3.md]

### Project Structure Notes

**Files to create**:
- `tests/validation/strategies/rustybt/multi_factor.py` (NEW)
- `tests/validation/strategies/backtrader/multi_factor.py` (NEW)
- `tests/validation/test_multi_factor_strategy.py` (NEW)

**Existing files to reference**:
- `tests/validation/strategies/rustybt/momentum.py` - RSI pattern
- `tests/validation/strategies/rustybt/sma_crossover.py` - Base pattern

### Technical Notes

**MACD Calculation Differences (Potential DESIGN)**:
- MACD = Fast EMA - Slow EMA
- Signal = EMA of MACD line
- Backtrader may use different EMA initialization
- Document differences in `docs/validation/design-differences.md#macd-calculation`

**Factor Combination Logic**:
- All three factors must align for entry
- Any single factor failing triggers exit
- RSI > 80 is an emergency exit condition
- This is the most complex signal logic of the 4 strategies

### Testing Guidance

```python
import pytest

@pytest.mark.layer_2_signals
class TestMultiFactorStrategy:

    def test_ema_calculation(self, price_series):
        """Test EMA(50) calculation accuracy."""
        strategy = MultiFactorStrategy()
        ema = strategy.compute_ema(price_series, period=50)
        # Verify against known EMA values

    def test_macd_calculation(self, price_series):
        """Test MACD line and signal line calculation."""
        strategy = MultiFactorStrategy()
        macd, signal = strategy.compute_macd(price_series)
        # Verify MACD = Fast EMA - Slow EMA

    def test_factor_scoring_all_bullish(self):
        """Test all factors = 1 when conditions met."""
        # Price > EMA, 50 < RSI < 70, MACD > Signal
        factors = strategy.compute_factors(bullish_data)
        assert factors == {"trend": 1, "momentum_rsi": 1, "momentum_macd": 1}

    def test_factor_scoring_partial(self):
        """Test partial factor scores."""
        # Only some conditions met
        factors = strategy.compute_factors(mixed_data)
        assert sum(factors.values()) < 3

    def test_entry_requires_all_factors(self):
        """Test BUY only when all 3 factors = 1."""
        strategy = MultiFactorStrategy()
        # Mock factors = {trend: 1, momentum_rsi: 1, momentum_macd: 0}
        assert strategy.compute_signal(context, data) == "HOLD"

    def test_exit_on_any_factor_failure(self):
        """Test SELL when any factor drops to 0."""
        strategy = MultiFactorStrategy()
        strategy.has_position = lambda: True
        # One factor fails -> SELL

    def test_emergency_exit_rsi_overbought(self):
        """Test SELL when RSI > 80 regardless of other factors."""
        strategy = MultiFactorStrategy()
        strategy.has_position = lambda: True
        strategy.rsi = [85.0]  # Overbought
        assert strategy.compute_signal(context, data) == "SELL"

    def test_factor_values_logged(self, caplog):
        """Test all factor values appear in logs."""
        strategy = MultiFactorStrategy(log_path="/tmp/test.jsonl")
        strategy.compute_signal(context, data)
        # Verify log contains ema, rsi, macd, factors dict
```

### References

- [Source: docs/architecture.md#Novel-Pattern-Log-Based-Validation-Architecture]
- [Source: docs/epics/epic-6-initial-strategy-validation-4-strategies.md#Story-6.4]
- [Source: docs/prd.md#FR58-Strategy-Validation]

## Dev Agent Record

### Context Reference

- docs/sprint-artifacts/6-4-initial-strategy-validation-story-4.context.xml

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

- `tests/validation/strategies/rustybt/multi_factor.py` - RustyBT Multi-Factor strategy implementation
- `tests/validation/strategies/bt_strategies/multi_factor.py` - Backtrader Multi-Factor strategy implementation
- `tests/validation/test_multi_factor_strategy.py` - Unit tests for Multi-Factor strategy (25 tests)
- `tests/validation/strategies/rustybt/__init__.py` - Updated to export MultiFactorStrategy
- `tests/validation/strategies/bt_strategies/__init__.py` - Updated to export MultiFactorStrategy

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-28 | Story drafted from Epic 6 specification | SM Agent |
| 2025-11-29 | Implemented dual Multi-Factor strategies and tests | Dev Agent |

## Senior Developer Review (AI)

- **Reviewer**: Antigravity (AI Senior Developer)
- **Date**: 2025-11-29
- **Outcome**: **Approve**
- **Summary**: The implementation of the Multi-Factor strategy (EMA + RSI + MACD) in both rustybt and Backtrader frameworks is complete and correct. The code follows the required patterns, correctly implements the factor scoring logic, and handles the complexity of multiple indicators. The test suite is comprehensive and verifies equivalence, including the known design differences in RSI and MACD calculations.

### Key Findings

- **HIGH Severity**: None.
- **MEDIUM Severity**: None.
- **LOW Severity**: None.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| 1 | rustybt Multi-Factor implementation exists | IMPLEMENTED | `tests/validation/strategies/rustybt/multi_factor.py` |
| 2 | Backtrader Multi-Factor implementation exists | IMPLEMENTED | `tests/validation/strategies/bt_strategies/multi_factor.py` |
| 3 | Factor scoring system implemented | IMPLEMENTED | `tests/validation/test_multi_factor_strategy.py` (TestFactorScoring) |
| 4 | Strategy audit checklist passed | IMPLEMENTED | `tests/validation/test_multi_factor_strategy.py` (TestStrategyAuditChecklist) |
| 5 | Log individual factor values for debugging | IMPLEMENTED | Verified in `test_log_output_format` and `test_log_output_matches_schema` |
| 6 | Unit tests verify all indicators and logic | IMPLEMENTED | `tests/validation/test_multi_factor_strategy.py` (25 tests passed) |

**Summary**: 6 of 6 acceptance criteria fully implemented.

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|----------|
| 1. Create rustybt Multi-Factor strategy | [x] | VERIFIED COMPLETE | `tests/validation/strategies/rustybt/multi_factor.py` |
| 2. Create Backtrader Multi-Factor strategy | [x] | VERIFIED COMPLETE | `tests/validation/strategies/bt_strategies/multi_factor.py` |
| 3. Implement factor scoring system | [x] | VERIFIED COMPLETE | `tests/validation/test_multi_factor_strategy.py` |
| 4. Verify strategy equivalence | [x] | VERIFIED COMPLETE | `tests/validation/test_multi_factor_strategy.py` |
| 5. Validate log output | [x] | VERIFIED COMPLETE | `tests/validation/test_multi_factor_strategy.py` |
| 6. Write unit tests | [x] | VERIFIED COMPLETE | `tests/validation/test_multi_factor_strategy.py` |

**Summary**: 6 of 6 completed tasks verified.

### Zero-Mock Enforcement

| Check Type | File:Line | Status | Details |
|------------|-----------|--------|---------|
| Hardcoded Returns | N/A | PASS | No hardcoded returns found in production code. |
| Always-Succeeding Validations | N/A | PASS | No dummy validations found. |
| Mock Patterns | N/A | PASS | No mock/stub patterns found in production code. |
| Empty Error Handlers | N/A | PASS | No empty error handlers found. |
| Test Quality | `tests/validation/test_multi_factor_strategy.py` | PASS | Tests use real framework execution and meaningful assertions. |

**Summary**: ZERO-MOCK STATUS: PASS (0 violations)

### Orphaned Files Enforcement

| File Path | Issue Type | Severity | Suggested Location |
|-----------|------------|----------|--------------------|
| `tests/validation/strategies/rustybt/multi_factor.py` | None | PASS | Correctly placed. |
| `tests/validation/strategies/bt_strategies/multi_factor.py` | None | PASS | Correctly placed. |
| `tests/validation/test_multi_factor_strategy.py` | None | PASS | Correctly placed. |

**Summary**: ORPHAN STATUS: PASS (0 violations)

### Action Items

**Code Changes Required:**
- None.

**Advisory Notes:**
- Note: The RSI and MACD calculation differences (simple average vs Wilder's smoothing, EMA initialization) are known design choices and are acceptable for this validation phase.
