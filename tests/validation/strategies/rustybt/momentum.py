"""Momentum strategy with RSI and trailing stops for rustybt validation.

This module implements a Momentum strategy that:
1. Extends RustyBTValidatedStrategy for validation logging
2. Uses rustybt's data.history() for RSI calculation
3. Uses rustybt's order_target_percent() for trade execution
4. Implements trailing stop logic for position management
5. Generates BUY signal when RSI < 30 (oversold)
6. Generates SELL signal when RSI > 70 (overbought)
7. Exits via trailing stop at 5%
8. Logs events to JSONL for comparison with Backtrader

The log format follows the validation framework schema:
    {
        "timestamp": ISO8601 string,
        "layer": "data|signals|orders|broker|portfolio",
        "event": descriptive event name,
        "asset": asset symbol or null,
        "data": dictionary of event-specific data
    }

Epic X Implementation:
    This implementation uses rustybt's real APIs:
    - data.history() for RSI calculation
    - order_target_percent() for trade execution
    - context.portfolio for position/cash tracking

Note on Trailing Stops:
    rustybt does not natively support trailing stop orders.
    This implementation simulates trailing stops in strategy logic
    by tracking high-water mark and triggering exits manually.
    This is documented as a DESIGN difference from Backtrader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy


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

    Note
    ----
    Trailing stops are simulated in strategy logic since rustybt
    does not natively support trailing stop orders. This is a
    documented DESIGN difference from Backtrader.
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

        # RSI value
        self._current_rsi: float | None = None

        # Position tracking
        self._position_state: str = "FLAT"  # "FLAT", "LONG", "SHORT"
        self._stop_price: float | None = None
        self._entry_price: float | None = None

        # Asset reference (set during initialize)
        self._asset: Any = None
        self._asset_str: str | None = None

        # Bar counter for warmup
        self._bar_count: int = 0
        self._warmup_period: int = rsi_period + 1  # RSI needs period + 1 prices

        # Portfolio tracking for metrics
        self._portfolio_values: list[float] = []
        self._peak_value: float = 0.0

    def initialize(self, context: Any) -> None:  # noqa: ANN401
        """Initialize strategy and log the event.

        Parameters
        ----------
        context : Any
            The strategy context object (TradingAlgorithm instance).
        """
        super().initialize(context)

        # Get asset from context
        if hasattr(context, "asset"):
            self._asset = context.asset
            self._asset_str = str(context.asset) if context.asset else None
        elif hasattr(context, "assets") and context.assets:
            self._asset = context.assets[0]
            self._asset_str = str(context.assets[0])

        # Log initialization with parameters
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

    def _calculate_rsi_from_history(self, data: Any) -> float | None:  # noqa: ANN401
        """Calculate RSI using rustybt's data.history() API.

        Parameters
        ----------
        data : Any
            The BarData object from rustybt.

        Returns
        -------
        float | None
            RSI value (0-100), or None if insufficient data.
        """
        if self._asset is None:
            return None

        try:
            # Use rustybt's data.history() API - need period + 1 for deltas
            prices = data.history(self._asset, "close", self._rsi_period + 1, "1d")

            if prices is None or len(prices) < self._rsi_period + 1:
                return None

            # Calculate price changes
            deltas = prices.diff().dropna()

            if len(deltas) < self._rsi_period:
                return None

            # Get last 'period' deltas
            recent_deltas = deltas.iloc[-self._rsi_period :]

            # Separate gains and losses
            gains = recent_deltas.where(recent_deltas > 0, 0.0)
            losses = -recent_deltas.where(recent_deltas < 0, 0.0)

            # Calculate average gain and loss
            avg_gain = float(gains.mean())
            avg_loss = float(losses.mean())

            # Handle division by zero
            if avg_loss == 0:
                return 100.0 if avg_gain > 0 else 50.0

            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

            return rsi
        except Exception:
            return None

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

        if self._position_state == "LONG":
            new_stop = current_price * (1 - self._trailing_stop_pct)
            if self._stop_price is None:
                self._stop_price = new_stop
            else:
                # Only move stop up (ratchet)
                self._stop_price = max(self._stop_price, new_stop)

        elif self._position_state == "SHORT":
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
                    "position_type": self._position_state,
                },
                asset=self._asset_str,
                simulation_timestamp=self._current_simulation_timestamp,
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

    def handle_data(self, context: Any, data: Any) -> Any:  # noqa: ANN401
        """Process bar data and execute orders based on signals.

        Uses rustybt's real APIs:
        - data.history() for RSI calculation
        - order_target_percent() for trade execution
        - context.portfolio for position/cash tracking

        Parameters
        ----------
        context : Any
            The strategy context object (TradingAlgorithm instance).
        data : Any
            The BarData object containing price information.

        Returns
        -------
        Any
            Order object if created, None otherwise.
        """
        # Increment bar counter
        self._bar_count += 1

        # Get current price using rustybt's data.current()
        if self._asset is None:
            return None

        try:
            current_price = float(data.current(self._asset, "price"))
        except Exception:
            return None

        # During warmup, only accumulate data without trading
        if self._bar_count <= self._warmup_period:
            self._current_rsi = self._calculate_rsi_from_history(data)
            return None

        # After warmup, proceed with normal logging and trading
        super().handle_data(context, data)

        # Calculate RSI using rustybt's data.history()
        self._current_rsi = self._calculate_rsi_from_history(data)

        # Log RSI computation (Layer 2)
        self._log_event(
            layer="signals",
            event="rsi_computed",
            data={
                "price": current_price,
                "rsi": self._current_rsi,
                "stop_price": self._stop_price,
                "position": self._position_state,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Determine signal
        signal = self._compute_signal(current_price)

        # Log the signal (Layer 2)
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=self._asset_str,
            rsi=self._current_rsi,
            stop_price=self._stop_price,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log signal_generated event
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "price": current_price,
                "rsi": self._current_rsi,
                "signal": signal,
                "stop_price": self._stop_price,
                "position": self._position_state,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute based on signal using rustybt's order API
        order_result = self._execute_signal(context, signal, current_price)

        # Update portfolio tracking (Layer 4 & 5)
        self._update_portfolio_metrics(context, current_price)

        return order_result

    def _compute_signal(self, current_price: float | None = None) -> str:
        """Compute trading signal based on RSI and trailing stop.

        Parameters
        ----------
        current_price : float | None, optional
            Current price. If None, uses last price from test buffer.

        Returns
        -------
        str
            Signal: "BUY", "SELL", "EXIT_STOP", "EXIT_RSI", or "HOLD".
        """
        # Get current price from buffer if not provided (for testing)
        if current_price is None:
            if hasattr(self, "_test_price_buffer") and self._test_price_buffer:
                current_price = self._test_price_buffer[-1]
            else:
                return "HOLD"

        # Check trailing stop first (if in position)
        if self._position_state != "FLAT":
            # Update trailing stop
            self.update_trailing_stop(current_price)

            # Check if stop triggered
            if self.check_stop_triggered(current_price):
                return "EXIT_STOP"

            # Check RSI exit conditions
            if self._current_rsi is not None:
                if self._position_state == "LONG" and self._current_rsi > self._overbought:
                    return "EXIT_RSI"
                if self._position_state == "SHORT" and self._current_rsi < self._oversold:
                    return "EXIT_RSI"

        # Check entry conditions (if flat)
        if self._position_state == "FLAT" and self._current_rsi is not None:
            # Oversold -> BUY
            if self._current_rsi < self._oversold:
                return "BUY"

            # Overbought -> SELL
            if self._current_rsi > self._overbought:
                return "SELL"

        return "HOLD"

    def _execute_signal(
        self,
        context: Any,  # noqa: ANN401
        signal: str,
        current_price: float,
    ) -> Any:  # noqa: ANN401
        """Execute trade based on signal using rustybt's order API.

        Parameters
        ----------
        context : Any
            The strategy context object.
        signal : str
            Trading signal.
        current_price : float
            Current price.

        Returns
        -------
        Any
            Order object if created, None otherwise.
        """
        from rustybt.api import order_target_percent

        asset_name = self._asset_str or "UNKNOWN"

        if signal == "BUY" and self._position_state == "FLAT":
            # Enter long position
            self._entry_price = current_price
            self._stop_price = current_price * (1 - self._trailing_stop_pct)

            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=self._target_percent,
                rsi=self._current_rsi,
                stop_price=self._stop_price,
            )

            order_id = order_target_percent(self._asset, self._target_percent)
            self._position_state = "LONG"

            self.log_transaction(
                asset=asset_name,
                quantity=self._target_percent,
                price=current_price,
                commission=1.0,
                slippage=0.0,
            )

            return order_id

        elif signal == "SELL" and self._position_state == "FLAT":
            # Enter short position
            self._entry_price = current_price
            self._stop_price = current_price * (1 + self._trailing_stop_pct)

            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=-self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=-self._target_percent,
                rsi=self._current_rsi,
                stop_price=self._stop_price,
            )

            order_id = order_target_percent(self._asset, -self._target_percent)
            self._position_state = "SHORT"

            self.log_transaction(
                asset=asset_name,
                quantity=-self._target_percent,
                price=current_price,
                commission=1.0,
                slippage=0.0,
            )

            return order_id

        elif signal in ("EXIT_STOP", "EXIT_RSI"):
            exit_reason = "trailing_stop" if signal == "EXIT_STOP" else "rsi_exit"
            prev_position = self._position_state

            if self._position_state == "LONG":
                self.log_order_created(
                    order_type="market",
                    asset=asset_name,
                    quantity=-self._target_percent,
                    simulation_timestamp=self._current_simulation_timestamp,
                    target_percent=0.0,
                    exit_reason=exit_reason,
                    rsi=self._current_rsi,
                )

                order_id = order_target_percent(self._asset, 0.0)

                self.log_transaction(
                    asset=asset_name,
                    quantity=-self._target_percent,
                    price=current_price,
                    commission=1.0,
                    slippage=0.0,
                )

            elif self._position_state == "SHORT":
                self.log_order_created(
                    order_type="market",
                    asset=asset_name,
                    quantity=self._target_percent,
                    simulation_timestamp=self._current_simulation_timestamp,
                    target_percent=0.0,
                    exit_reason=exit_reason,
                    rsi=self._current_rsi,
                )

                order_id = order_target_percent(self._asset, 0.0)

                self.log_transaction(
                    asset=asset_name,
                    quantity=self._target_percent,
                    price=current_price,
                    commission=1.0,
                    slippage=0.0,
                )
            else:
                return None

            # Reset position state
            self._position_state = "FLAT"
            self._stop_price = None
            self._entry_price = None

            return order_id

        return None

    def _get_portfolio_value(self, context: Any) -> float:  # noqa: ANN401
        """Get current portfolio value from rustybt context."""
        try:
            if hasattr(context, "portfolio"):
                return float(context.portfolio.portfolio_value)
        except Exception:
            pass
        return 100000.0

    def _get_cash_balance(self, context: Any) -> float:  # noqa: ANN401
        """Get current cash balance from rustybt context."""
        try:
            if hasattr(context, "portfolio"):
                return float(context.portfolio.cash)
        except Exception:
            pass
        return 100000.0

    def _update_portfolio_metrics(self, context: Any, current_price: float) -> None:  # noqa: ANN401
        """Update and log portfolio metrics."""
        portfolio_value = self._get_portfolio_value(context)
        cash = self._get_cash_balance(context)

        self._portfolio_values.append(portfolio_value)
        if portfolio_value > self._peak_value:
            self._peak_value = portfolio_value

        daily_return = None
        if len(self._portfolio_values) > 1:
            prev_value = self._portfolio_values[-2]
            if prev_value > 0:
                daily_return = (portfolio_value - prev_value) / prev_value

        drawdown = None
        if self._peak_value > 0:
            drawdown = (self._peak_value - portfolio_value) / self._peak_value

        self.log_portfolio_update(
            portfolio_value=portfolio_value,
            cash=cash,
            daily_return=daily_return,
            drawdown=drawdown,
        )

    def finalize(self) -> None:
        """Finalize strategy and log final portfolio metrics."""
        if self._portfolio_values:
            sharpe = self._calculate_sharpe_ratio()
            self.log_final_metrics(sharpe_ratio=sharpe)

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from portfolio value history."""
        import math

        if len(self._portfolio_values) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self._portfolio_values)):
            prev = self._portfolio_values[i - 1]
            curr = self._portfolio_values[i]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)
        if len(returns) > 1:
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_return = math.sqrt(variance)
        else:
            std_return = 0.0

        if std_return > 0:
            sharpe = (mean_return / std_return) * math.sqrt(252)
        else:
            sharpe = 0.0

        return sharpe

    @property
    def rsi(self) -> float | None:
        """Get current RSI value."""
        return self._current_rsi

    @property
    def position(self) -> str:
        """Get current position type ("FLAT", "LONG", "SHORT")."""
        return self._position_state

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
        return self._position_state

    @position_type.setter
    def position_type(self, value: str) -> None:
        """Set position type (for testing)."""
        self._position_state = value

    # =========================================================================
    # Test Helper Methods
    # =========================================================================

    def _test_feed_price(self, price: float, asset: str = "TEST") -> None:
        """Feed a single price for indicator calculation (test helper).

        This method updates indicator state for unit testing without
        requiring full rustybt execution infrastructure.

        Parameters
        ----------
        price : float
            The price value to feed.
        asset : str, optional
            Asset symbol, by default "TEST".
        """
        # Initialize price buffer if not exists
        if not hasattr(self, "_test_price_buffer"):
            self._test_price_buffer: list[float] = []
            self._test_prev_price: float | None = None

        # Add price to buffer
        self._test_price_buffer.append(price)

        # Calculate RSI using standard formula
        if len(self._test_price_buffer) > self._rsi_period:
            # Calculate price changes
            gains = []
            losses = []
            for i in range(1, len(self._test_price_buffer)):
                change = self._test_price_buffer[i] - self._test_price_buffer[i - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            # Use last rsi_period for calculation
            recent_gains = gains[-self._rsi_period :]
            recent_losses = losses[-self._rsi_period :]

            avg_gain = sum(recent_gains) / self._rsi_period
            avg_loss = sum(recent_losses) / self._rsi_period

            if avg_loss == 0:
                self._current_rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                self._current_rsi = 100 - (100 / (1 + rs))
        else:
            self._current_rsi = None

        # Update trailing stop if in position
        if self._position_state == "LONG" and self._stop_price is not None:
            new_stop = price * (1 - self._trailing_stop_pct)
            if new_stop > self._stop_price:
                self._stop_price = new_stop
        elif self._position_state == "SHORT" and self._stop_price is not None:
            new_stop = price * (1 + self._trailing_stop_pct)
            if new_stop < self._stop_price:
                self._stop_price = new_stop

        self._test_prev_price = price
