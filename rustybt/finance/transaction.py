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
from copy import copy

from rustybt.assets import Asset
from rustybt.protocol import DATASOURCE_TYPE
from rustybt.utils.input_validation import expect_types


class Transaction:
    @expect_types(asset=Asset)
    def __init__(self, asset, amount, dt, price, order_id):
        self.asset = asset
        self.amount = amount
        self.dt = dt
        self.price = price
        self.order_id = order_id
        self.type = DATASOURCE_TYPE.TRANSACTION

    def __getitem__(self, name):
        return self.__dict__[name]

    def __repr__(self):
        template = "{cls}(asset={asset}, dt={dt}, amount={amount}, price={price})"

        return template.format(
            cls=type(self).__name__,
            asset=self.asset,
            dt=self.dt,
            amount=self.amount,
            price=self.price,
        )

    def to_dict(self):
        py = copy(self.__dict__)
        del py["type"]
        del py["asset"]

        # Adding 'sid' for backwards compatibility with downstrean consumers.
        py["sid"] = self.asset

        # If you think this looks dumb, that is because it is! We once stored
        # commission here, but haven't for over a year. I don't want to change
        # the perf packet structure yet.
        py["commission"] = None

        return py


def create_transaction(order, dt, price, amount, fractional_order_mode=None):
    """Create a transaction from an order execution.

    Parameters
    ----------
    order : Order
        The order being executed.
    dt : pd.Timestamp
        The datetime of the transaction.
    price : float
        The execution price.
    amount : float
        The amount executed.
    fractional_order_mode : FractionalOrderMode, optional
        How to handle fractional amounts. If None, defaults to AUTO mode
        which auto-detects based on exchange.

    Returns
    -------
    Transaction
        The created transaction.

    Raises
    ------
    Exception
        If the transaction amount is too small (< 1 for equities, < 1e-8 for crypto).

    Notes
    -----
    Behavior depends on the ``fractional_order_mode`` setting:

    - AUTO (default): Crypto exchanges preserve fractional amounts,
      traditional exchanges round to integers
    - ALWAYS: All assets preserve fractional amounts
    - NEVER: All assets round to integer amounts

    For fractional assets, the minimum amount is 1e-8 (0.00000001).
    For integer assets, the minimum amount is 1.
    """
    from rustybt.finance.asset_config import FractionalOrderMode, should_use_fractional_orders

    # Default to AUTO mode if not specified
    if fractional_order_mode is None:
        fractional_order_mode = FractionalOrderMode.AUTO

    use_fractional = should_use_fractional_orders(order.asset, fractional_order_mode)

    if use_fractional:
        # For fractional orders, preserve the amount
        # Check that amount is not negligibly small (> 1e-8)
        amount_magnitude = abs(amount)
        if amount_magnitude < 1e-8:
            raise Exception(
                f"Transaction magnitude must be at least 1e-8 for fractional orders. "
                f"Got {amount_magnitude} for {order.asset.symbol}"
            )

        transaction = Transaction(
            asset=order.asset, amount=amount, dt=dt, price=price, order_id=order.id
        )
    else:
        # For integer orders, round to integer
        amount_magnitude = int(abs(amount))

        if amount_magnitude < 1:
            raise Exception(
                f"Transaction magnitude must be at least 1 for integer orders. "
                f"Got {amount} for {order.asset.symbol}"
            )

        transaction = Transaction(
            asset=order.asset, amount=int(amount), dt=dt, price=price, order_id=order.id
        )

    return transaction
