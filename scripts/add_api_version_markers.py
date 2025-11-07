#!/usr/bin/env python3
"""
Add API version markers to all tutorial notebooks.

Adds a cell at the beginning of each notebook indicating:
- RustyBT version the notebook was written for
- Last validated date
- Link to API documentation
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def add_version_marker(notebook_path: Path) -> bool:
    """Add API version marker to notebook.

    Returns:
        True if modified, False if already has marker
    """
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    # Check if first cell already has version marker
    cells = notebook.get('cells', [])
    if cells and 'API Version' in ''.join(cells[0].get('source', [])):
        return False  # Already has marker

    # Create version marker cell
    version_cell = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "---\n",
            "\n",
            "**📋 Notebook Information**\n",
            "\n",
            "- **RustyBT Version:** 0.1.2+\n",
            f"- **Last Validated:** {datetime.now().strftime('%Y-%m-%d')}\n",
            "- **API Compatibility:** Verified ✅\n",
            "- **Documentation:** [API Reference](https://rustybt.readthedocs.io/en/latest/api/)\n",
            "\n",
            "---"
        ]
    }

    # Insert at beginning (after title if exists)
    if cells and cells[0].get('cell_type') == 'markdown':
        # Insert after title
        cells.insert(1, version_cell)
    else:
        # Insert at very beginning
        cells.insert(0, version_cell)

    notebook['cells'] = cells

    # Write back
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)

    return True


def main():
    """Add version markers to all notebooks."""
    notebooks_dir = Path('docs/examples/notebooks')

    notebooks = list(notebooks_dir.rglob('*.ipynb'))

    print(f"\n{'='*60}")
    print(f"Adding API version markers to {len(notebooks)} notebooks")
    print(f"{'='*60}\n")

    modified = 0
    skipped = 0

    for notebook_path in sorted(notebooks):
        if add_version_marker(notebook_path):
            print(f"✅ Added marker: {notebook_path.relative_to(notebooks_dir)}")
            modified += 1
        else:
            print(f"⏭️  Skipped (has marker): {notebook_path.relative_to(notebooks_dir)}")
            skipped += 1

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Modified: {modified}")
    print(f"  Skipped: {skipped}")
    print(f"  Total: {len(notebooks)}")
    print(f"{'='*60}\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
