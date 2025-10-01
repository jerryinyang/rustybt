"""Parquet write operations with compression and partitioning.

This module handles writing OHLCV data to Parquet format with:
- Decimal precision preservation
- Compression (Snappy or ZSTD)
- Hive-style partitioning (year/month/day)
- Atomic write operations
- Metadata catalog integration

Example:
    >>> from decimal import Decimal
    >>> import polars as pl
    >>> from datetime import date
    >>>
    >>> df = pl.DataFrame({
    ...     "date": [date(2023, 1, 1)],
    ...     "sid": [1],
    ...     "open": [Decimal("100.12345678")],
    ...     "close": [Decimal("101.50000000")],
    ... })
    >>>
    >>> writer = ParquetWriter("data/bundles/quandl")
    >>> writer.write_daily_bars(df, compression="zstd")
"""

import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, Literal

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from rustybt.data.polars.parquet_schema import DAILY_BARS_SCHEMA, MINUTE_BARS_SCHEMA, validate_schema
from rustybt.data.polars.metadata_catalog import ParquetMetadataCatalog, calculate_file_checksum

logger = structlog.get_logger(__name__)


CompressionType = Literal["snappy", "zstd", "lz4", None]


class ParquetWriter:
    """Write OHLCV data to Parquet with compression and metadata tracking.

    Handles atomic writes, partitioning, compression, and metadata catalog updates.

    Attributes:
        bundle_path: Path to bundle directory
        daily_bars_path: Path to daily bars storage
        minute_bars_path: Path to minute bars storage
        metadata_catalog: Metadata catalog for tracking writes

    Example:
        >>> writer = ParquetWriter("data/bundles/quandl")
        >>> writer.write_daily_bars(df, compression="zstd")
    """

    def __init__(
        self,
        bundle_path: str,
        enable_metadata_catalog: bool = True,
    ):
        """Initialize Parquet writer.

        Args:
            bundle_path: Path to bundle directory
            enable_metadata_catalog: Enable metadata catalog tracking

        Example:
            >>> writer = ParquetWriter("data/bundles/quandl")
        """
        self.bundle_path = Path(bundle_path)
        self.daily_bars_path = self.bundle_path / "daily_bars"
        self.minute_bars_path = self.bundle_path / "minute_bars"

        # Create directories
        self.daily_bars_path.mkdir(parents=True, exist_ok=True)
        self.minute_bars_path.mkdir(parents=True, exist_ok=True)

        # Initialize metadata catalog
        self.enable_metadata_catalog = enable_metadata_catalog
        if enable_metadata_catalog:
            metadata_db_path = self.bundle_path / "metadata.db"
            self.metadata_catalog = ParquetMetadataCatalog(str(metadata_db_path))
        else:
            self.metadata_catalog = None

        logger.info(
            "parquet_writer_initialized",
            bundle_path=str(bundle_path),
            metadata_enabled=enable_metadata_catalog,
        )

    def write_daily_bars(
        self,
        df: pl.DataFrame,
        compression: CompressionType = "zstd",
        dataset_id: Optional[int] = None,
    ) -> Path:
        """Write daily bars to Parquet with partitioning.

        Uses year/month partitioning for daily data. Validates schema before writing.

        Args:
            df: Polars DataFrame with OHLCV data
            compression: Compression algorithm ('snappy', 'zstd', 'lz4', None)
            dataset_id: Optional dataset ID for metadata tracking

        Returns:
            Path to written Parquet file

        Raises:
            ValueError: If schema validation fails

        Example:
            >>> df = pl.DataFrame({
            ...     "date": [date(2023, 1, 1)],
            ...     "sid": [1],
            ...     "open": [Decimal("100.12345678")],
            ... }, schema=DAILY_BARS_SCHEMA)
            >>> writer.write_daily_bars(df, compression="zstd")
        """
        # Validate schema
        validate_schema(df, DAILY_BARS_SCHEMA)

        # Extract year/month for partitioning
        df_with_partitions = df.with_columns([
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.month().alias("month"),
        ])

        # Write with Hive partitioning
        output_path = self._write_partitioned_parquet(
            df_with_partitions,
            self.daily_bars_path,
            partition_cols=["year", "month"],
            compression=compression,
        )

        # Update metadata catalog
        if self.metadata_catalog and dataset_id is not None:
            self._update_metadata_catalog(
                dataset_id=dataset_id,
                parquet_path=output_path,
                df=df,
            )

        logger.info(
            "daily_bars_written",
            output_path=str(output_path),
            row_count=len(df),
            compression=compression,
        )

        return output_path

    def write_minute_bars(
        self,
        df: pl.DataFrame,
        compression: CompressionType = "zstd",
        dataset_id: Optional[int] = None,
    ) -> Path:
        """Write minute bars to Parquet with year/month/day partitioning.

        Uses finer-grained partitioning for minute data due to larger volume.

        Args:
            df: Polars DataFrame with minute-level OHLCV data
            compression: Compression algorithm ('snappy', 'zstd', 'lz4', None)
            dataset_id: Optional dataset ID for metadata tracking

        Returns:
            Path to written Parquet file

        Raises:
            ValueError: If schema validation fails

        Example:
            >>> df = pl.DataFrame({
            ...     "timestamp": [datetime(2023, 1, 1, 9, 30)],
            ...     "sid": [1],
            ...     "close": [Decimal("100.50000000")],
            ... }, schema=MINUTE_BARS_SCHEMA)
            >>> writer.write_minute_bars(df, compression="zstd")
        """
        # Validate schema
        validate_schema(df, MINUTE_BARS_SCHEMA)

        # Extract year/month/day for partitioning
        df_with_partitions = df.with_columns([
            pl.col("timestamp").dt.year().alias("year"),
            pl.col("timestamp").dt.month().alias("month"),
            pl.col("timestamp").dt.day().alias("day"),
        ])

        # Write with Hive partitioning
        output_path = self._write_partitioned_parquet(
            df_with_partitions,
            self.minute_bars_path,
            partition_cols=["year", "month", "day"],
            compression=compression,
        )

        # Update metadata catalog
        if self.metadata_catalog and dataset_id is not None:
            self._update_metadata_catalog(
                dataset_id=dataset_id,
                parquet_path=output_path,
                df=df,
            )

        logger.info(
            "minute_bars_written",
            output_path=str(output_path),
            row_count=len(df),
            compression=compression,
        )

        return output_path

    def _write_partitioned_parquet(
        self,
        df: pl.DataFrame,
        base_path: Path,
        partition_cols: list[str],
        compression: CompressionType,
    ) -> Path:
        """Write DataFrame to partitioned Parquet using atomic write pattern.

        Uses temp file + rename for atomic writes to prevent partial writes.

        Args:
            df: DataFrame to write
            base_path: Base directory for partitioned data
            partition_cols: Columns to partition by
            compression: Compression algorithm

        Returns:
            Path to written Parquet directory

        Example:
            >>> path = writer._write_partitioned_parquet(
            ...     df, Path("data/daily_bars"), ["year", "month"], "zstd"
            ... )
        """
        # Convert to Arrow Table for partitioned write
        arrow_table = df.to_arrow()

        # Determine partition path
        # For simplicity, write to single file per partition
        # In production, use pyarrow.dataset.write_dataset for better partitioning
        first_row = df.row(0, named=True)
        partition_values = [first_row[col] for col in partition_cols]
        partition_path = base_path / "/".join(
            f"{col}={val}" for col, val in zip(partition_cols, partition_values)
        )
        partition_path.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file + rename
        output_file = partition_path / "data.parquet"
        temp_file = partition_path / f".data.parquet.tmp.{int(datetime.now().timestamp())}"

        try:
            # Write to temp file
            pq.write_table(
                arrow_table,
                temp_file,
                compression=compression,
                use_dictionary=True,  # Dictionary encoding for string columns
                write_statistics=True,  # Enable Parquet statistics for pruning
            )

            # Atomic rename
            temp_file.rename(output_file)

            logger.debug(
                "parquet_written_atomically",
                output_file=str(output_file),
                compression=compression,
            )

            return output_file

        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            raise RuntimeError(
                f"Failed to write Parquet file to {output_file}: {e}"
            ) from e

    def _update_metadata_catalog(
        self,
        dataset_id: int,
        parquet_path: Path,
        df: pl.DataFrame,
    ) -> None:
        """Update metadata catalog with written Parquet file info.

        Args:
            dataset_id: Dataset ID
            parquet_path: Path to written Parquet file
            df: DataFrame that was written
        """
        if self.metadata_catalog is None:
            return

        # Calculate checksum
        checksum = calculate_file_checksum(parquet_path)

        # Get relative path from bundle root
        relative_path = parquet_path.relative_to(self.bundle_path)

        # Add checksum to catalog
        self.metadata_catalog.add_checksum(
            dataset_id=dataset_id,
            parquet_path=str(relative_path),
            checksum=checksum,
        )

        # Update date range if date/timestamp column exists
        if "date" in df.columns:
            min_date = df["date"].min()
            max_date = df["date"].max()
            self.metadata_catalog.update_date_range(
                dataset_id=dataset_id,
                start_date=min_date,
                end_date=max_date,
            )
        elif "timestamp" in df.columns:
            min_ts = df["timestamp"].min()
            max_ts = df["timestamp"].max()
            self.metadata_catalog.update_date_range(
                dataset_id=dataset_id,
                start_date=min_ts.date() if min_ts else date.today(),
                end_date=max_ts.date() if max_ts else date.today(),
            )

        logger.debug(
            "metadata_catalog_updated",
            dataset_id=dataset_id,
            parquet_path=str(relative_path),
            checksum=checksum[:16] + "...",  # Log first 16 chars
        )

    def write_batch(
        self,
        dataframes: list[pl.DataFrame],
        resolution: Literal["daily", "minute"],
        compression: CompressionType = "zstd",
        dataset_id: Optional[int] = None,
    ) -> list[Path]:
        """Write multiple DataFrames in batch.

        Args:
            dataframes: List of DataFrames to write
            resolution: Data resolution ('daily' or 'minute')
            compression: Compression algorithm
            dataset_id: Optional dataset ID for metadata tracking

        Returns:
            List of written Parquet file paths

        Example:
            >>> dfs = [df1, df2, df3]
            >>> paths = writer.write_batch(dfs, "daily", compression="zstd")
        """
        paths = []

        for df in dataframes:
            if resolution == "daily":
                path = self.write_daily_bars(df, compression, dataset_id)
            elif resolution == "minute":
                path = self.write_minute_bars(df, compression, dataset_id)
            else:
                raise ValueError(f"Invalid resolution: {resolution}")

            paths.append(path)

        logger.info(
            "batch_write_complete",
            batch_size=len(dataframes),
            resolution=resolution,
            total_rows=sum(len(df) for df in dataframes),
        )

        return paths


def get_compression_stats(
    df: pl.DataFrame,
    compression: CompressionType = "zstd",
) -> dict[str, float]:
    """Get compression statistics for DataFrame.

    Args:
        df: DataFrame to analyze
        compression: Compression algorithm to test

    Returns:
        Dictionary with compression statistics:
        - uncompressed_size_mb: Size without compression
        - compressed_size_mb: Size with compression
        - compression_ratio: Ratio (0.0-1.0, lower is better)
        - space_saved_percent: Percentage saved

    Example:
        >>> stats = get_compression_stats(df, "zstd")
        >>> assert stats["compression_ratio"] < 0.5  # >50% compression
    """
    import os

    # Write uncompressed
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        uncompressed_path = Path(tmp.name)

    arrow_table = df.to_arrow()
    pq.write_table(arrow_table, uncompressed_path, compression=None)
    uncompressed_size = uncompressed_path.stat().st_size
    uncompressed_path.unlink()

    # Write compressed
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        compressed_path = Path(tmp.name)

    pq.write_table(arrow_table, compressed_path, compression=compression)
    compressed_size = compressed_path.stat().st_size
    compressed_path.unlink()

    compression_ratio = compressed_size / uncompressed_size
    space_saved_percent = (1 - compression_ratio) * 100

    return {
        "uncompressed_size_mb": uncompressed_size / (1024 * 1024),
        "compressed_size_mb": compressed_size / (1024 * 1024),
        "compression_ratio": compression_ratio,
        "space_saved_percent": space_saved_percent,
    }
