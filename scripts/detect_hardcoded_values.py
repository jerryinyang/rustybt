#!/usr/bin/env python3
"""
Hardcoded Values Detection Script for Zero-Mock Enforcement

Identifies functions that return constant values (hardcoded returns) which are
often indicators of mock or placeholder implementations.

Detection Patterns:
1. Functions with single `return <constant>` statement
2. Constants: integers, floats, strings, True/False
3. Excludes: None, empty collections, constants from class attributes

Usage:
    python scripts/detect_hardcoded_values.py                  # Scan all rustybt/ files
    python scripts/detect_hardcoded_values.py --fail-on-found  # Exit with error if found
    python scripts/detect_hardcoded_values.py --file FILE      # Scan specific file
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Optional, Tuple


class HardcodedReturnDetector(ast.NodeVisitor):
    """AST visitor that detects functions returning hardcoded constant values."""

    def __init__(self):
        self.violations: List[Tuple[int, str, str, Optional[str]]] = []
        self.current_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Track current class context."""
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check function definitions for hardcoded return values."""
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Check async function definitions for hardcoded return values."""
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node):
        """Check if function returns hardcoded constant."""
        # Skip dunder methods (they often return constants legitimately)
        if node.name.startswith("__") and node.name.endswith("__"):
            return

        # Skip property getters and setters
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id in ("property", "setter", "getter"):
                return
            if isinstance(decorator, ast.Attribute) and decorator.attr in ("setter", "getter"):
                return

        # Skip methods that legitimately return constants
        # - graph_repr, __repr__, __str__ (display methods)
        # - Commission/fee calculate methods that return 0
        # - progress (can legitimately return 1.0 for 100% progress in some modes)
        if node.name in ("graph_repr", "__repr__", "__str__", "calculate", "progress"):
            return

        # Skip staticmethod decorated functions (often legitimate constant returns)
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
                # Check if it's a commission/fee calculation returning 0
                if "commission" in self.current_class.lower() if self.current_class else False:
                    return

        # Filter out docstrings
        body = [stmt for stmt in node.body if not self._is_docstring(stmt)]

        # Check for single return statement
        if len(body) == 1 and isinstance(body[0], ast.Return):
            ret_node = body[0]
            if ret_node.value and self._is_suspicious_constant(ret_node.value):
                value_str = self._get_value_repr(ret_node.value)
                context = f"{self.current_class}.{node.name}" if self.current_class else node.name
                self.violations.append(
                    (node.lineno, context, value_str, self._get_constant_type(ret_node.value))
                )

    def _is_docstring(self, stmt: ast.stmt) -> bool:
        """Check if statement is a docstring."""
        return (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        )

    def _is_suspicious_constant(self, node: ast.AST) -> bool:
        """
        Check if node is a suspicious constant value.

        Returns False for acceptable constants (None, empty collections).
        Returns True for suspicious constants (numbers, strings, booleans).
        """
        if isinstance(node, ast.Constant):
            value = node.value

            # None is acceptable
            if value is None:
                return False

            # Empty strings, empty tuples are acceptable
            if value == "" or value == ():
                return False

            # Detect hardcoded numbers, non-empty strings, booleans
            if isinstance(value, (int, float, str, bool)):
                # Special case: 0, 1, -1 might be legitimate
                if isinstance(value, int) and value in (0, 1, -1):
                    return False
                return True

        # Empty list/dict/set literals are acceptable
        if isinstance(node, (ast.List, ast.Dict, ast.Set)):
            if isinstance(node, ast.List) and not node.elts:
                return False
            if isinstance(node, ast.Dict) and not node.keys:
                return False
            if isinstance(node, ast.Set) and not node.elts:
                return False

        return False

    def _get_constant_type(self, node: ast.AST) -> Optional[str]:
        """Get the type name of a constant node."""
        if isinstance(node, ast.Constant):
            return type(node.value).__name__
        return None

    def _get_value_repr(self, node: ast.AST) -> str:
        """Get string representation of the return value."""
        try:
            return ast.unparse(node)
        except Exception:
            return "<unparseable>"


def scan_file(filepath: Path) -> List[Tuple[int, str, str, Optional[str]]]:
    """
    Scan a single Python file for hardcoded return values.

    Args:
        filepath: Path to the Python file to scan

    Returns:
        List of (line_number, function_name, value, value_type) tuples
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source_code = f.read()
    except (IOError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(source_code, filename=str(filepath))
    except SyntaxError as e:
        print(f"Warning: Syntax error in {filepath}: {e}", file=sys.stderr)
        return []

    detector = HardcodedReturnDetector()
    detector.visit(tree)
    return detector.violations


def scan_directory(directory: Path, exclude_tests: bool = True) -> bool:
    """
    Scan all Python files in a directory for hardcoded return values.

    Args:
        directory: Path to directory to scan
        exclude_tests: Whether to exclude test files

    Returns:
        True if violations found, False otherwise
    """
    violations_found = False
    total_files = 0
    total_violations = 0

    # Find all Python files
    python_files = list(directory.rglob("*.py"))

    # Filter files
    production_files = []
    for f in python_files:
        # Skip test files
        if exclude_tests and any(part.startswith("test") or part == "tests" for part in f.parts):
            continue

        # Skip __init__.py files (often have simple returns)
        if f.name == "__init__.py":
            continue

        # Skip _version.py and similar metadata files
        if f.name in ("_version.py", "version.py", "__version__.py"):
            continue

        production_files.append(f)

    for py_file in production_files:
        total_files += 1
        violations = scan_file(py_file)

        if violations:
            violations_found = True
            total_violations += len(violations)

            print(f"\n{py_file}:")
            for lineno, func_name, value, value_type in violations:
                type_info = f" ({value_type})" if value_type else ""
                print(
                    f"  Line {lineno}: Function '{func_name}' returns hardcoded{type_info}: {value}"
                )

    # Print summary
    print(f"\n{'='*60}")
    print(f"Scanned {total_files} production files")
    print(f"Found {total_violations} hardcoded return value(s)")
    print(f"{'='*60}")

    return violations_found


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect hardcoded return values in production code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--fail-on-found",
        action="store_true",
        help="Exit with error code if hardcoded values are found",
    )
    parser.add_argument(
        "--file", type=Path, help="Scan a specific file instead of entire directory"
    )
    parser.add_argument("--include-tests", action="store_true", help="Include test files in scan")

    args = parser.parse_args()

    if args.file:
        # Scan single file
        violations = scan_file(args.file)

        if violations:
            print(f"\n{args.file}:")
            for lineno, func_name, value, value_type in violations:
                type_info = f" ({value_type})" if value_type else ""
                print(
                    f"  Line {lineno}: Function '{func_name}' returns hardcoded{type_info}: {value}"
                )
            print(f"\n❌ Found {len(violations)} hardcoded return value(s)")

            if args.fail_on_found:
                sys.exit(1)
            else:
                sys.exit(0)
        else:
            print(f"✅ No hardcoded return values detected in {args.file}")
            sys.exit(0)
    else:
        # Scan entire rustybt directory
        rustybt_dir = Path("rustybt")

        if not rustybt_dir.exists():
            print(f"Error: Directory 'rustybt' not found", file=sys.stderr)
            sys.exit(1)

        violations_found = scan_directory(rustybt_dir, exclude_tests=not args.include_tests)

        if violations_found:
            print("\n❌ Hardcoded return values detected in production code")
            if args.fail_on_found:
                sys.exit(1)
            else:
                sys.exit(0)
        else:
            print("\n✅ No hardcoded return values detected")
            sys.exit(0)


if __name__ == "__main__":
    main()
