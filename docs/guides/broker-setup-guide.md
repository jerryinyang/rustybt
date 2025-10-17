# Broker Setup Guide

**Last Updated**: 2024-10-11

## Overview

This guide covers the complete setup process for all supported brokers in RustyBT. Each broker section includes account creation, API key generation, configuration, testing, and troubleshooting.

---

## Table of Contents

1. [PaperBroker (Testing)](#paperbroker-testing)
2. [Binance (Crypto)](#binance-crypto)
3. [Bybit (Derivatives)](#bybit-derivatives)
4. [Hyperliquid (DEX)](#hyperliquid-dex)
5. [Interactive Brokers (Traditional)](#interactive-brokers-traditional)
6. [CCXT Generic (100+ Exchanges)](#ccxt-generic-100-exchanges)
7. [Environment Variables](#environment-variables)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## PaperBroker (Testing)

The PaperBroker is a simulated broker for strategy development and testing without real capital.

### Setup

No account or API keys required! PaperBroker works out of the box.

```python
from rustybt.live.brokers import PaperBroker
from decimal import Decimal

broker = PaperBroker(
    starting_cash=Decimal("100000"),  # $100k starting capital
    commission_model=None,             # No commissions
    slippage_model=None                # No slippage
)
```

### Configuration Options

```python
from rustybt.finance.commission import PerShareCommission
from rustybt.finance.slippage import FixedSlippage

broker = PaperBroker(
    starting_cash=Decimal("100000"),
    commission_model=PerShareCommission(cost=Decimal("0.005")),  # $0.005 per share
    slippage_model=FixedSlippage(spread=Decimal("0.0005"))      # 0.05% slippage
)
```

### Use Cases

- ✅ Strategy development
- ✅ Backtesting validation
- ✅ Algorithm testing before live trading
- ✅ Education and learning
- ❌ Real market execution

---

## Binance (Crypto)

Binance is the world's largest cryptocurrency exchange.

### 1. Create Account

1. Go to [Binance.com](https://www.binance.com)
2. Click "Register" (top right)
3. Complete email verification
4. Complete KYC verification (required for API trading)
5. Enable 2FA (highly recommended)

### 2. Create API Keys

1. Log in to Binance
2. Hover over profile icon → **API Management**
3. Click **Create API**
4. Label your API (e.g., "RustyBT Trading")
5. Complete 2FA verification
6. **Save your API Key and Secret Key** (secret shown only once!)

### 3. Configure API Permissions

**IMPORTANT**: Set correct permissions:

- ✅ **Enable Reading** (required)
- ✅ **Enable Spot & Margin Trading** (if trading spot)
- ✅ **Enable Futures** (if trading futures)
- ❌ **Disable Withdrawals** (for security)

### 4. Whitelist IP (Optional but Recommended)

1. In API Management, click **Edit** on your API
2. Add your server's IP address
3. If testing locally, add your home IP (check at [whatismyip.com](https://www.whatismyip.com))

### 5. Test with Testnet

**Testnet Setup** (recommended before live trading):

1. Go to [Binance Testnet](https://testnet.binance.vision/)
2. Login with GitHub
3. Generate test API keys
4. Fund test account with fake USDT

### 6. RustyBT Configuration

```python
from rustybt.live.brokers import BinanceBrokerAdapter
import os

broker = BinanceBrokerAdapter(
    api_key=os.getenv('BINANCE_API_KEY'),
    api_secret=os.getenv('BINANCE_API_SECRET'),
    testnet=True  # Set False for production
)

await broker.connect()
```

### 7. Environment Variables

Add to your `.env` file:

```bash
# Binance Testnet
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here

# Binance Production (when ready)
BINANCE_PROD_API_KEY=your_production_api_key_here
BINANCE_PROD_API_SECRET=your_production_api_secret_here
```

### 8. Verify Setup

```python
import asyncio
from rustybt.live.brokers import BinanceBrokerAdapter
import os

async def verify_binance():
    broker = BinanceBrokerAdapter(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET'),
        testnet=True
    )

    await broker.connect()

    # Check account info
    account = await broker.get_account_info()
    print(f"✅ Connected! Balance: ${account['cash']}")

    # Check positions
    positions = await broker.get_positions()
    print(f"✅ Current positions: {len(positions)}")

    await broker.disconnect()

asyncio.run(verify_binance())
```

### Rate Limits

- **Weight Limit**: 1200 requests per minute
- **Order Limit**: 10 orders per second per symbol
- **WebSocket**: 10 connections per IP

---

## Bybit (Derivatives)

Bybit specializes in cryptocurrency derivatives and perpetual futures.

### 1. Create Account

1. Go to [Bybit.com](https://www.bybit.com)
2. Click "Sign Up"
3. Complete email/phone verification
4. Complete KYC for higher limits
5. Enable 2FA

### 2. Create API Keys

1. Log in to Bybit
2. Go to **Account & Security** → **API Management**
3. Click **Create New Key**
4. Select API type:
   - **System-generated API Key** (recommended for trading bots)
5. Set API name: "RustyBT"
6. Set permissions:
   - ✅ Read-Write (for trading)
   - ❌ Withdraw (keep disabled)
7. Save API Key and Secret

### 3. Test with Testnet

1. Go to [Bybit Testnet](https://testnet.bybit.com)
2. Register separate testnet account
3. Generate testnet API keys
4. Get free testnet funds from faucet

### 4. RustyBT Configuration

```python
from rustybt.live.brokers import BybitBrokerAdapter
import os

broker = BybitBrokerAdapter(
    api_key=os.getenv('BYBIT_API_KEY'),
    api_secret=os.getenv('BYBIT_API_SECRET'),
    testnet=True
)

await broker.connect()
```

### 5. Environment Variables

```bash
# Bybit Testnet
BYBIT_API_KEY=your_testnet_api_key
BYBIT_API_SECRET=your_testnet_api_secret

# Bybit Production
BYBIT_PROD_API_KEY=your_production_api_key
BYBIT_PROD_API_SECRET=your_production_api_secret
```

### Rate Limits

- **REST**: 120 requests per minute
- **WebSocket**: 240 messages per minute

---

## Hyperliquid (DEX)

Hyperliquid is a decentralized perpetuals exchange.

### 1. Create Account

1. Go to [Hyperliquid.xyz](https://app.hyperliquid.xyz)
2. Connect Web3 wallet (MetaMask, WalletConnect)
3. Bridge funds to Hyperliquid L1
4. No KYC required (decentralized)

### 2. Generate API Keys

1. In Hyperliquid app, go to **API**
2. Click **Generate API Key**
3. Sign message with wallet
4. Save generated API key and secret

### 3. Test on Testnet

1. Go to [Testnet](https://app.hyperliquid-testnet.xyz)
2. Connect wallet
3. Get testnet tokens from faucet
4. Generate testnet API keys

### 4. RustyBT Configuration

```python
from rustybt.live.brokers import HyperliquidBrokerAdapter
import os

broker = HyperliquidBrokerAdapter(
    api_key=os.getenv('HYPERLIQUID_API_KEY'),
    api_secret=os.getenv('HYPERLIQUID_API_SECRET'),
    testnet=True
)

await broker.connect()
```

### 5. Environment Variables

```bash
HYPERLIQUID_API_KEY=your_api_key
HYPERLIQUID_API_SECRET=your_api_secret
HYPERLIQUID_WALLET_ADDRESS=0x_your_wallet_address
```

### Special Features

- On-chain settlement
- No maker fees
- Low latency (~10ms)
- L2 orderbook data

---

## Interactive Brokers (Traditional)

Interactive Brokers provides access to stocks, options, futures, and forex.

### 1. Create Account

1. Go to [InteractiveBrokers.com](https://www.interactivebrokers.com)
2. Click "Open Account"
3. Choose account type:
   - **Individual** (most common)
   - **IRA** (retirement account)
   - **Entity** (company/trust)
4. Complete application (15-30 minutes)
5. Fund account (minimum $0 for paper, varies for live)

### 2. Enable Paper Trading

1. Log in to [Account Management](https://www.interactivebrokers.com/sso/Login)
2. Go to **Settings** → **Account Settings**
3. Select **Trading Permissions**
4. Enable **Paper Trading**
5. Note your paper trading username

### 3. Install TWS or IB Gateway

**Option A: TWS (Trader Workstation)** - Full featured

1. Download from [IB Downloads](https://www.interactivebrokers.com/en/trading/tws.php)
2. Install and launch
3. Login with paper trading credentials
4. Go to **File** → **Global Configuration** → **API** → **Settings**
5. Check:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Read-Only API
   - Add trusted IP: `127.0.0.1`
6. Note socket port (default: `7497` for paper, `7496` for live)

**Option B: IB Gateway** - Lightweight (recommended for bots)

1. Download from same page
2. Install and launch
3. Login
4. Configure API settings (same as TWS)

### 4. RustyBT Configuration

```python
from rustybt.live.brokers import IBBrokerAdapter

broker = IBBrokerAdapter(
    host='127.0.0.1',
    port=7497,  # 7497 = paper trading, 7496 = live
    client_id=1  # Unique ID per connection
)

await broker.connect()
```

### 5. Environment Variables

```bash
IB_HOST=127.0.0.1
IB_PORT=7497  # Paper trading port
IB_CLIENT_ID=1
```

### 6. Verify Connection

```python
import asyncio
from rustybt.live.brokers import IBBrokerAdapter

async def verify_ib():
    broker = IBBrokerAdapter(host='127.0.0.1', port=7497, client_id=1)

    await broker.connect()
    print("✅ Connected to Interactive Brokers!")

    account = await broker.get_account_info()
    print(f"Account value: ${account['equity']}")

    await broker.disconnect()

asyncio.run(verify_ib())
```

### Troubleshooting IB Connection

**Problem**: `Connection refused`
- **Solution**: Ensure TWS/Gateway is running and API is enabled

**Problem**: `Not connected`
- **Solution**: Check port number (7497 for paper, 7496 for live)

**Problem**: `Max clients reached`
- **Solution**: Disconnect other API clients or increase limit in TWS settings

---

## CCXT Generic (100+ Exchanges)

CCXT provides unified API for 100+ cryptocurrency exchanges.

### Supported Exchanges

Popular exchanges supported:
- Binance, Coinbase Pro, Kraken, Bitfinex
- KuCoin, Huobi, OKX, Gate.io
- FTX (historical data only), Bybit, Phemex
- [Full list](https://github.com/ccxt/ccxt#supported-cryptocurrency-exchange-markets)

### Setup

1. Create account on your chosen exchange
2. Generate API keys (follow exchange-specific instructions)
3. Use CCXTBrokerAdapter:

```python
from rustybt.live.brokers import CCXTBrokerAdapter
import os

# Example: Kraken
broker = CCXTBrokerAdapter(
    exchange_id='kraken',  # Exchange name
    api_key=os.getenv('KRAKEN_API_KEY'),
    api_secret=os.getenv('KRAKEN_API_SECRET'),
    rate_limit=True
)

await broker.connect()
```

### Exchange-Specific Configuration

Some exchanges require additional parameters:

```python
# Coinbase Pro (requires passphrase)
broker = CCXTBrokerAdapter(
    exchange_id='coinbasepro',
    api_key=os.getenv('COINBASE_API_KEY'),
    api_secret=os.getenv('COINBASE_API_SECRET'),
    password=os.getenv('COINBASE_PASSPHRASE')  # Additional field
)

# Binance US (different endpoint)
broker = CCXTBrokerAdapter(
    exchange_id='binanceus',
    api_key=os.getenv('BINANCE_US_API_KEY'),
    api_secret=os.getenv('BINANCE_US_API_SECRET')
)
```

### List Available Exchanges

```python
import ccxt

print(ccxt.exchanges)  # List all supported exchanges
```

---

## Environment Variables

### Recommended Structure

Create a `.env` file in your project root:

```bash
# ============================================================================
# RustyBT Broker Configuration
# ============================================================================

# --- PaperBroker (no keys needed) ---

# --- Binance ---
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here

# Binance Production (when ready)
# BINANCE_PROD_API_KEY=
# BINANCE_PROD_API_SECRET=

# --- Bybit ---
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_API_SECRET=your_bybit_api_secret_here

# --- Hyperliquid ---
HYPERLIQUID_API_KEY=your_hyperliquid_api_key_here
HYPERLIQUID_API_SECRET=your_hyperliquid_api_secret_here
HYPERLIQUID_WALLET_ADDRESS=0x_your_wallet_address

# --- Interactive Brokers ---
IB_HOST=127.0.0.1
IB_PORT=7497  # 7497=paper, 7496=live
IB_CLIENT_ID=1

# --- Other CCXT Exchanges ---
KRAKEN_API_KEY=
KRAKEN_API_SECRET=

COINBASE_API_KEY=
COINBASE_API_SECRET=
COINBASE_PASSPHRASE=

# ============================================================================
# Data Providers
# ============================================================================

POLYGON_API_KEY=your_polygon_api_key_here
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_API_SECRET=your_alpaca_api_secret_here
ALPHAVANTAGE_API_KEY=your_alphavantage_api_key_here
```

### Loading Environment Variables

```python
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Access variables
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
```

### Security Best Practices

1. **Never commit `.env` to git**:
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use different keys for test/prod**:
   - Separate API keys for testnet and production
   - Label keys clearly in broker dashboard

3. **Restrict API permissions**:
   - ❌ Disable withdrawals
   - ✅ Enable only trading
   - ✅ Whitelist IPs when possible

4. **Rotate keys regularly**:
   - Change API keys every 3-6 months
   - Immediately rotate if compromised

5. **Use secret management in production**:
   - AWS Secrets Manager
   - HashiCorp Vault
   - Azure Key Vault

---

## Best Practices

### 1. Always Start with Testnet

- ✅ Test on testnet before live trading
- ✅ Verify all order types work
- ✅ Test error handling
- ✅ Monitor for 24-48 hours

### 2. Implement Circuit Breakers

```python
from rustybt.live.circuit_breakers import (
    DailyLossCircuitBreaker,
    DrawdownCircuitBreaker,
    CircuitBreakerManager
)
from decimal import Decimal

# Create individual circuit breakers
daily_loss_breaker = DailyLossCircuitBreaker(
    limit=Decimal("-5000"),             # Stop if lose $5k in a day
    initial_portfolio_value=Decimal("100000"),
    is_percentage=False                 # Use absolute amount
)

drawdown_breaker = DrawdownCircuitBreaker(
    threshold=Decimal("-0.10"),         # Stop if 10% drawdown
    initial_portfolio_value=Decimal("100000")
)

# Manage all breakers together
breaker_manager = CircuitBreakerManager(
    daily_loss_breaker=daily_loss_breaker,
    drawdown_breaker=drawdown_breaker
)
```

### 3. Monitor Rate Limits

```python
# Use rate limiting
broker = BinanceBrokerAdapter(
    api_key=api_key,
    api_secret=api_secret,
    rate_limit=True  # Enable built-in rate limiting
)
```

### 4. Log Everything

```python
import structlog

logger = structlog.get_logger()

# All broker operations are auto-logged
await broker.submit_order(...)  # Logged automatically
```

### 5. Handle Errors Gracefully

```python
from rustybt.exceptions import BrokerError, InsufficientFundsError

try:
    order_id = await broker.submit_order(...)
except InsufficientFundsError as e:
    logger.error("Insufficient funds", error=str(e))
except BrokerError as e:
    logger.error("Broker error", error=str(e))
    # Implement retry logic or alert
```

---

## Troubleshooting

### Common Issues

#### "Authentication failed"

**Causes**:
- Wrong API key/secret
- API key expired or revoked
- IP not whitelisted (if enabled)

**Solutions**:
1. Double-check `.env` file
2. Regenerate API keys in broker dashboard
3. Add current IP to whitelist

#### "Permission denied"

**Causes**:
- API permissions not enabled
- Trading not enabled for account
- Insufficient account balance

**Solutions**:
1. Check API permissions in broker dashboard
2. Enable "Spot Trading" or "Futures" permission
3. Fund account with minimum required

#### "Rate limit exceeded"

**Causes**:
- Too many requests in short time
- Multiple bots using same API key

**Solutions**:
1. Enable `rate_limit=True` in adapter
2. Use separate API keys per bot
3. Add delays between requests

#### "Connection timeout"

**Causes**:
- Network issues
- Broker API downtime
- Firewall blocking requests

**Solutions**:
1. Check broker status page
2. Verify internet connection
3. Try different network (disable VPN if active)

### Getting Help

1. **Check Logs**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Broker API Status**:
   - Binance: [status.binance.com](https://status.binance.com)
   - Bybit: [status.bybit.com](https://status.bybit.com)
   - IB: [status.interactivebrokers.com](https://status.interactivebrokers.com)

3. **RustyBT Issues**:
   - GitHub Issues: [github.com/your-org/rustybt/issues](https://github.com/your-org/rustybt/issues)

---

## Next Steps

After setting up your broker:

1. ✅ Run verification script to test connection
2. ✅ Try a simple strategy on testnet/paper trading
3. ✅ Monitor for 24-48 hours
4. ✅ Review logs for any errors
5. ✅ When ready, switch to production (carefully!)

---

## See Also

- Live Trading API Reference (Coming soon)
- <!-- Live Trading Example (Coming soon) -->
- [Exception Handling Guide](exception-handling.md)
- [Testnet Setup Guide](testnet-setup-guide.md)
