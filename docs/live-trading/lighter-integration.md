# Lighter.xyz Integration Guide

Comprehensive documentation for integrating rustybt with Lighter.xyz, a high-performance DeFi perpetual futures DEX.

## Table of Contents

- [Overview](#overview)
- [Broker Adapter](#broker-adapter)
  - [Authentication](#authentication)
  - [Order Submission](#order-submission)
  - [Position Queries](#position-queries)
  - [Paper Trading Mode](#paper-trading-mode)
  - [Error Handling](#error-handling)
- [Data Adapter](#data-adapter)
  - [Asset Discovery](#asset-discovery)
  - [OHLCV Fetching](#ohlcv-fetching)
  - [Timeframe Options](#timeframe-options)
  - [Funding Rates](#funding-rates)
  - [Bundle Integration](#bundle-integration)
- [Streaming Adapter](#streaming-adapter)
  - [WebSocket Connection](#websocket-connection)
  - [Channel Subscriptions](#channel-subscriptions)
  - [Message Handling](#message-handling)
  - [BarBuffer Integration](#barbuffer-integration)
  - [Reconnection Behavior](#reconnection-behavior)
- [API Reference](#api-reference)
  - [LighterBrokerAdapter](#lighterbrokeradapter)
  - [LighterDataAdapter](#lighterdataadapter)
  - [LighterWebSocketAdapter](#lighterwebsocketadapter)
- [Examples](#examples)
  - [Submit Your First Order](#example-1-submit-your-first-order)
  - [Fetch Historical Data](#example-2-fetch-historical-data)
  - [Stream Live Trades](#example-3-stream-live-trades)
  - [Paper Trading Session](#example-4-paper-trading-session)

---

## Overview

Lighter.xyz is a high-performance decentralized exchange (DEX) for perpetual futures trading. rustybt provides three adapters for complete integration:

| Adapter | Purpose | Import Path |
|---------|---------|-------------|
| `LighterBrokerAdapter` | Order execution, positions | `rustybt.live.brokers.lighter_adapter` |
| `LighterDataAdapter` | Historical OHLCV data | `rustybt.data.adapters.lighter_adapter` |
| `LighterWebSocketAdapter` | Real-time streaming | `rustybt.live.streaming.lighter_stream` |

### Network Selection

| Network | API URL | When to Use |
|---------|---------|-------------|
| Testnet | `testnet.zklighter.elliot.ai` | Development, testing (default) |
| Mainnet | `mainnet.zklighter.elliot.ai` | Production trading |

All adapters default to testnet for safety (per ADR-003).

---

## Broker Adapter

The `LighterBrokerAdapter` handles order execution, position management, and account queries.

### Authentication

Lighter.xyz uses Ethereum private key authentication. The adapter supports three methods for loading credentials:

#### Method 1: Environment Variable (Recommended)

```bash
# Set in .env or shell profile
export LIGHTER_PRIVATE_KEY="1234567890abcdef..."  # 64 hex chars, no 0x prefix
```

```python
from rustybt.live.brokers.lighter_adapter import LighterBrokerAdapter

# Automatically loads from LIGHTER_PRIVATE_KEY
adapter = LighterBrokerAdapter(testnet=True)
await adapter.connect()
```

#### Method 2: Encrypted Keystore (Recommended for Production)

```python
from cryptography.fernet import Fernet

# 1. One-time: Generate encryption key and create keystore
encryption_key = Fernet.generate_key().decode()
print(f"Save this encryption key securely: {encryption_key}")

# Create encrypted keystore
LighterBrokerAdapter.create_encrypted_keystore(
    private_key="your_private_key_here",
    output_path="~/.rustybt/lighter_key.enc",
    encryption_key=encryption_key
)

# 2. Runtime: Load from encrypted keystore
adapter = LighterBrokerAdapter(
    encrypted_key_path="~/.rustybt/lighter_key.enc",
    encryption_key=os.environ["LIGHTER_ENCRYPTION_KEY"],
    testnet=True
)
```

#### Method 3: Direct Parameter (Not Recommended)

```python
# WARNING: Logs a security warning
adapter = LighterBrokerAdapter(
    private_key="your_private_key_here",
    testnet=True
)
```

#### Connection Example

```python
import asyncio
from rustybt.live.brokers.lighter_adapter import LighterBrokerAdapter

async def connect_example():
    adapter = LighterBrokerAdapter(testnet=True)

    try:
        await adapter.connect()
        print(f"Connected: {adapter.is_connected()}")
        print(f"API URL: {adapter.api_url}")

        # Get account info
        account = await adapter.get_account_info()
        print(f"Balance: {account['balance']}")
        print(f"Equity: {account['equity']}")

    finally:
        await adapter.disconnect()

asyncio.run(connect_example())
```

### Order Submission

The adapter supports market and limit orders with automatic rate limiting.

#### Market Orders

```python
from rustybt.assets import Asset
from decimal import Decimal

# Buy 0.001 BTC at market price
order_id = await adapter.submit_order(
    asset=Asset("BTC-PERP"),
    amount=Decimal("0.001"),  # Positive = buy
    order_type="market"
)
print(f"Order ID: {order_id}")  # Format: "BTC-PERP:ORDER_ID"

# Sell 0.001 BTC at market price
order_id = await adapter.submit_order(
    asset=Asset("BTC-PERP"),
    amount=Decimal("-0.001"),  # Negative = sell
    order_type="market"
)
```

#### Limit Orders

```python
# Buy limit order
order_id = await adapter.submit_order(
    asset=Asset("BTC-PERP"),
    amount=Decimal("0.001"),
    order_type="limit",
    limit_price=Decimal("40000.00")
)

# Sell limit order
order_id = await adapter.submit_order(
    asset=Asset("ETH-PERP"),
    amount=Decimal("-0.5"),
    order_type="limit",
    limit_price=Decimal("2500.00")
)
```

#### Order Cancellation

```python
# Cancel by order ID (format: SYMBOL:ORDER_ID)
await adapter.cancel_order("BTC-PERP:123456")

# Get open orders first
orders = await adapter.get_open_orders()
for order in orders:
    print(f"Order: {order['order_id']} - {order['side']} {order['quantity']} @ {order['price']}")
    await adapter.cancel_order(order['order_id'])
```

### Position Queries

```python
# Get all positions
positions = await adapter.get_positions()
for pos in positions:
    print(f"Symbol: {pos['symbol']}")
    print(f"Size: {pos['size']}")  # Positive=long, Negative=short
    print(f"Entry: {pos['entry_price']}")
    print(f"Mark: {pos['mark_price']}")
    print(f"PnL: {pos['unrealized_pnl']}")
    print("---")

# Get account info
account = await adapter.get_account_info()
print(f"Balance: {account['balance']}")
print(f"Available Margin: {account['available_margin']}")
print(f"Used Margin: {account['used_margin']}")
print(f"Equity: {account['equity']}")
print(f"Unrealized PnL: {account['unrealized_pnl']}")
```

### Paper Trading Mode

Paper trading simulates orders locally without hitting the exchange API.

```python
# Initialize in paper mode
adapter = LighterBrokerAdapter(
    paper_mode=True,
    paper_slippage=Decimal("0.001"),  # 0.1% slippage on market orders
    testnet=True  # Still use testnet for price data
)

# No connection required for paper orders
order_id = await adapter.submit_order(
    asset=Asset("BTC-PERP"),
    amount=Decimal("0.01"),
    order_type="market",
    limit_price=Decimal("50000")  # Used as reference price in paper mode
)
print(f"Paper Order: {order_id}")  # Format: "BTC-PERP:PAPER-000001"

# Check paper positions
positions = adapter.get_paper_positions()
print(f"Paper Positions: {positions}")

# Register fill callback
async def on_fill(fill_data):
    print(f"Fill: {fill_data['side']} {fill_data['fill_quantity']} @ {fill_data['fill_price']}")

adapter.set_fill_callback(on_fill)
```

### Error Handling

The adapter raises specific exceptions for different error conditions:

```python
from rustybt.live.brokers.lighter_adapter import (
    LighterBrokerAdapter,
    LighterKeyError,
    LighterConnectionError,
    LighterOrderRejectError,
    LighterRateLimitError,
)

try:
    adapter = LighterBrokerAdapter(testnet=True)
    await adapter.connect()

except LighterKeyError as e:
    # Private key issues
    print(f"Key error: {e}")
    # Check: LIGHTER_PRIVATE_KEY set? Key format valid (64 hex chars)?

except LighterConnectionError as e:
    # Network or API issues
    print(f"Connection error: {e}")
    # Check: Network connectivity? API endpoint accessible?

try:
    order_id = await adapter.submit_order(
        asset=Asset("BTC-PERP"),
        amount=Decimal("0.001"),
        order_type="limit",
        limit_price=Decimal("40000")
    )

except LighterOrderRejectError as e:
    # Order rejected by exchange
    print(f"Order rejected: {e}")
    # Check: Sufficient margin? Valid price? Position limits?

except LighterRateLimitError as e:
    # Rate limit exceeded
    print(f"Rate limit: {e}")
    # Wait before retrying - adapter has built-in rate limiting
```

---

## Data Adapter

The `LighterDataAdapter` fetches historical OHLCV data and asset information.

### Asset Discovery

```python
from rustybt.data.adapters.lighter_adapter import LighterDataAdapter

async with LighterDataAdapter(testnet=True) as adapter:
    # Get all available assets
    assets = await adapter.get_available_assets()

    for asset in assets:
        print(f"Symbol: {asset['symbol']}")
        print(f"Base/Quote: {asset['base']}/{asset['quote']}")
        print(f"Category: {asset['category']}")  # 'perpetual' or 'spot'
        print(f"Min Size: {asset['min_size']}")
        print(f"Tick Size: {asset['tick_size']}")
        print("---")
```

#### Filtering by Category

```python
# Get only perpetual contracts
perps = await adapter.get_assets_by_category("perpetual")
print(f"Found {len(perps)} perpetual contracts")

# Get only spot pairs
spot = await adapter.get_assets_by_category("spot")
print(f"Found {len(spot)} spot pairs")
```

#### Pattern Matching

```python
# Get all assets (to filter)
assets = await adapter.get_available_assets()

# Filter by pattern (supports wildcards and regex)
btc_assets = adapter.filter_assets_by_pattern(assets, "BTC*")
perp_assets = adapter.filter_assets_by_pattern(assets, "*PERP")
eth_perp = adapter.filter_assets_by_pattern(assets, "ETH-PERP")  # Exact match
```

### OHLCV Fetching

```python
import pandas as pd

async with LighterDataAdapter(testnet=True) as adapter:
    # Fetch 1-hour bars
    df = await adapter.fetch(
        symbols=["BTC-PERP"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-01"),
        resolution="1h"
    )

    print(f"Fetched {len(df)} bars")
    print(df.head())
```

#### Multi-Symbol Fetching

```python
df = await adapter.fetch(
    symbols=["BTC-PERP", "ETH-PERP", "SOL-PERP"],
    start_date=pd.Timestamp("2024-06-01"),
    end_date=pd.Timestamp("2024-12-01"),
    resolution="4h"
)

# DataFrame contains all symbols with 'symbol' column
for symbol in df["symbol"].unique():
    symbol_data = df.filter(pl.col("symbol") == symbol)
    print(f"{symbol}: {len(symbol_data)} bars")
```

### Timeframe Options

| Resolution | API Format | Description |
|------------|------------|-------------|
| `1m` | 1 | 1 minute |
| `5m` | 5 | 5 minutes |
| `15m` | 15 | 15 minutes |
| `1h` | 60 | 1 hour |
| `4h` | 240 | 4 hours |
| `1d` | 1440 | 1 day |

```python
# Examples for different timeframes
df_1m = await adapter.fetch(symbols=["BTC-PERP"], resolution="1m", ...)
df_1h = await adapter.fetch(symbols=["BTC-PERP"], resolution="1h", ...)
df_1d = await adapter.fetch(symbols=["BTC-PERP"], resolution="1d", ...)
```

### Funding Rates

```python
# Get funding rate history
funding_df = await adapter.get_funding_rates(
    symbol="BTC-PERP",
    start_date=pd.Timestamp("2024-01-01"),
    end_date=pd.Timestamp("2024-12-01")
)

print(f"Funding rate records: {len(funding_df)}")
print(funding_df.head())
# Columns: timestamp, symbol, funding_rate
```

### Bundle Integration

The data adapter returns Polars DataFrames compatible with rustybt's bundle system:

```python
from rustybt.data.bundle import DataBundle

async with LighterDataAdapter(testnet=True) as adapter:
    # Fetch data
    df = await adapter.fetch(
        symbols=["BTC-PERP"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-01"),
        resolution="1h"
    )

    # Standardize to rustybt schema
    df = adapter.standardize(df)

    # Validate OHLCV relationships
    adapter.validate(df)  # Raises ValidationError if invalid

    # Use with bundle
    bundle = DataBundle.from_polars(df)
```

#### Data Schema

The adapter outputs data in the rustybt standard schema:

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | `Datetime("us")` | Bar timestamp (UTC) |
| `symbol` | `Utf8` | Trading pair symbol |
| `open` | `Decimal(18, 8)` | Opening price |
| `high` | `Decimal(18, 8)` | Highest price |
| `low` | `Decimal(18, 8)` | Lowest price |
| `close` | `Decimal(18, 8)` | Closing price |
| `volume` | `Decimal(18, 8)` | Trading volume |

---

## Streaming Adapter

The `LighterWebSocketAdapter` provides real-time market data streaming.

### WebSocket Connection

```python
from rustybt.live.streaming.lighter_stream import (
    LighterWebSocketAdapter,
    LighterStreamConfig
)

# Basic connection
adapter = LighterWebSocketAdapter(testnet=True)
await adapter.connect()
print(f"Connected: {adapter.is_connected}")

# With configuration
config = LighterStreamConfig(
    bar_resolution=60,           # 1-minute bars
    heartbeat_interval=30,       # Ping every 30 seconds
    heartbeat_timeout=60,        # Connection timeout
    reconnect_attempts=None,     # Unlimited reconnection
    reconnect_delay=1,           # Initial retry delay
    reconnect_max_delay=16,      # Max retry delay (exponential backoff)
    enable_trade_stream=True,    # Subscribe to trades
    enable_orderbook_stream=False  # Skip orderbook (optional)
)

adapter = LighterWebSocketAdapter(testnet=True, config=config)
await adapter.connect()
```

### Channel Subscriptions

```python
# Subscribe to specific channels
await adapter.subscribe(
    symbols=["BTC-PERP", "ETH-PERP"],
    channels=["trades"]
)

# Subscribe to all available channels
await adapter.subscribe_all_channels(["BTC-PERP", "ETH-PERP"])

# Unsubscribe
await adapter.unsubscribe(
    symbols=["ETH-PERP"],
    channels=["trades"]
)
```

### Message Handling

The adapter converts WebSocket messages to `TickData` objects:

```python
from rustybt.live.streaming.models import TickData, TickSide

def handle_tick(tick: TickData):
    print(f"Symbol: {tick.symbol}")
    print(f"Time: {tick.timestamp}")
    print(f"Price: {tick.price}")
    print(f"Volume: {tick.volume}")
    print(f"Side: {tick.side.value}")  # 'buy', 'sell', or 'unknown'

# With callback
adapter = LighterWebSocketAdapter(
    testnet=True,
    on_tick=handle_tick
)

await adapter.connect()
await adapter.subscribe(["BTC-PERP"], ["trades"])

# Ticks are delivered via callback as they arrive
```

### BarBuffer Integration

The adapter can aggregate ticks into OHLCV bars:

```python
from rustybt.live.streaming.bar_buffer import OHLCVBar

def handle_bar(bar: OHLCVBar):
    print(f"Bar Complete: {bar.symbol} @ {bar.timestamp}")
    print(f"OHLCV: {bar.open}/{bar.high}/{bar.low}/{bar.close}")
    print(f"Volume: {bar.volume}")

config = LighterStreamConfig(
    bar_resolution=60  # 1-minute bars
)

adapter = LighterWebSocketAdapter(
    testnet=True,
    config=config,
    on_bar=handle_bar
)

await adapter.connect()
await adapter.subscribe(["BTC-PERP"], ["trades"])

# Bars are delivered via callback every minute
# Get current buffer state
state = adapter.get_bar_buffer_state()
print(f"Bar buffer enabled: {state['enabled']}")
print(f"Bar resolution: {state['bar_resolution']}s")
print(f"Symbols buffering: {state['symbols_buffering']}")

# Flush incomplete bars
incomplete_bars = adapter.flush_bars()
```

### Reconnection Behavior

The adapter automatically reconnects with message buffering:

```python
# Reconnection is automatic with exponential backoff
# Messages are buffered during reconnection

# Manual reconnection
await adapter.reconnect()

# Enable/disable buffering manually
adapter.enable_buffering()
# ... reconnection happens ...
await adapter.replay_buffer()  # Replay buffered messages
adapter.disable_buffering()

# Get buffered messages
buffered = adapter.get_buffered_messages()
print(f"Buffered messages: {len(buffered)}")
```

#### Context Manager Usage

```python
async with LighterWebSocketAdapter(testnet=True) as adapter:
    await adapter.subscribe(["BTC-PERP"], ["trades"])

    # Process messages for 60 seconds
    await asyncio.sleep(60)

# Automatically disconnects when context exits
```

---

## API Reference

### LighterBrokerAdapter

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `__init__()` | Initialize adapter | `private_key`, `encrypted_key_path`, `encryption_key`, `testnet=True`, `account_index=0`, `api_key_index=0`, `paper_mode=False`, `paper_slippage=Decimal("0.001")` | None |
| `connect()` | Connect to Lighter.xyz | None | `None` |
| `disconnect()` | Disconnect | None | `None` |
| `submit_order()` | Submit order | `asset: Asset`, `amount: Decimal`, `order_type: str`, `limit_price: Decimal \| None` | `str` (order ID) |
| `cancel_order()` | Cancel order | `broker_order_id: str` | `None` |
| `get_account_info()` | Get account balances | None | `dict[str, Decimal]` |
| `get_positions()` | Get open positions | None | `list[dict]` |
| `get_open_orders()` | Get open orders | None | `list[dict]` |
| `get_order_history()` | Get order history | `limit: int=100`, `offset: int=0` | `list[dict]` |
| `is_connected()` | Check connection | None | `bool` |
| `get_paper_positions()` | Get paper positions | None | `dict[str, dict]` |
| `set_fill_callback()` | Set fill callback | `callback: Callable` | `None` |
| `create_encrypted_keystore()` | Create keystore (static) | `private_key: str`, `output_path: str`, `encryption_key: str` | `None` |

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `api_url` | `str` | Current API URL |
| `paper_mode` | `bool` | Paper trading enabled |

### LighterDataAdapter

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `__init__()` | Initialize adapter | `testnet=True`, `rate_limit_per_second=10`, `max_retries=3`, `timeout=30.0` | None |
| `get_available_assets()` | List all assets | None | `list[dict]` |
| `get_assets_by_category()` | Filter by category | `category: str` | `list[dict]` |
| `filter_assets_by_pattern()` | Filter by pattern | `assets: list[dict]`, `pattern: str`, `field: str="symbol"` | `list[dict]` |
| `fetch()` | Fetch OHLCV data | `symbols: list[str]`, `start_date: Timestamp`, `end_date: Timestamp`, `resolution: str` | `pl.DataFrame` |
| `get_funding_rates()` | Get funding rates | `symbol: str`, `start_date: Timestamp \| None`, `end_date: Timestamp \| None` | `pl.DataFrame` |
| `standardize()` | Standardize schema | `df: pl.DataFrame` | `pl.DataFrame` |
| `validate()` | Validate OHLCV data | `df: pl.DataFrame` | `bool` |
| `close()` | Close HTTP session | None | `None` |

### LighterWebSocketAdapter

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `__init__()` | Initialize adapter | `testnet=True`, `config: LighterStreamConfig \| None`, `on_tick: Callable \| None`, `on_bar: Callable \| None` | None |
| `connect()` | Connect WebSocket | None | `None` |
| `disconnect()` | Disconnect | None | `None` |
| `subscribe()` | Subscribe to streams | `symbols: list[str]`, `channels: list[str]` | `None` |
| `unsubscribe()` | Unsubscribe | `symbols: list[str]`, `channels: list[str]` | `None` |
| `subscribe_all_channels()` | Subscribe all channels | `symbols: list[str]` | `None` |
| `parse_message()` | Parse raw message | `raw_message: dict` | `TickData \| None` |
| `reconnect()` | Reconnect with buffering | None | `None` |
| `enable_buffering()` | Enable message buffer | None | `None` |
| `disable_buffering()` | Disable buffer | None | `None` |
| `get_buffered_messages()` | Get buffered messages | None | `list[dict]` |
| `replay_buffer()` | Replay buffer | None | `None` |
| `flush_bars()` | Flush incomplete bars | None | `dict[str, OHLCVBar]` |
| `get_bar_buffer_state()` | Get buffer state | None | `dict` |

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_connected` | `bool` | Connection status |
| `on_bar` | `Callable \| None` | Bar complete callback |

---

## Examples

### Example 1: Submit Your First Order

Complete walkthrough from connection to order execution.

```python
import asyncio
import os
from decimal import Decimal

from rustybt.assets import Asset
from rustybt.live.brokers.lighter_adapter import (
    LighterBrokerAdapter,
    LighterOrderRejectError,
)

async def first_order():
    # Initialize adapter (testnet for safety)
    adapter = LighterBrokerAdapter(testnet=True)

    try:
        # Connect to Lighter.xyz
        print("Connecting to Lighter.xyz testnet...")
        await adapter.connect()
        print(f"Connected: {adapter.is_connected()}")

        # Check account balance
        account = await adapter.get_account_info()
        print(f"\nAccount Info:")
        print(f"  Balance: {account['balance']} USDC")
        print(f"  Equity: {account['equity']} USDC")
        print(f"  Available Margin: {account['available_margin']} USDC")

        # Submit limit order (buy 0.001 BTC)
        print("\nSubmitting limit order...")
        order_id = await adapter.submit_order(
            asset=Asset("BTC-PERP"),
            amount=Decimal("0.001"),
            order_type="limit",
            limit_price=Decimal("40000.00")
        )
        print(f"Order submitted: {order_id}")

        # Check open orders
        orders = await adapter.get_open_orders()
        print(f"\nOpen orders: {len(orders)}")
        for order in orders:
            print(f"  {order['order_id']}: {order['side']} {order['quantity']} @ {order['price']}")

        # Cancel the order
        print(f"\nCancelling order {order_id}...")
        await adapter.cancel_order(order_id)
        print("Order cancelled")

    except LighterOrderRejectError as e:
        print(f"Order rejected: {e}")
    finally:
        await adapter.disconnect()
        print("\nDisconnected")

if __name__ == "__main__":
    asyncio.run(first_order())
```

### Example 2: Fetch Historical Data

Fetch and analyze historical OHLCV data for backtesting.

```python
import asyncio
import pandas as pd
import polars as pl

from rustybt.data.adapters.lighter_adapter import LighterDataAdapter

async def fetch_historical():
    async with LighterDataAdapter(testnet=True) as adapter:
        # Discover available assets
        print("Discovering assets...")
        assets = await adapter.get_available_assets()
        print(f"Found {len(assets)} assets")

        # Filter perpetuals
        perps = await adapter.get_assets_by_category("perpetual")
        print(f"Perpetual contracts: {', '.join(a['symbol'] for a in perps[:5])}")

        # Fetch BTC-PERP 1-hour data
        print("\nFetching BTC-PERP hourly data...")
        df = await adapter.fetch(
            symbols=["BTC-PERP"],
            start_date=pd.Timestamp("2024-06-01"),
            end_date=pd.Timestamp("2024-12-01"),
            resolution="1h"
        )

        print(f"Fetched {len(df)} bars")
        print(f"\nData Schema:")
        print(df.schema)

        print(f"\nFirst 5 bars:")
        print(df.head(5))

        print(f"\nLast 5 bars:")
        print(df.tail(5))

        # Calculate some statistics
        print(f"\nStatistics:")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"  Price range: {df['low'].min()} to {df['high'].max()}")
        print(f"  Total volume: {df['volume'].sum()}")

        # Standardize and validate
        df = adapter.standardize(df)
        adapter.validate(df)
        print("\nData validated successfully!")

        # Fetch funding rates
        print("\nFetching funding rates...")
        funding = await adapter.get_funding_rates(
            symbol="BTC-PERP",
            start_date=pd.Timestamp("2024-06-01"),
            end_date=pd.Timestamp("2024-12-01")
        )
        print(f"Funding rate records: {len(funding)}")

if __name__ == "__main__":
    asyncio.run(fetch_historical())
```

### Example 3: Stream Live Trades

Real-time trade streaming with bar aggregation.

```python
import asyncio
from decimal import Decimal

from rustybt.live.streaming.lighter_stream import (
    LighterWebSocketAdapter,
    LighterStreamConfig
)
from rustybt.live.streaming.models import TickData
from rustybt.live.streaming.bar_buffer import OHLCVBar

# Track statistics
stats = {
    "tick_count": 0,
    "bar_count": 0,
    "total_volume": Decimal("0")
}

def on_tick(tick: TickData):
    stats["tick_count"] += 1
    stats["total_volume"] += tick.volume

    if stats["tick_count"] % 10 == 0:  # Print every 10 ticks
        print(f"Tick #{stats['tick_count']}: {tick.symbol} "
              f"{tick.side.value.upper()} {tick.volume} @ {tick.price}")

def on_bar(bar: OHLCVBar):
    stats["bar_count"] += 1
    print(f"\n*** BAR COMPLETE ***")
    print(f"Symbol: {bar.symbol}")
    print(f"Time: {bar.timestamp}")
    print(f"OHLCV: O={bar.open} H={bar.high} L={bar.low} C={bar.close}")
    print(f"Volume: {bar.volume}")
    print(f"*******************\n")

async def stream_trades():
    # Configure for 1-minute bars
    config = LighterStreamConfig(
        bar_resolution=60,
        heartbeat_interval=30,
        enable_trade_stream=True
    )

    adapter = LighterWebSocketAdapter(
        testnet=True,
        config=config,
        on_tick=on_tick,
        on_bar=on_bar
    )

    try:
        print("Connecting to Lighter.xyz WebSocket...")
        await adapter.connect()
        print("Connected!")

        print("Subscribing to BTC-PERP trades...")
        await adapter.subscribe(["BTC-PERP"], ["trades"])
        print("Subscribed! Streaming trades...\n")

        # Stream for 5 minutes
        await asyncio.sleep(300)

        # Print final stats
        print(f"\n--- Session Statistics ---")
        print(f"Total ticks: {stats['tick_count']}")
        print(f"Total bars: {stats['bar_count']}")
        print(f"Total volume: {stats['total_volume']}")

        # Flush incomplete bars
        incomplete = adapter.flush_bars()
        if incomplete:
            print(f"Incomplete bars: {list(incomplete.keys())}")

    finally:
        await adapter.disconnect()
        print("Disconnected")

if __name__ == "__main__":
    asyncio.run(stream_trades())
```

### Example 4: Paper Trading Session

Simulate trading without real orders.

```python
import asyncio
from decimal import Decimal
from datetime import datetime

from rustybt.assets import Asset
from rustybt.live.brokers.lighter_adapter import LighterBrokerAdapter

class SimplePaperStrategy:
    def __init__(self):
        self.adapter = LighterBrokerAdapter(
            paper_mode=True,
            paper_slippage=Decimal("0.0005"),  # 0.05% slippage
            testnet=True
        )
        self.trades = []

        # Register fill callback
        self.adapter.set_fill_callback(self.on_fill)

    async def on_fill(self, fill_data: dict):
        self.trades.append(fill_data)
        print(f"\nFILL: {fill_data['side'].upper()} {fill_data['fill_quantity']} "
              f"@ {fill_data['fill_price']}")

    async def run(self):
        print("=== Paper Trading Session ===\n")
        print("Note: No real orders - all simulated locally\n")

        # Simulate some trades
        trades = [
            ("BTC-PERP", Decimal("0.01"), "market", Decimal("45000")),
            ("ETH-PERP", Decimal("0.5"), "limit", Decimal("2500")),
            ("BTC-PERP", Decimal("-0.005"), "market", Decimal("45100")),  # Partial close
        ]

        for symbol, amount, order_type, price in trades:
            print(f"Submitting: {order_type.upper()} "
                  f"{'BUY' if amount > 0 else 'SELL'} {abs(amount)} {symbol}")

            order_id = await self.adapter.submit_order(
                asset=Asset(symbol),
                amount=amount,
                order_type=order_type,
                limit_price=price
            )
            print(f"Order ID: {order_id}")

            await asyncio.sleep(0.5)  # Small delay for readability

        # Display positions
        print("\n=== Paper Positions ===")
        positions = self.adapter.get_paper_positions()
        for symbol, pos in positions.items():
            pnl = (Decimal("45100") - pos['entry_price']) * pos['size']  # Simulated PnL
            print(f"{symbol}:")
            print(f"  Size: {pos['size']}")
            print(f"  Entry: {pos['entry_price']}")
            print(f"  Simulated PnL: {pnl}")

        # Summary
        print(f"\n=== Session Summary ===")
        print(f"Total trades executed: {len(self.trades)}")
        print(f"Open positions: {len(positions)}")

        # Note: Paper mode doesn't require connect/disconnect
        print("\nPaper trading session complete!")

if __name__ == "__main__":
    strategy = SimplePaperStrategy()
    asyncio.run(strategy.run())
```

---

## Rate Limits

Built-in rate limiting protects against API throttling:

| Limit Type | Value | Behavior |
|------------|-------|----------|
| REST API | 600 req/min | Token bucket with automatic waiting |
| Orders per Symbol | 20/sec | Per-symbol limiting |
| Warning Threshold | 80% | Logs warning when approaching limit |

The adapter handles rate limiting automatically. If you see rate limit warnings, reduce your request frequency.

---

## Exceptions

| Exception | When Raised | Common Causes |
|-----------|-------------|---------------|
| `LighterKeyError` | Key loading/validation | Missing env var, invalid format |
| `LighterConnectionError` | Connection/API issues | Network problems, API down |
| `LighterOrderRejectError` | Order rejected | Insufficient margin, invalid price |
| `LighterRateLimitError` | Rate limit exceeded | Too many requests |
| `LighterDataError` | Data adapter errors | Invalid response, parsing failure |
| `SubscriptionError` | WebSocket subscription | Not connected, invalid channel |
| `ParseError` | Message parsing | Malformed WebSocket message |
| `ValidationError` | Data validation | OHLCV relationship violated |

---

## Related Documentation

- [Live Trading Setup Guide](./setup-guide.md) - Platform setup and credentials
- [Testnet Setup Guide](./testnet-setup-guide.md) - Testnet registration
- [Code Audit Report](./audit-report.md) - Production readiness audit

---

*Last updated: 2025-12-07*
