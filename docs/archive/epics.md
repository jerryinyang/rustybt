# rustybt - Epic Breakdown

**Author:** .smirk
**Date:** 2025-11-23
**Project Level:** Complex brownfield validation framework
**Target Scale:** 73 functional requirements across 7 epics

---

## Overview

This document provides the complete epic and story breakdown for rustybt's validation framework, decomposing the requirements from the [PRD](./prd.md) into implementable stories with technical guidance from the [Architecture](./architecture.md).

**Living Document Notice:** This is the initial version created after PRD and Architecture. Ready for Phase 4 implementation.

### Epic Summary

1. **Foundation - Validation Framework Infrastructure** - Core architecture and project setup
2. **Strategy Comparison Infrastructure** - Dual-framework execution and log capture
3. **Session Management System** - Validation work organization and tracking
4. **5-Layer Comparison Test Suite** - Automated discrepancy detection
5. **Investigation & Classification Workflow** - BUG/DESIGN analysis and resolution
6. **Initial Strategy Validation (4 Strategies)** - Prove correctness through validation
7. **Reporting & Documentation System** - Visibility and documentation

---

## Functional Requirements Inventory

**Test Suite Development (22 FRs):** FR1-FR22 (Test specifications, log ingestion/parsing, layer-specific comparisons, discrepancy detection, pass/fail reporting)

**Strategy Comparison Infrastructure (8 FRs):** FR23-FR30 (Identical implementations, execution with same data/parameters, log collection/organization)

**Validation Session Management (10 FRs):** FR31-FR40 (Session creation, tracking, resumability, queries, duplicate prevention)

**Investigation & Classification Workflow (14 FRs):** FR41-FR54 (Discrepancy presentation, source linking, BUG/DESIGN classification, fix verification, regression detection)

**Strategy Validation (5 FRs):** FR55-FR59 (Validate 4 strategies across all 5 layers, extensibility)

**Reporting & Documentation (8 FRs):** FR60-FR67 (Multi-level reports, classification exports, completion tracking)

**Data & Configuration Management (6 FRs):** FR68-FR73 (Tolerances, test expectations, data management, versioning)

**Total: 73 Functional Requirements**

---

## FR Coverage Map

| Epic | FRs Covered | Count |
|------|-------------|-------|
| Epic 1 (Foundation) | Infrastructure for all FRs | Foundation |
| Epic 2 (Strategy Comparison) | FR23-FR30 | 8 |
| Epic 3 (Session Management) | FR31-FR40 | 10 |
| Epic 4 (Test Suite) | FR1-FR22 | 22 |
| Epic 5 (Investigation) | FR41-FR54 | 14 |
| Epic 6 (Strategy Validation) | FR55-FR59 | 5 |
| Epic 7 (Reporting) | FR60-FR73 | 14 |
| **Total** | **All 73 FRs** | **73** |

---

## Epic 1: Foundation - Validation Framework Infrastructure

**Goal:** Establish the dual-location validation architecture (`rustybt/validation/` + `tests/validation/`) with core infrastructure that enables all validation work.

**Architecture References:**
- Project Structure (Architecture pg 33-93)
- Technology Stack (Architecture pg 115-144)
- Development Environment (Architecture pg 541-575)

**Value:** Framework ready for validation development with proper structure, dependencies, and foundational code.

---

### Story 1.1: Initialize Validation Framework Directory Structure

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

### Story 1.2: Configure Validation Framework Dependencies

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

### Story 1.3: Implement Core Data Models

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

### Story 1.4: Create Test Data Fixture Generator

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

### Story 1.5: Implement Basic Session Manager

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

### Story 1.6: Create Basic CLI Structure

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

### Story 1.7: Add Development Setup Documentation

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

### Story 1.8: Implement Resilience Patterns

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

### Story 1.9: Configure CI Pipeline with Quality Gates

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


## Epic 2: Strategy Comparison Infrastructure

**Goal:** Enable execution of identical strategies in both rustybt and Backtrader with structured log capture for comparison.

**Architecture References:**
- Log-Based Validation Architecture (Architecture pg 149-248)
- Subprocess Isolation Pattern (Architecture pg 249-268)
- ValidatedStrategy Base Classes (Architecture pg 163-179)

**Value:** Developers can execute dual strategies and capture structured logs for automated comparison.

**FRs Covered:** FR23-FR30 (Strategy Comparison Infrastructure - 8 FRs)

---

### Story 2.1: Implement ValidatedStrategy Base Class for rustybt

As a developer,
I want a base strategy class that auto-logs lifecycle events,
So that rustybt strategies automatically produce structured logs for comparison.

**Acceptance Criteria:**

**Given** the `rustybt/validation/base_strategy.py` module
**When** RustyBTValidatedStrategy is implemented
**Then** it extends rustybt's TradingAlgorithm with automatic logging:

```python
class RustyBTValidatedStrategy(TradingAlgorithm):
    """Base class for validated rustybt strategies with auto-logging."""

    def __init__(self, log_path: Path):
        self._log_path = log_path
        self._log_file = open(log_path, 'w')
        super().__init__()

    def _log_event(self, layer: str, event: str, data: dict) -> None:
        """Write structured event to JSONL log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "layer": layer,
            "event": event,
            "asset": data.get("asset"),
            "data": data
        }
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    def initialize(self, context):
        self._log_event("data", "initialize", {"context": "strategy_init"})
        super().initialize(context)

    def handle_data(self, context, data):
        self._log_event("data", "bar_received", {
            "timestamp": str(context.current_dt),
            "bar_count": len(data.history(data.current, "close", 1))
        })
        super().handle_data(context, data)
```

**And** lifecycle methods auto-log to appropriate layers:
- `initialize()` → layer: "data", event: "initialize"
- `handle_data()` → layer: "data", event: "bar_received"
- Signal computations → layer: "signals", event: "signal_computed"
- Order creation → layer: "orders", event: "order_created"

**And** log file is closed on strategy completion:
```python
def __del__(self):
    if hasattr(self, '_log_file') and not self._log_file.closed:
        self._log_file.close()
```

**And** unit tests verify logging behavior

**Prerequisites:** Story 1.3 (data models for log schema)

**Technical Notes:**
- Reference Architecture ValidatedStrategy Base Classes (pg 163-179)
- JSONL format: one JSON object per line
- Flush after each write to prevent data loss on crash
- Use context manager pattern for file handling

---

### Story 2.2: Implement ValidatedStrategy Base Class for Backtrader

As a developer,
I want a Backtrader base strategy class with identical logging behavior,
So that Backtrader strategies produce logs in the same format as rustybt.

**Acceptance Criteria:**

**Given** the `tests/validation/strategies/backtrader/base_validated.py` module
**When** BacktraderValidatedStrategy is implemented
**Then** it extends bt.Strategy with automatic logging:

```python
import backtrader as bt
from pathlib import Path
import json
from datetime import datetime

class BacktraderValidatedStrategy(bt.Strategy):
    """Base class for validated Backtrader strategies with auto-logging."""

    params = (
        ('log_path', None),
    )

    def __init__(self):
        self._log_file = open(self.params.log_path, 'w')
        self._log_event("data", "initialize", {"params": dict(self.params._getkwargs())})
        super().__init__()

    def _log_event(self, layer: str, event: str, data: dict) -> None:
        """Write structured event to JSONL log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "layer": layer,
            "event": event,
            "asset": data.get("asset"),
            "data": data
        }
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    def next(self):
        self._log_event("data", "bar_received", {
            "timestamp": str(self.data.datetime.datetime()),
            "close": float(self.data.close[0]),
            "volume": float(self.data.volume[0])
        })

    def stop(self):
        self._log_file.close()
```

**And** logging matches rustybt schema exactly:
- Same field names: timestamp, layer, event, asset, data
- Same layer values: data, signals, orders, broker, portfolio
- Same event names for equivalent operations

**And** file cleanup occurs in `stop()` method (Backtrader lifecycle)

**And** unit tests verify log format matches rustybt format

**Prerequisites:** Story 2.1 (rustybt base class defines schema)

**Technical Notes:**
- Reference Architecture Backtrader integration (pg 163-179)
- Backtrader uses `next()` instead of `handle_data()`
- Backtrader uses `stop()` for cleanup instead of destructor
- Use `self.params` for configuration (Backtrader convention)
- Access data via `self.data.close[0]` syntax

---

### Story 2.3: Create Log Event Decorators for Custom Logic

As a developer,
I want decorators to log custom strategy logic,
So that strategies can log signals, orders, and portfolio events without boilerplate.

**Acceptance Criteria:**

**Given** the `rustybt/validation/decorators.py` module
**When** logging decorators are implemented
**Then** the following decorators are available:

**@log_signal decorator:**
```python
def log_signal(layer: str = "signals"):
    """Decorator to log signal computation results."""
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            self._log_event(layer, "signal_computed", {
                "signal_name": method.__name__,
                "signal_value": result,
                "args": str(args),
            })
            return result
        return wrapper
    return decorator
```

**@log_order decorator:**
```python
def log_order(layer: str = "orders"):
    """Decorator to log order creation."""
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            order = method(self, *args, **kwargs)
            self._log_event(layer, "order_created", {
                "order_type": type(order).__name__,
                "asset": str(order.asset) if order else None,
                "quantity": float(order.quantity) if order else None,
                "limit_price": float(order.limit_price) if hasattr(order, 'limit_price') else None,
            })
            return order
        return wrapper
    return decorator
```

**@log_portfolio decorator:**
```python
def log_portfolio(layer: str = "portfolio"):
    """Decorator to log portfolio state."""
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            self._log_event(layer, "portfolio_updated", {
                "portfolio_value": float(self.portfolio.portfolio_value),
                "cash": float(self.portfolio.cash),
                "positions": {str(k): float(v.amount) for k, v in self.portfolio.positions.items()},
            })
            return result
        return wrapper
    return decorator
```

**And** decorators work with both rustybt and Backtrader base classes

**And** decorators handle exceptions gracefully (log failure, re-raise)

**And** unit tests demonstrate decorator usage in sample strategies

**Prerequisites:** Story 2.1, Story 2.2 (base classes with `_log_event()`)

**Technical Notes:**
- Use `functools.wraps` to preserve method metadata
- Convert Decimal/float values consistently in logs
- Handle None returns gracefully
- Decorators should be optional - strategies can call `_log_event()` directly

---

### Story 2.4: Implement Subprocess Execution Runner

As a developer,
I want a runner that executes strategies in isolated subprocesses,
So that rustybt and Backtrader don't conflict during execution.

**Acceptance Criteria:**

**Given** the `rustybt/validation/runner.py` module
**When** strategy runners are implemented
**Then** they support subprocess execution:

**run_rustybt_strategy() function:**
```python
def run_rustybt_strategy(
    strategy_module: str,
    data_path: Path,
    output_log: Path,
    params: dict = None
) -> subprocess.CompletedProcess:
    """Execute rustybt strategy in subprocess."""
    cmd = [
        sys.executable, "-m", "rustybt.validation.execute_rustybt",
        "--strategy", strategy_module,
        "--data", str(data_path),
        "--output", str(output_log),
    ]
    if params:
        cmd.extend(["--params", json.dumps(params)])

    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

**run_backtrader_strategy() function:**
```python
def run_backtrader_strategy(
    strategy_module: str,
    data_path: Path,
    output_log: Path,
    params: dict = None
) -> subprocess.CompletedProcess:
    """Execute Backtrader strategy in subprocess."""
    cmd = [
        sys.executable, "-m", "rustybt.validation.execute_backtrader",
        "--strategy", strategy_module,
        "--data", str(data_path),
        "--output", str(output_log),
    ]
    if params:
        cmd.extend(["--params", json.dumps(params)])

    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

**And** execution scripts exist:
- `rustybt/validation/execute_rustybt.py` - CLI wrapper for rustybt execution
- `rustybt/validation/execute_backtrader.py` - CLI wrapper for Backtrader execution

**And** runners capture stdout/stderr for error diagnostics

**And** runners enforce timeout (default 300 seconds)

**And** runners return exit code for success/failure detection

**And** integration test executes a simple strategy in both frameworks

**Prerequisites:** Story 2.1, Story 2.2 (base classes), Story 1.4 (test data)

**Technical Notes:**
- Reference Architecture Subprocess Isolation Pattern (pg 249-268)
- Use `subprocess.run()` for synchronous execution
- Use `sys.executable` to ensure same Python interpreter
- Timeout prevents hanging processes
- Capture output for debugging failed runs

---

### Story 2.5: Create Strategy Execution Wrapper Scripts

As a developer,
I want CLI wrapper scripts for each framework,
So that subprocess runners can execute strategies with consistent interfaces.

**Acceptance Criteria:**

**Given** the execution wrapper scripts
**When** they are implemented
**Then** `rustybt/validation/execute_rustybt.py` provides:

```python
"""CLI wrapper for rustybt strategy execution."""
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, help="Strategy module path")
    parser.add_argument("--data", required=True, type=Path, help="Data fixture path")
    parser.add_argument("--output", required=True, type=Path, help="Log output path")
    parser.add_argument("--params", type=json.loads, default={}, help="Strategy params JSON")
    args = parser.parse_args()

    # Import strategy class from module
    strategy_class = import_strategy(args.strategy)

    # Load data from Parquet
    data = load_data(args.data)

    # Execute strategy with logging
    strategy = strategy_class(log_path=args.output, **args.params)
    run_backtest(strategy, data)

if __name__ == "__main__":
    main()
```

**And** `rustybt/validation/execute_backtrader.py` provides equivalent Backtrader execution:

```python
"""CLI wrapper for Backtrader strategy execution."""
import argparse
import json
from pathlib import Path
import backtrader as bt

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, help="Strategy module path")
    parser.add_argument("--data", required=True, type=Path, help="Data fixture path")
    parser.add_argument("--output", required=True, type=Path, help="Log output path")
    parser.add_argument("--params", type=json.loads, default={}, help="Strategy params JSON")
    args = parser.parse_args()

    # Import strategy class from module
    strategy_class = import_strategy(args.strategy)

    # Create Cerebro engine
    cerebro = bt.Cerebro()

    # Load data
    data = bt.feeds.ParquetData(dataname=str(args.data))
    cerebro.adddata(data)

    # Add strategy with params
    cerebro.addstrategy(strategy_class, log_path=args.output, **args.params)

    # Run
    cerebro.run()

if __name__ == "__main__":
    main()
```

**And** both scripts:
- Exit with code 0 on success
- Exit with code 1 on failure (with error message to stderr)
- Validate all paths exist before execution
- Handle import errors gracefully

**And** unit tests verify CLI argument parsing

**Prerequisites:** Story 2.4 (runner functions)

**Technical Notes:**
- Use `importlib` for dynamic strategy import
- Backtrader may need data adapter (Parquet → bt.feeds)
- Both scripts should use identical parameter names for consistency
- Error messages should be clear and actionable

---

### Story 2.6: Implement Log Schema Validation

As a developer,
I want validation that log files follow the expected schema,
So that comparison can detect malformed logs before processing.

**Acceptance Criteria:**

**Given** the `rustybt/validation/log_parser.py` module
**When** schema validation is implemented
**Then** the following validation functions exist:

**validate_log_schema() function:**
```python
def validate_log_schema(log_path: Path) -> ValidationResult:
    """Validate JSONL log file against expected schema."""
    errors = []
    line_count = 0

    with open(log_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line_count += 1
            try:
                entry = json.loads(line)

                # Required fields
                if "timestamp" not in entry:
                    errors.append(f"Line {line_num}: Missing 'timestamp' field")
                if "layer" not in entry:
                    errors.append(f"Line {line_num}: Missing 'layer' field")
                if "event" not in entry:
                    errors.append(f"Line {line_num}: Missing 'event' field")

                # Valid layer values
                valid_layers = {"data", "signals", "orders", "broker", "portfolio"}
                if entry.get("layer") not in valid_layers:
                    errors.append(f"Line {line_num}: Invalid layer '{entry.get('layer')}'")

            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")

    return ValidationResult(
        valid=len(errors) == 0,
        line_count=line_count,
        errors=errors
    )
```

**And** ValidationResult dataclass:
```python
@dataclass
class ValidationResult:
    valid: bool
    line_count: int
    errors: list[str]
```

**And** CLI command for validation:
```bash
rustybt-validate log validate <log_path>
# Output: ✓ Valid (1234 lines) or ✗ Invalid (5 errors)
```

**And** validation runs automatically before comparison

**And** unit tests cover:
- Valid log files pass
- Missing required fields detected
- Invalid JSON detected
- Invalid layer values detected

**Prerequisites:** Story 2.1, Story 2.2 (log schema defined by base classes)

**Technical Notes:**
- Reference Architecture Log Schema (pg 183-189)
- Stream file to handle large logs without loading into memory
- Collect all errors (don't stop at first error)
- Provide actionable error messages with line numbers

---

### Story 2.7: Implement Dual Framework Execution Coordinator

As a developer,
I want a coordinator that executes both frameworks and collects logs,
So that validation can be performed with a single command.

**Acceptance Criteria:**

**Given** the `rustybt/validation/coordinator.py` module
**When** execution coordinator is implemented
**Then** it provides:

**execute_dual() function:**
```python
def execute_dual(
    session: Session,
    strategy_name: str,
    rustybt_module: str,
    backtrader_module: str,
    params: dict = None
) -> ExecutionResult:
    """Execute strategy in both frameworks and collect logs."""

    # Create log paths
    logs_dir = Path(f"validation-sessions/{session.id}/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    rustybt_log = logs_dir / "rustybt.jsonl"
    backtrader_log = logs_dir / "backtrader.jsonl"

    # Execute rustybt
    rb_result = run_rustybt_strategy(
        strategy_module=rustybt_module,
        data_path=session.data_fixture,
        output_log=rustybt_log,
        params=params
    )

    # Execute Backtrader
    bt_result = run_backtrader_strategy(
        strategy_module=backtrader_module,
        data_path=session.data_fixture,
        output_log=backtrader_log,
        params=params
    )

    # Validate logs
    rb_valid = validate_log_schema(rustybt_log)
    bt_valid = validate_log_schema(backtrader_log)

    return ExecutionResult(
        rustybt_success=rb_result.returncode == 0,
        backtrader_success=bt_result.returncode == 0,
        rustybt_log=rustybt_log,
        backtrader_log=backtrader_log,
        rustybt_log_valid=rb_valid.valid,
        backtrader_log_valid=bt_valid.valid,
        errors=collect_errors(rb_result, bt_result, rb_valid, bt_valid)
    )
```

**And** ExecutionResult dataclass:
```python
@dataclass
class ExecutionResult:
    rustybt_success: bool
    backtrader_success: bool
    rustybt_log: Path
    backtrader_log: Path
    rustybt_log_valid: bool
    backtrader_log_valid: bool
    errors: list[str]

    @property
    def success(self) -> bool:
        return (self.rustybt_success and self.backtrader_success and
                self.rustybt_log_valid and self.backtrader_log_valid)
```

**And** CLI command:
```bash
rustybt-validate run <session_id>
# Output: ✓ Both frameworks executed successfully
#         - rustybt: 1234 log entries
#         - backtrader: 1256 log entries
```

**And** execution updates session status

**And** integration test validates full execution flow

**Prerequisites:** Story 2.4 (runners), Story 2.5 (wrappers), Story 2.6 (validation)

**Technical Notes:**
- Execute sequentially (not parallel) for determinism
- Collect all errors for comprehensive diagnostics
- Update session.yaml with execution results
- Support --dry-run flag for testing without execution

---

## Epic 3: Session Management System

**Goal:** Provide complete session lifecycle management with progress tracking, resumability, and query capabilities.

**Architecture References:**
- Session Storage (Architecture ADR-003)
- Data Models (Architecture pg 359-402)
- CLI Interface (Architecture pg 435-452)

**Value:** Developers can manage validation work efficiently with full traceability and resumability.

**FRs Covered:** FR31-FR40 (Validation Session Management - 10 FRs)

---

### Story 3.1: Implement Session Progress Tracking

As a developer,
I want session progress tracked at each stage,
So that I can see where each validation session stands.

**Acceptance Criteria:**

**Given** the Session model and SessionManager
**When** progress tracking is implemented
**Then** sessions track these stages:

```python
class SessionStage(Enum):
    CREATED = "created"           # Session initialized
    EXECUTING = "executing"       # Strategies running
    EXECUTED = "executed"         # Logs collected
    COMPARING = "comparing"       # Running comparison
    COMPARED = "compared"         # Discrepancies found
    INVESTIGATING = "investigating"  # Manual investigation
    COMPLETED = "completed"       # All findings resolved
    FAILED = "failed"             # Error occurred
```

**And** Session model includes progress fields:
```python
@dataclass
class Session:
    # ... existing fields ...
    stage: SessionStage = SessionStage.CREATED
    stage_started_at: Optional[datetime] = None
    execution_completed_at: Optional[datetime] = None
    comparison_completed_at: Optional[datetime] = None
    layers_completed: list[str] = field(default_factory=list)
```

**And** SessionManager.update_stage() method:
```python
def update_stage(self, session: Session, stage: SessionStage) -> None:
    """Update session stage with timestamp."""
    session.stage = stage
    session.stage_started_at = datetime.now()
    self.save(session)
```

**And** CLI shows stage in session list:
```bash
rustybt-validate session list
# Session ID                    | Strategy      | Stage        | Created
# 20251123-230000-sma_crossover | sma_crossover | comparing    | 2025-11-23 23:00:00
```

**And** unit tests verify stage transitions

**Prerequisites:** Story 1.5 (basic SessionManager)

**Technical Notes:**
- Use Python Enum for stage values
- Always save session after stage change
- Invalid stage transitions should raise ValueError
- Timestamps enable progress monitoring

---

### Story 3.2: Implement Session Resumability

As a developer,
I want to resume interrupted sessions,
So that work isn't lost when validation is interrupted.

**Acceptance Criteria:**

**Given** a session that was interrupted
**When** resume is invoked
**Then** the session continues from the last completed stage:

**resume() method:**
```python
def resume(self, session_id: str) -> Session:
    """Resume session from last completed stage."""
    session = self.load(session_id)

    if session.stage == SessionStage.COMPLETED:
        raise ValueError("Session already completed")

    if session.stage == SessionStage.FAILED:
        # Reset to last successful stage
        session.stage = self._last_successful_stage(session)
        session.status = "IN_PROGRESS"

    return session
```

**And** CLI command:
```bash
rustybt-validate session resume <session_id>
# Resuming session 20251123-230000-sma_crossover from stage: compared
# Next step: investigating
```

**And** resume detects what's already complete:
- If logs exist and valid → skip execution
- If comparison results exist → skip comparison
- If all findings classified → mark complete

**And** integration test verifies:
- Interrupt during execution → resume re-executes
- Interrupt during comparison → resume re-compares
- Interrupt during investigation → resume shows pending findings

**Prerequisites:** Story 3.1 (progress tracking)

**Technical Notes:**
- Check file existence to determine completed work
- Preserve partial results when possible
- Log resume action for audit trail
- Handle corrupt intermediate files gracefully

---

### Story 3.3: Implement Session Query Commands

As a developer,
I want comprehensive session query commands,
So that I can find and inspect sessions efficiently.

**Acceptance Criteria:**

**Given** the CLI session commands
**When** query commands are implemented
**Then** the following commands exist:

**session list with filters:**
```bash
rustybt-validate session list --strategy sma_crossover
rustybt-validate session list --status IN_PROGRESS
rustybt-validate session list --stage investigating
rustybt-validate session list --since 2025-11-01
rustybt-validate session list --has-findings
```

**session show with details:**
```bash
rustybt-validate session show <session_id>
# Session: 20251123-230000-sma_crossover
# Strategy: sma_crossover
# Status: IN_PROGRESS
# Stage: compared
# Created: 2025-11-23 23:00:00
#
# Progress:
#   ✓ Execution completed (23:01:00)
#   ✓ Comparison completed (23:02:00)
#   ○ Investigation in progress
#
# Findings: 5 total (2 BUG, 1 DESIGN, 2 unclassified)
#
# Layers Completed: data, signals
# Layers Pending: orders, broker, portfolio
```

**session findings for quick view:**
```bash
rustybt-validate session findings <session_id>
# FIND-001 | data    | BUG    | Timestamp mismatch at bar 42
# FIND-002 | signals | DESIGN | RSI uses different smoothing
# FIND-003 | orders  | -      | Order quantity differs by 0.01
```

**And** output formats supported:
```bash
rustybt-validate session list --format json
rustybt-validate session list --format table  # default
```

**And** unit tests verify query filtering logic

**Prerequisites:** Story 1.6 (basic CLI), Story 3.1 (progress tracking)

**Technical Notes:**
- Use Click options for filters
- Support multiple filters (AND logic)
- Table format using simple alignment (no external deps)
- JSON format for programmatic use

---

### Story 3.4: Implement Duplicate Prevention

As a developer,
I want duplicate session/finding prevention,
So that validation work isn't accidentally repeated.

**Acceptance Criteria:**

**Given** session creation and finding recording
**When** duplicate prevention is implemented
**Then** duplicates are detected and handled:

**Session duplicate detection:**
```python
def create(self, strategy_name: str, data_fixture: Path) -> Session:
    """Create session with duplicate check."""
    # Check for existing IN_PROGRESS session with same strategy
    existing = self.find_sessions(
        strategy=strategy_name,
        status="IN_PROGRESS"
    )

    if existing:
        raise DuplicateSessionError(
            f"Session {existing[0].id} already in progress for {strategy_name}. "
            f"Use 'session resume' or 'session delete' first."
        )

    # Continue with creation...
```

**Finding duplicate detection:**
```python
def add_finding(self, session: Session, finding: Finding) -> None:
    """Add finding with duplicate check."""
    # Check for existing finding with same layer/event/timestamp
    for existing in session.findings:
        if (existing.layer == finding.layer and
            existing.event == finding.event and
            existing.timestamp == finding.timestamp):
            raise DuplicateFindingError(
                f"Finding already exists: {existing.id}"
            )

    session.findings.append(finding)
    self.save(session)
```

**And** CLI provides clear error messages:
```bash
rustybt-validate session create --strategy sma_crossover --data data.parquet
# Error: Session 20251123-230000-sma_crossover already in progress.
# Use 'rustybt-validate session resume 20251123-230000-sma_crossover' to continue
# or 'rustybt-validate session delete 20251123-230000-sma_crossover' to start fresh.
```

**And** --force flag allows override:
```bash
rustybt-validate session create --strategy sma_crossover --data data.parquet --force
# Warning: Existing session 20251123-230000-sma_crossover marked as SUPERSEDED
# Created new session: 20251123-233000-sma_crossover
```

**And** unit tests verify duplicate detection

**Prerequisites:** Story 3.3 (query capabilities)

**Technical Notes:**
- Use strategy + status combination for session uniqueness
- Use layer + event + timestamp for finding uniqueness
- Superseded sessions preserved for audit trail
- Clear error messages with actionable suggestions

---

### Story 3.5: Implement Session Deletion and Archival

As a developer,
I want to delete or archive old sessions,
So that the validation directory stays manageable.

**Acceptance Criteria:**

**Given** session management needs
**When** deletion/archival is implemented
**Then** the following commands exist:

**session delete command:**
```bash
rustybt-validate session delete <session_id>
# Are you sure you want to delete session 20251123-230000-sma_crossover? [y/N]
# Session deleted.

rustybt-validate session delete <session_id> --force
# Session deleted. (no confirmation)
```

**session archive command:**
```bash
rustybt-validate session archive <session_id>
# Session 20251123-230000-sma_crossover archived to validation-sessions/archive/

rustybt-validate session archive --older-than 30d
# Archived 5 sessions older than 30 days.
```

**session cleanup command:**
```bash
rustybt-validate session cleanup
# Found 3 failed sessions with no findings.
# Delete these sessions? [y/N]
# Deleted 3 sessions.
```

**And** deletion removes:
- Session directory and all contents
- All logs, analysis files, session.yaml

**And** archival:
- Compresses session to .tar.gz
- Moves to archive/ subdirectory
- Preserves session for future reference

**And** cleanup targets:
- FAILED sessions with no findings
- Sessions older than specified age
- Sessions with superseded status

**And** unit tests verify file operations

**Prerequisites:** Story 1.5 (SessionManager)

**Technical Notes:**
- Use shutil for file operations
- Require confirmation for destructive operations
- Archive using tarfile module
- Support --dry-run for preview

---

### Story 3.6: Implement Timestamped Activity Log

As a developer,
I want all session activities timestamped,
So that I have a complete audit trail of validation work.

**Acceptance Criteria:**

**Given** session activity tracking needs
**When** activity logging is implemented
**Then** sessions include activity log:

**Activity model:**
```python
@dataclass
class Activity:
    timestamp: datetime
    action: str
    actor: str  # "system" or username
    details: Optional[dict] = None
```

**Session with activities:**
```python
@dataclass
class Session:
    # ... existing fields ...
    activities: list[Activity] = field(default_factory=list)
```

**Auto-logged activities:**
- Session created
- Execution started/completed
- Comparison started/completed
- Finding added
- Finding classified
- Session resumed
- Session completed

**Manual activity logging:**
```python
session.log_activity("note", "Investigated RSI calculation - confirmed design difference", actor="smirk")
```

**And** activities persisted in session.yaml:
```yaml
activities:
  - timestamp: 2025-11-23T23:00:00
    action: created
    actor: system
  - timestamp: 2025-11-23T23:01:00
    action: execution_started
    actor: system
  - timestamp: 2025-11-23T23:05:00
    action: note
    actor: smirk
    details:
      message: "Investigated RSI calculation"
```

**And** CLI command to view activities:
```bash
rustybt-validate session activities <session_id>
# 2025-11-23 23:00:00 | system | created
# 2025-11-23 23:01:00 | system | execution_started
# 2025-11-23 23:05:00 | smirk  | note: Investigated RSI calculation
```

**Prerequisites:** Story 1.5 (SessionManager), Story 1.3 (models)

**Technical Notes:**
- Store activities in separate section of session.yaml
- Use ISO 8601 timestamps
- Actor defaults to "system" for automated actions
- Activities append-only (never delete)

---

## Epic 4: 5-Layer Comparison Test Suite

**Goal:** Implement comprehensive comparison logic for all 5 validation layers with configurable tolerances.

**Architecture References:**
- Log-Based Validation Architecture (Architecture pg 149-248)
- Tolerance Configuration (Architecture pg 243)
- Comparison Engine (Architecture pg 195-204)

**Value:** Automated detection of discrepancies at each layer with precise diagnostics.

**FRs Covered:** FR1-FR22 (Test Suite Development - 22 FRs)

---

### Story 4.1: Implement Log Parser with Parquet Caching

As a developer,
I want efficient log parsing with caching,
So that comparison operations run quickly on large log files.

**Acceptance Criteria:**

**Given** the `rustybt/validation/log_parser.py` module
**When** the log parser is implemented
**Then** it provides:

**parse_log() function:**
```python
def parse_log(log_path: Path, use_cache: bool = True) -> pl.DataFrame:
    """Parse JSONL log file to Polars DataFrame with optional caching."""
    cache_path = log_path.with_suffix('.parquet')

    # Check cache validity
    if use_cache and cache_path.exists():
        if cache_path.stat().st_mtime > log_path.stat().st_mtime:
            return pl.read_parquet(cache_path)

    # Parse JSONL
    records = []
    with open(log_path, 'r') as f:
        for line in f:
            records.append(json.loads(line))

    df = pl.DataFrame(records)

    # Flatten nested 'data' column
    df = flatten_data_column(df)

    # Cache to Parquet
    if use_cache:
        df.write_parquet(cache_path)

    return df
```

**And** cache invalidation works correctly:
- Cache regenerated if JSONL newer than Parquet
- Cache skipped if use_cache=False
- Cache path is predictable (.jsonl → .parquet)

**And** flatten_data_column() expands nested data:
```python
# Before: {"timestamp": "...", "layer": "data", "data": {"close": 100.5, "volume": 1000}}
# After: columns: timestamp, layer, data_close, data_volume
```

**And** performance: Parse 100MB JSONL in <5 seconds

**And** unit tests verify:
- Basic parsing
- Cache creation and invalidation
- Nested data flattening

**Prerequisites:** Story 2.6 (schema validation)

**Technical Notes:**
- Use Polars for DataFrame operations
- Stream JSONL parsing for memory efficiency
- Prefix flattened columns with "data_" for clarity
- Handle missing fields gracefully (null values)

---

### Story 4.2: Implement Tolerance Configuration System

As a developer,
I want configurable tolerances per layer,
So that comparison accounts for acceptable differences.

**Acceptance Criteria:**

**Given** tolerance configuration needs
**When** the tolerance system is implemented
**Then** YAML configuration files exist:

**tests/validation/config/layer_1_tolerances.yaml:**
```yaml
layer_1_data:
  timestamp_window_ms: 1  # 1ms tolerance for timestamp alignment
  price_decimal_places: 4  # Compare prices to 4 decimal places
  volume_tolerance_pct: 0.001  # 0.1% volume tolerance
  bar_count_tolerance: 0  # Exact bar count match required
```

**tests/validation/config/layer_2_tolerances.yaml:**
```yaml
layer_2_signals:
  indicator_decimal_places: 6  # Compare indicators to 6 decimal places
  signal_timing_tolerance_bars: 0  # Signals must match same bar
  signal_count_tolerance: 0  # Exact signal count required
```

**And similar for layers 3, 4, 5**

**And** tolerance loading:
```python
def load_tolerances(layer: str) -> dict:
    """Load tolerance configuration for specified layer."""
    config_path = Path(f"tests/validation/config/{layer}_tolerances.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)
```

**And** tolerance override in tests:
```python
@pytest.mark.layer_1_data
def test_data_handling(tolerances):
    # Override specific tolerance
    tolerances["price_decimal_places"] = 2

    discrepancies = compare_layer("data", rustybt_logs, backtrader_logs, tolerances)
```

**And** CLI shows active tolerances:
```bash
rustybt-validate config show layer_1_data
# layer_1_data tolerances:
#   timestamp_window_ms: 1
#   price_decimal_places: 4
#   ...
```

**Prerequisites:** Story 1.2 (PyYAML dependency)

**Technical Notes:**
- Reference Architecture Tolerance Configuration (pg 243)
- Use pytest fixtures to inject tolerances
- Document each tolerance meaning in config file comments
- Default tolerances should be conservative (strict)

---

### Story 4.3: Implement Layer 1 Data Handling Comparator

As a developer,
I want Layer 1 comparison for data handling,
So that lookahead bias and bar alignment issues are detected.

**Acceptance Criteria:**

**Given** the `rustybt/validation/comparators.py` module
**When** Layer1DataComparator is implemented
**Then** it detects:

**Lookahead bias detection:**
```python
def detect_lookahead_bias(logs: pl.DataFrame) -> list[Discrepancy]:
    """Detect if strategy accessed future data."""
    discrepancies = []

    # Check that data access timestamps <= current bar timestamp
    data_events = logs.filter(pl.col("layer") == "data")

    for row in data_events.iter_rows(named=True):
        accessed_time = row.get("data_accessed_timestamp")
        current_bar = row.get("data_current_bar_timestamp")

        if accessed_time and current_bar:
            if accessed_time > current_bar:
                discrepancies.append(Discrepancy(
                    layer="data",
                    event="lookahead_bias",
                    timestamp=current_bar,
                    field="data_access",
                    rustybt_value=accessed_time,
                    backtrader_value=current_bar,
                    tolerance="none",
                    exceeded_by=f"{accessed_time - current_bar} ahead"
                ))

    return discrepancies
```

**Bar alignment comparison:**
```python
def compare_bar_alignment(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare bar timestamps and OHLCV values."""
    discrepancies = []

    rb_bars = rustybt_logs.filter(pl.col("event") == "bar_received")
    bt_bars = backtrader_logs.filter(pl.col("event") == "bar_received")

    # Compare bar counts
    if len(rb_bars) != len(bt_bars):
        discrepancies.append(Discrepancy(
            layer="data",
            event="bar_count_mismatch",
            timestamp=None,
            field="bar_count",
            rustybt_value=len(rb_bars),
            backtrader_value=len(bt_bars),
            tolerance=tolerances.get("bar_count_tolerance", 0),
            exceeded_by=abs(len(rb_bars) - len(bt_bars))
        ))

    # Compare individual bars
    # ... timestamp alignment, OHLCV value comparison ...

    return discrepancies
```

**And** pytest test function:
```python
@pytest.mark.layer_1_data
def test_layer_1_data_handling(sma_crossover_logs, layer_1_tolerances):
    """Validate data handling layer for SMA crossover strategy."""
    comparator = Layer1DataComparator(layer_1_tolerances)
    discrepancies = comparator.compare(
        sma_crossover_logs["rustybt"],
        sma_crossover_logs["backtrader"]
    )

    # Filter known DESIGN differences
    unexpected = [d for d in discrepancies if not is_known_design(d)]

    assert len(unexpected) == 0, format_discrepancies(unexpected)
```

**And** test file exists: `tests/validation/test_layer_1_data.py`

**Prerequisites:** Story 4.1 (log parser), Story 4.2 (tolerances)

**Technical Notes:**
- Reference Architecture Layer 1 specification
- Lookahead bias is CRITICAL - zero tolerance
- Bar alignment uses timestamp_window_ms tolerance
- OHLCV comparison uses price_decimal_places tolerance

---

### Story 4.4: Implement Layer 2 Signal Computation Comparator

As a developer,
I want Layer 2 comparison for signal computation,
So that indicator calculation and signal timing differences are detected.

**Acceptance Criteria:**

**Given** the comparators module
**When** Layer2SignalsComparator is implemented
**Then** it compares:

**Indicator value comparison:**
```python
def compare_indicators(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare indicator calculations."""
    discrepancies = []
    decimal_places = tolerances.get("indicator_decimal_places", 6)

    rb_signals = rustybt_logs.filter(pl.col("layer") == "signals")
    bt_signals = backtrader_logs.filter(pl.col("layer") == "signals")

    # Join on timestamp and signal name
    joined = rb_signals.join(bt_signals, on=["timestamp", "data_signal_name"], suffix="_bt")

    for row in joined.iter_rows(named=True):
        rb_value = row["data_signal_value"]
        bt_value = row["data_signal_value_bt"]

        if not values_match(rb_value, bt_value, decimal_places):
            discrepancies.append(Discrepancy(
                layer="signals",
                event="indicator_mismatch",
                timestamp=row["timestamp"],
                field=row["data_signal_name"],
                rustybt_value=rb_value,
                backtrader_value=bt_value,
                tolerance=f"{decimal_places} decimal places",
                exceeded_by=abs(rb_value - bt_value)
            ))

    return discrepancies
```

**Signal timing comparison:**
```python
def compare_signal_timing(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare when signals fire."""
    # Extract buy/sell signals
    # Compare signal bar numbers
    # Detect timing differences
```

**Signal count comparison:**
```python
def compare_signal_counts(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare total signal counts."""
    # Count signals by type (buy, sell, etc.)
    # Compare counts with tolerance
```

**And** pytest marker: `@pytest.mark.layer_2_signals`

**And** test file exists: `tests/validation/test_layer_2_signals.py`

**Prerequisites:** Story 4.3 (Layer 1 comparator pattern)

**Technical Notes:**
- Some indicator differences are DESIGN (e.g., RSI smoothing method)
- Document known DESIGN differences in config
- Signal timing uses bar index, not timestamp

---

### Story 4.5: Implement Layer 3 Order Lifecycle Comparator

As a developer,
I want Layer 3 comparison for order lifecycle,
So that order creation, execution, and state transition differences are detected.

**Acceptance Criteria:**

**Given** the comparators module
**When** Layer3OrdersComparator is implemented
**Then** it compares:

**Order creation comparison:**
```python
def compare_order_creation(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare order creation events."""
    discrepancies = []

    rb_orders = rustybt_logs.filter(pl.col("event") == "order_created")
    bt_orders = backtrader_logs.filter(pl.col("event") == "order_created")

    # Compare order counts
    # Compare order types (market, limit, stop)
    # Compare order quantities
    # Compare order timing (which bar)

    return discrepancies
```

**Order execution comparison:**
```python
def compare_order_execution(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare order fill events."""
    # Compare fill prices
    # Compare fill quantities
    # Compare fill timing
```

**Order state transition comparison:**
```python
def compare_order_states(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare order state transitions."""
    # CREATED → SUBMITTED → FILLED sequence
    # CREATED → CANCELLED handling
    # Partial fill handling
```

**And** pytest marker: `@pytest.mark.layer_3_orders`

**And** test file exists: `tests/validation/test_layer_3_orders.py`

**Prerequisites:** Story 4.4 (Layer 2 pattern)

**Technical Notes:**
- Order IDs may differ - match by timestamp + asset + quantity
- Fill prices may differ due to slippage model differences (DESIGN)
- State transitions should match exactly

---

### Story 4.6: Implement Layer 4 Broker Transaction Comparator

As a developer,
I want Layer 4 comparison for broker transactions,
So that commission, slippage, position, and cash differences are detected.

**Acceptance Criteria:**

**Given** the comparators module
**When** Layer4BrokerComparator is implemented
**Then** it compares:

**Commission comparison:**
```python
def compare_commissions(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare commission calculations."""
    # Extract transaction events with commissions
    # Compare commission per trade
    # Compare total commissions
```

**Slippage comparison:**
```python
def compare_slippage(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare slippage modeling."""
    # Compare expected price vs fill price
    # Compare slippage amounts
```

**Position tracking comparison:**
```python
def compare_positions(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare position tracking."""
    # Compare position sizes at each bar
    # Compare long/short positions
    # Compare position value
```

**Cash ledger comparison:**
```python
def compare_cash(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare cash ledger."""
    # Compare cash balance at each bar
    # Compare debits/credits per transaction
```

**And** pytest marker: `@pytest.mark.layer_4_broker`

**And** test file exists: `tests/validation/test_layer_4_broker.py`

**Prerequisites:** Story 4.5 (Layer 3 pattern)

**Technical Notes:**
- Commission models may differ (DESIGN) - document differences
- Slippage models may differ (DESIGN)
- Cash and position tracking should match closely

---

### Story 4.7: Implement Layer 5 Portfolio Returns Comparator

As a developer,
I want Layer 5 comparison for portfolio returns,
So that return calculations and portfolio valuations are validated.

**Acceptance Criteria:**

**Given** the comparators module
**When** Layer5PortfolioComparator is implemented
**Then** it compares:

**Return calculation comparison:**
```python
def compare_returns(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare return calculations."""
    # Compare daily returns
    # Compare cumulative returns
    # Compare annualized returns
```

**Portfolio valuation comparison:**
```python
def compare_portfolio_value(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare portfolio valuations."""
    # Compare portfolio value at each bar
    # Compare starting value
    # Compare final value
```

**Performance metrics comparison:**
```python
def compare_metrics(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare performance metrics."""
    # Compare Sharpe ratio
    # Compare max drawdown
    # Compare volatility
```

**And** pytest marker: `@pytest.mark.layer_5_portfolio`

**And** test file exists: `tests/validation/test_layer_5_portfolio.py`

**Prerequisites:** Story 4.6 (Layer 4 pattern)

**Technical Notes:**
- Return calculations may use different conventions (DESIGN)
- Portfolio value is most important metric for validation
- Performance metrics may differ due to calculation methods

---

### Story 4.8: Implement Master Comparison Orchestrator

As a developer,
I want a master orchestrator that runs all layer comparisons,
So that full validation can be performed with a single command.

**Acceptance Criteria:**

**Given** all layer comparators
**When** master orchestrator is implemented
**Then** it provides:

**run_all_comparisons() function:**
```python
def run_all_comparisons(
    session: Session,
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame
) -> ComparisonResult:
    """Run all 5 layer comparisons."""
    all_discrepancies = []
    layer_results = {}

    comparators = [
        ("data", Layer1DataComparator),
        ("signals", Layer2SignalsComparator),
        ("orders", Layer3OrdersComparator),
        ("broker", Layer4BrokerComparator),
        ("portfolio", Layer5PortfolioComparator),
    ]

    for layer_name, comparator_class in comparators:
        tolerances = load_tolerances(f"layer_{layer_name}")
        comparator = comparator_class(tolerances)

        discrepancies = comparator.compare(rustybt_logs, backtrader_logs)

        all_discrepancies.extend(discrepancies)
        layer_results[layer_name] = LayerResult(
            layer=layer_name,
            discrepancy_count=len(discrepancies),
            passed=len([d for d in discrepancies if not is_known_design(d)]) == 0
        )

        session.layers_completed.append(layer_name)
        SessionManager.save(session)

    return ComparisonResult(
        total_discrepancies=len(all_discrepancies),
        layer_results=layer_results,
        discrepancies=all_discrepancies
    )
```

**And** CLI command:
```bash
rustybt-validate compare <session_id>
# Running 5-layer comparison...
# Layer 1 (Data):      ✓ Passed (0 discrepancies)
# Layer 2 (Signals):   ✓ Passed (2 DESIGN, 0 unexpected)
# Layer 3 (Orders):    ✗ Failed (3 discrepancies)
# Layer 4 (Broker):    ✓ Passed (1 DESIGN, 0 unexpected)
# Layer 5 (Portfolio): ✓ Passed (0 discrepancies)
#
# Total: 6 discrepancies (3 DESIGN, 3 require investigation)
```

**And** selective layer comparison:
```bash
rustybt-validate compare <session_id> --layer data
rustybt-validate compare <session_id> --layer signals,orders
```

**And** comparison results saved to session

**Prerequisites:** Stories 4.3-4.7 (all layer comparators)

**Technical Notes:**
- Run layers sequentially for determinism
- Save progress after each layer (resumability)
- Pass/fail based on unexpected discrepancies (not DESIGN)
- Support partial comparison for debugging

---

## Epic 5: Investigation & Classification Workflow

**Goal:** Enable systematic investigation and classification of discrepancies as BUG or DESIGN with full traceability.

**Architecture References:**
- Finding Classification Workflow (Architecture Pattern 4)
- Data Models (Architecture pg 359-402)
- CLI Interface (Architecture pg 435-452)

**Value:** Every discrepancy is investigated, classified, and either fixed or documented.

**FRs Covered:** FR41-FR54 (Investigation & Classification Workflow - 14 FRs)

---

### Story 5.1: Implement Discrepancy Presentation Interface

As a developer,
I want discrepancies presented clearly for investigation,
So that I can efficiently analyze and classify each finding.

**Acceptance Criteria:**

**Given** a session with discrepancies
**When** investigation interface is invoked
**Then** CLI presents findings clearly:

**investigate command:**
```bash
rustybt-validate investigate <session_id>
#
# === Finding FIND-001 (1/5 unclassified) ===
#
# Layer: orders
# Event: order_quantity_mismatch
# Timestamp: 2020-03-15T09:30:00
# Asset: AAPL
#
# rustybt value: 100.0
# Backtrader value: 99.0
# Difference: 1.0 (1%)
# Tolerance: 0 (exact match required)
#
# Context:
#   Previous bar: 2020-03-15T09:29:00
#   Signal: buy_signal = True
#   Order type: MARKET
#
# Actions:
#   [b] Classify as BUG (requires fix)
#   [d] Classify as DESIGN (intentional difference)
#   [s] Skip (investigate later)
#   [v] View source code locations
#   [c] View comparison context
#   [q] Quit investigation
#
# Enter action:
```

**And** finding navigation:
```bash
rustybt-validate investigate <session_id> --finding FIND-003
# Jump directly to specific finding
```

**And** layer filtering:
```bash
rustybt-validate investigate <session_id> --layer orders
# Only show findings from orders layer
```

**And** status filtering:
```bash
rustybt-validate investigate <session_id> --unclassified
# Only show unclassified findings
```

**Prerequisites:** Story 4.8 (comparison generates findings)

**Technical Notes:**
- Use Click.prompt for interactive input
- Provide context (previous/next bars) for debugging
- Show tolerance configuration for reference
- Support keyboard shortcuts for efficiency

---

### Story 5.2: Implement Source Code Linking

As a developer,
I want findings linked to relevant source code,
So that I can investigate the root cause efficiently.

**Acceptance Criteria:**

**Given** a finding being investigated
**When** source code linking is requested
**Then** relevant code locations are identified:

**locate_source() function:**
```python
def locate_source(finding: Finding, framework: str) -> list[SourceLocation]:
    """Locate relevant source code for finding."""
    locations = []

    # Map layer to source modules
    layer_modules = {
        "data": ["rustybt/data/", "zipline/data/"],
        "signals": ["rustybt/algorithm.py", "rustybt/signals/"],
        "orders": ["rustybt/finance/order.py", "rustybt/finance/blotter.py"],
        "broker": ["rustybt/finance/broker.py", "rustybt/finance/commission.py"],
        "portfolio": ["rustybt/finance/portfolio.py", "rustybt/finance/returns.py"],
    }

    # Search for event-related functions
    for module_pattern in layer_modules.get(finding.layer, []):
        matches = grep_for_event(module_pattern, finding.event)
        locations.extend(matches)

    return locations
```

**And** CLI view source command:
```bash
# In investigation mode, press 'v':
#
# Source code locations for FIND-001:
#
# rustybt locations:
#   1. rustybt/finance/order.py:142 - order_quantity calculation
#   2. rustybt/finance/blotter.py:89 - create_order()
#
# Backtrader locations (reference):
#   1. backtrader/order.py:234 - Order.__init__
#   2. backtrader/broker.py:456 - submit()
#
# Open location? [1-4 or n to skip]:
```

**And** support for opening files in editor:
```bash
rustybt-validate config set editor "code -g {file}:{line}"
# Opens file in VS Code at specific line
```

**Prerequisites:** Story 5.1 (investigation interface)

**Technical Notes:**
- Use grep/ripgrep for code search
- Support configurable editor command
- Cache source locations for repeated queries
- Include Backtrader source for reference

---

### Story 5.3: Implement BUG Classification Workflow

As a developer,
I want to classify findings as BUG with required rationale,
So that bugs are properly documented and tracked for fixing.

**Acceptance Criteria:**

**Given** a finding requiring classification
**When** BUG classification is selected
**Then** workflow captures required information:

**CLI workflow:**
```bash
# Press 'b' to classify as BUG:
#
# === Classify as BUG ===
#
# Rationale (required - explain why this is a bug):
# > Order quantity calculation doesn't account for fractional shares
#
# Affected component(s):
# > rustybt/finance/order.py
#
# Severity:
#   [1] Critical - incorrect results
#   [2] Major - significant deviation
#   [3] Minor - small deviation
# > 2
#
# Suggested fix (optional):
# > Add round() to quantity calculation in create_order()
#
# === BUG Classification Saved ===
# Finding FIND-001 classified as BUG (Major)
# Next: Create fix in rustybt, then use 'rustybt-validate verify <finding_id>'
```

**And** Finding model updated:
```python
finding.classification = "BUG"
finding.rationale = "Order quantity calculation doesn't account for fractional shares"
finding.severity = "Major"
finding.affected_components = ["rustybt/finance/order.py"]
finding.suggested_fix = "Add round() to quantity calculation"
finding.investigated_by = "smirk"
finding.investigated_at = datetime.now()
```

**And** validation requires:
- Rationale (non-empty string)
- Affected component (at least one)
- Severity level

**Prerequisites:** Story 5.1 (investigation interface)

**Technical Notes:**
- Store all BUG metadata in findings.yaml
- Rationale required to prevent lazy classification
- Severity helps prioritize fixes
- Suggested fix is optional but helpful

---

### Story 5.4: Implement DESIGN Classification Workflow

As a developer,
I want to classify findings as DESIGN with documentation,
So that intentional differences are properly documented for users.

**Acceptance Criteria:**

**Given** a finding requiring classification
**When** DESIGN classification is selected
**Then** workflow captures required information:

**CLI workflow:**
```bash
# Press 'd' to classify as DESIGN:
#
# === Classify as DESIGN ===
#
# Rationale (required - explain why this is intentional):
# > rustybt uses Wilder's smoothing for RSI, Backtrader uses EMA smoothing.
# > This is a valid design choice with industry precedent.
#
# Which framework is correct? (both may be valid):
#   [r] rustybt approach is preferred
#   [b] Backtrader approach is preferred
#   [e] Either approach is valid
# > e
#
# User impact:
# > Users may see ~0.5% difference in RSI values. No functional impact on signal timing.
#
# Documentation reference (will be created if doesn't exist):
# > docs/validation/design-differences.md#rsi-calculation
#
# === DESIGN Classification Saved ===
# Finding FIND-002 classified as DESIGN
# Documentation stub created at docs/validation/design-differences.md
```

**And** Finding model updated:
```python
finding.classification = "DESIGN"
finding.rationale = "rustybt uses Wilder's smoothing for RSI..."
finding.design_choice = "either_valid"
finding.user_impact = "Users may see ~0.5% difference..."
finding.documentation_ref = "docs/validation/design-differences.md#rsi-calculation"
finding.investigated_by = "smirk"
finding.investigated_at = datetime.now()
```

**And** auto-generates documentation stub if doesn't exist

**Prerequisites:** Story 5.1 (investigation interface)

**Technical Notes:**
- DESIGN differences must be documented for users
- Auto-create docs/validation/design-differences.md
- Include anchor links for specific findings
- User impact helps users understand practical implications

---

### Story 5.5: Implement Bug Fix Verification

As a developer,
I want to verify that bug fixes resolve discrepancies,
So that fixes are validated before marking findings as resolved.

**Acceptance Criteria:**

**Given** a BUG-classified finding that has been fixed
**When** verification is invoked
**Then** the fix is validated:

**verify command:**
```bash
rustybt-validate verify FIND-001
#
# === Verifying Fix for FIND-001 ===
#
# Original discrepancy:
#   Layer: orders
#   Event: order_quantity_mismatch
#   rustybt: 100.0, Backtrader: 99.0
#
# Re-running strategy execution...
# ✓ rustybt executed successfully
# ✓ Backtrader executed successfully
#
# Re-running layer comparison...
# ✓ Order quantities now match
#
# === Fix Verified ===
# FIND-001 marked as resolved
# Regression test created: tests/validation/regression/test_find_001.py
```

**And** verification fails if discrepancy persists:
```bash
# ✗ Verification failed
# Discrepancy still present:
#   rustybt: 100.0, Backtrader: 99.0
#
# Fix not complete. Finding remains open.
```

**And** verification updates finding:
```python
finding.resolved = True
finding.resolved_at = datetime.now()
finding.regression_test = "tests/validation/regression/test_find_001.py"
```

**Prerequisites:** Story 5.3 (BUG classification), Story 4.8 (comparison)

**Technical Notes:**
- Re-executes strategy with same parameters
- Re-runs comparison for affected layer only
- Must pass to mark as resolved
- Creates regression test automatically

---

### Story 5.6: Implement Regression Test Generation

As a developer,
I want regression tests auto-generated for fixed bugs,
So that bugs don't reappear in future development.

**Acceptance Criteria:**

**Given** a verified bug fix
**When** regression test generation is triggered
**Then** a pytest test is created:

**Generated test:**
```python
# tests/validation/regression/test_find_001.py
"""
Regression test for FIND-001: Order quantity mismatch

Original finding:
- Layer: orders
- Event: order_quantity_mismatch
- rustybt: 100.0, Backtrader: 99.0

Fixed: 2025-11-24
Fix: Added round() to quantity calculation in rustybt/finance/order.py
"""
import pytest
from rustybt.validation import compare_layer, load_tolerances

@pytest.mark.regression
@pytest.mark.layer_3_orders
def test_find_001_order_quantity(sma_crossover_logs):
    """Verify order quantities match after fix for FIND-001."""
    tolerances = load_tolerances("layer_orders")

    discrepancies = compare_layer(
        "orders",
        sma_crossover_logs["rustybt"],
        sma_crossover_logs["backtrader"],
        tolerances
    )

    # Specific check for the fixed issue
    quantity_mismatches = [
        d for d in discrepancies
        if d.event == "order_quantity_mismatch"
    ]

    assert len(quantity_mismatches) == 0, (
        f"Regression: Order quantity mismatch detected. "
        f"Original bug FIND-001 may have reappeared."
    )
```

**And** regression test includes:
- Reference to original finding ID
- Original discrepancy details
- Fix date and description
- Specific assertion for the fixed issue

**And** regression tests run in CI:
```bash
pytest tests/validation/regression/ -v
```

**Prerequisites:** Story 5.5 (fix verification)

**Technical Notes:**
- Use pytest markers for categorization
- Include original finding context in docstring
- Generate meaningful test name from finding ID
- Store generated tests in regression/ subdirectory

---

### Story 5.7: Implement Regression Detection

As a developer,
I want automatic detection when fixed bugs reappear,
So that regressions are caught immediately.

**Acceptance Criteria:**

**Given** existing regression tests
**When** validation is run
**Then** regressions are detected and reported:

**Regression detection:**
```python
def detect_regressions(
    session: Session,
    discrepancies: list[Discrepancy]
) -> list[Regression]:
    """Check if any discrepancies match previously fixed bugs."""
    regressions = []

    # Load all resolved BUG findings
    resolved_bugs = load_resolved_bugs()

    for discrepancy in discrepancies:
        for bug in resolved_bugs:
            if matches_finding(discrepancy, bug):
                regressions.append(Regression(
                    original_finding=bug.id,
                    current_discrepancy=discrepancy,
                    fixed_at=bug.resolved_at,
                    regression_detected_at=datetime.now()
                ))

    return regressions
```

**And** CLI reports regressions prominently:
```bash
rustybt-validate compare <session_id>
#
# ⚠️ REGRESSION DETECTED ⚠️
#
# Finding FIND-001 (fixed 2025-11-24) has reappeared!
#   Layer: orders
#   Event: order_quantity_mismatch
#   Original fix: Added round() to quantity calculation
#
# This may indicate the fix was reverted or a new code path introduced the bug.
#
# Action required: Investigate and fix before proceeding.
```

**And** regressions block session completion

**Prerequisites:** Story 5.6 (regression tests)

**Technical Notes:**
- Compare discrepancies against resolved findings database
- Match by layer + event + similar values
- Regressions are critical - require immediate attention
- Block session completion until resolved

---

## Epic 6: Initial Strategy Validation (4 Strategies)

**Goal:** Implement and validate 4 trading strategies across all 5 layers to prove framework correctness.

**Architecture References:**
- Strategy Implementations (Architecture pg 57-68)
- ValidatedStrategy Base Classes (Architecture pg 163-179)

**Value:** Concrete proof of rustybt correctness through validated strategy implementations.

**FRs Covered:** FR55-FR59 (Strategy Validation - 5 FRs)

---

### Story 6.1: Implement SMA Crossover Strategy (Dual)

As a developer,
I want SMA Crossover strategy implemented in both frameworks,
So that this foundational strategy can be validated.

**Acceptance Criteria:**

**Given** the strategy template
**When** SMA Crossover is implemented
**Then** rustybt implementation exists:

**tests/validation/strategies/rustybt/sma_crossover.py:**
```python
"""SMA Crossover Strategy - rustybt implementation."""
from rustybt.validation.base_strategy import RustyBTValidatedStrategy
from rustybt.validation.decorators import log_signal, log_order

class SMACrossoverStrategy(RustyBTValidatedStrategy):
    """
    Simple Moving Average Crossover Strategy.

    Buy when fast SMA crosses above slow SMA.
    Sell when fast SMA crosses below slow SMA.
    """

    def __init__(self, log_path, fast_period=10, slow_period=30):
        super().__init__(log_path)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.fast_sma = None
        self.slow_sma = None

    def initialize(self, context):
        super().initialize(context)
        # Set up SMA indicators
        self.fast_sma = self.add_indicator('sma', period=self.fast_period)
        self.slow_sma = self.add_indicator('sma', period=self.slow_period)

    @log_signal()
    def compute_signal(self, context, data):
        """Compute crossover signal."""
        if self.fast_sma[-1] > self.slow_sma[-1] and self.fast_sma[-2] <= self.slow_sma[-2]:
            return "BUY"
        elif self.fast_sma[-1] < self.slow_sma[-1] and self.fast_sma[-2] >= self.slow_sma[-2]:
            return "SELL"
        return "HOLD"

    @log_order()
    def handle_data(self, context, data):
        super().handle_data(context, data)

        signal = self.compute_signal(context, data)

        if signal == "BUY" and not self.portfolio.positions:
            self.order_target_percent(data.current, 1.0)
        elif signal == "SELL" and self.portfolio.positions:
            self.order_target_percent(data.current, 0.0)
```

**And** Backtrader implementation exists:

**tests/validation/strategies/backtrader/sma_crossover.py:**
```python
"""SMA Crossover Strategy - Backtrader implementation."""
import backtrader as bt
from tests.validation.strategies.backtrader.base_validated import BacktraderValidatedStrategy

class SMACrossoverStrategy(BacktraderValidatedStrategy):
    """Backtrader SMA Crossover - logically equivalent to rustybt version."""

    params = (
        ('log_path', None),
        ('fast_period', 10),
        ('slow_period', 30),
    )

    def __init__(self):
        super().__init__()
        self.fast_sma = bt.indicators.SMA(period=self.params.fast_period)
        self.slow_sma = bt.indicators.SMA(period=self.params.slow_period)
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)

    def next(self):
        super().next()

        self._log_signal(self.fast_sma[0], self.slow_sma[0])

        if self.crossover > 0:  # Fast crossed above slow
            if not self.position:
                self.order_target_percent(target=1.0)
        elif self.crossover < 0:  # Fast crossed below slow
            if self.position:
                self.order_target_percent(target=0.0)
```

**And** strategy audit checklist passed:
- [ ] Same indicator calculations
- [ ] Same signal logic
- [ ] Same order sizing
- [ ] Same entry/exit conditions

**And** unit tests verify isolated logic

**Prerequisites:** Story 2.1, Story 2.2 (base classes)

**Technical Notes:**
- Reference Architecture Strategy Implementations (pg 57-68)
- Use default parameters: fast=10, slow=30
- Log all indicator values for comparison
- Keep logic simple and identical

---

### Story 6.2: Implement Mean Reversion Strategy (Dual)

As a developer,
I want Mean Reversion strategy implemented in both frameworks,
So that z-score based strategies can be validated.

**Acceptance Criteria:**

**Given** the strategy template
**When** Mean Reversion is implemented
**Then** both implementations exist with:

**Strategy logic:**
```python
"""
Mean Reversion Strategy (z-score based)

Buy when z-score < -2 (price significantly below mean)
Sell when z-score > 2 (price significantly above mean)
Exit when z-score returns to 0 (mean reversion complete)
"""
```

**Key parameters:**
- lookback_period: 20 (for mean/std calculation)
- entry_threshold: 2.0 (z-score threshold for entry)
- exit_threshold: 0.0 (z-score threshold for exit)

**And** rustybt implementation: `tests/validation/strategies/rustybt/mean_reversion.py`

**And** Backtrader implementation: `tests/validation/strategies/backtrader/mean_reversion.py`

**And** strategy audit checklist passed

**And** unit tests verify z-score calculation logic

**Prerequisites:** Story 6.1 (SMA Crossover establishes pattern)

**Technical Notes:**
- Z-score = (price - mean) / std_dev
- Use rolling window for mean/std calculation
- Log z-score values for signal comparison
- Handle division by zero (std_dev = 0)

---

### Story 6.3: Implement Momentum Strategy (Dual)

As a developer,
I want Momentum strategy with RSI and trailing stops implemented,
So that more complex order management can be validated.

**Acceptance Criteria:**

**Given** the strategy template
**When** Momentum is implemented
**Then** both implementations exist with:

**Strategy logic:**
```python
"""
Momentum Strategy (RSI + Trailing Stops)

Buy when RSI < 30 (oversold, expecting upward momentum)
Sell when RSI > 70 (overbought, expecting downward momentum)
Use 5% trailing stop for risk management
"""
```

**Key parameters:**
- rsi_period: 14
- oversold_threshold: 30
- overbought_threshold: 70
- trailing_stop_pct: 0.05 (5%)

**And** trailing stop logic:
```python
def update_trailing_stop(self, current_price):
    if self.position_type == "LONG":
        new_stop = current_price * (1 - self.trailing_stop_pct)
        self.stop_price = max(self.stop_price, new_stop)
    elif self.position_type == "SHORT":
        new_stop = current_price * (1 + self.trailing_stop_pct)
        self.stop_price = min(self.stop_price, new_stop)
```

**And** rustybt implementation: `tests/validation/strategies/rustybt/momentum.py`

**And** Backtrader implementation: `tests/validation/strategies/backtrader/momentum.py`

**And** strategy audit checklist passed

**Prerequisites:** Story 6.2 (Mean Reversion)

**Technical Notes:**
- RSI calculation may differ between frameworks (DESIGN)
- Trailing stop implementation is key validation point
- Log stop price updates for comparison
- Handle position size correctly with stops

---

### Story 6.4: Implement Multi-Factor Strategy (Dual)

As a developer,
I want Multi-Factor strategy combining EMA + RSI + MACD implemented,
So that complex multi-indicator strategies can be validated.

**Acceptance Criteria:**

**Given** the strategy template
**When** Multi-Factor is implemented
**Then** both implementations exist with:

**Strategy logic:**
```python
"""
Multi-Factor Strategy (EMA + RSI + MACD)

Buy when ALL conditions met:
1. Price > EMA(50) (uptrend)
2. RSI > 50 but < 70 (bullish but not overbought)
3. MACD > Signal line (momentum confirmation)

Sell when ANY condition fails or RSI > 80 (overbought exit)
"""
```

**Key parameters:**
- ema_period: 50
- rsi_period: 14
- macd_fast: 12
- macd_slow: 26
- macd_signal: 9

**And** factor scoring:
```python
def compute_factors(self, data):
    factors = {
        "trend": 1 if data.close > self.ema[-1] else 0,
        "momentum_rsi": 1 if 50 < self.rsi[-1] < 70 else 0,
        "momentum_macd": 1 if self.macd[-1] > self.macd_signal[-1] else 0,
    }
    return factors
```

**And** rustybt implementation: `tests/validation/strategies/rustybt/multi_factor.py`

**And** Backtrader implementation: `tests/validation/strategies/backtrader/multi_factor.py`

**And** strategy audit checklist passed

**Prerequisites:** Story 6.3 (Momentum)

**Technical Notes:**
- Log individual factor values for debugging
- MACD calculation may differ (DESIGN candidate)
- All three factors must align for entry
- Any factor failing triggers exit

---

### Story 6.5: Execute Full Validation for All 4 Strategies

As a developer,
I want all 4 strategies validated across all 5 layers,
So that framework correctness is proven comprehensively.

**Acceptance Criteria:**

**Given** all 4 strategies implemented
**When** full validation is executed
**Then** each strategy passes all 5 layers:

**Validation matrix:**
```
Strategy        | L1 Data | L2 Signals | L3 Orders | L4 Broker | L5 Portfolio | Overall
----------------|---------|------------|-----------|-----------|--------------|--------
SMA Crossover   | ✓       | ✓          | ✓         | ✓         | ✓            | PASS
Mean Reversion  | ✓       | ✓          | ✓         | ✓         | ✓            | PASS
Momentum        | ✓       | ✓ (2 DESIGN)| ✓        | ✓         | ✓            | PASS
Multi-Factor    | ✓       | ✓ (1 DESIGN)| ✓        | ✓         | ✓            | PASS
```

**And** all BUG-classified findings are fixed and verified

**And** all DESIGN-classified findings are documented

**And** regression tests exist for all fixed bugs

**And** validation report generated:
```bash
rustybt-validate report --all
#
# === rustybt Validation Report ===
#
# Strategies Validated: 4
# Layers Tested: 5 per strategy (20 total)
#
# Results:
#   Passed: 20 layers
#   Failed: 0 layers
#
# Findings:
#   Total: 12
#   BUG: 5 (all fixed and verified)
#   DESIGN: 7 (all documented)
#
# Confidence Level: HIGH
#
# Documentation:
#   - Design differences: docs/validation/design-differences.md
#   - Bug fixes: docs/validation/bug-fixes.md
#   - Regression tests: tests/validation/regression/
```

**Prerequisites:** Stories 6.1-6.4 (all strategies), Epic 4 (test suite), Epic 5 (investigation)

**Technical Notes:**
- This is the culminating validation story
- May require multiple sessions per strategy
- Document all findings regardless of classification
- Generate comprehensive validation report

---

## Epic 7: Reporting & Documentation System

**Goal:** Provide comprehensive reporting and documentation generation for validation results.

**Architecture References:**
- Reporting (Architecture pg 442-448)
- CLI Interface (Architecture pg 435-452)

**Value:** Clear visibility into validation status and comprehensive documentation for users.

**FRs Covered:** FR60-FR73 (Reporting & Documentation + Data/Config - 14 FRs)

---

### Story 7.1: Implement Session Report Generator

As a developer,
I want detailed reports per session,
So that validation results are clearly documented.

**Acceptance Criteria:**

**Given** a completed or in-progress session
**When** report generation is invoked
**Then** a markdown report is generated:

**Report structure:**
```markdown
# Validation Session Report

**Session ID:** 20251123-230000-sma_crossover
**Strategy:** SMA Crossover
**Status:** COMPLETED
**Date:** 2025-11-23

## Summary

| Metric | Value |
|--------|-------|
| Total Findings | 5 |
| BUG | 2 (fixed) |
| DESIGN | 3 (documented) |
| Unclassified | 0 |
| Layers Passed | 5/5 |

## Layer Results

### Layer 1: Data Handling
**Status:** ✓ PASSED

No discrepancies detected.

### Layer 2: Signal Computation
**Status:** ✓ PASSED (2 DESIGN findings)

| Finding | Classification | Description |
|---------|---------------|-------------|
| FIND-001 | DESIGN | RSI smoothing method differs |
| FIND-002 | DESIGN | SMA calculation order differs |

[...]

## Findings Detail

### FIND-001: RSI Smoothing Method
**Classification:** DESIGN
**Layer:** signals
**Rationale:** rustybt uses Wilder's smoothing, Backtrader uses EMA...
[...]
```

**And** CLI command:
```bash
rustybt-validate report <session_id>
# Report saved to: validation-sessions/{session_id}/report.md

rustybt-validate report <session_id> --format json
# JSON format for programmatic use
```

**And** reports saved to session directory

**Prerequisites:** Story 4.8 (comparison), Story 5.4 (classifications)

**Technical Notes:**
- Use markdown tables for readability
- Include all finding details
- Support JSON format for CI integration
- Auto-generate on session completion

---

### Story 7.2: Implement Layer Report Generator

As a developer,
I want reports per validation layer across all strategies,
So that layer-specific validation can be reviewed.

**Acceptance Criteria:**

**Given** multiple validated strategies
**When** layer report is generated
**Then** cross-strategy layer summary is produced:

**Layer report structure:**
```markdown
# Layer 2: Signal Computation - Validation Report

## Overview

Signal computation validation across all validated strategies.

## Strategy Results

| Strategy | Status | Findings | Notes |
|----------|--------|----------|-------|
| SMA Crossover | ✓ PASS | 2 DESIGN | RSI, SMA order |
| Mean Reversion | ✓ PASS | 0 | - |
| Momentum | ✓ PASS | 1 DESIGN | RSI smoothing |
| Multi-Factor | ✓ PASS | 1 DESIGN | MACD calculation |

## Common DESIGN Differences

### RSI Calculation (3 strategies affected)
rustybt uses Wilder's smoothing method, Backtrader uses EMA smoothing.
**User Impact:** RSI values may differ by ~0.5%
**Workaround:** None needed, both methods are valid.

[...]
```

**And** CLI command:
```bash
rustybt-validate report --layer signals
# Report saved to: docs/validation/layer-2-signals-report.md
```

**Prerequisites:** Story 7.1 (session reports)

**Technical Notes:**
- Aggregate findings across strategies
- Identify common patterns (same DESIGN across strategies)
- Help users understand layer-specific behaviors

---

### Story 7.3: Implement Strategy Report Generator

As a developer,
I want reports per strategy across all layers,
So that strategy-specific validation can be reviewed.

**Acceptance Criteria:**

**Given** a fully validated strategy
**When** strategy report is generated
**Then** comprehensive strategy summary is produced:

**Strategy report structure:**
```markdown
# SMA Crossover Strategy - Validation Report

## Strategy Overview

Simple Moving Average Crossover strategy validated against Backtrader.

**Parameters:**
- Fast Period: 10
- Slow Period: 30

## Validation Results

| Layer | Status | Findings |
|-------|--------|----------|
| Data Handling | ✓ PASS | 0 |
| Signal Computation | ✓ PASS | 2 DESIGN |
| Order Lifecycle | ✓ PASS | 0 |
| Broker Transactions | ✓ PASS | 0 |
| Portfolio Returns | ✓ PASS | 0 |

**Overall Status:** ✓ VALIDATED

## Findings Summary

[... detailed findings ...]

## Recommendations

- RSI values may differ slightly from Backtrader (see DESIGN-001)
- Strategy behaves identically for practical trading purposes
```

**And** CLI command:
```bash
rustybt-validate report --strategy sma_crossover
# Report saved to: docs/validation/strategy-sma-crossover-report.md
```

**Prerequisites:** Story 7.1 (session reports)

**Technical Notes:**
- Focus on single strategy across all layers
- Include recommendations for users
- Reference detailed findings

---

### Story 7.4: Implement Overall Status Dashboard

As a developer,
I want an overall validation status dashboard,
So that I can see the complete validation picture at a glance.

**Acceptance Criteria:**

**Given** all validation sessions
**When** status command is invoked
**Then** dashboard is displayed:

**CLI output:**
```bash
rustybt-validate status
#
# ═══════════════════════════════════════════════════════════════
#                    rustybt Validation Status
# ═══════════════════════════════════════════════════════════════
#
# Strategies Validated: 4/4
# ┌──────────────────┬───────────┬───────────┬────────────┐
# │ Strategy         │ Status    │ Findings  │ Last Run   │
# ├──────────────────┼───────────┼───────────┼────────────┤
# │ SMA Crossover    │ ✓ VALID   │ 5 (0 BUG) │ 2025-11-23 │
# │ Mean Reversion   │ ✓ VALID   │ 3 (0 BUG) │ 2025-11-23 │
# │ Momentum         │ ✓ VALID   │ 4 (0 BUG) │ 2025-11-24 │
# │ Multi-Factor     │ ✓ VALID   │ 6 (0 BUG) │ 2025-11-24 │
# └──────────────────┴───────────┴───────────┴────────────┘
#
# Layer Coverage: 5/5 (100%)
# ┌────────────────────┬────────┬─────────────────────────────┐
# │ Layer              │ Status │ Notes                       │
# ├────────────────────┼────────┼─────────────────────────────┤
# │ 1. Data Handling   │ ✓ PASS │ All strategies              │
# │ 2. Signals         │ ✓ PASS │ 4 DESIGN differences noted  │
# │ 3. Orders          │ ✓ PASS │ All strategies              │
# │ 4. Broker          │ ✓ PASS │ All strategies              │
# │ 5. Portfolio       │ ✓ PASS │ All strategies              │
# └────────────────────┴────────┴─────────────────────────────┘
#
# Findings Summary:
#   Total: 18
#   BUG: 6 (all fixed ✓)
#   DESIGN: 12 (all documented ✓)
#   Regression Tests: 6
#
# Overall Confidence: HIGH ███████████░ 92%
#
# ═══════════════════════════════════════════════════════════════
```

**And** JSON output for CI:
```bash
rustybt-validate status --format json
# {"strategies_validated": 4, "layers_covered": 5, "bugs_open": 0, ...}
```

**And** exit code for CI:
- Exit 0 if all strategies validated, no open bugs
- Exit 1 if any strategy failed or bugs open

**Prerequisites:** Story 7.1-7.3 (all report types)

**Technical Notes:**
- Use box-drawing characters for ASCII tables
- Calculate confidence based on coverage and findings
- Exit codes enable CI integration
- Refresh data from all sessions

---

### Story 7.5: Implement DESIGN Differences Documentation

As a developer,
I want auto-generated documentation for all DESIGN differences,
So that users understand framework behavioral differences.

**Acceptance Criteria:**

**Given** DESIGN-classified findings
**When** documentation generation is invoked
**Then** user-facing documentation is generated:

**docs/validation/design-differences.md:**
```markdown
# rustybt vs Backtrader: Design Differences

This document describes intentional design differences between rustybt and Backtrader discovered during validation.

## Signal Computation

### RSI Calculation Method

**Finding:** FIND-001, FIND-007, FIND-012

**Difference:**
- rustybt uses Wilder's smoothing (exponential moving average with α = 1/period)
- Backtrader uses standard EMA smoothing

**Impact:**
RSI values may differ by ~0.5% between frameworks. This does not affect trading signal timing in most cases.

**Recommendation:**
No action needed. Both methods are industry-standard approaches to RSI calculation.

---

### MACD Calculation

**Finding:** FIND-015

**Difference:**
- rustybt calculates MACD signal line using 9-period EMA
- Backtrader uses 9-period SMA by default

[...]

## Order Execution

[...]

## Broker Transactions

[...]
```

**And** auto-update when new DESIGN findings added

**And** CLI command:
```bash
rustybt-validate docs generate
# Generated: docs/validation/design-differences.md
# Generated: docs/validation/bug-fixes.md
```

**Prerequisites:** Story 5.4 (DESIGN classification)

**Technical Notes:**
- Group findings by layer/category
- Write in user-friendly language
- Include practical impact and recommendations
- Auto-regenerate to stay current

---

### Story 7.6: Implement Validation Completion Tracking

As a developer,
I want validation completion percentage tracked,
So that I know how much validation work remains.

**Acceptance Criteria:**

**Given** defined validation scope
**When** completion tracking is queried
**Then** progress is calculated:

**Completion calculation:**
```python
def calculate_completion() -> ValidationProgress:
    """Calculate overall validation completion."""
    # Strategy completion
    total_strategies = 4  # Defined in PRD
    validated_strategies = count_validated_strategies()

    # Layer completion per strategy
    total_layers = 5 * total_strategies  # 20 total
    completed_layers = count_completed_layers()

    # Finding resolution
    total_findings = count_all_findings()
    resolved_findings = count_resolved_findings()

    return ValidationProgress(
        strategy_completion=validated_strategies / total_strategies,
        layer_completion=completed_layers / total_layers,
        finding_resolution=resolved_findings / total_findings if total_findings > 0 else 1.0,
        overall=calculate_weighted_average(...)
    )
```

**And** CLI command:
```bash
rustybt-validate progress
#
# Validation Progress
# ═══════════════════
#
# Strategies: ████████░░ 3/4 (75%)
#   ✓ SMA Crossover
#   ✓ Mean Reversion
#   ✓ Momentum
#   ○ Multi-Factor (in progress)
#
# Layers: █████████░ 18/20 (90%)
#   Multi-Factor missing: signals, portfolio
#
# Findings: ██████████ 15/15 (100%)
#   All findings classified and resolved
#
# Overall: ████████░░ 88%
#
# Next Steps:
#   1. Complete Multi-Factor validation (2 layers remaining)
#   2. Generate final validation report
```

**Prerequisites:** Story 7.4 (status dashboard)

**Technical Notes:**
- Weight completion by importance (strategies > layers > findings)
- Track partial layer completion
- Suggest next actions based on gaps

---

### Story 7.7: Implement Next Actions Recommender

As a developer,
I want recommended next actions for validation,
So that I know what to work on next.

**Acceptance Criteria:**

**Given** current validation state
**When** next actions are queried
**Then** prioritized recommendations are provided:

**Recommendation logic:**
```python
def recommend_next_actions() -> list[Recommendation]:
    """Recommend next validation actions based on current state."""
    actions = []

    # Priority 1: Open bugs
    open_bugs = get_open_bug_findings()
    if open_bugs:
        actions.append(Recommendation(
            priority=1,
            action="Fix open bugs",
            details=f"{len(open_bugs)} BUG findings require fixes",
            command="rustybt-validate investigate --bugs"
        ))

    # Priority 2: Unclassified findings
    unclassified = get_unclassified_findings()
    if unclassified:
        actions.append(Recommendation(
            priority=2,
            action="Classify findings",
            details=f"{len(unclassified)} findings need classification",
            command="rustybt-validate investigate --unclassified"
        ))

    # Priority 3: Incomplete strategies
    incomplete = get_incomplete_strategies()
    if incomplete:
        actions.append(Recommendation(
            priority=3,
            action="Complete strategy validation",
            details=f"{incomplete[0]} has incomplete layers",
            command=f"rustybt-validate run {incomplete[0].session_id}"
        ))

    # Priority 4: Missing documentation
    if needs_documentation_update():
        actions.append(Recommendation(
            priority=4,
            action="Update documentation",
            details="DESIGN differences need documentation refresh",
            command="rustybt-validate docs generate"
        ))

    return sorted(actions, key=lambda x: x.priority)
```

**And** CLI integration:
```bash
rustybt-validate next
#
# Recommended Next Actions
# ════════════════════════
#
# 1. [HIGH] Fix open bugs (2 BUG findings)
#    Command: rustybt-validate investigate --bugs
#
# 2. [MEDIUM] Classify findings (3 unclassified)
#    Command: rustybt-validate investigate --unclassified
#
# 3. [LOW] Update documentation
#    Command: rustybt-validate docs generate
```

**Prerequisites:** Story 7.6 (completion tracking)

**Technical Notes:**
- Prioritize by impact (bugs > unclassified > incomplete > docs)
- Provide copy-pasteable commands
- Update dynamically based on state

---

## FR Coverage Matrix

| FR | Description | Epic | Story |
|----|-------------|------|-------|
| FR1 | Test specifications for 5 layers | Epic 4 | 4.3-4.7 |
| FR2 | Ingest structured logs | Epic 4 | 4.1 |
| FR3 | Parse logs to standard structures | Epic 4 | 4.1 |
| FR4-FR5 | Data handling comparison | Epic 4 | 4.3 |
| FR6-FR8 | Signal computation comparison | Epic 4 | 4.4 |
| FR9-FR11 | Order lifecycle comparison | Epic 4 | 4.5 |
| FR12-FR15 | Broker transaction comparison | Epic 4 | 4.6 |
| FR16-FR18 | Portfolio returns comparison | Epic 4 | 4.7 |
| FR19-FR22 | Discrepancy detection & reporting | Epic 4 | 4.8 |
| FR23-FR30 | Strategy comparison infrastructure | Epic 2 | 2.1-2.7 |
| FR31-FR40 | Session management | Epic 3 | 3.1-3.6 |
| FR41-FR54 | Investigation & classification | Epic 5 | 5.1-5.7 |
| FR55-FR59 | Strategy validation | Epic 6 | 6.1-6.5 |
| FR60-FR67 | Reporting & documentation | Epic 7 | 7.1-7.5 |
| FR68-FR73 | Data & configuration | Epic 4 | 4.2, Epic 7 | 7.6-7.7 |

---

## Summary

**Epic 1 (Foundation):** 9 stories - Core infrastructure, models, CLI, resilience, CI
**Epic 2 (Strategy Comparison):** 7 stories - Base classes, runners, coordinators
**Epic 3 (Session Management):** 6 stories - Progress tracking, resumability, queries
**Epic 4 (Test Suite):** 8 stories - Log parsing, tolerances, 5 layer comparators
**Epic 5 (Investigation):** 7 stories - Classification workflow, verification, regression
**Epic 6 (Strategy Validation):** 5 stories - 4 dual-implemented strategies
**Epic 7 (Reporting):** 7 stories - Reports, dashboard, documentation, recommendations

**Total: 49 stories across 7 epics covering 73 functional requirements**

---

_For implementation: Use the `create-story` workflow to generate individual story implementation plans from this epic breakdown._

_This document provides complete epic and story breakdown for Phase 4 implementation._

