"""Decimal-based portfolio ledger for RustyBT.

This module provides DecimalLedger, which tracks portfolio state (cash, positions,
portfolio value) with financial-grade Decimal precision to eliminate rounding errors.
"""

from decimal import Decimal

import pandas as pd
import structlog

from rustybt.assets import Asset
from rustybt.finance.decimal.config import DecimalConfig
from rustybt.finance.decimal.position import DecimalPosition

logger = structlog.get_logger(__name__)


class LedgerError(Exception):
    """Base exception for ledger errors."""


class InsufficientFundsError(LedgerError):
    """Raised when cash balance is insufficient for transaction."""


class InvalidTransactionError(LedgerError):
    """Raised when transaction data is invalid."""


class DecimalLedger:
    """Portfolio ledger with Decimal arithmetic.

    Tracks portfolio state (cash, positions, portfolio value) with financial-grade
    Decimal precision. All monetary values use Decimal to eliminate rounding errors
    in portfolio accounting.

    Attributes:
        starting_cash: Initial cash balance as Decimal
        cash: Current cash balance as Decimal
        positions: Dict mapping assets to DecimalPosition objects
        config: DecimalConfig for precision management

    Invariants:
        - portfolio_value == positions_value + cash (exact equality)
        - All monetary values are Decimal (never float)

    Example:
        >>> from decimal import Decimal
        >>> ledger = DecimalLedger(starting_cash=Decimal("100000"))
        >>> ledger.portfolio_value
        Decimal('100000')
    """

    def __init__(
        self,
        starting_cash: Decimal,
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize ledger with Decimal precision.

        Args:
            starting_cash: Initial cash balance as Decimal
            config: Decimal configuration (uses default if None)
        """
        if not isinstance(starting_cash, Decimal):
            raise InvalidTransactionError(
                f"starting_cash must be Decimal, got {type(starting_cash)}"
            )

        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.config = config or DecimalConfig.get_instance()
        self.positions: dict[Asset, DecimalPosition] = {}

        logger.info(
            "ledger_initialized",
            starting_cash=str(starting_cash),
        )

    @property
    def portfolio_value(self) -> Decimal:
        """Calculate total portfolio value with Decimal precision.

        Returns:
            Sum of position values plus cash balance

        Invariant:
            portfolio_value == positions_value + cash (exact equality)
        """
        return self.positions_value + self.cash

    @property
    def positions_value(self) -> Decimal:
        """Calculate total value of all positions.

        Returns:
            Sum of market values for all positions
        """
        if not self.positions:
            return Decimal("0")

        return sum(
            (pos.market_value for pos in self.positions.values()),
            start=Decimal("0"),
        )

    def process_transaction(
        self,
        asset: Asset,
        amount: Decimal,
        price: Decimal,
        commission: Decimal,
        dt: pd.Timestamp,
    ) -> None:
        """Process transaction and update ledger state.

        Args:
            asset: Asset being traded
            amount: Transaction quantity (positive=buy, negative=sell)
            price: Transaction price per unit
            commission: Transaction commission cost
            dt: Transaction timestamp

        Raises:
            InsufficientFundsError: If transaction would make cash negative
            InvalidTransactionError: If transaction data is invalid
        """
        # Validate inputs
        if not isinstance(amount, Decimal):
            raise InvalidTransactionError(f"amount must be Decimal, got {type(amount)}")
        if not isinstance(price, Decimal):
            raise InvalidTransactionError(f"price must be Decimal, got {type(price)}")
        if not isinstance(commission, Decimal):
            raise InvalidTransactionError(f"commission must be Decimal, got {type(commission)}")

        # Calculate cash impact (negative for buys, positive for sells)
        cash_impact = -(amount * price) - commission

        # Check for insufficient funds
        new_cash = self.cash + cash_impact
        if new_cash < Decimal("0"):
            raise InsufficientFundsError(
                f"Insufficient cash: have {self.cash}, need {-cash_impact}, shortfall {-new_cash}"
            )

        # Update or create position
        if asset in self.positions:
            position = self.positions[asset]
            position.update(amount, price, dt)

            # Remove position if amount is zero
            if position.amount == Decimal("0"):
                del self.positions[asset]
        else:
            # Create new position
            self.positions[asset] = DecimalPosition(
                asset=asset,
                amount=amount,
                cost_basis=price,
                last_sale_price=price,
                last_sale_date=dt,
            )

        # Adjust cost basis for commission if position still exists
        if asset in self.positions and commission != Decimal("0"):
            price_multiplier = Decimal("1")  # Default for equities
            # TODO: Get price multiplier from asset if it's a Future
            self.positions[asset].adjust_commission_cost_basis(commission, price_multiplier)

        # Update cash balance
        self.cash = new_cash

        logger.info(
            "transaction_processed",
            asset=asset.symbol if hasattr(asset, "symbol") else str(asset),
            amount=str(amount),
            price=str(price),
            commission=str(commission),
            cash=str(self.cash),
            portfolio_value=str(self.portfolio_value),
        )

    def calculate_returns(self, start_value: Decimal, end_value: Decimal) -> Decimal:
        """Calculate returns from value change.

        Args:
            start_value: Starting portfolio value
            end_value: Ending portfolio value

        Returns:
            Return = (end_value / start_value) - 1

        Raises:
            ValueError: If start_value is zero or negative
        """
        if start_value <= Decimal("0"):
            raise ValueError(f"Start value must be positive, got {start_value}")

        return (end_value / start_value) - Decimal("1")

    def calculate_daily_return(self, start_value: Decimal, end_value: Decimal) -> Decimal:
        """Calculate daily return from value change.

        Args:
            start_value: Portfolio value at start of day
            end_value: Portfolio value at end of day

        Returns:
            Daily return = (end_value - start_value) / start_value
        """
        if start_value <= Decimal("0"):
            raise ValueError(f"Start value must be positive, got {start_value}")

        return (end_value - start_value) / start_value

    def calculate_cumulative_return(self, current_value: Decimal) -> Decimal:
        """Calculate cumulative return from inception.

        Args:
            current_value: Current portfolio value

        Returns:
            Cumulative return = (current_value / starting_cash) - 1
        """
        if self.starting_cash <= Decimal("0"):
            raise ValueError(f"Starting cash must be positive, got {self.starting_cash}")

        return (current_value / self.starting_cash) - Decimal("1")

    def calculate_leverage(self) -> Decimal:
        """Calculate current leverage ratio.

        Returns:
            Leverage = gross_position_value / net_liquidation_value

        Raises:
            ValueError: If net liquidation value is zero

        Note:
            - Leverage = 1.0 for fully invested portfolio (no margin)
            - Leverage > 1.0 indicates margin/leverage usage
            - Leverage < 1.0 indicates cash reserves
        """
        from decimal import Decimal as D

        net_liquidation_value = self.portfolio_value

        if net_liquidation_value == D("0"):
            raise ValueError("Cannot calculate leverage with zero portfolio value")

        # Calculate gross exposure (sum of absolute position values)
        gross_exposure = sum(
            (abs(pos.market_value) for pos in self.positions.values()),
            start=D("0"),
        )

        return gross_exposure / net_liquidation_value

    def calculate_shares_from_dollars(
        self,
        asset: Asset,
        dollar_amount: Decimal,
        price: Decimal,
    ) -> Decimal:
        """Calculate number of shares/units from dollar allocation.

        Args:
            asset: Asset to purchase
            dollar_amount: Dollar amount to invest
            price: Current asset price

        Returns:
            Quantity to purchase (fractional for crypto, integer for equities)

        Example:
            >>> # Crypto: fractional shares
            >>> ledger.calculate_shares_from_dollars(BTC, Decimal("100"), Decimal("50000"))
            Decimal('0.002')
            >>> # Equity: integer shares (rounded down)
            >>> ledger.calculate_shares_from_dollars(AAPL, Decimal("1000"), Decimal("155.50"))
            Decimal('6')
        """
        from decimal import ROUND_DOWN
        from decimal import Decimal as D

        if price <= D("0"):
            raise ValueError(f"Price must be positive, got {price}")

        # Calculate raw quantity
        quantity = dollar_amount / price

        # Get asset class to determine rounding behavior
        # Check if asset has asset_type attribute (for test mocks)
        asset_type = asset.asset_type if hasattr(asset, "asset_type") else type(asset).__name__

        if asset_type in ("Equity", "Stock"):
            # Round down to whole shares for equities
            return quantity.quantize(D("1"), rounding=ROUND_DOWN)
        elif asset_type in ("Cryptocurrency", "Crypto"):
            # Keep fractional shares for crypto
            config = self.config
            scale = config.get_scale("crypto")
            quantize_str = "0." + "0" * scale
            return quantity.quantize(D(quantize_str), rounding=ROUND_DOWN)
        else:
            # Default to rounding down for other asset types
            return quantity.quantize(D("1"), rounding=ROUND_DOWN)

    def get_position(self, asset: Asset) -> DecimalPosition | None:
        """Get position for asset, returns None if not found."""
        return self.positions.get(asset)

    def to_dict(self) -> dict:
        """Convert ledger to dictionary representation."""
        return {
            "starting_cash": str(self.starting_cash),
            "cash": str(self.cash),
            "portfolio_value": str(self.portfolio_value),
            "positions_value": str(self.positions_value),
            "positions": {
                (asset.symbol if hasattr(asset, "symbol") else str(asset)): pos.to_dict()
                for asset, pos in self.positions.items()
            },
        }

    def __repr__(self) -> str:
        """String representation of ledger."""
        return (
            f"DecimalLedger(cash={self.cash}, positions={len(self.positions)}, "
            f"portfolio_value={self.portfolio_value})"
        )
