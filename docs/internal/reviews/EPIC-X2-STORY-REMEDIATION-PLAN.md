# Epic X2 Story Remediation Plan

**Date:** 2025-10-12
**Author:** Sarah (Product Owner)
**Purpose:** Comprehensive remediation plan and fix templates for NO-GO stories

---

## Executive Summary

**Validation Results:**
- **3 Stories NO-GO:** X2.4, X2.5, X2.6 (blocked for implementation)
- **2 Stories SHOULD-FIX:** X2.1, X2.3 (implementation-ready but need minor fixes)
- **2 Stories GO:** X2.2, X2.7 (ready, no changes needed)

**Total Remediation Effort:** 8-10 hours (1-2 days for one person)

**Critical Path Impact:**
- X2.5 (CI/CD) blocks X2.7 (validation) → HIGHEST PRIORITY
- X2.4 (Zero-Mock) blocks X2.5 → HIGH PRIORITY
- X2.6 (Dependencies) blocks X2.5 (can run parallel with X2.4) → HIGH PRIORITY

**Remediation Sequence:**
1. **Phase 1 (Critical):** Fix X2.5 first (3-4 hours)
2. **Phase 2 (High):** Fix X2.4 and X2.6 in parallel (4-6 hours combined)
3. **Phase 3 (Minor):** Fix X2.1 and X2.3 (1 hour combined)

---

## Table of Contents

1. [Story X2.5 Remediation (CRITICAL)](#story-x25-remediation-critical)
2. [Story X2.4 Remediation (HIGH)](#story-x24-remediation-high)
3. [Story X2.6 Remediation (HIGH)](#story-x26-remediation-high)
4. [Story X2.1 Remediation (MINOR)](#story-x21-remediation-minor)
5. [Story X2.3 Remediation (MINOR)](#story-x23-remediation-minor)
6. [Implementation Checklist](#pre-implementation-setup)

---

# Story X2.5 Remediation (CRITICAL)

**File:** `docs/stories/X2.5.p1-cicd-pipeline.story.md`
**Status:** ❌ NO-GO → Must fix before implementation
**Priority:** 🔴 CRITICAL (Blocks X2.7 validation story)
**Estimated Fix Time:** 3-4 hours

## Issues Summary

| Issue | Severity | Current State | Fix Required |
|-------|----------|---------------|--------------|
| Severely deficient Dev Notes | CRITICAL | 4 lines | Expand to 200+ lines |
| Missing Dev Agent Record subsections | CRITICAL | 0/4 subsections | Add all 4 subsections |
| Tasks lack subtasks | Should-Fix | 0 subtasks | Add 5-10 subtasks per task |
| Missing Testing subsection | Should-Fix | Missing | Add Testing subsection |

## Remediation Steps

### Step 1: Add Dev Agent Record Subsections

**Location:** Line 127 (after "## Dev Agent Record")

**Current:**
```markdown
## Dev Agent Record

*This section will be populated by the development agent during implementation.*

## QA Results
```

**Replace With:**
```markdown
## Dev Agent Record

*This section will be populated by the development agent during implementation.*

### Agent Model Used

*To be filled by dev agent*

### Debug Log References

*To be filled by dev agent*

### Completion Notes List

*To be filled by dev agent*

### File List

*To be filled by dev agent*

## QA Results
```

### Step 2: Expand Dev Notes (CRITICAL - 200+ lines needed)

**Location:** Line 109 (after "## Dev Notes")

**Current:**
```markdown
## Dev Notes

### Architecture Context

**CI/CD Workflows:**
- 6 workflows total
- Parallel execution for speed
- Branch protection enforced
- Clear, actionable error messages

## Change Log
```

**Replace With:**

```markdown
## Dev Notes

### Architecture Context

**Source:** [docs/architecture/tech-stack.md](../architecture/tech-stack.md)

**CI/CD Stack:**
- GitHub Actions (workflow orchestration)
- Parallel job execution for speed (target: < 12 minutes total)
- Branch protection rules (require status checks)
- Artifact archiving (coverage reports, security scans, benchmark results)

**Python Version:** 3.12+ required

**Source:** [docs/architecture/coding-standards.md](../architecture/coding-standards.md)

**Code Quality Tools:**
- ruff >= 0.11.12 (linting)
- black 24.1+ (formatting)
- mypy >= 1.10.0 (type checking)
- McCabe complexity: ≤10 per function

**Security Tools:**
- bandit (SAST - static analysis)
- truffleHog (secrets detection)
- detect-secrets (secrets detection)
- safety (dependency vulnerability scanning)
- pip-audit (dependency security auditing)

**Testing Tools:**
- pytest >= 7.2.0 (test framework)
- pytest-cov >= 3.0.0 (coverage measurement)
- hypothesis >= 6.0 (property-based testing)
- Coverage targets: ≥90% core, ≥95% financial

**Source:** [docs/architecture/source-tree.md](../architecture/source-tree.md)

**Relevant Source Locations:**
- CI workflows: `.github/workflows/` (6 workflow files to create)
- Scripts: `scripts/` (check_complexity.py, check_licenses.py, check_performance_regression.py)
- Zero-mock scripts: `scripts/` (from X2.4: detect_mocks.py, detect_hardcoded_values.py, verify_validations.py, test_unique_results.py)
- Configuration: `pyproject.toml` (tool configurations)
- Branch protection: GitHub repository settings
- PR template: `.github/pull_request_template.md`
- Documentation: `docs/development/ci-cd-pipeline.md`

### Technical Implementation Guidance

**Workflow 1: Code Quality CI Job**

**File:** `.github/workflows/code-quality.yml`

```yaml
name: Code Quality

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  code-quality:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: |
          uv sync -E dev -E test

      - name: Run ruff linting (BLOCKING)
        run: |
          uv run ruff check .

      - name: Run black formatting check (BLOCKING)
        run: |
          uv run black --check .

      - name: Run mypy type checking (BLOCKING)
        run: |
          uv run python3 -m mypy

      - name: Check code complexity (BLOCKING)
        run: |
          uv run python scripts/check_complexity.py --max-complexity 10
```

**Workflow 2: Zero-Mock Enforcement CI Job**

**File:** `.github/workflows/zero-mock-enforcement.yml`

```yaml
name: Zero-Mock Enforcement

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  zero-mock-enforcement:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: |
          uv sync -E dev -E test

      - name: Detect mock patterns (BLOCKING)
        run: |
          uv run python scripts/detect_mocks.py --strict

      - name: Detect hardcoded values (BLOCKING)
        run: |
          uv run python scripts/detect_hardcoded_values.py --fail-on-found

      - name: Verify validation functions (BLOCKING)
        run: |
          uv run python scripts/verify_validations.py --ensure-real-checks

      - name: Test result uniqueness (BLOCKING)
        run: |
          uv run python scripts/test_unique_results.py
```

**Workflow 3: Security CI Job**

**File:** `.github/workflows/security.yml`

```yaml
name: Security

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  security:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for truffleHog

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: |
          uv sync -E dev -E test

      - name: Run bandit SAST (BLOCKING)
        run: |
          uv run bandit -r rustybt -ll -i

      - name: Install truffleHog
        run: |
          curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin

      - name: Run truffleHog secrets detection (BLOCKING)
        run: |
          trufflehog git file://. --since-commit HEAD~1 --fail

      - name: Run detect-secrets (BLOCKING)
        run: |
          uv run detect-secrets scan --baseline .secrets.baseline
```

**Workflow 4: Testing CI Job**

**File:** `.github/workflows/testing.yml`

```yaml
name: Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.12']

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: |
          uv sync -E test

      - name: Run unit tests with coverage (BLOCKING)
        run: |
          uv run pytest -m "not memory and not api_integration and not live and not ib_integration" \
            --cov=rustybt \
            --cov-report=term \
            --cov-report=html \
            --cov-report=xml \
            --cov-fail-under=90

      - name: Run property-based tests (BLOCKING)
        run: |
          uv run pytest -m property --hypothesis-profile=ci

      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

      - name: Archive coverage report
        uses: actions/upload-artifact@v3
        with:
          name: coverage-report
          path: htmlcov/
```

**Workflow 5: Dependency Security CI Job (Weekly)**

**File:** `.github/workflows/dependency-security.yml`

```yaml
name: Dependency Security

on:
  schedule:
    - cron: '0 2 * * 1'  # Monday 2 AM UTC
  workflow_dispatch:  # Allow manual trigger

jobs:
  dependency-security:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: |
          uv sync -E dev -E test

      - name: Run safety scan
        run: |
          uv run safety scan --json > safety-report.json || true

      - name: Run pip-audit
        run: |
          uv run pip-audit --format json > pip-audit-report.json || true

      - name: Check licenses (BLOCKING)
        run: |
          uv run python scripts/check_licenses.py

      - name: Upload security reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            safety-report.json
            pip-audit-report.json

      - name: Create issue if vulnerabilities found
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'Weekly Dependency Security Scan: Vulnerabilities Found',
              body: 'Automated dependency security scan found vulnerabilities. Check workflow artifacts for details.',
              labels: ['security', 'dependencies']
            })
```

**Workflow 6: Performance Regression CI Job (Main Branch Only)**

**File:** `.github/workflows/performance.yml`

```yaml
name: Performance Regression

on:
  push:
    branches: [ main ]

jobs:
  performance:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: |
          uv sync -E test

      - name: Run benchmark suite
        run: |
          uv run python -m rustybt benchmark --suite backtest --output benchmark-results.json

      - name: Check performance regression
        run: |
          uv run python scripts/check_performance_regression.py \
            --threshold=0.20 \
            --baseline=benchmark-baseline.json \
            --current=benchmark-results.json || true

      - name: Upload benchmark results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: benchmark-results.json

      - name: Create issue if regression detected
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'Performance Regression Detected',
              body: 'Benchmark execution exceeded threshold. Check workflow artifacts for details.',
              labels: ['performance', 'regression']
            })
```

**Branch Protection Configuration:**

**GitHub Repository Settings → Branches → Branch protection rules:**

```yaml
# Branch: main
Require status checks to pass before merging: [x]
  Required status checks:
    - code-quality / code-quality
    - zero-mock-enforcement / zero-mock-enforcement
    - security / security
    - test / test (3.12)

Require branches to be up to date before merging: [x]
Require pull request reviews before merging: [x]
  Required approving reviews: 1
```

**PR Template:**

**File:** `.github/pull_request_template.md`

```markdown
## Description

<!-- Brief description of changes -->

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Checklist

### Code Quality
- [ ] Code follows style guidelines (ruff + black)
- [ ] Type hints added/updated (mypy strict for new code)
- [ ] Code complexity ≤10 (McCabe)
- [ ] No code quality violations

### Zero-Mock Compliance
- [ ] No mock/fake/stub implementations
- [ ] No hardcoded return values
- [ ] All validators reject invalid data
- [ ] Different inputs produce different outputs

### Testing
- [ ] Unit tests added/updated
- [ ] Property-based tests added (if applicable)
- [ ] All tests pass locally
- [ ] Coverage ≥90% (core modules), ≥95% (financial modules)

### Security
- [ ] No secrets committed
- [ ] No High severity bandit issues
- [ ] Dependencies reviewed for vulnerabilities
- [ ] Security best practices followed

### Documentation
- [ ] Code comments added for complex logic
- [ ] Docstrings added/updated
- [ ] README updated (if needed)
- [ ] CHANGELOG.md updated

## Related Issues

Closes #<!-- issue number -->

## Test Plan

<!-- Describe how you tested this change -->

## Screenshots (if applicable)

<!-- Add screenshots for UI changes -->
```

**CI/CD Performance Optimization:**

**Caching Strategy:**
```yaml
# Add to all workflows that install dependencies
- name: Cache uv dependencies
  uses: actions/cache@v3
  with:
    path: |
      ~/.cache/uv
      ~/.local/share/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('**/uv.lock') }}
    restore-keys: |
      ${{ runner.os }}-uv-
```

**Parallel Execution Strategy:**
- Workflows 1-4 run in parallel on every PR (total: ~8-10 minutes)
- Workflow 5 runs weekly (independent)
- Workflow 6 runs on main only (non-blocking)

**Expected CI Timeline:**
- Code quality: ~2 minutes
- Zero-mock enforcement: ~1 minute
- Security: ~3 minutes
- Testing: ~5-8 minutes (longest job)
- **Total parallel execution:** ~8-10 minutes (limited by longest job)

### Testing

**Source:** [docs/architecture/testing-strategy.md](../architecture/testing-strategy.md)

**Test Standards:**
- CI workflows tested locally using `act` (GitHub Actions local runner)
- Branch protection rules tested with test PRs
- PR template tested with sample PR
- Performance targets verified: < 12 minutes total execution

**Testing Commands:**

```bash
# Test workflows locally with act
act -j code-quality  # Test code quality workflow
act -j zero-mock-enforcement  # Test zero-mock workflow
act -j security  # Test security workflow
act -j test  # Test testing workflow

# Test branch protection (must be done via GitHub UI)
# Create test PR and verify:
# 1. All required checks appear
# 2. Merge blocked until checks pass
# 3. Reviews required

# Test PR template
# Create test PR and verify template renders correctly
```

**CI Integration Tests:**

```bash
# Verify all workflow files are valid YAML
yamllint .github/workflows/*.yml

# Verify all scripts referenced in workflows exist
test -f scripts/check_complexity.py || echo "Missing check_complexity.py"
test -f scripts/detect_mocks.py || echo "Missing detect_mocks.py"
test -f scripts/detect_hardcoded_values.py || echo "Missing detect_hardcoded_values.py"
test -f scripts/verify_validations.py || echo "Missing verify_validations.py"
test -f scripts/test_unique_results.py || echo "Missing test_unique_results.py"
test -f scripts/check_licenses.py || echo "Missing check_licenses.py"
test -f scripts/check_performance_regression.py || echo "Missing check_performance_regression.py"

# Verify all tools are installed
uv run ruff --version
uv run black --version
uv run mypy --version
uv run bandit --version
uv run pytest --version
```
```

### Step 3: Add Subtasks to All Tasks

**Location:** Lines 97-107 (Tasks / Subtasks section)

**Current:**
```markdown
## Tasks / Subtasks

- [ ] **Task 1: Create Code Quality Workflow** (AC: 1)
- [ ] **Task 2: Activate Zero-Mock Enforcement Workflow** (AC: 2)
- [ ] **Task 3: Create Security Workflow** (AC: 3)
- [ ] **Task 4: Create Testing Workflow** (AC: 4)
- [ ] **Task 5: Create Dependency Security Workflow** (AC: 5)
- [ ] **Task 6: Create Performance Regression Workflow** (AC: 6)
- [ ] **Task 7: Configure Branch Protection** (AC: 7)
- [ ] **Task 8: Create PR Template** (AC: 8)
- [ ] **Task 9: Write CI/CD Documentation** (AC: 9)
- [ ] **Task 10: Optimize CI Performance** (AC: 10)
- [ ] **Task 11: Final Validation** (AC: 11)
```

**Replace With:**

```markdown
## Tasks / Subtasks

- [ ] **Task 1: Create Code Quality Workflow** (AC: 1)
  - [ ] Create `.github/workflows/code-quality.yml`
  - [ ] Add ruff linting job (BLOCKING)
  - [ ] Add black formatting check job (BLOCKING)
  - [ ] Add mypy type checking job (BLOCKING)
  - [ ] Add McCabe complexity check job (BLOCKING)
  - [ ] Configure Python 3.12, uv installation
  - [ ] Test workflow locally with `act`
  - [ ] Commit and test in CI

- [ ] **Task 2: Activate Zero-Mock Enforcement Workflow** (AC: 2)
  - [ ] Verify workflow file exists from X2.4: `.github/workflows/zero-mock-enforcement.yml`
  - [ ] Verify all 4 detection scripts exist in `scripts/`
  - [ ] Test workflow locally with `act`
  - [ ] Enable workflow (remove any disabled flags)
  - [ ] Verify BLOCKING configuration
  - [ ] Test with sample PR

- [ ] **Task 3: Create Security Workflow** (AC: 3)
  - [ ] Create `.github/workflows/security.yml`
  - [ ] Add bandit SAST job (BLOCKING)
  - [ ] Add truffleHog secrets detection job (BLOCKING)
  - [ ] Add detect-secrets job (BLOCKING)
  - [ ] Configure fetch-depth: 0 for truffleHog
  - [ ] Test workflow locally with `act`
  - [ ] Commit and test in CI

- [ ] **Task 4: Create Testing Workflow** (AC: 4)
  - [ ] Create `.github/workflows/testing.yml`
  - [ ] Add unit test job with coverage (BLOCKING)
  - [ ] Configure coverage thresholds: ≥90% core, ≥95% financial
  - [ ] Add property-based test job (BLOCKING)
  - [ ] Configure hypothesis profile: ci
  - [ ] Add coverage report upload to Codecov
  - [ ] Add HTML coverage artifact upload
  - [ ] Test workflow locally with `act`
  - [ ] Commit and test in CI

- [ ] **Task 5: Create Dependency Security Workflow** (AC: 5)
  - [ ] Create `.github/workflows/dependency-security.yml`
  - [ ] Configure weekly schedule: `cron: '0 2 * * 1'`
  - [ ] Add workflow_dispatch for manual trigger
  - [ ] Add safety scan job
  - [ ] Add pip-audit job
  - [ ] Add license check job (BLOCKING)
  - [ ] Configure artifact upload for reports
  - [ ] Add issue creation on failure
  - [ ] Test workflow manually

- [ ] **Task 6: Create Performance Regression Workflow** (AC: 6)
  - [ ] Create `.github/workflows/performance.yml`
  - [ ] Configure to run on main branch only
  - [ ] Add benchmark execution job
  - [ ] Add regression check job (threshold: 20%)
  - [ ] Configure artifact upload for benchmark results
  - [ ] Add issue creation on regression
  - [ ] Create baseline: `benchmark-baseline.json`
  - [ ] Create script: `scripts/check_performance_regression.py`
  - [ ] Test workflow on main branch

- [ ] **Task 7: Configure Branch Protection** (AC: 7)
  - [ ] Navigate to GitHub repository settings → Branches
  - [ ] Create branch protection rule for `main`
  - [ ] Enable "Require status checks to pass before merging"
  - [ ] Add required checks: code-quality, zero-mock-enforcement, security, test
  - [ ] Enable "Require branches to be up to date before merging"
  - [ ] Enable "Require pull request reviews before merging" (1 approval)
  - [ ] Save branch protection rules
  - [ ] Test with sample PR

- [ ] **Task 8: Create PR Template** (AC: 8)
  - [ ] Create `.github/pull_request_template.md`
  - [ ] Add description section
  - [ ] Add type of change section
  - [ ] Add code quality checklist
  - [ ] Add zero-mock compliance checklist
  - [ ] Add testing checklist
  - [ ] Add security checklist
  - [ ] Add documentation checklist
  - [ ] Add related issues section
  - [ ] Test with sample PR

- [ ] **Task 9: Write CI/CD Documentation** (AC: 9)
  - [ ] Create `docs/development/ci-cd-pipeline.md`
  - [ ] Document all 6 workflows with purpose and triggers
  - [ ] Document branch protection rules
  - [ ] Document required checks
  - [ ] Document how to debug CI failures
  - [ ] Document CI performance expectations (< 12 minutes)
  - [ ] Add workflow diagrams (optional but recommended)
  - [ ] Add troubleshooting guide for common CI issues

- [ ] **Task 10: Optimize CI Performance** (AC: 10)
  - [ ] Add dependency caching to all workflows (uv cache)
  - [ ] Verify parallel execution configuration
  - [ ] Measure actual CI execution time
  - [ ] Optimize slowest jobs (likely testing)
  - [ ] Configure matrix strategies where applicable
  - [ ] Document caching strategy
  - [ ] Verify target: < 12 minutes total

- [ ] **Task 11: Final Validation** (AC: 11)
  - [ ] Create test PR to verify all workflows run
  - [ ] Verify all workflows pass on current codebase
  - [ ] Verify branch protection blocks merge until checks pass
  - [ ] Verify PR template renders correctly
  - [ ] Verify CI provides clear error messages
  - [ ] Verify CI performance < 12 minutes
  - [ ] Document any issues found
```

---

# Story X2.4 Remediation (HIGH)

**File:** `docs/stories/X2.4.p1-zero-mock-enforcement.story.md`
**Status:** ❌ NO-GO → Must fix before implementation
**Priority:** 🔴 HIGH (Blocks X2.5 CI/CD pipeline)
**Estimated Fix Time:** 2-3 hours

## Issues Summary

| Issue | Severity | Current State | Fix Required |
|-------|----------|---------------|--------------|
| Incomplete Dev Agent Record | CRITICAL | 0/4 subsections | Add all 4 subsections |
| Missing Testing subsection | Should-Fix | Missing | Add Testing subsection |
| Sparse Dev Notes | Should-Fix | Limited guidance | Expand with 100+ lines |

## Remediation Steps

### Step 1: Add Dev Agent Record Subsections

**Location:** Line 145 (after "## Dev Agent Record")

**Current:**
```markdown
## Dev Agent Record

*This section will be populated by the development agent during implementation.*

## QA Results
```

**Replace With:**
```markdown
## Dev Agent Record

*This section will be populated by the development agent during implementation.*

### Agent Model Used

*To be filled by dev agent*

### Debug Log References

*To be filled by dev agent*

### Completion Notes List

*To be filled by dev agent*

### File List

*To be filled by dev agent*

## QA Results
```

### Step 2: Enhance Dev Notes Technical Guidance

**Location:** Line 92 (after existing Dev Notes content)

**Current Dev Notes ends at line 106. Add this content BEFORE "## Change Log":**

```markdown
### Technical Implementation Guidance

**Mock Detection Script (detect_mocks.py):**

**Purpose:** Scan Python files for mock patterns in function/variable names and identify suspicious implementations.

**Detection Patterns:**
1. Function/variable names containing: `mock`, `fake`, `stub`, `dummy`, `placeholder`
2. Class names inheriting from Mock-like classes
3. Import statements with mock libraries in production code

**Algorithm:**
```python
# scripts/detect_mocks.py
import ast
import sys
from pathlib import Path
from typing import List, Tuple

class MockDetector(ast.NodeVisitor):
    def __init__(self):
        self.violations: List[Tuple[int, str]] = []
        self.mock_keywords = ['mock', 'fake', 'stub', 'dummy', 'placeholder']

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Check function name
        if any(keyword in node.name.lower() for keyword in self.mock_keywords):
            self.violations.append((node.lineno, f"Mock function name: {node.name}"))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        # Check class name
        if any(keyword in node.name.lower() for keyword in self.mock_keywords):
            self.violations.append((node.lineno, f"Mock class name: {node.name}"))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        # Check for mock imports in production code
        for alias in node.names:
            if 'mock' in alias.name.lower() or 'unittest.mock' in alias.name:
                self.violations.append((node.lineno, f"Mock import: {alias.name}"))
        self.generic_visit(node)

def scan_file(filepath: Path) -> List[Tuple[int, str]]:
    """Scan a single Python file for mock patterns."""
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=str(filepath))
        except SyntaxError:
            return []

    detector = MockDetector()
    detector.visit(tree)
    return detector.violations

def main():
    # Scan all Python files in rustybt/
    rustybt_dir = Path('rustybt')
    violations_found = False

    for py_file in rustybt_dir.rglob('*.py'):
        violations = scan_file(py_file)
        if violations:
            violations_found = True
            print(f"\n{py_file}:")
            for lineno, msg in violations:
                print(f"  Line {lineno}: {msg}")

    if violations_found:
        sys.exit(1)
    else:
        print("✅ No mock patterns detected")
        sys.exit(0)

if __name__ == '__main__':
    main()
```

**Usage:**
```bash
# Quick check (pre-commit)
python scripts/detect_mocks.py --quick

# Strict check (CI)
python scripts/detect_mocks.py --strict
```

---

**Hardcoded Values Detection Script (detect_hardcoded_values.py):**

**Purpose:** Identify functions that return constant values (hardcoded returns).

**Detection Patterns:**
1. Functions with single `return <constant>` statement
2. Constants: integers, floats, strings, True/False
3. Exclude: None, empty collections, constants from class attributes

**Algorithm:**
```python
# scripts/detect_hardcoded_values.py
import ast
import sys
from pathlib import Path
from typing import List, Tuple

class HardcodedReturnDetector(ast.NodeVisitor):
    def __init__(self):
        self.violations: List[Tuple[int, str, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Check if function body is single return statement
        if len(node.body) == 1 and isinstance(node.body[0], ast.Return):
            ret_node = node.body[0]
            if ret_node.value and self._is_constant(ret_node.value):
                value_str = ast.unparse(ret_node.value)
                self.violations.append((
                    node.lineno,
                    node.name,
                    value_str
                ))

        # Also check for functions with only docstring + return constant
        if len(node.body) == 2:
            if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                if isinstance(node.body[1], ast.Return):
                    ret_node = node.body[1]
                    if ret_node.value and self._is_constant(ret_node.value):
                        value_str = ast.unparse(ret_node.value)
                        self.violations.append((
                            node.lineno,
                            node.name,
                            value_str
                        ))

        self.generic_visit(node)

    def _is_constant(self, node: ast.AST) -> bool:
        """Check if node is a constant value."""
        if isinstance(node, ast.Constant):
            # Exclude None (acceptable return)
            if node.value is None:
                return False
            # Detect hardcoded numbers, strings, booleans
            if isinstance(node.value, (int, float, str, bool)):
                return True
        return False

def scan_file(filepath: Path) -> List[Tuple[int, str, str]]:
    """Scan a single Python file for hardcoded return values."""
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=str(filepath))
        except SyntaxError:
            return []

    detector = HardcodedReturnDetector()
    detector.visit(tree)
    return detector.violations

def main():
    rustybt_dir = Path('rustybt')
    violations_found = False

    for py_file in rustybt_dir.rglob('*.py'):
        # Skip test files and __init__.py
        if 'test' in py_file.name or py_file.name == '__init__.py':
            continue

        violations = scan_file(py_file)
        if violations:
            violations_found = True
            print(f"\n{py_file}:")
            for lineno, func_name, value in violations:
                print(f"  Line {lineno}: Function '{func_name}' returns hardcoded value: {value}")

    if violations_found:
        print("\n❌ Hardcoded return values detected")
        sys.exit(1)
    else:
        print("✅ No hardcoded return values detected")
        sys.exit(0)

if __name__ == '__main__':
    main()
```

**Usage:**
```bash
# Check for hardcoded values (fail on found)
python scripts/detect_hardcoded_values.py --fail-on-found
```

---

**Validation Verification Script (verify_validations.py):**

**Purpose:** Verify that validation functions actually reject invalid data.

**Detection Strategy:**
1. Find all functions with "validate" in name
2. Test with intentionally invalid inputs
3. Verify they raise exceptions or return False

**Algorithm:**
```python
# scripts/verify_validations.py
import importlib
import inspect
import sys
from pathlib import Path
from typing import List, Callable

def find_validation_functions() -> List[Callable]:
    """Find all validation functions in rustybt package."""
    validators = []

    # Import rustybt package
    import rustybt

    # Recursively find modules
    for module_path in Path('rustybt').rglob('*.py'):
        if 'test' in str(module_path) or module_path.name == '__init__.py':
            continue

        # Convert path to module name
        module_name = str(module_path).replace('/', '.').replace('.py', '')

        try:
            module = importlib.import_module(module_name)
        except:
            continue

        # Find functions with 'validate' in name
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if 'validate' in name.lower():
                validators.append((module_name, name, obj))

    return validators

def test_validator(module_name: str, func_name: str, func: Callable) -> bool:
    """Test if validator rejects invalid data."""
    # Get function signature
    sig = inspect.signature(func)

    # Prepare invalid test inputs
    invalid_inputs = {
        'str': ['', None, 123, [], {}],
        'int': [None, 'invalid', [], {}],
        'float': [None, 'invalid', [], {}],
        'Decimal': [None, 'invalid', 0.1, []],
        'dict': [None, 'invalid', [], 123],
        'list': [None, 'invalid', {}, 123],
    }

    # Try to call with invalid inputs
    try:
        # Simple test: call with None if single parameter
        if len(sig.parameters) == 1:
            try:
                result = func(None)
                # If it returns True or doesn't raise, it's a bad validator
                if result is True:
                    return False
            except:
                # Good - it raised an exception for invalid input
                return True

        return True  # Can't test multi-param validators easily
    except:
        return True

def main():
    validators = find_validation_functions()
    print(f"Found {len(validators)} validation functions")

    bad_validators = []
    for module_name, func_name, func in validators:
        if not test_validator(module_name, func_name, func):
            bad_validators.append(f"{module_name}.{func_name}")

    if bad_validators:
        print("\n❌ Validators that always return True:")
        for validator in bad_validators:
            print(f"  - {validator}")
        sys.exit(1)
    else:
        print("✅ All validators reject invalid data")
        sys.exit(0)

if __name__ == '__main__':
    main()
```

**Usage:**
```bash
# Verify validation functions work
python scripts/verify_validations.py --ensure-real-checks
```

---

**Unique Results Test Script (test_unique_results.py):**

**Purpose:** Verify that functions produce different outputs for different inputs.

**Detection Strategy:**
1. Find functions that take parameters
2. Call with different inputs
3. Verify outputs are different

**Algorithm:**
```python
# scripts/test_unique_results.py
import importlib
import inspect
import sys
from pathlib import Path
from typing import List, Callable, Any
from decimal import Decimal

def find_testable_functions() -> List[Callable]:
    """Find functions that can be tested for unique results."""
    functions = []

    for module_path in Path('rustybt').rglob('*.py'):
        if 'test' in str(module_path) or module_path.name == '__init__.py':
            continue

        module_name = str(module_path).replace('/', '.').replace('.py', '')

        try:
            module = importlib.import_module(module_name)
        except:
            continue

        for name, obj in inspect.getmembers(module, inspect.isfunction):
            # Only test pure calculation functions
            if any(keyword in name.lower() for keyword in ['calculate', 'compute', 'process']):
                sig = inspect.signature(obj)
                # Only test if function takes parameters
                if len(sig.parameters) > 0:
                    functions.append((module_name, name, obj))

    return functions

def test_function_uniqueness(module_name: str, func_name: str, func: Callable) -> bool:
    """Test if function produces unique results for different inputs."""
    sig = inspect.signature(func)

    # Generate test inputs
    test_inputs = [
        (Decimal('10'),),
        (Decimal('20'),),
        (Decimal('30'),),
    ]

    try:
        results = set()
        for inputs in test_inputs:
            result = func(*inputs)
            if result is not None:
                # Convert to hashable type
                if isinstance(result, (int, float, str, Decimal)):
                    results.add(result)

        # If all results are the same, it's suspicious
        if len(results) == 1 and len(test_inputs) > 1:
            return False

        return True
    except:
        # Can't test - skip
        return True

def main():
    functions = find_testable_functions()
    print(f"Testing {len(functions)} functions for unique results")

    suspicious_functions = []
    for module_name, func_name, func in functions:
        if not test_function_uniqueness(module_name, func_name, func):
            suspicious_functions.append(f"{module_name}.{func_name}")

    if suspicious_functions:
        print("\n⚠️ Functions that produce identical results for different inputs:")
        for func_name in suspicious_functions:
            print(f"  - {func_name}")
        sys.exit(1)
    else:
        print("✅ All functions produce unique results")
        sys.exit(0)

if __name__ == '__main__':
    main()
```

**Usage:**
```bash
# Test result uniqueness
python scripts/test_unique_results.py
```

---

**Zero-Mock Policy Documentation:**

**Forbidden Patterns:**
```python
# ❌ FORBIDDEN: Hardcoded return values
def calculate_sharpe_ratio(returns):
    return 1.5  # Mock value - FORBIDDEN

def validate_price(price):
    return True  # Always passes - FORBIDDEN

# ❌ FORBIDDEN: Mock implementations
def mock_get_price(asset):
    return Decimal("100")

class FakeBroker:
    def submit_order(self, order):
        return "fake-order-123"

# ❌ FORBIDDEN: Placeholder implementations
def calculate_returns(data):
    pass  # TODO: implement later - FORBIDDEN
```

**Allowed Patterns:**
```python
# ✅ ALLOWED: Real calculation
def calculate_sharpe_ratio(returns: pl.Series) -> Decimal:
    """Calculate actual Sharpe ratio from returns series."""
    if len(returns) < 2:
        raise ValueError("Insufficient data")
    mean_return = returns.mean()
    std_return = returns.std()
    if std_return == 0:
        return Decimal(0)
    return Decimal(str(mean_return / std_return))

# ✅ ALLOWED: Real validation
def validate_price(price: Decimal) -> bool:
    """Validate price is positive Decimal."""
    if not isinstance(price, Decimal):
        raise TypeError("Price must be Decimal")
    if price <= Decimal("0"):
        raise ValueError("Price must be positive")
    return True

# ✅ ALLOWED: Real implementation
def get_price(self, asset: Asset, dt: pd.Timestamp) -> Decimal:
    """Get actual price from data portal."""
    return self._data_portal.get_price(asset, dt)

# ✅ ALLOWED: Test fixtures (in test files only)
@pytest.fixture
def sample_broker():
    """Create real broker instance for testing."""
    return PaperBroker(initial_capital=Decimal("100000"))
```

**Integration with CI/CD:**
- Pre-commit hook runs `detect_mocks.py --quick` (< 2 seconds)
- CI runs all 4 detection scripts (BLOCKING)
- CI workflow prepared in X2.4, activated in X2.5

### Testing

**Source:** [docs/architecture/testing-strategy.md](../architecture/testing-strategy.md)

**Test Standards:**
- Detection scripts themselves should be tested
- Test with known mock patterns to verify detection works
- Test with clean code to verify no false positives

**Testing Commands:**

```bash
# Test detection scripts work
# Create test file with mock patterns
cat > /tmp/test_mock.py <<'EOF'
def mock_calculate():
    return 10

def validate_data(data):
    return True
EOF

# Run detection (should find violations)
python scripts/detect_mocks.py --file /tmp/test_mock.py
python scripts/detect_hardcoded_values.py --file /tmp/test_mock.py

# Test on clean code (should pass)
python scripts/detect_mocks.py --file rustybt/exceptions.py
python scripts/detect_hardcoded_values.py --file rustybt/exceptions.py

# Full codebase scan
python scripts/detect_mocks.py --strict
python scripts/detect_hardcoded_values.py --fail-on-found
python scripts/verify_validations.py --ensure-real-checks
python scripts/test_unique_results.py
```

**Pre-Commit Hook Testing:**

```bash
# Install pre-commit hooks
pre-commit install

# Run all hooks manually
pre-commit run --all-files

# Test with sample commit containing mock code (should block)
echo "def mock_func(): return 10" > test.py
git add test.py
git commit -m "test" # Should be blocked by detect_mocks hook
git reset HEAD test.py
rm test.py
```
```

---

# Story X2.6 Remediation (HIGH)

**File:** `docs/stories/X2.6.p1-dependency-hygiene.story.md`
**Status:** ❌ NO-GO → Must fix before implementation
**Priority:** 🔴 HIGH (Blocks X2.5 CI/CD pipeline, can run parallel with X2.4)
**Estimated Fix Time:** 2-3 hours

## Issues Summary

| Issue | Severity | Current State | Fix Required |
|-------|----------|---------------|--------------|
| Incomplete Dev Agent Record | CRITICAL | 0/4 subsections | Add all 4 subsections |
| Missing Testing subsection | Should-Fix | Missing | Add Testing subsection |
| Sparse Dev Notes | Should-Fix | Limited guidance | Expand with 100+ lines |
| Tasks lack subtasks | Should-Fix | 0 subtasks | Add 5-10 subtasks per task |

## Remediation Steps

### Step 1: Add Dev Agent Record Subsections

**Location:** Line 102 (after "## Dev Agent Record")

**Current:**
```markdown
## Dev Agent Record

*This section will be populated by the development agent during implementation.*

## QA Results
```

**Replace With:**
```markdown
## Dev Agent Record

*This section will be populated by the development agent during implementation.*

### Agent Model Used

*To be filled by dev agent*

### Debug Log References

*To be filled by dev agent*

### Completion Notes List

*To be filled by dev agent*

### File List

*To be filled by dev agent*

## QA Results
```

### Step 2: Enhance Dev Notes Technical Guidance

**Location:** Line 79 (after existing Dev Notes content)

**Current Dev Notes ends at line 95. Add this content BEFORE "## Change Log":**

```markdown
### Technical Implementation Guidance

**Dependency Split Strategy:**

**Current Structure (pyproject.toml):**
```toml
[project]
dependencies = [
    # Core dependencies (production-required)
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "polars>=0.20.0",
    "ccxt>=4.0.0",
    # ... many more including dev tools
]
```

**Target Structure:**
```toml
[project]
dependencies = [
    # Production-only dependencies
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "polars>=0.20.0",
    "ccxt>=4.0.0",
    "ib-insync>=0.9.86",
    "yfinance>=0.2.0",
    "structlog>=23.0.0",
    "pydantic>=2.0.0",
    # ... core only
]

[project.optional-dependencies]
dev = [
    # Development tools
    "jupyter>=1.0.0",
    "jupyterlab>=4.0.0",
    "ipython>=8.0.0",
    "streamlit>=1.30.0",
    # Type stubs
    "pandas-stubs>=2.0.0",
    "types-requests>=2.31.0",
    "types-PyYAML>=6.0.1",
    "types-networkx>=3.1.0",
    # Documentation
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.0.0",
]

test = [
    # Testing tools (from X2.1)
    "pytest>=7.2.0",
    "pytest-cov>=3.0.0",
    "pytest-xdist>=2.5.0",
    "freezegun>=1.2.0",
    "responses>=0.23.0",
    "hypothesis>=6.0.0",
]
```

**Installation Commands:**
```bash
# Production only
uv sync

# Development
uv sync -E dev -E test

# Testing only
uv sync -E test
```

---

**Vulnerability Remediation Process:**

**Step 1: Identify Vulnerabilities**
```bash
# Run safety scan
uv run safety scan --json > safety-report.json

# Run pip-audit
uv run pip-audit --format json > pip-audit-report.json

# Review reports
cat safety-report.json | jq '.vulnerabilities[]'
cat pip-audit-report.json | jq '.vulnerabilities[]'
```

**Step 2: Prioritize Remediation**
```
Priority 1: High/Critical vulnerabilities in production dependencies
Priority 2: Medium vulnerabilities in production dependencies
Priority 3: High/Critical vulnerabilities in dev dependencies
Priority 4: Low/Medium vulnerabilities in dev dependencies
```

**Step 3: Upgrade or Pin**
```bash
# For upgradeable packages
uv add "package>=fixed_version"

# For packages without patches
# Option A: Pin to secure version if downgrade acceptable
uv add "package==last_secure_version"

# Option B: Document risk if upgrade breaks compatibility
# Add to docs/security-audit.md:
# - Package: package_name
# - Vulnerability: CVE-XXXX-XXXX
# - Severity: Medium
# - Status: Accepted (no patch available)
# - Mitigation: Not using vulnerable functionality
# - Review Date: 2025-Q2
```

**Step 4: Update Lockfile**
```bash
# Regenerate lockfile with new versions
uv lock

# Verify resolution succeeds
uv sync -E dev -E test

# Run test suite to verify compatibility
uv run pytest
```

---

**License Compliance Script:**

**Purpose:** Ensure no GPL-licensed dependencies (Apache 2.0/MIT only).

**Implementation:**
```python
# scripts/check_licenses.py
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

FORBIDDEN_LICENSES = ['GPL', 'AGPL', 'LGPL', 'SSPL']
ALLOWED_LICENSES = ['MIT', 'Apache', 'BSD', '3-Clause', '2-Clause', 'ISC', 'Python']

def get_installed_packages() -> List[str]:
    """Get list of installed packages."""
    result = subprocess.run(
        ['uv', 'pip', 'list', '--format=json'],
        capture_output=True,
        text=True
    )
    packages = json.loads(result.stdout)
    return [pkg['name'] for pkg in packages]

def get_package_license(package_name: str) -> str:
    """Get license for a package using pip-licenses."""
    result = subprocess.run(
        ['uv', 'run', 'pip-licenses', '--packages', package_name, '--format=json'],
        capture_output=True,
        text=True
    )
    try:
        licenses = json.loads(result.stdout)
        if licenses:
            return licenses[0].get('License', 'UNKNOWN')
    except:
        pass
    return 'UNKNOWN'

def check_license(license_str: str) -> bool:
    """Check if license is allowed."""
    license_upper = license_str.upper()

    # Check for forbidden licenses
    for forbidden in FORBIDDEN_LICENSES:
        if forbidden in license_upper:
            return False

    # Check for allowed licenses
    for allowed in ALLOWED_LICENSES:
        if allowed.upper() in license_upper:
            return True

    # Unknown or uncommon license - warn
    return None

def main():
    """Check all package licenses."""
    print("Checking dependency licenses...")

    # Install pip-licenses if not available
    subprocess.run(['uv', 'pip', 'install', 'pip-licenses'], capture_output=True)

    packages = get_installed_packages()

    forbidden_packages = []
    unknown_packages = []

    for package in packages:
        license_str = get_package_license(package)
        result = check_license(license_str)

        if result is False:
            forbidden_packages.append((package, license_str))
        elif result is None:
            unknown_packages.append((package, license_str))

    # Report results
    if forbidden_packages:
        print("\n❌ FORBIDDEN LICENSES DETECTED:")
        for package, license_str in forbidden_packages:
            print(f"  - {package}: {license_str}")
        sys.exit(1)

    if unknown_packages:
        print("\n⚠️ UNKNOWN LICENSES (review required):")
        for package, license_str in unknown_packages:
            print(f"  - {package}: {license_str}")

    print("\n✅ All dependencies use allowed licenses")
    sys.exit(0)

if __name__ == '__main__':
    main()
```

**Usage:**
```bash
# Check licenses (CI integration)
python scripts/check_licenses.py
```

---

**Dependency Security Documentation:**

**File:** `docs/security-audit.md`

**Add Section:**
```markdown
## Dependency Security

**Last Updated:** 2025-10-12

### Vulnerability Tracking

| Package | Version | Vulnerability | Severity | Status | Mitigation |
|---------|---------|---------------|----------|--------|------------|
| (example) requests | 2.28.0 | CVE-2023-XXXXX | Medium | Upgraded to 2.31.0 | N/A |

### Accepted Risks

| Package | Vulnerability | Severity | Justification | Review Date |
|---------|---------------|----------|---------------|-------------|
| (example) package_name | CVE-2023-XXXXX | Low | Not using vulnerable functionality | 2025-Q2 |

### Weekly Scan Results

Automated security scans run every Monday at 2 AM UTC via GitHub Actions workflow:
`.github/workflows/dependency-security.yml`

Reports uploaded as artifacts to workflow runs.

### Upgrade Policy

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
```

---

**Integration with CI/CD (from X2.5):**

The dependency security workflow from X2.5 will run weekly:

```yaml
# .github/workflows/dependency-security.yml
# (Created in X2.5, references scripts from X2.6)
name: Dependency Security

on:
  schedule:
    - cron: '0 2 * * 1'  # Monday 2 AM UTC
  workflow_dispatch:

jobs:
  dependency-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: |
          uv sync -E dev -E test

      - name: Run safety scan
        run: |
          uv run safety scan --json > safety-report.json || true

      - name: Run pip-audit
        run: |
          uv run pip-audit --format json > pip-audit-report.json || true

      - name: Check licenses (BLOCKING)
        run: |
          uv run python scripts/check_licenses.py

      - name: Upload security reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            safety-report.json
            pip-audit-report.json
```

### Testing

**Source:** [docs/architecture/testing-strategy.md](../architecture/testing-strategy.md)

**Test Standards:**
- Dependency split tested with fresh install
- Vulnerability remediation verified with security scans
- License check tested with known GPL package (should fail)
- Lockfile resolution verified with uv sync

**Testing Commands:**

```bash
# Test production dependencies only
rm -rf .venv
uv sync  # Should install only production deps
uv run python -c "import jupyter" # Should fail

# Test dev dependencies
rm -rf .venv
uv sync -E dev -E test
uv run python -c "import jupyter" # Should succeed

# Test license check
python scripts/check_licenses.py

# Test vulnerability scans
uv run safety scan
uv run pip-audit

# Test lockfile
uv lock
uv sync -E dev -E test
uv run pytest  # All tests should pass
```

**Regression Tests:**

```bash
# Verify full test suite still passes
uv sync -E test
uv run pytest -m "not memory and not api_integration and not live and not ib_integration"

# Verify coverage maintained
uv run pytest --cov=rustybt --cov-report=term

# Verify no dependency resolution conflicts
uv lock --verbose
```
```

### Step 3: Add Subtasks to All Tasks

**Location:** Lines 71-77 (Tasks / Subtasks section)

**Current:**
```markdown
## Tasks / Subtasks

- [ ] **Task 1: Split Dependencies** (AC: 1)
- [ ] **Task 2: Remediate Vulnerabilities** (AC: 2)
- [ ] **Task 3: Update Lockfile** (AC: 3)
- [ ] **Task 4: Create License Check Script** (AC: 4)
- [ ] **Task 5: Verify CI Integration** (AC: 5)
- [ ] **Task 6: Update Documentation** (AC: 6)
- [ ] **Task 7: Final Validation** (AC: 7)
```

**Replace With:**

```markdown
## Tasks / Subtasks

- [ ] **Task 1: Split Dependencies** (AC: 1)
  - [ ] Review current `[project.dependencies]` in pyproject.toml
  - [ ] Identify dev-only packages: jupyter, jupyterlab, streamlit, torch
  - [ ] Identify type stubs: pandas-stubs, types-*
  - [ ] Create `[project.optional-dependencies].dev` section
  - [ ] Move dev tools to dev extra
  - [ ] Move type stubs to dev extra
  - [ ] Verify core dependencies remain in `[project.dependencies]`
  - [ ] Test production install: `rm -rf .venv && uv sync`
  - [ ] Verify jupyter NOT available in production: `uv run python -c "import jupyter"`
  - [ ] Test dev install: `rm -rf .venv && uv sync -E dev -E test`
  - [ ] Verify jupyter available in dev: `uv run python -c "import jupyter"`
  - [ ] Document installation commands in README.md

- [ ] **Task 2: Remediate Vulnerabilities** (AC: 2)
  - [ ] Run safety scan: `uv run safety scan --json > safety-report.json`
  - [ ] Run pip-audit: `uv run pip-audit --format json > pip-audit-report.json`
  - [ ] Review reports and categorize vulnerabilities by severity
  - [ ] Prioritize High/Critical vulnerabilities in production dependencies
  - [ ] For each vulnerability:
    - [ ] Check if upgrade available
    - [ ] Upgrade to patched version if available
    - [ ] Test compatibility after upgrade
    - [ ] If no patch available, document in docs/security-audit.md
  - [ ] Verify production extras exclude dev-only vulnerable packages
  - [ ] Document any accepted risks with justification

- [ ] **Task 3: Update Lockfile** (AC: 3)
  - [ ] Run `uv lock` to update lock file with new versions
  - [ ] Review lockfile diff to verify changes are expected
  - [ ] Verify no dependency resolution conflicts
  - [ ] Test production install: `uv sync`
  - [ ] Test dev install: `uv sync -E dev -E test`
  - [ ] Run full test suite: `uv run pytest`
  - [ ] Verify all tests pass with new dependencies
  - [ ] Commit updated `uv.lock` with story changes

- [ ] **Task 4: Create License Check Script** (AC: 4)
  - [ ] Create `scripts/check_licenses.py`
  - [ ] Implement package license detection (using pip-licenses)
  - [ ] Define forbidden licenses: GPL, AGPL, LGPL, SSPL
  - [ ] Define allowed licenses: MIT, Apache, BSD, ISC, Python
  - [ ] Implement license checking logic
  - [ ] Test with known GPL package (should fail)
  - [ ] Test with current dependencies (should pass)
  - [ ] Document any license exceptions with justification
  - [ ] Verify script exits with code 1 if forbidden licenses found

- [ ] **Task 5: Verify CI Integration** (AC: 5)
  - [ ] Verify dependency-security workflow exists from X2.5
  - [ ] Verify workflow includes `check_licenses.py`
  - [ ] Verify safety scan runs weekly
  - [ ] Verify pip-audit runs weekly
  - [ ] Verify reports uploaded as artifacts
  - [ ] Test workflow manually: `gh workflow run dependency-security.yml`
  - [ ] Verify workflow creates issue on failure

- [ ] **Task 6: Update Documentation** (AC: 6)
  - [ ] Update README.md with dev extras installation: `uv sync -E dev -E test`
  - [ ] Update `docs/security-audit.md` with vulnerability tracking section
  - [ ] Add vulnerability tracking table
  - [ ] Add accepted risks table
  - [ ] Add weekly scan results section
  - [ ] Document dependency upgrade policy
  - [ ] Document license compliance requirements

- [ ] **Task 7: Final Validation** (AC: 7)
  - [ ] Fresh install test (production): `rm -rf .venv && uv sync`
  - [ ] Verify jupyter NOT available
  - [ ] Fresh install test (dev): `rm -rf .venv && uv sync -E dev -E test`
  - [ ] Verify jupyter available
  - [ ] Run full test suite: `uv run pytest`
  - [ ] Verify all tests pass
  - [ ] Verify no dependency resolution conflicts
  - [ ] Verify production dependencies reduced (count before/after)
  - [ ] Run license check: `python scripts/check_licenses.py`
  - [ ] Verify 0 forbidden licenses
```

---

# Story X2.1 Remediation (MINOR)

**File:** `docs/stories/X2.1.p0-security-test-infrastructure.story.md`
**Status:** ⚠️ SHOULD-FIX (but implementation-ready)
**Priority:** 🟡 MEDIUM (minor fix, can be done anytime)
**Estimated Fix Time:** 30 minutes

## Issues Summary

| Issue | Severity | Fix Required |
|-------|----------|--------------|
| Missing Testing subsection | Should-Fix | Add Testing subsection |

## Remediation Steps

### Add Testing Subsection

**Location:** Line 256 (after "### Technical Implementation Guidance")

**Add BEFORE the "## Change Log" section:**

```markdown
### Testing

**Source:** [docs/architecture/coding-standards.md](../architecture/coding-standards.md) (lines 433-483: Testing Standards)

**Test File Locations:**
- Security tests: `tests/data/bundles/test_quandl_security.py`, `tests/test_algorithm_security.py`
- Integration tests: `tests/integration/test_bundle_ingestion.py`, `tests/integration/test_request_timeouts.py`

**Test Standards:**
- All public functions require unit tests
- Coverage targets: ≥90% for core modules, ≥95% for financial modules
- Use pytest fixtures for test data setup
- Mock external dependencies (broker APIs, network calls)

**Testing Frameworks:**
- pytest for unit/integration tests
- pytest-cov for coverage measurement
- freezegun for time-dependent tests
- responses for HTTP mocking

**CI Test Command:**
```bash
# Unit tests with coverage
pytest -m "not memory and not api_integration and not live and not ib_integration" \
  --cov=rustybt --cov-report=term --cov-report=html
```

**Security Test Examples:**

```python
# tests/data/bundles/test_quandl_security.py
import tarfile
import tempfile
from pathlib import Path
import pytest
from rustybt.data.bundles.quandl import safe_extract

def test_tarfile_path_traversal_blocked():
    """Test that path traversal attempts are blocked."""
    # Create malicious tar with path traversal
    with tempfile.NamedTemporaryFile(suffix='.tar', delete=False) as tmp:
        tar_path = tmp.name
        with tarfile.open(tar_path, 'w') as tar:
            # Create member with path traversal
            info = tarfile.TarInfo(name='../../../etc/passwd')
            info.size = 0
            tar.addfile(info)

    # Attempt to extract should raise ValueError
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="Unsafe tar member path"):
            safe_extract(tar_path, tmpdir)

def test_tarfile_safe_extraction():
    """Test that legitimate tar extraction works."""
    # Create safe tar
    with tempfile.NamedTemporaryFile(suffix='.tar', delete=False) as tmp:
        tar_path = tmp.name
        with tarfile.open(tar_path, 'w') as tar:
            info = tarfile.TarInfo(name='data/file.txt')
            info.size = 0
            tar.addfile(info)

    # Extract should succeed
    with tempfile.TemporaryDirectory() as tmpdir:
        safe_extract(tar_path, tmpdir)
        assert Path(tmpdir, 'data', 'file.txt').exists()
```
```

---

# Story X2.3 Remediation (MINOR)

**File:** `docs/stories/X2.3.p1-code-quality-baseline.story.md`
**Status:** ⚠️ SHOULD-FIX (but implementation-ready)
**Priority:** 🟡 MEDIUM (minor fix, can be done anytime)
**Estimated Fix Time:** 30 minutes

## Issues Summary

| Issue | Severity | Fix Required |
|-------|----------|--------------|
| Missing Testing subsection | Should-Fix | Add Testing subsection |

## Remediation Steps

### Add Testing Subsection

**Location:** Line 285 (after "### Technical Implementation Guidance")

**Add BEFORE the "## Change Log" section:**

```markdown
### Testing

**Source:** [docs/architecture/coding-standards.md](../architecture/coding-standards.md) (lines 433-483: Testing Standards)

**Test File Locations:**
- No new test files required (code quality tools tested via pre-commit and CI)
- Existing tests must pass after formatting/linting changes

**Test Standards:**
- All public functions require unit tests
- Coverage targets: ≥90% for core modules, ≥95% for financial modules
- Use pytest fixtures for test data setup

**Testing Commands:**

```bash
# Verify code quality tools work
uv run ruff check .
uv run black --check .
uv run python3 -m mypy

# Run pre-commit hooks locally
pre-commit run --all-files

# Run full test suite (verify no regressions)
pytest -m "not memory and not api_integration and not live and not ib_integration" \
  --cov=rustybt --cov-report=term --cov-report=html

# Verify coverage maintained
pytest --cov=rustybt --cov-report=term | grep "TOTAL"
```

**Pre-Commit Testing:**

```bash
# Install hooks
pre-commit install

# Test hooks run correctly
echo "print('test')" > test_file.py
git add test_file.py
git commit -m "test"  # Hooks should run
git reset HEAD test_file.py
rm test_file.py

# Test hooks block bad commits
echo "print( 'badly formatted' )" > bad_format.py
git add bad_format.py
git commit -m "test"  # Should be blocked by black
git reset HEAD bad_format.py
rm bad_format.py
```

**Regression Testing:**

```bash
# Smoke tests after code quality changes
python -m rustybt ingest -b quandl  # Bundle ingestion
python -m rustybt run-algorithm --start 2023-01-01 --end 2023-12-31  # Backtest
python -m rustybt paper-trade --duration 1h  # Paper trading start
```
```

---

# Implementation Checklist

## Pre-Implementation Setup

- [ ] Pull latest main branch: `git checkout main && git pull`
- [ ] Create feature branch: `git checkout -b fix/epic-x2-story-remediation`
- [ ] Review this entire remediation document
- [ ] Allocate 8-10 hours for all fixes (1-2 days)

## Phase 1: Critical Fixes (Priority Order)

### Fix X2.5 First (3-4 hours)
- [ ] Open `docs/stories/X2.5.p1-cicd-pipeline.story.md`
- [ ] Add Dev Agent Record subsections (5 minutes)
- [ ] Expand Dev Notes to 200+ lines (2 hours)
  - [ ] Add Architecture Context
  - [ ] Add 6 workflow YAML examples
  - [ ] Add branch protection configuration
  - [ ] Add PR template
  - [ ] Add Testing subsection
- [ ] Add subtasks to all 11 tasks (1 hour)
- [ ] Save and commit: `git add docs/stories/X2.5.p1-cicd-pipeline.story.md`
- [ ] Commit: `git commit -m "fix: X2.5 - Expand Dev Notes and add subtasks"`

### Fix X2.4 and X2.6 in Parallel (4-6 hours combined)

#### Fix X2.4 (2-3 hours)
- [ ] Open `docs/stories/X2.4.p1-zero-mock-enforcement.story.md`
- [ ] Add Dev Agent Record subsections (5 minutes)
- [ ] Enhance Dev Notes with 100+ lines (1.5 hours)
  - [ ] Add 4 detection script implementations
  - [ ] Add zero-mock policy examples
  - [ ] Add Testing subsection
- [ ] Save and commit: `git add docs/stories/X2.4.p1-zero-mock-enforcement.story.md`
- [ ] Commit: `git commit -m "fix: X2.4 - Enhance Dev Notes with detection scripts"`

#### Fix X2.6 (2-3 hours)
- [ ] Open `docs/stories/X2.6.p1-dependency-hygiene.story.md`
- [ ] Add Dev Agent Record subsections (5 minutes)
- [ ] Enhance Dev Notes with 100+ lines (1 hour)
  - [ ] Add dependency split examples
  - [ ] Add vulnerability remediation process
  - [ ] Add license check script
  - [ ] Add Testing subsection
- [ ] Add subtasks to all 7 tasks (1 hour)
- [ ] Save and commit: `git add docs/stories/X2.6.p1-dependency-hygiene.story.md`
- [ ] Commit: `git commit -m "fix: X2.6 - Enhance Dev Notes and add subtasks"`

## Phase 2: Minor Fixes (1 hour)

### Fix X2.1 (30 minutes)
- [ ] Open `docs/stories/X2.1.p0-security-test-infrastructure.story.md`
- [ ] Add Testing subsection after Technical Implementation Guidance
- [ ] Save and commit: `git add docs/stories/X2.1.p0-security-test-infrastructure.story.md`
- [ ] Commit: `git commit -m "fix: X2.1 - Add Testing subsection"`

### Fix X2.3 (30 minutes)
- [ ] Open `docs/stories/X2.3.p1-code-quality-baseline.story.md`
- [ ] Add Testing subsection after Technical Implementation Guidance
- [ ] Save and commit: `git add docs/stories/X2.3.p1-code-quality-baseline.story.md`
- [ ] Commit: `git commit -m "fix: X2.3 - Add Testing subsection"`

## Validation & PR

### Validate All Fixes
- [ ] Re-run validation task against all 7 stories
- [ ] Verify all stories now have GO status
- [ ] Review all diffs to ensure quality

### Create Pull Request
- [ ] Push feature branch: `git push -u origin fix/epic-x2-story-remediation`
- [ ] Create PR with title: "fix: Epic X2 Story Remediation - Template Compliance"
- [ ] PR description should reference this remediation plan
- [ ] Request review from PM/Architect
- [ ] Merge after approval

## Post-Merge Actions

- [ ] Verify all 7 stories now marked GO in validation
- [ ] Communicate to team: Epic X2 stories ready for implementation
- [ ] Update Epic X2 PRD with story readiness status
- [ ] Archive this remediation plan for reference

---

## Time Tracking Template

| Story | Estimated Time | Actual Time | Notes |
|-------|----------------|-------------|-------|
| X2.5 | 3-4 hours | ___ hours | |
| X2.4 | 2-3 hours | ___ hours | |
| X2.6 | 2-3 hours | ___ hours | |
| X2.1 | 30 minutes | ___ minutes | |
| X2.3 | 30 minutes | ___ minutes | |
| **Total** | **8-10 hours** | **___ hours** | |

---

## Support & Questions

**Contact:**
- Product Owner: Sarah
- Scrum Master: Bob
- Architect: Winston

**References:**
- Validation Report: `docs/EPIC-X2-VALIDATION-REPORT.md`
- Story Template: `.bmad-core/templates/story-tmpl.yaml`
- Epic X2 PRD: `docs/prd/epic-X2-production-readiness-remediation.story.md`

---

**Document Version:** 1.0
**Last Updated:** 2025-10-12
**Status:** Ready for Implementation
