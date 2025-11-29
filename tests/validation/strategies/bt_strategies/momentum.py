"""Momentum strategy with RSI and trailing stops for Backtrader validation.

This module implements a Momentum strategy that:
1. Extends BacktraderValidatedStrategy
2. Uses bt.indicators.RSI for indicator calculation
3. Implements trailing stop logic for position management
4. Generates BUY signal when RSI < 30 (oversold)
5. Generates SELL signal when RSI > 70 (overbought)
6. Exits via trailing stop at 5%
7. Logs events to JSONL for comparison with rustybt

The log format follows the validation framework schema (identical to rustybt):
    {
        "timestamp": ISO8601 string,
        "layer": "data|signals|orders|broker|portfolio",
        "event": descriptive event name,
        "asset": asset symbol or null,
        "data": dictionary of event-specific data
    }
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import backtrader as bt

from tests.validation.strategies.bt_strategies.base_validated import (
    BacktraderValidatedStrategy,
)

if TYPE_CHECKING:
    pass


class MomentumStrategy(BacktraderValidatedStrategy):
    """Momentum validated strategy for Backtrader with RSI and trailing stops.

    This strategy implements a momentum-based approach:
    - BUY when RSI < oversold threshold (expecting upward momentum)
    - SELL when RSI > overbought threshold (expecting downward momentum)
    - Exit via trailing stop when price moves against position

    The implementation uses Backtrader's built-in RSI indicator but produces
    logs identical in structure to the rustybt implementation.

    Parameters (via params tuple)
    -----------------------------
    log_path : Path | str
        Path to the JSONL log file (inherited from base).
    rsi_period : int
        Number of periods for RSI calculation, by default 14.
    oversold : float
        RSI threshold for oversold condition (BUY signal), by default 30.
    overbought : float
        RSI threshold for overbought condition (SELL signal), by default 70.
    trailing_stop_pct : float
        Trailing stop percentage (0.05 = 5%), by default 0.05.
    target_percent : float
        Target allocation percentage (0-1), by default 1.0 (100%).
    """

    # Backtrader params
    params = (
        ("log_path", None),
        ("rsi_period", 14),
        ("oversold", 30.0),
        ("overbought", 70.0),
        ("trailing_stop_pct", 0.05),
        ("target_percent", 1.0),
    )

    def __init__(self) -> None:
        """Initialize the Momentum strategy with RSI indicator."""
        super().__init__()

        # Create RSI indicator using Backtrader's built-in
        self.rsi_indicator = bt.indicators.RSI(
            self.data.close,
            period=self.p.rsi_period,
        )

        # Position tracking
        self._position_state: str = "FLAT"  # "FLAT", "LONG", "SHORT"
        self._stop_price: float | None = None
        self._entry_price: float | None = None

        # Log initialization with parameters
        self._log_event(
            layer="data",
            event="momentum_init",
            data={
                "rsi_period": self.p.rsi_period,
                "oversold": self.p.oversold,
                "overbought": self.p.overbought,
                "trailing_stop_pct": self.p.trailing_stop_pct,
                "target_percent": self.p.target_percent,
            },
        )

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
        if self._position_state == "FLAT":
            return None

        previous_stop = self._stop_price
        asset = self.data._name if hasattr(self.data, "_name") else None

        if self._position_state == "LONG":
            new_stop = current_price * (1 - self.p.trailing_stop_pct)
            if self._stop_price is None:
                self._stop_price = new_stop
            else:
                # Only move stop up (ratchet)
                self._stop_price = max(self._stop_price, new_stop)

        elif self._position_state == "SHORT":
            new_stop = current_price * (1 + self.p.trailing_stop_pct)
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
                    "position_type": self._position_state,
                },
                asset=asset,
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
        if self._stop_price is None or self._position_state == "FLAT":
            return False

        if self._position_state == "LONG":
            return current_price <= self._stop_price

        if self._position_state == "SHORT":
            return current_price >= self._stop_price

        return False

    def next(self) -> None:
        """Process the current bar, compute signal, and execute orders."""
        # Call base class to log bar_received event
        super().next()

        # Get current values
        current_price = self.data.close[0]
        rsi_value = self.rsi_indicator[0] if len(self.data) > self.p.rsi_period else None

        # Get asset name from data feed
        asset = self.data._name if hasattr(self.data, "_name") else None

        # Log RSI computation (matches rustybt structure)
        self._log_event(
            layer="signals",
            event="rsi_computed",
            data={
                "price": current_price,
                "rsi": rsi_value,
                "stop_price": self._stop_price,
                "position": self._position_state,
            },
            asset=asset,
        )

        # Determine signal
        signal = self._compute_signal(current_price, rsi_value)

        # Log the signal
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=asset,
            rsi=rsi_value,
            stop_price=self._stop_price,
        )

        # Log signal_generated event (matches rustybt structure)
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "price": current_price,
                "rsi": rsi_value,
                "signal": signal,
                "stop_price": self._stop_price,
                "position": self._position_state,
            },
            asset=asset,
        )

        # Execute based on signal
        self._execute_signal(signal, current_price, rsi_value, asset)

    def _compute_signal(
        self, current_price: float, rsi_value: float | None
    ) -> str:
        """Compute trading signal based on RSI and trailing stop.

        Parameters
        ----------
        current_price : float
            Current price.
        rsi_value : float | None
            Current RSI value.

        Returns
        -------
        str
            Signal: "BUY", "SELL", "EXIT_STOP", "EXIT_RSI", or "HOLD".
        """
        # Check trailing stop first (if in position)
        if self._position_state != "FLAT":
            # Update trailing stop
            self.update_trailing_stop(current_price)

            # Check if stop triggered
            if self.check_stop_triggered(current_price):
                return "EXIT_STOP"

            # Check RSI exit conditions
            if rsi_value is not None:
                if (
                    self._position_state == "LONG"
                    and rsi_value > self.p.overbought
                ):
                    return "EXIT_RSI"
                if (
                    self._position_state == "SHORT"
                    and rsi_value < self.p.oversold
                ):
                    return "EXIT_RSI"

        # Check entry conditions (if flat)
        if self._position_state == "FLAT" and rsi_value is not None:
            # Oversold -> BUY
            if rsi_value < self.p.oversold:
                return "BUY"

            # Overbought -> SELL
            if rsi_value > self.p.overbought:
                return "SELL"

        return "HOLD"

    def _execute_signal(
        self,
        signal: str,
        current_price: float,
        rsi_value: float | None,
        asset: str | None,
    ) -> None:
        """Execute order based on signal.

        Parameters
        ----------
        signal : str
            Trading signal.
        current_price : float
            Current price.
        rsi_value : float | None
            Current RSI value.
        asset : str | None
            Asset symbol.
        """
        if signal == "BUY" and self._position_state == "FLAT":
            # Enter long position
            self.order_target_percent(target=self.p.target_percent)
            self._position_state = "LONG"
            self._entry_price = current_price
            self._stop_price = current_price * (1 - self.p.trailing_stop_pct)
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self.p.target_percent,
                target_percent=self.p.target_percent,
                rsi=rsi_value,
                stop_price=self._stop_price,
            )

        elif signal == "SELL" and self._position_state == "FLAT":
            # Enter short position
            self.order_target_percent(target=-self.p.target_percent)
            self._position_state = "SHORT"
            self._entry_price = current_price
            self._stop_price = current_price * (1 + self.p.trailing_stop_pct)
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self.p.target_percent,
                target_percent=-self.p.target_percent,
                rsi=rsi_value,
                stop_price=self._stop_price,
            )

        elif signal in ("EXIT_STOP", "EXIT_RSI"):
            exit_reason = "trailing_stop" if signal == "EXIT_STOP" else "rsi_exit"

            # Exit position
            self.order_target_percent(target=0.0)

            if self._position_state == "LONG":
                self.log_order_created(
                    order_type="market",
                    asset=asset or "UNKNOWN",
                    quantity=-self.p.target_percent,
                    target_percent=0.0,
                    exit_reason=exit_reason,
                    rsi=rsi_value,
                )
            elif self._position_state == "SHORT":
                self.log_order_created(
                    order_type="market",
                    asset=asset or "UNKNOWN",
                    quantity=self.p.target_percent,
                    target_percent=0.0,
                    exit_reason=exit_reason,
                    rsi=rsi_value,
                )

            # Reset position state
            self._position_state = "FLAT"
            self._stop_price = None
            self._entry_price = None

    @property
    def position_state(self) -> str:
        """Get current position state ("FLAT", "LONG", "SHORT")."""
        return self._position_state

    @position_state.setter
    def position_state(self, value: str) -> None:
        """Set position state (for testing)."""
        self._position_state = value

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
        """Get current position type (alias for position_state)."""
        return self._position_state
