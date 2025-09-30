# Component Architecture

## Decimal Finance Components

### DecimalLedger
**Purpose:** Portfolio accounting with Decimal arithmetic
**Location:** `rustybt/finance/decimal/ledger.py`
**Zipline Integration:** Extends `zipline.finance.ledger.Ledger`

**Key Responsibilities:**
- Track portfolio value, cash, positions with Decimal precision
- Calculate returns, P&L, leverage with zero rounding errors
- Maintain transaction cost breakdown (commission, slippage, borrow, financing)
- Support configurable precision per asset class

**Dependencies:**
- `DecimalPosition`: Position tracking
- `DecimalTransaction`: Transaction records
- `decimal.Context`: Precision management

**Integration Points:**
- Used by `TradingAlgorithm` for portfolio state
- Updated by `Blotter` on transaction execution
- Queried by `MetricsTracker` for performance calculation

### DecimalPosition
**Purpose:** Position tracking with Decimal precision
**Location:** `rustybt/finance/decimal/position.py`
**Zipline Integration:** Replaces `zipline.finance.position.Position`

**Key Responsibilities:**
- Store position amount, cost basis, market price as Decimal
- Calculate market value, unrealized P&L with precision
- Handle splits, dividends with Decimal accuracy
- Support fractional shares for crypto (0.00000001 BTC)

**Integration Points:**
- Created/updated by `PositionTracker` in `DecimalLedger`
- Referenced by `Order` execution logic
- Exposed via `context.portfolio.positions` in user strategies

### DecimalTransaction
**Purpose:** Transaction record with Decimal precision
**Location:** `rustybt/finance/decimal/transaction.py`
**Zipline Integration:** Replaces `zipline.finance.transaction.Transaction`

**Key Responsibilities:**
- Record trade execution details (price, amount, commission, slippage)
- Store all monetary values as Decimal
- Provide transaction value calculation
- Support audit logging with full precision

**Integration Points:**
- Created by `Blotter` on order fill
- Stored in `order_audit_log` table
- Used by `DecimalLedger` to update positions and cash

## Polars Data Components

### PolarsParquetDailyReader
**Purpose:** Read daily OHLCV bars from Parquet with Decimal columns
**Location:** `rustybt/data/polars/parquet_daily_bars.py`
**Zipline Integration:** Replaces `zipline.data.bcolz_daily_bars.BcolzDailyBarReader`

**Key Responsibilities:**
- Load daily bars from Parquet files partitioned by (year, month)
- Return Polars DataFrames with Decimal columns
- Support lazy loading via `scan_parquet()` for memory efficiency
- Provide date range queries with partition pruning

**Parquet Schema:**
```python
{
    "date": pl.Date,
    "sid": pl.Int64,
    "open": pl.Decimal(precision=18, scale=8),
    "high": pl.Decimal(precision=18, scale=8),
    "low": pl.Decimal(precision=18, scale=8),
    "close": pl.Decimal(precision=18, scale=8),
    "volume": pl.Decimal(precision=18, scale=8),
}
```

**Directory Structure:**
```
data/bundles/quandl/
├── daily_bars/
│   ├── year=2022/
│   │   ├── month=01/
│   │   │   └── data.parquet
│   │   └── month=02/
│   │       └── data.parquet
│   └── year=2023/
│       └── ...
└── metadata.db (SQLite)
```

**Integration Points:**
- Loaded by `PolarsDataPortal`
- Registered with `AssetFinder` for date range queries
- Used by backtesting engine for historical data

### PolarsParquetMinuteReader
**Purpose:** Read minute OHLCV bars from Parquet with Decimal columns
**Location:** `rustybt/data/polars/parquet_minute_bars.py`
**Zipline Integration:** Replaces `zipline.data.bcolz_minute_bars.BcolzMinuteBarReader`

**Key Responsibilities:**
- Load minute bars partitioned by (year, month, day) for efficient queries
- Support sub-second resolution for crypto (microsecond timestamps)
- Lazy evaluation for large date ranges
- Cache hot data in memory using Polars DataFrames

**Partition Strategy:**
```
minute_bars/
├── year=2023/
│   ├── month=01/
│   │   ├── day=01/
│   │   │   └── data.parquet  (~500MB/day for 3000 assets)
│   │   └── day=02/
│   │       └── data.parquet
```

**Integration Points:**
- Used by `PolarsDataPortal` for minute-resolution backtests
- Supports multi-resolution aggregation (minute → daily)
- Queried by live trading engine for recent bar data

### PolarsDataPortal
**Purpose:** Unified data access layer with Polars backend
**Location:** `rustybt/data/polars/data_portal.py`
**Zipline Integration:** Extends `zipline.data.data_portal.DataPortal`

**Key Responsibilities:**
- Provide unified interface to daily/minute readers
- Return Polars DataFrames with Decimal columns
- Support current() and history() methods from Zipline API
- Handle currency conversion for multi-currency portfolios

**API Compatibility:**
```python
class PolarsDataPortal(DataPortal):
    def get_spot_value(
        self, assets: List[Asset], field: str, dt: pd.Timestamp, data_frequency: str
    ) -> pl.Series:
        """Get current field values as Polars Series (Decimal dtype)."""

    def get_history_window(
        self, assets: List[Asset], end_dt: pd.Timestamp, bar_count: int,
        frequency: str, field: str, data_frequency: str
    ) -> pl.DataFrame:
        """Get historical window as Polars DataFrame (Decimal columns)."""
```

**Integration Points:**
- Created by `TradingAlgorithm` during initialization
- Accessed via `data.current()`, `data.history()` in user strategies
- Used by Pipeline engine for factor computation

## Live Trading Components

### LiveTradingEngine
**Purpose:** Orchestrate live trading execution with broker integration
**Location:** `rustybt/live/engine.py`
**Zipline Integration:** New component (no Zipline equivalent)

**Key Responsibilities:**
- Initialize broker connections via adapter pattern
- Maintain real-time portfolio state with broker reconciliation
- Execute scheduled calculations (market open/close, custom triggers)
- Handle order lifecycle (submit → fill/cancel/reject)
- Checkpoint strategy state for crash recovery
- Coordinate between user strategy and broker adapter

**Architecture:**
```python
class LiveTradingEngine:
    def __init__(
        self,
        strategy: TradingAlgorithm,
        broker_adapter: BrokerAdapter,
        data_portal: PolarsDataPortal,
        scheduler: APScheduler
    ):
        self.strategy = strategy
        self.broker = broker_adapter
        self.data_portal = data_portal
        self.scheduler = scheduler
        self.position_reconciler = PositionReconciler(broker_adapter)
        self.state_manager = StateManager()

    async def run(self):
        """Main live trading loop."""
        # Load saved state if exists
        self.state_manager.load_checkpoint(self.strategy.name)

        # Schedule strategy callbacks
        self.scheduler.add_job(
            self.on_market_open, trigger='cron', hour=9, minute=30
        )
        self.scheduler.add_job(
            self.on_market_close, trigger='cron', hour=16, minute=0
        )

        # Start real-time data feed
        await self.broker.subscribe_market_data(self.strategy.assets)

        # Event loop
        while True:
            event = await self.broker.get_next_event()
            await self.process_event(event)
```

**Integration Points:**
- Instantiated by user script for live trading
- Uses `BrokerAdapter` for broker communication
- Calls `TradingAlgorithm` lifecycle methods
- Writes to `strategy_state` and `order_audit_log` tables

### BrokerAdapter (Abstract Base)
**Purpose:** Standardized interface for broker integrations
**Location:** `rustybt/live/brokers/base.py`
**Zipline Integration:** New component (no Zipline equivalent)

**Interface:**
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from decimal import Decimal

class BrokerAdapter(ABC):
    """Abstract base class for broker integrations."""

    @abstractmethod
    async def connect(self, credentials: Dict[str, str]) -> bool:
        """Establish connection to broker API."""

    @abstractmethod
    async def submit_order(
        self, asset: Asset, amount: Decimal, order_type: str,
        limit_price: Optional[Decimal] = None
    ) -> str:
        """Submit order to broker, return broker_order_id."""

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel pending order."""

    @abstractmethod
    async def get_positions(self) -> List[Dict]:
        """Fetch current positions from broker."""

    @abstractmethod
    async def get_account_info(self) -> Dict[str, Decimal]:
        """Fetch account balance, buying power, margin info."""

    @abstractmethod
    async def subscribe_market_data(self, assets: List[Asset]):
        """Subscribe to real-time market data stream."""

    @abstractmethod
    async def get_next_event(self) -> Dict:
        """Get next event (fill, cancel, price update) from broker."""
```

**Implementations:**
- `CCXTAdapter`: Generic crypto exchange adapter (100+ exchanges)
- `IBAdapter`: Interactive Brokers (stocks, futures, options, forex)
- `BinanceAdapter`: Binance-specific (uses binance-connector)
- `BybitAdapter`: Bybit-specific (uses pybit)
- `HyperliquidAdapter`: Hyperliquid DEX (uses hyperliquid-python-sdk)

**Error Handling:**
- Retry logic with exponential backoff for transient errors
- Rate limiting per broker API specifications
- Disconnect/reconnect handling with state preservation

### CCXTAdapter
**Purpose:** Unified crypto exchange integration via CCXT
**Location:** `rustybt/live/brokers/ccxt_adapter.py`
**Zipline Integration:** New component

**Key Features:**
- Support 100+ exchanges via CCXT unified API
- Configurable exchange selection (Binance, Coinbase, Kraken, etc.)
- WebSocket support for real-time data (where available)
- Automatic rate limiting per exchange metadata
- Order type mapping (Market, Limit, Stop, Stop-Limit)

**Implementation:**
```python
import ccxt
from typing import Dict, Decimal

class CCXTAdapter(BrokerAdapter):
    def __init__(self, exchange_id: str, testnet: bool = False):
        self.exchange_id = exchange_id
        self.testnet = testnet
        self.exchange: Optional[ccxt.Exchange] = None

    async def connect(self, credentials: Dict[str, str]) -> bool:
        exchange_class = getattr(ccxt, self.exchange_id)
        self.exchange = exchange_class({
            'apiKey': credentials['api_key'],
            'secret': credentials['api_secret'],
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}  # or 'future'
        })

        if self.testnet:
            self.exchange.set_sandbox_mode(True)

        # Test connection
        await self.exchange.fetch_balance()
        return True

    async def submit_order(
        self, asset: Cryptocurrency, amount: Decimal, order_type: str,
        limit_price: Optional[Decimal] = None
    ) -> str:
        symbol = f"{asset.base_currency}/{asset.quote_currency}"

        order = await self.exchange.create_order(
            symbol=symbol,
            type=order_type.lower(),  # 'market', 'limit'
            side='buy' if amount > 0 else 'sell',
            amount=str(abs(amount)),
            price=str(limit_price) if limit_price else None
        )

        return order['id']
```

**Integration Points:**
- Registered with `LiveTradingEngine`
- Used by crypto-focused strategies
- Supports both spot and futures markets

### IBAdapter
**Purpose:** Interactive Brokers integration for stocks/futures/options
**Location:** `rustybt/live/brokers/ib_adapter.py`
**Zipline Integration:** New component

**Key Features:**
- Uses ib_async for Pythonic async interface
- Support stocks, futures, options, forex
- Real-time market data via IB streaming
- Order types: Market, Limit, Stop, Stop-Limit, Trailing Stop, Bracket
- TWS/Gateway connection with automatic reconnection

**Implementation:**
```python
from ib_async import IB, Stock, Future, Order, util
from typing import Decimal

class IBAdapter(BrokerAdapter):
    def __init__(self, host: str = '127.0.0.1', port: int = 7497):
        self.ib = IB()
        self.host = host
        self.port = port

    async def connect(self, credentials: Dict[str, str]) -> bool:
        await self.ib.connectAsync(self.host, self.port, clientId=1)

        # Subscribe to events
        self.ib.orderStatusEvent += self.on_order_status
        self.ib.execDetailsEvent += self.on_execution

        return self.ib.isConnected()

    async def submit_order(
        self, asset: Asset, amount: Decimal, order_type: str,
        limit_price: Optional[Decimal] = None
    ) -> str:
        # Create IB contract
        if isinstance(asset, Equity):
            contract = Stock(asset.symbol, asset.exchange, 'USD')
        elif isinstance(asset, Future):
            contract = Future(asset.symbol, asset.exchange)

        # Create IB order
        order = Order()
        order.action = 'BUY' if amount > 0 else 'SELL'
        order.totalQuantity = abs(float(amount))
        order.orderType = order_type.upper()

        if limit_price:
            order.lmtPrice = float(limit_price)

        trade = self.ib.placeOrder(contract, order)
        return str(trade.order.orderId)
```

**Integration Points:**
- Requires TWS or IB Gateway running locally
- Used for traditional asset classes (stocks, futures, options)
- Supports paper trading mode via paper trading account

## Data Adapter Components

### BaseDataAdapter
**Purpose:** Extensible framework for data source integrations
**Location:** `rustybt/data/adapters/base.py`
**Zipline Integration:** New component

**Interface:**
```python
from abc import ABC, abstractmethod
import polars as pl
from typing import List

class BaseDataAdapter(ABC):
    """Base class for data source adapters."""

    @abstractmethod
    async def fetch(
        self, symbols: List[str], start_date: pd.Timestamp,
        end_date: pd.Timestamp, resolution: str
    ) -> pl.DataFrame:
        """Fetch OHLCV data and return Polars DataFrame with Decimal columns."""

    @abstractmethod
    def validate(self, df: pl.DataFrame) -> bool:
        """Validate OHLCV relationships and data quality."""

    @abstractmethod
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider-specific format to RustyBT standard schema."""
```

**Standard Schema:**
```python
{
    "timestamp": pl.Datetime("us"),       # Microsecond precision
    "symbol": pl.Utf8,
    "open": pl.Decimal(18, 8),
    "high": pl.Decimal(18, 8),
    "low": pl.Decimal(18, 8),
    "close": pl.Decimal(18, 8),
    "volume": pl.Decimal(18, 8),
}
```

**Validation Logic:**
- OHLCV relationships: `high >= max(open, close)`, `low <= min(open, close)`
- Outlier detection: flag price changes >3 standard deviations
- Temporal consistency: timestamps sorted, no duplicates
- Completeness: no NULL values in required fields

### CCXTDataAdapter
**Purpose:** Fetch crypto OHLCV data via CCXT
**Location:** `rustybt/data/adapters/ccxt_adapter.py`
**Zipline Integration:** New component

**Features:**
- Support 100+ exchanges for historical data
- Resolutions: 1m, 5m, 15m, 1h, 4h, 1d, 1w
- Rate limiting per exchange
- Retry logic for transient failures

**Integration Points:**
- Used by `DataCatalog` to ingest crypto data
- Cached locally in Parquet format
- Queried during backtest initialization

### YFinanceAdapter
**Purpose:** Fetch stock/ETF/forex data via yfinance
**Location:** `rustybt/data/adapters/yfinance_adapter.py`
**Zipline Integration:** New component

**Features:**
- Free data for stocks, ETFs, forex, indices
- Resolutions: 1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo
- Dividend and split data included
- Adjusted and unadjusted prices

**Integration Points:**
- Used by `DataCatalog` for equity backtests
- Cached with checksum validation
- Supports both live and historical data

### CSVAdapter
**Purpose:** Import custom data from CSV files
**Location:** `rustybt/data/adapters/csv_adapter.py`
**Zipline Integration:** Extends Zipline's `csvdir` bundle concept

**Features:**
- Flexible schema mapping (configure column names)
- Multiple date formats (ISO8601, MM/DD/YYYY, epoch)
- Delimiter detection (comma, tab, semicolon, pipe)
- Missing data handling (skip, interpolate, fail)

**Configuration:**
```yaml
csv_adapter:
  file_path: "/data/custom_data.csv"
  schema_mapping:
    date_column: "Date"
    open_column: "Open"
    high_column: "High"
    low_column: "Low"
    close_column: "Close"
    volume_column: "Volume"
  date_format: "%Y-%m-%d"
  delimiter: ","
  timezone: "UTC"
```

**Integration Points:**
- Used for proprietary data sources
- Converts to Parquet for consistent storage
- Validates against standard schema

---
