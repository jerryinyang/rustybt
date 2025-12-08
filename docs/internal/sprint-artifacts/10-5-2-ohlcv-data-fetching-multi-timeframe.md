# Story 10.5.2: OHLCV Data Fetching & Multi-Timeframe Support

Status: review

## Story

As a **developer**,
I want **to fetch OHLCV candlestick data from Lighter.xyz for multiple timeframes**,
So that **users can ingest historical data for backtesting**.

## Acceptance Criteria

1. **AC1:** OHLCV data fetched successfully:
   - GET `/candlesticks` endpoint called with symbol, timeframe, date range
   - Response parsed into Polars DataFrame

2. **AC2:** Multiple timeframes supported:
   - 1m, 5m, 15m, 1h, 4h, 1d timeframes
   - Timeframe parameter mapped to Lighter.xyz API format

3. **AC3:** Date range handling works:
   - start_date and end_date respected
   - Data within range returned

4. **AC4:** Pagination handled for large date ranges:
   - Multiple requests made if needed
   - Results concatenated correctly

## Tasks / Subtasks

- [ ] Task 1: Implement fetch method (AC: #1, #2, #3)
  - [ ] Create `fetch()` async method
  - [ ] Accept symbols, start_date, end_date, resolution
  - [ ] Map resolution to Lighter API format
  - [ ] Call `/candlesticks` endpoint
  - [ ] Parse response to DataFrame

- [ ] Task 2: Implement timeframe mapping (AC: #2)
  - [ ] Create timeframe mapping dictionary
  - [ ] Map rustybt format to Lighter format
  - [ ] Validate supported timeframes

- [ ] Task 3: Implement date range handling (AC: #3)
  - [ ] Convert start_date/end_date to API format
  - [ ] Handle timezone conversion if needed
  - [ ] Validate date range

- [ ] Task 4: Implement pagination (AC: #4)
  - [ ] Detect if more data available
  - [ ] Make additional requests
  - [ ] Concatenate results
  - [ ] Handle pagination limits

- [ ] Task 5: Write unit tests (AC: #1-4)
  - [ ] Test fetch with mock response
  - [ ] Test all timeframes
  - [ ] Test pagination handling
  - [ ] Test date range filtering

## Dev Notes

### Fetch Implementation

```python
async def fetch(
    self,
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    resolution: str,
) -> pl.DataFrame:
    """Fetch OHLCV data from Lighter.xyz.

    Args:
        symbols: List of symbols to fetch (e.g., ["BTC-PERP"])
        start_date: Start of date range
        end_date: End of date range
        resolution: Timeframe ("1m", "5m", "15m", "1h", "4h", "1d")

    Returns:
        Polars DataFrame with OHLCV data
    """
    lighter_resolution = self._map_resolution(resolution)
    all_data = []

    for symbol in symbols:
        symbol_data = await self._fetch_symbol(
            symbol, start_date, end_date, lighter_resolution
        )
        all_data.append(symbol_data)

    if not all_data:
        return self._empty_dataframe()

    return pl.concat(all_data)

async def _fetch_symbol(
    self,
    symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    resolution: str,
) -> pl.DataFrame:
    """Fetch data for a single symbol with pagination."""
    all_candles = []
    current_start = start_date

    while current_start < end_date:
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "from": int(current_start.timestamp()),
            "to": int(end_date.timestamp()),
            "limit": 1000,  # Max per request
        }

        response = await self._client.get("/candlesticks", params=params)
        response.raise_for_status()
        data = response.json()

        candles = data.get("candles", [])
        if not candles:
            break

        all_candles.extend(candles)

        # Move to next page
        last_timestamp = candles[-1]["timestamp"]
        current_start = pd.Timestamp(last_timestamp, unit='s') + pd.Timedelta(seconds=1)

    return self._parse_candles(all_candles, symbol)
```

### Timeframe Mapping

```python
TIMEFRAME_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "4h": "240",
    "1d": "1440",
}

def _map_resolution(self, resolution: str) -> str:
    """Map rustybt timeframe to Lighter.xyz format."""
    mapped = TIMEFRAME_MAP.get(resolution)
    if not mapped:
        raise ValueError(f"Unsupported timeframe: {resolution}")
    return mapped
```

### Architecture Patterns and Constraints

- Follow existing data adapter fetch patterns
- Return Polars DataFrame
- Use NFR6: 1 year of daily data < 30 seconds

### Prerequisites

- Story 10.5.1 must be complete (adapter skeleton exists)

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.5.2]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#NFR Performance - NFR6]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.5.2]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

<!-- Will be filled by dev agent -->

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
