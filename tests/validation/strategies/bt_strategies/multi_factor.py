"""Multi-Factor strategy combining EMA + RSI + MACD for Backtrader validation.

This module implements a Multi-Factor strategy that:
1. Extends BacktraderValidatedStrategy
2. Uses bt.indicators for EMA, RSI, and MACD
3. Each factor returns a score of 1 (bullish) or 0 (not bullish)
4. Entry requires all 3 factors = 1 (total score = 3)
5. Exit when any factor drops to 0 OR RSI > 80 (overbought emergency exit)
6. Logs individual factor values and scores for comparison with rustybt

The log format follows the validation framework schema (identical to rustybt):
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

from typing import TYPE_CHECKING

import backtrader as bt

from tests.validation.strategies.bt_strategies.base_validated import (
    BacktraderValidatedStrategy,
)

if TYPE_CHECKING:
    pass


class MultiFactorStrategy(BacktraderValidatedStrategy):
    """Multi-Factor validated strategy for Backtrader with EMA + RSI + MACD.

    This strategy implements a factor-based approach:
    - Three factors must align for entry (trend, RSI momentum, MACD momentum)
    - Exit when any factor fails or RSI exceeds overbought threshold (80)

    The implementation uses Backtrader's built-in indicators but produces
    logs identical in structure to the rustybt implementation.

    Parameters (via params tuple)
    -----------------------------
    log_path : Path | str
        Path to the JSONL log file (inherited from base).
    ema_period : int
        Period for EMA calculation, by default 50.
    rsi_period : int
        Period for RSI calculation, by default 14.
    macd_fast : int
        Fast period for MACD, by default 12.
    macd_slow : int
        Slow period for MACD, by default 26.
    macd_signal : int
        Signal period for MACD, by default 9.
    target_percent : float
        Target allocation percentage (0-1), by default 1.0 (100%).
    """

    # Backtrader params
    params = (
        ("log_path", None),
        ("ema_period", 50),
        ("rsi_period", 14),
        ("macd_fast", 12),
        ("macd_slow", 26),
        ("macd_signal", 9),
        ("target_percent", 1.0),
    )

    def __init__(self) -> None:
        """Initialize the Multi-Factor strategy with indicators."""
        super().__init__()

        # Create EMA indicator
        self.ema_indicator = bt.indicators.EMA(
            self.data.close,
            period=self.p.ema_period,
        )

        # Create RSI indicator
        self.rsi_indicator = bt.indicators.RSI(
            self.data.close,
            period=self.p.rsi_period,
        )

        # Create MACD indicator
        self.macd_indicator = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal,
        )

        # Position tracking
        self._position_state: int = 0  # 0 = flat, 1 = long

        # Log initialization with parameters
        self._log_event(
            layer="data",
            event="multi_factor_init",
            data={
                "ema_period": self.p.ema_period,
                "rsi_period": self.p.rsi_period,
                "macd_fast": self.p.macd_fast,
                "macd_slow": self.p.macd_slow,
                "macd_signal": self.p.macd_signal,
                "target_percent": self.p.target_percent,
            },
        )

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

        # Ensure we have enough data
        min_period = max(self.p.ema_period, self.p.macd_slow + self.p.macd_signal)
        if len(self.data) < min_period:
            return factors

        # Get indicator values
        ema_value = self.ema_indicator[0]
        rsi_value = self.rsi_indicator[0]
        macd_line = self.macd_indicator.macd[0]
        macd_signal = self.macd_indicator.signal[0]

        # Trend factor: Price > EMA(50)
        if price > ema_value:
            factors["trend"] = 1

        # RSI momentum factor: 50 < RSI < 70
        if 50 < rsi_value < 70:
            factors["momentum_rsi"] = 1

        # MACD momentum factor: MACD > Signal
        if macd_line > macd_signal:
            factors["momentum_macd"] = 1

        return factors

    def _get_indicator_values(self) -> dict[str, float | None]:
        """Get current indicator values.

        Returns
        -------
        dict[str, float | None]
            Dictionary with indicator names and values.
        """
        min_period = max(self.p.ema_period, self.p.macd_slow + self.p.macd_signal)

        if len(self.data) < min_period:
            return {
                "ema_50": None,
                "rsi": None,
                "macd": None,
                "macd_signal": None,
            }

        return {
            "ema_50": self.ema_indicator[0],
            "rsi": self.rsi_indicator[0],
            "macd": self.macd_indicator.macd[0],
            "macd_signal": self.macd_indicator.signal[0],
        }

    def next(self) -> None:
        """Process the current bar, compute signal, and execute orders."""
        # Call base class to log bar_received event
        super().next()

        # Get current values
        current_price = self.data.close[0]

        # Get asset name from data feed
        asset = self.data._name if hasattr(self.data, "_name") else None

        # Get indicator values
        indicators = self._get_indicator_values()

        # Compute factors
        factors = self.compute_factors(current_price)
        total_score = sum(factors.values())

        # Log factors computed event (matches rustybt structure)
        self._log_event(
            layer="signals",
            event="factors_computed",
            data={
                "price": current_price,
                "ema_50": indicators["ema_50"],
                "rsi": indicators["rsi"],
                "macd": indicators["macd"],
                "macd_signal": indicators["macd_signal"],
                "factors": factors,
                "total_score": total_score,
            },
            asset=asset,
        )

        # Determine signal
        signal = self._compute_signal(current_price, factors, indicators)

        # Log the signal
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=asset,
            factors=factors,
            total_score=total_score,
        )

        # Log signal_generated event (matches rustybt structure)
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "price": current_price,
                "ema_50": indicators["ema_50"],
                "rsi": indicators["rsi"],
                "macd": indicators["macd"],
                "macd_signal": indicators["macd_signal"],
                "factors": factors,
                "total_score": total_score,
                "signal": signal,
            },
            asset=asset,
        )

        # Execute based on signal
        self._execute_signal(signal, current_price, factors, indicators, asset)

    def _compute_signal(
        self,
        current_price: float,  # noqa: ARG002
        factors: dict[str, int],
        indicators: dict[str, float | None],
    ) -> str:
        """Compute trading signal based on factor alignment.

        Parameters
        ----------
        current_price : float
            Current price (unused but kept for consistency).
        factors : dict[str, int]
            Factor scores.
        indicators : dict[str, float | None]
            Indicator values.

        Returns
        -------
        str
            Signal: "BUY", "SELL", or "HOLD".
        """
        total_score = sum(factors.values())

        # Entry: all factors must be bullish (score = 3)
        if total_score == 3 and self._position_state == 0:
            return "BUY"

        # Exit conditions when in position
        if self._position_state == 1:
            # Emergency exit: RSI > 80 (overbought)
            rsi = indicators.get("rsi")
            if rsi is not None and rsi > 80:
                return "SELL"

            # Factor failure exit: any factor drops to 0
            if total_score < 3:
                return "SELL"

        return "HOLD"

    def _execute_signal(
        self,
        signal: str,
        current_price: float,  # noqa: ARG002
        factors: dict[str, int],
        indicators: dict[str, float | None],
        asset: str | None,
    ) -> None:
        """Execute order based on signal.

        Parameters
        ----------
        signal : str
            Trading signal.
        current_price : float
            Current price (unused but kept for consistency).
        factors : dict[str, int]
            Factor scores.
        indicators : dict[str, float | None]
            Indicator values.
        asset : str | None
            Asset symbol.
        """
        if signal == "BUY" and self._position_state == 0:
            # Enter long position
            self.order_target_percent(target=self.p.target_percent)
            self._position_state = 1
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self.p.target_percent,
                target_percent=self.p.target_percent,
                factors=factors,
                total_score=sum(factors.values()),
            )

        elif signal == "SELL" and self._position_state == 1:
            # Determine exit reason
            exit_reason = "factor_failure"
            rsi = indicators.get("rsi")
            if rsi is not None and rsi > 80:
                exit_reason = "rsi_overbought"

            # Exit long position
            self.order_target_percent(target=0.0)
            self._position_state = 0
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self.p.target_percent,
                target_percent=0.0,
                exit_reason=exit_reason,
                rsi=rsi,
                factors=factors,
            )

    @property
    def position_state(self) -> int:
        """Get current position state (0 = flat, 1 = long)."""
        return self._position_state

    @position_state.setter
    def position_state(self, value: int) -> None:
        """Set position state (for testing)."""
        self._position_state = value

    @property
    def ema(self) -> float | None:
        """Get current EMA value."""
        if len(self.data) < self.p.ema_period:
            return None
        return self.ema_indicator[0]

    @property
    def rsi(self) -> float | None:
        """Get current RSI value."""
        if len(self.data) < self.p.rsi_period:
            return None
        return self.rsi_indicator[0]

    @property
    def macd_line(self) -> float | None:
        """Get current MACD line value."""
        min_period = self.p.macd_slow + self.p.macd_signal
        if len(self.data) < min_period:
            return None
        return self.macd_indicator.macd[0]

    @property
    def macd_signal_value(self) -> float | None:
        """Get current MACD signal line value."""
        min_period = self.p.macd_slow + self.p.macd_signal
        if len(self.data) < min_period:
            return None
        return self.macd_indicator.signal[0]
