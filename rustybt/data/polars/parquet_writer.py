"""Parquet write operations with compression and unified metadata tracking."""

import hashlib
import tempfile
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Any, Literal

import polars as pl
import pyarrow.parquet as pq
import structlog

from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.polars.metadata_catalog import (
    ParquetMetadataCatalog,
    calculate_file_checksum,
)
from rustybt.data.polars.parquet_schema import (
    DAILY_BARS_SCHEMA,
    MINUTE_BARS_SCHEMA,
    validate_schema,
)

logger = structlog.get_logger(__name__)


CompressionType = Literal["snappy", "zstd", "lz4"] | None


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
        dataset_id: int | None = None,
        source_metadata: dict | None = None,
        bundle_name: str | None = None,
    ) -> Path:
        """Write daily bars to Parquet with partitioning and auto-populate metadata.

        Uses year/month partitioning for daily data. Validates schema before writing.
        Automatically populates BundleMetadata with provenance, quality, and symbols.

        Args:
            df: Polars DataFrame with OHLCV data
            compression: Compression algorithm ('snappy', 'zstd', 'lz4', None)
            dataset_id: Optional dataset ID for metadata tracking
            source_metadata: Source provenance metadata (source_type, source_url, api_version)
            bundle_name: Bundle name for unified metadata tracking

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
            >>> metadata = {"source_type": "yfinance", "source_url": "https://..."}
            >>> writer.write_daily_bars(df, compression="zstd", source_metadata=metadata, bundle_name="test-bundle")
        """
        df_cast = df.cast(DAILY_BARS_SCHEMA, strict=False)

        # Validate schema
        validate_schema(df_cast, DAILY_BARS_SCHEMA)

        # Extract year/month for partitioning
        df_with_partitions = df_cast.with_columns(
            [
                pl.col("date").dt.year().alias("year"),
                pl.col("date").dt.month().alias("month"),
            ]
        )

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
                df=df_cast,
            )

        # Auto-populate unified BundleMetadata (Story 8.4 Phase 3)
        if source_metadata and bundle_name:
            self._auto_populate_metadata(
                df=df_cast,
                bundle_name=bundle_name,
                output_path=output_path,
                source_metadata=source_metadata,
            )

        logger.info(
            "daily_bars_written",
            output_path=str(output_path),
            row_count=len(df_cast),
            compression=compression,
        )

        return output_path

    def write_minute_bars(
        self,
        df: pl.DataFrame,
        compression: CompressionType = "zstd",
        dataset_id: int | None = None,
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
        df_cast = df.cast(MINUTE_BARS_SCHEMA, strict=False)

        # Validate schema
        validate_schema(df_cast, MINUTE_BARS_SCHEMA)

        # Extract year/month/day for partitioning
        df_with_partitions = df_cast.with_columns(
            [
                pl.col("timestamp").dt.year().alias("year"),
                pl.col("timestamp").dt.month().alias("month"),
                pl.col("timestamp").dt.day().alias("day"),
            ]
        )

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
                df=df_cast,
            )

        logger.info(
            "minute_bars_written",
            output_path=str(output_path),
            row_count=len(df_cast),
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
            f"{col}={val}" for col, val in zip(partition_cols, partition_values, strict=False)
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
            raise RuntimeError(f"Failed to write Parquet file to {output_file}: {e}") from e

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
        dataset_id: int | None = None,
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

    def _auto_populate_metadata(
        self,
        df: pl.DataFrame,
        bundle_name: str,
        output_path: Path,
        source_metadata: dict[str, Any],
    ) -> None:
        """Populate unified metadata after successful write."""
        current_time = int(time.time())

        row_count = len(df)
        file_size = output_path.stat().st_size
        file_checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()

        start_timestamp: int | None = None
        end_timestamp: int | None = None
        missing_days_list: list[str] = []
        missing_days_count = 0

        if row_count > 0 and "date" in df.columns:
            date_series = df["date"].unique().sort()
            unique_values = date_series.to_list()

            normalized_dates: list[date] = []
            for value in unique_values:
                if isinstance(value, datetime):
                    normalized_dates.append(value.date())
                elif isinstance(value, date):
                    normalized_dates.append(value)

            if normalized_dates:
                normalized_dates.sort()
                start_date = normalized_dates[0]
                end_date = normalized_dates[-1]

                start_dt = datetime.combine(start_date, dtime.min, tzinfo=UTC)
                end_dt = datetime.combine(end_date, dtime.min, tzinfo=UTC)
                start_timestamp = int(start_dt.timestamp())
                end_timestamp = int(end_dt.timestamp())

                expected_dates = {
                    start_date + timedelta(days=offset)
                    for offset in range((end_date - start_date).days + 1)
                }
                actual_dates = set(normalized_dates)
                missing_dates = sorted(expected_dates - actual_dates)
                missing_days_list = [d.isoformat() for d in missing_dates]
                missing_days_count = len(missing_dates)

        validation_result = self._validate_ohlcv(df)
        violations = validation_result["violations"]
        validation_passed = validation_result["passed"] and missing_days_count == 0

        update_payload: dict[str, Any] = {
            "source_type": source_metadata.get("source_type", "unknown"),
            "fetch_timestamp": current_time,
            "row_count": row_count,
            "start_date": start_timestamp,
            "end_date": end_timestamp,
            "missing_days_count": missing_days_count,
            "missing_days_list": missing_days_list,
            "outlier_count": 0,
            "ohlcv_violations": violations,
            "validation_passed": validation_passed,
            "validation_timestamp": current_time,
            "file_checksum": file_checksum,
            "file_size_bytes": file_size,
        }

        for field in ("source_url", "api_version", "data_version", "timezone"):
            value = source_metadata.get(field)
            if value is not None:
                update_payload[field] = value

        BundleMetadata.update(bundle_name=bundle_name, **update_payload)

        symbol_entries = self._resolve_symbol_entries(df, source_metadata)
        exchange_default = source_metadata.get("exchange")

        added_symbols = 0
        for entry in symbol_entries:
            symbol = entry.get("symbol")
            if not symbol:
                continue

            asset_type = entry.get("asset_type") or self._infer_asset_type(symbol)
            exchange = entry.get("exchange") or exchange_default

            BundleMetadata.add_symbol(
                bundle_name=bundle_name,
                symbol=symbol,
                asset_type=asset_type,
                exchange=exchange,
            )
            added_symbols += 1

        logger.debug(
            "bundle_metadata_autopopulated",
            bundle_name=bundle_name,
            row_count=row_count,
            file_size=file_size,
            validation_passed=validation_passed,
            violations=violations,
            missing_days=missing_days_count,
            symbols_added=added_symbols,
        )

    def _resolve_symbol_entries(
        self,
        df: pl.DataFrame,
        source_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Resolve symbol entries from DataFrame and metadata."""
        entries: list[dict[str, Any]] = []
        unique_symbols: list[Any] = []

        if "symbol" in df.columns:
            unique_symbols = df["symbol"].unique().to_list()
            entries = [{"symbol": symbol} for symbol in unique_symbols]
        else:
            metadata_symbols = source_metadata.get("symbols") or []
            if metadata_symbols:
                for symbol_data in metadata_symbols:
                    if isinstance(symbol_data, str):
                        entries.append({"symbol": symbol_data})
                    elif isinstance(symbol_data, dict):
                        entries.append(
                            {
                                "symbol": symbol_data.get("symbol"),
                                "asset_type": symbol_data.get("asset_type"),
                                "exchange": symbol_data.get("exchange"),
                            }
                        )
            else:
                symbol_map = source_metadata.get("symbol_map")
                if symbol_map and "sid" in df.columns:
                    unique_sids = df["sid"].unique().to_list()
                    for sid in unique_sids:
                        mapping = symbol_map.get(sid)
                        if mapping is None:
                            continue
                        if isinstance(mapping, str):
                            entries.append({"symbol": mapping})
                        elif isinstance(mapping, dict):
                            entries.append(
                                {
                                    "symbol": mapping.get("symbol"),
                                    "asset_type": mapping.get("asset_type"),
                                    "exchange": mapping.get("exchange"),
                                }
                            )

        if not entries and "sid" in df.columns:
            unique_sids = df["sid"].unique().to_list()
            entries = [{"symbol": f"SID-{sid}"} for sid in unique_sids]

        # Deduplicate while preserving order
        seen = set()
        deduped_entries: list[dict[str, Any]] = []
        for entry in entries:
            symbol = entry.get("symbol")
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            deduped_entries.append(entry)

        return deduped_entries

    def _validate_ohlcv(self, df: pl.DataFrame) -> dict:
        """Validate OHLCV relationships (High >= Low, Close in range).

        Args:
            df: DataFrame with OHLCV data

        Returns:
            dict with 'violations' count and 'passed' boolean
        """
        violations = 0

        # Check if OHLCV columns exist
        if not all(col in df.columns for col in ["open", "high", "low", "close"]):
            return {"violations": 0, "passed": True}

        # Validate OHLCV relationships
        invalid_rows = df.filter(
            (pl.col("high") < pl.col("low"))
            | (pl.col("high") < pl.col("open"))
            | (pl.col("high") < pl.col("close"))
            | (pl.col("low") > pl.col("open"))
            | (pl.col("low") > pl.col("close"))
        )

        violations = len(invalid_rows)

        return {
            "violations": violations,
            "passed": violations == 0,
        }

    def _infer_asset_type(self, symbol: str) -> str:
        """Infer asset type from symbol naming conventions.

        Args:
            symbol: Symbol string (e.g., 'AAPL', 'BTC/USDT', 'ESH25')

        Returns:
            Asset type: 'equity', 'crypto', 'future', or 'unknown'
        """
        # Crypto patterns: BTC/USDT, ETH-USD
        if "/" in symbol or "-" in symbol:
            return "crypto"

        # Futures patterns: ESH25, NQM24 (contract code + month + year)
        if len(symbol) >= 4 and symbol[-2:].isdigit():
            return "future"

        # Default to equity
        return "equity"


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
