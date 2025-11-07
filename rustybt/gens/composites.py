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

"""Utilities for merging and sorting event streams by timestamp.

This module provides functions for combining multiple event sources
into a single time-ordered stream, which is essential for simulation
when processing data from multiple assets or data sources.

Examples:
    Merge multiple data sources by timestamp::

        from rustybt.gens.composites import date_sorted_sources

        # Assume source1, source2 are generators yielding messages
        # with .dt and .source_id attributes
        merged_stream = date_sorted_sources(source1, source2, source3)

        for message in merged_stream:
            # Process messages in chronological order
            process_message(message)
"""

import heapq


def _decorate_source(source):
    """Decorate messages from a source with sorting keys.

    Wraps each message in a tuple containing (timestamp, source_id)
    for use in heap-based sorting. This ensures stable sorting when
    multiple messages have the same timestamp.

    Args:
        source: Iterable yielding messages with .dt and .source_id attributes.

    Yields:
        tuple: ((timestamp, source_id), message) pairs for sorting.

    Examples:
        Decorate a single source::

            messages = [msg1, msg2, msg3]  # Each has .dt and .source_id
            decorated = _decorate_source(messages)

            for (dt, sid), msg in decorated:
                print(f"Message at {dt} from source {sid}")
    """
    for message in source:
        yield ((message.dt, message.source_id), message)


def date_sorted_sources(*sources):
    """Merge multiple event sources into a single time-ordered stream.

    Takes multiple iterables of messages and merges them into a single
    stream sorted by timestamp. When messages have identical timestamps,
    they are ordered by source_id for deterministic behavior.

    Uses a heap-based merge for O(n log k) efficiency where n is the total
    number of messages and k is the number of sources.

    Args:
        *sources: Variable number of iterables, each yielding messages
            with .dt (timestamp) and .source_id attributes.

    Yields:
        message: Messages from all sources in chronological order.

    Examples:
        Merge trade data from multiple exchanges::

            from rustybt.gens.composites import date_sorted_sources

            # Three exchanges producing trade messages
            nyse_trades = generate_nyse_trades()
            nasdaq_trades = generate_nasdaq_trades()
            arca_trades = generate_arca_trades()

            # Merge into single time-ordered stream
            all_trades = date_sorted_sources(
                nyse_trades,
                nasdaq_trades,
                arca_trades
            )

            for trade in all_trades:
                # Process trades in the order they occurred
                process_trade(trade)

        Merge price and volume data::

            price_updates = get_price_feed()
            volume_updates = get_volume_feed()

            merged = date_sorted_sources(price_updates, volume_updates)

            for update in merged:
                if update.type == 'price':
                    handle_price_update(update)
                else:
                    handle_volume_update(update)
    """
    sorted_stream = heapq.merge(*(_decorate_source(s) for s in sources))

    # Strip out key decoration
    for _, message in sorted_stream:
        yield message
