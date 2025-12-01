r"""CLI wrapper for Backtrader strategy execution.

This script provides a command-line interface for executing Backtrader strategies
in isolation. It is called by the subprocess runner (runner.py) to ensure
clean separation between Backtrader and rustybt executions.

Usage:
    python -m rustybt.validation.execute_backtrader \
        --strategy module.path.ClassName \
        --data /path/to/data.parquet \
        --output /path/to/output.jsonl \
        [--params '{"key": "value"}']

Exit Codes:
    0: Success - strategy executed and log file produced
    1: Failure - error during import, loading, or execution

Note:
    - Strategy module path should include the class name (e.g., "module.Strategy")
    - If class name is omitted, defaults to "Strategy"
    - Data file must be in Parquet format
    - Output directory will be created if it doesn't exist
    - Strategy must extend BacktraderValidatedStrategy
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
from datetime import datetime
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
        Example: "tests.validation.strategies.bt_strategies.sma.SMAStrategy"

    Returns:
    -------
    type
        The strategy class.

    Raises:
    ------
    SystemExit
        If the module or class cannot be imported (exit code 1).

    Examples:
    --------
    >>> StrategyClass = import_strategy("my_module.MyStrategy")
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


def load_backtrader_data(data_path: Path, asset: str | None = None) -> tuple[Any, str | None]:
    """Load Parquet data into a Backtrader-compatible feed.

    Converts Parquet data to Pandas DataFrame and creates a
    bt.feeds.PandasData feed for Backtrader consumption.

    Parameters
    ----------
    data_path : Path
        Path to the Parquet data file.
    asset : str | None, optional
        Asset symbol to filter for (if data has multiple assets).
        If None and data has multiple assets, uses the first asset.

    Returns:
    -------
    tuple[bt.feeds.PandasData, str | None]
        Tuple of (Backtrader data feed, asset name).

    Raises:
    ------
    SystemExit
        If the data file doesn't exist or cannot be loaded (exit code 1).
    """
    if not data_path.exists():
        print(f"Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import backtrader as bt
        import polars as pl

        # Load data with Polars
        df_pl = pl.read_parquet(data_path)

        # Normalize column names to lowercase
        df_pl = df_pl.rename({col: col.lower() for col in df_pl.columns})

        # Track asset name for data feed naming
        asset_name: str | None = asset

        # If multi-asset data, filter to single asset
        if "asset" in df_pl.columns:
            unique_assets = sorted(
                df_pl["asset"].unique().to_list()
            )  # Sort for deterministic selection
            if len(unique_assets) > 1:
                if asset_name is None:
                    asset_name = unique_assets[0]  # Use first asset alphabetically
                    print(
                        f"Multi-asset data detected. Using first asset: {asset_name}",
                        file=sys.stderr,
                    )
                df_pl = df_pl.filter(pl.col("asset") == asset_name)
            elif len(unique_assets) == 1:
                asset_name = unique_assets[0]
            # Drop asset column for Backtrader
            df_pl = df_pl.drop("asset")

        # Handle datetime column - Backtrader needs it as index
        datetime_col = None
        for col in ["timestamp", "datetime", "date"]:
            if col in df_pl.columns:
                datetime_col = col
                break

        if datetime_col is None:
            print(
                "No datetime column found in data (expected: timestamp, datetime, or date)",
                file=sys.stderr,
            )
            sys.exit(1)

        # Sort by datetime
        df_pl = df_pl.sort(datetime_col)

        # Convert to Pandas
        df = df_pl.to_pandas()

        # Set datetime as index
        df[datetime_col] = df[datetime_col].apply(
            lambda x: (
                x
                if isinstance(x, datetime)
                else (
                    x.to_pydatetime()
                    if hasattr(x, "to_pydatetime")
                    else datetime.fromisoformat(str(x))
                )
            )
        )
        df.set_index(datetime_col, inplace=True)

        # Ensure required OHLCV columns exist
        required_cols = {"open", "high", "low", "close", "volume"}
        existing_cols = set(df.columns.str.lower())

        # Check for required columns
        missing = required_cols - existing_cols
        if missing:
            # Try to map common column name variations
            col_mapping = {
                "adj close": "close",
                "adj_close": "close",
            }
            for old_name, new_name in col_mapping.items():
                if old_name in df.columns and new_name not in df.columns:
                    df[new_name] = df[old_name]

        # Create Backtrader data feed
        return bt.feeds.PandasData(dataname=df), asset_name

    except ImportError as e:
        print(f"Failed to import required library: {e}", file=sys.stderr)
        print("Make sure backtrader and polars are installed", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to load data from {data_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


def validate_params(params_json: str | None) -> dict[str, Any]:
    """Validate and parse JSON parameters.

    Parameters
    ----------
    params_json : str | None
        JSON string of parameters, or None.

    Returns:
    -------
    dict[str, Any]
        Parsed parameters dictionary.

    Raises:
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
            print(
                f"Invalid params: expected JSON object, got {type(result).__name__}",
                file=sys.stderr,
            )
            sys.exit(1)
        return result
    except json.JSONDecodeError as e:
        print(f"Invalid params JSON: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for the Backtrader execution wrapper.

    Parses command line arguments, imports the strategy, loads data,
    and executes the strategy with validation logging using Cerebro.
    """
    parser = argparse.ArgumentParser(
        description="Execute Backtrader strategy with validation logging"
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

    # Import required libraries
    try:
        import backtrader as bt
    except ImportError:
        print("Backtrader is not installed. Install with: pip install backtrader", file=sys.stderr)
        sys.exit(1)

    # Import strategy class
    strategy_class = import_strategy(args.strategy)

    # Load data (returns tuple of data feed and asset name)
    data_feed, asset_name = load_backtrader_data(args.data)

    # Custom commission class for fixed per-trade commission
    class FixedTradeCommission(bt.CommInfoBase):
        """Fixed commission per trade (not per share)."""

        params = (
            ("commission", 1.0),  # $1 per trade
            ("stocklike", True),
            ("commtype", bt.CommInfoBase.COMM_FIXED),
        )

        def _getcommission(self, size, price, pseudoexec):
            """Return fixed commission per trade."""
            return self.p.commission  # Always $1 regardless of size

    try:
        # Create Cerebro engine
        cerebro = bt.Cerebro()

        # Configure broker with starting cash and commission
        # Starting cash: $100,000
        cerebro.broker.setcash(100000.0)

        # Commission: $1 fixed per trade (using custom commission class)
        cerebro.broker.addcommissioninfo(FixedTradeCommission())

        # Add data feed with asset name for identification
        cerebro.adddata(data_feed, name=asset_name or "data")

        # Add strategy with log_path and any additional params
        # BacktraderValidatedStrategy expects log_path as a param
        strategy_params = {"log_path": str(args.output)}
        strategy_params.update(args.params)
        cerebro.addstrategy(strategy_class, **strategy_params)

        # Run the backtest
        cerebro.run()

        sys.exit(0)
    except Exception as e:
        print(f"Execution failed: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
