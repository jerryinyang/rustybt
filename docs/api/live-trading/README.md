# Live Trading Infrastructure

**Module**: `rustybt.live`
**Purpose**: Production-ready live trading engine with async event processing, broker integrations, and safety mechanisms
**Status**: Production-ready ⚠️ **SAFETY CRITICAL**

---

## ⚠️ Critical Safety Notice

**Live trading involves real capital at risk. This documentation emphasizes safety patterns throughout.**

### Before You Begin

1. ✅ **ALWAYS start with paper trading** - Test strategies in paper mode before risking real capital
2. ✅ **ALWAYS use circuit breakers** - All live trading examples include circuit breakers
3. ✅ **ALWAYS implement position reconciliation** - Verify broker positions regularly
4. ✅ **ALWAYS use state checkpoints** - Enable crash recovery
5. ✅ **NEVER skip testing** - Shadow trading validation is your friend
6. ✅ **NEVER deploy untested strategies** - Backtest first, paper trade second, live trade last

**Recommended Progression**:
```
Backtest → Paper Trading → Shadow Trading → Small Live Position → Full Live Trading
          (weeks)        (weeks)          (days)              (gradual scale-up)
```

---

## Overview

The RustyBT live trading infrastructure provides async event-driven live trading with the same `TradingAlgorithm` interface used in backtesting. Strategies require **zero code changes** to run live.

**Core Philosophy**: Safety first, strategy reusability, minimal latency, comprehensive monitoring.

### Key Features

**Strategy Execution**
- **Zero code changes**: Same `TradingAlgorithm` class for backtest and live
- **Async event loop**: Non-blocking order execution and data processing
- **State checkpointing**: Automatic crash recovery with atomic writes
- **Position reconciliation**: Periodic verification with broker positions

**Safety Mechanisms** ⚠️ **CRITICAL**
- **Circuit breakers**: Drawdown, daily loss, order rate, error rate, manual halt
- **Position limits**: Per-asset and portfolio-level position limits
- **Risk monitoring**: Real-time risk metrics and alerts
- **Error handling**: Comprehensive exception handling with automatic recovery

**Broker Integration**
- **Multiple brokers**: Interactive Brokers, Binance, Bybit, Hyperliquid, Paper Broker
- **WebSocket streaming**: Real-time market data with reconnection
- **Unified interface**: `BrokerAdapter` abstraction for broker-agnostic strategies

**Validation & Monitoring**
- **Shadow trading**: Parallel backtest validation of live signals
- **Execution quality**: Track slippage, latency, fill rates
- **Structured logging**: Comprehensive audit trail with `structlog`
- **Dashboards**: Real-time monitoring (optional, separate module)

---

## Quick Start - Paper Trading

### Basic Paper Trading Setup

```python
import asyncio
from decimal import Decimal
from rustybt.algorithm import TradingAlgorithm
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers.paper_broker import PaperBroker
from rustybt.live.circuit_breakers import (
    CircuitBreakerManager,
    DrawdownCircuitBreaker,
    DailyLossCircuitBreaker
)
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage
from rustybt.data.polars.data_portal import PolarsDataPortal

# Define your strategy (same as backtest!)
class MyStrategy(TradingAlgorithm):
    def initialize(self):
        self.asset = self.symbol('AAPL')
        self.rebalance_interval = 60  # minutes

    def handle_data(self, context, data):
        current_price = data.current(self.asset, 'price')
        # Your trading logic here
        self.order_target_percent(self.asset, 0.95)

# Set up paper broker with realistic simulation
paper_broker = PaperBroker(
    starting_cash=Decimal("100000"),
    commission_model=PerShareCommission(Decimal("0.005")),  # $0.005/share
    slippage_model=FixedBasisPointsSlippage(Decimal("5")),  # 5 basis points
    order_latency_ms=100,  # 100ms simulated latency
    volume_limit_pct=Decimal("0.025")  # Max 2.5% of bar volume
)

# Set up data portal for historical data access
data_portal = PolarsDataPortal(
    bundle_name='quandl',
    data_frequency='minute'
)

# ⚠️ CRITICAL: Set up circuit breakers (ALWAYS!)
circuit_breakers = CircuitBreakerManager()
circuit_breakers.add_breaker(
    DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.10"))  # 10% max drawdown
)
circuit_breakers.add_breaker(
    DailyLossCircuitBreaker(max_daily_loss=Decimal("5000"))   # $5K max daily loss
)

# Initialize live trading engine
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=paper_broker,
    data_portal=data_portal,
    checkpoint_interval_seconds=60,     # Save state every minute
    reconciliation_interval_seconds=300  # Reconcile positions every 5 minutes
)

# Run engine (async)
async def main():
    try:
        await engine.run()
    except KeyboardInterrupt:
        print("Shutting down gracefully...")
        await engine.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

**What this does**:
- ✅ Runs your strategy in paper trading mode (no real capital at risk)
- ✅ Simulates realistic execution (latency, slippage, commission)
- ✅ Protects against drawdowns >10% and daily losses >$5K
- ✅ Saves state every 60 seconds for crash recovery
- ✅ Reconciles positions with paper broker every 5 minutes

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  LiveTradingEngine                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Event Queue (Priority Queue)                  │ │
│  │  MarketData → OrderFill → ScheduledTrigger → Error     │ │
│  └────────────────────────────────────────────────────────┘ │
│                             ↓                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            EventDispatcher (Async)                      │ │
│  │  Routes events to handlers based on priority            │ │
│  └────────────────────────────────────────────────────────┘ │
│                             ↓                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ OrderManager │  │  DataFeed    │  │ StrategyExecutor │  │
│  │  - Orders    │  │  - Real-time │  │  - Your strategy │  │
│  │  - Fills     │  │  - Historical│  │  - handle_data() │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                             ↓                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ StateManager │  │ Reconciler   │  │ CircuitBreakers  │  │
│  │  - Checkpts  │  │  - Pos sync  │  │  - Risk limits   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                             ↓                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              BrokerAdapter (Abstract)                    │ │
│  │  - submit_order() - get_positions() - get_account()     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                             ↓                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────────┐  │
│  │  Paper  │  │ Binance │  │  Bybit  │  │  Interactive │  │
│  │  Broker │  │ Adapter │  │ Adapter │  │  Brokers     │  │
│  └─────────┘  └─────────┘  └─────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘

Optional: Shadow Trading Engine (parallel validation)
```

### Event Flow

1. **Market Data Arrives** → `MarketDataEvent` queued
2. **EventDispatcher** → Routes to `StrategyExecutor`
3. **Strategy Logic** → `handle_data()` called, generates orders
4. **Order Validation** → Circuit breakers check risk limits
5. **Order Submission** → `BrokerAdapter.submit_order()`
6. **Order Fill** → `OrderFillEvent` queued
7. **Portfolio Update** → Position/cash ledger updated
8. **Checkpoint** → State saved (every 60s)
9. **Reconciliation** → Verify broker positions (every 5 min)

---

## Core Components

### 1. LiveTradingEngine

**Module**: `rustybt.live.engine`

Main orchestrator for live trading with async event loop.

**Import**:
```python
from rustybt.live import LiveTradingEngine
from rustybt.live.models import ReconciliationStrategy
```

**Initialization**:
```python
engine = LiveTradingEngine(
    strategy=MyStrategy(),              # Your TradingAlgorithm
    broker_adapter=broker,              # Broker connection
    data_portal=portal,                 # Historical data access
    portfolio=None,                     # Optional: custom Portfolio
    account=None,                       # Optional: custom Account
    scheduler=None,                     # Optional: TradingScheduler
    state_manager=StateManager(),       # State checkpointing
    checkpoint_interval_seconds=60,     # Checkpoint frequency
    reconciliation_strategy=ReconciliationStrategy.WARN_ONLY,
    reconciliation_interval_seconds=300,
    shadow_mode=False,                  # Enable shadow trading
    shadow_config=None                  # Shadow trading config
)
```

**Key Methods**:
```python
# Start live trading event loop
await engine.run()

# Graceful shutdown with final checkpoint
await engine.shutdown()

# Temporarily pause trading
await engine.pause()

# Resume after pause
await engine.resume()

# Get engine status and statistics
status = engine.get_status()
# Returns: {'running': True, 'paused': False, 'orders_submitted': 42, ...}
```

**Example - Basic Usage**:
```python
import asyncio
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers.paper_broker import PaperBroker

async def main():
    engine = LiveTradingEngine(
        strategy=MyStrategy(),
        broker_adapter=PaperBroker(starting_cash=Decimal("100000")),
        data_portal=data_portal
    )

    try:
        await engine.run()
    except KeyboardInterrupt:
        print("Shutting down...")
        await engine.shutdown()
    except Exception as e:
        logger.error("engine_error", error=str(e))
        await engine.shutdown()
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Circuit Breakers ⚠️ **CRITICAL**

**Module**: `rustybt.live.circuit_breakers`

Multiple circuit breaker types to halt trading on risk limit violations.

**Import**:
```python
from rustybt.live.circuit_breakers import (
    CircuitBreakerManager,
    DrawdownCircuitBreaker,
    DailyLossCircuitBreaker,
    OrderRateCircuitBreaker,
    ErrorRateCircuitBreaker,
    ManualCircuitBreaker,
    CircuitBreakerState
)
```

**Example - Complete Circuit Breaker Setup**:
```python
from decimal import Decimal
from rustybt.live.circuit_breakers import CircuitBreakerManager

# Create coordinator
breakers = CircuitBreakerManager()

# 1. Drawdown breaker (RECOMMENDED) - Halt at 10% drawdown
breakers.add_breaker(
    DrawdownCircuitBreaker(
        max_drawdown_pct=Decimal("0.10"),  # Halt at 10% drawdown
        lookback_days=30                    # From 30-day peak
    )
)

# 2. Daily loss limit (RECOMMENDED) - Halt at $5K daily loss
breakers.add_breaker(
    DailyLossCircuitBreaker(
        max_daily_loss=Decimal("5000")  # Halt at $5K daily loss
    )
)

# 3. Order rate limit (prevents runaway algorithms)
breakers.add_breaker(
    OrderRateCircuitBreaker(
        max_orders_per_minute=10,        # Max 10 orders/min
        window_seconds=60
    )
)

# 4. Error rate limit (halts on repeated errors)
breakers.add_breaker(
    ErrorRateCircuitBreaker(
        max_errors=5,                    # Halt after 5 errors
        window_seconds=300               # In 5-minute window
    )
)

# 5. Manual halt capability (for emergencies)
manual_breaker = ManualCircuitBreaker()
breakers.add_breaker(manual_breaker)

# Check if breakers allow trading
if breakers.can_trade():
    # Submit orders
    await broker.submit_order(asset, amount, 'market')
else:
    # Breakers tripped, do not trade
    reasons = breakers.get_trip_reasons()
    logger.error("trading_halted", reasons=reasons)
```

**Circuit Breaker States**:
- `NORMAL`: All clear, trading allowed
- `TRIPPED`: Breaker tripped, trading halted
- `MANUALLY_HALTED`: Manual emergency stop
- `RESETTING`: Breaker resetting after trip

**⚠️ IMPORTANT**: Always include circuit breakers in live trading. They are your last line of defense against catastrophic losses.

### 3. State Management

**Module**: `rustybt.live.state_manager`

Automatic state checkpointing for crash recovery.

**Import**:
```python
from rustybt.live.state_manager import StateManager
from rustybt.live.models import StateCheckpoint
```

**Example - State Checkpointing**:
```python
from pathlib import Path
from rustybt.live.state_manager import StateManager

# Initialize state manager
state_manager = StateManager(
    checkpoint_dir=Path.home() / ".rustybt" / "state",
    staleness_threshold_seconds=3600  # Warn if checkpoint >1 hour old
)

# Save checkpoint (automatic in engine, shown for reference)
checkpoint = StateCheckpoint(
    timestamp=pd.Timestamp.now(),
    portfolio_value=Decimal("105000"),
    cash=Decimal("5000"),
    positions=[...],
    pending_orders=[...]
)
state_manager.save_checkpoint(
    strategy_name="my_strategy",
    state=checkpoint
)

# Restore after crash
restored_checkpoint = state_manager.load_checkpoint("my_strategy")
if restored_checkpoint:
    logger.info("state_restored",
                checkpoint_time=restored_checkpoint.timestamp,
                portfolio_value=restored_checkpoint.portfolio_value)

    # Check staleness
    if state_manager.is_stale(restored_checkpoint):
        logger.warning("stale_checkpoint",
                      age_seconds=state_manager.get_checkpoint_age(restored_checkpoint))
        # Consider position reconciliation critical
```

**State Checkpoint Contents**:
- Timestamp
- Portfolio value
- Cash balance
- Open positions (asset, amount, cost basis)
- Pending orders (order_id, asset, amount, status)
- Strategy state (custom strategy variables)

**Atomic Write Guarantee**: Checkpoints use temp file + rename pattern to prevent corruption from interrupted writes.

### 4. Position Reconciliation

**Module**: `rustybt.live.reconciler`

Verify local positions match broker positions.

**Import**:
```python
from rustybt.live.reconciler import PositionReconciler
from rustybt.live.models import (
    ReconciliationStrategy,
    PositionSnapshot,
    OrderSnapshot,
    DiscrepancySeverity
)
```

**Example - Position Reconciliation**:
```python
from decimal import Decimal
from rustybt.live.reconciler import PositionReconciler
from rustybt.live.models import ReconciliationStrategy

# Initialize reconciler
reconciler = PositionReconciler(
    broker_adapter=broker,
    reconciliation_strategy=ReconciliationStrategy.WARN_ONLY,  # or TRUST_BROKER, HALT_AND_ALERT
    cash_tolerance_pct=0.01  # 1% tolerance for cash differences
)

# Perform reconciliation (automatic in engine, shown for reference)
local_positions = [
    PositionSnapshot(asset=asset1, amount=Decimal("100"), cost_basis=Decimal("5000")),
    PositionSnapshot(asset=asset2, amount=Decimal("-50"), cost_basis=Decimal("-2500"))
]
local_cash = Decimal("10000")
local_orders = [
    OrderSnapshot(order_id="order1", asset=asset1, amount=Decimal("50"), status="pending")
]

report = await reconciler.reconcile_all(
    local_positions=local_positions,
    local_cash=local_cash,
    local_orders=local_orders
)

# Check for discrepancies
if report.has_discrepancies:
    logger.warning("position_discrepancies_found",
                   position_count=len(report.position_discrepancies),
                   cash_discrepancy=report.cash_discrepancy,
                   severity=report.max_severity.value)

    # Handle based on strategy
    if report.max_severity == DiscrepancySeverity.CRITICAL:
        # HALT_AND_ALERT: Stop trading
        await engine.pause()
        # Send alerts
        ...
    elif report.max_severity == DiscrepancySeverity.WARNING:
        # WARN_ONLY: Log but continue
        pass
```

**Reconciliation Strategies**:
- `WARN_ONLY`: Log discrepancies, continue trading
- `TRUST_BROKER`: Update local state to match broker
- `HALT_AND_ALERT`: Stop trading on discrepancies

**Discrepancy Types**:
- **Position**: Asset amount mismatch
- **Cash**: Cash balance mismatch (>1% by default)
- **Order**: Pending order status mismatch

**Severity Levels**:
- `INFO`: Minor differences within tolerance
- `WARNING`: Differences outside tolerance but not critical
- `CRITICAL`: Major differences requiring immediate attention

### 5. Trading Scheduler

**Module**: `rustybt.live.scheduler`

Schedule strategy callbacks at specific times or intervals.

**Import**:
```python
from rustybt.live.scheduler import TradingScheduler
```

**Example - Scheduled Rebalancing**:
```python
from rustybt.live.scheduler import TradingScheduler

# Initialize scheduler
scheduler = TradingScheduler(event_queue=engine.event_queue)
scheduler.start()

# Schedule rebalancing at market close (NYSE)
scheduler.schedule_market_close(
    callback=lambda: strategy.rebalance_portfolio(),
    exchange='NYSE',
    timezone='America/New_York'
)

# Schedule risk check every hour
scheduler.add_job(
    trigger='cron',
    callback=lambda: strategy.check_risk(),
    cron='0 * * * *'  # Every hour on the hour
)

# Schedule intraday rebalance at specific time
scheduler.add_job(
    trigger='cron',
    callback=lambda: strategy.rebalance_intraday(),
    cron='0 12 * * 1-5',  # 12:00 PM, Monday-Friday
    timezone='America/New_York'
)

# Schedule interval-based callback
scheduler.add_job(
    trigger='interval',
    callback=lambda: strategy.update_signals(),
    interval_minutes=15  # Every 15 minutes
)

# Remove callback
scheduler.remove_job('market_close_rebalance')
```

**Trigger Types**:
- `cron`: Cron expression (minute, hour, day, month, day_of_week)
- `interval`: Fixed interval (minutes, hours, days)
- `date`: One-time at specific datetime
- `market_open`: At market open (exchange-aware)
- `market_close`: At market close (exchange-aware)

---

## Broker Integration

### Broker Adapter Interface

All brokers implement the `BrokerAdapter` interface for strategy portability.

**Import**:
```python
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.assets import Asset
from decimal import Decimal
```

**Interface**:
```python
class BrokerAdapter(ABC):
    @abstractmethod
    async def connect(self) -> None:
        """Establish broker connection."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker."""

    @abstractmethod
    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None
    ) -> str:
        """Submit order, returns broker order ID."""

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order."""

    @abstractmethod
    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account balances."""

    @abstractmethod
    async def get_positions(self) -> list[dict]:
        """Get current positions."""

    @abstractmethod
    async def get_open_orders(self) -> list[dict]:
        """Get pending orders."""

    @abstractmethod
    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data."""

    @abstractmethod
    async def get_next_market_data(self) -> dict | None:
        """Get next market data tick (blocking)."""
```

### Available Broker Adapters

#### Paper Broker

**Module**: `rustybt.live.brokers.paper_broker`

**Use Case**: Strategy testing without real capital risk

**Features**:
- Realistic simulation (latency, slippage, commission, partial fills)
- Same execution models as backtest
- Volume-based partial fills
- Market data replay or real-time

**Example**:
```python
from rustybt.live.brokers.paper_broker import PaperBroker
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage
from decimal import Decimal

broker = PaperBroker(
    starting_cash=Decimal("100000"),
    commission_model=PerShareCommission(Decimal("0.005")),  # $0.005/share
    slippage_model=FixedBasisPointsSlippage(Decimal("5")),  # 5 bps
    order_latency_ms=100,                # 100ms network + exchange latency
    latency_jitter_pct=Decimal("0.20"),  # ±20% jitter
    volume_limit_pct=Decimal("0.025")    # Max 2.5% of bar volume
)

await broker.connect()
order_id = await broker.submit_order(
    asset=asset,
    amount=Decimal("100"),
    order_type="market"
)
```

**Recommended**: Always start here before live trading.

#### Binance Adapter

**Module**: `rustybt.live.brokers.binance_adapter`

**Asset Classes**: Crypto spot and futures

**Example**:
```python
from rustybt.live.brokers.binance_adapter import BinanceBrokerAdapter
import os

# ⚠️ ALWAYS secure credentials in environment variables
api_key = os.environ["BINANCE_API_KEY"]
api_secret = os.environ["BINANCE_API_SECRET"]

broker = BinanceBrokerAdapter(
    api_key=api_key,
    api_secret=api_secret,
    testnet=True  # Use testnet first!
)

await broker.connect()
# Use same interface as PaperBroker
```

#### Bybit Adapter

**Module**: `rustybt.live.brokers.bybit_adapter`

**Asset Classes**: Crypto perpetuals and futures

**Example**:
```python
from rustybt.live.brokers.bybit_adapter import BybitBrokerAdapter
import os

api_key = os.environ["BYBIT_API_KEY"]
api_secret = os.environ["BYBIT_API_SECRET"]

broker = BybitBrokerAdapter(
    api_key=api_key,
    api_secret=api_secret,
    testnet=True  # Use testnet first!
)

await broker.connect()
```

#### Interactive Brokers

**Module**: `rustybt.live.brokers.ib_adapter`

**Asset Classes**: Stocks, options, futures, forex

**Example**:
```python
from rustybt.live.brokers.ib_adapter import IBBrokerAdapter

broker = IBBrokerAdapter(
    host='127.0.0.1',  # TWS/IB Gateway host
    port=7497,         # TWS paper trading port (7496 for live)
    client_id=1
)

await broker.connect()
```

#### Hyperliquid Adapter

**Module**: `rustybt.live.brokers.hyperliquid_adapter`

**Asset Classes**: Decentralized perpetuals

**Example**:
```python
from rustybt.live.brokers.hyperliquid_adapter import HyperliquidBrokerAdapter
import os

# ⚠️ Wallet private key - HIGHLY SENSITIVE
private_key = os.environ["HYPERLIQUID_PRIVATE_KEY"]

broker = HyperliquidBrokerAdapter(
    private_key=private_key,
    testnet=True  # Use testnet first!
)

await broker.connect()
```

---

## WebSocket Streaming

**Module**: `rustybt.live.streaming`

Real-time market data via WebSocket with reconnection and error handling.

**Import**:
```python
from rustybt.live.streaming import BinanceWebSocketAdapter
from rustybt.live.streaming.models import StreamConfig, TickData
```

**Example - WebSocket Streaming**:
```python
from rustybt.live.streaming import BinanceWebSocketAdapter
from rustybt.live.streaming.models import StreamConfig

# Configure streaming
config = StreamConfig(
    heartbeat_interval=30,     # Send heartbeat every 30s
    heartbeat_timeout=90,      # Reconnect if no message for 90s
    reconnect_delay=5,         # Wait 5s before reconnect
    max_reconnect_attempts=10, # Max 10 reconnect attempts
    max_consecutive_errors=5   # Reconnect after 5 consecutive errors
)

# Initialize adapter
stream = BinanceWebSocketAdapter(
    url="wss://stream.binance.com:9443/ws",
    config=config,
    on_tick=lambda tick: handle_tick(tick)  # Callback for each tick
)

# Connect and subscribe
await stream.connect()
await stream.subscribe(
    symbols=["BTCUSDT", "ETHUSDT"],
    channels=["trade", "kline_1m"]
)

# Stream processes ticks automatically via on_tick callback
def handle_tick(tick: TickData):
    logger.info("tick_received",
                symbol=tick.symbol,
                price=str(tick.price),
                volume=str(tick.volume))
    # Push to engine event queue
    engine.push_market_data(tick)

# Disconnect when done
await stream.disconnect()
```

**StreamConfig Options**:
- `heartbeat_interval`: Heartbeat frequency (seconds)
- `heartbeat_timeout`: Reconnect timeout (seconds)
- `reconnect_delay`: Delay before reconnect (seconds)
- `max_reconnect_attempts`: Max reconnect attempts
- `max_consecutive_errors`: Reconnect after N errors

**Connection States**:
- `DISCONNECTED`: Not connected
- `CONNECTING`: Connection in progress
- `CONNECTED`: Connected and streaming
- `RECONNECTING`: Reconnecting after disconnect

---

## Shadow Trading

**Module**: `rustybt.live.shadow`

Parallel backtest validation of live trading signals.

Shadow trading runs a lightweight backtest engine in parallel with live trading, consuming the same market data to generate signals that can be compared with live signals. This validates that your strategy behaves the same in live and backtest environments.

**Import**:
```python
from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live import LiveTradingEngine
```

**Example - Shadow Trading**:
```python
from decimal import Decimal
from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live import LiveTradingEngine

# Configure shadow trading
shadow_config = ShadowTradingConfig(
    enabled=True,
    signal_tolerance_pct=Decimal("0.05"),      # 5% signal tolerance
    max_misalignment_count=3,                  # Halt after 3 misalignments
    execution_quality_threshold=Decimal("0.90"), # 90% fill rate required
    track_slippage=True,
    track_latency=True
)

# Enable shadow mode in engine
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=paper_broker,
    data_portal=data_portal,
    shadow_mode=True,            # Enable shadow trading
    shadow_config=shadow_config  # Shadow configuration
)

# Shadow engine runs automatically
await engine.run()

# Get shadow trading report
shadow_report = engine.get_shadow_report()
print(f"Signal alignment: {shadow_report.alignment_rate:.2%}")
print(f"Execution quality: {shadow_report.execution_quality:.2%}")
print(f"Avg slippage: {shadow_report.avg_slippage_bps} bps")
print(f"Avg latency: {shadow_report.avg_latency_ms} ms")
```

**Shadow Trading Validates**:
- **Signal Alignment**: Live and backtest generate same signals
- **Execution Quality**: Fill rates, slippage, latency
- **Performance Deviation**: Live vs. backtest returns

**When to Use**:
- ✅ Before deploying new strategies live
- ✅ After code changes to validate behavior
- ✅ Continuously in production for validation

**Circuit Breaker Integration**: Shadow trading can halt live trading if signal misalignment exceeds threshold.

---

## Production Deployment Checklist

### Pre-Deployment ⚠️ **MANDATORY**

- [ ] **Backtesting Complete**
  - [ ] Positive risk-adjusted returns (Sharpe >1.0)
  - [ ] Tested on ≥3 years of data
  - [ ] Walk-forward validation passed
  - [ ] Monte Carlo robustness testing passed

- [ ] **Paper Trading Complete**
  - [ ] ≥2 weeks of paper trading
  - [ ] Strategy behaves as expected
  - [ ] No unexpected errors
  - [ ] Fill rates acceptable
  - [ ] Slippage within tolerance

- [ ] **Shadow Trading Complete**
  - [ ] ≥1 week of shadow validation
  - [ ] Signal alignment >95%
  - [ ] Execution quality >90%
  - [ ] No major deviations from backtest

- [ ] **Safety Mechanisms Configured**
  - [ ] Circuit breakers enabled (drawdown, daily loss, order rate, error rate)
  - [ ] Position limits set per-asset and portfolio
  - [ ] State checkpointing enabled (≤60s intervals)
  - [ ] Position reconciliation enabled (≤5 min intervals)

- [ ] **Monitoring Setup**
  - [ ] Structured logging enabled
  - [ ] Log aggregation configured (e.g., Grafana Loki, ELK)
  - [ ] Alerts configured (email, SMS, PagerDuty)
  - [ ] Dashboard deployed (optional but recommended)

- [ ] **Infrastructure**
  - [ ] Server redundancy (primary + backup)
  - [ ] Network redundancy
  - [ ] Broker API credentials secured (environment variables, secrets manager)
  - [ ] State checkpoint directory backed up

### Deployment Process

1. **Small Position Sizing** (Week 1)
   - Start with 10% of target position size
   - Monitor for issues
   - Verify all safety mechanisms work

2. **Gradual Scale-Up** (Weeks 2-4)
   - Increase position size by 25% per week
   - Continue monitoring
   - Verify execution quality remains acceptable

3. **Full Deployment** (Week 5+)
   - Reach target position size
   - Continuous monitoring
   - Regular shadow trading validation

### Ongoing Monitoring

- **Daily**: Check execution logs, circuit breaker status, position reconciliation reports
- **Weekly**: Review shadow trading alignment, execution quality metrics
- **Monthly**: Full strategy performance review, compare to backtest expectations

---

## Common Patterns

### 1. Live Trading with Real Broker (Binance)

```python
import asyncio
import os
from decimal import Decimal
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers.binance_adapter import BinanceBrokerAdapter
from rustybt.live.circuit_breakers import CircuitBreakerManager, DrawdownCircuitBreaker

# ⚠️ ALWAYS secure credentials in environment variables
api_key = os.environ["BINANCE_API_KEY"]
api_secret = os.environ["BINANCE_API_SECRET"]

# Initialize Binance adapter
binance = BinanceBrokerAdapter(
    api_key=api_key,
    api_secret=api_secret,
    testnet=False  # ⚠️ Set to False for real trading (use True for testing)
)

# ⚠️ CRITICAL: Circuit breakers (NEVER skip this)
breakers = CircuitBreakerManager()
breakers.add_breaker(DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.05")))  # 5% max

# Initialize engine
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=binance,
    data_portal=data_portal,
    shadow_mode=True  # Enable shadow validation in production
)

async def main():
    try:
        await engine.run()
    except Exception as e:
        logger.error("engine_crashed", error=str(e))
        await engine.shutdown()
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Manual Emergency Halt

```python
from rustybt.live.circuit_breakers import ManualCircuitBreaker

# Add manual breaker to coordinator
manual_breaker = ManualCircuitBreaker()
breakers.add_breaker(manual_breaker)

# In case of emergency (e.g., via admin dashboard or CLI)
manual_breaker.trigger_halt(
    reason="Unexpected market conditions",
    operator="trader_john"
)

# Engine will halt immediately
# All pending orders cancelled
# Positions left as-is (not closed)
```

### 3. Crash Recovery

```python
from rustybt.live.state_manager import StateManager

state_manager = StateManager()

# On restart after crash
checkpoint = state_manager.load_checkpoint("my_strategy")

if checkpoint:
    logger.info("restoring_from_checkpoint",
                timestamp=checkpoint.timestamp,
                portfolio_value=checkpoint.portfolio_value)

    # Check if checkpoint is stale
    if state_manager.is_stale(checkpoint):
        logger.warning("stale_checkpoint_detected",
                      age_seconds=state_manager.get_checkpoint_age(checkpoint))

        # CRITICAL: Perform immediate position reconciliation
        report = await reconciler.reconcile_all(
            local_positions=checkpoint.positions,
            local_cash=checkpoint.cash,
            local_orders=checkpoint.pending_orders
        )

        if report.has_critical_discrepancies:
            # Manual review required
            logger.critical("critical_discrepancies_after_crash",
                          report=report.to_dict())
            raise RuntimeError("Manual review required after crash recovery")

    # Restore strategy state
    engine.restore_checkpoint(checkpoint)
    await engine.run()
else:
    logger.info("no_checkpoint_found", strategy="my_strategy")
    await engine.run()
```

---

## Best Practices

### Safety

1. **Always use paper trading first** - Test strategies for ≥2 weeks in paper mode
2. **Always enable circuit breakers** - Drawdown and daily loss breakers are mandatory
3. **Always enable position reconciliation** - Verify broker positions every 5 minutes
4. **Always enable state checkpointing** - Save state every 60 seconds
5. **Always use shadow trading in production** - Continuously validate signal alignment

### Error Handling

```python
from rustybt.exceptions import InsufficientFundsError, BrokerConnectionError, BrokerError

# GOOD: Comprehensive error handling
try:
    order_id = await broker.submit_order(asset, amount, 'market')
except InsufficientFundsError as e:
    logger.error("insufficient_funds", asset=asset.symbol, amount=str(amount))
    # Reduce position size or skip order
except BrokerConnectionError as e:
    logger.error("broker_connection_failed", error=str(e))
    # Trigger reconnection logic
except BrokerError as e:
    logger.error("order_submission_failed", asset=asset.symbol, error=str(e))
    # Alert operator, may need manual intervention
```

### Logging

```python
import structlog
logger = structlog.get_logger()

# GOOD: Structured logging with context
logger.info(
    "order_submitted",
    order_id=order_id,
    asset=asset.symbol,
    amount=str(amount),
    order_type=order_type,
    limit_price=str(limit_price) if limit_price else None
)

# GOOD: Log circuit breaker events
if breakers.any_tripped():
    logger.error(
        "circuit_breakers_tripped",
        breaker_types=[b.breaker_type.value for b in breakers.get_tripped()],
        reasons=[b.get_trip_reason() for b in breakers.get_tripped()]
    )
```

---

## Further Reading

- [Circuit Breakers](./core/circuit-breakers.md) - All circuit breaker types
- [Production Deployment](./production-deployment.md) - Deployment guide

---

## Related Documentation

- [Data Management](../data-management/README.md) - Historical data access
- [Order Management](../order-management/README.md) - Order types and execution
- [Portfolio Management](../portfolio-management/README.md) - Position and risk tracking
- [Analytics](../analytics/README.md) - Performance analysis

---

**⚠️ FINAL REMINDER**: Live trading involves real capital at risk. Always follow the recommended progression: Backtest → Paper Trading → Shadow Trading → Small Live Position → Full Live Trading. Never skip safety mechanisms.
