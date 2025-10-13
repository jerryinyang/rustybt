"""SQLite metadata catalog for Parquet storage layer.

DEPRECATED: This module is deprecated and will be removed in v2.0.
Use rustybt.data.bundles.metadata.BundleMetadata instead.

This module provides a dedicated metadata catalog for managing Parquet-stored
OHLCV data. Unlike the general-purpose DataCatalog, this catalog is specifically
designed for Parquet file metadata tracking.

Schema Design:
- datasets: Dataset-level metadata (source, resolution, schema version)
- symbols: Symbol-level metadata (asset types, exchanges)
- date_ranges: Temporal coverage tracking
- checksums: File integrity verification

Example:
    >>> catalog = ParquetMetadataCatalog("data/bundles/quandl/metadata.db")
    >>> dataset_id = catalog.create_dataset("yfinance", "1d", schema_version=1)
    >>> catalog.add_symbol(dataset_id, "AAPL", "equity", "NASDAQ")
    >>> catalog.update_date_range(dataset_id, "2023-01-01", "2023-12-31")
"""

import hashlib
import time
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy import Column, ForeignKey, Index, Integer, MetaData, Table, Text, create_engine
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


class ParquetMetadataCatalog:
    """Metadata catalog for Parquet storage layer.

    .. deprecated:: 1.0
        Use :class:`rustybt.data.bundles.metadata.BundleMetadata` instead.
        ParquetMetadataCatalog will be removed in v2.0.

    Manages dataset, symbol, date range, and checksum metadata for
    Parquet-stored OHLCV data.

    Attributes:
        db_path: Path to SQLite database file
        engine: SQLAlchemy engine
        metadata: SQLAlchemy metadata object

    Example:
        >>> catalog = ParquetMetadataCatalog("data/bundles/quandl/metadata.db")
        >>> dataset_id = catalog.create_dataset("yfinance", "1d")
        >>> catalog.add_symbol(dataset_id, "AAPL", "equity", "NASDAQ")
    """

    def __init__(self, db_path: str):
        """Initialize metadata catalog.

        .. deprecated:: 1.0
            Use :class:`rustybt.data.bundles.metadata.BundleMetadata` instead.
            ParquetMetadataCatalog will be removed in v2.0.

        Args:
            db_path: Path to SQLite database file. Will be created if doesn't exist.

        Example:
            >>> catalog = ParquetMetadataCatalog("data/bundles/quandl/metadata.db")
        """
        warnings.warn(
            "ParquetMetadataCatalog is deprecated and will be removed in v2.0. "
            "Use BundleMetadata from rustybt.data.bundles.metadata instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.metadata_obj = MetaData()

        # Define schema
        self._define_schema()

        # Create tables
        self.metadata_obj.create_all(self.engine)

        logger.info(
            "metadata_catalog_initialized",
            db_path=str(self.db_path),
        )

    def _define_schema(self) -> None:
        """Define SQLite schema for Parquet metadata.

        Tables:
        - datasets: Dataset-level metadata
        - symbols: Symbol-level metadata
        - date_ranges: Temporal coverage
        - checksums: File integrity
        """
        # Datasets table
        self.datasets = Table(
            "datasets",
            self.metadata_obj,
            Column("dataset_id", Integer, primary_key=True, autoincrement=True),
            Column("source", Text, nullable=False),  # 'yfinance', 'ccxt', 'csv'
            Column("resolution", Text, nullable=False),  # '1m', '5m', '1h', '1d'
            Column("schema_version", Integer, nullable=False, default=1),
            Column("created_at", Integer, nullable=False),  # Unix timestamp
            Column("updated_at", Integer, nullable=False),  # Unix timestamp
        )

        # Symbols table
        self.symbols = Table(
            "symbols",
            self.metadata_obj,
            Column("symbol_id", Integer, primary_key=True, autoincrement=True),
            Column("dataset_id", Integer, ForeignKey("datasets.dataset_id"), nullable=False),
            Column("symbol", Text, nullable=False),  # 'AAPL', 'BTC/USDT'
            Column("asset_type", Text),  # 'equity', 'crypto', 'future'
            Column("exchange", Text),  # 'NYSE', 'binance'
            Index("idx_symbols_symbol", "symbol"),
            Index("idx_symbols_dataset", "dataset_id"),
        )

        # Date ranges table
        self.date_ranges = Table(
            "date_ranges",
            self.metadata_obj,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("dataset_id", Integer, ForeignKey("datasets.dataset_id"), nullable=False),
            Column("start_date", Integer, nullable=False),  # Unix timestamp
            Column("end_date", Integer, nullable=False),  # Unix timestamp
            Index("idx_date_ranges_dataset", "dataset_id"),
            Index("idx_date_ranges_dates", "start_date", "end_date"),
        )

        # Checksums table
        self.checksums = Table(
            "checksums",
            self.metadata_obj,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("dataset_id", Integer, ForeignKey("datasets.dataset_id"), nullable=False),
            Column("parquet_path", Text, nullable=False),  # Relative path
            Column("checksum", Text, nullable=False),  # SHA256 hash
            Column("last_updated", Integer, nullable=False),  # Unix timestamp
            Index("idx_checksums_dataset", "dataset_id"),
        )

        # Cache entries table (Story 3.3)
        self.cache_entries = Table(
            "cache_entries",
            self.metadata_obj,
            Column("cache_key", Text, primary_key=True),  # SHA256 hash (first 16 chars)
            Column("dataset_id", Integer, ForeignKey("datasets.dataset_id"), nullable=False),
            Column("parquet_path", Text, nullable=False),  # Relative path to cached Parquet
            Column("checksum", Text, nullable=False),  # SHA256 checksum of Parquet file
            Column("created_at", Integer, nullable=False),  # Unix timestamp
            Column("last_accessed", Integer, nullable=False),  # Unix timestamp
            Column("access_count", Integer, nullable=False, default=1),
            Column("size_bytes", Integer, nullable=False),
            Index("idx_cache_entries_dataset", "dataset_id"),
            Index("idx_cache_entries_accessed", "last_accessed"),
        )

        # Backtest to cache linkage table (Story 3.3)
        self.backtest_cache_links = Table(
            "backtest_cache_links",
            self.metadata_obj,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("backtest_id", Text, nullable=False),  # User-provided backtest identifier
            Column("cache_key", Text, ForeignKey("cache_entries.cache_key"), nullable=False),
            Column("linked_at", Integer, nullable=False),  # Unix timestamp
            Index("idx_backtest_links_backtest", "backtest_id"),
            Index("idx_backtest_links_cache", "cache_key"),
        )

        # Cache statistics table (Story 3.3)
        self.cache_statistics = Table(
            "cache_statistics",
            self.metadata_obj,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("stat_date", Integer, nullable=False),  # Unix timestamp (day granularity)
            Column("hit_count", Integer, nullable=False, default=0),
            Column("miss_count", Integer, nullable=False, default=0),
            Column("total_size_mb", sa.Float, nullable=False, default=0.0),
            sa.UniqueConstraint("stat_date", name="unique_stat_date"),
        )

    def create_dataset(
        self,
        source: str,
        resolution: str,
        schema_version: int = 1,
    ) -> int:
        """Create new dataset entry.

        Args:
            source: Data source ('yfinance', 'ccxt', 'csv')
            resolution: Time resolution ('1m', '5m', '1h', '1d')
            schema_version: Schema version for backward compatibility

        Returns:
            Dataset ID (primary key)

        Example:
            >>> catalog = ParquetMetadataCatalog("metadata.db")
            >>> dataset_id = catalog.create_dataset("yfinance", "1d", schema_version=1)
            >>> assert dataset_id > 0
        """
        current_time = int(time.time())

        with Session(self.engine) as session:
            insert_stmt = self.datasets.insert().values(
                source=source,
                resolution=resolution,
                schema_version=schema_version,
                created_at=current_time,
                updated_at=current_time,
            )
            result = session.execute(insert_stmt)
            session.commit()

            dataset_id = result.inserted_primary_key[0]

            logger.info(
                "dataset_created",
                dataset_id=dataset_id,
                source=source,
                resolution=resolution,
                schema_version=schema_version,
            )

            return dataset_id

    def add_symbol(
        self,
        dataset_id: int,
        symbol: str,
        asset_type: str | None = None,
        exchange: str | None = None,
    ) -> int:
        """Add symbol to dataset.

        Args:
            dataset_id: Dataset ID
            symbol: Symbol string (e.g., 'AAPL', 'BTC/USDT')
            asset_type: Asset type ('equity', 'crypto', 'future')
            exchange: Exchange name ('NYSE', 'binance')

        Returns:
            Symbol ID (primary key)

        Example:
            >>> catalog.add_symbol(1, "AAPL", "equity", "NASDAQ")
        """
        with Session(self.engine) as session:
            insert_stmt = self.symbols.insert().values(
                dataset_id=dataset_id,
                symbol=symbol,
                asset_type=asset_type,
                exchange=exchange,
            )
            result = session.execute(insert_stmt)
            session.commit()

            symbol_id = result.inserted_primary_key[0]

            logger.info(
                "symbol_added",
                symbol_id=symbol_id,
                dataset_id=dataset_id,
                symbol=symbol,
                asset_type=asset_type,
                exchange=exchange,
            )

            return symbol_id

    def update_date_range(
        self,
        dataset_id: int,
        start_date: date | str,
        end_date: date | str,
    ) -> None:
        """Update or insert date range for dataset.

        Args:
            dataset_id: Dataset ID
            start_date: Start date (date object or ISO string 'YYYY-MM-DD')
            end_date: End date (date object or ISO string 'YYYY-MM-DD')

        Example:
            >>> catalog.update_date_range(1, "2023-01-01", "2023-12-31")
        """
        # Convert to Unix timestamp
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()

        start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp())

        with Session(self.engine) as session:
            # Check if date range exists
            select_stmt = sa.select(self.date_ranges).where(
                self.date_ranges.c.dataset_id == dataset_id
            )
            existing = session.execute(select_stmt).fetchone()

            if existing:
                # Update existing range
                update_stmt = (
                    self.date_ranges.update()
                    .where(self.date_ranges.c.dataset_id == dataset_id)
                    .values(
                        start_date=start_timestamp,
                        end_date=end_timestamp,
                    )
                )
                session.execute(update_stmt)
            else:
                # Insert new range
                insert_stmt = self.date_ranges.insert().values(
                    dataset_id=dataset_id,
                    start_date=start_timestamp,
                    end_date=end_timestamp,
                )
                session.execute(insert_stmt)

            session.commit()

            logger.info(
                "date_range_updated",
                dataset_id=dataset_id,
                start_date=str(start_date),
                end_date=str(end_date),
            )

    def add_checksum(
        self,
        dataset_id: int,
        parquet_path: str,
        checksum: str,
    ) -> int:
        """Add or update checksum for Parquet file.

        Args:
            dataset_id: Dataset ID
            parquet_path: Relative path to Parquet file
            checksum: SHA256 checksum

        Returns:
            Checksum entry ID

        Example:
            >>> checksum = "a7b2c..."
            >>> catalog.add_checksum(1, "year=2023/month=01/data.parquet", checksum)
        """
        current_time = int(time.time())

        with Session(self.engine) as session:
            # Check if checksum exists for this path
            select_stmt = sa.select(self.checksums).where(
                sa.and_(
                    self.checksums.c.dataset_id == dataset_id,
                    self.checksums.c.parquet_path == parquet_path,
                )
            )
            existing = session.execute(select_stmt).fetchone()

            if existing:
                # Update existing checksum
                update_stmt = (
                    self.checksums.update()
                    .where(
                        sa.and_(
                            self.checksums.c.dataset_id == dataset_id,
                            self.checksums.c.parquet_path == parquet_path,
                        )
                    )
                    .values(
                        checksum=checksum,
                        last_updated=current_time,
                    )
                )
                session.execute(update_stmt)
                checksum_id = existing.id
            else:
                # Insert new checksum
                insert_stmt = self.checksums.insert().values(
                    dataset_id=dataset_id,
                    parquet_path=parquet_path,
                    checksum=checksum,
                    last_updated=current_time,
                )
                result = session.execute(insert_stmt)
                checksum_id = result.inserted_primary_key[0]

            session.commit()

            logger.info(
                "checksum_added",
                checksum_id=checksum_id,
                dataset_id=dataset_id,
                parquet_path=parquet_path,
            )

            return checksum_id

    def get_dataset_info(self, dataset_id: int) -> dict[str, Any] | None:
        """Get dataset metadata.

        Args:
            dataset_id: Dataset ID

        Returns:
            Dataset metadata dictionary or None if not found

        Example:
            >>> info = catalog.get_dataset_info(1)
            >>> assert info["source"] == "yfinance"
        """
        with Session(self.engine) as session:
            stmt = sa.select(self.datasets).where(self.datasets.c.dataset_id == dataset_id)
            result = session.execute(stmt).fetchone()

            if result is None:
                return None

            return {
                "dataset_id": result.dataset_id,
                "source": result.source,
                "resolution": result.resolution,
                "schema_version": result.schema_version,
                "created_at": result.created_at,
                "updated_at": result.updated_at,
            }

    def get_symbols(self, dataset_id: int) -> list[dict[str, Any]]:
        """Get all symbols for dataset.

        Args:
            dataset_id: Dataset ID

        Returns:
            List of symbol metadata dictionaries

        Example:
            >>> symbols = catalog.get_symbols(1)
            >>> assert len(symbols) > 0
        """
        with Session(self.engine) as session:
            stmt = sa.select(self.symbols).where(self.symbols.c.dataset_id == dataset_id)
            results = session.execute(stmt).fetchall()

            return [
                {
                    "symbol_id": row.symbol_id,
                    "dataset_id": row.dataset_id,
                    "symbol": row.symbol,
                    "asset_type": row.asset_type,
                    "exchange": row.exchange,
                }
                for row in results
            ]

    def get_date_range(self, dataset_id: int) -> dict[str, Any] | None:
        """Get date range for dataset.

        Args:
            dataset_id: Dataset ID

        Returns:
            Date range dictionary with start_date and end_date, or None

        Example:
            >>> date_range = catalog.get_date_range(1)
            >>> assert "start_date" in date_range
        """
        with Session(self.engine) as session:
            stmt = sa.select(self.date_ranges).where(self.date_ranges.c.dataset_id == dataset_id)
            result = session.execute(stmt).fetchone()

            if result is None:
                return None

            # Convert Unix timestamps to datetime
            start_dt = datetime.fromtimestamp(result.start_date)
            end_dt = datetime.fromtimestamp(result.end_date)

            return {
                "dataset_id": result.dataset_id,
                "start_date": start_dt.date(),
                "end_date": end_dt.date(),
            }

    def find_parquet_files(
        self,
        dataset_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[str]:
        """Find Parquet file paths for dataset and date range.

        Args:
            dataset_id: Dataset ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of Parquet file paths

        Example:
            >>> paths = catalog.find_parquet_files(1, date(2023, 1, 1), date(2023, 1, 31))
        """
        with Session(self.engine) as session:
            stmt = sa.select(self.checksums.c.parquet_path).where(
                self.checksums.c.dataset_id == dataset_id
            )

            # Date filtering would require parsing partition paths
            # For now, return all paths for the dataset
            results = session.execute(stmt).fetchall()

            return [row.parquet_path for row in results]

    def verify_checksum(self, parquet_path: str, actual_checksum: str) -> bool:
        """Verify Parquet file checksum.

        Args:
            parquet_path: Relative path to Parquet file
            actual_checksum: Actual SHA256 checksum of file

        Returns:
            True if checksum matches stored value, False otherwise

        Example:
            >>> is_valid = catalog.verify_checksum("year=2023/data.parquet", checksum)
        """
        with Session(self.engine) as session:
            stmt = sa.select(self.checksums.c.checksum).where(
                self.checksums.c.parquet_path == parquet_path
            )
            result = session.execute(stmt).fetchone()

            if result is None:
                logger.warning("checksum_not_found", parquet_path=parquet_path)
                return False

            stored_checksum = result.checksum
            is_valid = stored_checksum == actual_checksum

            if not is_valid:
                logger.error(
                    "checksum_mismatch",
                    parquet_path=parquet_path,
                    stored=stored_checksum,
                    actual=actual_checksum,
                )

            return is_valid

    def get_all_symbols(self) -> list[dict[str, Any]]:
        """Get all symbols across all datasets.

        Returns:
            List of symbol metadata dictionaries

        Example:
            >>> symbols = catalog.get_all_symbols()
            >>> assert len(symbols) > 0
        """
        with Session(self.engine) as session:
            stmt = sa.select(self.symbols)
            results = session.execute(stmt).fetchall()

            return [
                {
                    "symbol_id": row.symbol_id,
                    "dataset_id": row.dataset_id,
                    "symbol": row.symbol,
                    "asset_type": row.asset_type,
                    "exchange": row.exchange,
                }
                for row in results
            ]

    def get_cache_entries(self) -> list[dict[str, Any]]:
        """Get all cache entries.

        Returns:
            List of cache entry dictionaries

        Example:
            >>> entries = catalog.get_cache_entries()
        """
        with Session(self.engine) as session:
            stmt = sa.select(self.cache_entries)
            results = session.execute(stmt).fetchall()

            return [
                {
                    "cache_key": row.cache_key,
                    "dataset_id": row.dataset_id,
                    "parquet_path": row.parquet_path,
                    "checksum": row.checksum,
                    "created_at": row.created_at,
                    "last_accessed": row.last_accessed,
                    "access_count": row.access_count,
                    "size_bytes": row.size_bytes,
                }
                for row in results
            ]

    def count_symbols(self) -> int:
        """Count total symbols in catalog."""
        with Session(self.engine) as session:
            stmt = sa.select(sa.func.count()).select_from(self.symbols)
            return session.execute(stmt).scalar() or 0


def calculate_file_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of file.

    Args:
        file_path: Path to file

    Returns:
        SHA256 checksum as hex string

    Example:
        >>> checksum = calculate_file_checksum(Path("data.parquet"))
        >>> assert len(checksum) == 64  # SHA256 is 64 hex chars
    """
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read in 8MB chunks to handle large files
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()
