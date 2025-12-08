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
import math
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

import backtrader as bt

if TYPE_CHECKING:
    pass

# Type alias for validation layer names (matches rustybt)
ValidationLayer = str  # "data" | "signals" | "orders" | "broker" | "portfolio"

# Valid layer values for type checking and validation (matches rustybt)
VALID_LAYERS: frozenset[str] = frozenset({"data", "signals", "orders", "broker", "portfolio"})


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
    _current_simulation_timestamp: str | None
    # Portfolio tracking for Layer 4-5 events
    _portfolio_values: list[float]
    _portfolio_timestamps: list[str]
    _peak_value: float
    _initial_value: float | None

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
            raise TypeError(f"log_path must be a Path or str, got {type(log_path).__name__}")

        # Open log file
        self._log_file = open(log_path, "w")  # noqa: SIM115
        self._current_simulation_timestamp = None

        # Initialize portfolio tracking for Layer 4-5 events
        self._portfolio_values = []
        self._portfolio_timestamps = []
        self._peak_value = 0.0
        self._initial_value = None

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
        simulation_timestamp: datetime | str | None = None,
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
        simulation_timestamp : datetime | str | None, optional
            Simulation timestamp for the event. This is the time in the backtest
            simulation, not the wall-clock time. Used for cross-framework comparison.
            If None, falls back to current time.

        Notes
        -----
        - Schema is IDENTICAL to rustybt for comparison compatibility
        - Flushes after each write to prevent data loss on crash
        - Uses ISO8601 timestamp format
        - The 'timestamp' field contains simulation time for comparison
        - The 'logged_at' field contains execution time for debugging
        """
        if self._log_file is None or self._log_file.closed:
            return

        # Extract asset from data if not explicitly provided
        if asset is None:
            asset = data.get("asset")

        # Format simulation timestamp (normalize to ISO format with 'T')
        if simulation_timestamp is None:
            ts_str = datetime.now().isoformat()
        elif isinstance(simulation_timestamp, datetime):
            ts_str = simulation_timestamp.isoformat()
        else:
            # Normalize string format: replace space with 'T' for ISO compliance
            ts_str = str(simulation_timestamp).replace(" ", "T")

        entry = {
            "timestamp": ts_str,
            "logged_at": datetime.now().isoformat(),
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

        The log entry uses the bar timestamp from Backtrader's data as the
        simulation timestamp for cross-framework comparison.
        """
        # Get current bar timestamp from Backtrader data
        try:
            bar_dt = self.data.datetime.datetime()
            self._current_simulation_timestamp = bar_dt.isoformat() if bar_dt else None
        except (AttributeError, IndexError):
            self._current_simulation_timestamp = None

        # Include timestamp in data dict for backward compatibility
        event_data: dict[str, Any] = {}
        if self._current_simulation_timestamp is not None:
            event_data["timestamp"] = self._current_simulation_timestamp

        self._log_event(
            layer="data",
            event="bar_received",
            data=event_data,
            simulation_timestamp=self._current_simulation_timestamp,
        )

    def log_signal(
        self,
        signal_name: str,
        signal_value: Any,  # noqa: ANN401
        asset: str | None = None,
        simulation_timestamp: datetime | str | None = None,
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
        simulation_timestamp : datetime | str | None, optional
            Simulation timestamp for the event. If None, uses current bar timestamp.
        **extra_data : Any
            Additional data to include in the log.
        """
        # Use provided timestamp or fall back to current simulation timestamp
        ts = (
            simulation_timestamp
            if simulation_timestamp is not None
            else self._current_simulation_timestamp
        )
        self._log_event(
            layer="signals",
            event="signal_computed",
            data={
                "signal_name": signal_name,
                "signal_value": signal_value,
                **extra_data,
            },
            asset=asset,
            simulation_timestamp=ts,
        )

    def log_order_created(
        self,
        order_type: str,
        asset: str,
        quantity: float,
        limit_price: float | None = None,
        simulation_timestamp: datetime | str | None = None,
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
        simulation_timestamp : datetime | str | None, optional
            Simulation timestamp for the event. If None, uses current bar timestamp.
        **extra_data : Any
            Additional data to include in the log.
        """
        # Use provided timestamp or fall back to current simulation timestamp
        ts = (
            simulation_timestamp
            if simulation_timestamp is not None
            else self._current_simulation_timestamp
        )
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
            simulation_timestamp=ts,
        )

    def notify_order(self, order: bt.Order) -> None:
        """Handle order notifications from Backtrader broker.

        This method is called automatically by Backtrader when order state changes.
        Logs Layer 4 (broker) events for transaction, commission, and slippage.

        Parameters
        ----------
        order : bt.Order
            The order object with status, execution details.
        """
        # Only log completed (filled) orders
        if order.status != order.Completed:
            return

        # Get asset name from order's data feed
        asset = order.data._name if hasattr(order.data, "_name") else None

        # Log transaction_executed
        self._log_event(
            layer="broker",
            event="transaction_executed",
            data={
                "data_fill_price": order.executed.price,
                "data_fill_quantity": order.executed.size,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log commission_charged
        self._log_event(
            layer="broker",
            event="commission_charged",
            data={
                "data_commission": order.executed.comm,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log slippage_applied (0 for market orders at close price)
        self._log_event(
            layer="broker",
            event="slippage_applied",
            data={
                "data_slippage": 0.0,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

    def notify_cashvalue(self, cash: float, value: float) -> None:
        """Handle cash/value updates from Backtrader broker.

        This method is called automatically by Backtrader after each bar.
        Logs Layer 4 (cash_updated) and Layer 5 (portfolio) events.

        Only logs events after warmup period (when _current_simulation_timestamp is set),
        to match rustybt behavior which skips logging during indicator warmup.

        Parameters
        ----------
        cash : float
            Current cash balance.
        value : float
            Current total portfolio value (cash + positions).
        """
        # Skip logging during warmup (match rustybt behavior)
        # During warmup, next() hasn't been called so _current_simulation_timestamp is None
        if not self._current_simulation_timestamp:
            return

        # Log cash_updated (Layer 4)
        self._log_event(
            layer="broker",
            event="cash_updated",
            data={
                "data_cash_balance": cash,
            },
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log portfolio_value_updated (Layer 5)
        self._log_event(
            layer="portfolio",
            event="portfolio_value_updated",
            data={
                "data_portfolio_value": value,
            },
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Track values for returns and drawdown calculation
        if self._current_simulation_timestamp:
            self._portfolio_values.append(value)
            self._portfolio_timestamps.append(self._current_simulation_timestamp)

            # Initialize peak and initial value
            if self._initial_value is None:
                self._initial_value = value
                self._peak_value = value

            # Update peak for drawdown
            if value > self._peak_value:
                self._peak_value = value

            # Calculate and log daily return (after first bar)
            if len(self._portfolio_values) > 1:
                prev_value = self._portfolio_values[-2]
                if prev_value > 0:
                    daily_return = (value - prev_value) / prev_value
                    self._log_event(
                        layer="portfolio",
                        event="daily_return_calculated",
                        data={
                            "data_daily_return": daily_return,
                        },
                        simulation_timestamp=self._current_simulation_timestamp,
                    )

            # Calculate and log drawdown
            if self._peak_value > 0:
                drawdown = (self._peak_value - value) / self._peak_value
                self._log_event(
                    layer="portfolio",
                    event="drawdown_updated",
                    data={
                        "data_drawdown": drawdown,
                    },
                    simulation_timestamp=self._current_simulation_timestamp,
                )

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from portfolio value history.

        Returns
        -------
        float
            Annualized Sharpe ratio (assuming 252 trading days).
            Returns 0.0 if insufficient data.
        """
        if len(self._portfolio_values) < 2:
            return 0.0

        # Calculate daily returns
        returns = []
        for i in range(1, len(self._portfolio_values)):
            prev = self._portfolio_values[i - 1]
            curr = self._portfolio_values[i]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return 0.0

        # Calculate mean and std of returns
        mean_return = sum(returns) / len(returns)
        if len(returns) > 1:
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_return = math.sqrt(variance)
        else:
            std_return = 0.0

        # Annualize (assuming 252 trading days)
        if std_return > 0:
            sharpe = (mean_return / std_return) * math.sqrt(252)
        else:
            sharpe = 0.0

        return sharpe

    def stop(self) -> None:
        """Clean up resources when strategy completes.

        This method is called by Backtrader when the backtest finishes.
        Logs final portfolio metrics (Layer 5) and closes the log file.
        """
        # Log final_metrics (Layer 5)
        if self._portfolio_values:
            sharpe = self._calculate_sharpe_ratio()
            final_value = self._portfolio_values[-1]
            initial_value = self._portfolio_values[0] if self._portfolio_values else 0.0
            total_return = ((final_value / initial_value) - 1.0) * 100 if initial_value > 0 else 0.0
            self._log_event(
                layer="portfolio",
                event="final_metrics",
                data={
                    "data_sharpe_ratio": sharpe,
                    "data_final_portfolio_value": final_value,
                    "data_initial_portfolio_value": initial_value,
                    "data_total_return_pct": total_return,
                },
                simulation_timestamp=self._current_simulation_timestamp,
            )

        # Close log file
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
