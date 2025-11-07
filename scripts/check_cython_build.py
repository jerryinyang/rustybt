#!/usr/bin/env python3
"""Pre-commit hook to detect stale Cython extensions.

This script ensures that all Cython source files (.pyx) have corresponding
compiled extensions (.so, .pyd) that are up-to-date.

This prevents the bug where code changes in .pyx files don't take effect
because the compiled extensions weren't rebuilt.

Exit codes:
    0: All Cython extensions are up-to-date
    1: Some Cython extensions are stale or missing
"""

import sys
from pathlib import Path
from typing import List, Tuple


def find_cython_files(root: Path) -> List[Path]:
    """Find all .pyx files in the repository.

    Args:
        root: Root directory to search from

    Returns:
        List of paths to .pyx files
    """
    # Search in rustybt package only (exclude tests, docs, etc.)
    cython_files = []

    for pyx_file in root.rglob("*.pyx"):
        # Skip files in build, dist, .venv, etc.
        if any(
            part in pyx_file.parts for part in [".venv", "build", "dist", ".eggs", "__pycache__"]
        ):
            continue
        cython_files.append(pyx_file)

    return sorted(cython_files)


def get_compiled_extension_path(pyx_file: Path) -> Path:
    """Get the expected path for the compiled extension.

    For rustybt/_protocol.pyx, the compiled extension is:
    - Linux: rustybt/_protocol.cpython-312-x86_64-linux-gnu.so
    - macOS: rustybt/_protocol.cpython-312-darwin.so
    - Windows: rustybt/_protocol.cp312-win_amd64.pyd

    Args:
        pyx_file: Path to .pyx source file

    Returns:
        Path to expected compiled extension (may not exist)
    """
    # Get the module name (without .pyx extension)
    module_stem = pyx_file.stem
    parent_dir = pyx_file.parent

    # Find any .so or .pyd file that matches the module name
    # Pattern: <module>.cpython-*.so or <module>.cp*.pyd
    for ext_file in parent_dir.glob(f"{module_stem}.cpython-*"):
        if ext_file.suffix in [".so", ".pyd"]:
            return ext_file

    # If not found, return the expected path (won't exist)
    # Use generic pattern that works cross-platform
    return parent_dir / f"{module_stem}.cpython-312.so"


def check_cython_extensions(root: Path) -> Tuple[List[str], List[str]]:
    """Check all Cython extensions for staleness.

    Args:
        root: Root directory of the repository

    Returns:
        Tuple of (stale_files, missing_files) with error messages
    """
    cython_files = find_cython_files(root)

    if not cython_files:
        # No Cython files found - this is fine
        return [], []

    stale_files = []
    missing_files = []

    for pyx_file in cython_files:
        ext_file = get_compiled_extension_path(pyx_file)

        if not ext_file.exists():
            missing_files.append(
                f"  ❌ {pyx_file.relative_to(root)}\n"
                f"     Missing compiled extension: {ext_file.name}\n"
            )
            continue

        # Check if .so is older than .pyx
        pyx_mtime = pyx_file.stat().st_mtime
        ext_mtime = ext_file.stat().st_mtime

        if ext_mtime < pyx_mtime:
            pyx_time_str = pyx_file.stat().st_mtime
            ext_time_str = ext_file.stat().st_mtime

            from datetime import datetime

            pyx_dt = datetime.fromtimestamp(pyx_mtime)
            ext_dt = datetime.fromtimestamp(ext_mtime)

            stale_files.append(
                f"  ❌ {pyx_file.relative_to(root)}\n"
                f"     Source modified: {pyx_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"     Extension built: {ext_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"     Extension is {(pyx_mtime - ext_mtime) / 60:.1f} minutes older\n"
            )

    return stale_files, missing_files


def main() -> int:
    """Main entry point for the pre-commit hook.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Find the repository root (where .git directory is)
    current_dir = Path.cwd()
    root = current_dir

    # Look for .git directory to find repo root
    while root != root.parent:
        if (root / ".git").exists():
            break
        root = root.parent
    else:
        # If we can't find .git, assume current directory is root
        root = current_dir

    stale_files, missing_files = check_cython_extensions(root)

    if not stale_files and not missing_files:
        print("✅ All Cython extensions are up-to-date")
        return 0

    # Print errors
    print("\n" + "=" * 70)
    print("🚨 CYTHON EXTENSIONS ARE STALE OR MISSING")
    print("=" * 70)

    if stale_files:
        print("\n📋 Stale extensions (source newer than compiled):")
        for msg in stale_files:
            print(msg)

    if missing_files:
        print("\n📋 Missing extensions (not compiled):")
        for msg in missing_files:
            print(msg)

    print("\n" + "=" * 70)
    print("🔧 FIX: Recompile Cython extensions before committing:")
    print("=" * 70)
    print()
    print("  python setup.py build_ext --inplace")
    print()
    print("Then stage the updated .so/.pyd files:")
    print()
    print("  git add rustybt/**/*.so")
    print()
    print("=" * 70)
    print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
