"""Simple Backtrader strategy for validation testing.

This module provides a minimal strategy that:
1. Extends BacktraderValidatedStrategy
2. Logs events during execution
3. Produces JSONL output for comparison

Used by integration tests to verify subprocess execution works correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.validation.strategies.bt_strategies.base_validated import (
    BacktraderValidatedStrategy,
)

if TYPE_CHECKING:
    pass


class SimpleStrategy(BacktraderValidatedStrategy):
    """Minimal validated Backtrader strategy for testing.

    This strategy simply logs initialization and each data bar.
    It doesn't perform any trading logic - it's for testing the
    execution pipeline.

    Parameters (via params tuple)
    -----------------------------
    log_path : Path | str
        Path to the JSONL log file (inherited from base).
    """

    # Don't redefine params - we inherit from BacktraderValidatedStrategy
    # which already defines params = (("log_path", None),)

    def __init__(self) -> None:
        """Initialize the simple strategy."""
        super().__init__()
        # Log that we initialized (additional to base init log)
        self._log_event(
            layer="data",
            event="simple_init",
            data={"params": {}},
        )

    def next(self) -> None:
        """Process the current bar and log the event."""
        super().next()
        # Log a simple signal event
        self._log_event(
            layer="signals",
            event="simple_signal",
            data={"signal_value": 1.0},
        )
