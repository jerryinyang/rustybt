# Story 10.5.1: Lighter.xyz Data Adapter Skeleton & Asset Discovery

Status: review

## Story

As a **developer**,
I want **a LighterDataAdapter class that can discover available assets**,
So that **users can explore and select tradeable pairs on Lighter.xyz**.

## Acceptance Criteria

1. **AC1:** `LighterDataAdapter` class exists in `rustybt/data/adapters/lighter_adapter.py`:
   - Extends `BaseDataAdapter` ABC
   - Implements required interface methods (stubs initially)

2. **AC2:** Asset discovery works:
   - `get_available_assets()` returns list of all trading pairs
   - Each asset includes: symbol, base, quote, category (perp/spot)

3. **AC3:** Asset filtering works:
   - `get_assets_by_category(category)` filters by perp or spot
   - Symbol search/filter by pattern supported

4. **AC4:** Asset data matches Lighter.xyz API response format

## Tasks / Subtasks

- [x] Task 1: Create adapter file and class skeleton (AC: #1)
  - [x] Create `rustybt/data/adapters/lighter_adapter.py`
  - [x] Define `LighterDataAdapter` class
  - [x] Implement `BaseDataAdapter` ABC interface (stubs)
  - [x] Add API URL constants

- [x] Task 2: Implement get_available_assets (AC: #2)
  - [x] Create `get_available_assets()` async method
  - [x] Call Lighter.xyz assets/markets endpoint
  - [x] Parse response to list of asset dicts
  - [x] Include symbol, base, quote, category

- [x] Task 3: Implement get_assets_by_category (AC: #3)
  - [x] Create `get_assets_by_category()` method
  - [x] Filter assets by category (perp/spot)
  - [x] Handle case-insensitive category matching

- [x] Task 4: Implement symbol filtering (AC: #3)
  - [x] Create `filter_assets_by_pattern()` method
  - [x] Support wildcard/regex pattern matching
  - [x] Return matching assets

- [x] Task 5: Write unit tests (AC: #1-4)
  - [x] Create `tests/live/lighter/test_lighter_data.py`
  - [x] Test get_available_assets with mock
  - [x] Test filtering functions
  - [x] Test asset data structure

## Dev Notes

### Class Structure

```python
class LighterDataAdapter(BaseDataAdapter):
    """Lighter.xyz data adapter for OHLCV data ingestion.

    Fetches candlestick data from Lighter.xyz /candlesticks endpoint.
    Supports multiple timeframes and historical data retrieval.
    """

    # API endpoints
    BASE_URL = "https://mainnet.zklighter.elliot.ai/"
    TESTNET_URL = "https://testnet.zklighter.elliot.ai/"

    def __init__(self, testnet: bool = True):
        """Initialize Lighter data adapter.

        Args:
            testnet: Use testnet API (default True)
        """
        self._base_url = self.TESTNET_URL if testnet else self.BASE_URL
        self._client = httpx.AsyncClient(base_url=self._base_url)
```

### Asset Discovery Implementation

```python
async def get_available_assets(self) -> list[dict]:
    """List all tradeable pairs from Lighter.xyz.

    Returns:
        List of asset dictionaries with keys:
        - symbol: Trading pair symbol (e.g., "BTC-PERP")
        - base: Base asset (e.g., "BTC")
        - quote: Quote asset (e.g., "USD")
        - category: "perpetual" or "spot"
        - min_size: Minimum order size
        - tick_size: Price tick size
    """
    response = await self._client.get("/markets")
    response.raise_for_status()
    data = response.json()

    assets = []
    for market in data.get("markets", []):
        assets.append({
            "symbol": market["symbol"],
            "base": market.get("base_asset", market["symbol"].split("-")[0]),
            "quote": market.get("quote_asset", "USD"),
            "category": "perpetual" if "PERP" in market["symbol"] else "spot",
            "min_size": Decimal(str(market.get("min_size", "0.001"))),
            "tick_size": Decimal(str(market.get("tick_size", "0.01"))),
        })

    return assets

async def get_assets_by_category(self, category: str) -> list[dict]:
    """Filter trading pairs by category.

    Args:
        category: "perpetual" or "spot"

    Returns:
        Filtered list of assets
    """
    all_assets = await self.get_available_assets()
    return [a for a in all_assets if a["category"].lower() == category.lower()]
```

### Architecture Patterns and Constraints

From Architecture:
- Follow existing data adapter patterns (CCXTDataAdapter, PolygonAdapter)
- Use async/await for all I/O operations
- Return Decimal for financial values

### Prerequisites

- Epic 10.4 should be in progress (Lighter broker adapter provides reference)

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.5.1]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#APIs and Interfaces - LighterDataAdapter]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.5.1]

## Dev Agent Record

### Context Reference

- docs/internal/sprint-artifacts/10-5-1-lighter-data-adapter-skeleton-asset-discovery.context.xml

### Agent Model Used

- claude-opus-4-5-20251101

### Debug Log References

- Implementation completed with all acceptance criteria met

### Completion Notes List

- Created `LighterDataAdapter` class with `get_available_assets()`, `get_assets_by_category()`, and `filter_assets_by_pattern()` methods
- Used aiohttp for async HTTP client (project standard instead of httpx)
- Implemented 5-minute asset caching with TTL
- All 24 unit tests pass with mocked API responses
- Integration tests available (skipped without credentials)

### File List

- `rustybt/data/adapters/lighter_adapter.py` (created)
- `tests/live/lighter/test_lighter_data.py` (created)
- `tests/live/lighter/__init__.py` (created)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implementation completed, all ACs met | Dev Agent |
