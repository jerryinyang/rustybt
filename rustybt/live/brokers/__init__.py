"""Broker adapters for live trading."""

from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.brokers.ib_adapter import IBBrokerAdapter
from rustybt.live.brokers.paper_broker import PaperBroker

__all__ = [
    "BrokerAdapter",
    "IBBrokerAdapter",
    "PaperBroker",
]

# Optional exchange adapters (require additional dependencies)
try:
    from rustybt.live.brokers.binance_adapter import BinanceBrokerAdapter

    __all__.append("BinanceBrokerAdapter")
except ImportError:
    pass

try:
    from rustybt.live.brokers.bybit_adapter import BybitBrokerAdapter

    __all__.append("BybitBrokerAdapter")
except ImportError:
    pass

try:
    from rustybt.live.brokers.ccxt_adapter import CCXTBrokerAdapter

    __all__.append("CCXTBrokerAdapter")
except ImportError:
    pass

try:
    from rustybt.live.brokers.hyperliquid_adapter import HyperliquidBrokerAdapter

    __all__.append("HyperliquidBrokerAdapter")
except ImportError:
    pass
