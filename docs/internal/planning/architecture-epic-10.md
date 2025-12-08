# Epic 10 Architecture - Live Trading Production Readiness & Lighter.xyz Integration

## Executive Summary

This architecture document defines the technical approach for **Epic 10: Live Trading Production Readiness & Lighter.xyz Integration** - a production hardening and platform expansion epic for rustybt's live trading infrastructure.

**Architecture Approach:** Brownfield extension of existing rustybt live trading infrastructure. All new components follow established patterns:
- **Lighter.xyz Broker Adapter** follows `HyperliquidBrokerAdapter` pattern
- **Lighter.xyz Data Adapter** follows `BaseDataAdapter` pattern
- **Lighter.xyz Streaming Adapter** follows `BaseWebSocketAdapter` pattern
- **Audit/Testing Infrastructure** follows existing pytest patterns

**Key Principles:**
- **Pattern Consistency:** All new adapters implement existing abstract interfaces exactly
- **Zero Credential Exposure:** Private keys loaded from environment variables or encrypted keystores
- **Resilient Connections:** Exponential backoff reconnection, circuit breakers, rate limiting
- **Testnet First:** All live trading validated on testnet before mainnet deployment

## Decision Summary

| Category | Decision | Version | Affects FRs | Rationale |
| -------- | -------- | ------- | ----------- | --------- |
| Lighter.xyz SDK | `lighter-sdk` Python package | Latest | FR30-FR57 | Official Lighter.xyz Python SDK for API integration |
| Broker Adapter Pattern | Extend `BrokerAdapter` ABC | N/A | FR30-FR40 | Consistency with existing Hyperliquid, Binance, Bybit adapters |
| Data Adapter Pattern | Extend `BaseDataAdapter` ABC | N/A | FR41-FR50 | Consistency with existing yfinance, Polygon, CCXT adapters |
| Streaming Pattern | Extend `BaseWebSocketAdapter` ABC | N/A | FR51-FR57 | Consistency with existing streaming infrastructure |
| Audit Infrastructure | pytest + structured YAML findings | pytest >=7.2.0, PyYAML >=6.0 | FR1-FR5 | Leverages existing test framework, machine-readable findings |
| Stress Testing | pytest-asyncio + custom fixtures | pytest-asyncio >=0.21 | FR22-FR29 | Async stress test execution with configurable scenarios |
| Private Key Management | Environment variables + Fernet encryption | cryptography >=41.0 | FR30, NFR13-17 | Matches HyperliquidBrokerAdapter security pattern |
| Testnet Configuration | YAML config with testnet/mainnet switch | N/A | FR39, NFR15 | Clear separation to prevent accidental mainnet trades |
| Logging | structlog with JSON formatting | structlog >=24.0 | NFR10, NFR24 | Structured logging for audit trails and debugging |
| Rate Limiting | Token bucket algorithm | N/A | FR18, NFR18 | Matches existing rate limiting patterns in adapters |

## Project Structure

```
rustybt/
├── rustybt/
│   ├── live/
│   │   ├── brokers/
│   │   │   ├── base.py                      # BrokerAdapter ABC (existing)
│   │   │   ├── lighter_adapter.py           # NEW: LighterBrokerAdapter
│   │   │   ├── hyperliquid_adapter.py       # Reference pattern
│   │   │   └── ...
│   │   ├── streaming/
│   │   │   ├── base.py                      # BaseWebSocketAdapter (existing)
│   │   │   ├── lighter_stream.py            # NEW: LighterWebSocketAdapter
│   │   │   └── ...
│   │   ├── engine.py                        # Live trading engine (audit target)
│   │   ├── order_manager.py                 # Order lifecycle (audit target)
│   │   ├── state_manager.py                 # State persistence (audit target)
│   │   ├── reconciler.py                    # Position reconciliation (audit target)
│   │   └── circuit_breakers.py              # Safety mechanisms (audit target)
│   └── data/
│       └── adapters/
│           ├── base.py                      # BaseDataAdapter ABC (existing)
│           ├── lighter_adapter.py           # NEW: LighterDataAdapter
│           └── ...
├── tests/
│   ├── live/
│   │   ├── audit/                           # NEW: Code audit infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py                  # Audit fixtures
│   │   │   ├── test_engine_audit.py         # Engine audit tests
│   │   │   ├── test_brokers_audit.py        # Broker adapters audit
│   │   │   ├── test_streaming_audit.py      # Streaming audit
│   │   │   └── findings/                    # Audit findings storage
│   │   │       └── {module}_findings.yaml
│   │   ├── stress/                          # NEW: Stress testing infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py                  # Stress test fixtures
│   │   │   ├── test_network_resilience.py   # Disconnect/reconnect tests
│   │   │   ├── test_order_throughput.py     # High-frequency order tests
│   │   │   ├── test_long_running.py         # 24-48 hour stability tests
│   │   │   └── scenarios/                   # Configurable stress scenarios
│   │   │       └── {scenario}.yaml
│   │   ├── paper/                           # NEW: Paper trading validation
│   │   │   ├── test_paper_execution.py      # Paper trading tests
│   │   │   └── test_paper_parity.py         # Paper vs live parity
│   │   ├── testnet/                         # NEW: Testnet integration tests
│   │   │   ├── test_binance_testnet.py
│   │   │   ├── test_bybit_testnet.py
│   │   │   ├── test_hyperliquid_testnet.py
│   │   │   └── test_lighter_testnet.py
│   │   └── lighter/                         # NEW: Lighter.xyz adapter tests
│   │       ├── test_lighter_broker.py
│   │       ├── test_lighter_data.py
│   │       └── test_lighter_stream.py
│   └── ...
├── docs/
│   ├── architecture-epic-10.md              # This document
│   ├── prd-epic-10.md                       # Epic 10 PRD
│   └── live-trading/                        # NEW: Live trading documentation
│       ├── setup-guide.md                   # Platform setup guides
│       ├── lighter-integration.md           # Lighter.xyz specific docs
│       ├── testnet-guide.md                 # Testnet setup instructions
│       └── audit-report.md                  # Audit findings summary
└── pyproject.toml                           # Updated dependencies
```

## FR Category to Architecture Mapping

| FR Category | Primary Modules | Test Modules |
| ----------- | --------------- | ------------ |
| Code Audit & Issue Management (FR1-FR5) | N/A (audit process) | `tests/live/audit/` |
| Paper Trading Validation (FR6-FR13) | `rustybt/live/brokers/paper_broker.py` | `tests/live/paper/` |
| Live Trading Validation (FR14-FR21) | All `rustybt/live/` modules | `tests/live/testnet/` |
| Stress Testing (FR22-FR29) | N/A (stress infrastructure) | `tests/live/stress/` |
| Lighter.xyz Broker (FR30-FR40) | `rustybt/live/brokers/lighter_adapter.py` | `tests/live/lighter/` |
| Lighter.xyz Data (FR41-FR50) | `rustybt/data/adapters/lighter_adapter.py` | `tests/live/lighter/` |
| Lighter.xyz Streaming (FR51-FR57) | `rustybt/live/streaming/lighter_stream.py` | `tests/live/lighter/` |
| Documentation (FR58-FR63) | N/A | `docs/live-trading/` |

## Technology Stack Details

### Core Technologies (Inherited from rustybt)

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.12+ | Required by rustybt constitution |
| Async Runtime | asyncio | Built-in | Async broker/streaming operations |
| Data Processing | Polars | >=1.0 | OHLCV data processing |
| Precision | Decimal | Built-in | Financial calculations |
| Testing | pytest | >=7.2.0 | Test framework |
| Async Testing | pytest-asyncio | >=0.21 | Async test support |
| Logging | structlog | >=24.0 | Structured logging |
| Linting | Ruff | >=0.11.12 | Code quality |
| Type Checking | mypy | >=1.10.0 | Static analysis |

### New Dependencies for Epic 10

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Lighter.xyz SDK | lighter-sdk | Latest | Lighter.xyz API integration |
| Encryption | cryptography | >=41.0 | Private key encryption (Fernet) |
| WebSocket | websockets | >=12.0 | WebSocket connections (existing) |
| Configuration | PyYAML | >=6.0 | Audit findings, stress scenarios |
| HTTP Client | httpx | >=0.25 | REST API calls to Lighter.xyz |

### Integration Points

**With Existing rustybt Infrastructure:**
- Implements `BrokerAdapter` ABC from `rustybt/live/brokers/base.py`
- Implements `BaseDataAdapter` ABC from `rustybt/data/adapters/base.py`
- Extends `BaseWebSocketAdapter` from `rustybt/live/streaming/base.py`
- Uses `DecimalOrder`, `DecimalPosition`, `DecimalTransaction` from `rustybt/finance/decimal/`
- Integrates with existing `LiveTradingEngine` for strategy execution

**External Integrations:**
- **Lighter.xyz API:** REST endpoints for trading, positions, orders
- **Lighter.xyz WebSocket:** Real-time market data streaming
- **Exchange Testnets:** Binance, Bybit, Hyperliquid testnets for validation

## Novel Pattern: Lighter.xyz DeFi Adapter Architecture

### Pattern Name
**zk-Rollup DEX Broker Adapter**

### Purpose
Enable rustybt to trade on Lighter.xyz, a zk-rollup based decentralized exchange, while maintaining consistency with existing broker adapter patterns.

### Problem Solved
Lighter.xyz uses zk-proof verified transactions on L2, requiring different transaction flow than CEX adapters (Binance, Bybit) or L1 DeFi (Hyperliquid). The adapter must handle:
- Transaction signing with private keys
- L2 transaction submission via `/sendTx`
- zk-proof verification delays
- Different order status tracking flow

### Components

**1. LighterBrokerAdapter**

```python
class LighterBrokerAdapter(BrokerAdapter):
    """Lighter.xyz broker adapter for perpetual futures trading.

    Implements BrokerAdapter interface for Lighter DEX integration.
    Uses lighter-sdk for API communication and transaction signing.

    Key Differences from CEX Adapters:
    - Transactions signed with Ethereum private key
    - Orders submitted via /sendTx (transaction-based)
    - Positions tracked via /account endpoint
    - zk-proof verification may delay order confirmation
    """

    # API endpoints
    MAINNET_API_URL = "https://mainnet.zklighter.elliot.ai/"
    TESTNET_API_URL = "https://testnet.zklighter.elliot.ai/"

    def __init__(
        self,
        private_key: str | None = None,
        encrypted_key_path: str | None = None,
        encryption_key: str | None = None,
        testnet: bool = True,  # Default to testnet for safety
    ) -> None:
        """Initialize Lighter adapter with secure key management."""

    async def connect(self) -> None:
        """Authenticate and establish connection."""

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str:
        """Submit order via /sendTx endpoint."""

    async def get_positions(self) -> list[dict]:
        """Get positions via /account endpoint."""

    async def get_open_orders(self) -> list[dict]:
        """Get open orders via /accountActiveOrders."""
```

**2. LighterDataAdapter**

```python
class LighterDataAdapter(BaseDataAdapter):
    """Lighter.xyz data adapter for OHLCV data ingestion.

    Fetches candlestick data from Lighter.xyz /candlesticks endpoint.
    Supports multiple timeframes and historical data retrieval.
    """

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from Lighter.xyz."""

    async def get_available_assets(self) -> list[dict]:
        """List all tradeable pairs from Lighter.xyz."""

    async def get_funding_rates(self, symbol: str) -> pl.DataFrame:
        """Fetch funding rate history."""
```

**3. LighterWebSocketAdapter**

```python
class LighterWebSocketAdapter(BaseWebSocketAdapter):
    """Lighter.xyz WebSocket adapter for real-time streaming.

    Implements BaseWebSocketAdapter for Lighter.xyz data streams.
    Supports trades, orderbook, and candlestick subscriptions.
    """

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to Lighter.xyz WebSocket channels."""

    def parse_message(self, raw_message: dict) -> TickData | None:
        """Parse Lighter.xyz WebSocket message to TickData."""
```

### Data Flow

```
1. Order Submission
   Strategy Signal → LighterBrokerAdapter.submit_order()
                  → Sign transaction with private key
                  → POST /sendTx
                  → Parse response for order ID
                  → Return order ID to OrderManager

2. Position Tracking
   OrderManager.reconcile() → LighterBrokerAdapter.get_positions()
                           → GET /account
                           → Parse position data
                           → Update local position state

3. Market Data Streaming
   LiveTradingEngine.start() → LighterWebSocketAdapter.connect()
                            → Subscribe to trades channel
                            → parse_message() → TickData
                            → BarBuffer aggregation
                            → Engine receives OHLCV bars
```

### Affects FRs
FR30-FR57 (all Lighter.xyz integration requirements)

## Implementation Patterns

### Pattern 1: Private Key Security (Following HyperliquidBrokerAdapter)

**Convention:** Private keys loaded via priority order:
1. Environment variable: `LIGHTER_PRIVATE_KEY`
2. Encrypted keystore file + encryption key
3. Direct parameter (NOT RECOMMENDED, logs warning)

```python
def _load_private_key(
    self,
    private_key: str | None,
    encrypted_key_path: str | None,
    encryption_key: str | None,
) -> str:
    # Method 1: Environment variable (RECOMMENDED)
    env_key = os.environ.get("LIGHTER_PRIVATE_KEY")
    if env_key:
        logger.info("private_key_loaded_from_environment")
        return self._validate_private_key(env_key)

    # Method 2: Encrypted keystore (RECOMMENDED)
    if encrypted_key_path and encryption_key:
        return self._load_encrypted_key(encrypted_key_path, encryption_key)

    # Method 3: Direct parameter (NOT RECOMMENDED)
    if private_key:
        logger.warning("private_key_loaded_from_parameter")
        return self._validate_private_key(private_key)

    raise LighterKeyError("No private key provided")
```

**Enforcement:** Code review, never log private keys, mask addresses in logs

### Pattern 2: Rate Limiting (Token Bucket)

**Convention:** All API calls go through rate limiter before execution

```python
class LighterBrokerAdapter(BrokerAdapter):
    REQUESTS_PER_MINUTE = 600
    ORDERS_PER_SECOND = 20

    async def submit_order(self, ...):
        await self._check_request_rate_limit()
        await self._check_order_rate_limit(asset.symbol)
        # ... order submission
```

**Enforcement:** Rate limiter check before every API call, log warnings at 80% capacity

### Pattern 3: Reconnection with Exponential Backoff

**Convention:** WebSocket reconnection uses exponential backoff with jitter

```python
async def reconnect(self) -> None:
    delay = min(
        self.config.reconnect_delay * (2 ** (self._reconnect_count - 1)),
        self.config.reconnect_max_delay,
    )
    await asyncio.sleep(delay)
    await self.connect()
    # Re-subscribe to all symbols
    for symbol, channels in self._subscriptions.items():
        await self.subscribe([symbol], list(channels))
```

**Enforcement:** Circuit breaker trips after consecutive errors threshold

### Pattern 4: Testnet/Mainnet Configuration

**Convention:** Clear separation via configuration, default to testnet

```yaml
# config/lighter.yaml
lighter:
  testnet: true  # Default to testnet for safety
  mainnet_api_url: "https://mainnet.zklighter.elliot.ai/"
  testnet_api_url: "https://testnet.zklighter.elliot.ai/"

  # Credentials (environment variables)
  api_key_env: "LIGHTER_API_KEY"
  private_key_env: "LIGHTER_PRIVATE_KEY"
```

**Enforcement:** Environment variable names differ for testnet/mainnet, log warnings on mainnet use

### Pattern 5: Audit Finding Classification

**Convention:** All audit findings stored in structured YAML with severity classification

```yaml
# tests/live/audit/findings/engine_findings.yaml
findings:
  - id: AUDIT-E001
    module: rustybt/live/engine.py
    line: 234
    severity: HIGH  # CRITICAL, HIGH, MEDIUM, LOW
    category: error_handling
    description: "Uncaught exception in main loop can crash engine"
    recommendation: "Wrap main loop in try/except with graceful shutdown"
    status: OPEN  # OPEN, IN_PROGRESS, RESOLVED, VERIFIED
    found_by: "code_audit"
    found_at: "2025-12-05"
    resolved_at: null
    regression_test: null
```

**Enforcement:** All CRITICAL/HIGH findings must have regression tests before closing

## Consistency Rules

### Naming Conventions

**Adapter Classes:**
- Broker adapters: `{Exchange}BrokerAdapter` (e.g., `LighterBrokerAdapter`)
- Data adapters: `{Exchange}DataAdapter` (e.g., `LighterDataAdapter`)
- Streaming adapters: `{Exchange}WebSocketAdapter` (e.g., `LighterWebSocketAdapter`)

**Exception Classes:**
- `{Exchange}ConnectionError` - Connection failures
- `{Exchange}OrderRejectError` - Order rejections
- `{Exchange}RateLimitError` - Rate limit exceeded
- `{Exchange}KeyError` - Private key issues

**Test Files:**
- Audit tests: `test_{module}_audit.py`
- Stress tests: `test_{scenario}.py`
- Integration tests: `test_{exchange}_testnet.py`

**Findings:**
- IDs: `AUDIT-{MODULE_CODE}{NUMBER}` (e.g., `AUDIT-E001` for engine)
- Module codes: E=Engine, B=Brokers, S=Streaming, O=OrderManager, R=Reconciler

### Code Organization

**Adapter Implementation Order:**
1. Constants (API URLs, rate limits)
2. `__init__` with secure key loading
3. `connect()` / `disconnect()`
4. Order methods (`submit_order`, `cancel_order`)
5. Account methods (`get_account_info`, `get_positions`, `get_open_orders`)
6. Market data methods (`subscribe_market_data`, `get_current_price`)
7. Private helper methods (`_check_rate_limit`, `_load_private_key`)

### Error Handling

**Hierarchy:**
```
BrokerError (from rustybt.exceptions)
├── LighterConnectionError
├── LighterOrderRejectError
├── LighterRateLimitError
└── LighterKeyError
```

**Logging:**
- All errors logged with `logger.error()` including context
- Sensitive data (keys, addresses) masked before logging
- Include order_id, symbol, and operation in error context

### Logging Strategy

**Structured Logging Format:**
```python
logger.info(
    "order_submitted",
    order_id=order_id,
    symbol=asset.symbol,
    side="BUY" if amount > 0 else "SELL",
    order_type=order_type,
    quantity=str(abs(amount)),
    price=str(limit_price) if limit_price else "market",
)
```

**Log Levels:**
- `DEBUG`: Rate limit checks, message parsing details
- `INFO`: Order submissions, fills, connections, disconnections
- `WARNING`: Rate limit approaching, partial fills, reconnections
- `ERROR`: Failed operations, rejected orders, exceptions

## Data Architecture

### Lighter.xyz API Data Models

**Order Response:**
```python
@dataclass
class LighterOrderResponse:
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    order_type: str
    quantity: Decimal
    price: Decimal | None
    status: Literal["pending", "open", "filled", "cancelled"]
    filled_quantity: Decimal
    timestamp: datetime
```

**Position Response:**
```python
@dataclass
class LighterPosition:
    symbol: str
    size: Decimal  # Signed (positive=long, negative=short)
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: Decimal
```

**Candlestick Data:**
```python
# Standard OHLCV schema (Polars DataFrame)
LIGHTER_OHLCV_SCHEMA = {
    "timestamp": pl.Datetime("us"),
    "symbol": pl.Utf8,
    "open": pl.Decimal(precision=18, scale=8),
    "high": pl.Decimal(precision=18, scale=8),
    "low": pl.Decimal(precision=18, scale=8),
    "close": pl.Decimal(precision=18, scale=8),
    "volume": pl.Decimal(precision=18, scale=8),
}
```

## API Contracts

### Lighter.xyz Broker Adapter Interface

```python
class LighterBrokerAdapter(BrokerAdapter):
    # Connection
    async def connect(self) -> None
    async def disconnect(self) -> None
    def is_connected(self) -> bool

    # Orders
    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,  # "market", "limit"
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str  # Returns order_id

    async def cancel_order(self, broker_order_id: str) -> None

    # Account
    async def get_account_info(self) -> dict[str, Decimal]
    async def get_positions(self) -> list[dict]
    async def get_open_orders(self) -> list[dict]

    # Market Data
    async def subscribe_market_data(self, assets: list[Asset]) -> None
    async def unsubscribe_market_data(self, assets: list[Asset]) -> None
    async def get_next_market_data(self) -> dict | None
    async def get_current_price(self, asset: Asset) -> Decimal
```

### Lighter.xyz Data Adapter Interface

```python
class LighterDataAdapter(BaseDataAdapter):
    # Core fetch
    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,  # "1m", "5m", "15m", "1h", "4h", "1d"
    ) -> pl.DataFrame

    # Asset discovery
    async def get_available_assets(self) -> list[dict]
    async def get_assets_by_category(self, category: str) -> list[dict]

    # Additional data
    async def get_funding_rates(self, symbol: str) -> pl.DataFrame

    # Validation/standardization
    def validate(self, df: pl.DataFrame) -> bool
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame
```

## Security Architecture

### Private Key Management

**Environment Variables:**
- `LIGHTER_PRIVATE_KEY` - Ethereum private key (hex, no 0x prefix)
- `LIGHTER_API_KEY` - API key (if required)
- `LIGHTER_ENCRYPTION_KEY` - Fernet key for encrypted keystores

**Encrypted Keystore:**
```python
# Create encrypted keystore
LighterBrokerAdapter.create_encrypted_keystore(
    private_key="your_private_key_here",
    output_path="~/.rustybt/lighter_key.enc",
    encryption_key=Fernet.generate_key().decode()
)
```

**Key Validation:**
- Validate key length (64 hex characters)
- Validate hex format
- Derive wallet address and log masked version only

### Testnet Isolation

**Configuration:**
```python
# Default to testnet
LighterBrokerAdapter(testnet=True)  # Uses testnet API

# Mainnet requires explicit opt-in
LighterBrokerAdapter(testnet=False)  # Logs warning
```

**Environment Variable Separation:**
- Testnet: `LIGHTER_TESTNET_PRIVATE_KEY`
- Mainnet: `LIGHTER_MAINNET_PRIVATE_KEY`

## Performance Considerations

### Target Performance (from NFRs)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Order submission latency | < 100ms (excl. network) | Signal to API call |
| WebSocket reconnection | < 30 seconds | Disconnect to reconnected |
| Paper trading overhead | < 10ms vs live path | Order processing time |
| Memory stability | No leaks in 48 hours | Memory profiling |
| State persistence | < 1 second | State save operation |
| Data fetch (1 year daily) | < 30 seconds | Full fetch + parse |

### Optimization Strategies

1. **Connection Pooling:** Reuse HTTP connections for REST API calls
2. **Async Operations:** All I/O operations are async for concurrency
3. **Rate Limit Awareness:** Pre-check rate limits to avoid rejections
4. **Lazy Loading:** Only load data when needed
5. **Parquet Caching:** Cache historical data fetches as Parquet

## Deployment Architecture

**Not Applicable for MVP** - Epic 10 focuses on local development and testnet validation.

**Future Considerations:**
- Docker containers for live trading
- Kubernetes for multi-instance deployment
- Health checks and auto-recovery
- Secrets management (Vault, AWS Secrets Manager)

## Development Environment

### Prerequisites

```bash
# Python 3.12+
python --version  # Must be 3.12+

# rustybt development environment
cd rustybt
pip install -e ".[dev,test]"
```

### Setup Commands

```bash
# Install Epic 10 dependencies
pip install lighter-sdk cryptography httpx

# Set up Lighter.xyz testnet credentials
export LIGHTER_TESTNET_PRIVATE_KEY="your_testnet_private_key"

# Create encrypted keystore (optional, more secure)
python -c "
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(f'Encryption key: {key.decode()}')
print('Save this key securely!')
"

# Run audit tests
pytest tests/live/audit/ -v

# Run Lighter.xyz adapter tests (testnet)
pytest tests/live/lighter/ -v --testnet

# Run stress tests (long-running)
pytest tests/live/stress/test_long_running.py -v --duration=3600
```

## Architecture Decision Records (ADRs)

### ADR-001: Follow HyperliquidBrokerAdapter Pattern for Lighter.xyz

**Decision:** Implement LighterBrokerAdapter following the same patterns as HyperliquidBrokerAdapter

**Rationale:**
- Both are DeFi platforms requiring private key authentication
- Both use transaction-based order submission
- Both need similar security measures (key encryption, testnet isolation)
- Consistency reduces learning curve and maintenance burden

**Status:** Accepted

---

### ADR-002: Structured YAML for Audit Findings

**Decision:** Store audit findings in structured YAML files with severity classification

**Rationale:**
- Machine-readable for automated tracking
- Human-readable for review
- Version-controllable
- Supports regression test linkage

**Alternatives Considered:**
- JSON - Less readable, chose YAML
- Database - Over-engineering for this use case
- Markdown - Not machine-parseable

**Status:** Accepted

---

### ADR-003: Default to Testnet for All New Adapters

**Decision:** All new broker adapters default to testnet mode (`testnet=True`)

**Rationale:**
- Prevents accidental mainnet trades during development/testing
- Explicit opt-in for mainnet reduces risk
- Aligns with production safety requirements (NFR15)

**Status:** Accepted

---

### ADR-004: pytest-based Stress Testing Framework

**Decision:** Use pytest with async fixtures for stress testing rather than external tools

**Rationale:**
- Consistent with existing test infrastructure
- pytest-asyncio supports async stress tests natively
- Configurable via YAML scenario files
- Integrates with CI/CD

**Alternatives Considered:**
- Locust - Overkill for adapter testing
- Custom framework - Unnecessary complexity

**Status:** Accepted

---

### ADR-005: Rate Limiting at Adapter Level

**Decision:** Each adapter implements its own rate limiting using token bucket algorithm

**Rationale:**
- Different exchanges have different rate limits
- Adapter-level enforcement prevents rejections
- Matches existing pattern in HyperliquidBrokerAdapter
- Allows per-symbol order rate limiting

**Status:** Accepted

---

_Generated by BMAD Decision Architecture Workflow v1.0_
_Date: 2025-12-05_
_For: .smirk_
