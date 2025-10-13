"""Data feed integration for live trading.

This module manages market data subscriptions and converts broker data to
MarketDataEvent objects for the event queue.
"""

import asyncio
from decimal import Decimal

import structlog

from rustybt.assets import Asset
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.events import MarketDataEvent

logger = structlog.get_logger()


class DataFeed:
    """Manages market data subscriptions and event generation."""

    def __init__(self, broker_adapter: BrokerAdapter) -> None:
        """Initialize data feed.

        Args:
            broker_adapter: Broker adapter for market data
        """
        self._broker = broker_adapter
        self._subscribed_assets: set[Asset] = set()
        self._running = False
        self._reconnect_delay = 5  # seconds

    async def subscribe(self, assets: list[Asset]) -> None:
        """Subscribe to market data for assets.

        Args:
            assets: List of assets to subscribe to

        Raises:
            BrokerError: If subscription fails
        """
        new_assets = [asset for asset in assets if asset not in self._subscribed_assets]

        if not new_assets:
            logger.debug("assets_already_subscribed", count=len(assets))
            return

        await self._broker.subscribe_market_data(new_assets)
        self._subscribed_assets.update(new_assets)

        logger.info(
            "market_data_subscribed",
            assets=[asset.symbol for asset in new_assets],
            total_subscriptions=len(self._subscribed_assets),
        )

    async def unsubscribe(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data.

        Args:
            assets: List of assets to unsubscribe from

        Raises:
            BrokerError: If unsubscribe fails
        """
        subscribed = [asset for asset in assets if asset in self._subscribed_assets]

        if not subscribed:
            logger.debug("assets_not_subscribed", count=len(assets))
            return

        await self._broker.unsubscribe_market_data(subscribed)
        self._subscribed_assets.difference_update(subscribed)

        logger.info(
            "market_data_unsubscribed",
            assets=[asset.symbol for asset in subscribed],
            remaining_subscriptions=len(self._subscribed_assets),
        )

    async def get_next_market_data(self) -> MarketDataEvent:
        """Fetch next market data update and convert to event.

        This is a blocking call that waits for the next market data update.

        Returns:
            MarketDataEvent

        Raises:
            BrokerError: If data fetch fails
        """
        data = await self._broker.get_next_market_data()

        if data is None:
            raise ValueError("No market data available")

        # Convert broker data to MarketDataEvent
        event = MarketDataEvent(
            asset_symbol=data["asset"],
            open=Decimal(str(data["open"])),
            high=Decimal(str(data["high"])),
            low=Decimal(str(data["low"])),
            close=Decimal(str(data["close"])),
            volume=Decimal(str(data["volume"])),
            bar_timestamp=data["timestamp"],
        )

        logger.debug(
            "market_data_received",
            asset=event.asset_symbol,
            close=str(event.close),
            timestamp=str(event.bar_timestamp),
        )

        return event

    async def start_monitoring(self) -> None:
        """Start connection monitoring and auto-reconnect loop."""
        self._running = True
        logger.info("data_feed_monitoring_started")

        while self._running:
            if not self._broker.is_connected():
                logger.warning("broker_disconnected_reconnecting")
                try:
                    await self._broker.connect()
                    # Re-subscribe to assets after reconnect
                    if self._subscribed_assets:
                        await self._broker.subscribe_market_data(list(self._subscribed_assets))
                    logger.info("broker_reconnected")
                except Exception as e:
                    logger.error(
                        "reconnection_failed",
                        error=str(e),
                        retry_delay=self._reconnect_delay,
                    )

            await asyncio.sleep(self._reconnect_delay)

    async def stop_monitoring(self) -> None:
        """Stop connection monitoring."""
        self._running = False
        logger.info("data_feed_monitoring_stopped")

    def is_subscribed(self, asset: Asset) -> bool:
        """Check if subscribed to asset.

        Args:
            asset: Asset to check

        Returns:
            True if subscribed, False otherwise
        """
        return asset in self._subscribed_assets

    def get_subscribed_assets(self) -> list[Asset]:
        """Get list of subscribed assets.

        Returns:
            List of subscribed assets
        """
        return list(self._subscribed_assets)
