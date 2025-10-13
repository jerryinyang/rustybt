"""Signal alignment validator for shadow trading.

This module compares backtest signals vs. live signals in real-time to detect
when strategy behavior diverges from backtest expectations.
"""

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog

from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.models import SignalAlignment, SignalRecord

logger = structlog.get_logger()


class SignalAlignmentValidator:
    """Validates alignment between backtest and live signals.

    This validator matches signals by timestamp and asset, then classifies
    the alignment quality to detect divergence patterns.

    Attributes:
        config: Shadow trading configuration
        backtest_signals: Buffer of recent backtest signals
        live_signals: Buffer of recent live signals
        matched_pairs: History of matched signal pairs
        divergence_counts: Count of each divergence type
    """

    def __init__(self, config: ShadowTradingConfig):
        """Initialize signal alignment validator.

        Args:
            config: Shadow trading configuration with thresholds
        """
        self.config = config
        self._backtest_signals: deque = deque(maxlen=10000)  # Last 10k signals
        self._live_signals: deque = deque(maxlen=10000)
        self._matched_pairs: deque = deque(maxlen=1000)  # Last 1k matches
        self._divergence_counts: dict[SignalAlignment, int] = defaultdict(int)
        # Use deques with maxlen to prevent unbounded memory growth
        self._unmatched_backtest: deque = deque(maxlen=1000)  # Last 1k unmatched
        self._unmatched_live: deque = deque(maxlen=1000)  # Last 1k unmatched

        logger.info(
            "signal_alignment_validator_initialized",
            time_tolerance_ms=config.time_tolerance_ms,
            signal_match_rate_min=str(config.signal_match_rate_min),
        )

    def add_backtest_signal(self, signal: SignalRecord) -> None:
        """Add backtest signal for matching.

        Args:
            signal: Backtest signal record
        """
        self._backtest_signals.append(signal)
        logger.debug(
            "backtest_signal_added",
            signal_id=signal.signal_id,
            asset=signal.asset.symbol,
            side=signal.side,
            quantity=str(signal.quantity),
            timestamp=signal.timestamp.isoformat(),
        )

    def add_live_signal(self, signal: SignalRecord) -> tuple[SignalRecord, SignalAlignment] | None:
        """Add live signal and attempt to match with backtest signal.

        Args:
            signal: Live signal record

        Returns:
            Tuple of (matched_backtest_signal, alignment_classification) if match found,
            None otherwise
        """
        self._live_signals.append(signal)

        # Attempt to match with backtest signal
        match_result = self._find_matching_backtest_signal(signal)

        if match_result:
            backtest_signal, alignment = match_result
            self._divergence_counts[alignment] += 1
            self._matched_pairs.append((backtest_signal, signal, alignment))

            logger.info(
                "signal_matched",
                backtest_signal_id=backtest_signal.signal_id,
                live_signal_id=signal.signal_id,
                alignment=alignment.value,
                asset=signal.asset.symbol,
            )

            return match_result
        else:
            # No match found - missing signal
            self._divergence_counts[SignalAlignment.MISSING_SIGNAL] += 1
            self._unmatched_live.append(signal)

            logger.warning(
                "signal_missing_in_backtest",
                live_signal_id=signal.signal_id,
                asset=signal.asset.symbol,
                side=signal.side,
                quantity=str(signal.quantity),
                timestamp=signal.timestamp.isoformat(),
            )

            return None

    def _find_matching_backtest_signal(
        self, live_signal: SignalRecord
    ) -> tuple[SignalRecord, SignalAlignment] | None:
        """Find matching backtest signal for live signal.

        Matching criteria (in order of priority):
        1. Timestamp within tolerance
        2. Same asset
        3. Same side (BUY/SELL)
        4. Classify quantity/price alignment

        Args:
            live_signal: Live signal to match

        Returns:
            Tuple of (backtest_signal, alignment_classification) if found,
            None if no match
        """
        # Search recent backtest signals for match
        tolerance_ms = self.config.time_tolerance_ms
        candidates = []

        for backtest_signal in reversed(self._backtest_signals):
            # Check time window (only search recent signals)
            time_diff_s = (live_signal.timestamp - backtest_signal.timestamp).total_seconds()
            if time_diff_s < -1:  # Backtest signal is in future (shouldn't happen)
                continue
            if time_diff_s > 5:  # Backtest signal is too old (>5 seconds)
                break

            # Check if timestamps match within tolerance
            if backtest_signal.matches_time(live_signal, tolerance_ms):
                # Check if asset and direction match
                if backtest_signal.matches_direction(live_signal):
                    candidates.append(backtest_signal)

        if not candidates:
            # Check if this might be a time mismatch
            for backtest_signal in reversed(self._backtest_signals):
                if backtest_signal.matches_direction(live_signal):
                    # Same direction but outside time window
                    return (backtest_signal, SignalAlignment.TIME_MISMATCH)
            return None

        # Take closest match by timestamp
        best_match = min(
            candidates, key=lambda bs: abs((bs.timestamp - live_signal.timestamp).total_seconds())
        )

        # Classify alignment quality
        alignment = self._classify_alignment(best_match, live_signal)

        return (best_match, alignment)

    def _classify_alignment(
        self, backtest_signal: SignalRecord, live_signal: SignalRecord
    ) -> SignalAlignment:
        """Classify alignment quality between backtest and live signals.

        Args:
            backtest_signal: Backtest signal
            live_signal: Live signal

        Returns:
            SignalAlignment classification
        """
        # Check quantity difference
        quantity_diff_pct = backtest_signal.quantity_difference_pct(live_signal)

        # Check price difference (if both have prices)
        price_diff_pct = Decimal("0")
        if backtest_signal.price and live_signal.price:
            if backtest_signal.price > Decimal("0"):
                price_diff_pct = (
                    abs(backtest_signal.price - live_signal.price)
                    / backtest_signal.price
                    * Decimal("100")
                )

        # Exact match: quantity within 10%, price within 1%
        if quantity_diff_pct <= Decimal("10") and price_diff_pct <= Decimal("1"):
            return SignalAlignment.EXACT_MATCH

        # Direction match: same direction, but quantity/price differ
        if quantity_diff_pct <= Decimal("50"):
            return SignalAlignment.DIRECTION_MATCH

        # Magnitude mismatch: same direction, >50% quantity difference
        return SignalAlignment.MAGNITUDE_MISMATCH

    def calculate_match_rate(self, window_minutes: int = 60) -> Decimal:
        """Calculate signal match rate over recent window.

        Args:
            window_minutes: Time window for calculation (default: 60 minutes)

        Returns:
            Signal match rate as Decimal (0.95 = 95%)
        """
        cutoff_time = datetime.now(UTC) - timedelta(minutes=window_minutes)

        # Count signals in window
        backtest_count = sum(1 for sig in self._backtest_signals if sig.timestamp >= cutoff_time)

        live_count = sum(1 for sig in self._live_signals if sig.timestamp >= cutoff_time)

        # Count matches in window
        match_count = sum(
            1
            for bt_sig, live_sig, alignment in self._matched_pairs
            if live_sig.timestamp >= cutoff_time
            and alignment in (SignalAlignment.EXACT_MATCH, SignalAlignment.DIRECTION_MATCH)
        )

        # Calculate match rate (use backtest count as baseline)
        if backtest_count == 0:
            return Decimal("1")  # No signals = perfect alignment by default

        match_rate = Decimal(str(match_count)) / Decimal(str(backtest_count))

        logger.info(
            "signal_match_rate_calculated",
            window_minutes=window_minutes,
            backtest_count=backtest_count,
            live_count=live_count,
            match_count=match_count,
            match_rate=str(match_rate),
        )

        return match_rate

    def get_divergence_breakdown(self) -> dict[SignalAlignment, int]:
        """Get count of each divergence type.

        Returns:
            Dictionary mapping SignalAlignment to count
        """
        return dict(self._divergence_counts)

    def get_unmatched_signals(self) -> tuple[list[SignalRecord], list[SignalRecord]]:
        """Get unmatched signals for debugging.

        Returns:
            Tuple of (unmatched_backtest_signals, unmatched_live_signals)
        """
        return (self._unmatched_backtest, self._unmatched_live)

    def reset(self) -> None:
        """Reset validator state."""
        self._backtest_signals.clear()
        self._live_signals.clear()
        self._matched_pairs.clear()
        self._divergence_counts.clear()
        self._unmatched_backtest.clear()
        self._unmatched_live.clear()

        logger.info("signal_alignment_validator_reset")
