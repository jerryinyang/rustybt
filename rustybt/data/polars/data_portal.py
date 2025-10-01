"""Polars-based Data Portal with Decimal precision.

This module provides a simplified data portal interface using Polars DataFrames
with Decimal types for financial-grade precision.
"""

import polars as pl
import pandas as pd
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional

import structlog

from rustybt.assets import Asset
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.data.polars.parquet_minute_bars import PolarsParquetMinuteReader

logger = structlog.get_logger(__name__)


class DataPortalError(Exception):
    """Base exception for DataPortal errors."""


class NoDataAvailableError(DataPortalError):
    """Raised when requested data is not available."""


class LookaheadError(DataPortalError):
    """Raised when attempting to access future data (lookahead bias)."""


class PolarsDataPortal:
    """Data portal with Polars backend and Decimal precision.

    This class provides a simplified interface for accessing OHLCV data
    with Decimal precision. It supports both daily and minute-frequency data.

    Example:
        >>> from rustybt.data.polars import PolarsParquetDailyReader, PolarsDataPortal
        >>> reader = PolarsParquetDailyReader("/path/to/bundle")
        >>> portal = PolarsDataPortal(daily_reader=reader)
        >>> assets = [Asset(sid=1, symbol="AAPL")]
        >>> prices = portal.get_spot_value(
        ...     assets=assets,
        ...     field="close",
        ...     dt=pd.Timestamp("2023-01-01"),
        ...     data_frequency="daily"
        ... )
    """

    def __init__(
        self,
        daily_reader: Optional[PolarsParquetDailyReader] = None,
        minute_reader: Optional[PolarsParquetMinuteReader] = None,
        current_simulation_time: Optional[pd.Timestamp] = None,
    ):
        """Initialize PolarsDataPortal with readers.

        Args:
            daily_reader: Optional daily bars reader
            minute_reader: Optional minute bars reader
            current_simulation_time: Current simulation time (for lookahead prevention).
                If None, lookahead checks are disabled (live trading mode).

        Raises:
            ValueError: If both readers are None
        """
        if daily_reader is None and minute_reader is None:
            raise ValueError("At least one of daily_reader or minute_reader must be provided")

        self.daily_reader = daily_reader
        self.minute_reader = minute_reader
        self.current_simulation_time = current_simulation_time

        logger.info(
            "polars_data_portal_initialized",
            has_daily_reader=daily_reader is not None,
            has_minute_reader=minute_reader is not None,
            simulation_mode=current_simulation_time is not None,
        )

    def set_simulation_time(self, dt: pd.Timestamp) -> None:
        """Set current simulation time for lookahead prevention.

        Args:
            dt: Current simulation timestamp
        """
        self.current_simulation_time = dt
        logger.debug("simulation_time_updated", current_time=dt)

    def get_spot_value(
        self, assets: List[Asset], field: str, dt: pd.Timestamp, data_frequency: str
    ) -> pl.Series:
        """Get current field values as Polars Series with Decimal dtype.

        Args:
            assets: List of assets to query
            field: Field name ('open', 'high', 'low', 'close', 'volume')
            dt: Timestamp to query
            data_frequency: Data frequency ('daily' or 'minute')

        Returns:
            Polars Series with Decimal dtype, indexed by asset sid

        Raises:
            ValueError: If field not supported or data_frequency invalid
            NoDataAvailableError: If data not available for requested timestamp
            LookaheadError: If attempting to access future data
        """
        # Validate field
        valid_fields = ["open", "high", "low", "close", "volume"]
        if field not in valid_fields:
            raise ValueError(f"Invalid field: {field}. Must be one of {valid_fields}")

        # Check for lookahead bias
        if self.current_simulation_time is not None and dt > self.current_simulation_time:
            raise LookaheadError(
                f"Attempted to access future data at {dt}, "
                f"current simulation time is {self.current_simulation_time}"
            )

        # Select appropriate reader
        if data_frequency == "daily":
            if self.daily_reader is None:
                raise ValueError("Daily data not available")
            reader = self.daily_reader
        elif data_frequency == "minute":
            if self.minute_reader is None:
                raise ValueError("Minute data not available")
            reader = self.minute_reader
        else:
            raise ValueError(f"Unsupported frequency: {data_frequency}. Must be 'daily' or 'minute'")

        # Extract sids from assets
        sids = [asset.sid for asset in assets]

        # Load data for the requested timestamp
        try:
            if data_frequency == "daily":
                df = reader.load_daily_bars(
                    sids=sids, start_date=dt.date(), end_date=dt.date()
                )
            else:  # minute
                df = reader.load_minute_bars(
                    sids=sids, start_dt=dt, end_dt=dt
                )
        except Exception as e:
            raise NoDataAvailableError(
                f"Failed to load data for {len(assets)} assets on {dt.date()}: {e}"
            )

        if len(df) == 0:
            raise NoDataAvailableError(
                f"No data found for {len(assets)} assets on {dt.date()}"
            )

        # Filter to exact date (for daily) or timestamp (for minute)
        if data_frequency == "daily":
            df = df.filter(pl.col("date") == dt.date())
        else:
            df = df.filter(pl.col("timestamp") == dt)

        if len(df) == 0:
            raise NoDataAvailableError(
                f"No data found for requested timestamp {dt}"
            )

        # Extract field as Series
        if field not in df.columns:
            raise ValueError(f"Field '{field}' not found in data")

        result = df.select([pl.col("sid"), pl.col(field)])

        logger.debug(
            "spot_value_loaded",
            field=field,
            timestamp=dt,
            asset_count=len(assets),
            data_frequency=data_frequency,
        )

        return result[field]

    def get_history_window(
        self,
        assets: List[Asset],
        end_dt: pd.Timestamp,
        bar_count: int,
        frequency: str,
        field: str,
        data_frequency: str,
    ) -> pl.DataFrame:
        """Get historical window as Polars DataFrame with Decimal columns.

        Args:
            assets: List of assets to query
            end_dt: End timestamp (inclusive)
            bar_count: Number of bars to retrieve (looking backward from end_dt)
            frequency: Aggregation frequency ('1d', '1h', '1m', etc.)
            field: Field name ('open', 'high', 'low', 'close', 'volume')
            data_frequency: Source data frequency ('daily' or 'minute')

        Returns:
            Polars DataFrame with columns:
                - date/timestamp: pl.Date or pl.Datetime
                - sid: pl.Int64
                - {field}: pl.Decimal(18, 8)

        Raises:
            ValueError: If parameters invalid or data not available
            NoDataAvailableError: If insufficient data available
            LookaheadError: If attempting to access future data
        """
        # Validate field
        valid_fields = ["open", "high", "low", "close", "volume"]
        if field not in valid_fields:
            raise ValueError(f"Invalid field: {field}. Must be one of {valid_fields}")

        # Check for lookahead bias
        if self.current_simulation_time is not None and end_dt > self.current_simulation_time:
            raise LookaheadError(
                f"Attempted to access future data ending at {end_dt}, "
                f"current simulation time is {self.current_simulation_time}"
            )

        # Select appropriate reader
        if data_frequency == "daily":
            if self.daily_reader is None:
                raise ValueError("Daily data not available")
            reader = self.daily_reader
        elif data_frequency == "minute":
            if self.minute_reader is None:
                raise ValueError("Minute data not available")
            reader = self.minute_reader
        else:
            raise ValueError(f"Unsupported frequency: {data_frequency}. Must be 'daily' or 'minute'")

        # Extract sids from assets
        sids = [asset.sid for asset in assets]

        # Calculate start date for the window
        # For simplicity, load more data than needed and filter later
        # TODO: Implement proper date calculation based on frequency
        if data_frequency == "daily":
            # Load bar_count * 2 days to ensure we have enough data
            start_date = (end_dt - pd.Timedelta(days=bar_count * 2)).date()
        else:
            # Load bar_count * 2 minutes worth of data
            start_date = (end_dt - pd.Timedelta(minutes=bar_count * 2)).date()

        # Load data
        try:
            if data_frequency == "daily":
                df = reader.load_daily_bars(
                    sids=sids, start_date=start_date, end_date=end_dt.date()
                )
            else:  # minute
                start_dt = end_dt - pd.Timedelta(minutes=bar_count * 2)
                df = reader.load_minute_bars(
                    sids=sids, start_dt=start_dt, end_dt=end_dt
                )
        except Exception as e:
            raise NoDataAvailableError(
                f"Failed to load historical data: {e}"
            )

        if len(df) == 0:
            raise NoDataAvailableError(
                f"No historical data found for {len(assets)} assets"
            )

        # Filter to end_dt and take last bar_count rows per asset
        if data_frequency == "daily":
            df = df.filter(pl.col("date") <= end_dt.date())
        else:
            df = df.filter(pl.col("timestamp") <= end_dt)

        # Group by sid and take last bar_count rows
        df = df.group_by("sid").agg([
            pl.all().sort_by("date" if data_frequency == "daily" else "timestamp").tail(bar_count)
        ]).explode(pl.all().exclude("sid"))

        # Select only the required columns
        time_col = "date" if data_frequency == "daily" else "timestamp"
        df = df.select([pl.col(time_col), pl.col("sid"), pl.col(field)])

        logger.debug(
            "history_window_loaded",
            field=field,
            end_dt=end_dt,
            bar_count=bar_count,
            asset_count=len(assets),
            data_frequency=data_frequency,
            rows_returned=len(df),
        )

        return df
