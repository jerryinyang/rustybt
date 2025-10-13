"""
Latency Simulation Tutorial

This tutorial demonstrates how to use RustyBT's latency simulation models
to create realistic backtests that account for order execution delays.

Story 4.1: Implement Latency Simulation
"""

from decimal import Decimal

import pandas as pd

from rustybt.finance.execution import (
    BrokerProcessingLatency,
    CompositeLatencyModel,
    ExchangeMatchingLatency,
    FixedLatencyModel,
    HistoricalLatencyModel,
    LatencyComponents,
    LatencyProfileConfig,
    LatencyProfileRegistry,
    NetworkLatency,
    RandomLatencyModel,
)


def example_1_fixed_latency():
    """Example 1: Simple fixed latency model for deterministic testing."""
    print("=== Example 1: Fixed Latency Model ===\n")

    # Create a fixed latency model with constant delays
    model = FixedLatencyModel(
        network_ms=Decimal("10.0"),  # 10ms network latency
        broker_ms=Decimal("5.0"),  # 5ms broker processing
        exchange_ms=Decimal("2.0"),  # 2ms exchange matching
    )

    # Calculate latency for an order
    latency = model.calculate_latency(
        order=None, current_time=pd.Timestamp("2024-01-01 10:00:00"), broker_name="test"
    )

    print(f"Network latency: {latency.network_ms}ms")
    print(f"Broker processing: {latency.broker_processing_ms}ms")
    print(f"Exchange matching: {latency.exchange_matching_ms}ms")
    print(f"Total latency: {latency.total_ms}ms")
    print()


def example_2_random_latency():
    """Example 2: Random latency with uniform distribution."""
    print("=== Example 2: Random Latency Model (Uniform) ===\n")

    # Create random latency model with uniform distribution
    model = RandomLatencyModel(
        network_range_ms=(Decimal("5.0"), Decimal("15.0")),
        broker_range_ms=(Decimal("1.0"), Decimal("10.0")),
        exchange_range_ms=(Decimal("0.1"), Decimal("5.0")),
        distribution="uniform",
    )

    # Sample multiple latencies
    print("Sampling 5 latencies:")
    for i in range(5):
        latency = model.calculate_latency(
            order=None,
            current_time=pd.Timestamp("2024-01-01 10:00:00"),
            broker_name="test",
        )
        print(f"  Sample {i + 1}: Total = {latency.total_ms}ms")
    print()


def example_3_normal_distribution():
    """Example 3: Random latency with normal distribution."""
    print("=== Example 3: Random Latency Model (Normal) ===\n")

    # Create random latency model with normal distribution
    model = RandomLatencyModel(
        network_range_ms=(Decimal("10.0"), Decimal("30.0")),
        broker_range_ms=(Decimal("2.0"), Decimal("8.0")),
        exchange_range_ms=(Decimal("0.5"), Decimal("3.0")),
        distribution="normal",
    )

    # Sample multiple latencies
    latencies = []
    for _ in range(100):
        latency = model.calculate_latency(
            order=None,
            current_time=pd.Timestamp("2024-01-01 10:00:00"),
            broker_name="test",
        )
        latencies.append(float(latency.total_ms))

    print(f"Average latency over 100 samples: {sum(latencies) / len(latencies):.2f}ms")
    print(f"Min latency: {min(latencies):.2f}ms")
    print(f"Max latency: {max(latencies):.2f}ms")
    print()


def example_4_composite_latency():
    """Example 4: Composite latency model with specialized components."""
    print("=== Example 4: Composite Latency Model ===\n")

    # Create specialized latency models for each component
    network_model = NetworkLatency(
        base_latency_ms=Decimal("20.0"),
        jitter_range_ms=(Decimal("-5.0"), Decimal("5.0")),
        location="US_EAST",
    )

    broker_model = BrokerProcessingLatency(
        base_processing_ms=Decimal("3.0"),
        complexity_factor=Decimal("0.5"),
        processing_range_ms=(Decimal("2.0"), Decimal("8.0")),
    )

    exchange_model = ExchangeMatchingLatency(
        base_matching_ms=Decimal("1.0"),
        queue_factor=Decimal("0.1"),
        matching_range_ms=(Decimal("0.1"), Decimal("5.0")),
        exchange_type="crypto",
    )

    # Combine into composite model
    composite = CompositeLatencyModel(
        network_model=network_model,
        broker_model=broker_model,
        exchange_model=exchange_model,
    )

    # Calculate composite latency
    latency = composite.calculate_latency(
        order=None, current_time=pd.Timestamp("2024-01-01 10:00:00"), broker_name="test"
    )

    print(f"Network (with jitter): {latency.network_ms}ms")
    print(f"Broker (complexity-adjusted): {latency.broker_processing_ms}ms")
    print(f"Exchange (queue-adjusted): {latency.exchange_matching_ms}ms")
    print(f"Total composite latency: {latency.total_ms}ms")
    print()


def example_5_historical_latency():
    """Example 5: Historical latency replay from recorded data."""
    print("=== Example 5: Historical Latency Model ===\n")

    # Create historical latency data (would typically load from file)
    latency_data = {
        pd.Timestamp("2024-01-01 09:30:00"): LatencyComponents(
            network_ms=Decimal("12.5"),
            broker_processing_ms=Decimal("4.2"),
            exchange_matching_ms=Decimal("1.8"),
            total_ms=Decimal("18.5"),
        ),
        pd.Timestamp("2024-01-01 09:31:00"): LatencyComponents(
            network_ms=Decimal("15.3"),
            broker_processing_ms=Decimal("5.1"),
            exchange_matching_ms=Decimal("2.3"),
            total_ms=Decimal("22.7"),
        ),
        pd.Timestamp("2024-01-01 09:32:00"): LatencyComponents(
            network_ms=Decimal("11.8"),
            broker_processing_ms=Decimal("3.9"),
            exchange_matching_ms=Decimal("1.5"),
            total_ms=Decimal("17.2"),
        ),
    }

    model = HistoricalLatencyModel(latency_data=latency_data)

    # Query exact timestamp
    latency = model.calculate_latency(
        order=None,
        current_time=pd.Timestamp("2024-01-01 09:30:00"),
        broker_name="test",
    )
    print(f"Exact match (09:30:00): {latency.total_ms}ms")

    # Query between timestamps (uses nearest)
    latency = model.calculate_latency(
        order=None,
        current_time=pd.Timestamp("2024-01-01 09:30:30"),
        broker_name="test",
    )
    print(f"Nearest match (09:30:30): {latency.total_ms}ms")
    print()


def example_6_latency_profiles():
    """Example 6: Using broker-specific latency profiles."""
    print("=== Example 6: Broker Latency Profiles ===\n")

    # Create latency profile for Interactive Brokers
    ib_equities_profile = LatencyProfileConfig(
        broker_name="Interactive Brokers",
        asset_class="equities",
        network_latency_ms=(10.0, 30.0),
        broker_processing_ms=(2.0, 8.0),
        exchange_matching_ms=(0.5, 3.0),
        distribution="normal",
        location="US_EAST",
    )

    # Convert to latency model
    ib_model = ib_equities_profile.to_latency_model()

    print("Interactive Brokers - Equities Profile:")
    latency = ib_model.calculate_latency(
        order=None, current_time=pd.Timestamp("2024-01-01 10:00:00"), broker_name="IB"
    )
    print(f"  Total latency: {latency.total_ms}ms")

    # Create Binance crypto profile
    binance_crypto_profile = LatencyProfileConfig(
        broker_name="Binance",
        asset_class="crypto",
        network_latency_ms=(20.0, 50.0),
        broker_processing_ms=(1.0, 5.0),
        exchange_matching_ms=(0.1, 2.0),
        distribution="uniform",
        location="ASIA",
    )

    binance_model = binance_crypto_profile.to_latency_model()

    print("\nBinance - Crypto Profile:")
    latency = binance_model.calculate_latency(
        order=None,
        current_time=pd.Timestamp("2024-01-01 10:00:00"),
        broker_name="Binance",
    )
    print(f"  Total latency: {latency.total_ms}ms")
    print()


def example_7_profile_registry():
    """Example 7: Using latency profile registry."""
    print("=== Example 7: Latency Profile Registry ===\n")

    # Create registry
    registry = LatencyProfileRegistry()

    # Load profiles from configuration dict
    ib_config = {
        "broker_name": "Interactive Brokers",
        "asset_classes": {
            "equities": {
                "network_latency_ms": [10.0, 30.0],
                "broker_processing_ms": [2.0, 8.0],
                "exchange_matching_ms": [0.5, 3.0],
                "distribution": "normal",
                "location": "US_EAST",
            },
            "futures": {
                "network_latency_ms": [10.0, 30.0],
                "broker_processing_ms": [1.0, 5.0],
                "exchange_matching_ms": [0.1, 2.0],
                "distribution": "normal",
                "location": "US_EAST",
            },
        },
    }

    registry.load_from_dict(ib_config)

    # Retrieve and use profiles
    equities_profile = registry.get_profile("Interactive Brokers", "equities")
    print(f"Retrieved profile: {equities_profile.broker_name} - {equities_profile.asset_class}")
    print(f"  Network range: {equities_profile.network_latency_ms}")
    print(f"  Distribution: {equities_profile.distribution}")

    futures_profile = registry.get_profile("Interactive Brokers", "futures")
    print(f"\nRetrieved profile: {futures_profile.broker_name} - {futures_profile.asset_class}")
    print(f"  Network range: {futures_profile.network_latency_ms}")
    print()


def example_8_exchange_types():
    """Example 8: Exchange type differences (traditional vs crypto vs DEX)."""
    print("=== Example 8: Exchange Type Comparison ===\n")

    # Traditional exchange (NYSE/NASDAQ)
    traditional = ExchangeMatchingLatency(
        base_matching_ms=Decimal("2.0"),
        queue_factor=Decimal("0"),
        matching_range_ms=(Decimal("0.5"), Decimal("5.0")),
        exchange_type="traditional",
    )

    # Crypto exchange (Binance/Bybit)
    crypto = ExchangeMatchingLatency(
        base_matching_ms=Decimal("2.0"),
        queue_factor=Decimal("0"),
        matching_range_ms=(Decimal("0.1"), Decimal("5.0")),
        exchange_type="crypto",
    )

    # Decentralized exchange (Hyperliquid)
    dex = ExchangeMatchingLatency(
        base_matching_ms=Decimal("2.0"),
        queue_factor=Decimal("0"),
        matching_range_ms=(Decimal("1.0"), Decimal("10.0")),
        exchange_type="dex",
    )

    print("Exchange Type Latency Comparison (same base latency):")

    trad_latency = traditional.calculate_latency(
        order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
    )
    print(f"  Traditional (1.0x): {trad_latency.exchange_matching_ms}ms")

    crypto_latency = crypto.calculate_latency(
        order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
    )
    print(f"  Crypto (0.5x):      {crypto_latency.exchange_matching_ms}ms")

    dex_latency = dex.calculate_latency(
        order=None, current_time=pd.Timestamp("2024-01-01"), broker_name="test"
    )
    print(f"  DEX (2.0x):         {dex_latency.exchange_matching_ms}ms")
    print()


def example_9_load_yaml_profiles():
    """Example 9: Loading profiles from YAML files."""
    print("=== Example 9: Loading Profiles from YAML ===\n")

    registry = LatencyProfileRegistry()

    # Load Interactive Brokers profile
    try:
        registry.load_from_yaml("config/broker_latency_profiles/interactive_brokers.yaml")
        print("✓ Loaded Interactive Brokers profile")

        ib_equities = registry.get_profile("Interactive Brokers", "equities")
        print(f"  Equities: {ib_equities.network_latency_ms} network latency")

        ib_futures = registry.get_profile("Interactive Brokers", "futures")
        print(f"  Futures: {ib_futures.network_latency_ms} network latency")
    except Exception as e:
        print(f"✗ Failed to load IB profile: {e}")

    # Load Binance profile
    try:
        registry.load_from_yaml("config/broker_latency_profiles/binance.yaml")
        print("\n✓ Loaded Binance profile")

        binance_crypto = registry.get_profile("Binance", "crypto")
        print(f"  Crypto: {binance_crypto.network_latency_ms} network latency")
    except Exception as e:
        print(f"✗ Failed to load Binance profile: {e}")

    print()


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("RustyBT Latency Simulation Tutorial")
    print("Story 4.1: Implement Latency Simulation")
    print("=" * 70 + "\n")

    example_1_fixed_latency()
    example_2_random_latency()
    example_3_normal_distribution()
    example_4_composite_latency()
    example_5_historical_latency()
    example_6_latency_profiles()
    example_7_profile_registry()
    example_8_exchange_types()
    example_9_load_yaml_profiles()

    print("=" * 70)
    print("Tutorial Complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
