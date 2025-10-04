"""Tests for bar buffering system."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.live.streaming.bar_buffer import BarBuffer, OHLCVBar
from rustybt.live.streaming.models import TickData


class TestOHLCVBar:
    """Tests for OHLCVBar model."""

    def test_ohlcv_bar_creation(self) -> None:
        """Test OHLCVBar creation with valid data."""
        bar = OHLCVBar(
            symbol="BTCUSDT",
            timestamp=datetime(2025, 10, 3, 12, 0, 0),
            open=Decimal("49000.00"),
            high=Decimal("50000.00"),
            low=Decimal("48500.00"),
            close=Decimal("49500.00"),
            volume=Decimal("100.0"),
        )

        assert bar.symbol == "BTCUSDT"
        assert bar.timestamp == datetime(2025, 10, 3, 12, 0, 0)
        assert bar.open == Decimal("49000.00")
        assert bar.high == Decimal("50000.00")
        assert bar.low == Decimal("48500.00")
        assert bar.close == Decimal("49500.00")
        assert bar.volume == Decimal("100.0")

    def test_ohlcv_bar_invalid_high_low(self) -> None:
        """Test OHLCVBar with high < low."""
        with pytest.raises(ValueError, match="High .* must be >= low"):
            OHLCVBar(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 0),
                open=Decimal("49000.00"),
                high=Decimal("48000.00"),  # High < low
                low=Decimal("48500.00"),
                close=Decimal("49500.00"),
                volume=Decimal("100.0"),
            )

    def test_ohlcv_bar_invalid_high_open(self) -> None:
        """Test OHLCVBar with high < open."""
        with pytest.raises(ValueError, match="High .* must be >= open"):
            OHLCVBar(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 0),
                open=Decimal("50000.00"),
                high=Decimal("49000.00"),  # High < open
                low=Decimal("48500.00"),
                close=Decimal("49500.00"),
                volume=Decimal("100.0"),
            )

    def test_ohlcv_bar_invalid_low_open(self) -> None:
        """Test OHLCVBar with low > open."""
        with pytest.raises(ValueError, match="Low .* must be <= open"):
            OHLCVBar(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 0),
                open=Decimal("48000.00"),
                high=Decimal("50000.00"),
                low=Decimal("48500.00"),  # Low > open
                close=Decimal("49500.00"),
                volume=Decimal("100.0"),
            )

    def test_ohlcv_bar_negative_volume(self) -> None:
        """Test OHLCVBar with negative volume."""
        with pytest.raises(ValueError, match="Volume must be non-negative"):
            OHLCVBar(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 0),
                open=Decimal("49000.00"),
                high=Decimal("50000.00"),
                low=Decimal("48500.00"),
                close=Decimal("49500.00"),
                volume=Decimal("-10.0"),
            )


class TestBarBuffer:
    """Tests for BarBuffer."""

    def test_bar_buffer_creation(self) -> None:
        """Test BarBuffer creation."""
        buffer = BarBuffer(bar_resolution=60)

        assert buffer.bar_resolution == 60
        assert buffer.on_bar_complete is None

    def test_bar_buffer_invalid_resolution(self) -> None:
        """Test BarBuffer with invalid resolution."""
        with pytest.raises(ValueError, match="bar_resolution must be positive"):
            BarBuffer(bar_resolution=0)

        with pytest.raises(ValueError, match="bar_resolution must be positive"):
            BarBuffer(bar_resolution=-60)

    def test_add_tick_first_tick(self) -> None:
        """Test adding first tick to buffer."""
        buffer = BarBuffer(bar_resolution=60)

        tick = TickData(
            symbol="BTCUSDT",
            timestamp=datetime(2025, 10, 3, 12, 0, 15),
            price=Decimal("50000.00"),
            volume=Decimal("1.0"),
        )

        result = buffer.add_tick(tick)

        # Should not emit bar (incomplete)
        assert result is None

    def test_add_tick_multiple_ticks_same_bar(self) -> None:
        """Test adding multiple ticks to same bar."""
        buffer = BarBuffer(bar_resolution=60)

        ticks = [
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 10),
                price=Decimal("50000.00"),
                volume=Decimal("1.0"),
            ),
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 20),
                price=Decimal("51000.00"),
                volume=Decimal("2.0"),
            ),
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 30),
                price=Decimal("49500.00"),
                volume=Decimal("1.5"),
            ),
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 50),
                price=Decimal("50500.00"),
                volume=Decimal("0.5"),
            ),
        ]

        for tick in ticks:
            result = buffer.add_tick(tick)
            assert result is None  # No bar emitted yet

    def test_add_tick_bar_boundary_crossed(self) -> None:
        """Test bar emission when boundary crossed."""
        completed_bars = []

        def on_bar_complete(bar: OHLCVBar) -> None:
            completed_bars.append(bar)

        buffer = BarBuffer(bar_resolution=60, on_bar_complete=on_bar_complete)

        # Add ticks in first bar
        buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 10),
                price=Decimal("50000.00"),
                volume=Decimal("1.0"),
            )
        )
        buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 30),
                price=Decimal("51000.00"),
                volume=Decimal("2.0"),
            )
        )

        # No bar emitted yet
        assert len(completed_bars) == 0

        # Add tick in next bar (crosses boundary)
        result = buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 1, 5),
                price=Decimal("50500.00"),
                volume=Decimal("1.5"),
            )
        )

        # Bar should be emitted
        assert result is not None
        assert len(completed_bars) == 1

        bar = completed_bars[0]
        assert bar.symbol == "BTCUSDT"
        assert bar.timestamp == datetime(2025, 10, 3, 12, 0, 0)  # Aligned to bar boundary
        assert bar.open == Decimal("50000.00")  # First tick
        assert bar.high == Decimal("51000.00")  # Max price
        assert bar.low == Decimal("50000.00")  # Min price
        assert bar.close == Decimal("51000.00")  # Last tick
        assert bar.volume == Decimal("3.0")  # Sum of volumes

    def test_bar_aggregation_ohlc(self) -> None:
        """Test OHLC aggregation is correct."""
        buffer = BarBuffer(bar_resolution=60)

        # Add ticks with varying prices
        ticks = [
            TickData(  # Open
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 5),
                price=Decimal("50000.00"),
                volume=Decimal("1.0"),
            ),
            TickData(  # High
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 15),
                price=Decimal("52000.00"),
                volume=Decimal("0.5"),
            ),
            TickData(  # Low
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 25),
                price=Decimal("49000.00"),
                volume=Decimal("2.0"),
            ),
            TickData(  # Close
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 55),
                price=Decimal("50500.00"),
                volume=Decimal("1.5"),
            ),
        ]

        for tick in ticks:
            buffer.add_tick(tick)

        # Cross boundary to emit bar
        result = buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 1, 0),
                price=Decimal("50000.00"),
                volume=Decimal("1.0"),
            )
        )

        assert result is not None
        assert result.open == Decimal("50000.00")
        assert result.high == Decimal("52000.00")
        assert result.low == Decimal("49000.00")
        assert result.close == Decimal("50500.00")
        assert result.volume == Decimal("5.0")

    def test_multiple_symbols(self) -> None:
        """Test buffering multiple symbols separately."""
        buffer = BarBuffer(bar_resolution=60)

        # Add ticks for different symbols
        buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 10),
                price=Decimal("50000.00"),
                volume=Decimal("1.0"),
            )
        )
        buffer.add_tick(
            TickData(
                symbol="ETHUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 20),
                price=Decimal("3000.00"),
                volume=Decimal("5.0"),
            )
        )

        # Cross boundary
        btc_bar = buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 1, 0),
                price=Decimal("51000.00"),
                volume=Decimal("2.0"),
            )
        )

        eth_bar = buffer.add_tick(
            TickData(
                symbol="ETHUSDT",
                timestamp=datetime(2025, 10, 3, 12, 1, 0),
                price=Decimal("3100.00"),
                volume=Decimal("3.0"),
            )
        )

        # Both bars emitted separately
        assert btc_bar is not None
        assert btc_bar.symbol == "BTCUSDT"
        assert btc_bar.open == Decimal("50000.00")

        assert eth_bar is not None
        assert eth_bar.symbol == "ETHUSDT"
        assert eth_bar.open == Decimal("3000.00")

    def test_flush_all(self) -> None:
        """Test flushing all incomplete bars."""
        buffer = BarBuffer(bar_resolution=60)

        # Add ticks for multiple symbols (incomplete bars)
        buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 10),
                price=Decimal("50000.00"),
                volume=Decimal("1.0"),
            )
        )
        buffer.add_tick(
            TickData(
                symbol="ETHUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 20),
                price=Decimal("3000.00"),
                volume=Decimal("5.0"),
            )
        )

        # Flush all
        bars = buffer.flush_all()

        assert len(bars) == 2
        assert "BTCUSDT" in bars
        assert "ETHUSDT" in bars
        assert bars["BTCUSDT"].symbol == "BTCUSDT"
        assert bars["ETHUSDT"].symbol == "ETHUSDT"

    def test_flush_symbol(self) -> None:
        """Test flushing specific symbol."""
        buffer = BarBuffer(bar_resolution=60)

        # Add ticks for multiple symbols
        buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 10),
                price=Decimal("50000.00"),
                volume=Decimal("1.0"),
            )
        )
        buffer.add_tick(
            TickData(
                symbol="ETHUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 20),
                price=Decimal("3000.00"),
                volume=Decimal("5.0"),
            )
        )

        # Flush only BTCUSDT
        btc_bar = buffer.flush_symbol("BTCUSDT")

        assert btc_bar is not None
        assert btc_bar.symbol == "BTCUSDT"

        # ETHUSDT still in buffer
        eth_bar = buffer.flush_symbol("ETHUSDT")
        assert eth_bar is not None
        assert eth_bar.symbol == "ETHUSDT"

    def test_alignment_to_bar_boundary(self) -> None:
        """Test tick timestamps are aligned to bar boundaries."""
        buffer = BarBuffer(bar_resolution=60)

        # Add tick at 12:00:37
        buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 0, 37),
                price=Decimal("50000.00"),
                volume=Decimal("1.0"),
            )
        )

        # Cross boundary
        result = buffer.add_tick(
            TickData(
                symbol="BTCUSDT",
                timestamp=datetime(2025, 10, 3, 12, 1, 12),
                price=Decimal("51000.00"),
                volume=Decimal("1.0"),
            )
        )

        # Bar timestamp should be aligned to 12:00:00
        assert result is not None
        assert result.timestamp == datetime(2025, 10, 3, 12, 0, 0)
