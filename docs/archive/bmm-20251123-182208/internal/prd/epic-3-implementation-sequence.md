# Epic 3: Modern Data Architecture - Implementation Sequence

**Status**: Ready for Implementation ✅
**Last Updated**: 2025-10-01
**Epic Goal**: Replace Zipline-Reloaded's HDF5 storage with modern Polars/Parquet-based unified data catalog featuring intelligent local caching and core data source adapters.

---

## Implementation Phases

### Phase 1: Foundation & Design (3-5 days)

**Story 3.1: Design Unified Data Catalog Architecture**
- **Status**: FIRST - Must complete before all other stories
- **Duration**: 3-5 days
- **Output**: [docs/architecture/data-catalog.md](docs/architecture/data-catalog.md)
- **Type**: Design/Documentation only (NO code implementation)
- **Dependencies**: None
- **Blocks**: Stories 3.2, 3.3, 3.8

**Why First?**
- Establishes architectural foundation
- Defines interfaces and contracts for all other stories
- Provides blueprint for Parquet schema, cache design, and data flows

---

### Phase 2: Core Infrastructure (8-12 days, parallel execution)

#### Track A: Storage Layer (5-7 days)

**Story 3.2: Implement Parquet Storage Layer with Metadata Catalog**
- **Status**: Ready after 3.1 completes
- **Duration**: 5-7 days
- **Dependencies**: Story 3.1 ✓
- **Blocks**: Stories 3.3, 3.8
- **Can Run in Parallel With**: Story 3.4

**Key Deliverables:**
- PolarsParquetDailyReader
- PolarsParquetMinuteReader
- SQLite metadata catalog
- HDF5 to Parquet migration utility

#### Track B: Adapter Framework (3-5 days)

**Story 3.4: Implement Base Data Adapter Framework**
- **Status**: Ready after 3.1 completes (can start in parallel with 3.2)
- **Duration**: 3-5 days
- **Dependencies**: Story 3.1 ✓
- **Blocks**: Stories 3.5, 3.6, 3.7
- **Can Run in Parallel With**: Story 3.2

**Key Deliverables:**
- BaseDataAdapter abstract class
- RateLimiter implementation
- Validation framework
- Adapter registration system

---

### Phase 3: Caching + Data Adapters (10-18 days, parallel execution)

#### Track A: Caching System (5-7 days)

**Story 3.3: Implement Intelligent Local Caching System**
- **Status**: Ready after 3.2 completes
- **Duration**: 5-7 days
- **Dependencies**: Story 3.2 ✓
- **Blocks**: None (standalone feature)
- **Can Run in Parallel With**: Stories 3.5, 3.6, 3.7

**Key Deliverables:**
- Two-tier cache (hot/cold)
- Cache key generation
- Backtest linkage
- Cache statistics API

#### Track B: Data Source Adapters (parallel, 3-4 days each)

**Story 3.5: Implement CCXT Data Adapter**
- **Status**: Ready after 3.4 completes
- **Duration**: 3-4 days
- **Priority**: MVP - Crypto
- **Dependencies**: Story 3.4 ✓
- **Can Run in Parallel With**: Stories 3.3, 3.6, 3.7

**Story 3.6: Implement YFinance Data Adapter**
- **Status**: Ready after 3.4 completes
- **Duration**: 3-4 days
- **Priority**: MVP - Stocks/ETFs
- **Dependencies**: Story 3.4 ✓
- **Can Run in Parallel With**: Stories 3.3, 3.5, 3.7

**Story 3.7: Implement CSV Data Adapter with Schema Mapping**
- **Status**: Ready after 3.4 completes
- **Duration**: 2-3 days
- **Priority**: MVP
- **Dependencies**: Story 3.4 ✓
- **Can Run in Parallel With**: Stories 3.3, 3.5, 3.6

---

### Phase 4: Advanced Features (4-6 days)

**Story 3.8: Implement Multi-Resolution Aggregation with OHLCV Validation**
- **Status**: Ready after 3.2 completes
- **Duration**: 4-6 days
- **Dependencies**: Story 3.2 ✓ (required), Stories 3.5-3.7 (optional for testing)
- **Blocks**: None

**Key Deliverables:**
- Aggregation functions (minute→hourly, hourly→daily, etc.)
- OHLCV validation
- Timezone-aware aggregation
- Gap detection
- Outlier detection

**Note**: Can begin after 3.2, but benefits from having 3.5-3.7 complete for integration testing with real data sources.

---

## Recommended Execution Strategy

### Option A: Maximum Parallelization (Fastest - 25-33 days)

```
Week 1: Story 3.1 (Design)
Week 2-3: Stories 3.2 + 3.4 (parallel)
Week 3-4: Stories 3.3 + 3.5 + 3.6 + 3.7 (parallel after prerequisites)
Week 4-5: Story 3.8
```

**Team Requirements**: 3-4 developers
**Risk**: Higher coordination overhead
**Benefit**: Fastest completion

### Option B: Sequential Tracks (Balanced - 30-40 days)

```
Week 1: Story 3.1 (Design)
Week 2-3: Story 3.2 (Storage)
Week 3-4: Story 3.4 (Adapter Framework)
Week 4: Story 3.3 (Caching)
Week 4-6: Stories 3.5, 3.6, 3.7 (Adapters, sequential or 2 parallel)
Week 6-7: Story 3.8 (Aggregation)
```

**Team Requirements**: 2 developers
**Risk**: Lower
**Benefit**: Better quality control, easier code review

### Option C: Single Developer (Conservative - 35-45 days)

```
Week 1: Story 3.1
Week 2-3: Story 3.2
Week 4: Story 3.4
Week 5: Story 3.3
Week 6: Story 3.5
Week 7: Story 3.6
Week 8: Story 3.7
Week 9: Story 3.8
```

**Team Requirements**: 1 developer
**Risk**: Lowest
**Benefit**: Deep context, no coordination overhead

---

## Critical Path Analysis

### Longest Path (Critical Path)
```
3.1 (5d) → 3.2 (7d) → 3.8 (6d) = 18 days minimum
```

### Parallel Opportunities
- **After 3.1**: Start 3.2 AND 3.4 simultaneously
- **After 3.4**: Start 3.5, 3.6, 3.7 simultaneously (if team size allows)
- **After 3.2**: Start 3.3 AND 3.8 simultaneously

### Bottleneck Stories
- **Story 3.1**: Blocks everything (design must be complete)
- **Story 3.4**: Blocks all adapters (3.5, 3.6, 3.7)
- **Story 3.2**: Blocks caching (3.3) and aggregation (3.8)

---

## Story Dependencies Graph

```
                    ┌─────────┐
                    │  3.1    │ (Design)
                    │ Design  │
                    └────┬────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────▼─────┐  ┌────▼────┐    [3.8 can start]
    │   3.2     │  │   3.4   │         │
    │  Parquet  │  │  Base   │         │
    └─────┬─────┘  │ Adapter │         │
          │        └────┬────┘         │
          │             │              │
    ┌─────▼─────┐      │              │
    │   3.3     │      │              │
    │  Caching  │      │              │
    └───────────┘      │              │
          │            │              │
    ┌─────▼────────────▼───────┐     │
    │   3.5, 3.6, 3.7          │     │
    │   Data Adapters          │     │
    │   (CCXT, YFin, CSV)      │     │
    └──────────────────────────┘     │
                                     │
                              ┌──────▼──────┐
                              │     3.8     │
                              │ Aggregation │
                              └─────────────┘
```

---

## Quality Gates

### After Phase 1 (Story 3.1)
- [ ] Architecture document approved by stakeholders
- [ ] All interface contracts clearly defined
- [ ] Schema designs validated
- [ ] Migration plan documented

### After Phase 2 (Stories 3.2, 3.4)
- [ ] Parquet read/write roundtrip tests passing
- [ ] Decimal precision preserved in all operations
- [ ] BaseDataAdapter interface complete and documented
- [ ] Migration utility successfully converts sample HDF5 data

### After Phase 3 (Stories 3.3, 3.5-3.7)
- [ ] Cache hit performance <1 second verified
- [ ] All adapters fetch live data successfully
- [ ] Integration tests passing for each adapter
- [ ] Example notebooks demonstrate each data source

### After Phase 4 (Story 3.8)
- [ ] Aggregation accuracy validated with known examples
- [ ] Property-based tests passing (1000+ examples)
- [ ] Performance targets met (1M bars/second)
- [ ] Epic 3 acceptance criteria fully satisfied

---

## Risk Mitigation

### High Priority Risks

1. **Story 3.2 Complexity**
   - Risk: Parquet/SQLite integration more complex than estimated
   - Mitigation: Complete Story 3.1 design thoroughly; consider adding buffer time
   - Contingency: Split 3.2 into 3.2a (write path) and 3.2b (read path)

2. **External API Stability** (Stories 3.5-3.7)
   - Risk: CCXT/YFinance API changes during implementation
   - Mitigation: Use versioned dependencies; implement comprehensive error handling
   - Contingency: Add adapter version compatibility matrix

3. **Performance Targets** (Stories 3.3, 3.8)
   - Risk: Cache/aggregation performance below targets
   - Mitigation: Early performance benchmarking; use Polars lazy evaluation
   - Contingency: Optimize after functional completion; adjust targets if needed

### Medium Priority Risks

4. **HDF5 Migration Utility** (Story 3.2)
   - Risk: Legacy Zipline data formats vary
   - Mitigation: Test with multiple bundle formats; document unsupported cases
   - Contingency: Provide manual migration guide for edge cases

5. **Coordination Overhead** (Parallel execution)
   - Risk: Merge conflicts and integration issues with parallel work
   - Mitigation: Clear interface boundaries; frequent integration testing
   - Contingency: Reduce parallelization if coordination cost too high

---

## Success Metrics

### Completion Criteria
- [ ] All 8 stories marked as "Done"
- [ ] All acceptance criteria satisfied
- [ ] Test coverage ≥90% for new components
- [ ] Zero critical bugs in production

### Performance Metrics
- [ ] Cache hit latency <1 second (Story 3.3, AC#4)
- [ ] Parquet compression 50-80% vs HDF5 (Story 3.2, AC#6)
- [ ] Aggregation throughput ≥1M bars/second (Story 3.8, AC#6)

### Quality Metrics
- [ ] Zero-Mock enforcement: 100% compliance
- [ ] Decimal precision: 100% roundtrip accuracy
- [ ] Property-based tests: 1000+ examples passing

---

## Next Steps

1. **Review and Approve**: Team reviews this implementation sequence
2. **Resource Allocation**: Assign developers to stories/phases
3. **Environment Setup**: Ensure dev environments have required tools (Polars, pytz, etc.)
4. **Kickoff Story 3.1**: Begin design phase
5. **Daily Standups**: Track progress against sequence
6. **Weekly Integration**: Merge and test completed stories

---

## Document History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-10-01 | 1.0 | Initial implementation sequence | Sarah (PO) |
