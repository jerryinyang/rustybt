"""
Dataset representing OHLCV data.
"""

from rustybt.utils.numpy_utils import categorical_dtype, float64_dtype

from ..domain import US_EQUITIES
from .dataset import Column, DataSet


class EquityPricing(DataSet):
    """
    :class:`~zipline.pipeline.data.DataSet` containing daily trading prices and
    volumes.
    """

    open = Column(float64_dtype, currency_aware=True)
    high = Column(float64_dtype, currency_aware=True)
    low = Column(float64_dtype, currency_aware=True)
    close = Column(float64_dtype, currency_aware=True)
    volume = Column(float64_dtype)
    currency = Column(categorical_dtype)


# Backwards compat alias.
USEquityPricing = EquityPricing.specialize(US_EQUITIES)
