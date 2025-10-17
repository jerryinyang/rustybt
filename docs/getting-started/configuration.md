# Configuration Guide

RustyBT provides several configuration options to customize its behavior.

## Environment Configuration

### Setting Up Environment Variables

Create a `.env` file in your project root:

```bash
# Data directories
RUSTYBT_DATA_DIR=/path/to/data
RUSTYBT_CACHE_DIR=/path/to/cache

# Decimal precision (Epic 2)
RUSTYBT_DECIMAL_PRECISION=8

# Logging
RUSTYBT_LOG_LEVEL=INFO
RUSTYBT_LOG_FILE=/path/to/logs/rustybt.log
```

## Decimal Precision Configuration

Configure financial calculation precision:

```python
from decimal import Decimal, getcontext
from rustybt.finance.decimal import DecimalLedger, DecimalConfig

# Set global precision
getcontext().prec = 28

# Configure decimal precision
config = DecimalConfig()  # Uses defaults from config file

# Use Decimal for calculations
ledger = DecimalLedger(
    starting_cash=Decimal("100000.00"),
    config=config
)
```

See [Decimal Precision Configuration](../guides/decimal-precision-configuration.md) for more details.

## Caching Configuration

Configure the intelligent caching system:

```python
from rustybt.data.polars.cache_manager import CacheManager

# Initialize cache manager
cache_manager = CacheManager(
    db_path="./data/cache/metadata.db",
    cache_directory="./data/cache",
    hot_cache_size_mb=1024,     # 1 GB hot cache
    cold_cache_size_mb=10240    # 10 GB cold cache
)
```

See [Caching System Guide](../guides/caching-system.md) for more details.

## Broker Configuration

Configure broker connections for live trading:

```python
from rustybt.live.brokers import CCXTBrokerAdapter

broker = CCXTBrokerAdapter(
    exchange_id='binance',
    api_key='YOUR_API_KEY',
    api_secret='YOUR_API_SECRET',
    testnet=True,  # Use testnet first!
    rate_limit=True,
    timeout=30000
)
```

## Logging Configuration

Configure structured logging:

```python
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
```

## Performance Configuration

### Polars Configuration

```python
import polars as pl

# Configure Polars for optimal performance
pl.Config.set_streaming_chunk_size(50000)
pl.Config.set_tbl_width_chars(120)
```

### Parallel Processing

```python
from rustybt.optimization import ParallelOptimizer

optimizer = ParallelOptimizer(
    n_jobs=-1,  # Use all CPUs
    backend='multiprocessing',
    verbose=True
)
```

## Next Steps

- [Decimal Precision Guide](../guides/decimal-precision-configuration.md)
- [Caching System Guide](../guides/caching-system.md)
- [Testnet Setup Guide](../guides/testnet-setup-guide.md)
