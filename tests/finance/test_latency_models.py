"""
Tests for latency simulation models (Story 4.1).

This module contains comprehensive tests for latency models including:
- Unit tests for each latency model type
- Property-based tests for latency invariants
- Integration tests for latency profile configuration
- Performance tests for simulation overhead
"""

import json
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from rustybt.finance.execution import (
    BrokerLatencyProfile,
    BrokerProcessingLatency,
    CompositeLatencyModel,
    ExchangeMatchingLatency,
    FixedLatencyModel,
    HistoricalLatencyModel,
    LatencyComponents,
    LatencyConfigurationError,
    LatencyProfileConfig,
    LatencyProfileRegistry,
    NetworkLatency,
    RandomLatencyModel,
)


class TestLatencyComponents:
    """Tests for LatencyComponents dataclass."""

    def test_latency_components_immutable(self) -> None:
        """LatencyComponents is immutable (frozen dataclass)."""
        components = LatencyComponents(
            network_ms=Decimal("10.0"),
            broker_processing_ms=Decimal("5.0"),
            exchange_matching_ms=Decimal("2.0"),
            total_ms=Decimal("17.0"),
        )

        with pytest.raises(AttributeError):
            components.network_ms = Decimal("20.0")

    def test_latency_components_total_equals_sum(self) -> None:
        """Total latency should equal sum of components."""
        components = LatencyComponents(
            network_ms=Decimal("10.5"),
            broker_processing_ms=Decimal("3.2"),
            exchange_matching_ms=Decimal("1.8"),
            total_ms=Decimal("15.5"),
        )

        assert components.total_ms == Decimal("15.5")
        assert (
            components.network_ms
            + components.broker_processing_ms
            + components.exchange_matching_ms
            == Decimal("15.5")
        )


class TestFixedLatencyModel:
    """Tests for FixedLatencyModel."""

    def test_fixed_latency_returns_constant_values(self) -> None:
        """Fixed latency model returns constant values."""
        model = FixedLatencyModel(
            network_ms=Decimal("10.0"),
            broker_ms=Decimal("5.0"),
            exchange_ms=Decimal("2.0"),
        )

        # Call multiple times with different inputs
        for _ in range(10):
            latency = model.calculate_latency(
                order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
            )

            assert latency.network_ms == Decimal("10.0")
            assert latency.broker_processing_ms == Decimal("5.0")
            assert latency.exchange_matching_ms == Decimal("2.0")
            assert latency.total_ms == Decimal("17.0")

    def test_fixed_latency_total_is_sum_of_components(self) -> None:
        """Fixed latency total equals sum of components."""
        model = FixedLatencyModel(
            network_ms=Decimal("12.5"),
            broker_ms=Decimal("3.7"),
            exchange_ms=Decimal("1.3"),
        )

        latency = model.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )

        assert latency.total_ms == Decimal("12.5") + Decimal("3.7") + Decimal("1.3")


class TestRandomLatencyModel:
    """Tests for RandomLatencyModel."""

    def test_uniform_latency_within_range(self) -> None:
        """Uniform random latency generates values within configured ranges."""
        model = RandomLatencyModel(
            network_range_ms=(Decimal("5.0"), Decimal("15.0")),
            broker_range_ms=(Decimal("1.0"), Decimal("10.0")),
            exchange_range_ms=(Decimal("0.1"), Decimal("5.0")),
            distribution="uniform",
        )

        # Generate multiple samples to test distribution
        for _ in range(100):
            latency = model.calculate_latency(
                order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
            )

            assert Decimal("5.0") <= latency.network_ms <= Decimal("15.0")
            assert Decimal("1.0") <= latency.broker_processing_ms <= Decimal("10.0")
            assert Decimal("0.1") <= latency.exchange_matching_ms <= Decimal("5.0")
            assert latency.total_ms == (
                latency.network_ms + latency.broker_processing_ms + latency.exchange_matching_ms
            )

    def test_normal_latency_within_range(self) -> None:
        """Normal random latency generates values within configured ranges."""
        model = RandomLatencyModel(
            network_range_ms=(Decimal("5.0"), Decimal("15.0")),
            broker_range_ms=(Decimal("1.0"), Decimal("10.0")),
            exchange_range_ms=(Decimal("0.1"), Decimal("5.0")),
            distribution="normal",
        )

        # Generate multiple samples
        for _ in range(100):
            latency = model.calculate_latency(
                order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
            )

            # Normal distribution is clipped to range
            assert Decimal("5.0") <= latency.network_ms <= Decimal("15.0")
            assert Decimal("1.0") <= latency.broker_processing_ms <= Decimal("10.0")
            assert Decimal("0.1") <= latency.exchange_matching_ms <= Decimal("5.0")

    def test_invalid_distribution_raises_error(self) -> None:
        """Invalid distribution type raises ValueError."""
        with pytest.raises(ValueError, match="Distribution must be"):
            RandomLatencyModel(
                network_range_ms=(Decimal("5.0"), Decimal("15.0")),
                broker_range_ms=(Decimal("1.0"), Decimal("10.0")),
                exchange_range_ms=(Decimal("0.1"), Decimal("5.0")),
                distribution="invalid",
            )

    def test_random_latency_variance(self) -> None:
        """Random latency produces different values across samples."""
        model = RandomLatencyModel(
            network_range_ms=(Decimal("5.0"), Decimal("15.0")),
            broker_range_ms=(Decimal("1.0"), Decimal("10.0")),
            exchange_range_ms=(Decimal("0.1"), Decimal("5.0")),
            distribution="uniform",
        )

        # Collect samples
        samples = [
            model.calculate_latency(
                order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
            )
            for _ in range(50)
        ]

        # Check that we get different values (at least 40 unique total latencies)
        unique_totals = len(set(s.total_ms for s in samples))
        assert unique_totals >= 40, "Random latency should produce varied results"


class TestHistoricalLatencyModel:
    """Tests for HistoricalLatencyModel."""

    def test_historical_latency_exact_match(self) -> None:
        """Historical latency returns exact match when timestamp exists."""
        latency_data = {
            pd.Timestamp("2024-01-01 10:00:00"): LatencyComponents(
                network_ms=Decimal("10.0"),
                broker_processing_ms=Decimal("5.0"),
                exchange_matching_ms=Decimal("2.0"),
                total_ms=Decimal("17.0"),
            ),
            pd.Timestamp("2024-01-01 10:01:00"): LatencyComponents(
                network_ms=Decimal("12.0"),
                broker_processing_ms=Decimal("6.0"),
                exchange_matching_ms=Decimal("3.0"),
                total_ms=Decimal("21.0"),
            ),
        }

        model = HistoricalLatencyModel(latency_data=latency_data)

        latency = model.calculate_latency(
            order=None,
            current_time=pd.Timestamp("2024-01-01 10:00:00"),
            broker_name="test",
        )

        assert latency.network_ms == Decimal("10.0")
        assert latency.broker_processing_ms == Decimal("5.0")
        assert latency.exchange_matching_ms == Decimal("2.0")
        assert latency.total_ms == Decimal("17.0")

    def test_historical_latency_nearest_match(self) -> None:
        """Historical latency returns nearest match when timestamp not exact."""
        latency_data = {
            pd.Timestamp("2024-01-01 10:00:00"): LatencyComponents(
                network_ms=Decimal("10.0"),
                broker_processing_ms=Decimal("5.0"),
                exchange_matching_ms=Decimal("2.0"),
                total_ms=Decimal("17.0"),
            ),
            pd.Timestamp("2024-01-01 10:10:00"): LatencyComponents(
                network_ms=Decimal("12.0"),
                broker_processing_ms=Decimal("6.0"),
                exchange_matching_ms=Decimal("3.0"),
                total_ms=Decimal("21.0"),
            ),
        }

        model = HistoricalLatencyModel(latency_data=latency_data)

        # Query at 10:04:00 - closer to 10:00:00
        latency = model.calculate_latency(
            order=None,
            current_time=pd.Timestamp("2024-01-01 10:04:00"),
            broker_name="test",
        )

        assert latency.total_ms == Decimal("17.0")

        # Query at 10:06:00 - closer to 10:10:00
        latency = model.calculate_latency(
            order=None,
            current_time=pd.Timestamp("2024-01-01 10:06:00"),
            broker_name="test",
        )

        assert latency.total_ms == Decimal("21.0")


class TestCompositeLatencyModel:
    """Tests for CompositeLatencyModel."""

    def test_composite_latency_sums_components(self) -> None:
        """Composite latency correctly sums component latencies."""
        network_model = FixedLatencyModel(
            network_ms=Decimal("10.0"),
            broker_ms=Decimal("0"),
            exchange_ms=Decimal("0"),
        )
        broker_model = FixedLatencyModel(
            network_ms=Decimal("0"),
            broker_ms=Decimal("5.0"),
            exchange_ms=Decimal("0"),
        )
        exchange_model = FixedLatencyModel(
            network_ms=Decimal("0"),
            broker_ms=Decimal("0"),
            exchange_ms=Decimal("2.0"),
        )

        composite = CompositeLatencyModel(
            network_model=network_model,
            broker_model=broker_model,
            exchange_model=exchange_model,
        )

        latency = composite.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )

        assert latency.network_ms == Decimal("10.0")
        assert latency.broker_processing_ms == Decimal("5.0")
        assert latency.exchange_matching_ms == Decimal("2.0")
        assert latency.total_ms == Decimal("17.0")


class TestNetworkLatency:
    """Tests for NetworkLatency model."""

    def test_network_latency_with_jitter(self) -> None:
        """Network latency applies jitter to base latency."""
        model = NetworkLatency(
            base_latency_ms=Decimal("20.0"),
            jitter_range_ms=(Decimal("-5.0"), Decimal("5.0")),
            location="US_EAST",
        )

        # Generate samples
        samples = [
            model.calculate_latency(
                order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
            )
            for _ in range(50)
        ]

        # All samples should be within base ± jitter range
        for sample in samples:
            assert Decimal("15.0") <= sample.network_ms <= Decimal("25.0")
            assert sample.broker_processing_ms == Decimal("0")
            assert sample.exchange_matching_ms == Decimal("0")

    def test_network_latency_never_negative(self) -> None:
        """Network latency is clamped to non-negative values."""
        model = NetworkLatency(
            base_latency_ms=Decimal("2.0"),
            jitter_range_ms=(Decimal("-5.0"), Decimal("5.0")),  # Can go negative
            location="US_EAST",
        )

        # Generate many samples
        for _ in range(100):
            latency = model.calculate_latency(
                order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
            )
            # Should never be negative (clamped to 0)
            assert latency.network_ms >= Decimal("0")


class TestBrokerProcessingLatency:
    """Tests for BrokerProcessingLatency model."""

    def test_broker_latency_within_range(self) -> None:
        """Broker processing latency stays within configured range."""
        model = BrokerProcessingLatency(
            base_processing_ms=Decimal("3.0"),
            complexity_factor=Decimal("0.5"),
            processing_range_ms=(Decimal("2.0"), Decimal("8.0")),
        )

        # Generate samples
        for _ in range(50):
            latency = model.calculate_latency(
                order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
            )

            assert Decimal("2.0") <= latency.broker_processing_ms <= Decimal("8.0")
            assert latency.network_ms == Decimal("0")
            assert latency.exchange_matching_ms == Decimal("0")


class TestExchangeMatchingLatency:
    """Tests for ExchangeMatchingLatency model."""

    def test_exchange_latency_within_range(self) -> None:
        """Exchange matching latency stays within configured range."""
        model = ExchangeMatchingLatency(
            base_matching_ms=Decimal("1.0"),
            queue_factor=Decimal("0.1"),
            matching_range_ms=(Decimal("0.1"), Decimal("5.0")),
            exchange_type="crypto",
        )

        # Generate samples
        for _ in range(50):
            latency = model.calculate_latency(
                order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
            )

            assert Decimal("0.1") <= latency.exchange_matching_ms <= Decimal("5.0")
            assert latency.network_ms == Decimal("0")
            assert latency.broker_processing_ms == Decimal("0")

    def test_exchange_type_multipliers(self) -> None:
        """Different exchange types apply correct multipliers."""
        # Crypto exchanges are faster (0.5x multiplier)
        crypto_model = ExchangeMatchingLatency(
            base_matching_ms=Decimal("2.0"),
            queue_factor=Decimal("0"),  # No queue effect
            matching_range_ms=(Decimal("0.1"), Decimal("10.0")),
            exchange_type="crypto",
        )

        # DEX exchanges are slower (2.0x multiplier)
        dex_model = ExchangeMatchingLatency(
            base_matching_ms=Decimal("2.0"),
            queue_factor=Decimal("0"),  # No queue effect
            matching_range_ms=(Decimal("0.1"), Decimal("10.0")),
            exchange_type="dex",
        )

        crypto_latency = crypto_model.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )
        dex_latency = dex_model.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )

        # Crypto should be faster than DEX
        assert crypto_latency.exchange_matching_ms < dex_latency.exchange_matching_ms


class TestLatencyProfileConfig:
    """Tests for LatencyProfileConfig."""

    def test_valid_latency_profile_config(self) -> None:
        """Valid latency profile configuration creates successfully."""
        config = LatencyProfileConfig(
            broker_name="Interactive Brokers",
            asset_class="equities",
            network_latency_ms=(10.0, 30.0),
            broker_processing_ms=(2.0, 8.0),
            exchange_matching_ms=(0.5, 3.0),
            distribution="normal",
            location="US_EAST",
        )

        assert config.broker_name == "Interactive Brokers"
        assert config.asset_class == "equities"
        assert config.distribution == "normal"

    def test_invalid_distribution_raises_error(self) -> None:
        """Invalid distribution in config raises ValidationError."""
        with pytest.raises(ValueError, match="Distribution must be"):
            LatencyProfileConfig(
                broker_name="Test Broker",
                asset_class="equities",
                network_latency_ms=(10.0, 30.0),
                broker_processing_ms=(2.0, 8.0),
                exchange_matching_ms=(0.5, 3.0),
                distribution="invalid",
            )

    def test_negative_latency_raises_error(self) -> None:
        """Negative latency values raise ValidationError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            LatencyProfileConfig(
                broker_name="Test Broker",
                asset_class="equities",
                network_latency_ms=(-5.0, 30.0),  # Negative min
                broker_processing_ms=(2.0, 8.0),
                exchange_matching_ms=(0.5, 3.0),
            )

    def test_max_less_than_min_raises_error(self) -> None:
        """Max latency < min latency raises ValidationError."""
        with pytest.raises(ValueError, match="must be >= minimum"):
            LatencyProfileConfig(
                broker_name="Test Broker",
                asset_class="equities",
                network_latency_ms=(30.0, 10.0),  # Max < min
                broker_processing_ms=(2.0, 8.0),
                exchange_matching_ms=(0.5, 3.0),
            )

    def test_to_latency_model_conversion(self) -> None:
        """Configuration converts to RandomLatencyModel correctly."""
        config = LatencyProfileConfig(
            broker_name="Test Broker",
            asset_class="equities",
            network_latency_ms=(10.0, 30.0),
            broker_processing_ms=(2.0, 8.0),
            exchange_matching_ms=(0.5, 3.0),
            distribution="uniform",
        )

        model = config.to_latency_model()

        assert isinstance(model, RandomLatencyModel)
        assert model.distribution == "uniform"

        # Test model works
        latency = model.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )

        assert Decimal("10.0") <= latency.network_ms <= Decimal("30.0")


class TestBrokerLatencyProfile:
    """Tests for BrokerLatencyProfile."""

    def test_get_profile_for_asset_class(self) -> None:
        """Get profile for specific asset class."""
        equities_config = LatencyProfileConfig(
            broker_name="Test Broker",
            asset_class="equities",
            network_latency_ms=(10.0, 30.0),
            broker_processing_ms=(2.0, 8.0),
            exchange_matching_ms=(0.5, 3.0),
        )

        crypto_config = LatencyProfileConfig(
            broker_name="Test Broker",
            asset_class="crypto",
            network_latency_ms=(20.0, 50.0),
            broker_processing_ms=(1.0, 5.0),
            exchange_matching_ms=(0.1, 2.0),
        )

        profile = BrokerLatencyProfile(
            broker_name="Test Broker",
            profiles=[equities_config, crypto_config],
        )

        equities_profile = profile.get_profile_for_asset_class("equities")
        assert equities_profile.asset_class == "equities"
        assert equities_profile.network_latency_ms == (10.0, 30.0)

        crypto_profile = profile.get_profile_for_asset_class("crypto")
        assert crypto_profile.asset_class == "crypto"
        assert crypto_profile.network_latency_ms == (20.0, 50.0)

    def test_default_profile_fallback(self) -> None:
        """Falls back to default profile when asset class not found."""
        default_config = LatencyProfileConfig(
            broker_name="Test Broker",
            asset_class="default",
            network_latency_ms=(15.0, 35.0),
            broker_processing_ms=(3.0, 7.0),
            exchange_matching_ms=(1.0, 4.0),
        )

        profile = BrokerLatencyProfile(
            broker_name="Test Broker",
            profiles=[],
            default_profile=default_config,
        )

        result = profile.get_profile_for_asset_class("unknown")
        assert result == default_config

    def test_no_profile_found_raises_error(self) -> None:
        """Raises error when asset class not found and no default."""
        profile = BrokerLatencyProfile(
            broker_name="Test Broker",
            profiles=[],
            default_profile=None,
        )

        with pytest.raises(LatencyConfigurationError, match="No latency profile found"):
            profile.get_profile_for_asset_class("unknown")


class TestLatencyProfileRegistry:
    """Tests for LatencyProfileRegistry."""

    def test_register_and_get_profile(self) -> None:
        """Register and retrieve broker latency profile."""
        registry = LatencyProfileRegistry()

        config = LatencyProfileConfig(
            broker_name="Test Broker",
            asset_class="equities",
            network_latency_ms=(10.0, 30.0),
            broker_processing_ms=(2.0, 8.0),
            exchange_matching_ms=(0.5, 3.0),
        )

        profile = BrokerLatencyProfile(
            broker_name="Test Broker",
            profiles=[config],
        )

        registry.register_profile(profile)

        retrieved = registry.get_profile("Test Broker", "equities")
        assert retrieved.broker_name == "Test Broker"
        assert retrieved.asset_class == "equities"

    def test_get_nonexistent_broker_raises_error(self) -> None:
        """Getting profile for nonexistent broker raises error."""
        registry = LatencyProfileRegistry()

        with pytest.raises(LatencyConfigurationError, match="No latency profile registered"):
            registry.get_profile("Nonexistent Broker")

    def test_load_from_dict(self) -> None:
        """Load broker profile from dictionary."""
        registry = LatencyProfileRegistry()

        config_dict = {
            "broker_name": "Test Broker",
            "asset_classes": {
                "equities": {
                    "network_latency_ms": [10.0, 30.0],
                    "broker_processing_ms": [2.0, 8.0],
                    "exchange_matching_ms": [0.5, 3.0],
                    "distribution": "normal",
                    "location": "US_EAST",
                },
                "crypto": {
                    "network_latency_ms": [20.0, 50.0],
                    "broker_processing_ms": [1.0, 5.0],
                    "exchange_matching_ms": [0.1, 2.0],
                    "distribution": "uniform",
                    "location": "ASIA",
                },
            },
        }

        registry.load_from_dict(config_dict)

        equities_profile = registry.get_profile("Test Broker", "equities")
        assert equities_profile.distribution == "normal"
        assert equities_profile.location == "US_EAST"

        crypto_profile = registry.get_profile("Test Broker", "crypto")
        assert crypto_profile.distribution == "uniform"
        assert crypto_profile.location == "ASIA"

    def test_load_from_yaml(self) -> None:
        """Load broker profile from YAML file."""
        registry = LatencyProfileRegistry()

        config_dict = {
            "broker_name": "Interactive Brokers",
            "asset_classes": {
                "equities": {
                    "network_latency_ms": [10.0, 30.0],
                    "broker_processing_ms": [2.0, 8.0],
                    "exchange_matching_ms": [0.5, 3.0],
                    "distribution": "normal",
                }
            },
        }

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            yaml_path = f.name

        try:
            registry.load_from_yaml(yaml_path)
            profile = registry.get_profile("Interactive Brokers", "equities")
            assert profile.broker_name == "Interactive Brokers"
            assert profile.distribution == "normal"
        finally:
            Path(yaml_path).unlink()

    def test_load_from_json(self) -> None:
        """Load broker profile from JSON file."""
        registry = LatencyProfileRegistry()

        config_dict = {
            "broker_name": "Binance",
            "asset_classes": {
                "crypto": {
                    "network_latency_ms": [20.0, 50.0],
                    "broker_processing_ms": [1.0, 5.0],
                    "exchange_matching_ms": [0.1, 2.0],
                    "distribution": "uniform",
                }
            },
        }

        with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_dict, f)
            json_path = f.name

        try:
            registry.load_from_json(json_path)
            profile = registry.get_profile("Binance", "crypto")
            assert profile.broker_name == "Binance"
            assert profile.distribution == "uniform"
        finally:
            Path(json_path).unlink()


# ============================================================================
# Property-Based Tests
# ============================================================================


@given(
    network_ms=st.decimals(min_value=Decimal("0"), max_value=Decimal("100"), places=2),
    broker_ms=st.decimals(min_value=Decimal("0"), max_value=Decimal("50"), places=2),
    exchange_ms=st.decimals(min_value=Decimal("0"), max_value=Decimal("20"), places=2),
)
def test_total_latency_equals_sum_of_components(
    network_ms: Decimal, broker_ms: Decimal, exchange_ms: Decimal
) -> None:
    """Total latency always equals sum of component latencies."""
    model = FixedLatencyModel(network_ms=network_ms, broker_ms=broker_ms, exchange_ms=exchange_ms)

    latency = model.calculate_latency(
        order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
    )

    assert latency.total_ms == network_ms + broker_ms + exchange_ms


@given(
    network_range=st.tuples(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("50"), places=2),
        st.decimals(min_value=Decimal("50"), max_value=Decimal("100"), places=2),
    ),
    broker_range=st.tuples(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("25"), places=2),
        st.decimals(min_value=Decimal("25"), max_value=Decimal("50"), places=2),
    ),
    exchange_range=st.tuples(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("10"), places=2),
        st.decimals(min_value=Decimal("10"), max_value=Decimal("20"), places=2),
    ),
)
def test_latency_never_negative(
    network_range: tuple, broker_range: tuple, exchange_range: tuple
) -> None:
    """Latency components are never negative."""
    model = RandomLatencyModel(
        network_range_ms=network_range,
        broker_range_ms=broker_range,
        exchange_range_ms=exchange_range,
        distribution="uniform",
    )

    for _ in range(20):  # Test multiple samples
        latency = model.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )

        assert latency.network_ms >= Decimal("0")
        assert latency.broker_processing_ms >= Decimal("0")
        assert latency.exchange_matching_ms >= Decimal("0")
        assert latency.total_ms >= Decimal("0")


@given(
    network_range=st.tuples(
        st.decimals(min_value=Decimal("0"), max_value=Decimal("50"), places=2),
        st.decimals(min_value=Decimal("50"), max_value=Decimal("100"), places=2),
    ),
)
def test_random_latency_respects_ranges(network_range: tuple) -> None:
    """Random latency always stays within configured ranges."""
    model = RandomLatencyModel(
        network_range_ms=network_range,
        broker_range_ms=(Decimal("1"), Decimal("10")),
        exchange_range_ms=(Decimal("0.1"), Decimal("5")),
        distribution="uniform",
    )

    for _ in range(50):
        latency = model.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )

        assert network_range[0] <= latency.network_ms <= network_range[1]
        assert Decimal("1") <= latency.broker_processing_ms <= Decimal("10")
        assert Decimal("0.1") <= latency.exchange_matching_ms <= Decimal("5")


@given(
    base_latency=st.decimals(min_value=Decimal("1"), max_value=Decimal("50"), places=2),
    jitter_range=st.tuples(
        st.decimals(min_value=Decimal("-10"), max_value=Decimal("0"), places=2),
        st.decimals(min_value=Decimal("0"), max_value=Decimal("10"), places=2),
    ),
)
def test_network_latency_with_jitter_property(base_latency: Decimal, jitter_range: tuple) -> None:
    """Network latency with jitter produces values in expected range."""
    model = NetworkLatency(
        base_latency_ms=base_latency,
        jitter_range_ms=jitter_range,
        location="US_EAST",
    )

    for _ in range(20):
        latency = model.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )

        # Result should be base + jitter, but never negative
        expected_min = max(Decimal("0"), base_latency + jitter_range[0])
        expected_max = base_latency + jitter_range[1]

        assert expected_min <= latency.network_ms <= expected_max
        assert latency.total_ms == latency.network_ms  # Only network component


# ============================================================================
# Performance Tests
# ============================================================================


def test_latency_calculation_performance() -> None:
    """Test latency calculation completes quickly (manual timing test)."""
    import time

    model = CompositeLatencyModel(
        network_model=NetworkLatency(
            base_latency_ms=Decimal("20.0"),
            jitter_range_ms=(Decimal("-5.0"), Decimal("5.0")),
        ),
        broker_model=BrokerProcessingLatency(base_processing_ms=Decimal("3.0")),
        exchange_model=ExchangeMatchingLatency(
            base_matching_ms=Decimal("1.0"), exchange_type="crypto"
        ),
    )

    # Measure time for 1000 calculations
    start = time.perf_counter()
    for _ in range(1000):
        model.calculate_latency(
            order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
        )
    elapsed = time.perf_counter() - start

    # Should complete 1000 calculations in under 100ms (very generous)
    assert elapsed < 0.1, f"Latency calculations too slow: {elapsed:.4f}s for 1000 calls"
