"""Decorators for logging custom strategy logic.

This module provides decorators that automatically log method execution
to the validation framework's JSONL log files. These decorators work
with both RustyBTValidatedStrategy and BacktraderValidatedStrategy.

The decorators are optional conveniences - strategies can also call
`_log_event()` directly for full control over logging.

Available Decorators
--------------------
- @log_signal : Log signal computation results to "signals" layer
- @log_order : Log order creation to "orders" layer
- @log_portfolio : Log portfolio state to "portfolio" layer

Example:
    >>> from rustybt.validation.decorators import log_signal, log_order
    >>>
    >>> class MyStrategy(RustyBTValidatedStrategy):
    ...     @log_signal()
    ...     def compute_rsi(self, period: int = 14) -> float:
    ...         return calculate_rsi(self.data, period)
    ...
    ...     @log_order()
    ...     def place_buy_order(self, asset: str, quantity: int):
    ...         return self.order(asset, quantity)

Note:
    - All decorators use `functools.wraps` to preserve method metadata
    - Exceptions are logged before being re-raised
    - Decorators require the wrapped class to have a `_log_event()` method
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    pass

# Type variable for callable preservation
F = TypeVar("F", bound=Callable[..., Any])


def log_signal(layer: str = "signals") -> Callable[[F], F]:
    """Decorator to log signal computation results.

    Logs the method name, return value, and arguments to the specified
    validation layer (default: "signals").

    Parameters
    ----------
    layer : str, optional
        The validation layer to log to, by default "signals".

    Returns
    -------
    Callable
        Decorated method that logs signal computation.

    Examples
    --------
    >>> class MyStrategy(RustyBTValidatedStrategy):
    ...     @log_signal()
    ...     def compute_rsi(self, period: int = 14) -> float:
    ...         return calculate_rsi(self.data, period)
    ...
    ...     @log_signal(layer="custom_signals")
    ...     def compute_custom_indicator(self) -> float:
    ...         return 42.0

    Notes
    -----
    - The decorated method must be a bound method of a class with `_log_event()`
    - Signal value is captured from the method's return value
    - On exception, logs "signal_failed" event before re-raising
    """

    def decorator(method: F) -> F:
        @wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            try:
                result = method(self, *args, **kwargs)
                self._log_event(
                    layer,
                    "signal_computed",
                    {
                        "signal_name": method.__name__,
                        "signal_value": result,
                        "args": _serialize_args(args),
                        "kwargs": _serialize_kwargs(kwargs),
                    },
                )
                return result
            except Exception as e:
                self._log_event(
                    layer,
                    "signal_failed",
                    {
                        "signal_name": method.__name__,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def log_order(layer: str = "orders") -> Callable[[F], F]:
    """Decorator to log order creation.

    Logs the order type, asset, quantity, and limit price to the specified
    validation layer (default: "orders"). Handles None returns gracefully.

    Parameters
    ----------
    layer : str, optional
        The validation layer to log to, by default "orders".

    Returns
    -------
    Callable
        Decorated method that logs order creation.

    Examples
    --------
    >>> class MyStrategy(RustyBTValidatedStrategy):
    ...     @log_order()
    ...     def place_buy_order(self, asset: str, quantity: int):
    ...         return self.order(asset, quantity)
    ...
    ...     @log_order()
    ...     def place_market_order(self, asset: str, quantity: int):
    ...         if self.should_trade():
    ...             return self.order(asset, quantity)
    ...         return None  # No order created - not logged

    Notes
    -----
    - If the method returns None, no order event is logged
    - Order attributes are extracted via getattr with fallbacks
    - On exception, logs "order_failed" event before re-raising
    """

    def decorator(method: F) -> F:
        @wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            try:
                order = method(self, *args, **kwargs)
                if order is not None:
                    # Extract order details with safe fallbacks
                    order_data = {
                        "order_type": type(order).__name__,
                        "method_name": method.__name__,
                    }

                    # Try to extract common order attributes
                    if hasattr(order, "data") and hasattr(order.data, "_name"):
                        order_data["asset"] = str(order.data._name)
                    elif hasattr(order, "asset"):
                        order_data["asset"] = str(order.asset)

                    if hasattr(order, "size"):
                        order_data["quantity"] = float(order.size)
                    elif hasattr(order, "quantity"):
                        order_data["quantity"] = float(order.quantity)

                    if hasattr(order, "price") and order.price is not None:
                        order_data["limit_price"] = float(order.price)
                    elif hasattr(order, "limit_price") and order.limit_price is not None:
                        order_data["limit_price"] = float(order.limit_price)
                    else:
                        order_data["limit_price"] = None

                    self._log_event(layer, "order_created", order_data)
                return order
            except Exception as e:
                self._log_event(
                    layer,
                    "order_failed",
                    {
                        "method_name": method.__name__,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def log_portfolio(layer: str = "portfolio") -> Callable[[F], F]:
    """Decorator to log portfolio state after method execution.

    Logs the portfolio value, cash, and positions to the specified
    validation layer (default: "portfolio"). The state is captured
    AFTER the method executes.

    Parameters
    ----------
    layer : str, optional
        The validation layer to log to, by default "portfolio".

    Returns
    -------
    Callable
        Decorated method that logs portfolio state.

    Examples
    --------
    >>> class MyStrategy(RustyBTValidatedStrategy):
    ...     @log_portfolio()
    ...     def rebalance(self) -> None:
    ...         # Rebalancing logic here
    ...         pass
    ...
    ...     @log_portfolio()
    ...     def handle_data(self, context, data) -> None:
    ...         super().handle_data(context, data)
    ...         # Custom logic

    Notes
    -----
    - Portfolio state is logged AFTER method execution
    - Requires `self` to have a `portfolio` attribute with:
      - `portfolio_value` (or `value`)
      - `cash`
      - `positions` (dict-like)
    - On exception, logs "portfolio_update_failed" event before re-raising
    """

    def decorator(method: F) -> F:
        @wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            try:
                result = method(self, *args, **kwargs)

                # Try to access portfolio state with various attribute names
                portfolio_data: dict[str, Any] = {"method_name": method.__name__}

                if hasattr(self, "portfolio"):
                    portfolio = self.portfolio

                    # Portfolio value
                    if hasattr(portfolio, "portfolio_value"):
                        portfolio_data["portfolio_value"] = float(portfolio.portfolio_value)
                    elif hasattr(portfolio, "value"):
                        portfolio_data["portfolio_value"] = float(portfolio.value)

                    # Cash
                    if hasattr(portfolio, "cash"):
                        portfolio_data["cash"] = float(portfolio.cash)

                    # Positions
                    if hasattr(portfolio, "positions"):
                        positions = portfolio.positions
                        if hasattr(positions, "items"):
                            portfolio_data["positions"] = {
                                str(k): _extract_position_value(v)
                                for k, v in positions.items()
                            }
                        else:
                            portfolio_data["positions"] = str(positions)

                elif hasattr(self, "broker"):
                    # Backtrader style - access via broker
                    broker = self.broker

                    if hasattr(broker, "getvalue"):
                        portfolio_data["portfolio_value"] = float(broker.getvalue())
                    if hasattr(broker, "getcash"):
                        portfolio_data["cash"] = float(broker.getcash())
                    if hasattr(broker, "positions"):
                        positions = broker.positions
                        if hasattr(positions, "items"):
                            portfolio_data["positions"] = {
                                str(k): float(v.size) if hasattr(v, "size") else float(v)
                                for k, v in positions.items()
                            }

                self._log_event(layer, "portfolio_updated", portfolio_data)
                return result
            except Exception as e:
                self._log_event(
                    layer,
                    "portfolio_update_failed",
                    {
                        "method_name": method.__name__,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def log_broker(layer: str = "broker") -> Callable[[F], F]:
    """Decorator to log broker layer events after method execution.

    Logs broker events such as order fills, rejections, cancellations,
    and other broker-related actions to the specified validation layer
    (default: "broker"). The state is captured AFTER the method executes.

    Parameters
    ----------
    layer : str, optional
        The validation layer to log to, by default "broker".

    Returns:
    -------
    Callable
        Decorated method that logs broker events.

    Examples:
    --------
    >>> class MyStrategy(RustyBTValidatedStrategy):
    ...     @log_broker()
    ...     def on_fill(self, order_id: str, fill_price: float) -> None:
    ...         # Handle fill event
    ...         pass
    ...
    ...     @log_broker()
    ...     def process_execution(self, execution: Execution) -> dict:
    ...         return {"status": "processed", "id": execution.id}

    Notes:
    -----
    - Broker events are logged AFTER method execution
    - The return value (if any) is included in the log data
    - On exception, logs "broker_event_failed" event before re-raising
    - Useful for logging fills, rejections, cancellations, and settlements
    """

    def decorator(method: F) -> F:
        @wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            try:
                result = method(self, *args, **kwargs)

                broker_data: dict[str, Any] = {
                    "method_name": method.__name__,
                    "args": _serialize_args(args),
                    "kwargs": _serialize_kwargs(kwargs),
                }

                # Include result if it's meaningful
                if result is not None:
                    if isinstance(result, dict):
                        broker_data.update(result)
                    else:
                        broker_data["result"] = _safe_str(result)

                self._log_event(layer, "broker_event", broker_data)
                return result
            except Exception as e:
                self._log_event(
                    layer,
                    "broker_event_failed",
                    {
                        "method_name": method.__name__,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def _serialize_args(args: tuple[Any, ...]) -> list[str]:
    """Serialize positional arguments for logging.

    Parameters
    ----------
    args : tuple
        Positional arguments to serialize.

    Returns
    -------
    list[str]
        List of string representations of arguments.
    """
    return [_safe_str(arg) for arg in args]


def _serialize_kwargs(kwargs: dict[str, Any]) -> dict[str, str]:
    """Serialize keyword arguments for logging.

    Parameters
    ----------
    kwargs : dict
        Keyword arguments to serialize.

    Returns
    -------
    dict[str, str]
        Dictionary with string values.
    """
    return {k: _safe_str(v) for k, v in kwargs.items()}


def _safe_str(value: Any) -> str:  # noqa: ANN401
    """Safely convert a value to string for logging.

    Parameters
    ----------
    value : Any
        Value to convert.

    Returns
    -------
    str
        String representation of the value.
    """
    try:
        # For numeric types, preserve precision
        if isinstance(value, (int, float)):
            return str(value)
        # For other types, use repr for better debugging
        return repr(value)
    except Exception:
        return "<unserializable>"


def _extract_position_value(position: Any) -> float:  # noqa: ANN401
    """Extract numeric value from a position object.

    Parameters
    ----------
    position : Any
        Position object (may have .amount, .size, or be numeric).

    Returns
    -------
    float
        Numeric position value.
    """
    if hasattr(position, "amount"):
        return float(position.amount)
    if hasattr(position, "size"):
        return float(position.size)
    try:
        return float(position)
    except (TypeError, ValueError):
        return 0.0
