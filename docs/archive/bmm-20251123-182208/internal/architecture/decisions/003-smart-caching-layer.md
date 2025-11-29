# ADR 003: Smart Caching Layer with Freshness Policies

**Status:** Accepted
**Date:** 2025-10-05
**Epic:** Epic X1 - Unified Data Architecture
**Deciders:** Architect (Winston), Product Team

---

## Context

### Current State: No Cache Optimization
- Adapters fetch from APIs on every request
- Redundant API calls for same data (rate limits, latency)
- No sharing between live trading and backtesting
- Parquet bundles created manually, not reused

### Performance Pain Points
- YFinance API: 5-10s for 1 year daily data (250 trading days)
- CCXT API: 3-5s for 6 months hourly data (4,320 bars)
- Repeated backtests re-fetch identical data
- No warm-up mechanism for next trading day

---

## Decision

Implement **transparent `CachedDataSource` wrapper** with:

1. **Automatic cache lookup** - Check if data already exists in Parquet bundle
2. **Freshness policies** - Context-aware staleness detection (daily vs hourly vs minute)
3. **LRU eviction** - Keep cache under configurable size limit (default 10GB)
4. **Cache warming** - Async pre-fetch for next trading day
5. **Performance targets**:
   - Cache lookup: <10ms (SQLite metadata query)
   - Cache hit read: <100ms (Parquet scan)
   - Cache hit rate: >80% (repeated backtests)

### Architecture
```python
class CachedDataSource:
    def __init__(self, adapter: DataSource, cache_dir: Path):
        self.adapter = adapter
        self.cache_dir = cache_dir
        self.freshness_policy = FreshnessPolicyFactory.create(adapter)

    async def fetch(self, symbols, start, end, frequency):
        # 1. Generate cache key
        cache_key = hash(symbols, start, end, frequency)

        # 2. Check bundle metadata
        bundle = BundleMetadata.find_cached(cache_key)

        if bundle:
            # 3. Check freshness
            if self.freshness_policy.is_fresh(bundle, frequency):
                return self._read_from_cache(bundle)  # <100ms

        # 4. Cache miss → fetch from adapter
        df = await self.adapter.fetch(symbols, start, end, frequency)

        # 5. Write to cache
        self._write_to_cache(cache_key, df)

        return df
```

---

## Consequences

### Positive
✅ **10x performance improvement** - Cache hit <100ms vs API fetch 5-10s
✅ **Reduced API costs** - Fewer external calls (rate limits, quotas)
✅ **Offline backtesting** - Reuse cached data without network
✅ **Transparent** - No code changes for users (drop-in wrapper)
✅ **Configurable** - Freshness policies per frequency, eviction size tunable

### Negative
⚠️ **Stale data risk** - Incorrect freshness policy serves old data
⚠️ **Storage overhead** - 10GB default cache (configurable)
⚠️ **Concurrency complexity** - Race conditions during eviction
⚠️ **Cache invalidation** - Hard problem (freshness policies may miss edge cases)

### Neutral
- Cache hit rate depends on workload (backtest repetition)
- Memory usage unchanged (Parquet files on disk, not RAM)
- Requires migration for optimal use (existing bundles → cache entries)

---

## Alternatives Considered

### Alternative 1: No Caching (Status Quo)
**Rejected because:**
- Performance unacceptable (5-10s per fetch)
- Redundant API calls waste resources
- Offline backtesting impossible

### Alternative 2: Simple TTL Cache (Time-To-Live)
**Rejected because:**
- Ignores market context (daily data stale after close, not fixed TTL)
- Hourly data on weekends shouldn't invalidate (markets closed)
- One-size-fits-all TTL too coarse

### Alternative 3: Redis/Memcached External Cache
**Rejected because:**
- Added infrastructure complexity (separate service)
- Network latency for cache queries (defeats purpose)
- Parquet already on disk (no need for separate store)

### Alternative 4: HTTP ETag/Cache-Control Headers
**Rejected because:**
- Adapters don't expose HTTP headers (abstracted)
- Not all sources support ETags (CSV, custom APIs)
- Requires API support (can't control)

---

## Implementation Plan

### Phase 1: Core Caching (Story X1.4)
```python
class CachedDataSource:
    async def fetch(self, symbols, start, end, frequency):
        cache_key = self._generate_key(symbols, start, end, frequency)
        bundle = BundleMetadata.find_cached(cache_key)

        if bundle and self.freshness_policy.is_fresh(bundle, frequency):
            logger.info("cache_hit", key=cache_key)
            BundleMetadata.increment_hit_count()
            return self._read_from_cache(bundle)

        logger.info("cache_miss", key=cache_key)
        BundleMetadata.increment_miss_count()

        df = await self.adapter.fetch(symbols, start, end, frequency)
        self._write_to_cache(cache_key, df)
        self._enforce_cache_limit()  # LRU eviction

        return df
```

### Phase 2: Freshness Policies (Story X1.4)
See [ADR 004: Cache Freshness Strategy Patterns](004-cache-freshness-strategies.md) for detailed design.

### Phase 3: Cache Warming (Story X1.4)
```python
async def warm_cache(self, symbols: List[str], calendar):
    """Pre-fetch next trading day's data after market close."""
    next_session = calendar.next_session(pd.Timestamp.now())

    if next_session:
        logger.info("cache_warming", session=next_session)
        await self.fetch(symbols, next_session, next_session, '1d')
```

### Phase 4: LRU Eviction (Story X1.4)
```python
def _enforce_cache_limit(self):
    max_size = Config.get('cache.max_size_bytes', 10 * 1024**3)  # 10GB
    total_size = BundleMetadata.get_cache_size()

    if total_size < max_size:
        return

    # Evict LRU entries with thread safety
    with self._eviction_lock:
        lru_entries = BundleMetadata.get_lru_cache_entries()
        for entry in lru_entries:
            self._delete_bundle(entry['bundle_name'])
            BundleMetadata.delete_cache_entry(entry['cache_key'])

            total_size -= entry['size_bytes']
            if total_size < max_size:
                break
```

---

## Performance Targets & Validation

### Targets
| Metric | Target | Measurement |
|--------|--------|-------------|
| Cache lookup | <10ms | SQLite EXPLAIN QUERY PLAN |
| Cache hit read | <100ms | Parquet scan profiling |
| Cache hit rate | >80% | Repeated backtest workload |
| Eviction overhead | <50ms | Lock contention profiling |

### Validation Strategy
```python
@pytest.mark.benchmark
def test_cache_lookup_latency():
    """Cache lookup must be <10ms."""
    start = time.perf_counter()
    bundle = BundleMetadata.find_cached(cache_key)
    latency_ms = (time.perf_counter() - start) * 1000
    assert latency_ms < 10, f"Lookup too slow: {latency_ms}ms"

@pytest.mark.benchmark
def test_cache_hit_read_latency():
    """Cache hit read must be <100ms."""
    start = time.perf_counter()
    df = cached_source._read_from_cache(bundle)
    latency_ms = (time.perf_counter() - start) * 1000
    assert latency_ms < 100, f"Read too slow: {latency_ms}ms"
```

---

## Risk Mitigation

### Risk 1: Stale Data Served to Users
**Mitigation:**
- Comprehensive freshness policy tests (all edge cases)
- Add `--no-cache` CLI flag for debugging
- Cache validation checks (OHLCV relationships)
- Automatic invalidation on quality failure

### Risk 2: Cache Eviction Race Conditions
**Mitigation:**
- Thread-safe eviction lock (`threading.Lock()`)
- Atomic SQLite transactions for metadata updates
- Stress testing with parallel DataPortals

### Risk 3: Disk Space Exhaustion
**Mitigation:**
- Configurable max size (default 10GB)
- LRU eviction prevents unbounded growth
- CLI command `rustybt cache clean --max-size 5GB`
- Alert user when cache >90% of limit

---

## Metrics for Success

- [ ] Cache lookup latency <10ms (P95)
- [ ] Cache hit read latency <100ms (P95)
- [ ] Cache hit rate >80% for repeated backtests
- [ ] LRU eviction keeps cache under max size
- [ ] Zero stale data incidents (freshness policies correct)
- [ ] Performance regression tests in CI (<5% overhead)

---

## Configuration

```yaml
# rustybt/config/cache.yaml
cache:
  enabled: true
  max_size_bytes: 10737418240  # 10GB
  warming_enabled: true
  freshness:
    daily: "market_close"  # Refresh after market close
    hourly: 3600           # 1 hour TTL
    minute: 300            # 5 minute TTL
```

---

## Related Decisions
- [ADR 001: Unified DataSource Abstraction](001-unified-data-source-abstraction.md)
- [ADR 002: Unified Metadata Schema](002-unified-metadata-schema.md)
- [ADR 004: Cache Freshness Strategy Patterns](004-cache-freshness-strategies.md)

---

## References
- [Epic X1 Architecture](../epic-X1-unified-data-architecture.md)
- [Story X1.4: Smart Caching Layer](../../stories/X1.3.smart-caching-layer.story.md)
