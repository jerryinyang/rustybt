"""Strategy executor for live trading.

This module wraps TradingAlgorithm and provides async triggers for live events,
ensuring the same strategy code works in both backtest and live modes.
"""

from decimal import Decimal
from typing import Any

import structlog

from rustybt.algorithm import TradingAlgorithm
from rustybt.live.events import (
    MarketDataEvent,
    OrderFillEvent,
    OrderRejectEvent,
    ScheduledTriggerEvent,
)

logger = structlog.get_logger()


class LiveContext:
    """Context object for live trading (mirrors backtest context API).

    This provides the same interface as backtest context:
    - context.portfolio
    - context.account
    - context.asset (user-defined)

    The portfolio and account objects must provide the same API as backtest mode.
    """

    def __init__(self, portfolio: Any, account: Any) -> None:
        """Initialize live context.

        Args:
            portfolio: Portfolio object (same API as backtest)
            account: Account object (same API as backtest)
        """
        self.portfolio = portfolio
        self.account = account


class StrategyExecutor:
    """Executes TradingAlgorithm in live mode with async triggers."""

    def __init__(
        self,
        strategy: TradingAlgorithm,
        data_portal: Any,  # PolarsDataPortal
        portfolio: Any,  # Portfolio object with same API as backtest
        account: Any,  # Account object with same API as backtest
    ) -> None:
        """Initialize strategy executor.

        Args:
            strategy: TradingAlgorithm instance (same class as backtest)
            data_portal: PolarsDataPortal for historical data access
            portfolio: Portfolio object providing same API as backtest
            account: Account object providing same API as backtest

        Note:
            This ensures strategy reusability - the same TradingAlgorithm
            subclass runs in both backtest and live modes without code changes.
        """
        self._strategy = strategy
        self._data_portal = data_portal
        self._context = LiveContext(portfolio=portfolio, account=account)
        self._initialized = False

    async def initialize(self) -> None:
        """Call strategy initialize method.

        This is called once at strategy startup, same as backtest mode.
        """
        if self._initialized:
            logger.warning("strategy_already_initialized")
            return

        try:
            # Call strategy's initialize method
            # Note: initialize expects (context) signature
            self._strategy.initialize(self._context)
            self._initialized = True
            logger.info("strategy_initialized", strategy=self._strategy.__class__.__name__)
        except Exception as e:
            logger.error(
                "strategy_initialization_failed",
                strategy=self._strategy.__class__.__name__,
                error=str(e),
                exc_info=True,
            )
            raise

    async def on_data(self, event: MarketDataEvent) -> None:
        """Handle market data event by calling strategy.handle_data.

        This provides the same API as backtest:
        - context.portfolio, context.account, user-defined context attributes
        - data.current(), data.history(), data.can_trade()

        Args:
            event: Market data event
        """
        if not self._initialized:
            logger.warning("strategy_not_initialized_skipping_data")
            return

        try:
            # Create BarData object that provides same API as backtest
            # data.current(asset, field) → Decimal
            # data.history(asset, field, bar_count, frequency) → Polars DataFrame
            # data.can_trade(asset) → bool
            bar_data = self._create_bar_data(event)

            # Call strategy's handle_data method
            # Note: handle_data expects (context, data) signature in backtest
            # But TradingAlgorithm.handle_data only takes (data)
            # We need to check the actual signature
            self._strategy.handle_data(bar_data)

            logger.debug(
                "strategy_handle_data_called",
                asset=event.asset_symbol,
                timestamp=str(event.bar_timestamp),
            )
        except Exception as e:
            logger.error(
                "strategy_handle_data_error",
                asset=event.asset_symbol,
                error=str(e),
                exc_info=True,
            )
            # Don't re-raise - log and continue processing

    async def on_order_fill(self, event: OrderFillEvent) -> None:
        """Handle order fill event (optional strategy callback).

        This is a live-only optional callback. If strategy implements
        on_order_fill method, it will be called. Otherwise, this is a no-op.

        Args:
            event: Order fill event
        """
        if not self._initialized:
            return

        # Check if strategy implements on_order_fill
        if not hasattr(self._strategy, "on_order_fill"):
            return

        try:
            # Call optional callback
            self._strategy.on_order_fill(
                self._context,
                order_id=event.order_id,
                fill_price=event.fill_price,
                fill_amount=event.filled_amount,
                commission=event.commission,
            )
            logger.debug("strategy_on_order_fill_called", order_id=event.order_id)
        except Exception as e:
            logger.error(
                "strategy_on_order_fill_error",
                order_id=event.order_id,
                error=str(e),
                exc_info=True,
            )

    async def on_order_reject(self, event: OrderRejectEvent) -> None:
        """Handle order reject event (optional strategy callback).

        Args:
            event: Order reject event
        """
        if not self._initialized:
            return

        # Check if strategy implements on_order_reject
        if not hasattr(self._strategy, "on_order_reject"):
            return

        try:
            self._strategy.on_order_reject(
                self._context, order_id=event.order_id, reason=event.reason
            )
            logger.debug("strategy_on_order_reject_called", order_id=event.order_id)
        except Exception as e:
            logger.error(
                "strategy_on_order_reject_error",
                order_id=event.order_id,
                error=str(e),
                exc_info=True,
            )

    async def on_scheduled_event(self, event: ScheduledTriggerEvent) -> None:
        """Handle scheduled callback trigger.

        Args:
            event: Scheduled trigger event
        """
        if not self._initialized:
            return

        callback_name = event.callback_name
        if not hasattr(self._strategy, callback_name):
            logger.warning("scheduled_callback_not_found", callback=callback_name)
            return

        try:
            callback = getattr(self._strategy, callback_name)
            callback(self._context, **event.callback_args)
            logger.debug("scheduled_callback_executed", callback=callback_name)
        except Exception as e:
            logger.error(
                "scheduled_callback_error",
                callback=callback_name,
                error=str(e),
                exc_info=True,
            )

    def _create_bar_data(self, event: MarketDataEvent) -> Any:
        """Create BarData object from market data event.

        This provides the same API as backtest mode:
        - data.current(asset, field) → returns current value
        - data.history(asset, field, bar_count, frequency) → returns Polars DataFrame
        - data.can_trade(asset) → returns bool

        Args:
            event: Market data event

        Returns:
            BarData object with backtest-compatible API
        """
        # TODO: This needs actual implementation with BarData from data.bar_reader
        # For now, returning a placeholder - will be implemented with actual BarData
        # that wraps PolarsDataPortal and provides current() / history() / can_trade()

        # Note: This is a simplified version - full implementation requires
        # integrating with PolarsDataPortal and BarData
        class SimplifiedBarData:
            """Simplified BarData for initial implementation."""

            def __init__(self, event: MarketDataEvent, data_portal: Any) -> None:
                self._event = event
                self._data_portal = data_portal

            def current(self, asset: Any, field: str) -> Decimal:
                """Get current value for field."""
                if field == "close":
                    return self._event.close
                elif field == "open":
                    return self._event.open
                elif field == "high":
                    return self._event.high
                elif field == "low":
                    return self._event.low
                elif field == "volume":
                    return self._event.volume
                else:
                    raise ValueError(f"Unsupported field: {field}")

            def history(self, asset: Any, field: str, bar_count: int, frequency: str) -> Any:
                """Get historical data window from data portal."""
                # This should use PolarsDataPortal to fetch historical data
                # returning a Polars DataFrame with Decimal columns
                return self._data_portal.get_history(asset, field, bar_count, frequency)

            def can_trade(self, asset: Any) -> bool:
                """Check if asset is tradable."""
                # Simplified: assume always tradable for now
                return True

        return SimplifiedBarData(event, self._data_portal)
