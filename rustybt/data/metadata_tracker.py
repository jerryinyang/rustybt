"""Metadata tracking for bundle ingestion."""

import time
from pathlib import Path
from typing import Any

import polars as pl
from exchange_calendars import ExchangeCalendar

from rustybt.data.catalog import DataCatalog
from rustybt.data.quality import calculate_quality_metrics
from rustybt.utils.checksum import calculate_checksum, calculate_checksum_multiple


class BundleMetadataTracker:
    """Tracks metadata and quality metrics during bundle ingestion."""

    def __init__(self, catalog: DataCatalog | None = None):
        """Initialize metadata tracker.

        Args:
            catalog: DataCatalog instance. If None, creates default catalog.
        """
        self.catalog = catalog if catalog is not None else DataCatalog()

    def record_bundle_ingestion(
        self,
        bundle_name: str,
        source_type: str,
        data_files: list[Path],
        data: pl.DataFrame | None = None,
        source_url: str | None = None,
        api_version: str | None = None,
        data_version: str | None = None,
        calendar: ExchangeCalendar | None = None,
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Record metadata and quality metrics for bundle ingestion.

        Args:
            bundle_name: Name of the bundle
            source_type: Type of data source (csv, yfinance, ccxt, etc.)
            data_files: List of data file paths used for ingestion
            data: Optional DataFrame with OHLCV data for quality analysis
            source_url: Optional URL or path to data source
            api_version: Optional API version identifier
            data_version: Optional data version identifier
            calendar: Optional exchange calendar for gap detection
            timezone: Timezone of data (default UTC)

        Returns:
            Dictionary with recorded metadata and quality metrics
        """
        # Calculate checksum of data files
        if len(data_files) == 1:
            checksum = calculate_checksum(data_files[0])
        else:
            checksum = calculate_checksum_multiple(data_files)

        # Record provenance metadata
        metadata = {
            "bundle_name": bundle_name,
            "source_type": source_type,
            "source_url": source_url,
            "api_version": api_version,
            "fetch_timestamp": int(time.time()),
            "data_version": data_version,
            "checksum": checksum,
            "timezone": timezone,
        }

        self.catalog.store_metadata(metadata)

        # Calculate and record quality metrics if data provided
        quality_metrics = None
        if data is not None:
            quality_metrics = calculate_quality_metrics(data, calendar=calendar)
            quality_metrics["bundle_name"] = bundle_name
            self.catalog.store_quality_metrics(quality_metrics)

        return {
            "metadata": metadata,
            "quality_metrics": quality_metrics,
        }

    def record_csv_bundle(
        self,
        bundle_name: str,
        csv_dir: Path,
        data: pl.DataFrame | None = None,
        calendar: ExchangeCalendar | None = None,
    ) -> dict[str, Any]:
        """Record metadata for CSV bundle ingestion.

        Args:
            bundle_name: Name of the bundle
            csv_dir: Directory containing CSV files
            data: Optional DataFrame with OHLCV data
            calendar: Optional exchange calendar

        Returns:
            Dictionary with recorded metadata and quality metrics
        """
        csv_dir = Path(csv_dir)

        # Find all CSV files in directory
        csv_files = sorted(csv_dir.glob("*.csv"))

        return self.record_bundle_ingestion(
            bundle_name=bundle_name,
            source_type="csv",
            data_files=csv_files,
            data=data,
            source_url=str(csv_dir),
            calendar=calendar,
        )

    def record_api_bundle(
        self,
        bundle_name: str,
        source_type: str,
        data_file: Path,
        data: pl.DataFrame | None = None,
        api_url: str | None = None,
        api_version: str | None = None,
        data_version: str | None = None,
        calendar: ExchangeCalendar | None = None,
    ) -> dict[str, Any]:
        """Record metadata for API-sourced bundle ingestion.

        Args:
            bundle_name: Name of the bundle
            source_type: Type of API source (yfinance, ccxt, etc.)
            data_file: Path to saved API data file
            data: Optional DataFrame with OHLCV data
            api_url: Optional API endpoint URL
            api_version: Optional API version
            data_version: Optional data version from API
            calendar: Optional exchange calendar

        Returns:
            Dictionary with recorded metadata and quality metrics
        """
        return self.record_bundle_ingestion(
            bundle_name=bundle_name,
            source_type=source_type,
            data_files=[Path(data_file)],
            data=data,
            source_url=api_url,
            api_version=api_version,
            data_version=data_version,
            calendar=calendar,
        )


def track_csv_bundle_metadata(
    bundle_name: str,
    csv_dir: str,
    data: pl.DataFrame | None = None,
    calendar: ExchangeCalendar | None = None,
) -> dict[str, Any]:
    """Convenience function to track CSV bundle metadata.

    Args:
        bundle_name: Name of the bundle
        csv_dir: Directory containing CSV files
        data: Optional DataFrame with OHLCV data
        calendar: Optional exchange calendar

    Returns:
        Dictionary with recorded metadata and quality metrics
    """
    tracker = BundleMetadataTracker()
    return tracker.record_csv_bundle(bundle_name, Path(csv_dir), data, calendar)


def track_api_bundle_metadata(
    bundle_name: str,
    source_type: str,
    data_file: str,
    data: pl.DataFrame | None = None,
    api_url: str | None = None,
    api_version: str | None = None,
    data_version: str | None = None,
    calendar: ExchangeCalendar | None = None,
) -> dict[str, Any]:
    """Convenience function to track API bundle metadata.

    Args:
        bundle_name: Name of the bundle
        source_type: Type of API source
        data_file: Path to saved API data file
        data: Optional DataFrame with OHLCV data
        api_url: Optional API endpoint URL
        api_version: Optional API version
        data_version: Optional data version
        calendar: Optional exchange calendar

    Returns:
        Dictionary with recorded metadata and quality metrics
    """
    tracker = BundleMetadataTracker()
    return tracker.record_api_bundle(
        bundle_name,
        source_type,
        Path(data_file),
        data,
        api_url,
        api_version,
        data_version,
        calendar,
    )
