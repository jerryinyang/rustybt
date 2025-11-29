"""SMA Crossover strategy for rustybt validation.

This module implements a Simple Moving Average Crossover strategy that:
1. Extends RustyBTValidatedStrategy
2. Uses fast SMA (10-period) and slow SMA (30-period)
3. Generates BUY signal when fast crosses above slow
4. Generates SELL signal when fast crosses below slow
5. Logs events to JSONL for comparison with Backtrader

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

from collections import deque
from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy
from rustybt.validation.decorators import log_signal


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
        Target allocation percentage (0-1), by default 1.0 (100%).

    Attributes
    ----------
    _prices : deque
        Rolling window of prices for SMA calculation.
    _fast_sma : float | None
        Current fast SMA value.
    _slow_sma : float | None
        Current slow SMA value.
    _prev_fast_sma : float | None
        Previous fast SMA value (for crossover detection).
    _prev_slow_sma : float | None
        Previous slow SMA value (for crossover detection).
    _position : int
        Current position: 0 = no position, 1 = long.
    """

    def __init__(
        self,
        log_path: Path,
        fast_period: int = 10,
        slow_period: int = 30,
        target_percent: float = 1.0,
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
            Target allocation percentage (0-1), by default 1.0.
        """
        super().__init__(log_path)
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._target_percent = target_percent

        # Price history for SMA calculation
        self._prices: deque[float] = deque(maxlen=slow_period)

        # SMA values
        self._fast_sma: float | None = None
        self._slow_sma: float | None = None
        self._prev_fast_sma: float | None = None
        self._prev_slow_sma: float | None = None

        # Position tracking
        self._position: int = 0  # 0 = flat, 1 = long

        # Asset reference (set during handle_data)
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
            event="sma_init",
            data={
                "fast_period": self._fast_period,
                "slow_period": self._slow_period,
                "target_percent": self._target_percent,
            },
        )

    def _calculate_sma(self, period: int) -> float | None:
        """Calculate Simple Moving Average for the given period.

        Parameters
        ----------
        period : int
            Number of periods for the SMA.

        Returns
        -------
        float | None
            SMA value, or None if insufficient data.
        """
        if len(self._prices) < period:
            return None
        # Get the last 'period' prices from the deque
        prices_list = list(self._prices)
        return sum(prices_list[-period:]) / period

    @log_signal()
    def compute_signal(self, price: float, asset: str | None = None) -> str:
        """Compute trading signal based on SMA crossover.

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

        # Store previous values for crossover detection
        self._prev_fast_sma = self._fast_sma
        self._prev_slow_sma = self._slow_sma

        # Calculate current SMAs
        self._fast_sma = self._calculate_sma(self._fast_period)
        self._slow_sma = self._calculate_sma(self._slow_period)

        # Log indicator values
        self._log_event(
            layer="signals",
            event="indicator_values",
            data={
                "fast_sma": self._fast_sma,
                "slow_sma": self._slow_sma,
                "price": price,
            },
            asset=asset,
        )

        # Can't generate signal without both SMAs
        if self._fast_sma is None or self._slow_sma is None:
            return "HOLD"

        # Can't detect crossover without previous values
        if self._prev_fast_sma is None or self._prev_slow_sma is None:
            return "HOLD"

        # Detect crossover
        # BUY: fast crosses ABOVE slow (golden cross)
        if (
            self._prev_fast_sma <= self._prev_slow_sma
            and self._fast_sma > self._slow_sma
        ):
            return "BUY"

        # SELL: fast crosses BELOW slow (death cross)
        if (
            self._prev_fast_sma >= self._prev_slow_sma
            and self._fast_sma < self._slow_sma
        ):
            return "SELL"

        return "HOLD"

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
        # Support various data formats
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
                "fast_sma": self._fast_sma,
                "slow_sma": self._slow_sma,
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
            )

        elif signal == "SELL" and self._position == 1:
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
    def fast_sma(self) -> float | None:
        """Get current fast SMA value."""
        return self._fast_sma

    @property
    def slow_sma(self) -> float | None:
        """Get current slow SMA value."""
        return self._slow_sma

    @property
    def position(self) -> int:
        """Get current position (0 = flat, 1 = long)."""
        return self._position
