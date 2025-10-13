"""Freshness policy factory for automatic policy selection.

Automatically selects the appropriate freshness policy based on adapter type,
data frequency, and configuration.
"""

from pathlib import Path
from typing import Any

import yaml

from rustybt.data.sources.base import DataSource
from rustybt.data.sources.freshness import (
    AlwaysStaleFreshnessPolicy,
    CacheFreshnessPolicy,
    HybridFreshnessPolicy,
    MarketCloseFreshnessPolicy,
    NeverStaleFreshnessPolicy,
    TTLFreshnessPolicy,
)


class FreshnessPolicyFactory:
    """Factory for creating freshness policies.

    Automatically selects the appropriate freshness policy based on:
    1. Adapter type (live vs historical)
    2. Data frequency (daily vs intraday)
    3. Market hours (24/7 crypto vs traditional exchanges)
    4. User configuration overrides

    Example:
        >>> source = YFinanceDataSource()
        >>> policy = FreshnessPolicyFactory.create(source, "1d")
        >>> # Returns MarketCloseFreshnessPolicy (daily equity data)
        >>>
        >>> source = CCXTDataSource("binance")
        >>> policy = FreshnessPolicyFactory.create(source, "1h")
        >>> # Returns TTLFreshnessPolicy (24/7 crypto market)
    """

    @staticmethod
    def create(
        adapter: DataSource,
        frequency: str,
        config: dict[str, Any] | None = None,
    ) -> CacheFreshnessPolicy:
        """Create freshness policy for adapter and frequency.

        Args:
            adapter: DataSource adapter
            frequency: Data frequency (e.g., "1d", "1h", "1m")
            config: Optional configuration dict (overrides defaults)

        Returns:
            CacheFreshnessPolicy instance

        Policy selection logic:
        1. Live trading adapters → AlwaysStaleFreshnessPolicy
        2. CSV adapters → NeverStaleFreshnessPolicy
        3. Daily frequency + traditional markets → MarketCloseFreshnessPolicy
        4. Intraday + traditional markets → HybridFreshnessPolicy
        5. 24/7 markets (crypto) → TTLFreshnessPolicy
        """
        config = config or {}

        # Get adapter metadata
        metadata = adapter.get_metadata()
        source_type = metadata.source_type

        # 1. Live trading: always stale (force re-fetch)
        if adapter.supports_live():
            return AlwaysStaleFreshnessPolicy()

        # 2. Static data (CSV): never stale
        if source_type == "csv":
            return NeverStaleFreshnessPolicy()

        # 3. Daily data: market close policy
        if frequency == "1d":
            # Check for config override
            if config.get(f"{source_type}.daily") == "ttl":
                ttl = config.get(f"{source_type}.daily_ttl", 86400)
                return TTLFreshnessPolicy(ttl_seconds=ttl)

            # Default for traditional markets
            if source_type in ["yfinance", "polygon", "alpaca", "alphavantage"]:
                return MarketCloseFreshnessPolicy()

            # Crypto 24/7: use TTL
            if source_type == "ccxt":
                ttl = config.get("ccxt.daily_ttl", 86400)  # 24 hours
                return TTLFreshnessPolicy(ttl_seconds=ttl)

        # 4. Hourly/minute data with market hours (traditional markets)
        if source_type in ["yfinance", "polygon", "alpaca", "alphavantage"]:
            # Check for config override
            ttl_key = f"{source_type}.{frequency}_ttl"
            if ttl_key in config:
                ttl = config[ttl_key]
                return HybridFreshnessPolicy(ttl_seconds=ttl)

            # Default TTL by frequency
            default_ttl = {"1h": 3600, "5m": 300, "1m": 300}.get(frequency, 3600)
            return HybridFreshnessPolicy(ttl_seconds=default_ttl)

        # 5. Crypto 24/7 markets: pure TTL
        if source_type == "ccxt":
            ttl_key = f"ccxt.{frequency}_ttl"
            if ttl_key in config:
                ttl = config[ttl_key]
            else:
                ttl = {"1h": 3600, "5m": 300, "1m": 300}.get(frequency, 3600)

            return TTLFreshnessPolicy(ttl_seconds=ttl)

        # Fallback: conservative 1-hour TTL
        return TTLFreshnessPolicy(ttl_seconds=3600)

    @staticmethod
    def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
        """Load freshness configuration from YAML file.

        Args:
            config_path: Path to cache_freshness.yaml (default: rustybt/config/cache_freshness.yaml)

        Returns:
            Configuration dictionary

        Example config structure:
            freshness_policies:
              yfinance:
                daily: market_close
                hourly_ttl: 3600
                minute_ttl: 300
              ccxt:
                daily_ttl: 86400
                hourly_ttl: 3600
              csv:
                daily: never_stale
        """
        if config_path is None:
            # Default config path
            import rustybt

            rustybt_root = Path(rustybt.__file__).parent
            config_path = rustybt_root / "config" / "cache_freshness.yaml"

        config_path = Path(config_path)

        # If config doesn't exist, return empty dict (use defaults)
        if not config_path.exists():
            return {}

        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        # Flatten config for easier lookup
        flattened = {}

        policies = config_data.get("freshness_policies", {})
        for source, source_config in policies.items():
            for key, value in source_config.items():
                flattened[f"{source}.{key}"] = value

        # Add calendars
        calendars = config_data.get("calendars", {})
        for source, calendar in calendars.items():
            flattened[f"{source}.calendar"] = calendar

        return flattened
