"""Decimal-based order management blotter for RustyBT.

This module provides DecimalBlotter, a Decimal-precision order execution
and management system.
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

import structlog

from rustybt.assets import Asset
from rustybt.finance.decimal.commission import DecimalCommissionModel, NoCommission
from rustybt.finance.decimal.config import DecimalConfig
from rustybt.finance.decimal.order import DecimalOrder, InvalidQuantityError
from rustybt.finance.decimal.slippage import DecimalSlippageModel, NoSlippage
from rustybt.finance.decimal.transaction import DecimalTransaction, create_decimal_transaction

logger = structlog.get_logger(__name__)


class DecimalBlotter:
    """Order management system with Decimal precision.

    The blotter manages the order lifecycle:
    1. Accept order submissions
    2. Execute orders against market data
    3. Calculate commission and slippage
    4. Create transaction records
    5. Update ledger with fills

    Example:
        >>> blotter = DecimalBlotter(
        ...     commission_model=PerShareCommission(Decimal("0.005")),
        ...     slippage_model=FixedBasisPointsSlippage(Decimal("10"))
        ... )
        >>> order_id = blotter.order(
        ...     asset=equity_asset,
        ...     amount=Decimal("100"),
        ...     order_type="market"
        ... )
    """

    def __init__(
        self,
        commission_model: DecimalCommissionModel | None = None,
        slippage_model: DecimalSlippageModel | None = None,
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize DecimalBlotter.

        Args:
            commission_model: Commission model (defaults to NoCommission)
            slippage_model: Slippage model (defaults to NoSlippage)
            config: DecimalConfig instance (uses default if None)
        """
        self.commission_model = commission_model or NoCommission()
        self.slippage_model = slippage_model or NoSlippage()
        self.config = config or DecimalConfig.get_instance()

        # Order tracking
        self.open_orders: dict[Asset, list[DecimalOrder]] = defaultdict(list)
        self.orders: dict[str, DecimalOrder] = {}
        self.new_orders: list[DecimalOrder] = []

        # Transactions history
        self.transactions: list[DecimalTransaction] = []

        # Current datetime
        self.current_dt: datetime | None = None

        logger.info(
            "decimal_blotter_initialized",
            commission_model=str(self.commission_model),
            slippage_model=str(self.slippage_model),
        )

    def set_current_dt(self, dt: datetime) -> None:
        """Set current datetime for order processing.

        Args:
            dt: Current datetime
        """
        self.current_dt = dt

    def order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str = "market",
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
        order_id: str | None = None,
    ) -> str:
        """Submit an order.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: Order type (market, limit, stop, stop_limit)
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            order_id: Optional custom order ID

        Returns:
            Order ID

        Raises:
            InvalidQuantityError: If amount is zero
            OrderError: If order parameters are invalid
        """
        if amount == Decimal("0"):
            raise InvalidQuantityError("Order amount cannot be zero")

        # Create order
        order = DecimalOrder(
            dt=self.current_dt,
            asset=asset,
            amount=amount,
            order_type=order_type,
            stop=stop_price,
            limit=limit_price,
            id=order_id,
            config=self.config,
        )

        # Track order
        self.open_orders[asset].append(order)
        self.orders[order.id] = order
        self.new_orders.append(order)

        logger.info(
            "order_submitted",
            order_id=order.id,
            asset=str(asset),
            amount=str(amount),
            order_type=order_type,
        )

        return order.id

    def cancel_order(self, order_id: str) -> None:
        """Cancel an open order.

        Args:
            order_id: Order ID to cancel

        Raises:
            KeyError: If order not found
        """
        if order_id not in self.orders:
            raise KeyError(f"Order {order_id} not found")

        order = self.orders[order_id]

        if order.open:
            # Remove from open orders
            order_list = self.open_orders[order.asset]
            if order in order_list:
                order_list.remove(order)

            # Cancel order
            order.cancel()
            order.dt = self.current_dt

            # Track cancellation
            self.new_orders.append(order)

            logger.info("order_cancelled", order_id=order_id)

    def process_order(
        self,
        order: DecimalOrder,
        market_price: Decimal,
        fill_amount: Decimal | None = None,
    ) -> DecimalTransaction | None:
        """Process order execution.

        Args:
            order: Order to process
            market_price: Current market price
            fill_amount: Amount to fill (None = fill complete order)

        Returns:
            DecimalTransaction if order filled, None otherwise

        Raises:
            ValueError: If fill_amount exceeds remaining order quantity
        """
        # Check if order is triggered
        order.check_triggers(market_price, self.current_dt)
        if not order.triggered:
            logger.debug("order_not_triggered", order_id=order.id)
            return None

        # Determine fill amount
        if fill_amount is None:
            fill_amount = order.remaining
        else:
            if abs(fill_amount) > abs(order.remaining):
                raise ValueError(f"Fill amount {fill_amount} exceeds remaining {order.remaining}")

        # Calculate execution price with slippage
        execution_price = self.slippage_model.calculate(order, market_price)

        # Calculate commission
        commission = self.commission_model.calculate(order, execution_price, fill_amount)

        # Create transaction
        transaction = create_decimal_transaction(
            order_id=order.id,
            asset=order.asset,
            dt=self.current_dt,
            price=execution_price,
            amount=fill_amount,
            commission=commission,
            slippage=abs(execution_price - market_price) * abs(fill_amount),
        )

        # Update order
        self._update_order_on_fill(order, fill_amount, execution_price, commission)

        # Track transaction
        self.transactions.append(transaction)

        logger.info(
            "order_filled",
            order_id=order.id,
            fill_amount=str(fill_amount),
            execution_price=str(execution_price),
            commission=str(commission),
            total_cost=str(transaction.total_cost),
        )

        return transaction

    def process_partial_fill(
        self,
        order: DecimalOrder,
        fill_amount: Decimal,
        fill_price: Decimal,
    ) -> DecimalTransaction:
        """Process partial order fill.

        Args:
            order: Order to fill partially
            fill_amount: Amount to fill
            fill_price: Execution price

        Returns:
            DecimalTransaction for the partial fill

        Raises:
            ValueError: If fill_amount exceeds remaining quantity
        """
        if abs(fill_amount) > abs(order.remaining):
            raise ValueError(f"Fill amount {fill_amount} exceeds remaining {order.remaining}")

        # Calculate commission for this fill
        commission = self.commission_model.calculate(order, fill_price, fill_amount)

        # Create transaction
        transaction = create_decimal_transaction(
            order_id=order.id,
            asset=order.asset,
            dt=self.current_dt,
            price=fill_price,
            amount=fill_amount,
            commission=commission,
        )

        # Update order with partial fill
        self._update_order_on_fill(order, fill_amount, fill_price, commission)

        # Track transaction
        self.transactions.append(transaction)

        logger.info(
            "partial_fill_processed",
            order_id=order.id,
            fill_amount=str(fill_amount),
            fill_price=str(fill_price),
            remaining=str(order.remaining),
        )

        return transaction

    def _update_order_on_fill(
        self,
        order: DecimalOrder,
        fill_amount: Decimal,
        fill_price: Decimal,
        commission: Decimal,
    ) -> None:
        """Update order state after fill.

        Args:
            order: Order to update
            fill_amount: Amount filled
            fill_price: Execution price
            commission: Commission charged
        """
        # Update filled amount
        previous_filled = order.filled
        order.filled += fill_amount

        # Update average fill price
        if order.filled_price is None:
            order.filled_price = fill_price
        else:
            # Weighted average: (old_value + new_value) / total_filled
            old_value = previous_filled * order.filled_price
            new_value = fill_amount * fill_price
            order.filled_price = (old_value + new_value) / order.filled

        # Update commission
        order.commission += commission

        # Update order timestamp
        order.dt = self.current_dt

        # Remove from open orders if fully filled
        if order.remaining == Decimal("0"):
            order_list = self.open_orders[order.asset]
            if order in order_list:
                order_list.remove(order)

            logger.info("order_fully_filled", order_id=order.id)

    def get_order(self, order_id: str) -> DecimalOrder | None:
        """Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            DecimalOrder if found, None otherwise
        """
        return self.orders.get(order_id)

    def get_open_orders(self, asset: Asset | None = None) -> list[DecimalOrder]:
        """Get open orders.

        Args:
            asset: Filter by asset (None = all assets)

        Returns:
            List of open orders
        """
        if asset is not None:
            return list(self.open_orders.get(asset, []))
        else:
            all_orders = []
            for orders in self.open_orders.values():
                all_orders.extend(orders)
            return all_orders

    def get_transactions(self) -> list[DecimalTransaction]:
        """Get all transactions.

        Returns:
            List of all transactions
        """
        return list(self.transactions)

    def __repr__(self) -> str:
        """String representation of blotter.

        Returns:
            String representation
        """
        return (
            f"DecimalBlotter("
            f"commission_model={self.commission_model}, "
            f"slippage_model={self.slippage_model}, "
            f"open_orders={len(self.get_open_orders())}, "
            f"total_orders={len(self.orders)})"
        )
