# ADR 004: Cache Freshness Strategy Patterns

**Status:** Accepted
**Date:** 2025-10-05
**Epic:** Epic X1 - Unified Data Architecture
**Deciders:** Architect (Winston), Product Team

---

## Context

The `CachedDataSource` must determine **when cached data is stale** and needs refreshing. Simple TTL (time-to-live) is insufficient because:

### Market Context Matters
- **Daily data**: Stale after market close (4:00 PM ET for NYSE)
- **Hourly data**: Stale after 1 hour, but NOT on weekends (markets closed)
- **Minute data**: Stale after 5 minutes, but only during trading hours
- **Crypto (24/7)**: No market close, pure TTL works

### Edge Cases
- Early market closures (holidays, half-days)
- International markets (different timezones, calendars)
- Delayed data sources (YFinance 15min delay vs real-time)
- Static data (CSV files never stale)

### Current Complexity
The Smart Caching Layer implementation (see [Story X1.3](../../prd/epic-X1-unified-data-architecture.md#story-x13-smart-caching-layer)) addresses:
- Frequency-based rules (daily/hourly/minute)
- Market calendar awareness (market close detection)
- Timezone handling (ET for US markets)

**Problem**: Hardcoded logic doesn't scale to multiple markets/sources.

---

## Decision

Implement **Strategy Pattern** for cache freshness policies:

```python
class CacheFreshnessPolicy(ABC):
    """Abstract strategy for determining cache staleness."""

    @abstractmethod
    def is_fresh(
        self,
        bundle_metadata: Dict,
        frequency: str,
        calendar: ExchangeCalendar,
    ) -> bool:
        """Return True if cached data is still fresh."""
        pass

    @abstractmethod
    def get_next_refresh_time(
        self,
        bundle_metadata: Dict,
        frequency: str,
        calendar: ExchangeCalendar,
    ) -> pd.Timestamp:
        """When should this cache entry be invalidated?"""
        pass
```

### Policy Hierarchy
```
CacheFreshnessPolicy (ABC)
├── MarketCloseFreshnessPolicy (daily data, exchange hours)
├── TTLFreshnessPolicy (hourly/minute data, simple timeout)
├── HybridFreshnessPolicy (TTL + market hours awareness)
├── NeverStaleFreshnessPolicy (CSV, static data)
└── AlwaysStaleFreshnessPolicy (live trading, no cache)
```

---

## Concrete Implementations

### 1. MarketCloseFreshnessPolicy (Daily Data)

```python
class MarketCloseFreshnessPolicy(CacheFreshnessPolicy):
    """Daily data is stale after last market close."""

    def is_fresh(self, bundle_metadata, frequency, calendar):
        fetch_timestamp = bundle_metadata['fetch_timestamp']
        last_close = calendar.previous_close(pd.Timestamp.now())

        # Fresh if fetched AFTER last market close
        return fetch_timestamp > last_close.timestamp()

    def get_next_refresh_time(self, bundle_metadata, frequency, calendar):
        # Invalidate at next market close
        next_close = calendar.next_close(pd.Timestamp.now())
        return next_close
```

**Use Cases:**
- NYSE daily bars (close at 4:00 PM ET)
- NASDAQ daily bars
- Any daily frequency data

**Edge Cases Handled:**
- Weekends: `calendar.previous_close()` returns Friday 4 PM
- Holidays: Exchange calendar accounts for closures
- Early closures: Calendar handles half-days (1 PM close)

---

### 2. TTLFreshnessPolicy (Hourly/Minute Data)

```python
class TTLFreshnessPolicy(CacheFreshnessPolicy):
    """Simple TTL for high-frequency data."""

    TTL_SECONDS = {
        '1h': 3600,      # 1 hour
        '1m': 300,       # 5 minutes
        '5m': 900,       # 15 minutes
        '15m': 1800,     # 30 minutes
    }

    def is_fresh(self, bundle_metadata, frequency, calendar):
        fetch_timestamp = bundle_metadata['fetch_timestamp']
        ttl = self.TTL_SECONDS.get(frequency, 3600)  # Default 1h
        now = int(time.time())

        return (now - fetch_timestamp) < ttl

    def get_next_refresh_time(self, bundle_metadata, frequency, calendar):
        fetch_time = pd.Timestamp(bundle_metadata['fetch_timestamp'], unit='s')
        ttl = self.TTL_SECONDS.get(frequency, 3600)
        return fetch_time + pd.Timedelta(seconds=ttl)
```

**Use Cases:**
- Crypto hourly bars (24/7 markets)
- Intraday minute bars

**Limitations:**
- Doesn't account for market hours (refreshes on weekends)
- Fixed TTL per frequency (not context-aware)

---

### 3. HybridFreshnessPolicy (TTL + Market Hours)

```python
class HybridFreshnessPolicy(CacheFreshnessPolicy):
    """TTL freshness, but ONLY during market hours."""

    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds

    def is_fresh(self, bundle_metadata, frequency, calendar):
        fetch_timestamp = bundle_metadata['fetch_timestamp']
        now_ts = pd.Timestamp.now()

        # If market closed, cache always fresh (no new data)
        if not calendar.is_open_now(now_ts):
            return True

        # Market open: check TTL
        now = int(time.time())
        return (now - fetch_timestamp) < self.ttl_seconds

    def get_next_refresh_time(self, bundle_metadata, frequency, calendar):
        fetch_time = pd.Timestamp(bundle_metadata['fetch_timestamp'], unit='s')
        refresh_time = fetch_time + pd.Timedelta(seconds=self.ttl_seconds)

        # If refresh falls outside market hours, push to next open
        if not calendar.is_open_on_minute(refresh_time):
            next_open = calendar.next_open(refresh_time)
            return next_open

        return refresh_time
```

**Use Cases:**
- NYSE hourly bars (only refresh during 9:30 AM - 4:00 PM ET)
- Minute bars for traditional exchanges

**Benefits:**
- No wasted refreshes on weekends/nights
- Context-aware (market hours matter)

---

### 4. NeverStaleFreshnessPolicy (Static Data)

```python
class NeverStaleFreshnessPolicy(CacheFreshnessPolicy):
    """Data never goes stale (CSV files, historical bundles)."""

    def is_fresh(self, bundle_metadata, frequency, calendar):
        return True  # Always fresh

    def get_next_refresh_time(self, bundle_metadata, frequency, calendar):
        return pd.Timestamp.max  # Never refresh
```

**Use Cases:**
- CSV adapter (static files)
- Historical research bundles (immutable)

---

### 5. AlwaysStaleFreshnessPolicy (Live Trading)

```python
class AlwaysStaleFreshnessPolicy(CacheFreshnessPolicy):
    """Data always stale (force adapter fetch)."""

    def is_fresh(self, bundle_metadata, frequency, calendar):
        return False  # Always stale

    def get_next_refresh_time(self, bundle_metadata, frequency, calendar):
        return pd.Timestamp.now()  # Refresh immediately
```

**Use Cases:**
- Live trading mode (real-time data required)
- WebSocket adapters (streaming, no cache)

---

## Policy Selection Logic

### FreshnessPolicyFactory

```python
class FreshnessPolicyFactory:
    """Factory to select appropriate freshness policy."""

    @staticmethod
    def create(adapter: DataSource, frequency: str) -> CacheFreshnessPolicy:
        # 1. Live trading: never cache
        if adapter.supports_live():
            return AlwaysStaleFreshnessPolicy()

        # 2. Static data: never stale
        if adapter.source_type == 'csv':
            return NeverStaleFreshnessPolicy()

        # 3. Daily data: market close policy
        if frequency == '1d':
            return MarketCloseFreshnessPolicy()

        # 4. Hourly/minute with market hours
        if adapter.source_type in ['yfinance', 'polygon', 'alpaca']:
            ttl = TTLFreshnessPolicy.TTL_SECONDS.get(frequency, 3600)
            return HybridFreshnessPolicy(ttl_seconds=ttl)

        # 5. Crypto 24/7: pure TTL
        if adapter.source_type == 'ccxt':
            return TTLFreshnessPolicy()

        # 6. Fallback: conservative 1-hour TTL
        return TTLFreshnessPolicy()
```

---

## Configuration Support

### Per-Source Policy Override

```yaml
# rustybt/config/cache_freshness.yaml
freshness_policies:
  yfinance:
    daily: market_close
    hourly: hybrid_3600  # Hybrid policy, 1h TTL
    minute: hybrid_300   # Hybrid policy, 5min TTL

  ccxt:
    daily: ttl_86400     # 24 hours
    hourly: ttl_3600     # 1 hour
    minute: ttl_300      # 5 minutes

  csv:
    daily: never_stale
    hourly: never_stale
    minute: never_stale

  polygon:
    daily: market_close
    hourly: hybrid_3600
    minute: hybrid_60    # 1min TTL during market hours

# Market calendar per source
calendars:
  yfinance: NYSE
  polygon: XNYS
  alpaca: NYSE
  ccxt: 24/7  # No calendar (always open)
```

---

## Integration with CachedDataSource

```python
class CachedDataSource:
    def __init__(self, adapter: DataSource, cache_dir: Path, config: Dict):
        self.adapter = adapter
        self.cache_dir = cache_dir

        # Load calendar for adapter
        calendar_name = config['calendars'].get(adapter.source_type, 'NYSE')
        self.calendar = get_calendar(calendar_name)

    async def fetch(self, symbols, start, end, frequency):
        cache_key = self._generate_key(symbols, start, end, frequency)
        bundle = BundleMetadata.find_cached(cache_key)

        if bundle:
            # Select policy based on adapter + frequency
            policy = FreshnessPolicyFactory.create(self.adapter, frequency)

            if policy.is_fresh(bundle, frequency, self.calendar):
                logger.info("cache_hit", key=cache_key, policy=policy.__class__.__name__)
                return self._read_from_cache(bundle)

        # Cache miss or stale
        logger.info("cache_miss", key=cache_key)
        df = await self.adapter.fetch(symbols, start, end, frequency)
        self._write_to_cache(cache_key, df)

        return df
```

---

## Testing Strategy

### 1. Policy Unit Tests

```python
@pytest.mark.parametrize("fetch_time,expected", [
    ("2025-10-05 15:00:00", False),  # Before close
    ("2025-10-05 16:01:00", True),   # After close
    ("2025-10-06 10:00:00", True),   # Next day (after Friday close)
])
def test_market_close_freshness_policy(fetch_time, expected):
    policy = MarketCloseFreshnessPolicy()
    calendar = get_calendar('NYSE')

    bundle = {'fetch_timestamp': pd.Timestamp(fetch_time).timestamp()}
    is_fresh = policy.is_fresh(bundle, '1d', calendar)

    assert is_fresh == expected
```

### 2. Edge Case Tests

```python
def test_hybrid_policy_weekend():
    """Hybrid policy should treat cache as fresh on weekends."""
    policy = HybridFreshnessPolicy(ttl_seconds=3600)
    calendar = get_calendar('NYSE')

    # Fetched Friday 3 PM, checking Saturday 10 AM
    bundle = {'fetch_timestamp': pd.Timestamp("2025-10-03 15:00:00").timestamp()}

    with freeze_time("2025-10-04 10:00:00"):  # Saturday
        is_fresh = policy.is_fresh(bundle, '1h', calendar)
        assert is_fresh is True  # Market closed, cache fresh
```

### 3. Integration Tests

```python
@pytest.mark.integration
async def test_cached_source_with_hybrid_policy():
    """End-to-end test with hybrid policy."""
    adapter = YFinanceDataSource()
    cached = CachedDataSource(adapter, cache_dir="~/.test-cache")

    # First fetch (cache miss)
    df1 = await cached.fetch(["AAPL"], start, end, "1h")

    # Second fetch within TTL during market hours (cache hit)
    df2 = await cached.fetch(["AAPL"], start, end, "1h")

    assert df1.equals(df2)
    assert BundleMetadata.get_hit_count() == 1
```

---

## Consequences

### Positive
✅ **Extensible** - New policies easily added (crypto exchanges, international)
✅ **Testable** - Each policy isolated, unit testable
✅ **Configurable** - Users override via config YAML
✅ **Market-aware** - Respects trading hours, calendars
✅ **Performance** - Avoids unnecessary refreshes (weekends, nights)

### Negative
⚠️ **Complexity** - More classes than simple TTL
⚠️ **Configuration burden** - Users must understand policy types
⚠️ **Calendar dependency** - Requires accurate exchange calendars

### Neutral
- Policy selection automatic (factory pattern)
- Backwards compatible (default policies work out-of-box)
- Documentation required (policy types, when to use)

---

## Metrics for Success

- [ ] All edge cases covered (weekends, holidays, early close)
- [ ] Zero stale data incidents in production
- [ ] Policy selection automatic (no user config required)
- [ ] Test coverage ≥95% for all policies
- [ ] Performance: policy.is_fresh() <1ms

---

## Related Decisions
- [ADR 003: Smart Caching Layer](003-smart-caching-layer.md)
- [ADR 001: Unified DataSource Abstraction](001-unified-data-source-abstraction.md)

---

## References
- [Epic X1 Architecture](../epic-X1-unified-data-architecture.md)
- [Story X1.4: Smart Caching Layer](../../stories/X1.3.smart-caching-layer.story.md)
- [Exchange Calendars Documentation](https://exchange-calendars.readthedocs.io/)
