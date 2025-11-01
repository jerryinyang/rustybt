# Migrating to Cash Validation

**Applies to**: Strategies written before v0.x.x
**Impact**: Medium - Most strategies work as-is, some may need adjustments
**Timeline**: Immediate (enabled by default)

---

## What Changed

Starting in **v0.x.x**, RustyBT's backtest engine validates available cash before allowing orders to be placed or executed. This prevents backtests from showing impossible trades that would be rejected by real brokers.

### Before (Legacy Behavior)

```python
# Portfolio: $10,000 cash
order(AAPL, 200, LimitOrder(100))  # Needs $20,000

# ❌ PROBLEM: Order accepted, cash goes to -$10,000
# Backtest shows trades that couldn't happen in real trading
```

### After (New Behavior)

```python
# Portfolio: $10,000 cash
order_id = order(AAPL, 200, LimitOrder(100))  # Needs $20,000

# ✅ CORRECT: Order rejected (order_id = None)
# Warning logged: "Order rejected - insufficient cash"
# Backtest continues normally
```

---

## Will My Strategy Break?

**Short answer**: Probably not, but your results may change.

**Your strategy will work as-is if**:
- You never relied on negative cash balances
- You have proper position sizing that respects available capital
- You use `order_target_percent()` or `order_target_value()` (these already check cash)

**Your strategy may need adjustments if**:
- You place multiple large orders simultaneously
- You don't check available cash before ordering
- You relied on negative cash (this was always incorrect)

---

## Migration Steps

### Step 1: Test with "warn" Mode

First, run your strategy in "warn" mode to see if any orders would be rejected:

```python
def initialize(context):
    # Temporarily use warn mode to see issues without breaking
    context.set_cash_validation_mode("warn")

    # ... rest of your initialization
```

Run your backtest and check the output for warnings:

```
WARNING - Order placed with insufficient cash: need $50,000.00,
have $45,000.00 available ($45,000.00 total - $0.00 reserved)
Asset: AAPL, Amount: 500
```

### Step 2: Analyze Warnings

If you see warnings, review:

1. **How often** they occur
2. **Which assets** are affected
3. **How much** cash is short

### Step 3: Fix Cash Management

#### Option A: Reduce Position Sizes

```python
# BEFORE
def rebalance(context, data):
    for asset in context.universe:
        order_target_percent(asset, 0.10)  # 10% each

# AFTER
def rebalance(context, data):
    # Limit total exposure
    max_positions = min(len(context.universe), 10)
    target_percent = 0.90 / max_positions  # 90% total, divided evenly

    for asset in context.universe[:max_positions]:
        order_target_percent(asset, target_percent)
```

#### Option B: Check Cash Before Ordering

```python
# BEFORE
def handle_data(context, data):
    for asset in get_signals():
        shares = calculate_shares(asset)
        order(asset, shares, LimitOrder(price))

# AFTER
def handle_data(context, data):
    for asset in get_signals():
        shares = calculate_shares(asset)
        estimated_cost = shares * data.current(asset, 'price') * 1.01  # +1% buffer

        if estimated_cost <= context.portfolio.cash:
            order(asset, shares, LimitOrder(price))
        else:
            context.log.warning(f"Skipping {asset.symbol} - insufficient cash")
```

#### Option C: Limit Concurrent Orders

```python
# BEFORE
def handle_data(context, data):
    for asset in get_signals():
        order(asset, shares, LimitOrder(price))

# AFTER
def handle_data(context, data):
    # Limit to 5 open orders at a time
    if len(context.get_open_orders()) >= 5:
        return

    for asset in get_signals():
        if len(context.get_open_orders()) >= 5:
            break
        order(asset, shares, LimitOrder(price))
```

### Step 4: Switch to "reject" Mode

Once warnings are resolved, switch to default mode:

```python
def initialize(context):
    # Use default mode (or explicitly set to "reject")
    context.set_cash_validation_mode("reject")  # or remove line

    # ... rest of your initialization
```

### Step 5: Verify Results

Run your backtest and verify:

- No warnings about insufficient cash
- Results are reasonable
- Performance metrics make sense

---

## Common Migration Patterns

### Pattern 1: From Fixed Shares to Percentage

```python
# BEFORE: Fixed number of shares
def rebalance(context, data):
    order(context.aapl, 100, MarketOrder())  # Always 100 shares

# AFTER: Scale with portfolio value
def rebalance(context, data):
    order_target_percent(context.aapl, 0.05)  # Always 5% of portfolio
```

### Pattern 2: From Unlimited Orders to Cash-Aware

```python
# BEFORE: Order everything that signals
def handle_data(context, data):
    signals = get_buy_signals(data)
    for asset in signals:
        order(asset, 100, MarketOrder())

# AFTER: Distribute cash across signals
def handle_data(context, data):
    signals = get_buy_signals(data)
    if not signals:
        return

    # Allocate 80% of cash across signals
    cash_per_signal = (context.portfolio.cash * 0.80) / len(signals)

    for asset in signals:
        price = data.current(asset, 'price')
        shares = cash_per_signal / price
        order(asset, shares, MarketOrder())
```

### Pattern 3: From Batch Orders to Sequential with Checks

```python
# BEFORE: Place all orders at once
def rebalance(context, data):
    targets = calculate_targets(context, data)
    for asset, target_pct in targets.items():
        order_target_percent(asset, target_pct)

# AFTER: Track cumulative usage
def rebalance(context, data):
    targets = calculate_targets(context, data)
    total_cash = context.portfolio.cash
    used_cash = 0

    for asset, target_pct in targets.items():
        target_value = context.portfolio.portfolio_value * target_pct
        available = total_cash - used_cash

        if target_value <= available:
            order_target_percent(asset, target_pct)
            used_cash += target_value
        else:
            # Scale down to fit remaining cash
            affordable_pct = available / context.portfolio.portfolio_value
            order_target_percent(asset, affordable_pct)
            break  # No more cash
```

---

## Handling Rejected Orders

### Detect Rejections

```python
def handle_data(context, data):
    order_id = order(asset, shares, LimitOrder(price))

    if order_id is None:
        # Order was rejected
        context.log.warning(f"Order rejected for {asset.symbol}")
        handle_rejection(context, asset, shares)
    else:
        # Order accepted
        context.pending_orders[asset] = order_id
```

### Fallback Strategies

#### 1. Try Smaller Position

```python
def try_order_with_fallback(context, asset, shares, price):
    order_id = order(asset, shares, LimitOrder(price))

    if order_id is None and shares > 10:
        # Try 50% of original size
        order_id = order(asset, shares // 2, LimitOrder(price))

    return order_id
```

#### 2. Queue for Later

```python
def handle_data(context, data):
    # Try pending orders from previous bars first
    retry_pending_orders(context, data)

    # Then try new orders
    for signal in get_signals():
        order_id = order(signal.asset, signal.shares, LimitOrder(signal.price))

        if order_id is None:
            # Queue for next bar
            context.pending_signals.append(signal)

def retry_pending_orders(context, data):
    for signal in list(context.pending_signals):
        order_id = order(signal.asset, signal.shares, LimitOrder(signal.price))

        if order_id is not None:
            context.pending_signals.remove(signal)
```

#### 3. Prioritize Signals

```python
def handle_data(context, data):
    signals = get_signals(data)

    # Sort by strength/conviction
    signals.sort(key=lambda s: s.strength, reverse=True)

    # Try highest conviction first
    for signal in signals:
        order_id = order(signal.asset, signal.shares, LimitOrder(signal.price))

        if order_id is None:
            # Out of cash, stop trying
            break
```

---

## Backward Compatibility Options

### Option 1: Use "warn" Mode (Temporary)

For gradual migration, use "warn" mode:

```python
def initialize(context):
    # Logs warnings but allows all orders
    context.set_cash_validation_mode("warn")
```

⚠️ This is temporary - fix issues and switch to "reject" mode.

### Option 2: Disable Validation (Not Recommended)

Only for comparing with legacy results:

```python
def initialize(context):
    # Disable validation entirely
    context.blotter.enable_cash_validation = False
```

❌ **Do not use in production** - makes backtests unrealistic.

---

## Performance Comparison

After migrating, your strategy performance may change:

### Expected Changes

| Metric | Before | After | Why |
|--------|--------|-------|-----|
| **Returns** | May be higher | More realistic | No impossible over-leveraged trades |
| **Max Drawdown** | May be lower | More realistic | No negative cash compounding losses |
| **Sharpe Ratio** | May be different | More realistic | Realistic risk/return profile |
| **Number of Trades** | May be higher | Lower or same | Some orders rejected |

### Example Comparison

```
BEFORE (No Validation):
- Total Returns: 45.2%
- Max Drawdown: -12.3%
- Sharpe Ratio: 1.85
- Total Trades: 1,234
- Negative Cash Days: 16  ❌

AFTER (With Validation):
- Total Returns: 38.7%  (more realistic)
- Max Drawdown: -10.1%  (more realistic)
- Sharpe Ratio: 1.92    (better risk-adjusted)
- Total Trades: 1,156   (some orders rejected)
- Negative Cash Days: 0  ✅
```

**Interpretation**: The "after" results are more realistic and represent what would actually happen in live trading.

---

## Troubleshooting

### Issue: Many Orders Rejected

**Symptom**:
```
WARNING - Order rejected - Insufficient cash: need $50,000.00, have $45,000.00 available
WARNING - Order rejected - Insufficient cash: need $48,000.00, have $45,000.00 available
...
```

**Solutions**:

1. Reduce position sizes
2. Limit number of concurrent positions
3. Use `order_target_percent()` instead of fixed shares
4. Add cash buffer (use only 90% of available cash)

### Issue: Strategy Stops Trading

**Symptom**: No trades after first few bars

**Cause**: All cash tied up in positions, no orders can be placed

**Solutions**:

1. Implement sell logic to free up cash
2. Use `order_target_percent(asset, 0)` to close positions
3. Set maximum position holding period
4. Implement rebalancing logic

### Issue: Results Changed Significantly

**Symptom**: Performance dropped 20%+ after migration

**Cause**: Strategy heavily relied on over-leveraging

**Solutions**:

1. **Adjust expectations**: New results are realistic
2. **Add leverage**: Use `set_leverage()` if your broker supports it
3. **Optimize position sizing**: Better capital allocation
4. **Review strategy logic**: May need fundamental changes

---

## Getting Help

If you encounter issues during migration:

1. **Check logs**: Look for "insufficient cash" warnings
2. **Review the guide**: [Cash Validation Guide](../guides/cash-validation.md)
3. **Try examples**: See working examples in `examples/` directory
4. **Ask for help**: Open an issue on GitHub with your warning messages

---

## FAQ

**Q: Why did my backtest results change?**
A: The old results included impossible trades (negative cash). New results are what would actually happen in live trading.

**Q: Can I get the old behavior back?**
A: Yes, set `context.blotter.enable_cash_validation = False`, but this makes backtests unrealistic.

**Q: My strategy worked fine before, why change it?**
A: It may have *appeared* to work, but results included impossible trades. The new behavior ensures your backtest matches reality.

**Q: What if I want to test a high-leverage strategy?**
A: Use `set_leverage()` to simulate margin, or set `cash_validation_mode="warn"` (but results won't match live trading).

**Q: How do I know if my strategy needs changes?**
A: Run in "warn" mode first. If you see warnings, you need to adjust cash management.

**Q: Will this affect live trading?**
A: No - live trading already had cash validation. This only affects backtesting.

---

## Additional Resources

- [Cash Validation Guide](../guides/cash-validation.md) - Complete documentation
- [Order Management API](../api/order-management/README.md) - API reference
- [Order Types](../api/order-management/order-types.md) - Order types and examples
- [Exception Handling](../guides/exception-handling.md) - Error handling patterns
