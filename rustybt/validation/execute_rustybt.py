r"""CLI wrapper for rustybt strategy execution using real backtest engine.

This script provides a command-line interface for executing rustybt strategies
using rustybt's actual TradingAlgorithm engine. It replaces the previous
homebrew implementation that manually iterated through data rows.

Epic X Implementation:
    - Uses run_algorithm() from rustybt.utils.run_algo for real backtest execution
    - Registers validation fixture as a rustybt bundle for proper data loading
    - Strategies run through rustybt's actual broker simulation
    - All portfolio/position tracking comes from real rustybt engine

Usage:
    python -m rustybt.validation.execute_rustybt \
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
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

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
        sys.stderr.write(f"Could not import strategy: {module_path}\n")
        sys.stderr.write(f"Import error: {e}\n")
        sys.exit(1)
    except AttributeError as e:
        sys.stderr.write(f"Could not import strategy: {module_path}\n")
        sys.stderr.write(f"Class '{class_name}' not found in module '{module_name}'\n")
        sys.stderr.write(f"Error: {e}\n")
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
            sys.stderr.write(f"Invalid params: expected JSON object, got {type(result).__name__}\n")
            sys.exit(1)
        return result
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Invalid params JSON: {e}\n")
        sys.exit(1)


def register_validation_bundle(
    parquet_path: Path,
    bundle_name: str = "validation-fixture",
    calendar_name: str = "24/7",
) -> tuple[pd.Timestamp, pd.Timestamp, list[str]]:
    """Register a Parquet fixture as a rustybt data bundle.

    This function creates a temporary bundle registration that allows
    rustybt's DataPortal to load the validation fixture through its
    native data loading infrastructure.

    Parameters
    ----------
    parquet_path : Path
        Path to the Parquet data file.
    bundle_name : str, optional
        Name for the bundle, by default "validation-fixture".
    calendar_name : str, optional
        Trading calendar to use, by default "24/7" for continuous trading.

    Returns:
    -------
    tuple[pd.Timestamp, pd.Timestamp, list[str]]
        Start date, end date, and list of asset symbols from the fixture.

    Raises:
    ------
    SystemExit
        If the data file doesn't exist or cannot be loaded.
    """
    import polars as pl

    from rustybt.data.bundles import register

    if not parquet_path.exists():
        sys.stderr.write(f"Data file not found: {parquet_path}\n")
        sys.exit(1)

    # Load fixture to extract metadata
    try:
        df = pl.read_parquet(parquet_path)
        df = df.rename({col: col.lower() for col in df.columns})
    except (OSError, pl.exceptions.ComputeError) as e:
        sys.stderr.write(f"Failed to load data from {parquet_path}: {e}\n")
        sys.exit(1)

    # Extract date range
    datetime_col = None
    for col in ["timestamp", "datetime", "date"]:
        if col in df.columns:
            datetime_col = col
            break

    if datetime_col is None:
        sys.stderr.write(f"No datetime column found in {parquet_path}\n")
        sys.exit(1)

    # Get date range
    df = df.sort(datetime_col)
    start_ts = df[datetime_col].min()
    end_ts = df[datetime_col].max()

    # Convert to pandas Timestamps
    if hasattr(start_ts, "to_pandas"):
        start_date = pd.Timestamp(start_ts.to_pandas())
        end_date = pd.Timestamp(end_ts.to_pandas())
    else:
        start_date = pd.Timestamp(str(start_ts))
        end_date = pd.Timestamp(str(end_ts))

    # Ensure dates are tz-naive (rustybt calendars use naive sessions)
    if start_date.tz is not None:
        start_date = start_date.tz_convert("UTC").tz_localize(None)
    if end_date.tz is not None:
        end_date = end_date.tz_convert("UTC").tz_localize(None)

    # Get assets
    assets = []
    if "asset" in df.columns:
        assets = sorted(df["asset"].unique().to_list())
    else:
        assets = ["VALIDATION_ASSET"]

    # Store fixture data for ingest function
    _fixture_data = {
        "parquet_path": parquet_path,
        "df": df,
        "datetime_col": datetime_col,
        "assets": assets,
    }

    def ingest_validation_fixture(
        _environ: Any,  # noqa: ANN401
        asset_db_writer: Any,  # noqa: ANN401
        _minute_bar_writer: Any,  # noqa: ANN401
        daily_bar_writer: Any,  # noqa: ANN401
        adjustment_writer: Any,  # noqa: ANN401
        _calendar: Any,  # noqa: ANN401
        start_session: Any,  # noqa: ANN401
        end_session: Any,  # noqa: ANN401
        _cache: Any,  # noqa: ANN401
        show_progress: Any,  # noqa: ANN401
        _output_dir: Any,  # noqa: ANN401
    ) -> None:
        """Ingest validation fixture data into rustybt bundle format."""
        import numpy as np

        # Get data from closure
        df = _fixture_data["df"]
        datetime_col = _fixture_data["datetime_col"]
        assets = _fixture_data["assets"]

        # Write asset metadata
        # Note: rustybt asset finder reads timestamps as nanoseconds since epoch
        # Convert Timestamps to nanoseconds for correct storage
        start_ns = (
            int(start_session.timestamp() * 1e9)
            if hasattr(start_session, "timestamp")
            else start_session
        )
        end_ns = (
            int(end_session.timestamp() * 1e9) if hasattr(end_session, "timestamp") else end_session
        )
        auto_close_ns = int((end_session + pd.Timedelta(days=1)).timestamp() * 1e9)

        asset_metadata = pd.DataFrame(
            {
                "symbol": assets,
                "asset_name": assets,
                "start_date": pd.Timestamp(start_ns, unit="ns"),
                "end_date": pd.Timestamp(end_ns, unit="ns"),
                "first_traded": pd.Timestamp(start_ns, unit="ns"),
                "auto_close_date": pd.Timestamp(auto_close_ns, unit="ns"),
                "exchange": "VALIDATION",
            }
        )
        asset_db_writer.write(equities=asset_metadata)

        # Convert Polars to pandas for writing
        pdf = df.to_pandas()
        pdf[datetime_col] = pd.to_datetime(pdf[datetime_col])

        # Group by asset and write daily bars
        # daily_bar_writer.write() expects iterable of (sid, DataFrame) pairs
        # where DataFrame has all bars for that asset at once
        def generate_daily_bars() -> Iterator[tuple[int, pd.DataFrame]]:
            for asset_idx, asset_name in enumerate(assets):
                if "asset" in pdf.columns:
                    asset_df = pdf[pdf["asset"] == asset_name].copy()
                else:
                    asset_df = pdf.copy()

                asset_df = asset_df.sort_values(datetime_col)
                asset_df = asset_df.set_index(datetime_col)

                # Ensure index is tz-naive (bundle writer expects naive timestamps)
                if asset_df.index.tz is not None:
                    asset_df.index = asset_df.index.tz_convert("UTC").tz_localize(None)

                # Create DataFrame with all bars for this asset
                bars_df = pd.DataFrame(
                    {
                        "open": (
                            asset_df["open"].values
                            if "open" in asset_df.columns
                            else asset_df["close"].values
                        ),
                        "high": (
                            asset_df["high"].values
                            if "high" in asset_df.columns
                            else asset_df["close"].values
                        ),
                        "low": (
                            asset_df["low"].values
                            if "low" in asset_df.columns
                            else asset_df["close"].values
                        ),
                        "close": asset_df["close"].values,
                        "volume": (
                            asset_df["volume"].values
                            if "volume" in asset_df.columns
                            else np.zeros(len(asset_df))
                        ),
                    },
                    index=asset_df.index,
                )
                yield asset_idx, bars_df

        # Write daily bar data
        try:
            daily_bar_writer.write(generate_daily_bars(), show_progress=show_progress)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"Warning: Could not write daily bars: {e}\n")

        # Write empty adjustments (required for data portal to work)
        try:
            adjustment_writer.write(
                splits=pd.DataFrame(columns=["sid", "ratio", "effective_date"]),
                dividends=pd.DataFrame(
                    columns=["sid", "ex_date", "declared_date", "record_date", "pay_date", "amount"]
                ),
                mergers=pd.DataFrame(columns=["sid", "effective_date", "ratio"]),
            )
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"Warning: Could not write adjustments: {e}\n")

    # Register the bundle
    try:
        register(
            bundle_name,
            ingest_validation_fixture,
            calendar_name=calendar_name,
            start_session=start_date,
            end_session=end_date,
            create_writers=True,
        )
    except Exception as e:  # noqa: BLE001
        # Bundle may already be registered, which is fine
        sys.stderr.write(f"Note: Bundle registration: {e}\n")

    return start_date, end_date, assets


def run_validation_backtest(
    strategy_class: type,
    data_path: Path,
    output_path: Path,
    params: dict[str, Any],
    capital_base: float = 100000.0,
    commission_per_trade: float = 1.0,
) -> int:
    """Run a validated rustybt backtest using the real engine.

    This function executes a backtest using rustybt's actual TradingAlgorithm,
    DataPortal, and broker simulation. It replaces the previous homebrew
    row-iteration approach.

    Parameters
    ----------
    strategy_class : type
        Strategy class that implements initialize(context) and handle_data(context, data).
    data_path : Path
        Path to the Parquet data fixture.
    output_path : Path
        Path for JSONL log output.
    params : dict[str, Any]
        Strategy parameters to pass to the constructor.
    capital_base : float, optional
        Starting capital, by default 100000.0.
    commission_per_trade : float, optional
        Commission per trade (for logging), by default 1.0.

    Returns:
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """
    import polars as pl

    from rustybt.utils.run_algo import run_algorithm

    # Load the data directly to get date range and asset info
    try:
        df = pl.read_parquet(data_path)
        df = df.rename({col: col.lower() for col in df.columns})
    except (OSError, pl.exceptions.ComputeError) as e:
        sys.stderr.write(f"Failed to load data: {e}\n")
        return 1

    # Find datetime column
    datetime_col = None
    for col in ["timestamp", "datetime", "date"]:
        if col in df.columns:
            datetime_col = col
            break

    if datetime_col is None:
        sys.stderr.write("No datetime column found in data\n")
        return 1

    # Get date range
    df = df.sort(datetime_col)
    start_ts = df[datetime_col].min()
    end_ts = df[datetime_col].max()

    # Convert to pandas Timestamps
    if hasattr(start_ts, "to_pandas"):
        start_date = pd.Timestamp(start_ts.to_pandas())
        end_date = pd.Timestamp(end_ts.to_pandas())
    else:
        start_date = pd.Timestamp(str(start_ts))
        end_date = pd.Timestamp(str(end_ts))

    # Ensure dates are tz-naive (rustybt calendars use naive sessions)
    if start_date.tz is not None:
        start_date = start_date.tz_convert("UTC").tz_localize(None)
    if end_date.tz is not None:
        end_date = end_date.tz_convert("UTC").tz_localize(None)

    # Get asset(s) - filter to first asset if multiple
    asset_name = "VALIDATION_ASSET"
    if "asset" in df.columns:
        unique_assets = sorted(df["asset"].unique().to_list())
        if unique_assets:
            asset_name = unique_assets[0]
            if len(unique_assets) > 1:
                sys.stderr.write(f"Multi-asset data detected. Using first asset: {asset_name}\n")
            df = df.filter(pl.col("asset") == asset_name)

    # Bundle configuration
    bundle_name = "validation-fixture"
    calendar_name = "24/7"

    # Register the validation bundle for rustybt data loading
    register_validation_bundle(
        data_path,
        bundle_name=bundle_name,
        calendar_name=calendar_name,
    )

    # Create strategy instance with logging
    strategy = strategy_class(
        log_path=output_path,
        **params,
    )

    # Store strategy instance and data for the callbacks
    _execution_context = {
        "strategy": strategy,
        "df": df,
        "datetime_col": datetime_col,
        "asset_name": asset_name,
        "current_bar": 0,
        "capital_base": capital_base,
        "commission_per_trade": commission_per_trade,
    }

    def initialize(context: Any) -> None:  # noqa: ANN401
        """Initialize callback for run_algorithm."""
        strategy = _execution_context["strategy"]
        asset_name = _execution_context["asset_name"]

        # Get the asset using rustybt's symbol lookup
        # This creates a proper Asset object that works with data.history(), etc.
        try:
            asset = context.symbol(asset_name)
            context.asset = asset  # Store on context for strategy access
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"Warning: Could not resolve symbol '{asset_name}': {e}\n")
            context.asset = None

        # Store context reference for later access
        _execution_context["context"] = context

        # Call strategy's initialize
        strategy.initialize(context)

    def handle_data(context: Any, data: Any) -> None:  # noqa: ANN401
        """Handle data callback for run_algorithm - processes one bar.

        Passes the real rustybt BarData object to the strategy, enabling
        proper use of data.history(), data.current(), etc.
        """
        strategy = _execution_context["strategy"]
        # Pass the real rustybt data object to strategy
        strategy.handle_data(context, data)

    def analyze(context: Any, perf: Any) -> None:  # noqa: ANN401, ARG001
        """Analyze callback for run_algorithm - called at end of backtest."""
        strategy = _execution_context["strategy"]
        # Finalize strategy to log final metrics
        strategy.finalize()
        strategy.close()

    def notify_transaction(context: Any, transaction: Any) -> None:  # noqa: ANN401
        """Transaction callback - called when orders are filled.

        This callback is invoked by rustybt's simulation loop for each
        transaction (order fill). It forwards to the strategy's notify_transaction
        method to log Layer 4 broker events (transaction_executed, commission_charged,
        slippage_applied).
        """
        strategy = _execution_context["strategy"]
        strategy.notify_transaction(context, transaction)

    # Run the backtest using rustybt's REAL engine
    try:
        from rustybt.data.bundles import ingest
        from rustybt.utils.run_algo import run_algorithm

        # Ingest the bundle (writes data to rustybt's data directory)
        try:
            ingest(bundle_name, show_progress=False)
        except Exception as e:  # noqa: BLE001
            # Bundle may already be ingested
            sys.stderr.write(f"Note: Bundle ingest: {e}\n")

        # Run backtest using rustybt's real execution engine
        run_algorithm(
            start=start_date,
            end=end_date,
            initialize=initialize,
            handle_data=handle_data,
            analyze=analyze,
            notify_transaction=notify_transaction,
            capital_base=capital_base,
            bundle=bundle_name,
            data_frequency="daily",
            trading_calendar=calendar_name,
            benchmark_returns=None,
        )

        return 0

    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Backtest execution failed: {e}\n")
        traceback.print_exc()
        return 1


def main() -> None:
    """Main entry point for the rustybt execution wrapper.

    Parses command line arguments, imports the strategy, loads data,
    and executes the strategy with validation logging using rustybt's
    real backtest engine.
    """
    parser = argparse.ArgumentParser(description="Execute rustybt strategy with validation logging")
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

    # Validate data file exists
    if not args.data.exists():
        sys.stderr.write(f"Data file not found: {args.data}\n")
        sys.exit(1)

    # Import strategy class
    strategy_class = import_strategy(args.strategy)

    # Run the backtest
    exit_code = run_validation_backtest(
        strategy_class=strategy_class,
        data_path=args.data,
        output_path=args.output,
        params=args.params,
        capital_base=100000.0,
        commission_per_trade=1.0,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
