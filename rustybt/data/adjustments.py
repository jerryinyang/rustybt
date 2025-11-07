"""Corporate action adjustments reader and writer for backtesting.

This module provides infrastructure for storing and retrieving corporate action
data (splits, dividends, mergers) from a SQLite database. These adjustments are
applied retrospectively to historical pricing data to maintain comparability
across corporate actions.

Key Classes:
    SQLiteAdjustmentReader:
        Reads corporate action data from SQLite and provides it in formats
        suitable for adjustment application during backtesting.

    SQLiteAdjustmentWriter:
        Writes corporate action data to SQLite in a structured format.

Supported Corporate Actions:
    Splits:
        Stock splits that affect price and volume. A 2-for-1 split multiplies
        shares by 2 and divides price by 2. Historical prices are adjusted by
        the split ratio.

    Dividends:
        Cash dividends paid to shareholders. Historical prices are adjusted
        downward by the dividend amount to maintain comparability.

    Mergers:
        Mergers and acquisitions that result in share exchanges. Historical
        prices are adjusted by the merger ratio.

    Dividend Payouts:
        Detailed dividend information including ex-date, pay-date, and amount.
        Used for tracking dividend payments during simulation.

    Stock Dividends:
        Dividends paid in shares rather than cash. Includes the payment asset
        and ratio of shares received.

Database Schema:
    The adjustment database contains the following tables:

    - splits: effective_date, ratio, sid
    - dividends: effective_date, ratio, sid
    - mergers: effective_date, ratio, sid
    - dividend_payouts: sid, ex_date, declared_date, record_date, pay_date, amount
    - stock_dividend_payouts: sid, ex_date, declared_date, record_date, pay_date,
                               payment_sid, ratio

Data Types:
    Dividend: Named tuple (asset, amount, pay_date)
    StockDividend: Named tuple (asset, payment_asset, ratio, pay_date)

Usage Patterns:
    Reading adjustments:
        >>> from rustybt.data import SQLiteAdjustmentReader
        >>> reader = SQLiteAdjustmentReader("adjustments.db")
        >>> adjustments = reader.load_adjustments(
        ...     dates=date_range,
        ...     assets=asset_list,
        ...     should_include_splits=True,
        ...     should_include_dividends=True,
        ...     should_include_mergers=True,
        ...     adjustment_type="all"
        ... )

    Getting dividends for a date:
        >>> dividends = reader.get_dividends_with_ex_date(
        ...     assets=asset_list,
        ...     date=ex_date,
        ...     asset_finder=finder
        ... )

    Writing adjustments:
        >>> from rustybt.data import SQLiteAdjustmentWriter
        >>> writer = SQLiteAdjustmentWriter("adjustments.db")
        >>> writer.write(
        ...     splits=splits_df,
        ...     dividends=dividends_df,
        ...     dividend_payouts=payouts_df
        ... )

See Also:
    rustybt.data.history_loader: Uses adjustments for historical data
    rustybt.lib.adjustment: Low-level adjustment application
    rustybt.assets: Asset definitions that adjustments apply to

Performance Notes:
    - Adjustment lookups are optimized with proper indexing
    - Batch operations are more efficient than individual queries
    - Dates are stored as Unix timestamps (int64) for fast comparison
"""

import logging
import sqlite3
from collections import namedtuple
from errno import ENOENT
from os import remove

import numpy as np
import pandas as pd
from numpy import integer as any_integer

from rustybt.utils.functional import keysorted
from rustybt.utils.input_validation import preprocess
from rustybt.utils.numpy_utils import (
    datetime64ns_dtype,
    float64_dtype,
    int64_dtype,
    uint32_dtype,
    uint64_dtype,
)
from rustybt.utils.pandas_utils import empty_dataframe
from rustybt.utils.sqlite_utils import coerce_string_to_conn, group_into_chunks

from ._adjustments import load_adjustments_from_sqlite

log = logging.getLogger(__name__)

SQLITE_ADJUSTMENT_TABLENAMES = frozenset(["splits", "dividends", "mergers"])

UNPAID_QUERY_TEMPLATE = """
SELECT sid, amount, pay_date from dividend_payouts
WHERE ex_date=? AND sid IN ({0})
"""

Dividend = namedtuple("Dividend", ["asset", "amount", "pay_date"])

UNPAID_STOCK_DIVIDEND_QUERY_TEMPLATE = """
SELECT sid, payment_sid, ratio, pay_date from stock_dividend_payouts
WHERE ex_date=? AND sid IN ({0})
"""

StockDividend = namedtuple(
    "StockDividend",
    ["asset", "payment_asset", "ratio", "pay_date"],
)

SQLITE_ADJUSTMENT_COLUMN_DTYPES = {
    "effective_date": any_integer,
    "ratio": float64_dtype,
    "sid": any_integer,
}

SQLITE_DIVIDEND_PAYOUT_COLUMN_DTYPES = {
    "sid": any_integer,
    "ex_date": any_integer,
    "declared_date": any_integer,
    "record_date": any_integer,
    "pay_date": any_integer,
    "amount": float,
}

SQLITE_STOCK_DIVIDEND_PAYOUT_COLUMN_DTYPES = {
    "sid": any_integer,
    "ex_date": any_integer,
    "declared_date": any_integer,
    "record_date": any_integer,
    "pay_date": any_integer,
    "payment_sid": any_integer,
    "ratio": float,
}


def specialize_any_integer(d):
    """Convert any_integer placeholders to explicit int64 dtype.

    Used to ensure consistent integer dtypes across platforms. The any_integer
    type accepts various integer dtypes from users but can become int32 on some
    Windows numpy builds. This function ensures outputs always use int64.

    Args:
        d: Dict mapping column names to dtypes.

    Returns:
        dict: New dict with any_integer replaced by int64_dtype.
    """
    out = {}
    for k, v in d.items():
        if v is any_integer:
            out[k] = int64_dtype
        else:
            out[k] = v
    return out


class SQLiteAdjustmentReader:
    """Loads adjustments based on corporate actions from a SQLite database.

    Expects data written in the format output by `SQLiteAdjustmentWriter`.

    Parameters
    ----------
    conn : str or sqlite3.Connection
        Connection from which to load data.

    See Also:
    --------
    :class:`zipline.data.adjustments.SQLiteAdjustmentWriter`
    """

    _datetime_int_cols = {
        "splits": ("effective_date",),
        "mergers": ("effective_date",),
        "dividends": ("effective_date",),
        "dividend_payouts": (
            "declared_date",
            "ex_date",
            "pay_date",
            "record_date",
        ),
        "stock_dividend_payouts": (
            "declared_date",
            "ex_date",
            "pay_date",
            "record_date",
        ),
    }
    _raw_table_dtypes = {
        # We use any_integer above to be lenient in accepting different dtypes
        # from users. For our outputs, however, we always want to return the
        # same types, and any_integer turns into int32 on some numpy windows
        # builds, so specify int64 explicitly here.
        "splits": specialize_any_integer(SQLITE_ADJUSTMENT_COLUMN_DTYPES),
        "mergers": specialize_any_integer(SQLITE_ADJUSTMENT_COLUMN_DTYPES),
        "dividends": specialize_any_integer(SQLITE_ADJUSTMENT_COLUMN_DTYPES),
        "dividend_payouts": specialize_any_integer(
            SQLITE_DIVIDEND_PAYOUT_COLUMN_DTYPES,
        ),
        "stock_dividend_payouts": specialize_any_integer(
            SQLITE_STOCK_DIVIDEND_PAYOUT_COLUMN_DTYPES,
        ),
    }

    @preprocess(conn=coerce_string_to_conn(require_exists=True))
    def __init__(self, conn):
        """Initialize the adjustment reader.

        Args:
            conn: Database connection string or sqlite3.Connection object.
                If a string, must point to an existing database file.
        """
        self.conn = conn

    def __enter__(self):
        """Enter context manager.

        Returns:
            SQLiteAdjustmentReader: Self for context manager usage.
        """
        return self

    def __exit__(self, *exc_info):
        """Exit context manager, closing the connection.

        Args:
            *exc_info: Exception information if an error occurred.
        """
        self.close()

    def close(self):
        """Close the database connection."""
        return self.conn.close()

    def load_adjustments(
        self,
        dates,
        assets,
        should_include_splits,
        should_include_mergers,
        should_include_dividends,
        adjustment_type,
    ):
        """Load collection of Adjustment objects from underlying adjustments db.

        Parameters
        ----------
        dates : pd.DatetimeIndex
            Dates for which adjustments are needed.
        assets : pd.Int64Index
            Assets for which adjustments are needed.
        should_include_splits : bool
            Whether split adjustments should be included.
        should_include_mergers : bool
            Whether merger adjustments should be included.
        should_include_dividends : bool
            Whether dividend adjustments should be included.
        adjustment_type : str
            Whether price adjustments, volume adjustments, or both, should be
            included in the output.

        Returns:
        -------
        adjustments : dict[str -> dict[int -> Adjustment]]
            A dictionary containing price and/or volume adjustment mappings
            from index to adjustment objects to apply at that index.
        """
        dates = dates.tz_localize("UTC")
        return load_adjustments_from_sqlite(
            self.conn,
            dates,
            assets,
            should_include_splits,
            should_include_mergers,
            should_include_dividends,
            adjustment_type,
        )

    def load_pricing_adjustments(self, columns, dates, assets):
        """Load adjustments for pricing columns automatically determining type.

        Convenience method that determines whether to load price, volume, or both
        types of adjustments based on the requested columns. Includes all corporate
        action types (splits, dividends, mergers).

        Args:
            columns: List of column names ('open', 'high', 'low', 'close', 'volume').
            dates: DatetimeIndex of dates for which adjustments are needed.
            assets: List or Index of assets (sids) to load adjustments for.

        Returns:
            list[dict]: List of adjustment dicts, one per column. Each dict maps
                date indices to adjustment objects.
        """
        if "volume" not in set(columns):
            adjustment_type = "price"
        elif len(set(columns)) == 1:
            adjustment_type = "volume"
        else:
            adjustment_type = "all"

        adjustments = self.load_adjustments(
            dates,
            assets,
            should_include_splits=True,
            should_include_mergers=True,
            should_include_dividends=True,
            adjustment_type=adjustment_type,
        )
        price_adjustments = adjustments.get("price")
        volume_adjustments = adjustments.get("volume")

        return [
            volume_adjustments if column == "volume" else price_adjustments for column in columns
        ]

    def get_adjustments_for_sid(self, table_name, sid):
        """Get all adjustments for a specific asset from a table.

        Retrieves all corporate action adjustments (splits, dividends, or mergers)
        for a single asset, sorted by effective date.

        Args:
            table_name: Name of adjustment table ('splits', 'dividends', 'mergers').
            sid: Asset identifier to query.

        Returns:
            list[[Timestamp, float]]: List of [effective_date, ratio] pairs for
                the asset, where effective_date is a pandas Timestamp and ratio
                is the adjustment ratio.

        Raises:
            ValueError: If table_name is not a valid adjustment table.
        """
        # Validate table name to prevent SQL injection
        if table_name not in SQLITE_ADJUSTMENT_TABLENAMES:
            raise ValueError(
                f"Invalid table name: {table_name}. "
                f"Must be one of {SQLITE_ADJUSTMENT_TABLENAMES}"
            )

        t = (sid,)
        c = self.conn.cursor()
        # Table name is now validated, safe to use in query  # nosec B608
        adjustments_for_sid = c.execute(
            f"SELECT effective_date, ratio FROM {table_name} WHERE sid = ?", t
        ).fetchall()
        c.close()

        return [
            [pd.Timestamp(adjustment[0], unit="s"), adjustment[1]]
            for adjustment in adjustments_for_sid
        ]

    def get_dividends_with_ex_date(self, assets, date, asset_finder):
        """Get all cash dividends with a specific ex-date.

        Queries the dividend_payouts table for all dividends whose ex-date matches
        the specified date. Used during simulation to determine which dividends
        go ex on a given trading day.

        Args:
            assets: Iterable of asset sids to check for dividends.
            date: Timestamp representing the ex-date to query.
            asset_finder: AssetFinder for converting sids to Asset objects.

        Returns:
            list[Dividend]: List of Dividend namedtuples with fields:
                - asset: Asset object receiving the dividend
                - amount: Cash amount of the dividend
                - pay_date: Timestamp when dividend will be paid
        """
        seconds = date.value / int(1e9)
        c = self.conn.cursor()

        divs = []
        for chunk in group_into_chunks(assets):
            query = UNPAID_QUERY_TEMPLATE.format(",".join(["?" for _ in chunk]))
            t = (seconds,) + tuple(map(lambda x: int(x), chunk))

            c.execute(query, t)

            rows = c.fetchall()
            for row in rows:
                div = Dividend(
                    asset_finder.retrieve_asset(row[0]),
                    row[1],
                    pd.Timestamp(row[2], unit="s", tz="UTC"),
                )
                divs.append(div)
        c.close()

        return divs

    def get_stock_dividends_with_ex_date(self, assets, date, asset_finder):
        """Get all stock dividends with a specific ex-date.

        Queries the stock_dividend_payouts table for all stock dividends whose
        ex-date matches the specified date. Stock dividends pay shares instead
        of cash.

        Args:
            assets: Iterable of asset sids to check for stock dividends.
            date: Timestamp representing the ex-date to query.
            asset_finder: AssetFinder for converting sids to Asset objects.

        Returns:
            list[StockDividend]: List of StockDividend namedtuples with fields:
                - asset: Asset object receiving the dividend
                - payment_asset: Asset object representing the shares paid out
                - ratio: Number of payment_asset shares per asset share held
                - pay_date: Timestamp when dividend shares will be distributed
        """
        seconds = date.value / int(1e9)
        c = self.conn.cursor()

        stock_divs = []
        for chunk in group_into_chunks(assets):
            query = UNPAID_STOCK_DIVIDEND_QUERY_TEMPLATE.format(",".join(["?" for _ in chunk]))
            t = (seconds,) + tuple(map(lambda x: int(x), chunk))

            c.execute(query, t)

            rows = c.fetchall()

            for row in rows:
                stock_div = StockDividend(
                    asset_finder.retrieve_asset(row[0]),  # asset
                    asset_finder.retrieve_asset(row[1]),  # payment_asset
                    row[2],
                    pd.Timestamp(row[3], unit="s", tz="UTC"),
                )
                stock_divs.append(stock_div)
        c.close()

        return stock_divs

    def unpack_db_to_component_dfs(self, convert_dates=False):
        """Returns the set of known tables in the adjustments file in DataFrame
        form.

        Parameters
        ----------
        convert_dates : bool, optional
            By default, dates are returned in seconds since EPOCH. If
            convert_dates is True, all ints in date columns will be converted
            to datetimes.

        Returns:
        -------
        dfs : dict{str->DataFrame}
            Dictionary which maps table name to the corresponding DataFrame
            version of the table, where all date columns have been coerced back
            from int to datetime.
        """
        return {
            t_name: self.get_df_from_table(t_name, convert_dates)
            for t_name in self._datetime_int_cols
        }

    def get_df_from_table(self, table_name, convert_dates=False):
        try:
            date_cols = self._datetime_int_cols[table_name]
        except KeyError as exc:
            raise ValueError(
                f"Requested table {table_name} not found.\n"
                f"Available tables: {self._datetime_int_cols.keys()}\n"
            ) from exc

        # Dates are stored in second resolution as ints in adj.db tables.
        kwargs = (
            # {"parse_dates": {col: {"unit": "s", "utc": True} for col in date_cols}}
            {"parse_dates": {col: {"unit": "s"} for col in date_cols}}
            if convert_dates
            else {}
        )

        # Table name is validated against _datetime_int_cols keys  # nosec B608
        result = pd.read_sql(
            f"select * from {table_name}",
            self.conn,
            index_col="index",
            **kwargs,
        )
        dtypes = self._df_dtypes(table_name, convert_dates)

        if not len(result):
            return empty_dataframe(*keysorted(dtypes))

        result.rename_axis(None, inplace=True)
        result = result[sorted(dtypes)]  # ensure expected order of columns
        return result

    def _df_dtypes(self, table_name, convert_dates):
        """Get dtypes to use when unpacking sqlite tables as dataframes."""
        out = self._raw_table_dtypes[table_name]
        if convert_dates:
            out = out.copy()
            for date_column in self._datetime_int_cols[table_name]:
                out[date_column] = datetime64ns_dtype

        return out


class SQLiteAdjustmentWriter:
    """Writer for data to be read by SQLiteAdjustmentReader

    Parameters
    ----------
    conn_or_path : str or sqlite3.Connection
        A handle to the target sqlite database.
    equity_daily_bar_reader : SessionBarReader
        Daily bar reader to use for dividend writes.
    overwrite : bool, optional, default=False
        If True and conn_or_path is a string, remove any existing files at the
        given path before connecting.

    See Also:
    --------
    zipline.data.adjustments.SQLiteAdjustmentReader
    """

    def __init__(self, conn_or_path, equity_daily_bar_reader, overwrite=False):
        if isinstance(conn_or_path, sqlite3.Connection):
            self.conn = conn_or_path
        elif isinstance(conn_or_path, str):
            if overwrite:
                try:
                    remove(conn_or_path)
                except OSError as e:
                    if e.errno != ENOENT:
                        raise
            self.conn = sqlite3.connect(conn_or_path)
            self.uri = conn_or_path
        else:
            raise TypeError("Unknown connection type %s" % type(conn_or_path))

        self._equity_daily_bar_reader = equity_daily_bar_reader

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        self.conn.close()

    def _write(self, tablename, expected_dtypes, frame):
        if frame is None or frame.empty:
            # keeping the dtypes correct for empty frames is not easy
            # frame = pd.DataFrame(
            #     np.array([], dtype=list(expected_dtypes.items())),
            # )
            frame = pd.DataFrame(expected_dtypes, index=[])
        else:
            if frozenset(frame.columns) != frozenset(expected_dtypes):
                raise ValueError(
                    "Unexpected frame columns:\n"
                    "Expected Columns: %s\n"
                    "Received Columns: %s"
                    % (
                        set(expected_dtypes),
                        frame.columns.tolist(),
                    )
                )

            actual_dtypes = frame.dtypes
            for colname, expected in expected_dtypes.items():
                actual = actual_dtypes[colname]
                if not np.issubdtype(actual, expected):
                    raise TypeError(
                        f"Expected data of type {expected} for column"
                        f" '{colname}', but got '{actual}'.",
                    )

        frame.to_sql(
            tablename,
            self.conn,
            if_exists="append",
            chunksize=50000,
        )

    def write_frame(self, tablename, frame):
        if tablename not in SQLITE_ADJUSTMENT_TABLENAMES:
            raise ValueError(f"Adjustment table {tablename} not in {SQLITE_ADJUSTMENT_TABLENAMES}")
        if not (frame is None or frame.empty):
            frame = frame.copy()
            frame["effective_date"] = (
                frame["effective_date"]
                .values.astype(
                    "datetime64[s]",
                )
                .astype("int64")
            )
        return self._write(
            tablename,
            SQLITE_ADJUSTMENT_COLUMN_DTYPES,
            frame,
        )

    def write_dividend_payouts(self, frame):
        """Write dividend payout data to SQLite table `dividend_payouts`."""
        return self._write(
            "dividend_payouts",
            SQLITE_DIVIDEND_PAYOUT_COLUMN_DTYPES,
            frame,
        )

    def write_stock_dividend_payouts(self, frame):
        return self._write(
            "stock_dividend_payouts",
            SQLITE_STOCK_DIVIDEND_PAYOUT_COLUMN_DTYPES,
            frame,
        )

    def calc_dividend_ratios(self, dividends):
        """Calculate the ratios to apply to equities when looking back at pricing
        history so that the price is smoothed over the ex_date, when the market
        adjusts to the change in equity value due to upcoming dividend.

        Returns:
        -------
        DataFrame
            A frame in the same format as splits and mergers, with keys
            - sid, the id of the equity
            - effective_date, the date in seconds on which to apply the ratio.
            - ratio, the ratio to apply to backwards looking pricing data.
        """
        if dividends is None or dividends.empty:
            return pd.DataFrame(
                np.array(
                    [],
                    dtype=[
                        ("sid", uint64_dtype),
                        ("effective_date", uint32_dtype),
                        ("ratio", float64_dtype),
                    ],
                )
            )

        pricing_reader = self._equity_daily_bar_reader
        input_sids = dividends.sid.values
        unique_sids, sids_ix = np.unique(input_sids, return_inverse=True)
        dates = pricing_reader.sessions.values

        (close,) = pricing_reader.load_raw_arrays(
            ["close"],
            pd.Timestamp(dates[0]),
            pd.Timestamp(dates[-1]),
            unique_sids,
        )
        date_ix = np.searchsorted(dates, dividends.ex_date.values)
        mask = date_ix > 0

        date_ix = date_ix[mask]
        sids_ix = sids_ix[mask]
        input_dates = dividends.ex_date.values[mask]

        # subtract one day to get the close on the day prior to the merger
        previous_close = close[date_ix - 1, sids_ix]
        input_sids = input_sids[mask]

        amount = dividends.amount.values[mask]
        ratio = 1.0 - amount / previous_close

        non_nan_ratio_mask = ~np.isnan(ratio)
        for ix in np.flatnonzero(~non_nan_ratio_mask):
            log.warning(
                "Couldn't compute ratio for dividend"
                " sid=%(sid)s, ex_date=%(ex_date)s, amount=%(amount).3f",
                {
                    "sid": input_sids[ix],
                    "ex_date": pd.Timestamp(input_dates[ix]).strftime("%Y-%m-%d"),
                    "amount": amount[ix],
                },
            )

        positive_ratio_mask = ratio > 0
        for ix in np.flatnonzero(~positive_ratio_mask & non_nan_ratio_mask):
            log.warning(
                "Dividend ratio <= 0 for dividend"
                " sid=%(sid)s, ex_date=%(ex_date)s, amount=%(amount).3f",
                {
                    "sid": input_sids[ix],
                    "ex_date": pd.Timestamp(input_dates[ix]).strftime("%Y-%m-%d"),
                    "amount": amount[ix],
                },
            )

        valid_ratio_mask = non_nan_ratio_mask & positive_ratio_mask
        return pd.DataFrame(
            {
                "sid": input_sids[valid_ratio_mask],
                "effective_date": input_dates[valid_ratio_mask],
                "ratio": ratio[valid_ratio_mask],
            }
        )

    def _write_dividends(self, dividends):
        if dividends is None:
            dividend_payouts = None
        else:
            dividend_payouts = dividends.copy()
            # TODO: Check if that's the right place for this fix for pandas > 1.2.5
            dividend_payouts.fillna(np.datetime64("NaT"), inplace=True)
            dividend_payouts["ex_date"] = (
                dividend_payouts["ex_date"].values.astype("datetime64[s]").astype(int64_dtype)
            )
            dividend_payouts["record_date"] = (
                dividend_payouts["record_date"].values.astype("datetime64[s]").astype(int64_dtype)
            )
            dividend_payouts["declared_date"] = (
                dividend_payouts["declared_date"].values.astype("datetime64[s]").astype(int64_dtype)
            )
            dividend_payouts["pay_date"] = (
                dividend_payouts["pay_date"].values.astype("datetime64[s]").astype(int64_dtype)
            )

        self.write_dividend_payouts(dividend_payouts)

    def _write_stock_dividends(self, stock_dividends):
        if stock_dividends is None:
            stock_dividend_payouts = None
        else:
            stock_dividend_payouts = stock_dividends.copy()
            stock_dividend_payouts["ex_date"] = (
                stock_dividend_payouts["ex_date"].values.astype("datetime64[s]").astype(int64_dtype)
            )
            stock_dividend_payouts["record_date"] = (
                stock_dividend_payouts["record_date"]
                .values.astype("datetime64[s]")
                .astype(int64_dtype)
            )
            stock_dividend_payouts["declared_date"] = (
                stock_dividend_payouts["declared_date"]
                .values.astype("datetime64[s]")
                .astype(int64_dtype)
            )
            stock_dividend_payouts["pay_date"] = (
                stock_dividend_payouts["pay_date"]
                .values.astype("datetime64[s]")
                .astype(int64_dtype)
            )
        self.write_stock_dividend_payouts(stock_dividend_payouts)

    def write_dividend_data(self, dividends, stock_dividends=None):
        """Write both dividend payouts and the derived price adjustment ratios."""
        # First write the dividend payouts.
        self._write_dividends(dividends)
        self._write_stock_dividends(stock_dividends)

        # Second from the dividend payouts, calculate ratios.
        dividend_ratios = self.calc_dividend_ratios(dividends)
        self.write_frame("dividends", dividend_ratios)

    def write(self, splits=None, mergers=None, dividends=None, stock_dividends=None):
        """Writes data to a SQLite file to be read by SQLiteAdjustmentReader.

        Parameters
        ----------
        splits : pandas.DataFrame, optional
            Dataframe containing split data. The format of this dataframe is:
              effective_date : int
                  The date, represented as seconds since Unix epoch, on which
                  the adjustment should be applied.
              ratio : float
                  A value to apply to all data earlier than the effective date.
                  For open, high, low, and close those values are multiplied by
                  the ratio. Volume is divided by this value.
              sid : int
                  The asset id associated with this adjustment.
        mergers : pandas.DataFrame, optional
            DataFrame containing merger data. The format of this dataframe is:
              effective_date : int
                  The date, represented as seconds since Unix epoch, on which
                  the adjustment should be applied.
              ratio : float
                  A value to apply to all data earlier than the effective date.
                  For open, high, low, and close those values are multiplied by
                  the ratio. Volume is unaffected.
              sid : int
                  The asset id associated with this adjustment.
        dividends : pandas.DataFrame, optional
            DataFrame containing dividend data. The format of the dataframe is:
              sid : int
                  The asset id associated with this adjustment.
              ex_date : datetime64
                  The date on which an equity must be held to be eligible to
                  receive payment.
              declared_date : datetime64
                  The date on which the dividend is announced to the public.
              pay_date : datetime64
                  The date on which the dividend is distributed.
              record_date : datetime64
                  The date on which the stock ownership is checked to determine
                  distribution of dividends.
              amount : float
                  The cash amount paid for each share.

            Dividend ratios are calculated as:
            ``1.0 - (dividend_value / "close on day prior to ex_date")``
        stock_dividends : pandas.DataFrame, optional
            DataFrame containing stock dividend data. The format of the
            dataframe is:
              sid : int
                  The asset id associated with this adjustment.
              ex_date : datetime64
                  The date on which an equity must be held to be eligible to
                  receive payment.
              declared_date : datetime64
                  The date on which the dividend is announced to the public.
              pay_date : datetime64
                  The date on which the dividend is distributed.
              record_date : datetime64
                  The date on which the stock ownership is checked to determine
                  distribution of dividends.
              payment_sid : int
                  The asset id of the shares that should be paid instead of
                  cash.
              ratio : float
                  The ratio of currently held shares in the held sid that
                  should be paid with new shares of the payment_sid.

        See Also:
        --------
        zipline.data.adjustments.SQLiteAdjustmentReader
        """
        self.write_frame("splits", splits)
        self.write_frame("mergers", mergers)
        self.write_dividend_data(dividends, stock_dividends)
        # Use IF NOT EXISTS here to allow multiple writes if desired.
        self.conn.execute("CREATE INDEX IF NOT EXISTS splits_sids ON splits(sid)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS splits_effective_date ON splits(effective_date)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS mergers_sids ON mergers(sid)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS mergers_effective_date ON mergers(effective_date)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS dividends_sid ON dividends(sid)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS dividends_effective_date ON dividends(effective_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS dividend_payouts_sid ON dividend_payouts(sid)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS dividends_payouts_ex_date ON dividend_payouts(ex_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS stock_dividend_payouts_sid ON stock_dividend_payouts(sid)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS stock_dividends_payouts_ex_date "
            "ON stock_dividend_payouts(ex_date)"
        )
