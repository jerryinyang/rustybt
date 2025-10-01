"""Data catalog for bundle metadata queries and management."""

import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rustybt.assets.asset_db_schema import bundle_metadata, data_quality_metrics


class DataCatalog:
    """Catalog for querying bundle metadata and data quality metrics."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize data catalog.

        Args:
            db_path: Path to SQLite catalog database. If None, uses default location.
        """
        if db_path is None:
            from rustybt.utils.paths import zipline_root

            db_path = str(Path(zipline_root()) / "assets-8.db")

        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")

    def store_metadata(self, metadata: dict[str, Any]) -> None:
        """Store bundle metadata in catalog.

        Args:
            metadata: Metadata dictionary with required fields:
                - bundle_name: str
                - source_type: str
                - checksum: str
                - fetch_timestamp: int (Unix timestamp)
                And optional fields:
                - source_url: str
                - api_version: str
                - data_version: str
                - timezone: str (default 'UTC')

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = ["bundle_name", "source_type", "checksum", "fetch_timestamp"]
        missing_fields = [field for field in required_fields if field not in metadata]
        if missing_fields:
            raise ValueError(f"Missing required metadata fields: {missing_fields}")

        current_time = int(time.time())

        with Session(self.engine) as session:
            # Check if bundle already exists
            stmt = select(bundle_metadata).where(
                bundle_metadata.c.bundle_name == metadata["bundle_name"]
            )
            existing = session.execute(stmt).fetchone()

            if existing:
                # Update existing metadata
                update_stmt = (
                    bundle_metadata.update()
                    .where(bundle_metadata.c.bundle_name == metadata["bundle_name"])
                    .values(
                        source_type=metadata["source_type"],
                        source_url=metadata.get("source_url"),
                        api_version=metadata.get("api_version"),
                        fetch_timestamp=metadata["fetch_timestamp"],
                        data_version=metadata.get("data_version"),
                        checksum=metadata["checksum"],
                        timezone=metadata.get("timezone", "UTC"),
                        updated_at=current_time,
                    )
                )
                session.execute(update_stmt)
            else:
                # Insert new metadata
                insert_stmt = bundle_metadata.insert().values(
                    bundle_name=metadata["bundle_name"],
                    source_type=metadata["source_type"],
                    source_url=metadata.get("source_url"),
                    api_version=metadata.get("api_version"),
                    fetch_timestamp=metadata["fetch_timestamp"],
                    data_version=metadata.get("data_version"),
                    checksum=metadata["checksum"],
                    timezone=metadata.get("timezone", "UTC"),
                    created_at=current_time,
                    updated_at=current_time,
                )
                session.execute(insert_stmt)

            session.commit()

    def get_bundle_metadata(self, bundle_name: str) -> Optional[dict[str, Any]]:
        """Get metadata for a specific bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Dictionary with bundle metadata or None if not found
        """
        with Session(self.engine) as session:
            stmt = select(bundle_metadata).where(bundle_metadata.c.bundle_name == bundle_name)
            result = session.execute(stmt).fetchone()

            if result is None:
                return None

            return {
                "bundle_name": result.bundle_name,
                "source_type": result.source_type,
                "source_url": result.source_url,
                "api_version": result.api_version,
                "fetch_timestamp": result.fetch_timestamp,
                "data_version": result.data_version,
                "checksum": result.checksum,
                "timezone": result.timezone,
                "created_at": result.created_at,
                "updated_at": result.updated_at,
            }

    def store_quality_metrics(self, metrics: dict[str, Any]) -> None:
        """Store data quality metrics in catalog.

        Args:
            metrics: Quality metrics dictionary with required fields:
                - bundle_name: str
                - row_count: int
                - start_date: int (Unix timestamp)
                - end_date: int (Unix timestamp)
                - validation_timestamp: int (Unix timestamp)
                And optional fields:
                - missing_days_count: int
                - missing_days_list: str (JSON)
                - outlier_count: int
                - ohlcv_violations: int
                - validation_passed: bool

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = [
            "bundle_name",
            "row_count",
            "start_date",
            "end_date",
            "validation_timestamp",
        ]
        missing_fields = [field for field in required_fields if field not in metrics]
        if missing_fields:
            raise ValueError(f"Missing required quality metric fields: {missing_fields}")

        with Session(self.engine) as session:
            insert_stmt = data_quality_metrics.insert().values(
                bundle_name=metrics["bundle_name"],
                row_count=metrics["row_count"],
                start_date=metrics["start_date"],
                end_date=metrics["end_date"],
                missing_days_count=metrics.get("missing_days_count", 0),
                missing_days_list=metrics.get("missing_days_list", "[]"),
                outlier_count=metrics.get("outlier_count", 0),
                ohlcv_violations=metrics.get("ohlcv_violations", 0),
                validation_timestamp=metrics["validation_timestamp"],
                validation_passed=metrics.get("validation_passed", True),
            )
            session.execute(insert_stmt)
            session.commit()

    def get_quality_metrics(self, bundle_name: str) -> Optional[dict[str, Any]]:
        """Get most recent quality metrics for a bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Dictionary with quality metrics or None if not found
        """
        with Session(self.engine) as session:
            stmt = (
                select(data_quality_metrics)
                .where(data_quality_metrics.c.bundle_name == bundle_name)
                .order_by(data_quality_metrics.c.validation_timestamp.desc())
                .limit(1)
            )
            result = session.execute(stmt).fetchone()

            if result is None:
                return None

            return {
                "bundle_name": result.bundle_name,
                "row_count": result.row_count,
                "start_date": result.start_date,
                "end_date": result.end_date,
                "missing_days_count": result.missing_days_count,
                "missing_days_list": result.missing_days_list,
                "outlier_count": result.outlier_count,
                "ohlcv_violations": result.ohlcv_violations,
                "validation_timestamp": result.validation_timestamp,
                "validation_passed": result.validation_passed,
            }

    def list_bundles(
        self,
        source_type: Optional[str] = None,
        start_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """List all bundles with optional filtering.

        Args:
            source_type: Filter by source type (e.g., 'csv', 'yfinance')
            start_date: Filter bundles with data >= this date (Unix timestamp)
            end_date: Filter bundles with data <= this date (Unix timestamp)

        Returns:
            List of bundle metadata dictionaries with quality metrics
        """
        with Session(self.engine) as session:
            # Build query with joins
            stmt = (
                select(
                    bundle_metadata.c.bundle_name,
                    bundle_metadata.c.source_type,
                    bundle_metadata.c.source_url,
                    bundle_metadata.c.fetch_timestamp,
                    bundle_metadata.c.checksum,
                    data_quality_metrics.c.row_count,
                    data_quality_metrics.c.start_date,
                    data_quality_metrics.c.end_date,
                    data_quality_metrics.c.validation_passed,
                )
                .select_from(
                    bundle_metadata.outerjoin(
                        data_quality_metrics,
                        bundle_metadata.c.bundle_name == data_quality_metrics.c.bundle_name,
                    )
                )
                .distinct()
            )

            # Apply filters
            if source_type:
                stmt = stmt.where(bundle_metadata.c.source_type == source_type)

            if start_date:
                stmt = stmt.where(data_quality_metrics.c.start_date >= start_date)

            if end_date:
                stmt = stmt.where(data_quality_metrics.c.end_date <= end_date)

            results = session.execute(stmt).fetchall()

            bundles = []
            for row in results:
                bundles.append(
                    {
                        "bundle_name": row.bundle_name,
                        "source_type": row.source_type,
                        "source_url": row.source_url,
                        "fetch_timestamp": row.fetch_timestamp,
                        "checksum": row.checksum,
                        "row_count": row.row_count,
                        "start_date": row.start_date,
                        "end_date": row.end_date,
                        "validation_passed": row.validation_passed,
                    }
                )

            return bundles

    def delete_bundle_metadata(self, bundle_name: str) -> bool:
        """Delete bundle metadata and all associated quality metrics.

        Args:
            bundle_name: Name of the bundle to delete

        Returns:
            True if bundle was deleted, False if bundle not found
        """
        with Session(self.engine) as session:
            # Delete quality metrics first (foreign key constraint)
            delete_quality = data_quality_metrics.delete().where(
                data_quality_metrics.c.bundle_name == bundle_name
            )
            session.execute(delete_quality)

            # Delete metadata
            delete_metadata = bundle_metadata.delete().where(
                bundle_metadata.c.bundle_name == bundle_name
            )
            result = session.execute(delete_metadata)

            session.commit()

            return result.rowcount > 0
