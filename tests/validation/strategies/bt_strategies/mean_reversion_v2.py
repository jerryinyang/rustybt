"""Mean Reversion V2 strategy for Backtrader validation.

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
from typing import TYPE_CHECKING, Any

import backtrader as bt

from tests.validation.strategies.bt_strategies.base_validated import (
    BacktraderValidatedStrategy,
)

if TYPE_CHECKING:
    pass


class MeanReversionV2Strategy(BacktraderValidatedStrategy):
    """Mean Reversion V2 strategy with limit entries and stop-loss/take-profit exits.

    This strategy implements mean reversion with professional risk management:
    - Limit entries: Enter at favorable prices (0.5% better than current)
    - Stop-loss: Exit if loss exceeds threshold (3% default)
    - Take-profit: Lock in gains when target reached (6% default)
    - Mean reversion exit: Exit when z-score normalizes

    Parameters (via params tuple)
    -----------------------------
    log_path : Path | str
        Path to the JSONL log file (inherited from base).
    lookback_period : int
        Number of periods for rolling mean/std calculation, by default 20.
    z_entry : float
        Z-score threshold for entry signals (absolute value), by default 2.0.
    z_exit : float
        Z-score threshold for exit on mean reversion, by default 0.5.
    stop_loss_pct : float
        Stop-loss percentage (0-1), by default 0.03 (3%).
    take_profit_pct : float
        Take-profit percentage (0-1), by default 0.06 (6%).
    limit_offset_pct : float
        Limit order offset from current price (0-1), by default 0.005 (0.5%).
    shares_per_trade : int
        Number of shares per trade, by default 100.
    """

    # Backtrader params
    params = (
        ("log_path", None),
        ("lookback_period", 20),
        ("z_entry", 2.0),
        ("z_exit", 0.5),
        ("stop_loss_pct", 0.03),
        ("take_profit_pct", 0.06),
        ("limit_offset_pct", 0.005),
        ("shares_per_trade", 100),
    )

    def __init__(self) -> None:
        """Initialize the Mean Reversion V2 strategy with indicators."""
        super().__init__()

        # Create indicators for rolling statistics
        self.sma = bt.indicators.SMA(self.data.close, period=self.p.lookback_period)
        self.std = bt.indicators.StdDev(self.data.close, period=self.p.lookback_period)

        # Track position state: -1 = short, 0 = flat, 1 = long
        self._position_state: int = 0

        # Entry price tracking for stop-loss/take-profit
        self._entry_price: float | None = None

        # Log initialization with parameters
        self._log_event(
            layer="data",
            event="mean_reversion_v2_init",
            data={
                "lookback_period": self.p.lookback_period,
                "z_entry": self.p.z_entry,
                "z_exit": self.p.z_exit,
                "stop_loss_pct": self.p.stop_loss_pct,
                "take_profit_pct": self.p.take_profit_pct,
                "limit_offset_pct": self.p.limit_offset_pct,
                "shares_per_trade": self.p.shares_per_trade,
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
        signal, signal_details = self._compute_signal(z_score, current_price)

        # Log the signal (matches rustybt structure)
        self.log_signal(
            signal_name="compute_signal",
            signal_value=signal,
            asset=asset,
            z_score=z_score,
            mean=mean,
            std_dev=std_dev,
            **signal_details,
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
                **signal_details,
            },
            asset=asset,
            simulation_timestamp=self._current_simulation_timestamp,
        )

        # Execute based on signal
        self._execute_signal(signal, z_score, current_price, signal_details, asset)

    def _compute_signal(
        self, z_score: float | None, current_price: float
    ) -> tuple[str, dict[str, Any]]:
        """Compute trading signal based on z-score with stop-loss/take-profit.

        Parameters
        ----------
        z_score : float | None
            Current z-score value.
        current_price : float
            Current market price.

        Returns
        -------
        tuple[str, dict[str, Any]]
            Signal string and additional details dictionary.
        """
        details: dict[str, Any] = {}

        if z_score is None:
            return "HOLD", details

        # Exit Logic: Check stop-loss, take-profit, or mean reversion exits first
        if self._position_state != 0:
            pnl_pct = self._calculate_pnl_pct(current_price)
            details["pnl_pct"] = pnl_pct

            if pnl_pct is not None:
                # LONG position exits
                if self._position_state == 1:
                    # Stop-loss: Exit if loss exceeds threshold
                    if pnl_pct <= -self.p.stop_loss_pct:
                        details["exit_reason"] = "stop_loss"
                        return "STOP_LOSS", details

                    # Take-profit: Exit if profit target reached
                    if pnl_pct >= self.p.take_profit_pct:
                        details["exit_reason"] = "take_profit"
                        return "TAKE_PROFIT", details

                    # Mean reversion exit: Exit when z-score normalizes
                    if z_score > -self.p.z_exit:
                        details["exit_reason"] = "mean_revert"
                        return "EXIT_LONG", details

                # SHORT position exits
                elif self._position_state == -1:
                    # Stop-loss for short: Exit if loss exceeds threshold
                    if pnl_pct <= -self.p.stop_loss_pct:
                        details["exit_reason"] = "stop_loss"
                        return "STOP_LOSS_SHORT", details

                    # Take-profit for short
                    if pnl_pct >= self.p.take_profit_pct:
                        details["exit_reason"] = "take_profit"
                        return "TAKE_PROFIT_SHORT", details

                    # Mean reversion exit for short
                    if z_score < self.p.z_exit:
                        details["exit_reason"] = "mean_revert"
                        return "EXIT_SHORT", details

            return "HOLD", details

        # Entry Logic: Place limit orders when flat
        if self._position_state == 0:
            # Oversold: Place limit BUY order below current price
            if z_score < -self.p.z_entry:
                limit_price = current_price * (1 - self.p.limit_offset_pct)
                details["limit_price"] = limit_price
                return "BUY_LIMIT", details

            # Overbought: Place limit SELL order above current price (short)
            if z_score > self.p.z_entry:
                limit_price = current_price * (1 + self.p.limit_offset_pct)
                details["limit_price"] = limit_price
                return "SELL_LIMIT", details

        return "HOLD", details

    def _execute_signal(
        self,
        signal: str,
        z_score: float | None,
        current_price: float,
        signal_details: dict[str, Any],
        asset: str | None,
    ) -> None:
        """Execute order based on signal.

        Parameters
        ----------
        signal : str
            Trading signal.
        z_score : float | None
            Current z-score value.
        current_price : float
            Current market price.
        signal_details : dict[str, Any]
            Additional signal details.
        asset : str | None
            Asset symbol.
        """
        # Entry signals with limit orders
        if signal == "BUY_LIMIT" and self._position_state == 0:
            limit_price = signal_details.get("limit_price", current_price)
            self.buy(size=self.p.shares_per_trade, price=limit_price, exectype=bt.Order.Limit)
            self._position_state = 1
            self._entry_price = limit_price
            self.log_order_created(
                order_type="limit",
                asset=asset or "UNKNOWN",
                quantity=self.p.shares_per_trade,
                limit_price=limit_price,
                z_score=z_score,
            )
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={
                    "position_state": "LONG",
                    "entry_type": "limit",
                    "limit_price": limit_price,
                },
                asset=asset,
                simulation_timestamp=self._current_simulation_timestamp,
            )

        elif signal == "SELL_LIMIT" and self._position_state == 0:
            limit_price = signal_details.get("limit_price", current_price)
            self.sell(size=self.p.shares_per_trade, price=limit_price, exectype=bt.Order.Limit)
            self._position_state = -1
            self._entry_price = limit_price
            self.log_order_created(
                order_type="limit",
                asset=asset or "UNKNOWN",
                quantity=-self.p.shares_per_trade,
                limit_price=limit_price,
                z_score=z_score,
            )
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={
                    "position_state": "SHORT",
                    "entry_type": "limit",
                    "limit_price": limit_price,
                },
                asset=asset,
                simulation_timestamp=self._current_simulation_timestamp,
            )

        # Exit signals (all exit with market order)
        elif signal in ("STOP_LOSS", "TAKE_PROFIT", "EXIT_LONG") and self._position_state == 1:
            pnl_pct = signal_details.get("pnl_pct", 0)
            exit_reason = signal_details.get("exit_reason", signal.lower())
            self.close()
            self._position_state = 0
            self._entry_price = None
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=-self.p.shares_per_trade,
                target_percent=0.0,
                z_score=z_score,
                exit_reason=exit_reason,
                pnl_pct=pnl_pct,
            )
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={
                    "position_state": "FLAT",
                    "exit_reason": exit_reason,
                    "pnl_pct": pnl_pct,
                },
                asset=asset,
                simulation_timestamp=self._current_simulation_timestamp,
            )

        elif (
            signal in ("STOP_LOSS_SHORT", "TAKE_PROFIT_SHORT", "EXIT_SHORT")
            and self._position_state == -1
        ):
            pnl_pct = signal_details.get("pnl_pct", 0)
            exit_reason = signal_details.get("exit_reason", signal.lower())
            self.close()
            self._position_state = 0
            self._entry_price = None
            self.log_order_created(
                order_type="market",
                asset=asset or "UNKNOWN",
                quantity=self.p.shares_per_trade,
                target_percent=0.0,
                z_score=z_score,
                exit_reason=exit_reason,
                pnl_pct=pnl_pct,
            )
            self._log_event(
                layer="portfolio",
                event="position_updated",
                data={
                    "position_state": "FLAT",
                    "exit_reason": exit_reason,
                    "pnl_pct": pnl_pct,
                },
                asset=asset,
                simulation_timestamp=self._current_simulation_timestamp,
            )

    @property
    def position_state(self) -> int:
        """Get current position state (-1 = short, 0 = flat, 1 = long)."""
        return self._position_state

    @property
    def entry_price(self) -> float | None:
        """Get current entry price."""
        return self._entry_price
