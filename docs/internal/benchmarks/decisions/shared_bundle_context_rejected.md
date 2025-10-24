# SharedBundleContext Optimization - REJECTED

**Date:** 2025-10-23  
**Story:** X4.7 Phase 6B Heavy Operations Optimization  
**Rank:** #1 (13% expected improvement)  
**Decision:** ❌ **REJECTED**

## Summary

SharedBundleContext optimization was **rejected** due to architectural incompatibility with current bundle structure. Bundle data contains non-picklable sqlite3.Connection objects, preventing serialization to shared memory.

## Decision Criteria

Per Story X4.7 AC#1:
- ✅ Functional equivalence validated BEFORE performance measurement (BLOCKING)
- ❌ **FAILED**: Cannot serialize bundle data to shared memory
- Performance benchmarking: **NOT EXECUTED** (blocked by serialization failure)

## Technical Analysis

### Root Cause

```python
# Bundle structure contains non-picklable components
BundleData(
    asset_finder=...,  # Contains sqlite3.Connection
    adjustment_reader=...,  # Contains sqlite3.Connection
    # ... other readers with database connections
)
```

### Attempted Serialization

```
TypeError: cannot pickle 'sqlite3.Connection' object
```

### Why This Matters

The current bundle architecture relies on SQLite connections for:
1. Asset metadata queries
2. Adjustment data access
3. Symbology lookups

These connections cannot be serialized to shared memory without significant architectural changes.

## Alternative Approaches Considered

1. **Selective Serialization** - Only serialize data-only components
   - ❌ Incomplete: Would require redesigning bundle access patterns
   
2. **Connection Recreation** - Serialize connection strings, recreate in workers
   - ❌ Complex: Defeats purpose of shared memory (workers still recreate)
   
3. **Custom Pickle Protocol** - Implement `__getstate__`/`__setstate__` for BundleData
   - ❌ High Risk: Requires modifying core bundle infrastructure

## Recommendation

**REJECT SharedBundleContext** for Phase 6B.

Consider for future work:
- Refactor bundle architecture to separate data (picklable) from connections (per-worker)
- Implement lazy connection initialization pattern
- Use memory-mapped files for asset metadata instead of SQLite

## Impact

- Expected improvement: 13%
- Actual improvement: **0%** (not viable)
- Sequential evaluation continues with remaining optimizations

## Benchmark Configuration

- Bundle: mag-7 (8 symbols, 40,987 rows, yfinance data)
- Workers: 8
- Configuration: Per Story X4.7 requirements

## References

- Story: `docs/internal/stories/X4.7.heavy-operations-optimization.story.md`
- Implementation: `rustybt/optimization/shared_bundle_context.py`
- Tests: `tests/optimization/test_shared_bundle_context.py`
