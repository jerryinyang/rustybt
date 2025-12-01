# Architecture

## Executive Summary

This architecture document defines the technical foundation for the **rustybt Validation Framework** - a comprehensive testing system that proves rustybt's correctness through systematic comparison against Backtrader, a battle-tested reference implementation.

**Architecture Approach:** Brownfield integration extending rustybt's existing infrastructure with a dual-location validation framework:
- **Core library** (`rustybt/validation/`) provides reusable validation utilities
- **Test infrastructure** (`tests/validation/`) contains pytest-based test runners and fixtures

**Key Principles:**
- **Zero Mock Enforcement:** All comparisons use real rustybt and Backtrader executions
- **Deterministic Testing:** Reproducible results through controlled data and seeded randomness
- **Log-Based Validation:** Structured logs enable precise layer-by-layer comparison
- **Detective Methodology:** Systematic discovery, investigation, and classification of discrepancies

## Decision Summary

| Category | Decision | Version | Affects FR Categories | Rationale |
| -------- | -------- | ------- | --------------------- | --------- |
| Project Structure | Dual-location architecture: `rustybt/validation/` (library) + `tests/validation/` (tests) | N/A | All categories | Separates reusable validation utilities from test execution; leverages existing pytest infrastructure |
| Log Format | JSONL (JSON Lines) primary + Parquet caching | JSON (Python stdlib), Parquet via Polars | Test Suite Development, Strategy Comparison | Human-readable JSONL for debugging; fast Parquet queries for test execution; leverages existing Polars infrastructure |
| Session Storage | YAML files with directory structure | PyYAML >=6.0 | Validation Session Management, Investigation & Classification | Simple, version-controllable, human-readable; session directory: `validation-sessions/{session_id}/` with session.yaml, findings.yaml, logs/, analysis/ |
| Strategy Instrumentation | ValidatedStrategy base class + optional decorators | N/A (Python stdlib) | Strategy Comparison Infrastructure | Auto-logs core lifecycle methods; @log_event decorator for custom logic; balance of automation and flexibility |
| Comparison Engine | Polars-based DataFrame comparison | Polars >=1.0 | Test Suite Development | Leverages existing rustybt Polars infrastructure; fast columnar operations; built-in null-aware comparisons |
| Tolerance Configuration | YAML config files per validation layer | PyYAML >=6.0 | Data & Configuration Management | Layer-specific tolerance thresholds (e.g., decimal precision, timing windows); overridable per test |
| Test Framework | pytest with custom fixtures and markers | pytest >=7.2.0 | Test Suite Development | Leverages existing pytest setup; custom markers: @pytest.mark.layer_1_data, @pytest.mark.layer_2_signals, etc. |
| CLI Interface | Click-based command-line tool | Click >=8.0 | Validation Session Management | Simple, composable CLI: `rustybt-validate session create`, `rustybt-validate session list`, `rustybt-validate investigate` |
| Dual Framework Execution | Subprocess isolation with unified data fixtures | subprocess (Python stdlib) | Strategy Comparison Infrastructure | Run rustybt and Backtrader in separate processes to avoid conflicts; shared Parquet data ensures identical inputs |
| Version Tracking | Capture framework versions in session metadata | N/A (version introspection) | Data & Configuration Management | Record rustybt version, Backtrader version, Python version per session for reproducibility |

## Project Structure

```
rustybt/
├── rustybt/                          # Core library
│   ├── validation/                   # Validation framework library (NEW)
│   │   ├── __init__.py
│   │   ├── base_strategy.py         # ValidatedStrategy base classes
│   │   ├── session.py               # SessionManager
│   │   ├── log_parser.py            # JSONL/Parquet log parsing
│   │   ├── comparators.py           # Layer-specific comparison logic
│   │   ├── models.py                # Data models (Session, Finding, Discrepancy)
│   │   ├── reporting.py             # Report generation
│   │   └── cli.py                   # Click CLI commands
│   ├── benchmarks/                   # Existing performance benchmarks
│   └── ...                          # Existing rustybt modules
├── tests/
│   ├── validation/                   # Validation test infrastructure (ENHANCED)
│   │   ├── __init__.py
│   │   ├── conftest.py              # pytest fixtures
│   │   ├── test_layer_1_data.py     # Data handling validation tests
│   │   ├── test_layer_2_signals.py  # Signal computation validation tests
│   │   ├── test_layer_3_orders.py   # Order lifecycle validation tests
│   │   ├── test_layer_4_broker.py   # Broker transaction validation tests
│   │   ├── test_layer_5_portfolio.py # Portfolio returns validation tests
│   │   ├── strategies/              # Dual-implemented strategies
│   │   │   ├── rustybt/
│   │   │   │   ├── sma_crossover.py
│   │   │   │   ├── mean_reversion.py
│   │   │   │   ├── momentum.py
│   │   │   │   └── multi_factor.py
│   │   │   └── backtrader/
│   │   │       ├── sma_crossover.py
│   │   │       ├── mean_reversion.py
│   │   │       ├── momentum.py
│   │   │       └── multi_factor.py
│   │   ├── fixtures/                # Test data fixtures
│   │   │   └── validation_data.parquet
│   │   └── config/                  # Tolerance configurations
│   │       ├── layer_1_tolerances.yaml
│   │       ├── layer_2_tolerances.yaml
│   │       ├── layer_3_tolerances.yaml
│   │       ├── layer_4_tolerances.yaml
│   │       └── layer_5_tolerances.yaml
│   ├── benchmarks/                   # Existing performance benchmarks
│   └── ...                          # Existing test modules
├── validation-sessions/              # Session storage (NEW, gitignored)
│   └── {session_id}/
│       ├── session.yaml             # Session metadata
│       ├── findings.yaml            # Discrepancies and classifications
│       ├── logs/
│       │   ├── rustybt.jsonl
│       │   ├── backtrader.jsonl
│       │   ├── rustybt.parquet      # Cached for fast queries
│       │   └── backtrader.parquet
│       └── analysis/
│           ├── layer_1_report.md
│           ├── layer_2_report.md
│           ├── layer_3_report.md
│           ├── layer_4_report.md
│           └── layer_5_report.md
├── docs/
│   ├── architecture.md              # This document
│   ├── prd.md                       # Requirements
│   └── validation/                  # Validation framework docs (NEW)
│       ├── getting-started.md
│       ├── layer-specifications.md
│       └── investigation-guide.md
└── pyproject.toml                   # Updated dependencies
```

## FR Category to Architecture Mapping

| FR Category | Primary Modules | Test Modules |
| ----------- | --------------- | ------------ |
| Test Suite Development (FR1-FR22) | `rustybt/validation/comparators.py`, `log_parser.py` | `tests/validation/test_layer_*.py` |
| Strategy Comparison Infrastructure (FR23-FR30) | `rustybt/validation/base_strategy.py` | `tests/validation/strategies/` |
| Validation Session Management (FR31-FR40) | `rustybt/validation/session.py`, `models.py` | `tests/validation/conftest.py` |
| Investigation & Classification (FR41-FR54) | `rustybt/validation/models.py` (Finding, Classification) | Manual workflow via CLI |
| Strategy Validation (FR55-FR59) | `tests/validation/strategies/` | `tests/validation/test_layer_*.py` |
| Reporting & Documentation (FR60-FR67) | `rustybt/validation/reporting.py` | Auto-generated per session |
| Data & Configuration (FR68-FR73) | `tests/validation/config/*.yaml`, `fixtures/` | `tests/validation/conftest.py` |

## Technology Stack Details

### Core Technologies (Inherited from rustybt)

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.12+ | Required by rustybt |
| Testing | pytest | >=7.2.0 | Test framework |
| Data Processing | Polars | >=1.0 | Log parsing and comparison |
| Precision | Decimal | Built-in | Financial calculations |
| Property Testing | Hypothesis | >=6.0 | Validation correctness |
| Linting | Ruff | >=0.11.12 | Code quality |
| Type Checking | mypy | >=1.10.0 | Static analysis |

### New Dependencies for Validation Framework

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Configuration | PyYAML | >=6.0 | Session and tolerance configs |
| CLI | Click | >=8.0 | Command-line interface |
| Reference Framework | Backtrader | >=1.9.78 | Comparison baseline |

### Integration Points

**With Existing rustybt Infrastructure:**
- Shares `rustybt/testing/fixtures.py` for test data generation
- Uses `rustybt/benchmarks/models.py` patterns for result models
- Leverages `rustybt/data/` Parquet storage patterns
- Integrates with existing pytest configuration

**External Integrations:**
- **Backtrader:** Separate Python environment or venv for clean execution
- **CI/CD:** pytest integration for automated validation runs

## Novel Pattern: Log-Based Validation Architecture

### Pattern Name
**Structured Log Comparison for Framework Validation**

### Purpose
Enable layer-by-layer comparison of two trading frameworks without requiring identical internal APIs or data structures.

### Problem Solved
Traditional unit test comparison requires matching APIs. rustybt and Backtrader have different APIs, making direct comparison impossible. Log-based validation decouples frameworks while enabling precise behavioral comparison.

### Components

**1. ValidatedStrategy Base Classes**

The rustybt validation strategy uses a mixin pattern that integrates with rustybt's actual TradingAlgorithm engine:

```python
from rustybt.validation.base_strategy import RustyBTValidatedStrategy
from rustybt.api import order_target_percent

class MySMAStrategy(RustyBTValidatedStrategy):
    """Example validated strategy using real rustybt APIs."""

    def __init__(self, log_path: Path, fast_period: int = 10, slow_period: int = 30):
        super().__init__(log_path)
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._asset = None

    def initialize(self, context):
        super().initialize(context)  # Logs "initialize" event
        # Get asset reference from context (set by execution wrapper)
        if hasattr(context, "asset"):
            self._asset = context.asset

    def handle_data(self, context, data):
        super().handle_data(context, data)  # Logs "bar_received" event

        # Use rustybt's data.history() API for indicator calculation
        prices = data.history(self._asset, "close", self._slow_period, "1d")
        fast_sma = prices[-self._fast_period:].mean()
        slow_sma = prices.mean()

        # Log indicator values (Layer 2)
        self.log_signal("fast_sma", fast_sma, asset=str(self._asset),
                       simulation_timestamp=self._current_simulation_timestamp)

        # Execute using rustybt's order API
        if fast_sma > slow_sma:
            order_target_percent(self._asset, 1.0)
            self.log_order_created("market", str(self._asset), 100,
                                  simulation_timestamp=self._current_simulation_timestamp)

class BacktraderValidatedStrategy(bt.Strategy):
    """Parallel logging for Backtrader reference implementation."""
    def __init__(self):
        self._log_event("initialize", {"params": self.params._getkwargs()})
        super().__init__()
```

**Note:** The rustybt validated strategies use rustybt's real APIs:
- `data.history()` for price data and indicator calculation
- `order_target_percent()` for trade execution via rustybt's broker
- `context.portfolio` for position and cash tracking

**2. Log Schema**
```json
{
  "timestamp": "2020-01-15T09:30:00",
  "layer": "data|signals|orders|broker|portfolio",
  "event": "bar_received|signal_generated|order_created|fill_executed|portfolio_updated",
  "asset": "AAPL",
  "data": {...}
}
```

**3. Comparison Engine**
```python
def compare_layer(rustybt_logs: pl.DataFrame, backtrader_logs: pl.DataFrame,
                  layer: str, tolerances: dict) -> list[Discrepancy]:
    """Compare logs for specific validation layer."""
    # Filter to layer
    rb_layer = rustybt_logs.filter(pl.col("layer") == layer)
    bt_layer = backtrader_logs.filter(pl.col("layer") == layer)

    # Apply layer-specific comparison logic
    comparator = LAYER_COMPARATORS[layer]
    return comparator.compare(rb_layer, bt_layer, tolerances)
```

### Affects FR Categories
All categories - this is the foundational pattern enabling framework-agnostic validation.

### Implementation Guide
1. Implement `ValidatedStrategy` base classes for both frameworks
2. Implement 4 strategies using both base classes (identical logic)
3. Execute strategies, generate JSONL logs
4. Parse logs into Polars DataFrames
5. Apply layer-specific comparison logic
6. Report discrepancies as BUG or DESIGN classifications

## Implementation Patterns

### Pattern 1: Consistent Event Logging

**Convention:** All log events follow standard schema
```python
{
    "timestamp": ISO8601_string,
    "layer": "data|signals|orders|broker|portfolio",
    "event": descriptive_event_name,
    "asset": asset_symbol_or_null,
    "data": dict_of_relevant_data
}
```

**Enforcement:** `ValidatedStrategy` base classes enforce schema; linter checks via custom mypy plugin

### Pattern 2: Tolerance-Based Comparison

**Convention:** Each layer has YAML tolerance configuration
```yaml
# layer_1_tolerances.yaml
timestamp_window_seconds: 0.001  # 1ms tolerance
price_decimals: 4                # 4 decimal places
volume_tolerance_pct: 0.01       # 1% volume difference allowed
```

**Enforcement:** Load tolerances in `conftest.py`, pass to comparators; document all tolerances in layer specifications

### Pattern 3: Subprocess Isolation

**Convention:** Execute rustybt and Backtrader in separate subprocesses
```python
def run_rustybt_strategy(strategy_path, data_path, output_log):
    subprocess.run([
        "python", "-m", "rustybt.validation.runner",
        "--strategy", strategy_path,
        "--data", data_path,
        "--output", output_log
    ])

def run_backtrader_strategy(strategy_path, data_path, output_log):
    subprocess.run([
        "python", "-m", "rustybt.validation.runner_backtrader",
        "--strategy", strategy_path,
        "--data", data_path,
        "--output", output_log
    ])
```

**Enforcement:** Never import both frameworks in same process; CI enforces via import linter

### Pattern 4: Finding Classification Workflow

**Convention:** All findings must be classified as BUG or DESIGN
```yaml
# findings.yaml
findings:
  - id: FIND-001
    layer: signals
    description: "RSI calculation differs by 0.05"
    classification: DESIGN
    rationale: "rustybt uses Wilder's smoothing; Backtrader uses EMA"
    documented_in: "docs/validation/design-differences.md#rsi-calculation"
    investigated_by: ".smirk"
    investigated_at: "2025-11-23T23:00:00Z"
```

**Enforcement:** CLI enforces classification before marking finding as resolved; unclassified findings block validation completion

## Consistency Rules

### Naming Conventions

**Files:**
- Test modules: `test_layer_{N}_{layer_name}.py` (e.g., `test_layer_1_data.py`)
- Strategy implementations: `{strategy_name}.py` in `strategies/rustybt/` or `strategies/backtrader/`
- Session IDs: `{YYYYMMDD}-{HHMMSS}-{strategy_name}` (e.g., `20251123-230000-sma_crossover`)

**Code:**
- Validation classes: `{Framework}ValidatedStrategy` (e.g., `RustyBTValidatedStrategy`)
- Comparator classes: `Layer{N}{Name}Comparator` (e.g., `Layer1DataComparator`)
- Finding types: `Discrepancy`, `BugFinding`, `DesignFinding`

### Code Organization

**Validation Library Structure:**
```
rustybt/validation/
├── base_strategy.py    # Base classes for both frameworks
├── session.py          # SessionManager, Session model
├── log_parser.py       # LogParser, log schema validation
├── comparators.py      # All layer comparators
├── models.py           # Data models
├── reporting.py        # Report generation
└── cli.py              # CLI commands
```

**Test Organization:**
```
tests/validation/
├── conftest.py              # Shared fixtures
├── test_layer_*.py          # One file per layer
├── strategies/              # Dual implementations
└── config/                  # Tolerance configs
```

### Error Handling

**Strategy Execution Errors:**
- Capture all exceptions during strategy execution
- Log to `session/errors.log`
- Mark session as `FAILED` in `session.yaml`
- Provide clear error message with traceback

**Log Parsing Errors:**
- Validate log schema on parse
- Reject malformed logs with clear error message
- Suggest fixes (e.g., "Missing 'layer' field in line 42")

**Comparison Errors:**
- Handle missing data gracefully (log warnings, don't crash)
- Report comparison failures as findings (not exceptions)
- Provide context: expected vs actual values

### Logging Strategy

**Application Logging:**
- Use Python `logging` module with structured format
- Levels: DEBUG (verbose), INFO (progress), WARNING (issues), ERROR (failures)
- Output: Console (INFO+), File `session/validation.log` (DEBUG+)

**Validation Event Logging:**
- Use JSONL for structured validation events
- Schema-validated on write
- Human-readable for debugging, machine-parseable for testing

## Data Architecture

### Data Models

**Session Model:**
```python
@dataclass
class Session:
    id: str                          # Session identifier
    created_at: datetime             # Session creation timestamp
    strategy_name: str               # Strategy being validated
    rustybt_version: str             # rustybt version
    backtrader_version: str          # Backtrader version
    python_version: str              # Python version
    status: Literal["IN_PROGRESS", "COMPLETED", "FAILED"]
    data_fixture: Path               # Path to test data
    findings: list[Finding]          # All findings
```

**Finding Model:**
```python
@dataclass
class Finding:
    id: str                          # Finding identifier (FIND-001)
    layer: Literal["data", "signals", "orders", "broker", "portfolio"]
    description: str                 # Human-readable description
    classification: Optional[Literal["BUG", "DESIGN"]]
    rationale: Optional[str]         # Classification rationale
    investigated_by: Optional[str]   # Investigator
    investigated_at: Optional[datetime]
    resolved: bool                   # Whether bug fixed or documented
    rustybt_value: Any               # rustybt observed value
    backtrader_value: Any            # Backtrader observed value
```

**Discrepancy Model:**
```python
@dataclass
class Discrepancy:
    layer: str
    event: str
    timestamp: datetime
    asset: Optional[str]
    field: str                       # Which field differs
    rustybt_value: Any
    backtrader_value: Any
    tolerance: Any                   # Configured tolerance
    exceeded_by: Any                 # How much tolerance exceeded
```

### Data Flow

```
1. Data Preparation
   └→ Generate shared Parquet fixture (validation_data.parquet)
      - Same data consumed by both frameworks
      - Deterministic via seeded random generation

2. Strategy Execution
   ├→ rustybt subprocess:
   │   └→ DataBundle → TradingAlgorithm → real Broker → JSONL
   └→ Backtrader subprocess:
       └→ PandasData → Cerebro → Broker → JSONL

3. Log Parsing
   ├→ Parse JSONL → Validate schema
   └→ Convert to Parquet → Cache for fast queries

4. Comparison
   ├→ Load Parquet logs → Filter by layer
   ├→ Apply layer comparator → Generate discrepancies
   └→ Write findings to findings.yaml

5. Investigation
   ├→ Load findings → Present to user
   ├→ User classifies → BUG or DESIGN
   └→ Update findings.yaml → Mark resolved

6. Reporting
   ├→ Load session + findings
   ├→ Generate per-layer reports → Markdown
   └→ Generate summary report → Validation status
```

**Key Integration Point (Epic X):** rustybt validated strategies execute through the real TradingAlgorithm engine, not a homebrew simulation. This ensures validation compares actual rustybt behavior against Backtrader.

## API Contracts

### CLI Interface

```bash
# Session management
rustybt-validate session create --strategy sma_crossover --data validation_data.parquet
rustybt-validate session list [--status COMPLETED]
rustybt-validate session show <session_id>
rustybt-validate session resume <session_id>

# Execution
rustybt-validate run <session_id>

# Investigation
rustybt-validate investigate <session_id> [--layer data]
rustybt-validate classify <finding_id> --type BUG|DESIGN --rationale "..."

# Reporting
rustybt-validate report <session_id> [--layer data] [--format md|json]
rustybt-validate status  # Overall validation status across all sessions
```

### Python API

```python
from rustybt.validation import SessionManager, run_validation

# Create session
session = SessionManager.create(
    strategy_name="sma_crossover",
    data_fixture="validation_data.parquet"
)

# Run validation
results = run_validation(session)

# Investigate findings
for finding in session.findings:
    if not finding.classification:
        # Present finding to user, get classification
        finding.classify(type="BUG", rationale="...")

# Generate report
report = session.generate_report(layer="data")
```

### Pytest Integration

```python
@pytest.mark.layer_1_data
def test_data_handling_sma_crossover(validation_session, sma_crossover_logs):
    """Validate data handling layer for SMA crossover strategy."""
    discrepancies = compare_layer(
        rustybt_logs=sma_crossover_logs["rustybt"],
        backtrader_logs=sma_crossover_logs["backtrader"],
        layer="data",
        tolerances=load_tolerances("layer_1_tolerances.yaml")
    )

    # Allow known DESIGN differences
    unexpected = [d for d in discrepancies if not is_known_design(d)]

    assert len(unexpected) == 0, f"Found {len(unexpected)} unexpected discrepancies"
```

## Security Architecture

**Not Applicable** - This is a developer tool for internal use, not production software handling sensitive data.

**Note:** Validation framework does NOT handle:
- Live trading credentials
- Production data
- User authentication
- Network communication

## Performance Considerations

### Target Performance

- **Session creation:** <1 second
- **Strategy execution:** Variable (depends on strategy complexity)
- **Log parsing:** <5 seconds per 100MB JSONL file
- **Comparison per layer:** <10 seconds for typical strategy
- **Full validation (5 layers):** <2 minutes total

### Optimization Strategies

1. **Parquet Caching:** Convert JSONL to Parquet for 10-100x faster queries
2. **Lazy Loading:** Only load logs for layers being tested
3. **Parallel Execution:** Run rustybt and Backtrader strategies in parallel
4. **Incremental Comparison:** Skip layers that previously passed (resume mode)

### Memory Management

- Stream large JSONL files (don't load entirely into memory)
- Use Polars lazy evaluation for log processing
- Clear session cache after validation complete

## Deployment Architecture

**Not Applicable** - No deployment; runs locally on developer machines.

**CI/CD Integration (Future):**
- Run validation tests in GitHub Actions
- Store session results as artifacts
- Fail CI if new BUG findings detected

## Development Environment

### Prerequisites

```bash
# Python 3.12+
python --version  # Must be 3.12+

# rustybt development environment (already setup)
# See main rustybt docs/contributing/setup.md
```

### Setup Commands

```bash
# Install validation framework dependencies
pip install -e ".[dev,test,validation]"

# Install Backtrader (in separate venv or same environment)
pip install backtrader>=1.9.78

# Create validation directories
mkdir -p validation-sessions
mkdir -p tests/validation/fixtures

# Generate test data fixture
python -m rustybt.validation.generate_fixture \
    --output tests/validation/fixtures/validation_data.parquet \
    --assets 50 \
    --start 2020-01-01 \
    --end 2021-12-31 \
    --seed 42

# Verify setup
rustybt-validate --version
pytest tests/validation/ --collect-only
```

### Running Validation

```bash
# Create validation session
rustybt-validate session create \
    --strategy sma_crossover \
    --data tests/validation/fixtures/validation_data.parquet

# Run validation (executes both frameworks, compares logs)
rustybt-validate run <session_id>

# View results
rustybt-validate report <session_id>

# Run via pytest
pytest tests/validation/test_layer_1_data.py -v
```

## Architecture Decision Records (ADRs)

### ADR-001: Dual-Location Architecture
**Decision:** Split validation framework between `rustybt/validation/` (library) and `tests/validation/` (tests)

**Rationale:**
- Reusable validation utilities benefit from library location
- Test execution belongs in tests/
- Separates concerns: framework code vs test code

**Alternatives Considered:**
- Single location in `tests/` - rejected (utilities not reusable)
- Single location in `rustybt/` - rejected (bloats end-user package)

**Status:** Accepted

---

### ADR-002: Log-Based Validation vs Direct API Comparison
**Decision:** Use structured logs for comparison instead of direct API calls

**Rationale:**
- rustybt and Backtrader have incompatible APIs
- Logs decouple frameworks completely
- Enables temporal analysis (event ordering)
- Provides audit trail for debugging

**Alternatives Considered:**
- Mock/adapter layer to unify APIs - rejected (too complex, fragile)
- Manual result comparison only - rejected (insufficient granularity)

**Status:** Accepted

---

### ADR-003: YAML for Session Storage
**Decision:** Use YAML files for session metadata and findings

**Rationale:**
- Human-readable and version-controllable
- Simple to implement and maintain
- Easy to inspect/edit manually when needed
- Sufficient for expected data volumes (<1000 sessions)

**Alternatives Considered:**
- SQLite - rejected for MVP (over-engineering)
- JSON - considered equivalent, chose YAML for readability

**Status:** Accepted

---

### ADR-004: Subprocess Isolation for Framework Execution
**Decision:** Run rustybt and Backtrader in separate subprocesses

**Rationale:**
- Prevents dependency conflicts
- Clean environment isolation
- Easier to version-pin each framework
- Mirrors real-world usage patterns

**Alternatives Considered:**
- Same process execution - rejected (import conflicts likely)
- Docker containers - rejected (unnecessary complexity for MVP)

**Status:** Accepted

---

### ADR-005: Real rustybt Engine Integration (Epic X)
**Decision:** Replace homebrew broker simulation with actual rustybt TradingAlgorithm integration

**Context:**
The initial validation framework implementation included a homebrew broker simulation (`SimulatedPosition`, `_cash`, `_execute_order()`) that was intended as a placeholder. This implementation meant we were comparing a custom mock against Backtrader, rather than validating rustybt's actual behavior.

**Rationale:**
- Validation framework's core purpose is to prove rustybt's correctness
- Homebrew simulation defeats this purpose entirely (validates mock, not rustybt)
- Real integration validates actual rustybt behavior:
  - `data.history()` for indicator data access
  - `order_target_percent()` for trade execution
  - `context.portfolio` for position/cash tracking
  - Real broker simulation for fills/commissions

**Implementation (Epic X):**
- Removed `SimulatedPosition` class and all homebrew simulation code
- `RustyBTValidatedStrategy` now uses mixin pattern with logging hooks
- `execute_rustybt.py` uses rustybt's `run_algorithm()` entry point
- All 4 strategies reimplemented using real rustybt APIs
- JSONL log schema preserved for comparison compatibility

**Alternatives Considered:**
1. Continue with homebrew - Rejected (invalidates all validation results)
2. Partial integration (data only) - Rejected (incomplete coverage)
3. Full integration - Accepted (meets validation goals)

**Status:** Accepted

**Date:** 2025-11-29

---

_Generated by BMAD Decision Architecture Workflow v1.0_
_Date: 2025-11-23 (Updated: 2025-11-29)_
_For: .smirk_
