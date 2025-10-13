"""Multi-Indicator Strategy for Benchmarking.

Complexity: Complex (6+ indicators)
Indicators:
- Multiple SMAs (10, 20, 50, 200)
- EMAs (12, 26)
- MACD + Signal
- RSI (14)
- Bollinger Bands (20, 2)
- ATR (14)
- Volume indicators

Logic: Weighted scoring system combining all indicators

This strategy is deterministic and designed for benchmarking performance.
"""


class MultiIndicatorStrategy:
    """Multi-indicator strategy for benchmarking.

    Attributes:
        sma_windows: List of SMA windows (default: [10, 20, 50, 200])
        ema_windows: List of EMA windows (default: [12, 26])
        macd_fast: MACD fast period (default: 12)
        macd_slow: MACD slow period (default: 26)
        macd_signal: MACD signal period (default: 9)
        rsi_window: RSI window (default: 14)
        bb_window: Bollinger Bands window (default: 20)
        bb_std: Bollinger Bands standard deviations (default: 2.0)
        atr_window: ATR window (default: 14)
        volume_window: Volume MA window (default: 20)
    """

    def __init__(
        self,
        sma_windows: list = None,
        ema_windows: list = None,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        rsi_window: int = 14,
        bb_window: int = 20,
        bb_std: float = 2.0,
        atr_window: int = 14,
        volume_window: int = 20,
    ):
        """Initialize strategy parameters.

        Args:
            sma_windows: List of SMA windows
            ema_windows: List of EMA windows
            macd_fast: MACD fast period
            macd_slow: MACD slow period
            macd_signal: MACD signal period
            rsi_window: RSI window
            bb_window: Bollinger Bands window
            bb_std: Bollinger Bands standard deviations
            atr_window: ATR window
            volume_window: Volume MA window
        """
        self.sma_windows = sma_windows or [10, 20, 50, 200]
        self.ema_windows = ema_windows or [12, 26]
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.rsi_window = rsi_window
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.atr_window = atr_window
        self.volume_window = volume_window


def create_initialize_fn(
    n_assets: int,
    sma_windows: list = None,
    ema_windows: list = None,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    rsi_window: int = 14,
    bb_window: int = 20,
    bb_std: float = 2.0,
    atr_window: int = 14,
    volume_window: int = 20,
):
    """Create initialize function for run_algorithm.

    Args:
        n_assets: Number of assets to trade
        sma_windows: List of SMA windows
        ema_windows: List of EMA windows
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period
        rsi_window: RSI window
        bb_window: Bollinger Bands window
        bb_std: Bollinger Bands standard deviations
        atr_window: ATR window
        volume_window: Volume MA window

    Returns:
        Initialize function compatible with run_algorithm
    """

    def initialize(context):
        # Import here to avoid circular dependency
        from rustybt.api import symbol

        # Use SYM prefix to match profiling bundles
        context.assets = [symbol(f"SYM{i:03d}") for i in range(n_assets)]
        context.sma_windows = sma_windows or [10, 20, 50, 200]
        context.ema_windows = ema_windows or [12, 26]
        context.macd_fast = macd_fast
        context.macd_slow = macd_slow
        context.macd_signal = macd_signal
        context.rsi_window = rsi_window
        context.bb_window = bb_window
        context.bb_std = bb_std
        context.atr_window = atr_window
        context.volume_window = volume_window
        context.positions = {}

    return initialize


def create_handle_data_fn(
    sma_windows: list = None,
    ema_windows: list = None,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    rsi_window: int = 14,
    bb_window: int = 20,
    bb_std: float = 2.0,
    atr_window: int = 14,
    volume_window: int = 20,
):
    """Create handle_data function for run_algorithm.

    Args:
        sma_windows: List of SMA windows
        ema_windows: List of EMA windows
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period
        rsi_window: RSI window
        bb_window: Bollinger Bands window
        bb_std: Bollinger Bands standard deviations
        atr_window: ATR window
        volume_window: Volume MA window

    Returns:
        Handle data function compatible with run_algorithm
    """
    sma_windows = sma_windows or [10, 20, 50, 200]
    ema_windows = ema_windows or [12, 26]

    def handle_data(context, data):
        # Import here to avoid circular dependency
        from rustybt.api import order_target_percent, record

        for asset in context.assets:
            # Determine max window size
            max_window = max(
                max(sma_windows),
                max(ema_windows),
                macd_slow + macd_signal,
                rsi_window,
                bb_window,
                atr_window,
                volume_window,
            )

            # Get price and volume history
            prices = data.history(asset, "close", max_window + 1, "1d")
            highs = data.history(asset, "high", max_window + 1, "1d")
            lows = data.history(asset, "low", max_window + 1, "1d")
            volumes = data.history(asset, "volume", max_window + 1, "1d")

            # Check if we have enough data
            if len(prices) < max_window + 1:
                continue

            current_price = float(prices.iloc[-1])
            score = 0.0
            max_score = 0.0

            # 1. SMA Indicators (weight: 2 per SMA)
            sma_scores = []
            for window in sma_windows:
                if len(prices) >= window:
                    sma = float(prices.rolling(window=window).mean().iloc[-1])
                    sma_scores.append(1.0 if current_price > sma else -1.0)
                    max_score += 2.0
            score += sum(sma_scores) * 2.0

            # 2. EMA Indicators (weight: 3 per EMA)
            ema_scores = []
            for window in ema_windows:
                if len(prices) >= window:
                    ema = float(prices.ewm(span=window, adjust=False).mean().iloc[-1])
                    ema_scores.append(1.0 if current_price > ema else -1.0)
                    max_score += 3.0
            score += sum(ema_scores) * 3.0

            # 3. MACD Indicator (weight: 4)
            if len(prices) >= macd_slow + macd_signal:
                ema_fast = prices.ewm(span=macd_fast, adjust=False).mean()
                ema_slow = prices.ewm(span=macd_slow, adjust=False).mean()
                macd_line = ema_fast - ema_slow
                signal_line = macd_line.ewm(span=macd_signal, adjust=False).mean()
                macd_value = float(macd_line.iloc[-1])
                signal_value = float(signal_line.iloc[-1])
                macd_score = 1.0 if macd_value > signal_value else -1.0
                score += macd_score * 4.0
                max_score += 4.0

            # 4. RSI Indicator (weight: 3)
            if len(prices) >= rsi_window + 1:
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

                if rsi < 30:
                    rsi_score = 1.0  # Oversold, buy
                elif rsi > 70:
                    rsi_score = -1.0  # Overbought, sell
                else:
                    rsi_score = 0.0  # Neutral

                score += rsi_score * 3.0
                max_score += 3.0

            # 5. Bollinger Bands (weight: 2)
            if len(prices) >= bb_window:
                bb_ma = float(prices.rolling(window=bb_window).mean().iloc[-1])
                bb_std_val = float(prices.rolling(window=bb_window).std().iloc[-1])
                bb_upper = bb_ma + (bb_std * bb_std_val)
                bb_lower = bb_ma - (bb_std * bb_std_val)

                if current_price < bb_lower:
                    bb_score = 1.0  # Below lower band, buy
                elif current_price > bb_upper:
                    bb_score = -1.0  # Above upper band, sell
                else:
                    bb_score = 0.0  # Within bands, neutral

                score += bb_score * 2.0
                max_score += 2.0

            # 6. ATR (volatility, weight: 1)
            if len(highs) >= atr_window and len(lows) >= atr_window:
                tr = []
                for i in range(1, len(prices)):
                    high = float(highs.iloc[i])
                    low = float(lows.iloc[i])
                    prev_close = float(prices.iloc[i - 1])
                    tr_value = max(high - low, abs(high - prev_close), abs(low - prev_close))
                    tr.append(tr_value)

                if len(tr) >= atr_window:
                    atr = sum(tr[-atr_window:]) / atr_window
                    # High volatility favors holding cash (negative score)
                    # Low volatility favors trading (positive score)
                    # Normalize ATR as percentage of price
                    atr_pct = (atr / current_price) * 100
                    if atr_pct > 5:
                        atr_score = -0.5  # High volatility
                    else:
                        atr_score = 0.5  # Low volatility

                    score += atr_score * 1.0
                    max_score += 1.0

            # 7. Volume Indicator (weight: 2)
            if len(volumes) >= volume_window:
                volume_ma = float(volumes.rolling(window=volume_window).mean().iloc[-1])
                current_volume = float(volumes.iloc[-1])
                volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1.0

                if volume_ratio > 1.5:
                    volume_score = 1.0  # High volume confirms trend
                elif volume_ratio < 0.5:
                    volume_score = -1.0  # Low volume, weak trend
                else:
                    volume_score = 0.0  # Normal volume

                score += volume_score * 2.0
                max_score += 2.0

            # Normalize score to [-1, 1]
            normalized_score = score / max_score if max_score > 0 else 0.0

            # Generate signals based on normalized score
            if normalized_score > 0.3:
                # Strong buy signal
                target_percent = min(normalized_score, 1.0) / len(context.assets)
                order_target_percent(asset, target_percent)
            elif normalized_score < -0.3:
                # Strong sell signal
                order_target_percent(asset, 0.0)
            # else: hold position (do nothing)

            # Record indicators for analysis
            record(
                **{
                    f"{asset.symbol}_score": normalized_score,
                    f"{asset.symbol}_raw_score": score,
                }
            )

    return handle_data
