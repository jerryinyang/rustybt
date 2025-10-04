# Shadow Trading Validation Framework - Architecture Summary

**Date:** 2025-10-03
**Author:** Winston (Architect)
**Status:** Approved - Integrated into Epic 6

---

## Executive Summary

In response to concerns about backtest-live alignment validation, we've designed and integrated a **Shadow Trading Validation Framework** into Epic 6. This framework addresses the critical gap between one-time paper trading validation and continuous production monitoring.

**Related:** See [strategy-reusability-guarantee.md](strategy-reusability-guarantee.md) for confirmation that strategies written for backtest mode run in live mode without code changes. Shadow trading validates this guarantee holds in production by continuously comparing backtest predictions vs. live execution.

**Problem Solved:**
- Original design relied on paper trading validation before going live (point-in-time check)
- No continuous monitoring of backtest-live alignment during production
- Risk of undetected edge degradation due to market regime changes or model drift

**Solution:**
- Parallel backtest engine running alongside live trading
- Real-time signal comparison (backtest predictions vs. live execution)
- Execution quality tracking (slippage, fill rates, commission)
- Alignment circuit breaker halts trading when divergence exceeds thresholds

---

## How Shadow Trading Works

**Core Concept:** Shadow trading runs the **RustyBT backtest engine** in parallel with the **live trading engine**, feeding both engines the **same real-time market data**. This creates a continuous comparison between what the backtest predicts vs. what actually happens in live trading.

**Data Flow:**
```
Live WebSocket Feed (e.g., Binance, IB, Alpaca)
            │
            ├────────────────┬────────────────┐
            │                │                │
            ▼                ▼                ▼
    LiveTradingEngine  ShadowBacktestEngine  Comparison
    (Real Broker)      (Backtest Mode)       Layer
            │                │                │
            ▼                ▼                ▼
    Broker Orders      Simulated Fills    SignalValidator
    Actual Fills       (Slippage Model)   QualityTracker
                                              │
                                              ▼
                                   AlignmentCircuitBreaker
                                   (Halts if divergence)
```

**Key Point:** Both engines run the **same strategy code** (`TradingAlgorithm`), consume the **same market data**, but execute differently:
- **Live Engine**: Sends orders to real broker, gets real fills
- **Shadow Engine**: Uses backtest execution models (slippage, partial fills, latency)

If signals or execution quality diverge beyond thresholds, trading halts automatically.

**Concrete Example:**

At 10:30:00 AM, both engines receive market data: `SPY price = $450.00`

1. **Live Engine** (real broker):
   - Strategy calls `order(SPY, 100)`  ← Signal generated
   - Order sent to Interactive Brokers
   - Fill received: `100 shares @ $450.05` (5 cents slippage)

2. **Shadow Engine** (backtest mode):
   - Strategy calls `order(SPY, 100)`  ← Signal generated
   - Backtest slippage model applied: `100 shares @ $450.02` (2 cents expected)

3. **Comparison**:
   - ✅ **Signal Match:** Both generated `order(SPY, 100)` at same timestamp
   - ⚠️ **Slippage Error:** Actual (5 cents) vs. Expected (2 cents) = 3 cents difference (6.6 bps)
   - If slippage error accumulates >50bps over multiple trades → Circuit breaker trips

This validates that:
- Strategy logic works identically (same signals)
- Execution models are accurate (slippage within tolerance)
- If either diverges significantly → halt and investigate

---

## Key Components

### 1. ShadowBacktestEngine
**Location:** `rustybt/live/shadow/engine.py`

Runs backtest simulation in parallel with live trading:
- Consumes same market data feed as live engine (broadcast pattern)
- Executes same strategy code as live engine (separate instance)
- Generates backtest signals for comparison
- Maintains separate state (isolated from live)
- Uses backtest execution models (slippage, partial fills, commission)
- Handles failures gracefully (doesn't halt live trading)

### 2. SignalAlignmentValidator
**Location:** `rustybt/live/shadow/signal_validator.py`

Compares backtest signals vs. live signals:
- Matches signals by timestamp (±100ms tolerance) and asset
- Classifies alignment: EXACT_MATCH, DIRECTION_MATCH, MAGNITUDE_MISMATCH, MISSING_SIGNAL
- Calculates signal match rate (rolling 1-hour window)
- Tracks divergence reasons for debugging

### 3. ExecutionQualityTracker
**Location:** `rustybt/live/shadow/execution_tracker.py`

Tracks expected vs. actual execution quality:
- Slippage error (expected vs. actual in bps)
- Fill rate error (partial fill model vs. reality)
- Commission error (model vs. broker charges)
- Rolling metrics over last 100 fills

### 4. AlignmentCircuitBreaker
**Location:** `rustybt/live/shadow/alignment_breaker.py`

Halts trading on alignment degradation:
- Trips if signal_match_rate < 0.95 (5% divergence)
- Trips if slippage_error > 50bps (execution 5x worse than expected)
- Trips if fill_rate_error > 20%
- Requires manual reset (forces human review)

---

## Production Deployment Workflow

### Phase 1: Offline Backtest
- Run strategy on historical data
- Validate Sharpe ratio, max drawdown, etc.
- Optimize parameters (Epic 5 framework)

### Phase 2: Paper Trading with Shadow Mode
```python
engine = LiveTradingEngine(
    strategy=strategy,
    broker=PaperBroker(),
    shadow_mode=True,
    shadow_config=ShadowTradingConfig(
        signal_match_rate_min=Decimal("0.99"),  # 99% alignment required
        slippage_error_bps_max=Decimal("10")
    )
)
```
- Validate signal_match_rate ≥ 0.99 (near-perfect alignment)
- Verify execution quality within expectations

### Phase 3: Live Trading with Shadow Mode
```python
engine = LiveTradingEngine(
    strategy=strategy,
    broker=IBAdapter(),  # Real broker
    shadow_mode=True,
    shadow_config=ShadowTradingConfig(
        signal_match_rate_min=Decimal("0.95"),  # 95% alignment required
        slippage_error_bps_max=Decimal("50")
    )
)
```
- Monitor alignment dashboard for 24 hours
- If circuit breaker trips → investigate divergence → fix model or halt
- If alignment stable for 7 days → optionally disable shadow mode

### Phase 4: Production (Optional Shadow Disable)
- Disable shadow mode to reduce overhead (5% latency savings)
- Re-enable shadow mode periodically (quarterly) for validation
- Always enable shadow mode after strategy changes

---

## Alignment Metrics Schema

Persisted in StateManager checkpoints:

```json
{
  "execution_quality": {
    "expected_slippage_bps": "5.2",
    "actual_slippage_bps": "6.8",
    "slippage_error_bps": "1.6",
    "fill_rate_expected": "0.95",
    "fill_rate_actual": "0.93",
    "fill_rate_error_pct": "-2.1",
    "commission_expected": "12.50",
    "commission_actual": "13.20",
    "commission_error_pct": "5.6"
  },
  "signal_alignment": {
    "backtest_signal_count": 42,
    "live_signal_count": 41,
    "signal_match_rate": "0.976",
    "divergence_breakdown": {
      "EXACT_MATCH": 38,
      "DIRECTION_MATCH": 3,
      "MAGNITUDE_MISMATCH": 0,
      "MISSING_SIGNAL": 1
    }
  }
}
```

---

## Architecture Integration Points

### Story 6.1: Design Live Trading Engine Architecture
**Updated AC:**
- AC1: Architecture diagram now includes ShadowBacktestEngine
- AC4: State persistence now includes alignment metrics
- AC9: New AC for shadow trading architecture design

### Story 6.2: Implement Event-Driven Async Trading Engine Core
**Integration:**
- LiveTradingEngine instantiates ShadowBacktestEngine if `shadow_mode=True`
- Market data events broadcast to both live and shadow engines

### Story 6.3: Implement State Management with Save/Restore
**Integration:**
- StateManager schema extended with `alignment_metrics`
- Checkpoints include historical alignment data for trend analysis

### Story 6.11: Implement Circuit Breakers and Monitoring
**Integration:**
- AlignmentCircuitBreaker added to circuit breaker framework
- Dashboard includes alignment metrics visualization

### Story 6.12: Implement Shadow Trading Validation Framework (NEW)
**Full implementation story** for shadow trading components.

---

## Performance Considerations

**Overhead Targets:**
- Shadow mode latency overhead: <5%
- Alignment validation per signal: <1ms
- Memory usage: Bounded (24-hour history buffer)

**Scalability Limits:**
- Recommended for <100 signals/minute strategies
- High-frequency strategies (1000+ signals/second) should use sampling mode
- Shadow mode can be disabled after validation for latency-critical production

---

## Testing Strategy

**Test Coverage:** ≥90% for all shadow trading components

**Key Tests:**
1. **Perfect Alignment Test:** Identical inputs → 100% match rate
2. **Divergence Detection Test:** Simulated slippage increase → circuit breaker trips
3. **Performance Test:** Shadow mode overhead <5%
4. **Failure Isolation Test:** Shadow crash doesn't halt live trading

---

## Risk Mitigation

### Addressed Risks:
✅ **Edge Degradation:** Continuous monitoring detects when backtest assumptions break
✅ **Model Drift:** Execution quality tracking flags slippage/commission changes
✅ **Market Regime Changes:** Signal divergence alerts when live behavior changes
✅ **Silent Failures:** Circuit breaker halts trading before losses compound

### Remaining Risks:
⚠️ **Shadow Engine Complexity:** Additional component increases system complexity
⚠️ **False Positives:** Overly strict thresholds may halt valid strategies
⚠️ **Performance Overhead:** 5% latency increase may not be acceptable for all strategies

**Mitigation:**
- Thorough testing (Story 6.12 has comprehensive test plan)
- Configurable thresholds (adjust per strategy risk tolerance)
- Optional shadow mode (can disable for latency-critical production)

---

## Files Modified

### Documentation
- [docs/prd/epic-6-live-trading-engine-broker-integrations.md](../prd/epic-6-live-trading-engine-broker-integrations.md) - Added Story 6.12
- [docs/architecture/component-architecture.md](component-architecture.md) - Added Shadow Trading Components section
- [docs/architecture/testing-strategy.md](testing-strategy.md) - Added Shadow Trading Validation Tests
- [docs/stories/6.1.design-live-trading-architecture.story.md](../stories/6.1.design-live-trading-architecture.story.md) - Updated ACs and tasks

### New Files
- [docs/stories/6.12.implement-shadow-trading-validation.story.md](../stories/6.12.implement-shadow-trading-validation.story.md) - Full story specification

---

## Conclusion

The Shadow Trading Validation Framework transforms RustyBT's live trading architecture from a **point-in-time validation model** to a **continuous monitoring model**. This addresses the critical architectural gap identified during review and provides:

1. **Confidence:** Continuous validation ensures backtest edge remains valid
2. **Safety:** Circuit breaker halts trading before losses accumulate
3. **Insights:** Execution quality tracking improves backtest models over time
4. **Flexibility:** Configurable thresholds adapt to strategy risk tolerance

This framework is **mandatory for production live trading** and recommended to be enabled during:
- Paper trading validation (Phase 2)
- First 30 days of live trading (Phase 3)
- After any strategy changes
- Quarterly validation checks

**Status:** Ready for implementation after Epic 6 Stories 6.1-6.7 are complete.
