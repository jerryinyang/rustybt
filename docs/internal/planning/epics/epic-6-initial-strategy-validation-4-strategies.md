# Epic 6: Initial Strategy Validation (4 Strategies)

**Goal:** Implement and validate 4 trading strategies across all 5 layers to prove framework correctness.

**Architecture References:**
- Strategy Implementations (Architecture pg 57-68)
- ValidatedStrategy Base Classes (Architecture pg 163-179)

**Value:** Concrete proof of rustybt correctness through validated strategy implementations.

**FRs Covered:** FR55-FR59 (Strategy Validation - 5 FRs)

---

## Story 6.1: Implement SMA Crossover Strategy (Dual)

As a developer,
I want SMA Crossover strategy implemented in both frameworks,
So that this foundational strategy can be validated.

**Acceptance Criteria:**

**Given** the strategy template
**When** SMA Crossover is implemented
**Then** rustybt implementation exists:

**tests/validation/strategies/rustybt/sma_crossover.py:**
```python
"""SMA Crossover Strategy - rustybt implementation."""
from rustybt.validation.base_strategy import RustyBTValidatedStrategy
from rustybt.validation.decorators import log_signal, log_order

class SMACrossoverStrategy(RustyBTValidatedStrategy):
    """
    Simple Moving Average Crossover Strategy.

    Buy when fast SMA crosses above slow SMA.
    Sell when fast SMA crosses below slow SMA.
    """

    def __init__(self, log_path, fast_period=10, slow_period=30):
        super().__init__(log_path)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.fast_sma = None
        self.slow_sma = None

    def initialize(self, context):
        super().initialize(context)
        # Set up SMA indicators
        self.fast_sma = self.add_indicator('sma', period=self.fast_period)
        self.slow_sma = self.add_indicator('sma', period=self.slow_period)

    @log_signal()
    def compute_signal(self, context, data):
        """Compute crossover signal."""
        if self.fast_sma[-1] > self.slow_sma[-1] and self.fast_sma[-2] <= self.slow_sma[-2]:
            return "BUY"
        elif self.fast_sma[-1] < self.slow_sma[-1] and self.fast_sma[-2] >= self.slow_sma[-2]:
            return "SELL"
        return "HOLD"

    @log_order()
    def handle_data(self, context, data):
        super().handle_data(context, data)

        signal = self.compute_signal(context, data)

        if signal == "BUY" and not self.portfolio.positions:
            self.order_target_percent(data.current, 1.0)
        elif signal == "SELL" and self.portfolio.positions:
            self.order_target_percent(data.current, 0.0)
```

**And** Backtrader implementation exists:

**tests/validation/strategies/backtrader/sma_crossover.py:**
```python
"""SMA Crossover Strategy - Backtrader implementation."""
import backtrader as bt
from tests.validation.strategies.backtrader.base_validated import BacktraderValidatedStrategy

class SMACrossoverStrategy(BacktraderValidatedStrategy):
    """Backtrader SMA Crossover - logically equivalent to rustybt version."""

    params = (
        ('log_path', None),
        ('fast_period', 10),
        ('slow_period', 30),
    )

    def __init__(self):
        super().__init__()
        self.fast_sma = bt.indicators.SMA(period=self.params.fast_period)
        self.slow_sma = bt.indicators.SMA(period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)

    def next(self):
        super().next()

        self._log_signal(self.fast_sma[0], self.slow_sma[0])

        if self.crossover > 0:  # Fast crossed above slow
            if not self.position:
                self.order_target_percent(target=1.0)
        elif self.crossover < 0:  # Fast crossed below slow
            if self.position:
                self.order_target_percent(target=0.0)
```

**And** strategy audit checklist passed:
- [ ] Same indicator calculations
- [ ] Same signal logic
- [ ] Same order sizing
- [ ] Same entry/exit conditions

**And** unit tests verify isolated logic

**Prerequisites:** Story 2.1, Story 2.2 (base classes)

**Technical Notes:**
- Reference Architecture Strategy Implementations (pg 57-68)
- Use default parameters: fast=10, slow=30
- Log all indicator values for comparison
- Keep logic simple and identical

---

## Story 6.2: Implement Mean Reversion Strategy (Dual)

As a developer,
I want Mean Reversion strategy implemented in both frameworks,
So that z-score based strategies can be validated.

**Acceptance Criteria:**

**Given** the strategy template
**When** Mean Reversion is implemented
**Then** both implementations exist with:

**Strategy logic:**
```python
"""
Mean Reversion Strategy (z-score based)

Buy when z-score < -2 (price significantly below mean)
Sell when z-score > 2 (price significantly above mean)
Exit when z-score returns to 0 (mean reversion complete)
"""
```

**Key parameters:**
- lookback_period: 20 (for mean/std calculation)
- entry_threshold: 2.0 (z-score threshold for entry)
- exit_threshold: 0.0 (z-score threshold for exit)

**And** rustybt implementation: `tests/validation/strategies/rustybt/mean_reversion.py`

**And** Backtrader implementation: `tests/validation/strategies/backtrader/mean_reversion.py`

**And** strategy audit checklist passed

**And** unit tests verify z-score calculation logic

**Prerequisites:** Story 6.1 (SMA Crossover establishes pattern)

**Technical Notes:**
- Z-score = (price - mean) / std_dev
- Use rolling window for mean/std calculation
- Log z-score values for signal comparison
- Handle division by zero (std_dev = 0)

---

## Story 6.3: Implement Momentum Strategy (Dual)

As a developer,
I want Momentum strategy with RSI and trailing stops implemented,
So that more complex order management can be validated.

**Acceptance Criteria:**

**Given** the strategy template
**When** Momentum is implemented
**Then** both implementations exist with:

**Strategy logic:**
```python
"""
Momentum Strategy (RSI + Trailing Stops)

Buy when RSI < 30 (oversold, expecting upward momentum)
Sell when RSI > 70 (overbought, expecting downward momentum)
Use 5% trailing stop for risk management
"""
```

**Key parameters:**
- rsi_period: 14
- oversold_threshold: 30
- overbought_threshold: 70
- trailing_stop_pct: 0.05 (5%)

**And** trailing stop logic:
```python
def update_trailing_stop(self, current_price):
    if self.position_type == "LONG":
        new_stop = current_price * (1 - self.trailing_stop_pct)
        self.stop_price = max(self.stop_price, new_stop)
    elif self.position_type == "SHORT":
        new_stop = current_price * (1 + self.trailing_stop_pct)
        self.stop_price = min(self.stop_price, new_stop)
```

**And** rustybt implementation: `tests/validation/strategies/rustybt/momentum.py`

**And** Backtrader implementation: `tests/validation/strategies/backtrader/momentum.py`

**And** strategy audit checklist passed

**Prerequisites:** Story 6.2 (Mean Reversion)

**Technical Notes:**
- RSI calculation may differ between frameworks (DESIGN)
- Trailing stop implementation is key validation point
- Log stop price updates for comparison
- Handle position size correctly with stops

---

## Story 6.4: Implement Multi-Factor Strategy (Dual)

As a developer,
I want Multi-Factor strategy combining EMA + RSI + MACD implemented,
So that complex multi-indicator strategies can be validated.

**Acceptance Criteria:**

**Given** the strategy template
**When** Multi-Factor is implemented
**Then** both implementations exist with:

**Strategy logic:**
```python
"""
Multi-Factor Strategy (EMA + RSI + MACD)

Buy when ALL conditions met:
1. Price > EMA(50) (uptrend)
2. RSI > 50 but < 70 (bullish but not overbought)
3. MACD > Signal line (momentum confirmation)

Sell when ANY condition fails or RSI > 80 (overbought exit)
"""
```

**Key parameters:**
- ema_period: 50
- rsi_period: 14
- macd_fast: 12
- macd_slow: 26
- macd_signal: 9

**And** factor scoring:
```python
def compute_factors(self, data):
    factors = {
        "trend": 1 if data.close > self.ema[-1] else 0,
        "momentum_rsi": 1 if 50 < self.rsi[-1] < 70 else 0,
        "momentum_macd": 1 if self.macd[-1] > self.macd_signal[-1] else 0,
    }
    return factors
```

**And** rustybt implementation: `tests/validation/strategies/rustybt/multi_factor.py`

**And** Backtrader implementation: `tests/validation/strategies/backtrader/multi_factor.py`

**And** strategy audit checklist passed

**Prerequisites:** Story 6.3 (Momentum)

**Technical Notes:**
- Log individual factor values for debugging
- MACD calculation may differ (DESIGN candidate)
- All three factors must align for entry
- Any factor failing triggers exit

---

## Story 6.5: Execute Full Validation for All 4 Strategies

As a developer,
I want all 4 strategies validated across all 5 layers,
So that framework correctness is proven comprehensively.

**Acceptance Criteria:**

**Given** all 4 strategies implemented
**When** full validation is executed
**Then** each strategy passes all 5 layers:

**Validation matrix:**
```
Strategy        | L1 Data | L2 Signals | L3 Orders | L4 Broker | L5 Portfolio | Overall
----------------|---------|------------|-----------|-----------|--------------|--------
SMA Crossover   | ✓       | ✓          | ✓         | ✓         | ✓            | PASS
Mean Reversion  | ✓       | ✓          | ✓         | ✓         | ✓            | PASS
Momentum        | ✓       | ✓ (2 DESIGN)| ✓        | ✓         | ✓            | PASS
Multi-Factor    | ✓       | ✓ (1 DESIGN)| ✓        | ✓         | ✓            | PASS
```

**And** all BUG-classified findings are fixed and verified

**And** all DESIGN-classified findings are documented

**And** regression tests exist for all fixed bugs

**And** validation report generated:
```bash
rustybt-validate report --all
#
# === rustybt Validation Report ===
#
# Strategies Validated: 4
# Layers Tested: 5 per strategy (20 total)
#
# Results:
#   Passed: 20 layers
#   Failed: 0 layers
#
# Findings:
#   Total: 12
#   BUG: 5 (all fixed and verified)
#   DESIGN: 7 (all documented)
#
# Confidence Level: HIGH
#
# Documentation:
#   - Design differences: docs/validation/design-differences.md
#   - Bug fixes: docs/validation/bug-fixes.md
#   - Regression tests: tests/validation/regression/
```

**Prerequisites:** Stories 6.1-6.4 (all strategies), Epic 4 (test suite), Epic 5 (investigation)

**Technical Notes:**
- This is the culminating validation story
- May require multiple sessions per strategy
- Document all findings regardless of classification
- Generate comprehensive validation report

---
