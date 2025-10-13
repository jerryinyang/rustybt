"""Shadow backtest engine for parallel validation.

This module provides a lightweight backtest engine that runs in parallel with
live trading to validate signal alignment and execution quality.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from rustybt.algorithm import TradingAlgorithm
from rustybt.assets import Asset
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.order import DecimalOrder
from rustybt.live.shadow.alignment_breaker import AlignmentCircuitBreaker
from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.execution_tracker import ExecutionQualityTracker
from rustybt.live.shadow.models import SignalRecord
from rustybt.live.shadow.signal_validator import SignalAlignmentValidator

logger = structlog.get_logger()


class ShadowBacktestEngine:
    """Shadow backtest engine for real-time validation.

    This engine runs a simplified backtest in parallel with live trading,
    consuming the same market data to generate signals that can be compared
    with live signals for alignment validation.

    Key differences from full backtest:
    - Uses same execution models (slippage, commission) as PaperBroker
    - Maintains separate DecimalLedger for portfolio tracking
    - Does not execute actual orders (just tracks signals and fills)
    - Optimized for real-time performance with minimal overhead

    Attributes:
        strategy: TradingAlgorithm instance (separate from live)
        config: Shadow trading configuration
        signal_validator: Signal alignment validator
        execution_tracker: Execution quality tracker
        circuit_breaker: Alignment circuit breaker
        ledger: Separate portfolio ledger for shadow backtest
    """

    def __init__(
        self,
        strategy: TradingAlgorithm,
        config: ShadowTradingConfig,
        commission_model: Any,
        slippage_model: Any,
        starting_cash: Decimal,
    ):
        """Initialize shadow backtest engine.

        Args:
            strategy: TradingAlgorithm instance (will create separate copy)
            config: Shadow trading configuration
            commission_model: Commission model (same as live)
            slippage_model: Slippage model (same as live)
            starting_cash: Starting capital (same as live)
        """
        self.config = config
        self._commission_model = commission_model
        self._slippage_model = slippage_model

        # Store strategy initialization params for cloning
        self._strategy_sim_params = strategy.sim_params
        self._strategy_asset_finder = strategy.asset_finder

        # Create separate strategy instance for shadow execution
        # This prevents state contamination between live and shadow
        self._strategy = self._clone_strategy(strategy)

        # Initialize shadow portfolio components
        self._ledger = DecimalLedger(starting_cash=starting_cash)
        self._blotter = DecimalBlotter()

        # Initialize validation components
        self.signal_validator = SignalAlignmentValidator(config)
        self.execution_tracker = ExecutionQualityTracker(config)
        self.circuit_breaker = AlignmentCircuitBreaker(config)

        # Shadow engine state
        self._running = False
        self._current_timestamp: datetime | None = None
        self._signal_queue: asyncio.Queue = asyncio.Queue()

        logger.info(
            "shadow_backtest_engine_initialized",
            strategy=strategy.__class__.__name__,
            starting_cash=str(starting_cash),
            config_enabled=config.enabled,
        )

    def _clone_strategy(self, strategy: TradingAlgorithm) -> TradingAlgorithm:
        """Create a separate instance of strategy for shadow execution.

        Args:
            strategy: Original strategy instance

        Returns:
            New strategy instance with same configuration
        """
        # Create new instance of same strategy class with required params
        strategy_class = strategy.__class__
        shadow_strategy = strategy_class(
            sim_params=self._strategy_sim_params,
            asset_finder=self._strategy_asset_finder,
        )

        # Copy configuration attributes from original strategy
        # This includes user-set attributes like asset, thresholds, etc.
        # Only copy attributes from __dict__ to avoid triggering property accessors
        for attr, value in strategy.__dict__.items():
            if not attr.startswith("_") and not callable(value):
                try:
                    setattr(shadow_strategy, attr, value)
                except AttributeError:
                    # Skip read-only attributes
                    pass

        # Call initialize() on the cloned strategy if it hasn't been called yet
        # This ensures the strategy is properly set up with its attributes
        if hasattr(shadow_strategy, "initialize") and callable(shadow_strategy.initialize):
            try:
                # Check if initialize() has already been called by looking for a marker attribute
                if not hasattr(shadow_strategy, "_initialized"):
                    shadow_strategy.initialize()
                    shadow_strategy._initialized = True
            except Exception as e:
                logger.warning(
                    "shadow_strategy_initialize_failed",
                    strategy_class=strategy_class.__name__,
                    error=str(e),
                )

        logger.debug(
            "strategy_cloned_for_shadow",
            strategy_class=strategy_class.__name__,
        )

        return shadow_strategy

    async def process_market_data(
        self,
        timestamp: datetime,
        market_data: dict[Asset, dict],
    ) -> None:
        """Process market data event in shadow backtest.

        This simulates the strategy's handle_data() call using the same
        market data as live trading.

        Args:
            timestamp: Market data timestamp
            market_data: Market data by asset (dict with 'price', 'volume', etc.)
        """
        if not self.config.enabled:
            return

        self._current_timestamp = timestamp

        # 1. Create simple BarData wrapper for strategy
        bar_data = ShadowBarData(market_data, timestamp)

        # 2. Intercept order() calls by wrapping strategy's order method
        original_order = getattr(self._strategy, "order", None)
        captured_orders = []

        def intercept_order(asset, amount, **kwargs):
            """Intercept and capture order() calls from strategy."""
            order_type = kwargs.get("order_type", "market")
            limit_price = kwargs.get("limit_price")

            # Capture the signal
            signal = SignalRecord(
                timestamp=timestamp,
                asset=asset,
                side="BUY" if amount > 0 else "SELL",
                quantity=abs(Decimal(str(amount))),
                price=Decimal(str(limit_price)) if limit_price else None,
                order_type=order_type,
                source="backtest",
            )
            captured_orders.append(signal)

            # Don't actually execute (just capture signal)
            logger.debug(
                "shadow_signal_captured",
                asset=asset.symbol if hasattr(asset, "symbol") else str(asset),
                amount=str(amount),
                order_type=order_type,
            )

        # Temporarily replace order method
        if original_order:
            self._strategy.order = intercept_order

        try:
            # 3. Call strategy.handle_data() with intercepted order method
            if hasattr(self._strategy, "handle_data"):
                # Set datetime on strategy for compatibility with TradingAlgorithm properties
                self._strategy.datetime = timestamp

                # Create a no-op metrics_tracker for shadow mode
                # This is needed because TradingAlgorithm properties (account, portfolio) call this
                class NoOpMetricsTracker:
                    def sync_last_sale_prices(self, dt, data_portal):
                        pass  # No-op for shadow mode

                # Save original and set no-op tracker
                original_metrics_tracker = getattr(self._strategy, "metrics_tracker", None)
                if (
                    not hasattr(self._strategy, "metrics_tracker")
                    or self._strategy.metrics_tracker is None
                ):
                    self._strategy.metrics_tracker = NoOpMetricsTracker()

                # Create simple context for strategy
                context = ShadowContext(self._ledger, self._strategy)
                self._strategy.handle_data(context, bar_data)

                # Restore original metrics_tracker
                if original_metrics_tracker is not None:
                    self._strategy.metrics_tracker = original_metrics_tracker

        except Exception as e:
            logger.error(
                "shadow_handle_data_error",
                error=str(e),
                timestamp=timestamp.isoformat(),
            )
        finally:
            # Restore original order method
            if original_order:
                self._strategy.order = original_order

        # 4. Simulate fills for captured orders using slippage/commission models
        for signal in captured_orders:
            await self._simulate_fill(signal, market_data.get(signal.asset, {}))

        # 5. Add backtest signals to validator for comparison
        for signal in captured_orders:
            self.signal_validator.add_backtest_signal(signal)

        logger.debug(
            "shadow_market_data_processed",
            timestamp=timestamp.isoformat(),
            asset_count=len(market_data),
            signals_captured=len(captured_orders),
        )

    async def _simulate_fill(
        self,
        signal: SignalRecord,
        market_data: dict,
    ) -> None:
        """Simulate order fill using slippage and commission models.

        Args:
            signal: Signal to simulate fill for
            market_data: Market data for the asset
        """
        current_price = Decimal(str(market_data.get("price", 0)))
        if current_price == Decimal("0"):
            logger.warning(
                "shadow_fill_skipped_no_price",
                asset=signal.asset.symbol if hasattr(signal.asset, "symbol") else str(signal.asset),
            )
            return

        # Create a minimal DecimalOrder for slippage calculation
        order_amount = signal.quantity if signal.side == "BUY" else -signal.quantity
        order = DecimalOrder(
            dt=self._current_timestamp,
            asset=signal.asset,
            amount=order_amount,
        )

        # Apply slippage model (use calculate method for DecimalSlippageModel)
        fill_price = self._slippage_model.calculate(order, current_price)

        # Apply commission model
        commission = self._commission_model.calculate(order, fill_price, signal.quantity)

        # Update shadow ledger (simplified - real implementation would use full transaction flow)
        cost = fill_price * signal.quantity + commission

        if signal.side == "BUY":
            self._ledger.cash -= cost
        else:
            self._ledger.cash += cost

        logger.debug(
            "shadow_fill_simulated",
            asset=signal.asset.symbol if hasattr(signal.asset, "symbol") else str(signal.asset),
            fill_price=str(fill_price),
            commission=str(commission),
            quantity=str(signal.quantity),
        )

    def add_live_signal(
        self,
        asset: Asset,
        side: str,
        quantity: Decimal,
        price: Decimal | None,
        order_type: str,
        timestamp: datetime,
    ) -> None:
        """Add live signal for comparison with backtest signal.

        Args:
            asset: Asset being traded
            side: "BUY" or "SELL"
            quantity: Order quantity
            price: Signal price (None for market orders)
            order_type: Order type
            timestamp: Signal timestamp
        """
        live_signal = SignalRecord(
            timestamp=timestamp,
            asset=asset,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            source="live",
        )

        # Match with backtest signal
        match_result = self.signal_validator.add_live_signal(live_signal)

        if match_result:
            backtest_signal, alignment = match_result
            logger.info(
                "live_signal_matched",
                asset=asset.symbol,
                alignment=alignment.value,
                backtest_signal_id=backtest_signal.signal_id,
                live_signal_id=live_signal.signal_id,
            )
        else:
            logger.warning(
                "live_signal_unmatched",
                asset=asset.symbol,
                side=side,
                quantity=str(quantity),
                timestamp=timestamp.isoformat(),
            )

    def add_live_fill(
        self,
        order_id: str,
        signal_price: Decimal,
        fill_price: Decimal,
        fill_quantity: Decimal,
        order_quantity: Decimal,
        commission: Decimal,
        timestamp: datetime,
    ) -> None:
        """Add live fill for execution quality tracking.

        Args:
            order_id: Order identifier
            signal_price: Price when signal generated
            fill_price: Actual fill price from broker
            fill_quantity: Quantity filled
            order_quantity: Quantity ordered
            commission: Commission charged
            timestamp: Fill timestamp
        """
        self.execution_tracker.add_live_fill(
            order_id=order_id,
            signal_price=signal_price,
            fill_price=fill_price,
            fill_quantity=fill_quantity,
            order_quantity=order_quantity,
            commission=commission,
            timestamp=timestamp,
        )

        logger.debug(
            "live_fill_tracked",
            order_id=order_id,
            fill_price=str(fill_price),
            fill_quantity=str(fill_quantity),
        )

    def check_alignment(self) -> bool:
        """Check current alignment and trip circuit breaker if needed.

        Returns:
            True if alignment is good, False if circuit breaker tripped
        """
        # Calculate alignment metrics
        signal_match_rate = self.signal_validator.calculate_match_rate()
        execution_metrics = self.execution_tracker.calculate_metrics()

        from rustybt.live.shadow.models import AlignmentMetrics

        alignment_metrics = AlignmentMetrics(
            execution_quality=execution_metrics,
            backtest_signal_count=len(self.signal_validator._backtest_signals),
            live_signal_count=len(self.signal_validator._live_signals),
            signal_match_rate=signal_match_rate,
            divergence_breakdown=self.signal_validator.get_divergence_breakdown(),
        )

        # Check circuit breaker
        is_aligned = self.circuit_breaker.check_alignment(alignment_metrics)

        if not is_aligned:
            logger.error(
                "shadow_alignment_degraded_circuit_breaker_tripped",
                signal_match_rate=str(signal_match_rate),
                breaches=self.circuit_breaker.get_breach_summary(),
            )

        return is_aligned

    def get_alignment_metrics(self) -> dict:
        """Get current alignment metrics for monitoring/dashboard.

        Returns:
            Dictionary with alignment metrics
        """
        signal_match_rate = self.signal_validator.calculate_match_rate()
        execution_metrics = self.execution_tracker.calculate_metrics()

        from rustybt.live.shadow.models import AlignmentMetrics

        alignment_metrics = AlignmentMetrics(
            execution_quality=execution_metrics,
            backtest_signal_count=len(self.signal_validator._backtest_signals),
            live_signal_count=len(self.signal_validator._live_signals),
            signal_match_rate=signal_match_rate,
            divergence_breakdown=self.signal_validator.get_divergence_breakdown(),
        )

        return alignment_metrics.to_dict()

    async def start(self) -> None:
        """Start shadow backtest engine."""
        if not self.config.enabled:
            logger.info("shadow_engine_disabled_skipping_start")
            return

        self._running = True
        logger.info("shadow_backtest_engine_started")

    async def stop(self) -> None:
        """Stop shadow backtest engine."""
        self._running = False
        logger.info("shadow_backtest_engine_stopped")

    def reset(self) -> None:
        """Reset shadow engine state."""
        self.signal_validator.reset()
        self.execution_tracker.reset()
        self.circuit_breaker.reset()
        self._ledger = DecimalLedger(starting_cash=self._ledger.starting_cash)

        logger.info("shadow_backtest_engine_reset")


class ShadowBarData:
    """Simplified BarData wrapper for shadow backtest strategy execution.

    Provides minimal interface needed for strategy.handle_data() to access
    current market data without full DataPortal infrastructure.
    """

    def __init__(self, market_data: dict[Asset, dict], timestamp: datetime):
        """Initialize shadow bar data.

        Args:
            market_data: Market data by asset
            timestamp: Current bar timestamp
        """
        self._market_data = market_data
        self._timestamp = timestamp

    def current(self, asset: Asset, field: str) -> Any:
        """Get current value for asset field.

        Args:
            asset: Asset to get data for
            field: Field name ('price', 'volume', 'open', 'high', 'low', 'close')

        Returns:
            Field value (Decimal for price fields, int for volume)
        """
        data = self._market_data.get(asset, {})
        value = data.get(field)

        if value is not None:
            if field in ("price", "open", "high", "low", "close"):
                return Decimal(str(value))
            return value

        return None

    def can_trade(self, asset: Asset) -> bool:
        """Check if asset is tradable (has current data).

        Args:
            asset: Asset to check

        Returns:
            True if asset has current price data
        """
        return asset in self._market_data and "price" in self._market_data[asset]


class ShadowContext:
    """Simplified context object for shadow backtest strategy execution.

    Provides minimal interface needed for strategy.handle_data() without
    full TradingAlgorithm context.
    """

    def __init__(self, ledger: DecimalLedger, strategy: TradingAlgorithm):
        """Initialize shadow context.

        Args:
            ledger: Shadow portfolio ledger
            strategy: Strategy instance (for accessing strategy-defined context variables)
        """
        self._ledger = ledger
        self._strategy = strategy

        # Copy any context variables from strategy (excluding properties that require data_portal)
        # Properties like 'account' and 'portfolio' trigger _sync_last_sale_prices() which needs data_portal
        excluded_attrs = {"account", "portfolio", "datetime", "data_portal", "metrics_tracker"}

        for attr in dir(strategy):
            if attr in excluded_attrs:
                continue
            if not attr.startswith("_"):
                try:
                    value = getattr(strategy, attr)
                    if not callable(value):
                        setattr(self, attr, value)
                except (AttributeError, Exception):
                    # Skip attributes that can't be accessed or raise errors
                    pass

    @property
    def portfolio(self):
        """Get current portfolio state."""
        return self._ledger

    def __getattr__(self, name):
        """Fallback to strategy for undefined attributes."""
        return getattr(self._strategy, name, None)
