#!/usr/bin/env python
"""
Fix incorrect and fabricated API references in documentation.
Created for Story 10.X1 - Complete remediation of fabricated APIs.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Load the verification report
with open("scripts/api_verification_report.json", "r") as f:
    report = json.load(f)

# Define corrections for common import path errors
IMPORT_CORRECTIONS = {
    # TradingAlgorithm is in algorithm module, not root
    "from rustybt import TradingAlgorithm": "from rustybt.algorithm import TradingAlgorithm",
    # run_algorithm should be imported from api
    "from rustybt import run_algorithm": "from rustybt.api import run_algorithm",
    # symbol should be imported correctly
    "from rustybt.api import symbol": "from rustybt.api import symbol",  # This might be correct, need to verify
    # Finance module corrections
    "from rustybt.finance import PerShareCommission": "from rustybt.finance.commission import PerShare",
    "from rustybt.finance import FixedSlippage": "from rustybt.finance.slippage import FixedSlippage",
    # Optimization module corrections
    "from rustybt.optimization import MonteCarloTester": "from rustybt.optimization import MonteCarloSimulator",
    # Data module corrections
    "from rustybt.data.polars import PolarsDataPortal": "from rustybt.data.data_portal import DataPortal",
}

# Classes/functions that should be removed entirely (don't exist)
FABRICATED_APIS_TO_REMOVE = [
    "RollingAnalytics",  # Doesn't exist
    "BundleMetadata",  # Doesn't exist
    "CachedDataSource",
    "TTLFreshnessPolicy",
    "MarketCloseFreshnessPolicy",
    "HybridFreshnessPolicy",  # Cache policies don't exist
    "YFinanceDataSource",  # Should be YFinanceAdapter
    "CircuitBreaker",
    "CircuitBreakerConfig",  # Don't exist yet
    "StateManager",  # Doesn't exist
    "BorrowCost",
    "MarginInterest",  # Don't exist
    "MakerTakerFee",
    "PerAssetCommission",
    "PerDollarTiered",
    "PerShareTiered",  # Don't exist
    "PerAssetSlippage",  # Doesn't exist
    "RiskControl",  # Doesn't exist
    "MetricCalculator",  # Doesn't exist
    "BacktestRunner",
    "MockDataFeed",  # Testing utilities don't exist
    "detect_mocks",
    "detect_hardcoded_values",
    "generate_ohlcv",
    "generate_correlated_assets",
    "generate_regime_data",
    "latin_hypercube_sample",
    "sobol_sample",  # Sampling methods don't exist
]


def fix_import_in_file(file_path: Path, old_import: str, new_import: str) -> bool:
    """Fix a specific import in a file."""
    try:
        with open(file_path, "r") as f:
            content = f.read()

        if old_import in content:
            content = content.replace(old_import, new_import)
            with open(file_path, "w") as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
    return False


def remove_fabricated_content(file_path: Path, api_name: str) -> bool:
    """Remove sections documenting fabricated APIs."""
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        skip_section = False
        skip_code_block = False

        for i, line in enumerate(lines):
            # Check if this line starts a section about the fabricated API
            if f"### {api_name}" in line or f"## {api_name}" in line:
                skip_section = True
                continue

            # Check if we're in a code block that uses the fabricated API
            if "```python" in line and i + 1 < len(lines):
                # Look ahead to see if the code block contains the fabricated API
                next_lines = "".join(lines[i : min(i + 10, len(lines))])
                if api_name in next_lines:
                    skip_code_block = True

            # Skip lines in fabricated sections
            if skip_section:
                # Stop skipping at next section header
                if line.startswith("#") and not line.startswith("####"):
                    skip_section = False
                else:
                    continue

            # Skip code blocks with fabricated APIs
            if skip_code_block:
                if "```" in line and "```python" not in line:
                    skip_code_block = False
                    continue

            # Keep lines that don't contain the fabricated API
            if api_name not in line:
                new_lines.append(line)

        # Write back if changes were made
        if len(new_lines) != len(lines):
            with open(file_path, "w") as f:
                f.writelines(new_lines)
            return True
    except Exception as e:
        print(f"Error removing content from {file_path}: {e}")
    return False


def main():
    print("=" * 80)
    print("API Reference Fix Script")
    print("=" * 80)
    print()

    total_fixes = 0
    total_removals = 0

    # Process all fabricated APIs from the report
    for api_issue in report["fabricated_apis"]:
        file_path = Path(api_issue["file"])
        import_str = api_issue["import"]

        # Check if we have a correction for this import
        corrected = False
        for old_pattern, new_pattern in IMPORT_CORRECTIONS.items():
            if old_pattern in import_str or import_str.startswith(
                old_pattern.replace(" import ", ".")
            ):
                # Try to fix the import
                if fix_import_in_file(file_path, old_pattern, new_pattern):
                    print(f"✅ Fixed import in {file_path.name}: {old_pattern} → {new_pattern}")
                    total_fixes += 1
                    corrected = True
                    break

        # If not corrected and it's a fabricated API, remove it
        if not corrected:
            for fabricated_api in FABRICATED_APIS_TO_REMOVE:
                if fabricated_api in import_str:
                    if remove_fabricated_content(file_path, fabricated_api):
                        print(f"❌ Removed fabricated API from {file_path.name}: {fabricated_api}")
                        total_removals += 1
                    break

    # Special case: Fix TradingAlgorithm imports more comprehensively
    docs_path = Path("docs/api")
    for md_file in docs_path.rglob("*.md"):
        with open(md_file, "r") as f:
            content = f.read()

        original_content = content

        # Fix TradingAlgorithm imports
        content = re.sub(
            r"from rustybt import TradingAlgorithm",
            "from rustybt.algorithm import TradingAlgorithm",
            content,
        )

        # Fix run_algorithm imports
        content = re.sub(
            r"from rustybt import run_algorithm", "from rustybt.api import run_algorithm", content
        )

        # Fix symbol imports (check if it needs fixing)
        # symbol is actually in rustybt.api, so this might be correct

        if content != original_content:
            with open(md_file, "w") as f:
                f.write(content)
            print(f"✅ Fixed imports in {md_file}")
            total_fixes += 1

    print()
    print("=" * 80)
    print(f"SUMMARY: {total_fixes} imports fixed, {total_removals} fabricated APIs removed")
    print("=" * 80)

    return total_fixes + total_removals > 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
