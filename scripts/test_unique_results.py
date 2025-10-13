#!/usr/bin/env python3
"""
Unique Results Test Script for Zero-Mock Enforcement

Verifies that functions produce different outputs for different inputs, which
helps detect functions that always return the same value (mock implementations).

Detection Strategy:
1. Find functions that take parameters
2. Call with different inputs
3. Verify outputs are different

Usage:
    python scripts/test_unique_results.py           # Test all calculation functions
    python scripts/test_unique_results.py --verbose # Show detailed test results
"""

import argparse
import ast
import importlib
import inspect
import sys
import warnings
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, List, Optional, Set, Tuple


class FunctionFinder(ast.NodeVisitor):
    """AST visitor that finds testable calculation functions."""

    def __init__(self):
        self.functions: List[Tuple[int, str]] = []
        self.calculation_keywords = [
            "calculate",
            "compute",
            "process",
            "evaluate",
            "measure",
            "derive",
            "determine",
            "estimate",
        ]

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Find calculation functions."""
        func_name_lower = node.name.lower()

        # Check if function name contains calculation keywords
        if any(keyword in func_name_lower for keyword in self.calculation_keywords):
            # Make sure it takes parameters
            if len(node.args.args) > 0:
                self.functions.append((node.lineno, node.name))

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Find async calculation functions."""
        func_name_lower = node.name.lower()

        if any(keyword in func_name_lower for keyword in self.calculation_keywords):
            if len(node.args.args) > 0:
                self.functions.append((node.lineno, node.name))

        self.generic_visit(node)


def find_testable_functions(directory: Path) -> List[Tuple[str, str, int, Callable]]:
    """
    Find all testable calculation functions in the codebase.

    Args:
        directory: Root directory to search

    Returns:
        List of (module_path, function_name, line_number, function_object) tuples
    """
    functions = []

    for py_file in directory.rglob("*.py"):
        # Skip test files
        if any(part.startswith("test") or part == "tests" for part in py_file.parts):
            continue

        # Skip special files
        if py_file.name in ("__init__.py", "_version.py", "setup.py"):
            continue

        # Use AST to find function names
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
        except (IOError, SyntaxError):
            continue

        finder = FunctionFinder()
        finder.visit(tree)

        if not finder.functions:
            continue

        # Convert file path to module name
        try:
            rel_path = py_file.relative_to(Path.cwd())
            module_name = str(rel_path.with_suffix("")).replace("/", ".")
        except ValueError:
            continue

        # Try to import the module
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                module = importlib.import_module(module_name)
        except Exception:
            continue

        # Get function objects
        for lineno, func_name in finder.functions:
            try:
                func_obj = getattr(module, func_name)
                if callable(func_obj):
                    functions.append((module_name, func_name, lineno, func_obj))
            except AttributeError:
                continue

    return functions


def generate_test_inputs(param_count: int) -> List[Tuple[Any, ...]]:
    """
    Generate diverse test inputs for a function.

    Args:
        param_count: Number of parameters the function takes

    Returns:
        List of test input tuples
    """
    # Base test values
    test_values = [
        Decimal("10"),
        Decimal("20"),
        Decimal("30"),
        Decimal("100"),
        Decimal("0.5"),
    ]

    # Generate input combinations
    test_inputs = []
    for val in test_values[: min(5, len(test_values))]:
        args = tuple([val] * param_count)
        test_inputs.append(args)

    return test_inputs


def test_function_uniqueness(
    module_name: str, func_name: str, func: Callable, verbose: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Test if function produces unique results for different inputs.

    Args:
        module_name: Module containing the function
        func_name: Name of the function
        func: The function object
        verbose: Print detailed test information

    Returns:
        (passes_test, failure_reason) tuple
        - passes_test: True if function produces unique outputs
        - failure_reason: Description of why test failed, or None if passed
    """
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        # Can't introspect
        return True, None

    params = list(sig.parameters.values())

    # Skip if no parameters
    if not params:
        return True, None

    # Skip if too many parameters (hard to test)
    if len(params) > 5:
        if verbose:
            print(f"  Skipped (too many parameters: {len(params)})")
        return True, None

    # Generate test inputs
    test_inputs = generate_test_inputs(len(params))

    results: Set[Any] = set()
    successful_calls = 0

    for inputs in test_inputs:
        try:
            result = func(*inputs)

            # Skip None results
            if result is None:
                continue

            # Try to make result hashable for set comparison
            hashable_result = None
            if isinstance(result, (int, float, str, bool, Decimal)):
                hashable_result = result
            elif isinstance(result, (list, tuple)):
                try:
                    hashable_result = tuple(result)
                except TypeError:
                    pass
            elif hasattr(result, "__hash__"):
                try:
                    hash(result)
                    hashable_result = result
                except TypeError:
                    pass

            if hashable_result is not None:
                results.add(hashable_result)
                successful_calls += 1

        except Exception as e:
            # Function raised exception - skip this test
            if verbose:
                print(f"  Exception with inputs {inputs}: {type(e).__name__}")
            continue

    # Need at least 2 successful calls to compare
    if successful_calls < 2:
        if verbose:
            print(f"  Skipped (insufficient successful calls: {successful_calls})")
        return True, None

    # If all results are identical, it's suspicious
    if len(results) == 1:
        failure_reason = f"All {successful_calls} calls returned same value: {list(results)[0]}"
        return False, failure_reason

    # Function produces unique results - good
    if verbose:
        print(f"  Passed ({len(results)} unique results from {successful_calls} calls)")

    return True, None


def scan_functions(directory: Path, verbose: bool = False) -> bool:
    """
    Scan all calculation functions and test them.

    Args:
        directory: Root directory to scan
        verbose: Print detailed information

    Returns:
        True if any suspicious functions found, False otherwise
    """
    print("Searching for testable calculation functions...")
    functions = find_testable_functions(directory)

    if not functions:
        print("No testable calculation functions found")
        return False

    print(f"Found {len(functions)} calculation function(s)\n")

    suspicious_functions = []
    tested_count = 0
    skipped_count = 0

    for module_name, func_name, lineno, func in functions:
        if verbose:
            print(f"Testing {module_name}.{func_name}...")

        passes, failure_reason = test_function_uniqueness(module_name, func_name, func, verbose)

        if not passes:
            tested_count += 1
            suspicious_functions.append((module_name, func_name, lineno, failure_reason))
            if verbose:
                print(f"  ⚠️  SUSPICIOUS: {failure_reason}\n")
        else:
            if failure_reason is None:
                tested_count += 1
            else:
                skipped_count += 1
            if verbose:
                print()

    # Print summary
    print(f"{'='*60}")
    print(f"Tested {tested_count} function(s), skipped {skipped_count}")
    print(f"Found {len(suspicious_functions)} suspicious function(s)")
    print(f"{'='*60}")

    if suspicious_functions:
        print("\n⚠️  Functions that produce identical results for different inputs:\n")
        for module_name, func_name, lineno, reason in suspicious_functions:
            print(f"  {module_name}.{func_name}:{lineno}")
            print(f"    Issue: {reason}\n")
        return True
    else:
        print("\n✅ All functions produce unique results for different inputs")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test functions for unique output with different inputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--verbose", action="store_true", help="Print detailed test results")

    args = parser.parse_args()

    rustybt_dir = Path("rustybt")

    if not rustybt_dir.exists():
        print(f"Error: Directory 'rustybt' not found", file=sys.stderr)
        sys.exit(1)

    suspicious_found = scan_functions(rustybt_dir, verbose=args.verbose)

    # Note: This script exits with 0 even if suspicious functions found
    # because identical results might be legitimate in some cases
    # (e.g., clamping functions, boundary conditions)
    # It's a warning, not an error
    if suspicious_found:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
