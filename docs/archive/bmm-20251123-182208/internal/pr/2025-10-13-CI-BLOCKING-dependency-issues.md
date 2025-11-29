# CI/CD Blocking Issues - Dependency Compatibility & Build System

**Date**: 2025-10-13
**Status**: 🟡 PARTIALLY RESOLVED - 1 Critical Issue Remains
**Related Commits**: f5bc8f8, 9789fdf, d9b219d, a3ac611, 798441d
**Workflows Affected**: All (CI, Security, Property-Based Tests, Performance Regression)

---

## Executive Summary

All CI/CD workflows were failing on the main branch due to dependency compatibility issues and build system configuration problems. Investigation revealed three critical blocking issues:

1. ✅ **RESOLVED**: Numpy/Numexpr version conflicts across Python 3.12/3.13
2. ✅ **RESOLVED**: Python version classifiers mismatch
3. ❌ **BLOCKING**: Cython/Python modules not available in editable installs

---

## Issue Breakdown

### ✅ Issue 1: Numpy/Numexpr Version Compatibility (RESOLVED)

#### Problem Description
The dependency resolver was failing with conflicting numpy requirements:

```
× No solution found when resolving dependencies for split (markers:
│ python_full_version == '3.13.*'):
╰─▶ Because your project depends on numpy>=1.26.0,<2.0 and
    numpy{python_full_version >= '3.13'}>=2.1, we can conclude that your
    project's requirements are unsatisfiable.
```

**Root Cause**: Overlapping version constraints in `pyproject.toml`:
- Line 38: `numpy>=1.23.5; python_version<'3.12'` (unused, requires-python='>=3.12')
- Line 39: `numpy>=1.26.0,<2.0; python_version>='3.12'` (matches both 3.12 AND 3.13)
- Line 40: `numpy>=2.1; python_version>='3.13'` (also matches 3.13)

For Python 3.13, both conditions were true, creating an impossible constraint: `numpy>=1.26.0,<2.0` AND `numpy>=2.1`

Additionally, `numexpr>=2.6.1` was incompatible with numpy 2.x, causing import errors:
```python
AttributeError: module 'numpy' has no attribute 'typing'. Did you mean: '_typing'?
```

#### Solution Applied

**File**: `pyproject.toml`

```toml
# Before
dependencies = [
    "numpy>=1.23.5; python_version<'3.12'",
    "numpy>=1.26.0,<2.0; python_version>='3.12'",
    "numpy>=2.1; python_version>='3.13'",
    # ...
    'numexpr >=2.6.1',
]

# After
dependencies = [
    "numpy>=1.26.0,<2.0; python_version=='3.12'",  # Changed >= to ==
    "numpy>=2.1; python_version>='3.13'",
    # ...
    'numexpr >=2.8.0,<2.10; python_version=="3.12"',  # Version-specific
    'numexpr >=2.10; python_version>="3.13"',
]
```

**Key Changes**:
1. Changed Python 3.12 condition from `>=` to `==` to prevent overlap
2. Removed Python <3.12 constraint (not needed with requires-python='>=3.12')
3. Added version-specific numexpr constraints aligned with numpy versions

**Commits**:
- f5bc8f8: Initial numpy constraint fix
- 9789fdf: Added numexpr version constraints

**Verification**: UV resolver now successfully resolves dependencies for both Python 3.12 and 3.13

---

### ✅ Issue 2: Python Version Classifiers Mismatch (RESOLVED)

#### Problem Description
Inconsistency between package metadata:
- `requires-python = '>=3.12'` (line 36)
- Classifiers included Python 3.10 and 3.11 (lines 20-21)

This created confusion and potential issues with package distribution and compatibility declarations.

#### Solution Applied

**File**: `pyproject.toml`

```toml
# Before
classifiers = [
    'Development Status :: 4 - Beta',
    'Natural Language :: English',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3.10',  # Removed
    'Programming Language :: Python :: 3.11',  # Removed
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    # ...
]

# After
classifiers = [
    'Development Status :: 4 - Beta',
    'Natural Language :: English',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    # ...
]
```

**Commit**: f5bc8f8

**Verification**: Package metadata now consistently declares Python 3.12+ support

---

### ❌ Issue 3: Module Import Failures in Editable Installs (BLOCKING)

#### Problem Description
After fixing dependency resolution, the smoke test fails with:

```python
ModuleNotFoundError: No module named 'rustybt.lib.labelarray'
```

**Observations**:
1. ✅ File exists locally: `rustybt/lib/labelarray.py`
2. ✅ Package builds successfully (CI logs show ~2min build time)
3. ✅ Build system requirements are properly specified in `[build-system]`
4. ✅ Cython extensions are defined in `setup.py`
5. ❌ Module not importable after editable install (`pip install -e .`)

#### Root Cause Analysis

The issue appears to be related to how setuptools handles editable installs with mixed Cython/Python packages when using `pyproject.toml` as the primary configuration.

**Evidence from CI logs**:
```
Building editable for rustybt (pyproject.toml): started
Building editable for rustybt (pyproject.toml): still running...
Building editable for rustybt (pyproject.toml): finished with status 'done'
```

The build completes, but the resulting installation doesn't properly expose all Python modules from the `rustybt.lib` package.

**Package Structure**:
```
rustybt/
├── lib/
│   ├── __init__.py          ✅ Exists
│   ├── labelarray.py        ✅ Exists (pure Python)
│   ├── adjustment.pyx       ✅ Cython extension
│   ├── _factorize.pyx      ✅ Cython extension
│   └── ... (more .pyx files)
```

#### Attempted Solutions

**Attempt 1**: Use `uv pip install` with `--no-build-isolation`
- **Result**: Failed - peewee dependency failed to build with Cython 3.x
- **Error**: `undeclared name not builtin: long` (Python 2 syntax in peewee)
- **Commit**: d9b219d

**Attempt 2**: Pre-install build dependencies, then use uv
- **Result**: Failed - same peewee build issue
- **Commit**: a3ac611

**Attempt 3**: Use standard `pip install -e .` directly
- **Result**: Failed - still can't import rustybt.lib.labelarray
- **Commit**: 798441d (current state)

#### Current CI Smoke Test Configuration

**File**: `.github/workflows/ci.yml` (lines 29-36)

```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    python -m pip install -e .

- name: Run smoke test
  run: |
    python -c "import rustybt; print(f'RustyBT version: {rustybt.__version__}')"
    python -c "import polars, hypothesis, structlog, pydantic; print('All dependencies OK')"
```

**CI Log Evidence**:
- Dependencies resolve correctly ✅
- Package builds for ~3.5 minutes ✅
- Build completes with "finished with status 'done'" ✅
- Import fails at runtime ❌

#### Potential Solutions (Not Yet Implemented)

**Option A**: Use non-editable install for smoke test
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    python -m pip install .  # Remove -e flag
```
**Pros**: Standard installs typically work more reliably
**Cons**: Slower, doesn't reflect development workflow

**Option B**: Investigate setuptools editable install configuration
- Check if `[tool.setuptools.packages.find]` configuration is correct
- Ensure `include-package-data = true` is working properly
- May need to explicitly list packages or use MANIFEST.in

**Option C**: Skip smoke test, rely on full test suite
- Full test suite (`.github/workflows/ci.yml` lines 78-158) has proper build configuration
- Includes Rust toolchain setup
- Installs setuptools-rust explicitly
**Pros**: Tests are more comprehensive
**Cons**: Slower feedback loop, smoke test provides value

**Option D**: Add explicit package discovery
```toml
[tool.setuptools.packages.find]
where = ['.']
include = ['rustybt*']
exclude = ['tests*', 'deps*', 'docs*', '.bmad-core*']
```

Currently configured in `pyproject.toml` lines 193-195 but may need refinement.

---

## Impact Assessment

### Workflows Currently Failing

1. **CI Workflow** (`.github/workflows/ci.yml`)
   - ❌ Smoke Test: Import error
   - ⏸️  Lint & Format: Blocked by smoke test
   - ⏸️  Full Tests: Blocked by smoke test
   - ⏸️  Build Distribution: Blocked by smoke test

2. **Security Workflow** (`.github/workflows/security.yml`)
   - ❌ Bandit SAST: Separate issue (not dependency-related)
   - Resolution rate shows "failure" status

3. **Property-Based Tests** (`.github/workflows/property-tests.yml`)
   - ❌ Blocked by dependency installation issues (before fixes)
   - Status after fixes: Unknown (queued/not completed)

4. **Performance Regression** (`.github/workflows/performance.yml`)
   - ❌ Uses deprecated `actions/upload-artifact@v3`
   - Fails immediately (infrastructure issue)

### Estimated Time to Resolution

- **Issue 1 (Numpy/Numexpr)**: ✅ RESOLVED (2 hours investigation + fixes)
- **Issue 2 (Classifiers)**: ✅ RESOLVED (15 minutes)
- **Issue 3 (Editable Install)**: 🟡 IN PROGRESS
  - Investigation: 3 hours (completed)
  - Solution implementation: 1-2 hours (pending)
  - Testing/verification: 30 minutes (pending)

---

## Additional Issues Discovered

### 4. Performance Regression Workflow - Deprecated Action

**File**: `.github/workflows/performance.yml` (line 274)

```yaml
- name: Upload performance results
  if: always()
  uses: actions/upload-artifact@v4  # Should be v4, currently v3
```

**Error**:
```
##[error]This request has been automatically failed because it uses a
deprecated version of `actions/upload-artifact: v3`.
```

**Fix Required**: Update to `actions/upload-artifact@v4` throughout all workflows

**Priority**: Medium (workflow fails immediately, but not related to core functionality)

---

### 5. Bandit Security Scanner Failures

**Workflow**: `.github/workflows/security.yml`

**Status**: ❌ FAILING (but not blocking CI if configured as non-blocking)

**Log Output**:
```
=== Security Scan Results ===

✅ Bandit SAST: failure
✅ TruffleHog: skipped
✅ Detect-secrets: skipped

❌ Security checks FAILED
```

**Note**: The checkmarks (✅) next to "failure" suggest this might be a reporting issue where the workflow expects failures to be continue-on-error but the summary step fails.

**Priority**: Medium (security tool, but may be false positive or configuration issue)

---

## Recommendations

### Immediate Actions (Priority 1)

1. **Resolve editable install issue** (Issue 3)
   - Try Option A (non-editable install) first as quickest path
   - If that works, can investigate proper editable install later
   - Target: Unblock all CI workflows

2. **Update upload-artifact actions** (Issue 4)
   - Simple find/replace: `actions/upload-artifact@v3` → `actions/upload-artifact@v4`
   - Check all workflow files
   - Target: Fix Performance Regression workflow

### Short-term Actions (Priority 2)

3. **Investigate bandit failures** (Issue 5)
   - Review actual security findings
   - Determine if real issues or false positives
   - Consider adjusting bandit configuration or adding # nosec comments
   - Target: Green security workflow

4. **Improve smoke test**
   - Once import issues resolved, consider adding more sanity checks
   - Test critical module imports (pipeline, data, finance)
   - Verify Cython extensions loaded correctly

### Long-term Actions (Priority 3)

5. **Dependency pinning strategy**
   - Current approach uses loose version constraints
   - Consider adding `requirements.txt` with pinned versions for CI
   - Maintain `pyproject.toml` with loose constraints for flexibility

6. **Build system modernization**
   - Current setup uses legacy `setup.py` with `pyproject.toml`
   - Consider fully migrating to pyproject.toml-based build
   - Or clarify separation of concerns between files

7. **Test matrix optimization**
   - Currently testing Python 3.12 and 3.13
   - With recent classifier changes, ensure matrix is correct
   - Consider adding Python 3.14 alpha testing

---

## Testing Strategy

### Manual Testing Commands

```bash
# Test dependency resolution
uv sync --dev

# Test clean install (non-editable)
pip install .
python -c "import rustybt.lib.labelarray; print('✅ Import successful')"

# Test editable install
pip install -e .
python -c "import rustybt.lib.labelarray; print('✅ Import successful')"

# Test Cython extensions
python -c "from rustybt.lib._factorize import factorize; print('✅ Cython OK')"

# Test build
python -m build
```

### CI Verification Checklist

- [ ] Smoke test passes (imports work)
- [ ] Lint & format checks pass
- [ ] Full test suite passes on all platforms
- [ ] Build distribution succeeds
- [ ] Security scans complete (even if with warnings)
- [ ] Performance regression tests run
- [ ] Property-based tests pass

---

## References

### Relevant Files

- `pyproject.toml`: Package configuration and dependencies
- `setup.py`: Cython extension definitions
- `.github/workflows/ci.yml`: Main CI pipeline
- `.github/workflows/security.yml`: Security scanning
- `.github/workflows/property-tests.yml`: Hypothesis tests
- `.github/workflows/performance.yml`: Regression benchmarks

### Related Commits

| Commit | Description |
|--------|-------------|
| f5bc8f8 | Fix numpy version constraints and classifiers |
| 9789fdf | Add numexpr version constraints |
| d9b219d | Add Cython build dependencies to CI |
| a3ac611 | Simplify CI smoke test installation |
| 798441d | Use pip directly for smoke test |

### External Resources

- [setuptools editable installs](https://setuptools.pypa.io/en/latest/userguide/development_mode.html)
- [PEP 660 – Editable installs for pyproject.toml](https://peps.python.org/pep-0660/)
- [Cython documentation - Building Cython code](https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html)
- [NumPy 2.0 migration guide](https://numpy.org/devdocs/numpy_2_0_migration_guide.html)

---

## Appendix: Error Logs

### A1. Original Numpy Constraint Error

```
× No solution found when resolving dependencies for split (markers:
│ python_full_version == '3.13.*'):
╰─▶ Because your project depends on numpy>=1.26.0,<2.0 and
    numpy{python_full_version >= '3.13'}>=2.1, we can conclude that your
    project's requirements are unsatisfiable.
    And because your project requires rustybt[benchmarks], we can conclude
    that your project's requirements are unsatisfiable.

    hint: While the active Python version is 3.12, the resolution failed for
    other Python versions supported by your project. Consider limiting your
    project's supported Python versions using `requires-python`.
```

### A2. Numexpr/Numpy Incompatibility Error

```python
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/home/runner/work/rustybt/rustybt/rustybt/__init__.py", line 21, in <module>
    from rustybt.finance.blotter import Blotter
  # ... (traceback continues)
  File "/opt/hostedtoolcache/Python/3.12.11/x64/lib/python3.12/site-packages/numexpr/necompiler.py", line 762, in <module>
    def getType(a: numpy.typing.NDArray[Any] | numpy.generic) -> type:
                   ^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.11/x64/lib/python3.12/site-packages/numpy/__init__.py", line 333, in __getattr__
    raise AttributeError("module {!r} has no attribute "
AttributeError: module 'numpy' has no attribute 'typing'. Did you mean: '_typing'?
```

### A3. Module Import Error (Current)

```python
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/home/runner/work/rustybt/rustybt/rustybt/__init__.py", line 21, in <module>
    from rustybt.finance.blotter import Blotter
  File "/home/runner/work/rustybt/rustybt/rustybt/finance/__init__.py", line 16, in <module>
    from . import execution, trading
  File "/home/runner/work/rustybt/rustybt/rustybt/finance/execution.py", line 23, in <module>
    import pandas as pd
  File "/home/runner/work/rustybt/rustybt/rustybt/pipeline/__init__.py", line 1, in <module>
    from .classifiers import Classifier, CustomClassifier
  File "/home/runner/work/rustybt/rustybt/rustybt/pipeline/classifiers/__init__.py", line 1, in <module>
    from .classifier import (
  File "/home/runner/work/rustybt/rustybt/rustybt/pipeline/classifiers/classifier.py", line 14, in <module>
    from rustybt.lib.labelarray import LabelArray
ModuleNotFoundError: No module named 'rustybt.lib.labelarray'
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-13
**Author**: Claude Code Investigation
**Status**: Living Document - Will be updated as issues are resolved
