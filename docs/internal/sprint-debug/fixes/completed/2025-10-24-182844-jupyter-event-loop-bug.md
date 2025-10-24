# [2025-10-24 18:28:44] - ingest_to_bundle fails in Jupyter notebooks (event loop bug)

**Commit:** [Pending]
**Focus Area:** Framework - Data Adapters
**Severity:** 🔴 CRITICAL

---

## User-Reported Issue

**User Error:**
```
RuntimeError: asyncio.run() cannot be called from a running event loop
```

**User Scenario:**
User tried to run the corrected documentation example in a Jupyter notebook:

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source("yfinance")
source.ingest_to_bundle(
    bundle_name="tech-stocks",
    symbols=["AAPL", "MSFT", "GOOGL", "AMZN"],
    start=pd.Timestamp("2020-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
```

**Expected Behavior:**
- Code should work in both Jupyter notebooks and regular Python scripts
- Should ingest data successfully

**Actual Behavior:**
- RuntimeError: `asyncio.run() cannot be called from a running event loop`
- Jupyter notebooks already have a running event loop
- `asyncio.run()` at line 560 of yfinance_adapter.py fails

**Impact:**
- 🔴 CRITICAL - ALL adapters affected (yfinance, ccxt, polygon, alpaca, alphavantage, csv)
- Blocks ALL Jupyter notebook users (data scientists, researchers, analysts)
- Affects exploratory data analysis workflows

---

## Issues Found

**Issue 1: All 6 adapters use asyncio.run() in ingest_to_bundle**

All adapters have the same pattern in their `ingest_to_bundle()` method:

```python
df = asyncio.run(self.fetch(...))  # ❌ FAILS in Jupyter
```

Affected files:
1. `rustybt/data/adapters/yfinance_adapter.py:560`
2. `rustybt/data/adapters/ccxt_adapter.py:462`
3. `rustybt/data/adapters/polygon_adapter.py:400`
4. `rustybt/data/adapters/alpaca_adapter.py:294`
5. `rustybt/data/adapters/alphavantage_adapter.py:408`
6. `rustybt/data/adapters/csv_adapter.py:684`

---

## Root Cause Analysis

**Why did this issue occur:**
1. `ingest_to_bundle()` is synchronous (def, not async def)
2. Internally needs to call async `fetch()` method
3. Uses `asyncio.run()` to bridge sync→async
4. But `asyncio.run()` creates a NEW event loop
5. Jupyter notebooks already have a running event loop
6. Python prohibits nested `asyncio.run()` calls

**What pattern should prevent recurrence:**
1. Use utility function that detects running event loops
2. If loop exists, use `loop.run_until_complete()`
3. If no loop, use `asyncio.run()`
4. Add integration tests for Jupyter environments
5. Add CI test that simulates Jupyter notebook execution

---

## Fixes Applied

[Pending]

---

## Tests Added/Modified

[Pending]

---
