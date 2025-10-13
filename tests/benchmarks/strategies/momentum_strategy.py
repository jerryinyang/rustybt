"""Momentum Strategy for Benchmarking.

Complexity: Medium (3-5 indicators)
Indicators:
- Momentum (20 periods)
- RSI (14 periods)
- Volume MA (20 periods)
- Bollinger Bands (20 periods, 2 std)

Logic: Buy on momentum + RSI oversold + high volume, sell on opposite

This strategy is deterministic and designed for benchmarking performance.
"""

from typing import Any


class MomentumStrategy:
    """Momentum-based strategy for benchmarking.

    Attributes:
        momentum_window: Momentum calculation window (default: 20)
        rsi_window: RSI calculation window (default: 14)
        volume_window: Volume MA window (default: 20)
        bb_window: Bollinger Bands window (default: 20)
        bb_std: Bollinger Bands standard deviations (default: 2.0)
        rsi_oversold: RSI oversold threshold (default: 30)
        rsi_overbought: RSI overbought threshold (default: 70)
        volume_threshold: Volume threshold multiplier (default: 1.2)
    """

    def __init__(
        self,
        momentum_window: int = 20,
        rsi_window: int = 14,
        volume_window: int = 20,
        bb_window: int = 20,
        bb_std: float = 2.0,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        volume_threshold: float = 1.2,
    ):
        """Initialize strategy parameters.

        Args:
            momentum_window: Momentum calculation window
            rsi_window: RSI calculation window
            volume_window: Volume MA window
            bb_window: Bollinger Bands window
            bb_std: Bollinger Bands standard deviations
            rsi_oversold: RSI oversold threshold
            rsi_overbought: RSI overbought threshold
            volume_threshold: Volume threshold multiplier
        """
        self.momentum_window = momentum_window
        self.rsi_window = rsi_window
        self.volume_window = volume_window
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.volume_threshold = volume_threshold

    def calculate_rsi(self, prices: Any, window: int = 14) -> float:
        """Calculate RSI indicator.

        Args:
            prices: Price series
            window: RSI window

        Returns:
            RSI value (0-100)
        """
        if len(prices) < window + 1:
            return 50.0  # Neutral

        # Calculate price changes
        deltas = prices.diff()

        # Separate gains and losses
        gains = deltas.where(deltas > 0, 0.0)
        losses = -deltas.where(deltas < 0, 0.0)

        # Calculate average gains and losses
        avg_gain = gains.rolling(window=window).mean().iloc[-1]
        avg_loss = losses.rolling(window=window).mean().iloc[-1]

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

        return float(rsi)


def create_initialize_fn(
    n_assets: int,
    momentum_window: int = 20,
    rsi_window: int = 14,
    volume_window: int = 20,
    bb_window: int = 20,
    bb_std: float = 2.0,
    rsi_oversold: float = 30.0,
    rsi_overbought: float = 70.0,
    volume_threshold: float = 1.2,
):
    """Create initialize function for run_algorithm.

    Args:
        n_assets: Number of assets to trade
        momentum_window: Momentum calculation window
        rsi_window: RSI calculation window
        volume_window: Volume MA window
        bb_window: Bollinger Bands window
        bb_std: Bollinger Bands standard deviations
        rsi_oversold: RSI oversold threshold
        rsi_overbought: RSI overbought threshold
        volume_threshold: Volume threshold multiplier

    Returns:
        Initialize function compatible with run_algorithm
    """

    def initialize(context):
        # Import here to avoid circular dependency
        from rustybt.api import symbol

        # Use SYM prefix to match profiling bundles
        context.assets = [symbol(f"SYM{i:03d}") for i in range(n_assets)]
        context.momentum_window = momentum_window
        context.rsi_window = rsi_window
        context.volume_window = volume_window
        context.bb_window = bb_window
        context.bb_std = bb_std
        context.rsi_oversold = rsi_oversold
        context.rsi_overbought = rsi_overbought
        context.volume_threshold = volume_threshold
        context.positions = {}

    return initialize


def create_handle_data_fn(
    momentum_window: int = 20,
    rsi_window: int = 14,
    volume_window: int = 20,
    bb_window: int = 20,
    bb_std: float = 2.0,
    rsi_oversold: float = 30.0,
    rsi_overbought: float = 70.0,
    volume_threshold: float = 1.2,
):
    """Create handle_data function for run_algorithm.

    Args:
        momentum_window: Momentum calculation window
        rsi_window: RSI calculation window
        volume_window: Volume MA window
        bb_window: Bollinger Bands window
        bb_std: Bollinger Bands standard deviations
        rsi_oversold: RSI oversold threshold
        rsi_overbought: RSI overbought threshold
        volume_threshold: Volume threshold multiplier

    Returns:
        Handle data function compatible with run_algorithm
    """

    def handle_data(context, data):
        # Import here to avoid circular dependency
        from rustybt.api import order_target_percent, record

        for asset in context.assets:
            # Get price and volume history
            max_window = max(momentum_window, rsi_window, volume_window, bb_window)
            prices = data.history(asset, "close", max_window + 1, "1d")
            volumes = data.history(asset, "volume", volume_window + 1, "1d")

            # Check if we have enough data
            if len(prices) < max_window + 1:
                continue

            # Calculate momentum
            momentum = float((prices.iloc[-1] / prices.iloc[-momentum_window] - 1) * 100)

            # Calculate RSI
            deltas = prices.diff()
            gains = deltas.where(deltas > 0, 0.0)
            losses = -deltas.where(deltas < 0, 0.0)
            avg_gain = float(gains.rolling(window=rsi_window).mean().iloc[-1])
            avg_loss = float(losses.rolling(window=rsi_window).mean().iloc[-1])

            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100.0 - (100.0 / (1.0 + rs))

            # Calculate volume indicator
            volume_ma = float(volumes.rolling(window=volume_window).mean().iloc[-1])
            current_volume = float(volumes.iloc[-1])
            volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1.0

            # Calculate Bollinger Bands
            bb_ma = float(prices.rolling(window=bb_window).mean().iloc[-1])
            bb_std_val = float(prices.rolling(window=bb_window).std().iloc[-1])
            bb_upper = bb_ma + (bb_std * bb_std_val)
            bb_lower = bb_ma - (bb_std * bb_std_val)
            current_price = float(prices.iloc[-1])

            # Generate signals
            buy_signal = (
                momentum > 0
                and rsi < rsi_oversold
                and volume_ratio > volume_threshold
                and current_price < bb_lower
            )

            sell_signal = momentum < 0 or rsi > rsi_overbought or current_price > bb_upper

            # Execute orders
            if buy_signal:
                order_target_percent(asset, 1.0 / len(context.assets))
            elif sell_signal:
                order_target_percent(asset, 0.0)

            # Record indicators for analysis
            record(
                **{
                    f"{asset.symbol}_momentum": momentum,
                    f"{asset.symbol}_rsi": rsi,
                    f"{asset.symbol}_volume_ratio": volume_ratio,
                    f"{asset.symbol}_bb_position": (
                        (current_price - bb_ma) / bb_std_val if bb_std_val > 0 else 0
                    ),
                }
            )

    return handle_data
