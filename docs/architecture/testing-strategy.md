# Testing Strategy

## Test Coverage Targets

**Overall Coverage:** ≥90% (maintain/improve from Zipline's 88.26%)
**Financial Modules:** ≥95% (critical for correctness)
**New Components:** ≥90% (strict enforcement)

## Test Pyramid

**Unit Tests (70%):**
- Fast, isolated tests for individual functions/classes
- Mock external dependencies (broker APIs, data sources)
- Run on every commit (~5 seconds total)

**Integration Tests (25%):**
- Test component interactions (e.g., LiveTradingEngine + BrokerAdapter)
- Use paper trading accounts for broker integration tests
- Run on pull requests (~2 minutes total)

**End-to-End Tests (5%):**
- Complete workflows (backtest, optimization, live trading)
- Use realistic data and scenarios
- Run nightly (~10 minutes total)

## Property-Based Testing (Hypothesis)

**Purpose:** Validate Decimal arithmetic invariants and financial calculation correctness

**Key Properties:**

**Portfolio Value Invariant:**
```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    cash=st.decimals(min_value=Decimal("0"), max_value=Decimal("10000000")),
    positions=st.lists(
        st.tuples(
            st.decimals(min_value=Decimal("0"), max_value=Decimal("1000")),  # amount
            st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"))   # price
        ),
        max_size=10
    )
)
def test_portfolio_value_equals_cash_plus_positions(cash, positions):
    ledger = DecimalLedger(starting_cash=cash)

    positions_value = Decimal(0)
    for amount, price in positions:
        positions_value += amount * price

    expected_value = cash + positions_value
    assert ledger.portfolio_value == expected_value
```

**Commission Never Exceeds Order Value:**
```python
@given(
    order_value=st.decimals(min_value=Decimal("1"), max_value=Decimal("100000")),
    commission_rate=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.1"))
)
def test_commission_bounded(order_value, commission_rate):
    commission = calculate_commission(order_value, commission_rate)
    assert Decimal(0) <= commission <= order_value
```

**Decimal Precision Preservation:**
```python
@given(
    values=st.lists(
        st.decimals(min_value=Decimal("-1000"), max_value=Decimal("1000")),
        min_size=2, max_size=100
    )
)
def test_decimal_sum_associativity(values):
    """Sum order should not affect result due to Decimal precision."""
    sum_forward = sum(values, Decimal(0))
    sum_reverse = sum(reversed(values), Decimal(0))
    assert sum_forward == sum_reverse
```

**1000+ Examples:** Each property test runs with ≥1000 random examples to ensure robustness.

## Regression Testing

**Performance Benchmarks:**
- Track execution time for standard backtest scenarios
- Fail CI if performance degrades >10%
- Benchmark suite run on every release

**Benchmark Scenarios:**
```python
import pytest

@pytest.mark.benchmark(group="backtest")
def test_daily_backtest_performance(benchmark):
    """Benchmark 2-year daily backtest with 50 assets."""
    def run_backtest():
        result = run_algorithm(
            start='2021-01-01',
            end='2022-12-31',
            data_frequency='daily',
            bundle='quandl',
            capital_base=100000
        )
        return result

    result = benchmark(run_backtest)
    assert result.portfolio_value[-1] > 0  # Sanity check
```

**Stored Results:**
- Store benchmark results in CI artifacts
- Track performance trends over time
- Alert on significant regressions

## Temporal Isolation Tests

**Lookahead Bias Detection:**
- Verify no strategy has access to future data
- Timestamp validation at data access layer
- Tests for common mistakes (e.g., `.shift(-1)` on price data)

**Example Test:**
```python
def test_no_future_data_access():
    """Verify data.current() never returns future data."""

    class FutureDataAttempt(TradingAlgorithm):
        def handle_data(self, context, data):
            current_time = self.get_datetime()
            current_price = data.current(context.asset, 'close')

            # Attempt to access future data (should fail)
            with pytest.raises(DataNotAvailableError):
                future_price = data.current(
                    context.asset, 'close',
                    dt=current_time + pd.Timedelta(days=1)
                )

    run_algorithm(
        algorithm=FutureDataAttempt(),
        start='2023-01-01',
        end='2023-12-31'
    )
```

## Shadow Trading Validation Tests

**Purpose:** Validate backtest-live alignment framework catches divergence

**Shadow Engine Tests:**
- Unit test: ShadowBacktestEngine processes market events correctly
- Unit test: Shadow engine maintains separate state from live engine
- Integration test: Shadow engine consumes same data feed as live engine
- Integration test: Shadow engine failure doesn't halt live trading

**Signal Alignment Tests:**
- Unit test: SignalAlignmentValidator matches identical signals (100% match rate)
- Unit test: Validator classifies EXACT_MATCH, DIRECTION_MATCH, MAGNITUDE_MISMATCH correctly
- Unit test: Validator detects MISSING_SIGNAL when signal only in one engine
- Integration test: Simulated data delay (200ms) → signals flagged as divergent
- Property test: If inputs identical, signal_match_rate = 1.0

**Execution Quality Tests:**
- Unit test: ExecutionQualityTracker calculates slippage_error_bps correctly
- Unit test: Tracker calculates fill_rate_error_pct correctly
- Unit test: Rolling metrics calculation over 100 fills
- Integration test: Simulated slippage increase → quality degradation detected
- Property test: If expected = actual, all error metrics = 0

**Alignment Circuit Breaker Tests:**
- Unit test: Circuit breaker trips when signal_match_rate < 0.95
- Unit test: Circuit breaker trips when slippage_error > 50bps
- Unit test: Circuit breaker trips when fill_rate_error > 20%
- Unit test: Manual reset required (auto-reset fails)
- Integration test: Alignment degradation → circuit breaker halts trading
- Integration test: Circuit breaker trip emits critical alert

**End-to-End Shadow Trading Tests:**
```python
def test_shadow_trading_perfect_alignment():
    """Test shadow mode with perfect backtest-live alignment."""

    # Setup
    strategy = MomentumStrategy()
    paper_broker = PaperBroker(use_realistic_fills=True)

    engine = LiveTradingEngine(
        strategy=strategy,
        broker=paper_broker,
        shadow_mode=True,
        shadow_config=ShadowTradingConfig(
            signal_match_rate_min=Decimal("0.99"),
            slippage_error_bps_max=Decimal("10")
        )
    )

    # Run for 1 hour of simulated trading
    asyncio.run(engine.run(duration_hours=1))

    # Verify alignment
    alignment_metrics = engine.state_manager.get_alignment_metrics()
    assert alignment_metrics['signal_match_rate'] >= Decimal("0.99")
    assert abs(alignment_metrics['slippage_error_bps']) <= Decimal("10")
    assert not engine.circuit_breakers['alignment'].is_tripped

def test_shadow_trading_detects_divergence():
    """Test shadow mode detects backtest-live divergence."""

    # Setup with intentional divergence
    strategy = MomentumStrategy()
    paper_broker = PaperBroker(use_realistic_fills=True)

    # Inject slippage increase in live fills
    paper_broker.slippage_multiplier = 5.0  # 5x worse than backtest

    engine = LiveTradingEngine(
        strategy=strategy,
        broker=paper_broker,
        shadow_mode=True,
        shadow_config=ShadowTradingConfig(
            signal_match_rate_min=Decimal("0.95"),
            slippage_error_bps_max=Decimal("50")
        )
    )

    # Run until circuit breaker trips
    with pytest.raises(CircuitBreakerTrippedError) as exc_info:
        asyncio.run(engine.run(duration_hours=1))

    # Verify correct trip reason
    assert exc_info.value.reason == CircuitBreakerReason.EXECUTION_QUALITY_DEGRADED
    assert engine.circuit_breakers['alignment'].is_tripped
```

**Performance Tests:**
- Test: Shadow mode overhead <5% latency increase
- Test: Shadow engine handles 1000+ events/second
- Test: Alignment validation completes in <1ms per signal
- Test: Memory usage bounded (shadow history buffer doesn't grow unbounded)

## Continuous Integration

**CI Pipeline (GitHub Actions):**

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.12', '3.13']

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest -v --cov=rustybt --cov-report=xml --cov-report=term

      - name: Type check
        run: |
          mypy --strict rustybt

      - name: Lint
        run: |
          ruff check rustybt

      - name: Format check
        run: |
          black --check rustybt

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

**Coverage Enforcement:**
- Fail PR if coverage drops below 90%
- Require 95%+ coverage for financial modules
- Coverage reports uploaded to Codecov

**Pre-commit Hooks:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.0
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.11.12
    hooks:
      - id: ruff

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## Test Data Management

**Fixtures:**
- Stored in `tests/resources/`
- Small datasets only (<10MB)
- Use synthetic data where possible

**Live Data Integration Tests:**
- Require explicit opt-in: `pytest --run-live`
- Use testnet/paper accounts only
- Rate-limited to avoid API abuse

**Mocking:**
- Mock broker APIs using `pytest-mock` or `responses`
- Mock expensive operations (data downloads)
- Example:
  ```python
  def test_broker_order_submission(mocker):
      mock_broker = mocker.Mock(spec=BrokerAdapter)
      mock_broker.submit_order.return_value = "order-123"

      engine = LiveTradingEngine(broker=mock_broker)
      order_id = engine.submit_order(...)

      assert order_id == "order-123"
      mock_broker.submit_order.assert_called_once()
  ```

---
