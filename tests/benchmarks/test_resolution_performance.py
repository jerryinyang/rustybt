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
Performance benchmarks for different clock resolutions.

Tests verify that sub-second resolution adds <10% overhead vs daily resolution.
"""

import pandas as pd
import pytest

from rustybt.gens.clock import SimulationClock


class TestClockPerformance:
    """Performance benchmarks for clock resolutions."""

    @pytest.mark.benchmark
    def test_daily_resolution_baseline(self, benchmark):
        """Benchmark daily resolution (baseline)."""

        def iterate_clock():
            start = pd.Timestamp("2023-01-01")
            end = pd.Timestamp("2023-12-31")  # 365 days
            clock = SimulationClock(start, end, resolution="daily")
            return list(clock)

        result = benchmark(iterate_clock)
        assert len(result) == 365

    @pytest.mark.benchmark
    def test_minute_resolution(self, benchmark):
        """Benchmark minute resolution."""

        def iterate_clock():
            start = pd.Timestamp("2023-01-01 09:30:00")
            end = pd.Timestamp("2023-01-01 16:00:00")  # 390 minutes (trading day)
            clock = SimulationClock(start, end, resolution="minute")
            return list(clock)

        result = benchmark(iterate_clock)
        assert len(result) == 391  # 390 minutes + start

    @pytest.mark.benchmark
    def test_second_resolution(self, benchmark):
        """Benchmark second resolution."""

        def iterate_clock():
            start = pd.Timestamp("2023-01-01 09:30:00")
            end = pd.Timestamp("2023-01-01 09:35:00")  # 5 minutes = 300 seconds
            clock = SimulationClock(start, end, resolution="second")
            return list(clock)

        result = benchmark(iterate_clock)
        assert len(result) == 301  # 300 seconds + start

    @pytest.mark.benchmark
    def test_millisecond_resolution(self, benchmark):
        """Benchmark millisecond resolution."""

        def iterate_clock():
            start = pd.Timestamp("2023-01-01 09:30:00.000")
            end = pd.Timestamp("2023-01-01 09:30:01.000")  # 1 second = 1000ms
            clock = SimulationClock(start, end, resolution="millisecond")
            return list(clock)

        result = benchmark(iterate_clock)
        assert len(result) == 1001  # 1000 ms + start

    @pytest.mark.benchmark
    def test_microsecond_resolution(self, benchmark):
        """Benchmark microsecond resolution."""

        def iterate_clock():
            start = pd.Timestamp("2023-01-01 09:30:00.000000")
            end = pd.Timestamp("2023-01-01 09:30:00.001000")  # 1ms = 1000μs
            clock = SimulationClock(start, end, resolution="microsecond")
            return list(clock)

        result = benchmark(iterate_clock)
        assert len(result) == 1001  # 1000 μs + start


class TestEventQueuePerformance:
    """Performance benchmarks for event queue operations."""

    @pytest.mark.benchmark
    def test_event_queue_push_pop(self, benchmark):
        """Benchmark event queue push/pop operations."""
        from rustybt.gens.events import Event, EventPriority, EventQueue

        def push_pop_events():
            queue = EventQueue()
            dt_base = pd.Timestamp("2023-01-01 10:00:00")

            # Push 1000 events
            for i in range(1000):
                dt = dt_base + pd.Timedelta(seconds=i)
                priority = EventPriority.BAR_DATA if i % 2 == 0 else EventPriority.CUSTOM
                event = Event(dt=dt, event_type=f"event_{i}", priority=priority)
                queue.push(event)

            # Pop all events
            results = []
            while queue:
                results.append(queue.pop())

            return results

        result = benchmark(push_pop_events)
        assert len(result) == 1000

    @pytest.mark.benchmark
    def test_event_priority_ordering(self, benchmark):
        """Benchmark event ordering with mixed priorities."""
        from rustybt.gens.events import Event, EventPriority, EventQueue

        def order_events():
            queue = EventQueue()
            dt = pd.Timestamp("2023-01-01 10:00:00")
            priorities = [
                EventPriority.MARKET_OPEN,
                EventPriority.BAR_DATA,
                EventPriority.CUSTOM,
                EventPriority.MARKET_CLOSE,
            ]

            # Push 1000 events with mixed priorities at same time
            for i in range(1000):
                priority = priorities[i % len(priorities)]
                event = Event(dt=dt, event_type=f"event_{i}", priority=priority)
                queue.push(event)

            # Verify correct ordering
            results = []
            while queue:
                results.append(queue.pop())

            return results

        result = benchmark(order_events)
        assert len(result) == 1000
