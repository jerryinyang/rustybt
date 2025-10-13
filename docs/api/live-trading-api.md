# Live Trading API Reference

**Last Updated**: 2024-10-11

## Overview

The Live Trading module provides production-ready infrastructure for executing trading strategies in real-time markets. It supports multiple brokers, real-time data streaming, position reconciliation, state management, and shadow trading validation.

---

## Core Classes

### LiveTradingEngine

The main orchestrator for live trading operations.

```python
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers import PaperBroker
from rustybt import TradingAlgorithm

engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=PaperBroker(),
    data_portal=portal
)
await engine.run()
```

#### Constructor

```python
LiveTradingEngine(
    strategy: TradingAlgorithm,
    broker_adapter: BrokerAdapter,
    data_portal: Any,
    portfolio: Optional[Any] = None,
    account: Optional[Any] = None,
    scheduler: Optional[Any] = None,
    state_manager: Optional[StateManager] = None,
    checkpoint_interval_seconds: int = 60,
    reconciliation_strategy: ReconciliationStrategy = ReconciliationStrategy.WARN_ONLY,
    reconciliation_interval_seconds: int = 300,
    shadow_mode: bool = False,
    shadow_config: Optional[ShadowTradingConfig] = None,
)
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | `TradingAlgorithm` | Required | Strategy instance (same class used in backtesting) |
| `broker_adapter` | `BrokerAdapter` | Required | Broker adapter for order execution and market data |
| `data_portal` | `Any` | Required | PolarsDataPortal for historical data access |
| `portfolio` | `Optional[Any]` | `None` | Portfolio object (auto-created if None) |
| `account` | `Optional[Any]` | `None` | Account object (auto-created if None) |
| `scheduler` | `Optional[Any]` | `None` | Trading scheduler for scheduled callbacks |
| `state_manager` | `Optional[StateManager]` | `None` | StateManager for checkpoint/restore |
| `checkpoint_interval_seconds` | `int` | `60` | How often to save state (seconds) |
| `reconciliation_strategy` | `ReconciliationStrategy` | `WARN_ONLY` | Strategy for position reconciliation |
| `reconciliation_interval_seconds` | `int` | `300` | How often to reconcile positions (seconds) |
| `shadow_mode` | `bool` | `False` | Enable shadow backtest validation |
| `shadow_config` | `Optional[ShadowTradingConfig]` | `None` | Shadow trading configuration |

#### Methods

##### `async run() -> None`

Start the live trading engine. Runs until `graceful_shutdown()` is called.

```python
await engine.run()
```

**Behavior**:
1. Restores state from checkpoint if available
2. Connects to broker
3. Initializes strategy
4. Starts checkpoint scheduler
5. Starts position reconciliation
6. Enters main event loop
7. Processes market data and order events

**Raises**:
- `BrokerConnectionError`: If broker connection fails
- `StateRestoreError`: If state restoration fails

##### `async graceful_shutdown() -> None`

Gracefully shutdown the engine.

```python
await engine.graceful_shutdown()
```

**Behavior**:
1. Stops accepting new events
2. Processes remaining events in queue
3. Creates final checkpoint
4. Closes all positions (if configured)
5. Disconnects from broker
6. Logs shutdown metrics

##### `async force_reconciliation() -> AlignmentMetrics`

Manually trigger position reconciliation.

```python
metrics = await engine.force_reconciliation()
print(f"Position alignment: {metrics.alignment_score}")
```

**Returns**: `AlignmentMetrics` with position alignment status

---

## Broker Adapters

### BrokerAdapter (Abstract Base Class)

All broker adapters implement this interface.

```python
from rustybt.live.brokers.base import BrokerAdapter
```

#### Required Methods

##### `async connect() -> None`

Establish connection to broker.

```python
await broker.connect()
```

**Raises**:
- `BrokerConnectionError`: If connection fails

##### `async disconnect() -> None`

Disconnect from broker.

```python
await broker.disconnect()
```

##### `async submit_order() -> str`

Submit order to broker.

```python
order_id = await broker.submit_order(
    asset=asset,
    amount=Decimal("100"),  # Positive = buy
    order_type="market"
)
```

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `asset` | `Asset` | Yes | Asset to trade |
| `amount` | `Decimal` | Yes | Quantity (positive=buy, negative=sell) |
| `order_type` | `str` | Yes | `'market'`, `'limit'`, `'stop'`, `'stop-limit'` |
| `limit_price` | `Optional[Decimal]` | No | Limit price for limit/stop-limit orders |
| `stop_price` | `Optional[Decimal]` | No | Stop price for stop/stop-limit orders |

**Returns**: Broker's order ID (string)

**Raises**:
- `InsufficientFundsError`: If account has insufficient funds
- `InvalidOrderError`: If order parameters are invalid
- `BrokerError`: If order submission fails

##### `async cancel_order(broker_order_id: str) -> None`

Cancel pending order.

```python
await broker.cancel_order("ORDER_123456")
```

**Raises**:
- `OrderNotFoundError`: If order doesn't exist
- `BrokerError`: If cancellation fails

##### `async get_account_info() -> Dict[str, Decimal]`

Get account information.

```python
info = await broker.get_account_info()
print(f"Cash: ${info['cash']}")
print(f"Equity: ${info['equity']}")
print(f"Buying Power: ${info['buying_power']}")
```

**Returns**: Dict with keys:
- `cash`: Available cash
- `equity`: Total account equity
- `buying_power`: Available buying power
- `margin_used`: Margin currently in use (if applicable)

##### `async get_positions() -> List[Dict]`

Get current positions.

```python
positions = await broker.get_positions()
for pos in positions:
    print(f"{pos['asset']}: {pos['amount']} @ {pos['cost_basis']}")
```

**Returns**: List of dicts with keys:
- `asset`: Asset symbol
- `amount`: Position size
- `cost_basis`: Average cost basis
- `market_value`: Current market value
- `unrealized_pnl`: Unrealized P&L

##### `async get_open_orders() -> List[Dict]`

Get open/pending orders.

```python
orders = await broker.get_open_orders()
for order in orders:
    print(f"{order['order_id']}: {order['asset']} {order['amount']}")
```

**Returns**: List of dicts with keys:
- `order_id`: Broker's order ID
- `asset`: Asset symbol
- `amount`: Order quantity
- `status`: Order status (`'pending'`, `'submitted'`, `'open'`)
- `order_type`: Order type
- `limit_price`: Limit price (if applicable)
- `stop_price`: Stop price (if applicable)

##### `async subscribe_market_data(assets: List[Asset]) -> None`

Subscribe to real-time market data.

```python
await broker.subscribe_market_data([asset1, asset2])
```

**Raises**:
- `BrokerError`: If subscription fails

##### `async get_next_market_data() -> Optional[Dict]`

Get next market data update (blocking).

```python
data = await broker.get_next_market_data()
if data:
    print(f"{data['asset']}: ${data['close']}")
```

**Returns**: Dict with keys:
- `asset`: Asset symbol
- `open`: Open price
- `high`: High price
- `low`: Low price
- `close`: Close price
- `volume`: Volume
- `timestamp`: Data timestamp

Returns `None` if no data available.

##### `async get_current_price(asset: Asset) -> Decimal`

Get current price for asset.

```python
price = await broker.get_current_price(asset)
```

**Returns**: Current price as `Decimal`

**Raises**:
- `DataNotFoundError`: If price not available
- `BrokerError`: If request fails

##### `is_connected() -> bool`

Check if broker connection is active.

```python
if broker.is_connected():
    print("Connected to broker")
```

**Returns**: `True` if connected, `False` otherwise

---

## Built-in Broker Adapters

### PaperBroker

Simulated broker for testing.

```python
from rustybt.live.brokers import PaperBroker

broker = PaperBroker(
    starting_cash=Decimal("100000"),
    commission_model=None,
    slippage_model=None
)
```

**Parameters**:
- `starting_cash`: Initial capital (default: `Decimal("100000")`)
- `commission_model`: Commission model (default: zero commission)
- `slippage_model`: Slippage model (default: zero slippage)

**Use Case**: Strategy development and testing without real capital.

---

### CCXTBrokerAdapter

Cryptocurrency exchanges via CCXT library.

```python
from rustybt.live.brokers import CCXTBrokerAdapter

broker = CCXTBrokerAdapter(
    exchange_id='binance',
    api_key='YOUR_API_KEY',
    api_secret='YOUR_API_SECRET',
    testnet=True,
    rate_limit=True
)
```

**Parameters**:
- `exchange_id`: Exchange name (e.g., `'binance'`, `'coinbase'`, `'kraken'`)
- `api_key`: API key
- `api_secret`: API secret
- `testnet`: Use testnet (default: `False`)
- `rate_limit`: Enable rate limiting (default: `True`)
- `sandbox`: Use sandbox mode (default: `False`)

**Supported Exchanges**:
- Binance
- Coinbase Pro
- Kraken
- Bybit
- OKX
- And 100+ more (see [CCXT documentation](https://github.com/ccxt/ccxt))

**Example**:
```python
# Binance testnet
broker = CCXTBrokerAdapter(
    exchange_id='binance',
    api_key=os.getenv('BINANCE_API_KEY'),
    api_secret=os.getenv('BINANCE_API_SECRET'),
    testnet=True
)
await broker.connect()
```

---

### BinanceBrokerAdapter

Optimized Binance adapter with WebSocket streaming.

```python
from rustybt.live.brokers import BinanceBrokerAdapter

broker = BinanceBrokerAdapter(
    api_key='YOUR_API_KEY',
    api_secret='YOUR_API_SECRET',
    testnet=True
)
```

**Parameters**:
- `api_key`: Binance API key
- `api_secret`: Binance API secret
- `testnet`: Use testnet (default: `False`)

**Features**:
- WebSocket market data streaming
- Optimized order submission
- User data stream (order updates)

---

### BybitBrokerAdapter

Bybit derivatives exchange adapter.

```python
from rustybt.live.brokers import BybitBrokerAdapter

broker = BybitBrokerAdapter(
    api_key='YOUR_API_KEY',
    api_secret='YOUR_API_SECRET',
    testnet=True
)
```

**Parameters**:
- `api_key`: Bybit API key
- `api_secret`: Bybit API secret
- `testnet`: Use testnet (default: `False`)

**Features**:
- Perpetual futures support
- Leveraged positions
- WebSocket streaming

---

### HyperliquidBrokerAdapter

Hyperliquid DEX adapter.

```python
from rustybt.live.brokers import HyperliquidBrokerAdapter

broker = HyperliquidBrokerAdapter(
    api_key='YOUR_API_KEY',
    api_secret='YOUR_API_SECRET',
    testnet=True
)
```

**Parameters**:
- `api_key`: Hyperliquid API key
- `api_secret`: Hyperliquid API secret
- `testnet`: Use testnet (default: `False`)

**Features**:
- Decentralized perpetuals
- On-chain settlement
- WebSocket L2 orderbook data

---

### IBBrokerAdapter

Interactive Brokers adapter (TWS/Gateway required).

```python
from rustybt.live.brokers import IBBrokerAdapter

broker = IBBrokerAdapter(
    host='127.0.0.1',
    port=7497,  # TWS paper trading port
    client_id=1
)
```

**Parameters**:
- `host`: TWS/Gateway host (default: `'127.0.0.1'`)
- `port`: TWS/Gateway port (default: `7497` for paper trading)
- `client_id`: Client ID (default: `1`)

**Prerequisites**:
- Interactive Brokers account
- TWS or IB Gateway installed and running
- Enable API connections in TWS settings

**Use Case**: Traditional equity and options trading.

---

## State Management

### StateManager

Manages engine state persistence and recovery.

```python
from rustybt.live import StateManager

state_manager = StateManager(
    checkpoint_dir="/path/to/checkpoints"
)
```

#### Methods

##### `async save_checkpoint(checkpoint: StateCheckpoint) -> None`

Save state checkpoint.

```python
checkpoint = StateCheckpoint(
    timestamp=pd.Timestamp.now(),
    positions={...},
    orders={...},
    cash=Decimal("100000")
)
await state_manager.save_checkpoint(checkpoint)
```

##### `async load_latest_checkpoint() -> Optional[StateCheckpoint]`

Load most recent checkpoint.

```python
checkpoint = await state_manager.load_latest_checkpoint()
if checkpoint:
    print(f"Restored state from {checkpoint.timestamp}")
```

**Returns**: `StateCheckpoint` if found, `None` otherwise

---

## Position Reconciliation

### PositionReconciler

Reconciles engine positions with broker positions.

```python
from rustybt.live import PositionReconciler, ReconciliationStrategy

reconciler = PositionReconciler(
    broker_adapter=broker,
    strategy=ReconciliationStrategy.AUTO_ADJUST
)
```

#### ReconciliationStrategy Enum

| Strategy | Behavior |
|----------|----------|
| `WARN_ONLY` | Log discrepancies but don't adjust |
| `AUTO_ADJUST` | Automatically adjust engine positions to match broker |
| `HALT_ON_MISMATCH` | Stop trading on any discrepancy |
| `MANUAL_APPROVAL` | Require manual confirmation before adjustment |

#### Methods

##### `async reconcile() -> AlignmentMetrics`

Perform position reconciliation.

```python
metrics = await reconciler.reconcile()
print(f"Alignment score: {metrics.alignment_score}")
print(f"Discrepancies: {metrics.discrepancy_count}")
```

**Returns**: `AlignmentMetrics` with reconciliation results

---

## Shadow Trading

### ShadowBacktestEngine

Runs parallel backtest to validate live strategy.

```python
from rustybt.live.shadow import ShadowBacktestEngine, ShadowTradingConfig

config = ShadowTradingConfig(
    tolerance_percent=Decimal("0.02"),  # 2% tolerance
    alert_on_divergence=True
)

shadow = ShadowBacktestEngine(
    strategy=strategy,
    config=config,
    starting_cash=Decimal("100000")
)
```

#### ShadowTradingConfig

```python
@dataclass
class ShadowTradingConfig:
    tolerance_percent: Decimal = Decimal("0.02")
    alert_on_divergence: bool = True
    halt_on_large_divergence: bool = False
    large_divergence_threshold: Decimal = Decimal("0.10")
    enable_dashboard: bool = True
```

#### Methods

##### `async start() -> None`

Start shadow engine.

```python
await shadow.start()
```

##### `async process_market_data(timestamp: pd.Timestamp, market_data: Dict) -> None`

Process market data in shadow backtest.

```python
await shadow.process_market_data(
    timestamp=pd.Timestamp.now(),
    market_data={'AAPL': {'close': Decimal("150.00")}}
)
```

##### `check_alignment() -> bool`

Check if live and shadow are aligned.

```python
if not shadow.check_alignment():
    print("WARNING: Shadow divergence detected!")
```

**Returns**: `True` if aligned, `False` if diverged

##### `get_alignment_metrics() -> AlignmentMetrics`

Get detailed alignment metrics.

```python
metrics = shadow.get_alignment_metrics()
print(f"Portfolio value diff: ${metrics.portfolio_value_diff}")
print(f"Position discrepancies: {metrics.position_discrepancies}")
```

---

## Event System

### Event Types

All events inherit from base `Event` class with priority ordering.

#### MarketDataEvent

Market data update event (Priority: 5 - lowest).

```python
from rustybt.live.events import MarketDataEvent

event = MarketDataEvent(
    asset_symbol='AAPL',
    timestamp=pd.Timestamp.now(),
    data={
        'open': Decimal("150.00"),
        'high': Decimal("152.00"),
        'low': Decimal("149.00"),
        'close': Decimal("151.00"),
        'volume': Decimal("1000000")
    }
)
```

#### OrderFillEvent

Order fill notification (Priority: 2 - high).

```python
from rustybt.live.events import OrderFillEvent

event = OrderFillEvent(
    order_id='ORD123',
    asset_symbol='AAPL',
    filled_amount=Decimal("100"),
    fill_price=Decimal("150.50"),
    fill_timestamp=pd.Timestamp.now()
)
```

#### OrderRejectEvent

Order rejection notification (Priority: 3).

```python
from rustybt.live.events import OrderRejectEvent

event = OrderRejectEvent(
    order_id='ORD123',
    reject_reason='Insufficient funds',
    reject_timestamp=pd.Timestamp.now()
)
```

#### SystemErrorEvent

System error event (Priority: 1 - highest).

```python
from rustybt.live.events import SystemErrorEvent

event = SystemErrorEvent(
    error_type='broker_connection',
    error_message='Connection timeout',
    exception_details='...',
    error_timestamp=asyncio.get_event_loop().time()
)
```

---

## Circuit Breakers

### CircuitBreaker

Implements circuit breaker pattern for risk management.

```python
from rustybt.live import CircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    max_daily_loss=Decimal("5000"),
    max_position_size=Decimal("50000"),
    max_leverage=Decimal("2.0")
)

breaker = CircuitBreaker(config)
```

#### Methods

##### `check_trade(trade: Dict) -> bool`

Check if trade violates limits.

```python
if not breaker.check_trade({'value': Decimal("10000")}):
    print("Trade rejected by circuit breaker")
```

**Returns**: `True` if trade allowed, `False` if rejected

##### `trip() -> None`

Manually trip the circuit breaker.

```python
breaker.trip()
```

##### `reset() -> None`

Reset the circuit breaker.

```python
breaker.reset()
```

---

## Complete Example

```python
import asyncio
import os
from decimal import Decimal
from rustybt import TradingAlgorithm
from rustybt.live import LiveTradingEngine, ReconciliationStrategy
from rustybt.live.brokers import CCXTBrokerAdapter
from rustybt.live.shadow import ShadowTradingConfig
from rustybt.data.polars import PolarsDataPortal

class MyStrategy(TradingAlgorithm):
    def initialize(self):
        self.symbols = ['BTC/USDT']

    def handle_data(self, context, data):
        price = data.current(self.symbols[0], 'close')
        # Trading logic here

async def main():
    # Create broker adapter
    broker = CCXTBrokerAdapter(
        exchange_id='binance',
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET'),
        testnet=True
    )

    # Create data portal
    portal = PolarsDataPortal(bundle_name='crypto-data')

    # Configure shadow trading
    shadow_config = ShadowTradingConfig(
        tolerance_percent=Decimal("0.02"),
        alert_on_divergence=True
    )

    # Create engine
    engine = LiveTradingEngine(
        strategy=MyStrategy(),
        broker_adapter=broker,
        data_portal=portal,
        checkpoint_interval_seconds=60,
        reconciliation_strategy=ReconciliationStrategy.AUTO_ADJUST,
        reconciliation_interval_seconds=300,
        shadow_mode=True,
        shadow_config=shadow_config
    )

    # Run engine
    try:
        await engine.run()
    except KeyboardInterrupt:
        print("Shutting down...")
        await engine.graceful_shutdown()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## See Also

- [Broker Setup Guide](../guides/broker-setup-guide.md)
- [Live vs Backtest Data](../guides/live-vs-backtest-data.md)
- [WebSocket Streaming Guide](../guides/websocket-streaming-guide.md)
- [Exception Handling Guide](../guides/exception-handling.md)
