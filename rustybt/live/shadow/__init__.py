"""Shadow trading validation framework.

This module provides shadow trading functionality that runs a backtest engine
in parallel with live trading to validate signal alignment and execution quality.
"""

from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.dashboard import AlignmentDashboard
from rustybt.live.shadow.engine import ShadowBacktestEngine
from rustybt.live.shadow.execution_tracker import ExecutionQualityTracker
from rustybt.live.shadow.signal_validator import SignalAlignmentValidator
from rustybt.live.shadow.alignment_breaker import AlignmentCircuitBreaker
from rustybt.live.shadow.models import (
    AlignmentMetrics,
    ExecutionQualityMetrics,
    SignalAlignment,
    SignalRecord,
)

__all__ = [
    "ShadowTradingConfig",
    "AlignmentDashboard",
    "ShadowBacktestEngine",
    "ExecutionQualityTracker",
    "SignalAlignmentValidator",
    "AlignmentCircuitBreaker",
    "AlignmentMetrics",
    "ExecutionQualityMetrics",
    "SignalAlignment",
    "SignalRecord",
]
