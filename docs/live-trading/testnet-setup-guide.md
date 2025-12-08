# Testnet Setup Guide

This guide explains how to obtain testnet credentials for each supported exchange to run integration tests.

## Overview

| Exchange | Authentication Type | Testnet URL |
|----------|-------------------|-------------|
| Hyperliquid | Ethereum Private Key | testnet.hyperliquid.xyz |
| Binance Futures | API Key + Secret | testnet.binancefuture.com |
| Bybit | API Key + Secret | testnet.bybit.com |
| Lighter.xyz | ETH Private Key + API Key Index | testnet.zklighter.elliot.ai |

---

## Hyperliquid Testnet

### Authentication Model

Hyperliquid uses **Ethereum private keys** for authentication, not traditional API key/secret pairs. This is because Hyperliquid is a decentralized exchange (DEX) built on Ethereum.

**Two options:**

1. **API Wallet (Recommended)** - A dedicated wallet that can trade but cannot withdraw funds
2. **Main Wallet** - Your main Ethereum wallet (not recommended for bots)

### Step-by-Step Setup

#### 1. Create or Import an Ethereum Wallet

If you don't have an Ethereum wallet:
- Use [MetaMask](https://metamask.io/) browser extension
- Or generate one with Python:

```python
from eth_account import Account
account = Account.create()
print(f"Address: {account.address}")
print(f"Private Key: {account.key.hex()}")
# Save these securely!
```

#### 2. Access Hyperliquid Testnet

1. Go to https://app.hyperliquid-testnet.xyz
2. Connect your wallet (MetaMask or WalletConnect)
3. Sign the connection message when prompted

#### 3. Get Testnet USDC

1. Go to https://app.hyperliquid-testnet.xyz/drip
2. Click "Request Testnet USDC"
3. Wait for the transaction to complete

**Note:** You must have deposited on mainnet at least once with the same address before claiming testnet funds.

#### 4. Create an API Wallet (Recommended)

1. Go to https://app.hyperliquid-testnet.xyz/API
2. Click "Create API Wallet"
3. Enter a name (e.g., "trading-bot")
4. Click "Create" and sign the transaction
5. **Copy the generated private key** - this is shown only once!
6. Click "Authorize" to enable trading permissions

The API wallet private key starts with `0x` and is 66 characters total (0x + 64 hex characters).

#### 5. Configure Environment Variables

```bash
# In your .env file:

# The API wallet private key (recommended) or main wallet private key
HYPERLIQUID_PRIVATE_KEY=0x1234567890abcdef...  # 66 chars total

# Your MAIN wallet address (not the API wallet)
# This is the account that holds your positions
HYPERLIQUID_WALLET_ADDRESS=0xYourMainWalletAddress
```

#### 6. Verify Key Format

Your private key should be:
- **With 0x prefix:** Exactly 66 characters (`0x` + 64 hex digits)
- **Without 0x prefix:** Exactly 64 characters (just hex digits)

```python
# Validation check
key = "0x1234..."
if key.startswith("0x"):
    assert len(key) == 66, f"Invalid length: {len(key)}"
else:
    assert len(key) == 64, f"Invalid length: {len(key)}"
```

### Verify Setup

Run this code to confirm your Hyperliquid testnet setup is working:

```python
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def verify_hyperliquid():
    from rustybt.live.brokers import HyperliquidBrokerAdapter

    print("Verifying Hyperliquid testnet setup...")

    adapter = HyperliquidBrokerAdapter(testnet=True)

    try:
        await adapter.connect()
        print("✓ Connection successful")

        info = await adapter.get_account_info()
        print(f"✓ Account info: Balance = {info['balance']} USDC")

        positions = await adapter.get_positions()
        print(f"✓ Position query: {len(positions)} open positions")

        print("\n✅ Hyperliquid testnet setup verified!")

    except Exception as e:
        print(f"✗ Verification failed: {e}")
        print("\nTroubleshooting:")
        print("  - Check HYPERLIQUID_PRIVATE_KEY is set (66 chars with 0x)")
        print("  - Verify you've claimed testnet funds")
        print("  - Ensure wallet has traded on mainnet first")
    finally:
        await adapter.disconnect()

asyncio.run(verify_hyperliquid())
```

**Expected output:**
```
Verifying Hyperliquid testnet setup...
✓ Connection successful
✓ Account info: Balance = 10000.00 USDC
✓ Position query: 0 open positions

✅ Hyperliquid testnet setup verified!
```

### Reference Links

- [Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs)
- [API Documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api)
- [Python SDK](https://github.com/hyperliquid-dex/hyperliquid-python-sdk)

---

## Binance Futures Testnet

### Authentication Model

Binance uses traditional **API Key + Secret** pairs. The futures testnet is completely separate from the spot testnet.

### Step-by-Step Setup

#### 1. Access Binance Futures Testnet

1. Go to https://testnet.binancefuture.com
2. Click "Log In" in the top right
3. **Login with GitHub** - this is the only authentication method for testnet
4. Authorize the Binance application

#### 2. Get Test Funds

After logging in, you'll automatically receive testnet USDT for trading. If you need more:
1. Click your account balance
2. Look for a "Get Test Funds" or similar option

#### 3. Generate API Keys

1. Click on your profile icon → "API Management"
2. Click "Create API Key"
3. Select "HMAC_SHA256" as the key type
4. Enter a label (e.g., "rustybt-testing")
5. **Copy both the API Key and Secret** - the secret is shown only once!

#### 4. Configure API Permissions

For testing, enable:
- ✅ Enable Reading
- ✅ Enable Futures
- ❌ Disable Withdrawals (not needed for trading)

#### 5. Configure Environment Variables

```bash
# In your .env file:
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_SECRET=your_api_secret_here
```

### Important Notes

- Testnet and mainnet are **completely separate systems**
- Testnet keys will **not** work on mainnet and vice versa
- Testnet data may be reset periodically
- Rate limits are similar to mainnet

### Verify Setup

Run this code to confirm your Binance testnet setup is working:

```python
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def verify_binance():
    from rustybt.live.brokers import BinanceBrokerAdapter

    print("Verifying Binance Futures testnet setup...")

    adapter = BinanceBrokerAdapter(
        api_key=os.environ["BINANCE_TESTNET_API_KEY"],
        api_secret=os.environ["BINANCE_TESTNET_SECRET"],
        market_type="futures",
        testnet=True
    )

    try:
        await adapter.connect()
        print("✓ Connection successful")

        info = await adapter.get_account_info()
        print(f"✓ Account info: Balance = {info['balance']} USDT")

        positions = await adapter.get_positions()
        print(f"✓ Position query: {len(positions)} open positions")

        print("\n✅ Binance testnet setup verified!")

    except Exception as e:
        print(f"✗ Verification failed: {e}")
        print("\nTroubleshooting:")
        print("  - Verify BINANCE_TESTNET_API_KEY and SECRET are set")
        print("  - Ensure you used GitHub login at testnet.binancefuture.com")
        print("  - Check API permissions include Read and Futures")
    finally:
        await adapter.disconnect()

asyncio.run(verify_binance())
```

**Expected output:**
```
Verifying Binance Futures testnet setup...
✓ Connection successful
✓ Account info: Balance = 100000.00 USDT
✓ Position query: 0 open positions

✅ Binance testnet setup verified!
```

### Reference Links

- [Binance Futures Testnet](https://testnet.binancefuture.com)
- [API Documentation](https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info)
- [Testnet API Base URL](https://testnet.binancefuture.com): `https://testnet.binancefuture.com`

---

## Bybit Testnet

### Authentication Model

Bybit uses traditional **API Key + Secret** pairs. The testnet environment mirrors the mainnet API.

### Step-by-Step Setup

#### 1. Create Testnet Account

1. Go to https://testnet.bybit.com
2. Click "Sign Up"
3. Register with email or use existing Bybit account
4. Complete email verification

**Note:** Testnet accounts are separate from mainnet accounts.

#### 2. Get Test Funds

After registration:
1. Go to "Assets" → "Spot Account" or "Derivatives Account"
2. Click "Get Testnet Funds" or "Claim"
3. You'll receive testnet USDT automatically

#### 3. Generate API Keys

1. Click on your profile → "API"
2. Or go directly to https://testnet.bybit.com/app/user/api-management
3. Click "Create New Key"
4. Select key type: "System-generated API Keys"
5. Enter a name and configure permissions:
   - ✅ Read
   - ✅ Trade (for order placement)
   - ✅ Position (for position queries)
   - ❌ Withdraw (not needed)
6. Complete 2FA verification
7. **Copy API Key and Secret** - secret shown only once!

#### 4. Configure Environment Variables

```bash
# In your .env file:
BYBIT_TESTNET_API_KEY=your_api_key_here
BYBIT_TESTNET_SECRET=your_api_secret_here
```

### Important Notes

- Bybit's "Demo Trading" is different from testnet - use actual testnet
- Testnet API endpoint: `https://api-testnet.bybit.com`
- WebSocket endpoint: `wss://stream-testnet.bybit.com`

### Verify Setup

Run this code to confirm your Bybit testnet setup is working:

```python
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def verify_bybit():
    from rustybt.live.brokers import BybitBrokerAdapter

    print("Verifying Bybit testnet setup...")

    adapter = BybitBrokerAdapter(
        api_key=os.environ["BYBIT_TESTNET_API_KEY"],
        api_secret=os.environ["BYBIT_TESTNET_SECRET"],
        category="linear",
        testnet=True
    )

    try:
        await adapter.connect()
        print("✓ Connection successful")

        info = await adapter.get_account_info()
        print(f"✓ Account info: Balance = {info['balance']} USDT")

        positions = await adapter.get_positions()
        print(f"✓ Position query: {len(positions)} open positions")

        print("\n✅ Bybit testnet setup verified!")

    except Exception as e:
        print(f"✗ Verification failed: {e}")
        print("\nTroubleshooting:")
        print("  - Verify BYBIT_TESTNET_API_KEY and SECRET are set")
        print("  - Ensure API permissions include Read, Trade, Position")
        print("  - Check you're using testnet.bybit.com (not demo trading)")
    finally:
        await adapter.disconnect()

asyncio.run(verify_bybit())
```

**Expected output:**
```
Verifying Bybit testnet setup...
✓ Connection successful
✓ Account info: Balance = 50000.00 USDT
✓ Position query: 0 open positions

✅ Bybit testnet setup verified!
```

### Reference Links

- [Bybit Testnet](https://testnet.bybit.com)
- [API Management](https://testnet.bybit.com/app/user/api-management)
- [API Documentation](https://bybit-exchange.github.io/docs/v5/intro)

---

## Lighter.xyz Testnet

### Authentication Model

Lighter uses a unique authentication system combining:
1. **ETH Wallet Private Key** - For signing transactions
2. **API Private Key** - Generated on the Lighter platform
3. **Account Index** - Your account number on Lighter
4. **API Key Index** - Index of your API key (2-254)

### Step-by-Step Setup

#### 1. Create Ethereum Wallet

If you don't have one, create using MetaMask or:

```python
from eth_account import Account
account = Account.create()
print(f"Address: {account.address}")
print(f"Private Key: {account.key.hex()}")
```

#### 2. Access Lighter Testnet

1. Go to https://testnet.app.lighter.xyz
2. Connect your Ethereum wallet
3. Sign the message to create your Lighter account

#### 3. Get Testnet Funds

1. After connecting, you may receive testnet tokens automatically
2. Check the testnet faucet if available
3. Look for a "Get Test Funds" option in the interface

#### 4. Generate API Key

1. Navigate to Settings or API section
2. Click "Create API Key" or "Generate New Key"
3. You'll receive:
   - API Private Key (for signing API requests)
   - API Key Index (a number between 2-254)
4. Your Account Index is typically 0 for the first account

**Note:** API key indices 0 and 1 are reserved:
- 0: Desktop application
- 1: Mobile application
- 2-254: Available for API keys

#### 5. Configure Environment Variables

```bash
# In your .env file:

# The API key's private key (from Lighter app)
LIGHTER_API_PRIVATE_KEY=0x1234567890abcdef...

# Your ETH wallet private key (for signing)
LIGHTER_ETH_PRIVATE_KEY=0x1234567890abcdef...

# Your account index (usually 0)
LIGHTER_ACCOUNT_INDEX=0

# Your API key index (2-254)
LIGHTER_API_KEY_INDEX=2
```

### Important Notes

- Lighter is a DEX on Ethereum L2, so transactions require ETH wallet signatures
- The API uses both WebSocket and REST endpoints
- Testnet behavior should mirror mainnet closely

### Verify Setup

Run this code to confirm your Lighter.xyz testnet setup is working:

```python
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def verify_lighter():
    from rustybt.live.brokers.lighter_adapter import LighterBrokerAdapter

    print("Verifying Lighter.xyz testnet setup...")

    adapter = LighterBrokerAdapter(testnet=True)

    try:
        await adapter.connect()
        print("✓ Connection successful")
        print(f"  API URL: {adapter.api_url}")

        info = await adapter.get_account_info()
        print(f"✓ Account info: Balance = {info['balance']} USDC")

        positions = await adapter.get_positions()
        print(f"✓ Position query: {len(positions)} open positions")

        print("\n✅ Lighter.xyz testnet setup verified!")

    except Exception as e:
        print(f"✗ Verification failed: {e}")
        print("\nTroubleshooting:")
        print("  - Check LIGHTER_PRIVATE_KEY is set (64 hex chars without 0x)")
        print("  - Verify account created at testnet.app.lighter.xyz")
        print("  - Ensure testnet funds are available")
    finally:
        await adapter.disconnect()

asyncio.run(verify_lighter())
```

**Expected output:**
```
Verifying Lighter.xyz testnet setup...
✓ Connection successful
  API URL: https://testnet.zklighter.elliot.ai
✓ Account info: Balance = 10000.00 USDC
✓ Position query: 0 open positions

✅ Lighter.xyz testnet setup verified!
```

### Reference Links

- [Lighter Testnet](https://testnet.app.lighter.xyz)
- [API Documentation](https://apidocs.lighter.xyz)
- [Python SDK](https://github.com/elliottech/lighter-python)
- Testnet API Base: `https://testnet.zklighter.elliot.ai`
- Mainnet API Base: `https://mainnet.zklighter.elliot.ai`

---

## Running Tests with Credentials

### Setting Up Your Environment

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials for the exchanges you want to test

3. Load environment variables before running tests:
   ```bash
   # Using direnv (recommended)
   direnv allow

   # Or source manually
   source .env

   # Or use python-dotenv in tests (automatic)
   ```

### Running Testnet Integration Tests

```bash
# Run all testnet tests (skips tests without credentials)
pytest tests/live/testnet/ -v

# Run specific exchange tests
pytest tests/live/testnet/test_hyperliquid_testnet.py -v
pytest tests/live/testnet/test_binance_testnet.py -v
pytest tests/live/testnet/test_bybit_testnet.py -v

# Run with verbose output to see skip reasons
pytest tests/live/testnet/ -v -rs
```

### Test Behavior

- Tests **automatically skip** if credentials are not available
- Tests use minimal order sizes to conserve testnet funds
- Limit orders are placed at unlikely prices to avoid fills
- All tests clean up orders after completion

### Verifying Credentials

Before running full tests, verify your credentials are loaded:

```python
from dotenv import load_dotenv
import os

load_dotenv()

# Check Hyperliquid
key = os.environ.get("HYPERLIQUID_PRIVATE_KEY", "")
print(f"Hyperliquid key length: {len(key)} (expected 66)")

# Check Binance
print(f"Binance API Key set: {bool(os.environ.get('BINANCE_TESTNET_API_KEY'))}")

# Check Bybit
print(f"Bybit API Key set: {bool(os.environ.get('BYBIT_TESTNET_API_KEY'))}")

# Check Lighter
print(f"Lighter API Key set: {bool(os.environ.get('LIGHTER_API_PRIVATE_KEY'))}")
```

---

## Security Best Practices

1. **Never commit `.env` to version control**
   - The `.gitignore` already excludes `.env`

2. **Use separate keys for testing vs production**
   - Create different API keys for each environment

3. **Enable IP whitelisting where available**
   - Restricts API access to specific IP addresses

4. **Disable withdrawal permissions**
   - Trading bots don't need withdrawal access

5. **Rotate keys periodically**
   - Replace API keys every 3-6 months

6. **Use API wallets for DEXes**
   - For Hyperliquid, use API wallets instead of main wallet keys

---

## Troubleshooting

### "Credentials not available" - tests skipping

- Verify environment variables are set: `echo $VARIABLE_NAME`
- Check for typos in variable names
- Ensure `.env` file is loaded

### "Invalid private key length" - Hyperliquid

- Verify key is exactly 64 hex chars (without 0x) or 66 chars (with 0x)
- Check for trailing whitespace or newlines
- Remove quotes around the value in `.env`

### "Authentication failed" - Binance/Bybit

- Verify you're using testnet keys (not mainnet)
- Check API permissions are enabled
- Ensure secret is correct (shown only once during creation)

### Rate limit errors

- Add delays between rapid API calls
- Check exchange-specific rate limits
- Consider using built-in rate limiting in adapters

---

## Quick Verification Script

Use this all-in-one script to verify all configured testnet connections:

```python
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def verify_all_testnets():
    """Verify all configured testnet connections."""
    print("=" * 50)
    print("rustybt Testnet Setup Verification")
    print("=" * 50)

    results = {}

    # Check Hyperliquid
    if os.environ.get("HYPERLIQUID_PRIVATE_KEY"):
        try:
            from rustybt.live.brokers import HyperliquidBrokerAdapter
            adapter = HyperliquidBrokerAdapter(testnet=True)
            await adapter.connect()
            info = await adapter.get_account_info()
            await adapter.disconnect()
            results["Hyperliquid"] = f"✓ Balance: {info['balance']} USDC"
        except Exception as e:
            results["Hyperliquid"] = f"✗ {e}"
    else:
        results["Hyperliquid"] = "⊘ Not configured"

    # Check Binance
    if os.environ.get("BINANCE_TESTNET_API_KEY"):
        try:
            from rustybt.live.brokers import BinanceBrokerAdapter
            adapter = BinanceBrokerAdapter(
                api_key=os.environ["BINANCE_TESTNET_API_KEY"],
                api_secret=os.environ["BINANCE_TESTNET_SECRET"],
                market_type="futures",
                testnet=True
            )
            await adapter.connect()
            info = await adapter.get_account_info()
            await adapter.disconnect()
            results["Binance"] = f"✓ Balance: {info['balance']} USDT"
        except Exception as e:
            results["Binance"] = f"✗ {e}"
    else:
        results["Binance"] = "⊘ Not configured"

    # Check Bybit
    if os.environ.get("BYBIT_TESTNET_API_KEY"):
        try:
            from rustybt.live.brokers import BybitBrokerAdapter
            adapter = BybitBrokerAdapter(
                api_key=os.environ["BYBIT_TESTNET_API_KEY"],
                api_secret=os.environ["BYBIT_TESTNET_SECRET"],
                category="linear",
                testnet=True
            )
            await adapter.connect()
            info = await adapter.get_account_info()
            await adapter.disconnect()
            results["Bybit"] = f"✓ Balance: {info['balance']} USDT"
        except Exception as e:
            results["Bybit"] = f"✗ {e}"
    else:
        results["Bybit"] = "⊘ Not configured"

    # Check Lighter
    if os.environ.get("LIGHTER_PRIVATE_KEY"):
        try:
            from rustybt.live.brokers.lighter_adapter import LighterBrokerAdapter
            adapter = LighterBrokerAdapter(testnet=True)
            await adapter.connect()
            info = await adapter.get_account_info()
            await adapter.disconnect()
            results["Lighter.xyz"] = f"✓ Balance: {info['balance']} USDC"
        except Exception as e:
            results["Lighter.xyz"] = f"✗ {e}"
    else:
        results["Lighter.xyz"] = "⊘ Not configured"

    # Print results
    print("\nResults:")
    print("-" * 50)
    for exchange, status in results.items():
        print(f"  {exchange:15} {status}")

    # Summary
    configured = sum(1 for s in results.values() if not s.startswith("⊘"))
    passed = sum(1 for s in results.values() if s.startswith("✓"))
    print("-" * 50)
    print(f"Configured: {configured}/4 | Passed: {passed}/{configured}")

if __name__ == "__main__":
    asyncio.run(verify_all_testnets())
```

**Example output:**
```
==================================================
rustybt Testnet Setup Verification
==================================================

Results:
--------------------------------------------------
  Hyperliquid     ✓ Balance: 10000.00 USDC
  Binance         ✓ Balance: 100000.00 USDT
  Bybit           ⊘ Not configured
  Lighter.xyz     ✓ Balance: 10000.00 USDC
--------------------------------------------------
Configured: 3/4 | Passed: 3/3
```

---

## Related Documentation

- [Live Trading Setup Guide](./setup-guide.md) - Platform setup and credentials
- [Lighter.xyz Integration](./lighter-integration.md) - Lighter.xyz specific documentation
- [Code Audit Report](./audit-report.md) - Production readiness audit results

---

*Last updated: 2025-12-07*
