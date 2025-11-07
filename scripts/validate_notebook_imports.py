#!/usr/bin/env python3
"""
Validate that all imports in notebooks can be resolved.

This script checks that every import statement in every notebook
corresponds to an actual module/class/function in the rustybt codebase.
"""

import ast
import json
import sys
from pathlib import Path
from typing import List, Tuple


def extract_imports_from_cell(source: str) -> List[Tuple[str, str]]:
    """Extract import statements from notebook cell source.

    Returns:
        List of (module, name) tuples
    """
    imports = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, alias.asname or alias.name))

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                imports.append((f"{module}.{alias.name}", alias.asname or alias.name))

    return imports


def validate_import(module_path: str) -> Tuple[bool, str]:
    """Validate that an import can be resolved.

    Returns:
        (success, error_message)
    """
    try:
        # Try to import the module
        parts = module_path.split('.')
        module_name = parts[0]

        # Special handling for rustybt imports
        if module_name == 'rustybt':
            import rustybt
            obj = rustybt

            for part in parts[1:]:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return False, f"Module {module_path}: attribute '{part}' not found"

            return True, ""

        # For other imports, just try importing
        __import__(module_name)
        return True, ""

    except ImportError as e:
        return False, f"Import error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def validate_notebook(notebook_path: Path) -> Tuple[int, int, List[str]]:
    """Validate imports in a notebook.

    Returns:
        (total_imports, failed_imports, error_messages)
    """
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    errors = []
    total_imports = 0
    failed_imports = 0

    for i, cell in enumerate(notebook.get('cells', [])):
        if cell.get('cell_type') != 'code':
            continue

        source = ''.join(cell.get('source', []))
        imports = extract_imports_from_cell(source)

        for module_path, _ in imports:
            total_imports += 1

            # Skip commented imports
            if module_path.startswith('#'):
                continue

            success, error_msg = validate_import(module_path)

            if not success:
                failed_imports += 1
                errors.append(
                    f"  Cell {i}: {module_path}\n"
                    f"    Error: {error_msg}"
                )

    return total_imports, failed_imports, errors


def main():
    """Validate all notebooks."""
    notebooks_dir = Path('docs/examples/notebooks')

    if not notebooks_dir.exists():
        print(f"❌ Notebooks directory not found: {notebooks_dir}")
        return 1

    # Find all notebooks
    notebooks = list(notebooks_dir.rglob('*.ipynb'))

    if not notebooks:
        print(f"⚠️  No notebooks found in {notebooks_dir}")
        return 0

    print(f"\n{'='*60}")
    print(f"Validating imports in {len(notebooks)} notebooks")
    print(f"{'='*60}\n")

    total_notebooks = 0
    failed_notebooks = 0
    all_errors = []

    for notebook_path in sorted(notebooks):
        total_imports, failed_imports, errors = validate_notebook(notebook_path)

        total_notebooks += 1

        if failed_imports > 0:
            failed_notebooks += 1
            print(f"❌ {notebook_path.name}")
            print(f"   {failed_imports}/{total_imports} imports failed")
            for error in errors:
                print(error)
            all_errors.extend(errors)
        else:
            print(f"✅ {notebook_path.name}")
            print(f"   {total_imports} imports verified")

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total notebooks: {total_notebooks}")
    print(f"  Failed notebooks: {failed_notebooks}")
    print(f"  Success rate: {(total_notebooks - failed_notebooks) / total_notebooks * 100:.1f}%")
    print(f"{'='*60}\n")

    if failed_notebooks > 0:
        print(f"❌ {failed_notebooks} notebooks have import errors")
        return 1

    print("✅ All notebook imports validated successfully!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
