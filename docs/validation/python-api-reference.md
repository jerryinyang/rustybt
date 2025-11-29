# Python API Reference

Complete Python API reference for the rustybt validation framework.

## Quick Start

```python
from pathlib import Path
from rustybt.validation.session import SessionManager
from rustybt.validation.models import Session, Finding
from rustybt.validation.comparators import Layer1DataComparator
from rustybt.validation.reporting import ReportGenerator

# Create session manager
sm = SessionManager()

# Create a validation session
session = sm.create_session(
    strategy_name="sma_crossover",
    data_fixture=Path("tests/validation/fixtures/validation_data.parquet"),
    rustybt_version="0.3.4",
    backtrader_version="1.9.78",
)

# List sessions
for s in sm.list_sessions():
    print(f"{s.id}: {s.status}")

# Generate report
generator = ReportGenerator(session)
report = generator.generate_markdown()
```

---

## SessionManager

```python
from rustybt.validation.session import SessionManager
```

Manages validation sessions with YAML persistence.

### Constructor

```python
SessionManager(sessions_dir: Path = Path("validation-sessions"))
```

**Parameters:**
- `sessions_dir`: Directory for session storage. Created automatically if it doesn't exist.

---

### create_session()

Create a new validation session with duplicate detection.

```python
def create_session(
    strategy_name: str,
    data_fixture: Path,
    rustybt_version: str,
    backtrader_version: str,
    force: bool = False,
) -> Session
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `strategy_name` | `str` | Yes | - | Name of the strategy to validate |
| `data_fixture` | `Path` | Yes | - | Path to test data fixture |
| `rustybt_version` | `str` | Yes | - | Version of rustybt under test |
| `backtrader_version` | `str` | Yes | - | Version of Backtrader reference |
| `force` | `bool` | No | `False` | If True, supersede existing IN_PROGRESS sessions |

**Returns:** `Session` - Newly created session

**Raises:**
- `DuplicateSessionError` - If duplicate IN_PROGRESS session exists and `force=False`

**Example:**

```python
from pathlib import Path
from rustybt.validation.session import SessionManager

sm = SessionManager()

# Create new session
session = sm.create_session(
    strategy_name="sma_crossover",
    data_fixture=Path("tests/validation/fixtures/validation_data.parquet"),
    rustybt_version="0.3.4",
    backtrader_version="1.9.78",
)
print(f"Created: {session.id}")

# Force override existing session
session = sm.create_session(
    strategy_name="sma_crossover",
    data_fixture=Path("fixtures/data.parquet"),
    rustybt_version="0.4.0",
    backtrader_version="1.9.78",
    force=True,
)
```

---

### load_session()

Load a session from YAML with automatic retry on transient failures.

```python
def load_session(session_id: str) -> Session
```

**Parameters:**
- `session_id`: Session identifier string

**Returns:** `Session` - Loaded session

**Raises:**
- `FileNotFoundError` - If session does not exist

**Example:**

```python
session = sm.load_session("20251129-143000-sma_crossover")
print(f"Strategy: {session.strategy_name}")
print(f"Status: {session.status}")
print(f"Findings: {len(session.findings)}")
```

---

### list_sessions()

List all sessions with optional status filter.

```python
def list_sessions(status: str | None = None) -> list[Session]
```

**Parameters:**
- `status`: Optional status filter (`"IN_PROGRESS"`, `"COMPLETED"`, `"FAILED"`)

**Returns:** List of `Session` objects sorted by `created_at` descending

**Example:**

```python
# List all sessions
all_sessions = sm.list_sessions()

# List only completed sessions
completed = sm.list_sessions(status="COMPLETED")
for s in completed:
    print(f"{s.id}: {len(s.findings)} findings")
```

---

### find_sessions()

Find sessions matching the given criteria (AND logic).

```python
def find_sessions(
    strategy: str | None = None,
    status: str | None = None,
    stage: SessionStage | None = None,
    since: datetime | None = None,
    has_findings: bool = False,
) -> list[Session]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | `str \| None` | `None` | Filter by strategy name |
| `status` | `str \| None` | `None` | Filter by status |
| `stage` | `SessionStage \| None` | `None` | Filter by session stage |
| `since` | `datetime \| None` | `None` | Only sessions created after this time |
| `has_findings` | `bool` | `False` | Only include sessions with findings |

**Returns:** List of matching `Session` objects

**Example:**

```python
from datetime import datetime
from rustybt.validation.models import SessionStage

# Find sessions for a strategy
sma_sessions = sm.find_sessions(strategy="sma_crossover")

# Find recent sessions with findings
recent = sm.find_sessions(
    since=datetime(2025, 1, 1),
    has_findings=True,
)

# Find sessions in investigation stage
investigating = sm.find_sessions(stage=SessionStage.INVESTIGATING)
```

---

### update_session()

Update an existing session (persists to YAML).

```python
def update_session(session: Session) -> None
```

**Parameters:**
- `session`: Session to update

**Example:**

```python
session = sm.load_session("20251129-143000-sma_crossover")
session.status = "COMPLETED"
sm.update_session(session)
```

---

### update_stage()

Update session stage with timestamp and validation.

```python
def update_stage(session: Session, new_stage: SessionStage) -> None
```

**Parameters:**
- `session`: Session to update
- `new_stage`: New stage to transition to

**Raises:**
- `ValueError` - If the stage transition is not allowed

**Valid Transitions:**
```
CREATED -> EXECUTING, FAILED
EXECUTING -> EXECUTED, FAILED
EXECUTED -> COMPARING, FAILED
COMPARING -> COMPARED, FAILED
COMPARED -> INVESTIGATING, FAILED
INVESTIGATING -> COMPLETED, COMPARED, FAILED
FAILED -> CREATED (retry)
```

**Example:**

```python
from rustybt.validation.models import SessionStage

session = sm.load_session("20251129-143000-sma_crossover")
sm.update_stage(session, SessionStage.EXECUTING)
# ... run execution ...
sm.update_stage(session, SessionStage.EXECUTED)
```

---

### add_finding()

Add a finding to a session with duplicate detection.

```python
def add_finding(session: Session, finding: Finding) -> None
```

**Parameters:**
- `session`: Session to add finding to
- `finding`: Finding to add

**Raises:**
- `DuplicateFindingError` - If finding with same ID already exists

**Example:**

```python
from rustybt.validation.models import Finding

finding = Finding(
    id="layer_1_finding_001",
    layer="data",
    description="Bar count mismatch",
    rustybt_value=1000,
    backtrader_value=1001,
)
sm.add_finding(session, finding)
```

---

### resume()

Resume session from last completed stage.

```python
def resume(session_id: str) -> Session
```

**Parameters:**
- `session_id`: ID of session to resume

**Returns:** Session ready for continuation

**Raises:**
- `ValueError` - If session is already COMPLETED
- `FileNotFoundError` - If session does not exist

**Example:**

```python
session = sm.resume("20251129-143000-sma_crossover")
print(f"Resuming from stage: {session.stage}")
```

---

### delete_session()

Delete a session and all its files permanently.

```python
def delete_session(session_id: str, dry_run: bool = False) -> bool
```

**Parameters:**
- `session_id`: ID of session to delete
- `dry_run`: If True, only simulate deletion

**Returns:** `True` if deletion was successful

**Raises:**
- `FileNotFoundError` - If session does not exist

---

### archive_session()

Archive a session to a compressed tarball.

```python
def archive_session(
    session_id: str,
    archive_dir: Path | None = None,
    dry_run: bool = False,
) -> Path | None
```

**Parameters:**
- `session_id`: ID of session to archive
- `archive_dir`: Directory to store archive (default: `sessions_dir/archive`)
- `dry_run`: If True, only simulate archiving

**Returns:** Path to created archive file, or `None` in dry_run mode

---

### cleanup_sessions()

Clean up old sessions by deleting or archiving.

```python
def cleanup_sessions(
    older_than_days: int | None = None,
    status: str | None = None,
    dry_run: bool = False,
    archive: bool = False,
) -> list[str]
```

**Parameters:**
- `older_than_days`: Only clean sessions older than N days
- `status`: Only clean sessions with this status
- `dry_run`: If True, only simulate cleanup
- `archive`: If True, archive sessions instead of deleting

**Returns:** List of session IDs that were (or would be) cleaned up

**Example:**

```python
# Archive completed sessions older than 30 days
cleaned = sm.cleanup_sessions(
    older_than_days=30,
    status="COMPLETED",
    archive=True,
)
print(f"Archived {len(cleaned)} sessions")
```

---

## Data Models

### Session

```python
from rustybt.validation.models import Session
```

Validation session metadata and tracking.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique session identifier (format: `YYYYMMDD-HHMMSS-strategy`) |
| `created_at` | `datetime` | Session creation timestamp |
| `strategy_name` | `str` | Name of the strategy being validated |
| `rustybt_version` | `str` | Version of rustybt under test |
| `backtrader_version` | `str` | Version of Backtrader reference |
| `python_version` | `str` | Python interpreter version |
| `status` | `Literal["IN_PROGRESS", "EXECUTED", "COMPLETED", "FAILED", "SUPERSEDED"]` | Current session state |
| `data_fixture` | `Path` | Path to test data fixture |
| `findings` | `list[Finding]` | List of discrepancies found |
| `stage` | `SessionStage` | Current lifecycle stage |
| `stage_started_at` | `datetime \| None` | When current stage began |
| `execution_completed_at` | `datetime \| None` | When execution finished |
| `comparison_completed_at` | `datetime \| None` | When comparison finished |
| `layers_completed` | `list[str]` | Completed validation layer names |
| `activities` | `list[Activity]` | Audit trail of activities |

**Methods:**

#### log_activity()

Log an activity to the session's audit trail.

```python
def log_activity(
    action: str,
    message: str | None = None,
    actor: str = "system",
) -> None
```

**Example:**

```python
session.log_activity("note", "Investigation paused for review", "developer")
session.log_activity("finding_classified", "Classified FIND-001 as BUG")
```

---

### SessionStage

```python
from rustybt.validation.models import SessionStage
```

Session lifecycle stages (Enum).

| Value | Description |
|-------|-------------|
| `CREATED` | Session initialized, ready to start |
| `EXECUTING` | Strategies actively running in both frameworks |
| `EXECUTED` | Both frameworks completed, logs collected |
| `COMPARING` | Running layer-by-layer comparison |
| `COMPARED` | Discrepancies identified, ready for investigation |
| `INVESTIGATING` | Manual investigation in progress |
| `COMPLETED` | All findings resolved, session finished |
| `FAILED` | Error occurred during any stage |

---

### Finding

```python
from rustybt.validation.models import Finding
```

Layer-specific discrepancy with classification.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique finding identifier (e.g., `"layer_1_finding_001"`) |
| `layer` | `Literal["data", "signals", "orders", "broker", "portfolio"]` | Validation layer |
| `description` | `str` | Human-readable description |
| `classification` | `Literal["BUG", "DESIGN"] \| None` | BUG, DESIGN, or None (pending) |
| `rationale` | `str \| None` | Explanation for classification |
| `investigated_by` | `str \| None` | Person/agent who investigated |
| `investigated_at` | `datetime \| None` | Timestamp of investigation |
| `resolved` | `bool` | Whether the finding has been resolved |
| `resolved_at` | `datetime \| None` | When the fix was verified |
| `regression_test` | `str \| None` | Path to regression test |
| `rustybt_value` | `Any` | Value from rustybt execution |
| `backtrader_value` | `Any` | Value from Backtrader execution |
| `severity` | `str \| None` | Bug severity (Critical/Major/Minor) - BUG only |
| `affected_components` | `list[str]` | Affected file paths - BUG only |
| `suggested_fix` | `str \| None` | Suggested fix description - BUG only |
| `design_rationale` | `str \| None` | Explanation for difference - DESIGN only |
| `design_choice` | `str \| None` | Preferred approach - DESIGN only |
| `user_impact` | `str \| None` | Impact on users - DESIGN only |

**Example:**

```python
from rustybt.validation.models import Finding

# Create a finding
finding = Finding(
    id="layer_3_finding_001",
    layer="orders",
    description="Order fill price mismatch",
    rustybt_value=152.35,
    backtrader_value=152.38,
)

# Classify as BUG
finding.classification = "BUG"
finding.severity = "Minor"
finding.affected_components = ["rustybt/broker/execution.py"]
finding.rationale = "Price calculation off by 0.02%"
```

---

### Discrepancy

```python
from rustybt.validation.comparators import Discrepancy
```

Specific value mismatch discovered during comparison.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `layer` | `str` | Validation layer |
| `event` | `str` | Event type (e.g., `"bar_received"`, `"order_filled"`) |
| `timestamp` | `str \| None` | When the discrepancy occurred |
| `field` | `str` | Field name that differs |
| `rustybt_value` | `Any` | Value from rustybt |
| `backtrader_value` | `Any` | Value from Backtrader |
| `tolerance` | `Any` | Tolerance threshold that was exceeded |
| `exceeded_by` | `Any` | Amount by which tolerance was exceeded |
| `asset` | `str \| None` | Asset symbol |
| `severity` | `str` | Severity level (`"critical"`, `"warning"`, `"info"`) |
| `description` | `str` | Human-readable description |

---

### Activity

```python
from rustybt.validation.models import Activity
```

Timestamped activity record for audit trail.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `timestamp` | `datetime` | When the activity occurred |
| `action` | `str` | Type of action (e.g., `"created"`, `"finding_added"`) |
| `actor` | `str` | Who performed the action (`"system"` or username) |
| `details` | `dict[str, Any] \| None` | Additional context |

---

## Comparators

Layer comparators validate specific aspects of rustybt behavior against Backtrader.

### BaseComparator

Abstract base class for layer comparators.

```python
from rustybt.validation.comparators import BaseComparator

class BaseComparator(ABC):
    @property
    @abstractmethod
    def layer_name(self) -> str: ...

    @abstractmethod
    def compare(
        self,
        rustybt_logs: pl.DataFrame,
        backtrader_logs: pl.DataFrame,
    ) -> ComparisonResult: ...
```

---

### Layer1DataComparator

Comparator for Layer 1: Data Handling.

```python
from rustybt.validation.comparators import Layer1DataComparator
from rustybt.validation.tolerance import Layer1Tolerances
```

**Validates:**
- Lookahead bias detection (zero tolerance)
- Bar alignment between frameworks
- OHLCV value comparison with tolerance
- Data integrity (missing bars, gaps, anomalies)

**Constructor:**

```python
Layer1DataComparator(tolerances: Layer1Tolerances | None = None)
```

**Methods:**

```python
def compare(
    self,
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
) -> ComparisonResult

def detect_lookahead_bias(logs: pl.DataFrame) -> list[Discrepancy]

def compare_bar_alignment(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
) -> list[Discrepancy]

def validate_data_integrity(
    logs: pl.DataFrame,
    source: str = "unknown",
) -> list[Discrepancy]
```

**Example:**

```python
from rustybt.validation.comparators import Layer1DataComparator
from rustybt.validation.log_parser import parse_log

comparator = Layer1DataComparator()

rb_logs = parse_log(Path("logs/rustybt.jsonl"))
bt_logs = parse_log(Path("logs/backtrader.jsonl"))

result = comparator.compare(rb_logs, bt_logs)
print(f"Layer: {result.layer}")
print(f"Passed: {result.passed}")
print(f"Discrepancies: {len(result.discrepancies)}")
```

---

### Layer2SignalComparator

Comparator for Layer 2: Signal Computation.

```python
from rustybt.validation.comparators import Layer2SignalComparator
```

**Validates:**
- Indicator value comparison with tolerance
- Signal generation timing
- Signal count matching
- Boolean signal exact match (buy/sell)

---

### Layer3OrdersComparator

Comparator for Layer 3: Order Lifecycle.

```python
from rustybt.validation.comparators import Layer3OrdersComparator
```

**Validates:**
- Order creation comparison (count, type, quantity, timing)
- Order execution comparison (fill price, fill quantity)
- Order state transition comparison (CREATED->SUBMITTED->FILLED)
- Partial fill handling

**Note:** Orders are matched by timestamp + asset + quantity, not order ID.

---

### Layer4BrokerComparator

Comparator for Layer 4: Broker Transactions.

```python
from rustybt.validation.comparators import Layer4BrokerComparator
```

**Validates:**
- Transaction execution comparison (fills, commissions)
- Cash balance comparison
- Slippage comparison

---

### Layer5PortfolioComparator

Comparator for Layer 5: Portfolio Returns.

```python
from rustybt.validation.comparators import Layer5PortfolioComparator
```

**Validates:**
- Portfolio value comparison
- Returns comparison
- Sharpe ratio comparison
- Drawdown comparison

---

### ComparisonResult

Result of a layer comparison.

```python
from rustybt.validation.comparators import ComparisonResult
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `layer` | `str` | Layer name |
| `passed` | `bool` | True if no critical discrepancies |
| `discrepancies` | `list[Discrepancy]` | All discrepancies found |
| `stats` | `dict[str, Any]` | Comparison statistics |

**Properties:**

- `critical_count` - Count of critical discrepancies
- `warning_count` - Count of warning discrepancies

---

## Report Generation

### ReportGenerator

```python
from rustybt.validation.reporting import ReportGenerator
```

Generate validation reports from session data.

**Constructor:**

```python
ReportGenerator(session: Session)
```

**Methods:**

#### generate_markdown()

Generate a markdown report.

```python
def generate_markdown(self) -> str
```

**Returns:** Markdown-formatted report string

#### generate_json()

Generate a JSON report.

```python
def generate_json(self) -> dict[str, Any]
```

**Returns:** Dictionary containing structured report data

#### save_markdown()

Save markdown report to session directory.

```python
def save_markdown(directory: Path | None = None) -> Path
```

**Returns:** Path to the saved report file

#### save_json()

Save JSON report to session directory.

```python
def save_json(directory: Path | None = None) -> Path
```

**Returns:** Path to the saved report file

**Example:**

```python
from rustybt.validation.reporting import ReportGenerator

session = sm.load_session("20251129-143000-sma_crossover")
generator = ReportGenerator(session)

# Generate markdown
markdown = generator.generate_markdown()
print(markdown)

# Generate JSON for CI
json_data = generator.generate_json()
print(f"Status: {json_data['status']}")
print(f"Bug count: {json_data['summary']['bug_count']}")

# Save to file
report_path = generator.save_markdown()
print(f"Report saved to: {report_path}")
```

---

### LayerReportGenerator

Generate cross-strategy reports for a specific validation layer.

```python
from rustybt.validation.reporting import LayerReportGenerator
```

**Constructor:**

```python
LayerReportGenerator(layer: str, session_manager: SessionManager)
```

**Parameters:**
- `layer`: Layer name (`"data"`, `"signals"`, `"orders"`, `"broker"`, `"portfolio"`)
- `session_manager`: SessionManager for loading sessions

**Methods:**

```python
def generate(self) -> str
def save(output_dir: Path | None = None) -> Path
def get_layer_findings(self) -> list[Finding]
def identify_common_patterns(findings: list, sessions: list) -> list[CommonPattern]
```

**Example:**

```python
from rustybt.validation.reporting import LayerReportGenerator

generator = LayerReportGenerator("signals", sm)
report = generator.generate()

# Get all findings for this layer
findings = generator.get_layer_findings()
print(f"Total signal findings: {len(findings)}")

# Save to file
path = generator.save()
print(f"Layer report saved to: {path}")
```

---

### StrategyReportGenerator

Generate validation reports for a specific strategy across all layers.

```python
from rustybt.validation.reporting import StrategyReportGenerator
```

**Constructor:**

```python
StrategyReportGenerator(strategy_name: str, session_manager: SessionManager)
```

**Methods:**

```python
def generate(self) -> str
def save(output_dir: Path | None = None) -> Path
def calculate_overall_status(session: Session) -> str
def generate_recommendations(findings: list[Finding]) -> list[str]
```

**Example:**

```python
from rustybt.validation.reporting import StrategyReportGenerator

generator = StrategyReportGenerator("sma_crossover", sm)
report = generator.generate()
print(report)

# Get overall status
session = sm.find_sessions(strategy="sma_crossover")[0]
status = generator.calculate_overall_status(session)
print(f"Overall: {status}")  # "✓ VALIDATED", "⚠ PARTIAL", or "✗ FAILED"
```

---

### StatusDashboard

Generate overall validation status dashboard.

```python
from rustybt.validation.reporting import StatusDashboard
```

**Constructor:**

```python
StatusDashboard(session_manager: SessionManager | None = None)
```

**Methods:**

```python
def get_data(self) -> DashboardData
def render(self) -> str
def to_json(self) -> dict[str, Any]
def is_healthy(self) -> bool
def get_exit_code(self) -> int
```

**Example:**

```python
from rustybt.validation.reporting import StatusDashboard

dashboard = StatusDashboard(sm)

# Render ASCII dashboard
print(dashboard.render())

# Get JSON for CI
data = dashboard.to_json()
print(f"Confidence: {data['confidence']:.1f}%")
print(f"Healthy: {data['healthy']}")

# Use in CI
exit_code = dashboard.get_exit_code()
# Returns 0 if healthy, 1 if unhealthy
```

---

### DocumentationGenerator

Generate user-facing documentation from validation findings.

```python
from rustybt.validation.reporting import DocumentationGenerator
```

**Constructor:**

```python
DocumentationGenerator(
    session_manager: SessionManager | None = None,
    output_dir: Path | None = None,
)
```

**Methods:**

```python
def generate_design_differences(self) -> str
def generate_bug_fixes(self) -> str
def save_design_differences(self) -> Path
def save_bug_fixes(self) -> Path
def generate_all(self) -> tuple[Path, Path]
```

**Example:**

```python
from rustybt.validation.reporting import DocumentationGenerator

generator = DocumentationGenerator(sm)

# Generate all documentation
design_path, bugs_path = generator.generate_all()
print(f"Design differences: {design_path}")
print(f"Bug fixes: {bugs_path}")

# Preview without saving
content = generator.generate_design_differences()
print(content)
```

---

### CompletionTracker

Track validation completion and suggest next steps.

```python
from rustybt.validation.reporting import CompletionTracker, ValidationProgress
```

**Methods:**

```python
def get_progress(self) -> ValidationProgress
def get_incomplete_strategies(self) -> list[str]
def get_next_steps(self) -> list[str]
def render(self) -> str
```

**Example:**

```python
from rustybt.validation.reporting import CompletionTracker

tracker = CompletionTracker(sm)
progress = tracker.get_progress()

print(f"Strategy completion: {progress.strategy_completion * 100:.1f}%")
print(f"Layer completion: {progress.layer_completion * 100:.1f}%")
print(f"Overall: {progress.overall * 100:.1f}%")

# Get incomplete strategies
for strategy in tracker.get_incomplete_strategies():
    missing = progress.missing_layers.get(strategy, [])
    print(f"  {strategy}: missing {', '.join(missing)}")

# Get next steps
for step in tracker.get_next_steps():
    print(f"  - {step}")

# Render progress display
print(tracker.render())
```

---

### NextActionsRecommender

Recommend next validation actions based on current state.

```python
from rustybt.validation.reporting import NextActionsRecommender, Recommendation
```

**Methods:**

```python
def recommend(self) -> list[Recommendation]
def render(self) -> str
```

**Example:**

```python
from rustybt.validation.reporting import NextActionsRecommender

recommender = NextActionsRecommender(sm)

for rec in recommender.recommend():
    print(f"[{rec.get_priority_label()}] {rec.action}")
    print(f"  Details: {rec.details}")
    print(f"  Command: {rec.command}")
    print()

# Render formatted display
print(recommender.render())
```

---

## Tolerance Configuration

```python
from rustybt.validation.tolerance import ToleranceConfig
```

Configurable tolerance values for validation comparison.

### ToleranceConfig

Complete tolerance configuration for all validation layers.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `layer_1` | `Layer1Tolerances` | Data handling tolerances |
| `layer_2` | `Layer2Tolerances` | Signal computation tolerances |
| `layer_3` | `Layer3Tolerances` | Order lifecycle tolerances |
| `layer_4` | `Layer4Tolerances` | Broker transaction tolerances |
| `layer_5` | `Layer5Tolerances` | Portfolio returns tolerances |

**Class Methods:**

```python
@classmethod
def load_from_yaml(cls, config_path: Path) -> ToleranceConfig

@classmethod
def load_from_directory(cls, config_dir: Path) -> ToleranceConfig
```

**Instance Methods:**

```python
def to_dict(self) -> dict[str, Any]
def with_overrides(self, **kwargs) -> ToleranceConfig
```

**Example:**

```python
from pathlib import Path
from rustybt.validation.tolerance import ToleranceConfig, get_default_tolerances

# Get default tolerances
config = get_default_tolerances()

# Load from YAML file
config = ToleranceConfig.load_from_yaml(Path("tolerances.yaml"))

# Load from directory with layer-specific files
config = ToleranceConfig.load_from_directory(Path("tests/validation/config"))

# Create with overrides for specific strategy
strict_config = config.with_overrides(
    layer_1_price_decimal_places=6,
    layer_5_returns_tolerance_pct=0.00001,
)

# Access layer tolerances
print(f"Price tolerance: {config.layer_1.price_tolerance}")
print(f"Signal exact match: {config.layer_2.signal_exact_match}")
```

---

### Layer Tolerance Classes

Each layer has its own tolerance dataclass:

#### Layer1Tolerances (Data Handling)

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `timestamp_window_ms` | `int` | `1` | Milliseconds allowed between framework timestamps |
| `price_decimal_places` | `int` | `4` | Decimal places for price comparison |
| `volume_tolerance_pct` | `float` | `0.001` | Percentage tolerance for volume |
| `bar_count_tolerance` | `int` | `0` | Allowed difference in bar counts |

#### Layer2Tolerances (Signals)

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `indicator_decimal_places` | `int` | `4` | Decimal places for indicator comparison |
| `signal_tolerance_pct` | `float` | `0.0001` | Percentage tolerance for signal values |
| `signal_exact_match` | `bool` | `True` | Whether boolean signals must match exactly |
| `signal_timestamp_window_ms` | `int` | `1` | Milliseconds for signal timestamp alignment |

#### Layer3Tolerances (Orders)

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `order_timestamp_window_ms` | `int` | `1` | Milliseconds for order timestamp alignment |
| `fill_price_decimal_places` | `int` | `4` | Decimal places for fill price comparison |
| `quantity_tolerance_pct` | `float` | `0.0001` | Percentage tolerance for order quantity |
| `order_id_exact_match` | `bool` | `False` | Whether order IDs must match |

#### Layer4Tolerances (Broker)

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `transaction_timestamp_window_ms` | `int` | `1` | Milliseconds for transaction timestamps |
| `commission_decimal_places` | `int` | `2` | Decimal places for commission comparison |
| `slippage_tolerance_pct` | `float` | `0.001` | Percentage tolerance for slippage |
| `cash_decimal_places` | `int` | `2` | Decimal places for cash comparison |

#### Layer5Tolerances (Portfolio)

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `portfolio_value_decimal_places` | `int` | `2` | Decimal places for portfolio value |
| `returns_tolerance_pct` | `float` | `0.0001` | Percentage tolerance for returns |
| `sharpe_decimal_places` | `int` | `4` | Decimal places for Sharpe ratio |
| `drawdown_tolerance_pct` | `float` | `0.0001` | Percentage tolerance for drawdown |

---

## Integration Examples

### pytest Fixture Integration

```python
import pytest
from pathlib import Path
from rustybt.validation.session import SessionManager
from rustybt.validation.comparators import Layer1DataComparator
from rustybt.validation.log_parser import parse_log

@pytest.fixture
def session_manager():
    """Create a session manager for tests."""
    return SessionManager(sessions_dir=Path("test-sessions"))

@pytest.fixture
def validation_session(session_manager):
    """Create a test validation session."""
    session = session_manager.create_session(
        strategy_name="test_strategy",
        data_fixture=Path("tests/fixtures/test_data.parquet"),
        rustybt_version="0.3.4",
        backtrader_version="1.9.78",
    )
    yield session
    # Cleanup
    session_manager.delete_session(session.id)

def test_data_layer_comparison(validation_session):
    """Test data layer produces matching results."""
    comparator = Layer1DataComparator()

    rb_logs = parse_log(Path("logs/rustybt.jsonl"))
    bt_logs = parse_log(Path("logs/backtrader.jsonl"))

    result = comparator.compare(rb_logs, bt_logs)

    assert result.passed, f"Data layer failed: {result.discrepancies}"
    assert result.critical_count == 0
```

### CI/CD Pipeline Integration

```python
#!/usr/bin/env python
"""CI validation script."""
import sys
from pathlib import Path
from rustybt.validation.session import SessionManager
from rustybt.validation.reporting import StatusDashboard

def main():
    sm = SessionManager()
    dashboard = StatusDashboard(sm)

    # Print status
    print(dashboard.render())

    # Get JSON for CI artifacts
    data = dashboard.to_json()

    # Write JSON report
    import json
    Path("validation-report.json").write_text(
        json.dumps(data, indent=2, default=str)
    )

    # Exit with appropriate code
    if not dashboard.is_healthy():
        print("\n⚠️  Validation unhealthy - failing CI")
        sys.exit(1)

    print("\n✓ Validation healthy")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Custom Script Integration

```python
"""Custom validation script example."""
from pathlib import Path
from rustybt.validation.session import SessionManager
from rustybt.validation.coordinator import execute_dual
from rustybt.validation.comparators import (
    Layer1DataComparator,
    Layer2SignalComparator,
    Layer3OrdersComparator,
    Layer4BrokerComparator,
    Layer5PortfolioComparator,
)
from rustybt.validation.log_parser import parse_log
from rustybt.validation.reporting import ReportGenerator

def run_full_validation(strategy_name: str, data_path: Path) -> dict:
    """Run complete validation for a strategy."""
    sm = SessionManager()

    # Create session
    session = sm.create_session(
        strategy_name=strategy_name,
        data_fixture=data_path,
        rustybt_version="0.3.4",
        backtrader_version="1.9.78",
        force=True,
    )

    # Execute dual
    result = execute_dual(
        session=session,
        strategy_name=strategy_name,
        rustybt_module=f"strategies.rustybt.{strategy_name}",
        backtrader_module=f"strategies.bt.{strategy_name}",
    )

    if not result.success:
        return {"success": False, "errors": result.errors}

    # Run comparisons
    rb_logs = parse_log(result.rustybt_log)
    bt_logs = parse_log(result.backtrader_log)

    comparators = [
        Layer1DataComparator(),
        Layer2SignalComparator(),
        Layer3OrdersComparator(),
        Layer4BrokerComparator(),
        Layer5PortfolioComparator(),
    ]

    all_discrepancies = []
    for comparator in comparators:
        comp_result = comparator.compare(rb_logs, bt_logs)
        all_discrepancies.extend(comp_result.discrepancies)

    # Generate report
    generator = ReportGenerator(session)
    report_path = generator.save_markdown()

    return {
        "success": True,
        "session_id": session.id,
        "discrepancies": len(all_discrepancies),
        "report_path": str(report_path),
    }

if __name__ == "__main__":
    result = run_full_validation(
        "sma_crossover",
        Path("tests/validation/fixtures/validation_data.parquet"),
    )
    print(f"Validation complete: {result}")
```

---

## See Also

- [CLI Reference](cli-reference.md) - Command-line interface documentation
- [Getting Started Guide](getting-started.md) - Quick start tutorial
- [Investigation Guide](investigation-guide.md) - How to investigate discrepancies
- [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions
