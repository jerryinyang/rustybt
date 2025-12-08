# rustybt - Epic 10: Live Trading Production Readiness & Lighter.xyz Integration

**Author:** .smirk
**Date:** 2025-12-05
**Project Level:** High Complexity
**Target Scale:** Production-Ready Trading System

---

## Overview

This document provides the complete epic and story breakdown for **Epic 10: Live Trading Production Readiness & Lighter.xyz Integration**, decomposing the requirements from the [PRD](../prd-epic-10.md) into implementable stories.

**Living Document Notice:** This is the initial version incorporating both PRD and Architecture context.

**Context Incorporated:**
- ✅ PRD requirements (63 FRs, 27 NFRs)
- ✅ Architecture technical decisions (following HyperliquidBrokerAdapter patterns)
- ✅ Implementation Readiness validated (READY status)

## Epic Summary

| Epic | Title | FRs Covered | Stories |
|------|-------|-------------|---------|
| 10.1 | Production Code Audit & Issue Resolution | FR1-FR5 | 5 |
| 10.2 | Paper & Testnet Trading Validation | FR6-FR21 | 6 |
| 10.3 | Stress Testing & Resilience Framework | FR22-FR29 | 5 |
| 10.4 | Lighter.xyz Broker Adapter | FR30-FR40 | 6 |
| 10.5 | Lighter.xyz Data & Streaming Adapters | FR41-FR57 | 6 |
| 10.6 | Documentation & Reporting | FR58-FR63 | 4 |
| **Total** | | **63 FRs** | **32 Stories** |

---

## Functional Requirements Inventory

| FR ID | Description | Category |
|-------|-------------|----------|
| **Code Audit & Issue Management** |||
| FR1 | System can perform static analysis on all live trading module files using existing linting tools (ruff, mypy) | Code Audit |
| FR2 | System can document audit findings with severity classification (Critical/High/Medium/Low) | Code Audit |
| FR3 | System can track audit findings through resolution lifecycle (Open → In Progress → Resolved → Verified) | Code Audit |
| FR4 | System can generate audit reports summarizing findings by module and severity | Code Audit |
| FR5 | System can create regression tests for each Critical/High issue resolved | Code Audit |
| **Paper Trading Validation** |||
| FR6 | System can execute trading strategies in paper trading mode using PaperBroker | Paper Trading |
| FR7 | System can simulate order fills with configurable fill models (immediate, delayed, partial) | Paper Trading |
| FR8 | System can track simulated positions accurately across trading sessions | Paper Trading |
| FR9 | System can calculate PnL for paper trading positions matching live calculation logic | Paper Trading |
| FR10 | System can persist paper trading state across restarts | Paper Trading |
| FR11 | System can run paper trading sessions continuously for 24+ hours | Paper Trading |
| FR12 | System can validate order state transitions (pending → submitted → filled/cancelled) | Paper Trading |
| FR13 | System can compare paper trading behavior against live trading behavior for parity verification | Paper Trading |
| **Live Trading Validation (Testnet)** |||
| FR14 | System can connect to exchange testnets (Binance, Bybit, Hyperliquid) | Testnet |
| FR15 | System can submit orders to testnet and receive fill confirmations | Testnet |
| FR16 | System can track real positions from testnet accounts | Testnet |
| FR17 | System can handle WebSocket disconnections and automatically reconnect | Testnet |
| FR18 | System can detect and handle API rate limits gracefully | Testnet |
| FR19 | System can recover trading state after unexpected disconnection | Testnet |
| FR20 | System can validate end-to-end order flow: signal → order → fill → position update | Testnet |
| FR21 | System can run testnet trading sessions across multiple restarts | Testnet |
| **Stress Testing** |||
| FR22 | System can simulate network failures (WebSocket disconnect) during active trading | Stress Test |
| FR23 | System can measure reconnection time after network failure | Stress Test |
| FR24 | System can submit orders at high frequency (configurable rate) to test throughput | Stress Test |
| FR25 | System can run continuously for extended periods (24-48 hours) without degradation | Stress Test |
| FR26 | System can monitor memory usage during long-running sessions | Stress Test |
| FR27 | System can detect and report state corruption or inconsistencies | Stress Test |
| FR28 | System can simulate API error responses (500, 429, timeout) to test error handling | Stress Test |
| FR29 | System can generate stress test reports with pass/fail status and metrics | Stress Test |
| **Lighter.xyz Broker Adapter** |||
| FR30 | System can authenticate with Lighter.xyz API using API key and private key | Lighter Broker |
| FR31 | System can submit market orders to Lighter.xyz via `/sendTx` endpoint | Lighter Broker |
| FR32 | System can submit limit orders to Lighter.xyz via `/sendTx` endpoint | Lighter Broker |
| FR33 | System can cancel open orders on Lighter.xyz | Lighter Broker |
| FR34 | System can query current positions from Lighter.xyz via `/account` endpoint | Lighter Broker |
| FR35 | System can query open orders from Lighter.xyz via `/accountActiveOrders` endpoint | Lighter Broker |
| FR36 | System can query order history from Lighter.xyz via `/accountInactiveOrders` endpoint | Lighter Broker |
| FR37 | System can receive fill notifications from Lighter.xyz (polling or WebSocket) | Lighter Broker |
| FR38 | System can handle Lighter.xyz-specific error codes and responses | Lighter Broker |
| FR39 | System can switch between Lighter.xyz testnet and mainnet via configuration | Lighter Broker |
| FR40 | System can operate Lighter.xyz adapter in paper trading mode (simulated fills) | Lighter Broker |
| **Lighter.xyz Data Adapter** |||
| FR41 | System can fetch list of all available trading pairs from Lighter.xyz | Lighter Data |
| FR42 | System can filter trading pairs by asset category (perpetuals, spot) | Lighter Data |
| FR43 | System can filter trading pairs by asset name/symbol pattern | Lighter Data |
| FR44 | System can fetch OHLCV candlestick data from Lighter.xyz via `/candlesticks` endpoint | Lighter Data |
| FR45 | System can fetch candlestick data for multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d) | Lighter Data |
| FR46 | System can fetch historical data with configurable date range | Lighter Data |
| FR47 | System can fetch funding rate history from Lighter.xyz via `/funding-rates` endpoint | Lighter Data |
| FR48 | System can convert Lighter.xyz data format to rustybt internal format | Lighter Data |
| FR49 | System can ingest Lighter.xyz data into rustybt bundle system | Lighter Data |
| FR50 | System can handle pagination for large data requests | Lighter Data |
| **Lighter.xyz Streaming** |||
| FR51 | System can establish real-time connection to Lighter.xyz for live data | Lighter Stream |
| FR52 | System can subscribe to real-time trade updates for specified symbols | Lighter Stream |
| FR53 | System can subscribe to order book updates for specified symbols | Lighter Stream |
| FR54 | System can subscribe to real-time candlestick updates | Lighter Stream |
| FR55 | System can handle streaming connection failures and auto-reconnect | Lighter Stream |
| FR56 | System can buffer streaming data during brief disconnections | Lighter Stream |
| FR57 | System can integrate Lighter.xyz streaming with existing `StreamBase` interface | Lighter Stream |
| **Documentation & Reporting** |||
| FR58 | System can generate live trading setup guide for each supported platform | Documentation |
| FR59 | System can generate Lighter.xyz integration documentation | Documentation |
| FR60 | System can generate testnet setup instructions for each platform | Documentation |
| FR61 | System can generate audit summary report | Documentation |
| FR62 | System can generate stress test results report | Documentation |
| FR63 | System can update existing live trading documentation with audit findings | Documentation |

**Total: 63 Functional Requirements across 8 categories**

---

## FR Coverage Map

| Epic | FRs Covered | Description |
|------|-------------|-------------|
| 10.1 | FR1, FR2, FR3, FR4, FR5 | Code audit infrastructure and issue resolution |
| 10.2 | FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR21 | Paper trading and testnet validation |
| 10.3 | FR22, FR23, FR24, FR25, FR26, FR27, FR28, FR29 | Stress testing and resilience validation |
| 10.4 | FR30, FR31, FR32, FR33, FR34, FR35, FR36, FR37, FR38, FR39, FR40 | Lighter.xyz broker adapter |
| 10.5 | FR41, FR42, FR43, FR44, FR45, FR46, FR47, FR48, FR49, FR50, FR51, FR52, FR53, FR54, FR55, FR56, FR57 | Lighter.xyz data and streaming adapters |
| 10.6 | FR58, FR59, FR60, FR61, FR62, FR63 | Documentation and reporting |

---

## Epic 10.1: Production Code Audit & Issue Resolution

**Goal:** Systematically audit all 38 live trading modules for correctness, document findings with severity classification, and resolve Critical/High issues with regression tests.

**User Value:** Confidence that the live trading infrastructure has been professionally reviewed and hardened for production use.

**FRs Covered:** FR1, FR2, FR3, FR4, FR5

---

### Story 10.1.1: Create Audit Infrastructure & Findings Schema

As a **developer**,
I want **a structured audit infrastructure with YAML-based findings storage**,
So that **audit findings are machine-readable, trackable, and version-controlled**.

**Acceptance Criteria:**

**Given** the audit infrastructure does not exist
**When** I run the audit setup script
**Then** the following structure is created:
- `tests/live/audit/` directory with `__init__.py`, `conftest.py`
- `tests/live/audit/findings/` directory for YAML findings files
- Findings schema with fields: id, module, line, severity (Critical/High/Medium/Low), category, description, recommendation, status (Open/In Progress/Resolved/Verified), found_by, found_at, resolved_at, regression_test

**And** a sample findings file demonstrates the schema
**And** pytest fixtures for loading/validating findings are available

**Prerequisites:** None (first story)

**Technical Notes:**
- Follow Pattern 5 from Architecture (Audit Finding Classification)
- Finding IDs use format: `AUDIT-{MODULE_CODE}{NUMBER}` (E=Engine, B=Brokers, S=Streaming, O=OrderManager, R=Reconciler, C=CircuitBreakers)
- Use PyYAML >=6.0 for YAML parsing
- Store in `tests/live/audit/findings/{module}_findings.yaml`

---

### Story 10.1.2: Static Analysis Audit of Live Trading Core

As a **developer**,
I want **static analysis (ruff, mypy) run against all live trading core modules**,
So that **type errors, linting issues, and potential bugs are identified**.

**Acceptance Criteria:**

**Given** the audit infrastructure from Story 10.1.1 exists
**When** I run static analysis on the following modules:
- `rustybt/live/engine.py`
- `rustybt/live/order_manager.py`
- `rustybt/live/state_manager.py`
- `rustybt/live/strategy_executor.py`
- `rustybt/live/reconciler.py`
- `rustybt/live/circuit_breakers.py`
- `rustybt/live/data_feed.py`
**Then** all issues are captured in `core_findings.yaml`
**And** each finding has severity classification based on impact
**And** a summary report shows counts by module and severity

**And** zero new ruff errors are introduced (existing violations documented)
**And** zero new mypy errors are introduced (existing violations documented)

**Prerequisites:** Story 10.1.1

**Technical Notes:**
- Run `ruff check rustybt/live/*.py --output-format=json` for machine-parseable output
- Run `mypy rustybt/live/*.py --show-error-codes` for type checking
- Focus areas per module as defined in PRD Audit Scope tables
- Classify severity: Critical (data loss/financial), High (incorrect behavior), Medium (edge cases), Low (style/minor)

---

### Story 10.1.3: Static Analysis Audit of Broker & Streaming Adapters

As a **developer**,
I want **static analysis run against all broker adapters and streaming modules**,
So that **exchange-specific issues and WebSocket handling problems are identified**.

**Acceptance Criteria:**

**Given** the audit infrastructure exists
**When** I run static analysis on:
- `rustybt/live/brokers/base.py`, `ccxt_adapter.py`, `binance_adapter.py`, `bybit_adapter.py`, `hyperliquid_adapter.py`, `ib_adapter.py`, `paper_broker.py`
- `rustybt/live/streaming/base.py`, `ccxt_stream.py`, `binance_stream.py`, `bybit_stream.py`, `hyperliquid_stream.py`, `bar_buffer.py`
**Then** findings are captured in `brokers_findings.yaml` and `streaming_findings.yaml`
**And** each finding includes the specific exchange/adapter affected
**And** reconnection logic and error handling paths are specifically reviewed

**Prerequisites:** Story 10.1.1

**Technical Notes:**
- Pay special attention to async/await patterns in streaming modules
- Check for proper exception handling around WebSocket operations
- Verify rate limiting implementation in each adapter
- Check credential handling never logs sensitive data

---

### Story 10.1.4: Manual Code Review & Control Flow Analysis

As a **developer**,
I want **manual code review focused on control flow, state machines, and concurrency**,
So that **logic errors not caught by static analysis are identified**.

**Acceptance Criteria:**

**Given** static analysis audits are complete (Stories 10.1.2, 10.1.3)
**When** I perform manual code review focusing on:
- Order state machine transitions in `order_manager.py`
- State persistence/recovery in `state_manager.py`
- Reconnection logic in streaming modules
- Circuit breaker trigger conditions
- Concurrency patterns (async/await, locks, race conditions)
**Then** findings are added to respective YAML files with category "manual_review"
**And** each finding includes specific line numbers and code snippets
**And** Critical/High findings have detailed reproduction steps

**Prerequisites:** Stories 10.1.2, 10.1.3

**Technical Notes:**
- State machine verification: Ensure all order transitions are valid (pending→submitted→filled/cancelled)
- Concurrency review: Check for shared state mutations without locks
- Error path analysis: Verify all exception handlers preserve state consistency
- Security review: Confirm no credential exposure in logs or error messages

---

### Story 10.1.5: Critical/High Issue Resolution & Regression Tests

As a **developer**,
I want **all Critical and High severity findings resolved with regression tests**,
So that **the codebase is production-ready and issues won't regress**.

**Acceptance Criteria:**

**Given** audit findings exist from Stories 10.1.2-10.1.4
**When** I resolve each Critical/High finding
**Then** the fix is implemented in the appropriate module
**And** a regression test is created in `tests/live/audit/test_{module}_regressions.py`
**And** the finding YAML is updated: status="Resolved", resolved_at=date, regression_test=test_path
**And** all regression tests pass

**And** an audit summary report is generated showing:
- Total findings by severity
- Resolution status
- Remaining Medium/Low items (documented for future)

**Prerequisites:** Stories 10.1.2, 10.1.3, 10.1.4

**Technical Notes:**
- Each regression test should reproduce the original bug scenario
- Tests should verify the fix prevents the issue
- Medium/Low findings may be deferred but must be documented
- Generate report using `pytest --collect-only tests/live/audit/` + findings YAML aggregation

---

## Epic 10.2: Paper & Testnet Trading Validation

**Goal:** Validate that paper trading accurately simulates live trading behavior, and that testnet integration works correctly for at least one exchange.

**User Value:** Confidence that paper trading results are trustworthy and that the system can successfully trade on real exchange APIs.

**FRs Covered:** FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR21

---

### Story 10.2.1: Paper Trading Execution Test Harness

As a **developer**,
I want **an end-to-end test harness for paper trading execution**,
So that **I can validate strategy execution, order fills, and position tracking**.

**Acceptance Criteria:**

**Given** a test strategy that generates known signals
**When** I run the strategy in paper trading mode via `PaperBroker`
**Then** orders are submitted and filled according to the configured fill model
**And** positions are tracked accurately (entry price, size, direction)
**And** PnL calculations match expected values for the test scenario
**And** order state transitions follow: pending → submitted → filled/cancelled

**Given** the fill model is set to "immediate"
**When** a market order is submitted
**Then** the fill occurs at the current simulated price within the same tick

**Given** the fill model is set to "delayed"
**When** a market order is submitted
**Then** the fill occurs after a configurable delay (default 100ms)

**Prerequisites:** Epic 10.1 complete (audit findings resolved)

**Technical Notes:**
- Create `tests/live/paper/test_paper_execution.py`
- Use a deterministic test strategy with known signal patterns
- Test both long and short positions
- Verify Decimal precision for all financial calculations (FR9)
- Test location: `tests/live/paper/`

---

### Story 10.2.2: Paper Trading State Persistence & Long-Running Stability

As a **developer**,
I want **paper trading state to persist across restarts and run stably for 24+ hours**,
So that **users can trust paper trading for extended strategy validation**.

**Acceptance Criteria:**

**Given** a paper trading session with open positions
**When** the session is stopped and restarted
**Then** positions are restored exactly as before (size, entry price, unrealized PnL)
**And** order history is preserved
**And** the session continues from the restored state

**Given** a paper trading session running continuously
**When** 24 hours have elapsed
**Then** memory usage remains stable (no leaks, <10% growth)
**And** no state corruption occurs
**And** position tracking remains accurate
**And** all order state transitions are logged for audit

**Prerequisites:** Story 10.2.1

**Technical Notes:**
- State persistence uses `state_manager.py` - verify it works for paper mode
- Long-running test should use pytest with `--duration=86400` (24h) or pytest-timeout
- Monitor memory with `memory_profiler` or `tracemalloc`
- Create `tests/live/paper/test_paper_stability.py`

---

### Story 10.2.3: Paper vs Live Parity Verification

As a **developer**,
I want **to verify paper trading behavior matches live trading behavior**,
So that **paper trading results are a reliable proxy for live performance**.

**Acceptance Criteria:**

**Given** identical strategy configurations
**When** the same signals are processed by both PaperBroker and a mock live broker
**Then** order submission calls have identical parameters (asset, amount, type, price)
**And** position calculations use the same logic
**And** PnL calculations produce identical results for the same fill prices
**And** state transitions follow the same state machine

**And** a parity report documents any intentional differences (e.g., paper has no real fills)

**Prerequisites:** Story 10.2.1

**Technical Notes:**
- Create `tests/live/paper/test_paper_parity.py`
- Use mocks to capture calls to both broker types
- Compare call signatures and return value processing
- Document expected differences (paper simulates fills, live receives them)

---

### Story 10.2.4: Testnet Connection & Basic Order Flow

As a **developer**,
I want **to validate testnet connectivity and basic order submission for at least one exchange**,
So that **I can prove the system works with real exchange APIs**.

**Acceptance Criteria:**

**Given** valid testnet credentials for Hyperliquid (primary) or Binance/Bybit (fallback)
**When** I connect to the exchange testnet
**Then** connection is established successfully
**And** account information is retrieved (balance, existing positions)

**Given** a connected testnet session
**When** I submit a small limit order (e.g., 0.001 BTC at a price unlikely to fill)
**Then** the order is accepted by the exchange
**And** the order appears in open orders
**And** the order can be cancelled successfully

**Given** a connected testnet session
**When** I submit a small market order
**Then** the order is filled
**And** the fill is received and processed
**And** position is updated accordingly

**Prerequisites:** Story 10.2.1, Testnet credentials configured

**Technical Notes:**
- Create `tests/live/testnet/test_hyperliquid_testnet.py` (primary)
- Use environment variables for credentials: `HYPERLIQUID_TESTNET_API_KEY`, etc.
- Skip tests if credentials not available (pytest.mark.skipif)
- Use minimal order sizes to avoid testnet fund depletion
- Verify rate limit handling during order submission

---

### Story 10.2.5: Testnet Reconnection & State Recovery

As a **developer**,
I want **to validate WebSocket reconnection and state recovery after disconnection**,
So that **the system is resilient to network failures**.

**Acceptance Criteria:**

**Given** an active testnet trading session with open positions
**When** the WebSocket connection is forcibly disconnected
**Then** reconnection is attempted with exponential backoff
**And** reconnection succeeds within 30 seconds (NFR2)
**And** subscriptions are restored automatically
**And** position state is reconciled with exchange

**Given** a disconnection during an active order
**When** reconnection completes
**Then** order status is queried and synced
**And** any missed fills are processed
**And** local state matches exchange state

**Prerequisites:** Story 10.2.4

**Technical Notes:**
- Create `tests/live/testnet/test_testnet_reconnection.py`
- Simulate disconnect by closing WebSocket connection
- Verify exponential backoff: delay = min(base * 2^attempts, max_delay)
- Test with Hyperliquid testnet (uses WebSocket for market data)
- Verify `reconciler.py` correctly syncs state

---

### Story 10.2.6: End-to-End Order Flow Validation

As a **developer**,
I want **to validate the complete order flow from strategy signal to position update**,
So that **I can confirm the entire trading pipeline works correctly**.

**Acceptance Criteria:**

**Given** a test strategy running on testnet
**When** the strategy generates a BUY signal
**Then** the signal is processed by `strategy_executor.py`
**And** an order is created by `order_manager.py`
**And** the order is submitted via the broker adapter
**And** the fill is received via streaming or polling
**And** the position is updated in `state_manager.py`
**And** all state transitions are logged

**Given** the same flow for a SELL signal
**Then** the position is reduced or closed
**And** PnL is calculated correctly

**Prerequisites:** Stories 10.2.4, 10.2.5

**Technical Notes:**
- Create `tests/live/testnet/test_e2e_order_flow.py`
- Use a simple test strategy that generates signals on schedule
- Verify the complete chain: Engine → StrategyExecutor → OrderManager → Broker → Fill → StateManager
- Include timing measurements (NFR1: < 100ms signal to API call)
- Test across restarts (FR21)

---

## Epic 10.3: Stress Testing & Resilience Framework

**Goal:** Build a stress testing framework that validates system resilience under network failures, high load, and extended operation.

**User Value:** Confidence that the trading system won't fail under stress conditions and can recover gracefully from failures.

**FRs Covered:** FR22, FR23, FR24, FR25, FR26, FR27, FR28, FR29

---

### Story 10.3.1: Stress Testing Infrastructure & Scenario Configuration

As a **developer**,
I want **a stress testing infrastructure with configurable YAML scenarios**,
So that **I can run repeatable stress tests with different parameters**.

**Acceptance Criteria:**

**Given** the stress testing infrastructure does not exist
**When** I create the stress test framework
**Then** the following structure is created:
- `tests/live/stress/` directory with `__init__.py`, `conftest.py`
- `tests/live/stress/scenarios/` for YAML scenario definitions
- Scenario schema with: name, type (network/throughput/long_running/error), duration, parameters, success_criteria

**And** pytest fixtures for loading and executing scenarios are available
**And** a sample scenario file demonstrates the schema
**And** stress test results are logged in structured JSON format

**Prerequisites:** Epic 10.1 complete

**Technical Notes:**
- Use pytest-asyncio for async stress test execution
- Scenarios should be parameterizable (duration, rate, error types)
- Results include: start_time, end_time, pass/fail, metrics (reconnection_time, memory_usage, etc.)
- Create `tests/live/stress/conftest.py` with scenario loading fixtures

---

### Story 10.3.2: Network Failure & Reconnection Tests

As a **developer**,
I want **stress tests that simulate network failures and measure reconnection behavior**,
So that **I can validate system resilience to network issues**.

**Acceptance Criteria:**

**Given** an active trading session (paper or testnet)
**When** a network failure is simulated (WebSocket disconnect)
**Then** the system detects the disconnect within 60 seconds (NFR8)
**And** reconnection is attempted with exponential backoff
**And** reconnection succeeds within 30 seconds (NFR2)
**And** reconnection time is measured and logged

**Given** multiple consecutive network failures
**When** failures exceed the circuit breaker threshold
**Then** the circuit breaker trips
**And** the system enters a safe state
**And** recovery is attempted after cooldown period

**And** a stress test report includes:
- Total disconnections simulated
- Average reconnection time
- Max reconnection time
- Circuit breaker trips (if any)
- Pass/fail status

**Prerequisites:** Story 10.3.1

**Technical Notes:**
- Create `tests/live/stress/test_network_resilience.py`
- Simulate disconnect by closing WebSocket or blocking network
- Test scenarios: single disconnect, rapid disconnects, disconnect during order
- Verify queued orders are handled during disconnect (NFR9)
- Use mock broker for consistent testing

---

### Story 10.3.3: High-Frequency Order Throughput Tests

As a **developer**,
I want **stress tests that submit orders at high frequency**,
So that **I can validate order processing throughput and rate limit handling**.

**Acceptance Criteria:**

**Given** a paper trading session
**When** I submit orders at 10 orders/second for 60 seconds
**Then** all orders are tracked correctly in `order_manager.py`
**And** no orders are lost or duplicated
**And** order submission latency remains < 100ms (NFR1)

**Given** rate limits are approached
**When** submission rate exceeds 80% of limit
**Then** a warning is logged
**And** the system throttles submissions (not rejects)

**Given** rate limits are exceeded
**When** an order is rate-limited (429 response)
**Then** the system backs off gracefully
**And** the order is retried after delay
**And** no crash or state corruption occurs

**Prerequisites:** Story 10.3.1

**Technical Notes:**
- Create `tests/live/stress/test_order_throughput.py`
- Use paper broker for consistent, repeatable tests
- Measure: orders/second achieved, latency percentiles (p50, p95, p99)
- Verify token bucket rate limiting from Architecture Pattern 2
- Test with burst patterns (10 orders in 1 second)

---

### Story 10.3.4: Long-Running Stability & Memory Monitoring

As a **developer**,
I want **stress tests that run for 24-48 hours continuously**,
So that **I can validate long-term stability and detect memory leaks**.

**Acceptance Criteria:**

**Given** a paper trading session with continuous strategy execution
**When** the session runs for 24 hours
**Then** the system remains responsive
**And** memory usage remains stable (< 10% growth, no leaks)
**And** state remains consistent (no corruption)
**And** all positions are tracked correctly

**Given** the same session runs for 48 hours
**When** memory is sampled at intervals
**Then** memory growth is linear or flat (not exponential)
**And** no resource exhaustion occurs

**And** a stability report includes:
- Runtime duration
- Memory usage over time (snapshots every hour)
- Order count processed
- Error count
- State integrity verification
- Pass/fail status

**Prerequisites:** Story 10.3.1

**Technical Notes:**
- Create `tests/live/stress/test_long_running.py`
- Use `tracemalloc` or `memory_profiler` for memory tracking
- Sample memory every hour, log to JSON
- Verify state consistency by comparing position calculations
- Support pytest `--duration` parameter for configurable runtime
- This test should be marked as slow and run separately

---

### Story 10.3.5: API Error Simulation & Stress Test Reporting

As a **developer**,
I want **stress tests that simulate API errors and generate comprehensive reports**,
So that **I can validate error handling and track stress test results over time**.

**Acceptance Criteria:**

**Given** API error simulation capability
**When** I simulate various error responses:
- 500 Internal Server Error
- 429 Rate Limit Exceeded
- 408 Request Timeout
- Connection refused
**Then** each error is handled gracefully
**And** appropriate retry logic is applied
**And** no crash or state corruption occurs
**And** errors are logged with context

**Given** all stress tests complete
**When** I generate the stress test report
**Then** the report includes:
- Test date and duration
- Scenarios executed with parameters
- Pass/fail status for each scenario
- Metrics: reconnection times, throughput, memory usage
- Error counts by type
- Overall pass/fail verdict

**And** the report is saved to `docs/live-trading/stress-test-report.md`

**Prerequisites:** Stories 10.3.2, 10.3.3, 10.3.4

**Technical Notes:**
- Create `tests/live/stress/test_api_errors.py`
- Use mock responses to simulate specific error codes
- Verify retry logic: exponential backoff, max retries
- Report generation: aggregate results from all stress test runs
- Consider using pytest-html or custom JSON → Markdown conversion

---

## Epic 10.4: Lighter.xyz Broker Adapter

**Goal:** Implement a complete broker adapter for Lighter.xyz DEX, enabling order submission, position tracking, and fill notifications.

**User Value:** Can trade perpetual futures on Lighter.xyz directly from rustybt, accessing a leading DeFi DEX with $1-2B daily volume.

**FRs Covered:** FR30, FR31, FR32, FR33, FR34, FR35, FR36, FR37, FR38, FR39, FR40

---

### Story 10.4.1: Lighter.xyz Broker Adapter Skeleton & Authentication

As a **developer**,
I want **a LighterBrokerAdapter class that authenticates with Lighter.xyz API**,
So that **I can establish secure connections for trading**.

**Acceptance Criteria:**

**Given** the `lighter-sdk` package is installed
**When** I create a `LighterBrokerAdapter` instance with valid credentials
**Then** private key is loaded securely via priority order:
  1. Environment variable `LIGHTER_PRIVATE_KEY`
  2. Encrypted keystore file + encryption key
  3. Direct parameter (logs warning)
**And** the adapter validates the private key format (64 hex characters)
**And** the wallet address is derived and logged (masked)

**Given** valid credentials
**When** I call `connect()`
**Then** connection to Lighter.xyz API is established
**And** account info is retrieved to verify credentials
**And** testnet/mainnet URL is selected based on `testnet` parameter (default: testnet)

**Given** invalid or missing credentials
**When** I attempt to connect
**Then** a `LighterKeyError` is raised with helpful message

**Prerequisites:** Epic 10.1 complete, `lighter-sdk` installed

**Technical Notes:**
- Create `rustybt/live/brokers/lighter_adapter.py`
- Follow HyperliquidBrokerAdapter pattern exactly (ADR-001)
- Implement Pattern 1 (Private Key Security) from Architecture
- Use Fernet encryption for keystore (cryptography >=41.0)
- Default to testnet (ADR-003): `testnet=True`
- API URLs from Architecture: mainnet `https://mainnet.zklighter.elliot.ai/`, testnet `https://testnet.zklighter.elliot.ai/`

---

### Story 10.4.2: Order Submission (Market & Limit)

As a **developer**,
I want **to submit market and limit orders to Lighter.xyz**,
So that **users can execute trades on the platform**.

**Acceptance Criteria:**

**Given** a connected `LighterBrokerAdapter`
**When** I call `submit_order(asset, amount, "market")`
**Then** a transaction is signed with the private key
**And** the transaction is submitted via POST `/sendTx`
**And** the response is parsed for order ID
**And** the order ID is returned

**Given** a connected adapter
**When** I call `submit_order(asset, amount, "limit", limit_price=price)`
**Then** a limit order transaction is created with the specified price
**And** the order is submitted and order ID returned

**Given** any order submission
**When** rate limits are checked before submission
**Then** the order waits if rate limit would be exceeded (Pattern 2)
**And** submission proceeds when under limit

**Given** an order submission fails
**When** Lighter.xyz returns an error
**Then** a `LighterOrderRejectError` is raised with error details
**And** the error is logged with order context (no sensitive data)

**Prerequisites:** Story 10.4.1

**Technical Notes:**
- Use `lighter-sdk` for transaction signing and submission
- Implement rate limiting: 600 requests/minute, 20 orders/second per symbol
- Log all submissions with structured logging (Pattern from Architecture)
- Handle zk-proof verification delays (orders may not confirm immediately)
- Amount is signed: positive = buy, negative = sell

---

### Story 10.4.3: Order Cancellation & Query Operations

As a **developer**,
I want **to cancel orders and query order status from Lighter.xyz**,
So that **users can manage their orders**.

**Acceptance Criteria:**

**Given** an open order on Lighter.xyz
**When** I call `cancel_order(order_id)`
**Then** a cancel transaction is signed and submitted
**And** the order is cancelled on the exchange
**And** success is confirmed

**Given** a connected adapter
**When** I call `get_open_orders()`
**Then** GET `/accountActiveOrders` is called
**And** a list of open orders is returned with: order_id, symbol, side, type, quantity, price, status

**Given** a connected adapter
**When** I call `get_order_history()` or query for a specific order
**Then** GET `/accountInactiveOrders` is called
**And** filled/cancelled orders are returned with fill details

**Prerequisites:** Story 10.4.2

**Technical Notes:**
- Cancel uses POST `/sendTx` with cancel transaction type
- Parse Lighter.xyz order response format into internal format
- Handle pagination if order history is large
- Include order status mapping: Lighter status → rustybt OrderStatus enum

---

### Story 10.4.4: Position & Account Queries

As a **developer**,
I want **to query positions and account information from Lighter.xyz**,
So that **the system can track portfolio state**.

**Acceptance Criteria:**

**Given** a connected adapter
**When** I call `get_positions()`
**Then** GET `/account` is called
**And** positions are returned with: symbol, size (signed), entry_price, mark_price, unrealized_pnl, leverage
**And** positions use Decimal precision for financial values

**Given** a connected adapter
**When** I call `get_account_info()`
**Then** account balance and margin information is returned
**And** values are converted to Decimal

**Given** position data from Lighter.xyz
**When** the data is processed
**Then** it matches the `LighterPosition` dataclass from Architecture
**And** sign convention is preserved (positive=long, negative=short)

**Prerequisites:** Story 10.4.1

**Technical Notes:**
- Use Decimal for all financial values (required by rustybt)
- Map Lighter.xyz field names to rustybt conventions
- Verify leverage and margin calculations

---

### Story 10.4.5: Fill Notifications & Paper Trading Mode

As a **developer**,
I want **to receive fill notifications and support paper trading mode**,
So that **live and simulated trading are both supported**.

**Acceptance Criteria:**

**Given** a connected adapter in live mode
**When** an order is filled on Lighter.xyz
**Then** the fill notification is received (via polling or WebSocket)
**And** the fill is processed with: order_id, fill_price, fill_quantity, timestamp
**And** the fill is passed to the order manager

**Given** an adapter configured with `paper_mode=True`
**When** an order is submitted
**Then** the order is NOT sent to Lighter.xyz
**And** a simulated fill is generated locally
**And** positions are updated based on simulated fills
**And** all paper trades are logged for review

**Given** paper mode
**When** market data is needed for fill simulation
**Then** real market prices are fetched from Lighter.xyz (or streaming)
**And** fills use realistic prices

**Prerequisites:** Stories 10.4.2, 10.4.4

**Technical Notes:**
- Fill notification: Poll `/accountInactiveOrders` or use WebSocket if available
- Paper mode reuses the `PaperBroker` pattern but with Lighter.xyz prices
- Consider using streaming adapter (Epic 10.5) for real-time prices in paper mode
- Log paper trades separately from live trades

---

### Story 10.4.6: Error Handling, Configuration & Integration Tests

As a **developer**,
I want **comprehensive error handling and integration tests for the Lighter.xyz adapter**,
So that **the adapter is production-ready and testable**.

**Acceptance Criteria:**

**Given** various Lighter.xyz error responses
**When** errors occur (rate limit, invalid order, network error, etc.)
**Then** appropriate exception types are raised:
  - `LighterConnectionError` for connection failures
  - `LighterOrderRejectError` for order rejections
  - `LighterRateLimitError` for rate limit exceeded
**And** errors are logged with context (order_id, symbol, operation)
**And** sensitive data is never logged

**Given** configuration via YAML
**When** the adapter is initialized
**Then** testnet/mainnet is selected correctly
**And** environment variable names are correct for each mode
**And** a warning is logged when using mainnet

**Given** the complete adapter implementation
**When** I run integration tests against testnet
**Then** all operations are tested: connect, submit_order, cancel_order, get_positions, get_open_orders
**And** tests pass on Lighter.xyz testnet
**And** tests are skipped if credentials unavailable

**Prerequisites:** Stories 10.4.1-10.4.5

**Technical Notes:**
- Create `tests/live/lighter/test_lighter_broker.py`
- Follow error hierarchy from Architecture (Consistency Rules)
- Test both testnet and paper mode
- Mark integration tests appropriately for CI (skip without creds)
- Create mock tests for error handling scenarios

---

## Epic 10.5: Lighter.xyz Data & Streaming Adapters

**Goal:** Implement data adapter for historical OHLCV ingestion and streaming adapter for real-time market data from Lighter.xyz.

**User Value:** Can backtest strategies using Lighter.xyz historical data and receive real-time prices for live trading.

**FRs Covered:** FR41-FR57

---

### Story 10.5.1: Lighter.xyz Data Adapter Skeleton & Asset Discovery

As a **developer**,
I want **a LighterDataAdapter that discovers available trading pairs**,
So that **users can see what assets are available on Lighter.xyz**.

**Acceptance Criteria:**

**Given** the data adapter does not exist
**When** I create `LighterDataAdapter`
**Then** it extends `BaseDataAdapter` from `rustybt/data/adapters/base.py`
**And** implements the required interface methods

**Given** a connected data adapter
**When** I call `get_available_assets()`
**Then** all tradeable pairs are returned from Lighter.xyz
**And** each asset includes: symbol, category (perpetual/spot), base_currency, quote_currency

**Given** a connected adapter
**When** I call `get_assets_by_category("perpetual")`
**Then** only perpetual futures pairs are returned

**When** I call `get_assets_by_pattern("BTC*")`
**Then** only BTC-related pairs are returned

**Prerequisites:** Epic 10.1 complete

**Technical Notes:**
- Create `rustybt/data/adapters/lighter_adapter.py`
- Follow existing data adapter patterns (yfinance, Polygon, CCXT)
- Parse Lighter.xyz asset metadata format
- Cache asset list with TTL (refresh every hour)

---

### Story 10.5.2: OHLCV Data Fetching & Timeframe Support

As a **developer**,
I want **to fetch OHLCV candlestick data from Lighter.xyz**,
So that **users can backtest strategies with historical data**.

**Acceptance Criteria:**

**Given** a connected data adapter
**When** I call `fetch(symbols=["BTC-PERP"], start_date, end_date, resolution="1h")`
**Then** GET `/candlesticks` is called with appropriate parameters
**And** OHLCV data is returned as Polars DataFrame
**And** schema matches `LIGHTER_OHLCV_SCHEMA` from Architecture

**Given** multiple timeframes requested
**When** I fetch data for 1m, 5m, 15m, 1h, 4h, 1d resolutions
**Then** all timeframes are supported
**And** data is correctly aggregated/returned per timeframe

**Given** a large date range
**When** data exceeds pagination limits
**Then** pagination is handled automatically
**And** all data is fetched and combined

**Given** fetched data
**When** validated
**Then** `validate(df)` returns True for well-formed data
**And** timestamps are in chronological order
**And** no missing required fields

**Prerequisites:** Story 10.5.1

**Technical Notes:**
- Use Polars for data processing (required by rustybt)
- Decimal precision for OHLCV values (precision=18, scale=8)
- Handle Lighter.xyz timestamp format (convert to datetime)
- Implement automatic pagination with configurable page size
- Performance target: 1 year daily data in < 30 seconds (NFR6)

---

### Story 10.5.3: Data Standardization & Bundle Integration

As a **developer**,
I want **Lighter.xyz data converted to rustybt format and ingested into the bundle system**,
So that **data is usable for backtesting**.

**Acceptance Criteria:**

**Given** raw data from Lighter.xyz
**When** I call `standardize(df)`
**Then** data is converted to rustybt internal format
**And** column names match expected schema
**And** data types are correct (Decimal for prices, Datetime for timestamps)

**Given** standardized data
**When** I ingest into the bundle system
**Then** data is saved to Parquet format
**And** bundle metadata is updated
**And** data is queryable via the catalog

**Given** funding rate data requested
**When** I call `get_funding_rates(symbol)`
**Then** GET `/funding-rates` is called
**And** funding rate history is returned with: timestamp, symbol, funding_rate

**Prerequisites:** Story 10.5.2

**Technical Notes:**
- Follow existing bundle ingestion patterns
- Funding rates are stored separately from OHLCV
- Verify integration with `rustybt ingest` CLI command
- Create `tests/live/lighter/test_lighter_data.py`

---

### Story 10.5.4: Lighter.xyz WebSocket Streaming Adapter

As a **developer**,
I want **a LighterWebSocketAdapter for real-time market data streaming**,
So that **live trading has access to real-time prices**.

**Acceptance Criteria:**

**Given** the streaming adapter does not exist
**When** I create `LighterWebSocketAdapter`
**Then** it extends `BaseWebSocketAdapter` from `rustybt/live/streaming/base.py`
**And** implements the required interface methods

**Given** a connected streaming adapter
**When** I call `connect()`
**Then** WebSocket connection is established to Lighter.xyz
**And** connection success is logged

**Given** a connected adapter
**When** I call `subscribe(symbols=["BTC-PERP"], channels=["trades"])`
**Then** subscription request is sent
**And** real-time trade updates are received
**And** messages are parsed to `TickData` format

**Given** trade messages received
**When** `parse_message(raw_message)` is called
**Then** `TickData` is returned with: symbol, price, volume, timestamp
**And** None is returned for non-trade messages

**Prerequisites:** Epic 10.1 complete

**Technical Notes:**
- Create `rustybt/live/streaming/lighter_stream.py`
- Use websockets >=12.0 for WebSocket connection
- Follow existing streaming patterns (binance_stream, hyperliquid_stream)
- Implement heartbeat/ping handling if required by Lighter.xyz

---

### Story 10.5.5: Streaming Subscriptions & Bar Aggregation

As a **developer**,
I want **to subscribe to various data channels and aggregate to OHLCV bars**,
So that **the live trading engine receives consistent data**.

**Acceptance Criteria:**

**Given** a connected streaming adapter
**When** I subscribe to orderbook channel
**Then** order book updates are received
**And** best bid/ask are available

**Given** trade stream active
**When** trades are received
**Then** the `BarBuffer` aggregates trades into OHLCV bars
**And** bars are emitted at the configured interval (e.g., 1m)

**Given** candlestick subscription available
**When** I subscribe to candlesticks
**Then** real-time candle updates are received
**And** bar data is parsed correctly

**Given** streaming to live trading engine
**When** bars are ready
**Then** `get_next_market_data()` returns the bar
**And** the engine processes it for strategy execution

**Prerequisites:** Story 10.5.4

**Technical Notes:**
- Integrate with existing `bar_buffer.py`
- Trade aggregation: collect trades, emit bar at interval boundary
- Verify timestamp alignment for bar boundaries
- Test multiple symbol subscriptions simultaneously

---

### Story 10.5.6: Streaming Resilience & Integration Tests

As a **developer**,
I want **streaming to handle disconnections gracefully and pass integration tests**,
So that **real-time data is reliable for live trading**.

**Acceptance Criteria:**

**Given** an active streaming connection
**When** the connection is lost
**Then** reconnection is attempted with exponential backoff (Pattern 3)
**And** reconnection succeeds within 30 seconds
**And** subscriptions are automatically restored

**Given** brief disconnection (< 30 seconds)
**When** data buffering is enabled
**Then** data during disconnection is buffered (if possible)
**And** buffered data is processed after reconnection

**Given** reconnection after disconnect
**When** subscriptions are restored
**Then** no duplicate data is delivered
**And** sequence numbers are handled correctly (if applicable)

**Given** complete streaming implementation
**When** I run integration tests
**Then** all operations are tested: connect, subscribe (trades, orderbook, candles), parse, reconnect
**And** tests pass or skip appropriately
**And** mock tests cover error scenarios

**Prerequisites:** Stories 10.5.4, 10.5.5

**Technical Notes:**
- Create `tests/live/lighter/test_lighter_stream.py`
- Reconnection follows Pattern 3 from Architecture
- Buffer size should be configurable
- Test with mock WebSocket for deterministic behavior
- Integration tests require Lighter.xyz connectivity

---

## Epic 10.6: Documentation & Reporting

**Goal:** Create comprehensive documentation for live trading setup, Lighter.xyz integration, testnet usage, and generate audit/stress test reports.

**User Value:** Can learn how to use all new capabilities and understand the audit/stress test results.

**FRs Covered:** FR58, FR59, FR60, FR61, FR62, FR63

---

### Story 10.6.1: Live Trading Setup Guide

As a **user**,
I want **a comprehensive live trading setup guide**,
So that **I can configure and run live trading on supported platforms**.

**Acceptance Criteria:**

**Given** a user wants to set up live trading
**When** they read the setup guide
**Then** they can:
- Install required dependencies
- Configure credentials securely (environment variables, encrypted keystores)
- Select and configure a broker adapter (Binance, Bybit, Hyperliquid, Lighter.xyz)
- Run a paper trading session
- Run a testnet trading session
- Transition to mainnet (with safety warnings)

**And** the guide includes:
- Step-by-step instructions for each platform
- Code examples for configuration
- Troubleshooting common issues
- Security best practices (credential handling, testnet first)
- Links to platform-specific documentation

**Prerequisites:** Epics 10.1-10.5 complete

**Technical Notes:**
- Create `docs/live-trading/setup-guide.md`
- Include platform-specific subsections
- Emphasize security (never commit credentials, use env vars)
- Include example YAML configurations
- Follow existing rustybt documentation style

---

### Story 10.6.2: Lighter.xyz Integration Documentation

As a **user**,
I want **dedicated documentation for Lighter.xyz integration**,
So that **I can understand the platform-specific details and capabilities**.

**Acceptance Criteria:**

**Given** a user wants to trade on Lighter.xyz
**When** they read the Lighter.xyz documentation
**Then** they understand:
- What Lighter.xyz is (zk-rollup DEX, perpetuals, spot)
- How to obtain testnet/mainnet credentials
- Broker adapter configuration options
- Data adapter usage for backtesting
- Streaming adapter for live data
- Paper trading mode on Lighter.xyz

**And** the documentation includes:
- API endpoint reference (from Architecture)
- Supported order types and timeframes
- Rate limits and best practices
- Error codes and troubleshooting
- Example strategies using Lighter.xyz data

**Prerequisites:** Epics 10.4, 10.5 complete

**Technical Notes:**
- Create `docs/live-trading/lighter-integration.md`
- Reference Architecture document for technical details
- Include code snippets for common operations
- Link to Lighter.xyz official documentation

---

### Story 10.6.3: Testnet Setup Instructions

As a **user**,
I want **testnet setup instructions for each supported platform**,
So that **I can safely test live trading without risking real funds**.

**Acceptance Criteria:**

**Given** a user wants to use testnets
**When** they read the testnet guide
**Then** they can:
- Set up Binance testnet credentials
- Set up Bybit testnet credentials
- Set up Hyperliquid testnet credentials
- Set up Lighter.xyz testnet credentials
- Verify connectivity before trading
- Understand testnet limitations

**And** the guide includes:
- Links to each exchange's testnet registration
- Environment variable naming conventions
- Configuration examples for each platform
- Common testnet issues and solutions

**Prerequisites:** Epic 10.2 complete

**Technical Notes:**
- Create `docs/live-trading/testnet-guide.md`
- Emphasize testnet vs mainnet environment variable separation
- Include verification commands/scripts
- Note that testnet funds may need to be requested

---

### Story 10.6.4: Audit & Stress Test Reports

As a **user**,
I want **to view audit findings and stress test results**,
So that **I understand the production-readiness of the system**.

**Acceptance Criteria:**

**Given** the code audit is complete
**When** I view the audit report
**Then** I can see:
- Audit scope (modules reviewed)
- Findings by severity (Critical/High/Medium/Low)
- Resolution status for each finding
- Regression test coverage
- Overall audit verdict

**Given** stress tests are complete
**When** I view the stress test report
**Then** I can see:
- Test scenarios executed
- Pass/fail status for each scenario
- Key metrics: reconnection time, throughput, memory stability
- Test dates and duration
- Overall stress test verdict

**And** reports are generated from actual test results
**And** reports are saved to `docs/live-trading/`

**Prerequisites:** Epics 10.1, 10.3 complete

**Technical Notes:**
- Create `docs/live-trading/audit-report.md` (generated from YAML findings)
- Create `docs/live-trading/stress-test-report.md` (generated from test results)
- Include generation scripts or pytest plugins
- Reports should be regeneratable as tests are run
- Update existing live trading docs with audit findings (FR63)

---

## FR Coverage Matrix

| FR | Description | Epic | Story |
|----|-------------|------|-------|
| FR1 | Static analysis on live trading modules | 10.1 | 10.1.2, 10.1.3 |
| FR2 | Document audit findings with severity | 10.1 | 10.1.1, 10.1.2, 10.1.3, 10.1.4 |
| FR3 | Track findings through lifecycle | 10.1 | 10.1.1, 10.1.5 |
| FR4 | Generate audit reports | 10.1 | 10.1.5, 10.6.4 |
| FR5 | Create regression tests for Critical/High | 10.1 | 10.1.5 |
| FR6 | Execute strategies in paper trading mode | 10.2 | 10.2.1 |
| FR7 | Simulate fills with configurable models | 10.2 | 10.2.1 |
| FR8 | Track simulated positions accurately | 10.2 | 10.2.1, 10.2.2 |
| FR9 | Calculate PnL for paper trading | 10.2 | 10.2.1 |
| FR10 | Persist paper trading state | 10.2 | 10.2.2 |
| FR11 | Run paper trading 24+ hours | 10.2 | 10.2.2 |
| FR12 | Validate order state transitions | 10.2 | 10.2.1 |
| FR13 | Compare paper vs live behavior | 10.2 | 10.2.3 |
| FR14 | Connect to exchange testnets | 10.2 | 10.2.4 |
| FR15 | Submit orders to testnet | 10.2 | 10.2.4 |
| FR16 | Track positions from testnet | 10.2 | 10.2.4, 10.2.6 |
| FR17 | Handle WebSocket disconnections | 10.2 | 10.2.5 |
| FR18 | Detect and handle rate limits | 10.2 | 10.2.4 |
| FR19 | Recover state after disconnection | 10.2 | 10.2.5 |
| FR20 | Validate end-to-end order flow | 10.2 | 10.2.6 |
| FR21 | Run testnet across restarts | 10.2 | 10.2.6 |
| FR22 | Simulate network failures | 10.3 | 10.3.2 |
| FR23 | Measure reconnection time | 10.3 | 10.3.2 |
| FR24 | Submit orders at high frequency | 10.3 | 10.3.3 |
| FR25 | Run continuously 24-48 hours | 10.3 | 10.3.4 |
| FR26 | Monitor memory usage | 10.3 | 10.3.4 |
| FR27 | Detect state corruption | 10.3 | 10.3.4 |
| FR28 | Simulate API error responses | 10.3 | 10.3.5 |
| FR29 | Generate stress test reports | 10.3 | 10.3.5 |
| FR30 | Authenticate with Lighter.xyz | 10.4 | 10.4.1 |
| FR31 | Submit market orders | 10.4 | 10.4.2 |
| FR32 | Submit limit orders | 10.4 | 10.4.2 |
| FR33 | Cancel orders | 10.4 | 10.4.3 |
| FR34 | Query positions | 10.4 | 10.4.4 |
| FR35 | Query open orders | 10.4 | 10.4.3 |
| FR36 | Query order history | 10.4 | 10.4.3 |
| FR37 | Receive fill notifications | 10.4 | 10.4.5 |
| FR38 | Handle Lighter.xyz error codes | 10.4 | 10.4.6 |
| FR39 | Switch testnet/mainnet | 10.4 | 10.4.1, 10.4.6 |
| FR40 | Paper trading mode for Lighter | 10.4 | 10.4.5 |
| FR41 | Fetch available trading pairs | 10.5 | 10.5.1 |
| FR42 | Filter by category | 10.5 | 10.5.1 |
| FR43 | Filter by name/symbol | 10.5 | 10.5.1 |
| FR44 | Fetch OHLCV data | 10.5 | 10.5.2 |
| FR45 | Multiple timeframes | 10.5 | 10.5.2 |
| FR46 | Historical data with date range | 10.5 | 10.5.2 |
| FR47 | Fetch funding rates | 10.5 | 10.5.3 |
| FR48 | Convert to rustybt format | 10.5 | 10.5.3 |
| FR49 | Ingest to bundle system | 10.5 | 10.5.3 |
| FR50 | Handle pagination | 10.5 | 10.5.2 |
| FR51 | Establish real-time connection | 10.5 | 10.5.4 |
| FR52 | Subscribe to trade updates | 10.5 | 10.5.4, 10.5.5 |
| FR53 | Subscribe to orderbook | 10.5 | 10.5.5 |
| FR54 | Subscribe to candlesticks | 10.5 | 10.5.5 |
| FR55 | Handle connection failures | 10.5 | 10.5.6 |
| FR56 | Buffer during disconnections | 10.5 | 10.5.6 |
| FR57 | Integrate with StreamBase | 10.5 | 10.5.4 |
| FR58 | Live trading setup guide | 10.6 | 10.6.1 |
| FR59 | Lighter.xyz documentation | 10.6 | 10.6.2 |
| FR60 | Testnet setup instructions | 10.6 | 10.6.3 |
| FR61 | Audit summary report | 10.6 | 10.6.4 |
| FR62 | Stress test results report | 10.6 | 10.6.4 |
| FR63 | Update existing docs | 10.6 | 10.6.4 |

**Coverage: 63/63 FRs (100%)**

---

## Summary

**Epic 10: Live Trading Production Readiness & Lighter.xyz Integration** has been decomposed into:

| Metric | Value |
|--------|-------|
| Total Epics | 6 |
| Total Stories | 32 |
| FRs Covered | 63/63 (100%) |

### Epic Sequence

1. **Epic 10.1: Production Code Audit** - Foundation work auditing existing code
2. **Epic 10.2: Paper & Testnet Validation** - Validate trading works correctly
3. **Epic 10.3: Stress Testing Framework** - Prove resilience under stress
4. **Epic 10.4: Lighter.xyz Broker Adapter** - Enable trading on Lighter.xyz
5. **Epic 10.5: Lighter.xyz Data & Streaming** - Enable data ingestion and real-time feeds
6. **Epic 10.6: Documentation & Reports** - Complete documentation and reports

### Implementation Order

Epics are sequenced for logical dependency flow:
- Epic 10.1 must complete first (audit findings may affect other work)
- Epics 10.2 and 10.3 can proceed in parallel after 10.1
- Epics 10.4 and 10.5 can proceed in parallel after 10.1
- Epic 10.6 should proceed last (documents completed work)

### Next Steps

1. Run **sprint-planning** workflow to create sprint status tracking
2. Run **create-story** workflow for first story implementation
3. Begin with Epic 10.1, Story 10.1.1

---

_For implementation: Use the `create-story` workflow to generate individual story implementation plans from this epic breakdown._

_This document incorporates PRD and Architecture context for Phase 4 implementation._
