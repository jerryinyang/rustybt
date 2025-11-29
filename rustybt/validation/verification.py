"""Bug fix verification workflow for validation findings.

This module provides functionality to verify that bug fixes resolve discrepancies
by re-executing strategies and re-running layer comparisons.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from rustybt.validation.comparators import (
    ComparisonResult,
    Discrepancy,
    Layer1DataComparator,
    Layer2SignalComparator,
    Layer3OrdersComparator,
    Layer4BrokerComparator,
    Layer5PortfolioComparator,
)
from rustybt.validation.log_parser import parse_log
from rustybt.validation.runner import run_backtrader_strategy, run_rustybt_strategy
from rustybt.validation.tolerance import ToleranceConfig

if TYPE_CHECKING:
    from rustybt.validation.models import Finding, Session


class ExecutionError(Exception):
    """Raised when strategy execution fails during verification."""

    pass


class VerificationResult:
    """Result of a bug fix verification attempt.

    Attributes:
        passed: True if the discrepancy is no longer present
        finding_id: ID of the finding being verified
        original_discrepancy: Description of the original discrepancy
        current_discrepancies: List of discrepancies found in re-comparison
        error: Error message if verification could not complete
    """

    def __init__(
        self,
        passed: bool,
        finding_id: str,
        original_discrepancy: str | None = None,
        current_discrepancies: list[Discrepancy] | None = None,
        error: str | None = None,
    ):
        self.passed = passed
        self.finding_id = finding_id
        self.original_discrepancy = original_discrepancy
        self.current_discrepancies = current_discrepancies or []
        self.error = error


def get_comparator_for_layer(layer: str) -> Any:
    """Get the appropriate comparator for a validation layer.

    Args:
        layer: Layer name (data, signals, orders, broker, portfolio)

    Returns:
        Instantiated comparator for the layer

    Raises:
        ValueError: If layer name is invalid
    """
    comparators = {
        "data": Layer1DataComparator,
        "signals": Layer2SignalComparator,
        "orders": Layer3OrdersComparator,
        "broker": Layer4BrokerComparator,
        "portfolio": Layer5PortfolioComparator,
    }

    if layer not in comparators:
        raise ValueError(f"Invalid layer: {layer}. Must be one of: {list(comparators.keys())}")

    return comparators[layer]()


def load_tolerances_for_layer(layer: str, config_dir: Path | None = None) -> Any:
    """Load tolerance configuration for a specific layer.

    Args:
        layer: Layer name
        config_dir: Directory containing tolerance YAML files

    Returns:
        Tolerance configuration for the layer
    """
    # Just return default tolerances - config loading is optional
    config = ToleranceConfig()

    # Return the appropriate tolerances based on layer
    layer_tolerances = {
        "data": config.layer_1,
        "signals": config.layer_2,
        "orders": config.layer_3,
        "broker": config.layer_4,
        "portfolio": config.layer_5,
    }

    return layer_tolerances.get(layer)


def re_execute_strategies(
    session: Session,
    sessions_dir: Path | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Re-execute strategies and return log DataFrames.

    Executes both rustybt and Backtrader strategies using the session's
    configuration and returns parsed log DataFrames.

    Args:
        session: Session containing strategy configuration
        sessions_dir: Base directory for sessions (default: validation-sessions)

    Returns:
        Tuple of (rustybt_logs, backtrader_logs) as Polars DataFrames

    Raises:
        ExecutionError: If either framework fails to execute
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        rb_log_path = tmp_path / "rustybt.jsonl"
        bt_log_path = tmp_path / "backtrader.jsonl"

        # Construct module paths from strategy name
        strategy = session.strategy_name
        rb_module = f"tests.validation.strategies.rustybt.{strategy}"
        bt_module = f"tests.validation.strategies.bt_strategies.{strategy}"

        # Run rustybt strategy
        rb_result = run_rustybt_strategy(
            strategy_module=rb_module,
            data_path=session.data_fixture,
            output_log=rb_log_path,
            params=None,
        )

        if rb_result.returncode != 0:
            raise ExecutionError(f"rustybt execution failed: {rb_result.stderr}")

        # Run Backtrader strategy
        bt_result = run_backtrader_strategy(
            strategy_module=bt_module,
            data_path=session.data_fixture,
            output_log=bt_log_path,
            params=None,
        )

        if bt_result.returncode != 0:
            raise ExecutionError(f"Backtrader execution failed: {bt_result.stderr}")

        # Parse logs
        rb_logs = parse_log(rb_log_path)
        bt_logs = parse_log(bt_log_path)

        return rb_logs, bt_logs


def compare_layer_for_finding(
    finding: Finding,
    rb_logs: pl.DataFrame,
    bt_logs: pl.DataFrame,
    config_dir: Path | None = None,
) -> list[Discrepancy]:
    """Run comparison for the finding's layer only.

    Args:
        finding: Finding to verify
        rb_logs: rustybt execution logs
        bt_logs: Backtrader execution logs
        config_dir: Directory containing tolerance configuration

    Returns:
        List of discrepancies found in the layer
    """
    # Get comparator for the finding's layer
    comparator = get_comparator_for_layer(finding.layer)

    # Load tolerances and set on comparator if it has a tolerances attribute
    tolerances = load_tolerances_for_layer(finding.layer, config_dir)
    if tolerances is not None and hasattr(comparator, "tolerances"):
        comparator.tolerances = tolerances

    # Run comparison
    result: ComparisonResult = comparator.compare(rb_logs, bt_logs)

    return result.discrepancies


def verify_fix(
    finding: Finding,
    session: Session,
    sessions_dir: Path | None = None,
    config_dir: Path | None = None,
) -> VerificationResult:
    """Verify that a bug fix resolves the discrepancy.

    Re-executes strategies and re-runs comparison to check if the
    original discrepancy is still present.

    Args:
        finding: Finding to verify (must be classified as BUG)
        session: Session containing the finding
        sessions_dir: Base directory for sessions
        config_dir: Directory containing tolerance configuration

    Returns:
        VerificationResult indicating pass/fail status
    """
    # Validate finding is a BUG
    if finding.classification != "BUG":
        return VerificationResult(
            passed=False,
            finding_id=finding.id,
            error=f"Finding {finding.id} is not classified as BUG (classification: {finding.classification})",
        )

    # Re-execute strategies
    try:
        rb_logs, bt_logs = re_execute_strategies(session, sessions_dir)
    except ExecutionError as e:
        return VerificationResult(
            passed=False,
            finding_id=finding.id,
            error=str(e),
        )

    # Re-run comparison for the finding's layer
    discrepancies = compare_layer_for_finding(finding, rb_logs, bt_logs, config_dir)

    # Check if original discrepancy still present
    # Match by event type and description pattern
    original_still_present = any(
        d.event == finding.description.split(":")[0].split("/")[-1]  # Extract event from description
        or finding.description.lower() in d.description.lower()
        for d in discrepancies
    )

    # Also check by the event field if stored in finding
    if hasattr(finding, "event") and finding.event:
        original_still_present = original_still_present or any(
            d.event == finding.event for d in discrepancies
        )

    return VerificationResult(
        passed=not original_still_present,
        finding_id=finding.id,
        original_discrepancy=finding.description,
        current_discrepancies=discrepancies if original_still_present else [],
    )


def load_finding(finding_id: str, sessions_dir: Path | None = None) -> tuple[Finding | None, Session | None]:
    """Load a finding by ID from any session.

    Searches through all sessions to find the specified finding.

    Args:
        finding_id: ID of the finding to load
        sessions_dir: Base directory for sessions

    Returns:
        Tuple of (Finding, Session) if found, (None, None) otherwise
    """
    from rustybt.validation.session import SessionManager

    if sessions_dir is None:
        sessions_dir = Path("validation-sessions")

    sm = SessionManager(sessions_dir)
    sessions = sm.list_sessions()

    for session in sessions:
        for finding in session.findings:
            if finding.id == finding_id:
                return finding, session

    return None, None


def save_finding(finding: Finding, session: Session, sessions_dir: Path | None = None) -> None:
    """Save updated finding to session.

    Args:
        finding: Finding to save
        session: Session containing the finding
        sessions_dir: Base directory for sessions
    """
    from rustybt.validation.session import SessionManager

    if sessions_dir is None:
        sessions_dir = Path("validation-sessions")

    sm = SessionManager(sessions_dir)

    # Update finding in session's findings list
    for i, f in enumerate(session.findings):
        if f.id == finding.id:
            session.findings[i] = finding
            break

    # Log activity
    if finding.resolved:
        session.log_activity(
            "finding_resolved",
            f"Finding {finding.id} verified and marked as resolved",
        )

    sm.update_session(session)
