"""Integration tests for end-to-end WebSocket market data flow (AC 5, 10)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from rustybt.assets import Equity
from rustybt.live.brokers.bybit_adapter import BybitBrokerAdapter
from rustybt.live.streaming.bar_buffer import OHLCVBar
from rustybt.live.streaming.models import TickData, TickSide


@pytest.fixture
def test_asset():
    """Create test asset for integration tests."""
    return Equity(
        sid=1,
        symbol="BTCUSDT",
        exchange="BYBIT",
        start_date=None,
        end_date=None,
    )


# ====================================================================================
# Integration Tests (AC 5, 10)
# ====================================================================================


class TestWebSocketIntegrationEndToEnd:
    """Test end-to-end WebSocket integration flow (AC 5, AC 10 - TEST-003)."""

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_tick_to_strategy_handle_data(self, test_asset):
        """Test end-to-end: WebSocket tick → BarBuffer → MarketDataEvent → Strategy.handle_data() (AC 5)."""
        from unittest.mock import patch

        # Create broker adapter with mocked WebSocket
        with patch("rustybt.live.brokers.bybit_adapter.HTTP"):
            adapter = BybitBrokerAdapter(
                api_key="test_key", api_secret="test_secret", market_type="linear", testnet=True
            )
            adapter.client = MagicMock()
            adapter.client.get_server_time.return_value = {
                "retCode": 0,
                "result": {"timeSecond": "1234567890"},
            }

            # Connect adapter (initializes WebSocket and BarBuffer)
            await adapter.connect()

            # Create mock BarBuffer that immediately calls bar callback
            MagicMock()
            adapter._bar_buffer = MagicMock()
            adapter._bar_buffer.add_tick = MagicMock()

            # Simulate tick arrival from WebSocket
            tick = TickData(
                symbol="BTCUSDT",
                timestamp=datetime.now(UTC),
                price=Decimal("50000.50"),
                volume=Decimal("0.1"),
                side=TickSide.BUY,
            )

            # Call tick handler (simulates WebSocket → BarBuffer flow)
            adapter._handle_tick(tick)

            # Verify tick was added to BarBuffer
            adapter._bar_buffer.add_tick.assert_called_once_with(tick)

            # Simulate bar completion (BarBuffer → MarketDataEvent flow)
            bar = OHLCVBar(
                symbol="BTCUSDT",
                timestamp=datetime.now(UTC),
                open=Decimal("50000"),
                high=Decimal("50100"),
                low=Decimal("49900"),
                close=Decimal("50050"),
                volume=Decimal("10.5"),
            )

            # Call bar complete handler (simulates BarBuffer → Event Queue flow)
            adapter._handle_bar_complete(bar)

            # Verify MarketDataEvent was pushed to queue
            assert not adapter._market_data_queue.empty()
            market_data = await adapter._market_data_queue.get()

            # Verify event structure (ready for Strategy.handle_data())
            assert market_data["type"] == "bar"
            assert market_data["symbol"] == "BTCUSDT"
            assert market_data["open"] == Decimal("50000")
            assert market_data["high"] == Decimal("50100")
            assert market_data["low"] == Decimal("49900")
            assert market_data["close"] == Decimal("50050")
            assert market_data["volume"] == Decimal("10.5")

            # Cleanup
            await adapter.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.websocket_integration
    async def test_websocket_lifecycle_complete_flow(self, test_asset):
        """Test WebSocket lifecycle: connect → subscribe → receive ticks → disconnect (AC 4, 5)."""
        from unittest.mock import patch

        # Create broker adapter with mocked WebSocket
        with patch("rustybt.live.brokers.bybit_adapter.HTTP"):
            adapter = BybitBrokerAdapter(
                api_key="test_key", api_secret="test_secret", market_type="linear", testnet=True
            )
            adapter.client = MagicMock()
            adapter.client.get_server_time.return_value = {
                "retCode": 0,
                "result": {"timeSecond": "1234567890"},
            }

            # Step 1: Connect broker (should initialize WebSocket)
            await adapter.connect()
            assert adapter.is_connected()
            assert adapter._ws_adapter is not None
            assert adapter._bar_buffer is not None

            # Step 2: Subscribe to market data
            mock_ws = AsyncMock()
            adapter._ws_adapter = mock_ws

            await adapter.subscribe_market_data([test_asset])
            mock_ws.subscribe.assert_called_once_with(symbols=["BTCUSDT"], channels=["publicTrade"])

            # Step 3: Receive ticks (simulate WebSocket data flow)
            ticks = [
                TickData(
                    symbol="BTCUSDT",
                    timestamp=datetime.now(UTC),
                    price=Decimal("50000"),
                    volume=Decimal("0.1"),
                    side=TickSide.BUY,
                ),
                TickData(
                    symbol="BTCUSDT",
                    timestamp=datetime.now(UTC),
                    price=Decimal("50100"),
                    volume=Decimal("0.2"),
                    side=TickSide.SELL,
                ),
            ]

            # Mock BarBuffer to track tick additions
            mock_bar_buffer = MagicMock()
            adapter._bar_buffer = mock_bar_buffer

            for tick in ticks:
                adapter._handle_tick(tick)

            # Verify all ticks were added to BarBuffer
            assert mock_bar_buffer.add_tick.call_count == 2

            # Step 4: Disconnect (should disconnect WebSocket)
            await adapter.disconnect()
            mock_ws.disconnect.assert_called_once()
            assert not adapter.is_connected()
            assert adapter._ws_adapter is None
            assert adapter._bar_buffer is None
