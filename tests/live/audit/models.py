"""
Pydantic models for audit findings schema.

Finding IDs use format: AUDIT-{MODULE_CODE}{NUMBER}
Module codes:
- E = Engine (rustybt/live/engine.py)
- B = Brokers (rustybt/live/brokers/)
- S = Streaming (rustybt/live/streaming/)
- O = OrderManager (rustybt/live/order_manager.py)
- R = Reconciler (rustybt/live/reconciler.py)
- C = CircuitBreakers (rustybt/live/circuit_breakers.py)
- M = StateManager (rustybt/live/state_manager.py)
- X = StrategyExecutor (rustybt/live/strategy_executor.py)
- D = DataFeed (rustybt/live/data_feed.py)
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    """Finding severity classification.

    CRITICAL: Data loss, financial impact, security vulnerabilities
    HIGH: Incorrect behavior, state corruption, crash potential
    MEDIUM: Edge case bugs, non-critical error handling
    LOW: Code style, minor improvements, documentation
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Status(str, Enum):
    """Finding lifecycle status.

    OPEN: Finding identified, not yet addressed
    IN_PROGRESS: Fix being implemented
    RESOLVED: Fix implemented, awaiting verification
    VERIFIED: Fix verified with passing regression test
    """

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    VERIFIED = "VERIFIED"


class Category(str, Enum):
    """Finding category types."""

    ERROR_HANDLING = "error_handling"
    CONCURRENCY = "concurrency"
    STATE_MANAGEMENT = "state_management"
    SECURITY = "security"
    TYPE_ERROR = "type_error"
    STYLE = "style"
    LOGGING = "logging"
    RECONNECTION_LOGIC = "reconnection_logic"
    RATE_LIMITING = "rate_limiting"
    MANUAL_REVIEW = "manual_review"
    STATIC_ANALYSIS = "static_analysis"


class FoundBy(str, Enum):
    """How the finding was discovered."""

    CODE_AUDIT = "code_audit"
    STATIC_ANALYSIS = "static_analysis"
    MANUAL_REVIEW = "manual_review"
    TESTING = "testing"


# Module code mapping for ID generation
MODULE_CODES: dict[str, str] = {
    "rustybt/live/engine.py": "E",
    "rustybt/live/order_manager.py": "O",
    "rustybt/live/state_manager.py": "M",
    "rustybt/live/strategy_executor.py": "X",
    "rustybt/live/reconciler.py": "R",
    "rustybt/live/circuit_breakers.py": "C",
    "rustybt/live/data_feed.py": "D",
    "rustybt/live/brokers/": "B",
    "rustybt/live/streaming/": "S",
}


def get_module_code(module_path: str) -> str:
    """Get the module code for a given module path."""
    # Check exact matches first
    if module_path in MODULE_CODES:
        return MODULE_CODES[module_path]
    # Check prefix matches for directories
    for prefix, code in MODULE_CODES.items():
        if prefix.endswith("/") and module_path.startswith(prefix):
            return code
    return "U"  # Unknown


class AuditFinding(BaseModel):
    """A single audit finding.

    Represents an issue discovered during code audit with severity,
    classification, and resolution tracking.
    """

    id: Annotated[str, Field(description="Finding ID: AUDIT-{MODULE_CODE}{NUMBER}")]
    module: Annotated[str, Field(description="Path to the affected module file")]
    line: Annotated[int | None, Field(description="Line number where issue is located")] = None
    severity: Annotated[Severity, Field(description="Classification: CRITICAL/HIGH/MEDIUM/LOW")]
    category: Annotated[Category, Field(description="Type of issue")]
    description: Annotated[str, Field(description="Clear description of the issue")]
    recommendation: Annotated[str, Field(description="Suggested fix")]
    status: Annotated[Status, Field(description="Lifecycle state")] = Status.OPEN
    found_by: Annotated[FoundBy, Field(description="Method of discovery")]
    found_at: Annotated[date, Field(description="Date finding was created")]
    resolved_at: Annotated[date | None, Field(description="Date finding was resolved")] = None
    regression_test: Annotated[str | None, Field(description="Path to regression test")] = None
    exchange: Annotated[
        str | None, Field(description="Affected exchange (for broker/streaming)")
    ] = None

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """Validate finding ID matches expected format."""
        pattern = r"^AUDIT-[A-Z]\d{3}$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Finding ID must match pattern AUDIT-{{MODULE_CODE}}{{NUMBER}}, got: {v}"
            )
        return v

    @field_validator("line")
    @classmethod
    def validate_line_positive(cls, v: int | None) -> int | None:
        """Validate line number is positive if provided."""
        if v is not None and v < 1:
            raise ValueError("Line number must be positive")
        return v


class FindingsFile(BaseModel):
    """A YAML findings file containing multiple findings."""

    findings: list[AuditFinding] = Field(default_factory=list)

    @classmethod
    def load_from_yaml(cls, path: Path) -> FindingsFile:
        """Load findings from a YAML file."""
        if not path.exists():
            return cls(findings=[])
        with open(path) as f:
            data = yaml.safe_load(f)
        if data is None:
            return cls(findings=[])
        return cls.model_validate(data)

    def save_to_yaml(self, path: Path) -> None:
        """Save findings to a YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def filter_by_severity(self, severity: Severity) -> list[AuditFinding]:
        """Filter findings by severity."""
        return [f for f in self.findings if f.severity == severity]

    def filter_by_status(self, status: Status) -> list[AuditFinding]:
        """Filter findings by status."""
        return [f for f in self.findings if f.status == status]

    def filter_by_module(self, module_path: str) -> list[AuditFinding]:
        """Filter findings by module path prefix."""
        return [f for f in self.findings if f.module.startswith(module_path)]

    def filter_by_category(self, category: Category) -> list[AuditFinding]:
        """Filter findings by category."""
        return [f for f in self.findings if f.category == category]

    def severity_counts(self) -> dict[Severity, int]:
        """Get counts by severity level."""
        counts = {s: 0 for s in Severity}
        for finding in self.findings:
            counts[finding.severity] += 1
        return counts

    def status_counts(self) -> dict[Status, int]:
        """Get counts by status."""
        counts = {s: 0 for s in Status}
        for finding in self.findings:
            counts[finding.status] += 1
        return counts
