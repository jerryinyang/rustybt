#!/usr/bin/env python
#
# Copyright 2015 Quantopian, Inc.
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

"""Simple buy-and-hold strategy for multiple stocks.

This example demonstrates the most basic trading strategy: buying stocks
at the beginning and holding them throughout the simulation period. It
shows how to:

- Initialize context with configuration
- Execute trades only once using a flag
- Set commission and slippage models
- Order multiple securities

The strategy buys a fixed quantity (100 shares) of each configured stock
on the first data event and holds those positions for the entire backtest.

Usage:
    This example can be run directly or imported and used in tests::

        from rustybt.examples.buy_and_hold import initialize, handle_data
        from rustybt import run_algorithm

        results = run_algorithm(
            initialize=initialize,
            handle_data=handle_data,
            start=pd.Timestamp('2008'),
            end=pd.Timestamp('2013'),
            capital_base=10000,
            bundle='quantopian-quandl'
        )

Note:
    This example uses legacy commission/slippage models for reproducibility
    with historical test data.
"""
from rustybt.api import order, symbol
from rustybt.finance import commission, slippage

stocks = ["AAPL", "MSFT"]


def initialize(context):
    """Initialize the trading algorithm.

    Called once at the start of the simulation to set up the algorithm's
    initial state and configuration.

    Args:
        context: Algorithm context object that persists across function calls.
            Modified to store:
            - has_ordered: Flag to ensure we only order once
            - stocks: List of stock symbols to trade
            - commission model: Per-share commission structure
            - slippage model: Volume-based slippage model
    """
    context.has_ordered = False
    context.stocks = stocks

    # Explicitly set the commission/slippage to the "old" value until we can
    # rebuild example data.
    # github.com/quantopian/zipline/blob/master/tests/resources/
    # rebuild_example_data#L105
    context.set_commission(commission.PerShare(cost=0.0075, min_trade_cost=1.0))
    context.set_slippage(slippage.VolumeShareSlippage())


def handle_data(context, data):
    """Process each market data event.

    Called on each bar of market data (minute or daily depending on
    simulation frequency). Places orders on the first call, then
    does nothing for subsequent calls.

    Args:
        context: Algorithm context with state from initialize().
        data: Bar data object providing current and historical market data.

    Note:
        The has_ordered flag ensures we only place orders once at the
        beginning of the simulation, implementing a true buy-and-hold
        strategy.
    """
    if not context.has_ordered:
        for stock in context.stocks:
            order(symbol(stock), 100)
        context.has_ordered = True


def _test_args():
    """Extra arguments to use when zipline's automated tests run this example."""
    import pandas as pd

    return {"start": pd.Timestamp("2008"), "end": pd.Timestamp("2013")}
