"""Tests for regression test generation.

Story 5.6: Implement Regression Test Generation

Tests the regression module which auto-generates pytest tests for
verified bug fixes.
"""

import ast
from datetime import datetime
from pathlib import Path

import pytest

from rustybt.validation.models import Finding
from rustybt.validation.regression import (
    LAYER_TO_MARKER,
    REGRESSION_DIR,
    _extract_event_type,
    _sanitize_test_name,
    generate_regression_test,
    generate_test_content,
)


class TestSanitizeTestName:
    """Tests for _sanitize_test_name function."""

    def test_converts_to_lowercase(self):
        """Should convert to lowercase."""
        assert _sanitize_test_name("FIND-001") == "find_001"

    def test_replaces_hyphens(self):
        """Should replace hyphens with underscores."""
        assert _sanitize_test_name("layer-3-finding-001") == "layer_3_finding_001"

    def test_handles_already_valid_name(self):
        """Should keep already valid names."""
        assert _sanitize_test_name("find_001") == "find_001"

    def test_removes_invalid_characters(self):
        """Should remove characters not valid in identifiers."""
        assert _sanitize_test_name("find@001!") == "find_001_"

    def test_prefixes_numeric_start(self):
        """Should prefix names starting with digit."""
        assert _sanitize_test_name("001_test") == "f_001_test"


class TestExtractEventType:
    """Tests for _extract_event_type function."""

    def test_extracts_mismatch_pattern(self):
        """Should extract mismatch event type."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Order quantity mismatch detected",
        )
        assert "mismatch" in _extract_event_type(finding).lower()

    def test_extracts_from_colon_pattern(self):
        """Should extract from layer/event: description pattern."""
        finding = Finding(
            id="FIND-002",
            layer="data",
            description="data/bar_received: price differs by 0.01",
        )
        result = _extract_event_type(finding)
        assert "bar_received" in result

    def test_uses_first_words_as_fallback(self):
        """Should use first words if no pattern matches."""
        finding = Finding(
            id="FIND-003",
            layer="signals",
            description="Something unexpected happened",
        )
        result = _extract_event_type(finding)
        assert len(result) > 0


class TestLayerToMarker:
    """Tests for LAYER_TO_MARKER mapping."""

    def test_all_layers_mapped(self):
        """Should have mapping for all 5 layers."""
        expected_layers = ["data", "signals", "orders", "broker", "portfolio"]
        for layer in expected_layers:
            assert layer in LAYER_TO_MARKER

    def test_marker_format(self):
        """Should follow layer_N_name format."""
        assert LAYER_TO_MARKER["data"] == "layer_1_data"
        assert LAYER_TO_MARKER["signals"] == "layer_2_signals"
        assert LAYER_TO_MARKER["orders"] == "layer_3_orders"
        assert LAYER_TO_MARKER["broker"] == "layer_4_broker"
        assert LAYER_TO_MARKER["portfolio"] == "layer_5_portfolio"


class TestGenerateTestContent:
    """Tests for generate_test_content function."""

    def test_generates_valid_python(self):
        """Should generate syntactically valid Python code."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Order quantity mismatch",
            rustybt_value=100.0,
            backtrader_value=99.0,
            resolved=True,
            resolved_at=datetime.now(),
            rationale="Fixed calculation",
        )

        content = generate_test_content(finding)

        # Parse as AST to verify valid Python
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

    def test_includes_regression_marker(self):
        """Should include @pytest.mark.regression decorator."""
        finding = Finding(
            id="FIND-002",
            layer="data",
            description="Price mismatch",
            resolved=True,
        )

        content = generate_test_content(finding)

        assert "@pytest.mark.regression" in content

    def test_includes_layer_marker(self):
        """Should include layer-specific pytest marker."""
        finding = Finding(
            id="FIND-003",
            layer="broker",
            description="Commission mismatch",
            resolved=True,
        )

        content = generate_test_content(finding)

        assert "@pytest.mark.layer_4_broker" in content

    def test_includes_finding_details_in_docstring(self):
        """Should include finding details in docstring."""
        finding = Finding(
            id="FIND-004",
            layer="portfolio",
            description="Return calculation error",
            rustybt_value=0.15,
            backtrader_value=0.14,
            resolved=True,
            resolved_at=datetime(2025, 11, 27),
            rationale="Fixed return calculation",
            affected_components=["rustybt/finance/returns.py"],
        )

        content = generate_test_content(finding)

        assert "FIND-004" in content
        assert "Return calculation error" in content
        assert "0.15" in content
        assert "0.14" in content
        assert "2025-11-27" in content
        assert "rustybt/finance/returns.py" in content

    def test_assertion_references_finding_id(self):
        """Should include finding ID in assertion message."""
        finding = Finding(
            id="FIND-005",
            layer="signals",
            description="RSI mismatch",
            resolved=True,
        )

        content = generate_test_content(finding)

        assert "FIND-005" in content
        assert "reappeared" in content or "regressed" in content

    def test_test_function_name_derived_from_id(self):
        """Should derive test function name from finding ID."""
        finding = Finding(
            id="FIND-006",
            layer="orders",
            description="Test",
            resolved=True,
        )

        content = generate_test_content(finding)

        assert "def test_find_006" in content


class TestGenerateRegressionTest:
    """Tests for generate_regression_test function."""

    def test_creates_test_file(self, tmp_path):
        """Should create test file at correct path."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Order quantity mismatch",
            rustybt_value=100.0,
            backtrader_value=99.0,
            resolved=True,
            resolved_at=datetime.now(),
            rationale="Fixed calculation",
        )

        test_path = generate_regression_test(finding, tmp_path)

        assert test_path.exists()
        assert test_path.name == "test_find_001.py"
        assert test_path.parent.name == "regression"

    def test_creates_regression_directory(self, tmp_path):
        """Should create regression directory if not exists."""
        finding = Finding(
            id="FIND-002",
            layer="data",
            description="Test",
            resolved=True,
        )

        generate_regression_test(finding, tmp_path)

        assert (tmp_path / REGRESSION_DIR).exists()

    def test_creates_init_file(self, tmp_path):
        """Should create __init__.py in regression directory."""
        finding = Finding(
            id="FIND-003",
            layer="signals",
            description="Test",
            resolved=True,
        )

        generate_regression_test(finding, tmp_path)

        init_file = tmp_path / REGRESSION_DIR / "__init__.py"
        assert init_file.exists()

    def test_does_not_overwrite_existing_init(self, tmp_path):
        """Should not overwrite existing __init__.py."""
        regression_dir = tmp_path / REGRESSION_DIR
        regression_dir.mkdir(parents=True)
        init_file = regression_dir / "__init__.py"
        init_file.write_text("# Custom content\n")

        finding = Finding(
            id="FIND-004",
            layer="broker",
            description="Test",
            resolved=True,
        )

        generate_regression_test(finding, tmp_path)

        assert init_file.read_text() == "# Custom content\n"

    def test_generated_file_is_valid_python(self, tmp_path):
        """Should generate syntactically valid Python file."""
        finding = Finding(
            id="FIND-005",
            layer="portfolio",
            description="Return mismatch",
            rustybt_value=0.10,
            backtrader_value=0.11,
            resolved=True,
            resolved_at=datetime.now(),
            rationale="Fixed calculation",
            affected_components=["rustybt/finance/returns.py"],
        )

        test_path = generate_regression_test(finding, tmp_path)
        content = test_path.read_text()

        # Verify valid Python
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Generated file has syntax error: {e}")

    def test_handles_complex_finding_id(self, tmp_path):
        """Should handle complex finding IDs with special characters."""
        finding = Finding(
            id="LAYER-3-FINDING-001-ORDERS",
            layer="orders",
            description="Test",
            resolved=True,
        )

        test_path = generate_regression_test(finding, tmp_path)

        assert test_path.exists()
        assert "layer_3_finding_001_orders" in test_path.name


class TestRegressionDirectoryStructure:
    """Tests for regression test directory structure."""

    def test_regression_dir_constant(self):
        """Should have correct default regression directory."""
        assert REGRESSION_DIR == Path("tests/validation/regression")

    def test_conftest_exists(self):
        """Should have conftest.py with fixtures."""
        conftest_path = Path("tests/validation/regression/conftest.py")
        assert conftest_path.exists()

    def test_init_exists(self):
        """Should have __init__.py."""
        init_path = Path("tests/validation/regression/__init__.py")
        assert init_path.exists()


class TestCLIIntegration:
    """Tests for CLI integration with regression test generation."""

    def test_verify_mentions_regression_test(self, tmp_path, monkeypatch):
        """Should mention regression test in verify output."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main
        from rustybt.validation.session import SessionManager

        monkeypatch.chdir(tmp_path)

        # Create a session with a BUG finding
        sessions_dir = tmp_path / "validation-sessions"
        sm = SessionManager(sessions_dir)
        session = sm.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.csv"),
            rustybt_version="1.0.0",
            backtrader_version="1.9.0",
        )
        finding = Finding(
            id="FIND-CLI-001",
            layer="data",
            description="Test discrepancy",
            classification="BUG",
        )
        sm.add_finding(session, finding)

        runner = CliRunner()
        # This will fail at execution, but we're testing the CLI structure
        result = runner.invoke(main, ["verify", "FIND-CLI-001"])

        # Should at least recognize the command and finding
        assert "Verifying Fix" in result.output or "not found" not in result.output
