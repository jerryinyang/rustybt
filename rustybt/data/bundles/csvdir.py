"""
Module for building a complete dataset from local directory with csv files.
"""

import logging
import os

import numpy as np
import pandas as pd
import polars as pl

from rustybt.data.polars.validation import validate_ohlcv_relationships
from rustybt.finance.decimal.config import DecimalConfig
from rustybt.utils.calendar_utils import register_calendar_alias
from rustybt.utils.cli import maybe_show_progress

from ..metadata_tracker import track_csv_bundle_metadata
from . import core as bundles

handler = logging.StreamHandler()
# handler = logging.StreamHandler(sys.stdout, format_string=" | {record.message}")
logger = logging.getLogger(__name__)
logger.handlers.append(handler)


def csvdir_equities(tframes=None, csvdir=None):
    """
    Generate an ingest function for custom data bundle
    This function can be used in ~/.zipline/extension.py
    to register bundle with custom parameters, e.g. with
    a custom trading calendar.

    Parameters
    ----------
    tframes: tuple, optional
        The data time frames, supported timeframes: 'daily' and 'minute'
    csvdir : string, optional, default: CSVDIR environment variable
        The path to the directory of this structure:
        <directory>/<timeframe1>/<symbol1>.csv
        <directory>/<timeframe1>/<symbol2>.csv
        <directory>/<timeframe1>/<symbol3>.csv
        <directory>/<timeframe2>/<symbol1>.csv
        <directory>/<timeframe2>/<symbol2>.csv
        <directory>/<timeframe2>/<symbol3>.csv

    Returns:
    -------
    ingest : callable
        The bundle ingest function

    Examples:
    --------
    This code should be added to ~/.zipline/extension.py
    .. code-block:: python
       from rustybt.data.bundles import csvdir_equities, register
       register('custom-csvdir-bundle',
                csvdir_equities(["daily", "minute"],
                '/full/path/to/the/csvdir/directory'))
    """
    return CSVDIRBundle(tframes, csvdir).ingest


class CSVDIRBundle:
    """
    Wrapper class to call csvdir_bundle with provided
    list of time frames and a path to the csvdir directory
    """

    def __init__(self, tframes=None, csvdir=None):
        self.tframes = tframes
        self.csvdir = csvdir

    def ingest(
        self,
        environ,
        asset_db_writer,
        minute_bar_writer,
        daily_bar_writer,
        adjustment_writer,
        calendar,
        start_session,
        end_session,
        cache,
        show_progress,
        output_dir,
    ):
        csvdir_bundle(
            environ,
            asset_db_writer,
            minute_bar_writer,
            daily_bar_writer,
            adjustment_writer,
            calendar,
            start_session,
            end_session,
            cache,
            show_progress,
            output_dir,
            self.tframes,
            self.csvdir,
        )


@bundles.register("csvdir")
def csvdir_bundle(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
    tframes=None,
    csvdir=None,
):
    """
    Build a zipline data bundle from the directory with csv files.
    """
    if not csvdir:
        csvdir = environ.get("CSVDIR")
        if not csvdir:
            raise ValueError("CSVDIR environment variable is not set")

    if not os.path.isdir(csvdir):
        raise ValueError("%s is not a directory" % csvdir)

    if not tframes:
        tframes = set(["daily", "minute"]).intersection(os.listdir(csvdir))

        if not tframes:
            raise ValueError("'daily' and 'minute' directories not found in '%s'" % csvdir)

    divs_splits = {
        "divs": pd.DataFrame(
            columns=[
                "sid",
                "amount",
                "ex_date",
                "record_date",
                "declared_date",
                "pay_date",
            ]
        ),
        "splits": pd.DataFrame(columns=["sid", "ratio", "effective_date"]),
    }
    for tframe in tframes:
        ddir = os.path.join(csvdir, tframe)

        symbols = sorted(item.split(".csv")[0] for item in os.listdir(ddir) if ".csv" in item)
        if not symbols:
            raise ValueError("no <symbol>.csv* files found in %s" % ddir)

        dtype = [
            ("start_date", "datetime64[ns]"),
            ("end_date", "datetime64[ns]"),
            ("auto_close_date", "datetime64[ns]"),
            ("symbol", "object"),
        ]
        metadata = pd.DataFrame(np.empty(len(symbols), dtype=dtype))

        if tframe == "minute":
            writer = minute_bar_writer
        else:
            writer = daily_bar_writer

        writer.write(
            _pricing_iter(ddir, symbols, metadata, divs_splits, show_progress),
            show_progress=show_progress,
        )

        # Hardcode the exchange to "CSVDIR" for all assets and (elsewhere)
        # register "CSVDIR" to resolve to the NYSE calendar, because these
        # are all equities and thus can use the NYSE calendar.
        metadata["exchange"] = "CSVDIR"

        asset_db_writer.write(equities=metadata)

        divs_splits["divs"]["sid"] = divs_splits["divs"]["sid"].astype(int)
        divs_splits["splits"]["sid"] = divs_splits["splits"]["sid"].astype(int)
        adjustment_writer.write(splits=divs_splits["splits"], dividends=divs_splits["divs"])

    # Record bundle metadata and quality metrics
    try:
        # Get bundle name from output_dir path
        bundle_name = os.path.basename(os.path.dirname(output_dir))

        # Attempt to load and combine all data for quality analysis
        # This is optional - if it fails, metadata will still be recorded without quality metrics
        all_data = None
        try:
            if "daily" in tframes:
                daily_dir = os.path.join(csvdir, "daily")
                daily_files = [
                    os.path.join(daily_dir, f) for f in os.listdir(daily_dir) if f.endswith(".csv")
                ]
                # Load first file as sample for quality analysis
                if daily_files:
                    sample_df = pd.read_csv(
                        daily_files[0], parse_dates=[0], index_col=0
                    ).sort_index()
                    # Convert to Polars for quality analysis
                    sample_df = sample_df.reset_index()
                    sample_df.columns = ["date"] + list(sample_df.columns[1:])
                    all_data = pl.from_pandas(sample_df)
        except Exception as e:
            logger.debug(f"Could not load data for quality analysis: {e}")

        # Track metadata
        track_csv_bundle_metadata(
            bundle_name=bundle_name,
            csv_dir=csvdir,
            data=all_data,
            calendar=calendar,
        )
        logger.info(f"Bundle metadata recorded for {bundle_name}")
    except Exception as e:
        # Don't fail ingestion if metadata tracking fails
        logger.warning(f"Failed to record bundle metadata: {e}")


def convert_csv_to_decimal_parquet(
    csv_path: str,
    parquet_path: str,
    asset_class: str = "equity",
    frequency: str = "daily",
    config: DecimalConfig | None = None,
) -> dict:
    """Convert CSV data to Parquet with Decimal precision.

    Args:
        csv_path: Path to input CSV file
        parquet_path: Path to output Parquet file
        asset_class: Asset class for precision config ("equity", "crypto", etc.)
        frequency: Data frequency ("daily" or "minute")
        config: Optional DecimalConfig instance (uses singleton if None)

    Returns:
        Dictionary with ingestion summary:
            - rows_ingested: Number of rows successfully ingested
            - precision_warnings: List of precision warning messages
            - errors: List of error messages

    Raises:
        FileNotFoundError: If CSV file not found
        ValueError: If OHLCV relationships invalid or data format incorrect
    """
    config = config or DecimalConfig.get_instance()
    precision = config.get_precision(asset_class)
    scale = config.get_scale(asset_class)

    summary = {"rows_ingested": 0, "precision_warnings": [], "errors": []}

    # Read CSV as string columns first to avoid float contamination
    try:
        df = pl.read_csv(
            csv_path,
            dtypes={
                "open": pl.Utf8,
                "high": pl.Utf8,
                "low": pl.Utf8,
                "close": pl.Utf8,
                "volume": pl.Utf8,
            },
        )
    except Exception as e:
        raise FileNotFoundError(f"Failed to read CSV file {csv_path}: {e}")

    # Convert date/timestamp column based on frequency
    try:
        if frequency == "daily":
            # Infer date column name
            date_col = None
            for col in df.columns:
                if col.lower() in ["date", "day", "timestamp", "time"]:
                    date_col = col
                    break

            if date_col is None:
                raise ValueError("No date column found in CSV")

            df = df.with_columns(
                [pl.col(date_col).str.strptime(pl.Date, "%Y-%m-%d", strict=False).alias("date")]
            )

            # Drop original date column if it had a different name
            if date_col != "date":
                df = df.drop(date_col)
        else:  # minute
            # Infer timestamp column
            ts_col = None
            for col in df.columns:
                if col.lower() in ["timestamp", "time", "datetime", "date"]:
                    ts_col = col
                    break

            if ts_col is None:
                raise ValueError("No timestamp column found in CSV")

            df = df.with_columns(
                [
                    pl.col(ts_col)
                    .str.strptime(pl.Datetime("us"), "%Y-%m-%d %H:%M:%S", strict=False)
                    .alias("timestamp")
                ]
            )

            # Drop original timestamp column if it had a different name
            if ts_col != "timestamp":
                df = df.drop(ts_col)
    except Exception as e:
        raise ValueError(f"Failed to parse date/timestamp column: {e}")

    # Detect scientific notation and reject it
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            scientific_notation = df.filter(pl.col(col).str.contains("[eE]"))
            if len(scientific_notation) > 0:
                summary["errors"].append(
                    f"Scientific notation detected in '{col}' column. "
                    f"Please convert to decimal format before ingestion."
                )

    if summary["errors"]:
        raise ValueError(f"Data validation errors: {summary['errors']}")

    # Convert price columns to Decimal with configured precision
    decimal_dtype = pl.Decimal(precision=precision, scale=scale)

    try:
        df = df.with_columns(
            [
                pl.col("open").cast(decimal_dtype),
                pl.col("high").cast(decimal_dtype),
                pl.col("low").cast(decimal_dtype),
                pl.col("close").cast(decimal_dtype),
                pl.col("volume").cast(decimal_dtype),
            ]
        )
    except Exception as e:
        raise ValueError(f"Failed to convert prices to Decimal: {e}")

    # Validate prices are non-negative
    for col in ["open", "high", "low", "close", "volume"]:
        negative_values = df.filter(pl.col(col) < 0)
        if len(negative_values) > 0:
            raise ValueError(
                f"Negative values detected in '{col}' column. Prices must be non-negative."
            )

    # Validate OHLCV relationships
    validate_ohlcv_relationships(df)

    # Write to Parquet with Snappy compression
    df.write_parquet(parquet_path, compression="snappy")

    summary["rows_ingested"] = len(df)
    logger.info(
        f"Converted {csv_path} to Parquet: {summary['rows_ingested']} rows, "
        f"precision={precision}, scale={scale}, asset_class={asset_class}"
    )

    return summary


def _pricing_iter(csvdir, symbols, metadata, divs_splits, show_progress):
    with maybe_show_progress(symbols, show_progress, label="Loading custom pricing data: ") as it:
        # using scandir instead of listdir can be faster
        files = os.scandir(csvdir)
        # building a dictionary of filenames
        # NOTE: if there are duplicates it will arbitrarily pick the latest found
        fnames = {f.name.split(".")[0]: f.name for f in files if f.is_file()}

        for sid, symbol in enumerate(it):
            logger.debug(f"{symbol}: sid {sid}")
            fname = fnames.get(symbol)

            if fname is None:
                raise ValueError(f"{symbol}.csv file is not in {csvdir}")

            # NOTE: read_csv can also read compressed csv files
            dfr = pd.read_csv(
                os.path.join(csvdir, fname),
                parse_dates=[0],
                index_col=0,
            ).sort_index()

            start_date = dfr.index[0]
            end_date = dfr.index[-1]

            # The auto_close date is the day after the last trade.
            ac_date = end_date + pd.Timedelta(days=1)
            metadata.iloc[sid] = start_date, end_date, ac_date, symbol

            if "split" in dfr.columns:
                tmp = 1.0 / dfr[dfr["split"] != 1.0]["split"]
                split = pd.DataFrame(data=tmp.index.tolist(), columns=["effective_date"])
                split["ratio"] = tmp.tolist()
                split["sid"] = sid

                splits = divs_splits["splits"]
                index = pd.Index(range(splits.shape[0], splits.shape[0] + split.shape[0]))
                split.set_index(index, inplace=True)
                divs_splits["splits"] = pd.concat([splits, split], axis=0)

            if "dividend" in dfr.columns:
                # ex_date   amount  sid record_date declared_date pay_date
                tmp = dfr[dfr["dividend"] != 0.0]["dividend"]
                div = pd.DataFrame(data=tmp.index.tolist(), columns=["ex_date"])
                div["record_date"] = pd.NaT
                div["declared_date"] = pd.NaT
                div["pay_date"] = pd.NaT
                div["amount"] = tmp.tolist()
                div["sid"] = sid

                divs = divs_splits["divs"]
                ind = pd.Index(range(divs.shape[0], divs.shape[0] + div.shape[0]))
                div.set_index(ind, inplace=True)
                divs_splits["divs"] = pd.concat([divs, div], axis=0)

            yield sid, dfr


register_calendar_alias("CSVDIR", "NYSE")
