#!/usr/bin/env python
#
# Copyright 2025 RustyBT Contributors
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
"""
Example: Creating a Custom Data Adapter

This example demonstrates how to create a custom data adapter for RustyBT
that fetches data from a proprietary or custom data source.

We'll implement a simple REST API adapter that could be adapted for any
custom data provider.

Key Concepts Demonstrated:
- Inheriting from DataSource base class
- Implementing required abstract methods
- Error handling and retry logic
- Data validation
- Type conversion (to Decimal)
- Registering adapter with DataSourceRegistry

Usage:
    python examples/custom_data_adapter.py
"""

import asyncio
import random
from decimal import Decimal, getcontext
from pathlib import Path

import httpx
import pandas as pd
import polars as pl
import structlog

from rustybt.data.sources.base import (
    DataSource,
    DataSourceMetadata,
    DataValidationError,
    NetworkError,
    RateLimitError,
    with_retry,
)

# Set decimal precision
getcontext().prec = 28

logger = structlog.get_logger()


class CustomAPIDataSource(DataSource):
    """Custom data source adapter for a hypothetical REST API.

    This adapter demonstrates the complete implementation of a DataSource
    for fetching OHLCV data from a custom API endpoint.

    Adapt this template for your own data sources by:
    1. Changing the API endpoint and authentication
    2. Modifying the data parsing logic
    3. Adjusting error handling for your API
    4. Updating metadata and capabilities

    Example:
        >>> source = CustomAPIDataSource(
        ...     api_url="https://api.example.com/v1",
        ...     api_key="your_api_key"
        ... )
        >>> data = await source.fetch(
        ...     symbols=["AAPL", "MSFT"],
        ...     start=pd.Timestamp("2023-01-01"),
        ...     end=pd.Timestamp("2023-12-31"),
        ...     frequency="1d"
        ... )
    """

    def __init__(
        self, api_url: str, api_key: str, rate_limit_per_second: int = 5, timeout: int = 30
    ):
        """Initialize custom data source.

        Args:
            api_url: Base URL for API (e.g., "https://api.example.com/v1")
            api_key: API authentication key
            rate_limit_per_second: Maximum requests per second
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # Initialize HTTP client
        self.client = httpx.AsyncClient(timeout=timeout)

        logger.info(
            "custom_adapter_initialized", api_url=self.api_url, rate_limit=rate_limit_per_second
        )

    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    async def fetch(
        self, symbols: list[str], start: pd.Timestamp, end: pd.Timestamp, frequency: str
    ) -> pl.DataFrame:
        """Fetch OHLCV data from custom API.

        Args:
            symbols: List of ticker symbols
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)
            frequency: Data frequency ("1d", "1h", "1m", etc.)

        Returns:
            Polars DataFrame with columns:
            - symbol: str
            - date: date (for daily) or timestamp: datetime (for intraday)
            - open: Decimal
            - high: Decimal
            - low: Decimal
            - close: Decimal
            - volume: Decimal

        Raises:
            NetworkError: If API request fails
            RateLimitError: If rate limit exceeded
            DataValidationError: If data format is invalid
        """
        logger.info(
            "fetching_data",
            symbols=symbols,
            start=start.isoformat(),
            end=end.isoformat(),
            frequency=frequency,
        )

        all_data = []

        for symbol in symbols:
            # Fetch data for each symbol
            try:
                symbol_data = await self._fetch_symbol(symbol, start, end, frequency)
                all_data.append(symbol_data)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limit exceeded
                    raise RateLimitError(
                        f"Rate limit exceeded for {symbol}", adapter="custom_api", reset_after=60.0
                    )
                elif e.response.status_code >= 500:
                    # Server error - retry
                    raise NetworkError(f"Server error for {symbol}: {e}", adapter="custom_api")
                else:
                    # Client error - don't retry
                    logger.error("api_error", symbol=symbol, status=e.response.status_code)
                    raise

            except httpx.TimeoutException as e:
                raise NetworkError(f"Timeout fetching {symbol}: {e}", adapter="custom_api")

        # Combine all symbols into single DataFrame
        if not all_data:
            return pl.DataFrame()

        df = pl.concat(all_data)

        # Validate data
        self._validate_ohlcv_data(df)

        logger.info("fetch_complete", rows=len(df), symbols=len(symbols))

        return df

    async def _fetch_symbol(
        self, symbol: str, start: pd.Timestamp, end: pd.Timestamp, frequency: str
    ) -> pl.DataFrame:
        """Fetch data for a single symbol.

        This is where you implement your API-specific logic.

        Args:
            symbol: Ticker symbol
            start: Start timestamp
            end: End timestamp
            frequency: Data frequency

        Returns:
            Polars DataFrame with OHLCV data for the symbol
        """
        # Build API request
        url = f"{self.api_url}/ohlcv/{symbol}"
        params = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "frequency": frequency,
            "format": "json",
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

        # Make API request
        response = await self.client.get(url, params=params, headers=headers)
        response.raise_for_status()

        # Parse response
        data = response.json()

        # Convert to DataFrame
        # NOTE: Adapt this to your API's response format
        if not data or "data" not in data:
            return pl.DataFrame()

        rows = []
        for record in data["data"]:
            rows.append(
                {
                    "symbol": symbol,
                    "date": (
                        pd.Timestamp(record["timestamp"]).date()
                        if frequency.endswith("d")
                        else pd.Timestamp(record["timestamp"])
                    ),
                    "open": Decimal(str(record["open"])),
                    "high": Decimal(str(record["high"])),
                    "low": Decimal(str(record["low"])),
                    "close": Decimal(str(record["close"])),
                    "volume": Decimal(str(record["volume"])),
                }
            )

        if not rows:
            return pl.DataFrame()

        # Create DataFrame with proper types
        if frequency.endswith("d"):
            # Daily data - use date
            df = pl.DataFrame(rows).with_columns(
                [
                    pl.col("date").cast(pl.Date),
                    pl.col("open").cast(pl.Decimal(18, 8)),
                    pl.col("high").cast(pl.Decimal(18, 8)),
                    pl.col("low").cast(pl.Decimal(18, 8)),
                    pl.col("close").cast(pl.Decimal(18, 8)),
                    pl.col("volume").cast(pl.Decimal(18, 8)),
                ]
            )
        else:
            # Intraday data - use timestamp
            df = (
                pl.DataFrame(rows)
                .rename({"date": "timestamp"})
                .with_columns(
                    [
                        pl.col("timestamp").cast(pl.Datetime),
                        pl.col("open").cast(pl.Decimal(18, 8)),
                        pl.col("high").cast(pl.Decimal(18, 8)),
                        pl.col("low").cast(pl.Decimal(18, 8)),
                        pl.col("close").cast(pl.Decimal(18, 8)),
                        pl.col("volume").cast(pl.Decimal(18, 8)),
                    ]
                )
            )

        return df

    def _validate_ohlcv_data(self, df: pl.DataFrame) -> None:
        """Validate OHLCV data integrity.

        Args:
            df: DataFrame to validate

        Raises:
            DataValidationError: If validation fails
        """
        if df.is_empty():
            return

        # Check required columns
        required_cols = {"symbol", "open", "high", "low", "close", "volume"}
        actual_cols = set(df.columns)

        if not required_cols.issubset(actual_cols):
            missing = required_cols - actual_cols
            raise DataValidationError(f"Missing required columns: {missing}", adapter="custom_api")

        # Validate OHLCV relationships (high >= low, etc.)
        invalid_rows = df.filter(
            (pl.col("high") < pl.col("low"))
            | (pl.col("close") > pl.col("high"))
            | (pl.col("close") < pl.col("low"))
            | (pl.col("open") > pl.col("high"))
            | (pl.col("open") < pl.col("low"))
        )

        if len(invalid_rows) > 0:
            raise DataValidationError(
                f"Found {len(invalid_rows)} rows with invalid OHLCV relationships",
                adapter="custom_api",
            )

    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs,
    ) -> Path:
        """Ingest data and create bundle.

        This uses the default bundle creation logic from adapter_bundles.

        Args:
            bundle_name: Name for the bundle
            symbols: Symbols to ingest
            start: Start date
            end: End date
            frequency: Data frequency
            **kwargs: Additional options

        Returns:
            Path to created bundle directory
        """
        from rustybt.data.bundles.adapter_bundles import ingest_from_datasource

        return ingest_from_datasource(
            datasource=self,
            bundle_name=bundle_name,
            symbols=symbols,
            start=start,
            end=end,
            frequency=frequency,
            **kwargs,
        )

    def get_metadata(self) -> DataSourceMetadata:
        """Get data source metadata.

        Returns:
            Metadata describing this data source
        """
        return DataSourceMetadata(
            source_type="custom_api",
            source_url=self.api_url,
            api_version="v1",
            supports_live=False,  # Set True if supports real-time streaming
            supported_frequencies=["1d", "1h", "5m", "1m"],
            rate_limit=300,  # Requests per minute
            requires_auth=True,
        )

    def supports_live(self) -> bool:
        """Check if source supports live streaming.

        Returns:
            True if live streaming supported, False otherwise
        """
        return False  # Change to True if you implement WebSocket streaming

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        await self.client.aclose()
        logger.info("custom_adapter_closed")


# ============================================================================
# Example Usage
# ============================================================================


class MockAPIDataSource(CustomAPIDataSource):
    """Mock version that generates fake data for demonstration.

    This removes the need for a real API endpoint to test the example.
    """

    async def _fetch_symbol(
        self, symbol: str, start: pd.Timestamp, end: pd.Timestamp, frequency: str
    ) -> pl.DataFrame:
        """Generate mock data instead of fetching from API."""
        # Generate date range
        if frequency == "1d":
            dates = pd.date_range(start=start, end=end, freq="D")
        elif frequency == "1h":
            dates = pd.date_range(start=start, end=end, freq="H")
        else:
            dates = pd.date_range(start=start, end=end, freq="5min")

        # Generate fake OHLCV data
        base_price = Decimal("100")
        rows = []

        for date in dates:
            # Random walk
            open_price = base_price + Decimal(str(random.uniform(-2, 2)))  # noqa: S311
            high_price = open_price + Decimal(str(random.uniform(0, 3)))  # noqa: S311
            low_price = open_price - Decimal(str(random.uniform(0, 3)))  # noqa: S311
            close_price = open_price + Decimal(str(random.uniform(-2, 2)))  # noqa: S311
            close_price = min(max(close_price, low_price), high_price)
            volume = Decimal(str(random.randint(100000, 1000000)))  # noqa: S311

            rows.append(
                {
                    "symbol": symbol,
                    "date": date.date() if frequency == "1d" else date,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                }
            )

            base_price = close_price

        # Create DataFrame
        if frequency == "1d":
            df = pl.DataFrame(rows).with_columns(
                [
                    pl.col("date").cast(pl.Date),
                    pl.col("open").cast(pl.Decimal(18, 8)),
                    pl.col("high").cast(pl.Decimal(18, 8)),
                    pl.col("low").cast(pl.Decimal(18, 8)),
                    pl.col("close").cast(pl.Decimal(18, 8)),
                    pl.col("volume").cast(pl.Decimal(18, 8)),
                ]
            )
        else:
            df = (
                pl.DataFrame(rows)
                .rename({"date": "timestamp"})
                .with_columns(
                    [
                        pl.col("timestamp").cast(pl.Datetime),
                        pl.col("open").cast(pl.Decimal(18, 8)),
                        pl.col("high").cast(pl.Decimal(18, 8)),
                        pl.col("low").cast(pl.Decimal(18, 8)),
                        pl.col("close").cast(pl.Decimal(18, 8)),
                        pl.col("volume").cast(pl.Decimal(18, 8)),
                    ]
                )
            )

        return df


async def main():
    """Demonstrate custom data adapter usage."""
    print("=" * 70)
    print("Custom Data Adapter Example")
    print("=" * 70)

    # Create custom adapter (using mock version for demo)
    print("\n[1/4] Initializing custom data source...")
    source = MockAPIDataSource(
        api_url="https://api.example.com/v1", api_key="mock_api_key", rate_limit_per_second=5
    )
    print("✓ Data source initialized")

    # Fetch data
    print("\n[2/4] Fetching data...")
    print("  Symbols: AAPL, MSFT")
    print("  Period: 2023-01-01 to 2023-03-31")
    print("  Frequency: 1d")

    data = await source.fetch(
        symbols=["AAPL", "MSFT"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-03-31"),
        frequency="1d",
    )

    print(f"✓ Fetched {len(data)} rows")
    print("\nSample data:")
    print(data.head(10))

    # Display metadata
    print("\n[3/4] Data source metadata:")
    metadata = source.get_metadata()
    print(f"  Type: {metadata.source_type}")
    print(f"  URL: {metadata.source_url}")
    print(f"  Supports live: {metadata.supports_live}")
    print(f"  Frequencies: {metadata.supported_frequencies}")
    print(f"  Rate limit: {metadata.rate_limit} req/min")

    # Create bundle
    print("\n[4/4] Creating bundle...")
    bundle_path = await source.ingest_to_bundle(
        bundle_name="custom-example",
        symbols=["AAPL", "MSFT"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-03-31"),
        frequency="1d",
    )
    print(f"✓ Bundle created: {bundle_path}")

    # Cleanup
    await source.close()

    print("\n" + "=" * 70)
    print("✓ Example complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Adapt CustomAPIDataSource for your API")
    print("  2. Implement authentication for your provider")
    print("  3. Add WebSocket support for live data (optional)")
    print("  4. Register adapter with DataSourceRegistry")


if __name__ == "__main__":
    asyncio.run(main())
