#
# Copyright 2013 Quantopian, Inc.
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

"""Test data sources for backtesting simulations.

This module provides utilities for generating synthetic trade and market data
for testing backtesting algorithms. It includes functions for creating individual
trade events and classes for generating streams of test data.

The primary components are:
- create_trade: Create individual trade events
- date_gen: Generate trading date sequences
- SpecificEquityTrades: Generate streams of trade events for specific securities
"""

import itertools
from datetime import timedelta

from rustybt.protocol import DATASOURCE_TYPE, Event


def create_trade(sid, price, amount, datetime, source_id="test_factory"):
    """Create a synthetic trade event for testing.

    Generates a complete trade event with OHLCV data. The high and low prices
    are automatically calculated as +/-5% of the given price.

    Args:
        sid: Security identifier for the trade.
        price: The trade price, used for open, close, and base price.
        amount: Volume of the trade.
        datetime: Timestamp for the trade.
        source_id: Identifier for the data source. Default 'test_factory'.

    Returns:
        An Event object configured as a trade with all required fields populated.

    Examples:
        Create a single trade event::

            from datetime import datetime
            trade = create_trade(
                sid=1,
                price=100.50,
                amount=1000,
                datetime=datetime(2020, 1, 15, 9, 30)
            )
            print(trade.high)  # 105.525 (price * 1.05)
            print(trade.low)   # 95.475 (price * 0.95)
    """
    trade = Event()

    trade.source_id = source_id
    trade.type = DATASOURCE_TYPE.TRADE
    trade.sid = sid
    trade.dt = datetime
    trade.price = price
    trade.close_price = price
    trade.open_price = price
    trade.low = price * 0.95
    trade.high = price * 1.05
    trade.volume = amount

    return trade


def date_gen(start, end, trading_calendar, delta=timedelta(minutes=1), repeats=None):
    """Generate a stream of trading dates/times.

    Yields timestamps at regular intervals, skipping non-trading days and times
    according to the trading calendar. Supports both daily and intraday frequencies.

    Args:
        start: Starting datetime for generation.
        end: Ending datetime (exclusive).
        trading_calendar: Trading calendar to determine valid trading times.
        delta: Time interval between generated dates. Default 1 minute.
        repeats: If specified, yields each timestamp this many times before
            advancing. Optional.

    Yields:
        Datetime objects representing valid trading times in the range [start, end).

    Examples:
        Generate minute-frequency trading times::

            from datetime import datetime, timedelta
            for dt in date_gen(
                start=datetime(2020, 1, 2),
                end=datetime(2020, 1, 3),
                trading_calendar=calendar,
                delta=timedelta(minutes=1)
            ):
                print(dt)  # Only market hours

        Generate daily trading dates::

            for dt in date_gen(
                start=datetime(2020, 1, 1),
                end=datetime(2020, 2, 1),
                trading_calendar=calendar,
                delta=timedelta(days=1)
            ):
                print(dt)  # Only trading days
    """
    daily_delta = not (delta.total_seconds() % timedelta(days=1).total_seconds())
    cur = start
    if daily_delta:
        # if we are producing daily timestamps, we
        # use midnight
        cur = cur.replace(hour=0, minute=0, second=0, microsecond=0)

    def advance_current(cur):
        """Advance to the next valid trading time.

        Args:
            cur: Current datetime.

        Returns:
            Next valid trading datetime, skipping non-trading days and times.
        """
        cur = cur + delta

        currently_executing = (daily_delta and (cur in trading_calendar.sessions)) or (
            trading_calendar.is_open_on_minute(cur)
        )

        if currently_executing:
            return cur
        else:
            if daily_delta:
                return trading_calendar.minute_to_session(cur).tz_localize(cur.tzinfo)
            else:
                return trading_calendar.session_open_close(trading_calendar.minute_to_session(cur))[
                    0
                ]

    # yield count trade events, all on trading days, and
    # during trading hours.
    while cur < end:
        if repeats:
            for _ in range(repeats):
                yield cur
        else:
            yield cur

        cur = advance_current(cur)


class SpecificEquityTrades:
    """Generate synthetic trade events for specific equity securities.

    Creates a stream of test trade events for specified securities over a
    given time range. Useful for testing backtesting algorithms with controlled,
    predictable data.

    The generator produces trades with:
    - Prices cycling from 1.0 to 10.0
    - Volumes cycling from 100 to 900 in increments of 50
    - Timestamps aligned to trading calendar

    Attributes:
        trading_calendar: Calendar defining valid trading times.
        count: Maximum number of events to generate (unused in current implementation).
        start: Starting datetime for trade generation.
        end: Ending datetime for trade generation.
        delta: Time interval between trades.
        sids: List of security IDs to generate trades for.

    Examples:
        Generate test trades for multiple securities::

            from datetime import datetime, timedelta

            source = SpecificEquityTrades(
                trading_calendar=calendar,
                asset_finder=finder,
                sids=[1, 2, 3],  # Generate for 3 securities
                start=datetime(2020, 1, 1),
                end=datetime(2020, 1, 31),
                delta=timedelta(minutes=1),
                count=500
            )

            # Iterate through generated trades
            for trade in source:
                print(f"Trade for sid {trade.sid} at {trade.dt}: ${trade.price}")

        Use in a backtesting simulation::

            algorithm = TradingAlgorithm(...)
            trades = SpecificEquityTrades(...)
            results = algorithm.run(trades)
    """

    def __init__(self, trading_calendar, asset_finder, sids, start, end, delta, count=500):
        """Initialize the trade generator.

        Args:
            trading_calendar: Trading calendar for valid trading times.
            asset_finder: Asset finder for security lookups (currently unused).
            sids: List of security IDs to generate trades for.
            start: Starting datetime for trade generation.
            end: Ending datetime for trade generation.
            delta: Time interval between trades.
            count: Maximum number of trades to generate. Default 500 (currently unused).
        """
        self.trading_calendar = trading_calendar

        # Unpack config dictionary with default values.
        self.count = count
        self.start = start
        self.end = end
        self.delta = delta
        self.sids = sids
        self.generator = self.create_fresh_generator()

    def __iter__(self):
        """Make this object iterable.

        Returns:
            Self, as this object implements the iterator protocol.
        """
        return self

    def next(self):
        """Get next trade event (Python 2 compatibility).

        Returns:
            The next trade event.
        """
        return self.generator.next()

    def __next__(self):
        """Get next trade event.

        Returns:
            The next trade event from the generator.

        Raises:
            StopIteration: When all trades have been generated.
        """
        return next(self.generator)

    def rewind(self):
        """Reset the generator to start from the beginning.

        Creates a fresh generator with the same configuration, allowing
        the trade stream to be iterated again.
        """
        self.generator = self.create_fresh_generator()

    def update_source_id(self, gen):
        """Update source_id on events from a generator.

        Args:
            gen: Generator yielding events.

        Yields:
            Events with updated source_id field.
        """
        for event in gen:
            event.source_id = self.get_hash()
            yield event

    def create_fresh_generator(self):
        """Create a new trade event generator.

        Generates synthetic trades with:
        - Prices cycling from 1.0 to 10.0
        - Volumes cycling from 100 to 900 in steps of 50
        - Timestamps from date_gen aligned to trading calendar
        - One trade per sid at each timestamp

        Returns:
            Generator yielding trade events for all configured securities
            across the configured time range.
        """
        date_generator = date_gen(
            start=self.start,
            end=self.end,
            delta=self.delta,
            trading_calendar=self.trading_calendar,
        )
        return (
            create_trade(
                sid=sid,
                price=float(i % 10) + 1.0,
                amount=(i * 50) % 900 + 100,
                datetime=date,
            )
            for (i, date), sid in itertools.product(enumerate(date_generator), self.sids)
        )
