"""CLI wrapper for rustybt strategy execution.

This script provides a command-line interface for executing rustybt strategies
in isolation. It is called by the subprocess runner (runner.py) to ensure
clean separation between rustybt and Backtrader executions.

Usage:
    python -m rustybt.validation.execute_rustybt \\
        --strategy module.path.ClassName \\
        --data /path/to/data.parquet \\
        --output /path/to/output.jsonl \\
        [--params '{"key": "value"}']

Exit Codes:
    0: Success - strategy executed and log file produced
    1: Failure - error during import, loading, or execution

Note:
    - Strategy module path should include the class name (e.g., "module.Strategy")
    - If class name is omitted, defaults to "Strategy"
    - Data file must be in Parquet format
    - Output directory will be created if it doesn't exist
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def import_strategy(module_path: str) -> type:
    """Import a strategy class from a dotted module path.

    The module path can be in one of two formats:
    - "module.path.ClassName" - full path including class name
    - "module.path" - module path only, defaults to "Strategy" class

    Parameters
    ----------
    module_path : str
        Dotted module path to the strategy class.
        Example: "tests.validation.strategies.rustybt.sma.SMAStrategy"

    Returns
    -------
    type
        The strategy class.

    Raises
    ------
    SystemExit
        If the module or class cannot be imported (exit code 1).

    Examples
    --------
    >>> StrategyClass = import_strategy("my_module.MyStrategy")
    >>> strategy = StrategyClass(log_path=Path("output.jsonl"))
    """
    parts = module_path.rsplit(".", 1)
    if len(parts) == 2:
        module_name, class_name = parts
    else:
        module_name = parts[0]
        class_name = "Strategy"  # Default class name

    try:
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except ImportError as e:
        print(f"Could not import strategy: {module_path}", file=sys.stderr)
        print(f"Import error: {e}", file=sys.stderr)
        sys.exit(1)
    except AttributeError as e:
        print(f"Could not import strategy: {module_path}", file=sys.stderr)
        print(f"Class '{class_name}' not found in module '{module_name}'", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def load_data(data_path: Path) -> Any:  # noqa: ANN401
    """Load data from a Parquet file.

    Parameters
    ----------
    data_path : Path
        Path to the Parquet data file.

    Returns
    -------
    polars.DataFrame
        Loaded data as a Polars DataFrame.

    Raises
    ------
    SystemExit
        If the data file doesn't exist or cannot be loaded (exit code 1).
    """
    if not data_path.exists():
        print(f"Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import polars as pl

        return pl.read_parquet(data_path)
    except Exception as e:
        print(f"Failed to load data from {data_path}: {e}", file=sys.stderr)
        sys.exit(1)


def validate_params(params_json: str | None) -> dict[str, Any]:
    """Validate and parse JSON parameters.

    Parameters
    ----------
    params_json : str | None
        JSON string of parameters, or None.

    Returns
    -------
    dict[str, Any]
        Parsed parameters dictionary.

    Raises
    ------
    SystemExit
        If params_json is not valid JSON (exit code 1).
    """
    if params_json is None:
        return {}

    # argparse json.loads already handles parsing, but verify it's a dict
    if isinstance(params_json, dict):
        return params_json

    try:
        result = json.loads(params_json)
        if not isinstance(result, dict):
            print(f"Invalid params: expected JSON object, got {type(result).__name__}", file=sys.stderr)
            sys.exit(1)
        return result
    except json.JSONDecodeError as e:
        print(f"Invalid params JSON: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for the rustybt execution wrapper.

    Parses command line arguments, imports the strategy, loads data,
    and executes the strategy with validation logging.
    """
    parser = argparse.ArgumentParser(
        description="Execute rustybt strategy with validation logging"
    )
    parser.add_argument(
        "--strategy",
        required=True,
        help="Strategy module.class path (e.g., 'my_module.MyStrategy')",
    )
    parser.add_argument(
        "--data",
        required=True,
        type=Path,
        help="Path to data fixture (Parquet format)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path for JSONL log output",
    )
    parser.add_argument(
        "--params",
        type=json.loads,
        default={},
        help="Strategy parameters as JSON object",
    )
    args = parser.parse_args()

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Import strategy class
    strategy_class = import_strategy(args.strategy)

    # Load data
    data = load_data(args.data)

    try:
        # Execute strategy with logging
        # RustyBTValidatedStrategy expects log_path as first positional or keyword arg
        strategy = strategy_class(log_path=args.output, **args.params)

        # Run the strategy through the data
        # The strategy's initialize and handle_data methods log automatically
        strategy.initialize(context=None)

        # Iterate through data and call handle_data for each row
        for row_idx in range(len(data)):
            # Extract individual row as a dict for the strategy
            row = data.row(row_idx, named=True)
            strategy.handle_data(context=None, data=row)

        # Clean up
        strategy.close()

        sys.exit(0)
    except Exception as e:
        print(f"Execution failed: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
