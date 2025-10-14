# Circuit Breakers

Automated safety controls that halt trading when risk limits are breached.

## Overview

Circuit breakers protect against catastrophic losses by automatically stopping trading when predefined risk thresholds are exceeded.

## Basic Usage

```python
from rustybt.live import CircuitBreaker, CircuitBreakerConfig
from decimal import Decimal

# Configure safety limits
config = CircuitBreakerConfig(
    max_daily_loss=Decimal("5000"),      # Max $5k loss per day
    max_position_size=Decimal("50000"),   # Max $50k position
    max_leverage=Decimal("2.0"),          # Max 2x leverage
    max_drawdown=Decimal("0.15"),         # Max 15% drawdown
    max_order_value=Decimal("10000"),     # Max $10k per order
    max_orders_per_minute=10              # Rate limit
)

breaker = CircuitBreaker(config)

# Check before each trade
if breaker.check_trade({'value': Decimal("5000")}):
    # Trade allowed
    execute_trade()
else:
    # Trade rejected
    logger.warning("Circuit breaker triggered!")
```

## Circuit Breaker Types

### Loss Limits

```python
# Daily loss limit
if current_daily_loss > config.max_daily_loss:
    breaker.trip("Daily loss limit exceeded")

# Total drawdown limit
if current_drawdown > config.max_drawdown:
    breaker.trip("Max drawdown exceeded")
```

### Position Limits

```python
# Single position size
if position_value > config.max_position_size:
    breaker.reject_order("Position size limit exceeded")

# Leverage limit
if total_leverage > config.max_leverage:
    breaker.reject_order("Leverage limit exceeded")
```

### Rate Limits

```python
# Orders per time period
if orders_last_minute > config.max_orders_per_minute:
    breaker.reject_order("Rate limit exceeded")
```

## Integration with Live Trading

```python
from rustybt.live import LiveTradingEngine

# Create engine with circuit breaker
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=portal,
    circuit_breaker=breaker
)

# Engine automatically checks breaker before each trade
await engine.run()
```

## Recovery Procedures

```python
# Manual reset after investigation
if breaker.is_tripped():
    # 1. Review what triggered breaker
    trigger_reason = breaker.get_trigger_reason()

    # 2. Fix underlying issue

    # 3. Reset breaker
    breaker.reset()

    # 4. Resume trading
    await engine.resume()
```

## Best Practices

### 1. Conservative Limits

Start with tight limits and relax gradually:

```python
# Initial deployment
config = CircuitBreakerConfig(
    max_daily_loss=Decimal("1000"),  # Conservative
    max_position_size=Decimal("10000")
)

# After proven reliability
config = CircuitBreakerConfig(
    max_daily_loss=Decimal("5000"),  # Relaxed
    max_position_size=Decimal("50000")
)
```

### 2. Multiple Layers

Use cascading safety limits:

```python
config = CircuitBreakerConfig(
    # Layer 1: Warning (log but continue)
    warning_daily_loss=Decimal("2000"),

    # Layer 2: Reduce position sizes
    caution_daily_loss=Decimal("3500"),

    # Layer 3: Hard stop
    max_daily_loss=Decimal("5000")
)
```

### 3. Alert Notifications

```python
def on_circuit_breaker_trip(reason):
    """Send alerts when breaker trips."""
    send_email(f"Circuit breaker tripped: {reason}")
    send_slack(f"⚠️ Trading halted: {reason}")
    send_sms(f"ALERT: {reason}")

breaker = CircuitBreaker(
    config=config,
    on_trip=on_circuit_breaker_trip
)
```

## See Also

- [Position Limits](limits.md)
- [Monitoring](monitoring.md)
- [Main Live Trading API](../../live-trading-api.md)
