#!/usr/bin/env python
#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Example: WebSocket Real-Time Data Streaming

This example demonstrates how to use WebSocket adapters to stream real-time
market data from exchanges and brokers.

Key Concepts Demonstrated:
- WebSocket connection management
- Real-time data streaming
- Event-driven data processing
- Multiple concurrent streams
- Error handling and reconnection
- Data aggregation and buffering

Usage:
    python examples/websocket_streaming.py
"""

import asyncio
import os
from collections import deque
from decimal import Decimal

import pandas as pd
import structlog

from rustybt.live.streaming.base import BaseWebSocketAdapter
from rustybt.live.streaming.models import StreamingBar

# Try to import specific WebSocket adapters (may not all be available)
try:
    from rustybt.live.streaming.binance_stream import BinanceWebSocketAdapter

    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False

try:
    from rustybt.live.streaming.ccxt_stream import CCXTWebSocketAdapter

    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

logger = structlog.get_logger()


class MockWebSocketAdapter(BaseWebSocketAdapter):
    """Mock WebSocket adapter for demonstration purposes.

    Generates fake streaming data to demonstrate the streaming API
    without requiring actual broker credentials.
    """

    def __init__(self, symbols: list[str]):
        """Initialize mock adapter.

        Args:
            symbols: List of symbols to stream
        """
        super().__init__()
        self.symbols = symbols
        self._running = False
        self._task = None

    async def connect(self) -> None:
        """Connect to mock WebSocket."""
        logger.info("mock_websocket_connecting")
        await asyncio.sleep(0.5)  # Simulate connection delay
        self._running = True
        logger.info("mock_websocket_connected")

    async def disconnect(self) -> None:
        """Disconnect from mock WebSocket."""
        logger.info("mock_websocket_disconnecting")
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("mock_websocket_disconnected")

    async def subscribe(self, symbols: list[str]) -> None:
        """Subscribe to symbols.

        Args:
            symbols: Symbols to subscribe to
        """
        logger.info("subscribing_to_symbols", symbols=symbols)
        self.symbols.extend(symbols)

    async def unsubscribe(self, symbols: list[str]) -> None:
        """Unsubscribe from symbols.

        Args:
            symbols: Symbols to unsubscribe from
        """
        logger.info("unsubscribing_from_symbols", symbols=symbols)
        for symbol in symbols:
            if symbol in self.symbols:
                self.symbols.remove(symbol)

    async def stream(self) -> asyncio.Queue:
        """Start streaming mock data.

        Returns:
            Queue that will receive StreamingBar objects
        """
        queue = asyncio.Queue()
        self._task = asyncio.create_task(self._generate_data(queue))
        return queue

    async def _generate_data(self, queue: asyncio.Queue) -> None:
        """Generate mock streaming data.

        Args:
            queue: Queue to put data into
        """
        import random

        base_prices = {symbol: Decimal("100.00") for symbol in self.symbols}

        while self._running:
            for symbol in self.symbols:
                # Generate random price movement
                change = Decimal(str(random.uniform(-1, 1)))
                new_price = base_prices[symbol] + change
                base_prices[symbol] = new_price

                # Create streaming bar
                bar = StreamingBar(
                    symbol=symbol,
                    timestamp=pd.Timestamp.now(tz="UTC"),
                    open=new_price,
                    high=new_price + Decimal("0.5"),
                    low=new_price - Decimal("0.5"),
                    close=new_price,
                    volume=Decimal(str(random.randint(1000, 10000))),
                )

                await queue.put(bar)

            # Wait before next update
            await asyncio.sleep(1.0)  # 1 second intervals


class StreamingDataAggregator:
    """Aggregates streaming ticks into OHLCV bars.

    Example:
        >>> aggregator = StreamingDataAggregator(window_seconds=60)
        >>> aggregator.process_tick(bar)
        >>> ohlcv_bar = aggregator.get_bar('AAPL')
    """

    def __init__(self, window_seconds: int = 60):
        """Initialize aggregator.

        Args:
            window_seconds: Time window for aggregation (default: 60s)
        """
        self.window_seconds = window_seconds
        self._ticks: dict[str, deque[StreamingBar]] = {}
        self._current_bars: dict[str, dict] = {}

    def process_tick(self, bar: StreamingBar) -> None:
        """Process incoming tick.

        Args:
            bar: Streaming bar to process
        """
        symbol = bar.symbol

        # Initialize if needed
        if symbol not in self._ticks:
            self._ticks[symbol] = deque(maxlen=1000)
            self._current_bars[symbol] = {
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "start_time": bar.timestamp,
            }

        # Add tick
        self._ticks[symbol].append(bar)

        # Update current bar
        current = self._current_bars[symbol]
        current["high"] = max(current["high"], bar.high)
        current["low"] = min(current["low"], bar.low)
        current["close"] = bar.close
        current["volume"] += bar.volume

        # Check if window elapsed
        elapsed = (bar.timestamp - current["start_time"]).total_seconds()
        if elapsed >= self.window_seconds:
            self._finalize_bar(symbol, bar.timestamp)

    def _finalize_bar(self, symbol: str, timestamp: pd.Timestamp) -> None:
        """Finalize current bar and start new one.

        Args:
            symbol: Symbol to finalize
            timestamp: Current timestamp
        """
        logger.debug(
            "bar_finalized", symbol=symbol, close=float(self._current_bars[symbol]["close"])
        )

        # Start new bar
        last_close = self._current_bars[symbol]["close"]
        self._current_bars[symbol] = {
            "open": last_close,
            "high": last_close,
            "low": last_close,
            "close": last_close,
            "volume": Decimal("0"),
            "start_time": timestamp,
        }

    def get_bar(self, symbol: str) -> dict:
        """Get current aggregated bar for symbol.

        Args:
            symbol: Symbol to get bar for

        Returns:
            Dict with OHLCV data
        """
        return self._current_bars.get(symbol, {})


async def example_basic_streaming():
    """Example 1: Basic WebSocket streaming."""
    print("\n" + "=" * 70)
    print("Example 1: Basic WebSocket Streaming")
    print("=" * 70)

    # Create mock adapter
    adapter = MockWebSocketAdapter(symbols=["AAPL", "MSFT"])

    # Connect
    print("\n[1/4] Connecting to WebSocket...")
    await adapter.connect()
    print("✓ Connected")

    # Start streaming
    print("\n[2/4] Starting data stream...")
    queue = await adapter.stream()
    print("✓ Stream started")

    # Receive data for 10 seconds
    print("\n[3/4] Receiving data (10 seconds)...")
    count = 0
    start_time = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start_time < 10:
        try:
            bar = await asyncio.wait_for(queue.get(), timeout=2.0)
            count += 1

            if count % 5 == 0:  # Print every 5th bar
                print(f"  {bar.symbol}: ${bar.close:.2f} (volume: {int(bar.volume)})")

        except TimeoutError:
            continue

    print(f"✓ Received {count} bars")

    # Disconnect
    print("\n[4/4] Disconnecting...")
    await adapter.disconnect()
    print("✓ Disconnected")


async def example_data_aggregation():
    """Example 2: Real-time data aggregation."""
    print("\n" + "=" * 70)
    print("Example 2: Data Aggregation (Tick → 5-Second Bars)")
    print("=" * 70)

    # Create adapter and aggregator
    adapter = MockWebSocketAdapter(symbols=["BTC/USDT"])
    aggregator = StreamingDataAggregator(window_seconds=5)

    # Connect
    print("\n[1/3] Connecting to WebSocket...")
    await adapter.connect()
    print("✓ Connected")

    # Start streaming
    queue = await adapter.stream()
    print("\n[2/3] Aggregating ticks into 5-second bars...")
    print("  (Displaying completed bars only)\n")

    count = 0
    bars_completed = 0
    start_time = asyncio.get_event_loop().time()
    last_bar_close = None

    while asyncio.get_event_loop().time() - start_time < 15:
        try:
            tick = await asyncio.wait_for(queue.get(), timeout=2.0)
            aggregator.process_tick(tick)
            count += 1

            # Check if bar completed (price changed significantly)
            current_bar = aggregator.get_bar(tick.symbol)
            if last_bar_close and abs(float(current_bar["close"] - last_bar_close)) < 0.01:
                # Bar completed
                bars_completed += 1
                print(
                    f"  Bar {bars_completed}: "
                    f"O={current_bar['open']:.2f} "
                    f"H={current_bar['high']:.2f} "
                    f"L={current_bar['low']:.2f} "
                    f"C={current_bar['close']:.2f} "
                    f"V={int(current_bar['volume'])}"
                )
                last_bar_close = None
            else:
                last_bar_close = current_bar["close"]

        except TimeoutError:
            continue

    print(f"\n✓ Processed {count} ticks into {bars_completed} bars")

    # Disconnect
    print("\n[3/3] Disconnecting...")
    await adapter.disconnect()
    print("✓ Disconnected")


async def example_multiple_streams():
    """Example 3: Multiple concurrent WebSocket streams."""
    print("\n" + "=" * 70)
    print("Example 3: Multiple Concurrent Streams")
    print("=" * 70)

    # Create multiple adapters
    adapter1 = MockWebSocketAdapter(symbols=["AAPL"])
    adapter2 = MockWebSocketAdapter(symbols=["MSFT"])
    adapter3 = MockWebSocketAdapter(symbols=["GOOGL"])

    print("\n[1/3] Connecting to multiple WebSockets...")
    await asyncio.gather(adapter1.connect(), adapter2.connect(), adapter3.connect())
    print("✓ All connections established")

    # Start all streams
    print("\n[2/3] Starting streams...")
    queue1 = await adapter1.stream()
    queue2 = await adapter2.stream()
    queue3 = await adapter3.stream()
    print("✓ All streams started")

    # Receive data concurrently
    print("\n[3/3] Receiving data from all streams (10 seconds)...\n")

    async def process_stream(name: str, queue: asyncio.Queue, duration: float):
        """Process data from one stream."""
        count = 0
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < duration:
            try:
                await asyncio.wait_for(queue.get(), timeout=2.0)
                count += 1
            except TimeoutError:
                continue

        print(f"  {name}: Received {count} bars")

    # Process all streams concurrently
    await asyncio.gather(
        process_stream("Stream 1 (AAPL)", queue1, 10),
        process_stream("Stream 2 (MSFT)", queue2, 10),
        process_stream("Stream 3 (GOOGL)", queue3, 10),
    )

    # Disconnect all
    await asyncio.gather(adapter1.disconnect(), adapter2.disconnect(), adapter3.disconnect())
    print("\n✓ All streams disconnected")


async def example_binance_realtime():
    """Example 4: Real Binance WebSocket (if available)."""
    if not BINANCE_AVAILABLE:
        print("\n⚠️  Binance WebSocket adapter not available (skipping)")
        return

    print("\n" + "=" * 70)
    print("Example 4: Real Binance WebSocket Streaming")
    print("=" * 70)
    print("\n⚠️  This example requires Binance API credentials")
    print("Set BINANCE_API_KEY and BINANCE_API_SECRET environment variables")

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        print("\n⚠️  Credentials not found (skipping real Binance example)")
        return

    try:
        # Create Binance adapter
        adapter = BinanceWebSocketAdapter(api_key=api_key, api_secret=api_secret, testnet=True)

        # Connect
        print("\n[1/3] Connecting to Binance WebSocket...")
        await adapter.connect()
        print("✓ Connected")

        # Subscribe to symbols
        await adapter.subscribe(["BTC/USDT", "ETH/USDT"])

        # Start stream
        queue = await adapter.stream()

        # Receive real data
        print("\n[2/3] Receiving real-time data (30 seconds)...\n")
        count = 0
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < 30:
            try:
                bar = await asyncio.wait_for(queue.get(), timeout=5.0)
                count += 1

                if count % 10 == 0:
                    print(f"  {bar.symbol}: ${bar.close:.2f}")

            except TimeoutError:
                continue

        print(f"\n✓ Received {count} real-time bars")

        # Disconnect
        print("\n[3/3] Disconnecting...")
        await adapter.disconnect()
        print("✓ Disconnected")

    except Exception as e:
        print(f"\n❌ Error: {e}")


async def main():
    """Run all WebSocket streaming examples."""
    print("=" * 70)
    print("🌊 WebSocket Real-Time Streaming Examples")
    print("=" * 70)

    try:
        # Run examples
        await example_basic_streaming()
        await example_data_aggregation()
        await example_multiple_streams()
        await example_binance_realtime()

        print("\n" + "=" * 70)
        print("✨ All examples completed successfully!")
        print("=" * 70)

        print("\n💡 Key Takeaways:")
        print("  1. WebSockets provide real-time market data streaming")
        print("  2. Ticks can be aggregated into OHLCV bars")
        print("  3. Multiple streams can run concurrently")
        print("  4. Error handling and reconnection are critical")
        print("\n📚 Next Steps:")
        print("  1. Implement WebSocket reconnection logic")
        print("  2. Add data validation and sanitization")
        print("  3. Store streaming data to database")
        print("  4. Integrate with live trading engine")

    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
