# CI/CD Fix Plan - Comprehensive Solution

## Analysis Date: October 13, 2025

## Executive Summary
The CI/CD pipeline has 5 critical failures across different workflows. All workflows are currently failing, preventing successful builds and deployments. This document provides a complete fix plan with prioritized solutions.

## Critical Issues Identified

### 1. Package Import Error (CRITICAL - Blocks ALL Tests)
**Status**: 🔴 FAILING
**Workflow**: CI - Smoke Test
**Error**: `ModuleNotFoundError: No module named 'rustybt.lib.labelarray'`
**Location**: `/rustybt/pipeline/classifiers/classifier.py:14`

**Root Cause**:
- `labelarray.py` exists in `rustybt/lib/` but is not being included in the package distribution
- The MANIFEST.in file only includes `.pyx`, `.pxd`, `.pxi` files but not `.py` files in recursive includes
- The package-data configuration in pyproject.toml might be missing the labelarray module

**Fix**:
```python
# Update MANIFEST.in
recursive-include rustybt *.py
recursive-include rustybt *.pyx
recursive-include rustybt *.pxd
recursive-include rustybt *.pxi

# Update pyproject.toml [tool.setuptools.package-data]
"rustybt.lib" = ["*.py", "*.pyx", "*.pxd", "*.pxi", "*.so", "*.pyd"]
```

### 2. Security Vulnerabilities - SQL Injection (BLOCKING)
**Status**: 🔴 FAILING
**Workflow**: Security Checks
**Severity**: Medium (CWE-89)
**Locations**:
- `rustybt/assets/asset_db_migrations.py:78`
- `rustybt/assets/asset_db_migrations.py:409`

**Issues**:
1. Line 78: `f"INSERT INTO {name} SELECT {selection_string} FROM {tmp_name}"`
2. Lines 409-429: Multi-line f-string SQL query with table interpolation

**Fix**:
Since these are database migration scripts with validated internal table names:
```python
# Add validation and use SQLAlchemy's text() with bound parameters where possible
from sqlalchemy import text

# Validate table names against whitelist
VALID_TABLES = {'equities', 'exchanges', 'futures', 'assets'}
if name not in VALID_TABLES:
    raise ValueError(f"Invalid table name: {name}")

# Use parameterized queries where possible
# For schema operations that require table names, add # nosec B608 after validation
```

### 3. Property Test Coverage Failure
**Status**: 🔴 FAILING
**Workflow**: Property-Based Tests
**Coverage**: 4/10 (40%) - Below 60% threshold

**Missing Coverage**:
- `rustybt.data.polars.parquet_minute_bars` (0/1 tests)
- `rustybt.data.polars.parquet_daily_bars` (0/1 tests)
- `rustybt.data.polars.data_portal` (0/2 tests)
- `rustybt.finance.metrics.core` (0/? tests)
- `rustybt.finance.decimal.blotter` (0/2 tests)
- `rustybt.finance.slippage` (0/? tests)

**Fix**: Create property tests for each module in `tests/property/`

### 4. Deprecated GitHub Action
**Status**: 🔴 FAILING
**Workflow**: Performance Regression
**Error**: `This request has been automatically failed because it uses a deprecated version of actions/upload-artifact: v3`

**Fix**:
```yaml
# In .github/workflows/performance.yml line 82
- uses: actions/upload-artifact@v4  # Changed from v3
```

### 5. Benchmarks Workflow Failure
**Status**: 🔴 FAILING
**Workflow**: .github/workflows/benchmarks.yml
**Issue**: Workflow fails immediately with no logs

**Potential Causes**:
- Workflow file syntax error
- Missing dependencies
- Incorrect Python setup

**Fix**: Verify workflow syntax and ensure all dependencies are available

## Implementation Priority

### Phase 1: Critical Blockers (Must fix first)
1. ✅ Fix package import error (blocks all tests)
2. ✅ Update deprecated GitHub action (blocks performance tests)

### Phase 2: Security & Quality Gates
3. ✅ Fix SQL injection warnings (security gate)
4. ✅ Fix benchmarks workflow

### Phase 3: Test Coverage
5. ✅ Add missing property tests (quality gate)

## Files to Modify

### High Priority
1. `/Users/jerryinyang/Code/bmad-dev/rustybt/MANIFEST.in`
2. `/Users/jerryinyang/Code/bmad-dev/rustybt/pyproject.toml`
3. `/Users/jerryinyang/Code/bmad-dev/rustybt/.github/workflows/performance.yml`

### Medium Priority
4. `/Users/jerryinyang/Code/bmad-dev/rustybt/rustybt/assets/asset_db_migrations.py`
5. `/Users/jerryinyang/Code/bmad-dev/rustybt/.github/workflows/benchmarks.yml`

### Lower Priority
6. Create new test files in `/Users/jerryinyang/Code/bmad-dev/rustybt/tests/property/`

## Verification Steps

After implementing fixes:
1. Run `uv sync` to ensure dependencies are installed
2. Run `python -m pip install -e .` to test local installation
3. Run `python -c "from rustybt.lib import labelarray"` to verify import
4. Run `uv run bandit -r rustybt -ll -i` to verify security fixes
5. Run `uv run python scripts/property_test_coverage.py --report` to check coverage
6. Push changes and verify all GitHub Actions pass

## Expected Outcome
All 5 workflows should pass:
- ✅ CI (Smoke Test, Lint, Tests, Build)
- ✅ Security
- ✅ Property-Based Tests
- ✅ Performance Regression
- ✅ Performance Benchmarks

## Notes
- The labelarray import issue is the most critical as it blocks all other tests
- SQL injection warnings are in migration code with internal table names, but should still be addressed
- Property test coverage needs to reach 60% minimum threshold
- GitHub deprecated v3 artifacts actions on April 16, 2024
