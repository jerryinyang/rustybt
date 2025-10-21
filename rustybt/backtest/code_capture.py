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
from typing import Any

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
            - 'inspect': Runtime introspection via inspect.stack()
            - 'ast_analysis': Static AST analysis
            - 'yaml_override': User explicitly specified via strategy.yaml
            - 'fallback': Fallback method used due to primary detection failure
            - 'failed': No detection method succeeded
        confidence: Confidence level in detection accuracy (0.0-1.0)
            - 1.0: Certain (inspect, yaml_override)
            - 0.8: High confidence (ast_analysis)
            - 0.5-0.7: Medium confidence (fallback methods)
            - 0.0: Failed detection
        fallback_used: Whether fallback strategy was used due to primary detection failure
        warnings: Warning messages generated during detection (empty if no issues)
        execution_context: Detected execution environment
            - 'file': Standard Python file execution
            - 'notebook': Jupyter notebook
            - 'interactive': Interactive Python session (REPL, ipython)
            - 'frozen': Frozen application (PyInstaller, cx_Freeze)
            - 'unknown': Could not determine context
    """

    detected_file: Path | None
    detection_method: str  # inspect | ast_analysis | yaml_override | fallback | failed
    confidence: float  # 0.0-1.0
    fallback_used: bool = False
    warnings: list[str] = field(default_factory=list)
    execution_context: str = "unknown"  # file | notebook | interactive | frozen | unknown


@dataclass
class CodeCaptureConfiguration:
    """Configuration for code capture mechanism.

    Attributes:
        mode: Code capture mode determining which files to store
            - 'entry_point': Store only the entry point file (new default)
            - 'yaml': Store files specified in strategy.yaml
            - 'disabled': Skip code capture
        entry_point_path: Absolute path to detected entry point file
            (required if mode='entry_point')
        yaml_path: Absolute path to strategy.yaml configuration
            (required if mode='yaml')
        additional_files: Additional files specified in YAML config (relative paths)
        enabled: Whether code capture is enabled for this backtest
            Automatically false for live trading mode
    """

    mode: str  # entry_point | yaml | disabled
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
        self,
        entry_point: Path | None = None,
        dest_dir: Path | None = None,
        project_root: Path | None = None,
        use_entry_point_detection: bool = True,
    ) -> tuple[list[Path], EntryPointDetectionResult | None]:
        """Capture strategy code with automatic entry point detection or YAML config.

        Precedence (Constitutional Requirement - CR-003: 100% backward compatibility):
        1. YAML file exists → Use YAML (explicit always wins)
        2. Entry point detection enabled → Detect and capture entry point only (NEW default)
        3. Fallback → Import analysis (old behavior)

        Args:
            entry_point: Path to strategy entry point file (optional if using detection)
            dest_dir: Destination directory (backtests/{id}/code/) - required
            project_root: Project root directory (auto-detected if None)
            use_entry_point_detection: Enable automatic entry point detection (default: True)

        Returns:
            Tuple of (captured file paths, detection result)
            - captured files: List of destination paths
            - detection result: EntryPointDetectionResult if detection was attempted, None otherwise

        Example:
            >>> capture = StrategyCodeCapture()
            >>> # New behavior: automatic detection
            >>> files, result = capture.capture_strategy_code(
            ...     dest_dir=Path("backtests/20251018_143527_123/code")
            ... )
            >>> print(f"Captured {len(files)} files via {result.detection_method}")
            >>>
            >>> # Old behavior: explicit entry point
            >>> files, _ = capture.capture_strategy_code(
            ...     entry_point=Path("strategies/my_strategy.py"),
            ...     dest_dir=Path("backtests/20251018_143527_123/code"),
            ...     use_entry_point_detection=False
            ... )
        """
        if dest_dir is None:
            raise CodeCaptureError("dest_dir is required for code capture")

        dest_dir.mkdir(parents=True, exist_ok=True)

        detection_result: EntryPointDetectionResult | None = None

        # Determine entry point (if not provided)
        if entry_point is None and use_entry_point_detection:
            # NEW: Automatic entry point detection
            detection_result = self.detect_entry_point()
            if detection_result.detected_file:
                entry_point = detection_result.detected_file
                logger.info(
                    "using_detected_entry_point",
                    file=str(entry_point),
                    method=detection_result.detection_method,
                    confidence=detection_result.confidence,
                )
            else:
                # Detection failed - check for YAML as fallback
                logger.warning(
                    "entry_point_detection_failed_checking_yaml",
                    warnings=detection_result.warnings,
                )
                # Will try YAML below, or skip code capture

        # If entry_point is still None, we cannot proceed
        if entry_point is None:
            logger.warning(
                "code_capture_skipped",
                reason="No entry point provided and detection failed",
            )
            return ([], detection_result)

        if project_root is None:
            project_root = self.find_project_root(entry_point)

        strategy_dir = entry_point.parent

        # Rule 1: YAML file exists → use it (Constitutional Requirement CR-003)
        yaml_config = self.load_strategy_yaml(strategy_dir)
        if yaml_config:
            logger.info(
                "using_yaml_code_capture",
                reason="strategy.yaml found (explicit override)",
            )
            captured_files = self._capture_from_yaml(yaml_config, strategy_dir, dest_dir)

            # Update detection result to indicate YAML override
            if detection_result:
                detection_result = EntryPointDetectionResult(
                    detected_file=entry_point,
                    detection_method="yaml_override",
                    confidence=1.0,
                    fallback_used=False,
                    warnings=detection_result.warnings,
                    execution_context=detection_result.execution_context,
                )
            else:
                detection_result = EntryPointDetectionResult(
                    detected_file=entry_point,
                    detection_method="yaml_override",
                    confidence=1.0,
                    fallback_used=False,
                    warnings=[],
                    execution_context="file",
                )

            return (captured_files, detection_result)

        # Rule 2: Entry point detection succeeded → capture entry point only (NEW default)
        if use_entry_point_detection and detection_result and detection_result.detected_file:
            logger.info(
                "using_entry_point_mode",
                file=str(entry_point),
                reason="Entry point detected (new default - 90%+ storage savings)",
            )

            # Copy only the entry point file
            captured_files = self.copy_strategy_files([entry_point], dest_dir, project_root)

            return (captured_files, detection_result)

        # Rule 3: Fallback → import analysis (old behavior for backward compatibility)
        logger.info(
            "using_import_analysis_fallback",
            reason="Entry point detection disabled or entry point provided explicitly",
        )
        imports = self.analyze_imports(entry_point, project_root)
        captured_files = self.copy_strategy_files(imports, dest_dir, project_root)

        return (captured_files, detection_result)

    def detect_entry_point(self) -> EntryPointDetectionResult:
        """Detect the file containing run_algorithm() call using runtime introspection.

        Uses inspect.stack() to walk up the call stack and identify the file that
        invoked run_algorithm(). This method is called during TradingAlgorithm
        initialization when code capture is enabled.

        Algorithm:
            1. Walk up call stack using inspect.stack()
            2. Filter out framework files (rustybt/*)
            3. Filter out standard library and site-packages
            4. Find first non-framework file mentioning 'run_algorithm'
            5. Handle edge cases (Jupyter, interactive sessions, frozen apps)
            6. Return detection result with confidence level

        Returns:
            EntryPointDetectionResult with detected file path, method used,
            confidence level, warnings, and execution context

        Example:
            >>> capture = StrategyCodeCapture()
            >>> result = capture.detect_entry_point()
            >>> if result.detected_file:
            ...     print(f"Entry point: {result.detected_file}")
            ... else:
            ...     print(f"Detection failed: {result.warnings}")
        """
        warnings: list[str] = []
        execution_context = "unknown"

        try:
            # Walk up the call stack
            stack = inspect.stack()

            for frame_info in stack:
                filename = frame_info.filename

                # Detect execution context
                if "<ipython-input" in filename or "<ipython console>" in filename:
                    execution_context = "notebook"
                elif filename in ("<stdin>", "<console>", "<string>"):
                    execution_context = "interactive"
                elif getattr(sys, "frozen", False):
                    execution_context = "frozen"
                elif filename.endswith(".py"):
                    execution_context = "file"

                # Skip framework files (rustybt/*)
                if "rustybt" in filename:
                    continue

                # Skip standard library and site-packages
                if "site-packages" in filename or "lib/python" in filename:
                    continue

                # Skip special Python runtime files
                if filename in ("<stdin>", "<console>", "<string>"):
                    continue

                # Skip IPython/Jupyter internals
                if "<ipython" in filename.lower():
                    continue

                # Check if this frame contains run_algorithm() call
                code_context = frame_info.code_context
                if code_context and any("run_algorithm" in line for line in code_context):
                    # Found the entry point!
                    detected_path = Path(filename).resolve()

                    # Verify file exists
                    if not detected_path.exists():
                        warnings.append(f"Detected entry point does not exist: {detected_path}")
                        continue

                    logger.info(
                        "entry_point_detected",
                        file=str(detected_path),
                        method="inspect",
                        confidence=1.0,
                        context=execution_context,
                    )

                    return EntryPointDetectionResult(
                        detected_file=detected_path,
                        detection_method="inspect",
                        confidence=1.0,
                        fallback_used=False,
                        warnings=warnings,
                        execution_context=execution_context,
                    )

            # No entry point found in stack - try fallback strategies

            # Fallback 1: Jupyter notebook detection
            if execution_context == "notebook":
                result = self._detect_jupyter_notebook()
                if result:
                    return result

            # Fallback 2: Check current working directory for .py files
            cwd_files = list(Path.cwd().glob("*.py"))
            if len(cwd_files) == 1:
                warnings.append(
                    "Entry point detection from stack failed, "
                    f"using single .py file in current directory: {cwd_files[0].name}"
                )
                logger.warning(
                    "entry_point_fallback_single_file",
                    file=str(cwd_files[0]),
                    confidence=0.7,
                )
                return EntryPointDetectionResult(
                    detected_file=cwd_files[0].resolve(),
                    detection_method="fallback",
                    confidence=0.7,
                    fallback_used=True,
                    warnings=warnings,
                    execution_context=execution_context,
                )

            # All detection methods failed
            if execution_context == "interactive":
                warnings.append("Interactive session detected - cannot determine source file")
                warnings.append("Code capture will be skipped unless strategy.yaml is provided")
            elif execution_context == "frozen":
                warnings.append("Frozen application detected - code capture not supported")
                warnings.append("Use strategy.yaml for explicit file list if needed")
            else:
                warnings.append(
                    "Entry point detection failed - could not find run_algorithm() call in stack"
                )
                warnings.append("Create strategy.yaml to specify files for code capture")

            logger.warning(
                "entry_point_detection_failed",
                context=execution_context,
                warnings=warnings,
            )

            return EntryPointDetectionResult(
                detected_file=None,
                detection_method="failed",
                confidence=0.0,
                fallback_used=True,
                warnings=warnings,
                execution_context=execution_context,
            )

        except Exception as e:  # noqa: BLE001
            # Catch-all for any unexpected errors during detection
            error_msg = f"Unexpected error during entry point detection: {e}"
            warnings.append(error_msg)
            logger.error(
                "entry_point_detection_error",
                error=str(e),
                error_type=type(e).__name__,
            )

            return EntryPointDetectionResult(
                detected_file=None,
                detection_method="failed",
                confidence=0.0,
                fallback_used=True,
                warnings=warnings,
                execution_context=execution_context,
            )

    def _detect_jupyter_notebook(self) -> EntryPointDetectionResult | None:
        """Attempt to detect Jupyter notebook filename.

        Returns:
            EntryPointDetectionResult if notebook detected, None otherwise
        """
        warnings: list[str] = []

        try:
            # Try to get notebook name from IPython
            from IPython import get_ipython  # type: ignore[attr-defined]

            ipython = get_ipython()  # type: ignore[no-untyped-call]
            if ipython is None:
                return None

            # Attempt to get notebook metadata (may not always be available)
            parent = getattr(ipython, "parent", None)
            if parent:
                metadata = getattr(parent, "metadata", {})
                notebook_path = metadata.get("path")
                if notebook_path:
                    detected_path = Path(notebook_path).resolve()
                    warnings.append(
                        "Jupyter notebook detected - using notebook path from IPython metadata"
                    )
                    logger.info(
                        "jupyter_notebook_detected_from_metadata",
                        path=str(detected_path),
                    )
                    return EntryPointDetectionResult(
                        detected_file=detected_path,
                        detection_method="fallback",
                        confidence=0.8,
                        fallback_used=True,
                        warnings=warnings,
                        execution_context="notebook",
                    )

            # Fallback: Look for .ipynb files in current directory
            ipynb_files = list(Path.cwd().glob("*.ipynb"))
            if len(ipynb_files) == 1:
                warnings.append(
                    "Jupyter notebook detected - used .ipynb filename from current directory"
                )
                logger.info(
                    "jupyter_notebook_detected_from_cwd",
                    path=str(ipynb_files[0]),
                )
                return EntryPointDetectionResult(
                    detected_file=ipynb_files[0].resolve(),
                    detection_method="fallback",
                    confidence=0.7,
                    fallback_used=True,
                    warnings=warnings,
                    execution_context="notebook",
                )

        except ImportError:
            # IPython not available
            pass
        except Exception as e:  # noqa: BLE001
            logger.debug(
                "jupyter_detection_failed",
                error=str(e),
            )

        return None

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
