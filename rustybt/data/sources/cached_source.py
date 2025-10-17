"""Smart caching layer for DataSource implementations.

Provides transparent caching with market-aware freshness policies, LRU eviction,
and performance monitoring. Cache hits avoid redundant API calls, improving
backtest performance 10x for repeated runs.
"""

import hashlib
import threading
import time
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import structlog

from rustybt.data.sources.base import DataSource, DataSourceMetadata

logger = structlog.get_logger(__name__)


class CachedDataSource(DataSource):
    """Transparent caching wrapper for DataSource implementations.

    Wraps any DataSource adapter (YFinance, CCXT, CSV, etc.) with automatic
    caching to bundle storage. Cache hits return data from Parquet without
    hitting external APIs, while cache misses fetch from the underlying adapter.

    Features:
    - Automatic cache key generation from query parameters
    - Market-aware freshness policies (configurable per adapter type)
    - Thread-safe LRU eviction to enforce cache size limits
    - Cache statistics tracking (hit rate, latency, size)

    Performance targets:
    - Cache lookup: <10ms (P95)
    - Cache hit read: <100ms (P95)
    - Hit rate: >80% for repeated backtests

    Example:
        >>> source = YFinanceDataSource()
        >>> cached_source = CachedDataSource(
        ...     adapter=source,
        ...     cache_dir="~/.rustybt/cache",
        ...     config={"cache.max_size_bytes": 10 * 1024**3}
        ... )
        >>> df = await cached_source.fetch(["AAPL"], start, end, "1d")
        >>> # Second fetch returns cached data (no API call)
        >>> df2 = await cached_source.fetch(["AAPL"], start, end, "1d")

    Args:
        adapter: Underlying DataSource implementation to cache
        cache_dir: Directory for bundle cache storage
        config: Configuration dict with cache settings
        freshness_policy: Optional custom freshness policy (defaults to auto-select)
    """

    def __init__(
        self,
        adapter: DataSource,
        cache_dir: str | Path = "~/.rustybt/cache",
        config: dict[str, Any] | None = None,
        freshness_policy: Any | None = None,
    ):
        """Initialize cached data source wrapper.

        Args:
            adapter: DataSource to wrap with caching
            cache_dir: Cache storage directory (default: ~/.rustybt/cache)
            config: Configuration dict (e.g., {"cache.max_size_bytes": 10GB})
            freshness_policy: Optional CacheFreshnessPolicy (auto-selected if None)
        """
        self.adapter = adapter
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.config = config or {}
        self.freshness_policy = freshness_policy  # Will be set by factory in Phase 2

        # Lazy import to avoid circular dependency with DataCatalog
        from rustybt.data.catalog import DataCatalog

        self.catalog = DataCatalog()

        # Thread-safe eviction lock
        self._eviction_lock = threading.Lock()

        logger.info(
            "cached_source_init",
            adapter=adapter.__class__.__name__,
            cache_dir=str(self.cache_dir),
            max_size_mb=self.config.get("cache.max_size_bytes", 10 * 1024**3) / 1024**2,
        )

    async def fetch(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data with automatic caching.

        Workflow:
        1. Generate cache key from query parameters
        2. Check if cached data exists and is fresh
        3. If cache hit: read from bundle (<100ms)
        4. If cache miss: fetch from adapter, write to cache
        5. Enforce cache size limit with LRU eviction

        Args:
            symbols: List of symbols (e.g., ["AAPL", "MSFT"])
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution (e.g., "1d", "1h", "1m")

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            NetworkError: If adapter fetch fails
            ValidationError: If data validation fails
        """
        # 1. Generate cache key
        cache_key = self._generate_cache_key(symbols, start, end, frequency)

        # 2. Check bundle metadata for cached entry
        start_time = time.perf_counter()
        bundle_metadata = self.catalog.find_cached_bundle(cache_key)
        lookup_latency_ms = (time.perf_counter() - start_time) * 1000

        # Log cache lookup performance
        logger.debug(
            "cache_lookup",
            cache_key=cache_key,
            lookup_latency_ms=round(lookup_latency_ms, 2),
            found=bundle_metadata is not None,
        )

        # 3. If cached and fresh, read from bundle
        if bundle_metadata and self._is_fresh(bundle_metadata, frequency):
            logger.info(
                "cache_hit",
                cache_key=cache_key,
                bundle_name=bundle_metadata.get("bundle_name"),
                symbols=symbols[:5],  # Log first 5 symbols
                symbol_count=len(symbols),
            )

            start_time = time.perf_counter()
            try:
                df = self._read_from_cache(bundle_metadata)
                read_latency_ms = (time.perf_counter() - start_time) * 1000

                # Update last accessed timestamp
                self.catalog.update_cache_access(cache_key)

                # Track cache hit statistics
                self.catalog.increment_cache_hits()

                logger.info(
                    "cache_hit_complete",
                    cache_key=cache_key,
                    read_latency_ms=round(read_latency_ms, 2),
                    row_count=len(df),
                )

                return df
            except FileNotFoundError:
                # Cache metadata exists but file is missing (orphaned metadata)
                # Fall through to cache miss logic below
                logger.warning(
                    "cache_orphaned_metadata",
                    cache_key=cache_key,
                    bundle_name=bundle_metadata.get("bundle_name"),
                    reason="File missing despite metadata entry - treating as cache miss",
                )
                bundle_metadata = None  # Force cache miss

        # 4. Cache miss → fetch from adapter
        logger.info(
            "cache_miss",
            cache_key=cache_key,
            symbols=symbols[:5],
            symbol_count=len(symbols),
            reason="not_found" if bundle_metadata is None else "stale",
        )

        start_time = time.perf_counter()
        df = await self.adapter.fetch(symbols, start, end, frequency)
        fetch_latency_ms = (time.perf_counter() - start_time) * 1000

        # 5. Write to cache
        self._write_to_cache(cache_key, df, symbols, start, end, frequency)

        # 6. Enforce cache size limit (LRU eviction)
        self._enforce_cache_limit()

        # Track cache miss statistics
        self.catalog.increment_cache_misses()

        logger.info(
            "cache_miss_complete",
            cache_key=cache_key,
            fetch_latency_ms=round(fetch_latency_ms, 2),
            row_count=len(df),
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
        """Delegate bundle ingestion to underlying adapter.

        Args:
            bundle_name: Bundle name
            symbols: List of symbols
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution
            **kwargs: Additional adapter-specific parameters
        """
        self.adapter.ingest_to_bundle(bundle_name, symbols, start, end, frequency, **kwargs)

    def get_metadata(self) -> DataSourceMetadata:
        """Get metadata from underlying adapter.

        Returns:
            DataSourceMetadata from wrapped adapter
        """
        return self.adapter.get_metadata()

    def supports_live(self) -> bool:
        """Check if underlying adapter supports live streaming.

        Returns:
            True if adapter supports live streaming
        """
        return self.adapter.supports_live()

    async def warm_cache(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> None:
        """Pre-fetch data to warm the cache (async pre-loading).

        Useful for warming cache before backtests or after market close
        to prepare for next trading session. This is a fire-and-forget
        operation that populates cache without returning data.

        Args:
            symbols: List of symbols to pre-fetch
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution (e.g., "1d", "1h", "1m")

        Example:
            >>> # Warm cache for next trading day after market close
            >>> calendar = get_calendar('NYSE')
            >>> next_session = calendar.next_session(pd.Timestamp.now())
            >>> await cached_source.warm_cache(
            ...     symbols=["AAPL", "MSFT"],
            ...     start=next_session,
            ...     end=next_session,
            ...     frequency="1d"
            ... )
        """
        logger.info(
            "cache_warming_start",
            symbols=symbols[:5],  # Log first 5 symbols
            symbol_count=len(symbols),
            start=start.isoformat(),
            end=end.isoformat(),
            frequency=frequency,
        )

        # Simply fetch data - this will populate cache
        await self.fetch(symbols, start, end, frequency)

        logger.info(
            "cache_warming_complete",
            symbols=symbols[:5],
            symbol_count=len(symbols),
        )

    def _generate_cache_key(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> str:
        """Generate unique cache key from query parameters.

        Cache key must uniquely identify the data request. Uses SHA256 hash
        for compact key that handles special characters in symbols.

        Args:
            symbols: List of symbols (sorted for consistency)
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution

        Returns:
            16-character hex string (first 16 chars of SHA256 hash)

        Example:
            >>> key = self._generate_cache_key(
            ...     ["MSFT", "AAPL"],  # Will be sorted
            ...     pd.Timestamp("2023-01-01"),
            ...     pd.Timestamp("2023-12-31"),
            ...     "1d"
            ... )
            >>> print(key)  # e.g., "a3f2b1c4d5e6f7a8"
        """
        # Sort symbols for consistent key (AAPL,MSFT == MSFT,AAPL)
        symbols_str = ",".join(sorted(symbols))

        # Format timestamps consistently
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        # Combine all parameters
        key_str = f"{symbols_str}:{start_str}:{end_str}:{frequency}"

        # Hash for compact key
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def _is_fresh(self, bundle_metadata: dict[str, Any], frequency: str) -> bool:
        """Check if cached data is still fresh.

        Uses freshness policy to determine staleness. If no policy is set,
        defaults to conservative 1-hour TTL.

        Args:
            bundle_metadata: Bundle metadata from catalog
            frequency: Time resolution

        Returns:
            True if cache entry is fresh, False if stale
        """
        if self.freshness_policy is None:
            # Default: 1-hour TTL (conservative)
            fetch_timestamp = bundle_metadata.get("fetch_timestamp", 0)
            current_time = time.time()
            age_seconds = current_time - fetch_timestamp
            return age_seconds < 3600  # 1 hour

        # Delegate to freshness policy (Phase 2)
        return self.freshness_policy.is_fresh(bundle_metadata, frequency, calendar=None)

    def _read_from_cache(self, bundle_metadata: dict[str, Any]) -> pl.DataFrame:
        """Read cached data from bundle.

        Args:
            bundle_metadata: Bundle metadata with cache location

        Returns:
            Polars DataFrame from bundle cache

        Raises:
            IOError: If bundle read fails
        """
        bundle_name = bundle_metadata["bundle_name"]
        bundle_path = self.cache_dir / bundle_name / "data.parquet"

        if not bundle_path.exists():
            raise FileNotFoundError(f"Cache bundle not found: {bundle_path}")

        # Read from Parquet (target: <100ms)
        df = pl.read_parquet(bundle_path)

        logger.debug(
            "cache_read",
            bundle_name=bundle_name,
            bundle_path=str(bundle_path),
            row_count=len(df),
        )

        return df

    def _write_to_cache(
        self,
        cache_key: str,
        df: pl.DataFrame,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> None:
        """Write fetched data to cache bundle.

        Args:
            cache_key: Unique cache key
            df: Fetched OHLCV data
            symbols: List of symbols
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution
        """
        # Generate unique bundle name from cache key
        bundle_name = f"cache_{cache_key}"
        bundle_path = self.cache_dir / bundle_name
        bundle_path.mkdir(parents=True, exist_ok=True)

        # Write data to Parquet
        data_file = bundle_path / "data.parquet"
        df.write_parquet(data_file)

        # Calculate bundle size
        bundle_size = data_file.stat().st_size

        # Store cache metadata
        metadata = {
            "cache_key": cache_key,
            "bundle_name": bundle_name,
            "bundle_path": str(bundle_path),
            "symbols": symbols,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "frequency": frequency,
            "fetch_timestamp": int(time.time()),
            "size_bytes": bundle_size,
            "row_count": len(df),
            "last_accessed": int(time.time()),
        }

        self.catalog.store_cache_metadata(metadata)

        logger.info(
            "cache_write",
            cache_key=cache_key,
            bundle_name=bundle_name,
            size_mb=round(bundle_size / 1024**2, 2),
            row_count=len(df),
        )

    def _enforce_cache_limit(self) -> None:
        """Enforce cache size limit with LRU eviction.

        Thread-safe eviction that removes oldest accessed entries when cache
        exceeds configured size limit (default 10GB). Also alerts when cache
        size exceeds 90% of limit.
        """
        max_size = self.config.get("cache.max_size_bytes", 10 * 1024**3)  # 10GB default
        total_size = self.catalog.get_cache_size()
        usage_pct = (total_size / max_size) * 100 if max_size > 0 else 0

        # Alert when cache size >90% of limit
        if usage_pct >= 90.0 and total_size < max_size:
            logger.warning(
                "cache_size_alert",
                total_size_mb=round(total_size / 1024**2, 2),
                max_size_mb=round(max_size / 1024**2, 2),
                usage_pct=round(usage_pct, 1),
                message="Cache size exceeds 90% of limit. Consider running 'rustybt cache clean' or increasing cache.max_size_bytes.",
            )

        if total_size < max_size:
            return

        logger.info(
            "cache_eviction_start",
            total_size_mb=round(total_size / 1024**2, 2),
            max_size_mb=round(max_size / 1024**2, 2),
        )

        with self._eviction_lock:
            # Get LRU entries (ordered by last_accessed ASC)
            lru_entries = self.catalog.get_lru_cache_entries()

            evicted_count = 0
            evicted_size = 0

            for entry in lru_entries:
                # Delete bundle files
                bundle_path = Path(entry["bundle_path"])
                if bundle_path.exists():
                    # Delete all files in bundle directory
                    for file in bundle_path.iterdir():
                        file.unlink()
                    bundle_path.rmdir()

                # Delete cache metadata
                self.catalog.delete_cache_entry(entry["cache_key"])

                evicted_count += 1
                evicted_size += entry["size_bytes"]
                total_size -= entry["size_bytes"]

                # Stop when under limit
                if total_size < max_size:
                    break

        logger.info(
            "cache_eviction_complete",
            evicted_count=evicted_count,
            evicted_size_mb=round(evicted_size / 1024**2, 2),
            new_total_size_mb=round(total_size / 1024**2, 2),
        )
