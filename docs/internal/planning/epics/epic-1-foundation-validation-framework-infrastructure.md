# Epic 1: Foundation - Validation Framework Infrastructure

**Goal:** Establish the dual-location validation architecture (`rustybt/validation/` + `tests/validation/`) with core infrastructure that enables all validation work.

**Architecture References:**
- Project Structure (Architecture pg 33-93)
- Technology Stack (Architecture pg 115-144)
- Development Environment (Architecture pg 541-575)

**Value:** Framework ready for validation development with proper structure, dependencies, and foundational code.

---

## Story 1.1: Initialize Validation Framework Directory Structure

As a developer,
I want the dual-location validation architecture created,
So that validation code is properly organized between library and test locations.

**Acceptance Criteria:**

**Given** the rustybt repository with existing structure
**When** validation framework initialization is executed
**Then** the following directories are created:

- `rustybt/validation/` (library location)
  - `__init__.py` (module initialization)
  - Empty placeholders for: `base_strategy.py`, `session.py`, `log_parser.py`, `comparators.py`, `models.py`, `reporting.py`, `cli.py`

**And** test directories are created:
- `tests/validation/` (test location)
  - `__init__.py`
  - `conftest.py` (pytest fixtures)
  - `strategies/` (dual implementations)
    - `rustybt/` (rustybt strategies)
    - `backtrader/` (backtrader strategies)
  - `fixtures/` (test data)
  - `config/` (tolerance configurations)

**And** session storage directory is created:
- `validation-sessions/` (gitignored, for local execution)

**And** documentation structure is created:
- `docs/validation/` (validation framework docs)

**Prerequisites:** None (first story)

**Technical Notes:**
- Use `mkdir -p` or Python pathlib for directory creation
- Add `validation-sessions/` to `.gitignore`
- Create `__init__.py` files to make packages importable
- Follow Architecture Project Structure (pg 33-93)

---

## Story 1.2: Configure Validation Framework Dependencies

As a developer,
I want validation-specific dependencies installed,
So that the validation framework has all required libraries.

**Acceptance Criteria:**

**Given** the rustybt `pyproject.toml` file
**When** validation dependencies are configured
**Then** the following dependencies are added to a new `[project.optional-dependencies]` section:

```toml
[project.optional-dependencies]
validation = [
    "backtrader>=1.9.78",  # Reference framework
    "click>=8.0",          # CLI interface
    "pyyaml>=6.0",         # Session/config storage
]
```

**And** development dependencies already include (verify):
- `pytest>=7.2.0`
- `polars>=1.0`
- `hypothesis>=6.0`

**And** a new CLI entry point is registered:
```toml
[project.scripts]
rustybt-validate = "rustybt.validation.cli:main"
```

**And** installation succeeds:
```bash
pip install -e ".[validation]"
```

**And** CLI is accessible:
```bash
rustybt-validate --version  # Returns version number
```

**Prerequisites:** Story 1.1 (directory structure exists)

**Technical Notes:**
- Use optional dependencies group to avoid bloating core installation
- Reference Architecture Technology Stack (pg 115-144)
- Backtrader can coexist with rustybt in same environment (subprocess isolation prevents conflicts)
- Click CLI framework chosen per Architecture Decision (pg 428)

---

## Story 1.3: Implement Core Data Models

As a developer,
I want foundational data models defined,
So that validation code has strongly-typed structures.

**Acceptance Criteria:**

**Given** the `rustybt/validation/models.py` module
**When** core models are implemented
**Then** the following data models are defined using `@dataclass`:

**Session Model:**
```python
@dataclass
class Session:
    id: str                          # Format: {YYYYMMDD}-{HHMMSS}-{strategy_name}
    created_at: datetime
    strategy_name: str
    rustybt_version: str
    backtrader_version: str
    python_version: str
    status: Literal["IN_PROGRESS", "COMPLETED", "FAILED"]
    data_fixture: Path
    findings: list[Finding] = field(default_factory=list)
```

**Finding Model:**
```python
@dataclass
class Finding:
    id: str                          # Format: FIND-001, FIND-002, etc.
    layer: Literal["data", "signals", "orders", "broker", "portfolio"]
    description: str
    classification: Optional[Literal["BUG", "DESIGN"]] = None
    rationale: Optional[str] = None
    investigated_by: Optional[str] = None
    investigated_at: Optional[datetime] = None
    resolved: bool = False
    rustybt_value: Any = None
    backtrader_value: Any = None
```

**Discrepancy Model:**
```python
@dataclass
class Discrepancy:
    layer: str
    event: str
    timestamp: datetime
    asset: Optional[str]
    field: str
    rustybt_value: Any
    backtrader_value: Any
    tolerance: Any
    exceeded_by: Any
```

**And** models include type hints for all fields
**And** models use Python 3.12+ syntax
**And** models are exported in `rustybt/validation/__init__.py`

**Prerequisites:** Story 1.1 (directory structure), Story 1.2 (dependencies)

**Technical Notes:**
- Reference Architecture Data Models (pg 359-402)
- Use `from typing import Literal, Optional, Any` for type hints
- Use `from dataclasses import dataclass, field` for dataclasses
- Use `pathlib.Path` for file paths
- Models follow rustybt coding standards (type hints, docstrings)

---

## Story 1.4: Create Test Data Fixture Generator

As a developer,
I want a tool to generate standardized test data,
So that validation strategies execute with identical, reproducible data.

**Acceptance Criteria:**

**Given** a test data generation script
**When** fixture generator is executed
**Then** a Parquet file is created at `tests/validation/fixtures/validation_data.parquet`

**And** the data contains:
- 50 assets (mix of stocks with realistic symbols: AAPL, GOOGL, MSFT, etc.)
- Date range: 2020-01-01 to 2021-12-31 (2 years of daily OHLCV data)
- Columns: timestamp, asset, open, high, low, close, volume
- All prices use Decimal precision (NFR1: financial accuracy)
- Deterministic generation (seed=42 for reproducibility)
- Realistic price movements (use random walk with drift)
- Volume ranges appropriate for each asset tier (large-cap vs small-cap)

**And** generation is invocable via CLI:
```bash
python -m rustybt.validation.generate_fixture \
    --output tests/validation/fixtures/validation_data.parquet \
    --assets 50 \
    --start 2020-01-01 \
    --end 2021-12-31 \
    --seed 42
```

**And** fixture file size is reasonable (<100MB)
**And** fixture loads successfully in both rustybt and Backtrader

**Prerequisites:** Story 1.2 (dependencies including Polars)

**Technical Notes:**
- Create `rustybt/validation/generate_fixture.py` with CLI via `if __name__ == "__main__"`
- Use `numpy.random.seed(42)` for deterministic generation
- Use Polars to write Parquet (leverage existing rustybt infrastructure)
- Reference Architecture Data Flow (pg 406-429)
- Price generation: Start at realistic base (e.g., $100), apply random walk with 0.05% drift, 1.5% daily volatility
- Volume generation: Scale by market cap tier (large-cap: 1M-10M, mid-cap: 100K-1M, small-cap: 10K-100K)

---

## Story 1.5: Implement Basic Session Manager

As a developer,
I want a SessionManager class to handle session lifecycle,
So that validation sessions can be created, stored, and loaded.

**Acceptance Criteria:**

**Given** the `rustybt/validation/session.py` module
**When** SessionManager is implemented
**Then** it provides these methods:

**create() method:**
```python
@staticmethod
def create(strategy_name: str, data_fixture: Path) -> Session:
    """Create new validation session with unique ID."""
    # Generate session ID: {YYYYMMDD}-{HHMMSS}-{strategy_name}
    # Capture framework versions (rustybt, backtrader, python)
    # Create session directory: validation-sessions/{session_id}/
    # Create session.yaml with metadata
    # Return Session object
```

**save() method:**
```python
def save(session: Session) -> None:
    """Save session state to YAML."""
    # Write to validation-sessions/{session_id}/session.yaml
    # Preserve all fields
    # Human-readable YAML format
```

**load() method:**
```python
@staticmethod
def load(session_id: str) -> Session:
    """Load session from YAML."""
    # Read from validation-sessions/{session_id}/session.yaml
    # Parse YAML to Session object
    # Validate session data
    # Return Session object
```

**list_sessions() method:**
```python
@staticmethod
def list_sessions(status: Optional[str] = None) -> list[Session]:
    """List all sessions, optionally filtered by status."""
    # Scan validation-sessions/ directory
    # Load each session.yaml
    # Filter by status if provided
    # Return list of Session objects
```

**And** session directories include subdirectories:
- `logs/` (for JSONL and Parquet logs)
- `analysis/` (for layer reports)

**And** proper error handling for missing/corrupt session files

**Prerequisites:** Story 1.3 (Session model defined)

**Technical Notes:**
- Use PyYAML for YAML serialization
- Use `importlib.metadata.version()` to capture framework versions
- Session ID format: `20251123-230000-sma_crossover`
- Reference Architecture Session Storage (pg 23, ADR-003)
- Validate session.yaml schema on load (detect corrupt files)

---

## Story 1.6: Create Basic CLI Structure

As a developer,
I want a Click-based CLI with foundational commands,
So that developers can interact with the validation framework.

**Acceptance Criteria:**

**Given** the `rustybt/validation/cli.py` module
**When** CLI is implemented
**Then** the following command structure exists:

```bash
rustybt-validate --version          # Show version
rustybt-validate --help             # Show all commands

rustybt-validate session create --strategy <name> --data <path>
rustybt-validate session list [--status <status>]
rustybt-validate session show <session_id>
```

**And** `session create` command:
- Validates strategy name (non-empty string)
- Validates data fixture exists
- Calls SessionManager.create()
- Prints session ID and summary

**And** `session list` command:
- Calls SessionManager.list_sessions()
- Displays table: Session ID | Strategy | Status | Created At
- Filters by status if --status provided
- Shows "(no sessions)" if empty

**And** `session show` command:
- Loads session by ID
- Displays full session details (all metadata fields)
- Shows count of findings
- Shows session directory path

**And** all commands have proper help text
**And** CLI uses Click decorators for arguments/options
**And** CLI provides clear error messages for invalid inputs

**Prerequisites:** Story 1.5 (SessionManager implemented)

**Technical Notes:**
- Use Click command groups: `@click.group()`
- Use Click options: `@click.option()` for flags
- Use Click arguments: `@click.argument()` for required params
- Reference Architecture CLI Interface (pg 435-452)
- Entry point registered in pyproject.toml (Story 1.2)
- Color output using Click.style() for better UX (green for success, red for errors)

---

## Story 1.7: Add Development Setup Documentation

As a developer,
I want clear setup instructions,
So that I can quickly configure the validation framework.

**Acceptance Criteria:**

**Given** the `docs/validation/getting-started.md` file
**When** documentation is written
**Then** it includes:

**Prerequisites section:**
- Python 3.12+ requirement
- rustybt development environment setup reference
- Link to main contributing docs

**Installation section:**
```bash
# Install validation framework dependencies
pip install -e ".[validation]"

# Verify installation
rustybt-validate --version
pytest tests/validation/ --collect-only  # Should show 0 tests initially
```

**Setup section:**
```bash
# Generate test data fixture
python -m rustybt.validation.generate_fixture \
    --output tests/validation/fixtures/validation_data.parquet \
    --assets 50 \
    --start 2020-01-01 \
    --end 2021-12-31 \
    --seed 42
```

**Quick start section:**
```bash
# Create validation session
rustybt-validate session create --strategy example --data tests/validation/fixtures/validation_data.parquet

# View sessions
rustybt-validate session list
```

**Troubleshooting section:**
- Common setup issues
- Version conflicts between rustybt and Backtrader
- Path issues with validation-sessions/ directory

**And** documentation uses clear, step-by-step format
**And** all commands are copy-pasteable
**And** examples show expected output

**Prerequisites:** Stories 1.1-1.6 (all foundation stories complete)

**Technical Notes:**
- Use markdown with code blocks (triple backticks with language identifiers)
- Include links to Architecture document for deeper dive
- Reference Architecture Development Environment (pg 541-575)
- Keep getting-started focused on MVP workflow (defer advanced topics)

---

## Story 1.8: Implement Resilience Patterns

As a developer,
I want resilience patterns implemented for error recovery,
So that the validation framework handles failures gracefully without manual intervention.

**Acceptance Criteria:**

**Given** the `rustybt/validation/` module
**When** resilience infrastructure is implemented
**Then** the following components are created:

**Retry Logic Module (`rustybt/validation/resilience.py`):**
```python
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

**Health Check Module (`rustybt/validation/health_checks.py`):**
```python
def validate_log_integrity(log_path: Path) -> HealthCheckResult:
    """Validate JSONL log file integrity before comparison."""
    # Check file exists and is readable
    # Validate JSONL schema (all required fields present)
    # Check for truncated lines
    # Verify row count > 0
    # Return PASS/FAIL with diagnostic details
```

**Circuit Breaker Module (`rustybt/validation/timeouts.py`):**
```python
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

**And** log parsing applies retry logic:
```python
@retry(max_attempts=3, backoff_factor=2, exceptions=(IOError, ParquetReadError))
def parse_log_file(path: Path) -> pl.DataFrame:
    # Parsing logic with automatic retry on failure
```

**And** strategy execution has circuit breaker:
```python
@timeout(seconds=300)  # 5 minutes max
def execute_strategy(strategy: Strategy, data: DataFrame) -> Logs:
    # Kill subprocess if exceeds timeout
```

**And** health checks run before comparison:
```python
# Before comparison, validate both log files
rustybt_health = validate_log_integrity(rustybt_logs_path)
backtrader_health = validate_log_integrity(backtrader_logs_path)

if not (rustybt_health.passed and backtrader_health.passed):
    raise ValidationError("Log integrity check failed")
```

**And** unit tests verify resilience patterns:
- Retry logic handles transient failures
- Health checks detect corrupted logs
- Timeouts kill hanging operations

**Prerequisites:** Story 1.3 (models), Story 1.4 (log parsing patterns)

**Technical Notes:**
- Reference Implementation Readiness Report HC-001 (resilience patterns)
- Reference Test Design TC-002 (resilience patterns missing)
- Use Python stdlib (functools, signal, time) - no new dependencies
- Apply retry to: log parsing, Parquet operations, session file I/O
- Apply health checks to: JSONL logs, Parquet files, session YAML
- Apply timeouts to: strategy execution (5min), comparison (2min/layer)

---

## Story 1.9: Configure CI Pipeline with Quality Gates

As a developer,
I want CI pipeline configured with automated quality gates,
So that code quality is enforced on every commit.

**Acceptance Criteria:**

**Given** the project repository
**When** CI pipeline is configured
**Then** a GitHub Actions workflow file is created at `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.12
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e ".[validation,dev,test]"

      - name: Run tests with coverage
        run: |
          pytest --cov=rustybt/validation --cov-fail-under=80 --cov-report=xml --cov-report=term

      - name: Type check with mypy
        run: |
          mypy --strict rustybt/validation/

      - name: Lint with ruff
        run: |
          ruff check rustybt/validation/ --select=ALL

      - name: Security audit
        run: |
          pip-audit --desc

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

**And** quality gates enforce these thresholds:
- ❌ **FAIL if coverage <80%**
- ❌ **FAIL if mypy errors detected**
- ❌ **FAIL if ruff violations detected**
- ❌ **FAIL if critical/high vulnerabilities found**

**And** local development tools are configured:

**pytest configuration (pyproject.toml):**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "layer_1_data: Data handling validation tests",
    "layer_2_signals: Signal computation validation tests",
    "layer_3_orders: Order lifecycle validation tests",
    "layer_4_broker: Broker transaction validation tests",
    "layer_5_portfolio: Portfolio returns validation tests",
    "integration: Cross-layer integration tests",
    "e2e: Full strategy validation tests"
]
addopts = "--strict-markers --tb=short"

[tool.coverage.run]
source = ["rustybt/validation"]
omit = ["tests/*", "*/test_*.py"]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

**mypy configuration (pyproject.toml):**
```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**ruff configuration (pyproject.toml):**
```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "ANN", "S", "B", "A", "C4", "DTZ", "T10", "DJ", "EM", "EXE", "ISC", "ICN", "G", "INP", "PIE", "T20", "PYI", "PT", "Q", "RSE", "RET", "SLF", "SIM", "TID", "TCH", "INT", "ARG", "PTH", "TD", "FIX", "ERA", "PD", "PGH", "PL", "TRY", "FLY", "NPY", "AIR", "PERF", "FURB", "LOG", "RUF"]
ignore = ["ANN101", "ANN102"]  # Allow missing type annotations for self and cls
```

**And** CI badge is added to README.md (if exists)

**And** developers can run quality checks locally:
```bash
# Run all checks
pytest --cov=rustybt/validation --cov-fail-under=80
mypy --strict rustybt/validation/
ruff check rustybt/validation/
pip-audit
```

**Prerequisites:** Story 1.2 (dependencies), Story 1.3 (code to test)

**Technical Notes:**
- Reference Implementation Readiness Report HC-001 (CI pipeline missing)
- Reference Test Design Sprint 0 Recommendation #2 (configure CI pipeline)
- Reference Test Design Maintainability section (coverage ≥80%, mypy strict, ruff)
- CI runs on every push to main and on all pull requests
- Quality gates must pass before merging PRs
- Coverage threshold: 80% (can be increased to 90% later)
- Use GitHub Actions (free for public repos, generous limits for private)

---

