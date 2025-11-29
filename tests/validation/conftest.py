"""
Pytest Fixtures for Validation Framework.

This module defines shared fixtures for validation tests, including
session management, data loading, and tolerance configuration.
"""
from pathlib import Path

import pytest

from rustybt.validation.tolerance import (
    ToleranceConfig,
)


@pytest.fixture
def tolerance_config() -> ToleranceConfig:
    """Provide default tolerance configuration for tests.

    Returns:
        ToleranceConfig with default values.
    """
    config_dir = Path("tests/validation/config")
    if config_dir.exists():
        return ToleranceConfig.load_from_directory(config_dir)
    return ToleranceConfig()


@pytest.fixture
def layer_1_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 1 (Data Handling) tolerances with override capability.

    Example usage in test:
        def test_example(layer_1_tolerances):
            # Get default value
            assert layer_1_tolerances.price_decimal_places == 4

            # Override for stricter test
            layer_1_tolerances.price_decimal_places = 6
    """
    return tolerance_config.layer_1


@pytest.fixture
def layer_2_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 2 (Signal Computation) tolerances with override capability."""
    return tolerance_config.layer_2


@pytest.fixture
def layer_3_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 3 (Order Lifecycle) tolerances with override capability."""
    return tolerance_config.layer_3


@pytest.fixture
def layer_4_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 4 (Broker Transaction) tolerances with override capability."""
    return tolerance_config.layer_4


@pytest.fixture
def layer_5_tolerances(tolerance_config: ToleranceConfig):
    """Provide Layer 5 (Portfolio Returns) tolerances with override capability."""
    return tolerance_config.layer_5
