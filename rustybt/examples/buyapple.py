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

"""Minimal example buying Apple stock repeatedly.

This is the simplest possible trading algorithm, designed as an introduction
to the rustybt API. It demonstrates:

- Looking up securities by symbol
- Placing orders on every bar
- Recording custom metrics for analysis
- Setting up commission and slippage models

The strategy naively buys 10 shares of Apple on every single bar of data,
continuously accumulating a position regardless of price or portfolio constraints.
This is not a realistic strategy, but serves as a clear demonstration of the
basic API.

Usage:
    Run this algorithm from the command line::

        rustybt run -f buyapple.py --start 2008-1-1 --end 2013-1-1 \\
            -o output.pickle --bundle quantopian-quandl

    Or run programmatically::

        from rustybt.examples.buyapple import initialize, handle_data, analyze
        from rustybt import run_algorithm
        import pandas as pd

        results = run_algorithm(
            initialize=initialize,
            handle_data=handle_data,
            analyze=analyze,
            start=pd.Timestamp('2008-01-01'),
            end=pd.Timestamp('2013-01-01'),
            capital_base=10000,
            bundle='quantopian-quandl'
        )

Note:
    This example includes an analyze() function that generates plots of
    portfolio value and Apple's price. The plots are displayed but not saved.
"""

from rustybt.api import Context, order, record, symbol
from rustybt.finance import commission, slippage


def initialize(context: Context) -> None:
    """Initialize the algorithm with Apple as the target asset.

    Sets up the algorithm to trade Apple stock with specified commission
    and slippage models.

    Args:
        context: Algorithm context object that persists throughout the
            simulation. Modified to store:
            - asset: The Apple stock security object
            - commission model: Per-share commission structure
            - slippage model: Volume-based slippage model

    Note:
        Uses legacy commission/slippage models for reproducibility with
        historical test data.
    """
    context.asset = symbol("AAPL")

    # Explicitly set the commission/slippage to the "old" value until we can
    # rebuild example data.
    # github.com/quantopian/zipline/blob/master/tests/resources/
    # rebuild_example_data#L105
    context.set_commission(commission.PerShare(cost=0.0075, min_trade_cost=1.0))
    context.set_slippage(slippage.VolumeShareSlippage())


def handle_data(context: Context, data) -> None:
    """Process each bar of market data.

    Called on every bar (minute or daily). Places an order for 10 shares
    of Apple and records the current Apple price for later analysis.

    Args:
        context: Algorithm context with the asset from initialize().
        data: Bar data object providing current and historical market data.

    Note:
        This strategy places orders on EVERY bar, which is unrealistic and
        will quickly accumulate a large position. It's purely for demonstration
        purposes.
    """
    order(context.asset, 10)
    record(AAPL=data.current(context.asset, "price"))


# Note: this function can be removed if running
# this algorithm on quantopian.com
def analyze(context=None, results=None):
    import matplotlib.pyplot as plt

    # Plot the portfolio and asset data.
    plt.clf()
    ax1 = plt.subplot(211)
    results.portfolio_value.plot(ax=ax1)
    ax1.set_ylabel("Portfolio value (USD)")
    ax2 = plt.subplot(212, sharex=ax1)
    results.AAPL.plot(ax=ax2)
    ax2.set_ylabel("AAPL price (USD)")

    # Show the plot.
    plt.gcf().set_size_inches(18, 8)
    plt.show()


def _test_args():
    """Extra arguments to use when zipline's automated tests run this example."""
    import pandas as pd

    return {"start": pd.Timestamp("2014-01-01"), "end": pd.Timestamp("2014-11-01")}
