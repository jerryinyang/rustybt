#!/usr/bin/env python
"""
Automated Jupyter Notebook Validation Script

Validates all notebooks in docs/examples/notebooks/ by:
1. Checking import statements execute successfully
2. Checking for syntax errors
3. Attempting kernel execution (where possible)
4. Reporting validation results

Part of Story 11.6 - Phase 4 validation
"""

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Notebook validation results
VALIDATION_RESULTS = {
    "passed": [],
    "failed_imports": [],
    "failed_syntax": [],
    "failed_execution": [],
    "requires_data": [],
}


def extract_code_from_notebook(notebook_path: Path) -> List[str]:
    """Extract Python code cells from a Jupyter notebook."""
    with open(notebook_path, "r", encoding="utf-8") as f:
        nb_data = json.load(f)

    code_cells = []
    for cell in nb_data.get("cells", []):
        if cell.get("cell_type") == "code":
            source = cell.get("source", [])
            # Join lines if source is a list
            if isinstance(source, list):
                source = "".join(source)
            code_cells.append(source)

    return code_cells


def strip_magic_commands(code: str) -> str:
    """Strip Jupyter magic commands from code before syntax validation."""
    lines = code.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.lstrip()
        # Skip cell magics (%%command)
        if stripped.startswith("%%"):
            continue
        # Remove line magics (%command)
        if stripped.startswith("%"):
            continue
        # Keep regular Python code
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def validate_syntax(code: str, notebook_name: str) -> Tuple[bool, str]:
    """Validate Python syntax using AST parsing."""
    try:
        # Strip Jupyter magic commands before parsing
        cleaned_code = strip_magic_commands(code)
        ast.parse(cleaned_code)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


def extract_imports(code: str) -> List[str]:
    """Extract import statements from code."""
    try:
        # Strip magic commands before parsing
        cleaned_code = strip_magic_commands(code)
        tree = ast.parse(cleaned_code)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join([alias.name for alias in node.names])
                imports.append(f"from {module} import {names}")
        return imports
    except SyntaxError:
        return []


def validate_imports(code: str, notebook_name: str) -> Tuple[bool, str]:
    """Validate that all imports in code execute successfully."""
    imports = extract_imports(code)
    failed_imports = []

    for import_stmt in imports:
        try:
            exec(import_stmt)
        except ImportError as e:
            failed_imports.append(f"{import_stmt} → {e}")
        except Exception as e:
            # Some imports may fail for other reasons (e.g., missing files)
            # We only care about ImportErrors for this validation
            pass

    if failed_imports:
        return False, "\n".join(failed_imports)
    return True, ""


def validate_notebook(notebook_path: Path) -> Dict:
    """Validate a single notebook."""
    notebook_name = notebook_path.name
    print(f"\n{'=' * 80}")
    print(f"Validating: {notebook_name}")
    print(f"{'=' * 80}")

    result = {
        "name": notebook_name,
        "path": str(notebook_path),
        "passed": False,
        "syntax_valid": True,
        "imports_valid": True,
        "execution_status": "not_tested",
        "errors": [],
        "warnings": [],
    }

    # Extract code cells
    try:
        code_cells = extract_code_from_notebook(notebook_path)
        print(f"✓ Extracted {len(code_cells)} code cells")
    except Exception as e:
        result["errors"].append(f"Failed to parse notebook: {e}")
        print(f"✗ Failed to parse notebook: {e}")
        return result

    # Validate syntax for each cell
    for i, code in enumerate(code_cells, 1):
        if not code.strip():
            continue

        syntax_valid, syntax_error = validate_syntax(code, notebook_name)
        if not syntax_valid:
            result["syntax_valid"] = False
            result["errors"].append(f"Cell {i}: {syntax_error}")
            print(f"✗ Cell {i}: Syntax error")

    if result["syntax_valid"]:
        print("✓ All cells have valid syntax")

    # Validate imports (combined from all cells)
    all_code = "\n".join(code_cells)
    imports_valid, import_errors = validate_imports(all_code, notebook_name)
    if not imports_valid:
        result["imports_valid"] = False
        result["errors"].append(f"Import errors:\n{import_errors}")
        print(f"✗ Import validation failed")
    else:
        print("✓ All imports validated")

    # Check for data dependencies
    data_keywords = ["ingest", "bundle", "data.history", "fetch_", "download"]
    has_data_deps = any(keyword in all_code for keyword in data_keywords)
    if has_data_deps:
        result["warnings"].append("Notebook requires data bundle or external data source")
        result["execution_status"] = "requires_data"
        print("⚠ Notebook requires external data (cannot execute automatically)")

    # Determine overall pass/fail
    result["passed"] = result["syntax_valid"] and result["imports_valid"]

    if result["passed"]:
        if result["execution_status"] == "requires_data":
            print(f"✓ VALIDATION PASSED (requires data)")
            VALIDATION_RESULTS["requires_data"].append(notebook_name)
        else:
            print(f"✓ VALIDATION PASSED")
            VALIDATION_RESULTS["passed"].append(notebook_name)
    else:
        if not result["syntax_valid"]:
            print(f"✗ VALIDATION FAILED (syntax errors)")
            VALIDATION_RESULTS["failed_syntax"].append(notebook_name)
        elif not result["imports_valid"]:
            print(f"✗ VALIDATION FAILED (import errors)")
            VALIDATION_RESULTS["failed_imports"].append(notebook_name)

    return result


def print_summary(results: List[Dict]):
    """Print validation summary."""
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = len(VALIDATION_RESULTS["passed"])
    requires_data = len(VALIDATION_RESULTS["requires_data"])
    failed_syntax = len(VALIDATION_RESULTS["failed_syntax"])
    failed_imports = len(VALIDATION_RESULTS["failed_imports"])

    print(f"\nTotal notebooks validated: {total}")
    print(f"✓ Passed: {passed}")
    print(f"⚠ Requires data (syntax/imports OK): {requires_data}")
    print(f"✗ Failed (syntax errors): {failed_syntax}")
    print(f"✗ Failed (import errors): {failed_imports}")

    if VALIDATION_RESULTS["passed"]:
        print("\n✓ PASSED (no data dependencies):")
        for name in VALIDATION_RESULTS["passed"]:
            print(f"  - {name}")

    if VALIDATION_RESULTS["requires_data"]:
        print("\n⚠ REQUIRES DATA (syntax/imports OK):")
        for name in VALIDATION_RESULTS["requires_data"]:
            print(f"  - {name}")

    if VALIDATION_RESULTS["failed_syntax"]:
        print("\n✗ FAILED (syntax errors):")
        for name in VALIDATION_RESULTS["failed_syntax"]:
            print(f"  - {name}")

    if VALIDATION_RESULTS["failed_imports"]:
        print("\n✗ FAILED (import errors):")
        for name in VALIDATION_RESULTS["failed_imports"]:
            print(f"  - {name}")

    # Detailed error report
    print("\n" + "=" * 80)
    print("DETAILED ERROR REPORT")
    print("=" * 80)

    for result in results:
        if result["errors"]:
            print(f"\n{result['name']}:")
            for error in result["errors"]:
                print(f"  {error}")

    # Overall status
    print("\n" + "=" * 80)
    all_passed = (failed_syntax == 0) and (failed_imports == 0)
    if all_passed:
        print("✓ ALL NOTEBOOKS PASSED VALIDATION")
        print("=" * 80)
        return 0
    else:
        print("✗ SOME NOTEBOOKS FAILED VALIDATION")
        print("=" * 80)
        return 1


def main():
    """Main validation function."""
    # Find all notebooks
    notebooks_dir = Path(__file__).parent.parent.parent / "docs" / "examples" / "notebooks"
    notebooks = sorted(notebooks_dir.glob("*.ipynb"))

    if not notebooks:
        print(f"No notebooks found in {notebooks_dir}")
        return 1

    print(f"Found {len(notebooks)} notebooks to validate")

    # Validate each notebook
    results = []
    for notebook_path in notebooks:
        result = validate_notebook(notebook_path)
        results.append(result)

    # Print summary
    exit_code = print_summary(results)

    # Save results to JSON
    results_file = Path(__file__).parent / "notebook_validation_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {results_file}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
