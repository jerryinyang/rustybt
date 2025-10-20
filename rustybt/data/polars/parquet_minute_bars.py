"""Polars-based minute bars reader with Decimal precision.

This module provides efficient reading of minute OHLCV bars from Parquet files
with Decimal columns for financial-grade precision.

Parquet Structure:
    data/bundles/<bundle_name>/minute_bars/
    ├── year=2022/
    │   ├── month=01/
    │   │   ├── day=01/
    │   │   │   └── data.parquet
    │   │   ├── day=02/
    │   │   │   └── data.parquet
    │   │   └── ...
    │   └── month=02/
    │       └── ...
    └── year=2023/
        └── ...
"""

from datetime import date, datetime
from pathlib import Path

import polars as pl
import structlog

from rustybt.data.polars.metadata_catalog import ParquetMetadataCatalog
from rustybt.data.polars.validation import DataError, validate_ohlcv_relationships

logger = structlog.get_logger(__name__)


class PolarsParquetMinuteReader:
    """Read minute OHLCV bars from Parquet with Decimal precision.

    This reader uses Polars lazy evaluation and partition pruning for
    efficient data loading from partitioned Parquet files.

    Attributes:
        bundle_path: Path to bundle directory (e.g., "data/bundles/quandl")
        minute_bars_path: Path to minute bars directory
        cache: In-memory cache for recently accessed data

    Example:
        >>> reader = PolarsParquetMinuteReader("data/bundles/quandl")
        >>> df = reader.load_minute_bars(
        ...     sids=[1, 2, 3],
        ...     start_dt=datetime(2023, 1, 1, 9, 30),
        ...     end_dt=datetime(2023, 1, 1, 16, 0)
        ... )
        >>> assert df.schema["open"] == pl.Decimal(18, 8)
    """

    def __init__(
        self,
        bundle_path: str,
        enable_cache: bool = True,
        enable_metadata_catalog: bool = True,
    ):
        """Initialize reader with bundle directory path.

        Args:
            bundle_path: Path to bundle directory (e.g., "data/bundles/quandl")
            enable_cache: Enable in-memory caching for hot data (default: True)
            enable_metadata_catalog: Enable metadata catalog integration (default: True)
        """
        self.bundle_path = Path(bundle_path)
        self.minute_bars_path = self.bundle_path / "minute_bars"
        self.enable_cache = enable_cache
        self._cache: pl.DataFrame | None = None
        self._cache_date_range: tuple[datetime, datetime] | None = None

        # Initialize metadata catalog
        self.enable_metadata_catalog = enable_metadata_catalog
        if enable_metadata_catalog:
            metadata_db_path = self.bundle_path / "metadata.db"
            self.metadata_catalog: ParquetMetadataCatalog | None = ParquetMetadataCatalog(
                str(metadata_db_path)
            )
        else:
            self.metadata_catalog = None

        logger.info(
            "minute_reader_initialized",
            bundle_path=str(bundle_path),
            minute_bars_path=str(self.minute_bars_path),
            enable_cache=enable_cache,
            metadata_catalog_enabled=enable_metadata_catalog,
        )

    def load_minute_bars(
        self,
        sids: list[int],
        start_dt: datetime,
        end_dt: datetime,
        fields: list[str] | None = None,
    ) -> pl.DataFrame:
        """Load minute bars for assets in datetime range.

        Uses lazy loading with partition pruning for efficient queries.
        Validates OHLCV relationships after loading.

        Args:
            sids: List of asset IDs (sids) to load
            start_dt: Start datetime (inclusive)
            end_dt: End datetime (inclusive)
            fields: Columns to load (default: all OHLCV columns)

        Returns:
            Polars DataFrame with Decimal columns for OHLCV data

        Schema:
            dt: pl.Datetime
            sid: pl.Int64
            open: pl.Decimal(18, 8)
            high: pl.Decimal(18, 8)
            low: pl.Decimal(18, 8)
            close: pl.Decimal(18, 8)
            volume: pl.Decimal(18, 8)

        Raises:
            FileNotFoundError: If Parquet files not found for datetime range
            DataError: If no data found or validation fails

        Example:
            >>> reader = PolarsParquetMinuteReader("data/bundles/quandl")
            >>> df = reader.load_minute_bars(
            ...     sids=[1, 2],
            ...     start_dt=datetime(2023, 1, 1, 9, 30),
            ...     end_dt=datetime(2023, 1, 1, 16, 0)
            ... )
            >>> assert len(df) > 0
            >>> assert df["dt"].min() >= datetime(2023, 1, 1, 9, 30)
        """
        fields = fields or ["open", "high", "low", "close", "volume"]

        # Check if data exists
        if not self.minute_bars_path.exists():
            raise FileNotFoundError(f"Minute bars directory not found: {self.minute_bars_path}")

        # Check cache
        if self._use_cache(start_dt, end_dt):
            logger.debug(
                "using_cached_data",
                start_dt=str(start_dt),
                end_dt=str(end_dt),
            )
            df = self._filter_cached_data(sids, start_dt, end_dt, fields)
            return df

        # Lazy load with partition pruning
        try:
            parquet_pattern = str(self.minute_bars_path / "**" / "*.parquet")
            df = (
                pl.scan_parquet(parquet_pattern)
                .filter(pl.col("dt").is_between(start_dt, end_dt, closed="both"))
                .filter(pl.col("sid").is_in(sids))
                .select(["dt", "sid"] + fields)
                .collect()
            )
        except Exception as e:
            raise DataError(f"Failed to load minute bars from {self.minute_bars_path}: {e}") from e

        if len(df) == 0:
            raise DataError(f"No data found for {len(sids)} assets between {start_dt} and {end_dt}")

        # Validate OHLCV relationships
        validate_ohlcv_relationships(df)

        # Update cache if enabled
        if self.enable_cache:
            self._update_cache(df, start_dt, end_dt)

        logger.info(
            "minute_bars_loaded",
            row_count=len(df),
            asset_count=df["sid"].n_unique(),
            start_dt=str(start_dt),
            end_dt=str(end_dt),
        )

        return df

    def get_last_available_dt(self, sid: int) -> datetime | None:
        """Get the last available minute for an asset.

        Args:
            sid: Asset ID

        Returns:
            Last available datetime or None if no data

        Example:
            >>> reader = PolarsParquetMinuteReader("data/bundles/quandl")
            >>> last_dt = reader.get_last_available_dt(sid=1)
        """
        try:
            parquet_pattern = str(self.minute_bars_path / "**" / "*.parquet")
            result = (
                pl.scan_parquet(parquet_pattern)
                .filter(pl.col("sid") == sid)
                .select(pl.col("dt").max().alias("last_dt"))
                .collect()
            )

            if len(result) == 0 or result["last_dt"][0] is None:
                return None

            return result["last_dt"][0]
        except Exception as e:
            logger.error("get_last_dt_failed", sid=sid, error=str(e))
            return None

    def get_first_available_dt(self, sid: int) -> datetime | None:
        """Get the first available minute for an asset.

        Args:
            sid: Asset ID

        Returns:
            First available datetime or None if no data

        Example:
            >>> reader = PolarsParquetMinuteReader("data/bundles/quandl")
            >>> first_dt = reader.get_first_available_dt(sid=1)
        """
        try:
            parquet_pattern = str(self.minute_bars_path / "**" / "*.parquet")
            result = (
                pl.scan_parquet(parquet_pattern)
                .filter(pl.col("sid") == sid)
                .select(pl.col("dt").min().alias("first_dt"))
                .collect()
            )

            if len(result) == 0 or result["first_dt"][0] is None:
                return None

            return result["first_dt"][0]
        except Exception as e:
            logger.error("get_first_dt_failed", sid=sid, error=str(e))
            return None

    def load_spot_value(
        self,
        sids: list[int],
        target_dt: datetime,
        field: str = "close",
    ) -> pl.DataFrame:
        """Load spot values for assets at specific datetime.

        Args:
            sids: List of asset IDs
            target_dt: Target datetime
            field: Field to retrieve (default: "close")

        Returns:
            DataFrame with sid and field value

        Example:
            >>> reader = PolarsParquetMinuteReader("data/bundles/quandl")
            >>> df = reader.load_spot_value([1, 2], datetime(2023, 1, 15, 10, 30), "close")
            >>> assert "close" in df.columns
        """
        df = self.load_minute_bars(
            sids=sids,
            start_dt=target_dt,
            end_dt=target_dt,
            fields=[field],
        )

        return df.select(["sid", field])

    def _use_cache(self, start_dt: datetime, end_dt: datetime) -> bool:
        """Check if cache can be used for datetime range.

        Args:
            start_dt: Query start datetime
            end_dt: Query end datetime

        Returns:
            True if cache contains requested datetime range
        """
        if not self.enable_cache or self._cache is None:
            return False

        if self._cache_date_range is None:
            return False

        cache_start, cache_end = self._cache_date_range
        return start_dt >= cache_start and end_dt <= cache_end

    def _filter_cached_data(
        self,
        sids: list[int],
        start_dt: datetime,
        end_dt: datetime,
        fields: list[str],
    ) -> pl.DataFrame:
        """Filter cached data for query.

        Args:
            sids: Asset IDs
            start_dt: Start datetime
            end_dt: End datetime
            fields: Fields to select

        Returns:
            Filtered DataFrame
        """
        if self._cache is None:
            raise DataError("Cache is None but _use_cache returned True")

        df = (
            self._cache.filter(pl.col("dt").is_between(start_dt, end_dt, closed="both"))
            .filter(pl.col("sid").is_in(sids))
            .select(["dt", "sid"] + fields)
        )

        return df

    def _update_cache(self, df: pl.DataFrame, start_dt: datetime, end_dt: datetime) -> None:
        """Update cache with loaded data.

        Args:
            df: Loaded DataFrame
            start_dt: Start datetime of loaded data
            end_dt: End datetime of loaded data
        """
        self._cache = df
        self._cache_date_range = (start_dt, end_dt)

        logger.debug(
            "cache_updated",
            row_count=len(df),
            date_range=f"{start_dt} to {end_dt}",
        )

    def clear_cache(self) -> None:
        """Clear in-memory cache.

        Example:
            >>> reader = PolarsParquetMinuteReader("data/bundles/quandl")
            >>> reader.clear_cache()
        """
        self._cache = None
        self._cache_date_range = None
        logger.debug("cache_cleared")
