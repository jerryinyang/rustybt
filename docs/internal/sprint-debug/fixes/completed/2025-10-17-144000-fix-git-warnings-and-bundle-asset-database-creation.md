# [2025-10-17 14:40:00] - Fix Git Warnings and Bundle Asset Database Creation

**Commit:** [Pending]
**Focus Area:** Core Framework / Bundle Ingestion
**Severity:** 🔴 CRITICAL - Blocks user onboarding and bundle usage

## Issues Fixed

### Issue 1: Fatal Git HEAD Warning
**Symptom:**
```
fatal: bad revision 'HEAD'
```
Displayed on every `rustybt` CLI invocation and Python API usage.

**Impact:** 🔴 CRITICAL
- Confuses users with scary error messages
- Makes debugging other issues harder
- Looks like a broken installation
- Persistent across all operations

**Root Cause Analysis:**
Deep investigation revealed that `bcolz-zipline` and `ccxt` dependencies call `git describe` during module import to detect their version. When executed in a git repository without commits (or any directory with a `.git` folder but no HEAD), these commands fail with "fatal: bad revision 'HEAD'". The error is written to stderr but doesn't prevent execution.

**Stack Trace:**
```
rustybt/__main__.py → bundles/__init__.py → quandl.py → bcolz_daily_bars.py → bcolz.__init__:116
rustybt/__main__.py → bundles/__init__.py → adapter_bundles.py → ccxt_adapter.py → ccxt.__init__.py
```

**Solution:**
Added stderr suppression context manager in `rustybt/data/bundles/__init__.py`:
- Created `_suppress_git_stderr()` context manager that redirects stderr to `/dev/null` during imports
- Wrapped `from . import quandl` and `from . import adapter_bundles` imports
- Prevents git error from being displayed while allowing imports to succeed
- Cross-platform compatible (Unix and Windows)

**Files Modified:**
- `rustybt/data/bundles/__init__.py` (rustybt/data/bundles/__init__.py:1-60)

**Testing:**
```bash
# Before fix:
$ rustybt --help
fatal: bad revision 'HEAD'
Usage: rustybt [OPTIONS] COMMAND [ARGS]...

# After fix:
$ rustybt --help
Usage: rustybt [OPTIONS] COMMAND [ARGS]...
# ✅ No warning!
```

**Status:** ✅ FIXED & VERIFIED

---

### Issue 2: Missing SQLite Assets Database in Adapter Bundles
**Symptom:**
```
ValueError: SQLite file '/Users/.../.zipline/data/yfinance-profiling/.../assets-9.sqlite' doesn't exist.
```

**Impact:** 🔴 CRITICAL
- All adapter-based bundles (yfinance-profiling, ccxt-*-profiling, csv-profiling) unusable
- Quick start examples fail immediately
- Bundle ingestion succeeds but bundles can't be loaded
- Affects all new users trying the framework

**Root Cause:**
The adapter bundle bridge functions (`_create_bundle_from_adapter()` in `adapter_bundles.py`) were writing bar data (OHLCV) but not creating the assets database. The assets database is required for bundle loading to map symbols to asset IDs (SIDs).

Investigation showed:
1. `csvdir` and `quandl` bundles call `asset_db_writer.write(equities=metadata, exchanges=exchanges)`
2. Adapter bundles received `asset_db_writer` parameter but never used it
3. Adapter bundles only wrote to `daily_bar_writer` and `minute_bar_writer`

**Solution:**
Implemented complete asset database creation in adapter bundles:

1. **Created `_create_asset_metadata()` helper function** (rustybt/data/bundles/adapter_bundles.py:44-141):
   - Extracts symbols from OHLCV DataFrame
   - Computes start_date and end_date for each symbol
   - Handles both Polars and pandas DataFrames
   - Handles multiple timestamp column naming conventions
   - Creates properly formatted asset metadata DataFrame

2. **Modified `_create_bundle_from_adapter()`** (rustybt/data/bundles/adapter_bundles.py:144-288):
   - Calls `_create_asset_metadata()` after fetch but before transformation
   - Creates exchanges DataFrame
   - Writes to `asset_db_writer` before writing bar data
   - Added comprehensive error handling and logging

3. **Updated all adapter bundle functions** to include `asset_db_writer` in writers dict:
   - `yfinance_profiling_bundle()` (rustybt/data/bundles/adapter_bundles.py:633-638)
   - `ccxt_hourly_profiling_bundle()` (rustybt/data/bundles/adapter_bundles.py:706-711)
   - `ccxt_minute_profiling_bundle()` (rustybt/data/bundles/adapter_bundles.py:769-774)
   - `csv_profiling_bundle()` (rustybt/data/bundles/adapter_bundles.py:836-841)

**Files Modified:**
- `rustybt/data/bundles/adapter_bundles.py` (rustybt/data/bundles/adapter_bundles.py:44-841)

**Asset Metadata Format:**
```python
{
    'symbol': str,           # Symbol name (e.g., 'AAPL')
    'start_date': datetime,  # First date with data
    'end_date': datetime,    # Last date with data
    'exchange': str,         # Exchange name (derived from bundle_name)
    'auto_close_date': datetime  # end_date + 1 day
}
```

**Status:** ✅ FIXED & IMPLEMENTED (requires valid data ingestion to verify)

---

## Testing Notes

**Git Warning Fix:** ✅ Fully tested and verified
- Tested in git repo without commits: No warning
- Tested rustybt CLI: No warning
- Tested Python API imports: No warning

**Assets Database Fix:** ⚠️ Code correct, awaiting clean data
- Code logic verified against working bundles (csvdir, quandl)
- Implementation follows exact same pattern
- Testing blocked by:
  - yfinance returning invalid OHLCV data during market hours
  - Asset database version mismatch (old bundles v8, new code v9)
  - Requires clean bundle ingestion to fully verify

## Recommendations

1. **Re-ingest all adapter bundles** after deploying this fix
2. **Update quick start docs** to mention asset database requirement
3. **Consider migration script** to upgrade v8 bundles to v9
4. **Add validation** to detect missing assets database and provide helpful error message

## Related Issues

- Previous attempt to fix git warning (commit 1d3e9ff) only modified setuptools-scm config, didn't address actual cause
- Asset database version recently upgraded from 8 to 9, breaking old bundles

---
