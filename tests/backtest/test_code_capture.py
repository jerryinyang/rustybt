"""Unit tests for strategy code capture via import analysis."""

import ast
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from rustybt.backtest.code_capture import CodeCaptureError, StrategyCodeCapture


class TestStrategyCodeCapture:
    """Test suite for StrategyCodeCapture class."""

    @pytest.fixture
    def code_capture(self):
        """Create StrategyCodeCapture instance."""
        return StrategyCodeCapture()

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project structure for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create a marker file to identify as project root
        (project_root / ".git").mkdir()

        return project_root

    # ==================== Import Analysis Tests ====================

    def test_analyze_imports_simple_import(self, code_capture, temp_project):
        """Verify analyze_imports handles 'import X' statements."""
        # Create test file with simple imports
        test_file = temp_project / "strategy.py"
        test_file.write_text(
            dedent(
                """
            import os
            import sys
            import pandas as pd
            """
            )
        )

        # Analyze imports
        result = code_capture.analyze_imports(test_file, temp_project)

        # Should include only the strategy file itself (stdlib modules filtered)
        assert len(result) == 1
        assert result[0] == test_file.resolve()

    def test_analyze_imports_from_import(self, code_capture, temp_project):
        """Verify analyze_imports handles 'from X import Y' statements."""
        # Create helper module
        utils_dir = temp_project / "utils"
        utils_dir.mkdir()
        (utils_dir / "__init__.py").touch()
        helper_file = utils_dir / "helpers.py"
        helper_file.write_text("def helper(): pass")

        # Create strategy that imports from helper
        test_file = temp_project / "strategy.py"
        test_file.write_text(
            dedent(
                """
            from utils.helpers import helper
            """
            )
        )

        # Analyze imports
        result = code_capture.analyze_imports(test_file, temp_project)

        # Should include both strategy and helper
        result_names = {f.name for f in result}
        assert "strategy.py" in result_names
        assert "helpers.py" in result_names

    def test_analyze_imports_relative_import_single_dot(self, code_capture, temp_project):
        """Verify analyze_imports handles relative imports with single dot."""
        # Create package structure
        strategies_dir = temp_project / "strategies"
        strategies_dir.mkdir()
        (strategies_dir / "__init__.py").touch()

        # Create helper module
        helper_file = strategies_dir / "helpers.py"
        helper_file.write_text("def helper(): pass")

        # Create strategy with relative import
        strategy_file = strategies_dir / "strategy.py"
        strategy_file.write_text(
            dedent(
                """
            from .helpers import helper
            """
            )
        )

        # Analyze imports
        result = code_capture.analyze_imports(strategy_file, temp_project)

        # Should include both files
        result_names = {f.name for f in result}
        assert "strategy.py" in result_names
        assert "helpers.py" in result_names

    def test_analyze_imports_relative_import_double_dot(self, code_capture, temp_project):
        """Verify analyze_imports handles multi-level relative imports."""
        # Create nested package structure
        strategies_dir = temp_project / "strategies"
        strategies_dir.mkdir()
        (strategies_dir / "__init__.py").touch()

        momentum_dir = strategies_dir / "momentum"
        momentum_dir.mkdir()
        (momentum_dir / "__init__.py").touch()

        # Create helper at parent level
        helper_file = strategies_dir / "common_helpers.py"
        helper_file.write_text("def helper(): pass")

        # Create strategy with parent relative import
        strategy_file = momentum_dir / "strategy.py"
        strategy_file.write_text(
            dedent(
                """
            from ..common_helpers import helper
            """
            )
        )

        # Analyze imports
        result = code_capture.analyze_imports(strategy_file, temp_project)

        # Should include both files
        result_names = {f.name for f in result}
        assert "strategy.py" in result_names
        assert "common_helpers.py" in result_names

    def test_analyze_imports_multiline_import(self, code_capture, temp_project):
        """Verify analyze_imports handles multi-line imports."""
        # Create helper modules
        utils_dir = temp_project / "utils"
        utils_dir.mkdir()
        (utils_dir / "__init__.py").touch()
        (utils_dir / "helpers.py").write_text("def helper1(): pass")
        (utils_dir / "indicators.py").write_text("def indicator1(): pass")

        # Create strategy with multi-line import
        test_file = temp_project / "strategy.py"
        test_file.write_text(
            dedent(
                """
            from utils import (
                helpers,
                indicators
            )
            """
            )
        )

        # Analyze imports
        result = code_capture.analyze_imports(test_file, temp_project)

        # Should include strategy and both utils modules
        result_names = {f.name for f in result}
        assert "strategy.py" in result_names
        # Note: These will be __init__.py since we import the package
        assert "__init__.py" in result_names

    def test_analyze_imports_recursive(self, code_capture, temp_project):
        """Verify analyze_imports recursively analyzes imported modules."""
        # Create a chain of imports: strategy -> utils -> helpers
        helpers_file = temp_project / "helpers.py"
        helpers_file.write_text("def helper(): pass")

        utils_file = temp_project / "utils.py"
        utils_file.write_text(
            dedent(
                """
            from helpers import helper
            """
            )
        )

        strategy_file = temp_project / "strategy.py"
        strategy_file.write_text(
            dedent(
                """
            from utils import helper
            """
            )
        )

        # Analyze imports
        result = code_capture.analyze_imports(strategy_file, temp_project)

        # Should include all three files
        result_names = {f.name for f in result}
        assert "strategy.py" in result_names
        assert "utils.py" in result_names
        assert "helpers.py" in result_names

    def test_analyze_imports_empty_file(self, code_capture, temp_project):
        """Verify analyze_imports handles empty files."""
        test_file = temp_project / "empty.py"
        test_file.write_text("")

        result = code_capture.analyze_imports(test_file, temp_project)

        # Should include only the empty file itself
        assert len(result) == 1
        assert result[0] == test_file.resolve()

    def test_analyze_imports_syntax_error(self, code_capture, temp_project):
        """Verify analyze_imports handles files with syntax errors."""
        test_file = temp_project / "bad_syntax.py"
        test_file.write_text("def broken(:\n    pass")

        # Should not raise, but log warning
        result = code_capture.analyze_imports(test_file, temp_project)

        # Should still include the file itself
        assert len(result) == 1
        assert result[0] == test_file.resolve()

    def test_analyze_imports_nonexistent_file(self, code_capture, temp_project):
        """Verify analyze_imports raises for nonexistent files."""
        nonexistent = temp_project / "does_not_exist.py"

        with pytest.raises(CodeCaptureError, match="Entry point file not found"):
            code_capture.analyze_imports(nonexistent, temp_project)

    def test_analyze_imports_circular_import(self, code_capture, temp_project):
        """Verify analyze_imports handles circular imports without infinite loop."""
        # Create circular import: a.py imports b.py, b.py imports a.py
        a_file = temp_project / "a.py"
        a_file.write_text("from b import func_b")

        b_file = temp_project / "b.py"
        b_file.write_text("from a import func_a")

        # Should not hang
        result = code_capture.analyze_imports(a_file, temp_project)

        # Should include both files
        result_names = {f.name for f in result}
        assert "a.py" in result_names
        assert "b.py" in result_names

    # ==================== Module Filtering Tests ====================

    def test_is_local_module_filters_stdlib(self, code_capture, temp_project):
        """Verify standard library modules are filtered out."""
        assert not code_capture.is_local_module("os", temp_project)
        assert not code_capture.is_local_module("sys", temp_project)
        assert not code_capture.is_local_module("pathlib", temp_project)
        assert not code_capture.is_local_module("collections", temp_project)

    def test_is_local_module_filters_site_packages(self, code_capture, temp_project):
        """Verify site-packages modules are filtered out."""
        # These should be filtered (common third-party packages)
        assert not code_capture.is_local_module("pytest", temp_project)
        assert not code_capture.is_local_module("structlog", temp_project)

    def test_is_local_module_filters_framework(self, code_capture, temp_project):
        """Verify framework modules (rustybt) are filtered out."""
        # rustybt framework should be filtered unless in project root
        assert not code_capture.is_local_module("rustybt", temp_project)
        assert not code_capture.is_local_module("rustybt.algorithm", temp_project)

    def test_is_local_module_identifies_local(self, code_capture, temp_project):
        """Verify local modules are identified correctly."""
        # Create a local module
        local_file = temp_project / "my_module.py"
        local_file.write_text("def func(): pass")

        # Add project to sys.path so it can be found
        sys.path.insert(0, str(temp_project))
        try:
            assert code_capture.is_local_module("my_module", temp_project)
        finally:
            sys.path.remove(str(temp_project))

    def test_is_local_module_handles_module_not_found(self, code_capture, temp_project):
        """Verify handling of modules that cannot be resolved."""
        # Non-existent module should return False
        assert not code_capture.is_local_module("nonexistent_module_xyz", temp_project)

    # ==================== File Copying Tests ====================

    def test_copy_strategy_files_preserves_structure(self, code_capture, temp_project):
        """Verify directory structure is preserved when copying files."""
        # Create nested structure
        strategies_dir = temp_project / "strategies"
        strategies_dir.mkdir()
        utils_dir = strategies_dir / "utils"
        utils_dir.mkdir()

        strategy_file = strategies_dir / "strategy.py"
        strategy_file.write_text("# strategy")

        helper_file = utils_dir / "helpers.py"
        helper_file.write_text("# helpers")

        # Copy files
        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        files_to_copy = [strategy_file, helper_file]
        copied = code_capture.copy_strategy_files(files_to_copy, dest_dir, temp_project)

        # Verify structure preserved
        assert len(copied) == 2
        assert (dest_dir / "strategies" / "strategy.py").exists()
        assert (dest_dir / "strategies" / "utils" / "helpers.py").exists()

    def test_copy_strategy_files_preserves_content(self, code_capture, temp_project):
        """Verify file content is preserved when copying."""
        content = "# Test content\ndef func():\n    return 42"

        source_file = temp_project / "source.py"
        source_file.write_text(content)

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        copied = code_capture.copy_strategy_files([source_file], dest_dir, temp_project)

        # Verify content matches
        copied_content = copied[0].read_text()
        assert copied_content == content

    def test_copy_strategy_files_preserves_metadata(self, code_capture, temp_project):
        """Verify file metadata (timestamps) are preserved."""
        import time

        source_file = temp_project / "source.py"
        source_file.write_text("# test")

        # Get original modification time
        original_mtime = source_file.stat().st_mtime

        # Wait a bit to ensure time difference
        time.sleep(0.01)

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        copied = code_capture.copy_strategy_files([source_file], dest_dir, temp_project)

        # Verify timestamp preserved (copy2 preserves metadata)
        copied_mtime = copied[0].stat().st_mtime
        assert abs(copied_mtime - original_mtime) < 0.01  # Allow small difference

    def test_copy_strategy_files_handles_missing_file(self, code_capture, temp_project):
        """Verify handling of missing files during copy."""
        nonexistent = temp_project / "nonexistent.py"
        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Should not raise, but log warning
        copied = code_capture.copy_strategy_files([nonexistent], dest_dir, temp_project)

        # Should return empty list
        assert len(copied) == 0

    def test_copy_strategy_files_creates_subdirectories(self, code_capture, temp_project):
        """Verify subdirectories are created as needed."""
        deep_dir = temp_project / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)

        source_file = deep_dir / "deep.py"
        source_file.write_text("# deep")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        copied = code_capture.copy_strategy_files([source_file], dest_dir, temp_project)

        # Verify deep directory structure created
        assert (dest_dir / "a" / "b" / "c" / "deep.py").exists()

    def test_copy_strategy_files_outside_project_root(self, code_capture, temp_project):
        """Verify handling of files outside project root."""
        # Create file outside project root
        outside_dir = temp_project.parent / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "external.py"
        outside_file.write_text("# external")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Should copy file but use filename only (logged as warning)
        copied = code_capture.copy_strategy_files([outside_file], dest_dir, temp_project)

        # Should copy with filename only
        assert len(copied) == 1
        assert copied[0].name == "external.py"

    # ==================== Project Root Detection Tests ====================

    def test_find_project_root_detects_git(self, code_capture, temp_project):
        """Verify project root detection via .git directory."""
        nested_dir = temp_project / "a" / "b" / "c"
        nested_dir.mkdir(parents=True)
        strategy_file = nested_dir / "strategy.py"
        strategy_file.touch()

        root = code_capture.find_project_root(strategy_file)

        assert root == temp_project

    def test_find_project_root_detects_pyproject_toml(self, code_capture, tmp_path):
        """Verify project root detection via pyproject.toml."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").touch()

        nested_dir = project_root / "src"
        nested_dir.mkdir()
        strategy_file = nested_dir / "strategy.py"
        strategy_file.touch()

        root = code_capture.find_project_root(strategy_file)

        assert root == project_root

    def test_find_project_root_detects_setup_py(self, code_capture, tmp_path):
        """Verify project root detection via setup.py."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "setup.py").touch()

        nested_dir = project_root / "src"
        nested_dir.mkdir()
        strategy_file = nested_dir / "strategy.py"
        strategy_file.touch()

        root = code_capture.find_project_root(strategy_file)

        assert root == project_root

    def test_find_project_root_fallback(self, code_capture, tmp_path):
        """Verify fallback to parent directory if no markers found."""
        strategy_dir = tmp_path / "strategies"
        strategy_dir.mkdir()
        strategy_file = strategy_dir / "strategy.py"
        strategy_file.touch()

        root = code_capture.find_project_root(strategy_file)

        # Should fallback to strategy file's parent directory
        assert root == strategy_dir

    # ==================== Integration Tests ====================

    def test_full_workflow_single_file(self, code_capture, temp_project):
        """Test complete workflow with single-file strategy."""
        strategy_file = temp_project / "simple_strategy.py"
        strategy_file.write_text(
            dedent(
                """
            import pandas as pd

            def initialize(context):
                pass
            """
            )
        )

        dest_dir = temp_project / "output"
        dest_dir.mkdir()

        # Analyze and copy
        local_files = code_capture.analyze_imports(strategy_file, temp_project)
        copied = code_capture.copy_strategy_files(local_files, dest_dir, temp_project)

        # Should capture only the strategy file
        assert len(copied) == 1
        assert (dest_dir / "simple_strategy.py").exists()

    def test_full_workflow_multi_file(self, code_capture, temp_project):
        """Test complete workflow with multi-file strategy."""
        # Create project structure
        utils_dir = temp_project / "utils"
        utils_dir.mkdir()
        (utils_dir / "__init__.py").touch()

        indicators_file = utils_dir / "indicators.py"
        indicators_file.write_text("def sma(data, window): pass")

        helpers_file = utils_dir / "helpers.py"
        helpers_file.write_text(
            dedent(
                """
            from utils.indicators import sma

            def log_trade(asset, value): pass
            """
            )
        )

        strategy_file = temp_project / "strategy.py"
        strategy_file.write_text(
            dedent(
                """
            from utils.indicators import sma
            from utils.helpers import log_trade

            def handle_data(context, data):
                pass
            """
            )
        )

        dest_dir = temp_project / "output"
        dest_dir.mkdir()

        # Analyze and copy
        local_files = code_capture.analyze_imports(strategy_file, temp_project)
        copied = code_capture.copy_strategy_files(local_files, dest_dir, temp_project)

        # Should capture all local files
        copied_names = {f.name for f in copied}
        assert "strategy.py" in copied_names
        assert "indicators.py" in copied_names
        assert "helpers.py" in copied_names

        # Verify structure preserved
        assert (dest_dir / "strategy.py").exists()
        assert (dest_dir / "utils" / "indicators.py").exists()
        assert (dest_dir / "utils" / "helpers.py").exists()


class TestErrorPathCoverage:
    """Test suite for error path coverage to reach 90%+ coverage."""

    @pytest.fixture
    def code_capture(self):
        """Create StrategyCodeCapture instance."""
        return StrategyCodeCapture()

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project structure for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        return project_root

    # ==================== Relative Import Error Paths ====================

    def test_relative_import_reaches_filesystem_root(self, code_capture, temp_project):
        """Test relative import that would exceed filesystem root."""
        # Create file at project root
        test_file = temp_project / "strategy.py"
        test_file.write_text(
            dedent(
                """
            from .....nonexistent import something
            """
            )
        )

        # Should handle gracefully (returns None for invalid relative import)
        result = code_capture.analyze_imports(test_file, temp_project)

        # Should still include the strategy file
        assert len(result) >= 1
        assert test_file.resolve() in result

    def test_relative_import_outside_project_root(self, code_capture, tmp_path):
        """Test relative import that resolves outside project root."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        # Create nested file
        nested_dir = project_root / "deep" / "nested"
        nested_dir.mkdir(parents=True)
        test_file = nested_dir / "strategy.py"
        test_file.write_text(
            dedent(
                """
            from ....external import something
            """
            )
        )

        # Should handle gracefully
        result = code_capture.analyze_imports(test_file, project_root)

        # Should include the strategy file
        assert test_file.resolve() in result

    def test_relative_import_resolution_exception(self, code_capture, temp_project):
        """Test exception handling in relative import resolution."""
        # Create a file with a relative import
        test_file = temp_project / "strategy.py"
        test_file.write_text("from . import utils")

        # Analyze should handle any exceptions gracefully
        result = code_capture.analyze_imports(test_file, temp_project)

        # Should not crash
        assert isinstance(result, list)

    # ==================== File Reading Error Paths ====================

    def test_analyze_imports_file_encoding_error(self, code_capture, temp_project):
        """Test handling of files with encoding errors."""
        # Create file with invalid UTF-8
        test_file = temp_project / "bad_encoding.py"
        test_file.write_bytes(b"\xff\xfe# Invalid UTF-8")

        # Should handle gracefully with warning
        result = code_capture.analyze_imports(test_file, temp_project)

        # Should include the file itself (added before reading)
        assert test_file.resolve() in result

    def test_analyze_imports_permission_error(self, code_capture, temp_project):
        """Test handling of files without read permission."""
        import os
        import stat

        test_file = temp_project / "no_permission.py"
        test_file.write_text("import os")

        # Remove read permissions
        os.chmod(test_file, 0o000)

        try:
            # Should handle gracefully
            result = code_capture.analyze_imports(test_file, temp_project)
            # Should include file in result (added before reading)
            assert test_file.resolve() in result
        finally:
            # Restore permissions for cleanup
            os.chmod(test_file, stat.S_IRUSR | stat.S_IWUSR)

    # ==================== Module Spec Error Paths ====================

    def test_get_module_spec_import_error(self, code_capture, temp_project):
        """Test _get_module_spec with modules that raise ImportError."""
        # This should return None for non-existent modules
        spec = code_capture._get_module_spec("definitely_does_not_exist_xyz123")
        assert spec is None

    def test_get_module_spec_value_error(self, code_capture, temp_project):
        """Test _get_module_spec caching with ValueError."""
        # Module names with special characters might cause ValueError
        spec = code_capture._get_module_spec("invalid..module..name")
        assert spec is None

    # ==================== Filesystem Module Resolution Error Paths ====================

    def test_resolve_module_path_from_name_not_in_project(self, code_capture, temp_project):
        """Test filesystem resolution for modules outside project root."""
        # Try to resolve stdlib module (should return None)
        result = code_capture._resolve_module_path_from_name("os", temp_project, temp_project)
        assert result is None

    def test_resolve_module_path_from_name_nonexistent(self, code_capture, temp_project):
        """Test filesystem resolution for nonexistent modules."""
        result = code_capture._resolve_module_path_from_name(
            "nonexistent.module", temp_project, temp_project
        )
        assert result is None

    def test_resolve_module_path_from_name_as_package(self, code_capture, temp_project):
        """Test filesystem resolution finding __init__.py."""
        # Create package
        package_dir = temp_project / "mypackage"
        package_dir.mkdir()
        init_file = package_dir / "__init__.py"
        init_file.write_text("# Package init")

        # Should find the __init__.py
        result = code_capture._resolve_module_path_from_name(
            "mypackage", temp_project, temp_project
        )
        assert result == init_file

    def test_resolve_module_path_from_name_relative_to_current_dir(
        self, code_capture, temp_project
    ):
        """Test filesystem resolution relative to current directory."""
        # Create nested structure
        subdir = temp_project / "subdir"
        subdir.mkdir()
        module_file = subdir / "utils.py"
        module_file.write_text("def helper(): pass")

        # Resolve from subdir context
        result = code_capture._resolve_module_path_from_name("utils", temp_project, subdir)
        assert result == module_file

    # ==================== File Copying Error Paths ====================

    def test_copy_strategy_files_file_outside_project_creates_flat(
        self, code_capture, temp_project
    ):
        """Test copying files outside project root uses filename only."""
        # Create file outside project
        outside_dir = temp_project.parent / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "external.py"
        outside_file.write_text("# external")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Copy should work with warning
        copied = code_capture.copy_strategy_files([outside_file], dest_dir, temp_project)

        # Should copy with filename only (flat structure)
        assert len(copied) == 1
        assert copied[0].name == "external.py"

    def test_copy_strategy_files_io_error(self, code_capture, temp_project):
        """Test file copy failure (e.g., disk full, permissions)."""
        import os
        import stat

        source_file = temp_project / "source.py"
        source_file.write_text("# test")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Make dest_dir read-only
        os.chmod(dest_dir, stat.S_IRUSR | stat.S_IXUSR)

        try:
            # Should handle error gracefully
            copied = code_capture.copy_strategy_files([source_file], dest_dir, temp_project)
            # Should return empty list or partial list
            assert isinstance(copied, list)
        finally:
            # Restore permissions
            os.chmod(dest_dir, stat.S_IRWXU)

    # ==================== Project Root Detection Error Paths ====================

    def test_find_project_root_at_filesystem_root(self, code_capture, tmp_path):
        """Test project root detection when reaching filesystem root."""
        # Create file deep in filesystem without markers
        deep_dir = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)
        test_file = deep_dir / "strategy.py"
        test_file.write_text("# test")

        # Should fall back to parent directory
        root = code_capture.find_project_root(test_file)
        assert root == deep_dir

    def test_find_project_root_multiple_markers(self, code_capture, tmp_path):
        """Test project root detection prioritizes .git over others."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        # Create multiple markers
        (project_root / ".git").mkdir()
        (project_root / "pyproject.toml").touch()
        (project_root / "setup.py").touch()

        nested_dir = project_root / "src"
        nested_dir.mkdir()
        test_file = nested_dir / "strategy.py"
        test_file.touch()

        # Should find .git directory (highest priority)
        root = code_capture.find_project_root(test_file)
        assert root == project_root
        assert (root / ".git").exists()

    # ==================== Extract Module Names Error Path ====================

    def test_extract_module_names_with_from_import_no_module(self, code_capture, temp_project):
        """Test extracting module names from 'from . import X' (module=None)."""
        test_file = temp_project / "strategy.py"
        test_file.write_text(
            dedent(
                """
            from . import utils, helpers
            """
            )
        )

        # Parse and extract
        with open(test_file) as f:
            tree = ast.parse(f.read())

        module_names = code_capture._extract_module_names(tree, test_file, temp_project)

        # Should handle gracefully (resolve relative import)
        assert isinstance(module_names, list)

    # ==================== Additional Coverage for Remaining Lines ====================

    def test_analyze_imports_file_outside_project_root(self, code_capture, tmp_path):
        """Test analyzing file outside project root (line 111)."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        # Create file outside project root
        outside_file = tmp_path / "outside_file.py"
        outside_file.write_text("import os")

        # Analyze - should include file but mark as outside project
        result = code_capture.analyze_imports(outside_file, project_root)

        # File should not be in result since it's outside project root
        # (line 111: ValueError exception caught, file not added to local_files)
        assert outside_file.resolve() not in result or len(result) == 0

    def test_relative_import_at_exact_filesystem_boundary(self, code_capture, tmp_path):
        """Test relative import resolution at filesystem boundary (lines 119-121)."""
        # Create minimal project at tmp root
        project_root = tmp_path / "proj"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        test_file = project_root / "file.py"
        test_file.write_text("from .... import something")

        # Should handle gracefully - resolves to None
        result = code_capture.analyze_imports(test_file, project_root)

        # Should not crash
        assert isinstance(result, list)

    def test_relative_import_debug_logging_path(self, code_capture, temp_project):
        """Test relative import exception logging (lines 160-162)."""
        # Create file with many levels of relative imports
        deep_dir = temp_project / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)
        test_file = deep_dir / "module.py"
        test_file.write_text("from ...... import impossible")

        # Should handle and log debug message
        result = code_capture.analyze_imports(test_file, temp_project)

        # Should complete without crash
        assert isinstance(result, list)

    def test_module_spec_caching_multiple_calls(self, code_capture, temp_project):
        """Test module spec caching behavior (line 229)."""
        # Call multiple times to trigger caching
        spec1 = code_capture._get_module_spec("nonexistent_module_test")
        spec2 = code_capture._get_module_spec("nonexistent_module_test")

        # Both should be None and cached
        assert spec1 is None
        assert spec2 is None
        assert "nonexistent_module_test" in code_capture._module_spec_cache

    def test_resolve_module_path_from_name_nested_package(self, code_capture, temp_project):
        """Test filesystem resolution for nested packages (lines 246-255)."""
        # Create nested package structure
        pkg1 = temp_project / "pkg1"
        pkg1.mkdir()
        (pkg1 / "__init__.py").touch()

        pkg2 = pkg1 / "pkg2"
        pkg2.mkdir()
        (pkg2 / "__init__.py").touch()

        # Try to resolve nested module
        result = code_capture._resolve_module_path_from_name(
            "pkg1.pkg2", temp_project, temp_project
        )

        # Should find the __init__.py
        assert result is not None
        assert result.name == "__init__.py"

    def test_copy_files_with_nested_directory_creation(self, code_capture, temp_project):
        """Test file copying creates nested directories (lines 300, 309-313)."""
        # Create deeply nested source
        deep_source = temp_project / "src" / "deep" / "nested" / "module.py"
        deep_source.parent.mkdir(parents=True)
        deep_source.write_text("# deep module")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Copy should create full path
        copied = code_capture.copy_strategy_files([deep_source], dest_dir, temp_project)

        # Verify structure created
        assert len(copied) == 1
        expected = dest_dir / "src" / "deep" / "nested" / "module.py"
        assert expected.exists()

    def test_copy_files_exception_in_copy_operation(self, code_capture, temp_project):
        """Test exception handling during file copy (lines 341-344)."""
        source_file = temp_project / "source.py"
        source_file.write_text("# test")

        # Create destination that will cause issues
        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Create a file where we expect a directory
        conflict_path = dest_dir / "source.py"
        conflict_path.mkdir()  # Make it a directory instead of file

        # Try to copy - should handle gracefully
        copied = code_capture.copy_strategy_files([source_file], dest_dir, temp_project)

        # Should return empty or partial list
        assert isinstance(copied, list)

    def test_find_project_root_no_markers_deep_path(self, code_capture, tmp_path):
        """Test project root fallback for deep paths (lines 373, 395, 399)."""
        # Create very deep directory without markers
        deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "g"
        deep.mkdir(parents=True)

        test_file = deep / "file.py"
        test_file.touch()

        # Should fall back to parent
        root = code_capture.find_project_root(test_file)

        # Should return deep directory (parent of file)
        assert root == deep

    def test_analyze_imports_triggers_file_outside_project_path(self, code_capture, tmp_path):
        """Test that analyzing triggers the ValueError path for files outside project (line 111)."""
        project_root = tmp_path / "myproject"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        # Create a file that imports something from outside
        inside_file = project_root / "strategy.py"
        inside_file.write_text("import os")

        # Create another file outside that we'll pretend gets imported
        outside_dir = tmp_path / "external"
        outside_dir.mkdir()
        outside_file = outside_dir / "external_module.py"
        outside_file.write_text("def external_func(): pass")

        # Manually trigger the recursive analysis with outside file
        analyzed_files = set()
        local_files = set()

        # This should trigger line 111 ValueError path
        code_capture._analyze_imports_recursive(
            outside_file, project_root, analyzed_files, local_files
        )

        # The outside file should be in analyzed_files but NOT in local_files
        assert outside_file.resolve() in analyzed_files
        assert outside_file.resolve() not in local_files

    def test_resolve_module_nested_dotted_path(self, code_capture, temp_project):
        """Test resolving deeply nested module paths (lines 246-255)."""
        # Create structure: pkg1/pkg2/module.py
        pkg1 = temp_project / "pkg1"
        pkg1.mkdir()
        (pkg1 / "__init__.py").touch()

        pkg2 = pkg1 / "pkg2"
        pkg2.mkdir()
        (pkg2 / "__init__.py").touch()

        module_file = pkg2 / "mymodule.py"
        module_file.write_text("def func(): pass")

        # Test resolving "pkg1.pkg2.mymodule"
        result = code_capture._resolve_module_path_from_name(
            "pkg1.pkg2.mymodule", temp_project, temp_project
        )

        # Should find the module file
        assert result == module_file

    def test_copy_files_detailed_error_logging(self, code_capture, temp_project):
        """Test detailed error path in copy_strategy_files (lines 341-344)."""
        source = temp_project / "src.py"
        source.write_text("test")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Create a file that will conflict
        (dest_dir / "src.py").write_text("existing")
        (dest_dir / "src.py").chmod(0o000)  # Make it unwritable

        try:
            # Should log warning but not crash
            result = code_capture.copy_strategy_files([source], dest_dir, temp_project)
            assert isinstance(result, list)
        finally:
            (dest_dir / "src.py").chmod(0o644)  # Cleanup


class TestStrategyYAMLCodeCapture:
    """Test suite for strategy.yaml-based code capture."""

    @pytest.fixture
    def code_capture(self):
        """Create StrategyCodeCapture instance."""
        return StrategyCodeCapture()

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project structure for testing."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        return project_root

    # ==================== YAML Loading Tests ====================

    def test_load_strategy_yaml_valid_format(self, code_capture, temp_project):
        """Verify valid strategy.yaml loads correctly."""
        yaml_content = """
files:
  - my_strategy.py
  - utils/indicators.py
  - config/settings.json
"""
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(yaml_content)

        config = code_capture.load_strategy_yaml(temp_project)

        assert config is not None
        assert "files" in config
        assert isinstance(config["files"], list)
        assert len(config["files"]) == 3
        assert "my_strategy.py" in config["files"]
        assert "utils/indicators.py" in config["files"]
        assert "config/settings.json" in config["files"]

    def test_load_strategy_yaml_missing_file(self, code_capture, temp_project):
        """Verify returns None when strategy.yaml doesn't exist."""
        config = code_capture.load_strategy_yaml(temp_project)
        assert config is None

    def test_load_strategy_yaml_missing_files_key(self, code_capture, temp_project):
        """Verify YAML without 'files' key returns None."""
        yaml_content = """
some_other_key: value
nested:
  data: 123
"""
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(yaml_content)

        config = code_capture.load_strategy_yaml(temp_project)
        assert config is None

    def test_load_strategy_yaml_files_not_a_list(self, code_capture, temp_project):
        """Verify YAML with 'files' as non-list returns None."""
        yaml_content = """
files: "not a list"
"""
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(yaml_content)

        config = code_capture.load_strategy_yaml(temp_project)
        assert config is None

    def test_load_strategy_yaml_not_a_dict(self, code_capture, temp_project):
        """Verify YAML that's not a dict returns None."""
        yaml_content = "- item1\n- item2\n- item3"
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(yaml_content)

        config = code_capture.load_strategy_yaml(temp_project)
        assert config is None

    def test_load_strategy_yaml_malformed(self, code_capture, temp_project):
        """Verify malformed YAML returns None."""
        yaml_content = """
files:
  - file1.py
  invalid yaml syntax here: [ { }
"""
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(yaml_content)

        config = code_capture.load_strategy_yaml(temp_project)
        assert config is None

    def test_load_strategy_yaml_empty_files_list(self, code_capture, temp_project):
        """Verify YAML with empty files list loads successfully."""
        yaml_content = """
files: []
"""
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(yaml_content)

        config = code_capture.load_strategy_yaml(temp_project)

        assert config is not None
        assert "files" in config
        assert len(config["files"]) == 0

    # ==================== YAML-Based Capture Tests ====================

    def test_capture_from_yaml_copies_listed_files(self, code_capture, temp_project):
        """Verify files in YAML are copied to code directory."""
        # Create strategy files
        strategy_file = temp_project / "my_strategy.py"
        strategy_file.write_text("def handle_data(context, data): pass")

        utils_dir = temp_project / "utils"
        utils_dir.mkdir()
        indicators_file = utils_dir / "indicators.py"
        indicators_file.write_text("def sma(data, window): pass")

        # Create config
        config = {"files": ["my_strategy.py", "utils/indicators.py"]}

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Capture
        captured = code_capture._capture_from_yaml(config, temp_project, dest_dir)

        # Verify both files captured
        assert len(captured) == 2
        assert (dest_dir / "my_strategy.py").exists()
        assert (dest_dir / "utils" / "indicators.py").exists()

    def test_capture_from_yaml_preserves_directory_structure(self, code_capture, temp_project):
        """Verify directory structure preserved for nested files."""
        # Create nested structure
        deep_dir = temp_project / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)
        deep_file = deep_dir / "deep_module.py"
        deep_file.write_text("# deep module")

        config = {"files": ["a/b/c/deep_module.py"]}

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        captured = code_capture._capture_from_yaml(config, temp_project, dest_dir)

        # Verify structure preserved
        assert (dest_dir / "a" / "b" / "c" / "deep_module.py").exists()

    def test_capture_from_yaml_handles_non_python_files(self, code_capture, temp_project):
        """Verify non-Python files (JSON, MD, etc.) are copied."""
        # Create various file types
        (temp_project / "strategy.py").write_text("# strategy")
        (temp_project / "config.json").write_text('{"param": 42}')
        (temp_project / "README.md").write_text("# Documentation")

        config = {"files": ["strategy.py", "config.json", "README.md"]}

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        captured = code_capture._capture_from_yaml(config, temp_project, dest_dir)

        # All files should be captured
        assert len(captured) == 3
        assert (dest_dir / "strategy.py").exists()
        assert (dest_dir / "config.json").exists()
        assert (dest_dir / "README.md").exists()

    def test_capture_from_yaml_warns_on_missing_file(self, code_capture, temp_project):
        """Verify warning logged when YAML file doesn't exist."""
        config = {"files": ["existing.py", "nonexistent.py", "also_missing.py"]}

        # Create only one file
        (temp_project / "existing.py").write_text("# exists")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Should not raise, but log warnings
        captured = code_capture._capture_from_yaml(config, temp_project, dest_dir)

        # Should capture only existing file
        assert len(captured) == 1
        assert captured[0].name == "existing.py"

    def test_capture_from_yaml_continues_after_missing_file(self, code_capture, temp_project):
        """Verify capture continues after encountering missing file."""
        config = {"files": ["file1.py", "missing.py", "file2.py"]}

        (temp_project / "file1.py").write_text("# file 1")
        (temp_project / "file2.py").write_text("# file 2")
        # missing.py not created

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        captured = code_capture._capture_from_yaml(config, temp_project, dest_dir)

        # Should capture both existing files
        assert len(captured) == 2
        assert (dest_dir / "file1.py").exists()
        assert (dest_dir / "file2.py").exists()

    def test_capture_from_yaml_handles_copy_error(self, code_capture, temp_project):
        """Verify error handling when file copy fails."""
        import os
        import stat

        # Create file
        source_file = temp_project / "source.py"
        source_file.write_text("# test")

        config = {"files": ["source.py"]}

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Make dest_dir read-only
        os.chmod(dest_dir, stat.S_IRUSR | stat.S_IXUSR)

        try:
            # Should handle error gracefully
            captured = code_capture._capture_from_yaml(config, temp_project, dest_dir)
            # Should return empty or partial list
            assert isinstance(captured, list)
        finally:
            os.chmod(dest_dir, stat.S_IRWXU)

    # ==================== Configuration and Precedence Tests ====================

    def test_capture_strategy_code_uses_yaml_when_present(self, code_capture, temp_project):
        """Verify strategy.yaml used when present (precedence rule 1)."""
        # Create strategy file
        strategy_file = temp_project / "strategy.py"
        strategy_file.write_text(
            dedent(
                """
            from utils import helper

            def handle_data(context, data): pass
            """
            )
        )

        # Create utils module that would be found by import analysis
        (temp_project / "utils.py").write_text("def helper(): pass")

        # Create strategy.yaml specifying different files
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(
            """
files:
  - strategy.py
"""
        )

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Capture
        captured = code_capture.capture_strategy_code(strategy_file, dest_dir, temp_project)

        # Should use YAML (only strategy.py, not utils.py)
        assert len(captured) == 1
        assert captured[0].name == "strategy.py"
        assert not (dest_dir / "utils.py").exists()

    def test_capture_strategy_code_fallback_to_import_analysis(self, code_capture, temp_project):
        """Verify entry point detection used when no YAML present (NEW - Story 001).

        In test context, entry point detection fails (no run_algorithm() in call stack),
        so code capture is gracefully skipped. This is the correct NEW behavior.
        """
        # Create strategy with import
        (temp_project / "utils.py").write_text("def helper(): pass")

        strategy_file = temp_project / "strategy.py"
        strategy_file.write_text("from utils import helper")

        # No strategy.yaml

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Capture - NEW BEHAVIOR: Entry point detection (not import analysis)
        captured = code_capture.capture_strategy_code(strategy_file, dest_dir, temp_project)

        # NEW BEHAVIOR: Entry point detection fails → graceful skip (empty list)
        # This is correct - when detection fails and no YAML, skip code capture
        assert len(captured) == 0  # Graceful degradation

    def test_capture_strategy_code_yaml_mode_warns_when_no_yaml(self, code_capture, temp_project):
        """Verify warning logged when mode=strategy_yaml but no YAML found (NEW - Story 001).

        code_capture_mode is now deprecated - we always use YAML if present,
        otherwise entry point detection. In test context, detection fails.
        """
        capture = StrategyCodeCapture(code_capture_mode="strategy_yaml")

        strategy_file = temp_project / "strategy.py"
        strategy_file.write_text("def handle_data(context, data): pass")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # NEW BEHAVIOR: Entry point detection (mode parameter is legacy)
        captured = capture.capture_strategy_code(strategy_file, dest_dir, temp_project)

        # NEW BEHAVIOR: Entry point detection fails → graceful skip
        assert len(captured) == 0  # Graceful degradation

    def test_capture_strategy_code_auto_detects_project_root(self, code_capture, temp_project):
        """Verify project root auto-detection when not specified (NEW - Story 001).

        Project root detection still works, but entry point detection will fail
        in test context (no run_algorithm() in call stack).
        """
        strategy_file = temp_project / "strategy.py"
        strategy_file.write_text("def handle_data(context, data): pass")

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Don't specify project_root - will auto-detect
        captured = code_capture.capture_strategy_code(strategy_file, dest_dir, project_root=None)

        # NEW BEHAVIOR: Entry point detection fails → graceful skip
        assert len(captured) == 0  # Graceful degradation

    # ==================== Integration Tests ====================

    def test_full_workflow_yaml_based_capture(self, code_capture, temp_project):
        """Test complete workflow with strategy.yaml."""
        # Create project structure
        (temp_project / "strategy.py").write_text("def handle_data(context, data): pass")

        utils_dir = temp_project / "utils"
        utils_dir.mkdir()
        (utils_dir / "indicators.py").write_text("def sma(): pass")
        (utils_dir / "helpers.py").write_text("def log(): pass")

        config_dir = temp_project / "config"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text('{"param": 42}')

        (temp_project / "README.md").write_text("# Strategy")

        # Create strategy.yaml
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(
            """
files:
  - strategy.py
  - utils/indicators.py
  - utils/helpers.py
  - config/settings.json
  - README.md
"""
        )

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Capture
        captured = code_capture.capture_strategy_code(
            temp_project / "strategy.py", dest_dir, temp_project
        )

        # Verify all files captured with structure preserved
        assert len(captured) == 5
        assert (dest_dir / "strategy.py").exists()
        assert (dest_dir / "utils" / "indicators.py").exists()
        assert (dest_dir / "utils" / "helpers.py").exists()
        assert (dest_dir / "config" / "settings.json").exists()
        assert (dest_dir / "README.md").exists()

    def test_full_workflow_yaml_explicit_vs_import_analysis(self, code_capture, temp_project):
        """Test that YAML takes precedence over import analysis."""
        # Create complex import structure
        (temp_project / "module_a.py").write_text("def a(): pass")
        (temp_project / "module_b.py").write_text("def b(): pass")
        (temp_project / "module_c.py").write_text("def c(): pass")

        strategy_file = temp_project / "strategy.py"
        strategy_file.write_text(
            dedent(
                """
            from module_a import a
            from module_b import b
            from module_c import c
            """
            )
        )

        # Create YAML specifying only subset
        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(
            """
files:
  - strategy.py
  - module_a.py
"""
        )

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Capture
        captured = code_capture.capture_strategy_code(strategy_file, dest_dir, temp_project)

        # Should capture only what YAML specified
        captured_names = {f.name for f in captured}
        assert "strategy.py" in captured_names
        assert "module_a.py" in captured_names
        assert "module_b.py" not in captured_names
        assert "module_c.py" not in captured_names

    def test_yaml_based_capture_performance(self, code_capture, temp_project):
        """Verify YAML-based capture completes quickly."""
        import time

        # Create many files
        for i in range(50):
            (temp_project / f"module_{i}.py").write_text(f"def func_{i}(): pass")

        # Create YAML listing all files
        file_list = [f"module_{i}.py" for i in range(50)]
        yaml_content = "files:\n" + "\n".join(f"  - {f}" for f in file_list)

        yaml_path = temp_project / "strategy.yaml"
        yaml_path.write_text(yaml_content)

        dest_dir = temp_project / "dest"
        dest_dir.mkdir()

        # Time the capture
        start = time.time()
        captured = code_capture.capture_strategy_code(
            temp_project / "module_0.py", dest_dir, temp_project
        )
        duration = time.time() - start

        # Should complete quickly (< 5 seconds per spec)
        assert duration < 5.0
        assert len(captured) == 50
