# DataSource API Reference

## Overview

The `DataSource` interface provides a unified abstraction for fetching market data from various sources (brokers, data vendors, files). All adapters implement this interface for consistent usage.

## Base Interface

### `DataSource` (Abstract Base Class)

```python
from rustybt.data.sources.base import DataSource, DataSourceMetadata
import pandas as pd
import polars as pl

class DataSource(ABC):
    """Abstract base class for data sources."""

    @abstractmethod
    async def fetch(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str
    ) -> pl.DataFrame:
        """Fetch OHLCV data for symbols.

        Args:
            symbols: List of ticker symbols
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)
            frequency: Data frequency ("daily", "hourly", "minute")

        Returns:
            Polars DataFrame with columns:
            - symbol: str
            - date: date (for daily) or timestamp: datetime (for intraday)
            - open: Decimal
            - high: Decimal
            - low: Decimal
            - close: Decimal
            - volume: Decimal
        """
        pass

    @abstractmethod
    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs
    ) -> Path:
        """Ingest data and create bundle.

        Args:
            bundle_name: Name for the bundle
            symbols: Symbols to ingest
            start: Start date
            end: End date
            frequency: Data frequency
            **kwargs: Adapter-specific options

        Returns:
            Path to created bundle directory
        """
        pass

    @abstractmethod
    def get_metadata(self) -> DataSourceMetadata:
        """Get data source metadata."""
        pass

    @abstractmethod
    def supports_live(self) -> bool:
        """Whether this source supports live streaming."""
        pass
```

### `DataSourceMetadata`

```python
@dataclass
class DataSourceMetadata:
    """Metadata about a data source."""
    source_type: str  # "yfinance", "alpaca", "ccxt", etc.
    source_url: str  # API endpoint
    api_version: str  # API version
    supports_live: bool  # Real-time streaming support
    supported_frequencies: list[str]  # ["daily", "hourly", "minute"]
    rate_limit: Optional[int] = None  # Requests per minute
    requires_auth: bool = False
```

## Built-in Adapters

### YFinance (via DataSourceRegistry)

Free historical data from Yahoo Finance (15-minute delayed).

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source("yfinance")

    # Fetch data
    df = await source.fetch(
        symbols=["AAPL", "MSFT"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

    # Ingest to bundle
    await source.ingest_to_bundle(
        bundle_name="stocks-2023",
        symbols=["AAPL", "MSFT", "GOOGL"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

asyncio.run(main())
```

**Limitations**:
- 15-minute delayed quotes
- Rate limits: ~2000 requests/hour
- No real-time streaming
- Historical data only

### Alpaca (via DataSourceRegistry)

Real-time and historical stock data via Alpaca Markets API.

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source(
        "alpaca",
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET",
        paper_trading=True,
    )
    df = await source.fetch(
        symbols=["AAPL"],
        start=pd.Timestamp.now() - pd.Timedelta(hours=1),
        end=pd.Timestamp.now(),
        frequency="1m"
    )

asyncio.run(main())
```

**Features**:
- Real-time quotes (IEX feed)
- WebSocket streaming
- Paper trading mode
- Free tier available

### CCXT (via DataSourceRegistry)

Cryptocurrency data via CCXT library (100+ exchanges).

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source(
        "ccxt",
        exchange="binance",
        # api_key / api_secret optional depending on endpoint
    )
    df = await source.fetch(
        symbols=["BTC/USDT", "ETH/USDT"],
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-12-31"),
        frequency="1h"
    )

asyncio.run(main())
```

**Supported Exchanges**: binance, coinbase, kraken, bybit, okx, and 100+ more.

### Polygon (via DataSourceRegistry)

High-quality financial data from Polygon.io.

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source(
        "polygon",
        api_key="YOUR_API_KEY"
    )
    df = await source.fetch(
        symbols=["AAPL"],
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-01-31"),
        frequency="1m"
    )

asyncio.run(main())
```

**Features**:
- Real-time and historical
- Stocks, options, forex, crypto
- Tick-level data available
- Premium tiers for more data

### CSV (via DataSourceRegistry)

Load data from CSV files.

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source(
        "csv",
        data_dir="/path/to/csv/files",
    )
    df = await source.fetch(
        symbols=["AAPL", "MSFT"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

asyncio.run(main())
```

**CSV Format**:
```csv
date,open,high,low,close,volume
2023-01-01,100.0,105.0,99.0,103.0,1000000
2023-01-02,103.0,106.0,102.0,105.0,1200000
```

## Registry Pattern

### DataSourceRegistry

Centralized registry for managing data sources.

```python
from rustybt.data.sources import DataSourceRegistry

# Get source by name
source = DataSourceRegistry.get_source("yfinance")

# Get source with config
source = DataSourceRegistry.get_source(
    "alpaca",
    api_key="...",
    api_secret="..."
)

# List available sources
sources = DataSourceRegistry.list_sources()
print(sources)  # ["alpaca", "alphavantage", "ccxt", "csv", "polygon", "yfinance"]
```

## Creating Custom Adapters

### Example: Custom REST API Adapter (advanced)

---

**See Also**:
- [Data Management Performance](data-management/README.md)
- [Data Ingestion Guide](../guides/data-ingestion.md)
- [Live vs Backtest Data](../guides/live-vs-backtest-data.md)
