# rustybt Design Differences

This document catalogues known DESIGN differences between rustybt and Backtrader.
These are intentional implementation choices, not bugs.

## Classification Criteria

- **DESIGN**: Intentional difference in implementation approach
- **BUG**: Unintentional error that needs fixing

All differences listed here are classified as DESIGN and do not require fixes.

---

## Signal Computation (Layer 2)

### DD-001: RSI Calculation Method

**Status**: DESIGN
**Affected Strategies**: Momentum, Multi-Factor
**Framework Versions**: rustybt 0.1.x, Backtrader 1.9.x

**rustybt Implementation**:
```python
# Simple average of gains/losses
avg_gain = sum(gains) / period
avg_loss = sum(losses) / period
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
```

**Backtrader Implementation**:
- Uses Wilder's exponential smoothing method
- Produces smoother RSI values
- Industry-standard approach for RSI

**Rationale**:
Both methods are mathematically valid RSI calculations. The simple average method
is computationally simpler and easier to verify. The difference is most noticeable
in the first few periods after initialization but converges over time.

**User Guidance**:
- Expect minor RSI value differences, especially early in the data series
- Signal timing may differ slightly near threshold crossings
- Both implementations correctly identify overbought/oversold conditions

---

### DD-002: MACD EMA Initialization

**Status**: DESIGN
**Affected Strategies**: Multi-Factor
**Framework Versions**: rustybt 0.1.x, Backtrader 1.9.x

**rustybt Implementation**:
```python
# Initialize EMA with SMA of first 'period' values
initial_sma = sum(prices[:period]) / period
# Then apply EMA formula from there
ema = initial_sma
for price in prices[period:]:
    ema = (price - ema) * multiplier + ema
```

**Backtrader Implementation**:
- May use different EMA seeding method
- Different handling of initial "warm-up" period

**Rationale**:
The EMA initialization method affects early values but converges after sufficient
data. This is a common difference between financial libraries.

**User Guidance**:
- MACD values may differ in the first ~2x slow_period bars
- Signal line crossovers may occur at slightly different times
- Long-running strategies show convergent behavior

---

## Data Handling (Layer 1)

### DD-003: Timestamp Precision

**Status**: DESIGN
**Affected Strategies**: All
**Framework Versions**: rustybt 0.1.x, Backtrader 1.9.x

**rustybt Implementation**:
- Uses ISO8601 format with millisecond precision
- `datetime.now().isoformat(timespec="milliseconds")`

**Backtrader Implementation**:
- Uses `datetime.now().isoformat()` (microsecond precision)

**Rationale**:
Timestamp precision differs but does not affect strategy logic. Millisecond
precision is sufficient for backtesting purposes.

**User Guidance**:
- Timestamps in logs may have different precision
- Does not affect signal generation or order execution

---

## Order Management (Layer 3)

### DD-004: Order Sizing Rounding

**Status**: DESIGN
**Affected Strategies**: All
**Framework Versions**: rustybt 0.1.x, Backtrader 1.9.x

**rustybt Implementation**:
- Uses target_percent directly
- Fractional orders supported

**Backtrader Implementation**:
- `order_target_percent()` may round to integer shares
- Rounding behavior depends on broker configuration

**Rationale**:
Order sizing differences are common between frameworks due to different
broker simulation approaches. Both approaches are valid.

**User Guidance**:
- Position sizes may differ slightly
- Final portfolio values may have minor differences due to rounding
- For validation, focus on signal alignment rather than exact position sizes

---

## Summary

| ID | Component | Affected Strategies | Impact |
|----|-----------|---------------------|--------|
| DD-001 | RSI Calculation | Momentum, Multi-Factor | Minor signal timing |
| DD-002 | MACD EMA Init | Multi-Factor | Early period values |
| DD-003 | Timestamp | All | Cosmetic only |
| DD-004 | Order Sizing | All | Minor position size |

All DESIGN differences have been reviewed and accepted. They do not indicate
errors in the rustybt implementation.

---

## Change Log

| Date | Change |
|------|--------|
| 2025-11-29 | Initial documentation of DESIGN differences |
