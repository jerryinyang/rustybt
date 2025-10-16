# Data Models and Schema Changes

## New Database Tables (Extend Zipline Asset DB)

### broker_connections
Stores broker API credentials and connection configurations for live trading.

```sql
CREATE TABLE broker_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_name TEXT NOT NULL,              -- 'binance', 'interactive_brokers', etc.
    connection_type TEXT NOT NULL,          -- 'live', 'paper', 'testnet'
    api_key_encrypted BLOB NOT NULL,        -- Encrypted API key
    api_secret_encrypted BLOB,              -- Encrypted API secret (if applicable)
    additional_credentials TEXT,            -- JSON for extra fields (account_id, passphrase, etc.)
    base_url TEXT,                          -- Custom API endpoint if needed
    is_active BOOLEAN DEFAULT 1,
    created_at INTEGER NOT NULL,            -- Unix timestamp
    updated_at INTEGER NOT NULL,
    last_connected_at INTEGER,
    UNIQUE(broker_name, connection_type)
);
```

**Integration:** Referenced by `LiveTradingEngine` for broker authentication.

### live_positions
Real-time position tracking with broker reconciliation for live trading mode.

```sql
CREATE TABLE live_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,              -- Strategy identifier
    broker_connection_id INTEGER NOT NULL,  -- FK to broker_connections
    asset_sid INTEGER NOT NULL,             -- FK to equities/futures_contracts
    amount TEXT NOT NULL,                   -- Decimal as TEXT (e.g., "1.23456789")
    cost_basis TEXT NOT NULL,               -- Decimal as TEXT
    last_sale_price TEXT NOT NULL,          -- Decimal as TEXT
    last_sale_date INTEGER NOT NULL,        -- Unix timestamp
    broker_reported_amount TEXT,            -- Decimal from broker reconciliation
    broker_reported_price TEXT,             -- Decimal from broker reconciliation
    reconciliation_status TEXT,             -- 'matched', 'mismatch', 'pending'
    last_reconciled_at INTEGER,             -- Unix timestamp
    updated_at INTEGER NOT NULL,
    FOREIGN KEY(broker_connection_id) REFERENCES broker_connections(id),
    FOREIGN KEY(asset_sid) REFERENCES asset_router(sid)
);

CREATE INDEX idx_live_positions_strategy ON live_positions(strategy_id);
CREATE INDEX idx_live_positions_asset ON live_positions(asset_sid);
```

**Integration:** Extends Zipline's `Position` class with broker reconciliation fields. Queried by `LiveTradingEngine` for position synchronization.

### order_audit_log
Comprehensive trade-by-trade audit trail in JSON format for regulatory compliance.

```sql
CREATE TABLE order_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    broker_connection_id INTEGER,
    order_id TEXT NOT NULL,                 -- Internal order ID
    broker_order_id TEXT,                   -- Broker's order ID
    asset_sid INTEGER NOT NULL,
    event_type TEXT NOT NULL,               -- 'submitted', 'filled', 'partially_filled', 'canceled', 'rejected'
    event_timestamp INTEGER NOT NULL,       -- Unix timestamp (microsecond precision)
    event_data TEXT NOT NULL,               -- JSON: full order state snapshot
    FOREIGN KEY(broker_connection_id) REFERENCES broker_connections(id),
    FOREIGN KEY(asset_sid) REFERENCES asset_router(sid)
);

CREATE INDEX idx_audit_log_order ON order_audit_log(order_id);
CREATE INDEX idx_audit_log_timestamp ON order_audit_log(event_timestamp);
CREATE INDEX idx_audit_log_strategy ON order_audit_log(strategy_id);
```

**Event Data JSON Schema:**
```json
{
  "order_type": "limit",
  "side": "buy",
  "amount": "100.50",
  "price": "42.125",
  "fill_price": "42.130",
  "filled_amount": "100.50",
  "commission": "0.105",
  "slippage": "0.005",
  "reason": "filled_by_broker",
  "latency_ms": 125
}
```

**Integration:** Written by `LiveBlotter` and `SimulationBlotter` (in audit mode). Queryable via RESTful API for compliance reporting.

### strategy_state
Checkpoint storage for crash recovery in live trading.

```sql
CREATE TABLE strategy_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL UNIQUE,
    state_data TEXT NOT NULL,               -- JSON: serialized strategy state
    checkpoint_timestamp INTEGER NOT NULL,  -- Unix timestamp
    portfolio_value TEXT NOT NULL,          -- Decimal as TEXT
    cash TEXT NOT NULL,                     -- Decimal as TEXT
    positions_snapshot TEXT NOT NULL,       -- JSON: list of positions
    pending_orders_snapshot TEXT NOT NULL,  -- JSON: list of pending orders
    custom_state TEXT                       -- JSON: user-defined state from strategy
);

CREATE INDEX idx_strategy_state_timestamp ON strategy_state(checkpoint_timestamp DESC);
```

**State Data JSON Schema:**
```json
{
  "algorithm_state": {
    "portfolio_value": "1000000.00",
    "cash": "250000.00",
    "leverage": "1.5"
  },
  "positions": [
    {"asset_sid": 24, "amount": "100.0", "cost_basis": "42.00"}
  ],
  "pending_orders": [
    {"order_id": "abc123", "asset_sid": 24, "amount": "50.0", "limit_price": "43.00"}
  ],
  "custom_state": {
    "moving_average_50": "42.35",
    "signal_strength": "0.85"
  }
}
```

**Integration:** Saved by `LiveTradingEngine` at configurable intervals (default: every trade + every 5 minutes). Loaded on strategy restart.

## Decimal Finance Models (Replaces float64)

### DecimalLedger
Extends Zipline's `Ledger` class with Decimal arithmetic.

**Key Fields:**
```python
from decimal import Decimal
from dataclasses import dataclass
from typing import Dict

@dataclass
class DecimalLedger:
    """Maintains portfolio accounting with Decimal precision."""

    portfolio_value: Decimal          # Total portfolio value
    positions_value: Decimal          # Sum of all position values
    cash: Decimal                     # Available cash
    starting_cash: Decimal            # Initial capital
    leverage: Decimal                 # Current leverage ratio
    pnl: Decimal                      # Unrealized P&L
    returns: Decimal                  # Period returns

    # Transaction costs (tracked separately)
    cumulative_commission: Decimal
    cumulative_slippage: Decimal
    cumulative_borrow_cost: Decimal
    cumulative_financing_cost: Decimal
```

**Integration:** Replaces Zipline's `finance/ledger.py::Ledger` class. All calculations use Decimal context with configurable precision.

### DecimalPosition
Extends Zipline's `Position` class with Decimal types.

```python
@dataclass
class DecimalPosition:
    """Position tracking with Decimal precision."""

    asset: Asset                      # Asset reference (unchanged)
    amount: Decimal                   # Number of shares/contracts
    cost_basis: Decimal               # Average price paid
    last_sale_price: Decimal          # Current market price
    last_sale_date: pd.Timestamp      # Timestamp of last price update

    @property
    def market_value(self) -> Decimal:
        """Calculate position market value."""
        return self.amount * self.last_sale_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized profit/loss."""
        return (self.last_sale_price - self.cost_basis) * self.amount
```

**Integration:** Replaces Zipline's `finance/position.py::Position`. Used by `DecimalLedger` and `PositionTracker`.

### DecimalTransaction
Extends Zipline's `Transaction` class with Decimal precision.

```python
@dataclass
class DecimalTransaction:
    """Transaction record with Decimal precision."""

    asset: Asset
    amount: Decimal                   # Signed quantity (positive = buy, negative = sell)
    dt: pd.Timestamp
    price: Decimal                    # Execution price
    order_id: str
    commission: Decimal               # Commission paid
    slippage: Decimal                 # Slippage cost

    @property
    def transaction_value(self) -> Decimal:
        """Total transaction value including costs."""
        base_value = abs(self.amount) * self.price
        return base_value + self.commission + self.slippage
```

**Integration:** Replaces Zipline's `finance/transaction.py::Transaction`. Created by `Blotter` on order fills.

## Polars Data Layer Models

### PolarsBarReader
Replaces Zipline's `BcolzDailyBarReader` and `BcolzMinuteBarReader` with Polars-based readers.

**Interface:**
```python
from abc import ABC, abstractmethod
import polars as pl
from typing import List, Optional

class PolarsBarReader(ABC):
    """Base class for Polars-based bar readers."""

    @abstractmethod
    def load_raw_arrays(
        self,
        sids: List[int],
        fields: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp
    ) -> Dict[str, pl.DataFrame]:
        """Load OHLCV data as Polars DataFrames with Decimal columns."""
        pass

    @abstractmethod
    def get_last_traded_dt(self, asset: Asset, dt: pd.Timestamp) -> Optional[pd.Timestamp]:
        """Get last traded datetime for asset before dt."""
        pass
```

**Implementation:**
- `PolarsParquetDailyReader`: Reads daily bars from Parquet files
- `PolarsParquetMinuteReader`: Reads minute bars from Parquet files with partition pruning
- Lazy loading via Polars `scan_parquet()` for efficient memory usage
- Decimal columns for OHLCV data: `Decimal128(18, 8)` dtype

**Integration:** Drop-in replacement for Zipline's `BcolzDailyBarReader` and `BcolzMinuteBarReader`. Used by `DataPortal`.

### PolarsDataPortal
Extends Zipline's `DataPortal` to work with Polars readers.

**Key Changes:**
- Returns Polars DataFrames instead of pandas DataFrames (with fallback conversion)
- Decimal columns preserved throughout data pipeline
- Supports zero-copy Arrow interchange with data adapters

**Integration:** Replaces Zipline's `data/data_portal.py::DataPortal`. Feature flag: `RUSTYBT_USE_POLARS`.

## Asset Model Extensions

### Cryptocurrency Asset Type
Extends Zipline's Asset types to support crypto.

```python
@dataclass
class Cryptocurrency(Asset):
    """Cryptocurrency asset metadata."""

    base_currency: str                # 'BTC', 'ETH', etc.
    quote_currency: str               # 'USD', 'USDT', etc.
    exchange: str                     # 'binance', 'coinbase', etc.
    tick_size: Decimal                # Minimum price increment
    lot_size: Decimal                 # Minimum order size
    precision_price: int              # Decimal places for price
    precision_amount: int             # Decimal places for amount
    trading_enabled: bool
    margin_enabled: bool
```

**Database Schema Addition:**
```sql
CREATE TABLE cryptocurrencies (
    sid INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,               -- 'BTC/USDT'
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    exchange TEXT NOT NULL,
    tick_size TEXT NOT NULL,            -- Decimal as TEXT
    lot_size TEXT NOT NULL,             -- Decimal as TEXT
    precision_price INTEGER,
    precision_amount INTEGER,
    trading_enabled BOOLEAN DEFAULT 1,
    margin_enabled BOOLEAN DEFAULT 0,
    start_date INTEGER,
    end_date INTEGER,
    FOREIGN KEY(sid) REFERENCES asset_router(sid)
);
```

**Integration:** Registered with `AssetFinder`. Used by broker adapters for order validation.

---
