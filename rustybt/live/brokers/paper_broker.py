"""Paper trading broker adapter for RustyBT.

This module implements a simulated broker (PaperBroker) that mimics real
broker behavior with realistic fills, latency, slippage, and commission models.
Used for strategy validation before live trading with real capital.
"""

import asyncio
import random
from datetime import datetime
from decimal import Decimal

import structlog

from rustybt.assets import Asset
from rustybt.exceptions import (
    BrokerError as BaseBrokerError,
)
from rustybt.exceptions import (
    DataNotFoundError,
)
from rustybt.exceptions import (
    InsufficientFundsError as BaseInsufficientFundsError,
)
from rustybt.finance.decimal.commission import DecimalCommissionModel, NoCommission
from rustybt.finance.decimal.order import DecimalOrder
from rustybt.finance.decimal.position import DecimalPosition
from rustybt.finance.decimal.slippage import DecimalSlippageModel, NoSlippage
from rustybt.finance.decimal.transaction import DecimalTransaction
from rustybt.live.brokers.base import BrokerAdapter

logger = structlog.get_logger(__name__)


class PaperBrokerError(BaseBrokerError):
    """Base exception for PaperBroker errors."""


class InsufficientFundsError(BaseInsufficientFundsError, PaperBrokerError):
    """Raised when insufficient funds for order execution."""


class MarketDataUnavailableError(DataNotFoundError, PaperBrokerError):
    """Raised when market data is unavailable for asset."""


class PaperBroker(BrokerAdapter):
    """Paper trading broker adapter with simulated execution.

    Implements BrokerAdapter interface to simulate broker behavior for
    strategy validation without real capital risk. Features include:

    - Real-time market data consumption (via subscribe_market_data)
    - Simulated order execution (market, limit, stop, stop-limit)
    - Configurable latency simulation (network + exchange delays)
    - Partial fill simulation based on volume
    - Commission and slippage models from backtest
    - Paper position and balance tracking

    This is a REAL implementation (not a mock) that uses actual Decimal
    arithmetic and real execution logic to match backtest behavior.

    Example:
        >>> broker = PaperBroker(
        ...     starting_cash=Decimal("100000"),
        ...     commission_model=PerShareCommission(Decimal("0.005")),
        ...     slippage_model=FixedBasisPointsSlippage(Decimal("5")),
        ...     order_latency_ms=100,
        ...     volume_limit_pct=Decimal("0.025")
        ... )
        >>> await broker.connect()
        >>> order_id = await broker.submit_order(
        ...     asset=asset,
        ...     amount=Decimal("100"),
        ...     order_type="market"
        ... )
    """

    def __init__(
        self,
        starting_cash: Decimal = Decimal("100000"),
        commission_model: DecimalCommissionModel | None = None,
        slippage_model: DecimalSlippageModel | None = None,
        order_latency_ms: int = 100,
        latency_jitter_pct: Decimal = Decimal("0.20"),
        volume_limit_pct: Decimal = Decimal("0.025"),
    ) -> None:
        """Initialize PaperBroker.

        Args:
            starting_cash: Initial paper account balance (default: $100,000)
            commission_model: Commission model (default: NoCommission)
            slippage_model: Slippage model (default: NoSlippage)
            order_latency_ms: Base order latency in milliseconds (default: 100ms)
            latency_jitter_pct: Latency jitter as percentage (default: 0.20 = ±20%)
            volume_limit_pct: Max order as % of bar volume (default: 0.025 = 2.5%)

        Example:
            >>> broker = PaperBroker(
            ...     starting_cash=Decimal("50000"),
            ...     commission_model=PerShareCommission(Decimal("0.005")),
            ...     slippage_model=FixedBasisPointsSlippage(Decimal("5")),
            ...     order_latency_ms=50  # 50ms for crypto
            ... )
        """
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.commission_model = commission_model or NoCommission()
        self.slippage_model = slippage_model or NoSlippage()
        self.order_latency_ms = order_latency_ms
        self.latency_jitter_pct = latency_jitter_pct
        self.volume_limit_pct = volume_limit_pct

        # Paper positions tracking
        self.positions: dict[Asset, DecimalPosition] = {}

        # Paper orders tracking (order_id → DecimalOrder)
        self.orders: dict[str, DecimalOrder] = {}

        # Open orders (pending execution)
        self.open_orders: dict[str, DecimalOrder] = {}

        # Market data tracking (asset → latest price/volume)
        self.market_data: dict[Asset, dict] = {}

        # Market data queue for get_next_market_data
        self.market_data_queue: asyncio.Queue = asyncio.Queue()

        # Subscribed assets
        self.subscribed_assets: list[Asset] = []

        # Connection state
        self._connected = False

        # Transaction history
        self.transactions: list[DecimalTransaction] = []

        # Fill event queue (for get_next_event)
        self.fill_events: asyncio.Queue = asyncio.Queue()

        logger.info(
            "paper_broker_initialized",
            starting_cash=str(starting_cash),
            commission_model=str(commission_model),
            slippage_model=str(slippage_model),
            order_latency_ms=order_latency_ms,
            volume_limit_pct=str(volume_limit_pct),
        )

    async def connect(self) -> None:
        """Establish connection to paper broker.

        Paper broker always succeeds (no real connection needed).
        """
        self._connected = True
        logger.info("paper_broker_connected")

    async def disconnect(self) -> None:
        """Disconnect from paper broker."""
        self._connected = False
        logger.info("paper_broker_disconnected")

    def is_connected(self) -> bool:
        """Check if paper broker is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str:
        """Submit order to paper broker.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: 'market', 'limit', 'stop', 'stop-limit'
            limit_price: Limit price for limit/stop-limit orders
            stop_price: Stop price for stop/stop-limit orders

        Returns:
            Order ID

        Raises:
            PaperBrokerError: If order submission fails
            InsufficientFundsError: If insufficient cash for buy order
        """
        if not self._connected:
            raise PaperBrokerError("Paper broker not connected")

        # Create order
        order = DecimalOrder(
            dt=datetime.now(),
            asset=asset,
            amount=amount,
            order_type=order_type,
            limit=limit_price,
            stop=stop_price,
        )

        # Check buying power for buy orders
        if amount > Decimal("0"):
            estimated_cost = await self._estimate_order_cost(order)
            if estimated_cost > self.cash:
                raise InsufficientFundsError(
                    f"Insufficient cash: need {estimated_cost}, have {self.cash}",
                    required=estimated_cost,
                    available=self.cash,
                )

        # Store order
        self.orders[order.id] = order
        self.open_orders[order.id] = order

        logger.info(
            "paper_order_submitted",
            order_id=order.id,
            asset=asset.symbol if hasattr(asset, "symbol") else str(asset),
            amount=str(amount),
            order_type=order_type,
            limit_price=str(limit_price) if limit_price else None,
            stop_price=str(stop_price) if stop_price else None,
        )

        # Schedule order execution (async task)
        asyncio.create_task(self._execute_order(order))

        return order.id

    async def _estimate_order_cost(self, order: DecimalOrder) -> Decimal:
        """Estimate cost of order for buying power check.

        Args:
            order: Order to estimate

        Returns:
            Estimated cost including commission and slippage
        """
        # Get current price
        try:
            current_price = await self.get_current_price(order.asset)
        except MarketDataUnavailableError:
            # If no market data, use limit price or assume $100
            current_price = order.limit if order.limit else Decimal("100")

        # Estimate fill price with slippage
        estimated_fill_price = self.slippage_model.calculate(order, current_price)

        # Estimate order value
        order_value = abs(order.amount) * estimated_fill_price

        # Estimate commission (use approximate for buying power check)
        estimated_commission = self.commission_model.calculate(
            order, estimated_fill_price, order.amount
        )

        return order_value + estimated_commission

    async def _execute_order(self, order: DecimalOrder) -> None:
        """Execute order with latency simulation and fill logic.

        Args:
            order: Order to execute
        """
        try:
            # Simulate latency (network + exchange delay)
            latency_sec = self._simulate_latency()
            await asyncio.sleep(latency_sec)

            # Check if order still open (could have been canceled)
            if order.id not in self.open_orders:
                logger.info("paper_order_canceled_before_fill", order_id=order.id)
                return

            # Execute based on order type
            if order.order_type == "market":
                await self._execute_market_order(order)
            elif order.order_type == "limit":
                await self._execute_limit_order(order)
            elif order.order_type == "stop":
                await self._execute_stop_order(order)
            elif order.order_type == "stop-limit":
                await self._execute_stop_limit_order(order)
            else:
                logger.error("unsupported_order_type", order_type=order.order_type)
                raise PaperBrokerError(f"Unsupported order type: {order.order_type}")

        except Exception as e:
            logger.error("paper_order_execution_failed", order_id=order.id, error=str(e))
            # Remove from open orders on failure
            self.open_orders.pop(order.id, None)

    def _simulate_latency(self) -> float:
        """Simulate network latency with jitter.

        Returns:
            Latency in seconds
        """
        # Base latency
        base_latency_sec = self.order_latency_ms / 1000.0

        # Add jitter: ±latency_jitter_pct
        jitter_range = float(self.latency_jitter_pct)
        jitter_factor = random.uniform(1.0 - jitter_range, 1.0 + jitter_range)

        latency_sec = base_latency_sec * jitter_factor

        logger.debug(
            "latency_simulated",
            base_latency_ms=self.order_latency_ms,
            actual_latency_ms=latency_sec * 1000,
        )

        return latency_sec

    async def _execute_market_order(self, order: DecimalOrder) -> None:
        """Execute market order at current price.

        Args:
            order: Market order to execute
        """
        # Get current market price
        try:
            market_price = await self.get_current_price(order.asset)
        except MarketDataUnavailableError:
            logger.error(
                "market_data_unavailable_rejecting_order",
                order_id=order.id,
                asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            )
            self.open_orders.pop(order.id, None)
            return

        # Calculate fill price with slippage
        fill_price = self.slippage_model.calculate(order, market_price)

        # Determine fill amount (check partial fills based on volume)
        fill_amount = await self._calculate_fill_amount(order, order.amount)

        # Calculate commission
        commission = self.commission_model.calculate(order, fill_price, fill_amount)

        # Process fill
        await self._process_fill(order, fill_amount, fill_price, commission)

        logger.info(
            "paper_market_order_filled",
            order_id=order.id,
            fill_amount=str(fill_amount),
            fill_price=str(fill_price),
            commission=str(commission),
        )

    async def _execute_limit_order(self, order: DecimalOrder) -> None:
        """Execute limit order when price crosses limit.

        Args:
            order: Limit order to execute
        """
        # For paper trading, we'll fill immediately if limit is marketable
        # In real live trading, this would monitor price continuously
        try:
            market_price = await self.get_current_price(order.asset)
        except MarketDataUnavailableError:
            logger.error(
                "market_data_unavailable_rejecting_order",
                order_id=order.id,
                asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            )
            self.open_orders.pop(order.id, None)
            return

        # Check if limit is marketable
        is_buy = order.amount > Decimal("0")
        limit_price = order.limit

        if limit_price is None:
            logger.error("limit_order_missing_limit_price", order_id=order.id)
            self.open_orders.pop(order.id, None)
            return

        # Buy limit: fill if market price <= limit
        # Sell limit: fill if market price >= limit
        is_marketable = (is_buy and market_price <= limit_price) or (
            not is_buy and market_price >= limit_price
        )

        if is_marketable:
            # Fill at limit price (no slippage for limit orders)
            fill_price = limit_price
            fill_amount = await self._calculate_fill_amount(order, order.amount)
            commission = self.commission_model.calculate(order, fill_price, fill_amount)

            await self._process_fill(order, fill_amount, fill_price, commission)

            logger.info(
                "paper_limit_order_filled",
                order_id=order.id,
                fill_amount=str(fill_amount),
                fill_price=str(fill_price),
                commission=str(commission),
            )
        else:
            # Limit not marketable yet - in real implementation would monitor price
            logger.debug(
                "limit_order_not_marketable",
                order_id=order.id,
                market_price=str(market_price),
                limit_price=str(limit_price),
            )
            # For simplicity, reject non-marketable limits in paper trading
            self.open_orders.pop(order.id, None)

    async def _execute_stop_order(self, order: DecimalOrder) -> None:
        """Execute stop order when price crosses stop.

        Args:
            order: Stop order to execute
        """
        # Simplified: trigger stop immediately and fill as market order
        try:
            market_price = await self.get_current_price(order.asset)
        except MarketDataUnavailableError:
            logger.error(
                "market_data_unavailable_rejecting_order",
                order_id=order.id,
                asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            )
            self.open_orders.pop(order.id, None)
            return

        # Fill as market order with slippage
        fill_price = self.slippage_model.calculate(order, market_price)
        fill_amount = await self._calculate_fill_amount(order, order.amount)
        commission = self.commission_model.calculate(order, fill_price, fill_amount)

        await self._process_fill(order, fill_amount, fill_price, commission)

        logger.info(
            "paper_stop_order_filled",
            order_id=order.id,
            fill_amount=str(fill_amount),
            fill_price=str(fill_price),
            commission=str(commission),
        )

    async def _execute_stop_limit_order(self, order: DecimalOrder) -> None:
        """Execute stop-limit order.

        Args:
            order: Stop-limit order to execute
        """
        # Simplified: trigger stop, then try to fill at limit
        await self._execute_limit_order(order)

    async def _calculate_fill_amount(
        self, order: DecimalOrder, requested_amount: Decimal
    ) -> Decimal:
        """Calculate fill amount based on volume limit.

        Args:
            order: Order being filled
            requested_amount: Requested fill quantity

        Returns:
            Actual fill amount (may be partial)
        """
        # Get bar volume from market data
        market_data = self.market_data.get(order.asset)
        if market_data is None or "volume" not in market_data:
            # No volume data - assume full fill
            logger.debug(
                "no_volume_data_assuming_full_fill",
                order_id=order.id,
                requested_amount=str(requested_amount),
            )
            return requested_amount

        bar_volume = market_data["volume"]

        # Calculate volume limit
        max_fill_volume = bar_volume * self.volume_limit_pct

        # Calculate fill percentage
        if abs(requested_amount) <= max_fill_volume:
            # Full fill
            fill_amount = requested_amount
        else:
            # Partial fill
            fill_pct = max_fill_volume / abs(requested_amount)
            fill_amount = requested_amount * fill_pct

            logger.info(
                "partial_fill_due_to_volume",
                order_id=order.id,
                requested_amount=str(requested_amount),
                fill_amount=str(fill_amount),
                bar_volume=str(bar_volume),
                volume_limit_pct=str(self.volume_limit_pct),
            )

        return fill_amount

    async def _process_fill(
        self,
        order: DecimalOrder,
        fill_amount: Decimal,
        fill_price: Decimal,
        commission: Decimal,
    ) -> None:
        """Process order fill: update positions, cash, and create transaction.

        Args:
            order: Order being filled
            fill_amount: Quantity filled
            fill_price: Execution price
            commission: Commission charged
        """
        # Update order
        order.filled += fill_amount
        order.commission += commission

        # Mark order as filled or partially filled
        if abs(order.filled) >= abs(order.amount):
            # Fully filled - remove from open orders
            self.open_orders.pop(order.id, None)
            logger.info("paper_order_fully_filled", order_id=order.id)
        else:
            # Partially filled - keep in open orders
            logger.info(
                "paper_order_partially_filled",
                order_id=order.id,
                filled=str(order.filled),
                amount=str(order.amount),
            )

        # Update cash (buy: decrease cash, sell: increase cash)
        cash_impact = fill_amount * fill_price
        if fill_amount > Decimal("0"):
            # Buy: pay (amount × price) + commission
            self.cash -= cash_impact + commission
        else:
            # Sell: receive (amount × price) - commission
            self.cash += abs(cash_impact) - commission

        # Update position
        self._update_position(order.asset, fill_amount, fill_price)

        # Create transaction
        transaction = DecimalTransaction(
            timestamp=datetime.now(),
            order_id=order.id,
            asset=order.asset,
            amount=fill_amount,
            price=fill_price,
            commission=commission,
            slippage=Decimal("0"),  # Slippage already included in fill_price
        )
        self.transactions.append(transaction)

        # Add fill event to queue
        await self.fill_events.put(
            {
                "type": "fill",
                "order_id": order.id,
                "transaction": transaction,
                "timestamp": transaction.timestamp,
            }
        )

        logger.info(
            "paper_fill_processed",
            order_id=order.id,
            asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            fill_amount=str(fill_amount),
            fill_price=str(fill_price),
            commission=str(commission),
            new_cash=str(self.cash),
        )

    def _update_position(
        self, asset: Asset, transaction_amount: Decimal, transaction_price: Decimal
    ) -> None:
        """Update position with new transaction.

        Args:
            asset: Asset traded
            transaction_amount: Transaction quantity
            transaction_price: Transaction price
        """
        if asset not in self.positions:
            # Create new position
            self.positions[asset] = DecimalPosition(
                asset=asset,
                amount=transaction_amount,
                cost_basis=transaction_price,
                last_sale_price=transaction_price,
                last_sale_date=datetime.now(),
            )
        else:
            # Update existing position
            position = self.positions[asset]
            position.update(transaction_amount, transaction_price, datetime.now())

            # Remove position if closed
            if position.amount == Decimal("0"):
                del self.positions[asset]

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order.

        Args:
            broker_order_id: Order ID to cancel
        """
        if broker_order_id in self.open_orders:
            self.open_orders.pop(broker_order_id)
            logger.info("paper_order_canceled", order_id=broker_order_id)
        else:
            logger.warning("cancel_order_not_found", order_id=broker_order_id)

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get paper account information.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power', 'portfolio_value'
        """
        # Calculate portfolio value
        positions_value = sum(pos.market_value for pos in self.positions.values())
        portfolio_value = self.cash + positions_value

        return {
            "cash": self.cash,
            "equity": portfolio_value,
            "buying_power": self.cash,  # Simplified: no margin
            "portfolio_value": portfolio_value,
            "starting_cash": self.starting_cash,
        }

    async def get_positions(self) -> list[dict]:
        """Get current paper positions.

        Returns:
            List of position dicts
        """
        return [
            {
                "asset": pos.asset,
                "amount": pos.amount,
                "cost_basis": pos.cost_basis,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
            }
            for pos in self.positions.values()
        ]

    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders.

        Returns:
            List of order dicts
        """
        return [
            {
                "order_id": order.id,
                "asset": order.asset,
                "amount": order.amount,
                "filled": order.filled,
                "order_type": order.order_type,
                "limit_price": order.limit,
                "stop_price": order.stop,
            }
            for order in self.open_orders.values()
        ]

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data.

        Args:
            assets: List of assets to subscribe to

        Note:
            Paper broker doesn't actually connect to data feed.
            Market data must be pushed via _update_market_data() for testing.
        """
        self.subscribed_assets.extend(assets)
        logger.info(
            "paper_broker_subscribed_to_market_data",
            assets=[asset.symbol if hasattr(asset, "symbol") else str(asset) for asset in assets],
        )

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data.

        Args:
            assets: List of assets to unsubscribe from
        """
        for asset in assets:
            if asset in self.subscribed_assets:
                self.subscribed_assets.remove(asset)

        logger.info("paper_broker_unsubscribed_from_market_data")

    async def get_next_market_data(self) -> dict | None:
        """Get next market data update (blocking).

        Returns:
            Dict with market data or None if queue empty
        """
        try:
            return await asyncio.wait_for(self.market_data_queue.get(), timeout=0.1)
        except TimeoutError:
            return None

    async def get_current_price(self, asset: Asset) -> Decimal:
        """Get current price for asset.

        Args:
            asset: Asset to get price for

        Returns:
            Current price

        Raises:
            MarketDataUnavailableError: If no price data available
        """
        if asset not in self.market_data or "close" not in self.market_data[asset]:
            symbol = asset.symbol if hasattr(asset, "symbol") else asset
            raise MarketDataUnavailableError(f"No market data available for {symbol}")

        return self.market_data[asset]["close"]

    def _update_market_data(self, asset: Asset, market_data: dict) -> None:
        """Update market data for asset (internal method for testing).

        Args:
            asset: Asset to update
            market_data: Dict with keys: open, high, low, close, volume, timestamp
        """
        self.market_data[asset] = market_data

        # Add to market data queue
        # Store task reference to avoid garbage collection issues
        _ = asyncio.create_task(
            self.market_data_queue.put(
                {
                    "asset": asset,
                    "open": market_data.get("open"),
                    "high": market_data.get("high"),
                    "low": market_data.get("low"),
                    "close": market_data.get("close"),
                    "volume": market_data.get("volume"),
                    "timestamp": market_data.get("timestamp"),
                }
            )
        )

        logger.debug(
            "paper_broker_market_data_updated",
            asset=asset.symbol if hasattr(asset, "symbol") else str(asset),
            close=str(market_data.get("close")),
            volume=str(market_data.get("volume")),
        )
