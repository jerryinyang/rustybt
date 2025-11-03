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
    """

    data_path: str
    timezone: str = "UTC"
    extra_columns: list[str] | None = None
    use_instrument_id: bool = True
    symbol_format: str = "symbol_id"


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

    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs: Any,
    ) -> None:
        """Ingest Databento data into bundle.

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest (empty = all)
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution
            **kwargs: Additional parameters

        Raises:
            InvalidDataError: If ingestion fails

        Note:
            If extra_columns are configured, they will be stored in a separate
            metadata parquet file: {bundle}/metadata_columns.parquet
            This ensures backward compatibility with existing bundles.
        """
        logger.info(
            "databento_ingest_to_bundle",
            bundle_name=bundle_name,
            symbols=symbols if symbols else "all",
            start=str(start),
            end=str(end),
            frequency=frequency,
            extra_columns=self.config.extra_columns,
        )

        # Fetch data (includes extra columns if configured)
        df = run_async(self.fetch(symbols, start, end, frequency))

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
            writer.write_minute_bars(df_prepared)

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
