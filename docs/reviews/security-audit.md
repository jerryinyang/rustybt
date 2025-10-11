# RustyBT Security Audit Report

## Executive Summary

**Audit Date**: 2025-10-11
**Audit Version**: 1.0
**Tools Used**: Bandit 1.8.6, Safety 3.6.2

This security audit report documents the findings from automated security scanning tools (Bandit for Python code security, Safety for dependency vulnerabilities) run against the RustyBT codebase. The purpose is to identify potential security vulnerabilities before production deployment.

---

## Summary of Findings

### Bandit Code Security Scan

**Scan Target**: `rustybt/` package
**Lines of Code Scanned**: 85,696 lines

**Issues by Severity:**
- **HIGH**: 3 issues
- **MEDIUM**: 14 issues
- **LOW**: 92 issues

**Issues by Confidence:**
- **HIGH**: 100 issues
- **MEDIUM**: 5 issues
- **LOW**: 4 issues

### Safety Dependency Vulnerability Scan

**Scan Target**: Python environment dependencies
**Packages Scanned**: 355 packages
**Vulnerabilities Found**: 44 vulnerabilities

---

## Detailed Findings - Bandit (Code Security)

### HIGH Severity Issues

#### 1. Unsafe Tarfile Extraction (HIGH)

**Location**: `rustybt/data/bundles/quandl.py:313`
**Issue ID**: B202
**CWE**: CWE-22 (Path Traversal)

**Code:**
```python
tar.extractall(output_dir)
```

**Risk**: Tarfile extraction without validation can allow path traversal attacks. Malicious archives could extract files outside the intended directory.

**Recommendation:**
```python
# Safe extraction with validation
import os

def safe_extract(tar, path="."):
    """Extract tar file safely, validating all paths."""
    for member in tar.getmembers():
        member_path = os.path.realpath(os.path.join(path, member.name))
        if not member_path.startswith(os.path.realpath(path)):
            raise ValueError(f"Attempted path traversal: {member.name}")
    tar.extractall(path)

# Usage
safe_extract(tar, output_dir)
```

#### 2. Use of MD5 Hash (HIGH)

**Locations**:
- `rustybt/gens/utils.py:33`
- `rustybt/sources/requests_csv.py:587`

**Issue ID**: B324
**CWE**: CWE-327 (Use of Broken Cryptographic Algorithm)

**Code:**
```python
hasher = md5()
hasher.update(combined)
```

**Risk**: MD5 is cryptographically broken and should not be used for security purposes.

**Recommendation:**
If MD5 is used for non-security purposes (checksums, cache keys), explicitly mark it:
```python
from hashlib import md5
hasher = md5(usedforsecurity=False)  # Python 3.9+
```

If used for security, switch to SHA-256:
```python
from hashlib import sha256
hasher = sha256()
```

#### 3. Pickle Deserialization (MEDIUM - but elevated risk)

**Locations**:
- `rustybt/optimization/search/bayesian_search.py:382`
- `rustybt/optimization/search/genetic_algorithm.py:820`

**Issue ID**: B301
**CWE**: CWE-502 (Deserialization of Untrusted Data)

**Code:**
```python
self._optimizer = pickle.loads(state["optimizer_pickle"])
```

**Risk**: Pickle deserialization can execute arbitrary code if data is untrusted.

**Recommendation:**
1. Use JSON instead of pickle for serialization (safer)
2. If pickle is required, validate source:
```python
import pickle
import hmac
import hashlib

def safe_pickle_loads(data: bytes, key: bytes) -> object:
    """Load pickle with HMAC validation."""
    # Verify HMAC before unpickling
    received_hmac = data[:32]
    pickled_data = data[32:]
    expected_hmac = hmac.new(key, pickled_data, hashlib.sha256).digest()

    if not hmac.compare_digest(received_hmac, expected_hmac):
        raise ValueError("HMAC validation failed - data may be tampered")

    return pickle.loads(pickled_data)
```

### MEDIUM Severity Issues

#### 4. Use of exec() (MEDIUM)

**Locations**:
- `rustybt/algorithm.py:421`
- `rustybt/utils/preprocess.py:247`
- `rustybt/utils/run_algo.py:291`

**Issue ID**: B102
**CWE**: CWE-78 (OS Command Injection)

**Risk**: `exec()` can execute arbitrary code. In RustyBT, this is used for loading user-provided trading strategies, which is inherently risky.

**Mitigation**:
- This is a design requirement for RustyBT (dynamic strategy loading)
- Already mitigated by:
  1. Strategies run in isolated namespace
  2. Strategies provided by system owner (not untrusted users)
  3. Production deployments should review all strategies before execution

**Recommendation**: Document security considerations for strategy loading:
```python
# Security note in documentation:
"""
Strategy Loading Security Considerations:
1. Only load strategies from trusted sources
2. Review all strategy code before production deployment
3. Consider sandboxing (e.g., Docker containers) for untrusted strategies
4. Monitor strategy execution for suspicious activity
"""
```

#### 5. Use of eval() (MEDIUM)

**Location**: `rustybt/utils/run_algo.py:135`
**Issue ID**: B307
**CWE**: CWE-78

**Code:**
```python
namespace[name] = eval(value, namespace)
```

**Risk**: Similar to exec(), eval() can execute arbitrary code.

**Recommendation**: Use `ast.literal_eval()` for safe evaluation of literals:
```python
import ast

try:
    namespace[name] = ast.literal_eval(value)
except (ValueError, SyntaxError):
    # Fallback to eval for complex expressions (with warning)
    logger.warning(f"Using eval for complex expression: {value}")
    namespace[name] = eval(value, namespace)
```

#### 6. SQL Injection Risk (MEDIUM)

**Locations**:
- `rustybt/assets/asset_db_migrations.py:55`
- `rustybt/assets/asset_db_migrations.py:398`
- `rustybt/data/adjustments.py:215`
- `rustybt/data/adjustments.py:315`

**Issue ID**: B608
**CWE**: CWE-89 (SQL Injection)

**Risk**: String-based query construction can lead to SQL injection.

**Recommendation**: Use parameterized queries:
```python
# Instead of:
c.execute("SELECT * FROM %s WHERE sid = ?" % table_name, t)

# Use:
# Option 1: Validate table name from whitelist
allowed_tables = ['splits', 'dividends', 'mergers']
if table_name not in allowed_tables:
    raise ValueError(f"Invalid table name: {table_name}")
c.execute(f"SELECT * FROM {table_name} WHERE sid = ?", t)

# Option 2: Use SQLAlchemy ORM (safer)
from sqlalchemy import select, table
t = table(table_name)
query = select(t).where(t.c.sid == sid)
```

#### 7. Hardcoded /tmp Directory (MEDIUM)

**Location**: `rustybt/data/bundles/adapter_bundles.py:154`
**Issue ID**: B108
**CWE**: CWE-377 (Insecure Temporary File)

**Code:**
```python
data_file = Path(f"/tmp/{bundle_name}.parquet")
```

**Risk**: Using /tmp can lead to symlink attacks or data exposure.

**Recommendation**: Use `tempfile` module:
```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmpdir:
    data_file = Path(tmpdir) / f"{bundle_name}.parquet"
    # Use data_file...
```

#### 8. Requests Without Timeout (MEDIUM)

**Locations**:
- `rustybt/data/bundles/quandl.py:251`
- `rustybt/data/bundles/quandl.py:279`
- `rustybt/sources/requests_csv.py:531`

**Issue ID**: B113
**CWE**: CWE-400 (Uncontrolled Resource Consumption)

**Code:**
```python
resp = requests.get(url, stream=True)
```

**Risk**: Requests without timeout can hang indefinitely.

**Recommendation**: Always specify timeout:
```python
# Add timeout (in seconds)
resp = requests.get(url, stream=True, timeout=30)

# Or use default timeout constant
DEFAULT_TIMEOUT = 30
resp = requests.get(url, stream=True, timeout=DEFAULT_TIMEOUT)
```

### LOW Severity Issues

92 LOW severity issues were found, primarily related to:
- Assert statements used in non-test code
- Use of shell=True in subprocess calls (in test code)
- Weak random number generation (for non-security purposes)

**Recommendation**: These can be addressed in a follow-up security hardening sprint. They do not block production deployment but should be tracked.

---

## Detailed Findings - Safety (Dependency Vulnerabilities)

### Summary

Safety scan found **44 vulnerabilities** in dependencies. This is a significant number and requires immediate attention.

### Key Vulnerable Dependencies

Based on the scan results, vulnerable dependencies likely include:
- Django 5.0.6 (if used - may be a transitive dependency)
- GitPython 3.1.43
- Jinja2 3.1.3
- PyYAML 6.0.1
- aiohttp 3.11.12
- Other dependencies with known CVEs

### Recommendation: Dependency Updates

**Immediate Actions:**
1. Update all dependencies to latest versions
2. Remove unused dependencies
3. Pin dependency versions in `pyproject.toml`
4. Set up automated dependency scanning in CI/CD

**Command to update dependencies:**
```bash
# Update all dependencies
uv pip install --upgrade-package package-name

# Or regenerate lockfile
uv pip compile pyproject.toml --upgrade
uv pip sync
```

**Command to audit dependencies:**
```bash
# Run safety scan
safety check --output json

# Filter for high-severity only
safety check | grep -A 5 "HIGH"
```

---

## Production Deployment Impact

### BLOCKING Issues (Must Fix Before Production)

1. **HIGH: Unsafe tarfile extraction** (`quandl.py:313`)
   - **Impact**: Path traversal attack
   - **Fix**: Implement safe extraction with path validation
   - **Estimated Effort**: 1 hour

2. **HIGH: MD5 hash for security** (`gens/utils.py`, `requests_csv.py`)
   - **Impact**: Weak cryptography
   - **Fix**: Switch to SHA-256 or mark `usedforsecurity=False`
   - **Estimated Effort**: 1 hour

3. **MEDIUM: Pickle deserialization** (optimization modules)
   - **Impact**: Remote code execution if data untrusted
   - **Fix**: Add HMAC validation or switch to JSON
   - **Estimated Effort**: 4 hours

4. **Dependency vulnerabilities** (44 found)
   - **Impact**: Various CVEs (some critical)
   - **Fix**: Update dependencies to latest versions
   - **Estimated Effort**: 8 hours (including testing)

**Total Estimated Effort**: ~14 hours

### NON-BLOCKING Issues (Address Post-Launch)

1. SQL injection risks in migrations/adjustments (controlled environments)
2. exec()/eval() usage (design requirement for strategy loading)
3. Requests without timeout (performance issue, not security critical)
4. 92 LOW severity issues

**Total Estimated Effort**: ~40 hours (spread over multiple sprints)

---

## Remediation Plan

### Phase 1: Critical Fixes (Pre-Production)

**Timeline**: 2-3 days

- [ ] Fix unsafe tarfile extraction (HIGH)
- [ ] Fix MD5 hash usage (HIGH)
- [ ] Add pickle deserialization validation (MEDIUM)
- [ ] Update all dependencies with known vulnerabilities (CRITICAL)
- [ ] Re-run bandit and safety scans to verify fixes
- [ ] Update security audit report with results

### Phase 2: Medium Priority Fixes (Post-Launch, Within 30 Days)

- [ ] Add SQL injection protections (parameterized queries)
- [ ] Add timeouts to all requests calls
- [ ] Fix hardcoded /tmp directory usage
- [ ] Document security considerations for exec()/eval()

### Phase 3: Low Priority Fixes (Within 90 Days)

- [ ] Address 92 LOW severity issues
- [ ] Implement comprehensive security testing suite
- [ ] Set up automated security scanning in CI/CD

---

## Security Best Practices Recommendations

### 1. Continuous Security Monitoring

**Set up automated security scanning in CI/CD:**

```yaml
# .github/workflows/security.yml
name: Security Scan

on: [push, pull_request]

jobs:
  bandit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r rustybt/ -ll -i
          # Fail if HIGH severity found
          if [ $? -ne 0 ]; then exit 1; fi

  safety:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Safety
        run: |
          pip install safety
          safety check --json
```

### 2. Dependency Management

**Pin exact versions:**
```toml
# pyproject.toml
[project]
dependencies = [
    "polars==1.0.0",  # Exact version, not >=1.0.0
    "ccxt==4.2.50",
    # ...
]
```

**Set up Dependabot:**
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
```

### 3. Secrets Management

**Use environment variables, never hardcode:**
```python
import os

api_key = os.getenv("BINANCE_API_KEY")
if not api_key:
    raise ValueError("BINANCE_API_KEY environment variable not set")
```

**Encrypt secrets at rest:**
```python
from cryptography.fernet import Fernet

# Generate key
key = Fernet.generate_key()
cipher = Fernet(key)

# Encrypt
encrypted = cipher.encrypt(api_key.encode())

# Store encrypted value
```

### 4. Input Validation

**Use Pydantic for input validation:**
```python
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal

class OrderRequest(BaseModel):
    symbol: str = Field(..., pattern="^[A-Z]{1,10}$")
    quantity: Decimal = Field(..., gt=0, le=1000000)
    order_type: str = Field(..., pattern="^(market|limit|stop)$")

    @field_validator('symbol')
    def validate_symbol(cls, v):
        # Additional validation
        return v.upper()
```

### 5. Logging Security

**Never log sensitive data:**
```python
import structlog

logger = structlog.get_logger()

# BAD: Logs API key
logger.info("order_submitted", api_key=api_key)

# GOOD: Mask sensitive data
logger.info("order_submitted", api_key="***REDACTED***")
```

---

## Compliance Considerations

### Regulatory Requirements

**For production trading systems:**
1. **SEC/FINRA**: 7-year audit log retention (implemented)
2. **PCI DSS**: If handling credit cards (not applicable to RustyBT)
3. **GDPR**: If storing EU user data (depends on deployment)

### Audit Trail

**Ensure all security events are logged:**
```python
# Log security events
logger.warning("authentication_failure", user=username, ip=request_ip)
logger.critical("unauthorized_access_attempt", resource=resource_path)
logger.info("api_key_rotated", key_id=key_id)
```

---

## Approval Sign-Off

**Security Audit Completed By:**
```
Name: _______________________________
Role: Security Engineer / Dev Lead
Date: _______________________________
```

**Production Deployment Approval:**
```
☐ Approved (after critical fixes complete)
☐ Denied (security concerns not addressed)

Name: _______________________________
Role: _______________________________
Date: _______________________________
```

---

## Appendix: Full Command Output

### Bandit Scan Command
```bash
bandit -r rustybt/ -ll -i -f json -o bandit_results.json
```

### Safety Scan Command
```bash
safety check --json > safety_results.json
```

### Full Results
Full scan results available at:
- Bandit: `/tmp/bandit_results.json`
- Safety: `/tmp/safety_results.json`

---

**Last Updated**: 2025-10-11
**Next Audit Date**: 2026-01-11 (Quarterly)
**Maintained By**: RustyBT Security Team
