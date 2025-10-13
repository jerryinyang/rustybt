"""Event system for live trading engine.

This module defines the event types and priority system for the async event loop.
Events are processed in priority order: CircuitBreaker > SystemError > OrderFill >
OrderReject > ScheduledTrigger > MarketData.
"""

from decimal import Decimal
from enum import IntEnum
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field


class EventPriority(IntEnum):
    """Event priority levels (lower number = higher priority)."""

    CIRCUIT_BREAKER = 0  # Highest priority
    SYSTEM_ERROR = 1
    ORDER_FILL = 2
    ORDER_REJECT = 3
    SCHEDULED_TRIGGER = 4
    MARKET_DATA = 5


class Event(BaseModel):
    """Base event class with priority and timestamp."""

    priority: EventPriority
    timestamp: pd.Timestamp = Field(default_factory=pd.Timestamp.now)
    event_type: str

    class Config:
        """Pydantic config."""

        frozen = True
        arbitrary_types_allowed = True

    def __lt__(self, other: "Event") -> bool:
        """Compare events for priority queue ordering (lower priority value = higher priority)."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

    def __le__(self, other: "Event") -> bool:
        """Less than or equal comparison."""
        return self < other or (
            self.priority == other.priority and self.timestamp == other.timestamp
        )

    def __gt__(self, other: "Event") -> bool:
        """Greater than comparison."""
        return not self <= other

    def __ge__(self, other: "Event") -> bool:
        """Greater than or equal comparison."""
        return not self < other


class MarketDataEvent(Event):
    """Market data update event."""

    asset_symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    bar_timestamp: pd.Timestamp

    def __init__(self, **data: Any) -> None:
        """Initialize with MARKET_DATA priority."""
        data.setdefault("priority", EventPriority.MARKET_DATA)
        data.setdefault("event_type", "market_data")
        super().__init__(**data)


class OrderFillEvent(Event):
    """Order fill notification event."""

    order_id: str
    broker_order_id: str | None = None
    asset_symbol: str
    filled_amount: Decimal
    fill_price: Decimal
    commission: Decimal
    fill_timestamp: pd.Timestamp

    def __init__(self, **data: Any) -> None:
        """Initialize with ORDER_FILL priority."""
        data.setdefault("priority", EventPriority.ORDER_FILL)
        data.setdefault("event_type", "order_fill")
        super().__init__(**data)


class OrderRejectEvent(Event):
    """Order rejection event."""

    order_id: str
    broker_order_id: str | None = None
    asset_symbol: str
    amount: Decimal
    reason: str
    reject_timestamp: pd.Timestamp

    def __init__(self, **data: Any) -> None:
        """Initialize with ORDER_REJECT priority."""
        data.setdefault("priority", EventPriority.ORDER_REJECT)
        data.setdefault("event_type", "order_reject")
        super().__init__(**data)


class ScheduledTriggerEvent(Event):
    """Scheduled callback trigger event."""

    callback_name: str
    callback_args: dict[str, Any] = Field(default_factory=dict)
    trigger_timestamp: pd.Timestamp

    def __init__(self, **data: Any) -> None:
        """Initialize with SCHEDULED_TRIGGER priority."""
        data.setdefault("priority", EventPriority.SCHEDULED_TRIGGER)
        data.setdefault("event_type", "scheduled_trigger")
        super().__init__(**data)


class SystemErrorEvent(Event):
    """System error event."""

    error_type: str
    error_message: str
    exception_details: str | None = None
    error_timestamp: pd.Timestamp

    def __init__(self, **data: Any) -> None:
        """Initialize with SYSTEM_ERROR priority."""
        data.setdefault("priority", EventPriority.SYSTEM_ERROR)
        data.setdefault("event_type", "system_error")
        super().__init__(**data)
