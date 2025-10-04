## Shadow Trading Validation Framework

The shadow trading framework runs a backtest engine in parallel with live trading to continuously validate that live execution aligns with backtest expectations. This provides early detection of edge degradation, model drift, or execution quality issues.

### Architecture Overview

```
Live Market Data
       │
       ├──────────────┬────────────────┐
       │              │                │
       ▼              ▼                ▼
LiveTradingEngine  ShadowBacktest  Comparison
(Real Broker)      (Simulation)     Layer
       │              │                │
       ▼              ▼                ▼
 Actual Orders   Expected Orders  Alignment
 Actual Fills    Expected Fills   Validator
                                      │
                                      ▼
                            AlignmentCircuitBreaker
                            (Halts if divergence)
```

### Core Components

#### 1. ShadowBacktestEngine (`engine.py`)
Runs a lightweight backtest in parallel with live trading:
- Consumes same market data as live engine
- Executes same strategy code (separate instance)
- Uses same execution models (slippage, commission, partial fills)
- Maintains separate DecimalLedger for portfolio tracking
- Does not execute actual orders (monitoring only)

#### 2. SignalAlignmentValidator (`signal_validator.py`)
Compares backtest signals vs. live signals:
- Matches signals by timestamp (±100ms tolerance) and asset
- Classifies alignment quality:
  - **EXACT_MATCH**: Quantity ≤10% diff, price ≤1% diff
  - **DIRECTION_MATCH**: Same direction, quantity ≤50% diff
  - **MAGNITUDE_MISMATCH**: Same direction, >50% quantity diff
  - **MISSING_SIGNAL**: Signal in one engine but not the other
  - **TIME_MISMATCH**: Signals outside time tolerance window
- Calculates signal match rate over rolling window (default: 1 hour)

#### 3. ExecutionQualityTracker (`execution_tracker.py`)
Tracks expected vs. actual execution quality:
- **Slippage error**: Expected slippage (from model) vs. actual slippage (from fills)
- **Fill rate error**: Expected fill rate (partial fill model) vs. actual fill rate
- **Commission error**: Expected commission (model) vs. actual charged by broker
- Maintains rolling window of fills (default: last 100)
- Calculates metrics over configurable time windows

#### 4. AlignmentCircuitBreaker (`alignment_breaker.py`)
Halts trading on alignment degradation:
- Monitors signal match rate and execution quality metrics
- Includes grace period (default: 5 minutes) before tripping
- Trips if:
  - Signal match rate < 95% (configurable)
  - Slippage error > 50 bps (configurable)
  - Fill rate error > 20% (configurable)
  - Commission error > 10% (configurable)
- Requires manual reset after trip (forced investigation)
- Supports trader override with reason logging

#### 5. ShadowTradingConfig (`config.py`)
Configuration with preset profiles:
- **Paper Trading** (strict): 99% match rate, 10 bps slippage
- **Live Trading** (relaxed): 95% match rate, 50 bps slippage
- **High-Frequency** (sampled): 90% match rate, 10% signal sampling

### Data Models (`models.py`)

**SignalRecord:**
```python
@dataclass
class SignalRecord:
    timestamp: datetime
    asset: Asset
    side: str  # "BUY" or "SELL"
    quantity: Decimal
    price: Optional[Decimal]
    order_type: str
    source: str  # "backtest" or "live"
```

**AlignmentMetrics:**
```python
@dataclass
class AlignmentMetrics:
    execution_quality: ExecutionQualityMetrics
    backtest_signal_count: int
    live_signal_count: int
    signal_match_rate: Decimal
    divergence_breakdown: Dict[SignalAlignment, int]
    timestamp: datetime
```

### Usage Example

```python
from decimal import Decimal
from rustybt.live.shadow import ShadowBacktestEngine, ShadowTradingConfig

# Create configuration
config = ShadowTradingConfig.for_live_trading()

# Create shadow engine
shadow_engine = ShadowBacktestEngine(
    strategy=my_strategy,  # TradingAlgorithm instance
    config=config,
    commission_model=commission_model,  # Same as live
    slippage_model=slippage_model,      # Same as live
    starting_cash=Decimal("100000"),    # Same as live
)

# Start shadow engine
await shadow_engine.start()

# Process market data (called by LiveTradingEngine)
await shadow_engine.process_market_data(timestamp, market_data)

# Add live signals for comparison
shadow_engine.add_live_signal(
    asset=AAPL,
    side="BUY",
    quantity=Decimal("100"),
    price=Decimal("150.00"),
    order_type="market",
    timestamp=datetime.utcnow(),
)

# Add live fills for execution quality tracking
shadow_engine.add_live_fill(
    order_id="order-123",
    signal_price=Decimal("150.00"),
    fill_price=Decimal("150.05"),
    fill_quantity=Decimal("100"),
    order_quantity=Decimal("100"),
    commission=Decimal("0.50"),
    timestamp=datetime.utcnow(),
)

# Check alignment (trips circuit breaker if thresholds breached)
is_aligned = shadow_engine.check_alignment()

if not is_aligned:
    # Circuit breaker has tripped - trading halted
    breach_summary = shadow_engine.circuit_breaker.get_breach_summary()
    print(f"Trading halted: {breach_summary}")

# Get alignment metrics for monitoring/dashboard
metrics = shadow_engine.get_alignment_metrics()
```

### Integration with LiveTradingEngine

The shadow engine will be integrated with LiveTradingEngine via a `shadow_mode` parameter:

```python
engine = LiveTradingEngine(
    strategy=strategy,
    broker=broker,
    data_portal=data_portal,
    shadow_mode=True,  # Enable shadow trading validation
    shadow_config=ShadowTradingConfig.for_live_trading(),
)
```

When enabled:
1. LiveTradingEngine instantiates ShadowBacktestEngine
2. Market data events broadcast to both engines
3. Live signals captured and compared with shadow signals
4. Live fills tracked for execution quality metrics
5. Alignment checked on configurable interval (default: every minute)
6. Circuit breaker trips if alignment degrades beyond thresholds

### Persistence in StateManager

Alignment metrics are included in StateManager checkpoints:

```python
checkpoint = StateCheckpoint(
    strategy_name="my_strategy",
    timestamp=datetime.utcnow(),
    positions=[...],
    pending_orders=[...],
    cash_balance="100000.00",
    alignment_metrics=shadow_engine.get_alignment_metrics(),  # Saved automatically
)
```

This enables:
- Historical alignment analysis across restarts
- Trend detection (degrading alignment over time)
- Post-mortem analysis if circuit breaker trips

### Testing

Unit tests validate core functionality:
- `tests/live/shadow/test_signal_validator.py`: Signal matching and alignment classification
- Future: `tests/live/shadow/test_execution_tracker.py`: Execution quality metrics
- Future: `tests/live/shadow/test_alignment_breaker.py`: Circuit breaker trip conditions
- Future: `tests/integration/shadow/test_shadow_engine.py`: End-to-end integration

Run tests:
```bash
pytest tests/live/shadow/ -v
```

### Production Deployment Workflow

1. **Offline Backtest**: Run strategy on historical data, validate Sharpe/drawdown
2. **Paper Trading + Shadow**: Enable shadow mode with strict thresholds (99% match)
3. **Live Trading + Shadow**: Enable shadow mode with relaxed thresholds (95% match)
4. **Monitor**: Watch alignment dashboard for first 24 hours
5. **Investigate**: If circuit breaker trips, investigate divergence before resuming
6. **Optional**: Disable shadow mode after 7 days of stable alignment (reduces overhead)

### Performance Considerations

- **Overhead**: Shadow mode adds ~5% latency (parallel processing)
- **Memory**: Bounded to last 24 hours of alignment history
- **Scalability**: Recommended for strategies <100 signals/minute
- **Sampling**: High-frequency strategies can use 10% signal sampling

### Remaining Work

1. **Full TradingAlgorithm Integration**: ShadowBacktestEngine needs complete backtest infrastructure
2. **LiveTradingEngine Integration**: Add shadow_mode parameter and event broadcasting
3. **Alignment Dashboard**: Real-time visualization of alignment metrics
4. **Integration Tests**: End-to-end validation with PaperBroker and live data
5. **Documentation**: Alignment interpretation guide and troubleshooting

See [Story 6.12](../../../docs/stories/6.12.implement-shadow-trading-validation.story.md) for complete implementation details.
