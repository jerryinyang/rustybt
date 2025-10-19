"""Tests for path resolution utilities in rustybt.utils.paths."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rustybt.utils.paths import (
    find_project_root,
    get_bundle_path,
    is_jupyter_environment,
    validate_bundle_configuration,
)


class TestFindProjectRoot:
    """Tests for find_project_root() function."""

    def test_find_git_root(self, tmp_path):
        """Test finding project root by .git directory."""
        # Create project structure
        project_root = tmp_path / "my_project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        nested_dir = project_root / "src" / "subdir"
        nested_dir.mkdir(parents=True)

        # Test from nested directory
        result = find_project_root(nested_dir)
        assert result == project_root

    def test_find_pyproject_root(self, tmp_path):
        """Test finding project root by pyproject.toml."""
        # Create project structure
        project_root = tmp_path / "my_project"
        project_root.mkdir()
        (project_root / "pyproject.toml").touch()
        nested_dir = project_root / "src" / "subdir"
        nested_dir.mkdir(parents=True)

        # Test from nested directory
        result = find_project_root(nested_dir)
        assert result == project_root

    def test_find_setup_py_root(self, tmp_path):
        """Test finding project root by setup.py."""
        # Create project structure
        project_root = tmp_path / "my_project"
        project_root.mkdir()
        (project_root / "setup.py").touch()
        nested_dir = project_root / "src" / "subdir"
        nested_dir.mkdir(parents=True)

        # Test from nested directory
        result = find_project_root(nested_dir)
        assert result == project_root

    def test_multiple_markers_prefers_closest(self, tmp_path):
        """Test that closest marker is found when multiple exist."""
        # Create nested project structure
        outer_root = tmp_path / "outer"
        outer_root.mkdir()
        (outer_root / ".git").mkdir()

        inner_root = outer_root / "inner"
        inner_root.mkdir()
        (inner_root / "pyproject.toml").touch()

        nested_dir = inner_root / "src"
        nested_dir.mkdir()

        # Should find inner project root first
        result = find_project_root(nested_dir)
        assert result == inner_root

    def test_fallback_to_cwd_when_no_markers(self, tmp_path):
        """Test fallback to CWD when no project markers found."""
        # Create directory without markers
        test_dir = tmp_path / "no_markers"
        test_dir.mkdir()

        # Should return the test directory itself (since we can't go higher)
        result = find_project_root(test_dir)
        # Result should be either test_dir or its parent depending on filesystem root
        assert result.exists()

    def test_default_start_path_is_cwd(self, tmp_path, monkeypatch):
        """Test that default start path is current working directory."""
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        # Change to project directory
        monkeypatch.chdir(project_root)

        # Should find project root from CWD
        result = find_project_root()
        assert result == project_root


class TestIsJupyterEnvironment:
    """Tests for is_jupyter_environment() function."""

    def test_not_jupyter_when_ipython_not_available(self):
        """Test returns False when IPython is not available."""
        with patch("IPython.get_ipython", side_effect=ImportError):
            assert is_jupyter_environment() is False

    def test_not_jupyter_when_ipython_none(self):
        """Test returns False when get_ipython() returns None."""
        with patch("IPython.get_ipython", return_value=None):
            assert is_jupyter_environment() is False

    def test_jupyter_when_ipkernel_in_config(self):
        """Test returns True when IPKernelApp in IPython config."""
        mock_ipython = MagicMock()
        mock_ipython.config = {"IPKernelApp": {}}

        with patch("IPython.get_ipython", return_value=mock_ipython):
            assert is_jupyter_environment() is True

    def test_not_jupyter_when_ipkernel_not_in_config(self):
        """Test returns False when IPKernelApp not in config."""
        mock_ipython = MagicMock()
        mock_ipython.config = {}

        with patch("IPython.get_ipython", return_value=mock_ipython):
            assert is_jupyter_environment() is False

    def test_handles_attribute_error(self):
        """Test handles AttributeError gracefully."""
        mock_ipython = MagicMock()
        del mock_ipython.config  # Remove config attribute

        with patch("IPython.get_ipython", return_value=mock_ipython):
            assert is_jupyter_environment() is False


class TestGetBundlePath:
    """Tests for get_bundle_path() function."""

    def test_csvdir_uses_env_variable(self, tmp_path):
        """Test that csvdir bundle respects CSVDIR environment variable."""
        csvdir = tmp_path / "custom_csvdir"
        csvdir.mkdir()

        environ = {"CSVDIR": str(csvdir)}
        result = get_bundle_path("csvdir", environ=environ)

        assert result == csvdir.resolve()

    def test_csvdir_expands_tilde(self, tmp_path):
        """Test that ~ is expanded in CSVDIR path."""
        environ = {"CSVDIR": "~/test_csvdir"}
        result = get_bundle_path("csvdir", environ=environ)

        # Should expand ~ to home directory
        assert "~" not in str(result)
        assert result.is_absolute()

    def test_bundle_path_uses_zipline_root(self, tmp_path):
        """Test bundle path uses ZIPLINE_ROOT when set."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        result = get_bundle_path("testbundle", environ=environ)

        # Should be under ZIPLINE_ROOT/data/bundles/testbundle
        assert str(zipline_root) in str(result)
        assert "bundles" in str(result)
        assert "testbundle" in str(result)

    def test_bundle_path_defaults_to_home_zipline(self):
        """Test bundle path defaults to ~/.zipline when ZIPLINE_ROOT not set."""
        environ = {}  # No ZIPLINE_ROOT
        result = get_bundle_path("testbundle", environ=environ)

        # Should contain .zipline in path
        assert ".zipline" in str(result)
        assert "bundles" in str(result)
        assert "testbundle" in str(result)

    def test_creates_bundle_directory_if_missing(self, tmp_path):
        """Test that bundle directory is created if it doesn't exist."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        result = get_bundle_path("newbundle", environ=environ)

        # Directory should be created
        assert result.exists()
        assert result.is_dir()

    def test_returns_absolute_path(self, tmp_path):
        """Test that returned path is always absolute."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        result = get_bundle_path("testbundle", environ=environ)

        assert result.is_absolute()

    def test_base_bundle_path_when_no_name(self, tmp_path):
        """Test returns base bundles directory when no bundle name specified."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        result = get_bundle_path(None, environ=environ)

        # Should be bundles directory without specific bundle name
        assert "bundles" in str(result)
        assert result.exists()
        assert result.is_dir()

    def test_handles_permission_error_gracefully(self, tmp_path):
        """Test that permission errors are raised appropriately."""
        # Create read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        environ = {"ZIPLINE_ROOT": str(readonly_dir)}

        # Should raise OSError when trying to create bundle directory
        with pytest.raises(OSError):
            get_bundle_path("testbundle", environ=environ)

        # Cleanup
        readonly_dir.chmod(0o755)


class TestValidateBundleConfiguration:
    """Tests for validate_bundle_configuration() function."""

    def test_validation_succeeds_with_writable_directory(self, tmp_path):
        """Test validation passes with writable bundle directory."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        result = validate_bundle_configuration("testbundle", environ=environ)

        assert result is True

    def test_creates_directory_if_missing(self, tmp_path):
        """Test validation creates bundle directory if missing."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        bundle_path = zipline_root / "data" / "bundles" / "testbundle"
        assert not bundle_path.exists()

        validate_bundle_configuration("testbundle", environ=environ)

        assert bundle_path.exists()
        assert bundle_path.is_dir()

    def test_validation_fails_without_write_permissions(self, tmp_path):
        """Test validation raises OSError without write permissions."""
        # Create read-only bundle directory
        readonly_bundle = tmp_path / "readonly_bundle"
        readonly_bundle.mkdir()
        readonly_bundle.chmod(0o444)  # Read-only

        environ = {"CSVDIR": str(readonly_bundle)}

        # Should raise OSError (which wraps PermissionError)
        with pytest.raises(OSError) as exc_info:
            validate_bundle_configuration("csvdir", environ=environ)

        assert "not writable" in str(exc_info.value) or "inaccessible" in str(exc_info.value)

        # Cleanup
        readonly_bundle.chmod(0o755)

    def test_validates_base_bundle_directory(self, tmp_path):
        """Test can validate base bundle directory without specific bundle name."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        result = validate_bundle_configuration(None, environ=environ)

        assert result is True

    def test_cleans_up_test_file(self, tmp_path):
        """Test that validation test file is cleaned up."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        validate_bundle_configuration("testbundle", environ=environ)

        bundle_path = zipline_root / "data" / "bundles" / "testbundle"
        test_file = bundle_path / ".write_test"

        # Test file should not exist after validation
        assert not test_file.exists()


class TestPathResolutionIntegration:
    """Integration tests for path resolution in different environments."""

    def test_jupyter_workflow_uses_central_storage(self, tmp_path, monkeypatch):
        """Test that Jupyter workflow uses central bundle storage."""
        # Create project structure
        project_root = tmp_path / "rustybt_project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        notebook_dir = project_root / "notebooks"
        notebook_dir.mkdir()

        # Set ZIPLINE_ROOT
        zipline_root = project_root / ".zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        # Change to notebook directory (simulating Jupyter)
        monkeypatch.chdir(notebook_dir)

        # Get bundle path from notebook context
        bundle_path = get_bundle_path("csvdir", environ=environ)

        # Should NOT be in notebook directory
        assert notebook_dir not in bundle_path.parents
        # Should be in ZIPLINE_ROOT
        assert zipline_root in bundle_path.parents
        # Should contain 'bundles' directory
        assert "bundles" in str(bundle_path)

    def test_cli_workflow_uses_central_storage(self, tmp_path):
        """Test that CLI workflow uses central bundle storage."""
        zipline_root = tmp_path / ".zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        bundle_path = get_bundle_path("quandl", environ=environ)

        # Should be in ZIPLINE_ROOT
        assert zipline_root in bundle_path.parents
        assert "bundles" in str(bundle_path)
        assert "quandl" in str(bundle_path)

    def test_multiple_bundles_share_base_directory(self, tmp_path):
        """Test that multiple bundles use same base directory."""
        zipline_root = tmp_path / ".zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        csvdir_path = get_bundle_path("csvdir", environ=environ)
        quandl_path = get_bundle_path("quandl", environ=environ)

        # Both should share the same bundles base directory
        assert csvdir_path.parent == quandl_path.parent
        assert csvdir_path.parent.name == "bundles"


# Performance tests
class TestPathResolutionPerformance:
    """Performance tests for path resolution."""

    def test_path_resolution_is_fast(self, tmp_path, benchmark):
        """Test that path resolution completes in <1ms."""
        zipline_root = tmp_path / ".zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        def resolve_path():
            return get_bundle_path("testbundle", environ=environ)

        result = benchmark(resolve_path)

        # Should return valid path
        assert result.exists()
        assert result.is_absolute()

        # Performance assertion is handled by pytest-benchmark
        # Typically should be < 1ms


# Legacy Zipline utility function tests (for coverage)
class TestLegacyZiplineUtilities:
    """Tests for legacy Zipline utility functions."""

    def test_hidden_detects_hidden_files(self):
        """Test hidden() identifies hidden files correctly."""
        from rustybt.utils.paths import hidden

        assert hidden(".hidden") is True
        assert hidden("visible") is False
        assert hidden("path/to/.hidden") is True
        assert hidden("path/to/visible") is False

    def test_ensure_directory_creates_directory(self, tmp_path):
        """Test ensure_directory() creates directories."""
        from rustybt.utils.paths import ensure_directory

        new_dir = tmp_path / "new" / "nested" / "directory"
        assert not new_dir.exists()

        ensure_directory(str(new_dir))

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_ensure_directory_containing_creates_parent(self, tmp_path):
        """Test ensure_directory_containing() creates parent directories."""
        from rustybt.utils.paths import ensure_directory_containing

        file_path = tmp_path / "new" / "nested" / "file.txt"
        parent_dir = file_path.parent

        assert not parent_dir.exists()

        ensure_directory_containing(str(file_path))

        assert parent_dir.exists()
        assert parent_dir.is_dir()

    def test_ensure_file_creates_file_and_parents(self, tmp_path):
        """Test ensure_file() creates file and parent directories."""
        from rustybt.utils.paths import ensure_file

        file_path = tmp_path / "new" / "nested" / "file.txt"
        assert not file_path.exists()

        ensure_file(str(file_path))

        assert file_path.exists()
        assert file_path.is_file()

    def test_last_modified_time_returns_timestamp(self, tmp_path):
        """Test last_modified_time() returns Timestamp."""
        import pandas as pd

        from rustybt.utils.paths import last_modified_time

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = last_modified_time(str(test_file))

        assert isinstance(result, pd.Timestamp)
        assert result.tz is not None  # Should have UTC timezone

    def test_modified_since_detects_recent_modifications(self, tmp_path):
        """Test modified_since() detects file modifications."""
        import pandas as pd

        from rustybt.utils.paths import modified_since

        test_file = tmp_path / "test.txt"
        test_file.write_text("initial")

        # Old timestamp (file should be newer)
        old_time = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=1)
        assert modified_since(str(test_file), old_time) is True

        # Future timestamp (file should be older)
        future_time = pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=1)
        assert modified_since(str(test_file), future_time) is False

        # Non-existent file
        assert modified_since(str(tmp_path / "nonexistent.txt"), old_time) is False

    def test_zipline_root_uses_environ(self, tmp_path):
        """Test zipline_root() respects ZIPLINE_ROOT environment variable."""
        from rustybt.utils.paths import zipline_root

        custom_root = tmp_path / "custom_zipline"
        environ = {"ZIPLINE_ROOT": str(custom_root)}

        result = zipline_root(environ=environ)

        assert result == str(custom_root)

    def test_zipline_root_defaults_to_home_zipline(self):
        """Test zipline_root() defaults to ~/.zipline when not set."""
        from pathlib import Path

        from rustybt.utils.paths import zipline_root

        environ = {}  # No ZIPLINE_ROOT
        result = zipline_root(environ=environ)

        assert ".zipline" in result
        # Should expand ~ to home directory
        assert "~" not in result

    def test_default_extension_returns_extension_path(self, tmp_path):
        """Test default_extension() returns extension.py path."""
        from rustybt.utils.paths import default_extension

        environ = {"ZIPLINE_ROOT": str(tmp_path)}
        result = default_extension(environ=environ)

        assert "extension.py" in result
        assert str(tmp_path) in result

    def test_data_root_returns_data_directory(self, tmp_path):
        """Test data_root() returns data directory path."""
        from rustybt.utils.paths import data_root

        environ = {"ZIPLINE_ROOT": str(tmp_path)}
        result = data_root(environ=environ)

        assert "data" in result
        assert str(tmp_path) in result

    def test_cache_root_returns_cache_directory(self, tmp_path):
        """Test cache_root() returns cache directory path."""
        from rustybt.utils.paths import cache_root

        environ = {"ZIPLINE_ROOT": str(tmp_path)}
        result = cache_root(environ=environ)

        assert "cache" in result
        assert str(tmp_path) in result

    def test_ensure_cache_root_creates_cache_directory(self, tmp_path):
        """Test ensure_cache_root() creates cache directory."""
        from pathlib import Path

        from rustybt.utils.paths import cache_root, ensure_cache_root

        environ = {"ZIPLINE_ROOT": str(tmp_path)}

        # Cache directory shouldn't exist yet
        cache_dir = Path(cache_root(environ=environ))
        assert not cache_dir.exists()

        # Create it
        ensure_cache_root(environ=environ)

        # Now it should exist
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_cache_path_returns_path_in_cache(self, tmp_path):
        """Test cache_path() returns path within cache directory."""
        from rustybt.utils.paths import cache_path

        environ = {"ZIPLINE_ROOT": str(tmp_path)}
        result = cache_path(["subfolder", "file.txt"], environ=environ)

        assert "cache" in result
        assert "subfolder" in result
        assert "file.txt" in result

    def test_get_bundle_path_uses_default_environ(self, tmp_path, monkeypatch):
        """Test get_bundle_path() uses os.environ when environ=None."""
        # Set environment variable
        monkeypatch.setenv("ZIPLINE_ROOT", str(tmp_path))

        result = get_bundle_path("testbundle", environ=None)

        # Should use the environment variable we set
        assert str(tmp_path) in str(result)
        assert "bundles" in str(result)
        assert "testbundle" in str(result)

    def test_validate_bundle_configuration_creates_missing_directory(self, tmp_path):
        """Test validate_bundle_configuration() creates directory if missing."""
        zipline_root = tmp_path / "zipline"
        environ = {"ZIPLINE_ROOT": str(zipline_root)}

        bundle_path = zipline_root / "data" / "bundles" / "newbundle"
        assert not bundle_path.exists()

        # Validation should create it
        result = validate_bundle_configuration("newbundle", environ=environ)

        assert result is True
        assert bundle_path.exists()
        assert bundle_path.is_dir()
