"""Strategy code capture via import analysis or explicit YAML specification.

This module provides functionality to capture strategy source code by:
1. Explicit file list in strategy.yaml (if present)
2. Analyzing import statements (fallback)

Copying local module files to backtest output directories enables
reproducibility and audit purposes.
"""

import ast
import importlib.util
import inspect
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import structlog
import yaml

from rustybt.backtest.artifact_manager import BacktestArtifactError

logger = structlog.get_logger(__name__)


class CodeCaptureError(BacktestArtifactError):
    """Exception raised for code capture errors."""

    pass


@dataclass
class EntryPointDetectionResult:
    """Result of entry point detection process.

    Attributes:
        detected_file: Absolute path to detected entry point file, or None if detection failed
        detection_method: Method used to detect entry point
        confidence: Confidence level in detection accuracy (1.0 = certain, 0.0 = failed)
        fallback_used: Whether fallback strategy was used due to primary detection failure
        warnings: Warning messages generated during detection
        execution_context: Detected execution environment
    """

    detected_file: Path | None
    detection_method: Literal["inspect", "ast_analysis", "yaml_override", "fallback", "failed"]
    confidence: float
    fallback_used: bool
    warnings: list[str] = field(default_factory=list)
    execution_context: Literal["file", "notebook", "interactive", "frozen", "unknown"] = "unknown"


@dataclass
class CodeCaptureConfiguration:
    """Configuration for determining which code files to capture during a backtest run.

    Attributes:
        mode: Capture mode determining which files to store
        entry_point_path: Absolute path to detected entry point file
        yaml_path: Absolute path to strategy.yaml configuration
        additional_files: Additional files specified in YAML config
        enabled: Whether code capture is enabled for this backtest
    """

    mode: Literal["entry_point", "yaml", "disabled"]
    entry_point_path: Path | None = None
    yaml_path: Path | None = None
    additional_files: list[Path] = field(default_factory=list)
    enabled: bool = True


class StrategyCodeCapture:
    """Captures strategy code by analyzing imports and copying local modules.

    This class uses Python's AST module to statically analyze import statements
    in strategy files, identifies local project modules (excluding stdlib and
    site-packages), and copies them to the backtest output directory while
    preserving directory structure.

    Example:
        >>> capture = StrategyCodeCapture()
        >>> entry_point = Path("my_strategy.py")
        >>> project_root = Path.cwd()
        >>> dest_dir = Path("backtests/20251018_143527_123/code")
        >>> imports = capture.analyze_imports(entry_point, project_root)
        >>> files = capture.copy_strategy_files(imports, dest_dir, project_root)
        >>> print(f"Captured {len(files)} files")
    """

    def __init__(self, code_capture_mode: str = "import_analysis") -> None:
        """Initialize StrategyCodeCapture.

        Args:
            code_capture_mode: Code capture mode - "import_analysis" (default) or "strategy_yaml"
                Note: If strategy.yaml exists, it always takes precedence regardless of this setting
        """
        # Cache for module specs to avoid repeated lookups
        self._module_spec_cache: dict[str, importlib.machinery.ModuleSpec | None] = {}
        self.code_capture_mode = code_capture_mode

    def detect_entry_point(self) -> EntryPointDetectionResult:
        """Detect the file containing the run_algorithm() call using runtime introspection.

        Uses inspect.stack() to walk up the call stack and identify the file that
        invoked run_algorithm(). Handles edge cases like Jupyter notebooks, interactive
        sessions, and frozen applications.

        Returns:
            EntryPointDetectionResult with detection outcome, confidence, and warnings

        Example:
            >>> capture = StrategyCodeCapture()
            >>> result = capture.detect_entry_point()
            >>> if result.detected_file:
            ...     print(f"Entry point: {result.detected_file}")
            >>> else:
            ...     print(f"Detection failed: {result.warnings}")
        """
        warnings: list[str] = []

        # Detect execution context first
        execution_context = self._detect_execution_context()

        # Handle special contexts that can't use standard detection
        if execution_context == "frozen":
            warnings.append(
                "Frozen application detected - code capture not supported in compiled executables"
            )
            warnings.append("Use strategy.yaml for explicit file list if needed")
            return EntryPointDetectionResult(
                detected_file=None,
                detection_method="failed",
                confidence=0.0,
                fallback_used=True,
                warnings=warnings,
                execution_context=execution_context,
            )

        if execution_context == "interactive":
            warnings.append("Interactive session detected - cannot determine source file")
            warnings.append("Code capture will be skipped unless strategy.yaml is provided")
            return EntryPointDetectionResult(
                detected_file=None,
                detection_method="failed",
                confidence=0.0,
                fallback_used=True,
                warnings=warnings,
                execution_context=execution_context,
            )

        # Try inspect.stack() for standard file or notebook execution
        stack = inspect.stack()

        try:
            # Walk up the call stack looking for run_algorithm call
            for frame_info in stack:
                filename = frame_info.filename

                # Skip framework files (rustybt/*)
                if "rustybt" in Path(filename).parts:
                    continue

                # Skip standard library and site-packages
                if (
                    "site-packages" in filename
                    or "/lib/python" in filename
                    or "\\lib\\python" in filename
                ):
                    continue

                # Skip built-in or special files
                if filename.startswith("<") or filename == "<string>":
                    continue

                # Check if this frame mentions run_algorithm in code context
                code_context = frame_info.code_context
                if code_context and any("run_algorithm" in line for line in code_context):
                    detected_path = Path(filename).resolve()

                    # Special handling for Jupyter notebooks
                    if execution_context == "notebook":
                        warnings.append(f"Jupyter notebook detected: {detected_path.name}")

                        # Try to find the actual .ipynb file instead of the temp IPython file
                        logger.warning(
                            "attempting_notebook_detection",
                            temp_file=str(detected_path),
                            cwd=str(Path.cwd()),
                        )
                        notebook_path = self._detect_jupyter_notebook()

                        if notebook_path:
                            logger.warning(
                                "notebook_path_found",
                                notebook=str(notebook_path),
                                exists=notebook_path.exists(),
                            )

                        if notebook_path and notebook_path.exists():
                            logger.info("notebook_file_detected", notebook=str(notebook_path))
                            return EntryPointDetectionResult(
                                detected_file=notebook_path,
                                detection_method="inspect",
                                confidence=0.9,  # High confidence - we found the actual notebook
                                fallback_used=False,
                                warnings=warnings,
                                execution_context=execution_context,
                            )
                        else:
                            # Could not find .ipynb file, skip code capture for notebooks
                            logger.warning(
                                "notebook_detection_failed",
                                notebook_path=str(notebook_path) if notebook_path else "None",
                                cwd=str(Path.cwd()),
                            )
                            warnings.append("Could not locate .ipynb file for code capture")
                            warnings.append(
                                "Code capture will be skipped for this notebook execution"
                            )
                            return EntryPointDetectionResult(
                                detected_file=None,
                                detection_method="failed",
                                confidence=0.0,
                                fallback_used=True,
                                warnings=warnings,
                                execution_context=execution_context,
                            )

                    # Standard file execution - highest confidence
                    logger.info("entry_point_detected", path=str(detected_path), method="inspect")
                    return EntryPointDetectionResult(
                        detected_file=detected_path,
                        detection_method="inspect",
                        confidence=1.0,
                        fallback_used=False,
                        warnings=warnings,
                        execution_context=execution_context,
                    )

            # No frame with run_algorithm found
            warnings.append("Could not find run_algorithm() in call stack")
            warnings.append("This may occur with dynamic code execution or unusual import patterns")

            # Attempt fallback for Jupyter notebooks
            if execution_context == "notebook":
                notebook_path = self._detect_jupyter_notebook()
                if notebook_path:
                    warnings.append(f"Using fallback detection for notebook: {notebook_path.name}")
                    return EntryPointDetectionResult(
                        detected_file=notebook_path,
                        detection_method="fallback",
                        confidence=0.7,
                        fallback_used=True,
                        warnings=warnings,
                        execution_context=execution_context,
                    )

            # Detection failed
            warnings.append("Code capture will be skipped unless strategy.yaml is provided")
            return EntryPointDetectionResult(
                detected_file=None,
                detection_method="failed",
                confidence=0.0,
                fallback_used=True,
                warnings=warnings,
                execution_context=execution_context,
            )

        except Exception as e:  # noqa: BLE001
            # Catch any unexpected errors during stack inspection
            logger.warning("entry_point_detection_error", error=str(e), error_type=type(e).__name__)
            warnings.append(f"Entry point detection error: {type(e).__name__}")
            warnings.append("Code capture will be skipped unless strategy.yaml is provided")
            return EntryPointDetectionResult(
                detected_file=None,
                detection_method="failed",
                confidence=0.0,
                fallback_used=True,
                warnings=warnings,
                execution_context="unknown",
            )

    def _detect_execution_context(
        self,
    ) -> Literal["file", "notebook", "interactive", "frozen", "unknown"]:
        """Detect the execution environment.

        Returns:
            Execution context type
        """
        # Check for frozen application (PyInstaller, cx_Freeze)
        if getattr(sys, "frozen", False):
            return "frozen"

        # Check for Jupyter/IPython
        try:
            # Try importing IPython to detect notebook environment
            from IPython import get_ipython

            ipython = get_ipython()
            if ipython is not None:
                # Check if running in notebook (not just IPython shell)
                if "IPKernelApp" in ipython.config:
                    return "notebook"
                # IPython shell is still interactive
                return "interactive"
        except ImportError:
            pass

        # Check for interactive session by examining sys.argv and stdin
        if hasattr(sys, "ps1"):  # Python interactive mode
            return "interactive"

        if not sys.argv or sys.argv[0] in ("", "-c", "-m"):
            return "interactive"

        # Default to file execution
        return "file"

    def _detect_jupyter_notebook(self) -> Path | None:
        """Attempt to detect Jupyter notebook filename.

        Returns:
            Path to notebook file or None if cannot determine
        """
        try:
            from IPython import get_ipython

            ipython = get_ipython()
            if ipython is None:
                logger.info("notebook_detection_no_ipython")
                return None

            logger.warning("notebook_detection_starting", cwd=str(Path.cwd()))

            # Strategy 1: Try to get notebook name from __vsc_ipynb_file__ (VS Code Jupyter)
            import sys

            if hasattr(sys, "__vsc_ipynb_file__"):
                notebook_path = Path(sys.__vsc_ipynb_file__)
                logger.warning(
                    "notebook_detection_vscode_attr_found",
                    path=str(notebook_path),
                    exists=notebook_path.exists(),
                    suffix=notebook_path.suffix,
                )
                if notebook_path.exists() and notebook_path.suffix == ".ipynb":
                    logger.warning("notebook_detected_vscode", path=str(notebook_path))
                    return notebook_path

            # Strategy 2: Check current working directory for .ipynb files
            notebook_dir = Path.cwd()
            ipynb_files = list(notebook_dir.glob("*.ipynb"))
            logger.warning(
                "notebook_detection_strategy2",
                notebook_dir=str(notebook_dir),
                found_notebooks=len(ipynb_files),
                notebooks=[str(f) for f in ipynb_files],
            )

            if len(ipynb_files) == 1:
                # Only one notebook in directory, likely the current one
                logger.warning("notebook_detected_single_file", path=str(ipynb_files[0]))
                return ipynb_files[0]

            # Strategy 3: If multiple notebooks, try to find the most recently modified one
            # (assumes user is working on the most recent notebook)
            if len(ipynb_files) > 1:
                most_recent = max(ipynb_files, key=lambda p: p.stat().st_mtime)
                logger.warning(
                    "notebook_detected_recent",
                    path=str(most_recent),
                    total_notebooks=len(ipynb_files),
                )
                return most_recent

            logger.warning("notebook_detection_no_notebooks_found")
            return None

        except (ImportError, AttributeError, Exception) as e:
            # Jupyter notebook detection failed - this is expected in non-notebook environments
            logger.warning(
                "jupyter_notebook_detection_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

        return None

    def analyze_imports(self, entry_point: Path, project_root: Path) -> list[Path]:
        """Extract all local module imports from Python file recursively.

        Uses Python's AST module to parse import statements without executing code.
        Handles various import patterns:
        - import X
        - import X as Y
        - from X import Y
        - from .X import Y (relative imports)
        - from ..X import Y (multi-level relative imports)

        Args:
            entry_point: Path to Python file to analyze
            project_root: Root directory of the project

        Returns:
            List of absolute paths to local module files

        Raises:
            CodeCaptureError: If entry point file cannot be read or parsed

        Example:
            >>> capture = StrategyCodeCapture()
            >>> files = capture.analyze_imports(
            ...     Path("strategies/my_strategy.py"),
            ...     Path("/project")
            ... )
            >>> print([f.name for f in files])
            ['my_strategy.py', 'indicators.py', 'helpers.py']
        """
        if not entry_point.exists():
            raise CodeCaptureError(f"Entry point file not found: {entry_point}")

        # Track analyzed files to avoid infinite loops
        analyzed_files: set[Path] = set()
        local_files: set[Path] = set()

        self._analyze_imports_recursive(entry_point, project_root, analyzed_files, local_files)

        return sorted(local_files)

    def load_strategy_yaml(self, strategy_dir: Path) -> dict[str, Any] | None:
        """Load strategy.yaml if present.

        Args:
            strategy_dir: Directory containing the strategy entry point

        Returns:
            Parsed YAML dict with validated schema, or None if not found or invalid

        Example:
            >>> capture = StrategyCodeCapture()
            >>> config = capture.load_strategy_yaml(Path("my_strategy_dir"))
            >>> if config:
            ...     print(f"Files to capture: {config['files']}")
        """
        yaml_path = strategy_dir / "strategy.yaml"
        if not yaml_path.exists():
            return None

        try:
            with open(yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Validate schema
            if not isinstance(config, dict):
                logger.warning(
                    "strategy_yaml_invalid_format",
                    path=str(yaml_path),
                    error="YAML must contain a dictionary",
                )
                return None

            if "files" not in config:
                logger.warning(
                    "strategy_yaml_missing_files_key",
                    path=str(yaml_path),
                    error="YAML must have 'files' key",
                )
                return None

            if not isinstance(config["files"], list):
                logger.warning(
                    "strategy_yaml_invalid_files_type",
                    path=str(yaml_path),
                    error="'files' must be a list",
                )
                return None

            logger.info(
                "using_strategy_yaml",
                path=str(yaml_path),
                file_count=len(config["files"]),
            )
            return config

        except yaml.YAMLError as e:
            logger.warning(
                "strategy_yaml_parse_error",
                path=str(yaml_path),
                error=str(e),
            )
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "strategy_yaml_load_failed",
                path=str(yaml_path),
                error=str(e),
            )
            return None

    def _analyze_imports_recursive(
        self,
        file_path: Path,
        project_root: Path,
        analyzed_files: set[Path],
        local_files: set[Path],
    ) -> None:
        """Recursively analyze imports in a file.

        Args:
            file_path: Path to Python file to analyze
            project_root: Root directory of the project
            analyzed_files: Set of already analyzed files (to prevent loops)
            local_files: Set of local files found (accumulator)
        """
        # Resolve to absolute path
        file_path = file_path.resolve()

        # Skip if already analyzed
        if file_path in analyzed_files:
            return

        analyzed_files.add(file_path)

        # Add this file to local files if it's within project root
        try:
            file_path.relative_to(project_root)
            local_files.add(file_path)
        except ValueError:
            # File is outside project root, don't include it
            pass

        # Skip non-Python files (binary .so, .pyd, .pyc, .whl, etc.)
        if file_path.suffix not in {".py", ".pyi"}:
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError as e:
            logger.warning(
                "syntax_error_parsing_file",
                file=str(file_path),
                error=str(e),
            )
            return
        except Exception as e:  # noqa: BLE001
            # Catch-all for any file reading errors (permissions, encoding, etc.)
            logger.warning(
                "error_reading_file",
                file=str(file_path),
                error=str(e),
            )
            return

        # Extract module names from import statements
        module_names = self._extract_module_names(tree, file_path, project_root)

        # Resolve module names to file paths and recurse
        for module_name in module_names:
            # Try to resolve module path directly first
            module_path = self._resolve_module_path_from_name(
                module_name, project_root, file_path.parent
            )

            if module_path and module_path not in analyzed_files:
                # Check if it's a local file
                try:
                    module_path.relative_to(project_root)
                    # It's within project root, recurse
                    self._analyze_imports_recursive(
                        module_path, project_root, analyzed_files, local_files
                    )
                except ValueError:
                    # Outside project root, skip
                    pass

    def _extract_module_names(
        self, tree: ast.AST, file_path: Path, project_root: Path
    ) -> list[str]:
        """Extract module names from AST.

        Args:
            tree: Parsed AST
            file_path: Path to the file being analyzed
            project_root: Root directory of the project

        Returns:
            List of module names
        """
        module_names: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # Handles: import X, import X as Y
                for alias in node.names:
                    module_names.append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                # Handles: from X import Y, from .X import Y
                module = node.module or ""  # None for "from . import X"
                level = node.level  # 0 for absolute, 1+ for relative

                if level > 0:
                    # Relative import
                    resolved = self._resolve_relative_import(file_path, module, level, project_root)
                    if resolved:
                        module_names.append(resolved)
                elif module:
                    # Absolute import
                    module_names.append(module)

        return module_names

    def _resolve_relative_import(
        self, entry_point: Path, module: str, level: int, project_root: Path
    ) -> str | None:
        """Resolve relative import to absolute module name.

        Args:
            entry_point: Path to the file containing the import
            module: Module name from import (may be empty string)
            level: Number of dots (1 for '.', 2 for '..', etc.)
            project_root: Root directory of the project

        Returns:
            Absolute module name or None if cannot resolve

        Example:
            entry_point = /project/strategies/momentum/strategy.py
            module = 'utils'
            level = 1  # from .utils import helper

            Returns: 'strategies.momentum.utils'
        """
        try:
            # Get package path by going up 'level' directories
            package_path = entry_point.parent
            for _ in range(level - 1):
                package_path = package_path.parent
                if package_path == package_path.parent:
                    # Reached filesystem root
                    return None

            # Calculate relative path from project root
            try:
                rel_path = package_path.relative_to(project_root)
            except ValueError:
                # Package path is outside project root
                return None

            # Convert path to module name (replace / with .)
            module_parts = list(rel_path.parts)

            if module:
                module_parts.append(module)

            return ".".join(module_parts) if module_parts else None

        except Exception as e:  # noqa: BLE001
            # Catch-all for any path resolution errors
            logger.debug(
                "relative_import_resolution_failed",
                entry_point=str(entry_point),
                module=module,
                level=level,
                error=str(e),
            )
            return None

    def is_local_module(self, module_name: str, project_root: Path) -> bool:
        """Check if module is a local project file.

        Filters out:
        - Standard library modules
        - Site-packages modules
        - Framework modules (rustybt)

        Args:
            module_name: Module name (e.g., 'mypackage.utils')
            project_root: Root directory of the project

        Returns:
            True if module is local to project, False otherwise

        Example:
            >>> capture = StrategyCodeCapture()
            >>> capture.is_local_module('os', Path.cwd())
            False
            >>> capture.is_local_module('my_utils', Path.cwd())
            True
        """
        # Filter out standard library
        if module_name.split(".")[0] in sys.stdlib_module_names:
            return False

        # Try to find module spec
        try:
            spec = self._get_module_spec(module_name)
            if spec is None or spec.origin is None:
                return False

            module_path = Path(spec.origin)

            # Filter out site-packages
            if "site-packages" in module_path.parts:
                return False

            # Filter out framework (rustybt) - unless it's within project root
            if "rustybt" in module_path.parts:
                try:
                    module_path.relative_to(project_root)
                    # rustybt is within project root (local development)
                    return True
                except ValueError:
                    # rustybt is installed package
                    return False

            # Check if module is within project root
            try:
                module_path.relative_to(project_root)
                return True
            except ValueError:
                return False

        except (ModuleNotFoundError, ImportError, ValueError):
            return False

    def _get_module_spec(self, module_name: str) -> importlib.machinery.ModuleSpec | None:
        """Get module spec with caching.

        Args:
            module_name: Module name

        Returns:
            Module spec or None
        """
        if module_name not in self._module_spec_cache:
            try:
                self._module_spec_cache[module_name] = importlib.util.find_spec(module_name)
            except (ModuleNotFoundError, ImportError, ValueError):
                self._module_spec_cache[module_name] = None

        return self._module_spec_cache[module_name]

    def _resolve_module_path(self, module_name: str) -> Path | None:
        """Resolve module name to file path.

        Args:
            module_name: Module name

        Returns:
            Path to module file or None
        """
        spec = self._get_module_spec(module_name)
        if spec and spec.origin:
            return Path(spec.origin)
        return None

    def _resolve_module_path_from_name(
        self, module_name: str, project_root: Path, current_dir: Path
    ) -> Path | None:
        """Resolve module name to file path using filesystem search.

        This method attempts to resolve modules without relying on sys.path,
        which is useful for analyzing code that isn't installed.

        Args:
            module_name: Module name (e.g., 'utils.helpers')
            project_root: Project root directory
            current_dir: Directory of the importing file

        Returns:
            Path to module file or None
        """
        # Filter out stdlib modules
        if module_name.split(".")[0] in sys.stdlib_module_names:
            return None

        # Try importlib first (for installed packages)
        spec = self._get_module_spec(module_name)
        if spec and spec.origin:
            module_path = Path(spec.origin)
            # Only return if it's within project root
            try:
                module_path.relative_to(project_root)
                return module_path
            except ValueError:
                # Not in project root
                pass

        # Fall back to filesystem search within project root
        # Convert module name to relative path
        parts = module_name.split(".")

        # Try as package (__init__.py)
        package_path = project_root / Path(*parts) / "__init__.py"
        if package_path.exists():
            return package_path

        # Try as module (.py file)
        module_path = project_root / Path(*parts[:-1]) / f"{parts[-1]}.py"
        if module_path.exists():
            return module_path

        # Try relative to current directory
        package_path = current_dir / Path(*parts) / "__init__.py"
        if package_path.exists():
            return package_path

        module_path = current_dir / Path(*parts[:-1]) / f"{parts[-1]}.py"
        if module_path.exists():
            return module_path

        return None

    def copy_strategy_files(
        self, files: list[Path], dest_dir: Path, project_root: Path
    ) -> list[Path]:
        """Copy strategy files to destination, preserving directory structure.

        Args:
            files: List of absolute paths to strategy files
            dest_dir: Destination directory (backtests/{id}/code/)
            project_root: Project root directory for relative path calculation

        Returns:
            List of successfully copied file paths (destinations)

        Example:
            >>> capture = StrategyCodeCapture()
            >>> files = [Path("/project/strategies/my_strategy.py")]
            >>> dest_dir = Path("backtests/20251018_143527_123/code")
            >>> copied = capture.copy_strategy_files(files, dest_dir, Path("/project"))
            >>> print(copied)
            [PosixPath('backtests/20251018_143527_123/code/strategies/my_strategy.py')]
        """
        copied_files: list[Path] = []

        for file_path in files:
            try:
                # Calculate relative path from project root
                try:
                    rel_path = file_path.relative_to(project_root)
                except ValueError:
                    # File is outside project root, use filename only
                    logger.warning(
                        "file_outside_project_root",
                        file=str(file_path),
                        project_root=str(project_root),
                    )
                    rel_path = Path(file_path.name)

                # Create destination path preserving structure
                dest_path = dest_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file with metadata (timestamps)
                shutil.copy2(file_path, dest_path)

                copied_files.append(dest_path)

                logger.debug(
                    "file_captured",
                    source=str(file_path),
                    destination=str(dest_path),
                )

            except Exception as e:  # noqa: BLE001
                # Catch-all for any file copy errors (permissions, disk space, etc.)
                logger.warning(
                    "file_capture_failed",
                    file=str(file_path),
                    error=str(e),
                )
                # Don't fail backtest if file capture fails

        return copied_files

    def _capture_from_yaml(
        self, config: dict[str, Any], strategy_dir: Path, dest_dir: Path
    ) -> list[Path]:
        """Capture files listed in strategy.yaml.

        Args:
            config: Parsed YAML configuration
            strategy_dir: Directory containing strategy.yaml
            dest_dir: Destination directory for captured files

        Returns:
            List of successfully copied file paths (destinations)

        Example:
            >>> capture = StrategyCodeCapture()
            >>> config = {'files': ['my_strategy.py', 'utils/indicators.py']}
            >>> copied = capture._capture_from_yaml(
            ...     config,
            ...     Path("my_strategy_dir"),
            ...     Path("backtests/20251018_143527_123/code")
            ... )
        """
        captured_files: list[Path] = []

        for rel_path_str in config["files"]:
            file_path = strategy_dir / rel_path_str

            if not file_path.exists():
                logger.warning(
                    "yaml_file_not_found",
                    file=str(file_path),
                    relative_path=rel_path_str,
                )
                continue

            try:
                # Calculate destination path preserving structure
                dest_path = dest_dir / rel_path_str
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file with metadata (timestamps)
                shutil.copy2(file_path, dest_path)

                captured_files.append(dest_path)

                logger.debug(
                    "file_captured_from_yaml",
                    source=str(file_path),
                    destination=str(dest_path),
                )

            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "yaml_file_capture_failed",
                    file=str(file_path),
                    error=str(e),
                )
                # Continue processing other files

        return captured_files

    def capture_strategy_code(
        self, entry_point: Path, dest_dir: Path, project_root: Path | None = None
    ) -> tuple[list[Path], EntryPointDetectionResult]:
        """Capture strategy code using YAML (if present) or entry point detection.

        NEW BEHAVIOR: Captures only the entry point file by default (90%+ storage reduction).

        Precedence Rule:
        1. strategy.yaml exists → use YAML file list (explicit always wins)
        2. No YAML → detect entry point using inspect.stack(), capture only that file
        3. Detection fails → skip code capture gracefully (don't fail backtest)

        Args:
            entry_point: Path to strategy entry point file
            dest_dir: Destination directory (backtests/{id}/code/)
            project_root: Project root directory (auto-detected if None)

        Returns:
            Tuple of (captured_files, detection_result):
                - captured_files: List of captured file paths (destinations)
                - detection_result: EntryPointDetectionResult with metadata

        Example:
            >>> capture = StrategyCodeCapture()
            >>> files, detection = capture.capture_strategy_code(
            ...     Path("strategies/my_strategy.py"),
            ...     Path("backtests/20251018_143527_123/code")
            ... )
            >>> print(f"Captured {len(files)} files with method {detection.detection_method}")
        """
        if project_root is None:
            project_root = self.find_project_root(entry_point)

        strategy_dir = entry_point.parent

        # Rule 1: YAML file exists → use it (explicit always wins)
        yaml_config = self.load_strategy_yaml(strategy_dir)
        if yaml_config:
            logger.info(
                "using_yaml_code_capture",
                reason="strategy.yaml found (explicit configuration)",
            )
            captured_files = self._capture_from_yaml(yaml_config, strategy_dir, dest_dir)
            # Create detection result for YAML case
            yaml_detection = EntryPointDetectionResult(
                detected_file=entry_point,
                detection_method="yaml_override",
                confidence=1.0,
                execution_context="yaml",
                warnings=[],
                fallback_used=False,
            )
            return (captured_files, yaml_detection)

        # Rule 2: No YAML → use entry point detection (NEW DEFAULT BEHAVIOR)
        logger.info(
            "using_entry_point_detection",
            reason="no strategy.yaml found, using entry point detection for storage optimization",
        )

        # Detect entry point using inspect.stack()
        detection_result = self.detect_entry_point()

        # Log warnings from detection
        for warning in detection_result.warnings:
            logger.warning("entry_point_detection_warning", message=warning)

        # If detection succeeded, capture only the detected file
        if detection_result.detected_file:
            logger.info(
                "entry_point_capture_mode",
                file=str(detection_result.detected_file),
                method=detection_result.detection_method,
                confidence=detection_result.confidence,
            )

            # Copy only the entry point file
            captured_files = self.copy_strategy_files(
                [detection_result.detected_file], dest_dir, project_root
            )
            return (captured_files, detection_result)

        # Rule 3: Detection failed → skip code capture gracefully
        logger.warning(
            "code_capture_skipped",
            reason=f"Entry point detection failed ({detection_result.detection_method})",
            context=detection_result.execution_context,
            message="Code capture will be skipped. Use strategy.yaml for explicit file list.",
        )
        return ([], detection_result)

    def find_project_root(self, entry_point: Path) -> Path:
        """Find project root by looking for markers.

        Looks for (in order of preference):
        1. .git directory
        2. pyproject.toml
        3. setup.py
        4. Fallback to parent directory of entry point

        Args:
            entry_point: Path to strategy file

        Returns:
            Path to project root

        Example:
            >>> capture = StrategyCodeCapture()
            >>> root = capture.find_project_root(Path("strategies/my_strategy.py"))
            >>> print(root.name)
            'my_project'
        """
        current = entry_point.resolve().parent

        while current != current.parent:  # Stop at filesystem root
            if (current / ".git").exists():
                return current
            if (current / "pyproject.toml").exists():
                return current
            if (current / "setup.py").exists():
                return current
            current = current.parent

        # Fallback: use entry point's parent directory
        return entry_point.resolve().parent
