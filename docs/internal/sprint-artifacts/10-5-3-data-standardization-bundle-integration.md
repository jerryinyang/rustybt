# Story 10.5.3: Data Standardization & Bundle Integration

Status: review

## Story

As a **developer**,
I want **Lighter.xyz data standardized to rustybt format and ingested into the bundle system**,
So that **users can store and use Lighter.xyz data like any other data source**.

## Acceptance Criteria

1. **AC1:** Data standardization works:
   - Lighter.xyz response converted to rustybt OHLCV schema
   - Column names mapped correctly
   - Timestamps normalized to UTC

2. **AC2:** Data validation works:
   - OHLCV relationship validated (low <= open,close <= high)
   - No missing required fields
   - Proper Decimal precision

3. **AC3:** Funding rate data fetchable:
   - `get_funding_rates(symbol)` returns funding rate history
   - Data returned as Polars DataFrame

4. **AC4:** Bundle integration works:
   - Data saveable to rustybt bundle system
   - Catalog metadata updated
   - Data retrievable from bundles

## Tasks / Subtasks

- [ ] Task 1: Implement standardize method (AC: #1)
  - [ ] Create `standardize()` method
  - [ ] Map column names to rustybt schema
  - [ ] Normalize timestamps to UTC
  - [ ] Convert values to Decimal

- [ ] Task 2: Implement validate method (AC: #2)
  - [ ] Create `validate()` method
  - [ ] Check OHLCV relationships
  - [ ] Check for null values
  - [ ] Return bool or raise ValidationError

- [ ] Task 3: Implement funding rates (AC: #3)
  - [ ] Create `get_funding_rates()` async method
  - [ ] Call funding rates endpoint
  - [ ] Parse to DataFrame

- [ ] Task 4: Implement bundle integration (AC: #4)
  - [ ] Create methods to save to bundle
  - [ ] Update catalog metadata
  - [ ] Test data retrieval

- [ ] Task 5: Write unit tests (AC: #1-4)
  - [ ] Test standardization
  - [ ] Test validation (valid and invalid data)
  - [ ] Test funding rates
  - [ ] Test bundle round-trip

## Dev Notes

### OHLCV Schema (from Tech Spec)

```python
LIGHTER_OHLCV_SCHEMA = {
    "timestamp": pl.Datetime("us"),
    "symbol": pl.Utf8,
    "open": pl.Decimal(precision=18, scale=8),
    "high": pl.Decimal(precision=18, scale=8),
    "low": pl.Decimal(precision=18, scale=8),
    "close": pl.Decimal(precision=18, scale=8),
    "volume": pl.Decimal(precision=18, scale=8),
}
```

### Standardize Implementation

```python
def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
    """Convert Lighter.xyz data to rustybt standard schema.

    Args:
        df: Raw data from Lighter.xyz

    Returns:
        Standardized DataFrame with rustybt schema
    """
    # Map columns
    column_map = {
        "time": "timestamp",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
    }

    df = df.rename(column_map)

    # Convert timestamp to UTC datetime
    df = df.with_columns([
        pl.col("timestamp").cast(pl.Datetime("us")).dt.replace_time_zone("UTC"),
    ])

    # Convert prices to Decimal
    for col in ["open", "high", "low", "close", "volume"]:
        df = df.with_columns([
            pl.col(col).cast(pl.Decimal(precision=18, scale=8))
        ])

    return df.select(list(LIGHTER_OHLCV_SCHEMA.keys()))
```

### Validate Implementation

```python
def validate(self, df: pl.DataFrame) -> bool:
    """Validate OHLCV data relationships and schema.

    Args:
        df: DataFrame to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If validation fails
    """
    # Check required columns
    required = set(LIGHTER_OHLCV_SCHEMA.keys())
    if not required.issubset(set(df.columns)):
        raise ValidationError(f"Missing columns: {required - set(df.columns)}")

    # Check OHLCV relationships: low <= open, close <= high
    invalid = df.filter(
        (pl.col("low") > pl.col("open")) |
        (pl.col("low") > pl.col("close")) |
        (pl.col("high") < pl.col("open")) |
        (pl.col("high") < pl.col("close"))
    )

    if len(invalid) > 0:
        raise ValidationError(f"OHLCV relationship violated in {len(invalid)} rows")

    # Check for nulls
    null_counts = df.null_count()
    if null_counts.row(0).sum() > 0:
        raise ValidationError("Null values found in data")

    return True
```

### Funding Rates

```python
async def get_funding_rates(self, symbol: str) -> pl.DataFrame:
    """Fetch funding rate history from Lighter.xyz.

    Args:
        symbol: Trading pair symbol

    Returns:
        DataFrame with columns: timestamp, symbol, funding_rate
    """
    response = await self._client.get(
        "/funding-rates",
        params={"symbol": symbol}
    )
    response.raise_for_status()
    data = response.json()

    rows = []
    for rate in data.get("rates", []):
        rows.append({
            "timestamp": pd.Timestamp(rate["timestamp"], unit='s'),
            "symbol": symbol,
            "funding_rate": Decimal(str(rate["rate"])),
        })

    return pl.DataFrame(rows)
```

### Prerequisites

- Story 10.5.2 must be complete (data fetching works)
- rustybt bundle system available

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#Data Models and Contracts - OHLCV Schema]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.5.3]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.5.3]

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
