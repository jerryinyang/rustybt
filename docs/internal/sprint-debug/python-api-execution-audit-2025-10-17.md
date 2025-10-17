# Documentation Audit: Python API Execution Gaps

**Audit Date**: 2025-10-17
**Auditor**: James (Dev Agent)
**Scope**: All user-facing documentation
**Issue**: Code examples are CLI-first without Python API options

---

## Executive Summary

A comprehensive audit of 114 user-facing documentation files revealed a **critical gap** in execution method documentation. The main user onboarding paths (`index.md` and `quickstart.md`) **only show CLI execution** (`rustybt run`), with no mention of the Python API execution method using `run_algorithm()`.

### Key Findings

- **2 critical files** (home page, quick start) show CLI-only execution
- **7 files** demonstrate good Python API usage (`run_algorithm()`)
- **4+ files** show strategy definitions without ANY execution instructions
- **0 files** show both CLI and Python API side-by-side
- **Impact**: HIGH - New users assume CLI is the only execution method

---

## Audit Methodology

**Files Audited**: 114 user-facing documentation files
- `docs/index.md` - Main documentation home
- `docs/getting-started/*.md` (3 files)
- `docs/guides/*.md` (19 files)
- `docs/examples/*.md` (2 files)
- `docs/api/**/*.md` (90+ files)

**Search Patterns Used**:
- `rustybt run` - CLI command usage
- `run_algorithm` - Python API usage
- `def initialize`, `def handle_data` - Strategy definitions
- `if __name__ == "__main__":` - Execution pattern
- `TradingAlgorithm` - Class-based strategies

**Excluded** (as appropriate):
- `docs/internal/*` - Internal documentation
- `docs/_archive/*` - Archived content

---

## Critical Issues (Fix Immediately)

### 1. Home Page - CLI-Only Quick Start

**File**: `docs/index.md`
**Lines**: 79
**Issue**: Only shows `rustybt run` command
**Impact**: **CRITICAL** - First impression for all users

**Current Code**:
```bash
rustybt run -f strategy.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31
```

**Missing**: Python API alternative
```python
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

if __name__ == "__main__":
    result = run_algorithm(
        algorithm_file='strategy.py',
        bundle='yfinance-profiling',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=10000
    )
```

**Recommendation**: Add Python API example immediately after CLI example with heading "Alternative: Python API Execution"

---

### 2. Quick Start Guide - CLI-Only Tutorial

**File**: `docs/getting-started/quickstart.md`
**Lines**: 82, 104, 134
**Issue**: Multiple CLI examples, zero Python API examples
**Impact**: **CRITICAL** - Primary onboarding document

**Current Approach**:
1. Shows strategy definition (lines 15-61)
2. Shows data ingestion CLI (line 68)
3. Shows execution CLI only (line 82)
4. Troubleshooting shows only CLI (lines 104, 134)

**Missing**: Complete Python API execution example with:
- Import statements
- `run_algorithm()` call
- `if __name__ == "__main__":` pattern
- Results handling

**Recommendation**: Add "Alternative: Python API Execution" section after line 86

**Suggested Content**:
```python
## Alternative: Python API Execution

You can also run strategies directly from Python without the CLI:

```python
# my_strategy.py
from rustybt.api import order_target, record, symbol
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

def initialize(context):
    context.i = 0
    context.asset = symbol('AAPL')

def handle_data(context, data):
    context.i += 1
    if context.i < 300:
        return

    short_mavg = data.history(context.asset, 'price', bar_count=100, frequency="1d").mean()
    long_mavg = data.history(context.asset, 'price', bar_count=300, frequency="1d").mean()

    if short_mavg > long_mavg:
        order_target(context.asset, 100)
    elif short_mavg < long_mavg:
        order_target(context.asset, 0)

    record(AAPL=data.current(context.asset, 'price'), short_mavg=short_mavg, long_mavg=long_mavg)

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=10000,
        data_frequency='daily'
    )

    print(f"\nBacktest Results:")
    print(f"Total return: {result['returns'].iloc[-1]:.2%}")
    print(f"Sharpe ratio: {result['sharpe']:.2f}")
    print(f"Max drawdown: {result['max_drawdown']:.2%}")
```

Then run with:
```bash
python my_strategy.py
```

**Benefits**:
- Standard Python development workflow
- Easy debugging with IDE breakpoints
- Better integration with notebooks and scripts
- More Pythonic approach
```

---

## High Priority Issues (Fix Soon)

### 3. Pipeline API Guide - Missing Execution

**File**: `docs/guides/pipeline-api-guide.md`
**Lines**: 32-42, 389-432
**Issue**: Shows `MomentumStrategy` class definition without execution
**Impact**: HIGH - Users don't know how to run pipeline strategies

**Current**: Shows strategy class definition
```python
class MomentumStrategy(TradingAlgorithm):
    # ... implementation
```

**Missing**: Execution section showing:
```python
if __name__ == "__main__":
    from rustybt.utils.run_algo import run_algorithm
    import pandas as pd

    result = run_algorithm(
        algorithm_class=MomentumStrategy,
        bundle='my-bundle',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=100000
    )
```

**Recommendation**: Add "Running Pipeline Strategies" section after line 432 showing both CLI and Python API

---

### 4. Order Types API - Broken Promise

**File**: `docs/api/order-management/order-types.md`
**Lines**: 108 (references), 85-200 (snippets)
**Issue**: Promises "Complete Examples" section that doesn't exist
**Impact**: HIGH - Users expect complete runnable code

**Line 108 states**: "See Complete Examples section for full runnable code."

**Problem**: No "Complete Examples" section exists in the file

**Missing Section Should Include**:
1. Full imports
2. Strategy class with various order types
3. `if __name__ == "__main__":` execution
4. Both `run_algorithm()` and CLI methods
5. Results handling

**Recommendation**: Add "Complete Examples" section with full runnable strategies demonstrating:
- Market orders
- Limit orders
- Stop orders
- Stop-limit orders

---

### 5. Audit Logging Guide - Incomplete Example

**File**: `docs/guides/audit-logging.md`
**Lines**: 391-421
**Issue**: Shows `CustomStrategy` with logging but no execution
**Impact**: MEDIUM - Users see what to log, not how to run it

**Current**: Shows strategy with logging setup
```python
class CustomStrategy(TradingAlgorithm):
    def initialize(self, context):
        setup_custom_audit_logger(...)
    # ... strategy code
```

**Missing**: Execution example after line 421

**Recommendation**: Add execution section:
```python
if __name__ == "__main__":
    from rustybt.utils.run_algo import run_algorithm

    result = run_algorithm(
        algorithm_class=CustomStrategy,
        # ... parameters
    )
```

---

## Medium Priority Issues (Improve Completeness)

### 6. Portfolio Management API - Usage Snippets Only

**File**: `docs/api/portfolio-management/README.md`
**Lines**: 77-99, 128-142
**Issue**: Shows portfolio access patterns without complete example
**Impact**: MEDIUM - Advanced users can infer, beginners cannot

**Current**: Snippets like:
```python
portfolio = context.portfolio
print(f"Cash: {portfolio.cash}")
```

**Missing**: Complete runnable example from start to finish

**Recommendation**: Add "Complete Example" section showing:
1. Full strategy class
2. Portfolio access in `handle_data()`
3. Execution with `run_algorithm()`
4. Results printing

---

### 7. Cross-References Missing

**Files**: Multiple API documentation files
**Issue**: Mention strategies but don't link to execution guides
**Impact**: MEDIUM - Navigation friction

**Recommendation**: Add consistent footer to all API docs that show strategy examples:

```markdown
## Running This Strategy

**CLI Method**:
```bash
rustybt run -f my_strategy.py -b my-bundle --start 2020-01-01 --end 2023-12-31
```

**Python API Method**: See [Quick Start Guide](../../getting-started/quickstart.md#alternative-python-api-execution) for details.
```python
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='my-bundle',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=100000
    )
```
```

---

## Positive Findings - Good Examples

### Files Demonstrating Python API Correctly

**1. docs/api/analytics/risk/metrics.md** (Lines 98-142)
✅ Shows complete `run_algorithm()` usage with proper imports
✅ Demonstrates results handling
✅ Good template for other docs

**2. docs/api/computation/pipeline-api.md** (Lines 886-901)
✅ Shows `run_algorithm()` with pipeline
✅ Correct import: `from rustybt.utils.run_algo import run_algorithm`
✅ Complete example

**3. docs/api/data-management/catalog/bundle-system.md** (Lines 99-108)
✅ Shows `run_algorithm()` with bundle specification
✅ Good demonstration of bundle parameter

**4. docs/api/live-trading/README.md** (Lines 83-136)
✅ **BEST EXAMPLE** - Shows complete paper trading setup
✅ Uses `if __name__ == "__main__":` pattern
✅ Demonstrates `asyncio.run(main())`
✅ **Should be template for other docs**

**5. docs/api/live-trading/production-deployment.md** (Lines 35-45)
✅ Shows `run_algorithm()` for production
✅ Proper error handling

**6. docs/guides/data-ingestion.md**
✅ Shows `asyncio.run(main())` pattern
✅ Complete execution example

**7. docs/guides/live-vs-backtest-data.md** (Lines 87-148)
✅ Shows Python API setup (partial)
✅ Good comparison of backtest vs live

---

## Pattern Analysis

### Current Distribution

**CLI-Only Examples**: 2 files (CRITICAL)
- `docs/index.md`
- `docs/getting-started/quickstart.md`

**Python API Examples**: 7 files (GOOD)
- Most in API reference
- Few in getting-started/guides

**Neither CLI nor Python API**: 4+ files (PROBLEM)
- `docs/guides/pipeline-api-guide.md`
- `docs/guides/audit-logging.md`
- `docs/api/order-management/order-types.md`
- `docs/api/portfolio-management/README.md`

**Both Methods Side-by-Side**: 0 files (IDEAL NOT ACHIEVED)

### User Journey Impact

**New User Path**:
1. Lands on `docs/index.md` → Sees CLI only
2. Clicks "Quick Start" → `docs/getting-started/quickstart.md` → Sees CLI only
3. **Conclusion**: "CLI is the only way to run RustyBT"
4. **Never discovers**: `run_algorithm()` exists

**Advanced User Path**:
1. Reads API documentation → Sees `run_algorithm()` occasionally
2. **Confusion**: "Why wasn't this mentioned in Quick Start?"
3. **Frustration**: "I've been using CLI when I could have used Python?"

---

## Recommendations Summary

### Immediate Actions (Critical User Impact)

**Priority 1**: Update `docs/index.md`
- Add Python API example after CLI example
- Show both methods as equally valid
- Estimated effort: 30 minutes

**Priority 2**: Update `docs/getting-started/quickstart.md`
- Add "Alternative: Python API Execution" section
- Complete example with imports, execution, results
- Estimated effort: 1 hour

### Short-Term Actions (Feature Documentation)

**Priority 3**: Fix incomplete examples
- `docs/guides/pipeline-api-guide.md` - Add execution section
- `docs/api/order-management/order-types.md` - Add promised "Complete Examples"
- `docs/guides/audit-logging.md` - Add execution example
- Estimated effort: 2 hours

**Priority 4**: Improve API docs
- `docs/api/portfolio-management/README.md` - Add complete example
- Add cross-reference footers to all API docs
- Estimated effort: 1 hour

### Long-Term Actions (Documentation Standards)

**Priority 5**: Create standard templates
- "Strategy Example Template" with both execution methods
- "API Documentation Footer" with execution links
- Documentation style guide for code examples
- Estimated effort: 2 hours

**Priority 6**: Create dedicated execution guide
- New file: `docs/guides/execution-methods.md`
- Comprehensive guide to all execution options:
  - CLI (`rustybt run`)
  - Python API (`run_algorithm()`)
  - Jupyter notebooks
  - Class-based vs function-based
- Estimated effort: 3 hours

---

## Statistics

**Total Files Audited**: 114

**Execution Method Coverage**:
- CLI-only: 2 files (1.8%)
- Python API only: 7 files (6.1%)
- Both methods: 0 files (0%)
- Neither method: 4+ files (3.5%)
- Not applicable (no code examples): ~101 files (88.6%)

**Impact Assessment**:
- **Critical impact**: 2 files (home, quickstart)
- **High impact**: 4 files (missing execution)
- **Medium impact**: 2+ files (incomplete examples)
- **Low impact**: Cross-reference improvements

**Estimated Total Fix Time**: 9.5 hours
- Critical fixes: 1.5 hours
- High priority: 2 hours
- Medium priority: 1 hour
- Long-term improvements: 5 hours

---

## Conclusion

The audit reveals a **systematic documentation gap** where the primary user onboarding path teaches CLI-first execution without mentioning the Python API alternative. This creates a poor user experience where:

1. **New users** learn CLI-only and never discover `run_algorithm()`
2. **Advanced users** find Python API in scattered API docs
3. **No documentation** shows both methods side-by-side
4. **Some examples** show strategies without ANY execution instructions

The **root cause** appears to be documentation inherited from Zipline's CLI-centric approach, never updated to prioritize Pythonic execution patterns.

**Immediate fix required**: Update `docs/index.md` and `docs/getting-started/quickstart.md` to show Python API as the primary method, with CLI as an alternative.

---

## Next Steps for Sprint Debugging Session

1. ✅ Documented in `KNOWN_ISSUES.md`
2. ✅ Comprehensive audit completed
3. ⏭️ **Next session**: Create fixes following priority order
4. ⏭️ **Create**: `docs/guides/execution-methods.md` comprehensive guide
5. ⏭️ **Update**: All affected files per recommendations above

---

**Audit Completed**: 2025-10-17
**Report Location**: `docs/internal/sprint-debug/python-api-execution-audit-2025-10-17.md`
**Issue Tracking**: `docs/internal/KNOWN_ISSUES.md` (updated)
**Status**: Ready for fix implementation in next sprint-debug session
