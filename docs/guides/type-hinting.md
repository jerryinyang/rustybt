# Type Hinting Guide for RustyBT

## Overview

RustyBT uses [mypy](https://mypy.readthedocs.io/) with `--strict` mode for static type checking following [PEP 484](https://peps.python.org/pep-0484/), [PEP 526](https://peps.python.org/pep-0526/), and [PEP 561](https://peps.python.org/pep-0561/). This guide explains our type hinting conventions, best practices, and gradual typing strategy.

## Quick Reference

### Basic Type Hints

```python
from decimal import Decimal
from typing import Optional

def calculate_returns(
    start_value: Decimal,
    end_value: Decimal,
    period_days: int
) -> Decimal:
    """Calculate annualized returns."""
    daily_return = (end_value - start_value) / start_value
    return daily_return * (Decimal(365) / Decimal(period_days))
```

### Modern Python 3.12+ Syntax

RustyBT requires Python 3.12+, so use modern type hint syntax:

```python
# ✅ Modern syntax (Python 3.12+)
def process_assets(assets: list[str]) -> dict[str, Decimal]:
    ...

def find_position(sid: int) -> Position | None:
    ...

# ❌ Old syntax (avoid)
from typing import List, Dict, Optional

def process_assets(assets: List[str]) -> Dict[str, Decimal]:
    ...

def find_position(sid: int) -> Optional[Position]:
    ...
```

### Collection Types

```python
# Lists
def get_sids() -> list[int]:
    return [1, 2, 3]

# Dictionaries
def get_prices() -> dict[str, Decimal]:
    return {"AAPL": Decimal("150.25")}

# Sets
def get_unique_assets() -> set[str]:
    return {"AAPL", "GOOGL"}

# Tuples (fixed length)
def get_high_low() -> tuple[Decimal, Decimal]:
    return (Decimal("100"), Decimal("90"))
```

### Optional and Union Types

```python
# Optional (value or None)
def get_position(sid: int) -> Position | None:
    """Returns position or None if not found."""
    return self._positions.get(sid)

# Union (multiple possible types)
def process_price(value: Decimal | float) -> Decimal:
    """Accept either Decimal or float."""
    if isinstance(value, float):
        return Decimal(str(value))
    return value
```

### Generic Types

```python
from typing import TypeVar, Generic

T = TypeVar('T')

class DataLoader(Generic[T]):
    """Generic data loader for any data type."""

    def load(self, source: str) -> list[T]:
        """Load data from source."""
        ...

    def validate(self, data: T) -> bool:
        """Validate a single data item."""
        ...
```

### Protocols (Structural Typing)

```python
from typing import Protocol
from decimal import Decimal

class BrokerAdapter(Protocol):
    """Protocol defining the broker adapter interface."""

    def submit_order(self, symbol: str, quantity: Decimal) -> str:
        """Submit order and return order ID."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order by ID."""
        ...

# Any class implementing these methods satisfies the protocol
# No explicit inheritance required
```

## Type Hinting Best Practices

### 1. Always Annotate Function Signatures

```python
# ✅ Good: Complete type hints
def calculate_sharpe_ratio(
    returns: list[Decimal],
    risk_free_rate: Decimal
) -> Decimal:
    ...

# ❌ Bad: Missing annotations
def calculate_sharpe_ratio(returns, risk_free_rate):
    ...
```

### 2. Use `None` for Void Functions

```python
# ✅ Good
def log_trade(order_id: str, price: Decimal) -> None:
    logger.info("trade_executed", order_id=order_id, price=price)

# ❌ Bad: Missing return type
def log_trade(order_id: str, price: Decimal):
    logger.info("trade_executed", order_id=order_id, price=price)
```

### 3. Avoid `Any` Unless Necessary

```python
# ✅ Good: Specific types
def serialize_order(order: Order) -> dict[str, str | int | Decimal]:
    ...

# ⚠️ Acceptable with justification
from typing import Any

def serialize_to_json(obj: Any) -> str:
    """Serialize arbitrary object to JSON.

    Uses Any because JSON supports arbitrary nested structures.
    """
    return json.dumps(obj)

# ❌ Bad: Lazy use of Any
def process_data(data: Any) -> Any:
    ...
```

### 4. Type Narrow for Complex Logic

```python
def process_price(value: str | Decimal | None) -> Decimal:
    """Process price from various input types."""
    if value is None:
        return Decimal(0)

    if isinstance(value, str):
        return Decimal(value)

    # mypy knows value must be Decimal here
    return value
```

### 5. Use TypeAlias for Complex Types

```python
from typing import TypeAlias

# Define complex types once
PriceMap: TypeAlias = dict[str, dict[str, Decimal]]
PositionMap: TypeAlias = dict[int, Position]

def get_prices() -> PriceMap:
    ...

def get_positions() -> PositionMap:
    ...
```

## Gradual Typing Strategy

RustyBT uses **gradual typing** to balance type safety with pragmatic development:

### Strict Typing Modules

These modules enforce full `mypy --strict` compliance:

- ✅ `rustybt.exceptions` - Exception hierarchy
- ✅ `rustybt.utils.logging` - Structured logging
- ✅ `rustybt.utils.error_handling` - Error handling utilities
- ✅ **All new code** (Epic 8+)

### Gradual Migration Modules

Legacy Zipline modules have relaxed type checking (temporarily):

- `rustybt.algorithm` - Core backtest algorithm
- `rustybt.assets.*` - Asset classes
- `rustybt.data.*` - Data infrastructure
- `rustybt.finance.*` - Finance calculations
- `rustybt.pipeline.*` - Pipeline framework

**Migration plan**: These modules will be migrated to strict typing incrementally in future releases.

### Configuration

Type checking behavior is configured in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.12"
strict = true  # Global strict mode
warn_return_any = true
# ... other strict flags

[[tool.mypy.overrides]]
module = [
    "rustybt.algorithm",
    "rustybt.assets.*",
    # ... other legacy modules
]
# Temporarily disable strict checks for gradual migration
disallow_untyped_defs = false
disallow_untyped_calls = false
```

## mypy Configuration

### Running mypy Locally

```bash
# Check entire codebase
mypy rustybt/ --strict

# Check specific module
mypy rustybt/analytics/attribution.py --strict

# Check with coverage report
mypy rustybt/ --strict --any-exprs-report=.mypy_coverage
```

### Pre-commit Integration

mypy runs automatically on staged files:

```bash
# Install pre-commit hooks
pre-commit install

# Run manually on all files
pre-commit run mypy --all-files
```

### CI/CD Integration

GitHub Actions runs mypy on every PR:

```yaml
# .github/workflows/ci.yml
- name: Run mypy
  run: mypy --strict rustybt/
```

Builds **fail** if mypy finds type errors in strict modules.

## Common mypy Errors and Solutions

### Error: Missing return type

```python
# ❌ Error
def get_price(asset):
    return asset.price

# ✅ Fix
def get_price(asset: Asset) -> Decimal:
    return asset.price
```

### Error: Incompatible return type

```python
# ❌ Error (dict.get returns Optional[V])
def get_position(sid: int) -> Position:
    return self._positions.get(sid)

# ✅ Fix (acknowledge None possibility)
def get_position(sid: int) -> Position | None:
    return self._positions.get(sid)
```

### Error: Untyped function call

```python
# ❌ Error (calling function without type hints)
result = some_legacy_function(data)

# ✅ Fix (annotate the legacy function)
def some_legacy_function(data: DataFrame) -> ProcessedData:
    ...

# ⚠️ Temporary workaround (use with caution)
from typing import cast
result = cast(ProcessedData, some_legacy_function(data))
```

### Error: Missing library stubs

```python
# ❌ Error: "toolz" has no type stubs
import toolz

# ✅ Fix: Add module override in pyproject.toml
[[tool.mypy.overrides]]
module = ["toolz.*"]
ignore_missing_imports = true
```

## Type Stubs for External Libraries

RustyBT includes type stubs for common libraries:

```toml
# pyproject.toml
dev = [
    'mypy>=1.10.0',
    'types-requests>=2.31.0',
    'types-pytz>=2024.1.0',
    'types-PyYAML>=6.0.12',
    'pandas-stubs>=2.0.0',
    'sqlalchemy-stubs>=0.4',
    'types-python-dateutil>=2.8.19',
    'types-networkx>=3.0',
    'types-seaborn>=0.13.0',
]
```

Libraries without stubs (configured to `ignore_missing_imports`):
- `toolz`
- `multipledispatch`
- `statsmodels`

## PEP 561 Typed Package

RustyBT is a [PEP 561](https://peps.python.org/pep-0561/) typed package:

- Contains `rustybt/py.typed` marker file
- Distributes `.pyi` stub files
- Downstream projects can type-check against RustyBT APIs

## Resources

- [mypy Documentation](https://mypy.readthedocs.io/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 526 - Variable Annotations](https://peps.python.org/pep-0526/)
- [PEP 561 - Distributing Type Information](https://peps.python.org/pep-0561/)
- [Python typing module](https://docs.python.org/3/library/typing.html)

## Migration Checklist for New Code

When adding new modules or functions:

- [ ] Add parameter type hints for all function arguments
- [ ] Add return type hints (use `-> None` for void functions)
- [ ] Use Python 3.12+ syntax (`list[T]`, `dict[K,V]`, `T | None`)
- [ ] Avoid `Any` unless absolutely necessary (document why if used)
- [ ] Run `mypy --strict` on your module before committing
- [ ] Verify pre-commit hook passes
- [ ] Ensure CI mypy check passes

## Contact

For questions about type hinting in RustyBT:
- Review this guide
- Check `pyproject.toml` for current mypy configuration
- See examples in `rustybt/exceptions.py`, `rustybt/utils/logging.py`
