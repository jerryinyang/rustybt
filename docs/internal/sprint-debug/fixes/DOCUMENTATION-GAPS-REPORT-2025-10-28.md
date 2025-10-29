# Documentation Gaps Report - Recent Fixes

**Date**: 2025-10-28
**Scope**: Last 3 merged fixes (Fix 1, Fix 2, Fix 3)
**Purpose**: Identify user-facing changes that need documentation updates

---

## Executive Summary

Reviewed 3 recently merged fixes to identify user-facing changes requiring documentation. Found **2 CRITICAL documentation gaps** that affect users directly:

1. **Fix 3**: New `asset_type` parameter in `ingest_to_bundle()` - **NOT DOCUMENTED**
2. **Fix 3**: Automatic calendar selection based on asset type - **NOT DOCUMENTED**

**Fix 1** and **Fix 2** are internal improvements with no user-facing documentation needs.

---

## Fix-by-Fix Analysis

### ✅ Fix 1: Conditional Import Type Hints (20251027-101501)

**Type**: Developer Experience Improvement
**User Impact**: NONE (transparent)
**Documentation Needed**: ❌ NONE

**What Changed**:
- Added TYPE_CHECKING imports for IDE autocomplete
- Added `.pyi` stub files for better type hints
- Added `algorithm.pyi` for class-based strategy type hints

**Why No Docs Needed**:
- Purely improves IDE experience (autocomplete, type checking)
- No API changes
- No behavioral changes
- Users don't need to know about implementation details

---

### ✅ Fix 2: Bundle SID Mapping Mismatch (20251027-184838)

**Type**: Internal Bug Fix
**User Impact**: Transparent (automatic)
**Documentation Needed**: ❌ NONE

**What Changed**:
- Fixed SID mismatch between parquet files and database
- Added `sid` parameter to `BundleMetadata.add_symbol()` (internal API)
- Added `get_next_symbol_id()` method (internal API)
- Updated `build_symbol_sid_map()` to use database (internal)

**Why No Docs Needed**:
- All changes are internal implementation details
- Users don't interact with SIDs directly
- Fix is backward compatible and automatic
- `BundleMetadata` is an internal API, not user-facing
- Users should never call `add_symbol()` directly

**User Benefit** (transparent):
- Programmatically ingested bundles now work correctly
- No action required from users

---

### 🔴 Fix 3: Forex Calendar Mismatch (20251028-220437)

**Type**: Feature Enhancement + Bug Fix
**User Impact**: HIGH (new parameter, new behavior)
**Documentation Needed**: ✅ YES - CRITICAL

#### Changes Requiring Documentation

#### 1. New `asset_type` Parameter in `ingest_to_bundle()`

**Status**: 🔴 **NOT DOCUMENTED**

**API Signature** (new):
```python
source.ingest_to_bundle(
    bundle_name="forex-data",
    symbols=["EURUSD=X", "GBPUSD=X"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="forex"  # ← NEW PARAMETER
)
```

**What It Does**:
- Optional parameter to explicitly specify asset type
- Valid values: `"forex"`, `"crypto"`, `"equity"`, `"future"`
- If not provided, framework infers from symbol patterns
- Used to determine appropriate trading calendar

**Why Users Need To Know**:
1. **Forex users MUST use it** for correct calendar assignment
2. **Crypto users SHOULD use it** to get 24/7 calendar
3. Ensures strategies run on correct trading days
4. Prevents `NotSessionError` on valid trading days

**Example Use Cases**:
- Forex bundles: Use `asset_type="forex"` to get 24/5 calendar
- Crypto bundles: Use `asset_type="crypto"` to get 24/7 calendar
- Stock bundles: Use `asset_type="equity"` (or omit, will be inferred)

**Current Documentation Gap**:
- ❌ `docs/guides/data-ingestion.md` - NO mention of `asset_type`
- ❌ `docs/api/datasource-api.md` - NO mention of `asset_type`
- ❌ All example code shows ingestion without `asset_type`

---

#### 2. Automatic Calendar Selection Based on Asset Type

**Status**: 🔴 **NOT DOCUMENTED**

**What Changed**:
Bundles now automatically get appropriate trading calendars:

| Asset Type | Calendar | Trading Hours |
|------------|----------|---------------|
| `forex` | 24/5 | Sunday evening - Friday evening |
| `crypto` | 24/7 | Continuous (no holidays) |
| `equity` | XNYS | NYSE business hours (default) |
| `future` | XNYS | NYSE business hours (default) |

**Why Users Need To Know**:
1. **Behavior change**: Forex/crypto bundles now use different calendars
2. **Date validation**: Framework validates strategy dates against bundle calendar
3. **Automatic adjustment**: Invalid dates are adjusted to nearest valid date with warning
4. **Migration**: Existing bundles default to XNYS (may need re-ingestion)

**Example Scenarios**:

**Before (Bug)**:
```python
# Forex bundle with XNYS calendar
source.ingest_to_bundle(
    bundle_name="forex-1d",
    symbols=["EURUSD=X"],
    start=pd.Timestamp("2023-01-02"),  # NYSE holiday (New Year's observed)
    ...
)
# Result: NotSessionError - January 2, 2023 rejected
```

**After (Fixed)**:
```python
# Forex bundle with 24/5 calendar
source.ingest_to_bundle(
    bundle_name="forex-1d",
    symbols=["EURUSD=X"],
    start=pd.Timestamp("2023-01-02"),  # Valid forex day (Monday)
    frequency="1d",
    asset_type="forex"  # Assigns 24/5 calendar
)
# Result: SUCCESS - January 2 is valid for forex
```

**Current Documentation Gap**:
- ❌ NO explanation of calendar selection logic
- ❌ NO documentation of 24/5 and 24/7 calendars
- ❌ NO migration guide for existing forex/crypto bundles
- ❌ NO examples showing `asset_type` usage

---

#### 3. Automatic Date Adjustment (New Feature)

**Status**: 🔴 **NOT DOCUMENTED**

**What It Does**:
Framework now automatically adjusts requested dates to calendar boundaries:

```python
source.ingest_to_bundle(
    bundle_name="forex-data",
    symbols=["EURUSD=X"],
    start=pd.Timestamp("2000-01-01"),  # Before 24/5 calendar start
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="forex"
)
# WARNING: Adjusted start date from 2000-01-01 to 2005-10-28 (24/5 calendar start)
```

**Why Users Need To Know**:
1. Prevents confusing "date not found" errors
2. Clear warnings explain why dates were adjusted
3. Users understand why they get less data than requested
4. Helps users choose appropriate date ranges

**Current Documentation Gap**:
- ❌ NO mention of automatic date adjustment
- ❌ NO explanation of calendar boundaries
- ❌ NO warning message documentation

---

#### 4. Migration Requirements for Existing Bundles

**Status**: 🔴 **NOT DOCUMENTED**

**Impact on Existing Users**:
- Existing forex/crypto bundles have NULL calendar (defaults to XNYS)
- Will still work but with wrong calendar behavior
- Should re-ingest to get correct calendar

**Migration Path** (needs documentation):
```python
# For existing forex bundles, re-ingest with asset_type
source = DataSourceRegistry.get_source("yfinance")
source.ingest_to_bundle(
    bundle_name="forex-1d",  # Overwrites existing bundle
    symbols=["EURUSD=X", "GBPUSD=X", ...],
    start=pd.Timestamp("2005-10-28"),  # 24/5 calendar start
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="forex"  # ← Critical: assigns 24/5 calendar
)
```

**Current Documentation Gap**:
- ❌ NO migration instructions for existing bundles
- ❌ NO explanation of backward compatibility behavior
- ❌ NO guidance on when re-ingestion is needed

---

## Required Documentation Updates

### CRITICAL: Update Data Ingestion Guide

**File**: `docs/guides/data-ingestion.md`

**Required Changes**:

1. **Add `asset_type` parameter to all examples**:
   ```python
   # Forex example
   source.ingest_to_bundle(
       bundle_name="forex-daily",
       symbols=["EURUSD=X", "GBPUSD=X"],
       start=pd.Timestamp("2020-01-01"),
       end=pd.Timestamp("2023-12-31"),
       frequency="1d",
       asset_type="forex"  # ← ADD THIS
   )

   # Crypto example
   source.ingest_to_bundle(
       bundle_name="crypto-hourly",
       symbols=["BTC/USDT", "ETH/USDT"],
       start=pd.Timestamp("2024-01-01"),
       end=pd.Timestamp("2024-12-31"),
       frequency="1h",
       asset_type="crypto"  # ← ADD THIS
   )
   ```

2. **Add new section: "Asset Types and Trading Calendars"**:
   - Explain calendar selection logic
   - List supported asset types
   - Show calendar mapping table
   - Explain why it matters

3. **Add new section: "Automatic Date Adjustment"**:
   - Explain boundary adjustment
   - Show example warnings
   - Guide users on choosing dates

4. **Add new section: "Migrating Existing Bundles"**:
   - Explain backward compatibility
   - Provide re-ingestion instructions
   - Show how to check bundle calendar

---

### CRITICAL: Update DataSource API Reference

**File**: `docs/api/datasource-api.md`

**Required Changes**:

1. **Update `ingest_to_bundle()` signature**:
   ```python
   def ingest_to_bundle(
       self,
       bundle_name: str,
       symbols: list[str],
       start: pd.Timestamp,
       end: pd.Timestamp,
       frequency: str,
       asset_type: str | None = None,  # ← ADD THIS
       **kwargs
   ) -> Path:
   ```

2. **Document `asset_type` parameter**:
   ```
   asset_type: Optional asset type override ('forex', 'crypto', 'equity', 'future').
              If None, will be inferred from symbol patterns.
              Used to determine appropriate trading calendar.
   ```

3. **Add parameter descriptions table**:
   | Parameter | Type | Required | Description |
   |-----------|------|----------|-------------|
   | `asset_type` | `str | None` | No | Asset type for calendar selection |

4. **Update all adapter examples** to include `asset_type`

---

### CRITICAL: Update CLI Documentation

**File**: `docs/guides/data-ingestion.md` (CLI section)

**Required Changes**:

Add `--asset-type` flag to CLI examples:
```bash
# Forex ingestion
rustybt ingest-unified yfinance \
    --symbols EURUSD=X,GBPUSD=X \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --frequency 1d \
    --bundle forex-1d \
    --asset-type forex  # ← ADD THIS

# Crypto ingestion
rustybt ingest-unified ccxt \
    --exchange binance \
    --symbols BTC/USDT,ETH/USDT \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --frequency 1h \
    --bundle crypto-hourly \
    --asset-type crypto  # ← ADD THIS
```

---

### HIGH: Create New Guide

**File**: `docs/guides/trading-calendars.md` (NEW)

**Content**:
1. Introduction to trading calendars
2. Calendar types (24/5, 24/7, XNYS, etc.)
3. Asset type to calendar mapping
4. How calendars affect backtesting
5. Common calendar-related errors and solutions
6. Advanced: Custom calendars

---

## Priority Summary

### Must-Have (CRITICAL - Blocks Users)
1. ✅ Add `asset_type` to data ingestion examples
2. ✅ Document calendar selection logic
3. ✅ Update API reference with new parameter
4. ✅ Add migration guide for existing bundles

### Should-Have (HIGH - Improves UX)
1. ⚠️ Create trading calendars guide
2. ⚠️ Add troubleshooting section for calendar errors
3. ⚠️ Document date adjustment behavior

### Nice-to-Have (MEDIUM - Completeness)
1. 📝 Add visual diagram of calendar types
2. 📝 Add FAQ section for calendar questions
3. 📝 Document calendar boundaries for each type

---

## Affected Documentation Files

### Files Requiring Updates
1. ✏️ `docs/guides/data-ingestion.md` - **CRITICAL**
2. ✏️ `docs/api/datasource-api.md` - **CRITICAL**
3. ✏️ `docs/guides/quickstart.md` - **HIGH** (if has ingestion examples)
4. ✏️ `docs/index.md` - **MEDIUM** (if has ingestion examples)

### Files to Create
1. 📄 `docs/guides/trading-calendars.md` - **HIGH**
2. 📄 `docs/migration/forex-crypto-calendar-migration.md` - **HIGH**

---

## Estimated Effort

**Documentation Updates**:
- Update existing examples: 30-45 minutes
- Add new sections: 60-90 minutes
- Create new guide: 90-120 minutes
- Review and testing: 30 minutes

**Total**: ~3-4 hours

---

## Verification Checklist

After documentation updates, verify:
- [ ] All code examples include `asset_type` where appropriate
- [ ] All adapters (yfinance, ccxt, alpaca, etc.) documented
- [ ] CLI examples updated with `--asset-type` flag
- [ ] Migration instructions tested with actual bundle
- [ ] Calendar behavior clearly explained
- [ ] Date adjustment warnings documented
- [ ] Examples tested and verified to work
- [ ] Documentation builds without warnings: `mkdocs build --strict`

---

## Recommendations

1. **Immediate**: Update critical examples (30 min)
   - Add `asset_type` to forex/crypto examples in data-ingestion.md
   - Update API reference with parameter documentation

2. **Short-term**: Complete comprehensive updates (2-3 hours)
   - Add calendar selection section
   - Create migration guide
   - Update all examples consistently

3. **Long-term**: Create dedicated guide (1-2 hours)
   - Trading calendars guide
   - Advanced calendar usage
   - Troubleshooting section

---

## Impact Assessment

**If Not Documented**:
- ❌ Users won't know about `asset_type` parameter
- ❌ Forex strategies will fail on NYSE holidays
- ❌ Crypto strategies will fail on weekends
- ❌ Existing bundles will use wrong calendar
- ❌ Users will encounter confusing errors
- ❌ Support burden increases

**If Documented**:
- ✅ Clear guidance for forex/crypto ingestion
- ✅ Users understand calendar behavior
- ✅ Smooth migration path for existing bundles
- ✅ Reduced support questions
- ✅ Professional, complete documentation

---

## Next Steps

1. Review this report with stakeholders
2. Prioritize documentation updates
3. Assign documentation tasks
4. Execute updates with testing
5. Deploy updated documentation
6. Notify users of new features (changelog/release notes)

---

**Report Completed**: 2025-10-28
**By**: Claude Code (AI Agent)
**Status**: Ready for action
