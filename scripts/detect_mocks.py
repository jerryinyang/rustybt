#!/usr/bin/env python3
"""
Mock Detection Script for Zero-Mock Enforcement

Scans Python files for mock patterns in function/variable names and identifies
suspicious implementations that don't belong in production code.

Detection Patterns:
1. Function/variable names containing: mock, fake, stub, dummy, placeholder
2. Class names inheriting from Mock-like classes
3. Import statements with mock libraries in production code

Usage:
    python scripts/detect_mocks.py                  # Scan all rustybt/ files
    python scripts/detect_mocks.py --quick          # Quick scan (for pre-commit)
    python scripts/detect_mocks.py --strict         # Strict scan (for CI)
    python scripts/detect_mocks.py --file FILE      # Scan specific file
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Tuple


class MockDetector(ast.NodeVisitor):
    """AST visitor that detects mock patterns in Python code."""

    def __init__(self, strict: bool = False):
        self.violations: List[Tuple[int, str]] = []
        self.mock_keywords = ["mock", "fake", "stub", "dummy", "placeholder"]
        self.strict = strict

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Check function names for mock patterns."""
        func_name_lower = node.name.lower()

        # Check if function name contains mock keywords
        for keyword in self.mock_keywords:
            if keyword in func_name_lower:
                self.violations.append(
                    (
                        node.lineno,
                        f"Mock function name detected: '{node.name}' (contains '{keyword}')",
                    )
                )
                break

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Check async function names for mock patterns."""
        func_name_lower = node.name.lower()

        for keyword in self.mock_keywords:
            if keyword in func_name_lower:
                self.violations.append(
                    (
                        node.lineno,
                        f"Mock async function name detected: '{node.name}' (contains '{keyword}')",
                    )
                )
                break

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Check class names for mock patterns."""
        class_name_lower = node.name.lower()

        # Check if class name contains mock keywords
        for keyword in self.mock_keywords:
            if keyword in class_name_lower:
                self.violations.append(
                    (node.lineno, f"Mock class name detected: '{node.name}' (contains '{keyword}')")
                )
                break

        # Check if class inherits from Mock-like base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name_lower = base.id.lower()
                if "mock" in base_name_lower:
                    self.violations.append(
                        (
                            node.lineno,
                            f"Class '{node.name}' inherits from mock-like base: '{base.id}'",
                        )
                    )

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Check for mock imports in production code."""
        for alias in node.names:
            module_name = alias.name.lower()

            # Detect unittest.mock or mock imports
            if "mock" in module_name or module_name == "unittest.mock":
                self.violations.append((node.lineno, f"Mock import detected: '{alias.name}'"))

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Check for mock imports from modules."""
        if node.module:
            module_name_lower = node.module.lower()

            # Detect imports from unittest.mock or mock modules
            if "mock" in module_name_lower:
                imported_names = ", ".join(alias.name for alias in node.names)
                self.violations.append(
                    (
                        node.lineno,
                        f"Mock import detected: 'from {node.module} import {imported_names}'",
                    )
                )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """Check variable names for mock patterns (in strict mode)."""
        if self.strict:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name_lower = target.id.lower()

                    for keyword in self.mock_keywords:
                        if keyword in var_name_lower:
                            self.violations.append(
                                (
                                    node.lineno,
                                    f"Mock variable name detected: '{target.id}' (contains '{keyword}')",
                                )
                            )
                            break

        self.generic_visit(node)


def scan_file(filepath: Path, strict: bool = False) -> List[Tuple[int, str]]:
    """
    Scan a single Python file for mock patterns.

    Args:
        filepath: Path to the Python file to scan
        strict: Enable strict mode (checks variable names too)

    Returns:
        List of (line_number, violation_message) tuples
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

    detector = MockDetector(strict=strict)
    detector.visit(tree)
    return detector.violations


def scan_directory(directory: Path, strict: bool = False, quick: bool = False) -> bool:
    """
    Scan all Python files in a directory for mock patterns.

    Args:
        directory: Path to directory to scan
        strict: Enable strict mode
        quick: Quick mode (scan only recently modified files)

    Returns:
        True if violations found, False otherwise
    """
    violations_found = False
    total_files = 0
    total_violations = 0

    # Find all Python files
    python_files = list(directory.rglob("*.py"))

    # Filter out test files (tests are allowed to use mocks)
    production_files = [
        f for f in python_files if not any(part.startswith("test") for part in f.parts)
    ]

    if quick:
        # In quick mode, only scan __init__.py and recently modified files
        production_files = [
            f
            for f in production_files
            if f.name == "__init__.py"
            or f.stat().st_mtime > (Path.cwd() / ".git" / "index").stat().st_mtime
        ]

    for py_file in production_files:
        total_files += 1
        violations = scan_file(py_file, strict=strict)

        if violations:
            violations_found = True
            total_violations += len(violations)

            print(f"\n{py_file}:")
            for lineno, msg in violations:
                print(f"  Line {lineno}: {msg}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"Scanned {total_files} production files")
    print(f"Found {total_violations} mock pattern violation(s)")
    print(f"{'='*60}")

    return violations_found


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Detect mock patterns in production code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--quick", action="store_true", help="Quick scan mode (for pre-commit hooks)"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Strict mode (also checks variable names)"
    )
    parser.add_argument(
        "--file", type=Path, help="Scan a specific file instead of entire directory"
    )

    args = parser.parse_args()

    if args.file:
        # Scan single file
        violations = scan_file(args.file, strict=args.strict)

        if violations:
            print(f"\n{args.file}:")
            for lineno, msg in violations:
                print(f"  Line {lineno}: {msg}")
            print(f"\n❌ Found {len(violations)} mock pattern violation(s)")
            sys.exit(1)
        else:
            print(f"✅ No mock patterns detected in {args.file}")
            sys.exit(0)
    else:
        # Scan entire rustybt directory
        rustybt_dir = Path("rustybt")

        if not rustybt_dir.exists():
            print(f"Error: Directory 'rustybt' not found", file=sys.stderr)
            sys.exit(1)

        violations_found = scan_directory(rustybt_dir, strict=args.strict, quick=args.quick)

        if violations_found:
            print("\n❌ Mock patterns detected in production code")
            sys.exit(1)
        else:
            print("\n✅ No mock patterns detected")
            sys.exit(0)


if __name__ == "__main__":
    main()
