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

"""Utility functions for event validation and hashing.

Provides helper functions for:
- Generating deterministic hashes from function arguments
- Validating data source event protocols
- Asserting event structure and types

Functions:
    hash_args: Generate MD5 hash from args/kwargs for caching
    assert_datasource_protocol: Validate general datasource events
    assert_trade_protocol: Validate trade-specific events
    assert_datasource_unframe_protocol: Validate unframed events
"""

import numbers
from datetime import datetime
from hashlib import md5

import pytz

from rustybt.protocol import DATASOURCE_TYPE


def hash_args(*args, **kwargs):
    """Generate a unique hash string for any set of arguments.

    Creates an MD5 hash from the string representation of positional
    and keyword arguments. Useful for caching and memoization where
    function calls need to be uniquely identified by their inputs.

    Note: MD5 is used for checksums only, not cryptographic security.

    Args:
        *args: Positional arguments to hash.
        **kwargs: Keyword arguments to hash.

    Returns:
        str: Hexadecimal MD5 hash of the arguments.

    Examples:
        Generate cache keys::

            # Same arguments produce same hash
            hash1 = hash_args('AAPL', 100, side='buy')
            hash2 = hash_args('AAPL', 100, side='buy')
            assert hash1 == hash2

            # Different arguments produce different hashes
            hash3 = hash_args('AAPL', 200, side='buy')
            assert hash1 != hash3

        Use for function memoization::

            cache = {}

            def expensive_computation(symbol, lookback):
                key = hash_args(symbol, lookback)
                if key not in cache:
                    cache[key] = _do_computation(symbol, lookback)
                return cache[key]
    """
    arg_string = "_".join([str(arg) for arg in args])
    kwarg_string = "_".join([str(key) + "=" + str(value) for key, value in kwargs.items()])
    combined = ":".join([arg_string, kwarg_string])

    # SECURITY FIX (Story 8.10): MD5 used for checksums, not cryptography
    hasher = md5(usedforsecurity=False)
    hasher.update(combined.encode("utf-8"))
    return hasher.hexdigest()


def assert_datasource_protocol(event):
    """Assert that an event meets the protocol for datasource outputs.

    Validates that an event has the correct structure for a datasource:
    - Must have a valid event type from DATASOURCE_TYPE
    - Non-DONE events must have a datetime with UTC timezone

    Args:
        event: Event object to validate.

    Raises:
        AssertionError: If event doesn't meet protocol requirements.

    Examples:
        Validate event structure::

            from rustybt.protocol import DATASOURCE_TYPE

            # Create event (example structure)
            event = Event(
                type=DATASOURCE_TYPE.TRADE,
                dt=pd.Timestamp('2023-01-01', tz='UTC')
            )

            # This should pass
            assert_datasource_protocol(event)
    """
    assert event.type in DATASOURCE_TYPE

    # Done packets have no dt.
    if not event.type == DATASOURCE_TYPE.DONE:
        assert isinstance(event.dt, datetime)
        assert event.dt.tzinfo == pytz.utc


def assert_trade_protocol(event):
    """Assert that an event meets the protocol for TRADE datasource outputs.

    Validates that a trade event has:
    - Valid datasource protocol (via assert_datasource_protocol)
    - TRADE event type
    - Real number price
    - Integer volume
    - Datetime timestamp

    Args:
        event: Trade event object to validate.

    Raises:
        AssertionError: If event doesn't meet trade protocol requirements.

    Examples:
        Validate trade event::

            from rustybt.protocol import DATASOURCE_TYPE

            trade_event = TradeEvent(
                type=DATASOURCE_TYPE.TRADE,
                dt=pd.Timestamp('2023-01-01 10:00', tz='UTC'),
                price=150.25,
                volume=1000
            )

            # Should pass all assertions
            assert_trade_protocol(trade_event)
    """
    assert_datasource_protocol(event)

    assert event.type == DATASOURCE_TYPE.TRADE
    assert isinstance(event.price, numbers.Real)
    assert isinstance(event.volume, numbers.Integral)
    assert isinstance(event.dt, datetime)


def assert_datasource_unframe_protocol(event):
    """Assert that an event is valid output of datasource unframe operation.

    Validates that an unframed event has a valid DATASOURCE_TYPE.

    Args:
        event: Unframed event object to validate.

    Raises:
        AssertionError: If event type is not in DATASOURCE_TYPE.

    Examples:
        Validate unframed event::

            from rustybt.protocol import DATASOURCE_TYPE

            unframed_event = UnframedEvent(
                type=DATASOURCE_TYPE.CUSTOM
            )

            assert_datasource_unframe_protocol(unframed_event)
    """
    assert event.type in DATASOURCE_TYPE
