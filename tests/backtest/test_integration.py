"""Integration tests for BacktestArtifactManager with TradingAlgorithm.

Tests cover:
- Artifact manager module imports correctly
- BacktestArtifactManager is accessible from rustybt.backtest
- Integration with algorithm.py imports correctly
- Code capture integration with backtest workflow
"""

from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from rustybt.backtest.artifact_manager import (
    BacktestArtifactError,
    BacktestArtifactManager,
)
from rustybt.backtest.code_capture import StrategyCodeCapture


class TestModuleIntegration:
    """Test module integration and imports."""

    def test_artifact_manager_importable_from_backtest(self):
        """Verify BacktestArtifactManager can be imported from backtest package."""
        from rustybt.backtest import BacktestArtifactManager as Manager

        assert Manager is not None
        assert Manager == BacktestArtifactManager

    def test_artifact_error_importable(self):
        """Verify BacktestArtifactError is accessible."""
        from rustybt.backtest.artifact_manager import BacktestArtifactError as Error

        assert Error is not None
        assert issubclass(Error, Exception)

    def test_algorithm_imports_artifact_manager(self):
        """Verify algorithm.py successfully imports BacktestArtifactManager."""
        # This will fail if there's an import error in algorithm.py
        from rustybt import TradingAlgorithm

        assert TradingAlgorithm is not None

    def test_artifact_manager_in_algorithm_namespace(self):
        """Verify BacktestArtifactManager is used in algorithm module."""
        import rustybt.algorithm as algo_module

        # Check that the import exists in the module
        assert hasattr(algo_module, "BacktestArtifactManager")


class TestArtifactManagerFunctionality:
    """Test basic artifact manager functionality in integration context."""

    def test_create_manager_with_default_settings(self, tmp_path):
        """Verify artifact manager can be created with default settings."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))

        assert manager.enabled is True
        assert manager.backtest_id is None
        assert manager.output_dir is None

    def test_create_and_use_directory_structure(self, tmp_path):
        """Verify full workflow: create manager, generate ID, create directories."""
        # This simulates what TradingAlgorithm.run() does
        manager = BacktestArtifactManager(base_dir=str(tmp_path / "backtests"))

        # Generate ID
        backtest_id = manager.generate_backtest_id()
        assert backtest_id is not None
        assert len(backtest_id) == 19

        # Create directory structure
        output_dir = manager.create_directory_structure()
        assert output_dir.exists()
        assert (output_dir / "results").exists()
        assert (output_dir / "code").exists()
        assert (output_dir / "metadata").exists()

    def test_disabled_manager_workflow(self, tmp_path):
        """Verify disabled manager behavior (like live trading mode)."""
        # This simulates what happens with live_trading=True
        manager = BacktestArtifactManager(base_dir=str(tmp_path / "backtests"), enabled=False)

        assert manager.enabled is False

        # Should not create directories when disabled
        with pytest.raises(BacktestArtifactError, match="disabled"):
            manager.create_directory_structure()


class TestCodeCaptureIntegration:
    """Test code capture integration with BacktestArtifactManager."""

    @pytest.fixture
    def sample_strategy_project(self, tmp_path):
        """Create sample multi-file strategy project for testing."""
        project_root = tmp_path / "strategy_project"
        project_root.mkdir()

        # Add git marker
        (project_root / ".git").mkdir()

        # Create strategy file
        strategy_file = project_root / "my_strategy.py"
        strategy_file.write_text(
            dedent(
                """
            from utils.indicators import sma, ema
            from utils.helpers import log_trade
            import pandas as pd  # Should be filtered out

            def initialize(context):
                pass

            def handle_data(context, data):
                pass
            """
            )
        )

        # Create utils package
        utils_dir = project_root / "utils"
        utils_dir.mkdir()
        (utils_dir / "__init__.py").touch()
        (utils_dir / "indicators.py").write_text(
            "def sma(data, window): pass\ndef ema(data, window): pass"
        )
        (utils_dir / "helpers.py").write_text("def log_trade(asset, value): pass")

        return project_root, strategy_file

    def test_capture_strategy_code_workflow(self, tmp_path, sample_strategy_project):
        """Verify complete code capture workflow with BacktestArtifactManager."""
        project_root, strategy_file = sample_strategy_project

        # Create artifact manager
        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=True
        )

        # Create directory structure
        manager.create_directory_structure()

        # Capture strategy code
        captured_files = manager.capture_strategy_code(
            entry_point=strategy_file, project_root=project_root
        )

        # Verify files were captured
        assert len(captured_files) > 0

        # Verify captured files exist in code directory
        code_dir = manager.get_code_dir()
        assert (code_dir / "my_strategy.py").exists()
        assert (code_dir / "utils" / "indicators.py").exists()
        assert (code_dir / "utils" / "helpers.py").exists()

    def test_capture_strategy_code_disabled(self, tmp_path, sample_strategy_project):
        """Verify code capture can be disabled."""
        project_root, strategy_file = sample_strategy_project

        # Create artifact manager with code capture disabled
        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=False
        )

        # Create directory structure
        manager.create_directory_structure()

        # Attempt to capture strategy code
        captured_files = manager.capture_strategy_code(
            entry_point=strategy_file, project_root=project_root
        )

        # Should return empty list when disabled
        assert len(captured_files) == 0

    def test_capture_strategy_code_auto_detect_project_root(
        self, tmp_path, sample_strategy_project
    ):
        """Verify project root auto-detection in code capture."""
        project_root, strategy_file = sample_strategy_project

        # Create artifact manager
        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=True
        )

        # Create directory structure
        manager.create_directory_structure()

        # Capture without explicit project_root (should auto-detect)
        captured_files = manager.capture_strategy_code(entry_point=strategy_file)

        # Should still work
        assert len(captured_files) > 0
        code_dir = manager.get_code_dir()
        assert (code_dir / "my_strategy.py").exists()

    def test_capture_strategy_code_handles_errors_gracefully(self, tmp_path):
        """Verify code capture errors don't fail backtest."""
        # Create artifact manager
        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=True
        )

        # Create directory structure
        manager.create_directory_structure()

        # Attempt to capture with invalid entry point
        nonexistent = tmp_path / "nonexistent.py"
        captured_files = manager.capture_strategy_code(entry_point=nonexistent)

        # Should return empty list, not raise
        assert len(captured_files) == 0

    def test_capture_strategy_single_file_no_imports(self, tmp_path):
        """Verify single-file strategy with no local imports."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        # Create simple strategy with no local imports
        strategy_file = project_root / "simple_strategy.py"
        strategy_file.write_text(
            dedent(
                """
            import pandas as pd

            def initialize(context):
                context.asset = symbol('AAPL')

            def handle_data(context, data):
                pass
            """
            )
        )

        # Create artifact manager
        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=True
        )

        # Create directory structure
        manager.create_directory_structure()

        # Capture strategy code
        captured_files = manager.capture_strategy_code(
            entry_point=strategy_file, project_root=project_root
        )

        # Should capture only the strategy file itself
        assert len(captured_files) == 1
        code_dir = manager.get_code_dir()
        assert (code_dir / "simple_strategy.py").exists()

        # Verify content matches
        captured_content = (code_dir / "simple_strategy.py").read_text()
        assert "def initialize(context):" in captured_content

    def test_capture_preserves_directory_structure(self, tmp_path):
        """Verify nested directory structure is preserved."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        # Create nested structure
        strategies_dir = project_root / "strategies" / "momentum"
        strategies_dir.mkdir(parents=True)
        utils_dir = project_root / "utils" / "technical"
        utils_dir.mkdir(parents=True)

        # Create files
        (utils_dir / "__init__.py").touch()
        (utils_dir / "indicators.py").write_text("def rsi(): pass")

        strategy_file = strategies_dir / "strategy.py"
        strategy_file.write_text("from utils.technical.indicators import rsi")

        # Create artifact manager
        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=True
        )

        # Create directory structure
        manager.create_directory_structure()

        # Capture strategy code
        captured_files = manager.capture_strategy_code(
            entry_point=strategy_file, project_root=project_root
        )

        # Verify nested structure preserved
        code_dir = manager.get_code_dir()
        assert (code_dir / "strategies" / "momentum" / "strategy.py").exists()
        assert (code_dir / "utils" / "technical" / "indicators.py").exists()


class TestMetadataGenerationIntegration:
    """Integration tests for metadata generation workflow."""

    def test_metadata_generation_workflow(self, tmp_path):
        """Verify complete metadata generation workflow."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path / "backtests"))

        # Create directory structure
        manager.create_directory_structure()

        # Create sample strategy file
        strategy_file = tmp_path / "strategy.py"
        strategy_file.write_text("def initialize(context): pass")

        # Generate metadata
        metadata = manager.generate_metadata(
            strategy_entry_point=strategy_file,
            captured_files=[strategy_file],
            data_bundle_info={"bundle_name": "test", "dataset_ids": ["id1"]},
        )

        # Verify all fields present
        assert "backtest_id" in metadata
        assert "timestamp" in metadata
        assert "framework_version" in metadata
        assert "python_version" in metadata
        assert "strategy_entry_point" in metadata
        assert "captured_files" in metadata
        assert "data_bundle_info" in metadata

        # Write metadata
        manager.write_metadata(metadata)

        # Verify file exists and is readable
        metadata_path = manager.output_dir / "metadata" / "backtest_metadata.json"
        assert metadata_path.exists()

        import json

        with open(metadata_path) as f:
            loaded_metadata = json.load(f)

        assert loaded_metadata == metadata

    def test_metadata_with_code_capture_integration(self, tmp_path):
        """Verify metadata generation with code capture."""
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        # Create strategy with imports
        strategy_file = project_root / "my_strategy.py"
        strategy_file.write_text(
            dedent(
                """
                import pandas as pd
                from utils.helpers import helper_func

                def initialize(context):
                    pass
            """
            )
        )

        # Create utils module
        utils_dir = project_root / "utils"
        utils_dir.mkdir()
        (utils_dir / "__init__.py").touch()
        (utils_dir / "helpers.py").write_text("def helper_func(): pass")

        # Create artifact manager
        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=True
        )
        manager.create_directory_structure()

        # Capture code
        captured_files = manager.capture_strategy_code(
            entry_point=strategy_file, project_root=project_root
        )

        # Generate metadata with captured files
        metadata = manager.generate_metadata(
            strategy_entry_point=strategy_file, captured_files=captured_files
        )

        # Verify captured files in metadata
        assert len(metadata["captured_files"]) > 0
        assert any("my_strategy.py" in str(f) for f in metadata["captured_files"])

        # Write and verify
        manager.write_metadata(metadata)
        metadata_path = manager.output_dir / "metadata" / "backtest_metadata.json"
        assert metadata_path.exists()

    def test_metadata_generation_error_handling(self, tmp_path):
        """Verify metadata generation handles errors gracefully."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path / "backtests"))
        manager.create_directory_structure()

        # Test write without valid metadata directory (simulate permission error scenario)
        import os

        metadata_dir = manager.output_dir / "metadata"

        # Make directory read-only
        original_mode = metadata_dir.stat().st_mode
        os.chmod(metadata_dir, 0o444)

        try:
            # This should not raise, just log error
            metadata = {"backtest_id": "test", "timestamp": "2025-01-01T00:00:00Z"}
            manager.write_metadata(metadata)
            # If we get here, error was handled gracefully

        finally:
            # Restore permissions
            os.chmod(metadata_dir, original_mode)

    def test_metadata_without_datacatalog(self, tmp_path):
        """Verify metadata generation when DataCatalog is unavailable."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path / "backtests"))
        manager.create_directory_structure()

        # Get data bundle info (DataCatalog not available in test environment)
        bundle_info = manager.get_data_bundle_info()

        # Should return None gracefully
        assert bundle_info is None

        # Generate metadata with None bundle info
        strategy_file = tmp_path / "strategy.py"
        strategy_file.write_text("pass")

        metadata = manager.generate_metadata(
            strategy_entry_point=strategy_file, captured_files=[], data_bundle_info=bundle_info
        )

        # data_bundle_info should be None in metadata
        assert metadata["data_bundle_info"] is None

    def test_code_capture_with_nonexistent_file(self, tmp_path):
        """Verify code capture handles nonexistent files gracefully."""
        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=True
        )
        manager.create_directory_structure()

        # Try to capture nonexistent file
        nonexistent = tmp_path / "nonexistent.py"
        captured = manager.capture_strategy_code(entry_point=nonexistent)

        # Should return empty list, not raise
        assert captured == []

    def test_code_capture_with_import_errors(self, tmp_path):
        """Verify code capture handles files with import errors gracefully."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        # Create file with circular import or syntax error
        strategy_file = project_root / "bad_strategy.py"
        strategy_file.write_text(
            dedent(
                """
                from nonexistent_module import something
                import missing_local_module

                def initialize(context):
                    pass
            """
            )
        )

        manager = BacktestArtifactManager(
            base_dir=str(tmp_path / "backtests"), code_capture_enabled=True
        )
        manager.create_directory_structure()

        # Should handle gracefully (may capture just the entry point)
        captured = manager.capture_strategy_code(
            entry_point=strategy_file, project_root=project_root
        )

        # Should not raise, may return empty or partial list
        assert isinstance(captured, list)

    def test_get_output_path_edge_cases(self, tmp_path):
        """Test get_output_path with various edge cases."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path / "backtests"))
        manager.create_directory_structure()

        # Test deeply nested path
        deep_path = manager.get_output_path("a/b/c/d/file.txt", subdir="results")
        assert deep_path.parent.exists()
        assert "a/b/c/d" in str(deep_path) or "a\\b\\c\\d" in str(deep_path)

        # Test path with special characters
        special_path = manager.get_output_path("file-with_special.chars.txt")
        assert special_path.name == "file-with_special.chars.txt"

        # Test empty subdirectory (should use results by default)
        default_path = manager.get_output_path("test.csv")
        assert "results" in str(default_path)

    def test_backtest_id_not_generated_error(self, tmp_path):
        """Verify generate_metadata fails if backtest_id not generated."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path / "backtests"))

        # Don't generate backtest_id or create directory
        strategy_file = tmp_path / "strategy.py"
        strategy_file.write_text("pass")

        # Should raise error
        with pytest.raises(BacktestArtifactError, match="Backtest ID not generated"):
            manager.generate_metadata(strategy_entry_point=strategy_file, captured_files=[])

    def test_metadata_write_without_output_dir(self, tmp_path):
        """Verify write_metadata handles missing output_dir gracefully."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path / "backtests"))

        # Don't create directory structure
        metadata = {"backtest_id": "test", "timestamp": "2025-01-01T00:00:00Z"}

        # Should not raise, just log error
        manager.write_metadata(metadata)
        # If we get here, it was handled gracefully

    def test_directory_creation_failure_handling(self, tmp_path):
        """Test handling when directory creation fails."""
        # Create a file where we want a directory
        blocking_file = tmp_path / "backtests"
        blocking_file.write_text("blocking")

        # Should raise BacktestArtifactError
        with pytest.raises(BacktestArtifactError, match="Failed to create base directory"):
            BacktestArtifactManager(base_dir=str(blocking_file))


class TestDataCatalogIntegrationEnd2End:
    """Integration tests for DataCatalog linkage (Story X3.7)."""

    @pytest.fixture
    def setup_database(self, tmp_path):
        """Create test database with schema."""
        import sqlalchemy as sa

        from rustybt.assets.asset_db_schema import backtest_data_links, bundle_metadata, metadata

        db_path = tmp_path / "test_assets.db"
        engine = sa.create_engine(f"sqlite:///{db_path}")

        # Create tables
        metadata.create_all(engine)

        # Insert sample bundle
        with engine.begin() as conn:
            conn.execute(
                bundle_metadata.insert().values(
                    bundle_name="test_bundle",
                    source_type="csv",
                    fetch_timestamp=1234567890,
                    created_at=1234567890,
                    updated_at=1234567890,
                )
            )

        return db_path

    def test_full_backtest_datacatalog_workflow(self, tmp_path, setup_database):
        """Test complete workflow: backtest → link to bundle → query metadata."""
        from rustybt.data.catalog import DataCatalog

        # Setup DataCatalog with test database
        catalog = DataCatalog(db_path=str(setup_database))

        # Create artifact manager
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_id = manager.generate_backtest_id()

        # Mock DataCatalog module in sys.modules to handle local imports
        mock_catalog_class = Mock(return_value=catalog)
        with patch.dict(
            "sys.modules", {"rustybt.data.catalog": Mock(DataCatalog=mock_catalog_class)}
        ):
            # Link backtest to bundles
            bundle_names = manager.link_backtest_to_bundles()

        assert bundle_names == ["test_bundle"]

        # Verify linkage in database
        linked_bundles = catalog.get_bundles_for_backtest(backtest_id)
        assert "test_bundle" in linked_bundles

    def test_backtest_with_multiple_bundles(self, tmp_path, setup_database):
        """Test backtest using multiple data bundles."""
        import sqlalchemy as sa

        from rustybt.assets.asset_db_schema import bundle_metadata
        from rustybt.data.catalog import DataCatalog

        # Add second bundle
        engine = sa.create_engine(f"sqlite:///{setup_database}")
        with engine.begin() as conn:
            conn.execute(
                bundle_metadata.insert().values(
                    bundle_name="test_bundle_2",
                    source_type="yfinance",
                    fetch_timestamp=1234567890,
                    created_at=1234567890,
                    updated_at=1234567891,  # More recent
                )
            )

        catalog = DataCatalog(db_path=str(setup_database))

        # Create artifact manager
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_id = manager.generate_backtest_id()

        # Manually link to multiple bundles
        catalog.link_backtest_to_bundles(backtest_id, ["test_bundle", "test_bundle_2"])

        # Verify multiple bundles linked
        linked_bundles = catalog.get_bundles_for_backtest(backtest_id)
        assert len(linked_bundles) == 2
        assert "test_bundle" in linked_bundles
        assert "test_bundle_2" in linked_bundles

    def test_metadata_includes_bundle_info(self, tmp_path, setup_database):
        """Test that generated metadata includes bundle information."""
        from rustybt.data.catalog import DataCatalog

        catalog = DataCatalog(db_path=str(setup_database))

        # Create artifact manager
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        manager.generate_backtest_id()
        manager.create_directory_structure()

        # Mock DataCatalog module in sys.modules to handle local imports
        mock_catalog_class = Mock(return_value=catalog)
        with patch.dict(
            "sys.modules", {"rustybt.data.catalog": Mock(DataCatalog=mock_catalog_class)}
        ):
            # Get bundle info
            bundle_info = manager.get_data_bundle_info()

        # Create strategy file
        strategy = tmp_path / "strategy.py"
        strategy.write_text("def initialize(context): pass")

        # Generate metadata with bundle info
        metadata = manager.generate_metadata(
            strategy_entry_point=strategy,
            captured_files=[],
            data_bundle_info=bundle_info,
        )

        # Write metadata
        manager.write_metadata(metadata)

        # Verify metadata file contains bundle info
        import json

        metadata_path = manager.output_dir / "metadata" / "backtest_metadata.json"
        with open(metadata_path) as f:
            loaded_metadata = json.load(f)

        assert "data_bundle_info" in loaded_metadata
        assert loaded_metadata["data_bundle_info"]["bundle_name"] == "test_bundle"

    def test_datacatalog_unavailable_graceful_degradation(self, tmp_path):
        """Test backtest continues when DataCatalog unavailable (AC4)."""
        # Create artifact manager
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        manager.generate_backtest_id()
        manager.create_directory_structure()

        # Mock DataCatalog import to fail
        mock_module = Mock()
        mock_module.DataCatalog.side_effect = ImportError("DataCatalog not available")

        with patch.dict("sys.modules", {"rustybt.data.catalog": mock_module}):
            # Should not raise, should return None
            bundle_names = manager.link_backtest_to_bundles()
            assert bundle_names is None

            bundle_info = manager.get_data_bundle_info()
            assert bundle_info is None

        # Create strategy file
        strategy = tmp_path / "strategy.py"
        strategy.write_text("def initialize(context): pass")

        # Metadata should still be generated
        metadata = manager.generate_metadata(
            strategy_entry_point=strategy,
            captured_files=[],
            data_bundle_info=None,
        )

        assert metadata["data_bundle_info"] is None
        assert metadata["backtest_id"] is not None

    def test_query_backtests_by_bundle(self, tmp_path, setup_database):
        """Test querying which backtests used a specific bundle."""
        from rustybt.data.catalog import DataCatalog

        catalog = DataCatalog(db_path=str(setup_database))

        # Link multiple backtests to same bundle
        backtest_ids = []
        for i in range(3):
            manager = BacktestArtifactManager(base_dir=str(tmp_path))
            backtest_id = manager.generate_backtest_id()
            backtest_ids.append(backtest_id)

            catalog.link_backtest_to_bundles(backtest_id, ["test_bundle"])

        # Query backtests using bundle
        backtests = catalog.get_backtests_using_bundle("test_bundle")

        assert len(backtests) == 3
        for bt_id in backtest_ids:
            assert bt_id in backtests

    def test_performance_database_operations(self, tmp_path, setup_database):
        """Test database operations complete within performance requirements (IV3: <500ms)."""
        import time

        from rustybt.data.catalog import DataCatalog

        catalog = DataCatalog(db_path=str(setup_database))

        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        backtest_id = manager.generate_backtest_id()

        # Mock DataCatalog module in sys.modules to handle local imports
        mock_catalog_class = Mock(return_value=catalog)
        with patch.dict(
            "sys.modules", {"rustybt.data.catalog": Mock(DataCatalog=mock_catalog_class)}
        ):
            # Measure database operation time
            start_time = time.time()
            manager.link_backtest_to_bundles()
            elapsed_ms = (time.time() - start_time) * 1000

        # Should complete in <500ms
        assert elapsed_ms < 500
