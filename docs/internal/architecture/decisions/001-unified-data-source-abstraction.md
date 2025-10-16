# ADR 001: Unified DataSource Abstraction

**Status:** Accepted
**Date:** 2025-10-05
**Epic:** Epic X1 - Unified Data Architecture
**Deciders:** Architect (Winston), Product Team

---

## Context

RustyBT has three separate data systems with no integration:
1. **Data Adapters** (Epic 6) - Fetch from external APIs (YFinance, CCXT, etc.)
2. **Bundle System** (Zipline legacy) - Pre-processed Parquet storage
3. **Metadata Catalogs** (2 systems) - Provenance and file tracking

### Problems
- Epic 7 profiling **BLOCKED** - no way to create bundles from adapters
- Manual scripting required for each data source
- Duplicate metadata tracking across systems
- No cache optimization (redundant API calls)
- Live trading and backtesting use separate code paths

---

## Decision

We will create a **unified `DataSource` interface** that all adapters implement, providing:

```python
class DataSource(ABC):
    @abstractmethod
    async def fetch(symbols, start, end, frequency) -> DataFrame

    @abstractmethod
    def ingest_to_bundle(bundle_name, symbols, start, end, frequency)

    @abstractmethod
    def get_metadata() -> Dict[str, Any]

    @abstractmethod
    def supports_live() -> bool
```

All existing adapters (YFinance, CCXT, Polygon, Alpaca, CSV) will implement this interface while maintaining backwards compatibility.

---

## Consequences

### Positive
✅ **Single code path** for bundle creation across all data sources
✅ **Automatic metadata tracking** - no manual catalog updates
✅ **Live/backtest unification** - same DataSource for both modes
✅ **Extensibility** - new adapters just implement interface
✅ **Testability** - mock DataSource for unit tests

### Negative
⚠️ **Migration effort** - 6 adapters to refactor (1 week)
⚠️ **Breaking changes risk** - requires backwards compatibility layer
⚠️ **Learning curve** - developers must understand new abstraction

### Neutral
- Old adapter APIs deprecated but functional (with warnings)
- Bundle creation logic moves from scripts to adapter methods
- DataPortal accepts DataSource instead of readers

---

## Alternatives Considered

### Alternative 1: Keep Adapters + Bundles Separate
**Rejected because:**
- Perpetuates fragmentation (3 systems stay disconnected)
- Manual scripting burden continues
- Epic 7 remains blocked indefinitely

### Alternative 2: Create Adapter-Specific Ingest Scripts
**Rejected because:**
- Code duplication (6 scripts with similar logic)
- Metadata tracking inconsistent per script
- Hard to maintain (changes must update all scripts)

### Alternative 3: Use Adapter Composition (Decorators)
**Rejected because:**
- Adds complexity (decorators on top of adapters)
- Implicit behavior (magic wrapper functions)
- Harder to debug (stack traces through decorators)

---

## Implementation Notes

### Phase 1: Bridge Pattern (Immediate)
Create temporary `adapter_bundles.py` with bridge functions:
- `yfinance_profiling_bundle()` - unblocks Epic 7
- `ccxt_profiling_bundle()` - hourly/minute scenarios
- Mark as `@deprecated` immediately

### Phase 2: Unified Interface (1 week)
Refactor adapters to implement `DataSource`:
- Maintain `fetch_ohlcv()` for backwards compatibility
- Add `ingest_to_bundle()` method
- Register with `DataSourceRegistry`

### Phase 3: Deprecation (v2.0)
Remove bridge functions and old APIs:
- 6-12 month deprecation period
- Migration guide provided
- Breaking change in major version

---

## Metrics for Success

- [ ] All 6 adapters implement `DataSource` interface
- [ ] Backwards compatibility: existing code works with warnings
- [ ] Test coverage: ≥90% for DataSource implementations
- [ ] Performance: <5% overhead vs direct adapter calls
- [ ] Epic 7 unblocked within 2 days (bridge functions)

---

## Related Decisions
- [ADR 002: Unified Metadata Schema](002-unified-metadata-schema.md)
- [ADR 003: Smart Caching Layer](003-smart-caching-layer.md)

---

## References
- [Epic X1 PRD](../../prd/epic-X1-unified-data-architecture.md)
- [Story X1.1: Adapter-Bundle Bridge](../../stories/X1.1.adapter-bundle-bridge.story.md)
- [Epic X1 Architecture](../epic-X1-unified-data-architecture.md)
