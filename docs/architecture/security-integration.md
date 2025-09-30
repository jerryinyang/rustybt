# Security Integration

## Credential Management

**Encryption at Rest:**
- All broker API keys encrypted using `cryptography.fernet`
- Encryption key stored in environment variable: `RUSTYBT_ENCRYPTION_KEY`
- Key generation: `python -m rustybt keygen`

**Implementation:**
```python
from cryptography.fernet import Fernet
import os

def encrypt_credential(plaintext: str) -> bytes:
    """Encrypt API key/secret."""
    key = os.environ.get("RUSTYBT_ENCRYPTION_KEY")
    if not key:
        raise ValueError("RUSTYBT_ENCRYPTION_KEY not set")

    f = Fernet(key.encode())
    return f.encrypt(plaintext.encode())

def decrypt_credential(ciphertext: bytes) -> str:
    """Decrypt API key/secret."""
    key = os.environ.get("RUSTYBT_ENCRYPTION_KEY")
    if not key:
        raise ValueError("RUSTYBT_ENCRYPTION_KEY not set")

    f = Fernet(key.encode())
    return f.decrypt(ciphertext).decode()
```

**Storage:**
- Encrypted credentials in `broker_connections.api_key_encrypted` column
- Never log or expose credentials in plaintext
- Rotate encryption key periodically (recommend: quarterly)

**Key Management Best Practices:**
- Production: Store encryption key in hardware security module (HSM) or cloud KMS
- Development: Store in `.env` file (never commit to git)
- Disaster Recovery: Backup encryption key securely offsite

## API Rate Limiting

**Purpose:** Prevent abuse of RESTful API (Epic 9) and protect against brute-force attacks

**Implementation:**
- Use `slowapi` for FastAPI rate limiting
- Limits:
  - Anonymous: 100 requests/hour
  - Authenticated: 10,000 requests/hour
  - WebSocket: 10 connections per user

**Example:**
```python
from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/portfolio")
@limiter.limit("100/hour")
async def get_portfolio(request: Request):
    return {"portfolio_value": "1000000.00"}
```

**Broker API Rate Limiting:**
- Respect broker-specific rate limits (see External API Integration section)
- Implement token bucket algorithm for smooth rate limiting
- Retry with exponential backoff on rate limit errors

## Audit Logging

**Comprehensive Trade-by-Trade Logging:**
- All orders logged to `order_audit_log` table (JSON format)
- Searchable via SQL queries
- Immutable (append-only, no updates/deletes)

**Log Retention:**
- Regulatory requirement: 7 years (configurable)
- Automatic archival to cold storage after 1 year
- Compressed archives with integrity checksums

**Audit Log Query Example:**
```sql
-- Find all trades for AAPL in January 2023
SELECT
    event_timestamp,
    event_type,
    json_extract(event_data, '$.fill_price') as fill_price,
    json_extract(event_data, '$.filled_amount') as filled_amount
FROM order_audit_log
WHERE
    asset_sid = (SELECT sid FROM equities WHERE symbol = 'AAPL')
    AND event_timestamp BETWEEN 1672531200 AND 1675209600
    AND event_type = 'filled'
ORDER BY event_timestamp;
```

**Regulatory Compliance:**
- MiFID II (Europe): Trade reporting, record keeping
- SEC Rule 17a-4 (US): Broker-dealer record retention
- GDPR (Europe): Data protection, user privacy (if applicable)

## Input Validation and Sanitization

**Data Validation:**
- Use Pydantic models for all external inputs (API requests, config files)
- Validate OHLCV data: relationships, outliers, temporal consistency
- Reject malformed inputs with clear error messages

**Example:**
```python
from pydantic import BaseModel, Field, validator
from decimal import Decimal

class OrderRequest(BaseModel):
    asset_symbol: str = Field(..., min_length=1, max_length=20)
    amount: Decimal = Field(..., gt=0)
    order_type: str = Field(..., regex="^(market|limit|stop)$")
    limit_price: Optional[Decimal] = Field(None, gt=0)

    @validator('limit_price')
    def limit_price_required_for_limit_orders(cls, v, values):
        if values.get('order_type') == 'limit' and v is None:
            raise ValueError('limit_price required for limit orders')
        return v
```

**SQL Injection Prevention:**
- Use parameterized queries via SQLAlchemy ORM
- Never construct SQL strings with user input
- Example:
  ```python
  # CORRECT: Parameterized query
  result = session.query(Order).filter(Order.asset_sid == asset_sid).all()

  # INCORRECT: String concatenation (NEVER DO THIS)
  # result = session.execute(f"SELECT * FROM orders WHERE asset_sid = {asset_sid}")
  ```

## Network Security

**TLS Everywhere:**
- All broker API calls use HTTPS/WSS
- WebSocket API (Epic 9) uses WSS (TLS-encrypted WebSockets)
- Certificate validation enabled (no `verify=False`)

**Firewall Rules:**
- Allow outbound HTTPS (443) to broker APIs
- Allow inbound only on API port (default: 8000) if exposing API
- Block all other inbound traffic

**VPN for Remote Access:**
- Require VPN for remote server administration
- Use key-based SSH authentication (disable password auth)
- Restrict SSH to specific IP ranges

## Secrets Management

**Environment Variables:**
- Store sensitive config in environment variables, not code
- Use `.env` files locally (never commit)
- Use secrets management in production (AWS Secrets Manager, HashiCorp Vault)

**Configuration:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

ENCRYPTION_KEY = os.environ["RUSTYBT_ENCRYPTION_KEY"]
DATABASE_URL = os.environ.get("RUSTYBT_DATABASE_URL", "sqlite:///~/.rustybt/assets.db")
LOG_LEVEL = os.environ.get("RUSTYBT_LOG_LEVEL", "INFO")
```

**Secrets Scanning:**
- Use `truffleHog` or `git-secrets` to scan for leaked credentials
- Pre-commit hooks to prevent accidental commits
- Regular scans of repository history

## Security Updates

**Dependency Scanning:**
- Use `safety` to check for known vulnerabilities
- Run on every CI build: `safety check`
- Update vulnerable dependencies promptly

**Patch Management:**
- Subscribe to security advisories for dependencies
- Monthly security update cycle
- Critical vulnerabilities patched within 48 hours

---
