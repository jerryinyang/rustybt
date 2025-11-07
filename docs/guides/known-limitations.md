# Known Limitations

This document lists features that are not yet implemented or have known limitations in RustyBT. This helps users understand what is currently available and what features are planned for future releases.

---

## Order Management Limitations

### ❌ Order Modification Not Implemented

**Status:** Not Implemented
**Planned:** Future Release

**Description:**
Modifying existing open orders (changing price, quantity, etc.) is not currently supported.

**Workaround:**
Cancel the existing order and place a new one:

```python
# Current approach (works):
cancel_order(order_id)
new_order = order(asset, amount, limit_price=new_price)

# Future API (not yet available):
# modify_order(order_id, limit_price=new_price)  # ❌ Not implemented
```

**Tracking:** Issue #XXX

---

### ⚠️ OCO Order Sibling Linking Partial

**Status:** Partially Implemented
**Planned:** Full implementation in v0.2.0

**Description:**
While `OCOOrder` execution style exists, the ability to manually link two separate orders as OCO siblings (`order.add_oco_sibling()`) is not implemented.

**What Works:**
```python
# OCO execution style (works):
from rustybt.finance import OCOOrder, StopOrder, LimitOrder

oco_style = OCOOrder(
    order1_style=StopOrder(stop_price),
    order2_style=LimitOrder(limit_price)
)
order(asset, amount, style=oco_style)  # ✅ Works
```

**What Doesn't Work:**
```python
# Manual OCO linking (not implemented):
order1 = order(asset, amount, style=StopOrder(price1))
order2 = order(asset, -amount, style=StopOrder(price2))
order1.add_oco_sibling(order2)  # ❌ Method doesn't exist
```

**Tracking:** Issue #XXX

---

### ❌ Trailing Stop Limit Orders Not Available

**Status:** Not Implemented
**Planned:** v0.2.0

**Description:**
`TrailingStopLimitOrder` is not available. Only `TrailingStopOrder` (market order on trigger) is supported.

**Available:**
```python
from rustybt.finance import TrailingStopOrder

# Trailing stop (market order on trigger) - ✅ Works
order(asset, -shares, style=TrailingStopOrder(trail_percent=0.05))
```

**Not Available:**
```python
# Trailing stop limit - ❌ Not available
# from rustybt.finance import TrailingStopLimitOrder  # Doesn't exist
# order(asset, -shares, style=TrailingStopLimitOrder(...))
```

**Workaround:**
Use `TrailingStopOrder` and accept market execution on trigger.

**Tracking:** Issue #XXX

---

## Pipeline API Limitations

### ❌ MACD Factor Not Available

**Status:** Class naming mismatch
**Fixed In:** Documentation

**Description:**
The MACD indicator is available as `MACDSignal`, not `MACD`.

**Correct Usage:**
```python
from rustybt.pipeline.factors import MACDSignal  # ✅ Correct

macd = MACDSignal()  # Not MACD()
```

---

### ❌ AverageTrueRange Factor Not Available

**Status:** Not Implemented
**Planned:** v0.2.0

**Description:**
`AverageTrueRange` is not available as a single factor. Use composition instead.

**Workaround:**
```python
from rustybt.pipeline.factors import TrueRange, SimpleMovingAverage

tr = TrueRange()
atr = SimpleMovingAverage(inputs=[tr], window_length=14)  # ✅ Works
```

**Not Available:**
```python
from rustybt.pipeline.factors import AverageTrueRange  # ❌ Doesn't exist
atr = AverageTrueRange(window_length=14)
```

**Tracking:** Issue #XXX

---

## Portfolio Management Limitations

### ⚠️ Multi-Strategy Portfolio API Complexity

**Status:** Different API Pattern
**Documentation:** [portfolio_allocator_tutorial.py](../examples/portfolio_allocator_tutorial.py)

**Description:**
Multi-strategy portfolio management uses a different API pattern than single-strategy `TradingAlgorithm`.

**Key Differences:**

| Feature | Single Strategy | Multi-Strategy |
|---------|----------------|----------------|
| Base class | `TradingAlgorithm` | Plain Python class |
| API functions | `order()`, `order_target_percent()` | Direct ledger access |
| Execution | `run_algorithm()` | `portfolio.execute_bar()` |

**Correct Pattern:**
```python
class MyStrategy:
    """Simple strategy for PortfolioAllocator."""

    def handle_data(self, ledger, data):
        # ledger: DecimalLedger for this strategy
        # data: Market data dict
        # Direct ledger manipulation (not API functions)
        pass
```

**Not Compatible:**
```python
class MyStrategy(TradingAlgorithm):
    def handle_data(self, context, data):
        order_target_percent(asset, 0.5, ledger=context.ledger)  # ❌ Wrong pattern
```

**See:** [Multi-Strategy Portfolio Note](../examples/notebooks/09_multi_strategy_portfolio_note.md)

---

## Optimization Limitations

### ⚠️ Class Naming Inconsistencies (Fixed)

**Status:** Fixed in documentation
**Affected Versions:** Documentation prior to 2025-11-07

**Description:**
Several optimization classes were incorrectly named in examples.

**Correct Names:**
- ✅ `GridSearchAlgorithm` (not `GridSearch`)
- ✅ `BayesianOptimizer` (not `BayesianOptimization`)
- ✅ `KellyCriterionAllocation` (not `KellyAllocation`)
- ✅ `ObjectiveFunction(metric="sharpe_ratio")` (not `SharpeRatio()`)

---

## Data Management Limitations

### ⚠️ Real-Time Data Latency

**Status:** Design Limitation
**Mitigation:** Use WebSocket streaming

**Description:**
REST API-based data adapters have inherent latency. For sub-second strategies, use WebSocket streaming.

**Recommendation:**
- **Daily/Hourly strategies:** REST APIs are fine
- **Minute strategies:** Consider WebSocket for real-time data
- **Sub-minute strategies:** WebSocket required

**See:** [WebSocket Streaming Guide](./websocket-streaming-guide.md)

---

## Live Trading Limitations

### ⚠️ Exchange-Specific Features

**Status:** Varies by Broker
**Documentation:** Per-broker adapter docs

**Description:**
Not all exchanges support all order types or features.

**Examples:**
- Some exchanges don't support stop-limit orders
- Some exchanges don't support OCO orders
- Margin requirements vary by exchange
- Fee structures differ significantly

**Recommendation:**
Always test in paper trading mode first to verify feature support for your specific broker.

**See:** [Testnet Setup Guide](./testnet-setup-guide.md)

---

## Performance Limitations

### ℹ️ Large Universe Performance

**Status:** Known Limitation
**Mitigation:** Use efficient filtering

**Description:**
Pipeline API performance degrades with very large universes (>5000 assets).

**Recommendations:**
- Pre-filter universes to relevant assets
- Use coarse filters before expensive computations
- Consider incremental universe updates
- Use data caching for repeated backtests

**See:** [Performance Optimization Guide](../guides/optimization-caching-performance-tuning.md)

---

## Testing and Validation Limitations

### ℹ️ No Built-In Walk-Forward Testing for Live Trading

**Status:** Design Decision
**Workaround:** Shadow trading mode

**Description:**
Walk-forward optimization is available for backtesting but not automatically for live trading.

**Recommendation:**
Use shadow trading mode to validate strategies with live data before enabling real trading.

**See:** [Shadow Trading Guide](../examples/shadow_trading_simple.py)

---

## Future Roadmap

### Planned for v0.2.0
- ✅ Order modification API
- ✅ Full OCO sibling linking
- ✅ Trailing stop-limit orders
- ✅ AverageTrueRange factor
- ✅ Enhanced multi-timeframe support

### Planned for v0.3.0
- ✅ Options trading support
- ✅ Futures spread trading
- ✅ Advanced portfolio analytics
- ✅ Machine learning integration

---

## Reporting Issues

Found a limitation not listed here?

1. **Check the Issues:** https://github.com/rustybt/rustybt/issues
2. **Create a New Issue:** Use the "Feature Request" template
3. **Discussions:** https://github.com/rustybt/rustybt/discussions

---

## Contributing

Want to help implement these features?

See [Docstring Style Guide](../contributing/docstring-style-guide.md) for:
- Development setup
- Code standards
- Pull request process
- Feature proposal guidelines

---

**Last Updated:** 2025-11-07
**Version:** 0.1.2
