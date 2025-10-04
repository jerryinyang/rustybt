"""WebSocket streaming adapters for real-time market data.

This module provides base classes and concrete implementations for
WebSocket-based real-time data streaming from various exchanges.
"""

from rustybt.live.streaming.bar_buffer import BarBuffer, OHLCVBar
from rustybt.live.streaming.base import BaseWebSocketAdapter, ConnectionState
from rustybt.live.streaming.binance_stream import BinanceWebSocketAdapter
from rustybt.live.streaming.bybit_stream import BybitWebSocketAdapter
from rustybt.live.streaming.ccxt_stream import CCXTWebSocketAdapter
from rustybt.live.streaming.hyperliquid_stream import HyperliquidWebSocketAdapter
from rustybt.live.streaming.models import StreamConfig, TickData, TickSide

__all__ = [
    "BarBuffer",
    "BaseWebSocketAdapter",
    "BinanceWebSocketAdapter",
    "BybitWebSocketAdapter",
    "CCXTWebSocketAdapter",
    "ConnectionState",
    "HyperliquidWebSocketAdapter",
    "OHLCVBar",
    "StreamConfig",
    "TickData",
    "TickSide",
]
