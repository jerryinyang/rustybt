# Contributing to RustyBT

Thank you for your interest in contributing to RustyBT! This document provides guidelines and instructions for setting up your development environment and contributing to the project.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [System Requirements](#system-requirements)
- [Quick Start Guide](#quick-start-guide)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)

## Development Environment Setup

### System Requirements

**Operating Systems:**
- Linux (Ubuntu 20.04+, Debian 11+, or equivalent)
- macOS (11.0+ / Big Sur or later)
- Windows 10/11 (with WSL2 recommended)

**Python Version:**
- Python 3.12 or higher (required)
- Python 3.13 supported

**Required Tools:**
- Git
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- C compiler (for Cython extensions)

### Quick Start Guide

#### 1. Clone the Repository

```bash
git clone https://github.com/your-org/rustybt.git
cd rustybt
```

#### 2. Set Up Virtual Environment

**Using uv (Recommended):**

```bash
# Create virtual environment with Python 3.12
uv venv --python 3.12

# Activate virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

**Using standard venv:**

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Unix/macOS
```

#### 3. Install Dependencies

**Using uv:**

```bash
uv pip install -e ".[dev,test]"
```

**Using pip:**

```bash
pip install -e ".[dev,test]"
```

This installs:
- **Core dependencies**: numpy, pandas, sqlalchemy, exchange-calendars, polars, structlog, pydantic
- **Development tools**: black, ruff, mypy, pre-commit
- **Testing tools**: pytest, pytest-cov, pytest-xdist, hypothesis

#### 4. Verify Installation

```bash
# Check that rustybt is installed
python -c "import rustybt; print(rustybt.__version__)"

# Verify dependencies
python -c "import polars, hypothesis, structlog; print('All dependencies OK')"

# Run a quick test
pytest tests/ -k "test_imports" -v
```

#### 5. Set Up Pre-Commit Hooks (Required)

RustyBT uses pre-commit hooks to automatically check code quality before each commit. This ensures consistent code style and catches issues early.

**Install pre-commit hooks:**

```bash
# Install the hooks into your git repository
pre-commit install
```

**What the hooks do:**
- **ruff**: Automatically fixes linting issues and enforces code quality rules
- **black**: Formats code to match project style (line length 100)
- **mypy**: Type checks strict modules (exceptions, utils/{logging,error_handling,secure_pickle}, analytics/*)
- **detect-mocks**: Scans production code for mock patterns (Zero-Mock Enforcement)
- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with newline
- **check-yaml/toml/json**: Validates config files
- **detect-private-key**: Prevents accidental commit of secrets
- **bandit**: Security checks for common vulnerabilities

**Test the hooks:**

```bash
# Run hooks on all files to verify setup
pre-commit run --all-files
```

**Bypass hooks (NOT recommended):**

If you absolutely need to commit without running hooks (not recommended):
```bash
git commit --no-verify -m "Your message"
```

## Coding Standards

RustyBT follows strict coding standards to ensure code quality and maintainability.

### Python Style

**Language Version:**
- Python 3.12+ required
- Use modern features: structural pattern matching, enhanced type hints, improved asyncio

**Code Formatting:**
- **black**: Line length 100, Python 3.12 target
  ```bash
  black rustybt/ tests/ --line-length 100
  ```

- **ruff**: Fast linter (replaces flake8, isort, pyupgrade)
  ```bash
  ruff check rustybt/ tests/
  ```

**Type Hints:**
- 100% type hint coverage for public APIs required
- Gradual typing strategy: strict for new code (Epic 8+), relaxed for legacy Zipline modules
- Strict modules (enforced in pre-commit): `exceptions`, `utils/logging`, `utils/error_handling`, `utils/secure_pickle`, `analytics/*`
- Run mypy before committing (pre-commit hooks will check strict modules automatically):
  ```bash
  python3 -m mypy
  ```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `DecimalLedger`, `PolarsDataPortal`)
- **Functions/methods**: `snake_case` (e.g., `calculate_returns`, `fetch_ohlcv`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_LEVERAGE`, `DEFAULT_PRECISION`)
- **Private members**: prefix with `_` (e.g., `_internal_state`)

### Docstrings

All public classes, functions, and methods require Google-style docstrings:

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

### Zero-Mock Enforcement

**CRITICAL**: RustyBT enforces a strict no-mock policy for production code to ensure production reliability. All production code must contain real implementations that perform actual calculations, validations, and business logic.

#### Policy Principles

1. ❌ **NEVER** return hardcoded values in production code
2. ❌ **NEVER** write validation that always succeeds
3. ❌ **NEVER** simulate when you should calculate
4. ❌ **NEVER** stub when you should implement
5. ❌ **NEVER** claim completion for incomplete work
6. ❌ **NEVER** simplify a test to avoid an error

#### Enforcement Mechanisms

Zero-mock enforcement is automatically checked via:

1. **Pre-commit hooks**: Runs `detect_mocks.py --quick` on every commit (< 2s)
2. **CI/CD pipeline**: Runs comprehensive checks on every PR (activated in Story X2.5)
3. **Manual scripts**: Available for local testing and validation

**Run checks locally:**

```bash
# Detect mock patterns in function/class names
python scripts/detect_mocks.py --strict

# Detect functions returning hardcoded constant values
python scripts/detect_hardcoded_values.py --fail-on-found

# Verify validation functions reject invalid data
python scripts/verify_validations.py --ensure-real-checks

# Test functions produce unique outputs for different inputs
python scripts/test_unique_results.py
```

#### Forbidden Patterns

**❌ Mock Implementations:**

```python
# FORBIDDEN: Mock function name
def mock_calculate_returns(prices):
    return [0.01, 0.02, 0.03]

# FORBIDDEN: Fake broker
class FakeBroker:
    def submit_order(self, order):
        return "fake-order-123"

# FORBIDDEN: Placeholder implementation
def calculate_sharpe_ratio(returns):
    pass  # TODO: implement later
```

**❌ Hardcoded Return Values:**

```python
# FORBIDDEN: Always returns same value
def calculate_commission(order):
    return Decimal("10.00")  # Hardcoded!

# FORBIDDEN: Validation that never fails
def validate_price(price):
    return True  # Always passes!

# FORBIDDEN: Mock calculation
def calculate_volatility(returns):
    return 0.15  # Fake value
```

**❌ Mock Imports in Production Code:**

```python
# FORBIDDEN: Mock imports in production modules
from unittest.mock import Mock, MagicMock
import mock

# These are only allowed in test files!
```

#### Allowed Patterns

**✅ Real Implementations:**

```python
# ALLOWED: Real calculation
def calculate_commission(order: Order) -> Decimal:
    """Calculate actual commission based on order parameters."""
    if order.quantity < 100:
        return Decimal("9.99")
    return Decimal("9.99") + (order.quantity * Decimal("0.01"))

# ALLOWED: Real validation
def validate_price(price: Decimal) -> bool:
    """Validate price is positive Decimal."""
    if not isinstance(price, Decimal):
        raise TypeError(f"Price must be Decimal, got {type(price)}")
    if price <= Decimal("0"):
        raise ValueError(f"Price must be positive, got {price}")
    return True

# ALLOWED: Real calculation with business logic
def calculate_sharpe_ratio(returns: pl.Series) -> Decimal:
    """Calculate actual Sharpe ratio from returns series."""
    if len(returns) < 2:
        raise ValueError("Insufficient data for Sharpe ratio")
    mean_return = returns.mean()
    std_return = returns.std()
    if std_return == 0:
        return Decimal("0")
    return Decimal(str(mean_return / std_return * np.sqrt(252)))
```

**✅ Test Fixtures (Only in Test Files):**

```python
# ALLOWED: Mock objects in test files only
@pytest.fixture
def mock_broker():
    """Create mock broker for testing."""
    return Mock(spec=BrokerBase)

# ALLOWED: Fake data for testing
@pytest.fixture
def sample_prices():
    """Create sample price data for testing."""
    return pl.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10),
        "close": [100.0, 101.0, 99.5, 102.0, 103.5, 102.8, 104.0, 105.2, 104.8, 106.0]
    })
```

#### Rationale

**Why No Mocks in Production Code?**

1. **Reliability**: Mock implementations don't perform real work and can mask bugs
2. **Correctness**: Hardcoded values bypass business logic and produce incorrect results
3. **Maintainability**: Mock code creates technical debt and confusion
4. **Trust**: Production systems must be trustworthy with real implementations

**Where Mocks ARE Allowed:**

- Test files (`tests/**/*.py`)
- Test fixtures and helpers
- Development/debugging utilities (clearly marked)

#### Getting Help

If you're unsure whether your code violates the zero-mock policy:

1. Run the detection scripts locally: `python scripts/detect_mocks.py`
2. Check the pre-commit hooks: `pre-commit run --all-files`
3. Review examples in this document
4. Ask in PR review if uncertain

See [docs/architecture/zero-mock-enforcement.md](docs/architecture/zero-mock-enforcement.md) for full architectural details.

## Testing

### Running Tests

**Run full test suite:**

```bash
pytest tests/ -v
```

**Run with coverage:**

```bash
pytest tests/ --cov=rustybt --cov-report=term --cov-report=html
```

**Run in parallel:**

```bash
pytest tests/ -n auto
```

**Run specific test file:**

```bash
pytest tests/finance/test_decimal_ledger.py -v
```

### Test Organization

- Tests mirror source structure: `tests/finance/test_ledger.py` → `rustybt/finance/ledger.py`
- Test files follow naming convention: `test_<module>.py`
- Test functions follow naming convention: `test_<function_name>_<scenario>`

### Coverage Requirements

- Overall: ≥90%
- Financial modules: ≥95%
- New code: 100% coverage required

### Test Types

**Unit Tests:**
```python
def test_portfolio_value_calculation():
    ledger = DecimalLedger(starting_cash=Decimal("100000"))
    # Test implementation...
    assert ledger.portfolio_value == expected_value
```

**Property-Based Tests (Hypothesis):**

RustyBT uses [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing to verify mathematical properties hold across thousands of test cases.

Basic example:
```python
from hypothesis import given, strategies as st, settings
from decimal import Decimal
import pytest

@pytest.mark.property
@given(
    a=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000")),
    b=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000"))
)
@settings(max_examples=1000)
def test_decimal_addition_commutative(a: Decimal, b: Decimal) -> None:
    """Verify Decimal addition is commutative: a + b == b + a."""
    assert a + b == b + a
```

**Hypothesis Profiles:**

RustyBT configures three hypothesis profiles in `pyproject.toml`:

- **`default`**: 1000 examples per test (standard development)
- **`quick`**: 100 examples per test (fast iteration during development)
- **`ci`**: 1000 examples, derandomized (reproducible CI/CD runs)

Run tests with specific profile:
```bash
# Quick profile for fast feedback
pytest -m property --hypothesis-profile=quick

# Default profile (1000 examples)
pytest -m property

# CI profile (deterministic)
pytest -m property --hypothesis-profile=ci
```

**Writing Property Tests:**

1. **Mark with `@pytest.mark.property`** to enable selective execution:
   ```python
   @pytest.mark.property
   @given(...)
   def test_my_property(...):
       ...
   ```

2. **Use appropriate strategies** for financial data:
   ```python
   # Decimals with financial precision
   st.decimals(
       min_value=Decimal("0.01"),
       max_value=Decimal("1000000"),
       allow_nan=False,
       allow_infinity=False,
       places=8
   )

   # Non-zero decimals for division
   st.one_of(
       st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000")),
       st.decimals(min_value=Decimal("-1000"), max_value=Decimal("-0.01"))
   )
   ```

3. **Configure test examples** with `@settings`:
   ```python
   @settings(max_examples=1000)
   def test_my_property(...):
       ...
   ```

4. **Document the property** being tested in docstring:
   ```python
   def test_decimal_distributivity(a, b, c):
       """Verify Decimal distributivity: a * (b + c) == (a * b) + (a * c)."""
       assert a * (b + c) == (a * b) + (a * c)
   ```

**Running Property Tests:**

```bash
# Run all property tests
pytest -m property

# Run property tests with coverage
pytest -m property --cov=rustybt --cov-report=term

# Run property tests with statistics
pytest -m property --hypothesis-show-statistics
```

**CI Property Test Execution:**

Property tests run automatically in CI/CD with the `ci` profile:
- ✅ 1000 examples per test for thorough validation
- ✅ Derandomized for reproducible results
- ✅ Failures create GitHub issues with shrunk examples

See `.github/workflows/property-tests.yml` for CI configuration.

For complete examples, see `tests/finance/test_decimal_properties.py`.

## Pull Request Process

### Before Submitting

1. **Run all quality checks:**
   ```bash
   # Format code
   black rustybt/ tests/

   # Lint
   ruff check rustybt/ tests/

   # Type check
   mypy rustybt/ --strict

   # Run tests
   pytest tests/ -v --cov=rustybt
   ```

2. **Ensure all tests pass**
3. **Update documentation** if you changed APIs
4. **Add tests** for new functionality

### PR Guidelines

**Title Format:**
```
[Category] Brief description

Examples:
[Feature] Add DecimalLedger for financial calculations
[Fix] Correct Polars data loading bug
[Docs] Update installation instructions
[Test] Add property tests for decimal arithmetic
```

**Description Template:**

```markdown
## Summary
Brief description of changes

## Changes Made
- Bullet list of specific changes
- Include file paths for major changes

## Testing
- How did you test these changes?
- What test cases did you add?

## Checklist
- [ ] All tests pass locally
- [ ] Added tests for new functionality
- [ ] Updated documentation
- [ ] Followed coding standards
- [ ] No mock code or hardcoded values
```

### Code Review

All PRs require:
- ✅ 2 approvals from maintainers
- ✅ All CI/CD checks passing
- ✅ Code coverage maintained or improved
- ✅ No violations of zero-mock policy

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/your-org/rustybt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/rustybt/discussions)
- **Documentation**: See [docs/](docs/) directory

## Additional Resources

- [Coding Standards](docs/architecture/coding-standards.md)
- [Tech Stack](docs/architecture/tech-stack.md)
- [Source Tree](docs/architecture/source-tree.md)
- [Zero-Mock Enforcement](docs/architecture/zero-mock-enforcement.md)

---

Thank you for contributing to RustyBT! 🚀
