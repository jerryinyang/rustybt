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
"""Exception classes for RustyBT trading algorithms.

This module defines all custom exceptions used throughout the RustyBT backtesting
framework. Exceptions are organized into hierarchical categories for different
error scenarios:

- Trading errors: Asset availability, order validation, transaction processing
- Configuration errors: Slippage, commission, cancel policy setup
- Pipeline errors: Term construction, data type validation, window operations
- Calendar/scheduling errors: Date handling, calendar management
- Asset database errors: Version management, asset lookups

All exceptions inherit from `ZiplineError` base class, which provides formatted
error messages with template substitution support.

Key Exception Categories:
    Trading & Market Data:
        - NoTradeDataAvailable: Asset data not available at requested time
        - InvalidBenchmarkAsset: Invalid benchmark configuration
        - CannotOrderDelistedAsset: Attempted order on delisted asset

    Configuration & Setup:
        - SetSlippagePostInit: Post-initialization configuration errors
        - UnsupportedCommissionModel: Invalid commission model
        - ZeroCapitalError: Invalid capital base

    Pipeline API:
        - TermInputsNotSpecified: Missing pipeline term inputs
        - WindowLengthTooLong: Invalid window specification
        - UnsupportedDataType: Incompatible data types

    Trading Controls:
        - TradingControlViolation: Order violates trading constraint
        - AccountControlViolation: Account violates constraint

Examples:
    Catching trade data errors:
        >>> from rustybt.errors import NoTradeDataAvailable
        >>> try:
        ...     price = data.current(asset, 'price')
        ... except NoTradeDataAvailable as e:
        ...     print(f"Data not available: {e}")

    Handling configuration errors:
        >>> from rustybt.errors import SetSlippagePostInit
        >>> try:
        ...     context.set_slippage(...)
        ... except SetSlippagePostInit as e:
        ...     print(f"Configuration error: {e}")
"""
from textwrap import dedent

from rustybt.utils.memoize import lazyval


class ZiplineError(Exception):
    """Base class for all RustyBT/Zipline exceptions.

    This base exception provides template-based error message formatting with
    keyword argument substitution. Subclasses define a `msg` class attribute
    containing a format string, and pass formatting values as kwargs to __init__.

    Attributes:
        msg (str): Format string template for the error message. Subclasses
            should define this as a class attribute.
        kwargs (dict): Keyword arguments used for message formatting.

    Examples:
        Creating a custom exception:
            >>> class MyError(ZiplineError):
            ...     msg = "Failed to process {asset} at {time}"
            >>> raise MyError(asset="AAPL", time="2024-01-01")
            MyError: Failed to process AAPL at 2024-01-01

        Accessing error details:
            >>> try:
            ...     raise MyError(asset="AAPL", time="2024-01-01")
            ... except MyError as e:
            ...     print(e.kwargs['asset'])  # 'AAPL'
    """

    msg = None

    def __init__(self, **kwargs):
        """Initialize exception with formatting arguments.

        Args:
            **kwargs: Keyword arguments for message template formatting.
                Keys should match placeholders in the `msg` template.
        """
        self.kwargs = kwargs

    @lazyval
    def message(self):
        """Get the formatted error message.

        Returns:
            str: The formatted error message.

        Note:
            This property is lazily evaluated and cached.
        """
        return str(self)

    def __str__(self):
        msg = self.msg.format(**self.kwargs)
        return msg

    __repr__ = __str__


class NoTradeDataAvailable(ZiplineError):
    """Base exception for assets with unavailable trading data.

    Raised when attempting to access data for an asset that doesn't have
    data available at the requested time. This can occur when:
    - The asset hasn't started trading yet
    - The asset has stopped trading
    - The asset is delisted

    See Also:
        NoTradeDataAvailableTooEarly: Asset data requested before trading start
        NoTradeDataAvailableTooLate: Asset data requested after trading end
    """

    pass


class NoTradeDataAvailableTooEarly(NoTradeDataAvailable):
    """Asset data requested before the asset started trading.

    Raised when attempting to access data for an asset before its
    first trading date.

    Attributes:
        sid: The security identifier of the asset
        dt: The datetime when data was requested
        start_dt: The actual start date of trading for this asset

    Examples:
        >>> # Assuming AAPL started trading on 1980-12-12
        >>> data.current(aapl, 'price')  # Called on 1980-01-01
        NoTradeDataAvailableTooEarly: AAPL does not exist on 1980-01-01.
        It started trading on 1980-12-12.
    """

    msg = "{sid} does not exist on {dt}. It started trading on {start_dt}."


class NoTradeDataAvailableTooLate(NoTradeDataAvailable):
    """Asset data requested after the asset stopped trading.

    Raised when attempting to access data for an asset after its
    last trading date (e.g., after delisting).

    Attributes:
        sid: The security identifier of the asset
        dt: The datetime when data was requested
        end_dt: The actual end date of trading for this asset

    Examples:
        >>> # Assuming DELL delisted on 2013-10-29
        >>> data.current(dell, 'price')  # Called on 2020-01-01
        NoTradeDataAvailableTooLate: DELL does not exist on 2020-01-01.
        It stopped trading on 2013-10-29.
    """

    msg = "{sid} does not exist on {dt}. It stopped trading on {end_dt}."


class BenchmarkAssetNotAvailableTooEarly(NoTradeDataAvailableTooEarly):
    """Benchmark asset data requested before the asset started trading.

    Raised when the specified benchmark asset doesn't have data available
    at the start of the backtest period because trading hasn't started yet.

    See Also:
        NoTradeDataAvailableTooEarly: General asset availability error
    """

    pass


class BenchmarkAssetNotAvailableTooLate(NoTradeDataAvailableTooLate):
    """Benchmark asset data requested after the asset stopped trading.

    Raised when the specified benchmark asset doesn't have data available
    at the end of the backtest period because trading has ended.

    See Also:
        NoTradeDataAvailableTooLate: General asset availability error
    """

    pass


class InvalidBenchmarkAsset(ZiplineError):
    """Asset cannot be used as benchmark due to corporate actions.

    Raised when attempting to use an asset as a benchmark that has
    disqualifying corporate actions such as stock dividends, which can
    complicate return calculations.

    Attributes:
        sid: The security identifier of the invalid benchmark asset
        dt: The datetime when the disqualifying event occurs

    Examples:
        >>> algo.set_benchmark(asset_with_stock_dividend)
        InvalidBenchmarkAsset: AAPL cannot be used as the benchmark because
        it has a stock dividend on 2020-08-28. Choose another asset to use
        as the benchmark.
    """

    msg = """
{sid} cannot be used as the benchmark because it has a stock \
dividend on {dt}.  Choose another asset to use as the benchmark.
""".strip()


class WrongDataForTransform(ZiplineError):
    """Raised whenever a rolling transform is called on an event that
    does not have the necessary properties.
    """

    msg = "{transform} requires {fields}. Event cannot be processed."


class UnsupportedSlippageModel(ZiplineError):
    """Raised if a user script calls the set_slippage magic
    with a slipage object that isn't a VolumeShareSlippage or
    FixedSlipapge
    """

    msg = """
You attempted to set slippage with an unsupported class. \
Please use VolumeShareSlippage or FixedSlippage.
""".strip()


class IncompatibleSlippageModel(ZiplineError):
    """Raised if a user tries to set a futures slippage model for equities or vice
    versa.
    """

    msg = """
You attempted to set an incompatible slippage model for {asset_type}. \
The slippage model '{given_model}' only supports {supported_asset_types}.
""".strip()


class SetSlippagePostInit(ZiplineError):
    # Raised if a users script calls set_slippage magic
    # after the initialize method has returned.
    msg = """
You attempted to set slippage outside of `initialize`. \
You may only call 'set_slippage' in your initialize method.
""".strip()


class SetCancelPolicyPostInit(ZiplineError):
    # Raised if a users script calls set_cancel_policy
    # after the initialize method has returned.
    msg = """
You attempted to set the cancel policy outside of `initialize`. \
You may only call 'set_cancel_policy' in your initialize method.
""".strip()


class RegisterTradingControlPostInit(ZiplineError):
    # Raised if a user's script register's a trading control after initialize
    # has been run.
    msg = """
You attempted to set a trading control outside of `initialize`. \
Trading controls may only be set in your initialize method.
""".strip()


class RegisterAccountControlPostInit(ZiplineError):
    # Raised if a user's script register's a trading control after initialize
    # has been run.
    msg = """
You attempted to set an account control outside of `initialize`. \
Account controls may only be set in your initialize method.
""".strip()


class UnsupportedCommissionModel(ZiplineError):
    """Raised if a user script calls the set_commission magic
    with a commission object that isn't a PerShare, PerTrade or
    PerDollar commission
    """

    msg = """
You attempted to set commission with an unsupported class. \
Please use PerShare or PerTrade.
""".strip()


class IncompatibleCommissionModel(ZiplineError):
    """Raised if a user tries to set a futures commission model for equities or
    vice versa.
    """

    msg = """
You attempted to set an incompatible commission model for {asset_type}. \
The commission model '{given_model}' only supports {supported_asset_types}.
""".strip()


class UnsupportedCancelPolicy(ZiplineError):
    """Raised if a user script calls set_cancel_policy with an object that isn't
    a CancelPolicy.
    """

    msg = """
You attempted to set the cancel policy with an unsupported class.  Please use
an instance of CancelPolicy.
""".strip()


class SetCommissionPostInit(ZiplineError):
    """Raised if a users script calls set_commission magic
    after the initialize method has returned.
    """

    msg = """
You attempted to override commission outside of `initialize`. \
You may only call 'set_commission' in your initialize method.
""".strip()


class TransactionWithNoVolume(ZiplineError):
    """Raised if a transact call returns a transaction with zero volume."""

    msg = """
Transaction {txn} has a volume of zero.
""".strip()


class TransactionWithWrongDirection(ZiplineError):
    """Raised if a transact call returns a transaction with a direction that
    does not match the order.
    """

    msg = """
Transaction {txn} not in same direction as corresponding order {order}.
""".strip()


class TransactionWithNoAmount(ZiplineError):
    """Raised if a transact call returns a transaction with zero amount."""

    msg = """
Transaction {txn} has an amount of zero.
""".strip()


class TransactionVolumeExceedsOrder(ZiplineError):
    """Raised if a transact call returns a transaction with a volume greater than
    the corresponding order.
    """

    msg = """
Transaction volume of {txn} exceeds the order volume of {order}.
""".strip()


class UnsupportedOrderParameters(ZiplineError):
    """Raised if a set of mutually exclusive parameters are passed to an order
    call.
    """

    msg = "{msg}"


class CannotOrderDelistedAsset(ZiplineError):
    """Raised if an order is for a delisted asset."""

    msg = "{msg}"


class BadOrderParameters(ZiplineError):
    """Raised if any impossible parameters (nan, negative limit/stop)
    are passed to an order call.
    """

    msg = "{msg}"


class OrderDuringInitialize(ZiplineError):
    """Raised if order is called during initialize()"""

    msg = "{msg}"


class SetBenchmarkOutsideInitialize(ZiplineError):
    """Raised if set_benchmark is called outside initialize()"""

    msg = "'set_benchmark' can only be called within initialize function."


class ZeroCapitalError(ZiplineError):
    """Initial capital is set at or below zero.

    Raised during algorithm initialization when the capital_base parameter
    is set to zero or a negative value. All backtests require positive
    initial capital.

    Examples:
        >>> algo = TradingAlgorithm(capital_base=0)
        ZeroCapitalError: initial capital base must be greater than zero

        >>> algo = TradingAlgorithm(capital_base=-1000)
        ZeroCapitalError: initial capital base must be greater than zero

    Note:
        The minimum valid capital_base is any positive value (e.g., 0.01),
        though typical backtests use realistic starting capital (e.g., 10000).
    """

    msg = "initial capital base must be greater than zero"


class AccountControlViolation(ZiplineError):
    """Account state violates a registered account control constraint.

    Raised when the algorithm's account violates constraints set via
    `register_account_control()`. Account controls check portfolio-level
    metrics like leverage, net leverage, or custom account-level constraints.

    Attributes:
        constraint: The AccountControl instance that was violated

    Examples:
        >>> # MaxLeverage constraint violated
        >>> context.register_account_control(MaxLeverage(1.0))
        >>> # ... later in backtest ...
        AccountControlViolation: Account violates account constraint
        MaxLeverage(1.0)

    See Also:
        TradingControlViolation: Order-level constraint violations
        rustybt.finance.controls: Available control types
    """

    msg = """
Account violates account constraint {constraint}.
""".strip()


class TradingControlViolation(ZiplineError):
    """Order would violate a registered trading control constraint.

    Raised when attempting to place an order that would violate constraints
    set via `register_trading_control()`. Trading controls validate individual
    orders against rules like max order size, restricted lists, or long-only.

    Attributes:
        amount: The number of shares in the attempted order
        asset: The asset for which the order was attempted
        datetime: The datetime when the order was attempted
        constraint: The TradingControl instance that was violated

    Examples:
        >>> # MaxOrderSize constraint violated
        >>> context.register_trading_control(MaxOrderSize(asset=aapl, max_shares=100))
        >>> context.order(aapl, 200)  # Attempt to order 200 shares
        TradingControlViolation: Order for 200 shares of AAPL at 2020-01-15
        15:59:00+00:00 violates trading constraint MaxOrderSize(AAPL, 100)

    See Also:
        AccountControlViolation: Account-level constraint violations
        rustybt.finance.controls: Available control types
    """

    msg = """
Order for {amount} shares of {asset} at {datetime} violates trading constraint
{constraint}.
""".strip()


class IncompatibleHistoryFrequency(ZiplineError):
    """Raised when a frequency is given to history which is not supported.
    At least, not yet.
    """

    msg = """
Requested history at frequency '{frequency}' cannot be created with data
at frequency '{data_frequency}'.
""".strip()


class OrderInBeforeTradingStart(ZiplineError):
    """Raised when an algorithm calls an order method in before_trading_start."""

    msg = "Cannot place orders inside before_trading_start."


class MultipleSymbolsFound(ZiplineError):
    """Raised when a symbol() call contains a symbol that changed over
    time and is thus not resolvable without additional information
    provided via as_of_date.
    """

    msg = """
Multiple symbols with the name '{symbol}' found. Use the
as_of_date' argument to specify when the date symbol-lookup
should be valid.

Possible options: {options}
    """.strip()


class MultipleSymbolsFoundForFuzzySymbol(MultipleSymbolsFound):
    """Raised when a fuzzy symbol lookup is not resolvable without additional
    information.
    """

    msg = dedent(
        """\
        Multiple symbols were found fuzzy matching the name '{symbol}'. Use
        the as_of_date and/or country_code arguments to specify the date
        and country for the symbol-lookup.

        Possible options: {options}
    """
    )


class SameSymbolUsedAcrossCountries(MultipleSymbolsFound):
    """Raised when a symbol() call contains a symbol that is used in more than
    one country and is thus not resolvable without a country_code.
    """

    msg = dedent(
        """\
        The symbol '{symbol}' is used in more than one country. Use the
        country_code argument to specify the country.

        Possible options by country: {options}
    """
    )


class SymbolNotFound(ZiplineError):
    """Raised when a symbol() call contains a non-existant symbol."""

    msg = """
Symbol '{symbol}' was not found.
""".strip()


class RootSymbolNotFound(ZiplineError):
    """Raised when a lookup_future_chain() call contains a non-existant symbol."""

    msg = """
Root symbol '{root_symbol}' was not found.
""".strip()


class ValueNotFoundForField(ZiplineError):
    """Raised when a lookup_by_supplementary_mapping() call contains a
    value does not exist for the specified mapping type.
    """

    msg = """
Value '{value}' was not found for field '{field}'.
""".strip()


class MultipleValuesFoundForField(ZiplineError):
    """Raised when a lookup_by_supplementary_mapping() call contains a
    value that changed over time for the specified field and is
    thus not resolvable without additional information provided via
    as_of_date.
    """

    msg = """
Multiple occurrences of the value '{value}' found for field '{field}'.
Use the 'as_of_date' or 'country_code' argument to specify when or where the
lookup should be valid.

Possible options: {options}
    """.strip()


class NoValueForSid(ZiplineError):
    """Raised when a get_supplementary_field() call contains a sid that
    does not have a value for the specified mapping type.
    """

    msg = """
No '{field}' value found for sid '{sid}'.
""".strip()


class MultipleValuesFoundForSid(ZiplineError):
    """Raised when a get_supplementary_field() call contains a value that
    changed over time for the specified field and is thus not resolvable
    without additional information provided via as_of_date.
    """

    msg = """
Multiple '{field}' values found for sid '{sid}'. Use the as_of_date' argument
to specify when the lookup should be valid.

Possible options: {options}
""".strip()


class SidsNotFound(ZiplineError):
    """One or more security identifiers (sids) not found in asset database.

    Raised when attempting to retrieve assets by sid and one or more of the
    requested sids don't exist in the asset database. This can occur with
    `retrieve_asset()`, `retrieve_all()`, or similar lookup methods.

    Attributes:
        sids (list): List of sids that were not found

    Examples:
        >>> asset_finder.retrieve_asset(999999)
        SidsNotFound: No asset found for sid: 999999.

        >>> asset_finder.retrieve_all([123, 456, 789])
        SidsNotFound: No assets found for sids: [123, 456, 789].

    Note:
        The error message automatically adjusts between singular and plural
        forms based on the number of missing sids.
    """

    @lazyval
    def plural(self):
        """Check if multiple sids are missing.

        Returns:
            bool: True if more than one sid is missing, False otherwise.
        """
        return len(self.sids) > 1

    @lazyval
    def sids(self):
        """Get the list of missing sids.

        Returns:
            list: The sids that were not found in the asset database.
        """
        return self.kwargs["sids"]

    @lazyval
    def msg(self):
        """Generate appropriate error message based on sid count.

        Returns:
            str: Singular or plural error message format string.
        """
        if self.plural:
            return "No assets found for sids: {sids}."
        return "No asset found for sid: {sids[0]}."


class EquitiesNotFound(SidsNotFound):
    """Raised when a call to `retrieve_equities` fails to find an asset."""

    @lazyval
    def msg(self):
        if self.plural:
            return "No equities found for sids: {sids}."
        return "No equity found for sid: {sids[0]}."


class FutureContractsNotFound(SidsNotFound):
    """Raised when a call to `retrieve_futures_contracts` fails to find an asset."""

    @lazyval
    def msg(self):
        if self.plural:
            return "No future contracts found for sids: {sids}."
        return "No future contract found for sid: {sids[0]}."


class ConsumeAssetMetaDataError(ZiplineError):
    """Raised when AssetFinder.consume() is called on an invalid object."""

    msg = """
AssetFinder can not consume metadata of type {obj}. Metadata must be a dict, a
DataFrame, or a tables.Table. If the provided metadata is a Table, the rows
must contain both or one of 'sid' or 'symbol'.
""".strip()


class SidAssignmentError(ZiplineError):
    """Raised when an AssetFinder tries to build an Asset that does not have a sid
    and that AssetFinder is not permitted to assign sids.
    """

    msg = """
AssetFinder metadata is missing a SID for identifier '{identifier}'.
""".strip()


class NoSourceError(ZiplineError):
    """Raised when no source is given to the pipeline"""

    msg = """
No data source given.
""".strip()


class PipelineDateError(ZiplineError):
    """Raised when only one date is passed to the pipeline"""

    msg = """
Only one simulation date given. Please specify both the 'start' and 'end' for
the simulation, or neither. If neither is given, the start and end of the
DataSource will be used. Given start = '{start}', end = '{end}'
""".strip()


class WindowLengthTooLong(ZiplineError):
    """Raised when a trailing window is instantiated with a lookback greater than
    the length of the underlying array.
    """

    msg = (
        "Can't construct a rolling window of length {window_length} on an array of length {nrows}."
    ).strip()


class WindowLengthNotPositive(ZiplineError):
    """Raised when a trailing window would be instantiated with a length less than
    1.
    """

    msg = ("Expected a window_length greater than 0, got {window_length}.").strip()


class NonWindowSafeInput(ZiplineError):
    """Raised when a Pipeline API term that is not deemed window safe is specified
    as an input to another windowed term.

    This is an error because it's generally not safe to compose windowed
    functions on split/dividend adjusted data.
    """

    msg = "Can't compute windowed expression {parent} with windowed input {child}."


class TermInputsNotSpecified(ZiplineError):
    """Raised if a user attempts to construct a term without specifying inputs and
    that term does not have class-level default inputs.
    """

    msg = "{termname} requires inputs, but no inputs list was passed."


class NonPipelineInputs(ZiplineError):
    """Raised when a non-pipeline object is passed as input to a ComputableTerm"""

    def __init__(self, term, inputs):
        self.term = term
        self.inputs = inputs

    def __str__(self):
        return (
            f"Unexpected input types in {type(self.term).__name__}. "
            "Inputs to Pipeline expressions must be Filters, Factors, "
            "Classifiers, or BoundColumns.\n"
            f"Got the following type(s) instead: {sorted(set(map(type, self.inputs)), key=lambda t: t.__name__)}"
        )


class TermOutputsEmpty(ZiplineError):
    """Raised if a user attempts to construct a term with an empty outputs list."""

    msg = "{termname} requires at least one output when passed an outputs argument."


class InvalidOutputName(ZiplineError):
    """Raised if a term's output names conflict with any of its attributes."""

    msg = (
        "{output_name!r} cannot be used as an output name for {termname}. "
        "Output names cannot start with an underscore or be contained in the "
        "following list: {disallowed_names}."
    )


class WindowLengthNotSpecified(ZiplineError):
    """Raised if a user attempts to construct a term without specifying window
    length and that term does not have a class-level default window length.
    """

    msg = "{termname} requires a window_length, but no window_length was passed."


class InvalidTermParams(ZiplineError):
    """Raised if a user attempts to construct a Term using ParameterizedTermMixin
    without specifying a `params` list in the class body.
    """

    msg = (
        "Expected a list of strings as a class-level attribute for "
        "{termname}.params, but got {value} instead."
    )


class DTypeNotSpecified(ZiplineError):
    """Raised if a user attempts to construct a term without specifying dtype and
    that term does not have class-level default dtype.
    """

    msg = "{termname} requires a dtype, but no dtype was passed."


class NotDType(ZiplineError):
    """Raised when a pipeline Term is constructed with a dtype that isn't a numpy
    dtype object.
    """

    msg = "{termname} expected a numpy dtype object for a dtype, but got {dtype} instead."


class UnsupportedDType(ZiplineError):
    """Raised when a pipeline Term is constructed with a dtype that's not
    supported.
    """

    msg = "Failed to construct {termname}.\nPipeline terms of dtype {dtype} are not yet supported."


class BadPercentileBounds(ZiplineError):
    """Raised by API functions accepting percentile bounds when the passed bounds
    are invalid.
    """

    msg = (
        "Percentile bounds must fall between 0.0 and {upper_bound}, and min "
        "must be less than max."
        "\nInputs were min={min_percentile}, max={max_percentile}."
    )


class UnknownRankMethod(ZiplineError):
    """Raised during construction of a Rank factor when supplied a bad Rank
    method.
    """

    msg = "Unknown ranking method: '{method}'. `method` must be one of {choices}"


class AttachPipelineAfterInitialize(ZiplineError):
    """Raised when a user tries to call add_pipeline outside of initialize."""

    msg = (
        "Attempted to attach a pipeline after initialize(). "
        "attach_pipeline() can only be called during initialize."
    )


class PipelineOutputDuringInitialize(ZiplineError):
    """Raised when a user tries to call `pipeline_output` during initialize."""

    msg = (
        "Attempted to call pipeline_output() during initialize. "
        "pipeline_output() can only be called once initialize has completed."
    )


class NoSuchPipeline(ZiplineError, KeyError):
    """Raised when a user tries to access a non-existent pipeline by name."""

    msg = (
        "No pipeline named '{name}' exists. Valid pipeline names are {valid}. "
        "Did you forget to call attach_pipeline()?"
    )


class DuplicatePipelineName(ZiplineError):
    """Raised when a user tries to attach a pipeline with a name that already
    exists for another attached pipeline.
    """

    msg = (
        "Attempted to attach pipeline named {name!r}, but the name already "
        "exists for another pipeline. Please use a different name for this "
        "pipeline."
    )


class UnsupportedDataType(ZiplineError):
    """
    Raised by CustomFactors with unsupported dtypes.
    """

    def __init__(self, hint="", **kwargs):
        if hint:
            hint = " " + hint
        kwargs["hint"] = hint
        super().__init__(**kwargs)

    msg = "{typename} instances with dtype {dtype} are not supported.{hint}"


class NoFurtherDataError(ZiplineError):
    """Calendar operation requested dates beyond available data range.

    Raised when calendar operations (like lookback windows) would require
    data from before the earliest available date or after the latest
    available date in the dataset.

    This commonly occurs when:
    - A pipeline window length extends before the start of available data
    - History calls request more bars than are available
    - Lookback periods extend beyond data boundaries

    Attributes:
        msg (str): Custom error message describing the specific issue

    Examples:
        >>> # Pipeline with 100-day lookback, but only 50 days of data
        >>> NoFurtherDataError: Initial window exceeds available data.
        ... lookback window started at 2020-01-01
        ... earliest known date was 2020-02-20
        ... 50 extra rows of data were required
    """

    # This accepts an arbitrary message string because it's used in more places
    # that can be usefully templated.
    msg = "{msg}"

    @classmethod
    def from_lookback_window(cls, initial_message, first_date, lookback_start, lookback_length):
        """Create error from lookback window parameters.

        Factory method for constructing NoFurtherDataError with detailed
        information about a lookback window that extends beyond available data.

        Args:
            initial_message (str): High-level description of the error
            first_date: The earliest date for which data is available
            lookback_start: The date at which the lookback window starts
            lookback_length (int): Number of additional data rows needed

        Returns:
            NoFurtherDataError: Configured exception with formatted message

        Examples:
            >>> error = NoFurtherDataError.from_lookback_window(
            ...     "Pipeline window too long",
            ...     pd.Timestamp('2020-01-15'),
            ...     pd.Timestamp('2020-01-01'),
            ...     10
            ... )
        """
        return cls(
            msg=dedent(
                """
                {initial_message}

                lookback window started at {lookback_start}
                earliest known date was {first_date}
                {lookback_length} extra rows of data were required
                """
            ).format(
                initial_message=initial_message,
                first_date=first_date,
                lookback_start=lookback_start,
                lookback_length=lookback_length,
            )
        )


class UnsupportedDatetimeFormat(ZiplineError):
    """Raised when an unsupported datetime is passed to an API method."""

    msg = "The input '{input}' passed to '{method}' is not coercible to a pandas.Timestamp object."


class AssetDBVersionError(ZiplineError):
    """
    Raised by an AssetDBWriter or AssetFinder if the version number in the
    versions table does not match the ASSET_DB_VERSION in asset_writer.py.
    """

    msg = (
        "The existing Asset database has an incorrect version: {db_version}. "
        "Expected version: {expected_version}. Try rebuilding your asset "
        "database or updating your version of Zipline."
    )


class AssetDBImpossibleDowngrade(ZiplineError):
    msg = (
        "The existing Asset database is version: {db_version} which is lower "
        "than the desired downgrade version: {desired_version}."
    )


class HistoryWindowStartsBeforeData(ZiplineError):
    msg = (
        "History window extends before {first_trading_day}. To use this "
        "history window, start the backtest on or after {suggested_start_day}."
    )


class NonExistentAssetInTimeFrame(ZiplineError):
    msg = (
        "The target asset '{asset}' does not exist for the entire timeframe "
        "between {start_date} and {end_date}."
    )


class InvalidCalendarName(ZiplineError):
    """Raised when a calendar with an invalid name is requested."""

    msg = "The requested TradingCalendar, {calendar_name}, does not exist."


class CalendarNameCollision(ZiplineError):
    """
    Raised when the static calendar registry already has a calendar with a
    given name.
    """

    msg = "A calendar with the name {calendar_name} is already registered."


class CyclicCalendarAlias(ZiplineError):
    """
    Raised when calendar aliases form a cycle.
    """

    msg = "Cycle in calendar aliases: [{cycle}]"


class ScheduleFunctionWithoutCalendar(ZiplineError):
    """
    Raised when schedule_function is called but there is not a calendar to be
    used in the construction of an event rule.
    """

    # TODO update message when new TradingSchedules are built
    msg = (
        "To use schedule_function, the TradingAlgorithm must be running on an "
        "ExchangeTradingSchedule, rather than {schedule}."
    )


class ScheduleFunctionInvalidCalendar(ZiplineError):
    """
    Raised when schedule_function is called with an invalid calendar argument.
    """

    msg = (
        "Invalid calendar '{given_calendar}' passed to schedule_function. "
        "Allowed options are {allowed_calendars}."
    )


class UnsupportedPipelineOutput(ZiplineError):
    """
    Raised when a 1D term is added as a column to a pipeline.
    """

    msg = (
        "Cannot add column {column_name!r} with term {term}. Adding slices or "
        "single-column-output terms as pipeline columns is not currently "
        "supported."
    )


class NonSliceableTerm(ZiplineError):
    """
    Raised when attempting to index into a non-sliceable term, e.g. instances
    of `zipline.pipeline.term.LoadableTerm`.
    """

    msg = "Taking slices of {term} is not currently supported."


class IncompatibleTerms(ZiplineError):
    """
    Raised when trying to compute correlations/regressions between two 2D
    factors with different masks.
    """

    msg = (
        "{term_1} and {term_2} must have the same mask in order to compute "
        "correlations and regressions asset-wise."
    )
