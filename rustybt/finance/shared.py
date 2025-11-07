"""Shared metaclasses and utilities for financial models.

This module provides metaclasses that enable flexible financial model creation,
particularly for slippage and commission models that need to support multiple
asset types (equities, futures, cryptocurrencies, etc.).

The metaclass system allows users to create models that work with multiple
asset types by simply inheriting from the appropriate base classes.

Examples:
    Creating a custom slippage model that supports both equities and futures:

    >>> from rustybt.finance.slippage import EquitySlippageModel, FutureSlippageModel
    >>>
    >>> class MyCustomSlippage(EquitySlippageModel, FutureSlippageModel):
    ...     def process_order(self, data, order):
    ...         # Custom slippage logic here
    ...         return price, amount
    >>>
    >>> # This model automatically supports both equities and futures
    >>> model = MyCustomSlippage()
    >>> print(model.allowed_asset_types)  # (Equity, Future)
"""

from abc import ABCMeta
from itertools import chain


class FinancialModelMeta(ABCMeta):
    """Metaclass for financial models supporting multiple asset types.

    This metaclass allows users to create custom slippage and commission models
    that support both equities and futures by subclassing the appropriate
    individualized classes. The metaclass automatically merges the allowed_asset_types
    from all parent classes.

    Without this metaclass, when inheriting from multiple model classes, only the
    first parent's allowed_asset_types would be used (due to Python's MRO). This
    metaclass intelligently combines all allowed asset types from all parents.

    Args:
        name (str): The name of the class being created
        bases (tuple): The base classes being inherited from
        dict_ (dict): The class dictionary containing attributes and methods

    Returns:
        type: The newly created class with merged allowed_asset_types

    Examples:
        Creating a custom model supporting multiple asset types:

        >>> class MyCustomSlippage(EquitySlippageModel, FutureSlippageModel):
        ...     def process_order(self, data, order):
        ...         # Single implementation works for both asset types
        ...         price = data.current(order.asset, 'close')
        ...         return price, order.amount
        >>>
        >>> # The metaclass automatically merges allowed asset types
        >>> model = MyCustomSlippage()
        >>> model.allowed_asset_types  # (Equity, Future)

    Note:
        If a class explicitly defines allowed_asset_types, that definition
        takes precedence and the metaclass does not override it.
    """

    def __new__(mcls, name, bases, dict_):
        if "allowed_asset_types" not in dict_:
            allowed_asset_types = tuple(
                chain.from_iterable(
                    marker.allowed_asset_types
                    for marker in bases
                    if isinstance(marker, AllowedAssetMarker)
                )
            )
            if allowed_asset_types:
                dict_["allowed_asset_types"] = allowed_asset_types

        return super(FinancialModelMeta, mcls).__new__(
            mcls,
            name,
            bases,
            dict_,
        )


class AllowedAssetMarker(FinancialModelMeta):
    """Marker metaclass for financial models with asset type restrictions.

    This metaclass marks classes that specify which asset types they support
    via the allowed_asset_types attribute. It works in conjunction with
    FinancialModelMeta to enable proper merging of asset types when creating
    multi-asset models through multiple inheritance.

    Attributes:
        allowed_asset_types (tuple): Tuple of asset types (e.g., Equity, Future)
            that the model supports. Empty tuple by default.

    Examples:
        Creating an equity-only slippage model:

        >>> from rustybt.assets import Equity
        >>> from rustybt.finance.shared import AllowedAssetMarker
        >>>
        >>> class EquityOnlyModel(metaclass=AllowedAssetMarker):
        ...     allowed_asset_types = (Equity,)
        ...     def process_order(self, data, order):
        ...         return price, amount

    Note:
        This is primarily used internally by the slippage and commission model
        base classes. Users typically inherit from EquitySlippageModel or
        FutureSlippageModel rather than using this metaclass directly.
    """

    allowed_asset_types: tuple[type, ...] = ()
