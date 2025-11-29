"""Subprocess execution runner for strategy validation.

This module provides functions to execute rustybt and Backtrader strategies
in isolated subprocesses. This approach prevents dependency conflicts between
the two frameworks during validation testing.

The runners use subprocess.run() with the same Python interpreter (sys.executable)
to ensure consistent environments. Each runner captures stdout/stderr for
error diagnostics and enforces configurable timeouts.

Architecture Note:
    Running frameworks in separate subprocesses is mandated by ADR-004.
    This prevents import conflicts and provides clean isolation for comparison.

Example:
    >>> from pathlib import Path
    >>> from rustybt.validation.runner import run_rustybt_strategy
    >>>
    >>> result = run_rustybt_strategy(
    ...     strategy_module="tests.validation.strategies.rustybt.sma.SMAStrategy",
    ...     data_path=Path("/data/test.parquet"),
    ...     output_log=Path("/logs/rustybt.jsonl"),
    ...     params={"sma_period": 20},
    ...     timeout=60
    ... )
    >>> print(result.returncode)
    0
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Default timeout for strategy execution (5 minutes)
DEFAULT_TIMEOUT = 300


def run_rustybt_strategy(
    strategy_module: str,
    data_path: Path,
    output_log: Path,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Execute a rustybt strategy in an isolated subprocess.

    This function runs the specified strategy using rustybt's execution wrapper
    in a separate subprocess. This ensures clean isolation from any Backtrader
    imports that might exist in the parent process.

    Parameters
    ----------
    strategy_module : str
        Python module path to the strategy class, in the format
        "module.path.ClassName" (e.g., "tests.validation.strategies.rustybt.sma.SMAStrategy").
    data_path : Path
        Path to the data fixture file (Parquet format).
    output_log : Path
        Path for the JSONL log output file.
    params : dict[str, Any] | None, optional
        Optional dictionary of strategy parameters to pass, by default None.
    timeout : int, optional
        Execution timeout in seconds, by default 300 (5 minutes).

    Returns
    -------
    subprocess.CompletedProcess[str]
        Completed process object with returncode, stdout, and stderr.
        - returncode: 0 on success, 1 on failure
        - stdout: Captured standard output as string
        - stderr: Captured standard error as string

    Raises
    ------
    subprocess.TimeoutExpired
        If execution exceeds the specified timeout.

    Examples
    --------
    >>> result = run_rustybt_strategy(
    ...     strategy_module="my_module.MyStrategy",
    ...     data_path=Path("data.parquet"),
    ...     output_log=Path("output.jsonl")
    ... )
    >>> if result.returncode != 0:
    ...     print(f"Error: {result.stderr}")

    Notes
    -----
    - Uses sys.executable to ensure the same Python interpreter
    - Parameters are JSON serialized for command line passing
    - Strategy must extend RustyBTValidatedStrategy base class
    """
    cmd = [
        sys.executable,
        "-m",
        "rustybt.validation.execute_rustybt",
        "--strategy",
        strategy_module,
        "--data",
        str(data_path),
        "--output",
        str(output_log),
    ]

    if params:
        cmd.extend(["--params", json.dumps(params)])

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_backtrader_strategy(
    strategy_module: str,
    data_path: Path,
    output_log: Path,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Execute a Backtrader strategy in an isolated subprocess.

    This function runs the specified strategy using Backtrader's execution wrapper
    in a separate subprocess. This ensures clean isolation from any rustybt
    imports that might exist in the parent process.

    Parameters
    ----------
    strategy_module : str
        Python module path to the strategy class, in the format
        "module.path.ClassName" (e.g., "tests.validation.strategies.bt_strategies.sma.SMAStrategy").
    data_path : Path
        Path to the data fixture file (Parquet format).
    output_log : Path
        Path for the JSONL log output file.
    params : dict[str, Any] | None, optional
        Optional dictionary of strategy parameters to pass, by default None.
    timeout : int, optional
        Execution timeout in seconds, by default 300 (5 minutes).

    Returns
    -------
    subprocess.CompletedProcess[str]
        Completed process object with returncode, stdout, and stderr.
        - returncode: 0 on success, 1 on failure
        - stdout: Captured standard output as string
        - stderr: Captured standard error as string

    Raises
    ------
    subprocess.TimeoutExpired
        If execution exceeds the specified timeout.

    Examples
    --------
    >>> result = run_backtrader_strategy(
    ...     strategy_module="my_module.MyBTStrategy",
    ...     data_path=Path("data.parquet"),
    ...     output_log=Path("bt_output.jsonl")
    ... )
    >>> if result.returncode != 0:
    ...     print(f"Error: {result.stderr}")

    Notes
    -----
    - Uses sys.executable to ensure the same Python interpreter
    - Parameters are JSON serialized for command line passing
    - Strategy must extend BacktraderValidatedStrategy base class
    """
    cmd = [
        sys.executable,
        "-m",
        "rustybt.validation.execute_backtrader",
        "--strategy",
        strategy_module,
        "--data",
        str(data_path),
        "--output",
        str(output_log),
    ]

    if params:
        cmd.extend(["--params", json.dumps(params)])

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
