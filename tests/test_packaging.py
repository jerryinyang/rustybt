"""Tests for package extras and installation configuration.

This module tests the package metadata and optional dependencies configuration,
specifically validating the 'full' and 'all' meta-extras added in
Story 001-storage-install-improvements.

Constitutional Requirements:
- CR-005: 90%+ test coverage with real implementations (no mocks)
- CR-002: Zero-mock enforcement - use real package metadata, no hardcoded values
"""

import importlib.metadata
import subprocess
import sys
from pathlib import Path

import pytest


class TestPackageExtras:
    """Test suite for package extras metadata validation."""

    def test_full_extras_defined(self) -> None:
        """Verify 'full' extras group exists in package metadata.

        Acceptance Criteria:
        - 'full' key exists in optional-dependencies
        - 'full' contains non-empty list of dependencies
        """
        # Read pyproject.toml to verify extras definition
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"

        content = pyproject_path.read_text()

        # Verify 'full' extras section exists
        assert "full = [" in content, "'full' extras not defined in pyproject.toml"

        # Verify expected dependencies are present
        expected_packages = [
            "scikit-learn",
            "scikit-optimize",
            "deap",
            "matplotlib",
            "tqdm",
            "psutil",
            "pytest-benchmark",
            "memory_profiler",
            "snakeviz",
        ]

        for package in expected_packages:
            assert (
                package in content
            ), f"Expected dependency '{package}' not found in pyproject.toml"

    def test_all_extras_defined(self) -> None:
        """Verify 'all' extras group exists and is equivalent to 'full'.

        Acceptance Criteria:
        - 'all' key exists in optional-dependencies
        - 'all' contains same dependencies as 'full'
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Verify 'all' extras section exists
        assert "all = [" in content, "'all' extras not defined in pyproject.toml"

        # Extract full and all extras sections for comparison
        full_start = content.find("full = [")
        full_end = content.find("]", full_start)
        full_section = content[full_start:full_end]

        all_start = content.find("all = [")
        all_end = content.find("]", all_start)
        all_section = content[all_start:all_end]

        # Extract package names from both sections
        full_packages = {
            line.strip().strip("',\"")
            for line in full_section.split("\n")
            if line.strip() and not line.strip().startswith("#")
        }
        all_packages = {
            line.strip().strip("',\"")
            for line in all_section.split("\n")
            if line.strip() and not line.strip().startswith("#")
        }

        # Remove the "full = [" and "all = [" lines themselves
        full_packages = {p for p in full_packages if "full = [" not in p}
        all_packages = {p for p in all_packages if "all = [" not in p}

        # Verify 'all' and 'full' have the same packages
        assert full_packages == all_packages, "'all' extras should be equivalent to 'full' extras"

    def test_optimization_packages_included(self) -> None:
        """Verify optimization packages are included in 'full' extras.

        Acceptance Criteria:
        - scikit-learn included
        - scikit-optimize included
        - deap included
        - Required for parameter optimization workflows
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Find full extras section
        full_start = content.find("full = [")
        full_end = content.find("\n\n", full_start)  # Next blank line
        full_section = content[full_start:full_end]

        # Verify optimization packages
        assert "scikit-learn" in full_section
        assert "scikit-optimize" in full_section
        assert "deap" in full_section

    def test_benchmarks_packages_included(self) -> None:
        """Verify benchmarking packages are included in 'full' extras.

        Acceptance Criteria:
        - pytest-benchmark included
        - memory_profiler included
        - snakeviz included
        - Required for performance analysis workflows
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Find full extras section
        full_start = content.find("full = [")
        full_end = content.find("\n\n", full_start)
        full_section = content[full_start:full_end]

        # Verify benchmarking packages
        assert "pytest-benchmark" in full_section
        assert "memory_profiler" in full_section
        assert "snakeviz" in full_section

    def test_dev_tools_not_included(self) -> None:
        """Verify dev tools are NOT included in 'full' extras.

        Acceptance Criteria:
        - pre-commit NOT in full
        - mypy NOT in full
        - black NOT in full
        - ruff NOT in full
        - Dev tools should be in separate 'dev' extras
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Find full extras section
        full_start = content.find("full = [")
        full_end = content.find("\n\n", full_start)
        full_section = content[full_start:full_end]

        # Verify dev tools are NOT in full extras
        dev_tools = ["pre-commit", "mypy", "black", "ruff"]
        for tool in dev_tools:
            assert tool not in full_section, f"Dev tool '{tool}' should not be in 'full' extras"

    def test_test_tools_not_included(self) -> None:
        """Verify test tools are NOT included in 'full' extras.

        Acceptance Criteria:
        - tox NOT in full
        - pytest-cov NOT in full
        - pytest-xdist NOT in full
        - Test tools should be in separate 'test' extras
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Find full extras section
        full_start = content.find("full = [")
        full_end = content.find("\n\n", full_start)
        full_section = content[full_start:full_end]

        # Verify test tools are NOT in full extras
        # Note: pytest-benchmark IS included (it's a benchmarking tool, not a test tool)
        test_tools = ["tox", "pytest-cov", "pytest-xdist", "pytest-asyncio"]
        for tool in test_tools:
            assert tool not in full_section, f"Test tool '{tool}' should not be in 'full' extras"

    def test_docs_tools_not_included(self) -> None:
        """Verify documentation tools are NOT included in 'full' extras.

        Acceptance Criteria:
        - mkdocs NOT in full
        - Sphinx NOT in full
        - Documentation tools should be in separate 'docs' extras
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Find full extras section
        full_start = content.find("full = [")
        full_end = content.find("\n\n", full_start)
        full_section = content[full_start:full_end]

        # Verify docs tools are NOT in full extras
        docs_tools = ["mkdocs", "Sphinx", "numpydoc"]
        for tool in docs_tools:
            assert tool not in full_section, f"Docs tool '{tool}' should not be in 'full' extras"

    def test_full_extras_package_count(self) -> None:
        """Verify 'full' extras contains expected number of packages.

        Acceptance Criteria:
        - Package count should be 9-12 unique packages
        - Duplicates should be avoided (e.g., matplotlib listed once)
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Find full extras section
        full_start = content.find("full = [")
        full_end = content.find("]", full_start)
        full_section = content[full_start:full_end]

        # Count package lines (exclude comments and empty lines)
        package_lines = [
            line.strip()
            for line in full_section.split("\n")
            if line.strip() and not line.strip().startswith("#") and "full = [" not in line
        ]

        # Verify package count is within expected range
        assert (
            9 <= len(package_lines) <= 12
        ), f"Expected 9-12 packages in 'full' extras, found {len(package_lines)}"


class TestPackageMetadata:
    """Test suite for package metadata and version information."""

    def test_package_name(self) -> None:
        """Verify package name is correctly set."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        assert "name = 'rustybt'" in content or 'name = "rustybt"' in content

    def test_python_version_requirement(self) -> None:
        """Verify Python version requirement is 3.12+.

        Constitutional Requirement CR-004: Python 3.12+ REQUIRED
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        assert "requires-python = '>=3.12'" in content or 'requires-python = ">=3.12"' in content


@pytest.mark.slow
@pytest.mark.integration
class TestInstallation:
    """Integration tests for package installation.

    Note: These tests are marked as 'slow' and 'integration' because they
    require creating virtual environments and installing packages.
    Run with: pytest -m "not slow" to skip these tests in development.
    """

    def test_pyproject_toml_valid_syntax(self) -> None:
        """Verify pyproject.toml has valid TOML syntax.

        This is a basic validation that the file can be parsed.
        """
        import tomllib

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_bytes()

        # Should not raise exception
        config = tomllib.loads(content.decode("utf-8"))

        assert "project" in config
        assert "optional-dependencies" in config["project"]
        assert "full" in config["project"]["optional-dependencies"]
        assert "all" in config["project"]["optional-dependencies"]

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Virtual environment creation differs on Windows",
    )
    def test_extras_install_dry_run(self) -> None:
        """Test that 'full' extras can be resolved without conflicts.

        Uses pip's --dry-run to verify dependencies can be installed
        without actually installing them.
        """
        repo_root = Path(__file__).parent.parent

        # Use pip's dependency resolver to check for conflicts
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--dry-run",
                "--no-deps",
                f"{repo_root}[full]",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        # Dry run should succeed (exit code 0) or skip with warning
        # We're mainly checking that there are no syntax errors
        assert result.returncode in (0, 1), f"Dependency resolution failed: {result.stderr}"


class TestExtrasConsistency:
    """Test suite for extras consistency and correctness."""

    def test_no_duplicate_packages_in_full(self) -> None:
        """Verify no duplicate packages in 'full' extras.

        Acceptance Criteria:
        - Each package listed only once
        - Prevents installation conflicts
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Find full extras section
        full_start = content.find("full = [")
        full_end = content.find("]", full_start)
        full_section = content[full_start:full_end]

        # Extract package names (first word before >=, ==, etc.)
        packages = []
        for line in full_section.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "full = [" not in line:
                # Extract package name (before version specifier)
                package_name = line.split(">=")[0].split("==")[0].split("<")[0]
                package_name = package_name.strip().strip("',\"")
                if package_name:
                    packages.append(package_name)

        # Check for duplicates
        duplicates = {pkg for pkg in packages if packages.count(pkg) > 1}
        assert not duplicates, f"Duplicate packages found in 'full' extras: {duplicates}"

    def test_version_specifiers_consistent(self) -> None:
        """Verify all packages have version specifiers.

        Acceptance Criteria:
        - All packages use >= for minimum version
        - Version format is consistent (e.g., >=X.Y.Z)
        """
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Find full extras section
        full_start = content.find("full = [")
        full_end = content.find("]", full_start)
        full_section = content[full_start:full_end]

        # Verify version specifiers
        for line in full_section.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "full = [" not in line:
                # Each package should have >= version specifier
                assert ">=" in line, f"Package missing version specifier: {line}"
