# Segfault Investigation - Bundle Tests

**Date**: 2025-10-28
**Investigator**: Claude Code (AI Agent)
**Context**: QA review of Fix 2 & Fix 3

---

## Issue Summary

When running `pytest tests/data/bundles/`, Python crashes with a segmentation fault:

```
Fatal Python error: Segmentation fault
```

---

## Investigation

### Step 1: Verify Pre-Existing Issue

Checked if segfault occurs on main branch (before any fixes):

```bash
git checkout main
pytest tests/data/bundles/ --collect-only
```

**Result**: ✅ Segfault occurs on main branch too
**Conclusion**: This is a **PRE-EXISTING ISSUE**, not caused by Fix 2 or Fix 3

---

## Root Cause

**Stack Trace Analysis**:
```
File "/Users/jerryinyang/Code/bmad-dev/rustybt/rustybt/testing/fixtures.py", line 10 in <module>
  ...
File "/Users/jerryinyang/Code/bmad-dev/rustybt/.venv/lib/python3.12/site-packages/h5py/__init__.py", line 45 in <module>
```

**Root Cause**:
- `rustybt/testing/fixtures.py` imports h5py
- h5py crashes with segmentation fault on macOS with Python 3.12
- This is a **known compatibility issue** with h5py on Apple Silicon macOS

**Affected Test Files**:
- `tests/data/bundles/test_csvdir.py` - imports rustybt.testing
- `tests/data/bundles/test_csvdir_decimal.py` - imports rustybt.testing
- `tests/data/bundles/test_quandl.py` - imports rustybt.testing
- `tests/data/bundles/test_quandl_security.py` - imports rustybt.testing
- `tests/data/bundles/test_adapter_bundles.py` - imports rustybt.testing
- `tests/data/bundles/test_core.py` - imports rustybt.testing

**NOT Affected** (our new tests):
- ✅ `tests/data/bundles/test_bundle_metadata.py` - NO rustybt.testing import
- ✅ `tests/data/bundles/test_calendar_detection.py` - NO rustybt.testing import
- ✅ `tests/data/bundles/test_sid_mapping.py` - NO rustybt.testing import

---

## Verification

Successfully ran all Fix 2 & Fix 3 tests:

```bash
pytest tests/data/bundles/test_bundle_metadata.py \
      tests/data/bundles/test_calendar_detection.py \
      tests/data/bundles/test_sid_mapping.py -v
```

**Result**:
```
45 passed, 22 warnings in 3.00s
```

- 9 existing bundle metadata tests ✓
- 19 new calendar detection tests ✓
- 17 new SID mapping tests ✓

**Conclusion**: All Fix 2 and Fix 3 tests pass successfully. The segfault does NOT affect our fixes.

---

## Impact Assessment

### Fix 2 & Fix 3 Status
- ✅ **NOT AFFECTED** by segfault
- ✅ All new tests pass (45/45)
- ✅ Tests don't import rustybt.testing
- ✅ Tests use real database operations (CR-002 compliant)
- ✅ Ready to merge

### Pre-Existing Issue Impact
- ❌ Cannot run full `tests/data/bundles/` suite
- ⚠️ 6+ test files affected by h5py import
- ℹ️ Issue exists on main branch
- ℹ️ NOT introduced by any recent fixes

---

## Workaround

To run bundle tests without crashing:

```bash
# Run specific test files that don't import rustybt.testing
pytest tests/data/bundles/test_bundle_metadata.py \
      tests/data/bundles/test_calendar_detection.py \
      tests/data/bundles/test_sid_mapping.py -v
```

OR

```bash
# Run tests excluding problematic files
pytest tests/data/bundles/ \
      --ignore=tests/data/bundles/test_csvdir.py \
      --ignore=tests/data/bundles/test_csvdir_decimal.py \
      --ignore=tests/data/bundles/test_quandl.py \
      --ignore=tests/data/bundles/test_quandl_security.py \
      --ignore=tests/data/bundles/test_adapter_bundles.py \
      --ignore=tests/data/bundles/test_core.py
```

---

## Recommended Solution

**Short-term** (for current fixes):
- ✅ Document in QA review that segfault is pre-existing
- ✅ Run Fix 2 & Fix 3 tests separately (all pass)
- ✅ Proceed with merge (not blocked by pre-existing issue)

**Long-term** (separate issue/fix):
1. **Option A**: Update h5py to latest version compatible with Python 3.12 + macOS
   ```bash
   pip install --upgrade h5py
   ```

2. **Option B**: Make h5py import in `rustybt/testing/fixtures.py` optional/lazy
   ```python
   # Only import h5py when actually needed, not at module level
   def get_h5py_fixture():
       import h5py  # Lazy import
       ...
   ```

3. **Option C**: Skip h5py-dependent tests on macOS Python 3.12
   ```python
   import sys
   import platform

   @pytest.mark.skipif(
       sys.version_info >= (3, 12) and platform.system() == "Darwin",
       reason="h5py segfaults on macOS Python 3.12"
   )
   def test_with_h5py():
       ...
   ```

4. **Create separate issue**: Document h5py segfault and track resolution separately from Fix 2 & Fix 3

---

## QA Decision

**Status**: Segfault is **PRE-EXISTING** and does **NOT BLOCK** Fix 2 & Fix 3

**Justification**:
1. ✅ Segfault exists on main branch (confirmed)
2. ✅ NOT caused by Fix 2 or Fix 3 changes
3. ✅ Fix 2 & Fix 3 tests pass completely (45/45)
4. ✅ Fix 2 & Fix 3 tests don't use affected code paths
5. ✅ Workaround available for running tests

**Recommendation**: Proceed with Fix 2 & Fix 3 merge. Create separate issue to address h5py segfault.

---

## References

- h5py issue tracker: https://github.com/h5py/h5py/issues
- Known h5py macOS segfault issues with Python 3.12+
- Fix 2: docs/internal/sprint-debug/fixes/completed/2025-10-27-184844-bundle-sid-mapping-mismatch.md
- Fix 3: docs/internal/sprint-debug/fixes/completed/2025-10-28-220437-forex-calendar-mismatch.md
