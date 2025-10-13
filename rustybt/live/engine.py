"""Live trading engine with async event loop.

This module provides the main LiveTradingEngine that orchestrates live trading
with async event processing, order management, and strategy execution.
"""

import asyncio
import signal
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from rustybt._version import __version__
from rustybt.algorithm import TradingAlgorithm
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.data_feed import DataFeed
from rustybt.live.event_dispatcher import EventDispatcher
from rustybt.live.events import (
    Event,
    MarketDataEvent,
    OrderFillEvent,
    OrderRejectEvent,
    ScheduledTriggerEvent,
    SystemErrorEvent,
)
from rustybt.live.models import (
    DiscrepancySeverity,
    OrderSnapshot,
    ReconciliationStrategy,
    StateCheckpoint,
)
from rustybt.live.order_manager import OrderManager
from rustybt.live.reconciler import PositionReconciler, ReconciliationError
from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.engine import ShadowBacktestEngine
from rustybt.live.state_manager import StateManager
from rustybt.live.strategy_executor import StrategyExecutor

logger = structlog.get_logger()


class LiveTradingEngine:
    """Main live trading engine with async event loop.

    This engine orchestrates all live trading components:
    - Event queue and dispatcher
    - Order management
    - Data feed integration
    - Strategy execution

    The same TradingAlgorithm class that runs in backtest mode can run
    in live mode without code changes.
    """

    def __init__(
        self,
        strategy: TradingAlgorithm,
        broker_adapter: BrokerAdapter,
        data_portal: Any,
        portfolio: Any | None = None,
        account: Any | None = None,
        scheduler: Any | None = None,
        state_manager: StateManager | None = None,
        checkpoint_interval_seconds: int = 60,
        reconciliation_strategy: ReconciliationStrategy = ReconciliationStrategy.WARN_ONLY,
        reconciliation_interval_seconds: int = 300,
        shadow_mode: bool = False,
        shadow_config: ShadowTradingConfig | None = None,
    ) -> None:
        """Initialize live trading engine.

        Args:
            strategy: TradingAlgorithm instance (same class as backtest)
            broker_adapter: Broker adapter for order execution and market data
            data_portal: PolarsDataPortal for historical data access
            portfolio: Portfolio object (optional, will create if None)
            account: Account object (optional, will create if None)
            scheduler: Trading scheduler (optional, for scheduled callbacks)
            state_manager: StateManager for checkpoint/restore (default: create new)
            checkpoint_interval_seconds: Checkpoint frequency in seconds (default: 60)
            reconciliation_strategy: Strategy for position reconciliation (default: WARN_ONLY)
            reconciliation_interval_seconds: Reconciliation frequency in seconds (default: 300 = 5 minutes)
            shadow_mode: Enable shadow backtest validation (default: False)
            shadow_config: Shadow trading configuration (default: use defaults)

        Example:
            >>> engine = LiveTradingEngine(
            ...     strategy=MyStrategy(),
            ...     broker_adapter=PaperBroker(),
            ...     data_portal=portal
            ... )
            >>> await engine.run()
        """
        self._strategy = strategy
        self._broker = broker_adapter
        self._data_portal = data_portal
        self._scheduler = scheduler
        self._checkpoint_interval_seconds = checkpoint_interval_seconds
        self._reconciliation_interval_seconds = reconciliation_interval_seconds

        # Initialize components
        self._event_queue: asyncio.PriorityQueue[Event] = asyncio.PriorityQueue()
        self._dispatcher = EventDispatcher()
        self._order_manager = OrderManager()
        self._data_feed = DataFeed(broker_adapter)
        self._state_manager = state_manager or StateManager()
        self._reconciler = PositionReconciler(broker_adapter, reconciliation_strategy)

        # Portfolio and account (placeholder - will be fully implemented in later stories)
        self._portfolio = portfolio
        self._account = account

        # Strategy executor
        self._strategy_executor = StrategyExecutor(
            strategy=strategy,
            data_portal=data_portal,
            portfolio=self._portfolio,
            account=self._account,
        )

        # Engine state
        self._running = False
        self._shutdown_requested = False

        # Shadow mode setup
        self._shadow_mode = shadow_mode
        self._shadow_engine: ShadowBacktestEngine | None = None
        if shadow_mode:
            config = shadow_config or ShadowTradingConfig()
            self._shadow_engine = ShadowBacktestEngine(
                strategy=strategy,
                config=config,
                commission_model=(
                    broker_adapter.commission_model
                    if hasattr(broker_adapter, "commission_model")
                    else None
                ),
                slippage_model=(
                    broker_adapter.slippage_model
                    if hasattr(broker_adapter, "slippage_model")
                    else None
                ),
                starting_cash=Decimal("100000"),  # TODO: Get from portfolio
            )

        # Periodic checkpoint scheduler
        self._checkpoint_scheduler = AsyncIOScheduler()

        # Register event handlers
        self._register_handlers()

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        logger.info(
            "engine_initialized",
            strategy=strategy.__class__.__name__,
            broker=broker_adapter.__class__.__name__,
            checkpoint_interval_seconds=checkpoint_interval_seconds,
            reconciliation_interval_seconds=reconciliation_interval_seconds,
            shadow_mode=shadow_mode,
        )

    def _register_handlers(self) -> None:
        """Register event handlers with dispatcher."""
        # Market data → strategy
        self._dispatcher.register_handler("market_data", self._handle_market_data)

        # Order fill → portfolio update + strategy notification
        self._dispatcher.register_handler("order_fill", self._handle_order_fill)

        # Order reject → strategy notification
        self._dispatcher.register_handler("order_reject", self._handle_order_reject)

        # Scheduled trigger → strategy callback
        self._dispatcher.register_handler("scheduled_trigger", self._handle_scheduled_trigger)

        # System error → error handler
        self._dispatcher.register_handler("system_error", self._handle_system_error)

        logger.debug("event_handlers_registered")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        if sys.platform != "win32":
            # Unix-like systems
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.graceful_shutdown()))
        else:
            # Windows
            signal.signal(
                signal.SIGTERM, lambda s, f: asyncio.create_task(self.graceful_shutdown())
            )
            signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(self.graceful_shutdown()))

        logger.debug("signal_handlers_configured")

    async def run(self) -> None:
        """Run the live trading engine.

        This is the main entry point that starts the async event loop.
        The engine runs until graceful_shutdown() is called.
        """
        # Comprehensive system startup logging (AC: 4)
        logger.info(
            "system_startup",
            event_type="system_startup",
            version=__version__,
            strategy_class=self._strategy.__class__.__name__,
            broker=self._broker.__class__.__name__,
            checkpoint_interval_seconds=self._checkpoint_interval_seconds,
            reconciliation_strategy=self._reconciliation_strategy.value,
            shadow_mode=self._shadow_mode,
            timestamp=pd.Timestamp.now(tz="UTC").isoformat(),
        )
        self._running = True

        try:
            # Restore state from checkpoint if available
            await self._restore_state()

            # Connect to broker
            await self._broker.connect()
            logger.info("broker_connected")

            # Initialize strategy
            await self._strategy_executor.initialize()
            logger.info("strategy_initialized")

            # Start periodic checkpoint scheduler
            self._start_checkpoint_scheduler()

            # Start periodic reconciliation scheduler
            self._start_reconciliation_scheduler()

            # Run initial reconciliation on startup
            await self._run_reconciliation()

            # Start shadow engine if enabled
            if self._shadow_engine:
                await self._shadow_engine.start()
                logger.info("shadow_engine_started")

            # Start data feed monitoring (background task)
            monitoring_task = asyncio.create_task(self._data_feed.start_monitoring())

            # Start main event loop
            await self._event_loop()

            # Wait for monitoring to stop
            await self._data_feed.stop_monitoring()
            await monitoring_task

        except Exception as e:
            # Comprehensive error logging (AC: 4)
            logger.error(
                "system_error",
                event_type="system_error",
                exception_type=type(e).__name__,
                error_message=str(e),
                timestamp=pd.Timestamp.now(tz="UTC").isoformat(),
                exc_info=True,
            )
            await self.graceful_shutdown()
            raise
        finally:
            self._running = False
            # Comprehensive shutdown logging (AC: 4)
            logger.info(
                "system_shutdown",
                event_type="system_shutdown",
                reason="graceful" if not self._shutdown_requested else "requested",
                timestamp=pd.Timestamp.now(tz="UTC").isoformat(),
            )

    async def _event_loop(self) -> None:
        """Main event processing loop.

        Processes events from the priority queue in priority order:
        1. SystemError (priority 1)
        2. OrderFill (priority 2)
        3. OrderReject (priority 3)
        4. ScheduledTrigger (priority 4)
        5. MarketData (priority 5)
        """
        logger.info("event_loop_started")

        # Start market data feed task
        data_feed_task = asyncio.create_task(self._market_data_feed())

        while self._running and not self._shutdown_requested:
            try:
                # Get next event from queue (blocks until event available)
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)

                logger.debug(
                    "event_dequeued",
                    event_type=event.event_type,
                    priority=event.priority,
                )

                # Dispatch event to handlers
                await self._dispatcher.dispatch(event)

                # Mark task done
                self._event_queue.task_done()

            except TimeoutError:
                # No events in queue, continue
                continue
            except Exception as e:
                logger.error("event_processing_error", error=str(e), exc_info=True)
                # Create system error event
                error_event = SystemErrorEvent(
                    error_type="event_processing",
                    error_message=str(e),
                    exception_details=repr(e),
                    error_timestamp=asyncio.get_event_loop().time(),
                )
                await self._event_queue.put(error_event)

        # Cancel data feed task
        data_feed_task.cancel()
        try:
            await data_feed_task
        except asyncio.CancelledError:
            pass

        logger.info("event_loop_stopped")

    async def _market_data_feed(self) -> None:
        """Background task that fetches market data and enqueues events."""
        logger.info("market_data_feed_started")

        while self._running and not self._shutdown_requested:
            try:
                # Get next market data (blocking)
                event = await self._data_feed.get_next_market_data()

                # Enqueue market data event
                await self._event_queue.put(event)

                logger.debug("market_data_enqueued", asset=event.asset_symbol)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("market_data_feed_error", error=str(e), exc_info=True)
                await asyncio.sleep(1)  # Backoff on error

        logger.info("market_data_feed_stopped")

    async def _handle_market_data(self, event: Event) -> None:
        """Handle market data event.

        Args:
            event: MarketDataEvent
        """
        if not isinstance(event, MarketDataEvent):
            logger.warning("unexpected_event_type", expected="MarketDataEvent")
            return

        # Forward to strategy executor
        await self._strategy_executor.on_data(event)

        # Broadcast to shadow engine if enabled
        if self._shadow_engine and self._shadow_engine._running:
            try:
                # Process same market data in shadow backtest
                await self._shadow_engine.process_market_data(
                    timestamp=event.timestamp, market_data=event.data
                )

                # Check alignment and update checkpoint metrics
                if not self._shadow_engine.check_alignment():
                    logger.error(
                        "shadow_alignment_failed",
                        timestamp=event.timestamp.isoformat(),
                    )
                    # Shadow failure doesn't halt live trading
                    # Circuit breaker in shadow engine will trip if needed

            except Exception as e:
                logger.error(
                    "shadow_engine_error",
                    error=str(e),
                    timestamp=event.timestamp.isoformat(),
                )
                # Shadow errors isolated from live trading

    async def _handle_order_fill(self, event: Event) -> None:
        """Handle order fill event.

        Updates portfolio and notifies strategy.

        Args:
            event: OrderFillEvent
        """
        if not isinstance(event, OrderFillEvent):
            logger.warning("unexpected_event_type", expected="OrderFillEvent")
            return

        # Update order status in order manager
        await self._order_manager.update_order_status(
            order_id=event.order_id,
            status="filled",
            filled_price=event.fill_price,
            filled_amount=event.filled_amount,
            commission=event.commission,
        )

        # TODO: Update portfolio with filled order
        # This will be implemented in Story 6.3 with StateManager

        # Notify strategy (optional callback)
        await self._strategy_executor.on_order_fill(event)

    async def _handle_order_reject(self, event: Event) -> None:
        """Handle order reject event.

        Args:
            event: OrderRejectEvent
        """
        if not isinstance(event, OrderRejectEvent):
            logger.warning("unexpected_event_type", expected="OrderRejectEvent")
            return

        # Update order status
        await self._order_manager.update_order_status(
            order_id=event.order_id,
            status="rejected",
            reject_reason=event.reason,
        )

        # Notify strategy (optional callback)
        await self._strategy_executor.on_order_reject(event)

    async def _handle_scheduled_trigger(self, event: Event) -> None:
        """Handle scheduled trigger event.

        Args:
            event: ScheduledTriggerEvent
        """
        if not isinstance(event, ScheduledTriggerEvent):
            logger.warning("unexpected_event_type", expected="ScheduledTriggerEvent")
            return

        # Forward to strategy executor
        await self._strategy_executor.on_scheduled_event(event)

    async def _handle_system_error(self, event: Event) -> None:
        """Handle system error event.

        Logs error and potentially triggers alerting.

        Args:
            event: SystemErrorEvent
        """
        if not isinstance(event, SystemErrorEvent):
            logger.warning("unexpected_event_type", expected="SystemErrorEvent")
            return

        logger.critical(
            "system_error",
            error_type=event.error_type,
            error_message=event.error_message,
            exception_details=event.exception_details,
        )

        # TODO: Implement alerting system (Epic 6 future story)

    def _start_checkpoint_scheduler(self) -> None:
        """Start periodic checkpoint scheduler."""
        self._checkpoint_scheduler.add_job(
            self._save_checkpoint,
            "interval",
            seconds=self._checkpoint_interval_seconds,
            id="periodic_checkpoint",
        )
        self._checkpoint_scheduler.start()
        logger.info(
            "checkpoint_scheduler_started",
            interval_seconds=self._checkpoint_interval_seconds,
        )

    def _start_reconciliation_scheduler(self) -> None:
        """Start periodic reconciliation scheduler."""
        self._checkpoint_scheduler.add_job(
            self._run_reconciliation,
            "interval",
            seconds=self._reconciliation_interval_seconds,
            id="periodic_reconciliation",
        )
        logger.info(
            "reconciliation_scheduler_started",
            interval_seconds=self._reconciliation_interval_seconds,
        )

    async def _run_reconciliation(self) -> None:
        """Run comprehensive reconciliation of positions, cash, and orders.

        This method is called:
        1. On engine startup (after state restoration)
        2. Periodically during operation (every reconciliation_interval_seconds)
        3. After significant events (large order fills, strategy changes)
        """
        try:
            logger.info("reconciliation_started")

            # Get current local positions (placeholder - will use DecimalLedger)
            local_positions = []
            if self._portfolio:
                # TODO: Extract positions from DecimalLedger
                pass

            # Get local cash balance (placeholder)
            local_cash = Decimal("100000.00")  # TODO: Get from portfolio

            # Get local pending orders
            pending_orders_raw = await self._order_manager.get_pending_orders()
            local_orders = []
            for order in pending_orders_raw:
                local_orders.append(
                    OrderSnapshot(
                        order_id=order.get("order_id"),
                        asset=order.get("asset"),
                        sid=order.get("sid", 0),
                        amount=str(order.get("amount", Decimal(0))),
                        order_type=order.get("order_type", "market"),
                        limit_price=str(order["limit_price"]) if order.get("limit_price") else None,
                        broker_order_id=order.get("broker_order_id"),
                        status=order.get("status", "pending"),
                        created_at=order.get("created_at", datetime.now()),
                    )
                )

            # Run reconciliation
            report = await self._reconciler.reconcile_all(
                local_positions=local_positions,
                local_cash=local_cash,
                local_orders=local_orders,
            )

            # Log results
            if report.total_discrepancy_count() == 0:
                logger.info("reconciliation_success", summary=report.summary)
            else:
                logger.warning(
                    "reconciliation_discrepancies_detected",
                    discrepancy_count=report.total_discrepancy_count(),
                    position_discrepancies=len(report.position_discrepancies),
                    cash_discrepancy=report.cash_discrepancy is not None,
                    order_discrepancies=len(report.order_discrepancies),
                    summary=report.summary,
                )

                # Log details of critical discrepancies
                if report.has_critical_discrepancies():
                    logger.critical(
                        "critical_discrepancies_detected",
                        position_discrepancies=[
                            {
                                "asset": d.asset,
                                "local": d.local_amount,
                                "broker": d.broker_amount,
                                "type": d.discrepancy_type.value,
                                "severity": d.severity.value,
                            }
                            for d in report.position_discrepancies
                            if d.severity == DiscrepancySeverity.CRITICAL
                        ],
                    )

                # TODO: Apply reconciliation actions based on strategy
                # For now, just log the recommended actions
                for action in report.actions_taken:
                    logger.info("reconciliation_action", action=action)

        except ReconciliationError as e:
            # Critical reconciliation error - may halt engine
            logger.critical(
                "reconciliation_critical_error",
                error=str(e),
                message="Manual intervention may be required",
            )
            raise
        except Exception as e:
            logger.error("reconciliation_error", error=str(e), exc_info=True)

    async def _save_checkpoint(self) -> None:
        """Save current engine state to checkpoint.

        This method captures positions, orders, cash balance, and strategy state.
        """
        try:
            # Get strategy name
            strategy_name = self._strategy.__class__.__name__

            # Capture positions (placeholder - will use DecimalLedger in full implementation)
            positions = []
            if self._portfolio:
                # TODO: Extract positions from DecimalLedger
                pass

            # Capture pending orders
            pending_orders = []
            for order in await self._order_manager.get_pending_orders():
                pending_orders.append(
                    OrderSnapshot(
                        order_id=order.get("order_id"),
                        asset=order.get("asset"),
                        sid=order.get("sid", 0),
                        amount=str(order.get("amount", Decimal(0))),
                        order_type=order.get("order_type", "market"),
                        limit_price=str(order["limit_price"]) if order.get("limit_price") else None,
                        broker_order_id=order.get("broker_order_id"),
                        status=order.get("status", "pending"),
                        created_at=order.get("created_at", datetime.now()),
                    )
                )

            # Capture cash balance (placeholder)
            cash_balance = "100000.00"  # TODO: Get from portfolio

            # Capture strategy state
            strategy_state = {}
            if hasattr(self._strategy, "get_state"):
                strategy_state = self._strategy.get_state()

            # Create checkpoint
            checkpoint = StateCheckpoint(
                strategy_name=strategy_name,
                timestamp=datetime.now(),
                strategy_state=strategy_state,
                positions=positions,
                pending_orders=pending_orders,
                cash_balance=cash_balance,
            )

            # Save checkpoint
            self._state_manager.save_checkpoint(strategy_name, checkpoint)

            logger.debug("checkpoint_saved_periodic", strategy_name=strategy_name)

        except Exception as e:
            logger.error("checkpoint_save_error", error=str(e), exc_info=True)

    async def _restore_state(self) -> None:
        """Restore engine state from checkpoint.

        Loads checkpoint, validates staleness, and restores positions/orders.
        """
        try:
            strategy_name = self._strategy.__class__.__name__

            # Load checkpoint
            checkpoint = self._state_manager.load_checkpoint(strategy_name)

            if checkpoint is None:
                logger.info(
                    "no_checkpoint_found",
                    strategy_name=strategy_name,
                    message="Starting with fresh state",
                )
                return

            # Checkpoint loaded, restore state
            logger.info(
                "restoring_state",
                strategy_name=strategy_name,
                checkpoint_timestamp=checkpoint.timestamp.isoformat(),
                positions_count=len(checkpoint.positions),
                pending_orders_count=len(checkpoint.pending_orders),
            )

            # Restore strategy state
            if checkpoint.strategy_state and hasattr(self._strategy, "set_state"):
                self._strategy.set_state(checkpoint.strategy_state)

            # Restore positions (placeholder - will integrate with DecimalLedger)
            # TODO: Restore positions to DecimalLedger

            # Restore pending orders
            for order_snapshot in checkpoint.pending_orders:
                # TODO: Restore order to OrderManager
                pass

            # Restore cash balance (placeholder)
            # TODO: Restore cash to portfolio

            # Reconcile positions with broker
            reconciliation_result = await self._reconciler.reconcile_positions(checkpoint.positions)

            if reconciliation_result["discrepancies"]:
                logger.warning(
                    "position_reconciliation_completed",
                    discrepancies_count=len(reconciliation_result["discrepancies"]),
                    action_taken=reconciliation_result["action_taken"],
                )

                # If sync to broker, update local positions
                if reconciliation_result["updated_positions"]:
                    # TODO: Apply updated positions to DecimalLedger
                    pass
            else:
                logger.info("position_reconciliation_success", message="All positions match")

            logger.info("state_restored_successfully", strategy_name=strategy_name)

        except Exception as e:
            logger.error("state_restoration_error", error=str(e), exc_info=True)
            raise

    async def graceful_shutdown(self) -> None:
        """Gracefully shutdown engine.

        This performs cleanup:
        1. Stop accepting new events
        2. Process remaining events in queue
        3. Persist state checkpoint
        4. Disconnect from broker
        5. Cleanup resources
        """
        if self._shutdown_requested:
            logger.warning("shutdown_already_requested")
            return

        # Comprehensive shutdown logging (AC: 4)
        logger.info(
            "graceful_shutdown_initiated",
            event_type="graceful_shutdown",
            reason="user_requested",
            timestamp=pd.Timestamp.now(tz="UTC").isoformat(),
        )
        self._shutdown_requested = True

        # Stop accepting new events
        self._running = False

        # Stop checkpoint scheduler
        if self._checkpoint_scheduler.running:
            self._checkpoint_scheduler.shutdown(wait=False)
            logger.info("checkpoint_scheduler_stopped")

        # Wait for queue to drain (with timeout)
        try:
            await asyncio.wait_for(self._event_queue.join(), timeout=10.0)
            logger.info("event_queue_drained")
        except TimeoutError:
            logger.warning("event_queue_drain_timeout")

        # Save final checkpoint
        await self._save_checkpoint()
        logger.info("final_checkpoint_saved")

        # Disconnect from broker
        try:
            await self._broker.disconnect()
            logger.info("broker_disconnected")
        except Exception as e:
            logger.error("broker_disconnect_error", error=str(e))

        logger.info("graceful_shutdown_complete")

    async def enqueue_event(self, event: Event) -> None:
        """Enqueue event for processing.

        This allows external components to inject events into the engine.

        Args:
            event: Event to enqueue
        """
        await self._event_queue.put(event)
        logger.debug("event_enqueued_externally", event_type=event.event_type)

    def is_running(self) -> bool:
        """Check if engine is running.

        Returns:
            True if running, False otherwise
        """
        return self._running

    def get_health_status(self) -> dict:
        """Get engine health status including shadow mode metrics.

        Returns:
            Dictionary with engine status and shadow metrics
        """
        status = {
            "engine_running": self._running,
            "shadow_enabled": self._shadow_mode,
        }

        if self._shadow_engine:
            status["shadow_engine_running"] = self._shadow_engine._running
            status["alignment_metrics"] = self._shadow_engine.get_alignment_metrics()

        return status
