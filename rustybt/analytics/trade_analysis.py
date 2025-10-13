#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Trade analysis and diagnostics for backtests.

This module provides comprehensive trade-level analysis to identify strategy weaknesses
and improve execution. Analysis includes:

- Trade log with entry/exit details
- Entry/exit quality analysis (timing vs. optimal prices)
- Maximum Adverse/Favorable Excursion (MAE/MFE)
- Holding period distribution
- Win/loss distribution
- Trade clustering (time and asset concentration)
- Slippage and commission impact

Methodologies follow Tomasini & Jaekle - "Trading Systems" for MAE/MFE analysis.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, getcontext
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns
import structlog

from rustybt.assets import Asset

# Set decimal precision
getcontext().prec = 28

logger = structlog.get_logger(__name__)


class TradeAnalysisError(Exception):
    """Base exception for trade analysis errors."""

    pass


class InsufficientTradeDataError(TradeAnalysisError):
    """Raised when insufficient trade data for analysis."""

    pass


@dataclass(frozen=True)
class Trade:
    """Single trade record with complete lifecycle information.

    Attributes:
        entry_time: Trade entry timestamp
        exit_time: Trade exit timestamp
        asset: Asset traded
        entry_price: Entry execution price
        exit_price: Exit execution price
        amount: Position size (positive=long, negative=short)
        pnl: Trade profit/loss after all costs
        duration: Time held (exit_time - entry_time)
        commission: Total commission paid
        slippage: Total slippage cost
        mae: Maximum Adverse Excursion (worst drawdown during trade)
        mfe: Maximum Favorable Excursion (best profit during trade)
    """

    entry_time: datetime
    exit_time: datetime
    asset: Asset
    entry_price: Decimal
    exit_price: Decimal
    amount: Decimal
    pnl: Decimal
    duration: timedelta
    commission: Decimal
    slippage: Decimal
    mae: Decimal
    mfe: Decimal


class TradeAnalyzer:
    """Analyze trade execution quality and patterns.

    This class provides comprehensive trade-level diagnostics to understand:
    - How well trades were timed (entry/exit quality)
    - Risk management effectiveness (MAE/MFE)
    - Trade distribution patterns
    - Cost impact on performance

    Example:
        >>> analyzer = TradeAnalyzer(backtest_result)
        >>> analysis = analyzer.analyze_trades()
        >>> print(f"Win rate: {analysis['summary_stats']['win_rate']:.2%}")
        >>> print(f"Profit factor: {analysis['summary_stats']['profit_factor']:.2f}")
        >>>
        >>> # Generate visualizations
        >>> analyzer.plot_mae_vs_pnl()
        >>> analyzer.plot_trade_timeline()
    """

    def __init__(self, backtest_result: Any) -> None:  # noqa: ANN401
        """Initialize trade analyzer.

        Args:
            backtest_result: Backtest result object containing transactions and price data.
                Must have attributes:
                - transactions: List of transaction objects with timestamp, asset, amount,
                  price, commission, slippage
                - portfolio_history: DataFrame with portfolio values over time
                - price_data: Price history for all traded assets

        Raises:
            ValueError: If backtest_result is invalid or missing required attributes.
            InsufficientTradeDataError: If no trades found in transactions.
        """
        if not hasattr(backtest_result, "transactions"):
            raise ValueError("backtest_result must have 'transactions' attribute")

        if not hasattr(backtest_result, "price_data"):
            raise ValueError("backtest_result must have 'price_data' attribute")

        self.backtest_result = backtest_result
        self.transactions = backtest_result.transactions
        self.price_data = backtest_result.price_data

        # Extract trades from transactions
        self.trades = self._extract_trades()

        if len(self.trades) == 0:
            raise InsufficientTradeDataError("No completed trades found in backtest results")

        logger.info(
            "trade_analyzer_initialized",
            total_trades=len(self.trades),
            unique_assets=len({t.asset for t in self.trades}),
        )

    def _extract_trades(self) -> list[Trade]:
        """Extract individual trades from transaction stream.

        Matches entry and exit transactions to create complete trade records.
        For each asset, tracks open positions and pairs them with closing transactions.

        Returns:
            List of Trade objects representing completed round-trip trades.

        Note:
            - Positions opened but not closed by end of backtest are excluded
            - Partial position closes are treated as separate trades
            - FIFO (First In First Out) matching for position closes
        """
        trades: list[Trade] = []
        open_positions: dict[Asset, list[dict]] = {}

        for txn in self.transactions:
            asset = txn.asset
            amount = txn.amount

            if asset not in open_positions:
                open_positions[asset] = []

            # Check if this is opening or closing a position
            total_position = sum(pos["amount"] for pos in open_positions[asset])

            if total_position == Decimal("0"):
                # Opening new position
                open_positions[asset].append(
                    {
                        "entry_time": txn.timestamp,
                        "entry_price": txn.price,
                        "amount": amount,
                        "entry_commission": txn.commission,
                        "entry_slippage": txn.slippage,
                    }
                )
            elif (total_position > Decimal("0") and amount < Decimal("0")) or (
                total_position < Decimal("0") and amount > Decimal("0")
            ):
                # Closing position (opposite sign)
                remaining_close = abs(amount)
                exit_commission = txn.commission
                exit_slippage = txn.slippage

                # Close positions FIFO
                while remaining_close > Decimal("0") and open_positions[asset]:
                    entry_pos = open_positions[asset][0]
                    entry_amount = abs(entry_pos["amount"])

                    if remaining_close >= entry_amount:
                        # Close entire position
                        close_amount = entry_amount
                        remaining_close -= entry_amount
                        open_positions[asset].pop(0)
                    else:
                        # Partial close
                        close_amount = remaining_close
                        entry_pos["amount"] = (
                            entry_amount - close_amount
                            if entry_pos["amount"] > Decimal("0")
                            else -(entry_amount - close_amount)
                        )
                        remaining_close = Decimal("0")

                    # Calculate trade PnL
                    if entry_pos["amount"] > Decimal("0") or total_position > Decimal("0"):
                        # Long trade
                        gross_pnl = (txn.price - entry_pos["entry_price"]) * close_amount
                    else:
                        # Short trade
                        gross_pnl = (entry_pos["entry_price"] - txn.price) * close_amount

                    # Allocate costs proportionally
                    position_fraction = (
                        close_amount / abs(amount) if amount != Decimal("0") else Decimal("1")
                    )
                    allocated_exit_commission = exit_commission * position_fraction
                    allocated_exit_slippage = exit_slippage * position_fraction

                    total_commission = entry_pos["entry_commission"] + allocated_exit_commission
                    total_slippage = entry_pos["entry_slippage"] + allocated_exit_slippage
                    net_pnl = gross_pnl - total_commission - total_slippage

                    duration = txn.timestamp - entry_pos["entry_time"]

                    # Calculate MAE and MFE
                    mae, mfe = self._calculate_mae_mfe(
                        asset=asset,
                        entry_time=entry_pos["entry_time"],
                        exit_time=txn.timestamp,
                        entry_price=entry_pos["entry_price"],
                        is_long=entry_pos["amount"] > Decimal("0"),
                    )

                    trade = Trade(
                        entry_time=entry_pos["entry_time"],
                        exit_time=txn.timestamp,
                        asset=asset,
                        entry_price=entry_pos["entry_price"],
                        exit_price=txn.price,
                        amount=entry_pos["amount"],
                        pnl=net_pnl,
                        duration=duration,
                        commission=total_commission,
                        slippage=total_slippage,
                        mae=mae,
                        mfe=mfe,
                    )
                    trades.append(trade)

            else:
                # Adding to existing position (same direction)
                open_positions[asset].append(
                    {
                        "entry_time": txn.timestamp,
                        "entry_price": txn.price,
                        "amount": amount,
                        "entry_commission": txn.commission,
                        "entry_slippage": txn.slippage,
                    }
                )

        logger.info("trades_extracted", total_trades=len(trades))
        return trades

    def _calculate_mae_mfe(
        self,
        asset: Asset,
        entry_time: datetime,
        exit_time: datetime,
        entry_price: Decimal,
        is_long: bool,
    ) -> tuple[Decimal, Decimal]:
        """Calculate Maximum Adverse Excursion (MAE) and Maximum Favorable Excursion (MFE).

        Args:
            asset: Asset traded
            entry_time: Trade entry time
            exit_time: Trade exit time
            entry_price: Entry execution price
            is_long: True if long position, False if short

        Returns:
            Tuple of (mae, mfe) as percentages of entry price

        Note:
            - MAE measures worst price movement against the trade
            - MFE measures best price movement in favor of the trade
            - Used for optimal stop-loss and profit-target placement
        """
        try:
            # Get price history during trade
            price_history = self._get_price_history(asset, entry_time, exit_time)

            if len(price_history) == 0:
                return Decimal("0"), Decimal("0")

            if is_long:
                # Long position: MAE = max drawdown, MFE = max profit
                lowest = min(price_history)
                highest = max(price_history)
                mae = max(Decimal("0"), (entry_price - lowest) / entry_price)
                mfe = max(Decimal("0"), (highest - entry_price) / entry_price)
            else:
                # Short position: MAE = max price increase, MFE = max price decrease
                highest = max(price_history)
                lowest = min(price_history)
                mae = max(Decimal("0"), (highest - entry_price) / entry_price)
                mfe = max(Decimal("0"), (entry_price - lowest) / entry_price)

            return mae, mfe

        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.warning(
                "mae_mfe_calculation_failed",
                asset=str(asset),
                error=str(e),
            )
            return Decimal("0"), Decimal("0")

    def _get_price_history(
        self, asset: Asset, start_time: datetime, end_time: datetime
    ) -> list[Decimal]:
        """Get price history for asset between start and end times.

        Args:
            asset: Asset to get prices for
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of prices (as Decimal) during the time range
        """
        try:
            # Access price_data which should be a DataFrame or dict-like structure
            if isinstance(self.price_data, pd.DataFrame):
                # Assume multi-index or columns include asset identifier
                if asset.symbol in self.price_data.columns:
                    mask = (self.price_data.index >= start_time) & (
                        self.price_data.index <= end_time
                    )
                    prices = self.price_data.loc[mask, asset.symbol].dropna()
                    return [Decimal(str(p)) for p in prices.values]
                else:
                    return []
            elif isinstance(self.price_data, dict):
                # Dictionary keyed by asset
                asset_key = asset.symbol if hasattr(asset, "symbol") else str(asset)
                if asset_key in self.price_data:
                    df = self.price_data[asset_key]
                    mask = (df.index >= start_time) & (df.index <= end_time)
                    prices = df.loc[mask, "close"].dropna()
                    return [Decimal(str(p)) for p in prices.values]
                else:
                    return []
            else:
                return []
        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            logger.warning(
                "price_history_fetch_failed",
                asset=str(asset),
                start_time=start_time,
                end_time=end_time,
                error=str(e),
            )
            return []

    def _trades_to_dataframe(self) -> pl.DataFrame:
        """Convert trade list to Polars DataFrame.

        Returns:
            Polars DataFrame with trade data
        """
        data = {
            "entry_time": [t.entry_time for t in self.trades],
            "exit_time": [t.exit_time for t in self.trades],
            "asset": [str(t.asset) for t in self.trades],
            "entry_price": [float(t.entry_price) for t in self.trades],
            "exit_price": [float(t.exit_price) for t in self.trades],
            "amount": [float(t.amount) for t in self.trades],
            "pnl": [float(t.pnl) for t in self.trades],
            "duration_seconds": [t.duration.total_seconds() for t in self.trades],
            "commission": [float(t.commission) for t in self.trades],
            "slippage": [float(t.slippage) for t in self.trades],
            "mae": [float(t.mae) for t in self.trades],
            "mfe": [float(t.mfe) for t in self.trades],
        }

        return pl.DataFrame(data)

    def analyze_trades(self) -> dict[str, Any]:
        """Run comprehensive trade analysis.

        Returns:
            Dictionary containing:
            - trade_log: DataFrame with all trades
            - summary_stats: Overall statistics (win rate, profit factor, etc.)
            - entry_exit_quality: Entry/exit timing quality scores
            - holding_period_dist: Holding period distribution statistics
            - win_loss_dist: Win/loss distribution statistics
            - mae_mfe_analysis: MAE/MFE statistics
            - clustering: Trade clustering analysis (time and asset)
            - slippage_analysis: Slippage impact analysis
            - commission_impact: Commission impact analysis

        Raises:
            InsufficientTradeDataError: If insufficient trades for analysis
        """
        if len(self.trades) < 2:
            raise InsufficientTradeDataError(
                f"Need at least 2 trades for analysis, got {len(self.trades)}"
            )

        trades_df = self._trades_to_dataframe()

        analysis = {
            "trade_log": trades_df,
            "summary_stats": self._calculate_summary_stats(trades_df),
            "entry_exit_quality": self._analyze_entry_exit_quality(),
            "holding_period_dist": self._analyze_holding_period(trades_df),
            "win_loss_dist": self._analyze_win_loss_distribution(trades_df),
            "mae_mfe_analysis": self._analyze_mae_mfe(),
            "clustering": self._analyze_clustering(trades_df),
            "slippage_analysis": self._analyze_slippage(trades_df),
            "commission_impact": self._analyze_commissions(trades_df),
        }

        logger.info("trade_analysis_completed", total_trades=len(self.trades))
        return analysis

    def _calculate_summary_stats(self, trades_df: pl.DataFrame) -> dict[str, Any]:
        """Calculate trade summary statistics.

        Args:
            trades_df: DataFrame with trade data

        Returns:
            Dictionary with summary statistics
        """
        total_trades = len(trades_df)
        winning_trades = trades_df.filter(pl.col("pnl") > 0)
        losing_trades = trades_df.filter(pl.col("pnl") < 0)

        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0.0

        total_wins = winning_trades["pnl"].sum() if win_count > 0 else 0.0
        total_losses = abs(losing_trades["pnl"].sum()) if loss_count > 0 else 0.0

        avg_win = winning_trades["pnl"].mean() if win_count > 0 else 0.0
        avg_loss = losing_trades["pnl"].mean() if loss_count > 0 else 0.0

        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        largest_win = winning_trades["pnl"].max() if win_count > 0 else 0.0
        largest_loss = losing_trades["pnl"].min() if loss_count > 0 else 0.0

        avg_duration_seconds = trades_df["duration_seconds"].mean()
        avg_duration_hours = avg_duration_seconds / 3600.0 if avg_duration_seconds else 0.0

        return {
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "average_win": float(avg_win),
            "average_loss": float(avg_loss),
            "profit_factor": float(profit_factor) if profit_factor != float("inf") else None,
            "largest_win": float(largest_win),
            "largest_loss": float(largest_loss),
            "average_duration_hours": avg_duration_hours,
            "total_pnl": float(trades_df["pnl"].sum()),
        }

    def _analyze_entry_exit_quality(self) -> dict[str, Any]:
        """Analyze entry and exit quality vs. optimal prices.

        For each trade, compares actual entry/exit prices to optimal prices
        in hindsight (lowest price before entry, highest after exit for longs).

        Returns:
            Dictionary with quality metrics
        """
        entry_qualities = []
        exit_qualities = []

        # Lookback window for optimal price calculation (bars)
        lookback_bars = 20

        for trade in self.trades:
            # Get price history before entry
            optimal_entry = self._get_optimal_entry_price(
                trade.asset, trade.entry_time, lookback_bars
            )
            if optimal_entry is not None:
                if trade.amount > Decimal("0"):
                    # Long: lower entry is better
                    entry_quality = float(
                        (optimal_entry - trade.entry_price) / optimal_entry
                        if optimal_entry > Decimal("0")
                        else 0
                    )
                else:
                    # Short: higher entry is better
                    entry_quality = float(
                        (trade.entry_price - optimal_entry) / optimal_entry
                        if optimal_entry > Decimal("0")
                        else 0
                    )
                entry_qualities.append(entry_quality)

            # Get price history after exit
            optimal_exit = self._get_optimal_exit_price(trade.asset, trade.exit_time, lookback_bars)
            if optimal_exit is not None:
                if trade.amount > Decimal("0"):
                    # Long: higher exit is better
                    exit_quality = float(
                        (trade.exit_price - optimal_exit) / optimal_exit
                        if optimal_exit > Decimal("0")
                        else 0
                    )
                else:
                    # Short: lower exit is better
                    exit_quality = float(
                        (optimal_exit - trade.exit_price) / optimal_exit
                        if optimal_exit > Decimal("0")
                        else 0
                    )
                exit_qualities.append(exit_quality)

        return {
            "average_entry_quality": (float(np.mean(entry_qualities)) if entry_qualities else 0.0),
            "average_exit_quality": float(np.mean(exit_qualities)) if exit_qualities else 0.0,
            "entry_quality_std": float(np.std(entry_qualities)) if entry_qualities else 0.0,
            "exit_quality_std": float(np.std(exit_qualities)) if exit_qualities else 0.0,
        }

    def _get_optimal_entry_price(
        self, asset: Asset, entry_time: datetime, lookback_bars: int
    ) -> Decimal | None:
        """Get optimal entry price (lowest price in lookback window before entry).

        Args:
            asset: Asset traded
            entry_time: Entry timestamp
            lookback_bars: Number of bars to look back

        Returns:
            Optimal entry price or None if data unavailable
        """
        try:
            start_time = entry_time - timedelta(days=lookback_bars)
            prices = self._get_price_history(asset, start_time, entry_time)
            if len(prices) > 0:
                return min(prices)
            return None
        except (KeyError, IndexError, ValueError, TypeError):
            return None

    def _get_optimal_exit_price(
        self, asset: Asset, exit_time: datetime, lookforward_bars: int
    ) -> Decimal | None:
        """Get optimal exit price (highest price in lookforward window after exit).

        Args:
            asset: Asset traded
            exit_time: Exit timestamp
            lookforward_bars: Number of bars to look forward

        Returns:
            Optimal exit price or None if data unavailable
        """
        try:
            end_time = exit_time + timedelta(days=lookforward_bars)
            prices = self._get_price_history(asset, exit_time, end_time)
            if len(prices) > 0:
                return max(prices)
            return None
        except (KeyError, IndexError, ValueError, TypeError):
            return None

    def _analyze_holding_period(self, trades_df: pl.DataFrame) -> dict[str, Any]:
        """Analyze holding period distribution.

        Args:
            trades_df: DataFrame with trade data

        Returns:
            Dictionary with holding period statistics
        """
        durations_hours = trades_df["duration_seconds"] / 3600.0

        return {
            "mean_holding_hours": float(durations_hours.mean()),
            "median_holding_hours": float(durations_hours.median()),
            "min_holding_hours": float(durations_hours.min()),
            "max_holding_hours": float(durations_hours.max()),
            "std_holding_hours": float(durations_hours.std()),
        }

    def _analyze_win_loss_distribution(self, trades_df: pl.DataFrame) -> dict[str, Any]:
        """Analyze win/loss distribution.

        Args:
            trades_df: DataFrame with trade data

        Returns:
            Dictionary with win/loss statistics
        """
        pnls = trades_df["pnl"]

        return {
            "mean_pnl": float(pnls.mean()),
            "median_pnl": float(pnls.median()),
            "std_pnl": float(pnls.std()),
            "min_pnl": float(pnls.min()),
            "max_pnl": float(pnls.max()),
            "pnl_skewness": float(
                ((pnls - pnls.mean()) ** 3).mean() / (pnls.std() ** 3) if pnls.std() > 0 else 0.0
            ),
        }

    def _analyze_mae_mfe(self) -> dict[str, Any]:
        """Analyze MAE/MFE statistics.

        Returns:
            Dictionary with MAE/MFE statistics
        """
        maes = [float(t.mae) for t in self.trades]
        mfes = [float(t.mfe) for t in self.trades]

        return {
            "average_mae": float(np.mean(maes)) if maes else 0.0,
            "average_mfe": float(np.mean(mfes)) if mfes else 0.0,
            "max_mae": float(np.max(maes)) if maes else 0.0,
            "max_mfe": float(np.max(mfes)) if mfes else 0.0,
            "mae_mfe_ratio": (
                float(np.mean(maes) / np.mean(mfes)) if mfes and np.mean(mfes) > 0 else float("inf")
            ),
        }

    def _analyze_clustering(self, trades_df: pl.DataFrame) -> dict[str, Any]:
        """Analyze trade clustering (time and asset concentration).

        Args:
            trades_df: DataFrame with trade data

        Returns:
            Dictionary with clustering statistics
        """
        # Asset concentration
        asset_counts = trades_df["asset"].value_counts()
        total_trades = len(trades_df)

        top_3_assets = asset_counts.head(3)["count"].sum() if len(asset_counts) > 0 else 0
        top_3_concentration = float(top_3_assets / total_trades) if total_trades > 0 else 0.0

        # Time clustering - calculate trades per day
        trades_by_date = (
            trades_df.with_columns(pl.col("entry_time").cast(pl.Date).alias("entry_date"))
            .group_by("entry_date")
            .agg(pl.count().alias("trades_per_day"))
        )

        return {
            "unique_assets_traded": len(asset_counts),
            "top_3_asset_concentration": top_3_concentration,
            "avg_trades_per_day": (
                float(trades_by_date["trades_per_day"].mean()) if len(trades_by_date) > 0 else 0.0
            ),
            "max_trades_per_day": (
                int(trades_by_date["trades_per_day"].max()) if len(trades_by_date) > 0 else 0
            ),
        }

    def _analyze_slippage(self, trades_df: pl.DataFrame) -> dict[str, Any]:
        """Analyze slippage impact.

        Args:
            trades_df: DataFrame with trade data

        Returns:
            Dictionary with slippage statistics
        """
        total_slippage = float(trades_df["slippage"].sum())
        total_pnl = float(trades_df["pnl"].sum())

        avg_slippage = float(trades_df["slippage"].mean())

        # Find trades with excessive slippage (>2x average)
        if avg_slippage > 0:
            excessive_slippage_trades = len(trades_df.filter(pl.col("slippage") > 2 * avg_slippage))
        else:
            excessive_slippage_trades = 0

        return {
            "total_slippage": total_slippage,
            "slippage_pct_of_pnl": (
                float((total_slippage / abs(total_pnl)) * 100) if total_pnl != 0 else 0.0
            ),
            "average_slippage_per_trade": avg_slippage,
            "excessive_slippage_trades": excessive_slippage_trades,
        }

    def _analyze_commissions(self, trades_df: pl.DataFrame) -> dict[str, Any]:
        """Analyze commission impact.

        Args:
            trades_df: DataFrame with trade data

        Returns:
            Dictionary with commission statistics
        """
        total_commission = float(trades_df["commission"].sum())
        total_pnl = float(trades_df["pnl"].sum())

        avg_commission = float(trades_df["commission"].mean())

        # Find high-commission trades (>2x average)
        if avg_commission > 0:
            high_commission_trades = len(
                trades_df.filter(pl.col("commission") > 2 * avg_commission)
            )
        else:
            high_commission_trades = 0

        return {
            "total_commissions": total_commission,
            "commission_pct_of_pnl": (
                float((total_commission / abs(total_pnl)) * 100) if total_pnl != 0 else 0.0
            ),
            "average_commission_per_trade": avg_commission,
            "high_commission_trades": high_commission_trades,
        }

    # ========================================================================
    # Visualization Methods
    # ========================================================================

    def plot_holding_period_histogram(self, bins: int = 30) -> plt.Figure:
        """Plot histogram of trade holding periods.

        Args:
            bins: Number of histogram bins

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        durations_hours = [t.duration.total_seconds() / 3600 for t in self.trades]

        ax.hist(durations_hours, bins=bins, edgecolor="black", alpha=0.7)
        ax.set_xlabel("Holding Period (hours)")
        ax.set_ylabel("Frequency")
        ax.set_title("Trade Holding Period Distribution")
        ax.grid(True, alpha=0.3)

        return fig

    def plot_win_loss_histogram(self, bins: int = 30) -> plt.Figure:
        """Plot histogram of trade PnLs.

        Args:
            bins: Number of histogram bins

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        pnls = [float(t.pnl) for t in self.trades]

        ax.hist(pnls, bins=bins, edgecolor="black", alpha=0.7)
        ax.axvline(x=0, color="red", linestyle="--", label="Break-even")
        ax.set_xlabel("Trade PnL")
        ax.set_ylabel("Frequency")
        ax.set_title("Trade Win/Loss Distribution")
        ax.legend()
        ax.grid(True, alpha=0.3)

        return fig

    def plot_mae_vs_pnl(self) -> plt.Figure:
        """Plot MAE vs. final PnL scatter plot.

        This plot helps identify optimal stop-loss levels. Trades in the
        upper-left quadrant (high MAE, positive PnL) suggest stop-loss
        might have exited winners prematurely.

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        maes = [float(t.mae) * 100 for t in self.trades]  # Convert to percentage
        pnls = [float(t.pnl) for t in self.trades]

        colors = ["green" if pnl > 0 else "red" for pnl in pnls]

        ax.scatter(maes, pnls, c=colors, alpha=0.6)
        ax.axhline(y=0, color="black", linestyle="--", linewidth=0.8)
        ax.set_xlabel("Maximum Adverse Excursion (%)")
        ax.set_ylabel("Final Trade PnL")
        ax.set_title("MAE vs. Final PnL (Optimal Stop-Loss Analysis)")
        ax.grid(True, alpha=0.3)

        return fig

    def plot_mfe_vs_pnl(self) -> plt.Figure:
        """Plot MFE vs. final PnL scatter plot.

        This plot helps identify optimal profit targets. Trades in the
        upper-right quadrant (high MFE, positive PnL but MFE >> PnL)
        suggest profit targets might be too conservative.

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        mfes = [float(t.mfe) * 100 for t in self.trades]  # Convert to percentage
        pnls = [float(t.pnl) for t in self.trades]

        colors = ["green" if pnl > 0 else "red" for pnl in pnls]

        ax.scatter(mfes, pnls, c=colors, alpha=0.6)
        ax.axhline(y=0, color="black", linestyle="--", linewidth=0.8)
        ax.set_xlabel("Maximum Favorable Excursion (%)")
        ax.set_ylabel("Final Trade PnL")
        ax.set_title("MFE vs. Final PnL (Optimal Profit Target Analysis)")
        ax.grid(True, alpha=0.3)

        return fig

    def plot_trade_timeline(self) -> plt.Figure:
        """Plot trade timeline (entry time vs. PnL).

        Shows when profitable/unprofitable trades occurred, helping identify
        if performance varies by time period.

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        entry_times = [t.entry_time for t in self.trades]
        pnls = [float(t.pnl) for t in self.trades]

        colors = ["green" if pnl > 0 else "red" for pnl in pnls]

        ax.scatter(entry_times, pnls, c=colors, alpha=0.6)
        ax.axhline(y=0, color="black", linestyle="--", linewidth=0.8)
        ax.set_xlabel("Trade Entry Time")
        ax.set_ylabel("Trade PnL")
        ax.set_title("Trade Timeline")
        ax.grid(True, alpha=0.3)

        # Rotate x-axis labels for better readability
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        return fig

    def plot_trade_heatmap(self) -> plt.Figure:
        """Plot trade heatmap (asset vs. time).

        Shows concentration of trades across assets and time periods.

        Returns:
            Matplotlib figure
        """
        # Create DataFrame with trade counts by asset and date
        data = []
        for trade in self.trades:
            data.append(
                {
                    "asset": str(trade.asset),
                    "date": trade.entry_time.date(),
                    "pnl": float(trade.pnl),
                }
            )

        df = pd.DataFrame(data)

        # Pivot for heatmap
        pivot = df.pivot_table(
            index="asset", columns="date", values="pnl", aggfunc="sum", fill_value=0
        )

        fig, ax = plt.subplots(figsize=(14, max(6, len(pivot) * 0.4)))

        sns.heatmap(
            pivot,
            annot=False,
            cmap="RdYlGn",
            center=0,
            cbar_kws={"label": "PnL"},
            ax=ax,
        )

        ax.set_title("Trade Heatmap (Asset vs. Time)")
        ax.set_xlabel("Date")
        ax.set_ylabel("Asset")

        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        return fig
