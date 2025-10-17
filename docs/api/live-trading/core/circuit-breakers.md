# Circuit Breakers - Comprehensive Guide

**Module**: `rustybt.live.circuit_breakers`
**Purpose**: Risk management through automatic trading halts
**Status**: ⚠️ **SAFETY CRITICAL** - ALWAYS use in live trading

---

## Overview

Circuit breakers are your last line of defense against catastrophic losses in live trading. They automatically halt trading when predefined risk limits are exceeded, preventing runaway losses from algorithm bugs, market anomalies, or unexpected conditions.

**Core Principle**: It's better to miss opportunities than to suffer unbounded losses.

---

## Why Circuit Breakers Are Critical

### Real-World Scenarios

**Without Circuit Breakers**:
- Algorithm bug causes infinite buy loop → Account blown in minutes
- Flash crash triggers massive drawdown → -50% before manual intervention
- API rate limiting causes order spam → Exchange bans account

**With Circuit Breakers**:
- Drawdown breaker halts at -10% → Maximum loss contained
- Order rate breaker stops runaway loop after 10 orders → Bug isolated
- Error rate breaker detects API issues → Trading paused, investigation begins

---

## Circuit Breaker Types

### 1. DrawdownCircuitBreaker ⚠️ **HIGHLY RECOMMENDED**

Halts trading when portfolio drawdown exceeds threshold.

**Import**:
```python
from rustybt.live.circuit_breakers import DrawdownCircuitBreaker
from decimal import Decimal
```

**Initialization**:
```python
breaker = DrawdownCircuitBreaker(
    max_drawdown_pct=Decimal("0.10"),  # Halt at 10% drawdown
    lookback_days=30                    # From 30-day peak
)
```

**Parameters**:
- `max_drawdown_pct`: Maximum drawdown percentage before halt (e.g., `Decimal("0.10")` = 10%)
- `lookback_days`: Days to look back for peak portfolio value (default: 30)

**How It Works**:
1. Tracks portfolio value over `lookback_days`
2. Calculates peak value in lookback window
3. Current drawdown = `(peak - current) / peak`
4. If `current_drawdown > max_drawdown_pct`, trip breaker

**Example**:
```python
from decimal import Decimal
from rustybt.live.circuit_breakers import DrawdownCircuitBreaker

# Halt at 10% drawdown from 30-day peak
breaker = DrawdownCircuitBreaker(
    max_drawdown_pct=Decimal("0.10"),
    lookback_days=30
)

# Check before trading
if breaker.can_trade(current_portfolio_value=Decimal("95000")):
    # Peak was $100K, current $95K = 5% drawdown, OK to trade
    await submit_order(...)
else:
    # Drawdown exceeded 10%, trading halted
    logger.error("drawdown_breaker_tripped",
                reason=breaker.get_trip_reason())
```

**Recommended Settings**:
- **Conservative**: `max_drawdown_pct=Decimal("0.05")` (5%)
- **Moderate**: `max_drawdown_pct=Decimal("0.10")` (10%)
- **Aggressive**: `max_drawdown_pct=Decimal("0.15")` (15%)

**Important**: Use shorter `lookback_days` for volatile strategies (7-14 days), longer for stable strategies (30-60 days).

---

### 2. DailyLossCircuitBreaker ⚠️ **HIGHLY RECOMMENDED**

Halts trading when daily loss exceeds absolute dollar threshold.

**Import**:
```python
from rustybt.live.circuit_breakers import DailyLossCircuitBreaker
from decimal import Decimal
```

**Initialization**:
```python
breaker = DailyLossCircuitBreaker(
    max_daily_loss=Decimal("5000")  # Halt after $5K daily loss
)
```

**Parameters**:
- `max_daily_loss`: Maximum daily loss in dollars before halt

**How It Works**:
1. Tracks portfolio value at start of trading day (market open or midnight UTC for crypto)
2. Calculates current daily P&L = `current_value - start_of_day_value`
3. If `daily_loss > max_daily_loss`, trip breaker
4. Resets at start of next trading day

**Example**:
```python
from decimal import Decimal
from rustybt.live.circuit_breakers import DailyLossCircuitBreaker

# Halt after $5K daily loss
breaker = DailyLossCircuitBreaker(max_daily_loss=Decimal("5000"))

# Check before trading
if breaker.can_trade(current_portfolio_value=Decimal("97000"), start_of_day_value=Decimal("100000")):
    # Lost $3K today, OK to trade
    await submit_order(...)
else:
    # Lost >$5K today, trading halted
    logger.error("daily_loss_breaker_tripped",
                daily_loss=breaker.get_current_daily_loss())
```

**Recommended Settings**:
- Set to 5-10% of portfolio value for conservative risk management
- For $100K portfolio: `max_daily_loss=Decimal("5000")` to `Decimal("10000")`
- For $1M portfolio: `max_daily_loss=Decimal("50000")` to `Decimal("100000")`

**Important**: This is an absolute loss limit, not percentage. Adjust as portfolio grows.

---

### 3. OrderRateCircuitBreaker

Prevents runaway algorithms by limiting order submission rate.

**Import**:
```python
from rustybt.live.circuit_breakers import OrderRateCircuitBreaker
```

**Initialization**:
```python
breaker = OrderRateCircuitBreaker(
    max_orders_per_minute=10,   # Max 10 orders per minute
    window_seconds=60            # 60-second sliding window
)
```

**Parameters**:
- `max_orders_per_minute`: Maximum orders allowed per minute
- `window_seconds`: Time window for rate calculation (default: 60)

**How It Works**:
1. Maintains sliding window of order submission times
2. Counts orders in last `window_seconds`
3. If count exceeds `max_orders_per_minute`, trip breaker
4. Automatically resets as orders age out of window

**Example**:
```python
from rustybt.live.circuit_breakers import OrderRateCircuitBreaker

# Max 10 orders per minute
breaker = OrderRateCircuitBreaker(
    max_orders_per_minute=10,
    window_seconds=60
)

# Check before each order
if breaker.can_trade():
    await broker.submit_order(...)
    breaker.record_order()  # Track this order
else:
    # Too many orders in last 60 seconds
    logger.error("order_rate_breaker_tripped",
                orders_in_window=breaker.get_order_count())
```

**Recommended Settings**:
- **Low-frequency strategies** (e.g., daily rebalance): `max_orders_per_minute=5`
- **Medium-frequency strategies** (e.g., hourly signals): `max_orders_per_minute=10`
- **High-frequency strategies** (e.g., minute bars): `max_orders_per_minute=30`

**Important**: Set conservatively to catch infinite loops. Legitimate strategies rarely submit >10 orders/minute.

---

### 4. ErrorRateCircuitBreaker

Halts trading when error rate exceeds threshold, indicating system issues.

**Import**:
```python
from rustybt.live.circuit_breakers import ErrorRateCircuitBreaker
```

**Initialization**:
```python
breaker = ErrorRateCircuitBreaker(
    max_errors=5,           # Halt after 5 errors
    window_seconds=300      # In 5-minute window
)
```

**Parameters**:
- `max_errors`: Maximum errors allowed in time window
- `window_seconds`: Time window for error counting (default: 300 = 5 minutes)

**How It Works**:
1. Maintains sliding window of error timestamps
2. Counts errors in last `window_seconds`
3. If count exceeds `max_errors`, trip breaker
4. Automatically resets as errors age out of window

**Example**:
```python
from rustybt.live.circuit_breakers import ErrorRateCircuitBreaker

# Halt after 5 errors in 5 minutes
breaker = ErrorRateCircuitBreaker(
    max_errors=5,
    window_seconds=300
)

# Track errors
try:
    await broker.submit_order(...)
except BrokerError as e:
    breaker.record_error()
    logger.error("order_failed", error=str(e))

    if not breaker.can_trade():
        # Too many errors, halt trading
        logger.critical("error_rate_breaker_tripped",
                       errors_in_window=breaker.get_error_count())
        await engine.pause()
```

**Recommended Settings**:
- **Stable production**: `max_errors=3`, `window_seconds=300` (strict)
- **Development/testing**: `max_errors=10`, `window_seconds=600` (lenient)

**Error Types to Track**:
- Broker connection errors
- Order submission failures
- Data feed disconnections
- Strategy exceptions

**Important**: Distinguish between expected errors (e.g., insufficient funds) and unexpected errors (e.g., API crashes).

---

### 5. ManualCircuitBreaker

Provides manual emergency stop capability for operators.

**Import**:
```python
from rustybt.live.circuit_breakers import ManualCircuitBreaker
```

**Initialization**:
```python
breaker = ManualCircuitBreaker()
```

**How It Works**:
1. Starts in `NORMAL` state (trading allowed)
2. Operator triggers halt manually
3. Remains halted until manually reset

**Example - Emergency Halt**:
```python
from rustybt.live.circuit_breakers import ManualCircuitBreaker

# Add to coordinator
breaker = ManualCircuitBreaker()
coordinator.add_breaker(breaker)

# Later, in emergency situation (e.g., via dashboard, CLI, or API)
breaker.trigger_halt(
    reason="Unexpected market volatility - Flash crash detected",
    operator="trader_john"
)

# Engine will halt immediately
# Check status
print(f"Breaker state: {breaker.state}")  # MANUALLY_HALTED
print(f"Halt reason: {breaker.get_trip_reason()}")

# Reset after investigation
breaker.reset(operator="trader_john")
```

**Use Cases**:
- Flash crashes or extreme market volatility
- News events affecting strategy assumptions
- Exchange maintenance windows
- Debugging production issues
- Testing circuit breaker integration

**Important**: Integrate with admin dashboard or CLI for easy operator access.

---

## Circuit Breaker Coordinator

The `CircuitBreakerManager` manages multiple circuit breakers as a unified system.

**Import**:
```python
from rustybt.live.circuit_breakers import CircuitBreakerManager
```

**Example - Complete Setup**:
```python
from decimal import Decimal
from rustybt.live.circuit_breakers import (
    CircuitBreakerManager,
    DrawdownCircuitBreaker,
    DailyLossCircuitBreaker,
    OrderRateCircuitBreaker,
    ErrorRateCircuitBreaker,
    ManualCircuitBreaker
)

# Create coordinator
coordinator = CircuitBreakerManager()

# Add breakers (order doesn't matter)
coordinator.add_breaker(
    DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.10"), lookback_days=30)
)
coordinator.add_breaker(
    DailyLossCircuitBreaker(max_daily_loss=Decimal("5000"))
)
coordinator.add_breaker(
    OrderRateCircuitBreaker(max_orders_per_minute=10)
)
coordinator.add_breaker(
    ErrorRateCircuitBreaker(max_errors=5, window_seconds=300)
)
coordinator.add_breaker(
    ManualCircuitBreaker()
)

# Check all breakers before trading
if coordinator.can_trade():
    # All breakers OK, proceed with trading
    await submit_order(...)
else:
    # At least one breaker tripped
    tripped = coordinator.get_tripped()
    for breaker in tripped:
        logger.error("breaker_tripped",
                    type=breaker.breaker_type.value,
                    reason=breaker.get_trip_reason())
```

**Coordinator Methods**:
```python
# Check if any breaker is tripped
if coordinator.any_tripped():
    ...

# Get all tripped breakers
tripped_breakers = coordinator.get_tripped()

# Get trip reasons for all tripped breakers
reasons = coordinator.get_trip_reasons()

# Reset all breakers (use with caution!)
coordinator.reset_all()

# Get status of all breakers
status = coordinator.get_status()
# Returns: {'drawdown': 'NORMAL', 'daily_loss': 'TRIPPED', ...}
```

---

## Integration with LiveTradingEngine

Circuit breakers integrate seamlessly with `LiveTradingEngine`:

```python
from rustybt.live import LiveTradingEngine
from rustybt.live.circuit_breakers import CircuitBreakerManager

# Set up coordinator with breakers
coordinator = CircuitBreakerManager()
coordinator.add_breaker(DrawdownCircuitBreaker(...))
coordinator.add_breaker(DailyLossCircuitBreaker(...))

# Pass to engine (engine checks breakers before each order)
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=data_portal,
    circuit_breakers=coordinator  # ⚠️ CRITICAL: Always include
)

# Engine automatically:
# - Checks breakers before order submission
# - Logs breaker trips
# - Emits events when breakers trip
# - Can auto-pause trading on trip (configurable)
```

---

## Circuit Breaker States

Each circuit breaker has one of four states:

### NORMAL
- **Meaning**: All clear, trading allowed
- **Actions**: None
- **Next States**: TRIPPED, MANUALLY_HALTED

### TRIPPED
- **Meaning**: Breaker condition exceeded, trading halted
- **Actions**: Log trip reason, alert operator
- **Next States**: NORMAL (after reset), RESETTING

### MANUALLY_HALTED
- **Meaning**: Operator triggered emergency stop
- **Actions**: Log halt reason, alert all operators
- **Next States**: NORMAL (after manual reset)

### RESETTING
- **Meaning**: Breaker resetting after trip (transient state)
- **Actions**: Clear trip conditions
- **Next States**: NORMAL

**State Transitions**:
```
NORMAL → TRIPPED (when condition exceeded)
TRIPPED → RESETTING (when reset() called)
RESETTING → NORMAL (after reset completes)
NORMAL → MANUALLY_HALTED (when trigger_halt() called)
MANUALLY_HALTED → NORMAL (when reset() called)
```

---

## Best Practices

### 1. Always Use Circuit Breakers in Live Trading

```python
# ❌ BAD: No circuit breakers
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=data_portal
    # Missing circuit_breakers parameter!
)

# ✅ GOOD: Circuit breakers included
coordinator = CircuitBreakerManager()
coordinator.add_breaker(DrawdownCircuitBreaker(...))
coordinator.add_breaker(DailyLossCircuitBreaker(...))

engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=data_portal,
    circuit_breakers=coordinator  # ✅ CRITICAL
)
```

### 2. Set Conservative Limits Initially

```python
# ✅ GOOD: Start conservative, relax later
coordinator = CircuitBreakerManager()

# Conservative limits for first week
coordinator.add_breaker(
    DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.05"))  # 5% max
)
coordinator.add_breaker(
    DailyLossCircuitBreaker(max_daily_loss=Decimal("2500"))  # $2.5K max
)
coordinator.add_breaker(
    OrderRateCircuitBreaker(max_orders_per_minute=5)  # Very low rate
)

# After 1-2 weeks of stable operation, increase limits if justified
```

### 3. Test Circuit Breakers in Paper Trading

```python
# ✅ GOOD: Test breaker behavior in paper mode
# Force breaker trip to verify behavior

# Temporarily set low limits
test_breaker = DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.01"))  # 1%

# Run paper trading until breaker trips
# Verify:
# - Breaker trips as expected
# - Trading halts
# - Logs are generated
# - Alerts are sent
# - Reset works correctly
```

### 4. Monitor Breaker Status

```python
# ✅ GOOD: Regular monitoring
import schedule

def check_circuit_breakers():
    status = coordinator.get_status()

    if coordinator.any_tripped():
        logger.critical("circuit_breakers_tripped", status=status)
        # Send alerts (email, SMS, PagerDuty, etc.)
        send_alert("Circuit breakers tripped!", status)
    else:
        logger.info("circuit_breakers_status", status=status)

# Check every minute
schedule.every(1).minutes.do(check_circuit_breakers)
```

### 5. Log All Breaker Events

```python
# ✅ GOOD: Comprehensive logging
def on_breaker_trip(breaker, reason):
    logger.error(
        "circuit_breaker_tripped",
        breaker_type=breaker.breaker_type.value,
        state=breaker.state.value,
        reason=reason,
        timestamp=pd.Timestamp.now()
    )

    # Also log to separate circuit breaker audit log
    with open("/var/log/rustybt/circuit_breakers.log", "a") as f:
        f.write(f"{pd.Timestamp.now()} | {breaker.breaker_type.value} | TRIPPED | {reason}\n")
```

---

## Troubleshooting

### Breaker Tripped Unexpectedly

**Symptom**: Circuit breaker tripped but conditions don't seem excessive

**Diagnosis**:
```python
# Check breaker state and reason
if breaker.state == CircuitBreakerState.TRIPPED:
    reason = breaker.get_trip_reason()
    details = breaker.get_trip_details()
    print(f"Reason: {reason}")
    print(f"Details: {details}")
```

**Common Causes**:
1. **Drawdown Breaker**: Peak value was higher than expected (check lookback window)
2. **Daily Loss Breaker**: Start-of-day value incorrect (verify market open time)
3. **Order Rate Breaker**: Multiple strategies submitting orders (aggregate count)
4. **Error Rate Breaker**: Transient errors counted (check error types)

**Resolution**:
- Review logs around trip time
- Verify breaker thresholds are appropriate
- Check for correlated events (market moves, API issues)
- Adjust thresholds if justified

### Breaker Not Tripping When Expected

**Symptom**: Breaker should have tripped but didn't

**Diagnosis**:
```python
# Check breaker is added to coordinator
breakers_list = coordinator.get_all_breakers()
print(f"Active breakers: {[b.breaker_type.value for b in breakers_list]}")

# Check breaker is being called
if not coordinator.can_trade():
    # Coordinator working
    ...
```

**Common Causes**:
1. **Not Added to Coordinator**: Breaker created but not added
2. **Wrong Parameters**: Threshold set too high
3. **Not Integrated**: Engine not checking coordinator before orders
4. **Timing Issues**: Breaker checked before condition met

**Resolution**:
- Verify breaker added: `coordinator.add_breaker(breaker)`
- Verify thresholds: Print breaker config
- Verify integration: Check `engine.circuit_breakers` is set
- Add debug logging to breaker checks

### Breaker Stuck in TRIPPED State

**Symptom**: Breaker remains tripped after conditions resolved

**Diagnosis**:
```python
# Check breaker state
print(f"State: {breaker.state}")
print(f"Can trade: {breaker.can_trade()}")
```

**Resolution**:
```python
# Manual reset (after verifying conditions resolved)
breaker.reset(operator="admin")

# Verify state changed
print(f"New state: {breaker.state}")  # Should be NORMAL
```

**Important**: Only reset after:
1. Understanding why breaker tripped
2. Resolving underlying issue
3. Verifying conditions are back to normal

---

## Advanced Usage

### Custom Circuit Breakers

You can implement custom circuit breakers by subclassing `BaseCircuitBreaker`:

```python
from rustybt.live.circuit_breakers import BaseCircuitBreaker, CircuitBreakerType, CircuitBreakerState
from decimal import Decimal

class VolatilityCircuitBreaker(BaseCircuitBreaker):
    """Halt trading when volatility exceeds threshold."""

    def __init__(self, max_volatility: Decimal, window_minutes: int = 60):
        super().__init__(breaker_type=CircuitBreakerType.CUSTOM)
        self.max_volatility = max_volatility
        self.window_minutes = window_minutes
        self._returns_window = []

    def can_trade(self, returns: list[Decimal]) -> bool:
        """Check if volatility is within limits."""
        if self.state in [CircuitBreakerState.TRIPPED, CircuitBreakerState.MANUALLY_HALTED]:
            return False

        # Calculate realized volatility
        if len(returns) < 2:
            return True

        volatility = self._calculate_volatility(returns)

        if volatility > self.max_volatility:
            self._trip(reason=f"Volatility {volatility:.4f} exceeds max {self.max_volatility:.4f}")
            return False

        return True

    def _calculate_volatility(self, returns: list[Decimal]) -> Decimal:
        """Calculate annualized volatility."""
        import statistics
        return Decimal(str(statistics.stdev([float(r) for r in returns]))) * Decimal("15.87")  # sqrt(252)

# Usage
volatility_breaker = VolatilityCircuitBreaker(
    max_volatility=Decimal("0.30"),  # 30% annualized
    window_minutes=60
)
coordinator.add_breaker(volatility_breaker)
```

### Conditional Circuit Breakers

Enable/disable breakers based on conditions:

```python
# Enable different breakers for different trading sessions
if trading_session == "MARKET_OPEN":
    # More aggressive during market hours
    coordinator.add_breaker(
        DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.10"))
    )
elif trading_session == "AFTER_HOURS":
    # More conservative during after hours
    coordinator.add_breaker(
        DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.05"))
    )
```

---

## Summary

**Circuit Breakers Are Mandatory** ⚠️

- **Always** use `DrawdownCircuitBreaker` and `DailyLossCircuitBreaker` in live trading
- **Always** include `ManualCircuitBreaker` for emergency stops
- **Always** test breakers in paper trading before live deployment
- **Never** bypass circuit breakers to "catch up" on missed trades
- **Never** reset breakers without understanding why they tripped

**Recommended Minimum Setup**:
```python
coordinator = CircuitBreakerManager()
coordinator.add_breaker(DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.10")))
coordinator.add_breaker(DailyLossCircuitBreaker(max_daily_loss=Decimal("5000")))
coordinator.add_breaker(OrderRateCircuitBreaker(max_orders_per_minute=10))
coordinator.add_breaker(ManualCircuitBreaker())

engine = LiveTradingEngine(..., circuit_breakers=coordinator)
```

**Your capital depends on circuit breakers working correctly. Test them thoroughly.**

---

## Related Documentation

- [Live Trading Overview](../README.md)
- [Production Deployment](../production-deployment.md)
