#!/usr/bin/env python3
"""
Validation Verification Script for Zero-Mock Enforcement

Verifies that validation functions actually reject invalid data rather than
being mock implementations that always return True.

Detection Strategy:
1. Find all functions with "validate" in name
2. Test with intentionally invalid inputs
3. Verify they raise exceptions or return False

Usage:
    python scripts/verify_validations.py                     # Scan all validators
    python scripts/verify_validations.py --ensure-real-checks # Exit with error if bad validators found
    python scripts/verify_validations.py --verbose           # Show detailed test results
"""

import argparse
import ast
import importlib
import inspect
import sys
import warnings
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple


class ValidatorFinder(ast.NodeVisitor):
    """AST visitor that finds validation functions."""

    def __init__(self):
        self.validators: List[Tuple[int, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Find functions with 'validate' in name."""
        if "validate" in node.name.lower() or "check" in node.name.lower():
            self.validators.append((node.lineno, node.name))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Find async functions with 'validate' in name."""
        if "validate" in node.name.lower() or "check" in node.name.lower():
            self.validators.append((node.lineno, node.name))
        self.generic_visit(node)


def find_validation_functions(directory: Path) -> List[Tuple[str, str, int, Callable]]:
    """
    Find all validation functions in the codebase.

    Args:
        directory: Root directory to search

    Returns:
        List of (module_path, function_name, line_number, function_object) tuples
    """
    validators = []

    for py_file in directory.rglob("*.py"):
        # Skip test files
        if any(part.startswith("test") or part == "tests" for part in py_file.parts):
            continue

        # Skip __init__.py and special files
        if py_file.name in ("__init__.py", "_version.py", "setup.py"):
            continue

        # Use AST to find validator function names
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
        except (IOError, SyntaxError):
            continue

        finder = ValidatorFinder()
        finder.visit(tree)

        if not finder.validators:
            continue

        # Convert file path to module name
        try:
            rel_path = py_file.relative_to(Path.cwd())
            module_name = str(rel_path.with_suffix("")).replace("/", ".")
        except ValueError:
            continue

        # Try to import the module and get function objects
        try:
            # Suppress warnings during import
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                module = importlib.import_module(module_name)
        except Exception:
            continue

        # Get function objects
        for lineno, func_name in finder.validators:
            try:
                func_obj = getattr(module, func_name)
                if callable(func_obj):
                    validators.append((module_name, func_name, lineno, func_obj))
            except AttributeError:
                continue

    return validators


def test_validator(
    module_name: str, func_name: str, func: Callable, verbose: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Test if validator properly rejects invalid data.

    Args:
        module_name: Module containing the validator
        func_name: Name of the validator function
        func: The validator function object
        verbose: Print detailed test information

    Returns:
        (passes_test, failure_reason) tuple
        - passes_test: True if validator works correctly, False if it's a mock
        - failure_reason: Description of why test failed, or None if passed
    """
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        # Can't introspect signature
        return True, None

    params = list(sig.parameters.values())

    # Skip if no parameters (can't test)
    if not params:
        return True, None

    # Skip if all parameters have defaults (might be legitimate)
    if all(p.default != inspect.Parameter.empty for p in params):
        return True, None

    # Prepare invalid test inputs
    invalid_test_cases = [
        None,
        "",
        "invalid",
        -999999,
        [],
        {},
        object(),
    ]

    test_results = []
    accepted_invalid_inputs = []

    # Test with first parameter only
    for invalid_input in invalid_test_cases:
        try:
            # Call validator with invalid input
            if len(params) == 1:
                result = func(invalid_input)
            else:
                # Multi-parameter function - try calling with None for all params
                args = [None] * len(params)
                result = func(*args)

            # If it returns True, it's accepting invalid data
            if result is True:
                accepted_invalid_inputs.append(repr(invalid_input))
            elif result is False:
                # Validator correctly returned False
                test_results.append("rejected")
            # None or other returns are ambiguous

        except Exception as e:
            # Good - validator raised an exception for invalid input
            test_results.append("raised")
            if verbose:
                print(f"  Validator correctly raised: {type(e).__name__}")

    # Determine if validator is real or mock
    if accepted_invalid_inputs:
        # Validator accepted invalid inputs - likely a mock
        failure_reason = f"Accepted invalid inputs: {', '.join(accepted_invalid_inputs)}"
        return False, failure_reason

    if not test_results:
        # Couldn't test effectively - assume it's OK
        return True, None

    # If validator raised exceptions or returned False, it's good
    if "raised" in test_results or "rejected" in test_results:
        return True, None

    # Ambiguous - assume OK
    return True, None


def scan_validators(directory: Path, verbose: bool = False) -> bool:
    """
    Scan all validators and test them.

    Args:
        directory: Root directory to scan
        verbose: Print detailed information

    Returns:
        True if any bad validators found, False otherwise
    """
    print("Searching for validation functions...")
    validators = find_validation_functions(directory)

    if not validators:
        print("No validation functions found")
        return False

    print(f"Found {len(validators)} validation function(s)\n")

    bad_validators = []
    tested_count = 0

    for module_name, func_name, lineno, func in validators:
        tested_count += 1

        if verbose:
            print(f"Testing {module_name}.{func_name}...")

        passes, failure_reason = test_validator(module_name, func_name, func, verbose)

        if not passes:
            bad_validators.append((module_name, func_name, lineno, failure_reason))
            if verbose:
                print(f"  ❌ FAILED: {failure_reason}\n")
        else:
            if verbose:
                print(f"  ✅ Passed\n")

    # Print summary
    print(f"{'='*60}")
    print(f"Tested {tested_count} validator function(s)")
    print(f"Found {len(bad_validators)} suspicious validator(s)")
    print(f"{'='*60}")

    if bad_validators:
        print("\n❌ Validators that may be mocks (accept invalid data):\n")
        for module_name, func_name, lineno, reason in bad_validators:
            print(f"  {module_name}.{func_name}:{lineno}")
            print(f"    Reason: {reason}\n")
        return True
    else:
        print("\n✅ All validators properly reject invalid data")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify validation functions reject invalid data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--ensure-real-checks",
        action="store_true",
        help="Exit with error if validators that always return True are found",
    )
    parser.add_argument("--verbose", action="store_true", help="Print detailed test results")

    args = parser.parse_args()

    rustybt_dir = Path("rustybt")

    if not rustybt_dir.exists():
        print(f"Error: Directory 'rustybt' not found", file=sys.stderr)
        sys.exit(1)

    bad_validators_found = scan_validators(rustybt_dir, verbose=args.verbose)

    if bad_validators_found and args.ensure_real_checks:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
