# CI/CD Blocking Issues - Solutions Proposal

**Date**: 2025-10-13
**Status**: 🔴 CRITICAL - Smoke Test Failing on All CI Runs
**Author**: Factory Droid Analysis
**Related**: [CI-BLOCKING-dependency-issues.md](./2025-10-13-CI-BLOCKING-dependency-issues.md)

---

## Executive Summary

The CI pipeline is blocked by a **Cython module import failure** in the smoke test. After resolving numpy/numexpr dependency conflicts, a new critical issue emerged: `rustybt.gens.sim_engine` (Cython extension) cannot be imported after `pip install .` in CI, despite successful builds.

**Current Error**:
```python
ModuleNotFoundError: No module named 'rustybt.gens.sim_engine'
```

**Impact**:
- ❌ All CI workflows blocked at smoke test stage
- ❌ Cannot merge any PRs (CI required to pass)
- ❌ Development velocity severely impacted

This document provides **3 actionable solutions** with implementation details, risk assessment, and recommendations.

---

## Root Cause Analysis

### The Problem

The package structure uses:
1. **Cython extensions** defined in `setup.py` (13 extensions including `rustybt.gens.sim_engine`)
2. **Mixed configuration**: `pyproject.toml` + `setup.py` for backwards compatibility
3. **setuptools build backend** with setuptools-rust for Rust extensions

**What Works**:
- ✅ Local development (editable installs work fine)
- ✅ Package builds successfully in CI (~3-4 minutes build time)
- ✅ Build artifacts are created (no errors during build)
- ✅ Dependencies resolve correctly

**What Fails**:
- ❌ Cython extensions not importable after CI installation
- ❌ Module directory structure not properly created in site-packages

### Evidence from CI Logs

```
File "/home/runner/work/rustybt/rustybt/rustybt/finance/cancel_policy.py", line 18
    from rustybt.gens.sim_engine import SESSION_END
ModuleNotFoundError: No module named 'rustybt.gens.sim_engine'
```

**Import chain**:
```
rustybt/__init__.py
  → finance/blotter.py
    → finance/cancel_policy.py
      → gens/sim_engine (FAILS HERE)
```

### Technical Deep Dive

**Package Structure**:
```
rustybt/
├── gens/
│   ├── __init__.py
│   ├── sim_engine.pyx     # Cython source
│   ├── sim_engine.c        # Generated C code (local)
│   └── sim_engine.*.so     # Compiled extension (local)
```

**setup.py Configuration**:
```python
Extension(
    name="rustybt.gens.sim_engine",
    sources=["rustybt/gens/sim_engine.pyx"],
    define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
)
```

**Potential Root Causes**:

1. **Missing `__init__.py` in installed package**
   - The `gens/` directory might not be recognized as a package after installation
   - setuptools package discovery may be excluding it

2. **Incomplete package discovery configuration**
   ```toml
   [tool.setuptools.packages.find]
   where = ['.']
   exclude = ['tests*', 'deps*', 'docs*', '.bmad-core*']
   ```
   - No explicit `include` parameter
   - May not discover nested packages with Cython extensions

3. **Build artifact not copied to correct location**
   - The `.so` file is built but not placed in the installed package directory
   - May be a setuptools build meta issue with mixed Cython/Rust extensions

4. **MANIFEST.in incomplete**
   ```
   recursive-include rust *
   ```
   - Only includes Rust sources
   - Missing explicit inclusion of Cython `.pyx`, `.pxd`, `.pxi` files

---

## Proposed Solutions

### Solution 1: Explicit Package Discovery (RECOMMENDED)

**Approach**: Explicitly list all packages and ensure Cython modules are included.

**Changes Required**:

**File**: `pyproject.toml`

```toml
[tool.setuptools.packages.find]
where = ['.']
include = ['rustybt*']  # Explicitly include all rustybt subpackages
exclude = ['tests*', 'deps*', 'docs*', '.bmad-core*']

[tool.setuptools.package-data]
"*" = [
    "*.pyi",
    "*.pyx",
    "*.pxi",
    "*.pxd",
    "*.so",      # ADD: Include compiled extensions
    "*.pyd",     # ADD: Include Windows extensions
]
```

**File**: `setup.py`

```python
setup(
    use_scm_version=True,
    packages=find_packages(
        where='.',
        include=['rustybt*'],
        exclude=['tests*', 'deps*', 'docs*', '.bmad-core*']
    ),
    ext_modules=cythonize(ext_modules, **ext_options),
    rust_extensions=[...],
    include_dirs=[numpy.get_include()],
    zip_safe=False,
)
```

**Pros**:
- ✅ Explicit control over package discovery
- ✅ Minimal changes required
- ✅ Preserves existing build configuration
- ✅ Should work for both editable and non-editable installs

**Cons**:
- ⚠️ May need to import `find_packages` from setuptools in setup.py
- ⚠️ Requires testing to ensure all packages are discovered

**Risk Level**: 🟡 LOW-MEDIUM

**Implementation Time**: 15-30 minutes

---

### Solution 2: Enhanced MANIFEST.in + Build Verification

**Approach**: Ensure all source files are included in the distribution and add build verification.

**Changes Required**:

**File**: `MANIFEST.in`

```
recursive-include rust *
recursive-include rustybt *.pyx
recursive-include rustybt *.pxd
recursive-include rustybt *.pxi
include rustybt/*/__init__.py
include rustybt/*/*/__init__.py
include rustybt/*/*/*/__init__.py
```

**File**: `.github/workflows/ci.yml` (add verification step)

```yaml
- name: Verify package structure after installation
  run: |
    echo "=== Checking installed package structure ==="
    python -c "import rustybt, os, subprocess; pkg_dir = os.path.dirname(rustybt.__file__); subprocess.run(['find', pkg_dir, '-name', '*.so', '-o', '-name', '*.pyd'])"

    echo "=== Checking for gens package ==="
    python -c "import os; import rustybt; gens_path = os.path.join(os.path.dirname(rustybt.__file__), 'gens'); print(f'gens exists: {os.path.exists(gens_path)}'); print(f'gens __init__.py: {os.path.exists(os.path.join(gens_path, \"__init__.py\"))}'); import subprocess; subprocess.run(['ls', '-la', gens_path])"

    echo "=== Attempting to import sim_engine ==="
    python -c "import sys; from rustybt.gens import sim_engine; print(f'sim_engine module: {sim_engine}'); print(f'sim_engine location: {sim_engine.__file__}')"

- name: Run smoke test
  run: |
    python -c "import rustybt; print(f'RustyBT version: {rustybt.__version__}')"
    python -c "import polars, hypothesis, structlog, pydantic; print('All dependencies OK')"
    python -c "from rustybt.lib.labelarray import LabelArray; print('✅ Cython/Python modules OK')"
```

**Pros**:
- ✅ Ensures source files are in distribution
- ✅ Adds diagnostic output for debugging
- ✅ Can identify exactly what's missing

**Cons**:
- ⚠️ May not fix the root cause if it's a build system issue
- ⚠️ More verbose CI output

**Risk Level**: 🟢 LOW

**Implementation Time**: 10-20 minutes

---

### Solution 3: Migrate to Pure pyproject.toml Build (LONG-TERM)

**Approach**: Remove `setup.py` and fully migrate to modern `pyproject.toml`-based build using `setuptools>=61.0`.

**Changes Required**:

**File**: `pyproject.toml`

```toml
[build-system]
requires = [
    'setuptools>=64.0.0',
    "setuptools_scm[toml]>=8.0",
    'setuptools-rust>=1.5.0',
    'wheel>=0.36.0',
    'Cython>=0.29.21,<3.2.0',
    'numpy>=2.0.0 ; python_version>"3.9"',
]
build-backend = 'setuptools.build_meta'

[tool.setuptools]
packages = { find = { where = ["."], include = ["rustybt*"] } }
include-package-data = true
zip-safe = false

[tool.setuptools.ext-modules]
# This would require setuptools 69.3+ which adds native Cython support
# Alternative: use a custom build backend or keep setup.py

# For now, may need to keep setup.py for Cython extensions
```

**File**: Delete or rename `setup.py` → `_setup.py.legacy`

**Note**: This is challenging because:
- setuptools native Cython support is still evolving
- Multiple extensions with dependencies (numpy include dirs, etc.)
- Rust extensions also need configuration
- May require custom build backend

**Pros**:
- ✅ Modern, future-proof approach
- ✅ Better package metadata handling
- ✅ Aligns with Python packaging standards (PEP 517/518)

**Cons**:
- ❌ High complexity - requires significant refactoring
- ❌ May introduce new issues
- ❌ Requires extensive testing across platforms
- ❌ Not compatible with current setuptools version constraints

**Risk Level**: 🔴 HIGH

**Implementation Time**: 4-8 hours + testing

**Recommendation**: **Defer** until after immediate CI blocking issue is resolved.

---

### Solution 4: Temporary CI Bypass (NOT RECOMMENDED)

**Approach**: Skip Cython module checks in smoke test, rely on full test suite.

**Changes**:

```yaml
- name: Run smoke test
  run: |
    python -c "import rustybt; print(f'RustyBT version: {rustybt.__version__}')" || echo "⚠️ Import warning"
    python -c "import polars, hypothesis, structlog, pydantic; print('All dependencies OK')"
  continue-on-error: true
```

**Pros**:
- ✅ Unblocks CI immediately
- ✅ Zero build configuration changes

**Cons**:
- ❌ Doesn't fix the root cause
- ❌ Reduces confidence in build artifacts
- ❌ May mask issues in deployment
- ❌ Not a real solution

**Risk Level**: 🔴 HIGH (technical debt)

**Recommendation**: **Only use as last resort** if all other solutions fail.

---

## Recommended Action Plan

### Phase 1: Quick Win (Estimated: 1-2 hours)

1. **Implement Solution 1 + Solution 2 combined**
   - Update `pyproject.toml` with explicit package discovery
   - Enhance `MANIFEST.in` with Cython sources
   - Add verification steps to CI
   - Test locally: `pip install .` in fresh venv
   - Push and verify CI passes

2. **If Phase 1 fails, implement diagnostic enhancement**
   - Add extensive debugging output to CI
   - Check installed package structure
   - Identify exactly what's missing
   - Adjust Solution 1/2 based on findings

### Phase 2: Root Cause Fix (If Phase 1 insufficient)

3. **Investigate setup.py Cython build**
   - Verify `ext_modules` configuration
   - Check if extensions are being built but not installed
   - May need to add explicit `package_dir` mapping
   - Consider using `setuptools.find_namespace_packages`

4. **Test installation methods**
   ```bash
   # Clean test
   python -m pip install --no-cache-dir --force-reinstall .

   # Verify build output
   pip install --verbose .

   # Check wheel contents
   python -m build
   unzip -l dist/rustybt-*.whl | grep -E '(gens|sim_engine)'
   ```

### Phase 3: Long-term Improvement (Post-CI Fix)

5. **Documentation**
   - Document the fix in CHANGELOG.md
   - Update CONTRIBUTING.md with build troubleshooting
   - Add architecture decision record (ADR) for build system

6. **Consider Solution 3 (Modernization)**
   - Create spike/investigation task
   - Evaluate setuptools 69.3+ Cython support
   - Plan migration if benefits are clear

---

## Testing Strategy

### Local Testing Checklist

```bash
# 1. Clean environment
python -m venv test_venv
source test_venv/bin/activate  # or test_venv\Scripts\activate on Windows

# 2. Test non-editable install
pip install .
python -c "from rustybt.gens.sim_engine import SESSION_END; print('✅ SUCCESS')"

# 3. Test editable install
pip uninstall rustybt -y
pip install -e .
python -c "from rustybt.gens.sim_engine import SESSION_END; print('✅ SUCCESS')"

# 4. Check wheel contents
pip install build
python -m build
unzip -l dist/rustybt-*.whl | grep sim_engine

# 5. Verify all Cython extensions
python -c "
from rustybt.lib.adjustment import Float64Multiply
from rustybt.lib._factorize import factorize_strings
from rustybt.gens.sim_engine import SESSION_END
from rustybt.lib.rank import rankdata_2d_f64
print('✅ All Cython extensions importable')
"
```

### CI Verification

After implementing fix:

1. ✅ Smoke test passes on all platforms (ubuntu, macos, windows)
2. ✅ Full test suite passes
3. ✅ Build distribution job completes
4. ✅ No import errors in any workflow
5. ✅ Performance regression tests run (if on main branch)

---

## Additional Issues to Address

### Issue #2: Performance Regression Workflow - Deprecated Action (LOW PRIORITY)

**File**: `.github/workflows/performance.yml`

**Current**:
```yaml
- uses: actions/upload-artifact@v3
```

**Fix**:
```yaml
- uses: actions/upload-artifact@v4
```

**Impact**: Low - workflow fails immediately but doesn't block CI

---

### Issue #3: Security Workflow - Bandit Failures (MEDIUM PRIORITY)

The security workflow shows failures but with checkmarks, suggesting continue-on-error is configured but the summary step fails.

**Investigation needed**:
- Review actual bandit findings
- Determine if real issues or false positives
- Fix workflow summary logic

---

## Success Criteria

### Immediate (CI Unblocked)
- [ ] Smoke test passes in CI
- [ ] `rustybt.gens.sim_engine` is importable after `pip install .`
- [ ] All Cython extensions are importable
- [ ] CI workflows proceed beyond smoke test stage

### Short-term (Stable CI)
- [ ] All CI workflows passing consistently
- [ ] No import errors across any test
- [ ] Build artifacts are valid and installable
- [ ] Documentation updated with fix details

### Long-term (Robust Build System)
- [ ] Build configuration is well-documented
- [ ] Clear separation between build-time and runtime dependencies
- [ ] Consider migration to pure pyproject.toml (if feasible)
- [ ] CI includes comprehensive build verification

---

## References

- [setuptools documentation - Building Extension Modules](https://setuptools.pypa.io/en/latest/userguide/ext_modules.html)
- [setuptools documentation - Package Discovery](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html)
- [PEP 517 – A build-system independent format for source trees](https://peps.python.org/pep-0517/)
- [PEP 518 – Specifying Minimum Build System Requirements](https://peps.python.org/pep-0518/)
- [Cython documentation - Compilation](https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html)

---

## Appendix: Quick Reference Commands

### Debug CI Build
```bash
# View latest CI run
gh run list --limit 5

# Get detailed logs
gh run view <run-id> --log

# Watch run in progress
gh run watch <run-id>
```

### Local Build Testing
```bash
# Clean build
rm -rf build/ dist/ *.egg-info/
pip install -e .

# Build wheel and inspect
python -m build
unzip -l dist/*.whl

# Test in fresh environment
python -m venv fresh_test
source fresh_test/bin/activate
pip install dist/*.whl
python -c "from rustybt.gens.sim_engine import SESSION_END; print('OK')"
```

### Debugging Import Issues
```python
# Check package location
import rustybt
print(rustybt.__file__)

# List installed files
import pkg_resources
dist = pkg_resources.get_distribution('rustybt')
print(dist.location)

# Check for .so files
import os, glob
base = os.path.dirname(rustybt.__file__)
so_files = glob.glob(os.path.join(base, '**/*.so'), recursive=True)
print('\n'.join(so_files))
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-13
**Status**: Draft - Awaiting Implementation
**Next Steps**: Implement Phase 1 - Solutions 1 + 2
