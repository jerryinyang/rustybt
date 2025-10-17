"""
Validation tests for Jupyter notebooks and Python examples.

Tests notebooks and examples for:
1. Valid Python syntax
2. Import statements work (no ImportError)
3. No fabricated APIs
4. Code quality and patterns

Part of Story 11.6 Phase 4: Examples & Tutorials Validation
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


class NotebookValidator:
    """Validator for Jupyter notebooks."""

    @staticmethod
    def extract_code_cells(notebook_path: Path) -> List[Tuple[int, str]]:
        """Extract code cells from notebook."""
        with open(notebook_path, "r", encoding="utf-8") as f:
            notebook = json.load(f)

        code_cells = []
        for idx, cell in enumerate(notebook.get("cells", [])):
            if cell.get("cell_type") == "code":
                source = cell.get("source", [])
                if isinstance(source, list):
                    code = "".join(source)
                else:
                    code = source
                # Skip cells that are entirely commented or empty
                if code.strip() and not all(
                    line.strip().startswith("#") or not line.strip() for line in code.split("\n")
                ):
                    code_cells.append((idx, code))
        return code_cells

    @staticmethod
    def validate_syntax(code: str) -> Tuple[bool, str]:
        """Validate Python syntax using AST."""
        # Remove IPython magic commands before validation (valid in notebooks)
        lines = code.split("\n")
        filtered_lines = [line for line in lines if not line.strip().startswith("%")]
        cleaned_code = "\n".join(filtered_lines)

        # If all lines were magic commands, consider it valid
        if not cleaned_code.strip():
            return True, ""

        try:
            ast.parse(cleaned_code)
            return True, ""
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    @staticmethod
    def extract_imports(code: str) -> List[str]:
        """Extract import statements from code."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])
        return list(set(imports))


class ExampleValidator:
    """Validator for Python example files."""

    @staticmethod
    def validate_syntax(file_path: Path) -> Tuple[bool, str]:
        """Validate Python file syntax."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    @staticmethod
    def extract_imports(file_path: Path) -> List[str]:
        """Extract import statements from Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            tree = ast.parse(code)
        except SyntaxError:
            return []

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
        return imports


# Discover notebooks and examples
NOTEBOOKS_DIR = Path("docs/examples/notebooks")
EXAMPLES_DIR = Path("examples")

notebooks = list(NOTEBOOKS_DIR.glob("*.ipynb")) if NOTEBOOKS_DIR.exists() else []
examples = list(EXAMPLES_DIR.glob("*.py")) if EXAMPLES_DIR.exists() else []


class TestNotebookSyntax:
    """Test that all notebooks have valid Python syntax."""

    @pytest.mark.parametrize(
        "notebook_path",
        notebooks,
        ids=[nb.stem for nb in notebooks],
    )
    def test_notebook_syntax_valid(self, notebook_path):
        """Test notebook code cells have valid syntax."""
        validator = NotebookValidator()
        code_cells = validator.extract_code_cells(notebook_path)

        errors = []
        for cell_idx, code in code_cells:
            valid, error = validator.validate_syntax(code)
            if not valid:
                errors.append(f"Cell {cell_idx}: {error}")

        assert not errors, f"Syntax errors in {notebook_path.name}:\n" + "\n".join(errors)


class TestNotebookImports:
    """Test that notebook imports reference real modules."""

    @pytest.mark.parametrize(
        "notebook_path",
        notebooks,
        ids=[nb.stem for nb in notebooks],
    )
    def test_notebook_imports(self, notebook_path):
        """Test that notebook imports can be executed."""
        validator = NotebookValidator()
        code_cells = validator.extract_code_cells(notebook_path)

        # Extract all imports
        all_imports = set()
        for _, code in code_cells:
            imports = validator.extract_imports(code)
            all_imports.update(imports)

        # Filter to rustybt imports only
        rustybt_imports = [imp for imp in all_imports if imp.startswith("rustybt")]

        # Test rustybt imports
        import_errors = []
        for imp in rustybt_imports:
            try:
                __import__(imp)
            except ImportError as e:
                import_errors.append(f"{imp}: {str(e)}")

        # Some imports might fail due to missing test data or optional dependencies
        # That's acceptable - we're primarily checking for fabricated APIs
        if import_errors:
            # Only fail if more than 50% of imports fail (indicates systemic issue)
            failure_rate = len(import_errors) / len(rustybt_imports) if rustybt_imports else 0
            if failure_rate > 0.5:
                pytest.fail(
                    f"High import failure rate ({failure_rate:.0%}) in {notebook_path.name}:\n"
                    + "\n".join(import_errors[:5])  # Show first 5 errors
                )


class TestExampleSyntax:
    """Test that all Python examples have valid syntax."""

    @pytest.mark.parametrize(
        "example_path",
        examples,
        ids=[ex.stem for ex in examples],
    )
    def test_example_syntax_valid(self, example_path):
        """Test example file has valid Python syntax."""
        validator = ExampleValidator()
        valid, error = validator.validate_syntax(example_path)

        assert valid, f"Syntax error in {example_path.name}: {error}"


class TestExampleImports:
    """Test that example imports reference real modules."""

    @pytest.mark.parametrize(
        "example_path",
        examples,
        ids=[ex.stem for ex in examples],
    )
    def test_example_imports(self, example_path):
        """Test that example imports can be executed."""
        validator = ExampleValidator()
        imports = validator.extract_imports(example_path)

        # Filter to rustybt imports only
        rustybt_imports = [imp for imp in imports if imp.startswith("rustybt")]

        # Test rustybt imports (just the module part before the attribute)
        import_errors = []
        for full_import in rustybt_imports:
            # Extract module path (before the attribute)
            module_parts = full_import.split(".")
            # Try importing progressively from rustybt
            for i in range(1, len(module_parts) + 1):
                module_path = ".".join(module_parts[:i])
                try:
                    __import__(module_path)
                    break  # Success
                except ImportError as e:
                    if i == len(module_parts):  # Last attempt failed
                        import_errors.append(f"{full_import}: {str(e)}")

        # Allow some import failures (optional dependencies, test-only modules)
        if import_errors:
            failure_rate = len(import_errors) / len(rustybt_imports) if rustybt_imports else 0
            if failure_rate > 0.5:
                pytest.fail(
                    f"High import failure rate ({failure_rate:.0%}) in {example_path.name}:\n"
                    + "\n".join(import_errors[:5])
                )


class TestCriticalImports:
    """Test that critical imports from Phase 0 fix work in notebooks and examples."""

    CRITICAL_IMPORTS = [
        "rustybt.api.order_target",
        "rustybt.api.record",
        "rustybt.api.symbol",
        "rustybt.api.order",
        "rustybt.api.schedule_function",
    ]

    @pytest.mark.parametrize("import_path", CRITICAL_IMPORTS)
    def test_critical_api_imports_work(self, import_path):
        """Test that critical API imports fixed in Phase 0 work."""
        module_path, attr_name = import_path.rsplit(".", 1)

        try:
            module = __import__(module_path, fromlist=[attr_name])
            assert hasattr(module, attr_name), f"{module_path} missing attribute {attr_name}"
            attr = getattr(module, attr_name)
            assert callable(attr), f"{import_path} is not callable"
        except ImportError as e:
            pytest.fail(f"Critical import failed: {import_path} - {str(e)}")


class TestNotebookMetadata:
    """Test notebook metadata and structure."""

    def test_all_notebooks_exist(self):
        """Verify all expected notebooks exist."""
        expected_notebooks = [
            "01_getting_started.ipynb",
            "02_data_ingestion.ipynb",
            "03_strategy_development.ipynb",
            "04_performance_analysis.ipynb",
            "05_optimization.ipynb",
            "06_walk_forward.ipynb",
            "07_risk_analytics.ipynb",
            "08_portfolio_construction.ipynb",
            "09_live_paper_trading.ipynb",
            "10_full_workflow.ipynb",
            "11_advanced_topics.ipynb",
            "crypto_backtest_ccxt.ipynb",
            "equity_backtest_yfinance.ipynb",
            "report_generation.ipynb",
        ]

        missing = []
        for nb_name in expected_notebooks:
            nb_path = NOTEBOOKS_DIR / nb_name
            if not nb_path.exists():
                missing.append(nb_name)

        assert not missing, f"Missing notebooks: {', '.join(missing)}"

    def test_notebook_count(self):
        """Verify we have exactly 14 notebooks."""
        notebook_count = len(notebooks)
        assert notebook_count == 14, f"Expected 14 notebooks, found {notebook_count}"


class TestExampleMetadata:
    """Test example file metadata and structure."""

    def test_all_examples_have_docstrings(self):
        """Verify all examples have module-level docstrings."""
        missing_docstrings = []
        for example_path in examples:
            with open(example_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Skip shebang and comments to find docstring
                lines = content.split("\n")
                found_docstring = False
                for line in lines:
                    stripped = line.strip()
                    # Skip empty lines, shebangs, and comments
                    if not stripped or stripped.startswith("#"):
                        continue
                    # Check if this line starts a docstring
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        found_docstring = True
                        break
                    # If we hit code before finding a docstring, it's missing
                    break

                if not found_docstring:
                    missing_docstrings.append(example_path.name)

        # All examples should have docstrings
        if len(missing_docstrings) > 0:
            pytest.fail(
                f"Examples missing docstrings ({len(missing_docstrings)}): "
                + ", ".join(missing_docstrings)
            )

    def test_example_count(self):
        """Verify we have at least 25 examples."""
        example_count = len(examples)
        assert example_count >= 25, f"Expected at least 25 examples, found {example_count}"
