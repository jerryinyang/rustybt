# Epic 9: Databento Adapter Definition Integration

**Author:** .smirk
**Date:** 2025-12-02
**Status:** Draft
**Priority:** HIGH

---

## Epic Goal

Integrate optional Definition dataset support into the Databento adapter, enabling enhanced metadata-driven filtering and enrichment when Definition data is available alongside OHLCV packages. The adapter must continue working without Definition datasets (current behavior), with Definition providing an optional enhancement layer.

## Business Value

- **Local data ingestion:** Ingest CME and NASDAQ datasets with full metadata into local bundles
- **Reusable infrastructure:** Parsing code becomes reusable for future adapter enhancements
- **Optional enhancement:** Definition unlocks advanced filtering without breaking existing workflows
- **Metadata-driven filtering:** Enable User-Defined Spread filtering, instrument class selection, and contract metadata access when Definition is available

## Architectural Principle

```
┌─────────────────────────────────────────────────────────────┐
│                   DatabentoAdapter                          │
├─────────────────────────────────────────────────────────────┤
│  OHLCV Package (required)                                   │
│  ├── Works standalone (current behavior)                    │
│  └── Produces standard OHLCV bundle                         │
├─────────────────────────────────────────────────────────────┤
│  Definition Package (optional)                              │
│  ├── When provided: enables metadata-driven features        │
│  │   ├── include_user_defined_spreads: bool                 │
│  │   ├── instrument_class_filter: list[str]                 │
│  │   ├── Parent symbol resolution                           │
│  │   └── Contract metadata enrichment                       │
│  └── When absent: features gracefully disabled              │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Existing Databento adapter at `rustybt/data/adapters/databento_adapter.py`
- Available data packages:
  - CME: `GLBX-CME-DEFINITION.zip` (1.16 GB), `GLBX-CME-1D.zip`, `GLBX-CME-1H.zip`
  - NASDAQ: `NASDAQ-DEFINITION.zip` (5.32 GB), `NASDAQ-1D.zip`

---

## Story 9.1: Exploration & Documentation of Existing Infrastructure

As a **developer preparing to enhance the Databento adapter**,
I want **to explore and document the existing adapter infrastructure and available Definition files**,
So that **I can make targeted implementation decisions for the remaining stories**.

### Acceptance Criteria

**Given** the existing Databento adapter codebase
**When** I analyze the current implementation
**Then** I document:
  - Current `DatabentoConfig` structure and all existing options
  - OHLCV parsing flow (`_parse_ohlcv_csv`, `_decompress_zstd`, etc.)
  - Symbology handling (`_parse_symbology_*` methods)
  - Bundle output format and metadata structure
  - Extension points for Definition integration

**Given** the available Definition packages (CME and NASDAQ)
**When** I explore the file structure and sample data
**Then** I document:
  - Package structure (ZIP contents, file naming conventions)
  - Sample Definition file analysis (extract 1-2 daily files, examine schema)
  - CME vs NASDAQ schema differences (columns present/absent)
  - `condition.json` structure and purpose
  - Data volume estimates (rows per day, date range coverage)

**And** I identify integration touchpoints:
  - Where Definition loading should hook into existing flow
  - Which existing methods need modification vs new methods needed
  - Config changes required (`DatabentoConfig` additions)
  - Potential breaking changes (if any) and mitigation

**And** I produce a technical exploration document:
  - `databento/docs/exploration-existing-infrastructure.md`
  - Includes code snippets, file paths, and architecture notes
  - Serves as reference for Stories 9.2-9.5

### Technical Notes

**Files to analyze:**
- `rustybt/data/adapters/databento_adapter.py` - Main adapter (~900 lines)
- `rustybt/data/adapters/utils.py` - Shared utilities
- `databento/docs/definition_dataset_structure.md` - Existing schema docs
- `databento/docs/implementation_flaws_and_recommendations.md` - Improvement roadmap

**Definition packages to explore:**
- `databento/CME packages/GLBX-CME-DEFINITION.zip`
- `databento/NASDAQ-DEFINITION.zip`

**Exploration tasks:**
```bash
# Extract and examine CME Definition structure
unzip -l "GLBX-CME-DEFINITION.zip" | head -50
# Extract single day for analysis
unzip -p "GLBX-CME-DEFINITION.zip" "glbx-mdp3-20231001.definition.csv.zst" | zstd -d | head -100

# Same for NASDAQ
unzip -l "NASDAQ-DEFINITION.zip" | head -50
```

**Key questions to answer:**
1. How does current `_find_data_files()` work? Can it be extended for Definition?
2. What's the symbology → Definition relationship? Overlap? Replacement?
3. How are instrument_ids currently handled? Composite key format?
4. What bundle metadata exists? Where would Definition metadata fit?

**Output document structure:**
```markdown
# Databento Adapter Exploration

## 1. Current Adapter Architecture
### 1.1 DatabentoConfig
### 1.2 Ingestion Flow
### 1.3 Bundle Output Format

## 2. Definition Package Analysis
### 2.1 CME Package Structure
### 2.2 NASDAQ Package Structure
### 2.3 Schema Comparison

## 3. Integration Plan
### 3.1 Extension Points
### 3.2 New Methods Required
### 3.3 Config Changes
### 3.4 Risk Assessment
```

**Prerequisites:** None (first story in epic)

---

## Story 9.2: CME Definition Parsing & Schema Understanding

As a **developer working with CME futures data**,
I want **to implement CME Definition dataset parsing based on exploration findings**,
So that **I can extract instrument metadata and build reusable parsing infrastructure**.

### Acceptance Criteria

**Given** the CME Definition package `GLBX-CME-DEFINITION.zip`
**When** I extract and parse the Definition files
**Then** I understand the complete schema (all 65 columns documented)

**And** I can parse daily Definition files (`glbx-mdp3-{YYYYMMDD}.definition.csv.zst`)
**And** I can decompress zstd-compressed CSV files
**And** I can extract key fields:
  - `instrument_id`, `raw_symbol`, `symbol`, `asset`
  - `instrument_class` (F/C/P/S/T)
  - `user_defined_instrument` (Y/N)
  - `underlying_id` for parent relationships
  - `expiration`, `activation`, `strike_price`
  - `min_price_increment`, `contract_multiplier`

**And** I document schema findings including:
  - Column types and valid values
  - Instrument class distribution
  - User-Defined Spread identification patterns
  - Parent/child relationship structure via `underlying_id`

**And** parsing code is structured for reuse in `databento_adapter.py`

### Technical Notes

**Files to create/modify:**
- `rustybt/data/adapters/databento_adapter.py` - Add Definition parsing methods
- `databento/docs/definition_dataset_structure.md` - Update with parsing findings

**Key implementation:**
```python
def _parse_definition_file(self, file_path: Path) -> pl.DataFrame:
    """Parse a single Definition CSV file.

    Returns DataFrame with instrument metadata indexed by instrument_id.
    """

def _load_definition_for_date(self, date: pd.Timestamp) -> Optional[pl.DataFrame]:
    """Load Definition data for a specific date.

    Returns None if Definition package not configured.
    """
```

**CME Definition file pattern:** `glbx-mdp3-{YYYYMMDD}.definition.csv.zst`

**Prerequisites:** Story 9.1 (exploration document provides integration plan)

---

## Story 9.3: CME Data Ingestion & Bundle Verification

As a **developer needing CME futures data locally**,
I want **to ingest CME OHLCV data with optional Definition enrichment into a local bundle**,
So that **I have correctly represented CME data available for backtesting**.

### Acceptance Criteria

**Given** CME OHLCV package(s) and optionally the Definition package
**When** I run the Databento adapter ingestion
**Then** OHLCV data is ingested into a local bundle (works without Definition)

**Given** Definition package IS provided via `definition_package_path` config
**When** ingestion runs
**Then** Definition metadata is available for filtering and enrichment
**And** `include_user_defined_spreads=False` excludes instruments where `user_defined_instrument='Y'` or `instrument_class='T'`
**And** `include_user_defined_spreads=True` (default) includes all instruments
**And** enriched bundle includes metadata columns when Definition available

**Given** Definition package is NOT provided
**When** ingestion runs
**Then** adapter works exactly as before (current behavior preserved)
**And** filtering options that require Definition are ignored with warning

**Verification checklist:**
- [ ] Bundle contains expected instruments for date range
- [ ] OHLCV values match source data (spot check)
- [ ] instrument_id uniqueness preserved
- [ ] With Definition: UDS filtering works correctly
- [ ] With Definition: Metadata columns populated
- [ ] Without Definition: Existing behavior unchanged

### Technical Notes

**Files to modify:**
- `rustybt/data/adapters/databento_adapter.py`

**Config additions:**
```python
@dataclass
class DatabentoConfig:
    # ... existing fields ...
    definition_package_path: Optional[Path] = None
    include_user_defined_spreads: bool = True  # Only applies when Definition available
```

**Graceful degradation:**
```python
if self.config.definition_package_path is None:
    if not self.config.include_user_defined_spreads:
        logger.warning(
            "include_user_defined_spreads=False requires Definition package; ignoring"
        )
```

**Prerequisites:** Story 9.2

---

## Story 9.4: NASDAQ Definition Parsing & Schema Understanding

As a **developer working with NASDAQ equity data**,
I want **to parse and understand the NASDAQ Definition dataset structure**,
So that **I can extract equity instrument metadata and extend parsing infrastructure**.

### Acceptance Criteria

**Given** the NASDAQ Definition package `NASDAQ-DEFINITION.zip`
**When** I extract and parse the Definition files
**Then** I understand the NASDAQ-specific schema differences from CME

**And** I can parse daily Definition files (`xnas-{YYYYMMDD}.definition.csv.zst`)
**And** I document NASDAQ-specific fields:
  - Equity-relevant: `exchange`, `currency`, `lot_size`
  - Fields NOT applicable: `instrument_class` (no derivatives), `underlying_id`, `strike_price`, `expiration`

**And** parsing code handles both CME and NASDAQ schemas
**And** exchange identifier prevents instrument_id collision between CME and NASDAQ

### Technical Notes

**Files to modify:**
- `rustybt/data/adapters/databento_adapter.py` - Extend Definition parsing for NASDAQ
- `databento/docs/definition_dataset_structure.md` - Add NASDAQ schema documentation

**NASDAQ Definition file pattern:** `xnas-{YYYYMMDD}.definition.csv.zst`

**Schema detection:**
```python
def _detect_definition_schema(self, df: pl.DataFrame) -> str:
    """Detect whether Definition is CME or NASDAQ based on columns/values."""
    if "instrument_class" in df.columns and df["instrument_class"].is_not_null().any():
        return "CME"
    return "NASDAQ"
```

**Collision prevention:**
```python
# Prefix instrument_id with exchange for cross-exchange uniqueness
composite_id = f"{exchange}_{instrument_id}"
```

**Prerequisites:** Story 9.2 (reuses CME parsing patterns)

---

## Story 9.5: NASDAQ Data Ingestion & Bundle Verification

As a **developer needing NASDAQ equity data locally**,
I want **to ingest NASDAQ OHLCV data with optional Definition enrichment into a local bundle**,
So that **I have correctly represented NASDAQ data available for analysis**.

### Acceptance Criteria

**Given** NASDAQ OHLCV package and optionally the Definition package
**When** I run the Databento adapter ingestion
**Then** OHLCV data is ingested into a local bundle (works without Definition)

**Given** Definition package IS provided
**When** ingestion runs
**Then** Definition metadata is available for enrichment
**And** equity-appropriate fields are populated (`exchange`, `currency`, `lot_size`)
**And** derivative-specific fields are null/absent for equities

**Given** Definition package is NOT provided
**When** ingestion runs
**Then** adapter works exactly as before (current behavior preserved)

**Verification checklist:**
- [ ] Bundle contains expected NASDAQ instruments for date range
- [ ] OHLCV values match source data (spot check)
- [ ] No instrument_id collision with CME data (if both ingested)
- [ ] With Definition: Equity metadata columns populated
- [ ] Without Definition: Existing behavior unchanged

### Technical Notes

**Files to modify:**
- `rustybt/data/adapters/databento_adapter.py`

**NASDAQ-specific considerations:**
- No UDS filtering needed (equities don't have user-defined spreads)
- No parent resolution needed (no derivatives hierarchy)
- Different metadata columns relevant (exchange, sector vs expiration, strike)

**Prerequisites:** Stories 9.3, 9.4

---

## Summary

| Story | Dataset | Focus | Key Deliverable |
|-------|---------|-------|-----------------|
| 9.1 | Both | Exploration & Documentation | Infrastructure analysis + integration plan |
| 9.2 | CME | Parse & Understand | Schema docs + reusable parsing code |
| 9.3 | CME | Ingest & Verify | Local bundle with optional Definition enrichment |
| 9.4 | NASDAQ | Parse & Understand | Extended parsing code for equity schema |
| 9.5 | NASDAQ | Ingest & Verify | Local bundle with optional Definition enrichment |

## Implementation Order

```
Story 9.1 (Exploration & Documentation)
    ↓
Story 9.2 (CME Parse)
    ↓
Story 9.3 (CME Ingest) ──→ Story 9.4 (NASDAQ Parse)
                              ↓
                          Story 9.5 (NASDAQ Ingest)
```

**Recommended sequence:**
1. Story 9.1 establishes foundation with exploration document
2. Complete CME track (9.2 → 9.3) to validate the pattern
3. Apply to NASDAQ (9.4 → 9.5) using established patterns

## Reusability

The exploration document from Story 9.1 and parsing infrastructure from Stories 9.2 and 9.4 become integrated into `databento_adapter.py` as optional Definition support:

```python
# Future usage pattern
config = DatabentoConfig(
    ohlcv_package_path=Path("GLBX-CME-1D.zip"),
    definition_package_path=Path("GLBX-CME-DEFINITION.zip"),  # Optional
    include_user_defined_spreads=False,  # Only effective with Definition
)
adapter = DatabentoAdapter(config)
bundle = adapter.ingest()  # Enriched with Definition metadata if available
```
