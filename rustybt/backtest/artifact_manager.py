"""Backtest artifact management with unique ID generation and directory structure.

This module provides the BacktestArtifactManager class for managing backtest outputs,
including unique ID generation, directory creation, path management, and strategy
code capture.
"""

import json
import os
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from rustybt.exceptions import RustyBTError

logger = structlog.get_logger(__name__)


class BacktestArtifactError(RustyBTError):
    """Exception raised for backtest artifact management errors."""

    pass


class BacktestArtifactManager:
    """Manages backtest output artifacts with unique IDs and directory structure.

    This class handles:
    - Thread-safe generation of unique backtest IDs
    - Creation of organized directory structures for backtest outputs
    - Validation of directory write permissions
    - Logging of backtest initialization

    The directory structure created is:
        backtests/
        └── {backtest_id}/
            ├── results/      # For CSV, Parquet, reports
            ├── code/         # For strategy code capture
            └── metadata/     # For backtest_metadata.json

    Attributes:
        base_dir: Base directory for all backtest outputs
        backtest_id: Unique identifier for this backtest (YYYYMMDD_HHMMSS_mmm format)
        output_dir: Full path to this backtest's output directory

    Example:
        >>> manager = BacktestArtifactManager(base_dir="backtests")
        >>> manager.create_directory_structure()
        >>> print(manager.backtest_id)
        '20251018_143527_123'
        >>> print(manager.output_dir)
        PosixPath('backtests/20251018_143527_123')
    """

    # Class-level lock for thread-safe ID generation
    _id_generation_lock = threading.Lock()

    def __init__(
        self,
        base_dir: str = "backtests",
        enabled: bool = True,
        code_capture_enabled: bool = True,
    ) -> None:
        """Initialize BacktestArtifactManager.

        Args:
            base_dir: Base directory for backtest outputs (default: "backtests")
                     Can be absolute or relative. Relative paths are resolved to
                     ~/.zipline/backtests/ for consistency with bundle storage.
            enabled: Whether artifact management is enabled (default: True)
            code_capture_enabled: Whether code capture is enabled (default: True)

        Raises:
            BacktestArtifactError: If base_dir is not writable when enabled
        """
        # Resolve base_dir to absolute path
        base_path = Path(base_dir)
        if not base_path.is_absolute():
            # Use central storage for relative paths (like bundle storage)
            from rustybt.utils.paths import zipline_root

            zipline_dir = Path(zipline_root())
            self.base_dir = zipline_dir / base_path
        else:
            self.base_dir = base_path

        self.enabled = enabled
        self.code_capture_enabled = code_capture_enabled
        self._backtest_id: str | None = None
        self._output_dir: Path | None = None

        if self.enabled:
            self._validate_base_directory()

    def _validate_base_directory(self) -> None:
        """Validate that base directory exists and is writable.

        Creates the base directory if it doesn't exist.

        Raises:
            BacktestArtifactError: If directory cannot be created or is not writable
        """
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise BacktestArtifactError(
                f"Failed to create base directory '{self.base_dir}': {e}"
            ) from e

        # Check write permissions
        if not os.access(self.base_dir, os.W_OK):
            raise BacktestArtifactError(
                f"Base directory '{self.base_dir}' is not writable. "
                f"Please check directory permissions."
            )

    def generate_backtest_id(self) -> str:
        """Generate unique backtest ID with thread-safe timestamp.

        The ID format is: YYYYMMDD_HHMMSS_mmm (millisecond precision)
        Example: 20251018_143527_123

        Thread-safe: Uses class-level lock to prevent race conditions in concurrent
        backtest execution.

        Returns:
            Unique backtest ID string

        Example:
            >>> manager = BacktestArtifactManager()
            >>> backtest_id = manager.generate_backtest_id()
            >>> len(backtest_id)
            19
        """
        with self._id_generation_lock:
            now = datetime.now()
            # Format: YYYYMMDD_HHMMSS_mmm
            date_time_part = now.strftime("%Y%m%d_%H%M%S")
            milliseconds = f"{now.microsecond // 1000:03d}"
            backtest_id = f"{date_time_part}_{milliseconds}"

            self._backtest_id = backtest_id

            # Small sleep to ensure uniqueness in rapid concurrent generation
            # This ensures millisecond timestamp will be different for next call
            import time

            time.sleep(0.001)

            return backtest_id

    def create_directory_structure(self) -> Path:
        """Create complete directory structure for backtest outputs.

        Creates:
        - backtests/{backtest_id}/
        - backtests/{backtest_id}/results/
        - backtests/{backtest_id}/code/
        - backtests/{backtest_id}/metadata/

        Returns:
            Path to the backtest output directory

        Raises:
            BacktestArtifactError: If directories cannot be created or artifact
                                  management is disabled

        Example:
            >>> manager = BacktestArtifactManager(base_dir="backtests")
            >>> output_dir = manager.create_directory_structure()
            >>> (output_dir / "results").exists()
            True
        """
        if not self.enabled:
            raise BacktestArtifactError(
                "Artifact management is disabled. Cannot create directory structure."
            )

        # Generate ID if not already generated
        if self._backtest_id is None:
            self.generate_backtest_id()

        # At this point _backtest_id is guaranteed to be set
        if self._backtest_id is None:  # Type narrowing for mypy and runtime safety
            raise BacktestArtifactError("Backtest ID generation failed unexpectedly")

        # Create main output directory
        self._output_dir = self.base_dir / self._backtest_id
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)

            # Create subdirectories
            subdirs = ["results", "code", "metadata"]
            for subdir in subdirs:
                (self._output_dir / subdir).mkdir(exist_ok=True)

            logger.info(
                "backtest_directory_created",
                backtest_id=self._backtest_id,
                output_dir=str(self._output_dir),
            )

        except OSError as e:
            raise BacktestArtifactError(
                f"Failed to create directory structure at '{self._output_dir}': {e}"
            ) from e

        return self._output_dir

    @property
    def backtest_id(self) -> str | None:
        """Get the backtest ID.

        Returns:
            Backtest ID string or None if not yet generated
        """
        return self._backtest_id

    @property
    def output_dir(self) -> Path | None:
        """Get the output directory path.

        Returns:
            Path to output directory or None if not yet created
        """
        return self._output_dir

    def get_results_dir(self) -> Path:
        """Get path to results subdirectory.

        Returns:
            Path to results directory

        Raises:
            BacktestArtifactError: If directory structure not yet created
        """
        if self._output_dir is None:
            raise BacktestArtifactError(
                "Directory structure not created. Call create_directory_structure() first."
            )
        return self._output_dir / "results"

    def get_code_dir(self) -> Path:
        """Get path to code subdirectory.

        Returns:
            Path to code directory

        Raises:
            BacktestArtifactError: If directory structure not yet created
        """
        if self._output_dir is None:
            raise BacktestArtifactError(
                "Directory structure not created. Call create_directory_structure() first."
            )
        return self._output_dir / "code"

    def get_metadata_dir(self) -> Path:
        """Get path to metadata subdirectory.

        Returns:
            Path to metadata directory

        Raises:
            BacktestArtifactError: If directory structure not yet created
        """
        if self._output_dir is None:
            raise BacktestArtifactError(
                "Directory structure not created. Call create_directory_structure() first."
            )
        return self._output_dir / "metadata"

    def get_output_path(self, filename: str, subdir: str = "results") -> Path:
        """Get output path for a file within backtest directory.

        This method resolves a filename to an absolute path within the backtest
        directory structure. It automatically creates parent directories if they
        don't exist (e.g., for nested paths like 'reports/file.html').

        Args:
            filename: Name of file (can include nested path like 'reports/file.html')
            subdir: Subdirectory within backtest dir ('results', 'code', 'metadata')

        Returns:
            Absolute path to output file

        Raises:
            BacktestArtifactError: If directory structure not yet created or
                                  directory creation fails

        Example:
            >>> manager = BacktestArtifactManager()
            >>> manager.create_directory_structure()
            >>> path = manager.get_output_path('backtest_results.csv')
            >>> print(path)
            /path/to/backtests/20251018_143527_123/results/backtest_results.csv

            >>> path = manager.get_output_path('basic_report.html', subdir='results/reports')
            >>> print(path)
            /path/to/backtests/20251018_143527_123/results/reports/basic_report.html
        """
        if self._output_dir is None:
            raise BacktestArtifactError(
                "Directory structure not created. Call create_directory_structure() first."
            )

        # Construct the full output path
        output_path = self._output_dir / subdir / filename

        # Create parent directories if they don't exist (for nested paths)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise BacktestArtifactError(
                f"Failed to create parent directory for '{output_path}': {e}"
            ) from e

        logger.debug(
            "output_path_resolved",
            filename=filename,
            subdir=subdir,
            output_path=str(output_path),
        )

        return output_path

    def capture_strategy_code(
        self,
        entry_point: Path,
        project_root: Path | None = None,
    ) -> list[Path]:
        """Capture strategy code by analyzing imports and copying files.

        This method uses static import analysis to identify all local modules
        imported by the strategy and copies them to the code/ subdirectory
        while preserving directory structure.

        Args:
            entry_point: Path to strategy entry point file
            project_root: Project root directory (auto-detected if None)

        Returns:
            List of captured file paths (in destination directory)

        Raises:
            BacktestArtifactError: If directory structure not yet created

        Example:
            >>> manager = BacktestArtifactManager()
            >>> manager.create_directory_structure()
            >>> captured = manager.capture_strategy_code(Path("my_strategy.py"))
            >>> print(f"Captured {len(captured)} files")
        """
        if not self.enabled or not self.code_capture_enabled:
            logger.debug("code_capture_disabled")
            return []

        if self._output_dir is None:
            raise BacktestArtifactError(
                "Directory structure not created. Call create_directory_structure() first."
            )

        # Lazy import to avoid circular dependencies
        from rustybt.backtest.code_capture import StrategyCodeCapture

        try:
            capture = StrategyCodeCapture()

            # Auto-detect project root if not provided
            if project_root is None:
                project_root = capture.find_project_root(entry_point)
                logger.debug("project_root_detected", project_root=str(project_root))

            # Analyze imports to find all local files
            local_files = capture.analyze_imports(entry_point, project_root)

            logger.debug(
                "imports_analyzed",
                entry_point=str(entry_point),
                local_files_found=len(local_files),
            )

            # Copy files to code directory
            code_dir = self.get_code_dir()
            captured_files = capture.copy_strategy_files(local_files, code_dir, project_root)

            logger.info(
                "code_captured",
                backtest_id=self._backtest_id,
                files_captured=len(captured_files),
                entry_point=str(entry_point),
            )

            return captured_files

        except Exception as e:  # noqa: BLE001
            # Log error but don't fail backtest - catch all errors during code capture
            # Using broad Exception is intentional: ensures backtest never fails due to
            # code capture issues (AC6 requirement). This catches OSError, ImportError,
            # CodeCaptureError, and any unexpected errors during code analysis.
            logger.error(
                "code_capture_failed",
                backtest_id=self._backtest_id,
                entry_point=str(entry_point),
                error=str(e),
                error_type=type(e).__name__,
            )
            # Return empty list on failure
            return []

    def link_backtest_to_bundles(self) -> list[str] | None:
        """Link backtest to bundles in DataCatalog.

        Returns:
            List of bundle names linked, or None if unavailable

        Example:
            >>> manager = BacktestArtifactManager()
            >>> manager.generate_backtest_id()
            >>> bundle_names = manager.link_backtest_to_bundles()
            >>> if bundle_names:
            ...     print(f"Linked {len(bundle_names)} bundles")
        """
        if self._backtest_id is None:
            logger.error(
                "link_backtest_failed_no_id",
                error="Backtest ID not generated",
            )
            return None

        try:
            # Import DataCatalog (may not be available in all configurations)
            from rustybt.data.catalog import DataCatalog

            catalog = DataCatalog()

            # Get bundle name (most recently accessed)
            bundle_name = catalog.get_bundle_name()

            if bundle_name == "unknown":
                logger.warning(
                    "no_bundles_found",
                    backtest_id=self._backtest_id,
                )
                return None

            # Link backtest to bundle(s)
            bundle_names = [bundle_name]
            catalog.link_backtest_to_bundles(self._backtest_id, bundle_names)

            logger.info(
                "backtest_bundles_linked",
                backtest_id=self._backtest_id,
                bundle_count=len(bundle_names),
                bundle_names=bundle_names,
            )

            return bundle_names

        except ImportError:
            logger.warning("datacatalog_unavailable", reason="Import failed")
            return None
        except Exception as e:  # noqa: BLE001
            # Using broad Exception is intentional: ensures backtest never fails due to
            # DataCatalog linkage errors (AC6 requirement). This catches OSError,
            # RuntimeError, ValueError, and any unexpected database or catalog errors.
            logger.error(
                "datacatalog_linkage_failed",
                backtest_id=self._backtest_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def get_data_bundle_info(self) -> dict[str, Any] | None:
        """Retrieve data bundle information from DataCatalog.

        Returns:
            Dictionary with bundle_name and bundle_names list, or None if unavailable

        Example:
            >>> manager = BacktestArtifactManager()
            >>> bundle_info = manager.get_data_bundle_info()
            >>> if bundle_info:
            ...     print(f"Bundle: {bundle_info['bundle_name']}")
        """
        try:
            # Import DataCatalog (may not be available in all configurations)
            from rustybt.data.catalog import DataCatalog

            catalog = DataCatalog()

            # Get bundle name (most recently accessed)
            bundle_name = catalog.get_bundle_name()

            if bundle_name == "unknown":
                return None

            # Get all bundles for this backtest (if already linked)
            bundle_names = []
            if self._backtest_id:
                bundle_names = catalog.get_bundles_for_backtest(self._backtest_id)

            # If no bundles linked yet, use current bundle
            if not bundle_names:
                bundle_names = [bundle_name]

            return {
                "bundle_name": bundle_name,
                "bundle_names": bundle_names,
            }

        except ImportError:
            logger.debug("data_catalog_unavailable", reason="Import failed")
            return None
        except Exception as e:  # noqa: BLE001
            # Using broad Exception is intentional: ensures backtest never fails due to
            # DataCatalog query errors (AC6 requirement). This catches OSError,
            # RuntimeError, ValueError, and any unexpected database or catalog errors.
            logger.warning(
                "data_catalog_query_failed",
                backtest_id=self._backtest_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def generate_metadata(
        self,
        strategy_entry_point: Path,
        captured_files: list[Path],
        data_bundle_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate metadata dictionary for backtest.

        Args:
            strategy_entry_point: Absolute path to strategy file
            captured_files: List of captured file paths
            data_bundle_info: Optional data bundle information from DataCatalog

        Returns:
            Metadata dictionary ready for JSON serialization

        Raises:
            BacktestArtifactError: If backtest_id not yet generated

        Example:
            >>> manager = BacktestArtifactManager()
            >>> manager.generate_backtest_id()
            >>> metadata = manager.generate_metadata(
            ...     strategy_entry_point=Path("/path/to/strategy.py"),
            ...     captured_files=[Path("strategy.py"), Path("utils/indicators.py")]
            ... )
            >>> print(metadata['backtest_id'])
        """
        if self._backtest_id is None:
            raise BacktestArtifactError(
                "Backtest ID not generated. Call generate_backtest_id() first."
            )

        # Get framework version
        try:
            from rustybt import __version__ as framework_version
        except ImportError:
            framework_version = "unknown"

        # Get Python version
        python_version = sys.version.split()[0]  # e.g., "3.12.1"

        # Generate timestamp in ISO8601 format
        timestamp = datetime.now(UTC).isoformat()

        # Convert captured files to relative paths for readability
        captured_files_rel: list[str] = []
        for f in captured_files:
            try:
                # Try to make path relative to strategy entry point parent
                if strategy_entry_point.parent and f.is_relative_to(strategy_entry_point.parent):
                    captured_files_rel.append(str(f.relative_to(strategy_entry_point.parent)))
                else:
                    captured_files_rel.append(str(f))
            except (ValueError, AttributeError):
                # Fallback to string representation
                captured_files_rel.append(str(f))

        metadata: dict[str, Any] = {
            "backtest_id": self._backtest_id,
            "timestamp": timestamp,
            "framework_version": framework_version,
            "python_version": python_version,
            "strategy_entry_point": str(strategy_entry_point),
            "captured_files": captured_files_rel,
            "data_bundle_info": data_bundle_info,
        }

        logger.debug("metadata_generated", backtest_id=self._backtest_id)

        return metadata

    def write_metadata(self, metadata: dict[str, Any]) -> None:
        """Write metadata to JSON file.

        Args:
            metadata: Metadata dictionary to write

        Note:
            This method will not raise exceptions - errors are logged only.
            This ensures metadata write failures don't fail the backtest.

        Example:
            >>> manager = BacktestArtifactManager()
            >>> manager.create_directory_structure()
            >>> metadata = manager.generate_metadata(...)
            >>> manager.write_metadata(metadata)
        """
        if self._output_dir is None:
            logger.error(
                "metadata_write_failed_no_output_dir",
                backtest_id=self._backtest_id,
                error="Output directory not created",
            )
            return

        metadata_path = self._output_dir / "metadata" / "backtest_metadata.json"

        try:
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info("metadata_written", path=str(metadata_path))

        except OSError as e:
            # Catch expected file I/O errors (OSError includes IOError and PermissionError)
            logger.error(
                "metadata_write_failed",
                path=str(metadata_path),
                backtest_id=self._backtest_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't raise - metadata write failure shouldn't fail backtest
