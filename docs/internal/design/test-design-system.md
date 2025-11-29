# System-Level Test Design: rustybt Validation Framework

**Date:** 2025-11-24
**Author:** .smirk (via TEA Agent - Murat)
**Status:** Draft - Pending Implementation-Readiness Gate Check
**Phase:** Phase 3 - Solutioning (Testability Review)

---

## Executive Summary

**Scope:** System-level testability assessment of rustybt validation framework architecture before Phase 4 implementation.

**Gate Recommendation:** ⚠️ **CONCERNS** - Architecture is fundamentally testable with excellent controllability and observability. Requires 3 high-priority enhancements (resilience patterns, performance SLOs, investigation workflow validation) before implementation-readiness approval. Note: Decimal tolerance testing (originally TC-001 blocker) deferred to Post-MVP per user scope decision.

**Risk Summary:**

- **Critical Risks (Score 9):** 2 risks identified (decimal precision validation, temporal integrity testing)
- **High-Priority Risks (Score 6-8):** 3 risks identified (resilience patterns, performance baselines, investigation testability)
- **Testability Blockers:** 1 blocker (TC-001: Missing tolerance tests)
- **Recommendations:** 4 actionable items for Sprint 0 / Epic 1

**Architecture Strengths:**
- ✅ Excellent controllability via ValidatedStrategy pattern and subprocess isolation
- ✅ Strong observability through structured JSONL logs and Parquet caching
- ✅ Solid maintainability foundation (pytest, Polars, mypy, ruff)

**Architecture Gaps:**
- ❌ Missing decimal precision tolerance validation tests
- ⚠️ No resilience patterns (retries, health checks, circuit breakers)
- ⚠️ Undefined performance SLOs
- ⚠️ Manual investigation workflow lacks automated validation

---

## Testability Assessment

### Controllability: ✅ PASS

**Definition:** Can we control system state for testing?

**Assessment:**

The architecture demonstrates excellent controllability across all critical dimensions:

**✅ State Control:**
- **ValidatedStrategy Base Classes** (Architecture pg 162-178): Auto-logging lifecycle events enables precise state tracking
- **Shared Parquet Fixtures** (Architecture pg 206-211): Identical data inputs for rustybt and Backtrader ensure controlled comparisons
- **Session Management** (FR31-40): YAML-based session state with timestamped execution records

**✅ Dependency Mockability:**
- **Subprocess Isolation** (Architecture pg 27): Separate processes for rustybt and Backtrader prevent API conflicts
- **Zero Mock Enforcement** (PRD pg 13): Real executions with controlled inputs (no mocks = no test brittleness)

**✅ Test Data Factories:**
- **Strategy Instrumentation** (Architecture pg 162-199): @log_event decorators for custom logic logging
- **Tolerance Configuration** (Architecture pg 24): YAML configs per validation layer for fine-grained control

**✅ Reproducibility:**
- **Version Tracking** (Architecture pg 27-30): Capture rustybt version, Backtrader version, Python version per session
- **Seed Control** (Inferred from deterministic testing requirement): Controlled randomness for reproducible results

**Evidence:** Architecture decisions table (pg 17-30), ValidatedStrategy pattern (pg 162-199)

**Verdict:** **PASS** - All controllability criteria met

---

### Observability: ✅ PASS with CONCERNS

**Definition:** Can we inspect system state and validate results?

**Assessment:**

Strong foundational observability, but lacks real-time visibility and investigation metrics:

**✅ Logging Infrastructure:**
- **JSONL Primary Format** (Architecture pg 20): Human-readable logs for debugging
- **Parquet Caching** (Architecture pg 20): Fast columnar queries for test execution
- **Layer Separation** (Architecture pg 185): Explicit layer tags in logs (data|signals|orders|broker|portfolio)

**✅ Test Result Determinism:**
- **Polars-Based Comparison** (Architecture pg 24): Null-aware DataFrame comparisons with tolerance thresholds
- **Pass/Fail Reporting** (FR15-22): Detailed diagnostics per validation layer

**✅ Traceability:**
- **Session Metadata** (Architecture pg 77-91): Complete audit trail per validation run
- **Findings Database** (Architecture pg 79-80): Timestamped discrepancies with classifications

**⚠️ CONCERN - Real-Time Visibility Gaps:**
- **Missing Discrepancy Dashboards:** No real-time view of comparison results during long-running validations
- **Missing Investigation Metrics:** No KPIs for investigation velocity (time to classify BUG vs DESIGN)
- **Missing Progress Indicators:** No incremental reporting for multi-strategy validation sessions

**Recommendations:**
1. Add progress logging to comparison engine (log completion % per layer)
2. Generate intermediate reports during long validations (e.g., after each layer)
3. Track investigation metrics: time-to-classification, BUG-to-fix ratio

**Evidence:** Log schema (Architecture pg 181-199), session structure (pg 77-91), FR60-67 (reporting requirements)

**Verdict:** **PASS with CONCERNS** - Core observability strong, but lacks operational visibility

---

### Reliability: ⚠️ CONCERNS

**Definition:** Are tests isolated, reproducible, and resilient to failures?

**Assessment:**

Test isolation is excellent, but resilience patterns are missing:

**✅ Test Isolation:**
- **pytest Framework** (Architecture pg 25): Custom fixtures with proper teardown
- **Parallel-Safe Design** (Architecture pg 46-50): Strategy directories isolated, no shared state
- **Cleanup Discipline** (Inferred): Session directories gitignored, temporary data managed

**✅ Reproducibility:**
- **Version Tracking** (Architecture pg 29): Framework versions recorded per session
- **Controlled Data** (Architecture pg 68-74): Shared Parquet fixtures ensure identical inputs
- **Deterministic Comparison** (Architecture pg 24-26): Tolerance-based comparisons with fixed thresholds

**❌ FAIL - Missing Resilience Patterns:**

**No Retry Logic:**
- Log parsing failures (corrupted JSONL, incomplete Parquet writes) will halt validation
- No exponential backoff for transient file system errors
- **Impact:** Brittle validation runs require manual recovery

**No Health Checks:**
- No validation of log file integrity before comparison (e.g., schema validation, row count checks)
- No data quality checks on Parquet fixtures (missing columns, null values in critical fields)
- **Impact:** Silent failures produce misleading comparison results

**No Circuit Breakers:**
- Long-running strategy executions could hang indefinitely (no timeout enforcement)
- Infinite loops in strategy code would block entire validation session
- **Impact:** Resource exhaustion, hanging CI jobs

**Recommendations:**
1. **Add retry logic** (exponential backoff, max 3 attempts) for:
   - JSONL parsing (handle corrupted lines)
   - Parquet read operations (handle incomplete writes)
   - Session file I/O (handle concurrent access)

2. **Add health checks** before comparison:
   - Log file integrity: Validate JSONL schema, check for truncated lines
   - Parquet data quality: Verify required columns exist, check for critical nulls
   - Strategy execution success: Verify both rustybt and Backtrader produced logs

3. **Add circuit breakers**:
   - Strategy execution timeout: Kill subprocess after 5 minutes
   - Comparison engine timeout: Fail gracefully after 2 minutes per layer
   - Session timeout: Warn user after 30 minutes total validation time

**Evidence:** Missing from architecture document, inferred from lack of error handling specifications

**Verdict:** **CONCERNS** - Isolation strong, but missing resilience patterns create brittleness

---

## Architecturally Significant Requirements (ASRs)

**ASRs are quality requirements that drive architecture decisions and pose testability challenges.**

### Critical ASRs (Score = 9) - MUST RESOLVE BEFORE IMPLEMENTATION

| ASR ID | NFR Requirement | Architectural Impact | Probability | Impact | Score | Testability Challenge | Mitigation |
|--------|----------------|---------------------|-------------|--------|-------|---------------------|-----------|
| **ASR-001** | **Decimal precision for all financial calculations** (PRD pg 176-180) | Decimal types throughout, tolerance configuration per layer | 3 (Likely) | 3 (Critical) | **9** | **CRITICAL:** Tolerance validation tests missing from architecture | Add Hypothesis property tests per layer validating decimal precision within tolerance thresholds |
| **ASR-002** | **No lookahead bias - temporal integrity** (PRD pg 182-188) | Data windowing validation, timestamp alignment checks | 3 (Likely) | 3 (Critical) | **9** | **CRITICAL:** Must prove strategies cannot access future data | Create intentional lookahead bias test cases that MUST be detected by validation framework |

### High-Priority ASRs (Score 6-8) - SHOULD RESOLVE BEFORE SPRINT 1

| ASR ID | NFR Requirement | Architectural Impact | Probability | Impact | Score | Testability Challenge | Mitigation |
|--------|----------------|---------------------|-------------|--------|-------|---------------------|-----------|
| **ASR-003** | **Deterministic comparison results** (Architecture pg 24-26) | Seed control, controlled data fixtures | 2 (Possible) | 3 (Critical) | **6** | **HIGH:** Randomness must be reproducible across test runs | Document seeding strategy, add tests verifying identical results on re-runs |
| **ASR-004** | **3-4 strategies validated (MVP)** (PRD pg 146-151) | Dual-implementation framework, strategy audit checklist | 2 (Possible) | 3 (Critical) | **6** | **HIGH:** Strategy implementations must be provably equivalent | Create strategy audit checklist (Epic 2), enforce via pre-validation review |
| **ASR-005** | **Zero mock enforcement** (PRD pg 13, Architecture pg 27) | Real executions via subprocess isolation | 1 (Unlikely) | 3 (Critical) | **3** | **MEDIUM:** Performance overhead of dual execution | Benchmark overhead (Story 2.7), optimize if >2x baseline |

### Medium-Priority ASRs (Score 3-4) - MONITOR

| ASR ID | NFR Requirement | Architectural Impact | Probability | Impact | Score | Testability Challenge | Mitigation |
|--------|----------------|---------------------|-------------|--------|-------|---------------------|-----------|
| **ASR-006** | **Resumable validation sessions** (FR35-40) | YAML session state management | 2 (Possible) | 2 (Degraded) | **4** | **MEDIUM:** Session corruption recovery untested | Add session corruption recovery tests (missing session.yaml, partial findings.yaml) |

---

## Test Levels Strategy

**Context:** rustybt validation framework is a **developer tool** (testing infrastructure), not a UI application. Test pyramid adjusts to reflect this.

### Recommended Test Distribution

| Test Level | Percentage | Rationale | Primary Focus Areas |
|------------|-----------|-----------|-------------------|
| **Unit** | **40%** | Complex comparison logic with edge cases | Comparators (tolerance validation), log parsers (corrupted data), session models (CRUD operations), discrepancy classification (BUG vs DESIGN logic) |
| **Integration** | **30%** | Layer interactions and data pipelines | 5-layer comparison engines, pytest fixture behavior, Polars DataFrame operations, session lifecycle (create → execute → classify → complete) |
| **E2E (Validation)** | **30%** | Full strategy validation proving framework correctness | SMA crossover strategy validation, mean reversion strategy validation, full session lifecycle with findings database |

**Justification:**

This distribution reflects the nature of a **validation framework** (testing a testing tool):

- **Higher unit test coverage (40%)**: Complex algorithms need exhaustive edge case testing
  - Decimal tolerance calculations (1.0000001 vs 1.0000002 with tolerance 1e-6)
  - Log parsing edge cases (missing fields, extra fields, null values, truncated lines)
  - Discrepancy classification rules (when is a difference a BUG vs DESIGN?)

- **Integration tests (30%)**: Validate component interactions without full strategy execution overhead
  - Layer-by-layer comparison (data layer only, signals layer only, etc.)
  - Session state transitions (pending → running → completed → archived)
  - Findings database queries (filter by category, filter by session, aggregate statistics)

- **E2E validation tests (30%)**: Prove the framework works by validating real strategies
  - Full dual execution (rustybt + Backtrader) for SMA crossover strategy
  - Complete comparison across all 5 layers
  - BUG/DESIGN classification and resolution verification

**Test Environment Requirements:**

| Environment | Purpose | Setup | Data |
|------------|---------|-------|------|
| **Local Dev** | Fast iteration during development | In-memory fixtures, fast pytest execution | Small datasets (100 bars), single strategy |
| **CI Pipeline** | Automated regression on every commit | pytest with coverage, mypy strict, ruff linting | Medium datasets (1000 bars), 2 strategies |
| **Manual Validation** | Full strategy validation before releases | Complete dual execution with logging | Full datasets (10K+ bars), all 4 MVP strategies |

**No staging/production environments needed** - this is a CLI tool with no deployment.

---

## NFR Testing Approach

### Security: ✅ PASS (Not Applicable)

**Assessment:** Validation framework is a local CLI tool with no authentication, authorization, or network exposure.

**Security Considerations:**
- ✅ **No credentials stored:** Strategies use local data files
- ✅ **No API keys required:** All comparisons run locally
- ✅ **No user data:** Only synthetic test data and strategy code

**Gate Criteria:** **PASS** (security NFRs not applicable to CLI tools)

---

### Performance: ⚠️ CONCERNS (No SLOs Defined)

**Assessment:** Architecture includes performance-conscious decisions (Parquet caching, subprocess isolation), but lacks quantitative targets.

**Performance Considerations:**

**Missing SLOs:**
- ❌ No target for log parsing throughput (lines/second)
- ❌ No target for comparison engine latency (seconds/layer)
- ❌ No target for end-to-end strategy validation time (minutes/strategy)

**Recommended SLOs (Based on Developer Experience):**

| Operation | Target SLO | Rationale |
|-----------|-----------|-----------|
| **Log Parsing** | <5 seconds for 10K log lines | Fast feedback during development |
| **Comparison Engine** | <10 seconds per validation layer | 5 layers × 10s = 50s total acceptable |
| **Full Strategy Validation** | <2 minutes per strategy | 4 strategies × 2min = 8min total acceptable for MVP |
| **Session Overhead** | <5 seconds for session CRUD | Session management shouldn't dominate validation time |

**Testing Approach:**
- **Tool:** pytest-benchmark (already in test plan per Architecture)
- **Baseline Establishment:** Story 2.7 (Document performance baselines for rust optimization)
- **Regression Detection:** CI pipeline fails if performance degrades >20% from baseline

**Missing from Architecture:**
- No benchmarking suite structure defined
- No performance regression detection in CI

**Recommendations:**
1. Define SLO targets in Story 2.7 (already planned)
2. Add pytest-benchmark tests for critical paths:
   - Log parsing (JSONL → Polars DataFrame)
   - Comparison engine (layer-by-layer)
   - Full dual execution (subprocess overhead)
3. Integrate benchmarks into CI pipeline with regression thresholds

**Gate Criteria:** **CONCERNS** - Performance targets undefined, no regression detection

---

### Reliability: ⚠️ CONCERNS (Missing Resilience Patterns)

**Assessment:** Core reliability is strong (deterministic tests, version tracking), but lacks error recovery mechanisms.

**Reliability Strengths:**
- ✅ **Deterministic tests:** Controlled data, seeded randomness
- ✅ **Version tracking:** Framework versions recorded per session
- ✅ **Test isolation:** pytest fixtures with proper cleanup

**Reliability Gaps:**

**❌ No Retry Logic:**
- Log file corruption → validation halts (no recovery)
- Parquet read errors → session fails (no fallback)
- Transient file system errors → manual intervention required

**❌ No Health Checks:**
- Corrupted log files → misleading comparison results (silent failure)
- Missing log entries → false positives/negatives (no detection)
- Schema mismatches → DataFrame comparison crashes (no validation)

**❌ No Circuit Breakers:**
- Infinite loops in strategy code → hanging sessions (no timeout)
- Long-running comparisons → resource exhaustion (no limits)
- Subprocess hangs → entire validation blocked (no isolation)

**Testing Approach:**

**Recommended Reliability Tests:**

| Test Category | Test Scenarios | Tool | Priority |
|--------------|----------------|------|----------|
| **Error Recovery** | Corrupted JSONL lines, incomplete Parquet writes, concurrent file access | pytest with fault injection | P0 (Critical) |
| **Health Checks** | Missing log files, schema validation failures, null values in critical fields | pytest with invalid data fixtures | P0 (Critical) |
| **Circuit Breakers** | Strategy timeouts (5min), comparison timeouts (2min/layer), session timeouts (30min) | pytest with mock time | P1 (High) |
| **Graceful Degradation** | Partial log availability (layer 1-3 only), missing Backtrader logs (rustybt-only analysis) | pytest with partial data | P2 (Medium) |

**Recommendations:**
1. **Add retry logic** to log parsing and Parquet operations:
   ```python
   @retry(max_attempts=3, backoff_factor=2, exceptions=(IOError, ParquetReadError))
   def parse_log_file(path: Path) -> pl.DataFrame:
       # Parsing logic with automatic retry on failure
   ```

2. **Add health checks** before comparison:
   ```python
   def validate_log_integrity(logs: pl.DataFrame, expected_schema: Schema) -> ValidationResult:
       # Check schema, row counts, critical nulls
       # Return PASS/FAIL with diagnostic details
   ```

3. **Add circuit breakers** for subprocess execution:
   ```python
   @timeout(seconds=300)  # 5 minutes max
   def execute_strategy(strategy: Strategy, data: DataFrame) -> Logs:
       # Kill subprocess if exceeds timeout
   ```

**Gate Criteria:** **CONCERNS** - Core reliability strong, but missing resilience patterns create brittleness

---

### Maintainability: ✅ PASS

**Assessment:** Excellent maintainability foundation with modern tooling and standards.

**Maintainability Strengths:**

**✅ Code Quality Tools:**
- **pytest ≥7.2.0:** Test framework (Architecture pg 25)
- **mypy ≥1.10.0:** Static type checking (Architecture pg 126)
- **ruff ≥0.11.12:** Fast linting (Architecture pg 126)
- **Hypothesis ≥6.0:** Property-based testing (Architecture pg 125)

**✅ Clean Code Practices:**
- **Coverage Target:** ≥80% (standard for production tools)
- **Type Safety:** mypy strict mode (all public APIs typed)
- **Code Style:** ruff enforces PEP 8 compliance

**✅ Observability:**
- **Structured Logging:** JSONL format with layer tags
- **Traceability:** Session metadata with version tracking
- **Audit Trail:** Complete findings database

**Testing Approach:**

**Maintainability Validation (CI Pipeline):**

| Check | Tool | Threshold | Blocker |
|-------|------|-----------|---------|
| **Test Coverage** | pytest-cov | ≥80% | Yes (gate failure if <80%) |
| **Type Safety** | mypy --strict | 0 errors | Yes (gate failure if any errors) |
| **Code Quality** | ruff check | 0 violations | Yes (gate failure if any violations) |
| **Dependency Audit** | pip-audit | 0 critical/high vulnerabilities | Yes (gate failure if critical found) |

**Recommendations:**
1. Configure pytest-cov in CI with 80% threshold:
   ```bash
   pytest --cov=rustybt/validation --cov-fail-under=80
   ```

2. Enable mypy strict mode in CI:
   ```bash
   mypy --strict rustybt/validation/
   ```

3. Run ruff in CI with zero-tolerance:
   ```bash
   ruff check rustybt/validation/ --select=ALL
   ```

**Gate Criteria:** **PASS** - All maintainability tools and standards in place

---

## Testability Concerns and Blockers

### Critical Blocker (MUST RESOLVE)

**TC-001: Decimal Precision Tolerance Validation Missing**

**Category:** TECH (Testing Infrastructure)

**Description:**
While PRD specifies Decimal precision for all financial calculations (pg 176-180) and Architecture includes tolerance configuration (pg 24), there are **no tolerance validation tests** defined in the architecture.

**Impact:**
- **Probability:** 3 (Likely - financial calculations are core to validation)
- **Impact:** 3 (Critical - incorrect tolerances produce false positives/negatives)
- **Risk Score:** **9 (CRITICAL BLOCKER)**

**Evidence:**
- PRD FR68-73: "Tolerances must be configurable per validation layer"
- Architecture pg 24: "YAML config files per validation layer" (configuration exists)
- **Missing:** Tests that validate tolerance thresholds are correct

**Example Failure Scenario:**
```python
# Rustybt calculates: portfolio_value = Decimal("10000.0000001")
# Backtrader calculates: portfolio_value = Decimal("10000.0000002")
# Difference: 0.0000001

# If tolerance = 1e-6 (incorrect):
#   → FAIL (difference exceeds tolerance)
#   → FALSE POSITIVE (this is acceptable floating-point rounding)

# If tolerance = 1e-5 (correct):
#   → PASS (difference within tolerance)
```

**Mitigation Strategy:**

**Owner:** Architect + Dev Team

**Action Plan:**
1. **Add tolerance validation tests to Epic 1 (Story 1.6)** or **Epic 4 (Story 4.X)**:
   - Property-based tests using Hypothesis
   - Test each validation layer's tolerance configuration
   - Verify tolerances handle legitimate precision limits without false positives

2. **Test Structure:**
   ```python
   # tests/validation/test_tolerance_validation.py
   from hypothesis import given, strategies as st
   import polars as pl
   from decimal import Decimal

   @given(
       value1=st.decimals(min_value=0, max_value=1000000, places=10),
       value2=st.decimals(min_value=0, max_value=1000000, places=10)
   )
   def test_portfolio_value_tolerance_handles_precision(value1: Decimal, value2: Decimal):
       """Verify portfolio value tolerance doesn't produce false positives."""
       difference = abs(value1 - value2)

       # Load tolerance from config
       tolerance = load_tolerance("layer_5_portfolio", "portfolio_value")

       # If difference is within machine precision (1e-10), should pass
       if difference <= Decimal("1e-10"):
           assert is_within_tolerance(value1, value2, tolerance)
   ```

3. **Documentation:**
   - Add tolerance selection rationale to Architecture
   - Document tolerance thresholds per layer in test-design-system.md
   - Explain why each threshold was chosen (e.g., "1e-6 for prices accounts for Decimal rounding")

**Timeline:** Before Epic 4 (5-Layer Test Suite) implementation

**Verification:** Property tests pass for all 5 validation layers

**Status:** **DEFERRED to Post-MVP** (User decision: Decimal precision optimization is Post-MVP scope, not MVP blocker)

---

### High-Priority Concerns (SHOULD RESOLVE)

**TC-002: No Resilience Patterns in Log Processing**

**Category:** OPS (Operational Reliability)

**Description:**
Log parsing failures (corrupted JSONL, incomplete Parquet writes) will halt entire validation session with no retry or recovery mechanism.

**Impact:**
- **Probability:** 2 (Possible - file system errors, concurrent access)
- **Impact:** 3 (Critical - brittle validation runs require manual recovery)
- **Risk Score:** **6 (HIGH)**

**Mitigation:**
- Add retry logic with exponential backoff (max 3 attempts)
- Add health checks before comparison (schema validation, row count checks)
- Add circuit breakers for hanging operations (timeout after 5 minutes)

**Owner:** Dev Team

**Timeline:** Epic 1 (Foundation) or Epic 2 (Strategy Comparison)

---

**TC-003: Missing Performance Baselines**

**Category:** PERF (Performance)

**Description:**
No SLOs defined for log parsing, comparison engine, or end-to-end validation time. Can't detect performance regressions during implementation.

**Impact:**
- **Probability:** 2 (Possible - performance could degrade unnoticed)
- **Impact:** 3 (Critical - slow validations block developer productivity)
- **Risk Score:** **6 (HIGH)**

**Mitigation:**
- Establish baselines in Story 2.7 (already planned)
- Define SLO targets (log parsing <5s, comparison <10s/layer, full validation <2min/strategy)
- Add pytest-benchmark tests with regression thresholds (±20%)

**Owner:** Dev Team

**Timeline:** Story 2.7 (Document performance baselines for rust optimization)

---

**TC-004: Investigation Workflow Not Testable**

**Category:** BUS (Business Logic)

**Description:**
Manual investigation workflow (FR41-54) has no automated quality checks. Inconsistent BUG vs DESIGN classifications possible, no audit trail validation.

**Impact:**
- **Probability:** 2 (Possible - human classification errors)
- **Impact:** 2 (Degraded - incorrect classifications confuse future investigations)
- **Risk Score:** **4 (MEDIUM)**

**Mitigation:**
- Add classification validation tests (e.g., "security issues must be BUG, not DESIGN")
- Create classification audit reports (review history of classifications)
- Document classification criteria in investigation guide

**Owner:** QA / Test Architect

**Timeline:** Epic 5 (Investigation & Classification Workflow)

---

## Test Environment Requirements

### Local Development Environment

**Purpose:** Fast iteration during feature development

**Setup:**
- In-memory pytest fixtures (no persistent storage)
- Fast test execution (<30 seconds for unit/integration suite)
- Small datasets (100 OHLCV bars, 1 strategy)

**Tools:**
- pytest with auto-rerun on file changes (pytest-watch)
- Coverage reporting (pytest-cov)
- Type checking on save (mypy --watch)

**Data:**
- Synthetic test data (faker-generated strategy parameters)
- Minimal log files (<1000 lines)
- Single strategy validation (SMA crossover)

---

### CI Pipeline Environment

**Purpose:** Automated regression testing on every commit

**Setup:**
- Full pytest suite with coverage (≥80%)
- Type safety enforcement (mypy strict)
- Code quality checks (ruff)
- Dependency audit (pip-audit)

**Tools:**
- pytest with parallel execution (pytest-xdist)
- Coverage enforcement (pytest-cov --fail-under=80)
- Benchmark regression detection (pytest-benchmark)

**Data:**
- Medium datasets (1000 OHLCV bars, 2 strategies)
- Full 5-layer comparison
- Session lifecycle tests (create → execute → classify → complete)

**CI Job Structure:**
```yaml
test:
  runs-on: ubuntu-latest
  steps:
    - name: Run tests with coverage
      run: pytest --cov=rustybt/validation --cov-fail-under=80

    - name: Type check
      run: mypy --strict rustybt/validation/

    - name: Lint
      run: ruff check rustybt/validation/ --select=ALL

    - name: Security audit
      run: pip-audit
```

---

### Manual Validation Environment

**Purpose:** Full strategy validation before releases

**Setup:**
- Complete dual execution (rustybt + Backtrader)
- Full logging enabled (JSONL + Parquet)
- Full datasets (10K+ OHLCV bars, all 4 MVP strategies)

**Tools:**
- rustybt-validate CLI (complete session workflow)
- Manual investigation workflow (BUG/DESIGN classification)
- Report generation (session reports, findings exports)

**Data:**
- Real market data (historical OHLCV from yfinance/CCXT)
- All 4 MVP strategies (SMA crossover, mean reversion, momentum, multi-factor)
- Multi-session validation (test resumability)

**Manual Validation Checklist:**
- [ ] All 4 strategies execute successfully (rustybt + Backtrader)
- [ ] All 5 validation layers pass comparison
- [ ] Zero unresolved discrepancies (all classified as BUG or DESIGN)
- [ ] Session resumability tested (pause → resume)
- [ ] Reports generated successfully (session report, findings export)

---

## Sprint 0 Recommendations

**Before starting Epic 2 (Strategy Comparison Infrastructure), complete these foundational tasks:**

### 1. Scaffold Test Infrastructure (*framework workflow)

**Action:** Run test framework initialization workflow to set up pytest structure

**Deliverables:**
- pytest configuration with custom markers:
  - `@pytest.mark.layer_1_data` - Data handling tests
  - `@pytest.mark.layer_2_signals` - Signal computation tests
  - `@pytest.mark.layer_3_orders` - Order lifecycle tests
  - `@pytest.mark.layer_4_broker` - Broker transaction tests
  - `@pytest.mark.layer_5_portfolio` - Portfolio returns tests
  - `@pytest.mark.integration` - Cross-layer integration tests
  - `@pytest.mark.e2e` - Full strategy validation tests

- Fixture structure:
  - `conftest.py` with session management fixtures
  - Data loading fixtures (Parquet, JSONL)
  - Strategy factory fixtures

- Test data factories:
  - Log file generators (valid, corrupted, truncated)
  - Strategy parameter generators
  - Session metadata generators

**Verification:** Run `pytest --collect-only` and verify markers are registered

---

### 2. Configure CI Pipeline (*ci workflow)

**Action:** Set up automated CI pipeline with quality gates

**Deliverables:**
- GitHub Actions workflow (or equivalent) with:
  - pytest execution on every commit
  - Coverage reporting (≥80% threshold)
  - Type checking (mypy strict mode)
  - Linting (ruff with zero-tolerance)
  - Dependency audit (pip-audit for vulnerabilities)

- CI quality gates:
  - ❌ FAIL if coverage <80%
  - ❌ FAIL if mypy errors detected
  - ❌ FAIL if ruff violations detected
  - ❌ FAIL if critical/high vulnerabilities found

**Verification:** Trigger CI build and verify all checks pass

---

### 3. Add Resilience Patterns (TC-002 Mitigation)

**Action:** Enhance architecture with retry logic, health checks, and circuit breakers

**Deliverables:**

**Retry Logic:**
```python
# rustybt/validation/resilience.py
from functools import wraps
import time

def retry(max_attempts=3, backoff_factor=2, exceptions=(Exception,)):
    """Retry decorator with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff_factor ** attempt
                    time.sleep(wait_time)
        return wrapper
    return decorator
```

**Health Checks:**
```python
# rustybt/validation/health_checks.py
def validate_log_integrity(log_path: Path) -> HealthCheckResult:
    """Validate JSONL log file integrity before comparison."""
    # Check file exists and is readable
    # Validate JSONL schema (all required fields present)
    # Check for truncated lines
    # Verify row count > 0
    # Return PASS/FAIL with diagnostics
```

**Circuit Breakers:**
```python
# rustybt/validation/timeouts.py
import signal

def timeout(seconds):
    """Timeout decorator for subprocess execution."""
    def decorator(func):
        def handler(signum, frame):
            raise TimeoutError(f"Function exceeded {seconds}s timeout")

        @wraps(func)
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)  # Cancel alarm
            return result
        return wrapper
    return decorator
```

**Verification:** Add tests for retry logic, health checks, and timeouts

---

### 4. Establish Performance Baselines (Story 2.7)

**Action:** Define SLO targets and create benchmarking suite

**Deliverables:**

**SLO Targets:**
| Operation | Target SLO | Measurement |
|-----------|-----------|-------------|
| Log parsing | <5s for 10K lines | pytest-benchmark |
| Comparison engine | <10s per layer | pytest-benchmark |
| Full strategy validation | <2min per strategy | End-to-end timing |
| Session overhead | <5s for CRUD | pytest-benchmark |

**Benchmarking Suite:**
```python
# tests/benchmarks/test_performance.py
import pytest
from rustybt.validation import log_parser, comparators

def test_log_parsing_performance(benchmark):
    """Benchmark JSONL parsing for 10K log lines."""
    log_file = generate_test_logs(num_lines=10000)

    result = benchmark(log_parser.parse_jsonl, log_file)

    # Verify SLO: <5 seconds
    assert benchmark.stats['mean'] < 5.0

@pytest.mark.parametrize("layer", ["data", "signals", "orders", "broker", "portfolio"])
def test_comparison_performance(benchmark, layer):
    """Benchmark layer comparison for typical dataset."""
    rustybt_logs = load_fixture(f"rustybt_{layer}_1000rows.parquet")
    backtrader_logs = load_fixture(f"backtrader_{layer}_1000rows.parquet")

    result = benchmark(comparators.compare_layer, rustybt_logs, backtrader_logs, layer)

    # Verify SLO: <10 seconds per layer
    assert benchmark.stats['mean'] < 10.0
```

**CI Integration:**
```yaml
benchmark:
  runs-on: ubuntu-latest
  steps:
    - name: Run benchmarks
      run: pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmark-results.json

    - name: Check regression
      run: |
        python scripts/check_benchmark_regression.py \
          --current=benchmark-results.json \
          --baseline=baseline-benchmarks.json \
          --threshold=20  # Fail if >20% slower
```

**Verification:** Run benchmarks and establish baseline values

---

## Quality Gate Criteria

**Before proceeding to Implementation-Readiness Gate Check:**

### Critical (MUST PASS):
- [x] **TC-001 DEFERRED:** Decimal precision tolerance validation deferred to Post-MVP (user scope decision)
- [ ] **ASR-002 TESTED:** Temporal integrity tests prove no lookahead bias detection

### High-Priority (SHOULD PASS):
- [ ] **TC-002 MITIGATED:** Retry logic, health checks, and circuit breakers implemented
- [ ] **TC-003 MITIGATED:** Performance SLOs defined and baseline benchmarks established
- [ ] **TC-004 ADDRESSED:** Investigation workflow validation tests planned for Epic 5

### Maintainability (MUST PASS):
- [ ] **Test coverage:** ≥80% for rustybt/validation/ module
- [ ] **Type safety:** mypy --strict passes with 0 errors
- [ ] **Code quality:** ruff check passes with 0 violations
- [ ] **Security:** pip-audit shows 0 critical/high vulnerabilities

### Test Levels (MUST PASS):
- [ ] **Unit tests:** 40% of test suite (comparators, parsers, models)
- [ ] **Integration tests:** 30% of test suite (layer comparisons, session lifecycle)
- [ ] **E2E tests:** 30% of test suite (full strategy validation)

---

## Approval

**Test Design Ready for Implementation-Readiness Gate Check:**

- [ ] Architect: Approve testability assessment and ASR risk scores
- [ ] Tech Lead: Approve test levels strategy and Sprint 0 recommendations
- [ ] QA Lead: Approve NFR testing approach and quality gate criteria

**Comments:**

_Pending TC-001 resolution (decimal tolerance tests) before final approval._

---

## Appendix

### Knowledge Base References

- `nfr-criteria.md` - NFR validation approach (security, performance, reliability, maintainability)
- `test-levels-framework.md` - Test level selection guidance (unit vs integration vs E2E)
- `risk-governance.md` - Testability risk identification and scoring methodology
- `test-quality.md` - Quality standards and Definition of Done

### Related Documents

- **PRD:** docs/prd.md (73 functional requirements, 33 NFRs)
- **Architecture:** docs/architecture.md (dual-location validation framework, log-based comparison)
- **Epics:** docs/epics.md (7 epics, 51 stories breakdown)

### Testability Concern Tracking

| ID | Title | Category | Score | Status | Owner |
|----|-------|----------|-------|--------|-------|
| TC-001 | Decimal precision tolerance validation missing | TECH | 9 | OPEN | Architect |
| TC-002 | No resilience patterns in log processing | OPS | 6 | OPEN | Dev Team |
| TC-003 | Missing performance baselines | PERF | 6 | OPEN | Dev Team |
| TC-004 | Investigation workflow not testable | BUS | 4 | OPEN | QA Lead |

---

**Generated by**: BMad TEA Agent - Test Architect Module (Murat)
**Workflow**: `.bmad/bmm/testarch/test-design`
**Mode**: System-Level (Phase 3 - Testability Review)
**Version**: 4.0 (BMad v6)
