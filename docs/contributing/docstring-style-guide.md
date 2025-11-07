# Docstring Style Guide

**Last Updated:** 2025-11-07
**Standard:** Google Style
**Python Version:** 3.12+

## Overview

RustyBT uses **Google-style docstrings** for all Python code. This guide provides templates, examples, and best practices for writing clear, comprehensive, and maintainable documentation.

## Why Google Style?

- **Readability:** Clean, easy-to-read format
- **Tool Support:** Excellent support in mkdocstrings, IDEs, and type checkers
- **Consistency:** Matches modern Python ecosystem standards
- **Examples:** Natural integration of code examples

## Table of Contents

1. [Module Docstrings](#module-docstrings)
2. [Class Docstrings](#class-docstrings)
3. [Function/Method Docstrings](#functionmethod-docstrings)
4. [Type Hints](#type-hints)
5. [Examples](#examples)
6. [Common Patterns](#common-patterns)
7. [Migration from NumPy Style](#migration-from-numpy-style)

---

## Module Docstrings

Every Python module (`.py` file) should start with a module-level docstring.

### Template

```python
"""Brief one-line summary of the module.

More detailed description of the module's purpose and contents.
Can span multiple lines.

Key components:
- Component 1: Brief description
- Component 2: Brief description

Example:
    >>> from rustybt.module import SomeClass
    >>> obj = SomeClass()
    >>> obj.method()
"""
```

### Examples

**Good - Comprehensive Module Docstring:**
```python
"""Decimal-precision performance metrics for RustyBT.

This module implements performance metrics using Decimal arithmetic for
audit-compliant financial calculations. All metrics maintain precision
throughout the calculation pipeline.

Key metrics:
- Sharpe ratio: Risk-adjusted return metric
- Sortino ratio: Downside risk-adjusted return
- Maximum drawdown: Largest peak-to-trough decline
- VaR/CVaR: Value at Risk and Conditional VaR

The module uses Polars DataFrames with Decimal types to ensure financial-grade
precision without floating-point errors.

Example:
    >>> from rustybt.finance.metrics import calculate_sharpe_ratio
    >>> sharpe = calculate_sharpe_ratio(returns_series, risk_free_rate=Decimal("0.02"))
    >>> print(f"Sharpe Ratio: {sharpe}")
"""
```

**Good - Simple Module Docstring:**
```python
"""Order execution styles for algorithmic trading.

Defines execution style classes (Market, Limit, Stop, etc.) that control
how orders are executed in the simulation and live trading environments.
"""
```

**Bad - Missing Details:**
```python
"""Order execution."""  # Too brief, no context
```

**Bad - No Docstring:**
```python
# order_execution.py
from .base import Order  # Missing module docstring entirely!
```

---

## Class Docstrings

Every public class should have a comprehensive docstring.

### Template

```python
class ClassName:
    """Brief one-line summary of the class.

    More detailed description of what the class does, its purpose,
    and how it fits into the larger system.

    Attributes:
        attr1: Description of attribute 1
        attr2: Description of attribute 2

    Example:
        >>> obj = ClassName(param1="value")
        >>> result = obj.method()
        >>> print(result)

    Note:
        Any important notes about usage, thread safety, etc.
    """
```

### Examples

**Good - Complete Class Docstring:**
```python
class PolarsDataPortal:
    """Data portal with Polars backend and Decimal precision.

    This class provides a unified interface for accessing OHLCV data
    with Decimal precision. It supports both daily and minute-frequency data
    and handles currency conversion automatically.

    The portal acts as the main data access layer for backtesting and live
    trading, providing consistent APIs regardless of the underlying data source.

    Attributes:
        daily_reader: Reader for daily OHLCV bars
        minute_reader: Reader for minute OHLCV bars (optional)
        data_source: Unified data source interface
        fx_converter: Currency conversion handler

    Example:
        >>> from rustybt.data.polars import PolarsDataPortal
        >>> portal = PolarsDataPortal.from_bundle("/path/to/bundle")
        >>> data = portal.get_history_window(
        ...     assets=[Asset(1)],
        ...     end_dt=pd.Timestamp("2024-01-31"),
        ...     bar_count=30,
        ...     frequency="1d",
        ...     field="close"
        ... )
        >>> print(data.head())

    Note:
        Thread-safe for read operations. Multiple strategies can share
        the same portal instance.
    """
```

**Good - Dataclass with Attributes:**
```python
@dataclass
class OrderConfig:
    """Configuration for order execution behavior.

    Controls how orders are validated, executed, and tracked during
    backtesting and live trading.

    Attributes:
        validate_cash: Whether to check available cash before orders
        allow_fractional: Whether fractional shares are permitted
        default_commission: Default commission model to use
        default_slippage: Default slippage model to use
        max_order_value: Maximum value per order (None = unlimited)

    Example:
        >>> config = OrderConfig(
        ...     validate_cash=True,
        ...     allow_fractional=False,
        ...     max_order_value=Decimal("100000")
        ... )
    """
    validate_cash: bool = True
    allow_fractional: bool = False
    default_commission: CommissionModel | None = None
    default_slippage: SlippageModel | None = None
    max_order_value: Decimal | None = None
```

**Bad - Minimal Class Docstring:**
```python
class Order:
    """An order."""  # Too brief, no useful information
```

---

## Function/Method Docstrings

All public functions and methods should have docstrings.

### Template

```python
def function_name(param1: type1, param2: type2) -> return_type:
    """Brief one-line summary of what the function does.

    More detailed description of the function's behavior,
    algorithm, or implementation details if needed.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter
            Can span multiple lines if needed

    Returns:
        Description of return value. Include type if not obvious
        from type hints.

    Raises:
        ErrorType1: When this error occurs
        ErrorType2: When this other error occurs

    Example:
        >>> result = function_name(param1=10, param2="value")
        >>> print(result)
        42

    Note:
        Any important notes about performance, side effects, etc.
    """
```

### Examples

**Good - Complete Function Docstring:**
```python
def calculate_sharpe_ratio(
    returns: pl.Series,
    risk_free_rate: Decimal = Decimal("0"),
    annualization_factor: int = 252,
    config: DecimalConfig | None = None,
) -> Decimal:
    """Calculate Sharpe ratio with Decimal precision.

    The Sharpe ratio measures risk-adjusted return by dividing excess return
    (return minus risk-free rate) by return volatility (standard deviation).
    Higher values indicate better risk-adjusted performance.

    Args:
        returns: Time series of returns (as decimal values, not percentages)
        risk_free_rate: Annual risk-free rate (default: 0)
        annualization_factor: Factor to annualize ratio (252 for daily, 12 for monthly)
        config: Decimal configuration for precision control

    Returns:
        Annualized Sharpe ratio as Decimal. Returns Decimal("0") if insufficient
        data or zero volatility.

    Raises:
        InsufficientDataError: If returns series is empty or has < 2 values
        InvalidMetricError: If calculation produces NaN or invalid result

    Example:
        >>> returns = pl.Series([
        ...     Decimal("0.01"), Decimal("-0.005"), Decimal("0.02"),
        ...     Decimal("0.015"), Decimal("-0.01")
        ... ])
        >>> sharpe = calculate_sharpe_ratio(
        ...     returns,
        ...     risk_free_rate=Decimal("0.02"),
        ...     annualization_factor=252
        ... )
        >>> print(f"Sharpe: {sharpe:.4f}")
        Sharpe: 1.2456

    Note:
        Uses Decimal arithmetic throughout to avoid floating-point errors.
        For large datasets (>10k returns), consider performance implications.
    """
```

**Good - Simple Method Docstring:**
```python
def get_asset_price(self, asset: Asset, dt: pd.Timestamp) -> Decimal:
    """Get the price of an asset at a specific datetime.

    Args:
        asset: Asset to retrieve price for
        dt: Timestamp to retrieve price at

    Returns:
        Price as Decimal value

    Raises:
        NoDataError: If no price data available for asset at dt
    """
```

**Good - Property Docstring:**
```python
@property
def total_value(self) -> Decimal:
    """Total portfolio value (positions + cash).

    Includes:
    - Market value of all positions at current prices
    - Cash balance in account currency
    - Pending deposits/withdrawals

    Returns:
        Total portfolio value as Decimal
    """
```

**Bad - Missing Details:**
```python
def calculate_metric(returns, rf):
    """Calculate metric."""  # What metric? What does it return?
    # No Args, Returns, or Raises sections
```

**Bad - No Docstring:**
```python
def process_data(df):  # Missing docstring entirely
    return df.filter(...)
```

---

## Type Hints

RustyBT requires Python 3.12+ and uses modern type hints extensively.

### Best Practices

1. **Always use type hints** for function parameters and return values
2. **Use modern syntax** (PEP 604: `X | Y` instead of `Union[X, Y]`)
3. **Import from `collections.abc`** not `typing` for abstract types
4. **Use `None` defaults** to indicate optional parameters

### Examples

**Good - Modern Type Hints:**
```python
from collections.abc import Callable, Sequence
from decimal import Decimal

def process_orders(
    orders: Sequence[Order],
    validator: Callable[[Order], bool] | None = None,
    max_retries: int = 3,
) -> dict[str, Order]:
    """Process a sequence of orders with optional validation.

    Args:
        orders: Orders to process
        validator: Optional validation function
        max_retries: Maximum retry attempts per order

    Returns:
        Dictionary mapping order IDs to processed orders
    """
```

**Good - Generic Type:**
```python
from typing import TypeVar, Generic

T = TypeVar('T')

class DataCache(Generic[T]):
    """Generic data cache supporting any hashable type.

    Args:
        max_size: Maximum cache entries
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._cache: dict[str, T] = {}
        self._max_size = max_size
```

**Bad - Old-Style Type Hints:**
```python
from typing import Union, Optional, List, Dict

def process_orders(
    orders: List[Order],  # Use list[Order]
    validator: Optional[Callable[[Order], bool]],  # Use | None
    max_retries: Union[int, None] = None,  # Use int | None
) -> Dict[str, Order]:  # Use dict[str, Order]
    pass
```

---

## Examples

Examples are crucial for understanding API usage. Include them liberally!

### Guidelines

1. **Use doctest format** (`>>>` prefix) for runnable examples
2. **Show realistic usage** not trivial cases
3. **Include expected output** when helpful
4. **Show error handling** for exception examples

### Examples

**Good - Realistic Example:**
```python
def backtest_strategy(
    strategy: TradingAlgorithm,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    capital_base: Decimal,
) -> BacktestResult:
    """Run a backtest for a trading strategy.

    Args:
        strategy: Trading algorithm instance
        start_date: Backtest start date
        end_date: Backtest end date
        capital_base: Starting capital

    Returns:
        Backtest result with performance metrics

    Example:
        >>> from rustybt import TradingAlgorithm
        >>> from decimal import Decimal
        >>> import pandas as pd
        >>>
        >>> class MyStrategy(TradingAlgorithm):
        ...     def initialize(self, context):
        ...         self.asset = self.symbol("AAPL")
        ...
        ...     def handle_data(self, context, data):
        ...         self.order_target_percent(self.asset, 0.5)
        >>>
        >>> result = backtest_strategy(
        ...     strategy=MyStrategy(),
        ...     start_date=pd.Timestamp("2023-01-01"),
        ...     end_date=pd.Timestamp("2023-12-31"),
        ...     capital_base=Decimal("100000")
        ... )
        >>> print(f"Total Return: {result.total_return:.2%}")
        Total Return: 15.43%
        >>> print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        Sharpe Ratio: 1.85
    """
```

**Good - Error Handling Example:**
```python
def get_price(self, asset: Asset, dt: pd.Timestamp) -> Decimal:
    """Get asset price at specific datetime.

    Args:
        asset: Asset to get price for
        dt: Datetime to get price at

    Returns:
        Price as Decimal

    Raises:
        NoDataError: If asset has no data at datetime

    Example:
        Normal usage:
        >>> portal = PolarsDataPortal.from_bundle("my_bundle")
        >>> asset = Asset(1)
        >>> price = portal.get_price(asset, pd.Timestamp("2024-01-15"))
        >>> print(price)
        Decimal('150.25')

        Error handling:
        >>> try:
        ...     price = portal.get_price(asset, pd.Timestamp("2020-01-01"))
        ... except NoDataError as e:
        ...     print(f"No data: {e}")
        No data: Asset 1 has no data on 2020-01-01
    """
```

---

## Common Patterns

### Async Functions

```python
async def fetch_live_data(
    symbols: list[str],
    adapter: BaseDataAdapter,
) -> pl.DataFrame:
    """Fetch live market data asynchronously.

    Args:
        symbols: List of ticker symbols
        adapter: Data adapter to use for fetching

    Returns:
        DataFrame with live OHLCV data

    Example:
        >>> import asyncio
        >>> from rustybt.data.adapters import YFinanceAdapter
        >>>
        >>> async def main():
        ...     adapter = YFinanceAdapter()
        ...     data = await fetch_live_data(["AAPL", "MSFT"], adapter)
        ...     print(data.head())
        >>>
        >>> asyncio.run(main())
    """
```

### Context Managers

```python
class DataConnection:
    """Database connection with automatic cleanup.

    Example:
        >>> with DataConnection("postgres://localhost/db") as conn:
        ...     data = conn.query("SELECT * FROM prices")
        ...     print(len(data))
        1000
    """

    def __enter__(self) -> DataConnection:
        """Enter context and establish connection.

        Returns:
            Self reference for context variable
        """

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context and close connection.

        Args:
            exc_type: Exception type if exception occurred
            exc_val: Exception value if exception occurred
            exc_tb: Exception traceback if exception occurred

        Returns:
            False to propagate exceptions
        """
```

### Generators

```python
def generate_trading_signals(
    prices: pl.DataFrame,
    window: int = 20,
) -> Iterator[Signal]:
    """Generate trading signals from price data.

    Yields signals one at a time for memory efficiency with large datasets.

    Args:
        prices: DataFrame with OHLCV data
        window: Lookback window for signal generation

    Yields:
        Signal objects containing entry/exit points

    Example:
        >>> prices = load_price_data("AAPL")
        >>> for signal in generate_trading_signals(prices, window=50):
        ...     if signal.action == "BUY":
        ...         print(f"Buy signal at {signal.price}")
    """
```

### Decorators

```python
def cached(ttl_seconds: int = 300):
    """Cache function results with time-to-live.

    Args:
        ttl_seconds: Cache lifetime in seconds

    Returns:
        Decorator function

    Example:
        >>> @cached(ttl_seconds=60)
        ... def expensive_calculation(x: int) -> int:
        ...     return x ** 2
        >>>
        >>> result = expensive_calculation(10)  # Calculates
        >>> result = expensive_calculation(10)  # Uses cache
    """
```

---

## Migration from NumPy Style

If you encounter NumPy-style docstrings, convert them to Google style.

### NumPy Style (Old)

```python
def calculate_returns(prices):
    """Calculate returns from price series.

    Parameters
    ----------
    prices : pd.Series
        Price series with datetime index

    Returns
    -------
    pd.Series
        Returns series (prices.pct_change())

    See Also
    --------
    calculate_log_returns : Calculate log returns instead

    Notes
    -----
    Uses simple returns: (P_t / P_{t-1}) - 1

    Examples
    --------
    >>> prices = pd.Series([100, 102, 101])
    >>> returns = calculate_returns(prices)
    """
```

### Google Style (New)

```python
def calculate_returns(prices: pd.Series) -> pd.Series:
    """Calculate returns from price series.

    Uses simple returns formula: (P_t / P_{t-1}) - 1

    Args:
        prices: Price series with datetime index

    Returns:
        Returns series (prices.pct_change())

    Example:
        >>> prices = pd.Series([100, 102, 101])
        >>> returns = calculate_returns(prices)
        >>> print(returns)
        0         NaN
        1    0.020000
        2   -0.009804

    See Also:
        calculate_log_returns: Calculate log returns instead
    """
```

### Key Differences

| NumPy Style | Google Style |
|-------------|--------------|
| `Parameters\n----------` | `Args:` |
| `Returns\n-------` | `Returns:` |
| `Raises\n------` | `Raises:` |
| `See Also\n--------` | `See Also:` (or omit) |
| `Notes\n-----` | Include in description or `Note:` |
| `Examples\n--------` | `Example:` (singular) |

### Conversion Tool

Use the `pyment` tool for automated conversion:

```bash
# Install pyment
pip install pyment

# Convert single file
pyment -w -o google rustybt/finance/slippage.py

# Convert entire directory
pyment -w -o google rustybt/finance/

# Preview changes without writing
pyment -o google rustybt/finance/slippage.py
```

---

## Docstring Quality Checklist

Use this checklist when writing or reviewing docstrings:

### Module-Level
- [ ] One-line summary present
- [ ] Detailed description of module purpose
- [ ] Key components listed
- [ ] At least one usage example

### Class-Level
- [ ] One-line summary present
- [ ] Detailed description of class purpose
- [ ] All public attributes documented
- [ ] At least one usage example
- [ ] Important notes (thread safety, etc.) included

### Function/Method-Level
- [ ] One-line summary present
- [ ] All parameters documented in Args
- [ ] Return value documented
- [ ] Exceptions documented in Raises
- [ ] At least one example for public APIs
- [ ] Type hints present for all parameters

### General
- [ ] Google style format followed
- [ ] Grammar and spelling correct
- [ ] Examples are realistic and runnable
- [ ] No outdated information
- [ ] Consistent terminology with rest of codebase

---

## Tools and Automation

### IDE Support

**VS Code:**
```json
{
  "python.analysis.typeCheckingMode": "strict",
  "autoDocstring.docstringFormat": "google",
  "autoDocstring.startOnNewLine": true,
  "autoDocstring.includeExtendedSummary": true
}
```

**PyCharm:**
- Settings → Tools → Python Integrated Tools → Docstring format → Google

### Linting

Add to `.pre-commit-config.yaml`:
```yaml
- repo: https://github.com/pycqa/pydocstyle
  rev: 6.3.0
  hooks:
    - id: pydocstyle
      args: ['--convention=google']
```

### Coverage Checking

```bash
# Check docstring coverage
pip install interrogate
interrogate -vv rustybt/ --fail-under=80

# Generate report
interrogate rustybt/ --generate-badge .
```

---

## References

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [Napoleon - Google Style Guide](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)
- [mkdocstrings Documentation](https://mkdocstrings.github.io/)

---

## Questions?

If you have questions about docstring style:

1. Check examples in modern modules (`rustybt/analytics/`, `rustybt/live/`)
2. Search this guide for similar patterns
3. Ask in GitHub Discussions
4. Reference the official Google Python Style Guide

---

**Remember:** Good documentation is as important as good code. Take the time to write clear, comprehensive docstrings that help users understand and use your code effectively.
