# RustyBT Test Suite

## Test Structure

```
tests/
├── live/
│   └── brokers/           # Unit tests for broker adapters (mock-based)
├── integration/
│   └── live/              # Integration tests with real testnet accounts
└── README.md              # This file
```

## Running Tests

### Unit Tests (No Credentials Required)

Run all unit tests:
```bash
pytest tests/live/brokers/ -v
```

Run specific adapter tests:
```bash
pytest tests/live/brokers/test_binance_adapter.py -v
pytest tests/live/brokers/test_bybit_adapter.py -v
pytest tests/live/brokers/test_hyperliquid_adapter.py -v
pytest tests/live/brokers/test_ccxt_adapter.py -v
```

### Integration Tests (Testnet Credentials Required)

**Setup:**
See `tests/integration/live/README.md` for testnet account setup instructions.

**Run:**
```bash
pytest tests/integration/live/ -v -m exchange_integration
```

### All Tests

```bash
pytest tests/ -v
```

## Test Coverage

Generate coverage report:
```bash
pytest --cov=rustybt --cov-report=html --cov-report=term
```

View HTML report:
```bash
open htmlcov/index.html
```

## Test Markers

- `@pytest.mark.exchange_integration` - Integration tests requiring testnet credentials
- `@pytest.mark.websocket_integration` - WebSocket integration tests (Story 6.13)
- Tests are automatically skipped if credentials are not configured

## WebSocket Integration Tests (Story 6.13)

### Running WebSocket Tests

Run all WebSocket integration tests:
```bash
pytest tests/ -v -m websocket_integration
```

Run WebSocket tests for specific adapter:
```bash
pytest tests/live/brokers/test_bybit_adapter.py::TestBybitWebSocketIntegration -v
pytest tests/live/brokers/test_hyperliquid_adapter.py::TestHyperliquidWebSocketIntegration -v
pytest tests/live/brokers/test_ccxt_adapter.py::TestCCXTWebSocketIntegration -v
```

Run end-to-end integration tests:
```bash
pytest tests/integration/live/test_websocket_integration.py -v
```

### Testnet Setup for WebSocket Tests

WebSocket integration tests use mocked WebSocket adapters by default (no credentials needed). For testing with real testnet WebSocket connections, configure:

**Bybit Testnet:**
```bash
export BYBIT_API_KEY="your_testnet_api_key"
export BYBIT_API_SECRET="your_testnet_api_secret"
export BYBIT_TESTNET=true
```

**Hyperliquid Testnet:**
```bash
export HYPERLIQUID_PRIVATE_KEY="your_64_character_hex_private_key"
export HYPERLIQUID_TESTNET=true
```

**Binance Testnet:**
```bash
export BINANCE_API_KEY="your_testnet_api_key"
export BINANCE_API_SECRET="your_testnet_api_secret"
export BINANCE_TESTNET=true
```

**CCXT (Multi-Exchange):**
```bash
export CCXT_EXCHANGE_ID="binance"  # or coinbase, kraken, etc.
export CCXT_API_KEY="your_testnet_api_key"
export CCXT_API_SECRET="your_testnet_api_secret"
export CCXT_TESTNET=true
```

### Obtaining Testnet Credentials

**Bybit:**
1. Visit: https://testnet.bybit.com/
2. Create account
3. Navigate to API Management → Create New Key
4. Copy API Key and Secret

**Hyperliquid:**
1. Visit: https://app.hyperliquid-testnet.xyz/
2. Connect wallet (MetaMask recommended)
3. Export private key from wallet (Settings → Security → Export Private Key)
4. **SECURITY WARNING**: Use a dedicated testnet wallet, NEVER use mainnet keys

**Binance:**
1. Visit: https://testnet.binance.vision/
2. Login with GitHub
3. Generate HMAC_SHA256 API Key
4. Copy API Key and Secret

**CCXT (Exchange-Specific):**
Follow testnet setup for each exchange (Binance, Coinbase, Kraken, etc.)

## More Information

- [Integration Tests Setup](integration/live/README.md) - Testnet account setup guide
- [Testing Strategy](../docs/architecture/testing-strategy.md) - Overall testing approach
