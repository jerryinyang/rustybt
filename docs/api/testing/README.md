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

### Basic Example

```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000")),
    quantity=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"))
)
def test_order_value_calculation(price, quantity):
    """Order value should equal price * quantity."""
    order = Order(price=price, quantity=quantity)
    expected = price * quantity
    assert order.value == expected
```

### Financial Invariants

#### Portfolio Value Conservation

```python
from hypothesis import given, strategies as st
from rustybt.testing.strategies import ohlcv_dataframe
from decimal import Decimal

@given(
    starting_cash=st.decimals(min_value=Decimal("1000"), max_value=Decimal("100000")),
    data=ohlcv_dataframe(n_bars=100)
)
def test_portfolio_value_conservation(starting_cash, data):
    """
    Portfolio value should equal cash + position values.

    This is a fundamental invariant that must hold at all times.
    """
    portfolio = Portfolio(starting_cash=starting_cash)

    # Execute some trades
    for bar in data.itertuples():
        portfolio.update(bar)

    # Invariant check
    cash = portfolio.cash
    positions_value = sum(pos.market_value for pos in portfolio.positions.values())

    assert portfolio.value == cash + positions_value
```

#### Decimal Precision

```python
@given(
    amounts=st.lists(
        st.decimals(min_value=Decimal("-1000"), max_value=Decimal("1000")),
        min_size=2, max_size=100
    )
)
def test_decimal_summation_precision(amounts):
    """
    Decimal summation should maintain precision.

    Tests that we never lose precision due to floating point errors.
    """
    # Calculate sum using Decimal
    decimal_sum = sum(amounts, Decimal("0"))

    # Should maintain exact precision (no rounding errors)
    for amount in amounts:
        decimal_sum -= amount

    assert decimal_sum == Decimal("0")
```

#### OHLCV Relationships

```python
from hypothesis import given
from rustybt.testing.strategies import valid_ohlcv_bar

@given(bar=valid_ohlcv_bar())
def test_ohlcv_invariants(bar):
    """
    OHLCV data must satisfy fundamental relationships.

    High >= max(Open, Close, Low)
    Low <= min(Open, Close, High)
    Volume >= 0
    """
    assert bar['high'] >= bar['open']
    assert bar['high'] >= bar['close']
    assert bar['high'] >= bar['low']

    assert bar['low'] <= bar['open']
    assert bar['low'] <= bar['close']
    assert bar['low'] <= bar['high']

    assert bar['volume'] >= 0
```

### Custom Strategies

Create custom Hypothesis strategies for domain objects:

```python
from hypothesis import strategies as st
from decimal import Decimal

@st.composite
def asset_strategy(draw):
    """Generate valid Asset objects."""
    symbol = draw(st.text(alphabet=st.characters(whitelist_categories=('Lu',)),
                          min_size=1, max_size=5))
    exchange = draw(st.sampled_from(['NYSE', 'NASDAQ', 'BINANCE']))

    return Asset(symbol=symbol, exchange=exchange)

@st.composite
def order_strategy(draw):
    """Generate valid Order objects."""
    asset = draw(asset_strategy())
    amount = draw(st.decimals(min_value=Decimal("1"), max_value=Decimal("1000")))
    price = draw(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000")))
    order_type = draw(st.sampled_from(['market', 'limit']))

    return Order(asset=asset, amount=amount, price=price, order_type=order_type)

# Usage
@given(order=order_strategy())
def test_order_submission(order):
    broker = PaperBroker()
    order_id = broker.submit_order(order)
    assert order_id is not None
```

## Test Data Generation

### OHLCV Data

Generate realistic OHLCV data:

```python
from rustybt.testing import generate_ohlcv

# Random walk with drift
data = generate_ohlcv(
    n_bars=1000,
    start_price=100.0,
    volatility=0.02,  # 2% daily volatility
    drift=0.0005,     # 0.05% daily drift
    seed=42
)

# Trending data
trending_data = generate_ohlcv(
    n_bars=1000,
    start_price=100.0,
    volatility=0.02,
    drift=0.001,  # Positive drift = uptrend
    seed=42
)

# Mean-reverting data
mean_reverting_data = generate_ohlcv(
    n_bars=1000,
    start_price=100.0,
    volatility=0.02,
    mean_reversion=0.1,  # Mean reversion strength
    seed=42
)
```

### Market Regimes

Generate data with different market regimes:

```python
from rustybt.testing import generate_regime_data

data = generate_regime_data(
    regimes=[
        {'type': 'bull', 'duration': 250, 'drift': 0.001, 'volatility': 0.015},
        {'type': 'bear', 'duration': 100, 'drift': -0.002, 'volatility': 0.030},
        {'type': 'sideways', 'duration': 150, 'drift': 0.0, 'volatility': 0.010},
    ],
    start_price=100.0,
    seed=42
)
```

### Correlated Assets

Generate multiple correlated assets:

```python
from rustybt.testing import generate_correlated_assets

assets_data = generate_correlated_assets(
    n_assets=3,
    n_bars=1000,
    correlation_matrix=[
        [1.0, 0.7, 0.3],
        [0.7, 1.0, 0.5],
        [0.3, 0.5, 1.0]
    ],
    start_prices=[100.0, 50.0, 200.0],
    volatilities=[0.02, 0.03, 0.015],
    seed=42
)
```

## Strategy Testing Patterns

### Unit Testing Strategies

```python
import pytest
from rustybt import TradingAlgorithm
from rustybt.testing import BacktestRunner

class SimpleMAStrategy(TradingAlgorithm):
    def initialize(self):
        self.asset = self.symbol('AAPL')

    def handle_data(self, context, data):
        prices = data.history(self.asset, 'close', 20, '1d')
        ma = prices.mean()
        current = data.current(self.asset, 'close')

        if current > ma:
            self.order(self.asset, 100)

def test_strategy_initialization():
    """Test strategy initializes correctly."""
    strategy = SimpleMAStrategy()
    runner = BacktestRunner(strategy)

    assert strategy.initialized
    assert strategy.asset is not None

def test_strategy_generates_signals():
    """Test strategy generates trading signals."""
    strategy = SimpleMAStrategy()
    runner = BacktestRunner(strategy)

    result = runner.run(start='2023-01-01', end='2023-12-31')

    assert len(result.orders) > 0
    assert result.portfolio_value != result.starting_cash

def test_strategy_handles_no_data():
    """Test strategy handles missing data gracefully."""
    strategy = SimpleMAStrategy()
    runner = BacktestRunner(strategy)

    # Run with insufficient data for MA calculation
    result = runner.run(start='2023-01-01', end='2023-01-05')  # Only 5 days

    # Should not crash, should not trade
    assert len(result.orders) == 0
```

### Integration Testing

```python
def test_full_backtest_workflow():
    """Test complete backtest workflow."""
    # 1. Create strategy
    strategy = SimpleMAStrategy()

    # 2. Load data
    data = load_data('AAPL', '2023-01-01', '2023-12-31')

    # 3. Run backtest
    result = run_backtest(
        strategy=strategy,
        data=data,
        starting_cash=Decimal("100000"),
        commission=PerShareCommission(0.01),
        slippage=FixedSlippage(0.001)
    )

    # 4. Validate results
    assert result.portfolio_value > 0
    assert result.num_trades >= 0
    assert -1.0 <= result.max_drawdown <= 0.0

    # 5. Calculate metrics
    metrics = calculate_metrics(result)
    assert 'sharpe_ratio' in metrics
    assert 'max_drawdown' in metrics
```

### Parameterized Testing

```python
import pytest

@pytest.mark.parametrize("lookback,threshold", [
    (20, 0.02),
    (50, 0.05),
    (100, 0.10),
])
def test_strategy_with_parameters(lookback, threshold):
    """Test strategy with different parameters."""
    strategy = SimpleMAStrategy(lookback=lookback, threshold=threshold)

    result = run_backtest(strategy, start='2023-01-01', end='2023-12-31')

    # Should complete successfully
    assert result is not None
    assert result.sharpe_ratio != 0
```

## Backtesting Validation

### Result Consistency

```python
def test_backtest_determinism():
    """Same inputs should produce same results."""
    strategy = SimpleMAStrategy()

    result1 = run_backtest(strategy, start='2023-01-01', end='2023-12-31', seed=42)
    result2 = run_backtest(strategy, start='2023-01-01', end='2023-12-31', seed=42)

    assert result1.portfolio_value == result2.portfolio_value
    assert result1.sharpe_ratio == result2.sharpe_ratio
    assert len(result1.orders) == len(result2.orders)
```

### No Look-Ahead Bias

```python
def test_no_look_ahead_bias():
    """Ensure strategy cannot access future data."""
    class LookAheadStrategy(TradingAlgorithm):
        def handle_data(self, context, data):
            # Try to access future data
            with pytest.raises(LookaheadError):
                future_price = data.current(self.asset, 'close', offset=1)

    strategy = LookAheadStrategy()
    runner = BacktestRunner(strategy)

    # Should raise error when accessing future data
    with pytest.raises(LookaheadError):
        runner.run()
```

### Performance Bounds

```python
def test_performance_bounds():
    """Performance metrics should be within reasonable bounds."""
    strategy = SimpleMAStrategy()
    result = run_backtest(strategy, start='2023-01-01', end='2023-12-31')

    # Sharpe ratio should be reasonable
    assert -5.0 <= result.sharpe_ratio <= 10.0

    # Max drawdown should be between 0 and -100%
    assert -1.0 <= result.max_drawdown <= 0.0

    # Portfolio value should be positive
    assert result.portfolio_value > 0

    # Number of trades should be reasonable
    assert 0 <= result.num_trades <= 10000
```

## Mock Environments

### Paper Broker

```python
from rustybt.live.brokers import PaperBroker
from decimal import Decimal

def test_with_paper_broker():
    """Test strategy with simulated broker."""
    broker = PaperBroker(
        starting_cash=Decimal("100000"),
        commission_model=None,
        slippage_model=None
    )

    # Submit order
    order_id = broker.submit_order(
        asset=Asset('AAPL'),
        amount=Decimal("100"),
        order_type='market'
    )

    # Check order was created
    assert order_id is not None

    # Check position
    positions = broker.get_positions()
    assert len(positions) == 1
```

### Mock Data Feed

```python
from rustybt.testing import MockDataFeed

def test_with_mock_data():
    """Test strategy with mock data feed."""
    # Create mock data
    data = generate_ohlcv(n_bars=100)

    # Create mock feed
    feed = MockDataFeed(data)

    # Test strategy with mock feed
    strategy = SimpleMAStrategy()
    runner = BacktestRunner(strategy, data_feed=feed)

    result = runner.run()
    assert result is not None
```

## Zero-Mock Enforcement

Prevent mock code in production:

```python
def test_no_mocks_in_production():
    """Ensure no mock objects in production code."""
    from rustybt.testing import detect_mocks

    violations = detect_mocks('rustybt/')

    assert len(violations) == 0, f"Found mocks in production: {violations}"

def test_no_hardcoded_values():
    """Ensure no hardcoded return values."""
    from rustybt.testing import detect_hardcoded_values

    violations = detect_hardcoded_values('rustybt/')

    assert len(violations) == 0, f"Found hardcoded values: {violations}"
```

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
