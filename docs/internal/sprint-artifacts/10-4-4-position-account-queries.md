# Story 10.4.4: Position & Account Queries

Status: review

## Story

As a **developer**,
I want **to query positions and account information from Lighter.xyz**,
So that **the system can track portfolio state**.

## Acceptance Criteria

1. **AC1:** Position query works:
   - GET `/account` called
   - Positions returned with: symbol, size (signed), entry_price, mark_price, unrealized_pnl, leverage
   - All values use Decimal precision

2. **AC2:** Account info query works:
   - Account balance and margin information returned
   - Values converted to Decimal

3. **AC3:** Position data matches `LighterPosition` dataclass from Architecture:
   - All fields populated correctly
   - Sign convention preserved (positive=long, negative=short)

## Tasks / Subtasks

- [x] Task 1: Implement get_positions method (AC: #1, #3)
  - [x] Create `get_positions()` async method
  - [x] Call `account()` via AccountApi
  - [x] Parse positions from response
  - [x] Convert to standard format with Decimal (1e8 base units)
  - [x] Preserve sign convention (positive=long, negative=short)

- [x] Task 2: Implement get_account_info method (AC: #2)
  - [x] Create `get_account_info()` async method
  - [x] Call `account()` via AccountApi
  - [x] Parse balance, margin, equity, PnL
  - [x] Convert to Decimal (1e8 base units)

- [x] Task 3: Create position parsing (AC: #3)
  - [x] `_parse_position()` method for standardization
  - [x] Include all required fields (symbol, size, entry_price, mark_price, pnl, leverage)
  - [x] Use Decimal for all financial values

- [x] Task 4: Write unit tests (AC: #1-3)
  - [x] Test get_positions with mock response
  - [x] Test get_account_info with mock
  - [x] Test short position sign convention
  - [x] Test connection required

## Dev Notes

### Get Positions Implementation

```python
async def get_positions(self) -> list[dict]:
    """Get current positions from Lighter.xyz.

    Returns:
        List of positions with standardized fields.
        Size is signed: positive=long, negative=short
    """
    await self._check_request_rate_limit()

    response = await self._client.get(
        "/account",
        params={"account": self._wallet_address}
    )
    response.raise_for_status()
    data = response.json()

    positions = []
    for pos in data.get("positions", []):
        # Size is signed: positive for long, negative for short
        size = Decimal(str(pos["size"]))
        if pos.get("side", "").lower() == "short":
            size = -abs(size)

        positions.append({
            "symbol": pos["symbol"],
            "size": size,
            "entry_price": Decimal(str(pos["entry_price"])),
            "mark_price": Decimal(str(pos["mark_price"])),
            "unrealized_pnl": Decimal(str(pos["unrealized_pnl"])),
            "leverage": Decimal(str(pos.get("leverage", "1"))),
        })

    return positions
```

### LighterPosition Dataclass

From Architecture document:
```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class LighterPosition:
    """Position data from Lighter.xyz.

    Attributes:
        symbol: Trading pair symbol (e.g., "BTC-PERP")
        size: Position size (signed: positive=long, negative=short)
        entry_price: Average entry price
        mark_price: Current mark price
        unrealized_pnl: Unrealized profit/loss
        leverage: Position leverage
    """
    symbol: str
    size: Decimal  # Signed: positive=long, negative=short
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: Decimal
```

### Get Account Info Implementation

```python
async def get_account_info(self) -> dict[str, Decimal]:
    """Get account balance and margin information.

    Returns:
        Dict with account info:
        - balance: Total account balance
        - available_margin: Available margin for new positions
        - used_margin: Margin used by open positions
    """
    await self._check_request_rate_limit()

    response = await self._client.get(
        "/account",
        params={"account": self._wallet_address}
    )
    response.raise_for_status()
    data = response.json()

    return {
        "balance": Decimal(str(data.get("balance", "0"))),
        "available_margin": Decimal(str(data.get("available_margin", "0"))),
        "used_margin": Decimal(str(data.get("used_margin", "0"))),
        "equity": Decimal(str(data.get("equity", "0"))),
    }
```

### Architecture Patterns and Constraints

From Tech Spec:
- All financial values MUST use Decimal type
- Precision=18, scale=8 for financial values
- Sign convention: positive=long, negative=short

### Prerequisites

- Story 10.4.1 must be complete (connection works)

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#Data Models and Contracts - LighterPosition]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.4.4]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.4.4]

## Dev Agent Record

### Context Reference

- `docs/internal/sprint-artifacts/10-4-4-position-account-queries.context.xml`

### Agent Model Used

Claude claude-opus-4-5-20251101

### Debug Log References

- Implemented get_account_info() using AccountApi.account()
- Implemented get_positions() with _parse_position() helper
- All financial values converted from base units (1e8) to Decimal
- Sign convention: is_long=False results in negative size

### Completion Notes List

- ✅ `get_account_info()` returns balance, available_margin, used_margin, equity, unrealized_pnl
- ✅ `get_positions()` returns list with symbol, size (signed), entry_price, mark_price, unrealized_pnl, leverage
- ✅ `_parse_position()` handles both dict and object response formats
- ✅ 4 unit tests covering account info, positions, short positions, connection check

### File List

| File | Action |
|------|--------|
| `rustybt/live/brokers/lighter_adapter.py` | Modified |
| `tests/live/lighter/test_lighter_broker.py` | Modified |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implementation complete, 4 tests passing | Dev Agent |
