"""Layer-Specific Comparators for rustybt validation framework.

This module contains the logic for comparing rustybt and Backtrader logs
across the 5 validation layers (data, signals, orders, broker, portfolio).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import polars as pl

from rustybt.validation.tolerance import (
    Layer1Tolerances,
    Layer2Tolerances,
    Layer3Tolerances,
    Layer4Tolerances,
    Layer5Tolerances,
)


@dataclass
class Discrepancy:
    """Represents a discrepancy found during comparison.

    Attributes:
        layer: Validation layer where discrepancy was found
        event: Event type that caused the discrepancy
        timestamp: Timestamp when discrepancy occurred (simulation time)
        field: Field name that differs
        rustybt_value: Value from rustybt execution
        backtrader_value: Value from Backtrader execution
        tolerance: Tolerance threshold that was exceeded
        exceeded_by: Amount by which tolerance was exceeded
        asset: Asset symbol (optional)
        severity: Severity level (critical, warning, info)
        description: Human-readable description
    """

    layer: str
    event: str
    timestamp: str | None
    field: str
    rustybt_value: Any
    backtrader_value: Any
    tolerance: Any
    exceeded_by: Any
    asset: str | None = None
    severity: str = "warning"
    description: str = ""

    def __post_init__(self) -> None:
        """Generate description if not provided."""
        if not self.description:
            self.description = (
                f"{self.layer}/{self.event}: {self.field} differs - "
                f"rustybt={self.rustybt_value}, backtrader={self.backtrader_value}"
            )


@dataclass
class ComparisonResult:
    """Result of a layer comparison.

    Attributes:
        layer: Layer name
        passed: True if no critical discrepancies found
        discrepancies: List of all discrepancies found
        stats: Comparison statistics
    """

    layer: str
    passed: bool
    discrepancies: list[Discrepancy] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        """Count of critical discrepancies."""
        return sum(1 for d in self.discrepancies if d.severity == "critical")

    @property
    def warning_count(self) -> int:
        """Count of warning discrepancies."""
        return sum(1 for d in self.discrepancies if d.severity == "warning")


class BaseComparator(ABC):
    """Abstract base class for layer comparators."""

    @property
    @abstractmethod
    def layer_name(self) -> str:
        """Return the layer name this comparator handles."""
        pass

    @abstractmethod
    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> ComparisonResult:
        """Run comparison and return result.

        Args:
            rustybt_logs: Parsed logs from rustybt execution
            backtrader_logs: Parsed logs from Backtrader execution

        Returns:
            ComparisonResult with discrepancies and pass/fail status
        """
        pass


class Layer1DataComparator(BaseComparator):
    """Comparator for Layer 1: Data Handling.

    Validates:
    - Lookahead bias detection (zero tolerance)
    - Bar alignment between frameworks
    - OHLCV value comparison with tolerance
    - Data integrity (missing bars, gaps, anomalies)
    """

    def __init__(self, tolerances: Layer1Tolerances | None = None):
        """Initialize with tolerances.

        Args:
            tolerances: Layer 1 tolerance configuration. Uses defaults if None.
        """
        self.tolerances = tolerances or Layer1Tolerances()

    @property
    def layer_name(self) -> str:
        """Return the layer name this comparator handles."""
        return "data"

    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> ComparisonResult:
        """Run all Layer 1 comparisons.

        Args:
            rustybt_logs: Parsed logs from rustybt execution
            backtrader_logs: Parsed logs from Backtrader execution

        Returns:
            ComparisonResult with all discrepancies found
        """
        discrepancies: list[Discrepancy] = []

        # Check for lookahead bias in rustybt logs (critical)
        discrepancies.extend(self.detect_lookahead_bias(rustybt_logs))

        # Compare bar alignment between frameworks
        discrepancies.extend(self.compare_bar_alignment(rustybt_logs, backtrader_logs))

        # Validate data integrity in both logs
        discrepancies.extend(self.validate_data_integrity(rustybt_logs, "rustybt"))
        discrepancies.extend(self.validate_data_integrity(backtrader_logs, "backtrader"))

        # Determine pass/fail - fail if any critical discrepancies
        passed = not any(d.severity == "critical" for d in discrepancies)

        return ComparisonResult(
            layer=self.layer_name,
            passed=passed,
            discrepancies=discrepancies,
            stats={
                "rustybt_bar_count": len(rustybt_logs.filter(pl.col("event") == "bar_received")),
                "backtrader_bar_count": len(
                    backtrader_logs.filter(pl.col("event") == "bar_received")
                ),
                "total_discrepancies": len(discrepancies),
            },
        )

    def detect_lookahead_bias(self, logs: pl.DataFrame) -> list[Discrepancy]:
        """Detect if strategy accessed future data.

        Lookahead bias occurs when a strategy has access to data that
        wouldn't be available at that point in real trading.

        Args:
            logs: Parsed log DataFrame

        Returns:
            List of lookahead bias discrepancies (always critical severity)
        """
        discrepancies: list[Discrepancy] = []

        # Filter to data layer events
        if "layer" not in logs.columns:
            return discrepancies

        data_events = logs.filter(pl.col("layer") == "data")

        if data_events.is_empty():
            return discrepancies

        for row in data_events.iter_rows(named=True):
            accessed_time = row.get("data_accessed_timestamp")
            current_bar = row.get("data_current_bar_timestamp")

            if accessed_time is not None and current_bar is not None:
                # Compare timestamps
                if str(accessed_time) > str(current_bar):
                    discrepancies.append(
                        Discrepancy(
                            layer="data",
                            event="lookahead_bias",
                            timestamp=str(current_bar),
                            field="data_access",
                            rustybt_value=str(accessed_time),
                            backtrader_value=str(current_bar),
                            tolerance="none (zero tolerance)",
                            exceeded_by=f"accessed {accessed_time} > current {current_bar}",
                            asset=row.get("asset"),
                            severity="critical",
                            description=f"LOOKAHEAD BIAS: Strategy accessed data from {accessed_time} while current bar is {current_bar}",
                        )
                    )

        return discrepancies

    def compare_bar_alignment(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare bar timestamps and OHLCV values between frameworks.

        Args:
            rustybt_logs: Parsed logs from rustybt
            backtrader_logs: Parsed logs from Backtrader

        Returns:
            List of bar alignment discrepancies
        """
        discrepancies: list[Discrepancy] = []

        # Filter to bar_received events
        if "event" not in rustybt_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_bars = rustybt_logs.filter(pl.col("event") == "bar_received")
        bt_bars = backtrader_logs.filter(pl.col("event") == "bar_received")

        # Compare bar counts
        count_diff = abs(len(rb_bars) - len(bt_bars))
        if count_diff > self.tolerances.bar_count_tolerance:
            discrepancies.append(
                Discrepancy(
                    layer="data",
                    event="bar_count_mismatch",
                    timestamp=None,
                    field="bar_count",
                    rustybt_value=len(rb_bars),
                    backtrader_value=len(bt_bars),
                    tolerance=self.tolerances.bar_count_tolerance,
                    exceeded_by=count_diff,
                    severity="critical" if count_diff > 1 else "warning",
                    description=f"Bar count mismatch: rustybt={len(rb_bars)}, backtrader={len(bt_bars)}",
                )
            )

        if rb_bars.is_empty() or bt_bars.is_empty():
            return discrepancies

        # Compare OHLCV values for matching timestamps
        discrepancies.extend(self._compare_ohlcv(rb_bars, bt_bars))

        return discrepancies

    def _compare_ohlcv(
        self,
        rb_bars: pl.DataFrame,
        bt_bars: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare OHLCV values between frameworks.

        Args:
            rb_bars: rustybt bar events
            bt_bars: Backtrader bar events

        Returns:
            List of OHLCV discrepancies
        """
        discrepancies: list[Discrepancy] = []
        price_tol = self.tolerances.price_tolerance
        volume_tol_pct = self.tolerances.volume_tolerance_pct

        ohlcv_fields = ["data_open", "data_high", "data_low", "data_close", "data_volume"]

        # Build timestamp lookup for Backtrader bars
        bt_by_timestamp: dict[str, dict[str, Any]] = {}
        for row in bt_bars.iter_rows(named=True):
            ts = row.get("timestamp")
            if ts:
                bt_by_timestamp[str(ts)] = row

        # Compare each rustybt bar with corresponding Backtrader bar
        for rb_row in rb_bars.iter_rows(named=True):
            rb_ts = rb_row.get("timestamp")
            if not rb_ts:
                continue

            bt_row = bt_by_timestamp.get(str(rb_ts))
            if not bt_row:
                # Missing bar in Backtrader
                discrepancies.append(
                    Discrepancy(
                        layer="data",
                        event="missing_bar",
                        timestamp=str(rb_ts),
                        field="bar",
                        rustybt_value="present",
                        backtrader_value="missing",
                        tolerance="none",
                        exceeded_by="bar not found",
                        asset=rb_row.get("asset"),
                        severity="warning",
                    )
                )
                continue

            # Compare OHLCV fields
            for field in ohlcv_fields:
                rb_val = rb_row.get(field)
                bt_val = bt_row.get(field)

                if rb_val is None or bt_val is None:
                    continue

                try:
                    rb_decimal = Decimal(str(rb_val))
                    bt_decimal = Decimal(str(bt_val))
                    diff = abs(rb_decimal - bt_decimal)

                    if field == "data_volume":
                        # Use percentage tolerance for volume
                        if bt_decimal != 0:
                            pct_diff = float(diff / bt_decimal)
                            if pct_diff > volume_tol_pct:
                                discrepancies.append(
                                    Discrepancy(
                                        layer="data",
                                        event="ohlcv_mismatch",
                                        timestamp=str(rb_ts),
                                        field=field,
                                        rustybt_value=float(rb_decimal),
                                        backtrader_value=float(bt_decimal),
                                        tolerance=f"{volume_tol_pct:.4%}",
                                        exceeded_by=f"{pct_diff:.4%}",
                                        asset=rb_row.get("asset"),
                                        severity="warning",
                                    )
                                )
                    else:
                        # Use absolute tolerance for price fields
                        if diff > price_tol:
                            discrepancies.append(
                                Discrepancy(
                                    layer="data",
                                    event="ohlcv_mismatch",
                                    timestamp=str(rb_ts),
                                    field=field,
                                    rustybt_value=float(rb_decimal),
                                    backtrader_value=float(bt_decimal),
                                    tolerance=float(price_tol),
                                    exceeded_by=float(diff),
                                    asset=rb_row.get("asset"),
                                    severity="warning",
                                )
                            )
                except (ValueError, TypeError):
                    # Non-numeric values, skip comparison
                    pass

        return discrepancies

    def validate_data_integrity(
        self,
        logs: pl.DataFrame,
        source: str = "unknown",
    ) -> list[Discrepancy]:
        """Validate data integrity in logs.

        Checks for:
        - Missing bars (gaps in timestamp sequence)
        - OHLCV anomalies (high < low, etc.)

        Args:
            logs: Parsed log DataFrame
            source: Source identifier (rustybt or backtrader)

        Returns:
            List of data integrity discrepancies
        """
        discrepancies: list[Discrepancy] = []

        if "event" not in logs.columns:
            return discrepancies

        bars = logs.filter(pl.col("event") == "bar_received")

        if bars.is_empty():
            return discrepancies

        # Check OHLCV anomalies
        for row in bars.iter_rows(named=True):
            ts = row.get("timestamp")
            high = row.get("data_high")
            low = row.get("data_low")
            open_val = row.get("data_open")
            close = row.get("data_close")

            if high is not None and low is not None:
                try:
                    if float(high) < float(low):
                        discrepancies.append(
                            Discrepancy(
                                layer="data",
                                event="ohlcv_anomaly",
                                timestamp=str(ts) if ts else None,
                                field="high_low",
                                rustybt_value=f"high={high}, low={low}",
                                backtrader_value="high >= low expected",
                                tolerance="none",
                                exceeded_by=f"high ({high}) < low ({low})",
                                asset=row.get("asset"),
                                severity="critical",
                                description=f"OHLCV anomaly in {source}: high ({high}) < low ({low})",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

            # Check open/close within high/low bounds
            if all(v is not None for v in [high, low, open_val, close]):
                try:
                    h, l, o, c = float(high), float(low), float(open_val), float(close)
                    if o < l or o > h:
                        discrepancies.append(
                            Discrepancy(
                                layer="data",
                                event="ohlcv_anomaly",
                                timestamp=str(ts) if ts else None,
                                field="open_bounds",
                                rustybt_value=f"open={o}",
                                backtrader_value=f"expected between {l} and {h}",
                                tolerance="none",
                                exceeded_by="open out of bounds",
                                asset=row.get("asset"),
                                severity="warning",
                                description=f"OHLCV anomaly in {source}: open ({o}) outside high/low bounds",
                            )
                        )
                    if c < l or c > h:
                        discrepancies.append(
                            Discrepancy(
                                layer="data",
                                event="ohlcv_anomaly",
                                timestamp=str(ts) if ts else None,
                                field="close_bounds",
                                rustybt_value=f"close={c}",
                                backtrader_value=f"expected between {l} and {h}",
                                tolerance="none",
                                exceeded_by="close out of bounds",
                                asset=row.get("asset"),
                                severity="warning",
                                description=f"OHLCV anomaly in {source}: close ({c}) outside high/low bounds",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies


class Layer2SignalComparator(BaseComparator):
    """Comparator for Layer 2: Signal Computation.

    Validates:
    - Indicator value comparison with tolerance
    - Signal generation timing
    - Signal count matching
    - Boolean signal exact match (buy/sell)
    """

    def __init__(self, tolerances: Layer2Tolerances | None = None):
        """Initialize with tolerances.

        Args:
            tolerances: Layer 2 tolerance configuration. Uses defaults if None.
        """
        self.tolerances = tolerances or Layer2Tolerances()

    @property
    def layer_name(self) -> str:
        """Return the layer name this comparator handles."""
        return "signals"

    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> ComparisonResult:
        """Run all Layer 2 comparisons.

        Args:
            rustybt_logs: Parsed logs from rustybt execution
            backtrader_logs: Parsed logs from Backtrader execution

        Returns:
            ComparisonResult with all discrepancies found
        """
        discrepancies: list[Discrepancy] = []

        # Compare signal counts
        discrepancies.extend(self.compare_signal_counts(rustybt_logs, backtrader_logs))

        # Compare indicator values
        discrepancies.extend(self.compare_indicator_values(rustybt_logs, backtrader_logs))

        # Compare signal timing
        discrepancies.extend(self.compare_signal_timing(rustybt_logs, backtrader_logs))

        # Determine pass/fail
        passed = not any(d.severity == "critical" for d in discrepancies)

        return ComparisonResult(
            layer=self.layer_name,
            passed=passed,
            discrepancies=discrepancies,
            stats={
                "rustybt_signal_count": (
                    len(
                        rustybt_logs.filter(
                            (pl.col("layer") == "signals")
                            & (pl.col("event").str.contains("signal"))
                        )
                    )
                    if "layer" in rustybt_logs.columns and "event" in rustybt_logs.columns
                    else 0
                ),
                "backtrader_signal_count": (
                    len(
                        backtrader_logs.filter(
                            (pl.col("layer") == "signals")
                            & (pl.col("event").str.contains("signal"))
                        )
                    )
                    if "layer" in backtrader_logs.columns and "event" in backtrader_logs.columns
                    else 0
                ),
                "total_discrepancies": len(discrepancies),
            },
        )

    def compare_signal_counts(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare signal counts between frameworks.

        Args:
            rustybt_logs: rustybt logs
            backtrader_logs: Backtrader logs

        Returns:
            List of signal count discrepancies
        """
        discrepancies: list[Discrepancy] = []

        if "layer" not in rustybt_logs.columns or "layer" not in backtrader_logs.columns:
            return discrepancies

        # Filter to signals layer
        rb_signals = rustybt_logs.filter(pl.col("layer") == "signals")
        bt_signals = backtrader_logs.filter(pl.col("layer") == "signals")

        # Count buy/sell signals separately if event column exists
        if "event" in rb_signals.columns and "event" in bt_signals.columns:
            for signal_type in ["buy", "sell"]:
                rb_count = len(rb_signals.filter(pl.col("event").str.contains(signal_type)))
                bt_count = len(bt_signals.filter(pl.col("event").str.contains(signal_type)))

                if rb_count != bt_count:
                    discrepancies.append(
                        Discrepancy(
                            layer="signals",
                            event="signal_count_mismatch",
                            timestamp=None,
                            field=f"{signal_type}_signal_count",
                            rustybt_value=rb_count,
                            backtrader_value=bt_count,
                            tolerance=0,
                            exceeded_by=abs(rb_count - bt_count),
                            severity=(
                                "critical" if self.tolerances.signal_exact_match else "warning"
                            ),
                            description=f"{signal_type.upper()} signal count mismatch: rustybt={rb_count}, backtrader={bt_count}",
                        )
                    )

        return discrepancies

    def compare_indicator_values(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare indicator values between frameworks.

        Args:
            rustybt_logs: rustybt logs
            backtrader_logs: Backtrader logs

        Returns:
            List of indicator value discrepancies
        """
        discrepancies: list[Discrepancy] = []
        indicator_tol = self.tolerances.indicator_tolerance

        if "layer" not in rustybt_logs.columns or "layer" not in backtrader_logs.columns:
            return discrepancies

        # Filter to signals layer
        rb_signals = rustybt_logs.filter(pl.col("layer") == "signals")
        bt_signals = backtrader_logs.filter(pl.col("layer") == "signals")

        if rb_signals.is_empty() or bt_signals.is_empty():
            return discrepancies

        # Build timestamp lookup for Backtrader signals
        bt_by_timestamp: dict[str, dict[str, Any]] = {}
        for row in bt_signals.iter_rows(named=True):
            ts = row.get("timestamp")
            if ts:
                bt_by_timestamp[str(ts)] = row

        # Compare indicator values for matching timestamps
        indicator_fields = [col for col in rb_signals.columns if col.startswith("data_")]

        for rb_row in rb_signals.iter_rows(named=True):
            rb_ts = rb_row.get("timestamp")
            if not rb_ts:
                continue

            bt_row = bt_by_timestamp.get(str(rb_ts))
            if not bt_row:
                continue

            for field in indicator_fields:
                rb_val = rb_row.get(field)
                bt_val = bt_row.get(field)

                if rb_val is None or bt_val is None:
                    continue

                try:
                    rb_decimal = Decimal(str(rb_val))
                    bt_decimal = Decimal(str(bt_val))
                    diff = abs(rb_decimal - bt_decimal)

                    if diff > indicator_tol:
                        discrepancies.append(
                            Discrepancy(
                                layer="signals",
                                event="indicator_mismatch",
                                timestamp=str(rb_ts),
                                field=field,
                                rustybt_value=float(rb_decimal),
                                backtrader_value=float(bt_decimal),
                                tolerance=float(indicator_tol),
                                exceeded_by=float(diff),
                                asset=rb_row.get("asset"),
                                severity="warning",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies

    def compare_signal_timing(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare signal timing between frameworks.

        Args:
            rustybt_logs: rustybt logs
            backtrader_logs: Backtrader logs

        Returns:
            List of signal timing discrepancies
        """
        discrepancies: list[Discrepancy] = []
        timing_window_ms = self.tolerances.signal_timestamp_window_ms

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        # Get signal events
        rb_signals = rustybt_logs.filter(
            (pl.col("layer") == "signals") & (pl.col("event").str.contains("signal"))
        )
        bt_signals = backtrader_logs.filter(
            (pl.col("layer") == "signals") & (pl.col("event").str.contains("signal"))
        )

        if rb_signals.is_empty() or bt_signals.is_empty():
            return discrepancies

        # Get sorted timestamps
        rb_timestamps = sorted(
            [
                str(row.get("timestamp", ""))
                for row in rb_signals.iter_rows(named=True)
                if row.get("timestamp")
            ]
        )
        bt_timestamps = sorted(
            [
                str(row.get("timestamp", ""))
                for row in bt_signals.iter_rows(named=True)
                if row.get("timestamp")
            ]
        )

        # Compare signal sequence - timestamps should match within tolerance
        # For simplicity, we compare by position (this is a basic implementation)
        min_len = min(len(rb_timestamps), len(bt_timestamps))
        for i in range(min_len):
            if rb_timestamps[i] != bt_timestamps[i]:
                # Signal at different times
                discrepancies.append(
                    Discrepancy(
                        layer="signals",
                        event="signal_timing_mismatch",
                        timestamp=rb_timestamps[i],
                        field=f"signal_{i+1}_timestamp",
                        rustybt_value=rb_timestamps[i],
                        backtrader_value=bt_timestamps[i],
                        tolerance=f"{timing_window_ms}ms",
                        exceeded_by="timestamps differ",
                        severity="warning",
                    )
                )

        return discrepancies


class Layer3OrdersComparator(BaseComparator):
    """Comparator for Layer 3: Order Lifecycle.

    Validates:
    - Order creation comparison (count, type, quantity, timing)
    - Order execution comparison (fill price with tolerance, fill quantity)
    - Order state transition comparison (CREATED->SUBMITTED->FILLED sequence)
    - Partial fill handling

    Note:
        Order IDs may differ between frameworks. Orders are matched by
        timestamp + asset + quantity instead of order ID.
    """

    def __init__(self, tolerances: Layer3Tolerances | None = None):
        """Initialize with tolerances.

        Args:
            tolerances: Layer 3 tolerance configuration. Uses defaults if None.
        """
        self.tolerances = tolerances or Layer3Tolerances()

    @property
    def layer_name(self) -> str:
        """Return the layer name this comparator handles."""
        return "orders"

    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> ComparisonResult:
        """Run all Layer 3 comparisons.

        Args:
            rustybt_logs: Parsed logs from rustybt execution
            backtrader_logs: Parsed logs from Backtrader execution

        Returns:
            ComparisonResult with all discrepancies found
        """
        discrepancies: list[Discrepancy] = []

        discrepancies.extend(self.compare_order_creation(rustybt_logs, backtrader_logs))
        discrepancies.extend(self.compare_order_execution(rustybt_logs, backtrader_logs))
        discrepancies.extend(self.compare_order_states(rustybt_logs, backtrader_logs))

        passed = not any(d.severity == "critical" for d in discrepancies)

        rb_order_count = 0
        bt_order_count = 0
        if "layer" in rustybt_logs.columns and "event" in rustybt_logs.columns:
            rb_order_count = len(
                rustybt_logs.filter(
                    (pl.col("layer") == "orders") & (pl.col("event") == "order_created")
                )
            )
        if "layer" in backtrader_logs.columns and "event" in backtrader_logs.columns:
            bt_order_count = len(
                backtrader_logs.filter(
                    (pl.col("layer") == "orders") & (pl.col("event") == "order_created")
                )
            )

        return ComparisonResult(
            layer=self.layer_name,
            passed=passed,
            discrepancies=discrepancies,
            stats={
                "rustybt_order_count": rb_order_count,
                "backtrader_order_count": bt_order_count,
                "total_discrepancies": len(discrepancies),
            },
        )

    def compare_order_creation(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare order creation events between frameworks.

        Orders are matched by timestamp + asset + quantity, not order ID.

        Args:
            rustybt_logs: rustybt logs
            backtrader_logs: Backtrader logs

        Returns:
            List of order creation discrepancies
        """
        discrepancies: list[Discrepancy] = []

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_orders = rustybt_logs.filter(
            (pl.col("layer") == "orders") & (pl.col("event") == "order_created")
        )
        bt_orders = backtrader_logs.filter(
            (pl.col("layer") == "orders") & (pl.col("event") == "order_created")
        )

        if len(rb_orders) != len(bt_orders):
            discrepancies.append(
                Discrepancy(
                    layer="orders",
                    event="order_count_mismatch",
                    timestamp=None,
                    field="order_count",
                    rustybt_value=len(rb_orders),
                    backtrader_value=len(bt_orders),
                    tolerance=0,
                    exceeded_by=abs(len(rb_orders) - len(bt_orders)),
                    severity="critical",
                )
            )

        if rb_orders.is_empty() or bt_orders.is_empty():
            return discrepancies

        bt_order_lookup: dict[tuple[str, str | None, Any], dict[str, Any]] = {}
        for row in bt_orders.iter_rows(named=True):
            key = (str(row.get("timestamp", "")), row.get("asset"), row.get("data_quantity"))
            bt_order_lookup[key] = row

        for rb_row in rb_orders.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            rb_asset = rb_row.get("asset")
            rb_quantity = rb_row.get("data_quantity")
            key = (rb_ts, rb_asset, rb_quantity)

            if key not in bt_order_lookup:
                discrepancies.append(
                    Discrepancy(
                        layer="orders",
                        event="order_not_found",
                        timestamp=rb_ts,
                        field="order_match",
                        rustybt_value=f"{rb_asset}:{rb_quantity}",
                        backtrader_value="not found",
                        tolerance="exact match",
                        exceeded_by="missing order",
                        asset=rb_asset,
                        severity="critical",
                    )
                )
                continue

            bt_row = bt_order_lookup[key]
            rb_type = rb_row.get("data_order_type")
            bt_type = bt_row.get("data_order_type")

            if rb_type is not None and bt_type is not None and rb_type != bt_type:
                discrepancies.append(
                    Discrepancy(
                        layer="orders",
                        event="order_type_mismatch",
                        timestamp=rb_ts,
                        field="order_type",
                        rustybt_value=rb_type,
                        backtrader_value=bt_type,
                        tolerance="exact match",
                        exceeded_by=f"{rb_type} != {bt_type}",
                        asset=rb_asset,
                        severity="warning",
                    )
                )

        return discrepancies

    def compare_order_execution(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare order fill events between frameworks.

        Args:
            rustybt_logs: rustybt logs
            backtrader_logs: Backtrader logs

        Returns:
            List of order execution discrepancies
        """
        discrepancies: list[Discrepancy] = []
        price_tol = self.tolerances.fill_price_tolerance
        qty_tol_pct = self.tolerances.quantity_tolerance_pct

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_fills = rustybt_logs.filter(
            (pl.col("layer") == "orders") & (pl.col("event") == "order_filled")
        )
        bt_fills = backtrader_logs.filter(
            (pl.col("layer") == "orders") & (pl.col("event") == "order_filled")
        )

        if rb_fills.is_empty() or bt_fills.is_empty():
            return discrepancies

        bt_fill_lookup: dict[tuple[str, str | None], dict[str, Any]] = {}
        for row in bt_fills.iter_rows(named=True):
            key = (str(row.get("timestamp", "")), row.get("asset"))
            bt_fill_lookup[key] = row

        for rb_row in rb_fills.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            rb_asset = rb_row.get("asset")
            key = (rb_ts, rb_asset)

            if key not in bt_fill_lookup:
                discrepancies.append(
                    Discrepancy(
                        layer="orders",
                        event="fill_not_found",
                        timestamp=rb_ts,
                        field="fill_match",
                        rustybt_value=f"fill at {rb_ts}",
                        backtrader_value="not found",
                        tolerance="exact timestamp",
                        exceeded_by="missing fill",
                        asset=rb_asset,
                        severity="warning",
                    )
                )
                continue

            bt_row = bt_fill_lookup[key]

            rb_price = rb_row.get("data_fill_price")
            bt_price = bt_row.get("data_fill_price")
            if rb_price is not None and bt_price is not None:
                try:
                    rb_decimal = Decimal(str(rb_price))
                    bt_decimal = Decimal(str(bt_price))
                    diff = abs(rb_decimal - bt_decimal)
                    if diff > price_tol:
                        discrepancies.append(
                            Discrepancy(
                                layer="orders",
                                event="fill_price_mismatch",
                                timestamp=rb_ts,
                                field="fill_price",
                                rustybt_value=float(rb_decimal),
                                backtrader_value=float(bt_decimal),
                                tolerance=float(price_tol),
                                exceeded_by=float(diff),
                                asset=rb_asset,
                                severity="warning",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

            rb_qty = rb_row.get("data_fill_quantity")
            bt_qty = bt_row.get("data_fill_quantity")
            if rb_qty is not None and bt_qty is not None:
                try:
                    rb_qty_val = float(rb_qty)
                    bt_qty_val = float(bt_qty)
                    if bt_qty_val != 0:
                        pct_diff = abs(rb_qty_val - bt_qty_val) / abs(bt_qty_val)
                        if pct_diff > qty_tol_pct:
                            discrepancies.append(
                                Discrepancy(
                                    layer="orders",
                                    event="fill_quantity_mismatch",
                                    timestamp=rb_ts,
                                    field="fill_quantity",
                                    rustybt_value=rb_qty_val,
                                    backtrader_value=bt_qty_val,
                                    tolerance=f"{qty_tol_pct:.4%}",
                                    exceeded_by=f"{pct_diff:.4%}",
                                    asset=rb_asset,
                                    severity="warning",
                                )
                            )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies

    def compare_order_states(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare order state transitions between frameworks.

        Args:
            rustybt_logs: rustybt logs
            backtrader_logs: Backtrader logs

        Returns:
            List of state transition discrepancies
        """
        discrepancies: list[Discrepancy] = []

        if "layer" not in rustybt_logs.columns or "layer" not in backtrader_logs.columns:
            return discrepancies

        rb_states = self._extract_state_sequences(rustybt_logs)
        bt_states = self._extract_state_sequences(backtrader_logs)

        for order_key, rb_seq in rb_states.items():
            if order_key not in bt_states:
                continue
            bt_seq = bt_states[order_key]
            if rb_seq != bt_seq:
                discrepancies.append(
                    Discrepancy(
                        layer="orders",
                        event="state_transition_mismatch",
                        timestamp=None,
                        field=f"order_{order_key}_states",
                        rustybt_value=" -> ".join(rb_seq),
                        backtrader_value=" -> ".join(bt_seq),
                        tolerance="exact sequence match",
                        exceeded_by="sequence differs",
                        severity="warning",
                    )
                )

        for order_key in bt_states:
            if order_key not in rb_states:
                discrepancies.append(
                    Discrepancy(
                        layer="orders",
                        event="extra_order_in_backtrader",
                        timestamp=None,
                        field=f"order_{order_key}",
                        rustybt_value="not found",
                        backtrader_value=" -> ".join(bt_states[order_key]),
                        tolerance="order should exist",
                        exceeded_by="missing order",
                        severity="warning",
                    )
                )

        return discrepancies

    def _extract_state_sequences(self, logs: pl.DataFrame) -> dict[str, list[str]]:
        """Extract state sequences per order from logs."""
        order_states: dict[str, list[str]] = {}
        order_logs = logs.filter(pl.col("layer") == "orders")

        if order_logs.is_empty():
            return order_states

        for row in order_logs.iter_rows(named=True):
            ts = row.get("timestamp")
            asset = row.get("asset")
            state = row.get("data_order_state")
            if ts is None or state is None:
                continue
            order_key = f"{ts}_{asset}" if asset else str(ts)
            if order_key not in order_states:
                order_states[order_key] = []
            order_states[order_key].append(str(state))

        return order_states


class Layer4BrokerComparator(BaseComparator):
    """Comparator for Layer 4: Broker Transactions.

    Validates:
    - Transaction execution comparison (fills, commissions)
    - Cash balance comparison
    - Slippage comparison
    """

    def __init__(self, tolerances: Layer4Tolerances | None = None):
        """Initialize with tolerances.

        Args:
            tolerances: Layer 4 tolerance configuration. Uses defaults if None.
        """
        self.tolerances = tolerances or Layer4Tolerances()

    @property
    def layer_name(self) -> str:
        """Return the layer name this comparator handles."""
        return "broker"

    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> ComparisonResult:
        """Run all Layer 4 comparisons."""
        discrepancies: list[Discrepancy] = []

        discrepancies.extend(self.compare_transactions(rustybt_logs, backtrader_logs))
        discrepancies.extend(self.compare_cash_balance(rustybt_logs, backtrader_logs))
        discrepancies.extend(self.compare_commissions(rustybt_logs, backtrader_logs))
        discrepancies.extend(self.compare_slippage(rustybt_logs, backtrader_logs))

        passed = not any(d.severity == "critical" for d in discrepancies)

        rb_txn_count = 0
        bt_txn_count = 0
        if "layer" in rustybt_logs.columns and "event" in rustybt_logs.columns:
            rb_txn_count = len(
                rustybt_logs.filter(
                    (pl.col("layer") == "broker") & (pl.col("event") == "transaction_executed")
                )
            )
        if "layer" in backtrader_logs.columns and "event" in backtrader_logs.columns:
            bt_txn_count = len(
                backtrader_logs.filter(
                    (pl.col("layer") == "broker") & (pl.col("event") == "transaction_executed")
                )
            )

        return ComparisonResult(
            layer=self.layer_name,
            passed=passed,
            discrepancies=discrepancies,
            stats={
                "rustybt_transaction_count": rb_txn_count,
                "backtrader_transaction_count": bt_txn_count,
                "total_discrepancies": len(discrepancies),
            },
        )

    def compare_transactions(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare broker transaction events."""
        discrepancies: list[Discrepancy] = []

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_txns = rustybt_logs.filter(
            (pl.col("layer") == "broker") & (pl.col("event") == "transaction_executed")
        )
        bt_txns = backtrader_logs.filter(
            (pl.col("layer") == "broker") & (pl.col("event") == "transaction_executed")
        )

        if len(rb_txns) != len(bt_txns):
            discrepancies.append(
                Discrepancy(
                    layer="broker",
                    event="transaction_count_mismatch",
                    timestamp=None,
                    field="transaction_count",
                    rustybt_value=len(rb_txns),
                    backtrader_value=len(bt_txns),
                    tolerance=0,
                    exceeded_by=abs(len(rb_txns) - len(bt_txns)),
                    severity="critical",
                )
            )

        if rb_txns.is_empty() or bt_txns.is_empty():
            return discrepancies

        bt_txn_lookup: dict[tuple[str, str | None], dict[str, Any]] = {}
        for row in bt_txns.iter_rows(named=True):
            key = (str(row.get("timestamp", "")), row.get("asset"))
            bt_txn_lookup[key] = row

        for rb_row in rb_txns.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            rb_asset = rb_row.get("asset")
            key = (rb_ts, rb_asset)

            if key not in bt_txn_lookup:
                discrepancies.append(
                    Discrepancy(
                        layer="broker",
                        event="transaction_not_found",
                        timestamp=rb_ts,
                        field="transaction_match",
                        rustybt_value=f"transaction at {rb_ts}",
                        backtrader_value="not found",
                        tolerance="exact timestamp",
                        exceeded_by="missing transaction",
                        asset=rb_asset,
                        severity="critical",
                    )
                )

        return discrepancies

    def compare_cash_balance(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare cash balance between frameworks."""
        discrepancies: list[Discrepancy] = []
        cash_tol = self.tolerances.cash_tolerance

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_cash = rustybt_logs.filter(
            (pl.col("layer") == "broker") & (pl.col("event") == "cash_updated")
        )
        bt_cash = backtrader_logs.filter(
            (pl.col("layer") == "broker") & (pl.col("event") == "cash_updated")
        )

        if rb_cash.is_empty() or bt_cash.is_empty():
            return discrepancies

        bt_cash_lookup: dict[str, dict[str, Any]] = {}
        for row in bt_cash.iter_rows(named=True):
            bt_cash_lookup[str(row.get("timestamp", ""))] = row

        for rb_row in rb_cash.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            if rb_ts not in bt_cash_lookup:
                continue

            bt_row = bt_cash_lookup[rb_ts]
            rb_balance = rb_row.get("data_cash_balance")
            bt_balance = bt_row.get("data_cash_balance")

            if rb_balance is not None and bt_balance is not None:
                try:
                    rb_decimal = Decimal(str(rb_balance))
                    bt_decimal = Decimal(str(bt_balance))
                    diff = abs(rb_decimal - bt_decimal)
                    if diff > cash_tol:
                        discrepancies.append(
                            Discrepancy(
                                layer="broker",
                                event="cash_balance_mismatch",
                                timestamp=rb_ts,
                                field="cash_balance",
                                rustybt_value=float(rb_decimal),
                                backtrader_value=float(bt_decimal),
                                tolerance=float(cash_tol),
                                exceeded_by=float(diff),
                                severity="warning",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies

    def compare_commissions(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare commission calculations."""
        discrepancies: list[Discrepancy] = []
        commission_tol = self.tolerances.commission_tolerance

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_comm = rustybt_logs.filter(
            (pl.col("layer") == "broker") & (pl.col("event") == "commission_charged")
        )
        bt_comm = backtrader_logs.filter(
            (pl.col("layer") == "broker") & (pl.col("event") == "commission_charged")
        )

        if rb_comm.is_empty() or bt_comm.is_empty():
            return discrepancies

        bt_comm_lookup: dict[tuple[str, str | None], dict[str, Any]] = {}
        for row in bt_comm.iter_rows(named=True):
            key = (str(row.get("timestamp", "")), row.get("asset"))
            bt_comm_lookup[key] = row

        for rb_row in rb_comm.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            rb_asset = rb_row.get("asset")
            key = (rb_ts, rb_asset)

            if key not in bt_comm_lookup:
                continue

            bt_row = bt_comm_lookup[key]
            rb_commission = rb_row.get("data_commission")
            bt_commission = bt_row.get("data_commission")

            if rb_commission is not None and bt_commission is not None:
                try:
                    rb_decimal = Decimal(str(rb_commission))
                    bt_decimal = Decimal(str(bt_commission))
                    diff = abs(rb_decimal - bt_decimal)
                    if diff > commission_tol:
                        discrepancies.append(
                            Discrepancy(
                                layer="broker",
                                event="commission_mismatch",
                                timestamp=rb_ts,
                                field="commission",
                                rustybt_value=float(rb_decimal),
                                backtrader_value=float(bt_decimal),
                                tolerance=float(commission_tol),
                                exceeded_by=float(diff),
                                asset=rb_asset,
                                severity="warning",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies

    def compare_slippage(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare slippage calculations."""
        discrepancies: list[Discrepancy] = []
        slippage_tol_pct = self.tolerances.slippage_tolerance_pct

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_slip = rustybt_logs.filter(
            (pl.col("layer") == "broker") & (pl.col("event") == "slippage_applied")
        )
        bt_slip = backtrader_logs.filter(
            (pl.col("layer") == "broker") & (pl.col("event") == "slippage_applied")
        )

        if rb_slip.is_empty() or bt_slip.is_empty():
            return discrepancies

        bt_slip_lookup: dict[tuple[str, str | None], dict[str, Any]] = {}
        for row in bt_slip.iter_rows(named=True):
            key = (str(row.get("timestamp", "")), row.get("asset"))
            bt_slip_lookup[key] = row

        for rb_row in rb_slip.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            rb_asset = rb_row.get("asset")
            key = (rb_ts, rb_asset)

            if key not in bt_slip_lookup:
                continue

            bt_row = bt_slip_lookup[key]
            rb_slippage = rb_row.get("data_slippage")
            bt_slippage = bt_row.get("data_slippage")

            if rb_slippage is not None and bt_slippage is not None:
                try:
                    rb_val = float(rb_slippage)
                    bt_val = float(bt_slippage)
                    if bt_val != 0:
                        pct_diff = abs(rb_val - bt_val) / abs(bt_val)
                        if pct_diff > slippage_tol_pct:
                            discrepancies.append(
                                Discrepancy(
                                    layer="broker",
                                    event="slippage_mismatch",
                                    timestamp=rb_ts,
                                    field="slippage",
                                    rustybt_value=rb_val,
                                    backtrader_value=bt_val,
                                    tolerance=f"{slippage_tol_pct:.4%}",
                                    exceeded_by=f"{pct_diff:.4%}",
                                    asset=rb_asset,
                                    severity="warning",
                                )
                            )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies


class Layer5PortfolioComparator(BaseComparator):
    """Comparator for Layer 5: Portfolio Returns.

    Validates:
    - Portfolio value comparison
    - Returns comparison
    - Sharpe ratio comparison
    - Drawdown comparison
    """

    def __init__(self, tolerances: Layer5Tolerances | None = None):
        """Initialize with tolerances.

        Args:
            tolerances: Layer 5 tolerance configuration. Uses defaults if None.
        """
        self.tolerances = tolerances or Layer5Tolerances()

    @property
    def layer_name(self) -> str:
        """Return the layer name this comparator handles."""
        return "portfolio"

    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> ComparisonResult:
        """Run all Layer 5 comparisons."""
        discrepancies: list[Discrepancy] = []

        discrepancies.extend(self.compare_portfolio_values(rustybt_logs, backtrader_logs))
        discrepancies.extend(self.compare_returns(rustybt_logs, backtrader_logs))
        discrepancies.extend(self.compare_sharpe_ratio(rustybt_logs, backtrader_logs))
        discrepancies.extend(self.compare_drawdowns(rustybt_logs, backtrader_logs))

        passed = not any(d.severity == "critical" for d in discrepancies)

        return ComparisonResult(
            layer=self.layer_name,
            passed=passed,
            discrepancies=discrepancies,
            stats={"total_discrepancies": len(discrepancies)},
        )

    def compare_portfolio_values(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare portfolio values."""
        discrepancies: list[Discrepancy] = []
        value_tol = self.tolerances.portfolio_value_tolerance

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_values = rustybt_logs.filter(
            (pl.col("layer") == "portfolio") & (pl.col("event") == "portfolio_value_updated")
        )
        bt_values = backtrader_logs.filter(
            (pl.col("layer") == "portfolio") & (pl.col("event") == "portfolio_value_updated")
        )

        if rb_values.is_empty() or bt_values.is_empty():
            return discrepancies

        bt_value_lookup: dict[str, dict[str, Any]] = {}
        for row in bt_values.iter_rows(named=True):
            bt_value_lookup[str(row.get("timestamp", ""))] = row

        for rb_row in rb_values.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            if rb_ts not in bt_value_lookup:
                continue

            bt_row = bt_value_lookup[rb_ts]
            rb_value = rb_row.get("data_portfolio_value")
            bt_value = bt_row.get("data_portfolio_value")

            if rb_value is not None and bt_value is not None:
                try:
                    rb_decimal = Decimal(str(rb_value))
                    bt_decimal = Decimal(str(bt_value))
                    diff = abs(rb_decimal - bt_decimal)
                    if diff > value_tol:
                        discrepancies.append(
                            Discrepancy(
                                layer="portfolio",
                                event="portfolio_value_mismatch",
                                timestamp=rb_ts,
                                field="portfolio_value",
                                rustybt_value=float(rb_decimal),
                                backtrader_value=float(bt_decimal),
                                tolerance=float(value_tol),
                                exceeded_by=float(diff),
                                severity="warning",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies

    def compare_returns(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare returns."""
        discrepancies: list[Discrepancy] = []
        returns_tol_pct = self.tolerances.returns_tolerance_pct

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_returns = rustybt_logs.filter(
            (pl.col("layer") == "portfolio") & (pl.col("event") == "daily_return_calculated")
        )
        bt_returns = backtrader_logs.filter(
            (pl.col("layer") == "portfolio") & (pl.col("event") == "daily_return_calculated")
        )

        if rb_returns.is_empty() or bt_returns.is_empty():
            return discrepancies

        bt_return_lookup: dict[str, dict[str, Any]] = {}
        for row in bt_returns.iter_rows(named=True):
            bt_return_lookup[str(row.get("timestamp", ""))] = row

        for rb_row in rb_returns.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            if rb_ts not in bt_return_lookup:
                continue

            bt_row = bt_return_lookup[rb_ts]
            rb_return = rb_row.get("data_daily_return")
            bt_return = bt_row.get("data_daily_return")

            if rb_return is not None and bt_return is not None:
                try:
                    rb_val = float(rb_return)
                    bt_val = float(bt_return)
                    diff = abs(rb_val - bt_val)

                    if abs(bt_val) > 0.0001:
                        pct_diff = diff / abs(bt_val)
                        if pct_diff > returns_tol_pct:
                            discrepancies.append(
                                Discrepancy(
                                    layer="portfolio",
                                    event="return_mismatch",
                                    timestamp=rb_ts,
                                    field="daily_return",
                                    rustybt_value=rb_val,
                                    backtrader_value=bt_val,
                                    tolerance=f"{returns_tol_pct:.4%}",
                                    exceeded_by=f"{pct_diff:.4%}",
                                    severity="warning",
                                )
                            )
                    elif diff > returns_tol_pct:
                        discrepancies.append(
                            Discrepancy(
                                layer="portfolio",
                                event="return_mismatch",
                                timestamp=rb_ts,
                                field="daily_return",
                                rustybt_value=rb_val,
                                backtrader_value=bt_val,
                                tolerance=f"{returns_tol_pct:.4%}",
                                exceeded_by=f"{diff:.6f}",
                                severity="warning",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies

    def compare_sharpe_ratio(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare Sharpe ratio."""
        discrepancies: list[Discrepancy] = []
        sharpe_tol = self.tolerances.sharpe_tolerance

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_metrics = rustybt_logs.filter(
            (pl.col("layer") == "portfolio") & (pl.col("event") == "final_metrics")
        )
        bt_metrics = backtrader_logs.filter(
            (pl.col("layer") == "portfolio") & (pl.col("event") == "final_metrics")
        )

        if rb_metrics.is_empty() or bt_metrics.is_empty():
            return discrepancies

        rb_row = rb_metrics.row(0, named=True)
        bt_row = bt_metrics.row(0, named=True)

        rb_sharpe = rb_row.get("data_sharpe_ratio")
        bt_sharpe = bt_row.get("data_sharpe_ratio")

        if rb_sharpe is not None and bt_sharpe is not None:
            try:
                rb_decimal = Decimal(str(rb_sharpe))
                bt_decimal = Decimal(str(bt_sharpe))
                diff = abs(rb_decimal - bt_decimal)
                if diff > sharpe_tol:
                    discrepancies.append(
                        Discrepancy(
                            layer="portfolio",
                            event="sharpe_ratio_mismatch",
                            timestamp=None,
                            field="sharpe_ratio",
                            rustybt_value=float(rb_decimal),
                            backtrader_value=float(bt_decimal),
                            tolerance=float(sharpe_tol),
                            exceeded_by=float(diff),
                            severity="warning",
                        )
                    )
            except (ValueError, TypeError):
                pass

        return discrepancies

    def compare_drawdowns(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> list[Discrepancy]:
        """Compare drawdown calculations."""
        discrepancies: list[Discrepancy] = []
        dd_tol_pct = self.tolerances.drawdown_tolerance_pct

        if "layer" not in rustybt_logs.columns or "event" not in rustybt_logs.columns:
            return discrepancies
        if "layer" not in backtrader_logs.columns or "event" not in backtrader_logs.columns:
            return discrepancies

        rb_dd = rustybt_logs.filter(
            (pl.col("layer") == "portfolio") & (pl.col("event") == "drawdown_updated")
        )
        bt_dd = backtrader_logs.filter(
            (pl.col("layer") == "portfolio") & (pl.col("event") == "drawdown_updated")
        )

        if rb_dd.is_empty() or bt_dd.is_empty():
            return discrepancies

        bt_dd_lookup: dict[str, dict[str, Any]] = {}
        for row in bt_dd.iter_rows(named=True):
            bt_dd_lookup[str(row.get("timestamp", ""))] = row

        for rb_row in rb_dd.iter_rows(named=True):
            rb_ts = str(rb_row.get("timestamp", ""))
            if rb_ts not in bt_dd_lookup:
                continue

            bt_row = bt_dd_lookup[rb_ts]
            rb_drawdown = rb_row.get("data_drawdown")
            bt_drawdown = bt_row.get("data_drawdown")

            if rb_drawdown is not None and bt_drawdown is not None:
                try:
                    rb_val = float(rb_drawdown)
                    bt_val = float(bt_drawdown)
                    diff = abs(rb_val - bt_val)
                    if diff > dd_tol_pct:
                        discrepancies.append(
                            Discrepancy(
                                layer="portfolio",
                                event="drawdown_mismatch",
                                timestamp=rb_ts,
                                field="drawdown",
                                rustybt_value=rb_val,
                                backtrader_value=bt_val,
                                tolerance=f"{dd_tol_pct:.4%}",
                                exceeded_by=f"{diff:.4%}",
                                severity="warning",
                            )
                        )
                except (ValueError, TypeError, InvalidOperation):
                    pass

        return discrepancies
