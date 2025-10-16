# Data Bundles

Comprehensive guide to creating, managing, and using data bundles in RustyBT.

## Bundle Lifecycle

1. **Registration**: Define bundle configuration
2. **Ingestion**: Fetch and store data
3. **Usage**: Access data in backtests
4. **Maintenance**: Update and clean old data
5. **Migration**: Convert between formats

## Creating Bundles

### From Data Adapter

```python
from rustybt.data.bundles import register
from rustybt.data.adapters import YFinanceAdapter

register(
    bundle_name='sp500_daily',
    adapter=YFinanceAdapter(),
    symbols=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2020-01-01',
    end_date='2024-01-01',
    calendar_name='NYSE',
    storage_format='parquet'
)
```

### From CSV Files

```python
from rustybt.data.adapters import CSVAdapter
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

register(
    bundle_name='custom_data',
    adapter=CSVAdapter(),
    config=CSVConfig(
        file_path='/data/stocks.csv',
        schema_mapping=SchemaMapping(...)
    ),
    calendar_name='NYSE'
)
```

### Cryptocurrency Bundle

```python
from rustybt.data.adapters import CCXTAdapter

register(
    bundle_name='crypto_hourly',
    adapter=CCXTAdapter(exchange_id='binance'),
    symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
    start_date='2024-01-01',
    end_date='2024-01-31',
    resolution='1h',
    calendar_name='24/7'  # Crypto trades 24/7
)
```

## Ingestion

```python
from rustybt.data.bundles import ingest

# Basic ingestion
ingest('sp500_daily')

# With progress tracking
ingest('sp500_daily', show_progress=True)

# Keep only recent ingestions
ingest('sp500_daily', keep_last=5)
```

## Using Bundles

```python
from rustybt.utils.run_algo import run_algorithm

def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    price = data.current(context.asset, 'close')
    context.order(context.asset, 100)

result = run_algorithm(
    start='2023-01-01',
    end='2023-12-31',
    bundle='sp500_daily',  # Use bundle
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000
)
```
