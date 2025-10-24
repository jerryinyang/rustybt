"""Polars-based Data Portal with Decimal precision.

This module provides a simplified data portal interface using Polars DataFrames
with Decimal types for financial-grade precision.
"""

import asyncio
import threading
import warnings
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Literal, Optional, TypeVar, Union

import numpy as np
import pandas as pd
import polars as pl
import structlog

from rustybt.assets import Asset
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.data.polars.parquet_minute_bars import PolarsParquetMinuteReader

if TYPE_CHECKING:
    from rustybt.data.polars.validation import DataValidator
    from rustybt.data.sources.base import DataSource

logger = structlog.get_logger(__name__)

T = TypeVar("T")


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
        daily_reader: PolarsParquetDailyReader | None = None,
        minute_reader: PolarsParquetMinuteReader | None = None,
        current_simulation_time: pd.Timestamp | None = None,
        data_source: Optional["DataSource"] = None,
        use_cache: bool = True,
        *,
        asset_finder: object | None = None,
        calendar: object | None = None,
        validator: Optional["DataValidator"] = None,
        enable_history_cache: bool = True,
    ):
        """Initialize PolarsDataPortal with readers or DataSource.

        Args:
            daily_reader: Optional daily bars reader (DEPRECATED - use data_source)
            minute_reader: Optional minute bars reader (DEPRECATED - use data_source)
            current_simulation_time: Current simulation time (for lookahead prevention).
                If None, lookahead checks are disabled (live trading mode).
            data_source: Unified DataSource for fetching data (NEW - preferred)
            use_cache: Whether to wrap data_source with caching (default: True)
            asset_finder: Optional asset finder instance
            calendar: Optional trading calendar instance
            validator: Optional DataValidator for lightweight validation during strategy execution
            enable_history_cache: Whether to enable multi-tier history cache (default: True)

        Raises:
            ValueError: If neither data_source nor readers provided
        """
        # NEW: Unified data source path
        if data_source is not None:
            from rustybt.data.sources.cached_source import CachedDataSource

            if use_cache and not isinstance(data_source, CachedDataSource):
                # Wrap with caching
                self.data_source = CachedDataSource(
                    adapter=data_source,
                    cache_dir="~/.rustybt/cache",
                )
            else:
                self.data_source = data_source

            # Set legacy readers to None (new path doesn't use them)
            self.daily_reader = None
            self.minute_reader = None

            logger.info(
                "polars_data_portal_initialized",
                mode="unified",
                data_source=data_source.__class__.__name__,
                use_cache=use_cache,
                simulation_mode=current_simulation_time is not None,
            )

        # LEGACY: Backwards compatibility for old API
        elif daily_reader is not None or minute_reader is not None:
            warnings.warn(
                "Using daily_reader/minute_reader is deprecated and will be removed in v2.0. "
                "Please migrate to the unified DataSource API: "
                "PolarsDataPortal(data_source=YFinanceDataSource(), use_cache=True)",
                DeprecationWarning,
                stacklevel=2,
            )

            self.daily_reader = daily_reader
            self.minute_reader = minute_reader
            self.data_source = None

            logger.info(
                "polars_data_portal_initialized",
                mode="legacy",
                has_daily_reader=daily_reader is not None,
                has_minute_reader=minute_reader is not None,
                simulation_mode=current_simulation_time is not None,
            )

        else:
            raise ValueError(
                "Must provide either data_source or legacy readers (daily_reader/minute_reader)"
            )

        self.current_simulation_time = current_simulation_time
        self.use_cache = use_cache
        self.asset_finder = asset_finder
        self.calendar = calendar
        self.validator = validator

        # Cache statistics (for new data_source path)
        self.cache_hit_count = 0
        self.cache_miss_count = 0

        # Initialize multi-tier history cache (Layer 2 optimization)
        self.enable_history_cache = enable_history_cache
        if enable_history_cache:
            from rustybt.optimization.dataportal_ext import HistoryCache

            self.history_cache = HistoryCache(
                permanent_windows=[20, 50, 200],
                tier2_maxsize=256,
            )
        else:
            self.history_cache = None

    def set_simulation_time(self, dt: pd.Timestamp) -> None:
        """Set current simulation time for lookahead prevention.

        Args:
            dt: Current simulation timestamp
        """
        self.current_simulation_time = dt
        logger.debug("simulation_time_updated", current_time=dt)

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage.

        Returns:
            Cache hit rate as percentage (0-100), or 0 if no cache requests
        """
        total = self.cache_hit_count + self.cache_miss_count
        if total == 0:
            return 0.0
        return (self.cache_hit_count / total) * 100

    def history(
        self,
        assets: Union[Asset, list[Asset]],
        fields: Union[str, list[str]],
        bar_count: int,
        frequency: str,
        return_type: Literal["dataframe", "array"] = "dataframe",
    ) -> Union[pd.DataFrame, np.ndarray]:
        """Get historical window with optional NumPy array return.

        This method provides flexible history access with optional NumPy array
        returns to skip DataFrame construction overhead (19.35% speedup for
        array-consuming strategies).

        Args:
            assets: Single asset or list of assets to query
            fields: Single field or list of fields ('open', 'high', 'low', 'close', 'volume')
            bar_count: Number of bars to retrieve (looking backward from current time)
            frequency: Aggregation frequency ('1d', '1h', '1m', etc.)
            return_type: Return type - 'dataframe' (default) or 'array' for NumPy

        Returns:
            DataFrame (default) or NumPy array based on return_type parameter:
            - 'dataframe': pd.DataFrame with historical data (backward compatible)
            - 'array': np.ndarray with shape (bar_count, n_fields), dtype float64

        Raises:
            ValueError: If parameters invalid
            NoDataAvailableError: If insufficient data available
            LookaheadError: If attempting to access future data

        Example:
            >>> # Default: DataFrame return (backward compatible)
            >>> df = portal.history([asset], 'close', 20, '1d')
            >>> fast_mavg = df['close'].mean()
            >>>
            >>> # NumPy array return (19.35% faster)
            >>> prices = portal.history([asset], 'close', 20, '1d', return_type='array')
            >>> fast_mavg = np.mean(prices)
        """
        # Normalize inputs
        if not isinstance(assets, list):
            assets = [assets]
        if not isinstance(fields, list):
            fields = [fields]

        # Validate fields
        for field in fields:
            self._validate_field(field)

        # For array return, use optimized path with caching
        if return_type == "array":
            return self._history_array(assets, fields, bar_count, frequency)
        else:
            return self._history_dataframe(assets, fields, bar_count, frequency)

    def _history_dataframe(
        self,
        assets: list[Asset],
        fields: list[str],
        bar_count: int,
        frequency: str,
    ) -> pd.DataFrame:
        """Get historical window as DataFrame (existing behavior).

        This method preserves the existing DataFrame return path for
        backward compatibility.
        """
        # Use existing get_history_window for each field
        # Note: This uses the legacy path, combining results into a multi-field DataFrame
        if len(fields) == 1 and len(assets) == 1:
            # Simple case: single asset, single field
            data_frequency = "daily" if frequency.endswith("d") else "minute"
            end_dt = (
                self.current_simulation_time
                if self.current_simulation_time is not None
                else pd.Timestamp.now()
            )

            df = self.get_history_window(
                assets=assets,
                end_dt=end_dt,
                bar_count=bar_count,
                frequency=frequency,
                field=fields[0],
                data_frequency=data_frequency,
            )

            # Convert to pandas DataFrame format
            return df.to_pandas()

        # Multi-field or multi-asset case (future enhancement)
        raise NotImplementedError(
            "Multi-field/multi-asset DataFrame history not yet implemented. "
            "Use single asset and single field, or use return_type='array'."
        )

    def _history_array(
        self,
        assets: list[Asset],
        fields: list[str],
        bar_count: int,
        frequency: str,
    ) -> np.ndarray:
        """Get historical window as NumPy array (optimized path).

        This method skips DataFrame construction entirely, returning NumPy
        arrays directly from the cache or data source. Achieves 19.35% speedup
        by eliminating DataFrame overhead.

        Returns:
            np.ndarray with shape (bar_count, n_fields), dtype float64
        """
        from rustybt.optimization.dataportal_ext import CacheKey

        # Check cache first if enabled
        if self.history_cache is not None and len(assets) == 1 and len(fields) == 1:
            asset = assets[0]
            field = fields[0]
            end_dt = (
                self.current_simulation_time
                if self.current_simulation_time is not None
                else pd.Timestamp.now()
            )

            cache_key = CacheKey(
                asset_id=asset.sid,
                field=field,
                bar_count=bar_count,
                end_date=str(end_dt.date()),
            )

            cached_result = self.history_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(
                    "history_cache_hit",
                    asset_id=asset.sid,
                    field=field,
                    bar_count=bar_count,
                    cache_hit_rate=self.history_cache.hit_rate,
                )
                return cached_result

        # Cache miss - fetch data
        data_frequency = "daily" if frequency.endswith("d") else "minute"
        end_dt = (
            self.current_simulation_time
            if self.current_simulation_time is not None
            else pd.Timestamp.now()
        )

        # Get data from underlying storage
        df = self.get_history_window(
            assets=assets,
            end_dt=end_dt,
            bar_count=bar_count,
            frequency=frequency,
            field=fields[0],  # Start with single field support
            data_frequency=data_frequency,
        )

        # Convert to NumPy array (skip DataFrame construction)
        # Note: Polars DataFrame to NumPy is efficient (zero-copy when possible)
        if isinstance(df, pl.DataFrame):
            # Extract field column and convert to NumPy
            field_col = df[fields[0]]

            # Convert Decimal to float64 with controlled precision
            if field_col.dtype == pl.Decimal:
                # Cast to Float64 first, then to NumPy
                array_data = field_col.cast(pl.Float64).to_numpy()
            else:
                array_data = field_col.to_numpy()
        else:
            # If it's already a pandas DataFrame (legacy path)
            array_data = df[fields[0]].values

        # Ensure correct shape (bar_count, n_fields)
        if len(fields) == 1:
            array_data = array_data.reshape(-1, 1)

        # Store in cache if enabled
        if self.history_cache is not None and len(assets) == 1 and len(fields) == 1:
            self.history_cache.put(cache_key, array_data)
            logger.debug(
                "history_cache_put",
                asset_id=assets[0].sid,
                field=fields[0],
                bar_count=bar_count,
                array_shape=array_data.shape,
            )

        return array_data

    def get_spot_value(
        self, assets: list[Asset], field: str, dt: pd.Timestamp, data_frequency: str
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
        self._validate_field(field)
        self._ensure_supported_frequency(data_frequency)
        self._check_lookahead(dt)

        if self.data_source is not None:
            return self._execute_coroutine(
                self._fetch_spot_value_unified(assets, field, dt, data_frequency)
            )

        # LEGACY: Use old reader-based approach
        return self._get_spot_value_legacy(assets, field, dt, data_frequency)

    async def async_get_spot_value(
        self, assets: list[Asset], field: str, dt: pd.Timestamp, data_frequency: str
    ) -> pl.Series:
        self._validate_field(field)
        self._ensure_supported_frequency(data_frequency)
        self._check_lookahead(dt)

        if self.data_source is not None:
            return await self._fetch_spot_value_unified(assets, field, dt, data_frequency)

        return await asyncio.to_thread(
            self._get_spot_value_legacy, assets, field, dt, data_frequency
        )

    def get_history_window(
        self,
        assets: list[Asset],
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
        self._validate_field(field)
        self._ensure_supported_frequency(data_frequency)
        self._check_lookahead(end_dt)

        if self.data_source is not None:
            return self._execute_coroutine(
                self._fetch_history_window_unified(
                    assets, end_dt, bar_count, frequency, field, data_frequency
                )
            )

        # LEGACY: Use old reader-based approach
        return self._get_history_window_legacy(
            assets, end_dt, bar_count, frequency, field, data_frequency
        )

    async def async_get_history_window(
        self,
        assets: list[Asset],
        end_dt: pd.Timestamp,
        bar_count: int,
        frequency: str,
        field: str,
        data_frequency: str,
    ) -> pl.DataFrame:
        self._validate_field(field)
        self._ensure_supported_frequency(data_frequency)
        self._check_lookahead(end_dt)

        if self.data_source is not None:
            return await self._fetch_history_window_unified(
                assets, end_dt, bar_count, frequency, field, data_frequency
            )

        return await asyncio.to_thread(
            self._get_history_window_legacy,
            assets,
            end_dt,
            bar_count,
            frequency,
            field,
            data_frequency,
        )

    async def _fetch_spot_value_unified(
        self, assets: list[Asset], field: str, dt: pd.Timestamp, data_frequency: str
    ) -> pl.Series:
        symbols = [asset.symbol for asset in assets]

        try:
            df = await self.data_source.fetch(
                symbols=symbols,
                start=dt,
                end=dt,
                frequency=data_frequency,
            )
            if hasattr(self.data_source, "cache_hit_count"):
                self.cache_hit_count = getattr(self.data_source, "cache_hit_count", 0)
                self.cache_miss_count = getattr(self.data_source, "cache_miss_count", 0)
        except Exception as exc:  # pragma: no cover - defensive
            raise NoDataAvailableError(
                f"Failed to fetch data for {len(assets)} assets on {dt.date()}: {exc}"
            ) from exc

        if len(df) == 0:
            raise NoDataAvailableError(f"No data found for {len(assets)} assets on {dt.date()}")

        if field not in df.columns:
            raise ValueError(f"Field '{field}' not found in data")

        logger.debug(
            "spot_value_loaded",
            field=field,
            timestamp=dt,
            asset_count=len(assets),
            data_frequency=data_frequency,
            mode="unified",
        )

        return df[field]

    async def _fetch_history_window_unified(
        self,
        assets: list[Asset],
        end_dt: pd.Timestamp,
        bar_count: int,
        frequency: str,
        field: str,
        data_frequency: str,
    ) -> pl.DataFrame:
        symbols = [asset.symbol for asset in assets]
        start_dt = self._compute_start_dt(end_dt, bar_count, frequency)

        try:
            df = await self.data_source.fetch(
                symbols=symbols,
                start=start_dt,
                end=end_dt,
                frequency=frequency,
            )
        except Exception as exc:  # pragma: no cover - defensive
            raise NoDataAvailableError(f"Failed to fetch historical data: {exc}") from exc

        if len(df) == 0:
            raise NoDataAvailableError(f"No historical data found for {len(assets)} assets")

        if field not in df.columns:
            raise ValueError(f"Field '{field}' not found in data")

        time_col = "date" if "date" in df.columns else "timestamp"
        df = self._build_history_tail_frame(
            df=df,
            identifier="symbol",
            time_col=time_col,
            field=field,
            bar_count=bar_count,
        )

        logger.debug(
            "history_window_loaded",
            field=field,
            end_dt=end_dt,
            bar_count=bar_count,
            asset_count=len(assets),
            data_frequency=data_frequency,
            rows_returned=len(df),
            mode="unified",
        )

        return df

    def _get_spot_value_legacy(
        self, assets: list[Asset], field: str, dt: pd.Timestamp, data_frequency: str
    ) -> pl.Series:
        reader = self._resolve_reader(data_frequency)

        sids = [asset.sid for asset in assets]

        try:
            if data_frequency == "daily":
                df = reader.load_daily_bars(sids=sids, start_date=dt.date(), end_date=dt.date())
            else:
                df = reader.load_minute_bars(sids=sids, start_dt=dt, end_dt=dt)
        except Exception as exc:
            raise NoDataAvailableError(
                f"Failed to load data for {len(assets)} assets on {dt.date()}: {exc}"
            ) from exc

        if len(df) == 0:
            raise NoDataAvailableError(f"No data found for {len(assets)} assets on {dt.date()}")

        time_col = "date" if data_frequency == "daily" else "timestamp"
        df = df.filter(pl.col(time_col) == (dt.date() if data_frequency == "daily" else dt))

        if len(df) == 0:
            raise NoDataAvailableError(f"No data found for requested timestamp {dt}")

        if field not in df.columns:
            raise ValueError(f"Field '{field}' not found in data")

        result = df.select([pl.col("sid"), pl.col(field)])

        logger.debug(
            "spot_value_loaded",
            field=field,
            timestamp=dt,
            asset_count=len(assets),
            data_frequency=data_frequency,
            mode="legacy",
        )

        return result[field]

    def _get_history_window_legacy(
        self,
        assets: list[Asset],
        end_dt: pd.Timestamp,
        bar_count: int,
        frequency: str,
        field: str,
        data_frequency: str,
    ) -> pl.DataFrame:
        reader = self._resolve_reader(data_frequency)
        sids = [asset.sid for asset in assets]

        if data_frequency == "daily":
            start_date = (end_dt - pd.Timedelta(days=bar_count * 2)).date()
        else:
            start_date = end_dt - pd.Timedelta(minutes=bar_count * 2)

        try:
            if data_frequency == "daily":
                df = reader.load_daily_bars(
                    sids=sids, start_date=start_date, end_date=end_dt.date()
                )
            else:
                start_dt = end_dt - pd.Timedelta(minutes=bar_count * 2)
                df = reader.load_minute_bars(sids=sids, start_dt=start_dt, end_dt=end_dt)
        except Exception as exc:
            raise NoDataAvailableError(f"Failed to load historical data: {exc}") from exc

        if len(df) == 0:
            raise NoDataAvailableError(f"No historical data found for {len(assets)} assets")

        if data_frequency == "daily":
            df = df.filter(pl.col("date") <= end_dt.date())
        else:
            df = df.filter(pl.col("timestamp") <= end_dt)

        time_col = "date" if data_frequency == "daily" else "timestamp"
        df = self._build_history_tail_frame(
            df=df,
            identifier="sid",
            time_col=time_col,
            field=field,
            bar_count=bar_count,
        )

        logger.debug(
            "history_window_loaded",
            field=field,
            end_dt=end_dt,
            bar_count=bar_count,
            asset_count=len(assets),
            data_frequency=data_frequency,
            rows_returned=len(df),
            mode="legacy",
        )

        return df

    def _build_history_tail_frame(
        self,
        df: pl.DataFrame,
        identifier: str,
        time_col: str,
        field: str,
        bar_count: int,
    ) -> pl.DataFrame:
        """Build history tail frame using Polars (already Rust-optimized).

        Note: We intentionally use pure Polars here instead of our custom Rust
        integration because:
        1. Polars is already Rust-backed and highly optimized for these operations
        2. Python↔Rust conversion overhead outweighs computation time for simple ops
        3. Benchmarks show 25x slowdown when adding custom Rust layer (see AC5)

        Our Rust optimizations are beneficial for complex operations (SMA, EMA) on
        large datasets, but not for DataFrame operations that Polars already handles.
        """
        return self._build_history_tail_frame_polars(df, identifier, time_col, field, bar_count)

    @staticmethod
    def _build_history_tail_frame_polars(
        df: pl.DataFrame,
        identifier: str,
        time_col: str,
        field: str,
        bar_count: int,
    ) -> pl.DataFrame:
        return (
            df.group_by(identifier)
            .agg([pl.all().sort_by(time_col).tail(bar_count)])
            .explode(pl.all().exclude(identifier))
            .select([pl.col(time_col), pl.col(identifier), pl.col(field)])
        )

    def _resolve_reader(self, data_frequency: str):
        if data_frequency == "daily":
            if self.daily_reader is None:
                raise ValueError("Daily data not available")
            return self.daily_reader
        if data_frequency == "minute":
            if self.minute_reader is None:
                raise ValueError("Minute data not available")
            return self.minute_reader
        raise ValueError(f"Unsupported frequency: {data_frequency}. Must be 'daily' or 'minute'")

    def _execute_coroutine(self, coro: Awaitable[T]) -> T:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        if not loop.is_running():
            return loop.run_until_complete(coro)

        result: dict[str, T] = {}
        error: dict[str, BaseException] = {}

        def runner() -> None:
            try:
                result["value"] = asyncio.run(coro)
            except BaseException as exc:  # pragma: no cover - defensive
                error["error"] = exc

        thread = threading.Thread(target=runner)
        thread.start()
        thread.join()

        if "error" in error:
            raise error["error"]

        return result["value"]

    def _validate_field(self, field: str) -> None:
        valid_fields = {"open", "high", "low", "close", "volume"}
        if field not in valid_fields:
            raise ValueError(f"Invalid field: {field}. Must be one of {sorted(valid_fields)}")

    def _ensure_supported_frequency(self, data_frequency: str) -> None:
        if data_frequency not in {"daily", "minute"}:
            raise ValueError("Unsupported frequency: Must be 'daily' or 'minute'")

    def _check_lookahead(self, dt: pd.Timestamp) -> None:
        if self.current_simulation_time is not None and dt > self.current_simulation_time:
            raise LookaheadError(
                f"Attempted to access future data at {dt}, current simulation time is {self.current_simulation_time}"
            )

    @staticmethod
    def _compute_start_dt(end_dt: pd.Timestamp, bar_count: int, frequency: str) -> pd.Timestamp:
        if frequency.endswith("d"):
            return end_dt - pd.Timedelta(days=bar_count * 2)
        if frequency.endswith("h"):
            hours = int(frequency[:-1]) if len(frequency) > 1 else 1
            return end_dt - pd.Timedelta(hours=bar_count * hours * 2)
        if frequency.endswith("m"):
            minutes = int(frequency[:-1]) if len(frequency) > 1 else 1
            return end_dt - pd.Timedelta(minutes=bar_count * minutes * 2)
        return end_dt - pd.Timedelta(days=bar_count * 2)
