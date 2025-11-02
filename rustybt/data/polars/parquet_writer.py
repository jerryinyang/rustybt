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

from rustybt.data.bundles import bundles as bundles_registry
from rustybt.data.bundles import register as register_bundle
from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.polars.local_bundle_metadata import LocalBundleMetadata
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

        # Initialize local bundle metadata (always enabled)
        self.local_metadata = LocalBundleMetadata(self.bundle_path)

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
        asset_type: str | None = None,
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
            asset_type: Manual asset type override ('forex', 'crypto', 'equity', 'future').
                       If None, will be inferred from symbols.

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
            >>> writer.write_daily_bars(df, compression="zstd", source_metadata=metadata,
            ...                         bundle_name="test-bundle", asset_type="forex")
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
                asset_type=asset_type,
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
        bundle_name: str | None = None,
        source_metadata: dict[str, Any] | None = None,
        compression: CompressionType = "zstd",
        dataset_id: int | None = None,
    ) -> Path:
        """Write minute bars to Parquet with year/month/day partitioning.

        Uses finer-grained partitioning for minute data due to larger volume.
        Automatically populates BundleMetadata with provenance, quality, and symbols.

        Args:
            df: Polars DataFrame with minute-level OHLCV data
            bundle_name: Name of bundle (required for metadata registration)
            source_metadata: Source metadata dict with provenance info
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
            >>> writer.write_minute_bars(
            ...     df,
            ...     bundle_name="my-bundle",
            ...     source_metadata={"source_type": "ccxt"},
            ...     compression="zstd"
            ... )
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

        # === Auto-populate BundleMetadata (unified metadata system) ===
        # Register bundle metadata if bundle_name and source_metadata provided
        if bundle_name and source_metadata:
            self._register_minute_bundle_metadata(
                df=df_cast,
                bundle_name=bundle_name,
                source_metadata=source_metadata,
                output_path=output_path,
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

        Properly partitions data by grouping on partition columns and writing
        each group to its corresponding partition file with merge support.

        Args:
            df: DataFrame to write (must include partition columns)
            base_path: Base directory for partitioned data
            partition_cols: Columns to partition by
            compression: Compression algorithm

        Returns:
            Path to base directory (data is written to multiple partition subdirs)

        Example:
            >>> path = writer._write_partitioned_parquet(
            ...     df, Path("data/daily_bars"), ["year", "month"], "zstd"
            ... )
        """
        # Group data by partition columns
        partitions = df.group_by(partition_cols, maintain_order=True)

        partitions_written = 0
        last_output_file = None

        for partition_key, partition_df in partitions:
            # Extract partition values from the key tuple
            if len(partition_cols) == 1:
                partition_values = [partition_key]
            else:
                partition_values = list(partition_key)

            # Build partition path
            partition_path = base_path / "/".join(
                f"{col}={val}" for col, val in zip(partition_cols, partition_values, strict=False)
            )
            partition_path.mkdir(parents=True, exist_ok=True)

            output_file = partition_path / "data.parquet"
            temp_file = partition_path / f".data.parquet.tmp.{int(datetime.now().timestamp())}"

            try:
                # Remove partition columns from data before writing
                data_cols = [col for col in partition_df.columns if col not in partition_cols]
                partition_data = partition_df.select(data_cols)

                # Merge with existing data if file exists
                if output_file.exists():
                    existing_df = pl.read_parquet(output_file)

                    # Concatenate and deduplicate
                    merged_df = pl.concat([existing_df, partition_data])

                    # Remove duplicates based on time column + sid
                    if "date" in merged_df.columns:
                        merged_df = merged_df.unique(
                            subset=["date", "sid"], keep="last", maintain_order=False
                        )
                        merged_df = merged_df.sort(["date", "sid"])
                    elif "timestamp" in merged_df.columns:
                        merged_df = merged_df.unique(
                            subset=["timestamp", "sid"], keep="last", maintain_order=False
                        )
                        merged_df = merged_df.sort(["timestamp", "sid"])

                    logger.debug(
                        "parquet_partition_merged",
                        partition=str(partition_path.relative_to(base_path)),
                        existing_rows=len(existing_df),
                        new_rows=len(partition_data),
                        merged_rows=len(merged_df),
                    )

                    partition_data = merged_df

                # Write to temp file
                arrow_table = partition_data.to_arrow()
                pq.write_table(
                    arrow_table,
                    temp_file,
                    compression=compression,
                    use_dictionary=True,
                    write_statistics=True,
                )

                # Atomic rename
                temp_file.rename(output_file)
                partitions_written += 1
                last_output_file = output_file

                # Verbose logging disabled to reduce noise during ingestion
                # logger.debug(
                #     "parquet_partition_written",
                #     partition=str(partition_path.relative_to(base_path)),
                #     rows=len(partition_data),
                #     compression=compression,
                # )

            except Exception as e:
                # Clean up temp file on error
                if temp_file.exists():
                    temp_file.unlink()
                raise RuntimeError(f"Failed to write partition {partition_path}: {e}") from e

        logger.info(
            "parquet_partitioned_write_complete",
            base_path=str(base_path),
            partitions_written=partitions_written,
            total_rows=len(df),
        )

        # Return last written file for backward compatibility
        return last_output_file if last_output_file else base_path

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

    def _calculate_total_row_count(self, bundle_name: str) -> int:
        """Calculate total row count across all parquet files in bundle.

        Scans both daily_bars and minute_bars directories to get the cumulative
        total of all rows across all assets in the bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Total row count across all parquet files

        Example:
            >>> writer = ParquetWriter("data/bundles/test-bundle")
            >>> total_rows = writer._calculate_total_row_count("test-bundle")
            >>> print(f"Total rows: {total_rows}")
        """
        total_rows = 0

        # Check daily bars
        daily_dir = self.daily_bars_path
        if daily_dir.exists():
            parquet_files = list(daily_dir.glob("**/data.parquet"))
            if parquet_files:
                try:
                    scan = pl.scan_parquet([str(p) for p in parquet_files])
                    total_rows += scan.select(pl.len()).collect().item()
                except Exception as e:
                    logger.warning(
                        "failed_to_count_daily_rows",
                        bundle_name=bundle_name,
                        error=str(e),
                    )

        # Check minute bars
        minute_dir = self.minute_bars_path
        if minute_dir.exists():
            parquet_files = list(minute_dir.glob("**/data.parquet"))
            if parquet_files:
                try:
                    scan = pl.scan_parquet([str(p) for p in parquet_files])
                    total_rows += scan.select(pl.len()).collect().item()
                except Exception as e:
                    logger.warning(
                        "failed_to_count_minute_rows",
                        bundle_name=bundle_name,
                        error=str(e),
                    )

        return total_rows

    def _auto_populate_metadata(
        self,
        df: pl.DataFrame,
        bundle_name: str,
        output_path: Path,
        source_metadata: dict[str, Any],
        asset_type: str | None = None,
    ) -> None:
        """Populate unified metadata after successful write with smart gap detection.

        This method now populates BOTH:
        1. Local bundle metadata.db (for ParquetAssetFinder)
        2. Global bundle metadata (for bundle discovery)

        And tracks min/max date range across ALL writes instead of overwriting.

        Args:
            df: DataFrame that was written
            bundle_name: Name of the bundle
            output_path: Path where data was written
            source_metadata: Metadata about the data source
            asset_type: Optional manual asset type override. If None, will be inferred.
        """
        current_time = int(time.time())

        # Calculate total row count across ALL parquet files in bundle
        row_count = self._calculate_total_row_count(bundle_name)
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

        # === ASSET-AWARE GAP VALIDATION ===

        # Determine asset type (from parameter, source metadata, or inferred from symbols)
        detected_asset_type = asset_type  # Manual override takes precedence
        if not detected_asset_type:
            # Try to get from source_metadata
            detected_asset_type = source_metadata.get("asset_type")

        if not detected_asset_type:
            # Infer from symbols in the data
            symbols_in_data = []
            if "symbol" in df.columns:
                symbols_in_data = df.select("symbol").unique().to_series().to_list()
            elif source_metadata.get("symbols"):
                symbols_in_data = source_metadata["symbols"]

            # Infer from first symbol if available
            if symbols_in_data:
                detected_asset_type = self._infer_asset_type(symbols_in_data[0])
            else:
                detected_asset_type = "equity"  # Default fallback

        # Analyze gap pattern to distinguish regular vs irregular gaps
        gap_pattern_analysis = self._analyze_gap_pattern(
            missing_dates=missing_dates, all_dates=normalized_dates
        )

        # Validate OHLCV relationships
        validation_result = self._validate_ohlcv(df)
        violations = validation_result["violations"]

        # Asset-aware gap validation logic:
        # - Crypto (24/7 markets): FAIL if gaps exist AND they're irregular (data quality issue)
        # - Forex/Stocks: PASS if gaps are regular (weekends/holidays), FAIL if irregular
        # - Futures: Similar to stocks, allow regular gaps
        # - Unknown: Conservative - allow regular gaps only

        enforce_no_gaps = detected_asset_type == "crypto"
        allow_regular_gaps = detected_asset_type in ("forex", "equity", "future", "unknown")

        if enforce_no_gaps:
            # Crypto: gaps should never exist (24/7 trading)
            # But if they do exist and are irregular, it's a data quality issue
            gap_validation_passed = (
                missing_days_count == 0 or gap_pattern_analysis["is_regular_pattern"]
            )
        elif allow_regular_gaps:
            # Forex/Stocks: regular gaps (weekends/holidays) are OK
            # Only fail if gaps are irregular (data quality issue)
            gap_validation_passed = (
                missing_days_count == 0 or gap_pattern_analysis["is_regular_pattern"]
            )
        else:
            # Fallback: no gaps allowed
            gap_validation_passed = missing_days_count == 0

        validation_passed = validation_result["passed"] and gap_validation_passed

        # Log gap analysis for debugging
        if missing_days_count > 0:
            logger.info(
                "gap_validation_applied",
                asset_type=detected_asset_type,
                missing_days=missing_days_count,
                gap_pattern=gap_pattern_analysis["analysis_summary"],
                is_regular_pattern=gap_pattern_analysis["is_regular_pattern"],
                validation_passed=gap_validation_passed,
            )

        # Determine calendar based on asset type
        calendar_name = self._get_calendar_name(detected_asset_type)

        # === FIX: Track min/max date range across all writes ===
        # Get existing bundle metadata to preserve min start_date and max end_date
        existing_metadata = BundleMetadata.get(bundle_name)

        if existing_metadata:
            existing_start = existing_metadata.get("start_date")
            existing_end = existing_metadata.get("end_date")

            # Update to min/max of existing and new data
            if existing_start is not None and start_timestamp is not None:
                start_timestamp = min(existing_start, start_timestamp)
            elif existing_start is not None:
                start_timestamp = existing_start

            if existing_end is not None and end_timestamp is not None:
                end_timestamp = max(existing_end, end_timestamp)
            elif existing_end is not None:
                end_timestamp = existing_end

        update_payload: dict[str, Any] = {
            "source_type": source_metadata.get("source_type", "unknown"),
            "fetch_timestamp": current_time,
            "row_count": row_count,  # Total cumulative rows across all assets in bundle
            "start_date": start_timestamp,  # Now tracks min across all writes
            "end_date": end_timestamp,  # Now tracks max across all writes
            "missing_days_count": missing_days_count,
            "missing_days_list": missing_days_list,
            "outlier_count": 0,
            "ohlcv_violations": violations,
            "validation_passed": validation_passed,
            "validation_timestamp": current_time,
            "file_checksum": file_checksum,
            "file_size_bytes": file_size,
            "calendar": calendar_name,
        }

        for field in ("source_url", "api_version", "data_version", "timezone"):
            value = source_metadata.get(field)
            if value is not None:
                update_payload[field] = value

        BundleMetadata.update(bundle_name=bundle_name, **update_payload)

        # Auto-register bundle if not already registered
        # This makes Parquet bundles discoverable via bundles.load()
        if bundle_name not in bundles_registry:
            self._register_parquet_bundle(bundle_name, source_metadata)

        symbol_entries = self._resolve_symbol_entries(df, source_metadata)
        exchange_default = source_metadata.get("exchange")

        # Get symbol_map from source_metadata (contains symbol -> SID mapping)
        symbol_map = source_metadata.get("symbol_map", {})

        added_symbols = 0
        for entry in symbol_entries:
            symbol = entry.get("symbol")
            if not symbol:
                continue

            asset_type_final = entry.get("asset_type") or self._infer_asset_type(symbol)
            exchange = entry.get("exchange") or exchange_default

            # Get SID from symbol_map if available
            sid = symbol_map.get(symbol)

            # Add to GLOBAL metadata
            BundleMetadata.add_symbol(
                bundle_name=bundle_name,
                symbol=symbol,
                asset_type=asset_type_final,
                exchange=exchange,
                sid=sid,  # Pass explicit SID to ensure consistency
            )

            # === FIX: Add to LOCAL bundle metadata.db ===
            if sid is not None:
                self.local_metadata.add_symbol(
                    sid=sid,
                    symbol=symbol,
                    asset_type=asset_type_final,
                    exchange=exchange,
                )

                # === FIX: Track per-symbol date range in local metadata ===
                # Calculate date range for this specific symbol from the data
                if "date" in df.columns and "sid" in df.columns:
                    symbol_df = df.filter(pl.col("sid") == sid)
                    if len(symbol_df) > 0:
                        symbol_dates = symbol_df["date"].unique().sort()
                        if len(symbol_dates) > 0:
                            symbol_start = symbol_dates.min()
                            symbol_end = symbol_dates.max()
                            symbol_row_count = len(symbol_df)

                            # Convert to date objects if needed
                            if isinstance(symbol_start, datetime):
                                symbol_start = symbol_start.date()
                            if isinstance(symbol_end, datetime):
                                symbol_end = symbol_end.date()

                            # Get existing date range for this symbol (if re-ingesting)
                            existing_ranges = self.local_metadata.get_date_ranges()
                            if sid in existing_ranges:
                                existing_start = existing_ranges[sid]["start_date"]
                                existing_end = existing_ranges[sid]["end_date"]

                                # Track min/max across re-ingestions
                                if isinstance(existing_start, str):
                                    from datetime import datetime as dt

                                    existing_start = dt.fromisoformat(existing_start).date()
                                if isinstance(existing_end, str):
                                    from datetime import datetime as dt

                                    existing_end = dt.fromisoformat(existing_end).date()

                                symbol_start = min(symbol_start, existing_start)
                                symbol_end = max(symbol_end, existing_end)
                                symbol_row_count += existing_ranges[sid].get("row_count", 0)

                            self.local_metadata.update_date_range(
                                sid=sid,
                                start_date=symbol_start,
                                end_date=symbol_end,
                                row_count=symbol_row_count,
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
            local_metadata_updated=True,
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

    def _register_parquet_bundle(self, bundle_name: str, source_metadata: dict[str, Any]) -> None:
        """Register Parquet bundle in the bundle registry.

        This makes the bundle discoverable via bundles.load() for use in
        run_algorithm() and other Zipline APIs. Parquet bundles created by
        ingest-unified need to be registered to work with the traditional
        bundle loading system.

        Args:
            bundle_name: Name of the bundle to register
            source_metadata: Source metadata containing source_type, etc.

        Note:
            The registered ingest function raises an error directing users
            to use 'rustybt ingest-unified' instead of 'rustybt ingest'.
        """

        def parquet_bundle_ingest_disabled(*args, **kwargs):
            """Ingest function for Parquet bundles that raises informative error.

            Parquet bundles are created by 'rustybt ingest-unified' command
            and should not be re-ingested using the traditional 'rustybt ingest'.

            Raises:
                RuntimeError: Always raised with instructions to use ingest-unified
            """
            source_type = source_metadata.get("source_type", "unknown")
            raise RuntimeError(
                f"Bundle '{bundle_name}' is a Parquet bundle created by "
                f"'rustybt ingest-unified {source_type}'.\n\n"
                f"To update this bundle, use:\n"
                f"  rustybt ingest-unified {source_type} --bundle {bundle_name} [...options]\n\n"
                f"Traditional 'rustybt ingest' is not supported for Parquet bundles."
            )

        # Register with appropriate calendar based on asset type
        calendar_name = "NYSE"  # Default to NYSE
        if source_metadata.get("source_type") == "ccxt":
            calendar_name = "24/7"  # Crypto exchanges are 24/7

        register_bundle(
            name=bundle_name,
            f=parquet_bundle_ingest_disabled,
            calendar_name=calendar_name,
        )

        logger.info(
            "parquet_bundle_registered",
            bundle_name=bundle_name,
            calendar=calendar_name,
            source_type=source_metadata.get("source_type"),
        )

    def _analyze_gap_pattern(
        self,
        missing_dates: list[date],
        all_dates: list[date],
    ) -> dict[str, Any]:
        """Analyze gap pattern to distinguish regular (weekend/holiday) vs irregular (data quality) gaps.

        Uses statistical analysis to detect if gaps follow a predictable pattern:
        - Regular gaps: Consistent weekly pattern (weekends), predictable spacing
        - Irregular gaps: Random distribution, varying lengths, unpredictable

        Args:
            missing_dates: List of dates with missing data
            all_dates: List of all dates present in the data

        Returns:
            dict with:
                - is_regular_pattern: bool, True if gaps appear intentional (weekends/holidays)
                - weekend_gap_ratio: float, ratio of weekend gaps to total gaps
                - max_gap_days: int, longest consecutive gap
                - gap_length_variance: float, variance in gap lengths (high = irregular)
                - analysis_summary: str, human-readable interpretation

        Example:
            >>> # Forex data with weekend gaps
            >>> missing = [date(2023, 1, 7), date(2023, 1, 8), ...]  # Saturdays/Sundays
            >>> present = [date(2023, 1, 2), date(2023, 1, 3), ...]  # Weekdays
            >>> result = _analyze_gap_pattern(missing, present)
            >>> result['is_regular_pattern']  # True (weekend pattern)
            True
        """
        if not missing_dates or len(missing_dates) == 0:
            return {
                "is_regular_pattern": True,
                "weekend_gap_ratio": 0.0,
                "max_gap_days": 0,
                "gap_length_variance": 0.0,
                "analysis_summary": "No gaps detected",
            }

        if len(all_dates) < 7:
            # Not enough data to determine pattern
            return {
                "is_regular_pattern": False,
                "weekend_gap_ratio": 0.0,
                "max_gap_days": len(missing_dates),
                "gap_length_variance": 0.0,
                "analysis_summary": "Insufficient data to analyze gap pattern (< 7 days)",
            }

        # === WEEKEND DETECTION ===
        # Count how many missing dates are weekends (Saturday=5, Sunday=6)
        weekend_gaps = sum(1 for d in missing_dates if d.weekday() in (5, 6))
        weekend_gap_ratio = weekend_gaps / len(missing_dates) if missing_dates else 0.0

        # === GAP LENGTH ANALYSIS ===
        # Find consecutive gap sequences
        missing_set = set(missing_dates)
        all_dates_sorted = sorted(all_dates)

        if all_dates_sorted:
            full_range_start = all_dates_sorted[0]
            full_range_end = all_dates_sorted[-1]
        else:
            return {
                "is_regular_pattern": False,
                "weekend_gap_ratio": 0.0,
                "max_gap_days": 0,
                "gap_length_variance": 0.0,
                "analysis_summary": "No date data available",
            }

        # Build full date range and identify gap sequences
        gap_lengths: list[int] = []
        current_gap_length = 0
        max_gap_days = 0

        current_date = full_range_start
        while current_date <= full_range_end:
            if current_date in missing_set:
                current_gap_length += 1
                max_gap_days = max(max_gap_days, current_gap_length)
            else:
                if current_gap_length > 0:
                    gap_lengths.append(current_gap_length)
                    current_gap_length = 0
            current_date += timedelta(days=1)

        # Add final gap if range ends with gap
        if current_gap_length > 0:
            gap_lengths.append(current_gap_length)

        # === GAP VARIANCE ANALYSIS ===
        # Regular patterns (weekends) have low variance: mostly 2-day gaps
        # Irregular patterns (missing data) have high variance: random lengths
        gap_length_variance = 0.0
        if gap_lengths:
            mean_gap = sum(gap_lengths) / len(gap_lengths)
            gap_length_variance = sum((g - mean_gap) ** 2 for g in gap_lengths) / len(gap_lengths)

        # === PATTERN CLASSIFICATION ===
        # Criteria for regular pattern (likely weekends/holidays):
        # 1. High weekend ratio (>60% of gaps are weekends)
        # 2. Low gap variance (<2.0 indicates consistent 2-day weekend gaps)
        # 3. Max gap not excessive (<=4 days for long weekends)

        is_regular_weekend = (
            weekend_gap_ratio > 0.6 and gap_length_variance < 2.0 and max_gap_days <= 4
        )

        # Criteria for regular holiday pattern:
        # - Moderate weekend ratio (40-60%) + very low variance (<1.5)
        # - Suggests mix of weekends + occasional holidays
        is_regular_holiday = (
            0.4 <= weekend_gap_ratio <= 0.6 and gap_length_variance < 1.5 and max_gap_days <= 4
        )

        is_regular_pattern = is_regular_weekend or is_regular_holiday

        # === SUMMARY ===
        if is_regular_weekend:
            summary = (
                f"Regular weekend pattern detected ({weekend_gap_ratio:.1%} weekend gaps, "
                f"variance={gap_length_variance:.2f})"
            )
        elif is_regular_holiday:
            summary = (
                f"Regular weekend+holiday pattern detected ({weekend_gap_ratio:.1%} weekend gaps, "
                f"variance={gap_length_variance:.2f})"
            )
        else:
            summary = (
                f"Irregular gap pattern detected ({weekend_gap_ratio:.1%} weekend gaps, "
                f"variance={gap_length_variance:.2f}, max_gap={max_gap_days} days) - "
                f"possible data quality issue"
            )

        logger.debug(
            "gap_pattern_analyzed",
            total_gaps=len(missing_dates),
            weekend_gaps=weekend_gaps,
            weekend_ratio=weekend_gap_ratio,
            max_gap_days=max_gap_days,
            gap_variance=gap_length_variance,
            is_regular=is_regular_pattern,
        )

        return {
            "is_regular_pattern": is_regular_pattern,
            "weekend_gap_ratio": weekend_gap_ratio,
            "max_gap_days": max_gap_days,
            "gap_length_variance": gap_length_variance,
            "analysis_summary": summary,
        }

    def _infer_asset_type(self, symbol: str) -> str:
        """Infer asset type from symbol naming conventions with robust pattern matching.

        Handles multiple formats for forex and crypto symbols from different providers.

        Args:
            symbol: Symbol string (e.g., 'AAPL', 'BTC/USDT', 'EURUSD=X', 'ESH25')

        Returns:
            Asset type: 'forex', 'crypto', 'equity', 'future', or 'unknown'

        Examples:
            >>> _infer_asset_type('EURUSD=X')  # yfinance forex
            'forex'
            >>> _infer_asset_type('EUR/USD')   # Standard forex
            'forex'
            >>> _infer_asset_type('EURUSD')    # Broker-style forex
            'forex'
            >>> _infer_asset_type('BTC/USDT')  # Crypto with slash
            'crypto'
            >>> _infer_asset_type('BTCUSDT')   # Binance-style crypto
            'crypto'
            >>> _infer_asset_type('ESH25')     # Future contract
            'future'
            >>> _infer_asset_type('AAPL')      # Stock
            'equity'
        """
        symbol_upper = symbol.upper().strip()

        # === FOREX DETECTION ===

        # Pattern 1: Yahoo Finance forex suffix (EURUSD=X, GBPJPY=X)
        if symbol_upper.endswith("=X"):
            return "forex"

        # Pattern 2: Forex with separator (EUR/USD, GBP-JPY)
        if "/" in symbol_upper or "-" in symbol_upper:
            # Check if it looks like crypto first (to avoid false positives)
            parts = symbol_upper.replace("/", "-").split("-")
            if len(parts) == 2:
                base, quote = parts
                # Common crypto base currencies
                crypto_bases = {
                    "BTC",
                    "ETH",
                    "USDT",
                    "USDC",
                    "BNB",
                    "SOL",
                    "ADA",
                    "XRP",
                    "DOT",
                    "DOGE",
                    "AVAX",
                    "MATIC",
                    "LINK",
                    "UNI",
                    "ATOM",
                    "LTC",
                    "BCH",
                    "XLM",
                    "ALGO",
                    "VET",
                    "FIL",
                    "AAVE",
                    "EOS",
                }
                # Common crypto quote currencies
                crypto_quotes = {"USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB", "EUR"}

                # If base is known crypto symbol, it's crypto
                if base in crypto_bases:
                    return "crypto"

                # If both parts are 3-letter currency codes, likely forex
                if len(base) == 3 and len(quote) == 3:
                    # Common fiat currency codes
                    fiat_codes = {
                        "USD",
                        "EUR",
                        "GBP",
                        "JPY",
                        "CHF",
                        "AUD",
                        "CAD",
                        "NZD",
                        "SEK",
                        "NOK",
                        "DKK",
                        "SGD",
                        "HKD",
                        "KRW",
                        "CNY",
                        "INR",
                        "MXN",
                        "ZAR",
                        "TRY",
                        "BRL",
                        "RUB",
                        "PLN",
                        "THB",
                        "IDR",
                    }
                    if base in fiat_codes or quote in fiat_codes:
                        return "forex"

                # If quote is common crypto quote, it's crypto
                if quote in crypto_quotes:
                    return "crypto"

        # Pattern 3: 6-character forex pair (EURUSD, GBPJPY, USDJPY)
        if len(symbol_upper) == 6 and symbol_upper.isalpha():
            # Split into potential currency codes
            base_curr = symbol_upper[:3]
            quote_curr = symbol_upper[3:]

            # Major and minor currency codes
            currency_codes = {
                "USD",
                "EUR",
                "GBP",
                "JPY",
                "CHF",
                "AUD",
                "CAD",
                "NZD",
                "SEK",
                "NOK",
                "DKK",
                "SGD",
                "HKD",
                "KRW",
                "CNY",
                "INR",
                "MXN",
                "ZAR",
                "TRY",
                "BRL",
                "RUB",
                "PLN",
                "THB",
                "IDR",
                "CZK",
                "HUF",
                "ILS",
                "CLP",
                "PHP",
                "AED",
                "SAR",
                "MYR",
            }

            # Both parts are currency codes = forex
            if base_curr in currency_codes and quote_curr in currency_codes:
                return "forex"

        # === CRYPTO DETECTION ===

        # Pattern 1: Known crypto suffixes (BTCUSDT, ETHUSDC, SOLUSD)
        crypto_quote_suffixes = ["USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB", "EUR", "TUSD"]
        for suffix in crypto_quote_suffixes:
            if symbol_upper.endswith(suffix) and len(symbol_upper) > len(suffix):
                base = symbol_upper[: -len(suffix)]
                # Base should be 2-5 chars for crypto
                if 2 <= len(base) <= 5:
                    return "crypto"

        # Pattern 2: Known crypto base prefixes (BTCUSD, ETHUSD, SOLUSD)
        crypto_bases = {
            "BTC",
            "ETH",
            "SOL",
            "ADA",
            "XRP",
            "DOT",
            "DOGE",
            "AVAX",
            "MATIC",
            "LINK",
            "UNI",
            "ATOM",
            "LTC",
            "BCH",
            "XLM",
            "ALGO",
            "VET",
            "FIL",
            "AAVE",
            "EOS",
            "XTZ",
            "EGLD",
            "THETA",
            "CAKE",
        }
        for base in crypto_bases:
            if symbol_upper.startswith(base):
                return "crypto"

        # === FUTURES DETECTION ===

        # Pattern: Contract code + month code + year (ESH25, NQM24, GCZ23)
        # Typical format: 1-3 letter code + 1 letter month + 2 digit year
        if len(symbol_upper) >= 4:
            # Check if last 2 chars are digits (year)
            if symbol_upper[-2:].isdigit():
                # Check if char before year is alpha (month code)
                if len(symbol_upper) >= 3 and symbol_upper[-3].isalpha():
                    # Check if remaining prefix is 1-3 alphas (product code)
                    prefix = symbol_upper[:-3]
                    if 1 <= len(prefix) <= 3 and prefix.isalpha():
                        return "future"

        # === DEFAULT ===
        # If no patterns matched, default to equity
        return "equity"

    def _get_calendar_name(self, asset_type: str | None) -> str:
        """Get appropriate trading calendar name for asset type.

        Maps asset types to their corresponding exchange_calendars calendar names.

        Args:
            asset_type: Asset type ('forex', 'crypto', 'equity', 'future', 'unknown', or None)

        Returns:
            Calendar name for use with exchange_calendars.get_calendar():
            - 'forex' → '24/5' (24 hours, 5 days/week)
            - 'crypto' → '24/7' (continuous trading)
            - 'equity', 'future', 'unknown', None → 'XNYS' (default)

        Example:
            >>> writer = ParquetWriter("/path/to/bundle")
            >>> writer._get_calendar_name("forex")
            '24/5'
            >>> writer._get_calendar_name("crypto")
            '24/7'
            >>> writer._get_calendar_name("equity")
            'XNYS'
        """
        if asset_type == "forex":
            return "24/5"
        elif asset_type == "crypto":
            return "24/7"
        else:
            # Default for equity, future, unknown, or None
            return "XNYS"

    def _register_minute_bundle_metadata(
        self,
        df: pl.DataFrame,
        bundle_name: str,
        source_metadata: dict[str, Any],
        output_path: Path,
    ) -> None:
        """Register minute bundle metadata in unified BundleMetadata system.

        Similar to write_daily_bars() metadata registration but for minute data.

        Args:
            df: Minute bars DataFrame (with timestamp column)
            bundle_name: Name of the bundle
            source_metadata: Source metadata dict with provenance info
            output_path: Path to written Parquet files
        """
        import hashlib
        import json
        import time
        from decimal import Decimal

        current_time = int(time.time())

        # === Calculate quality metrics ===
        # Total row count across all assets
        row_count = len(df)

        # Extract timestamp range (for minute data, use "timestamp" column)
        if "timestamp" in df.columns and len(df) > 0:
            timestamps = df["timestamp"].unique().sort()
            start_timestamp = int(timestamps.min().timestamp()) if len(timestamps) > 0 else None
            end_timestamp = int(timestamps.max().timestamp()) if len(timestamps) > 0 else None
        else:
            start_timestamp = None
            end_timestamp = None

        # OHLCV violations check
        violations = 0
        if all(col in df.columns for col in ["high", "low", "open", "close"]):
            invalid_rows = df.filter(
                (pl.col("high") < pl.col("low"))
                | (pl.col("high") < pl.col("open"))
                | (pl.col("high") < pl.col("close"))
                | (pl.col("low") > pl.col("open"))
                | (pl.col("low") > pl.col("close"))
            )
            violations = len(invalid_rows)

        validation_passed = violations == 0

        # Calculate file checksum and size
        if output_path.exists() and output_path.is_file():
            file_size = output_path.stat().st_size
            with open(output_path, "rb") as f:
                file_checksum = hashlib.sha256(f.read()).hexdigest()
        elif output_path.exists() and output_path.is_dir():
            # For partitioned writes, calculate total size of all parquet files
            file_size = sum(p.stat().st_size for p in output_path.rglob("*.parquet") if p.is_file())
            # For checksum, use a representative file or skip
            parquet_files = list(output_path.rglob("data.parquet"))
            if parquet_files:
                with open(parquet_files[0], "rb") as f:
                    file_checksum = hashlib.sha256(f.read()).hexdigest()
            else:
                file_checksum = "multi-file-bundle"
        else:
            file_size = 0
            file_checksum = "unknown"

        # Infer calendar from asset type
        symbols = source_metadata.get("symbols", [])
        asset_type = None
        if symbols:
            asset_type = self._infer_asset_type(symbols[0])
        calendar_name = self._get_calendar_name(asset_type)

        # Missing days calculation not applicable to minute data
        missing_days_count = 0
        missing_days_list: list[str] = []

        # === Track min/max date range across all writes ===
        existing_metadata = BundleMetadata.get(bundle_name)

        if existing_metadata:
            existing_start = existing_metadata.get("start_date")
            existing_end = existing_metadata.get("end_date")

            # Update to min/max of existing and new data
            if existing_start is not None and start_timestamp is not None:
                start_timestamp = min(existing_start, start_timestamp)
            elif existing_start is not None:
                start_timestamp = existing_start

            if existing_end is not None and end_timestamp is not None:
                end_timestamp = max(existing_end, end_timestamp)
            elif existing_end is not None:
                end_timestamp = existing_end

        update_payload: dict[str, Any] = {
            "source_type": source_metadata.get("source_type", "unknown"),
            "fetch_timestamp": current_time,
            "row_count": row_count,
            "start_date": start_timestamp,
            "end_date": end_timestamp,
            "missing_days_count": missing_days_count,
            "missing_days_list": json.dumps(missing_days_list),
            "outlier_count": 0,
            "ohlcv_violations": violations,
            "validation_passed": validation_passed,
            "validation_timestamp": current_time,
            "file_checksum": file_checksum,
            "file_size_bytes": file_size,
            "calendar": calendar_name,
        }

        for field in ("source_url", "api_version", "data_version", "timezone"):
            value = source_metadata.get(field)
            if value is not None:
                update_payload[field] = value

        BundleMetadata.update(bundle_name=bundle_name, **update_payload)

        # Auto-register bundle if not already registered
        if bundle_name not in bundles_registry:
            self._register_parquet_bundle(bundle_name, source_metadata)

        # Register symbols
        symbol_entries = self._resolve_symbol_entries(df, source_metadata)
        exchange_default = source_metadata.get("exchange")

        # Get symbol_map from source_metadata
        symbol_map = source_metadata.get("symbol_map", {})

        for entry in symbol_entries:
            symbol = entry.get("symbol")
            if not symbol:
                continue

            asset_type_final = entry.get("asset_type") or self._infer_asset_type(symbol)
            exchange = entry.get("exchange") or exchange_default

            # Get SID from symbol_map if available
            sid = symbol_map.get(symbol)

            # Add to GLOBAL metadata
            BundleMetadata.add_symbol(
                bundle_name=bundle_name,
                symbol=symbol,
                asset_type=asset_type_final,
                exchange=exchange,
                sid=sid,
            )

            # Add to LOCAL bundle metadata
            if sid is not None:
                self.local_metadata.add_symbol(
                    sid=sid,
                    symbol=symbol,
                    asset_type=asset_type_final,
                    exchange=exchange,
                )

                # Track per-symbol date range in local metadata
                if "timestamp" in df.columns and "sid" in df.columns:
                    symbol_df = df.filter(pl.col("sid") == sid)
                    if len(symbol_df) > 0:
                        symbol_timestamps = symbol_df["timestamp"].unique().sort()
                        if len(symbol_timestamps) > 0:
                            symbol_start = symbol_timestamps.min()
                            symbol_end = symbol_timestamps.max()
                            symbol_row_count = len(symbol_df)

                            # Convert timestamps to dates
                            if hasattr(symbol_start, "date"):
                                symbol_start_date = symbol_start.date()
                            else:
                                symbol_start_date = symbol_start

                            if hasattr(symbol_end, "date"):
                                symbol_end_date = symbol_end.date()
                            else:
                                symbol_end_date = symbol_end

                            # Update local metadata with per-symbol range
                            self.local_metadata.update_date_range(
                                sid=sid,
                                start_date=symbol_start_date,
                                end_date=symbol_end_date,
                                row_count=symbol_row_count,
                            )

        logger.info(
            "minute_bundle_metadata_registered",
            bundle_name=bundle_name,
            row_count=row_count,
            symbols=len(symbol_entries),
            validation_passed=validation_passed,
        )


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
