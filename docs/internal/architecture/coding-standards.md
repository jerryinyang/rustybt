# Coding Standards

## Python Coding Standards

**Language Version:**
- Python 3.12+ required
- Use modern features: structural pattern matching, type hints, asyncio

**Type Hints:**
- 100% type hint coverage for public APIs
- `mypy --strict` compliance enforced in CI/CD
- Use `typing` module for complex types: `List`, `Dict`, `Optional`, `Union`, `Callable`
- Example:
  ```python
  from decimal import Decimal
  from typing import List, Optional

  def calculate_portfolio_value(
      positions: List[DecimalPosition],
      cash: Decimal
  ) -> Decimal:
      """Calculate total portfolio value."""
      positions_value = sum(p.market_value for p in positions, Decimal(0))
      return positions_value + cash
  ```

**Code Formatting:**
- **black** for code formatting (line length: 100)
- **ruff** for linting (replaces flake8, isort, pyupgrade)
- Configuration in `pyproject.toml`:
  ```toml
  [tool.black]
  line-length = 100
  target-version = ['py312']

  [tool.ruff]
  line-length = 100
  target-version = "py312"
  select = ["E", "F", "W", "I", "N", "UP", "ANN", "B", "A", "C4", "DTZ", "T20", "SIM"]
  ```

**Naming Conventions:**
- Classes: `PascalCase` (e.g., `DecimalLedger`, `PolarsDataPortal`)
- Functions/methods: `snake_case` (e.g., `calculate_returns`, `fetch_ohlcv`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_LEVERAGE`, `DEFAULT_PRECISION`)
- Private members: prefix with `_` (e.g., `_internal_state`, `_validate_order`)

**Docstrings:**
- All public classes, functions, methods require docstrings
- Use Google-style docstrings:
  ```python
  def submit_order(
      self,
      asset: Asset,
      amount: Decimal,
      order_type: str,
      limit_price: Optional[Decimal] = None
  ) -> str:
      """Submit order to broker.

      Args:
          asset: Asset to trade
          amount: Order quantity (positive=buy, negative=sell)
          order_type: 'market', 'limit', 'stop', 'stop-limit'
          limit_price: Limit price for limit/stop-limit orders

      Returns:
          Broker order ID as string

      Raises:
          BrokerError: If order submission fails
          ValidationError: If order parameters invalid
      """
  ```

**Decimal Precision:**
- Import: `from decimal import Decimal, getcontext`
- Set context: `getcontext().prec = 28` (configurable per asset class)
- String construction: `Decimal("42.123")` (never `Decimal(42.123)` to avoid float rounding)
- Comparison: Use Decimal comparison directly (`a > b`), avoid float conversion

**Error Handling:**
- Specific exceptions: Create custom exception classes (e.g., `BrokerError`, `DataAdapterError`)
- Exception hierarchy:
  ```python
  class RustyBTError(Exception):
      """Base exception for RustyBT."""

  class BrokerError(RustyBTError):
      """Broker API error."""

  class OrderRejectedError(BrokerError):
      """Order rejected by broker."""
  ```
- Logging: Always log exceptions with context:
  ```python
  import structlog
  logger = structlog.get_logger()

  try:
      order_id = broker.submit_order(...)
  except BrokerError as e:
      logger.error("order_submission_failed", asset=asset, amount=amount, error=str(e))
      raise
  ```

**Async/Await:**
- Use `async`/`await` for all broker API calls and I/O operations
- Event loop: asyncio (standard library)
- Example:
  ```python
  async def fetch_positions(self) -> List[Dict]:
      async with aiohttp.ClientSession() as session:
          async with session.get(self.positions_url) as response:
              return await response.json()
  ```

**Logging:**
- Use `structlog` for structured logging
- Log levels:
  - DEBUG: Detailed calculations, internal state
  - INFO: Trade executions, strategy signals, state checkpoints
  - WARNING: Retries, reconciliation mismatches, degraded performance
  - ERROR: Order rejections, connection failures, exceptions
- Example:
  ```python
  logger.info(
      "order_filled",
      order_id=order.id,
      asset=order.asset.symbol,
      fill_price=str(order.fill_price),
      amount=str(order.amount),
      commission=str(order.commission)
  )
  ```

## Zero-Mock Enforcement (MANDATORY)

**The Five Absolutes - NEVER:**
1. **NEVER** return hardcoded values in production code
2. **NEVER** write validation that always succeeds
3. **NEVER** simulate when you should calculate
4. **NEVER** stub when you should implement
5. **NEVER** claim completion for incomplete work
6. **NEVER** simplify a test to avoid an error

**Pre-Commit Checklist (BLOCKING):**

Before EVERY commit, CI/CD will verify:
- ❌ No TODO/FIXME/HACK comments without issue tracking
- ❌ No hardcoded return values (e.g., `return 10`, `return 1.0`, `return True`)
- ❌ No empty `except` blocks or `pass` statements in production code
- ❌ No "mock", "fake", "stub", "dummy" in variable/function names
- ❌ No simplified implementations without SIMPLIFIED warning blocks
- ✅ All tests exercise real functionality, not mocks
- ✅ All validations perform actual checks

**Forbidden Patterns:**

```python
# ❌ ABSOLUTELY FORBIDDEN
def calculate_sharpe_ratio(returns):
    return 1.5  # Mock value

def validate_data(data):
    return True  # Always passes

try:
    risky_operation()
except:
    pass  # Silently swallows errors

# ✅ CORRECT IMPLEMENTATION
def calculate_sharpe_ratio(returns: pl.Series) -> Decimal:
    """Calculate actual Sharpe ratio from returns series."""
    if len(returns) < 2:
        raise ValueError("Insufficient data for Sharpe ratio calculation")
    mean_return = returns.mean()
    std_return = returns.std()
    if std_return == 0:
        return Decimal(0)
    return Decimal(str(mean_return / std_return))

def validate_ohlcv_data(data: pl.DataFrame) -> bool:
    """Validate OHLCV data constraints."""
    # Check required columns exist
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    if not all(col in data.columns for col in required_cols):
        raise ValidationError(f"Missing required columns: {required_cols}")

    # Validate OHLCV relationships
    invalid_rows = data.filter(
        (pl.col('high') < pl.col('low')) |
        (pl.col('high') < pl.col('open')) |
        (pl.col('high') < pl.col('close')) |
        (pl.col('low') > pl.col('open')) |
        (pl.col('low') > pl.col('close'))
    )
    if len(invalid_rows) > 0:
        raise ValidationError(f"Invalid OHLCV relationships in {len(invalid_rows)} rows")

    return True

try:
    order_id = broker.submit_order(asset, amount)
except BrokerConnectionError as e:
    logger.error("broker_connection_failed", error=str(e), broker=broker.name)
    raise BrokerError(f"Failed to connect to {broker.name}: {e}") from e
except OrderRejectedError as e:
    logger.warning("order_rejected", asset=asset, amount=amount, reason=str(e))
    raise
```

**Automated Enforcement in CI/CD:**

```yaml
# Required in .github/workflows/quality-enforcement.yml
jobs:
  zero-mock-enforcement:
    runs-on: ubuntu-latest
    steps:
      - name: Detect mock patterns (BLOCKING)
        run: |
          python scripts/detect_mocks.py --strict
          # Returns exit code 1 if ANY mocks found

      - name: Validate hardcoded values (BLOCKING)
        run: |
          python scripts/detect_hardcoded_values.py --fail-on-found

      - name: Check validation functions (BLOCKING)
        run: |
          python scripts/verify_validations.py --ensure-real-checks

      - name: Test result uniqueness (BLOCKING)
        run: |
          pytest tests/ --unique-results-check
          # Ensures different inputs produce different outputs
```

**Pre-Commit Hook (Installed Automatically):**

```python
#!/usr/bin/env python
# .git/hooks/pre-commit (auto-generated)

import subprocess
import sys

def check_for_violations():
    """Prevent commits with mock code or hardcoded values."""
    checks = [
        ('Mock detection', ['python', 'scripts/detect_mocks.py', '--quick']),
        ('Hardcoded values', ['python', 'scripts/detect_hardcoded_values.py', '--quick']),
        ('Empty except blocks', ['python', 'scripts/check_error_handling.py']),
    ]

    violations = []
    for check_name, command in checks:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            violations.append((check_name, result.stdout))

    if violations:
        print("❌ COMMIT BLOCKED: Quality violations detected!\n")
        for name, output in violations:
            print(f"\n[{name}]")
            print(output)
        print("\nTo override (NOT RECOMMENDED): git commit --no-verify")
        return False

    print("✅ Pre-commit checks passed")
    return True

if __name__ == "__main__":
    if not check_for_violations():
        sys.exit(1)
```

**Story Completion Criteria (BLOCKING):**

No story can be marked complete without passing:

1. **Mock Scan**: `scripts/detect_mocks.py` returns 0 violations
2. **Validation Test**: All validators reject invalid data
3. **Unique Results Test**: Different inputs produce different outputs
4. **Performance Validation**: Computation shows measurable time (not instant)
5. **Code Review**: Senior developer sign-off on implementation quality

**Consequences:**

- **First Violation**: Mandatory code review training + all code requires senior review for 2 weeks
- **Second Violation**: Removed from critical path stories
- **Third Violation**: Removed from project development team

## Code Quality Guardrails (MANDATORY)

**1. Complexity Limits:**
- Maximum cyclomatic complexity: 10 per function
- Maximum function length: 50 lines
- Maximum file length: 500 lines
- Enforce via `ruff` with complexity checks:
  ```toml
  [tool.ruff.lint.mccabe]
  max-complexity = 10
  ```

**2. Import Organization:**
- Standard library imports first
- Third-party imports second
- Local imports third
- Example:
  ```python
  # Standard library
  from decimal import Decimal
  from typing import List, Optional

  # Third-party
  import polars as pl
  from ccxt import Exchange

  # Local
  from rustybt.finance.decimal import DecimalLedger
  from rustybt.data.polars import PolarsBarReader
  ```

**3. Mutation Safety:**
- Immutable data structures preferred (use `dataclasses(frozen=True)`)
- Functions should not mutate input arguments
- Example:
  ```python
  from dataclasses import dataclass

  @dataclass(frozen=True)
  class DecimalPosition:
      asset: Asset
      amount: Decimal
      cost_basis: Decimal
      last_sale_price: Decimal
  ```

**4. Null Safety:**
- Explicit `Optional` types for nullable values
- No implicit `None` returns
- Example:
  ```python
  def find_position(asset: Asset) -> Optional[DecimalPosition]:
      """Find position for asset, returns None if not found."""
      return self._positions.get(asset.sid)

  # Usage with null check
  position = ledger.find_position(asset)
  if position is not None:
      # Safe to use position
      return position.market_value
  else:
      return Decimal(0)
  ```

**5. Performance Assertions:**
- All performance-critical functions must have benchmarks
- Regression tests fail if performance degrades >20%
- Example:
  ```python
  @pytest.mark.benchmark
  def test_decimal_ledger_performance(benchmark):
      """Ensure ledger updates complete in <1ms."""
      result = benchmark(ledger.process_transaction, transaction)
      assert result.duration < 0.001  # 1ms threshold
  ```

**6. Temporal Integrity Enforcement:**
- All data access must be timestamp-validated
- Forward-looking data access raises `LookaheadError`
- Example:
  ```python
  def get_price(self, asset: Asset, dt: pd.Timestamp) -> Decimal:
      """Get price at timestamp, raises if future data accessed."""
      if dt > self.current_simulation_time:
          raise LookaheadError(
              f"Attempted to access future price at {dt}, "
              f"current time is {self.current_simulation_time}"
          )
      return self._data_portal.get_price(asset, dt)
  ```

**7. Mandatory Code Reviews:**
- All PRs require 2 approvals:
  - 1 from senior developer
  - 1 from financial domain expert (for finance/ modules)
- PR checklist enforced via GitHub Actions:
  - [ ] All tests pass (90%+ coverage)
  - [ ] Mock detection returns 0 violations
  - [ ] Performance benchmarks pass
  - [ ] Documentation updated
  - [ ] CHANGELOG.md entry added

**8. Documentation Requirements:**
- Public API: 100% docstring coverage
- Complex algorithms: Inline comments explaining approach
- Non-obvious decisions: ADR (Architecture Decision Record) in `docs/adr/`
- Example ADR:
  ```markdown
  # ADR-001: Use Decimal for Financial Calculations

  ## Status
  Accepted

  ## Context
  Python float64 causes rounding errors in financial calculations.

  ## Decision
  Use Decimal throughout finance modules.

  ## Consequences
  - ✅ Audit-compliant precision
  - ✅ No rounding errors
  - ❌ 30% performance overhead (mitigated by Rust optimization)
  ```

**9. Security Guardrails:**
- Secrets detection in CI/CD (truffleHog, detect-secrets)
- All API keys must be in environment variables, never hardcoded
- SQL queries use parameterized statements (SQLAlchemy ORM)
- Input sanitization for all external data (Pydantic validation)

**10. Dependency Management:**
- Pin exact versions in `pyproject.toml`
- Weekly `pip-audit` security scan in CI/CD
- Quarterly dependency update review
- No GPL-licensed dependencies (Apache 2.0/MIT only)

## Testing Standards

**Test Coverage:**
- Overall: ≥90%
- Financial modules: ≥95%
- Property-based tests: 1000+ examples per test
- No mocking of production code (unit tests use real implementations)

**Test Organization:**
- Mirror source structure: `tests/finance/test_decimal_ledger.py` → `rustybt/finance/decimal/ledger.py`
- Test file naming: `test_<module>.py`
- Test function naming: `test_<function_name>_<scenario>`

**Test Types:**

**Unit Tests:**
```python
import pytest
from decimal import Decimal
from rustybt.finance.decimal import DecimalLedger, DecimalPosition

def test_portfolio_value_calculation():
    ledger = DecimalLedger(starting_cash=Decimal("100000"))
    position = DecimalPosition(
        asset=Asset(...),
        amount=Decimal("100"),
        cost_basis=Decimal("50"),
        last_sale_price=Decimal("55")
    )
    ledger.positions[position.asset] = position

    expected_value = Decimal("100") * Decimal("55") + Decimal("100000")
    assert ledger.portfolio_value == expected_value
```

**Property-Based Tests:**
```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    starting_cash=st.decimals(min_value=Decimal("1000"), max_value=Decimal("1000000")),
    position_value=st.decimals(min_value=Decimal("0"), max_value=Decimal("500000"))
)
def test_portfolio_value_invariant(starting_cash, position_value):
    """Portfolio value must equal cash + sum of position values."""
    ledger = DecimalLedger(starting_cash=starting_cash)
    # ... add position worth position_value

    assert ledger.portfolio_value == ledger.cash + ledger.positions_value
```

**Integration Tests:**
```python
@pytest.mark.integration
async def test_live_trading_order_lifecycle():
    """Test complete order lifecycle: submit → fill → position update."""
    engine = LiveTradingEngine(strategy=..., broker=PaperBroker())

    # Submit order
    order_id = await engine.submit_order(asset=AAPL, amount=Decimal("100"), order_type="market")

    # Wait for fill
    await asyncio.sleep(1)

    # Verify position
    position = engine.get_position(AAPL)
    assert position.amount == Decimal("100")
    assert position.cost_basis > Decimal("0")
```

**Fixtures:**
```python
@pytest.fixture
def sample_strategy():
    """Create sample strategy for testing."""
    class SampleStrategy(TradingAlgorithm):
        def initialize(self, context):
            context.asset = self.symbol('AAPL')

        def handle_data(self, context, data):
            self.order(context.asset, 100)

    return SampleStrategy()

def test_strategy_execution(sample_strategy):
    # Use fixture in test
    ...
```

## Documentation Standards

**Public API Documentation:**
- 100% docstring coverage for public APIs
- Sphinx-compatible reStructuredText format
- Include examples in docstrings:
  ```python
  def order(self, asset: Asset, amount: Decimal, **kwargs) -> str:
      """Place order for asset.

      Example:
          >>> order(context.asset, Decimal("100"), order_type="limit", limit_price=Decimal("42.50"))
          'order-123'
      """
  ```

**Tutorial Examples:**
- ≥30 tutorial notebooks (Jupyter)
- Categories:
  - Getting Started (5 notebooks)
  - Backtesting Strategies (10 notebooks)
  - Live Trading (8 notebooks)
  - Optimization (5 notebooks)
  - Advanced Topics (2 notebooks)
- Hosted on documentation site with Binder integration

**Architecture Documentation:**
- Keep `docs/architecture.md` updated with major changes
- Add diagrams using Mermaid or PlantUML
- Document integration points between components

**Changelog:**
- Maintain `CHANGELOG.md` following Keep a Changelog format
- Semantic versioning: MAJOR.MINOR.PATCH
- Document breaking changes prominently

---
