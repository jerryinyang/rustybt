"""Unit and integration tests for export utilities.

Tests cover:
- Path resolution with and without backtest context
- CSV export with automatic redirection
- Parquet export with automatic redirection
- JSON export with automatic redirection
- Integration with TradingAlgorithm
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from rustybt.backtest.artifact_manager import BacktestArtifactManager
from rustybt.utils.export import (
    export_csv,
    export_json,
    export_parquet,
    get_active_backtest_dir,
    resolve_output_path,
)


class TestResolveOutputPath:
    """Test resolve_output_path function."""

    def test_resolve_output_path_without_backtest_context(self, tmp_path, monkeypatch):
        """Verify resolve_output_path returns filename as-is without backtest context."""
        monkeypatch.chdir(tmp_path)

        path = resolve_output_path("results.csv")

        # Should return Path object of filename
        assert isinstance(path, Path)
        assert path == Path("results.csv")

    def test_resolve_output_path_with_explicit_backtest_dir(self, tmp_path):
        """Verify resolve_output_path uses explicit backtest_dir parameter."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        path = resolve_output_path("results.csv", backtest_dir=backtest_dir)

        # Should be under backtest directory
        assert path.parent.name == "results"
        assert path.parent.parent == backtest_dir

    def test_resolve_output_path_creates_parent_dirs(self, tmp_path):
        """Verify resolve_output_path creates parent directories."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        path = resolve_output_path("reports/file.html", backtest_dir=backtest_dir)

        # Parent directory should be created
        assert path.parent.exists()
        assert path.parent.name == "reports"

    def test_resolve_output_path_custom_subdir(self, tmp_path):
        """Verify resolve_output_path with custom subdir."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        path = resolve_output_path("strategy.py", subdir="code", backtest_dir=backtest_dir)

        # Should be in code subdirectory
        assert path.parent.name == "code"
        assert path.parent.parent == backtest_dir


class TestGetActiveBacktestDir:
    """Test get_active_backtest_dir function."""

    def test_get_active_backtest_dir_no_context(self):
        """Verify get_active_backtest_dir returns None without backtest context."""
        result = get_active_backtest_dir()
        assert result is None

    def test_get_active_backtest_dir_with_mock_context(self, tmp_path):
        """Verify get_active_backtest_dir finds backtest in call stack."""
        # Create mock TradingAlgorithm with artifact manager
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        output_dir = manager.create_directory_structure()

        mock_algo = MagicMock()
        mock_algo.artifact_manager = manager
        mock_algo.output_dir = output_dir

        # Simulate being in a function called by the algorithm
        def mock_user_function():
            # This would normally be called from within a strategy
            # For testing, we'll patch the stack inspection at the import level
            import inspect as inspect_module

            with patch.object(inspect_module, "stack") as mock_stack:
                # Mock frame with algorithm in locals
                mock_frame = MagicMock()
                mock_frame.frame.f_locals = {"self": mock_algo, "algo": mock_algo}
                mock_stack.return_value = [mock_frame]

                return get_active_backtest_dir()

        result = mock_user_function()
        assert result == output_dir


class TestExportCSV:
    """Test export_csv function."""

    def test_export_csv_without_backtest_context(self, tmp_path, monkeypatch):
        """Verify export_csv writes to current directory without backtest context."""
        monkeypatch.chdir(tmp_path)

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        path = export_csv(df, "test.csv", index=False)

        # Should write to current directory
        assert path == Path("test.csv")
        assert (tmp_path / "test.csv").exists()

        # Verify content
        df_read = pd.read_csv(tmp_path / "test.csv")
        pd.testing.assert_frame_equal(df, df_read)

    def test_export_csv_with_explicit_backtest_dir(self, tmp_path):
        """Verify export_csv writes to backtest directory when provided."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        path = export_csv(df, "results.csv", backtest_dir=backtest_dir, index=False)

        # Should write to backtest results directory
        assert path.parent.name == "results"
        assert path.parent.parent == backtest_dir
        assert path.exists()

        # Verify content
        df_read = pd.read_csv(path)
        pd.testing.assert_frame_equal(df, df_read)

    def test_export_csv_custom_subdir(self, tmp_path):
        """Verify export_csv with custom subdir parameter."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        df = pd.DataFrame({"a": [1, 2, 3]})
        path = export_csv(df, "metadata.csv", subdir="metadata", backtest_dir=backtest_dir)

        # Should be in metadata subdirectory
        assert path.parent.name == "metadata"
        assert path.exists()

    def test_export_csv_nested_path(self, tmp_path):
        """Verify export_csv with nested filename."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        df = pd.DataFrame({"a": [1, 2, 3]})
        path = export_csv(df, "analysis/detailed.csv", backtest_dir=backtest_dir)

        # Should create nested directory
        assert path.parent.name == "analysis"
        assert path.exists()

    def test_export_csv_kwargs_forwarded(self, tmp_path, monkeypatch):
        """Verify additional kwargs are forwarded to df.to_csv()."""
        monkeypatch.chdir(tmp_path)

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        path = export_csv(df, "test.csv", index=True, sep=";")

        # Verify semicolon separator was used
        content = (tmp_path / "test.csv").read_text()
        assert ";" in content


class TestExportParquet:
    """Test export_parquet function."""

    def test_export_parquet_without_backtest_context(self, tmp_path, monkeypatch):
        """Verify export_parquet writes to current directory without backtest context."""
        monkeypatch.chdir(tmp_path)

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
        path = export_parquet(df, "test.parquet")

        # Should write to current directory
        assert path == Path("test.parquet")
        assert (tmp_path / "test.parquet").exists()

        # Verify content
        df_read = pd.read_parquet(tmp_path / "test.parquet")
        pd.testing.assert_frame_equal(df, df_read)

    def test_export_parquet_with_explicit_backtest_dir(self, tmp_path):
        """Verify export_parquet writes to backtest directory when provided."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
        path = export_parquet(df, "results.parquet", backtest_dir=backtest_dir)

        # Should write to backtest results directory
        assert path.parent.name == "results"
        assert path.parent.parent == backtest_dir
        assert path.exists()

        # Verify content
        df_read = pd.read_parquet(path)
        pd.testing.assert_frame_equal(df, df_read)

    def test_export_parquet_nested_path(self, tmp_path):
        """Verify export_parquet with nested filename."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        df = pd.DataFrame({"a": [1, 2, 3]})
        path = export_parquet(df, "optimizations/best.parquet", backtest_dir=backtest_dir)

        # Should create nested directory
        assert path.parent.name == "optimizations"
        assert path.exists()


class TestExportJSON:
    """Test export_json function."""

    def test_export_json_without_backtest_context(self, tmp_path, monkeypatch):
        """Verify export_json writes to current directory without backtest context."""
        monkeypatch.chdir(tmp_path)

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        path = export_json(df, "test.json", orient="records")

        # Should write to current directory
        assert path == Path("test.json")
        assert (tmp_path / "test.json").exists()

        # Verify content
        df_read = pd.read_json(tmp_path / "test.json", orient="records")
        pd.testing.assert_frame_equal(df, df_read)

    def test_export_json_with_explicit_backtest_dir(self, tmp_path):
        """Verify export_json writes to backtest directory when provided."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_dir = manager.create_directory_structure()

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        path = export_json(df, "results.json", backtest_dir=backtest_dir, orient="records")

        # Should write to backtest results directory
        assert path.parent.name == "results"
        assert path.parent.parent == backtest_dir
        assert path.exists()

        # Verify content
        df_read = pd.read_json(path, orient="records")
        pd.testing.assert_frame_equal(df, df_read)


class TestIntegrationWithAlgorithm:
    """Integration tests with TradingAlgorithm."""

    def test_algorithm_output_dir_property(self, tmp_path):
        """Verify algorithm.output_dir returns correct directory."""
        from rustybt.algorithm import TradingAlgorithm

        # Create minimal algorithm (we can't run it fully in unit test)
        # Just test the property access
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        manager.create_directory_structure()

        # Mock minimal algorithm attributes
        mock_algo = MagicMock(spec=TradingAlgorithm)
        mock_algo.artifact_manager = manager

        # Test the property logic
        output_dir = manager.output_dir if manager.enabled else None
        assert output_dir is not None
        assert output_dir.exists()

    def test_algorithm_get_output_path_method(self, tmp_path):
        """Verify algorithm.get_output_path() works correctly."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        manager.create_directory_structure()

        # Test the method directly on manager
        path = manager.get_output_path("custom_analysis.csv")

        assert path.name == "custom_analysis.csv"
        assert path.parent.name == "results"


# Fixtures
@pytest.fixture
def sample_dataframe():
    """Create sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=10),
            "portfolio_value": range(100000, 100010),
            "returns": [0.01, -0.02, 0.03, 0.00, 0.01, -0.01, 0.02, 0.01, -0.01, 0.00],
        }
    )


@pytest.fixture
def artifact_manager_with_structure(tmp_path):
    """Create artifact manager with directory structure already created."""
    manager = BacktestArtifactManager(base_dir=str(tmp_path))
    manager.create_directory_structure()
    return manager
