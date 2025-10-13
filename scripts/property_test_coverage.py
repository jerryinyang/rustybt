#!/usr/bin/env python
"""Property test coverage analyzer.

This script analyzes property test coverage across the codebase and generates
metrics for quality gates. It ensures critical financial calculations have
adequate property-based test coverage.

Usage:
    python scripts/property_test_coverage.py --check
    python scripts/property_test_coverage.py --report
    python scripts/property_test_coverage.py --enforce-gates

Exit codes:
    0: All quality gates passed
    1: Quality gates failed (coverage below threshold)
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import ClassVar


class PropertyTestCoverageAnalyzer:
    """Analyzes property test coverage for financial calculation modules."""

    # Modules that REQUIRE property test coverage
    CRITICAL_MODULES: ClassVar[set[str]] = {
        "rustybt.finance.decimal.ledger",
        "rustybt.finance.decimal.position",
        "rustybt.finance.decimal.transaction",
        "rustybt.finance.decimal.blotter",
        "rustybt.finance.commission",
        "rustybt.finance.slippage",
        "rustybt.finance.metrics.core",
        "rustybt.data.polars.data_portal",
        "rustybt.data.polars.parquet_daily_bars",
        "rustybt.data.polars.parquet_minute_bars",
    }

    # Minimum number of property tests required per critical module
    MIN_PROPERTY_TESTS_PER_MODULE: ClassVar[dict[str, int]] = {
        "rustybt.finance.decimal.ledger": 3,
        "rustybt.finance.decimal.position": 2,
        "rustybt.finance.decimal.transaction": 2,
        "rustybt.finance.decimal.blotter": 2,
        "rustybt.finance.commission": 1,
        "rustybt.finance.slippage": 1,
        "rustybt.finance.metrics.core": 3,
        "rustybt.data.polars.data_portal": 2,
        "rustybt.data.polars.parquet_daily_bars": 1,
        "rustybt.data.polars.parquet_minute_bars": 1,
    }

    # Property types that should be tested
    REQUIRED_PROPERTY_TYPES: ClassVar[set[str]] = {
        "invariant",  # e.g., portfolio_value = sum(positions) + cash
        "reconstruction",  # e.g., (1 + return) * start = end
        "bounds",  # e.g., commission >= 0, drawdown in [-1, 0]
        "associativity",  # e.g., (a + b) + c == a + (b + c)
        "commutativity",  # e.g., a + b == b + a
        "idempotence",  # e.g., f(f(x)) == f(x)
    }

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.property_tests_dir = project_root / "tests" / "property_tests"
        self.source_dir = project_root / "rustybt"

    def find_property_tests(self) -> dict[str, list[str]]:
        """Find all property tests and the modules they test.

        Returns:
            Dict mapping module names to list of property test names
        """
        module_tests = {}

        for test_file in self.property_tests_dir.glob("test_*.py"):
            if test_file.name == "test_performance_benchmarks.py":
                continue  # Skip benchmark tests

            with open(test_file) as f:
                tree = ast.parse(f.read(), filename=str(test_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    # Check if it's a property test (has @given decorator)
                    has_given = any(
                        (isinstance(dec, ast.Name) and dec.id == "given")
                        or (
                            isinstance(dec, ast.Call)
                            and isinstance(dec.func, ast.Name)
                            and dec.func.id == "given"
                        )
                        for dec in node.decorator_list
                    )

                    if has_given:
                        # Extract tested module from imports
                        tested_modules = self._extract_tested_modules(tree)
                        for module in tested_modules:
                            if module not in module_tests:
                                module_tests[module] = []
                            module_tests[module].append(f"{test_file.stem}::{node.name}")

        return module_tests

    def _extract_tested_modules(self, tree: ast.AST) -> set[str]:
        """Extract module names being tested from import statements."""
        modules = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if (node.module and node.module.startswith("rustybt.finance")) or (
                    node.module and node.module.startswith("rustybt.data")
                ):
                    modules.add(node.module)

        return modules

    def count_property_tests(self) -> int:
        """Count total number of property tests."""
        count = 0
        for test_file in self.property_tests_dir.glob("test_*.py"):
            if test_file.name == "test_performance_benchmarks.py":
                continue

            with open(test_file) as f:
                tree = ast.parse(f.read(), filename=str(test_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    has_given = any(
                        (isinstance(dec, ast.Name) and dec.id == "given")
                        or (
                            isinstance(dec, ast.Call)
                            and isinstance(dec.func, ast.Name)
                            and dec.func.id == "given"
                        )
                        for dec in node.decorator_list
                    )
                    if has_given:
                        count += 1

        return count

    def count_regression_tests(self) -> int:
        """Count number of regression tests from shrunk examples."""
        regression_file = self.property_tests_dir / "test_regression_examples.py"
        if not regression_file.exists():
            return 0

        with open(regression_file) as f:
            tree = ast.parse(f.read(), filename=str(regression_file))

        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_regression_"):
                count += 1

        return count

    def check_coverage(self) -> dict[str, any]:
        """Check property test coverage against quality gates.

        Returns:
            Dict with coverage metrics and pass/fail status
        """
        module_tests = self.find_property_tests()
        total_tests = self.count_property_tests()
        regression_tests = self.count_regression_tests()

        # Check coverage for critical modules
        missing_coverage = []
        insufficient_coverage = []

        for module in self.CRITICAL_MODULES:
            test_count = len(module_tests.get(module, []))
            required_count = self.MIN_PROPERTY_TESTS_PER_MODULE.get(module, 1)

            if test_count == 0:
                missing_coverage.append(module)
            elif test_count < required_count:
                insufficient_coverage.append((module, test_count, required_count))

        # Calculate coverage metrics
        covered_modules = len(
            [m for m in self.CRITICAL_MODULES if m in module_tests and len(module_tests[m]) > 0]
        )
        coverage_percentage = (
            (covered_modules / len(self.CRITICAL_MODULES)) * 100 if self.CRITICAL_MODULES else 0
        )

        passed = len(missing_coverage) == 0 and len(insufficient_coverage) == 0

        return {
            "passed": passed,
            "total_property_tests": total_tests,
            "regression_tests": regression_tests,
            "critical_modules": len(self.CRITICAL_MODULES),
            "covered_modules": covered_modules,
            "coverage_percentage": coverage_percentage,
            "missing_coverage": missing_coverage,
            "insufficient_coverage": insufficient_coverage,
            "module_tests": module_tests,
        }

    def generate_report(self, results: dict[str, any]) -> str:
        """Generate human-readable coverage report.

        Args:
            results: Results from check_coverage()

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("PROPERTY TEST COVERAGE REPORT")
        report.append("=" * 80)
        report.append("")

        # Summary
        report.append("SUMMARY")
        report.append("-" * 80)
        report.append(f"Total Property Tests: {results['total_property_tests']}")
        report.append(f"Regression Tests: {results['regression_tests']}")
        report.append(
            f"Critical Modules Covered: {results['covered_modules']}/{results['critical_modules']} "
            f"({results['coverage_percentage']:.1f}%)"
        )
        report.append("")

        # Status
        status = "✅ PASS" if results["passed"] else "❌ FAIL"
        report.append(f"Status: {status}")
        report.append("")

        # Missing coverage
        if results["missing_coverage"]:
            report.append("MISSING COVERAGE (0 property tests)")
            report.append("-" * 80)
            for module in results["missing_coverage"]:
                report.append(f"  ❌ {module}")
            report.append("")

        # Insufficient coverage
        if results["insufficient_coverage"]:
            report.append("INSUFFICIENT COVERAGE")
            report.append("-" * 80)
            for module, actual, required in results["insufficient_coverage"]:
                report.append(f"  ⚠️  {module}: {actual}/{required} tests")
            report.append("")

        # Module coverage details
        report.append("MODULE COVERAGE DETAILS")
        report.append("-" * 80)
        for module in sorted(self.CRITICAL_MODULES):
            tests = results["module_tests"].get(module, [])
            required = self.MIN_PROPERTY_TESTS_PER_MODULE.get(module, 1)
            status_symbol = "✅" if len(tests) >= required else "❌"

            report.append(f"{status_symbol} {module} ({len(tests)}/{required} tests)")
            for test in tests:
                report.append(f"     - {test}")
            report.append("")

        report.append("=" * 80)
        return "\n".join(report)

    def enforce_quality_gates(self, results: dict[str, any]) -> bool:
        """Enforce quality gates for CI/CD.

        Quality Gates:
        1. All critical modules must have >= minimum property tests
        2. Total property tests >= 30
        3. Regression tests >= 5
        4. Coverage >= 90%

        Args:
            results: Results from check_coverage()

        Returns:
            True if all gates pass, False otherwise
        """
        gates_passed = True

        # Gate 1: All critical modules covered
        if results["missing_coverage"]:
            print("❌ Gate 1 FAILED: Missing coverage for critical modules")
            gates_passed = False
        else:
            print("✅ Gate 1 PASSED: All critical modules have property tests")

        # Gate 2: Sufficient coverage per module
        if results["insufficient_coverage"]:
            print("❌ Gate 2 FAILED: Insufficient tests for some modules")
            gates_passed = False
        else:
            print("✅ Gate 2 PASSED: All modules meet minimum test requirements")

        # Gate 3: Total property tests
        if results["total_property_tests"] < 30:
            print(
                f"❌ Gate 3 FAILED: Total property tests ({results['total_property_tests']}) < 30"
            )
            gates_passed = False
        else:
            print(
                f"✅ Gate 3 PASSED: Total property tests ({results['total_property_tests']}) >= 30"
            )

        # Gate 4: Regression tests
        if results["regression_tests"] < 5:
            print(
                f"⚠️  Gate 4 WARNING: Regression tests ({results['regression_tests']}) < 5 (recommended)"
            )
            # Not a hard failure
        else:
            print(f"✅ Gate 4 PASSED: Regression tests ({results['regression_tests']}) >= 5")

        # Gate 5: Coverage percentage
        if results["coverage_percentage"] < 90.0:
            print(f"❌ Gate 5 FAILED: Coverage ({results['coverage_percentage']:.1f}%) < 90%")
            gates_passed = False
        else:
            print(f"✅ Gate 5 PASSED: Coverage ({results['coverage_percentage']:.1f}%) >= 90%")

        return gates_passed


def main():
    parser = argparse.ArgumentParser(
        description="Analyze property test coverage and enforce quality gates"
    )
    parser.add_argument("--check", action="store_true", help="Check coverage and print summary")
    parser.add_argument("--report", action="store_true", help="Generate detailed coverage report")
    parser.add_argument(
        "--enforce-gates",
        action="store_true",
        help="Enforce quality gates (exits with code 1 if failed)",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Default to check if no args provided
    if not (args.check or args.report or args.enforce_gates):
        args.check = True

    # Find project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    analyzer = PropertyTestCoverageAnalyzer(project_root)
    results = analyzer.check_coverage()

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    if args.report:
        report = analyzer.generate_report(results)
        print(report)

    if args.check:
        print(f"Property Test Coverage: {results['coverage_percentage']:.1f}%")
        print(f"Total Property Tests: {results['total_property_tests']}")
        print(f"Regression Tests: {results['regression_tests']}")
        print(f"Status: {'PASS' if results['passed'] else 'FAIL'}")

    if args.enforce_gates:
        print("\nEnforcing Quality Gates...")
        print("=" * 80)
        gates_passed = analyzer.enforce_quality_gates(results)
        print("=" * 80)

        if not gates_passed:
            print("\n❌ Quality gates FAILED")
            return 1
        else:
            print("\n✅ All quality gates PASSED")
            return 0

    return 0 if results["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
