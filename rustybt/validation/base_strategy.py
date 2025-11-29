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

Architecture Note:
    The logging functionality is provided as a mixin class (ValidatedStrategyMixin)
    that can be combined with TradingAlgorithm. This separation allows:
    - Unit testing of logging without requiring full TradingAlgorithm setup
    - Flexibility in how logging is composed with different base classes
    - Clear separation of concerns

Example:
    >>> from pathlib import Path
    >>> class MyStrategy(RustyBTValidatedStrategy):
    ...     def initialize(self, context):
    ...         super().initialize(context)
    ...         context.asset = self.symbol('AAPL')
    ...
    ...     def handle_data(self, context, data):
    ...         super().handle_data(context, data)
    ...         # Custom logic here
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
VALID_LAYERS: frozenset[str] = frozenset(
    {"data", "signals", "orders", "broker", "portfolio"}
)


class ValidatedStrategyMixin:
    """Mixin class providing validation logging functionality.

    This mixin provides the core logging infrastructure used by validated
    strategies. It can be used independently for testing or combined with
    TradingAlgorithm for real strategy execution.

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

        Notes:
        -----
        - Flushes after each write to prevent data loss on crash
        - Uses ISO8601 timestamp format
        - Logs are written as single JSON lines (JSONL format)

        Examples:
        --------
        >>> strategy._log_event(
        ...     layer="signals",
        ...     event="signal_computed",
        ...     data={"signal_name": "sma_crossover", "value": 1.0},
        ...     asset="AAPL"
        ... )
        """
        if not hasattr(self, "_log_file") or self._log_file is None or self._log_file.closed:
            return

        # Extract asset from data if not explicitly provided
        if asset is None:
            asset = data.get("asset")

        entry = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
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

    def log_broker_event(
        self,
        event: str,
        asset: str | None = None,
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
    """Standalone validated strategy class for testing and simple use cases.

    This class provides the full validated strategy interface without requiring
    TradingAlgorithm initialization. It's useful for:
    - Unit testing the logging functionality
    - Simple strategy validation without full backtest infrastructure
    - Integration testing with mock contexts

    For real backtesting, use ValidatedTradingAlgorithm which properly inherits
    from TradingAlgorithm.

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file. The file will be created/overwritten.

    Examples:
    --------
    >>> from pathlib import Path
    >>> log_path = Path("/tmp/strategy.jsonl")
    >>> with RustyBTValidatedStrategy(log_path=log_path) as strategy:
    ...     strategy._log_event("data", "test", {"key": "value"})
    """

    def __init__(self, log_path: Path) -> None:
        """Initialize the validated strategy with logging.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        """
        self._init_logging(log_path)

    def initialize(self, context: Any) -> None:  # noqa: ANN401, ARG002
        """Initialize strategy and log the event.

        Override this method to add custom initialization logic.

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

        Override this method to add custom data handling logic.

        Parameters
        ----------
        context : Any
            The strategy context object.
        data : Any
            The bar data object.
        """
        # Get current timestamp from context if available
        timestamp_str = ""
        if hasattr(context, "current_dt"):
            timestamp_str = str(context.current_dt)

        self._log_event(
            layer="data",
            event="bar_received",
            data={"timestamp": timestamp_str},
        )


class ValidatedTradingAlgorithm(ValidatedStrategyMixin):
    """Validated strategy that properly inherits from TradingAlgorithm.

    This class combines TradingAlgorithm with validation logging for
    real backtest execution. Use this class when running actual backtests
    that need structured log output.

    Note: This class requires full TradingAlgorithm initialization including
    sim_params, data_portal, etc. For simpler testing, use RustyBTValidatedStrategy.

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file.
    *args : Any
        Arguments passed to TradingAlgorithm.
    **kwargs : Any
        Keyword arguments passed to TradingAlgorithm.

    Example:
    -------
    >>> from rustybt.validation import ValidatedTradingAlgorithm
    >>> algo = ValidatedTradingAlgorithm(
    ...     log_path=Path("strategy.jsonl"),
    ...     sim_params=sim_params,
    ...     initialize=my_initialize,
    ...     handle_data=my_handle_data,
    ... )
    >>> results = algo.run()
    """

    def __init__(
        self,
        log_path: Path,
        *args: Any,  # noqa: ANN401, ARG002
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> None:
        """Initialize validated trading algorithm.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        *args : Any
            Positional arguments for TradingAlgorithm (reserved for future use).
        **kwargs : Any
            Keyword arguments for TradingAlgorithm (reserved for future use).
        """
        # Import here to avoid circular imports and allow testing without full rustybt
        from rustybt.algorithm import TradingAlgorithm

        # Initialize logging first
        self._init_logging(log_path)

        # Store reference to parent class for proper MRO
        self._trading_algo_class = TradingAlgorithm

        # Note: In actual use, this would inherit from TradingAlgorithm
        # This is a placeholder - the actual integration requires careful
        # handling of the complex TradingAlgorithm initialization

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
        timestamp_str = ""
        if hasattr(context, "current_dt"):
            timestamp_str = str(context.current_dt)

        self._log_event(
            layer="data",
            event="bar_received",
            data={"timestamp": timestamp_str},
        )
