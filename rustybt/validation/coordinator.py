"""Execution coordinator for dual framework validation.

This module orchestrates the execution of strategies in both rustybt and Backtrader
frameworks, collecting logs for comparison. It validates logs after execution
and updates session status.

Architecture Note:
    Frameworks are executed sequentially (not in parallel) to ensure determinism
    and simplify debugging. Each framework runs in its own subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rustybt.validation.log_parser import ValidationResult, validate_log_schema
from rustybt.validation.runner import run_backtrader_strategy, run_rustybt_strategy

if TYPE_CHECKING:
    from rustybt.validation.models import Session


@dataclass
class ExecutionResult:
    """Result of dual framework execution.

    Attributes:
        rustybt_success: True if rustybt execution completed successfully
        backtrader_success: True if Backtrader execution completed successfully
        rustybt_log: Path to rustybt JSONL log file
        backtrader_log: Path to Backtrader JSONL log file
        rustybt_log_valid: True if rustybt log passes schema validation
        backtrader_log_valid: True if Backtrader log passes schema validation
        errors: List of error messages encountered during execution
    """

    rustybt_success: bool
    backtrader_success: bool
    rustybt_log: Path
    backtrader_log: Path
    rustybt_log_valid: bool
    backtrader_log_valid: bool
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if both frameworks executed successfully with valid logs."""
        return (
            self.rustybt_success
            and self.backtrader_success
            and self.rustybt_log_valid
            and self.backtrader_log_valid
        )

    def __str__(self) -> str:
        """Format execution result for display."""
        if self.success:
            return "✓ Both frameworks executed successfully"
        parts = []
        if not self.rustybt_success:
            parts.append("rustybt execution failed")
        if not self.backtrader_success:
            parts.append("Backtrader execution failed")
        if not self.rustybt_log_valid:
            parts.append("rustybt log invalid")
        if not self.backtrader_log_valid:
            parts.append("Backtrader log invalid")
        return "✗ Execution failed: " + ", ".join(parts)


def execute_dual(
    session: Session,
    strategy_name: str,
    rustybt_module: str,
    backtrader_module: str,
    params: dict[str, Any] | None = None,
    sessions_dir: Path | None = None,
) -> ExecutionResult:
    """Execute strategy in both frameworks and collect logs.

    This function orchestrates the execution of a strategy in both rustybt
    and Backtrader, collecting JSONL logs for later comparison. Executes
    sequentially for determinism.

    Args:
        session: Current validation session
        strategy_name: Name of strategy being validated
        rustybt_module: Python module path for rustybt strategy
        backtrader_module: Python module path for Backtrader strategy
        params: Optional strategy parameters
        sessions_dir: Optional base directory for sessions (default: validation-sessions)

    Returns:
        ExecutionResult with success status and log paths
    """
    errors: list[str] = []

    # Determine base path for logs
    base_dir = sessions_dir or Path("validation-sessions")
    logs_dir = base_dir / session.id / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    rustybt_log = logs_dir / "rustybt.jsonl"
    backtrader_log = logs_dir / "backtrader.jsonl"

    # Execute rustybt
    rb_result = run_rustybt_strategy(
        strategy_module=rustybt_module,
        data_path=session.data_fixture,
        output_log=rustybt_log,
        params=params,
    )
    if rb_result.returncode != 0:
        errors.append(f"rustybt execution failed: {rb_result.stderr}")

    # Execute Backtrader
    bt_result = run_backtrader_strategy(
        strategy_module=backtrader_module,
        data_path=session.data_fixture,
        output_log=backtrader_log,
        params=params,
    )
    if bt_result.returncode != 0:
        errors.append(f"Backtrader execution failed: {bt_result.stderr}")

    # Validate logs
    rb_valid = ValidationResult(valid=False, line_count=0, errors=[])
    bt_valid = ValidationResult(valid=False, line_count=0, errors=[])

    if rustybt_log.exists():
        rb_valid = validate_log_schema(rustybt_log)
        if not rb_valid.valid:
            errors.extend([f"rustybt log: {e}" for e in rb_valid.errors])
    else:
        errors.append("rustybt log file not created")

    if backtrader_log.exists():
        bt_valid = validate_log_schema(backtrader_log)
        if not bt_valid.valid:
            errors.extend([f"Backtrader log: {e}" for e in bt_valid.errors])
    else:
        errors.append("Backtrader log file not created")

    return ExecutionResult(
        rustybt_success=rb_result.returncode == 0,
        backtrader_success=bt_result.returncode == 0,
        rustybt_log=rustybt_log,
        backtrader_log=backtrader_log,
        rustybt_log_valid=rb_valid.valid,
        backtrader_log_valid=bt_valid.valid,
        errors=errors,
    )
