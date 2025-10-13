"""Simple SMA Crossover Strategy for Benchmarking.

Complexity: Simple (1-2 indicators)
Indicators:
- SMA Short (50 periods)
- SMA Long (200 periods)

Logic: Buy when SMA Short > SMA Long, sell otherwise

This strategy is deterministic and designed for benchmarking performance.
"""

from typing import Any


class SimpleSMACrossover:
    """Simple SMA crossover strategy for benchmarking.

    Attributes:
        sma_short: Short-term SMA window (default: 50)
        sma_long: Long-term SMA window (default: 200)
    """

    def __init__(self, sma_short: int = 50, sma_long: int = 200):
        """Initialize strategy parameters.

        Args:
            sma_short: Short-term SMA window
            sma_long: Long-term SMA window
        """
        self.sma_short = sma_short
        self.sma_long = sma_long

    def initialize(self, context: Any) -> None:
        """Initialize strategy context.

        Args:
            context: Trading context object
        """
        # Store parameters in context
        context.sma_short = self.sma_short
        context.sma_long = self.sma_long

        # Track positions
        context.positions = {}

    def handle_data(self, context: Any, data: Any) -> None:
        """Execute strategy logic on each bar.

        Args:
            context: Trading context object
            data: Market data object
        """
        # Iterate through all assets in context
        if not hasattr(context, "assets"):
            return

        for asset in context.assets:
            # Get price history
            short_hist = data.history(asset, "close", context.sma_short, "1d")
            long_hist = data.history(asset, "close", context.sma_long, "1d")

            # Check if we have enough data
            if len(short_hist) < context.sma_short or len(long_hist) < context.sma_long:
                continue

            # Calculate SMAs
            short_mavg = float(short_hist.mean())
            long_mavg = float(long_hist.mean())

            # Generate signals
            if short_mavg > long_mavg:
                # Buy signal: go long
                context.order_target_percent(asset, 1.0 / len(context.assets))
            elif short_mavg < long_mavg:
                # Sell signal: exit position
                context.order_target_percent(asset, 0.0)

            # Record indicators for analysis
            context.record(
                **{
                    f"{asset.symbol}_sma_short": short_mavg,
                    f"{asset.symbol}_sma_long": long_mavg,
                }
            )


def create_initialize_fn(n_assets: int, sma_short: int = 50, sma_long: int = 200):
    """Create initialize function for run_algorithm.

    Args:
        n_assets: Number of assets to trade
        sma_short: Short-term SMA window
        sma_long: Long-term SMA window

    Returns:
        Initialize function compatible with run_algorithm
    """

    def initialize(context):
        # Import here to avoid circular dependency
        from rustybt.api import symbol

        # Use SYM prefix to match profiling bundles
        context.assets = [symbol(f"SYM{i:03d}") for i in range(n_assets)]
        context.sma_short = sma_short
        context.sma_long = sma_long
        context.positions = {}

    return initialize


def create_handle_data_fn(sma_short: int = 50, sma_long: int = 200):
    """Create handle_data function for run_algorithm.

    Args:
        sma_short: Short-term SMA window
        sma_long: Long-term SMA window

    Returns:
        Handle data function compatible with run_algorithm
    """

    def handle_data(context, data):
        # Import here to avoid circular dependency
        from rustybt.api import order_target_percent, record

        for asset in context.assets:
            # Get price history
            short_hist = data.history(asset, "close", sma_short, "1d")
            long_hist = data.history(asset, "close", sma_long, "1d")

            # Check if we have enough data
            if len(short_hist) < sma_short or len(long_hist) < sma_long:
                continue

            # Calculate SMAs
            short_mavg = float(short_hist.mean())
            long_mavg = float(long_hist.mean())

            # Generate signals
            if short_mavg > long_mavg:
                # Buy signal: go long
                order_target_percent(asset, 1.0 / len(context.assets))
            elif short_mavg < long_mavg:
                # Sell signal: exit position
                order_target_percent(asset, 0.0)

            # Record indicators for analysis
            record(
                **{
                    f"{asset.symbol}_sma_short": short_mavg,
                    f"{asset.symbol}_sma_long": long_mavg,
                }
            )

    return handle_data
