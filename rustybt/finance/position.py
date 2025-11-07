#
# Copyright 2018 Quantopian, Inc.
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

"""
Position Tracking
=================

    +-----------------+----------------------------------------------------+
    | key             | value                                              |
    +=================+====================================================+
    | asset           | the asset held in this position                    |
    +-----------------+----------------------------------------------------+
    | amount          | whole number of shares in the position             |
    +-----------------+----------------------------------------------------+
    | last_sale_price | price at last sale of the asset on the exchange    |
    +-----------------+----------------------------------------------------+
    | cost_basis      | the volume weighted average price paid per share   |
    +-----------------+----------------------------------------------------+

"""

import logging
from math import copysign

import numpy as np

import rustybt.protocol as zp
from rustybt.assets import Future

log = logging.getLogger("Performance")


class Position:
    __slots__ = "inner_position", "protocol_position"

    def __init__(self, asset, amount=0, cost_basis=0.0, last_sale_price=0.0, last_sale_date=None):
        """Initialize a position.

        Args:
            asset (Asset): The asset being held in this position
            amount (int, optional): Number of shares/units held. Positive for long
                positions, negative for short positions. Defaults to 0
            cost_basis (float, optional): Volume-weighted average price paid per
                share/unit. Defaults to 0.0
            last_sale_price (float, optional): Most recent market price for the asset.
                Defaults to 0.0
            last_sale_date (pd.Timestamp, optional): Date of the last sale price.
                Defaults to None

        Examples:
            Creating a long position:

            >>> position = Position(asset=aapl, amount=100, cost_basis=150.0)
            >>> print(f"Holding {position.amount} shares at ${position.cost_basis} cost basis")

            Creating a short position:

            >>> short_position = Position(asset=tsla, amount=-50, cost_basis=800.0)
            >>> print(f"Short {abs(short_position.amount)} shares")
        """
        inner = zp.InnerPosition(
            asset=asset,
            amount=amount,
            cost_basis=cost_basis,
            last_sale_price=last_sale_price,
            last_sale_date=last_sale_date,
        )
        object.__setattr__(self, "inner_position", inner)
        object.__setattr__(self, "protocol_position", zp.Position(inner))

    def __getattr__(self, attr):
        return getattr(self.inner_position, attr)

    def __setattr__(self, attr, value):
        setattr(self.inner_position, attr, value)

    def earn_dividend(self, dividend):
        """Calculate cash dividend owed based on shares held at ex-date.

        Registers the dividend payment that will be owed on the pay date based
        on the number of shares held at the ex-date. For short positions, the
        amount will be negative (representing a payment owed).

        Args:
            dividend: Dividend event with amount per share

        Returns:
            dict: Dictionary with 'amount' key containing total cash owed

        Examples:
            >>> position = Position(asset=aapl, amount=100)
            >>> dividend = Dividend(amount=0.25)  # $0.25 per share
            >>> payment = position.earn_dividend(dividend)
            >>> print(payment['amount'])  # 25.0 (100 shares * $0.25)

        Note:
            For short positions (negative amount), the returned amount is negative,
            representing cash the position must pay to the lender.
        """
        return {"amount": self.amount * dividend.amount}

    def earn_stock_dividend(self, stock_dividend):
        """Calculate stock dividend owed based on shares held at ex-date.

        Registers the stock dividend payment (in shares of another asset) that
        will be owed on the pay date. Fractional shares are floored to whole shares.

        Args:
            stock_dividend: Stock dividend event with payment_asset and ratio

        Returns:
            dict: Dictionary with keys:
                - 'payment_asset': Asset to receive as dividend
                - 'share_count': Number of whole shares to receive

        Examples:
            >>> position = Position(asset=googl, amount=100)
            >>> # 1:10 stock dividend in GOOG
            >>> stock_div = StockDividend(payment_asset=goog, ratio=0.1)
            >>> payment = position.earn_stock_dividend(stock_div)
            >>> print(payment['share_count'])  # 10 shares (100 * 0.1)

        Note:
            Fractional shares from the ratio calculation are dropped (floored).
            For example, 100 shares with a 0.105 ratio yields 10 shares, not 10.5.
        """
        return {
            "payment_asset": stock_dividend.payment_asset,
            "share_count": np.floor(self.amount * float(stock_dividend.ratio)),
        }

    def handle_split(self, asset, ratio):
        """Update position to reflect a stock split.

        Adjusts the position's share count and cost basis to account for a stock
        split. Fractional shares resulting from the split are converted to cash
        at the post-split cost basis.

        Args:
            asset (Asset): The asset that split (must match position's asset)
            ratio (float): Split ratio (e.g., 3.0 for a 3:1 split where 1 old
                share becomes 1/3 new shares)

        Returns:
            float: Cash value of fractional shares rounded to nearest cent

        Raises:
            Exception: If asset doesn't match position's asset

        Examples:
            3:1 reverse split (3 old shares become 1 new share):

            >>> position = Position(asset=aapl, amount=100, cost_basis=20.0)
            >>> cash_returned = position.handle_split(aapl, ratio=3.0)
            >>> print(f"New amount: {position.amount}")  # 33 shares
            >>> print(f"New cost basis: {position.cost_basis}")  # $60.00
            >>> print(f"Cash from fractional: ${cash_returned}")  # $20.00

            2:1 forward split (1 old share becomes 2 new shares):

            >>> position = Position(asset=tsla, amount=100, cost_basis=800.0)
            >>> cash_returned = position.handle_split(tsla, ratio=0.5)
            >>> print(f"New amount: {position.amount}")  # 200 shares
            >>> print(f"New cost basis: {position.cost_basis}")  # $400.00

        Note:
            The new cost basis is rounded to the nearest cent. Fractional shares
            are floored (e.g., 33.333 becomes 33) and the remainder is converted
            to cash at the new cost basis.
        """
        if self.asset != asset:
            raise Exception("updating split with the wrong asset!")

        # adjust the # of shares by the ratio
        # (if we had 100 shares, and the ratio is 3,
        #  we now have 33 shares)
        # (old_share_count / ratio = new_share_count)
        # (old_price * ratio = new_price)

        # e.g., 33.333
        raw_share_count = self.amount / float(ratio)

        # e.g., 33
        full_share_count = np.floor(raw_share_count)

        # e.g., 0.333
        fractional_share_count = raw_share_count - full_share_count

        # adjust the cost basis to the nearest cent, e.g., 60.0
        new_cost_basis = round(self.cost_basis * ratio, 2)

        self.cost_basis = new_cost_basis
        self.amount = full_share_count

        return_cash = round(float(fractional_share_count * new_cost_basis), 2)

        log.info("after split: " + str(self))
        log.info("returning cash: " + str(return_cash))

        # return the leftover cash, which will be converted into cash
        # (rounded to the nearest cent)
        return return_cash

    def update(self, txn):
        """Update position based on a transaction.

        Modifies the position's amount and cost basis to reflect a new transaction.
        The cost basis calculation depends on whether the transaction increases,
        decreases, or reverses the position.

        Args:
            txn (Transaction): Transaction to apply to the position. Must be for
                the same asset as the position

        Raises:
            Exception: If transaction is for a different asset

        Examples:
            Adding to a long position (buy more):

            >>> position = Position(asset=aapl, amount=100, cost_basis=150.0)
            >>> txn = Transaction(asset=aapl, amount=50, price=160.0, dt=timestamp, order_id='abc')
            >>> position.update(txn)
            >>> # New cost basis: (100*150 + 50*160) / 150 = 153.33
            >>> print(f"Amount: {position.amount}, Cost basis: {position.cost_basis:.2f}")

            Reducing a position (sell some):

            >>> position = Position(asset=aapl, amount=100, cost_basis=150.0)
            >>> txn = Transaction(asset=aapl, amount=-30, price=160.0, dt=timestamp, order_id='abc')
            >>> position.update(txn)
            >>> # Cost basis stays 150.0 (reducing position doesn't change basis)
            >>> print(f"Amount: {position.amount}, Cost basis: {position.cost_basis:.2f}")

            Reversing a position (sell more than you own):

            >>> position = Position(asset=aapl, amount=100, cost_basis=150.0)
            >>> txn = Transaction(asset=aapl, amount=-150, price=160.0, dt=timestamp, order_id='abc')
            >>> position.update(txn)
            >>> # New cost basis is the reversal price: 160.0
            >>> print(f"Amount: {position.amount}, Cost basis: {position.cost_basis:.2f}")

        Note:
            Cost basis calculation rules:
            - Increasing position: weighted average of old and new
            - Decreasing position: cost basis unchanged
            - Reversing position: cost basis set to reversal transaction price
            - Closing position: cost basis set to 0.0
        """
        if self.asset != txn.asset:
            raise Exception("updating position with txn for a different asset")

        total_shares = self.amount + txn.amount

        if total_shares == 0:
            self.cost_basis = 0.0
        else:
            prev_direction = copysign(1, self.amount)
            txn_direction = copysign(1, txn.amount)

            if prev_direction != txn_direction:
                # we're covering a short or closing a position
                if abs(txn.amount) > abs(self.amount):
                    # we've closed the position and gone short
                    # or covered the short position and gone long
                    self.cost_basis = txn.price
            else:
                prev_cost = self.cost_basis * self.amount
                txn_cost = txn.amount * txn.price
                total_cost = prev_cost + txn_cost
                self.cost_basis = total_cost / total_shares

            # Update the last sale price if txn is
            # best data we have so far
            if self.last_sale_date is None or txn.dt > self.last_sale_date:
                self.last_sale_price = txn.price
                self.last_sale_date = txn.dt

        self.amount = total_shares

    def adjust_commission_cost_basis(self, asset, cost):
        """Adjust cost basis to account for commission costs.

        Modifies the position's cost basis to include commission charges. The
        commission is spread across all shares in the position, increasing the
        effective cost basis (for long positions) or decreasing it (for short
        positions).

        Args:
            asset (Asset): The asset (must match position's asset)
            cost (float): Total commission cost to add to the position. For
                futures, this is divided by the price multiplier

        Raises:
            Exception: If asset doesn't match position's asset

        Examples:
            Adding commission to a long position:

            >>> position = Position(asset=aapl, amount=100, cost_basis=150.0)
            >>> position.adjust_commission_cost_basis(aapl, cost=10.0)
            >>> # New cost basis: (100*150 + 10) / 100 = 150.10
            >>> print(f"Cost basis: ${position.cost_basis:.2f}")

            Adding commission to a short position:

            >>> short_position = Position(asset=tsla, amount=-50, cost_basis=800.0)
            >>> short_position.adjust_commission_cost_basis(tsla, cost=5.0)
            >>> # New cost basis: (-50*800 + 5) / -50 = 799.90
            >>> # Cost basis decreases because we break even at a lower price
            >>> print(f"Cost basis: ${short_position.cost_basis:.2f}")

        Note:
            Cost basis represents the price at which the position breaks even.
            For long positions, commissions increase the break-even price.
            For short positions, commissions decrease the break-even price.

            If the position has zero shares, the commission is ignored (no
            cost basis to adjust).

            For futures contracts, the cost is divided by the asset's price
            multiplier before being added to the cost basis.
        """
        if asset != self.asset:
            raise Exception("Updating a commission for a different asset?")
        if cost == 0.0:
            return

        # If we no longer hold this position, there is no cost basis to
        # adjust.
        if self.amount == 0:
            return

        # We treat cost basis as the share price where we have broken even.
        # For longs, commissions cause a relatively straight forward increase
        # in the cost basis.
        #
        # For shorts, you actually want to decrease the cost basis because you
        # break even and earn a profit when the share price decreases.
        #
        # Shorts are represented as having a negative `amount`.
        #
        # The multiplication and division by `amount` cancel out leaving the
        # cost_basis positive, while subtracting the commission.

        prev_cost = self.cost_basis * self.amount
        if isinstance(asset, Future):
            cost_to_use = cost / asset.price_multiplier
        else:
            cost_to_use = cost
        new_cost = prev_cost + cost_to_use
        self.cost_basis = new_cost / self.amount

    def __repr__(self):
        template = "asset: {asset}, amount: {amount}, cost_basis: {cost_basis}, \
last_sale_price: {last_sale_price}"
        return template.format(
            asset=self.asset,
            amount=self.amount,
            cost_basis=self.cost_basis,
            last_sale_price=self.last_sale_price,
        )

    def to_dict(self):
        """
        Creates a dictionary representing the state of this position.
        Returns a dict object of the form:
        """
        return {
            "sid": self.asset,
            "amount": self.amount,
            "cost_basis": self.cost_basis,
            "last_sale_price": self.last_sale_price,
        }

    def _repr_html_(self):
        """Rich HTML representation for Jupyter notebooks.

        Returns:
            HTML string with formatted position information
        """
        # Calculate market value and P&L
        market_value = self.amount * self.last_sale_price
        cost = self.amount * self.cost_basis
        pnl = market_value - cost
        pnl_pct = (pnl / abs(cost) * 100) if cost != 0 else 0

        # Determine position type
        position_type = "LONG" if self.amount > 0 else "SHORT" if self.amount < 0 else "FLAT"

        # Color code P&L
        pnl_color = "#00c853" if pnl >= 0 else "#d32f2f"

        html = f"""
        <div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 5px 0;">
            <h4 style="margin: 0 0 10px 0;">Position: {self.asset.symbol if hasattr(self.asset, "symbol") else self.asset}</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 5px; font-weight: bold;">Type</td>
                    <td style="padding: 5px;">{position_type}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 5px; font-weight: bold;">Quantity</td>
                    <td style="padding: 5px;">{self.amount:,.0f}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 5px; font-weight: bold;">Cost Basis</td>
                    <td style="padding: 5px;">${self.cost_basis:,.2f}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 5px; font-weight: bold;">Last Price</td>
                    <td style="padding: 5px;">${self.last_sale_price:,.2f}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 5px; font-weight: bold;">Market Value</td>
                    <td style="padding: 5px;">${market_value:,.2f}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 5px; font-weight: bold;">P&L</td>
                    <td style="padding: 5px; color: {pnl_color}; font-weight: bold;">
                        ${pnl:,.2f} ({pnl_pct:+.2f}%)
                    </td>
                </tr>
            </table>
        </div>
        """
        return html
