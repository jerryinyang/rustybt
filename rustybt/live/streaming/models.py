"""Data models for WebSocket streaming."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TickSide(str, Enum):
    """Side of trade tick (buy or sell)."""

    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TickData:
    """Standardized tick data from WebSocket streams.

    Attributes:
        symbol: Asset symbol (e.g., 'BTCUSDT')
        timestamp: Tick timestamp (UTC)
        price: Trade price
        volume: Trade volume
        side: Trade side (buy/sell)
    """

    symbol: str
    timestamp: datetime
    price: Decimal
    volume: Decimal
    side: TickSide = TickSide.UNKNOWN

    def __post_init__(self) -> None:
        """Validate tick data."""
        if self.price <= 0:
            raise ValueError(f"Price must be positive, got {self.price}")
        if self.volume < 0:
            raise ValueError(f"Volume must be non-negative, got {self.volume}")


@dataclass(frozen=True)
class StreamConfig:
    """Configuration for WebSocket streaming.

    Attributes:
        bar_resolution: Bar resolution in seconds (e.g., 60 for 1-minute bars)
        heartbeat_interval: Heartbeat interval in seconds
        heartbeat_timeout: Heartbeat timeout in seconds (triggers reconnect)
        reconnect_attempts: Max reconnect attempts (None for infinite)
        reconnect_delay: Initial reconnect delay in seconds
        reconnect_max_delay: Maximum reconnect delay in seconds
        circuit_breaker_threshold: Number of consecutive errors to trip circuit breaker
    """

    bar_resolution: int = 60  # 1 minute
    heartbeat_interval: int = 30
    heartbeat_timeout: int = 60
    reconnect_attempts: int | None = None  # infinite
    reconnect_delay: int = 1
    reconnect_max_delay: int = 16
    circuit_breaker_threshold: int = 10

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.bar_resolution <= 0:
            raise ValueError(f"bar_resolution must be positive, got {self.bar_resolution}")
        if self.heartbeat_interval <= 0:
            raise ValueError(f"heartbeat_interval must be positive, got {self.heartbeat_interval}")
        if self.heartbeat_timeout <= 0:
            raise ValueError(f"heartbeat_timeout must be positive, got {self.heartbeat_timeout}")
        if self.reconnect_delay <= 0:
            raise ValueError(f"reconnect_delay must be positive, got {self.reconnect_delay}")
        if self.reconnect_max_delay < self.reconnect_delay:
            raise ValueError(
                f"reconnect_max_delay ({self.reconnect_max_delay}) must be >= "
                f"reconnect_delay ({self.reconnect_delay})"
            )
        if self.circuit_breaker_threshold <= 0:
            raise ValueError(
                f"circuit_breaker_threshold must be positive, got {self.circuit_breaker_threshold}"
            )
