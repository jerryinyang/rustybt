from decimal import Decimal

import pandas as pd
import polars as pl

from rustybt.algorithm import TradingAlgorithm
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.utils import factory


class DummyAssetFinder:
    """Minimal asset finder stub for algorithm initialization."""

    def lookup_symbol(self, *args, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError

    def retrieve_asset(self, *args, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError


class InMemoryDataSource(DataSource):
    """Minimal DataSource returning deterministic data for testing."""

    def __init__(self, supports_live: bool = False) -> None:
        self._supports_live = supports_live

    async def fetch(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        closes = [Decimal("100.00") for _ in symbols]
        return pl.DataFrame(
            {
                "symbol": symbols,
                "timestamp": [start] * len(symbols),
                "date": pl.Series("date", [start.date()] * len(symbols), dtype=pl.Date),
                "open": pl.Series("open", closes, dtype=pl.Decimal(18, 8)),
                "high": pl.Series("high", closes, dtype=pl.Decimal(18, 8)),
                "low": pl.Series("low", closes, dtype=pl.Decimal(18, 8)),
                "close": pl.Series("close", closes, dtype=pl.Decimal(18, 8)),
                "volume": pl.Series(
                    "volume", [Decimal("1000000")] * len(symbols), dtype=pl.Decimal(18, 8)
                ),
            }
        )

    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs,
    ) -> None:
        raise NotImplementedError

    def get_metadata(self) -> DataSourceMetadata:
        return DataSourceMetadata(
            source_type="in-memory",
            source_url="https://example.com",
            api_version="v1",
            supports_live=self._supports_live,
        )

    def supports_live(self) -> bool:
        return self._supports_live


def _make_sim_params() -> object:
    return factory.create_simulation_parameters(
        start=pd.Timestamp("2024-01-02"),
        num_days=3,
    )


def test_trading_algorithm_builds_polars_portal_with_cache():
    sim_params = _make_sim_params()
    finder = DummyAssetFinder()
    algo = TradingAlgorithm(
        sim_params=sim_params,
        asset_finder=finder,
        data_source=InMemoryDataSource(),
        live_trading=False,
    )

    assert isinstance(algo.data_portal, PolarsDataPortal)
    assert algo.data_portal.use_cache is True
    assert algo.asset_finder is finder


def test_trading_algorithm_disables_cache_for_live_sources():
    sim_params = _make_sim_params()
    finder = DummyAssetFinder()
    algo = TradingAlgorithm(
        sim_params=sim_params,
        asset_finder=finder,
        data_source=InMemoryDataSource(supports_live=True),
        live_trading=True,
    )

    assert isinstance(algo.data_portal, PolarsDataPortal)
    assert algo.data_portal.use_cache is False
