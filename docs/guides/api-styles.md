# Strategy API Styles Guide

RustyBT supports two API styles for writing trading strategies: **Functional API** and **Class-Based API**. This guide explains when and how to use each.

---

## Overview

| Feature | Functional API | Class-Based API |
|---------|---------------|-----------------|
| **Primary Use** | Python notebooks, `run_algorithm()` | CLI execution (`rustybt run -f`) |
| **Structure** | Top-level functions | TradingAlgorithm subclass |
| **Method Signatures** | `def initialize(context)` | `def initialize(self)` |
| | `def handle_data(context, data)` | `def handle_data(self, context, data)` |
| **Helper Methods** | Module-level functions | Class methods |
| **State Storage** | `context.` attributes | `self.` attributes |
| **Supported Since** | v1.0 | v2.0+ (commit 42b8fe7) |

---

## Functional API

### When to Use
- ✅ Python notebooks (Jupyter)
- ✅ Calling `run_algorithm()` from Python code
- ✅ Quick prototyping and testing
- ✅ Simple strategies without helper methods

### Structure

```python
from rustybt.api import order_target, record, symbol

def initialize(context):
    """
    Called once at the start of the backtest.

    Parameters
    ----------
    context : TradingAlgorithm
        The algorithm instance. Store state as context.attribute_name
    """
    context.asset = symbol('AAPL')
    context.i = 0

def handle_data(context, data):
    """
    Called on every trading period (bar).

    Parameters
    ----------
    context : TradingAlgorithm
        The algorithm instance with your stored state
    data : BarData
        Market data for current and historical bars
    """
    context.i += 1
    # Your trading logic here

def before_trading_start(context, data):
    """
    Called before market open each day (optional).

    Parameters
    ----------
    context : TradingAlgorithm
    data : BarData
    """
    pass

def analyze(context, perf):
    """
    Called once at end of backtest (optional).

    Parameters
    ----------
    context : TradingAlgorithm
    perf : pd.DataFrame
        Performance results
    """
    pass
```

### Running Functional API

**With `run_algorithm()`:**
```python
from rustybt import run_algorithm
import pandas as pd

results = run_algorithm(
    start=pd.Timestamp('2020-01-01', tz='utc'),
    end=pd.Timestamp('2020-12-31', tz='utc'),
    initialize=initialize,        # Pass function objects
    handle_data=handle_data,       # NOT strings
    before_trading_start=before_trading_start,  # Optional
    analyze=analyze,               # Optional
    capital_base=100000,
    bundle='quandl'
)
```

**With CLI (functional format):**
```bash
# File: my_strategy.py with top-level functions
rustybt run -f my_strategy.py -b quandl --start 2020-01-01 --end 2020-12-31 --capital-base 100000
```

---

## Class-Based API

### When to Use
- ✅ CLI execution (`rustybt run -f`)
- ✅ Complex strategies with helper methods
- ✅ Organizing code into reusable strategy classes
- ✅ Multiple related strategies in one module

### Structure

```python
from rustybt import TradingAlgorithm
from rustybt.api import order_target, record, symbol

class MyStrategy(TradingAlgorithm):
    """
    Class-based strategy example.

    IMPORTANT: Method signatures differ from functional API!
    - initialize(self) instead of initialize(context)
    - handle_data(self, context, data) instead of handle_data(context, data)
    """

    def initialize(self):
        """
        Called once at the start of the backtest.

        NO PARAMETERS (just self).
        Store state as self.attribute_name
        """
        self.asset = symbol('AAPL')
        self.i = 0

    def handle_data(self, context, data):
        """
        Called on every trading period (bar).

        Parameters
        ----------
        self : MyStrategy
            The strategy instance
        context : TradingAlgorithm
            The algorithm context (usually same as self)
        data : BarData
            Market data for current and historical bars
        """
        self.i += 1
        # Your trading logic here

    def before_trading_start(self, context, data):
        """
        Called before market open each day (optional).

        Parameters
        ----------
        self : MyStrategy
        context : TradingAlgorithm
        data : BarData
        """
        pass

    def analyze(self, context, perf):
        """
        Called once at end of backtest (optional).

        Parameters
        ----------
        self : MyStrategy
        context : TradingAlgorithm
        perf : pd.DataFrame
            Performance results
        """
        pass

    # Helper methods (class-based only!)
    def calculate_signal(self, data):
        """Helper methods are natural with class-based API."""
        short_ma = data.history(self.asset, 'price', 50, '1d').mean()
        long_ma = data.history(self.asset, 'price', 200, '1d').mean()
        return short_ma > long_ma
```

### Running Class-Based API

**With CLI:**
```bash
# File: my_strategy.py with MyStrategy class
rustybt run -f my_strategy.py -b quandl --start 2020-01-01 --end 2020-12-31 --capital-base 100000
```

**Framework automatically detects the TradingAlgorithm subclass!**

**NOT supported with `run_algorithm()`:**
```python
# ❌ WRONG - run_algorithm() requires functional API
results = run_algorithm(
    strategy_class=MyStrategy,  # This parameter doesn't exist!
    start=pd.Timestamp('2020-01-01', tz='utc'),
    end=pd.Timestamp('2020-12-31', tz='utc'),
    capital_base=100000,
)
```

---

## Key Differences

### Method Signatures

| Method | Functional API | Class-Based API |
|--------|---------------|-----------------|
| `initialize` | `def initialize(context)` | `def initialize(self)` |
| `handle_data` | `def handle_data(context, data)` | `def handle_data(self, context, data)` |
| `before_trading_start` | `def before_trading_start(context, data)` | `def before_trading_start(self, context, data)` |
| `analyze` | `def analyze(context, perf)` | `def analyze(self, context, perf)` |

### State Storage

**Functional API:**
```python
def initialize(context):
    context.my_var = 100  # Store on context

def handle_data(context, data):
    print(context.my_var)  # Access from context
```

**Class-Based API:**
```python
class MyStrategy(TradingAlgorithm):
    def initialize(self):
        self.my_var = 100  # Store on self

    def handle_data(self, context, data):
        print(self.my_var)  # Access from self
        # Note: context == self in class-based API
```

### Helper Methods

**Functional API** - Use module-level functions:
```python
def calculate_signal(asset, data):
    """Module-level helper function."""
    return data.history(asset, 'price', 50, '1d').mean()

def handle_data(context, data):
    signal = calculate_signal(context.asset, data)
```

**Class-Based API** - Use class methods:
```python
class MyStrategy(TradingAlgorithm):
    def calculate_signal(self, data):
        """Class method - can access self.asset."""
        return data.history(self.asset, 'price', 50, '1d').mean()

    def handle_data(self, context, data):
        signal = self.calculate_signal(data)
```

---

## Execution Methods Compatibility Matrix

| Execution Method | Functional API | Class-Based API |
|-----------------|---------------|-----------------|
| `run_algorithm()` | ✅ Supported | ❌ Not supported |
| `rustybt run -f` (CLI) | ✅ Supported | ✅ Supported |
| Jupyter notebooks | ✅ Preferred | ⚠️ Use run_algorithm() instead |

---

## Migration Guide

### Converting Functional → Class-Based

```python
# BEFORE (Functional)
def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    price = data.current(context.asset, 'price')

# AFTER (Class-Based)
class MyStrategy(TradingAlgorithm):
    def initialize(self):              # No context parameter
        self.asset = symbol('AAPL')    # self instead of context

    def handle_data(self, context, data):  # Add self, keep context and data
        price = data.current(self.asset, 'price')  # self instead of context
```

### Converting Class-Based → Functional

```python
# BEFORE (Class-Based)
class MyStrategy(TradingAlgorithm):
    def initialize(self):
        self.asset = symbol('AAPL')

    def handle_data(self, context, data):
        price = data.current(self.asset, 'price')

# AFTER (Functional)
def initialize(context):                  # Add context parameter
    context.asset = symbol('AAPL')        # context instead of self

def handle_data(context, data):           # Remove self, keep context and data
    price = data.current(context.asset, 'price')  # context instead of self
```

---

## Best Practices

### Functional API Best Practices
- ✅ Use for notebooks and quick prototypes
- ✅ Keep helper functions in same module
- ✅ Pass function objects to `run_algorithm()`, not strings
- ✅ Store all state on `context` object
- ⚠️ Avoid global variables

### Class-Based API Best Practices
- ✅ Use for complex strategies with multiple helper methods
- ✅ Organize related strategies as separate classes in one module
- ✅ Store all state as instance attributes (`self.`)
- ✅ Use class methods for helper functions
- ⚠️ Remember: `context` and `self` refer to the same object

---

## Common Errors

### Error: "No strategy format detected"

**Cause:** CLI execution found neither class nor functions.

**Solution:** Ensure you have EITHER:
- Top-level `initialize()` and `handle_data()` functions (functional)
- A `TradingAlgorithm` subclass with those methods (class-based)

### Error: "TypeError: initialize() takes 0 positional arguments but 1 was given"

**Cause:** Class method has wrong signature.

**Wrong:**
```python
class MyStrategy(TradingAlgorithm):
    def initialize(context):  # ❌ Missing self
        pass
```

**Correct:**
```python
class MyStrategy(TradingAlgorithm):
    def initialize(self):  # ✅ Correct
        pass
```

### Error: "AttributeError: 'TradingAlgorithm' object has no attribute..."

**Cause:** Trying to access `context.` attribute that was stored on `self.`

**Solution:** In class-based API, use `self.` consistently:
```python
def initialize(self):
    self.my_var = 100  # Store on self

def handle_data(self, context, data):
    print(self.my_var)  # Access from self (not context.my_var)
```

---

## Examples

See also:
- [Quickstart Guide](../getting-started/quickstart.md) - Functional API example
- [Examples Directory](../examples/) - Both API styles
- [User Guide](../user-guide/) - Advanced usage patterns

---

## Version History

- **v2.0+** (commit 42b8fe7): Class-based API CLI support added
- **v1.0**: Functional API introduced

---

**Questions?** See [FAQ](../faq.md) or [API Reference](../api/README.md)
