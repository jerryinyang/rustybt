# Security Audit & Remediation

## Overview

This document summarizes security vulnerabilities identified in RustyBT and their remediation status.

Last Updated: 2025-10-13
Story: X2.1 - P0 Security & Test Infrastructure, X2.6 - P1 Dependency Hygiene

---

## Security Fixes Implemented

### 1. Safe Tarfile Extraction (FIXED)

**Vulnerability:** Path traversal attacks via malicious tar archives
**Location:** `rustybt/data/bundles/quandl.py:316-324`
**Risk Level:** High
**Status:** ✅ Remediated

**Description:**
Tarfile extraction without path validation could allow attackers to write files outside the intended extraction directory using path traversal techniques (e.g., `../../../etc/passwd`).

**Remediation:**
```python
# Validate all tar members before extraction
output_path = pathlib.Path(output_dir).resolve()
for member in tar.getmembers():
    member_path = (output_path / member.name).resolve()
    if not str(member_path).startswith(str(output_path)):
        raise ValueError(f"Attempted path traversal in tar file: {member.name}")
tar.extractall(output_dir)
```

**Test Coverage:**
- `tests/data/bundles/test_quandl_security.py` - 8 security tests
- Tests cover: `../` traversal, absolute paths, symlinks, legitimate extraction

---

### 2. Exec/Eval Security Documentation (DOCUMENTED)

**Vulnerability:** Dynamic code execution without security documentation
**Locations:**
- `rustybt/algorithm.py:421` - User algorithm execution
- `rustybt/utils/run_algo.py:135` - CLI parameter evaluation
- `rustybt/utils/run_algo.py:291` - Extension module loading
- `rustybt/utils/preprocess.py:247` - Function preprocessing

**Risk Level:** Medium (Trusted code sources)
**Status:** ✅ Documented

**Threat Model:**

| Location | Input Source | Trust Level | Risk |
|----------|-------------|-------------|------|
| algorithm.py | User algorithm code | Trusted | Low - users have full system access |
| run_algo.py (eval) | CLI arguments | Trusted | Low - user controls CLI input |
| run_algo.py (exec) | Extension files | Trusted | Low - user controls extension files |
| preprocess.py | Framework internals | Trusted | Low - internal code only |

**Security Model:**
RustyBT is a **local backtesting framework**, not a multi-tenant SaaS platform. Users run their own trading strategies on their own machines with full system privileges. The exec/eval usage is appropriate for this trust model.

**Mitigations:**
- All exec/eval calls annotated with `# nosec` and security comments
- Threat models documented in code
- Clear documentation that RustyBT is NOT suitable for untrusted code execution
- Future consideration: AST validation, process isolation for untrusted sources

---

### 3. SQL Parameterization (VALIDATED)

**Vulnerability:** SQL injection via f-string formatting
**Location:** `rustybt/assets/asset_db_migrations.py:49-84`
**Risk Level:** Low (Migration code only)
**Status:** ✅ Validated & Documented

**Context:**
SQL f-strings found in database migration code (Alembic). Table and column names are hardcoded in migration definitions, not derived from user input.

**Remediation:**
```python
# Validate table name is SQL-safe identifier
if not name.replace('_', '').isalnum():
    raise ValueError(f"Invalid table name for migration: {name!r}")

# Validate column names
for column in columns:
    if not column.name.replace('_', '').isalnum():
        raise ValueError(f"Invalid column name for migration: {column.name!r}")

# nosec B608 - table and column names validated as SQL identifiers above
op.execute(f"DROP INDEX IF EXISTS ix_{table}_{column.name}")
```

**Risk Assessment:**
- **Input Source:** Migration code (trusted)
- **Injection Risk:** Low - identifiers validated as alphanumeric
- **Parameterization:** Not applicable for DDL table/column names
- **Mitigation:** Whitelist validation ensures SQL-safe identifiers

---

### 4. Request Timeouts (FIXED)

**Vulnerability:** Network requests without timeout (DoS risk)
**Locations:**
- `rustybt/sources/requests_csv.py:533`
- `rustybt/data/bundles/quandl.py:252`
- `rustybt/data/bundles/quandl.py:281`
- `rustybt/__main__.py:2162`

**Risk Level:** Medium
**Status:** ✅ Remediated

**Remediation:**
All `requests.*` calls now include explicit `timeout=` parameters:
- Data fetching operations: `timeout=30` (30 seconds)
- Webhook notifications: `timeout=10` (10 seconds)

**Example:**
```python
# Before (vulnerable to hanging connections)
response = requests.get(url)

# After (protected with timeout)
response = requests.get(url, timeout=30)  # SECURITY FIX (Story X2.1)
```

---

## Dependency Security

**Last Scanned:** 2025-10-13
**Tool:** pip-audit 2.9.0
**Story:** X2.6 - P1 Dependency Hygiene

### Vulnerability Tracking

| Package | Version | Vulnerability | Severity | Status | Mitigation |
|---------|---------|---------------|----------|--------|------------|
| pip | 25.2 | CVE-2025-8869 / GHSA-4xh5-x5gv-qwph | High | Accepted (awaiting fix) | Dev-time risk only; install from trusted sources only |

**Production Dependencies:** ✅ **0 vulnerabilities**
**Dev Dependencies:** ⚠️ **1 accepted risk** (pip tarfile extraction)

### Accepted Risks

| Package | Vulnerability | Severity | Justification | Review Date |
|---------|---------------|----------|---------------|-------------|
| pip | CVE-2025-8869 (tarfile extraction path traversal) | High | Dev tooling only, not runtime dependency. Fix planned for pip 25.3. Mitigation: Only install packages from trusted sources (PyPI). | 2025-Q1 |

### Weekly Scan Results

Automated security scans run every Monday at 2 AM UTC via GitHub Actions workflow:
`.github/workflows/dependency-security.yml`

**Scan Tools:**
- `pip-audit` - Python dependency vulnerability scanner
- `safety` - Safety DB vulnerability scanner
- `scripts/check_licenses.py` - License compliance checker (Story X2.6)

Reports uploaded as artifacts to workflow runs.

### Dependency Upgrade Policy

**Immediate Upgrade (within 24 hours):**
- Critical vulnerabilities in production dependencies
- High vulnerabilities in production dependencies with active exploits

**Planned Upgrade (within 1 week):**
- High vulnerabilities in production dependencies
- Critical vulnerabilities in dev dependencies

**Scheduled Upgrade (next sprint):**
- Medium vulnerabilities in production dependencies
- High vulnerabilities in dev dependencies

**Monitored:**
- Low vulnerabilities (upgrade during regular dependency updates)
- Dev tooling vulnerabilities with no production impact

### License Compliance

**Policy:** Apache 2.0 / MIT / BSD / ISC licenses only
**Forbidden:** GPL, AGPL, LGPL, SSPL
**Enforcement:** `scripts/check_licenses.py` runs in CI/CD
**Status:** ⚠️ 2 LGPL exceptions documented below

**Known LGPL Dependencies (Accepted Risks):**

| Package | License | Used By | Type | Justification | Review Date |
|---------|---------|---------|------|---------------|-------------|
| chardet | LGPL | tox | Dev-only | Transitive dependency of tox (test tool). No production impact. Consider replacing tox or using charset-normalizer alternative. | 2025-Q2 |
| frozendict | LGPL v3 | yfinance | Production | Transitive dependency of yfinance (Yahoo Finance data). LGPL allows dynamic linking without GPL contamination. Consider forking yfinance with MIT alternative or finding different data provider. | 2025-Q1 |

**Note:** LGPL allows use as a library without contaminating our Apache 2.0 license, but we aim to replace these in future releases.

---

## Testing Infrastructure

### Pytest Markers

Test markers configured in `pyproject.toml` for selective test execution:

| Marker | Description | Usage |
|--------|-------------|-------|
| `memory` | Memory profiling benchmarks | `-m memory` |
| `api_integration` | External API integration tests | `-m api_integration` |
| `live` | Live broker connection tests | `-m live` |
| `ib_integration` | Interactive Brokers tests | `-m ib_integration` |

**CI/CD Test Command:**
```bash
pytest -m "not memory and not api_integration and not live and not ib_integration" \
  --cov=rustybt --cov-report=term --cov-report=html
```

### Test Coverage Requirements

- **Core modules:** ≥90% coverage
- **Financial modules:** ≥95% coverage (rustybt/finance/*, rustybt/analytics/*)
- **Configuration:** `pyproject.toml` → `[tool.coverage.report].fail_under`

### Test Extras Installation

```bash
# Install test dependencies
uv sync -E test

# Or with pip
pip install -e ".[test]"
```

**Test Dependencies:**
- pytest >= 7.2.0
- pytest-cov >= 3.0.0
- pytest-xdist >= 2.5.0 (parallel testing)
- freezegun >= 1.2.0 (time mocking)
- responses >= 0.9.0 (HTTP mocking)
- hypothesis >= 6.0 (property-based testing)

---

## Security Best Practices

### For Developers

1. **Never use exec/eval for untrusted input** - All dynamic code execution must be from trusted sources
2. **Always set request timeouts** - Network calls must have explicit timeout parameters
3. **Validate file paths** - Use `pathlib.Path.resolve()` to prevent path traversal
4. **Sanitize SQL identifiers** - Validate table/column names as alphanumeric
5. **Document security decisions** - Use `# SECURITY:` comments and `# nosec` annotations

### For Users

1. **RustyBT is for local use** - Not designed for shared hosting or untrusted code
2. **Review third-party strategies** - Algorithm code has full system access
3. **Keep dependencies updated** - Run `pip-audit` regularly for security advisories
4. **Use environment variables for secrets** - Never hardcode API keys in algorithm code
5. **Enable logging** - Monitor for suspicious activity in production

---

## Bandit Configuration

Security linting configured in `pyproject.toml`:

```toml
[tool.bandit]
exclude_dirs = ["tests/", "scripts/", "examples/"]
skips = []  # No global skips - use inline # nosec with justification
```

**Inline Security Annotations:**
- `# nosec B102` - exec() for trusted code
- `# nosec B307` - eval() for trusted CLI input
- `# nosec B608` - SQL f-strings with validated identifiers

---

## Future Security Enhancements

### Short Term
- [ ] Add AST validation for user algorithm code
- [ ] Implement resource limits (CPU, memory, time) for algorithm execution
- [ ] Add secrets detection in pre-commit hooks (detect-secrets, truffleHog)

### Medium Term
- [ ] Process isolation for untrusted algorithm execution
- [ ] Sandboxing for third-party extensions
- [ ] Rate limiting for API calls

### Long Term
- [ ] Multi-tenant architecture with proper isolation
- [ ] Comprehensive security audit by external firm
- [ ] SOC 2 compliance for cloud offering

---

## Reporting Security Issues

**Do NOT open public GitHub issues for security vulnerabilities.**

Instead, email security findings to: [security@ml4trading.io](mailto:security@ml4trading.io)

**Include:**
- Detailed description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested remediation (optional)

We aim to respond within 48 hours and provide a fix within 30 days for high-severity issues.

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/latest/library/security_warnings.html)
- [Bandit Security Linter](https://bandit.readthedocs.io/)
- [CWE-22: Path Traversal](https://cwe.mitre.org/data/definitions/22.html)
- [CWE-89: SQL Injection](https://cwe.mitre.org/data/definitions/89.html)
- [CWE-95: Code Injection](https://cwe.mitre.org/data/definitions/95.html)
