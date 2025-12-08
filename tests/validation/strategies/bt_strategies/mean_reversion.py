"""Mean Reversion strategy for Backtrader validation.

This module implements a Z-score based Mean Reversion strategy that:
1. Extends BacktraderValidatedStrategy
2. Uses rolling window for mean/std calculation
3. Generates BUY signal when z-score < -2 (oversold)
4. Generates SELL signal when z-score > 2 (overbought)
5. Generates EXIT signal when z-score returns to 0
6. Logs events to JSONL for comparison with rustybt

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

import math
from typing import TYPE_CHECKING

import backtrader as bt

from tests.validation.strategies.bt_strategies.base_validated import (
    BacktraderValidatedStrategy,
)

if TYPE_CHECKING:
    pass


class MeanReversionStrategy(BacktraderValidatedStrategy):
    """Mean Reversion validated strategy for Backtrader using z-score.

    This strategy implements a classic mean reversion approach:
    - BUY when z-score < -entry_threshold (price significantly below mean)
    - SELL when z-score > +entry_threshold (price significantly above mean)
    - EXIT when |z-score| < exit_threshold (mean reversion complete)

    The implementation uses Backtrader's built-in indicators for calculation
    but produces logs identical in structure to the rustybt implementation.

    Parameters (via params tuple)
    -----------------------------
    log_path : Path | str
        Path to the JSONL log file (inherited from base).
    lookback_period : int
        Number of periods for rolling mean/std calculation, by default 20.
    entry_threshold : float
        Z-score threshold for entry signals (absolute value), by default 2.0.
    exit_threshold : float
        Z-score threshold for exit signals (absolute value), by default 0.0.
    target_percent : float
        Target allocation percentage (0-1), by default 1.0 (100%).
    """

    # Backtrader params
    params = (
        ("log_path", None),
        ("lookback_period", 20),
        ("entry_threshold", 2.0),
        ("exit_threshold", 0.0),
        ("target_percent", 1.0),
    )

    def __init__(self) -> None:
        """Initialize the Mean Reversion strategy with indicators."""
        super().__init__()

        # Create indicators for rolling statistics
        self.sma = bt.indicators.SMA(self.data.close, period=self.p.lookback_period)
        self.std = bt.indicators.StdDev(self.data.close, period=self.p.lookback_period)

        # Track position state: -1 = short, 0 = flat, 1 = long
        self._position_state: int = 0

        # Log initialization with parameters
        self._log_event(
            layer="data",
            event="mean_reversion_init",
            data={
                "lookback_period": self.p.lookback_period,
                "entry_threshold": self.p.entry_threshold,
                "exit_threshold": self.p.exit_threshold,
                "target_percent": self.p.target_percent,
            },
        )

    def _calculate_zscore(self) -> float | None:
        """Calculate z-score for the current bar.

        Returns
        -------
        float | None
            Z-score value, or None if std_dev is 0 or not available.
        """
        # Check if we have enough data
        if len(self.data) < self.p.lookback_period:
            return None

        current_price = self.data.close[0]
        mean = self.sma[0]
        std_dev = self.std[0]

        # Handle division by zero
        if std_dev == 0 or math.isnan(std_dev):
            return 0.0

        z_score = (current_price - mean) / std_dev

        # Handle NaN/Inf
        if math.isnan(z_score) or math.isinf(z_score):
            return 0.0

        return z_score

    def next(self) -> None:
        """Process the current bar, compute z-score signal, and execute orders."""
        # Call base class to log bar_received event
        super().next()

        # Get current values
        current_price = self.data.close[0]
        mean = self.sma[0] if len(self.data) >= self.p.lookback_period else None
        std_dev = self.std[0] if len(self.data) >= self.p.lookback_period else None

        # Calculate z-score
        z_score = self._calculate_zscore()

        # Get asset name from data feed
        asset = self.data._name if hasattr(self.data, "_name") else None

        # Log z-score computation (matches rustybt structure)
        self._log_event(
            layer="signals",
            event="zscore_computed",
            data={
                "price": current_price,
                "mean": mean,
                "std_dev": std_dev,
                "z_score": z_score,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Determine signal
        signal = self._compute_signal(z_score)

        # Log the signal (matches rustybt structure)
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=asset,
            z_score=z_score,
            mean=mean,
            std_dev=std_dev,
        )

        # Log signal_generated event (matches rustybt structure)
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "price": current_price,
                "mean": mean,
                "std_dev": std_dev,
                "z_score": z_score,
                "signal": signal,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute based on signal
        self._execute_signal(signal, z_score, asset)

    def _compute_signal(self, z_score: float | None) -> str:
        """Compute trading signal based on z-score.

        Parameters
        ----------
        z_score : float | None
            Current z-score value.

        Returns
        -------
        str
            Signal: "BUY", "SELL", "EXIT_LONG", "EXIT_SHORT", or "HOLD".
        """
        if z_score is None:
            return "HOLD"

        # Check exit conditions first (if in position)
        if self._position_state == 1:  # Long position
            if abs(z_score) <= self.p.exit_threshold:
                return "EXIT_LONG"

        if self._position_state == -1:  # Short position
            if abs(z_score) <= self.p.exit_threshold:
                return "EXIT_SHORT"

        # Check entry conditions (if flat)
        if self._position_state == 0:
            # Oversold: z-score significantly negative -> BUY
            if z_score < -self.p.entry_threshold:
                return "BUY"

            # Overbought: z-score significantly positive -> SELL
            if z_score > self.p.entry_threshold:
                return "SELL"

        return "HOLD"

    def _execute_signal(self, signal: str, z_score: float | None, asset: str | None) -> None:
        """Execute order based on signal.

        Parameters
        ----------
        signal : str
            Trading signal.
        z_score : float | None
            Current z-score value.
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
                z_score=z_score,
            )
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={"position_state": "LONG", "target_percent": self.p.target_percent},
                asset=asset,
                simulation_timestamp=self._current_simulation_timestamp,
            )

        elif signal == "SELL" and self._position_state == 0:
            # Enter short position
            self.order_target_percent(target=-self.p.target_percent)
            self._position_state = -1
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self.p.target_percent,
                target_percent=-self.p.target_percent,
                z_score=z_score,
            )
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={"position_state": "SHORT", "target_percent": -self.p.target_percent},
                asset=asset,
                simulation_timestamp=self._current_simulation_timestamp,
            )

        elif signal == "EXIT_LONG" and self._position_state == 1:
            # Exit long position
            self.order_target_percent(target=0.0)
            self._position_state = 0
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self.p.target_percent,
                target_percent=0.0,
                z_score=z_score,
            )
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={"position_state": "FLAT", "target_percent": 0.0},
                asset=asset,
                simulation_timestamp=self._current_simulation_timestamp,
            )

        elif signal == "EXIT_SHORT" and self._position_state == -1:
            # Exit short position
            self.order_target_percent(target=0.0)
            self._position_state = 0
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self.p.target_percent,
                target_percent=0.0,
                z_score=z_score,
            )
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={"position_state": "FLAT", "target_percent": 0.0},
                asset=asset,
                simulation_timestamp=self._current_simulation_timestamp,
            )

    @property
    def position_state(self) -> int:
        """Get current position state (-1 = short, 0 = flat, 1 = long)."""
        return self._position_state
