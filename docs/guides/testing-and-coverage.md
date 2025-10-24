# Testing and Coverage Guide

**Last Updated**: 2025-10-24
**Framework Version**: rustybt (post Epic X4)
**Python Version**: 3.12+

---

## Overview

This guide provides comprehensive instructions for running tests and measuring code coverage in rustybt. The framework uses pytest for testing and coverage.py for measuring test coverage.

---

## Quick Start

### Running All Tests

```bash
# Run full test suite
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test module
pytest tests/benchmarks/test_models.py
```

### Measuring Coverage

**IMPORTANT**: Use `coverage run` instead of `pytest --cov` to avoid scipy/numpy compatibility issues.

```bash
# Run tests with coverage measurement
coverage run -m pytest tests/

# Generate coverage report
coverage report --include="rustybt/*"

# Generate HTML coverage report
coverage html --include="rustybt/*"
# Open htmlcov/index.html in browser

# Generate JSON coverage report
coverage json --include="rustybt/*"
```

---

## Test Organization

### Directory Structure

```
tests/
├── analytics/              # Analytics module tests
├── backtest/              # Backtest functionality tests
├── benchmarks/            # Performance benchmarking tests (Epic X4)
│   ├── test_comparisons.py   # 100% coverage
│   ├── test_exceptions.py    # 100% coverage
│   ├── test_models.py         # 99% coverage
│   ├── test_threshold.py      # 100% coverage
│   ├── test_profiling.py
│   ├── test_reporter.py
│   └── test_sequential.py
├── integration/           # Integration tests
├── optimization/          # Optimization module tests
├── property_tests/        # Hypothesis property-based tests
├── regression/            # Performance regression tests
└── validation/            # Cross-validation tests
```

### Test Types

1. **Unit Tests**: Test individual functions/classes in isolation
2. **Integration Tests**: Test interactions between components
3. **Property Tests**: Hypothesis-based property testing for invariants
4. **Regression Tests**: Ensure performance doesn't degrade
5. **Validation Tests**: Cross-validate against known good results

---

## Coverage Measurement

### Current Framework Coverage

**Overall**: 47% (16,615 / 35,304 statements)

**By Module Category**:

| Category | Average Coverage | Status |
|----------|------------------|--------|
| Benchmarks (X4) | 84% | ✅ Excellent |
| Analytics (X4) | 91% | ✅ Excellent |
| Polars Data | 81% | ✅ Good |
| Data Bundles | 82% | ✅ Good |
| Optimization Core | 54% | ⚠️ Needs Improvement |
| Legacy Zipline | 15-30% | ℹ️ Expected (not focus) |

**High-Coverage Modules (≥90%)**:
- `benchmarks/comparisons.py`: 100%
- `benchmarks/exceptions.py`: 100%
- `benchmarks/threshold.py`: 100%
- `benchmarks/models.py`: 99%
- `analytics/attribution.py`: 91%
- `analytics/risk.py`: 95%
- `analytics/notebook.py`: 93%
- `analytics/trade_analysis.py`: 90%
- `data/resample.py`: 96%
- `data/decimal_adjustments.py`: 100%
- `data/polars/cache_manager.py`: 94%
- `data/polars/metadata_catalog.py`: 92%
- `optimization/config.py`: 96%
- `country.py`: 100%
- `asset_db_schema.py`: 100%
- `backtest/artifact_manager.py`: 94%

---

## Running Specific Test Suites

### Benchmarks Tests (Epic X4)

```bash
# Run all benchmark tests
pytest tests/benchmarks/ -v

# Run with coverage
coverage run -m pytest tests/benchmarks/
coverage report --include="rustybt/benchmarks/*"

# Run specific test file
pytest tests/benchmarks/test_threshold.py -v
```

### Analytics Tests

```bash
# Run all analytics tests
pytest tests/analytics/ -v

# Run with coverage
coverage run -m pytest tests/analytics/
coverage report --include="rustybt/analytics/*"
```

### Optimization Tests

```bash
# Run all optimization tests
pytest tests/optimization/ -v

# Run with coverage
coverage run -m pytest tests/optimization/
coverage report --include="rustybt/optimization/*"
```

### Property-Based Tests

```bash
# Run hypothesis property tests
pytest tests/property_tests/ -v

# Run with custom Hypothesis profile
pytest tests/property_tests/ --hypothesis-profile=quick
```

---

## Important: scipy/numpy Compatibility Issue

### Problem

When using `pytest --cov`, scipy functions fail with:
```
AttributeError: module 'numpy.dtypes' has no attribute 'VoidDType'
```

This is caused by pytest-cov's instrumentation conflicting with scipy 1.16.2 and numpy 1.26.4.

### Solution

✅ **Use `coverage run` instead of `pytest --cov`**:

```bash
# ❌ DON'T USE THIS (will fail with scipy tests)
pytest --cov=rustybt tests/benchmarks/

# ✅ USE THIS INSTEAD
coverage run -m pytest tests/benchmarks/
coverage report --include="rustybt/benchmarks/*"
```

This approach bypasses pytest-cov's instrumentation and works perfectly with scipy.

---

## Test Markers

### Available Markers

```python
@pytest.mark.integration    # Integration tests
@pytest.mark.property        # Property-based tests
@pytest.mark.regression      # Performance regression tests
@pytest.mark.slow            # Slow-running tests
@pytest.mark.validation      # Validation tests
@pytest.mark.benchmark       # Performance benchmarks
```

### Running Tests by Marker

```bash
# Run only integration tests
pytest tests/ -m integration

# Run only fast tests (exclude slow)
pytest tests/ -m "not slow"

# Run property and regression tests
pytest tests/ -m "property or regression"
```

---

## Coverage Targets

### Epic X4 Targets

- **Benchmarks core modules**: ≥90% (✅ Achieved: 99.5% average for threshold.py + models.py)
- **Analytics modules**: ≥90% (✅ Achieved: 91% average)
- **Optimization core**: ≥70% (⚠️ Current: 54%, needs improvement)

### Framework Standards

- **New code**: Aim for ≥90% coverage
- **Critical modules**: Require ≥90% coverage
- **Legacy modules**: No specific target (focus on new development)

---

## CI/CD Integration

### Recommended CI Pipeline

```yaml
# .github/workflows/tests.yml
name: Tests and Coverage

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest coverage hypothesis

      - name: Run tests with coverage
        run: |
          coverage run -m pytest tests/
          coverage report --include="rustybt/*"
          coverage html --include="rustybt/*"

      - name: Upload coverage report
        uses: actions/upload-artifact@v3
        with:
          name: coverage-report
          path: htmlcov/
```

---

## Writing New Tests

### Test Template

```python
"""Tests for new_module.py"""

import pytest
from decimal import Decimal
from hypothesis import given, strategies as st

from rustybt.module import NewClass


class TestNewClass:
    """Unit tests for NewClass."""

    def test_basic_functionality(self):
        """Test basic operation."""
        obj = NewClass(param=Decimal("10.5"))
        result = obj.calculate()
        assert result == Decimal("21.0")

    def test_error_handling(self):
        """Test error conditions."""
        with pytest.raises(ValueError, match="Invalid param"):
            NewClass(param=Decimal("-1"))

    @given(value=st.decimals(min_value=Decimal("0"), max_value=Decimal("1000")))
    def test_property_invariant(self, value):
        """Test property holds for all valid inputs."""
        obj = NewClass(param=value)
        result = obj.calculate()
        assert result >= Decimal("0")  # Result always non-negative
```

### Constitutional Compliance

All tests must follow these principles:

1. **CR-001: Decimal Financial Computing**
   - Use `Decimal` for all financial values
   - Never use `float` for money

2. **CR-002: Zero-Mock Enforcement**
   - No mocks in production code tests
   - Use real functions and real data
   - Test actual behavior, not mocked behavior

3. **CR-004: Type Safety Excellence**
   - 100% type hints in test functions
   - Use frozen dataclasses where applicable

4. **CR-005: Test-Driven Development**
   - Property-based tests for invariants
   - Comprehensive edge case coverage

---

## Debugging Failed Tests

### Common Issues

1. **Import Errors**: Ensure all dependencies installed
   ```bash
   pip install -e .
   ```

2. **scipy/numpy Errors**: Use `coverage run` instead of `pytest --cov`

3. **Decimal Precision**: Set precision explicitly
   ```python
   from decimal import getcontext
   getcontext().prec = 28
   ```

### Verbose Output

```bash
# Show full error traces
pytest tests/module/ -vv --tb=long

# Show captured output
pytest tests/module/ -vs

# Stop at first failure
pytest tests/module/ -x
```

---

## Performance Testing

### Benchmark Tests

```bash
# Run performance benchmarks
pytest tests/benchmarks/ --benchmark-only

# Compare against baseline
pytest tests/benchmarks/ --benchmark-compare
```

### Regression Detection

```bash
# Run regression tests
pytest tests/regression/ -v

# Generate regression report
pytest tests/regression/ --regression-report=report.json
```

---

## Test Results Summary

### Latest Full Test Run (2025-10-24)

- **Total Tests**: 1,744
- ✅ **Passed**: 1,618 (92.8%)
- ❌ **Failed**: 81 (4.6%) - mostly legacy Zipline tests
- ⏭️ **Skipped**: 45 (2.6%) - Rust tests (removed in X4)
- **Execution Time**: 19 minutes 55 seconds

**Coverage**: 47% overall (16,615 / 35,304 statements)

---

## Resources

### Documentation
- [Testing Standards](../internal/architecture/coding-standards.md#testing-standards)
- [Zero-Mock Enforcement](../internal/architecture/zero-mock-enforcement.md)
- [X4.8 Coverage Report](../internal/qa/X4.8-TEST-COVERAGE-ENHANCEMENT.md)

### Tools
- [pytest Documentation](https://docs.pytest.org/)
- [coverage.py Documentation](https://coverage.readthedocs.io/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)

---

## Getting Help

- **Test Failures**: Check test output and error messages
- **Coverage Issues**: Use `coverage report -m` to see missing lines
- **scipy/numpy Issues**: Use `coverage run` instead of `pytest --cov`
- **CI/CD Integration**: Refer to CI/CD Integration section above

---

**Document Version**: 1.0
**Last Verified**: 2025-10-24
**Maintainer**: RustyBT Development Team
