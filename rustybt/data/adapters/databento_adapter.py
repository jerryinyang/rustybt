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


@dataclass
class DatabentoConfig:
    """Configuration for Databento adapter.

    Attributes:
        data_path: Path to Databento ZIP file or extracted folder
        timezone: Timezone for timestamps (default: UTC)
    """

    data_path: str
    timezone: str = "UTC"


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

    Implements both BaseDataAdapter and DataSource interfaces.

    Example:
        >>> config = DatabentoConfig(
        ...     data_path="/path/to/databento.zip"
        ... )
        >>> adapter = DatabentoAdapter(config)
        >>> df = await adapter.fetch(
        ...     symbols=[],  # All symbols
        ...     start=pd.Timestamp('2023-01-01'),
        ...     end=pd.Timestamp('2023-12-31'),
        ...     frequency='1h'
        ... )
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

        # Verify data path exists
        if not self.data_path.exists():
            raise FileNotFoundError(f"Databento data path not found: {self.data_path}")

        logger.info(
            "databento_adapter_initialized",
            data_path=str(self.data_path),
            is_zip=self._is_zip_file(),
            timezone=config.timezone,
        )

    def __del__(self) -> None:
        """Cleanup temporary directory if created."""
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
            )

            logger.info(
                "databento_metadata_parsed",
                dataset=metadata.dataset,
                schema=metadata.schema,
                symbols_count=len(metadata.symbols),
                start=metadata.start,
                end=metadata.end,
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

    def _find_ohlcv_file(self) -> Path:
        """Find OHLCV CSV file (compressed or uncompressed).

        Returns:
            Path to OHLCV file

        Raises:
            FileNotFoundError: If no OHLCV file found
        """
        working_dir = self._get_working_dir()

        # Look for .csv.zst file first
        zst_files = list(working_dir.glob("*.ohlcv-*.csv.zst"))
        if zst_files:
            return zst_files[0]

        # Look for uncompressed .csv file
        csv_files = list(working_dir.glob("*.ohlcv-*.csv"))
        if csv_files:
            return csv_files[0]

        raise FileNotFoundError(f"No OHLCV file found in {working_dir}")

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

    def _get_ohlcv_csv_path(self) -> Path:
        """Get path to decompressed OHLCV CSV file.

        Handles decompression if needed.

        Returns:
            Path to CSV file
        """
        ohlcv_file = self._find_ohlcv_file()

        # If already CSV, return it
        if ohlcv_file.suffix == ".csv":
            return ohlcv_file

        # Decompress zst file (check if ends with .zst)
        if ohlcv_file.suffix == ".zst" and ".csv" in ohlcv_file.suffixes:
            working_dir = self._get_working_dir()
            output_csv = working_dir / ohlcv_file.name.replace(".zst", "")

            # Check if already decompressed
            if output_csv.exists():
                return output_csv

            return self._decompress_zst(ohlcv_file, output_csv)

        raise InvalidDataError(f"Unknown OHLCV file format: {ohlcv_file}")

    def _parse_ohlcv_csv(
        self,
        symbols_filter: list[str] | None = None,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
    ) -> pl.DataFrame:
        """Parse OHLCV CSV to Polars DataFrame.

        Args:
            symbols_filter: Optional list of symbols to filter
            start: Optional start timestamp
            end: Optional end timestamp

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            InvalidDataError: If CSV parsing fails
        """
        csv_path = self._get_ohlcv_csv_path()

        try:
            logger.info("databento_parsing_ohlcv_csv", csv_path=str(csv_path))

            # Read CSV with Polars (disable auto date parsing to handle manually)
            df = pl.read_csv(
                csv_path,
                separator=",",
                has_header=True,
                try_parse_dates=False,  # Parse dates manually for control
            )

            logger.info(
                "databento_csv_read",
                rows=len(df),
                columns=len(df.columns),
            )

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

            # Filter by symbols if provided
            if symbols_filter:
                df = df.filter(pl.col("symbol").is_in(symbols_filter))

            # Filter by date range if provided
            if start is not None:
                start_utc = pd.Timestamp(start).tz_localize("UTC") if start.tz is None else start
                df = df.filter(pl.col("timestamp") >= start_utc)

            if end is not None:
                end_utc = pd.Timestamp(end).tz_localize("UTC") if end.tz is None else end
                df = df.filter(pl.col("timestamp") <= end_utc)

            # Select only required columns
            df = df.select(["timestamp", "symbol", "open", "high", "low", "close", "volume"])

            logger.info(
                "databento_ohlcv_parsed",
                rows=len(df),
                symbols=len(df["symbol"].unique()),
            )

            return df

        except Exception as e:
            raise InvalidDataError(f"Failed to parse OHLCV CSV: {e}") from e

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
        """
        logger.info(
            "databento_ingest_to_bundle",
            bundle_name=bundle_name,
            symbols=symbols if symbols else "all",
            start=str(start),
            end=str(end),
            frequency=frequency,
        )

        # Fetch data
        df = run_async(self.fetch(symbols, start, end, frequency))

        # Prepare OHLCV frame for ingestion
        df_prepared = prepare_ohlcv_frame(df)

        # Write to bundle using ParquetWriter
        bundle_dir = data_path(["bundles", bundle_name])
        ensure_directory(bundle_dir)

        writer = ParquetWriter(bundle_dir)
        writer.write(df_prepared)

        logger.info(
            "databento_ingested",
            bundle_name=bundle_name,
            rows=len(df),
            symbols=len(df["symbol"].unique()),
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
