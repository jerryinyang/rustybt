# Testing Utilities

**Module**: `rustybt.testing`
**Purpose**: Comprehensive testing utilities for strategy development and validation
**Status**: Production-ready

---

## Overview

RustyBT provides extensive testing utilities to help develop, validate, and maintain trading strategies with high confidence. These utilities cover unit testing, integration testing, property-based testing, and strategy validation.

**Testing Philosophy**: Strategies involve capital at risk. Comprehensive testing is mandatory, not optional.

---

## Quick Start

### Basic Strategy Test

```python
import pytest
from decimal import Decimal
from rustybt.algorithm import TradingAlgorithm
from rustybt.utils.run_algo import run_algorithm
from rustybt.testing import ZiplineTestCase
from rustybt.testing import create_data_portal, tmp_asset_finder
import pandas as pd

class MyStrategy(TradingAlgorithm):
    def initialize(self):
        self.asset = self.symbol('AAPL')

    def handle_data(self, context, data):
        self.order_target_percent(self.asset, 0.95)

class TestMyStrategy(ZiplineTestCase):
    def test_strategy_execution(self):
        """Test strategy executes without errors."""
        results = run_algorithm(
            strategy_class=MyStrategy,
            start='2020-01-01',
            end='2020-12-31',
            capital_base=100000,
            data_frequency='daily'
        )

        # Verify results
        assert results['portfolio_value'].iloc[-1] > Decimal("0")
        assert len(results['transactions']) > 0

    def test_strategy_performance(self):
        """Test strategy achieves positive returns."""
        results = run_algorithm(
            strategy_class=MyStrategy,
            start='2020-01-01',
            end='2020-12-31',
            capital_base=100000
        )

        final_value = results['portfolio_value'].iloc[-1]
        initial_value = results['portfolio_value'].iloc[0]
        total_return = (final_value - initial_value) / initial_value

        assert total_return > Decimal("0"), "Strategy should have positive returns"
```

---

## Core Testing Classes

### ZiplineTestCase

**Module**: `rustybt.testing.fixtures`

Base test class with automatic resource management and cleanup.

**Features**:
- Automatic setup/teardown via `ExitStack`
- Per-test and per-class fixture support
- Temporary directory management
- Asset finder creation
- Data portal setup

**Usage**:
```python
from rustybt.testing import ZiplineTestCase

class TestMyStrategy(ZiplineTestCase):
    @classmethod
    def init_class_fixtures(cls):
        """Set up fixtures shared across all tests in class."""
        super().init_class_fixtures()  # ALWAYS call super()

        # Create trading calendar
        cls.trading_calendar = cls.enter_class_context(
            get_calendar('NYSE')
        )

        # Create asset finder
        cls.asset_finder = cls.enter_class_context(
            tmp_asset_finder(num_assets=10)
        )

    def init_instance_fixtures(self):
        """Set up fixtures for each test method."""
        super().init_instance_fixtures()  # ALWAYS call super()

        # Create temporary directory
        self.temp_dir = self.enter_instance_context(
            tmp_dir()
        )

        # Create data portal
        self.data_portal = create_data_portal(
            asset_finder=self.asset_finder,
            trading_calendar=self.trading_calendar
        )

    def test_something(self):
        # Use self.asset_finder, self.data_portal, etc.
        ...
```

**Important Methods**:
```python
# Register context managers (auto-cleanup)
self.enter_instance_context(context_manager)
self.enter_class_context(context_manager)

# Register cleanup callbacks
self.add_instance_callback(callback_func)
self.add_class_callback(callback_func)
```

---

## Test Fixtures

### Asset Creation

**Create Asset Finder**:
```python
from rustybt.testing import tmp_asset_finder

# Create asset finder for testing
asset_finder = tmp_asset_finder()
```

**Create Data Portal**:
```python
from rustybt.testing import create_data_portal

data_portal = create_data_portal(
    asset_finder=asset_finder,
    trading_calendar=trading_calendar,
    start_date='2020-01-01',
    end_date='2023-12-31',
    data_frequency='daily'
)
```

---

## Strategy Testing Patterns

### Pattern 1: Basic Execution Test

```python
def test_strategy_executes(self):
    """Verify strategy runs to completion without errors."""
    results = run_algorithm(
        strategy_class=MyStrategy,
        start='2020-01-01',
        end='2020-12-31',
        capital_base=100000
    )

    # Basic assertions
    assert results is not None
    assert 'portfolio_value' in results
    assert len(results) > 0
    assert results['portfolio_value'].iloc[-1] > Decimal("0")
```

### Pattern 2: Performance Test

```python
from rustybt.analytics.risk import RiskAnalytics

def test_strategy_performance(self):
    """Verify strategy achieves positive risk-adjusted returns."""
    results = run_algorithm(
        strategy_class=MyStrategy,
        start='2020-01-01',
        end='2023-12-31',
        capital_base=100000
    )

    # Calculate risk metrics
    risk = RiskAnalytics(results)

    # Assertions
    assert risk.total_return > Decimal("0"), "Positive returns required"
    assert risk.sharpe_ratio > Decimal("1.0"), "Sharpe ratio >= 1.0 required"
    assert risk.max_drawdown < Decimal("0.20"), "Max drawdown < 20% required"
```

### Pattern 3: Parametric Test

```python
import pytest

@pytest.mark.parametrize("lookback_period", [10, 20, 50, 100])
@pytest.mark.parametrize("rebalance_frequency", ['daily', 'weekly', 'monthly'])
def test_parameter_combinations(self, lookback_period, rebalance_frequency):
    """Test strategy across parameter space."""
    class ParametricStrategy(TradingAlgorithm):
        def initialize(self):
            self.lookback_period = lookback_period
            self.rebalance_frequency = rebalance_frequency
            self.asset = self.symbol('AAPL')

        def handle_data(self, context, data):
            # Strategy logic using parameters
            ...

    results = run_algorithm(
        strategy_class=ParametricStrategy,
        start='2020-01-01',
        end='2023-12-31',
        capital_base=100000
    )

    # Verify strategy works for all parameter combinations
    assert results['portfolio_value'].iloc[-1] > Decimal("0")
```

---

## Property-Based Testing

**Module**: `hypothesis` (third-party integration)

Property-based testing generates random test cases to verify strategy invariants.

### Example - Portfolio Value Invariant

```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    starting_cash=st.decimals(min_value=Decimal("10000"), max_value=Decimal("1000000")),
    asset_price=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000")),
    shares=st.integers(min_value=0, max_value=1000)
)
def test_portfolio_value_invariant(self, starting_cash, asset_price, shares):
    """Portfolio value = cash + sum(position values)."""
    # Create simple portfolio
    cash = starting_cash - (asset_price * Decimal(shares))
    position_value = asset_price * Decimal(shares)

    portfolio_value = cash + position_value

    # Invariant: Portfolio value should equal starting cash
    assert portfolio_value == starting_cash
```

---

## Best Practices

### 1. Test Strategy Incrementally

```python
# ✅ GOOD: Test each component separately
def test_initialize(self):
    """Test strategy initialization."""
    strategy = MyStrategy()
    strategy.initialize()
    assert hasattr(strategy, 'asset')

def test_signal_generation(self):
    """Test signal generation logic."""
    ...

def test_full_strategy(self):
    """Test complete strategy."""
    ...
```

### 2. Use Fixtures for Common Setup

```python
import pytest

@pytest.fixture
def strategy():
    """Create strategy instance."""
    return MyStrategy()

@pytest.fixture
def test_data():
    """Create test data."""
    return create_data_portal(...)

def test_with_fixtures(self, strategy, test_data):
    # Use strategy and test_data
    ...
```

### 3. Test Edge Cases

```python
def test_zero_volume_handling(self):
    """Test handling of zero-volume bars."""
    ...

def test_missing_data_handling(self):
    """Test handling of missing price data."""
    ...

def test_extreme_volatility_handling(self):
    """Test handling of extreme volatility."""
    ...
```

---

## Summary

**Testing Checklist**:
- [ ] Unit tests for each strategy component
- [ ] Integration tests for complete workflow
- [ ] Property-based tests for invariants
- [ ] Performance benchmarks
- [ ] Edge case tests (flash crashes, missing data, etc.)
- [ ] Parametric tests across parameter ranges
- [ ] CI/CD integration

**Remember**: Comprehensive testing is mandatory for strategies involving real capital. Test early, test often, test thoroughly.

---

## Related Documentation

- [Data Management](../data-management/README.md) - Test data creation
- [Order Management](../order-management/README.md) - Order testing
- [Analytics](../analytics/README.md) - Performance validation
- [Live Trading](../live-trading/README.md) - Live trading validation

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

- **Property-Based Testing** - Testing with Hypothesis (see below)
- **Test Data Generation** - Creating realistic test data (see project tests/)
- **Strategy Testing Patterns** - Common testing patterns (see project tests/)
- **Backtesting Validation** - Validating backtest correctness (see project tests/)
- **Mock Environments** - Paper brokers and data feeds (see project tests/)

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

- Property-Based Testing Guide - See Hypothesis documentation
- Strategy Testing Guide - See project tests/ directory
- Zero-Mock Enforcement - See project architecture documentation
- Coding Standards - See project architecture documentation

## Examples

See `tests/` directory for complete examples:

- `tests/test_portfolio.py` - Portfolio testing examples
- `tests/test_strategies.py` - Strategy testing patterns
- `tests/property_tests/` - Property-based testing examples
- `tests/integration/` - Integration testing examples
