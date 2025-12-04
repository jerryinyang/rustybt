"""Databento data adapter for importing Databento market data packages.

Databento provides comprehensive market data packaged as ZIP files containing:
- metadata.json: Query parameters, schema, symbols, date range
- manifest.json: File listing with hashes
- symbology.csv/json: Symbol mappings
- *.ohlcv-*.csv.zst: zstd-compressed OHLCV data

This adapter supports:
- ZIP file or extracted folder input
- zstd decompression
- Multi-asset ingestion
- OHLCV data with 1m, 5m, 15m, 30m, 1h, 1d frequencies
- Symbol mapping and filtering
"""

import asyncio
import json
import shutil
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import pytz
import structlog
import zstandard as zstd

from rustybt.data.adapters.base import (
    BaseDataAdapter,
    InvalidDataError,
    NetworkError,
)
from rustybt.data.adapters.utils import (
    build_symbol_sid_map,
    normalize_symbols,
    prepare_ohlcv_frame,
    run_async,
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
class DatabentoFileInfo:
    """Information about a file in the Databento package."""

    filename: str
    size: int
    hash: str
    urls: dict[str, str]


@dataclass
class DatabentoManifest:
    """Databento manifest.json structure."""

    job_id: str
    files: list[DatabentoFileInfo]


@dataclass
class DatabentoMetadata:
    """Databento metadata.json structure."""

    version: int
    job_id: str
    dataset: str
    schema: str
    symbols: list[str]
    start: int  # Unix timestamp (nanoseconds)
    end: int  # Unix timestamp (nanoseconds)
    encoding: str
    compression: str
    stype_in: str
    stype_out: str
    split_duration: str | None = None  # "day", "month", or None for single file
    split_symbols: bool = False  # Whether symbols are split into separate files


@dataclass
class DatabentoConfig:
    """Configuration for Databento adapter.

    Attributes:
        data_path: Path to Databento ZIP file or extracted folder
        timezone: Timezone for timestamps (default: UTC)
        extra_columns: List of additional columns to preserve beyond standard OHLCV
                      (e.g., ['rtype', 'publisher_id', 'instrument_id']).
                      Use get_available_columns() to see what's available.
                      Default: None (only keep standard OHLCV columns)
        use_instrument_id: If True, use instrument_id for unique asset identification.
                          Creates composite symbols like "AAPL_13" to prevent collisions.
                          If False, use symbol only (legacy mode, may cause collisions).
                          Default: True (recommended)
        symbol_format: Format for composite symbols when use_instrument_id=True.
                      Options: "symbol_id" (e.g., "AAPL_13")
                      Default: "symbol_id"
        definition_package_path: Path to Definition ZIP file or extracted folder.
                                If provided, Definition metadata will be loaded and used to:
                                - Filter out User-Defined Spreads (unless include_user_defined_spreads=True)
                                - Enrich OHLCV data with contract specifications
                                - Validate instrument_id consistency
                                Default: None (no Definition enrichment)
        include_user_defined_spreads: Whether to include User-Defined Spreads (UD:EN symbols).
                                     Default True: include all instruments.
                                     Set to False to exclude UD:EN to focus on standard contracts.
                                     Only applicable when definition_package_path is provided.
    """

    data_path: str
    timezone: str = "UTC"
    extra_columns: list[str] | None = None
    use_instrument_id: bool = True
    symbol_format: str = "symbol_id"
    definition_package_path: str | None = None
    include_user_defined_spreads: bool = True


# ============================================================================
# Databento Data Adapter
# ============================================================================


class DatabentoAdapter(BaseDataAdapter, DataSource):
    """Databento adapter for importing Databento market data packages.

    Supports:
    - ZIP files or extracted folders
    - zstd-compressed CSV data
    - Multi-asset packages
    - Symbol filtering
    - Date range filtering
    - Multiple frequencies (1m, 5m, 15m, 30m, 1h, 1d)
    - Automatic cleanup of extracted ZIP files via context manager

    Implements both BaseDataAdapter and DataSource interfaces.

    Example (recommended - with context manager for automatic cleanup):
        >>> config = DatabentoConfig(
        ...     data_path="/path/to/databento.zip",
        ...     use_instrument_id=True
        ... )
        >>> with DatabentoAdapter(config) as adapter:
        ...     df = await adapter.fetch(
        ...         symbols=[],  # All symbols
        ...         start=pd.Timestamp('2023-01-01'),
        ...         end=pd.Timestamp('2023-12-31'),
        ...         frequency='1h'
        ...     )
        ...     # Temporary files automatically cleaned up on exit

    Example (without context manager - requires manual cleanup):
        >>> adapter = DatabentoAdapter(config)
        >>> try:
        ...     df = await adapter.fetch(...)
        ... finally:
        ...     adapter.cleanup()  # Explicitly cleanup extracted files
    """

    def __init__(self, config: DatabentoConfig | None = None, **kwargs: Any) -> None:
        """Initialize Databento adapter.

        Args:
            config: Databento configuration
            **kwargs: Additional config parameters (data_path, timezone)
        """
        super().__init__(
            name="DatabentoAdapter",
            rate_limit_per_second=1000,  # Local file I/O, no API rate limit
        )

        # Handle both config object and kwargs
        if config is None:
            if "data_path" not in kwargs:
                raise ValueError("data_path is required")
            config = DatabentoConfig(**kwargs)

        self.config = config
        self.data_path = Path(config.data_path)
        self.timezone = pytz.timezone(config.timezone)
        self._temp_dir: Path | None = None
        self._symbology_cache: pl.DataFrame | None = None
        # Symbol -> file path index for fast lookups (built once, used per batch)
        self._definition_file_index: dict[str, Path] | None = None
        # Pre-loaded Definition data cache (loaded once, used per batch)
        self._definition_data_cache: pl.DataFrame | None = None

        # Verify data path exists
        if not self.data_path.exists():
            raise FileNotFoundError(f"Databento data path not found: {self.data_path}")

        logger.info(
            "databento_adapter_initialized",
            data_path=str(self.data_path),
            is_zip=self._is_zip_file(),
            timezone=config.timezone,
        )

    def __enter__(self) -> "DatabentoAdapter":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and cleanup resources."""
        self.cleanup()

    def cleanup(self) -> None:
        """Explicitly cleanup temporary directory if created.

        This method can be called directly or automatically via context manager.
        Also called by __del__ as fallback, but explicit cleanup is preferred.
        """
        if self._temp_dir is not None and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=False)
                logger.info("databento_temp_dir_cleaned_up", path=str(self._temp_dir))
                self._temp_dir = None
            except Exception as e:
                logger.warning("databento_cleanup_failed", path=str(self._temp_dir), error=str(e))

        # Also cleanup Definition temp directory
        self.cleanup_definition()

    def __del__(self) -> None:
        """Cleanup temporary directory if created (fallback for non-context-manager usage).

        Note: __del__ is not guaranteed to be called. Prefer using context manager
        or calling cleanup() explicitly.
        """
        if self._temp_dir is not None and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def _is_zip_file(self) -> bool:
        """Check if data path is a ZIP file.

        Returns:
            True if ZIP file, False if directory
        """
        return self.data_path.is_file() and self.data_path.suffix == ".zip"

    def _get_working_dir(self) -> Path:
        """Get working directory (extract ZIP if needed).

        Returns:
            Path to directory containing Databento files

        Raises:
            InvalidDataError: If ZIP extraction fails
        """
        if self._is_zip_file():
            if self._temp_dir is None:
                # Extract to temporary directory
                self._temp_dir = Path(tempfile.mkdtemp(prefix="databento_"))
                self._extract_zip(self._temp_dir)
            return self._temp_dir
        else:
            return self.data_path

    def _extract_zip(self, target_dir: Path) -> Path:
        """Extract ZIP file to target directory.

        Args:
            target_dir: Directory to extract files to

        Returns:
            Path to extracted directory

        Raises:
            InvalidDataError: If extraction fails
        """
        try:
            logger.info("databento_extracting_zip", zip_path=str(self.data_path))
            with zipfile.ZipFile(self.data_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)

            logger.info("databento_zip_extracted", target_dir=str(target_dir))
            return target_dir

        except zipfile.BadZipFile as e:
            raise InvalidDataError(f"Invalid ZIP file: {e}") from e
        except Exception as e:
            raise InvalidDataError(f"Failed to extract ZIP: {e}") from e

    def _parse_metadata(self) -> DatabentoMetadata:
        """Parse metadata.json file.

        Returns:
            DatabentoMetadata object

        Raises:
            FileNotFoundError: If metadata.json not found
            InvalidDataError: If metadata parsing fails
        """
        working_dir = self._get_working_dir()
        metadata_file = working_dir / "metadata.json"

        if not metadata_file.exists():
            raise FileNotFoundError(f"metadata.json not found in {working_dir}")

        try:
            with open(metadata_file, "r") as f:
                data = json.load(f)

            query = data["query"]
            customizations = data.get("customizations", {})

            metadata = DatabentoMetadata(
                version=data["version"],
                job_id=data["job_id"],
                dataset=query["dataset"],
                schema=query["schema"],
                symbols=query["symbols"],
                start=query["start"],
                end=query["end"],
                encoding=query["encoding"],
                compression=query["compression"],
                stype_in=query["stype_in"],
                stype_out=query["stype_out"],
                split_duration=customizations.get("split_duration"),
                split_symbols=customizations.get("split_symbols", False),
            )

            logger.info(
                "databento_metadata_parsed",
                dataset=metadata.dataset,
                schema=metadata.schema,
                symbols_count=len(metadata.symbols),
                start=metadata.start,
                end=metadata.end,
                split_duration=metadata.split_duration,
                split_symbols=metadata.split_symbols,
            )

            return metadata

        except Exception as e:
            raise InvalidDataError(f"Failed to parse metadata.json: {e}") from e

    def _parse_manifest(self) -> DatabentoManifest:
        """Parse manifest.json file.

        Returns:
            DatabentoManifest object

        Raises:
            FileNotFoundError: If manifest.json not found
            InvalidDataError: If manifest parsing fails
        """
        working_dir = self._get_working_dir()
        manifest_file = working_dir / "manifest.json"

        if not manifest_file.exists():
            raise FileNotFoundError(f"manifest.json not found in {working_dir}")

        try:
            with open(manifest_file, "r") as f:
                data = json.load(f)

            files = []
            for file_data in data["files"]:
                files.append(
                    DatabentoFileInfo(
                        filename=file_data["filename"],
                        size=file_data["size"],
                        hash=file_data["hash"],
                        urls=file_data["urls"],
                    )
                )

            manifest = DatabentoManifest(job_id=data["job_id"], files=files)

            logger.info(
                "databento_manifest_parsed",
                job_id=manifest.job_id,
                files_count=len(manifest.files),
            )

            return manifest

        except Exception as e:
            raise InvalidDataError(f"Failed to parse manifest.json: {e}") from e

    def _find_all_ohlcv_files(self) -> list[Path]:
        """Find all OHLCV CSV files (compressed or uncompressed).

        Handles both single-file and multi-file packages.
        Multi-file packages (e.g., XNAS with daily splits) have thousands of files.

        Returns:
            Sorted list of OHLCV file paths (chronological order)

        Raises:
            FileNotFoundError: If no OHLCV files found
        """
        working_dir = self._get_working_dir()

        # Look for .csv.zst files first
        zst_files = sorted(working_dir.glob("*.ohlcv-*.csv.zst"))
        if zst_files:
            logger.info(
                "databento_ohlcv_files_discovered",
                file_count=len(zst_files),
                file_type="zst",
            )
            return zst_files

        # Look for uncompressed .csv files
        csv_files = sorted(working_dir.glob("*.ohlcv-*.csv"))
        if csv_files:
            logger.info(
                "databento_ohlcv_files_discovered",
                file_count=len(csv_files),
                file_type="csv",
            )
            return csv_files

        raise FileNotFoundError(f"No OHLCV files found in {working_dir}")

    def _decompress_zst(self, zst_file: Path, output_file: Path) -> Path:
        """Decompress zstd file.

        Args:
            zst_file: Path to .zst file
            output_file: Path to output CSV file

        Returns:
            Path to decompressed file

        Raises:
            InvalidDataError: If decompression fails
        """
        try:
            logger.info("databento_decompressing_zst", zst_file=str(zst_file))

            with open(zst_file, "rb") as compressed:
                dctx = zstd.ZstdDecompressor()
                with open(output_file, "wb") as destination:
                    dctx.copy_stream(compressed, destination)

            logger.info(
                "databento_decompressed",
                output_file=str(output_file),
                size_bytes=output_file.stat().st_size,
            )

            return output_file

        except Exception as e:
            raise InvalidDataError(f"Failed to decompress zstd file: {e}") from e

    def get_available_columns(self) -> dict[str, list[str]]:
        """Get available columns in the Databento package.

        Returns dictionary with:
        - 'standard': Standard OHLCV columns (always present)
        - 'extra': Additional columns available for preservation

        Returns:
            Dictionary with 'standard' and 'extra' column lists

        Example:
            >>> adapter = DatabentoAdapter(DatabentoConfig(
            ...     data_path="/path/to/databento.zip"
            ... ))
            >>> columns = adapter.get_available_columns()
            >>> print(f"Extra columns: {columns['extra']}")
            Extra columns: ['rtype', 'publisher_id', 'instrument_id']
        """
        csv_paths = self._get_ohlcv_csv_paths()

        # Use first file for column discovery (all files have same schema)
        csv_path = csv_paths[0]

        # Read just first row to get column names
        df_sample = pl.read_csv(
            csv_path,
            separator=",",
            has_header=True,
            n_rows=1,
        )

        all_columns = df_sample.columns
        standard_ohlcv = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]

        # Map Databento column names to what they'll become after renaming
        databento_to_standard = {
            "ts_event": "timestamp",
        }

        # Determine which columns are extra
        extra_columns = []
        for col in all_columns:
            # Map to standard name if applicable
            mapped_col = databento_to_standard.get(col, col)
            if mapped_col not in standard_ohlcv:
                extra_columns.append(col)

        logger.info(
            "databento_columns_discovered",
            total_columns=len(all_columns),
            standard_columns=len(standard_ohlcv),
            extra_columns=len(extra_columns),
        )

        return {
            "standard": standard_ohlcv,
            "extra": extra_columns,
        }

    def _get_ohlcv_csv_paths(self) -> list[Path]:
        """Get paths to all decompressed OHLCV CSV files.

        Handles decompression of multiple files if needed (multi-file packages).

        Returns:
            List of CSV file paths

        Raises:
            InvalidDataError: If file format is unknown
        """
        ohlcv_files = self._find_all_ohlcv_files()
        csv_paths = []

        for ohlcv_file in ohlcv_files:
            # If already CSV, use it
            if ohlcv_file.suffix == ".csv":
                csv_paths.append(ohlcv_file)
                continue

            # Decompress zst file
            if ohlcv_file.suffix == ".zst" and ".csv" in ohlcv_file.suffixes:
                working_dir = self._get_working_dir()
                output_csv = working_dir / ohlcv_file.name.replace(".zst", "")

                # Check if already decompressed
                if not output_csv.exists():
                    self._decompress_zst(ohlcv_file, output_csv)

                csv_paths.append(output_csv)
                continue

            raise InvalidDataError(f"Unknown OHLCV file format: {ohlcv_file}")

        return csv_paths

    def _parse_ohlcv_csv(
        self,
        symbols_filter: list[str] | None = None,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
    ) -> pl.DataFrame:
        """Parse all OHLCV CSV files to Polars DataFrame.

        Handles both single-file and multi-file packages. Multi-file packages
        (e.g., XNAS with 1,888 daily files) are concatenated into single DataFrame.

        Args:
            symbols_filter: Optional list of symbols to filter
            start: Optional start timestamp
            end: Optional end timestamp

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            InvalidDataError: If CSV parsing fails or no valid data found
        """
        csv_paths = self._get_ohlcv_csv_paths()

        logger.info(
            "databento_parsing_ohlcv_files",
            file_count=len(csv_paths),
        )

        dfs = []
        for csv_path in csv_paths:
            try:
                # Read CSV with Polars
                df = pl.read_csv(
                    csv_path,
                    separator=",",
                    has_header=True,
                    try_parse_dates=False,  # Parse dates manually for control
                )

                # Skip empty files
                if len(df) == 0:
                    logger.warning("databento_empty_file", path=str(csv_path))
                    continue

                dfs.append(df)

            except Exception as e:
                logger.error(
                    "databento_file_parse_error",
                    path=str(csv_path),
                    error=str(e),
                )
                # Continue processing other files
                continue

        if not dfs:
            raise InvalidDataError("No valid OHLCV data found in package")

        # Concatenate all DataFrames
        df = pl.concat(dfs)

        logger.info(
            "databento_files_concatenated",
            total_rows=len(df),
            files_processed=len(dfs),
        )

        try:
            # Map Databento schema to rustybt schema
            df = df.rename(
                {
                    "ts_event": "timestamp",
                    # symbol already exists
                    # open, high, low, close, volume already exist
                }
            )

            # Parse timestamp to datetime with UTC timezone
            df = df.with_columns(
                [
                    pl.col("timestamp")
                    .str.strptime(pl.Datetime("us", "UTC"), "%Y-%m-%dT%H:%M:%S%.fZ")
                    .alias("timestamp")
                ]
            )

            # Create composite asset identifier using instrument_id (if enabled)
            if self.config.use_instrument_id:
                # Ensure instrument_id column exists
                if "instrument_id" not in df.columns:
                    logger.warning(
                        "databento_missing_instrument_id",
                        message="instrument_id column not found, falling back to symbol-only mode",
                    )
                else:
                    if self.config.symbol_format == "symbol_id":
                        # Format: SYMBOL_INSTRUMENTID (e.g., "AAPL_13", "ESM0_6640")
                        # Exception: UD:EN symbols already contain instrument_id, don't append
                        df = df.with_columns(
                            [
                                pl.when(pl.col("symbol").str.starts_with("UD:EN:"))
                                .then(pl.col("symbol"))  # UD:EN already contains ID
                                .otherwise(
                                    pl.col("symbol") + "_" + pl.col("instrument_id").cast(pl.Utf8)
                                )
                                .alias("asset_id")
                            ]
                        )

                        logger.info(
                            "databento_using_instrument_id",
                            format="symbol_id",
                            sample_assets=df.select("asset_id")
                            .unique()
                            .head(5)
                            .to_series()
                            .to_list(),
                        )
                    else:
                        # symbol_only format (same as legacy mode)
                        df = df.with_columns([pl.col("symbol").alias("asset_id")])

                        logger.warning(
                            "databento_symbol_only_mode",
                            message="Using symbol-only mode may cause data collisions for reused symbols",
                        )

                    # Replace 'symbol' with 'asset_id' for downstream processing
                    # Keep original symbol for reference
                    df = df.rename({"symbol": "original_symbol"})
                    df = df.rename({"asset_id": "symbol"})

            # Filter by symbols if provided (now filters on original_symbol if using instrument_id)
            if symbols_filter:
                if "original_symbol" in df.columns:
                    # Filter by original symbol when using instrument_id
                    df = df.filter(pl.col("original_symbol").is_in(symbols_filter))
                else:
                    df = df.filter(pl.col("symbol").is_in(symbols_filter))

            # Filter by date range if provided
            if start is not None:
                start_utc = pd.Timestamp(start).tz_localize("UTC") if start.tz is None else start
                df = df.filter(pl.col("timestamp") >= start_utc)

            if end is not None:
                end_utc = pd.Timestamp(end).tz_localize("UTC") if end.tz is None else end
                df = df.filter(pl.col("timestamp") <= end_utc)

            # Select columns: always include standard OHLCV, optionally include extra
            columns_to_select = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]

            # If using instrument_id, preserve original_symbol and instrument_id for reference
            if self.config.use_instrument_id and "original_symbol" in df.columns:
                if "instrument_id" not in columns_to_select:
                    columns_to_select.append("instrument_id")
                if "original_symbol" not in columns_to_select:
                    columns_to_select.append("original_symbol")

            # Add extra columns if specified in config
            if self.config.extra_columns:
                # Validate that requested extra columns exist
                available_cols = set(df.columns)
                for extra_col in self.config.extra_columns:
                    if extra_col in available_cols and extra_col not in columns_to_select:
                        columns_to_select.append(extra_col)
                    elif extra_col not in available_cols:
                        logger.warning(
                            "databento_extra_column_not_found",
                            column=extra_col,
                            available=list(available_cols),
                        )

            # Ensure columns exist before selecting
            columns_to_select = [col for col in columns_to_select if col in df.columns]
            df = df.select(columns_to_select)

            extra_cols_preserved = [
                col
                for col in columns_to_select
                if col not in ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
            ]
            logger.info(
                "databento_ohlcv_parsed",
                rows=len(df),
                symbols=len(df["symbol"].unique()),
                unique_instruments=(
                    len(df["instrument_id"].unique()) if "instrument_id" in df.columns else None
                ),
                columns_preserved=len(columns_to_select),
                extra_columns=extra_cols_preserved if extra_cols_preserved else None,
                using_instrument_id=self.config.use_instrument_id,
            )

            return df

        except Exception as e:
            raise InvalidDataError(f"Failed to parse OHLCV CSV: {e}") from e

    # ============================================================================
    # Batch Processing Methods (Memory Optimization)
    # ============================================================================

    def _parse_ohlcv_batch(
        self,
        file_paths: list[Path],
        symbols_filter: list[str] | None = None,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
    ) -> pl.DataFrame:
        """Parse a batch of OHLCV files to Polars DataFrame.

        Memory-efficient version that processes a subset of files.

        Args:
            file_paths: List of file paths to process (zst or csv)
            symbols_filter: Optional list of symbols to filter
            start: Optional start timestamp
            end: Optional end timestamp

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            InvalidDataError: If parsing fails
        """
        csv_paths = []
        working_dir = self._get_working_dir()

        # Decompress only the files in this batch
        for file_path in file_paths:
            if file_path.suffix == ".csv":
                csv_paths.append(file_path)
            elif file_path.suffix == ".zst" and ".csv" in file_path.suffixes:
                output_csv = working_dir / file_path.name.replace(".zst", "")
                if not output_csv.exists():
                    self._decompress_zst(file_path, output_csv)
                csv_paths.append(output_csv)
            else:
                logger.warning("databento_unknown_file_format", path=str(file_path))
                continue

        if not csv_paths:
            raise InvalidDataError("No valid CSV files in batch")

        # Parse batch of CSV files
        dfs = []
        for csv_path in csv_paths:
            try:
                df = pl.read_csv(
                    csv_path,
                    separator=",",
                    has_header=True,
                    try_parse_dates=False,
                )
                if len(df) > 0:
                    dfs.append(df)
            except Exception as e:
                logger.warning(
                    "databento_batch_file_parse_error",
                    path=str(csv_path),
                    error=str(e),
                )
                continue

        if not dfs:
            raise InvalidDataError("No valid data in batch")

        # Concatenate batch
        df = pl.concat(dfs)

        # Apply same transformations as _parse_ohlcv_csv
        try:
            df = df.rename({"ts_event": "timestamp"})

            df = df.with_columns(
                [
                    pl.col("timestamp")
                    .str.strptime(pl.Datetime("us", "UTC"), "%Y-%m-%dT%H:%M:%S%.fZ")
                    .alias("timestamp")
                ]
            )

            # Create composite asset identifier using instrument_id (if enabled)
            if self.config.use_instrument_id and "instrument_id" in df.columns:
                if self.config.symbol_format == "symbol_id":
                    df = df.with_columns(
                        [
                            pl.when(pl.col("symbol").str.starts_with("UD:EN:"))
                            .then(pl.col("symbol"))
                            .otherwise(
                                pl.col("symbol") + "_" + pl.col("instrument_id").cast(pl.Utf8)
                            )
                            .alias("asset_id")
                        ]
                    )
                else:
                    df = df.with_columns([pl.col("symbol").alias("asset_id")])

                df = df.rename({"symbol": "original_symbol"})
                df = df.rename({"asset_id": "symbol"})

            # Filter by symbols
            if symbols_filter:
                if "original_symbol" in df.columns:
                    df = df.filter(pl.col("original_symbol").is_in(symbols_filter))
                else:
                    df = df.filter(pl.col("symbol").is_in(symbols_filter))

            # Filter by date range
            if start is not None:
                start_utc = pd.Timestamp(start).tz_localize("UTC") if start.tz is None else start
                df = df.filter(pl.col("timestamp") >= start_utc)

            if end is not None:
                end_utc = pd.Timestamp(end).tz_localize("UTC") if end.tz is None else end
                df = df.filter(pl.col("timestamp") <= end_utc)

            # Select columns
            columns_to_select = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
            if self.config.use_instrument_id and "original_symbol" in df.columns:
                if "instrument_id" not in columns_to_select:
                    columns_to_select.append("instrument_id")
                if "original_symbol" not in columns_to_select:
                    columns_to_select.append("original_symbol")

            if self.config.extra_columns:
                available_cols = set(df.columns)
                for extra_col in self.config.extra_columns:
                    if extra_col in available_cols and extra_col not in columns_to_select:
                        columns_to_select.append(extra_col)

            columns_to_select = [col for col in columns_to_select if col in df.columns]
            df = df.select(columns_to_select)

            return df

        except Exception as e:
            raise InvalidDataError(f"Failed to parse batch: {e}") from e

    def _cleanup_batch_files(self, file_paths: list[Path]) -> None:
        """Clean up decompressed files from a batch to free disk space.

        Args:
            file_paths: Original file paths (will clean corresponding CSVs)
        """
        working_dir = self._get_working_dir()
        for file_path in file_paths:
            if file_path.suffix == ".zst":
                csv_path = working_dir / file_path.name.replace(".zst", "")
                if csv_path.exists():
                    try:
                        csv_path.unlink()
                    except Exception as e:
                        logger.debug(
                            "databento_batch_cleanup_error", path=str(csv_path), error=str(e)
                        )

    def _find_symbology_file(self) -> Path | None:
        """Find symbology file (CSV or JSON).

        Returns:
            Path to symbology file, or None if not found
        """
        working_dir = self._get_working_dir()

        # Check for CSV first
        csv_path = working_dir / "symbology.csv"
        if csv_path.exists():
            return csv_path

        # Check for JSON
        json_path = working_dir / "symbology.json"
        if json_path.exists():
            return json_path

        return None

    def _parse_symbology(self) -> pl.DataFrame | None:
        """Parse symbology file (CSV or JSON) to DataFrame.

        Symbology provides symbol → instrument_id → date mappings.

        Returns:
            Polars DataFrame with symbology data, or None if not found

        Raises:
            InvalidDataError: If symbology parsing fails
        """
        # Return cached symbology if available
        if self._symbology_cache is not None:
            return self._symbology_cache

        symbology_file = self._find_symbology_file()
        if symbology_file is None:
            logger.info("databento_symbology_not_found")
            return None

        try:
            logger.info("databento_parsing_symbology", path=str(symbology_file))

            if symbology_file.suffix == ".csv":
                # Parse CSV symbology
                symbology = pl.read_csv(
                    symbology_file,
                    separator=",",
                    has_header=True,
                    try_parse_dates=False,
                )
            elif symbology_file.suffix == ".json":
                # Parse JSON symbology
                symbology = self._parse_symbology_json()
                if symbology is None:
                    raise InvalidDataError(f"Failed to parse JSON symbology file: {symbology_file}")
            else:
                raise InvalidDataError(f"Unknown symbology format: {symbology_file}")

            logger.info(
                "databento_symbology_parsed",
                rows=len(symbology),
                columns=len(symbology.columns),
            )

            # Cache for future use
            self._symbology_cache = symbology

            return symbology

        except Exception as e:
            logger.error("databento_symbology_parse_error", path=str(symbology_file), error=str(e))
            return None

    def _parse_symbology_json(self) -> pl.DataFrame | None:
        """Parse symbology.json file to DataFrame.

        Returns:
            Polars DataFrame with symbology data

        Raises:
            InvalidDataError: If JSON parsing fails
        """
        working_dir = self._get_working_dir()
        json_path = working_dir / "symbology.json"

        if not json_path.exists():
            return None

        try:
            # Use Polars' native JSON reader for efficient parsing
            # This is much faster than json.load() for large files
            symbology = pl.read_json(json_path)

            return symbology

        except Exception as e:
            raise InvalidDataError(f"Failed to parse symbology.json: {e}") from e

    def get_instruments_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        """Get all instruments for a given symbol.

        Args:
            symbol: Symbol to look up (e.g., "ES", "AAPL")

        Returns:
            List of instrument dictionaries with metadata
        """
        symbology = self._parse_symbology()
        if symbology is None:
            logger.warning("databento_symbology_unavailable_for_lookup")
            return []

        if "symbol" not in symbology.columns:
            # Try alternative column names
            if "raw_symbol" in symbology.columns:
                symbol_col = "raw_symbol"
            else:
                logger.warning("databento_symbology_missing_symbol_column")
                return []
        else:
            symbol_col = "symbol"

        # Filter by symbol
        matches = symbology.filter(pl.col(symbol_col) == symbol)

        # Convert to list of dicts
        instruments = []
        for row in matches.iter_rows(named=True):
            instruments.append(dict(row))

        return instruments

    def get_symbol_for_instrument(self, instrument_id: int) -> dict[str, Any] | None:
        """Get symbol for a specific instrument_id.

        Args:
            instrument_id: Instrument ID to look up

        Returns:
            Dictionary with symbol metadata, or None if not found
        """
        symbology = self._parse_symbology()
        if symbology is None:
            return None

        if "instrument_id" not in symbology.columns:
            logger.warning("databento_symbology_missing_instrument_id_column")
            return None

        # Filter by instrument_id
        matches = symbology.filter(pl.col("instrument_id") == instrument_id)

        if len(matches) == 0:
            return None

        # Return first match as dict
        return dict(matches.row(0, named=True))

    def get_active_symbols_for_date(self, date: pd.Timestamp) -> list[str]:
        """Get symbols active on a specific date.

        Args:
            date: Date to query

        Returns:
            List of active symbols
        """
        symbology = self._parse_symbology()
        if symbology is None:
            return []

        # Check for date range columns
        date_columns = [col for col in symbology.columns if "date" in col.lower()]
        if len(date_columns) < 2:
            logger.warning("databento_symbology_missing_date_columns")
            # Return all symbols if no date filtering possible
            if "symbol" in symbology.columns:
                return symbology["symbol"].unique().to_list()
            return []

        # Assume first two date columns are start/end
        # This is a simplification - actual logic depends on Databento format
        if "symbol" in symbology.columns:
            return symbology["symbol"].unique().to_list()

        return []

    def validate_symbology_consistency(self, df: pl.DataFrame) -> dict[str, Any]:
        """Validate symbology consistency with OHLCV data.

        Args:
            df: OHLCV DataFrame to validate

        Returns:
            Dictionary with validation results
        """
        symbology = self._parse_symbology()

        if symbology is None:
            return {
                "valid": False,
                "errors": ["Symbology file not found"],
            }

        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }
        errors: list[str] = result["errors"]  # type: ignore[assignment]
        warnings: list[str] = result["warnings"]  # type: ignore[assignment]

        # Check instrument_id coverage
        if "instrument_id" in df.columns and "instrument_id" in symbology.columns:
            ohlcv_instruments = set(df["instrument_id"].unique().to_list())
            symbology_instruments = set(symbology["instrument_id"].unique().to_list())

            missing = ohlcv_instruments - symbology_instruments
            if len(missing) > 0:
                coverage = (len(ohlcv_instruments) - len(missing)) / len(ohlcv_instruments)
                warnings.append(
                    f"Symbology missing {len(missing)} instruments ({coverage:.1%} coverage)"
                )

        return result

    def _validate_symbol_uniqueness(self, df: pl.DataFrame) -> None:
        """Validate that symbols are unique across instrument_ids.

        Logs warnings if same symbol appears with multiple instrument_ids
        at the same timestamp (indicating potential data collisions).

        Args:
            df: DataFrame with 'symbol', 'instrument_id', 'timestamp' columns
        """
        if "instrument_id" not in df.columns or "original_symbol" not in df.columns:
            return

        # Check for symbol collisions (same original_symbol, different instrument_id, same date)
        # Group by date (not exact timestamp) for daily collision check
        df_with_date = df.with_columns([pl.col("timestamp").dt.date().alias("date")])

        collisions = (
            df_with_date.group_by(["date", "original_symbol"])
            .agg(pl.col("instrument_id").n_unique().alias("instrument_count"))
            .filter(pl.col("instrument_count") > 1)
        )

        if len(collisions) > 0:
            logger.warning(
                "databento_symbol_collisions_detected",
                collision_count=len(collisions),
                message="Same symbol used by multiple instruments at same timestamp",
                recommendation="Use use_instrument_id=True in config (already enabled)",
            )

            # Log sample collisions
            sample = collisions.head(5)
            for row in sample.iter_rows(named=True):
                logger.warning(
                    "databento_collision_example",
                    date=str(row["date"]),
                    symbol=row["original_symbol"],
                    instrument_count=row["instrument_count"],
                )

    # ============================================================================
    # Definition Package Methods (Story 9.2/9.3)
    # ============================================================================

    def _get_definition_working_dir(self) -> Path | None:
        """Get working directory for Definition package (extract ZIP if needed).

        Returns:
            Path to directory containing Definition files, or None if not configured

        Raises:
            InvalidDataError: If ZIP extraction fails
        """
        if self.config.definition_package_path is None:
            return None

        definition_path = Path(self.config.definition_package_path)
        if not definition_path.exists():
            logger.warning(
                "databento_definition_path_not_found",
                path=str(definition_path),
            )
            return None

        # Check if ZIP file
        if definition_path.is_file() and definition_path.suffix == ".zip":
            # Extract to temp directory if not already done
            if not hasattr(self, "_definition_temp_dir") or self._definition_temp_dir is None:
                self._definition_temp_dir = Path(tempfile.mkdtemp(prefix="databento_def_"))
                self._extract_definition_zip(self._definition_temp_dir)
            return self._definition_temp_dir
        else:
            return definition_path

    def _extract_definition_zip(self, target_dir: Path) -> Path:
        """Extract Definition ZIP file to target directory.

        Args:
            target_dir: Directory to extract files to

        Returns:
            Path to extracted directory

        Raises:
            InvalidDataError: If extraction fails
        """
        definition_path = Path(self.config.definition_package_path)  # type: ignore
        try:
            logger.info("databento_extracting_definition_zip", zip_path=str(definition_path))
            with zipfile.ZipFile(definition_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)

            logger.info("databento_definition_zip_extracted", target_dir=str(target_dir))
            return target_dir

        except zipfile.BadZipFile as e:
            raise InvalidDataError(f"Invalid Definition ZIP file: {e}") from e
        except Exception as e:
            raise InvalidDataError(f"Failed to extract Definition ZIP: {e}") from e

    def _parse_definition_metadata(self) -> DatabentoMetadata | None:
        """Parse Definition package metadata.json file.

        Returns:
            DatabentoMetadata object, or None if not configured

        Raises:
            InvalidDataError: If metadata parsing fails
        """
        working_dir = self._get_definition_working_dir()
        if working_dir is None:
            return None

        metadata_file = working_dir / "metadata.json"
        if not metadata_file.exists():
            logger.warning(
                "databento_definition_metadata_not_found",
                path=str(working_dir),
            )
            return None

        try:
            with open(metadata_file, "r") as f:
                data = json.load(f)

            query = data["query"]
            customizations = data.get("customizations", {})

            metadata = DatabentoMetadata(
                version=data["version"],
                job_id=data["job_id"],
                dataset=query["dataset"],
                schema=query["schema"],
                symbols=query["symbols"],
                start=query["start"],
                end=query["end"],
                encoding=query["encoding"],
                compression=query["compression"],
                stype_in=query["stype_in"],
                stype_out=query["stype_out"],
                split_duration=customizations.get("split_duration"),
                split_symbols=customizations.get("split_symbols", False),
            )

            logger.info(
                "databento_definition_metadata_parsed",
                dataset=metadata.dataset,
                schema=metadata.schema,
                split_duration=metadata.split_duration,
                split_symbols=metadata.split_symbols,
            )

            return metadata

        except Exception as e:
            raise InvalidDataError(f"Failed to parse Definition metadata.json: {e}") from e

    def _detect_definition_schema(self, df: pl.DataFrame) -> str:
        """Detect whether Definition is CME or NASDAQ based on columns/values.

        CME indicators:
        - Has varied instrument_class values (F, C, P, S, T)
        - Has user_defined_instrument = 'Y' values
        - Has non-zero underlying_id for options/spreads

        NASDAQ indicators:
        - All instrument_class = 'K' (equity)
        - All user_defined_instrument = 'N'
        - All underlying_id = 0

        Args:
            df: Definition DataFrame to analyze

        Returns:
            "CME" or "NASDAQ" based on detected schema
        """
        # Check instrument_class column
        if "instrument_class" in df.columns:
            classes = df["instrument_class"].unique().to_list()
            # NASDAQ only has 'K' (equity)
            if classes == ["K"] or set(classes) == {"K"}:
                return "NASDAQ"
            # CME has varied classes (F, C, P, S, T)
            if any(c in ["F", "C", "P", "S", "T"] for c in classes if c is not None):
                return "CME"

        # Check user_defined_instrument - CME has 'Y' values, NASDAQ only 'N'
        if "user_defined_instrument" in df.columns:
            uds_values = df["user_defined_instrument"].unique().to_list()
            if "Y" in uds_values:
                return "CME"

        # Check underlying_id - NASDAQ all zeros, CME has non-zero for options/spreads
        if "underlying_id" in df.columns:
            non_zero = df.filter(pl.col("underlying_id") != 0)
            if len(non_zero) > 0:
                return "CME"

        # Default to NASDAQ if no CME indicators found
        return "NASDAQ"

    def _find_definition_file_for_date(self, date: pd.Timestamp) -> Path | None:
        """Find Definition file for a specific date.

        CME files use pattern: glbx-mdp3-{YYYYMMDD}.definition.csv.zst

        Args:
            date: Date to find Definition file for

        Returns:
            Path to Definition file, or None if not found
        """
        working_dir = self._get_definition_working_dir()
        if working_dir is None:
            return None

        # Format date for CME filename pattern
        date_str = date.strftime("%Y%m%d")

        # CME pattern: glbx-mdp3-{YYYYMMDD}.definition.csv.zst
        cme_pattern = f"*-{date_str}.definition.csv.zst"
        matches = list(working_dir.glob(cme_pattern))

        if matches:
            return matches[0]

        # Also try uncompressed version
        uncompressed_pattern = f"*-{date_str}.definition.csv"
        matches = list(working_dir.glob(uncompressed_pattern))

        if matches:
            return matches[0]

        return None

    def _build_definition_file_index(self) -> dict[str, Path]:
        """Build symbol -> file path index for NASDAQ Definition files.

        This is an optimization to avoid repeated glob operations.
        The index is built once and cached in self._definition_file_index.

        Returns:
            Dictionary mapping symbol to file path
        """
        if self._definition_file_index is not None:
            return self._definition_file_index

        working_dir = self._get_definition_working_dir()
        if working_dir is None:
            self._definition_file_index = {}
            return {}

        # NASDAQ pattern: xnas-itch-*.definition.*.csv.zst
        nasdaq_pattern = "xnas-itch-*.definition.*.csv.zst"
        all_files = list(working_dir.glob(nasdaq_pattern))

        # Also check uncompressed
        nasdaq_pattern_csv = "xnas-itch-*.definition.*.csv"
        all_files.extend(
            [f for f in working_dir.glob(nasdaq_pattern_csv) if not str(f).endswith(".zst")]
        )

        # Build symbol -> file path index
        index: dict[str, Path] = {}
        for file_path in all_files:
            name = file_path.name
            if ".definition." in name:
                parts = name.split(".definition.")
                if len(parts) == 2:
                    symbol_part = parts[1]
                    symbol = symbol_part.replace(".csv.zst", "").replace(".csv", "")
                    index[symbol] = file_path

        self._definition_file_index = index
        logger.info(
            "databento_definition_file_index_built",
            total_symbols=len(index),
        )

        return index

    def _preload_all_definition_data(self) -> pl.DataFrame | None:
        """Pre-load ALL Definition data into memory cache.

        This optimization prevents re-parsing Definition files for each batch.
        For NASDAQ with thousands of symbol files, this loads them once at the
        start and keeps the combined DataFrame in memory.

        To avoid OOM errors when concatenating thousands of DataFrames, this uses
        a "Chunk-and-Cache" strategy:
        1. Process files in chunks (e.g., 2000 files)
        2. Write each chunk to a temporary Parquet file
        3. Load the final result from the Parquet files

        Returns:
            Combined Definition DataFrame, or None if not available
        """
        import gc
        import uuid

        # Return cached data if already loaded
        if self._definition_data_cache is not None:
            logger.debug(
                "databento_using_cached_definition_data",
                rows=len(self._definition_data_cache),
            )
            return self._definition_data_cache

        if self.config.definition_package_path is None:
            return None

        # Parse Definition metadata to determine split strategy
        def_metadata = self._parse_definition_metadata()
        if def_metadata is None:
            return None

        logger.info(
            "databento_preloading_definition_data",
            split_symbols=def_metadata.split_symbols,
            split_duration=def_metadata.split_duration,
        )

        combined_definition: pl.DataFrame | None = None

        # NASDAQ: Symbol-split strategy - load ALL symbol files
        if def_metadata.split_symbols:
            # Get all Definition files (pass None to get all)
            files = self._find_definition_files_by_symbol(None)
            if not files:
                logger.warning(
                    "databento_no_definition_files_to_preload",
                )
                return None

            logger.info(
                "databento_preloading_definition_files",
                file_count=len(files),
            )

            # Create temp directory for intermediate Parquet chunks
            if self._temp_dir is None:
                self._temp_dir = Path(tempfile.mkdtemp(prefix="databento_"))

            cache_dir = self._temp_dir / "def_cache"
            cache_dir.mkdir(exist_ok=True)

            # Chunk size: 2000 files per chunk seems safe for 16GB RAM
            # Each file is small (~3 rows), but Polars overhead adds up
            chunk_size = 2000
            total_chunks = (len(files) + chunk_size - 1) // chunk_size

            parquet_files = []

            # Process in chunks
            for chunk_idx in range(total_chunks):
                start_idx = chunk_idx * chunk_size
                end_idx = min(start_idx + chunk_size, len(files))
                chunk_files = files[start_idx:end_idx]

                logger.info(
                    "databento_processing_definition_chunk",
                    chunk=chunk_idx + 1,
                    total_chunks=total_chunks,
                    files_in_chunk=len(chunk_files),
                )

                # Parse files in PARALLEL
                max_workers = min(32, len(chunk_files))
                dfs = []

                def parse_file_safe(file_path: Path) -> pl.DataFrame | None:
                    try:
                        return self._parse_definition_file(file_path)
                    except Exception as e:
                        logger.warning(
                            "databento_definition_file_parse_error",
                            file=str(file_path),
                            error=str(e),
                        )
                        return None

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_file = {executor.submit(parse_file_safe, f): f for f in chunk_files}
                    for future in as_completed(future_to_file):
                        result = future.result()
                        if result is not None:
                            dfs.append(result)

                if dfs:
                    # Concatenate this chunk
                    chunk_df = pl.concat(dfs, how="diagonal_relaxed")

                    # Write to temporary Parquet file
                    chunk_file = cache_dir / f"chunk_{chunk_idx}_{uuid.uuid4().hex}.parquet"
                    chunk_df.write_parquet(chunk_file)
                    parquet_files.append(chunk_file)

                    # Clear memory
                    del dfs
                    del chunk_df
                    gc.collect()

            if parquet_files:
                logger.info(
                    "databento_loading_cached_chunks",
                    chunk_count=len(parquet_files),
                )

                # Load all chunks efficiently using scan_parquet
                # This handles memory much better than concat(dfs)
                combined_definition = pl.scan_parquet(str(cache_dir / "*.parquet")).collect()

                # Remove duplicates (keep most recent by ts_event if available)
                if "ts_event" in combined_definition.columns:
                    combined_definition = combined_definition.sort("ts_event", descending=True)
                combined_definition = combined_definition.unique(
                    subset=["instrument_id"], keep="first"
                )

                logger.info(
                    "databento_definition_data_preloaded",
                    total_rows=len(combined_definition),
                    unique_instruments=(
                        len(combined_definition["instrument_id"].unique())
                        if "instrument_id" in combined_definition.columns
                        else None
                    ),
                )

                # Cleanup intermediate files
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning("databento_cache_cleanup_failed", error=str(e))

        # CME: Date-split strategy - don't preload (date-specific loading is fine)
        elif def_metadata.split_duration == "day":
            logger.info(
                "databento_cme_no_preload",
                message="CME uses date-split; Definition loaded per-date as needed",
            )
            return None

        # Cache and return
        self._definition_data_cache = combined_definition
        return combined_definition

    def _find_definition_files_by_symbol(self, symbols: list[str] | None = None) -> list[Path]:
        """Find Definition files for NASDAQ symbols.

        NASDAQ uses symbol-split strategy with file pattern:
        xnas-itch-{start}-{end}.definition.{SYMBOL}.csv.zst

        Uses cached file index for O(1) lookups instead of repeated glob operations.

        Args:
            symbols: List of symbols to find Definition files for.
                    If None, returns all symbol Definition files.

        Returns:
            List of paths to matching Definition files
        """
        # Use cached index for fast lookups
        index = self._build_definition_file_index()

        if not index:
            logger.debug(
                "databento_no_nasdaq_definition_files",
                message="File index is empty",
            )
            return []

        if symbols is None:
            # Return all files
            logger.info(
                "databento_nasdaq_definition_files_found",
                file_count=len(index),
            )
            return sorted(index.values())

        # O(1) lookups using index
        matching_files = []
        for symbol in symbols:
            if symbol in index:
                matching_files.append(index[symbol])

        logger.info(
            "databento_nasdaq_definition_files_filtered",
            requested_symbols=len(symbols),
            matching_files=len(matching_files),
        )

        return sorted(matching_files)

    def _parse_definition_file(self, file_path: Path) -> pl.DataFrame:
        """Parse a single Definition CSV file.

        Handles zstd decompression if needed. Returns DataFrame with instrument
        metadata indexed by instrument_id.

        Args:
            file_path: Path to Definition file (.csv or .csv.zst)

        Returns:
            Polars DataFrame with Definition data

        Raises:
            InvalidDataError: If parsing fails
        """
        try:
            # Handle zstd compression
            if file_path.suffix == ".zst" and ".csv" in file_path.suffixes:
                working_dir = self._get_definition_working_dir()
                if working_dir is None:
                    raise InvalidDataError("Definition working directory not available")

                output_csv = working_dir / file_path.name.replace(".zst", "")

                # Decompress if not already done
                if not output_csv.exists():
                    self._decompress_zst(file_path, output_csv)

                csv_path = output_csv
            else:
                csv_path = file_path

            # Parse CSV with Polars
            # Definition files have 65 columns - let Polars infer types initially
            df = pl.read_csv(
                csv_path,
                separator=",",
                has_header=True,
                try_parse_dates=False,
                null_values=["", "NA", "N/A"],
            )

            logger.info(
                "databento_definition_file_parsed",
                path=str(file_path),
                rows=len(df),
                columns=len(df.columns),
            )

            return df

        except Exception as e:
            raise InvalidDataError(f"Failed to parse Definition file {file_path}: {e}") from e

    def _load_definition_for_date(self, date: pd.Timestamp) -> pl.DataFrame | None:
        """Load Definition data for a specific date.

        Args:
            date: Date to load Definition for

        Returns:
            Polars DataFrame with Definition data, or None if:
            - Definition package not configured
            - No Definition file for the specified date

        Note:
            This method returns None gracefully if Definition is not available,
            allowing the caller to proceed without Definition enrichment.
        """
        # Check if Definition package is configured
        if self.config.definition_package_path is None:
            return None

        # Find the Definition file for this date
        definition_file = self._find_definition_file_for_date(date)
        if definition_file is None:
            logger.debug(
                "databento_definition_file_not_found_for_date",
                date=str(date),
            )
            return None

        # Parse and return the Definition data
        return self._parse_definition_file(definition_file)

    def _load_definition_for_symbols(
        self,
        symbols: list[str],
        date: pd.Timestamp | None = None,
    ) -> pl.DataFrame | None:
        """Load Definition data for specific symbols (NASDAQ) or date (CME).

        This is a unified API that handles both CME and NASDAQ Definition loading:
        - CME (split_duration="day"): Loads by date using _find_definition_file_for_date
        - NASDAQ (split_symbols=True): Loads by symbol using _find_definition_files_by_symbol

        Args:
            symbols: List of symbols to load Definition for
            date: Date to load Definition for (used for CME, ignored for NASDAQ)

        Returns:
            Polars DataFrame with Definition data, or None if not available
        """
        if self.config.definition_package_path is None:
            return None

        # Parse Definition metadata to determine split strategy
        def_metadata = self._parse_definition_metadata()
        if def_metadata is None:
            return None

        # NASDAQ uses symbol-split strategy
        if def_metadata.split_symbols:
            files = self._find_definition_files_by_symbol(symbols)
            if not files:
                logger.debug(
                    "databento_no_nasdaq_definition_for_symbols",
                    symbols=symbols,
                )
                return None

            # Parse and concatenate all symbol files
            dfs = []
            for file_path in files:
                try:
                    df = self._parse_definition_file(file_path)
                    dfs.append(df)
                except Exception as e:
                    logger.warning(
                        "databento_definition_file_parse_error",
                        file=str(file_path),
                        error=str(e),
                    )
                    continue

            if not dfs:
                return None

            # Use how="diagonal_relaxed" to handle schema mismatches across symbol files
            combined = pl.concat(dfs, how="diagonal_relaxed")
            logger.info(
                "databento_nasdaq_definition_loaded",
                symbols_requested=len(symbols),
                files_loaded=len(dfs),
                total_rows=len(combined),
            )
            return combined

        # CME uses date-split strategy
        elif def_metadata.split_duration == "day":
            if date is None:
                logger.warning(
                    "databento_cme_definition_needs_date",
                    message="CME Definition requires a date parameter",
                )
                return None
            return self._load_definition_for_date(date)

        else:
            logger.warning(
                "databento_unknown_definition_split_strategy",
                split_duration=def_metadata.split_duration,
                split_symbols=def_metadata.split_symbols,
            )
            return None

    def _get_definition_key_fields(self, df: pl.DataFrame) -> pl.DataFrame:
        """Extract key metadata fields from Definition DataFrame.

        Extracts the fields needed for OHLCV enrichment and filtering.
        Handles both CME and NASDAQ schemas:

        CME (derivatives):
        - Core identification: instrument_id, raw_symbol, symbol, asset
        - Classification: instrument_class, user_defined_instrument
        - Relationships: underlying_id
        - Contract specs: expiration, activation, strike_price, min_price_increment, contract_multiplier

        NASDAQ (equities):
        - Core identification: instrument_id, raw_symbol, symbol
        - Exchange info: exchange, currency, lot_size (min_lot_size)
        - Note: asset, instrument_class, underlying_id typically empty/default for equities

        Args:
            df: Full Definition DataFrame with all 65 columns

        Returns:
            DataFrame with only key metadata fields
        """
        # Detect schema to determine which fields are relevant
        schema_type = self._detect_definition_schema(df)

        if schema_type == "NASDAQ":
            # NASDAQ equity-relevant fields
            key_columns = [
                # Core identification
                "instrument_id",
                "raw_symbol",
                "symbol",
                # Exchange info (equity-relevant)
                "exchange",
                "currency",
                "min_lot_size",  # NASDAQ uses min_lot_size as lot_size
                # Classification (will be 'K' for all NASDAQ)
                "instrument_class",
                "user_defined_instrument",
                # Include these for cross-exchange compatibility, though mostly null for NASDAQ
                "underlying_id",
                "expiration",
                "strike_price",
            ]
        else:
            # CME derivatives fields
            key_columns = [
                # Core identification
                "instrument_id",
                "raw_symbol",
                "symbol",
                "asset",
                # Classification
                "instrument_class",
                "user_defined_instrument",
                # Relationships
                "underlying_id",
                # Contract specifications
                "expiration",
                "activation",
                "strike_price",
                "min_price_increment",
                "contract_multiplier",
            ]

        # Select only columns that exist
        available_cols = [col for col in key_columns if col in df.columns]

        return df.select(available_cols)

    def _filter_user_defined_spreads(self, df: pl.DataFrame) -> pl.DataFrame:
        """Filter out User-Defined Spreads from DataFrame.

        Excludes instruments where:
        - user_defined_instrument = 'Y', OR
        - instrument_class = 'T'

        Args:
            df: DataFrame with Definition metadata

        Returns:
            Filtered DataFrame excluding UDS instruments
        """
        if "user_defined_instrument" not in df.columns and "instrument_class" not in df.columns:
            logger.warning(
                "databento_cannot_filter_uds",
                message="Missing user_defined_instrument and instrument_class columns",
            )
            return df

        original_count = len(df)

        # Build filter conditions
        conditions = []
        if "user_defined_instrument" in df.columns:
            conditions.append(pl.col("user_defined_instrument") != "Y")
        if "instrument_class" in df.columns:
            conditions.append(pl.col("instrument_class") != "T")

        # Apply filter (AND of all conditions)
        if conditions:
            filter_expr = conditions[0]
            for cond in conditions[1:]:
                filter_expr = filter_expr & cond
            df = df.filter(filter_expr)

        filtered_count = original_count - len(df)
        if filtered_count > 0:
            logger.info(
                "databento_uds_filtered",
                original_count=original_count,
                filtered_count=filtered_count,
                remaining_count=len(df),
            )

        return df

    def _create_composite_instrument_id(
        self,
        df: pl.DataFrame,
        exchange: str | None = None,
    ) -> pl.DataFrame:
        """Create composite instrument_id to prevent cross-exchange collisions.

        Creates a new column `composite_instrument_id` with format: {exchange}_{instrument_id}
        This ensures CME and NASDAQ instruments are distinguishable even if they share
        the same numeric instrument_id.

        Args:
            df: DataFrame with instrument_id column
            exchange: Exchange identifier (e.g., "XCME", "XNAS"). If None, attempts
                     to detect from 'exchange' column in the DataFrame.

        Returns:
            DataFrame with added composite_instrument_id column
        """
        if "instrument_id" not in df.columns:
            logger.warning(
                "databento_cannot_create_composite_id",
                message="DataFrame missing instrument_id column",
            )
            return df

        # Determine exchange
        if exchange is None:
            if "exchange" in df.columns:
                # Use exchange from DataFrame
                df = df.with_columns(
                    (pl.col("exchange") + "_" + pl.col("instrument_id").cast(pl.Utf8)).alias(
                        "composite_instrument_id"
                    )
                )
            else:
                # No exchange info available, just use instrument_id as string
                df = df.with_columns(
                    pl.col("instrument_id").cast(pl.Utf8).alias("composite_instrument_id")
                )
        else:
            # Use provided exchange
            df = df.with_columns(
                pl.lit(f"{exchange}_")
                .add(pl.col("instrument_id").cast(pl.Utf8))
                .alias("composite_instrument_id")
            )

        return df

    def _enrich_ohlcv_with_definition(
        self,
        ohlcv_df: pl.DataFrame,
        definition_df: pl.DataFrame,
    ) -> pl.DataFrame:
        """Join Definition metadata to OHLCV data on instrument_id.

        Args:
            ohlcv_df: OHLCV DataFrame with instrument_id column
            definition_df: Definition DataFrame with metadata

        Returns:
            Enriched DataFrame with Definition columns added
        """
        if "instrument_id" not in ohlcv_df.columns:
            logger.warning(
                "databento_cannot_enrich",
                message="OHLCV DataFrame missing instrument_id column",
            )
            return ohlcv_df

        if "instrument_id" not in definition_df.columns:
            logger.warning(
                "databento_cannot_enrich",
                message="Definition DataFrame missing instrument_id column",
            )
            return ohlcv_df

        # Get key fields from Definition
        def_key = self._get_definition_key_fields(definition_df)

        # Ensure instrument_id types match for join
        ohlcv_df = ohlcv_df.with_columns(pl.col("instrument_id").cast(pl.Int64))
        def_key = def_key.with_columns(pl.col("instrument_id").cast(pl.Int64))

        # Remove duplicates from Definition (take first occurrence per instrument_id)
        def_key = def_key.unique(subset=["instrument_id"], keep="first")

        # Columns to add (exclude instrument_id since it's the join key)
        # Also exclude columns that already exist in OHLCV
        cols_to_add = [
            col for col in def_key.columns if col != "instrument_id" and col not in ohlcv_df.columns
        ]
        def_to_join = def_key.select(["instrument_id"] + cols_to_add)

        # Left join to preserve all OHLCV rows
        enriched_df = ohlcv_df.join(def_to_join, on="instrument_id", how="left")

        # Log join statistics
        matched = (
            enriched_df.filter(pl.col(cols_to_add[0]).is_not_null()).height
            if cols_to_add
            else len(enriched_df)
        )
        unmatched = len(enriched_df) - matched

        logger.info(
            "databento_ohlcv_enriched",
            total_rows=len(enriched_df),
            matched_rows=matched,
            unmatched_rows=unmatched,
            columns_added=cols_to_add,
        )

        return enriched_df

    def cleanup_definition(self) -> None:
        """Cleanup Definition temporary directory if created."""
        if hasattr(self, "_definition_temp_dir") and self._definition_temp_dir is not None:
            if self._definition_temp_dir.exists():
                try:
                    shutil.rmtree(self._definition_temp_dir, ignore_errors=False)
                    logger.info(
                        "databento_definition_temp_dir_cleaned_up",
                        path=str(self._definition_temp_dir),
                    )
                    self._definition_temp_dir = None
                except Exception as e:
                    logger.warning(
                        "databento_definition_cleanup_failed",
                        path=str(self._definition_temp_dir),
                        error=str(e),
                    )

    def _apply_definition_enrichment(
        self,
        df: pl.DataFrame,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> tuple[pl.DataFrame, list[str]]:
        """Apply Definition enrichment to OHLCV DataFrame.

        This method:
        1. Detects Definition type (CME date-split or NASDAQ symbol-split)
        2. Loads Definition data appropriately for the package type
        3. Applies UDS filtering if include_user_defined_spreads=False (CME only)
        4. Enriches OHLCV data with Definition metadata
        5. Creates composite instrument IDs for cross-exchange collision prevention

        Args:
            df: OHLCV DataFrame to enrich
            start: Start timestamp of date range
            end: End timestamp of date range

        Returns:
            Tuple of (enriched DataFrame, list of columns added)
        """
        if "instrument_id" not in df.columns:
            logger.warning(
                "databento_enrichment_skipped",
                message="OHLCV data missing instrument_id column; cannot enrich with Definition",
            )
            return df, []

        # Parse Definition metadata to determine split strategy
        def_metadata = self._parse_definition_metadata()
        if def_metadata is None:
            logger.warning(
                "databento_no_definition_metadata",
                message="Could not parse Definition metadata; proceeding without enrichment",
            )
            return df, []

        combined_definition: pl.DataFrame | None = None

        # NASDAQ: Symbol-split strategy - use pre-cached data if available
        if def_metadata.split_symbols:
            # OPTIMIZATION: Use pre-cached Definition data if available
            # This avoids re-parsing thousands of files for each batch
            if self._definition_data_cache is not None:
                # Filter cached data to only instrument_ids in this batch
                batch_instrument_ids = df["instrument_id"].unique().to_list()
                combined_definition = self._definition_data_cache.filter(
                    pl.col("instrument_id").is_in(batch_instrument_ids)
                )
                logger.debug(
                    "databento_using_cached_definition",
                    batch_instruments=len(batch_instrument_ids),
                    matched_definitions=len(combined_definition),
                )
            else:
                # Fallback: Load by symbols (slower, used when cache not pre-loaded)
                # Get unique symbols from OHLCV data
                if "original_symbol" in df.columns:
                    symbols = df["original_symbol"].unique().to_list()
                elif "symbol" in df.columns:
                    # Extract base symbol from composite (e.g., "AAPL_13" -> "AAPL")
                    symbols = []
                    for sym in df["symbol"].unique().to_list():
                        if "_" in str(sym):
                            base_sym = str(sym).rsplit("_", 1)[0]
                            symbols.append(base_sym)
                        else:
                            symbols.append(str(sym))
                    symbols = list(set(symbols))
                else:
                    symbols = []

                if symbols:
                    combined_definition = self._load_definition_for_symbols(symbols)

        # CME: Date-split strategy - load by dates
        elif def_metadata.split_duration == "day":
            # Get unique dates from the OHLCV data
            if "timestamp" in df.columns:
                unique_dates = (
                    df.select(pl.col("timestamp").dt.date().unique()).to_series().to_list()
                )
            else:
                # Fall back to date range
                unique_dates = pd.date_range(start, end, freq="D").tolist()

            # Load Definition data for all dates
            definition_dfs = []
            for date in unique_dates:
                if isinstance(date, pd.Timestamp):
                    date_ts = date
                else:
                    date_ts = pd.Timestamp(date)

                def_df = self._load_definition_for_date(date_ts)
                if def_df is not None:
                    definition_dfs.append(def_df)

            if definition_dfs:
                # Use how="diagonal_relaxed" to handle schema mismatches across dates
                # (some columns may have different types across files)
                combined_definition = pl.concat(definition_dfs, how="diagonal_relaxed")

        if combined_definition is None or len(combined_definition) == 0:
            logger.warning(
                "databento_no_definition_data",
                message="No Definition data found; proceeding without enrichment",
                split_strategy="symbol" if def_metadata.split_symbols else "day",
            )
            return df, []

        # Remove duplicates (keep most recent by ts_event if available)
        if "ts_event" in combined_definition.columns:
            combined_definition = combined_definition.sort("ts_event", descending=True)
        combined_definition = combined_definition.unique(subset=["instrument_id"], keep="first")

        # Detect schema type for logging
        schema_type = self._detect_definition_schema(combined_definition)

        logger.info(
            "databento_definition_loaded",
            total_instruments=len(combined_definition),
            schema_type=schema_type,
        )

        # Apply UDS filtering if requested (only relevant for CME)
        if not self.config.include_user_defined_spreads and schema_type == "CME":
            original_count = len(df)

            # Get instrument_ids that are UDS
            uds_filter_cols = []
            if "user_defined_instrument" in combined_definition.columns:
                uds_filter_cols.append(pl.col("user_defined_instrument") == "Y")
            if "instrument_class" in combined_definition.columns:
                uds_filter_cols.append(pl.col("instrument_class") == "T")

            if uds_filter_cols:
                filter_expr = uds_filter_cols[0]
                for cond in uds_filter_cols[1:]:
                    filter_expr = filter_expr | cond

                uds_instruments = combined_definition.filter(filter_expr)

                if len(uds_instruments) > 0:
                    uds_ids = set(uds_instruments["instrument_id"].to_list())

                    # Filter OHLCV data to exclude UDS
                    df = df.filter(~pl.col("instrument_id").is_in(list(uds_ids)))

                    filtered_count = original_count - len(df)
                    logger.info(
                        "databento_uds_filtered_from_ohlcv",
                        original_rows=original_count,
                        filtered_rows=filtered_count,
                        remaining_rows=len(df),
                        uds_instruments_excluded=len(uds_ids),
                    )

        # Enrich OHLCV with Definition metadata
        enriched_df = self._enrich_ohlcv_with_definition(df, combined_definition)

        # Create composite instrument IDs for cross-exchange collision prevention
        # This adds a composite_instrument_id column with format: {exchange}_{instrument_id}
        if "exchange" in enriched_df.columns:
            enriched_df = self._create_composite_instrument_id(enriched_df)

        # Determine which columns were added
        original_cols = set(df.columns)
        new_cols = [col for col in enriched_df.columns if col not in original_cols]

        return enriched_df, new_cols

    async def fetch(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from Databento package.

        Args:
            symbols: List of symbols to fetch (empty list = all symbols)
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution (extracted from filename, not used for filtering)

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            InvalidDataError: If data parsing fails
        """
        logger.info(
            "databento_fetch",
            symbols=symbols if symbols else "all",
            start=str(start),
            end=str(end),
            frequency=frequency,
        )

        # Parse OHLCV with filters
        df = await asyncio.to_thread(
            self._parse_ohlcv_csv,
            symbols_filter=symbols if symbols else None,
            start=start,
            end=end,
        )

        return df

    def _ingest_to_bundle_batched(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        batch_size: int,
        ohlcv_files: list[Path],
        **kwargs: Any,
    ) -> None:
        """Memory-efficient batched ingestion for large datasets.

        Processes OHLCV files in batches, applying Definition enrichment per batch,
        and writes incrementally to the bundle.

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest (empty = all)
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution
            batch_size: Number of files per batch
            ohlcv_files: Pre-discovered list of OHLCV files
            **kwargs: Additional parameters
        """
        import gc

        logger.info(
            "databento_batched_ingest_start",
            bundle_name=bundle_name,
            symbols=symbols if symbols else "all",
            start=str(start),
            end=str(end),
            frequency=frequency,
            file_count=len(ohlcv_files),
            batch_size=batch_size,
            definition_package=self.config.definition_package_path is not None,
        )

        # Setup bundle directory and writer
        bundle_dir = data_path(["bundles", bundle_name])
        ensure_directory(bundle_dir)
        writer = ParquetWriter(bundle_dir)

        # Prepare source metadata
        metadata = self.get_metadata()
        source_metadata_base = {
            "source_type": metadata.source_type,
            "source_url": metadata.source_url,
            "api_version": metadata.api_version,
            "timezone": self.config.timezone,
        }

        # Track aggregated stats
        total_rows = 0
        all_symbols: set[str] = set()
        all_instrument_mappings: dict[str, dict] = {}
        all_extra_dfs: list[pl.DataFrame] = []
        definition_columns_added: list[str] = []

        # Determine frame type from frequency
        frame_type = "daily" if frequency in ["1d", "d", "daily"] else "minute"

        # OPTIMIZATION: Build Definition file index and pre-load Definition data ONCE
        # This prevents re-parsing thousands of Definition files for each batch
        if self.config.definition_package_path is not None:
            self._build_definition_file_index()
            # Pre-load ALL Definition data into memory cache
            # For NASDAQ (symbol-split), this loads all files once upfront
            # For CME (date-split), this returns None and per-date loading is used
            self._preload_all_definition_data()

        # Process files in batches
        total_batches = (len(ohlcv_files) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, len(ohlcv_files))
            batch_files = ohlcv_files[batch_start:batch_end]

            logger.info(
                "databento_processing_batch",
                batch=batch_idx + 1,
                total_batches=total_batches,
                files_in_batch=len(batch_files),
                progress=f"{batch_end}/{len(ohlcv_files)}",
            )

            try:
                # Parse this batch of OHLCV files
                df = self._parse_ohlcv_batch(
                    file_paths=batch_files,
                    symbols_filter=symbols if symbols else None,
                    start=start,
                    end=end,
                )

                if len(df) == 0:
                    logger.warning(
                        "databento_batch_empty",
                        batch=batch_idx + 1,
                    )
                    continue

                # Apply Definition enrichment for this batch
                # Uses pre-cached Definition data (NASDAQ) or per-date loading (CME)
                batch_definition_cols: list[str] = []
                if self.config.definition_package_path is not None:
                    df, batch_definition_cols = self._apply_definition_enrichment(df, start, end)
                    if batch_definition_cols and not definition_columns_added:
                        definition_columns_added = batch_definition_cols

                # Check for extra columns
                standard_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
                has_extra_columns = any(col not in standard_cols for col in df.columns)

                # Save extra columns for later
                if has_extra_columns:
                    extra_cols = [col for col in df.columns if col not in standard_cols]
                    df_extra = df.select(["timestamp", "symbol"] + extra_cols)
                    all_extra_dfs.append(df_extra)

                # Separate standard OHLCV
                df_ohlcv = df.select(standard_cols)

                # Get batch symbols
                batch_symbols = df_ohlcv["symbol"].unique().to_list()
                all_symbols.update(batch_symbols)

                # Build symbol map for this batch
                symbol_map = build_symbol_sid_map(
                    normalize_symbols(batch_symbols),
                    bundle_name=bundle_name,
                )

                # Prepare OHLCV frame
                df_prepared, _ = prepare_ohlcv_frame(df_ohlcv, symbol_map, frequency)

                # Update source metadata with batch symbols
                source_metadata = {
                    **source_metadata_base,
                    "symbols": list(symbol_map.keys()),
                    "symbol_map": symbol_map,
                }

                # Write batch to parquet (will merge with existing)
                if frame_type == "daily":
                    writer.write_daily_bars(
                        df_prepared,
                        bundle_name=bundle_name,
                        source_metadata=source_metadata,
                    )
                else:
                    writer.write_minute_bars(
                        df_prepared,
                        bundle_name=bundle_name,
                        source_metadata=source_metadata,
                    )

                # Collect instrument mappings
                if (
                    self.config.use_instrument_id
                    and "instrument_id" in df.columns
                    and "original_symbol" in df.columns
                ):
                    mapping_df = df.select(["instrument_id", "original_symbol", "symbol"]).unique()
                    for row in mapping_df.iter_rows(named=True):
                        all_instrument_mappings[str(row["instrument_id"])] = {
                            "original_symbol": row["original_symbol"],
                            "composite_symbol": row["symbol"],
                            "sid": symbol_map.get(row["symbol"]),
                        }

                total_rows += len(df)

                logger.info(
                    "databento_batch_complete",
                    batch=batch_idx + 1,
                    rows_in_batch=len(df),
                    total_rows=total_rows,
                    symbols_in_batch=len(batch_symbols),
                )

                # Cleanup: delete variables and run garbage collection
                del df, df_ohlcv, df_prepared
                if has_extra_columns:
                    del df_extra
                gc.collect()

                # Clean up decompressed files from this batch to save disk space
                self._cleanup_batch_files(batch_files)

            except Exception as e:
                logger.error(
                    "databento_batch_error",
                    batch=batch_idx + 1,
                    error=str(e),
                )
                # Continue with next batch
                continue

        # Write aggregated extra columns
        if all_extra_dfs:
            combined_extra = pl.concat(all_extra_dfs)
            extra_cols_list = [
                col for col in combined_extra.columns if col not in ["timestamp", "symbol"]
            ]
            metadata_path = Path(bundle_dir) / "metadata_columns.parquet"
            combined_extra.write_parquet(metadata_path, compression="zstd")
            logger.info(
                "databento_extra_columns_written",
                path=str(metadata_path),
                columns=extra_cols_list,
                rows=len(combined_extra),
            )
            del combined_extra, all_extra_dfs
            gc.collect()

        # Write aggregated instrument mappings
        if all_instrument_mappings:
            mapping_path = Path(bundle_dir) / "databento_instrument_mappings.json"
            with open(mapping_path, "w") as f:
                json.dump(all_instrument_mappings, f, indent=2)
            logger.info(
                "databento_instrument_mappings_written",
                path=str(mapping_path),
                instruments=len(all_instrument_mappings),
            )

        # Clear Definition cache to free memory
        if self._definition_data_cache is not None:
            del self._definition_data_cache
            self._definition_data_cache = None
            gc.collect()

        logger.info(
            "databento_batched_ingest_complete",
            bundle_name=bundle_name,
            total_rows=total_rows,
            total_symbols=len(all_symbols),
            total_batches=total_batches,
            definition_enriched=len(definition_columns_added) > 0,
            definition_columns=definition_columns_added if definition_columns_added else None,
        )

    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        batch_size: int = 100,
        **kwargs: Any,
    ) -> None:
        """Ingest Databento data into bundle.

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest (empty = all)
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution
            batch_size: Number of files to process per batch (default: 100).
                       Set to 0 to disable batching.
            **kwargs: Additional parameters

        Raises:
            InvalidDataError: If ingestion fails

        Note:
            If extra_columns are configured, they will be stored in a separate
            metadata parquet file: {bundle}/metadata_columns.parquet
            This ensures backward compatibility with existing bundles.

            If definition_package_path is configured, Definition metadata will be
            loaded and used to:
            - Filter out User-Defined Spreads (unless include_user_defined_spreads=True)
            - Enrich OHLCV data with contract specifications

            For large datasets (> batch_size files), batched processing is used
            to reduce memory consumption. Each batch is processed independently
            and written incrementally to the bundle.
        """
        # Check file count to determine if batching is needed
        ohlcv_files = self._find_all_ohlcv_files()
        file_count = len(ohlcv_files)

        # Use batched processing for large datasets
        if batch_size > 0 and file_count > batch_size:
            logger.info(
                "databento_using_batched_ingestion",
                file_count=file_count,
                batch_size=batch_size,
                total_batches=(file_count + batch_size - 1) // batch_size,
            )
            return self._ingest_to_bundle_batched(
                bundle_name=bundle_name,
                symbols=symbols,
                start=start,
                end=end,
                frequency=frequency,
                batch_size=batch_size,
                ohlcv_files=ohlcv_files,
                **kwargs,
            )

        logger.info(
            "databento_ingest_to_bundle",
            bundle_name=bundle_name,
            symbols=symbols if symbols else "all",
            start=str(start),
            end=str(end),
            frequency=frequency,
            extra_columns=self.config.extra_columns,
            definition_package=self.config.definition_package_path is not None,
            include_uds=self.config.include_user_defined_spreads,
        )

        # Fetch data (includes extra columns if configured)
        df = run_async(self.fetch(symbols, start, end, frequency))

        # ========================================================================
        # Definition Integration (Story 9.3)
        # ========================================================================

        # Check for graceful degradation: warn if UDS filter requested without Definition
        if (
            not self.config.include_user_defined_spreads
            and self.config.definition_package_path is None
        ):
            logger.warning(
                "databento_uds_filter_ignored",
                message="include_user_defined_spreads=False requires Definition package; ignoring filter",
            )

        # Load and apply Definition enrichment if configured
        definition_columns_added = []
        if self.config.definition_package_path is not None:
            df, definition_columns_added = self._apply_definition_enrichment(df, start, end)

        # ========================================================================
        # End Definition Integration
        # ========================================================================

        # Check if we have extra columns
        standard_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
        has_extra_columns = any(col not in standard_cols for col in df.columns)

        # Separate standard OHLCV from extra columns
        df_ohlcv = df.select(standard_cols)

        # Build symbol map for ingestion
        if symbols:
            symbol_list = normalize_symbols(symbols)
        else:
            symbol_list = normalize_symbols(df_ohlcv["symbol"].unique().to_list())

        symbol_map = build_symbol_sid_map(symbol_list, bundle_name=bundle_name)

        # Prepare OHLCV frame for ingestion
        df_prepared, frame_type = prepare_ohlcv_frame(df_ohlcv, symbol_map, frequency)

        # Write to bundle using ParquetWriter
        bundle_dir = data_path(["bundles", bundle_name])
        ensure_directory(bundle_dir)

        writer = ParquetWriter(bundle_dir)

        # Prepare source metadata
        metadata = self.get_metadata()
        source_metadata = {
            "source_type": metadata.source_type,
            "source_url": metadata.source_url,
            "api_version": metadata.api_version,
            "symbols": list(symbol_map.keys()),
            "symbol_map": symbol_map,
            "timezone": self.config.timezone,
        }

        # Write based on frame type
        if frame_type == "daily":
            writer.write_daily_bars(
                df_prepared,
                bundle_name=bundle_name,
                source_metadata=source_metadata,
            )
        else:
            writer.write_minute_bars(
                df_prepared,
                bundle_name=bundle_name,
                source_metadata=source_metadata,
            )

        # Write extra columns to separate metadata file if present
        if has_extra_columns:
            extra_cols = [col for col in df.columns if col not in standard_cols]
            df_metadata = df.select(["timestamp", "symbol"] + extra_cols)

            metadata_path = Path(bundle_dir) / "metadata_columns.parquet"
            df_metadata.write_parquet(
                metadata_path,
                compression="zstd",
            )

            logger.info(
                "databento_extra_columns_written",
                path=str(metadata_path),
                columns=extra_cols,
                rows=len(df_metadata),
            )

        # Write instrument mappings if using instrument_id
        if (
            self.config.use_instrument_id
            and "instrument_id" in df.columns
            and "original_symbol" in df.columns
        ):
            instrument_mappings = {}
            mapping_df = df.select(
                ["instrument_id", "original_symbol", "symbol"]  # composite identifier
            ).unique()

            for row in mapping_df.iter_rows(named=True):
                instrument_mappings[str(row["instrument_id"])] = {
                    "original_symbol": row["original_symbol"],
                    "composite_symbol": row["symbol"],
                    "sid": symbol_map.get(row["symbol"]),
                }

            mapping_path = Path(bundle_dir) / "databento_instrument_mappings.json"
            with open(mapping_path, "w") as f:
                json.dump(instrument_mappings, f, indent=2)

            logger.info(
                "databento_instrument_mappings_written",
                path=str(mapping_path),
                instruments=len(instrument_mappings),
            )

        logger.info(
            "databento_ingested",
            bundle_name=bundle_name,
            rows=len(df),
            symbols=len(df["symbol"].unique()),
            extra_columns_stored=has_extra_columns,
            instrument_mappings_stored=self.config.use_instrument_id
            and "instrument_id" in df.columns,
            definition_enriched=len(definition_columns_added) > 0,
            definition_columns=definition_columns_added if definition_columns_added else None,
        )

    def get_metadata(self) -> DataSourceMetadata:
        """Get Databento source metadata.

        Returns:
            DataSourceMetadata with Databento information
        """
        metadata = self._parse_metadata()

        # Extract frequency from schema (e.g., "ohlcv-1h" -> "1h")
        frequency = metadata.schema.split("-")[-1] if "-" in metadata.schema else "1d"

        return DataSourceMetadata(
            source_type="databento",
            source_url=str(self.data_path),
            api_version="1",
            supports_live=False,  # Historical data only
            rate_limit=None,  # File-based, no rate limit
            auth_required=False,
            data_delay=None,  # Historical data
            supported_frequencies=[frequency],  # Based on package schema
            additional_info={
                "dataset": metadata.dataset,
                "schema": metadata.schema,
                "symbols_count": len(metadata.symbols),
                "job_id": metadata.job_id,
            },
        )

    def supports_live(self) -> bool:
        """Check if Databento supports live streaming.

        Returns:
            False (Databento packages are historical data only)
        """
        return False

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider-specific format to RustyBT standard schema.

        Data is already standardized in _parse_ohlcv_csv() method through
        column renaming, timestamp parsing, and type conversion.

        Args:
            df: DataFrame in Databento format

        Returns:
            Standardized DataFrame (no additional changes needed)
        """
        return df
