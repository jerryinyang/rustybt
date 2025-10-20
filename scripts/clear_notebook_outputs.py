#!/usr/bin/env python3
"""
Clear all output cells from Jupyter notebooks.

This script removes execution outputs, execution counts, and metadata
from notebooks to prevent personal information leakage.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def clear_notebook_outputs(notebook_path: Path) -> bool:
    """
    Clear all outputs from a Jupyter notebook.

    Args:
        notebook_path: Path to the notebook file

    Returns:
        True if notebook was modified, False otherwise
    """
    try:
        with open(notebook_path, "r", encoding="utf-8") as f:
            notebook = json.load(f)

        modified = False

        # Clear outputs from all cells
        for cell in notebook.get("cells", []):
            if cell.get("cell_type") == "code":
                # Clear outputs
                if cell.get("outputs"):
                    cell["outputs"] = []
                    modified = True

                # Clear execution count
                if cell.get("execution_count") is not None:
                    cell["execution_count"] = None
                    modified = True

        if modified:
            # Write back to file
            with open(notebook_path, "w", encoding="utf-8") as f:
                json.dump(notebook, f, indent=1, ensure_ascii=False)
                f.write("\n")  # Add newline at end of file

            print(f"✓ Cleared outputs from: {notebook_path}")
            return True
        else:
            print(f"○ No outputs to clear: {notebook_path}")
            return False

    except Exception as e:
        print(f"✗ Error processing {notebook_path}: {e}", file=sys.stderr)
        return False


def main():
    """Clear outputs from specified notebooks or all notebooks in a directory."""
    if len(sys.argv) < 2:
        print("Usage: python clear_notebook_outputs.py <notebook1.ipynb> [notebook2.ipynb ...]")
        print("   or: python clear_notebook_outputs.py <directory>")
        sys.exit(1)

    paths = [Path(arg) for arg in sys.argv[1:]]
    notebooks_to_clear = []

    # Collect all notebooks to process
    for path in paths:
        if path.is_dir():
            notebooks_to_clear.extend(path.rglob("*.ipynb"))
        elif path.is_file() and path.suffix == ".ipynb":
            notebooks_to_clear.append(path)
        else:
            print(f"Warning: Skipping {path} (not a notebook or directory)")

    if not notebooks_to_clear:
        print("No notebooks found to process")
        sys.exit(0)

    # Process all notebooks
    print(f"\nProcessing {len(notebooks_to_clear)} notebook(s)...\n")
    modified_count = 0

    for notebook in notebooks_to_clear:
        if clear_notebook_outputs(notebook):
            modified_count += 1

    print(f"\n✓ Cleared outputs from {modified_count}/{len(notebooks_to_clear)} notebook(s)")


if __name__ == "__main__":
    main()
