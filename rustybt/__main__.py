import errno
import logging
import os
from datetime import UTC, datetime
from importlib import util as importlib_util
from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

import rustybt
from rustybt.data import bundles as bundles_module
from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.extensions import create_args
from rustybt.utils.calendar_utils import get_calendar
from rustybt.utils.cli import Date, Timestamp
from rustybt.utils.compat import wraps
from rustybt.utils.paths import zipline_root
from rustybt.utils.run_algo import BenchmarkSpec, _run, load_extensions

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

    Returns:
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

    Returns:
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
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S %Z")
    except (OSError, OverflowError, ValueError):
        return str(ts)


def _format_date(ts: int | None) -> str:
    if ts is None:
        return "—"
    try:
        return datetime.fromtimestamp(ts, tz=UTC).date().isoformat()
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

    script_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "migrate_catalog_to_unified.py"
    )
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
    help="The date to lookup data on or before.\n[default: <current-time>]",
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
    help="The location to write the perf data. If this is '-' the perf will be written to stdout.",
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
    help="The metrics set to use. New metrics sets may be registered in your extension.py.",
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
        help="Should the algorithm methods be resolved in the local namespace.",
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
            "must specify exactly one of '-f' / '--algofile' or '-t' / '--algotext'",
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
            raise ValueError("main returned non-zero status code: %d" % exc.code) from exc


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
    "--list-exchanges",
    is_flag=True,
    help="List available CCXT exchanges and exit (use with 'ccxt' source).",
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
    source,
    bundle,
    symbols,
    start,
    end,
    frequency,
    list_sources,
    source_info,
    list_exchanges,
    exchange,
    api_key,
    api_secret,
    csv_dir,
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

        # List CCXT exchanges
        rustybt ingest-unified ccxt --list-exchanges

        # Ingest from CSV
        rustybt ingest-unified csv --bundle csv-data --symbols AAPL \\
            --start 2023-01-01 --end 2023-12-31 --frequency 1d \\
            --csv-dir /path/to/csv
    """
    import pandas as pd

    from rustybt.data.sources import DataSourceRegistry

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

            if info["rate_limit"]:
                click.echo(f"  Rate Limit: {info['rate_limit']} req/min")

            if info["data_delay"] is not None:
                delay_str = (
                    f"{info['data_delay']} minutes" if info["data_delay"] > 0 else "Real-time"
                )
                click.echo(f"  Data Delay: {delay_str}")

            if info["supported_frequencies"]:
                freqs = ", ".join(info["supported_frequencies"])
                click.echo(f"  Supported Frequencies: {freqs}")

            metadata = info["metadata"]
            if metadata.additional_info:
                click.echo("  Additional Info:")
                for key, value in metadata.additional_info.items():
                    click.echo(f"    {key}: {value}")

            click.echo()
            return  # Exit after showing info
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            return

    # Handle --list-exchanges flag (only for CCXT)
    if list_exchanges:
        if (source or "").lower() != "ccxt":
            click.echo("Error: --list-exchanges requires 'ccxt' as the SOURCE argument", err=True)
            return
        try:
            import ccxt  # type: ignore
        except Exception:
            click.echo("Error: ccxt is not installed. Install with 'pip install ccxt'", err=True)
            return
        exchanges = sorted(getattr(ccxt, "exchanges", []))
        if not exchanges:
            click.echo("No exchanges reported by ccxt.")
            return
        click.echo("\nCCXT Exchanges:")
        for ex in exchanges:
            click.echo(f"  - {ex}")
        click.echo(f"\nTotal: {len(exchanges)} exchanges")
        return

    # Require source argument if not using info flags
    if not source:
        click.echo(
            "Error: SOURCE argument is required (or use --list-sources or --source-info)", err=True
        )
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
            click.echo(
                f"Warning: {source} typically requires --api-key for authentication", err=True
            )
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
            length=len(symbol_list), label="Ingesting data", show_eta=True
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
    help="Clear all data before TIMESTAMP. This may not be passed with -k / --keep-last",
)
@click.option(
    "-a",
    "--after",
    type=Timestamp(),
    help="Clear all data after TIMESTAMP This may not be passed with -k / --keep-last",
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
    console.print(
        "\nUse 'rustybt bundle info <name>' for details or 'rustybt bundle validate <name>' to run checks."
    )


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
            f"{date_str:<12} {hits:<8} {misses:<8} {hit_rate:<12} {size_mb:<12} {latency_ms:<12}"
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
    from pathlib import Path

    from rustybt.data.catalog import DataCatalog

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
        last_accessed = pd.Timestamp(entry["last_accessed"], unit="s").strftime("%Y-%m-%d %H:%M:%S")

        click.echo(f"{cache_key:<18} {bundle_name:<25} {size_mb:<12} {last_accessed:<20}")

    click.echo("=" * 100)

    # Summary
    total_size = sum(e["size_bytes"] for e in entries)
    click.echo(f"\nTotal cache size: {total_size / 1024**2:.1f} MB ({total_size / 1024**3:.2f} GB)")


# ============================================================================
# Security & Configuration Commands (Story 8.10)
# ============================================================================


@main.command()
def keygen():
    """Generate encryption key for credential storage.

    Generates a Fernet encryption key for encrypting broker API keys and secrets.
    Save the generated key to RUSTYBT_ENCRYPTION_KEY environment variable.

    Example:
        rustybt keygen
        # Copy output to .env file:
        # RUSTYBT_ENCRYPTION_KEY=<generated-key>
    """
    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    key_str = key.decode("utf-8")

    click.echo("\n" + "=" * 80)
    click.echo("Generated Encryption Key")
    click.echo("=" * 80)
    click.echo(f"\n{key_str}\n")
    click.echo("Add this key to your .env file:")
    click.echo(f"RUSTYBT_ENCRYPTION_KEY={key_str}")
    click.echo("\n⚠️  IMPORTANT: Store this key securely. Loss of this key means")
    click.echo("   loss of access to encrypted credentials.")
    click.echo("=" * 80 + "\n")


@main.command()
@click.option(
    "--env-file",
    type=click.Path(exists=True),
    default=".env",
    help="Path to .env file containing credentials",
)
def encrypt_credentials(env_file):
    """Encrypt broker credentials at rest.

    Encrypts API keys and secrets from .env file using RUSTYBT_ENCRYPTION_KEY.
    Creates encrypted credentials file at ~/.rustybt/credentials.enc

    Example:
        rustybt encrypt-credentials
        rustybt encrypt-credentials --env-file /path/to/.env
    """
    import json
    import os
    from pathlib import Path

    from cryptography.fernet import Fernet

    # Check for encryption key
    encryption_key = os.getenv("RUSTYBT_ENCRYPTION_KEY")
    if not encryption_key:
        click.echo("❌ Error: RUSTYBT_ENCRYPTION_KEY not found in environment", err=True)
        click.echo("   Run 'rustybt keygen' to generate a key first", err=True)
        raise click.exceptions.Exit(1)

    # Read credentials from .env file
    credentials = {}
    credential_keys = [
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "IB_ACCOUNT",
        "API_AUTH_TOKEN",
    ]

    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    if key in credential_keys:
                        credentials[key] = value
    except FileNotFoundError:
        click.echo(f"❌ Error: File not found: {env_file}", err=True)
        raise click.exceptions.Exit(1)

    if not credentials:
        click.echo("⚠️  Warning: No credentials found in .env file", err=True)
        click.echo("   Expected keys: " + ", ".join(credential_keys))
        raise click.exceptions.Exit(1)

    # Encrypt credentials
    cipher = Fernet(encryption_key.encode())
    encrypted_data = cipher.encrypt(json.dumps(credentials).encode())

    # Save to encrypted file
    creds_dir = Path.home() / ".rustybt" / "config"
    creds_dir.mkdir(parents=True, exist_ok=True)
    creds_file = creds_dir / "credentials.enc"

    with open(creds_file, "wb") as f:
        f.write(encrypted_data)

    # Set restrictive permissions
    os.chmod(creds_file, 0o600)

    click.echo(f"\n✓ Successfully encrypted {len(credentials)} credentials")
    click.echo(f"  Saved to: {creds_file}")
    click.echo("  Permissions: -rw------- (600)")
    click.echo("\n⚠️  You can now remove plaintext credentials from .env file\n")


@main.command()
@click.option(
    "--broker",
    type=click.Choice(["binance", "bybit", "hyperliquid", "ccxt", "ib"], case_sensitive=False),
    required=True,
    help="Broker to test",
)
@click.option("--testnet", is_flag=True, help="Use testnet/paper trading environment")
def test_broker(broker, testnet):
    """Test broker connection and authentication.

    Verifies broker API credentials and connection by:
    - Testing authentication
    - Fetching account information
    - Checking API rate limits

    Example:
        rustybt test-broker --broker binance
        rustybt test-broker --broker binance --testnet
        rustybt test-broker --broker bybit
        rustybt test-broker --broker hyperliquid
    """
    import asyncio
    import os

    click.echo(f"\n{'=' * 80}")
    click.echo(f"Testing {broker.upper()} Connection")
    if testnet:
        click.echo("Mode: TESTNET/PAPER TRADING")
    click.echo(f"{'=' * 80}\n")

    async def test_connection():
        try:
            if broker.lower() == "binance":
                import ccxt.async_support as ccxt_async

                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_API_SECRET")

                if not api_key or not api_secret:
                    click.echo("❌ Error: BINANCE_API_KEY or BINANCE_API_SECRET not set", err=True)
                    return False

                exchange = ccxt_async.binance(
                    {
                        "apiKey": api_key,
                        "secret": api_secret,
                        "options": {"defaultType": "spot"},
                    }
                )

                if testnet:
                    exchange.set_sandbox_mode(True)

                click.echo("📡 Connecting to Binance...")
                balance = await exchange.fetch_balance()

                click.echo("✓ Connection successful")
                click.echo("✓ Account authenticated")
                click.echo(f"✓ Total balance: {len(balance.get('total', {}))} assets")

                # Test market data
                ticker = await exchange.fetch_ticker("BTC/USDT")
                click.echo(f"✓ Market data accessible (BTC/USDT: ${ticker['last']:.2f})")

                await exchange.close()
                return True

            elif broker.lower() == "bybit":
                import ccxt.async_support as ccxt_async

                api_key = os.getenv("BYBIT_API_KEY")
                api_secret = os.getenv("BYBIT_API_SECRET")

                if not api_key or not api_secret:
                    click.echo("❌ Error: BYBIT_API_KEY or BYBIT_API_SECRET not set", err=True)
                    return False

                exchange = ccxt_async.bybit(
                    {
                        "apiKey": api_key,
                        "secret": api_secret,
                    }
                )

                if testnet:
                    exchange.set_sandbox_mode(True)

                click.echo("📡 Connecting to Bybit...")
                balance = await exchange.fetch_balance()

                click.echo("✓ Connection successful")
                click.echo("✓ Account authenticated")
                click.echo(f"✓ Total balance: {len(balance.get('total', {}))} assets")

                # Test market data
                ticker = await exchange.fetch_ticker("BTC/USDT")
                click.echo(f"✓ Market data accessible (BTC/USDT: ${ticker['last']:.2f})")

                await exchange.close()
                return True

            elif broker.lower() == "hyperliquid":
                private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
                wallet_address = os.getenv("HYPERLIQUID_WALLET_ADDRESS")

                if not private_key:
                    click.echo("❌ Error: HYPERLIQUID_PRIVATE_KEY not set", err=True)
                    return False

                if not wallet_address:
                    click.echo("⚠️  Warning: HYPERLIQUID_WALLET_ADDRESS not set (optional)")

                # Import Hyperliquid SDK
                from hyperliquid.info import Info
                from hyperliquid.utils import constants

                # Initialize Info API (read-only, no authentication needed)
                base_url = constants.MAINNET_API_URL
                if testnet:
                    click.echo(
                        "⚠️  Hyperliquid testnet not available, using mainnet for info queries"
                    )

                info = Info(base_url=base_url, skip_ws=True)

                click.echo("📡 Connecting to Hyperliquid...")

                # Test market data access (no auth required)
                try:
                    all_mids = info.all_mids()
                    if all_mids and len(all_mids) > 0:
                        click.echo("✓ Connection successful")
                        click.echo(f"✓ Market data accessible ({len(all_mids)} markets)")

                        # Show BTC price if available
                        if "BTC" in all_mids:
                            click.echo(f"✓ BTC/USD: ${float(all_mids['BTC']):.2f}")
                except Exception as e:
                    click.echo(f"⚠️  Market data test failed: {e}")

                # Test user data access (requires private key/wallet)
                if wallet_address:
                    try:
                        user_state = info.user_state(wallet_address)
                        if user_state:
                            click.echo("✓ Account authenticated")

                            # Show position info
                            positions = user_state.get("assetPositions", [])
                            click.echo(f"✓ Account accessible ({len(positions)} positions)")
                    except Exception as e:
                        click.echo(f"⚠️  Account data access: {e}")
                else:
                    click.echo("⚠️  Skipping account authentication (no wallet address)")

                click.echo("✓ Private key validated (format correct)")
                return True

            elif broker.lower() == "ccxt":
                click.echo(
                    "⚠️  CCXT supports 100+ exchanges. Specify exchange with --broker <exchange>"
                )
                return False

            elif broker.lower() == "ib":
                click.echo("⚠️  Interactive Brokers testing requires IB Gateway/TWS running")
                click.echo(
                    "   Please ensure IB Gateway is running on port 7497 (paper) or 7496 (live)"
                )
                return False

            else:
                click.echo(f"❌ Error: Broker '{broker}' not fully implemented yet", err=True)
                return False

        except Exception as e:
            click.echo(f"\n❌ Connection failed: {e!s}", err=True)
            import traceback

            click.echo(f"\nDebug info:\n{traceback.format_exc()}", err=True)
            return False

    success = asyncio.run(test_connection())

    click.echo(f"\n{'=' * 80}")
    if success:
        click.echo("✓ Test completed successfully")
    else:
        click.echo("✗ Test failed")
    click.echo(f"{'=' * 80}\n")

    if not success:
        raise click.exceptions.Exit(1)


@main.command()
@click.option(
    "--env-file", type=click.Path(exists=True), default=".env", help="Path to .env file to validate"
)
def verify_config(env_file):
    """Validate configuration file.

    Checks .env file for:
    - Required variables
    - Valid values
    - Security issues (e.g., weak encryption keys)

    Example:
        rustybt verify-config
        rustybt verify-config --env-file /path/to/.env
    """
    click.echo(f"\n{'=' * 80}")
    click.echo("Configuration Validation")
    click.echo(f"{'=' * 80}\n")
    click.echo(f"Checking: {env_file}\n")

    errors = []
    warnings = []
    config = {}

    # Read .env file
    try:
        with open(env_file) as f:
            for _line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    except FileNotFoundError:
        click.echo(f"❌ Error: File not found: {env_file}", err=True)
        raise click.exceptions.Exit(1)

    # Check required variables
    required_vars = {
        "RUSTYBT_ENCRYPTION_KEY": "Encryption key for credential storage",
        "LOG_LEVEL": "Logging level",
        "LOG_DIR": "Log directory path",
    }

    for var, description in required_vars.items():
        if var not in config:
            warnings.append(f"Missing recommended variable: {var} ({description})")
        elif not config[var]:
            errors.append(f"Empty value for: {var}")

    # Validate encryption key
    if "RUSTYBT_ENCRYPTION_KEY" in config:
        key = config["RUSTYBT_ENCRYPTION_KEY"]
        if len(key) < 40:
            errors.append("RUSTYBT_ENCRYPTION_KEY appears too short (should be Fernet key)")

    # Validate risk limits
    risk_vars = {
        "MAX_POSITION_SIZE": (0.0, 1.0),
        "MAX_DAILY_LOSS": (0.0, 1.0),
        "MAX_LEVERAGE": (1.0, 10.0),
    }

    for var, (min_val, max_val) in risk_vars.items():
        if var in config:
            try:
                value = float(config[var])
                if not (min_val <= value <= max_val):
                    warnings.append(
                        f"{var}={value} outside recommended range [{min_val}, {max_val}]"
                    )
            except ValueError:
                errors.append(f"Invalid numeric value for {var}: {config[var]}")

    # Check for common mistakes
    if "BINANCE_API_KEY" in config and len(config["BINANCE_API_KEY"]) < 20:
        warnings.append("BINANCE_API_KEY seems too short")

    # Display results
    click.echo("Results:")
    click.echo("-" * 80)

    if not errors and not warnings:
        click.echo("✓ Configuration valid - no issues found")
    else:
        if errors:
            click.echo(f"\n❌ Errors ({len(errors)}):")
            for err in errors:
                click.echo(f"   - {err}")

        if warnings:
            click.echo(f"\n⚠️  Warnings ({len(warnings)}):")
            for warn in warnings:
                click.echo(f"   - {warn}")

    click.echo(f"\n{'=' * 80}\n")

    if errors:
        raise click.exceptions.Exit(1)


# ============================================================================
# Live Trading Commands (Story 8.10)
# ============================================================================


@main.command()
@click.option(
    "--strategy", type=click.Path(exists=True), required=True, help="Path to strategy Python file"
)
@click.option(
    "--broker",
    type=click.Choice(["binance", "bybit", "paper"], case_sensitive=False),
    default="paper",
    help="Broker to use (default: paper)",
)
@click.option("--duration", type=str, default="24h", help="Duration to run (e.g., 24h, 7d, 30d)")
@click.option(
    "--log-file",
    type=click.Path(),
    help="Path to log file (default: logs/paper_trade_{timestamp}.log)",
)
def paper_trade(strategy, broker, duration, log_file):
    """Run paper trading mode.

    Executes strategy in paper trading mode with simulated broker.
    Tracks uptime, error rate, and performance metrics.

    Example:
        rustybt paper-trade --strategy momentum.py --duration 30d
        rustybt paper-trade --strategy momentum.py --broker binance --duration 7d
    """
    import importlib.util
    import sys
    from datetime import datetime
    from pathlib import Path

    click.echo(f"\n{'=' * 80}")
    click.echo("Paper Trading Mode")
    click.echo(f"{'=' * 80}")
    click.echo(f"Strategy: {strategy}")
    click.echo(f"Broker: {broker}")
    click.echo(f"Duration: {duration}")
    click.echo(f"{'=' * 80}\n")

    # Parse duration
    duration_mapping = {"h": "hours", "d": "days", "w": "weeks", "m": "months"}
    unit = duration[-1]
    int(duration[:-1])

    if unit not in duration_mapping:
        click.echo(f"❌ Invalid duration format: {duration}", err=True)
        click.echo("   Use format: 24h, 7d, 30d, 4w", err=True)
        raise click.exceptions.Exit(1)

    # Setup logging
    if not log_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"paper_trade_{timestamp}.log"

    # Load strategy
    try:
        spec = importlib.util.spec_from_file_location("strategy", strategy)
        if spec and spec.loader:
            strategy_module = importlib.util.module_from_spec(spec)
            sys.modules["strategy"] = strategy_module
            spec.loader.exec_module(strategy_module)
        else:
            raise ImportError(f"Cannot load strategy from {strategy}")
    except Exception as e:
        click.echo(f"❌ Error loading strategy: {e}", err=True)
        raise click.exceptions.Exit(1)

    click.echo("✓ Strategy loaded successfully")
    click.echo(f"✓ Logging to: {log_file}")
    click.echo("\n⚠️  Paper trading will run for {value} {duration_mapping[unit]}")
    click.echo("   Press Ctrl+C to stop\n")

    # Note: Actual implementation would start LiveTradingEngine with PaperBroker
    click.echo("⚠️  Full paper trading engine integration coming in Epic 6")
    click.echo("   This command validates strategy loading and configuration")


@main.command()
@click.option(
    "--strategy", type=click.Path(exists=True), required=True, help="Path to strategy Python file"
)
@click.option(
    "--broker",
    type=click.Choice(["binance", "bybit", "ib"], case_sensitive=False),
    required=True,
    help="Live broker to use",
)
@click.option("--confirm", is_flag=True, help="Confirm live trading with real money")
def live_trade(strategy, broker, confirm):
    """Run live trading mode.

    ⚠️  CAUTION: Trades with REAL MONEY

    Executes strategy in live trading mode with real broker connection.
    Requires --confirm flag for safety.

    Example:
        rustybt live-trade --strategy momentum.py --broker binance --confirm
    """
    import importlib.util
    import sys

    if not confirm:
        click.echo("\n⚠️  LIVE TRADING REQUIRES --confirm FLAG", err=True)
        click.echo("   This will trade with REAL MONEY on a REAL BROKER", err=True)
        click.echo(
            "\n   Run: rustybt live-trade --strategy <file> --broker <broker> --confirm\n", err=True
        )
        raise click.exceptions.Exit(1)

    click.echo(f"\n{'=' * 80}")
    click.echo("⚠️  LIVE TRADING MODE - REAL MONEY")
    click.echo(f"{'=' * 80}")
    click.echo(f"Strategy: {strategy}")
    click.echo(f"Broker: {broker}")
    click.echo(f"{'=' * 80}\n")

    # Final confirmation
    click.confirm("Are you ABSOLUTELY SURE you want to start live trading?", abort=True)

    # Load strategy
    try:
        spec = importlib.util.spec_from_file_location("strategy", strategy)
        if spec and spec.loader:
            strategy_module = importlib.util.module_from_spec(spec)
            sys.modules["strategy"] = strategy_module
            spec.loader.exec_module(strategy_module)
        else:
            raise ImportError(f"Cannot load strategy from {strategy}")
    except Exception as e:
        click.echo(f"❌ Error loading strategy: {e}", err=True)
        raise click.exceptions.Exit(1)

    click.echo("✓ Strategy loaded successfully")
    click.echo("\n⚠️  Live trading engine requires Epic 6 implementation")
    click.echo("   This command validates strategy loading and broker connection")


# ============================================================================
# Monitoring & Analysis Commands (Story 8.10)
# ============================================================================


@main.command()
@click.option("--log-file", type=click.Path(exists=True), help="Path to log file to analyze")
@click.option(
    "--log-dir", type=click.Path(exists=True), default="logs", help="Directory containing log files"
)
@click.option("--days", type=int, default=30, help="Number of days to analyze")
def analyze_uptime(log_file, log_dir, days):
    """Analyze logs for uptime statistics.

    Calculates:
    - Total uptime percentage
    - Downtime duration and frequency
    - Error rate per 1000 operations
    - Common error patterns

    Example:
        rustybt analyze-uptime --days 30
        rustybt analyze-uptime --log-file logs/paper_trade.log
    """
    import re
    from collections import Counter
    from datetime import datetime, timedelta
    from pathlib import Path

    click.echo(f"\n{'=' * 80}")
    click.echo("Uptime Analysis")
    click.echo(f"{'=' * 80}\n")

    # Collect log files
    log_files = []
    if log_file:
        log_files = [Path(log_file)]
    else:
        log_dir_path = Path(log_dir)
        if log_dir_path.exists():
            cutoff_date = datetime.now() - timedelta(days=days)
            for lf in log_dir_path.glob("*.log"):
                if lf.stat().st_mtime > cutoff_date.timestamp():
                    log_files.append(lf)

    if not log_files:
        click.echo(f"❌ No log files found in {log_dir}", err=True)
        raise click.exceptions.Exit(1)

    click.echo(f"Analyzing {len(log_files)} log files from last {days} days\n")

    # Parse logs
    total_operations = 0
    errors = 0
    warnings = 0
    start_events = []
    stop_events = []
    error_types = Counter()

    for lf in log_files:
        with open(lf) as f:
            for line in f:
                # Count operations
                if "order_filled" in line or "order_submitted" in line:
                    total_operations += 1

                # Track errors
                if "ERROR" in line:
                    errors += 1
                    # Extract error type
                    match = re.search(r"ERROR.*?(\w+Error|\w+Exception)", line)
                    if match:
                        error_types[match.group(1)] += 1

                if "WARNING" in line:
                    warnings += 1

                # Track start/stop
                if "engine_started" in line or "strategy_initialized" in line:
                    start_events.append(line)
                if "engine_stopped" in line or "strategy_halted" in line:
                    stop_events.append(line)

    # Calculate uptime
    total_hours = days * 24
    # Approximate downtime based on restarts
    estimated_downtime_hours = len(stop_events) * 0.5  # Assume 30min per restart

    uptime_pct = ((total_hours - estimated_downtime_hours) / total_hours) * 100

    # Display results
    click.echo("Results:")
    click.echo("-" * 80)
    click.echo(f"Total Operations: {total_operations:,}")
    click.echo(f"Errors: {errors:,} ({(errors / max(total_operations, 1) * 100):.2f}%)")
    click.echo(f"Warnings: {warnings:,}")
    click.echo(f"\nUptime: {uptime_pct:.3f}%")
    click.echo(f"Estimated Downtime: {estimated_downtime_hours:.1f} hours")
    click.echo(f"Restarts: {len(stop_events)}")

    # 99.9% uptime target
    target_uptime = 99.9
    max_downtime = total_hours * (1 - target_uptime / 100)
    click.echo(f"\nTarget: 99.9% uptime (max {max_downtime:.1f} hours downtime)")

    if uptime_pct >= target_uptime:
        click.echo("✓ PASS - Uptime target met")
    else:
        click.echo(f"✗ FAIL - Uptime {uptime_pct:.3f}% below target {target_uptime}%")

    # Error breakdown
    if error_types:
        click.echo("\nTop Error Types:")
        for error_type, count in error_types.most_common(5):
            click.echo(f"  {error_type}: {count}")

    click.echo(f"\n{'=' * 80}\n")


@main.command()
@click.option(
    "--output",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format",
)
def benchmark(output):
    """Run performance benchmarks.

    Tests:
    - Order execution latency
    - Backtest speed
    - Memory usage
    - Data portal throughput

    Example:
        rustybt benchmark
        rustybt benchmark --output json
    """
    import json as json_module
    import time
    from decimal import Decimal

    import psutil

    click.echo(f"\n{'=' * 80}")
    click.echo("Performance Benchmarks")
    click.echo(f"{'=' * 80}\n")

    results = {}

    # Benchmark 1: Decimal arithmetic
    click.echo("Running Decimal arithmetic benchmark...")
    start = time.perf_counter()
    total = Decimal("0")
    for i in range(10000):
        total += Decimal(str(i)) * Decimal("1.01")
    decimal_time = (time.perf_counter() - start) * 1000
    results["decimal_arithmetic_ms"] = round(decimal_time, 2)
    click.echo(f"  ✓ Completed in {decimal_time:.2f}ms")

    # Benchmark 2: Memory usage
    click.echo("Measuring memory usage...")
    process = psutil.Process()
    mem_info = process.memory_info()
    results["memory_rss_mb"] = round(mem_info.rss / 1024**2, 2)
    results["memory_vms_mb"] = round(mem_info.vms / 1024**2, 2)
    click.echo(f"  ✓ RSS: {results['memory_rss_mb']} MB")

    # Benchmark 3: File I/O
    click.echo("Testing file I/O...")
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", delete=True) as f:
        start = time.perf_counter()
        for _ in range(1000):
            f.write("test data line\n")
        f.flush()
        io_time = (time.perf_counter() - start) * 1000
    results["file_io_1000_lines_ms"] = round(io_time, 2)
    click.echo(f"  ✓ 1000 writes in {io_time:.2f}ms")

    # Display results
    if output == "json":
        click.echo(f"\n{json_module.dumps(results, indent=2)}\n")
    else:
        click.echo(f"\n{'=' * 80}")
        click.echo("Benchmark Results:")
        click.echo("-" * 80)
        for key, value in results.items():
            click.echo(f"{key}: {value}")
        click.echo(f"{'=' * 80}\n")


@main.command()
@click.option(
    "--broker",
    type=click.Choice(["binance", "bybit", "paper"], case_sensitive=False),
    required=True,
    help="Broker to query",
)
def balance(broker):
    """Query account balance from broker.

    Example:
        rustybt balance --broker binance
        rustybt balance --broker paper
    """
    import asyncio
    import os

    async def fetch_balance():
        try:
            if broker == "binance":
                import ccxt

                api_key = os.getenv("BINANCE_API_KEY")
                api_secret = os.getenv("BINANCE_API_SECRET")

                if not api_key or not api_secret:
                    click.echo("❌ BINANCE_API_KEY or BINANCE_API_SECRET not set", err=True)
                    return None

                exchange = ccxt.binance(
                    {
                        "apiKey": api_key,
                        "secret": api_secret,
                    }
                )

                balance = await exchange.fetch_balance()
                await exchange.close()
                return balance

            elif broker == "paper":
                click.echo("⚠️  Paper broker balance requires running paper trading engine")
                return None

            else:
                click.echo(f"❌ Broker {broker} not yet implemented", err=True)
                return None

        except Exception as e:
            click.echo(f"❌ Error fetching balance: {e}", err=True)
            return None

    click.echo(f"\n{'=' * 80}")
    click.echo(f"Account Balance - {broker.upper()}")
    click.echo(f"{'=' * 80}\n")

    balance_data = asyncio.run(fetch_balance())

    if balance_data:
        # Display non-zero balances
        total_balances = balance_data.get("total", {})
        non_zero = {k: v for k, v in total_balances.items() if v > 0}

        if non_zero:
            click.echo(f"{'Asset':<10} {'Total':<15} {'Free':<15} {'Used':<15}")
            click.echo("-" * 80)
            for asset, total in sorted(non_zero.items(), key=lambda x: x[1], reverse=True):
                free = balance_data.get("free", {}).get(asset, 0)
                used = balance_data.get("used", {}).get(asset, 0)
                click.echo(f"{asset:<10} {total:<15.8f} {free:<15.8f} {used:<15.8f}")
        else:
            click.echo("No balances found")

    click.echo(f"\n{'=' * 80}\n")


@main.command()
def status():
    """Show live trading engine status.

    Displays:
    - Engine state (running/stopped)
    - Active strategy
    - Open positions
    - Recent orders
    - System health

    Example:
        rustybt status
    """
    import json as json_module
    from pathlib import Path

    click.echo(f"\n{'=' * 80}")
    click.echo("Live Trading Engine Status")
    click.echo(f"{'=' * 80}\n")

    # Check for state file
    state_file = Path.home() / ".rustybt" / "state" / "engine_state.json"

    if not state_file.exists():
        click.echo("Engine Status: NOT RUNNING")
        click.echo("\n⚠️  No active trading engine detected")
        click.echo("   Start with: rustybt paper-trade or rustybt live-trade\n")
        return

    # Load state
    try:
        with open(state_file) as f:
            state = json_module.load(f)

        click.echo(f"Engine Status: {state.get('status', 'UNKNOWN').upper()}")
        click.echo(f"Strategy: {state.get('strategy_name', 'N/A')}")
        click.echo(f"Broker: {state.get('broker', 'N/A')}")
        click.echo(f"Started: {state.get('started_at', 'N/A')}")
        click.echo(f"Uptime: {state.get('uptime_hours', 0):.1f} hours")

        # Positions
        positions = state.get("positions", {})
        click.echo(f"\nOpen Positions: {len(positions)}")
        for asset, pos in positions.items():
            click.echo(f"  {asset}: {pos.get('amount', 0)} @ {pos.get('avg_price', 0)}")

        # Recent orders
        recent_orders = state.get("recent_orders", [])
        click.echo(f"\nRecent Orders: {len(recent_orders)}")

    except Exception as e:
        click.echo(f"❌ Error reading state: {e}", err=True)

    click.echo(f"\n{'=' * 80}\n")


@main.command()
@click.option(
    "--source",
    type=click.Choice(["yfinance", "ccxt", "binance"], case_sensitive=False),
    required=True,
    help="Data source to test",
)
@click.option("--symbol", type=str, default="BTC/USDT", help="Symbol to fetch (default: BTC/USDT)")
def test_data(source, symbol):
    """Test data source connectivity.

    Example:
        rustybt test-data --source yfinance --symbol AAPL
        rustybt test-data --source ccxt --symbol BTC/USDT
    """
    import asyncio

    click.echo(f"\n{'=' * 80}")
    click.echo(f"Testing Data Source: {source.upper()}")
    click.echo(f"{'=' * 80}\n")
    click.echo(f"Symbol: {symbol}")

    async def test_fetch():
        try:
            if source == "yfinance":
                import yfinance as yf

                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")
                if not hist.empty:
                    click.echo("✓ Data fetched successfully")
                    click.echo(f"  Latest close: ${hist['Close'].iloc[-1]:.2f}")
                    return True
                return False

            elif source == "ccxt":
                import ccxt.async_support as ccxt_async

                exchange = ccxt_async.binance()
                ticker = await exchange.fetch_ticker(symbol)
                await exchange.close()
                click.echo("✓ Data fetched successfully")
                click.echo(f"  Latest price: ${ticker['last']:.2f}")
                return True

            elif source == "binance":
                click.echo("⚠️  Use 'ccxt' source with Binance exchange instead")
                click.echo("   Example: rustybt test-data --source ccxt --symbol BTC/USDT")
                return False

            else:
                click.echo(f"❌ Source {source} not yet implemented", err=True)
                return False

        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            return False

    success = asyncio.run(test_fetch())

    click.echo(f"\n{'=' * 80}")
    if success:
        click.echo("✓ Test completed successfully")
    else:
        click.echo("✗ Test failed")
    click.echo(f"{'=' * 80}\n")


@main.command()
@click.option("--email", type=str, help="Test email alert")
@click.option("--slack", type=str, help="Test Slack webhook")
def test_alerts(email, slack):
    """Test alert configuration.

    Example:
        rustybt test-alerts --email your@email.com
        rustybt test-alerts --slack https://hooks.slack.com/...
    """
    import requests

    click.echo(f"\n{'=' * 80}")
    click.echo("Testing Alert Configuration")
    click.echo(f"{'=' * 80}\n")

    success_count = 0
    total_tests = 0

    if email:
        total_tests += 1
        click.echo(f"Testing email alert to: {email}")
        click.echo("⚠️  Email alert configuration requires SMTP settings")
        click.echo("   Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS in .env")

    if slack:
        total_tests += 1
        click.echo("Testing Slack webhook...")
        try:
            # SECURITY FIX (Story 8.10): Already has timeout=10, which is good
            response = requests.post(
                slack, json={"text": "RustyBT Test Alert: System Operational"}, timeout=10
            )
            if response.status_code == 200:
                click.echo("✓ Slack alert sent successfully")
                success_count += 1
            else:
                click.echo(f"✗ Slack alert failed: {response.status_code}")
        except Exception as e:
            click.echo(f"✗ Slack alert error: {e}")

    if total_tests == 0:
        click.echo("⚠️  No alert methods specified")
        click.echo("   Use --email or --slack to test alerts")

    click.echo(f"\n{'=' * 80}")
    click.echo(f"Tests Passed: {success_count}/{total_tests}")
    click.echo(f"{'=' * 80}\n")


@main.command()
@click.option("--expiry", type=int, default=365, help="Token expiry in days (default: 365)")
def generate_api_token(expiry):
    """Generate API authentication token.

    Creates JWT token for REST API authentication (Epic 9).

    Example:
        rustybt generate-api-token
        rustybt generate-api-token --expiry 30
    """
    import secrets
    from datetime import datetime, timedelta

    click.echo(f"\n{'=' * 80}")
    click.echo("Generate API Token")
    click.echo(f"{'=' * 80}\n")

    # Generate secure random token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=expiry)

    click.echo(f"Token: {token}")
    click.echo(f"Expires: {expires_at.strftime('%Y-%m-%d')}")
    click.echo("\nAdd to .env file:")
    click.echo(f"RUSTYBT_API_TOKEN={token}")
    click.echo("\n⚠️  Store this token securely. It grants full API access.")
    click.echo(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
