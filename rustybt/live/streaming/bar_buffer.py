"""Bar buffering system to accumulate ticks into OHLCV bars."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import structlog

from rustybt.live.streaming.models import TickData

logger = structlog.get_logger(__name__)


@dataclass
class OHLCVBar:
    """OHLCV bar data.

    Attributes:
        symbol: Asset symbol
        timestamp: Bar start timestamp (aligned to bar boundary)
        open: Open price (first tick)
        high: High price (max tick)
        low: Low price (min tick)
        close: Close price (last tick)
        volume: Total volume
    """

    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        """Validate OHLCV relationships."""
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) must be >= low ({self.low})")
        if self.high < self.open:
            raise ValueError(f"High ({self.high}) must be >= open ({self.open})")
        if self.high < self.close:
            raise ValueError(f"High ({self.high}) must be >= close ({self.close})")
        if self.low > self.open:
            raise ValueError(f"Low ({self.low}) must be <= open ({self.open})")
        if self.low > self.close:
            raise ValueError(f"Low ({self.low}) must be <= close ({self.close})")
        if self.volume < 0:
            raise ValueError(f"Volume must be non-negative, got {self.volume}")


class BarBuffer:
    """Accumulates ticks into OHLCV bars.

    Buffers ticks by symbol and bar resolution, emitting completed bars
    when the bar boundary is crossed.
    """

    def __init__(
        self,
        bar_resolution: int,
        on_bar_complete: Callable[[OHLCVBar], None] | None = None,
    ) -> None:
        """Initialize bar buffer.

        Args:
            bar_resolution: Bar resolution in seconds (e.g., 60 for 1-minute bars)
            on_bar_complete: Callback for completed bars
        """
        if bar_resolution <= 0:
            raise ValueError(f"bar_resolution must be positive, got {bar_resolution}")

        self.bar_resolution = bar_resolution
        self.on_bar_complete = on_bar_complete

        # Current bar data by symbol
        self._current_bars: dict[str, dict[str, any]] = defaultdict(dict)

    def add_tick(self, tick: TickData) -> OHLCVBar | None:
        """Add tick to buffer and return completed bar if boundary crossed.

        Args:
            tick: Tick data to add

        Returns:
            Completed bar if bar boundary crossed, None otherwise
        """
        # Calculate bar timestamp (aligned to bar boundary)
        bar_timestamp = self._align_to_bar_boundary(tick.timestamp)

        # Get current bar for symbol
        current_bar = self._current_bars[tick.symbol]

        # Check if this tick belongs to a new bar
        if "timestamp" in current_bar and current_bar["timestamp"] != bar_timestamp:
            # Emit completed bar
            completed_bar = self._build_bar(tick.symbol, current_bar)

            # Start new bar
            self._start_new_bar(tick.symbol, tick, bar_timestamp)

            # Call callback if provided
            if completed_bar and self.on_bar_complete:
                self.on_bar_complete(completed_bar)

            return completed_bar

        # Update current bar
        if "timestamp" not in current_bar:
            # First tick in bar
            self._start_new_bar(tick.symbol, tick, bar_timestamp)
        else:
            # Update existing bar
            self._update_bar(current_bar, tick)

        return None

    def flush_all(self) -> dict[str, OHLCVBar]:
        """Flush all incomplete bars and return them.

        Returns:
            Dict of symbol -> bar for all symbols with incomplete bars
        """
        bars = {}

        for symbol, bar_data in self._current_bars.items():
            if bar_data:  # Has data
                bar = self._build_bar(symbol, bar_data)
                if bar:
                    bars[symbol] = bar

        # Clear all buffers
        self._current_bars.clear()

        return bars

    def flush_symbol(self, symbol: str) -> OHLCVBar | None:
        """Flush incomplete bar for specific symbol.

        Args:
            symbol: Symbol to flush

        Returns:
            Incomplete bar if exists, None otherwise
        """
        bar_data = self._current_bars.get(symbol)
        if not bar_data:
            return None

        bar = self._build_bar(symbol, bar_data)

        # Clear symbol buffer
        self._current_bars[symbol] = {}

        return bar

    def _align_to_bar_boundary(self, timestamp: datetime) -> datetime:
        """Align timestamp to bar boundary.

        Args:
            timestamp: Timestamp to align

        Returns:
            Aligned timestamp (floored to bar resolution)
        """
        # Calculate seconds since epoch
        epoch = datetime(1970, 1, 1)
        seconds_since_epoch = int((timestamp - epoch).total_seconds())

        # Floor to bar resolution
        aligned_seconds = (seconds_since_epoch // self.bar_resolution) * self.bar_resolution

        # Convert back to datetime
        return epoch + timedelta(seconds=aligned_seconds)

    def _start_new_bar(self, symbol: str, tick: TickData, bar_timestamp: datetime) -> None:
        """Start new bar with first tick.

        Args:
            symbol: Symbol
            tick: First tick in bar
            bar_timestamp: Bar start timestamp
        """
        self._current_bars[symbol] = {
            "timestamp": bar_timestamp,
            "open": tick.price,
            "high": tick.price,
            "low": tick.price,
            "close": tick.price,
            "volume": tick.volume,
        }

        logger.debug(
            "bar_started",
            symbol=symbol,
            timestamp=bar_timestamp.isoformat(),
            price=str(tick.price),
        )

    def _update_bar(self, bar_data: dict[str, any], tick: TickData) -> None:
        """Update existing bar with new tick.

        Args:
            bar_data: Current bar data
            tick: New tick to add
        """
        # Update high/low
        bar_data["high"] = max(bar_data["high"], tick.price)
        bar_data["low"] = min(bar_data["low"], tick.price)

        # Update close (last tick)
        bar_data["close"] = tick.price

        # Accumulate volume
        bar_data["volume"] += tick.volume

    def _build_bar(self, symbol: str, bar_data: dict[str, any]) -> OHLCVBar | None:
        """Build OHLCVBar from bar data.

        Args:
            symbol: Symbol
            bar_data: Bar data dict

        Returns:
            OHLCVBar if bar_data is valid, None otherwise
        """
        if not bar_data or "timestamp" not in bar_data:
            return None

        try:
            bar = OHLCVBar(
                symbol=symbol,
                timestamp=bar_data["timestamp"],
                open=bar_data["open"],
                high=bar_data["high"],
                low=bar_data["low"],
                close=bar_data["close"],
                volume=bar_data["volume"],
            )

            logger.debug(
                "bar_completed",
                symbol=symbol,
                timestamp=bar.timestamp.isoformat(),
                open=str(bar.open),
                high=str(bar.high),
                low=str(bar.low),
                close=str(bar.close),
                volume=str(bar.volume),
            )

            return bar

        except ValueError as e:
            logger.error("invalid_bar_data", symbol=symbol, error=str(e))
            return None
