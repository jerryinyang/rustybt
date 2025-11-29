"""Multi-Factor strategy combining EMA + RSI + MACD for rustybt validation.

This module implements a Multi-Factor strategy that:
1. Extends RustyBTValidatedStrategy
2. Implements three indicators: EMA(50), RSI(14), MACD(12,26,9)
3. Each factor returns a score of 1 (bullish) or 0 (not bullish)
4. Entry requires all 3 factors = 1 (total score = 3)
5. Exit when any factor drops to 0 OR RSI > 80 (overbought emergency exit)
6. Logs individual factor values and scores for comparison

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
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy
from rustybt.validation.decorators import log_order, log_signal


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

    Attributes
    ----------
    _prices : deque
        Rolling window of prices for indicator calculations.
    _ema : float | None
        Current EMA value.
    _rsi : float | None
        Current RSI value.
    _macd_line : float | None
        Current MACD line value.
    _macd_signal_line : float | None
        Current MACD signal line value.
    _position : int
        Current position: 0 = no position, 1 = long.
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

        # Price history - need enough for slowest indicator (EMA 50)
        max_period = max(ema_period, rsi_period + 1, macd_slow + macd_signal)
        self._prices: deque[float] = deque(maxlen=max_period)

        # MACD history for signal line calculation
        self._macd_history: deque[float] = deque(maxlen=macd_signal)

        # Indicator values
        self._ema: float | None = None
        self._rsi: float | None = None
        self._macd_line: float | None = None
        self._macd_signal_line: float | None = None

        # RSI calculation state
        self._prev_avg_gain: float = 0.0
        self._prev_avg_loss: float = 0.0
        self._rsi_initialized: bool = False

        # EMA state for fast/slow EMAs
        self._fast_ema: float | None = None
        self._slow_ema: float | None = None

        # Position tracking
        self._position: int = 0  # 0 = flat, 1 = long

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

    def compute_ema(self, prices: list[float], period: int) -> float | None:
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

    def _calculate_ema_50(self) -> float | None:
        """Calculate 50-period EMA.

        Returns
        -------
        float | None
            EMA value, or None if insufficient data.
        """
        prices_list = list(self._prices)
        return self.compute_ema(prices_list, self._ema_period)

    def _calculate_rsi(self) -> float | None:
        """Calculate Relative Strength Index using simple average method.

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

        # Calculate average gain and loss (simple average)
        avg_gain = sum(gains) / self._rsi_period
        avg_loss = sum(losses) / self._rsi_period

        # Handle division by zero
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(self) -> tuple[float | None, float | None]:
        """Calculate MACD line and signal line.

        Returns
        -------
        tuple[float | None, float | None]
            (MACD line, Signal line), or (None, None) if insufficient data.
        """
        prices_list = list(self._prices)

        # Need enough data for slow EMA
        if len(prices_list) < self._macd_slow:
            return None, None

        # Calculate fast and slow EMAs
        fast_ema = self.compute_ema(prices_list, self._macd_fast)
        slow_ema = self.compute_ema(prices_list, self._macd_slow)

        if fast_ema is None or slow_ema is None:
            return None, None

        # MACD line = Fast EMA - Slow EMA
        macd_line = fast_ema - slow_ema

        # Add to MACD history for signal line calculation
        self._macd_history.append(macd_line)

        # Signal line = EMA of MACD line
        if len(self._macd_history) < self._macd_signal_period:
            return macd_line, None

        macd_list = list(self._macd_history)
        signal_line = self.compute_ema(macd_list, self._macd_signal_period)

        return macd_line, signal_line

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

    def _log_factors(
        self, price: float, factors: dict[str, int], asset: str | None = None
    ) -> None:
        """Log factor values and scores.

        Parameters
        ----------
        price : float
            Current price.
        factors : dict[str, int]
            Factor scores.
        asset : str | None, optional
            Asset symbol, by default None.
        """
        self._log_event(
            layer="signals",
            event="factors_computed",
            data={
                "price": price,
                "ema_50": self._ema,
                "rsi": self._rsi,
                "macd": self._macd_line,
                "macd_signal": self._macd_signal_line,
                "factors": factors,
                "total_score": sum(factors.values()),
            },
            asset=asset,
        )

    @log_signal()
    def compute_signal(self, price: float, asset: str | None = None) -> str:
        """Compute trading signal based on factor alignment.

        Parameters
        ----------
        price : float
            Current price.
        asset : str | None, optional
            Asset symbol, by default None.

        Returns
        -------
        str
            Signal: "BUY", "SELL", or "HOLD".
        """
        self._asset = asset

        # Add price to history
        self._prices.append(price)

        # Calculate indicators
        self._ema = self._calculate_ema_50()
        self._rsi = self._calculate_rsi()
        self._macd_line, self._macd_signal_line = self._calculate_macd()

        # Compute factors
        factors = self.compute_factors(price)
        total_score = sum(factors.values())

        # Log factors for comparison
        self._log_factors(price, factors, asset)

        # Entry: all factors must be bullish (score = 3)
        if total_score == 3 and self._position == 0:
            return "BUY"

        # Exit conditions when in position
        if self._position == 1:
            # Emergency exit: RSI > 80 (overbought)
            if self._rsi is not None and self._rsi > 80:
                return "SELL"

            # Factor failure exit: any factor drops to 0
            if total_score < 3:
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
        factors = self.compute_factors(price)
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "price": price,
                "ema_50": self._ema,
                "rsi": self._rsi,
                "macd": self._macd_line,
                "macd_signal": self._macd_signal_line,
                "factors": factors,
                "total_score": sum(factors.values()),
                "signal": signal,
            },
            asset=asset,
        )

        # Execute based on signal
        order = None

        if signal == "BUY" and self._position == 0:
            # Enter long position
            order = self._create_order(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self._target_percent,
                side="buy",
            )
            self._position = 1
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self._target_percent,
                target_percent=self._target_percent,
                factors=factors,
                total_score=sum(factors.values()),
            )

        elif signal == "SELL" and self._position == 1:
            # Determine exit reason
            exit_reason = "factor_failure"
            if self._rsi is not None and self._rsi > 80:
                exit_reason = "rsi_overbought"

            # Exit long position
            order = self._create_order(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self._target_percent,
                side="sell",
            )
            self._position = 0
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self._target_percent,
                target_percent=0.0,
                exit_reason=exit_reason,
                rsi=self._rsi,
                factors=factors,
            )

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
        return self._position

    @position.setter
    def position(self, value: int) -> None:
        """Set current position (for testing)."""
        self._position = value
