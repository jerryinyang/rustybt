"""Decimal-based position tracking for RustyBT.

This module provides DecimalPosition, which tracks position data with
financial-grade Decimal precision, eliminating rounding errors in
position calculations.
"""

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
import structlog

from rustybt.assets import Asset
from rustybt.finance.decimal.config import DecimalConfig

logger = structlog.get_logger(__name__)


class PositionError(Exception):
    """Base exception for position errors."""


class InvalidPositionError(PositionError):
    """Raised when position data is invalid."""


@dataclass
class DecimalPosition:
    """Position tracking with Decimal precision.

    Tracks position data (amount, cost basis, market price) with financial-grade
    Decimal arithmetic to eliminate rounding errors. Supports fractional shares
    for cryptocurrencies and integer shares for equities.

    Attributes:
        asset: Asset held in this position
        amount: Position quantity as Decimal (positive=long, negative=short)
        cost_basis: Volume-weighted average price paid per unit
        last_sale_price: Most recent market price
        last_sale_date: Timestamp of most recent price update
        cash_used: Cash used to open position (for leverage calculation)
        accumulated_borrow_cost: Total borrow cost accrued on short positions
        accumulated_financing: Total financing cost accrued on leveraged positions

    Invariants:
        - market_value == amount * last_sale_price (exact equality)
        - unrealized_pnl == market_value - (cost_basis * amount)

    Example:
        >>> from decimal import Decimal
        >>> from rustybt.assets import Equity
        >>> position = DecimalPosition(
        ...     asset=Equity(symbol="AAPL"),
        ...     amount=Decimal("100"),
        ...     cost_basis=Decimal("150.00"),
        ...     last_sale_price=Decimal("155.50")
        ... )
        >>> position.market_value
        Decimal('15550.00')
        >>> position.unrealized_pnl
        Decimal('550.00')
    """

    asset: Asset
    amount: Decimal
    cost_basis: Decimal
    last_sale_price: Decimal
    last_sale_date: pd.Timestamp | None = None
    cash_used: Decimal = Decimal("0")
    accumulated_borrow_cost: Decimal = Decimal("0")
    accumulated_financing: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        """Validate position data after initialization."""
        # Ensure all numeric fields are Decimal
        if not isinstance(self.amount, Decimal):
            raise InvalidPositionError(f"Position amount must be Decimal, got {type(self.amount)}")
        if not isinstance(self.cost_basis, Decimal):
            raise InvalidPositionError(
                f"Position cost_basis must be Decimal, got {type(self.cost_basis)}"
            )
        if not isinstance(self.last_sale_price, Decimal):
            raise InvalidPositionError(
                f"Position last_sale_price must be Decimal, got {type(self.last_sale_price)}"
            )

        # Validate precision matches asset class requirements
        config = DecimalConfig.get_instance()
        asset_class = self._get_asset_class()
        expected_scale = config.get_scale(asset_class)

        # Check amount precision
        amount_scale = self._get_decimal_scale(self.amount)
        if amount_scale > expected_scale:
            logger.warning(
                "position_amount_precision_exceeds_expected",
                asset=self.asset.symbol if hasattr(self.asset, "symbol") else str(self.asset),
                amount=str(self.amount),
                actual_scale=amount_scale,
                expected_scale=expected_scale,
                asset_class=asset_class,
            )

    def _get_asset_class(self) -> str:
        """Get asset class string for DecimalConfig lookup."""
        # Check if asset has asset_type attribute (for test mocks)
        if hasattr(self.asset, "asset_type"):
            asset_type = self.asset.asset_type
        else:
            asset_type = type(self.asset).__name__

        # Map asset type to asset class
        if asset_type in ("Equity", "Stock"):
            return "equity"
        elif asset_type in ("Cryptocurrency", "Crypto"):
            return "crypto"
        elif asset_type == "Future":
            return "future"
        elif asset_type in ("Forex", "CurrencyPair"):
            return "forex"
        else:
            # Default to equity for unknown types
            logger.warning(
                "unknown_asset_type_defaulting_to_equity",
                asset_type=asset_type,
                asset=str(self.asset),
            )
            return "equity"

    @staticmethod
    def _get_decimal_scale(value: Decimal) -> int:
        """Get the scale (decimal places) of a Decimal value."""
        value_tuple = value.as_tuple()
        if value_tuple.exponent >= 0:
            return 0
        return -value_tuple.exponent

    @property
    def market_value(self) -> Decimal:
        """Calculate current market value of position.

        Returns:
            Market value = amount * last_sale_price

        Example:
            >>> position.amount
            Decimal('100')
            >>> position.last_sale_price
            Decimal('155.50')
            >>> position.market_value
            Decimal('15550.00')
        """
        return self.amount * self.last_sale_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized profit/loss.

        Returns:
            Unrealized P&L = market_value - (cost_basis * amount)

        Example:
            >>> position.market_value
            Decimal('15550.00')
            >>> position.cost_basis
            Decimal('150.00')
            >>> position.amount
            Decimal('100')
            >>> position.unrealized_pnl
            Decimal('550.00')
        """
        cost_value = self.cost_basis * self.amount
        return self.market_value - cost_value

    @property
    def is_short(self) -> bool:
        """Check if position is short.

        Returns:
            True if position is short (amount < 0), False otherwise
        """
        return self.amount < Decimal("0")

    @property
    def is_leveraged(self) -> bool:
        """Check if position uses leverage.

        Returns:
            True if position uses leverage (market_value > cash_used), False otherwise
        """
        return abs(self.market_value) > self.cash_used

    @property
    def leverage_ratio(self) -> Decimal:
        """Calculate leverage ratio.

        Returns:
            Leverage ratio = market_value / cash_used (1.0 = no leverage)

        Example:
            >>> position.market_value
            Decimal('100000.00')
            >>> position.cash_used
            Decimal('50000.00')
            >>> position.leverage_ratio
            Decimal('2.0')
        """
        if self.cash_used > Decimal("0"):
            return abs(self.market_value) / self.cash_used
        return Decimal("1")

    @property
    def leveraged_exposure(self) -> Decimal:
        """Calculate leveraged exposure (amount financed).

        Returns:
            Leveraged exposure = abs(market_value) - cash_used

        Example:
            >>> position.market_value
            Decimal('100000.00')
            >>> position.cash_used
            Decimal('50000.00')
            >>> position.leveraged_exposure
            Decimal('50000.00')
        """
        return max(abs(self.market_value) - self.cash_used, Decimal("0"))

    @property
    def total_costs(self) -> Decimal:
        """Total accumulated costs (borrow + financing + commissions).

        Returns:
            Sum of all accumulated costs
        """
        return self.accumulated_borrow_cost + self.accumulated_financing

    @property
    def unrealized_pnl_net_of_costs(self) -> Decimal:
        """Unrealized P&L after all costs.

        Returns:
            Unrealized P&L minus total accumulated costs
        """
        return self.unrealized_pnl - self.total_costs

    def update(
        self, transaction_amount: Decimal, transaction_price: Decimal, transaction_dt: pd.Timestamp
    ) -> None:
        """Update position with new transaction.

        Args:
            transaction_amount: Transaction quantity (positive=buy, negative=sell)
            transaction_price: Transaction price per unit
            transaction_dt: Transaction timestamp

        Updates cost basis using volume-weighted average for same-direction trades.
        Resets cost basis to transaction price when reversing direction past zero.
        """
        from decimal import Decimal as D

        total_shares = self.amount + transaction_amount

        if total_shares == D("0"):
            # Position completely closed
            self.cost_basis = D("0")
        else:
            # Determine direction using sign comparison
            prev_direction = (
                D("1") if self.amount > D("0") else D("-1") if self.amount < D("0") else D("0")
            )
            txn_direction = (
                D("1")
                if transaction_amount > D("0")
                else D("-1") if transaction_amount < D("0") else D("0")
            )

            if (
                prev_direction != D("0")
                and txn_direction != D("0")
                and prev_direction != txn_direction
            ):
                # Covering a short or closing a long position
                if abs(transaction_amount) > abs(self.amount):
                    # Reversed direction (crossed zero)
                    self.cost_basis = transaction_price
            elif prev_direction == txn_direction or prev_direction == D("0"):
                # Same direction or first position: update volume-weighted average cost
                prev_cost = self.cost_basis * self.amount
                txn_cost = transaction_amount * transaction_price
                total_cost = prev_cost + txn_cost
                self.cost_basis = total_cost / total_shares

        # Update last sale price and date
        if self.last_sale_date is None or transaction_dt > self.last_sale_date:
            self.last_sale_price = transaction_price
            self.last_sale_date = transaction_dt

        self.amount = total_shares

        logger.debug(
            "position_updated",
            asset=self.asset.symbol if hasattr(self.asset, "symbol") else str(self.asset),
            amount=str(self.amount),
            cost_basis=str(self.cost_basis),
            last_sale_price=str(self.last_sale_price),
        )

    def handle_split(self, ratio: Decimal) -> Decimal:
        """Handle stock split by adjusting position amount and cost basis.

        Args:
            ratio: Split ratio (e.g., Decimal("3") for 3-for-1 split)

        Returns:
            Cash from fractional shares (for equities that don't support fractional shares)

        Example:
            >>> position = DecimalPosition(
            ...     asset=Equity(symbol="AAPL"),
            ...     amount=Decimal("100"),
            ...     cost_basis=Decimal("150.00"),
            ...     last_sale_price=Decimal("150.00")
            ... )
            >>> cash_returned = position.handle_split(Decimal("3"))
            >>> position.amount
            Decimal('33')
            >>> position.cost_basis
            Decimal('450.00')
        """
        from decimal import ROUND_DOWN
        from decimal import Decimal as D

        # Calculate new share count after split
        raw_share_count = self.amount / ratio

        # For equities, round down to whole shares
        asset_class = self._get_asset_class()
        if asset_class == "equity":
            full_share_count = raw_share_count.quantize(D("1"), rounding=ROUND_DOWN)
            fractional_share_count = raw_share_count - full_share_count
        else:
            # Crypto and other assets support fractional shares
            full_share_count = raw_share_count
            fractional_share_count = D("0")

        # Adjust cost basis by split ratio
        new_cost_basis = self.cost_basis * ratio

        # Round cost basis to 2 decimal places (cents)
        self.cost_basis = new_cost_basis.quantize(D("0.01"))

        self.amount = full_share_count

        # Calculate cash from fractional shares
        return_cash = (fractional_share_count * new_cost_basis).quantize(D("0.01"))

        logger.info(
            "position_split_processed",
            asset=self.asset.symbol if hasattr(self.asset, "symbol") else str(self.asset),
            split_ratio=str(ratio),
            new_amount=str(self.amount),
            new_cost_basis=str(self.cost_basis),
            return_cash=str(return_cash),
        )

        return return_cash

    def adjust_commission_cost_basis(
        self, commission: Decimal, price_multiplier: Decimal = Decimal("1")
    ) -> None:
        """Adjust cost basis to account for commission costs.

        Args:
            commission: Commission cost to spread across position
            price_multiplier: Asset price multiplier (for futures contracts)

        Note:
            For long positions, commissions increase cost basis.
            For short positions, commissions decrease cost basis (you break even at lower price).
        """
        from decimal import Decimal as D

        if commission == D("0") or self.amount == D("0"):
            return

        # Adjust commission for futures multiplier
        cost_to_use = commission / price_multiplier

        # Spread commission across all shares in position
        prev_cost = self.cost_basis * self.amount
        new_cost = prev_cost + cost_to_use
        self.cost_basis = new_cost / self.amount

        logger.debug(
            "position_commission_adjusted",
            asset=self.asset.symbol if hasattr(self.asset, "symbol") else str(self.asset),
            commission=str(commission),
            new_cost_basis=str(self.cost_basis),
        )

    def to_dict(self) -> dict:
        """Convert position to dictionary representation.

        Returns:
            Dictionary with position data (Decimal values as strings)
        """
        return {
            "asset": self.asset,
            "amount": str(self.amount),
            "cost_basis": str(self.cost_basis),
            "last_sale_price": str(self.last_sale_price),
            "last_sale_date": self.last_sale_date,
            "cash_used": str(self.cash_used),
            "market_value": str(self.market_value),
            "unrealized_pnl": str(self.unrealized_pnl),
            "is_leveraged": self.is_leveraged,
            "leverage_ratio": str(self.leverage_ratio),
            "leveraged_exposure": str(self.leveraged_exposure),
            "accumulated_borrow_cost": str(self.accumulated_borrow_cost),
            "accumulated_financing": str(self.accumulated_financing),
            "total_costs": str(self.total_costs),
            "unrealized_pnl_net_of_costs": str(self.unrealized_pnl_net_of_costs),
        }

    def __repr__(self) -> str:
        """String representation of position."""
        return (
            f"DecimalPosition(asset={self.asset}, amount={self.amount}, "
            f"cost_basis={self.cost_basis}, last_sale_price={self.last_sale_price})"
        )
