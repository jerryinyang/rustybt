# RustyBT Troubleshooting Guide

## Overview

This guide provides solutions to common issues encountered when deploying and operating RustyBT in production. Issues are organized by category for quick reference.

**Last Updated**: 2025-10-11
**Version**: 1.0

---

## Table of Contents

1. [Installation & Setup Issues](#1-installation-setup-issues)
2. [Broker Connection Issues](#2-broker-connection-issues)
3. [Data Source Issues](#3-data-source-issues)
4. [Order Execution Issues](#4-order-execution-issues)
5. [Performance Issues](#5-performance-issues)
6. [Security & Authentication Issues](#6-security-authentication-issues)
7. [Logging & Monitoring Issues](#7-logging-monitoring-issues)
8. [State Persistence & Recovery Issues](#8-state-persistence-recovery-issues)
9. [Common Error Messages](#9-common-error-messages)
10. [Log Interpretation Guide](#10-log-interpretation-guide)

---

## 1. Installation & Setup Issues

### Issue 1.1: Python 3.12 Not Found

**Symptoms:**
```bash
$ python3.12 --version
bash: python3.12: command not found
```

**Solution:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# macOS
brew install python@3.12

# Verify installation
python3.12 --version
```

### Issue 1.2: uv Installation Fails

**Symptoms:**
```bash
$ curl -LsSf https://astral.sh/uv/install.sh | sh
curl: (7) Failed to connect to astral.sh
```

**Solutions:**

**Option 1: Check internet connection**
```bash
ping astral.sh
# Verify network connectivity
```

**Option 2: Install via pip (fallback)**
```bash
pip install uv
```

**Option 3: Manual installation**
```bash
# Download from GitHub releases
wget https://github.com/astral-sh/uv/releases/download/0.5.x/uv-x86_64-unknown-linux-gnu.tar.gz
tar -xzf uv-x86_64-unknown-linux-gnu.tar.gz
sudo mv uv /usr/local/bin/
```

### Issue 1.3: Dependency Installation Fails

**Symptoms:**
```bash
$ uv pip install -e ".[all]"
error: Failed to build wheel for polars
```

**Solutions:**

**Option 1: Install build dependencies**
```bash
# Ubuntu/Debian
sudo apt install -y build-essential python3.12-dev

# macOS
xcode-select --install
```

**Option 2: Increase pip timeout**
```bash
uv pip install -e ".[all]" --timeout 300
```

**Option 3: Install dependencies separately**
```bash
# Core dependencies
uv pip install polars pandas numpy

# Data dependencies
uv pip install ccxt yfinance

# Development dependencies
uv pip install pytest mypy ruff black
```

### Issue 1.4: Virtual Environment Activation Fails

**Symptoms:**
```bash
$ source .venv/bin/activate
bash: .venv/bin/activate: No such file or directory
```

**Solution:**
```bash
# Recreate virtual environment
rm -rf .venv
uv venv --python 3.12

# Activate
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

---

## 2. Broker Connection Issues

### Issue 2.1: Binance Connection Failure

**Symptoms:**
```python
BrokerConnectionError: Failed to connect to Binance API
```

**Root Causes & Solutions:**

**Cause 1: Invalid API credentials**
```bash
# Verify API key and secret in .env
cat .env | grep BINANCE

# Test with Binance testnet first
BINANCE_TESTNET=true python -m rustybt test-broker --broker binance
```

**Cause 2: IP not whitelisted**
```bash
# Check your public IP
curl ifconfig.me

# Add IP to Binance API whitelist:
# 1. Log in to Binance
# 2. Go to API Management
# 3. Edit API key
# 4. Add your IP to whitelist
```

**Cause 3: API permissions insufficient**
```text
Ensure API key has the following permissions enabled:
- Enable Reading
- Enable Spot & Margin Trading
- Enable Futures (if trading futures)
```

**Cause 4: Rate limit exceeded**
```python
# Binance rate limits:
# - 1200 requests per minute (weight-based)
# - 10 orders per second
# - 100,000 orders per 24 hours

# Solution: Implement exponential backoff
import time

def retry_with_backoff(func, max_retries=5):
    for i in range(max_retries):
        try:
            return func()
        except RateLimitError:
            wait_time = 2 ** i
            time.sleep(wait_time)
    raise
```

### Issue 2.2: Interactive Brokers Connection Failure

**Symptoms:**
```python
BrokerConnectionError: Failed to connect to IB Gateway on 127.0.0.1:7497
```

**Solutions:**

**Step 1: Verify IB Gateway is running**
```bash
# Check if IB Gateway/TWS is running
ps aux | grep -i "ib\|tws"

# Start IB Gateway
# (Launch TWS or IB Gateway application)
```

**Step 2: Verify API settings in TWS**
```text
1. Open TWS/IB Gateway
2. Go to Edit > Global Configuration > API > Settings
3. Check "Enable ActiveX and Socket Clients"
4. Add 127.0.0.1 to "Trusted IP Addresses"
5. Set Socket Port: 7497 (paper) or 7496 (live)
```

**Step 3: Check firewall**
```bash
# Allow port 7497 (paper trading)
sudo ufw allow 7497/tcp

# Allow port 7496 (live trading)
sudo ufw allow 7496/tcp
```

### Issue 2.3: CCXT Exchange Not Supported

**Symptoms:**
```python
ExchangeNotSupported: Exchange 'kraken' not available
```

**Solution:**
```bash
# List supported exchanges
python -c "import ccxt; print(ccxt.exchanges)"

# Verify exchange is installed
python -c "import ccxt; exchange = ccxt.binance(); print(exchange.name)"

# Update CCXT to latest version
uv pip install --upgrade ccxt
```

---

## 3. Data Source Issues

### Issue 3.1: Yahoo Finance Data Fetch Fails

**Symptoms:**
```python
DataFetchError: Failed to fetch data for AAPL from yfinance
```

**Solutions:**

**Cause 1: Invalid symbol**
```python
# Verify symbol exists
import yfinance as yf
ticker = yf.Ticker("AAPL")
print(ticker.info)  # Should return company info
```

**Cause 2: Date range too large**
```python
# Reduce date range
# Instead of 10 years:
# data = yf.download("AAPL", start="2014-01-01", end="2024-01-01")

# Try 1 year first:
data = yf.download("AAPL", start="2023-01-01", end="2024-01-01")
```

**Cause 3: Rate limiting**
```python
# Add delays between requests
import time
for symbol in symbols:
    data = yf.download(symbol, start="2023-01-01")
    time.sleep(1)  # 1 second delay
```

### Issue 3.2: Missing Data / Data Gaps

**Symptoms:**
```python
ValidationError: Missing data for 2024-03-15 in OHLCV dataset
```

**Solutions:**

**Option 1: Forward fill**
```python
import polars as pl
data = data.with_columns([
    pl.col("close").forward_fill().alias("close"),
    pl.col("volume").fill_null(0).alias("volume"),
])
```

**Option 2: Drop missing rows**
```python
data = data.drop_nulls(subset=["close"])
```

**Option 3: Interpolate**
```python
data = data.interpolate()
```

### Issue 3.3: Parquet File Corruption

**Symptoms:**
```python
ParquetError: File appears to be corrupted
```

**Solution:**
```bash
# Remove corrupted file
rm ~/.rustybt/data/bundles/parquet/daily/AAPL.parquet

# Re-download data
python -m rustybt fetch-data --source yfinance --symbols AAPL --start 2023-01-01

# Verify integrity
python -c "import polars as pl; df = pl.read_parquet('~/.rustybt/data/bundles/parquet/daily/AAPL.parquet'); print(df.shape)"
```

---

## 4. Order Execution Issues

### Issue 4.1: Order Rejected - Insufficient Funds

**Symptoms:**
```python
OrderRejectedError: Insufficient funds to execute order
```

**Solutions:**

**Step 1: Check account balance**
```python
# Verify available balance
python -m rustybt balance --broker binance

# Compare order value vs. available balance
order_value = price * quantity
print(f"Order value: ${order_value}, Available: ${available_balance}")
```

**Step 2: Reduce position size**
```python
# Adjust MAX_POSITION_SIZE in .env
MAX_POSITION_SIZE=0.05  # Reduce from 10% to 5%
```

**Step 3: Account for fees**
```python
# Include commission in order sizing
commission_rate = 0.001  # 0.1%
order_value_with_fees = order_value * (1 + commission_rate)
```

### Issue 4.2: Order Rejected - Invalid Price

**Symptoms:**
```python
OrderRejectedError: Limit price outside allowed range
```

**Solution:**
```python
# Check tick size and price filters
import ccxt

exchange = ccxt.binance()
markets = exchange.load_markets()
symbol_info = markets['BTC/USDT']

# Verify price meets tick size requirement
tick_size = symbol_info['precision']['price']
limit_price = round(limit_price, tick_size)

# Verify price within min/max limits
min_price = symbol_info['limits']['price']['min']
max_price = symbol_info['limits']['price']['max']
assert min_price <= limit_price <= max_price
```

### Issue 4.3: Order Stuck in Pending State

**Symptoms:**
```python
# Order submitted but never fills
order.status == 'pending'  # for > 5 minutes
```

**Solutions:**

**Option 1: Cancel and resubmit**
```python
# Cancel stuck order
engine.cancel_order(order_id)

# Resubmit as market order
engine.submit_order(asset, amount, order_type='market')
```

**Option 2: Check order book depth**
```python
# Verify liquidity exists
order_book = broker.get_order_book(symbol)
print(f"Bid: {order_book['bids'][0]}, Ask: {order_book['asks'][0]}")
```

**Option 3: Increase timeout**
```python
# Wait longer for limit orders
timeout_seconds = 600  # 10 minutes
```

### Issue 4.4: Position Not Updated After Fill

**Symptoms:**
```python
# Order filled but position not reflected
order.status == 'filled'
position = engine.get_position(asset)  # Returns None or old position
```

**Solution:**
```python
# Force position reconciliation
engine.reconcile_positions()

# Verify with broker API
broker_positions = broker.get_positions()
print(broker_positions)
```

---

## 5. Performance Issues

### Issue 5.1: Slow Backtest Execution

**Symptoms:**
```bash
# Backtest takes > 10 minutes for 1 year, 10 stocks
```

**Solutions:**

**Option 1: Use Polars (not pandas)**
```python
# Switch to Polars-based data portal
from rustybt.data.polars.data_portal import PolarsDataPortal
data_portal = PolarsDataPortal(...)
```

**Option 2: Reduce data frequency**
```python
# Use daily data instead of minute data
bundle = 'polars-parquet-daily'  # Instead of 'polars-parquet-minute'
```

**Option 3: Limit data range**
```python
# Test with smaller date range first
start = pd.Timestamp('2023-01-01')  # Instead of 2014-01-01
end = pd.Timestamp('2024-01-01')
```

**Option 4: Enable Rust optimizations (if Epic 7 complete)**
```bash
# Rebuild with Rust optimizations
RUSTYBT_USE_RUST=1 uv pip install -e ".[all]"
```

### Issue 5.2: High Memory Usage

**Symptoms:**
```bash
# Memory usage grows over time
# htop shows > 8GB RAM used
```

**Solutions:**

**Option 1: Reduce data cache size**
```bash
# Edit .env
DATA_CACHE_SIZE_MB=512  # Reduce from 1024
```

**Option 2: Use lazy evaluation (Polars)**
```python
import polars as pl

# Use lazy frames
df = pl.scan_parquet('data.parquet')
result = df.filter(pl.col('close') > 100).collect()  # Evaluate only when needed
```

**Option 3: Clear cache periodically**
```python
# Clear data catalog cache
data_portal.clear_cache()
```

**Option 4: Check for memory leaks**
```bash
# Run with memory profiler
pip install memory_profiler
python -m memory_profiler backtest_script.py
```

### Issue 5.3: Slow Order Execution (High Latency)

**Symptoms:**
```python
# Order execution latency > 500ms
```

**Solutions:**

**Option 1: Use async broker adapter**
```python
# Ensure using async methods
async def submit_order_async():
    order_id = await broker.submit_order_async(asset, amount)
```

**Option 2: Optimize network**
```bash
# Use closer server (e.g., AWS us-east-1 for US markets)
# Reduce network hops
# Use dedicated server (not shared hosting)
```

**Option 3: Profile code**
```bash
# Find bottlenecks
python -m cProfile -o profile.stats backtest_script.py
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"
```

---

## 6. Security & Authentication Issues

### Issue 6.1: Encryption Key Not Found

**Symptoms:**
```python
EncryptionError: RUSTYBT_ENCRYPTION_KEY not found in environment
```

**Solution:**
```bash
# Generate new encryption key
python -m rustybt keygen

# Copy output to .env
echo "RUSTYBT_ENCRYPTION_KEY=your-key-here" >> .env

# Verify
grep RUSTYBT_ENCRYPTION_KEY .env
```

### Issue 6.2: Permission Denied on .env File

**Symptoms:**
```bash
$ cat .env
cat: .env: Permission denied
```

**Solution:**
```bash
# Fix file permissions
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- (600)
```

### Issue 6.3: API Token Invalid

**Symptoms:**
```python
AuthenticationError: Invalid API token
```

**Solutions:**

**Option 1: Regenerate token**
```bash
python -m rustybt generate-api-token
# Copy new token to .env
```

**Option 2: Verify token format**
```bash
# Token should be base64-encoded, 32+ characters
echo $API_AUTH_TOKEN | wc -c  # Should be >= 32
```

---

## 7. Logging & Monitoring Issues

### Issue 7.1: Logs Not Being Written

**Symptoms:**
```bash
$ ls ~/.rustybt/logs/
ls: cannot access '~/.rustybt/logs/': No such file or directory
```

**Solution:**
```bash
# Create log directory
mkdir -p ~/.rustybt/logs

# Verify permissions
chmod 755 ~/.rustybt/logs

# Verify LOG_DIR in .env
grep LOG_DIR .env
```

### Issue 7.2: Log Files Growing Too Large

**Symptoms:**
```bash
$ du -sh ~/.rustybt/logs/
50G    ~/.rustybt/logs/
```

**Solution:**
```bash
# Configure log rotation (Ubuntu/Debian)
sudo nano /etc/logrotate.d/rustybt

# Add:
/home/user/.rustybt/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 user user
}

# Test
sudo logrotate -d /etc/logrotate.d/rustybt

# Force rotation now
sudo logrotate -f /etc/logrotate.d/rustybt
```

### Issue 7.3: Alerts Not Being Sent

**Symptoms:**
```python
# Critical error occurred but no email/SMS received
```

**Solutions:**

**Step 1: Test alert configuration**
```bash
python -m rustybt test-alerts
```

**Step 2: Check SMTP settings (for email)**
```bash
# Test SMTP connection
python -c "
import smtplib
smtp = smtplib.SMTP('smtp.gmail.com', 587)
smtp.starttls()
smtp.login('your-email@gmail.com', 'your-app-password')
smtp.quit()
print('SMTP connection successful')
"
```

**Step 3: Check alert rules**
```bash
cat ~/.rustybt/config/alerts.yaml
# Verify 'enabled: true' for desired channels
```

---

## 8. State Persistence & Recovery Issues

### Issue 8.1: Strategy State Not Persisted

**Symptoms:**
```python
# After restart, strategy state is lost
context.custom_variable  # AttributeError
```

**Solution:**
```python
# Ensure state persistence enabled
engine = LiveTradingEngine(
    strategy=your_strategy,
    broker=your_broker,
    state_persistence_enabled=True,  # Must be True
    state_persistence_path="~/.rustybt/state/strategy_state.json",
)
```

### Issue 8.2: Cannot Restore from Backup

**Symptoms:**
```bash
$ ./restore-rustybt.sh backup.tar.gz
tar: Error opening archive: Failed to open 'backup.tar.gz'
```

**Solutions:**

**Option 1: Verify backup file exists**
```bash
ls -lh backup.tar.gz
file backup.tar.gz  # Should show "gzip compressed data"
```

**Option 2: Test backup integrity**
```bash
tar -tzf backup.tar.gz  # List contents without extracting
```

**Option 3: Download from offsite storage**
```bash
# If backup on AWS S3
aws s3 cp s3://your-backup-bucket/rustybt/backup.tar.gz ./
```

---

## 9. Common Error Messages

### Error: `ModuleNotFoundError: No module named 'rustybt'`

**Cause**: Virtual environment not activated or RustyBT not installed

**Solution**:
```bash
# Activate virtual environment
source .venv/bin/activate

# Install RustyBT
uv pip install -e ".[all]"
```

### Error: `ValueError: Asset not found: AAPL`

**Cause**: Asset not in asset database

**Solution**:
```python
# Register asset
from rustybt.assets import Asset
asset = Asset(symbol='AAPL', exchange='NASDAQ')
asset_db.write_asset(asset)
```

### Error: `LookaheadError: Attempted to access future data`

**Cause**: Strategy accessing data from the future (look-ahead bias)

**Solution**:
```python
# Ensure all data access uses current or past timestamps
current_time = context.current_dt
price = data.current(asset, 'close')  # Correct
# NOT: price = data.history(asset, 'close', 1, '1d')[0]  # May cause lookahead
```

### Error: `CircuitBreakerTripped: Daily loss limit reached`

**Cause**: Strategy exceeded daily loss limit

**Solution**:
```bash
# Review strategy performance
python -m rustybt analyze-trades

# Adjust risk limits if necessary
nano .env  # Increase MAX_DAILY_LOSS if appropriate

# Investigate why loss occurred (bug in strategy? market crash?)
```

### Error: `DatabaseLockedError: database is locked`

**Cause**: Multiple processes accessing SQLite database

**Solution**:
```bash
# Stop all RustyBT processes
pkill -f rustybt

# Wait a few seconds
sleep 5

# Restart
python -m rustybt live-trade --strategy momentum.py
```

---

## 10. Log Interpretation Guide

### Log Format

RustyBT uses structured JSON logging in production:

```json
{
  "timestamp": "2025-01-31T14:30:45.123Z",
  "level": "INFO",
  "event": "order_filled",
  "order_id": "12345",
  "asset": "AAPL",
  "amount": "100.0",
  "fill_price": "150.25",
  "commission": "0.10"
}
```

### Key Log Events

#### Order Events
```json
// Order submitted
{"event": "order_submitted", "order_id": "123", "asset": "AAPL", "amount": "100"}

// Order filled
{"event": "order_filled", "order_id": "123", "fill_price": "150.25"}

// Order rejected
{"event": "order_rejected", "order_id": "123", "reason": "insufficient_funds"}

// Order cancelled
{"event": "order_cancelled", "order_id": "123", "reason": "user_requested"}
```

#### Error Events
```json
// Broker connection error
{"event": "broker_connection_error", "broker": "binance", "error": "Connection timeout"}

// Data fetch error
{"event": "data_fetch_error", "source": "yfinance", "symbol": "AAPL", "error": "Rate limit"}

// Circuit breaker trip
{"event": "circuit_breaker_trip", "reason": "daily_loss_limit", "loss_pct": "5.2"}
```

#### Position Events
```json
// Position opened
{"event": "position_opened", "asset": "AAPL", "amount": "100", "cost_basis": "150.00"}

// Position closed
{"event": "position_closed", "asset": "AAPL", "pnl": "250.50"}
```

### Log Analysis Commands

```bash
# Count errors in last 24 hours
grep '"level":"ERROR"' ~/.rustybt/logs/rustybt.log | wc -l

# Find all order rejections
grep '"event":"order_rejected"' ~/.rustybt/logs/rustybt.log

# Calculate uptime
python -m rustybt analyze-uptime --log-dir ~/.rustybt/logs --start-date 2025-01-01

# Find slow operations (> 1 second)
grep '"duration_ms"' ~/.rustybt/logs/rustybt.log | awk -F'"duration_ms":' '{print $2}' | awk '{if($1 > 1000) print}'
```

---

## Getting Additional Help

If your issue is not covered in this guide:

1. **Check Logs**: Review `~/.rustybt/logs/rustybt.log` for detailed error messages
2. **Search GitHub Issues**: https://github.com/yourusername/rustybt/issues
3. **Community Support**: [Discord/Slack link]
4. **Open New Issue**: Provide:
   - RustyBT version: `python -c "import rustybt; print(rustybt.__version__)"`
   - Python version: `python --version`
   - OS: `uname -a` (Linux/macOS) or `systeminfo` (Windows)
   - Full error traceback
   - Relevant log entries
   - Steps to reproduce

---

**Last Updated**: 2025-10-11
**Version**: 1.0
**Maintained By**: RustyBT Development Team
