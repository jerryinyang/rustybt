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
Unified clock abstraction for simulation and live trading modes.
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Literal

import pandas as pd

# Resolution types
Resolution = Literal["daily", "minute", "second", "millisecond", "microsecond"]


class BaseClock(ABC):
    """Base class for simulation and live clocks."""

    @abstractmethod
    def __iter__(self) -> Iterator[pd.Timestamp]:
        """Iterate over timestamps."""
        pass

    @abstractmethod
    def get_current_time(self) -> pd.Timestamp:
        """Get current simulation/real time."""
        pass


class SimulationClock(BaseClock):
    """
    Fast-forward simulation clock with configurable resolution.

    Supports daily, minute, second, millisecond, and microsecond resolutions
    for backtesting strategies at different time granularities.
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
        """Generate timestamps based on resolution."""
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
        """Get current simulation time."""
        return self.current_time


class LiveClock(BaseClock):
    """
    Real-time clock for live trading.

    Yields timestamps in real-time for live trading mode.
    Includes configurable tick interval to control update frequency.
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
        """
        Infinite loop for live trading.

        Yields current UTC timestamp at configured tick interval.
        """
        while True:
            self.current_time = pd.Timestamp.now(tz="UTC")
            yield self.current_time
            # Sleep to avoid tight loop
            time.sleep(self.tick_interval_ms / 1000.0)

    def get_current_time(self) -> pd.Timestamp:
        """Get current real-world time in UTC."""
        return pd.Timestamp.now(tz="UTC")
