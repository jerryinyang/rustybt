# Testing Framework

Comprehensive testing utilities and best practices for RustyBT strategies and systems.

## Overview

RustyBT provides a robust testing framework including unit testing utilities, property-based testing with Hypothesis, strategy testing patterns, backtesting validation, and mock trading environments.

### Key Features

- **Property-Based Testing**: Hypothesis integration for testing financial invariants
- **Test Data Generation**: Realistic OHLCV data generation for testing
- **Strategy Testing Patterns**: Reusable patterns for testing trading strategies
- **Backtesting Validation**: Ensure backtest correctness and consistency
- **Mock Environments**: Simulated brokers and data feeds for testing
- **Zero-Mock Enforcement**: Tools to prevent mock code in production

## Quick Navigation

### Core Testing

- **[Property-Based Testing](#property-based-testing)** - Testing with Hypothesis
- **[Test Data Generation](#test-data-generation)** - Creating realistic test data
- **[Strategy Testing Patterns](#strategy-testing-patterns)** - Common testing patterns
- **[Backtesting Validation](#backtesting-validation)** - Validating backtest correctness
- **[Mock Environments](#mock-environments)** - Paper brokers and data feeds

## Property-Based Testing

### Overview

Property-based testing with Hypothesis generates thousands of test cases automatically, finding edge cases that manual testing misses.

See the [Hypothesis documentation](https://hypothesis.readthedocs.io/) for comprehensive examples and usage patterns.

## Best Practices

### 1. Test at Multiple Levels

```python
# Unit tests: Individual components
def test_order_creation():
    order = Order(...)
    assert order.is_valid()

# Integration tests: Components working together
def test_order_execution():
    broker = PaperBroker()
    order_id = broker.submit_order(...)
    assert broker.get_order(order_id).status == 'filled'

# End-to-end tests: Complete workflow
def test_full_strategy():
    result = run_backtest(strategy, ...)
    assert result.sharpe_ratio > 1.0
```

### 2. Use Property-Based Testing for Invariants

```python
@given(...)
def test_portfolio_invariant(...):
    # Test fundamental properties that must always hold
    assert portfolio.value == cash + positions_value
```

### 3. Test Edge Cases

```python
def test_zero_cash():
    portfolio = Portfolio(starting_cash=Decimal("0"))
    # Should handle gracefully

def test_negative_prices():
    with pytest.raises(ValueError):
        bar = Bar(open=-100, ...)

def test_missing_data():
    # Strategy should handle missing data without crashing
    pass
```

### 4. Validate Against Known Results

```python
def test_moving_average_calculation():
    """Test MA matches known result."""
    prices = [10, 20, 30, 40, 50]
    ma = calculate_ma(prices, window=3)

    # Known result for last 3: (30 + 40 + 50) / 3 = 40
    assert ma[-1] == 40
```

## See Also

- [Property-Based Testing Guide](property-testing.md)
- [Strategy Testing Guide](strategy-testing.md)
- [Zero-Mock Enforcement](../../architecture/zero-mock-enforcement.md)
- [Coding Standards](../../architecture/coding-standards.md)

## Examples

See `tests/` directory for complete examples:

- `tests/test_portfolio.py` - Portfolio testing examples
- `tests/test_strategies.py` - Strategy testing patterns
- `tests/property_tests/` - Property-based testing examples
- `tests/integration/` - Integration testing examples
