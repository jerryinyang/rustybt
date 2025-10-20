# Parquet Bundle Integration Status

**Date:** 2025-10-20
**Session:** Sprint Debug - Bundle Recognition Issues
**Status:** Partial Implementation

---

## Problem Statement

Bundles created with `rustybt ingest-unified` (Parquet format) were not recognized by `run_algorithm()`, causing the following error:

```python
# This failed:
run_algorithm(
    initialize=initialize,
    handle_data=handle_data,
    bundle="mag-7",  # Bundle created with ingest-unified
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2025-09-30"),
    capital_base=10000,
)
# Error: UnknownBundle: No bundle registered with the name 'mag-7'
```

---

## Root Cause

The unified data ingestion system (`ingest-unified`) creates Parquet bundles but does not register them in the traditional bundle registry. The `bundles.load()` function only recognizes bundles that are explicitly registered via the `@register()` decorator.

**Architecture Gap:**
- **Parquet bundles**: Created by `ingest-unified`, stored in metadata database, use `PolarsParquetDailyReader`
- **Traditional bundles**: Registered via `@register()`, use Bcolz format, use `BcolzDailyBarReader`
- **No bridge**: These two systems were not connected

---

## What Was Fixed

### 1. Auto-Registration (rustybt/data/polars/parquet_writer.py)

**Change:** When a Parquet bundle is created, it is now automatically registered in the bundle registry.

```python
# New method added to ParquetWriter:
def _register_parquet_bundle(self, bundle_name: str, source_metadata: dict) -> None:
    """Register Parquet bundle in the bundle registry."""

    def parquet_bundle_ingest_placeholder(*args, **kwargs):
        raise RuntimeError(
            f"Bundle '{bundle_name}' is a Parquet bundle.\n"
            f"Use 'rustybt ingest-unified' to update it."
        )

    register_bundle(
        name=bundle_name,
        f=parquet_bundle_ingest_placeholder,
        calendar_name="NYSE",  # or "24/7" for crypto
    )
```

**Result:**
- ✅ Bundle now appears in registry
- ✅ `rustybt bundle list` shows the bundle
- ✅ Prevents accidental re-ingestion with wrong command

### 2. Parquet Bundle Detection (rustybt/data/bundles/core.py)

**Change:** `bundles.load()` now detects Parquet bundles and raises a clear error with workarounds.

```python
def load(name, environ=os.environ, timestamp=None):
    """Loads a previously ingested bundle."""

    # NEW: Check if this is a Parquet bundle
    metadata = BundleMetadata.get(name)
    if metadata is not None:
        raise NotImplementedError(
            f"Bundle '{name}' is a Parquet bundle.\n\n"
            f"Parquet bundles are not yet fully integrated with run_algorithm().\n"
            f"See workarounds below..."
        )

    # Existing Bcolz bundle loading logic...
```

**Result:**
- ✅ Clear error message instead of confusing failure
- ✅ Provides workarounds for users
- ✅ Preserves existing Bcolz bundle functionality

---

## What Still Needs Implementation

### Full Parquet Bundle Integration

To make `run_algorithm(bundle="mag-7")` work with Parquet bundles, the following components need to be implemented:

#### 1. BarReader Interface Adaptation

**File:** `rustybt/data/polars/parquet_bar_reader_adapter.py` (new file)

```python
class ParquetBarReaderAdapter(BarReader):
    """Adapter to make PolarsParquetDailyReader compatible with BarReader interface."""

    def __init__(self, parquet_reader):
        self._parquet_reader = parquet_reader
        self._calendar = ...  # From bundle metadata
        self._first_trading_day = ...  # From metadata
        self._last_available_dt = ...  # From metadata

    def load_raw_arrays(self, columns, start_date, end_date, assets):
        """Convert Polars DataFrame to numpy arrays expected by Zipline."""
        df = self._parquet_reader.load_daily_bars(
            sids=assets,
            start_date=start_date.date(),
            end_date=end_date.date(),
            fields=columns
        )
        # Convert Polars DataFrame to numpy arrays
        return [df[col].to_numpy() for col in columns]

    @property
    def first_trading_day(self):
        return self._first_trading_day

    @property
    def last_available_dt(self):
        return self._last_available_dt

    @property
    def trading_calendar(self):
        return self._calendar

    @property
    def data_frequency(self):
        return "daily"
```

#### 2. Asset Database Generation

**File:** `rustybt/data/bundles/parquet_asset_db.py` (new file)

```python
def create_asset_db_from_metadata(bundle_name: str) -> str:
    """Create asset database from bundle metadata."""

    symbols = BundleMetadata.get_symbols(bundle_name)
    metadata = BundleMetadata.get(bundle_name)

    # Create AssetDBWriter
    # Write equities/cryptocurrencies from symbols
    # Return path to asset database
```

#### 3. Modified bundles.load()

```python
def load(name, environ=os.environ, timestamp=None):
    metadata = BundleMetadata.get(name)
    if metadata is not None:
        # Load Parquet bundle
        bundle_path = pth.data_path(["bundles", name], environ=environ)

        # Create or load asset database
        asset_db = get_or_create_asset_db(name, metadata)

        # Wrap Parquet readers with BarReader adapters
        daily_reader = ParquetBarReaderAdapter(
            PolarsParquetDailyReader(bundle_path)
        )
        minute_reader = ParquetBarReaderAdapter(
            PolarsParquetMinuteReader(bundle_path)
        )

        return BundleData(
            asset_finder=AssetFinder(asset_db),
            equity_daily_bar_reader=daily_reader,
            equity_minute_bar_reader=minute_reader,
            adjustment_reader=None,  # TODO: Implement adjustment support
        )

    # Traditional Bcolz loading...
```

---

## Current Workarounds

Until full integration is complete, users have these options:

### Option 1: Use Parquet Readers Directly (Advanced)

```python
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from pathlib import Path
import os

# Load the reader
bundle_path = Path(os.path.expanduser("~/.zipline/data/bundles/mag-7"))
reader = PolarsParquetDailyReader(str(bundle_path))

# Load data
df = reader.load_daily_bars(
    sids=[1, 2, 3],  # Asset IDs
    start_date=date(2024, 1, 1),
    end_date=date(2025, 9, 30),
)

# DataFrame has Decimal precision OHLCV data
print(df.head())
```

### Option 2: Convert to Traditional Bundle Format

For users who need `run_algorithm()` support immediately, convert the Parquet bundle to traditional Bcolz format:

```bash
# This feature doesn't exist yet but could be added:
rustybt bundle convert mag-7 --format bcolz

# Or re-ingest using a traditional bundle adapter
# (requires creating a custom bundle registration)
```

### Option 3: Use Legacy yfinance-reloaded Adapter

The old system still works for backward compatibility:

```python
# Install adapter
pip install yfinance-reloaded

# Use traditional ingestion
rustybt ingest -b quandl  # or other registered bundle
```

---

## Estimated Implementation Effort

| Component | Complexity | Estimated Time |
|-----------|------------|----------------|
| BarReader adapters | Medium | 4-6 hours |
| Asset DB generation | Medium | 3-4 hours |
| Testing & validation | High | 6-8 hours |
| Documentation | Low | 2-3 hours |
| **Total** | **Medium-High** | **15-21 hours** |

---

## Recommendations

### For Users (Short Term)

1. **Use Parquet bundles for data exploration** (direct reader access)
2. **Use traditional bundles for backtesting** (`run_algorithm()`)
3. **Watch for updates** - full integration is planned for next release

### For Developers (Implementation Priority)

1. **Create GitHub issue** tracking full Parquet bundle integration
2. **Implement BarReader adapters** as the highest priority component
3. **Add asset DB generation** from bundle metadata
4. **Write comprehensive tests** for both Parquet and Bcolz paths
5. **Document migration guide** for users

---

## Files Modified

1. `rustybt/data/polars/parquet_writer.py`
   - Added `_register_parquet_bundle()` method
   - Auto-registration on bundle creation

2. `rustybt/data/bundles/core.py`
   - Modified `load()` to detect Parquet bundles
   - Clear error message with workarounds

3. `docs/internal/sprint-debug/fixes/active-session.md`
   - Documented investigation and implementation

---

## Related Issues

- GitHub Issue #XXX - Full Parquet Bundle Integration (to be created)
- Epic X1 - Unified Data Architecture
- Story X1.4 - Unified Metadata Management

---

**Status:** Ready for Review
**Next Action:** Create GitHub issue and plan full implementation
