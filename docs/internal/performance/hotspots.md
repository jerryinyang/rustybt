# Decimal Implementation Hotspots

**Generated:** Profiling run of 252-day backtest with 10 assets

## Purpose

Identify top time-consuming functions for Rust optimization in Epic 7.

## Top 20 Functions (by cumulative time)

| Rank | Function | Cumulative Time (s) | Calls | Time/Call (ms) |
|------|----------|--------------------:|------:|---------------:|
| 1 | `r:u:n` | 0.032 | 1 | 32.000 |
| 2 | `s:e:q` | 0.009 | 1 | 9.000 |
| 3 | `g:e:t` | 0.007 | 22 | 0.318 |
| 4 | `l:o:a` | 0.006 | 1 | 6.000 |
| 5 | `s:a:f` | 0.006 | 1 | 6.000 |
| 6 | `l:o:a` | 0.006 | 1 | 6.000 |
| 7 | `g:e:t` | 0.006 | 1 | 6.000 |
| 8 | `g:e:t` | 0.005 | 1 | 5.000 |
| 9 | `c:o:m` | 0.005 | 1 | 5.000 |
| 10 | `c:o:m` | 0.005 | 61/1 | 0.082 |
| 11 | `s:h:a` | 0.005 | 1 | 5.000 |
| 12 | `c:o:m` | 0.005 | 8/1 | 0.625 |
| 13 | `c:h:e` | 0.005 | 178 | 0.028 |
| 14 | `m:a:p` | 0.004 | 1 | 4.000 |
| 15 | `c:h:e` | 0.004 | 476 | 0.008 |
| 16 | `<:m:e` | 0.004 | 1 | 4.000 |
| 17 | `f:e:t` | 0.003 | 84 | 0.036 |
| 18 | `_:c:o` | 0.003 | 1 | 3.000 |
| 19 | `<:b:u` | 0.003 | 1 | 3.000 |
| 20 | `p:a:r` | 0.003 | 38 | 0.079 |

## Optimization Priorities for Epic 7

Based on profiling results, prioritize:

1. **Decimal arithmetic operations** (if in top 10) - Implement in Rust with rust-decimal
2. **Metrics calculations** (Sharpe, drawdown) - Vectorize with SIMD in Rust
3. **Data aggregation** (Polars operations on Decimal) - Optimize type conversions
4. **Commission calculations** - Batch processing in Rust if hot path

---

*Profile data: benchmarks/results/decimal_backtest.prof*
