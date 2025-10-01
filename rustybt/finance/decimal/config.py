"""Decimal precision configuration system for RustyBT.

This module provides configurable precision management for Decimal arithmetic,
allowing different asset classes to use appropriate precision per data provider
specifications.
"""

import json
import threading
from collections.abc import Generator
from contextlib import contextmanager
from decimal import (
    ROUND_05UP,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Context,
    localcontext,
)
from pathlib import Path
from typing import Any, Literal, Optional

import structlog
import yaml

logger = structlog.get_logger(__name__)

# Type alias for asset classes
AssetClass = Literal["crypto", "equity", "forex", "future", "index"]

# Valid rounding modes mapping
ROUNDING_MODES = {
    "ROUND_HALF_EVEN": ROUND_HALF_EVEN,
    "ROUND_DOWN": ROUND_DOWN,
    "ROUND_HALF_UP": ROUND_HALF_UP,
    "ROUND_UP": ROUND_UP,
    "ROUND_CEILING": ROUND_CEILING,
    "ROUND_FLOOR": ROUND_FLOOR,
    "ROUND_05UP": ROUND_05UP,
    "ROUND_HALF_DOWN": ROUND_HALF_DOWN,
}


class DecimalConfigError(Exception):
    """Base exception for Decimal configuration errors."""


class InvalidPrecisionError(DecimalConfigError):
    """Raised when precision is out of valid range (0-18)."""


class InvalidRoundingModeError(DecimalConfigError):
    """Raised when rounding mode is not recognized."""


class InvalidAssetClassError(DecimalConfigError):
    """Raised when asset class is not recognized."""


class DecimalConfig:
    """Manages Decimal precision configuration for different asset classes.

    This class implements a singleton pattern to ensure consistent configuration
    across the application. It supports loading configuration from YAML, JSON,
    or programmatically via dictionaries.

    Example:
        >>> config = DecimalConfig.get_instance()
        >>> config.get_precision("crypto")
        18
        >>> with config.with_precision("crypto") as ctx:
        ...     value = Decimal("1.123456789")
        ...     result = +value  # Apply current context
    """

    _instance: Optional["DecimalConfig"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "DecimalConfig":
        """Implement singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize DecimalConfig with default configuration."""
        # Only initialize once (singleton pattern)
        if hasattr(self, "_initialized"):
            return

        self._config: dict[str, Any] = {}
        self._thread_local = threading.local()

        # Load default configuration
        default_config_path = Path(__file__).parent / "default_config.yaml"
        self.load_from_yaml(str(default_config_path))

        self._initialized = True
        logger.info("decimal_config_initialized", config_source=str(default_config_path))

    @classmethod
    def get_instance(cls) -> "DecimalConfig":
        """Get the singleton instance of DecimalConfig.

        Returns:
            DecimalConfig: The singleton instance.
        """
        return cls()

    def load_from_yaml(self, file_path: str) -> None:
        """Load configuration from a YAML file.

        Args:
            file_path: Path to YAML configuration file.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file is not valid YAML.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with path.open("r") as f:
            config_dict = yaml.safe_load(f)

        self.load_from_dict(config_dict)
        logger.info("config_loaded_from_yaml", file_path=file_path)

    def load_from_json(self, file_path: str) -> None:
        """Load configuration from a JSON file.

        Args:
            file_path: Path to JSON configuration file.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with path.open("r") as f:
            config_dict = json.load(f)

        self.load_from_dict(config_dict)
        logger.info("config_loaded_from_json", file_path=file_path)

    def load_from_dict(self, config_dict: dict[str, Any]) -> None:
        """Load configuration from a dictionary.

        Args:
            config_dict: Configuration dictionary with structure:
                {
                    "global_defaults": {
                        "precision": int,
                        "rounding_mode": str,
                        "scale": int
                    },
                    "asset_classes": {
                        "crypto": {...},
                        "equity": {...},
                        ...
                    }
                }

        Raises:
            InvalidPrecisionError: If precision values are invalid.
            InvalidRoundingModeError: If rounding modes are invalid.
        """
        self._config = config_dict
        self.validate_config()
        asset_classes = list(config_dict.get("asset_classes", {}).keys())
        logger.info("config_loaded_from_dict", asset_classes=asset_classes)

    def validate_config(self) -> bool:
        """Validate the entire configuration.

        Returns:
            True if configuration is valid.

        Raises:
            InvalidPrecisionError: If any precision value is invalid.
            InvalidRoundingModeError: If any rounding mode is invalid.
            InvalidAssetClassError: If configuration structure is invalid.
        """
        if "global_defaults" not in self._config:
            raise InvalidAssetClassError("Configuration missing 'global_defaults' section")

        if "asset_classes" not in self._config:
            raise InvalidAssetClassError("Configuration missing 'asset_classes' section")

        # Validate global defaults
        global_defaults = self._config["global_defaults"]
        self._validate_precision(global_defaults.get("precision", 18))
        self._validate_rounding_mode(global_defaults.get("rounding_mode", "ROUND_HALF_EVEN"))

        # Validate each asset class
        for asset_class, settings in self._config["asset_classes"].items():
            self._validate_precision(settings.get("precision", 18))
            self._validate_rounding_mode(settings.get("rounding_mode", "ROUND_HALF_EVEN"))

            # Warn if precision seems unusual
            if asset_class == "crypto" and settings.get("scale", 8) < 8:
                logger.warning(
                    "unusual_crypto_scale",
                    asset_class=asset_class,
                    scale=settings.get("scale"),
                    message="Crypto scale < 8 may not support Satoshi precision",
                )

        return True

    def _validate_precision(self, precision: int) -> None:
        """Validate precision is in valid range.

        Args:
            precision: Precision value to validate.

        Raises:
            InvalidPrecisionError: If precision is not in range 0-18.
            TypeError: If precision is not an integer.
        """
        if not isinstance(precision, int):
            raise TypeError(f"Precision must be int, got {type(precision).__name__}")

        if not 0 <= precision <= 18:
            raise InvalidPrecisionError(
                f"Precision must be 0-18, got {precision}. "
                f"Higher precision values may cause performance degradation."
            )

    def _validate_rounding_mode(self, rounding_mode: str) -> None:
        """Validate rounding mode is recognized.

        Args:
            rounding_mode: Rounding mode to validate.

        Raises:
            InvalidRoundingModeError: If rounding mode is not recognized.
            TypeError: If rounding_mode is not a string.
        """
        if not isinstance(rounding_mode, str):
            raise TypeError(f"Rounding mode must be str, got {type(rounding_mode).__name__}")

        if rounding_mode not in ROUNDING_MODES:
            raise InvalidRoundingModeError(
                f"Invalid rounding mode: {rounding_mode}. "
                f"Valid modes: {', '.join(ROUNDING_MODES.keys())}"
            )

    def get_precision(self, asset_class: str) -> int:
        """Get precision (total significant digits) for an asset class.

        Args:
            asset_class: Asset class identifier (e.g., "crypto", "equity").

        Returns:
            Precision value (number of significant digits).

        Raises:
            InvalidAssetClassError: If asset class is not found in configuration.
        """
        if asset_class not in self._config.get("asset_classes", {}):
            raise InvalidAssetClassError(
                f"Unknown asset class: {asset_class}. "
                f"Available classes: {', '.join(self._config.get('asset_classes', {}).keys())}"
            )

        return self._config["asset_classes"][asset_class]["precision"]

    def get_scale(self, asset_class: str) -> int:
        """Get scale (decimal places for display) for an asset class.

        Args:
            asset_class: Asset class identifier.

        Returns:
            Scale value (number of decimal places).

        Raises:
            InvalidAssetClassError: If asset class is not found.
        """
        if asset_class not in self._config.get("asset_classes", {}):
            raise InvalidAssetClassError(
                f"Unknown asset class: {asset_class}. "
                f"Available classes: {', '.join(self._config.get('asset_classes', {}).keys())}"
            )

        return self._config["asset_classes"][asset_class].get("scale", 8)

    def get_rounding_mode(self, asset_class: str) -> str:
        """Get rounding mode constant name for an asset class.

        Args:
            asset_class: Asset class identifier.

        Returns:
            Rounding mode constant name (e.g., "ROUND_HALF_EVEN").

        Raises:
            InvalidAssetClassError: If asset class is not found.
        """
        if asset_class not in self._config.get("asset_classes", {}):
            raise InvalidAssetClassError(
                f"Unknown asset class: {asset_class}. "
                f"Available classes: {', '.join(self._config.get('asset_classes', {}).keys())}"
            )

        return self._config["asset_classes"][asset_class]["rounding_mode"]

    def get_rounding_constant(self, asset_class: str) -> str:
        """Get rounding mode constant for an asset class.

        Args:
            asset_class: Asset class identifier.

        Returns:
            Rounding mode constant from decimal module.

        Raises:
            InvalidAssetClassError: If asset class is not found.
        """
        rounding_mode_name = self.get_rounding_mode(asset_class)
        return ROUNDING_MODES[rounding_mode_name]

    def set_precision(
        self, asset_class: str, precision: int, rounding_mode: str, scale: int | None = None
    ) -> None:
        """Set precision and rounding mode for an asset class.

        Args:
            asset_class: Asset class identifier.
            precision: Precision value (0-18).
            rounding_mode: Rounding mode name (e.g., "ROUND_HALF_EVEN").
            scale: Optional scale (decimal places for display).

        Raises:
            InvalidPrecisionError: If precision is out of range.
            InvalidRoundingModeError: If rounding mode is invalid.
        """
        self._validate_precision(precision)
        self._validate_rounding_mode(rounding_mode)

        if "asset_classes" not in self._config:
            self._config["asset_classes"] = {}

        if asset_class not in self._config["asset_classes"]:
            self._config["asset_classes"][asset_class] = {}

        self._config["asset_classes"][asset_class]["precision"] = precision
        self._config["asset_classes"][asset_class]["rounding_mode"] = rounding_mode

        if scale is not None:
            self._config["asset_classes"][asset_class]["scale"] = scale

        logger.info(
            "precision_set",
            asset_class=asset_class,
            precision=precision,
            rounding_mode=rounding_mode,
            scale=scale,
        )

    def get_context(self, asset_class: str) -> Context:
        """Get a Decimal context configured for an asset class.

        This creates a new context with the precision and rounding mode
        configured for the specified asset class.

        Args:
            asset_class: Asset class identifier.

        Returns:
            Decimal Context configured for the asset class.

        Raises:
            InvalidAssetClassError: If asset class is not found.
        """
        precision = self.get_precision(asset_class)
        rounding = self.get_rounding_constant(asset_class)

        ctx = Context(prec=precision, rounding=rounding)
        return ctx

    @contextmanager
    def with_precision(self, asset_class: str) -> Generator[Context, None, None]:
        """Context manager for temporary precision switching.

        This uses decimal.localcontext() to provide thread-safe,
        temporary precision changes.

        Args:
            asset_class: Asset class identifier.

        Yields:
            Decimal Context configured for the asset class.

        Example:
            >>> config = DecimalConfig.get_instance()
            >>> with config.with_precision("crypto") as ctx:
            ...     value = Decimal("1.123456789")
            ...     result = +value  # Apply current context
        """
        precision = self.get_precision(asset_class)
        rounding = self.get_rounding_constant(asset_class)

        with localcontext() as ctx:
            ctx.prec = precision
            ctx.rounding = rounding
            logger.debug(
                "context_activated",
                asset_class=asset_class,
                precision=precision,
                rounding_mode=self.get_rounding_mode(asset_class),
            )
            yield ctx
