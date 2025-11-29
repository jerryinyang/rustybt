"""
Validation Reporting.

This module generates human-readable reports (Markdown/JSON) from validation
session results. Reports include session summaries, layer results, and
detailed findings with classifications.

Example:
    >>> from rustybt.validation.reporting import ReportGenerator, LayerReportGenerator
    >>> from rustybt.validation.session import SessionManager
    >>>
    >>> sm = SessionManager()
    >>> session = sm.load_session("20251124-143000-sma_crossover")
    >>> generator = ReportGenerator(session)
    >>> markdown = generator.generate_markdown()
    >>> print(markdown)
    >>>
    >>> # Generate layer report
    >>> layer_generator = LayerReportGenerator("signals", sm)
    >>> layer_report = layer_generator.generate()
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rustybt.validation.models import Finding, Session
    from rustybt.validation.session import SessionManager


# Layer name to number mapping
LAYER_NUMBERS: dict[str, int] = {
    "data": 1,
    "signals": 2,
    "orders": 3,
    "broker": 4,
    "portfolio": 5,
}

# Layer descriptions
LAYER_DESCRIPTIONS: dict[str, str] = {
    "data": "Data handling validation compares how both frameworks handle OHLCV data, timestamps, and data access patterns.",
    "signals": "Signal computation validation compares indicator calculations, smoothing methods, and signal generation logic.",
    "orders": "Order lifecycle validation compares order creation, submission, modification, and cancellation behavior.",
    "broker": "Broker transaction validation compares fill execution, commission calculation, and slippage handling.",
    "portfolio": "Portfolio returns validation compares position tracking, P&L calculation, and portfolio value computation.",
}


@dataclass
class CommonPattern:
    """Represents a common DESIGN pattern found across multiple strategies.

    Attributes:
        description: Human-readable description of the pattern.
        affected_strategies: List of strategy names affected by this pattern.
        user_impact: Description of how this affects users.
        workaround: Suggested workaround if any.
        findings: List of findings that match this pattern.
    """

    description: str
    affected_strategies: list[str] = field(default_factory=list)
    user_impact: str = ""
    workaround: str = ""
    findings: list[Any] = field(default_factory=list)  # Finding objects


class ReportGenerator:
    """Generate validation reports from session data.

    ReportGenerator creates human-readable reports in markdown or JSON format
    from validation session results. Reports include session metadata, summary
    tables, layer-by-layer results, and detailed findings.

    Attributes:
        session: The validation session to generate reports for.
        generated_at: Timestamp when the report was generated.

    Example:
        >>> generator = ReportGenerator(session)
        >>> markdown_report = generator.generate_markdown()
        >>> json_report = generator.generate_json()
        >>> saved_path = generator.save_markdown()
    """

    def __init__(self, session: Session) -> None:
        """Initialize ReportGenerator with a session.

        Args:
            session: The validation session to generate reports for.
        """
        self.session = session
        self.generated_at = datetime.now()

    def generate_markdown(self) -> str:
        """Generate a markdown report from session data.

        Creates a comprehensive markdown report including:
        - Session header with ID, strategy, status, and date
        - Summary table with findings counts and layer pass status
        - Per-layer results with findings tables
        - Detailed findings section with full classification info

        Returns:
            Markdown-formatted report string.
        """
        lines: list[str] = []

        # Session Header
        lines.append("# Validation Session Report")
        lines.append("")
        lines.append(f"**Session ID:** {self.session.id}")
        lines.append(f"**Strategy:** {self.session.strategy_name}")
        lines.append(f"**Status:** {self.session.status}")
        lines.append(f"**Date:** {self.session.created_at.strftime('%Y-%m-%d')}")
        lines.append(f"**Report Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Summary Section
        lines.append("## Summary")
        lines.append("")
        lines.extend(self._generate_summary_table())
        lines.append("")

        # Layer Results Section
        lines.append("## Layer Results")
        lines.append("")
        lines.extend(self._generate_layer_results())
        lines.append("")

        # Findings Detail Section
        if self.session.findings:
            lines.append("## Findings Detail")
            lines.append("")
            lines.extend(self._generate_findings_detail())

        return "\n".join(lines)

    def generate_json(self) -> dict[str, Any]:
        """Generate a JSON report from session data.

        Creates a structured JSON report suitable for programmatic use
        and CI integration. Contains the same data as the markdown report
        in machine-parseable format.

        Returns:
            Dictionary containing structured report data.
        """
        # Count findings by classification
        bug_count = sum(1 for f in self.session.findings if f.classification == "BUG")
        design_count = sum(1 for f in self.session.findings if f.classification == "DESIGN")
        unclassified_count = sum(1 for f in self.session.findings if f.classification is None)

        # Count resolved bugs
        resolved_bugs = sum(
            1 for f in self.session.findings
            if f.classification == "BUG" and f.resolved
        )

        # Build layer results
        all_layers = ["data", "signals", "orders", "broker", "portfolio"]
        layers_completed = self.session.layers_completed or []
        layer_results = {}

        for layer in all_layers:
            layer_findings = [f for f in self.session.findings if f.layer == layer]
            layer_bugs = [f for f in layer_findings if f.classification == "BUG"]
            layer_design = [f for f in layer_findings if f.classification == "DESIGN"]

            if layer in layers_completed:
                if layer_bugs:
                    status = "FAILED"
                elif layer_findings:
                    status = "PASSED_WITH_FINDINGS"
                else:
                    status = "PASSED"
            else:
                status = "PENDING"

            layer_results[layer] = {
                "status": status,
                "findings_count": len(layer_findings),
                "bug_count": len(layer_bugs),
                "design_count": len(layer_design),
                "findings": [self._finding_to_dict(f) for f in layer_findings],
            }

        return {
            "session_id": self.session.id,
            "strategy": self.session.strategy_name,
            "status": self.session.status,
            "stage": self.session.stage.value,
            "created_at": self.session.created_at.isoformat(),
            "report_generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_findings": len(self.session.findings),
                "bug_count": bug_count,
                "bug_resolved": resolved_bugs,
                "design_count": design_count,
                "unclassified_count": unclassified_count,
                "layers_passed": f"{len(layers_completed)}/{len(all_layers)}",
                "layers_completed": layers_completed,
            },
            "layers": layer_results,
            "findings": [self._finding_to_dict(f) for f in self.session.findings],
            "metadata": {
                "rustybt_version": self.session.rustybt_version,
                "backtrader_version": self.session.backtrader_version,
                "python_version": self.session.python_version,
                "data_fixture": str(self.session.data_fixture),
            },
        }

    def save_markdown(self, directory: Path | None = None) -> Path:
        """Save markdown report to session directory.

        Generates a markdown report and saves it to the session directory
        or a specified directory.

        Args:
            directory: Optional directory to save to. If None, saves to
                      validation-sessions/{session_id}/

        Returns:
            Path to the saved report file.
        """
        if directory is None:
            directory = Path("validation-sessions") / self.session.id

        directory.mkdir(parents=True, exist_ok=True)
        report_path = directory / "report.md"

        content = self.generate_markdown()
        report_path.write_text(content)

        return report_path

    def save_json(self, directory: Path | None = None) -> Path:
        """Save JSON report to session directory.

        Generates a JSON report and saves it to the session directory
        or a specified directory.

        Args:
            directory: Optional directory to save to. If None, saves to
                      validation-sessions/{session_id}/

        Returns:
            Path to the saved report file.
        """
        if directory is None:
            directory = Path("validation-sessions") / self.session.id

        directory.mkdir(parents=True, exist_ok=True)
        report_path = directory / "report.json"

        content = self.generate_json()
        report_path.write_text(json.dumps(content, indent=2))

        return report_path

    def _generate_summary_table(self) -> list[str]:
        """Generate the summary table section."""
        lines: list[str] = []

        # Count findings by classification
        bug_count = sum(1 for f in self.session.findings if f.classification == "BUG")
        design_count = sum(1 for f in self.session.findings if f.classification == "DESIGN")
        unclassified_count = sum(1 for f in self.session.findings if f.classification is None)

        # Count resolved bugs
        resolved_bugs = sum(
            1 for f in self.session.findings
            if f.classification == "BUG" and f.resolved
        )

        # Build summary status strings
        bug_status = f"{bug_count}"
        if resolved_bugs > 0:
            bug_status += f" ({resolved_bugs} fixed)"

        design_status = f"{design_count}"
        if design_count > 0:
            design_status += " (documented)"

        # Calculate layer pass status
        all_layers = ["data", "signals", "orders", "broker", "portfolio"]
        layers_completed = self.session.layers_completed or []
        layers_passed = len(layers_completed)

        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Findings | {len(self.session.findings)} |")
        lines.append(f"| BUG | {bug_status} |")
        lines.append(f"| DESIGN | {design_status} |")
        lines.append(f"| Unclassified | {unclassified_count} |")
        lines.append(f"| Layers Passed | {layers_passed}/{len(all_layers)} |")

        return lines

    def _generate_layer_results(self) -> list[str]:
        """Generate the per-layer results section."""
        lines: list[str] = []

        all_layers = ["data", "signals", "orders", "broker", "portfolio"]
        layer_names = {
            "data": "Layer 1: Data Handling",
            "signals": "Layer 2: Signal Computation",
            "orders": "Layer 3: Order Lifecycle",
            "broker": "Layer 4: Broker Transactions",
            "portfolio": "Layer 5: Portfolio Returns",
        }

        layers_completed = self.session.layers_completed or []

        for layer in all_layers:
            layer_findings = [f for f in self.session.findings if f.layer == layer]
            layer_bugs = [f for f in layer_findings if f.classification == "BUG"]
            layer_design = [f for f in layer_findings if f.classification == "DESIGN"]

            lines.append(f"### {layer_names[layer]}")

            # Determine layer status
            if layer not in layers_completed:
                lines.append("**Status:** PENDING")
            elif layer_bugs:
                unresolved = [f for f in layer_bugs if not f.resolved]
                if unresolved:
                    lines.append(f"**Status:** FAILED ({len(unresolved)} unresolved BUG findings)")
                else:
                    lines.append(f"**Status:** PASSED ({len(layer_bugs)} BUG findings, all fixed)")
            elif layer_design:
                lines.append(f"**Status:** PASSED ({len(layer_design)} DESIGN findings)")
            elif layer_findings:
                unclassified = [f for f in layer_findings if f.classification is None]
                lines.append(f"**Status:** NEEDS INVESTIGATION ({len(unclassified)} unclassified)")
            else:
                lines.append("**Status:** PASSED")
                lines.append("")
                lines.append("No discrepancies detected.")
                lines.append("")
                continue

            lines.append("")

            # Add findings table if any
            if layer_findings:
                lines.append("| Finding | Classification | Description |")
                lines.append("|---------|---------------|-------------|")
                for f in layer_findings:
                    classification = f.classification or "Unclassified"
                    # Truncate description for table
                    desc = f.description[:50] + "..." if len(f.description) > 50 else f.description
                    lines.append(f"| {f.id} | {classification} | {desc} |")

            lines.append("")

        return lines

    def _generate_findings_detail(self) -> list[str]:
        """Generate the detailed findings section."""
        lines: list[str] = []

        for finding in self.session.findings:
            lines.append(f"### {finding.id}: {finding.description[:60]}")
            lines.append("")
            lines.append(f"**Classification:** {finding.classification or 'Unclassified'}")
            lines.append(f"**Layer:** {finding.layer}")

            if finding.rustybt_value is not None or finding.backtrader_value is not None:
                lines.append(f"**rustybt Value:** {finding.rustybt_value}")
                lines.append(f"**Backtrader Value:** {finding.backtrader_value}")

            if finding.rationale:
                lines.append("")
                lines.append(f"**Rationale:** {finding.rationale}")

            # BUG-specific fields
            if finding.classification == "BUG":
                if finding.severity:
                    lines.append(f"**Severity:** {finding.severity}")
                if finding.affected_components:
                    lines.append(f"**Affected Components:** {', '.join(finding.affected_components)}")
                if finding.suggested_fix:
                    lines.append(f"**Suggested Fix:** {finding.suggested_fix}")
                if finding.resolved:
                    lines.append(f"**Status:** Resolved")
                    if finding.resolved_at:
                        lines.append(f"**Resolved At:** {finding.resolved_at.strftime('%Y-%m-%d %H:%M')}")
                    if finding.regression_test:
                        lines.append(f"**Regression Test:** {finding.regression_test}")
                else:
                    lines.append("**Status:** Open")

            # DESIGN-specific fields
            if finding.classification == "DESIGN":
                if finding.design_rationale:
                    lines.append(f"**Design Rationale:** {finding.design_rationale}")
                if finding.design_choice:
                    lines.append(f"**Preferred Approach:** {finding.design_choice}")
                if finding.user_impact:
                    lines.append(f"**User Impact:** {finding.user_impact}")
                if finding.acceptance_criteria:
                    lines.append(f"**Acceptance Criteria:** {finding.acceptance_criteria}")
                if finding.documentation_ref:
                    lines.append(f"**Documentation:** {finding.documentation_ref}")

            if finding.investigated_by:
                lines.append("")
                lines.append(f"*Investigated by {finding.investigated_by}*")
                if finding.investigated_at:
                    lines.append(f"*on {finding.investigated_at.strftime('%Y-%m-%d %H:%M')}*")

            lines.append("")
            lines.append("---")
            lines.append("")

        return lines

    def _finding_to_dict(self, finding: Finding) -> dict[str, Any]:
        """Convert a Finding to a JSON-serializable dictionary."""
        return {
            "id": finding.id,
            "layer": finding.layer,
            "description": finding.description,
            "classification": finding.classification,
            "rationale": finding.rationale,
            "rustybt_value": finding.rustybt_value,
            "backtrader_value": finding.backtrader_value,
            "resolved": finding.resolved,
            "resolved_at": finding.resolved_at.isoformat() if finding.resolved_at else None,
            "regression_test": finding.regression_test,
            "severity": finding.severity,
            "affected_components": finding.affected_components,
            "suggested_fix": finding.suggested_fix,
            "design_rationale": finding.design_rationale,
            "design_choice": finding.design_choice,
            "user_impact": finding.user_impact,
            "acceptance_criteria": finding.acceptance_criteria,
            "documentation_ref": finding.documentation_ref,
            "investigated_by": finding.investigated_by,
            "investigated_at": finding.investigated_at.isoformat() if finding.investigated_at else None,
        }


class LayerReportGenerator:
    """Generate cross-strategy reports for a specific validation layer.

    LayerReportGenerator aggregates findings across all validated sessions
    for a specific layer and identifies common patterns.

    Attributes:
        layer: The validation layer name (data, signals, orders, broker, portfolio).
        session_manager: SessionManager for loading sessions.
        generated_at: Timestamp when the report was generated.

    Example:
        >>> from rustybt.validation.reporting import LayerReportGenerator
        >>> from rustybt.validation.session import SessionManager
        >>>
        >>> sm = SessionManager()
        >>> generator = LayerReportGenerator("signals", sm)
        >>> report = generator.generate()
        >>> print(report)
    """

    def __init__(self, layer: str, session_manager: SessionManager) -> None:
        """Initialize LayerReportGenerator.

        Args:
            layer: Layer name (data, signals, orders, broker, portfolio).
            session_manager: SessionManager for loading sessions.

        Raises:
            ValueError: If layer name is not valid.
        """
        if layer not in LAYER_NUMBERS:
            valid = ", ".join(LAYER_NUMBERS.keys())
            raise ValueError(f"Invalid layer: {layer}. Valid layers: {valid}")

        self.layer = layer
        self.session_manager = session_manager
        self.generated_at = datetime.now()

    def generate(self) -> str:
        """Generate a markdown report for the layer.

        Returns:
            Markdown-formatted layer report string.
        """
        lines: list[str] = []
        layer_num = LAYER_NUMBERS[self.layer]

        # Header
        lines.append(f"# Layer {layer_num}: {self.layer.title()} - Validation Report")
        lines.append("")
        lines.append(f"**Report Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Overview
        lines.append("## Overview")
        lines.append("")
        lines.append(LAYER_DESCRIPTIONS.get(self.layer, ""))
        lines.append("")

        # Load sessions and findings
        sessions = self._load_completed_sessions()
        strategy_data = self._aggregate_by_strategy(sessions)
        all_findings = self._get_layer_findings(sessions)

        # Strategy Results table
        lines.append("## Strategy Results")
        lines.append("")
        lines.extend(self._generate_strategy_table(strategy_data))
        lines.append("")

        # Common DESIGN Differences
        design_findings = [f for f in all_findings if f.classification == "DESIGN"]
        if design_findings:
            patterns = self.identify_common_patterns(design_findings, sessions)
            lines.append("## Common DESIGN Differences")
            lines.append("")
            lines.extend(self._generate_patterns_section(patterns))

        # BUG Findings (if any)
        bug_findings = [f for f in all_findings if f.classification == "BUG"]
        if bug_findings:
            lines.append("## BUG Findings")
            lines.append("")
            lines.extend(self._generate_bugs_section(bug_findings, sessions))

        return "\n".join(lines)

    def save(self, output_dir: Path | None = None) -> Path:
        """Save the layer report to a file.

        Args:
            output_dir: Directory to save to. Defaults to docs/validation/

        Returns:
            Path to saved report file.
        """
        if output_dir is None:
            output_dir = Path("docs/validation")

        output_dir.mkdir(parents=True, exist_ok=True)
        layer_num = LAYER_NUMBERS[self.layer]
        filename = f"layer-{layer_num}-{self.layer}-report.md"
        report_path = output_dir / filename

        content = self.generate()
        report_path.write_text(content)

        return report_path

    def get_layer_findings(self) -> list[Any]:
        """Get all findings for this layer across sessions.

        Returns:
            List of Finding objects for this layer.
        """
        sessions = self._load_completed_sessions()
        return self._get_layer_findings(sessions)

    def identify_common_patterns(
        self, findings: list[Any], sessions: list[Any]
    ) -> list[CommonPattern]:
        """Identify common DESIGN patterns across findings.

        Groups similar findings based on description similarity and
        counts affected strategies.

        Args:
            findings: List of DESIGN findings to analyze.
            sessions: List of sessions for strategy mapping.

        Returns:
            List of CommonPattern objects.
        """
        # Build session ID to strategy name mapping
        session_to_strategy = {s.id: s.strategy_name for s in sessions}

        # Group findings by normalized description
        groups: dict[str, list[tuple[Any, str]]] = defaultdict(list)

        for finding in findings:
            # Normalize description for grouping
            key = self._normalize_description(finding.description)
            # Find strategy name for this finding
            strategy = self._find_strategy_for_finding(finding, sessions)
            groups[key].append((finding, strategy))

        # Convert groups to CommonPattern objects
        patterns: list[CommonPattern] = []
        for desc_key, finding_strategy_pairs in groups.items():
            if len(finding_strategy_pairs) >= 1:  # Include all patterns
                affected = list(set(s for _, s in finding_strategy_pairs if s))
                sample_finding = finding_strategy_pairs[0][0]

                pattern = CommonPattern(
                    description=sample_finding.description,
                    affected_strategies=affected,
                    user_impact=sample_finding.user_impact or "",
                    workaround="None needed" if not sample_finding.suggested_fix else sample_finding.suggested_fix,
                    findings=[f for f, _ in finding_strategy_pairs],
                )
                patterns.append(pattern)

        # Sort by number of affected strategies (descending)
        patterns.sort(key=lambda p: len(p.affected_strategies), reverse=True)
        return patterns

    def _load_completed_sessions(self) -> list[Any]:
        """Load all completed sessions."""
        from rustybt.validation.models import SessionStage

        # Get all sessions with any status that have completed comparison
        all_sessions = self.session_manager.list_sessions()
        completed = []
        for s in all_sessions:
            # Include sessions that have completed comparison or are fully complete
            if s.stage in (
                SessionStage.COMPARED,
                SessionStage.INVESTIGATING,
                SessionStage.COMPLETED,
            ) or s.status == "COMPLETED":
                completed.append(s)
        return completed

    def _get_layer_findings(self, sessions: list[Any]) -> list[Any]:
        """Get all findings for this layer from sessions."""
        findings = []
        for session in sessions:
            for finding in session.findings:
                if finding.layer == self.layer:
                    findings.append(finding)
        return findings

    def _aggregate_by_strategy(
        self, sessions: list[Any]
    ) -> dict[str, dict[str, Any]]:
        """Aggregate layer findings by strategy.

        Returns:
            Dict mapping strategy name to findings data.
        """
        result: dict[str, dict[str, Any]] = {}

        for session in sessions:
            strategy = session.strategy_name
            layer_findings = [f for f in session.findings if f.layer == self.layer]

            if strategy not in result:
                result[strategy] = {
                    "status": "PASS",
                    "findings": [],
                    "bug_count": 0,
                    "design_count": 0,
                    "notes": [],
                }

            result[strategy]["findings"].extend(layer_findings)

            for finding in layer_findings:
                if finding.classification == "BUG":
                    result[strategy]["bug_count"] += 1
                    result[strategy]["status"] = "FAIL"
                elif finding.classification == "DESIGN":
                    result[strategy]["design_count"] += 1
                    # Add note about DESIGN findings
                    short_desc = finding.description[:30]
                    if short_desc not in result[strategy]["notes"]:
                        result[strategy]["notes"].append(short_desc)

        return result

    def _generate_strategy_table(
        self, strategy_data: dict[str, dict[str, Any]]
    ) -> list[str]:
        """Generate the strategy results table."""
        lines: list[str] = []

        if not strategy_data:
            lines.append("*No validated strategies found for this layer.*")
            return lines

        lines.append("| Strategy | Status | Findings | Notes |")
        lines.append("|----------|--------|----------|-------|")

        for strategy, data in sorted(strategy_data.items()):
            status = "PASS" if data["status"] == "PASS" else "FAIL"
            status_icon = "PASS" if status == "PASS" else "FAIL"

            findings = []
            if data["bug_count"] > 0:
                findings.append(f"{data['bug_count']} BUG")
            if data["design_count"] > 0:
                findings.append(f"{data['design_count']} DESIGN")
            findings_str = ", ".join(findings) if findings else "0"

            notes = ", ".join(data["notes"][:2]) if data["notes"] else "-"
            if len(notes) > 40:
                notes = notes[:37] + "..."

            lines.append(f"| {strategy} | {status_icon} | {findings_str} | {notes} |")

        return lines

    def _generate_patterns_section(self, patterns: list[CommonPattern]) -> list[str]:
        """Generate the common patterns section."""
        lines: list[str] = []

        if not patterns:
            lines.append("*No common DESIGN patterns found.*")
            return lines

        for i, pattern in enumerate(patterns, 1):
            affected_count = len(pattern.affected_strategies)
            affected_str = f"({affected_count} strategies affected)" if affected_count > 1 else "(1 strategy)"

            lines.append(f"### Pattern {i}: {pattern.description[:60]} {affected_str}")
            lines.append("")
            lines.append(f"**Description:** {pattern.description}")
            lines.append("")

            if pattern.affected_strategies:
                lines.append(f"**Affected Strategies:** {', '.join(pattern.affected_strategies)}")

            if pattern.user_impact:
                lines.append(f"**User Impact:** {pattern.user_impact}")
            else:
                lines.append("**User Impact:** Minor numerical differences")

            lines.append(f"**Workaround:** {pattern.workaround or 'None needed'}")
            lines.append("")

        return lines

    def _generate_bugs_section(
        self, findings: list[Any], sessions: list[Any]
    ) -> list[str]:
        """Generate the BUG findings section."""
        lines: list[str] = []

        for finding in findings:
            strategy = self._find_strategy_for_finding(finding, sessions)
            status = "Resolved" if finding.resolved else "Open"

            lines.append(f"### {finding.id}")
            lines.append("")
            lines.append(f"**Strategy:** {strategy or 'Unknown'}")
            lines.append(f"**Status:** {status}")
            lines.append(f"**Description:** {finding.description}")

            if finding.severity:
                lines.append(f"**Severity:** {finding.severity}")
            if finding.suggested_fix:
                lines.append(f"**Fix:** {finding.suggested_fix}")

            lines.append("")

        return lines

    def _normalize_description(self, description: str) -> str:
        """Normalize description for pattern matching.

        Extracts key terms to group similar findings.
        """
        # Simple normalization: lowercase and extract key words
        words = description.lower().split()
        # Remove common words
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or"}
        key_words = [w for w in words if w not in stopwords and len(w) > 2]
        return " ".join(sorted(key_words[:5]))  # Use first 5 key words

    def _find_strategy_for_finding(
        self, finding: Any, sessions: list[Any]
    ) -> str:
        """Find the strategy name for a finding."""
        for session in sessions:
            if finding in session.findings:
                return session.strategy_name
        return ""


# Strategy name to display name mapping
STRATEGY_DISPLAY_NAMES: dict[str, str] = {
    "sma_crossover": "SMA Crossover",
    "mean_reversion": "Mean Reversion",
    "momentum": "Momentum",
    "multi_factor": "Multi-Factor",
}

# Strategy descriptions
STRATEGY_DESCRIPTIONS: dict[str, str] = {
    "sma_crossover": "Simple Moving Average Crossover strategy that generates signals based on fast/slow SMA crossovers.",
    "mean_reversion": "Mean Reversion strategy that trades based on z-score deviations from rolling mean.",
    "momentum": "Momentum strategy using RSI and trailing stops to capture trending moves.",
    "multi_factor": "Multi-Factor strategy combining EMA, RSI, and MACD indicators for signal generation.",
}

# Strategy parameters (default/typical values)
STRATEGY_PARAMETERS: dict[str, dict[str, Any]] = {
    "sma_crossover": {"fast_period": 10, "slow_period": 30},
    "mean_reversion": {"period": 20, "z_threshold": 2.0},
    "momentum": {"rsi_period": 14, "trailing_stop": 0.05},
    "multi_factor": {"ema_period": 20, "rsi_period": 14, "macd_fast": 12, "macd_slow": 26},
}


class StrategyReportGenerator:
    """Generate validation reports for a specific strategy across all layers.

    StrategyReportGenerator creates a comprehensive report for a single strategy
    showing validation results across all 5 layers with findings and recommendations.

    Attributes:
        strategy_name: The strategy name to generate report for.
        session_manager: SessionManager for loading sessions.
        generated_at: Timestamp when the report was generated.

    Example:
        >>> from rustybt.validation.reporting import StrategyReportGenerator
        >>> from rustybt.validation.session import SessionManager
        >>>
        >>> sm = SessionManager()
        >>> generator = StrategyReportGenerator("sma_crossover", sm)
        >>> report = generator.generate()
        >>> print(report)
    """

    def __init__(self, strategy_name: str, session_manager: SessionManager) -> None:
        """Initialize StrategyReportGenerator.

        Args:
            strategy_name: Strategy name to generate report for.
            session_manager: SessionManager for loading sessions.
        """
        self.strategy_name = strategy_name
        self.session_manager = session_manager
        self.generated_at = datetime.now()

    def generate(self) -> str:
        """Generate a markdown report for the strategy.

        Returns:
            Markdown-formatted strategy report string.
        """
        lines: list[str] = []

        # Get display name
        display_name = STRATEGY_DISPLAY_NAMES.get(
            self.strategy_name, self.strategy_name.replace("_", " ").title()
        )

        # Header
        lines.append(f"# {display_name} Strategy - Validation Report")
        lines.append("")
        lines.append(f"**Report Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Strategy Overview
        lines.append("## Strategy Overview")
        lines.append("")
        description = STRATEGY_DESCRIPTIONS.get(
            self.strategy_name,
            f"Validation report for {display_name} strategy against Backtrader.",
        )
        lines.append(description)
        lines.append("")

        # Parameters
        params = STRATEGY_PARAMETERS.get(self.strategy_name, {})
        if params:
            lines.append("**Parameters:**")
            for param, value in params.items():
                param_display = param.replace("_", " ").title()
                lines.append(f"- {param_display}: {value}")
            lines.append("")

        # Get session data
        session = self._get_latest_session()
        if session is None:
            lines.append("## Validation Results")
            lines.append("")
            lines.append("*No validation sessions found for this strategy.*")
            return "\n".join(lines)

        # Validation Results Table
        lines.append("## Validation Results")
        lines.append("")
        lines.extend(self._generate_validation_table(session))
        lines.append("")

        # Overall Status
        overall_status = self.calculate_overall_status(session)
        lines.append(f"**Overall Status:** {overall_status}")
        lines.append("")

        # Findings Summary
        if session.findings:
            lines.append("## Findings Summary")
            lines.append("")
            lines.extend(self._generate_findings_summary(session))
            lines.append("")

        # Recommendations
        recommendations = self.generate_recommendations(session.findings)
        if recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for rec in recommendations:
                lines.append(f"- {rec}")
            lines.append("")
        else:
            lines.append("## Recommendations")
            lines.append("")
            lines.append("- Strategy behaves identically to Backtrader for practical trading purposes")
            lines.append("- No significant differences detected")
            lines.append("")

        return "\n".join(lines)

    def save(self, output_dir: Path | None = None) -> Path:
        """Save the strategy report to a file.

        Args:
            output_dir: Directory to save to. Defaults to docs/validation/

        Returns:
            Path to saved report file.
        """
        if output_dir is None:
            output_dir = Path("docs/validation")

        output_dir.mkdir(parents=True, exist_ok=True)
        # Normalize strategy name for filename (use hyphens)
        filename = f"strategy-{self.strategy_name.replace('_', '-')}-report.md"
        report_path = output_dir / filename

        content = self.generate()
        report_path.write_text(content)

        return report_path

    def calculate_overall_status(self, session: Any) -> str:
        """Calculate the overall validation status.

        Args:
            session: Session to calculate status for.

        Returns:
            Status string: "✓ VALIDATED", "⚠ PARTIAL", or "✗ FAILED"
        """
        all_layers = ["data", "signals", "orders", "broker", "portfolio"]
        layers_completed = session.layers_completed or []

        # Check for any BUG findings
        bug_findings = [f for f in session.findings if f.classification == "BUG" and not f.resolved]
        if bug_findings:
            return "✗ FAILED"

        # Check if all layers are completed
        if set(all_layers) <= set(layers_completed):
            return "✓ VALIDATED"

        # Partial completion
        if layers_completed:
            return "⚠ PARTIAL"

        return "⚠ NOT STARTED"

    def generate_recommendations(self, findings: list[Any]) -> list[str]:
        """Generate recommendations based on findings.

        Args:
            findings: List of findings to generate recommendations for.

        Returns:
            List of recommendation strings.
        """
        recommendations: list[str] = []

        design_findings = [f for f in findings if f.classification == "DESIGN"]
        bug_findings = [f for f in findings if f.classification == "BUG"]

        # Generate recommendations for DESIGN differences
        for finding in design_findings:
            rec = self._finding_to_recommendation(finding)
            if rec and rec not in recommendations:
                recommendations.append(rec)

        # Generate recommendations for unresolved BUGs
        for finding in bug_findings:
            if not finding.resolved:
                rec = f"**Action Required:** {finding.description} (see {finding.id})"
                recommendations.append(rec)

        return recommendations

    def _get_latest_session(self) -> Any | None:
        """Get the most recent session for this strategy."""
        from rustybt.validation.models import SessionStage

        all_sessions = self.session_manager.list_sessions()
        strategy_sessions = []

        for s in all_sessions:
            if s.strategy_name == self.strategy_name:
                # Include completed or progressing sessions
                if s.stage in (
                    SessionStage.COMPARED,
                    SessionStage.INVESTIGATING,
                    SessionStage.COMPLETED,
                ) or s.status == "COMPLETED":
                    strategy_sessions.append(s)

        if not strategy_sessions:
            return None

        # Return most recent by created_at
        return max(strategy_sessions, key=lambda s: s.created_at)

    def _generate_validation_table(self, session: Any) -> list[str]:
        """Generate the validation results table."""
        lines: list[str] = []
        all_layers = ["data", "signals", "orders", "broker", "portfolio"]
        layer_display = {
            "data": "Data Handling",
            "signals": "Signal Computation",
            "orders": "Order Lifecycle",
            "broker": "Broker Transactions",
            "portfolio": "Portfolio Returns",
        }

        layers_completed = session.layers_completed or []

        lines.append("| Layer | Status | Findings |")
        lines.append("|-------|--------|----------|")

        for layer in all_layers:
            display_name = layer_display[layer]
            layer_findings = [f for f in session.findings if f.layer == layer]
            bug_count = sum(1 for f in layer_findings if f.classification == "BUG")
            design_count = sum(1 for f in layer_findings if f.classification == "DESIGN")

            if layer not in layers_completed:
                status = "⏳ PENDING"
                findings_str = "-"
            elif bug_count > 0:
                unresolved = sum(1 for f in layer_findings if f.classification == "BUG" and not f.resolved)
                if unresolved > 0:
                    status = "✗ FAIL"
                else:
                    status = "✓ PASS"
                findings_str = f"{bug_count} BUG"
                if design_count > 0:
                    findings_str += f", {design_count} DESIGN"
            elif design_count > 0:
                status = "✓ PASS"
                findings_str = f"{design_count} DESIGN"
            else:
                status = "✓ PASS"
                findings_str = "0"

            lines.append(f"| {display_name} | {status} | {findings_str} |")

        return lines

    def _generate_findings_summary(self, session: Any) -> list[str]:
        """Generate the findings summary section."""
        lines: list[str] = []
        all_layers = ["data", "signals", "orders", "broker", "portfolio"]

        for layer in all_layers:
            layer_findings = [f for f in session.findings if f.layer == layer]
            if not layer_findings:
                continue

            layer_display = {
                "data": "Data Handling",
                "signals": "Signal Computation",
                "orders": "Order Lifecycle",
                "broker": "Broker Transactions",
                "portfolio": "Portfolio Returns",
            }

            lines.append(f"### {layer_display[layer]}")
            lines.append("")

            for finding in layer_findings:
                lines.append(f"**{finding.id}:** {finding.description}")
                if finding.classification:
                    lines.append(f"- Classification: {finding.classification}")
                if finding.rationale:
                    lines.append(f"- Rationale: {finding.rationale}")
                if finding.user_impact:
                    lines.append(f"- User Impact: {finding.user_impact}")
                lines.append("")

        return lines

    def _finding_to_recommendation(self, finding: Any) -> str:
        """Convert a finding to a user-friendly recommendation."""
        if finding.user_impact:
            return f"{finding.user_impact} (see {finding.id})"
        elif finding.design_rationale:
            return f"{finding.description}: {finding.design_rationale} (see {finding.id})"
        elif "RSI" in finding.description.upper():
            return f"RSI values may differ slightly from Backtrader (see {finding.id})"
        elif "MACD" in finding.description.upper():
            return f"MACD calculation may differ in initialization period (see {finding.id})"
        elif "timestamp" in finding.description.lower():
            return f"Timestamp precision differs (see {finding.id})"
        else:
            return f"{finding.description} (see {finding.id})"


# Story 7.4: Status Dashboard

# Box-drawing characters for ASCII tables
BOX_TOP_LEFT = "┌"
BOX_TOP_RIGHT = "┐"
BOX_BOTTOM_LEFT = "└"
BOX_BOTTOM_RIGHT = "┘"
BOX_HORIZONTAL = "─"
BOX_VERTICAL = "│"
BOX_T_DOWN = "┬"
BOX_T_UP = "┴"
BOX_T_RIGHT = "├"
BOX_T_LEFT = "┤"
BOX_CROSS = "┼"
BOX_DOUBLE_HORIZONTAL = "═"

# Progress bar characters
PROGRESS_FILLED = "█"
PROGRESS_EMPTY = "░"

# ANSI color codes
ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_RESET = "\033[0m"


def supports_color() -> bool:
    """Check if terminal supports ANSI colors."""
    import os
    import sys

    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False

    # Check for NO_COLOR environment variable
    if os.environ.get("NO_COLOR"):
        return False

    # Check for TERM environment variable
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False

    return True


def colorize(text: str, color: str) -> str:
    """Apply ANSI color to text if terminal supports it."""
    if supports_color():
        return f"{color}{text}{ANSI_RESET}"
    return text


def render_progress_bar(percentage: float, width: int = 10) -> str:
    """Render a Unicode progress bar.

    Args:
        percentage: Progress percentage (0-100)
        width: Width of the progress bar in characters

    Returns:
        Progress bar string like "████████░░"
    """
    filled = int(percentage * width / 100)
    empty = width - filled
    return PROGRESS_FILLED * filled + PROGRESS_EMPTY * empty


@dataclass
class DashboardData:
    """Data structure for status dashboard.

    Attributes:
        strategies_validated: Number of strategies with completed validation
        total_strategies: Total number of strategies to validate
        strategies: List of strategy result dictionaries
        layers_covered: Number of layers with all strategies passing
        total_layers: Total expected layer validations (strategies * 5)
        layers: List of layer status dictionaries
        total_findings: Total findings count
        bug_count: Number of BUG findings
        bug_fixed_count: Number of resolved BUG findings
        design_count: Number of DESIGN findings
        regression_tests: Number of regression tests created
        confidence: Overall confidence score (0-100)
        generated_at: When the dashboard data was generated
    """

    strategies_validated: int
    total_strategies: int
    strategies: list[dict[str, Any]]
    layers_covered: int
    total_layers: int
    layers: list[dict[str, Any]]
    total_findings: int
    bug_count: int
    bug_fixed_count: int
    design_count: int
    regression_tests: int
    confidence: float
    generated_at: datetime = field(default_factory=datetime.now)


class StatusDashboard:
    """Generate overall validation status dashboard.

    StatusDashboard aggregates data across all validation sessions to provide
    a comprehensive view of validation progress and health.

    Attributes:
        session_manager: SessionManager for loading sessions
        generated_at: Timestamp when dashboard was generated

    Example:
        >>> from rustybt.validation.reporting import StatusDashboard
        >>> from rustybt.validation.session import SessionManager
        >>>
        >>> sm = SessionManager()
        >>> dashboard = StatusDashboard(sm)
        >>> print(dashboard.render())
        >>>
        >>> # Get JSON for CI
        >>> data = dashboard.to_json()
    """

    # Expected strategies for validation
    EXPECTED_STRATEGIES = ["sma_crossover", "mean_reversion", "momentum", "multi_factor"]
    LAYERS = ["data", "signals", "orders", "broker", "portfolio"]

    def __init__(self, session_manager: "SessionManager | None" = None) -> None:
        """Initialize StatusDashboard.

        Args:
            session_manager: Optional SessionManager. If None, creates a new one.
        """
        if session_manager is None:
            from rustybt.validation.session import SessionManager
            session_manager = SessionManager()
        self.session_manager = session_manager
        self.generated_at = datetime.now()

    def get_data(self) -> DashboardData:
        """Aggregate all validation data for dashboard.

        Returns:
            DashboardData with all aggregated information.
        """
        sessions = self._load_completed_sessions()

        # Build strategy results
        strategies: list[dict[str, Any]] = []
        strategy_sessions: dict[str, Any] = {}

        for session in sessions:
            name = session.strategy_name
            # Keep the most recent session per strategy
            if name not in strategy_sessions or session.created_at > strategy_sessions[name].created_at:
                strategy_sessions[name] = session

        for strategy in self.EXPECTED_STRATEGIES:
            session = strategy_sessions.get(strategy)
            if session:
                bug_count = sum(1 for f in session.findings if f.classification == "BUG" and not f.resolved)
                status = "✓ VALID" if bug_count == 0 else "✗ FAIL"
                strategies.append({
                    "name": STRATEGY_DISPLAY_NAMES.get(strategy, strategy),
                    "status": status,
                    "findings": len(session.findings),
                    "bugs": sum(1 for f in session.findings if f.classification == "BUG"),
                    "last_run": session.created_at.strftime("%Y-%m-%d"),
                })
            else:
                strategies.append({
                    "name": STRATEGY_DISPLAY_NAMES.get(strategy, strategy),
                    "status": "⏳ PENDING",
                    "findings": 0,
                    "bugs": 0,
                    "last_run": "-",
                })

        strategies_validated = sum(1 for s in strategies if "VALID" in s["status"])

        # Build layer coverage data
        layers: list[dict[str, Any]] = []
        layer_names = {
            "data": "1. Data Handling",
            "signals": "2. Signals",
            "orders": "3. Orders",
            "broker": "4. Broker",
            "portfolio": "5. Portfolio",
        }

        total_layers_validated = 0
        for layer in self.LAYERS:
            # Count strategies that have this layer completed
            strategies_with_layer = 0
            design_count = 0
            for session in strategy_sessions.values():
                if layer in (session.layers_completed or []):
                    strategies_with_layer += 1
                design_count += sum(
                    1 for f in session.findings
                    if f.layer == layer and f.classification == "DESIGN"
                )

            total_layers_validated += strategies_with_layer

            if strategies_with_layer == len(self.EXPECTED_STRATEGIES):
                status = "✓ PASS"
            elif strategies_with_layer > 0:
                status = "⚠ PARTIAL"
            else:
                status = "⏳ PENDING"

            notes = []
            if design_count > 0:
                notes.append(f"{design_count} DESIGN differences noted")
            if strategies_with_layer > 0:
                notes.append(f"{strategies_with_layer}/{len(self.EXPECTED_STRATEGIES)} strategies")

            layers.append({
                "name": layer_names[layer],
                "status": status,
                "notes": ", ".join(notes) if notes else "All strategies",
            })

        layers_covered = sum(1 for l in layers if l["status"] == "✓ PASS")

        # Count all findings
        all_findings = []
        for session in strategy_sessions.values():
            all_findings.extend(session.findings)

        total_findings = len(all_findings)
        bug_count = sum(1 for f in all_findings if f.classification == "BUG")
        bug_fixed = sum(1 for f in all_findings if f.classification == "BUG" and f.resolved)
        design_count = sum(1 for f in all_findings if f.classification == "DESIGN")
        regression_tests = sum(1 for f in all_findings if f.regression_test)

        # Calculate confidence score
        confidence = self._calculate_confidence(
            strategies_validated=strategies_validated,
            total_strategies=len(self.EXPECTED_STRATEGIES),
            layers_validated=total_layers_validated,
            total_layer_validations=len(self.EXPECTED_STRATEGIES) * len(self.LAYERS),
            resolved_findings=bug_fixed + design_count,
            total_findings=total_findings,
        )

        return DashboardData(
            strategies_validated=strategies_validated,
            total_strategies=len(self.EXPECTED_STRATEGIES),
            strategies=strategies,
            layers_covered=layers_covered,
            total_layers=len(self.LAYERS),
            layers=layers,
            total_findings=total_findings,
            bug_count=bug_count,
            bug_fixed_count=bug_fixed,
            design_count=design_count,
            regression_tests=regression_tests,
            confidence=confidence,
            generated_at=self.generated_at,
        )

    def _calculate_confidence(
        self,
        strategies_validated: int,
        total_strategies: int,
        layers_validated: int,
        total_layer_validations: int,
        resolved_findings: int,
        total_findings: int,
    ) -> float:
        """Calculate overall validation confidence score.

        Weights:
        - Strategy coverage: 40%
        - Layer coverage: 30%
        - Finding resolution: 30%

        Returns:
            Confidence score as percentage (0-100)
        """
        strategy_score = strategies_validated / total_strategies if total_strategies > 0 else 0
        layer_score = layers_validated / total_layer_validations if total_layer_validations > 0 else 0
        finding_score = resolved_findings / total_findings if total_findings > 0 else 1.0

        confidence = (strategy_score * 0.4) + (layer_score * 0.3) + (finding_score * 0.3)
        return confidence * 100

    def _get_confidence_label(self, confidence: float) -> str:
        """Get human-readable confidence label."""
        if confidence >= 90:
            return "HIGH"
        elif confidence >= 70:
            return "MEDIUM"
        elif confidence >= 50:
            return "LOW"
        else:
            return "VERY LOW"

    def render(self) -> str:
        """Generate ASCII dashboard display.

        Returns:
            Formatted dashboard string with tables and progress indicators.
        """
        data = self.get_data()
        lines: list[str] = []

        # Header
        lines.append(BOX_DOUBLE_HORIZONTAL * 63)
        lines.append("                   rustybt Validation Status")
        lines.append(BOX_DOUBLE_HORIZONTAL * 63)
        lines.append("")

        # Strategies table
        lines.append(f"Strategies Validated: {data.strategies_validated}/{data.total_strategies}")
        lines.append(self._render_strategies_table(data.strategies))
        lines.append("")

        # Layer coverage table
        lines.append(f"Layer Coverage: {data.layers_covered}/{data.total_layers} ({int(data.layers_covered / data.total_layers * 100) if data.total_layers else 0}%)")
        lines.append(self._render_layers_table(data.layers))
        lines.append("")

        # Findings summary
        lines.append("Findings Summary:")
        bug_status = f"{data.bug_count}"
        if data.bug_fixed_count > 0:
            bug_status += f" (all fixed ✓)" if data.bug_fixed_count == data.bug_count else f" ({data.bug_fixed_count} fixed)"
        design_status = f"{data.design_count}"
        if data.design_count > 0:
            design_status += " (all documented ✓)"

        lines.append(f"  Total: {data.total_findings}")
        lines.append(f"  BUG: {bug_status}")
        lines.append(f"  DESIGN: {design_status}")
        lines.append(f"  Regression Tests: {data.regression_tests}")
        lines.append("")

        # Confidence score
        confidence_label = self._get_confidence_label(data.confidence)
        progress_bar = render_progress_bar(data.confidence, 11)
        confidence_line = f"Overall Confidence: {confidence_label} {progress_bar} {int(data.confidence)}%"
        if "HIGH" in confidence_label:
            confidence_line = colorize(confidence_line, ANSI_GREEN)
        elif "LOW" in confidence_label:
            confidence_line = colorize(confidence_line, ANSI_YELLOW)
        lines.append(confidence_line)
        lines.append("")

        lines.append(BOX_DOUBLE_HORIZONTAL * 63)

        return "\n".join(lines)

    def _render_strategies_table(self, strategies: list[dict[str, Any]]) -> str:
        """Render strategies table with box-drawing characters."""
        lines: list[str] = []

        # Column widths
        col_widths = [18, 11, 11, 12]

        # Top border
        lines.append(
            BOX_TOP_LEFT +
            BOX_HORIZONTAL * col_widths[0] + BOX_T_DOWN +
            BOX_HORIZONTAL * col_widths[1] + BOX_T_DOWN +
            BOX_HORIZONTAL * col_widths[2] + BOX_T_DOWN +
            BOX_HORIZONTAL * col_widths[3] + BOX_TOP_RIGHT
        )

        # Header
        lines.append(
            BOX_VERTICAL + " Strategy".ljust(col_widths[0] - 1) +
            BOX_VERTICAL + " Status".ljust(col_widths[1] - 1) +
            BOX_VERTICAL + " Findings".ljust(col_widths[2] - 1) +
            BOX_VERTICAL + " Last Run".ljust(col_widths[3] - 1) + BOX_VERTICAL
        )

        # Header separator
        lines.append(
            BOX_T_RIGHT +
            BOX_HORIZONTAL * col_widths[0] + BOX_CROSS +
            BOX_HORIZONTAL * col_widths[1] + BOX_CROSS +
            BOX_HORIZONTAL * col_widths[2] + BOX_CROSS +
            BOX_HORIZONTAL * col_widths[3] + BOX_T_LEFT
        )

        # Data rows
        for s in strategies:
            findings_str = f"{s['findings']} ({s['bugs']} BUG)"
            status = s["status"]
            if "VALID" in status:
                status = colorize(status, ANSI_GREEN)
            elif "FAIL" in status:
                status = colorize(status, ANSI_RED)

            lines.append(
                BOX_VERTICAL + f" {s['name'][:col_widths[0]-2]}".ljust(col_widths[0] - 1) +
                BOX_VERTICAL + f" {status}".ljust(col_widths[1] - 1 + (len(status) - len(s["status"]))) +
                BOX_VERTICAL + f" {findings_str[:col_widths[2]-2]}".ljust(col_widths[2] - 1) +
                BOX_VERTICAL + f" {s['last_run']}".ljust(col_widths[3] - 1) + BOX_VERTICAL
            )

        # Bottom border
        lines.append(
            BOX_BOTTOM_LEFT +
            BOX_HORIZONTAL * col_widths[0] + BOX_T_UP +
            BOX_HORIZONTAL * col_widths[1] + BOX_T_UP +
            BOX_HORIZONTAL * col_widths[2] + BOX_T_UP +
            BOX_HORIZONTAL * col_widths[3] + BOX_BOTTOM_RIGHT
        )

        return "\n".join(lines)

    def _render_layers_table(self, layers: list[dict[str, Any]]) -> str:
        """Render layers table with box-drawing characters."""
        lines: list[str] = []

        # Column widths
        col_widths = [20, 8, 31]

        # Top border
        lines.append(
            BOX_TOP_LEFT +
            BOX_HORIZONTAL * col_widths[0] + BOX_T_DOWN +
            BOX_HORIZONTAL * col_widths[1] + BOX_T_DOWN +
            BOX_HORIZONTAL * col_widths[2] + BOX_TOP_RIGHT
        )

        # Header
        lines.append(
            BOX_VERTICAL + " Layer".ljust(col_widths[0] - 1) +
            BOX_VERTICAL + " Status".ljust(col_widths[1] - 1) +
            BOX_VERTICAL + " Notes".ljust(col_widths[2] - 1) + BOX_VERTICAL
        )

        # Header separator
        lines.append(
            BOX_T_RIGHT +
            BOX_HORIZONTAL * col_widths[0] + BOX_CROSS +
            BOX_HORIZONTAL * col_widths[1] + BOX_CROSS +
            BOX_HORIZONTAL * col_widths[2] + BOX_T_LEFT
        )

        # Data rows
        for layer in layers:
            status = layer["status"]
            if "PASS" in status:
                status = colorize(status, ANSI_GREEN)
            elif "FAIL" in status:
                status = colorize(status, ANSI_RED)

            lines.append(
                BOX_VERTICAL + f" {layer['name'][:col_widths[0]-2]}".ljust(col_widths[0] - 1) +
                BOX_VERTICAL + f" {status}".ljust(col_widths[1] - 1 + (len(status) - len(layer["status"]))) +
                BOX_VERTICAL + f" {layer['notes'][:col_widths[2]-2]}".ljust(col_widths[2] - 1) + BOX_VERTICAL
            )

        # Bottom border
        lines.append(
            BOX_BOTTOM_LEFT +
            BOX_HORIZONTAL * col_widths[0] + BOX_T_UP +
            BOX_HORIZONTAL * col_widths[1] + BOX_T_UP +
            BOX_HORIZONTAL * col_widths[2] + BOX_BOTTOM_RIGHT
        )

        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """Generate JSON representation of dashboard data.

        Returns:
            Dictionary with all dashboard data for CI integration.
        """
        data = self.get_data()
        return {
            "generated_at": data.generated_at.isoformat(),
            "strategies_validated": data.strategies_validated,
            "total_strategies": data.total_strategies,
            "strategies": data.strategies,
            "layers_covered": data.layers_covered,
            "total_layers": data.total_layers,
            "layers": data.layers,
            "findings": {
                "total": data.total_findings,
                "bug_count": data.bug_count,
                "bug_fixed": data.bug_fixed_count,
                "design_count": data.design_count,
                "regression_tests": data.regression_tests,
            },
            "confidence": data.confidence,
            "confidence_label": self._get_confidence_label(data.confidence),
            "healthy": self.is_healthy(),
        }

    def is_healthy(self) -> bool:
        """Check if validation state is healthy for CI.

        A healthy state requires:
        - All strategies validated
        - No open (unresolved) bugs

        Returns:
            True if healthy, False otherwise.
        """
        data = self.get_data()
        all_validated = data.strategies_validated == data.total_strategies
        no_open_bugs = data.bug_count == data.bug_fixed_count
        return all_validated and no_open_bugs

    def get_exit_code(self) -> int:
        """Get appropriate exit code for CI.

        Returns:
            0 if healthy, 1 if unhealthy.
        """
        return 0 if self.is_healthy() else 1

    def _load_completed_sessions(self) -> list[Any]:
        """Load all sessions that have completed comparison or later."""
        from rustybt.validation.models import SessionStage

        all_sessions = self.session_manager.list_sessions()
        completed = []
        for s in all_sessions:
            if s.stage in (
                SessionStage.COMPARED,
                SessionStage.INVESTIGATING,
                SessionStage.COMPLETED,
            ) or s.status == "COMPLETED":
                completed.append(s)
        return completed


# Story 7.5: Documentation Generator

class DocumentationGenerator:
    """Generate user-facing documentation for validation findings.

    DocumentationGenerator creates markdown documentation files for DESIGN
    differences and bug fixes discovered during validation.

    Attributes:
        session_manager: SessionManager for loading sessions
        output_dir: Directory to save generated documentation

    Example:
        >>> from rustybt.validation.reporting import DocumentationGenerator
        >>> from rustybt.validation.session import SessionManager
        >>>
        >>> sm = SessionManager()
        >>> generator = DocumentationGenerator(sm)
        >>> generator.generate_all()
    """

    MANUAL_SECTION_START = "<!-- MANUAL SECTION START -->"
    MANUAL_SECTION_END = "<!-- MANUAL SECTION END -->"

    def __init__(
        self,
        session_manager: "SessionManager | None" = None,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize DocumentationGenerator.

        Args:
            session_manager: Optional SessionManager. If None, creates a new one.
            output_dir: Output directory for docs. Defaults to docs/validation/
        """
        if session_manager is None:
            from rustybt.validation.session import SessionManager
            session_manager = SessionManager()
        self.session_manager = session_manager
        self.output_dir = output_dir or Path("docs/validation")
        self.generated_at = datetime.now()

    def generate_design_differences(self) -> str:
        """Generate design-differences.md content.

        Groups DESIGN findings by layer and formats them in user-friendly language.

        Returns:
            Markdown content for design differences documentation.
        """
        lines: list[str] = []
        findings_by_layer = self._get_design_findings_by_layer()

        # Header
        lines.append("# rustybt vs Backtrader: Design Differences")
        lines.append("")
        lines.append("This document describes intentional design differences between rustybt")
        lines.append("and Backtrader discovered during validation.")
        lines.append("")
        lines.append(f"*Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M')}*")
        lines.append("")

        # Layer sections
        layer_titles = {
            "data": "Data Handling",
            "signals": "Signal Computation",
            "orders": "Order Execution",
            "broker": "Broker Transactions",
            "portfolio": "Portfolio Management",
        }

        for layer in ["data", "signals", "orders", "broker", "portfolio"]:
            findings = findings_by_layer.get(layer, [])
            if not findings:
                continue

            lines.append(f"# {layer_titles[layer]}")
            lines.append("")

            for finding in findings:
                lines.extend(self._format_design_finding(finding))
                lines.append("")

        # Add manual section placeholder
        lines.append(self.MANUAL_SECTION_START)
        lines.append("")
        lines.append("<!-- Add any manual notes here - they will be preserved on regeneration -->")
        lines.append("")
        lines.append(self.MANUAL_SECTION_END)

        return "\n".join(lines)

    def generate_bug_fixes(self) -> str:
        """Generate bug-fixes.md content.

        Lists all resolved BUG findings with regression test references.

        Returns:
            Markdown content for bug fixes documentation.
        """
        lines: list[str] = []
        bug_findings = self._get_bug_findings()

        # Header
        lines.append("# rustybt Bug Fixes")
        lines.append("")
        lines.append("This document lists bugs identified during validation and their fixes.")
        lines.append("")
        lines.append(f"*Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M')}*")
        lines.append("")

        resolved = [f for f in bug_findings if f.resolved]
        open_bugs = [f for f in bug_findings if not f.resolved]

        if not bug_findings:
            lines.append("## Status")
            lines.append("")
            lines.append("No bugs identified during validation. All discrepancies have been")
            lines.append("classified as intentional DESIGN differences.")
            lines.append("")
        else:
            # Resolved bugs
            if resolved:
                lines.append("## Resolved Bugs")
                lines.append("")
                for finding in resolved:
                    lines.extend(self._format_bug_finding(finding))
                    lines.append("")

            # Open bugs
            if open_bugs:
                lines.append("## Open Bugs")
                lines.append("")
                for finding in open_bugs:
                    lines.extend(self._format_bug_finding(finding))
                    lines.append("")

        return "\n".join(lines)

    def _format_design_finding(self, finding: Any) -> list[str]:
        """Format a DESIGN finding for documentation."""
        lines: list[str] = []

        # Title from description
        title = finding.description[:60]
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"**Finding:** {finding.id}")
        lines.append("")

        # Difference explanation
        lines.append("**Difference:**")
        if finding.rustybt_value and finding.backtrader_value:
            lines.append(f"- rustybt: {finding.rustybt_value}")
            lines.append(f"- Backtrader: {finding.backtrader_value}")
        elif finding.design_rationale:
            lines.append(finding.design_rationale)
        else:
            lines.append(finding.description)
        lines.append("")

        # Impact
        lines.append("**Impact:**")
        if finding.user_impact:
            lines.append(finding.user_impact)
        else:
            lines.append("Minor numerical differences that do not affect trading signal timing.")
        lines.append("")

        # Recommendation
        lines.append("**Recommendation:**")
        if finding.suggested_fix:
            lines.append(finding.suggested_fix)
        elif finding.design_choice == "either_valid":
            lines.append("No action needed. Both implementations are industry-standard approaches.")
        elif finding.design_choice == "rustybt_preferred":
            lines.append("rustybt's approach is recommended. No action needed.")
        else:
            lines.append("No action needed. Documented for user awareness.")

        lines.append("")
        lines.append("---")

        return lines

    def _format_bug_finding(self, finding: Any) -> list[str]:
        """Format a BUG finding for documentation."""
        lines: list[str] = []

        lines.append(f"### {finding.id}: {finding.description[:50]}")
        lines.append("")
        lines.append(f"**Layer:** {finding.layer}")
        lines.append(f"**Severity:** {finding.severity or 'Not specified'}")
        lines.append(f"**Status:** {'Resolved' if finding.resolved else 'Open'}")
        lines.append("")

        if finding.resolved:
            if finding.resolved_at:
                lines.append(f"**Resolved:** {finding.resolved_at.strftime('%Y-%m-%d')}")
            if finding.regression_test:
                lines.append(f"**Regression Test:** `{finding.regression_test}`")
        else:
            if finding.suggested_fix:
                lines.append(f"**Suggested Fix:** {finding.suggested_fix}")
            if finding.affected_components:
                lines.append(f"**Affected Files:** {', '.join(finding.affected_components)}")

        return lines

    def _get_design_findings_by_layer(self) -> dict[str, list[Any]]:
        """Get all DESIGN findings grouped by layer."""
        from rustybt.validation.models import SessionStage

        all_sessions = self.session_manager.list_sessions()
        findings_by_layer: dict[str, list[Any]] = {}

        for session in all_sessions:
            if session.stage in (SessionStage.COMPARED, SessionStage.INVESTIGATING, SessionStage.COMPLETED):
                for finding in session.findings:
                    if finding.classification == "DESIGN":
                        layer = finding.layer
                        if layer not in findings_by_layer:
                            findings_by_layer[layer] = []
                        # Avoid duplicates by ID
                        if not any(f.id == finding.id for f in findings_by_layer[layer]):
                            findings_by_layer[layer].append(finding)

        return findings_by_layer

    def _get_bug_findings(self) -> list[Any]:
        """Get all BUG findings."""
        from rustybt.validation.models import SessionStage

        all_sessions = self.session_manager.list_sessions()
        bugs: list[Any] = []
        seen_ids: set[str] = set()

        for session in all_sessions:
            if session.stage in (SessionStage.COMPARED, SessionStage.INVESTIGATING, SessionStage.COMPLETED):
                for finding in session.findings:
                    if finding.classification == "BUG" and finding.id not in seen_ids:
                        bugs.append(finding)
                        seen_ids.add(finding.id)

        return bugs

    def save_design_differences(self) -> Path:
        """Generate and save design-differences.md.

        Preserves manual sections if the file already exists.

        Returns:
            Path to saved file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / "design-differences.md"

        # Preserve manual sections if file exists
        manual_content = ""
        if output_path.exists():
            existing = output_path.read_text()
            start_idx = existing.find(self.MANUAL_SECTION_START)
            end_idx = existing.find(self.MANUAL_SECTION_END)
            if start_idx != -1 and end_idx != -1:
                manual_content = existing[start_idx:end_idx + len(self.MANUAL_SECTION_END)]

        content = self.generate_design_differences()

        # Replace placeholder with preserved manual content
        if manual_content:
            placeholder = (
                self.MANUAL_SECTION_START + "\n\n"
                "<!-- Add any manual notes here - they will be preserved on regeneration -->\n\n"
                + self.MANUAL_SECTION_END
            )
            content = content.replace(placeholder, manual_content)

        output_path.write_text(content)
        return output_path

    def save_bug_fixes(self) -> Path:
        """Generate and save bug-fixes.md.

        Returns:
            Path to saved file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / "bug-fixes.md"
        content = self.generate_bug_fixes()
        output_path.write_text(content)
        return output_path

    def generate_all(self) -> tuple[Path, Path]:
        """Generate both documentation files.

        Returns:
            Tuple of (design_differences_path, bug_fixes_path)
        """
        design_path = self.save_design_differences()
        bugs_path = self.save_bug_fixes()
        return design_path, bugs_path


# Story 7.6: Validation Progress and Completion Tracking

@dataclass
class ValidationProgress:
    """Validation completion progress tracking.

    Tracks completion percentage across strategies, layers, and findings.

    Attributes:
        strategy_completion: Ratio of validated strategies (0.0 to 1.0)
        layer_completion: Ratio of completed layer validations (0.0 to 1.0)
        finding_resolution: Ratio of resolved findings (0.0 to 1.0)
        overall: Weighted overall completion percentage
        completed_strategies: List of completed strategy names
        incomplete_strategies: List of incomplete strategy names
        missing_layers: Dict mapping strategy to missing layers
    """

    strategy_completion: float
    layer_completion: float
    finding_resolution: float
    overall: float
    completed_strategies: list[str] = field(default_factory=list)
    incomplete_strategies: list[str] = field(default_factory=list)
    missing_layers: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def calculate(
        cls,
        validated_strategies: int = 0,
        total_strategies: int = 4,
        completed_layers: int = 0,
        total_layers: int = 20,
        resolved_findings: int = 0,
        total_findings: int = 0,
        completed_strategy_names: list[str] | None = None,
        incomplete_strategy_names: list[str] | None = None,
        missing_layer_map: dict[str, list[str]] | None = None,
    ) -> "ValidationProgress":
        """Calculate progress from raw counts.

        Args:
            validated_strategies: Number of fully validated strategies
            total_strategies: Total expected strategies (default: 4)
            completed_layers: Number of completed layer validations
            total_layers: Total layer validations (default: 20 = 4 strategies × 5 layers)
            resolved_findings: Number of resolved findings (BUG fixed or DESIGN documented)
            total_findings: Total findings count
            completed_strategy_names: List of validated strategy names
            incomplete_strategy_names: List of incomplete strategy names
            missing_layer_map: Dict mapping strategy to missing layer names

        Returns:
            ValidationProgress with calculated percentages
        """
        strategy_completion = validated_strategies / total_strategies if total_strategies > 0 else 0
        layer_completion = completed_layers / total_layers if total_layers > 0 else 0
        finding_resolution = resolved_findings / total_findings if total_findings > 0 else 1.0

        # Weighted average: Strategy 40%, Layer 30%, Finding 30%
        overall = (strategy_completion * 0.4) + (layer_completion * 0.3) + (finding_resolution * 0.3)

        return cls(
            strategy_completion=strategy_completion,
            layer_completion=layer_completion,
            finding_resolution=finding_resolution,
            overall=overall,
            completed_strategies=completed_strategy_names or [],
            incomplete_strategies=incomplete_strategy_names or [],
            missing_layers=missing_layer_map or {},
        )

    def calculate_overall(self) -> None:
        """Recalculate overall from current completion values."""
        self.overall = (
            (self.strategy_completion * 0.4) +
            (self.layer_completion * 0.3) +
            (self.finding_resolution * 0.3)
        )


class CompletionTracker:
    """Track validation completion and suggest next steps.

    CompletionTracker analyzes the current validation state and provides
    progress information and actionable suggestions.

    Attributes:
        session_manager: SessionManager for loading sessions

    Example:
        >>> from rustybt.validation.reporting import CompletionTracker
        >>> tracker = CompletionTracker()
        >>> progress = tracker.get_progress()
        >>> print(f"Overall: {progress.overall * 100:.1f}%")
        >>> for step in tracker.get_next_steps():
        ...     print(f"  - {step}")
    """

    EXPECTED_STRATEGIES = ["sma_crossover", "mean_reversion", "momentum", "multi_factor"]
    ALL_LAYERS = ["data", "signals", "orders", "broker", "portfolio"]

    def __init__(self, session_manager: "SessionManager | None" = None) -> None:
        """Initialize CompletionTracker.

        Args:
            session_manager: Optional SessionManager. If None, creates a new one.
        """
        if session_manager is None:
            from rustybt.validation.session import SessionManager
            session_manager = SessionManager()
        self.session_manager = session_manager

    def get_progress(self) -> ValidationProgress:
        """Calculate current validation progress.

        Returns:
            ValidationProgress with completion percentages and details.
        """
        from rustybt.validation.models import SessionStage

        sessions = self.session_manager.list_sessions()

        # Get best session per strategy
        strategy_sessions: dict[str, Any] = {}
        for session in sessions:
            if session.stage in (SessionStage.COMPARED, SessionStage.INVESTIGATING, SessionStage.COMPLETED):
                name = session.strategy_name
                if name not in strategy_sessions or session.created_at > strategy_sessions[name].created_at:
                    strategy_sessions[name] = session

        # Calculate strategy completion
        completed_strategies = []
        incomplete_strategies = []
        missing_layers: dict[str, list[str]] = {}

        for strategy in self.EXPECTED_STRATEGIES:
            session = strategy_sessions.get(strategy)
            if session and set(self.ALL_LAYERS) <= set(session.layers_completed or []):
                completed_strategies.append(strategy)
            else:
                incomplete_strategies.append(strategy)
                if session:
                    missing = [l for l in self.ALL_LAYERS if l not in (session.layers_completed or [])]
                    if missing:
                        missing_layers[strategy] = missing
                else:
                    missing_layers[strategy] = self.ALL_LAYERS.copy()

        # Count total completed layers
        total_completed_layers = 0
        for session in strategy_sessions.values():
            total_completed_layers += len(session.layers_completed or [])

        # Count findings
        all_findings = []
        for session in strategy_sessions.values():
            all_findings.extend(session.findings)

        resolved = sum(
            1 for f in all_findings
            if (f.classification == "BUG" and f.resolved) or f.classification == "DESIGN"
        )

        return ValidationProgress.calculate(
            validated_strategies=len(completed_strategies),
            total_strategies=len(self.EXPECTED_STRATEGIES),
            completed_layers=total_completed_layers,
            total_layers=len(self.EXPECTED_STRATEGIES) * len(self.ALL_LAYERS),
            resolved_findings=resolved,
            total_findings=len(all_findings),
            completed_strategy_names=completed_strategies,
            incomplete_strategy_names=incomplete_strategies,
            missing_layer_map=missing_layers,
        )

    def get_incomplete_strategies(self) -> list[str]:
        """Get list of incomplete strategy names.

        Returns:
            List of strategy names that haven't completed validation.
        """
        progress = self.get_progress()
        return progress.incomplete_strategies

    def get_next_steps(self) -> list[str]:
        """Generate actionable next step suggestions.

        Returns:
            List of suggestion strings based on current state.
        """
        progress = self.get_progress()
        suggestions: list[str] = []

        # Suggest completing incomplete strategies
        for strategy in progress.incomplete_strategies:
            missing = progress.missing_layers.get(strategy, [])
            if missing:
                layers_str = ", ".join(missing)
                suggestions.append(f"Complete {strategy} validation ({len(missing)} layers remaining: {layers_str})")
            else:
                suggestions.append(f"Start validation for {strategy}")

        # If all strategies complete, suggest final report
        if not progress.incomplete_strategies:
            suggestions.append("Generate final validation report")

        return suggestions

    def render(self) -> str:
        """Generate progress display.

        Returns:
            Formatted progress string with bars and details.
        """
        progress = self.get_progress()
        lines: list[str] = []

        lines.append("Validation Progress")
        lines.append("═══════════════════")
        lines.append("")

        # Strategy progress
        strategy_pct = progress.strategy_completion * 100
        strategy_bar = render_progress_bar(strategy_pct)
        lines.append(f"Strategies: {strategy_bar} {len(progress.completed_strategies)}/{len(self.EXPECTED_STRATEGIES)} ({int(strategy_pct)}%)")

        for strategy in progress.completed_strategies:
            lines.append(f"  ✓ {STRATEGY_DISPLAY_NAMES.get(strategy, strategy)}")
        for strategy in progress.incomplete_strategies:
            missing = progress.missing_layers.get(strategy, [])
            if missing:
                lines.append(f"  ○ {STRATEGY_DISPLAY_NAMES.get(strategy, strategy)} (missing: {', '.join(missing)})")
            else:
                lines.append(f"  ○ {STRATEGY_DISPLAY_NAMES.get(strategy, strategy)} (not started)")

        lines.append("")

        # Layer progress
        layer_pct = progress.layer_completion * 100
        layer_bar = render_progress_bar(layer_pct)
        total_layers = len(self.EXPECTED_STRATEGIES) * len(self.ALL_LAYERS)
        completed_layers = int(progress.layer_completion * total_layers)
        lines.append(f"Layers: {layer_bar} {completed_layers}/{total_layers} ({int(layer_pct)}%)")

        # Show which strategies are missing which layers
        for strategy, missing in progress.missing_layers.items():
            if missing:
                display_name = STRATEGY_DISPLAY_NAMES.get(strategy, strategy)
                lines.append(f"  {display_name} missing: {', '.join(missing)}")

        lines.append("")

        # Finding progress
        finding_pct = progress.finding_resolution * 100
        finding_bar = render_progress_bar(finding_pct)
        lines.append(f"Findings: {finding_bar} ({int(finding_pct)}%)")
        if finding_pct >= 100:
            lines.append("  All findings classified and resolved")

        lines.append("")

        # Overall
        overall_pct = progress.overall * 100
        overall_bar = render_progress_bar(overall_pct)
        lines.append(f"Overall: {overall_bar} {int(overall_pct)}%")

        lines.append("")

        # Next steps
        next_steps = self.get_next_steps()
        if next_steps:
            lines.append("Next Steps:")
            for i, step in enumerate(next_steps, 1):
                lines.append(f"  {i}. {step}")

        return "\n".join(lines)


# Story 7.7: Next Actions Recommender

@dataclass
class Recommendation:
    """Prioritized action recommendation.

    Attributes:
        priority: Priority level (1 = highest)
        action: Short action description
        details: Detailed description
        command: CLI command to execute
    """

    priority: int
    action: str
    details: str
    command: str

    def get_priority_label(self) -> str:
        """Get priority label (HIGH, MEDIUM, LOW)."""
        if self.priority == 1:
            return "HIGH"
        elif self.priority == 2:
            return "MEDIUM"
        else:
            return "LOW"


class NextActionsRecommender:
    """Recommend next validation actions based on current state.

    Analyzes validation state and provides prioritized recommendations
    with executable CLI commands.

    Priority levels:
    1. Open bugs (highest)
    2. Unclassified findings
    3. Incomplete strategies
    4. Missing documentation

    Example:
        >>> from rustybt.validation.reporting import NextActionsRecommender
        >>> recommender = NextActionsRecommender()
        >>> for rec in recommender.recommend():
        ...     print(f"[{rec.get_priority_label()}] {rec.action}")
        ...     print(f"  Command: {rec.command}")
    """

    def __init__(self, session_manager: "SessionManager | None" = None) -> None:
        """Initialize NextActionsRecommender.

        Args:
            session_manager: Optional SessionManager. If None, creates a new one.
        """
        if session_manager is None:
            from rustybt.validation.session import SessionManager
            session_manager = SessionManager()
        self.session_manager = session_manager

    def recommend(self) -> list[Recommendation]:
        """Get prioritized recommendations.

        Returns:
            List of Recommendation objects sorted by priority.
        """
        recommendations: list[Recommendation] = []

        # Priority 1: Open bugs
        open_bugs = self._get_open_bugs()
        if open_bugs:
            recommendations.append(Recommendation(
                priority=1,
                action="Fix open bugs",
                details=f"{len(open_bugs)} BUG findings require fixes",
                command="rustybt-validate investigate --bugs",
            ))

        # Priority 2: Unclassified findings
        unclassified = self._get_unclassified_findings()
        if unclassified:
            recommendations.append(Recommendation(
                priority=2,
                action="Classify findings",
                details=f"{len(unclassified)} findings need classification",
                command="rustybt-validate investigate --unclassified",
            ))

        # Priority 3: Incomplete strategies
        incomplete = self._get_incomplete_strategies()
        if incomplete:
            # Get session ID for first incomplete
            session_info = self._get_strategy_session_info(incomplete[0])
            if session_info:
                recommendations.append(Recommendation(
                    priority=3,
                    action="Complete strategy validation",
                    details=f"{incomplete[0]} has incomplete layers",
                    command=f"rustybt-validate run {session_info['session_id']}",
                ))
            else:
                recommendations.append(Recommendation(
                    priority=3,
                    action="Start strategy validation",
                    details=f"{incomplete[0]} not yet started",
                    command=f"rustybt-validate session create --strategy {incomplete[0]} --data fixtures/test.parquet",
                ))

        # Priority 4: Documentation needs refresh
        if self._needs_documentation_update():
            recommendations.append(Recommendation(
                priority=4,
                action="Update documentation",
                details="DESIGN differences need documentation refresh",
                command="rustybt-validate docs generate",
            ))

        # If everything is done, suggest final report
        if not recommendations:
            recommendations.append(Recommendation(
                priority=4,
                action="Generate final report",
                details="All validation complete. Generate final validation report.",
                command="rustybt-validate status --format json",
            ))

        return sorted(recommendations, key=lambda r: r.priority)

    def _get_open_bugs(self) -> list[Any]:
        """Get all open (unresolved) BUG findings."""
        from rustybt.validation.models import SessionStage

        sessions = self.session_manager.list_sessions()
        open_bugs = []

        for session in sessions:
            if session.stage in (SessionStage.COMPARED, SessionStage.INVESTIGATING, SessionStage.COMPLETED):
                for finding in session.findings:
                    if finding.classification == "BUG" and not finding.resolved:
                        open_bugs.append(finding)

        return open_bugs

    def _get_unclassified_findings(self) -> list[Any]:
        """Get all unclassified findings."""
        from rustybt.validation.models import SessionStage

        sessions = self.session_manager.list_sessions()
        unclassified = []

        for session in sessions:
            if session.stage in (SessionStage.COMPARED, SessionStage.INVESTIGATING):
                for finding in session.findings:
                    if finding.classification is None:
                        unclassified.append(finding)

        return unclassified

    def _get_incomplete_strategies(self) -> list[str]:
        """Get list of incomplete strategy names."""
        tracker = CompletionTracker(self.session_manager)
        return tracker.get_incomplete_strategies()

    def _get_strategy_session_info(self, strategy: str) -> dict[str, str] | None:
        """Get session info for a strategy."""
        sessions = self.session_manager.find_sessions(strategy=strategy)
        if sessions:
            return {"session_id": sessions[0].id}
        return None

    def _needs_documentation_update(self) -> bool:
        """Check if documentation needs to be regenerated."""
        from rustybt.validation.models import SessionStage

        # Check for DESIGN findings that might not be documented
        sessions = self.session_manager.list_sessions()

        for session in sessions:
            if session.stage in (SessionStage.COMPARED, SessionStage.INVESTIGATING, SessionStage.COMPLETED):
                for finding in session.findings:
                    if finding.classification == "DESIGN" and not finding.documentation_ref:
                        return True

        return False

    def render(self) -> str:
        """Generate recommendations display.

        Returns:
            Formatted recommendations string.
        """
        recommendations = self.recommend()
        lines: list[str] = []

        lines.append("Recommended Next Actions")
        lines.append("════════════════════════")
        lines.append("")

        if not recommendations:
            lines.append("No recommendations - validation is complete!")
        else:
            for i, rec in enumerate(recommendations, 1):
                label = rec.get_priority_label()
                if label == "HIGH":
                    label = colorize(f"[{label}]", ANSI_RED)
                elif label == "MEDIUM":
                    label = colorize(f"[{label}]", ANSI_YELLOW)
                else:
                    label = colorize(f"[{label}]", ANSI_GREEN)

                lines.append(f"{i}. {label} {rec.action} ({rec.details})")
                lines.append(f"   Command: {rec.command}")
                lines.append("")

        return "\n".join(lines)
