"""Parquet-based adjustment reader and writer for corporate actions.

This module provides efficient storage and retrieval of corporate actions
(splits, dividends, mergers) using SQLite tables in metadata.db.
"""

import sqlite3
from collections import namedtuple
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

from rustybt.data._adjustments import load_adjustments_from_sqlite
from rustybt.data.adjustments import (
    SQLITE_ADJUSTMENT_COLUMN_DTYPES,
    SQLITE_DIVIDEND_PAYOUT_COLUMN_DTYPES,
    SQLITE_STOCK_DIVIDEND_PAYOUT_COLUMN_DTYPES,
    Dividend,
    StockDividend,
)
from rustybt.utils.sqlite_utils import group_into_chunks

logger = structlog.get_logger(__name__)

# SQL schema for adjustment tables in metadata.db
ADJUSTMENT_TABLES_SCHEMA = """
-- Splits table
CREATE TABLE IF NOT EXISTS splits (
    sid INTEGER NOT NULL,
    effective_date INTEGER NOT NULL,
    ratio REAL NOT NULL,
    PRIMARY KEY (sid, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_splits_sid ON splits(sid);
CREATE INDEX IF NOT EXISTS idx_splits_effective_date ON splits(effective_date);

-- Dividends table
CREATE TABLE IF NOT EXISTS dividends (
    sid INTEGER NOT NULL,
    effective_date INTEGER NOT NULL,
    ratio REAL NOT NULL,
    PRIMARY KEY (sid, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_dividends_sid ON dividends(sid);
CREATE INDEX IF NOT EXISTS idx_dividends_effective_date ON dividends(effective_date);

-- Mergers table
CREATE TABLE IF NOT EXISTS mergers (
    sid INTEGER NOT NULL,
    effective_date INTEGER NOT NULL,
    ratio REAL NOT NULL,
    PRIMARY KEY (sid, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_mergers_sid ON mergers(sid);
CREATE INDEX IF NOT EXISTS idx_mergers_effective_date ON mergers(effective_date);

-- Dividend payouts table
CREATE TABLE IF NOT EXISTS dividend_payouts (
    sid INTEGER NOT NULL,
    ex_date INTEGER NOT NULL,
    declared_date INTEGER,
    record_date INTEGER,
    pay_date INTEGER NOT NULL,
    amount REAL NOT NULL,
    PRIMARY KEY (sid, ex_date)
);

CREATE INDEX IF NOT EXISTS idx_dividend_payouts_sid ON dividend_payouts(sid);
CREATE INDEX IF NOT EXISTS idx_dividend_payouts_ex_date ON dividend_payouts(ex_date);
CREATE INDEX IF NOT EXISTS idx_dividend_payouts_pay_date ON dividend_payouts(pay_date);

-- Stock dividend payouts table
CREATE TABLE IF NOT EXISTS stock_dividend_payouts (
    sid INTEGER NOT NULL,
    ex_date INTEGER NOT NULL,
    declared_date INTEGER,
    record_date INTEGER,
    pay_date INTEGER NOT NULL,
    payment_sid INTEGER NOT NULL,
    ratio REAL NOT NULL,
    PRIMARY KEY (sid, ex_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_dividend_payouts_sid ON stock_dividend_payouts(sid);
CREATE INDEX IF NOT EXISTS idx_stock_dividend_payouts_ex_date ON stock_dividend_payouts(ex_date);
CREATE INDEX IF NOT EXISTS idx_stock_dividend_payouts_pay_date ON stock_dividend_payouts(pay_date);
"""

UNPAID_QUERY_TEMPLATE = """
SELECT sid, amount, pay_date from dividend_payouts
WHERE ex_date=? AND sid IN ({0})
"""

UNPAID_STOCK_DIVIDEND_QUERY_TEMPLATE = """
SELECT sid, payment_sid, ratio, pay_date from stock_dividend_payouts
WHERE ex_date=? AND sid IN ({0})
"""


class ParquetAdjustmentReader:
    """Loads adjustments from Parquet bundle metadata.db.

    This reader is compatible with SQLiteAdjustmentReader but reads from
    the unified metadata.db file in Parquet bundles.

    Parameters
    ----------
    bundle_path : str
        Path to Parquet bundle directory

    Example
    -------
    >>> reader = ParquetAdjustmentReader("~/.zipline/data/bundles/mag-7")
    >>> adjustments = reader.load_adjustments(dates, assets, True, True, True, "all")
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

    def __init__(self, bundle_path: str):
        """Initialize reader with bundle path.

        Args:
            bundle_path: Path to bundle directory
        """
        self.bundle_path = Path(bundle_path).expanduser()
        self.metadata_db = self.bundle_path / "metadata.db"

        if not self.metadata_db.exists():
            raise FileNotFoundError(f"Metadata database not found: {self.metadata_db}")

        self.conn = sqlite3.connect(str(self.metadata_db))

        # Ensure adjustment tables exist
        self._ensure_tables()

        logger.info(
            "parquet_adjustment_reader_initialized",
            bundle_path=str(bundle_path),
            metadata_db=str(self.metadata_db),
        )

    def _ensure_tables(self):
        """Ensure adjustment tables exist in metadata.db."""
        cursor = self.conn.cursor()
        cursor.executescript(ADJUSTMENT_TABLES_SCHEMA)
        self.conn.commit()
        cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def load_adjustments(
        self,
        dates,
        assets,
        should_include_splits,
        should_include_mergers,
        should_include_dividends,
        adjustment_type,
    ):
        """Load collection of Adjustment objects from adjustments db.

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

        Returns
        -------
        adjustments : dict[str -> dict[int -> Adjustment]]
            A dictionary containing price and/or volume adjustment mappings
            from index to adjustment objects to apply at that index.
        """
        dates = dates.tz_localize("UTC") if dates.tz is None else dates
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
        """Load pricing adjustments for specified columns.

        Parameters
        ----------
        columns : list[str]
            Columns for which adjustments are needed
        dates : pd.DatetimeIndex
            Dates for which adjustments are needed
        assets : pd.Int64Index
            Assets for which adjustments are needed

        Returns
        -------
        list[dict]
            List of adjustment dictionaries, one per column
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
        """Get all adjustments for a specific asset.

        Parameters
        ----------
        table_name : str
            Name of adjustment table ('splits', 'dividends', or 'mergers')
        sid : int
            Asset ID

        Returns
        -------
        list[list]
            List of [effective_date, ratio] pairs
        """
        valid_tables = {"splits", "dividends", "mergers"}
        if table_name not in valid_tables:
            raise ValueError(f"Invalid table name: {table_name}. Must be one of {valid_tables}")

        cursor = self.conn.cursor()
        # Table name is validated against whitelist, safe to use
        query = f"SELECT effective_date, ratio FROM {table_name} WHERE sid = ?"  # nosec B608
        adjustments_for_sid = cursor.execute(query, (sid,)).fetchall()
        cursor.close()

        return [
            [pd.Timestamp(adjustment[0], unit="s"), adjustment[1]]
            for adjustment in adjustments_for_sid
        ]

    def get_dividends_with_ex_date(self, assets, date, asset_finder):
        """Get dividends with ex-date on specified date.

        Parameters
        ----------
        assets : list[int]
            Asset IDs
        date : pd.Timestamp
            Ex-date to query
        asset_finder : AssetFinder
            Asset finder for resolving assets

        Returns
        -------
        list[Dividend]
            List of Dividend namedtuples
        """
        seconds = date.value / int(1e9)
        cursor = self.conn.cursor()

        divs = []
        for chunk in group_into_chunks(assets):
            query = UNPAID_QUERY_TEMPLATE.format(",".join(["?" for _ in chunk]))
            params = (seconds,) + tuple(map(int, chunk))

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                div = Dividend(
                    asset_finder.retrieve_asset(row[0]),
                    row[1],
                    pd.Timestamp(row[2], unit="s", tz="UTC"),
                )
                divs.append(div)

        cursor.close()
        return divs

    def get_stock_dividends_with_ex_date(self, assets, date, asset_finder):
        """Get stock dividends with ex-date on specified date.

        Parameters
        ----------
        assets : list[int]
            Asset IDs
        date : pd.Timestamp
            Ex-date to query
        asset_finder : AssetFinder
            Asset finder for resolving assets

        Returns
        -------
        list[StockDividend]
            List of StockDividend namedtuples
        """
        seconds = date.value / int(1e9)
        cursor = self.conn.cursor()

        stock_divs = []
        for chunk in group_into_chunks(assets):
            query = UNPAID_STOCK_DIVIDEND_QUERY_TEMPLATE.format(",".join(["?" for _ in chunk]))
            params = (seconds,) + tuple(map(int, chunk))

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                stock_div = StockDividend(
                    asset_finder.retrieve_asset(row[0]),  # asset
                    asset_finder.retrieve_asset(row[1]),  # payment_asset
                    row[2],  # ratio
                    pd.Timestamp(row[3], unit="s", tz="UTC"),  # pay_date
                )
                stock_divs.append(stock_div)

        cursor.close()
        return stock_divs


class ParquetAdjustmentWriter:
    """Writer for adjustment data in Parquet bundle metadata.db.

    This writer is compatible with SQLiteAdjustmentWriter but writes to
    the unified metadata.db file in Parquet bundles.

    Parameters
    ----------
    bundle_path : str
        Path to Parquet bundle directory

    Example
    -------
    >>> writer = ParquetAdjustmentWriter("~/.zipline/data/bundles/mag-7")
    >>> writer.write_splits(splits_df)
    >>> writer.write_dividends(dividends_df)
    """

    def __init__(self, bundle_path: str):
        """Initialize writer with bundle path.

        Args:
            bundle_path: Path to bundle directory
        """
        self.bundle_path = Path(bundle_path).expanduser()
        self.metadata_db = self.bundle_path / "metadata.db"

        self.conn = sqlite3.connect(str(self.metadata_db))

        # Ensure adjustment tables exist
        cursor = self.conn.cursor()
        cursor.executescript(ADJUSTMENT_TABLES_SCHEMA)
        self.conn.commit()
        cursor.close()

        logger.info(
            "parquet_adjustment_writer_initialized",
            bundle_path=str(bundle_path),
            metadata_db=str(self.metadata_db),
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def write_splits(self, splits_df):
        """Write splits data.

        Parameters
        ----------
        splits_df : pd.DataFrame
            DataFrame with columns: sid, effective_date, ratio
        """
        if splits_df is None or len(splits_df) == 0:
            return

        # Convert dates to Unix timestamps
        df = splits_df.copy()
        if "effective_date" in df.columns:
            df["effective_date"] = pd.to_datetime(df["effective_date"]).astype(np.int64) // 10**9

        df.to_sql("splits", self.conn, if_exists="append", index=False)
        logger.info("splits_written", count=len(df))

    def write_dividends(self, dividends_df):
        """Write dividends data.

        Parameters
        ----------
        dividends_df : pd.DataFrame
            DataFrame with columns: sid, effective_date, ratio
        """
        if dividends_df is None or len(dividends_df) == 0:
            return

        # Convert dates to Unix timestamps
        df = dividends_df.copy()
        if "effective_date" in df.columns:
            df["effective_date"] = pd.to_datetime(df["effective_date"]).astype(np.int64) // 10**9

        df.to_sql("dividends", self.conn, if_exists="append", index=False)
        logger.info("dividends_written", count=len(df))

    def write_mergers(self, mergers_df):
        """Write mergers data.

        Parameters
        ----------
        mergers_df : pd.DataFrame
            DataFrame with columns: sid, effective_date, ratio
        """
        if mergers_df is None or len(mergers_df) == 0:
            return

        # Convert dates to Unix timestamps
        df = mergers_df.copy()
        if "effective_date" in df.columns:
            df["effective_date"] = pd.to_datetime(df["effective_date"]).astype(np.int64) // 10**9

        df.to_sql("mergers", self.conn, if_exists="append", index=False)
        logger.info("mergers_written", count=len(df))

    def write_dividend_payouts(self, dividend_payouts_df):
        """Write dividend payouts data.

        Parameters
        ----------
        dividend_payouts_df : pd.DataFrame
            DataFrame with columns: sid, ex_date, declared_date, record_date,
            pay_date, amount
        """
        if dividend_payouts_df is None or len(dividend_payouts_df) == 0:
            return

        # Convert dates to Unix timestamps
        df = dividend_payouts_df.copy()
        date_cols = ["ex_date", "declared_date", "record_date", "pay_date"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).astype(np.int64) // 10**9

        df.to_sql("dividend_payouts", self.conn, if_exists="append", index=False)
        logger.info("dividend_payouts_written", count=len(df))

    def write_stock_dividend_payouts(self, stock_dividend_payouts_df):
        """Write stock dividend payouts data.

        Parameters
        ----------
        stock_dividend_payouts_df : pd.DataFrame
            DataFrame with columns: sid, ex_date, declared_date, record_date,
            pay_date, payment_sid, ratio
        """
        if stock_dividend_payouts_df is None or len(stock_dividend_payouts_df) == 0:
            return

        # Convert dates to Unix timestamps
        df = stock_dividend_payouts_df.copy()
        date_cols = ["ex_date", "declared_date", "record_date", "pay_date"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).astype(np.int64) // 10**9

        df.to_sql("stock_dividend_payouts", self.conn, if_exists="append", index=False)
        logger.info("stock_dividend_payouts_written", count=len(df))

    def write(
        self,
        splits=None,
        mergers=None,
        dividends=None,
        dividend_payouts=None,
        stock_dividend_payouts=None,
    ):
        """Write all adjustment data.

        Parameters
        ----------
        splits : pd.DataFrame, optional
            Splits data
        mergers : pd.DataFrame, optional
            Mergers data
        dividends : pd.DataFrame, optional
            Dividends data
        dividend_payouts : pd.DataFrame, optional
            Dividend payouts data
        stock_dividend_payouts : pd.DataFrame, optional
            Stock dividend payouts data
        """
        if splits is not None:
            self.write_splits(splits)
        if mergers is not None:
            self.write_mergers(mergers)
        if dividends is not None:
            self.write_dividends(dividends)
        if dividend_payouts is not None:
            self.write_dividend_payouts(dividend_payouts)
        if stock_dividend_payouts is not None:
            self.write_stock_dividend_payouts(stock_dividend_payouts)

        self.conn.commit()
