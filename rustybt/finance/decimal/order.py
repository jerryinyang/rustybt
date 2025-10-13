"""Decimal-based order tracking for RustyBT.

This module provides DecimalOrder, a Decimal-precision order tracking class
extending Zipline's Order with support for fractional quantities and exact prices.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import structlog

from rustybt.assets import Asset
from rustybt.finance.decimal.config import DecimalConfig
from rustybt.finance.order import ORDER_STATUS, Order
from rustybt.utils.input_validation import expect_types

logger = structlog.get_logger(__name__)


class OrderError(Exception):
    """Base exception for order errors."""


class InvalidPriceError(OrderError):
    """Raised when order price is invalid."""


class InvalidQuantityError(OrderError):
    """Raised when order quantity is invalid."""


class InsufficientPrecisionError(OrderError):
    """Raised when order precision doesn't match asset requirements."""


class DecimalOrder(Order):
    """Order with Decimal precision for prices and quantities.

    Extends Zipline's Order class to support:
    - Decimal prices (limit_price, stop_price, filled_price)
    - Decimal quantities (amount, filled)
    - Fractional shares/crypto (0.00000001 BTC minimum)
    - Asset-class-specific precision validation

    Example:
        >>> order = DecimalOrder(
        ...     dt=datetime.now(),
        ...     asset=crypto_asset,
        ...     amount=Decimal("0.00000001"),
        ...     order_type="market"
        ... )
        >>> order.order_value  # price × quantity
        Decimal('0.0005')
    """

    __slots__ = [
        "_status",
        "amount",
        "asset",
        "broker_order_id",
        "commission",
        "config",
        "created",
        "direction",
        "dt",
        "filled",
        "filled_price",
        "id",
        "is_trailing_stop",
        "limit",
        "limit_reached",
        "linked_order_ids",
        "order_type",
        "parent_order_id",
        "reason",
        "stop",
        "stop_reached",
        "trail_amount",
        "trail_percent",
        "trailing_highest_price",
        "trailing_lowest_price",
        "type",
    ]

    @expect_types(asset=Asset)
    def __init__(
        self,
        dt: datetime,
        asset: Asset,
        amount: Decimal,
        order_type: str = "market",
        stop: Decimal | None = None,
        limit: Decimal | None = None,
        filled: Decimal | None = None,
        commission: Decimal | None = None,
        id: str | None = None,
        trail_amount: Decimal | None = None,
        trail_percent: Decimal | None = None,
        linked_order_ids: list[str] | None = None,
        parent_order_id: str | None = None,
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize DecimalOrder with Decimal values.

        Args:
            dt: Timestamp when order was created
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell) as Decimal
            order_type: Order type (market, limit, stop, stop_limit)
            stop: Stop price for stop orders (Decimal)
            limit: Limit price for limit orders (Decimal)
            filled: Quantity filled so far (Decimal, defaults to 0)
            commission: Commission paid so far (Decimal, defaults to 0)
            id: Order ID (auto-generated if None)
            trail_amount: Absolute dollar amount for trailing stop (Decimal)
            trail_percent: Percentage for trailing stop (Decimal)
            linked_order_ids: List of order IDs in OCO relationship
            parent_order_id: Parent order ID for bracket order children
            config: DecimalConfig instance (uses default if None)

        Raises:
            InvalidPriceError: If prices are non-positive
            InvalidQuantityError: If amount is zero
            InsufficientPrecisionError: If precision doesn't match asset class
        """
        self.id = self.make_id() if id is None else id
        self.dt = dt
        self.reason = None
        self.created = dt
        self.asset = asset
        self.amount = amount
        self.filled = filled if filled is not None else Decimal("0")
        self.commission = commission if commission is not None else Decimal("0")
        self._status = ORDER_STATUS.OPEN
        self.stop = stop
        self.limit = limit
        self.stop_reached = False
        self.limit_reached = False
        self.direction = 1 if self.amount > Decimal("0") else -1
        self.type = None  # Set by protocol
        self.broker_order_id = None
        self.order_type = order_type

        # Advanced order type fields (Decimal)
        self.trail_amount = trail_amount
        self.trail_percent = trail_percent
        self.linked_order_ids = linked_order_ids if linked_order_ids else []
        self.parent_order_id = parent_order_id
        self.is_trailing_stop = trail_amount is not None or trail_percent is not None
        self.trailing_highest_price: Decimal | None = None
        self.trailing_lowest_price: Decimal | None = None

        # Decimal-specific fields
        self.filled_price: Decimal | None = None
        self.config = config or DecimalConfig.get_instance()

        # Validate order
        self._validate()

        logger.debug(
            "decimal_order_created",
            order_id=self.id,
            asset=str(asset),
            amount=str(amount),
            order_type=order_type,
        )

    @staticmethod
    def make_id() -> str:
        """Generate unique order ID.

        Returns:
            Order ID as hex string
        """
        return uuid4().hex

    def _validate(self) -> None:
        """Validate order meets requirements.

        Raises:
            InvalidPriceError: If limit_price or stop_price is non-positive
            InvalidQuantityError: If amount is zero
            InsufficientPrecisionError: If precision doesn't match asset class
        """
        # Validate prices are positive
        if self.limit is not None and self.limit <= Decimal("0"):
            raise InvalidPriceError(f"Limit price must be positive, got {self.limit}")

        if self.stop is not None and self.stop <= Decimal("0"):
            raise InvalidPriceError(f"Stop price must be positive, got {self.stop}")

        # Validate quantity is non-zero
        if self.amount == Decimal("0"):
            raise InvalidQuantityError("Order amount cannot be zero")

        # Validate precision matches asset class
        asset_class = getattr(self.asset, "asset_class", "equity")
        expected_scale = self.config.get_scale(asset_class)

        # Check amount precision
        amount_tuple = abs(self.amount).as_tuple()
        actual_scale = -amount_tuple.exponent if amount_tuple.exponent < 0 else 0

        if actual_scale > expected_scale:
            raise InsufficientPrecisionError(
                f"Order amount scale {actual_scale} exceeds "
                f"expected {expected_scale} for {asset_class}"
            )

    @property
    def order_value(self) -> Decimal:
        """Calculate order value: price × quantity.

        Returns:
            Order value as Decimal (uses limit_price or filled_price)

        Raises:
            ValueError: If order has no price information
        """
        price = self.limit or self.filled_price
        if price is None:
            raise ValueError("Cannot calculate order value without price")

        return abs(self.amount) * price

    @property
    def open_amount(self) -> Decimal:
        """Calculate remaining unfilled quantity.

        Returns:
            Remaining quantity as Decimal

        Invariant:
            amount = filled + open_amount (exact equality)
        """
        return self.amount - self.filled

    @property
    def remaining(self) -> Decimal:
        """Alias for open_amount for API compatibility.

        Returns:
            Remaining quantity as Decimal
        """
        return self.open_amount

    def update_trailing_stop(self, current_price: Decimal) -> Decimal:
        """Update trailing stop price based on current market price.

        Args:
            current_price: Current market price (Decimal)

        Returns:
            Updated stop price (Decimal)
        """
        if not self.is_trailing_stop:
            return self.stop

        is_buy = self.amount > Decimal("0")

        if is_buy:
            # For buy/cover orders (closing short), track lowest price
            if self.trailing_lowest_price is None or current_price < self.trailing_lowest_price:
                self.trailing_lowest_price = current_price

            if self.trail_amount is not None:
                self.stop = self.trailing_lowest_price + self.trail_amount
            else:
                self.stop = self.trailing_lowest_price * (Decimal("1") + self.trail_percent)
        else:
            # For sell orders (closing long), track highest price
            if self.trailing_highest_price is None or current_price > self.trailing_highest_price:
                self.trailing_highest_price = current_price

            if self.trail_amount is not None:
                self.stop = self.trailing_highest_price - self.trail_amount
            else:
                self.stop = self.trailing_highest_price * (Decimal("1") - self.trail_percent)

        return self.stop

    def check_triggers(self, price: Decimal, dt: datetime) -> None:
        """Update internal state based on price triggers.

        Args:
            price: Current market price (Decimal)
            dt: Current timestamp
        """
        # Update trailing stop price if applicable
        if self.is_trailing_stop:
            self.update_trailing_stop(price)

        (
            stop_reached,
            limit_reached,
            sl_stop_reached,
        ) = self.check_order_triggers(price)

        if (stop_reached, limit_reached) != (
            self.stop_reached,
            self.limit_reached,
        ):
            self.dt = dt

        self.stop_reached = stop_reached
        self.limit_reached = limit_reached

        if sl_stop_reached:
            # Change the STOP LIMIT order into a LIMIT order
            self.stop = None

    def check_order_triggers(self, current_price: Decimal) -> tuple[bool, bool, bool]:
        """Check if order price triggers have been reached.

        Args:
            current_price: Current market price (Decimal)

        Returns:
            Tuple of (stop_reached, limit_reached, sl_stop_reached)
        """
        if self.triggered:
            return (self.stop_reached, self.limit_reached, False)

        stop_reached = False
        limit_reached = False
        sl_stop_reached = False

        is_buy = self.amount > Decimal("0")
        has_stop = self.stop is not None
        has_limit = self.limit is not None

        # Buy Stop Limit
        if is_buy and has_stop and has_limit:
            if current_price >= self.stop:
                sl_stop_reached = True
                if current_price <= self.limit:
                    limit_reached = True
        # Sell Stop Limit
        elif not is_buy and has_stop and has_limit:
            if current_price <= self.stop:
                sl_stop_reached = True
                if current_price >= self.limit:
                    limit_reached = True
        # Buy Stop
        elif is_buy and has_stop:
            if current_price >= self.stop:
                stop_reached = True
        # Sell Stop
        elif not is_buy and has_stop:
            if current_price <= self.stop:
                stop_reached = True
        # Buy Limit
        elif is_buy and has_limit:
            if current_price <= self.limit:
                limit_reached = True
        # Sell Limit
        elif not is_buy and has_limit:
            if current_price >= self.limit:
                limit_reached = True

        return (stop_reached, limit_reached, sl_stop_reached)

    def handle_split(self, ratio: Decimal) -> None:
        """Adjust order for stock split.

        Args:
            ratio: Split ratio (e.g., Decimal("2") for 2:1 split)

        Note:
            new_share_amount = old_share_amount / ratio
            new_price = old_price * ratio
        """
        self.amount = self.amount / ratio

        if self.limit is not None:
            self.limit = self.limit * ratio

        if self.stop is not None:
            self.stop = self.stop * ratio

    def __repr__(self) -> str:
        """String representation of order.

        Returns:
            String representation
        """
        return (
            f"DecimalOrder(id={self.id}, asset={self.asset}, amount={self.amount}, "
            f"order_type={self.order_type}, status={self.status})"
        )
