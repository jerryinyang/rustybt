# Rust Optimizations Performance Benchmarks

**Date**: 2025-01-09
**Platform**: macOS (Apple Silicon)
**Python**: 3.13.1
**Rust**: 1.90+

## Summary

This document contains performance benchmarks comparing Rust-optimized implementations
against pure Python implementations for performance-critical operations in RustyBT.

## Benchmark Results

### Key Findings

| Operation | Dataset Size | Python (μs) | Rust (μs) | Speedup |
|-----------|-------------|-------------|-----------|---------|
| composite_indicator | small | 1947.63 | 2425.12 | **0.80x** |
| create_columns | small | 27.56 | 246.46 | **0.11x** |
| ema | large | 630.70 | 594.24 | **1.06x** |
| ema | small | 4.51 | 5.85 | **0.77x** |
| fillna | large | 284.23 | 560.19 | **0.51x** |
| index_select | large | 15.81 | 443.51 | **0.04x** |
| mean | large | 31.89 | 424.48 | **0.08x** |
| pairwise_add | large | 329.12 | 985.47 | **0.33x** |
| rolling_sum | large | 675.31 | 586.59 | **1.15x** |
| slice | large | 28.24 | 565.44 | **0.05x** |
| sma | large | 849.60 | 578.08 | **1.47x** |
| sma | medium | 78.41 | 56.69 | **1.38x** |
| sma | small | 6.08 | 5.72 | **1.06x** |
| sum | large | 31.75 | 423.26 | **0.08x** |


### Detailed Results


#### python_sma_small

- **Mean**: 0.0061 ms
- **Min**: 0.0057 ms
- **Max**: 0.0909 ms
- **StdDev**: 0.0012 ms
- **Median**: 0.0060 ms
- **Rounds**: 60300


#### rust_sma_small

- **Mean**: 0.0057 ms
- **Min**: 0.0055 ms
- **Max**: 0.0371 ms
- **StdDev**: 0.0009 ms
- **Median**: 0.0056 ms
- **Rounds**: 27682


#### python_sma_medium

- **Mean**: 0.0784 ms
- **Min**: 0.0757 ms
- **Max**: 0.1982 ms
- **StdDev**: 0.0046 ms
- **Median**: 0.0773 ms
- **Rounds**: 10148


#### rust_sma_medium

- **Mean**: 0.0567 ms
- **Min**: 0.0555 ms
- **Max**: 0.2289 ms
- **StdDev**: 0.0035 ms
- **Median**: 0.0562 ms
- **Rounds**: 14177


#### python_sma_large

- **Mean**: 0.8496 ms
- **Min**: 0.8347 ms
- **Max**: 1.0256 ms
- **StdDev**: 0.0193 ms
- **Median**: 0.8434 ms
- **Rounds**: 1117


#### rust_sma_large

- **Mean**: 0.5781 ms
- **Min**: 0.5619 ms
- **Max**: 1.2295 ms
- **StdDev**: 0.0242 ms
- **Median**: 0.5761 ms
- **Rounds**: 1629


#### python_ema_small

- **Mean**: 0.0045 ms
- **Min**: 0.0043 ms
- **Max**: 0.0638 ms
- **StdDev**: 0.0006 ms
- **Median**: 0.0045 ms
- **Rounds**: 96386


#### rust_ema_small

- **Mean**: 0.0059 ms
- **Min**: 0.0056 ms
- **Max**: 0.1361 ms
- **StdDev**: 0.0010 ms
- **Median**: 0.0058 ms
- **Rounds**: 80264


#### python_ema_large

- **Mean**: 0.6307 ms
- **Min**: 0.6244 ms
- **Max**: 0.6943 ms
- **StdDev**: 0.0073 ms
- **Median**: 0.6290 ms
- **Rounds**: 1434


#### rust_ema_large

- **Mean**: 0.5942 ms
- **Min**: 0.5772 ms
- **Max**: 0.8388 ms
- **StdDev**: 0.0154 ms
- **Median**: 0.5921 ms
- **Rounds**: 1556


#### python_sum_large

- **Mean**: 0.0317 ms
- **Min**: 0.0292 ms
- **Max**: 0.1275 ms
- **StdDev**: 0.0021 ms
- **Median**: 0.0315 ms
- **Rounds**: 31373


#### rust_sum_large

- **Mean**: 0.4233 ms
- **Min**: 0.4089 ms
- **Max**: 0.6262 ms
- **StdDev**: 0.0122 ms
- **Median**: 0.4239 ms
- **Rounds**: 2224


#### python_mean_large

- **Mean**: 0.0319 ms
- **Min**: 0.0289 ms
- **Max**: 0.1420 ms
- **StdDev**: 0.0022 ms
- **Median**: 0.0316 ms
- **Rounds**: 31662


#### rust_mean_large

- **Mean**: 0.4245 ms
- **Min**: 0.4085 ms
- **Max**: 0.9825 ms
- **StdDev**: 0.0194 ms
- **Median**: 0.4241 ms
- **Rounds**: 2261


#### python_rolling_sum_large

- **Mean**: 0.6753 ms
- **Min**: 0.6658 ms
- **Max**: 0.8870 ms
- **StdDev**: 0.0131 ms
- **Median**: 0.6715 ms
- **Rounds**: 1410


#### rust_rolling_sum_large

- **Mean**: 0.5866 ms
- **Min**: 0.5696 ms
- **Max**: 0.7833 ms
- **StdDev**: 0.0137 ms
- **Median**: 0.5856 ms
- **Rounds**: 1618


#### python_slice_large

- **Mean**: 0.0282 ms
- **Min**: 0.0193 ms
- **Max**: 0.1437 ms
- **StdDev**: 0.0058 ms
- **Median**: 0.0312 ms
- **Rounds**: 27908


#### rust_slice_large

- **Mean**: 0.5654 ms
- **Min**: 0.5497 ms
- **Max**: 0.8407 ms
- **StdDev**: 0.0144 ms
- **Median**: 0.5641 ms
- **Rounds**: 1484


#### python_index_select_large

- **Mean**: 0.0158 ms
- **Min**: 0.0153 ms
- **Max**: 0.1020 ms
- **StdDev**: 0.0010 ms
- **Median**: 0.0157 ms
- **Rounds**: 23033


#### rust_index_select_large

- **Mean**: 0.4435 ms
- **Min**: 0.4278 ms
- **Max**: 0.6139 ms
- **StdDev**: 0.0127 ms
- **Median**: 0.4435 ms
- **Rounds**: 2071


#### python_fillna_large

- **Mean**: 0.2842 ms
- **Min**: 0.2691 ms
- **Max**: 0.5845 ms
- **StdDev**: 0.0099 ms
- **Median**: 0.2828 ms
- **Rounds**: 3374


#### rust_fillna_large

- **Mean**: 0.5602 ms
- **Min**: 0.5497 ms
- **Max**: 0.9547 ms
- **StdDev**: 0.0152 ms
- **Median**: 0.5565 ms
- **Rounds**: 1448


#### python_pairwise_add_large

- **Mean**: 0.3291 ms
- **Min**: 0.3224 ms
- **Max**: 0.7389 ms
- **StdDev**: 0.0134 ms
- **Median**: 0.3256 ms
- **Rounds**: 2966


#### rust_pairwise_add_large

- **Mean**: 0.9855 ms
- **Min**: 0.9506 ms
- **Max**: 2.0728 ms
- **StdDev**: 0.0515 ms
- **Median**: 0.9762 ms
- **Rounds**: 970


#### python_create_columns

- **Mean**: 0.0276 ms
- **Min**: 0.0252 ms
- **Max**: 0.0881 ms
- **StdDev**: 0.0020 ms
- **Median**: 0.0276 ms
- **Rounds**: 11242


#### rust_create_columns

- **Mean**: 0.2465 ms
- **Min**: 0.2423 ms
- **Max**: 0.3755 ms
- **StdDev**: 0.0070 ms
- **Median**: 0.2443 ms
- **Rounds**: 3055


#### python_composite_indicator

- **Mean**: 1.9476 ms
- **Min**: 1.9137 ms
- **Max**: 2.5496 ms
- **StdDev**: 0.0403 ms
- **Median**: 1.9379 ms
- **Rounds**: 502


#### rust_composite_indicator

- **Mean**: 2.4251 ms
- **Min**: 2.3795 ms
- **Max**: 2.9770 ms
- **StdDev**: 0.0472 ms
- **Median**: 2.4153 ms
- **Rounds**: 406


## Analysis & Conclusions

### Key Finding: Conversion Overhead Dominates Simple Operations

The benchmarks reveal a **critical insight** about Python/Rust integration:

**Python↔Rust conversion overhead** (allocating Vec, copying data, converting back) is **much more expensive** than simple computations for small-to-medium datasets.

### What Works (Rust Faster)

Operations where Rust shows **real speedups**:

1. **SMA (Simple Moving Average)**:
   - Small (100 elements): 1.06× speedup
   - Medium (1,000 elements): 1.38× speedup
   - **Large (10,000 elements): 1.47× speedup** ✅

2. **EMA (Exponential Moving Average)**:
   - Large (10,000 elements): 1.06× speedup ✅

3. **Rolling Sum**:
   - **Large (10,000 elements): 1.15× speedup** ✅

**Why these work**: Complex multi-pass algorithms where **computation cost >> conversion cost**

### What Doesn't Work (Rust Slower)

Operations where Rust shows **performance regressions**:

1. **Simple Array Operations** (sum, mean, index_select):
   - **0.04-0.08× speedup = 12-25× SLOWER** ❌
   - **Root cause**: 2 allocations + 2 full data copies for trivial work
   - Python builtins (written in C) are faster than Rust when you factor in conversion

2. **DataFrame Operations** (slice, fillna, create_columns):
   - **0.05-0.51× speedup = 2-20× SLOWER** ❌
   - **Root cause**: Polars is already Rust-backed and optimized
   - Adding another Rust layer just adds overhead

3. **Small Datasets** (< 1,000 elements):
   - Even complex operations show minimal or no speedup
   - Conversion overhead dominates

### Lesson Learned: Use Rust Selectively

**✅ Good use cases for custom Rust:**
- Complex algorithms (SMA, EMA, indicators) with **large datasets** (10,000+ elements)
- Operations with multiple passes over data
- Situations where computation cost >> conversion cost

**❌ Bad use cases for custom Rust:**
- Simple operations (sum, mean, index selection)
- Operations on small datasets (< 1,000 elements)
- Operations that Polars/NumPy already optimize (DataFrame manipulation)
- Any operation where Python builtins (C-optimized) are available

### Why DataPortal Doesn't Use Custom Rust

The profiling identified `DataPortal.history()` as a bottleneck (61.5% of runtime), but:

1. **Polars is already Rust-backed** - adding our own Rust layer just adds overhead
2. **Benchmarks confirmed**: `rust_index_select` is **25× slower** than Python (0.04× speedup)
3. **Better solution**: Let Polars do what it does best (DataFrame operations)

**Our Rust optimizations are available** for custom indicators and strategies where they provide real value.

## Recommendations

### For Strategy Developers

**Use Rust optimizations when**:
- Implementing custom technical indicators on large datasets
- Processing 10,000+ data points
- Doing multi-pass calculations (rolling windows, moving averages)

**Don't use Rust when**:
- Working with small datasets (< 1,000 points)
- Doing simple operations (sum, mean, basic math)
- Using Polars/pandas DataFrame operations (already optimized)

### For Future Optimization

1. **Profile first**: Measure before optimizing
2. **Let libraries do their job**: Polars, NumPy, pandas are already highly optimized
3. **Consider batch processing**: Amortize conversion overhead by processing larger chunks
4. **Measure actual gains**: Don't assume Rust is always faster

## Next Steps

- ✅ Benchmarks captured and analyzed
- ✅ DataPortal kept using pure Polars (already optimal)
- ⏭ Run end-to-end backtest profiling to measure actual impact
- ⏭ Document which operations benefit from Rust in production use
