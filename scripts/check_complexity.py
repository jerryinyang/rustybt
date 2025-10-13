#!/usr/bin/env python3
"""Check McCabe cyclomatic complexity of Python files.

This script uses radon to measure cyclomatic complexity and ensures
all functions stay below the configured threshold (default: 10).

Exit codes:
    0: All functions meet complexity requirements
    1: One or more functions exceed complexity threshold
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

try:
    from radon.cli import Config
    from radon.complexity import cc_visit
except ImportError:
    print("Error: radon not installed. Install with: pip install radon")
    sys.exit(1)


def check_complexity(
    path: Path, max_complexity: int = 10, exclude_patterns: List[str] = None
) -> List[Tuple[str, str, int]]:
    """Check cyclomatic complexity of Python files.

    Args:
        path: Path to check (file or directory)
        max_complexity: Maximum allowed complexity (default: 10)
        exclude_patterns: List of patterns to exclude (default: tests/, examples/)

    Returns:
        List of (filepath, function_name, complexity) tuples that exceed threshold
    """
    if exclude_patterns is None:
        exclude_patterns = ["tests/", "examples/", ".venv/", "venv/", "__pycache__/"]

    violations = []

    if path.is_file():
        files = [path]
    else:
        files = path.rglob("*.py")

    for file_path in files:
        # Skip excluded patterns
        if any(pattern in str(file_path) for pattern in exclude_patterns):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            # Calculate complexity for all code blocks
            results = cc_visit(code)

            for result in results:
                if result.complexity > max_complexity:
                    violations.append((str(file_path), result.fullname, result.complexity))

        except Exception as e:
            print(f"Warning: Failed to analyze {file_path}: {e}", file=sys.stderr)

    return violations


def main():
    parser = argparse.ArgumentParser(
        description="Check McCabe cyclomatic complexity of Python code"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="rustybt",
        help="Path to check (default: rustybt)",
    )
    parser.add_argument(
        "--max-complexity",
        type=int,
        default=10,
        help="Maximum allowed complexity (default: 10)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=None,
        help="Additional patterns to exclude",
    )

    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path {path} does not exist", file=sys.stderr)
        sys.exit(1)

    exclude_patterns = ["tests/", "examples/", ".venv/", "venv/", "__pycache__/"]
    if args.exclude:
        exclude_patterns.extend(args.exclude)

    print(f"Checking cyclomatic complexity in {path}...")
    print(f"Maximum complexity threshold: {args.max_complexity}")
    print(f"Excluding patterns: {', '.join(exclude_patterns)}")
    print()

    violations = check_complexity(path, args.max_complexity, exclude_patterns)

    if violations:
        print(f"❌ Found {len(violations)} complexity violations:\n")
        for filepath, func_name, complexity in sorted(violations, key=lambda x: x[2], reverse=True):
            print(f"  {filepath}")
            print(f"    Function: {func_name}")
            print(f"    Complexity: {complexity} (threshold: {args.max_complexity})")
            print()

        print(f"Refactor these functions to reduce complexity below {args.max_complexity}")
        sys.exit(1)
    else:
        print(f"✅ All functions meet complexity threshold (≤{args.max_complexity})")
        sys.exit(0)


if __name__ == "__main__":
    main()
