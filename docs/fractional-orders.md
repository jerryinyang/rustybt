# Fractional Orders

RustyBT supports fractional order amounts for assets that allow them, such as cryptocurrencies. This guide explains how to configure and use this feature.

## Overview

Traditional stock trading requires whole number of shares (e.g., you can buy 10 shares of AAPL, but not 10.5 shares). However, cryptocurrency exchanges allow fractional amounts (e.g., you can buy 0.5 BTC).

RustyBT automatically handles this distinction based on the asset's exchange, but also provides configuration options for fine-grained control.

## Configuration Modes

The `fractional_order_mode` parameter controls how order amounts are handled:

### AUTO (Default - Recommended)

Automatically detects the asset type based on its exchange:
- **Crypto exchanges** (Binance, Coinbase, Kraken, etc.): Preserves fractional amounts
- **Traditional exchanges** (NYSE, NASDAQ, etc.): Rounds to integer share counts

```python
from rustybt import run_algorithm

results = run_algorithm(
    start=start_date,
    end=end_date,
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000,
    bundle="binance-spot-1d",
    fractional_order_mode="auto",  # Default - can be omitted
)
```

### ALWAYS

Forces all assets to preserve fractional amounts, regardless of exchange:

```python
from rustybt import run_algorithm
from rustybt.finance.asset_config import FractionalOrderMode

results = run_algorithm(
    start=start_date,
    end=end_date,
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000,
    bundle="my-bundle",
    fractional_order_mode=FractionalOrderMode.ALWAYS,  # or "always"
)
```

**Use case**: Backtesting strategies that assume fractional shares are available for all assets.

### NEVER

Forces all assets to round to integer share counts:

```python
from rustybt import run_algorithm

results = run_algorithm(
    start=start_date,
    end=end_date,
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000,
    bundle="binance-spot-1d",
    fractional_order_mode="never",
)
```

**Use case**: Testing how a crypto strategy would perform with integer-only positions.

## Examples

### Example 1: Crypto Trading with AUTO Mode (Default)

```python
import pandas as pd
from rustybt import run_algorithm
from rustybt.api import order, symbol

def initialize(context):
    context.btc = symbol('BTC/USDT')
    context.eth = symbol('ETH/USDT')

def handle_data(context, data):
    # Calculate position size based on risk (1% of portfolio)
    risk_per_trade = 0.01
    portfolio_value = context.portfolio.portfolio_value

    # For BTC at $50,000, this might be 0.2 BTC
    btc_amount = (risk_per_trade * portfolio_value) / data.current(context.btc, 'price')

    # Order fractional amounts - this works!
    order(context.btc, btc_amount)  # e.g., 0.334827 BTC

results = run_algorithm(
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000,
    bundle="binance-spot-1d",
    # fractional_order_mode="auto" is default
)
```

### Example 2: Force Integer Orders for All Assets

```python
from rustybt.finance.asset_config import FractionalOrderMode

# Same strategy, but force integer amounts
results = run_algorithm(
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000,
    bundle="binance-spot-1d",
    fractional_order_mode=FractionalOrderMode.NEVER,
)

# Now order(context.btc, 0.334827) would become 0 and fail
# You'd need to order at least 1 BTC: order(context.btc, 1)
```

### Example 3: Using String Values

```python
# All three formats are equivalent:

# Option 1: String value
fractional_order_mode="auto"

# Option 2: Enum
from rustybt.finance.asset_config import FractionalOrderMode
fractional_order_mode=FractionalOrderMode.AUTO

# Option 3: Enum value
fractional_order_mode=FractionalOrderMode.AUTO.value
```

## Supported Crypto Exchanges

The AUTO mode recognizes the following cryptocurrency exchanges:

- Binance
- Coinbase
- Kraken
- OKEx
- Huobi
- Bybit
- KuCoin
- Gate.io
- Bitfinex
- Gemini
- Crypto.com
- Bitstamp
- Bittrex
- Poloniex

## Minimum Order Sizes

### Fractional Mode (AUTO or ALWAYS for crypto)
- Minimum amount: `1e-8` (0.00000001)
- Example: `0.000001 BTC` is valid

### Integer Mode (AUTO for equities or NEVER)
- Minimum amount: `1` share
- Example: Must order at least `1` share

## Technical Details

### How It Works

1. **Order Placement** (`algorithm.py:round_order`)
   - Checks the `fractional_order_mode` setting
   - For AUTO: Detects if asset is from a crypto exchange
   - Preserves fractional amounts or rounds to integer accordingly

2. **Transaction Creation** (`transaction.py:create_transaction`)
   - Validates minimum amount based on mode
   - Creates transaction with appropriate precision

3. **Near-Integer Rounding**
   - Values within 0.0001 of an integer are rounded
   - Examples: `0.9999` → `1.0`, `5.0001` → `5.0`
   - Prevents floating-point precision issues

### Exchange Detection

Assets are identified as crypto by checking the `exchange_info` attribute:

```python
from rustybt.finance.asset_config import is_crypto_exchange

# Automatic detection
is_crypto = is_crypto_exchange(asset)  # True for binance, coinbase, etc.
```

## Migration Guide

### Before (rustybt < v1.0)

BTC fractional orders would fail:

```python
# This would fail with "Transaction magnitude must be at least 1"
order(btc_asset, 0.5)  # 0.5 rounded to 0, then rejected
```

### After (rustybt >= v1.0)

BTC fractional orders work automatically:

```python
# This works automatically with AUTO mode (default)
order(btc_asset, 0.5)  # 0.5 BTC order placed successfully
```

No code changes required - existing strategies will work correctly with the new AUTO mode default.

## Best Practices

1. **Use AUTO mode** (default) for most strategies
   - Automatically handles crypto vs equity differences
   - No manual configuration needed

2. **Use ALWAYS mode** for research/backtesting
   - When exploring strategies that assume fractional shares
   - When comparing against platforms that support fractional equities

3. **Use NEVER mode** for validation
   - Testing how crypto strategies perform with integer constraints
   - Ensuring compatibility with integer-only exchanges

4. **Position Sizing**
   - For crypto: Use dollar-based position sizing, let the system calculate fractional amounts
   - For equities: Consider rounding effects in your risk calculations

## Troubleshooting

### Error: "Transaction magnitude must be at least 1"

**Cause**: Trying to order fractional amounts with NEVER mode or for equities in AUTO mode.

**Solution**:
- Check your `fractional_order_mode` setting
- Ensure you're ordering at least 1 share for equities
- For crypto, verify the asset exchange is recognized

### BTC Orders Not Executing

**Cause**: Order amounts being rounded to 0.

**Solution**:
- Verify you're using AUTO or ALWAYS mode
- Check that your bundle uses a recognized crypto exchange
- Increase position size to ensure amount > 1e-8

### Position Size Calculation

For fractional assets, always calculate based on dollar value:

```python
# Good: Dollar-based calculation
target_value = 10000  # $10,000 position
amount = target_value / current_price

# Avoid: Hardcoded fractional amounts
amount = 0.5  # May not achieve desired $ value
```

## API Reference

### FractionalOrderMode

```python
from rustybt.finance.asset_config import FractionalOrderMode

class FractionalOrderMode(Enum):
    AUTO = "auto"      # Auto-detect based on exchange (default)
    ALWAYS = "always"  # Always preserve fractional amounts
    NEVER = "never"    # Always round to integers
```

### Helper Functions

```python
from rustybt.finance.asset_config import (
    is_crypto_exchange,
    should_use_fractional_orders,
)

# Check if an asset is from a crypto exchange
is_crypto_exchange(asset)  # Returns: bool

# Determine if fractional orders should be used
should_use_fractional_orders(asset, mode)  # Returns: bool
```

## See Also

- [Order Types Documentation](api/order-types.md)
- [Order Management API](api/order-management/README.md)
- [Data Ingestion Guide](guides/data-ingestion.md)
