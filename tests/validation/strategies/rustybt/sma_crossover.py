"""SMA Crossover strategy for rustybt validation.

This module implements a Simple Moving Average Crossover strategy that:
1. Extends RustyBTValidatedStrategy for validation logging
2. Uses rustybt's data.history() for SMA calculation
3. Uses rustybt's order_target_percent() for trade execution
4. Generates BUY signal when fast crosses above slow
5. Generates SELL signal when fast crosses below slow
6. Logs events to JSONL for comparison with Backtrader

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
    - data.history() for price data and indicator calculation
    - order_target_percent() for trade execution
    - context.portfolio for position/cash tracking
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy


class SMACrossoverStrategy(RustyBTValidatedStrategy):
    """SMA Crossover validated strategy for rustybt.

    This strategy implements a classic dual Simple Moving Average crossover:
    - BUY when fast SMA crosses above slow SMA (golden cross)
    - SELL when fast SMA crosses below slow SMA (death cross)

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file.
    fast_period : int, optional
        Period for fast SMA, by default 10.
    slow_period : int, optional
        Period for slow SMA, by default 30.
    target_percent : float, optional
        Target allocation percentage (0-1), by default 0.98 (98%).
        Using 98% provides a 2% cash buffer for price movements between
        order placement and fill (rustybt fills on next bar).

    Attributes
    ----------
    _fast_sma : float | None
        Current fast SMA value.
    _slow_sma : float | None
        Current slow SMA value.
    _prev_fast_sma : float | None
        Previous fast SMA value (for crossover detection).
    _prev_slow_sma : float | None
        Previous slow SMA value (for crossover detection).
    _position_state : int
        Current position state: 0 = flat, 1 = long.

    Note
    ----
    This implementation uses rustybt's real APIs:
    - data.history() for SMA calculation via pandas rolling mean
    - order_target_percent() for trade execution via rustybt's broker
    - context.portfolio for position/cash tracking
    """

    def __init__(
        self,
        log_path: Path,
        fast_period: int = 10,
        slow_period: int = 30,
        target_percent: float = 0.98,
    ) -> None:
        """Initialize the SMA Crossover strategy.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        fast_period : int, optional
            Period for fast SMA, by default 10.
        slow_period : int, optional
            Period for slow SMA, by default 30.
        target_percent : float, optional
            Target allocation percentage (0-1), by default 0.98.
            Using 98% instead of 100% provides a cash buffer to handle
            price movements between order placement and fill.
        """
        super().__init__(log_path)
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._target_percent = target_percent

        # SMA values for crossover detection
        self._fast_sma: float | None = None
        self._slow_sma: float | None = None
        self._prev_fast_sma: float | None = None
        self._prev_slow_sma: float | None = None

        # Position tracking (mirrors Backtrader logic)
        self._position_state: int = 0  # 0 = flat, 1 = long

        # Asset reference (set during initialize)
        self._asset: Any = None
        self._asset_str: str | None = None

        # Bar counter for warmup (match Backtrader's indicator warmup behavior)
        self._bar_count: int = 0
        # Warmup period is slow_period (Backtrader waits for slowest indicator)
        self._warmup_period: int = slow_period

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

        # Get asset from context (set by execute_rustybt.py)
        if hasattr(context, "asset"):
            self._asset = context.asset
            self._asset_str = str(context.asset) if context.asset else None
        elif hasattr(context, "assets") and context.assets:
            self._asset = context.assets[0]
            self._asset_str = str(context.assets[0])

        # Log initialization with parameters
        self._log_event(
            layer="data",
            event="sma_init",
            data={
                "fast_period": self._fast_period,
                "slow_period": self._slow_period,
                "target_percent": self._target_percent,
            },
        )

    def _calculate_sma_from_history(self, data: Any, period: int) -> float | None:  # noqa: ANN401
        """Calculate SMA using rustybt's data.history() API.

        Parameters
        ----------
        data : Any
            The BarData object from rustybt.
        period : int
            Number of periods for the SMA.

        Returns
        -------
        float | None
            SMA value, or None if insufficient data.
        """
        if self._asset is None:
            return None

        try:
            # Use rustybt's data.history() API
            prices = data.history(self._asset, "close", period, "1d")

            if prices is None or len(prices) < period:
                return None

            # Calculate SMA using pandas mean
            return float(prices.mean())
        except Exception:
            return None

    def handle_data(self, context: Any, data: Any) -> Any:  # noqa: ANN401
        """Process bar data and execute orders based on signals.

        Uses rustybt's real APIs:
        - data.history() for SMA calculation
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
        # This matches Backtrader's behavior where next() isn't called
        # until indicators have enough data
        if self._bar_count <= self._warmup_period:
            # Still calculate SMAs to track warmup progress
            self._prev_fast_sma = self._fast_sma
            self._prev_slow_sma = self._slow_sma
            self._fast_sma = self._calculate_sma_from_history(data, self._fast_period)
            self._slow_sma = self._calculate_sma_from_history(data, self._slow_period)
            return None

        # After warmup, proceed with normal logging and trading
        super().handle_data(context, data)

        # Store previous values for crossover detection
        self._prev_fast_sma = self._fast_sma
        self._prev_slow_sma = self._slow_sma

        # Calculate current SMAs using rustybt's data.history()
        self._fast_sma = self._calculate_sma_from_history(data, self._fast_period)
        self._slow_sma = self._calculate_sma_from_history(data, self._slow_period)

        # Log indicator values (Layer 2)
        self._log_event(
            layer="signals",
            event="indicator_values",
            data={
                "fast_sma": self._fast_sma,
                "slow_sma": self._slow_sma,
                "price": current_price,
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
            fast_sma=self._fast_sma,
            slow_sma=self._slow_sma,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log signal_generated event
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "fast_sma": self._fast_sma,
                "slow_sma": self._slow_sma,
                "signal": signal,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute based on signal using rustybt's order API
        order_result = self._execute_signal(context, data, signal, current_price)

        # Update portfolio tracking (Layer 4 & 5)
        self._update_portfolio_metrics(context, current_price)

        return order_result

    def _compute_signal(self) -> str:
        """Compute trading signal based on SMA crossover.

        Returns
        -------
        str
            Signal: "BUY", "SELL", or "HOLD".
        """
        # Can't generate signal without both SMAs
        if self._fast_sma is None or self._slow_sma is None:
            return "HOLD"

        # Can't detect crossover without previous values
        if self._prev_fast_sma is None or self._prev_slow_sma is None:
            return "HOLD"

        # Detect crossover
        # BUY: fast crosses ABOVE slow (golden cross)
        if self._prev_fast_sma <= self._prev_slow_sma and self._fast_sma > self._slow_sma:
            return "BUY"

        # SELL: fast crosses BELOW slow (death cross)
        if self._prev_fast_sma >= self._prev_slow_sma and self._fast_sma < self._slow_sma:
            return "SELL"

        return "HOLD"

    def _execute_signal(
        self,
        context: Any,  # noqa: ANN401
        data: Any,  # noqa: ANN401
        signal: str,
        current_price: float,
    ) -> Any:  # noqa: ANN401
        """Execute trade based on signal using rustybt's order API.

        Parameters
        ----------
        context : Any
            The strategy context object.
        data : Any
            The BarData object.
        signal : str
            Trading signal: "BUY", "SELL", or "HOLD".
        current_price : float
            Current price for share calculation.

        Returns
        -------
        Any
            Order object if created, None otherwise.

        Note
        ----
        This method checks ACTUAL portfolio positions rather than relying on
        assumed state. This ensures correct behavior when orders are rejected
        by the broker due to insufficient funds or other reasons.
        """
        from rustybt.api import order_target_percent

        asset_name = self._asset_str or "UNKNOWN"

        # Sync position state with actual portfolio before executing
        # This handles cases where previous orders were rejected
        actual_position = self._get_position_size(context)
        if actual_position > 0 and self._position_state == 0:
            # We have a position but state says flat - sync it
            self._position_state = 1
        elif actual_position == 0 and self._position_state == 1:
            # No position but state says long - sync it (order was rejected)
            self._position_state = 0

        if signal == "BUY" and self._position_state == 0:
            # Double-check we don't already have a position
            if actual_position > 0:
                return None  # Already have position, skip BUY

            # Calculate shares to buy for logging (matches Backtrader calculation)
            portfolio_value = self._get_portfolio_value(context)
            target_value = portfolio_value * self._target_percent
            shares_to_buy = int(target_value / current_price) if current_price > 0 else 0

            if shares_to_buy > 0:
                # Execute order using rustybt's API
                order_id = order_target_percent(self._asset, self._target_percent)

                # Only log order_created if order was accepted
                # Note: We do NOT update position state or log transaction here
                # because the order fills on the NEXT bar and may be rejected
                # due to price movement. Position state is synced from actual
                # portfolio at the start of each _execute_signal() call.
                if order_id is not None:
                    # Log order_created (Layer 3)
                    self.log_order_created(
                        order_type="market",
                        asset=asset_name,
                        quantity=shares_to_buy,
                        simulation_timestamp=self._current_simulation_timestamp,
                        target_percent=self._target_percent,
                    )
                    # Do NOT log transaction here - fills happen on next bar
                    # and may be rejected. Actual fills are tracked via portfolio state.

                return order_id

        elif signal == "SELL" and self._position_state == 1:
            # Check ACTUAL position size, not assumed state
            shares_to_sell = actual_position

            if shares_to_sell > 0:
                # Execute order using rustybt's API
                order_id = order_target_percent(self._asset, 0.0)

                # Only log order_created if order was accepted
                # Note: We do NOT update position state or log transaction here
                # because the order fills on the NEXT bar. Position state is
                # synced from actual portfolio at the start of each _execute_signal() call.
                if order_id is not None:
                    # Log order_created (Layer 3)
                    self.log_order_created(
                        order_type="market",
                        asset=asset_name,
                        quantity=-shares_to_sell,
                        simulation_timestamp=self._current_simulation_timestamp,
                        target_percent=0.0,
                    )
                    # Do NOT log transaction here - fills happen on next bar.
                    # Actual fills are tracked via portfolio state.

                return order_id

        return None

    def _get_portfolio_value(self, context: Any) -> float:  # noqa: ANN401
        """Get current portfolio value from rustybt context.

        Parameters
        ----------
        context : Any
            The strategy context object.

        Returns
        -------
        float
            Current portfolio value.
        """
        try:
            if hasattr(context, "portfolio"):
                return float(context.portfolio.portfolio_value)
        except Exception:
            pass
        return 100000.0  # Default fallback

    def _get_position_size(self, context: Any) -> float:  # noqa: ANN401
        """Get current position size from rustybt context.

        Parameters
        ----------
        context : Any
            The strategy context object.

        Returns
        -------
        float
            Current position size (shares held).
        """
        try:
            if hasattr(context, "portfolio") and self._asset is not None:
                positions = context.portfolio.positions
                if self._asset in positions:
                    return abs(float(positions[self._asset].amount))
        except Exception:
            pass
        return 0.0

    def _get_cash_balance(self, context: Any) -> float:  # noqa: ANN401
        """Get current cash balance from rustybt context.

        Parameters
        ----------
        context : Any
            The strategy context object.

        Returns
        -------
        float
            Current cash balance.
        """
        try:
            if hasattr(context, "portfolio"):
                return float(context.portfolio.cash)
        except Exception:
            pass
        return 100000.0  # Default fallback

    def _update_portfolio_metrics(self, context: Any, current_price: float) -> None:  # noqa: ANN401
        """Update and log portfolio metrics.

        Parameters
        ----------
        context : Any
            The strategy context object.
        current_price : float
            Current price for position valuation.
        """
        portfolio_value = self._get_portfolio_value(context)
        cash = self._get_cash_balance(context)

        # Track values for drawdown calculation
        self._portfolio_values.append(portfolio_value)
        if portfolio_value > self._peak_value:
            self._peak_value = portfolio_value

        # Calculate daily return (after first bar post-warmup)
        daily_return = None
        if len(self._portfolio_values) > 1:
            prev_value = self._portfolio_values[-2]
            if prev_value > 0:
                daily_return = (portfolio_value - prev_value) / prev_value

        # Calculate drawdown
        drawdown = None
        if self._peak_value > 0:
            drawdown = (self._peak_value - portfolio_value) / self._peak_value

        # Log portfolio update (Layer 4 & 5)
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
        """Calculate Sharpe ratio from portfolio value history.

        Returns
        -------
        float
            Annualized Sharpe ratio (assuming 252 trading days).
            Returns 0.0 if insufficient data.
        """
        import math

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

    @property
    def fast_sma(self) -> float | None:
        """Get current fast SMA value."""
        return self._fast_sma

    @property
    def slow_sma(self) -> float | None:
        """Get current slow SMA value."""
        return self._slow_sma

    @property
    def position_state(self) -> int:
        """Get current position state (0 = flat, 1 = long)."""
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
        # Initialize price buffer if not exists
        if not hasattr(self, "_test_price_buffer"):
            self._test_price_buffer: list[float] = []

        # Add price to buffer
        self._test_price_buffer.append(price)

        # Store previous values for crossover detection
        self._prev_fast_sma = self._fast_sma
        self._prev_slow_sma = self._slow_sma

        # Calculate SMAs from buffer
        if len(self._test_price_buffer) >= self._fast_period:
            self._fast_sma = sum(self._test_price_buffer[-self._fast_period :]) / self._fast_period
        else:
            self._fast_sma = None

        if len(self._test_price_buffer) >= self._slow_period:
            self._slow_sma = sum(self._test_price_buffer[-self._slow_period :]) / self._slow_period
        else:
            self._slow_sma = None
