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
Tests for event system with priorities and custom triggers.
"""

from decimal import Decimal

import pandas as pd
import pytest

from rustybt.gens.events import (
    Event,
    EventPriority,
    EventQueue,
    PriceThresholdTrigger,
    TimeIntervalTrigger,
)


class TestEvent:
    """Test Event dataclass."""

    def test_event_creation(self):
        """Test event creates with correct fields."""
        dt = pd.Timestamp("2023-01-01 10:00")
        event = Event(
            dt=dt,
            event_type="bar",
            priority=EventPriority.BAR_DATA,
            data={"test": "data"},
        )

        assert event.dt == dt
        assert event.event_type == "bar"
        assert event.priority == EventPriority.BAR_DATA
        assert event.data == {"test": "data"}
        assert event.priority_neg == -EventPriority.BAR_DATA

    def test_event_default_priority(self):
        """Test event uses default priority."""
        dt = pd.Timestamp("2023-01-01 10:00")
        event = Event(dt=dt, event_type="bar")

        assert event.priority == EventPriority.BAR_DATA

    def test_event_ordering_by_time(self):
        """Test events order by timestamp first."""
        e1 = Event(dt=pd.Timestamp("2023-01-01 10:00"), event_type="early")
        e2 = Event(dt=pd.Timestamp("2023-01-01 11:00"), event_type="late")

        assert e1 < e2

    def test_event_ordering_by_priority(self):
        """Test events at same time order by priority."""
        dt = pd.Timestamp("2023-01-01 10:00")
        e1 = Event(dt=dt, event_type="high", priority=EventPriority.MARKET_OPEN)
        e2 = Event(dt=dt, event_type="low", priority=EventPriority.MARKET_CLOSE)

        # Higher priority should be "less than" (comes first in heap)
        assert e1 < e2


class TestEventQueue:
    """Test priority queue for events."""

    def test_queue_initialization(self):
        """Test queue initializes empty."""
        queue = EventQueue()

        assert len(queue) == 0
        assert not queue
        assert queue.peek() is None

    def test_push_and_pop(self):
        """Test pushing and popping events."""
        queue = EventQueue()
        event = Event(dt=pd.Timestamp("2023-01-01 10:00"), event_type="test")

        queue.push(event)

        assert len(queue) == 1
        assert queue

        popped = queue.pop()
        assert popped.event_type == "test"
        assert len(queue) == 0

    def test_priority_ordering(self):
        """Test events processed in priority order."""
        queue = EventQueue()
        dt = pd.Timestamp("2023-01-01 10:00")

        # Add events in random order
        queue.push(Event(dt=dt, event_type="bar", priority=EventPriority.BAR_DATA))
        queue.push(Event(dt=dt, event_type="open", priority=EventPriority.MARKET_OPEN))
        queue.push(Event(dt=dt, event_type="custom", priority=EventPriority.CUSTOM))
        queue.push(Event(dt=dt, event_type="close", priority=EventPriority.MARKET_CLOSE))

        # Pop in priority order
        assert queue.pop().event_type == "open"  # Highest priority
        assert queue.pop().event_type == "bar"
        assert queue.pop().event_type == "custom"
        assert queue.pop().event_type == "close"  # Lowest priority

    def test_time_ordering(self):
        """Test events processed in chronological order."""
        queue = EventQueue()

        queue.push(Event(dt=pd.Timestamp("2023-01-01 12:00"), event_type="noon"))
        queue.push(Event(dt=pd.Timestamp("2023-01-01 09:00"), event_type="morning"))
        queue.push(Event(dt=pd.Timestamp("2023-01-01 15:00"), event_type="afternoon"))

        assert queue.pop().event_type == "morning"
        assert queue.pop().event_type == "noon"
        assert queue.pop().event_type == "afternoon"

    def test_peek(self):
        """Test peeking at next event without removing."""
        queue = EventQueue()
        event = Event(dt=pd.Timestamp("2023-01-01 10:00"), event_type="test")

        queue.push(event)

        peeked = queue.peek()
        assert peeked.event_type == "test"
        assert len(queue) == 1  # Still in queue

    def test_deterministic_ordering(self):
        """Test same priority events maintain insertion order."""
        queue = EventQueue()
        dt = pd.Timestamp("2023-01-01 10:00")
        priority = EventPriority.CUSTOM

        # Add multiple events at same time and priority
        queue.push(Event(dt=dt, event_type="first", priority=priority))
        queue.push(Event(dt=dt, event_type="second", priority=priority))
        queue.push(Event(dt=dt, event_type="third", priority=priority))

        # Should maintain insertion order
        assert queue.pop().event_type == "first"
        assert queue.pop().event_type == "second"
        assert queue.pop().event_type == "third"


class TestPriceThresholdTrigger:
    """Test price threshold trigger."""

    def test_initialization(self):
        """Test trigger initializes with correct parameters."""
        asset = "AAPL"
        threshold = Decimal("100.00")

        trigger = PriceThresholdTrigger(asset, threshold, direction="above")

        assert trigger.asset == asset
        assert trigger.threshold == threshold
        assert trigger.direction == "above"
        assert trigger.field == "close"
        assert trigger.last_price is None

    def test_invalid_direction(self):
        """Test trigger rejects invalid direction."""
        with pytest.raises(ValueError, match="must be 'above' or 'below'"):
            PriceThresholdTrigger("AAPL", Decimal("100"), direction="invalid")

    def test_invalid_field(self):
        """Test trigger rejects invalid field."""
        with pytest.raises(ValueError, match="must be 'open', 'high', 'low', or 'close'"):
            PriceThresholdTrigger("AAPL", Decimal("100"), direction="above", field="invalid")

    def test_crossing_above_threshold(self):
        """Test trigger detects price crossing above threshold."""
        trigger = PriceThresholdTrigger("AAPL", Decimal("100.00"), direction="above")

        # First observation - no trigger
        assert not trigger.should_trigger(
            pd.Timestamp("2023-01-01"), {"AAPL": {"close": Decimal("99.00")}}
        )

        # Cross above threshold - should trigger
        assert trigger.should_trigger(
            pd.Timestamp("2023-01-02"), {"AAPL": {"close": Decimal("101.00")}}
        )

        # Stay above threshold - no trigger
        assert not trigger.should_trigger(
            pd.Timestamp("2023-01-03"), {"AAPL": {"close": Decimal("102.00")}}
        )

    def test_crossing_below_threshold(self):
        """Test trigger detects price crossing below threshold."""
        trigger = PriceThresholdTrigger("AAPL", Decimal("100.00"), direction="below")

        # Start above threshold
        assert not trigger.should_trigger(
            pd.Timestamp("2023-01-01"), {"AAPL": {"close": Decimal("105.00")}}
        )

        # Cross below threshold - should trigger
        assert trigger.should_trigger(
            pd.Timestamp("2023-01-02"), {"AAPL": {"close": Decimal("95.00")}}
        )

        # Stay below threshold - no trigger
        assert not trigger.should_trigger(
            pd.Timestamp("2023-01-03"), {"AAPL": {"close": Decimal("90.00")}}
        )

    def test_exact_threshold_crossing(self):
        """Test trigger fires when price equals threshold."""
        trigger = PriceThresholdTrigger("AAPL", Decimal("100.00"), direction="above")

        # Below threshold
        trigger.should_trigger(pd.Timestamp("2023-01-01"), {"AAPL": {"close": Decimal("99.00")}})

        # Exactly at threshold - should trigger
        assert trigger.should_trigger(
            pd.Timestamp("2023-01-02"), {"AAPL": {"close": Decimal("100.00")}}
        )

    def test_missing_data(self):
        """Test trigger handles missing data gracefully."""
        trigger = PriceThresholdTrigger("AAPL", Decimal("100.00"), direction="above")

        # Missing asset data
        assert not trigger.should_trigger(pd.Timestamp("2023-01-01"), {})

        # Missing price field
        assert not trigger.should_trigger(pd.Timestamp("2023-01-01"), {"AAPL": {}})

    def test_different_price_fields(self):
        """Test trigger works with different price fields."""
        trigger = PriceThresholdTrigger("AAPL", Decimal("100.00"), direction="above", field="high")

        # High crosses threshold
        assert not trigger.should_trigger(
            pd.Timestamp("2023-01-01"), {"AAPL": {"high": Decimal("99.00")}}
        )

        assert trigger.should_trigger(
            pd.Timestamp("2023-01-02"), {"AAPL": {"high": Decimal("101.00")}}
        )


class TestTimeIntervalTrigger:
    """Test time interval trigger."""

    def test_initialization(self):
        """Test trigger initializes with interval."""
        interval = pd.Timedelta(minutes=5)
        trigger = TimeIntervalTrigger(interval)

        assert trigger.interval == interval
        assert trigger.callback is None
        assert trigger.last_trigger is None

    def test_invalid_interval(self):
        """Test trigger rejects non-positive interval."""
        with pytest.raises(ValueError, match="must be positive"):
            TimeIntervalTrigger(pd.Timedelta(0))

        with pytest.raises(ValueError, match="must be positive"):
            TimeIntervalTrigger(pd.Timedelta(seconds=-1))

    def test_first_trigger(self):
        """Test trigger fires on first call."""
        trigger = TimeIntervalTrigger(pd.Timedelta(minutes=5))

        # First call should trigger
        assert trigger.should_trigger(pd.Timestamp("2023-01-01 10:00"), {})
        assert trigger.last_trigger == pd.Timestamp("2023-01-01 10:00")

    def test_interval_elapsed(self):
        """Test trigger fires after interval elapses."""
        trigger = TimeIntervalTrigger(pd.Timedelta(minutes=5))

        # First trigger
        trigger.should_trigger(pd.Timestamp("2023-01-01 10:00"), {})

        # Before interval - no trigger
        assert not trigger.should_trigger(pd.Timestamp("2023-01-01 10:04"), {})

        # After interval - should trigger
        assert trigger.should_trigger(pd.Timestamp("2023-01-01 10:05"), {})

    def test_callback_invoked(self):
        """Test callback is invoked on trigger."""
        callback_invoked = False

        def callback(context, data):
            nonlocal callback_invoked
            callback_invoked = True

        trigger = TimeIntervalTrigger(pd.Timedelta(minutes=5), callback=callback)

        # Trigger
        trigger.should_trigger(pd.Timestamp("2023-01-01 10:00"), {})
        trigger.on_trigger(context=None, data=None)

        assert callback_invoked
