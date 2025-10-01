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
Tests for simulation and live clocks.
"""

import pandas as pd
import pytest

from rustybt.gens.clock import LiveClock, SimulationClock


class TestSimulationClock:
    """Test simulation clock functionality."""

    def test_clock_initialization(self):
        """Test clock initializes with correct parameters."""
        start = pd.Timestamp("2023-01-01 09:30:00", tz="UTC")
        end = pd.Timestamp("2023-01-01 16:00:00", tz="UTC")

        clock = SimulationClock(start, end, resolution="minute")

        assert clock.start == start
        assert clock.end == end
        assert clock.resolution == "minute"
        assert clock.current_time == start

    def test_invalid_time_range(self):
        """Test clock rejects start > end."""
        start = pd.Timestamp("2023-01-02")
        end = pd.Timestamp("2023-01-01")

        with pytest.raises(ValueError, match="must be before"):
            SimulationClock(start, end)

    def test_invalid_resolution(self):
        """Test clock rejects invalid resolution."""
        start = pd.Timestamp("2023-01-01")
        end = pd.Timestamp("2023-01-02")

        with pytest.raises(ValueError, match="Invalid resolution"):
            SimulationClock(start, end, resolution="invalid")

    def test_daily_resolution(self):
        """Test clock generates daily timestamps."""
        start = pd.Timestamp("2023-01-01")
        end = pd.Timestamp("2023-01-05")

        clock = SimulationClock(start, end, resolution="daily")
        timestamps = list(clock)

        assert len(timestamps) == 5  # 5 days inclusive
        assert timestamps[0] == start
        assert timestamps[-1] == end
        assert timestamps[1] - timestamps[0] == pd.Timedelta(days=1)

    def test_minute_resolution(self):
        """Test clock generates minute timestamps."""
        start = pd.Timestamp("2023-01-01 09:30:00")
        end = pd.Timestamp("2023-01-01 09:35:00")

        clock = SimulationClock(start, end, resolution="minute")
        timestamps = list(clock)

        assert len(timestamps) == 6  # 6 minutes inclusive (09:30-09:35)
        assert timestamps[0] == start
        assert timestamps[-1] == end
        assert timestamps[1] - timestamps[0] == pd.Timedelta(minutes=1)

    def test_second_resolution(self):
        """Test clock generates second timestamps."""
        start = pd.Timestamp("2023-01-01 09:30:00")
        end = pd.Timestamp("2023-01-01 09:30:05")

        clock = SimulationClock(start, end, resolution="second")
        timestamps = list(clock)

        assert len(timestamps) == 6  # 6 seconds inclusive
        assert timestamps[0] == start
        assert timestamps[-1] == end
        assert timestamps[1] - timestamps[0] == pd.Timedelta(seconds=1)

    def test_millisecond_resolution(self):
        """Test clock generates millisecond timestamps."""
        start = pd.Timestamp("2023-01-01 09:30:00.000")
        end = pd.Timestamp("2023-01-01 09:30:00.100")

        clock = SimulationClock(start, end, resolution="millisecond")
        timestamps = list(clock)

        assert len(timestamps) == 101  # 0-100ms inclusive
        assert timestamps[0] == start
        assert timestamps[-1] == end
        assert timestamps[1] - timestamps[0] == pd.Timedelta(milliseconds=1)

    def test_microsecond_resolution(self):
        """Test clock generates microsecond timestamps."""
        start = pd.Timestamp("2023-01-01 09:30:00.000000")
        end = pd.Timestamp("2023-01-01 09:30:00.000100")

        clock = SimulationClock(start, end, resolution="microsecond")
        timestamps = list(clock)

        assert len(timestamps) == 101  # 0-100μs inclusive
        assert timestamps[0] == start
        assert timestamps[-1] == end
        assert timestamps[1] - timestamps[0] == pd.Timedelta(microseconds=1)

    def test_monotonic_progression(self):
        """Test timestamps always increase monotonically."""
        start = pd.Timestamp("2023-01-01")
        end = pd.Timestamp("2023-01-10")

        clock = SimulationClock(start, end, resolution="daily")
        timestamps = list(clock)

        # Verify monotonic increase
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i - 1]

    def test_get_current_time(self):
        """Test get_current_time tracks iteration."""
        start = pd.Timestamp("2023-01-01")
        end = pd.Timestamp("2023-01-03")

        clock = SimulationClock(start, end, resolution="daily")

        # Before iteration
        assert clock.get_current_time() == start

        # During iteration
        timestamps = []
        for ts in clock:
            timestamps.append(ts)
            assert clock.get_current_time() == ts

        # Verify all timestamps captured
        assert len(timestamps) == 3


class TestLiveClock:
    """Test live clock functionality."""

    def test_live_clock_initialization(self):
        """Test live clock initializes with default parameters."""
        clock = LiveClock()

        assert clock.tick_interval_ms == 1
        assert clock.current_time is not None

    def test_live_clock_custom_interval(self):
        """Test live clock accepts custom tick interval."""
        clock = LiveClock(tick_interval_ms=10)

        assert clock.tick_interval_ms == 10

    def test_invalid_tick_interval(self):
        """Test live clock rejects non-positive tick interval."""
        with pytest.raises(ValueError, match="must be positive"):
            LiveClock(tick_interval_ms=0)

        with pytest.raises(ValueError, match="must be positive"):
            LiveClock(tick_interval_ms=-1)

    def test_get_current_time(self):
        """Test live clock returns current UTC time."""
        clock = LiveClock()

        time1 = clock.get_current_time()
        assert time1.tz is not None  # Has timezone
        assert str(time1.tz) == "UTC"

        # Time should progress (even if slightly)
        import time

        time.sleep(0.01)  # 10ms
        time2 = clock.get_current_time()
        assert time2 >= time1

    def test_live_clock_iteration(self):
        """Test live clock yields timestamps."""
        clock = LiveClock(tick_interval_ms=10)

        # Test limited iteration
        timestamps = []
        for i, ts in enumerate(clock):
            timestamps.append(ts)
            if i >= 2:  # Get 3 timestamps
                break

        assert len(timestamps) == 3

        # Timestamps should progress
        assert timestamps[1] >= timestamps[0]
        assert timestamps[2] >= timestamps[1]
