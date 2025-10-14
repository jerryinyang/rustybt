# Decimal Precision Configuration Guide

## Overview

RustyBT provides a flexible decimal precision configuration system that allows different asset classes (cryptocurrencies, equities, forex, futures) to use appropriate precision based on their specific requirements and data provider specifications.

## Why Decimal Precision Matters

Financial calculations require precise arithmetic to avoid rounding errors that accumulate over many operations. Python's `float` type uses binary floating-point representation, which can introduce subtle errors in decimal calculations:

```python
# Float precision issues
>>> 0.1 + 0.2
0.30000000000000004  # Not exactly 0.3!

# Decimal precision
>>> from decimal import Decimal
>>> Decimal("0.1") + Decimal("0.2")
Decimal('0.3')  # Exact!
```

RustyBT uses Python's `decimal` module throughout the financial calculation stack to ensure audit-compliant precision.

## Configuration Schema

### YAML Configuration

The decimal precision system is configured via YAML files with the following structure:

```yaml
# Global defaults
global_defaults:
  precision: 18              # Total significant digits
  rounding_mode: ROUND_HALF_EVEN  # Banker's rounding
  scale: 8                   # Decimal places for display

# Asset class-specific settings
asset_classes:
  crypto:
    precision: 18
    rounding_mode: ROUND_DOWN
    scale: 8
    rationale: "Cryptocurrencies require high precision for fractional shares"

  equity:
    precision: 18
    rounding_mode: ROUND_HALF_UP
    scale: 2
    rationale: "Equities trade in cents"

  # ... more asset classes
```

### Configuration Parameters

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `precision` | int | 0-18 | Total number of significant digits |
| `rounding_mode` | str | See below | Rounding algorithm to use |
| `scale` | int | 0-18 | Decimal places for display/formatting |

## Default Precision Presets

RustyBT provides sensible defaults for common asset classes:

### Cryptocurrency (crypto)
- **Precision:** 18 digits
- **Rounding Mode:** ROUND_DOWN
- **Scale:** 8 decimal places
- **Rationale:** Bitcoin uses Satoshi precision (0.00000001 BTC = 1 Satoshi). High precision ensures accurate calculations for fractional cryptocurrency holdings.

### Equities (equity)
- **Precision:** 18 digits
- **Rounding Mode:** ROUND_HALF_UP
- **Scale:** 2 decimal places
- **Rationale:** US stocks trade in cents ($42.50), but large positions require high precision for intermediate calculations.

### Forex (forex)
- **Precision:** 18 digits
- **Rounding Mode:** ROUND_HALF_EVEN
- **Scale:** 5 decimal places
- **Rationale:** Forex pairs require pip precision (0.00001 for most pairs, 0.001 for JPY pairs).

### Futures (future)
- **Precision:** 18 digits
- **Rounding Mode:** ROUND_HALF_UP
- **Scale:** 2 decimal places
- **Rationale:** Tick sizes vary by contract, but 2 decimals covers most cases.

### Index (index)
- **Precision:** 18 digits
- **Rounding Mode:** ROUND_HALF_EVEN
- **Scale:** 2 decimal places
- **Rationale:** Index values like S&P 500 typically use 2 decimals (4521.25).

## Rounding Modes

RustyBT supports all Python decimal rounding modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| `ROUND_HALF_EVEN` | Round to nearest even (Banker's rounding) | Default, minimizes bias |
| `ROUND_DOWN` | Round toward zero | Crypto exchanges (round quantities down) |
| `ROUND_HALF_UP` | Traditional rounding (0.5 → 1) | Equities, futures |
| `ROUND_UP` | Round away from zero | Conservative risk calculations |
| `ROUND_CEILING` | Round toward +∞ | Special cases |
| `ROUND_FLOOR` | Round toward -∞ | Special cases |
| `ROUND_05UP` | Round away if last digit is 0 or 5 | Specialized accounting |

### Rounding Mode Selection Guide

- **ROUND_HALF_EVEN** (Banker's Rounding): Best default choice. Over many operations, rounding 0.5 to the nearest even number minimizes cumulative bias.

- **ROUND_DOWN**: Use when the exchange or broker always rounds quantities down (common in crypto exchanges).

- **ROUND_HALF_UP**: Traditional rounding familiar to most users. Suitable for equities and futures.

- **ROUND_UP**: Use for conservative risk calculations where you want to round losses up and gains down.

## Usage Examples

### Basic Configuration Loading

```python
from rustybt.finance.decimal import DecimalConfig

# Get singleton instance (loads default config)
config = DecimalConfig.get_instance()

# Check precision for crypto
precision = config.get_precision("crypto")  # 18
rounding = config.get_rounding_mode("crypto")  # "ROUND_DOWN"
scale = config.get_scale("crypto")  # 8
```

### Loading Custom Configuration

```python
from rustybt.finance.decimal import DecimalConfig

config = DecimalConfig.get_instance()

# Load from YAML file
config.load_from_yaml("my_custom_config.yaml")

# Load from JSON file
config.load_from_json("config.json")

# Load from dictionary
custom_config = {
    "global_defaults": {
        "precision": 18,
        "rounding_mode": "ROUND_HALF_EVEN",
        "scale": 8
    },
    "asset_classes": {
        "crypto": {
            "precision": 18,
            "rounding_mode": "ROUND_DOWN",
            "scale": 8
        }
    }
}
config.load_from_dict(custom_config)
```

### Programmatic Configuration

```python
from rustybt.finance.decimal import DecimalConfig

config = DecimalConfig.get_instance()

# Set custom precision for a new asset class
config.set_precision(
    asset_class="option",
    precision=18,
    rounding_mode="ROUND_HALF_EVEN",
    scale=4
)
```

### Using Context Managers for Calculations

```python
from decimal import Decimal
from rustybt.finance.decimal import DecimalConfig

config = DecimalConfig.get_instance()

# Calculate with crypto precision
with config.with_precision("crypto") as ctx:
    btc_price = Decimal("42150.12345678")
    btc_amount = Decimal("0.00012345")

    # Calculation uses crypto precision (18 digits, ROUND_DOWN)
    total_value = btc_price * btc_amount
    print(f"Total: {total_value}")  # Precise to 8 decimals

# Calculate with equity precision
with config.with_precision("equity") as ctx:
    stock_price = Decimal("150.25")
    shares = Decimal("100")

    # Calculation uses equity precision (18 digits, ROUND_HALF_UP)
    total_value = stock_price * shares
    print(f"Total: ${total_value}")  # Result: $15025.00
```

### Thread-Safe Context Management

The precision system is thread-safe using Python's `decimal.localcontext()`:

```python
import threading
from decimal import Decimal
from rustybt.finance.decimal import DecimalConfig

config = DecimalConfig.get_instance()

def calculate_crypto_value():
    """Thread 1: Calculate crypto position."""
    with config.with_precision("crypto") as ctx:
        # This context is isolated to this thread
        value = Decimal("1.12345678") * Decimal("42000")
        return value

def calculate_equity_value():
    """Thread 2: Calculate equity position."""
    with config.with_precision("equity") as ctx:
        # Different context, isolated from Thread 1
        value = Decimal("150.25") * Decimal("100")
        return value

# Spawn threads - each has isolated context
thread1 = threading.Thread(target=calculate_crypto_value)
thread2 = threading.Thread(target=calculate_equity_value)

thread1.start()
thread2.start()
thread1.join()
thread2.join()
```

## Advanced Configuration

### Creating Custom Asset Classes

```yaml
# custom_config.yaml
asset_classes:
  # Custom asset class for options
  option:
    precision: 18
    rounding_mode: ROUND_HALF_EVEN
    scale: 4
    rationale: "Options require 4 decimal precision for Greeks calculations"

  # Custom asset class for bonds
  bond:
    precision: 18
    rounding_mode: ROUND_HALF_UP
    scale: 6
    rationale: "Bonds require high precision for yield calculations"
```

### Configuration File Search Path

RustyBT searches for configuration files in the following order:

1. User-provided file path (via `load_from_yaml()` or `load_from_json()`)
2. Project-level config: `./decimal_config.yaml`
3. Package default: `rustybt/finance/decimal/default_config.yaml`

### Validation and Error Handling

The configuration system validates all inputs:

```python
from rustybt.finance.decimal import (
    DecimalConfig,
    InvalidPrecisionError,
    InvalidRoundingModeError,
    InvalidAssetClassError
)

config = DecimalConfig.get_instance()

# Invalid precision (out of range 0-18)
try:
    config.set_precision("crypto", 50, "ROUND_HALF_EVEN")
except InvalidPrecisionError as e:
    print(f"Error: {e}")  # Precision must be 0-18

# Invalid rounding mode
try:
    config.set_precision("crypto", 8, "ROUND_INVALID")
except InvalidRoundingModeError as e:
    print(f"Error: {e}")  # Invalid rounding mode

# Unknown asset class
try:
    precision = config.get_precision("unknown_asset")
except InvalidAssetClassError as e:
    print(f"Error: {e}")  # Unknown asset class
```

## Best Practices

### 1. Use High Precision for Intermediate Calculations

Always use precision 18 for intermediate calculations, even if final display only needs 2 decimals:

```python
from decimal import Decimal
from rustybt.finance.decimal import DecimalConfig

config = DecimalConfig.get_instance()

# GOOD: High precision for calculation, format for display
with config.with_precision("equity") as ctx:
    price = Decimal("150.256789")  # High precision input
    shares = Decimal("1000")
    total = price * shares  # Precise calculation

    # Format for display with 2 decimals
    scale = config.get_scale("equity")
    display_value = round(total, scale)
    print(f"${display_value}")  # $150256.79

# BAD: Low precision loses accuracy
price_low_prec = Decimal("150.26")  # Truncated input
total_low_prec = price_low_prec * Decimal("1000")
# Result: $150260.00 (lost precision!)
```

### 2. Choose Rounding Mode Based on Use Case

- **Calculations:** Use `ROUND_HALF_EVEN` (minimizes bias)
- **Order Quantities (Crypto):** Use `ROUND_DOWN` (matches exchange behavior)
- **Risk Metrics:** Use `ROUND_UP` (conservative)
- **Display:** Use asset class default

### 3. Always Use String Construction for Decimal

```python
from decimal import Decimal

# GOOD: String construction (exact)
price = Decimal("42.50")

# BAD: Float construction (introduces rounding error)
price = Decimal(42.50)  # May not be exactly 42.50!
```

### 4. Validate Configuration on Startup

```python
from rustybt.finance.decimal import DecimalConfig

config = DecimalConfig.get_instance()

# Load custom config
config.load_from_yaml("my_config.yaml")

# Validate configuration
try:
    config.validate_config()
    print("Configuration valid ✓")
except Exception as e:
    print(f"Configuration invalid: {e}")
    exit(1)
```

## Performance Considerations

### Precision vs Performance

Higher precision incurs computational cost. RustyBT defaults to precision 18 as a balance:

- **Precision 28** (Python Decimal default): Maximum accuracy, ~50% slower
- **Precision 18** (RustyBT default): Excellent accuracy, good performance
- **Precision 8**: Faster, but may lose accuracy in intermediate calculations

For most use cases, precision 18 provides sufficient accuracy with acceptable performance.

### Optimization Tips

1. **Reuse contexts:** Use `with_precision()` for blocks of calculations, not individual operations
2. **Batch operations:** Process multiple calculations within a single context
3. **Profile first:** Only reduce precision if profiling shows it's a bottleneck

## Troubleshooting

### Common Issues

**Problem:** "Unknown asset class" error

**Solution:** Check that asset class exists in configuration:

```python
config = DecimalConfig.get_instance()
print(config._config["asset_classes"].keys())  # List available classes
```

**Problem:** Unexpected rounding behavior

**Solution:** Verify rounding mode for asset class:

```python
config = DecimalConfig.get_instance()
mode = config.get_rounding_mode("crypto")
print(f"Crypto rounding mode: {mode}")
```

**Problem:** Thread context leakage

**Solution:** Always use `with_precision()` context manager, never modify global context directly.

## Summary

- RustyBT uses `decimal.Decimal` for all financial calculations
- Precision is configurable per asset class (default: 18 digits)
- Rounding modes support different calculation requirements
- Thread-safe context management via `with_precision()`
- Defaults provided for crypto, equity, forex, futures, index
- Validation ensures precision (0-18) and rounding modes are valid

For more information, see:
- [Python Decimal Module Documentation](https://docs.python.org/3/library/decimal.html)
- [Examples & Tutorials](../examples/README.md)
