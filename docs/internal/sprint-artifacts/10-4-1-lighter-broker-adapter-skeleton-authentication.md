# Story 10.4.1: Lighter.xyz Broker Adapter Skeleton & Authentication

Status: review

## Story

As a **developer**,
I want **a LighterBrokerAdapter class that authenticates with Lighter.xyz API**,
So that **I can establish secure connections for trading**.

## Acceptance Criteria

1. **AC1:** `LighterBrokerAdapter` class exists in `rustybt/live/brokers/lighter_adapter.py`:
   - Extends `BrokerAdapter` ABC
   - Implements required interface methods (stubs initially)

2. **AC2:** Private key is loaded securely via priority order:
   - Priority 1: Environment variable `LIGHTER_PRIVATE_KEY`
   - Priority 2: Encrypted keystore file + encryption key
   - Priority 3: Direct parameter (logs warning)

3. **AC3:** Private key validation works:
   - Validates format (64 hex characters)
   - Derives wallet address
   - Logs masked address (not full key)

4. **AC4:** `connect()` method works:
   - Connection to Lighter.xyz API established
   - Account info retrieved to verify credentials
   - Testnet/mainnet URL selected based on `testnet` parameter (default: testnet)

5. **AC5:** Invalid credentials raise appropriate error:
   - `LighterKeyError` raised with helpful message
   - No sensitive data in error message

## Tasks / Subtasks

- [x] Task 1: Create adapter file and class skeleton (AC: #1)
  - [x] Create `rustybt/live/brokers/lighter_adapter.py`
  - [x] Define `LighterBrokerAdapter` class
  - [x] Implement `BrokerAdapter` ABC interface (stub methods)
  - [x] Add API URL constants (mainnet, testnet)

- [x] Task 2: Implement secure key loading (AC: #2)
  - [x] Create `_load_private_key()` method
  - [x] Check environment variable first
  - [x] Check encrypted keystore second
  - [x] Check direct parameter (with warning)
  - [x] Raise `LighterKeyError` if no key found

- [x] Task 3: Implement key validation (AC: #3)
  - [x] Create `_validate_private_key()` method
  - [x] Validate hex format
  - [x] Validate length (64 characters)
  - [x] Derive wallet address using eth-account
  - [x] Log masked address

- [x] Task 4: Implement encrypted keystore support (AC: #2)
  - [x] Create `_load_encrypted_key()` method
  - [x] Use Fernet encryption
  - [x] Support keystore file path parameter
  - [x] Support encryption key from env or parameter

- [x] Task 5: Implement connect method (AC: #4)
  - [x] Create `connect()` async method
  - [x] Select API URL based on testnet parameter
  - [x] Initialize lighter-sdk client
  - [x] Verify credentials with account info call
  - [x] Log connection success

- [x] Task 6: Implement error handling (AC: #5)
  - [x] Create `LighterKeyError` exception class
  - [x] Create `LighterConnectionError` exception class
  - [x] Ensure no sensitive data in error messages
  - [x] Log errors with context (no credentials)

- [x] Task 7: Write unit tests (AC: #1-5)
  - [x] Create `tests/live/lighter/test_lighter_broker.py`
  - [x] Test key loading priority
  - [x] Test key validation
  - [x] Test connect with mock
  - [x] Test error handling

## Dev Notes

### Class Structure

```python
class LighterBrokerAdapter(BrokerAdapter):
    """Lighter.xyz broker adapter for perpetual futures trading.

    Implements BrokerAdapter interface for Lighter DEX integration.
    Uses lighter-sdk for API communication and transaction signing.
    """

    # API endpoints
    MAINNET_API_URL = "https://mainnet.zklighter.elliot.ai/"
    TESTNET_API_URL = "https://testnet.zklighter.elliot.ai/"

    def __init__(
        self,
        private_key: str | None = None,
        encrypted_key_path: str | None = None,
        encryption_key: str | None = None,
        testnet: bool = True,  # Default to testnet for safety
    ) -> None:
        """Initialize Lighter adapter with secure key management."""
        self._testnet = testnet
        self._private_key = self._load_private_key(
            private_key, encrypted_key_path, encryption_key
        )
        self._client = None
        self._connected = False
```

### Key Loading Pattern (from Architecture Pattern 1)

```python
def _load_private_key(
    self,
    private_key: str | None,
    encrypted_key_path: str | None,
    encryption_key: str | None,
) -> str:
    # Method 1: Environment variable (RECOMMENDED)
    env_key = os.environ.get("LIGHTER_PRIVATE_KEY")
    if env_key:
        logger.info("private_key_loaded_from_environment")
        return self._validate_private_key(env_key)

    # Method 2: Encrypted keystore (RECOMMENDED)
    if encrypted_key_path and encryption_key:
        return self._load_encrypted_key(encrypted_key_path, encryption_key)

    # Method 3: Direct parameter (NOT RECOMMENDED)
    if private_key:
        logger.warning("private_key_loaded_from_parameter")
        return self._validate_private_key(private_key)

    raise LighterKeyError("No private key provided")
```

### Encrypted Keystore (using Fernet)

```python
from cryptography.fernet import Fernet

def _load_encrypted_key(self, keystore_path: str, encryption_key: str) -> str:
    """Load and decrypt private key from encrypted keystore."""
    fernet = Fernet(encryption_key.encode())
    with open(keystore_path, 'rb') as f:
        encrypted_data = f.read()
    decrypted = fernet.decrypt(encrypted_data).decode()
    return self._validate_private_key(decrypted)
```

### Architecture Patterns and Constraints

From Architecture document:
- **ADR-001**: Follow HyperliquidBrokerAdapter pattern exactly
- **ADR-003**: Default to testnet (`testnet=True`)
- **Pattern 1**: Private Key Security - env vars, encrypted keystores, never log

From NFRs:
- **NFR13**: API keys and private keys MUST never be logged
- **NFR14**: Credentials loaded from environment variables or secure config
- **NFR15**: Testnet/mainnet clearly separated

### Prerequisites

- Epic 10.1 must be complete (audit findings resolved)
- `lighter-sdk` package installed
- `cryptography` package available (for Fernet)

### References

- [Source: docs/internal/planning/architecture-epic-10.md#ADR-001: Follow HyperliquidBrokerAdapter Pattern]
- [Source: docs/internal/planning/architecture-epic-10.md#Pattern 1: Private Key Security]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.4.1]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.4.1]

## Dev Agent Record

### Context Reference

- `docs/internal/sprint-artifacts/10-4-1-lighter-broker-adapter-skeleton-authentication.context.xml`

### Agent Model Used

Claude claude-opus-4-5-20251101

### Debug Log References

- Created LighterBrokerAdapter following HyperliquidBrokerAdapter pattern
- Implemented secure key loading with three-tier priority (env var > encrypted keystore > direct param)
- Used Fernet encryption for encrypted keystore support
- Added wallet address derivation using eth-account
- Implemented connect() with lighter-sdk ApiClient and SignerClient
- Added comprehensive unit tests (34 tests, all passing)

### Completion Notes List

- ✅ LighterBrokerAdapter class created at `rustybt/live/brokers/lighter_adapter.py`
- ✅ Follows HyperliquidBrokerAdapter pattern per ADR-001
- ✅ Defaults to testnet per ADR-003
- ✅ Private key never logged (NFR13)
- ✅ Exception classes: LighterKeyError, LighterConnectionError, LighterOrderRejectError, LighterRateLimitError
- ✅ 34 unit tests covering key loading, validation, connect, disconnect, error handling
- ✅ Stub methods implemented for Stories 10.4.2-10.4.6 and 10.5.x

### File List

| File | Action |
|------|--------|
| `rustybt/live/brokers/lighter_adapter.py` | Created |
| `rustybt/live/brokers/__init__.py` | Modified (added LighterBrokerAdapter export) |
| `tests/live/lighter/__init__.py` | Created |
| `tests/live/lighter/test_lighter_broker.py` | Created |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implementation complete, all 34 tests passing | Dev Agent |
