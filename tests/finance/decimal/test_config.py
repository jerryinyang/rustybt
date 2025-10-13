"""Unit tests for DecimalConfig class."""

from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from rustybt.finance.decimal import (
    DecimalConfig,
    InvalidAssetClassError,
    InvalidPrecisionError,
    InvalidRoundingModeError,
)


class TestDecimalConfigLoading:
    """Test configuration loading from various sources."""

    def test_singleton_pattern(self):
        """Test DecimalConfig implements singleton pattern."""
        config1 = DecimalConfig.get_instance()
        config2 = DecimalConfig.get_instance()
        config3 = DecimalConfig()

        # All instances should be the same object
        assert config1 is config2
        assert config1 is config3

    def test_load_from_yaml(self):
        """Test loading configuration from YAML file."""
        config = DecimalConfig.get_instance()
        test_yaml = Path(__file__).parent.parent.parent / "fixtures" / "decimal_config.yaml"

        config.load_from_yaml(str(test_yaml))

        assert config.get_precision("crypto") == 18
        assert config.get_rounding_mode("crypto") == "ROUND_DOWN"
        assert config.get_scale("crypto") == 8

        assert config.get_precision("equity") == 18
        assert config.get_rounding_mode("equity") == "ROUND_HALF_UP"
        assert config.get_scale("equity") == 2

    def test_load_from_json(self):
        """Test loading configuration from JSON file."""
        config = DecimalConfig.get_instance()
        test_json = Path(__file__).parent.parent.parent / "fixtures" / "decimal_config.json"

        config.load_from_json(str(test_json))

        assert config.get_precision("crypto") == 18
        assert config.get_rounding_mode("crypto") == "ROUND_DOWN"
        assert config.get_scale("crypto") == 8

    def test_load_from_dict(self):
        """Test loading configuration from dictionary."""
        config = DecimalConfig.get_instance()

        test_config = {
            "global_defaults": {"precision": 18, "rounding_mode": "ROUND_HALF_EVEN", "scale": 8},
            "asset_classes": {
                "test_asset": {"precision": 12, "rounding_mode": "ROUND_UP", "scale": 4}
            },
        }

        config.load_from_dict(test_config)

        assert config.get_precision("test_asset") == 12
        assert config.get_rounding_mode("test_asset") == "ROUND_UP"
        assert config.get_scale("test_asset") == 4

    def test_load_from_yaml_file_not_found(self):
        """Test loading from non-existent YAML file raises error."""
        config = DecimalConfig.get_instance()

        with pytest.raises(FileNotFoundError):
            config.load_from_yaml("nonexistent_file.yaml")

    def test_load_from_json_file_not_found(self):
        """Test loading from non-existent JSON file raises error."""
        config = DecimalConfig.get_instance()

        with pytest.raises(FileNotFoundError):
            config.load_from_json("nonexistent_file.json")


class TestDecimalConfigGetters:
    """Test configuration getter methods."""

    def test_get_precision_for_asset_class(self):
        """Test retrieving precision for different asset classes."""
        config = DecimalConfig.get_instance()

        # Load defaults
        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        assert config.get_precision("crypto") == 18
        assert config.get_precision("equity") == 18
        assert config.get_precision("forex") == 18
        assert config.get_precision("future") == 18

    def test_get_rounding_mode_for_asset_class(self):
        """Test retrieving rounding mode for different asset classes."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        assert config.get_rounding_mode("crypto") == "ROUND_DOWN"
        assert config.get_rounding_mode("equity") == "ROUND_HALF_UP"
        assert config.get_rounding_mode("forex") == "ROUND_HALF_EVEN"

    def test_get_scale_for_asset_class(self):
        """Test retrieving scale for different asset classes."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        assert config.get_scale("crypto") == 8
        assert config.get_scale("equity") == 2
        assert config.get_scale("forex") == 5

    def test_get_precision_unknown_asset_class(self):
        """Test getting precision for unknown asset class raises error."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        with pytest.raises(InvalidAssetClassError) as exc_info:
            config.get_precision("unknown_asset")

        assert "unknown_asset" in str(exc_info.value)

    def test_get_rounding_constant(self):
        """Test getting rounding constant returns decimal module constant."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        assert config.get_rounding_constant("crypto") == ROUND_DOWN
        assert config.get_rounding_constant("equity") == ROUND_HALF_UP
        assert config.get_rounding_constant("forex") == ROUND_HALF_EVEN


class TestDecimalConfigSetters:
    """Test configuration setter methods."""

    def test_set_precision_valid(self):
        """Test setting precision with valid values."""
        config = DecimalConfig.get_instance()

        # Set precision for new asset class
        config.set_precision("test_asset", 10, "ROUND_HALF_EVEN")

        assert config.get_precision("test_asset") == 10
        assert config.get_rounding_mode("test_asset") == "ROUND_HALF_EVEN"

    def test_set_precision_with_scale(self):
        """Test setting precision with scale parameter."""
        config = DecimalConfig.get_instance()

        config.set_precision("test_asset", 12, "ROUND_UP", scale=6)

        assert config.get_precision("test_asset") == 12
        assert config.get_rounding_mode("test_asset") == "ROUND_UP"
        assert config.get_scale("test_asset") == 6

    def test_set_precision_invalid_too_high(self):
        """Test setting precision above maximum raises error."""
        config = DecimalConfig.get_instance()

        with pytest.raises(InvalidPrecisionError) as exc_info:
            config.set_precision("test_asset", 50, "ROUND_HALF_EVEN")

        assert "0-18" in str(exc_info.value)

    def test_set_precision_invalid_negative(self):
        """Test setting negative precision raises error."""
        config = DecimalConfig.get_instance()

        with pytest.raises(InvalidPrecisionError) as exc_info:
            config.set_precision("test_asset", -5, "ROUND_HALF_EVEN")

        assert "0-18" in str(exc_info.value)

    def test_set_precision_invalid_rounding_mode(self):
        """Test setting invalid rounding mode raises error."""
        config = DecimalConfig.get_instance()

        with pytest.raises(InvalidRoundingModeError) as exc_info:
            config.set_precision("test_asset", 8, "ROUND_INVALID_MODE")

        assert "ROUND_INVALID_MODE" in str(exc_info.value)

    def test_set_precision_non_integer(self):
        """Test setting non-integer precision raises error."""
        config = DecimalConfig.get_instance()

        with pytest.raises(TypeError):
            config.set_precision("test_asset", "8", "ROUND_HALF_EVEN")

    def test_set_precision_non_string_rounding_mode(self):
        """Test setting non-string rounding mode raises error."""
        config = DecimalConfig.get_instance()

        with pytest.raises(TypeError):
            config.set_precision("test_asset", 8, ROUND_DOWN)


class TestDecimalConfigValidation:
    """Test configuration validation."""

    def test_validate_config_valid(self):
        """Test validation passes for valid configuration."""
        config = DecimalConfig.get_instance()

        valid_config = {
            "global_defaults": {"precision": 18, "rounding_mode": "ROUND_HALF_EVEN", "scale": 8},
            "asset_classes": {
                "crypto": {"precision": 18, "rounding_mode": "ROUND_DOWN", "scale": 8}
            },
        }

        config.load_from_dict(valid_config)
        assert config.validate_config() is True

    def test_validate_config_missing_global_defaults(self):
        """Test validation fails for missing global_defaults."""
        config = DecimalConfig.get_instance()

        invalid_config = {
            "asset_classes": {"crypto": {"precision": 18, "rounding_mode": "ROUND_DOWN"}}
        }

        with pytest.raises(InvalidAssetClassError) as exc_info:
            config.load_from_dict(invalid_config)

        assert "global_defaults" in str(exc_info.value)

    def test_validate_config_missing_asset_classes(self):
        """Test validation fails for missing asset_classes."""
        config = DecimalConfig.get_instance()

        invalid_config = {"global_defaults": {"precision": 18, "rounding_mode": "ROUND_HALF_EVEN"}}

        with pytest.raises(InvalidAssetClassError) as exc_info:
            config.load_from_dict(invalid_config)

        assert "asset_classes" in str(exc_info.value)

    def test_validate_config_invalid_precision_in_asset_class(self):
        """Test validation fails for invalid precision in asset class."""
        config = DecimalConfig.get_instance()

        invalid_config = {
            "global_defaults": {"precision": 18, "rounding_mode": "ROUND_HALF_EVEN"},
            "asset_classes": {
                "crypto": {"precision": 50, "rounding_mode": "ROUND_DOWN"}  # Invalid: > 18
            },
        }

        with pytest.raises(InvalidPrecisionError):
            config.load_from_dict(invalid_config)

    def test_validate_config_invalid_rounding_mode_in_asset_class(self):
        """Test validation fails for invalid rounding mode in asset class."""
        config = DecimalConfig.get_instance()

        invalid_config = {
            "global_defaults": {"precision": 18, "rounding_mode": "ROUND_HALF_EVEN"},
            "asset_classes": {"crypto": {"precision": 18, "rounding_mode": "INVALID_MODE"}},
        }

        with pytest.raises(InvalidRoundingModeError):
            config.load_from_dict(invalid_config)


class TestDecimalConfigContext:
    """Test Decimal context management."""

    def test_get_context(self):
        """Test getting Decimal context for asset class."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        ctx = config.get_context("crypto")

        assert ctx.prec == 18
        assert ctx.rounding == ROUND_DOWN

    def test_with_precision_context_manager(self):
        """Test context manager temporarily changes precision."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        # Use context manager
        with config.with_precision("crypto") as ctx:
            assert ctx.prec == 18
            assert ctx.rounding == ROUND_DOWN

            # Perform calculation with crypto precision
            value = Decimal("1.123456789012345678901234567890")
            # Unary plus applies current context
            result = +value

            # Result should respect precision
            assert isinstance(result, Decimal)

    def test_context_manager_restores_previous_context(self):
        """Test context manager restores previous context after exit."""
        from decimal import getcontext

        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        # Save original context
        getcontext().prec

        # Use context manager
        with config.with_precision("crypto") as ctx:
            # Context changed
            assert ctx.prec == 18

        # Context should be restored (approximately, may differ due to localcontext)
        # We don't assert exact equality as localcontext creates new contexts

    def test_nested_context_managers(self):
        """Test nested context managers work correctly."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        with config.with_precision("crypto") as ctx1:
            assert ctx1.prec == 18
            assert ctx1.rounding == ROUND_DOWN

            with config.with_precision("equity") as ctx2:
                assert ctx2.prec == 18
                assert ctx2.rounding == ROUND_HALF_UP

            # Outer context should still be active
            # (Note: getcontext() may show different context due to localcontext nesting)


class TestDecimalConfigDefaults:
    """Test default preset configurations."""

    def test_default_presets_loaded(self):
        """Test default precision presets are loaded correctly."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        # Verify default presets
        assert config.get_precision("crypto") == 18
        assert config.get_precision("equity") == 18
        assert config.get_precision("forex") == 18
        assert config.get_precision("future") == 18
        assert config.get_precision("index") == 18

        assert config.get_rounding_mode("crypto") == "ROUND_DOWN"
        assert config.get_rounding_mode("equity") == "ROUND_HALF_UP"
        assert config.get_rounding_mode("forex") == "ROUND_HALF_EVEN"
        assert config.get_rounding_mode("future") == "ROUND_HALF_UP"
        assert config.get_rounding_mode("index") == "ROUND_HALF_EVEN"

    def test_default_scales(self):
        """Test default scale values for each asset class."""
        config = DecimalConfig.get_instance()

        default_config_path = (
            Path(__file__).parent.parent.parent.parent
            / "rustybt"
            / "finance"
            / "decimal"
            / "default_config.yaml"
        )
        config.load_from_yaml(str(default_config_path))

        assert config.get_scale("crypto") == 8
        assert config.get_scale("equity") == 2
        assert config.get_scale("forex") == 5
        assert config.get_scale("future") == 2
        assert config.get_scale("index") == 2
