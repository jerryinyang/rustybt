# Known Issues

## Documentation Build

### Pydantic V2 Deprecation Warning in mkdocstrings

**Status**: Informational only - No action required

**Issue**: During `mkdocs build`, an INFO-level message appears:

```
INFO - PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated...
```

**Source**: `mkdocstrings-python` v1.18.2 (third-party dependency)

**Impact**: None
- Build completes successfully
- Documentation quality unaffected
- `--strict` mode passes (only blocks on WARNING/ERROR)
- Future deprecation notice (won't break until Pydantic V3)

**Resolution**:
- No action needed from our side
- Will be fixed in future mkdocstrings-python release
- Monitor upstream: https://github.com/mkdocstrings/python

**Workaround** (optional): Filter the message during CI/CD:
```bash
mkdocs build --strict 2>&1 | grep -v "PydanticDeprecatedSince20"
```

**Last Checked**: 2025-10-17
**Dependencies**: mkdocstrings 0.30.1, mkdocstrings-python 1.18.2

---

## Documentation - Code Execution Examples

### Python API Execution Not Documented

**Status**: ✅ RESOLVED (2025-10-17)

**Issue**: Documentation examples were CLI-first (`rustybt run`) without showing Python API option

**Resolution Summary**:
All priority fixes have been completed across multiple sprint-debug sessions. Documentation now shows both CLI and Python API execution methods.

**Fixes Completed**:

1. ✅ **CRITICAL: docs/index.md** - Added "Alternative: Python API Execution" section (lines 85-122)
   - Complete example with `run_algorithm()`
   - Shows `if __name__ == "__main__":` pattern
   - Demonstrates results handling
   - Shows execution: `python strategy.py`

2. ✅ **CRITICAL: docs/getting-started/quickstart.md** - Added "Alternative: Python API Execution" section (lines 92-164)
   - Complete function-based example
   - Lists benefits of Python API
   - Shows results analysis
   - Emphasizes standard Python workflow

3. ✅ **HIGH: docs/api/order-management/order-types.md** - Added "Complete Examples" section (lines 1722-1955)
   - Multiple complete strategy examples
   - "Running the Examples" section with both CLI and Python API methods
   - Shows `run_algorithm()` with full imports
   - Demonstrates order history access

4. ✅ **HIGH: docs/guides/pipeline-api-guide.md** - Added "Running Pipeline Strategies" section (lines 434-447)
   - Correctly documents that class-based strategies require CLI only
   - Removed fabricated `algorithm_class` parameter (commit 8cdd50e)
   - Clarifies Python API only supports function-based strategies
   - Provides complete CLI execution instructions

**Critical Discovery**:
- The `algorithm_class` parameter was **fabricated** and never existed in `run_algorithm()`
- Removed from 3 files in commit 8cdd50e (2025-10-17 15:30:00)
- Established verification pattern: Always use `inspect.signature()` to verify API before documenting

**Actual Execution Methods**:

| Strategy Type | CLI | Python API |
|---------------|-----|------------|
| **Function-based** | ✅ `rustybt run -f file.py` | ✅ `run_algorithm(initialize=..., handle_data=...)` |
| **Class-based** (TradingAlgorithm) | ✅ `rustybt run -f file.py` | ❌ NOT SUPPORTED |

**Documentation Quality Improvements**:
- All critical user onboarding paths now show both execution methods
- Python API execution properly documented with correct parameters
- Class-based vs function-based execution requirements clarified
- Examples verified against actual source code signatures

**Audit Artifacts**:
- Full audit report: `docs/internal/sprint-debug/python-api-execution-audit-2025-10-17.md`
- Fix documentation: `docs/internal/sprint-debug/fixes/2025-10-17-131112-python-api-execution-documentation-gap-fix.md`
- Fabrication removal: `docs/internal/sprint-debug/fixes/2025-10-17-153000-critical-fix-remove-fabricated-algorithmclass-parameter.md`

**Resolved**: 2025-10-17
**Fixed By**: James (Dev Agent) - Multiple sprint-debug sessions
**Verified By**: Documentation build passes (`mkdocs build --strict`)

---

## Testing Infrastructure

### h5py Segfault on macOS Python 3.12

**Status**: 🔴 ACTIVE - Known Issue

**Issue**: Python crashes with segmentation fault when running some bundle tests:

```bash
pytest tests/data/bundles/
# Fatal Python error: Segmentation fault
```

**Root Cause**:
- h5py library compatibility issue on Apple Silicon macOS with Python 3.12
- Occurs when `rustybt/testing/fixtures.py` imports h5py at module level
- Known upstream issue with h5py on macOS

**Affected Tests**:
- `tests/data/bundles/test_csvdir.py`
- `tests/data/bundles/test_csvdir_decimal.py`
- `tests/data/bundles/test_quandl.py`
- `tests/data/bundles/test_quandl_security.py`
- `tests/data/bundles/test_adapter_bundles.py`
- `tests/data/bundles/test_core.py`

**NOT Affected** (safe to run):
- ✅ `tests/data/bundles/test_bundle_metadata.py`
- ✅ `tests/data/bundles/test_calendar_detection.py`
- ✅ `tests/data/bundles/test_sid_mapping.py`
- ✅ All other test suites

**Workaround**:
```bash
# Run specific test files that don't use h5py
pytest tests/data/bundles/test_bundle_metadata.py \
      tests/data/bundles/test_calendar_detection.py \
      tests/data/bundles/test_sid_mapping.py -v

# OR exclude problematic files
pytest tests/data/bundles/ \
      --ignore=tests/data/bundles/test_csvdir.py \
      --ignore=tests/data/bundles/test_csvdir_decimal.py \
      --ignore=tests/data/bundles/test_quandl.py \
      --ignore=tests/data/bundles/test_quandl_security.py \
      --ignore=tests/data/bundles/test_adapter_bundles.py \
      --ignore=tests/data/bundles/test_core.py
```

**Potential Solutions**:
1. Upgrade h5py to latest version: `pip install --upgrade h5py`
2. Make h5py import lazy in `rustybt/testing/fixtures.py`
3. Skip h5py-dependent tests on macOS Python 3.12
4. Investigate upstream h5py issue tracker

**Impact**:
- Low - Does not affect framework functionality
- Only affects running specific older test files
- New tests (Fix 2 & Fix 3) all pass successfully

**Investigation Report**: `docs/internal/sprint-debug/fixes/completed/QA-SEGFAULT-INVESTIGATION.md`

**Discovered**: 2025-10-28 (during QA review of Fix 2 & Fix 3)
**Platform**: macOS (Apple Silicon), Python 3.12.10
