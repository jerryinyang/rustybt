# rustybt Epic 10 - Product Requirements Document

**Author:** .smirk
**Date:** 2025-12-05
**Version:** 1.0

---

## Executive Summary

This PRD defines requirements for **Epic 10: Live Trading Production Readiness & Lighter.xyz Integration** - a comprehensive effort to audit, harden, stress-test, and expand rustybt's paper trading and live trading capabilities.

**The Core Problem:** rustybt has extensive live trading infrastructure (38+ modules covering broker adapters, streaming, order management, and paper trading), but this infrastructure has not been rigorously audited for production correctness or stress-tested under realistic conditions. Additionally, the growing DeFi ecosystem demands integration with new platforms like Lighter.xyz.

**The Solution:**
1. **Complete Code Audit** - Systematic review of all live/paper trading modules for correctness, edge cases, and error handling
2. **Application Testing** - End-to-end testing beyond unit tests using paper trading and testnet environments
3. **Stress Testing** - Validate behavior under realistic operational stress (network failures, high order volume, reconnection)
4. **Platform Expansion** - Add Lighter.xyz as both a broker adapter (for trading) and data adapter (for market data ingestion)

### What Makes This Special

**This is a production-readiness epic** - transforming rustybt from a framework with live trading capabilities into a **battle-tested, production-ready trading system**.

Unlike typical feature development, this epic focuses on:
- **Proving correctness** through comprehensive code audits
- **Building confidence** through realistic application testing
- **Validating resilience** through stress testing
- **Expanding reach** through Lighter.xyz integration (a leading DeFi perp DEX processing $1-2B daily volume)

The Lighter.xyz integration is particularly compelling - it brings rustybt into the DeFi perpetuals space with a platform that offers:
- Zero-knowledge proof verified order matching
- 117+ trading pairs with up to 25x leverage
- Emerging spot trading capabilities
- Active Python SDK (`lighter-sdk`) for seamless integration

---

## Project Classification

**Technical Type:** Developer Tool (Trading Framework)
**Domain:** Fintech (Algorithmic Trading / DeFi)
**Complexity:** High

**Classification Rationale:**

This is a **developer tool** epic within the rustybt algorithmic trading framework. It combines:
- **Infrastructure hardening** - Production-readiness validation of existing code
- **Quality assurance** - Code audits, integration testing, stress testing
- **Platform integration** - New broker and data adapters for Lighter.xyz

**Domain Complexity - Fintech/DeFi (High):**

The fintech/algorithmic trading domain with DeFi expansion requires:
- **Financial Calculation Accuracy:** Order execution, position tracking, PnL calculations must be exact
- **Network Resilience:** Live trading must handle WebSocket disconnections, API failures, rate limits
- **Order Lifecycle Integrity:** Orders must transition through states correctly (pending → submitted → filled/cancelled)
- **DeFi-Specific Concerns:** zk-rollup transaction submission, L2 gas management, on-chain settlement verification
- **Security:** API key management, transaction signing, testnet vs mainnet isolation

**Key Domain Concerns Addressed:**
1. **Execution Reliability:** Paper and live trading must behave identically (minus real fills)
2. **State Consistency:** Position state must survive restarts, reconnections, and network failures
3. **DeFi Integration:** Lighter.xyz uses zk-proofs and L2 transactions requiring careful handling
4. **Multi-Platform Parity:** New adapters must follow established patterns for consistency

---

## Success Criteria

Epic 10 is successful when:

### Primary Success Criteria

1. **Complete Code Audit Coverage**
   - All 38 live trading module files audited for correctness
   - All identified issues documented with severity classification
   - Critical and high-severity issues resolved before production use
   - Audit findings documented in ADR or similar format

2. **Paper Trading Validation**
   - Paper broker executes strategies identically to live brokers (minus real fills)
   - Paper trading sessions can run for 24+ hours without state corruption
   - Order lifecycle tracked correctly through all state transitions
   - Position and PnL calculations verified against expected values

3. **Live Trading Validation (Testnet)**
   - At least one existing broker adapter (Binance/Bybit/Hyperliquid) validated on testnet
   - End-to-end order flow verified: signal → order → fill → position update
   - Reconnection handling verified after intentional disconnection
   - Strategy execution validated across multiple sessions

4. **Stress Testing Passed**
   - High-frequency order submission (realistic rate for retail/small fund)
   - Network failure recovery (WebSocket disconnect/reconnect)
   - API rate limit handling (graceful degradation)
   - Long-running stability (24-48 hour continuous operation)

5. **Lighter.xyz Integration Complete**
   - Broker adapter following existing pattern (`LighterBrokerAdapter`)
   - Data adapter for candlestick/OHLCV ingestion (`LighterDataAdapter`)
   - Asset discovery and filtering (by name, category, or all)
   - Paper trading mode support
   - Testnet/mainnet configuration support

### Confidence Metrics

6. **Zero Critical Bugs in Production Path**
   - No order execution bugs that could cause financial loss
   - No state corruption bugs that could misreport positions
   - No security vulnerabilities in API key handling

7. **Documentation Complete**
   - Live trading user guide updated
   - Lighter.xyz integration documented
   - Testnet setup guide for each supported platform

---

## Product Scope

### MVP - Minimum Viable Product

The MVP delivers **production-ready live/paper trading with Lighter.xyz support**.

**1. Code Audit & Issue Resolution**
- Systematic audit of all live trading modules:
  - `rustybt/live/engine.py` - Core trading engine
  - `rustybt/live/brokers/` - All 6 broker adapters
  - `rustybt/live/streaming/` - All 6 streaming modules
  - `rustybt/live/order_manager.py` - Order lifecycle management
  - `rustybt/live/state_manager.py` - State persistence
  - `rustybt/live/reconciler.py` - Position reconciliation
  - `rustybt/live/circuit_breakers.py` - Safety mechanisms
  - `rustybt/live/shadow/` - Shadow trading validation
- Issue classification (Critical/High/Medium/Low)
- Resolution of Critical and High issues

**2. Application Testing Infrastructure**
- End-to-end test harness for paper trading
- Testnet integration tests for live trading
- Strategy execution validation tests
- Order lifecycle verification tests

**3. Stress Testing Suite**
- Network resilience tests (disconnect/reconnect)
- High-frequency order tests (within rate limits)
- Long-running stability tests (24-48 hours)
- Error recovery validation

**4. Lighter.xyz Broker Adapter**
- `LighterBrokerAdapter` following `CCXTBrokerAdapter` pattern
- Order submission via `/sendTx` endpoint
- Position tracking via `/account` endpoint
- Order status via `/accountActiveOrders`, `/accountInactiveOrders`
- Paper trading mode (simulated fills)
- Testnet/mainnet configuration

**5. Lighter.xyz Data Adapter**
- `LighterDataAdapter` following existing data adapter pattern
- Candlestick/OHLCV data via `/candlesticks` endpoint
- Asset discovery and listing
- Filtering by asset name, category, or fetch all
- Integration with rustybt bundle system

**6. Lighter.xyz Streaming Adapter**
- Real-time price updates for live trading
- WebSocket or polling-based implementation
- Integration with existing streaming infrastructure

### Growth Features (Post-MVP)

**Expanded Platform Support:**
- Additional DEX integrations (dYdX, GMX, Vertex)
- Additional CEX testnet validations
- Cross-platform arbitrage testing

**Advanced Stress Testing:**
- Chaos engineering tests (random failures)
- Multi-strategy concurrent execution
- High-volatility market simulation

**Enhanced Monitoring:**
- Real-time trading dashboard improvements
- Alerting system for anomalies
- Performance metrics collection

### Vision (Future)

**Production Operations:**
- Kubernetes deployment configurations
- Health check and auto-recovery systems
- Distributed trading across multiple instances

**Institutional Features:**
- Multi-account management
- Risk management overlays
- Compliance logging and audit trails

---

## Developer Tool Specific Requirements

### Code Audit Requirements

**Audit Scope - Live Trading Core:**
| Module | Files | Focus Areas |
|--------|-------|-------------|
| Engine | `engine.py` | Main loop, event dispatch, error handling |
| Order Manager | `order_manager.py` | Order state machine, timeout handling |
| State Manager | `state_manager.py` | Persistence, recovery, corruption prevention |
| Strategy Executor | `strategy_executor.py` | Signal handling, order generation |
| Reconciler | `reconciler.py` | Position sync, discrepancy detection |
| Circuit Breakers | `circuit_breakers.py` | Safety limits, emergency stops |
| Data Feed | `data_feed.py` | Bar assembly, data integrity |

**Audit Scope - Broker Adapters:**
| Adapter | File | Focus Areas |
|---------|------|-------------|
| Base | `brokers/base.py` | Interface contract, error types |
| CCXT | `brokers/ccxt_adapter.py` | Generic exchange handling |
| Binance | `brokers/binance_adapter.py` | Binance-specific quirks |
| Bybit | `brokers/bybit_adapter.py` | Bybit-specific handling |
| Hyperliquid | `brokers/hyperliquid_adapter.py` | DeFi/L1 specific |
| IB | `brokers/ib_adapter.py` | Traditional broker handling |
| Paper | `brokers/paper_broker.py` | Simulation accuracy |

**Audit Scope - Streaming:**
| Stream | File | Focus Areas |
|--------|------|-------------|
| Base | `streaming/base.py` | Interface, reconnection logic |
| CCXT | `streaming/ccxt_stream.py` | Generic WebSocket |
| Binance | `streaming/binance_stream.py` | Binance streams |
| Bybit | `streaming/bybit_stream.py` | Bybit streams |
| Hyperliquid | `streaming/hyperliquid_stream.py` | Hyperliquid streams |
| Bar Buffer | `streaming/bar_buffer.py` | Bar aggregation |

**Audit Methodology:**
1. Static analysis (type checking, linting)
2. Control flow analysis (error paths, edge cases)
3. State machine verification (order lifecycle)
4. Concurrency review (async/await patterns)
5. Security review (credential handling)

### Testing Requirements

**Paper Trading Tests:**
- Strategy execution with simulated fills
- Multi-day session continuity
- Position tracking accuracy
- PnL calculation verification
- Order state transition correctness

**Testnet Integration Tests:**
- Real API connectivity
- Order submission and fill reception
- WebSocket stream reliability
- Rate limit compliance
- Error response handling

**Stress Test Scenarios:**
| Scenario | Description | Success Criteria |
|----------|-------------|------------------|
| Disconnect Recovery | Kill WebSocket mid-session | Reconnect within 30s, no lost orders |
| Order Burst | Submit 10 orders in 1 second | All orders tracked correctly |
| Long Running | 48-hour continuous operation | No memory leaks, state intact |
| API Failure | Simulate 500 errors | Graceful degradation, retry logic |
| Rate Limit | Exceed rate limit intentionally | Backoff and recovery |

### Lighter.xyz Integration Requirements

**Broker Adapter Specification:**
```
LighterBrokerAdapter(BrokerAdapterBase):
  - connect() → Authenticate via lighter-sdk
  - disconnect() → Clean shutdown
  - submit_order(order) → POST /sendTx
  - cancel_order(order_id) → POST /sendTx (cancel tx)
  - get_positions() → GET /account
  - get_open_orders() → GET /accountActiveOrders
  - get_order_status(order_id) → GET /accountActiveOrders or /accountInactiveOrders
  - subscribe_fills() → WebSocket or polling
```

**Data Adapter Specification:**
```
LighterDataAdapter(DataAdapterBase):
  - get_available_assets() → List all tradeable pairs
  - get_assets_by_category(category) → Filter by asset type
  - fetch_ohlcv(symbol, timeframe, start, end) → GET /candlesticks
  - get_funding_rates(symbol) → GET /funding-rates
  - supports_timeframes() → ['1m', '5m', '15m', '1h', '4h', '1d']
```

**Streaming Adapter Specification:**
```
LighterStream(StreamBase):
  - connect() → Establish connection
  - subscribe_trades(symbol) → Real-time trades
  - subscribe_orderbook(symbol) → Order book updates
  - subscribe_candlesticks(symbol, timeframe) → Live candles
  - on_message(callback) → Message handler
```

**Configuration:**
```yaml
lighter:
  api_url: "https://mainnet.zklighter.elliot.ai/"
  testnet: true  # Use testnet for paper trading
  api_key: "${LIGHTER_API_KEY}"
  private_key: "${LIGHTER_PRIVATE_KEY}"  # For tx signing
```

---

## Functional Requirements

### Code Audit & Issue Management

**FR1:** System can perform static analysis on all live trading module files using existing linting tools (ruff, mypy)

**FR2:** System can document audit findings with severity classification (Critical/High/Medium/Low)

**FR3:** System can track audit findings through resolution lifecycle (Open → In Progress → Resolved → Verified)

**FR4:** System can generate audit reports summarizing findings by module and severity

**FR5:** System can create regression tests for each Critical/High issue resolved

### Paper Trading Validation

**FR6:** System can execute trading strategies in paper trading mode using PaperBroker

**FR7:** System can simulate order fills with configurable fill models (immediate, delayed, partial)

**FR8:** System can track simulated positions accurately across trading sessions

**FR9:** System can calculate PnL for paper trading positions matching live calculation logic

**FR10:** System can persist paper trading state across restarts

**FR11:** System can run paper trading sessions continuously for 24+ hours

**FR12:** System can validate order state transitions (pending → submitted → filled/cancelled)

**FR13:** System can compare paper trading behavior against live trading behavior for parity verification

### Live Trading Validation (Testnet)

**FR14:** System can connect to exchange testnets (Binance, Bybit, Hyperliquid)

**FR15:** System can submit orders to testnet and receive fill confirmations

**FR16:** System can track real positions from testnet accounts

**FR17:** System can handle WebSocket disconnections and automatically reconnect

**FR18:** System can detect and handle API rate limits gracefully

**FR19:** System can recover trading state after unexpected disconnection

**FR20:** System can validate end-to-end order flow: signal → order → fill → position update

**FR21:** System can run testnet trading sessions across multiple restarts

### Stress Testing

**FR22:** System can simulate network failures (WebSocket disconnect) during active trading

**FR23:** System can measure reconnection time after network failure

**FR24:** System can submit orders at high frequency (configurable rate) to test throughput

**FR25:** System can run continuously for extended periods (24-48 hours) without degradation

**FR26:** System can monitor memory usage during long-running sessions

**FR27:** System can detect and report state corruption or inconsistencies

**FR28:** System can simulate API error responses (500, 429, timeout) to test error handling

**FR29:** System can generate stress test reports with pass/fail status and metrics

### Lighter.xyz Broker Adapter

**FR30:** System can authenticate with Lighter.xyz API using API key and private key

**FR31:** System can submit market orders to Lighter.xyz via `/sendTx` endpoint

**FR32:** System can submit limit orders to Lighter.xyz via `/sendTx` endpoint

**FR33:** System can cancel open orders on Lighter.xyz

**FR34:** System can query current positions from Lighter.xyz via `/account` endpoint

**FR35:** System can query open orders from Lighter.xyz via `/accountActiveOrders` endpoint

**FR36:** System can query order history from Lighter.xyz via `/accountInactiveOrders` endpoint

**FR37:** System can receive fill notifications from Lighter.xyz (polling or WebSocket)

**FR38:** System can handle Lighter.xyz-specific error codes and responses

**FR39:** System can switch between Lighter.xyz testnet and mainnet via configuration

**FR40:** System can operate Lighter.xyz adapter in paper trading mode (simulated fills)

### Lighter.xyz Data Adapter

**FR41:** System can fetch list of all available trading pairs from Lighter.xyz

**FR42:** System can filter trading pairs by asset category (perpetuals, spot)

**FR43:** System can filter trading pairs by asset name/symbol pattern

**FR44:** System can fetch OHLCV candlestick data from Lighter.xyz via `/candlesticks` endpoint

**FR45:** System can fetch candlestick data for multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d)

**FR46:** System can fetch historical data with configurable date range

**FR47:** System can fetch funding rate history from Lighter.xyz via `/funding-rates` endpoint

**FR48:** System can convert Lighter.xyz data format to rustybt internal format

**FR49:** System can ingest Lighter.xyz data into rustybt bundle system

**FR50:** System can handle pagination for large data requests

### Lighter.xyz Streaming

**FR51:** System can establish real-time connection to Lighter.xyz for live data

**FR52:** System can subscribe to real-time trade updates for specified symbols

**FR53:** System can subscribe to order book updates for specified symbols

**FR54:** System can subscribe to real-time candlestick updates

**FR55:** System can handle streaming connection failures and auto-reconnect

**FR56:** System can buffer streaming data during brief disconnections

**FR57:** System can integrate Lighter.xyz streaming with existing `StreamBase` interface

### Documentation & Reporting

**FR58:** System can generate live trading setup guide for each supported platform

**FR59:** System can generate Lighter.xyz integration documentation

**FR60:** System can generate testnet setup instructions for each platform

**FR61:** System can generate audit summary report

**FR62:** System can generate stress test results report

**FR63:** System can update existing live trading documentation with audit findings

---

## Non-Functional Requirements

### Performance

**NFR1:** Order submission latency must be < 100ms from signal to API call (excluding network)

**NFR2:** WebSocket reconnection must complete within 30 seconds of disconnect detection

**NFR3:** Paper trading simulation must process orders with < 10ms overhead vs live path

**NFR4:** Memory usage must remain stable during 48-hour continuous operation (no leaks)

**NFR5:** State persistence operations must complete within 1 second

**NFR6:** Data adapter must fetch 1 year of daily OHLCV data in < 30 seconds

### Reliability

**NFR7:** System must survive and recover from any single API failure without data loss

**NFR8:** System must detect stale connections and trigger reconnection within 60 seconds

**NFR9:** System must queue orders during brief disconnections (< 30 seconds)

**NFR10:** System must log all order state transitions for audit/debug purposes

**NFR11:** Paper trading must produce deterministic results given same inputs

**NFR12:** State recovery after restart must restore exact position state

### Security

**NFR13:** API keys and private keys must never be logged or exposed in error messages

**NFR14:** Credentials must be loaded from environment variables or secure config

**NFR15:** Testnet and mainnet configurations must be clearly separated to prevent accidents

**NFR16:** All API communications must use HTTPS/WSS (encrypted transport)

**NFR17:** Private key operations (transaction signing) must use lighter-sdk's secure methods

### Integration & Compatibility

**NFR18:** Lighter.xyz adapters must follow existing adapter interface contracts exactly

**NFR19:** New adapters must integrate with existing CLI commands (`rustybt live`, `rustybt ingest`)

**NFR20:** Stress tests must be runnable via pytest with standard test discovery

**NFR21:** All new code must pass existing linting and type checking (ruff, mypy)

**NFR22:** Documentation must integrate with existing MkDocs structure

**NFR23:** Lighter.xyz data must be compatible with existing bundle/catalog system

### Maintainability

**NFR24:** Code audit findings must be documented in machine-readable format (JSON/YAML)

**NFR25:** Test scenarios must be configurable without code changes

**NFR26:** Adapter implementations must be < 500 lines each (following existing patterns)

**NFR27:** All public methods must have docstrings with type hints

---

## Summary

This PRD defines **Epic 10: Live Trading Production Readiness & Lighter.xyz Integration** for the rustybt framework.

### What We're Building

| Component | FRs | Description |
|-----------|-----|-------------|
| Code Audit | FR1-FR5 | Systematic audit of 38 live trading modules |
| Paper Trading Validation | FR6-FR13 | End-to-end paper trading verification |
| Live Trading Validation | FR14-FR21 | Testnet integration testing |
| Stress Testing | FR22-FR29 | Network, throughput, and stability tests |
| Lighter.xyz Broker | FR30-FR40 | Full trading adapter for Lighter DEX |
| Lighter.xyz Data | FR41-FR50 | OHLCV and market data ingestion |
| Lighter.xyz Streaming | FR51-FR57 | Real-time data feed integration |
| Documentation | FR58-FR63 | User guides and reports |

**Total: 63 Functional Requirements, 27 Non-Functional Requirements**

### Why It Matters

rustybt has extensive live trading infrastructure, but it hasn't been battle-tested for production use. This epic transforms rustybt from a framework with live trading capabilities into a **production-ready trading system** that users can trust with real capital.

The Lighter.xyz integration expands rustybt into the DeFi perpetuals space, connecting to a leading DEX processing billions in daily volume.

### Success Means

- All 38 live trading modules audited with zero unresolved Critical issues
- Paper and live trading validated through application-level testing
- Stress tests passing for network resilience and long-running stability
- Lighter.xyz fully integrated as broker adapter, data adapter, and streaming source
- Complete documentation for production deployment

---

## Next Steps

**Recommended workflow path:**

1. **Architecture Review** (`workflow create-architecture`)
   - Design audit process and tracking infrastructure
   - Design Lighter.xyz adapter architecture
   - Define stress testing framework

2. **Epic Breakdown** (`workflow create-epics-and-stories`)
   - Create stories for code audit phase
   - Create stories for testing infrastructure
   - Create stories for Lighter.xyz adapters
   - Create stories for documentation

---

_This PRD captures the requirements for Epic 10 - Live Trading Production Readiness & Lighter.xyz Integration._

_Created through collaborative discovery between .smirk and PM agent._
