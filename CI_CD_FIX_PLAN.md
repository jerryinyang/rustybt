# CI/CD Failure Analysis and Remediation Plan

## Executive Summary
Multiple workflows (CI Smoke Test, Testing, Code Quality, Property-Based Tests) failed due to missing package modules at runtime and import-time side effects. Primary root causes:
- .gitignore patterns inadvertently ignored `rustybt/lib/**`, so pure-Python modules (labelarray, adjusted_array, normalize, quantiles) were not committed and thus absent in CI.
- `rustybt/__init__.py` imported pipeline components at import time, surfacing missing submodules during a simple `import rustybt` in the smoke step.

We fixed the ignore rules, added the missing modules, and made top-level imports lazy.

## Evidence
- CI Smoke Test (Run 18472114171): `ModuleNotFoundError: No module named 'rustybt.lib.labelarray'` during `import rustybt` in the verification step.
- Property-Based Tests (Run 18472114155/…): identical error raised from tests’ `import rustybt` in conftest.

## Root Causes and Fixes
1) .gitignore masking sources
- Cause: `lib/` (duplicated) matched nested paths; `!rustybt/lib/` didn’t re-include contents.
- Fix: Anchor ignores to `/lib/` and `/lib64/`, and explicitly unignore `!rustybt/lib/**`.
  - Result: all `rustybt/lib/*.py` are now tracked.

2) Import-time side effects
- Cause: `rustybt/__init__.py` imported heavy modules (algorithm/pipeline) at import time, failing early when submodules missing.
- Fix: Added module-level `__getattr__` to lazily resolve `TradingAlgorithm`, `Blotter`, and `run_algorithm`.

3) Code quality gates
- Fixed ruff findings in `labelarray.py` (no `assert`, avoid builtin shadowing).

## Validation Plan
- Local check: `import rustybt` and `from rustybt.lib.labelarray import LabelArray` succeed from source.
- After merge:
  - Smoke Test should pass package verification and proceed.
  - Testing/Property-Based Tests should no longer fail on missing `rustybt.lib.*`.
  - Code Quality should pass for touched files.

## Notes on Local Debugging
- act installed (via Homebrew). Examples:
  - `act -l`
  - `act -j smoke-test -W .github/workflows/ci.yml --container-architecture linux/amd64`
  - Docker is available locally.

## Outstanding Item
- Local pre-commit hook `detect-mocks` calls `python` (not available). Either:
  - Adjust hook to use `python3`, or
  - Install `python` shim, or
  - Temporarily commit with `--no-verify` (if approved).

---
Legacy plan (for reference):
## Executive Summary
Following the commit `21d4978` ("fix: Import from specific module files for coverage detection"), 9 out of 10 CI/CD workflows are failing. The failures are primarily due to:
1. A circular import issue in `rustybt.lib`
2. Missing pytest/ruff executables in uv environments
3. Deprecated GitHub Actions artifacts upload version
4. Deleted test files in the local workspace

## Failure Analysis

### 1. Smoke Test Failure (CI Workflow) ⚠️ CRITICAL
**Status:** FAILING
**Root Cause:** Circular import in `rustybt.lib` module

**Error:**
```python
ImportError: cannot import name 'labelarray' from partially initialized module 'rustybt.lib'
(most likely due to a circular import)
```

**Issue Details:**
- The `rustybt/lib/__init__.py` uses `from . import labelarray`
- When `rustybt.pipeline.classifiers.classifier` imports `from rustybt.lib.labelarray import LabelArray`, it triggers the circular import
- This blocks the entire CI pipeline as smoke test is a prerequisite for other jobs

### 2. Property-Based Tests Failure
**Status:** FAILING
**Root Cause:** pytest executable not found in uv environment

**Error:**
```bash
error: Failed to spawn: `pytest`
  Caused by: No such file or directory (os error 2)
```

**Issue Details:**
- The workflow uses `uv run pytest` but pytest isn't available
- The dev dependencies might not be installed correctly with `uv sync --dev`

### 3. Code Quality Checks Failure
**Status:** FAILING
**Root Cause:** ruff executable not found in uv environment

**Error:**
```bash
error: Failed to spawn: `ruff`
  Caused by: No such file or directory (os error 2)
```

### 4. Testing Workflow Failure
**Status:** FAILING
**Root Cause:** Deprecated GitHub Actions artifact upload

**Error:**
```
This request has been automatically failed because it uses a deprecated version of
`actions/upload-artifact: v3`. Learn more: https://github.blog/changelog/2024-04-16-deprecation-notice-v3-of-the-artifact-actions/
```

### 5. Security Workflow
**Status:** FAILING (but running)
**Root Cause:** Warnings from bandit but workflow continues

### 6. Performance Regression Workflow
**Status:** SUCCESS ✅
This is the only passing workflow.

## Fix Plan

### Priority 1: Fix Circular Import (Blocks Everything)

**File:** `rustybt/lib/__init__.py`

**Current Code:**
```python
from . import labelarray, adjusted_array, normalize, quantiles
```

**Fixed Code:**
```python
# Lazy imports to avoid circular dependencies
# These modules will be imported when accessed
__all__ = ['labelarray', 'adjusted_array', 'normalize', 'quantiles']

def __getattr__(name):
    if name == 'labelarray':
        from . import labelarray
        return labelarray
    elif name == 'adjusted_array':
        from . import adjusted_array
        return adjusted_array
    elif name == 'normalize':
        from . import normalize
        return normalize
    elif name == 'quantiles':
        from . import quantiles
        return quantiles
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
```

### Priority 2: Fix GitHub Actions Artifact Upload

**Files to Update:**
- `.github/workflows/testing.yml`
- `.github/workflows/property-tests.yml`
- All other workflows using `actions/upload-artifact@v3`

**Change:** Replace all instances of `actions/upload-artifact@v3` with `actions/upload-artifact@v4`

### Priority 3: Fix uv Dependencies Installation

**Files to Update:**
- `.github/workflows/property-tests.yml`
- `.github/workflows/code-quality.yml`
- `.github/workflows/testing.yml`
- `.github/workflows/security.yml`

**Change:** Ensure dev dependencies are properly installed
```yaml
- name: Install dependencies
  run: |
    uv sync --all-extras
    # Or alternatively:
    # uv pip install -e ".[dev,test]" --system
```

### Priority 4: Local Workspace Cleanup

**Local Changes to Address:**
- Deleted test files in `tests/property/` (should be in `tests/property_tests/`)
- Modified `rustybt/_version.py`

**Actions:**
1. Remove `.delete/` directory
2. Clean up the deleted test files from git status
3. Review changes to `_version.py`

## Implementation Steps

1. **Immediate Fix (5 minutes)**
   - Fix the circular import in `rustybt/lib/__init__.py`
   - Commit and push to trigger CI

2. **Workflow Updates (10 minutes)**
   - Update all workflows to use `actions/upload-artifact@v4`
   - Fix uv dependency installation commands
   - Commit and push

3. **Verification (5 minutes)**
   - Monitor GitHub Actions dashboard
   - Verify all workflows pass
   - Run local tests to confirm

## Alternative Quick Fix

If the lazy import solution doesn't work, an alternative is to remove the imports from `__init__.py` entirely:

```python
# rustybt/lib/__init__.py
# Module imports handled directly by importers
__all__ = ['labelarray', 'adjusted_array', 'normalize', 'quantiles']
```

This requires no other code changes as modules already import directly from submodules.

## Success Criteria

✅ All 10 CI/CD workflows pass successfully:
- CI (Smoke Test, Lint, Tests, Build, Security, Performance)
- Testing
- Property-Based Tests
- Code Quality
- Security
- Performance Regression (already passing)
- Benchmarks
- Dependency Security
- Nightly Benchmarks
- Zero-Mock Enforcement

## Risk Assessment

- **Low Risk:** Artifact version upgrade (v3 → v4)
- **Low Risk:** Dependency installation fixes
- **Medium Risk:** Circular import fix (needs testing)

## Timeline

- **Total Time:** ~20-30 minutes
- **First Success Expected:** Within 10 minutes (after circular import fix)
- **Full Resolution:** Within 30 minutes

## Post-Fix Actions

1. Document the circular import issue prevention in contributing guidelines
2. Add pre-commit hooks to catch circular imports
3. Review why property test files were moved/deleted
4. Consider adding smoke tests to pre-commit hooks
