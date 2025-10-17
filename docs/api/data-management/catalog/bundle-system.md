# Bundle System

Comprehensive guide to RustyBT's data bundle system for creating, managing, and using data bundles.

## Overview

The bundle system provides a complete lifecycle for managing financial data:
1. **Registration** - Define how data should be fetched and stored
2. **Ingestion** - Download and store data
3. **Loading** - Access ingested data for backtesting
4. **Maintenance** - Clean up old data
5. **Migration** - Convert between storage formats

## Core Concepts

### What is a Bundle?

A **bundle** is a named collection of financial data that has been:
- Fetched from a data source (API, CSV, etc.)
- Validated and processed
- Stored in an optimized format (Bcolz/Parquet)
- Indexed for fast lookups

### Bundle Components

Each bundle contains:
- **OHLCV data**: Daily or minute bar data
- **Asset metadata**: Symbol information, exchanges
- **Adjustments**: Splits, dividends, corporate actions
- **Calendar**: Trading calendar for the data

### Bundle Storage

Bundles are stored in versioned directories:
```
~/.rustybt/data/
  └── my-bundle/
      ├── 2024-01-01T00;00;00.000000/  # Ingestion timestamp
      │   ├── daily_equities.bcolz/
      │   ├── minute_equities.bcolz/
      │   ├── assets-9.sqlite
      │   └── adjustments.sqlite
      ├── 2024-01-15T00;00;00.000000/  # Later ingestion
      │   └── ...
      └── .cache/  # Temporary ingestion cache
```

## Quick Start

### 1. Register a Bundle

```python
from rustybt.data.bundles import register

@register('my-stocks')
def my_stocks_ingest(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir
):
    """Custom bundle ingestion function."""
    # Fetch and write data
    # (See detailed examples below)
    pass
```

### 2. Ingest Data

```python
from rustybt.data.bundles import ingest

# Ingest the bundle
ingest('my-stocks', show_progress=True)
```

### 3. Load and Use

```python
from rustybt.data.bundles import load

# Load bundle data
bundle_data = load('my-stocks')

# Access data readers
asset_finder = bundle_data.asset_finder
daily_reader = bundle_data.equity_daily_bar_reader
minute_reader = bundle_data.equity_minute_bar_reader
adjustments = bundle_data.adjustment_reader

# Use in backtests
from rustybt.utils.run_algo import run_algorithm

result = run_algorithm(
    start='2023-01-01',
    end='2023-12-31',
    bundle='my-stocks',
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000
)
```

### 4. Maintain Bundles

```python
from rustybt.data.bundles import clean

# Keep only last 5 ingestions
clean('my-stocks', keep_last=5)

# Remove old ingestions
import pandas as pd
clean('my-stocks', before=pd.Timestamp('2023-01-01'))
```

## Bundle Registration

### register()

Register a bundle with an ingestion function.

**Signature**:
```python
def register(
    name: str,
    f: callable,
    calendar_name: str = "NYSE",
    start_session: pd.Timestamp | None = None,
    end_session: pd.Timestamp | None = None,
    minutes_per_day: int = 390,
    create_writers: bool = True
) -> callable
```

**Parameters**:
- `name` (str): Bundle name
- `f` (callable): Ingestion function (see below for signature)
- `calendar_name` (str, optional): Trading calendar name (default: "NYSE")
- `start_session` (pd.Timestamp, optional): First session of data
- `end_session` (pd.Timestamp, optional): Last session of data
- `minutes_per_day` (int, optional): Minutes per trading day (default: 390)
- `create_writers` (bool, optional): Create data writers (default: True)

**Returns**: The ingestion function (allows decorator usage)

**Ingestion Function Signature**:
```python
def ingest_function(
    environ: dict,
    asset_db_writer: AssetDBWriter,
    minute_bar_writer: BcolzMinuteBarWriter,
    daily_bar_writer: BcolzDailyBarWriter,
    adjustment_writer: SQLiteAdjustmentWriter,
    calendar: TradingCalendar,
    start_session: pd.Timestamp,
    end_session: pd.Timestamp,
    cache: DataFrameCache,
    show_progress: bool,
    output_dir: str
) -> None
```

**Example - Simple CSV Bundle**:
```python
import pandas as pd
from rustybt.data.bundles import register

@register('csv-stocks')
def csv_stocks_ingest(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir
):
    """Ingest CSV stock data."""
    # Load CSV data
    df = pd.read_csv('stocks.csv', parse_dates=['date'])
    df = df.set_index('date')

    # Write asset metadata
    symbols = df['symbol'].unique()
    asset_db_writer.write(
        equities=pd.DataFrame({
            'symbol': symbols,
            'exchange': 'NYSE',
            'asset_name': symbols,
        })
    )

    # Write daily bars
    daily_bar_writer.write(
        data=[(
            sid,
            df[df['symbol'] == symbol][['open', 'high', 'low', 'close', 'volume']]
        ) for sid, symbol in enumerate(symbols)],
        show_progress=show_progress
    )
```

**Example - API-based Bundle**:
```python
from rustybt.data.bundles import register
from rustybt.data.adapters import YFinanceAdapter

@register('yfinance-sp500', calendar_name='NYSE')
def yfinance_sp500_ingest(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir
):
    """Ingest S&P 500 stocks from YFinance."""
    import polars as pl

    # Define symbols
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    # Fetch data using adapter
    adapter = YFinanceAdapter()
    data = adapter.fetch_ohlcv(
        symbols=symbols,
        start=str(start_session),
        end=str(end_session),
        resolution='1d'
    )

    # Write assets
    asset_db_writer.write(
        equities=pl.DataFrame({
            'symbol': symbols,
            'exchange': 'NASDAQ',
            'asset_name': symbols,
        }).to_pandas()
    )

    # Convert to pandas format expected by writer
    for sid, symbol in enumerate(symbols):
        symbol_data = data.filter(pl.col('symbol') == symbol).to_pandas()
        symbol_data = symbol_data.set_index('date')

        daily_bar_writer.write_sid(
            sid=sid,
            df=symbol_data[['open', 'high', 'low', 'close', 'volume']]
        )
```

---

### unregister()

Remove a bundle from the registry.

**Signature**:
```python
def unregister(name: str) -> None
```

**Parameters**:
- `name` (str): Name of bundle to unregister

**Raises**:
- `UnknownBundle`: If bundle not registered

**Example**:
```python
from rustybt.data.bundles import unregister

# Unregister a bundle
unregister('old-bundle')
```

**Notes**:
- Does NOT delete ingested data (use `clean()` for that)
- Only removes from in-memory registry
- Useful for testing or dynamic bundle management

---

## Bundle Ingestion

### ingest()

Download and store data for a bundle.

**Signature**:
```python
def ingest(
    name: str,
    environ: dict = os.environ,
    timestamp: datetime | None = None,
    assets_versions: tuple[int, ...] = (),
    show_progress: bool = False
) -> None
```

**Parameters**:
- `name` (str): Bundle name
- `environ` (dict, optional): Environment variables (default: os.environ)
- `timestamp` (datetime, optional): Ingestion timestamp (default: now)
- `assets_versions` (tuple, optional): Asset DB versions to create
- `show_progress` (bool, optional): Display progress (default: False)

**Raises**:
- `UnknownBundle`: If bundle not registered

**Example - Basic Ingestion**:
```python
from rustybt.data.bundles import ingest

# Ingest with default settings
ingest('my-bundle')

# Ingest with progress bar
ingest('my-bundle', show_progress=True)
```

**Example - Custom Timestamp**:
```python
import pandas as pd
from rustybt.data.bundles import ingest

# Ingest with specific timestamp (for testing/replay)
timestamp = pd.Timestamp('2024-01-01', tz='UTC')
ingest('my-bundle', timestamp=timestamp)
```

**Example - Asset DB Downgrade**:
```python
from rustybt.data.bundles import ingest

# Create bundle with multiple asset DB versions
ingest(
    'my-bundle',
    assets_versions=(7, 8, 9),  # Create v7, v8, v9 databases
    show_progress=True
)
```

**Notes**:
- Creates new ingestion directory with timestamp
- Old ingestions are preserved (use `clean()` to remove)
- Safe to re-run (creates new version)
- Can take significant time for large datasets

---

## Bundle Loading

### load()

Load a previously ingested bundle for use.

**Signature**:
```python
def load(
    name: str,
    environ: dict = os.environ,
    timestamp: datetime | None = None
) -> BundleData
```

**Parameters**:
- `name` (str): Bundle name
- `environ` (dict, optional): Environment variables (default: os.environ)
- `timestamp` (datetime, optional): Load data as of this time (default: latest)

**Returns**:
- `BundleData`: Named tuple with data readers

**Raises**:
- `UnknownBundle`: If bundle not registered
- `ValueError`: If no data found for bundle

**Example - Basic Loading**:
```python
from rustybt.data.bundles import load

# Load most recent ingestion
bundle_data = load('my-bundle')

# Access readers
asset_finder = bundle_data.asset_finder
daily_reader = bundle_data.equity_daily_bar_reader
minute_reader = bundle_data.equity_minute_bar_reader
adjustment_reader = bundle_data.adjustment_reader

# Look up an asset
asset = asset_finder.lookup_symbol('AAPL', as_of_date=None)
print(f"Asset: {asset.symbol} (SID: {asset.sid})")

# Read daily data
import pandas as pd
data = daily_reader.load_raw_arrays(
    columns=['close'],
    start_date=pd.Timestamp('2023-01-01'),
    end_date=pd.Timestamp('2023-12-31'),
    assets=[asset]
)
print(f"Loaded {len(data[0])} days of data")
```

**Example - Load Specific Ingestion**:
```python
import pandas as pd
from rustybt.data.bundles import load

# Load bundle as of specific date
timestamp = pd.Timestamp('2024-01-01', tz='UTC')
bundle_data = load('my-bundle', timestamp=timestamp)
```

**Example - Context Manager (Resource Cleanup)**:
```python
from rustybt.data.bundles import load

# Use context manager for automatic cleanup
with load('my-bundle') as bundle_data:
    asset_finder = bundle_data.asset_finder
    # Use bundle data...
    # Resources automatically closed on exit
```

**BundleData Fields**:
```python
class BundleData(NamedTuple):
    asset_finder: AssetFinder  # Asset metadata lookup
    equity_minute_bar_reader: BcolzMinuteBarReader  # Minute data
    equity_daily_bar_reader: BcolzDailyBarReader  # Daily data
    adjustment_reader: SQLiteAdjustmentReader  # Splits, dividends
```

---

## Bundle Maintenance

### clean()

Remove old bundle ingestions to free disk space.

**Signature**:
```python
def clean(
    name: str,
    before: datetime | None = None,
    after: datetime | None = None,
    keep_last: int | None = None,
    environ: dict = os.environ
) -> set[str]
```

**Parameters**:
- `name` (str): Bundle name
- `before` (datetime, optional): Remove ingestions before this date
- `after` (datetime, optional): Remove ingestions after this date
- `keep_last` (int, optional): Keep only last N ingestions
- `environ` (dict, optional): Environment variables (default: os.environ)

**Returns**:
- `set[str]`: Paths of removed ingestion directories

**Raises**:
- `UnknownBundle`: If bundle not registered
- `BadClean`: If invalid parameter combination

**Constraints**:
- Must specify exactly one of: `before`, `after`, `keep_last`
- Cannot mix `before`/`after` with `keep_last`

**Example - Keep Last N**:
```python
from rustybt.data.bundles import clean

# Keep only last 3 ingestions
removed = clean('my-bundle', keep_last=3)
print(f"Removed {len(removed)} old ingestions")
```

**Example - Remove Old Data**:
```python
import pandas as pd
from rustybt.data.bundles import clean

# Remove ingestions before 2023
cutoff = pd.Timestamp('2023-01-01', tz='UTC')
removed = clean('my-bundle', before=cutoff)

for path in removed:
    print(f"Removed: {path}")
```

**Example - Remove Recent Data**:
```python
import pandas as pd
from rustybt.data.bundles import clean

# Remove ingestions after 2024 (keep only historical)
cutoff = pd.Timestamp('2024-01-01', tz='UTC')
removed = clean('my-bundle', after=cutoff)
```

**Notes**:
- Permanently deletes data (cannot be undone)
- Does not affect bundle registration
- Frees disk space
- Use with caution in production

---

## Bundle Utilities

### bundles

Dictionary of all registered bundles.

**Type**: `MappingProxy[str, RegisteredBundle]`

**Example**:
```python
from rustybt.data.bundles import bundles

# List all registered bundles
print("Registered bundles:")
for name, bundle in bundles.items():
    print(f"  - {name}: {bundle.calendar_name} calendar")

# Check if bundle exists
if 'my-bundle' in bundles:
    print("Bundle is registered")
```

---

### ingestions_for_bundle()

List all ingestion timestamps for a bundle.

**Signature**:
```python
def ingestions_for_bundle(
    bundle: str,
    environ: dict | None = None
) -> list[pd.Timestamp]
```

**Parameters**:
- `bundle` (str): Bundle name
- `environ` (dict, optional): Environment variables

**Returns**:
- `list[pd.Timestamp]`: List of ingestion timestamps (newest first)

**Example**:
```python
from rustybt.data.bundles import ingestions_for_bundle

# List all ingestions
ingestions = ingestions_for_bundle('my-bundle')

print(f"Bundle has {len(ingestions)} ingestions:")
for ts in ingestions:
    print(f"  - {ts}")

# Get most recent
if ingestions:
    latest = ingestions[0]
    print(f"Latest ingestion: {latest}")
```

---

### to_bundle_ingest_dirname()

Convert timestamp to bundle directory name.

**Signature**:
```python
def to_bundle_ingest_dirname(ts: pd.Timestamp) -> str
```

**Parameters**:
- `ts` (pd.Timestamp): Timestamp to convert

**Returns**:
- `str`: Directory name (ISO format with `;` instead of `:`)

**Example**:
```python
import pandas as pd
from rustybt.data.bundles import to_bundle_ingest_dirname

ts = pd.Timestamp('2024-01-15 10:30:00', tz='UTC')
dirname = to_bundle_ingest_dirname(ts)
print(dirname)  # "2024-01-15T10;30;00+00;00"
```

---

### from_bundle_ingest_dirname()

Convert bundle directory name back to timestamp.

**Signature**:
```python
def from_bundle_ingest_dirname(dirname: str) -> pd.Timestamp
```

**Parameters**:
- `dirname` (str): Directory name

**Returns**:
- `pd.Timestamp`: Parsed timestamp

**Example**:
```python
from rustybt.data.bundles import from_bundle_ingest_dirname

dirname = "2024-01-15T10;30;00.000000"
ts = from_bundle_ingest_dirname(dirname)
print(ts)  # Timestamp('2024-01-15 10:30:00')
```

---

## Exceptions

### UnknownBundle

Raised when referencing a bundle that hasn't been registered.

**Inheritance**: `click.ClickException`, `LookupError`

**Attributes**:
- `name` (str): The unknown bundle name
- `message` (str): Error message

**Example**:
```python
from rustybt.data.bundles import load, UnknownBundle

try:
    load('nonexistent-bundle')
except UnknownBundle as e:
    print(f"Bundle not found: {e.name}")
    print(f"Error: {e.message}")
```

---

### BadClean

Raised when invalid parameters passed to `clean()`.

**Inheritance**: `click.ClickException`, `ValueError`

**Example**:
```python
from rustybt.data.bundles import clean
from rustybt.data.bundles.core import BadClean
import pandas as pd

try:
    # Invalid: mixing before with keep_last
    clean(
        'my-bundle',
        before=pd.Timestamp('2023-01-01'),
        keep_last=5  # Cannot use both!
    )
except BadClean as e:
    print(f"Invalid clean parameters: {e}")
```

---

## Advanced Usage

### Custom Data Writers

```python
import pandas as pd
from rustybt.data.bundles import register

@register('custom-format')
def custom_ingest(
    environ, asset_db_writer, minute_bar_writer,
    daily_bar_writer, adjustment_writer, calendar,
    start_session, end_session, cache, show_progress, output_dir
):
    """Custom ingestion with adjustments."""

    # Write assets
    equities = pd.DataFrame({
        'symbol': ['AAPL', 'MSFT'],
        'exchange': 'NASDAQ',
        'asset_name': ['Apple Inc.', 'Microsoft Corp.'],
        'start_date': [start_session, start_session],
        'end_date': [end_session, end_session],
    })
    asset_db_writer.write(equities=equities)

    # Write daily bars
    for sid, symbol in enumerate(['AAPL', 'MSFT']):
        data = fetch_data(symbol)  # Your data fetch logic
        daily_bar_writer.write_sid(sid, data)

    # Write splits
    splits = pd.DataFrame({
        'sid': [0],  # AAPL
        'effective_date': [pd.Timestamp('2023-06-01')],
        'ratio': [4.0],  # 4-for-1 split
    })
    adjustment_writer.write_splits(splits)

    # Write dividends
    dividends = pd.DataFrame({
        'sid': [0, 1],  # AAPL, MSFT
        'ex_date': [pd.Timestamp('2023-03-15'), pd.Timestamp('2023-03-20')],
        'declared_date': [pd.Timestamp('2023-03-01'), pd.Timestamp('2023-03-05')],
        'pay_date': [pd.Timestamp('2023-03-30'), pd.Timestamp('2023-04-05')],
        'amount': [0.25, 0.68],
    })
    adjustment_writer.write_dividends(dividends)
```

---

### Crypto Bundle (24/7 Calendar)

```python
from rustybt.data.bundles import register
from rustybt.data.adapters import CCXTAdapter

@register('crypto-btc-eth', calendar_name='24/7')
def crypto_ingest(
    environ, asset_db_writer, minute_bar_writer,
    daily_bar_writer, adjustment_writer, calendar,
    start_session, end_session, cache, show_progress, output_dir
):
    """Ingest crypto data with 24/7 trading."""
    adapter = CCXTAdapter(exchange_id='binance')

    symbols = ['BTC/USDT', 'ETH/USDT']
    data = adapter.fetch_ohlcv(
        symbols=symbols,
        start=str(start_session),
        end=str(end_session),
        resolution='1h'
    )

    # Write metadata (no splits/dividends for crypto)
    asset_db_writer.write(
        equities=pd.DataFrame({
            'symbol': symbols,
            'exchange': 'binance',
            'asset_name': symbols,
        })
    )

    # Write minute data (1-hour bars)
    for sid, symbol in enumerate(symbols):
        symbol_data = data.filter(pl.col('symbol') == symbol).to_pandas()
        minute_bar_writer.write_sid(sid, symbol_data)
```

---

## Best Practices

### 1. Bundle Naming

```python
# Good: Descriptive, includes key info
'yfinance-sp500-daily'
'ccxt-binance-btc-hourly'
'csv-custom-stocks-2023'

# Avoid: Vague or overly generic
'data'
'bundle1'
'test'
```

### 2. Regular Maintenance

```python
# Set up periodic cleanup
from rustybt.data.bundles import clean

def maintain_bundles():
    """Weekly bundle maintenance."""
    bundles_to_clean = ['stocks', 'crypto', 'forex']

    for bundle in bundles_to_clean:
        # Keep last 4 weeks of data
        removed = clean(bundle, keep_last=4)
        print(f"{bundle}: removed {len(removed)} old ingestions")
```

### 3. Error Handling

```python
from rustybt.data.bundles import ingest, UnknownBundle

def safe_ingest(bundle_name):
    """Ingest with proper error handling."""
    try:
        ingest(bundle_name, show_progress=True)
        print(f"✓ Successfully ingested {bundle_name}")
    except UnknownBundle:
        print(f"✗ Bundle '{bundle_name}' not registered")
    except Exception as e:
        print(f"✗ Ingestion failed: {e}")
        raise
```

### 4. Testing Bundles

```python
import tempfile
import os
from rustybt.data.bundles import register, ingest, load

def test_custom_bundle():
    """Test bundle in isolated environment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override data directory
        test_environ = os.environ.copy()
        test_environ['RUSTYBT_ROOT'] = tmpdir

        # Register and ingest
        @register('test-bundle')
        def test_ingest(*args, **kwargs):
            # Minimal test data
            pass

        ingest('test-bundle', environ=test_environ)
        bundle_data = load('test-bundle', environ=test_environ)

        assert bundle_data.asset_finder is not None
        print("✓ Bundle test passed")
```

---

## See Also

- [Catalog Overview](README.md) - Bundle metadata management
- [Data Adapters](../adapters/README.md) - Data source adapters
- [Metadata Tracking](metadata-tracking.md) - Automatic metadata collection
- [Migration Guide](migration-guide.md) - HDF5/Bcolz to Parquet migration
