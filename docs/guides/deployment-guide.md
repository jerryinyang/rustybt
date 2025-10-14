# RustyBT Production Deployment Guide

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Environment Setup](#2-environment-setup)
3. [Configuration](#3-configuration)
4. [Security Hardening](#4-security-hardening)
5. [Monitoring Setup](#5-monitoring-setup)
6. [Backup & Disaster Recovery](#6-backup-disaster-recovery)
7. [Deployment Verification](#7-deployment-verification)
8. [Going Live](#8-going-live)

---

## 1. Prerequisites

### Hardware Requirements
- **Minimum**:
  - CPU: 2 cores (x86_64)
  - RAM: 8GB
  - Disk: 50GB SSD
  - Network: Stable internet connection (1 Mbps minimum)

- **Recommended**:
  - CPU: 4+ cores (x86_64)
  - RAM: 16GB+
  - Disk: 100GB+ SSD
  - Network: High-speed internet (10+ Mbps)

### Operating System
- **Supported**:
  - Ubuntu 22.04 LTS or 24.04 LTS (recommended)
  - Debian 12+
  - macOS 13+ (Ventura or later)
  - Windows 11 with WSL2 (Ubuntu 22.04)

- **Not Recommended**:
  - Windows native (use WSL2 instead)
  - macOS < 13 (Python 3.12 compatibility issues)

### Software Prerequisites
- Python 3.12+ (required)
- Rust 1.90+ (optional, for Rust optimizations)
- uv package manager 0.5.x+ (required)
- Git 2.30+ (for version control)
- SQLite 3.35+ (bundled with Python)

---

## 2. Environment Setup

### Step 1: Install Python 3.12+

#### Ubuntu/Debian
```bash
# Update package list
sudo apt update

# Install Python 3.12
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# Verify installation
python3.12 --version  # Should show 3.12.x
```

#### macOS
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.12
brew install python@3.12

# Verify installation
python3.12 --version  # Should show 3.12.x
```

#### Windows (WSL2)
```bash
# Open WSL2 Ubuntu terminal
# Follow Ubuntu/Debian instructions above
```

### Step 2: Install Rust (Optional, for Performance Optimizations)

```bash
# Install Rust using rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Source cargo environment
source "$HOME/.cargo/env"

# Verify installation
rustc --version  # Should show 1.90.x or later

# Install required Rust components
rustup component add rustfmt clippy
```

### Step 3: Install uv Package Manager

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (add to ~/.bashrc or ~/.zshrc for persistence)
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
uv --version  # Should show 0.5.x or later
```

### Step 4: Clone RustyBT Repository

```bash
# Clone from GitHub
git clone https://github.com/yourusername/rustybt.git
cd rustybt

# Verify you're on the correct branch
git branch
```

### Step 5: Create Virtual Environment

```bash
# Create virtual environment with Python 3.12
uv venv --python 3.12

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Verify Python version
python --version  # Should show 3.12.x
```

### Step 6: Install Dependencies

```bash
# Install RustyBT with all optional dependencies
uv pip install -e ".[all]"

# This installs:
# - Core dependencies (polars, pandas, numpy, etc.)
# - Live trading dependencies (ccxt, ib_async, etc.)
# - Development dependencies (pytest, mypy, ruff, etc.)

# Verify installation
python -c "import rustybt; print(rustybt.__version__)"
```

### Step 7: Verify Installation

```bash
# Run basic test suite to verify installation
pytest tests/ -v --tb=short

# Run type checking
mypy rustybt/ --strict

# Run linting
ruff check rustybt/
```

---

## 3. Configuration

### Step 1: Create Configuration Directory

```bash
# Create config directory (if not exists)
mkdir -p ~/.rustybt/config
mkdir -p ~/.rustybt/data
mkdir -p ~/.rustybt/logs
mkdir -p ~/.rustybt/state
```

### Step 2: Create Environment File

Create a `.env` file in the project root:

```bash
# Copy example environment file
cp .env.example .env

# Edit with your configuration
nano .env  # or use your preferred editor
```

#### Example .env File Template

```bash
# ========================================
# RustyBT Configuration
# ========================================

# Encryption Key (generate with: python -m rustybt keygen)
RUSTYBT_ENCRYPTION_KEY=your-encryption-key-here

# ========================================
# Broker Configuration
# ========================================

# Binance
BINANCE_API_KEY=your-binance-api-key
BINANCE_API_SECRET=your-binance-api-secret
BINANCE_TESTNET=false  # Set to true for paper trading

# Bybit
BYBIT_API_KEY=your-bybit-api-key
BYBIT_API_SECRET=your-bybit-api-secret
BYBIT_TESTNET=false

# Interactive Brokers
IB_ACCOUNT=your-ib-account-number
IB_HOST=127.0.0.1
IB_PORT=7497  # 7497 for paper, 7496 for live
IB_CLIENT_ID=1

# ========================================
# Data Source Configuration
# ========================================

# Yahoo Finance (free, no API key needed)
YFINANCE_ENABLED=true

# CCXT (for crypto data)
CCXT_ENABLED=true

# Custom data sources
CUSTOM_DATA_PATH=~/.rustybt/data/custom

# ========================================
# Risk Limits Configuration
# ========================================

# Maximum position size (as fraction of portfolio)
MAX_POSITION_SIZE=0.10  # 10% of portfolio

# Maximum daily loss limit (as fraction of portfolio)
MAX_DAILY_LOSS=0.05  # 5% of portfolio

# Maximum leverage
MAX_LEVERAGE=1.0  # No leverage by default

# Maximum number of open positions
MAX_OPEN_POSITIONS=10

# ========================================
# Trading Calendar Configuration
# ========================================

# Trading calendar (NYSE, NASDAQ, 24/7)
TRADING_CALENDAR=NYSE  # or NASDAQ, or 24/7 for crypto

# Trading hours (for custom calendars)
MARKET_OPEN=09:30
MARKET_CLOSE=16:00
TIMEZONE=America/New_York

# ========================================
# Logging Configuration
# ========================================

# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Log directory
LOG_DIR=~/.rustybt/logs

# Log retention (days)
LOG_RETENTION_DAYS=90

# Structured logging format (json, text)
LOG_FORMAT=json

# ========================================
# API Configuration (Epic 9)
# ========================================

# REST API enabled
API_ENABLED=false

# API host and port
API_HOST=0.0.0.0
API_PORT=8000

# API authentication token
API_AUTH_TOKEN=your-api-token-here

# ========================================
# Performance Configuration
# ========================================

# Data catalog cache size (MB)
DATA_CACHE_SIZE_MB=1024

# Number of worker threads
NUM_WORKERS=4

# Database connection pool size
DB_POOL_SIZE=5
```

### Step 3: Configure Broker Connections

#### Binance Configuration
1. Log in to Binance account
2. Navigate to API Management
3. Create new API key with trading permissions
4. Enable IP whitelist for security
5. Copy API key and secret to `.env` file

#### Interactive Brokers Configuration
1. Install IB Gateway or Trader Workstation
2. Enable API connections in settings
3. Configure socket port (7497 for paper, 7496 for live)
4. Note your account number
5. Update `.env` file with connection details

### Step 4: Configure Risk Limits

Edit risk limits in `.env` file based on your risk tolerance:

```bash
# Conservative settings
MAX_POSITION_SIZE=0.05  # 5% per position
MAX_DAILY_LOSS=0.02     # 2% daily loss limit
MAX_LEVERAGE=1.0        # No leverage

# Moderate settings
MAX_POSITION_SIZE=0.10  # 10% per position
MAX_DAILY_LOSS=0.05     # 5% daily loss limit
MAX_LEVERAGE=2.0        # 2x leverage

# Aggressive settings (NOT RECOMMENDED)
MAX_POSITION_SIZE=0.20  # 20% per position
MAX_DAILY_LOSS=0.10     # 10% daily loss limit
MAX_LEVERAGE=5.0        # 5x leverage
```

### Step 5: Test Configuration

```bash
# Test broker connection
python -m rustybt test-broker --broker binance

# Test data source connection
python -m rustybt test-data --source yfinance

# Verify risk limits configuration
python -m rustybt verify-config
```

---

## 4. Security Hardening

### Step 1: Generate Encryption Key

```bash
# Generate strong encryption key
python -m rustybt keygen

# This generates a Fernet key for credential encryption
# Copy the output to RUSTYBT_ENCRYPTION_KEY in .env
```

### Step 2: Encrypt Credentials

```bash
# Encrypt broker credentials at rest
python -m rustybt encrypt-credentials

# This encrypts API keys/secrets in local storage
# Original plaintext credentials in .env can now be removed (optional)
```

### Step 3: Configure Firewall

#### Ubuntu/Debian
```bash
# Enable UFW firewall
sudo ufw enable

# Allow SSH (change 22 to your SSH port if different)
sudo ufw allow 22/tcp

# Allow API port (if Epic 9 implemented)
sudo ufw allow 8000/tcp

# Deny all other incoming connections
sudo ufw default deny incoming

# Allow all outgoing connections
sudo ufw default allow outgoing

# Verify firewall status
sudo ufw status verbose
```

#### macOS
```bash
# Enable macOS firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on

# Enable stealth mode
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on

# Verify firewall status
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
```

### Step 4: Configure SSH Key-Based Authentication

```bash
# Generate SSH key pair (if not already exists)
ssh-keygen -t ed25519 -C "your-email@example.com"

# Copy public key to server
ssh-copy-id user@your-server-ip

# Disable password authentication on server
sudo nano /etc/ssh/sshd_config

# Set these values:
# PasswordAuthentication no
# PubkeyAuthentication yes
# PermitRootLogin no

# Restart SSH service
sudo systemctl restart sshd
```

### Step 5: Secure File Permissions

```bash
# Secure .env file (only owner can read/write)
chmod 600 .env

# Secure config directory
chmod 700 ~/.rustybt/config

# Secure state directory (contains strategy state)
chmod 700 ~/.rustybt/state

# Secure log directory
chmod 700 ~/.rustybt/logs
```

### Step 6: API Authentication (if Epic 9 implemented)

```bash
# Generate API authentication token
python -m rustybt generate-api-token

# Copy token to .env file (API_AUTH_TOKEN)

# Enable HTTPS for API
# Install certbot for Let's Encrypt SSL certificate
sudo apt install certbot  # Ubuntu/Debian

# Generate SSL certificate
sudo certbot certonly --standalone -d your-domain.com
```

### Step 7: Secrets Management

**Best Practices:**
1. Never commit `.env` file to version control
2. Use environment variables for sensitive data
3. Consider using a secrets manager (AWS Secrets Manager, HashiCorp Vault)
4. Rotate API keys regularly (every 90 days recommended)
5. Use separate API keys for development, staging, and production

**Example secrets manager integration:**
```python
# Example: AWS Secrets Manager integration
import boto3
import json

def get_broker_credentials(secret_name: str) -> dict:
    """Retrieve broker credentials from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
credentials = get_broker_credentials('production/binance/api-keys')
api_key = credentials['api_key']
api_secret = credentials['api_secret']
```

---

## 5. Monitoring Setup

### Step 1: Configure Structured Logging

RustyBT uses `structlog` for structured logging. Configure logging in `.env`:

```bash
# Log level
LOG_LEVEL=INFO  # DEBUG for development, INFO for production

# Log format
LOG_FORMAT=json  # json for production, text for development

# Log directory
LOG_DIR=~/.rustybt/logs

# Log retention
LOG_RETENTION_DAYS=90  # Keep logs for 90 days
```

### Step 2: Set Up Log Rotation

#### Using logrotate (Ubuntu/Debian)
```bash
# Create logrotate config
sudo nano /etc/logrotate.d/rustybt

# Add configuration:
/home/user/.rustybt/logs/*.log {
    daily
    rotate 90
    compress
    delaycompress
    notifempty
    create 0640 user user
    sharedscripts
    postrotate
        # Restart RustyBT if running
        systemctl reload rustybt || true
    endscript
}

# Test logrotate configuration
sudo logrotate -d /etc/logrotate.d/rustybt
```

### Step 3: Configure Alert Notifications

Create alert configuration file:

```bash
# Create alerts config
nano ~/.rustybt/config/alerts.yaml
```

```yaml
# alerts.yaml
alerts:
  email:
    enabled: true
    smtp_host: smtp.gmail.com
    smtp_port: 587
    smtp_user: your-email@gmail.com
    smtp_password: your-app-password
    from_address: rustybt-alerts@yourdomain.com
    to_addresses:
      - your-email@gmail.com
      - backup-email@gmail.com

  sms:
    enabled: false
    provider: twilio  # twilio, aws_sns
    account_sid: your-twilio-account-sid
    auth_token: your-twilio-auth-token
    from_number: +1234567890
    to_numbers:
      - +1234567890

  slack:
    enabled: false
    webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
    channel: "#trading-alerts"

# Alert rules
rules:
  critical_errors:
    level: CRITICAL
    notify: [email, sms, slack]

  broker_connection_failure:
    level: ERROR
    notify: [email, slack]

  circuit_breaker_trip:
    level: WARNING
    notify: [email, slack]

  order_rejection:
    level: WARNING
    notify: [email]

  daily_loss_limit_reached:
    level: CRITICAL
    notify: [email, sms, slack]
```

### Step 4: Configure Health Check Endpoint (if API enabled)

```python
# Example health check endpoint
from fastapi import FastAPI, status

app = FastAPI()

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": rustybt.__version__,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status."""
    return {
        "status": "healthy",
        "components": {
            "database": check_database_connection(),
            "broker": check_broker_connection(),
            "data_sources": check_data_sources(),
        },
        "metrics": {
            "uptime_seconds": get_uptime_seconds(),
            "memory_usage_mb": get_memory_usage_mb(),
        }
    }
```

### Step 5: Set Up Monitoring Dashboard (Optional)

#### Using Grafana
```bash
# Install Grafana (Ubuntu/Debian)
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo apt-get update
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Access Grafana at http://localhost:3000
# Default credentials: admin/admin
```

#### Key Metrics to Monitor
1. **System Metrics**:
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network latency

2. **Application Metrics**:
   - Order execution latency
   - Number of active orders
   - Portfolio value
   - Daily P&L
   - Error rate
   - Circuit breaker trips

3. **Broker Metrics**:
   - Broker connection status
   - Order fill rate
   - Order rejection rate
   - API rate limits

### Step 6: Configure Uptime Monitoring

Use external monitoring service:

**Example: UptimeRobot configuration**
1. Create account at uptimerobot.com
2. Add HTTP(s) monitor for health check endpoint
3. Set monitoring interval (1 minute recommended)
4. Configure alert contacts (email, SMS)
5. Set up status page (optional)

---

## 6. Backup & Disaster Recovery

### Step 1: Understand What to Backup

**Critical Data:**
1. **Strategy State**: Algorithm variables, internal state
2. **Position State**: Open positions, pending orders
3. **Configuration**: .env file, strategy configs
4. **Trade History**: Completed trades, fills
5. **Logs**: Error logs, audit logs (7-year retention required)

**Non-Critical Data (can be regenerated):**
1. Market data (OHLCV bars)
2. Cached calculations
3. Temporary files

### Step 2: Configure State Persistence

```python
# Example: State persistence configuration
from rustybt.live import LiveTradingEngine

engine = LiveTradingEngine(
    strategy=your_strategy,
    broker=your_broker,
    state_persistence_enabled=True,
    state_persistence_path="~/.rustybt/state/strategy_state.json",
    checkpoint_interval_seconds=60,  # Save state every 60 seconds
)
```

### Step 3: Set Up Automated Backups

Create backup script:

```bash
#!/bin/bash
# backup-rustybt.sh

# Configuration
BACKUP_DIR="/backup/rustybt"
RUSTYBT_HOME="$HOME/.rustybt"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="rustybt_backup_$DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

# Backup state directory (critical)
cp -r "$RUSTYBT_HOME/state" "$BACKUP_DIR/$BACKUP_NAME/"

# Backup config directory (critical)
cp -r "$RUSTYBT_HOME/config" "$BACKUP_DIR/$BACKUP_NAME/"

# Backup logs (critical for audit)
cp -r "$RUSTYBT_HOME/logs" "$BACKUP_DIR/$BACKUP_NAME/"

# Backup .env file (critical)
cp .env "$BACKUP_DIR/$BACKUP_NAME/"

# Compress backup
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"

# Remove uncompressed backup
rm -rf "$BACKUP_DIR/$BACKUP_NAME"

# Upload to offsite storage (AWS S3 example)
aws s3 cp "$BACKUP_DIR/$BACKUP_NAME.tar.gz" s3://your-backup-bucket/rustybt/

# Keep only last 30 days of local backups
find "$BACKUP_DIR" -name "rustybt_backup_*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_NAME.tar.gz"
```

### Step 4: Schedule Daily Backups

```bash
# Add to crontab
crontab -e

# Add line (runs daily at 2 AM):
0 2 * * * /path/to/backup-rustybt.sh >> /var/log/rustybt-backup.log 2>&1
```

### Step 5: Test Restore Procedure

```bash
# Test restore procedure
#!/bin/bash
# restore-rustybt.sh

BACKUP_FILE="$1"
RUSTYBT_HOME="$HOME/.rustybt"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    exit 1
fi

# Extract backup
TEMP_DIR=$(mktemp -d)
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Restore state (critical)
cp -r "$TEMP_DIR"/*/state/* "$RUSTYBT_HOME/state/"

# Restore config (critical)
cp -r "$TEMP_DIR"/*/config/* "$RUSTYBT_HOME/config/"

# Restore .env (critical)
cp "$TEMP_DIR"/*/.env .env

# Restore logs (for audit purposes)
cp -r "$TEMP_DIR"/*/logs/* "$RUSTYBT_HOME/logs/"

# Clean up
rm -rf "$TEMP_DIR"

echo "Restore completed from $BACKUP_FILE"
```

### Step 6: Offsite Backup Storage

**Option 1: AWS S3**
```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure

# Upload backups to S3
aws s3 sync /backup/rustybt s3://your-backup-bucket/rustybt/

# Enable versioning on S3 bucket (protects against accidental deletion)
aws s3api put-bucket-versioning --bucket your-backup-bucket --versioning-configuration Status=Enabled
```

**Option 2: Google Cloud Storage**
```bash
# Install gcloud CLI
# Follow: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Upload backups
gsutil -m rsync -r /backup/rustybt gs://your-backup-bucket/rustybt/
```

### Step 7: Disaster Recovery Plan

**Scenario 1: Server Hardware Failure**
1. Provision new server with same OS
2. Install Python, Rust, uv (follow Section 2)
3. Clone RustyBT repository
4. Restore latest backup (state, config, .env)
5. Verify broker connection
6. Reconcile positions with broker
7. Resume trading

**Scenario 2: Data Corruption**
1. Stop trading engine immediately
2. Restore from most recent uncorrupted backup
3. Reconcile positions with broker API
4. Verify trade history matches broker records
5. Resume trading

**Scenario 3: Security Breach (API Key Compromised)**
1. Immediately revoke compromised API keys
2. Close all open positions (if suspicious activity detected)
3. Generate new API keys
4. Update .env file with new credentials
5. Encrypt new credentials
6. Conduct security audit
7. Resume trading with new credentials

**Scenario 4: Extended Downtime (Vacation, Emergency)**
1. Close all positions before planned downtime
2. Disable automatic trading
3. Set up monitoring alerts
4. Document restart procedure
5. Test restart procedure before resuming

### Step 8: Test Disaster Recovery Procedures

```bash
# Test restore on clean system quarterly
# 1. Provision test VM
# 2. Restore from backup
# 3. Verify functionality
# 4. Document any issues
# 5. Update disaster recovery plan
```

---

## 7. Deployment Verification

### Step 1: Run Test Suite

```bash
# Activate virtual environment
source .venv/bin/activate

# Run full test suite
pytest tests/ -v --cov=rustybt --cov-report=html

# Verify coverage >= 90%
```

### Step 2: Run Type Checking

```bash
# Run mypy with strict mode
mypy rustybt/ --strict

# Should report no errors
```

### Step 3: Run Linting

```bash
# Run ruff linter
ruff check rustybt/

# Run black formatter check
black --check rustybt/

# Should report no errors
```

### Step 4: Run Security Audit

```bash
# Install security tools
pip install bandit safety

# Run bandit (Python security linter)
bandit -r rustybt/ -ll -i

# Run safety (checks for known vulnerabilities)
safety check --json

# Should report no high-severity issues
```

### Step 5: Test Broker Connection

```bash
# Test broker connection (paper trading)
python -m rustybt test-broker --broker binance --testnet

# Verify:
# - Connection succeeds
# - Account balance retrieved
# - Test order placed and filled
```

### Step 6: Test Data Ingestion

```bash
# Test data connectivity with yfinance
python -m rustybt test-data --source yfinance --symbol AAPL
python -m rustybt test-data --source yfinance --symbol MSFT

# Verify data source is accessible
```

### Step 7: Run Paper Trading Validation

```bash
# Run paper trading for 30 days
python -m rustybt paper-trade \
    --strategy momentum.py \
    --broker binance \
    --duration 30d \
    --log-level INFO

# Monitor logs for errors
tail -f ~/.rustybt/logs/rustybt.log

# Measure uptime and error rate
python -m rustybt analyze-uptime \
    --log-dir ~/.rustybt/logs \
    --start-date 2025-01-01 \
    --end-date 2025-01-30

# Target: 99.9% uptime (< 43 minutes downtime per 30 days)
```

### Step 8: Performance Validation

```bash
# Run performance benchmarks
python -m rustybt benchmark \
    --suite backtest \
    --iterations 10

# Verify performance meets targets:
# - Backtest execution time acceptable
# - Order execution latency < 100ms
# - Memory usage stable (no leaks)

# Example expected output:
# Backtest (1 year, 10 stocks): 2.5 seconds
# Order execution latency: 45ms (avg)
# Memory usage: 250MB (stable)
```

---

## 8. Going Live

### Step 1: Complete Production Readiness Checklist

Review and complete all items in `docs/production-checklist.md` (see Section 8 of this guide).

**Critical items:**
- [ ] All tests pass (90%+ coverage)
- [ ] Security audit complete (no high-severity issues)
- [ ] Paper trading validation complete (99.9% uptime)
- [ ] Backup and restore procedures tested
- [ ] Monitoring and alerts configured
- [ ] Team trained on platform operation

### Step 2: Switch to Live Trading Mode

```bash
# Update .env file
# Change BINANCE_TESTNET=false (or equivalent for your broker)

# Verify risk limits are appropriate for live trading
nano .env  # Review MAX_POSITION_SIZE, MAX_DAILY_LOSS, etc.
```

### Step 3: Start with Small Position Sizes

```bash
# Reduce risk limits for initial live trading period (1-2 weeks)
MAX_POSITION_SIZE=0.01  # 1% per position (conservative)
MAX_DAILY_LOSS=0.005    # 0.5% daily loss limit
```

### Step 4: Start Live Trading Engine

```bash
# Start live trading (run in tmux or screen for persistence)
tmux new -s rustybt-live

# Activate virtual environment
source .venv/bin/activate

# Start live trading
python -m rustybt live-trade \
    --strategy momentum.py \
    --broker binance \
    --log-level INFO

# Detach from tmux: Ctrl+B, then D
# Reattach later: tmux attach -t rustybt-live
```

### Step 5: Monitor Closely for First 24-48 Hours

```bash
# Monitor logs in real-time
tail -f ~/.rustybt/logs/rustybt.log

# Check portfolio status
python -m rustybt status

# Monitor alerts (check email/SMS/Slack)
```

### Step 6: Gradually Increase Position Sizes

After successful initial period (1-2 weeks):

1. Week 1-2: 1% position sizes
2. Week 3-4: 3% position sizes
3. Week 5+: Target position sizes (5-10%)

### Step 7: Ongoing Maintenance

**Daily:**
- Check logs for errors
- Verify positions match broker API
- Review P&L

**Weekly:**
- Review performance metrics
- Check backup completion
- Review security logs

**Monthly:**
- Rotate API keys
- Review disaster recovery plan
- Update dependencies (security patches)

**Quarterly:**
- Test disaster recovery procedures
- Security audit
- Performance benchmark

---

## Additional Resources

- **Production Checklist**: See [Production Checklist](production-checklist.md)
- **User Guides**: See [User Guides](../guides/decimal-precision-configuration.md)
- **Examples**: See [Examples & Tutorials](../examples/README.md)

---

## Support

For issues or questions:
1. Review logs: `~/.rustybt/logs/rustybt.log`
2. Open GitHub issue: https://github.com/jerryinyang/rustybt/issues
3. Check documentation: https://jerryinyang.github.io/rustybt

---

**Last Updated**: 2025-10-11
**Version**: 1.0
**Maintained By**: RustyBT Development Team
