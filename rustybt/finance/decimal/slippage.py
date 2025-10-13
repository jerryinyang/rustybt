"""Decimal-based slippage models for RustyBT.

This module provides slippage calculation models using Decimal precision
for accurate price impact simulation in order execution.
"""

from abc import ABC, abstractmethod
from decimal import Decimal

import structlog

from rustybt.finance.decimal.config import DecimalConfig
from rustybt.finance.decimal.order import DecimalOrder

logger = structlog.get_logger(__name__)


class DecimalSlippageModel(ABC):
    """Abstract base class for Decimal slippage models.

    Slippage models adjust execution price to simulate market impact.
    All slippage calculations must worsen execution price (never improve).
    """

    @abstractmethod
    def calculate(self, order: DecimalOrder, market_price: Decimal) -> Decimal:
        """Calculate execution price with slippage.

        Args:
            order: Order being filled
            market_price: Current market price (Decimal)

        Returns:
            Execution price with slippage (Decimal)

        Note:
            Buy orders: execution price >= market price (worse)
            Sell orders: execution price <= market price (worse)
        """
        pass


class NoSlippage(DecimalSlippageModel):
    """Zero slippage model for testing.

    Returns exact market price with no price impact.
    Primarily used for testing strategies without market impact.
    """

    def calculate(self, order: DecimalOrder, market_price: Decimal) -> Decimal:
        """Return market price with no slippage.

        Args:
            order: Order being filled
            market_price: Current market price

        Returns:
            Market price (unchanged)
        """
        return market_price

    def __repr__(self) -> str:
        return "NoSlippage()"


class FixedSlippage(DecimalSlippageModel):
    """Fixed slippage as absolute dollar amount.

    Formula:
        Buy: market_price + slippage
        Sell: market_price - slippage

    Example:
        >>> model = FixedSlippage(slippage=Decimal("0.10"))
        >>> # Buy order with $100 market price
        >>> execution_price = model.calculate(buy_order, Decimal("100"))
        Decimal('100.10')  # Pay 10 cents more
    """

    def __init__(self, slippage: Decimal, config: DecimalConfig | None = None) -> None:
        """Initialize fixed slippage model.

        Args:
            slippage: Fixed slippage amount (e.g., Decimal("0.10") = $0.10)
            config: DecimalConfig instance (uses default if None)

        Raises:
            ValueError: If slippage is negative
        """
        if slippage < Decimal("0"):
            raise ValueError(f"Slippage must be non-negative, got {slippage}")

        self.slippage = slippage
        self.config = config or DecimalConfig.get_instance()

        logger.info("fixed_slippage_initialized", slippage=str(slippage))

    def calculate(self, order: DecimalOrder, market_price: Decimal) -> Decimal:
        """Calculate execution price with fixed slippage.

        Args:
            order: Order being filled
            market_price: Current market price

        Returns:
            Execution price (market_price +/- slippage)
        """
        # Buy: pay more (worse execution)
        if order.amount > Decimal("0"):
            result = market_price + self.slippage
        # Sell: receive less (worse execution)
        else:
            result = market_price - self.slippage

        logger.debug(
            "fixed_slippage_calculated",
            order_id=order.id,
            market_price=str(market_price),
            execution_price=str(result),
            slippage=str(self.slippage),
        )

        return result

    def __repr__(self) -> str:
        return f"FixedSlippage(slippage={self.slippage})"


class FixedBasisPointsSlippage(DecimalSlippageModel):
    """Slippage as fixed basis points (percentage of price).

    Formula:
        Buy: market_price × (1 + bps / 10000)
        Sell: market_price × (1 - bps / 10000)

    Example:
        >>> model = FixedBasisPointsSlippage(basis_points=Decimal("10"))  # 0.1%
        >>> # Buy order with $100 market price
        >>> execution_price = model.calculate(buy_order, Decimal("100"))
        Decimal('100.10')  # 100 × 1.001 = 100.10
    """

    def __init__(self, basis_points: Decimal, config: DecimalConfig | None = None) -> None:
        """Initialize fixed basis points slippage model.

        Args:
            basis_points: Slippage in basis points (e.g., Decimal("10") = 0.1%)
            config: DecimalConfig instance (uses default if None)

        Raises:
            ValueError: If basis_points is negative
        """
        if basis_points < Decimal("0"):
            raise ValueError(f"Basis points must be non-negative, got {basis_points}")

        self.basis_points = basis_points
        self.config = config or DecimalConfig.get_instance()

        logger.info("fixed_bps_slippage_initialized", basis_points=str(basis_points))

    def calculate(self, order: DecimalOrder, market_price: Decimal) -> Decimal:
        """Calculate execution price with fixed basis points slippage.

        Args:
            order: Order being filled
            market_price: Current market price

        Returns:
            Execution price with percentage slippage
        """
        slippage_factor = self.basis_points / Decimal("10000")

        # Buy: pay more (worse execution)
        if order.amount > Decimal("0"):
            result = market_price * (Decimal("1") + slippage_factor)
        # Sell: receive less (worse execution)
        else:
            result = market_price * (Decimal("1") - slippage_factor)

        logger.debug(
            "fixed_bps_slippage_calculated",
            order_id=order.id,
            market_price=str(market_price),
            execution_price=str(result),
            basis_points=str(self.basis_points),
        )

        return result

    def __repr__(self) -> str:
        return f"FixedBasisPointsSlippage(basis_points={self.basis_points})"


class VolumeShareSlippage(DecimalSlippageModel):
    """Volume-based slippage model with price impact.

    Formula:
        volume_share = order_volume / bar_volume
        price_impact = volume_share^2 × impact_factor
        execution_price = market_price × (1 +/- price_impact)

    Example:
        >>> model = VolumeShareSlippage(
        ...     volume_limit=Decimal("0.025"),  # Max 2.5% of volume
        ...     impact_factor=Decimal("0.1")    # Price impact coefficient
        ... )
        >>> # Order for 1000 shares, bar volume 100000
        >>> execution_price = model.calculate(order, Decimal("100"), Decimal("1000"), Decimal("100000"))
        Decimal('100.001')  # Small price impact
    """

    def __init__(
        self,
        volume_limit: Decimal = Decimal("0.025"),
        impact_factor: Decimal = Decimal("0.1"),
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize volume share slippage model.

        Args:
            volume_limit: Maximum order volume as fraction of bar volume
            impact_factor: Price impact coefficient
            config: DecimalConfig instance (uses default if None)

        Raises:
            ValueError: If volume_limit or impact_factor is negative
        """
        if volume_limit <= Decimal("0"):
            raise ValueError(f"Volume limit must be positive, got {volume_limit}")

        if impact_factor < Decimal("0"):
            raise ValueError(f"Impact factor must be non-negative, got {impact_factor}")

        self.volume_limit = volume_limit
        self.impact_factor = impact_factor
        self.config = config or DecimalConfig.get_instance()

        logger.info(
            "volume_share_slippage_initialized",
            volume_limit=str(volume_limit),
            impact_factor=str(impact_factor),
        )

    def calculate(
        self,
        order: DecimalOrder,
        market_price: Decimal,
        fill_amount: Decimal,
        bar_volume: Decimal,
    ) -> Decimal:
        """Calculate execution price with volume-based slippage.

        Args:
            order: Order being filled
            market_price: Current market price
            fill_amount: Quantity being filled
            bar_volume: Total bar volume

        Returns:
            Execution price with volume-based slippage

        Raises:
            ValueError: If fill exceeds volume limit
        """
        if bar_volume == Decimal("0"):
            raise ValueError("Bar volume cannot be zero")

        # Calculate volume share
        volume_share = abs(fill_amount) / bar_volume

        # Check volume limit
        if volume_share > self.volume_limit:
            raise ValueError(
                f"Fill volume {fill_amount} exceeds limit of {self.volume_limit * bar_volume} "
                f"(volume_share: {volume_share}, limit: {self.volume_limit})"
            )

        # Calculate price impact: volume_share^2 × impact_factor
        price_impact = (volume_share * volume_share) * self.impact_factor

        # Buy: pay more (worse execution)
        if order.amount > Decimal("0"):
            result = market_price * (Decimal("1") + price_impact)
        # Sell: receive less (worse execution)
        else:
            result = market_price * (Decimal("1") - price_impact)

        logger.debug(
            "volume_share_slippage_calculated",
            order_id=order.id,
            market_price=str(market_price),
            execution_price=str(result),
            volume_share=str(volume_share),
            price_impact=str(price_impact),
        )

        return result

    def __repr__(self) -> str:
        return (
            f"VolumeShareSlippage(volume_limit={self.volume_limit}, "
            f"impact_factor={self.impact_factor})"
        )


class AsymmetricSlippage(DecimalSlippageModel):
    """Asymmetric slippage with different rates for buy and sell.

    Allows different slippage models for buy and sell orders.

    Example:
        >>> model = AsymmetricSlippage(
        ...     buy_model=FixedBasisPointsSlippage(Decimal("10")),   # 0.1% on buys
        ...     sell_model=FixedBasisPointsSlippage(Decimal("15"))   # 0.15% on sells
        ... )
    """

    def __init__(
        self,
        buy_model: DecimalSlippageModel,
        sell_model: DecimalSlippageModel,
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize asymmetric slippage model.

        Args:
            buy_model: Slippage model for buy orders
            sell_model: Slippage model for sell orders
            config: DecimalConfig instance (uses default if None)
        """
        self.buy_model = buy_model
        self.sell_model = sell_model
        self.config = config or DecimalConfig.get_instance()

        logger.info(
            "asymmetric_slippage_initialized",
            buy_model=str(buy_model),
            sell_model=str(sell_model),
        )

    def calculate(self, order: DecimalOrder, market_price: Decimal, **kwargs) -> Decimal:
        """Calculate execution price using appropriate model for buy/sell.

        Args:
            order: Order being filled
            market_price: Current market price
            **kwargs: Additional arguments passed to underlying models

        Returns:
            Execution price from buy or sell model
        """
        if order.amount > Decimal("0"):
            # Buy order
            result = self.buy_model.calculate(order, market_price, **kwargs)
        else:
            # Sell order
            result = self.sell_model.calculate(order, market_price, **kwargs)

        logger.debug(
            "asymmetric_slippage_calculated",
            order_id=order.id,
            side="buy" if order.amount > Decimal("0") else "sell",
            market_price=str(market_price),
            execution_price=str(result),
        )

        return result

    def __repr__(self) -> str:
        return f"AsymmetricSlippage(buy_model={self.buy_model}, sell_model={self.sell_model})"
