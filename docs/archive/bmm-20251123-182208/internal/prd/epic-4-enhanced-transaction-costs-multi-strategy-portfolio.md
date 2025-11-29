# Epic 4: Enhanced Transaction Costs & Multi-Strategy Portfolio

**Expanded Goal**: Implement realistic transaction cost modeling including latency simulation, partial fills based on volume, multiple slippage models, tiered commission structures, borrow costs for short selling, and overnight financing for leveraged positions. Build multi-strategy portfolio management system supporting concurrent strategies with capital allocation algorithms (Fixed, Dynamic, Risk-Parity, Kelly Criterion, Drawdown-Based), cross-strategy risk management, and order aggregation, enabling professional-grade backtesting and multi-strategy live trading. Testing, examples, and documentation integrated throughout.

---

## Story 4.1: Implement Latency Simulation

**As a** quantitative trader,
**I want** realistic latency simulation (network + broker + exchange),
**so that** backtests account for order submission delays and reflect live trading conditions.

### Acceptance Criteria

1. Latency model configurable (fixed, random distribution, or historical latency data)
2. Network latency component simulated (e.g., 5-50ms based on geographic distance)
3. Broker processing latency simulated (e.g., 1-10ms for order validation and routing)
4. Exchange matching latency simulated (e.g., 0.1-5ms for order matching)
5. Total latency applied to order submission: order_submission_time + latency = actual_execution_time
6. Price movement during latency period affects fill price (market orders filled at price after latency)
7. Configuration API allows per-broker latency profiles
8. Tests validate latency impact on order execution timing and fill prices
9. Performance overhead measured: latency simulation adds <5% to backtest time
10. Documentation explains latency configuration with realistic examples per broker type

---

## Story 4.2: Implement Partial Fill Model

**As a** quantitative trader,
**I want** partial fill simulation based on order size vs. available volume,
**so that** backtests reflect reality of large orders that cannot be fully filled immediately.

### Acceptance Criteria

1. Volume-based partial fill logic: if order_size > available_volume × fill_ratio, partially fill
2. Fill ratio configurable (e.g., can fill up to 10% of bar's volume without impact)
3. Multi-bar fill simulation: unfilled portion persists to next bar(s) until fully filled or timeout
4. Order state tracking for partial fills (PartiallyFilled state, cumulative fill quantity)
5. Average fill price calculated across multiple partial fills
6. Market impact modeled: larger orders relative to volume get worse average prices
7. Configuration supports different fill models (aggressive: fill more quickly, conservative: fill slower)
8. Tests validate partial fill behavior with large orders in low-volume scenarios
9. Integration test demonstrates realistic partial fill across multiple bars
10. Documentation explains partial fill logic and configuration options

---

## Story 4.3: Implement Multiple Slippage Models

**As a** quantitative trader,
**I want** multiple slippage models (volume-share, fixed bps, bid-ask spread),
**so that** I can choose the most appropriate model for different markets and strategies.

### Acceptance Criteria

1. VolumeShareSlippage model: slippage = f(order_size / bar_volume) × volatility
2. FixedBasisPointSlippage model: slippage = price × fixed_bps (e.g., 0.05% = 5 bps)
3. BidAskSpreadSlippage model: slippage = spread / 2 for market orders crossing spread
4. CustomSlippage base class for user-defined models
5. Slippage applied directionally: buy orders slip upward, sell orders slip downward
6. Configuration API allows per-asset or per-strategy slippage model selection
7. Slippage affects fill price: fill_price = quoted_price ± slippage
8. Tests validate each slippage model with known inputs/outputs
9. Property-based tests ensure slippage always worsens execution (never improves)
10. Documentation compares models with guidance on when to use each

---

## Story 4.4: Implement Tiered Commission Models

**As a** quantitative trader,
**I want** tiered commission structures (per-share, percentage, maker/taker for crypto),
**so that** backtests accurately reflect broker fee schedules including volume discounts.

### Acceptance Criteria

1. PerShareCommission model: fee = shares × rate_per_share (e.g., $0.005/share)
2. PercentageCommission model: fee = trade_value × percentage (e.g., 0.1%)
3. TieredCommission model: fee varies by cumulative monthly volume (volume discounts)
4. MakerTakerCommission model: different rates for maker (add liquidity) vs. taker (take liquidity) orders
5. MinimumCommission enforced: fee = max(calculated_fee, minimum_fee)
6. Commission configuration per broker (load from broker profile configs)
7. Commission tracking accumulated for tier calculations (monthly volume resets)
8. All commissions calculated using Decimal for precision
9. Tests validate each commission model with realistic broker fee schedules
10. Documentation includes examples from major brokers (Interactive Brokers, Binance, etc.)

---

## Story 4.5: Implement Borrow Cost Model for Short Selling

**As a** quantitative trader,
**I want** borrow cost simulation for short positions,
**so that** backtests account for stock borrow fees that impact short strategy profitability.

### Acceptance Criteria

1. BorrowCostModel calculates daily interest on short position value
2. Borrow rate configurable per asset (easy-to-borrow: 0.3%, hard-to-borrow: 5-50%+)
3. Borrow cost accrues daily and debits from cash balance
4. Borrow rate lookup supports external data sources (e.g., CSV with symbol → rate mapping)
5. Default borrow rate applied when specific rate unavailable
6. Borrow cost tracked separately in performance reporting (itemized cost breakdown)
7. Tests validate daily accrual calculation accuracy using Decimal arithmetic
8. Integration test demonstrates short strategy with borrow costs over extended period
9. Property-based test ensures borrow cost always reduces short position profitability
10. Documentation explains borrow cost impact with example calculations

---

## Story 4.6: Implement Overnight Financing for Leveraged Positions

**As a** quantitative trader,
**I want** overnight financing cost/credit for leveraged positions (margin interest, swap rates),
**so that** backtests reflect carrying costs of leveraged strategies.

### Acceptance Criteria

1. OvernightFinancingModel calculates daily financing on leveraged exposure
2. Long leverage: pays interest (debit from cash)
3. Short leverage in forex/crypto: may pay or receive interest (swap rates)
4. Financing rate configurable (e.g., broker margin rate: 5% annualized)
5. Daily accrual calculation: exposure × rate / 365 (or 360 for some markets)
6. Financing applied at end-of-day (or rollover time for forex/crypto)
7. Financing tracked separately in performance reporting
8. Tests validate daily accrual for long and short leveraged positions
9. Integration test demonstrates leveraged strategy with financing costs
10. Documentation explains financing mechanics for different asset classes

---

## Story 4.7: Implement Portfolio Allocator for Multi-Strategy Management

**As a** quantitative trader,
**I want** portfolio allocator supporting multiple concurrent strategies,
**so that** I can run diversified strategy portfolios with sophisticated capital allocation.

### Acceptance Criteria

1. PortfolioAllocator class manages multiple Strategy instances concurrently
2. Capital allocation to each strategy tracked and enforced
3. Strategy isolation: each strategy operates on its allocated capital independently
4. Portfolio-level cash management: aggregate cash across strategies
5. Strategy performance tracked individually (per-strategy returns, drawdowns, metrics)
6. Portfolio-level performance aggregated (combined returns, diversification benefit)
7. Rebalancing support: reallocate capital between strategies based on performance
8. Strategy start/stop control (add/remove strategies dynamically during live trading)
9. Tests validate multi-strategy execution with capital allocation enforcement
10. Example demonstrates 3-strategy portfolio (long equity, short equity, market-neutral)

---

## Story 4.8: Implement Capital Allocation Algorithms

**As a** quantitative trader,
**I want** multiple capital allocation algorithms (Fixed, Dynamic, Risk-Parity, Kelly, Drawdown-Based),
**so that** I can optimize portfolio capital distribution across strategies.

### Acceptance Criteria

1. FixedAllocation: static percentage per strategy (e.g., 30% / 40% / 30%)
2. DynamicAllocation: adjust based on recent performance (winners get more capital)
3. RiskParityAllocation: allocate inversely proportional to strategy volatility (equal risk contribution)
4. KellyCriterionAllocation: allocate based on expected return / variance (optimal growth)
5. DrawdownBasedAllocation: reduce allocation to strategies in drawdown, increase to recovering strategies
6. Allocation constraints enforced (min/max per strategy, sum = 100%)
7. Rebalancing frequency configurable (daily, weekly, monthly)
8. All allocations calculated using Decimal precision
9. Tests validate each algorithm with synthetic strategy performance data
10. Documentation explains each algorithm with mathematical formulas and use cases

---

## Story 4.9: Implement Cross-Strategy Risk Management

**As a** quantitative trader,
**I want** portfolio-level risk limits and correlation-aware position sizing,
**so that** I can control aggregate risk across multiple strategies.

### Acceptance Criteria

1. Portfolio-level position limits (max total leverage, max single asset exposure)
2. Correlation-aware sizing: reduce allocation when strategies are highly correlated
3. Drawdown limits: halt all strategies if portfolio drawdown exceeds threshold (e.g., -15%)
4. Volatility targeting: adjust strategy allocations to maintain target portfolio volatility
5. Concentration limits: max exposure to single asset across all strategies
6. Risk limit violations trigger alerts and optionally halt trading
7. Risk metrics calculated in real-time (portfolio beta, VaR, correlation matrix)
8. Tests validate risk limit enforcement with simulated limit violations
9. Integration test demonstrates risk limits preventing excessive drawdown
10. Documentation explains risk management configuration and best practices

---

## Story 4.10: Implement Order Aggregation Across Strategies

**As a** quantitative trader,
**I want** intelligent order aggregation that nets positions across strategies,
**so that** I minimize transaction costs by combining offsetting orders before execution.

### Acceptance Criteria

1. Order aggregation engine collects orders from all strategies before execution
2. Netting logic: cancel offsetting orders (Strategy A buys 100, Strategy B sells 50 → net buy 50)
3. Aggregation respects order types: only compatible orders aggregated (both Market, or same limit price)
4. Order attribution maintained: track which strategies contributed to aggregated order
5. Fill allocation: distribute fills back to originating strategies proportionally
6. Commission savings from aggregation tracked and reported
7. Tests validate netting logic with various offsetting order scenarios
8. Integration test demonstrates multi-strategy portfolio with order aggregation savings
9. Property-based test ensures aggregation never increases transaction costs
10. Documentation explains aggregation rules and limitations

---
