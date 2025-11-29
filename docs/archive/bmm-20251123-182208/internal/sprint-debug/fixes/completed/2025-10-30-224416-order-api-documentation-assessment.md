# [2025-10-30 22:44:16] - Order API Documentation Assessment

**Commit:** [Pending]
**Focus Area:** Documentation (Assessment)
**Severity:** 🟡 MEDIUM (Potential confusion, not blocking)
**Branch:** `fix/20251030-224404-order-api-documentation-assessment`

---

## ⚠️ MANDATORY PRE-FLIGHT CHECKLIST

### For Documentation Updates: Pre-Flight Checklist

- [x] **Content verified in source code**
  - [x] Located source implementation: `rustybt/api.pyi:251` (order function)
  - [x] Located source implementation: `rustybt/finance/execution.py:63-80` (MarketOrder, LimitOrder classes)
  - [x] Confirmed functionality exists as documented
  - [x] Understand actual behavior

- [x] **Technical accuracy verified**
  - [x] API signatures match source code exactly
  - [x] Both approaches (legacy and style parameter) are real
  - [x] Import paths tested and working
  - [x] NO fabricated content found

- [x] **Quality standards compliance**
  - [x] Read `docs/internal/architecture/DOCUMENTATION_QUALITY_STANDARDS.md`
  - [x] Read `docs/internal/architecture/coding-standards.md`
  - [x] Commit to zero documentation debt
  - [x] Will NOT use syntax inference without verification

- [x] **Cross-references checked**
  - [x] Identified related documentation to update
  - [x] Checked for outdated information
  - [x] Verified terminology consistency

- [x] **Testing preparation**
  - [x] Testing environment ready
  - [x] Can validate source code directly

**Documentation Pre-Flight Complete**: [x] YES [ ] NO

---

## User-Reported Issue

**User Concern:**
```
The "API Reference" and "Examples and Tutorials" guides seem to take different approaches for
Order Execution and Management. The "Examples" uses functions (order(), order_target(), and so on)
to illustrate different types of order types and strategy techniques. The API reference introduces
these order types as classes (MarketOrder, LimitOrder), and a `style` parameter for the functions;
the parameter was not mentioned in the examples (particularly "Strategy Development with RustyBT").

The assessment is to make sure neither of these approaches are a false or fabricated API.

Also, a question: does the framework allow managing trades/positions individually by the order
that created them, or positions must be managed per asset?
```

**User Scenario:**
User is trying to understand order execution API and noticed two different approaches in documentation:
1. Examples show: `order(asset, 100)` and `order(asset, 100, style=LimitOrder(150.0))`
2. API Reference shows: classes (MarketOrder, LimitOrder) with `style` parameter

User suspects one might be fabricated or outdated.

**Expected Behavior:**
Documentation should be consistent and explain both approaches clearly, with all approaches verified against source code.

**Actual Behavior:**
Both approaches exist in documentation but the relationship between them is not clearly explained.

**Impact:**
Medium - Could confuse users about correct API usage, but not blocking development.

---

## Issues Found

**Issue 1: Both approaches are REAL (not fabricated)** - ✅ VERIFIED

**Source Code Evidence:**

1. **Order function signature** (`rustybt/api.pyi:251-283`):
   ```python
   def order(asset, amount, limit_price=None, stop_price=None, style=None):
   ```

2. **Documentation in source** (rustybt/api.pyi:277-283):
   ```
   The ``limit_price`` and ``stop_price`` arguments provide shorthands for
   passing common execution styles. Passing ``limit_price=N`` is
   equivalent to ``style=LimitOrder(N)``. Similarly, passing
   ``stop_price=M`` is equivalent to ``style=StopOrder(M)``, and passing
   ``limit_price=N`` and ``stop_price=M`` is equivalent to
   ``style=StopLimitOrder(N, M)``. It is an error to pass both a ``style``
   and ``limit_price`` or ``stop_price``.
   ```

3. **Order classes exist** (`rustybt/finance/execution.py:63-99`):
   - `MarketOrder` (line 63)
   - `LimitOrder` (line 80)
   - `StopOrder`, `StopLimitOrder`, etc.

**Valid API Approaches:**

1. **Legacy/Shorthand approach** (backward compatible):
   ```python
   order(asset, 100)  # Market order (default)
   order(asset, 100, limit_price=150.0)  # Limit order
   order(asset, 100, stop_price=90.0)  # Stop order
   order(asset, 100, limit_price=150.0, stop_price=145.0)  # Stop-limit
   ```

2. **Explicit style approach** (recommended, more flexible):
   ```python
   order(asset, 100, style=MarketOrder())
   order(asset, 100, style=LimitOrder(limit_price=150.0))
   order(asset, 100, style=StopOrder(stop_price=90.0))
   order(asset, 100, style=StopLimitOrder(limit_price=150.0, stop_price=145.0))
   order(asset, 100, style=TrailingStopOrder(trail_percent=0.03))  # Only via style!
   order(asset, 100, style=BracketOrder(...))  # Only via style!
   ```

3. **CONFLICT:** Cannot use both approaches simultaneously:
   ```python
   # ❌ ERROR: Cannot pass both style and limit_price/stop_price
   order(asset, 100, limit_price=150.0, style=LimitOrder(150.0))
   ```

**Issue 2: Documentation inconsistency - Examples don't explain both approaches** - 🟡 MINOR

- `docs/api/order-management/workflows/examples.md` shows both approaches but doesn't explain they're equivalent
- Line 31: `order(context.asset, 100)` - uses default (no explanation)
- Line 61: `order(context.asset, 100, style=LimitOrder(current_price))` - uses style
- Line 67: `order(context.asset, -position.amount)` - uses default
- No mention that `limit_price` parameter is a shorthand for `style=LimitOrder(...)`

**Issue 3: Position management question** - ✅ ANSWERED

**Question:** Does the framework allow managing trades/positions individually by the order that created them, or positions must be managed per asset?

**Answer:** **Positions are managed per asset, not per individual order.**

**Source Code Evidence** (`rustybt/finance/position.py:44-149`):

1. Position class tracks:
   - `asset` - the asset held in this position
   - `amount` - total shares (aggregated from all orders)
   - `cost_basis` - **volume-weighted average price** paid per share
   - `last_sale_price` - price at last sale

2. Position.update() method (lines 121-149):
   ```python
   def update(self, txn):
       # ... aggregates multiple orders into single position
       prev_cost = self.cost_basis * self.amount
       txn_cost = txn.amount * txn.price
       total_cost = prev_cost + txn_cost
       self.cost_basis = total_cost / total_shares  # Weighted average
   ```

**Implication:** If you place multiple orders for the same asset, they are aggregated into one position with a weighted average cost basis. You cannot track or manage individual orders separately after they fill.

**To track individual trades:**
- Use order IDs returned by `order()` function
- Query order status via `get_order(order_id)` or `get_open_orders(asset)`
- Track fills via order objects in `context.blotter.orders`

But positions themselves are always per-asset aggregates.

---

## Root Cause Analysis

**Why did this issue occur:**
1. Framework supports BOTH legacy and modern approaches for backward compatibility
2. Documentation was written at different times with different conventions
3. Examples documentation doesn't explain the relationship between the two approaches
4. Users reading both docs may not realize they're equivalent approaches

**What pattern should prevent recurrence:**
1. Add a "API Compatibility" section to Examples documentation explaining both approaches
2. Create a migration guide showing legacy → modern style conversions
3. Add notes to examples showing "This can also be written as..."
4. Document position aggregation behavior clearly in position management docs

---

## Fixes Applied

**ASSESSMENT RESULT: No fixes needed - both approaches are valid and verified**

The documentation is technically accurate. Both approaches exist in the source code and work as documented.

**Recommendation for future improvement:**
1. Add clarification section to `docs/api/order-management/workflows/examples.md` explaining:
   - Two equivalent approaches (legacy shorthand vs. explicit style)
   - When to use each approach
   - That advanced order types (TrailingStop, Bracket, OCO) require style parameter

2. Add position management section explaining per-asset aggregation

**No immediate fixes required** - this is a clarification issue, not a bug or fabrication.

---

## Tests Added/Modified

N/A - Assessment only, no code changes

---

## Documentation Updated

N/A - No updates needed at this time (recommendations for future improvement listed above)

---

## Verification

- [x] All source code verified: `rustybt/api.pyi`, `rustybt/finance/execution.py`, `rustybt/finance/position.py`
- [x] API signatures match documentation exactly
- [x] Both approaches tested and work as documented
- [x] No fabricated content found
- [x] Position management behavior confirmed
- [x] Pre-flight checklist completed above

---

## Files Examined

- `docs/api/order-management/order-types.md` - API Reference (verified correct)
- `docs/api/order-management/workflows/examples.md` - Examples (verified correct, could use clarification)
- `rustybt/api.pyi:251-290` - Order function signatures (verified)
- `rustybt/finance/execution.py:34-408` - Order classes (verified)
- `rustybt/finance/position.py:44-149` - Position class (verified)

---

## Statistics

- Issues found: 0 (just clarification opportunity)
- Issues fixed: 0 (assessment only)
- Tests added: 0 (no changes needed)
- Lines changed: 0 (no changes needed)

---

## User Questions Answered

### Question 1: Are these approaches fabricated?
**Answer:** NO - Both approaches are real and verified in source code.

- ✅ `order(asset, 100)` - Real (uses MarketOrder by default)
- ✅ `order(asset, 100, limit_price=150.0)` - Real (shorthand for LimitOrder)
- ✅ `order(asset, 100, style=LimitOrder(150.0))` - Real (explicit style)
- ✅ MarketOrder, LimitOrder, StopOrder classes - Real (in rustybt/finance/execution.py)
- ✅ `style` parameter - Real (in rustybt/api.pyi:251)

### Question 2: Position management - per-order or per-asset?
**Answer:** **Per-asset aggregation**

Positions are tracked per asset with volume-weighted average cost basis. Multiple orders for the same asset are aggregated into one position. You cannot manage positions by individual order after fills.

However, you can:
- Track individual orders via order IDs
- Query order status via `get_order(order_id)`
- Access order history via `context.blotter.orders`

But positions themselves (`context.portfolio.positions[asset]`) are always per-asset aggregates.

---

## Recommendations for User

1. **Both approaches work** - Use whichever is clearer for your strategy:
   - Simple orders: `order(asset, 100, limit_price=150.0)` is fine
   - Advanced orders (Trailing, Bracket, OCO): Must use `style=` parameter

2. **Position management:**
   - Access position: `context.portfolio.positions.get(asset)`
   - Position shows aggregated amount and weighted cost basis
   - For per-order tracking, use order IDs and blotter

3. **Documentation is accurate** - No fabrication found

---

## Commit Hash

`[Pending - assessment complete, no changes needed]`

---

## Branch

`fix/20251030-224404-order-api-documentation-assessment`

---

## Notes

- **Assessment result:** Both approaches are real and verified in source code
- **No documentation bugs found** - Just opportunity for clarification
- **Position management behavior confirmed:** Per-asset aggregation with weighted cost basis
- **User can proceed with confidence** - All APIs are real and work as documented

---

**Next Steps:**
1. Share findings with user
2. Consider adding clarification section to Examples documentation (future improvement)
3. Consider adding position management behavior section (future improvement)
4. Close branch (no changes needed)

---
