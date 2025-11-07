"""Testing slippage model for deterministic order fills.

Provides a simple slippage model that fills a fixed number of shares
per tick, enabling deterministic and predictable test behavior.

Classes:
    TestingSlippage: Slippage model with constant fill amounts

Examples:
    Fill orders instantly::

        from rustybt.testing.slippage import TestingSlippage

        # Fill entire order immediately
        algo.set_slippage(TestingSlippage(TestingSlippage.ALL))

        # Place order that gets filled in one tick
        algo.order('AAPL', 100)

    Fill orders gradually::

        # Fill 10 shares per bar
        algo.set_slippage(TestingSlippage(filled_per_tick=10))

        # Order of 100 shares takes 10 bars to fill
        algo.order('AAPL', 100)

    Use in test fixtures::

        from rustybt.testing import ZiplineTestCase
        from rustybt.testing.slippage import TestingSlippage

        class MyAlgoTest(ZiplineTestCase):
            def test_order_fill(self):
                algo = self.make_algo(
                    slippage=TestingSlippage(filled_per_tick=50)
                )
                # Orders fill 50 shares per bar
"""

from rustybt.assets import Equity
from rustybt.finance.slippage import SlippageModel
from rustybt.utils.sentinel import sentinel


class TestingSlippage(SlippageModel):
    """Slippage model that fills a constant number of shares per tick.

    Simple slippage model for testing that fills either a fixed number
    of shares per bar or the entire order instantly. Provides predictable
    and deterministic order execution for tests.

    Attributes:
        ALL: Sentinel value to fill entire order immediately
        filled_per_tick: Number of shares to fill per bar
        allowed_asset_types: Tuple of allowed asset types (Equity only)

    Args:
        filled_per_tick: Number of shares to fill on each call to
            process_order, or TestingSlippage.ALL to fill entire order.

    Examples:
        Instant order fills::

            from rustybt.testing.slippage import TestingSlippage

            slippage = TestingSlippage(TestingSlippage.ALL)

            # In algorithm
            self.set_slippage(slippage)
            self.order('AAPL', 100)  # Filled immediately

        Gradual fills::

            # Fill 25 shares per bar
            slippage = TestingSlippage(filled_per_tick=25)

            self.set_slippage(slippage)
            self.order('AAPL', 100)  # Takes 4 bars to complete

    See Also:
        rustybt.finance.slippage.SlippageModel: Base slippage model class
    """

    __test__ = False
    ALL = sentinel("ALL")

    allowed_asset_types = (Equity,)

    def __init__(self, filled_per_tick):
        super(TestingSlippage, self).__init__()
        self.filled_per_tick = filled_per_tick

    def process_order(self, data, order):
        """Process an order and return fill price and volume.

        Determines how many shares to fill based on filled_per_tick setting.
        Always fills at the current close price.

        Args:
            data: BarData object providing current market data.
            order: Order object to process.

        Returns:
            tuple: (price, volume) where:
                - price: Fill price (current close)
                - volume: Number of shares to fill this tick

        Examples:
            Fill entire order::

                slippage = TestingSlippage(TestingSlippage.ALL)
                order = Order(asset=asset, amount=100)

                price, volume = slippage.process_order(data, order)
                assert volume == 100  # Entire order filled

            Partial fills::

                slippage = TestingSlippage(filled_per_tick=30)
                order = Order(asset=asset, amount=100)

                price, volume = slippage.process_order(data, order)
                assert volume == 30  # Only 30 shares filled
        """
        price = data.current(order.asset, "close")
        if self.filled_per_tick is self.ALL:
            volume = order.amount
        else:
            volume = self.filled_per_tick

        return price, volume
