# CLI Commands Inventory

**Date:** 2025-10-13
**Story:** X2.7 - P2 Production Validation & Documentation
**Purpose:** Document all CLI commands and their options for validation

## Verification Summary

✅ All required commands exist and are accessible via `python3 -m rustybt`

## Commands Overview

| Command | Status | Purpose |
|---------|--------|---------|
| test-broker | ✅ Available | Test broker connection and authentication |
| test-data | ✅ Available | Test data source connectivity |
| benchmark | ✅ Available | Run performance benchmarks |
| paper-trade | ✅ Available | Run paper trading mode |
| analyze-uptime | ✅ Available | Analyze logs for uptime statistics |
| verify-config | ✅ Available | Validate configuration file |
| test-alerts | ✅ Available | Test alert configuration |

## Detailed Command Documentation

### 1. test-broker

**Purpose:** Test broker connection and authentication

**Usage:**
```bash
python3 -m rustybt test-broker [OPTIONS]
```

**Options:**
- `--broker [binance|bybit|ccxt|ib]` - Broker to test [REQUIRED]
- `--testnet` - Use testnet/paper trading environment
- `--help` - Show help message

**Examples:**
```bash
python3 -m rustybt test-broker --broker binance
python3 -m rustybt test-broker --broker binance --testnet
```

**Functionality:**
- Tests authentication
- Fetches account information
- Checks API rate limits

---

### 2. test-data

**Purpose:** Test data source connectivity

**Usage:**
```bash
python3 -m rustybt test-data [OPTIONS]
```

**Options:**
- `--source [yfinance|ccxt|binance]` - Data source to test [REQUIRED]
- `--symbol TEXT` - Symbol to fetch (default: BTC/USDT)
- `--help` - Show help message

**Examples:**
```bash
python3 -m rustybt test-data --source yfinance --symbol AAPL
python3 -m rustybt test-data --source ccxt --symbol BTC/USDT
```

---

### 3. benchmark

**Purpose:** Run performance benchmarks

**Usage:**
```bash
python3 -m rustybt benchmark [OPTIONS]
```

**Options:**
- `--output [table|json]` - Output format
- `--help` - Show help message

**Examples:**
```bash
python3 -m rustybt benchmark
python3 -m rustybt benchmark --output json
```

**Tests:**
- Order execution latency
- Backtest speed
- Memory usage
- Data portal throughput

---

### 4. paper-trade

**Purpose:** Run paper trading mode

**Usage:**
```bash
python3 -m rustybt paper-trade [OPTIONS]
```

**Options:**
- `--strategy PATH` - Path to strategy Python file [REQUIRED]
- `--broker [binance|bybit|paper]` - Broker to use (default: paper)
- `--duration TEXT` - Duration to run (e.g., 24h, 7d, 30d)
- `--log-file PATH` - Path to log file (default: logs/paper_trade_{timestamp}.log)
- `--help` - Show help message

**Examples:**
```bash
python3 -m rustybt paper-trade --strategy momentum.py --duration 30d
python3 -m rustybt paper-trade --strategy momentum.py --broker binance --duration 7d
```

**Functionality:**
- Executes strategy in paper trading mode with simulated broker
- Tracks uptime, error rate, and performance metrics

---

### 5. analyze-uptime

**Purpose:** Analyze logs for uptime statistics

**Usage:**
```bash
python3 -m rustybt analyze-uptime [OPTIONS]
```

**Options:**
- `--log-file PATH` - Path to log file to analyze
- `--log-dir PATH` - Directory containing log files
- `--days INTEGER` - Number of days to analyze
- `--help` - Show help message

**Examples:**
```bash
python3 -m rustybt analyze-uptime --days 30
python3 -m rustybt analyze-uptime --log-file logs/paper_trade.log
```

**Calculates:**
- Total uptime percentage
- Downtime duration and frequency
- Error rate per 1000 operations
- Common error patterns

---

### 6. verify-config

**Purpose:** Validate configuration file

**Usage:**
```bash
python3 -m rustybt verify-config [OPTIONS]
```

**Options:**
- `--env-file PATH` - Path to .env file to validate
- `--help` - Show help message

**Examples:**
```bash
python3 -m rustybt verify-config
python3 -m rustybt verify-config --env-file /path/to/.env
```

**Checks:**
- Required variables
- Valid values
- Security issues (e.g., weak encryption keys)

---

### 7. test-alerts

**Purpose:** Test alert configuration

**Usage:**
```bash
python3 -m rustybt test-alerts [OPTIONS]
```

**Options:**
- `--email TEXT` - Test email alert
- `--slack TEXT` - Test Slack webhook
- `--help` - Show help message

**Examples:**
```bash
python3 -m rustybt test-alerts --email your@email.com
python3 -m rustybt test-alerts --slack https://hooks.slack.com/...
```

---

## Additional Commands Available

The CLI also provides these additional commands (not required for X2.7 validation):

- `run` - Run a backtest for the given algorithm
- `live-trade` - Run live trading mode
- `bundle` / `bundles` - Manage data bundles
- `ingest` / `ingest-unified` - Ingest data
- `clean` - Clean up downloaded data
- `cache` - Manage data source cache
- `balance` - Query account balance from broker
- `status` - Show live trading engine status
- `encrypt-credentials` - Encrypt broker credentials at rest
- `keygen` - Generate encryption key for credential storage
- `generate-api-token` - Generate API authentication token

---

## Validation Findings

### Status: ✅ PASS

All required CLI commands for Story X2.7 are present and functional:
- ✅ test-broker
- ✅ test-data
- ✅ benchmark
- ✅ paper-trade
- ✅ analyze-uptime
- ✅ verify-config
- ✅ test-alerts

**No blockers identified.** All commands have proper help text and expected options.

### Environment Configuration

- Python version: Python 3.12.0
- CLI entry point: `python3 -m rustybt`
- Validation log directory: `~/.rustybt/logs/validation` (created)

### Next Steps

Proceed with operational validation:
1. Task 2: Broker Connection Validation
2. Task 3: Data Provider Validation
3. Task 4: Benchmark Execution
4. Task 5-7: Paper Trading and Uptime Analysis
5. Task 8-11: Documentation Audit and Fixes
6. Task 12: Comprehensive Validation Report
