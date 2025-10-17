# Production Deployment Guide

**Purpose**: Step-by-step guide for deploying live trading strategies to production
**Audience**: DevOps engineers, quantitative traders, system administrators
**Status**: ⚠️ **SAFETY CRITICAL** - Follow all steps carefully

---

## Overview

This guide covers the complete production deployment process for RustyBT live trading strategies, from pre-deployment validation through ongoing monitoring and incident response.

**Deployment Timeline**: Minimum 4-6 weeks from backtest completion to full live deployment

---

## Pre-Deployment Phase (Weeks 1-3)

### Week 1: Backtest Validation

**Objective**: Verify strategy performance meets production standards

**Checklist**:
- [ ] Strategy tested on ≥3 years of historical data
- [ ] Positive risk-adjusted returns (Sharpe ratio ≥1.0)
- [ ] Maximum drawdown <20% in backtest
- [ ] Walk-forward validation passed (≥10 windows)
- [ ] Monte Carlo robustness testing passed (≥1000 simulations)
- [ ] Parameter sensitivity analysis shows stable performance
- [ ] Transaction costs realistically modeled
- [ ] No look-ahead bias detected

**Validation Script**:
```python
from rustybt.utils.run_algo import run_algorithm
from rustybt.analytics.risk import RiskAnalytics
from rustybt.optimization.walk_forward import WalkForwardOptimizer

# Run backtest
results = run_algorithm(
    strategy=MyStrategy(),
    start='2020-01-01',
    end='2023-12-31',
    capital_base=100000
)

# Validate performance metrics
risk = RiskAnalytics(results)
assert risk.sharpe_ratio >= 1.0, "Sharpe ratio too low"
assert risk.max_drawdown < 0.20, "Max drawdown too high"

# Walk-forward validation
wf = WalkForwardOptimizer(strategy=MyStrategy(), ...)
wf_results = wf.run(num_windows=10)
assert wf_results['avg_oos_sharpe'] >= 0.8, "Out-of-sample performance poor"

print("✅ Backtest validation passed")
```

**Exit Criteria**:
- All checklist items complete
- Strategy performance meets expectations
- No red flags in robustness testing

---

### Week 2: Paper Trading

**Objective**: Validate strategy in simulated live environment

**Setup**:
```python
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers.paper_broker import PaperBroker
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage
from decimal import Decimal

# Configure paper broker with realistic simulation
paper_broker = PaperBroker(
    starting_cash=Decimal("100000"),
    commission_model=PerShareCommission(Decimal("0.005")),
    slippage_model=FixedBasisPointsSlippage(Decimal("5")),
    order_latency_ms=100,
    volume_limit_pct=Decimal("0.025")
)

# Initialize engine with circuit breakers
from rustybt.live.circuit_breakers import CircuitBreakerManager
breakers = CircuitBreakerManager()
breakers.add_breaker(DrawdownCircuitBreaker(max_drawdown_pct=Decimal("0.10")))
breakers.add_breaker(DailyLossCircuitBreaker(max_daily_loss=Decimal("5000")))

engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=paper_broker,
    data_portal=data_portal,
    circuit_breakers=breakers,
    checkpoint_interval_seconds=60,
    reconciliation_interval_seconds=300
)

# Run for 2 weeks
await engine.run()
```

**Monitoring Checklist**:
- [ ] Strategy generates expected number of signals
- [ ] Orders execute without errors
- [ ] Position sizing matches expectations
- [ ] Circuit breakers never trip unexpectedly
- [ ] State checkpointing works correctly
- [ ] Position reconciliation always succeeds
- [ ] No memory leaks or performance degradation
- [ ] Logging captures all necessary events

**Daily Review**:
- Check execution logs for errors
- Review order history and fills
- Verify positions match expectations
- Check circuit breaker status
- Review performance metrics

**Exit Criteria**:
- 2 weeks of stable operation (14 consecutive days)
- No unexpected errors or circuit breaker trips
- Performance aligns with backtest expectations (±20%)
- Fill rates >95%
- Average slippage within backtest assumptions

---

### Week 3: Shadow Trading

**Objective**: Validate signal alignment between live and backtest

**Setup**:
```python
from rustybt.live.shadow.config import ShadowTradingConfig

# Configure shadow trading
shadow_config = ShadowTradingConfig(
    enabled=True,
    signal_tolerance_pct=Decimal("0.05"),      # 5% signal tolerance
    max_misalignment_count=3,                  # Halt after 3 misalignments
    execution_quality_threshold=Decimal("0.90"), # 90% fill rate required
    track_slippage=True,
    track_latency=True
)

# Enable shadow mode
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    broker_adapter=paper_broker,
    data_portal=data_portal,
    shadow_mode=True,
    shadow_config=shadow_config
)

await engine.run()
```

**Monitoring Checklist**:
- [ ] Signal alignment >95%
- [ ] Execution quality >90%
- [ ] Slippage within expected range
- [ ] Latency <500ms on average
- [ ] No systematic deviations between live and shadow

**Daily Review**:
```python
# Get shadow report
report = engine.get_shadow_report()
print(f"Signal alignment: {report.alignment_rate:.2%}")
print(f"Execution quality: {report.execution_quality:.2%}")
print(f"Avg slippage: {report.avg_slippage_bps} bps")
print(f"Avg latency: {report.avg_latency_ms} ms")

# Alert if alignment drops
if report.alignment_rate < 0.95:
    send_alert("Shadow trading alignment below 95%", report)
```

**Exit Criteria**:
- 1 week of stable operation (7 consecutive days)
- Signal alignment ≥95%
- Execution quality ≥90%
- No systematic deviations
- Team confident in live deployment

---

## Deployment Phase (Week 4)

### Day 1-2: Infrastructure Setup

**Server Requirements**:
- **Primary Server**: 4+ CPU cores, 16GB+ RAM, 100GB SSD
- **Backup Server**: Same specs as primary
- **Network**: Low-latency connection to broker (ideally co-located)
- **OS**: Ubuntu 22.04 LTS or RHEL 9 (stable, long-term support)

**Installation**:
```bash
# Install RustyBT and dependencies
uv pip install rustybt[live]

# Install monitoring tools
uv pip install prometheus-client grafana-api

# Set up systemd service
cat > /etc/systemd/system/rustybt-trading.service <<EOF
[Unit]
Description=RustyBT Live Trading Engine
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/rustybt
Environment="PYTHONPATH=/opt/rustybt"
ExecStart=/usr/bin/python3 -m rustybt.live.main --strategy my_strategy
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable service
sudo systemctl enable rustybt-trading
sudo systemctl start rustybt-trading
```

**Security Setup**:
```bash
# Store broker credentials in environment variables
export BROKER_API_KEY="your_api_key_here"
export BROKER_API_SECRET="your_api_secret_here"

# Or use secrets manager (recommended for production)
aws secretsmanager get-secret-value --secret-id rustybt/broker/credentials

# Set file permissions
chmod 600 /opt/rustybt/config/*
chown trading:trading /opt/rustybt/config/*
```

**Checklist**:
- [ ] Primary server deployed and tested
- [ ] Backup server deployed and synchronized
- [ ] Network latency to broker <50ms
- [ ] Credentials securely stored
- [ ] Systemd service configured
- [ ] Log rotation configured
- [ ] Monitoring agents installed

---

### Day 3-4: Monitoring Setup

**Logging Configuration**:
```python
# Configure structured logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Log to file and stdout
import logging
logging.basicConfig(
    level=logging.INFO,
    filename='/var/log/rustybt/trading.log',
    format='%(message)s'
)
```

**Metrics Collection**:
```python
from prometheus_client import start_http_server, Counter, Gauge, Histogram

# Define metrics
orders_submitted = Counter('rustybt_orders_submitted_total', 'Total orders submitted')
orders_filled = Counter('rustybt_orders_filled_total', 'Total orders filled')
portfolio_value = Gauge('rustybt_portfolio_value', 'Current portfolio value')
order_latency = Histogram('rustybt_order_latency_seconds', 'Order submission latency')
circuit_breaker_trips = Counter('rustybt_circuit_breaker_trips_total', 'Circuit breaker trips', ['breaker_type'])

# Start Prometheus metrics server
start_http_server(8000)

# Record metrics in strategy
orders_submitted.inc()
portfolio_value.set(float(current_portfolio_value))
order_latency.observe(latency_seconds)
```

**Alerting Configuration**:
```yaml
# Prometheus alerting rules (alertmanager.yml)
groups:
  - name: rustybt_alerts
    interval: 30s
    rules:
      - alert: CircuitBreakerTripped
        expr: increase(rustybt_circuit_breaker_trips_total[5m]) > 0
        for: 1m
        annotations:
          summary: "Circuit breaker tripped"
          description: "{{ $labels.breaker_type }} circuit breaker has tripped"

      - alert: HighOrderLatency
        expr: histogram_quantile(0.95, rustybt_order_latency_seconds) > 1.0
        for: 5m
        annotations:
          summary: "High order latency detected"
          description: "95th percentile order latency is {{ $value }}s"

      - alert: NoOrdersSubmitted
        expr: increase(rustybt_orders_submitted_total[1h]) == 0
        for: 2h
        annotations:
          summary: "No orders submitted in 2 hours"
          description: "Strategy may be stalled or waiting for signals"
```

**Dashboard Setup** (Grafana):
```json
{
  "dashboard": {
    "title": "RustyBT Live Trading",
    "panels": [
      {
        "title": "Portfolio Value",
        "targets": [{"expr": "rustybt_portfolio_value"}]
      },
      {
        "title": "Orders Per Hour",
        "targets": [{"expr": "rate(rustybt_orders_submitted_total[1h])"}]
      },
      {
        "title": "Circuit Breaker Status",
        "targets": [{"expr": "rustybt_circuit_breaker_trips_total"}]
      },
      {
        "title": "Order Latency (p95)",
        "targets": [{"expr": "histogram_quantile(0.95, rustybt_order_latency_seconds)"}]
      }
    ]
  }
}
```

**Checklist**:
- [ ] Structured logging configured
- [ ] Metrics collection enabled
- [ ] Prometheus scraping configured
- [ ] Alerting rules deployed
- [ ] Grafana dashboard created
- [ ] Alert destinations configured (email, SMS, PagerDuty)

---

### Day 5-7: Initial Live Deployment (10% Position Size)

**Start Small**:
```python
# Override position sizing to 10% of normal
class MyStrategySmall(MyStrategy):
    def handle_data(self, context, data):
        # Call parent strategy logic
        super().handle_data(context, data)

        # Scale down all positions to 10%
        for asset, target_pct in self._target_positions.items():
            scaled_target = target_pct * Decimal("0.10")  # 10% of normal
            self.order_target_percent(asset, scaled_target)

# Use scaled strategy for initial deployment
engine = LiveTradingEngine(
    strategy=MyStrategySmall(),
    broker_adapter=real_broker,  # Real broker now!
    data_portal=data_portal,
    circuit_breakers=breakers,
    shadow_mode=True  # Keep shadow mode enabled
)

await engine.run()
```

**Monitoring Protocol**:
- **First 24 hours**: Check every 2 hours
- **Days 2-7**: Check twice daily (morning, evening)
- **Focus areas**:
  - Order executions
  - Circuit breaker status
  - Position reconciliation
  - Performance vs. backtest
  - Shadow trading alignment

**Daily Checklist**:
- [ ] Review execution logs
- [ ] Check circuit breaker status
- [ ] Verify position reconciliation
- [ ] Compare performance to backtest
- [ ] Review shadow trading report
- [ ] Check for any alerts/incidents
- [ ] Document any issues

**Exit Criteria**:
- 7 days of stable operation
- No critical incidents
- Performance within expectations (±30% due to small size)
- Team confident to scale up

---

## Scale-Up Phase (Weeks 5-7)

### Week 5: Scale to 35% Position Size

```python
# Increase to 35% of normal
class MyStrategyScaled35(MyStrategy):
    def handle_data(self, context, data):
        super().handle_data(context, data)
        for asset, target_pct in self._target_positions.items():
            scaled_target = target_pct * Decimal("0.35")
            self.order_target_percent(asset, scaled_target)
```

**Monitoring**: Check daily, same protocol as Week 4

**Exit Criteria**:
- 7 days stable operation
- Performance aligns with expectations
- No scaling-related issues

---

### Week 6: Scale to 65% Position Size

```python
# Increase to 65% of normal
class MyStrategyScaled65(MyStrategy):
    def handle_data(self, context, data):
        super().handle_data(context, data)
        for asset, target_pct in self._target_positions.items():
            scaled_target = target_pct * Decimal("0.65")
            self.order_target_percent(asset, scaled_target)
```

**Monitoring**: Check daily

**Exit Criteria**:
- 7 days stable operation
- Market impact within tolerance
- Slippage remains acceptable

---

### Week 7: Scale to 100% Position Size

```python
# Use normal strategy (100%)
engine = LiveTradingEngine(
    strategy=MyStrategy(),  # Full position sizing
    broker_adapter=real_broker,
    data_portal=data_portal,
    circuit_breakers=breakers,
    shadow_mode=True
)
```

**Monitoring**: Check daily for first month, then weekly

**Exit Criteria**:
- 7 days stable operation at full size
- Performance meets expectations
- Strategy fully deployed

---

## Ongoing Operations

### Daily Operations Checklist

**Morning** (before market open):
- [ ] Check overnight logs for errors
- [ ] Verify strategy still running
- [ ] Check circuit breaker status
- [ ] Review pending orders
- [ ] Verify position reconciliation

**Evening** (after market close):
- [ ] Review day's trades and performance
- [ ] Check for any alerts/incidents
- [ ] Verify state checkpoint saved
- [ ] Review shadow trading alignment
- [ ] Check resource utilization (CPU, memory, disk)

### Weekly Operations Checklist

- [ ] Performance review vs. backtest expectations
- [ ] Shadow trading comprehensive report
- [ ] Execution quality analysis (slippage, fill rates)
- [ ] Infrastructure health check
- [ ] Log rotation and archival
- [ ] Backup state checkpoints
- [ ] Review and update risk limits if needed

### Monthly Operations Checklist

- [ ] Comprehensive performance attribution
- [ ] Risk metrics analysis (VaR, CVaR, Sharpe, drawdown)
- [ ] Strategy behavior review
- [ ] Infrastructure capacity planning
- [ ] Dependency updates (security patches)
- [ ] Disaster recovery drill
- [ ] Review and update runbooks

---

## Incident Response

### Critical Incident: Circuit Breaker Tripped

**Immediate Actions** (within 5 minutes):
1. Acknowledge alert
2. Check which breaker tripped:
   ```python
   tripped = coordinator.get_tripped()
   for breaker in tripped:
       print(f"Breaker: {breaker.breaker_type.value}")
       print(f"Reason: {breaker.get_trip_reason()}")
   ```
3. Review recent logs for cause
4. If drawdown/daily loss: Accept losses, do NOT reset breaker immediately
5. If order rate/error rate: Investigate technical issue

**Investigation** (within 30 minutes):
1. Analyze logs around trip time
2. Check market conditions
3. Review recent trades
4. Verify broker connectivity
5. Check for code/data issues

**Resolution**:
1. Resolve root cause
2. Document incident in runbook
3. Only reset breaker after:
   - Root cause identified and fixed
   - Team consensus on reset
   - Market conditions normalized
4. Monitor closely after reset

**Post-Incident**:
1. Write incident report
2. Update runbooks
3. Consider adjusting breaker thresholds
4. Schedule post-mortem meeting

---

### Critical Incident: Position Discrepancy

**Immediate Actions**:
1. Acknowledge alert
2. Get reconciliation report:
   ```python
   report = await reconciler.reconcile_all(
       local_positions=local_positions,
       local_cash=local_cash,
       local_orders=local_orders
   )

   for disc in report.position_discrepancies:
       print(f"Asset: {disc.asset.symbol}")
       print(f"Local: {disc.local_amount}, Broker: {disc.broker_amount}")
       print(f"Difference: {disc.difference}")
   ```
3. Pause trading if discrepancy is large (>5% of position)
4. Verify broker account directly (via broker UI/API)

**Investigation**:
1. Check if orders were executed but not recorded
2. Review state checkpoint history
3. Check for partial fills
4. Verify reconnection/crash recovery worked correctly

**Resolution**:
1. If discrepancy confirmed:
   - Update local state to match broker (source of truth)
   - Investigate why mismatch occurred
   - Fix any code issues
2. If discrepancy was timing issue:
   - Wait for next reconciliation
   - If persists, investigate further
3. Resume trading only after positions aligned

---

### Critical Incident: Strategy Stopped

**Immediate Actions**:
1. Check if process is running:
   ```bash
   systemctl status rustybt-trading
   ```
2. If crashed, check crash logs:
   ```bash
   journalctl -u rustybt-trading -n 100
   ```
3. Check recent exception logs
4. Verify broker connectivity

**Recovery**:
1. If crash was transient:
   ```bash
   systemctl restart rustybt-trading
   ```
2. Engine will restore from last checkpoint
3. Verify checkpoint is recent (<5 minutes old)
4. Perform immediate position reconciliation
5. Monitor closely for stability

**Post-Recovery**:
1. Investigate crash cause
2. Fix any code/infrastructure issues
3. Update monitoring to detect earlier
4. Schedule post-mortem

---

## Disaster Recovery

### Scenario: Primary Server Failure

**Recovery Steps**:
1. **Failover to backup server** (5 minutes):
   ```bash
   # On backup server
   sudo systemctl start rustybt-trading
   ```
2. **Verify state restoration**:
   - Check last checkpoint age
   - If >1 hour old, perform critical position reconciliation
3. **Verify broker connectivity**
4. **Resume trading**

**Post-Recovery**:
- Investigate primary server failure
- Repair primary server
- Sync state back to primary
- Update runbooks

---

### Scenario: Broker API Down

**Immediate Actions**:
1. Verify broker status (check broker status page)
2. If confirmed broker outage:
   - Pause trading
   - Do NOT reset circuit breakers
   - Document outage start time
3. If broker API issue is isolated:
   - Check credentials
   - Verify network connectivity
   - Check rate limits

**Recovery**:
1. Wait for broker API restoration
2. Perform comprehensive position reconciliation
3. Verify account state
4. Resume trading gradually
5. Monitor closely for issues

---

## Decommissioning

### Graceful Shutdown

```python
# Trigger graceful shutdown
await engine.shutdown()

# Engine will:
# - Cancel all pending orders
# - Save final checkpoint
# - Close broker connection
# - Flush logs
```

### Strategy Replacement

1. Deploy new strategy to backup server
2. Run in paper trading mode for 1 week
3. Run in shadow mode for 1 week
4. Gradually replace old strategy:
   - Stop old strategy
   - Start new strategy at 10% size
   - Scale up new strategy over 3 weeks
   - Fully decommission old strategy

---

## Compliance and Auditing

### Audit Trail

**Required Logs**:
- All order submissions and fills
- All circuit breaker events
- All position reconciliation reports
- All state checkpoint operations
- All manual interventions

**Log Retention**:
- Keep logs for minimum 7 years (regulatory requirement for some jurisdictions)
- Compress logs older than 90 days
- Archive to cold storage annually

**Audit Query Examples**:
```python
# Get all orders for date
orders = db.query("SELECT * FROM orders WHERE date = '2024-01-15'")

# Get all circuit breaker trips
trips = db.query("SELECT * FROM circuit_breaker_events WHERE event_type = 'TRIP'")

# Get position reconciliation history
reconciliations = db.query("SELECT * FROM reconciliation_reports WHERE severity = 'CRITICAL'")
```

---

## Summary

**Critical Success Factors**:
1. ✅ Follow deployment timeline (don't rush)
2. ✅ Start small (10% position size)
3. ✅ Scale gradually (weeks, not days)
4. ✅ Monitor continuously
5. ✅ Maintain comprehensive logs
6. ✅ Have incident response plan
7. ✅ Test disaster recovery

**Never**:
- ❌ Deploy to production without paper trading
- ❌ Skip shadow trading validation
- ❌ Deploy without circuit breakers
- ❌ Scale up faster than weekly
- ❌ Ignore reconciliation discrepancies
- ❌ Reset circuit breakers without investigation

**Production deployment is a marathon, not a sprint. Patience and discipline are critical.**

---

## Related Documentation

- [Live Trading Overview](./README.md)
- [Circuit Breakers](./core/circuit-breakers.md)
