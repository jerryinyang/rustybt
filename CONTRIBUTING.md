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
- Run `mypy --strict` before committing:
  ```bash
  mypy rustybt/ --strict
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

**CRITICAL**: RustyBT enforces a strict no-mock policy for production code:

1. ❌ **NEVER** return hardcoded values in production code
2. ❌ **NEVER** write validation that always succeeds
3. ❌ **NEVER** simulate when you should calculate
4. ❌ **NEVER** stub when you should implement
5. ❌ **NEVER** claim completion for incomplete work
6. ❌ **NEVER** simplify a test to avoid an error

See [docs/architecture/zero-mock-enforcement.md](docs/architecture/zero-mock-enforcement.md) for full details.

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

**Property-Based Tests:**
```python
from hypothesis import given, strategies as st

@given(starting_cash=st.decimals(min_value=Decimal("1000")))
def test_portfolio_value_invariant(starting_cash):
    """Portfolio value must equal cash + sum of position values."""
    ledger = DecimalLedger(starting_cash=starting_cash)
    assert ledger.portfolio_value == ledger.cash + ledger.positions_value
```

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
