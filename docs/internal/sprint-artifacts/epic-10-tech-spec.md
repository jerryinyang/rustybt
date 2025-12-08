# Epic Technical Specification: Live Trading Production Readiness & Lighter.xyz Integration

Date: 2025-12-05
Author: .smirk
Epic ID: 10
Status: Draft

---

## Overview

Epic 10 transforms rustybt from a framework with live trading capabilities into a **production-ready trading system** through systematic code auditing, comprehensive testing, and platform expansion. This epic addresses the critical gap between rustybt's extensive live trading infrastructure (38+ modules covering broker adapters, streaming, order management, and paper trading) and the rigorous validation required for production deployment.

The epic has two primary thrusts: (1) **Production hardening** through code audits, paper trading validation, testnet integration testing, and stress testing to build confidence in the existing infrastructure, and (2) **Platform expansion** through Lighter.xyz integration, adding a leading DeFi perpetual DEX ($1-2B daily volume) as both a broker adapter and data source.

## Objectives and Scope

### In Scope

- **Code Audit Infrastructure:** Systematic audit of all 38 live trading modules with YAML-based findings tracking, severity classification, and regression test creation
- **Paper Trading Validation:** End-to-end test harness validating strategy execution, order fills, position tracking, PnL calculations, state persistence, and 24+ hour stability
- **Testnet Integration Testing:** Validation against at least one exchange testnet (Hyperliquid primary) including order submission, fill reception, reconnection, and state recovery
- **Stress Testing Framework:** Network resilience tests, high-frequency order throughput tests, 24-48 hour long-running stability tests, and API error simulation
- **Lighter.xyz Broker Adapter:** Full trading adapter implementing `BrokerAdapter` ABC with order submission, position tracking, fill notifications, testnet/mainnet support, and paper trading mode
- **Lighter.xyz Data Adapter:** OHLCV data ingestion implementing `BaseDataAdapter` with asset discovery, multi-timeframe support, funding rate fetching, and bundle integration
- **Lighter.xyz Streaming Adapter:** Real-time market data implementing `BaseWebSocketAdapter` with trade/orderbook subscriptions, bar aggregation, and reconnection resilience
- **Documentation:** Live trading setup guide, Lighter.xyz integration docs, testnet guides, audit reports, stress test reports

### Out of Scope

- Additional DEX integrations (dYdX, GMX, Vertex) - Growth feature for post-MVP
- Chaos engineering / advanced stress testing scenarios
- Kubernetes deployment configurations
- Multi-account management / institutional features
- Real-time trading dashboard improvements beyond existing functionality
- Performance optimizations to core backtesting engine

## System Architecture Alignment

This epic aligns with rustybt's existing architecture through **brownfield extension** of established patterns:

### Component Alignment

| New Component | Existing Pattern | Interface |
|---------------|------------------|-----------|
| `LighterBrokerAdapter` | `HyperliquidBrokerAdapter` | `BrokerAdapter` ABC |
| `LighterDataAdapter` | `CCXTDataAdapter`, `PolygonAdapter` | `BaseDataAdapter` ABC |
| `LighterWebSocketAdapter` | `HyperliquidWebSocketAdapter` | `BaseWebSocketAdapter` ABC |
| Audit Infrastructure | pytest framework | `tests/live/audit/` |
| Stress Testing | pytest-asyncio | `tests/live/stress/` |

### Architectural Constraints

- **Private Key Security:** Following `HyperliquidBrokerAdapter` pattern - environment variables, encrypted keystores, never log credentials
- **Rate Limiting:** Token bucket algorithm at adapter level (600 req/min REST, 20 orders/sec per symbol)
- **Reconnection:** Exponential backoff with jitter, circuit breaker after consecutive errors threshold
- **Testnet First:** All adapters default to testnet (`testnet=True`) per ADR-003
- **Decimal Precision:** All financial calculations use `Decimal` type with precision=18, scale=8

## Detailed Design

### Services and Modules

| Module | Responsibility | Location |
|--------|---------------|----------|
| **LighterBrokerAdapter** | Order submission, position tracking, fill notifications for Lighter.xyz DEX | `rustybt/live/brokers/lighter_adapter.py` |
| **LighterDataAdapter** | Historical OHLCV data fetching, asset discovery, funding rates | `rustybt/data/adapters/lighter_adapter.py` |
| **LighterWebSocketAdapter** | Real-time trade/orderbook streaming, bar aggregation | `rustybt/live/streaming/lighter_stream.py` |
| **Audit Infrastructure** | YAML-based findings storage, audit fixtures, regression tests | `tests/live/audit/` |
| **Stress Testing Framework** | Configurable YAML scenarios, network/throughput/stability tests | `tests/live/stress/` |
| **Paper Trading Tests** | Execution harness, state persistence, parity verification | `tests/live/paper/` |
| **Testnet Integration Tests** | Per-exchange testnet validation | `tests/live/testnet/` |

### Data Models and Contracts

**LighterOrderResponse:**
```python
@dataclass
class LighterOrderResponse:
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    order_type: str  # "market", "limit"
    quantity: Decimal
    price: Decimal | None
    status: Literal["pending", "open", "filled", "cancelled"]
    filled_quantity: Decimal
    timestamp: datetime
```

**LighterPosition:**
```python
@dataclass
class LighterPosition:
    symbol: str
    size: Decimal  # Signed: positive=long, negative=short
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: Decimal
```

**OHLCV Schema (Polars DataFrame):**
```python
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

**Audit Finding Schema (YAML):**
```yaml
findings:
  - id: AUDIT-E001  # E=Engine, B=Brokers, S=Streaming, O=OrderManager, R=Reconciler, C=CircuitBreakers
    module: rustybt/live/engine.py
    line: 234
    severity: HIGH  # CRITICAL, HIGH, MEDIUM, LOW
    category: error_handling
    description: "Uncaught exception in main loop can crash engine"
    recommendation: "Wrap main loop in try/except with graceful shutdown"
    status: OPEN  # OPEN, IN_PROGRESS, RESOLVED, VERIFIED
    found_by: code_audit
    found_at: "2025-12-05"
    resolved_at: null
    regression_test: null
```

### APIs and Interfaces

**LighterBrokerAdapter Interface:**
```python
class LighterBrokerAdapter(BrokerAdapter):
    # Constants
    MAINNET_API_URL = "https://mainnet.zklighter.elliot.ai/"
    TESTNET_API_URL = "https://testnet.zklighter.elliot.ai/"
    REQUESTS_PER_MINUTE = 600
    ORDERS_PER_SECOND = 20

    # Connection
    async def connect(self) -> None
    async def disconnect(self) -> None
    def is_connected(self) -> bool

    # Orders
    async def submit_order(
        self, asset: Asset, amount: Decimal, order_type: str,
        limit_price: Decimal | None = None, stop_price: Decimal | None = None
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

**LighterDataAdapter Interface:**
```python
class LighterDataAdapter(BaseDataAdapter):
    # Core fetch
    async def fetch(
        self, symbols: list[str], start_date: pd.Timestamp,
        end_date: pd.Timestamp, resolution: str
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

**LighterWebSocketAdapter Interface:**
```python
class LighterWebSocketAdapter(BaseWebSocketAdapter):
    async def subscribe(self, symbols: list[str], channels: list[str]) -> None
    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None
    def parse_message(self, raw_message: dict) -> TickData | None
    def _build_subscription_message(self, symbols: list[str], channels: list[str]) -> dict
    def _build_unsubscription_message(self, symbols: list[str], channels: list[str]) -> dict
```

**Exception Hierarchy:**
```
BrokerError (from rustybt.exceptions)
├── LighterConnectionError
├── LighterOrderRejectError
├── LighterRateLimitError
└── LighterKeyError
```

### Workflows and Sequencing

**Order Submission Flow:**
```
1. Strategy Signal → LighterBrokerAdapter.submit_order()
2. Check rate limits (token bucket) → Wait if exceeded
3. Sign transaction with private key (via lighter-sdk)
4. POST /sendTx → Parse response for order ID
5. Return order ID to OrderManager
6. Poll /accountInactiveOrders OR WebSocket for fill notification
7. Process fill → Update StateManager positions
```

**Data Ingestion Flow:**
```
1. User invokes `rustybt ingest lighter BTC-PERP --start 2024-01-01`
2. LighterDataAdapter.fetch() → GET /candlesticks with pagination
3. Parse response → Polars DataFrame
4. standardize() → Convert to rustybt schema
5. validate() → OHLCV relationship checks
6. Write to bundle system (Parquet)
7. Update catalog metadata
```

**Code Audit Flow:**
```
1. Run static analysis (ruff, mypy) on target modules
2. Parse output → Create structured findings in YAML
3. Manual code review → Add findings with "manual_review" category
4. Classify severity (Critical/High/Medium/Low)
5. Resolve Critical/High issues
6. Create regression test for each resolved issue
7. Update finding status → RESOLVED → VERIFIED
8. Generate audit summary report
```

**Stress Test Flow:**
```
1. Load scenario configuration from YAML
2. Initialize paper broker or testnet connection
3. Execute scenario (network failure, order burst, long-running)
4. Collect metrics (reconnection time, memory usage, error counts)
5. Evaluate against success criteria
6. Generate stress test report (pass/fail, metrics)
```

## Non-Functional Requirements

### Performance

| Metric | Target | Source |
|--------|--------|--------|
| Order submission latency | < 100ms (signal to API call, excl. network) | NFR1 |
| WebSocket reconnection | < 30 seconds | NFR2 |
| Paper trading overhead | < 10ms vs live path | NFR3 |
| Memory stability | No leaks in 48-hour operation | NFR4 |
| State persistence | < 1 second | NFR5 |
| Data fetch (1 year daily) | < 30 seconds | NFR6 |

### Security

- **NFR13:** API keys and private keys MUST never be logged or exposed in error messages
- **NFR14:** Credentials loaded from environment variables or secure config only
- **NFR15:** Testnet and mainnet configurations clearly separated (different env var names)
- **NFR16:** All API communications via HTTPS/WSS
- **NFR17:** Private key operations use lighter-sdk's secure methods

**Key Loading Priority:**
1. Environment variable: `LIGHTER_PRIVATE_KEY` (RECOMMENDED)
2. Encrypted keystore file + `LIGHTER_ENCRYPTION_KEY`
3. Direct parameter (logs warning, NOT RECOMMENDED)

### Reliability/Availability

- **NFR7:** System survives any single API failure without data loss
- **NFR8:** Stale connections detected and trigger reconnection within 60 seconds
- **NFR9:** Orders queued during brief disconnections (< 30 seconds)
- **NFR10:** All order state transitions logged for audit/debug
- **NFR11:** Paper trading produces deterministic results given same inputs
- **NFR12:** State recovery after restart restores exact position state

### Observability

**Structured Logging (structlog):**
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
- `WARNING`: Rate limit approaching (80%), partial fills, reconnections
- `ERROR`: Failed operations, rejected orders, exceptions

**Audit Trails:**
- All order state transitions logged with timestamps
- Findings tracked in machine-readable YAML
- Stress test results in structured JSON

## Dependencies and Integrations

### Core Dependencies (Existing in pyproject.toml)

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | >=3.12 | Required by rustybt constitution |
| polars | >=1.0 | Data processing |
| structlog | >=24.0 | Structured logging |
| websockets | >=14.0 | WebSocket connections |
| cryptography | >=41.0.0 | Fernet encryption for keystores |
| eth-account | >=0.10.0 | Ethereum wallet operations |
| pytest | >=7.2.0 | Test framework |
| pytest-asyncio | >=0.21.0 | Async test support |
| httpx | >=0.25 | HTTP client (existing via aiohttp >=3.9.0) |
| pyyaml | >=6.0 | YAML parsing for findings/scenarios |

### New Dependencies for Epic 10

| Dependency | Version | Purpose |
|------------|---------|---------|
| lighter-sdk | Latest | Official Lighter.xyz Python SDK |

### Integration Points

**Internal rustybt:**
- `BrokerAdapter` ABC at `rustybt/live/brokers/base.py`
- `BaseDataAdapter` ABC at `rustybt/data/adapters/base.py`
- `BaseWebSocketAdapter` ABC at `rustybt/live/streaming/base.py`
- `DecimalOrder`, `DecimalPosition`, `DecimalTransaction` from `rustybt/finance/decimal/`
- Bundle/catalog system at `rustybt/data/`
- `LiveTradingEngine` at `rustybt/live/engine.py`

**External:**
- Lighter.xyz REST API: `https://mainnet.zklighter.elliot.ai/` (mainnet), `https://testnet.zklighter.elliot.ai/` (testnet)
- Lighter.xyz WebSocket: Real-time market data
- Exchange testnets: Binance, Bybit, Hyperliquid (for validation)

## Acceptance Criteria (Authoritative)

### Epic 10.1: Production Code Audit & Issue Resolution

**AC-10.1.1:** Audit infrastructure created with YAML schema supporting: id, module, line, severity, category, description, recommendation, status, found_by, found_at, resolved_at, regression_test fields

**AC-10.1.2:** Static analysis (ruff, mypy) completed on all 7 core live trading modules (engine.py, order_manager.py, state_manager.py, strategy_executor.py, reconciler.py, circuit_breakers.py, data_feed.py) with findings captured in YAML

**AC-10.1.3:** Static analysis completed on all 7 broker adapters and 6 streaming modules with findings captured in YAML

**AC-10.1.4:** Manual code review completed focusing on order state machine, state persistence/recovery, reconnection logic, circuit breaker conditions, and concurrency patterns

**AC-10.1.5:** All Critical and High severity findings resolved with corresponding regression tests, finding YAML updated with resolved_at and regression_test paths

### Epic 10.2: Paper & Testnet Trading Validation

**AC-10.2.1:** Paper trading test harness validates strategy execution, order fills (immediate/delayed models), position tracking, PnL calculations, and order state transitions

**AC-10.2.2:** Paper trading state persists across restarts and runs stably for 24+ hours with < 10% memory growth

**AC-10.2.3:** Paper trading behavior verified to match live trading behavior for order submission parameters, position calculations, and PnL logic

**AC-10.2.4:** Testnet connectivity validated with successful order submission, fill reception, and position tracking on at least one exchange (Hyperliquid)

**AC-10.2.5:** WebSocket reconnection validated: reconnects within 30 seconds, restores subscriptions, reconciles state after disconnection

**AC-10.2.6:** End-to-end order flow validated: signal → order → fill → position update, with < 100ms latency (excluding network)

### Epic 10.3: Stress Testing & Resilience Framework

**AC-10.3.1:** Stress testing infrastructure created with configurable YAML scenarios supporting network, throughput, long_running, and error test types

**AC-10.3.2:** Network failure tests pass: disconnect detection within 60s, reconnection within 30s, circuit breaker trips after threshold

**AC-10.3.3:** High-frequency order tests pass: 10 orders/sec for 60 seconds with no lost/duplicated orders, latency < 100ms

**AC-10.3.4:** Long-running stability test passes: 24-48 hours continuous operation with stable memory and no state corruption

**AC-10.3.5:** API error simulation tests pass: graceful handling of 500, 429, timeout, connection refused errors

### Epic 10.4: Lighter.xyz Broker Adapter

**AC-10.4.1:** LighterBrokerAdapter authenticates via lighter-sdk with secure key loading (env var priority)

**AC-10.4.2:** Market and limit orders submitted successfully via /sendTx with rate limiting

**AC-10.4.3:** Orders cancelled successfully, open orders and order history queryable

**AC-10.4.4:** Positions and account info queryable with Decimal precision

**AC-10.4.5:** Fill notifications received (polling or WebSocket), paper trading mode simulates fills with real prices

**AC-10.4.6:** Error handling implemented with LighterConnectionError, LighterOrderRejectError, LighterRateLimitError, LighterKeyError; integration tests pass on testnet

### Epic 10.5: Lighter.xyz Data & Streaming Adapters

**AC-10.5.1:** LighterDataAdapter discovers available assets with filtering by category and name pattern

**AC-10.5.2:** OHLCV data fetched for multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d) with pagination handling

**AC-10.5.3:** Data standardized to rustybt schema and ingested into bundle system; funding rates fetchable

**AC-10.5.4:** LighterWebSocketAdapter connects and subscribes to trades channel, parses messages to TickData

**AC-10.5.5:** Trade/orderbook/candlestick subscriptions work, BarBuffer aggregates to OHLCV bars

**AC-10.5.6:** Streaming reconnects with exponential backoff, restores subscriptions, buffers during brief disconnections

### Epic 10.6: Documentation & Reporting

**AC-10.6.1:** Live trading setup guide covers all platforms with step-by-step instructions and security best practices

**AC-10.6.2:** Lighter.xyz integration documentation covers broker/data/streaming adapters with API reference and examples

**AC-10.6.3:** Testnet setup instructions provided for Binance, Bybit, Hyperliquid, and Lighter.xyz

**AC-10.6.4:** Audit report and stress test report generated from actual test results

## Traceability Mapping

| AC | Spec Section | Component(s) | Test Idea |
|----|--------------|--------------|-----------|
| AC-10.1.1 | Services and Modules, Data Models | `tests/live/audit/` | Verify YAML schema loads, validates, supports all fields |
| AC-10.1.2 | Workflows | `tests/live/audit/test_*_audit.py` | Run ruff/mypy, verify output captured in YAML |
| AC-10.1.3 | Workflows | `tests/live/audit/test_brokers_audit.py`, `test_streaming_audit.py` | Static analysis on broker/streaming modules |
| AC-10.1.4 | Workflows | `tests/live/audit/` | Manual review checklist verification |
| AC-10.1.5 | Workflows | `tests/live/audit/test_*_regressions.py` | Each Critical/High has regression test |
| AC-10.2.1 | APIs and Interfaces | `tests/live/paper/test_paper_execution.py` | Execute strategy, verify fills/positions/PnL |
| AC-10.2.2 | NFR Performance/Reliability | `tests/live/paper/test_paper_stability.py` | Restart test, 24h run with memory profiling |
| AC-10.2.3 | Workflows | `tests/live/paper/test_paper_parity.py` | Compare paper vs mock live broker calls |
| AC-10.2.4 | APIs and Interfaces | `tests/live/testnet/test_hyperliquid_testnet.py` | Connect, submit order, verify fill |
| AC-10.2.5 | Workflows | `tests/live/testnet/test_testnet_reconnection.py` | Force disconnect, verify reconnect < 30s |
| AC-10.2.6 | Workflows | `tests/live/testnet/test_e2e_order_flow.py` | Full chain test with timing |
| AC-10.3.1 | Services and Modules, Data Models | `tests/live/stress/conftest.py` | Load YAML scenario, execute test |
| AC-10.3.2 | Workflows | `tests/live/stress/test_network_resilience.py` | Simulate disconnect, measure reconnect time |
| AC-10.3.3 | Workflows | `tests/live/stress/test_order_throughput.py` | Submit 10/sec, verify no loss |
| AC-10.3.4 | NFR Performance | `tests/live/stress/test_long_running.py` | 24-48h run with memory sampling |
| AC-10.3.5 | Workflows | `tests/live/stress/test_api_errors.py` | Mock 500/429/timeout, verify handling |
| AC-10.4.1 | APIs and Interfaces, Security | `tests/live/lighter/test_lighter_broker.py` | Test auth with env var, encrypted keystore |
| AC-10.4.2 | APIs and Interfaces | `tests/live/lighter/test_lighter_broker.py` | Submit market/limit, verify rate limiting |
| AC-10.4.3 | APIs and Interfaces | `tests/live/lighter/test_lighter_broker.py` | Cancel, get_open_orders, get_order_history |
| AC-10.4.4 | Data Models | `tests/live/lighter/test_lighter_broker.py` | get_positions, get_account_info |
| AC-10.4.5 | Workflows | `tests/live/lighter/test_lighter_broker.py` | Fill notification, paper mode |
| AC-10.4.6 | APIs and Interfaces | `tests/live/lighter/test_lighter_broker.py` | Error scenarios, testnet integration |
| AC-10.5.1 | APIs and Interfaces | `tests/live/lighter/test_lighter_data.py` | get_available_assets, filtering |
| AC-10.5.2 | APIs and Interfaces | `tests/live/lighter/test_lighter_data.py` | fetch with various timeframes |
| AC-10.5.3 | Workflows | `tests/live/lighter/test_lighter_data.py` | standardize, validate, bundle integration |
| AC-10.5.4 | APIs and Interfaces | `tests/live/lighter/test_lighter_stream.py` | connect, subscribe, parse_message |
| AC-10.5.5 | Workflows | `tests/live/lighter/test_lighter_stream.py` | Multiple channels, bar aggregation |
| AC-10.5.6 | Workflows | `tests/live/lighter/test_lighter_stream.py` | Reconnect test, buffering |
| AC-10.6.1 | Documentation | Manual review | Guide completeness, security coverage |
| AC-10.6.2 | Documentation | Manual review | Lighter docs complete |
| AC-10.6.3 | Documentation | Manual review | Testnet instructions for all platforms |
| AC-10.6.4 | Workflows | Report generation scripts | Reports generated from test results |

## Risks, Assumptions, Open Questions

### Risks

| ID | Type | Description | Mitigation |
|----|------|-------------|------------|
| R1 | Risk | lighter-sdk may have breaking changes or undocumented behavior | Pin version, implement adapter layer, comprehensive error handling |
| R2 | Risk | Lighter.xyz testnet may be unavailable or rate-limited | Implement mock-based tests as fallback, document testnet limitations |
| R3 | Risk | Code audit may reveal critical issues requiring significant refactoring | Prioritize Critical/High issues, track Medium/Low for future, maintain audit transparency |
| R4 | Risk | 24-48 hour stress tests may be impractical in CI/CD | Run long tests manually/nightly, use shorter CI tests with markers |
| R5 | Risk | zk-proof verification delays may cause unexpected order confirmation latency | Document expected delays, implement polling with appropriate timeout |

### Assumptions

| ID | Type | Description |
|----|------|-------------|
| A1 | Assumption | Lighter.xyz API endpoints and SDK behavior are stable during epic duration |
| A2 | Assumption | Hyperliquid testnet remains available for integration testing |
| A3 | Assumption | Existing HyperliquidBrokerAdapter pattern is production-ready and can be followed |
| A4 | Assumption | Paper broker accurately simulates live broker behavior for validation purposes |
| A5 | Assumption | rustybt bundle system can handle Lighter.xyz data format after standardization |

### Open Questions

| ID | Type | Description | Resolution Path |
|----|------|-------------|-----------------|
| Q1 | Question | What specific zk-proof verification delays should we expect on Lighter.xyz? | Test on testnet, consult Lighter.xyz documentation |
| Q2 | Question | Should audit findings be tracked in GitHub Issues in addition to YAML? | Decision during Story 10.1.1 - start with YAML, evaluate GitHub integration |
| Q3 | Question | Which exchange testnet should be primary for validation (Hyperliquid, Binance, Bybit)? | Start with Hyperliquid (similar DeFi pattern), expand as needed |

## Test Strategy Summary

### Test Levels

| Level | Scope | Location | Markers |
|-------|-------|----------|---------|
| Unit | Individual adapter methods, parsing, validation | `tests/live/lighter/`, `tests/live/audit/` | Default |
| Integration | End-to-end flows with mocks | `tests/live/paper/`, `tests/live/testnet/` | `@pytest.mark.integration` |
| Testnet | Real exchange API calls | `tests/live/testnet/` | `@pytest.mark.live`, skip if no creds |
| Stress | Long-running, high-frequency | `tests/live/stress/` | `@pytest.mark.slow` |

### Frameworks and Tools

- **pytest** + **pytest-asyncio**: Core test framework with async support
- **pytest-timeout**: Timeout handling for long tests
- **memory_profiler** / **tracemalloc**: Memory leak detection
- **hypothesis**: Property-based testing for edge cases (existing in project)
- **freezegun**: Time mocking for timestamp-sensitive tests (existing)

### Coverage Strategy

- All Critical/High audit findings MUST have regression tests before status=RESOLVED
- Lighter.xyz adapter tests cover: auth, orders, positions, errors, rate limiting
- Paper trading tests cover: execution, state persistence, parity
- Stress tests cover: network resilience, throughput, long-running stability
- Integration tests skip gracefully without credentials (`pytest.mark.skipif`)

### Edge Cases to Test

- Order submission during rate limit approach (80% threshold)
- WebSocket disconnect during active order
- State recovery after crash (position reconciliation)
- Invalid/malformed API responses
- Partial fills
- Network timeout during order cancellation
- Memory usage during rapid order submission
- Concurrent order submissions to same symbol
