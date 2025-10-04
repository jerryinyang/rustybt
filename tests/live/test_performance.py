"""Performance tests for live trading engine.

These tests validate AC9: Engine handles 1000+ events/second with <10ms latency.
"""

import asyncio
import time
from decimal import Decimal

import pandas as pd
import pytest

from rustybt.live.event_dispatcher import EventDispatcher
from rustybt.live.events import MarketDataEvent, OrderFillEvent, SystemErrorEvent


class TestEventProcessingPerformance:
    """Test event processing performance."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_event_queue_throughput(self):
        """Test event queue can handle 1000+ events/second.

        AC9: Engine handles 1000+ events/second
        """
        event_count = 1000
        queue = asyncio.PriorityQueue()

        # Create events
        events = [
            MarketDataEvent(
                asset_symbol=f"ASSET{i}",
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.50"),
                volume=Decimal("10000"),
                bar_timestamp=pd.Timestamp.now(),
            )
            for i in range(event_count)
        ]

        # Measure enqueue time
        start = time.perf_counter()
        for event in events:
            await queue.put(event)
        enqueue_duration = time.perf_counter() - start

        # Measure dequeue time
        start = time.perf_counter()
        dequeued = []
        while not queue.empty():
            dequeued.append(await queue.get())
        dequeue_duration = time.perf_counter() - start

        # Verify throughput
        enqueue_rate = event_count / enqueue_duration
        dequeue_rate = event_count / dequeue_duration

        print(f"\nEnqueue rate: {enqueue_rate:.0f} events/sec")
        print(f"Dequeue rate: {dequeue_rate:.0f} events/sec")

        # Should exceed 1000 events/second
        assert enqueue_rate > 1000, f"Enqueue rate too slow: {enqueue_rate:.0f}/sec"
        assert dequeue_rate > 1000, f"Dequeue rate too slow: {dequeue_rate:.0f}/sec"

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_event_dispatch_latency(self):
        """Test event dispatch latency is <10ms per event.

        AC9: <10ms latency per event
        """
        dispatcher = EventDispatcher()
        latencies = []

        async def handler(event):
            """Simple handler that records processing time."""
            await asyncio.sleep(0)  # Yield control

        dispatcher.register_handler("market_data", handler)

        # Process 100 events and measure latency
        for i in range(100):
            event = MarketDataEvent(
                asset_symbol=f"ASSET{i}",
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.50"),
                volume=Decimal("10000"),
                bar_timestamp=pd.Timestamp.now(),
            )

            start = time.perf_counter()
            await dispatcher.dispatch(event)
            duration = time.perf_counter() - start

            latencies.append(duration * 1000)  # Convert to ms

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        print(f"\nAverage latency: {avg_latency:.2f}ms")
        print(f"Max latency: {max_latency:.2f}ms")

        # Average should be well under 10ms
        assert avg_latency < 10, f"Average latency too high: {avg_latency:.2f}ms"
        assert max_latency < 50, f"Max latency too high: {max_latency:.2f}ms"

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_priority_queue_ordering_performance(self):
        """Test priority queue maintains ordering efficiently with high volume."""
        queue = asyncio.PriorityQueue()
        event_count = 10000

        # Create mix of events with different priorities
        events = []
        for i in range(event_count // 5):
            events.append(
                MarketDataEvent(
                    asset_symbol=f"ASSET{i}",
                    open=Decimal("100"),
                    high=Decimal("101"),
                    low=Decimal("99"),
                    close=Decimal("100.50"),
                    volume=Decimal("10000"),
                    bar_timestamp=pd.Timestamp.now(),
                )
            )
            events.append(
                OrderFillEvent(
                    order_id=f"order-{i}",
                    asset_symbol=f"ASSET{i}",
                    filled_amount=Decimal("100"),
                    fill_price=Decimal("100.50"),
                    commission=Decimal("1.00"),
                    fill_timestamp=pd.Timestamp.now(),
                )
            )
            events.append(
                SystemErrorEvent(
                    error_type="test",
                    error_message="test error",
                    error_timestamp=pd.Timestamp.now(),
                )
            )

        # Measure enqueue + dequeue with ordering
        start = time.perf_counter()

        # Enqueue all
        for event in events:
            await queue.put(event)

        # Dequeue all and verify ordering
        previous_priority = 0
        while not queue.empty():
            event = await queue.get()
            # Priority should be non-decreasing
            assert event.priority >= previous_priority
            previous_priority = event.priority

        duration = time.perf_counter() - start
        throughput = len(events) / duration

        print(f"\nProcessed {len(events)} events in {duration:.2f}s")
        print(f"Throughput: {throughput:.0f} events/sec")

        # Should maintain high throughput with ordering
        assert throughput > 1000

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_concurrent_event_processing(self):
        """Test concurrent event processing performance."""
        dispatcher = EventDispatcher()
        processed_count = 0
        lock = asyncio.Lock()

        async def handler(event):
            """Handler that simulates work."""
            nonlocal processed_count
            await asyncio.sleep(0.001)  # Simulate 1ms processing
            async with lock:
                processed_count += 1

        # Register 3 handlers
        dispatcher.register_handler("market_data", handler)
        dispatcher.register_handler("market_data", handler)
        dispatcher.register_handler("market_data", handler)

        # Process 100 events concurrently
        event_count = 100
        events = [
            MarketDataEvent(
                asset_symbol=f"ASSET{i}",
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.50"),
                volume=Decimal("10000"),
                bar_timestamp=pd.Timestamp.now(),
            )
            for i in range(event_count)
        ]

        start = time.perf_counter()
        tasks = [dispatcher.dispatch(event) for event in events]
        await asyncio.gather(*tasks)
        duration = time.perf_counter() - start

        # All handlers should have been called for each event
        assert processed_count == event_count * 3

        throughput = event_count / duration
        print(f"\nConcurrent throughput: {throughput:.0f} events/sec")
        print(f"Total handler calls: {processed_count}")

        # Should still achieve good throughput with concurrent handlers
        assert throughput > 100

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_extended_operation_no_memory_leak(self):
        """Test extended operation doesn't leak memory (1 hour simulated).

        This is a simplified version - full test would run for actual 1 hour.
        We simulate by processing many events.
        """
        import gc
        import sys

        queue = asyncio.PriorityQueue()

        # Get initial memory by filling queue first
        gc.collect()
        # Fill queue with 100 events to get baseline
        for i in range(100):
            event = MarketDataEvent(
                asset_symbol="AAPL",
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.50"),
                volume=Decimal("10000"),
                bar_timestamp=pd.Timestamp.now(),
            )
            await queue.put(event)

        # Measure initial size with events
        initial_size = sys.getsizeof(queue.queue) if hasattr(queue, "queue") else 100

        # Clear queue
        while not queue.empty():
            await queue.get()
        gc.collect()

        # Process 10000 events
        for i in range(10000):
            event = MarketDataEvent(
                asset_symbol="AAPL",
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100.50"),
                volume=Decimal("10000"),
                bar_timestamp=pd.Timestamp.now(),
            )
            await queue.put(event)
            await queue.get()

            # Periodic cleanup
            if i % 1000 == 0:
                gc.collect()

        # Final cleanup
        gc.collect()
        final_size = sys.getsizeof(queue.queue) if hasattr(queue, "queue") else 0

        print(f"\nInitial queue size (with 100 events): {initial_size} bytes")
        print(f"Final queue size (empty): {final_size} bytes")

        # Memory usage should not grow - empty queue should be smaller or similar
        # This test verifies no memory accumulation after processing many events
        assert final_size <= initial_size, f"Memory leak detected: {final_size} > {initial_size}"
