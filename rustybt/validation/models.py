"""Core data models for the rustybt validation framework.

This module defines strongly-typed dataclasses for managing validation sessions,
tracking discrepancies, and classifying findings during the validation process.

The validation framework compares rustybt against Backtrader (reference implementation)
across 5 layers: data handling, signal computation, order lifecycle, broker transactions,
and portfolio returns.

Models:
    Session: Validation session metadata and lifecycle tracking
    Finding: Layer-specific discrepancy with BUG/DESIGN classification
    Discrepancy: Specific value mismatch discovered during comparison

Example:
    >>> from pathlib import Path
    >>> from datetime import datetime
    >>> session = Session(
    ...     id="20251124-143000-sma_crossover",
    ...     created_at=datetime.now(),
    ...     strategy_name="sma_crossover",
    ...     rustybt_version="0.3.4",
    ...     backtrader_version="1.9.78",
    ...     python_version="3.12.0",
    ...     status="IN_PROGRESS",
    ...     data_fixture=Path("fixtures/validation_data.parquet"),
    ... )
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal


@dataclass
class Activity:
    """Timestamped activity record for audit trail.

    Activities provide a complete audit trail of all actions performed
    during a validation session. They are append-only and never deleted.

    Attributes:
        timestamp: When the activity occurred (ISO 8601 format)
        action: Type of action (e.g., "created", "execution_started", "finding_added")
        actor: Who/what performed the action ("system" for automated, username for manual)
        details: Optional dictionary with additional context

    Example:
        >>> activity = Activity(
        ...     timestamp=datetime.now(),
        ...     action="finding_classified",
        ...     actor="developer",
        ...     details={"finding_id": "finding_001", "classification": "BUG"}
        ... )
    """

    timestamp: datetime
    action: str
    actor: str = "system"
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert Activity to dictionary for YAML serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "actor": self.actor,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Activity":
        """Create Activity from dictionary (YAML deserialization)."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=data["action"],
            actor=data.get("actor", "system"),
            details=data.get("details"),
        )


class SessionStage(Enum):
    """Session lifecycle stages for progress tracking.

    Stage Lifecycle Flow:
        CREATED -> EXECUTING (start execution)
        EXECUTING -> EXECUTED (logs collected) or FAILED (execution error)
        EXECUTED -> COMPARING (start comparison)
        COMPARING -> COMPARED (discrepancies found) or FAILED (comparison error)
        COMPARED -> INVESTIGATING (manual investigation started)
        INVESTIGATING -> COMPLETED (all findings resolved) or COMPARED (back to review)
        Any -> FAILED (error at any point)
        FAILED -> CREATED (retry from scratch)

    Attributes:
        CREATED: Session initialized, ready to start
        EXECUTING: Strategies actively running in both frameworks
        EXECUTED: Both frameworks completed, logs collected
        COMPARING: Running layer-by-layer comparison
        COMPARED: Discrepancies identified, ready for investigation
        INVESTIGATING: Manual investigation of findings in progress
        COMPLETED: All findings resolved, session finished
        FAILED: Error occurred during any stage
    """

    CREATED = "created"
    EXECUTING = "executing"
    EXECUTED = "executed"
    COMPARING = "comparing"
    COMPARED = "compared"
    INVESTIGATING = "investigating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Session:
    """Validation session metadata and tracking.

    A session represents a complete validation run comparing a strategy
    implementation between rustybt and Backtrader across all 5 layers.

    Session IDs follow the format: {YYYYMMDD}-{HHMMSS}-{strategy_name}
    Example: 20251124-143000-sma_crossover

    Attributes:
        id: Unique session identifier (timestamp + strategy name)
        created_at: Session creation timestamp
        strategy_name: Name of the strategy being validated
        rustybt_version: Version of rustybt under test
        backtrader_version: Version of Backtrader reference
        python_version: Python interpreter version
        status: Current session state (IN_PROGRESS, EXECUTED, COMPLETED, FAILED, SUPERSEDED)
        data_fixture: Path to test data fixture (Parquet file)
        findings: List of discrepancies found during validation
        stage: Current lifecycle stage (see SessionStage enum)
        stage_started_at: Timestamp when current stage began
        execution_completed_at: Timestamp when execution finished
        comparison_completed_at: Timestamp when comparison finished
        layers_completed: List of completed validation layer names
        activities: List of timestamped activity records for audit trail
    """

    id: str
    created_at: datetime
    strategy_name: str
    rustybt_version: str
    backtrader_version: str
    python_version: str
    status: Literal["IN_PROGRESS", "EXECUTED", "COMPLETED", "FAILED", "SUPERSEDED"]
    data_fixture: Path
    findings: list["Finding"] = field(default_factory=list)
    stage: SessionStage = SessionStage.CREATED
    stage_started_at: datetime | None = None
    execution_completed_at: datetime | None = None
    comparison_completed_at: datetime | None = None
    layers_completed: list[str] = field(default_factory=list)
    activities: list["Activity"] = field(default_factory=list)

    def log_activity(
        self,
        action: str,
        message: str | None = None,
        actor: str = "system",
    ) -> None:
        """Log an activity to the session's audit trail.

        Creates a new Activity with current timestamp and appends it to
        the activities list. Activities are append-only (never deleted).

        Args:
            action: Type of action (e.g., "finding_added", "note")
            message: Optional message or description to include in details
            actor: Who/what performed the action (default: "system")

        Example:
            >>> session.log_activity("finding_classified", "Classified as BUG", "developer")
            >>> session.log_activity("note", "Investigation paused for review")
        """
        details: dict[str, Any] | None = None
        if message:
            details = {"message": message}

        activity = Activity(
            timestamp=datetime.now(),
            action=action,
            actor=actor,
            details=details,
        )
        self.activities.append(activity)


class BugSeverity(str, Enum):
    """Bug severity levels for classification.

    Attributes:
        CRITICAL: Incorrect results - fundamentally wrong calculations
        MAJOR: Significant deviation - noticeable impact on results
        MINOR: Small deviation - minor numerical differences
    """

    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"

    @classmethod
    def from_number(cls, n: int) -> "BugSeverity":
        """Convert numeric selection to severity.

        Args:
            n: Number from user input (1=Critical, 2=Major, 3=Minor)

        Returns:
            BugSeverity enum value, defaults to Minor for invalid input
        """
        mapping = {1: cls.CRITICAL, 2: cls.MAJOR, 3: cls.MINOR}
        return mapping.get(n, cls.MINOR)


class DesignChoice(str, Enum):
    """Design choice preference for DESIGN classification.

    Indicates which framework's approach is preferred or if both are valid.

    Attributes:
        RUSTYBT_PREFERRED: rustybt's implementation is the preferred approach
        BACKTRADER_PREFERRED: Backtrader's implementation is the preferred approach
        EITHER_VALID: Both implementations are valid, choice depends on use case
    """

    RUSTYBT_PREFERRED = "rustybt_preferred"
    BACKTRADER_PREFERRED = "backtrader_preferred"
    EITHER_VALID = "either_valid"

    @classmethod
    def from_key(cls, key: str) -> "DesignChoice":
        """Convert single-character key to DesignChoice.

        Args:
            key: Single character (r=rustybt, b=backtrader, e=either)

        Returns:
            DesignChoice enum value, defaults to EITHER_VALID
        """
        mapping = {
            "r": cls.RUSTYBT_PREFERRED,
            "b": cls.BACKTRADER_PREFERRED,
            "e": cls.EITHER_VALID,
        }
        return mapping.get(key.lower(), cls.EITHER_VALID)


@dataclass
class Finding:
    """Layer-specific discrepancy with classification.

    Findings represent discrepancies discovered during validation that require
    investigation. They are classified as either:
    - BUG: Incorrect rustybt behavior requiring a fix
    - DESIGN: Intentional difference to be documented and accepted
    - None: Not yet investigated

    Attributes:
        id: Unique finding identifier (e.g., "layer_1_finding_001")
        layer: Validation layer where discrepancy occurred
        description: Human-readable description of the discrepancy
        classification: BUG, DESIGN, or None (pending investigation)
        rationale: Explanation for classification decision
        investigated_by: Person/agent who investigated the finding
        investigated_at: Timestamp of investigation
        resolved: Whether the finding has been resolved
        rustybt_value: Value from rustybt execution
        backtrader_value: Value from Backtrader execution
        severity: Bug severity level (Critical/Major/Minor) - BUG only
        affected_components: List of affected file paths - BUG only
        suggested_fix: Optional suggested fix description - BUG only
        design_rationale: Explanation for intentional difference - DESIGN only
        acceptance_criteria: Criteria for accepting the difference - DESIGN only
    """

    id: str
    layer: Literal["data", "signals", "orders", "broker", "portfolio"]
    description: str
    classification: Literal["BUG", "DESIGN"] | None = None
    rationale: str | None = None
    investigated_by: str | None = None
    investigated_at: datetime | None = None
    resolved: bool = False
    resolved_at: datetime | None = None  # When the fix was verified
    regression_test: str | None = None  # Path to regression test (Story 5.6)
    rustybt_value: Any = None
    backtrader_value: Any = None
    # BUG-specific fields
    severity: str | None = None  # Critical, Major, Minor
    affected_components: list[str] = field(default_factory=list)
    suggested_fix: str | None = None
    # DESIGN-specific fields
    design_rationale: str | None = None
    acceptance_criteria: str | None = None
    design_choice: str | None = None  # rustybt_preferred, backtrader_preferred, either_valid
    user_impact: str | None = None
    documentation_ref: str | None = None  # path#anchor format

    def to_dict(self) -> dict[str, Any]:
        """Convert Finding to dictionary for YAML serialization."""
        return {
            "id": self.id,
            "layer": self.layer,
            "description": self.description,
            "classification": self.classification,
            "rationale": self.rationale,
            "investigated_by": self.investigated_by,
            "investigated_at": self.investigated_at.isoformat() if self.investigated_at else None,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "regression_test": self.regression_test,
            "rustybt_value": self.rustybt_value,
            "backtrader_value": self.backtrader_value,
            "severity": self.severity,
            "affected_components": self.affected_components if self.affected_components else None,
            "suggested_fix": self.suggested_fix,
            "design_rationale": self.design_rationale,
            "acceptance_criteria": self.acceptance_criteria,
            "design_choice": self.design_choice,
            "user_impact": self.user_impact,
            "documentation_ref": self.documentation_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Finding":
        """Create Finding from dictionary (YAML deserialization)."""
        investigated_at = None
        if data.get("investigated_at"):
            investigated_at = datetime.fromisoformat(data["investigated_at"])

        resolved_at = None
        if data.get("resolved_at"):
            resolved_at = datetime.fromisoformat(data["resolved_at"])

        return cls(
            id=data["id"],
            layer=data["layer"],
            description=data["description"],
            classification=data.get("classification"),
            rationale=data.get("rationale"),
            investigated_by=data.get("investigated_by"),
            investigated_at=investigated_at,
            resolved=data.get("resolved", False),
            resolved_at=resolved_at,
            regression_test=data.get("regression_test"),
            rustybt_value=data.get("rustybt_value"),
            backtrader_value=data.get("backtrader_value"),
            severity=data.get("severity"),
            affected_components=data.get("affected_components") or [],
            suggested_fix=data.get("suggested_fix"),
            design_rationale=data.get("design_rationale"),
            acceptance_criteria=data.get("acceptance_criteria"),
            design_choice=data.get("design_choice"),
            user_impact=data.get("user_impact"),
            documentation_ref=data.get("documentation_ref"),
        )


@dataclass
class Discrepancy:
    """Specific value mismatch discovered during comparison.

    Discrepancies are raw comparison results that may become Findings after
    investigation. They capture exact values and tolerance information.

    Attributes:
        layer: Validation layer (data, signals, orders, broker, portfolio)
        event: Event type (e.g., "on_data", "place_order", "portfolio_value")
        timestamp: When the discrepancy occurred (simulation time)
        asset: Asset symbol (None for portfolio-wide events)
        field: Field name that differs (e.g., "close_price", "order_quantity")
        rustybt_value: Value from rustybt execution
        backtrader_value: Value from Backtrader execution
        tolerance: Tolerance threshold that was exceeded
        exceeded_by: Amount by which tolerance was exceeded
    """

    layer: str
    event: str
    timestamp: datetime
    asset: str | None
    field: str
    rustybt_value: Any
    backtrader_value: Any
    tolerance: Any
    exceeded_by: Any


@dataclass
class HealthCheckResult:
    """Result of a health check validation.

    Health checks validate file integrity, data quality, and system health
    before processing. They help detect corrupted data, missing files, or
    other issues that would cause failures during validation.

    Attributes:
        passed: Whether the health check passed
        diagnostics: Dictionary of diagnostic information with details about
            what was checked and any issues found

    Example:
        >>> result = HealthCheckResult(
        ...     passed=False,
        ...     diagnostics={
        ...         "file_exists": True,
        ...         "file_readable": True,
        ...         "valid_jsonl": False,
        ...         "row_count": 0,
        ...         "truncated_lines": [42, 108],
        ...         "missing_fields": ["timestamp", "layer"]
        ...     }
        ... )
        >>> if not result.passed:
        ...     print(f"Health check failed: {result.diagnostics}")
    """

    passed: bool
    diagnostics: dict[str, Any] = field(default_factory=dict)
