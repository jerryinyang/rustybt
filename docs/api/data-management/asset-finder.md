# Asset Finder API

The **AssetFinder** is rustybt's interface for querying and retrieving assets (stocks, futures, etc.) from bundles. This guide covers the `ParquetAssetFinder` implementation used by modern Parquet-based bundles.

## Overview

The `AssetFinder` provides methods to:

- Retrieve all assets in a bundle
- Look up assets by symbol
- Retrieve assets by identifier (sid)
- Query bundle metadata

All Parquet bundles (`yfinance-profiling`, csvdir, custom adapters) use the `ParquetAssetFinder` implementation.

---

## Common Use Cases

### Get All Assets in a Bundle

The most common use case - retrieve all assets programmatically to iterate over them in your strategy.

```python
from rustybt.api import symbol
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

def initialize(context):
    """Initialize strategy with all assets in bundle."""
    # Get all asset identifiers
    all_sids = context.asset_finder.sids

    # Retrieve all asset objects
    all_assets = context.asset_finder.retrieve_all(all_sids)

    # Store for use in handle_data
    context.all_assets = all_assets

    print(f"Found {len(all_assets)} assets in bundle:")
    for asset in all_assets:
        print(f"  - {asset.symbol} (sid: {asset.sid})")

def handle_data(context, data):
    """Process data for all assets."""
    # Iterate over all assets
    for asset in context.all_assets:
        current_price = data.current(asset, 'price')
        print(f"{asset.symbol}: ${current_price}")

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2024-01-01'),
        end=pd.Timestamp('2024-01-31'),
        capital_base=10000,
    )
```

### Look Up Asset by Symbol

Retrieve a specific asset by its ticker symbol:

```python
def initialize(context):
    """Look up specific assets."""
    # Single asset lookup
    aapl = context.asset_finder.lookup_symbol('AAPL')
    print(f"Found: {aapl.symbol} with sid {aapl.sid}")

    # Multiple asset lookup
    tech_stocks = context.asset_finder.lookup_symbols(['AAPL', 'GOOGL', 'MSFT'])
    context.tech_portfolio = tech_stocks
```

### Retrieve Asset by SID

If you have an asset identifier (sid), retrieve the asset object directly:

```python
def initialize(context):
    """Retrieve assets by identifier."""
    # Get specific asset by sid
    asset = context.asset_finder.retrieve_asset(0)
    print(f"SID 0 is: {asset.symbol}")

    # Get multiple assets by sids
    sids = [0, 1, 2]
    assets = context.asset_finder.retrieve_all(sids)
    context.portfolio_assets = assets
```

### Filter Assets Dynamically

Combine methods to build custom asset filters:

```python
def initialize(context):
    """Select assets based on criteria."""
    # Get all assets
    all_assets = context.asset_finder.retrieve_all(
        context.asset_finder.sids
    )

    # Filter by some criterion (e.g., symbol pattern)
    tech_assets = [
        asset for asset in all_assets
        if asset.symbol in ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'NVDA', 'TSLA']
    ]

    context.watchlist = tech_assets
    print(f"Monitoring {len(tech_assets)} tech stocks")
```

---

## API Reference

### Properties

#### `.sids`

Returns all asset identifiers in the bundle.

**Returns:** `pd.Index` - Index of all asset identifiers (sids)

**Example:**
```python
def initialize(context):
    all_sids = context.asset_finder.sids
    print(f"Bundle contains {len(all_sids)} assets")
    print(f"SID range: {all_sids.min()} to {all_sids.max()}")
```

---

### Methods

#### `.retrieve_all(sids)`

Retrieve multiple assets by their identifiers.

**Parameters:**

- `sids` (iterable[int]): Asset identifiers to retrieve

**Returns:** `list[Asset]` - List of Asset objects

**Raises:**

- `SidsNotFound`: If any sid does not exist in the bundle

**Example:**
```python
def initialize(context):
    # Get all assets
    all_assets = context.asset_finder.retrieve_all(
        context.asset_finder.sids
    )

    # Or get specific subset
    selected_sids = [0, 1, 2, 3, 4]
    selected_assets = context.asset_finder.retrieve_all(selected_sids)
```

---

#### `.retrieve_asset(sid, default_none=False)`

Retrieve a single asset by its identifier.

**Parameters:**

- `sid` (int): Asset identifier
- `default_none` (bool, optional): If True, return None instead of raising exception. Default: False

**Returns:** `Asset | None` - Asset object, or None if not found and `default_none=True`

**Raises:**

- `SidsNotFound`: If sid does not exist and `default_none=False`

**Example:**
```python
def initialize(context):
    # Get asset, raise exception if not found
    asset = context.asset_finder.retrieve_asset(0)

    # Get asset, return None if not found
    maybe_asset = context.asset_finder.retrieve_asset(999, default_none=True)
    if maybe_asset is None:
        print("Asset 999 not found")
```

---

#### `.lookup_symbol(symbol, as_of_date=None, fuzzy=False, country_code=None)`

Look up an asset by its ticker symbol.

**Parameters:**

- `symbol` (str): Ticker symbol (e.g., 'AAPL', 'GOOGL')
- `as_of_date` (pd.Timestamp, optional): Not used in Parquet bundles (all symbols always available)
- `fuzzy` (bool, optional): Not implemented for Parquet bundles
- `country_code` (str, optional): Not used in Parquet bundles

**Returns:** `Asset` - The asset with the given symbol

**Raises:**

- `SymbolNotFound`: If no asset with the given symbol exists

**Example:**
```python
def initialize(context):
    try:
        aapl = context.asset_finder.lookup_symbol('AAPL')
        context.primary_asset = aapl
    except SymbolNotFound:
        print("AAPL not in bundle")
```

---

#### `.lookup_symbols(symbols, as_of_date=None, fuzzy=False)`

Look up multiple assets by their ticker symbols.

**Parameters:**

- `symbols` (iterable[str]): Ticker symbols to look up
- `as_of_date` (pd.Timestamp, optional): Not used in Parquet bundles
- `fuzzy` (bool, optional): Not implemented for Parquet bundles

**Returns:** `list[Asset]` - List of assets

**Raises:**

- `SymbolNotFound`: If any symbol does not exist

**Example:**
```python
def initialize(context):
    # Look up multiple symbols at once
    watchlist = context.asset_finder.lookup_symbols([
        'AAPL', 'GOOGL', 'MSFT', 'AMZN'
    ])
    context.watchlist = watchlist
```

---

## Asset Object

Assets retrieved from the AssetFinder have the following key attributes:

### Equity Assets

```python
asset = context.asset_finder.lookup_symbol('AAPL')

# Common attributes
print(asset.sid)           # Asset identifier (int)
print(asset.symbol)        # Ticker symbol (str)
print(asset.asset_name)    # Full name (str)
print(asset.exchange)      # Exchange (str, e.g., 'NASDAQ')
print(asset.start_date)    # First available date
print(asset.end_date)      # Last available date
print(asset.first_traded)  # First trade date
```

### Future Assets

Futures have additional attributes:

```python
future = context.asset_finder.lookup_symbol('ESH21')

# Future-specific attributes
print(future.root_symbol)      # Root symbol (e.g., 'ES')
print(future.expiration_date)  # Contract expiration
print(future.notice_date)      # First notice date
print(future.tick_size)        # Minimum price movement
print(future.multiplier)       # Contract size multiplier
```

---

## Error Handling

### SymbolNotFound

Raised when a symbol doesn't exist in the bundle:

```python
from rustybt.errors import SymbolNotFound

def initialize(context):
    try:
        asset = context.asset_finder.lookup_symbol('INVALID')
    except SymbolNotFound as e:
        print(f"Symbol not found: {e}")
        # Fallback to a different asset
        asset = context.asset_finder.lookup_symbol('AAPL')
```

### SidsNotFound

Raised when one or more sids don't exist:

```python
from rustybt.errors import SidsNotFound

def initialize(context):
    try:
        assets = context.asset_finder.retrieve_all([0, 1, 999])
    except SidsNotFound as e:
        print(f"Invalid sids: {e.sids}")
        # Retry with valid sids only
        assets = context.asset_finder.retrieve_all([0, 1])
```

---

## Performance Tips

### Cache Asset Lookups

Look up assets once in `initialize()` and store them:

```python
def initialize(context):
    # ✅ Good: Lookup once, reuse many times
    context.all_assets = context.asset_finder.retrieve_all(
        context.asset_finder.sids
    )

def handle_data(context, data):
    # Use cached assets
    for asset in context.all_assets:
        price = data.current(asset, 'price')
```

### Avoid Repeated Symbol Lookups

```python
# ❌ Bad: Looking up symbol every bar
def handle_data(context, data):
    aapl = context.asset_finder.lookup_symbol('AAPL')  # Slow!
    price = data.current(aapl, 'price')

# ✅ Good: Lookup once in initialize
def initialize(context):
    context.aapl = context.asset_finder.lookup_symbol('AAPL')

def handle_data(context, data):
    price = data.current(context.aapl, 'price')  # Fast!
```

---

## Common Patterns

### Universe Selection

Select a subset of assets for trading:

```python
def initialize(context):
    """Select top N liquid assets."""
    # Get all assets
    all_assets = context.asset_finder.retrieve_all(
        context.asset_finder.sids
    )

    # In production, you might filter by:
    # - Market cap
    # - Average volume
    # - Sector/industry
    # Here we just take first 10 for example
    context.universe = all_assets[:10]

    print(f"Trading universe: {[a.symbol for a in context.universe]}")
```

### Symbol to Asset Mapping

Create a dictionary for quick lookups:

```python
def initialize(context):
    """Create symbol-to-asset mapping."""
    all_assets = context.asset_finder.retrieve_all(
        context.asset_finder.sids
    )

    # Build lookup dict
    context.asset_map = {
        asset.symbol: asset
        for asset in all_assets
    }

    # Now you can quickly access any asset
    context.watchlist_symbols = ['AAPL', 'GOOGL', 'MSFT']

def handle_data(context, data):
    """Use the mapping."""
    for symbol in context.watchlist_symbols:
        asset = context.asset_map[symbol]
        price = data.current(asset, 'price')
```

---

## Bundle Compatibility

The `ParquetAssetFinder` API is consistent across all Parquet-based bundles:

| Bundle Type | AssetFinder | Notes |
|-------------|-------------|-------|
| `yfinance-profiling` | `ParquetAssetFinder` | Free Yahoo Finance data |
| `csvdir` | `ParquetAssetFinder` | Custom CSV data |
| Custom adapters | `ParquetAssetFinder` | Your own data sources |
| Legacy bundles | May differ | Older bundles may use different AssetFinder |

**All examples on this page work with any Parquet bundle.**

---

## Related Documentation

- [Quick Start Guide](../../getting-started/quickstart.md) - Basic strategy examples
- [Bundle System](catalog/bundle-system.md) - Understanding bundles
- [Data Portal API](readers/data-portal.md) - Accessing price data
- [Pipeline API](../computation/pipeline-api.md) - Advanced data processing

---

## Frequently Asked Questions

### Why doesn't `retrieve_equities()` exist?

The `ParquetAssetFinder` uses a unified interface:

```python
# ❌ Old pattern (doesn't exist)
# all_equities = context.asset_finder.retrieve_equities(all_sids)

# ✅ Correct pattern
all_assets = context.asset_finder.retrieve_all(context.asset_finder.sids)
```

The `retrieve_all()` method works for all asset types (equities, futures, etc.).

### How do I filter for only equities?

Check the asset type:

```python
from rustybt.assets import Equity

def initialize(context):
    all_assets = context.asset_finder.retrieve_all(
        context.asset_finder.sids
    )

    # Filter for equities only
    equities = [asset for asset in all_assets if isinstance(asset, Equity)]
    context.equity_portfolio = equities
```

### Can I get the full symbol list without retrieving assets?

Yes, but you need to retrieve assets to get symbols:

```python
def initialize(context):
    # Get all sids (fast)
    all_sids = context.asset_finder.sids

    # Get assets to access symbols (required)
    all_assets = context.asset_finder.retrieve_all(all_sids)

    # Extract symbols
    symbols = [asset.symbol for asset in all_assets]
    print(f"Available symbols: {symbols}")
```

### What if a symbol doesn't exist in my bundle?

Handle the `SymbolNotFound` exception:

```python
from rustybt.errors import SymbolNotFound

def initialize(context):
    desired_symbols = ['AAPL', 'GOOGL', 'TSLA', 'NONEXISTENT']
    context.portfolio = []

    for symbol in desired_symbols:
        try:
            asset = context.asset_finder.lookup_symbol(symbol)
            context.portfolio.append(asset)
        except SymbolNotFound:
            print(f"Warning: {symbol} not in bundle, skipping")

    print(f"Portfolio: {[a.symbol for a in context.portfolio]}")
```

---

## Source Code

Implementation: [`rustybt/data/polars/parquet_asset_finder.py`](https://github.com/anthonyb8/rustybt/blob/main/rustybt/data/polars/parquet_asset_finder.py)
