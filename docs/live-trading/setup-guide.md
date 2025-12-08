# Live Trading Setup Guide

This comprehensive guide walks you through setting up rustybt for live trading on all supported platforms.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Platform Setup](#platform-setup)
  - [Binance](#binance)
  - [Bybit](#bybit)
  - [Hyperliquid](#hyperliquid)
  - [Lighter.xyz](#lighterxyz)
  - [Interactive Brokers](#interactive-brokers)
- [Security Best Practices](#security-best-practices)
- [Configuration File](#configuration-file)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

---

## Overview

rustybt supports live trading on multiple centralized and decentralized exchanges. Each platform requires specific authentication credentials and configuration.

| Platform | Type | Authentication | Markets |
|----------|------|----------------|---------|
| [Binance](#binance) | CEX | API Key + Secret | Spot, Futures |
| [Bybit](#bybit) | CEX | API Key + Secret | Spot, Derivatives |
| [Hyperliquid](#hyperliquid) | DEX | ETH Private Key | Perpetual Futures |
| [Lighter.xyz](#lighterxyz) | DEX | ETH Private Key + API Key | Perpetual Futures |
| [Interactive Brokers](#interactive-brokers) | Traditional | TWS/Gateway | Stocks, Futures, Options |

---

## Prerequisites

Before setting up live trading, ensure you have:

1. **Python 3.12+** installed
2. **rustybt installed** with live trading extras:
   ```bash
   pip install rustybt[live]
   ```
3. **Exchange account(s)** with API access enabled
4. **Understanding of risks** - Live trading involves real capital

> **Warning**: Always test with paper trading or testnet before using real funds. Never trade with capital you cannot afford to lose.

---

## Platform Setup

### Binance

Binance is a leading centralized cryptocurrency exchange supporting both spot and futures trading.

#### Account Setup

1. Create a Binance account at [binance.com](https://www.binance.com)
2. Complete identity verification (KYC)
3. Enable two-factor authentication (2FA)

#### API Key Generation

1. Go to **Account** → **API Management**
2. Click **Create API**
3. Select **System generated** for key type
4. Enter a label (e.g., "rustybt-trading")
5. Complete 2FA verification
6. **Copy both API Key and Secret** - the secret is shown only once!

#### API Key Permissions

Configure the minimum required permissions:

| Permission | Required | Purpose |
|------------|----------|---------|
| Enable Reading | ✅ Yes | Position and balance queries |
| Enable Spot & Margin Trading | ✅ For spot | Spot order execution |
| Enable Futures | ✅ For futures | Futures order execution |
| Enable Withdrawals | ❌ **Never** | Not needed - security risk |
| Enable IP Whitelist | ✅ Recommended | Restrict to your server IPs |

#### Environment Variables

```bash
# Mainnet (PRODUCTION - use with caution)
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_SECRET="your_api_secret_here"

# Testnet (recommended for testing)
export BINANCE_TESTNET_API_KEY="your_testnet_api_key"
export BINANCE_TESTNET_SECRET="your_testnet_secret"
```

#### Testnet vs Mainnet

| Environment | API Endpoint | Purpose |
|-------------|--------------|---------|
| Spot Mainnet | api.binance.com | Production trading |
| Futures Mainnet | fapi.binance.com | Production futures |
| Spot Testnet | testnet.binance.vision | Testing |
| Futures Testnet | testnet.binancefuture.com | Futures testing |

```python
from rustybt.live.brokers import BinanceBrokerAdapter

# Testnet (recommended for testing)
adapter = BinanceBrokerAdapter(
    api_key=os.environ["BINANCE_TESTNET_API_KEY"],
    api_secret=os.environ["BINANCE_TESTNET_SECRET"],
    market_type="futures",
    testnet=True,  # Use testnet
)

# Mainnet (production)
adapter = BinanceBrokerAdapter(
    api_key=os.environ["BINANCE_API_KEY"],
    api_secret=os.environ["BINANCE_SECRET"],
    market_type="futures",
    testnet=False,  # Use mainnet
)
```

#### Rate Limits

| Limit Type | Value | Notes |
|------------|-------|-------|
| REST API | 1200 req/min | Weight-based system |
| Orders | 100/10 sec/symbol | Per trading pair |
| WebSocket | 5 messages/sec | Subscription changes |

---

### Bybit

Bybit is a cryptocurrency derivatives exchange supporting perpetual futures and spot trading.

#### Account Setup

1. Create a Bybit account at [bybit.com](https://www.bybit.com)
2. Complete identity verification
3. Enable 2FA (Google Authenticator recommended)

#### API Key Generation

1. Go to **Account** → **API** (or Profile → API Management)
2. Click **Create New Key**
3. Select **System-generated API Keys**
4. Configure permissions:
   - ✅ Read
   - ✅ Trade
   - ✅ Position
   - ❌ Withdraw (never enable)
5. Complete 2FA verification
6. **Copy API Key and Secret** - secret shown only once!

#### Environment Variables

```bash
# Mainnet
export BYBIT_API_KEY="your_api_key_here"
export BYBIT_SECRET="your_api_secret_here"

# Testnet
export BYBIT_TESTNET_API_KEY="your_testnet_api_key"
export BYBIT_TESTNET_SECRET="your_testnet_secret"
```

#### Python Configuration

```python
from rustybt.live.brokers import BybitBrokerAdapter

# Testnet
adapter = BybitBrokerAdapter(
    api_key=os.environ["BYBIT_TESTNET_API_KEY"],
    api_secret=os.environ["BYBIT_TESTNET_SECRET"],
    category="linear",  # linear, inverse, spot
    testnet=True,
)

# Mainnet
adapter = BybitBrokerAdapter(
    api_key=os.environ["BYBIT_API_KEY"],
    api_secret=os.environ["BYBIT_SECRET"],
    category="linear",
    testnet=False,
)
```

#### Rate Limits

| Limit Type | Value |
|------------|-------|
| REST API | 120 req/min |
| Orders | 100/sec/symbol |
| WebSocket | 10 messages/sec |

---

### Hyperliquid

Hyperliquid is a decentralized exchange (DEX) for perpetual futures, using Ethereum private keys for authentication.

#### Wallet Setup

Hyperliquid uses Ethereum wallets for authentication. You have two options:

1. **API Wallet (Recommended)** - Dedicated wallet for trading, cannot withdraw
2. **Main Wallet** - Your primary Ethereum wallet (not recommended for bots)

##### Creating a New Wallet

```python
from eth_account import Account

# Generate new wallet
account = Account.create()
print(f"Address: {account.address}")
print(f"Private Key: {account.key.hex()}")
# Save these securely! The private key is shown only once.
```

##### Creating an API Wallet (Recommended)

1. Go to [app.hyperliquid.xyz](https://app.hyperliquid.xyz)
2. Connect your main wallet
3. Navigate to **API** section
4. Click **Create API Wallet**
5. Name your wallet (e.g., "rustybt-trading")
6. **Copy the private key** - shown only once!
7. Click **Authorize** to enable trading

#### Private Key Configuration

```bash
# The API wallet private key (recommended) - 66 chars with 0x prefix
export HYPERLIQUID_PRIVATE_KEY="0x1234567890abcdef..."

# Your main wallet address (for account queries)
export HYPERLIQUID_WALLET_ADDRESS="0xYourMainWalletAddress"
```

#### Using Encrypted Keystores

For enhanced security, use encrypted keystores:

```bash
# Path to encrypted keystore file
export HYPERLIQUID_ENCRYPTED_KEY_PATH="/path/to/keystore.enc"

# Encryption key (separate from the private key)
export HYPERLIQUID_ENCRYPTION_KEY="your_encryption_key"
```

Creating an encrypted keystore:

```python
from cryptography.fernet import Fernet

# Generate encryption key (save this separately and securely!)
encryption_key = Fernet.generate_key()
print(f"Encryption Key: {encryption_key.decode()}")

# Encrypt your private key
fernet = Fernet(encryption_key)
private_key = "0x1234..."  # Your private key
encrypted = fernet.encrypt(private_key.encode())

# Save to file
with open("keystore.enc", "wb") as f:
    f.write(encrypted)
```

#### Python Configuration

```python
from rustybt.live.brokers import HyperliquidBrokerAdapter
import os

# Option 1: Environment variable (recommended)
adapter = HyperliquidBrokerAdapter(
    testnet=False,  # True for testnet
)

# Option 2: Encrypted keystore
adapter = HyperliquidBrokerAdapter(
    encrypted_key_path="/path/to/keystore.enc",
    encryption_key=os.environ["HYPERLIQUID_ENCRYPTION_KEY"],
    testnet=False,
)

# Option 3: Direct (NOT recommended for production)
adapter = HyperliquidBrokerAdapter(
    private_key="0x1234...",  # Logs warning
    testnet=False,
)
```

#### Rate Limits

| Limit Type | Value |
|------------|-------|
| REST API | 600 req/min |
| Orders | 20/sec |
| WebSocket | Unlimited (event-driven) |

---

### Lighter.xyz

Lighter.xyz is a DeFi perpetual DEX with high throughput and low fees.

#### Wallet and API Key Setup

Lighter uses a unique dual-key authentication:
1. **ETH Wallet Private Key** - For signing transactions
2. **API Private Key** - For API authentication
3. **Account Index** - Your account number (usually 0)
4. **API Key Index** - Index of your API key (2-254)

##### Step 1: Create Ethereum Wallet

If you don't have one:
```python
from eth_account import Account
account = Account.create()
print(f"Address: {account.address}")
print(f"Private Key: {account.key.hex()}")
```

##### Step 2: Access Lighter Platform

1. Go to [app.lighter.xyz](https://app.lighter.xyz) (mainnet) or [testnet.app.lighter.xyz](https://testnet.app.lighter.xyz)
2. Connect your Ethereum wallet
3. Sign the message to create your Lighter account

##### Step 3: Generate API Key

1. Navigate to **Settings** or **API**
2. Click **Create API Key**
3. You'll receive:
   - **API Private Key** (for signing API requests)
   - **API Key Index** (number between 2-254)
4. Note your **Account Index** (typically 0 for first account)

> **Note**: API key indices 0-1 are reserved (0=desktop, 1=mobile). Use indices 2-254 for API keys.

#### Environment Variables

```bash
# ETH wallet private key (for signing)
export LIGHTER_ETH_PRIVATE_KEY="0x1234567890abcdef..."

# API key's private key (from Lighter app)
export LIGHTER_API_PRIVATE_KEY="0x1234567890abcdef..."

# Account index (usually 0)
export LIGHTER_ACCOUNT_INDEX="0"

# API key index (2-254)
export LIGHTER_API_KEY_INDEX="2"
```

#### Python Configuration

```python
from rustybt.live.brokers import LighterBrokerAdapter
import os

adapter = LighterBrokerAdapter(
    testnet=True,  # Start with testnet
    # Credentials loaded from environment variables by default
)

# Or explicitly:
adapter = LighterBrokerAdapter(
    eth_private_key=os.environ.get("LIGHTER_ETH_PRIVATE_KEY"),
    api_private_key=os.environ.get("LIGHTER_API_PRIVATE_KEY"),
    account_index=int(os.environ.get("LIGHTER_ACCOUNT_INDEX", "0")),
    api_key_index=int(os.environ.get("LIGHTER_API_KEY_INDEX", "2")),
    testnet=True,
)
```

#### Testnet vs Mainnet

| Environment | API URL | App URL |
|-------------|---------|---------|
| Testnet | testnet.zklighter.elliot.ai | testnet.app.lighter.xyz |
| Mainnet | mainnet.zklighter.elliot.ai | app.lighter.xyz |

#### Rate Limits

| Limit Type | Value |
|------------|-------|
| REST API | 600 req/min |
| Orders | 20/sec/symbol |
| WebSocket | Event-driven |

---

### Interactive Brokers

Interactive Brokers is a traditional broker supporting stocks, futures, options, forex, and more.

#### TWS/Gateway Requirements

Interactive Brokers requires running TWS (Trader Workstation) or IB Gateway on the same machine or network as your trading bot.

| Application | Use Case | Download |
|-------------|----------|----------|
| TWS | Full trading interface + API | [Download TWS](https://www.interactivebrokers.com/en/trading/tws.php) |
| IB Gateway | Headless API-only mode | [Download Gateway](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) |

#### Socket Ports

| Mode | TWS Port | Gateway Port |
|------|----------|--------------|
| Paper Trading | 7496 | 4002 |
| Live Trading | 7497 | 4001 |

#### TWS/Gateway Configuration

1. Open TWS or IB Gateway
2. Go to **Edit** → **Global Configuration** → **API** → **Settings**
3. Enable **Enable ActiveX and Socket Clients**
4. Set the **Socket port** (default: 7496 for TWS paper)
5. Enable **Allow connections from localhost only** (recommended)
6. Click **Apply** and **OK**

#### Paper Trading Setup

1. Login to TWS with paper trading account
2. Or create paper account in Account Management
3. Use port 7496 (TWS) or 4002 (Gateway)

#### Python Configuration

```python
from rustybt.live.brokers import IBBrokerAdapter

# Paper trading (recommended for testing)
adapter = IBBrokerAdapter(
    host="127.0.0.1",
    port=7496,  # TWS paper trading port
    client_id=1,  # Unique ID (1-32)
    auto_reconnect=True,
)

# Live trading
adapter = IBBrokerAdapter(
    host="127.0.0.1",
    port=7497,  # TWS live trading port
    client_id=1,
    auto_reconnect=True,
)

# Connect to running TWS/Gateway
await adapter.connect()
```

#### Client ID Management

Each connection to TWS requires a unique client ID (1-32). Multiple strategies can run simultaneously with different IDs:

```python
# Strategy 1
adapter1 = IBBrokerAdapter(port=7496, client_id=1)

# Strategy 2
adapter2 = IBBrokerAdapter(port=7496, client_id=2)
```

---

## Security Best Practices

### API Key Permissions

Configure the minimum permissions required:

| Permission | Recommended | Notes |
|------------|-------------|-------|
| Read/View | ✅ Enable | Required for balance/position queries |
| Trade | ✅ Enable | Required for order execution |
| Withdraw | ❌ **Never enable** | Major security risk |
| Transfer | ❌ Disable | Not needed for trading |

### Environment Variables

**Always** load credentials from environment variables, never hardcode them:

```bash
# Create .env file (excluded from git via .gitignore)
# .env
BINANCE_API_KEY=your_key
BINANCE_SECRET=your_secret
HYPERLIQUID_PRIVATE_KEY=0x...
```

```python
# Load in Python
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.environ["BINANCE_API_KEY"]
```

### Encrypted Keystores

For DEX adapters (Hyperliquid, Lighter), use encrypted keystores:

```python
from cryptography.fernet import Fernet

# 1. Generate encryption key (store separately!)
encryption_key = Fernet.generate_key()

# 2. Encrypt private key
fernet = Fernet(encryption_key)
encrypted = fernet.encrypt(private_key.encode())

# 3. Save encrypted key to file
with open("keystore.enc", "wb") as f:
    f.write(encrypted)

# 4. Load when needed
with open("keystore.enc", "rb") as f:
    encrypted = f.read()
private_key = fernet.decrypt(encrypted).decode()
```

### IP Whitelisting

Enable IP restrictions where supported:

| Platform | IP Whitelist Support |
|----------|---------------------|
| Binance | ✅ Yes (recommended) |
| Bybit | ✅ Yes (recommended) |
| Hyperliquid | ❌ No (uses private key auth) |
| Lighter.xyz | ❌ No (uses private key auth) |
| Interactive Brokers | ✅ Via TWS settings |

### Testnet First

**Always test on testnet before using real funds:**

```python
# GOOD: Start with testnet
adapter = BinanceBrokerAdapter(testnet=True)

# After thorough testing...
# PRODUCTION: Switch to mainnet
adapter = BinanceBrokerAdapter(testnet=False)
```

### Key Rotation

Rotate API keys periodically:
- CEX (Binance, Bybit): Every 3-6 months
- DEX (Hyperliquid, Lighter): Consider using API wallets

---

## Configuration File

rustybt supports YAML configuration for live trading:

```yaml
# config/live_trading.yaml
live_trading:
  # Default broker
  broker: hyperliquid

  # Broker-specific settings
  brokers:
    binance:
      market_type: futures
      testnet: true  # Start with testnet

    bybit:
      category: linear
      testnet: true

    hyperliquid:
      testnet: true
      # Keys loaded from environment

    lighter:
      testnet: true
      account_index: 0
      api_key_index: 2

    ib:
      host: "127.0.0.1"
      port: 7496  # Paper trading
      client_id: 1

  # Risk management
  risk:
    max_position_size: 0.1  # 10% of account
    max_drawdown: 0.05  # 5% max drawdown
    stop_loss_pct: 0.02  # 2% stop loss

  # Logging
  logging:
    level: INFO
    # Never log credentials!
```

Loading configuration:

```python
import yaml

with open("config/live_trading.yaml") as f:
    config = yaml.safe_load(f)

broker_config = config["live_trading"]["brokers"]["hyperliquid"]
```

---

## Troubleshooting

### Connection Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ConnectionRefused` | API endpoint unreachable | Check network, verify URL |
| `Timeout` | Slow network or overloaded API | Increase timeout, retry |
| `SSLError` | Certificate issue | Update certificates, check date/time |

**Binance/Bybit:**
```python
# Test connection
async with aiohttp.ClientSession() as session:
    async with session.get("https://api.binance.com/api/v3/ping") as resp:
        print(f"Status: {resp.status}")
```

**Interactive Brokers:**
```python
# Verify TWS is running and API enabled
# Check port settings in TWS Global Configuration
```

### Authentication Failures

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid API-key` | Wrong key or typo | Verify key copied correctly |
| `Invalid signature` | Wrong secret or timestamp | Check secret, sync time |
| `Permission denied` | Missing API permissions | Enable required permissions |
| `IP not whitelisted` | Request from wrong IP | Add IP to whitelist |

**Time sync issues (Binance):**
```bash
# Linux: Sync system time
sudo ntpdate -u time.google.com

# Check time difference
python -c "import time; print(int(time.time() * 1000))"
```

### Rate Limit Errors

| Platform | Error Code | Recovery |
|----------|------------|----------|
| Binance | -1015 | Wait 1 minute, reduce request rate |
| Bybit | 10006 | Wait, implement backoff |
| Hyperliquid | 429 | Token bucket limiting |

**Built-in rate limiting:**
```python
# rustybt adapters include rate limiting
# If you see rate limit errors, reduce order frequency
```

### Order Rejections

| Reason | Cause | Solution |
|--------|-------|----------|
| `Insufficient balance` | Not enough funds | Check balance, reduce size |
| `Invalid quantity` | Below minimum or wrong precision | Check symbol info |
| `Invalid price` | Price too far from market | Adjust price, use market order |
| `Position limit exceeded` | Max positions reached | Close existing positions |

**Check symbol requirements:**
```python
# Binance - Get symbol info
info = await adapter.get_exchange_info("BTCUSDT")
print(f"Min quantity: {info['minQty']}")
print(f"Price precision: {info['pricePrecision']}")
```

### DEX-Specific Issues

**Private key errors:**
```python
# Verify key format
key = os.environ.get("HYPERLIQUID_PRIVATE_KEY", "")
if key.startswith("0x"):
    assert len(key) == 66, f"Invalid length: {len(key)} (expected 66)"
else:
    assert len(key) == 64, f"Invalid length: {len(key)} (expected 64)"
```

**Transaction failures:**
- Check wallet has sufficient ETH for gas (if required)
- Verify account is funded on the DEX
- Check testnet vs mainnet configuration

---

## Next Steps

After completing setup:

1. **Run tests** to verify connectivity:
   ```bash
   pytest tests/live/testnet/ -v
   ```

2. **Paper trade** before using real funds:
   - Use testnet credentials
   - Monitor for unexpected behavior
   - Verify order execution logic

3. **Start small** when going live:
   - Use minimum order sizes
   - Monitor closely
   - Gradually increase exposure

4. **Read the API documentation**:
   - [Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs)
   - [Binance API](https://developers.binance.com/docs)
   - [Bybit API](https://bybit-exchange.github.io/docs/v5/intro)
   - [Lighter.xyz API](https://apidocs.lighter.xyz)
   - [IB API](https://interactivebrokers.github.io/tws-api/)

5. **Implement monitoring**:
   - Set up alerts for disconnections
   - Monitor position sizes
   - Track PnL in real-time

---

## Related Documentation

- [Testnet Setup Guide](./testnet-setup-guide.md) - Detailed testnet credential setup
- [Lighter.xyz Integration](./lighter-integration.md) - Lighter.xyz specific documentation
- [Code Audit Report](./audit-report.md) - Production readiness audit results
- [Stress Test Results](./stress-test-report.md) - System resilience testing

---

*Last updated: 2025-12-06*
