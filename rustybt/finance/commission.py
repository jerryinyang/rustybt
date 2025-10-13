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
        """
        Calculate the amount of commission to charge on ``order`` as a result
        of ``transaction``.

        Parameters
        ----------
        order : zipline.finance.order.Order
            The order being processed.

            The ``commission`` field of ``order`` is a float indicating the
            amount of commission already charged on this order.

        transaction : zipline.finance.transaction.Transaction
            The transaction being processed. A single order may generate
            multiple transactions if there isn't enough volume in a given bar
            to fill the full amount requested in the order.

        Returns:
        -------
        amount_charged : float
            The additional commission, in dollars, that we should attribute to
            this order.
        """
        raise NotImplementedError("calculate")


class NoCommission(CommissionModel):
    """Model commissions as free.

    Notes:
    -----
    This is primarily used for testing.
    """

    @staticmethod
    def calculate(order, transaction):
        return 0.0


# todo: update to Python3
class EquityCommissionModel(CommissionModel, metaclass=AllowedAssetMarker):
    """
    Base class for commission models which only support equities.
    """

    allowed_asset_types = (Equity,)


# todo: update to Python3
class FutureCommissionModel(CommissionModel, metaclass=AllowedAssetMarker):
    """
    Base class for commission models which only support futures.
    """

    allowed_asset_types = (Future,)


def calculate_per_unit_commission(
    order, transaction, cost_per_unit, initial_commission, min_trade_cost
):
    """
    If there is a minimum commission:
        If the order hasn't had a commission paid yet, pay the minimum
        commission.

        If the order has paid a commission, start paying additional
        commission once the minimum commission has been reached.

    If there is no minimum commission:
        Pay commission based on number of units in the transaction.
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
    """
    Calculates a commission for a transaction based on a per share cost with
    an optional minimum cost per trade.

    Parameters
    ----------
    cost : float, optional
        The amount of commissions paid per share traded. Default is one tenth
        of a cent per share.
    min_trade_cost : float, optional
        The minimum amount of commissions paid per trade. Default is no
        minimum.

    Notes:
    -----
    This is zipline's default commission model for equities.
    """

    def __init__(
        self,
        cost=DEFAULT_PER_SHARE_COST,
        min_trade_cost=DEFAULT_MINIMUM_COST_PER_EQUITY_TRADE,
    ):
        self.cost_per_share = float(cost)
        self.min_trade_cost = min_trade_cost or 0

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(cost_per_share={self.cost_per_share}, "
            f"min_trade_cost={self.min_trade_cost})"
        )

    def calculate(self, order, transaction):
        return calculate_per_unit_commission(
            order=order,
            transaction=transaction,
            cost_per_unit=self.cost_per_share,
            initial_commission=0,
            min_trade_cost=self.min_trade_cost,
        )


class PerContract(FutureCommissionModel):
    """
    Calculates a commission for a transaction based on a per contract cost with
    an optional minimum cost per trade.

    Parameters
    ----------
    cost : float or dict
        The amount of commissions paid per contract traded. If given a float,
        the commission for all futures contracts is the same. If given a
        dictionary, it must map root symbols to the commission cost for
        contracts of that symbol.
    exchange_fee : float or dict
        A flat-rate fee charged by the exchange per trade. This value is a
        constant, one-time charge no matter how many contracts are being
        traded. If given a float, the fee for all contracts is the same. If
        given a dictionary, it must map root symbols to the fee for contracts
        of that symbol.
    min_trade_cost : float, optional
        The minimum amount of commissions paid per trade.
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
    """
    Calculates a commission for a transaction based on a per trade cost.

    For orders that require multiple fills, the full commission is charged to
    the first fill.

    Parameters
    ----------
    cost : float, optional
        The flat amount of commissions paid per equity trade.
    """

    def __init__(self, cost=DEFAULT_MINIMUM_COST_PER_EQUITY_TRADE):
        """
        Cost parameter is the cost of a trade, regardless of share count.
        $5.00 per trade is fairly typical of discount brokers.
        """
        # Cost needs to be floating point so that calculation using division
        # logic does not floor to an integer.
        self.cost = float(cost)

    def __repr__(self):
        return f"{self.__class__.__name__}(cost_per_trade={self.cost})"

    def calculate(self, order, transaction):
        """
        If the order hasn't had a commission paid yet, pay the fixed
        commission.
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
    """
    Calculates a commission for a transaction based on a per trade cost.

    Parameters
    ----------
    cost : float or dict
        The flat amount of commissions paid per trade, regardless of the number
        of contracts being traded. If given a float, the commission for all
        futures contracts is the same. If given a dictionary, it must map root
        symbols to the commission cost for trading contracts of that symbol.
    """

    def __init__(self, cost=DEFAULT_MINIMUM_COST_PER_FUTURE_TRADE):
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
        if isinstance(self._cost_per_trade, SingleValueMapping):
            # Cost per trade is a constant, so extract it.
            cost_per_trade = self._cost_per_trade["dummy key"]
        else:
            cost_per_trade = "<varies>"
        return f"{self.__class__.__name__}(cost_per_trade={cost_per_trade})"


class PerDollar(EquityCommissionModel):
    """
    Model commissions by applying a fixed cost per dollar transacted.

    Parameters
    ----------
    cost : float, optional
        The flat amount of commissions paid per dollar of equities
        traded. Default is a commission of $0.0015 per dollar transacted.
    """

    def __init__(self, cost=DEFAULT_PER_DOLLAR_COST):
        """
        Cost parameter is the cost of a trade per-dollar. 0.0015
        on $1 million means $1,500 commission (=1M * 0.0015)
        """
        self.cost_per_dollar = float(cost)

    def __repr__(self):
        return f"{self.__class__.__name__}(cost_per_dollar={self.cost_per_dollar})"

    def calculate(self, order, transaction):
        """
        Pay commission based on dollar value of shares.
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
    """Raised when commission model configuration is invalid."""

    pass


class CommissionCalculationError(Exception):
    """Raised when commission calculation fails."""

    pass


@dataclass(frozen=True)
class CommissionResult:
    """Result of commission calculation."""

    commission: Decimal  # Total commission amount
    model_name: str  # Name of commission model used
    tier_applied: str | None = None  # Tier name if applicable
    maker_taker: str | None = None  # "maker" or "taker" if applicable
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional data


class DecimalCommissionModel(ABC):
    """Abstract base class for Decimal-based commission models.

    This is the RustyBT version using Decimal for precision.
    For legacy float-based models, see CommissionModel above.
    """

    def __init__(self, min_commission: Decimal = Decimal("0")):
        """Initialize commission model.

        Args:
            min_commission: Minimum commission amount per order
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

        Args:
            order: Order being filled
            fill_price: Price at which order was filled
            fill_quantity: Quantity filled
            current_time: Current simulation time

        Returns:
            CommissionResult with commission details
        """
        pass

    def apply_minimum(self, commission: Decimal) -> tuple[Decimal, bool]:
        """Apply minimum commission threshold.

        Args:
            commission: Calculated commission

        Returns:
            Tuple of (final commission, minimum_applied_flag)
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
    """Per-share commission model.

    Formula: commission = shares × cost_per_share

    Common for US equity brokers (e.g., Interactive Brokers: $0.005/share).
    """

    def __init__(self, cost_per_share: Decimal, min_commission: Decimal = Decimal("1.00")):
        """Initialize per-share commission model.

        Args:
            cost_per_share: Commission per share (e.g., $0.005)
            min_commission: Minimum commission per order
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
        """Calculate per-share commission."""
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
    """Percentage commission model.

    Formula: commission = trade_value × percentage

    Common for international brokers and small accounts.
    """

    def __init__(
        self,
        percentage: Decimal,
        min_commission: Decimal = Decimal("0"),  # As decimal (e.g., 0.001 = 0.1%)
    ):
        """Initialize percentage commission model.

        Args:
            percentage: Commission as decimal fraction (e.g., 0.001 = 0.1%)
            min_commission: Minimum commission per order
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
        """Calculate percentage commission."""
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
    """Tracks trading volume for tiered commissions."""

    def __init__(self):
        """Initialize volume tracker."""
        self.monthly_volumes: dict[str, Decimal] = {}
        self.current_month: str | None = None
        self.logger = structlog.get_logger()

    def get_monthly_volume(self, current_time: pd.Timestamp) -> Decimal:
        """Get accumulated volume for current month.

        Args:
            current_time: Current simulation time

        Returns:
            Accumulated volume for current month
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
        """Add trade volume to current month.

        Args:
            trade_value: Value of trade to add
            current_time: Current simulation time
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
