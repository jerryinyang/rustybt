#
# Copyright 2014 Quantopian, Inc.
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

import abc
import random
from dataclasses import dataclass
from decimal import Decimal
from sys import float_info
from typing import Any

import pandas as pd
import structlog
from numpy import isfinite
from pydantic import BaseModel, Field, field_validator

import rustybt.utils.math_utils as zp_math
from rustybt.errors import BadOrderParameters
from rustybt.utils.compat import consistent_round

logger = structlog.get_logger()


class ExecutionStyle(metaclass=abc.ABCMeta):
    """Base class for order execution styles."""

    _exchange = None

    @abc.abstractmethod
    def get_limit_price(self, is_buy):
        """
        Get the limit price for this order.
        Returns either None or a numerical value >= 0.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_stop_price(self, is_buy):
        """
        Get the stop price for this order.
        Returns either None or a numerical value >= 0.
        """
        raise NotImplementedError

    @property
    def exchange(self):
        """
        The exchange to which this order should be routed.
        """
        return self._exchange


class MarketOrder(ExecutionStyle):
    """
    Execution style for orders to be filled at current market price.

    This is the default for orders placed with :func:`~zipline.api.order`.
    """

    def __init__(self, exchange=None):
        self._exchange = exchange

    def get_limit_price(self, _is_buy):
        return None

    def get_stop_price(self, _is_buy):
        return None


class LimitOrder(ExecutionStyle):
    """
    Execution style for orders to be filled at a price equal to or better than
    a specified limit price.

    Parameters
    ----------
    limit_price : float
        Maximum price for buys, or minimum price for sells, at which the order
        should be filled.
    """

    def __init__(self, limit_price, asset=None, exchange=None):
        check_stoplimit_prices(limit_price, "limit")

        self.limit_price = limit_price
        self._exchange = exchange
        self.asset = asset

    def get_limit_price(self, is_buy):
        return asymmetric_round_price(
            self.limit_price,
            is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )

    def get_stop_price(self, _is_buy):
        return None


class StopOrder(ExecutionStyle):
    """
    Execution style representing a market order to be placed if market price
    reaches a threshold.

    Parameters
    ----------
    stop_price : float
        Price threshold at which the order should be placed. For sells, the
        order will be placed if market price falls below this value. For buys,
        the order will be placed if market price rises above this value.
    """

    def __init__(self, stop_price, asset=None, exchange=None):
        check_stoplimit_prices(stop_price, "stop")

        self.stop_price = stop_price
        self._exchange = exchange
        self.asset = asset

    def get_limit_price(self, _is_buy):
        return None

    def get_stop_price(self, is_buy):
        return asymmetric_round_price(
            self.stop_price,
            not is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )


class StopLimitOrder(ExecutionStyle):
    """
    Execution style representing a limit order to be placed if market price
    reaches a threshold.

    Parameters
    ----------
    limit_price : float
        Maximum price for buys, or minimum price for sells, at which the order
        should be filled, if placed.
    stop_price : float
        Price threshold at which the order should be placed. For sells, the
        order will be placed if market price falls below this value. For buys,
        the order will be placed if market price rises above this value.
    """

    def __init__(self, limit_price, stop_price, asset=None, exchange=None):
        check_stoplimit_prices(limit_price, "limit")
        check_stoplimit_prices(stop_price, "stop")

        self.limit_price = limit_price
        self.stop_price = stop_price
        self._exchange = exchange
        self.asset = asset

    def get_limit_price(self, is_buy):
        return asymmetric_round_price(
            self.limit_price,
            is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )

    def get_stop_price(self, is_buy):
        return asymmetric_round_price(
            self.stop_price,
            not is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )


def asymmetric_round_price(price, prefer_round_down, tick_size, diff=0.95):
    """
    Asymmetric rounding function for adjusting prices to the specified number
    of places in a way that "improves" the price. For limit prices, this means
    preferring to round down on buys and preferring to round up on sells.
    For stop prices, it means the reverse.

    If prefer_round_down == True:
        When .05 below to .95 above a specified decimal place, use it.
    If prefer_round_down == False:
        When .95 below to .05 above a specified decimal place, use it.

    In math-speak:
    If prefer_round_down: [<X-1>.0095, X.0195) -> round to X.01.
    If not prefer_round_down: (<X-1>.0005, X.0105] -> round to X.01.
    """
    precision = zp_math.number_of_decimal_places(tick_size)
    multiplier = int(tick_size * (10**precision))
    diff -= 0.5  # shift the difference down
    diff *= 10**-precision  # adjust diff to precision of tick size
    diff *= multiplier  # adjust diff to value of tick_size

    # Subtracting an epsilon from diff to enforce the open-ness of the upper
    # bound on buys and the lower bound on sells.  Using the actual system
    # epsilon doesn't quite get there, so use a slightly less epsilon-ey value.
    epsilon = float_info.epsilon * 10
    diff = diff - epsilon

    # relies on rounding half away from zero, unlike numpy's bankers' rounding
    rounded = tick_size * consistent_round(
        (price - (diff if prefer_round_down else -diff)) / tick_size
    )
    if zp_math.tolerant_equals(rounded, 0.0):
        return 0.0
    return rounded


class TrailingStopOrder(ExecutionStyle):
    """
    Execution style for trailing stop orders that adjust stop price as market
    price moves favorably.

    Parameters
    ----------
    trail_amount : float, optional
        Absolute dollar amount to trail behind market price.
    trail_percent : float, optional
        Percentage (as decimal) to trail behind market price.
        For example, 0.05 = 5% trailing stop.

    Notes:
    -----
    Exactly one of trail_amount or trail_percent must be specified.
    For long positions: stop_price = highest_price - trail_amount (or * trail_percent)
    For short positions: stop_price = lowest_price + trail_amount (or * trail_percent)
    """

    def __init__(self, trail_amount=None, trail_percent=None, asset=None, exchange=None):
        if trail_amount is None and trail_percent is None:
            raise BadOrderParameters(
                msg="TrailingStopOrder requires either trail_amount or trail_percent"
            )
        if trail_amount is not None and trail_percent is not None:
            raise BadOrderParameters(
                msg="TrailingStopOrder cannot have both trail_amount and trail_percent"
            )

        if trail_amount is not None:
            if trail_amount <= 0:
                raise BadOrderParameters(msg=f"trail_amount must be positive, got {trail_amount}")
            self.trail_amount = trail_amount
            self.trail_percent = None
        else:
            if trail_percent <= 0 or trail_percent >= 1:
                raise BadOrderParameters(
                    msg=f"trail_percent must be between 0 and 1, got {trail_percent}"
                )
            self.trail_amount = None
            self.trail_percent = trail_percent

        self._exchange = exchange
        self.asset = asset
        # Internal tracking for trailing stop adjustment
        self._highest_price = None
        self._lowest_price = None
        self._stop_price = None

    def update_trailing_stop(self, current_price, is_buy):
        """Update the trailing stop price based on current market price.

        Parameters
        ----------
        current_price : float
            Current market price
        is_buy : bool
            True if this is a buy order (closing short), False if sell (closing long)

        Returns:
        -------
        float
            Updated stop price
        """
        if is_buy:
            # For buy/cover orders (closing short), track lowest price
            if self._lowest_price is None or current_price < self._lowest_price:
                self._lowest_price = current_price

            if self.trail_amount is not None:
                self._stop_price = self._lowest_price + self.trail_amount
            else:
                self._stop_price = self._lowest_price * (1 + self.trail_percent)
        else:
            # For sell orders (closing long), track highest price
            if self._highest_price is None or current_price > self._highest_price:
                self._highest_price = current_price

            if self.trail_amount is not None:
                self._stop_price = self._highest_price - self.trail_amount
            else:
                self._stop_price = self._highest_price * (1 - self.trail_percent)

        return self._stop_price

    def get_limit_price(self, _is_buy):
        return None

    def get_stop_price(self, is_buy):
        if self._stop_price is None:
            return None
        return asymmetric_round_price(
            self._stop_price,
            not is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )


class OCOOrder(ExecutionStyle):
    """
    One-Cancels-Other (OCO) order execution style.

    Links two orders together such that when one fills, the other is automatically
    canceled. Commonly used for take-profit/stop-loss pairs.

    Parameters
    ----------
    order1_style : ExecutionStyle
        First order's execution style
    order2_style : ExecutionStyle
        Second order's execution style

    Notes:
    -----
    Both orders must be for the same asset and typically opposite directions
    (e.g., one limit order above market, one stop order below market).
    """

    def __init__(self, order1_style, order2_style, exchange=None):
        if not isinstance(order1_style, ExecutionStyle):
            raise BadOrderParameters(msg="order1_style must be an ExecutionStyle instance")
        if not isinstance(order2_style, ExecutionStyle):
            raise BadOrderParameters(msg="order2_style must be an ExecutionStyle instance")

        self.order1_style = order1_style
        self.order2_style = order2_style
        self._exchange = exchange
        # Track which order filled first
        self._filled_order = None

    def get_limit_price(self, _is_buy):
        # OCO doesn't have its own limit price; child orders have prices
        return None

    def get_stop_price(self, _is_buy):
        # OCO doesn't have its own stop price; child orders have prices
        return None


class BracketOrder(ExecutionStyle):
    """
    Bracket order execution style combining entry, stop-loss, and take-profit.

    A bracket order consists of three parts:
    1. Entry order (limit or market)
    2. Stop-loss order (activated after entry fills)
    3. Take-profit order (activated after entry fills)

    The stop-loss and take-profit orders form an OCO pair.

    Parameters
    ----------
    entry_style : ExecutionStyle
        Execution style for the entry order
    stop_loss_price : float
        Stop price for the protective stop-loss order
    take_profit_price : float
        Limit price for the take-profit order

    Notes:
    -----
    After entry fills, stop-loss and take-profit orders are automatically placed
    as an OCO pair. When one fills, the other is canceled.
    """

    def __init__(self, entry_style, stop_loss_price, take_profit_price, asset=None, exchange=None):
        if not isinstance(entry_style, ExecutionStyle):
            raise BadOrderParameters(msg="entry_style must be an ExecutionStyle instance")

        check_stoplimit_prices(stop_loss_price, "stop_loss")
        check_stoplimit_prices(take_profit_price, "take_profit")

        self.entry_style = entry_style
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self._exchange = exchange
        self.asset = asset
        # Track bracket state
        self._entry_filled = False
        self._stop_loss_order_id = None
        self._take_profit_order_id = None

    def get_limit_price(self, is_buy):
        # Return entry order's limit price
        return self.entry_style.get_limit_price(is_buy)

    def get_stop_price(self, is_buy):
        # Return entry order's stop price
        return self.entry_style.get_stop_price(is_buy)


def check_stoplimit_prices(price, label):
    """
    Check to make sure the stop/limit prices are reasonable and raise
    a BadOrderParameters exception if not.
    """
    try:
        if not isfinite(price):
            raise BadOrderParameters(
                msg=f"Attempted to place an order with a {label} price of {price}."
            )
    # This catches arbitrary objects
    except TypeError as exc:
        raise BadOrderParameters(
            msg=f"Attempted to place an order with a {label} price of {type(price)}."
        ) from exc

    if price < 0:
        raise BadOrderParameters(msg=f"Can't place a {label} order with a negative price.")


# ============================================================================
# Latency Simulation Models (Story 4.1)
# ============================================================================


@dataclass(frozen=True)
class LatencyComponents:
    """Breakdown of latency components for an order.

    Attributes:
        network_ms: Network latency in milliseconds
        broker_processing_ms: Broker processing latency in milliseconds
        exchange_matching_ms: Exchange matching latency in milliseconds
        total_ms: Total latency (sum of all components) in milliseconds
    """

    network_ms: Decimal
    broker_processing_ms: Decimal
    exchange_matching_ms: Decimal
    total_ms: Decimal


class LatencyModel(metaclass=abc.ABCMeta):
    """Abstract base class for latency simulation models.

    Latency models simulate realistic order execution delays that occur in
    live trading environments. These delays include:
    - Network latency (geographic distance to broker/exchange)
    - Broker processing latency (order validation and routing)
    - Exchange matching latency (order matching engine delays)
    """

    @abc.abstractmethod
    def calculate_latency(
        self, order: Any, current_time: pd.Timestamp, broker_name: str
    ) -> LatencyComponents:
        """Calculate latency components for an order.

        Args:
            order: Order being submitted
            current_time: Current simulation time
            broker_name: Name of broker (for profile lookup)

        Returns:
            LatencyComponents with breakdown of latency sources
        """
        raise NotImplementedError


class FixedLatencyModel(LatencyModel):
    """Fixed latency model with constant delays.

    This model applies constant latency values for each component,
    useful for deterministic testing and baseline scenarios.

    Args:
        network_ms: Network latency in milliseconds
        broker_ms: Broker processing latency in milliseconds
        exchange_ms: Exchange matching latency in milliseconds

    Example:
        >>> model = FixedLatencyModel(
        ...     network_ms=Decimal("10.0"),
        ...     broker_ms=Decimal("5.0"),
        ...     exchange_ms=Decimal("2.0")
        ... )
        >>> latency = model.calculate_latency(order, current_time, "test_broker")
        >>> latency.total_ms
        Decimal('17.0')
    """

    def __init__(self, network_ms: Decimal, broker_ms: Decimal, exchange_ms: Decimal) -> None:
        """Initialize fixed latency model."""
        self.network_ms = network_ms
        self.broker_ms = broker_ms
        self.exchange_ms = exchange_ms

    def calculate_latency(
        self, order: Any, current_time: pd.Timestamp, broker_name: str
    ) -> LatencyComponents:
        """Calculate fixed latency."""
        total_ms = self.network_ms + self.broker_ms + self.exchange_ms

        return LatencyComponents(
            network_ms=self.network_ms,
            broker_processing_ms=self.broker_ms,
            exchange_matching_ms=self.exchange_ms,
            total_ms=total_ms,
        )


class RandomLatencyModel(LatencyModel):
    """Random latency model with statistical distributions.

    This model samples latency values from configurable ranges using
    either uniform or normal distributions to simulate realistic variance.

    Args:
        network_range_ms: (min, max) network latency in milliseconds
        broker_range_ms: (min, max) broker processing latency in milliseconds
        exchange_range_ms: (min, max) exchange matching latency in milliseconds
        distribution: Distribution type ("uniform" or "normal")

    Example:
        >>> model = RandomLatencyModel(
        ...     network_range_ms=(Decimal("5.0"), Decimal("15.0")),
        ...     broker_range_ms=(Decimal("1.0"), Decimal("10.0")),
        ...     exchange_range_ms=(Decimal("0.1"), Decimal("5.0")),
        ...     distribution="uniform"
        ... )
    """

    def __init__(
        self,
        network_range_ms: tuple[Decimal, Decimal],
        broker_range_ms: tuple[Decimal, Decimal],
        exchange_range_ms: tuple[Decimal, Decimal],
        distribution: str = "uniform",
    ) -> None:
        """Initialize random latency model."""
        if distribution not in ("uniform", "normal"):
            raise ValueError(f"Distribution must be 'uniform' or 'normal', got '{distribution}'")

        self.network_range = network_range_ms
        self.broker_range = broker_range_ms
        self.exchange_range = exchange_range_ms
        self.distribution = distribution

    def _sample_range(self, min_val: Decimal, max_val: Decimal) -> Decimal:
        """Sample value from range based on distribution type.

        Args:
            min_val: Minimum value in range
            max_val: Maximum value in range

        Returns:
            Sampled value as Decimal
        """
        if self.distribution == "uniform":
            value = random.uniform(float(min_val), float(max_val))
        elif self.distribution == "normal":
            mean = (float(min_val) + float(max_val)) / 2
            std = (float(max_val) - float(min_val)) / 6  # 3-sigma rule
            value = random.gauss(mean, std)
            value = max(float(min_val), min(float(max_val), value))  # Clip to range
        else:
            raise ValueError(f"Unknown distribution: {self.distribution}")

        return Decimal(str(value))

    def calculate_latency(
        self, order: Any, current_time: pd.Timestamp, broker_name: str
    ) -> LatencyComponents:
        """Calculate random latency from configured distributions."""
        network_ms = self._sample_range(*self.network_range)
        broker_ms = self._sample_range(*self.broker_range)
        exchange_ms = self._sample_range(*self.exchange_range)
        total_ms = network_ms + broker_ms + exchange_ms

        return LatencyComponents(
            network_ms=network_ms,
            broker_processing_ms=broker_ms,
            exchange_matching_ms=exchange_ms,
            total_ms=total_ms,
        )


class HistoricalLatencyModel(LatencyModel):
    """Historical latency model replaying from recorded data.

    This model replays latency values from historical execution data,
    allowing backtests to use actual latency patterns observed in live trading.

    Args:
        latency_data: DataFrame with columns ['timestamp', 'network_ms',
                     'broker_ms', 'exchange_ms'] or dict mapping timestamps
                     to LatencyComponents

    Example:
        >>> import polars as pl
        >>> data = pl.DataFrame({
        ...     'timestamp': [...],
        ...     'network_ms': [...],
        ...     'broker_ms': [...],
        ...     'exchange_ms': [...]
        ... })
        >>> model = HistoricalLatencyModel(latency_data=data)
    """

    def __init__(self, latency_data: dict[pd.Timestamp, LatencyComponents]) -> None:
        """Initialize historical latency model."""
        self.latency_data = latency_data
        self.sorted_timestamps = sorted(latency_data.keys())

    def calculate_latency(
        self, order: Any, current_time: pd.Timestamp, broker_name: str
    ) -> LatencyComponents:
        """Calculate latency by looking up historical data."""
        # Find closest timestamp in historical data
        if current_time in self.latency_data:
            return self.latency_data[current_time]

        # Find nearest timestamp
        idx = pd.Series(self.sorted_timestamps).searchsorted(current_time)

        if idx == 0:
            nearest_time = self.sorted_timestamps[0]
        elif idx >= len(self.sorted_timestamps):
            nearest_time = self.sorted_timestamps[-1]
        else:
            # Choose closest between idx-1 and idx
            before = self.sorted_timestamps[idx - 1]
            after = self.sorted_timestamps[idx]
            nearest_time = (
                before
                if abs((current_time - before).total_seconds())
                < abs((current_time - after).total_seconds())
                else after
            )

        return self.latency_data[nearest_time]


class CompositeLatencyModel(LatencyModel):
    """Composite latency model combining multiple latency sources.

    This model allows using different models for each latency component,
    enabling fine-grained control over simulation realism.

    Args:
        network_model: Model for network latency
        broker_model: Model for broker processing latency
        exchange_model: Model for exchange matching latency

    Example:
        >>> network = FixedLatencyModel(Decimal("10"), Decimal("0"), Decimal("0"))
        >>> broker = RandomLatencyModel(
        ...     (Decimal("1"), Decimal("10")),
        ...     (Decimal("0"), Decimal("0")),
        ...     (Decimal("0"), Decimal("0"))
        ... )
        >>> exchange = FixedLatencyModel(Decimal("0"), Decimal("0"), Decimal("2"))
        >>> model = CompositeLatencyModel(network, broker, exchange)
    """

    def __init__(
        self,
        network_model: LatencyModel,
        broker_model: LatencyModel,
        exchange_model: LatencyModel,
    ) -> None:
        """Initialize composite latency model."""
        self.network_model = network_model
        self.broker_model = broker_model
        self.exchange_model = exchange_model

    def calculate_latency(
        self, order: Any, current_time: pd.Timestamp, broker_name: str
    ) -> LatencyComponents:
        """Calculate composite latency from sub-models."""
        network = self.network_model.calculate_latency(order, current_time, broker_name)
        broker = self.broker_model.calculate_latency(order, current_time, broker_name)
        exchange = self.exchange_model.calculate_latency(order, current_time, broker_name)

        return LatencyComponents(
            network_ms=network.network_ms,
            broker_processing_ms=broker.broker_processing_ms,
            exchange_matching_ms=exchange.exchange_matching_ms,
            total_ms=network.network_ms
            + broker.broker_processing_ms
            + exchange.exchange_matching_ms,
        )


class NetworkLatency(LatencyModel):
    """Network latency model based on geographic distance.

    Simulates network delays based on physical distance between trader
    and broker/exchange, including jitter for realistic variance.

    Args:
        base_latency_ms: Base network latency in milliseconds
        jitter_range_ms: (min, max) jitter range in milliseconds
        location: Geographic location identifier (e.g., "US_EAST", "EU", "ASIA")

    Example:
        >>> # US-based trading with 10-30ms base latency
        >>> model = NetworkLatency(
        ...     base_latency_ms=Decimal("20.0"),
        ...     jitter_range_ms=(Decimal("-5.0"), Decimal("5.0")),
        ...     location="US_EAST"
        ... )
    """

    def __init__(
        self,
        base_latency_ms: Decimal,
        jitter_range_ms: tuple[Decimal, Decimal],
        location: str = "US_EAST",
    ) -> None:
        """Initialize network latency model."""
        self.base_latency_ms = base_latency_ms
        self.jitter_range = jitter_range_ms
        self.location = location

    def calculate_latency(
        self, order: Any, current_time: pd.Timestamp, broker_name: str
    ) -> LatencyComponents:
        """Calculate network latency with jitter."""
        # Add random jitter to base latency
        jitter = Decimal(
            str(random.uniform(float(self.jitter_range[0]), float(self.jitter_range[1])))
        )
        network_ms = max(Decimal("0"), self.base_latency_ms + jitter)

        return LatencyComponents(
            network_ms=network_ms,
            broker_processing_ms=Decimal("0"),
            exchange_matching_ms=Decimal("0"),
            total_ms=network_ms,
        )


class BrokerProcessingLatency(LatencyModel):
    """Broker processing latency model for order validation and routing.

    Simulates delays from broker-side order validation, risk checks,
    and routing to exchanges. More complex orders take longer to process.

    Args:
        base_processing_ms: Base processing latency in milliseconds
        complexity_factor: Additional latency per order complexity unit
        processing_range_ms: (min, max) processing time range

    Example:
        >>> # Broker processing with 2-8ms typical range
        >>> model = BrokerProcessingLatency(
        ...     base_processing_ms=Decimal("3.0"),
        ...     complexity_factor=Decimal("0.5"),
        ...     processing_range_ms=(Decimal("2.0"), Decimal("8.0"))
        ... )
    """

    def __init__(
        self,
        base_processing_ms: Decimal,
        complexity_factor: Decimal = Decimal("0.5"),
        processing_range_ms: tuple[Decimal, Decimal] = (Decimal("1.0"), Decimal("10.0")),
    ) -> None:
        """Initialize broker processing latency model."""
        self.base_processing_ms = base_processing_ms
        self.complexity_factor = complexity_factor
        self.processing_range = processing_range_ms

    def calculate_latency(
        self, order: Any, current_time: pd.Timestamp, broker_name: str
    ) -> LatencyComponents:
        """Calculate broker processing latency."""
        # Determine order complexity (simple heuristic)
        complexity = Decimal("1.0")  # Base complexity
        if hasattr(order, "style"):
            # More complex order types take longer to validate
            if isinstance(order.style, (StopLimitOrder, BracketOrder, OCOOrder)):
                complexity = Decimal("2.0")
            elif isinstance(order.style, TrailingStopOrder):
                complexity = Decimal("1.5")

        # Calculate processing time with complexity adjustment
        processing_ms = self.base_processing_ms + (self.complexity_factor * complexity)

        # Add random variation
        variation = Decimal(
            str(random.uniform(float(self.processing_range[0]), float(self.processing_range[1])))
        )
        broker_ms = (processing_ms + variation) / Decimal("2")  # Average with variation
        broker_ms = max(self.processing_range[0], min(self.processing_range[1], broker_ms))

        return LatencyComponents(
            network_ms=Decimal("0"),
            broker_processing_ms=broker_ms,
            exchange_matching_ms=Decimal("0"),
            total_ms=broker_ms,
        )


class ExchangeMatchingLatency(LatencyModel):
    """Exchange matching latency model for order matching engine delays.

    Simulates delays from exchange matching engines, including queue position
    effects and priority matching rules.

    Args:
        base_matching_ms: Base matching latency in milliseconds
        queue_factor: Additional latency per queue position unit
        matching_range_ms: (min, max) matching time range
        exchange_type: Type of exchange ("traditional", "crypto", "dex")

    Example:
        >>> # Crypto exchange matching with 0.1-2ms typical range
        >>> model = ExchangeMatchingLatency(
        ...     base_matching_ms=Decimal("1.0"),
        ...     queue_factor=Decimal("0.1"),
        ...     matching_range_ms=(Decimal("0.1"), Decimal("2.0")),
        ...     exchange_type="crypto"
        ... )
    """

    def __init__(
        self,
        base_matching_ms: Decimal,
        queue_factor: Decimal = Decimal("0.1"),
        matching_range_ms: tuple[Decimal, Decimal] = (Decimal("0.1"), Decimal("5.0")),
        exchange_type: str = "traditional",
    ) -> None:
        """Initialize exchange matching latency model."""
        self.base_matching_ms = base_matching_ms
        self.queue_factor = queue_factor
        self.matching_range = matching_range_ms
        self.exchange_type = exchange_type

        # Exchange type affects base latency
        self.type_multiplier = {
            "traditional": Decimal("1.0"),  # Traditional exchanges (NASDAQ, NYSE)
            "crypto": Decimal("0.5"),  # Crypto exchanges (faster matching)
            "dex": Decimal("2.0"),  # Decentralized exchanges (slower)
        }.get(exchange_type, Decimal("1.0"))

    def calculate_latency(
        self, order: Any, current_time: pd.Timestamp, broker_name: str
    ) -> LatencyComponents:
        """Calculate exchange matching latency."""
        # Simulate queue position effect (random for now)
        queue_position = Decimal(str(random.uniform(0, 5)))
        queue_latency = self.queue_factor * queue_position

        # Apply exchange type multiplier
        matching_ms = (self.base_matching_ms + queue_latency) * self.type_multiplier

        # Clamp to valid range
        matching_ms = max(self.matching_range[0], min(self.matching_range[1], matching_ms))

        return LatencyComponents(
            network_ms=Decimal("0"),
            broker_processing_ms=Decimal("0"),
            exchange_matching_ms=matching_ms,
            total_ms=matching_ms,
        )


# ============================================================================
# Latency Profile Configuration (Story 4.1 - AC 7)
# ============================================================================


class LatencyConfigurationError(Exception):
    """Exception raised for invalid latency configuration."""

    pass


class LatencyProfileConfig(BaseModel):
    """Configuration for broker-specific latency profiles.

    This model defines latency characteristics for a specific broker
    and asset class combination.

    Attributes:
        broker_name: Name of the broker
        asset_class: Asset class ("equities", "crypto", "futures", etc.)
        network_latency_ms: (min, max) network latency range
        broker_processing_ms: (min, max) broker processing latency range
        exchange_matching_ms: (min, max) exchange matching latency range
        distribution: Distribution type ("uniform" or "normal")
        location: Geographic location identifier

    Example:
        >>> config = LatencyProfileConfig(
        ...     broker_name="Interactive Brokers",
        ...     asset_class="equities",
        ...     network_latency_ms=(10.0, 30.0),
        ...     broker_processing_ms=(2.0, 8.0),
        ...     exchange_matching_ms=(0.5, 3.0),
        ...     distribution="normal",
        ...     location="US_EAST"
        ... )
    """

    broker_name: str = Field(description="Name of the broker")
    asset_class: str = Field(
        default="equities", description="Asset class (equities, crypto, futures, etc.)"
    )
    network_latency_ms: tuple[float, float] = Field(
        description="(min, max) network latency in milliseconds"
    )
    broker_processing_ms: tuple[float, float] = Field(
        description="(min, max) broker processing latency in milliseconds"
    )
    exchange_matching_ms: tuple[float, float] = Field(
        description="(min, max) exchange matching latency in milliseconds"
    )
    distribution: str = Field(
        default="uniform", description="Distribution type (uniform or normal)"
    )
    location: str = Field(default="US_EAST", description="Geographic location")

    @field_validator("distribution")
    @classmethod
    def validate_distribution(cls, v: str) -> str:
        """Validate distribution type."""
        if v not in ("uniform", "normal"):
            raise ValueError(f"Distribution must be 'uniform' or 'normal', got '{v}'")
        return v

    @field_validator("network_latency_ms", "broker_processing_ms", "exchange_matching_ms")
    @classmethod
    def validate_latency_range(cls, v: tuple[float, float]) -> tuple[float, float]:
        """Validate latency ranges are positive and min <= max."""
        min_val, max_val = v
        if min_val < 0:
            raise ValueError(f"Minimum latency cannot be negative, got {min_val}")
        if max_val < min_val:
            raise ValueError(f"Maximum latency ({max_val}) must be >= minimum ({min_val})")
        return v

    def to_latency_model(self) -> RandomLatencyModel:
        """Convert configuration to a RandomLatencyModel instance.

        Returns:
            RandomLatencyModel configured with profile settings
        """
        return RandomLatencyModel(
            network_range_ms=(
                Decimal(str(self.network_latency_ms[0])),
                Decimal(str(self.network_latency_ms[1])),
            ),
            broker_range_ms=(
                Decimal(str(self.broker_processing_ms[0])),
                Decimal(str(self.broker_processing_ms[1])),
            ),
            exchange_range_ms=(
                Decimal(str(self.exchange_matching_ms[0])),
                Decimal(str(self.exchange_matching_ms[1])),
            ),
            distribution=self.distribution,
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "broker_name": "Interactive Brokers",
                    "asset_class": "equities",
                    "network_latency_ms": [10.0, 30.0],
                    "broker_processing_ms": [2.0, 8.0],
                    "exchange_matching_ms": [0.5, 3.0],
                    "distribution": "normal",
                    "location": "US_EAST",
                },
                {
                    "broker_name": "Binance",
                    "asset_class": "crypto",
                    "network_latency_ms": [20.0, 50.0],
                    "broker_processing_ms": [1.0, 5.0],
                    "exchange_matching_ms": [0.1, 2.0],
                    "distribution": "uniform",
                    "location": "ASIA",
                },
            ]
        }
    }


class BrokerLatencyProfile(BaseModel):
    """Complete latency profile for a broker with multiple asset classes.

    Attributes:
        broker_name: Name of the broker
        profiles: List of asset class-specific latency configurations
        default_profile: Default profile to use if asset class not found

    Example:
        >>> profile = BrokerLatencyProfile(
        ...     broker_name="Interactive Brokers",
        ...     profiles=[
        ...         LatencyProfileConfig(
        ...             broker_name="Interactive Brokers",
        ...             asset_class="equities",
        ...             ...
        ...         ),
        ...         LatencyProfileConfig(
        ...             broker_name="Interactive Brokers",
        ...             asset_class="futures",
        ...             ...
        ...         )
        ...     ]
        ... )
    """

    broker_name: str = Field(description="Name of the broker")
    profiles: list[LatencyProfileConfig] = Field(
        description="List of asset class-specific latency configurations"
    )
    default_profile: LatencyProfileConfig | None = Field(
        default=None, description="Default profile if asset class not found"
    )

    def get_profile_for_asset_class(self, asset_class: str) -> LatencyProfileConfig:
        """Get latency profile for specific asset class.

        Args:
            asset_class: Asset class to look up

        Returns:
            LatencyProfileConfig for the asset class

        Raises:
            LatencyConfigurationError: If asset class not found and no default
        """
        for profile in self.profiles:
            if profile.asset_class == asset_class:
                return profile

        if self.default_profile:
            return self.default_profile

        raise LatencyConfigurationError(
            f"No latency profile found for asset class '{asset_class}' "
            f"in broker '{self.broker_name}' and no default profile configured"
        )


class LatencyProfileRegistry:
    """Registry for managing broker latency profiles.

    This class provides a centralized registry for loading and accessing
    broker-specific latency profiles from configuration files.

    Example:
        >>> registry = LatencyProfileRegistry()
        >>> registry.load_from_yaml("config/broker_latency_profiles/binance.yaml")
        >>> profile = registry.get_profile("Binance", "crypto")
        >>> model = profile.to_latency_model()
    """

    def __init__(self) -> None:
        """Initialize latency profile registry."""
        self._profiles: dict[str, BrokerLatencyProfile] = {}
        logger.debug("latency_profile_registry_initialized")

    def register_profile(self, profile: BrokerLatencyProfile) -> None:
        """Register a broker latency profile.

        Args:
            profile: BrokerLatencyProfile to register
        """
        self._profiles[profile.broker_name] = profile
        logger.info(
            "latency_profile_registered",
            broker=profile.broker_name,
            num_asset_classes=len(profile.profiles),
        )

    def get_profile(self, broker_name: str, asset_class: str = "equities") -> LatencyProfileConfig:
        """Get latency profile for broker and asset class.

        Args:
            broker_name: Name of broker
            asset_class: Asset class (default: "equities")

        Returns:
            LatencyProfileConfig for the broker and asset class

        Raises:
            LatencyConfigurationError: If broker not found
        """
        if broker_name not in self._profiles:
            raise LatencyConfigurationError(
                f"No latency profile registered for broker '{broker_name}'"
            )

        broker_profile = self._profiles[broker_name]
        return broker_profile.get_profile_for_asset_class(asset_class)

    def load_from_dict(self, config: dict[str, Any]) -> None:
        """Load broker latency profile from dictionary.

        Args:
            config: Configuration dictionary

        Raises:
            LatencyConfigurationError: If configuration is invalid
        """
        try:
            broker_name = config.get("broker_name")
            if not broker_name:
                raise LatencyConfigurationError("Missing 'broker_name' in configuration")

            # Parse asset class profiles
            asset_classes = config.get("asset_classes", {})
            profiles = []

            for asset_class, latency_config in asset_classes.items():
                profile_config = LatencyProfileConfig(
                    broker_name=broker_name,
                    asset_class=asset_class,
                    network_latency_ms=tuple(latency_config["network_latency_ms"]),
                    broker_processing_ms=tuple(latency_config["broker_processing_ms"]),
                    exchange_matching_ms=tuple(latency_config["exchange_matching_ms"]),
                    distribution=latency_config.get("distribution", "uniform"),
                    location=latency_config.get("location", "US_EAST"),
                )
                profiles.append(profile_config)

            # Create broker profile
            broker_profile = BrokerLatencyProfile(
                broker_name=broker_name,
                profiles=profiles,
                default_profile=profiles[0] if profiles else None,
            )

            self.register_profile(broker_profile)

        except Exception as e:
            raise LatencyConfigurationError(f"Failed to load latency profile: {e}") from e

    def load_from_yaml(self, filepath: str) -> None:
        """Load broker latency profile from YAML file.

        Args:
            filepath: Path to YAML configuration file

        Raises:
            LatencyConfigurationError: If file cannot be loaded or is invalid
        """
        import yaml

        try:
            with open(filepath) as f:
                config = yaml.safe_load(f)
            self.load_from_dict(config)
            logger.info("latency_profile_loaded_from_yaml", filepath=filepath)
        except Exception as e:
            raise LatencyConfigurationError(
                f"Failed to load YAML latency profile from '{filepath}': {e}"
            ) from e

    def load_from_json(self, filepath: str) -> None:
        """Load broker latency profile from JSON file.

        Args:
            filepath: Path to JSON configuration file

        Raises:
            LatencyConfigurationError: If file cannot be loaded or is invalid
        """
        import json

        try:
            with open(filepath) as f:
                config = json.load(f)
            self.load_from_dict(config)
            logger.info("latency_profile_loaded_from_json", filepath=filepath)
        except Exception as e:
            raise LatencyConfigurationError(
                f"Failed to load JSON latency profile from '{filepath}': {e}"
            ) from e


# ============================================================================
# Partial Fill Models (Story 4.2)
# ============================================================================

from enum import Enum


class OrderState(Enum):
    """Order states for tracking fill status.

    Attributes:
        NEW: Order created but not yet filled
        PARTIALLY_FILLED: Order partially filled, has remaining quantity
        FILLED: Order completely filled
        CANCELED: Order canceled before complete fill
        REJECTED: Order rejected by broker/exchange
    """

    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PartialFill:
    """Record of a single partial fill.

    Attributes:
        timestamp: Timestamp when fill occurred
        quantity: Quantity filled (always positive)
        price: Price at which fill occurred
        value: Total value of fill (quantity × price)

    Example:
        >>> fill = PartialFill(
        ...     timestamp=pd.Timestamp("2023-01-01 10:00"),
        ...     quantity=Decimal("100"),
        ...     price=Decimal("50.00")
        ... )
        >>> fill.value
        Decimal('5000.00')
    """

    timestamp: pd.Timestamp
    quantity: Decimal
    price: Decimal
    value: Decimal = None

    def __post_init__(self) -> None:
        """Calculate fill value after initialization."""
        if self.value is None:
            # Use object.__setattr__ for frozen dataclass
            object.__setattr__(self, "value", self.quantity * self.price)


@dataclass
class Order:
    """Order with partial fill tracking.

    Attributes:
        id: Unique order identifier
        asset: Asset being traded
        amount: Order amount (positive=buy, negative=sell)
        order_type: Order type ("market", "limit", etc.)
        limit_price: Limit price for limit orders
        state: Current order state
        partial_fills: List of partial fills
        created_at: Order creation timestamp
        timeout_bars: Cancel after N bars if not filled

    Example:
        >>> order = Order(
        ...     id="order-1",
        ...     asset=asset,
        ...     amount=Decimal("1000"),
        ...     order_type="market"
        ... )
        >>> order.add_fill(PartialFill(...))
        >>> order.filled_quantity
        Decimal('100')
    """

    id: str
    asset: Any
    amount: Decimal
    order_type: str
    limit_price: Decimal | None = None
    state: OrderState = OrderState.NEW
    partial_fills: list[PartialFill] = None
    created_at: pd.Timestamp | None = None
    timeout_bars: int | None = None

    def __post_init__(self) -> None:
        """Initialize mutable fields."""
        if self.partial_fills is None:
            self.partial_fills = []

    @property
    def filled_quantity(self) -> Decimal:
        """Total quantity filled across all partial fills.

        Returns:
            Sum of all partial fill quantities
        """
        return sum((fill.quantity for fill in self.partial_fills), Decimal("0"))

    @property
    def remaining_quantity(self) -> Decimal:
        """Remaining quantity to be filled.

        Returns:
            Absolute order amount minus filled quantity
        """
        return abs(self.amount) - self.filled_quantity

    @property
    def is_fully_filled(self) -> bool:
        """Check if order is fully filled.

        Returns:
            True if no remaining quantity, False otherwise
        """
        return self.remaining_quantity <= Decimal("0")

    @property
    def average_fill_price(self) -> Decimal | None:
        """Volume-weighted average fill price.

        Returns:
            VWAP across all partial fills, or None if no fills

        Example:
            >>> order.partial_fills = [
            ...     PartialFill(ts, Decimal("100"), Decimal("50.00")),
            ...     PartialFill(ts, Decimal("100"), Decimal("52.00"))
            ... ]
            >>> order.average_fill_price
            Decimal('51.00')
        """
        if not self.partial_fills:
            return None

        total_value = sum((fill.value for fill in self.partial_fills), Decimal("0"))
        total_quantity = sum((fill.quantity for fill in self.partial_fills), Decimal("0"))

        if total_quantity == Decimal("0"):
            return None

        return total_value / total_quantity

    def add_fill(self, partial_fill: PartialFill) -> None:
        """Add partial fill to order.

        Args:
            partial_fill: PartialFill to add

        Raises:
            ValueError: If fill would exceed order quantity
        """
        if self.filled_quantity + partial_fill.quantity > abs(self.amount):
            raise ValueError(
                f"Partial fill quantity {partial_fill.quantity} would exceed "
                f"remaining order quantity {self.remaining_quantity}"
            )

        self.partial_fills.append(partial_fill)

        # Update order state
        if self.is_fully_filled:
            self.state = OrderState.FILLED
        elif self.filled_quantity > Decimal("0"):
            self.state = OrderState.PARTIALLY_FILLED


class PartialFillModel(metaclass=abc.ABCMeta):
    """Abstract base class for partial fill simulation.

    Partial fill models simulate realistic order execution where large orders
    cannot be filled immediately due to limited market liquidity.
    """

    @abc.abstractmethod
    def calculate_fill(
        self,
        order: Order,
        bar_volume: Decimal,
        bar_price: Decimal,
        current_time: pd.Timestamp,
    ) -> PartialFill | None:
        """Calculate partial fill for current bar.

        Args:
            order: Order being filled
            bar_volume: Available volume in current bar
            bar_price: Price for current bar
            current_time: Current simulation time

        Returns:
            PartialFill if order can be filled, None otherwise
        """
        raise NotImplementedError


class VolumeBasedFillModel(PartialFillModel):
    """Volume-based partial fill model.

    This model fills orders based on available market volume, with configurable
    fill ratio and market impact modeling.

    Args:
        fill_ratio: Maximum fraction of bar volume to fill (default: 0.10 = 10%)
        market_impact_factor: Market impact coefficient (default: 0.01 = 1%)

    Example:
        >>> model = VolumeBasedFillModel(
        ...     fill_ratio=Decimal("0.10"),
        ...     market_impact_factor=Decimal("0.01")
        ... )
        >>> fill = model.calculate_fill(order, bar_volume, bar_price, current_time)
    """

    def __init__(
        self,
        fill_ratio: Decimal = Decimal("0.10"),
        market_impact_factor: Decimal = Decimal("0.01"),
    ) -> None:
        """Initialize volume-based fill model."""
        if fill_ratio <= Decimal("0") or fill_ratio > Decimal("1"):
            raise ValueError(f"fill_ratio must be between 0 and 1, got {fill_ratio}")
        if market_impact_factor < Decimal("0"):
            raise ValueError(
                f"market_impact_factor must be non-negative, got {market_impact_factor}"
            )

        self.fill_ratio = fill_ratio
        self.market_impact_factor = market_impact_factor

    def calculate_fill(
        self,
        order: Order,
        bar_volume: Decimal,
        bar_price: Decimal,
        current_time: pd.Timestamp,
    ) -> PartialFill | None:
        """Calculate volume-based partial fill.

        Args:
            order: Order being filled
            bar_volume: Available volume in current bar
            bar_price: Price for current bar
            current_time: Current simulation time

        Returns:
            PartialFill if volume available, None otherwise
        """
        # Calculate available fill quantity
        available_quantity = bar_volume * self.fill_ratio
        remaining = order.remaining_quantity

        # Determine fill quantity (lesser of available and remaining)
        fill_quantity = min(available_quantity, remaining)

        if fill_quantity <= Decimal("0"):
            logger.debug(
                "no_fill_available",
                order_id=order.id,
                bar_volume=str(bar_volume),
                available_quantity=str(available_quantity),
            )
            return None

        # Calculate market impact (larger orders get worse prices)
        order_volume_ratio = (
            fill_quantity / bar_volume if bar_volume > Decimal("0") else Decimal("0")
        )
        market_impact = self.market_impact_factor * order_volume_ratio

        # Apply market impact to price (directional: buy orders slip up, sell orders slip down)
        if order.amount > Decimal("0"):  # Buy order
            fill_price = bar_price * (Decimal("1") + market_impact)
        else:  # Sell order
            fill_price = bar_price * (Decimal("1") - market_impact)

        # Create partial fill record
        partial_fill = PartialFill(timestamp=current_time, quantity=fill_quantity, price=fill_price)

        logger.info(
            "partial_fill_executed",
            order_id=order.id,
            asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            fill_quantity=str(fill_quantity),
            fill_price=str(fill_price),
            remaining_quantity=str(remaining - fill_quantity),
            market_impact_pct=str(market_impact * Decimal("100")),
        )

        return partial_fill


class AggressiveFillModel(VolumeBasedFillModel):
    """Aggressive fill model (fills quickly, accepts higher impact).

    Uses higher fill ratio (25%) and accepts higher market impact (2%).
    Suitable for strategies that prioritize execution speed over price.

    Example:
        >>> model = AggressiveFillModel()
        >>> # Fills up to 25% of bar volume per bar
    """

    def __init__(self) -> None:
        """Initialize aggressive fill model."""
        super().__init__(fill_ratio=Decimal("0.25"), market_impact_factor=Decimal("0.02"))


class ConservativeFillModel(VolumeBasedFillModel):
    """Conservative fill model (fills slowly, minimizes impact).

    Uses lower fill ratio (5%) and minimizes market impact (0.5%).
    Suitable for strategies that prioritize price over execution speed.

    Example:
        >>> model = ConservativeFillModel()
        >>> # Fills up to 5% of bar volume per bar
    """

    def __init__(self) -> None:
        """Initialize conservative fill model."""
        super().__init__(fill_ratio=Decimal("0.05"), market_impact_factor=Decimal("0.005"))


class BalancedFillModel(VolumeBasedFillModel):
    """Balanced fill model (moderate fill speed and impact).

    Uses moderate fill ratio (10%) and market impact (1%).
    Suitable for most strategies balancing speed and price.

    Example:
        >>> model = BalancedFillModel()
        >>> # Fills up to 10% of bar volume per bar
    """

    def __init__(self) -> None:
        """Initialize balanced fill model."""
        super().__init__(fill_ratio=Decimal("0.10"), market_impact_factor=Decimal("0.01"))


class OrderTracker:
    """Tracks partially filled orders across multiple bars.

    This class manages open orders and attempts to fill them as new market
    data becomes available. Orders persist across bars until fully filled,
    canceled, or timed out.

    Args:
        fill_model: Partial fill model to use for calculating fills

    Example:
        >>> tracker = OrderTracker(BalancedFillModel())
        >>> tracker.add_order(order, current_time)
        >>> filled_orders = tracker.process_bar(current_time, data_portal)
    """

    def __init__(self, fill_model: PartialFillModel) -> None:
        """Initialize order tracker."""
        self.fill_model = fill_model
        self.open_orders: dict[str, Order] = {}
        self.logger = structlog.get_logger()

    def add_order(self, order: Order, current_time: pd.Timestamp) -> None:
        """Add new order to tracker.

        Args:
            order: Order to track
            current_time: Current simulation time
        """
        order.created_at = current_time
        self.open_orders[order.id] = order

        self.logger.info(
            "order_created",
            order_id=order.id,
            asset=order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset),
            amount=str(order.amount),
            order_type=order.order_type,
        )

    def process_bar(self, current_time: pd.Timestamp, data_portal: Any) -> list[Order]:
        """Process current bar and attempt to fill open orders.

        Args:
            current_time: Current simulation time
            data_portal: Data source for price and volume

        Returns:
            List of orders that were fully filled in this bar
        """
        filled_orders = []

        for order_id, order in list(self.open_orders.items()):
            # Check timeout
            if order.timeout_bars is not None and order.created_at is not None:
                # Calculate bars elapsed (assumes minute bars)
                bars_elapsed = int((current_time - order.created_at).total_seconds() / 60)
                if bars_elapsed > order.timeout_bars:
                    order.state = OrderState.CANCELED
                    del self.open_orders[order_id]
                    self.logger.warning(
                        "order_timeout",
                        order_id=order.id,
                        bars_elapsed=bars_elapsed,
                    )
                    continue

            # Get bar data
            try:
                bar_volume = data_portal.get_volume(order.asset, current_time)
                bar_price = data_portal.get_price(order.asset, current_time, field="close")
            except Exception as e:
                self.logger.error(
                    "data_portal_error",
                    order_id=order.id,
                    error=str(e),
                    current_time=str(current_time),
                )
                continue

            # Attempt partial fill
            partial_fill = self.fill_model.calculate_fill(
                order, bar_volume, bar_price, current_time
            )

            if partial_fill:
                order.add_fill(partial_fill)

                # Update order state
                if order.is_fully_filled:
                    order.state = OrderState.FILLED
                    filled_orders.append(order)
                    del self.open_orders[order_id]

                    self.logger.info(
                        "order_fully_filled",
                        order_id=order.id,
                        total_fills=len(order.partial_fills),
                        average_price=str(order.average_fill_price),
                    )
                else:
                    order.state = OrderState.PARTIALLY_FILLED

        return filled_orders

    def get_open_orders(self) -> list[Order]:
        """Get list of currently open orders.

        Returns:
            List of open orders
        """
        return list(self.open_orders.values())

    def cancel_order(self, order_id: str) -> Order | None:
        """Cancel an open order.

        Args:
            order_id: ID of order to cancel

        Returns:
            Canceled order if found, None otherwise
        """
        if order_id in self.open_orders:
            order = self.open_orders[order_id]
            order.state = OrderState.CANCELED
            del self.open_orders[order_id]
            self.logger.info("order_canceled", order_id=order_id)
            return order
        return None


# ============================================================================
# Execution Engine with Slippage Integration (Story 4.3)
# ============================================================================


@dataclass
class ExecutionResult:
    """Result of order execution with complete execution details.

    Attributes:
        order: Original order
        fill_price: Final fill price (after slippage)
        fill_quantity: Quantity filled
        execution_time: Timestamp when order executed
        latency: Latency components (if latency model used)
        slippage: Slippage calculation result (if slippage model used)
        commission: Commission calculation result (if commission model used)
    """

    order: Any
    fill_price: Decimal
    fill_quantity: Decimal
    execution_time: pd.Timestamp
    latency: LatencyComponents | None = None
    slippage: Any | None = None  # SlippageResult from slippage.py
    commission: Any | None = None  # CommissionResult from commission.py


class ExecutionEngine:
    """Enhanced execution engine with slippage, latency, partial fills, and commissions.

    This execution engine combines multiple models to simulate realistic order execution:
    - Latency simulation: Delays between order submission and execution
    - Slippage modeling: Price impact and market friction costs
    - Partial fill simulation: Orders may fill across multiple bars
    - Commission calculation: Broker fees and transaction costs

    Args:
        latency_model: Optional latency model for order submission delays
        slippage_model: Optional slippage model for price impact
        partial_fill_model: Optional partial fill model for execution across time
        commission_model: Optional commission model for transaction costs
        data_portal: Data source for price and volume lookup
        logger: Optional structured logger instance

    Example:
        >>> from rustybt.finance.slippage import VolumeShareSlippageDecimal
        >>> from rustybt.finance.execution import FixedLatencyModel
        >>> from rustybt.finance.commission import PerShareCommission
        >>>
        >>> engine = ExecutionEngine(
        ...     latency_model=FixedLatencyModel(
        ...         Decimal("10"), Decimal("5"), Decimal("2")
        ...     ),
        ...     slippage_model=VolumeShareSlippageDecimal(),
        ...     commission_model=PerShareCommission(Decimal("0.005")),
        ...     data_portal=data_portal
        ... )
        >>> result = engine.execute_order(order, current_time)
    """

    def __init__(
        self,
        latency_model: LatencyModel | None = None,
        slippage_model: Any | None = None,  # DecimalSlippageModel from slippage.py
        partial_fill_model: PartialFillModel | None = None,
        commission_model: Any | None = None,  # DecimalCommissionModel from commission.py
        data_portal: Any = None,
        logger_instance: Any = None,
    ) -> None:
        """Initialize execution engine."""
        self.latency_model = latency_model
        self.slippage_model = slippage_model
        self.partial_fill_model = partial_fill_model
        self.commission_model = commission_model
        self.data_portal = data_portal
        self.logger = logger_instance or structlog.get_logger()

    def execute_order(
        self,
        order: Any,
        current_time: pd.Timestamp,
        broker_name: str = "default",
        bar_data: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Execute order with latency, slippage, partial fills, and commission calculation.

        Execution pipeline:
        1. Apply latency model (if configured)
        2. Get bar data at execution time
        3. Calculate slippage (if configured)
        4. Apply directional slippage to fill price
        5. Apply partial fill model (if configured)
        6. Calculate commission (if configured)
        7. Return execution result

        Args:
            order: Order to execute
            current_time: Current simulation time
            broker_name: Broker name for profile lookup
            bar_data: Optional pre-fetched bar data (overrides data_portal lookup)

        Returns:
            ExecutionResult with complete execution details including commission
        """
        # Step 1: Apply latency (from Story 4.1)
        if self.latency_model:
            latency = self.latency_model.calculate_latency(order, current_time, broker_name)
            execution_time = current_time + pd.Timedelta(milliseconds=float(latency.total_ms))

            self.logger.debug(
                "latency_applied",
                order_id=order.id if hasattr(order, "id") else "unknown",
                latency_ms=str(latency.total_ms),
                execution_time=str(execution_time),
            )
        else:
            execution_time = current_time
            latency = None

        # Step 2: Get bar data at execution time
        if bar_data is None:
            if self.data_portal is None:
                raise ValueError(
                    "Either bar_data must be provided or data_portal must be configured"
                )

            # Fetch bar data from data portal
            bar_data = self._fetch_bar_data(order.asset, execution_time)

        base_price = Decimal(str(bar_data.get("close", 0)))

        # Step 3: Calculate slippage (Story 4.3)
        slippage_result = None
        fill_price = base_price

        if self.slippage_model:
            slippage_result = self.slippage_model.calculate_slippage(
                order, bar_data, execution_time
            )

            # Apply directional slippage to price
            order_side = self.slippage_model._get_order_side(order)
            fill_price = self.slippage_model._apply_directional_slippage(
                base_price, slippage_result.slippage_amount, order_side
            )

            self.logger.info(
                "slippage_applied",
                order_id=order.id if hasattr(order, "id") else "unknown",
                base_price=str(base_price),
                fill_price=str(fill_price),
                slippage_bps=str(slippage_result.slippage_bps),
                slippage_model=slippage_result.model_name,
            )

        # Step 4: Apply partial fill logic if configured (from Story 4.2)
        if self.partial_fill_model:
            bar_volume = Decimal(str(bar_data.get("volume", 0)))

            partial_fill = self.partial_fill_model.calculate_fill(
                order, bar_volume, fill_price, execution_time
            )

            if partial_fill:
                fill_quantity = partial_fill.quantity
            else:
                fill_quantity = Decimal("0")
        else:
            # Full fill
            fill_quantity = abs(order.amount)

        # Step 5: Calculate commission (Story 4.4)
        commission_result = None
        if self.commission_model:
            try:
                commission_result = self.commission_model.calculate_commission(
                    order, fill_price, fill_quantity, execution_time
                )

                self.logger.info(
                    "commission_calculated",
                    order_id=order.id if hasattr(order, "id") else "unknown",
                    commission=str(commission_result.commission),
                    commission_model=commission_result.model_name,
                    tier=commission_result.tier_applied,
                    maker_taker=commission_result.maker_taker,
                )
            except Exception as e:
                self.logger.error(
                    "commission_calculation_failed",
                    order_id=order.id if hasattr(order, "id") else "unknown",
                    error=str(e),
                )
                # Don't fail execution on commission calculation error
                # Fall through with commission_result = None

        # Step 6: Create execution result
        result = ExecutionResult(
            order=order,
            fill_price=fill_price,
            fill_quantity=fill_quantity,
            execution_time=execution_time,
            latency=latency,
            slippage=slippage_result,
            commission=commission_result,
        )

        self.logger.info(
            "order_executed",
            order_id=order.id if hasattr(order, "id") else "unknown",
            asset=(order.asset.symbol if hasattr(order.asset, "symbol") else str(order.asset)),
            fill_price=str(fill_price),
            fill_quantity=str(fill_quantity),
            slippage_bps=str(slippage_result.slippage_bps) if slippage_result else "0",
            commission=str(commission_result.commission) if commission_result else "0",
        )

        return result

    def _fetch_bar_data(self, asset: Any, timestamp: pd.Timestamp) -> dict[str, Any]:
        """Fetch bar data from data portal.

        Args:
            asset: Asset to fetch data for
            timestamp: Timestamp for data lookup

        Returns:
            Dictionary with bar data (close, volume, bid, ask, etc.)

        Raises:
            ValueError: If data portal is not configured or data unavailable
        """
        if self.data_portal is None:
            raise ValueError("Data portal not configured")

        # Fetch current bar data
        # This is a simplified interface; actual implementation depends on data portal API
        try:
            bar_data = {
                "close": self.data_portal.get_price(asset, timestamp, field="close"),
                "volume": self.data_portal.get_volume(asset, timestamp),
            }

            # Try to fetch bid/ask if available (for BidAskSpreadSlippage)
            try:
                bar_data["bid"] = self.data_portal.get_price(asset, timestamp, field="bid")
                bar_data["ask"] = self.data_portal.get_price(asset, timestamp, field="ask")
            except (AttributeError, KeyError):
                # Bid/ask not available, will use spread estimation
                pass

            return bar_data

        except Exception as e:
            self.logger.error(
                "bar_data_fetch_failed",
                asset=asset.symbol if hasattr(asset, "symbol") else str(asset),
                timestamp=str(timestamp),
                error=str(e),
            )
            raise ValueError(f"Failed to fetch bar data for {asset} at {timestamp}: {e}") from e
