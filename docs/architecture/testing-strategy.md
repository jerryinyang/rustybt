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
