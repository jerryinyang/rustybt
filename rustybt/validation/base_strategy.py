"""Base strategy classes for validation.

This module defines the ValidatedStrategy base classes that enforce
structured logging for rustybt implementations. Strategies extending
this class automatically produce JSONL logs that can be compared against
Backtrader reference implementations.

The log format follows the validation framework schema:
    {
        "timestamp": ISO8601 string,
        "layer": "data|signals|orders|broker|portfolio",
        "event": descriptive event name,
        "asset": asset symbol or null,
        "data": dictionary of event-specific data
    }

Architecture Note (Epic X):
    The logging functionality is provided as a mixin class (ValidatedStrategyMixin)
    that can be combined with rustybt's function-based strategy pattern. This allows:
    - Logging from real rustybt TradingAlgorithm execution
    - Integration with rustybt's DataPortal, Broker, and order APIs
    - Clear separation between logging and trading logic

Integration Pattern:
    Strategies use the function-based pattern with ValidatedStrategyMixin:

    >>> from rustybt.validation.base_strategy import ValidatedStrategyMixin
    >>> from rustybt.api import order_target, symbol
    >>>
    >>> class MyValidationContext(ValidatedStrategyMixin):
    ...     def __init__(self, log_path):
    ...         self._init_logging(log_path)
    ...         self.asset = None
    >>>
    >>> def initialize(context):
    ...     context.asset = symbol('AAPL')
    ...     context._log_event("data", "initialize", {})
    >>>
    >>> def handle_data(context, data):
    ...     context._log_event("data", "bar_received", {})
    ...     # Use real rustybt APIs: data.history(), order_target(), etc.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from types import TracebackType


# Type alias for validation layer names
ValidationLayer = str  # "data" | "signals" | "orders" | "broker" | "portfolio"

# Valid layer values for type checking and validation
VALID_LAYERS: frozenset[str] = frozenset({"data", "signals", "orders", "broker", "portfolio"})


class ValidatedStrategyMixin:
    """Mixin class providing validation logging functionality.

    This mixin provides the core logging infrastructure used by validated
    strategies. It can be used independently for testing or combined with
    rustybt's function-based strategy pattern for real backtest execution.

    The mixin provides:
        - JSONL log file management (open, write, close)
        - _log_event() method for structured event logging
        - Context manager support for automatic cleanup
        - Convenience methods for signal, order, and portfolio logging

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file. The file will be created/overwritten.

    Attributes:
    ----------
    _log_path : Path
        Path to the log file.
    _log_file : TextIO | None
        Open file handle for writing logs.

    Notes:
    -----
    - Log file is opened in write mode, overwriting any existing file
    - Each log entry is flushed immediately to prevent data loss
    - File handle is closed automatically via close() or context manager
    """

    _log_path: Path
    _log_file: TextIO | None

    def _init_logging(self, log_path: Path) -> None:
        """Initialize logging infrastructure.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.

        Raises:
        ------
        TypeError
            If log_path is not a Path object.
        """
        if not isinstance(log_path, Path):
            raise TypeError(f"log_path must be a Path, got {type(log_path).__name__}")

        self._log_path = log_path
        self._log_file = open(log_path, "w")  # noqa: SIM115

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

        Notes:
        -----
        - Flushes after each write to prevent data loss on crash
        - Uses ISO8601 timestamp format
        - Logs are written as single JSON lines (JSONL format)
        - The 'timestamp' field contains simulation time for comparison
        - The 'logged_at' field contains execution time for debugging

        Examples:
        --------
        >>> strategy._log_event(
        ...     layer="signals",
        ...     event="signal_computed",
        ...     data={"signal_name": "sma_crossover", "value": 1.0},
        ...     asset="AAPL",
        ...     simulation_timestamp="2020-01-15T00:00:00"
        ... )
        """
        if not hasattr(self, "_log_file") or self._log_file is None or self._log_file.closed:
            return

        # Extract asset from data if not explicitly provided
        if asset is None:
            asset = data.get("asset")

        # Format simulation timestamp (normalize to ISO format with 'T')
        if simulation_timestamp is None:
            ts_str = datetime.now().isoformat(timespec="milliseconds")
        elif isinstance(simulation_timestamp, datetime):
            ts_str = simulation_timestamp.isoformat()
        else:
            # Normalize string format: replace space with 'T' for ISO compliance
            ts_str = str(simulation_timestamp).replace(" ", "T")

        entry = {
            "timestamp": ts_str,
            "logged_at": datetime.now().isoformat(timespec="milliseconds"),
            "layer": layer,
            "event": event,
            "asset": asset,
            "data": data,
        }
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    def log_signal(
        self,
        signal_name: str,
        signal_value: Any,  # noqa: ANN401
        asset: str | None = None,
        simulation_timestamp: datetime | str | None = None,
        **extra_data: Any,  # noqa: ANN401
    ) -> None:
        """Log a signal computation event.

        Convenience method for logging signal events. Prefer using the
        @log_signal decorator for automatic logging.

        Parameters
        ----------
        signal_name : str
            Name of the signal (e.g., "sma_crossover", "rsi").
        signal_value : Any
            Computed signal value.
        asset : str | None, optional
            Asset symbol the signal applies to.
        simulation_timestamp : datetime | str | None, optional
            Simulation timestamp for the event.
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
            simulation_timestamp=simulation_timestamp,
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

        Convenience method for logging order events. Prefer using the
        @log_order decorator for automatic logging.

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
            Simulation timestamp for the event.
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
            simulation_timestamp=simulation_timestamp,
        )

    def log_broker_event(
        self,
        event: str,
        asset: str | None = None,
        simulation_timestamp: datetime | str | None = None,
        **extra_data: Any,  # noqa: ANN401
    ) -> None:
        """Log a broker layer event.

        Convenience method for logging broker events such as fills,
        rejections, cancellations, and other broker-related actions.

        Parameters
        ----------
        event : str
            Event type (e.g., "fill_executed", "order_rejected", "order_cancelled").
        asset : str | None, optional
            Asset symbol associated with the event.
        simulation_timestamp : datetime | str | None, optional
            Simulation timestamp for the event.
        **extra_data : Any
            Additional data to include in the log, typically:
            - order_id: ID of the related order
            - fill_price: Execution price for fills
            - fill_quantity: Quantity filled
            - commission: Commission charged
            - reason: Rejection/cancellation reason

        Examples:
        --------
        >>> strategy.log_broker_event(
        ...     event="fill_executed",
        ...     asset="AAPL",
        ...     order_id="12345",
        ...     fill_price=150.25,
        ...     fill_quantity=100,
        ...     commission=1.00,
        ...     simulation_timestamp="2020-01-15T00:00:00"
        ... )
        >>> strategy.log_broker_event(
        ...     event="order_rejected",
        ...     asset="GOOG",
        ...     order_id="12346",
        ...     reason="Insufficient funds",
        ... )
        """
        self._log_event(
            layer="broker",
            event=event,
            data=extra_data,
            asset=asset,
            simulation_timestamp=simulation_timestamp,
        )

    def log_portfolio_event(
        self,
        event: str,
        simulation_timestamp: datetime | str | None = None,
        **extra_data: Any,  # noqa: ANN401
    ) -> None:
        """Log a portfolio layer event.

        Convenience method for logging portfolio events such as
        portfolio value updates, returns, and drawdown.

        Parameters
        ----------
        event : str
            Event type (e.g., "portfolio_value_updated", "daily_return_calculated").
        simulation_timestamp : datetime | str | None, optional
            Simulation timestamp for the event.
        **extra_data : Any
            Additional data to include in the log, typically:
            - data_portfolio_value: Current portfolio value
            - data_daily_return: Daily return
            - data_drawdown: Current drawdown
            - data_sharpe_ratio: Sharpe ratio (for final_metrics)

        Examples:
        --------
        >>> strategy.log_portfolio_event(
        ...     event="portfolio_value_updated",
        ...     data_portfolio_value=105000.0,
        ...     simulation_timestamp="2020-01-15T00:00:00"
        ... )
        """
        self._log_event(
            layer="portfolio",
            event=event,
            data=extra_data,
            simulation_timestamp=simulation_timestamp,
        )

    def close(self) -> None:
        """Explicitly close the log file.

        Call this method to close the log file before the strategy
        is garbage collected. This is useful when you want to ensure
        the file is closed at a specific point in time.
        """
        if hasattr(self, "_log_file") and self._log_file is not None and not self._log_file.closed:
            self._log_file.close()

    def __del__(self) -> None:
        """Close log file on deletion to prevent handle leaks."""
        self.close()

    def __enter__(self) -> ValidatedStrategyMixin:  # noqa: PYI034
        """Enter context manager.

        Returns:
        -------
        ValidatedStrategyMixin
            Self for use in with statement.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager and close log file.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type if an exception was raised.
        exc_val : BaseException | None
            Exception value if an exception was raised.
        exc_tb : TracebackType | None
            Exception traceback if an exception was raised.
        """
        self.close()


class RustyBTValidatedStrategy(ValidatedStrategyMixin):
    """Validated strategy base class for rustybt integration.

    This class provides the validation logging infrastructure for strategies
    that execute through rustybt's real TradingAlgorithm engine. It removes
    all homebrew broker simulation and instead relies on rustybt's actual
    execution for:
    - Data access via DataPortal (data.history(), data.current())
    - Order execution via rustybt's order API (order(), order_target())
    - Portfolio tracking via context.portfolio
    - Broker simulation via rustybt's Blotter

    The class is designed to work with rustybt's function-based strategy pattern,
    where strategies define standalone initialize() and handle_data() functions
    that receive a context object (the TradingAlgorithm instance).

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file. The file will be created/overwritten.

    Attributes:
    ----------
    _current_simulation_timestamp : str | None
        The current simulation timestamp, updated on each handle_data call.
        Subclasses can use this when logging events.

    Examples:
    --------
    Basic usage with function-based pattern:

    >>> from pathlib import Path
    >>> from rustybt.validation.base_strategy import RustyBTValidatedStrategy
    >>>
    >>> class MySMAStrategy(RustyBTValidatedStrategy):
    ...     def __init__(self, log_path, fast_period=10, slow_period=30):
    ...         super().__init__(log_path)
    ...         self.fast_period = fast_period
    ...         self.slow_period = slow_period
    ...         self.asset = None
    ...
    ...     def initialize(self, context):
    ...         super().initialize(context)
    ...         # Use rustybt's symbol() to get asset reference
    ...         from rustybt.api import symbol
    ...         self.asset = symbol('AAPL')
    ...
    ...     def handle_data(self, context, data):
    ...         super().handle_data(context, data)
    ...         # Use rustybt's data.history() for indicators
    ...         prices = data.history(self.asset, 'close', self.slow_period, '1d')
    ...         fast_sma = prices[-self.fast_period:].mean()
    ...         slow_sma = prices.mean()
    ...
    ...         # Log signal
    ...         self.log_signal("sma_crossover", fast_sma > slow_sma,
    ...                         asset=str(self.asset),
    ...                         simulation_timestamp=self._current_simulation_timestamp)
    ...
    ...         # Use rustybt's order API
    ...         from rustybt.api import order_target
    ...         if fast_sma > slow_sma:
    ...             order_target(self.asset, 100)
    ...             self.log_order_created("market", str(self.asset), 100,
    ...                                    simulation_timestamp=self._current_simulation_timestamp)
    """

    _current_simulation_timestamp: str | None

    def __init__(self, log_path: Path) -> None:
        """Initialize the validated strategy with logging.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        """
        self._init_logging(log_path)
        self._current_simulation_timestamp = None

    def initialize(self, context: Any) -> None:  # noqa: ANN401, ARG002
        """Initialize strategy and log the event.

        Override this method to add custom initialization logic.
        Always call super().initialize(context) first.

        Parameters
        ----------
        context : Any
            The strategy context object (TradingAlgorithm instance in real execution).
        """
        self._log_event(
            layer="data",
            event="initialize",
            data={"context": "strategy_init"},
        )

    def _extract_simulation_timestamp(self, context: Any, data: Any) -> str | None:  # noqa: ANN401
        """Extract simulation timestamp from context or data.

        This method attempts to extract the current simulation time from
        rustybt's context object. In real execution, context.get_datetime()
        provides the simulation timestamp.

        Parameters
        ----------
        context : Any
            The strategy context object (TradingAlgorithm instance).
        data : Any
            The bar data object.

        Returns:
        -------
        str | None
            The simulation timestamp as a string, or None if not found.
        """
        # Try rustybt's get_datetime() method first (real execution)
        if context is not None and hasattr(context, "get_datetime"):
            try:
                dt = context.get_datetime()
                return dt.isoformat() if dt else None
            except (AttributeError, TypeError):
                pass  # Context doesn't support get_datetime, try fallback

        # Fallback: try context.datetime attribute
        if context is not None and hasattr(context, "datetime"):
            try:
                dt = context.datetime
                return dt.isoformat() if dt else None
            except (AttributeError, TypeError):
                pass  # Context.datetime not available, try fallback

        # Fallback: try context.current_dt attribute (for testing/mock scenarios)
        if context is not None and hasattr(context, "current_dt"):
            try:
                dt = context.current_dt
                if dt is not None:
                    # Handle both datetime objects and strings
                    if hasattr(dt, "isoformat"):
                        return dt.isoformat()
                    return str(dt)
            except (AttributeError, TypeError):
                pass  # Context.current_dt not available, try fallback

        # Fallback: try data dictionary (for testing/mock scenarios)
        if isinstance(data, dict):
            for col in ["timestamp", "datetime", "date"]:
                if col in data and data[col] is not None:
                    return str(data[col])

        return None

    def handle_data(self, context: Any, data: Any) -> None:  # noqa: ANN401
        """Process bar data and log the bar_received event.

        Override this method to add custom data handling logic.
        Always call super().handle_data(context, data) first to ensure
        proper timestamp extraction and bar_received logging.

        Parameters
        ----------
        context : Any
            The strategy context object (TradingAlgorithm instance in real execution).
        data : Any
            The bar data object (BarData in real execution).
        """
        # Extract and store simulation timestamp for use by subclasses
        self._current_simulation_timestamp = self._extract_simulation_timestamp(context, data)

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

    def log_transaction(
        self,
        asset: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        slippage: float = 0.0,
    ) -> None:
        """Log broker transaction events (Layer 4).

        This method logs the transaction_executed, commission_charged,
        and slippage_applied events that occur when an order is filled.
        In real rustybt execution, call this after extracting transaction
        data from context.blotter.get_transactions().

        Parameters
        ----------
        asset : str
            Asset symbol.
        quantity : float
            Fill quantity (positive for buy, negative for sell).
        price : float
            Fill price.
        commission : float, optional
            Commission charged, by default 0.0.
        slippage : float, optional
            Slippage applied, by default 0.0.
        """
        # Log transaction_executed (Layer 4)
        self._log_event(
            layer="broker",
            event="transaction_executed",
            data={
                "data_fill_price": price,
                "data_fill_quantity": quantity,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log commission_charged (Layer 4)
        self._log_event(
            layer="broker",
            event="commission_charged",
            data={
                "data_commission": commission,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log slippage_applied (Layer 4)
        self._log_event(
            layer="broker",
            event="slippage_applied",
            data={
                "data_slippage": slippage,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

    def log_portfolio_update(
        self,
        portfolio_value: float,
        cash: float,
        daily_return: float | None = None,
        drawdown: float | None = None,
    ) -> None:
        """Log portfolio state events (Layer 4 & 5).

        This method logs the cash_updated (Layer 4), portfolio_value_updated,
        daily_return_calculated, and drawdown_updated (Layer 5) events.
        In real rustybt execution, call this using values from context.portfolio.

        Parameters
        ----------
        portfolio_value : float
            Current total portfolio value.
        cash : float
            Current cash balance.
        daily_return : float | None, optional
            Daily return if available, by default None.
        drawdown : float | None, optional
            Current drawdown if available, by default None.
        """
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
                "data_portfolio_value": portfolio_value,
            },
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log daily_return_calculated if available (Layer 5)
        if daily_return is not None:
            self._log_event(
                layer="portfolio",
                event="daily_return_calculated",
                data={
                    "data_daily_return": daily_return,
                },
                simulation_timestamp=self._current_simulation_timestamp,
            )

        # Log drawdown_updated if available (Layer 5)
        if drawdown is not None:
            self._log_event(
                layer="portfolio",
                event="drawdown_updated",
                data={
                    "data_drawdown": drawdown,
                },
                simulation_timestamp=self._current_simulation_timestamp,
            )

    def log_final_metrics(
        self, sharpe_ratio: float = 0.0, **extra_metrics: Any  # noqa: ANN401
    ) -> None:
        """Log final portfolio metrics at backtest completion (Layer 5).

        This method logs the final_metrics event at the end of the backtest.
        In real rustybt execution, call this in the analyze() callback or
        after run_algorithm() completes.

        Parameters
        ----------
        sharpe_ratio : float, optional
            Sharpe ratio, by default 0.0.
        **extra_metrics : Any
            Additional metrics to include.
        """
        self._log_event(
            layer="portfolio",
            event="final_metrics",
            data={
                "data_sharpe_ratio": sharpe_ratio,
                **extra_metrics,
            },
            simulation_timestamp=self._current_simulation_timestamp,
        )

    def finalize(self) -> None:
        """Finalize strategy - placeholder for backwards compatibility.

        In the new rustybt-integrated implementation, final metrics should
        be logged via log_final_metrics() in the analyze() callback or after
        run_algorithm() completes. This method is kept for API compatibility.
        """
        pass

    def notify_transaction(self, context: Any, transaction: Any) -> None:  # noqa: ANN401
        """Called when an order is filled and a transaction occurs.

        This callback is invoked by the rustybt simulation loop for each
        transaction (order fill) that occurs during the backtest. It automatically
        logs Layer 4 broker events (transaction_executed, commission_charged,
        slippage_applied) to match Backtrader's notify_order() behavior.

        Parameters
        ----------
        context : Any
            The strategy context object (TradingAlgorithm instance).
        transaction : Transaction
            The transaction object containing fill details:
            - asset: The asset that was traded
            - amount: Number of shares/contracts (positive=buy, negative=sell)
            - price: Fill price
            - dt: Transaction datetime
            - order_id: ID of the order that generated this transaction

        Notes:
        -----
        - Called BEFORE handle_data() on each bar where fills occur
        - Multiple transactions may occur on the same bar
        - Logs transaction_executed, commission_charged, slippage_applied events
        - Similar to Backtrader's notify_order() callback
        """
        # Extract transaction details
        asset_str = str(transaction.asset) if transaction.asset else None
        amount = float(transaction.amount)
        price = float(transaction.price)

        # Get commission from the order object in the blotter
        # The commission is calculated by the blotter and stored on the order
        # For complete fills (our case), order.commission equals the transaction commission
        commission = 0.0
        try:
            if hasattr(context, "blotter") and context.blotter is not None:
                order = context.blotter.orders.get(transaction.order_id)
                if order is not None:
                    # For PerTrade commission, the full amount is charged on first fill
                    # Use the order's cumulative commission (which equals transaction commission
                    # for single-fill orders like our market orders)
                    commission = float(getattr(order, "commission", 0.0) or 0.0)
        except Exception:  # noqa: BLE001
            # Fall back to transaction attribute if blotter lookup fails
            commission = float(getattr(transaction, "commission", 0.0) or 0.0)

        # Update simulation timestamp from transaction datetime
        if transaction.dt is not None:
            self._current_simulation_timestamp = transaction.dt.isoformat()

        # Log the transaction using the existing log_transaction method
        self.log_transaction(
            asset=asset_str or "UNKNOWN",
            quantity=amount,
            price=price,
            commission=commission,
            slippage=0.0,  # Slippage is built into the fill price
        )

    # =========================================================================
    # Test Helper Interface
    # =========================================================================
    # These methods provide a simplified interface for unit testing strategies
    # without requiring full rustybt execution infrastructure.

    def _test_feed_price(self, price: float, asset: str = "TEST") -> None:
        """Feed a single price for indicator calculation (test helper).

        This method should be overridden by subclasses to update their
        indicator state with the new price. It is used for unit testing
        indicator calculations without full rustybt execution.

        Parameters
        ----------
        price : float
            The price value to feed.
        asset : str, optional
            Asset symbol, by default "TEST".
        """
        pass  # Override in subclasses

    def compute_signal(self, price: float, asset: str = "TEST") -> str:
        """Compute signal from price (test helper for backward compatibility).

        This method provides a simplified interface for unit testing.
        It feeds the price to indicators and computes the signal.
        For real execution, use handle_data() with proper context/data.

        Parameters
        ----------
        price : float
            The current price.
        asset : str, optional
            Asset symbol, by default "TEST".

        Returns:
        -------
        str
            Signal: "BUY", "SELL", or "HOLD".
        """
        self._test_feed_price(price, asset)
        if hasattr(self, "_compute_signal"):
            return self._compute_signal()
        return "HOLD"

    @property
    def position(self) -> int:
        """Get current position state (test helper for backward compatibility).

        Returns:
        -------
        int
            Position state: -1 = short, 0 = flat, 1 = long.
        """
        if hasattr(self, "_position_state"):
            return self._position_state
        return 0

    def _test_execute_signal(self, signal: str) -> None:
        """Execute signal by updating position state (test helper).

        This method simulates signal execution for unit testing
        without requiring real rustybt order APIs.

        Parameters
        ----------
        signal : str
            Signal to execute: "BUY", "SELL", "HOLD", etc.
        """
        if not hasattr(self, "_position_state"):
            self._position_state = 0

        # Handle string-based position states (momentum strategy uses "FLAT", "LONG", "SHORT")
        if isinstance(self._position_state, str):
            if signal == "BUY" and self._position_state == "FLAT":
                self._position_state = "LONG"
            elif signal == "SELL" and self._position_state == "FLAT":
                self._position_state = "SHORT"
            elif (
                (signal == "SELL" and self._position_state == "LONG")
                or (signal == "BUY" and self._position_state == "SHORT")
                or signal in ("EXIT_LONG", "EXIT_SHORT", "EXIT_STOP", "EXIT_RSI")
            ):
                self._position_state = "FLAT"
        else:
            # Handle integer-based position states (other strategies use -1, 0, 1)
            if signal == "BUY" and self._position_state == 0:
                self._position_state = 1
            elif signal == "SELL" and self._position_state in (0, 1):
                if self._position_state == 0:
                    self._position_state = -1
                else:
                    self._position_state = 0
            elif signal in ("EXIT_LONG", "EXIT_SHORT", "EXIT_STOP", "EXIT_RSI"):
                self._position_state = 0


class ValidatedTradingAlgorithm(ValidatedStrategyMixin):
    """Validated strategy that can be used with TradingAlgorithm.

    This class combines validation logging with rustybt's TradingAlgorithm
    for real backtest execution. Use this when running actual backtests
    that need structured log output.

    Note: This class is designed to be used as a mixin or base for
    TradingAlgorithm subclasses. For the function-based pattern,
    use RustyBTValidatedStrategy instead.

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file.

    Attributes:
    ----------
    _current_simulation_timestamp : str | None
        The current simulation timestamp, updated on each handle_data call.

    Example:
    -------
    >>> from rustybt.validation import ValidatedTradingAlgorithm
    >>> from rustybt.algorithm import TradingAlgorithm
    >>>
    >>> class MyValidatedAlgo(ValidatedTradingAlgorithm, TradingAlgorithm):
    ...     def __init__(self, log_path, **kwargs):
    ...         ValidatedTradingAlgorithm.__init__(self, log_path)
    ...         TradingAlgorithm.__init__(self, **kwargs)
    ...
    ...     def initialize(self):
    ...         self._log_event("data", "initialize", {})
    ...         # ... strategy setup
    ...
    ...     def handle_data(self, data):
    ...         self._current_simulation_timestamp = self.get_datetime().isoformat()
    ...         self._log_event("data", "bar_received", {},
    ...                         simulation_timestamp=self._current_simulation_timestamp)
    ...         # ... trading logic
    """

    _current_simulation_timestamp: str | None

    def __init__(self, log_path: Path) -> None:
        """Initialize validated trading algorithm.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        """
        self._init_logging(log_path)
        self._current_simulation_timestamp = None

    def initialize(self, context: Any) -> None:  # noqa: ANN401, ARG002
        """Initialize strategy and log the event.

        Parameters
        ----------
        context : Any
            The strategy context object.
        """
        self._log_event(
            layer="data",
            event="initialize",
            data={"context": "strategy_init"},
        )

    def handle_data(self, context: Any, data: Any) -> None:  # noqa: ANN401, ARG002
        """Process bar data and log the event.

        Parameters
        ----------
        context : Any
            The strategy context object.
        data : Any
            The bar data object.
        """
        # Extract simulation timestamp from context
        self._current_simulation_timestamp = None
        if hasattr(context, "get_datetime"):
            try:
                dt = context.get_datetime()
                self._current_simulation_timestamp = dt.isoformat() if dt else None
            except (AttributeError, TypeError):
                pass  # Context doesn't support get_datetime

        self._log_event(
            layer="data",
            event="bar_received",
            data={},
            simulation_timestamp=self._current_simulation_timestamp,
        )
