"""Backtest infrastructure for RustyBT.

This package provides utilities for managing backtest artifacts, including:
- Unique backtest ID generation
- Directory structure management
- Result organization
- Strategy code capture via import analysis
"""

from rustybt.backtest.artifact_manager import BacktestArtifactManager
from rustybt.backtest.code_capture import CodeCaptureError, StrategyCodeCapture

__all__ = ["BacktestArtifactManager", "CodeCaptureError", "StrategyCodeCapture"]
