"""Decimal-based commission models for RustyBT.

This module provides commission calculation models using Decimal precision
for accurate cost tracking in order execution.
"""

from abc import ABC, abstractmethod
from decimal import Decimal

import structlog

from rustybt.finance.decimal.config import DecimalConfig
from rustybt.finance.decimal.order import DecimalOrder

logger = structlog.get_logger(__name__)


class DecimalCommissionModel(ABC):
    """Abstract base class for Decimal commission models.

    Commission models calculate transaction costs with Decimal precision.
    All commission calculations must return non-negative Decimal values.
    """

    @abstractmethod
    def calculate(self, order: DecimalOrder, fill_price: Decimal, fill_amount: Decimal) -> Decimal:
        """Calculate commission for order fill.

        Args:
            order: Order being filled
            fill_price: Execution price (Decimal)
            fill_amount: Quantity filled (Decimal)

        Returns:
            Commission as Decimal (non-negative)

        Raises:
            ValueError: If inputs are invalid
        """
        pass


class NoCommission(DecimalCommissionModel):
    """Zero commission model for testing.

    This model charges no commission and is primarily used for testing
    strategies without transaction costs.
    """

    def calculate(self, order: DecimalOrder, fill_price: Decimal, fill_amount: Decimal) -> Decimal:
        """Calculate zero commission.

        Args:
            order: Order being filled
            fill_price: Execution price
            fill_amount: Quantity filled

        Returns:
            Zero commission
        """
        return Decimal("0")

    def __repr__(self) -> str:
        return "NoCommission()"


class PerShareCommission(DecimalCommissionModel):
    """Commission charged per share/contract.

    Formula: max(shares × rate, minimum)

    Example:
        >>> model = PerShareCommission(
        ...     rate=Decimal("0.005"),  # $0.005 per share
        ...     minimum=Decimal("1.00")  # $1 minimum per trade
        ... )
        >>> commission = model.calculate(order, price, Decimal("100"))
        Decimal('1.00')  # 100 × 0.005 = 0.50, but minimum is 1.00
    """

    def __init__(
        self,
        rate: Decimal,
        minimum: Decimal = Decimal("0"),
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize per-share commission model.

        Args:
            rate: Commission per share (e.g., Decimal("0.005") = $0.005/share)
            minimum: Minimum commission per order (e.g., Decimal("1.00"))
            config: DecimalConfig instance (uses default if None)

        Raises:
            ValueError: If rate or minimum is negative
        """
        if rate < Decimal("0"):
            raise ValueError(f"Commission rate must be non-negative, got {rate}")

        if minimum < Decimal("0"):
            raise ValueError(f"Minimum commission must be non-negative, got {minimum}")

        self.rate = rate
        self.minimum = minimum
        self.config = config or DecimalConfig.get_instance()

        logger.info(
            "per_share_commission_initialized",
            rate=str(rate),
            minimum=str(minimum),
        )

    def calculate(self, order: DecimalOrder, fill_price: Decimal, fill_amount: Decimal) -> Decimal:
        """Calculate commission: max(shares × rate, minimum).

        Args:
            order: Order being filled
            fill_price: Execution price
            fill_amount: Quantity filled

        Returns:
            Commission as Decimal
        """
        # Commission based on shares for this fill
        commission = abs(fill_amount) * self.rate

        # Apply minimum commission handling for partial fills
        # Strategy: Charge minimum upfront on first fill, then adjust on subsequent fills
        if order.commission == Decimal("0"):
            # First fill: apply minimum commission
            # Example: 30 shares × $0.005 = $0.15, but minimum is $1.00 → charge $1.00
            result = max(commission, self.minimum)
        else:
            # Subsequent fills: calculate total commission based on all shares filled
            # Example: Previously filled 30 shares (paid $1.00 minimum)
            #          Now filling 70 more shares (total 100)
            #          Total commission should be: 100 × $0.005 = $0.50
            #          Since $0.50 < $1.00 minimum, no additional charge
            total_shares_so_far = abs(order.filled) + abs(fill_amount)
            per_share_total = total_shares_so_far * self.rate

            if per_share_total < self.minimum:
                # Total commission still below minimum - don't charge more
                result = Decimal("0")
            else:
                # Total commission exceeded minimum - charge incremental amount
                # Example: If total should be $5.00 and we've paid $1.00, charge $4.00 more
                result = per_share_total - order.commission

        logger.debug(
            "per_share_commission_calculated",
            order_id=order.id,
            fill_amount=str(fill_amount),
            commission=str(result),
        )

        return result

    def __repr__(self) -> str:
        return f"PerShareCommission(rate={self.rate}, minimum={self.minimum})"


class PerTradeCommission(DecimalCommissionModel):
    """Flat commission per trade.

    Formula: cost (charged once on first fill)

    Example:
        >>> model = PerTradeCommission(cost=Decimal("5.00"))
        >>> commission = model.calculate(order, price, amount)
        Decimal('5.00')  # Flat $5 per trade
    """

    def __init__(self, cost: Decimal, config: DecimalConfig | None = None) -> None:
        """Initialize per-trade commission model.

        Args:
            cost: Flat commission per trade (e.g., Decimal("5.00"))
            config: DecimalConfig instance (uses default if None)

        Raises:
            ValueError: If cost is negative
        """
        if cost < Decimal("0"):
            raise ValueError(f"Commission cost must be non-negative, got {cost}")

        self.cost = cost
        self.config = config or DecimalConfig.get_instance()

        logger.info("per_trade_commission_initialized", cost=str(cost))

    def calculate(self, order: DecimalOrder, fill_price: Decimal, fill_amount: Decimal) -> Decimal:
        """Calculate flat commission (charged once on first fill).

        Args:
            order: Order being filled
            fill_price: Execution price
            fill_amount: Quantity filled

        Returns:
            Commission as Decimal (cost on first fill, 0 on subsequent fills)
        """
        if order.commission == Decimal("0"):
            # First fill: charge full commission
            result = self.cost
        else:
            # Subsequent fills: no additional commission
            result = Decimal("0")

        logger.debug(
            "per_trade_commission_calculated",
            order_id=order.id,
            commission=str(result),
        )

        return result

    def __repr__(self) -> str:
        return f"PerTradeCommission(cost={self.cost})"


class PerDollarCommission(DecimalCommissionModel):
    """Commission as percentage of transaction value.

    Formula: order_value × rate

    Example:
        >>> model = PerDollarCommission(rate=Decimal("0.0015"))  # 0.15%
        >>> commission = model.calculate(order, Decimal("100"), Decimal("100"))
        Decimal('15.00')  # 10000 × 0.0015 = 15.00
    """

    def __init__(self, rate: Decimal, config: DecimalConfig | None = None) -> None:
        """Initialize per-dollar commission model.

        Args:
            rate: Commission rate (e.g., Decimal("0.0015") = 0.15%)
            config: DecimalConfig instance (uses default if None)

        Raises:
            ValueError: If rate is negative
        """
        if rate < Decimal("0"):
            raise ValueError(f"Commission rate must be non-negative, got {rate}")

        self.rate = rate
        self.config = config or DecimalConfig.get_instance()

        logger.info("per_dollar_commission_initialized", rate=str(rate))

    def calculate(self, order: DecimalOrder, fill_price: Decimal, fill_amount: Decimal) -> Decimal:
        """Calculate commission: order_value × rate.

        Args:
            order: Order being filled
            fill_price: Execution price
            fill_amount: Quantity filled

        Returns:
            Commission as Decimal
        """
        # Calculate transaction value
        order_value = abs(fill_amount) * fill_price

        # Apply commission rate
        commission = order_value * self.rate

        logger.debug(
            "per_dollar_commission_calculated",
            order_id=order.id,
            order_value=str(order_value),
            commission=str(commission),
        )

        return commission

    def __repr__(self) -> str:
        return f"PerDollarCommission(rate={self.rate})"


class CryptoCommission(DecimalCommissionModel):
    """Commission for crypto exchanges with maker/taker fees.

    Maker orders add liquidity (limit orders that rest in the book).
    Taker orders remove liquidity (market orders or marketable limit orders).

    Formula: order_value × (maker_rate or taker_rate)

    Example:
        >>> model = CryptoCommission(
        ...     maker_rate=Decimal("0.001"),  # 0.1% maker fee
        ...     taker_rate=Decimal("0.002")   # 0.2% taker fee
        ... )
        >>> # Market order (taker)
        >>> commission = model.calculate(market_order, Decimal("50000"), Decimal("1"))
        Decimal('100.00')  # 50000 × 0.002 = 100.00
    """

    def __init__(
        self,
        maker_rate: Decimal,
        taker_rate: Decimal,
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize crypto commission model.

        Args:
            maker_rate: Maker fee rate (e.g., Decimal("0.001") = 0.1%)
            taker_rate: Taker fee rate (e.g., Decimal("0.002") = 0.2%)
            config: DecimalConfig instance (uses default if None)

        Raises:
            ValueError: If rates are negative
        """
        if maker_rate < Decimal("0"):
            raise ValueError(f"Maker rate must be non-negative, got {maker_rate}")

        if taker_rate < Decimal("0"):
            raise ValueError(f"Taker rate must be non-negative, got {taker_rate}")

        self.maker_rate = maker_rate
        self.taker_rate = taker_rate
        self.config = config or DecimalConfig.get_instance()

        logger.info(
            "crypto_commission_initialized",
            maker_rate=str(maker_rate),
            taker_rate=str(taker_rate),
        )

    def calculate(self, order: DecimalOrder, fill_price: Decimal, fill_amount: Decimal) -> Decimal:
        """Calculate commission based on order type (maker vs taker).

        Args:
            order: Order being filled
            fill_price: Execution price
            fill_amount: Quantity filled

        Returns:
            Commission as Decimal

        Note:
            Limit orders are makers (provide liquidity)
            Market orders are takers (take liquidity)
        """
        # Determine maker vs taker
        is_maker = order.order_type == "limit"
        rate = self.maker_rate if is_maker else self.taker_rate

        # Calculate transaction value
        order_value = abs(fill_amount) * fill_price

        # Apply commission rate
        commission = order_value * rate

        logger.debug(
            "crypto_commission_calculated",
            order_id=order.id,
            order_type=order.order_type,
            is_maker=is_maker,
            order_value=str(order_value),
            commission=str(commission),
        )

        return commission

    def __repr__(self) -> str:
        return f"CryptoCommission(maker_rate={self.maker_rate}, taker_rate={self.taker_rate})"
