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

"""Event system with priority handling and custom triggers.

Provides a flexible event system for managing simulation events with:
- Priority-based event ordering (MARKET_OPEN, BAR_DATA, CUSTOM, MARKET_CLOSE)
- Custom event triggers (price thresholds, time intervals)
- Event queue management with deterministic ordering

Classes:
    EventPriority: Enum defining event priority levels
    Event: Dataclass representing a simulation event
    EventTrigger: Abstract base for custom triggers
    PriceThresholdTrigger: Trigger when price crosses threshold
    TimeIntervalTrigger: Trigger at regular intervals
    EventQueue: Priority queue for managing events

Examples:
    Create and queue events with different priorities::

        import pandas as pd
        from rustybt.gens.events import Event, EventPriority, EventQueue

        queue = EventQueue()

        # Add events with different priorities
        queue.push(Event(
            dt=pd.Timestamp('2023-01-01 09:30'),
            event_type='market_open',
            priority=EventPriority.MARKET_OPEN
        ))

        queue.push(Event(
            dt=pd.Timestamp('2023-01-01 09:31'),
            event_type='bar_data',
            priority=EventPriority.BAR_DATA,
            data={'symbol': 'AAPL', 'price': 150.0}
        ))

        # Events are retrieved in priority order
        event = queue.pop()
        assert event.event_type == 'market_open'

    Use price threshold trigger::

        from decimal import Decimal
        from rustybt.gens.events import PriceThresholdTrigger

        class AlertTrigger(PriceThresholdTrigger):
            def on_trigger(self, context, data):
                print(f"Price crossed ${self.threshold}!")

        trigger = AlertTrigger(
            asset='AAPL',
            threshold=Decimal('150.00'),
            direction='above'
        )
"""

import heapq
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import IntEnum
from typing import Any

import pandas as pd


class EventPriority(IntEnum):
    """
    Event priority levels.

    Higher numbers = higher priority (processed first).
    """

    MARKET_OPEN = 100
    BAR_DATA = 50
    CUSTOM = 25
    MARKET_CLOSE = 10


@dataclass(order=True)
class Event:
    """Represents a simulation event with timestamp, type, and priority.

    Events are ordered by: timestamp (ascending), priority (descending via
    negation), then sequence number for deterministic tie-breaking.

    Attributes:
        dt: Event timestamp
        event_type: String describing event type (e.g., 'bar_data', 'market_open')
        priority: Priority level from EventPriority enum
        data: Optional dictionary with event-specific data
        priority_neg: Internal field for heap ordering (auto-set)
        sequence: Internal sequence number for tie-breaking (auto-set)

    Examples:
        Create a market open event::

            import pandas as pd
            from rustybt.gens.events import Event, EventPriority

            event = Event(
                dt=pd.Timestamp('2023-01-01 09:30'),
                event_type='market_open',
                priority=EventPriority.MARKET_OPEN
            )

        Create a bar data event with payload::

            event = Event(
                dt=pd.Timestamp('2023-01-01 09:31'),
                event_type='bar_data',
                priority=EventPriority.BAR_DATA,
                data={
                    'symbol': 'AAPL',
                    'open': 150.0,
                    'high': 151.0,
                    'low': 149.5,
                    'close': 150.5,
                    'volume': 1000000
                }
            )

            # Access event data
            price = event.data['close']
    """

    # Comparison fields (for heapq) - must come first for ordering
    dt: pd.Timestamp = field(compare=True)
    priority_neg: int = field(init=False, compare=True, repr=False)
    sequence: int = field(default=0, compare=True, repr=False)

    # Non-comparison fields - init fields must come before fields with defaults
    event_type: str = ""
    priority: int = EventPriority.BAR_DATA
    data: dict | None = None

    def __post_init__(self):
        """Set negative priority for max-heap behavior with min-heap.

        Python's heapq is a min-heap, so we negate priority values to
        achieve max-heap behavior (higher priority = processed first).
        """
        # heapq is min-heap, so negate priority for max-heap
        object.__setattr__(self, "priority_neg", -self.priority)


class EventTrigger(ABC):
    """
    Base class for custom event triggers.

    Triggers allow strategies to register custom conditions that
    fire callbacks when specific market conditions occur.
    """

    @abstractmethod
    def should_trigger(self, current_time: pd.Timestamp, data: dict) -> bool:
        """
        Check if event should trigger.

        Args:
            current_time: Current simulation time
            data: Market data dictionary (asset -> bar data)

        Returns:
            True if trigger condition is met
        """
        pass

    @abstractmethod
    def on_trigger(self, context, data):
        """
        Callback when event triggers.

        Args:
            context: Algorithm context
            data: BarData object for current time
        """
        pass


class PriceThresholdTrigger(EventTrigger):
    """
    Trigger when price crosses threshold.

    Fires when price crosses above or below a specified threshold.
    """

    def __init__(
        self,
        asset: Any,
        threshold: Decimal,
        direction: str = "above",
        field: str = "close",
    ):
        """
        Initialize price threshold trigger.

        Args:
            asset: Asset to monitor
            threshold: Price threshold to cross
            direction: 'above' or 'below' - direction of crossing
            field: Price field to monitor ('open', 'high', 'low', 'close')

        Raises:
            ValueError: If direction is invalid
        """
        if direction not in ("above", "below"):
            raise ValueError(f"direction must be 'above' or 'below', got '{direction}'")

        if field not in ("open", "high", "low", "close"):
            raise ValueError(f"field must be 'open', 'high', 'low', or 'close', got '{field}'")

        self.asset = asset
        self.threshold = threshold
        self.direction = direction
        self.field = field
        self.last_price: Decimal | None = None

    def should_trigger(self, current_time: pd.Timestamp, data: dict) -> bool:
        """
        Check if price has crossed threshold.

        Args:
            current_time: Current simulation time
            data: Market data dictionary

        Returns:
            True if price crossed threshold since last check
        """
        # Get current price for asset
        asset_data = data.get(self.asset, {})
        current_price_raw = asset_data.get(self.field)

        if current_price_raw is None:
            return False

        current_price = Decimal(str(current_price_raw))

        # First observation - no crossing yet
        if self.last_price is None:
            self.last_price = current_price
            return False

        # Check for crossing
        if self.direction == "above":
            triggered = self.last_price < self.threshold <= current_price
        else:  # below
            triggered = self.last_price > self.threshold >= current_price

        self.last_price = current_price
        return triggered

    def on_trigger(self, context, data):
        """
        User-defined callback when price crosses threshold.

        Override this method in subclass or use with callback parameter.
        """
        pass


class TimeIntervalTrigger(EventTrigger):
    """
    Trigger at regular time intervals.

    Fires callback at specified time intervals during simulation.
    """

    def __init__(self, interval: pd.Timedelta, callback: Callable | None = None):
        """
        Initialize time interval trigger.

        Args:
            interval: Time interval between triggers
            callback: Optional callback function(context, data)

        Raises:
            ValueError: If interval is non-positive
        """
        if interval <= pd.Timedelta(0):
            raise ValueError(f"interval must be positive, got {interval}")

        self.interval = interval
        self.callback = callback
        self.last_trigger: pd.Timestamp | None = None

    def should_trigger(self, current_time: pd.Timestamp, data: dict) -> bool:
        """
        Check if interval has elapsed.

        Args:
            current_time: Current simulation time
            data: Market data dictionary (unused)

        Returns:
            True if interval has elapsed since last trigger
        """
        if self.last_trigger is None:
            self.last_trigger = current_time
            return True

        if current_time - self.last_trigger >= self.interval:
            self.last_trigger = current_time
            return True

        return False

    def on_trigger(self, context, data):
        """Call registered callback if provided."""
        if self.callback:
            self.callback(context, data)


class EventQueue:
    """Priority queue for managing simulation events.

    Events are ordered by:
    1. Timestamp (earliest first)
    2. Priority (highest first - MARKET_OPEN > BAR_DATA > CUSTOM > MARKET_CLOSE)
    3. Insertion order (for deterministic tie-breaking)

    Uses a heap-based implementation for O(log n) push/pop operations.

    Examples:
        Basic event queue usage::

            import pandas as pd
            from rustybt.gens.events import Event, EventPriority, EventQueue

            queue = EventQueue()

            # Add events
            queue.push(Event(
                dt=pd.Timestamp('2023-01-01 09:31'),
                event_type='bar_data',
                priority=EventPriority.BAR_DATA
            ))

            queue.push(Event(
                dt=pd.Timestamp('2023-01-01 09:30'),
                event_type='market_open',
                priority=EventPriority.MARKET_OPEN
            ))

            # Pop returns earliest event by timestamp
            event = queue.pop()
            assert event.event_type == 'market_open'

        Priority ordering at same timestamp::

            queue = EventQueue()

            # Same timestamp, different priorities
            dt = pd.Timestamp('2023-01-01 10:00')

            queue.push(Event(dt=dt, event_type='custom',
                           priority=EventPriority.CUSTOM))
            queue.push(Event(dt=dt, event_type='market_open',
                           priority=EventPriority.MARKET_OPEN))
            queue.push(Event(dt=dt, event_type='bar_data',
                           priority=EventPriority.BAR_DATA))

            # Higher priority processed first
            assert queue.pop().event_type == 'market_open'
            assert queue.pop().event_type == 'bar_data'
            assert queue.pop().event_type == 'custom'
    """

    def __init__(self):
        """Initialize empty event queue.

        Creates internal heap and sequence counter for deterministic ordering.
        """
        self._heap: list[Event] = []
        self._sequence = 0

    def push(self, event: Event):
        """Add event to queue.

        Assigns a sequence number and inserts into priority heap.
        Sequence numbers ensure deterministic ordering when events
        have identical timestamps and priorities.

        Args:
            event: Event to add to the queue.

        Examples:
            Add multiple events::

                queue = EventQueue()

                for i in range(100):
                    queue.push(Event(
                        dt=pd.Timestamp('2023-01-01') + pd.Timedelta(minutes=i),
                        event_type='bar_data',
                        priority=EventPriority.BAR_DATA
                    ))

                assert len(queue) == 100
        """
        event.sequence = self._sequence
        self._sequence += 1
        heapq.heappush(self._heap, event)

    def pop(self) -> Event:
        """Remove and return highest-priority event.

        Returns:
            Next event to process (earliest timestamp, highest priority).

        Raises:
            IndexError: If queue is empty.

        Examples:
            Process all events in order::

                queue = EventQueue()
                # ... add events ...

                while queue:
                    event = queue.pop()
                    process_event(event)
        """
        return heapq.heappop(self._heap)

    def peek(self) -> Event | None:
        """View next event without removing it.

        Useful for checking upcoming event without consuming it,
        for example to determine if processing should continue.

        Returns:
            Next event or None if queue is empty.

        Examples:
            Check next event time::

                queue = EventQueue()
                # ... add events ...

                next_event = queue.peek()
                if next_event and next_event.dt > cutoff_time:
                    # Stop processing
                    break
        """
        return self._heap[0] if self._heap else None

    def __len__(self) -> int:
        """Return number of events in queue.

        Returns:
            Number of events currently in the queue.
        """
        return len(self._heap)

    def __bool__(self) -> bool:
        """Return True if queue has events.

        Returns:
            True if queue is non-empty, False otherwise.

        Examples:
            Use in while loop::

                while queue:  # Evaluates __bool__
                    event = queue.pop()
                    process_event(event)
        """
        return bool(self._heap)
