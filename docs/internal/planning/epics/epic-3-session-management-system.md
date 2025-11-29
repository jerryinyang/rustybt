# Epic 3: Session Management System

**Goal:** Provide complete session lifecycle management with progress tracking, resumability, and query capabilities.

**Architecture References:**
- Session Storage (Architecture ADR-003)
- Data Models (Architecture pg 359-402)
- CLI Interface (Architecture pg 435-452)

**Value:** Developers can manage validation work efficiently with full traceability and resumability.

**FRs Covered:** FR31-FR40 (Validation Session Management - 10 FRs)

---

## Story 3.1: Implement Session Progress Tracking

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

## Story 3.2: Implement Session Resumability

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

## Story 3.3: Implement Session Query Commands

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

## Story 3.4: Implement Duplicate Prevention

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

## Story 3.5: Implement Session Deletion and Archival

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

## Story 3.6: Implement Timestamped Activity Log

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
