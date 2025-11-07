#!/usr/bin/env python3
"""Fix import errors in notebooks."""

import json
from pathlib import Path

fixes = {
    # Notebook 12: Fix finance imports
    "docs/examples/notebooks/advanced/12_advanced_order_management.ipynb": [
        ("from rustybt.finance import (", "from rustybt.finance.execution import ("),
    ],
    # Notebook 13: Fix optimization imports
    "docs/examples/notebooks/advanced/13_portfolio_optimization_walk_forward.ipynb": [
        (
            "from rustybt.optimization import BayesianOptimizer",
            "from rustybt.optimization.search import BayesianOptimizer",
        ),
        (
            "from rustybt.optimization.objective import SharpeRatio",
            "from rustybt.optimization.objective import ObjectiveMetric",
        ),
        (
            "from rustybt.optimization.objective import SortinoRatio",
            "# SortinoRatio is available via ObjectiveMetric enum",
        ),
        (
            "from rustybt.optimization.objective import CalmarRatio",
            "# CalmarRatio is available via ObjectiveMetric enum",
        ),
    ],
    # Notebook 14: Fix ATR and StopOrder imports
    "docs/examples/notebooks/advanced/14_multi_timeframe_strategies.ipynb": [
        (
            "from rustybt.pipeline.factors import ATR",
            "from rustybt.pipeline.factors import TrueRange",
        ),
        (
            "from rustybt.finance import StopOrder",
            "from rustybt.finance.execution import StopOrder",
        ),
    ],
}


def fix_notebook(notebook_path: Path, replacements: list):
    """Apply fixes to a notebook."""
    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook = json.load(f)

    modified = False
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue

        source = "".join(cell.get("source", []))
        original_source = source

        for old, new in replacements:
            if old in source:
                source = source.replace(old, new)
                modified = True
                print(f"  Fixed: {old[:50]}...")

        if source != original_source:
            cell["source"] = source.split("\n")
            # Preserve newlines
            cell["source"] = [
                line + "\n" if i < len(cell["source"]) - 1 else line
                for i, line in enumerate(cell["source"])
            ]

    if modified:
        with open(notebook_path, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=1)
        print(f"✅ Fixed {notebook_path.name}")
    else:
        print(f"⚠️  No changes needed for {notebook_path.name}")

    return modified


def main():
    """Fix all notebooks."""
    print("Fixing notebook import errors...")
    print("=" * 60)

    total_fixed = 0
    for notebook_path, replacements in fixes.items():
        path = Path(notebook_path)
        if not path.exists():
            print(f"❌ Not found: {path}")
            continue

        print(f"\n📓 {path.name}")
        if fix_notebook(path, replacements):
            total_fixed += 1

    print("\n" + "=" * 60)
    print(f"✅ Fixed {total_fixed} notebooks")
    print("=" * 60)


if __name__ == "__main__":
    main()
