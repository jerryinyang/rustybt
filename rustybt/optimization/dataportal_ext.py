"""Multi-tier LRU cache for DataPortal history operations.

This module implements a sophisticated caching strategy to optimize DataPortal
history() calls by avoiding redundant data access. The cache uses a two-tier
architecture:

- Tier 1: Permanent cache for common lookback windows [20, 50, 200] bars
- Tier 2: LRU cache for variable windows (maxsize=256, OrderedDict-based)

The cache is thread-safe and integrates with bundle version tracking for
automatic invalidation when bundle data changes.

Example:
    >>> from rustybt.optimization.dataportal_ext import HistoryCache, CacheKey
    >>> cache = HistoryCache(permanent_windows=[20, 50, 200], tier2_maxsize=256)
    >>> key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
    >>> cache.put(key, np.array([100.0, 101.0, 102.0]))
    >>> result = cache.get(key)
"""

from collections import OrderedDict, namedtuple
from threading import Lock
from typing import Any, Dict, List, Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


# Immutable cache key for history window lookups
CacheKey = namedtuple("CacheKey", ["asset_id", "field", "bar_count", "end_date"])


class HistoryCache:
    """Multi-tier LRU cache for DataPortal history windows.

    This cache implements two tiers:
    1. Permanent cache (tier1): For common windows [20, 50, 200], never evicted
    2. LRU cache (tier2): For variable windows, OrderedDict with maxsize eviction

    Thread-safe for concurrent access from multiple strategies.

    Attributes:
        permanent_windows: List of bar counts to cache permanently (default: [20, 50, 200])
        tier2_maxsize: Maximum entries in tier2 LRU cache (default: 256)
        hits: Total cache hit count
        misses: Total cache miss count

    Example:
        >>> cache = HistoryCache()
        >>> key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
        >>> cache.put(key, np.array([100.0, 101.0]))
        >>> data = cache.get(key)  # Cache hit
        >>> cache.hit_rate  # Returns hit percentage
        50.0
    """

    def __init__(
        self,
        permanent_windows: Optional[List[int]] = None,
        tier2_maxsize: int = 256,
    ):
        """Initialize multi-tier cache.

        Args:
            permanent_windows: Bar counts for permanent cache (default: [20, 50, 200])
            tier2_maxsize: Maximum entries in tier2 LRU cache (default: 256)
        """
        self.permanent_windows = permanent_windows or [20, 50, 200]
        self.tier2_maxsize = tier2_maxsize

        # Tier 1: Permanent cache (never evicted)
        self.tier1_cache: Dict[CacheKey, np.ndarray] = {}

        # Tier 2: LRU cache with maxsize
        self.tier2_cache: OrderedDict[CacheKey, np.ndarray] = OrderedDict()

        # Thread safety
        self._lock = Lock()

        # Statistics
        self.hits = 0
        self.misses = 0

        logger.info(
            "history_cache_initialized",
            permanent_windows=self.permanent_windows,
            tier2_maxsize=self.tier2_maxsize,
        )

    def get(self, cache_key: CacheKey) -> Optional[np.ndarray]:
        """Retrieve data from cache (checks tier1 then tier2).

        Args:
            cache_key: Immutable cache key for lookup

        Returns:
            Cached NumPy array if found, None if cache miss
        """
        with self._lock:
            # Check tier1 (permanent) first
            if cache_key in self.tier1_cache:
                self.hits += 1
                logger.debug(
                    "cache_hit",
                    tier="tier1",
                    asset_id=cache_key.asset_id,
                    field=cache_key.field,
                    bar_count=cache_key.bar_count,
                    hit_rate=self.hit_rate,
                )
                return self.tier1_cache[cache_key]

            # Check tier2 (LRU)
            if cache_key in self.tier2_cache:
                self.hits += 1
                # Move to end (most recently used)
                self.tier2_cache.move_to_end(cache_key)
                logger.debug(
                    "cache_hit",
                    tier="tier2",
                    asset_id=cache_key.asset_id,
                    field=cache_key.field,
                    bar_count=cache_key.bar_count,
                    hit_rate=self.hit_rate,
                )
                return self.tier2_cache[cache_key]

            # Cache miss
            self.misses += 1
            logger.debug(
                "cache_miss",
                asset_id=cache_key.asset_id,
                field=cache_key.field,
                bar_count=cache_key.bar_count,
                hit_rate=self.hit_rate,
            )
            return None

    def put(self, cache_key: CacheKey, data: np.ndarray) -> None:
        """Store data in appropriate cache tier.

        Args:
            cache_key: Immutable cache key
            data: NumPy array to cache
        """
        with self._lock:
            # Permanent windows go to tier1
            if cache_key.bar_count in self.permanent_windows:
                self.tier1_cache[cache_key] = data
                logger.debug(
                    "cache_put",
                    tier="tier1",
                    asset_id=cache_key.asset_id,
                    field=cache_key.field,
                    bar_count=cache_key.bar_count,
                    tier1_size=len(self.tier1_cache),
                )
            else:
                # Variable windows go to tier2 with LRU eviction
                self.tier2_cache[cache_key] = data
                self.tier2_cache.move_to_end(cache_key)

                # Evict oldest if exceeds maxsize
                if len(self.tier2_cache) > self.tier2_maxsize:
                    evicted_key, _ = self.tier2_cache.popitem(last=False)
                    logger.debug(
                        "cache_eviction",
                        tier="tier2",
                        evicted_asset=evicted_key.asset_id,
                        evicted_bar_count=evicted_key.bar_count,
                        tier2_size=len(self.tier2_cache),
                    )

                logger.debug(
                    "cache_put",
                    tier="tier2",
                    asset_id=cache_key.asset_id,
                    field=cache_key.field,
                    bar_count=cache_key.bar_count,
                    tier2_size=len(self.tier2_cache),
                )

    def invalidate_cache(self, bundle_version_hash: str) -> None:
        """Clear all caches when bundle version changes.

        Args:
            bundle_version_hash: SHA256 hash of bundle version metadata
        """
        with self._lock:
            tier1_count = len(self.tier1_cache)
            tier2_count = len(self.tier2_cache)

            self.tier1_cache.clear()
            self.tier2_cache.clear()
            self.hits = 0
            self.misses = 0

            logger.info(
                "cache_invalidated",
                bundle_version_hash=bundle_version_hash,
                tier1_cleared=tier1_count,
                tier2_cleared=tier2_count,
            )

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage.

        Returns:
            Hit rate as percentage (0-100), or 0 if no requests
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100.0

    def get_stats(self) -> Dict[str, Any]:
        """Export cache statistics for monitoring.

        Returns:
            Dictionary with cache metrics:
                - hits: Total cache hits
                - misses: Total cache misses
                - hit_rate: Hit rate percentage
                - tier1_size: Number of tier1 entries
                - tier2_size: Number of tier2 entries
                - memory_bytes: Estimated memory usage in bytes
                - memory_mb: Estimated memory usage in MB
        """
        with self._lock:
            memory_bytes = self._estimate_memory_usage()
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": self.hit_rate,
                "tier1_size": len(self.tier1_cache),
                "tier2_size": len(self.tier2_cache),
                "memory_bytes": memory_bytes,
                "memory_mb": memory_bytes / (1024 * 1024),
            }

    def _estimate_memory_usage(self) -> int:
        """Estimate total memory usage of cache in bytes.

        Returns:
            Estimated memory usage in bytes (sum of all NumPy arrays)
        """
        total_bytes = 0

        # Tier 1 memory
        for array in self.tier1_cache.values():
            total_bytes += array.nbytes

        # Tier 2 memory
        for array in self.tier2_cache.values():
            total_bytes += array.nbytes

        return total_bytes

    def get_cache_warming_stats(self) -> Dict[str, Any]:
        """Analyze cache warming progress.

        Returns:
            Dictionary with cache warming metrics:
                - total_requests: Total cache requests (hits + misses)
                - current_hit_rate: Current hit rate percentage
                - is_warmed: True if hit rate > 60% (target threshold)
                - tier1_utilization: Percentage of tier1 slots used
                - tier2_utilization: Percentage of tier2 slots used
        """
        with self._lock:
            total_requests = self.hits + self.misses
            tier1_utilization = (
                (len(self.tier1_cache) / len(self.permanent_windows)) * 100
                if self.permanent_windows
                else 0
            )
            tier2_utilization = (len(self.tier2_cache) / self.tier2_maxsize) * 100

            return {
                "total_requests": total_requests,
                "current_hit_rate": self.hit_rate,
                "is_warmed": self.hit_rate > 60.0,
                "tier1_utilization": tier1_utilization,
                "tier2_utilization": tier2_utilization,
            }
