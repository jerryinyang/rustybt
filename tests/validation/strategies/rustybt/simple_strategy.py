"""Simple rustybt strategy for validation testing.

This module provides a minimal strategy that:
1. Extends RustyBTValidatedStrategy
2. Logs events during execution
3. Produces JSONL output for comparison

Used by integration tests to verify subprocess execution works correctly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rustybt.validation.base_strategy import RustyBTValidatedStrategy


class SimpleStrategy(RustyBTValidatedStrategy):
    """Minimal validated strategy for testing.

    This strategy simply logs initialization and each data bar.
    It doesn't perform any trading logic - it's for testing the
    execution pipeline.

    Parameters
    ----------
    log_path : Path
        Path to the JSONL log file.
    """

    def __init__(self, log_path: Path, **params: Any) -> None:  # noqa: ANN401
        """Initialize the simple strategy.

        Parameters
        ----------
        log_path : Path
            Path to the JSONL log file.
        **params : Any
            Additional parameters (ignored for simple strategy).
        """
        super().__init__(log_path)
        self._params = params

    def initialize(self, context: Any) -> None:  # noqa: ANN401
        """Initialize strategy and log the event.

        Parameters
        ----------
        context : Any
            The strategy context object.
        """
        super().initialize(context)
        # Log that we initialized with params
        self._log_event(
            layer="data",
            event="simple_init",
            data={"params": self._params},
        )

    def handle_data(self, context: Any, data: Any) -> None:  # noqa: ANN401
        """Process bar data and log the event.

        Parameters
        ----------
        context : Any
            The strategy context object.
        data : Any
            The bar data object.
        """
        super().handle_data(context, data)
        # Log a simple signal event
        self._log_event(
            layer="signals",
            event="simple_signal",
            data={"signal_value": 1.0},
        )
