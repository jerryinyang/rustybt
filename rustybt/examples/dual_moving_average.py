#!/usr/bin/env python
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

"""Dual Moving Average Crossover trading strategy.

This example demonstrates a classic technical analysis strategy based on
moving average crossovers. The algorithm:

1. Computes two moving averages: a short-term (100-day) and long-term (300-day)
2. Generates buy signals when the short MA crosses above the long MA
3. Generates sell signals when the short MA crosses below the long MA

Key Concepts Demonstrated:
    - Using data.history() to access historical price data
    - Computing technical indicators (moving averages)
    - Implementing state-based trading logic
    - Recording custom metrics for analysis
    - Handling warmup periods (waiting for full windows)

The Strategy:
    - **Buy Signal**: Short MA > Long MA (upward momentum)
      - Target position: 100 shares
    - **Sell Signal**: Short MA < Long MA (downward momentum)
      - Target position: 0 shares (exit)

Usage:
    Run this strategy from the command line::

        rustybt run -f dual_moving_average.py --start 2008-1-1 --end 2013-1-1 \\
            --bundle quantopian-quandl -o dma_results.pickle

    Or programmatically::

        from rustybt.examples.dual_moving_average import initialize, handle_data
        from rustybt import run_algorithm
        import pandas as pd

        results = run_algorithm(
            initialize=initialize,
            handle_data=handle_data,
            start=pd.Timestamp('2008'),
            end=pd.Timestamp('2013'),
            capital_base=100000,
            bundle='quantopian-quandl'
        )

Note:
    The algorithm skips the first 300 days to ensure the long moving average
    has a full window of data before making trading decisions.
"""

import os

from rustybt.api import order_target, record, symbol
from rustybt.finance import commission, slippage


def initialize(context):
    """Initialize the dual moving average strategy.

    Sets up the algorithm to trade Apple stock using moving average
    crossover signals.

    Args:
        context: Algorithm context that persists throughout simulation.
            Modified to store:
            - sym: The Apple stock security object
            - i: Counter for tracking elapsed bars
            - commission model: Per-share commission structure
            - slippage model: Volume-based slippage model
    """
    context.sym = symbol("AAPL")
    context.i = 0

    # Explicitly set the commission/slippage to the "old" value until we can
    # rebuild example data.
    # github.com/quantopian/zipline/blob/master/tests/resources/
    # rebuild_example_data#L105
    context.set_commission(commission.PerShare(cost=0.0075, min_trade_cost=1.0))
    context.set_slippage(slippage.VolumeShareSlippage())


def handle_data(context, data):
    """Execute moving average crossover strategy on each bar.

    Called on every bar of market data. Computes short and long moving
    averages and generates trading signals based on their relationship.

    Strategy Logic:
        1. Skip first 300 bars (warmup period for long MA)
        2. Compute 100-day and 300-day moving averages
        3. If short MA > long MA: Buy signal (target 100 shares)
        4. If short MA < long MA: Sell signal (target 0 shares)

    Args:
        context: Algorithm context containing:
            - sym: The security to trade
            - i: Bar counter for warmup period
        data: Bar data object providing current and historical prices.

    Note:
        Uses order_target() which adjusts position to reach target share count,
        automatically calculating how many shares to buy or sell.

    Example Signal Generation:
        If we have no position and short MA crosses above long MA:
        - order_target(sym, 100) will buy 100 shares

        If we have 100 shares and short MA crosses below long MA:
        - order_target(sym, 0) will sell all 100 shares
    """
    # Skip first 300 days to get full windows
    context.i += 1
    if context.i < 300:
        return

    # Compute averages
    # history() has to be called with the same params
    # from above and returns a pandas dataframe.
    short_mavg = data.history(context.sym, "price", 100, "1d").mean()
    long_mavg = data.history(context.sym, "price", 300, "1d").mean()

    # Trading logic
    if short_mavg > long_mavg:
        # order_target orders as many shares as needed to
        # achieve the desired number of shares.
        order_target(context.sym, 100)
    elif short_mavg < long_mavg:
        order_target(context.sym, 0)

    # Save values for later inspection
    record(
        AAPL=data.current(context.sym, "price"),
        short_mavg=short_mavg,
        long_mavg=long_mavg,
    )


# Note: this function can be removed if running
# this algorithm on quantopian.com
def analyze(context=None, results=None):
    import logging

    import matplotlib.pyplot as plt

    logging.basicConfig(
        format="[%(asctime)s-%(levelname)s][%(name)s]\n %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    log = logging.getLogger("Algorithm")

    fig = plt.figure()
    ax1 = fig.add_subplot(211)
    results.portfolio_value.plot(ax=ax1)
    ax1.set_ylabel("Portfolio value (USD)")

    ax2 = fig.add_subplot(212)
    ax2.set_ylabel("Price (USD)")

    # If data has been record()ed, then plot it.
    # Otherwise, log the fact that no data has been recorded.
    if "AAPL" in results and "short_mavg" in results and "long_mavg" in results:
        results["AAPL"].plot(ax=ax2)
        results[["short_mavg", "long_mavg"]].plot(ax=ax2)

        trans = results[[t != [] for t in results.transactions]]
        buys = trans[[t[0]["amount"] > 0 for t in trans.transactions]]
        sells = trans[[t[0]["amount"] < 0 for t in trans.transactions]]
        ax2.plot(
            buys.index,
            results.short_mavg.loc[buys.index],
            "^",
            markersize=10,
            color="m",
        )
        ax2.plot(
            sells.index,
            results.short_mavg.loc[sells.index],
            "v",
            markersize=10,
            color="k",
        )
        plt.legend(loc=0)
    else:
        msg = "AAPL, short_mavg & long_mavg data not captured using record()."
        ax2.annotate(msg, xy=(0.1, 0.5))
        log.info(msg)

    plt.show()

    if "PYTEST_CURRENT_TEST" in os.environ:
        plt.close("all")


def _test_args():
    """Extra arguments to use when zipline's automated tests run this example."""
    import pandas as pd

    return {"start": pd.Timestamp("2011"), "end": pd.Timestamp("2013")}
