"""Health check utilities for data integrity validation.

This module provides functions to validate file integrity, data quality, and
system health before processing. Health checks help detect corrupted data,
missing files, or schema violations that would cause failures during validation.

Example:
    >>> from pathlib import Path
    >>> from rustybt.validation.health_checks import validate_log_integrity
    >>>
    >>> result = validate_log_integrity(Path("logs/rustybt.jsonl"))
    >>> if not result.passed:
    ...     print(f"Integrity check failed: {result.diagnostics}")
    >>> else:
    ...     print(f"Log file valid: {result.diagnostics['row_count']} rows")
"""

import json
from pathlib import Path
from typing import Any

from rustybt.validation.models import HealthCheckResult


def validate_log_integrity(log_path: Path) -> HealthCheckResult:
    """Validate JSONL log file integrity.

    Checks for common issues with log files including:
    - File existence and readability
    - Valid JSONL format (each line is valid JSON)
    - Required fields present in each record
    - No truncated or malformed lines
    - Non-empty file (at least 1 record)

    Args:
        log_path: Path to JSONL log file to validate

    Returns:
        HealthCheckResult with passed status and diagnostic information

    Example:
        >>> result = validate_log_integrity(Path("logs/rustybt.jsonl"))
        >>> result.passed
        True
        >>> result.diagnostics
        {
            'file_exists': True,
            'file_readable': True,
            'valid_jsonl': True,
            'row_count': 1542,
            'truncated_lines': [],
            'missing_fields': []
        }
    """
    diagnostics: dict[str, Any] = {
        "file_exists": False,
        "file_readable": False,
        "valid_jsonl": True,  # Assume valid until proven otherwise
        "row_count": 0,
        "truncated_lines": [],
        "missing_fields": [],
    }

    # Check 1: File exists
    if not log_path.exists():
        return HealthCheckResult(passed=False, diagnostics=diagnostics)

    diagnostics["file_exists"] = True

    # Check 2: File is a file (not directory)
    if not log_path.is_file():
        diagnostics["error"] = "Path exists but is not a file"
        return HealthCheckResult(passed=False, diagnostics=diagnostics)

    # Check 3: File is readable
    try:
        with open(log_path, encoding="utf-8") as f:
            # Try reading first byte to verify readability
            f.read(1)
            diagnostics["file_readable"] = True
    except (OSError, PermissionError) as e:
        diagnostics["error"] = f"File not readable: {e}"
        return HealthCheckResult(passed=False, diagnostics=diagnostics)

    # Check 4: Parse JSONL and validate schema
    required_fields = {"layer", "event", "timestamp"}
    truncated_lines: list[int] = []
    missing_fields_set: set[str] = set()
    row_count = 0

    try:
        with open(log_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                # Skip empty lines
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                    row_count += 1

                    # Check required fields
                    record_fields = set(record.keys())
                    missing = required_fields - record_fields
                    if missing:
                        missing_fields_set.update(missing)

                except json.JSONDecodeError:
                    diagnostics["valid_jsonl"] = False
                    truncated_lines.append(line_num)

    except OSError as e:
        diagnostics["error"] = f"Error reading file: {e}"
        return HealthCheckResult(passed=False, diagnostics=diagnostics)

    diagnostics["row_count"] = row_count
    diagnostics["truncated_lines"] = truncated_lines
    diagnostics["missing_fields"] = sorted(missing_fields_set)

    # Check 5: Non-empty file
    if row_count == 0:
        diagnostics["error"] = "Log file is empty (0 records)"
        return HealthCheckResult(passed=False, diagnostics=diagnostics)

    # Determine overall pass/fail
    passed = (
        diagnostics["file_exists"]
        and diagnostics["file_readable"]
        and diagnostics["valid_jsonl"]
        and row_count > 0
        and len(truncated_lines) == 0
        and len(missing_fields_set) == 0
    )

    return HealthCheckResult(passed=passed, diagnostics=diagnostics)


# Usage example for future integration (Epic 2 and Epic 4)
"""
Future usage in comparison code:

from rustybt.validation.health_checks import validate_log_integrity
from rustybt.validation.comparators import compare_layer

def compare_logs(rustybt_log: Path, backtrader_log: Path, layer: str):
    # Health check before comparison
    rb_health = validate_log_integrity(rustybt_log)
    if not rb_health.passed:
        raise ValidationError(
            f"rustybt log failed health check: {rb_health.diagnostics}"
        )

    bt_health = validate_log_integrity(backtrader_log)
    if not bt_health.passed:
        raise ValidationError(
            f"Backtrader log failed health check: {bt_health.diagnostics}"
        )

    # Proceed with comparison only if both logs are healthy
    return compare_layer(rustybt_log, backtrader_log, layer)
"""
