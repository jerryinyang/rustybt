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

"""Unified clock abstraction for simulation and live trading modes.

This module provides clock implementations that abstract time progression
for both backtesting (fast-forward simulation) and live trading (real-time).

Classes:
    BaseClock: Abstract base class for all clock implementations
    SimulationClock: Fast-forward clock for backtesting
    LiveClock: Real-time clock for live trading

Examples:
    Create a simulation clock for daily backtesting::

        import pandas as pd
        from rustybt.gens.clock import SimulationClock

        clock = SimulationClock(
            start=pd.Timestamp('2023-01-01'),
            end=pd.Timestamp('2023-12-31'),
            resolution='daily'
        )

        for timestamp in clock:
            current = clock.get_current_time()
            print(f"Simulating {current}")

    Create a live clock for paper trading::

        from rustybt.gens.clock import LiveClock

        clock = LiveClock(tick_interval_ms=100)

        # Run for a limited time in production
        count = 0
        for timestamp in clock:
            print(f"Live time: {timestamp}")
            count += 1
            if count > 10:
                break
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Literal

import pandas as pd

# Resolution types
Resolution = Literal["daily", "minute", "second", "millisecond", "microsecond"]


class BaseClock(ABC):
    """Base class for simulation and live clocks.

    Provides a unified interface for time iteration in both backtesting
    and live trading scenarios. Subclasses must implement __iter__ and
    get_current_time to define how time progresses.

    Examples:
        Iterate over clock timestamps::

            for timestamp in clock:
                current = clock.get_current_time()
                # Process data at this timestamp
                process_market_data(current)
    """

    @abstractmethod
    def __iter__(self) -> Iterator[pd.Timestamp]:
        """Iterate over timestamps.

        Yields:
            Timestamp: Next timestamp in the simulation or real-time sequence.
        """
        pass

    @abstractmethod
    def get_current_time(self) -> pd.Timestamp:
        """Get current simulation/real time.

        Returns:
            Timestamp: Current point in time (UTC).
        """
        pass


class SimulationClock(BaseClock):
    """Fast-forward simulation clock with configurable resolution.

    Supports daily, minute, second, millisecond, and microsecond resolutions
    for backtesting strategies at different time granularities. Time progresses
    instantly (no sleeping) to enable fast backtesting.

    Examples:
        Create a daily simulation clock::

            import pandas as pd
            from rustybt.gens.clock import SimulationClock

            clock = SimulationClock(
                start=pd.Timestamp('2023-01-01'),
                end=pd.Timestamp('2023-01-10'),
                resolution='daily'
            )

            for dt in clock:
                print(f"Day: {dt.date()}")
            # Outputs: 2023-01-01 through 2023-01-10

        Create a minute-level backtest::

            clock = SimulationClock(
                start=pd.Timestamp('2023-01-01 09:30'),
                end=pd.Timestamp('2023-01-01 16:00'),
                resolution='minute'
            )

            tick_count = sum(1 for _ in clock)
            print(f"Processed {tick_count} minutes")
    """

    def __init__(
        self,
        start: pd.Timestamp,
        end: pd.Timestamp,
        resolution: Resolution = "minute",
        trading_calendar=None,
    ):
        """
        Initialize simulation clock.

        Args:
            start: Start timestamp for simulation
            end: End timestamp for simulation
            resolution: Time resolution ('daily', 'minute', 'second', 'millisecond', 'microsecond')
            trading_calendar: Optional trading calendar for session-based iteration

        Raises:
            ValueError: If resolution is invalid or start > end
        """
        if start > end:
            raise ValueError(f"Start time {start} must be before end time {end}")

        valid_resolutions = {"daily", "minute", "second", "millisecond", "microsecond"}
        if resolution not in valid_resolutions:
            raise ValueError(
                f"Invalid resolution '{resolution}'. Must be one of {valid_resolutions}"
            )

        self.start = start
        self.end = end
        self.resolution = resolution
        self.trading_calendar = trading_calendar
        self.current_time = start

    def __iter__(self) -> Iterator[pd.Timestamp]:
        """Generate timestamps based on resolution.

        Yields timestamps at the configured resolution from start to end (inclusive).
        Updates internal state to track current simulation time.

        Yields:
            Timestamp: Next timestamp at the configured resolution.

        Examples:
            Iterate through simulation time::

                clock = SimulationClock(
                    start=pd.Timestamp('2023-01-01'),
                    end=pd.Timestamp('2023-01-03'),
                    resolution='daily'
                )

                for dt in clock:
                    # Process each day
                    assert dt == clock.get_current_time()
        """
        # Map resolution to pandas frequency
        freq_map = {
            "daily": pd.DateOffset(days=1),
            "minute": pd.DateOffset(minutes=1),
            "second": pd.DateOffset(seconds=1),
            "millisecond": pd.DateOffset(milliseconds=1),
            "microsecond": pd.DateOffset(microseconds=1),
        }

        freq = freq_map[self.resolution]
        current = self.start

        while current <= self.end:
            self.current_time = current
            yield current
            current = current + freq

    def get_current_time(self) -> pd.Timestamp:
        """Get current simulation time.

        Returns the most recently yielded timestamp from iteration.
        Initially set to start time before iteration begins.

        Returns:
            Timestamp: Current point in simulated time.

        Examples:
            Check current simulation time::

                clock = SimulationClock(
                    start=pd.Timestamp('2023-01-01'),
                    end=pd.Timestamp('2023-01-10'),
                    resolution='daily'
                )

                assert clock.get_current_time() == pd.Timestamp('2023-01-01')

                next(iter(clock))  # Advance to first timestamp
                assert clock.get_current_time() == pd.Timestamp('2023-01-01')
        """
        return self.current_time


class LiveClock(BaseClock):
    """Real-time clock for live trading.

    Yields timestamps in real-time for live trading mode. Unlike SimulationClock,
    this clock sleeps between ticks to match real-world time progression.
    Includes configurable tick interval to control update frequency.

    Examples:
        Create a live clock for paper trading::

            from rustybt.gens.clock import LiveClock

            clock = LiveClock(tick_interval_ms=1000)  # 1 second ticks

            # Process live data (runs indefinitely)
            for timestamp in clock:
                current = clock.get_current_time()
                # Fetch and process live market data
                process_live_data(current)

        Use with timeout for testing::

            import time
            from rustybt.gens.clock import LiveClock

            clock = LiveClock(tick_interval_ms=100)
            start_time = time.time()

            for timestamp in clock:
                if time.time() - start_time > 5:  # Run for 5 seconds
                    break
                print(f"Live tick: {timestamp}")
    """

    def __init__(self, tick_interval_ms: int = 1):
        """
        Initialize live clock.

        Args:
            tick_interval_ms: Milliseconds to sleep between ticks (default: 1ms)

        Raises:
            ValueError: If tick_interval_ms <= 0
        """
        if tick_interval_ms <= 0:
            raise ValueError(f"tick_interval_ms must be positive, got {tick_interval_ms}")

        self.tick_interval_ms = tick_interval_ms
        self.current_time = pd.Timestamp.now(tz="UTC")

    def __iter__(self) -> Iterator[pd.Timestamp]:
        """Infinite loop for live trading.

        Yields current UTC timestamp at configured tick interval.
        Sleeps between yields to match real-world time progression.

        Yields:
            Timestamp: Current real-world UTC timestamp.

        Examples:
            Iterate with break condition::

                clock = LiveClock(tick_interval_ms=500)
                count = 0

                for timestamp in clock:
                    print(f"Tick at {timestamp}")
                    count += 1
                    if count >= 10:
                        break  # Exit after 10 ticks
        """
        while True:
            self.current_time = pd.Timestamp.now(tz="UTC")
            yield self.current_time
            # Sleep to avoid tight loop
            time.sleep(self.tick_interval_ms / 1000.0)

    def get_current_time(self) -> pd.Timestamp:
        """Get current real-world time in UTC.

        Returns:
            Timestamp: Current wall-clock time in UTC timezone.

        Examples:
            Get current time::

                clock = LiveClock()
                now = clock.get_current_time()
                assert now.tz.zone == 'UTC'
        """
        return pd.Timestamp.now(tz="UTC")
