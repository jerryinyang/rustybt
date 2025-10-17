# WebSocket Streaming Guide

**Last Updated**: 2024-10-11

## Overview

WebSocket streaming provides real-time market data for live trading strategies. This guide covers WebSocket connection management, data processing, and integration with RustyBT's live trading engine.

---

## Table of Contents

1. [Why WebSockets?](#why-websockets)
2. [Supported Exchanges](#supported-exchanges)
3. [Basic Usage](#basic-usage)
4. [Data Aggregation](#data-aggregation)
5. [Multiple Streams](#multiple-streams)
6. [Error Handling](#error-handling)
7. [Performance Optimization](#performance-optimization)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Why WebSockets?

### REST API vs WebSocket

| Feature | REST API | WebSocket |
|---------|----------|-----------|
| **Latency** | 100-500ms per request | 10-50ms (persistent connection) |
| **Updates** | Poll (wastes bandwidth) | Push (server initiated) |
| **Rate Limits** | Strict (e.g., 1200 req/min) | More generous (e.g., 5000 msg/min) |
| **Cost** | Higher (multiple requests) | Lower (single connection) |
| **Use Case** | Historical data, infrequent updates | Real-time trading, tick data |

**When to Use WebSockets**:
- ✅ Live trading with real-time execution
- ✅ High-frequency strategies (< 1 minute intervals)
- ✅ Monitoring multiple assets simultaneously
- ✅ Tick-by-tick data analysis
- ❌ Historical backtesting (use REST API)
- ❌ Daily/hourly rebalancing (REST is sufficient)

---

## Supported Exchanges

RustyBT provides WebSocket adapters for:

### Cryptocurrency Exchanges

| Exchange | Adapter | Features |
|----------|---------|----------|
| **Binance** | `BinanceWebSocketAdapter` | Orderbook, trades, klines |
| **Bybit** | `BybitWebSocketAdapter` | Perpetuals, orderbook L2 |
| **Hyperliquid** | `HyperliquidWebSocketAdapter` | DEX orderbook, trades |
| **CCXT Generic** | `CCXTWebSocketAdapter` | 100+ exchanges via CCXT |

### Traditional Brokers

| Broker | Adapter | Features |
|--------|---------|----------|
| **Interactive Brokers** | `IBBrokerAdapter` | TWS/Gateway streaming |
| **Alpaca** | Via REST fallback | Polling mode |

---

## Basic Usage

### Example: Binance WebSocket

```python
import asyncio
from rustybt.live.streaming.binance_stream import BinanceWebSocketAdapter

async def stream_binance():
    # Create adapter
    adapter = BinanceWebSocketAdapter(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET'),
        testnet=True
    )

    # Connect
    await adapter.connect()

    # Subscribe to symbols
    await adapter.subscribe(['BTC/USDT', 'ETH/USDT'])

    # Start streaming
    queue = await adapter.stream()

    # Process data
    while True:
        bar = await queue.get()
        print(f"{bar.symbol}: ${bar.close:.2f} @ {bar.timestamp}")

    # Disconnect
    await adapter.disconnect()

asyncio.run(stream_binance())
```

### Data Format

WebSocket adapters return `OHLCVBar` objects:

```python
from rustybt.live.streaming import OHLCVBar

@dataclass
class OHLCVBar:
    symbol: str               # 'BTC/USDT'
    timestamp: datetime       # UTC timestamp (bar start)
    open: Decimal             # Bar open price
    high: Decimal             # Bar high price
    low: Decimal              # Bar low price
    close: Decimal            # Bar close price
    volume: Decimal           # Bar volume
```

---

## Data Aggregation

### Aggregating Ticks to Bars

WebSocket data often comes as individual ticks. Aggregate them into OHLCV bars:

```python
from collections import deque
from decimal import Decimal
import pandas as pd

class BarAggregator:
    """Aggregate ticks into time-based bars."""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._ticks = deque(maxlen=1000)
        self._current_bar = None

    def add_tick(self, tick: OHLCVBar):
        """Add tick and update current bar."""
        if self._current_bar is None:
            # Start new bar
            self._current_bar = {
                'open': tick.open,
                'high': tick.high,
                'low': tick.low,
                'close': tick.close,
                'volume': tick.volume,
                'start_time': tick.timestamp
            }
        else:
            # Update bar
            self._current_bar['high'] = max(self._current_bar['high'], tick.high)
            self._current_bar['low'] = min(self._current_bar['low'], tick.low)
            self._current_bar['close'] = tick.close
            self._current_bar['volume'] += tick.volume

        # Check if window elapsed
        elapsed = (tick.timestamp - self._current_bar['start_time']).total_seconds()
        if elapsed >= self.window_seconds:
            completed_bar = self._current_bar
            self._current_bar = None
            return completed_bar

        return None

# Usage
aggregator = BarAggregator(window_seconds=60)

while True:
    tick = await queue.get()
    bar = aggregator.add_tick(tick)

    if bar:
        print(f"Completed 1-min bar: O={bar['open']:.2f} C={bar['close']:.2f}")
```

---

## Multiple Streams

### Concurrent WebSocket Connections

Handle multiple symbol streams simultaneously:

```python
import asyncio

async def multi_stream_example():
    # Create adapters for different exchanges
    binance = BinanceWebSocketAdapter(...)
    bybit = BybitWebSocketAdapter(...)

    # Connect all
    await asyncio.gather(
        binance.connect(),
        bybit.connect()
    )

    # Subscribe
    await binance.subscribe(['BTC/USDT'])
    await bybit.subscribe(['BTC-PERP'])

    # Start streams
    binance_queue = await binance.stream()
    bybit_queue = await bybit.stream()

    # Process both streams concurrently
    async def process_binance():
        while True:
            bar = await binance_queue.get()
            # Handle Binance data

    async def process_bybit():
        while True:
            bar = await bybit_queue.get()
            # Handle Bybit data

    await asyncio.gather(
        process_binance(),
        process_bybit()
    )
```

### Stream Manager

Manage multiple streams with a central coordinator:

```python
class StreamManager:
    """Manage multiple WebSocket connections."""

    def __init__(self):
        self.adapters = {}
        self.queues = {}

    async def add_stream(self, name: str, adapter, symbols: list):
        """Add a new stream."""
        await adapter.connect()
        await adapter.subscribe(symbols)
        queue = await adapter.stream()

        self.adapters[name] = adapter
        self.queues[name] = queue

    async def get_next(self, name: str):
        """Get next bar from named stream."""
        return await self.queues[name].get()

    async def close_all(self):
        """Close all streams."""
        for adapter in self.adapters.values():
            await adapter.disconnect()

# Usage
manager = StreamManager()
await manager.add_stream('binance', binance_adapter, ['BTC/USDT'])
await manager.add_stream('bybit', bybit_adapter, ['BTC-PERP'])

bar = await manager.get_next('binance')
```

---

## Error Handling

### Connection Errors

Handle connection failures with automatic reconnection:

```python
class RobustWebSocketAdapter:
    """WebSocket adapter with auto-reconnect."""

    def __init__(self, adapter, max_retries=5):
        self.adapter = adapter
        self.max_retries = max_retries

    async def connect_with_retry(self):
        """Connect with exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                await self.adapter.connect()
                return
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise

                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Connection failed, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

    async def stream_with_reconnect(self):
        """Stream with automatic reconnection."""
        queue = asyncio.Queue()

        async def reconnect_loop():
            while True:
                try:
                    await self.connect_with_retry()

                    # Start streaming
                    stream_queue = await self.adapter.stream()

                    # Forward data to main queue
                    while True:
                        bar = await stream_queue.get()
                        await queue.put(bar)

                except Exception as e:
                    print(f"Stream error: {e}, reconnecting...")
                    await asyncio.sleep(5)

        # Start reconnection loop in background
        asyncio.create_task(reconnect_loop())

        return queue
```

### Data Validation

Validate incoming data for anomalies:

```python
def validate_bar(bar: OHLCVBar) -> bool:
    """Validate streaming bar data."""
    # Check OHLCV relationships
    if bar.high < bar.low:
        logger.warning("Invalid bar: high < low", bar=bar)
        return False

    if bar.close > bar.high or bar.close < bar.low:
        logger.warning("Invalid bar: close outside range", bar=bar)
        return False

    # Check for zero/negative prices
    if bar.close <= 0 or bar.volume < 0:
        logger.warning("Invalid bar: negative price/volume", bar=bar)
        return False

    # Check for excessive price movement (circuit breaker)
    if hasattr(self, 'last_price'):
        change_pct = abs((bar.close - self.last_price) / self.last_price)
        if change_pct > 0.10:  # 10% circuit breaker
            logger.warning("Excessive price movement", change_pct=change_pct)
            return False

    self.last_price = bar.close
    return True

# Usage
while True:
    bar = await queue.get()
    if validate_bar(bar):
        process_bar(bar)
```

---

## Performance Optimization

### 1. Batch Processing

Process bars in batches for efficiency:

```python
async def batch_processor(queue, batch_size=10, timeout=1.0):
    """Process bars in batches."""
    batch = []

    while True:
        try:
            # Collect batch
            while len(batch) < batch_size:
                bar = await asyncio.wait_for(queue.get(), timeout=timeout)
                batch.append(bar)
        except asyncio.TimeoutError:
            # Timeout - process partial batch
            pass

        if batch:
            # Process entire batch
            process_batch(batch)
            batch = []

def process_batch(bars):
    """Process multiple bars at once."""
    # Convert to DataFrame for vectorized operations
    df = pd.DataFrame([{
        'symbol': b.symbol,
        'timestamp': b.timestamp,
        'close': float(b.close),
        'volume': float(b.volume)
    } for b in bars])

    # Vectorized calculations
    df['vwap'] = (df['close'] * df['volume']).sum() / df['volume'].sum()
    # ...
```

### 2. Async Queue Sizing

Tune queue sizes for your use case:

```python
# Small queue (low latency, may drop data if consumer slow)
queue = asyncio.Queue(maxsize=100)

# Large queue (high throughput, higher latency)
queue = asyncio.Queue(maxsize=10000)

# Infinite queue (risk of memory growth)
queue = asyncio.Queue()  # No maxsize
```

### 3. Selective Subscriptions

Only subscribe to symbols you're trading:

```python
# ❌ Bad: Subscribe to everything
await adapter.subscribe(['BTC/USDT', 'ETH/USDT', 'ADA/USDT', ...])  # 100+ symbols

# ✅ Good: Subscribe only to active positions
active_symbols = list(context.portfolio.positions.keys())
await adapter.subscribe([s.symbol for s in active_symbols])
```

---

## Best Practices

### 1. Heartbeat Monitoring

Monitor connection health:

```python
class HeartbeatMonitor:
    """Monitor WebSocket connection health."""

    def __init__(self, timeout_seconds=30):
        self.timeout_seconds = timeout_seconds
        self.last_message_time = None

    def on_message(self):
        """Call this when message received."""
        self.last_message_time = asyncio.get_event_loop().time()

    def is_alive(self) -> bool:
        """Check if connection is alive."""
        if self.last_message_time is None:
            return False

        elapsed = asyncio.get_event_loop().time() - self.last_message_time
        return elapsed < self.timeout_seconds

# Usage
monitor = HeartbeatMonitor(timeout_seconds=30)

async def stream_with_heartbeat():
    while True:
        bar = await queue.get()
        monitor.on_message()

        if not monitor.is_alive():
            logger.warning("Heartbeat timeout, reconnecting...")
            await reconnect()
```

### 2. Graceful Shutdown

Handle shutdown cleanly:

```python
import signal

shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """Handle shutdown signal."""
    shutdown_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def graceful_stream():
    adapter = BinanceWebSocketAdapter(...)
    await adapter.connect()
    queue = await adapter.stream()

    try:
        while not shutdown_event.is_set():
            bar = await asyncio.wait_for(queue.get(), timeout=1.0)
            process_bar(bar)
    except asyncio.TimeoutError:
        pass
    finally:
        print("Shutting down...")
        await adapter.disconnect()
        print("Disconnected gracefully")
```

### 3. Rate Limit Respect

Even WebSockets have rate limits:

```python
# Binance: 5 subscriptions per second
async def batch_subscribe(adapter, symbols, batch_size=5):
    """Subscribe in batches to respect rate limits."""
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        await adapter.subscribe(batch)
        await asyncio.sleep(1)  # 1 second between batches
```

---

## Troubleshooting

### Common Issues

#### "Connection refused"

**Cause**: WebSocket endpoint unavailable or wrong URL

**Solutions**:
- Check adapter configuration
- Verify exchange status page
- Try testnet endpoint first

#### "Too many open connections"

**Cause**: Exceeded concurrent connection limit

**Solutions**:
- Close unused connections
- Use single connection with multiple subscriptions
- Check exchange limits (e.g., Binance: 10 connections per IP)

#### "Message rate exceeded"

**Cause**: Receiving more messages than you can process

**Solutions**:
- Increase queue size
- Process in batches
- Filter unnecessary subscriptions

#### "Disconnected unexpectedly"

**Cause**: Network issues, exchange maintenance, or idle timeout

**Solutions**:
- Implement auto-reconnect
- Send periodic ping/pong messages
- Check exchange scheduled maintenance

### Debug Mode

Enable debug logging:

```python
import structlog

# Configure debug logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)

logger = structlog.get_logger()
logger.debug("WebSocket message received", data=bar)
```

---

## Next Steps

- **Example**: <!-- WebSocket Example (Coming soon) -->
- **Live Trading Guide**: [Live vs Backtest Data](live-vs-backtest-data.md)
- **Broker Setup**: [Broker Setup Guide](broker-setup-guide.md)
- **API Reference**: Live Trading API (Coming soon)

---

**Last Updated**: 2024-10-11
