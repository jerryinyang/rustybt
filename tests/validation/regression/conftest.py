"""Shared fixtures for regression tests.

These fixtures provide common functionality for regression tests generated
from verified bug fixes.
"""

from pathlib import Path

import polars as pl
import pytest

from rustybt.validation.log_parser import parse_log


@pytest.fixture
def regression_test_logs(request):
    """Load logs for regression test based on strategy.

    This fixture attempts to load strategy logs from:
    1. A marker-specified session directory
    2. The default latest validation session

    Example usage in test:
        @pytest.mark.session_dir("validation-sessions/20251127-120000-sma_crossover")
        def test_regression(regression_test_logs):
            rb_logs = regression_test_logs["rustybt"]
            bt_logs = regression_test_logs["backtrader"]
    """
    # Check for session_dir marker
    session_marker = request.node.get_closest_marker("session_dir")
    if session_marker:
        logs_dir = Path(session_marker.args[0]) / "logs"
    else:
        # Default to looking for latest session
        sessions_dir = Path("validation-sessions")
        if sessions_dir.exists():
            # Find most recent session
            sessions = sorted(sessions_dir.iterdir(), reverse=True)
            for session in sessions:
                if (session / "logs" / "rustybt.jsonl").exists():
                    logs_dir = session / "logs"
                    break
            else:
                pytest.skip("No validation session with logs found")
        else:
            pytest.skip("No validation-sessions directory found")

    rb_log = logs_dir / "rustybt.jsonl"
    bt_log = logs_dir / "backtrader.jsonl"

    if not rb_log.exists() or not bt_log.exists():
        pytest.skip(f"Log files not found in {logs_dir}")

    return {
        "rustybt": parse_log(rb_log),
        "backtrader": parse_log(bt_log),
    }


@pytest.fixture
def sma_crossover_logs(request):
    """Load logs specifically for SMA crossover strategy tests.

    This is a convenience fixture for the common SMA crossover strategy
    used in many validation tests.
    """
    # Try to find sma_crossover session
    sessions_dir = Path("validation-sessions")
    if not sessions_dir.exists():
        pytest.skip("No validation-sessions directory")

    for session_dir in sorted(sessions_dir.iterdir(), reverse=True):
        if "sma_crossover" in session_dir.name.lower():
            logs_dir = session_dir / "logs"
            if (logs_dir / "rustybt.jsonl").exists():
                return {
                    "rustybt": parse_log(logs_dir / "rustybt.jsonl"),
                    "backtrader": parse_log(logs_dir / "backtrader.jsonl"),
                }

    pytest.skip("No SMA crossover session with logs found")
