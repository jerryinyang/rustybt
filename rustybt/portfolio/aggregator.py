"""Order Aggregation Engine for Multi-Strategy Portfolios.

This module provides order aggregation and netting capabilities to minimize
transaction costs by combining offsetting orders across multiple strategies
before execution.

Classes:
    OrderDirection: Enum for buy/sell direction
    OrderContribution: Tracks individual strategy contribution to aggregated order
    AggregatedOrder: Aggregated order combining multiple strategy orders
    NetOrderResult: Result of order netting operation with savings tracking
    OrderAggregator: Main aggregation engine with netting and fill allocation

Example:
    >>> from rustybt.portfolio.aggregator import OrderAggregator
    >>> aggregator = OrderAggregator()
    >>>
    >>> # Collect orders from multiple strategies
    >>> orders = {
    ...     "momentum": [buy_order_100],
    ...     "mean_reversion": [sell_order_50],
    ...     "trend": [buy_order_30]
    ... }
    >>>
    >>> # Aggregate with netting
    >>> result = aggregator.aggregate_orders(orders)
    >>> # Net: 100 - 50 + 30 = 80 shares (buy)
    >>> # Commission savings: ~70%
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


class OrderDirection(Enum):
    """Order direction (buy/sell)."""

    BUY = "buy"
    SELL = "sell"


@dataclass
class OrderContribution:
    """Contribution from a single strategy to aggregated order.

    Tracks:
    - Which strategy contributed
    - Original order details
    - Contribution amount (signed: positive = buy, negative = sell)
    - Contribution percentage of total

    Attributes:
        strategy_id: Unique identifier for contributing strategy
        original_order: Original order object from strategy
        contribution_amount: Signed amount (+ for buy, - for sell)
        contribution_pct: Percentage of total contribution (0-1)
    """

    strategy_id: str
    original_order: Any  # Order object
    contribution_amount: Decimal  # Signed amount
    contribution_pct: Decimal = field(default=Decimal("0"))  # % of total contribution

    @property
    def direction(self) -> OrderDirection:
        """Get order direction from contribution amount.

        Returns:
            OrderDirection.BUY if contribution_amount > 0, else SELL
        """
        return OrderDirection.BUY if self.contribution_amount > 0 else OrderDirection.SELL

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"OrderContribution(strategy={self.strategy_id}, "
            f"amount={self.contribution_amount}, "
            f"direction={self.direction.value})"
        )


@dataclass
class AggregatedOrder:
    """Aggregated order combining multiple strategy orders.

    Example Netting:
        Strategy A: Buy 100 AAPL @ Market
        Strategy B: Sell 50 AAPL @ Market
        Strategy C: Buy 30 AAPL @ Market

        Aggregated Result:
        - Net amount: +80 AAPL (100 - 50 + 30)
        - Direction: BUY
        - Contributions: [A: +100, B: -50, C: +30]

    Attributes:
        asset: Asset being traded
        net_amount: Signed net amount (positive = buy, negative = sell)
        order_type: Order type ("market" or "limit")
        limit_price: Limit price for limit orders
        contributions: List of strategy contributions
        created_at: Order creation timestamp
        original_commission: Commission without aggregation
        aggregated_commission: Commission with aggregation
        commission_savings: Savings from aggregation
    """

    asset: Any  # Asset object
    net_amount: Decimal  # Signed net amount (positive = buy, negative = sell)
    order_type: str  # "market" or "limit"
    limit_price: Decimal | None = None
    contributions: list[OrderContribution] = field(default_factory=list)
    created_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)

    # Savings tracking
    original_commission: Decimal = field(default=Decimal("0"))
    aggregated_commission: Decimal = field(default=Decimal("0"))
    commission_savings: Decimal = field(default=Decimal("0"))

    @property
    def direction(self) -> OrderDirection | None:
        """Get net order direction.

        Returns:
            OrderDirection.BUY if net positive, SELL if negative, None if fully netted
        """
        if self.net_amount > Decimal("0"):
            return OrderDirection.BUY
        elif self.net_amount < Decimal("0"):
            return OrderDirection.SELL
        return None  # Fully netted

    @property
    def is_fully_netted(self) -> bool:
        """Check if order is fully netted (net = 0).

        Returns:
            True if net_amount is zero
        """
        return self.net_amount == Decimal("0")

    @property
    def num_strategies(self) -> int:
        """Number of strategies contributing to this order.

        Returns:
            Count of contributing strategies
        """
        return len(self.contributions)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging.

        Returns:
            Dictionary representation with formatted values
        """
        return {
            "asset": self.asset.symbol if hasattr(self.asset, "symbol") else str(self.asset),
            "net_amount": str(self.net_amount),
            "direction": self.direction.value if self.direction else "NETTED",
            "order_type": self.order_type,
            "limit_price": str(self.limit_price) if self.limit_price else None,
            "num_strategies": self.num_strategies,
            "original_commission": f"${float(self.original_commission):.2f}",
            "aggregated_commission": f"${float(self.aggregated_commission):.2f}",
            "commission_savings": f"${float(self.commission_savings):.2f}",
            "savings_pct": (
                f"{float(self.commission_savings / self.original_commission * 100):.1f}%"
                if self.original_commission > 0
                else "N/A"
            ),
        }


@dataclass
class NetOrderResult:
    """Result of order netting operation.

    Tracks:
    - Original orders processed
    - Aggregated orders created
    - Fully netted orders (cancelled)
    - Total commission savings

    Attributes:
        original_orders_count: Number of original orders before aggregation
        aggregated_orders: List of aggregated orders to execute
        fully_netted_count: Number of orders fully netted (cancelled)
        total_original_commission: Total commission without aggregation
        total_aggregated_commission: Total commission with aggregation
        total_savings: Total commission savings
    """

    original_orders_count: int
    aggregated_orders: list[AggregatedOrder]
    fully_netted_count: int
    total_original_commission: Decimal
    total_aggregated_commission: Decimal
    total_savings: Decimal

    @property
    def savings_pct(self) -> Decimal:
        """Calculate savings percentage.

        Returns:
            Percentage of commission saved (0-100)
        """
        if self.total_original_commission > Decimal("0"):
            return (self.total_savings / self.total_original_commission) * Decimal("100")
        return Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging.

        Returns:
            Dictionary representation with formatted values
        """
        return {
            "original_orders": self.original_orders_count,
            "aggregated_orders": len(self.aggregated_orders),
            "fully_netted": self.fully_netted_count,
            "total_original_commission": f"${float(self.total_original_commission):.2f}",
            "total_aggregated_commission": f"${float(self.total_aggregated_commission):.2f}",
            "total_savings": f"${float(self.total_savings):.2f}",
            "savings_pct": f"{float(self.savings_pct):.1f}%",
        }


class OrderAggregator:
    """Order aggregation engine for multi-strategy portfolios.

    Aggregation Algorithm:
    =====================

    1. Order Collection:
       - Collect all orders from strategies at execution point
       - Group orders by (asset, order_type, limit_price)
       - Only compatible orders can be aggregated

    2. Netting Calculation:
       - For each group, sum amounts (buy = +, sell = -)
       - Net amount = Σ(buy amounts) - Σ(sell amounts)
       - If net = 0: fully netted, cancel all orders
       - If net ≠ 0: create aggregated order with net amount

    3. Fill Allocation:
       - Proportional to contribution: fill_i = net_fill * (contribution_i / total_contribution)
       - Preserve direction: buy contributions get buys, sell get sells
       - Handle rounding with Decimal precision

    4. Commission Savings:
       - Before: Σ(commission per order)
       - After: commission(net_order)
       - Savings: before - after

    Netting Examples:
    ================

    Example 1: Simple 2-Strategy Netting
    -------------------------------------
    Strategy A: Buy 100 AAPL @ Market
    Strategy B: Sell 50 AAPL @ Market

    Net = +100 - 50 = +50 (Buy)
    Aggregated order: Buy 50 AAPL @ Market

    Example 2: Complex 3-Strategy Netting
    --------------------------------------
    Strategy A: Buy 100 AAPL @ Market
    Strategy B: Sell 80 AAPL @ Market
    Strategy C: Buy 30 AAPL @ Market

    Net = +100 - 80 + 30 = +50 (Buy)
    Aggregated order: Buy 50 AAPL @ Market

    Example 3: Full Netting (Zero Net)
    -----------------------------------
    Strategy A: Buy 100 AAPL @ Market
    Strategy B: Sell 100 AAPL @ Market

    Net = +100 - 100 = 0
    Result: Both orders cancelled, no execution needed

    Compatibility Rules:
    ===================
    Orders can be aggregated if:
    1. Same asset
    2. Same order type (Market or Limit)
    3. If Limit: same limit price
    4. Same execution timeframe (same bar)

    Orders CANNOT be aggregated if:
    - Different assets (AAPL vs GOOGL)
    - Different order types (Market vs Limit)
    - Different limit prices
    - Different execution times
    """

    def __init__(
        self,
        commission_model: Any | None = None,  # noqa: ANN401
        limit_price_tolerance: Decimal | None = None,
    ):
        """Initialize order aggregator.

        Args:
            commission_model: Commission model for savings calculation
            limit_price_tolerance: Tolerance for limit price matching (e.g., 0.01 = 1%)
        """
        self.commission_model = commission_model
        self.limit_price_tolerance = limit_price_tolerance

        # Statistics
        self.total_orders_processed = 0
        self.total_orders_aggregated = 0
        self.total_orders_netted = 0
        self.cumulative_savings = Decimal("0")

        logger.info(
            "order_aggregator_initialized",
            has_commission_model=commission_model is not None,
            limit_price_tolerance=str(limit_price_tolerance) if limit_price_tolerance else None,
        )

    def aggregate_orders(
        self,
        orders: dict[str, list[Any]],  # {strategy_id: [Order, ...]}
    ) -> NetOrderResult:
        """Aggregate orders across strategies with netting.

        Args:
            orders: Dict mapping strategy_id to list of orders

        Returns:
            NetOrderResult with aggregated orders and savings
        """
        # Track original order count
        original_count = sum(len(order_list) for order_list in orders.values())
        self.total_orders_processed += original_count

        if original_count == 0:
            logger.debug("no_orders_to_aggregate")
            return NetOrderResult(
                original_orders_count=0,
                aggregated_orders=[],
                fully_netted_count=0,
                total_original_commission=Decimal("0"),
                total_aggregated_commission=Decimal("0"),
                total_savings=Decimal("0"),
            )

        # Group orders by compatibility
        order_groups = self._group_orders(orders)

        logger.info("orders_grouped", original_orders=original_count, num_groups=len(order_groups))

        # Aggregate each group
        aggregated_orders = []
        fully_netted_count = 0
        total_original_commission = Decimal("0")
        total_aggregated_commission = Decimal("0")

        for group_key, order_list in order_groups.items():
            asset, order_type, limit_price = group_key

            # Calculate net amount
            net_amount = self._calculate_net_amount(order_list)

            # Create order contributions
            contributions = self._create_contributions(order_list, net_amount)

            # Calculate commissions
            original_comm = self._calculate_original_commission(order_list)
            total_original_commission += original_comm

            if net_amount == Decimal("0"):
                # Fully netted - cancel all orders
                fully_netted_count += len(order_list)
                self.total_orders_netted += len(order_list)

                logger.info(
                    "orders_fully_netted",
                    asset=asset.symbol if hasattr(asset, "symbol") else str(asset),
                    num_orders=len(order_list),
                    commission_saved=f"${float(original_comm):.2f}",
                )

                # Create aggregated order record (for tracking, even though net = 0)
                agg_order = AggregatedOrder(
                    asset=asset,
                    net_amount=Decimal("0"),
                    order_type=order_type,
                    limit_price=limit_price,
                    contributions=contributions,
                    original_commission=original_comm,
                    aggregated_commission=Decimal("0"),
                    commission_savings=original_comm,  # 100% savings
                )
                aggregated_orders.append(agg_order)

            else:
                # Partial or no netting - execute net order
                aggregated_comm = self._calculate_aggregated_commission(
                    asset, abs(net_amount), order_type
                )
                total_aggregated_commission += aggregated_comm

                savings = original_comm - aggregated_comm
                self.cumulative_savings += savings

                # Create aggregated order
                agg_order = AggregatedOrder(
                    asset=asset,
                    net_amount=net_amount,
                    order_type=order_type,
                    limit_price=limit_price,
                    contributions=contributions,
                    original_commission=original_comm,
                    aggregated_commission=aggregated_comm,
                    commission_savings=savings,
                )
                aggregated_orders.append(agg_order)

                self.total_orders_aggregated += 1

                logger.info(
                    "orders_aggregated",
                    asset=asset.symbol if hasattr(asset, "symbol") else str(asset),
                    original_orders=len(order_list),
                    net_amount=str(net_amount),
                    direction=agg_order.direction.value if agg_order.direction else "NETTED",
                    commission_savings=f"${float(savings):.2f}",
                    savings_pct=(
                        f"{float(savings / original_comm * 100):.1f}%"
                        if original_comm > 0
                        else "N/A"
                    ),
                )

        # Create result
        total_savings = total_original_commission - total_aggregated_commission

        result = NetOrderResult(
            original_orders_count=original_count,
            aggregated_orders=[agg for agg in aggregated_orders if not agg.is_fully_netted],
            fully_netted_count=fully_netted_count,
            total_original_commission=total_original_commission,
            total_aggregated_commission=total_aggregated_commission,
            total_savings=total_savings,
        )

        logger.info("aggregation_complete", **result.to_dict())

        return result

    def _group_orders(self, orders: dict[str, list[Any]]) -> dict[tuple, list[Any]]:
        """Group orders by asset, order type, and limit price.

        Grouping Key: (asset, order_type, limit_price)

        Args:
            orders: Dict mapping strategy_id to list of orders

        Returns:
            Dict mapping group key to list of orders
        """
        groups: dict[tuple, list[Any]] = {}

        for strategy_id, strategy_orders in orders.items():
            for order in strategy_orders:
                # Create group key
                limit_price = getattr(order, "limit_price", None)

                # Get asset - handle both direct asset objects and asset attributes
                if hasattr(order, "asset"):
                    asset = order.asset
                elif hasattr(order, "sid"):
                    asset = order.sid
                else:
                    # Assume order itself is the asset identifier
                    asset = str(order)

                order_type = getattr(order, "order_type", "market")

                key = (asset, order_type, limit_price)

                if key not in groups:
                    groups[key] = []

                # Attach strategy_id to order for attribution
                order.strategy_id = strategy_id
                groups[key].append(order)

        return groups

    def _calculate_net_amount(self, orders: list[Any]) -> Decimal:
        """Calculate net amount for order group.

        Formula:
            net = Σ(buy amounts) - Σ(sell amounts)

        Convention:
            - Buy orders: positive amount
            - Sell orders: negative amount (or positive with sell flag)

        Args:
            orders: List of orders in group

        Returns:
            Net signed amount
        """
        net = Decimal("0")

        for order in orders:
            # Get signed amount (buy = +, sell = -)
            signed_amount = self._get_order_signed_amount(order)
            net += signed_amount

        return net

    def _create_contributions(
        self,
        orders: list[Any],
        net_amount: Decimal,  # noqa: ARG002
    ) -> list[OrderContribution]:
        """Create order contributions with percentages.

        Args:
            orders: List of orders
            net_amount: Net amount for calculation

        Returns:
            List of OrderContribution objects
        """
        contributions = []

        # Calculate total contribution (sum of absolute values)
        total_contribution = sum(abs(self._get_order_signed_amount(order)) for order in orders)

        for order in orders:
            signed_amount = self._get_order_signed_amount(order)

            # Calculate contribution percentage
            if total_contribution > Decimal("0"):
                contribution_pct = abs(signed_amount) / total_contribution
            else:
                contribution_pct = Decimal("0")

            contrib = OrderContribution(
                strategy_id=order.strategy_id,
                original_order=order,
                contribution_amount=signed_amount,
                contribution_pct=contribution_pct,
            )
            contributions.append(contrib)

        return contributions

    def _get_order_signed_amount(self, order: Any) -> Decimal:  # noqa: ANN401
        """Get signed amount for order (buy = +, sell = -).

        Args:
            order: Order object

        Returns:
            Signed amount
        """
        # Get amount
        if hasattr(order, "amount"):
            amount = order.amount
        elif hasattr(order, "quantity"):
            amount = order.quantity
        else:
            # Default to 0 if no amount attribute found
            logger.warning(
                "order_missing_amount_attribute",
                order_type=type(order).__name__,
                order_attrs=dir(order),
            )
            return Decimal("0")

        # Ensure Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        # Check if amount is already signed or if we need to apply side
        if hasattr(order, "side"):
            # Order has explicit side field
            if order.side == "buy":
                return abs(amount)
            else:  # sell
                return -abs(amount)
        else:
            # Amount already signed (zipline convention: positive = buy, negative = sell)
            return amount

    def _calculate_original_commission(self, orders: list[Any]) -> Decimal:
        """Calculate total commission for original orders (without aggregation).

        Args:
            orders: List of original orders

        Returns:
            Total commission
        """
        if self.commission_model is None:
            # Default simplified commission: $0.005 per share
            return sum(
                abs(self._get_order_signed_amount(order)) * Decimal("0.005") for order in orders
            )

        # Use commission model
        total_commission = Decimal("0")
        for order in orders:
            amount = abs(self._get_order_signed_amount(order))

            # Get asset
            asset = getattr(order, "asset", None)
            if asset is None:
                asset = getattr(order, "sid", None)

            # Calculate commission using model
            if hasattr(self.commission_model, "calculate"):
                # Assume calculate method takes asset and amount
                commission = self.commission_model.calculate(asset=asset, order_value=amount)
            else:
                # Fallback to default
                commission = amount * Decimal("0.005")

            total_commission += commission

        return total_commission

    def _calculate_aggregated_commission(
        self,
        asset: Any,  # noqa: ANN401
        net_amount: Decimal,
        order_type: str,  # noqa: ARG002
    ) -> Decimal:
        """Calculate commission for aggregated order.

        Args:
            asset: Asset object
            net_amount: Net amount (absolute value)
            order_type: Order type

        Returns:
            Commission for aggregated order
        """
        if self.commission_model is None:
            # Default simplified commission: $0.005 per share
            return net_amount * Decimal("0.005")

        # Use commission model
        if hasattr(self.commission_model, "calculate"):
            commission = self.commission_model.calculate(asset=asset, order_value=net_amount)
        else:
            # Fallback to default
            commission = net_amount * Decimal("0.005")

        return commission

    def allocate_fill(
        self, agg_order: AggregatedOrder, fill_price: Decimal, fill_quantity: Decimal
    ) -> dict[str, Decimal]:
        """Allocate aggregated fill back to contributing strategies.

        Allocation Algorithm:
        ====================
        1. Calculate each strategy's proportion of total contribution
        2. Allocate fill proportionally
        3. Preserve direction (buy contributions get buys, sell get sells)
        4. Handle rounding with Decimal precision

        Formula:
        --------
        For each contribution i:
            proportion_i = |contribution_i| / Σ|contributions|
            allocated_fill_i = fill_quantity * proportion_i

            If contribution_i > 0 (buy):
                allocated_fill_i = +allocated_fill_i
            Else (sell):
                allocated_fill_i = -allocated_fill_i

        Example:
        --------
        Aggregated fill: 50 shares
        Contributions:
            Strategy A: +100 (buy)
            Strategy B: -80 (sell)
            Strategy C: +30 (buy)

        Total contribution: |100| + |80| + |30| = 210

        Allocations:
            Strategy A: 50 * (100/210) = 23.81 shares (buy)
            Strategy B: 50 * (80/210) = 19.05 shares (sell)
            Strategy C: 50 * (30/210) = 7.14 shares (buy)

        Args:
            agg_order: Aggregated order
            fill_price: Fill price
            fill_quantity: Fill quantity (absolute value)

        Returns:
            Dict mapping strategy_id to allocated fill (signed)
        """
        # Calculate total contribution (sum of absolute values)
        total_contribution = sum(
            abs(contrib.contribution_amount) for contrib in agg_order.contributions
        )

        if total_contribution == Decimal("0"):
            logger.warning("fill_allocation_zero_contribution", aggregated_order=str(agg_order))
            return {}

        allocations = {}

        for contrib in agg_order.contributions:
            # Calculate proportional allocation
            proportion = abs(contrib.contribution_amount) / total_contribution
            allocated_quantity = fill_quantity * proportion

            # Preserve direction
            if contrib.contribution_amount < Decimal("0"):
                # Sell contribution - allocate as sell
                allocated_quantity = -allocated_quantity

            allocations[contrib.strategy_id] = allocated_quantity

            logger.debug(
                "fill_allocated",
                strategy_id=contrib.strategy_id,
                contribution=str(contrib.contribution_amount),
                proportion=f"{float(proportion):.2%}",
                allocated_quantity=str(allocated_quantity),
                fill_price=str(fill_price),
            )

        # Verify allocation sums to fill_quantity (within rounding tolerance)
        total_allocated = sum(abs(qty) for qty in allocations.values())
        if abs(total_allocated - fill_quantity) > Decimal("0.01"):
            logger.warning(
                "fill_allocation_sum_mismatch",
                fill_quantity=str(fill_quantity),
                total_allocated=str(total_allocated),
                difference=str(total_allocated - fill_quantity),
            )

        return allocations

    def get_statistics(self) -> dict[str, Any]:
        """Get aggregation statistics.

        Returns:
            Dictionary with aggregation stats
        """
        aggregation_rate = "N/A"
        if self.total_orders_processed > 0:
            rate = (
                Decimal(str(self.total_orders_aggregated))
                / Decimal(str(self.total_orders_processed))
                * 100
            )
            aggregation_rate = f"{float(rate):.1f}%"

        return {
            "total_orders_processed": self.total_orders_processed,
            "total_orders_aggregated": self.total_orders_aggregated,
            "total_orders_netted": self.total_orders_netted,
            "cumulative_savings": f"${float(self.cumulative_savings):,.2f}",
            "aggregation_rate": aggregation_rate,
        }
