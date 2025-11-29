# Investigation Workflow Guide

This guide explains how to investigate, classify, and resolve discrepancies discovered by the validation framework.

## Overview: The Investigation Process

When validation finds discrepancies between rustybt and Backtrader, you need to:

1. **Investigate** - Understand what differs and why
2. **Classify** - Determine if it's a BUG (requires fix) or DESIGN (intentional)
3. **Resolve** - Either fix the bug or document the design difference

```
Discrepancy Found
        │
        ▼
┌───────────────────┐
│   INVESTIGATE     │ ← Read logs, compare values
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│    CLASSIFY       │ ← BUG or DESIGN?
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
┌───────┐   ┌───────────┐
│  BUG  │   │  DESIGN   │
└───┬───┘   └─────┬─────┘
    │             │
    ▼             ▼
┌──────────┐  ┌──────────────┐
│ Fix Code │  │ Document in  │
│ Re-verify│  │ design-diffs │
└──────────┘  └──────────────┘
```

## Reading Discrepancy Reports

### Report Structure

After running validation, view discrepancies:

```bash
rustybt-validate report <session_id>
```

Example output:
```
# Validation Report: 20251129-120000-sma_crossover

## Summary
- Strategy: sma_crossover
- Status: NEEDS_INVESTIGATION
- Total Findings: 3 discrepancies

## Findings

### FIND-001: Layer 2 (Signals) - Unclassified
- Event: indicator_values
- Asset: AAPL
- Timestamp: 2025-01-15T10:30:00
- Expected (Backtrader): fast_sma = 150.234567
- Actual (rustybt):      fast_sma = 150.234568
- Difference: 0.000001 (within tolerance: YES)
- Notes: Floating-point precision difference

### FIND-002: Layer 3 (Orders) - Unclassified
- Event: order_created
- Asset: GOOG
- Timestamp: 2025-01-16T11:00:00
- Expected: quantity = 100
- Actual:   quantity = 99
- Difference: 1 share (within tolerance: NO)
- Notes: Possible rounding difference in position sizing
```

### Understanding Fields

| Field | Description |
|-------|-------------|
| Layer | Validation layer (data, signals, orders, broker, portfolio) |
| Event | Type of logged event (bar_received, signal_computed, etc.) |
| Asset | Symbol affected |
| Expected | Value from Backtrader (reference) |
| Actual | Value from rustybt (under test) |
| Tolerance | Whether difference is within acceptable range |

## CLI Investigation Commands

### View All Findings

```bash
# Start interactive investigation
rustybt-validate investigate <session_id>

# Example
rustybt-validate investigate 20251129-120000-sma_crossover
```

### Filter by Layer

```bash
# Focus on signal discrepancies
rustybt-validate investigate <session_id> --layer signals

# Focus on order discrepancies
rustybt-validate investigate <session_id> --layer orders
```

### Filter by Status

```bash
# Show only unclassified findings
rustybt-validate investigate <session_id> --unclassified

# Show only BUG findings
rustybt-validate investigate <session_id> --bugs

# Show only DESIGN findings
rustybt-validate investigate <session_id> --design
```

### Jump to Specific Finding

```bash
# Go directly to a finding
rustybt-validate investigate <session_id> --finding FIND-002
```

## BUG vs DESIGN Classification

### Decision Tree

```
                    Discrepancy Found
                           │
                           ▼
          ┌─────────────────────────────────┐
          │ Is the rustybt value incorrect? │
          │  (e.g., math error, wrong logic)│
          └───────────────┬─────────────────┘
                          │
              ┌───────────┴───────────┐
              │ YES                   │ NO
              ▼                       ▼
          ┌───────┐    ┌─────────────────────────────┐
          │  BUG  │    │ Is this an intentional      │
          └───────┘    │ design decision in rustybt? │
                       └─────────────┬───────────────┘
                                     │
                         ┌───────────┴───────────┐
                         │ YES                   │ NO
                         ▼                       ▼
                   ┌───────────┐          ┌───────────────┐
                   │  DESIGN   │          │ Investigate   │
                   └───────────┘          │ further...    │
                                          └───────────────┘
```

### BUG Classification Criteria

Classify as **BUG** when:
- rustybt produces mathematically incorrect results
- Logic error in signal generation
- Order quantity or direction is wrong
- Position tracking is incorrect
- Data transformation is corrupted

**Examples:**
- SMA calculates with wrong period
- Order placed as BUY when should be SELL
- Position shows 100 shares when should be 0
- Price data off by orders of magnitude

### DESIGN Classification Criteria

Classify as **DESIGN** when:
- Difference is intentional (documented design choice)
- Precision difference within tolerance
- Timing difference that doesn't affect correctness
- Different default values that are both valid

**Examples:**
- rustybt uses Decimal precision, Backtrader uses float
- Order execution at bar open vs close (both valid)
- Different commission rounding (both correct within cents)
- Timestamp format differences

## Classifying Findings

### Classify as BUG

```bash
rustybt-validate classify FIND-002 \
    --type BUG \
    --rationale "Order quantity is off by 1 due to integer truncation instead of rounding in position sizing calculation. See rustybt/portfolio/sizing.py:142"
```

### Classify as DESIGN

```bash
rustybt-validate classify FIND-001 \
    --type DESIGN \
    --rationale "Floating-point precision difference (1e-6) is expected due to rustybt using Decimal internally while Backtrader uses float64. This is within tolerance and does not affect trading decisions."
```

### Rationale Requirements

**For BUG classifications:**
- Describe what is wrong
- Identify root cause
- Reference source file and line number
- Explain expected correct behavior

**For DESIGN classifications:**
- Explain the design decision
- Reference architecture documentation if applicable
- Explain why difference is acceptable
- Note any user-facing implications

## Resolving Findings

### Bug Fix Workflow

1. **Identify Root Cause**
   ```bash
   # Review the finding details
   rustybt-validate investigate <session_id> --finding FIND-002
   ```

2. **Fix the Code**
   ```python
   # Before (bug):
   quantity = int(portfolio_value / price)

   # After (fix):
   quantity = round(portfolio_value / price)
   ```

3. **Verify the Fix**
   ```bash
   rustybt-validate verify FIND-002
   ```

   Expected output:
   ```
   Verifying fix for FIND-002...
   Re-executing rustybt strategy... done
   Re-executing Backtrader strategy... done
   Comparing Layer 3 (Orders)...

   Result: FIXED
   - Previous: quantity = 99
   - Current:  quantity = 100
   - Expected: quantity = 100

   Finding FIND-002 marked as RESOLVED.
   ```

4. **Create Regression Test**
   ```python
   # tests/validation/regression/test_find_002.py
   def test_order_quantity_rounding():
       """Regression test for FIND-002: Order quantity rounding."""
       # ... test implementation
   ```

### Design Documentation Workflow

1. **Classify the Finding**
   ```bash
   rustybt-validate classify FIND-001 --type DESIGN --rationale "..."
   ```

2. **Add to Design Differences Doc**

   Update `docs/validation/design-differences.md`:
   ```markdown
   ### Decimal Precision vs Float64

   **Finding:** FIND-001
   **Layer:** Signals
   **Difference:** SMA values differ by ~1e-6

   **Explanation:** rustybt uses Python's Decimal type for all financial
   calculations to ensure audit-compliant precision. Backtrader uses
   numpy's float64. This causes small precision differences that do not
   affect trading decisions.

   **User Impact:** None - differences are below meaningful thresholds.
   ```

3. **Generate User Documentation**
   ```bash
   rustybt-validate docs generate-design-diffs
   ```

## Example: Investigating a BUG

### Scenario: Signal Computed on Wrong Bar

**Finding:**
```
FIND-003: Layer 2 (Signals) - Unclassified
- Event: signal_generated
- Asset: AAPL
- Timestamp: 2025-01-15T10:30:00
- Expected (Backtrader): signal = BUY
- Actual (rustybt):      signal = HOLD
- Notes: Crossover detection missed
```

### Step 1: View Indicator Values

```bash
rustybt-validate investigate <session_id> --finding FIND-003
```

Output:
```
Finding Details:
- rustybt fast_sma: 150.50
- rustybt slow_sma: 150.45
- Backtrader fast_sma: 150.50
- Backtrader slow_sma: 150.45

Previous bar:
- rustybt fast_sma: 150.40
- rustybt slow_sma: 150.55  <-- Different from Backtrader
- Backtrader fast_sma: 150.40
- Backtrader slow_sma: 150.48
```

### Step 2: Trace Root Cause

Look at the SMA calculation in `tests/validation/strategies/rustybt/sma_crossover.py`:

```python
def _calculate_sma(self, period: int) -> float | None:
    if len(self._prices) < period:
        return None
    prices_list = list(self._prices)
    return sum(prices_list[-period:]) / period  # Bug: using wrong slice
```

Compare with Backtrader which uses `bt.indicators.SMA` correctly.

### Step 3: Classify and Fix

```bash
rustybt-validate classify FIND-003 \
    --type BUG \
    --rationale "Off-by-one error in SMA calculation. prices_list[-period:] should be prices_list[-period:] but the deque maxlen was set incorrectly, causing the wrong values to be used."
```

Fix the code and verify:

```bash
rustybt-validate verify FIND-003
```

## Example: Documenting a DESIGN Difference

### Scenario: Order Execution Timing

**Finding:**
```
FIND-004: Layer 4 (Broker) - Unclassified
- Event: fill_executed
- Asset: TSLA
- Timestamp: 2025-01-20T14:00:00
- Expected (Backtrader): fill_price = 250.00 (bar open)
- Actual (rustybt):      fill_price = 251.50 (bar close)
```

### Investigation

This is a known design difference: rustybt executes market orders at bar close, while Backtrader executes at bar open.

### Classification

```bash
rustybt-validate classify FIND-004 \
    --type DESIGN \
    --rationale "rustybt uses bar close for market order execution to avoid lookahead bias. Backtrader uses bar open. Both are valid simulation approaches. See architecture.md#order-execution-model for design rationale."
```

### Documentation

Add to `design-differences.md`:
```markdown
### Order Execution Timing

| Framework | Market Order Execution |
|-----------|----------------------|
| rustybt | Bar close price |
| Backtrader | Bar open price |

**Rationale:** rustybt uses bar close to prevent lookahead bias...
```

## Best Practices

### Reproducibility

1. **Record exact versions**
   ```bash
   rustybt-validate session show <session_id>
   ```
   Note rustybt and Backtrader versions used.

2. **Save the data fixture**
   ```bash
   cp tests/validation/fixtures/validation_data.parquet \
      validation-sessions/<session_id>/data_backup.parquet
   ```

3. **Document environment**
   ```bash
   pip freeze > validation-sessions/<session_id>/requirements.txt
   ```

### Evidence Gathering

1. **Export raw logs**
   ```bash
   rustybt-validate log export <session_id> --format jsonl
   ```

2. **Create screenshots** of key discrepancies

3. **Link to source commits**
   ```bash
   git log --oneline -5
   ```

### Source Code Linking

When classifying bugs, include:
- File path: `rustybt/validation/base_strategy.py:142`
- Git commit: `abc123`
- Line number and context

### Root Cause Analysis

Ask these questions:
1. What is the immediate cause of the discrepancy?
2. What is the underlying reason for that cause?
3. Are there other places with the same issue?
4. Could this have been prevented?

## Next Steps

- **[Strategy Implementation Guide](strategy-implementation-guide.md)** - Add more strategies to validate
- **[Design Differences](design-differences.md)** - View all documented design differences
- **[Bug Fixes](bug-fixes.md)** - View all bugs discovered and fixed
- **[Getting Started](getting-started.md)** - Return to basics
