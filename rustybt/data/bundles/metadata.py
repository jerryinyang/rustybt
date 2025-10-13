"""Unified bundle metadata management."""

import json
import time
from pathlib import Path
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rustybt.assets.asset_db_schema import (
    ASSET_DB_VERSION,
    bundle_cache,
    bundle_metadata,
    bundle_symbols,
)
from rustybt.assets.asset_db_schema import (
    metadata as schema_metadata,
)

logger = structlog.get_logger(__name__)


class BundleMetadata:
    """Unified metadata catalog for bundles.

    Merges functionality from DataCatalog and ParquetMetadataCatalog into a single
    metadata system with:
    - Provenance tracking (source, API version, fetch timestamp)
    - Quality metrics (row count, OHLCV violations, validation status)
    - Symbol tracking (asset type, exchange)
    - Cache management (LRU eviction, statistics)
    - File metadata (checksums, sizes)

    All metadata is stored in a single SQLite database with proper foreign key
    relationships and indexes for performance.

    Example:
        >>> # Update bundle with provenance and quality
        >>> BundleMetadata.update(
        ...     bundle_name="yfinance-daily",
        ...     source_type="yfinance",
        ...     source_url="https://...",
        ...     row_count=12000,
        ...     ohlcv_violations=0,
        ... )
        >>>
        >>> # Add symbols to bundle
        >>> BundleMetadata.add_symbol("yfinance-daily", "AAPL", "equity", "NASDAQ")
        >>>
        >>> # Query metadata
        >>> metadata = BundleMetadata.get("yfinance-daily")
    """

    _db_path: str | None = None
    _engine = None

    _FIELD_NAMES = {
        "source_type",
        "source_url",
        "api_version",
        "fetch_timestamp",
        "data_version",
        "timezone",
        "row_count",
        "start_date",
        "end_date",
        "missing_days_count",
        "missing_days_list",
        "outlier_count",
        "ohlcv_violations",
        "validation_passed",
        "validation_timestamp",
        "file_checksum",
        "file_size_bytes",
        "checksum",
    }

    _INT_FIELDS = {
        "fetch_timestamp",
        "row_count",
        "start_date",
        "end_date",
        "missing_days_count",
        "outlier_count",
        "ohlcv_violations",
        "validation_timestamp",
        "file_size_bytes",
    }

    _JSON_FIELDS = {"missing_days_list"}

    @classmethod
    def _get_engine(cls) -> sa.engine.Engine:
        """Get or create SQLAlchemy engine."""
        if cls._engine is None:
            if cls._db_path is None:
                from rustybt.utils.paths import zipline_root

                cls._db_path = str(Path(zipline_root()) / f"assets-{ASSET_DB_VERSION}.db")

            cls._engine = create_engine(f"sqlite:///{cls._db_path}")

            # Create tables if they don't exist
            schema_metadata.create_all(cls._engine)

        return cls._engine

    @classmethod
    def set_db_path(cls, db_path: str) -> None:
        """Set custom database path (useful for testing).

        Args:
            db_path: Path to SQLite database
        """
        cls._db_path = db_path
        cls._engine = None  # Force recreation with new path

    # ========================================================================
    # Core Metadata Methods (merged from DataCatalog)
    # ========================================================================

    @classmethod
    def _normalize_metadata(cls, metadata: dict[str, Any]) -> dict[str, Any]:
        """Normalize metadata payload for storage."""
        normalized: dict[str, Any] = {}

        for key, value in metadata.items():
            if key not in cls._FIELD_NAMES:
                continue

            if value is None:
                normalized[key] = None
                continue

            if key in cls._INT_FIELDS:
                try:
                    normalized[key] = int(value)
                except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                    raise ValueError(f"Field '{key}' must be an integer-compatible value") from exc
            elif key in cls._JSON_FIELDS:
                if isinstance(value, str):
                    normalized[key] = value
                else:
                    normalized[key] = json.dumps(list(value))
            elif key == "validation_passed":
                normalized[key] = bool(value)
            else:
                normalized[key] = value

        if "file_checksum" in normalized and "checksum" not in normalized:
            normalized["checksum"] = normalized["file_checksum"]
        if "checksum" in normalized and "file_checksum" not in normalized:
            normalized["file_checksum"] = normalized["checksum"]

        return normalized

    @classmethod
    def update(cls, bundle_name: str, **metadata: Any) -> None:
        """Update bundle metadata (provenance, quality, file metadata).

        This method accepts all metadata fields from the merged schema:
        - Provenance: source_type, source_url, api_version, fetch_timestamp, etc.
        - Quality: row_count, ohlcv_violations, validation_passed, etc.
        - File: file_checksum, file_size_bytes

        Args:
            bundle_name: Name of the bundle
            **metadata: Metadata fields to update

        Example:
            >>> BundleMetadata.update(
            ...     bundle_name="test-bundle",
            ...     source_type="yfinance",
            ...     source_url="https://...",
            ...     api_version="v8",
            ...     fetch_timestamp=int(time.time()),
            ...     row_count=1000,
            ...     ohlcv_violations=0,
            ...     validation_passed=True,
            ... )
        """
        engine = cls._get_engine()
        current_time = int(time.time())

        normalized = cls._normalize_metadata(metadata)

        with Session(engine) as session:
            stmt = (
                select(bundle_metadata).where(bundle_metadata.c.bundle_name == bundle_name).limit(1)
            )
            existing = session.execute(stmt).fetchone()

            if existing:
                update_values = {**normalized}
                update_values["updated_at"] = current_time

                if update_values:
                    session.execute(
                        bundle_metadata.update()
                        .where(bundle_metadata.c.bundle_name == bundle_name)
                        .values(**update_values)
                    )
            else:
                if "source_type" not in normalized:
                    raise ValueError(
                        "'source_type' is required when creating new bundle metadata entry"
                    )

                source_type = normalized.pop("source_type")
                fetch_timestamp = normalized.pop("fetch_timestamp", current_time)
                if fetch_timestamp is None:
                    fetch_timestamp = current_time

                insert_values = {
                    "bundle_name": bundle_name,
                    "source_type": source_type,
                    "fetch_timestamp": fetch_timestamp,
                    "created_at": current_time,
                    "updated_at": current_time,
                }

                # Default values for newly introduced quality fields
                insert_defaults = {
                    "timezone": "UTC",
                    "missing_days_count": 0,
                    "missing_days_list": "[]",
                    "outlier_count": 0,
                    "ohlcv_violations": 0,
                    "validation_passed": True,
                }

                for key, value in insert_defaults.items():
                    if key not in normalized or normalized[key] is None:
                        insert_values[key] = value

                # Merge remaining normalized values (excluding defaults already handled)
                for key, value in normalized.items():
                    if value is not None:
                        insert_values[key] = value

                session.execute(bundle_metadata.insert().values(**insert_values))

            session.commit()

        logger.info(
            "bundle_metadata_updated",
            bundle_name=bundle_name,
            fields_updated=list(metadata.keys()),
        )

    @classmethod
    def get(cls, bundle_name: str) -> dict[str, Any] | None:
        """Get complete metadata for a bundle.

        Returns merged view of bundle metadata and latest quality metrics.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Dictionary with all metadata fields or None if not found

        Example:
            >>> metadata = BundleMetadata.get("yfinance-daily")
            >>> print(metadata['source_type'])
            'yfinance'
            >>> print(metadata['row_count'])
            12000
        """
        engine = cls._get_engine()

        with Session(engine) as session:
            # Get bundle metadata
            stmt = (
                select(bundle_metadata).where(bundle_metadata.c.bundle_name == bundle_name).limit(1)
            )
            row = session.execute(stmt).mappings().fetchone()

            if row is None:
                return None

            result = dict(row)
            result.pop("id", None)

            missing_days = result.get("missing_days_list")
            if isinstance(missing_days, str) and missing_days:
                try:
                    result["missing_days_list"] = json.loads(missing_days)
                except json.JSONDecodeError:
                    # Leave as original string if decoding fails
                    pass

            return result

    @classmethod
    def list_bundles(
        cls,
        source_type: str | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict[str, Any]]:
        """List all bundles with optional filtering.

        Args:
            source_type: Optional filter by source type
            start_date: Optional filter by minimum data start timestamp
            end_date: Optional filter by maximum data end timestamp

        Returns:
            List of bundle metadata dictionaries

        Example:
            >>> bundles = BundleMetadata.list_bundles(source_type="yfinance")
            >>> for bundle in bundles:
            ...     print(f"{bundle['bundle_name']}: {bundle['row_count']} rows")
        """
        engine = cls._get_engine()

        with Session(engine) as session:
            stmt = select(
                bundle_metadata.c.bundle_name,
                bundle_metadata.c.source_type,
                bundle_metadata.c.source_url,
                bundle_metadata.c.fetch_timestamp,
                bundle_metadata.c.checksum,
                bundle_metadata.c.file_checksum,
                bundle_metadata.c.file_size_bytes,
                bundle_metadata.c.row_count,
                bundle_metadata.c.start_date,
                bundle_metadata.c.end_date,
                bundle_metadata.c.validation_passed,
            )

            if source_type:
                stmt = stmt.where(bundle_metadata.c.source_type == source_type)

            if start_date is not None:
                stmt = stmt.where(bundle_metadata.c.start_date >= start_date)

            if end_date is not None:
                stmt = stmt.where(bundle_metadata.c.end_date <= end_date)

            results = session.execute(stmt).fetchall()

            return [
                {
                    "bundle_name": row.bundle_name,
                    "source_type": row.source_type,
                    "source_url": row.source_url,
                    "fetch_timestamp": row.fetch_timestamp,
                    "checksum": row.checksum,
                    "file_checksum": row.file_checksum,
                    "file_size_bytes": row.file_size_bytes,
                    "row_count": row.row_count,
                    "start_date": row.start_date,
                    "end_date": row.end_date,
                    "validation_passed": row.validation_passed,
                }
                for row in results
            ]

    @classmethod
    def delete(cls, bundle_name: str) -> bool:
        """Delete bundle and all associated metadata.

        Args:
            bundle_name: Name of bundle to delete

        Returns:
            True if deleted, False if not found
        """
        engine = cls._get_engine()

        with Session(engine) as session:
            # Delete cache entries
            delete_cache = bundle_cache.delete().where(bundle_cache.c.bundle_name == bundle_name)
            session.execute(delete_cache)

            # Delete associated symbols
            delete_symbols = bundle_symbols.delete().where(
                bundle_symbols.c.bundle_name == bundle_name
            )
            session.execute(delete_symbols)

            # Delete bundle metadata
            delete_bundle = bundle_metadata.delete().where(
                bundle_metadata.c.bundle_name == bundle_name
            )
            result = session.execute(delete_bundle)

            session.commit()

            return result.rowcount > 0

    # ========================================================================
    # Symbol Tracking Methods (merged from ParquetMetadataCatalog)
    # ========================================================================

    @classmethod
    def add_symbol(
        cls,
        bundle_name: str,
        symbol: str,
        asset_type: str | None = None,
        exchange: str | None = None,
    ) -> int:
        """Add symbol to bundle.

        Args:
            bundle_name: Bundle name
            symbol: Symbol string
            asset_type: Asset type ('equity', 'crypto', etc.)
            exchange: Exchange name

        Returns:
            Symbol ID

        Example:
            >>> BundleMetadata.add_symbol("yfinance-daily", "AAPL", "equity", "NASDAQ")
        """
        engine = cls._get_engine()

        with Session(engine) as session:
            # Check if symbol already exists
            stmt = select(bundle_symbols).where(
                sa.and_(
                    bundle_symbols.c.bundle_name == bundle_name, bundle_symbols.c.symbol == symbol
                )
            )
            existing = session.execute(stmt).fetchone()

            if existing:
                # Update existing symbol
                update_stmt = (
                    bundle_symbols.update()
                    .where(
                        sa.and_(
                            bundle_symbols.c.bundle_name == bundle_name,
                            bundle_symbols.c.symbol == symbol,
                        )
                    )
                    .values(asset_type=asset_type, exchange=exchange)
                )
                session.execute(update_stmt)
                symbol_id = existing.id
            else:
                # Insert new symbol
                insert_stmt = bundle_symbols.insert().values(
                    bundle_name=bundle_name,
                    symbol=symbol,
                    asset_type=asset_type,
                    exchange=exchange,
                )
                result = session.execute(insert_stmt)
                symbol_id = result.inserted_primary_key[0]

            session.commit()

            logger.info(
                "symbol_added",
                bundle_name=bundle_name,
                symbol=symbol,
                asset_type=asset_type,
                exchange=exchange,
                symbol_id=symbol_id,
            )

            return symbol_id

    @classmethod
    def get_symbols(cls, bundle_name: str) -> list[dict[str, Any]]:
        """Get all symbols for bundle.

        Args:
            bundle_name: Bundle name

        Returns:
            List of symbol dictionaries

        Example:
            >>> symbols = BundleMetadata.get_symbols("yfinance-daily")
            >>> for symbol in symbols:
            ...     print(f"{symbol['symbol']}: {symbol['asset_type']}")
        """
        engine = cls._get_engine()

        with Session(engine) as session:
            stmt = select(bundle_symbols).where(bundle_symbols.c.bundle_name == bundle_name)
            results = session.execute(stmt).fetchall()

            return [
                {
                    "symbol_id": row.id,
                    "bundle_name": row.bundle_name,
                    "symbol": row.symbol,
                    "asset_type": row.asset_type,
                    "exchange": row.exchange,
                }
                for row in results
            ]

    # ========================================================================
    # Cache Management Methods (merged from DataCatalog cache methods)
    # ========================================================================

    @classmethod
    def add_cache_entry(
        cls, cache_key: str, bundle_name: str, parquet_path: str, size_bytes: int
    ) -> None:
        """Add cache entry for bundle.

        Args:
            cache_key: Unique cache key
            bundle_name: Bundle name
            parquet_path: Path to cached Parquet file
            size_bytes: Size of cached file in bytes
        """
        engine = cls._get_engine()
        current_time = int(time.time())

        with Session(engine) as session:
            # Check if exists
            stmt = select(bundle_cache).where(bundle_cache.c.cache_key == cache_key)
            existing = session.execute(stmt).fetchone()

            if existing:
                # Update access time
                update_stmt = (
                    bundle_cache.update()
                    .where(bundle_cache.c.cache_key == cache_key)
                    .values(last_accessed=current_time)
                )
                session.execute(update_stmt)
            else:
                # Insert new
                insert_stmt = bundle_cache.insert().values(
                    cache_key=cache_key,
                    bundle_name=bundle_name,
                    bundle_path=parquet_path,
                    fetch_timestamp=current_time,
                    size_bytes=size_bytes,
                    last_accessed=current_time,
                )
                session.execute(insert_stmt)

            session.commit()

    @classmethod
    def get_quality_metrics(cls, bundle_name: str) -> dict[str, Any] | None:
        """Get latest quality metrics for bundle.

        Args:
            bundle_name: Bundle name

        Returns:
            Quality metrics dictionary or None
        """
        metadata = cls.get(bundle_name)
        if metadata is None:
            return None

        # Extract quality fields
        quality_fields = {
            "bundle_name",
            "row_count",
            "start_date",
            "end_date",
            "missing_days_count",
            "missing_days_list",
            "outlier_count",
            "ohlcv_violations",
            "validation_timestamp",
            "validation_passed",
        }

        return {k: v for k, v in metadata.items() if k in quality_fields}

    # ========================================================================
    # Helper Methods for Migration Script
    # ========================================================================

    @classmethod
    def count_bundles(cls) -> int:
        """Count total bundles."""
        engine = cls._get_engine()

        with Session(engine) as session:
            stmt = select(sa.func.count()).select_from(bundle_metadata)
            return session.execute(stmt).scalar() or 0

    @classmethod
    def count_quality_records(cls) -> int:
        """Count total quality metric records."""
        engine = cls._get_engine()

        with Session(engine) as session:
            stmt = (
                select(sa.func.count())
                .select_from(bundle_metadata)
                .where(bundle_metadata.c.validation_timestamp.isnot(None))
            )
            return session.execute(stmt).scalar() or 0

    @classmethod
    def count_symbols(cls, bundle_name: str) -> int:
        """Count symbols for bundle."""
        engine = cls._get_engine()

        with Session(engine) as session:
            stmt = (
                select(sa.func.count())
                .select_from(bundle_symbols)
                .where(bundle_symbols.c.bundle_name == bundle_name)
            )
            return session.execute(stmt).scalar() or 0

    @classmethod
    def count_all_symbols(cls) -> int:
        """Count total symbols across all bundles."""
        engine = cls._get_engine()

        with Session(engine) as session:
            stmt = select(sa.func.count()).select_from(bundle_symbols)
            return session.execute(stmt).scalar() or 0
