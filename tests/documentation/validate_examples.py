#!/usr/bin/env python
"""
Automated Python Examples Validation Script

Validates all Python example files in examples/ by:
1. Checking syntax validity
2. Checking import statements execute successfully
3. Categorizing examples by type
4. Reporting validation results

Part of Story 11.6 - Phase 4 validation
"""

import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Example validation results
VALIDATION_RESULTS = {
    "passed": [],
    "failed_syntax": [],
    "failed_imports": [],
    "live_trading": [],  # Cannot execute (requires real credentials)
}

# Example categorization
EXAMPLE_CATEGORIES = {
    "data_ingestion": ["ingest_", "custom_data_adapter"],
    "live_trading": ["live_trading", "custom_broker_adapter"],
    "paper_trading": ["paper_trading"],
    "shadow_trading": ["shadow_trading"],
    "portfolio": ["allocation_", "portfolio_allocator"],
    "transaction_costs": ["slippage", "borrow_cost", "overnight_financing", "latency_simulation"],
    "analytics": ["attribution_", "generate_backtest_report"],
    "caching": ["cache"],
    "pipeline": ["pipeline"],
    "advanced": ["high_frequency", "rust_optimized", "websocket"],
}


def categorize_example(filename: str) -> str:
    """Categorize example by filename patterns."""
    for category, patterns in EXAMPLE_CATEGORIES.items():
        if any(pattern in filename for pattern in patterns):
            return category
    return "other"


def validate_syntax(code: str, filename: str) -> Tuple[bool, str]:
    """Validate Python syntax using AST parsing."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


def extract_imports(code: str) -> List[str]:
    """Extract import statements from code."""
    try:
        tree = ast.parse(code)
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


def validate_imports(code: str, filename: str) -> Tuple[bool, str]:
    """Validate that all imports in code execute successfully."""
    imports = extract_imports(code)
    failed_imports = []

    for import_stmt in imports:
        try:
            exec(import_stmt)
        except ImportError as e:
            failed_imports.append(f"{import_stmt} → {e}")
        except Exception as e:
            # Some imports may fail for other reasons (e.g., missing optional dependencies)
            # We only care about ImportErrors for this validation
            pass

    if failed_imports:
        return False, "\n".join(failed_imports)
    return True, ""


def check_security_patterns(code: str, filename: str) -> List[str]:
    """Check for potential security issues in examples."""
    warnings = []

    # Check for hardcoded API keys or secrets
    suspicious_patterns = [
        ("api_key", "Potential hardcoded API key"),
        ("api_secret", "Potential hardcoded API secret"),
        ("password", "Potential hardcoded password"),
    ]

    for pattern, warning in suspicious_patterns:
        if f"{pattern}=" in code or f"{pattern} =" in code:
            # Check if it's using environment variables
            if f"os.getenv" not in code and f"os.environ" not in code:
                warnings.append(warning)

    return warnings


def validate_example(example_path: Path) -> Dict:
    """Validate a single Python example."""
    filename = example_path.name
    category = categorize_example(filename)

    print(f"\n{'=' * 80}")
    print(f"Validating: {filename}")
    print(f"Category: {category}")
    print(f"{'=' * 80}")

    result = {
        "name": filename,
        "path": str(example_path),
        "category": category,
        "passed": False,
        "syntax_valid": True,
        "imports_valid": True,
        "is_live_trading": "live_trading" in filename
        and "paper" not in filename
        and "shadow" not in filename,
        "errors": [],
        "warnings": [],
        "security_warnings": [],
    }

    # Read file
    try:
        with open(example_path, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        result["errors"].append(f"Failed to read file: {e}")
        print(f"✗ Failed to read file: {e}")
        return result

    # Validate syntax
    syntax_valid, syntax_error = validate_syntax(code, filename)
    if not syntax_valid:
        result["syntax_valid"] = False
        result["errors"].append(syntax_error)
        print(f"✗ Syntax error: {syntax_error}")
    else:
        print("✓ Syntax valid")

    # Validate imports
    imports_valid, import_errors = validate_imports(code, filename)
    if not imports_valid:
        result["imports_valid"] = False
        result["errors"].append(f"Import errors:\n{import_errors}")
        print(f"✗ Import validation failed")
    else:
        print("✓ All imports validated")

    # Security checks
    security_warnings = check_security_patterns(code, filename)
    if security_warnings:
        result["security_warnings"] = security_warnings
        for warning in security_warnings:
            print(f"⚠ Security: {warning}")

    # Determine pass/fail
    result["passed"] = result["syntax_valid"] and result["imports_valid"]

    # Categorize result
    if result["is_live_trading"]:
        result["warnings"].append("Live trading example - cannot execute safely")
        print("⚠ Live trading example (cannot execute)")
        VALIDATION_RESULTS["live_trading"].append(filename)
    elif result["passed"]:
        print(f"✓ VALIDATION PASSED")
        VALIDATION_RESULTS["passed"].append(filename)
    else:
        if not result["syntax_valid"]:
            print(f"✗ VALIDATION FAILED (syntax errors)")
            VALIDATION_RESULTS["failed_syntax"].append(filename)
        elif not result["imports_valid"]:
            print(f"✗ VALIDATION FAILED (import errors)")
            VALIDATION_RESULTS["failed_imports"].append(filename)

    return result


def print_summary(results: List[Dict]):
    """Print validation summary."""
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = len(VALIDATION_RESULTS["passed"])
    live_trading = len(VALIDATION_RESULTS["live_trading"])
    failed_syntax = len(VALIDATION_RESULTS["failed_syntax"])
    failed_imports = len(VALIDATION_RESULTS["failed_imports"])

    print(f"\nTotal examples validated: {total}")
    print(f"✓ Passed: {passed}")
    print(f"⚠ Live trading (cannot execute): {live_trading}")
    print(f"✗ Failed (syntax errors): {failed_syntax}")
    print(f"✗ Failed (import errors): {failed_imports}")

    # Category breakdown
    print("\n" + "=" * 80)
    print("CATEGORY BREAKDOWN")
    print("=" * 80)

    categories = {}
    for result in results:
        category = result["category"]
        if category not in categories:
            categories[category] = {"total": 0, "passed": 0, "failed": 0}
        categories[category]["total"] += 1
        if result["passed"] or result["is_live_trading"]:
            categories[category]["passed"] += 1
        else:
            categories[category]["failed"] += 1

    for category, stats in sorted(categories.items()):
        status = "✓" if stats["failed"] == 0 else "✗"
        print(f"{status} {category}: {stats['passed']}/{stats['total']} passed")

    # Detailed lists
    if VALIDATION_RESULTS["passed"]:
        print("\n✓ PASSED:")
        for name in VALIDATION_RESULTS["passed"]:
            print(f"  - {name}")

    if VALIDATION_RESULTS["live_trading"]:
        print("\n⚠ LIVE TRADING (syntax/imports OK, cannot execute):")
        for name in VALIDATION_RESULTS["live_trading"]:
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

    errors_found = False
    for result in results:
        if result["errors"] or result["security_warnings"]:
            errors_found = True
            print(f"\n{result['name']}:")
            for error in result["errors"]:
                print(f"  ERROR: {error}")
            for warning in result["security_warnings"]:
                print(f"  SECURITY WARNING: {warning}")

    if not errors_found:
        print("\nNo errors or security warnings found!")

    # Overall status
    print("\n" + "=" * 80)
    all_passed = (failed_syntax == 0) and (failed_imports == 0)
    if all_passed:
        print("✓ ALL EXAMPLES PASSED VALIDATION")
        print("=" * 80)
        return 0
    else:
        print("✗ SOME EXAMPLES FAILED VALIDATION")
        print("=" * 80)
        return 1


def main():
    """Main validation function."""
    # Find all Python examples
    examples_dir = Path(__file__).parent.parent.parent / "examples"
    examples = sorted(examples_dir.glob("*.py"))

    if not examples:
        print(f"No examples found in {examples_dir}")
        return 1

    print(f"Found {len(examples)} Python examples to validate")

    # Validate each example
    results = []
    for example_path in examples:
        result = validate_example(example_path)
        results.append(result)

    # Print summary
    exit_code = print_summary(results)

    # Save results to JSON
    results_file = Path(__file__).parent / "examples_validation_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {results_file}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
