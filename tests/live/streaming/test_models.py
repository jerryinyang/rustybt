"""Tests for streaming models."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.live.streaming.models import StreamConfig, TickData, TickSide


class TestTickData:
    """Tests for TickData model."""

    def test_tick_data_creation(self) -> None:
        """Test TickData creation with valid data."""
        tick = TickData(
            symbol="BTCUSDT",
            timestamp=datetime(2025, 10, 3, 12, 0, 0),
            price=Decimal("50000.00"),
            volume=Decimal("1.5"),
            side=TickSide.BUY,
        )

        assert tick.symbol == "BTCUSDT"
        assert tick.timestamp == datetime(2025, 10, 3, 12, 0, 0)
        assert tick.price == Decimal("50000.00")
        assert tick.volume == Decimal("1.5")
        assert tick.side == TickSide.BUY

    def test_tick_data_default_side(self) -> None:
        """Test TickData with default side."""
        tick = TickData(
            symbol="ETHUSDT",
            timestamp=datetime(2025, 10, 3, 12, 0, 0),
            price=Decimal("3000.00"),
            volume=Decimal("2.0"),
        )

        assert tick.side == TickSide.UNKNOWN

    def test_tick_data_invalid_price(self) -> None:
        """Test TickData with invalid price (zero or negative)."""
        with pytest.raises(ValueError, match="Price must be positive"):
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 0),
                price=Decimal("0"),
                volume=Decimal("1.0"),
            )

        with pytest.raises(ValueError, match="Price must be positive"):
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 0),
                price=Decimal("-100.00"),
                volume=Decimal("1.0"),
            )

    def test_tick_data_invalid_volume(self) -> None:
        """Test TickData with negative volume."""
        with pytest.raises(ValueError, match="Volume must be non-negative"):
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 0),
                price=Decimal("50000.00"),
                volume=Decimal("-1.0"),
            )

    def test_tick_data_immutable(self) -> None:
        """Test TickData is immutable."""
        tick = TickData(
            symbol="BTCUSDT",
            timestamp=datetime(2025, 10, 3, 12, 0, 0),
            price=Decimal("50000.00"),
            volume=Decimal("1.0"),
        )

        with pytest.raises(AttributeError):
            tick.price = Decimal("60000.00")  # type: ignore


class TestStreamConfig:
    """Tests for StreamConfig model."""

    def test_stream_config_defaults(self) -> None:
        """Test StreamConfig with default values."""
        config = StreamConfig()

        assert config.bar_resolution == 60
        assert config.heartbeat_interval == 30
        assert config.heartbeat_timeout == 60
        assert config.reconnect_attempts is None
        assert config.reconnect_delay == 1
        assert config.reconnect_max_delay == 16
        assert config.circuit_breaker_threshold == 10

    def test_stream_config_custom_values(self) -> None:
        """Test StreamConfig with custom values."""
        config = StreamConfig(
            bar_resolution=300,
            heartbeat_interval=60,
            heartbeat_timeout=120,
            reconnect_attempts=5,
            reconnect_delay=2,
            reconnect_max_delay=32,
            circuit_breaker_threshold=20,
        )

        assert config.bar_resolution == 300
        assert config.heartbeat_interval == 60
        assert config.heartbeat_timeout == 120
        assert config.reconnect_attempts == 5
        assert config.reconnect_delay == 2
        assert config.reconnect_max_delay == 32
        assert config.circuit_breaker_threshold == 20

    def test_stream_config_invalid_bar_resolution(self) -> None:
        """Test StreamConfig with invalid bar_resolution."""
        with pytest.raises(ValueError, match="bar_resolution must be positive"):
            StreamConfig(bar_resolution=0)

        with pytest.raises(ValueError, match="bar_resolution must be positive"):
            StreamConfig(bar_resolution=-60)

    def test_stream_config_invalid_heartbeat_interval(self) -> None:
        """Test StreamConfig with invalid heartbeat_interval."""
        with pytest.raises(ValueError, match="heartbeat_interval must be positive"):
            StreamConfig(heartbeat_interval=0)

    def test_stream_config_invalid_heartbeat_timeout(self) -> None:
        """Test StreamConfig with invalid heartbeat_timeout."""
        with pytest.raises(ValueError, match="heartbeat_timeout must be positive"):
            StreamConfig(heartbeat_timeout=-10)

    def test_stream_config_invalid_reconnect_delay(self) -> None:
        """Test StreamConfig with invalid reconnect_delay."""
        with pytest.raises(ValueError, match="reconnect_delay must be positive"):
            StreamConfig(reconnect_delay=0)

    def test_stream_config_invalid_reconnect_max_delay(self) -> None:
        """Test StreamConfig with reconnect_max_delay < reconnect_delay."""
        with pytest.raises(ValueError, match="reconnect_max_delay .* must be >="):
            StreamConfig(reconnect_delay=10, reconnect_max_delay=5)

    def test_stream_config_invalid_circuit_breaker_threshold(self) -> None:
        """Test StreamConfig with invalid circuit_breaker_threshold."""
        with pytest.raises(ValueError, match="circuit_breaker_threshold must be positive"):
            StreamConfig(circuit_breaker_threshold=0)

    def test_stream_config_immutable(self) -> None:
        """Test StreamConfig is immutable."""
        config = StreamConfig()

        with pytest.raises(AttributeError):
            config.bar_resolution = 300  # type: ignore
