#!/usr/bin/env python
"""
Automated verification script for RustyBT API documentation.

This script:
1. Parses all markdown files in docs/api/
2. Extracts Python imports and class/function references
3. Verifies each API actually exists in the rustybt package
4. Generates a verification report

Created for Story 10.X1: Audit and Remediate Epic 10 Fabricated APIs
"""

import ast
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Adjust path to find rustybt module
sys.path.insert(0, str(Path(__file__).parent.parent))


def extract_python_blocks(markdown_file: Path) -> List[str]:
    """Extract Python code blocks from a markdown file."""
    with open(markdown_file, "r") as f:
        content = f.read()

    # Find all ```python code blocks
    pattern = r"```python\n(.*?)\n```"
    code_blocks = re.findall(pattern, content, re.DOTALL)

    return code_blocks


def extract_imports_from_code(code: str) -> Set[str]:
    """Extract import statements from Python code."""
    imports = set()

    # Parse line by line to handle various import formats
    for line in code.split("\n"):
        line = line.strip()

        # Match: from rustybt.xxx import yyy
        match = re.match(r"^from\s+(rustybt[\w.]*)\s+import\s+(.+)", line)
        if match:
            module = match.group(1)
            items = match.group(2)

            # Handle multiple imports: Class1, Class2, Class3
            items = [item.strip() for item in items.split(",")]

            # Handle parenthesized imports
            if "(" in items[0]:
                # Continue reading until we find the closing parenthesis
                continue

            for item in items:
                # Remove 'as' aliases
                if " as " in item:
                    item = item.split(" as ")[0].strip()
                imports.add(f"{module}.{item}")

        # Match: import rustybt.xxx
        elif line.startswith("import rustybt"):
            match = re.match(r"^import\s+(rustybt[\w.]*)", line)
            if match:
                imports.add(match.group(1))

    return imports


def verify_import(import_path: str) -> Tuple[bool, str]:
    """
    Verify if an import actually exists.

    Returns:
        (exists, details) - exists is True if import works, details provides info
    """
    try:
        # Split module and item (if any)
        parts = import_path.split(".")

        # Try to import the module
        if len(parts) > 2:
            # e.g., rustybt.finance.execution.MarketOrder
            module_path = ".".join(parts[:-1])
            item_name = parts[-1]

            try:
                module = importlib.import_module(module_path)
                if hasattr(module, item_name):
                    return True, f"✅ Found: {item_name} in {module_path}"
                else:
                    return False, f"❌ Not found: {item_name} not in {module_path}"
            except ImportError as e:
                return False, f"❌ Module not found: {module_path}"
        else:
            # Just a module import
            try:
                importlib.import_module(import_path)
                return True, f"✅ Module exists: {import_path}"
            except ImportError:
                return False, f"❌ Module not found: {import_path}"

    except Exception as e:
        return False, f"⚠️ Error verifying: {str(e)}"


def analyze_documentation_file(md_file: Path) -> Dict:
    """Analyze a single documentation file."""
    print(f"Analyzing: {md_file}")

    results = {
        "file": str(md_file),
        "total_imports": 0,
        "verified": 0,
        "fabricated": 0,
        "errors": 0,
        "details": [],
    }

    # Extract code blocks
    code_blocks = extract_python_blocks(md_file)

    # Extract imports from all code blocks
    all_imports = set()
    for code in code_blocks:
        imports = extract_imports_from_code(code)
        all_imports.update(imports)

    # Verify each import
    for import_path in sorted(all_imports):
        exists, details = verify_import(import_path)

        results["total_imports"] += 1
        if exists:
            results["verified"] += 1
        elif "⚠️" in details:
            results["errors"] += 1
        else:
            results["fabricated"] += 1

        results["details"].append({"import": import_path, "verified": exists, "details": details})

    return results


def main():
    """Main verification process."""
    print("=" * 80)
    print("RustyBT API Documentation Verification Script")
    print("=" * 80)
    print()

    # Find all markdown files in docs/api/
    docs_path = Path(__file__).parent.parent / "docs" / "api"
    md_files = list(docs_path.rglob("*.md"))

    print(f"Found {len(md_files)} documentation files to analyze")
    print()

    # Analyze each file
    all_results = []
    total_imports = 0
    total_verified = 0
    total_fabricated = 0
    total_errors = 0

    fabricated_apis = []

    for md_file in sorted(md_files):
        result = analyze_documentation_file(md_file)
        all_results.append(result)

        total_imports += result["total_imports"]
        total_verified += result["verified"]
        total_fabricated += result["fabricated"]
        total_errors += result["errors"]

        # Collect fabricated APIs
        for detail in result["details"]:
            if not detail["verified"] and "❌" in detail["details"]:
                fabricated_apis.append(
                    {"file": str(md_file), "import": detail["import"], "details": detail["details"]}
                )

    # Print summary
    print()
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print()
    print(f"Total files analyzed: {len(md_files)}")
    print(f"Total API references: {total_imports}")
    print(f"✅ Verified APIs: {total_verified}")
    print(f"❌ Fabricated APIs: {total_fabricated}")
    print(f"⚠️ Errors: {total_errors}")
    print()

    if total_imports > 0:
        verification_rate = (total_verified / total_imports) * 100
        print(f"Verification Rate: {verification_rate:.1f}%")

        if verification_rate == 100:
            print("🎉 PERFECT! All documented APIs are verified!")
        elif verification_rate >= 90:
            print("✅ Good: Most APIs are verified, but some issues remain")
        else:
            print("❌ Issues found: Multiple fabricated APIs detected")

    # List fabricated APIs if any
    if fabricated_apis:
        print()
        print("=" * 80)
        print("FABRICATED APIS FOUND")
        print("=" * 80)
        print()

        for api in fabricated_apis:
            print(f"File: {api['file']}")
            print(f"  Import: {api['import']}")
            print(f"  Status: {api['details']}")
            print()

    # Write detailed report to JSON
    report_file = Path(__file__).parent / "api_verification_report.json"
    with open(report_file, "w") as f:
        json.dump(
            {
                "summary": {
                    "total_files": len(md_files),
                    "total_imports": total_imports,
                    "verified": total_verified,
                    "fabricated": total_fabricated,
                    "errors": total_errors,
                    "verification_rate": (
                        (total_verified / total_imports * 100) if total_imports > 0 else 0
                    ),
                },
                "fabricated_apis": fabricated_apis,
                "file_results": all_results,
            },
            f,
            indent=2,
        )

    print(f"Detailed report written to: {report_file}")

    # Exit code based on verification
    if total_fabricated == 0 and total_errors == 0:
        print()
        print("✅ SUCCESS: All documented APIs verified!")
        sys.exit(0)
    else:
        print()
        print("❌ FAILURE: Fabricated or problematic APIs found!")
        sys.exit(1)


if __name__ == "__main__":
    main()
