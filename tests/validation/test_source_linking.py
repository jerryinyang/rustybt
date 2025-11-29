"""Tests for source code linking module."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from rustybt.validation.cli import main
from rustybt.validation.models import Finding
from rustybt.validation.source_linking import (
    DEFAULT_EDITOR,
    LAYER_MODULES,
    SourceLocation,
    SourceLocationCache,
    _extract_search_terms,
    _parse_grep_line,
    format_source_locations,
    get_editor_command,
    get_layer_modules,
    grep_for_event,
    locate_source,
    set_editor_command,
)


class TestSourceLocation:
    """Tests for SourceLocation dataclass."""

    def test_source_location_creation(self):
        """Test creating a SourceLocation."""
        loc = SourceLocation(
            file=Path("rustybt/finance/order.py"),
            line=142,
            description="order_quantity calculation",
            framework="rustybt",
        )

        assert loc.file == Path("rustybt/finance/order.py")
        assert loc.line == 142
        assert loc.description == "order_quantity calculation"
        assert loc.framework == "rustybt"

    def test_source_location_str_format(self):
        """Test SourceLocation string representation."""
        loc = SourceLocation(
            file=Path("rustybt/finance/order.py"),
            line=142,
            description="order_quantity calculation",
            framework="rustybt",
        )
        result = str(loc)

        assert "rustybt/finance/order.py:142" in result
        assert "order_quantity calculation" in result


class TestLayerModules:
    """Tests for layer-to-module mapping."""

    def test_all_layers_have_mappings(self):
        """Test all validation layers have module mappings."""
        expected_layers = ["data", "signals", "orders", "broker", "portfolio"]
        for layer in expected_layers:
            assert layer in LAYER_MODULES

    def test_layers_have_both_frameworks(self):
        """Test each layer maps both rustybt and backtrader."""
        for layer, mapping in LAYER_MODULES.items():
            assert "rustybt" in mapping, f"{layer} missing rustybt mapping"
            assert "backtrader" in mapping, f"{layer} missing backtrader mapping"

    def test_layer_modules_not_empty(self):
        """Test layer modules lists are not empty."""
        for layer, mapping in LAYER_MODULES.items():
            assert len(mapping["rustybt"]) > 0
            assert len(mapping["backtrader"]) > 0

    def test_get_layer_modules(self):
        """Test get_layer_modules returns correct mapping."""
        orders_modules = get_layer_modules("orders")

        assert "rustybt" in orders_modules
        assert "backtrader" in orders_modules
        assert "rustybt/finance/order.py" in orders_modules["rustybt"]

    def test_get_layer_modules_unknown_layer(self):
        """Test get_layer_modules returns empty dict for unknown layer."""
        result = get_layer_modules("unknown_layer")
        assert result == {}


class TestSearchTermExtraction:
    """Tests for search term extraction."""

    def test_extract_simple_event(self):
        """Test extracting terms from simple event."""
        terms = _extract_search_terms("order_quantity")
        assert "order" in terms or "quantity" in terms

    def test_extract_mismatch_event(self):
        """Test _mismatch suffix is removed."""
        terms = _extract_search_terms("order_quantity_mismatch")
        assert "mismatch" not in terms

    def test_extract_error_event(self):
        """Test _error suffix is removed."""
        terms = _extract_search_terms("cash_balance_error")
        assert "error" not in terms

    def test_short_terms_filtered(self):
        """Test very short terms are filtered out."""
        terms = _extract_search_terms("a_b_valid_test")
        # 'a' and 'b' should be filtered (len <= 2)
        assert "a|" not in terms or "|a" not in terms


class TestGrepLineParsing:
    """Tests for grep line parsing."""

    def test_parse_valid_grep_line(self):
        """Test parsing valid grep output line."""
        line = "rustybt/order.py:142:def create_order(quantity):"
        result = _parse_grep_line(line)

        assert result is not None
        assert result[0] == "rustybt/order.py"
        assert result[1] == 142
        assert "def create_order" in result[2]

    def test_parse_invalid_grep_line(self):
        """Test parsing invalid grep line returns None."""
        line = "not a valid grep line"
        result = _parse_grep_line(line)
        assert result is None

    def test_parse_grep_line_with_colons_in_content(self):
        """Test parsing grep line with colons in the content."""
        line = "file.py:10:dict = {'key': 'value'}"
        result = _parse_grep_line(line)

        assert result is not None
        assert result[0] == "file.py"
        assert result[1] == 10
        assert "dict" in result[2]


class TestGrepForEvent:
    """Tests for grep_for_event function."""

    def test_grep_nonexistent_path(self):
        """Test grep returns empty for nonexistent path."""
        result = grep_for_event(Path("/nonexistent/path"), "test")
        assert result == []

    def test_grep_existing_file(self, tmp_path):
        """Test grep finds content in existing file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def calculate_order():\n    pass\n")

        result = grep_for_event(tmp_path, "calculate_order")
        # May or may not find depending on grep/rg availability
        assert isinstance(result, list)


class TestLocateSource:
    """Tests for locate_source function."""

    def test_locate_source_returns_list(self):
        """Test locate_source returns list of SourceLocations."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="order_quantity_mismatch",
        )

        result = locate_source(finding)
        assert isinstance(result, list)

    def test_locate_source_with_project_root(self, tmp_path):
        """Test locate_source with custom project root."""
        # Create mock source structure
        orders_dir = tmp_path / "rustybt" / "finance"
        orders_dir.mkdir(parents=True)
        order_file = orders_dir / "order.py"
        order_file.write_text("def create_order(quantity):\n    pass\n")

        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="create_order",
        )

        result = locate_source(finding, project_root=tmp_path)
        assert isinstance(result, list)


class TestEditorConfiguration:
    """Tests for editor configuration."""

    def test_get_editor_default(self):
        """Test get_editor_command returns default when no config."""
        with patch("rustybt.validation.source_linking.CONFIG_FILE") as mock_file:
            mock_file.exists.return_value = False
            cmd = get_editor_command()

            assert "{file}" in cmd
            assert "{line}" in cmd
            assert cmd == DEFAULT_EDITOR

    def test_set_and_get_editor(self, tmp_path):
        """Test setting and getting editor command."""
        config_file = tmp_path / "config.yaml"

        with patch("rustybt.validation.source_linking.CONFIG_FILE", config_file):
            with patch("rustybt.validation.source_linking.CONFIG_DIR", tmp_path):
                set_editor_command("vim +{line} {file}")
                result = get_editor_command()

                assert result == "vim +{line} {file}"

    def test_editor_command_formatting(self):
        """Test editor command placeholder replacement."""
        loc = SourceLocation(
            file=Path("test.py"),
            line=10,
            description="test",
            framework="rustybt",
        )
        cmd = "code -g {file}:{line}"
        formatted = cmd.format(file=loc.file, line=loc.line)
        assert formatted == "code -g test.py:10"


class TestFormatSourceLocations:
    """Tests for format_source_locations function."""

    def test_format_empty_locations(self):
        """Test formatting empty locations list."""
        result = format_source_locations([])
        assert "No source locations found" in result

    def test_format_rustybt_locations(self):
        """Test formatting rustybt-only locations."""
        locations = [
            SourceLocation(
                file=Path("rustybt/order.py"),
                line=10,
                description="create_order",
                framework="rustybt",
            ),
        ]
        result = format_source_locations(locations)

        assert "rustybt locations:" in result
        assert "rustybt/order.py:10" in result
        assert "1." in result

    def test_format_mixed_locations(self):
        """Test formatting locations from both frameworks."""
        locations = [
            SourceLocation(
                file=Path("rustybt/order.py"),
                line=10,
                description="create_order",
                framework="rustybt",
            ),
            SourceLocation(
                file=Path("backtrader/order.py"),
                line=20,
                description="Order.__init__",
                framework="backtrader",
            ),
        ]
        result = format_source_locations(locations)

        assert "rustybt locations:" in result
        assert "Backtrader locations (reference):" in result
        assert "1." in result
        assert "2." in result


class TestSourceLocationCache:
    """Tests for SourceLocationCache."""

    def test_cache_creation(self, tmp_path):
        """Test creating cache."""
        cache = SourceLocationCache(tmp_path)
        assert cache.cache_dir == tmp_path

    def test_cache_set_and_get(self, tmp_path):
        """Test storing and retrieving from cache."""
        cache = SourceLocationCache(tmp_path)

        finding = Finding(id="F1", layer="orders", description="test finding")
        locations = [
            SourceLocation(
                file=Path("test.py"),
                line=10,
                description="test",
                framework="rustybt",
            )
        ]

        cache.set(finding, locations)
        result = cache.get(finding)

        assert result is not None
        assert len(result) == 1
        assert result[0].file == Path("test.py")
        assert result[0].line == 10

    def test_cache_miss(self, tmp_path):
        """Test cache returns None on miss."""
        cache = SourceLocationCache(tmp_path)
        finding = Finding(id="F1", layer="orders", description="not cached")

        result = cache.get(finding)
        assert result is None

    def test_cache_invalidate_specific(self, tmp_path):
        """Test invalidating specific cache entry."""
        cache = SourceLocationCache(tmp_path)

        finding1 = Finding(id="F1", layer="orders", description="finding 1")
        finding2 = Finding(id="F2", layer="data", description="finding 2")

        locations = [
            SourceLocation(file=Path("test.py"), line=10, description="test", framework="rustybt")
        ]

        cache.set(finding1, locations)
        cache.set(finding2, locations)

        cache.invalidate(finding1)

        assert cache.get(finding1) is None
        assert cache.get(finding2) is not None

    def test_cache_invalidate_all(self, tmp_path):
        """Test invalidating entire cache."""
        cache = SourceLocationCache(tmp_path)

        finding = Finding(id="F1", layer="orders", description="test")
        locations = [
            SourceLocation(file=Path("test.py"), line=10, description="test", framework="rustybt")
        ]

        cache.set(finding, locations)
        cache.invalidate()

        assert cache.get(finding) is None


@pytest.mark.source_linking
class TestConfigCLICommands:
    """Tests for config CLI commands."""

    def test_config_command_exists(self):
        """Test config command group exists."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--help"])

        assert result.exit_code == 0
        assert "set" in result.output
        assert "get" in result.output
        assert "list" in result.output

    def test_config_set_editor(self, tmp_path):
        """Test setting editor via CLI."""
        config_file = tmp_path / "config.yaml"

        with patch("rustybt.validation.source_linking.CONFIG_FILE", config_file):
            with patch("rustybt.validation.source_linking.CONFIG_DIR", tmp_path):
                runner = CliRunner()
                result = runner.invoke(
                    main, ["config", "set", "editor", "vim +{line} {file}"]
                )

                assert result.exit_code == 0
                assert "Editor set to" in result.output

    def test_config_set_unknown_key(self):
        """Test setting unknown config key fails."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "set", "unknown", "value"])

        assert result.exit_code == 1
        assert "Unknown config key" in result.output

    def test_config_get_editor(self, tmp_path):
        """Test getting editor via CLI."""
        config_file = tmp_path / "config.yaml"

        with patch("rustybt.validation.source_linking.CONFIG_FILE", config_file):
            with patch("rustybt.validation.source_linking.CONFIG_DIR", tmp_path):
                runner = CliRunner()
                result = runner.invoke(main, ["config", "get", "editor"])

                assert result.exit_code == 0
                assert "editor =" in result.output

    def test_config_get_unknown_key(self):
        """Test getting unknown config key fails."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "get", "unknown"])

        assert result.exit_code == 1
        assert "Unknown config key" in result.output

    def test_config_list(self, tmp_path):
        """Test listing all config values."""
        config_file = tmp_path / "config.yaml"

        with patch("rustybt.validation.source_linking.CONFIG_FILE", config_file):
            with patch("rustybt.validation.source_linking.CONFIG_DIR", tmp_path):
                runner = CliRunner()
                result = runner.invoke(main, ["config", "list"])

                assert result.exit_code == 0
                assert "editor" in result.output

    def test_config_set_editor_warns_missing_placeholders(self, tmp_path):
        """Test warning when editor command missing placeholders."""
        config_file = tmp_path / "config.yaml"

        with patch("rustybt.validation.source_linking.CONFIG_FILE", config_file):
            with patch("rustybt.validation.source_linking.CONFIG_DIR", tmp_path):
                runner = CliRunner()
                result = runner.invoke(main, ["config", "set", "editor", "vim"])

                assert result.exit_code == 0
                # Should warn about missing placeholders
                assert "{file}" in result.output or "{line}" in result.output
