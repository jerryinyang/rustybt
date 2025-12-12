"""Mean Reversion V2 strategy for rustybt validation.

This module implements a Z-score based Mean Reversion strategy with:
1. Limit orders for entries (buy low, sell high)
2. Stop-loss orders for risk management
3. Take-profit orders for profit targets
4. Position closing with order_target_percent

Strategy Logic (from 03_strategy_development.ipynb):
- Calculate z-score to identify overbought/oversold conditions
- Place limit BUY orders when oversold (z-score < -2)
- Place limit SELL orders when overbought (z-score > +2)
- Set stop-loss to limit downside risk (3% default)
- Set take-profit to lock in gains (6% default)
- Exit when z-score returns to ±0.5 (mean reversion complete)
- Close all positions using order_target_percent

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

import math
from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy


class MeanReversionV2Strategy(RustyBTValidatedStrategy):
    """Mean Reversion V2 strategy with limit entries and stop-loss/take-profit exits.

    This strategy implements mean reversion with professional risk management:
    - Limit entries: Enter at favorable prices (0.5% better than current)
    - Stop-loss: Exit if loss exceeds threshold (3% default)
    - Take-profit: Lock in gains when target reached (6% default)
    - Mean reversion exit: Exit when z-score normalizes

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file.
    lookback_period : int, optional
        Number of periods for rolling mean/std calculation, by default 20.
    z_entry : float, optional
        Z-score threshold for entry signals (absolute value), by default 2.0.
    z_exit : float, optional
        Z-score threshold for exit on mean reversion, by default 0.5.
    stop_loss_pct : float, optional
        Stop-loss percentage (0-1), by default 0.03 (3%).
    take_profit_pct : float, optional
        Take-profit percentage (0-1), by default 0.06 (6%).
    limit_offset_pct : float, optional
        Limit order offset from current price (0-1), by default 0.005 (0.5%).
    shares_per_trade : int, optional
        Number of shares per trade, by default 100.
    """

    def __init__(
        self,
        log_path: Path,
        lookback_period: int = 20,
        z_entry: float = 2.0,
        z_exit: float = 0.5,
        stop_loss_pct: float = 0.03,
        take_profit_pct: float = 0.06,
        limit_offset_pct: float = 0.005,
        shares_per_trade: int = 100,
    ) -> None:
        """Initialize the Mean Reversion V2 strategy.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        lookback_period : int, optional
            Number of periods for rolling mean/std, by default 20.
        z_entry : float, optional
            Z-score threshold for entries, by default 2.0.
        z_exit : float, optional
            Z-score threshold for mean reversion exit, by default 0.5.
        stop_loss_pct : float, optional
            Stop-loss percentage, by default 0.03.
        take_profit_pct : float, optional
            Take-profit percentage, by default 0.06.
        limit_offset_pct : float, optional
            Limit order offset from current price, by default 0.005.
        shares_per_trade : int, optional
            Shares per trade, by default 100.
        """
        super().__init__(log_path)
        self._lookback_period = lookback_period
        self._z_entry = z_entry
        self._z_exit = z_exit
        self._stop_loss_pct = stop_loss_pct
        self._take_profit_pct = take_profit_pct
        self._limit_offset_pct = limit_offset_pct
        self._shares_per_trade = shares_per_trade

        # Current statistics
        self._current_mean: float | None = None
        self._current_std: float | None = None
        self._current_zscore: float | None = None

        # Position tracking: -1 = short, 0 = flat, 1 = long
        self._position_state: int = 0

        # Entry price tracking for stop-loss/take-profit
        self._entry_price: float | None = None

        # Asset reference (set during initialize)
        self._asset: Any = None
        self._asset_str: str | None = None

        # Bar counter for warmup
        self._bar_count: int = 0
        self._warmup_period: int = lookback_period

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
            event="mean_reversion_v2_init",
            data={
                "lookback_period": self._lookback_period,
                "z_entry": self._z_entry,
                "z_exit": self._z_exit,
                "stop_loss_pct": self._stop_loss_pct,
                "take_profit_pct": self._take_profit_pct,
                "limit_offset_pct": self._limit_offset_pct,
                "shares_per_trade": self._shares_per_trade,
            },
        )

    def _calculate_statistics_from_history(
        self, data: Any  # noqa: ANN401
    ) -> tuple[float | None, float | None]:
        """Calculate rolling mean and standard deviation using data.history().

        Parameters
        ----------
        data : Any
            The BarData object from rustybt.

        Returns
        -------
        tuple[float | None, float | None]
            (mean, std_dev) or (None, None) if insufficient data.
        """
        if self._asset is None:
            return None, None

        try:
            # Use rustybt's data.history() API
            prices = data.history(self._asset, "close", self._lookback_period, "1d")

            if prices is None or len(prices) < self._lookback_period:
                return None, None

            # Calculate mean using pandas
            mean = float(prices.mean())

            # Calculate population standard deviation using pandas
            std_dev = float(prices.std(ddof=0))  # Population std (ddof=0)

            return mean, std_dev
        except Exception:
            return None, None

    def _calculate_zscore(self, price: float) -> float | None:
        """Calculate z-score for the current price.

        Parameters
        ----------
        price : float
            Current price.

        Returns
        -------
        float | None
            Z-score value, or None if insufficient data or std_dev is 0.
        """
        if self._current_mean is None or self._current_std is None:
            return None

        # Handle division by zero (no variance in prices)
        if self._current_std == 0:
            return 0.0

        z_score = (price - self._current_mean) / self._current_std

        # Handle NaN/Inf
        if math.isnan(z_score) or math.isinf(z_score):
            return 0.0

        return z_score

    def _calculate_pnl_pct(self, current_price: float) -> float | None:
        """Calculate profit/loss percentage from entry.

        Parameters
        ----------
        current_price : float
            Current market price.

        Returns
        -------
        float | None
            P&L percentage, or None if no entry price.
        """
        if self._entry_price is None or self._entry_price == 0:
            return None

        # For long positions: (current - entry) / entry
        # For short positions: (entry - current) / entry
        if self._position_state == 1:  # Long
            return (current_price - self._entry_price) / self._entry_price
        elif self._position_state == -1:  # Short
            return (self._entry_price - current_price) / self._entry_price
        return None

    def handle_data(self, context: Any, data: Any) -> Any:  # noqa: ANN401
        """Process bar data and execute orders based on signals.

        Uses rustybt's real APIs:
        - data.history() for statistics calculation
        - order() with limit_price for limit entries
        - order_target_percent() for exits

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
        if self._bar_count < self._warmup_period:
            self._current_mean, self._current_std = self._calculate_statistics_from_history(data)
            self._current_zscore = self._calculate_zscore(current_price)
            return None

        # After warmup, proceed with normal logging and trading
        super().handle_data(context, data)

        # Calculate statistics using rustybt's data.history()
        self._current_mean, self._current_std = self._calculate_statistics_from_history(data)

        # Calculate z-score
        self._current_zscore = self._calculate_zscore(current_price)

        # Log z-score computation (Layer 2)
        self._log_event(
            layer="signals",
            event="zscore_computed",
            data={
                "price": current_price,
                "mean": self._current_mean,
                "std_dev": self._current_std,
                "z_score": self._current_zscore,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Determine signal
        signal, signal_details = self._compute_signal(current_price)

        # Log the signal (Layer 2)
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=self._asset_str,
            z_score=self._current_zscore,
            mean=self._current_mean,
            std_dev=self._current_std,
            **signal_details,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log signal_generated event
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "price": current_price,
                "mean": self._current_mean,
                "std_dev": self._current_std,
                "z_score": self._current_zscore,
                "signal": signal,
                **signal_details,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute based on signal using rustybt's order API
        order_result = self._execute_signal(context, signal, current_price, signal_details)

        # Update portfolio tracking (Layer 4 & 5)
        self._update_portfolio_metrics(context, current_price)

        return order_result

    def _compute_signal(self, current_price: float) -> tuple[str, dict[str, Any]]:
        """Compute trading signal based on z-score with stop-loss/take-profit.

        Parameters
        ----------
        current_price : float
            Current market price.

        Returns
        -------
        tuple[str, dict[str, Any]]
            Signal string and additional details dictionary.
        """
        details: dict[str, Any] = {}

        # Can't generate signal without z-score
        if self._current_zscore is None:
            return "HOLD", details

        # Exit Logic: Check stop-loss, take-profit, or mean reversion exits first
        if self._position_state != 0:
            pnl_pct = self._calculate_pnl_pct(current_price)
            details["pnl_pct"] = pnl_pct

            if pnl_pct is not None:
                # LONG position exits
                if self._position_state == 1:
                    # Stop-loss: Exit if loss exceeds threshold
                    if pnl_pct <= -self._stop_loss_pct:
                        details["exit_reason"] = "stop_loss"
                        return "STOP_LOSS", details

                    # Take-profit: Exit if profit target reached
                    if pnl_pct >= self._take_profit_pct:
                        details["exit_reason"] = "take_profit"
                        return "TAKE_PROFIT", details

                    # Mean reversion exit: Exit when z-score normalizes
                    if self._current_zscore > -self._z_exit:
                        details["exit_reason"] = "mean_revert"
                        return "EXIT_LONG", details

                # SHORT position exits
                elif self._position_state == -1:
                    # Stop-loss for short: Exit if loss exceeds threshold
                    if pnl_pct <= -self._stop_loss_pct:
                        details["exit_reason"] = "stop_loss"
                        return "STOP_LOSS_SHORT", details

                    # Take-profit for short
                    if pnl_pct >= self._take_profit_pct:
                        details["exit_reason"] = "take_profit"
                        return "TAKE_PROFIT_SHORT", details

                    # Mean reversion exit for short
                    if self._current_zscore < self._z_exit:
                        details["exit_reason"] = "mean_revert"
                        return "EXIT_SHORT", details

            return "HOLD", details

        # Entry Logic: Place limit orders when flat
        if self._position_state == 0:
            # Oversold: Place limit BUY order below current price
            if self._current_zscore < -self._z_entry:
                limit_price = current_price * (1 - self._limit_offset_pct)
                details["limit_price"] = limit_price
                return "BUY_LIMIT", details

            # Overbought: Place limit SELL order above current price (short)
            if self._current_zscore > self._z_entry:
                limit_price = current_price * (1 + self._limit_offset_pct)
                details["limit_price"] = limit_price
                return "SELL_LIMIT", details

        return "HOLD", details

    def _execute_signal(
        self,
        context: Any,  # noqa: ANN401
        signal: str,
        current_price: float,
        signal_details: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        """Execute trade based on signal using rustybt's order API.

        Parameters
        ----------
        context : Any
            The strategy context object.
        signal : str
            Trading signal.
        current_price : float
            Current price for logging.
        signal_details : dict[str, Any]
            Additional signal details (limit_price, etc.).

        Returns
        -------
        Any
            Order object if created, None otherwise.
        """
        from rustybt.api import order, order_target_percent

        asset_name = self._asset_str or "UNKNOWN"

        # Entry signals with limit orders
        if signal == "BUY_LIMIT" and self._position_state == 0:
            limit_price = signal_details.get("limit_price", current_price)
            self.log_order_created(
                order_type="limit",
                asset=asset_name,
                quantity=self._shares_per_trade,
                limit_price=limit_price,
                simulation_timestamp=self._current_simulation_timestamp,
                z_score=self._current_zscore,
            )

            order_id = order(self._asset, self._shares_per_trade, limit_price=limit_price)
            self._position_state = 1
            self._entry_price = limit_price  # Track limit price as entry
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={
                    "position_state": "LONG",
                    "entry_type": "limit",
                    "limit_price": limit_price,
                },
                asset=asset_name,
                simulation_timestamp=self._current_simulation_timestamp,
            )
            return order_id

        elif signal == "SELL_LIMIT" and self._position_state == 0:
            limit_price = signal_details.get("limit_price", current_price)
            self.log_order_created(
                order_type="limit",
                asset=asset_name,
                quantity=-self._shares_per_trade,
                limit_price=limit_price,
                simulation_timestamp=self._current_simulation_timestamp,
                z_score=self._current_zscore,
            )

            order_id = order(self._asset, -self._shares_per_trade, limit_price=limit_price)
            self._position_state = -1
            self._entry_price = limit_price  # Track limit price as entry
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={
                    "position_state": "SHORT",
                    "entry_type": "limit",
                    "limit_price": limit_price,
                },
                asset=asset_name,
                simulation_timestamp=self._current_simulation_timestamp,
            )
            return order_id

        # Exit signals (all exit with market order via order_target_percent)
        elif signal in ("STOP_LOSS", "TAKE_PROFIT", "EXIT_LONG") and self._position_state == 1:
            pnl_pct = signal_details.get("pnl_pct", 0)
            exit_reason = signal_details.get("exit_reason", signal.lower())
            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=-self._shares_per_trade,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=0.0,
                z_score=self._current_zscore,
                exit_reason=exit_reason,
                pnl_pct=pnl_pct,
            )

            order_id = order_target_percent(self._asset, 0.0)
            self._position_state = 0
            self._entry_price = None
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={
                    "position_state": "FLAT",
                    "exit_reason": exit_reason,
                    "pnl_pct": pnl_pct,
                },
                asset=asset_name,
                simulation_timestamp=self._current_simulation_timestamp,
            )
            return order_id

        elif (
            signal in ("STOP_LOSS_SHORT", "TAKE_PROFIT_SHORT", "EXIT_SHORT")
            and self._position_state == -1
        ):
            pnl_pct = signal_details.get("pnl_pct", 0)
            exit_reason = signal_details.get("exit_reason", signal.lower())
            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=self._shares_per_trade,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=0.0,
                z_score=self._current_zscore,
                exit_reason=exit_reason,
                pnl_pct=pnl_pct,
            )

            order_id = order_target_percent(self._asset, 0.0)
            self._position_state = 0
            self._entry_price = None
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={
                    "position_state": "FLAT",
                    "exit_reason": exit_reason,
                    "pnl_pct": pnl_pct,
                },
                asset=asset_name,
                simulation_timestamp=self._current_simulation_timestamp,
            )
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
            final_value = self._portfolio_values[-1]
            initial_value = self._portfolio_values[0] if self._portfolio_values else 0.0
            total_return = ((final_value / initial_value) - 1.0) * 100 if initial_value > 0 else 0.0
            self.log_final_metrics(
                sharpe_ratio=sharpe,
                data_final_portfolio_value=final_value,
                data_initial_portfolio_value=initial_value,
                data_total_return_pct=total_return,
            )

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
    def mean(self) -> float | None:
        """Get current rolling mean."""
        return self._current_mean

    @property
    def std_dev(self) -> float | None:
        """Get current rolling standard deviation."""
        return self._current_std

    @property
    def zscore(self) -> float | None:
        """Get current z-score."""
        return self._current_zscore

    @property
    def position(self) -> int:
        """Get current position (-1 = short, 0 = flat, 1 = long)."""
        return self._position_state

    @property
    def entry_price(self) -> float | None:
        """Get current entry price."""
        return self._entry_price

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
        import math

        # Initialize price buffer if not exists
        if not hasattr(self, "_test_price_buffer"):
            self._test_price_buffer: list[float] = []

        # Add price to buffer
        self._test_price_buffer.append(price)

        # Calculate statistics from buffer
        if len(self._test_price_buffer) >= self._lookback_period:
            window = self._test_price_buffer[-self._lookback_period :]
            self._current_mean = sum(window) / len(window)

            # Calculate standard deviation
            variance = sum((x - self._current_mean) ** 2 for x in window) / len(window)
            self._current_std = math.sqrt(variance)

            # Calculate z-score (with division by zero protection)
            if self._current_std > 0:
                self._current_zscore = (price - self._current_mean) / self._current_std
            else:
                self._current_zscore = 0.0
        else:
            self._current_mean = None
            self._current_std = None
            self._current_zscore = None

    def _test_set_entry_price(self, entry_price: float) -> None:
        """Set entry price for testing stop-loss/take-profit logic.

        Parameters
        ----------
        entry_price : float
            The entry price to set.
        """
        self._entry_price = entry_price

    def _test_set_position(self, position: int) -> None:
        """Set position state for testing.

        Parameters
        ----------
        position : int
            Position state: -1 = short, 0 = flat, 1 = long.
        """
        self._position_state = position

    def compute_signal(self, price: float, asset: str = "TEST") -> str:
        """Compute signal from price (test helper for backward compatibility).

        This method provides a simplified interface for unit testing.
        It feeds the price to indicators and computes the signal.

        Parameters
        ----------
        price : float
            The current price.
        asset : str, optional
            Asset symbol, by default "TEST".

        Returns
        -------
        str
            Signal: "BUY_LIMIT", "SELL_LIMIT", "STOP_LOSS", "TAKE_PROFIT",
            "EXIT_LONG", "EXIT_SHORT", or "HOLD".
        """
        self._test_feed_price(price, asset)
        signal, _ = self._compute_signal(price)
        return signal
