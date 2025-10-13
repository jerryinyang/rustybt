#!/usr/bin/env python3
"""Check module-specific coverage thresholds.

This script enforces different coverage requirements for different modules:
- Core modules: ≥90%
- Financial modules: ≥95%

Exit codes:
    0: All modules meet coverage requirements
    1: One or more modules below threshold
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

# Module patterns and their required coverage thresholds
MODULE_THRESHOLDS = {
    "finance": 95.0,  # Financial modules require 95%
    "core": 90.0,  # Core modules require 90%
}

# Default threshold for modules not matching specific patterns
DEFAULT_THRESHOLD = 90.0


def parse_coverage_xml(xml_path: Path) -> Dict[str, float]:
    """Parse coverage XML and extract per-module coverage percentages.

    Args:
        xml_path: Path to coverage.xml file

    Returns:
        Dictionary mapping module_name -> coverage_percentage
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    module_coverage = {}

    # Find all package elements
    for package in root.findall(".//package"):
        package_name = package.get("name", "")

        # Calculate coverage for this package
        lines_valid = int(package.get("line-rate", 0)) if package.get("line-rate") else 0
        branches_valid = int(package.get("branch-rate", 0)) if package.get("branch-rate") else 0

        # Use line-rate as primary coverage metric (percentage 0-1)
        line_rate = float(package.get("line-rate", 0))
        coverage_pct = line_rate * 100

        if package_name:
            module_coverage[package_name] = coverage_pct

    return module_coverage


def get_threshold_for_module(module_name: str) -> float:
    """Get the required coverage threshold for a module.

    Args:
        module_name: Module name (e.g., 'rustybt.finance', 'rustybt.data')

    Returns:
        Required coverage percentage
    """
    # Check if module matches any specific pattern
    for pattern, threshold in MODULE_THRESHOLDS.items():
        if pattern in module_name:
            return threshold

    return DEFAULT_THRESHOLD


def check_thresholds(
    module_coverage: Dict[str, float], verbose: bool = False
) -> List[Tuple[str, float, float]]:
    """Check if all modules meet their coverage thresholds.

    Args:
        module_coverage: Dictionary mapping module_name -> coverage_percentage
        verbose: Show all modules, not just violations

    Returns:
        List of (module_name, actual_coverage, required_threshold) tuples for violations
    """
    violations = []

    for module_name, actual_coverage in sorted(module_coverage.items()):
        required_threshold = get_threshold_for_module(module_name)

        if verbose:
            status = "✓" if actual_coverage >= required_threshold else "✗"
            print(
                f"  {status} {module_name}: {actual_coverage:.2f}% "
                f"(threshold: {required_threshold:.0f}%)"
            )

        if actual_coverage < required_threshold:
            violations.append((module_name, actual_coverage, required_threshold))

    return violations


def main():
    parser = argparse.ArgumentParser(description="Check module-specific coverage thresholds")
    parser.add_argument(
        "--coverage-file",
        default="coverage.xml",
        help="Path to coverage XML file (default: coverage.xml)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show all modules, not just violations"
    )

    args = parser.parse_args()

    coverage_file = Path(args.coverage_file)
    if not coverage_file.exists():
        print(f"Error: Coverage file not found: {coverage_file}", file=sys.stderr)
        sys.exit(1)

    print("Checking module-specific coverage thresholds...")
    print(f"Requirements: finance ≥95%, core ≥90%, others ≥{DEFAULT_THRESHOLD:.0f}%")
    print()

    try:
        module_coverage = parse_coverage_xml(coverage_file)
    except Exception as e:
        print(f"Error: Failed to parse coverage file: {e}", file=sys.stderr)
        sys.exit(1)

    if not module_coverage:
        print("Warning: No coverage data found in XML file", file=sys.stderr)
        sys.exit(0)

    violations = check_thresholds(module_coverage, verbose=args.verbose)

    if violations:
        print(f"\n❌ Found {len(violations)} coverage violations:\n")
        for module_name, actual, required in sorted(violations, key=lambda x: x[1] - x[2]):
            deficit = required - actual
            print(f"  {module_name}")
            print(f"    Actual: {actual:.2f}%")
            print(f"    Required: {required:.0f}%")
            print(f"    Deficit: {deficit:.2f}%")
            print()

        print("Action required:")
        print("1. Add tests to cover untested code paths")
        print("2. Review if code is testable (refactor if needed)")
        print("3. Ensure critical financial modules have ≥95% coverage")
        sys.exit(1)
    else:
        print(f"✅ All modules meet coverage thresholds")
        print(
            f"   Checked {len(module_coverage)} modules: finance ≥95%, others ≥{DEFAULT_THRESHOLD:.0f}%"
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
