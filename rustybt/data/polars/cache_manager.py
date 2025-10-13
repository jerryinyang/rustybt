"""Intelligent caching system for Parquet data storage.

This module implements a two-tier caching architecture with cache key generation,
cache lookup, and cache statistics tracking.

Two-Tier Architecture:
- Hot Cache: In-memory LRU cache with Polars DataFrames (fast access < 0.01s)
- Cold Cache: Disk-based Parquet files (fast access < 1s)

Example:
    >>> cache = CacheManager("data/bundles/quandl/metadata.db", "data/bundles/quandl/cache")
    >>> cache_key = cache.generate_cache_key(["AAPL"], "2023-01-01", "2023-12-31", "1d", "yfinance")
    >>> df = cache.get_cached_data(cache_key)  # Cache hit or miss
"""

import hashlib
import json
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl
import structlog

from rustybt.data.polars.metadata_catalog import ParquetMetadataCatalog, calculate_file_checksum

logger = structlog.get_logger(__name__)


class LRUCache:
    """LRU (Least Recently Used) cache for in-memory DataFrames.

    Implements an in-memory cache with configurable size limit and LRU eviction.

    Attributes:
        max_size_bytes: Maximum cache size in bytes
        cache: OrderedDict storing DataFrames with most recent at end

    Example:
        >>> cache = LRUCache(max_size_bytes=1024 * 1024 * 1024)  # 1GB
        >>> cache.put("key1", df)
        >>> df_cached = cache.get("key1")
    """

    def __init__(self, max_size_bytes: int = 1024 * 1024 * 1024):
        """Initialize LRU cache.

        Args:
            max_size_bytes: Maximum cache size in bytes (default: 1GB)
        """
        self.max_size_bytes = max_size_bytes
        self.cache: OrderedDict[str, pl.DataFrame] = OrderedDict()
        self.current_size_bytes = 0

        logger.info(
            "lru_cache_initialized",
            max_size_mb=max_size_bytes / (1024 * 1024),
        )

    def get(self, key: str) -> pl.DataFrame | None:
        """Get DataFrame from cache (marks as recently used).

        Args:
            key: Cache key

        Returns:
            DataFrame if found, None otherwise
        """
        if key not in self.cache:
            return None

        # Move to end (most recent)
        self.cache.move_to_end(key)

        logger.debug("hot_cache_hit", cache_key=key)
        return self.cache[key]

    def put(self, key: str, df: pl.DataFrame) -> None:
        """Put DataFrame into cache (may trigger eviction).

        Args:
            key: Cache key
            df: Polars DataFrame to cache
        """
        df_size = df.estimated_size()

        # If single DataFrame exceeds max size, skip caching
        if df_size > self.max_size_bytes:
            logger.warning(
                "dataframe_too_large_for_hot_cache",
                cache_key=key,
                df_size_mb=df_size / (1024 * 1024),
                max_size_mb=self.max_size_bytes / (1024 * 1024),
            )
            return

        # Evict old entries until space available
        while self.current_size_bytes + df_size > self.max_size_bytes and self.cache:
            evicted_key, evicted_df = self.cache.popitem(last=False)  # Remove oldest
            evicted_size = evicted_df.estimated_size()
            self.current_size_bytes -= evicted_size

            logger.info(
                "hot_cache_eviction",
                evicted_key=evicted_key,
                evicted_size_mb=evicted_size / (1024 * 1024),
            )

        # Add new entry
        self.cache[key] = df
        self.current_size_bytes += df_size

        logger.debug(
            "hot_cache_put",
            cache_key=key,
            df_size_mb=df_size / (1024 * 1024),
            total_size_mb=self.current_size_bytes / (1024 * 1024),
        )

    def clear(self) -> None:
        """Clear all entries from cache."""
        self.cache.clear()
        self.current_size_bytes = 0
        logger.info("hot_cache_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with entry_count and total_size_mb
        """
        return {
            "entry_count": len(self.cache),
            "total_size_mb": self.current_size_bytes / (1024 * 1024),
        }


class CacheManager:
    """Intelligent cache manager with two-tier architecture.

    Manages both hot (in-memory) and cold (disk) caches with automatic
    promotion/demotion and statistics tracking.

    Attributes:
        metadata_catalog: SQLite metadata catalog
        cache_directory: Directory for cached Parquet files
        hot_cache: In-memory LRU cache
        session_stats: Statistics for current session

    Example:
        >>> cache = CacheManager("metadata.db", "cache/")
        >>> df = cache.get_or_fetch(
        ...     ["AAPL"], "2023-01-01", "2023-12-31", "1d", "yfinance", fetch_fn
        ... )
    """

    def __init__(
        self,
        db_path: str,
        cache_directory: str,
        hot_cache_size_mb: int = 1024,
        cold_cache_size_mb: int = 10240,
        eviction_policy: str = "lru",
    ):
        """Initialize cache manager.

        Args:
            db_path: Path to SQLite metadata database
            cache_directory: Directory for cached Parquet files
            hot_cache_size_mb: Hot cache size in MB (default: 1GB)
            cold_cache_size_mb: Cold cache size in MB (default: 10GB)
            eviction_policy: Eviction policy ('lru', 'size', 'hybrid')
        """
        self.metadata_catalog = ParquetMetadataCatalog(db_path)
        self.cache_directory = Path(cache_directory)
        self.cache_directory.mkdir(parents=True, exist_ok=True)

        self.hot_cache = LRUCache(max_size_bytes=hot_cache_size_mb * 1024 * 1024)
        self.cold_cache_size_mb = cold_cache_size_mb
        self.eviction_policy = eviction_policy

        # Session statistics (reset on initialization)
        self.session_stats = {
            "hit_count": 0,
            "miss_count": 0,
            "hot_hits": 0,
            "cold_hits": 0,
        }

        logger.info(
            "cache_manager_initialized",
            cache_directory=str(self.cache_directory),
            hot_cache_mb=hot_cache_size_mb,
            cold_cache_mb=cold_cache_size_mb,
            eviction_policy=eviction_policy,
        )

    def generate_cache_key(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        resolution: str,
        data_source: str,
    ) -> str:
        """Generate deterministic cache key from parameters.

        Args:
            symbols: List of symbols (e.g., ['AAPL', 'MSFT'])
            start_date: Start date (ISO8601: '2023-01-01')
            end_date: End date (ISO8601: '2023-12-31')
            resolution: Time resolution ('1m', '5m', '1h', '1d')
            data_source: Data source ('yfinance', 'ccxt:binance', 'csv')

        Returns:
            Cache key (first 16 chars of SHA256 hash)

        Example:
            >>> key = cache.generate_cache_key(
            ...     ["AAPL"], "2023-01-01", "2023-12-31", "1d", "yfinance"
            ... )
            >>> assert len(key) == 16
        """
        # Sort symbols for consistency
        sorted_symbols = sorted(symbols)

        # Create cache key dict
        cache_params = {
            "symbols": sorted_symbols,
            "start_date": start_date,
            "end_date": end_date,
            "resolution": resolution,
            "data_source": data_source,
        }

        # Serialize to JSON (sorted keys for determinism)
        cache_json = json.dumps(cache_params, sort_keys=True)

        # Hash to create cache key
        cache_hash = hashlib.sha256(cache_json.encode()).hexdigest()

        return cache_hash[:16]  # Use first 16 chars for shorter keys

    def lookup_cache(self, cache_key: str) -> dict[str, Any] | None:
        """Lookup cache entry in metadata catalog.

        Args:
            cache_key: Cache key

        Returns:
            Cache entry metadata or None if not found

        Example:
            >>> entry = cache.lookup_cache("abc123def456")
        """
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        with Session(self.metadata_catalog.engine) as session:
            stmt = sa.select(self.metadata_catalog.cache_entries).where(
                self.metadata_catalog.cache_entries.c.cache_key == cache_key
            )
            result = session.execute(stmt).fetchone()

            if result is None:
                return None

            return {
                "cache_key": result.cache_key,
                "dataset_id": result.dataset_id,
                "parquet_path": result.parquet_path,
                "checksum": result.checksum,
                "created_at": result.created_at,
                "last_accessed": result.last_accessed,
                "access_count": result.access_count,
                "size_bytes": result.size_bytes,
            }

    def get_cached_data(self, cache_key: str) -> pl.DataFrame | None:
        """Get cached data (hot cache → cold cache → None).

        Args:
            cache_key: Cache key

        Returns:
            Polars DataFrame if cache hit, None if cache miss

        Example:
            >>> df = cache.get_cached_data("abc123def456")
        """
        start_time = time.time()

        # Check hot cache first
        df = self.hot_cache.get(cache_key)
        if df is not None:
            latency_ms = (time.time() - start_time) * 1000
            self.session_stats["hit_count"] += 1
            self.session_stats["hot_hits"] += 1

            logger.info(
                "cache_hit_hot",
                cache_key=cache_key,
                latency_ms=round(latency_ms, 2),
            )

            # Update last_accessed in metadata
            self._update_cache_access(cache_key)

            return df

        # Check cold cache (disk)
        cache_entry = self.lookup_cache(cache_key)
        if cache_entry is None:
            self.session_stats["miss_count"] += 1
            logger.info("cache_miss", cache_key=cache_key)
            return None

        # Load from Parquet
        parquet_path = self.cache_directory / cache_entry["parquet_path"]

        if not parquet_path.exists():
            logger.error(
                "cache_file_missing",
                cache_key=cache_key,
                parquet_path=str(parquet_path),
            )
            self.session_stats["miss_count"] += 1
            return None

        # Verify checksum
        actual_checksum = calculate_file_checksum(parquet_path)
        if actual_checksum != cache_entry["checksum"]:
            logger.error(
                "cache_checksum_mismatch",
                cache_key=cache_key,
                expected=cache_entry["checksum"],
                actual=actual_checksum,
            )
            # Delete corrupted cache entry
            self._delete_cache_entry(cache_key)
            self.session_stats["miss_count"] += 1
            return None

        # Load DataFrame
        df = pl.read_parquet(parquet_path)

        latency_ms = (time.time() - start_time) * 1000
        self.session_stats["hit_count"] += 1
        self.session_stats["cold_hits"] += 1

        logger.info(
            "cache_hit_cold",
            cache_key=cache_key,
            latency_ms=round(latency_ms, 2),
        )

        # Promote to hot cache
        self.hot_cache.put(cache_key, df)

        # Update last_accessed in metadata
        self._update_cache_access(cache_key)

        return df

    def put_cached_data(
        self,
        cache_key: str,
        df: pl.DataFrame,
        dataset_id: int,
        backtest_id: str | None = None,
    ) -> None:
        """Store DataFrame in cache (both hot and cold).

        Args:
            cache_key: Cache key
            df: Polars DataFrame to cache
            dataset_id: Dataset ID for linkage
            backtest_id: Optional backtest ID for linkage

        Example:
            >>> cache.put_cached_data("abc123def456", df, dataset_id=1, backtest_id="backtest-001")
        """
        # Store in hot cache
        self.hot_cache.put(cache_key, df)

        # Store in cold cache (Parquet)
        parquet_filename = f"{cache_key}.parquet"
        parquet_path = self.cache_directory / parquet_filename

        # Write to Parquet with Snappy compression (fast decompression)
        df.write_parquet(parquet_path, compression="snappy")

        # Calculate checksum and file size
        checksum = calculate_file_checksum(parquet_path)
        size_bytes = parquet_path.stat().st_size
        current_time = int(time.time())

        # Store in metadata catalog
        from sqlalchemy.orm import Session

        with Session(self.metadata_catalog.engine) as session:
            insert_stmt = self.metadata_catalog.cache_entries.insert().values(
                cache_key=cache_key,
                dataset_id=dataset_id,
                parquet_path=parquet_filename,
                checksum=checksum,
                created_at=current_time,
                last_accessed=current_time,
                access_count=1,
                size_bytes=size_bytes,
            )
            session.execute(insert_stmt)

            # Link to backtest if provided
            if backtest_id:
                link_stmt = self.metadata_catalog.backtest_cache_links.insert().values(
                    backtest_id=backtest_id,
                    cache_key=cache_key,
                    linked_at=current_time,
                )
                session.execute(link_stmt)

            session.commit()

        logger.info(
            "cache_write",
            cache_key=cache_key,
            dataset_id=dataset_id,
            size_mb=size_bytes / (1024 * 1024),
            backtest_id=backtest_id,
        )

        # Check if eviction needed
        self._check_cold_cache_eviction()

    def _update_cache_access(self, cache_key: str) -> None:
        """Update last_accessed timestamp and access_count.

        Args:
            cache_key: Cache key
        """
        from sqlalchemy.orm import Session

        current_time = int(time.time())

        with Session(self.metadata_catalog.engine) as session:
            update_stmt = (
                self.metadata_catalog.cache_entries.update()
                .where(self.metadata_catalog.cache_entries.c.cache_key == cache_key)
                .values(
                    last_accessed=current_time,
                    access_count=self.metadata_catalog.cache_entries.c.access_count + 1,
                )
            )
            session.execute(update_stmt)
            session.commit()

    def _delete_cache_entry(self, cache_key: str) -> None:
        """Delete cache entry from disk and metadata.

        Args:
            cache_key: Cache key
        """
        from sqlalchemy.orm import Session

        # Get cache entry to find file path
        cache_entry = self.lookup_cache(cache_key)
        if cache_entry is None:
            return

        # Delete Parquet file
        parquet_path = self.cache_directory / cache_entry["parquet_path"]
        if parquet_path.exists():
            parquet_path.unlink()
            logger.info("cache_file_deleted", cache_key=cache_key, path=str(parquet_path))

        # Delete metadata entry
        with Session(self.metadata_catalog.engine) as session:
            delete_stmt = self.metadata_catalog.cache_entries.delete().where(
                self.metadata_catalog.cache_entries.c.cache_key == cache_key
            )
            session.execute(delete_stmt)
            session.commit()

    def _check_cold_cache_eviction(self) -> None:
        """Check if cold cache needs eviction based on size limit."""
        total_size_mb = self._get_total_cache_size_mb()

        if total_size_mb <= self.cold_cache_size_mb:
            return

        logger.info(
            "cold_cache_eviction_triggered",
            total_size_mb=total_size_mb,
            max_size_mb=self.cold_cache_size_mb,
        )

        # Evict entries until under limit
        if self.eviction_policy == "lru":
            self._evict_lru()
        elif self.eviction_policy == "size":
            self._evict_by_size()
        else:  # hybrid
            self._evict_hybrid()

    def _get_total_cache_size_mb(self) -> float:
        """Calculate total cache size in MB.

        Returns:
            Total cache size in MB
        """
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        with Session(self.metadata_catalog.engine) as session:
            stmt = sa.select(sa.func.sum(self.metadata_catalog.cache_entries.c.size_bytes))
            result = session.execute(stmt).scalar()

            if result is None:
                return 0.0

            return result / (1024 * 1024)

    def _evict_lru(self) -> None:
        """Evict least recently used entries until under size limit."""
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        with Session(self.metadata_catalog.engine) as session:
            # Get entries ordered by last_accessed (oldest first)
            stmt = sa.select(self.metadata_catalog.cache_entries).order_by(
                self.metadata_catalog.cache_entries.c.last_accessed.asc()
            )
            entries = session.execute(stmt).fetchall()

            # Evict entries until under limit
            for entry in entries:
                self._delete_cache_entry(entry.cache_key)

                total_size_mb = self._get_total_cache_size_mb()
                if total_size_mb <= self.cold_cache_size_mb:
                    break

                logger.info(
                    "lru_eviction",
                    cache_key=entry.cache_key,
                    last_accessed=entry.last_accessed,
                )

    def _evict_by_size(self) -> None:
        """Evict largest entries first until under size limit."""
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        with Session(self.metadata_catalog.engine) as session:
            # Get entries ordered by size (largest first)
            stmt = sa.select(self.metadata_catalog.cache_entries).order_by(
                self.metadata_catalog.cache_entries.c.size_bytes.desc()
            )
            entries = session.execute(stmt).fetchall()

            # Evict entries until under limit
            for entry in entries:
                self._delete_cache_entry(entry.cache_key)

                total_size_mb = self._get_total_cache_size_mb()
                if total_size_mb <= self.cold_cache_size_mb:
                    break

                logger.info(
                    "size_eviction",
                    cache_key=entry.cache_key,
                    size_mb=entry.size_bytes / (1024 * 1024),
                )

    def _evict_hybrid(self) -> None:
        """Evict using hybrid strategy (largest + least recently used)."""
        # Simple hybrid: evict by size first, then by LRU if needed
        self._evict_by_size()

        # If still over limit, use LRU
        if self._get_total_cache_size_mb() > self.cold_cache_size_mb:
            self._evict_lru()

    def record_daily_statistics(self) -> None:
        """Record cache statistics to database for current day."""
        from sqlalchemy.orm import Session

        # Get today's date at midnight (Unix timestamp)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stat_date = int(today.timestamp())

        total_size_mb = self._get_total_cache_size_mb()
        hit_count = self.session_stats["hit_count"]
        miss_count = self.session_stats["miss_count"]

        with Session(self.metadata_catalog.engine) as session:
            # Try to update existing record
            update_stmt = (
                self.metadata_catalog.cache_statistics.update()
                .where(self.metadata_catalog.cache_statistics.c.stat_date == stat_date)
                .values(
                    hit_count=self.metadata_catalog.cache_statistics.c.hit_count + hit_count,
                    miss_count=self.metadata_catalog.cache_statistics.c.miss_count + miss_count,
                    total_size_mb=total_size_mb,
                )
            )
            result = session.execute(update_stmt)

            # If no existing record, insert new one
            if result.rowcount == 0:
                insert_stmt = self.metadata_catalog.cache_statistics.insert().values(
                    stat_date=stat_date,
                    hit_count=hit_count,
                    miss_count=miss_count,
                    total_size_mb=total_size_mb,
                )
                session.execute(insert_stmt)

            session.commit()

        logger.info(
            "daily_statistics_recorded",
            stat_date=today.isoformat(),
            hit_count=hit_count,
            miss_count=miss_count,
            total_size_mb=total_size_mb,
        )

    def get_cache_statistics(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get cache statistics for date range.

        Args:
            start_date: Optional start date (ISO8601: '2023-01-01')
            end_date: Optional end date (ISO8601: '2023-12-31')

        Returns:
            Dictionary with cache statistics

        Example:
            >>> stats = cache.get_cache_statistics("2023-01-01", "2023-12-31")
            >>> assert "hit_rate" in stats
        """
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        with Session(self.metadata_catalog.engine) as session:
            stmt = sa.select(self.metadata_catalog.cache_statistics)

            # Apply date filters if provided
            if start_date:
                start_dt = datetime.fromisoformat(start_date)
                start_timestamp = int(start_dt.timestamp())
                stmt = stmt.where(
                    self.metadata_catalog.cache_statistics.c.stat_date >= start_timestamp
                )

            if end_date:
                end_dt = datetime.fromisoformat(end_date)
                end_timestamp = int(end_dt.timestamp())
                stmt = stmt.where(
                    self.metadata_catalog.cache_statistics.c.stat_date <= end_timestamp
                )

            results = session.execute(stmt).fetchall()

            # Aggregate statistics
            total_hits = sum(r.hit_count for r in results)
            total_misses = sum(r.miss_count for r in results)
            total_requests = total_hits + total_misses

            hit_rate = total_hits / total_requests if total_requests > 0 else 0.0

            # Get current cache info
            total_size_mb = self._get_total_cache_size_mb()

            # Get entry count
            entry_count_stmt = sa.select(
                sa.func.count(self.metadata_catalog.cache_entries.c.cache_key)
            )
            entry_count = session.execute(entry_count_stmt).scalar() or 0

            # Get average access count
            avg_access_stmt = sa.select(
                sa.func.avg(self.metadata_catalog.cache_entries.c.access_count)
            )
            avg_access_count = session.execute(avg_access_stmt).scalar() or 0.0

            return {
                "hit_count": total_hits,
                "miss_count": total_misses,
                "hit_rate": hit_rate,
                "total_size_mb": total_size_mb,
                "entry_count": entry_count,
                "avg_access_count": avg_access_count,
                "session_stats": self.session_stats.copy(),
            }

    def clear_cache(self, cache_key: str | None = None, backtest_id: str | None = None) -> None:
        """Clear cache entries.

        Args:
            cache_key: Optional specific cache key to clear
            backtest_id: Optional backtest ID to clear all linked entries

        Example:
            >>> cache.clear_cache(cache_key="abc123def456")
            >>> cache.clear_cache(backtest_id="backtest-001")
            >>> cache.clear_cache()  # Clear all
        """
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        if cache_key:
            # Clear specific cache entry
            self._delete_cache_entry(cache_key)
            self.hot_cache.clear()
            logger.info("cache_cleared_by_key", cache_key=cache_key)
            return

        if backtest_id:
            # Clear all entries linked to backtest
            with Session(self.metadata_catalog.engine) as session:
                stmt = sa.select(self.metadata_catalog.backtest_cache_links.c.cache_key).where(
                    self.metadata_catalog.backtest_cache_links.c.backtest_id == backtest_id
                )
                cache_keys = [row.cache_key for row in session.execute(stmt).fetchall()]

            for key in cache_keys:
                self._delete_cache_entry(key)

            self.hot_cache.clear()
            logger.info("cache_cleared_by_backtest", backtest_id=backtest_id, count=len(cache_keys))
            return

        # Clear entire cache
        with Session(self.metadata_catalog.engine) as session:
            # Get all cache keys
            stmt = sa.select(self.metadata_catalog.cache_entries.c.cache_key)
            cache_keys = [row.cache_key for row in session.execute(stmt).fetchall()]

        for key in cache_keys:
            self._delete_cache_entry(key)

        self.hot_cache.clear()
        logger.info("cache_cleared_all", count=len(cache_keys))
