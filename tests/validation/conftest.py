"""
Pytest Fixtures for Validation Framework.

This module defines shared fixtures for validation tests, including
session management, data loading, and tolerance configuration.

Data Loading Infrastructure (Story X.2):
    - load_fixture_for_rustybt(): Load Parquet fixture for rustybt consumption
    - load_fixture_for_backtrader(): Load Parquet fixture for Backtrader consumption
    - Ensures both frameworks receive identical OHLCV data
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from rustybt.validation.tolerance import (
    ToleranceConfig,
)

if TYPE_CHECKING:
    import backtrader as bt
    import pandas as pd


# =============================================================================
# Data Loading Infrastructure (Story X.2)
# =============================================================================

# Default fixture path
DEFAULT_FIXTURE_PATH = Path("tests/validation/fixtures/validation_data.parquet")


def load_fixture_for_rustybt(
    fixture_path: Path | str,
    asset: str | None = None,
) -> pl.DataFrame:
    """Load Parquet fixture for rustybt consumption.

    This function loads a validation fixture and prepares it for rustybt
    strategy execution. It ensures consistent data handling between
    rustybt and Backtrader.

    Parameters
    ----------
    fixture_path : Path | str
        Path to the Parquet fixture file.
    asset : str | None, optional
        Asset symbol to filter for (if multi-asset fixture).
        If None, uses the first asset alphabetically.

    Returns
    -------
    pl.DataFrame
        Polars DataFrame with columns:
        - timestamp: datetime64[ns, UTC]
        - asset: str (if multi-asset)
        - open, high, low, close: float64
        - volume: int64

    Raises
    ------
    FileNotFoundError
        If the fixture file does not exist.

    Examples
    --------
    >>> df = load_fixture_for_rustybt("tests/validation/fixtures/validation_data.parquet")
    >>> df.columns
    ['timestamp', 'asset', 'open', 'high', 'low', 'close', 'volume']
    """
    fixture_path = Path(fixture_path)
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture file not found: {fixture_path}")

    # Load with Polars
    df = pl.read_parquet(fixture_path)

    # Normalize column names to lowercase
    df = df.rename({col: col.lower() for col in df.columns})

    # Ensure timestamp has UTC timezone
    if "timestamp" in df.columns:
        # Convert to UTC if not already
        if df["timestamp"].dtype == pl.Datetime:
            df = df.with_columns(pl.col("timestamp").dt.replace_time_zone("UTC"))

    # Filter to single asset if specified or multi-asset
    if "asset" in df.columns:
        unique_assets = sorted(df["asset"].unique().to_list())
        if asset is None and len(unique_assets) > 1:
            asset = unique_assets[0]  # First asset alphabetically
        if asset is not None:
            df = df.filter(pl.col("asset") == asset)

    # Sort by timestamp
    if "timestamp" in df.columns:
        df = df.sort("timestamp")

    return df


def load_fixture_for_backtrader(
    fixture_path: Path | str,
    asset: str | None = None,
) -> tuple[Any, str | None]:
    """Load Parquet fixture for Backtrader consumption.

    This function loads a validation fixture and converts it to a
    Backtrader PandasData feed. It ensures consistent data handling
    between rustybt and Backtrader.

    Parameters
    ----------
    fixture_path : Path | str
        Path to the Parquet fixture file.
    asset : str | None, optional
        Asset symbol to filter for (if multi-asset fixture).
        If None, uses the first asset alphabetically.

    Returns
    -------
    tuple[bt.feeds.PandasData, str | None]
        Tuple of (Backtrader data feed, asset name).

    Raises
    ------
    FileNotFoundError
        If the fixture file does not exist.
    ImportError
        If backtrader is not installed.

    Examples
    --------
    >>> data_feed, asset_name = load_fixture_for_backtrader("fixture.parquet")
    >>> cerebro.adddata(data_feed, name=asset_name)
    """
    import backtrader as bt

    fixture_path = Path(fixture_path)
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture file not found: {fixture_path}")

    # Load with Polars first for consistent handling
    df_pl = pl.read_parquet(fixture_path)

    # Normalize column names to lowercase
    df_pl = df_pl.rename({col: col.lower() for col in df_pl.columns})

    # Track asset name
    asset_name: str | None = asset

    # Filter to single asset if multi-asset
    if "asset" in df_pl.columns:
        unique_assets = sorted(df_pl["asset"].unique().to_list())
        if len(unique_assets) > 1:
            if asset_name is None:
                asset_name = unique_assets[0]  # First asset alphabetically
            df_pl = df_pl.filter(pl.col("asset") == asset_name)
        elif len(unique_assets) == 1:
            asset_name = unique_assets[0]
        # Drop asset column for Backtrader
        df_pl = df_pl.drop("asset")

    # Sort by timestamp
    datetime_col = None
    for col in ["timestamp", "datetime", "date"]:
        if col in df_pl.columns:
            datetime_col = col
            break

    if datetime_col:
        df_pl = df_pl.sort(datetime_col)

    # Convert to Pandas for Backtrader
    df = df_pl.to_pandas()

    # Set datetime as index (Backtrader requirement)
    if datetime_col:
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

    # Create Backtrader data feed
    return bt.feeds.PandasData(dataname=df), asset_name


def get_fixture_info(fixture_path: Path | str) -> dict[str, Any]:
    """Get metadata about a fixture file.

    Useful for verifying fixture properties before running validation tests.

    Parameters
    ----------
    fixture_path : Path | str
        Path to the Parquet fixture file.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - assets: List of asset symbols
        - bar_count: Total number of bars
        - first_timestamp: First timestamp
        - last_timestamp: Last timestamp
        - columns: List of column names
        - schema: Polars schema

    Examples
    --------
    >>> info = get_fixture_info("fixture.parquet")
    >>> print(f"Bar count: {info['bar_count']}")
    Bar count: 730
    """
    fixture_path = Path(fixture_path)
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture file not found: {fixture_path}")

    df = pl.read_parquet(fixture_path)
    df = df.rename({col: col.lower() for col in df.columns})

    # Get unique assets
    assets = []
    if "asset" in df.columns:
        assets = sorted(df["asset"].unique().to_list())

    # Get timestamp range
    datetime_col = None
    for col in ["timestamp", "datetime", "date"]:
        if col in df.columns:
            datetime_col = col
            break

    first_ts = None
    last_ts = None
    if datetime_col:
        first_ts = df[datetime_col].min()
        last_ts = df[datetime_col].max()

    return {
        "assets": assets,
        "bar_count": len(df),
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "columns": df.columns,
        "schema": dict(df.schema),
    }


def verify_data_alignment(
    rustybt_df: pl.DataFrame,
    backtrader_df: Any,  # pd.DataFrame
    tolerance: float = 1e-10,
) -> dict[str, Any]:
    """Verify that rustybt and Backtrader see identical data.

    Compares first bar, last bar, bar count, and samples intermediate
    bars to ensure both frameworks receive the same OHLCV values.

    Parameters
    ----------
    rustybt_df : pl.DataFrame
        Data loaded for rustybt (from load_fixture_for_rustybt).
    backtrader_df : pd.DataFrame
        DataFrame used by Backtrader (from PandasData.dataname).
    tolerance : float, optional
        Tolerance for floating-point comparisons. Default 1e-10.

    Returns
    -------
    dict[str, Any]
        Verification results:
        - aligned: bool - True if all checks pass
        - bar_count_match: bool
        - first_bar_match: bool
        - last_bar_match: bool
        - sample_match: bool
        - details: dict with comparison details
    """
    import pandas as pd

    # Convert rustybt data to pandas for comparison
    rustybt_pd = rustybt_df.to_pandas()

    # Reset index if Backtrader df has datetime index
    if isinstance(backtrader_df.index, pd.DatetimeIndex):
        bt_df = backtrader_df.reset_index()
        # Rename index column to timestamp
        bt_df = bt_df.rename(columns={bt_df.columns[0]: "timestamp"})
    else:
        bt_df = backtrader_df.copy()

    # Normalize column names
    rustybt_pd.columns = [c.lower() for c in rustybt_pd.columns]
    bt_df.columns = [c.lower() for c in bt_df.columns]

    # Check bar count
    bar_count_match = len(rustybt_pd) == len(bt_df)

    # Check first bar
    first_bar_match = True
    first_bar_details = {}
    if len(rustybt_pd) > 0 and len(bt_df) > 0:
        for col in ["open", "high", "low", "close", "volume"]:
            if col in rustybt_pd.columns and col in bt_df.columns:
                rustybt_val = float(rustybt_pd[col].iloc[0])
                bt_val = float(bt_df[col].iloc[0])
                diff = abs(rustybt_val - bt_val)
                first_bar_details[col] = {
                    "rustybt": rustybt_val,
                    "backtrader": bt_val,
                    "diff": diff,
                }
                if diff > tolerance:
                    first_bar_match = False

    # Check last bar
    last_bar_match = True
    last_bar_details = {}
    if len(rustybt_pd) > 0 and len(bt_df) > 0:
        for col in ["open", "high", "low", "close", "volume"]:
            if col in rustybt_pd.columns and col in bt_df.columns:
                rustybt_val = float(rustybt_pd[col].iloc[-1])
                bt_val = float(bt_df[col].iloc[-1])
                diff = abs(rustybt_val - bt_val)
                last_bar_details[col] = {
                    "rustybt": rustybt_val,
                    "backtrader": bt_val,
                    "diff": diff,
                }
                if diff > tolerance:
                    last_bar_match = False

    # Sample intermediate bars (every 100th bar)
    sample_match = True
    sample_details = []
    sample_indices = list(range(0, min(len(rustybt_pd), len(bt_df)), 100))
    for idx in sample_indices[:10]:  # Check up to 10 samples
        sample_ok = True
        for col in ["close"]:  # Check close price as primary indicator
            if col in rustybt_pd.columns and col in bt_df.columns:
                rustybt_val = float(rustybt_pd[col].iloc[idx])
                bt_val = float(bt_df[col].iloc[idx])
                if abs(rustybt_val - bt_val) > tolerance:
                    sample_ok = False
                    sample_match = False
        sample_details.append({"index": idx, "match": sample_ok})

    aligned = bar_count_match and first_bar_match and last_bar_match and sample_match

    return {
        "aligned": aligned,
        "bar_count_match": bar_count_match,
        "first_bar_match": first_bar_match,
        "last_bar_match": last_bar_match,
        "sample_match": sample_match,
        "details": {
            "rustybt_bar_count": len(rustybt_pd),
            "backtrader_bar_count": len(bt_df),
            "first_bar": first_bar_details,
            "last_bar": last_bar_details,
            "samples": sample_details,
        },
    }


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def tolerance_config() -> ToleranceConfig:
    """Provide default tolerance configuration for tests.

    Returns:
        ToleranceConfig with default values.
    """
    config_dir = Path("tests/validation/config")
    if config_dir.exists():
        return ToleranceConfig.load_from_directory(config_dir)
    return ToleranceConfig()


@pytest.fixture
def layer_1_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 1 (Data Handling) tolerances with override capability.

    Example usage in test:
        def test_example(layer_1_tolerances):
            # Get default value
            assert layer_1_tolerances.price_decimal_places == 4

            # Override for stricter test
            layer_1_tolerances.price_decimal_places = 6
    """
    return tolerance_config.layer_1


@pytest.fixture
def layer_2_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 2 (Signal Computation) tolerances with override capability."""
    return tolerance_config.layer_2


@pytest.fixture
def layer_3_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 3 (Order Lifecycle) tolerances with override capability."""
    return tolerance_config.layer_3


@pytest.fixture
def layer_4_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 4 (Broker Transaction) tolerances with override capability."""
    return tolerance_config.layer_4


@pytest.fixture
def layer_5_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 5 (Portfolio Returns) tolerances with override capability."""
    return tolerance_config.layer_5


# =============================================================================
# Data Loading Fixtures (Story X.2)
# =============================================================================


@pytest.fixture
def fixture_path() -> Path:
    """Provide default fixture path for validation tests.

    Returns:
        Path to the default validation fixture.
    """
    return DEFAULT_FIXTURE_PATH


@pytest.fixture
def rustybt_data(fixture_path: Path) -> pl.DataFrame:
    """Load fixture data for rustybt consumption.

    Returns:
        Polars DataFrame ready for rustybt strategy execution.
    """
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")
    return load_fixture_for_rustybt(fixture_path)


@pytest.fixture
def backtrader_data(fixture_path: Path) -> tuple[Any, str | None]:
    """Load fixture data for Backtrader consumption.

    Returns:
        Tuple of (PandasData feed, asset name).
    """
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")
    return load_fixture_for_backtrader(fixture_path)
