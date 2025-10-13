"""Migration utility for converting HDF5/bcolz bundles to Parquet format.

This module provides tools for migrating Zipline's legacy storage formats (HDF5, bcolz)
to the new Parquet-based storage with Decimal precision.

Migration Process:
1. Read legacy data using Zipline readers
2. Convert to Polars DataFrame with Decimal columns
3. Write to Parquet with compression
4. Validate data integrity
5. Register in metadata catalog

Example:
    >>> migrator = BundleMigrator("data/bundles/quandl")
    >>> migrator.migrate_daily_bars(
    ...     source_format="hdf5",
    ...     compression="zstd",
    ...     validate=True
    ... )
"""

import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import polars as pl
import structlog

from rustybt.data.polars.metadata_catalog import ParquetMetadataCatalog
from rustybt.data.polars.parquet_writer import ParquetWriter

logger = structlog.get_logger(__name__)


SourceFormat = Literal["hdf5", "bcolz"]


class MigrationError(Exception):
    """Raised when migration fails."""

    pass


class BundleMigrator:
    """Migrate legacy HDF5/bcolz bundles to Parquet format.

    Handles data conversion, validation, and metadata catalog registration.

    Attributes:
        bundle_path: Path to bundle directory
        parquet_writer: Parquet writer instance
        metadata_catalog: Metadata catalog for tracking migration

    Example:
        >>> migrator = BundleMigrator("data/bundles/quandl")
        >>> migrator.migrate_daily_bars("hdf5", compression="zstd")
    """

    def __init__(self, bundle_path: str):
        """Initialize migrator for bundle.

        Args:
            bundle_path: Path to bundle directory

        Example:
            >>> migrator = BundleMigrator("data/bundles/quandl")
        """
        self.bundle_path = Path(bundle_path)
        self.legacy_daily_path = self.bundle_path / "daily_bars.h5"
        self.legacy_minute_path = self.bundle_path / "minute_bars" / "minute.bcolz"

        # Initialize Parquet writer
        self.parquet_writer = ParquetWriter(str(bundle_path))

        # Initialize metadata catalog
        metadata_db_path = self.bundle_path / "metadata.db"
        self.metadata_catalog = ParquetMetadataCatalog(str(metadata_db_path))

        logger.info(
            "bundle_migrator_initialized",
            bundle_path=str(bundle_path),
        )

    def migrate_daily_bars(
        self,
        source_format: SourceFormat = "hdf5",
        compression: Literal["snappy", "zstd", "lz4"] | None = "zstd",
        validate: bool = True,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """Migrate daily bars from legacy format to Parquet.

        Args:
            source_format: Source format ('hdf5' or 'bcolz')
            compression: Compression algorithm for Parquet
            validate: Validate data integrity after migration
            batch_size: Number of assets to process per batch

        Returns:
            Migration statistics dictionary

        Raises:
            MigrationError: If migration or validation fails

        Example:
            >>> stats = migrator.migrate_daily_bars("hdf5", compression="zstd")
            >>> assert stats["success"] == True
        """
        start_time = time.time()

        logger.info(
            "migration_started",
            source_format=source_format,
            data_type="daily_bars",
            compression=compression,
        )

        # Create dataset entry in metadata catalog
        dataset_id = self.metadata_catalog.create_dataset(
            source=f"migrated_{source_format}",
            resolution="1d",
            schema_version=1,
        )

        # Read legacy data
        df_pandas = self._read_legacy_daily_bars(source_format)

        # Convert to Polars with Decimal columns
        df_polars = self._convert_to_polars_daily(df_pandas)

        # Get unique symbols for metadata
        if "sid" in df_polars.columns:
            unique_sids = df_polars["sid"].unique().to_list()
            for sid in unique_sids:
                # Add symbol to catalog
                # In real implementation, map sid to actual symbol
                self.metadata_catalog.add_symbol(
                    dataset_id=dataset_id,
                    symbol=f"SID_{sid}",
                    asset_type="equity",
                )

        # Write to Parquet
        output_path = self.parquet_writer.write_daily_bars(
            df=df_polars,
            compression=compression,
            dataset_id=dataset_id,
        )

        # Validate if requested
        if validate:
            self._validate_migration(df_pandas, output_path, "daily")

        duration = time.time() - start_time

        stats = {
            "success": True,
            "source_format": source_format,
            "data_type": "daily_bars",
            "row_count": len(df_polars),
            "asset_count": len(unique_sids) if "sid" in df_polars.columns else 0,
            "dataset_id": dataset_id,
            "output_path": str(output_path),
            "compression": compression,
            "duration_seconds": duration,
        }

        logger.info(
            "migration_completed",
            **stats,
        )

        return stats

    def migrate_minute_bars(
        self,
        source_format: SourceFormat = "bcolz",
        compression: Literal["snappy", "zstd", "lz4"] | None = "zstd",
        validate: bool = True,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Migrate minute bars from legacy format to Parquet.

        Args:
            source_format: Source format ('hdf5' or 'bcolz')
            compression: Compression algorithm for Parquet
            validate: Validate data integrity after migration
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Migration statistics dictionary

        Raises:
            MigrationError: If migration or validation fails

        Example:
            >>> stats = migrator.migrate_minute_bars("bcolz", compression="zstd")
            >>> assert stats["success"] == True
        """
        start_time = time.time()

        logger.info(
            "migration_started",
            source_format=source_format,
            data_type="minute_bars",
            compression=compression,
        )

        # Create dataset entry
        dataset_id = self.metadata_catalog.create_dataset(
            source=f"migrated_{source_format}",
            resolution="1m",
            schema_version=1,
        )

        # Read legacy data
        df_pandas = self._read_legacy_minute_bars(source_format, start_date, end_date)

        # Convert to Polars with Decimal columns
        df_polars = self._convert_to_polars_minute(df_pandas)

        # Write to Parquet
        output_path = self.parquet_writer.write_minute_bars(
            df=df_polars,
            compression=compression,
            dataset_id=dataset_id,
        )

        # Validate if requested
        if validate:
            self._validate_migration(df_pandas, output_path, "minute")

        duration = time.time() - start_time

        stats = {
            "success": True,
            "source_format": source_format,
            "data_type": "minute_bars",
            "row_count": len(df_polars),
            "dataset_id": dataset_id,
            "output_path": str(output_path),
            "compression": compression,
            "duration_seconds": duration,
        }

        logger.info(
            "migration_completed",
            **stats,
        )

        return stats

    def _read_legacy_daily_bars(self, source_format: SourceFormat) -> pd.DataFrame:
        """Read daily bars from legacy format.

        Args:
            source_format: Source format ('hdf5' or 'bcolz')

        Returns:
            Pandas DataFrame with legacy data

        Raises:
            MigrationError: If reading fails
        """
        if source_format == "hdf5":
            if not self.legacy_daily_path.exists():
                raise MigrationError(f"HDF5 daily bars file not found: {self.legacy_daily_path}")

            try:
                # Read HDF5 using pandas
                df = pd.read_hdf(self.legacy_daily_path, key="daily_bars")

                logger.info(
                    "legacy_data_loaded",
                    source_format="hdf5",
                    row_count=len(df),
                )

                return df

            except Exception as e:
                raise MigrationError(f"Failed to read HDF5 daily bars: {e}") from e

        elif source_format == "bcolz":
            # Implement bcolz daily bars migration
            try:
                import bcolz
            except ImportError:
                raise MigrationError("bcolz package not installed. Install with: pip install bcolz")

            if not self.legacy_daily_path.exists():
                # Try alternative path (Zipline bundles use different naming)
                bcolz_path = self.bundle_path / "daily_equities.bcolz"
                if not bcolz_path.exists():
                    raise MigrationError(
                        f"bcolz daily bars not found. Tried: {self.legacy_daily_path}, {bcolz_path}"
                    )
            else:
                bcolz_path = self.legacy_daily_path

            try:
                # Open bcolz ctable
                ctable = bcolz.open(str(bcolz_path))

                # Convert to pandas DataFrame
                # bcolz ctable has columns: open, high, low, close, volume, day, sid
                df = ctable.todataframe()

                # Convert 'day' column to date if it's in epoch format
                if "day" in df.columns:
                    df["date"] = pd.to_datetime(df["day"], unit="D", origin="unix")
                    df = df.drop(columns=["day"])
                elif "date" not in df.columns:
                    raise MigrationError("bcolz ctable missing date/day column")

                logger.info(
                    "legacy_data_loaded",
                    source_format="bcolz",
                    row_count=len(df),
                    columns=df.columns.tolist(),
                )

                return df

            except Exception as e:
                raise MigrationError(
                    f"Failed to read bcolz daily bars from {bcolz_path}: {e}"
                ) from e

        else:
            raise ValueError(f"Unsupported source format: {source_format}")

    def _read_legacy_minute_bars(
        self,
        source_format: SourceFormat,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Read minute bars from legacy format.

        Args:
            source_format: Source format ('hdf5' or 'bcolz')
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Pandas DataFrame with legacy data

        Raises:
            MigrationError: If reading fails
        """
        if source_format == "bcolz":
            # Implement bcolz minute bars migration
            try:
                import bcolz
            except ImportError:
                raise MigrationError("bcolz package not installed. Install with: pip install bcolz")

            # Try different possible paths for minute bars
            possible_paths = [
                self.legacy_minute_path,
                self.bundle_path / "minute_equities.bcolz",
                self.bundle_path / "minute_bars.bcolz",
            ]

            bcolz_path = None
            for path in possible_paths:
                if path.exists():
                    bcolz_path = path
                    break

            if bcolz_path is None:
                raise MigrationError(f"bcolz minute bars not found. Tried: {possible_paths}")

            try:
                # Open bcolz ctable
                ctable = bcolz.open(str(bcolz_path))

                # Convert to pandas DataFrame
                df = ctable.todataframe()

                # Handle timestamp column
                # bcolz minute bars typically use 'minute' or 'timestamp' column
                if "minute" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["minute"], unit="s")
                    df = df.drop(columns=["minute"])
                elif "timestamp" not in df.columns:
                    raise MigrationError("bcolz ctable missing timestamp/minute column")

                # Apply date range filtering if requested
                if start_date is not None:
                    start_ts = pd.Timestamp(start_date)
                    df = df[df["timestamp"] >= start_ts]

                if end_date is not None:
                    end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1)
                    df = df[df["timestamp"] < end_ts]

                logger.info(
                    "legacy_data_loaded",
                    source_format="bcolz",
                    row_count=len(df),
                    start_date=df["timestamp"].min() if len(df) > 0 else None,
                    end_date=df["timestamp"].max() if len(df) > 0 else None,
                )

                return df

            except Exception as e:
                raise MigrationError(
                    f"Failed to read bcolz minute bars from {bcolz_path}: {e}"
                ) from e

        elif source_format == "hdf5":
            # Implement HDF5 minute bars migration
            if not self.bundle_path.exists():
                raise MigrationError(f"Bundle path not found: {self.bundle_path}")

            # Try different possible HDF5 file names for minute bars
            possible_files = [
                self.bundle_path / "minute_bars.h5",
                self.bundle_path / "minute_equities.h5",
                self.bundle_path / "adjustments.h5",  # Some bundles store minute data here
            ]

            hdf5_path = None
            for path in possible_files:
                if path.exists():
                    hdf5_path = path
                    break

            if hdf5_path is None:
                raise MigrationError(f"HDF5 minute bars file not found. Tried: {possible_files}")

            try:
                # Try different HDF5 keys that might contain minute bars
                possible_keys = ["minute_bars", "minute_equities", "ohlcv"]

                df = None
                for key in possible_keys:
                    try:
                        df = pd.read_hdf(hdf5_path, key=key)
                        break
                    except (KeyError, ValueError):
                        continue

                if df is None:
                    # Try reading without key specification
                    try:
                        df = pd.read_hdf(hdf5_path)
                    except Exception as e:
                        raise MigrationError(
                            f"Could not read minute bars from {hdf5_path}. "
                            f"Tried keys: {possible_keys}. Error: {e}"
                        )

                # Ensure timestamp column exists
                if isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index()
                    df = df.rename(columns={"index": "timestamp"})
                elif "timestamp" not in df.columns and "date" in df.columns:
                    df = df.rename(columns={"date": "timestamp"})
                elif "timestamp" not in df.columns:
                    raise MigrationError("HDF5 data missing timestamp column")

                # Apply date range filtering
                if start_date is not None:
                    start_ts = pd.Timestamp(start_date)
                    df = df[df["timestamp"] >= start_ts]

                if end_date is not None:
                    end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1)
                    df = df[df["timestamp"] < end_ts]

                logger.info(
                    "legacy_data_loaded",
                    source_format="hdf5",
                    row_count=len(df),
                    start_date=df["timestamp"].min() if len(df) > 0 else None,
                    end_date=df["timestamp"].max() if len(df) > 0 else None,
                )

                return df

            except Exception as e:
                raise MigrationError(
                    f"Failed to read HDF5 minute bars from {hdf5_path}: {e}"
                ) from e

        else:
            raise ValueError(f"Unsupported source format: {source_format}")

    def _convert_to_polars_daily(self, df_pandas: pd.DataFrame) -> pl.DataFrame:
        """Convert pandas DataFrame to Polars with Decimal columns for daily data.

        Args:
            df_pandas: Pandas DataFrame from legacy format

        Returns:
            Polars DataFrame with Decimal columns

        Example:
            >>> df_polars = migrator._convert_to_polars_daily(df_pandas)
            >>> assert df_polars.schema["open"] == pl.Decimal(18, 8)
        """
        # Reset index if date is index
        if isinstance(df_pandas.index, pd.DatetimeIndex):
            df_pandas = df_pandas.reset_index()
            df_pandas = df_pandas.rename(columns={"index": "date"})

        # Convert float columns to Decimal strings for precision
        decimal_cols = ["open", "high", "low", "close", "volume"]
        for col in decimal_cols:
            if col in df_pandas.columns:
                # Convert float to Decimal string to preserve precision
                df_pandas[col] = df_pandas[col].apply(
                    lambda x: str(Decimal(str(x))) if pd.notna(x) else None
                )

        # Convert to Polars
        df_polars = pl.from_pandas(df_pandas)

        # Cast to proper schema
        for col in decimal_cols:
            if col in df_polars.columns:
                df_polars = df_polars.with_columns(
                    pl.col(col).cast(pl.Decimal(precision=18, scale=8))
                )

        # Ensure date column is Date type
        if "date" in df_polars.columns:
            df_polars = df_polars.with_columns(pl.col("date").cast(pl.Date))

        logger.debug(
            "converted_to_polars_daily",
            row_count=len(df_polars),
            columns=df_polars.columns,
        )

        return df_polars

    def _convert_to_polars_minute(self, df_pandas: pd.DataFrame) -> pl.DataFrame:
        """Convert pandas DataFrame to Polars with Decimal columns for minute data.

        Args:
            df_pandas: Pandas DataFrame from legacy format

        Returns:
            Polars DataFrame with Decimal columns
        """
        # Reset index if timestamp is index
        if isinstance(df_pandas.index, pd.DatetimeIndex):
            df_pandas = df_pandas.reset_index()
            df_pandas = df_pandas.rename(columns={"index": "timestamp"})

        # Convert float columns to Decimal strings
        decimal_cols = ["open", "high", "low", "close", "volume"]
        for col in decimal_cols:
            if col in df_pandas.columns:
                df_pandas[col] = df_pandas[col].apply(
                    lambda x: str(Decimal(str(x))) if pd.notna(x) else None
                )

        # Convert to Polars
        df_polars = pl.from_pandas(df_pandas)

        # Cast to proper schema
        for col in decimal_cols:
            if col in df_polars.columns:
                df_polars = df_polars.with_columns(
                    pl.col(col).cast(pl.Decimal(precision=18, scale=8))
                )

        # Ensure timestamp column is Datetime type
        if "timestamp" in df_polars.columns:
            df_polars = df_polars.with_columns(pl.col("timestamp").cast(pl.Datetime("us")))

        logger.debug(
            "converted_to_polars_minute",
            row_count=len(df_polars),
            columns=df_polars.columns,
        )

        return df_polars

    def _validate_migration(
        self,
        source_df: pd.DataFrame,
        parquet_path: Path,
        data_type: Literal["daily", "minute"],
    ) -> None:
        """Validate migrated data matches source.

        Args:
            source_df: Original pandas DataFrame
            parquet_path: Path to migrated Parquet file
            data_type: Type of data ('daily' or 'minute')

        Raises:
            MigrationError: If validation fails
        """
        # Read back Parquet
        df_parquet = pl.read_parquet(parquet_path)

        # Compare row counts
        if len(source_df) != len(df_parquet):
            raise MigrationError(
                f"Row count mismatch: source={len(source_df)}, parquet={len(df_parquet)}"
            )

        # Spot check random samples (convert Decimal to float for comparison)
        sample_size = min(100, len(source_df))
        sample_indices = source_df.sample(sample_size).index

        decimal_cols = ["open", "high", "low", "close", "volume"]
        for idx in sample_indices:
            for col in decimal_cols:
                if col in source_df.columns and col in df_parquet.columns:
                    source_val = float(source_df.loc[idx, col])
                    # Find corresponding row in Parquet
                    # This is simplified - real implementation needs proper matching
                    parquet_val = float(
                        df_parquet.filter(pl.col("sid") == source_df.loc[idx, "sid"])
                        .select(col)
                        .head(1)[col][0]
                    )

                    # Allow small floating point difference
                    if abs(source_val - parquet_val) > 1e-6:
                        raise MigrationError(
                            f"Value mismatch at index {idx}, column {col}: "
                            f"source={source_val}, parquet={parquet_val}"
                        )

        logger.info(
            "migration_validated",
            data_type=data_type,
            sample_size=sample_size,
        )


def migrate_bundle(
    bundle_path: str,
    source_format: SourceFormat = "hdf5",
    compression: Literal["snappy", "zstd", "lz4"] | None = "zstd",
    migrate_daily: bool = True,
    migrate_minute: bool = False,
    validate: bool = True,
) -> dict[str, Any]:
    """Convenience function to migrate entire bundle.

    Args:
        bundle_path: Path to bundle directory
        source_format: Source format ('hdf5' or 'bcolz')
        compression: Compression algorithm
        migrate_daily: Migrate daily bars
        migrate_minute: Migrate minute bars
        validate: Validate migration

    Returns:
        Migration statistics

    Example:
        >>> stats = migrate_bundle(
        ...     "data/bundles/quandl",
        ...     source_format="hdf5",
        ...     compression="zstd"
        ... )
        >>> assert stats["daily"]["success"] == True
    """
    migrator = BundleMigrator(bundle_path)

    results = {}

    if migrate_daily:
        results["daily"] = migrator.migrate_daily_bars(
            source_format=source_format,
            compression=compression,
            validate=validate,
        )

    if migrate_minute:
        results["minute"] = migrator.migrate_minute_bars(
            source_format=source_format,
            compression=compression,
            validate=validate,
        )

    return results
