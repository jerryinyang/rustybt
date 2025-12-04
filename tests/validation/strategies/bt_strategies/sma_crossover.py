"""SMA Crossover strategy for Backtrader validation.

This module implements a Simple Moving Average Crossover strategy that:
1. Extends BacktraderValidatedStrategy
2. Uses bt.indicators.SMA for indicator calculation
3. Uses bt.indicators.CrossOver for crossover detection
4. Generates BUY signal when fast crosses above slow
5. Generates SELL signal when fast crosses below slow
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

from typing import TYPE_CHECKING

import backtrader as bt

from tests.validation.strategies.bt_strategies.base_validated import (
    BacktraderValidatedStrategy,
)

if TYPE_CHECKING:
    pass


class SMACrossoverStrategy(BacktraderValidatedStrategy):
    """SMA Crossover validated strategy for Backtrader.

    This strategy implements a classic dual Simple Moving Average crossover:
    - BUY when fast SMA crosses above slow SMA (golden cross)
    - SELL when fast SMA crosses below slow SMA (death cross)

    The implementation uses Backtrader's built-in indicators for calculation
    but produces logs identical in structure to the rustybt implementation.

    Parameters (via params tuple)
    -----------------------------
    log_path : Path | str
        Path to the JSONL log file (inherited from base).
    fast_period : int
        Period for fast SMA, by default 10.
    slow_period : int
        Period for slow SMA, by default 30.
    target_percent : float
        Target allocation percentage (0-1), by default 0.98 (98%).
        Using 98% provides consistency with rustybt's buffer for price movements.
    """

    # Backtrader params - log_path inherited, plus strategy-specific params
    params = (
        ("log_path", None),
        ("fast_period", 10),
        ("slow_period", 30),
        ("target_percent", 0.98),
    )

    def __init__(self) -> None:
        """Initialize the SMA Crossover strategy with indicators."""
        super().__init__()

        # Create SMA indicators using Backtrader's built-in
        self.fast_sma = bt.indicators.SMA(
            self.data.close,
            period=self.p.fast_period,
        )
        self.slow_sma = bt.indicators.SMA(
            self.data.close,
            period=self.p.slow_period,
        )

        # CrossOver indicator: positive = fast crosses above slow
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)

        # Track position state for comparison (matches rustybt logic)
        self._position_state: int = 0  # 0 = flat, 1 = long

        # Log initialization with parameters
        self._log_event(
            layer="data",
            event="sma_init",
            data={
                "fast_period": self.p.fast_period,
                "slow_period": self.p.slow_period,
                "target_percent": self.p.target_percent,
            },
        )

    def next(self) -> None:
        """Process the current bar, compute signal, and execute orders."""
        # Call base class to log bar_received event
        super().next()

        # Get current values
        current_price = self.data.close[0]
        fast_sma_value = self.fast_sma[0]
        slow_sma_value = self.slow_sma[0]
        crossover_value = self.crossover[0]

        # Get asset name from data feed
        asset = self.data._name if hasattr(self.data, "_name") else None

        # Log indicator values (matches rustybt structure)
        self._log_event(
            layer="signals",
            event="indicator_values",
            data={
                "fast_sma": fast_sma_value,
                "slow_sma": slow_sma_value,
                "price": current_price,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Determine signal based on crossover
        # CrossOver indicator: > 0 means fast crossed above slow (BUY)
        #                      < 0 means fast crossed below slow (SELL)
        if crossover_value > 0:
            signal = "BUY"
        elif crossover_value < 0:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Log the signal (matches rustybt structure)
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=asset,
            fast_sma=fast_sma_value,
            slow_sma=slow_sma_value,
        )

        # Log signal_generated event (matches rustybt structure)
        self._log_event(
            layer="signals",
            event="signal_generated",
            data={
                "fast_sma": fast_sma_value,
                "slow_sma": slow_sma_value,
                "signal": signal,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute based on signal
        # BUY only if no position (matches rustybt logic)
        if signal == "BUY" and self._position_state == 0:
            # Calculate actual share count that will be bought
            # This matches rustybt's calculation for parity
            portfolio_value = self.broker.getvalue()
            target_value = portfolio_value * self.p.target_percent
            shares_to_buy = int(target_value / current_price)

            # In Backtrader, use order_target_percent for percentage orders
            order = self.order_target_percent(target=self.p.target_percent)
            self._position_state = 1

            # Log order creation with actual share count (matches rustybt)
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=shares_to_buy,
                target_percent=self.p.target_percent,
            )

        # SELL only if has position (matches rustybt logic)
        elif signal == "SELL" and self._position_state == 1:
            # Get actual shares held to sell
            shares_to_sell = abs(self.position.size)

            # Exit position completely
            order = self.order_target_percent(target=0.0)
            self._position_state = 0

            # Log order creation with actual share count (matches rustybt)
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-shares_to_sell,
                target_percent=0.0,
            )

    @property
    def position_state(self) -> int:
        """Get current position state (0 = flat, 1 = long)."""
        return self._position_state
