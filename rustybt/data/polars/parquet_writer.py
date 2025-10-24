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
        asset_type: str | None = None,
    ) -> None:
        """Populate unified metadata after successful write with smart gap detection.

        Args:
            df: DataFrame that was written
            bundle_name: Name of the bundle
            output_path: Path where data was written
            source_metadata: Metadata about the data source
            asset_type: Optional manual asset type override. If None, will be inferred.
        """
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

        # Auto-register bundle if not already registered
        # This makes Parquet bundles discoverable via bundles.load()
        if bundle_name not in bundles_registry:
            self._register_parquet_bundle(bundle_name, source_metadata)

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
