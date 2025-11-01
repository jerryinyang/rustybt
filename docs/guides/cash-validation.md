# Cash Validation & Margin Management

**Status**: ✅ Available (v0.x.x+)
**Applies to**: Backtesting and Paper Trading
**Default**: Enabled with graceful rejection

---

## Overview

RustyBT's cash validation system ensures your backtests accurately simulate real trading conditions by preventing orders that would exceed available capital. This critical feature validates cash availability at **two stages**: when orders are placed and when they execute.

---

## Why Cash Validation Matters

### The Problem

Without cash validation, backtests can produce misleading results by executing impossible trades:

```python
# Portfolio: $10,000 cash
# Without validation (❌ INVALID):

order(AAPL, 200, LimitOrder(100))  # Needs $20,000
# ❌ Backtest allows this, goes to -$10,000 cash
# ✅ Real broker would reject immediately
```

**Result**: Your backtest shows performance from trades that could never happen in live trading.

### The Solution

Cash validation matches real broker behavior:

```python
# Portfolio: $10,000 cash
# With validation (✅ CORRECT):

order_id = order(AAPL, 200, LimitOrder(100))  # Needs $20,000
# order_id = None (order rejected)
# Warning logged: "Insufficient cash for order"
# Backtest continues normally
```

---

## How It Works

### Dual-Stage Validation

RustyBT validates cash at **two critical points**:

#### 1. Order Placement (Prevention)

When you call `order()`, the system:

1. Estimates the order cost (shares × price + commission)
2. Calculates reserved cash from pending orders
3. Checks if `available_cash = total_cash - reserved_cash` is sufficient
4. Rejects/warns/raises based on validation mode

```python
# Day 1: Two orders placed
order(AAPL, 50, LimitOrder(100))  # $5,000 → ACCEPTED
# Reserved: $5,000, Available: $5,000

order(MSFT, 60, LimitOrder(100))  # $6,000 → REJECTED
# Needs $6,000 but only $5,000 available
```

#### 2. Order Execution (Protection)

When orders fill via `get_transactions()`, the system:

1. Calculates actual transaction cost (filled amount × execution price + commission)
2. Checks current cash balance
3. Rejects fills if cash insufficient (order stays open)

```python
# Day 2: Order 1 attempts to fill
# If cash = $5,000: ✅ Fill succeeds
# If cash = $4,000 (due to fees): ❌ Fill rejected, order stays open
```

**Why both stages?**

- Placement: Prevents over-ordering
- Execution: Protects against cash changes (commissions, dividends, other fills)

---

## Validation Modes

Configure how the system responds to insufficient cash:

### `"reject"` Mode (Default - Recommended)

**Behavior**: Gracefully rejects orders/fills, logs warnings, backtest continues

**Use Case**: Production backtests - matches real broker behavior

```python
from rustybt import run_algorithm

def initialize(context):
    # Default mode - no configuration needed
    pass

# Or explicitly:
from rustybt.finance.blotter import SimulationBlotter

blotter = SimulationBlotter(cash_validation_mode="reject")
```

**What happens:**
- Insufficient cash at placement → Returns `None`, logs warning
- Insufficient cash at execution → Skips fill, order stays open, logs warning
- Backtest continues normally

### `"warn"` Mode (Backward Compatible)

**Behavior**: Logs warnings but allows orders/fills anyway

**Use Case**: Migrating existing strategies, debugging

```python
def initialize(context):
    context.set_cash_validation_mode("warn")
```

**What happens:**
- Insufficient cash at placement → Creates order, logs warning
- Insufficient cash at execution → Executes fill, logs warning
- May result in negative cash (like old behavior)

### `"strict"` Mode (Debugging)

**Behavior**: Raises `InsufficientFundsError`, crashes backtest

**Use Case**: Development, catching cash issues immediately

```python
def initialize(context):
    context.set_cash_validation_mode("strict")
```

**What happens:**
- Insufficient cash at placement → Raises exception
- Insufficient cash at execution → Raises exception
- Backtest stops with error details

### Comparison Table

| Mode | Order Placement | Order Execution | Backtest Continues | Use Case |
|------|----------------|-----------------|-------------------|----------|
| `"reject"` | Returns `None` | Skips fill | ✅ Yes | **Production** |
| `"warn"` | Creates order | Executes fill | ✅ Yes | Migration |
| `"strict"` | Raises exception | Raises exception | ❌ No | Debugging |

---

## Configuration

### Global Configuration

Set validation mode for entire algorithm:

```python
from rustybt import run_algorithm

def initialize(context):
    # Set mode globally
    context.set_cash_validation_mode("reject")  # or "warn" or "strict"

    # Check current mode
    mode = context.blotter.cash_validation_mode
    print(f"Cash validation mode: {mode}")
```

### Disable Validation (Not Recommended)

```python
def initialize(context):
    # Disable cash validation entirely
    context.blotter.enable_cash_validation = False
```

⚠️ **Warning**: Disabling validation makes backtests unrealistic. Only use for testing or comparing with legacy results.

---

## Reserved Cash Tracking

The system tracks cash reserved for pending orders:

```python
# Portfolio: $10,000 cash

# Order 1: 50 shares @ $100 = $5,000
order_id_1 = order(AAPL, 50, LimitOrder(100))
# Reserved: $5,000
# Available: $5,000

# Order 2: 60 shares @ $100 = $6,000
order_id_2 = order(MSFT, 60, LimitOrder(100))
# Needs: $6,000
# Available: $5,000
# ❌ REJECTED

# Order 3: 40 shares @ $100 = $4,000
order_id_3 = order(GOOGL, 40, LimitOrder(100))
# Needs: $4,000
# Available: $5,000
# ✅ ACCEPTED
```

**Key Points:**
- Only **buy orders** reserve cash (sells don't)
- Reserved cash is released when orders fill or cancel
- Calculation includes estimated commissions

---

## Common Scenarios

### Scenario 1: Multiple Orders Same Bar

```python
def handle_data(context, data):
    # Portfolio: $100,000

    # Place 10 orders for different assets
    for asset in context.universe:
        order(asset, 100, LimitOrder(price))

    # System automatically:
    # 1. Tracks cumulative reserved cash
    # 2. Rejects orders once cash exhausted
    # 3. Ensures total orders ≤ available cash
```

### Scenario 2: Order Fills Over Multiple Bars

```python
# Day 1: Order placed
order_id = order(AAPL, 1000, LimitOrder(100))
# Reserved: $100,000

# Day 2: Partial fill (500 shares)
# Cash used: $50,000
# Reserved reduced: $50,000

# Day 3: Remaining fill (500 shares)
# Cash validation checks: "Do I have $50,000?"
# If yes: ✅ Fill executes
# If no: ❌ Fill rejected, order stays open
```

### Scenario 3: Cash Changes Between Placement and Execution

```python
# Day 1:
# Cash: $10,000
# Order placed: 100 shares @ $100 = $10,000

# Day 2 (before fill):
# Dividend received: +$500 → Cash: $10,500
# Commission charged: -$600 → Cash: $9,900
# Order tries to fill: Needs $10,000
# ❌ Execution rejected (only $9,900 available)
# Order remains open for next bar
```

### Scenario 4: Handling Rejections Gracefully

```python
def handle_data(context, data):
    # Place order
    order_id = order(AAPL, shares, LimitOrder(price))

    if order_id is None:
        # Order was rejected - handle gracefully
        context.log.warning(f"Order rejected for {AAPL.symbol}")

        # Try smaller position
        reduced_shares = shares // 2
        order_id = order(AAPL, reduced_shares, LimitOrder(price))
```

---

## Best Practices

### 1. Check Order Status

```python
def handle_data(context, data):
    order_id = order(asset, amount, style)

    if order_id is None:
        # Order rejected - insufficient cash
        handle_rejection(asset)
    else:
        # Order accepted - track it
        context.pending_orders[asset] = order_id
```

### 2. Position Sizing with Cash Constraints

```python
def calculate_position_size(context, asset, target_percent):
    # Calculate ideal position value
    target_value = context.portfolio.portfolio_value * target_percent

    # Get available cash (accounts for reserved cash automatically)
    available = context.portfolio.cash

    # Use lesser of target and available
    position_value = min(target_value, available * 0.95)  # 5% buffer

    # Calculate shares
    price = data.current(asset, 'price')
    shares = position_value / price

    return shares
```

### 3. Monitor Cash Usage

```python
def handle_data(context, data):
    # Check cash metrics
    total_cash = context.portfolio.cash
    reserved = context.blotter._calculate_reserved_cash()
    available = total_cash - reserved

    context.record(
        cash_total=total_cash,
        cash_reserved=reserved,
        cash_available=available,
        cash_utilization=reserved / total_cash if total_cash > 0 else 0
    )
```

### 4. Use "reject" Mode in Production

```python
# ✅ RECOMMENDED: Graceful rejection
def initialize(context):
    # Default mode - no config needed
    pass

# ❌ NOT RECOMMENDED: Strict mode in production
def initialize(context):
    context.set_cash_validation_mode("strict")  # Will crash backtest
```

---

## Troubleshooting

### Issue: "Order rejected - insufficient cash"

**Cause**: Not enough available cash for the order

**Solutions**:

1. **Reduce position sizes**:
   ```python
   # Instead of fixed shares
   order(asset, 100, LimitOrder(price))

   # Use percentage of available cash
   available = context.portfolio.cash - reserved_cash
   shares = (available * 0.10) / price  # 10% of available
   order(asset, shares, LimitOrder(price))
   ```

2. **Limit concurrent orders**:
   ```python
   # Track number of open orders
   if len(context.get_open_orders()) < context.max_open_orders:
       order(asset, shares, LimitOrder(price))
   ```

3. **Check before ordering**:
   ```python
   estimated_cost = shares * price * 1.001  # +0.1% for commission
   if estimated_cost <= context.portfolio.cash:
       order(asset, shares, LimitOrder(price))
   ```

### Issue: "Order fill rejected at execution"

**Cause**: Cash was sufficient at placement but insufficient at execution

**Solutions**:

1. **Reserve extra buffer**:
   ```python
   # Leave 5-10% cash buffer
   max_position = context.portfolio.cash * 0.90
   ```

2. **Cancel stale orders**:
   ```python
   # Cancel orders older than N days
   for asset, order_id in context.get_open_orders().items():
       order = get_order(order_id)
       if (context.get_datetime() - order.created).days > 5:
           cancel_order(order_id)
   ```

### Issue: Backtest crashes with InsufficientFundsError

**Cause**: Running in "strict" mode

**Solution**: Switch to "reject" mode

```python
def initialize(context):
    context.set_cash_validation_mode("reject")  # Graceful rejection
```

---

## Migration Guide

### From Legacy Strategies (No Validation)

**Step 1**: Run in "warn" mode

```python
def initialize(context):
    context.set_cash_validation_mode("warn")
```

**Step 2**: Review warnings in backtest output

```
WARNING - Order placed with insufficient cash: need $50,000.00,
have $45,000.00 available
```

**Step 3**: Fix cash management issues

- Reduce position sizes
- Limit concurrent orders
- Add cash availability checks

**Step 4**: Switch to "reject" mode

```python
def initialize(context):
    context.set_cash_validation_mode("reject")  # or remove line (default)
```

**Step 5**: Verify backtest still works as expected

### Comparison: Before vs After

**Before (Legacy)**:
```python
# No validation - could go negative
order(AAPL, 1000, LimitOrder(100))  # $100,000 needed
# Works even with only $50,000 cash
# Backtest shows -$50,000 cash
```

**After (With Validation)**:
```python
# Default "reject" mode
order_id = order(AAPL, 1000, LimitOrder(100))  # $100,000 needed
# order_id = None (rejected)
# Warning logged
# Backtest continues normally
```

---

## API Reference

### Check Validation Mode

```python
# Get current mode
mode = context.blotter.cash_validation_mode  # "reject", "warn", or "strict"

# Check if validation enabled
enabled = context.blotter.enable_cash_validation  # True/False
```

### Set Validation Mode

```python
# In initialize()
context.set_cash_validation_mode("reject")  # or "warn" or "strict"

# Directly on blotter
context.blotter.cash_validation_mode = "warn"
```

### Calculate Available Cash

```python
# Total cash
total = context.portfolio.cash

# Reserved for pending orders
reserved = context.blotter._calculate_reserved_cash()

# Available for new orders
available = total - reserved
```

### Handle Rejected Orders

```python
order_id = order(asset, amount, style)

if order_id is None:
    # Order was rejected
    print(f"Order rejected for {asset.symbol}")
else:
    # Order accepted
    print(f"Order placed: {order_id}")
```

---

## Performance Impact

Cash validation adds minimal overhead:

- **Order Placement**: ~0.1ms per order (reserved cash calculation)
- **Order Execution**: ~0.05ms per fill (cash check)
- **Total Impact**: <1% increase in backtest time for typical strategies

**Benchmark** (10,000 orders):
- Without validation: 1.23s
- With validation: 1.25s (+1.6%)

---

## See Also

- [Order Management API](../api/order-management/README.md) - Order placement and execution
- [Transaction Costs - Slippage](../api/order-management/transaction-costs/slippage.md) - Slippage modeling
- [Transaction Costs - Commissions](../api/order-management/transaction-costs/commissions.md) - Commission modeling
- [Exception Handling](./exception-handling.md) - Error handling patterns

---

## FAQ

**Q: Will my existing strategies break?**
A: Only if they relied on negative cash (which was already incorrect). Most strategies will work as-is or with minor adjustments.

**Q: Should I use "reject", "warn", or "strict" mode?**
A: Use `"reject"` (default) for production, `"warn"` for migration, `"strict"` for debugging.

**Q: Can I disable validation entirely?**
A: Yes, but it's not recommended. Disable with `context.blotter.enable_cash_validation = False`.

**Q: Does this affect live trading?**
A: Live trading (paper/live brokers) already had cash validation. This fix brings backtesting into parity.

**Q: What about short selling and margin?**
A: Currently, validation applies to long positions. Margin and short selling support is planned for future releases.

**Q: How do I know if an order was rejected?**
A: Check if `order()` returns `None`, and look for warnings in the log output.
