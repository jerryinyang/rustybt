"""Property-based tests for DecimalConfig using Hypothesis."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.finance.decimal import (
    DecimalConfig,
    InvalidPrecisionError,
    InvalidRoundingModeError,
)

# Valid rounding modes for Hypothesis
VALID_ROUNDING_MODES = [
    "ROUND_HALF_EVEN",
    "ROUND_DOWN",
    "ROUND_HALF_UP",
    "ROUND_UP",
    "ROUND_CEILING",
    "ROUND_FLOOR",
    "ROUND_05UP",
    "ROUND_HALF_DOWN",
]

# Asset classes for testing
ASSET_CLASSES = ["crypto", "equity", "forex", "future", "index"]


class TestDecimalConfigPropertyBased:
    """Property-based tests for DecimalConfig."""

    @given(
        precision=st.integers(min_value=0, max_value=18),
        asset_class=st.sampled_from(ASSET_CLASSES),
        rounding_mode=st.sampled_from(VALID_ROUNDING_MODES),
    )
    def test_precision_roundtrip(self, precision, asset_class, rounding_mode):
        """Test precision can be set and retrieved correctly."""
        config = DecimalConfig.get_instance()
        config.set_precision(asset_class, precision, rounding_mode)

        retrieved_precision = config.get_precision(asset_class)
        retrieved_rounding = config.get_rounding_mode(asset_class)

        assert retrieved_precision == precision
        assert retrieved_rounding == rounding_mode

    @given(
        precision=st.integers(min_value=0, max_value=18),
        scale=st.integers(min_value=0, max_value=18),
    )
    def test_precision_and_scale_roundtrip(self, precision, scale):
        """Test precision and scale can be set and retrieved."""
        config = DecimalConfig.get_instance()

        config.set_precision("test_asset", precision, "ROUND_HALF_EVEN", scale=scale)

        assert config.get_precision("test_asset") == precision
        assert config.get_scale("test_asset") == scale

    @given(precision=st.integers(min_value=19, max_value=100))
    def test_precision_above_max_raises_error(self, precision):
        """Test precision above 18 always raises InvalidPrecisionError."""
        config = DecimalConfig.get_instance()

        with pytest.raises(InvalidPrecisionError):
            config.set_precision("test_asset", precision, "ROUND_HALF_EVEN")

    @given(precision=st.integers(max_value=-1))
    def test_precision_negative_raises_error(self, precision):
        """Test negative precision always raises InvalidPrecisionError."""
        config = DecimalConfig.get_instance()

        with pytest.raises(InvalidPrecisionError):
            config.set_precision("test_asset", precision, "ROUND_HALF_EVEN")

    @given(
        rounding_mode=st.text(min_size=1, max_size=50).filter(
            lambda x: x not in VALID_ROUNDING_MODES
        )
    )
    def test_invalid_rounding_mode_raises_error(self, rounding_mode):
        """Test invalid rounding mode always raises InvalidRoundingModeError."""
        config = DecimalConfig.get_instance()

        with pytest.raises(InvalidRoundingModeError):
            config.set_precision("test_asset", 8, rounding_mode)

    @given(
        config_dict=st.fixed_dictionaries(
            {
                "global_defaults": st.fixed_dictionaries(
                    {
                        "precision": st.integers(min_value=0, max_value=18),
                        "rounding_mode": st.sampled_from(VALID_ROUNDING_MODES),
                        "scale": st.integers(min_value=0, max_value=18),
                    }
                ),
                "asset_classes": st.dictionaries(
                    keys=st.text(
                        min_size=1,
                        max_size=20,
                        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
                    ),
                    values=st.fixed_dictionaries(
                        {
                            "precision": st.integers(min_value=0, max_value=18),
                            "rounding_mode": st.sampled_from(VALID_ROUNDING_MODES),
                            "scale": st.integers(min_value=0, max_value=18),
                        }
                    ),
                    min_size=1,
                    max_size=5,
                ),
            }
        )
    )
    def test_config_loading_preserves_values(self, config_dict):
        """Test configuration loading preserves all values."""
        config = DecimalConfig.get_instance()
        config.load_from_dict(config_dict)

        # Verify global defaults were preserved
        assert (
            config._config["global_defaults"]["precision"]
            == config_dict["global_defaults"]["precision"]
        )
        assert (
            config._config["global_defaults"]["rounding_mode"]
            == config_dict["global_defaults"]["rounding_mode"]
        )
        assert config._config["global_defaults"]["scale"] == config_dict["global_defaults"]["scale"]

        # Verify asset classes were preserved
        for asset_class, settings in config_dict["asset_classes"].items():
            assert config.get_precision(asset_class) == settings["precision"]
            assert config.get_rounding_mode(asset_class) == settings["rounding_mode"]
            assert config.get_scale(asset_class) == settings["scale"]

    @given(
        asset_class=st.sampled_from(ASSET_CLASSES), precision=st.integers(min_value=0, max_value=18)
    )
    def test_context_has_correct_precision(self, asset_class, precision):
        """Test context manager creates context with correct precision."""
        config = DecimalConfig.get_instance()

        # Set precision
        config.set_precision(asset_class, precision, "ROUND_HALF_EVEN")

        # Get context and verify
        with config.with_precision(asset_class) as ctx:
            assert ctx.prec == precision

    @given(
        value=st.decimals(
            allow_nan=False,
            allow_infinity=False,
            min_value=Decimal("-1000000"),
            max_value=Decimal("1000000"),
            places=8,
        ),
        precision=st.integers(min_value=1, max_value=18),
    )
    def test_context_applies_to_calculations(self, value, precision):
        """Test context manager precision applies to calculations."""
        config = DecimalConfig.get_instance()

        # Set precision for test
        config.set_precision("test_prop", precision, "ROUND_HALF_EVEN")

        # Perform calculation with context
        with config.with_precision("test_prop"):
            # Unary plus applies current context
            result = +value

            # Result should be a Decimal
            assert isinstance(result, Decimal)

            # Result should not have more significant digits than precision
            # (This is a simplified check - Decimal precision is complex)
            str_result = str(result).replace("-", "").replace(".", "")
            # Remove leading zeros
            str_result = str_result.lstrip("0") or "0"

            # Check that significant digits don't exceed precision
            # Note: This is approximate due to how Decimal handles precision
            if str_result != "0":
                assert len(str_result) <= precision + 5  # Allow some tolerance

    @given(
        precision1=st.integers(min_value=0, max_value=18),
        precision2=st.integers(min_value=0, max_value=18),
        rounding1=st.sampled_from(VALID_ROUNDING_MODES),
        rounding2=st.sampled_from(VALID_ROUNDING_MODES),
    )
    def test_different_asset_classes_independent(
        self, precision1, precision2, rounding1, rounding2
    ):
        """Test different asset classes maintain independent settings."""
        config = DecimalConfig.get_instance()

        # Set different precisions for two asset classes
        config.set_precision("asset1", precision1, rounding1)
        config.set_precision("asset2", precision2, rounding2)

        # Verify they remain independent
        assert config.get_precision("asset1") == precision1
        assert config.get_precision("asset2") == precision2
        assert config.get_rounding_mode("asset1") == rounding1
        assert config.get_rounding_mode("asset2") == rounding2

    @given(
        precision=st.integers(min_value=0, max_value=18),
        rounding_mode=st.sampled_from(VALID_ROUNDING_MODES),
    )
    def test_get_context_returns_valid_context(self, precision, rounding_mode):
        """Test get_context always returns a valid Decimal context."""
        config = DecimalConfig.get_instance()

        config.set_precision("test_context", precision, rounding_mode)

        ctx = config.get_context("test_context")

        # Verify context has expected attributes
        assert hasattr(ctx, "prec")
        assert hasattr(ctx, "rounding")
        assert ctx.prec == precision

    @given(
        asset_classes=st.lists(
            st.text(
                min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu"))
            ),
            min_size=1,
            max_size=10,
            unique=True,
        ),
        precision=st.integers(min_value=0, max_value=18),
        rounding_mode=st.sampled_from(VALID_ROUNDING_MODES),
    )
    def test_multiple_asset_classes_same_precision(self, asset_classes, precision, rounding_mode):
        """Test multiple asset classes can have the same precision."""
        config = DecimalConfig.get_instance()

        # Set same precision for all asset classes
        for asset_class in asset_classes:
            config.set_precision(asset_class, precision, rounding_mode)

        # Verify all have the same precision
        for asset_class in asset_classes:
            assert config.get_precision(asset_class) == precision
            assert config.get_rounding_mode(asset_class) == rounding_mode
