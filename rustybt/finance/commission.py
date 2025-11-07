"""Commission models for calculating trading costs.

This module provides both legacy float-based commission models (for backward
compatibility with Zipline) and modern Decimal-based models (for RustyBT)
that ensure precise financial calculations.

Legacy Models:
    - CommissionModel: Abstract base for float-based commission models
    - NoCommission: Zero commission (testing only)
    - PerShare: Commission per share traded
    - PerContract: Commission per futures contract
    - PerTrade: Fixed commission per trade
    - PerFutureTrade: Fixed commission per futures trade
    - PerDollar: Commission as percentage of trade value

Modern Decimal-Based Models:
    - DecimalCommissionModel: Abstract base for Decimal-based models
    - PerShareCommission: Commission per share with Decimal precision
    - PercentageCommission: Percentage-based commission
    - TieredCommission: Volume-based tiered pricing
    - MakerTakerCommission: Maker/taker fee structure (crypto exchanges)

Examples:
    Using legacy per-share commission::

        from rustybt.finance.commission import PerShare
        commission_model = PerShare(cost=0.005, min_trade_cost=1.0)

    Using modern Decimal-based percentage commission::

        from decimal import Decimal
        from rustybt.finance.commission import PercentageCommission
        commission_model = PercentageCommission(
            percentage=Decimal("0.001"),  # 0.1%
            min_commission=Decimal("1.00")
        )
"""
#
# Copyright 2016 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from abc import abstractmethod
from collections import defaultdict

from toolz import merge

from rustybt.assets import Equity, Future
from rustybt.finance.constants import FUTURE_EXCHANGE_FEES_BY_SYMBOL
from rustybt.finance.shared import AllowedAssetMarker, FinancialModelMeta
from rustybt.utils.dummy import SingleValueMapping

DEFAULT_PER_SHARE_COST = 0.001  # 0.1 cents per share
DEFAULT_PER_CONTRACT_COST = 0.85  # $0.85 per future contract
DEFAULT_PER_DOLLAR_COST = 0.0015  # 0.15 cents per dollar
DEFAULT_MINIMUM_COST_PER_EQUITY_TRADE = 0.0  # $0 per trade
DEFAULT_MINIMUM_COST_PER_FUTURE_TRADE = 0.0  # $0 per trade


class CommissionModel(metaclass=FinancialModelMeta):
    """Abstract base class for commission models.

    Commission models are responsible for accepting order/transaction pairs and
    calculating how much commission should be charged to an algorithm's account
    on each transaction.

    To implement a new commission model, create a subclass of
    :class:`~zipline.finance.commission.CommissionModel` and implement
    :meth:`calculate`.
    """

    # Asset types that are compatible with the given model.
    allowed_asset_types = (Equity, Future)

    @abstractmethod
    def calculate(self, order, transaction):
        """Calculate the amount of commission to charge on an order.

        This method computes the additional commission to charge as a result
        of a transaction. A single order may generate multiple transactions
        if there isn't enough volume in a given bar to fill the full amount.

        Args:
            order: The order being processed. The commission field indicates
                the amount of commission already charged on this order.
            transaction: The transaction being processed.

        Returns:
            float: The additional commission in dollars to attribute to this order.

        Note:
            This is an abstract method that must be implemented by subclasses.
        """
        raise NotImplementedError("calculate")


class NoCommission(CommissionModel):
    """Model commissions as free.

    This commission model always returns zero commission cost. It is primarily
    used for testing and backtesting scenarios where commission costs should
    be excluded from analysis.

    Examples:
        >>> from rustybt.finance.commission import NoCommission
        >>> commission_model = NoCommission()
        >>> cost = commission_model.calculate(order, transaction)
        >>> assert cost == 0.0

    Note:
        This is primarily used for testing and zero-commission scenarios.
    """

    @staticmethod
    def calculate(order, transaction):
        """Calculate commission (always returns zero).

        Args:
            order: The order being processed (unused).
            transaction: The transaction being processed (unused).

        Returns:
            float: Always returns 0.0.
        """
        return 0.0


# todo: update to Python3
class EquityCommissionModel(CommissionModel, metaclass=AllowedAssetMarker):
    """Base class for commission models that only support equities.

    This is a specialized commission model base class that restricts
    commission calculations to equity assets only. Attempting to use
    this model with non-equity assets will result in an error.

    Attributes:
        allowed_asset_types: Tuple containing only the Equity class.

    Examples:
        >>> from rustybt.finance.commission import PerShare
        >>> commission = PerShare(cost=0.005)
        >>> isinstance(commission, EquityCommissionModel)
        True
    """

    allowed_asset_types = (Equity,)


# todo: update to Python3
class FutureCommissionModel(CommissionModel, metaclass=AllowedAssetMarker):
    """Base class for commission models that only support futures.

    This is a specialized commission model base class that restricts
    commission calculations to futures contracts only. Attempting to use
    this model with non-futures assets will result in an error.

    Attributes:
        allowed_asset_types: Tuple containing only the Future class.

    Examples:
        >>> from rustybt.finance.commission import PerContract
        >>> commission = PerContract(cost=0.85, exchange_fee=1.50)
        >>> isinstance(commission, FutureCommissionModel)
        True
    """

    allowed_asset_types = (Future,)


def calculate_per_unit_commission(
    order, transaction, cost_per_unit, initial_commission, min_trade_cost
):
    """Calculate commission for a per-unit commission model with minimum trade cost.

    This helper function implements the core logic for per-unit commission
    calculation (used by both per-share and per-contract models). It handles
    minimum commission requirements and one-time initial fees.

    The logic works as follows:

    - If no commission has been paid yet on the order:
        - Pay the maximum of (minimum trade cost) or (per-unit cost + initial fee)
    - If commission has already been paid on the order:
        - Calculate total per-unit commission for all fills so far
        - If below minimum threshold, don't charge additional commission yet
        - If above minimum threshold, charge the incremental amount

    Args:
        order: The order being filled. Must have 'commission' and 'filled' attributes.
        transaction: The transaction being processed. Must have 'amount' attribute.
        cost_per_unit: Commission cost per unit (share or contract).
        initial_commission: One-time fee charged on first fill (e.g., exchange fee).
        min_trade_cost: Minimum commission to charge for the entire order.

    Returns:
        float: The additional commission to charge for this transaction.

    Examples:
        >>> # First fill of an order with minimum commission
        >>> order.commission = 0  # No commission paid yet
        >>> order.filled = 0
        >>> transaction.amount = 100
        >>> calculate_per_unit_commission(order, transaction, 0.005, 0, 1.0)
        1.0  # Pays minimum of $1.00 instead of $0.50

        >>> # Subsequent fill after minimum met
        >>> order.commission = 1.0
        >>> order.filled = 100
        >>> transaction.amount = 100
        >>> calculate_per_unit_commission(order, transaction, 0.005, 0, 1.0)
        0.5  # Pays per-unit cost of $0.50
    """
    additional_commission = abs(transaction.amount * cost_per_unit)

    if order.commission == 0:
        # no commission paid yet, pay at least the minimum plus a one-time
        # exchange fee.
        return max(min_trade_cost, additional_commission + initial_commission)
    else:
        # we've already paid some commission, so figure out how much we
        # would be paying if we only counted per unit.
        per_unit_total = (
            abs(order.filled * cost_per_unit) + additional_commission + initial_commission
        )

        if per_unit_total < min_trade_cost:
            # if we haven't hit the minimum threshold yet, don't pay
            # additional commission
            return 0
        else:
            # we've exceeded the threshold, so pay more commission.
            return per_unit_total - order.commission


class PerShare(EquityCommissionModel):
    """Per-share commission model for equity trading.

    Calculates commission based on the number of shares traded, with an
    optional minimum commission per trade. This is the default commission
    model for equity trading in Zipline/RustyBT.

    Args:
        cost: The commission cost per share traded. Defaults to $0.001
            (one-tenth of a cent per share).
        min_trade_cost: The minimum commission per trade. Defaults to $0
            (no minimum). If specified, ensures that even small orders pay
            at least this much commission.

    Attributes:
        cost_per_share: The commission rate per share.
        min_trade_cost: The minimum commission threshold.

    Examples:
        >>> # Interactive Brokers-style: $0.005 per share, $1 minimum
        >>> commission = PerShare(cost=0.005, min_trade_cost=1.0)
        >>>
        >>> # Traditional broker: $0.01 per share, $5 minimum
        >>> commission = PerShare(cost=0.01, min_trade_cost=5.0)

    Note:
        This is Zipline's default commission model for equities.
    """

    def __init__(
        self,
        cost=DEFAULT_PER_SHARE_COST,
        min_trade_cost=DEFAULT_MINIMUM_COST_PER_EQUITY_TRADE,
    ):
        """Initialize per-share commission model.

        Args:
            cost: Commission per share (default: 0.001).
            min_trade_cost: Minimum commission per trade (default: 0).
        """
        self.cost_per_share = float(cost)
        self.min_trade_cost = min_trade_cost or 0

    def __repr__(self):
        """Return string representation of the commission model.

        Returns:
            str: String representation showing cost_per_share and min_trade_cost.
        """
        return (
            f"{self.__class__.__name__}(cost_per_share={self.cost_per_share}, "
            f"min_trade_cost={self.min_trade_cost})"
        )

    def calculate(self, order, transaction):
        """Calculate commission for a share transaction.

        Args:
            order: The order being filled.
            transaction: The transaction to calculate commission for.

        Returns:
            float: The commission amount for this transaction.
        """
        return calculate_per_unit_commission(
            order=order,
            transaction=transaction,
            cost_per_unit=self.cost_per_share,
            initial_commission=0,
            min_trade_cost=self.min_trade_cost,
        )


class PerContract(FutureCommissionModel):
    """Per-contract commission model for futures trading.

    Calculates commission based on the number of futures contracts traded,
    with support for contract-specific rates and exchange fees. Exchange
    fees are one-time charges per trade, regardless of contract quantity.

    Args:
        cost: Commission per contract traded. Can be either:
            - float: Same commission for all futures contracts
            - dict: Maps root symbols to commission costs per contract
        exchange_fee: Flat-rate exchange fee per trade. Can be either:
            - float: Same fee for all contracts
            - dict: Maps root symbols to exchange fees
        min_trade_cost: Minimum commission per trade (default: 0).

    Attributes:
        _cost_per_contract: Commission rate mapping by root symbol.
        _exchange_fee: Exchange fee mapping by root symbol.
        min_trade_cost: Minimum commission threshold.

    Examples:
        >>> # Fixed commission for all contracts
        >>> commission = PerContract(cost=0.85, exchange_fee=1.50)
        >>>
        >>> # Contract-specific commissions
        >>> commission = PerContract(
        ...     cost={'ES': 0.85, 'NQ': 1.00},
        ...     exchange_fee={'ES': 1.28, 'NQ': 1.28}
        ... )

    Note:
        If a root symbol is not found in the provided dictionaries,
        default values are used from FUTURE_EXCHANGE_FEES_BY_SYMBOL.
    """

    def __init__(
        self,
        cost,
        exchange_fee,
        min_trade_cost=DEFAULT_MINIMUM_COST_PER_FUTURE_TRADE,
    ):
        # If 'cost' or 'exchange fee' are constants, use a dummy mapping to
        # treat them as a dictionary that always returns the same value.
        # NOTE: These dictionary does not handle unknown root symbols, so it
        # may be worth revisiting this behavior.
        if isinstance(cost, (int, float)):
            self._cost_per_contract = SingleValueMapping(float(cost))
        else:
            # Cost per contract is a dictionary. If the user's dictionary does
            # not provide a commission cost for a certain contract, fall back
            # on the pre-defined cost values per root symbol.
            self._cost_per_contract = defaultdict(lambda: DEFAULT_PER_CONTRACT_COST, **cost)

        if isinstance(exchange_fee, (int, float)):
            self._exchange_fee = SingleValueMapping(float(exchange_fee))
        else:
            # Exchange fee is a dictionary. If the user's dictionary does not
            # provide an exchange fee for a certain contract, fall back on the
            # pre-defined exchange fees per root symbol.
            self._exchange_fee = merge(
                FUTURE_EXCHANGE_FEES_BY_SYMBOL,
                exchange_fee,
            )

        self.min_trade_cost = min_trade_cost or 0

    def __repr__(self):
        """Return string representation of the commission model.

        Returns:
            str: String representation showing costs and fees.
        """
        if isinstance(self._cost_per_contract, SingleValueMapping):
            # Cost per contract is a constant, so extract it.
            cost_per_contract = self._cost_per_contract["dummy key"]
        else:
            cost_per_contract = "<varies>"

        if isinstance(self._exchange_fee, SingleValueMapping):
            # Exchange fee is a constant, so extract it.
            exchange_fee = self._exchange_fee["dummy key"]
        else:
            exchange_fee = "<varies>"

        return (
            f"{self.__class__.__name__}(cost_per_contract={cost_per_contract}, "
            f"exchange_fee={exchange_fee}, min_trade_cost={self.min_trade_cost})"
        )

    def calculate(self, order, transaction):
        """Calculate commission for a futures contract transaction.

        Retrieves the contract-specific commission rate and exchange fee
        based on the contract's root symbol, then applies the per-unit
        commission calculation logic.

        Args:
            order: The futures order being filled.
            transaction: The transaction to calculate commission for.

        Returns:
            float: The commission amount for this transaction.
        """
        root_symbol = order.asset.root_symbol
        cost_per_contract = self._cost_per_contract[root_symbol]
        exchange_fee = self._exchange_fee[root_symbol]

        return calculate_per_unit_commission(
            order=order,
            transaction=transaction,
            cost_per_unit=cost_per_contract,
            initial_commission=exchange_fee,
            min_trade_cost=self.min_trade_cost,
        )


class PerTrade(CommissionModel):
    """Fixed commission per trade model.

    Charges a flat commission amount per trade, regardless of the number
    of shares or contracts traded. For orders that require multiple fills,
    the full commission is charged on the first fill only.

    This model is common with traditional discount brokers that charge
    a flat fee per trade (e.g., $5 per trade regardless of size).

    Args:
        cost: The flat commission amount per trade (default: 0).

    Attributes:
        cost: The fixed commission per trade.

    Examples:
        >>> # Traditional discount broker: $5 per trade
        >>> commission = PerTrade(cost=5.0)
        >>>
        >>> # Zero commission broker
        >>> commission = PerTrade(cost=0.0)

    Note:
        For orders that fill across multiple bars, commission is only
        charged once on the first fill.
    """

    def __init__(self, cost=DEFAULT_MINIMUM_COST_PER_EQUITY_TRADE):
        """Initialize per-trade commission model.

        Args:
            cost: Fixed commission per trade. $5.00 per trade is fairly
                typical of discount brokers.
        """
        # Cost needs to be floating point so that calculation using division
        # logic does not floor to an integer.
        self.cost = float(cost)

    def __repr__(self):
        """Return string representation of the commission model.

        Returns:
            str: String representation showing cost_per_trade.
        """
        return f"{self.__class__.__name__}(cost_per_trade={self.cost})"

    def calculate(self, order, transaction):
        """Calculate commission for a trade.

        Charges the full commission on the first fill, then zero for
        subsequent fills of the same order.

        Args:
            order: The order being filled.
            transaction: The transaction to calculate commission for.

        Returns:
            float: The commission amount (cost on first fill, 0 thereafter).
        """
        if order.commission == 0:
            # if the order hasn't had a commission attributed to it yet,
            # that's what we need to pay.
            return self.cost
        else:
            # order has already had commission attributed, so no more
            # commission.
            return 0.0


class PerFutureTrade(PerContract):
    """Fixed commission per futures trade model.

    Charges a flat commission per futures trade, regardless of the number
    of contracts traded. Internally, this is implemented as a per-contract
    model with zero per-contract cost and the trade cost as an exchange fee,
    since exchange fees are one-time charges.

    Args:
        cost: The flat commission per trade. Can be either:
            - float: Same commission for all futures contracts
            - dict: Maps root symbols to commission costs per trade

    Attributes:
        _cost_per_trade: The per-trade commission (alias for _exchange_fee).

    Examples:
        >>> # Fixed $2.50 per trade for all contracts
        >>> commission = PerFutureTrade(cost=2.50)
        >>>
        >>> # Contract-specific per-trade costs
        >>> commission = PerFutureTrade(cost={'ES': 2.50, 'NQ': 3.00})

    Note:
        The per-trade cost is represented as an exchange fee because both
        are one-time charges incurred on the first fill.
    """

    def __init__(self, cost=DEFAULT_MINIMUM_COST_PER_FUTURE_TRADE):
        """Initialize per-futures-trade commission model.

        Args:
            cost: Fixed commission per futures trade (default: 0).
        """
        # The per-trade cost can be represented as the exchange fee in a
        # per-contract model because the exchange fee is just a one time cost
        # incurred on the first fill.
        super(PerFutureTrade, self).__init__(
            cost=0,
            exchange_fee=cost,
            min_trade_cost=0,
        )
        self._cost_per_trade = self._exchange_fee

    def __repr__(self):
        """Return string representation of the commission model.

        Returns:
            str: String representation showing cost_per_trade.
        """
        if isinstance(self._cost_per_trade, SingleValueMapping):
            # Cost per trade is a constant, so extract it.
            cost_per_trade = self._cost_per_trade["dummy key"]
        else:
            cost_per_trade = "<varies>"
        return f"{self.__class__.__name__}(cost_per_trade={cost_per_trade})"


class PerDollar(EquityCommissionModel):
    """Percentage-based commission model (per dollar transacted).

    Charges commission as a fixed percentage of the total dollar value
    of the transaction. This model is common with some brokers and for
    large institutional trades.

    Args:
        cost: Commission rate per dollar transacted (default: 0.0015,
            which is 0.15% or 15 basis points).

    Attributes:
        cost_per_dollar: The commission rate as a decimal fraction.

    Examples:
        >>> # 0.15% commission (15 basis points)
        >>> commission = PerDollar(cost=0.0015)
        >>> # On a $100,000 trade: $100,000 * 0.0015 = $150 commission
        >>>
        >>> # 0.1% commission (10 basis points)
        >>> commission = PerDollar(cost=0.001)

    Note:
        A cost of 0.0015 on a $1 million trade means $1,500 commission.
    """

    def __init__(self, cost=DEFAULT_PER_DOLLAR_COST):
        """Initialize per-dollar commission model.

        Args:
            cost: Commission per dollar. A value of 0.0015 means
                0.15% commission on the transaction value.
        """
        self.cost_per_dollar = float(cost)

    def __repr__(self):
        """Return string representation of the commission model.

        Returns:
            str: String representation showing cost_per_dollar.
        """
        return f"{self.__class__.__name__}(cost_per_dollar={self.cost_per_dollar})"

    def calculate(self, order, transaction):
        """Calculate commission based on dollar value of transaction.

        Commission is calculated as: price * shares * cost_per_dollar

        Args:
            order: The order being filled (unused).
            transaction: The transaction to calculate commission for.

        Returns:
            float: The commission amount based on transaction value.
        """
        cost_per_share = transaction.price * self.cost_per_dollar
        return abs(transaction.amount) * cost_per_share


# ============================================================================
# Decimal-Based Commission Models (RustyBT)
# ============================================================================

from abc import ABC
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger()


# Exceptions
class CommissionConfigurationError(Exception):
    """Raised when commission model configuration is invalid.

    This exception is raised during commission model initialization when
    the provided configuration parameters are invalid or inconsistent.

    Examples:
        >>> from rustybt.finance.commission import TieredCommission
        >>> try:
        ...     commission = TieredCommission(tiers={})  # Empty tiers
        ... except CommissionConfigurationError as e:
        ...     print(f"Configuration error: {e}")
    """

    pass


class CommissionCalculationError(Exception):
    """Raised when commission calculation fails.

    This exception is raised during runtime when a commission calculation
    cannot be completed due to invalid data or calculation errors.

    Examples:
        >>> # This would be raised internally if price data is unavailable
        >>> raise CommissionCalculationError("Cannot calculate commission: missing price data")
    """

    pass


@dataclass(frozen=True)
class CommissionResult:
    """Result of a commission calculation.

    This immutable dataclass encapsulates all information about a calculated
    commission, including the amount, model used, and any additional metadata
    such as tier information or maker/taker status.

    Attributes:
        commission: The total commission amount as a Decimal.
        model_name: The name of the commission model that generated this result.
        tier_applied: The tier name if using a tiered commission model (optional).
        maker_taker: "maker" or "taker" if using maker/taker pricing (optional).
        metadata: Additional data about the calculation (e.g., rates, volumes).

    Examples:
        >>> from decimal import Decimal
        >>> result = CommissionResult(
        ...     commission=Decimal("5.25"),
        ...     model_name="PerShareCommission",
        ...     metadata={"cost_per_share": "0.005", "shares": "1050"}
        ... )
        >>> print(f"Commission: ${result.commission}")
        Commission: $5.25
    """

    commission: Decimal  # Total commission amount
    model_name: str  # Name of commission model used
    tier_applied: str | None = None  # Tier name if applicable
    maker_taker: str | None = None  # "maker" or "taker" if applicable
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional data


class DecimalCommissionModel(ABC):
    """Abstract base class for Decimal-based commission models.

    This is the RustyBT version that uses Python's Decimal type for precise
    financial calculations, avoiding floating-point rounding errors that can
    accumulate in trading simulations.

    All modern RustyBT commission models should inherit from this class rather
    than the legacy float-based CommissionModel. Decimal precision ensures
    that commission calculations are accurate to the penny even after millions
    of trades.

    Attributes:
        min_commission: Minimum commission amount per order (Decimal).

    Examples:
        >>> from decimal import Decimal
        >>> from rustybt.finance.commission import PerShareCommission
        >>> commission = PerShareCommission(
        ...     cost_per_share=Decimal("0.005"),
        ...     min_commission=Decimal("1.00")
        ... )

    Note:
        For legacy float-based models, see CommissionModel above.
    """

    def __init__(self, min_commission: Decimal = Decimal("0")):
        """Initialize commission model.

        Args:
            min_commission: Minimum commission amount per order (default: 0).
                Ensures that even small orders pay at least this amount.
        """
        self.min_commission = min_commission

    @abstractmethod
    def calculate_commission(
        self,
        order: Any,
        fill_price: Decimal,
        fill_quantity: Decimal,
        current_time: pd.Timestamp,
    ) -> CommissionResult:
        """Calculate commission for an order fill.

        This is the primary method that subclasses must implement. It computes
        the commission for a specific fill (partial or complete) of an order.

        Args:
            order: The order being filled. Must have 'id' and 'asset' attributes.
            fill_price: The price at which the order was filled (Decimal).
            fill_quantity: The quantity filled in this transaction (Decimal).
                Can be negative for sell orders.
            current_time: The current simulation timestamp.

        Returns:
            CommissionResult: Object containing the commission amount and metadata.

        Note:
            Implementations should use absolute value of fill_quantity for
            commission calculations, as commissions are always positive costs.
        """
        pass

    def apply_minimum(self, commission: Decimal) -> tuple[Decimal, bool]:
        """Apply minimum commission threshold.

        Ensures that the commission is at least equal to the configured
        minimum commission amount. This is useful for brokers that charge
        a minimum fee per trade.

        Args:
            commission: The calculated commission amount (Decimal).

        Returns:
            tuple[Decimal, bool]: A tuple containing:
                - The final commission (max of calculated or minimum)
                - A boolean flag indicating if minimum was applied (True if yes)

        Examples:
            >>> model = PerShareCommission(
            ...     cost_per_share=Decimal("0.005"),
            ...     min_commission=Decimal("1.00")
            ... )
            >>> # Small trade: $0.50 calculated, $1.00 minimum
            >>> final, applied = model.apply_minimum(Decimal("0.50"))
            >>> assert final == Decimal("1.00") and applied is True
            >>>
            >>> # Large trade: $5.00 calculated, no minimum needed
            >>> final, applied = model.apply_minimum(Decimal("5.00"))
            >>> assert final == Decimal("5.00") and applied is False
        """
        if commission < self.min_commission:
            logger.debug(
                "minimum_commission_applied",
                calculated=str(commission),
                minimum=str(self.min_commission),
            )
            return self.min_commission, True
        return commission, False


class PerShareCommission(DecimalCommissionModel):
    """Decimal-based per-share commission model.

    Calculates commission as: commission = |shares| × cost_per_share

    This model is common for US equity brokers such as Interactive Brokers
    (typically $0.005 per share with a $1 minimum). Uses Decimal arithmetic
    for precise financial calculations.

    Args:
        cost_per_share: Commission cost per share as a Decimal (e.g., "0.005").
        min_commission: Minimum commission per order (default: "1.00").

    Attributes:
        cost_per_share: The commission rate per share.

    Examples:
        >>> from decimal import Decimal
        >>> # Interactive Brokers-style: $0.005/share, $1 minimum
        >>> commission = PerShareCommission(
        ...     cost_per_share=Decimal("0.005"),
        ...     min_commission=Decimal("1.00")
        ... )
        >>>
        >>> # Calculate commission for 100 shares at $50.00
        >>> result = commission.calculate_commission(
        ...     order=order,
        ...     fill_price=Decimal("50.00"),
        ...     fill_quantity=Decimal("100"),
        ...     current_time=pd.Timestamp("2024-01-01")
        ... )
        >>> assert result.commission == Decimal("1.00")  # Minimum applied
        >>>
        >>> # Calculate commission for 500 shares at $50.00
        >>> result = commission.calculate_commission(
        ...     order=order,
        ...     fill_price=Decimal("50.00"),
        ...     fill_quantity=Decimal("500"),
        ...     current_time=pd.Timestamp("2024-01-01")
        ... )
        >>> assert result.commission == Decimal("2.50")  # 500 * 0.005

    Note:
        This is the modern Decimal-based version. For the legacy float-based
        version, see PerShare.
    """

    def __init__(self, cost_per_share: Decimal, min_commission: Decimal = Decimal("1.00")):
        """Initialize per-share commission model.

        Args:
            cost_per_share: Commission per share (e.g., Decimal("0.005")).
            min_commission: Minimum commission per order (default: Decimal("1.00")).
        """
        super().__init__(min_commission)
        self.cost_per_share = cost_per_share

    def calculate_commission(
        self,
        order: Any,
        fill_price: Decimal,
        fill_quantity: Decimal,
        current_time: pd.Timestamp,
    ) -> CommissionResult:
        """Calculate per-share commission for an order fill.

        Computes commission as the absolute quantity times the cost per share,
        then applies the minimum commission threshold if configured.

        Args:
            order: The order being filled.
            fill_price: Price at which order was filled (unused for per-share model).
            fill_quantity: Quantity filled (positive for buys, negative for sells).
            current_time: Current simulation timestamp (unused).

        Returns:
            CommissionResult: Contains commission amount and metadata including:
                - commission: The calculated commission amount
                - model_name: "PerShareCommission"
                - metadata: Dict with cost_per_share, fill_quantity, and minimum_applied flag

        Examples:
            >>> commission = PerShareCommission(
            ...     cost_per_share=Decimal("0.005"),
            ...     min_commission=Decimal("1.00")
            ... )
            >>> result = commission.calculate_commission(
            ...     order=order,
            ...     fill_price=Decimal("50.00"),
            ...     fill_quantity=Decimal("100"),
            ...     current_time=pd.Timestamp("2024-01-01")
            ... )
            >>> print(result.commission)  # Decimal("1.00") - minimum applied
            >>> print(result.metadata["minimum_applied"])  # True
        """
        # Use absolute value for commission calculation
        abs_quantity = abs(fill_quantity)

        # Calculate base commission
        commission = abs_quantity * self.cost_per_share

        # Apply minimum
        commission, min_applied = self.apply_minimum(commission)

        metadata = {
            "cost_per_share": str(self.cost_per_share),
            "fill_quantity": str(fill_quantity),
            "minimum_applied": min_applied,
        }

        logger.info(
            "per_share_commission_calculated",
            order_id=order.id,
            asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            commission=str(commission),
            shares=str(abs_quantity),
            rate=str(self.cost_per_share),
        )

        return CommissionResult(
            commission=commission, model_name="PerShareCommission", metadata=metadata
        )


class PercentageCommission(DecimalCommissionModel):
    """Decimal-based percentage commission model.

    Calculates commission as: commission = |trade_value| × percentage

    Where trade_value = fill_price × fill_quantity

    This model is common for international brokers, small accounts, and
    cryptocurrency exchanges. Commission is calculated as a percentage of
    the total transaction value.

    Args:
        percentage: Commission rate as a decimal fraction (e.g., Decimal("0.001")
            for 0.1% or 10 basis points).
        min_commission: Minimum commission per order (default: Decimal("0")).

    Attributes:
        percentage: The commission rate as a decimal fraction.

    Examples:
        >>> from decimal import Decimal
        >>> # 0.1% commission (10 basis points), $5 minimum
        >>> commission = PercentageCommission(
        ...     percentage=Decimal("0.001"),
        ...     min_commission=Decimal("5.00")
        ... )
        >>>
        >>> # Trade: 100 shares at $50.00 = $5,000 value
        >>> result = commission.calculate_commission(
        ...     order=order,
        ...     fill_price=Decimal("50.00"),
        ...     fill_quantity=Decimal("100"),
        ...     current_time=pd.Timestamp("2024-01-01")
        ... )
        >>> assert result.commission == Decimal("5.00")  # $5,000 * 0.001
        >>>
        >>> # Small trade: 10 shares at $10.00 = $100 value
        >>> result = commission.calculate_commission(
        ...     order=order,
        ...     fill_price=Decimal("10.00"),
        ...     fill_quantity=Decimal("10"),
        ...     current_time=pd.Timestamp("2024-01-01")
        ... )
        >>> assert result.commission == Decimal("5.00")  # Minimum applied

    Note:
        A percentage of 0.001 equals 0.1% or 10 basis points (bps).
    """

    def __init__(
        self,
        percentage: Decimal,
        min_commission: Decimal = Decimal("0"),  # As decimal (e.g., 0.001 = 0.1%)
    ):
        """Initialize percentage commission model.

        Args:
            percentage: Commission rate as decimal fraction (e.g., Decimal("0.001") = 0.1%).
            min_commission: Minimum commission per order (default: Decimal("0")).
        """
        super().__init__(min_commission)
        self.percentage = percentage

    def calculate_commission(
        self,
        order: Any,
        fill_price: Decimal,
        fill_quantity: Decimal,
        current_time: pd.Timestamp,
    ) -> CommissionResult:
        """Calculate percentage commission for an order fill.

        Computes commission as trade value (price × quantity) times the
        percentage rate, then applies the minimum commission threshold.

        Args:
            order: The order being filled.
            fill_price: Price at which order was filled.
            fill_quantity: Quantity filled (positive for buys, negative for sells).
            current_time: Current simulation timestamp (unused).

        Returns:
            CommissionResult: Contains commission amount and metadata including:
                - commission: The calculated commission amount
                - model_name: "PercentageCommission"
                - metadata: Dict with percentage, percentage_bps, trade_value,
                    and minimum_applied flag

        Examples:
            >>> commission = PercentageCommission(
            ...     percentage=Decimal("0.001"),
            ...     min_commission=Decimal("5.00")
            ... )
            >>> result = commission.calculate_commission(
            ...     order=order,
            ...     fill_price=Decimal("50.00"),
            ...     fill_quantity=Decimal("100"),
            ...     current_time=pd.Timestamp("2024-01-01")
            ... )
            >>> print(result.commission)  # Decimal("5.00")
            >>> print(result.metadata["trade_value"])  # "5000"
            >>> print(result.metadata["percentage_bps"])  # "10" (10 basis points)
        """
        # Use absolute value for commission calculation
        abs_quantity = abs(fill_quantity)

        # Calculate trade value
        trade_value = fill_price * abs_quantity

        # Calculate base commission
        commission = trade_value * self.percentage

        # Apply minimum
        commission, min_applied = self.apply_minimum(commission)

        metadata = {
            "percentage": str(self.percentage),
            "percentage_bps": str(self.percentage * Decimal("10000")),
            "trade_value": str(trade_value),
            "minimum_applied": min_applied,
        }

        logger.info(
            "percentage_commission_calculated",
            order_id=order.id,
            asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            commission=str(commission),
            trade_value=str(trade_value),
            percentage=str(self.percentage * Decimal("100")),
        )

        return CommissionResult(
            commission=commission, model_name="PercentageCommission", metadata=metadata
        )


class VolumeTracker:
    """Tracks cumulative trading volume for tiered commission calculations.

    This class maintains a rolling history of trading volume organized by
    month. It automatically resets volumes at month boundaries and provides
    volume lookup for tiered commission models.

    Attributes:
        monthly_volumes: Dictionary mapping month keys (YYYY-MM) to Decimal volumes.
        current_month: The currently active month (YYYY-MM format).
        logger: Structured logger for volume tracking events.

    Examples:
        >>> tracker = VolumeTracker()
        >>> volume = tracker.get_monthly_volume(pd.Timestamp("2024-01-15"))
        >>> assert volume == Decimal("0")  # No trades yet
        >>>
        >>> tracker.add_volume(Decimal("10000"), pd.Timestamp("2024-01-15"))
        >>> tracker.add_volume(Decimal("5000"), pd.Timestamp("2024-01-15"))
        >>> volume = tracker.get_monthly_volume(pd.Timestamp("2024-01-15"))
        >>> assert volume == Decimal("15000")
        >>>
        >>> # New month resets
        >>> volume = tracker.get_monthly_volume(pd.Timestamp("2024-02-01"))
        >>> assert volume == Decimal("0")

    Note:
        Volume is tracked cumulatively within each calendar month.
        The tracker automatically detects month boundaries and resets.
    """

    def __init__(self):
        """Initialize volume tracker with empty volume history."""
        self.monthly_volumes: dict[str, Decimal] = {}
        self.current_month: str | None = None
        self.logger = structlog.get_logger()

    def get_monthly_volume(self, current_time: pd.Timestamp) -> Decimal:
        """Get accumulated volume for the current month.

        Retrieves the cumulative trading volume for the month containing
        current_time. Automatically detects and handles month transitions.

        Args:
            current_time: The current simulation timestamp.

        Returns:
            Decimal: The accumulated volume for the current month. Returns
                Decimal("0") if no trades have occurred this month.

        Examples:
            >>> tracker = VolumeTracker()
            >>> volume = tracker.get_monthly_volume(pd.Timestamp("2024-01-15"))
            >>> assert volume == Decimal("0")
        """
        month_key = current_time.strftime("%Y-%m")

        # Reset if new month
        if self.current_month != month_key:
            if self.current_month is not None:
                self.logger.info(
                    "volume_tracker_month_reset",
                    old_month=self.current_month,
                    new_month=month_key,
                    old_volume=str(self.monthly_volumes.get(self.current_month, Decimal("0"))),
                )
            self.current_month = month_key

        return self.monthly_volumes.get(month_key, Decimal("0"))

    def add_volume(self, trade_value: Decimal, current_time: pd.Timestamp):
        """Add trade volume to the current month's cumulative total.

        Increments the volume for the month containing current_time. If this
        is a new month, automatically initializes the month before adding volume.

        Args:
            trade_value: The dollar value of the trade to add (Decimal).
            current_time: The current simulation timestamp.

        Examples:
            >>> tracker = VolumeTracker()
            >>> tracker.add_volume(Decimal("10000"), pd.Timestamp("2024-01-15"))
            >>> tracker.add_volume(Decimal("5000"), pd.Timestamp("2024-01-15"))
            >>> volume = tracker.get_monthly_volume(pd.Timestamp("2024-01-15"))
            >>> assert volume == Decimal("15000")
        """
        month_key = current_time.strftime("%Y-%m")

        # Ensure current month is set
        if self.current_month != month_key:
            self.get_monthly_volume(current_time)

        current = self.monthly_volumes.get(month_key, Decimal("0"))
        self.monthly_volumes[month_key] = current + trade_value

        self.logger.debug(
            "volume_added_to_tracker",
            month=month_key,
            trade_value=str(trade_value),
            total_volume=str(self.monthly_volumes[month_key]),
        )


class TieredCommission(DecimalCommissionModel):
    """Tiered commission model with volume discounts.

    Commission rate depends on cumulative monthly trading volume.
    Higher volume → lower commission rates.

    Example tiers (Interactive Brokers-style):
    - $0 - $100k: 0.10% (10 bps)
    - $100k - $1M: 0.05% (5 bps)
    - $1M+: 0.02% (2 bps)
    """

    def __init__(
        self,
        tiers: dict[Decimal, Decimal],  # {volume_threshold: commission_rate}
        min_commission: Decimal = Decimal("0"),
        volume_tracker: VolumeTracker | None = None,
    ):
        """Initialize tiered commission model.

        Args:
            tiers: Dictionary mapping volume thresholds to commission rates
                   e.g., {Decimal("0"): Decimal("0.001"), Decimal("100000"): Decimal("0.0005")}
            min_commission: Minimum commission per order
            volume_tracker: Volume tracker instance (created if None)
        """
        super().__init__(min_commission)

        if not tiers:
            raise CommissionConfigurationError("Tiers dictionary cannot be empty")

        # Sort tiers by threshold (descending) for efficient lookup
        self.tiers = sorted(tiers.items(), key=lambda x: x[0], reverse=True)

        # Create or use provided volume tracker
        self.volume_tracker = volume_tracker or VolumeTracker()

    def calculate_commission(
        self,
        order: Any,
        fill_price: Decimal,
        fill_quantity: Decimal,
        current_time: pd.Timestamp,
    ) -> CommissionResult:
        """Calculate tiered commission based on monthly volume."""
        # Get current monthly volume
        monthly_volume = self.volume_tracker.get_monthly_volume(current_time)

        # Determine applicable tier
        rate = self.tiers[-1][1]  # Default to lowest tier (highest rate)
        tier_threshold = self.tiers[-1][0]
        tier_name = "base"

        for threshold, tier_rate in self.tiers:
            if monthly_volume >= threshold:
                rate = tier_rate
                tier_threshold = threshold
                tier_name = f"tier_{threshold}"
                break

        # Use absolute value for commission calculation
        abs_quantity = abs(fill_quantity)

        # Calculate trade value
        trade_value = fill_price * abs_quantity

        # Calculate commission
        commission = trade_value * rate

        # Apply minimum
        commission, min_applied = self.apply_minimum(commission)

        # Add this trade to volume tracker
        self.volume_tracker.add_volume(trade_value, current_time)

        metadata = {
            "tier_name": tier_name,
            "tier_threshold": str(tier_threshold),
            "tier_rate": str(rate),
            "monthly_volume_before": str(monthly_volume),
            "monthly_volume_after": str(monthly_volume + trade_value),
            "trade_value": str(trade_value),
            "minimum_applied": min_applied,
        }

        logger.info(
            "tiered_commission_calculated",
            order_id=order.id,
            asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            commission=str(commission),
            tier=tier_name,
            monthly_volume=str(monthly_volume),
            rate_bps=str(rate * Decimal("10000")),
        )

        return CommissionResult(
            commission=commission,
            model_name="TieredCommission",
            tier_applied=tier_name,
            metadata=metadata,
        )


class MakerTakerCommission(DecimalCommissionModel):
    """Maker/taker commission model for crypto exchanges.

    Maker orders (add liquidity): typically lower or rebated commission
    Taker orders (remove liquidity): typically higher commission

    Example (Binance):
    - Maker: 0.02% (2 bps) or -0.01% (rebate)
    - Taker: 0.04% (4 bps)
    """

    def __init__(
        self,
        maker_rate: Decimal,  # Can be negative for rebates
        taker_rate: Decimal,
        min_commission: Decimal = Decimal("0"),
    ):
        """Initialize maker/taker commission model.

        Args:
            maker_rate: Commission rate for maker orders (can be negative)
            taker_rate: Commission rate for taker orders
            min_commission: Minimum commission per order
        """
        super().__init__(min_commission)
        self.maker_rate = maker_rate
        self.taker_rate = taker_rate

    def calculate_commission(
        self,
        order: Any,
        fill_price: Decimal,
        fill_quantity: Decimal,
        current_time: pd.Timestamp,
    ) -> CommissionResult:
        """Calculate maker/taker commission."""
        # Determine if maker or taker
        is_maker = self._is_maker_order(order)

        rate = self.maker_rate if is_maker else self.taker_rate
        maker_taker = "maker" if is_maker else "taker"

        # Use absolute value for commission calculation
        abs_quantity = abs(fill_quantity)

        # Calculate trade value
        trade_value = fill_price * abs_quantity

        # Calculate commission (can be negative for maker rebates)
        commission = trade_value * rate

        # Apply minimum (only for positive commissions)
        if commission > Decimal("0"):
            commission, min_applied = self.apply_minimum(commission)
        else:
            min_applied = False

        metadata = {
            "maker_taker": maker_taker,
            "rate": str(rate),
            "rate_bps": str(rate * Decimal("10000")),
            "trade_value": str(trade_value),
            "minimum_applied": min_applied,
            "is_rebate": commission < Decimal("0"),
        }

        logger.info(
            "maker_taker_commission_calculated",
            order_id=order.id,
            asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            commission=str(commission),
            maker_taker=maker_taker,
            rate_bps=str(rate * Decimal("10000")),
            is_rebate=commission < Decimal("0"),
        )

        return CommissionResult(
            commission=commission,
            model_name="MakerTakerCommission",
            maker_taker=maker_taker,
            metadata=metadata,
        )

    def _is_maker_order(self, order: Any) -> bool:
        """Determine if order is maker or taker.

        Args:
            order: Order object

        Returns:
            True if maker order, False if taker
        """
        # Check order type
        if hasattr(order, "order_type"):
            if order.order_type == "market":
                return False  # Market orders always take liquidity

            if order.order_type == "limit":
                # Check if order has immediate fill flag
                if hasattr(order, "immediate_fill"):
                    return not order.immediate_fill
                # Default: limit orders are makers
                return True

        # Default to taker if uncertain
        return False
