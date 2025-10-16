#!/usr/bin/env python
"""
Automated verification script for RustyBT API documentation.

This script:
1. Parses all markdown files in docs/api/
2. Extracts Python imports and class/function references
3. Verifies each API actually exists in the rustybt package
4. Executes code examples to verify they run without errors
5. Validates usage patterns in examples
6. Generates a comprehensive verification report

Created for Story 10.X1: Audit and Remediate Epic 10 Fabricated APIs
Enhanced for Story 11.1: Documentation Quality Framework & Reorganization
"""

import ast
import importlib
import io
import json
import re
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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


def execute_example(code: str, timeout: int = 5) -> Tuple[bool, str, Optional[str]]:
    """
    Execute a code example to verify it runs without errors.

    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds (not enforced yet)

    Returns:
        (success, message, output) - success is True if code runs without errors
    """
    # Skip examples with ellipsis (incomplete examples)
    if "..." in code:
        return True, "⊘ Skipped: Example contains ellipsis (incomplete)", None

    # Skip examples with obvious placeholders
    placeholders = ["your_api_key", "YOUR_API_KEY", "<api_key>", "todo", "TODO", "FIXME"]
    if any(placeholder in code for placeholder in placeholders):
        return True, "⊘ Skipped: Example contains placeholders", None

    # Capture stdout and stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        # Create isolated namespace for execution
        namespace = {}

        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(code, namespace)

        stdout_output = stdout_capture.getvalue()
        stderr_output = stderr_capture.getvalue()

        # Check for errors in stderr
        if stderr_output and (
            "error" in stderr_output.lower() or "exception" in stderr_output.lower()
        ):
            return False, f"⚠️ Execution produced errors: {stderr_output[:100]}", None

        return True, "✅ Example executed successfully", stdout_output if stdout_output else None

    except SyntaxError as e:
        return False, f"❌ Syntax error: {str(e)}", None
    except ImportError as e:
        return False, f"❌ Import error: {str(e)}", None
    except Exception as e:
        error_trace = traceback.format_exc()
        # Truncate long error messages
        error_msg = str(e)[:200]
        return False, f"❌ Execution failed: {error_msg}", error_trace


def validate_usage_patterns(code: str) -> Tuple[bool, List[str]]:
    """
    Validate code examples follow proper usage patterns.

    Checks for:
    - Proper imports before usage
    - Class instantiation patterns
    - Method call patterns
    - Error handling patterns
    - Resource management patterns

    Returns:
        (valid, issues) - valid is True if no issues found, issues list describes problems
    """
    issues = []

    try:
        # Parse the code into an AST
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error prevents validation: {str(e)}"]

    # Track imports
    imported_modules = set()
    imported_items = set()

    # Track defined names
    defined_names = set()

    # Check for patterns
    has_imports = False
    has_usage = False

    for node in ast.walk(tree):
        # Track imports
        if isinstance(node, ast.Import):
            has_imports = True
            for alias in node.names:
                imported_modules.add(alias.name)

        elif isinstance(node, ast.ImportFrom):
            has_imports = True
            module = node.module or ""
            for alias in node.names:
                imported_items.add(alias.name)
                imported_modules.add(f"{module}.{alias.name}" if module else alias.name)

        # Track variable assignments
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_names.add(target.id)

        # Track usage (function calls, attribute access)
        elif isinstance(node, ast.Call):
            has_usage = True

    # Validate patterns
    if has_usage and not has_imports:
        # Check if it's a snippet that assumes imports
        if "rustybt" not in code.lower() and len(code.split("\n")) < 5:
            # Likely a snippet, not a complete example - acceptable
            pass
        else:
            issues.append("⚠️ Example uses APIs but has no imports (may be incomplete snippet)")

    # Check for bare excepts (bad practice)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append("⚠️ Example uses bare except clause (bad practice)")

    # Check for common anti-patterns
    if "eval(" in code or "exec(" in code:
        issues.append("⚠️ Example uses eval/exec (security risk)")

    # All checks passed if no issues
    return len(issues) == 0, issues


def analyze_documentation_file(md_file: Path, run_examples: bool = True) -> Dict:
    """
    Analyze a single documentation file.

    Args:
        md_file: Path to markdown file
        run_examples: If True, execute code examples to verify they work

    Returns:
        Dictionary with analysis results
    """
    print(f"Analyzing: {md_file}")

    results = {
        "file": str(md_file),
        "total_imports": 0,
        "verified": 0,
        "fabricated": 0,
        "errors": 0,
        "total_examples": 0,
        "examples_executed": 0,
        "examples_passed": 0,
        "examples_failed": 0,
        "examples_skipped": 0,
        "usage_patterns_valid": 0,
        "usage_patterns_issues": 0,
        "details": [],
        "example_results": [],
        "usage_validation_results": [],
    }

    # Extract code blocks
    code_blocks = extract_python_blocks(md_file)
    results["total_examples"] = len(code_blocks)

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

    # Execute examples if requested
    if run_examples:
        for idx, code in enumerate(code_blocks):
            example_num = idx + 1

            # Execute example
            success, message, output = execute_example(code)

            if "Skipped" in message:
                results["examples_skipped"] += 1
            else:
                results["examples_executed"] += 1
                if success:
                    results["examples_passed"] += 1
                else:
                    results["examples_failed"] += 1

            results["example_results"].append(
                {
                    "example_number": example_num,
                    "success": success,
                    "message": message,
                    "output": output[:500] if output else None,  # Truncate long output
                }
            )

            # Validate usage patterns
            valid, issues = validate_usage_patterns(code)

            if valid:
                results["usage_patterns_valid"] += 1
            else:
                results["usage_patterns_issues"] += 1

            if issues:
                results["usage_validation_results"].append(
                    {
                        "example_number": example_num,
                        "valid": valid,
                        "issues": issues,
                    }
                )

    return results


def main():
    """Main verification process."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify RustyBT API documentation for accuracy and completeness"
    )
    parser.add_argument("--no-examples", action="store_true", help="Skip example execution testing")
    parser.add_argument(
        "--docs-path",
        type=Path,
        default=None,
        help="Path to documentation directory (default: docs/api/)",
    )
    args = parser.parse_args()

    run_examples = not args.no_examples

    print("=" * 80)
    print("RustyBT API Documentation Verification Script")
    print("=" * 80)
    print()
    print(f"Example execution: {'Enabled' if run_examples else 'Disabled'}")
    print()

    # Find all markdown files in docs/api/
    if args.docs_path:
        docs_path = args.docs_path
    else:
        docs_path = Path(__file__).parent.parent / "docs" / "api"

    if not docs_path.exists():
        print(f"⚠️ Documentation path does not exist: {docs_path}")
        print("This may be expected if documentation has not been created yet.")
        sys.exit(0)

    md_files = list(docs_path.rglob("*.md"))

    if not md_files:
        print(f"⚠️ No markdown files found in: {docs_path}")
        print("This may be expected if documentation has not been created yet.")
        sys.exit(0)

    print(f"Found {len(md_files)} documentation files to analyze")
    print()

    # Analyze each file
    all_results = []
    total_imports = 0
    total_verified = 0
    total_fabricated = 0
    total_errors = 0
    total_examples = 0
    total_examples_executed = 0
    total_examples_passed = 0
    total_examples_failed = 0
    total_examples_skipped = 0
    total_usage_valid = 0
    total_usage_issues = 0

    fabricated_apis = []
    failed_examples = []
    usage_issues = []

    for md_file in sorted(md_files):
        result = analyze_documentation_file(md_file, run_examples=run_examples)
        all_results.append(result)

        total_imports += result["total_imports"]
        total_verified += result["verified"]
        total_fabricated += result["fabricated"]
        total_errors += result["errors"]
        total_examples += result["total_examples"]
        total_examples_executed += result["examples_executed"]
        total_examples_passed += result["examples_passed"]
        total_examples_failed += result["examples_failed"]
        total_examples_skipped += result["examples_skipped"]
        total_usage_valid += result["usage_patterns_valid"]
        total_usage_issues += result["usage_patterns_issues"]

        # Collect fabricated APIs
        for detail in result["details"]:
            if not detail["verified"] and "❌" in detail["details"]:
                fabricated_apis.append(
                    {"file": str(md_file), "import": detail["import"], "details": detail["details"]}
                )

        # Collect failed examples
        for example_result in result["example_results"]:
            if not example_result["success"] and "Skipped" not in example_result["message"]:
                failed_examples.append(
                    {
                        "file": str(md_file),
                        "example_number": example_result["example_number"],
                        "message": example_result["message"],
                    }
                )

        # Collect usage issues
        for usage_result in result["usage_validation_results"]:
            if not usage_result["valid"]:
                usage_issues.append(
                    {
                        "file": str(md_file),
                        "example_number": usage_result["example_number"],
                        "issues": usage_result["issues"],
                    }
                )

    # Print summary
    print()
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print()
    print(f"Total files analyzed: {len(md_files)}")
    print()
    print("API Import Verification:")
    print(f"  Total API references: {total_imports}")
    print(f"  ✅ Verified APIs: {total_verified}")
    print(f"  ❌ Fabricated APIs: {total_fabricated}")
    print(f"  ⚠️ Errors: {total_errors}")

    if run_examples:
        print()
        print("Example Execution:")
        print(f"  Total examples: {total_examples}")
        print(f"  ✅ Passed: {total_examples_passed}")
        print(f"  ❌ Failed: {total_examples_failed}")
        print(f"  ⊘ Skipped: {total_examples_skipped}")
        print()
        print("Usage Pattern Validation:")
        print(f"  ✅ Valid patterns: {total_usage_valid}")
        print(f"  ⚠️ Issues found: {total_usage_issues}")

    print()

    if total_imports > 0:
        verification_rate = (total_verified / total_imports) * 100
        print(f"API Verification Rate: {verification_rate:.1f}%")

        if verification_rate == 100:
            print("🎉 PERFECT! All documented APIs are verified!")
        elif verification_rate >= 90:
            print("✅ Good: Most APIs are verified, but some issues remain")
        else:
            print("❌ Issues found: Multiple fabricated APIs detected")

    if run_examples and total_examples_executed > 0:
        execution_rate = (total_examples_passed / total_examples_executed) * 100
        print(f"Example Execution Rate: {execution_rate:.1f}%")

        if execution_rate == 100:
            print("🎉 PERFECT! All examples execute successfully!")
        elif execution_rate >= 90:
            print("✅ Good: Most examples work, but some issues remain")
        else:
            print("❌ Issues found: Multiple examples fail to execute")

    # List fabricated APIs if any
    if fabricated_apis:
        print()
        print("=" * 80)
        print("FABRICATED APIS FOUND")
        print("=" * 80)
        print()

        for api in fabricated_apis[:10]:  # Show first 10
            print(f"File: {api['file']}")
            print(f"  Import: {api['import']}")
            print(f"  Status: {api['details']}")
            print()

        if len(fabricated_apis) > 10:
            print(f"... and {len(fabricated_apis) - 10} more (see JSON report)")
            print()

    # List failed examples if any
    if failed_examples:
        print()
        print("=" * 80)
        print("FAILED EXAMPLES")
        print("=" * 80)
        print()

        for example in failed_examples[:10]:  # Show first 10
            print(f"File: {example['file']}")
            print(f"  Example #{example['example_number']}")
            print(f"  Error: {example['message']}")
            print()

        if len(failed_examples) > 10:
            print(f"... and {len(failed_examples) - 10} more (see JSON report)")
            print()

    # List usage issues if any
    if usage_issues:
        print()
        print("=" * 80)
        print("USAGE PATTERN ISSUES")
        print("=" * 80)
        print()

        for issue in usage_issues[:10]:  # Show first 10
            print(f"File: {issue['file']}")
            print(f"  Example #{issue['example_number']}")
            for issue_msg in issue["issues"]:
                print(f"    {issue_msg}")
            print()

        if len(usage_issues) > 10:
            print(f"... and {len(usage_issues) - 10} more (see JSON report)")
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
                    "total_examples": total_examples,
                    "examples_executed": total_examples_executed,
                    "examples_passed": total_examples_passed,
                    "examples_failed": total_examples_failed,
                    "examples_skipped": total_examples_skipped,
                    "execution_rate": (
                        (total_examples_passed / total_examples_executed * 100)
                        if total_examples_executed > 0
                        else 0
                    ),
                    "usage_patterns_valid": total_usage_valid,
                    "usage_patterns_issues": total_usage_issues,
                },
                "fabricated_apis": fabricated_apis,
                "failed_examples": failed_examples,
                "usage_issues": usage_issues,
                "file_results": all_results,
            },
            f,
            indent=2,
        )

    print(f"Detailed report written to: {report_file}")

    # Exit code based on verification
    has_critical_issues = total_fabricated > 0 or total_errors > 0
    has_example_failures = run_examples and total_examples_failed > 0

    if has_critical_issues or has_example_failures:
        print()
        print("❌ FAILURE: Issues found in documentation!")
        if has_critical_issues:
            print("  - Fabricated or problematic APIs detected")
        if has_example_failures:
            print("  - Examples failed to execute")
        sys.exit(1)
    else:
        print()
        print("✅ SUCCESS: All documented APIs and examples verified!")
        sys.exit(0)


if __name__ == "__main__":
    main()
