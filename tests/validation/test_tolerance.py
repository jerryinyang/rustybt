"""Tests for tolerance configuration system."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from rustybt.validation.tolerance import (
    Layer1Tolerances,
    Layer2Tolerances,
    Layer3Tolerances,
    Layer4Tolerances,
    Layer5Tolerances,
    ToleranceConfig,
    ToleranceConfigError,
    get_default_tolerances,
)


class TestLayer1Tolerances:
    """Tests for Layer 1 (Data Handling) tolerances."""

    def test_default_values(self) -> None:
        """Test default tolerance values."""
        tolerances = Layer1Tolerances()
        assert tolerances.timestamp_window_ms == 1
        assert tolerances.price_decimal_places == 4
        assert tolerances.volume_tolerance_pct == 0.001
        assert tolerances.bar_count_tolerance == 0

    def test_custom_values(self) -> None:
        """Test custom tolerance values."""
        tolerances = Layer1Tolerances(
            timestamp_window_ms=5,
            price_decimal_places=6,
            volume_tolerance_pct=0.01,
            bar_count_tolerance=1,
        )
        assert tolerances.timestamp_window_ms == 5
        assert tolerances.price_decimal_places == 6
        assert tolerances.volume_tolerance_pct == 0.01
        assert tolerances.bar_count_tolerance == 1

    def test_price_tolerance_calculation(self) -> None:
        """Test price tolerance calculation as Decimal."""
        tolerances = Layer1Tolerances(price_decimal_places=4)
        assert tolerances.price_tolerance == Decimal("0.0001")

        tolerances = Layer1Tolerances(price_decimal_places=2)
        assert tolerances.price_tolerance == Decimal("0.01")

        tolerances = Layer1Tolerances(price_decimal_places=6)
        assert tolerances.price_tolerance == Decimal("0.000001")

    def test_validation_negative_timestamp(self) -> None:
        """Test validation rejects negative timestamp window."""
        with pytest.raises(ToleranceConfigError, match="timestamp_window_ms"):
            Layer1Tolerances(timestamp_window_ms=-1)

    def test_validation_negative_price_places(self) -> None:
        """Test validation rejects negative decimal places."""
        with pytest.raises(ToleranceConfigError, match="price_decimal_places"):
            Layer1Tolerances(price_decimal_places=-1)

    def test_validation_negative_volume_pct(self) -> None:
        """Test validation rejects negative volume tolerance."""
        with pytest.raises(ToleranceConfigError, match="volume_tolerance_pct"):
            Layer1Tolerances(volume_tolerance_pct=-0.001)

    def test_validation_negative_bar_count(self) -> None:
        """Test validation rejects negative bar count tolerance."""
        with pytest.raises(ToleranceConfigError, match="bar_count_tolerance"):
            Layer1Tolerances(bar_count_tolerance=-1)


class TestLayer2Tolerances:
    """Tests for Layer 2 (Signal Computation) tolerances."""

    def test_default_values(self) -> None:
        """Test default tolerance values."""
        tolerances = Layer2Tolerances()
        assert tolerances.indicator_decimal_places == 4
        assert tolerances.signal_tolerance_pct == 0.0001
        assert tolerances.signal_exact_match is True
        assert tolerances.signal_timestamp_window_ms == 1

    def test_indicator_tolerance_calculation(self) -> None:
        """Test indicator tolerance calculation as Decimal."""
        tolerances = Layer2Tolerances(indicator_decimal_places=4)
        assert tolerances.indicator_tolerance == Decimal("0.0001")

    def test_validation_negative_values(self) -> None:
        """Test validation rejects negative values."""
        with pytest.raises(ToleranceConfigError):
            Layer2Tolerances(indicator_decimal_places=-1)
        with pytest.raises(ToleranceConfigError):
            Layer2Tolerances(signal_tolerance_pct=-0.01)


class TestLayer3Tolerances:
    """Tests for Layer 3 (Order Lifecycle) tolerances."""

    def test_default_values(self) -> None:
        """Test default tolerance values."""
        tolerances = Layer3Tolerances()
        assert tolerances.order_timestamp_window_ms == 1
        assert tolerances.fill_price_decimal_places == 4
        assert tolerances.quantity_tolerance_pct == 0.0001
        assert tolerances.order_id_exact_match is False

    def test_fill_price_tolerance_calculation(self) -> None:
        """Test fill price tolerance calculation as Decimal."""
        tolerances = Layer3Tolerances(fill_price_decimal_places=2)
        assert tolerances.fill_price_tolerance == Decimal("0.01")


class TestLayer4Tolerances:
    """Tests for Layer 4 (Broker Transaction) tolerances."""

    def test_default_values(self) -> None:
        """Test default tolerance values."""
        tolerances = Layer4Tolerances()
        assert tolerances.transaction_timestamp_window_ms == 1
        assert tolerances.commission_decimal_places == 2
        assert tolerances.slippage_tolerance_pct == 0.001
        assert tolerances.cash_decimal_places == 2

    def test_commission_tolerance_calculation(self) -> None:
        """Test commission tolerance calculation as Decimal."""
        tolerances = Layer4Tolerances(commission_decimal_places=2)
        assert tolerances.commission_tolerance == Decimal("0.01")

    def test_cash_tolerance_calculation(self) -> None:
        """Test cash tolerance calculation as Decimal."""
        tolerances = Layer4Tolerances(cash_decimal_places=2)
        assert tolerances.cash_tolerance == Decimal("0.01")


class TestLayer5Tolerances:
    """Tests for Layer 5 (Portfolio Returns) tolerances."""

    def test_default_values(self) -> None:
        """Test default tolerance values."""
        tolerances = Layer5Tolerances()
        assert tolerances.portfolio_value_decimal_places == 2
        assert tolerances.returns_tolerance_pct == 0.0001
        assert tolerances.sharpe_decimal_places == 4
        assert tolerances.drawdown_tolerance_pct == 0.0001

    def test_portfolio_value_tolerance_calculation(self) -> None:
        """Test portfolio value tolerance calculation as Decimal."""
        tolerances = Layer5Tolerances(portfolio_value_decimal_places=2)
        assert tolerances.portfolio_value_tolerance == Decimal("0.01")

    def test_sharpe_tolerance_calculation(self) -> None:
        """Test Sharpe ratio tolerance calculation as Decimal."""
        tolerances = Layer5Tolerances(sharpe_decimal_places=4)
        assert tolerances.sharpe_tolerance == Decimal("0.0001")


class TestToleranceConfig:
    """Tests for ToleranceConfig class."""

    def test_default_config(self) -> None:
        """Test default configuration has all layers."""
        config = ToleranceConfig()
        assert isinstance(config.layer_1, Layer1Tolerances)
        assert isinstance(config.layer_2, Layer2Tolerances)
        assert isinstance(config.layer_3, Layer3Tolerances)
        assert isinstance(config.layer_4, Layer4Tolerances)
        assert isinstance(config.layer_5, Layer5Tolerances)

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        """Test loading config from YAML file."""
        config_path = tmp_path / "tolerances.yaml"
        config_path.write_text(
            """
layer_1_data:
  timestamp_window_ms: 5
  price_decimal_places: 6
layer_2_signals:
  indicator_decimal_places: 8
"""
        )

        config = ToleranceConfig.load_from_yaml(config_path)

        assert config.layer_1.timestamp_window_ms == 5
        assert config.layer_1.price_decimal_places == 6
        assert config.layer_2.indicator_decimal_places == 8
        # Defaults for unspecified values
        assert config.layer_1.volume_tolerance_pct == 0.001

    def test_load_from_yaml_file_not_found(self, tmp_path: Path) -> None:
        """Test FileNotFoundError for missing config file."""
        with pytest.raises(FileNotFoundError):
            ToleranceConfig.load_from_yaml(tmp_path / "nonexistent.yaml")

    def test_load_from_yaml_invalid_yaml(self, tmp_path: Path) -> None:
        """Test ToleranceConfigError for invalid YAML."""
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text("invalid: yaml: content:")

        with pytest.raises(ToleranceConfigError, match="Invalid YAML"):
            ToleranceConfig.load_from_yaml(config_path)

    def test_load_from_directory(self, tmp_path: Path) -> None:
        """Test loading config from directory with multiple files."""
        # Create layer 1 config
        layer_1_path = tmp_path / "layer_1_tolerances.yaml"
        layer_1_path.write_text(
            """
layer_1_data:
  timestamp_window_ms: 10
  price_decimal_places: 5
"""
        )

        # Create layer 2 config
        layer_2_path = tmp_path / "layer_2_tolerances.yaml"
        layer_2_path.write_text(
            """
layer_2_signals:
  indicator_decimal_places: 6
"""
        )

        config = ToleranceConfig.load_from_directory(tmp_path)

        assert config.layer_1.timestamp_window_ms == 10
        assert config.layer_1.price_decimal_places == 5
        assert config.layer_2.indicator_decimal_places == 6
        # Layer 3-5 should have defaults
        assert config.layer_3.order_timestamp_window_ms == 1

    def test_load_from_directory_missing_files(self, tmp_path: Path) -> None:
        """Test loading from directory with no config files uses defaults."""
        config = ToleranceConfig.load_from_directory(tmp_path)

        # All should be defaults
        assert config.layer_1.timestamp_window_ms == 1
        assert config.layer_2.indicator_decimal_places == 4

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        config = ToleranceConfig()
        data = config.to_dict()

        assert "layer_1_data" in data
        assert "layer_2_signals" in data
        assert "layer_3_orders" in data
        assert "layer_4_broker" in data
        assert "layer_5_portfolio" in data

        assert data["layer_1_data"]["timestamp_window_ms"] == 1
        assert data["layer_2_signals"]["signal_exact_match"] is True

    def test_with_overrides(self) -> None:
        """Test creating config with overrides."""
        config = ToleranceConfig()
        overridden = config.with_overrides(
            layer_1_price_decimal_places=6,
            layer_2_indicator_decimal_places=8,
        )

        # Original unchanged
        assert config.layer_1.price_decimal_places == 4

        # Override applied
        assert overridden.layer_1.price_decimal_places == 6
        assert overridden.layer_2.indicator_decimal_places == 8

        # Other values unchanged
        assert overridden.layer_1.timestamp_window_ms == 1

    def test_with_overrides_invalid_key_ignored(self) -> None:
        """Test that invalid override keys are ignored."""
        config = ToleranceConfig()
        overridden = config.with_overrides(
            layer_99_fake_field=100,  # Should be ignored
        )

        # No changes from original
        assert overridden.layer_1.price_decimal_places == 4


class TestGetDefaultTolerances:
    """Tests for get_default_tolerances function."""

    def test_returns_default_config(self) -> None:
        """Test get_default_tolerances returns default config."""
        config = get_default_tolerances()
        assert isinstance(config, ToleranceConfig)
        assert config.layer_1.timestamp_window_ms == 1


class TestToleranceConfigIntegration:
    """Integration tests for tolerance configuration."""

    def test_load_actual_config_files(self) -> None:
        """Test loading the actual config files from the test directory."""
        config_dir = Path("tests/validation/config")
        if not config_dir.exists():
            pytest.skip("Config directory not found")

        config = ToleranceConfig.load_from_directory(config_dir)

        # Verify layer 1 loaded correctly
        assert config.layer_1.timestamp_window_ms == 1
        assert config.layer_1.price_decimal_places == 4

        # Verify layer 2 loaded correctly
        assert config.layer_2.indicator_decimal_places == 4
        assert config.layer_2.signal_exact_match is True

    def test_roundtrip_yaml(self, tmp_path: Path) -> None:
        """Test config survives YAML roundtrip."""
        original = ToleranceConfig()
        original_dict = original.to_dict()

        # Write to YAML
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(original_dict, f)

        # Load back
        loaded = ToleranceConfig.load_from_yaml(config_path)

        # Compare
        assert loaded.layer_1.timestamp_window_ms == original.layer_1.timestamp_window_ms
        assert loaded.layer_2.signal_exact_match == original.layer_2.signal_exact_match
        assert loaded.layer_5.returns_tolerance_pct == original.layer_5.returns_tolerance_pct
