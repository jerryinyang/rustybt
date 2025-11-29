"""Tests for classification workflows."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rustybt.validation.classification import (
    classify_as_bug,
    classify_as_design,
    create_documentation_stub,
    format_classification_summary,
    get_current_user,
    parse_components,
    validate_components,
    validate_rationale,
)
from rustybt.validation.models import BugSeverity, DesignChoice, Finding


class TestBugSeverity:
    """Tests for BugSeverity enum."""

    def test_severity_from_number_critical(self):
        """Test converting 1 to Critical."""
        assert BugSeverity.from_number(1) == BugSeverity.CRITICAL

    def test_severity_from_number_major(self):
        """Test converting 2 to Major."""
        assert BugSeverity.from_number(2) == BugSeverity.MAJOR

    def test_severity_from_number_minor(self):
        """Test converting 3 to Minor."""
        assert BugSeverity.from_number(3) == BugSeverity.MINOR

    def test_severity_from_invalid_number(self):
        """Test invalid numbers default to Minor."""
        assert BugSeverity.from_number(0) == BugSeverity.MINOR
        assert BugSeverity.from_number(99) == BugSeverity.MINOR
        assert BugSeverity.from_number(-1) == BugSeverity.MINOR

    def test_severity_values(self):
        """Test severity string values."""
        assert BugSeverity.CRITICAL.value == "Critical"
        assert BugSeverity.MAJOR.value == "Major"
        assert BugSeverity.MINOR.value == "Minor"


class TestDesignChoice:
    """Tests for DesignChoice enum."""

    def test_design_choice_from_key_rustybt(self):
        """Test converting 'r' to rustybt_preferred."""
        assert DesignChoice.from_key("r") == DesignChoice.RUSTYBT_PREFERRED

    def test_design_choice_from_key_backtrader(self):
        """Test converting 'b' to backtrader_preferred."""
        assert DesignChoice.from_key("b") == DesignChoice.BACKTRADER_PREFERRED

    def test_design_choice_from_key_either(self):
        """Test converting 'e' to either_valid."""
        assert DesignChoice.from_key("e") == DesignChoice.EITHER_VALID

    def test_design_choice_case_insensitive(self):
        """Test key conversion is case insensitive."""
        assert DesignChoice.from_key("R") == DesignChoice.RUSTYBT_PREFERRED
        assert DesignChoice.from_key("B") == DesignChoice.BACKTRADER_PREFERRED
        assert DesignChoice.from_key("E") == DesignChoice.EITHER_VALID

    def test_design_choice_invalid_defaults(self):
        """Test invalid keys default to either_valid."""
        assert DesignChoice.from_key("x") == DesignChoice.EITHER_VALID
        assert DesignChoice.from_key("z") == DesignChoice.EITHER_VALID

    def test_design_choice_values(self):
        """Test design choice string values."""
        assert DesignChoice.RUSTYBT_PREFERRED.value == "rustybt_preferred"
        assert DesignChoice.BACKTRADER_PREFERRED.value == "backtrader_preferred"
        assert DesignChoice.EITHER_VALID.value == "either_valid"


class TestValidation:
    """Tests for validation functions."""

    def test_validate_rationale_valid(self):
        """Test valid rationale passes."""
        is_valid, error = validate_rationale("This is a valid rationale")
        assert is_valid is True
        assert error == ""

    def test_validate_rationale_empty(self):
        """Test empty rationale fails."""
        is_valid, error = validate_rationale("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_rationale_whitespace_only(self):
        """Test whitespace-only rationale fails."""
        is_valid, error = validate_rationale("   \t\n  ")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_components_valid(self):
        """Test valid components list passes."""
        is_valid, error = validate_components(["file.py"])
        assert is_valid is True
        assert error == ""

    def test_validate_components_empty(self):
        """Test empty components list fails."""
        is_valid, error = validate_components([])
        assert is_valid is False
        assert "required" in error.lower()

    def test_parse_components_single(self):
        """Test parsing single component."""
        result = parse_components("file.py")
        assert result == ["file.py"]

    def test_parse_components_multiple(self):
        """Test parsing multiple components."""
        result = parse_components("file1.py, file2.py, file3.py")
        assert result == ["file1.py", "file2.py", "file3.py"]

    def test_parse_components_with_whitespace(self):
        """Test parsing with extra whitespace."""
        result = parse_components("  file1.py  ,  file2.py  ")
        assert result == ["file1.py", "file2.py"]

    def test_parse_components_empty_entries(self):
        """Test parsing ignores empty entries."""
        result = parse_components("file1.py, , file2.py, ")
        assert result == ["file1.py", "file2.py"]


class TestGetCurrentUser:
    """Tests for get_current_user function."""

    def test_get_user_from_env(self):
        """Test getting user from environment variable."""
        with patch.dict("os.environ", {"RUSTYBT_USER": "test_user"}):
            assert get_current_user() == "test_user"

    def test_get_user_from_system(self):
        """Test falling back to system user."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("rustybt.validation.classification.os.environ.get", return_value=None):
                user = get_current_user()
                # Should return something (system username)
                assert isinstance(user, str)
                assert len(user) > 0


@pytest.mark.classification
class TestClassifyAsBug:
    """Tests for classify_as_bug workflow."""

    def test_classify_as_bug_updates_finding(self):
        """Test BUG classification updates all fields."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")

        with patch("click.prompt") as mock_prompt, patch("click.echo"):
            mock_prompt.side_effect = [
                "Test rationale",  # rationale
                "rustybt/order.py",  # components
                2,  # severity (Major)
                "",  # suggested fix (skip)
                "developer",  # investigator
            ]

            classify_as_bug(finding)

        assert finding.classification == "BUG"
        assert finding.rationale == "Test rationale"
        assert finding.severity == "Major"
        assert finding.affected_components == ["rustybt/order.py"]
        assert finding.suggested_fix is None
        assert finding.investigated_by == "developer"
        assert finding.investigated_at is not None

    def test_classify_as_bug_with_suggested_fix(self):
        """Test BUG classification with suggested fix."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")

        with patch("click.prompt") as mock_prompt, patch("click.echo"):
            mock_prompt.side_effect = [
                "Bug rationale",
                "file.py",
                1,  # Critical
                "Add validation check",  # suggested fix
                "developer",
            ]

            classify_as_bug(finding)

        assert finding.severity == "Critical"
        assert finding.suggested_fix == "Add validation check"

    def test_classify_as_bug_retries_empty_rationale(self):
        """Test workflow retries on empty rationale."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")

        with patch("click.prompt") as mock_prompt, patch("click.echo") as mock_echo, patch(
            "click.secho"
        ):
            mock_prompt.side_effect = [
                "",  # empty rationale (rejected)
                "   ",  # whitespace rationale (rejected)
                "Valid rationale",  # valid
                "file.py",
                2,
                "",
                "developer",
            ]

            classify_as_bug(finding)

        # Should have shown error messages
        error_calls = [c for c in mock_echo.call_args_list if "Error" in str(c)]
        # Note: secho is used for errors, not echo
        assert finding.rationale == "Valid rationale"

    def test_classify_as_bug_retries_empty_components(self):
        """Test workflow retries on empty components."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "Rationale",
                "",  # empty components (rejected)
                "file.py",  # valid
                2,
                "",
                "developer",
            ]

            classify_as_bug(finding)

        assert finding.affected_components == ["file.py"]

    def test_classify_as_bug_multiple_components(self):
        """Test classification with multiple components."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")

        with patch("click.prompt") as mock_prompt, patch("click.echo"):
            mock_prompt.side_effect = [
                "Rationale",
                "file1.py, file2.py, file3.py",
                3,  # Minor
                "",
                "developer",
            ]

            classify_as_bug(finding)

        assert finding.affected_components == ["file1.py", "file2.py", "file3.py"]

    def test_classify_as_bug_calls_save_callback(self):
        """Test save callback is called."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")
        save_callback = MagicMock()

        with patch("click.prompt") as mock_prompt, patch("click.echo"):
            mock_prompt.side_effect = ["Rationale", "file.py", 2, "", "developer"]

            classify_as_bug(finding, save_callback=save_callback)

        save_callback.assert_called_once_with(finding)

    def test_classify_as_bug_logs_activity(self):
        """Test session activity is logged."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")
        session = MagicMock()

        with patch("click.prompt") as mock_prompt, patch("click.echo"):
            mock_prompt.side_effect = ["Rationale", "file.py", 2, "", "developer"]

            classify_as_bug(finding, session=session)

        session.log_activity.assert_called_once()
        call_args = session.log_activity.call_args
        assert "finding_classified" in str(call_args)


@pytest.mark.classification
class TestClassifyAsDesign:
    """Tests for classify_as_design workflow."""

    def test_classify_as_design_updates_finding(self, tmp_path):
        """Test DESIGN classification updates all fields."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Test finding",
            rustybt_value=100.0,
            backtrader_value=99.5,
        )

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "Design rationale",  # rationale
                "e",  # design choice (either)
                "Minor impact on users",  # user impact
                "docs/validation/design-differences.md#test",  # doc ref
                "developer",  # investigator
            ]

            classify_as_design(finding, project_root=tmp_path)

        assert finding.classification == "DESIGN"
        assert finding.rationale == "Design rationale"
        assert finding.design_rationale == "Design rationale"
        assert finding.design_choice == "either_valid"
        assert finding.user_impact == "Minor impact on users"
        assert finding.documentation_ref == "docs/validation/design-differences.md#test"
        assert finding.investigated_by == "developer"
        assert finding.investigated_at is not None

    def test_classify_as_design_rustybt_preferred(self, tmp_path):
        """Test DESIGN classification with rustybt_preferred choice."""
        finding = Finding(
            id="FIND-001",
            layer="signals",
            description="RSI difference",
            rustybt_value=70.5,
            backtrader_value=71.0,
        )

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "rustybt uses Wilder's smoothing",
                "r",  # rustybt preferred
                "Minor RSI difference",
                "docs/validation/design-differences.md#rsi",
                "developer",
            ]

            classify_as_design(finding, project_root=tmp_path)

        assert finding.design_choice == "rustybt_preferred"

    def test_classify_as_design_backtrader_preferred(self, tmp_path):
        """Test DESIGN classification with backtrader_preferred choice."""
        finding = Finding(
            id="FIND-001",
            layer="signals",
            description="Test finding",
            rustybt_value=100.0,
            backtrader_value=99.5,
        )

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "Backtrader approach is industry standard",
                "b",  # backtrader preferred
                "Users should expect backtrader behavior",
                "docs/validation/design-differences.md#standard",
                "developer",
            ]

            classify_as_design(finding, project_root=tmp_path)

        assert finding.design_choice == "backtrader_preferred"

    def test_classify_as_design_retries_empty_rationale(self, tmp_path):
        """Test workflow retries on empty rationale."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "",  # empty (rejected)
                "Valid design rationale",  # valid
                "e",  # design choice
                "User impact",
                "docs/validation/design-differences.md#test",
                "developer",
            ]

            classify_as_design(finding, project_root=tmp_path)

        assert finding.rationale == "Valid design rationale"

    def test_classify_as_design_retries_empty_user_impact(self, tmp_path):
        """Test workflow retries on empty user impact."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "Valid rationale",
                "e",
                "",  # empty user impact (rejected)
                "Valid user impact",  # valid
                "docs/validation/design-differences.md#test",
                "developer",
            ]

            classify_as_design(finding, project_root=tmp_path)

        assert finding.user_impact == "Valid user impact"

    def test_classify_as_design_calls_save_callback(self, tmp_path):
        """Test save callback is called."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")
        save_callback = MagicMock()

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "Rationale",
                "e",
                "User impact",
                "docs/validation/design-differences.md#test",
                "developer",
            ]

            classify_as_design(finding, save_callback=save_callback, project_root=tmp_path)

        save_callback.assert_called_once_with(finding)

    def test_classify_as_design_logs_activity(self, tmp_path):
        """Test session activity is logged."""
        finding = Finding(id="FIND-001", layer="orders", description="Test finding")
        session = MagicMock()

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "Rationale",
                "e",
                "User impact",
                "docs/validation/design-differences.md#test",
                "developer",
            ]

            classify_as_design(finding, session=session, project_root=tmp_path)

        session.log_activity.assert_called_once()

    def test_classify_as_design_creates_documentation(self, tmp_path):
        """Test documentation stub is created when project_root provided."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Test finding",
            rustybt_value=100.0,
            backtrader_value=99.5,
        )

        with patch("click.prompt") as mock_prompt, patch("click.echo"), patch("click.secho"):
            mock_prompt.side_effect = [
                "Rationale",
                "e",
                "User impact",
                "docs/validation/design-differences.md#test-section",
                "developer",
            ]

            classify_as_design(finding, project_root=tmp_path)

        doc_path = tmp_path / "docs/validation/design-differences.md"
        assert doc_path.exists()
        content = doc_path.read_text()
        assert "## test-section" in content
        assert "FIND-001" in content


@pytest.mark.classification
class TestCreateDocumentationStub:
    """Tests for create_documentation_stub function."""

    def test_creates_new_file_with_header(self, tmp_path):
        """Test documentation file is created with header."""
        finding = Finding(
            id="FIND-001",
            layer="signals",
            description="Test finding",
            rustybt_value=70.5,
            backtrader_value=71.0,
        )

        with patch("click.echo"), patch("click.secho"):
            create_documentation_stub(
                finding=finding,
                rationale="Test rationale",
                design_choice=DesignChoice.EITHER_VALID,
                user_impact="Test impact",
                doc_ref="docs/validation/design-differences.md#test-anchor",
                project_root=tmp_path,
            )

        doc_path = tmp_path / "docs/validation/design-differences.md"
        assert doc_path.exists()

        content = doc_path.read_text()
        assert "# Design Differences" in content
        assert "## test-anchor" in content
        assert "FIND-001" in content
        assert "Test rationale" in content
        assert "Test impact" in content

    def test_appends_to_existing_file(self, tmp_path):
        """Test new section is appended to existing file."""
        doc_path = tmp_path / "docs/validation/design-differences.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text("# Design Differences\n\nExisting content.\n")

        finding = Finding(
            id="FIND-002",
            layer="orders",
            description="New finding",
            rustybt_value=100.0,
            backtrader_value=99.0,
        )

        with patch("click.echo"), patch("click.secho"):
            create_documentation_stub(
                finding=finding,
                rationale="New rationale",
                design_choice=DesignChoice.RUSTYBT_PREFERRED,
                user_impact="New impact",
                doc_ref="docs/validation/design-differences.md#new-section",
                project_root=tmp_path,
            )

        content = doc_path.read_text()
        assert "Existing content." in content
        assert "## new-section" in content
        assert "FIND-002" in content

    def test_skips_existing_anchor(self, tmp_path):
        """Test existing anchor is not duplicated."""
        doc_path = tmp_path / "docs/validation/design-differences.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text("# Design Differences\n\n## existing-anchor\n\nContent here.\n")

        finding = Finding(id="FIND-001", layer="signals", description="Test")

        with patch("click.echo"), patch("click.secho") as mock_secho:
            result = create_documentation_stub(
                finding=finding,
                rationale="Test",
                design_choice=DesignChoice.EITHER_VALID,
                user_impact="Test",
                doc_ref="docs/validation/design-differences.md#existing-anchor",
                project_root=tmp_path,
            )

        assert result is False
        content = doc_path.read_text()
        assert content.count("## existing-anchor") == 1

    def test_rustybt_preferred_text(self, tmp_path):
        """Test rustybt_preferred creates correct text."""
        finding = Finding(
            id="FIND-001",
            layer="signals",
            description="Test",
            rustybt_value=70.5,
            backtrader_value=71.0,
        )

        with patch("click.echo"), patch("click.secho"):
            create_documentation_stub(
                finding=finding,
                rationale="rustybt is better",
                design_choice=DesignChoice.RUSTYBT_PREFERRED,
                user_impact="Users benefit",
                doc_ref="docs/validation/design-differences.md#rustybt-test",
                project_root=tmp_path,
            )

        doc_path = tmp_path / "docs/validation/design-differences.md"
        content = doc_path.read_text()
        assert "rustybt's approach is preferred" in content

    def test_backtrader_preferred_text(self, tmp_path):
        """Test backtrader_preferred creates correct text."""
        finding = Finding(
            id="FIND-001",
            layer="signals",
            description="Test",
            rustybt_value=70.5,
            backtrader_value=71.0,
        )

        with patch("click.echo"), patch("click.secho"):
            create_documentation_stub(
                finding=finding,
                rationale="backtrader is standard",
                design_choice=DesignChoice.BACKTRADER_PREFERRED,
                user_impact="Users should expect this",
                doc_ref="docs/validation/design-differences.md#bt-test",
                project_root=tmp_path,
            )

        doc_path = tmp_path / "docs/validation/design-differences.md"
        content = doc_path.read_text()
        assert "Backtrader's approach is preferred" in content

    def test_either_valid_text(self, tmp_path):
        """Test either_valid creates correct text."""
        finding = Finding(
            id="FIND-001",
            layer="signals",
            description="Test",
            rustybt_value=70.5,
            backtrader_value=71.0,
        )

        with patch("click.echo"), patch("click.secho"):
            create_documentation_stub(
                finding=finding,
                rationale="Both are valid",
                design_choice=DesignChoice.EITHER_VALID,
                user_impact="User preference",
                doc_ref="docs/validation/design-differences.md#either-test",
                project_root=tmp_path,
            )

        doc_path = tmp_path / "docs/validation/design-differences.md"
        content = doc_path.read_text()
        assert "Either approach is acceptable" in content

    def test_creates_nested_directories(self, tmp_path):
        """Test nested directories are created."""
        finding = Finding(
            id="FIND-001",
            layer="signals",
            description="Test",
            rustybt_value=70.5,
            backtrader_value=71.0,
        )

        with patch("click.echo"), patch("click.secho"):
            create_documentation_stub(
                finding=finding,
                rationale="Test",
                design_choice=DesignChoice.EITHER_VALID,
                user_impact="Test",
                doc_ref="docs/deep/nested/path/design.md#anchor",
                project_root=tmp_path,
            )

        doc_path = tmp_path / "docs/deep/nested/path/design.md"
        assert doc_path.exists()

    def test_doc_ref_without_anchor(self, tmp_path):
        """Test doc_ref without anchor uses finding ID."""
        finding = Finding(
            id="FIND-001",
            layer="signals",
            description="Test",
            rustybt_value=70.5,
            backtrader_value=71.0,
        )

        with patch("click.echo"), patch("click.secho"):
            create_documentation_stub(
                finding=finding,
                rationale="Test",
                design_choice=DesignChoice.EITHER_VALID,
                user_impact="Test",
                doc_ref="docs/validation/design-differences.md",  # no anchor
                project_root=tmp_path,
            )

        doc_path = tmp_path / "docs/validation/design-differences.md"
        content = doc_path.read_text()
        assert "## find-001" in content.lower() or "FIND-001" in content


class TestFormatClassificationSummary:
    """Tests for format_classification_summary function."""

    def test_format_unclassified(self):
        """Test formatting unclassified finding."""
        finding = Finding(id="FIND-001", layer="orders", description="Test")
        result = format_classification_summary(finding)

        assert "FIND-001" in result
        assert "orders" in result
        assert "Unclassified" in result

    def test_format_bug_classification(self):
        """Test formatting BUG-classified finding."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Test",
            classification="BUG",
            rationale="Test bug",
            severity="Major",
            affected_components=["file.py"],
            suggested_fix="Fix it",
            investigated_by="developer",
            investigated_at=datetime.now(),
        )
        result = format_classification_summary(finding)

        assert "BUG" in result
        assert "Major" in result
        assert "Test bug" in result
        assert "file.py" in result
        assert "Fix it" in result
        assert "developer" in result

    def test_format_design_classification(self):
        """Test formatting DESIGN-classified finding."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Test",
            classification="DESIGN",
            rationale="Intentional",
            acceptance_criteria="< 0.01%",
            investigated_by="developer",
            investigated_at=datetime.now(),
        )
        result = format_classification_summary(finding)

        assert "DESIGN" in result
        assert "Intentional" in result
        assert "< 0.01%" in result


class TestFindingModel:
    """Tests for extended Finding model."""

    def test_finding_to_dict(self):
        """Test Finding serialization to dict."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Test finding",
            classification="BUG",
            rationale="Bug rationale",
            severity="Major",
            affected_components=["file.py"],
            suggested_fix="Fix suggestion",
            investigated_by="developer",
            investigated_at=datetime(2025, 1, 15, 10, 30),
        )
        result = finding.to_dict()

        assert result["id"] == "FIND-001"
        assert result["classification"] == "BUG"
        assert result["severity"] == "Major"
        assert result["affected_components"] == ["file.py"]
        assert result["suggested_fix"] == "Fix suggestion"
        assert result["investigated_at"] == "2025-01-15T10:30:00"

    def test_finding_from_dict(self):
        """Test Finding deserialization from dict."""
        data = {
            "id": "FIND-001",
            "layer": "orders",
            "description": "Test finding",
            "classification": "BUG",
            "rationale": "Bug rationale",
            "severity": "Major",
            "affected_components": ["file.py"],
            "suggested_fix": "Fix suggestion",
            "investigated_by": "developer",
            "investigated_at": "2025-01-15T10:30:00",
        }
        finding = Finding.from_dict(data)

        assert finding.id == "FIND-001"
        assert finding.classification == "BUG"
        assert finding.severity == "Major"
        assert finding.affected_components == ["file.py"]
        assert finding.investigated_at == datetime(2025, 1, 15, 10, 30)

    def test_finding_from_dict_with_missing_optional_fields(self):
        """Test Finding deserialization with missing optional fields."""
        data = {
            "id": "FIND-001",
            "layer": "orders",
            "description": "Test finding",
        }
        finding = Finding.from_dict(data)

        assert finding.classification is None
        assert finding.severity is None
        assert finding.affected_components == []
        assert finding.investigated_at is None

    def test_finding_roundtrip(self):
        """Test Finding survives serialization roundtrip."""
        original = Finding(
            id="FIND-001",
            layer="orders",
            description="Test finding",
            classification="DESIGN",
            rationale="Design choice",
            design_rationale="Design choice",
            acceptance_criteria="Always accept",
            investigated_by="architect",
            investigated_at=datetime(2025, 1, 15, 10, 30),
        )

        data = original.to_dict()
        restored = Finding.from_dict(data)

        assert restored.id == original.id
        assert restored.classification == original.classification
        assert restored.design_rationale == original.design_rationale
        assert restored.acceptance_criteria == original.acceptance_criteria

    def test_finding_with_design_fields_to_dict(self):
        """Test Finding with DESIGN fields serializes correctly."""
        finding = Finding(
            id="FIND-002",
            layer="signals",
            description="RSI difference",
            classification="DESIGN",
            rationale="Intentional calculation difference",
            design_rationale="Different smoothing algorithm",
            design_choice="either_valid",
            user_impact="Minor value differences",
            documentation_ref="docs/validation/design-differences.md#rsi",
            investigated_by="developer",
            investigated_at=datetime(2025, 1, 15, 10, 30),
        )
        result = finding.to_dict()

        assert result["design_choice"] == "either_valid"
        assert result["user_impact"] == "Minor value differences"
        assert result["documentation_ref"] == "docs/validation/design-differences.md#rsi"

    def test_finding_with_design_fields_from_dict(self):
        """Test Finding with DESIGN fields deserializes correctly."""
        data = {
            "id": "FIND-002",
            "layer": "signals",
            "description": "RSI difference",
            "classification": "DESIGN",
            "rationale": "Intentional",
            "design_choice": "rustybt_preferred",
            "user_impact": "Minor difference",
            "documentation_ref": "docs/test.md#anchor",
            "investigated_by": "developer",
            "investigated_at": "2025-01-15T10:30:00",
        }
        finding = Finding.from_dict(data)

        assert finding.design_choice == "rustybt_preferred"
        assert finding.user_impact == "Minor difference"
        assert finding.documentation_ref == "docs/test.md#anchor"

    def test_finding_design_roundtrip(self):
        """Test DESIGN Finding survives full serialization roundtrip."""
        original = Finding(
            id="FIND-002",
            layer="signals",
            description="Test DESIGN finding",
            classification="DESIGN",
            rationale="Design rationale",
            design_rationale="Design rationale",
            design_choice="backtrader_preferred",
            user_impact="User will see different values",
            documentation_ref="docs/validation/design-differences.md#test",
            rustybt_value=70.5,
            backtrader_value=71.0,
            investigated_by="architect",
            investigated_at=datetime(2025, 1, 15, 10, 30),
        )

        data = original.to_dict()
        restored = Finding.from_dict(data)

        assert restored.design_choice == original.design_choice
        assert restored.user_impact == original.user_impact
        assert restored.documentation_ref == original.documentation_ref
        assert restored.rustybt_value == original.rustybt_value
        assert restored.backtrader_value == original.backtrader_value
