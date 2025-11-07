# Diagnostic Findings: Off-By-One Data Shift Bug

**Bug ID**: RUSTYBT-DATA-001
**Date**: 2025-11-07
**Diagnostic Script**: `diagnostics/timestamp_tracer.py`
**Branch**: `fix/20251107-105919-history-off-by-one-data-shift`

---

## Executive Summary

✅ **ROOT CAUSE CONFIRMED**: The simulation clock yields `current_dt` that is **+1 day ahead** of the actual bar being processed.

**The Problem**:
- `data.current_dt` reports date X
- But `data.history()` returns bar for date X-2
- And `data.current()` returns price for date X-1
-  And `current_session` reports date X-1

**Impact**: ALL daily-frequency backtests return incorrect historical data, making backtest results unreliable.

---

## Diagnostic Evidence

###  Test Configuration
- **Bundle**: binance-spot-1d
- **Asset**: BTC/USDT (sid=770)
- **Date Range**: 2020-01-01 to 2020-01-10
- **Data Frequency**: daily

### Bundle Reference Data (Ground Truth)

```
2020-01-01: open=7195.24, close=7200.85  ← Row 0
2020-01-02: open=7200.77, close=6965.71  ← Row 1
2020-01-03: open=6965.49, close=7344.96  ← Row 2
2020-01-04: open=7345.00, close=7354.11  ← Row 3
2020-01-05: open=7354.19, close=7358.75  ← Row 4
2020-01-06: open=7357.64, close=7758.00  ← Row 5
2020-01-07: open=7758.90, close=8145.28  ← Row 6
2020-01-08: open=8145.92, close=8055.98  ← Row 7
2020-01-09: open=8054.72, close=7817.76  ← Row 8
2020-01-10: open=7817.74, close=8197.02  ← Row 9
```

###  Backtest Timestamps vs Actual Data

| Call # | current_dt | current_session | current() close | history() close | Matches Bundle Row |
|--------|------------|-----------------|-----------------|-----------------|-------------------|
| 1      | 2020-01-02 | 2020-01-01      | 7195.23         | 7195.23         | **2019-12-31** (NOT IN EXPORT!) |
| 2      | 2020-01-03 | 2020-01-02      | 7200.85         | 7200.85         | **Row 0** (2020-01-01) |
| 3      | 2020-01-04 | 2020-01-03      | 6965.71         | 6965.71         | **Row 1** (2020-01-02) |
| 4      | 2020-01-05 | 2020-01-04      | 7344.96         | 7344.96         | **Row 2** (2020-01-03) |
| 5      | 2020-01-06 | 2020-01-05      | 7354.11         | 7354.11         | **Row 3** (2020-01-04) |
| 6      | 2020-01-07 | 2020-01-06      | 7358.75         | 7358.75         | **Row 4** (2020-01-05) |
| 7      | 2020-01-08 | 2020-01-07      | 7758.00         | 7758.00         | **Row 5** (2020-01-06) |
| 8      | 2020-01-09 | 2020-01-08      | 8145.28         | 8145.28         | **Row 6** (2020-01-07) |
| 9      | 2020-01-10 | 2020-01-09      | 8055.98         | 8055.98         | **Row 7** (2020-01-08) |
| 10     | 2020-01-11 | 2020-01-10      | 7817.76         | 7817.76         | **Row 8** (2020-01-09) |

###  Key Observation

**PATTERN**: `current_dt` is ALWAYS +1 day ahead of `current_session`, and the data returned matches `current_session` date.

- When `current_dt = 2020-01-03`:
  - `current_session = 2020-01-02`
  - Data returned is for `2020-01-01` (the bar for `current_session - 1`)

**Offset Summary**:
- `current_dt` to actual bar: **-2 days**
- `current_session` to actual bar: **-1 day**

---

## Root Cause Analysis

### The Issue

In daily-frequency mode, there's a misalignment between three critical timestamps:

1. **simulation_dt** (set by `AlgorithmSimulator`) - What the clock yields
2. **current_dt** (property in `BarData`) - What the user sees via `data.current_dt`
3. **_get_current_minute()** (internal method) - What's used for data fetching

### The Code Flow

#### Step 1: Clock Yields Timestamp
```python
# rustybt/gens/sim_engine.pyx:78-79
for idx, session_nano in enumerate(self.sessions_nanos):
    yield pd.Timestamp(session_nano, tz='UTC'), SESSION_START
```

For daily mode, the clock yields the **session date** (midnight UTC).

#### Step 2: Simulation Sets current_dt
```python
# rustybt/gens/tradesimulation.py:113
self.simulation_dt = dt_to_use  # This is the session_nano from clock
```

#### Step 3: BarData Exposes current_dt
```python
# rustybt/_protocol.pyx:700-702
property current_dt:
    def __get__(self):
        return self.simulation_dt_func()  # Returns raw simulation_dt
```

**User sees this as `data.current_dt`** - This is the PROBLEM! It's the NEXT session, not the current bar's session.

#### Step 4: Data Fetching Uses Different Timestamp
```python
# rustybt/_protocol.pyx:177-186
cdef _get_current_minute(self):
    dt = self.simulation_dt_func()  # Get same simulation_dt

    if self._daily_mode:
        # Convert to SESSION LABEL (previous session!)
        dt = self.data_portal.trading_calendar.minute_to_session(dt)

    return dt  # This is what's used for data fetching!
```

When `simulation_dt = 2020-01-03 00:00:00`, `minute_to_session()` converts it to `2020-01-02` (previous session), and then data is fetched for that session.

### The Bug

**`current_dt` property returns the NEXT session's timestamp**, but data fetching uses the CURRENT session's timestamp (via `minute_to_session` conversion).

This creates a +1 day offset between what the user sees (`current_dt`) and what data they get.

---

## Why This Happens

### Trading Calendar Session Logic

In trading, a "session" is a trading day. The session starts at midnight and lasts 24 hours (for 24/7 markets).

When the simulation clock yields `2020-01-03 00:00:00`:
- This timestamp represents the **START** of the 2020-01-03 session
- But `minute_to_session(2020-01-03 00:00:00)` returns `2020-01-02` (the session this minute belongs to)
- This is because midnight UTC is considered the **close** of the previous session, not the open of the next session

### The Misalignment

The code has two competing interpretations:
1. **`current_dt`**: Treats `simulation_dt` as "we're in this session" (forward-looking)
2. **`_get_current_minute()`**: Treats `simulation_dt` as "midnight of next session" (backward-looking)

For daily mode, only ONE bar should be emitted per session. But which timestamp should represent that bar?

**Current behavior**: Clock yields midnight of NEXT session, but data fetch treats it as end of PREVIOUS session.

**Expected behavior**: The timestamp should consistently represent the SAME session for both `current_dt` and data fetching.

---

## Proposed Solutions

### Option 1: Fix `current_dt` Property (Recommended)

Make `current_dt` consistent with `_get_current_minute()`:

```python
# rustybt/_protocol.pyx
property current_dt:
    def __get__(self):
        return self._get_current_minute()  # Use same logic as data fetching!
```

**Pros**:
- Simple one-line fix
- Makes `current_dt` match the actual bar being processed
- Consistent with how data is fetched

**Cons**:
- Changes what users see in `data.current_dt`
- Potentially breaking change for existing strategies

### Option 2: Change Clock Emission Logic

Make the clock yield the CURRENT session's timestamp, not the NEXT session's:

```python
# rustybt/gens/sim_engine.pyx
# Instead of yielding session_nano (midnight of session)
# Yield session_close_nano (last minute of session)
```

**Pros**:
- Aligns clock with intuitive "current bar" semantics
- No change to `_protocol.pyx`

**Cons**:
- Requires changes to Cython clock code
- More complex, affects multiple systems

### Option 3: Remove `minute_to_session` Conversion

Keep `current_dt` as-is, but change data fetching logic to NOT convert in daily mode:

```python
# rustybt/_protocol.pyx:_get_current_minute
if self._daily_mode:
    # Don't convert - use raw simulation_dt
    pass
else:
    # Only convert for minute mode
    dt = self.data_portal.trading_calendar.minute_to_session(dt)
```

**Pros**:
- Keeps `current_dt` unchanged
- Fixes data alignment

**Cons**:
- May break other assumptions in data portal

---

## Recommendation

**Go with Option 1** - Fix the `current_dt` property.

**Rationale**:
1. Simplest fix with minimal code changes
2. Makes behavior consistent and predictable
3. The "breaking change" is actually a bug fix - strategies relying on the old behavior were already getting wrong data

**Migration Path**:
1. Implement fix
2. Add comprehensive tests
3. Document the change in CHANGELOG with clear migration notes
4. Add deprecation warning if needed

---

## Next Steps

1. ✅ Diagnostic complete - Root cause confirmed
2. ⏭️ Implement Option 1 fix to `_protocol.pyx`
3. ⏭️ Write comprehensive tests
4. ⏭️ Update documentation
5. ⏭️ Request QA review
6. ⏭️ Merge after approval

---

## Files Referenced

- **Diagnostic Script**: `diagnostics/timestamp_tracer.py`
- **Trace Log**: `diagnostics/timestamp_trace.json`
- **Reference Data**: `diagnostics/reference_data.csv`
- **Bug Report**: `temp/strategies/mbmr/benchmarks/backtrader/RUSTYBT_BUG_REPORT.md`
- **Fix Document**: `docs/internal/sprint-debug/fixes/completed/2025-11-07-105919-history-off-by-one-data-shift.md`
