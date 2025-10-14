#!/usr/bin/env python3
"""
Fix the last 8 API reference issues to achieve 100% verification.
"""

import re
from pathlib import Path


def fix_last_issues():
    """Fix the final 8 issues."""

    # These are the exact fixes needed based on the verification report
    FINAL_8_FIXES = {
        # FixedSlippage is in slippage module, not commission
        "from rustybt.finance.commission import FixedSlippage": "from rustybt.finance.slippage import FixedSlippage",
        # ContinuousParameterSpace should be ParameterSpace
        "from rustybt.optimization.parameter_space import ContinuousParameterSpace": "from rustybt.optimization.parameter_space import ParameterSpace",
        "ContinuousParameterSpace": "ParameterSpace",  # Fix references in text too
    }

    # Files to fix based on verification report
    files_to_fix = [
        "docs/api/analytics/README.md",
        "docs/api/optimization/README.md",
        "docs/api/optimization/algorithms/bayesian.md",
        "docs/api/optimization/algorithms/genetic.md",
        "docs/api/optimization/algorithms/grid-search.md",
        "docs/api/optimization/best-practices/overfitting-prevention.md",
        "docs/api/optimization/parallel/multiprocessing.md",
        "docs/api/optimization/walk-forward/framework.md",
    ]

    fixed_count = 0

    for file_path in files_to_fix:
        file_path = Path(file_path)
        if file_path.exists():
            with open(file_path, "r") as f:
                content = f.read()

            original_content = content

            # Apply fixes
            for old_text, new_text in FINAL_8_FIXES.items():
                if old_text in content:
                    content = content.replace(old_text, new_text)
                    fixed_count += 1

            if content != original_content:
                with open(file_path, "w") as f:
                    f.write(content)
                print(f"✅ Fixed {file_path.name}")

    return fixed_count


def main():
    print("=" * 80)
    print("Final 8 API Fixes - Achieving 100% Verification")
    print("=" * 80)
    print()

    fixed_count = fix_last_issues()

    print()
    print("=" * 80)
    print(f"Fixed {fixed_count} issues")
    print("Ready for 100% verification!")
    print("=" * 80)


if __name__ == "__main__":
    main()
