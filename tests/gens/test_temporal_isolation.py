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
Tests for temporal isolation validation.
"""

from datetime import datetime

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.gens.temporal_isolation import LookaheadError, TemporalValidator


class TestTemporalValidator:
    """Test temporal isolation validator."""

    def test_initialization(self):
        """Test validator initializes with current time."""
        current_time = pd.Timestamp("2023-01-01 10:00")
        validator = TemporalValidator(current_time)

        assert validator.current_time == current_time
        assert not validator.debug_mode
        assert len(validator.access_log) == 0

    def test_debug_mode(self):
        """Test validator enables debug mode."""
        validator = TemporalValidator(pd.Timestamp("2023-01-01 10:00"), debug_mode=True)

        assert validator.debug_mode

    def test_valid_past_access(self):
        """Test validator allows access to past data."""
        validator = TemporalValidator(pd.Timestamp("2023-01-01 10:00"))

        # Should not raise
        validator.validate_access(pd.Timestamp("2023-01-01 09:00"), "price")

    def test_valid_current_access(self):
        """Test validator allows access to current data."""
        current_time = pd.Timestamp("2023-01-01 10:00")
        validator = TemporalValidator(current_time)

        # Should not raise
        validator.validate_access(current_time, "price")

    def test_invalid_future_access(self):
        """Test validator blocks access to future data."""
        validator = TemporalValidator(pd.Timestamp("2023-01-01 10:00"))

        with pytest.raises(LookaheadError, match="Attempted to access price at 2023-01-01 11:00"):
            validator.validate_access(pd.Timestamp("2023-01-01 11:00"), "price")

    def test_error_message_includes_asset(self):
        """Test error message includes asset when provided."""
        validator = TemporalValidator(pd.Timestamp("2023-01-01 10:00"))

        with pytest.raises(LookaheadError, match="for asset AAPL"):
            validator.validate_access(pd.Timestamp("2023-01-01 11:00"), "price", asset="AAPL")

    def test_update_time(self):
        """Test validator updates current time."""
        validator = TemporalValidator(pd.Timestamp("2023-01-01 10:00"))

        validator.update_time(pd.Timestamp("2023-01-01 11:00"))

        assert validator.current_time == pd.Timestamp("2023-01-01 11:00")

    def test_update_time_backwards_fails(self):
        """Test validator rejects moving backwards in time."""
        validator = TemporalValidator(pd.Timestamp("2023-01-01 10:00"))

        with pytest.raises(ValueError, match="Cannot move backwards in time"):
            validator.update_time(pd.Timestamp("2023-01-01 09:00"))

    def test_debug_mode_logs_access(self):
        """Test debug mode logs all data accesses."""
        validator = TemporalValidator(pd.Timestamp("2023-01-01 10:00"), debug_mode=True)

        validator.validate_access(pd.Timestamp("2023-01-01 09:00"), "price", asset="AAPL")

        log = validator.get_access_log()
        assert len(log) == 1
        assert log[0]["current_time"] == pd.Timestamp("2023-01-01 10:00")
        assert log[0]["requested_time"] == pd.Timestamp("2023-01-01 09:00")
        assert log[0]["data_type"] == "price"
        assert log[0]["asset"] == "AAPL"

    def test_clear_access_log(self):
        """Test clearing access log."""
        validator = TemporalValidator(pd.Timestamp("2023-01-01 10:00"), debug_mode=True)

        validator.validate_access(pd.Timestamp("2023-01-01 09:00"), "price")
        assert len(validator.get_access_log()) == 1

        validator.clear_access_log()
        assert len(validator.get_access_log()) == 0


class TestTemporalIsolationProperties:
    """Property-based tests for temporal isolation."""

    @given(
        current_times=st.lists(
            st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2023, 12, 31)),
            min_size=2,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_future_access_always_fails(self, current_times):
        """Property: Accessing future data should always raise LookaheadError."""
        sorted_times = sorted(current_times)

        for i in range(len(sorted_times) - 1):
            current = pd.Timestamp(sorted_times[i], tz="UTC")
            future = pd.Timestamp(sorted_times[i + 1], tz="UTC")

            # Skip if times are equal
            if current == future:
                continue

            validator = TemporalValidator(current_time=current)

            # Accessing future should fail
            with pytest.raises(LookaheadError):
                validator.validate_access(future, "test")

    @given(
        current_times=st.lists(
            st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2023, 12, 31)),
            min_size=2,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_past_access_always_succeeds(self, current_times):
        """Property: Accessing past data should never raise LookaheadError."""
        sorted_times = sorted(current_times)

        for i in range(1, len(sorted_times)):
            current = pd.Timestamp(sorted_times[i], tz="UTC")
            past = pd.Timestamp(sorted_times[i - 1], tz="UTC")

            # Skip if times are equal
            if current == past:
                continue

            validator = TemporalValidator(current_time=current)

            # Accessing past should succeed (no exception)
            validator.validate_access(past, "test")

    @given(
        start_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2023, 1, 1)),
        time_deltas=st.lists(st.integers(min_value=1, max_value=1000), min_size=5, max_size=20),
    )
    @settings(max_examples=100)
    def test_monotonic_time_updates(self, start_time, time_deltas):
        """Property: Time updates should always move forward monotonically."""
        validator = TemporalValidator(pd.Timestamp(start_time, tz="UTC"))

        current = pd.Timestamp(start_time, tz="UTC")
        for delta in time_deltas:
            next_time = current + pd.Timedelta(seconds=delta)
            validator.update_time(next_time)
            assert validator.current_time == next_time
            current = next_time

    @given(
        base_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2023, 1, 1)),
        offset_seconds=st.integers(min_value=-3600, max_value=3600),
    )
    @settings(max_examples=200)
    def test_boundary_conditions(self, base_time, offset_seconds):
        """Property: Test boundary between past and future access."""
        current = pd.Timestamp(base_time, tz="UTC")
        requested = current + pd.Timedelta(seconds=offset_seconds)

        validator = TemporalValidator(current_time=current)

        if offset_seconds <= 0:
            # Past or current - should succeed
            validator.validate_access(requested, "test")
        else:
            # Future - should fail
            with pytest.raises(LookaheadError):
                validator.validate_access(requested, "test")
