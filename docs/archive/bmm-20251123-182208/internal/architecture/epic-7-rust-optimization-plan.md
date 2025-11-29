# Epic 7: Rust Optimization Plan

**Version:** 1.0
**Date:** 2025-10-01
**Status:** Planning (Epic 2 complete, Epic 7 pending)

## Executive Summary

This document outlines the optimization strategy for Epic 7 (Rust Optimization) based on performance baselines established in Story 2.7. The goal is to reduce Decimal implementation overhead from current levels to <30% compared to float baseline, with stretch goal of <12% overhead.

## Performance Baseline (Current State)

From Story 2.7 benchmarks (8 of 8 passing):

### Overall Performance
- **Portfolio calculations:** ~111% overhead (2.1x slower than float)
- **Sharpe ratio:** ~3162% overhead (32x slower) - **MAJOR HOTSPOT**
- **Data aggregation:** ~14,555% overhead (146x slower) - **CRITICAL HOTSPOT**
- **Order processing:** ~29% overhead (1.29x slower)
- **Max drawdown:** ~67% overhead (1.67x slower)

### Key Findings
1. **Metrics calculations** (Sharpe, drawdown) show extreme overhead due to Polars Decimal operations
2. **Data aggregation** on Decimal columns is significantly slower than float
3. **Core arithmetic** (portfolio value, order fills) shows moderate ~30% overhead
4. **Memory overhead:** Expected 100-150% (2-2.5x memory usage)

## Optimization Targets (Epic 7)

### Primary Goal
**Reduce overall Decimal overhead to <30% vs float baseline**

### Module-Specific Targets

| Module | Current Overhead | Target Overhead | Priority |
|--------|------------------|-----------------|----------|
| **Decimal Arithmetic** | ~30% | <15% | P0 - Highest |
| **Metrics Calculations** | ~3162% | <50% | P0 - Critical |
| **Data Aggregation** | ~14,555% | <100% | P0 - Critical |
| **Order Execution** | ~29% | <15% | P1 - High |
| **Portfolio Calculations** | ~111% | <30% | P1 - High |
| **Memory Footprint** | ~150% | <120% | P2 - Medium |

## Optimization Strategy

### Phase 1: Core Decimal Arithmetic (P0)

**Rationale:** Decimal arithmetic is the foundation - optimizing it benefits all modules.

**Approach:**
- Implement core Decimal operations in Rust using `rust-decimal` crate
- Operations: addition, subtraction, multiplication, division
- Create PyO3 bindings for seamless Python integration
- Target: 50-70% reduction in arithmetic overhead

**Estimated Impact:**
- Directly benefits: portfolio calculations, order fills, commission calculations
- Indirectly benefits: all downstream computations

**Implementation:**
```rust
// rustybt/rust/src/decimal.rs
use pyo3::prelude::*;
use rust_decimal::Decimal;

#[pyfunction]
fn decimal_multiply(a: &str, b: &str) -> PyResult<String> {
    let dec_a = Decimal::from_str_exact(a)?;
    let dec_b = Decimal::from_str_exact(b)?;
    Ok((dec_a * dec_b).to_string())
}
```

### Phase 2: Metrics Calculations (P0)

**Rationale:** Metrics show 3162% overhead - largest optimization opportunity.

**Approach:**
- Implement Sharpe ratio calculation in Rust with SIMD vectorization
- Implement max drawdown in Rust with cumulative max optimization
- Batch process returns series to minimize Python/Rust boundary crossings
- Target: 90% reduction in metrics overhead

**Key Optimizations:**
1. **SIMD operations** for mean/std calculations
2. **Parallel processing** for large return series
3. **Zero-copy** data transfer via Apache Arrow
4. **Batching** to amortize function call overhead

**Estimated Impact:**
- Sharpe ratio: 3162% → <300% overhead
- Max drawdown: 67% → <20% overhead

### Phase 3: Data Aggregation (P0)

**Rationale:** Data aggregation shows 14,555% overhead - critical bottleneck.

**Approach:**
- Optimize Polars Decimal column operations
- Implement custom Rust aggregators for OHLCV data
- Use Arrow compute kernels where possible
- Target: 95% reduction in aggregation overhead

**Key Optimizations:**
1. **Native Decimal support** in Arrow compute kernels
2. **Chunked processing** to improve cache locality
3. **Lazy evaluation** to eliminate redundant computations

**Estimated Impact:**
- Data aggregation: 14,555% → <500% overhead
- Still higher than float, but acceptable for Decimal precision

### Phase 4: Order Execution (P1)

**Rationale:** Already relatively efficient (29%), but optimization still valuable.

**Approach:**
- Batch order processing to reduce overhead
- Optimize commission calculations in Rust
- Implement fast path for common order types
- Target: 50% reduction in order overhead

**Estimated Impact:**
- Order processing: 29% → <15% overhead

### Phase 5: Portfolio Calculations (P1)

**Rationale:** Benefits from Phase 1 arithmetic improvements.

**Approach:**
- Vectorize portfolio value calculations
- Optimize position iteration and aggregation
- Cache intermediate results where safe
- Target: 70% reduction in portfolio overhead

**Estimated Impact:**
- Portfolio value: 111% → <30% overhead

### Phase 6: Memory Optimization (P2)

**Rationale:** Lower priority - memory is cheaper than correctness.

**Approach:**
- Use compact Decimal representation (Decimal128 vs Decimal256)
- Implement memory pooling for frequent allocations
- Lazy evaluation to avoid materializing intermediate results
- Target: 20% reduction in memory overhead

**Estimated Impact:**
- Memory usage: 150% → <120% overhead (2.2x → 1.8x)

## Technology Stack (Epic 7)

### Rust Dependencies
```toml
[dependencies]
pyo3 = "0.26"              # Python bindings
rust_decimal = "1.37"      # High-performance Decimal
arrow = "54"               # Zero-copy data exchange
rayon = "1.10"             # Parallel processing
num-traits = "0.2"         # Numeric traits
```

### PyO3 Integration Pattern
```python
# Import Rust-optimized functions
from rustybt.rust import (
    decimal_multiply,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    aggregate_ohlcv,
)

# Fallback to Python implementation if Rust unavailable
try:
    from rustybt.rust import decimal_multiply
except ImportError:
    from rustybt.finance.decimal import decimal_multiply
```

## Implementation Priorities

### Sprint 1 (2 weeks): Setup & Core Arithmetic
- [ ] Setup Rust project structure with PyO3
- [ ] Implement core Decimal arithmetic operations
- [ ] Create Python bindings
- [ ] Write benchmarks and validate correctness
- [ ] Achieve <15% overhead on arithmetic operations

### Sprint 2 (2 weeks): Metrics Calculations
- [ ] Implement Sharpe ratio in Rust
- [ ] Implement max drawdown in Rust
- [ ] Add SIMD optimizations
- [ ] Benchmark and validate
- [ ] Achieve <300% overhead on Sharpe ratio

### Sprint 3 (2 weeks): Data Aggregation
- [ ] Implement OHLCV aggregation in Rust
- [ ] Optimize Arrow/Polars integration
- [ ] Add parallel processing
- [ ] Benchmark and validate
- [ ] Achieve <500% overhead on aggregation

### Sprint 4 (1 week): Order & Portfolio
- [ ] Optimize order processing
- [ ] Optimize portfolio calculations
- [ ] Benchmark and validate
- [ ] Achieve <15% overhead on orders, <30% on portfolio

### Sprint 5 (1 week): Integration & Testing
- [ ] End-to-end integration testing
- [ ] Property-based testing with Hypothesis
- [ ] Performance regression testing
- [ ] Documentation updates

## Success Criteria

### Must Have (Epic 7 Completion)
- ✅ Overall Decimal overhead <30% vs float baseline
- ✅ All benchmarks passing with Rust optimizations
- ✅ Property-based tests validate correctness
- ✅ No regressions in existing functionality
- ✅ Documentation updated with Rust setup instructions

### Nice to Have (Stretch Goals)
- 🎯 Overall overhead <12% (aggressive target)
- 🎯 Metrics calculations within 2x of float performance
- 🎯 Memory overhead <120%
- 🎯 Parallel processing for large datasets

## Risk Mitigation

### Risk 1: Rust Complexity
**Mitigation:** Start with simple operations, gradual complexity increase

### Risk 2: PyO3 Overhead
**Mitigation:** Batch operations to amortize binding overhead, use zero-copy where possible

### Risk 3: Correctness Concerns
**Mitigation:** Extensive property-based testing, cross-validation with Python implementation

### Risk 4: Maintenance Burden
**Mitigation:** Rust code as optional optimization, Python fallback always available

## Benchmarking & Validation

### Continuous Benchmarking
- Run benchmarks on every PR
- Track performance trends over time
- Fail CI if regression >10%

### Validation Strategy
1. **Correctness:** Property-based tests verify Rust == Python results
2. **Performance:** Benchmarks track overhead reduction
3. **Regression:** Automated comparison with baseline

### Metrics Dashboard
Track key metrics:
- Arithmetic overhead: <15% target
- Metrics overhead: <300% target
- Aggregation overhead: <500% target
- Overall overhead: <30% target
- Memory footprint: <120% target

## Alternative Approaches Considered

### 1. Numba JIT Compilation
**Rejected:** Doesn't support Decimal type natively

### 2. Cython Optimization
**Rejected:** Rust provides better performance and safety

### 3. Native float64 + Rounding
**Rejected:** Violates audit compliance requirements (NFR1)

### 4. Database-backed Decimal
**Rejected:** Too slow for real-time trading

## Timeline & Milestones

| Milestone | Target Date | Deliverables |
|-----------|-------------|--------------|
| Epic 7 Kickoff | TBD | Rust environment setup |
| Sprint 1 Complete | +2 weeks | Core arithmetic <15% overhead |
| Sprint 2 Complete | +4 weeks | Metrics <300% overhead |
| Sprint 3 Complete | +6 weeks | Aggregation <500% overhead |
| Sprint 4 Complete | +7 weeks | Orders/Portfolio optimized |
| Sprint 5 Complete | +8 weeks | Integration testing done |
| Epic 7 Complete | +8 weeks | All targets achieved |

## Conclusion

Epic 7 Rust optimization is essential to make RustyBT production-ready. The strategy focuses on:

1. **High-impact wins:** Metrics and aggregation show extreme overhead - biggest ROI
2. **Incremental approach:** Start simple (arithmetic), build complexity gradually
3. **Safety first:** Property-based testing ensures correctness maintained
4. **Optional optimization:** Python fallback ensures project remains accessible

**Success = <30% overall overhead while maintaining Decimal precision and audit compliance.**

---

*This plan will be refined based on profiling results and implementation learnings.*
