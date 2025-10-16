# CI/CD Pipeline Documentation

## Overview

RustyBT uses a comprehensive CI/CD pipeline built on GitHub Actions to ensure code quality, security, and reliability. The pipeline consists of 6 automated workflows that run on every push and pull request, with additional scheduled checks for dependency security.

**Performance Target:** < 12 minutes total execution time for typical PRs (workflows run in parallel)

## Workflows

### 1. Code Quality (`code-quality.yml`)

**Purpose:** Enforce code style, formatting, type safety, and complexity standards.

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches
- Only runs when Python files or configuration changes

**Checks (All BLOCKING):**
- **Ruff linting:** Fast Python linter (replaces flake8, isort, pyupgrade)
  - Configuration: `pyproject.toml` → `[tool.ruff]`
  - Exit code 0 required to pass
- **Black formatting:** Code formatter with line length 100
  - Configuration: `pyproject.toml` → `[tool.black]`
  - Must show "0 files would be reformatted"
- **Mypy type checking (BLOCKING):** Static type checker (strict mode for new code)
  - Configuration: `pyproject.toml` → `[tool.mypy]`
  - Must pass for merge approval
- **Complexity check:** McCabe cyclomatic complexity ≤10
  - Script: `scripts/check_complexity.py`
  - Fails if any function exceeds threshold

**Estimated Duration:** ~2 minutes

**Common Failures:**
- Linting errors: Run `ruff check . --fix` locally to auto-fix
- Formatting: Run `black .` locally to reformat
- Complexity: Refactor functions to reduce cyclomatic complexity

### 2. Zero-Mock Enforcement (`zero-mock-enforcement.yml`)

**Purpose:** Ensure no mock/stub implementations, hardcoded values, or fake validations.

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches
- Only runs when Python files in `rustybt/` or detection scripts change

**Checks (All BLOCKING):**
- **Mock pattern detection:** Scans for mock/fake/stub patterns
  - Script: `scripts/detect_mocks.py --strict`
  - Forbidden patterns: `mock`, `fake`, `stub`, `dummy` in names
- **Hardcoded values:** Detects hardcoded return values
  - Script: `scripts/detect_hardcoded_values.py --fail-on-found`
  - Forbidden: `return 10`, `return 1.0`, `return True` (constants)
- **Validation verification:** Ensures validators reject invalid data
  - Script: `scripts/verify_validations.py --ensure-real-checks`
  - All `validate_*` functions must perform real checks
- **Unique results test:** Different inputs must produce different outputs
  - Script: `scripts/test_unique_results.py`
  - Ensures calculations aren't returning mocked values

**Estimated Duration:** ~1-2 minutes

**Common Failures:**
- Mock patterns: Remove mock implementations, write real code
- Hardcoded values: Replace with actual calculations
- Validation failures: Implement real validation logic

### 3. Security (`security.yml`)

**Purpose:** Detect security vulnerabilities, secrets, and unsafe code patterns.

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Checks:**
- **Bandit SAST (BLOCKING):** Static application security testing
  - Scans `rustybt/` directory for security issues
  - High/Medium severity issues cause failure
  - Configuration: Default + ignore INFO level
- **TruffleHog (BLOCKING):** Secrets detection via git history
  - Scans commits for API keys, passwords, tokens
  - Full git history scan (fetch-depth: 0)
  - Will fail build if secrets detected
- **Detect-secrets (BLOCKING):** Secrets detection via static analysis
  - Baseline file: `.secrets.baseline`
  - Updates baseline if not present

**Estimated Duration:** ~3 minutes

**Common Failures:**
- Bandit issues: Fix security vulnerabilities in code
- Secrets detected: Remove secrets, use environment variables
- Baseline update: Review and commit `.secrets.baseline`

### 4. Testing (`testing.yml`)

**Purpose:** Run unit tests and property-based tests with coverage enforcement.

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches
- Only runs when Python files or configuration changes

**Jobs:**

**a) Unit Tests & Coverage (BLOCKING):**
- Runs: `pytest` with coverage measurement
- Excludes: Memory, API integration, live trading, IB integration tests
- Coverage targets (module-specific):
  - Financial modules (`rustybt.finance`): ≥95%
  - Core modules (`rustybt.core`): ≥90%
  - Other modules: ≥90%
- Enforced by: `scripts/check_coverage_thresholds.py`
- Outputs: HTML coverage report, XML for Codecov
- Matrix: Python 3.12 (expandable to 3.13+)

**b) Property-Based Tests (BLOCKING):**
- Runs: `pytest -m property` with Hypothesis
- Profile: `ci` (1000+ examples per test)
- Ensures mathematical properties hold across inputs

**Estimated Duration:** ~5-8 minutes (longest job)

**Common Failures:**
- Test failures: Fix bugs in code
- Coverage below threshold: Add tests or fix coverage exclusions
- Property tests: Fix edge cases or relax property constraints

### 5. Dependency Security (`dependency-security.yml`)

**Purpose:** Weekly scan for vulnerable dependencies and license compliance.

**Triggers:**
- Scheduled: Mondays at 2 AM UTC (`cron: '0 2 * * 1'`)
- Manual: `workflow_dispatch` event

**Checks:**
- **Safety scan (Non-blocking):** Python vulnerability database
  - Output: `safety-report.json`
  - Creates issue if vulnerabilities found
- **Pip-audit (Non-blocking):** PyPI advisories scan
  - Output: `pip-audit-report.json`
  - Creates issue if vulnerabilities found
- **License check (BLOCKING):** Ensures no GPL dependencies
  - Script: `scripts/check_licenses.py`
  - Acceptable: Apache 2.0, MIT, BSD, ISC, LGPL
  - Forbidden: GPL, AGPL, Commercial

**Estimated Duration:** ~4 minutes

**Common Failures:**
- Vulnerabilities: Update packages to patched versions
- License violations: Replace with Apache 2.0/MIT alternatives

### 6. Performance Regression (`performance.yml`)

**Purpose:** Detect performance regressions on main branch after merge.

**Triggers:**
- Push to `main` branch only
- Manual: `workflow_dispatch` event

**Checks:**
- Runs: Pytest benchmarks with `--benchmark-only`
- Baseline: `benchmark-baseline.json` (committed)
- Threshold: 20% degradation triggers issue
- Output: `benchmark-results.json` uploaded as artifact
- Non-blocking: Creates issue but doesn't fail build

**Estimated Duration:** ~5-10 minutes

**Common Failures:**
- Regressions: Optimize code or update baseline if intentional

## Branch Protection Rules

**Main Branch Protection (Required):**

Configuration: GitHub Repository Settings → Branches → Branch protection rules

Required status checks before merging:
- `code-quality / Code Quality Checks`
- `zero-mock-enforcement / zero-mock-enforcement`
- `security / Security Checks`
- `test / Unit Tests & Coverage (3.12)`
- `property-tests / Property-Based Tests`

Additional requirements:
- ✅ Require branches to be up to date before merging
- ✅ Require pull request reviews (1 approval minimum)
- ✅ Dismiss stale reviews on new commits
- ✅ Require review from code owners (if CODEOWNERS file present)

## CI Performance Optimization

### Caching Strategy

All workflows use `actions/cache@v3` to cache `uv` dependencies:

```yaml
- name: Cache uv dependencies
  uses: actions/cache@v3
  with:
    path: |
      ~/.cache/uv
      ~/.local/share/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('**/pyproject.toml') }}
    restore-keys: |
      ${{ runner.os }}-uv-
```

**Cache Hit Rate:** ~90% (cache invalidated only when `pyproject.toml` changes)

**Time Savings:** ~2-3 minutes per workflow run

### Parallel Execution

Workflows 1-4 run in parallel on every PR:
- Code Quality: ~2 min
- Zero-Mock Enforcement: ~1-2 min
- Security: ~3 min
- Testing: ~5-8 min (bottleneck)

**Total parallel time:** ~8 minutes (limited by longest job: Testing)

### Path Filtering

Workflows use `paths:` filters to skip unnecessary runs:
- Only run when relevant files change (`.py` files, configs)
- Reduces CI load by ~30%

## Debugging CI Failures

### Local Testing with `act`

Install `act` (GitHub Actions local runner):
```bash
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

Run workflows locally:
```bash
# Test code quality workflow
act -j code-quality

# Test zero-mock enforcement
act -j zero-mock-enforcement

# Test security workflow
act -j security

# Test testing workflow (requires test data)
act -j test
```

### Common Issues & Solutions

#### 1. Code Quality Failures

**Issue:** Ruff linting errors
```
Solution:
ruff check . --fix    # Auto-fix issues
ruff check .          # Verify fixes
```

**Issue:** Black formatting errors
```
Solution:
black .               # Format all files
black --check .       # Verify formatting
```

**Issue:** Complexity violations
```
Solution:
python scripts/check_complexity.py --max-complexity 10
# Refactor functions exceeding threshold
```

#### 2. Zero-Mock Enforcement Failures

**Issue:** Mock patterns detected
```
Solution:
python scripts/detect_mocks.py --strict
# Remove mock implementations, write real code
```

**Issue:** Hardcoded values detected
```
Solution:
python scripts/detect_hardcoded_values.py --fail-on-found
# Replace hardcoded returns with calculations
```

#### 3. Security Failures

**Issue:** Bandit finds security issues
```
Solution:
bandit -r rustybt -ll
# Fix security vulnerabilities
# Or add # nosec comment if false positive (with justification)
```

**Issue:** Secrets detected
```
Solution:
# Remove secrets from code
# Use environment variables instead
# Update .secrets.baseline if false positive
detect-secrets scan --baseline .secrets.baseline
```

#### 4. Test Failures

**Issue:** Tests fail locally
```
Solution:
pytest -v                        # Run all tests
pytest -v -k test_name           # Run specific test
pytest -v --lf                   # Run last failed tests
```

**Issue:** Coverage below threshold
```
Solution:
pytest --cov=rustybt --cov-report=html
# Open htmlcov/index.html to see uncovered lines
# Add tests for uncovered code
```

#### 5. Dependency Security Issues

**Issue:** Vulnerabilities found
```
Solution:
safety scan                      # Check vulnerabilities
pip-audit                        # Check PyPI advisories
# Update vulnerable packages
uv pip install --upgrade <package>
```

**Issue:** License violations
```
Solution:
python scripts/check_licenses.py --verbose
# Replace GPL packages with Apache 2.0/MIT alternatives
```

## CI/CD Best Practices

### Before Pushing

1. **Run checks locally:**
   ```bash
   # Code quality
   ruff check .
   black .
   mypy rustybt

   # Zero-mock
   python scripts/detect_mocks.py --strict
   python scripts/detect_hardcoded_values.py --fail-on-found

   # Tests
   pytest -v --cov=rustybt
   ```

2. **Verify no secrets:**
   ```bash
   detect-secrets scan
   ```

3. **Check complexity:**
   ```bash
   python scripts/check_complexity.py
   ```

### Pull Request Workflow

1. Create feature branch from `develop`
2. Make changes and commit
3. Push to origin
4. Create PR (template auto-populates)
5. Wait for CI checks (8-10 minutes)
6. Address any failures
7. Request review (1 approval required)
8. Merge after approval + passing CI

### Merge Strategy

- **Squash and merge:** For feature branches (default)
- **Merge commit:** For epic branches
- **Rebase and merge:** For small fixes

## Monitoring & Alerts

### GitHub Actions Dashboard

View workflow status: `https://github.com/{org}/{repo}/actions`

### Notifications

- Email: Sent to commit author on workflow failure
- Slack: (Optional) Configure webhook for real-time alerts
- Issues: Auto-created for dependency/performance issues

### Metrics

Track CI performance in GitHub Insights:
- Average workflow duration
- Success rate
- Cache hit rate

## Troubleshooting

### Workflow Won't Trigger

**Check:**
1. Path filters match changed files
2. Branch is in triggers list
3. Workflow file is valid YAML (`yamllint .github/workflows/*.yml`)

### Caching Not Working

**Check:**
1. Cache key matches pattern
2. `pyproject.toml` hasn't changed
3. Cache size < 10GB (GitHub limit)

### Slow CI Runs

**Check:**
1. Cache hit rate (should be ~90%)
2. Parallel jobs running
3. No matrix expansion issues

## Maintenance

### Weekly Tasks

- Review dependency security issues
- Check cache hit rates
- Monitor CI execution times

### Monthly Tasks

- Update GitHub Actions versions
- Review and update baseline benchmarks
- Audit branch protection rules

### Quarterly Tasks

- Review and update required checks
- Optimize slow workflows
- Update CI documentation

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [uv Documentation](https://github.com/astral-sh/uv)
- [pytest Documentation](https://docs.pytest.org/)
- [Ruff Documentation](https://github.com/astral-sh/ruff)
- [Bandit Documentation](https://bandit.readthedocs.io/)

---

**Last Updated:** 2025-10-13
**Story:** X2.5 - P1 CI/CD Pipeline
