"""Mean Reversion strategy for rustybt validation.

This module implements a Z-score based Mean Reversion strategy that:
1. Extends RustyBTValidatedStrategy
2. Uses rolling window for mean/std calculation
3. Generates BUY signal when z-score < -2 (oversold)
4. Generates SELL signal when z-score > 2 (overbought)
5. Generates EXIT signal when z-score returns to 0
6. Logs events to JSONL for comparison with Backtrader

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
from collections import deque
from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy
from rustybt.validation.decorators import log_order, log_signal


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

    Attributes
    ----------
    _prices : deque
        Rolling window of prices for z-score calculation.
    _current_mean : float | None
        Current rolling mean.
    _current_std : float | None
        Current rolling standard deviation.
    _current_zscore : float | None
        Current z-score value.
    _position : int
        Current position: -1 = short, 0 = flat, 1 = long.
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

        # Price history for z-score calculation
        self._prices: deque[float] = deque(maxlen=lookback_period)

        # Current statistics
        self._current_mean: float | None = None
        self._current_std: float | None = None
        self._current_zscore: float | None = None

        # Position tracking: -1 = short, 0 = flat, 1 = long
        self._position: int = 0

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
            event="mean_reversion_init",
            data={
                "lookback_period": self._lookback_period,
                "entry_threshold": self._entry_threshold,
                "exit_threshold": self._exit_threshold,
                "target_percent": self._target_percent,
            },
        )

    def _calculate_statistics(self) -> tuple[float | None, float | None]:
        """Calculate rolling mean and standard deviation.

        Returns
        -------
        tuple[float | None, float | None]
            (mean, std_dev) or (None, None) if insufficient data.
        """
        if len(self._prices) < self._lookback_period:
            return None, None

        prices_list = list(self._prices)
        n = len(prices_list)

        # Calculate mean
        mean = sum(prices_list) / n

        # Calculate population standard deviation
        variance = sum((p - mean) ** 2 for p in prices_list) / n
        std_dev = math.sqrt(variance)

        return mean, std_dev

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
        mean, std_dev = self._calculate_statistics()

        if mean is None or std_dev is None:
            return None

        # Handle division by zero (no variance in prices)
        if std_dev == 0:
            return 0.0

        z_score = (price - mean) / std_dev

        # Handle NaN/Inf
        if math.isnan(z_score) or math.isinf(z_score):
            return 0.0

        return z_score

    @log_signal()
    def compute_signal(self, price: float, asset: str | None = None) -> str:
        """Compute trading signal based on z-score mean reversion.

        Parameters
        ----------
        price : float
            Current price.
        asset : str | None, optional
            Asset symbol, by default None.

        Returns
        -------
        str
            Signal: "BUY", "SELL", "EXIT_LONG", "EXIT_SHORT", or "HOLD".
        """
        self._asset = asset

        # Add price to history
        self._prices.append(price)

        # Calculate statistics
        self._current_mean, self._current_std = self._calculate_statistics()

        # Calculate z-score
        self._current_zscore = self._calculate_zscore(price)

        # Log z-score computation
        self._log_event(
            layer="signals",
            event="zscore_computed",
            data={
                "price": price,
                "mean": self._current_mean,
                "std_dev": self._current_std,
                "z_score": self._current_zscore,
            },
            asset=asset,
        )

        # Can't generate signal without z-score
        if self._current_zscore is None:
            return "HOLD"

        # Check exit conditions first (if in position)
        if self._position == 1:  # Long position
            # Exit long when z-score returns to mean
            if abs(self._current_zscore) <= self._exit_threshold:
                return "EXIT_LONG"

        if self._position == -1:  # Short position
            # Exit short when z-score returns to mean
            if abs(self._current_zscore) <= self._exit_threshold:
                return "EXIT_SHORT"

        # Check entry conditions (if flat)
        if self._position == 0:
            # Oversold: price significantly below mean -> BUY
            if self._current_zscore < -self._entry_threshold:
                return "BUY"

            # Overbought: price significantly above mean -> SELL (short)
            if self._current_zscore > self._entry_threshold:
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
                "mean": self._current_mean,
                "std_dev": self._current_std,
                "z_score": self._current_zscore,
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
                z_score=self._current_zscore,
            )

        elif signal == "SELL" and self._position == 0:
            # Enter short position
            order = self._create_order(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self._target_percent,
                side="sell",
            )
            self._position = -1
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self._target_percent,
                target_percent=-self._target_percent,
                z_score=self._current_zscore,
            )

        elif signal == "EXIT_LONG" and self._position == 1:
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
                z_score=self._current_zscore,
            )

        elif signal == "EXIT_SHORT" and self._position == -1:
            # Exit short position
            order = self._create_order(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self._target_percent,
                side="buy",
            )
            self._position = 0
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self._target_percent,
                target_percent=0.0,
                z_score=self._current_zscore,
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
        return self._position
