"""Decimal-based transaction records for RustyBT.

This module provides DecimalTransaction, an immutable transaction record
with Decimal precision for all monetary values.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import structlog

from rustybt.assets import Asset

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DecimalTransaction:
    """Immutable transaction record with Decimal precision.

    All monetary values stored as Decimal to maintain audit-trail precision.
    Frozen dataclass ensures transaction records cannot be modified after creation.

    Example:
        >>> txn = DecimalTransaction(
        ...     timestamp=datetime.now(),
        ...     order_id="abc123",
        ...     asset=equity_asset,
        ...     amount=Decimal("100"),
        ...     price=Decimal("150.50"),
        ...     commission=Decimal("1.00"),
        ...     slippage=Decimal("0.50")
        ... )
        >>> txn.transaction_value
        Decimal('15050.00')
        >>> txn.total_cost
        Decimal('15051.50')
    """

    timestamp: datetime
    order_id: str
    asset: Asset
    amount: Decimal  # Quantity filled (positive=buy, negative=sell)
    price: Decimal  # Execution price
    commission: Decimal  # Commission cost (always positive)
    slippage: Decimal = Decimal("0")  # Slippage cost (always positive)
    broker_order_id: str | None = None

    def __post_init__(self) -> None:
        """Validate transaction fields.

        Raises:
            ValueError: If price is non-positive
            ValueError: If commission is negative
            ValueError: If slippage is negative
        """
        if self.price <= Decimal("0"):
            raise ValueError(f"Price must be positive, got {self.price}")

        if self.commission < Decimal("0"):
            raise ValueError(f"Commission must be non-negative, got {self.commission}")

        if self.slippage < Decimal("0"):
            raise ValueError(f"Slippage must be non-negative, got {self.slippage}")

        logger.debug(
            "decimal_transaction_created",
            order_id=self.order_id,
            asset=str(self.asset),
            amount=str(self.amount),
            price=str(self.price),
            commission=str(self.commission),
            slippage=str(self.slippage),
        )

    @property
    def transaction_value(self) -> Decimal:
        """Calculate transaction value: price × amount.

        Returns:
            Gross transaction value (before costs) as Decimal

        Note:
            Always returns positive value (absolute value of amount × price)
        """
        return abs(self.amount) * self.price

    @property
    def total_cost(self) -> Decimal:
        """Calculate total transaction cost: value + commission + slippage.

        Returns:
            Total cost including all fees as Decimal

        Note:
            For buy orders: positive cost (cash outflow)
            For sell orders: positive revenue (cash inflow)
        """
        value = self.transaction_value
        costs = self.commission + self.slippage

        # Buy: cost = value + fees (cash decreases)
        # Sell: revenue = value - fees (cash increases)
        if self.amount > Decimal("0"):
            return value + costs
        else:
            return value - costs

    @property
    def net_proceeds(self) -> Decimal:
        """Calculate net proceeds for sell orders.

        Returns:
            Net proceeds after fees (for sell orders)
            Negative of total cost (for buy orders)

        Note:
            This is the inverse of total_cost for convenience
        """
        if self.amount < Decimal("0"):
            # Sell order: positive proceeds
            return self.total_cost
        else:
            # Buy order: negative cost
            return -self.total_cost

    def to_dict(self) -> dict:
        """Convert transaction to dictionary.

        Returns:
            Dictionary representation of transaction
        """
        return {
            "timestamp": self.timestamp.isoformat(),
            "order_id": self.order_id,
            "asset": str(self.asset),
            "amount": str(self.amount),
            "price": str(self.price),
            "commission": str(self.commission),
            "slippage": str(self.slippage),
            "broker_order_id": self.broker_order_id,
            "transaction_value": str(self.transaction_value),
            "total_cost": str(self.total_cost),
        }

    def __repr__(self) -> str:
        """String representation of transaction.

        Returns:
            String representation
        """
        return (
            f"DecimalTransaction(asset={self.asset}, amount={self.amount}, "
            f"price={self.price}, commission={self.commission}, slippage={self.slippage})"
        )


def create_decimal_transaction(
    order_id: str,
    asset: Asset,
    dt: datetime,
    price: Decimal,
    amount: Decimal,
    commission: Decimal = Decimal("0"),
    slippage: Decimal = Decimal("0"),
    broker_order_id: str | None = None,
) -> DecimalTransaction:
    """Create a DecimalTransaction with validation.

    Args:
        order_id: Order ID
        asset: Asset traded
        dt: Transaction timestamp
        price: Execution price
        amount: Quantity filled (positive=buy, negative=sell)
        commission: Commission cost
        slippage: Slippage cost
        broker_order_id: Optional broker order ID

    Returns:
        DecimalTransaction instance

    Raises:
        ValueError: If amount magnitude is less than minimum precision
    """
    # Validate amount is non-zero
    if amount == Decimal("0"):
        raise ValueError("Transaction amount cannot be zero")

    transaction = DecimalTransaction(
        timestamp=dt,
        order_id=order_id,
        asset=asset,
        amount=amount,
        price=price,
        commission=commission,
        slippage=slippage,
        broker_order_id=broker_order_id,
    )

    logger.info(
        "transaction_created",
        order_id=order_id,
        asset=str(asset),
        amount=str(amount),
        price=str(price),
        total_cost=str(transaction.total_cost),
    )

    return transaction
