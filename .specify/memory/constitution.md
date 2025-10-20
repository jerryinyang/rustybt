<!--
# Sync Impact Report

**Version Change**: 0.0.0 → 1.0.0 (MAJOR - Initial constitution establishment)

**Modified Principles**:
- N/A (initial version)

**Added Sections**:
1. Core Principles (7 principles)
2. Development Workflow Standards
3. Quality Gates and Enforcement
4. Governance

**Removed Sections**:
- N/A (initial version)

**Templates Requiring Updates**:
- ✅ `.specify/templates/plan-template.md` - Updated with explicit checks for all 7 principles in Constitution Check section
- ✅ `.specify/templates/spec-template.md` - Added Constitutional Requirements section (CR-001 through CR-007) mapping all 7 principles
- ✅ `.specify/templates/tasks-template.md` - Added Phase FINAL: Constitution Compliance Verification with explicit verification steps for all 7 principles
- ✅ `.claude/commands/speckit.implement.md` - Added step 3: Constitution Compliance Check (MANDATORY) before implementation, updated all subsequent step numbers

**Follow-up TODOs**:
- None - all placeholders filled with concrete values

**Ratification Details**:
- Constitution established for RustyBT project
- All principles derived from existing coding standards, zero-mock enforcement, and sprint-debug guidelines
- Version 1.0.0 marks formal adoption of project governance standards

-->

# RustyBT Constitution

## Core Principles

### I. Decimal Financial Computing

**All financial calculations MUST use Python's `Decimal` type for audit-compliant precision.**

**Non-Negotiable Rules**:
- NEVER use `float` or `float64` for monetary values, prices, quantities, or financial calculations
- ALL portfolio accounting (cash, positions, P&L, returns) MUST use `Decimal` with configurable precision (default: 28 digits)
- String construction REQUIRED: `Decimal("42.123")` - NEVER `Decimal(42.123)` to avoid float rounding
- ALL OHLCV data columns MUST be stored as `pl.Decimal(precision=18, scale=8)` in Parquet format
- Commission, slippage, and transaction cost calculations MUST preserve Decimal precision
- Comparison operations MUST use Decimal comparison directly - NEVER convert to float
- Set context precision explicitly: `getcontext().prec = 28` (or asset-class-specific precision)

**Rationale**: Financial-grade arithmetic with zero rounding errors is mandatory for audit compliance, regulatory requirements, and production trading systems. Float64 precision causes compounding errors in portfolio accounting that are unacceptable for real money.

**Property-Based Validation**:
- Portfolio value = cash + sum(position values) - MUST be exact (Hypothesis property test)
- Commission NEVER exceeds order value
- Decimal sum associativity preserved (sum order doesn't affect result)
- 1000+ examples per property test to ensure robustness

---

### II. Zero-Mock Enforcement (NON-NEGOTIABLE)

**The Five Absolutes - NEVER**:
1. **NEVER** return hardcoded values in production code (e.g., `return 1.5  # Mock value`)
2. **NEVER** write validation that always succeeds (e.g., `def validate(data): return True`)
3. **NEVER** simulate when you should calculate (e.g., fake Sharpe ratio instead of computing from returns)
4. **NEVER** stub when you should implement (e.g., empty `pass` in production code)
5. **NEVER** claim completion for incomplete work
6. **NEVER** simplify a test to avoid an error

**Pre-Commit Checklist (BLOCKING)**:
- ❌ No TODO/FIXME/HACK comments without issue tracking
- ❌ No hardcoded return values in production code
- ❌ No empty `except` blocks or `pass` statements in production code
- ❌ No "mock", "fake", "stub", "dummy" in variable/function names
- ❌ No simplified implementations without explicit SIMPLIFIED warning blocks
- ✅ ALL tests exercise real functionality, not mocks
- ✅ ALL validations perform actual checks with real logic

**CI/CD Enforcement (MANDATORY)**:
- `scripts/detect_mocks.py --strict` MUST return 0 violations (blocking)
- `scripts/detect_hardcoded_values.py --fail-on-found` MUST pass (blocking)
- `scripts/verify_validations.py --ensure-real-checks` MUST pass (blocking)
- `pytest tests/ --unique-results-check` ensures different inputs produce different outputs (blocking)

**Forbidden Patterns**:
```python
# ❌ ABSOLUTELY FORBIDDEN
def calculate_sharpe_ratio(returns):
    return 1.5  # Mock value - NEVER DO THIS

def validate_data(data):
    return True  # Always passes - NEVER DO THIS

try:
    risky_operation()
except:
    pass  # Silently swallows errors - NEVER DO THIS
```

**Rationale**: Every mock is technical debt. Every stub is a lie to users. Every placeholder is a broken promise. We build real software that does real things. Mock code creates false confidence and hides implementation gaps that cause production failures.

**Consequences**:
- First Violation: Mandatory code review training + all code requires senior review for 2 weeks
- Second Violation: Removed from critical path stories
- Third Violation: Removed from project development team

---

### III. Strategy Reusability Guarantee

**ANY strategy written for RustyBT's backtest engine MUST run in live/paper trading mode WITHOUT ANY CODE CHANGES.**

**Non-Negotiable Rules**:
- Same `TradingAlgorithm` class MUST execute identically in backtest, paper trading, and live trading modes
- `initialize()` and `handle_data()` methods MUST have identical behavior across all execution modes
- `context` API MUST provide identical interface in all modes (portfolio, cash, positions)
- `data` API MUST provide identical interface in all modes (current(), history(), can_trade())
- ALL data access returns Polars DataFrames with Decimal columns consistently
- Optional live hooks (`on_order_fill`, `on_order_cancel`, `on_order_reject`) MUST NOT be required - strategy works without them
- Paper trading MUST match backtest results within 0.1% for same historical data (>99% correlation)
- Shadow trading validation MUST run in parallel to detect execution divergence

**Rationale**: Write once, test in backtest, validate in paper trading, deploy to live with ZERO code risk. Eliminates "backtest version" vs. "live version" maintenance burden. Ensures confidence that backtested strategy behavior matches live execution. Forces investigation of execution differences, not code differences.

**Validation Requirements**:
- Story 6.7 AC9: Tests validate paper trading matches backtest for same data
- Story 6.7 AC10: Example demonstrates >99% correlation
- Shadow trading framework detects signal divergence and trips circuit breaker if alignment <95%

---

### IV. Type Safety Excellence

**100% type hint coverage for public APIs with `mypy --strict` enforcement in CI/CD.**

**Non-Negotiable Rules**:
- Python 3.12+ REQUIRED (structural pattern matching, enhanced type hints, modern features)
- ALL public functions, methods, and classes MUST have complete type hints
- `mypy --strict` compliance REQUIRED in CI/CD (blocking)
- Use `typing` module for complex types: `List`, `Dict`, `Optional`, `Union`, `Callable`, `Decimal`
- Google-style docstrings REQUIRED for all public APIs with Args, Returns, Raises sections
- No implicit `None` returns - use explicit `Optional[T]` types
- Frozen dataclasses preferred for immutability: `@dataclass(frozen=True)`
- Functions MUST NOT mutate input arguments

**Code Formatting (MANDATORY)**:
- `black` for code formatting (line length: 100, target Python 3.12)
- `ruff` for linting (replaces flake8, isort, pyupgrade) - configured with E, F, W, I, N, UP, ANN, B, A, C4, DTZ, T20, SIM
- Maximum cyclomatic complexity: 10 per function (enforced by ruff)
- Maximum function length: 50 lines
- Maximum file length: 500 lines

**Naming Conventions**:
- Classes: `PascalCase` (e.g., `DecimalLedger`, `PolarsDataPortal`)
- Functions/methods: `snake_case` (e.g., `calculate_returns`, `fetch_ohlcv`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_LEVERAGE`, `DEFAULT_PRECISION`)
- Private members: prefix with `_` (e.g., `_internal_state`, `_validate_order`)

**Rationale**: Type safety prevents entire classes of runtime errors, improves IDE tooling, and serves as executable documentation. Python 3.12+ features (structural pattern matching, improved type hints) enable more expressive, maintainable code.

---

### V. Test-Driven Development

**90%+ test coverage with real implementations, no mocks of production code.**

**Test Coverage Targets (MANDATORY)**:
- Overall coverage: ≥90% (maintain/improve from Zipline's 88.26%)
- Financial modules: ≥95% (critical for correctness)
- New components: ≥90% (strict enforcement)

**Test Pyramid**:
- **Unit Tests (70%)**: Fast, isolated tests for individual functions/classes (~5 seconds total on every commit)
- **Integration Tests (25%)**: Test component interactions (e.g., LiveTradingEngine + BrokerAdapter) (~2 minutes on PRs)
- **End-to-End Tests (5%)**: Complete workflows (backtest, optimization, live trading) (~10 minutes nightly)

**Property-Based Testing (Hypothesis - MANDATORY for Financial Code)**:
- 1000+ examples per property test
- Portfolio value invariant: `portfolio_value = cash + sum(positions)`
- Commission bounded: `0 <= commission <= order_value`
- Decimal precision preservation: sum order doesn't affect result
- Temporal isolation: no strategy has access to future data

**Test Organization**:
- Mirror source structure: `tests/finance/test_decimal_ledger.py` → `rustybt/finance/decimal/ledger.py`
- Test file naming: `test_<module>.py`
- Test function naming: `test_<function_name>_<scenario>`

**Rationale**: High test coverage with real implementations (not mocks) ensures correctness, prevents regressions, and provides confidence for refactoring. Property-based testing validates invariants that traditional example-based tests miss.

**Performance Benchmarks (MANDATORY)**:
- Track execution time for standard backtest scenarios
- Fail CI if performance degrades >10%
- Store benchmark results in CI artifacts for trend analysis

---

### VI. Modern Data Architecture

**Polars + Parquet for 5-10x performance improvement over pandas + HDF5.**

**Non-Negotiable Rules**:
- Polars REQUIRED as primary DataFrame library (pandas compatibility layer optional)
- Parquet REQUIRED for all OHLCV storage (columnar format, 50-80% smaller than HDF5)
- Standard schema for ALL data: `{timestamp: pl.Datetime("us"), symbol: pl.Utf8, open/high/low/close/volume: pl.Decimal(18, 8)}`
- Lazy evaluation REQUIRED for large datasets: use `scan_parquet()` instead of `read_parquet()`
- Partition strategy: daily bars by (year, month), minute bars by (year, month, day)
- Data validation REQUIRED: OHLCV relationships (high >= max(open, close), low <= min(open, close))
- Outlier detection: flag price changes >3 standard deviations
- Temporal consistency: timestamps sorted, no duplicates, no NULL in required fields

**Data Adapter Framework (BaseDataAdapter)**:
- ALL data sources MUST implement `BaseDataAdapter` interface
- `fetch()` returns Polars DataFrame with Decimal columns
- `validate()` checks OHLCV relationships and data quality
- `standardize()` converts provider-specific format to RustyBT standard schema
- Supported adapters: CCXT (100+ crypto exchanges), yfinance (stocks/ETFs/forex), CSV (custom data)
- Caching with checksum validation REQUIRED

**Rationale**: Polars provides 5-10x faster data processing with lazy evaluation and efficient memory usage. Parquet is industry-standard columnar format with better compression, interoperability (Spark, DuckDB, countless tools), and active ecosystem vs. unmaintained bcolz.

---

### VII. Sprint Debug Discipline

**Systematic issue resolution with mandatory pre-flight checklists and verification gates.**

**Mandatory Pre-Flight Checklist (BEFORE ANY FIX BATCH)**:

**For Documentation Updates**:
- [ ] Verify content exists in source code (use `inspect.signature()` to verify API)
- [ ] Test ALL code examples (run them, don't assume they work)
- [ ] Verify ALL API signatures match source (no fabricated parameters)
- [ ] Ensure realistic data (no "foo", "bar" placeholders in examples)
- [ ] Read quality standards (coding-standards.md, zero-mock-enforcement.md)
- [ ] Prepare testing environment (venv, dependencies installed)

**For Framework Code Updates**:
- [ ] Understand code to be modified (read existing implementation first)
- [ ] Review coding standards & zero-mock enforcement (no shortcuts)
- [ ] Plan testing strategy (NO MOCKS - real implementations only)
- [ ] Ensure complete type hints (mypy --strict compliance)
- [ ] Verify testing environment works (pytest runs successfully)
- [ ] Complete impact analysis (what else might this change affect?)

**Fix Documentation (REQUIRED in `docs/internal/sprint-debug/fixes/active-session.md`)**:
```markdown
## [YYYY-MM-DD HH:MM:SS] - Batch Description

**Focus Area:** [Framework/Documentation/Tests/etc.]

**Issues Found:**
1. Issue description and location

**Fixes Applied:**
1. Fix description and files modified

**Tests Added/Modified:**
- List of test files changed

**Verification:**
- [ ] Pre-flight checklist completed
- [ ] Tests pass (pytest tests/ -v)
- [ ] Linting passes (ruff check rustybt/)
- [ ] Type checking passes (mypy rustybt/ --strict)
- [ ] Documentation builds (mkdocs build --strict)
- [ ] No regressions introduced

**Files Modified:**
- `path/to/file1.py`

**Commit Hash:** [filled after commit]
```

**Rationale**: Systematic debugging prevents recurring issues, ensures quality, and provides audit trail. Pre-flight checklists catch common mistakes before they become production problems. Documentation of fixes enables knowledge transfer and pattern recognition.

**Critical Discovery Pattern** (from sprint-debug history):
- ALWAYS use `inspect.signature()` to verify API before documenting
- NEVER fabricate function parameters or assume API based on similar functions
- Example: `algorithm_class` parameter was fabricated and never existed in `run_algorithm()` - caught by this discipline

---

## Development Workflow Standards

### Code Review Requirements (MANDATORY)

**All PRs require 2 approvals**:
1. One from senior developer
2. One from financial domain expert (for `finance/` modules)

**PR Checklist (GitHub Actions enforced)**:
- [ ] All tests pass (90%+ coverage)
- [ ] Mock detection returns 0 violations (`scripts/detect_mocks.py`)
- [ ] Performance benchmarks pass (no >10% degradation)
- [ ] Documentation updated (if public API changed)
- [ ] CHANGELOG.md entry added
- [ ] `mypy --strict` passes
- [ ] `ruff check` passes
- [ ] `black --check` passes

### Commit Standards

**Git Commit Message Format**:
```
<type>(scope): <brief description>

- Detailed change 1
- Detailed change 2

Refs: docs/internal/sprint-debug/fixes/[timestamp] (if sprint-debug fix)
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `build`, `ci`

**Breaking Changes**:
- MUST be documented prominently in commit message with `BREAKING CHANGE:` footer
- MUST increment MAJOR version (MAJOR.MINOR.PATCH)
- MUST update migration guide in `docs/`

### Documentation Requirements

**Public API Documentation (MANDATORY)**:
- 100% docstring coverage for public APIs
- Google-style docstrings with Args, Returns, Raises, Example sections
- Sphinx-compatible reStructuredText format
- Include runnable examples in docstrings

**Architecture Decision Records (ADRs)**:
- Required for non-obvious decisions in `docs/internal/architecture/`
- Template: Status, Context, Decision, Consequences (pros/cons)
- Example: "ADR-001: Use Decimal for Financial Calculations"

---

## Quality Gates and Enforcement

### CI/CD Pipeline (GitHub Actions)

**Matrix Testing (BLOCKING)**:
- OS: ubuntu-latest, macos-latest, windows-latest
- Python: 3.12, 3.13

**Quality Checks (ALL BLOCKING)**:
1. **Tests**: `pytest -v --cov=rustybt --cov-report=xml --cov-report=term` (90%+ coverage required)
2. **Type Check**: `mypy --strict rustybt` (zero errors allowed)
3. **Lint**: `ruff check rustybt` (zero violations allowed)
4. **Format**: `black --check rustybt` (must pass)
5. **Zero-Mock Enforcement**: `scripts/detect_mocks.py --strict` (zero violations allowed)
6. **Hardcoded Values**: `scripts/detect_hardcoded_values.py --fail-on-found` (zero violations allowed)
7. **Validation Functions**: `scripts/verify_validations.py --ensure-real-checks` (must pass)
8. **Coverage Upload**: `codecov/codecov-action@v3` (track trends, block if <90%)

### Pre-Commit Hooks (AUTOMATIC)

Installed via `.pre-commit-config.yaml`:
- `black` (code formatting, Python 3.12)
- `ruff` (linting)
- `mypy` (type checking with types-all)
- Custom hooks: `scripts/detect_mocks.py --quick`, `scripts/check_error_handling.py`

**Override Discouraged**: `git commit --no-verify` should be rare and justified

### Security Guardrails

**Secrets Detection**:
- `truffleHog` and `detect-secrets` in CI/CD (blocking)
- ALL API keys MUST be in environment variables, NEVER hardcoded
- SQL queries MUST use parameterized statements (SQLAlchemy ORM)
- Input sanitization for ALL external data (Pydantic validation)

**Dependency Management**:
- Pin exact versions in `pyproject.toml` (reproducible builds)
- Weekly `pip-audit` security scan in CI/CD (blocking on HIGH/CRITICAL)
- Quarterly dependency update review
- Apache 2.0/MIT-only dependency policy (no GPL)
- Known LGPL exceptions: `frozendict` (via yfinance), `chardet` (via tox) - tracked for replacement

---

## Governance

### Constitution Authority

**This constitution supersedes all other practices, guidelines, and documentation.** In cases of conflict, constitution principles take precedence.

### Amendment Procedure

**Constitution amendments require**:
1. Written proposal with justification and impact analysis
2. Review by project architect and senior developers
3. Approval by project maintainers (majority vote)
4. Migration plan for affected code (if breaking change)
5. Version bump following semantic versioning:
   - **MAJOR**: Backward incompatible governance/principle removals or redefinitions
   - **MINOR**: New principle/section added or materially expanded guidance
   - **PATCH**: Clarifications, wording, typo fixes, non-semantic refinements

### Compliance Review

**Quarterly compliance audits** to verify:
- All code adheres to constitution principles
- CI/CD enforcement working correctly
- No systematic violations or workarounds
- Documentation reflects current practices
- Metrics tracked: mock detection violations, test coverage trends, type hint coverage, security vulnerabilities

### Complexity Justification

**Any practice violating constitution principles MUST be justified** in writing with:
- Specific technical reason (what problem does it solve?)
- Why simpler alternatives were rejected
- Mitigation plan (how to minimize impact)
- Sunset plan (when will violation be removed?)
- Approval from project architect

**Examples requiring justification**:
- Using `float` instead of `Decimal` (violates Principle I)
- Reducing test coverage below 90% (violates Principle V)
- Using mocks in tests (violates Principle II)
- Breaking strategy reusability (violates Principle III)

### Runtime Development Guidance

**For active development and implementation guidance**, refer to:
- `docs/internal/architecture/coding-standards.md` - Detailed coding standards
- `docs/internal/architecture/zero-mock-enforcement.md` - Zero-mock implementation details
- `docs/internal/sprint-debug/README.md` - Sprint debugging workflow and checklists
- `docs/internal/architecture/strategy-reusability-guarantee.md` - Strategy API contract
- `docs/internal/architecture/testing-strategy.md` - Comprehensive testing guidance

**Version**: 1.0.0 | **Ratified**: 2025-10-20 | **Last Amended**: 2025-10-20
