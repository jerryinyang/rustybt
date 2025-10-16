# Data Management & Pipeline Systems

Comprehensive guide to RustyBT's data infrastructure, covering everything from data acquisition to pipeline-based feature engineering.

## Overview

RustyBT's data management system provides a flexible, high-performance framework for handling financial market data across multiple asset classes and data sources. The system is built on modern technologies (Polars, Parquet) while maintaining backward compatibility with Zipline's bcolz/HDF5 formats.

### Architecture Layers

```
┌─────────────────────────────────────────────────────┐
│             Strategy / Algorithm                     │
├─────────────────────────────────────────────────────┤
│             Pipeline (Factors/Filters)               │
├─────────────────────────────────────────────────────┤
│      Data Portal (Unified Data Access Layer)        │
├─────────────────────────────────────────────────────┤
│   Bar Readers (Daily/Minute/HDF5/Parquet/Bcolz)    │
├─────────────────────────────────────────────────────┤
│     Data Catalog (Bundle Management & Metadata)     │
├─────────────────────────────────────────────────────┤
│     Data Adapters (CCXT/YFinance/CSV/APIs)         │
├─────────────────────────────────────────────────────┤
│          Data Sources (Exchanges/APIs)              │
└─────────────────────────────────────────────────────┘
```

## Quick Navigation

### Data Acquisition
- **[Data Adapters](adapters/overview.md)** - Fetch data from external sources (crypto exchanges, stock APIs, CSV files)
  - [CCXT Adapter](adapters/ccxt.md) - 100+ cryptocurrency exchanges
  - [YFinance Adapter](adapters/yfinance.md) - Stocks, ETFs, indices via Yahoo Finance
  - [CSV Adapter](adapters/csv.md) - Custom CSV data with flexible schemas
  - [Polygon Adapter](adapters/polygon.md) - Real-time and historical market data
  - [Alpaca Adapter](adapters/alpaca.md) - Commission-free trading data
  - [AlphaVantage Adapter](adapters/alphavantage.md) - Global market data and fundamentals

### Data Storage & Management
- **[Data Catalog](catalog/bundles.md)** - Central registry for data bundles and metadata
  - [Bundles](catalog/bundles.md) - Creating and managing data bundles
  - [Migration](catalog/migration.md) - Migrating from HDF5/bcolz to Parquet

### Data Access
- **[Data Readers](readers/data-portal.md)** - Reading and accessing stored data
  - [Data Portal](readers/data-portal.md) - Unified data access interface
  - [Bar Readers](readers/bar-readers.md) - Daily, minute, and tick data readers
  - [History Loader](readers/history-loader.md) - Efficient historical data loading
  - [Continuous Futures](readers/continuous-futures.md) - Continuous contract construction

### Feature Engineering
- **[Pipeline System](pipeline/overview.md)** - Building computational graphs for features
  - [Factors](pipeline/factors.md) - Numerical computations and indicators
  - [Filters](pipeline/filters.md) - Boolean selection and screening
  - [Loaders](pipeline/loaders.md) - Custom data loading for pipeline
  - [Expressions](pipeline/expressions.md) - Combining and transforming pipeline terms

### Performance Optimization
- **Performance (Coming soon)** - Optimization strategies
  - Caching (Coming soon) - Data and computation caching
  - Optimization (Coming soon) - Performance tuning techniques
  - Troubleshooting (Coming soon) - Common issues and solutions

## Key Concepts

### Data Formats

RustyBT supports multiple data storage formats:

| Format | Read Speed | Write Speed | Compression | Interoperability | Status |
|--------|-----------|-------------|-------------|------------------|--------|
| **Parquet** | ⚡⚡⚡ Fast | ⚡⚡⚡ Fast | ✅ Excellent | ✅ Industry standard | **Recommended** |
| **HDF5** | ⚡⚡ Medium | ⚡ Slow | ⚡⚡ Good | ⚡ Limited | Supported |
| **bcolz** | ⚡⚡ Medium | ⚡⚡ Medium | ⚡⚡ Good | ❌ None | Legacy |

**Recommendation**: Use Parquet for new projects. See [Migration Guide](catalog/migration.md) for converting existing data.

### Data Resolution

Supported resolutions across adapters:

- **Tick**: Individual trades (not yet supported in all adapters)
- **Minute**: 1m, 5m, 15m, 30m bars
- **Hourly**: 1h, 2h, 4h bars
- **Daily**: End-of-day OHLCV data
- **Weekly/Monthly**: Aggregated bars

### Asset Classes

- **Equities**: Stocks, ETFs, ADRs
- **Cryptocurrencies**: Spot and perpetual futures
- **Futures**: Commodities, indices, financials
- **Forex**: Currency pairs
- **Options**: Equity and index options (limited support)

## Common Workflows

### Workflow 1: Fetching and Storing Crypto Data

```python
from rustybt.data.adapters import CCXTAdapter
from rustybt.data.bundles import register
import pandas as pd

# 1. Create adapter
adapter = CCXTAdapter(exchange_id='binance')

# 2. Fetch data
df = await adapter.fetch(
    symbols=['BTC/USDT', 'ETH/USDT'],
    start_date=pd.Timestamp('2024-01-01'),
    end_date=pd.Timestamp('2024-01-31'),
    resolution='1h'
)

# 3. Register as bundle
register(
    bundle_name='crypto_data',
    adapter=adapter,
    symbols=['BTC/USDT', 'ETH/USDT'],
    start_date='2024-01-01',
    end_date='2024-01-31'
)
```

### Workflow 2: Loading Data in Strategy

```python
from rustybt.algorithm import TradingAlgorithm

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        self.btc = self.symbol('BTC/USDT')

    def handle_data(self, context, data):
        # Access current bar
        current_price = data.current(self.btc, 'close')

        # Access historical data
        prices = data.history(
            self.btc,
            fields='close',
            bar_count=20,
            frequency='1d'
        )

        # Use in strategy logic
        ma_20 = prices.mean()
        if current_price > ma_20:
            self.order(self.btc, 100)
```

### Workflow 3: Building Pipeline Features

```python
from rustybt.pipeline import Pipeline
from rustybt.pipeline.data import EquityPricing
from rustybt.pipeline.factors import SimpleMovingAverage, RSI

# Define pipeline
pipe = Pipeline()

# Add factors
pipe.add(
    SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20),
    name='sma_20'
)

pipe.add(
    RSI(window_length=14),
    name='rsi'
)

# Run pipeline in strategy
def before_trading_start(self, context, data):
    context.pipeline_output = self.pipeline_output('my_pipe')
```

## Data Quality & Validation

All data flows through validation layers:

1. **Schema Validation**: Ensures correct columns and data types
2. **OHLCV Relationships**: Validates High ≥ Open, Close, Low
3. **Temporal Consistency**: Checks for gaps and ordering
4. **Decimal Precision**: Financial-grade arithmetic (28 decimal places)

See [Data Quality](readers/bar-readers.md#data-quality) for details.

## Performance Considerations

### Caching Strategy

```python
from rustybt.data.polars.cache_manager import CacheManager

# Configure caching
cache = CacheManager(
    max_memory_mb=1024,  # 1GB cache
    disk_cache_path='/path/to/cache'
)

# Cache is automatically used by data portal
```

### Memory Management

- **Lazy Evaluation**: Polars DataFrames use lazy evaluation to minimize memory
- **Chunked Reading**: Large datasets read in chunks
- **LRU Eviction**: Least recently used data evicted from cache

### Parallel Processing

```python
# Enable parallel data loading
bundle.ingest(
    symbols=['AAPL', 'GOOGL', 'MSFT'],
    start_date='2020-01-01',
    end_date='2024-01-01',
    n_workers=4  # Parallel workers
)
```

## Configuration

### Environment Variables

```bash
# Data directory
export RUSTYBT_DATA_DIR=/path/to/data

# Cache settings
export RUSTYBT_CACHE_SIZE_MB=2048
export RUSTYBT_CACHE_DIR=/path/to/cache

# API credentials (secure storage recommended)
export POLYGON_API_KEY=your_key_here
export ALPACA_API_KEY=your_key_here
export ALPACA_API_SECRET=your_secret_here
```

### Configuration File

```yaml
# ~/.rustybt/config.yaml
data:
  root_dir: /path/to/data
  default_format: parquet
  compression: snappy

cache:
  enabled: true
  max_size_mb: 2048
  disk_cache: true

adapters:
  ccxt:
    rate_limit: 10  # requests per second
  yfinance:
    rate_limit: 2
```

## Next Steps

1. **New to RustyBT?** Start with [Data Adapters](adapters/overview.md)
2. **Migrating from Zipline?** See [Migration Guide](catalog/migration.md)
3. **Building Features?** Check out [Pipeline System](pipeline/overview.md)
4. **Performance Issues?** Read Optimization Guide (Coming soon)

## Support & Resources

- **Documentation**: Complete API reference at [rustybt.readthedocs.io](https://rustybt.readthedocs.io)
- **Examples**: See `examples/` directory for complete strategies
- **Issues**: Report bugs at [GitHub Issues](https://github.com/bmad-dev/rustybt/issues)
- **Discussions**: Community forum at [GitHub Discussions](https://github.com/bmad-dev/rustybt/discussions)
