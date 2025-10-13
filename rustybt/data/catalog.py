"""Data catalog for bundle metadata queries and management.

DEPRECATED: This module is deprecated and will be removed in v2.0.
Use rustybt.data.bundles.metadata.BundleMetadata instead.
"""

import time
import warnings
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rustybt.assets.asset_db_schema import (
    ASSET_DB_VERSION,
    bundle_cache,
    bundle_metadata,
    cache_statistics,
)
from rustybt.data.bundles.metadata import BundleMetadata


class DataCatalog:
    """Catalog for querying bundle metadata and data quality metrics.

    .. deprecated:: 1.0
        Use :class:`rustybt.data.bundles.metadata.BundleMetadata` instead.
        DataCatalog will be removed in v2.0.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize data catalog.

        .. deprecated:: 1.0
            Use :class:`rustybt.data.bundles.metadata.BundleMetadata` instead.
            DataCatalog will be removed in v2.0.

        Args:
            db_path: Path to SQLite catalog database. If None, uses default location.
        """
        warnings.warn(
            "DataCatalog is deprecated and will be removed in v2.0. "
            "Use BundleMetadata from rustybt.data.bundles.metadata instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if db_path is None:
            from rustybt.utils.paths import zipline_root

            db_path = str(Path(zipline_root()) / f"assets-{ASSET_DB_VERSION}.db")

        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        BundleMetadata.set_db_path(db_path)

    def store_metadata(self, metadata: dict[str, Any]) -> None:
        """Store bundle metadata in catalog.

        Args:
        metadata: Metadata dictionary with required fields:
            - bundle_name: str
            - source_type: str
            Optional fields are forwarded to :func:`BundleMetadata.update`
            and may include source_url, api_version, data_version,
            checksum/file_checksum, timezone, etc.

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = ["bundle_name", "source_type"]
        missing_fields = [field for field in required_fields if field not in metadata]
        if missing_fields:
            raise ValueError(f"Missing required metadata fields: {missing_fields}")

        metadata_copy = metadata.copy()
        bundle_name = metadata_copy.pop("bundle_name")
        BundleMetadata.update(bundle_name, **metadata_copy)

    def get_bundle_metadata(self, bundle_name: str) -> dict[str, Any] | None:
        """Get metadata for a specific bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Dictionary with bundle metadata or None if not found
        """
        metadata = BundleMetadata.get(bundle_name)
        if metadata is None:
            return None

        fields = [
            "bundle_name",
            "source_type",
            "source_url",
            "api_version",
            "fetch_timestamp",
            "data_version",
            "checksum",
            "file_checksum",
            "file_size_bytes",
            "timezone",
            "created_at",
            "updated_at",
        ]

        return {key: metadata.get(key) for key in fields if key in metadata}

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
            - missing_days_list: Sequence of dates or JSON string
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

        metrics_copy = metrics.copy()
        bundle_name = metrics_copy.pop("bundle_name")
        BundleMetadata.update(bundle_name, **metrics_copy)

    def get_quality_metrics(self, bundle_name: str) -> dict[str, Any] | None:
        """Get most recent quality metrics for a bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Dictionary with quality metrics or None if not found
        """
        return BundleMetadata.get_quality_metrics(bundle_name)

    def list_bundles(
        self,
        source_type: str | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict[str, Any]]:
        """List all bundles with optional filtering.

        Args:
            source_type: Filter by source type (e.g., 'csv', 'yfinance')
            start_date: Filter bundles with data >= this date (Unix timestamp)
            end_date: Filter bundles with data <= this date (Unix timestamp)

        Returns:
            List of bundle metadata dictionaries with quality metrics
        """
        return BundleMetadata.list_bundles(
            source_type=source_type,
            start_date=start_date,
            end_date=end_date,
        )

    def delete_bundle_metadata(self, bundle_name: str) -> bool:
        """Delete bundle metadata and all associated quality metrics.

        Args:
            bundle_name: Name of the bundle to delete

        Returns:
            True if bundle was deleted, False if bundle not found
        """
        return BundleMetadata.delete(bundle_name)

    # ========================================================================
    # Cache Management Methods (Story 8.3: Smart Caching Layer)
    # ========================================================================

    def store_cache_metadata(self, metadata: dict[str, Any]) -> None:
        """Store cache entry metadata.

        Args:
            metadata: Cache metadata with required fields:
                - cache_key: str
                - bundle_name: str
                - bundle_path: str
                - fetch_timestamp: int
                - size_bytes: int
                - last_accessed: int
                And optional fields:
                - symbols: list[str] (will be JSON-encoded)
                - start: str
                - end: str
                - frequency: str
                - row_count: int

        Raises:
            ValueError: If required fields are missing
        """
        import json

        required_fields = [
            "cache_key",
            "bundle_name",
            "bundle_path",
            "fetch_timestamp",
            "size_bytes",
            "last_accessed",
        ]
        missing_fields = [field for field in required_fields if field not in metadata]
        if missing_fields:
            raise ValueError(f"Missing required cache metadata fields: {missing_fields}")

        with Session(self.engine) as session:
            # Check if cache entry already exists
            stmt = select(bundle_cache).where(bundle_cache.c.cache_key == metadata["cache_key"])
            existing = session.execute(stmt).fetchone()

            symbols_json = json.dumps(metadata.get("symbols", []))

            if existing:
                # Update existing cache entry
                update_stmt = (
                    bundle_cache.update()
                    .where(bundle_cache.c.cache_key == metadata["cache_key"])
                    .values(
                        bundle_name=metadata["bundle_name"],
                        bundle_path=metadata["bundle_path"],
                        symbols=symbols_json,
                        start=metadata.get("start"),
                        end=metadata.get("end"),
                        frequency=metadata.get("frequency"),
                        fetch_timestamp=metadata["fetch_timestamp"],
                        size_bytes=metadata["size_bytes"],
                        row_count=metadata.get("row_count"),
                        last_accessed=metadata["last_accessed"],
                    )
                )
                session.execute(update_stmt)
            else:
                # Insert new cache entry
                insert_stmt = bundle_cache.insert().values(
                    cache_key=metadata["cache_key"],
                    bundle_name=metadata["bundle_name"],
                    bundle_path=metadata["bundle_path"],
                    symbols=symbols_json,
                    start=metadata.get("start"),
                    end=metadata.get("end"),
                    frequency=metadata.get("frequency"),
                    fetch_timestamp=metadata["fetch_timestamp"],
                    size_bytes=metadata["size_bytes"],
                    row_count=metadata.get("row_count"),
                    last_accessed=metadata["last_accessed"],
                )
                session.execute(insert_stmt)

            session.commit()

    def find_cached_bundle(self, cache_key: str) -> dict[str, Any] | None:
        """Find cached bundle by cache key.

        Args:
            cache_key: Unique cache key

        Returns:
            Dictionary with cache metadata or None if not found

        Performance target: <10ms (via indexed lookup)
        """
        with Session(self.engine) as session:
            stmt = select(bundle_cache).where(bundle_cache.c.cache_key == cache_key)
            result = session.execute(stmt).fetchone()

            if result is None:
                return None

            import json

            return {
                "cache_key": result.cache_key,
                "bundle_name": result.bundle_name,
                "bundle_path": result.bundle_path,
                "symbols": json.loads(result.symbols) if result.symbols else [],
                "start": result.start,
                "end": result.end,
                "frequency": result.frequency,
                "fetch_timestamp": result.fetch_timestamp,
                "size_bytes": result.size_bytes,
                "row_count": result.row_count,
                "last_accessed": result.last_accessed,
            }

    def update_cache_access(self, cache_key: str) -> None:
        """Update last accessed timestamp for cache entry (LRU tracking).

        Args:
            cache_key: Cache key to update
        """
        current_time = int(time.time())

        with Session(self.engine) as session:
            update_stmt = (
                bundle_cache.update()
                .where(bundle_cache.c.cache_key == cache_key)
                .values(last_accessed=current_time)
            )
            session.execute(update_stmt)
            session.commit()

    def get_cache_size(self) -> int:
        """Get total cache size in bytes.

        Returns:
            Total size of all cache entries in bytes
        """
        with Session(self.engine) as session:
            stmt = select(sa.func.sum(bundle_cache.c.size_bytes))
            result = session.execute(stmt).scalar()
            return result or 0

    def get_lru_cache_entries(self) -> list[dict[str, Any]]:
        """Get cache entries ordered by LRU (oldest first).

        Returns:
            List of cache entry dicts ordered by last_accessed ASC

        Used by LRU eviction to remove oldest entries.
        """
        with Session(self.engine) as session:
            stmt = select(bundle_cache).order_by(bundle_cache.c.last_accessed.asc())
            results = session.execute(stmt).fetchall()

            entries = []
            for row in results:
                entries.append(
                    {
                        "cache_key": row.cache_key,
                        "bundle_name": row.bundle_name,
                        "bundle_path": row.bundle_path,
                        "size_bytes": row.size_bytes,
                        "last_accessed": row.last_accessed,
                    }
                )

            return entries

    def delete_cache_entry(self, cache_key: str) -> bool:
        """Delete cache entry metadata.

        Args:
            cache_key: Cache key to delete

        Returns:
            True if entry was deleted, False if not found
        """
        with Session(self.engine) as session:
            delete_stmt = bundle_cache.delete().where(bundle_cache.c.cache_key == cache_key)
            result = session.execute(delete_stmt)
            session.commit()

            return result.rowcount > 0

    def increment_cache_hits(self) -> None:
        """Increment cache hit count for today's statistics."""
        self._update_cache_stats("hit_count", 1)

    def increment_cache_misses(self) -> None:
        """Increment cache miss count for today's statistics."""
        self._update_cache_stats("miss_count", 1)

    def _update_cache_stats(self, field: str, increment: int) -> None:
        """Update cache statistics for today.

        Args:
            field: Field to increment (hit_count or miss_count)
            increment: Value to add
        """
        # Get today's date as Unix timestamp (day granularity)
        current_time = int(time.time())
        stat_date = current_time - (current_time % 86400)  # Round to day start

        with Session(self.engine) as session:
            # Check if entry exists for today
            stmt = select(cache_statistics).where(cache_statistics.c.stat_date == stat_date)
            existing = session.execute(stmt).fetchone()

            if existing:
                # Update existing stats
                update_stmt = (
                    cache_statistics.update()
                    .where(cache_statistics.c.stat_date == stat_date)
                    .values(**{field: getattr(existing, field) + increment})
                )
                session.execute(update_stmt)
            else:
                # Insert new stats entry
                insert_stmt = cache_statistics.insert().values(
                    stat_date=stat_date, **{field: increment}
                )
                session.execute(insert_stmt)

            session.commit()

    def get_cache_stats(self, days: int = 7) -> list[dict[str, Any]]:
        """Get cache statistics for the last N days.

        Args:
            days: Number of days to retrieve (default 7)

        Returns:
            List of cache statistics dicts ordered by date DESC
        """
        current_time = int(time.time())
        cutoff_date = current_time - (days * 86400)  # N days ago

        with Session(self.engine) as session:
            stmt = (
                select(cache_statistics)
                .where(cache_statistics.c.stat_date >= cutoff_date)
                .order_by(cache_statistics.c.stat_date.desc())
            )
            results = session.execute(stmt).fetchall()

            stats = []
            for row in results:
                total_requests = row.hit_count + row.miss_count
                hit_rate = (row.hit_count / total_requests * 100) if total_requests > 0 else 0.0

                stats.append(
                    {
                        "stat_date": row.stat_date,
                        "hit_count": row.hit_count,
                        "miss_count": row.miss_count,
                        "hit_rate": round(hit_rate, 2),
                        "total_size_mb": row.total_size_mb,
                        "avg_fetch_latency_ms": row.avg_fetch_latency_ms,
                    }
                )

            return stats

    # ========================================================================
    # Helper Methods for Migration Script (Story 8.4)
    # ========================================================================

    def count_bundles(self) -> int:
        """Count total number of bundles."""
        with Session(self.engine) as session:
            stmt = select(sa.func.count()).select_from(bundle_metadata)
            return session.execute(stmt).scalar() or 0

    def count_quality_metrics(self) -> int:
        """Count total number of quality metric records."""
        return BundleMetadata.count_quality_records()
