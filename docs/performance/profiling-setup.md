# Profiling Infrastructure Setup

**Status**: Infrastructure Complete, Awaiting Data Bundle Setup for Full Profiling

## Overview

The profiling infrastructure for Story 7.1 has been successfully set up and tested. This document describes what has been implemented and what's required to complete the full profiling workflow.

## Completed Infrastructure

### 1. Profiling Harness Script

**Location**: `scripts/profiling/run_profiler.py`

**Features**:
- Command-line interface for running profiling scenarios
- Support for cProfile (deterministic profiling)
- Support for memory_profiler (memory usage tracking)
- Three predefined scenarios: daily, hourly, minute
- Structured logging with structlog
- Automatic output file generation

**Usage**:
```bash
# List available scenarios
python scripts/profiling/run_profiler.py --list-scenarios

# Run daily scenario with cProfile
python scripts/profiling/run_profiler.py --scenario daily --profiler cprofile

# Run all scenarios with all profilers
python scripts/profiling/run_profiler.py --scenario all --profiler all

# Custom output directory
python scripts/profiling/run_profiler.py --scenario daily --output-dir /path/to/output
```

**Output Files**:
- `<scenario>_cprofile.pstats`: Binary cProfile stats file
- `<scenario>_cprofile_summary.txt`: Human-readable top 20 functions by cumulative time
- `<scenario>_memory.txt`: Memory profiling results (if memory_profiler installed)

### 2. Profile Comparison Script

**Location**: `scripts/profiling/compare_profiles.py`

**Features**:
- Compares before/after profiling results
- Identifies optimizations (functions with reduced time)
- Identifies regressions (functions with increased time)
- Calculates overall runtime delta
- Generates markdown reports

**Usage**:
```bash
# Compare baseline vs post-rust profiles
python scripts/profiling/compare_profiles.py \
    docs/performance/profiles/baseline/ \
    docs/performance/profiles/post-rust/

# Compare specific scenario
python scripts/profiling/compare_profiles.py \
    docs/performance/profiles/baseline/ \
    docs/performance/profiles/post-rust/ \
    --scenario daily \
    --output comparison_report.md
```

**Output**:
- Markdown report with:
  - Overall runtime change (seconds and percentage)
  - Top improvements (functions with reduced time)
  - Top regressions (functions with increased time)

### 3. Makefile Targets

**Location**: `Makefile`

**Targets**:
```bash
make profile          # Run all profiling scenarios (daily, hourly, minute)
make profile-daily    # Run daily data profiling scenario
make profile-hourly   # Run hourly data profiling scenario
make profile-minute   # Run minute data profiling scenario
make profile-all      # Run all profiling with all profilers
make profile-compare  # Compare baseline vs post-rust results
```

### 4. Directory Structure

```
docs/performance/profiles/
├── baseline/         # Baseline profiling results (before Rust optimization)
│   ├── daily_cprofile.pstats
│   ├── daily_cprofile_summary.txt
│   └── ...
└── post-rust/        # Post-optimization profiling results
    ├── daily_cprofile.pstats
    ├── daily_cprofile_summary.txt
    └── ...
```

## Current Limitations

### Placeholder Backtest Scenarios

The profiling harness currently contains **placeholder** backtest scenarios that simulate work but don't run actual backtests. The placeholders are defined in:

```python
def run_daily_scenario() -> None:
    """Run daily data backtest scenario (2 years, 50 assets, SMA strategy)."""
    logger.info("running_daily_scenario")
    # Placeholder: just sleeps to simulate work
    import time
    time.sleep(0.1)
    logger.warning("daily_scenario_placeholder", message="Full backtest requires data bundle setup.")
```

### What's Required for Full Profiling

To complete the profiling workflow, the following backtest scenarios need to be implemented:

#### Scenario 1: Daily Data Backtest
- **Duration**: 2 years
- **Assets**: 50 equities
- **Strategy**: Simple SMA crossover (50/200 period)
- **Data Frequency**: Daily
- **Requirements**:
  - Data bundle with daily OHLCV data for 50 assets
  - 2+ years of historical data
  - Asset metadata and calendar

#### Scenario 2: Hourly Data Backtest
- **Duration**: 6 months
- **Assets**: 20 equities/crypto
- **Strategy**: Momentum (20-period lookback)
- **Data Frequency**: Hourly
- **Requirements**:
  - Data bundle with hourly OHLCV data for 20 assets
  - 6+ months of historical data
  - Intraday trading calendar

#### Scenario 3: Minute Data Backtest
- **Duration**: 1 month
- **Assets**: 10 equities/crypto
- **Strategy**: Mean reversion (20-period window, 2-sigma threshold)
- **Data Frequency**: Minute
- **Requirements**:
  - Data bundle with minute OHLCV data for 10 assets
  - 1+ month of historical data
  - Minute-level trading calendar

### Data Bundle Options

**Option 1: Use Existing Zipline Bundles**
- `quantopian-quandl`: Historical daily equity data (free, but data may be stale)
- Custom CSV bundle: Requires CSV data preparation

**Option 2: Create Synthetic Data**
- Generate synthetic OHLCV data for profiling purposes
- Pros: Quick setup, deterministic
- Cons: May not reflect real-world performance characteristics

**Option 3: Use YFinance/CCXT Adapters**
- Download recent data dynamically
- Pros: Real data, no manual setup
- Cons: Slower, requires network access

## Next Steps to Complete Profiling

### Step 1: Choose Data Source

Decide which data bundle approach to use based on project priorities.

### Step 2: Implement Backtest Scenarios

Replace placeholder functions in `scripts/profiling/run_profiler.py` with actual backtest execution:

```python
def run_daily_scenario() -> None:
    """Run daily data backtest scenario."""
    from rustybt.utils.run_algo import run_algorithm
    import pandas as pd
    from decimal import Decimal

    # Define strategy functions (initialize, handle_data)
    def initialize(context):
        context.sym = symbol("AAPL")
        # ... strategy initialization

    def handle_data(context, data):
        # ... strategy logic

    # Run backtest
    results = run_algorithm(
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2024-12-31"),
        initialize=initialize,
        handle_data=handle_data,
        capital_base=Decimal("100000"),
        data_frequency="daily",
        bundle="quantopian-quandl",  # or custom bundle
    )

    return results
```

### Step 3: Run Full Profiling

Once backtest scenarios are implemented:

```bash
# Run baseline profiling
make profile-all

# Results will be in docs/performance/profiles/baseline/
```

### Step 4: Analyze Results

Use the generated profiling data to:
1. Identify bottlenecks (functions >5% of total time)
2. Categorize by type (Decimal arithmetic, data processing, loops, etc.)
3. Prioritize optimization targets
4. Generate profiling report (docs/performance/profiling-results.md)

### Step 5: (Future) Re-profile After Rust Optimization

After implementing Rust optimizations in Story 7.3:

```bash
# Run post-optimization profiling
python scripts/profiling/run_profiler.py --scenario all --profiler all \
    --output-dir docs/performance/profiles/post-rust/

# Compare results
make profile-compare

# Results in profile_comparison_*.md files
```

## Dependencies

### Currently Installed
- `structlog`: Structured logging
- `memory_profiler`: Memory usage tracking (in benchmarks extras)

### Not Yet Installed (Optional)
- `py-spy`: Sampling profiler with flamegraph generation
  - Install: `pip install py-spy` or `cargo install py-spy`
  - Usage: Requires separate script or manual invocation

### Data Bundle Dependencies
- Depends on chosen data source:
  - Zipline bundles: Requires bundle ingestion
  - YFinance: Already installed
  - CCXT: Already installed
  - Synthetic: No external dependencies

## Testing

Unit tests for profiling infrastructure are pending (AC in Story 7.1).

Expected test coverage:
- Profiling harness runs without errors
- Output files generated in correct locations
- Output file format validation (pstats, memory profiles)
- Comparison script produces valid reports
- Makefile targets execute successfully

## References

- Story 7.1: [docs/stories/7.1.profile-python-implementation.story.md](../stories/7.1.profile-python-implementation.story.md)
- Tech Stack: [docs/architecture/tech-stack.md](../architecture/tech-stack.md)
- Source Tree: [docs/architecture/source-tree.md](../architecture/source-tree.md)
