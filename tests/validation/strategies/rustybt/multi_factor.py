"""Multi-Factor strategy combining EMA + RSI + MACD for rustybt validation.

This module implements a Multi-Factor strategy that:
1. Extends RustyBTValidatedStrategy for validation logging
2. Uses rustybt's data.history() for EMA, RSI, and MACD calculation
3. Uses rustybt's order_target_percent() for trade execution
4. Each factor returns a score of 1 (bullish) or 0 (not bullish)
5. Entry requires all 3 factors = 1 (total score = 3)
6. Exit when any factor drops to 0 OR RSI > 80 (overbought emergency exit)
7. Logs individual factor values and scores for comparison with Backtrader

The log format follows the validation framework schema:
    {
        "timestamp": ISO8601 string,
        "layer": "data|signals|orders|broker|portfolio",
        "event": descriptive event name,
        "asset": asset symbol or null,
        "data": dictionary of event-specific data
    }

Factor Logic:
    - Trend Factor: 1 if price > EMA(50), else 0
    - Momentum (RSI) Factor: 1 if 50 < RSI < 70, else 0
    - Momentum (MACD) Factor: 1 if MACD line > Signal line, else 0

Epic X Implementation:
    This implementation uses rustybt's real APIs:
    - data.history() for indicator calculations
    - order_target_percent() for trade execution
    - context.portfolio for position/cash tracking
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy


class MultiFactorStrategy(RustyBTValidatedStrategy):
    """Multi-Factor validated strategy for rustybt with EMA + RSI + MACD.

    This strategy implements a factor-based approach:
    - Three factors must align for entry (trend, RSI momentum, MACD momentum)
    - Exit when any factor fails or RSI exceeds overbought threshold (80)

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file.
    ema_period : int, optional
        Period for EMA calculation, by default 50.
    rsi_period : int, optional
        Period for RSI calculation, by default 14.
    macd_fast : int, optional
        Fast period for MACD, by default 12.
    macd_slow : int, optional
        Slow period for MACD, by default 26.
    macd_signal : int, optional
        Signal period for MACD, by default 9.
    target_percent : float, optional
        Target allocation percentage (0-1), by default 1.0 (100%).

    Note
    ----
    This implementation uses rustybt's real APIs:
    - data.history() for all indicator calculations
    - order_target_percent() for trade execution via rustybt's broker
    - context.portfolio for position/cash tracking
    """

    def __init__(
        self,
        log_path: Path,
        ema_period: int = 50,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        target_percent: float = 1.0,
    ) -> None:
        """Initialize the Multi-Factor strategy.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        ema_period : int, optional
            Period for EMA, by default 50.
        rsi_period : int, optional
            Period for RSI, by default 14.
        macd_fast : int, optional
            Fast period for MACD, by default 12.
        macd_slow : int, optional
            Slow period for MACD, by default 26.
        macd_signal : int, optional
            Signal period for MACD, by default 9.
        target_percent : float, optional
            Target allocation percentage (0-1), by default 1.0.
        """
        super().__init__(log_path)
        self._ema_period = ema_period
        self._rsi_period = rsi_period
        self._macd_fast = macd_fast
        self._macd_slow = macd_slow
        self._macd_signal_period = macd_signal
        self._target_percent = target_percent

        # Indicator values
        self._ema: float | None = None
        self._rsi: float | None = None
        self._macd_line: float | None = None
        self._macd_signal_line: float | None = None

        # MACD history for signal line calculation
        self._macd_history: list[float] = []

        # Position tracking
        self._position_state: int = 0  # 0 = flat, 1 = long

        # Asset reference (set during initialize)
        self._asset: Any = None
        self._asset_str: str | None = None

        # Bar counter for warmup
        self._bar_count: int = 0
        # Warmup period is the slowest indicator (EMA 50 or MACD slow + signal)
        self._warmup_period: int = max(ema_period, macd_slow + macd_signal, rsi_period + 1)

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
            event="multi_factor_init",
            data={
                "ema_period": self._ema_period,
                "rsi_period": self._rsi_period,
                "macd_fast": self._macd_fast,
                "macd_slow": self._macd_slow,
                "macd_signal": self._macd_signal_period,
                "target_percent": self._target_percent,
            },
        )

    def _compute_ema(self, prices: list[float], period: int) -> float | None:
        """Compute Exponential Moving Average.

        Parameters
        ----------
        prices : list[float]
            Price series.
        period : int
            EMA period.

        Returns
        -------
        float | None
            EMA value, or None if insufficient data.
        """
        if len(prices) < period:
            return None

        # Initial SMA for EMA seeding
        initial_sma = sum(prices[:period]) / period

        # EMA multiplier
        multiplier = 2 / (period + 1)

        # Calculate EMA
        ema = initial_sma
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_ema_from_history(self, data: Any) -> float | None:  # noqa: ANN401
        """Calculate EMA using rustybt's data.history() API.

        Parameters
        ----------
        data : Any
            The BarData object from rustybt.

        Returns
        -------
        float | None
            EMA value, or None if insufficient data.
        """
        if self._asset is None:
            return None

        try:
            prices = data.history(self._asset, "close", self._ema_period + 10, "1d")

            if prices is None or len(prices) < self._ema_period:
                return None

            prices_list = list(prices)
            return self._compute_ema(prices_list, self._ema_period)
        except Exception:
            return None

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

            # Calculate average gain and loss (simple average)
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

    def _calculate_macd_from_history(
        self, data: Any  # noqa: ANN401
    ) -> tuple[float | None, float | None]:
        """Calculate MACD line and signal line using data.history().

        Parameters
        ----------
        data : Any
            The BarData object from rustybt.

        Returns
        -------
        tuple[float | None, float | None]
            (MACD line, Signal line), or (None, None) if insufficient data.
        """
        if self._asset is None:
            return None, None

        try:
            # Need enough data for slow EMA + signal period
            required_bars = self._macd_slow + self._macd_signal_period
            prices = data.history(self._asset, "close", required_bars, "1d")

            if prices is None or len(prices) < self._macd_slow:
                return None, None

            prices_list = list(prices)

            # Calculate fast and slow EMAs
            fast_ema = self._compute_ema(prices_list, self._macd_fast)
            slow_ema = self._compute_ema(prices_list, self._macd_slow)

            if fast_ema is None or slow_ema is None:
                return None, None

            # MACD line = Fast EMA - Slow EMA
            macd_line = fast_ema - slow_ema

            # Add to MACD history for signal line calculation
            self._macd_history.append(macd_line)

            # Keep only what we need
            if len(self._macd_history) > self._macd_signal_period:
                self._macd_history = self._macd_history[-self._macd_signal_period :]

            # Signal line = EMA of MACD line
            if len(self._macd_history) < self._macd_signal_period:
                return macd_line, None

            signal_line = self._compute_ema(self._macd_history, self._macd_signal_period)

            return macd_line, signal_line
        except Exception:
            return None, None

    def compute_factors(self, price: float) -> dict[str, int]:
        """Compute factor scores for multi-factor strategy.

        Parameters
        ----------
        price : float
            Current price.

        Returns
        -------
        dict[str, int]
            Dictionary with factor names and scores (0 or 1).
        """
        factors = {
            "trend": 0,
            "momentum_rsi": 0,
            "momentum_macd": 0,
        }

        # Trend factor: Price > EMA(50)
        if self._ema is not None and price > self._ema:
            factors["trend"] = 1

        # RSI momentum factor: 50 < RSI < 70
        if self._rsi is not None and 50 < self._rsi < 70:
            factors["momentum_rsi"] = 1

        # MACD momentum factor: MACD > Signal
        if (
            self._macd_line is not None
            and self._macd_signal_line is not None
            and self._macd_line > self._macd_signal_line
        ):
            factors["momentum_macd"] = 1

        return factors

    def handle_data(self, context: Any, data: Any) -> Any:  # noqa: ANN401
        """Process bar data and execute orders based on signals.

        Uses rustybt's real APIs:
        - data.history() for all indicator calculations
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
            self._ema = self._calculate_ema_from_history(data)
            self._rsi = self._calculate_rsi_from_history(data)
            self._macd_line, self._macd_signal_line = self._calculate_macd_from_history(data)
            return None

        # After warmup, proceed with normal logging and trading
        super().handle_data(context, data)

        # Calculate all indicators using rustybt's data.history()
        self._ema = self._calculate_ema_from_history(data)
        self._rsi = self._calculate_rsi_from_history(data)
        self._macd_line, self._macd_signal_line = self._calculate_macd_from_history(data)

        # Compute factors
        factors = self.compute_factors(current_price)
        total_score = sum(factors.values())

        # Log factors computed event (Layer 2)
        self._log_event(
            layer="signals",
            event="factors_computed",
            data={
                "price": current_price,
                "ema_50": self._ema,
                "rsi": self._rsi,
                "macd": self._macd_line,
                "macd_signal": self._macd_signal_line,
                "factors": factors,
                "total_score": total_score,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Determine signal
        signal = self._compute_signal(factors)

        # Log the signal (Layer 2)
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=self._asset_str,
            factors=factors,
            total_score=total_score,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Log signal_generated event
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "price": current_price,
                "ema_50": self._ema,
                "rsi": self._rsi,
                "macd": self._macd_line,
                "macd_signal": self._macd_signal_line,
                "factors": factors,
                "total_score": total_score,
                "signal": signal,
            },
            asset=self._asset_str,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute based on signal using rustybt's order API
        order_result = self._execute_signal(context, signal, current_price, factors)

        # Update portfolio tracking (Layer 4 & 5)
        self._update_portfolio_metrics(context, current_price)

        return order_result

    def _compute_signal(self, factors: dict[str, int] | None = None) -> str:
        """Compute trading signal based on factor alignment.

        Parameters
        ----------
        factors : dict[str, int] | None, optional
            Factor scores. If None, computes from indicators (for testing).

        Returns
        -------
        str
            Signal: "BUY", "SELL", or "HOLD".
        """
        # Compute factors if not provided (for testing)
        if factors is None:
            if hasattr(self, "_test_price_buffer") and self._test_price_buffer:
                current_price = self._test_price_buffer[-1]
                factors = self.compute_factors(current_price)
            else:
                return "HOLD"

        total_score = sum(factors.values())

        # Entry: all factors must be bullish (score = 3)
        if total_score == 3 and self._position_state == 0:
            return "BUY"

        # Exit conditions when in position
        if self._position_state == 1:
            # Emergency exit: RSI > 80 (overbought)
            if self._rsi is not None and self._rsi > 80:
                return "SELL"

            # Factor failure exit: any factor drops to 0
            if total_score < 3:
                return "SELL"

        return "HOLD"

    def _execute_signal(
        self,
        context: Any,  # noqa: ANN401
        signal: str,
        current_price: float,
        factors: dict[str, int],
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
        factors : dict[str, int]
            Factor scores.

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
                factors=factors,
                total_score=sum(factors.values()),
            )

            order_id = order_target_percent(self._asset, self._target_percent)
            self._position_state = 1

            self.log_transaction(
                asset=asset_name,
                quantity=self._target_percent,
                price=current_price,
                commission=1.0,
                slippage=0.0,
            )

            return order_id

        elif signal == "SELL" and self._position_state == 1:
            # Determine exit reason
            exit_reason = "factor_failure"
            if self._rsi is not None and self._rsi > 80:
                exit_reason = "rsi_overbought"

            self.log_order_created(
                order_type="market",
                asset=asset_name,
                quantity=-self._target_percent,
                simulation_timestamp=self._current_simulation_timestamp,
                target_percent=0.0,
                exit_reason=exit_reason,
                rsi=self._rsi,
                factors=factors,
            )

            order_id = order_target_percent(self._asset, 0.0)
            self._position_state = 0

            self.log_transaction(
                asset=asset_name,
                quantity=-self._target_percent,
                price=current_price,
                commission=1.0,
                slippage=0.0,
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
    def ema(self) -> float | None:
        """Get current EMA value."""
        return self._ema

    @property
    def rsi(self) -> float | None:
        """Get current RSI value."""
        return self._rsi

    @property
    def macd_line(self) -> float | None:
        """Get current MACD line value."""
        return self._macd_line

    @property
    def macd_signal_line(self) -> float | None:
        """Get current MACD signal line value."""
        return self._macd_signal_line

    @property
    def position(self) -> int:
        """Get current position (0 = flat, 1 = long)."""
        return self._position_state

    @position.setter
    def position(self, value: int) -> None:
        """Set current position (for testing)."""
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

        # Add price to buffer
        self._test_price_buffer.append(price)

        # Calculate EMA
        if len(self._test_price_buffer) >= self._ema_period:
            # Simple EMA calculation using multiplier
            multiplier = 2 / (self._ema_period + 1)
            if self._ema is None:
                # Initialize with SMA
                self._ema = sum(self._test_price_buffer[: self._ema_period]) / self._ema_period
            else:
                self._ema = (price - self._ema) * multiplier + self._ema
        else:
            self._ema = None

        # Calculate RSI
        if len(self._test_price_buffer) > self._rsi_period:
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

            recent_gains = gains[-self._rsi_period :]
            recent_losses = losses[-self._rsi_period :]

            avg_gain = sum(recent_gains) / self._rsi_period
            avg_loss = sum(recent_losses) / self._rsi_period

            if avg_loss == 0:
                self._rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                self._rsi = 100 - (100 / (1 + rs))
        else:
            self._rsi = None

        # Calculate MACD
        if len(self._test_price_buffer) >= self._macd_slow:
            # Calculate fast EMA
            fast_mult = 2 / (self._macd_fast + 1)
            if not hasattr(self, "_test_fast_ema"):
                self._test_fast_ema = (
                    sum(self._test_price_buffer[: self._macd_fast]) / self._macd_fast
                )
            else:
                self._test_fast_ema = (
                    price - self._test_fast_ema
                ) * fast_mult + self._test_fast_ema

            # Calculate slow EMA
            slow_mult = 2 / (self._macd_slow + 1)
            if not hasattr(self, "_test_slow_ema"):
                self._test_slow_ema = (
                    sum(self._test_price_buffer[: self._macd_slow]) / self._macd_slow
                )
            else:
                self._test_slow_ema = (
                    price - self._test_slow_ema
                ) * slow_mult + self._test_slow_ema

            # MACD line
            self._macd_line = self._test_fast_ema - self._test_slow_ema

            # Signal line (EMA of MACD)
            if not hasattr(self, "_test_macd_history"):
                self._test_macd_history: list[float] = []
            self._test_macd_history.append(self._macd_line)

            if len(self._test_macd_history) >= self._macd_signal_period:
                signal_mult = 2 / (self._macd_signal_period + 1)
                if self._macd_signal_line is None:
                    self._macd_signal_line = (
                        sum(self._test_macd_history[: self._macd_signal_period])
                        / self._macd_signal_period
                    )
                else:
                    self._macd_signal_line = (
                        self._macd_line - self._macd_signal_line
                    ) * signal_mult + self._macd_signal_line
        else:
            self._macd_line = None
            self._macd_signal_line = None
