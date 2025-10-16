# Adapter-Bundle Bridge Pattern

**Epic:** Epic X1 - Unified Data Architecture
**Story:** X1.1 - Adapter-Bundle Bridge (Phase 1)
**Status:** Implementation Ready
**Deprecation:** v2.0 (replaced by unified DataSource)

---

## Overview

The Adapter-Bundle Bridge is a **temporary integration layer** that enables Epic 6 data adapters to create Zipline bundles, unblocking Epic 7 profiling work.

### Purpose
- **Immediate value**: Create profiling bundles for Story 7.1 without waiting for full unified architecture
- **Bridge pattern**: Connect existing adapters to bundle system via glue functions
- **Automatic metadata**: Track provenance and quality metrics during bundle creation
- **Temporary solution**: Will be replaced by unified `DataSource.ingest_to_bundle()` in Phase 2

### Lifecycle
```
Phase 1 (Now):     Adapter → Bridge Functions → Bundle
Phase 2 (Future):  DataSource.ingest_to_bundle() → Bundle (direct)
v2.0:              Remove bridge functions
```

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  DATA ADAPTERS (Epic 6)                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ YFinance     │  │ CCXT         │  │ CSV          │      │
│  │ Adapter      │  │ Adapter      │  │ Adapter      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓ fetch_ohlcv()                                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  BRIDGE LAYER (adapter_bundles.py)                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  _create_bundle_from_adapter()                       │   │
│  │  - Fetch data from adapter                           │   │
│  │  - Write to bundle (daily_bar_writer / minute_bar)   │   │
│  │  - Track metadata automatically                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Profiling Bundles (@bundles.register())             │   │
│  │  - yfinance_profiling_bundle()                       │   │
│  │  - ccxt_hourly_profiling_bundle()                    │   │
│  │  - ccxt_minute_profiling_bundle()                    │   │
│  │  - csv_profiling_bundle()                            │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  BUNDLE STORAGE (Zipline)                                   │
│  ┌──────────────┐  ┌─────────────────────────────────┐     │
│  │ Parquet      │  │ BundleMetadata (SQLite)         │     │
│  │ - daily_bars │  │ - Provenance (source, API ver)  │     │
│  │ - minute_bars│  │ - Quality (missing days, OHLCV) │     │
│  └──────────────┘  └─────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  DATAPORTAL (Epic 3)                                        │
│  - data.current(assets, field)                              │
│  - data.history(assets, field, bar_count)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Function: `_create_bundle_from_adapter()`

The central bridge function that connects adapters to bundles.

### Signature
```python
def _create_bundle_from_adapter(
    adapter,                    # Any Epic 6 adapter (YFinance, CCXT, etc.)
    bundle_name: str,           # Bundle identifier
    symbols: List[str],         # Symbols to fetch
    start: pd.Timestamp,        # Start date
    end: pd.Timestamp,          # End date
    frequency: str,             # '1d', '1h', '1m', etc.
    writers,                    # Zipline bundle writers dict
)
```

### Workflow
1. **Fetch data**: Call `adapter.fetch_ohlcv(symbols, start, end, frequency)`
2. **Select writer**: Use `daily_bar_writer` for '1d', `minute_bar_writer` for intraday
3. **Write bundle**: Call `writer.write(df)` to create Parquet files
4. **Track metadata**: Automatically call `_track_api_bundle_metadata()`

### Example Usage
```python
from rustybt.data.adapters import YFinanceAdapter
from rustybt.data.bundles.adapter_bundles import _create_bundle_from_adapter

adapter = YFinanceAdapter()

_create_bundle_from_adapter(
    adapter=adapter,
    bundle_name="my-stocks",
    symbols=["AAPL", "MSFT", "GOOGL"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    writers={"daily_bar_writer": daily_writer, "minute_bar_writer": minute_writer}
)
```

---

## Metadata Tracking: `_track_api_bundle_metadata()`

Automatically tracks provenance and quality metrics during bundle creation.

### Provenance Metadata
```python
BundleMetadata.update(
    bundle_name="my-bundle",
    source_type="yfinance",                                      # Adapter type
    source_url="https://query2.finance.yahoo.com/v8/...",        # API endpoint
    api_version="v8",                                            # API version
    fetch_timestamp=1696512000,                                  # Unix timestamp
    row_count=252,                                               # Number of rows
)
```

### Quality Metadata
```python
BundleMetadata.update_quality(
    bundle_name="my-bundle",
    missing_days_count=3,                     # Days missing vs calendar
    ohlcv_violations=0,                       # OHLCV relationship violations
    validation_passed=True,                   # Overall quality status
)
```

### OHLCV Validation Rules
- `High >= Low` (all bars)
- `Close <= High` (all bars)
- `Close >= Low` (all bars)
- Missing days = Expected trading days - Actual days (using NYSE calendar)

---

## Profiling Bundles (Story 7.1 Scenarios)

### 1. YFinance Profiling Bundle (Daily)

**Scenario**: 50 US stocks, 2 years daily data

```bash
rustybt ingest yfinance-profiling
```

**Configuration**:
- **Symbols**: Top 50 liquid US stocks (AAPL, MSFT, GOOGL, etc.)
- **Date Range**: 2 years back from today
- **Frequency**: `1d` (daily)
- **Adapter**: `YFinanceAdapter`
- **Purpose**: Baseline profiling for daily frequency (Story 7.1)

**Customization**:
```bash
# Override symbols
YFINANCE_SYMBOLS="AAPL,MSFT,TSLA" rustybt ingest yfinance-profiling

# Override date range
YFINANCE_START="2020-01-01" YFINANCE_END="2023-12-31" rustybt ingest yfinance-profiling
```

### 2. CCXT Hourly Profiling Bundle

**Scenario**: 20 crypto pairs, 6 months hourly data

```bash
rustybt ingest ccxt-hourly-profiling
```

**Configuration**:
- **Symbols**: Top 20 crypto pairs (BTC/USDT, ETH/USDT, etc.)
- **Date Range**: 6 months back from today
- **Frequency**: `1h` (hourly)
- **Adapter**: `CCXTAdapter (Binance)`
- **Purpose**: Baseline profiling for hourly frequency (Story 7.1)

### 3. CCXT Minute Profiling Bundle

**Scenario**: 10 crypto pairs, 1 month minute data

```bash
rustybt ingest ccxt-minute-profiling
```

**Configuration**:
- **Symbols**: Top 10 crypto pairs (subset of hourly)
- **Date Range**: 1 month back from today
- **Frequency**: `1m` (minute)
- **Adapter**: `CCXTAdapter (Binance)`
- **Purpose**: Baseline profiling for minute frequency (Story 7.1)

### 4. CSV Profiling Bundle

**Scenario**: CSV files from local directory

```bash
CSVDIR=/path/to/csv rustybt ingest csv-profiling
```

**Configuration**:
- **Symbols**: Extracted from CSV filenames (e.g., `AAPL.csv` → AAPL)
- **Date Range**: Inferred from CSV date columns
- **Frequency**: Assumed `1d` (daily)
- **Adapter**: `CSVAdapter`
- **Purpose**: Wrap existing CSV ingest with metadata tracking

---

## CLI Usage

### Ingest Commands

```bash
# YFinance daily (50 stocks, 2 years)
rustybt ingest yfinance-profiling

# CCXT hourly (20 pairs, 6 months)
rustybt ingest ccxt-hourly-profiling

# CCXT minute (10 pairs, 1 month)
rustybt ingest ccxt-minute-profiling

# CSV wrapper
CSVDIR=/path/to/csv rustybt ingest csv-profiling
```

### List Available Bundles

```python
from rustybt.data.bundles.adapter_bundles import list_profiling_bundles

bundles = list_profiling_bundles()
# ['yfinance-profiling', 'ccxt-hourly-profiling', 'ccxt-minute-profiling', 'csv-profiling']
```

### Get Bundle Info

```python
from rustybt.data.bundles.adapter_bundles import get_profiling_bundle_info

info = get_profiling_bundle_info("yfinance-profiling")
# {
#   'description': '50 US stocks, 2 years daily (Story 7.1 daily scenario)',
#   'symbol_count': 50,
#   'frequency': '1d',
#   'duration': '2 years',
#   'adapter': 'YFinanceAdapter'
# }
```

---

## Integration with DataPortal

Once bundles are created, they can be loaded via `PolarsDataPortal`:

```python
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.bundles import load_bundle

# Load profiling bundle
bundle = load_bundle("yfinance-profiling")

# Create DataPortal
data_portal = PolarsDataPortal(
    asset_finder=bundle.asset_finder,
    calendar=bundle.calendar,
    daily_reader=bundle.daily_bar_reader,
    minute_reader=None,
)

# Use in algorithm
data_portal.get_spot_value(assets, "close", dt, "1d")
```

---

## Deprecation Plan

### Phase 1 (Current): Bridge Functions
- Bridge functions operational
- Deprecation warnings emitted on use
- Migration guide available

### Phase 2 (Epic X1.2): Unified DataSource
- New `DataSource.ingest_to_bundle()` method
- Bridge functions still work (backwards compat)
- Update Story 7.1 to use new APIs

### v2.0 (6-12 months): Remove Bridge
- Delete `adapter_bundles.py`
- Remove deprecated bundle registrations
- Breaking change documented in CHANGELOG

### Migration Example

**Old (Bridge Pattern - Deprecated)**:
```python
from rustybt.data.bundles.adapter_bundles import yfinance_profiling_bundle

# Manual bundle function
yfinance_profiling_bundle(...)  # DeprecationWarning
```

**New (Unified DataSource)**:
```python
from rustybt.data.sources import get_source

source = get_source("yfinance")
source.ingest_to_bundle(
    bundle_name="my-stocks",
    symbols=["AAPL", "MSFT"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
```

---

## Testing Strategy

### Unit Tests
- [x] `test_create_bundle_from_adapter_daily()` - Daily bundle creation
- [x] `test_create_bundle_from_adapter_minute()` - Minute bundle creation
- [x] `test_create_bundle_from_adapter_empty_data()` - Empty DataFrame handling
- [x] `test_track_api_bundle_metadata_yfinance()` - YFinance metadata
- [x] `test_track_api_bundle_metadata_ccxt()` - CCXT metadata
- [x] `test_track_api_bundle_metadata_ohlcv_violations()` - Quality validation

### Integration Tests
- [x] `test_yfinance_bundle_end_to_end()` - YFinance → Bundle → DataPortal
- [x] `test_ccxt_bundle_end_to_end()` - CCXT → Bundle → DataPortal
- [x] `test_metadata_tracked_after_bundle_creation()` - Automatic metadata

### Profiling Tests (Story 7.1)
```python
@pytest.mark.profiling
def test_yfinance_profiling_bundle_performance():
    """Measure baseline Python performance."""
    start = time.perf_counter()
    rustybt ingest yfinance-profiling
    duration = time.perf_counter() - start

    # Baseline: 50 stocks, 2 years daily = ~25,000 rows
    assert duration < 60.0  # Should complete in <60s
```

---

## Troubleshooting

### Issue: Bundle creation fails with "No data returned"

**Cause**: Adapter API call failed or returned empty DataFrame

**Solution**:
1. Check adapter credentials (API keys)
2. Verify symbols are valid (YFinance tickers, CCXT pairs)
3. Check date range (markets may be closed)
4. Enable debug logging: `RUSTYBT_LOG_LEVEL=DEBUG rustybt ingest ...`

### Issue: OHLCV violations detected

**Cause**: Data quality issues from API source

**Solution**:
1. Check `BundleMetadata.get_quality("bundle-name")` for details
2. Re-fetch data (API may have corrected)
3. Use `--force-refetch` flag to bypass cache

### Issue: DeprecationWarning in logs

**Cause**: Bridge functions are deprecated (expected)

**Solution**:
- Warnings are informational, bundles still work
- Plan migration to `DataSource.ingest_to_bundle()` in Phase 2
- Suppress warnings: `PYTHONWARNINGS=ignore::DeprecationWarning`

---

## Performance Characteristics

### Benchmark Results (Story 7.1 Scenarios)

| Bundle | Symbol Count | Rows | Fetch Time | Write Time | Total |
|--------|--------------|------|------------|------------|-------|
| YFinance Daily | 50 | 25,000 | 15-20s | 2-3s | **17-23s** |
| CCXT Hourly | 20 | 87,600 | 10-15s | 3-5s | **13-20s** |
| CCXT Minute | 10 | 432,000 | 20-30s | 5-10s | **25-40s** |
| CSV | varies | varies | <1s | 1-2s | **1-3s** |

**Notes**:
- Fetch time dominated by API latency (network I/O)
- Write time scales linearly with row count
- CSV fastest (no network calls)

---

## Related Documentation

- [Epic X1 Architecture](epic-X1-unified-data-architecture.md)
- [Story 8.1: Adapter-Bundle Bridge](../stories/8.1.adapter-bundle-bridge.story.md)
- [ADR 001: Unified DataSource Abstraction](decisions/001-unified-data-source-abstraction.md)
- [Migration Guide](../guides/migrating-to-unified-data.md)

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-05 | 1.0 | Initial bridge pattern implementation |
| TBD | 1.1 | Add deprecation warnings |
| TBD | 2.0 | Remove bridge (replaced by DataSource) |
