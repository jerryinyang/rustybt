# Build System Architecture

**Last Updated**: 2025-10-13
**Status**: Active
**Maintainer**: RustyBT Contributors

---

## Overview

RustyBT uses a hybrid build system that combines:
- **setuptools** for Python package management
- **Cython** for performance-critical Python/C extensions
- **setuptools-rust** for Rust/Python interop via PyO3
- **pyproject.toml** for modern package metadata and configuration

This document describes the architecture, rationale, and maintenance guidelines.

---

## Architecture Diagram

```
pyproject.toml
├── [project] - Package metadata, dependencies, scripts
├── [build-system] - Build dependencies (setuptools, Cython, Rust tooling)
├── [tool.setuptools] - Package discovery configuration
│   ├── packages.find - Explicit include=['rustybt*']
│   └── package-data - Include .pyx, .pxd, .pxi, .so, .pyd files
└── [tool.setuptools_scm] - Version management from git tags

setup.py
├── Extension definitions - 13 Cython modules
│   ├── rustybt.assets._assets
│   ├── rustybt.lib.adjustment
│   ├── rustybt.lib._factorize
│   ├── rustybt.lib.*window (float64, int64, uint8, label)
│   ├── rustybt.gens.sim_engine
│   └── ... (more extensions)
├── RustExtension - rustybt._rustybt (PyO3 binding)
└── setup() - Ties everything together

MANIFEST.in
├── recursive-include rust * - Rust source files
├── recursive-include rustybt *.pyx - Cython implementation files
├── recursive-include rustybt *.pxd - Cython declaration files
└── recursive-include rustybt *.pxi - Cython include files
```

---

## File Responsibilities

### pyproject.toml
**Purpose**: Modern package metadata and configuration (PEP 517/518/621)

**Responsibilities**:
- Package name, version, description, authors, classifiers
- Runtime dependencies with version constraints
- Optional dependency groups (test, dev, benchmarks, etc.)
- Entry points (CLI scripts)
- Tool configurations (pytest, mypy, ruff, black)
- Package discovery configuration

**Key Sections**:
```toml
[build-system]
requires = [
    'setuptools>=64.0.0',       # Modern setuptools
    'setuptools_scm[toml]>=8.0', # Version from git
    'setuptools-rust>=1.5.0',    # Rust extension support
    'Cython>=0.29.21,<3.2.0',    # Cython compiler
    'numpy>=2.0.0 ; python_version>"3.9"',  # Build-time numpy
]
build-backend = 'setuptools.build_meta'

[tool.setuptools.packages.find]
where = ['.']
include = ['rustybt*']  # CRITICAL: Explicit package discovery
exclude = ['tests*', 'deps*', 'docs*', '.bmad-core*']
```

### setup.py
**Purpose**: Extension building (Cython and Rust)

**Why still needed**:
- setuptools does not yet have native Cython extension support in pyproject.toml
- Complex extension configurations (numpy include dirs, macros, dependencies)
- Rust extension configuration via setuptools-rust

**Responsibilities**:
- Define all Cython Extension objects
- Configure Cython compiler options
- Define Rust extensions via setuptools-rust
- Call cythonize() to compile .pyx → .c → .so
- Specify include directories (numpy headers)

**Key Functions**:
```python
def window_specialization(typename):
    """Factory for type-specialized rolling window extensions."""
    return Extension(
        name=f"rustybt.lib._{typename}window",
        sources=[f"rustybt/lib/_{typename}window.pyx"],
        depends=["rustybt/lib/_windowtemplate.pxi"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    )

setup(
    packages=find_packages(
        where='.',
        include=['rustybt*'],  # Must match pyproject.toml
        exclude=[...]
    ),
    ext_modules=cythonize(ext_modules, **ext_options),
    rust_extensions=[...],
    include_dirs=[numpy.get_include()],
)
```

### MANIFEST.in
**Purpose**: Include non-Python files in source distributions (sdist)

**Responsibilities**:
- Include Rust source code for building from sdist
- Include Cython source files (.pyx, .pxd, .pxi) for rebuilding
- Include __init__.py files explicitly (package markers)

**Why needed**:
- Binary wheels (.whl) include compiled extensions (.so, .pyd)
- Source distributions (.tar.gz) need source files for users to build locally
- Not all files are auto-included by setuptools

---

## Extension Modules

### Cython Extensions (13 modules)

| Module | Purpose | Lines | Critical Path |
|--------|---------|-------|---------------|
| `rustybt.gens.sim_engine` | Trading simulation engine | ~4,200 | **YES** - Import chain |
| `rustybt.lib.adjustment` | Corporate action adjustments | 1,054 | YES |
| `rustybt.lib._factorize` | Categorical data handling | 246 | YES |
| `rustybt.lib.*window` | Rolling window operations | ~800 | YES |
| `rustybt.lib.rank` | Ranking algorithms | 172 | YES |
| `rustybt.assets._assets` | Asset class implementations | ~500 | YES |
| `rustybt.data._equities` | Equity data handling | ~300 | Medium |
| `rustybt.data._adjustments` | Price adjustments | ~200 | Medium |
| `rustybt.data._minute_bar_internal` | Minute bar data | ~150 | Medium |
| `rustybt.data._resample` | Data resampling | ~180 | Medium |
| `rustybt.finance._finance_ext` | Financial calculations | ~250 | Medium |
| `rustybt._protocol` | Protocol implementations | ~100 | Low |
| `rustybt.assets.continuous_futures` | Futures handling | ~200 | Low |

### Rust Extension (1 module)

| Module | Purpose | Crate | Binding |
|--------|---------|-------|---------|
| `rustybt._rustybt` | High-performance computation | `rust/crates/rustybt` | PyO3 |

---

## Build Process

### Local Development

```bash
# Editable install (recommended for development)
pip install -e .

# Behavior:
# 1. Creates egg-link in site-packages pointing to source directory
# 2. Compiles Cython extensions in place (rustybt/lib/*.so)
# 3. Compiles Rust extension to target/release
# 4. Changes to Python code are immediately visible
# 5. Changes to Cython/Rust require rebuild: pip install -e . --force-reinstall --no-deps
```

### CI/Production Install

```bash
# Non-editable install (production)
pip install .

# Behavior:
# 1. Builds wheel (.whl) in temporary directory
# 2. Compiles all extensions
# 3. Copies everything to site-packages
# 4. Isolated from source directory
# 5. More reliable but slower
```

### Wheel Building

```bash
# Build wheel and sdist
python -m build

# Outputs:
# dist/rustybt-X.Y.Z-cp312-cp312-macosx_11_0_arm64.whl (wheel)
# dist/rustybt-X.Y.Z.tar.gz (source distribution)
```

---

## Package Discovery

**Critical Configuration**: Explicit package inclusion

### Why Explicit?

**Problem**: Implicit package discovery can miss subpackages with Cython extensions.

**Old behavior** (without `include`):
```toml
[tool.setuptools.packages.find]
where = ['.']
exclude = ['tests*', 'deps*', 'docs*']
```
- setuptools auto-discovers packages by looking for `__init__.py`
- May skip packages if structure is unusual or extensions confuse discovery
- **Result**: `rustybt.gens` package not installed in CI builds

**New behavior** (with `include`):
```toml
[tool.setuptools.packages.find]
where = ['.']
include = ['rustybt*']  # Explicit: "include anything matching rustybt*"
exclude = ['tests*', 'deps*', 'docs*']
```
- Explicitly tells setuptools to include ALL packages starting with `rustybt`
- Guarantees `rustybt.gens`, `rustybt.lib`, etc. are found
- **Result**: All packages reliably installed

### Verification

```python
# Check installed packages
import rustybt
import os
import glob

base = os.path.dirname(rustybt.__file__)
packages = [
    d for d in os.listdir(base)
    if os.path.isdir(os.path.join(base, d))
    and os.path.exists(os.path.join(base, d, '__init__.py'))
]
print(f"Installed packages: {packages}")

# Should include: assets, data, finance, gens, lib, pipeline, etc.
```

---

## Package Data

**Configuration**:
```toml
[tool.setuptools.package-data]
"*" = [
    "*.pyi",      # Type stubs
    "*.pyx",      # Cython source (for debugging)
    "*.pxi",      # Cython include files
    "*.pxd",      # Cython declaration files
    "*.so",       # Compiled extensions (Linux/Mac)
    "*.pyd",      # Compiled extensions (Windows)
]
"rustybt" = [
    "py.typed",   # PEP 561 marker for type checking
]
```

**Why include compiled extensions in package data?**
- Ensures `.so`/`.pyd` files are copied to site-packages during install
- Without this, extensions are built but not installed
- Critical for non-editable installs

---

## Common Issues and Solutions

### Issue 1: "ModuleNotFoundError: No module named 'rustybt.gens.sim_engine'"

**Symptom**: Import fails after `pip install .` but works in editable mode

**Cause**: Package not discovered during installation

**Solution**:
1. ✅ Add explicit `include=['rustybt*']` in `[tool.setuptools.packages.find]`
2. ✅ Add matching `include=['rustybt*']` in `setup.py` `find_packages()`
3. ✅ Include `*.so` and `*.pyd` in `[tool.setuptools.package-data]`

### Issue 2: Cython Extensions Not Building

**Symptom**: No `.so` files after `pip install -e .`

**Cause**: Missing build dependencies or Cython errors

**Diagnosis**:
```bash
pip install -e . --verbose 2>&1 | grep -i "error\|cython\|extension"
```

**Common causes**:
- Cython not installed: `pip install Cython`
- numpy headers missing: Ensure numpy is installed before building
- Compiler errors: Check C compiler is available (gcc/clang/MSVC)

### Issue 3: Rust Extension Not Building

**Symptom**: `ImportError: cannot import name 'rust_sum'`

**Cause**: Rust toolchain missing or build failure

**Solution**:
```bash
# Install Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install setuptools-rust
pip install setuptools-rust

# Rebuild
pip install -e . --force-reinstall --no-deps
```

### Issue 4: Version Conflicts in CI

**Symptom**: Dependency resolution failures for numpy/numexpr

**Solution**: Version-specific constraints in pyproject.toml
```toml
dependencies = [
    "numpy>=1.26.0,<2.0; python_version=='3.12'",  # Note: == not >=
    "numpy>=2.1; python_version>='3.13'",
    'numexpr >=2.8.0,<2.10; python_version=="3.12"',
    'numexpr >=2.10; python_version>="3.13"',
]
```

---

## Testing the Build System

### Local Verification

```bash
# 1. Clean environment
python -m venv test_env
source test_env/bin/activate  # or test_env\Scripts\activate on Windows

# 2. Install from source
pip install .

# 3. Test imports (from different directory)
cd /tmp
python -c "from rustybt.gens.sim_engine import SESSION_END; print('✅ SUCCESS')"

# 4. Check all Cython extensions
python -c "
from rustybt.lib.adjustment import Float64Multiply
from rustybt.lib._factorize import factorize_strings
from rustybt.gens.sim_engine import SESSION_END
from rustybt.lib.rank import rankdata_2d_f64
from rustybt.assets._assets import Asset
print('✅ All extensions importable')
"

# 5. Check package structure
python -c "
import rustybt, os, glob
base = os.path.dirname(rustybt.__file__)
so_files = glob.glob(os.path.join(base, '**/*.so'), recursive=True)
print(f'Found {len(so_files)} compiled extensions')
assert len(so_files) >= 13, 'Missing Cython extensions'
print('✅ Package structure correct')
"
```

### CI Verification (Automated)

The CI workflow includes comprehensive verification:

```yaml
- name: Verify package structure after installation
  run: |
    echo "=== Checking installed package location ==="
    python -c "import rustybt, os; print(f'RustyBT location: {os.path.dirname(rustybt.__file__)}')"

    echo "=== Checking for compiled extensions ==="
    python -c "import rustybt, os, glob; base = os.path.dirname(rustybt.__file__); so_files = glob.glob(os.path.join(base, '**/*.so'), recursive=True); print(f'Found {len(so_files)} extensions')"

    echo "=== Testing critical imports ==="
    python -c "from rustybt.gens import sim_engine; print('✅ sim_engine OK')"
```

---

## Future Improvements

### Short-term (Next Release)
- [ ] Add wheel inspection step to CI (verify contents of built wheels)
- [ ] Document platform-specific build requirements
- [ ] Add build troubleshooting flowchart

### Medium-term (6 months)
- [ ] Investigate setuptools 69.3+ native Cython support
- [ ] Consider migrating extension definitions to pyproject.toml (when mature)
- [ ] Add automated build performance benchmarks

### Long-term (1+ year)
- [ ] Evaluate meson-python as alternative build backend
- [ ] Consider splitting Cython extensions into separate subpackages
- [ ] Investigate compiled wheel distribution via PyPI

---

## References

### Official Documentation
- [setuptools - Building Extension Modules](https://setuptools.pypa.io/en/latest/userguide/ext_modules.html)
- [setuptools - Package Discovery](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html)
- [PEP 517 – Build System Interface](https://peps.python.org/pep-0517/)
- [PEP 518 – Build System Requirements](https://peps.python.org/pep-0518/)
- [PEP 621 – Metadata in pyproject.toml](https://peps.python.org/pep-0621/)
- [PEP 660 – Editable Installs](https://peps.python.org/pep-0660/)
- [Cython Documentation](https://cython.readthedocs.io/)
- [setuptools-rust](https://github.com/PyO3/setuptools-rust)

### Internal Documentation
- [CI/CD Blocking Issues](../pr/2025-10-13-CI-BLOCKING-dependency-issues.md)
- [Solutions Proposal](../pr/2025-10-13-CI-BLOCKING-solutions-proposal.md)
- [Contributing Guide](../../CONTRIBUTING.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-13
**Maintainer**: RustyBT Core Team
**Review Schedule**: Quarterly or after major build system changes
