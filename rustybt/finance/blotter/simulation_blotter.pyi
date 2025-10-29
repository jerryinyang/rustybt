"""Type stubs for rustybt.finance.blotter.simulation_blotter - SimulationBlotter class.

Provides type hints for the simulation blotter used in backtesting.
Most users interact with blotter indirectly via TradingAlgorithm.order() methods.
"""

from typing import Any

from rustybt.assets import Asset

class SimulationBlotter:
    """Blotter for simulation/backtest mode.

    Handles order placement, tracking, and execution during backtests.
    Users typically don't interact with this directly - use context.order() instead.

    Attributes
    ----------
    open_orders : dict
        Dictionary of open orders by asset.
    orders : dict
        Dictionary of all orders by order ID.
    """

    open_orders: dict[Asset, list[Any]]
    orders: dict[str, Any]

    def __init__(
        self,
        equity_slippage: Any | None = None,
        future_slippage: Any | None = None,
        equity_commission: Any | None = None,
        future_commission: Any | None = None,
        cancel_policy: Any | None = None,
    ) -> None: ...
