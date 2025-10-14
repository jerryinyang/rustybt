# Testnet & Demo Account Setup Guide for Epic 6

This guide provides step-by-step instructions for setting up testnet and demo accounts required for Epic 6 (Live Trading Engine & Broker Integrations) development and testing.

## Table of Contents
- [Overview](#overview)
- [Broker Integrations](#broker-integrations)
- [Data API Providers](#data-api-providers)
- [Environment Configuration](#environment-configuration)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

Epic 6 requires access to multiple broker testnet accounts and data API provider keys for comprehensive integration testing. This guide covers setup for:

**Brokers:**
- Interactive Brokers (IB) Paper Trading
- Binance Testnet
- Bybit Testnet
- Hyperliquid (Mainnet/Testnet)
- CCXT-supported exchanges

**Data Providers:**
- Polygon.io
- Alpaca
- Alpha Vantage

---

## Broker Integrations

### Interactive Brokers

**Setup Steps:**

1. **Create IB Account**
   - Visit: https://www.interactivebrokers.com
   - Register for individual account
   - Complete identity verification (may take 1-3 business days)

2. **Enable Paper Trading**
   - Log into Account Management
   - Navigate to Settings → Paper Trading
   - Enable paper trading account (instant activation)
   - Note your paper trading account number

3. **Install TWS or IB Gateway**
   - Download TWS: https://www.interactivebrokers.com/en/trading/tws.php
   - Alternative: IB Gateway (lighter, headless)
   - Install and launch application

4. **Configure API Access**
   - In TWS: File → Global Configuration → API → Settings
   - Enable ActiveX and Socket Clients: ✓
   - Socket port: 7496 (paper) or 7497 (live)
   - Master API client ID: Leave blank
   - Read-Only API: ✗ (uncheck for trading)
   - Trusted IP addresses: Add 127.0.0.1
   - Click OK and restart TWS

5. **Test Connection**
   ```bash
   # Create test script
   python -c "
   from ib_async import IB
   ib = IB()
   ib.connect('127.0.0.1', 7496, clientId=1)  # 7496 for paper trading
   print('Connected:', ib.isConnected())
   ib.disconnect()
   "
   ```

**Configuration:**
```bash
# .env
IB_HOST=127.0.0.1
IB_PORT=7496  # Paper trading
IB_CLIENT_ID=1
```

**Ports:**
- TWS Paper: 7496
- TWS Live: 7497
- Gateway Paper: 4002
- Gateway Live: 4001

---

### Binance Testnet

**Setup Steps:**

1. **Register for Testnet**
   - Visit: https://testnet.binance.vision
   - Log in with GitHub account
   - Generate API keys (no verification required)

2. **Create API Keys**
   - Click "Generate HMAC_SHA256 Key"
   - Save API Key and Secret Key immediately
   - Enable spot trading permissions

3. **Get Test Funds**
   - Use testnet faucet for test USDT/BTC
   - Test funds refresh daily

**Configuration:**
```bash
# .env
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_API_SECRET=your_testnet_api_secret
BINANCE_TESTNET_URL=https://testnet.binance.vision
```

**Endpoints:**
- REST API: https://testnet.binance.vision/api
- WebSocket: wss://testnet.binance.vision/ws

---

### Bybit Testnet

**Setup Steps:**

1. **Register for Testnet**
   - Visit: https://testnet.bybit.com
   - Create account (email + password, no KYC)
   - Verify email address

2. **Create API Keys**
   - Navigate to API Management
   - Create new API key
   - Enable: Read, Trade permissions
   - Whitelist IP: 0.0.0.0/0 (testnet only!)
   - Save API Key and Secret

3. **Get Test Funds**
   - Use testnet faucet in account page
   - Request USDT for testing

**Configuration:**
```bash
# .env
BYBIT_TESTNET_API_KEY=your_bybit_testnet_key
BYBIT_TESTNET_API_SECRET=your_bybit_testnet_secret
BYBIT_TESTNET_URL=https://api-testnet.bybit.com
```

---

### Hyperliquid

**Setup Steps:**

1. **Generate Ethereum Wallet**
   - Use MetaMask or generate keypair programmatically
   - **SECURITY:** Use dedicated wallet for testnet only
   - Never use mainnet wallet with significant funds

2. **Fund Wallet (if using mainnet)**
   - Transfer small amount of USDC to wallet
   - Note: Hyperliquid testnet availability varies

3. **Store Private Key Securely**
   - Encrypt private key before storing
   - Use environment variable or encrypted keystore

**Configuration:**
```bash
# .env
HYPERLIQUID_PRIVATE_KEY=encrypted:your_encrypted_private_key
HYPERLIQUID_NETWORK=mainnet  # or testnet if available
```

**Security Warning:**
- Never commit private keys to version control
- Use encrypted storage for private keys
- Implement key rotation strategy

---

### CCXT Exchanges

For CCXT-supported exchanges, register for testnet/demo accounts:

**Recommended Exchanges for Testing:**
- Coinbase (sandbox): https://public.sandbox.pro.coinbase.com
- Kraken (demo): Create demo account via support
- OKX (demo): https://www.okx.com/demo-trading

**Configuration:**
```bash
# .env
CCXT_EXCHANGE_ID=binance  # or coinbase, kraken, okx
CCXT_API_KEY=your_api_key
CCXT_API_SECRET=your_api_secret
CCXT_TESTNET=true
```

---

## Data API Providers

### Polygon.io

**Setup Steps:**

1. **Register Account**
   - Visit: https://polygon.io
   - Sign up for free tier (5 API calls/minute)
   - Verify email address

2. **Get API Key**
   - Navigate to Dashboard → API Keys
   - Copy your API key
   - Note rate limits for your tier

**Configuration:**
```bash
# .env
POLYGON_API_KEY=your_polygon_api_key
```

**Rate Limits:**
- Free: 5 requests/minute
- Starter ($29/month): 10 requests/minute
- Developer ($99/month): 100 requests/minute

---

### Alpaca

**Setup Steps:**

1. **Register for Paper Trading**
   - Visit: https://alpaca.markets
   - Sign up for free paper trading account
   - No KYC required for paper trading

2. **Get API Keys**
   - Navigate to Paper Trading → API Keys
   - Generate new API key pair
   - Save Key ID and Secret Key

**Configuration:**
```bash
# .env
ALPACA_API_KEY=your_alpaca_key_id
ALPACA_API_SECRET=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
```

**Endpoints:**
- Paper Trading API: https://paper-api.alpaca.markets
- Paper Data API: https://data.alpaca.markets
- Live Trading API: https://api.alpaca.markets

---

### Alpha Vantage

**Setup Steps:**

1. **Get Free API Key**
   - Visit: https://www.alphavantage.co/support/#api-key
   - Enter email address
   - Receive API key instantly (no verification)

2. **Note Rate Limits**
   - Free tier: 5 requests/minute, 500 requests/day
   - Premium tiers available for higher limits

**Configuration:**
```bash
# .env
ALPHAVANTAGE_API_KEY=your_alphavantage_api_key
```

---

## Environment Configuration

### Complete .env Template

Create `.env` file in project root:

```bash
# Interactive Brokers
IB_HOST=127.0.0.1
IB_PORT=7496  # Paper: 7496, Live: 7497
IB_CLIENT_ID=1

# Binance
BINANCE_TESTNET_API_KEY=your_binance_testnet_key
BINANCE_TESTNET_API_SECRET=your_binance_testnet_secret
BINANCE_TESTNET_URL=https://testnet.binance.vision

# Bybit
BYBIT_TESTNET_API_KEY=your_bybit_testnet_key
BYBIT_TESTNET_API_SECRET=your_bybit_testnet_secret
BYBIT_TESTNET_URL=https://api-testnet.bybit.com

# Hyperliquid
HYPERLIQUID_PRIVATE_KEY=encrypted:your_encrypted_key
HYPERLIQUID_NETWORK=mainnet

# CCXT
CCXT_EXCHANGE_ID=binance
CCXT_API_KEY=your_ccxt_api_key
CCXT_API_SECRET=your_ccxt_api_secret
CCXT_TESTNET=true

# Data Providers
POLYGON_API_KEY=your_polygon_api_key
ALPACA_API_KEY=your_alpaca_key_id
ALPACA_API_SECRET=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPHAVANTAGE_API_KEY=your_alphavantage_key
```

### .gitignore Configuration

Ensure `.env` and sensitive files are excluded:

```bash
# Add to .gitignore
.env
.env.*
*.env
api_keys.ini
~/.rustybt/api_keys.ini
credentials.json
*.pem
*.key
```

---

## Security Best Practices

### API Key Management

1. **Never Commit Credentials**
   - Always use `.env` files (excluded from version control)
   - Use environment variables in CI/CD
   - Implement pre-commit hooks to detect secrets

2. **Encryption**
   - Encrypt private keys (Hyperliquid) using `cryptography` library
   - Store encrypted keys in environment variables
   - Use secure key derivation (PBKDF2, scrypt, or Argon2)

3. **Key Rotation**
   - Rotate API keys every 90 days
   - Implement automated rotation for production
   - Track key usage and expiration

4. **IP Whitelisting**
   - Whitelist development machine IPs for API access
   - Use VPN for remote development
   - Restrict production keys to specific IP ranges

### Testnet Isolation

1. **Separate Credentials**
   - Use different API keys for testnet vs production
   - Never reuse production credentials in testnet

2. **Labeling**
   - Clearly label testnet vs production in configs
   - Use naming conventions (e.g., `_TESTNET_` suffix)

3. **Monitoring**
   - Monitor API usage to detect unauthorized access
   - Set up alerts for unusual activity

---

## Troubleshooting

### Interactive Brokers

**Issue: "Cannot connect to TWS"**
- Solution: Verify TWS is running and API is enabled
- Check port number (7496 for paper, 7497 for live)
- Ensure 127.0.0.1 is whitelisted in TWS settings

**Issue: "Socket connection refused"**
- Solution: Restart TWS and wait 30 seconds
- Check firewall settings (allow port 7496/7497)

### Binance/Bybit

**Issue: "Invalid API key"**
- Solution: Regenerate API keys from testnet dashboard
- Verify testnet URL is used (not production)
- Check API key permissions are enabled

**Issue: "Rate limit exceeded"**
- Solution: Implement exponential backoff
- Reduce request frequency
- Upgrade to paid tier if needed

### Data Providers

**Issue: "Quota exceeded"**
- Solution: Monitor API usage dashboard
- Implement request caching
- Upgrade to higher tier if needed

**Issue: "Invalid symbol"**
- Solution: Check symbol format (provider-specific)
- Use provider's symbol lookup API
- Verify asset is supported by provider

---

## Running Integration Tests

Once all accounts are configured:

```bash
# Run broker integration tests
pytest tests/integration/live/test_ib_integration.py --run-ib-integration
pytest tests/integration/live/test_exchange_integrations.py --run-exchange-integration

# Run data provider integration tests
pytest tests/integration/data/test_api_providers.py --run-api-integration

# Skip integration tests (default)
pytest tests/  # Integration tests skipped without flags
```

**Test Markers:**
- `@pytest.mark.ib_integration` - Requires IB paper account
- `@pytest.mark.exchange_integration` - Requires exchange testnet accounts
- `@pytest.mark.api_integration` - Requires data API keys

---

## Support & Resources

### Documentation
- Interactive Brokers: https://interactivebrokers.github.io/tws-api/
- Binance Testnet: https://testnet.binance.vision/
- Bybit Testnet: https://testnet.bybit.com/
- Polygon: https://polygon.io/docs
- Alpaca: https://alpaca.markets/docs
- Alpha Vantage: https://www.alphavantage.co/documentation/

### Community
- CCXT: https://github.com/ccxt/ccxt
- ib_async: https://github.com/erdewit/ib_insync

---

**Last Updated:** 2025-10-02
