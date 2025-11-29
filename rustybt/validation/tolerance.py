"""
Tolerance Configuration System.

This module provides configurable tolerance values for validation comparison
between rustybt and Backtrader frameworks. Tolerances account for acceptable
differences due to floating-point precision, datetime serialization, and
other implementation variations.

Supports:
- YAML-based configuration with defaults
- Per-layer tolerance groups
- Override capabilities for specific strategies
- Validation of tolerance values
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml


class ToleranceConfigError(Exception):
    """Exception raised for tolerance configuration errors."""

    pass


@dataclass
class Layer1Tolerances:
    """Layer 1: Data Handling tolerances.

    Used for lookahead bias detection and bar alignment comparison.

    Attributes:
        timestamp_window_ms: Milliseconds allowed between framework timestamps
        price_decimal_places: Number of decimal places for price comparison
        volume_tolerance_pct: Percentage tolerance for volume comparison
        bar_count_tolerance: Allowed difference in bar counts (0 = exact)
    """

    timestamp_window_ms: int = 1
    price_decimal_places: int = 4
    volume_tolerance_pct: float = 0.001
    bar_count_tolerance: int = 0

    def __post_init__(self) -> None:
        """Validate tolerance values."""
        if self.timestamp_window_ms < 0:
            raise ToleranceConfigError("timestamp_window_ms must be non-negative")
        if self.price_decimal_places < 0:
            raise ToleranceConfigError("price_decimal_places must be non-negative")
        if self.volume_tolerance_pct < 0:
            raise ToleranceConfigError("volume_tolerance_pct must be non-negative")
        if self.bar_count_tolerance < 0:
            raise ToleranceConfigError("bar_count_tolerance must be non-negative")

    @property
    def price_tolerance(self) -> Decimal:
        """Calculate price tolerance as Decimal for comparison.

        Returns:
            Decimal representing the minimum difference that is significant.
            For 4 decimal places, returns 0.0001.
        """
        return Decimal(10) ** -self.price_decimal_places


@dataclass
class Layer2Tolerances:
    """Layer 2: Signal Computation tolerances.

    Used for comparing indicator values and signal outputs.

    Attributes:
        indicator_decimal_places: Number of decimal places for indicator comparison
        signal_tolerance_pct: Percentage tolerance for signal values
        signal_exact_match: Whether boolean signals must match exactly
        signal_timestamp_window_ms: Milliseconds allowed for signal timestamp alignment
    """

    indicator_decimal_places: int = 4
    signal_tolerance_pct: float = 0.0001
    signal_exact_match: bool = True
    signal_timestamp_window_ms: int = 1

    def __post_init__(self) -> None:
        """Validate tolerance values."""
        if self.indicator_decimal_places < 0:
            raise ToleranceConfigError("indicator_decimal_places must be non-negative")
        if self.signal_tolerance_pct < 0:
            raise ToleranceConfigError("signal_tolerance_pct must be non-negative")
        if self.signal_timestamp_window_ms < 0:
            raise ToleranceConfigError("signal_timestamp_window_ms must be non-negative")

    @property
    def indicator_tolerance(self) -> Decimal:
        """Calculate indicator tolerance as Decimal for comparison.

        Returns:
            Decimal representing the minimum difference that is significant.
            For 4 decimal places, returns 0.0001.
        """
        return Decimal(10) ** -self.indicator_decimal_places


@dataclass
class Layer3Tolerances:
    """Layer 3: Order Lifecycle tolerances.

    Used for comparing order creation, fills, and cancellations.

    Attributes:
        order_timestamp_window_ms: Milliseconds allowed for order timestamp alignment
        fill_price_decimal_places: Number of decimal places for fill price comparison
        quantity_tolerance_pct: Percentage tolerance for order quantity
        order_id_exact_match: Whether order IDs must match (usually False)
    """

    order_timestamp_window_ms: int = 1
    fill_price_decimal_places: int = 4
    quantity_tolerance_pct: float = 0.0001
    order_id_exact_match: bool = False

    def __post_init__(self) -> None:
        """Validate tolerance values."""
        if self.order_timestamp_window_ms < 0:
            raise ToleranceConfigError("order_timestamp_window_ms must be non-negative")
        if self.fill_price_decimal_places < 0:
            raise ToleranceConfigError("fill_price_decimal_places must be non-negative")
        if self.quantity_tolerance_pct < 0:
            raise ToleranceConfigError("quantity_tolerance_pct must be non-negative")

    @property
    def fill_price_tolerance(self) -> Decimal:
        """Calculate fill price tolerance as Decimal for comparison."""
        return Decimal(10) ** -self.fill_price_decimal_places


@dataclass
class Layer4Tolerances:
    """Layer 4: Broker Transaction tolerances.

    Used for comparing broker fills, commissions, and slippage.

    Attributes:
        transaction_timestamp_window_ms: Milliseconds allowed for transaction timestamps
        commission_decimal_places: Number of decimal places for commission comparison
        slippage_tolerance_pct: Percentage tolerance for slippage calculations
        cash_decimal_places: Number of decimal places for cash comparison
    """

    transaction_timestamp_window_ms: int = 1
    commission_decimal_places: int = 2
    slippage_tolerance_pct: float = 0.001
    cash_decimal_places: int = 2

    def __post_init__(self) -> None:
        """Validate tolerance values."""
        if self.transaction_timestamp_window_ms < 0:
            raise ToleranceConfigError("transaction_timestamp_window_ms must be non-negative")
        if self.commission_decimal_places < 0:
            raise ToleranceConfigError("commission_decimal_places must be non-negative")
        if self.slippage_tolerance_pct < 0:
            raise ToleranceConfigError("slippage_tolerance_pct must be non-negative")
        if self.cash_decimal_places < 0:
            raise ToleranceConfigError("cash_decimal_places must be non-negative")

    @property
    def commission_tolerance(self) -> Decimal:
        """Calculate commission tolerance as Decimal for comparison."""
        return Decimal(10) ** -self.commission_decimal_places

    @property
    def cash_tolerance(self) -> Decimal:
        """Calculate cash tolerance as Decimal for comparison."""
        return Decimal(10) ** -self.cash_decimal_places


@dataclass
class Layer5Tolerances:
    """Layer 5: Portfolio Returns tolerances.

    Used for comparing portfolio values, returns, and metrics.

    Attributes:
        portfolio_value_decimal_places: Number of decimal places for portfolio value
        returns_tolerance_pct: Percentage tolerance for returns comparison
        sharpe_decimal_places: Number of decimal places for Sharpe ratio
        drawdown_tolerance_pct: Percentage tolerance for drawdown comparison
    """

    portfolio_value_decimal_places: int = 2
    returns_tolerance_pct: float = 0.0001
    sharpe_decimal_places: int = 4
    drawdown_tolerance_pct: float = 0.0001

    def __post_init__(self) -> None:
        """Validate tolerance values."""
        if self.portfolio_value_decimal_places < 0:
            raise ToleranceConfigError("portfolio_value_decimal_places must be non-negative")
        if self.returns_tolerance_pct < 0:
            raise ToleranceConfigError("returns_tolerance_pct must be non-negative")
        if self.sharpe_decimal_places < 0:
            raise ToleranceConfigError("sharpe_decimal_places must be non-negative")
        if self.drawdown_tolerance_pct < 0:
            raise ToleranceConfigError("drawdown_tolerance_pct must be non-negative")

    @property
    def portfolio_value_tolerance(self) -> Decimal:
        """Calculate portfolio value tolerance as Decimal for comparison."""
        return Decimal(10) ** -self.portfolio_value_decimal_places

    @property
    def sharpe_tolerance(self) -> Decimal:
        """Calculate Sharpe ratio tolerance as Decimal for comparison."""
        return Decimal(10) ** -self.sharpe_decimal_places


@dataclass
class ToleranceConfig:
    """Complete tolerance configuration for all validation layers.

    Provides access to per-layer tolerances and supports loading from YAML.

    Attributes:
        layer_1: Data handling tolerances
        layer_2: Signal computation tolerances
        layer_3: Order lifecycle tolerances
        layer_4: Broker transaction tolerances
        layer_5: Portfolio returns tolerances

    Example:
        >>> config = ToleranceConfig.load_from_yaml(Path("tolerances.yaml"))
        >>> print(config.layer_1.price_tolerance)
        0.0001
    """

    layer_1: Layer1Tolerances = field(default_factory=Layer1Tolerances)
    layer_2: Layer2Tolerances = field(default_factory=Layer2Tolerances)
    layer_3: Layer3Tolerances = field(default_factory=Layer3Tolerances)
    layer_4: Layer4Tolerances = field(default_factory=Layer4Tolerances)
    layer_5: Layer5Tolerances = field(default_factory=Layer5Tolerances)

    @classmethod
    def load_from_yaml(cls, config_path: Path) -> "ToleranceConfig":
        """Load tolerance configuration from YAML file.

        The YAML file can contain any subset of tolerance values.
        Missing values use defaults.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            ToleranceConfig with values from file merged with defaults

        Raises:
            ToleranceConfigError: If YAML is invalid or values are out of range
            FileNotFoundError: If config file does not exist
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Tolerance config not found: {config_path}")

        with open(config_path) as f:
            try:
                data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ToleranceConfigError(f"Invalid YAML in {config_path}: {e}") from e

        return cls._from_dict(data)

    @classmethod
    def load_from_directory(cls, config_dir: Path) -> "ToleranceConfig":
        """Load tolerance configuration from multiple YAML files in a directory.

        Looks for layer-specific files: layer_1_tolerances.yaml, etc.
        Missing files use defaults for that layer.

        Args:
            config_dir: Path to directory containing tolerance YAML files

        Returns:
            ToleranceConfig with values from all found files merged with defaults
        """
        config = cls()

        # Layer 1
        layer_1_path = config_dir / "layer_1_tolerances.yaml"
        if layer_1_path.exists():
            with open(layer_1_path) as f:
                data = yaml.safe_load(f) or {}
                if "layer_1_data" in data:
                    config.layer_1 = Layer1Tolerances(**data["layer_1_data"])

        # Layer 2
        layer_2_path = config_dir / "layer_2_tolerances.yaml"
        if layer_2_path.exists():
            with open(layer_2_path) as f:
                data = yaml.safe_load(f) or {}
                if "layer_2_signals" in data:
                    config.layer_2 = Layer2Tolerances(**data["layer_2_signals"])

        # Layer 3
        layer_3_path = config_dir / "layer_3_tolerances.yaml"
        if layer_3_path.exists():
            with open(layer_3_path) as f:
                data = yaml.safe_load(f) or {}
                if "layer_3_orders" in data:
                    config.layer_3 = Layer3Tolerances(**data["layer_3_orders"])

        # Layer 4
        layer_4_path = config_dir / "layer_4_tolerances.yaml"
        if layer_4_path.exists():
            with open(layer_4_path) as f:
                data = yaml.safe_load(f) or {}
                if "layer_4_broker" in data:
                    config.layer_4 = Layer4Tolerances(**data["layer_4_broker"])

        # Layer 5
        layer_5_path = config_dir / "layer_5_tolerances.yaml"
        if layer_5_path.exists():
            with open(layer_5_path) as f:
                data = yaml.safe_load(f) or {}
                if "layer_5_portfolio" in data:
                    config.layer_5 = Layer5Tolerances(**data["layer_5_portfolio"])

        return config

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "ToleranceConfig":
        """Create ToleranceConfig from dictionary.

        Args:
            data: Dictionary with layer tolerance values

        Returns:
            ToleranceConfig with values from dict merged with defaults
        """
        config = cls()

        if "layer_1_data" in data:
            config.layer_1 = Layer1Tolerances(**data["layer_1_data"])

        if "layer_2_signals" in data:
            config.layer_2 = Layer2Tolerances(**data["layer_2_signals"])

        if "layer_3_orders" in data:
            config.layer_3 = Layer3Tolerances(**data["layer_3_orders"])

        if "layer_4_broker" in data:
            config.layer_4 = Layer4Tolerances(**data["layer_4_broker"])

        if "layer_5_portfolio" in data:
            config.layer_5 = Layer5Tolerances(**data["layer_5_portfolio"])

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert ToleranceConfig to dictionary for serialization.

        Returns:
            Dictionary with all layer tolerances
        """
        return {
            "layer_1_data": {
                "timestamp_window_ms": self.layer_1.timestamp_window_ms,
                "price_decimal_places": self.layer_1.price_decimal_places,
                "volume_tolerance_pct": self.layer_1.volume_tolerance_pct,
                "bar_count_tolerance": self.layer_1.bar_count_tolerance,
            },
            "layer_2_signals": {
                "indicator_decimal_places": self.layer_2.indicator_decimal_places,
                "signal_tolerance_pct": self.layer_2.signal_tolerance_pct,
                "signal_exact_match": self.layer_2.signal_exact_match,
                "signal_timestamp_window_ms": self.layer_2.signal_timestamp_window_ms,
            },
            "layer_3_orders": {
                "order_timestamp_window_ms": self.layer_3.order_timestamp_window_ms,
                "fill_price_decimal_places": self.layer_3.fill_price_decimal_places,
                "quantity_tolerance_pct": self.layer_3.quantity_tolerance_pct,
                "order_id_exact_match": self.layer_3.order_id_exact_match,
            },
            "layer_4_broker": {
                "transaction_timestamp_window_ms": self.layer_4.transaction_timestamp_window_ms,
                "commission_decimal_places": self.layer_4.commission_decimal_places,
                "slippage_tolerance_pct": self.layer_4.slippage_tolerance_pct,
                "cash_decimal_places": self.layer_4.cash_decimal_places,
            },
            "layer_5_portfolio": {
                "portfolio_value_decimal_places": self.layer_5.portfolio_value_decimal_places,
                "returns_tolerance_pct": self.layer_5.returns_tolerance_pct,
                "sharpe_decimal_places": self.layer_5.sharpe_decimal_places,
                "drawdown_tolerance_pct": self.layer_5.drawdown_tolerance_pct,
            },
        }

    def with_overrides(self, **kwargs: Any) -> "ToleranceConfig":
        """Create a new config with specific values overridden.

        Useful for strategy-specific tolerance adjustments.

        Args:
            **kwargs: Tolerance values to override in format layer_field
                Example: layer_1_price_decimal_places=6

        Returns:
            New ToleranceConfig with overrides applied

        Example:
            >>> config = ToleranceConfig()
            >>> strict = config.with_overrides(layer_1_price_decimal_places=6)
            >>> print(strict.layer_1.price_decimal_places)
            6
        """
        data = self.to_dict()

        for key, value in kwargs.items():
            parts = key.split("_", 2)
            if len(parts) >= 3 and parts[0] == "layer":
                layer_num = parts[1]
                field_name = "_".join(parts[2:])

                layer_key_map = {
                    "1": "layer_1_data",
                    "2": "layer_2_signals",
                    "3": "layer_3_orders",
                    "4": "layer_4_broker",
                    "5": "layer_5_portfolio",
                }

                layer_key = layer_key_map.get(layer_num)
                if layer_key and layer_key in data:
                    if field_name in data[layer_key]:
                        data[layer_key][field_name] = value

        return self._from_dict(data)


def get_default_tolerances() -> ToleranceConfig:
    """Get default tolerance configuration.

    Returns:
        ToleranceConfig with all default values
    """
    return ToleranceConfig()
