# rustybt Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-20

## Active Technologies
- Python 3.12+ (required by project constitution) (001-storage-install-improvements)
- Python 3.12+ (required by constitution) + Polars (data processing), NumPy (numerical operations), Decimal (financial precision), pytest (testing), cProfile/line_profiler/memory_profiler (profiling) (002-performance-benchmarking-optimization)
- Parquet (OHLCV data), standard file system for benchmarks/reports (002-performance-benchmarking-optimization)
- Python 3.12+ (required by constitution) + Polars (data processing), NumPy (numerical operations, array returns), Pandas (backward compatibility), functools.lru_cache (multi-tier caching), Hypothesis (property-based testing) (003-profiling-optimization-targets)
- Parquet (OHLCV bundle data), Pickle (cache serialization for bundle version tracking) (003-profiling-optimization-targets)

## Project Structure
```
src/
tests/
```

## Commands
cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style
Python 3.12+ (required by project constitution): Follow standard conventions

## Recent Changes
- 003-profiling-optimization-targets: Added Python 3.12+ (required by constitution) + Polars (data processing), NumPy (numerical operations, array returns), Pandas (backward compatibility), functools.lru_cache (multi-tier caching), Hypothesis (property-based testing)
- 002-performance-benchmarking-optimization: Added Python 3.12+ (required by constitution) + Polars (data processing), NumPy (numerical operations), Decimal (financial precision), pytest (testing), cProfile/line_profiler/memory_profiler (profiling)
- 001-storage-install-improvements: Added Python 3.12+ (required by project constitution)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
