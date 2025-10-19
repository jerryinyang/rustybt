"""Utilities for exporting backtest results with automatic path redirection.

This module provides helper functions for exporting backtest results to various
formats (CSV, Parquet, JSON) with automatic redirection to organized output
directories when artifact management is enabled.
"""

from pathlib import Path
from typing import Optional, Union

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def get_active_backtest_dir() -> Optional[Path]:
    """Get the output directory of the currently active backtest.

    This function looks for a TradingAlgorithm instance in the call stack
    and returns its output directory if artifact management is enabled.

    Returns:
        Path to active backtest output directory, or None if not in backtest context
        or artifact management is disabled.

    Note:
        This is a convenience function for use in notebooks and scripts.
        It searches the call stack for a TradingAlgorithm instance.
    """
    import inspect

    # Search up the call stack for a TradingAlgorithm instance
    for frame_info in inspect.stack():
        frame_locals = frame_info.frame.f_locals
        for var_name, var_value in frame_locals.items():
            # Check if this is a TradingAlgorithm instance
            if hasattr(var_value, "artifact_manager") and hasattr(var_value, "output_dir"):
                if var_value.artifact_manager.enabled:
                    return var_value.output_dir
    return None


def resolve_output_path(
    filename: Union[str, Path],
    subdir: str = "results",
    backtest_dir: Optional[Path] = None,
    results: Optional[pd.DataFrame] = None,
) -> Path:
    """Resolve a filename to an output path, using backtest directory if available.

    If a backtest output directory is available (from explicit arg, results attrs,
    or call stack search), the filename will be resolved relative to that directory.
    Otherwise, the filename is returned as-is (converted to Path).

    Args:
        filename: Name of file or path
        subdir: Subdirectory within backtest dir ('results', 'code', 'metadata')
        backtest_dir: Explicit backtest directory (optional, auto-detected if None)
        results: Results DataFrame (checks attrs['output_dir'] if present)

    Returns:
        Resolved absolute path

    Example:
        >>> # With results DataFrame containing output_dir metadata
        >>> path = resolve_output_path('results.csv', results=results)
        >>> print(path)
        /path/to/backtests/20251018_143527_123/results/results.csv

        >>> # In a backtest context with artifact management enabled
        >>> path = resolve_output_path('results.csv')
        >>> print(path)
        /path/to/backtests/20251018_143527_123/results/results.csv

        >>> # Outside backtest context
        >>> path = resolve_output_path('results.csv')
        >>> print(path)
        results.csv
    """
    # Try multiple sources for backtest_dir (in order of preference)
    if backtest_dir is None:
        # 1. Check results DataFrame attrs
        if results is not None and hasattr(results, "attrs") and "output_dir" in results.attrs:
            output_dir_str = results.attrs["output_dir"]
            if output_dir_str is not None:
                backtest_dir = Path(output_dir_str)

        # 2. Search call stack
        if backtest_dir is None:
            backtest_dir = get_active_backtest_dir()

    if backtest_dir is not None:
        # Create subdirectory if needed
        output_path = backtest_dir / subdir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "output_path_resolved",
            filename=str(filename),
            subdir=subdir,
            output_path=str(output_path),
        )

        return output_path
    else:
        # No active backtest, return filename as-is
        return Path(filename)


def export_csv(
    df: pd.DataFrame,
    filename: str,
    subdir: str = "results",
    backtest_dir: Optional[Path] = None,
    results: Optional[pd.DataFrame] = None,
    **kwargs,
) -> Path:
    """Export DataFrame to CSV with automatic path redirection.

    If called within a backtest context with artifact management enabled,
    the file will be saved to the backtest's output directory. Otherwise,
    it will be saved to the current directory.

    Args:
        df: DataFrame to export
        filename: Name of CSV file
        subdir: Subdirectory within backtest dir (default: 'results')
        backtest_dir: Explicit backtest directory (optional)
        results: Backtest results DataFrame (checks attrs for output_dir)
        **kwargs: Additional arguments passed to df.to_csv()

    Returns:
        Path where file was saved

    Example:
        >>> results = algo.run()
        >>> export_csv(results, 'backtest_results.csv', results=results)
        PosixPath('/path/to/backtests/20251018_143527_123/results/backtest_results.csv')
    """
    # Use df as results source if results not explicitly provided
    if results is None and hasattr(df, "attrs"):
        results = df

    output_path = resolve_output_path(
        filename, subdir=subdir, backtest_dir=backtest_dir, results=results
    )

    df.to_csv(output_path, **kwargs)

    logger.info(
        "csv_exported",
        filename=str(filename),
        output_path=str(output_path),
        rows=len(df),
    )

    return output_path


def export_parquet(
    df: pd.DataFrame,
    filename: str,
    subdir: str = "results",
    backtest_dir: Optional[Path] = None,
    results: Optional[pd.DataFrame] = None,
    **kwargs,
) -> Path:
    """Export DataFrame to Parquet with automatic path redirection.

    If called within a backtest context with artifact management enabled,
    the file will be saved to the backtest's output directory. Otherwise,
    it will be saved to the current directory.

    Args:
        df: DataFrame to export
        filename: Name of Parquet file
        subdir: Subdirectory within backtest dir (default: 'results')
        backtest_dir: Explicit backtest directory (optional)
        results: Backtest results DataFrame (checks attrs for output_dir)
        **kwargs: Additional arguments passed to df.to_parquet()

    Returns:
        Path where file was saved

    Example:
        >>> results = algo.run()
        >>> export_parquet(results, 'backtest_results.parquet', results=results)
        PosixPath('/path/to/backtests/20251018_143527_123/results/backtest_results.parquet')
    """
    # Use df as results source if results not explicitly provided
    if results is None and hasattr(df, "attrs"):
        results = df

    output_path = resolve_output_path(
        filename, subdir=subdir, backtest_dir=backtest_dir, results=results
    )

    df.to_parquet(output_path, **kwargs)

    logger.info(
        "parquet_exported",
        filename=str(filename),
        output_path=str(output_path),
        rows=len(df),
    )

    return output_path


def export_json(
    df: pd.DataFrame,
    filename: str,
    subdir: str = "results",
    backtest_dir: Optional[Path] = None,
    **kwargs,
) -> Path:
    """Export DataFrame to JSON with automatic path redirection.

    If called within a backtest context with artifact management enabled,
    the file will be saved to the backtest's output directory. Otherwise,
    it will be saved to the current directory.

    Args:
        df: DataFrame to export
        filename: Name of JSON file
        subdir: Subdirectory within backtest dir (default: 'results')
        backtest_dir: Explicit backtest directory (optional)
        **kwargs: Additional arguments passed to df.to_json()

    Returns:
        Path where file was saved

    Example:
        >>> results = algo.run()
        >>> export_json(results, 'backtest_results.json')
        PosixPath('/path/to/backtests/20251018_143527_123/results/backtest_results.json')
    """
    output_path = resolve_output_path(filename, subdir=subdir, backtest_dir=backtest_dir)

    df.to_json(output_path, **kwargs)

    logger.info(
        "json_exported",
        filename=str(filename),
        output_path=str(output_path),
        rows=len(df),
    )

    return output_path
