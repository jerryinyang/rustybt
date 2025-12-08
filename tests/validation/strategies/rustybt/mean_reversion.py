"""Mean Reversion strategy for rustybt validation.

This module implements a Z-score based Mean Reversion strategy that:
1. Extends RustyBTValidatedStrategy for validation logging
2. Uses rustybt's data.history() for mean/std calculation
3. Uses rustybt's order_target_percent() for trade execution
4. Generates BUY signal when z-score < -2 (oversold)
5. Generates SELL signal when z-score > 2 (overbought)
6. Generates EXIT signal when z-score returns to 0
7. Logs events to JSONL for comparison with Backtrader

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
    - data.history() for price data and statistics calculation
    - order_target_percent() for trade execution
    - context.portfolio for position/cash tracking
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy


class MeanReversionStrategy(RustyBTValidatedStrategy):
    """Mean Reversion validated strategy for rustybt using z-score.

    This strategy implements a classic mean reversion approach:
    - BUY when z-score < -entry_threshold (price significantly below mean)
    - SELL when z-score > +entry_threshold (price significantly above mean)
    - EXIT when |z-score| < exit_threshold (mean reversion complete)

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file.
    lookback_period : int, optional
        Number of periods for rolling mean/std calculation, by default 20.
    entry_threshold : float, optional
        Z-score threshold for entry signals (absolute value), by default 2.0.
    exit_threshold : float, optional
        Z-score threshold for exit signals (absolute value), by default 0.0.
    target_percent : float, optional
        Target allocation percentage (0-1), by default 1.0 (100%).

    Note
    ----
    This implementation uses rustybt's real APIs:
    - data.history() for rolling statistics calculation
    - order_target_percent() for trade execution via rustybt's broker
    - context.portfolio for position/cash tracking
    """

    def __init__(
        self,
        log_path: Path,
        lookback_period: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.0,
        target_percent: float = 1.0,
    ) -> None:
        """Initialize the Mean Reversion strategy.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        lookback_period : int, optional
            Number of periods for rolling mean/std, by default 20.
        entry_threshold : float, optional
            Z-score threshold for entries, by default 2.0.
        exit_threshold : float, optional
            Z-score threshold for exits, by default 0.0.
        target_percent : float, optional
            Target allocation percentage (0-1), by default 1.0.
        """
        super().__init__(log_path)
        self._lookback_period = lookback_period
        self._entry_threshold = entry_threshold
        self._exit_threshold = exit_threshold
        self._target_percent = target_percent

        # Current statistics
        self._current_mean: float | None = None
        self._current_std: float | None = None
        self._current_zscore: float | None = None

        # Position tracking: -1 = short, 0 = flat, 1 = long
        self._position_state: int = 0

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
            event="mean_reversion_init",
            data={
                "lookback_period": self._lookback_period,
                "entry_threshold": self._entry_threshold,
                "exit_threshold": self._exit_threshold,
                "target_percent": self._target_percent,
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

    def handle_data(self, context: Any, data: Any) -> Any:  # noqa: ANN401
        """Process bar data and execute orders based on signals.

        Uses rustybt's real APIs:
        - data.history() for statistics calculation
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
        signal = self._compute_signal()

        # Log the signal (Layer 2)
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=self._asset_str,
            z_score=self._current_zscore,
            mean=self._current_mean,
            std_dev=self._current_std,
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
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute based on signal using rustybt's order API
        order_result = self._execute_signal(context, signal, current_price)

        # Update portfolio tracking (Layer 4 & 5)
        self._update_portfolio_metrics(context, current_price)

        return order_result

    def _compute_signal(self) -> str:
        """Compute trading signal based on z-score mean reversion.

        Returns
        -------
        str
            Signal: "BUY", "SELL", "EXIT_LONG", "EXIT_SHORT", or "HOLD".
        """
        # Can't generate signal without z-score
        if self._current_zscore is None:
            return "HOLD"

        # Check exit conditions first (if in position)
        if self._position_state == 1:  # Long position
            # Exit long when z-score returns to mean
            if abs(self._current_zscore) <= self._exit_threshold:
                return "EXIT_LONG"

        if self._position_state == -1:  # Short position
            # Exit short when z-score returns to mean
            if abs(self._current_zscore) <= self._exit_threshold:
                return "EXIT_SHORT"

        # Check entry conditions (if flat)
        if self._position_state == 0:
            # Oversold: price significantly below mean -> BUY
            if self._current_zscore < -self._entry_threshold:
                return "BUY"

            # Overbought: price significantly above mean -> SELL (short)
            if self._current_zscore > self._entry_threshold:
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
            Current price for logging.

        Returns
        -------
        Any
            Order object if created, None otherwise.
        """
        from rustybt.api import order_target_percent

        asset_name = self._asset_str or "UNKNOWN"

        if signal == "BUY" and self._position_state == 0:
            # Enter long position
            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=self._target_percent,
                z_score=self._current_zscore,
            )

            order_id = order_target_percent(self._asset, self._target_percent)
            self._position_state = 1
            # Log position change
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={"position_state": "LONG", "target_percent": self._target_percent},
                asset=asset_name,
                simulation_timestamp=self._current_simulation_timestamp,
            )
            return order_id

        elif signal == "SELL" and self._position_state == 0:
            # Enter short position
            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=-self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=-self._target_percent,
                z_score=self._current_zscore,
            )

            order_id = order_target_percent(self._asset, -self._target_percent)
            self._position_state = -1
            # Log position change
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={"position_state": "SHORT", "target_percent": -self._target_percent},
                asset=asset_name,
                simulation_timestamp=self._current_simulation_timestamp,
            )
            return order_id

        elif signal == "EXIT_LONG" and self._position_state == 1:
            # Exit long position
            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=-self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=0.0,
                z_score=self._current_zscore,
            )

            order_id = order_target_percent(self._asset, 0.0)
            self._position_state = 0
            # Log position change
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={"position_state": "FLAT", "target_percent": 0.0},
                asset=asset_name,
                simulation_timestamp=self._current_simulation_timestamp,
            )
            return order_id

        elif signal == "EXIT_SHORT" and self._position_state == -1:
            # Exit short position
            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=0.0,
                z_score=self._current_zscore,
            )

            order_id = order_target_percent(self._asset, 0.0)
            self._position_state = 0
            # Log position change
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={"position_state": "FLAT", "target_percent": 0.0},
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
