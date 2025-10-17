# Audit Logging Guide

RustyBT provides comprehensive trade-by-trade audit logging using `structlog` with JSON output format. This guide explains how to configure and query audit logs.

## Overview

The audit logging system captures:
- **Trade Events**: Order submission, fills, modifications, cancellations
- **Strategy Decisions**: Trading signals, reasoning, parameter values
- **System Events**: Startup, shutdown, errors, circuit breaker trips

All logs are written in JSON format with ISO 8601 timestamps, enabling easy searching and filtering with tools like `jq`, `grep`, or log aggregation platforms.

## Configuration

### Basic Setup

```python
from rustybt.utils.logging import configure_logging

# Configure with default settings
configure_logging()  # Logs to ./logs/rustybt.log

# Configure with custom directory and log level
configure_logging(
    log_dir=Path("/var/log/rustybt"),
    log_level="DEBUG",
    log_to_console=True,
    log_to_file=True
)
```

### Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `log_dir` | Directory for log files | `./logs` |
| `log_level` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` |
| `log_to_console` | Whether to log to console | `True` |
| `log_to_file` | Whether to log to file | `True` |

### Log Rotation

Logs are automatically rotated daily at midnight with the following settings:
- **Rotation**: Daily at midnight
- **Retention**: 30 days (configurable via `backupCount`)
- **Compression**: Not currently implemented (rotated logs are stored uncompressed)

Example log files:
```
logs/
  rustybt.log              # Current log
  rustybt.log.2025-01-30   # Yesterday's log
  rustybt.log.2025-01-29   # Day before yesterday
  ...
```

## Log Format

### JSON Structure

Each log entry is a single JSON object with the following common fields:

```json
{
  "event": "order_submitted",
  "event_type": "order_submitted",
  "level": "info",
  "timestamp": "2025-01-31T10:30:45.123456Z",
  "order_id": "order-00000001",
  "asset": "AAPL",
  "amount": "100",
  "order_type": "market",
  "limit_price": null,
  "stop_price": null
}
```

### Trade Event Logs

#### Order Submission

```json
{
  "event": "order_submitted",
  "event_type": "order_submitted",
  "order_id": "order-00000001",
  "asset": "AAPL",
  "amount": "100",
  "order_type": "market",
  "limit_price": null,
  "stop_price": null,
  "timestamp": "2025-01-31T10:30:45.123456Z"
}
```

#### Order Fill

```json
{
  "event": "order_filled",
  "event_type": "order_filled",
  "order_id": "order-00000001",
  "asset": "AAPL",
  "fill_price": "150.25",
  "filled_amount": "100",
  "commission": "0.50",
  "slippage": "0.00",
  "timestamp": "2025-01-31T10:30:46.789012Z"
}
```

#### Order Rejection

```json
{
  "event": "order_rejected",
  "event_type": "order_rejected",
  "level": "error",
  "order_id": "order-00000002",
  "asset": "AAPL",
  "rejection_reason": "Insufficient funds",
  "timestamp": "2025-01-31T10:31:00.123456Z"
}
```

#### Order Cancellation

```json
{
  "event": "order_canceled",
  "event_type": "order_canceled",
  "order_id": "order-00000003",
  "asset": "AAPL",
  "reason": "User requested",
  "timestamp": "2025-01-31T10:32:00.123456Z"
}
```

### Strategy Decision Logs

```json
{
  "event": "trading_decision",
  "event_type": "trading_decision",
  "signal_type": "buy",
  "asset": "AAPL",
  "amount": "100",
  "limit_price": null,
  "stop_price": null,
  "strategy_class": "MomentumStrategy",
  "timestamp": "2025-01-31T10:30:44.123456Z"
}
```

### System Event Logs

#### System Startup

```json
{
  "event": "system_startup",
  "event_type": "system_startup",
  "version": "0.1.0",
  "strategy_class": "MomentumStrategy",
  "broker": "PaperBroker",
  "checkpoint_interval_seconds": 60,
  "reconciliation_strategy": "WARN_ONLY",
  "shadow_mode": false,
  "timestamp": "2025-01-31T10:00:00.000000Z"
}
```

#### System Shutdown

```json
{
  "event": "system_shutdown",
  "event_type": "system_shutdown",
  "reason": "graceful",
  "timestamp": "2025-01-31T18:00:00.000000Z"
}
```

#### System Error

```json
{
  "event": "system_error",
  "event_type": "system_error",
  "level": "error",
  "exception_type": "BrokerConnectionError",
  "error_message": "Failed to connect to broker",
  "timestamp": "2025-01-31T10:15:30.123456Z"
}
```

## Searching and Filtering Logs

### Using `jq`

#### Find all rejected orders

```bash
cat logs/rustybt.log | jq 'select(.event_type == "order_rejected")'
```

#### Find all trades for specific asset

```bash
cat logs/rustybt.log | jq 'select(.asset == "AAPL")'
```

#### Find all errors in last hour

```bash
cat logs/rustybt.log | jq 'select(.level == "error" and .timestamp > "'$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)'")'
```

#### Calculate total commissions paid

```bash
cat logs/rustybt.log | jq 'select(.event_type == "order_filled") | .commission | tonumber' | awk '{sum+=$1} END {print sum}'
```

#### Count orders by type

```bash
cat logs/rustybt.log | jq -r 'select(.event_type == "order_submitted") | .order_type' | sort | uniq -c
```

#### Get all orders for a specific strategy

```bash
cat logs/rustybt.log | jq 'select(.strategy_class == "MomentumStrategy" and .event_type == "trading_decision")'
```

### Using `grep`

#### Find all order-related events

```bash
grep "order_" logs/rustybt.log
```

#### Find specific order by ID

```bash
grep "order-00000001" logs/rustybt.log
```

#### Find system errors

```bash
grep "system_error" logs/rustybt.log
```

## Sensitive Data Masking

RustyBT automatically masks sensitive data in logs. The following fields are masked with `***MASKED***`:
- `api_key`
- `api_secret`
- `password`
- `token`
- `encryption_key`
- `secret`
- `credentials`
- `private_key`

Example:
```python
logger.info(
    "broker_connected",
    broker_id="binance",
    api_key="secret123",  # Will be masked in logs
    user="john"  # Will appear in logs
)
```

Log output:
```json
{
  "event": "broker_connected",
  "broker_id": "binance",
  "api_key": "***MASKED***",
  "user": "john",
  "timestamp": "2025-01-31T10:00:00.000000Z"
}
```

## Integration with Log Aggregation Tools

### Elasticsearch

Use Filebeat to ship logs to Elasticsearch:

```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/rustybt/rustybt.log
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["localhost:9200"]
  index: "rustybt-logs-%{+yyyy.MM.dd}"
```

### Kibana Query Examples

- Find all rejected orders: `event_type:"order_rejected"`
- Find high-value trades: `filled_amount > 1000`
- Find errors: `level:"error"`

### Grafana Loki

Use Promtail to ship logs to Loki:

```yaml
# promtail.yml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: rustybt
    static_configs:
      - targets:
          - localhost
        labels:
          job: rustybt
          __path__: /var/log/rustybt/*.log
    pipeline_stages:
      - json:
          expressions:
            event_type: event_type
            level: level
            asset: asset
```

## Performance Considerations

- **Log Volume**: At INFO level, expect ~1-10 MB/day for typical strategies
- **Disk Space**: With 30-day retention, allocate ~300 MB for log storage
- **I/O Impact**: Logging is async and has minimal impact (<1% CPU, <5ms latency)

## Compliance and Retention

For regulatory compliance:
- Logs contain full audit trail of all trades
- Timestamps are ISO 8601 UTC format
- Logs are immutable after rotation
- Retention period is configurable (default: 30 days)

For financial regulations requiring 7-year retention, configure `backupCount=2555` (7 years × 365 days):

```python
# Custom configuration for 7-year retention
from rustybt.utils.logging import configure_logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

log_dir = Path("/var/log/rustybt")
log_dir.mkdir(parents=True, exist_ok=True)

handler = TimedRotatingFileHandler(
    filename=log_dir / "rustybt.log",
    when="midnight",
    interval=1,
    backupCount=2555,  # 7 years
    encoding="utf-8"
)

# Then configure with custom handler...
```

## Example: Custom Logging in Strategies

Strategies can log custom decision metadata:

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.utils.logging import get_logger

class CustomStrategy(TradingAlgorithm):
    def initialize(self, context):
        self.logger = get_logger(__name__)
        self.logger.info(
            "strategy_initialized",
            event_type="strategy_initialized",
            momentum_threshold=0.02,
            lookback_period=20
        )

    def handle_data(self, context, data):
        # Calculate signal
        momentum = self.calculate_momentum(context, data)

        # Log signal with reasoning
        self.logger.info(
            "signal_calculated",
            event_type="signal_calculated",
            asset=context.asset.symbol,
            momentum=str(momentum),
            threshold=str(self.momentum_threshold),
            signal="buy" if momentum > self.momentum_threshold else "hold"
        )

        # Place order if signal
        if momentum > self.momentum_threshold:
            self.order(context.asset, 100)
```

### Running Strategies with Audit Logging

Once you've configured audit logging in your strategy, execute it to generate logs:

#### CLI Method

```bash
rustybt run -f custom_strategy.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31
```

Logs will be written to the configured directory (default: `~/.rustybt/logs/`).

#### Python API Method

```python
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

if __name__ == "__main__":
    result = run_algorithm(
        algorithm_class=CustomStrategy,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=100000
    )

    print(f"Backtest complete. Check logs at: ~/.rustybt/logs/")
    print(f"Total return: {result['returns'].iloc[-1]:.2%}")
```

#### Analyzing Audit Logs

After running your strategy, you can analyze the structured logs:

```python
import json

# Read and parse structured logs
with open('~/.rustybt/logs/rustybt.log') as f:
    for line in f:
        log_entry = json.loads(line)
        if log_entry['event_type'] == 'order_placed':
            print(f"Order: {log_entry['asset']} @ {log_entry['price']}")
```

## Troubleshooting

### Logs not appearing

1. Check log directory exists and is writable
2. Verify log level is not filtering events (use DEBUG)
3. Call `logging.shutdown()` to flush buffers

### Large log files

1. Reduce log level to INFO or WARNING
2. Decrease retention period (reduce `backupCount`)
3. Manually compress old log files if needed (e.g., `gzip rustybt.log.*`)

### Missing timestamps

Ensure structlog is properly configured:
```python
configure_logging()  # Call before any logging
```

## API Reference

### `configure_logging()`

Configure structured logging with JSON output.

**Parameters:**
- `log_dir` (Path, optional): Directory for log files (default: ./logs)
- `log_level` (str, optional): Logging level (default: INFO)
- `log_to_console` (bool, optional): Log to console (default: True)
- `log_to_file` (bool, optional): Log to file (default: True)

**Raises:**
- `ValueError`: If log_level is invalid

### `get_logger(name=None)`

Get a structlog logger instance.

**Parameters:**
- `name` (str, optional): Logger name (typically `__name__`)

**Returns:**
- Configured structlog logger

### `mask_sensitive_data(logger, method_name, event_dict)`

Mask sensitive data in log events (auto-configured as processor).

**Parameters:**
- `logger`: The logger instance
- `method_name`: The logging method name
- `event_dict`: The event dictionary

**Returns:**
- Modified event dictionary with masked sensitive fields

---

For more information, see:
- [structlog documentation](https://www.structlog.org/)
- [Log rotation with TimedRotatingFileHandler](https://docs.python.org/3/library/logging.handlers.html#timedrotatingfilehandler)
