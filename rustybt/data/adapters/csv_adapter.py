"""CSV data adapter for importing custom data files.

This module provides flexible CSV import capabilities with schema mapping,
delimiter detection, date parsing, and missing data handling.
"""

import asyncio
import csv
import hashlib
from dataclasses import dataclass
from decimal import getcontext
from pathlib import Path

import pandas as pd
import polars as pl
import pytz
import structlog

from rustybt.data.adapters.base import (
    BaseDataAdapter,
    InvalidDataError,
    validate_ohlcv_relationships,
)
from rustybt.data.adapters.utils import (
    build_symbol_sid_map,
    normalize_symbols,
    prepare_ohlcv_frame,
)
from rustybt.data.polars.parquet_writer import ParquetWriter
from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.utils.paths import data_path, ensure_directory

# Set decimal precision for financial calculations
getcontext().prec = 28

logger = structlog.get_logger()


# ============================================================================
# Configuration Dataclasses
# ============================================================================


@dataclass
class SchemaMapping:
    """Configuration for CSV schema mapping.

    Maps CSV column names to standard OHLCV fields. Supports case-insensitive
    matching for flexible column name handling.

    Attributes:
        date_column: Name of date/timestamp column in CSV
        open_column: Name of open price column
        high_column: Name of high price column
        low_column: Name of low price column
        close_column: Name of close price column
        volume_column: Name of volume column
        symbol_column: Name of symbol/ticker column (optional)
    """

    date_column: str = "timestamp"
    open_column: str = "open"
    high_column: str = "high"
    low_column: str = "low"
    close_column: str = "close"
    volume_column: str = "volume"
    symbol_column: str | None = None


@dataclass
class CSVConfig:
    """Configuration for CSV parsing.

    Provides comprehensive configuration for CSV import including schema mapping,
    delimiter detection, date parsing, and missing data handling.

    Attributes:
        file_path: Path to CSV file
        schema_mapping: Schema mapping configuration
        delimiter: CSV delimiter (auto-detect if None)
        has_header: Whether CSV has header row
        date_format: Date parsing format string (auto-detect if None)
        timezone: Timezone of timestamps (converts to UTC)
        missing_data_strategy: Strategy for handling missing data ('skip', 'interpolate', 'fail')
    """

    file_path: str
    schema_mapping: SchemaMapping
    delimiter: str | None = None  # Auto-detect if None
    has_header: bool = True
    date_format: str | None = None  # Auto-detect if None
    timezone: str = "UTC"
    missing_data_strategy: str = "fail"  # 'skip', 'interpolate', 'fail'


# ============================================================================
# CSV Data Adapter
# ============================================================================


class CSVAdapter(BaseDataAdapter, DataSource):
    """CSV adapter for importing custom data files.

    Provides flexible CSV import with:
    - Schema mapping (custom column names)
    - Delimiter detection (comma, tab, semicolon, pipe)
    - Date parsing (ISO8601, US format, European format, epoch)
    - Timezone handling (convert to UTC)
    - Missing data handling (skip, interpolate, fail)
    - Decimal conversion for financial precision

    Implements both BaseDataAdapter and DataSource interfaces for backwards
    compatibility and unified data source access.

    Example:
        >>> config = CSVConfig(
        ...     file_path="data/ohlcv.csv",
        ...     schema_mapping=SchemaMapping(
        ...         date_column="Date",
        ...         open_column="Open",
        ...         high_column="High",
        ...         low_column="Low",
        ...         close_column="Close",
        ...         volume_column="Volume"
        ...     ),
        ...     delimiter=",",
        ...     date_format="%Y-%m-%d",
        ...     timezone="UTC"
        ... )
        >>> adapter = CSVAdapter(config)
        >>> df = await adapter.fetch(
        ...     symbols=[],
        ...     start_date=pd.Timestamp('2023-01-01'),
        ...     end_date=pd.Timestamp('2023-12-31'),
        ...     resolution='1d'
        ... )
    """

    def __init__(self, config: CSVConfig) -> None:
        """Initialize CSV adapter.

        Args:
            config: CSV configuration with schema mapping and parsing options
        """
        super().__init__(
            name="CSVAdapter",
            rate_limit_per_second=1000,  # No external API, just file I/O
        )

        self.config = config
        self.timezone = pytz.timezone(config.timezone)

        logger.info(
            "csv_adapter_initialized",
            file_path=config.file_path,
            delimiter=config.delimiter or "auto-detect",
            timezone=config.timezone,
            missing_data_strategy=config.missing_data_strategy,
        )

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Read OHLCV data from CSV file.

        Args:
            symbols: List of symbols to filter (if symbol column exists)
            start_date: Start date for data range
            end_date: End date for data range
            resolution: Not used for CSV (data resolution determined by file)

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            InvalidDataError: If CSV format is invalid or missing required columns
        """
        # Detect delimiter if not specified
        delimiter = self.config.delimiter
        if delimiter is None:
            delimiter = self._detect_delimiter()

        # Read CSV with Polars
        try:
            df = pl.read_csv(
                self.config.file_path,
                separator=delimiter,
                has_header=self.config.has_header,
                try_parse_dates=False,  # We'll handle date parsing manually
            )
        except Exception as e:
            raise InvalidDataError(f"Failed to read CSV: {e}") from e

        logger.info(
            "csv_read_initial",
            file=self.config.file_path,
            rows=len(df),
            columns=df.columns,
            delimiter=delimiter,
        )

        # Apply schema mapping
        df = self._apply_schema_mapping(df)

        # Parse dates
        df = self._parse_dates(df)

        # Convert to UTC
        df = self._convert_timezone(df)

        # Filter by date range - ensure timezone-aware comparison
        # Convert pandas Timestamp to timezone-aware if needed
        if start_date.tz is None:
            start_date = start_date.tz_localize("UTC")
        if end_date.tz is None:
            end_date = end_date.tz_localize("UTC")

        df = df.filter((pl.col("timestamp") >= start_date) & (pl.col("timestamp") <= end_date))

        # Filter by symbols if symbol column exists
        if self.config.schema_mapping.symbol_column and symbols:
            df = df.filter(pl.col("symbol").is_in(symbols))

        # Handle missing data
        df = self._handle_missing_data(df)

        # Convert to Decimal
        df = self._convert_to_decimal(df)

        # Standardize and validate
        df = self.standardize(df)
        self.validate(df)

        self._log_fetch_success(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            resolution=resolution,
            row_count=len(df),
        )

        return df

    def _detect_delimiter(self) -> str:
        """Auto-detect CSV delimiter using csv.Sniffer.

        Attempts to detect delimiter from first 1KB of file. Falls back
        to comma if detection fails.

        Returns:
            Detected delimiter character
        """
        try:
            with open(self.config.file_path, encoding="utf-8") as f:
                sample = f.read(1024)
                sniffer = csv.Sniffer()
                try:
                    delimiter = sniffer.sniff(sample).delimiter
                    logger.info(
                        "delimiter_detected",
                        delimiter=repr(delimiter),
                        file=self.config.file_path,
                    )
                    return delimiter
                except csv.Error:
                    # Default to comma if detection fails
                    logger.warning(
                        "delimiter_detection_failed",
                        using_default=",",
                        file=self.config.file_path,
                    )
                    return ","
        except OSError as e:
            logger.warning(
                "delimiter_detection_error",
                error=str(e),
                using_default=",",
                file=self.config.file_path,
            )
            return ","

    def _apply_schema_mapping(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply schema mapping to rename columns.

        Maps CSV column names to standard OHLCV field names. Supports
        case-insensitive matching for flexible column name handling.

        Args:
            df: DataFrame with original CSV column names

        Returns:
            DataFrame with standardized column names

        Raises:
            InvalidDataError: If required columns are missing
        """
        mapping = self.config.schema_mapping

        # Create column rename mapping
        rename_mapping = {
            mapping.date_column: "timestamp",
            mapping.open_column: "open",
            mapping.high_column: "high",
            mapping.low_column: "low",
            mapping.close_column: "close",
            mapping.volume_column: "volume",
        }

        if mapping.symbol_column:
            rename_mapping[mapping.symbol_column] = "symbol"

        # Handle case-insensitive matching
        actual_columns = {col.lower(): col for col in df.columns}
        final_mapping = {}

        for csv_col, std_col in rename_mapping.items():
            # Try exact match first
            if csv_col in df.columns:
                final_mapping[csv_col] = std_col
            # Try case-insensitive match
            elif csv_col.lower() in actual_columns:
                final_mapping[actual_columns[csv_col.lower()]] = std_col

        # Validate required columns exist
        required_std_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        mapped_std_cols = set(final_mapping.values())

        missing_cols = required_std_cols - mapped_std_cols
        if missing_cols:
            raise InvalidDataError(
                f"Missing required columns in CSV: {missing_cols}. Available columns: {df.columns}"
            )

        # Rename columns
        df = df.rename(final_mapping)

        # Add symbol column if not present
        if "symbol" not in df.columns:
            df = df.with_columns([pl.lit("CSV_DATA").alias("symbol")])

        logger.info(
            "schema_mapping_applied",
            original_columns=list(final_mapping.keys()),
            mapped_columns=list(final_mapping.values()),
            has_symbol_column="symbol" in df.columns,
        )

        return df

    def _parse_dates(self, df: pl.DataFrame) -> pl.DataFrame:
        """Parse date column to timestamp.

        Supports multiple date formats:
        - ISO8601 (YYYY-MM-DD, YYYY-MM-DD HH:MM:SS)
        - Unix epoch (seconds or milliseconds)
        - Custom format via date_format parameter

        Args:
            df: DataFrame with unparsed timestamp column

        Returns:
            DataFrame with parsed timestamp column

        Raises:
            InvalidDataError: If date parsing fails
        """
        date_col = df["timestamp"]

        # Check if already datetime
        if date_col.dtype in (pl.Datetime, pl.Date):
            result_df = df.with_columns(
                [pl.col("timestamp").cast(pl.Datetime("us")).alias("timestamp")]
            )
            logger.info(
                "date_parsing_skipped", reason="already_datetime", dtype=str(date_col.dtype)
            )
            return result_df

        # Try to parse as string
        if self.config.date_format:
            # Use specified format
            try:
                df = df.with_columns(
                    [
                        pl.col("timestamp")
                        .str.strptime(pl.Datetime("us"), format=self.config.date_format)
                        .alias("timestamp")
                    ]
                )
                logger.info(
                    "date_parsing_succeeded", format=self.config.date_format, method="explicit"
                )
                return df
            except Exception as e:
                raise InvalidDataError(
                    f"Failed to parse dates with format '{self.config.date_format}': {e}"
                ) from e
        else:
            # Auto-detect format - try common formats
            formats_to_try = [
                "%Y-%m-%d",  # ISO8601 date
                "%Y-%m-%d %H:%M:%S",  # ISO8601 datetime
                "%m/%d/%Y",  # US format
                "%d/%m/%Y",  # European format
            ]

            for fmt in formats_to_try:
                try:
                    result_df = df.with_columns(
                        [
                            pl.col("timestamp")
                            .str.strptime(pl.Datetime("us"), format=fmt)
                            .alias("timestamp")
                        ]
                    )
                    logger.info("date_parsing_succeeded", format=fmt, method="auto_detect")
                    return result_df
                except Exception:  # noqa: BLE001, S112
                    # Continue trying other formats - polars can raise various exceptions
                    continue

            # Try epoch timestamp (seconds)
            try:
                result_df = df.with_columns(
                    [
                        pl.from_epoch(pl.col("timestamp").cast(pl.Int64), time_unit="s").alias(
                            "timestamp"
                        )
                    ]
                )
                logger.info("date_parsing_succeeded", format="epoch_seconds", method="auto_detect")
                return result_df
            except Exception:  # noqa: BLE001, S110
                # Not epoch seconds, try milliseconds - polars can raise various exceptions
                pass

            # Try epoch timestamp (milliseconds)
            try:
                result_df = df.with_columns(
                    [
                        pl.from_epoch(pl.col("timestamp").cast(pl.Int64), time_unit="ms").alias(
                            "timestamp"
                        )
                    ]
                )
                logger.info(
                    "date_parsing_succeeded", format="epoch_milliseconds", method="auto_detect"
                )
                return result_df
            except Exception:  # noqa: BLE001, S110
                # Not epoch milliseconds either - polars can raise various exceptions
                pass

            # All formats failed
            raise InvalidDataError(
                f"Failed to auto-detect date format. Tried formats: {formats_to_try}, "
                f"epoch seconds/ms. Please specify date_format parameter explicitly."
            )

    def _convert_timezone(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert timestamps to UTC.

        If source timezone is not UTC, localizes timestamps to source timezone
        and converts to UTC.

        Args:
            df: DataFrame with timestamps in source timezone

        Returns:
            DataFrame with UTC timestamps
        """
        if self.config.timezone != "UTC":
            try:
                df = df.with_columns(
                    [
                        pl.col("timestamp")
                        .dt.replace_time_zone(self.config.timezone)
                        .dt.convert_time_zone("UTC")
                        .alias("timestamp")
                    ]
                )
                logger.info(
                    "timezone_conversion_applied",
                    from_timezone=self.config.timezone,
                    to_timezone="UTC",
                )
            except (ValueError, TypeError) as e:
                logger.warning(
                    "timezone_conversion_failed",
                    error=str(e),
                    timezone=self.config.timezone,
                    assuming_utc=True,
                )
                # If conversion fails, assume timestamps are already UTC
                df = df.with_columns(
                    [pl.col("timestamp").dt.replace_time_zone("UTC").alias("timestamp")]
                )
        else:
            # Already UTC, just ensure timezone is set
            df = df.with_columns(
                [pl.col("timestamp").dt.replace_time_zone("UTC").alias("timestamp")]
            )

        return df

    def _handle_missing_data(self, df: pl.DataFrame) -> pl.DataFrame:
        """Handle missing data according to strategy.

        Strategies:
        - 'fail': Raise error if any missing values detected
        - 'skip': Remove rows with any missing values
        - 'interpolate': Forward-fill missing values in OHLCV columns

        Args:
            df: DataFrame potentially containing missing values

        Returns:
            DataFrame with missing data handled

        Raises:
            InvalidDataError: If strategy is 'fail' and missing values exist
        """
        strategy = self.config.missing_data_strategy

        # Count missing values
        null_counts = df.null_count()
        total_nulls = null_counts.select(pl.all().sum()).to_numpy().sum()

        if total_nulls > 0:
            logger.warning(
                "missing_data_detected",
                total_nulls=int(total_nulls),
                strategy=strategy,
                file=self.config.file_path,
            )

            if strategy == "fail":
                raise InvalidDataError(
                    f"Missing values detected in CSV: {null_counts.to_dicts()[0]}. "
                    f"Set missing_data_strategy='skip' or 'interpolate' to handle."
                )

            elif strategy == "skip":
                # Remove rows with any missing values
                original_len = len(df)
                df = df.drop_nulls()
                logger.info(
                    "missing_data_skipped",
                    rows_removed=original_len - len(df),
                    rows_remaining=len(df),
                )

            elif strategy == "interpolate":
                # Forward-fill for OHLCV columns
                price_cols = ["open", "high", "low", "close", "volume"]
                for col in price_cols:
                    if col in df.columns:
                        df = df.with_columns([pl.col(col).fill_null(strategy="forward").alias(col)])

                # Check if any nulls remain (first row may still be null)
                remaining_nulls = df.null_count().select(pl.all().sum()).to_numpy().sum()
                if remaining_nulls > 0:
                    logger.warning(
                        "interpolation_incomplete",
                        remaining_nulls=int(remaining_nulls),
                        note="First row may have nulls that cannot be forward-filled",
                    )
                    # Drop rows that still have nulls
                    df = df.drop_nulls()

                logger.info("missing_data_interpolated", rows_remaining=len(df))

        return df

    def _convert_to_decimal(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert price columns to Decimal.

        Converts OHLCV numeric columns to Decimal type with 8 decimal places
        for financial-grade precision.

        Args:
            df: DataFrame with numeric price columns

        Returns:
            DataFrame with Decimal price columns
        """
        price_cols = ["open", "high", "low", "close", "volume"]

        for col in price_cols:
            if col in df.columns:
                # Convert to string first, then to Decimal to preserve precision
                df = df.with_columns([pl.col(col).cast(pl.Utf8).str.to_decimal(scale=8).alias(col)])

        logger.info("decimal_conversion_applied", columns=price_cols)

        return df

    def validate(self, df: pl.DataFrame) -> bool:
        """Validate CSV data.

        Uses base class validation for OHLCV relationships and data quality.

        Args:
            df: DataFrame to validate

        Returns:
            True if validation passes

        Raises:
            ValidationError: If data validation fails
        """
        return validate_ohlcv_relationships(df)

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Standardize data format.

        Data is already standardized in fetch() method through schema mapping,
        date parsing, and Decimal conversion.

        Args:
            df: DataFrame to standardize

        Returns:
            Standardized DataFrame (no changes needed)
        """
        return df

    def _compute_file_checksum(self) -> str:
        """Compute SHA256 checksum of CSV file.

        Returns:
            Hexadecimal checksum string
        """
        sha256_hash = hashlib.sha256()
        with open(self.config.file_path, "rb") as f:
            # Read file in chunks for memory efficiency
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # ========================================================================
    # DataSource Interface Implementation
    # ========================================================================

    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs,
    ) -> None:
        """Ingest CSV data into bundle (Parquet + metadata).

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to filter (if symbol column exists)
            start: Start timestamp for data range
            end: End timestamp for data range
            frequency: Time resolution (not used for CSV, data resolution from file)
            **kwargs: Additional parameters (ignored for CSV)

        Raises:
            InvalidDataError: If CSV format is invalid
            ValidationError: If data validation fails
            IOError: If bundle write fails
        """
        logger.info(
            "csv_ingest_start",
            bundle=bundle_name,
            file_path=self.config.file_path,
            symbols=symbols[:5] if symbols and len(symbols) > 5 else symbols,
            symbol_count=len(symbols) if symbols else "all",
            start=start,
            end=end,
            frequency=frequency,
        )

        df = asyncio.run(self.fetch(symbols, start, end, frequency))
        if df.is_empty():
            logger.warning(
                "csv_no_data",
                bundle=bundle_name,
                file_path=self.config.file_path,
                frequency=frequency,
            )
            return

        if symbols:
            symbol_list = normalize_symbols(symbols)
        else:
            symbol_list = normalize_symbols(df["symbol"].unique().to_list())

        symbol_map = build_symbol_sid_map(symbol_list)

        effective_frequency = frequency or "1d"
        if effective_frequency in {"N/A", "na", "none"}:
            effective_frequency = "1d"

        df_prepared, frame_type = prepare_ohlcv_frame(df, symbol_map, effective_frequency)

        bundle_dir = Path(data_path(["bundles", bundle_name]))
        ensure_directory(str(bundle_dir))

        writer = ParquetWriter(str(bundle_dir))

        metadata = self.get_metadata()
        additional_info = metadata.additional_info or {}
        source_metadata = {
            "source_type": metadata.source_type,
            "source_url": metadata.source_url,
            "api_version": metadata.api_version,
            "symbols": list(symbol_map.keys()),
            "file_size_bytes": additional_info.get("file_size_bytes"),
            "timezone": additional_info.get("timezone") or self.config.timezone or "UTC",
        }

        writer.write_daily_bars(
            df_prepared,
            bundle_name=bundle_name,
            source_metadata=source_metadata,
        )

        logger.info(
            "csv_ingest_complete",
            bundle=bundle_name,
            rows=len(df_prepared),
            bundle_path=str(bundle_dir),
        )

    def get_metadata(self) -> DataSourceMetadata:
        """Get CSV source metadata.

        Returns:
            DataSourceMetadata with CSV file information
        """
        file_path = Path(self.config.file_path)
        file_size = file_path.stat().st_size if file_path.exists() else 0
        checksum = self._compute_file_checksum() if file_path.exists() else "unknown"

        return DataSourceMetadata(
            source_type="csv",
            source_url=str(file_path.absolute()),
            api_version="N/A",
            supports_live=False,
            rate_limit=None,  # No rate limits for local files
            auth_required=False,
            data_delay=None,  # Static data, no delay concept
            supported_frequencies=["N/A"],  # Resolution determined by file
            additional_info={
                "file_path": str(file_path.absolute()),
                "file_size_bytes": file_size,
                "checksum_sha256": checksum,
                "delimiter": self.config.delimiter or "auto-detect",
                "timezone": self.config.timezone,
                "missing_data_strategy": self.config.missing_data_strategy,
            },
        )

    def supports_live(self) -> bool:
        """CSV does not support live streaming.

        Returns:
            False (static file data only)
        """
        return False

    # Backwards compatibility - fetch_ohlcv is an alias to fetch
    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        """Legacy method name for backwards compatibility.

        Delegates to fetch() method.

        Args:
            symbols: List of symbols to filter
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution (not used for CSV)

        Returns:
            Polars DataFrame with OHLCV data
        """
        return await self.fetch(symbols, start, end, frequency)
