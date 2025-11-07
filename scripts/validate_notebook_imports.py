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


def extract_imports_from_cell(source: str) -> List[Tuple[str, str, bool]]:
    """Extract import statements from notebook cell source.

    Returns:
        List of (module, name, is_optional) tuples where is_optional indicates
        if the import is inside a try-except block
    """
    imports = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imports

    def visit_node(node, in_try=False):
        """Recursively visit nodes, tracking if we're in a try block."""
        if isinstance(node, ast.Try):
            # Process nodes inside try block
            for child in node.body:
                visit_node(child, in_try=True)
            # Process except/else/finally normally
            for child in node.handlers + node.orelse + node.finalbody:
                visit_node(child, in_try=False)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, alias.asname or alias.name, in_try))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append((f"{module}.{alias.name}", alias.asname or alias.name, in_try))
        else:
            # Recursively visit children
            for child in ast.iter_child_nodes(node):
                visit_node(child, in_try)

    visit_node(tree, in_try=False)
    return imports


def validate_import(module_path: str) -> Tuple[bool, str]:
    """Validate that an import can be resolved.

    Returns:
        (success, error_message)
    """
    import importlib

    try:
        # Try to import the full module path first
        parts = module_path.split(".")

        # Try importing progressively longer paths
        obj = None
        for i in range(len(parts), 0, -1):
            test_path = ".".join(parts[:i])
            try:
                obj = importlib.import_module(test_path)
                # If we successfully imported a shorter path, check remaining parts as attributes
                for part in parts[i:]:
                    if hasattr(obj, part):
                        obj = getattr(obj, part)
                    else:
                        return False, f"Module {test_path}: attribute '{part}' not found"
                return True, ""
            except (ImportError, ModuleNotFoundError):
                continue

        # If none of the progressive imports worked
        return False, f"Could not import {module_path}"

    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def validate_notebook(notebook_path: Path) -> Tuple[int, int, List[str]]:
    """Validate imports in a notebook.

    Returns:
        (total_imports, failed_imports, error_messages)
    """
    with open(notebook_path, "r", encoding="utf-8") as f:
        notebook = json.load(f)

    errors = []
    total_imports = 0
    failed_imports = 0

    for i, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue

        source = "".join(cell.get("source", []))
        imports = extract_imports_from_cell(source)

        for module_path, _, is_optional in imports:
            total_imports += 1

            # Skip commented imports
            if module_path.startswith("#"):
                continue

            success, error_msg = validate_import(module_path)

            # Skip optional imports (in try-except blocks) that fail
            if not success and is_optional:
                continue

            if not success:
                failed_imports += 1
                errors.append(f"  Cell {i}: {module_path}\n    Error: {error_msg}")

    return total_imports, failed_imports, errors


def main():
    """Validate all notebooks."""
    notebooks_dir = Path("docs/examples/notebooks")

    if not notebooks_dir.exists():
        print(f"❌ Notebooks directory not found: {notebooks_dir}")
        return 1

    # Find all notebooks
    notebooks = list(notebooks_dir.rglob("*.ipynb"))

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


if __name__ == "__main__":
    sys.exit(main())
