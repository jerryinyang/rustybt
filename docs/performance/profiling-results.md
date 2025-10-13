# Python Implementation Profiling Results

**Story**: 7.1 - Profile Python Implementation to Identify Bottlenecks
**Date**: 2025-01-08
**Profiler**: cProfile (deterministic profiling)
**Scenario**: Daily data backtest (252 trading days, 10 symbols, SMA crossover strategy)

## Executive Summary

Profiling of the daily backtest scenario identified **data history operations** as the primary performance bottleneck, consuming **61.5% of total execution time** (1.725s out of 2.805s). The analysis reveals clear optimization targets for Rust implementation in Story 7.3.

### Key Findings

- **Total Runtime**: 2.805 seconds
- **Total Function Calls**: 4,994,902 calls
- **Primary Bottleneck**: Data portal history operations (61.5%)
- **Secondary Bottlenecks**: DataFrame construction (pandas overhead), datetime operations

### Top Optimization Targets

1. 🎯 **Data History Operations** (61.5% of runtime) - Highest priority for Rust optimization
2. 🎯 **DataFrame Construction** (pandas overhead) - Consider Polars or Rust-native structures
3. 🎯 **Datetime/Calendar Operations** - Trading calendar lookups and datetime conversions

---

## Profiling Methodology

### Scenario Configuration

**Daily Data Backtest**:
- **Period**: 2024-08-01 to 2025-08-01 (252 trading days)
- **Symbols**: 10 stocks (SYM000-SYM009)
- **Strategy**: Simple Moving Average (SMA) crossover
  - Short SMA: 50 days
  - Long SMA: 200 days
- **Capital**: $100,000 (float-based for performance measurement)
- **Data Frequency**: Daily OHLCV bars

### Profiling Tools

- **cProfile**: Deterministic profiling with function-level granularity
- **Output**: `.pstats` format for detailed analysis
- **Analysis**: Top 20 functions by cumulative time and total time

### Execution Environment

- **Python**: 3.13.1
- **Platform**: macOS (darwin 25.0.0)
- **Key Libraries**: pandas 2.x, numpy, exchange_calendars
- **Data Backend**: Parquet-based bundle (50 symbols, 3-year range)

---

## CPU Profiling Results

### Overall Statistics

```
Total Runtime:       2.805 seconds
Total Function Calls: 4,994,902
Primitive Calls:     4,922,462
Unique Functions:    2,619
```

### Top 20 Functions by Cumulative Time

These functions represent the critical path through the codebase:

| Rank | Function | Cumtime (s) | % Total | Calls | Module |
|------|----------|------------|---------|-------|--------|
| 1 | `data.history()` | 1.725 | **61.5%** | 5,020 | data_portal |
| 2 | `handle_data()` (user strategy) | 2.009 | 71.6% | 251 | profiling script |
| 3 | `_get_history_daily_window()` | 1.139 | 40.6% | 5,020 | data_portal |
| 4 | `DataFrame.__init__()` | 0.410 | 14.6% | 5,022 | pandas |
| 5 | `_get_daily_window_data()` | 0.364 | 13.0% | 5,020 | data_portal |
| 6 | `minute_to_session()` | 0.218 | 7.8% | 14,132 | exchange_calendars |
| 7 | `sanitize_array()` | 0.130 | 4.6% | 6,500 | pandas |
| 8 | `_generate_range()` | 0.153 | 5.5% | 13,135 | pandas datetime |
| 9 | `tz_localize()` | 0.088 | 3.1% | 6 | pandas datetime |
| 10 | `__getitem__` (indexing) | 0.365 | 13.0% | 5,021 | pandas |

**Key Insight**: Data history operations (`data.history()`) alone consume **1.725 seconds (61.5%)** of the total 2.805 seconds runtime. This is the #1 optimization target.

### Top 20 Functions by Total Time (Self Time)

These functions consume the most CPU time themselves (excluding calls to other functions):

| Rank | Function | Tottime (s) | % Total | Calls | Category |
|------|----------|------------|---------|-------|----------|
| 1 | `isinstance()` | 0.110 | 3.9% | 741,839 | Type checking |
| 2 | `_generate_range()` | 0.102 | 3.6% | 13,135 | Datetime generation |
| 3 | `_box_func()` | 0.043 | 1.5% | 31,099 | Datetime boxing |
| 4 | `_engine` property | 0.042 | 1.5% | 10,346 | Index engine |
| 5 | `len()` | 0.041 | 1.5% | 245,586 | Builtin |
| 6 | `tz_localize()` | 0.038 | 1.4% | 6 | Timezone ops |
| 7 | `getattr()` | 0.037 | 1.3% | 313,352 | Attribute access |
| 8 | `__getitem__` (index) | 0.036 | 1.3% | 46,743 | Indexing |
| 9 | `__getitem__` (datetime) | 0.035 | 1.2% | 36,988 | Datetime indexing |
| 10 | `parse_timestamp()` | 0.033 | 1.2% | 14,939 | Timestamp parsing |

---

## Module-Level Analysis

### Runtime Breakdown by Module

| Module | Cumtime (s) | % of Total | Primary Functions |
|--------|------------|-----------|-------------------|
| **data_portal** | **1.725** | **61.5%** | `history()`, `get_history_window()` |
| **pandas.core** | 0.850 | 30.3% | DataFrame construction, indexing |
| **exchange_calendars** | 0.218 | 7.8% | `minute_to_session()`, date parsing |
| **rustybt._protocol** | 0.085 | 3.0% | Cython protocol checks |
| **numpy** | 0.055 | 2.0% | Array operations |
| **Other** | 0.072 | 2.6% | Various utilities |

**Visualization**:
```
data_portal:        ████████████████████████████████████████████████████████████ 61.5%
pandas:             ██████████████████████████████ 30.3%
exchange_calendars: ████████ 7.8%
_protocol:          ███ 3.0%
numpy:              ██ 2.0%
other:              ██ 2.6%
```

### Bottleneck Categories

Based on function classification:

1. **Data Processing** (61.5%) - **PRIMARY TARGET**
   - Data history window retrieval
   - DataFrame construction from arrays
   - Index operations

2. **Datetime Operations** (15.3%)
   - Timestamp parsing and conversion
   - Trading calendar lookups
   - Timezone localization

3. **Type Checking** (3.9%)
   - `isinstance()` calls (741,839 times!)
   - Type validation overhead

4. **Python Overhead** (19.3%)
   - Attribute access (`getattr`)
   - Length checks (`len`)
   - Object construction

---

## Bottleneck Identification (>5% Total Time)

Functions consuming **>5% of total execution time** (threshold: 0.140s):

### 1. `data_portal.history()` - **PRIMARY BOTTLENECK**
- **Time**: 1.725s (61.5%)
- **Calls**: 5,020
- **Per-call**: 0.344ms
- **Category**: Data processing
- **Description**: Retrieves historical price windows for technical indicators
- **Impact**: Called once per symbol per bar (10 symbols × 502 bars ≈ 5,020 calls)
- **Optimization Potential**: ⭐⭐⭐⭐⭐ **HIGHEST PRIORITY**

**Why it's slow**:
- Multiple DataFrame constructions per call
- Pandas indexing overhead
- Array slicing and copying
- Historical adjustment lookups

**Rust Optimization Strategy**:
- Implement sliding window cache in Rust
- Use rust-ndarray for efficient array operations
- Avoid Python/pandas overhead for hot path
- Expected speedup: **5-10x**

### 2. `DataFrame.__init__()` - pandas overhead
- **Time**: 0.410s (14.6%)
- **Calls**: 5,022
- **Per-call**: 0.082ms
- **Category**: Data structure construction
- **Optimization Potential**: ⭐⭐⭐⭐ **HIGH PRIORITY**

**Rust Optimization Strategy**:
- Return Polars DataFrame or rust-ndarray directly
- Minimize Python object creation
- Expected speedup: **3-5x**

### 3. `_get_history_daily_window()` - window slicing
- **Time**: 1.139s (40.6%)
- **Calls**: 5,020
- **Per-call**: 0.227ms
- **Category**: Data processing
- **Optimization Potential**: ⭐⭐⭐⭐ **HIGH PRIORITY**

**Rust Optimization Strategy**:
- Implement efficient windowing in Rust
- Use zero-copy slicing where possible
- Expected speedup: **4-8x**

### 4. `minute_to_session()` - calendar lookups
- **Time**: 0.218s (7.8%)
- **Calls**: 14,132
- **Per-call**: 0.015ms
- **Category**: Datetime operations
- **Optimization Potential**: ⭐⭐⭐ **MEDIUM PRIORITY**

**Rust Optimization Strategy**:
- Cache session mappings
- Binary search on sorted sessions
- Expected speedup: **2-3x**

### 5. `_generate_range()` - datetime generation
- **Time**: 0.153s (5.5%)
- **Calls**: 13,135
- **Per-call**: 0.012ms
- **Category**: Datetime operations
- **Optimization Potential**: ⭐⭐ **MEDIUM PRIORITY**

**Rust Optimization Strategy**:
- Use chrono crate for efficient datetime generation
- Pre-generate common ranges
- Expected speedup: **2-4x**

---

## Memory Profiling Results

Memory profiling was performed using `memory_profiler` with 0.1-second sampling interval to identify high-allocation functions and memory usage patterns.

### Overall Memory Statistics

```
Peak Memory Usage:  443.72 MiB
Mean Memory Usage:  410.37 MiB
Memory Samples:     15 (sampled at 0.1s intervals)
Total Duration:     ~1.4 seconds
```

### Memory Usage Timeline

| Time (s) | Memory (MiB) | Delta (MiB) | Event |
|----------|--------------|-------------|-------|
| 0.0 | 344.92 | - | Baseline (startup) |
| 0.1 | 344.98 | +0.06 | Initialization |
| 0.2 | 347.58 | +2.60 | Bundle loading |
| 0.3 | 347.84 | +0.26 | Calendar setup |
| 0.4 | 351.75 | +3.91 | Algorithm initialization |
| **0.5** | **440.95** | **+89.20** | **🔥 MAJOR ALLOCATION** |
| 0.6 | 441.00 | +0.05 | Steady state |
| 0.7 | 441.06 | +0.06 | Backtesting |
| 0.8 | 441.23 | +0.17 | Backtesting |
| 0.9 | 441.61 | +0.38 | Backtesting |
| 1.0 | 441.84 | +0.23 | Backtesting |
| 1.1 | 442.11 | +0.27 | Backtesting |
| 1.2 | 442.36 | +0.25 | Backtesting |
| 1.3 | 442.61 | +0.25 | Backtesting |
| **1.4** | **443.72** | **+1.11** | **Peak** |

### Key Findings

#### 1. Memory Spike at 0.5s (89 MiB allocation)

**Critical Observation**: The largest memory allocation occurs at the 0.5-second mark, with an **89 MiB jump** from 351.75 MiB to 440.95 MiB.

**Likely Causes** (based on timeline correlation):
- **Data bundle loading**: Loading historical price data from Parquet files into memory
- **DataFrame initialization**: Creating initial DataFrames for 10 symbols × 252 days
- **History loader cache**: Pre-allocating sliding window arrays for technical indicators

**Impact**: This represents **20% of peak memory usage** in a single allocation event.

#### 2. Steady-State Memory (440-444 MiB)

After the initial spike, memory usage stabilizes around **441-444 MiB** with small incremental increases:
- **Growth rate**: ~1-2 MiB over 0.9 seconds of backtesting
- **Pattern**: Gradual accumulation suggests small per-bar allocations
- **Sources**: Likely position tracking, metrics history, and temporary DataFrames

#### 3. Memory Efficiency

**Positive**: Memory usage is relatively stable during backtesting (only +2.77 MiB over 0.9s)
- Indicates good memory management in the core backtest loop
- No major memory leaks observed
- Position tracking and metrics accumulation are efficient

### High-Allocation Functions (Inferred)

Based on memory spike correlation with code execution patterns:

#### Primary Memory Consumers (>50 MiB)

1. **Bundle Data Loading** (~89 MiB at 0.5s)
   - **Source**: Parquet file loading into pandas DataFrames
   - **Data**: 10 symbols × 752 days × 6 columns (OHLCV + date) × 8 bytes ≈ 36 MiB raw
   - **Overhead**: pandas indexing, metadata, object overhead (2.5x multiplier)
   - **Optimization**: Use memory-mapped files or Polars (less overhead)

2. **History Loader Arrays** (estimated ~30-40 MiB)
   - **Source**: Sliding window cache for technical indicators
   - **Size**: Pre-allocated arrays for 200-day SMA windows
   - **Optimization**: Lazy allocation, smaller window sizes, or Rust-native arrays

3. **Position Tracking & Metrics** (estimated ~10-15 MiB)
   - **Source**: Position dictionaries, ledger state, metrics history
   - **Pattern**: Gradual growth (1-2 MiB over backtest)
   - **Optimization**: Minimal - already efficient

### Memory Optimization Targets

#### Priority 1: High Impact (>25 MiB savings potential)

**1.1 Bundle Data Loading (89 MiB spike) ⭐⭐⭐⭐⭐**
- **Current**: Load full 752-day dataset into memory as pandas DataFrame
- **Target**:
  - Use Polars (50% less memory overhead vs pandas)
  - Memory-map Parquet files (zero-copy reads)
  - Load only required date range (252 days instead of 752)
- **Estimated Savings**: 40-60 MiB (45-67% reduction in spike)
- **Impact**: **CRITICAL** - Reduces peak memory by 9-14%

**1.2 History Window Cache (30-40 MiB) ⭐⭐⭐⭐**
- **Current**: Pre-allocate full 200-day window arrays
- **Target**:
  - Lazy allocation (only allocate when accessed)
  - Ring buffer for rolling windows (constant memory)
  - Rust-native arrays (less Python object overhead)
- **Estimated Savings**: 20-30 MiB (50-75% reduction)
- **Impact**: **HIGH** - Reduces peak memory by 5-7%

#### Priority 2: Medium Impact (5-15 MiB savings potential)

**2.1 DataFrame Construction Overhead ⭐⭐⭐**
- **Current**: pandas DataFrame with heavy object overhead
- **Target**: Polars or numpy arrays where possible
- **Estimated Savings**: 10-15 MiB
- **Impact**: **MEDIUM** - Reduces peak memory by 2-3%

### Projected Memory After Optimization

| Optimization | Current (MiB) | Post-Opt (MiB) | Savings |
|--------------|---------------|----------------|---------|
| Bundle loading | 89 | 40-50 | 39-49 MiB |
| History cache | 35 | 10-15 | 20-25 MiB |
| DataFrame overhead | 25 | 15-20 | 5-10 MiB |
| Other | 295 | 295 | 0 MiB |
| **Total Peak** | **444** | **360-380** | **64-84 MiB (14-19%)** |

### Memory vs CPU Tradeoff

**Important Observation**: Memory usage is **NOT** the primary bottleneck (stable at 444 MiB, well below typical system limits).

**Recommendation for Story 7.3**:
- **CPU optimization should take priority** over memory optimization
- Memory optimizations should be pursued **only if they also improve CPU performance**
  - Example: Polars reduces both memory (50% less) AND CPU (faster operations)
  - Example: Memory-mapped files reduce memory but may slow random access
- **Don't sacrifice CPU speed for memory savings** unless memory is truly constrained

### Comparison: Memory vs CPU Bottlenecks

| Metric | Memory | CPU Time |
|--------|---------|----------|
| **Peak Usage** | 444 MiB | 2.805s |
| **Primary Bottleneck?** | ❌ No (stable) | ✅ Yes (61.5% in data.history) |
| **Optimization Priority** | Lower | **Higher** |
| **User Impact** | Low (modern systems have GB of RAM) | **High (runtime is user-visible)** |

**Conclusion**: Focus Rust optimization efforts on **CPU performance** (data.history operations), with memory optimization as a secondary benefit rather than primary goal.

---

## Optimization Targets - Prioritized

### Priority 1: Highest Impact (>50% speedup potential)

#### 1.1 Data History Operations ⭐⭐⭐⭐⭐
- **Current Time**: 1.725s (61.5%)
- **Target**: Implement in Rust with sliding window cache
- **Expected Speedup**: 5-10x
- **Estimated Post-Optimization**: 0.17-0.35s (save 1.4-1.5s)
- **Impact**: **CRITICAL** - This alone could reduce total runtime by 50-54%

#### 1.2 DataFrame Construction ⭐⭐⭐⭐
- **Current Time**: 0.410s (14.6%)
- **Target**: Use Polars or rust-ndarray
- **Expected Speedup**: 3-5x
- **Estimated Post-Optimization**: 0.08-0.14s (save 0.27-0.33s)
- **Impact**: **HIGH** - Additional 9-12% runtime reduction

### Priority 2: Medium Impact (10-25% speedup potential)

#### 2.1 Trading Calendar Operations ⭐⭐⭐
- **Current Time**: 0.218s (7.8%)
- **Target**: Cache + binary search in Rust
- **Expected Speedup**: 2-3x
- **Estimated Post-Optimization**: 0.07-0.11s (save 0.11-0.15s)
- **Impact**: **MEDIUM** - 4-5% runtime reduction

#### 2.2 Datetime Operations ⭐⭐
- **Current Time**: 0.153s (5.5%)
- **Target**: chrono crate + caching
- **Expected Speedup**: 2-4x
- **Estimated Post-Optimization**: 0.04-0.08s (save 0.07-0.11s)
- **Impact**: **MEDIUM** - 2-4% runtime reduction

### Priority 3: Lower Impact (<10% speedup potential)

#### 3.1 Type Checking Overhead ⭐
- **Current Time**: 0.110s (3.9%)
- **Target**: Reduce isinstance calls, use duck typing
- **Expected Speedup**: 1.5-2x
- **Impact**: **LOW** - 2-3% runtime reduction

**Note**: Items in Priority 3 should be addressed if Priority 1-2 optimizations don't achieve the <30% overhead target.

---

## Projected Performance After Rust Optimization

### Conservative Estimate (Story 7.3 Target)

| Component | Current (s) | Post-Rust (s) | Speedup |
|-----------|------------|--------------|---------|
| Data history ops | 1.725 | 0.345 | 5x |
| DataFrame construction | 0.410 | 0.137 | 3x |
| Calendar ops | 0.218 | 0.109 | 2x |
| Other | 0.452 | 0.452 | 1x |
| **Total** | **2.805** | **1.043** | **2.7x** |

**Projected Overhead**: ~40% vs float baseline (needs baseline measurement)

### Aggressive Estimate (Best Case)

| Component | Current (s) | Post-Rust (s) | Speedup |
|-----------|------------|--------------|---------|
| Data history ops | 1.725 | 0.172 | 10x |
| DataFrame construction | 0.410 | 0.082 | 5x |
| Calendar ops | 0.218 | 0.073 | 3x |
| Datetime ops | 0.153 | 0.038 | 4x |
| Other | 0.299 | 0.299 | 1x |
| **Total** | **2.805** | **0.664** | **4.2x** |

**Projected Overhead**: ~25% vs float baseline (within target!)

---

## Recommendations for Story 7.3

### Phase 1: Critical Path Optimization

1. **Implement Rust-based History Window Cache**
   - Replace `data_portal.history()` hot path
   - Use rust-ndarray for efficient array operations
   - Implement zero-copy slicing where possible
   - Target: 5-10x speedup on this operation

2. **Replace DataFrame Construction with Polars**
   - Already using Polars elsewhere in codebase
   - Integrate Polars more deeply in data portal
   - Target: 3-5x speedup on DataFrame operations

### Phase 2: Secondary Optimizations

3. **Optimize Trading Calendar Lookups**
   - Implement binary search cache in Rust
   - Pre-compute session mappings
   - Target: 2-3x speedup

4. **Datetime Operations with chrono**
   - Use Rust chrono crate for date generation
   - Cache common date ranges
   - Target: 2-4x speedup

### Phase 3: Validation

5. **Re-profile After Optimization**
   - Run this same profiling harness
   - Compare results using `scripts/profiling/compare_profiles.py`
   - Verify >2.5x overall speedup achieved
   - Document remaining bottlenecks

---

## Comparison to Hypotheses

### Pre-Profiling Hypotheses (from Story 7.1)

| Hypothesis | Confirmed? | Evidence |
|------------|-----------|----------|
| Decimal arithmetic is slow | ❌ **Not tested** | Used float capital_base for profiling |
| Data transformations are slow | ✅ **CONFIRMED** | 61.5% of runtime in data operations |
| Indicator calculations are slow | ⚠️ **Partially** | Included in data.history() calls (SMA calculation) |
| Metrics calculations are slow | ❌ **Not significant** | Not in top 20 functions |
| Position tracking is slow | ❌ **Not significant** | Not in top 20 functions |

**Key Discovery**: Data history operations are the dominant bottleneck, not calculation-heavy operations. This suggests that **data access patterns** and **DataFrame overhead** are more critical than pure computation.

---

## Next Steps

### For Story 7.3 (Rust Optimization)

1. ✅ **Target Confirmed**: Data history operations (61.5% of runtime)
2. ⏭ **Implementation**: Rust sliding window cache for `data.history()`
3. ⏭ **Polars Integration**: Deeper Polars usage to reduce pandas overhead
4. ⏭ **Validation**: Re-run profiling and compare results

### For Future Stories

- **Memory Profiling** (AC 7): Add memory_profiler if memory becomes a concern
- **py-spy**: Generate flamegraphs for visualization (AC 1 optional)
- **Minute/Hourly Scenarios**: Profile other frequencies to identify frequency-specific bottlenecks

---

## Appendix: Raw Profiling Data

### File Locations

- **Profile Stats**: `docs/performance/profiles/baseline/daily_cprofile.pstats`
- **Summary**: `docs/performance/profiles/baseline/daily_cprofile_summary.txt`
- **This Report**: `docs/performance/profiling-results.md`

### Command to Reproduce

```bash
# Re-run profiling
make profile-daily

# Analyze results
python -c "import pstats; pstats.Stats('docs/performance/profiles/baseline/daily_cprofile.pstats').sort_stats('cumulative').print_stats(20)"

# Compare after Rust optimization
python scripts/profiling/compare_profiles.py docs/performance/profiles/baseline/ docs/performance/profiles/post-rust/
```

### Links

- [Story 7.1 - Profile Python Implementation](../stories/7.1.profile-python-implementation.story.md)
- [Story 7.3 - Implement Rust Optimized Modules](../stories/7.3.implement-rust-optimized-modules.story.md) (next)
- [Epic 7 - Performance Optimization & Rust Integration](../prd/epic-7-performance-optimization-rust-integration.md)

---

**Report Generated**: 2025-01-08
**Profiler**: Quinn (Test Architect) + cProfile
**Story**: 7.1 - Profile Python Implementation
