# RustyBT Production Readiness Checklist

## Overview

This checklist ensures that RustyBT is ready for live trading deployment. **All items must be checked before deploying to production.** This is a BLOCKING checklist - any unchecked item blocks production deployment.

**Last Updated**: 2025-10-11
**Version**: 1.0

---

## 1. Testing & Quality Assurance

### 1.1 Test Coverage
- [ ] All unit tests pass
- [ ] Overall test coverage ≥ 90%
- [ ] Financial module test coverage ≥ 95%
- [ ] All integration tests pass
- [ ] Property-based tests pass (1000+ examples per test)
- [ ] No flaky or intermittent test failures
- [ ] Regression test suite passes

**Verification Command:**
```bash
pytest tests/ -v --cov=rustybt --cov-report=html --cov-report=term
# Verify coverage percentage in output
```

### 1.2 Code Quality
- [ ] Type checking passes: `mypy rustybt/ --strict`
- [ ] Linting passes: `ruff check rustybt/`
- [ ] Code formatting passes: `black --check rustybt/`
- [ ] No TODO/FIXME without issue tracking
- [ ] Cyclomatic complexity ≤ 10 per function
- [ ] No hardcoded values or mock code (Zero-Mock Enforcement)

**Verification Command:**
```bash
mypy rustybt/ --strict
ruff check rustybt/
black --check rustybt/
```

### 1.3 Zero-Mock Enforcement
- [ ] Mock detection scan passes: `python scripts/detect_mocks.py --strict`
- [ ] No hardcoded return values detected
- [ ] All validation functions perform real checks
- [ ] All tests exercise real functionality
- [ ] Different inputs produce different outputs (uniqueness test)

**Verification Command:**
```bash
python scripts/detect_mocks.py --strict
python scripts/detect_hardcoded_values.py
python scripts/verify_validations.py
```

---

## 2. Security

### 2.1 Security Audit
- [ ] Bandit security scan passes (no high-severity issues)
- [ ] Safety vulnerability scan passes (no known vulnerabilities)
- [ ] No hardcoded secrets in codebase
- [ ] SQL injection vulnerabilities checked
- [ ] Input validation implemented (Pydantic)
- [ ] Code review by security expert completed

**Verification Command:**
```bash
pip install bandit safety
bandit -r rustybt/ -ll -i
safety check --json
```

### 2.2 Credential Management
- [ ] Encryption key generated: `python -m rustybt keygen`
- [ ] Credentials encrypted at rest
- [ ] .env file secured (chmod 600)
- [ ] API keys not committed to version control
- [ ] API key rotation schedule documented (recommended: 90 days)
- [ ] Separate keys for dev/staging/production

**Verification Command:**
```bash
# Check file permissions
ls -la .env  # Should show -rw------- (600)

# Verify .env in .gitignore
grep -q "^\.env$" .gitignore && echo "OK" || echo "FAIL: Add .env to .gitignore"
```

### 2.3 Network Security
- [ ] Firewall configured (UFW/iptables)
- [ ] Only necessary ports allowed (SSH, API)
- [ ] SSH key-based authentication enabled
- [ ] Password authentication disabled
- [ ] TLS enabled for all broker API calls (HTTPS)
- [ ] IP whitelisting configured for broker APIs

**Verification Command:**
```bash
# Check firewall status
sudo ufw status verbose

# Check SSH config
grep "PasswordAuthentication" /etc/ssh/sshd_config  # Should be "no"
grep "PubkeyAuthentication" /etc/ssh/sshd_config   # Should be "yes"
```

---

## 3. Configuration

### 3.1 Broker Configuration
- [ ] Broker API keys configured
- [ ] Broker connection tested successfully
- [ ] Test orders executed successfully (paper trading)
- [ ] Account balance retrieved successfully
- [ ] Position reconciliation tested
- [ ] Order management tested (submit, cancel, modify)

**Verification Command:**
```bash
python -m rustybt test-broker --broker binance --testnet
```

### 3.2 Data Source Configuration
- [ ] Data sources configured (yfinance, CCXT)
- [ ] Data fetch tested successfully
- [ ] Historical data backfill completed
- [ ] Data validation rules implemented
- [ ] Missing data handling tested
- [ ] Data catalog configured

**Verification Command:**
```bash
python -m rustybt test-data --source yfinance
python -m rustybt fetch-data --source yfinance --symbols AAPL,MSFT --start 2024-01-01
```

### 3.3 Risk Limits Configuration
- [ ] Maximum position size configured (recommended: ≤ 10%)
- [ ] Maximum daily loss limit configured (recommended: ≤ 5%)
- [ ] Maximum leverage configured (recommended: ≤ 2x)
- [ ] Maximum open positions configured
- [ ] Risk limits tested (orders blocked when limits exceeded)
- [ ] Circuit breaker configured and tested

**Verification Command:**
```bash
python -m rustybt verify-config
grep -E "MAX_POSITION_SIZE|MAX_DAILY_LOSS|MAX_LEVERAGE" .env
```

### 3.4 Trading Calendar Configuration
- [ ] Trading calendar configured (NYSE, NASDAQ, 24/7)
- [ ] Market hours configured correctly
- [ ] Timezone configured correctly
- [ ] Holiday calendar updated
- [ ] Trading schedule tested (no orders outside market hours)

**Verification Command:**
```bash
python -c "from rustybt.utils.calendar_utils import get_calendar; cal = get_calendar('NYSE'); print(cal.is_open_now())"
```

---

## 4. Performance

### 4.1 Performance Benchmarks
- [ ] Performance benchmarks executed on production hardware
- [ ] Backtest execution time meets targets (Epic 7 goals)
- [ ] Order execution latency < 100ms (critical path)
- [ ] Memory usage stable (no leaks detected)
- [ ] Performance regression tests pass
- [ ] Benchmarks documented in `docs/performance/`

**Verification Command:**
```bash
python -m rustybt benchmark --suite backtest --iterations 10
python -m rustybt benchmark --suite order-execution --iterations 100
```

### 4.2 Hardware Requirements
- [ ] Production hardware meets minimum requirements:
  - CPU: 2+ cores (x86_64)
  - RAM: 8GB+ (16GB recommended)
  - Disk: 50GB+ SSD
  - Network: Stable internet (1+ Mbps)
- [ ] Performance validated on production hardware
- [ ] Load testing completed (peak load scenarios)
- [ ] Stress testing completed (extended run periods)

### 4.3 Scalability
- [ ] Data catalog cache configured appropriately
- [ ] Database connection pool sized correctly
- [ ] Worker thread count configured for CPU cores
- [ ] Concurrent order handling tested
- [ ] Large portfolio (100+ positions) tested

---

## 5. Monitoring & Alerting

### 5.1 Logging Configuration
- [ ] Structured logging configured (structlog)
- [ ] Log level configured (INFO for production)
- [ ] Log format configured (JSON for production)
- [ ] Log directory configured and writable
- [ ] Log rotation configured (daily, 90-day retention)
- [ ] Sensitive data excluded from logs (no API keys, passwords)

**Verification Command:**
```bash
grep -E "LOG_LEVEL|LOG_FORMAT|LOG_DIR" .env
ls -la ~/.rustybt/logs/  # Verify writable
```

### 5.2 Alert Configuration
- [ ] Critical error alerts configured (email/SMS/Slack)
- [ ] Alert contacts configured and tested
- [ ] Alert rules defined:
  - Broker connection failure
  - Circuit breaker trip
  - Order rejection
  - Daily loss limit reached
  - System errors (exceptions)
- [ ] Test alerts sent and received successfully

**Verification Command:**
```bash
python -m rustybt test-alerts
```

### 5.3 Health Monitoring
- [ ] Health check endpoint accessible (if API enabled)
- [ ] External uptime monitoring configured (UptimeRobot, Pingdom)
- [ ] Dashboard configured (optional: Grafana)
- [ ] Key metrics monitored:
  - Order execution latency
  - Error rate
  - Portfolio value
  - Position count
  - Daily P&L

**Verification Command:**
```bash
# If API enabled:
curl http://localhost:8000/health
```

---

## 6. Backup & Disaster Recovery

### 6.1 Backup Configuration
- [ ] Backup procedures documented
- [ ] Daily backups scheduled (cron/Task Scheduler)
- [ ] Backup includes:
  - Strategy state
  - Position state
  - Configuration files (.env, configs)
  - Trade history
  - Audit logs
- [ ] Offsite backup storage configured (AWS S3, GCS)
- [ ] Backup retention policy documented (7 years for audit logs)

**Verification Command:**
```bash
# Test backup script
./backup-rustybt.sh

# Verify backup created
ls -lh /backup/rustybt/rustybt_backup_*.tar.gz
```

### 6.2 Restore Procedures
- [ ] Restore procedures documented
- [ ] Restore tested successfully on clean system
- [ ] Position reconciliation tested after restore
- [ ] Strategy state restored correctly
- [ ] Trade history restored correctly
- [ ] Recovery Time Objective (RTO) documented (target: < 1 hour)
- [ ] Recovery Point Objective (RPO) documented (target: < 5 minutes)

**Verification Command:**
```bash
# Test restore on test VM
./restore-rustybt.sh /backup/rustybt/rustybt_backup_YYYYMMDD_HHMMSS.tar.gz
python -m rustybt verify-restore
```

### 6.3 Disaster Recovery Plan
- [ ] Disaster recovery plan documented
- [ ] Scenarios covered:
  - Server hardware failure
  - Data corruption
  - Security breach
  - Extended downtime
- [ ] Incident response plan documented
- [ ] Team trained on disaster recovery procedures
- [ ] Emergency contacts documented

---

## 7. Validation

### 7.1 Paper Trading Validation
- [ ] Paper trading executed for minimum 30 days (720 hours)
- [ ] Uptime measured and documented
- [ ] Target: 99.9% uptime (< 43 minutes downtime per 30 days)
- [ ] Error rate measured and documented
- [ ] Target: < 0.1% error rate (< 1 error per 1000 operations)
- [ ] All critical errors analyzed and resolved
- [ ] Performance metrics documented

**Verification Command:**
```bash
# Start paper trading validation
python -m rustybt paper-trade --strategy momentum.py --broker binance --duration 30d

# After 30 days, analyze results
python -m rustybt analyze-uptime --log-dir ~/.rustybt/logs --start-date 2025-01-01 --end-date 2025-01-30
```

**Uptime Calculation:**
```python
# Example calculation
total_hours = 720  # 30 days
downtime_minutes = 42  # Measured downtime
downtime_hours = downtime_minutes / 60  # 0.7 hours
uptime_pct = ((total_hours - downtime_hours) / total_hours) * 100
# uptime_pct = 99.903% ✓ Passes (≥ 99.9%)
```

### 7.2 Functional Validation
- [ ] Order lifecycle tested (submit → pending → filled)
- [ ] Position updates tested (open, increase, decrease, close)
- [ ] Portfolio calculations tested (value, P&L, returns)
- [ ] Strategy signals tested (buy, sell, hold)
- [ ] Data ingestion tested (real-time and historical)
- [ ] Risk checks tested (position size, leverage, daily loss)

### 7.3 Edge Case Testing
- [ ] Market data gaps handled correctly
- [ ] Broker connection loss handled correctly
- [ ] Order rejection handled correctly
- [ ] Insufficient funds handled correctly
- [ ] Market closed scenarios handled correctly
- [ ] High volatility scenarios tested

---

## 8. Documentation

### 8.1 Deployment Documentation
- [ ] Deployment guide complete: See [Deployment Guide](deployment-guide.md)
- [ ] User guides up to date: See [User Guides](../guides/decimal-precision-configuration.md)
- [ ] API documentation complete: See [API Reference](../api/order-types.md)
- [ ] Examples documentation up to date: See [Examples](../examples/README.md)

### 8.2 Operational Documentation
- [ ] Runbook created for common operations:
  - Start/stop trading engine
  - Deploy new strategy
  - Rotate API keys
  - Perform backup/restore
  - Handle emergencies
- [ ] Monitoring dashboard guide (if applicable)
- [ ] Alert response procedures documented

### 8.3 Team Training
- [ ] Team trained on platform operation
- [ ] Team trained on monitoring and alerts
- [ ] Team trained on disaster recovery procedures
- [ ] Team trained on incident response
- [ ] Training materials documented
- [ ] Knowledge transfer sessions completed

---

## 9. Compliance & Regulatory

### 9.1 Audit Logging
- [ ] Audit logging enabled (structlog)
- [ ] All trades logged with timestamp, asset, quantity, price
- [ ] All orders logged (submitted, filled, rejected, cancelled)
- [ ] All risk events logged (circuit breaker, limit breaches)
- [ ] Log retention: 7 years (regulatory requirement)
- [ ] Logs immutable and tamper-proof

### 9.2 Regulatory Compliance
- [ ] Regulatory requirements reviewed (SEC, FINRA, etc.)
- [ ] Compliance officer sign-off (if applicable)
- [ ] Risk disclosure documentation complete
- [ ] Client agreements in place (if applicable)
- [ ] Terms of service reviewed by legal

---

## 10. Final Sign-Off

### 10.1 Technical Approval
- [ ] Technical lead approval
- [ ] Senior developer code review approval
- [ ] QA testing approval
- [ ] Security review approval

**Technical Lead Signature:**
```
Name: _______________________________
Date: _______________________________
```

### 10.2 Business Approval
- [ ] Business owner approval
- [ ] Risk manager approval
- [ ] Compliance officer approval (if applicable)

**Business Owner Signature:**
```
Name: _______________________________
Date: _______________________________
```

### 10.3 Production Deployment Authorization
- [ ] All checklist items completed
- [ ] All approvals obtained
- [ ] Deployment date scheduled
- [ ] Rollback plan documented
- [ ] Communication plan executed (notify stakeholders)

**Deployment Authorized By:**
```
Name: _______________________________
Role: _______________________________
Date: _______________________________
```

---

## 11. Post-Deployment

### 11.1 Initial Monitoring (First 48 Hours)
- [ ] Monitor logs continuously for first 24 hours
- [ ] Verify trades executing correctly
- [ ] Verify positions reconcile with broker
- [ ] Verify alerts functioning
- [ ] Verify backups completing
- [ ] No critical errors detected

### 11.2 Gradual Ramp-Up
- [ ] Week 1-2: Small position sizes (1% per position)
- [ ] Week 3-4: Medium position sizes (3% per position)
- [ ] Week 5+: Target position sizes (5-10% per position)
- [ ] Risk limits gradually increased
- [ ] Performance monitored continuously

### 11.3 Ongoing Validation
- [ ] Daily: Review logs, P&L, positions
- [ ] Weekly: Review performance metrics, backup status
- [ ] Monthly: Rotate API keys, review security
- [ ] Quarterly: Test disaster recovery, security audit

---

## Checklist Summary

**Total Items**: 150+
**Completed**: _____ / _____
**Percentage**: _____%

**Status**: ⬜ Not Ready for Production | ⬜ Ready for Production

**Notes:**
```
[Add any notes, exceptions, or special considerations here]
```

---

## Emergency Contacts

**Technical Lead:**
- Name: _______________________________
- Phone: _______________________________
- Email: _______________________________

**On-Call Engineer:**
- Name: _______________________________
- Phone: _______________________________
- Email: _______________________________

**Business Owner:**
- Name: _______________________________
- Phone: _______________________________
- Email: _______________________________

---

**Last Reviewed**: _______________________________
**Next Review Date**: _______________________________

---

**IMPORTANT**: This checklist is a living document. Update it as requirements change or new items are identified during deployment.
