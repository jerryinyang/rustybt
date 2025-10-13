"""Polars-based daily bars reader with Decimal precision.

This module provides efficient reading of daily OHLCV bars from Parquet files
with Decimal columns for financial-grade precision.

Parquet Structure:
    data/bundles/<bundle_name>/daily_bars/
    ├── year=2022/
    │   ├── month=01/
    │   │   └── data.parquet
    │   └── month=02/
    │       └── data.parquet
    └── year=2023/
        └── ...
"""

from datetime import date
from pathlib import Path

import polars as pl
import structlog

from rustybt.data.polars.metadata_catalog import ParquetMetadataCatalog
from rustybt.data.polars.validation import DataError, validate_ohlcv_relationships

logger = structlog.get_logger(__name__)


class PolarsParquetDailyReader:
    """Read daily OHLCV bars from Parquet with Decimal precision.

    This reader uses Polars lazy evaluation and partition pruning for
    efficient data loading from partitioned Parquet files.

    Attributes:
        bundle_path: Path to bundle directory (e.g., "data/bundles/quandl")
        daily_bars_path: Path to daily bars directory
        cache: In-memory cache for recently accessed data

    Example:
        >>> reader = PolarsParquetDailyReader("data/bundles/quandl")
        >>> df = reader.load_daily_bars(
        ...     sids=[1, 2, 3],
        ...     start_date=date(2023, 1, 1),
        ...     end_date=date(2023, 1, 31)
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
        self.daily_bars_path = self.bundle_path / "daily_bars"
        self.enable_cache = enable_cache
        self._cache: pl.DataFrame | None = None
        self._cache_date_range: tuple[date, date] | None = None

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
            "daily_reader_initialized",
            bundle_path=str(bundle_path),
            daily_bars_path=str(self.daily_bars_path),
            enable_cache=enable_cache,
            metadata_catalog_enabled=enable_metadata_catalog,
        )

    def load_daily_bars(
        self,
        sids: list[int],
        start_date: date,
        end_date: date,
        fields: list[str] | None = None,
    ) -> pl.DataFrame:
        """Load daily bars for assets in date range.

        Uses lazy loading with partition pruning for efficient queries.
        Validates OHLCV relationships after loading.

        Args:
            sids: List of asset IDs (sids) to load
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            fields: Columns to load (default: all OHLCV columns)

        Returns:
            Polars DataFrame with Decimal columns for OHLCV data

        Schema:
            date: pl.Date
            sid: pl.Int64
            open: pl.Decimal(18, 8)
            high: pl.Decimal(18, 8)
            low: pl.Decimal(18, 8)
            close: pl.Decimal(18, 8)
            volume: pl.Decimal(18, 8)

        Raises:
            FileNotFoundError: If Parquet files not found for date range
            DataError: If no data found or validation fails

        Example:
            >>> reader = PolarsParquetDailyReader("data/bundles/quandl")
            >>> df = reader.load_daily_bars(
            ...     sids=[1, 2],
            ...     start_date=date(2023, 1, 1),
            ...     end_date=date(2023, 1, 31)
            ... )
            >>> assert len(df) > 0
            >>> assert df["date"].min() >= date(2023, 1, 1)
        """
        fields = fields or ["open", "high", "low", "close", "volume"]

        # Check if data exists
        if not self.daily_bars_path.exists():
            raise FileNotFoundError(f"Daily bars directory not found: {self.daily_bars_path}")

        # Check cache
        if self._use_cache(start_date, end_date):
            logger.debug(
                "using_cached_data",
                start_date=str(start_date),
                end_date=str(end_date),
            )
            df = self._filter_cached_data(sids, start_date, end_date, fields)
            return df

        # Lazy load with partition pruning
        try:
            parquet_pattern = str(self.daily_bars_path / "**" / "*.parquet")
            df = (
                pl.scan_parquet(parquet_pattern)
                .filter(pl.col("date").is_between(start_date, end_date, closed="both"))
                .filter(pl.col("sid").is_in(sids))
                .select(["date", "sid"] + fields)
                .collect()
            )
        except Exception as e:
            raise DataError(f"Failed to load daily bars from {self.daily_bars_path}: {e}") from e

        if len(df) == 0:
            raise DataError(
                f"No data found for {len(sids)} assets between {start_date} and {end_date}"
            )

        # Validate OHLCV relationships
        validate_ohlcv_relationships(df)

        # Update cache if enabled
        if self.enable_cache:
            self._update_cache(df, start_date, end_date)

        logger.info(
            "daily_bars_loaded",
            row_count=len(df),
            asset_count=df["sid"].n_unique(),
            start_date=str(start_date),
            end_date=str(end_date),
        )

        return df

    def get_last_available_date(self, sid: int) -> date | None:
        """Get the last available trading date for an asset.

        Args:
            sid: Asset ID

        Returns:
            Last available date or None if no data

        Example:
            >>> reader = PolarsParquetDailyReader("data/bundles/quandl")
            >>> last_date = reader.get_last_available_date(sid=1)
        """
        try:
            parquet_pattern = str(self.daily_bars_path / "**" / "*.parquet")
            result = (
                pl.scan_parquet(parquet_pattern)
                .filter(pl.col("sid") == sid)
                .select(pl.col("date").max().alias("last_date"))
                .collect()
            )

            if len(result) == 0 or result["last_date"][0] is None:
                return None

            return result["last_date"][0]
        except Exception as e:
            logger.error("get_last_date_failed", sid=sid, error=str(e))
            return None

    def get_first_available_date(self, sid: int) -> date | None:
        """Get the first available trading date for an asset.

        Args:
            sid: Asset ID

        Returns:
            First available date or None if no data

        Example:
            >>> reader = PolarsParquetDailyReader("data/bundles/quandl")
            >>> first_date = reader.get_first_available_date(sid=1)
        """
        try:
            parquet_pattern = str(self.daily_bars_path / "**" / "*.parquet")
            result = (
                pl.scan_parquet(parquet_pattern)
                .filter(pl.col("sid") == sid)
                .select(pl.col("date").min().alias("first_date"))
                .collect()
            )

            if len(result) == 0 or result["first_date"][0] is None:
                return None

            return result["first_date"][0]
        except Exception as e:
            logger.error("get_first_date_failed", sid=sid, error=str(e))
            return None

    def load_spot_value(
        self,
        sids: list[int],
        target_date: date,
        field: str = "close",
    ) -> pl.DataFrame:
        """Load spot values for assets at specific date.

        Args:
            sids: List of asset IDs
            target_date: Target date
            field: Field to retrieve (default: "close")

        Returns:
            DataFrame with sid and field value

        Example:
            >>> reader = PolarsParquetDailyReader("data/bundles/quandl")
            >>> df = reader.load_spot_value([1, 2], date(2023, 1, 15), "close")
            >>> assert "close" in df.columns
        """
        df = self.load_daily_bars(
            sids=sids,
            start_date=target_date,
            end_date=target_date,
            fields=[field],
        )

        return df.select(["sid", field])

    def _use_cache(self, start_date: date, end_date: date) -> bool:
        """Check if cache can be used for date range.

        Args:
            start_date: Query start date
            end_date: Query end date

        Returns:
            True if cache contains requested date range
        """
        if not self.enable_cache or self._cache is None:
            return False

        if self._cache_date_range is None:
            return False

        cache_start, cache_end = self._cache_date_range
        return start_date >= cache_start and end_date <= cache_end

    def _filter_cached_data(
        self,
        sids: list[int],
        start_date: date,
        end_date: date,
        fields: list[str],
    ) -> pl.DataFrame:
        """Filter cached data for query.

        Args:
            sids: Asset IDs
            start_date: Start date
            end_date: End date
            fields: Fields to select

        Returns:
            Filtered DataFrame
        """
        if self._cache is None:
            raise DataError("Cache is None but _use_cache returned True")

        df = (
            self._cache.filter(pl.col("date").is_between(start_date, end_date, closed="both"))
            .filter(pl.col("sid").is_in(sids))
            .select(["date", "sid"] + fields)
        )

        return df

    def _update_cache(self, df: pl.DataFrame, start_date: date, end_date: date) -> None:
        """Update cache with loaded data.

        Args:
            df: Loaded DataFrame
            start_date: Start date of loaded data
            end_date: End date of loaded data
        """
        self._cache = df
        self._cache_date_range = (start_date, end_date)

        logger.debug(
            "cache_updated",
            row_count=len(df),
            date_range=f"{start_date} to {end_date}",
        )

    def clear_cache(self) -> None:
        """Clear in-memory cache.

        Example:
            >>> reader = PolarsParquetDailyReader("data/bundles/quandl")
            >>> reader.clear_cache()
        """
        self._cache = None
        self._cache_date_range = None
        logger.debug("cache_cleared")
