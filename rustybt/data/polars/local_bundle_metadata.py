"""Local bundle metadata management for parquet bundles.

This module provides a LocalBundleMetadata class that manages the metadata.db
file within each bundle directory. This is separate from the global assets DB
and is used by ParquetAssetFinder to load asset information.

The local metadata.db contains:
- symbols: Per-bundle symbol definitions with SIDs
- date_ranges: Actual date ranges for each symbol based on parquet data
- checksums: File integrity tracking (inherited from ParquetMetadataCatalog)
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


class LocalBundleMetadata:
    """Manages local metadata.db file within a bundle directory.

    This class handles the bundle-local metadata.db that ParquetAssetFinder
    reads from. It's separate from the global assets DB to keep bundle
    metadata self-contained and portable.

    Parameters
    ----------
    bundle_path : Path
        Path to the bundle directory

    Attributes
    ----------
    bundle_path : Path
        Path to the bundle directory
    db_path : Path
        Path to the metadata.db file
    engine : sqlalchemy.Engine
        SQLAlchemy engine for database operations

    Example
    -------
    >>> from pathlib import Path
    >>> metadata = LocalBundleMetadata(Path("/path/to/bundle"))
    >>> metadata.add_symbol(sid=1, symbol="AAPL", asset_type="equity", exchange="NASDAQ")
    >>> metadata.update_date_range(sid=1, start_date=date(2020, 1, 1), end_date=date(2023, 12, 31))
    """

    def __init__(self, bundle_path: Path):
        """Initialize local bundle metadata manager.

        Args:
            bundle_path: Path to bundle directory
        """
        self.bundle_path = Path(bundle_path)
        self.db_path = self.bundle_path / "metadata.db"

        # Create database connection
        self.engine = create_engine(f"sqlite:///{self.db_path}")

        # Create tables if they don't exist
        self._create_tables()

        logger.info(
            "local_bundle_metadata_initialized",
            bundle_path=str(bundle_path),
            db_path=str(self.db_path),
        )

    def _create_tables(self) -> None:
        """Create required tables if they don't exist."""
        with Session(self.engine) as session:
            # Check if symbols table exists with old schema
            result = session.execute(
                sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='symbols'")
            ).fetchone()

            if result:
                # Check if it has the old schema (with dataset_id)
                columns_result = session.execute(sa.text("PRAGMA table_info(symbols)")).fetchall()
                columns = [row[1] for row in columns_result]

                if "dataset_id" in columns:
                    # Old schema detected - drop and recreate
                    logger.warning(
                        "old_symbols_schema_detected",
                        message="Dropping old symbols table and recreating with new schema",
                    )
                    session.execute(sa.text("DROP TABLE IF EXISTS symbols"))
                    session.commit()

            # Create symbols table with new schema
            session.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS symbols (
                    symbol_id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    asset_type TEXT,
                    exchange TEXT,
                    UNIQUE(symbol)
                )
                """
                )
            )

            # Check if date_ranges table exists with old schema
            result = session.execute(
                sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='date_ranges'")
            ).fetchone()

            if result:
                # Check if it has the old schema (without symbol_id)
                columns_result = session.execute(
                    sa.text("PRAGMA table_info(date_ranges)")
                ).fetchall()
                columns = [row[1] for row in columns_result]

                if "symbol_id" not in columns:
                    # Old schema detected - drop and recreate
                    logger.warning(
                        "old_date_ranges_schema_detected",
                        message="Dropping old date_ranges table and recreating with new schema",
                    )
                    session.execute(sa.text("DROP TABLE IF EXISTS date_ranges"))
                    session.commit()

            # Create date_ranges table with new schema
            session.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS date_ranges (
                    symbol_id INTEGER PRIMARY KEY,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    row_count INTEGER,
                    FOREIGN KEY(symbol_id) REFERENCES symbols(symbol_id)
                )
                """
                )
            )

            # Create checksums table (compatibility with ParquetMetadataCatalog)
            session.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS checksums (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER,
                    parquet_path TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    UNIQUE(parquet_path)
                )
                """
                )
            )

            session.commit()

        logger.debug("local_metadata_tables_created", db_path=str(self.db_path))

    def add_symbol(
        self,
        sid: int,
        symbol: str,
        asset_type: str | None = None,
        exchange: str | None = None,
    ) -> None:
        """Add or update symbol in local metadata.

        Args:
            sid: Symbol ID (must match SID in parquet files)
            symbol: Symbol string (e.g., "AAPL", "BTC/USDT")
            asset_type: Asset type ("equity", "crypto", "forex", "future")
            exchange: Exchange name

        Example:
            >>> metadata.add_symbol(1, "AAPL", "equity", "NASDAQ")
        """
        with Session(self.engine) as session:
            # Check if symbol exists
            result = session.execute(
                sa.text("SELECT symbol_id FROM symbols WHERE symbol_id = :sid"), {"sid": sid}
            ).fetchone()

            if result:
                # Update existing symbol
                session.execute(
                    sa.text(
                        """
                    UPDATE symbols
                    SET symbol = :symbol, asset_type = :asset_type, exchange = :exchange
                    WHERE symbol_id = :sid
                    """
                    ),
                    {
                        "sid": sid,
                        "symbol": symbol,
                        "asset_type": asset_type,
                        "exchange": exchange,
                    },
                )
            else:
                # Insert new symbol
                session.execute(
                    sa.text(
                        """
                    INSERT INTO symbols (symbol_id, symbol, asset_type, exchange)
                    VALUES (:sid, :symbol, :asset_type, :exchange)
                    """
                    ),
                    {
                        "sid": sid,
                        "symbol": symbol,
                        "asset_type": asset_type,
                        "exchange": exchange,
                    },
                )

            session.commit()

        logger.debug(
            "local_symbol_added",
            sid=sid,
            symbol=symbol,
            asset_type=asset_type,
            exchange=exchange,
        )

    def update_date_range(
        self,
        sid: int,
        start_date: date | datetime | str,
        end_date: date | datetime | str,
        row_count: int | None = None,
    ) -> None:
        """Update date range for a symbol.

        Args:
            sid: Symbol ID
            start_date: Start date of available data
            end_date: End date of available data
            row_count: Number of rows for this symbol

        Example:
            >>> metadata.update_date_range(1, date(2020, 1, 1), date(2023, 12, 31), 1000)
        """
        # Convert dates to ISO format strings
        if isinstance(start_date, (date, datetime)):
            start_str = start_date.isoformat()
        else:
            start_str = str(start_date)

        if isinstance(end_date, (date, datetime)):
            end_str = end_date.isoformat()
        else:
            end_str = str(end_date)

        with Session(self.engine) as session:
            # Check if date range exists
            result = session.execute(
                sa.text("SELECT symbol_id FROM date_ranges WHERE symbol_id = :sid"), {"sid": sid}
            ).fetchone()

            if result:
                # Update existing date range
                session.execute(
                    sa.text(
                        """
                    UPDATE date_ranges
                    SET start_date = :start_date, end_date = :end_date, row_count = :row_count
                    WHERE symbol_id = :sid
                    """
                    ),
                    {
                        "sid": sid,
                        "start_date": start_str,
                        "end_date": end_str,
                        "row_count": row_count,
                    },
                )
            else:
                # Insert new date range
                session.execute(
                    sa.text(
                        """
                    INSERT INTO date_ranges (symbol_id, start_date, end_date, row_count)
                    VALUES (:sid, :start_date, :end_date, :row_count)
                    """
                    ),
                    {
                        "sid": sid,
                        "start_date": start_str,
                        "end_date": end_str,
                        "row_count": row_count,
                    },
                )

            session.commit()

        logger.debug(
            "local_date_range_updated",
            sid=sid,
            start_date=start_str,
            end_date=end_str,
            row_count=row_count,
        )

    def add_checksum(self, dataset_id: int | None, parquet_path: str, checksum: str) -> None:
        """Add file checksum to local metadata.

        Args:
            dataset_id: Optional dataset ID
            parquet_path: Relative path to parquet file
            checksum: SHA256 checksum of file
        """
        import time

        with Session(self.engine) as session:
            # Check if checksum exists
            result = session.execute(
                sa.text("SELECT id FROM checksums WHERE parquet_path = :path"),
                {"path": parquet_path},
            ).fetchone()

            if result:
                # Update existing checksum
                session.execute(
                    sa.text(
                        """
                    UPDATE checksums
                    SET checksum = :checksum, created_at = :created_at
                    WHERE parquet_path = :path
                    """
                    ),
                    {
                        "checksum": checksum,
                        "created_at": int(time.time()),
                        "path": parquet_path,
                    },
                )
            else:
                # Insert new checksum
                session.execute(
                    sa.text(
                        """
                    INSERT INTO checksums (dataset_id, parquet_path, checksum, created_at)
                    VALUES (:dataset_id, :path, :checksum, :created_at)
                    """
                    ),
                    {
                        "dataset_id": dataset_id,
                        "path": parquet_path,
                        "checksum": checksum,
                        "created_at": int(time.time()),
                    },
                )

            session.commit()

    def get_symbols(self) -> list[dict[str, Any]]:
        """Get all symbols from local metadata.

        Returns:
            List of symbol dictionaries with sid, symbol, asset_type, exchange

        Example:
            >>> symbols = metadata.get_symbols()
            >>> for sym in symbols:
            ...     print(f"{sym['symbol_id']}: {sym['symbol']}")
        """
        with Session(self.engine) as session:
            result = session.execute(
                sa.text("SELECT symbol_id, symbol, asset_type, exchange FROM symbols")
            )
            return [
                {
                    "symbol_id": row[0],
                    "symbol": row[1],
                    "asset_type": row[2],
                    "exchange": row[3],
                }
                for row in result
            ]

    def get_date_ranges(self) -> dict[int, dict[str, Any]]:
        """Get all date ranges from local metadata.

        Returns:
            Dictionary mapping symbol_id to date range dict

        Example:
            >>> ranges = metadata.get_date_ranges()
            >>> print(ranges[1])  # {'start_date': '2020-01-01', 'end_date': '2023-12-31', 'row_count': 1000}
        """
        with Session(self.engine) as session:
            result = session.execute(
                sa.text("SELECT symbol_id, start_date, end_date, row_count FROM date_ranges")
            )
            return {
                row[0]: {
                    "start_date": row[1],
                    "end_date": row[2],
                    "row_count": row[3],
                }
                for row in result
            }

    def clear_all(self) -> None:
        """Clear all data from local metadata (for testing/cleanup).

        Warning: This deletes all symbols, date_ranges, and checksums!
        """
        with Session(self.engine) as session:
            session.execute(sa.text("DELETE FROM date_ranges"))
            session.execute(sa.text("DELETE FROM symbols"))
            session.execute(sa.text("DELETE FROM checksums"))
            session.commit()

        logger.warning("local_metadata_cleared", db_path=str(self.db_path))
