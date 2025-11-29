"""Momentum strategy with RSI and trailing stops for rustybt validation.

This module implements a Momentum strategy that:
1. Extends RustyBTValidatedStrategy
2. Implements RSI (Relative Strength Index) indicator calculation
3. Implements trailing stop logic for position management
4. Generates BUY signal when RSI < 30 (oversold)
5. Generates SELL signal when RSI > 70 (overbought)
6. Exits via trailing stop at 5%
7. Logs events to JSONL for comparison with Backtrader

The log format follows the validation framework schema:
    {
        "timestamp": ISO8601 string,
        "layer": "data|signals|orders|broker|portfolio",
        "event": descriptive event name,
        "asset": asset symbol or null,
        "data": dictionary of event-specific data
    }
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy
from rustybt.validation.decorators import log_order, log_signal


class MomentumStrategy(RustyBTValidatedStrategy):
    """Momentum validated strategy for rustybt with RSI and trailing stops.

    This strategy implements a momentum-based approach:
    - BUY when RSI < oversold threshold (expecting upward momentum)
    - SELL when RSI > overbought threshold (expecting downward momentum)
    - Exit via trailing stop when price moves against position

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file.
    rsi_period : int, optional
        Number of periods for RSI calculation, by default 14.
    oversold : float, optional
        RSI threshold for oversold condition (BUY signal), by default 30.
    overbought : float, optional
        RSI threshold for overbought condition (SELL signal), by default 70.
    trailing_stop_pct : float, optional
        Trailing stop percentage (0.05 = 5%), by default 0.05.
    target_percent : float, optional
        Target allocation percentage (0-1), by default 1.0 (100%).

    Attributes
    ----------
    _prices : deque
        Rolling window of prices for RSI calculation.
    _current_rsi : float | None
        Current RSI value.
    _position : str
        Current position type: "FLAT", "LONG", or "SHORT".
    _stop_price : float | None
        Current trailing stop price.
    _entry_price : float | None
        Entry price for current position.
    """

    def __init__(
        self,
        log_path: Path,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        trailing_stop_pct: float = 0.05,
        target_percent: float = 1.0,
    ) -> None:
        """Initialize the Momentum strategy.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        rsi_period : int, optional
            Number of periods for RSI, by default 14.
        oversold : float, optional
            RSI oversold threshold, by default 30.
        overbought : float, optional
            RSI overbought threshold, by default 70.
        trailing_stop_pct : float, optional
            Trailing stop percentage, by default 0.05.
        target_percent : float, optional
            Target allocation percentage (0-1), by default 1.0.
        """
        super().__init__(log_path)
        self._rsi_period = rsi_period
        self._oversold = oversold
        self._overbought = overbought
        self._trailing_stop_pct = trailing_stop_pct
        self._target_percent = target_percent

        # Price history for RSI calculation (need period + 1 prices)
        self._prices: deque[float] = deque(maxlen=rsi_period + 1)

        # RSI value
        self._current_rsi: float | None = None

        # Position tracking
        self._position: str = "FLAT"  # "FLAT", "LONG", "SHORT"
        self._stop_price: float | None = None
        self._entry_price: float | None = None

        # Asset reference
        self._asset: str | None = None

    def initialize(self, context: Any) -> None:  # noqa: ANN401
        """Initialize strategy and log the event.

        Parameters
        ----------
        context : Any
            The strategy context object.
        """
        super().initialize(context)
        self._log_event(
            layer="data",
            event="momentum_init",
            data={
                "rsi_period": self._rsi_period,
                "oversold": self._oversold,
                "overbought": self._overbought,
                "trailing_stop_pct": self._trailing_stop_pct,
                "target_percent": self._target_percent,
            },
        )

    def _calculate_rsi(self) -> float | None:
        """Calculate Relative Strength Index.

        Returns
        -------
        float | None
            RSI value (0-100), or None if insufficient data.
        """
        if len(self._prices) < self._rsi_period + 1:
            return None

        prices_list = list(self._prices)

        # Calculate price changes
        deltas = [
            prices_list[i] - prices_list[i - 1] for i in range(1, len(prices_list))
        ]

        # Get last 'period' deltas
        recent_deltas = deltas[-self._rsi_period :]

        # Separate gains and losses
        gains = [d if d > 0 else 0 for d in recent_deltas]
        losses = [-d if d < 0 else 0 for d in recent_deltas]

        # Calculate average gain and loss
        avg_gain = sum(gains) / self._rsi_period
        avg_loss = sum(losses) / self._rsi_period

        # Handle division by zero
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def update_trailing_stop(self, current_price: float) -> float | None:
        """Update trailing stop price (ratchets in favorable direction only).

        Parameters
        ----------
        current_price : float
            Current price.

        Returns
        -------
        float | None
            New stop price, or None if no position.
        """
        if self._position == "FLAT":
            return None

        previous_stop = self._stop_price

        if self._position == "LONG":
            new_stop = current_price * (1 - self._trailing_stop_pct)
            if self._stop_price is None:
                self._stop_price = new_stop
            else:
                # Only move stop up (ratchet)
                self._stop_price = max(self._stop_price, new_stop)

        elif self._position == "SHORT":
            new_stop = current_price * (1 + self._trailing_stop_pct)
            if self._stop_price is None:
                self._stop_price = new_stop
            else:
                # Only move stop down (ratchet)
                self._stop_price = min(self._stop_price, new_stop)

        # Log stop update if changed
        if previous_stop != self._stop_price:
            self._log_event(
                layer="orders",
                event="stop_updated",
                data={
                    "price": current_price,
                    "previous_stop": previous_stop,
                    "new_stop": self._stop_price,
                    "position_type": self._position,
                },
                asset=self._asset,
            )

        return self._stop_price

    def check_stop_triggered(self, current_price: float) -> bool:
        """Check if trailing stop has been triggered.

        Parameters
        ----------
        current_price : float
            Current price.

        Returns
        -------
        bool
            True if stop triggered, False otherwise.
        """
        if self._stop_price is None or self._position == "FLAT":
            return False

        if self._position == "LONG":
            return current_price <= self._stop_price

        if self._position == "SHORT":
            return current_price >= self._stop_price

        return False

    @log_signal()
    def compute_signal(self, price: float, asset: str | None = None) -> str:
        """Compute trading signal based on RSI and trailing stop.

        Parameters
        ----------
        price : float
            Current price.
        asset : str | None, optional
            Asset symbol, by default None.

        Returns
        -------
        str
            Signal: "BUY", "SELL", "EXIT_STOP", "EXIT_RSI", or "HOLD".
        """
        self._asset = asset

        # Add price to history
        self._prices.append(price)

        # Calculate RSI
        self._current_rsi = self._calculate_rsi()

        # Log RSI computation
        self._log_event(
            layer="signals",
            event="rsi_computed",
            data={
                "price": price,
                "rsi": self._current_rsi,
                "stop_price": self._stop_price,
                "position": self._position,
            },
            asset=asset,
        )

        # Check trailing stop first (if in position)
        if self._position != "FLAT":
            # Update trailing stop
            self.update_trailing_stop(price)

            # Check if stop triggered
            if self.check_stop_triggered(price):
                return "EXIT_STOP"

            # Check RSI exit conditions
            if self._current_rsi is not None:
                if self._position == "LONG" and self._current_rsi > self._overbought:
                    return "EXIT_RSI"
                if self._position == "SHORT" and self._current_rsi < self._oversold:
                    return "EXIT_RSI"

        # Check entry conditions (if flat)
        if self._position == "FLAT" and self._current_rsi is not None:
            # Oversold -> BUY (expecting upward momentum)
            if self._current_rsi < self._oversold:
                return "BUY"

            # Overbought -> SELL (expecting downward momentum / short)
            if self._current_rsi > self._overbought:
                return "SELL"

        return "HOLD"

    @log_order()
    def handle_data(self, context: Any, data: Any) -> Any:  # noqa: ANN401
        """Process bar data and execute orders based on signals.

        Parameters
        ----------
        context : Any
            The strategy context object.
        data : Any
            The bar data object containing price information.

        Returns
        -------
        Any
            Order object if created, None otherwise.
        """
        super().handle_data(context, data)

        # Extract price from data
        if hasattr(data, "current"):
            price = float(data.current())
        elif hasattr(data, "close"):
            price = float(data.close)
        elif isinstance(data, dict):
            price = float(data.get("close", data.get("price", 0)))
        elif isinstance(data, (int, float)):
            price = float(data)
        else:
            price = 0.0

        # Extract asset from context or data
        asset = None
        if hasattr(context, "asset"):
            asset = str(context.asset)
        elif hasattr(data, "symbol"):
            asset = str(data.symbol)

        # Compute signal
        signal = self.compute_signal(price, asset)

        # Log the signal event
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "price": price,
                "rsi": self._current_rsi,
                "signal": signal,
                "stop_price": self._stop_price,
                "position": self._position,
            },
            asset=asset,
        )

        # Execute based on signal
        order = None

        if signal == "BUY" and self._position == "FLAT":
            # Enter long position
            order = self._create_order(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self._target_percent,
                side="buy",
            )
            self._position = "LONG"
            self._entry_price = price
            self._stop_price = price * (1 - self._trailing_stop_pct)
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self._target_percent,
                target_percent=self._target_percent,
                rsi=self._current_rsi,
                stop_price=self._stop_price,
            )

        elif signal == "SELL" and self._position == "FLAT":
            # Enter short position
            order = self._create_order(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self._target_percent,
                side="sell",
            )
            self._position = "SHORT"
            self._entry_price = price
            self._stop_price = price * (1 + self._trailing_stop_pct)
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self._target_percent,
                target_percent=-self._target_percent,
                rsi=self._current_rsi,
                stop_price=self._stop_price,
            )

        elif signal in ("EXIT_STOP", "EXIT_RSI"):
            exit_reason = "trailing_stop" if signal == "EXIT_STOP" else "rsi_exit"

            if self._position == "LONG":
                order = self._create_order(
                    order_type="market",
                    asset=asset or "UNKNOWN",
                    quantity=-self._target_percent,
                    side="sell",
                )
                self.log_order_created(
                    order_type="market",
                    asset=asset or "UNKNOWN",
                    quantity=-self._target_percent,
                    target_percent=0.0,
                    exit_reason=exit_reason,
                    rsi=self._current_rsi,
                )

            elif self._position == "SHORT":
                order = self._create_order(
                    order_type="market",
                    asset=asset or "UNKNOWN",
                    quantity=self._target_percent,
                    side="buy",
                )
                self.log_order_created(
                    order_type="market",
                    asset=asset or "UNKNOWN",
                    quantity=self._target_percent,
                    target_percent=0.0,
                    exit_reason=exit_reason,
                    rsi=self._current_rsi,
                )

            # Reset position state
            self._position = "FLAT"
            self._stop_price = None
            self._entry_price = None

        return order

    def _create_order(
        self,
        order_type: str,
        asset: str,
        quantity: float,
        side: str,
    ) -> dict[str, Any]:
        """Create an order representation.

        Parameters
        ----------
        order_type : str
            Type of order ("market", "limit", etc.).
        asset : str
            Asset symbol.
        quantity : float
            Order quantity.
        side : str
            Order side ("buy" or "sell").

        Returns
        -------
        dict
            Order details.
        """
        return {
            "order_type": order_type,
            "asset": asset,
            "quantity": quantity,
            "side": side,
        }

    @property
    def rsi(self) -> float | None:
        """Get current RSI value."""
        return self._current_rsi

    @property
    def position(self) -> str:
        """Get current position type ("FLAT", "LONG", "SHORT")."""
        return self._position

    @property
    def stop_price(self) -> float | None:
        """Get current trailing stop price."""
        return self._stop_price

    @stop_price.setter
    def stop_price(self, value: float | None) -> None:
        """Set trailing stop price (for testing)."""
        self._stop_price = value

    @property
    def position_type(self) -> str:
        """Get current position type (alias for position)."""
        return self._position

    @position_type.setter
    def position_type(self, value: str) -> None:
        """Set position type (for testing)."""
        self._position = value
