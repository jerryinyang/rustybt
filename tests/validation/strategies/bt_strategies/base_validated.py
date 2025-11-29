"""Base strategy class for validated Backtrader strategies.

This module defines the BacktraderValidatedStrategy base class that enforces
structured logging for Backtrader implementations. Strategies extending
this class automatically produce JSONL logs that can be compared against
rustybt implementations.

The log format follows the validation framework schema (identical to rustybt):
    {
        "timestamp": ISO8601 string,
        "layer": "data|signals|orders|broker|portfolio",
        "event": descriptive event name,
        "asset": asset symbol or null,
        "data": dictionary of event-specific data
    }

Example:
    >>> import backtrader as bt
    >>> from pathlib import Path
    >>>
    >>> class MyStrategy(BacktraderValidatedStrategy):
    ...     params = BacktraderValidatedStrategy.params + (
    ...         ('sma_period', 20),
    ...     )
    ...
    ...     def next(self):
    ...         super().next()
    ...         # Custom logic here

Note:
    - Uses Backtrader conventions: params tuple, next(), stop()
    - Log schema MUST match rustybt for comparison compatibility
    - File cleanup happens in stop() (not __del__ like rustybt)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

import backtrader as bt

if TYPE_CHECKING:
    pass

# Type alias for validation layer names (matches rustybt)
ValidationLayer = str  # "data" | "signals" | "orders" | "broker" | "portfolio"

# Valid layer values for type checking and validation (matches rustybt)
VALID_LAYERS: frozenset[str] = frozenset(
    {"data", "signals", "orders", "broker", "portfolio"}
)


class BacktraderValidatedStrategy(bt.Strategy):
    """Base class for validated Backtrader strategies with auto-logging.

    This class extends bt.Strategy to automatically log lifecycle events
    to a JSONL file. The logs follow a standardized schema identical to
    RustyBTValidatedStrategy for cross-framework comparison.

    The strategy automatically logs:
        - __init__() -> layer: "data", event: "initialize"
        - next() -> layer: "data", event: "bar_received"

    Subclasses can use the _log_event() method directly for custom logging.

    Parameters (via params tuple)
    -----------------------------
    log_path : Path | str
        Path to the JSONL log file. The file will be created/overwritten.
        This parameter is REQUIRED.

    Attributes
    ----------
    _log_file : TextIO | None
        Open file handle for writing logs.

    Examples
    --------
    >>> class SMAStrategy(BacktraderValidatedStrategy):
    ...     params = BacktraderValidatedStrategy.params + (
    ...         ('sma_period', 20),
    ...     )
    ...
    ...     def __init__(self):
    ...         super().__init__()
    ...         self.sma = bt.indicators.SMA(period=self.p.sma_period)
    ...
    ...     def next(self):
    ...         super().next()
    ...         if self.data.close[0] > self.sma[0]:
    ...             self.buy()

    Notes
    -----
    - Log schema is identical to rustybt for cross-framework comparison
    - Uses Backtrader params tuple convention
    - Cleanup happens in stop() method (Backtrader lifecycle)
    """

    # Backtrader params tuple - subclasses extend with their own params
    params = (("log_path", None),)

    _log_file: TextIO | None

    def __init__(self) -> None:
        """Initialize the strategy and open log file.

        Raises
        ------
        ValueError
            If log_path parameter is not provided.
        TypeError
            If log_path is not a Path or string.
        """
        # Validate log_path parameter
        if self.p.log_path is None:
            raise ValueError("log_path parameter is required")

        log_path = self.p.log_path
        if isinstance(log_path, str):
            log_path = Path(log_path)
        elif not isinstance(log_path, Path):
            raise TypeError(
                f"log_path must be a Path or str, got {type(log_path).__name__}"
            )

        # Open log file
        self._log_file = open(log_path, "w")  # noqa: SIM115

        # Log initialization event (matches rustybt schema)
        self._log_event(
            layer="data",
            event="initialize",
            data={"context": "strategy_init"},
        )

    def _log_event(
        self,
        layer: ValidationLayer,
        event: str,
        data: dict[str, Any],
        *,
        asset: str | None = None,
    ) -> None:
        """Write a structured event to the JSONL log.

        Parameters
        ----------
        layer : str
            Validation layer: "data", "signals", "orders", "broker", or "portfolio".
        event : str
            Descriptive event name (e.g., "bar_received", "signal_computed").
        data : dict
            Event-specific data dictionary.
        asset : str | None, optional
            Asset symbol associated with the event, by default None.

        Notes
        -----
        - Schema is IDENTICAL to rustybt for comparison compatibility
        - Flushes after each write to prevent data loss on crash
        - Uses ISO8601 timestamp format
        """
        if self._log_file is None or self._log_file.closed:
            return

        # Extract asset from data if not explicitly provided
        if asset is None:
            asset = data.get("asset")

        entry = {
            "timestamp": datetime.now().isoformat(),
            "layer": layer,
            "event": event,
            "asset": asset,
            "data": data,
        }
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    def next(self) -> None:
        """Process the current bar and log the event.

        Override this method to add custom bar processing logic.
        Always call super().next() to ensure logging.

        The log entry includes the bar timestamp from Backtrader's data.
        """
        # Get current bar timestamp from Backtrader data
        try:
            bar_dt = self.data.datetime.datetime()
            timestamp_str = bar_dt.isoformat() if bar_dt else ""
        except (AttributeError, IndexError):
            timestamp_str = ""

        self._log_event(
            layer="data",
            event="bar_received",
            data={"timestamp": timestamp_str},
        )

    def log_signal(
        self,
        signal_name: str,
        signal_value: Any,  # noqa: ANN401
        asset: str | None = None,
        **extra_data: Any,  # noqa: ANN401
    ) -> None:
        """Log a signal computation event.

        Convenience method for logging signal events.

        Parameters
        ----------
        signal_name : str
            Name of the signal (e.g., "sma_crossover", "rsi").
        signal_value : Any
            Computed signal value.
        asset : str | None, optional
            Asset symbol the signal applies to.
        **extra_data : Any
            Additional data to include in the log.
        """
        self._log_event(
            layer="signals",
            event="signal_computed",
            data={
                "signal_name": signal_name,
                "signal_value": signal_value,
                **extra_data,
            },
            asset=asset,
        )

    def log_order_created(
        self,
        order_type: str,
        asset: str,
        quantity: float,
        limit_price: float | None = None,
        **extra_data: Any,  # noqa: ANN401
    ) -> None:
        """Log an order creation event.

        Convenience method for logging order events.

        Parameters
        ----------
        order_type : str
            Type of order (e.g., "market", "limit", "stop").
        asset : str
            Asset symbol being ordered.
        quantity : float
            Order quantity (positive for buy, negative for sell).
        limit_price : float | None, optional
            Limit price for limit orders.
        **extra_data : Any
            Additional data to include in the log.
        """
        self._log_event(
            layer="orders",
            event="order_created",
            data={
                "order_type": order_type,
                "quantity": quantity,
                "limit_price": limit_price,
                **extra_data,
            },
            asset=asset,
        )

    def stop(self) -> None:
        """Clean up resources when strategy completes.

        This method is called by Backtrader when the backtest finishes.
        It closes the log file to prevent handle leaks.
        """
        if hasattr(self, "_log_file") and self._log_file is not None:
            if not self._log_file.closed:
                self._log_file.close()

    def close_log(self) -> None:
        """Explicitly close the log file.

        This method can be called manually to close the log file
        before the strategy completes.

        Note: Named close_log() to avoid conflicting with Backtrader's
        built-in close() method for closing positions.
        """
        if hasattr(self, "_log_file") and self._log_file is not None:
            if not self._log_file.closed:
                self._log_file.close()
