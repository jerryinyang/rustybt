import errno
import os
from datetime import datetime, timezone
from importlib import util as importlib_util
from pathlib import Path

import click
import logging
import pandas as pd

from rich.console import Console
from rich.table import Table

import rustybt
from rustybt.data import bundles as bundles_module
from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.utils.calendar_utils import get_calendar
from rustybt.utils.compat import wraps
from rustybt.utils.cli import Date, Timestamp
from rustybt.utils.run_algo import _run, BenchmarkSpec, load_extensions
from rustybt.extensions import create_args
from rustybt.utils.paths import zipline_root

try:
    __IPYTHON__
except NameError:
    __IPYTHON__ = False


@click.group()
@click.option(
    "-e",
    "--extension",
    multiple=True,
    help="File or module path to a zipline extension to load.",
)
@click.option(
    "--strict-extensions/--non-strict-extensions",
    is_flag=True,
    help="If --strict-extensions is passed then zipline will not "
    "run if it cannot load all of the specified extensions. "
    "If this is not passed or --non-strict-extensions is passed "
    "then the failure will be logged but execution will continue.",
)
@click.option(
    "--default-extension/--no-default-extension",
    is_flag=True,
    default=True,
    help="Don't load the default zipline extension.py file in $ZIPLINE_HOME.",
)
@click.option(
    "-x",
    multiple=True,
    help="Any custom command line arguments to define, in key=value form.",
)
@click.pass_context
def main(ctx, extension, strict_extensions, default_extension, x):
    """Top level zipline entry point."""
    # install a logging handler before performing any other operations

    logging.basicConfig(
        format="[%(asctime)s-%(levelname)s][%(name)s]\n %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    create_args(x, rustybt.extension_args)
    load_extensions(
        default_extension,
        extension,
        strict_extensions,
        os.environ,
    )


def extract_option_object(option):
    """Convert a click.option call into a click.Option object.

    Parameters
    ----------
    option : decorator
        A click.option decorator.

    Returns
    -------
    option_object : click.Option
        The option object that this decorator will create.
    """

    @option
    def opt():
        pass

    return opt.__click_params__[0]


def ipython_only(option):
    """Mark that an option should only be exposed in IPython.

    Parameters
    ----------
    option : decorator
        A click.option decorator.

    Returns
    -------
    ipython_only_dec : decorator
        A decorator that correctly applies the argument even when not
        using IPython mode.
    """
    if __IPYTHON__:
        return option

    argname = extract_option_object(option).name

    def d(f):
        @wraps(f)
        def _(*args, **kwargs):
            kwargs[argname] = None
            return f(*args, **kwargs)

        return _

    return d


DEFAULT_BUNDLE = "quandl"


def _format_timestamp(ts: int | None) -> str:
    if ts is None:
        return "—"
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    except (OSError, OverflowError, ValueError):
        return str(ts)


def _format_date(ts: int | None) -> str:
    if ts is None:
        return "—"
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    except (OSError, OverflowError, ValueError):
        return str(ts)


def _format_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "—"
    size = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


_migration_module = None


def _load_migration_module():
    global _migration_module
    if _migration_module is not None:
        return _migration_module

    script_path = Path(__file__).resolve().parent.parent / "scripts" / "migrate_catalog_to_unified.py"
    spec = importlib_util.spec_from_file_location("rustybt_cli_migration", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Migration script not found at {script_path}")
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _migration_module = module
    return module


@main.command()
@click.option(
    "-f",
    "--algofile",
    default=None,
    type=click.File("r"),
    help="The file that contains the algorithm to run.",
)
@click.option(
    "-t",
    "--algotext",
    help="The algorithm script to run.",
)
@click.option(
    "-D",
    "--define",
    multiple=True,
    help="Define a name to be bound in the namespace before executing"
    " the algotext. For example '-Dname=value'. The value may be any "
    "python expression. These are evaluated in order so they may refer "
    "to previously defined names.",
)
@click.option(
    "--data-frequency",
    type=click.Choice({"daily", "minute"}),
    default="daily",
    show_default=True,
    help="The data frequency of the simulation.",
)
@click.option(
    "--capital-base",
    type=float,
    default=10e6,
    show_default=True,
    help="The starting capital for the simulation.",
)
@click.option(
    "-b",
    "--bundle",
    default=DEFAULT_BUNDLE,
    metavar="BUNDLE-NAME",
    show_default=True,
    help="The data bundle to use for the simulation.",
)
@click.option(
    "--bundle-timestamp",
    type=Timestamp(),
    default=pd.Timestamp.utcnow(),
    show_default=False,
    help="The date to lookup data on or before.\n" "[default: <current-time>]",
)
@click.option(
    "-bf",
    "--benchmark-file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=str),
    help="The csv file that contains the benchmark returns",
)
@click.option(
    "--benchmark-symbol",
    default=None,
    type=click.STRING,
    help="The symbol of the instrument to be used as a benchmark "
    "(should exist in the ingested bundle)",
)
@click.option(
    "--benchmark-sid",
    default=None,
    type=int,
    help="The sid of the instrument to be used as a benchmark "
    "(should exist in the ingested bundle)",
)
@click.option(
    "--no-benchmark",
    is_flag=True,
    default=False,
    help="If passed, use a benchmark of zero returns.",
)
@click.option(
    "-s",
    "--start",
    type=Date(as_timestamp=True),
    help="The start date of the simulation.",
)
@click.option(
    "-e",
    "--end",
    type=Date(as_timestamp=True),
    help="The end date of the simulation.",
)
@click.option(
    "-o",
    "--output",
    default="-",
    metavar="FILENAME",
    show_default=True,
    help="The location to write the perf data. If this is '-' the perf will"
    " be written to stdout.",
)
@click.option(
    "--trading-calendar",
    metavar="TRADING-CALENDAR",
    default="XNYS",
    help="The calendar you want to use e.g. XLON. XNYS is the default.",
)
@click.option(
    "--print-algo/--no-print-algo",
    is_flag=True,
    default=False,
    help="Print the algorithm to stdout.",
)
@click.option(
    "--metrics-set",
    default="default",
    help="The metrics set to use. New metrics sets may be registered in your"
    " extension.py.",
)
@click.option(
    "--blotter",
    default="default",
    help="The blotter to use.",
    show_default=True,
)
@ipython_only(
    click.option(
        "--local-namespace/--no-local-namespace",
        is_flag=True,
        default=None,
        help="Should the algorithm methods be " "resolved in the local namespace.",
    )
)
@click.pass_context
def run(
    ctx,
    algofile,
    algotext,
    define,
    data_frequency,
    capital_base,
    bundle,
    bundle_timestamp,
    benchmark_file,
    benchmark_symbol,
    benchmark_sid,
    no_benchmark,
    start,
    end,
    output,
    trading_calendar,
    print_algo,
    metrics_set,
    local_namespace,
    blotter,
):
    """Run a backtest for the given algorithm."""
    # check that the start and end dates are passed correctly
    if start is None and end is None:
        # check both at the same time to avoid the case where a user
        # does not pass either of these and then passes the first only
        # to be told they need to pass the second argument also
        ctx.fail(
            "must specify dates with '-s' / '--start' and '-e' / '--end'",
        )
    if start is None:
        ctx.fail("must specify a start date with '-s' / '--start'")
    if end is None:
        ctx.fail("must specify an end date with '-e' / '--end'")

    if (algotext is not None) == (algofile is not None):
        ctx.fail(
            "must specify exactly one of '-f' / "
            "'--algofile' or"
            " '-t' / '--algotext'",
        )

    trading_calendar = get_calendar(trading_calendar)

    benchmark_spec = BenchmarkSpec.from_cli_params(
        no_benchmark=no_benchmark,
        benchmark_sid=benchmark_sid,
        benchmark_symbol=benchmark_symbol,
        benchmark_file=benchmark_file,
    )

    return _run(
        initialize=None,
        handle_data=None,
        before_trading_start=None,
        analyze=None,
        algofile=algofile,
        algotext=algotext,
        defines=define,
        data_frequency=data_frequency,
        capital_base=capital_base,
        bundle=bundle,
        bundle_timestamp=bundle_timestamp,
        start=start,
        end=end,
        output=output,
        trading_calendar=trading_calendar,
        print_algo=print_algo,
        metrics_set=metrics_set,
        local_namespace=local_namespace,
        environ=os.environ,
        blotter=blotter,
        benchmark_spec=benchmark_spec,
        custom_loader=None,
    )


def rustybt_magic(line, cell=None):
    """The zipline IPython cell magic."""
    load_extensions(
        default=True,
        extensions=[],
        strict=True,
        environ=os.environ,
    )
    try:
        return run.main(
            # put our overrides at the start of the parameter list so that
            # users may pass values with higher precedence
            [
                "--algotext",
                cell,
                "--output",
                os.devnull,  # don't write the results by default
            ]
            + (
                [
                    # these options are set when running in line magic mode
                    # set a non None algo text to use the ipython user_ns
                    "--algotext",
                    "",
                    "--local-namespace",
                ]
                if cell is None
                else []
            )
            + line.split(),
            "%s%%zipline" % ((cell or "") and "%"),
            # don't use system exit and propogate errors to the caller
            standalone_mode=False,
        )
    except SystemExit as exc:
        # https://github.com/mitsuhiko/click/pull/533
        # even in standalone_mode=False `--help` really wants to kill us ;_;
        if exc.code:
            raise ValueError(
                "main returned non-zero status code: %d" % exc.code
            ) from exc


@main.command()
@click.option(
    "-b",
    "--bundle",
    default=DEFAULT_BUNDLE,
    metavar="BUNDLE-NAME",
    show_default=True,
    help="The data bundle to ingest.",
)
@click.option(
    "--assets-version",
    type=int,
    multiple=True,
    help="Version of the assets db to which to downgrade.",
)
@click.option(
    "--show-progress/--no-show-progress",
    default=True,
    help="Print progress information to the terminal.",
)
def ingest(bundle, assets_version, show_progress):
    """Ingest the data for the given bundle."""
    bundles_module.ingest(
        bundle,
        os.environ,
        pd.Timestamp.utcnow(),
        assets_version,
        show_progress,
    )


@main.command(name="ingest-unified")
@click.argument("source", type=str, required=False)
@click.option(
    "-b",
    "--bundle",
    required=False,
    metavar="BUNDLE-NAME",
    help="The data bundle name to create/update.",
)
@click.option(
    "--symbols",
    required=False,
    help="Comma-separated list of symbols to ingest (e.g., 'AAPL,MSFT' or 'BTC/USDT,ETH/USDT').",
)
@click.option(
    "--start",
    type=Date(),
    required=False,
    help="Start date for data range (YYYY-MM-DD).",
)
@click.option(
    "--end",
    type=Date(),
    required=False,
    help="End date for data range (YYYY-MM-DD).",
)
@click.option(
    "--frequency",
    type=click.Choice(["1m", "5m", "15m", "30m", "1h", "1d"]),
    default="1d",
    show_default=True,
    help="Data frequency/resolution.",
)
@click.option(
    "--list-sources",
    is_flag=True,
    help="List all available data sources and exit.",
)
@click.option(
    "--source-info",
    type=str,
    metavar="SOURCE-NAME",
    help="Show detailed information about a specific source and exit.",
)
@click.option(
    "--exchange",
    type=str,
    help="Exchange ID for CCXT adapter (e.g., 'binance', 'coinbase').",
)
@click.option(
    "--api-key",
    type=str,
    help="API key for authenticated sources.",
)
@click.option(
    "--api-secret",
    type=str,
    help="API secret for authenticated sources.",
)
@click.option(
    "--csv-dir",
    type=click.Path(exists=True),
    help="Directory containing CSV files (for CSV adapter).",
)
def ingest_unified(
    source, bundle, symbols, start, end, frequency,
    list_sources, source_info, exchange, api_key, api_secret, csv_dir
):
    """Unified data ingestion command using DataSource interface.

    Examples:
        # List available sources
        rustybt ingest-unified --list-sources

        # Get source information
        rustybt ingest-unified --source-info yfinance

        # Ingest from YFinance
        rustybt ingest-unified yfinance --bundle my-stocks --symbols AAPL,MSFT \\
            --start 2023-01-01 --end 2023-12-31 --frequency 1d

        # Ingest from CCXT (crypto)
        rustybt ingest-unified ccxt --bundle crypto --symbols BTC/USDT,ETH/USDT \\
            --start 2024-01-01 --end 2024-01-31 --frequency 1h \\
            --exchange binance

        # Ingest from CSV
        rustybt ingest-unified csv --bundle csv-data --symbols AAPL \\
            --start 2023-01-01 --end 2023-12-31 --frequency 1d \\
            --csv-dir /path/to/csv
    """
    from rustybt.data.sources import DataSourceRegistry
    import pandas as pd

    # Handle --list-sources flag
    if list_sources:
        sources = DataSourceRegistry.list_sources()
        click.echo("\nAvailable data sources:")
        for src in sources:
            click.echo(f"  - {src}")
        click.echo(f"\nTotal: {len(sources)} sources")
        click.echo("\nUse --source-info <name> for details about a specific source.")
        return

    # Handle --source-info flag
    if source_info:
        try:
            info = DataSourceRegistry.get_source_info(source_info)
            click.echo(f"\nData Source: {info['name']}")
            click.echo(f"  Class: {info['class_name']}")
            click.echo(f"  Type: {info['source_type']}")
            click.echo(f"  Supports Live: {'Yes' if info['supports_live'] else 'No'}")
            click.echo(f"  Auth Required: {'Yes' if info['auth_required'] else 'No'}")

            if info['rate_limit']:
                click.echo(f"  Rate Limit: {info['rate_limit']} req/min")

            if info['data_delay'] is not None:
                delay_str = f"{info['data_delay']} minutes" if info['data_delay'] > 0 else "Real-time"
                click.echo(f"  Data Delay: {delay_str}")

            if info['supported_frequencies']:
                freqs = ', '.join(info['supported_frequencies'])
                click.echo(f"  Supported Frequencies: {freqs}")

            metadata = info['metadata']
            if metadata.additional_info:
                click.echo(f"  Additional Info:")
                for key, value in metadata.additional_info.items():
                    click.echo(f"    {key}: {value}")

            click.echo()
            return  # Exit after showing info
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            return

    # Require source argument if not using info flags
    if not source:
        click.echo("Error: SOURCE argument is required (or use --list-sources or --source-info)", err=True)
        click.echo("\nRun 'rustybt ingest-unified --help' for usage information.", err=True)
        return

    # Validate required parameters for actual ingestion
    if not bundle:
        click.echo("Error: --bundle is required for ingestion", err=True)
        return
    if not symbols:
        click.echo("Error: --symbols is required for ingestion", err=True)
        return
    if not start:
        click.echo("Error: --start is required for ingestion", err=True)
        return
    if not end:
        click.echo("Error: --end is required for ingestion", err=True)
        return

    # Parse symbols
    symbol_list = [s.strip() for s in symbols.split(",")]

    # Prepare source configuration
    config = {}

    if source.lower() == "ccxt":
        if not exchange:
            click.echo("Error: --exchange is required for CCXT adapter", err=True)
            return
        config["exchange_id"] = exchange
        if api_key:
            config["api_key"] = api_key
        if api_secret:
            config["api_secret"] = api_secret

    elif source.lower() == "csv":
        if not csv_dir:
            click.echo("Error: --csv-dir is required for CSV adapter", err=True)
            return
        config["csv_dir"] = csv_dir

    elif source.lower() in ["polygon", "alpaca", "alphavantage"]:
        if not api_key:
            click.echo(f"Warning: {source} typically requires --api-key for authentication", err=True)
        if api_key:
            config["api_key"] = api_key
        if api_secret:
            config["api_secret"] = api_secret

    # Get data source instance
    try:
        data_source = DataSourceRegistry.get_source(source, **config)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("\nUse --list-sources to see available sources.", err=True)
        return

    # Convert dates to timestamps
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    # Display ingestion info
    click.echo(f"\nIngesting data from {source}:")
    click.echo(f"  Bundle: {bundle}")
    click.echo(f"  Symbols: {', '.join(symbol_list)}")
    click.echo(f"  Date Range: {start_ts.date()} to {end_ts.date()}")
    click.echo(f"  Frequency: {frequency}")
    click.echo()

    # Perform ingestion
    try:
        with click.progressbar(
            length=len(symbol_list),
            label="Ingesting data",
            show_eta=True
        ) as bar:
            data_source.ingest_to_bundle(
                bundle_name=bundle,
                symbols=symbol_list,
                start=start_ts,
                end=end_ts,
                frequency=frequency,
            )
            bar.update(len(symbol_list))

        click.echo(f"\n✓ Successfully ingested data into bundle '{bundle}'")
        click.echo("  Use 'rustybt bundle list' to inspect bundles")

    except Exception as e:
        click.echo(f"\n✗ Ingestion failed: {e}", err=True)
        import traceback
        traceback.print_exc()


@main.command()
@click.option(
    "-b",
    "--bundle",
    default=DEFAULT_BUNDLE,
    metavar="BUNDLE-NAME",
    show_default=True,
    help="The data bundle to clean.",
)
@click.option(
    "-e",
    "--before",
    type=Timestamp(),
    help="Clear all data before TIMESTAMP."
    " This may not be passed with -k / --keep-last",
)
@click.option(
    "-a",
    "--after",
    type=Timestamp(),
    help="Clear all data after TIMESTAMP"
    " This may not be passed with -k / --keep-last",
)
@click.option(
    "-k",
    "--keep-last",
    type=int,
    metavar="N",
    help="Clear all but the last N downloads."
    " This may not be passed with -e / --before or -a / --after",
)
def clean(bundle, before, after, keep_last):
    """Clean up data downloaded with the ingest command."""
    bundles_module.clean(
        bundle,
        before,
        after,
        keep_last,
    )


@main.command()
def bundles():
    """List all of the available data bundles."""
    for bundle in sorted(bundles_module.bundles.keys()):
        if bundle.startswith("."):
            # hide the test data
            continue
        try:
            ingestions = list(map(str, bundles_module.ingestions_for_bundle(bundle)))
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            ingestions = []

        # If we got no ingestions, either because the directory didn't exist or
        # because there were no entries, print a single message indicating that
        # no ingestions have yet been made.
        for timestamp in ingestions or ["<no ingestions>"]:
            click.echo("%s %s" % (bundle, timestamp))


# ============================================================================
# Unified Bundle Management Commands (Story 8.4)
# ============================================================================


@main.group()
def bundle():
    """Manage unified bundle metadata."""


@bundle.command(name="list")
def bundle_list():
    """Display bundles with provenance summary."""

    console = Console()
    bundles = BundleMetadata.list_bundles()
    if not bundles:
        console.print("[yellow]No bundles found.[/yellow]")
        return

    table = Table(title="Available Bundles")
    table.add_column("Bundle Name", style="cyan", no_wrap=True)
    table.add_column("Source", style="magenta")
    table.add_column("Symbols", justify="right")
    table.add_column("Rows", justify="right")
    table.add_column("Date Range", style="green")
    table.add_column("Validation", style="blue")

    for item in sorted(bundles, key=lambda b: b["bundle_name"]):
        name = item["bundle_name"]
        symbol_count = BundleMetadata.count_symbols(name)
        start = _format_date(item.get("start_date"))
        end = _format_date(item.get("end_date"))
        date_range = "—" if start == "—" and end == "—" else f"{start} → {end}"
        validation_marker = "✓" if item.get("validation_passed") else "✗"
        table.add_row(
            name,
            item.get("source_type") or "—",
            str(symbol_count),
            f"{(item.get('row_count') or 0):,}",
            date_range,
            validation_marker,
        )

    console.print(table)
    console.print("\nUse 'rustybt bundle info <name>' for details or 'rustybt bundle validate <name>' to run checks.")


@bundle.command(name="info")
@click.argument("bundle_name", type=str)
def bundle_info(bundle_name: str):
    """Show detailed metadata for a bundle."""

    console = Console()
    metadata = BundleMetadata.get(bundle_name)
    if metadata is None:
        console.print(f"[red]Bundle '{bundle_name}' not found.[/red]")
        raise click.exceptions.Exit(1)

    symbols = BundleMetadata.get_symbols(bundle_name)
    symbol_names = [entry["symbol"] for entry in symbols]
    preview = ", ".join(symbol_names[:10])
    if len(symbol_names) > 10:
        preview += f", … (+{len(symbol_names) - 10})"

    console.print(f"[bold]Bundle:[/bold] {bundle_name}\n")

    provenance = Table(title="Provenance", show_header=False, box=None)
    provenance.add_row("Source Type", metadata.get("source_type") or "—")
    provenance.add_row("Source URL", metadata.get("source_url") or "—")
    provenance.add_row("API Version", metadata.get("api_version") or "—")
    provenance.add_row("Fetched", _format_timestamp(metadata.get("fetch_timestamp")))
    provenance.add_row("Timezone", metadata.get("timezone") or "UTC")
    console.print(provenance)

    quality = Table(title="Quality", show_header=False, box=None)
    quality.add_row("Row Count", f"{(metadata.get('row_count') or 0):,}")
    quality.add_row("Missing Days", str(metadata.get("missing_days_count") or 0))
    quality.add_row("OHLCV Violations", str(metadata.get("ohlcv_violations") or 0))
    status = "PASSED" if metadata.get("validation_passed") else "FAILED"
    quality.add_row("Validation", status)
    quality.add_row("Validated", _format_timestamp(metadata.get("validation_timestamp")))
    console.print(quality)

    file_meta = Table(title="File Metadata", show_header=False, box=None)
    file_meta.add_row("Checksum", metadata.get("file_checksum") or metadata.get("checksum") or "—")
    file_meta.add_row("Size", _format_size(metadata.get("file_size_bytes")))
    file_meta.add_row(
        "Date Range",
        f"{_format_date(metadata.get('start_date'))} → {_format_date(metadata.get('end_date'))}",
    )
    console.print(file_meta)

    symbols_table = Table(title=f"Symbols ({len(symbol_names)})", show_header=False, box=None)
    symbols_table.add_row("Sample", preview or "—")
    console.print(symbols_table)


@bundle.command(name="validate")
@click.argument("bundle_name", type=str)
def bundle_validate(bundle_name: str):
    """Validate bundle quality metrics against stored data."""

    import json
    import polars as pl

    console = Console()
    console.print(f"Validating bundle: {bundle_name}...\n")

    metadata = BundleMetadata.get(bundle_name)
    if metadata is None:
        console.print(f"[red]Bundle '{bundle_name}' not found in metadata catalog.[/red]")
        raise click.exceptions.Exit(1)

    bundle_root = Path(zipline_root()) / "data" / "bundles" / bundle_name
    daily_dir = bundle_root / "daily_bars"
    minute_dir = bundle_root / "minute_bars"

    parquet_files: list[str] = []
    dataset_type = None

    if daily_dir.exists():
        parquet_files = [str(p) for p in daily_dir.glob("**/data.parquet")]
        if parquet_files:
            dataset_type = "daily"
    if dataset_type is None and minute_dir.exists():
        parquet_files = [str(p) for p in minute_dir.glob("**/data.parquet")]
        if parquet_files:
            dataset_type = "minute"

    if dataset_type is None or not parquet_files:
        console.print("[yellow]No Parquet data files found for this bundle.[/yellow]")
        raise click.exceptions.Exit(1)

    scan = pl.scan_parquet(parquet_files)

    has_errors = False
    has_warnings = False

    date_col = "date" if dataset_type == "daily" else "timestamp"

    invalid_ohlcv = (
        scan.filter(
            (pl.col("high") < pl.col("low"))
            | (pl.col("high") < pl.col("open"))
            | (pl.col("high") < pl.col("close"))
            | (pl.col("low") > pl.col("open"))
            | (pl.col("low") > pl.col("close"))
        )
        .select(pl.len())
        .collect()
        .item()
    )

    if invalid_ohlcv == 0:
        console.print("[green]✓ OHLCV relationships valid (High ≥ Low, Close in range)[/green]")
    else:
        console.print(f"[red]✗ {invalid_ohlcv} rows violate OHLCV constraints[/red]")
        has_errors = True

    duplicates = (
        scan.group_by(["sid", date_col])
        .agg(pl.count().alias("count"))
        .filter(pl.col("count") > 1)
        .select(pl.len())
        .collect()
        .item()
    )

    if duplicates == 0:
        console.print("[green]✓ No duplicate timestamps[/green]")
    else:
        console.print(f"[red]✗ {duplicates} duplicate timestamp pairs detected[/red]")
        has_errors = True

    unique_sids = scan.select(pl.col("sid").n_unique()).collect().item()
    symbol_count = len(BundleMetadata.get_symbols(bundle_name))

    if symbol_count == 0:
        console.print("[yellow]⚠ No symbols recorded in metadata[/yellow]")
        has_warnings = True
    elif unique_sids == symbol_count:
        console.print("[green]✓ Symbol continuity valid (metadata matches data)[/green]")
    else:
        console.print(
            f"[yellow]⚠ Symbol metadata mismatch: {symbol_count} symbols vs {unique_sids} SIDs[/yellow]"
        )
        has_warnings = True

    missing_days = metadata.get("missing_days_count") or 0
    missing_list = metadata.get("missing_days_list")
    if isinstance(missing_list, str):
        try:
            missing_list = json.loads(missing_list)
        except json.JSONDecodeError:
            missing_list = []

    if missing_days > 0:
        preview = ", ".join(list(missing_list or [])[:5])
        suffix = f" (e.g., {preview})" if preview else ""
        console.print(f"[yellow]⚠ {missing_days} missing trading days detected{suffix}[/yellow]")
        has_warnings = True
    else:
        console.print("[green]✓ No missing trading days detected[/green]")

    if has_errors:
        console.print("\n[red]Overall: FAILED[/red]")
        raise click.exceptions.Exit(1)

    if has_warnings:
        console.print("\n[yellow]Overall: PASSED (with warnings)[/yellow]")
    else:
        console.print("\n[green]Overall: PASSED[/green]")


@bundle.command(name="migrate")
@click.option("--dry-run", is_flag=True, help="Preview migration without saving changes")
@click.option("--no-backup", is_flag=True, help="Skip backup before migration")
@click.option("--rollback", type=int, metavar="TIMESTAMP", help="Rollback to backup timestamp")
@click.option("--validate", is_flag=True, help="Validate migration integrity")
def bundle_migrate(dry_run: bool, no_backup: bool, rollback: int | None, validate: bool):
    """Run unified metadata migration commands."""

    module = _load_migration_module()
    console = Console()

    if rollback is not None:
        backup_dir = Path.home() / ".zipline" / "backups"
        backup_path = backup_dir / f"catalog-backup-{rollback}"
        manifest_file = backup_path / "manifest.json"
        if not backup_path.exists() or not manifest_file.exists():
            console.print(f"[red]Backup {rollback} not found.[/red]")
            raise click.exceptions.Exit(1)

        with open(manifest_file) as fh:
            data = module.json.load(fh)

        manifest = module.BackupManifest(
            timestamp=data["timestamp"],
            backup_path=backup_path,
            datacatalog_checksum=data.get("datacatalog_checksum", ""),
            parquet_catalogs=data.get("parquet_catalogs", {}),
            bundle_count=data.get("bundle_count", 0),
        )
        module.restore_from_backup(manifest)
        return

    if validate:
        success = module.validate_migration()
        if not success:
            raise click.exceptions.Exit(1)
        return

    stats = module.run_migration(dry_run=dry_run, backup=not no_backup)
    if not dry_run and not stats.errors:
        module.validate_migration()


# ============================================================================
# Cache Management Commands (Story 8.3: Smart Caching Layer)
# ============================================================================


@main.group()
def cache():
    """Manage data source cache."""
    pass


@cache.command(name="stats")
@click.option(
    "-d",
    "--days",
    type=int,
    default=7,
    help="Number of days to show statistics for (default: 7)",
)
def cache_stats(days):
    """Display cache statistics (hit rate, size, latency).

    Example:
        rustybt cache stats
        rustybt cache stats --days 30
    """
    from rustybt.data.catalog import DataCatalog

    catalog = DataCatalog()
    stats = catalog.get_cache_stats(days=days)

    if not stats:
        click.echo("No cache statistics available.")
        return

    # Display header
    click.echo(f"\nCache Statistics (Last {days} Days)")
    click.echo("=" * 80)
    click.echo(
        f"{'Date':<12} {'Hits':<8} {'Misses':<8} {'Hit Rate':<12} "
        f"{'Size (MB)':<12} {'Fetch (ms)':<12}"
    )
    click.echo("-" * 80)

    # Display stats rows
    for stat in stats:
        date_str = pd.Timestamp(stat["stat_date"], unit="s").strftime("%Y-%m-%d")
        hits = stat["hit_count"]
        misses = stat["miss_count"]
        hit_rate = f"{stat['hit_rate']:.1f}%"
        size_mb = f"{stat['total_size_mb']:.1f}"
        latency_ms = f"{stat['avg_fetch_latency_ms']:.1f}"

        click.echo(
            f"{date_str:<12} {hits:<8} {misses:<8} {hit_rate:<12} "
            f"{size_mb:<12} {latency_ms:<12}"
        )

    click.echo("=" * 80)

    # Summary
    total_hits = sum(s["hit_count"] for s in stats)
    total_misses = sum(s["miss_count"] for s in stats)
    total_requests = total_hits + total_misses
    overall_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0

    click.echo(f"\nOverall Hit Rate: {overall_hit_rate:.1f}%")
    click.echo(f"Total Requests: {total_requests:,} ({total_hits:,} hits, {total_misses:,} misses)")


@cache.command(name="clean")
@click.option(
    "--max-size",
    type=str,
    help="Maximum cache size (e.g., '5GB', '1000MB'). Evicts LRU entries to reach size.",
)
@click.option(
    "--all",
    "clean_all",
    is_flag=True,
    help="Remove all cache entries.",
)
def cache_clean(max_size, clean_all):
    """Clean cache by evicting LRU entries or removing all entries.

    Examples:
        rustybt cache clean --max-size 5GB
        rustybt cache clean --max-size 1000MB
        rustybt cache clean --all
    """
    from rustybt.data.catalog import DataCatalog
    from pathlib import Path

    catalog = DataCatalog()

    if clean_all:
        # Remove all cache entries
        click.echo("Removing all cache entries...")

        entries = catalog.get_lru_cache_entries()

        if not entries:
            click.echo("Cache is already empty.")
            return

        for entry in entries:
            # Delete bundle files
            bundle_path = Path(entry["bundle_path"])
            if bundle_path.exists():
                import shutil

                shutil.rmtree(bundle_path)

            # Delete cache metadata
            catalog.delete_cache_entry(entry["cache_key"])

        click.echo(f"Removed {len(entries)} cache entries.")
        return

    if max_size:
        # Parse max size (e.g., "5GB", "1000MB")
        max_size_upper = max_size.upper()
        if max_size_upper.endswith("GB"):
            max_size_bytes = int(float(max_size_upper[:-2]) * 1024**3)
        elif max_size_upper.endswith("MB"):
            max_size_bytes = int(float(max_size_upper[:-2]) * 1024**2)
        else:
            click.echo("Invalid size format. Use '5GB' or '1000MB'.")
            return

        current_size = catalog.get_cache_size()
        click.echo(f"Current cache size: {current_size / 1024**2:.1f} MB")
        click.echo(f"Target cache size: {max_size_bytes / 1024**2:.1f} MB")

        if current_size <= max_size_bytes:
            click.echo("Cache is already under the target size.")
            return

        # Evict LRU entries
        lru_entries = catalog.get_lru_cache_entries()

        evicted_count = 0
        evicted_size = 0

        for entry in lru_entries:
            # Delete bundle files
            bundle_path = Path(entry["bundle_path"])
            if bundle_path.exists():
                import shutil

                shutil.rmtree(bundle_path)

            # Delete cache metadata
            catalog.delete_cache_entry(entry["cache_key"])

            evicted_count += 1
            evicted_size += entry["size_bytes"]
            current_size -= entry["size_bytes"]

            # Stop when under limit
            if current_size <= max_size_bytes:
                break

        click.echo(f"Evicted {evicted_count} entries ({evicted_size / 1024**2:.1f} MB)")
        click.echo(f"New cache size: {current_size / 1024**2:.1f} MB")
    else:
        click.echo("Specify --max-size or --all to clean cache.")


@cache.command(name="list")
def cache_list():
    """List all cache entries with metadata.

    Example:
        rustybt cache list
    """
    from rustybt.data.catalog import DataCatalog

    catalog = DataCatalog()
    entries = catalog.get_lru_cache_entries()

    if not entries:
        click.echo("No cache entries found.")
        return

    # Display header
    click.echo(f"\nCache Entries ({len(entries)} total)")
    click.echo("=" * 100)
    click.echo(f"{'Cache Key':<18} {'Bundle Name':<25} {'Size (MB)':<12} {'Last Accessed':<20}")
    click.echo("-" * 100)

    # Display entries
    for entry in entries:
        cache_key = entry["cache_key"]
        bundle_name = entry["bundle_name"][:24]  # Truncate long names
        size_mb = f"{entry['size_bytes'] / 1024**2:.2f}"
        last_accessed = pd.Timestamp(entry["last_accessed"], unit="s").strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        click.echo(f"{cache_key:<18} {bundle_name:<25} {size_mb:<12} {last_accessed:<20}")

    click.echo("=" * 100)

    # Summary
    total_size = sum(e["size_bytes"] for e in entries)
    click.echo(f"\nTotal cache size: {total_size / 1024**2:.1f} MB ({total_size / 1024**3:.2f} GB)")


if __name__ == "__main__":
    main()
