# Epic 6: Live Trading Engine & Broker Integrations

**Expanded Goal**: Build production-ready live trading engine with event-driven async architecture, state management (save/restore, crash recovery, position reconciliation), scheduled calculations (market triggers, custom schedules), and paper trading mode. Implement direct broker integrations for 5+ major brokers, data API provider adapters (Polygon, Alpaca, Alpha Vantage), and WebSocket streaming foundation (deferred from Epic 3). Enable seamless backtest-to-live transition with >99% behavioral correlation validated through paper trading. Testing, examples, and documentation integrated throughout.

---

## Story 6.1: Design Live Trading Engine Architecture

**As a** developer,
**I want** architectural design for event-driven live trading engine,
**so that** implementation follows production-ready patterns with clear concurrency and error handling strategies.

### Acceptance Criteria

1. Architecture diagram showing EventLoop, OrderManager, DataFeed, BrokerAdapter, StateManager, Scheduler
2. Async/await design specified (asyncio for I/O-bound operations, threading for CPU-bound)
3. Event types defined (MarketData, OrderFill, OrderReject, ScheduledTrigger, SystemError)
4. State persistence design (what to save: strategy state, positions, orders, cash)
5. Crash recovery design (restore from last checkpoint, reconcile with broker)
6. Threading/concurrency model documented (avoid race conditions, use thread-safe queues)
7. Error handling strategy defined (retry logic, circuit breakers, graceful degradation)
8. Monitoring and alerting hooks designed (emit events for external monitoring)
9. Architecture documentation saved to docs/architecture/live-trading.md
10. Design reviewed for production readiness before implementation

---

## Story 6.2: Implement Event-Driven Async Trading Engine Core

**As a** developer,
**I want** async event loop with order management and data feed coordination,
**so that** live trading can handle real-time market data and order execution concurrently.

### Acceptance Criteria

1. TradingEngine class with async event loop (asyncio-based)
2. Event queue implemented (prioritized queue for different event types)
3. Event dispatcher routes events to appropriate handlers (market data → strategy, order fills → portfolio)
4. OrderManager tracks active orders (submitted, pending, filled, canceled)
5. DataFeed integration (subscribe to market data, dispatch to strategy on updates)
6. Strategy execution triggers (on_data, on_order_fill, on_scheduled_event)
7. Graceful shutdown handling (cleanup resources, persist state before exit)
8. Tests validate event loop processes events in correct order
9. Performance tested: engine handles 1000+ events/second with <10ms latency
10. Example demonstrates simple live strategy responding to market data events

---

## Story 6.3: Implement State Management with Save/Restore

**As a** quantitative trader,
**I want** automatic state persistence and restore on restart,
**so that** my live trading strategies survive crashes and restarts without losing positions.

### Acceptance Criteria

1. StateManager saves strategy state, positions, open orders, cash balance to disk (JSON or pickle)
2. State saved periodically (e.g., every 1 minute) and on shutdown
3. State restored on engine startup (load last checkpoint)
4. State includes timestamps to detect stale state (warn if state >1 hour old)
5. Position reconciliation with broker after restore (compare local state vs. broker positions)
6. Discrepancy handling (if local != broker, log warning and optionally sync to broker state)
7. Atomic state writes (use temporary file + rename to prevent corruption)
8. Tests validate save → crash → restore scenario
9. Integration test simulates crash and validates correct state restoration
10. Documentation explains state management and reconciliation process

---

## Story 6.4: Implement Position Reconciliation with Broker

**As a** quantitative trader,
**I want** automatic position reconciliation comparing local state vs. broker positions,
**so that** I can detect and resolve discrepancies before they cause trading errors.

### Acceptance Criteria

1. Reconciliation runs on engine startup and periodically during operation (e.g., every 5 minutes)
2. Fetch positions from broker via API
3. Compare local positions vs. broker positions (symbol, quantity, side)
4. Discrepancy detection (differences flagged with severity: minor vs. critical)
5. Reconciliation strategies configurable (sync_to_broker, sync_to_local, halt_and_alert)
6. Cash balance reconciliation (compare local cash vs. broker account balance)
7. Order reconciliation (compare local pending orders vs. broker open orders)
8. Reconciliation report generated (summary of discrepancies and actions taken)
9. Tests validate reconciliation with simulated discrepancies
10. Documentation explains reconciliation logic and configuration options

---

## Story 6.5: Implement Scheduled Calculations and Triggers

**As a** quantitative trader,
**I want** flexible scheduling for strategy calculations (market open/close, custom intervals),
**so that** I can run periodic rebalancing, risk checks, or strategy signals on defined schedules.

### Acceptance Criteria

1. Scheduler supports cron-like expressions (e.g., "0 9 30 * * MON-FRI" for market open)
2. Market event triggers (market_open, market_close, pre_market, after_hours)
3. Custom time-based triggers (every N minutes, specific times, custom cron expressions)
4. Trading calendar integration (skip non-trading days, handle holidays)
5. Timezone-aware scheduling (convert triggers to exchange local time)
6. Callback registration (strategy registers callbacks for scheduled events)
7. Missed trigger handling (if engine offline during scheduled time, handle on startup)
8. Tests validate scheduling accuracy (<1 second deviation from scheduled time)
9. Integration test demonstrates strategy with scheduled daily rebalancing
10. Documentation provides examples for common scheduling patterns

---

## Story 6.6: Implement Paper Trading Mode

**As a** quantitative trader,
**I want** paper trading mode simulating broker with real market data,
**so that** I can validate live strategy behavior before risking real capital.

### Acceptance Criteria

1. PaperBroker implements BrokerAdapter interface mimicking real broker
2. Real-time market data consumed (via WebSocket adapters from Story 6.8)
3. Simulated order execution with realistic fills (market orders fill at current price)
4. Latency simulation applied (same as backtest latency models)
5. Partial fills simulated based on volume (same as backtest partial fill model)
6. Commission and slippage applied (same models as backtest)
7. Paper positions tracked separately (not sent to real broker)
8. Paper account balance tracked (starting capital configurable)
9. Tests validate paper trading produces expected results (matches backtest for same data)
10. Example demonstrates backtest → paper trading comparison showing >99% correlation

---

## Story 6.7: Implement Interactive Brokers Integration

**As a** quantitative trader,
**I want** Interactive Brokers integration for stocks/options/futures/forex trading,
**so that** I can deploy strategies on a professional-grade broker with global market access.

### Acceptance Criteria

1. Decision made: use ib_async library (if most efficient) OR custom TWS API implementation (if faster)
2. IBBrokerAdapter implements BrokerAdapter interface
3. Authentication with TWS/IB Gateway (handle connection, login, session management)
4. Order submission for all asset types (stocks, options, futures, forex)
5. Order status tracking (submitted, filled, canceled, rejected)
6. Position queries (fetch current positions)
7. Account balance queries (fetch cash, buying power, margin)
8. Real-time market data subscription (via ib_async or native API)
9. Error handling (connection loss, order rejections, API errors)
10. Integration test with IB paper trading account validates order submission and fills

---

## Story 6.8: Implement WebSocket Data Adapter Foundation (Moved from Epic 3)

**As a** developer,
**I want** WebSocket adapter base class for real-time streaming data,
**so that** live trading can integrate real-time market data feeds.

### Acceptance Criteria

1. BaseWebSocketAdapter created for real-time data streaming
2. Connection management implemented (connect, disconnect, reconnect on failure)
3. Subscription management (subscribe to symbols/channels, unsubscribe)
4. Message parsing framework (standardize exchange-specific WebSocket messages to OHLCV)
5. Buffering system implemented (accumulate ticks into OHLCV bars for configured resolution)
6. Heartbeat/keepalive handling (maintain connection, detect stale connections)
7. Error handling covers disconnections, invalid messages, rate limits
8. Example WebSocket adapter implemented for one exchange (e.g., Binance WebSocket)
9. Tests validate connection lifecycle and message parsing (using mock WebSocket server)
10. Documentation explains WebSocket adapter architecture for extension

---

## Story 6.9: Implement Data API Provider Adapter Framework (Moved from Epic 3)

**As a** quantitative trader,
**I want** adapter framework for professional data API providers (Polygon, Alpaca, Alpha Vantage),
**so that** I can use paid data services for higher quality and more comprehensive data.

### Acceptance Criteria

1. BaseAPIProviderAdapter created extending BaseDataAdapter with authentication support
2. API key management implemented (load from environment variables or config file)
3. Polygon adapter implemented (stocks, options, forex, crypto via REST API)
4. Alpaca adapter implemented (stocks via market data API v2)
5. Alpha Vantage adapter implemented (stocks, forex, crypto via REST API)
6. Each adapter handles provider-specific authentication (API keys, OAuth if applicable)
7. Rate limiting configured per provider (respect tier limits: free vs. paid subscriptions)
8. Error handling covers authentication failures, quota exceeded, invalid symbols
9. Integration tests use test/demo API keys (documented in README)
10. Documentation explains setup for each provider with example configuration

---

## Story 6.10: Implement Binance, Bybit, Hyperliquid, and CCXT Broker Integrations

**As a** quantitative trader,
**I want** integrations for Binance, Bybit, Hyperliquid, and CCXT-supported exchanges,
**so that** I have broad exchange coverage for crypto strategies.

### Acceptance Criteria

1. BinanceBrokerAdapter implements BrokerAdapter (using binance-connector 3.12+ OR custom API)
2. BybitBrokerAdapter implements BrokerAdapter (using pybit OR custom API)
3. HyperliquidBrokerAdapter implements BrokerAdapter (using hyperliquid-python-sdk OR custom)
4. CCXTBrokerAdapter implements BrokerAdapter (using CCXT unified API for 100+ exchanges)
5. All adapters support order submission, position queries, balance queries
6. All adapters handle exchange-specific order types and constraints
7. WebSocket integration for real-time data where available
8. Error handling for exchange-specific issues (maintenance, delisted pairs, rate limits)
9. Rate limiting per exchange (respect individual exchange limits)
10. Integration tests with testnet/demo accounts for each exchange

---

## Story 6.11: Implement Circuit Breakers and Monitoring

**As a** quantitative trader,
**I want** circuit breakers and comprehensive monitoring for live trading,
**so that** I can prevent catastrophic losses and detect issues before they escalate.

### Acceptance Criteria

1. DrawdownCircuitBreaker halts trading if portfolio drawdown exceeds threshold (e.g., -10%)
2. DailyLossCircuitBreaker halts trading if daily loss exceeds limit
3. OrderRateCircuitBreaker prevents runaway order submission (e.g., max 100 orders/minute)
4. ErrorRateCircuitBreaker halts on repeated errors (e.g., 10 order rejections in 1 minute)
5. Manual circuit breaker (emergency stop button or API endpoint)
6. Circuit breaker state tracked (NORMAL, TRIPPED, MANUALLY_HALTED)
7. Alert system (email, SMS, webhook) when circuit breaker trips
8. Monitoring dashboard (optional Streamlit/Grafana) shows live positions, PnL, circuit breaker status
9. Tests validate circuit breakers trip correctly under adverse conditions
10. Documentation explains circuit breaker configuration and best practices for risk management

---
