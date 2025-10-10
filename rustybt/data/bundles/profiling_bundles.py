"""Register profiling bundles so that bundles.load() recognizes them.

These bundles are ingested via scripts/profiling/setup_profiling_data.py.
Registration here enables runtime loading in tests without importing scripts.*.
"""

from .core import register


@register("profiling-daily")
def profiling_daily_bundle(*args, **kwargs):  # pragma: no cover - load only
    raise RuntimeError(
        "profiling-daily bundle ingest is handled by scripts/profiling/setup_profiling_data.py"
    )


@register("profiling-hourly")
def profiling_hourly_bundle(*args, **kwargs):  # pragma: no cover - load only
    raise RuntimeError(
        "profiling-hourly bundle ingest is handled by scripts/profiling/setup_profiling_data.py"
    )


@register("profiling-minute")
def profiling_minute_bundle(*args, **kwargs):  # pragma: no cover - load only
    raise RuntimeError(
        "profiling-minute bundle ingest is handled by scripts/profiling/setup_profiling_data.py"
    )
