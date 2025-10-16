# Property-Based Testing Guide

## Overview

RustyBT uses property-based testing with Hypothesis to validate Decimal implementations across wide input ranges. Property-based tests automatically generate hundreds or thousands of test cases, catching edge cases that traditional unit tests might miss.

## Why Property-Based Testing?

Traditional unit tests check specific examples:
```python
def test_portfolio_value():
    assert calculate_portfolio_value([100, 200], 500) == 800
```

Property-based tests check universal properties:
```python
@given(cash=st.decimals(...), positions=st.lists(...))
def test_portfolio_value_invariant(cash, positions):
    # This must hold for ALL possible inputs
    assert portfolio_value == sum(position_values) + cash
```

## Hypothesis Profiles

RustyBT configures three Hypothesis profiles in `pyproject.toml`:

### Default Profile
- **Examples**: 1000 per test
- **Use**: Standard development and comprehensive testing
- **Activate**: `pytest -m property` (default)

### Quick Profile
- **Examples**: 100 per test
- **Use**: Fast feedback during development
- **Activate**: `pytest -m property --hypothesis-profile=quick`

### CI Profile (GitHub Actions)
- **Examples**: 1000 per test
- **Derandomize**: true (reproducible results)
- **Use**: Automated CI/CD pipeline
- **Activate**: `pytest -m property --hypothesis-profile=ci`

**Configuration** (`pyproject.toml`):
```toml
[tool.hypothesis]
database_file = ".hypothesis/examples.db"

[tool.hypothesis.profiles]
default = { max_examples = 1000 }
ci = { max_examples = 1000, derandomize = true }
quick = { max_examples = 100 }
```

## Running Property Tests

### Run all property tests (default - 1000 examples):
```bash
pytest -m property
```

### Run with quick profile (100 examples):
```bash
pytest -m property --hypothesis-profile=quick
```

### Run with CI profile (deterministic):
```bash
pytest -m property --hypothesis-profile=ci
```

### Run specific test file:
```bash
pytest tests/finance/test_decimal_properties.py -m property
```

### Run with Hypothesis statistics:
```bash
pytest -m property --hypothesis-show-statistics
```

### Run with coverage:
```bash
pytest -m property --cov=rustybt --cov-report=term
```

## Example Implementation

For a complete example of property-based testing for Decimal arithmetic, see:
- **`tests/finance/test_decimal_properties.py`** - 19 comprehensive property tests covering:
  - Commutativity (addition, multiplication)
  - Associativity (addition, multiplication)
  - Identity (additive, multiplicative)
  - Precision (Decimal vs float)
  - Division by zero handling
  - Distributivity
  - Inverse operations
  - Edge cases (very small, very large, negative numbers)

## Custom Strategies

Example strategies for financial data:

### Decimal Prices
```python
from tests.property_tests.strategies import decimal_prices

@given(price=decimal_prices(scale=8))  # 8 decimals for crypto
def test_crypto_price(price):
    assert price > Decimal("0")
```

### Decimal Quantities
```python
from tests.property_tests.strategies import decimal_quantities

@given(quantity=decimal_quantities(scale=2))
def test_quantity(quantity):
    assert quantity > Decimal("0")
```

### OHLCV Bars
```python
from tests.property_tests.strategies import ohlcv_bars

@given(bars=ohlcv_bars(num_bars=100, scale=8))
def test_ohlcv_data(bars):
    # bars is a Polars DataFrame with valid OHLCV relationships
    assert (bars["high"] >= bars["low"]).all()
```

### Return Series
```python
from tests.property_tests.strategies import return_series

@given(returns=return_series(min_size=30, max_size=252))
def test_returns(returns):
    # returns is a list of Decimal returns
    assert len(returns) >= 30
```

## Writing Property Tests

### 1. Test Accounting Identities

```python
@given(
    starting_cash=decimal_prices(...),
    positions=decimal_portfolio_positions(...)
)
def test_portfolio_value_accounting_identity(starting_cash, positions):
    """Portfolio value must equal sum of positions plus cash."""
    ledger = DecimalLedger(starting_cash=starting_cash)

    total_position_value = Decimal("0")
    for amount, price in positions:
        # ... add positions
        total_position_value += amount * price

    expected = total_position_value + starting_cash
    actual = ledger.portfolio_value

    assert actual == expected
```

### 2. Test Calculation Reversibility

```python
@given(
    start_value=decimal_prices(...),
    end_value=decimal_prices(...)
)
def test_returns_reconstruction(start_value, end_value):
    """Returns calculation must be reversible."""
    assume(start_value > Decimal("0"))

    returns = (end_value / start_value) - Decimal("1")
    reconstructed_end = (Decimal("1") + returns) * start_value

    assert reconstructed_end == end_value
```

### 3. Test Bounds and Constraints

```python
@given(
    returns=return_series(...)
)
def test_max_drawdown_range(returns):
    """Max drawdown must be in [-1, 0] range."""
    max_dd = calculate_max_drawdown(returns)

    assert max_dd <= Decimal("0")  # Non-positive
    assert max_dd >= Decimal("-1")  # Can't lose more than 100%
```

### 4. Test Mathematical Properties

```python
@given(
    a=decimal_prices(...),
    b=decimal_prices(...),
    c=decimal_prices(...)
)
def test_decimal_associativity(a, b, c):
    """Addition must be associative."""
    left = (a + b) + c
    right = a + (b + c)

    assert left == right
```

## Hypothesis Shrinking

When a property test fails, Hypothesis automatically "shrinks" the failing example to find the minimal case:

```
Falsifying example:
test_portfolio_value_accounting_identity(
    starting_cash=Decimal("0"),
    positions=[(Decimal("1"), Decimal("1"))]
)
```

This helps identify the root cause quickly.

### Using @example() for Edge Cases

Add explicit edge cases to ensure they're always tested:

```python
@given(
    value=decimal_prices(...)
)
@example(value=Decimal("0"))  # Zero edge case
@example(value=Decimal("0.00000001"))  # Minimum precision
@example(value=Decimal("1000000"))  # Large value
def test_something(value):
    ...
```

## Hypothesis Database

Hypothesis maintains a database of failing examples in `tests/.hypothesis/`:

- **Purpose**: Regression testing - previously failing examples are retested
- **Location**: `tests/.hypothesis/examples/`
- **Git**: This directory is git-ignored (contains test artifacts)

The database ensures that once a bug is found, it's automatically retested in future runs.

## Best Practices

### 1. Use assume() for Preconditions

```python
@given(
    a=decimal_prices(...),
    b=decimal_prices(...)
)
def test_division(a, b):
    assume(b > Decimal("0"))  # Avoid division by zero
    result = a / b
    assert result * b == a
```

### 2. Test Real Implementations (Zero-Mock)

```python
# ❌ BAD: Testing mock
@given(value=st.decimals())
def test_mock(value):
    mock_ledger = Mock()
    mock_ledger.value = value
    assert mock_ledger.value == value  # Trivial

# ✅ GOOD: Testing real implementation
@given(cash=st.decimals(...))
def test_real_ledger(cash):
    ledger = DecimalLedger(starting_cash=cash)
    assert ledger.cash == cash
```

### 3. Verify Exact Equality for Decimals

```python
# ✅ GOOD: Exact Decimal equality
assert calculated == expected

# ❌ BAD: Using epsilon tolerance (defeats Decimal precision)
assert abs(calculated - expected) < Decimal("0.0001")
```

### 4. Use Descriptive Assertion Messages

```python
assert actual == expected, (
    f"Portfolio value accounting identity violated: "
    f"{actual} != {expected} "
    f"(positions: {total_position_value}, cash: {starting_cash})"
)
```

## Common Patterns

### Portfolio Value Invariant
```python
@given(cash=..., positions=...)
def test_portfolio_value_invariant(cash, positions):
    # portfolio_value = sum(position_values) + cash
    ...
```

### Returns Reconstruction
```python
@given(start_value=..., end_value=...)
def test_returns_reconstruction(start_value, end_value):
    # (1 + return) × start_value = end_value
    ...
```

### Commission Bounds
```python
@given(order_value=..., commission_rate=...)
def test_commission_bounds(order_value, commission_rate):
    # 0 <= commission <= order_value
    ...
```

### Drawdown Range
```python
@given(returns=...)
def test_max_drawdown_range(returns):
    # -1 <= max_drawdown <= 0
    ...
```

### Arithmetic Properties
```python
@given(a=..., b=..., c=...)
def test_associativity(a, b, c):
    # (a + b) + c = a + (b + c)
    ...
```

## Debugging Failing Tests

### 1. Run with verbose output:
```bash
pytest tests/property_tests/test_ledger_properties.py::test_portfolio_value_accounting_identity -v
```

### 2. Use debug profile for detailed output:
```bash
HYPOTHESIS_PROFILE=debug pytest tests/property_tests/test_ledger_properties.py::test_portfolio_value_accounting_identity -v
```

### 3. Add print statements inside the test:
```python
@given(...)
def test_something(value):
    print(f"Testing with value: {value}")
    result = calculate(value)
    print(f"Result: {result}")
    assert ...
```

### 4. Reproduce the exact failing example:
```python
@example(cash=Decimal("1234.56"), positions=[(Decimal("10"), Decimal("50"))])
def test_portfolio_value_accounting_identity(cash, positions):
    ...
```

## Coverage Goals

- **All critical invariants**: Portfolio value, returns, drawdown, etc.
- **All arithmetic properties**: Associativity, commutativity, distributivity
- **All bounds**: Commission, drawdown, win rate, etc.
- **1000+ examples per test** (thorough profile)
- **Integration with CI/CD**: Automated regression testing

## Advanced Features

### Performance Benchmarks

Property tests can be combined with performance benchmarks to ensure tests complete within acceptable time bounds:

```python
@pytest.mark.benchmark
@given(positions=decimal_portfolio_positions(min_positions=0, max_positions=20))
def test_portfolio_value_calculation_performance(positions, benchmark):
    """Ensure portfolio value calculation completes within 1ms."""
    def setup():
        ledger = DecimalLedger(starting_cash=Decimal("100000"))
        for i, (amount, price) in enumerate(positions):
            asset = Equity(sid=i, symbol=f"STOCK{i}")
            ledger.positions[asset] = DecimalPosition(...)
        return (ledger,), {}

    def calculate_value(ledger):
        return ledger.portfolio_value

    result = benchmark.pedantic(calculate_value, setup=setup, rounds=100)
    assert result >= Decimal("0")
```

Run benchmarks:
```bash
pytest tests/property_tests/test_performance_benchmarks.py --benchmark-only
```

### Regression Tests from Shrunk Examples

When Hypothesis finds a failing example, it automatically shrinks it to the minimal case. Capture these as regression tests:

```python
# Example discovered by Hypothesis shrinking
@pytest.mark.regression
def test_regression_empty_portfolio_value():
    """Regression: Portfolio value with zero positions should equal cash.

    Discovered by Hypothesis shrinking from test_portfolio_value_accounting_identity.
    Minimal example: starting_cash=Decimal("0"), positions=[]
    """
    ledger = DecimalLedger(starting_cash=Decimal("0"))
    assert ledger.portfolio_value == Decimal("0")
```

See `tests/property_tests/test_regression_examples.py` for the complete regression test suite.

### Property Test Coverage Metrics

RustyBT enforces property test coverage quality gates via `scripts/property_test_coverage.py`:

```bash
# Check coverage
python scripts/property_test_coverage.py --check

# Generate detailed report
python scripts/property_test_coverage.py --report

# Enforce quality gates (CI/CD)
python scripts/property_test_coverage.py --enforce-gates
```

**Quality Gates:**
1. All critical modules have >= minimum property tests
2. Total property tests >= 30
3. Regression tests >= 5
4. Coverage >= 90%

**Critical Modules Requiring Property Tests:**
- `rustybt.finance.decimal.ledger` (minimum 3 tests)
- `rustybt.finance.decimal.position` (minimum 2 tests)
- `rustybt.finance.decimal.transaction` (minimum 2 tests)
- `rustybt.finance.metrics.core` (minimum 3 tests)
- `rustybt.data.polars.data_portal` (minimum 2 tests)
- And more...

Coverage metrics are automatically enforced in CI/CD pipeline.

## Further Reading

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing Patterns](https://hypothesis.works/articles/what-is-property-based-testing/)
- [Hypothesis Best Practices](https://hypothesis.readthedocs.io/en/latest/strategies.html)
- [pytest-benchmark Documentation](https://pytest-benchmark.readthedocs.io/)
