import asyncio
import logging
import sys
from pathlib import Path

import pandas as pd
import structlog

from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = structlog.get_logger()


async def ingest_nasdaq():
    """Ingest Nasdaq dataset."""

    # Paths
    base_dir = Path("databento")
    ohlcv_path = base_dir / "NASDAQ-1D.zip"
    definition_path = base_dir / "NASDAQ-DEFINITION.zip"

    if not ohlcv_path.exists():
        logger.error("ohlcv_file_not_found", path=str(ohlcv_path))
        return

    if not definition_path.exists():
        logger.error("definition_file_not_found", path=str(definition_path))
        return

    logger.info("starting_ingestion", ohlcv=str(ohlcv_path), definition=str(definition_path))

    # Config
    config = DatabentoConfig(
        data_path=str(ohlcv_path),
        definition_package_path=str(definition_path),
        use_instrument_id=True,
        symbol_format="symbol_id",
        include_user_defined_spreads=False,  # Equities only
    )

    # Ingest
    with DatabentoAdapter(config) as adapter:
        # We use the internal batched ingestion method directly for control
        # In a real CLI usage, this would be called via the bundle command

        # Discover files first to pass to batched ingestion
        ohlcv_files = adapter._find_all_ohlcv_files()

        # Ingest
        adapter._ingest_to_bundle_batched(
            bundle_name="nasdaq-1d",
            symbols=[],  # All
            start=pd.Timestamp("2010-01-01", tz="UTC"),
            end=pd.Timestamp("2025-12-31", tz="UTC"),
            frequency="1d",
            batch_size=100,  # Process 100 files at a time
            ohlcv_files=ohlcv_files,
        )

    logger.info("ingestion_complete")


if __name__ == "__main__":
    asyncio.run(ingest_nasdaq())
