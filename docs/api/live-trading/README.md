# Live Trading Infrastructure

Production-ready infrastructure for deploying strategies to live markets with safety controls and state management.

## Overview

The live trading system enables strategies developed in backtesting to run in production with real capital. It provides broker integrations, real-time data streaming, position reconciliation, state management, and comprehensive safety controls.

### Key Features

- **Multiple Broker Support**: CCXT (100+ exchanges), Interactive Brokers, Binance, Bybit, Hyperliquid
- **Real-Time Streaming**: WebSocket data feeds for live market data
- **State Management**: Checkpointing and recovery for reliability
- **Position Reconciliation**: Sync with broker positions automatically
- **Circuit Breakers**: Automated risk controls and safety limits
- **Shadow Trading**: Parallel backtest validation against live execution
- **Paper Trading**: Simulated trading for strategy validation

### Architecture

```
┌──────────────────────────────────────────────────────┐
│             Trading Strategy (Your Code)              │
├──────────────────────────────────────────────────────┤
│            LiveTradingEngine                          │
│  ┌─────────┬──────────┬───────────┬───────────┐     │
│  │ Event   │  State   │Position   │ Circuit   │     │
│  │ Loop    │ Manager  │Reconciler │ Breakers  │     │
│  └─────────┴──────────┴───────────┴───────────┘     │
├──────────────────────────────────────────────────────┤
│       Broker Adapter (CCXT/IB/Binance/etc.)         │
├──────────────────────────────────────────────────────┤
│    ┌──────────────┬──────────────┐                  │
│    │   Orders     │  Market Data │                  │
│    │  REST API    │   WebSocket  │                  │
│    └──────────────┴──────────────┘                  │
├──────────────────────────────────────────────────────┤
│         Live Market / Exchange / Broker              │
└──────────────────────────────────────────────────────┘
```

## Quick Navigation

### Core Infrastructure
- **[Streaming Architecture](streaming/architecture.md)** - Real-time data streaming design
- **[Exchange-Specific Streams](streaming/binance.md)** - Binance, Bybit, Hyperliquid, CCXT

### State Management
- **[State Management](state/management.md)** - Checkpointing and recovery
- **[Position Reconciliation](state/reconciliation.md)** - Syncing with broker positions
- **[Recovery Procedures](state/recovery.md)** - Handling failures and restarts

### Safety & Risk Controls
- **[Circuit Breakers](safety/circuit-breakers.md)** - Automated trading halts
- **[Position Limits](safety/limits.md)** - Risk limits and constraints
- **[Monitoring](safety/monitoring.md)** - Health checks and alerts

### Deployment
- **[Setup Guide](deployment/setup.md)** - Production deployment
- **[Configuration](deployment/configuration.md)** - Environment and settings
- **[Best Practices](deployment/best-practices.md)** - Production recommendations

## Quick Start

### Basic Live Trading

```python
import asyncio
from rustybt import TradingAlgorithm
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers import PaperBroker
from rustybt.data.polars import PolarsDataPortal

class MyStrategy(TradingAlgorithm):
    def initialize(self):
        self.symbol = self.symbol('BTC/USDT')

    def handle_data(self, context, data):
        price = data.current(self.symbol, 'close')
        # Your trading logic here

async def main():
    # Create broker adapter (paper trading for testing)
    broker = PaperBroker(starting_cash=Decimal("100000"))

    # Create data portal
    portal = PolarsDataPortal(bundle_name='crypto-data')

    # Create live trading engine
    engine = LiveTradingEngine(
        strategy=MyStrategy(),
        broker_adapter=broker,
        data_portal=portal
    )

    # Run engine
    await engine.run()

if __name__ == '__main__':
    asyncio.run(main())
```

### With Safety Controls

```python
from rustybt.live import LiveTradingEngine, CircuitBreaker, CircuitBreakerConfig

# Configure safety limits
circuit_breaker_config = CircuitBreakerConfig(
    max_daily_loss=Decimal("5000"),      # Max $5k loss per day
    max_position_size=Decimal("50000"),   # Max $50k position
    max_leverage=Decimal("2.0"),          # Max 2x leverage
    max_drawdown=Decimal("0.15")          # Max 15% drawdown
)

circuit_breaker = CircuitBreaker(circuit_breaker_config)

engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=portal,
    circuit_breaker=circuit_breaker
)

await engine.run()
```

### With State Management

```python
from rustybt.live import StateManager

# Create state manager for checkpointing
state_manager = StateManager(
    checkpoint_dir="/path/to/checkpoints"
)

engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=portal,
    state_manager=state_manager,
    checkpoint_interval_seconds=60  # Checkpoint every minute
)

await engine.run()
```

## Broker Adapters

### Paper Trading (Testing)

```python
from rustybt.live.brokers import PaperBroker

broker = PaperBroker(
    starting_cash=Decimal("100000"),
    commission_model=None,  # No commissions
    slippage_model=None     # No slippage
)
```

### CCXT (100+ Exchanges)

```python
from rustybt.live.brokers import CCXTBrokerAdapter
import os

broker = CCXTBrokerAdapter(
    exchange_id='binance',
    api_key=os.getenv('BINANCE_API_KEY'),
    api_secret=os.getenv('BINANCE_API_SECRET'),
    testnet=True,  # Use testnet for testing
    rate_limit=True
)
```

### Binance (Native)

```python
from rustybt.live.brokers import BinanceBrokerAdapter

broker = BinanceBrokerAdapter(
    api_key=os.getenv('BINANCE_API_KEY'),
    api_secret=os.getenv('BINANCE_API_SECRET'),
    testnet=True
)
```

### Interactive Brokers

```python
from rustybt.live.brokers import IBBrokerAdapter

broker = IBBrokerAdapter(
    host='127.0.0.1',
    port=7497,  # Paper trading port
    client_id=1
)
```

## Real-Time Data Streaming

### WebSocket Market Data

```python
from rustybt.live.streaming import BinanceStreamAdapter

# Create stream adapter
stream = BinanceStreamAdapter(
    symbols=['BTC/USDT', 'ETH/USDT'],
    testnet=True
)

# Subscribe to data
await stream.connect()
await stream.subscribe_market_data()

# Receive data
async for data in stream.stream():
    print(f"{data['symbol']}: ${data['close']}")
```

### Integration with Engine

```python
# Engine automatically handles streaming
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=portal
)

# Broker adapter manages WebSocket connections
await engine.run()  # Starts streaming automatically
```

## Position Reconciliation

Automatically sync positions with broker:

```python
from rustybt.live import ReconciliationStrategy

engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=portal,
    reconciliation_strategy=ReconciliationStrategy.AUTO_ADJUST,
    reconciliation_interval_seconds=300  # Every 5 minutes
)
```

**Reconciliation Strategies**:
- `WARN_ONLY`: Log discrepancies but don't adjust
- `AUTO_ADJUST`: Automatically fix engine state to match broker
- `HALT_ON_MISMATCH`: Stop trading on discrepancy
- `MANUAL_APPROVAL`: Require manual confirmation

## Circuit Breakers

Automated safety controls:

```python
from rustybt.live import CircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    max_daily_loss=Decimal("5000"),       # Daily loss limit
    max_position_size=Decimal("50000"),   # Position size limit
    max_leverage=Decimal("2.0"),          # Leverage limit
    max_order_value=Decimal("10000"),     # Per-order limit
    max_orders_per_minute=10,             # Rate limit
    trading_hours_only=True               # Only trade during hours
)

breaker = CircuitBreaker(config)

# Check before trading
if breaker.check_trade({'value': Decimal("1000")}):
    # Trade allowed
    pass
else:
    # Trade rejected by circuit breaker
    print("Circuit breaker triggered!")
```

## Shadow Trading

Validate live trading with parallel backtest:

```python
from rustybt.live.shadow import ShadowBacktestEngine, ShadowTradingConfig

shadow_config = ShadowTradingConfig(
    tolerance_percent=Decimal("0.02"),  # 2% tolerance
    alert_on_divergence=True,
    halt_on_large_divergence=True,
    large_divergence_threshold=Decimal("0.10")  # 10%
)

engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=broker,
    data_portal=portal,
    shadow_mode=True,
    shadow_config=shadow_config
)

# Engine runs shadow backtest in parallel
# Alerts if live trading diverges from backtest
await engine.run()
```

## Error Handling

### Graceful Shutdown

```python
import signal

engine = LiveTradingEngine(...)

# Handle shutdown signal
def handle_shutdown(sig, frame):
    asyncio.create_task(engine.graceful_shutdown())

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

await engine.run()
```

### Automatic Recovery

```python
# Engine automatically recovers from crashes
state_manager = StateManager(checkpoint_dir="/path/to/checkpoints")

engine = LiveTradingEngine(
    ...,
    state_manager=state_manager
)

# On restart, engine loads last checkpoint
await engine.run()  # Resumes from last state
```

## Monitoring

### Health Checks

```python
# Check engine health
health = engine.get_health_status()

print(f"Status: {health['status']}")  # 'healthy', 'degraded', 'critical'
print(f"Broker Connected: {health['broker_connected']}")
print(f"Last Data Update: {health['last_data_update']}")
print(f"Position Count: {health['position_count']}")
```

### Metrics

```python
# Get performance metrics
metrics = engine.get_metrics()

print(f"Orders Submitted: {metrics['orders_submitted']}")
print(f"Orders Filled: {metrics['orders_filled']}")
print(f"Total PnL: ${metrics['total_pnl']}")
print(f"Win Rate: {metrics['win_rate']:.1%}")
```

## Best Practices

### 1. Start with Paper Trading

```python
# Always test with paper trading first
broker = PaperBroker(starting_cash=Decimal("100000"))

# Run for days/weeks before live capital
```

### 2. Use Testnet for Crypto

```python
# Use exchange testnets
broker = BinanceBrokerAdapter(
    ...,
    testnet=True  # Free testnet tokens
)
```

### 3. Enable All Safety Controls

```python
engine = LiveTradingEngine(
    ...,
    circuit_breaker=circuit_breaker,  # Risk limits
    reconciliation_strategy=ReconciliationStrategy.AUTO_ADJUST,  # Position sync
    shadow_mode=True  # Validate against backtest
)
```

### 4. Monitor Closely

```python
# Set up monitoring
from rustybt.live.monitoring import setup_monitoring

setup_monitoring(
    engine=engine,
    alert_email='your@email.com',
    slack_webhook='https://hooks.slack.com/...'
)
```

### 5. Start Small

```python
# Start with small capital
starting_cash = Decimal("1000")  # Not $100,000

# Use small position sizes
max_position_size = Decimal("200")  # 20% of capital
```

## Common Workflows

### Workflow 1: Development to Production

1. **Backtest**: Optimize and validate strategy
2. **Paper Trading**: Test with simulated broker
3. **Testnet**: Test on exchange testnet
4. **Small Live**: Deploy with small capital
5. **Scale Up**: Gradually increase capital

### Workflow 2: Daily Operations

1. **Pre-Market**: Check system health
2. **Market Open**: Monitor initial trades
3. **Intraday**: Watch for circuit breakers
4. **Post-Market**: Review performance
5. **End of Day**: Check state checkpoint

## Common Pitfalls

### ❌ No Paper Trading

```python
# WRONG: Going straight to live
broker = CCXTBrokerAdapter(exchange_id='binance', testnet=False)

# RIGHT: Test with paper first
broker = PaperBroker(...)
# ... test thoroughly
# Then: broker = CCXTBrokerAdapter(..., testnet=True)
# Finally: broker = CCXTBrokerAdapter(..., testnet=False)
```

### ❌ No Safety Limits

```python
# WRONG: No limits
engine = LiveTradingEngine(strategy, broker, portal)

# RIGHT: With safety controls
engine = LiveTradingEngine(
    strategy, broker, portal,
    circuit_breaker=breaker,
    reconciliation_strategy=ReconciliationStrategy.AUTO_ADJUST
)
```

### ❌ Ignoring State Management

```python
# WRONG: No checkpointing
engine = LiveTradingEngine(strategy, broker, portal)

# RIGHT: Enable state management
engine = LiveTradingEngine(
    strategy, broker, portal,
    state_manager=StateManager(checkpoint_dir="/path")
)
```

## Examples

See `examples/live_trading/` for complete examples:

- `paper_trading_example.py` - Basic paper trading
- `binance_live_trading.py` - Binance integration
- `ib_live_trading.py` - Interactive Brokers
- `shadow_trading_example.py` - Shadow backtest validation
- `production_deployment.py` - Full production setup

## See Also

- [Main Live Trading API](../live-trading-api.md)
- [Optimization Documentation](../optimization/README.md)
- [Analytics Documentation](../analytics/README.md)
- [Broker Setup Guide](../../guides/broker-setup-guide.md)

## Support

- **Issues**: [GitHub Issues](https://github.com/bmad-dev/rustybt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/bmad-dev/rustybt/discussions)
- **Documentation**: [Full API Reference](https://rustybt.readthedocs.io)

## ⚠️ Risk Warning

**Live trading involves real financial risk. You can lose money.**

- Always test thoroughly in paper trading and testnets
- Start with small capital
- Use all safety controls
- Monitor closely
- Never risk more than you can afford to lose
